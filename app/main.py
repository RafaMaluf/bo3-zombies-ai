from __future__ import annotations

import asyncio
import logging
import mimetypes
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.answer_policy import resolve_answer_intent
from app.assets import AssetManifest
from app.chat_jobs import ChatJobs, ChatJobStatus
from app.chat_service import _select_image_assets as _select_image_assets
from app.chat_service import answer_chat
from app.companion_api import companion_router
from app.companion_state import build_catalog
from app.config import settings
from app.embeddings import EmbeddingError, EmbeddingIndex, VoyageEmbeddingClient
from app.knowledge_base import KnowledgeBase
from app.language import resolve_response_language
from app.llm import LLMService
from app.media import MediaService
from app.retrieval import SearchEngine
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MapSummary,
)

logger = logging.getLogger("krono")
request_logger = logging.getLogger("uvicorn.error.krono.chat")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/webp", ".webp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asset_manifest = AssetManifest.load(settings.asset_manifest_path)
    knowledge_base = KnowledgeBase(settings.maps_dir, asset_manifest=asset_manifest)
    app.state.knowledge_base = knowledge_base
    app.state.asset_manifest = asset_manifest
    embedding_index = None
    embedding_client = None
    if settings.embeddings_configured:
        try:
            embedding_index = EmbeddingIndex.load(
                settings.embedding_index_dir,
                knowledge_base,
                expected_model=settings.voyage_model,
            )
        except EmbeddingError as error:
            logger.warning("Semantic index unavailable; BM25 fallback active: %s", error)
        else:
            embedding_client = VoyageEmbeddingClient(
                settings.voyage_api_key,
                settings.voyage_model,
            )
    app.state.search_engine = SearchEngine(
        knowledge_base,
        embedding_index=embedding_index,
        embedding_client=embedding_client,
    )
    app.state.llm = LLMService(settings)
    app.state.chat_jobs = ChatJobs()
    app.state.media = MediaService(settings.cache_dir)

    for issue in knowledge_base.issues:
        log = logger.error if issue.severity == "error" else logger.warning
        log("%s [%s] %s", issue.path, issue.code, issue.message)

    try:
        yield
    finally:
        await app.state.chat_jobs.close()


app = FastAPI(
    title="Kronochat — Black Ops III Zombies",
    version="1.0.0",
    lifespan=lifespan,
)

if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@app.middleware("http")
async def require_frontend_revalidation(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/app" or path.startswith("/app/"):
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    return response


def _kb(request: Request) -> KnowledgeBase:
    return request.app.state.knowledge_base


def _asset_url(request: Request, image_id: str, variant: str) -> str:
    manifest: AssetManifest = request.app.state.asset_manifest
    if settings.asset_base_url:
        remote_url = manifest.url(settings.asset_base_url, image_id, variant)
        if remote_url:
            return remote_url
    return f"/media/{image_id}?variant={variant}"


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse("/app/")


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    knowledge_base = _kb(request)
    stats = knowledge_base.stats
    return HealthResponse(
        status="ok" if not knowledge_base.errors else "degraded",
        llm_configured=settings.llm_configured,
        embeddings_configured=settings.embeddings_configured,
        embeddings_ready=request.app.state.search_engine.semantic_ready,
        embedding_model=(
            settings.voyage_model if request.app.state.search_engine.semantic_ready else None
        ),
        **stats,
    )


@app.get("/maps", response_model=list[MapSummary])
async def maps(request: Request) -> list[MapSummary]:
    summaries = _kb(request).map_summaries()
    for summary in summaries:
        if summary.cover_image_id:
            summary.cover_image_url = _asset_url(request, summary.cover_image_id, "thumb")
    return summaries


@app.get("/media/{image_id}", response_class=FileResponse)
async def media(
    image_id: str,
    request: Request,
    variant: Literal["thumb", "full"] = Query(default="thumb"),
) -> Response:
    asset = _kb(request).get_image(image_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Unknown image.")

    manifest: AssetManifest = request.app.state.asset_manifest
    if settings.asset_base_url:
        remote_url = manifest.url(settings.asset_base_url, image_id, variant)
        if remote_url:
            redirect_response = RedirectResponse(remote_url, status_code=307)
            redirect_response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return redirect_response

    service: MediaService = request.app.state.media
    try:
        file_path = await asyncio.to_thread(service.get_path, asset, variant)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    file_response = FileResponse(file_path)
    file_response.headers["Cache-Control"] = "public, max-age=86400"
    return file_response


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    request_id = uuid.uuid4().hex[:12]
    started = time.monotonic()
    status = 500
    request_logger.info("Chat started id=%s map=%s", request_id, req.active_map_id)
    try:
        response = await asyncio.wait_for(
            answer_chat(
                req,
                _kb(request),
                request.app.state.search_engine,
                request.app.state.llm,
                lambda image_id, variant: _asset_url(request, image_id, variant),
            ),
            timeout=settings.chat_timeout_seconds,
        )
        status = 200
        response.response_language = resolve_response_language(
            req.message,
            req.conversation_history,
            req.preferred_language,
        )
        quest_paths = {
            c.path
            for c in _kb(request).chunks.values()
            if c.map_id == response.active_map_id and c.category == "main_ee"
        }
        related_quest = resolve_answer_intent(req.message).main_quest or any(
            s.path in quest_paths and s.map_id == response.active_map_id for s in response.sources
        )
        if response.active_map_id and related_quest:
            try:
                build_catalog(_kb(request), response.active_map_id)
            except ValueError:
                pass
            else:
                response.companion_offer_map_id = response.active_map_id
        return response
    except asyncio.TimeoutError as error:
        status = 504
        raise HTTPException(
            status_code=504,
            detail=(
                "A geração excedeu o tempo máximo de espera. Tente novamente ou peça "
                "uma etapa específica do guia. A resposta completa não foi concluída."
            ),
        ) from error
    except HTTPException as error:
        status = error.status_code
        raise
    except asyncio.CancelledError:
        status = 499
        raise
    finally:
        request_logger.info(
            "Chat finished id=%s status=%s elapsed=%.1fs",
            request_id,
            status,
            time.monotonic() - started,
        )


@app.post("/chat/jobs", response_model=ChatJobStatus, status_code=202)
async def start_chat_job(req: ChatRequest, request: Request, response: Response) -> ChatJobStatus:
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.chat_jobs.start(lambda: chat(req, request))


@app.get("/chat/jobs/{job_id}", response_model=ChatJobStatus)
async def chat_job(job_id: str, request: Request, response: Response) -> ChatJobStatus:
    response.headers["Cache-Control"] = "no-store"
    return request.app.state.chat_jobs.get(job_id)


@app.delete("/chat/jobs/{job_id}", response_model=ChatJobStatus)
async def cancel_chat_job(job_id: str, request: Request) -> ChatJobStatus:
    return await request.app.state.chat_jobs.cancel(job_id)


app.include_router(companion_router(_asset_url))


app.mount(
    "/app",
    StaticFiles(directory=settings.frontend_dir, html=True),
    name="frontend",
)
