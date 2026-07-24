from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.conversation import (
    build_resolution_messages,
    clarification_for_options,
    deterministic_follow_up_options,
    document_catalog,
    history_without_duplicate_current_message,
    should_resolve_follow_up,
    source_anchored_query,
    validated_document_options,
)
from app.domain import ImageAsset
from app.knowledge_base import KnowledgeBase
from app.llm import LLMResponseError, LLMService, LLMUnavailableError
from app.media import MediaService
from app.prompt_builder import build_answer_prompt
from app.retrieval import SearchEngine
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MapSummary,
    RelevantImage,
    SelectedSource,
)

logger = logging.getLogger("krono")


@asynccontextmanager
async def lifespan(app: FastAPI):
    knowledge_base = KnowledgeBase(settings.maps_dir)
    app.state.knowledge_base = knowledge_base
    app.state.search_engine = SearchEngine(knowledge_base)
    app.state.llm = LLMService(settings)
    app.state.media = MediaService(settings.cache_dir)

    for issue in knowledge_base.issues:
        log = logger.error if issue.severity == "error" else logger.warning
        log("%s [%s] %s", issue.path, issue.code, issue.message)

    yield


app = FastAPI(
    title="Krono — Black Ops III Zombies",
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


def _kb(request: Request) -> KnowledgeBase:
    return request.app.state.knowledge_base


def _select_image_assets(
    requested_ids: list[str],
    available_assets: tuple[ImageAsset, ...],
    limit: int,
) -> list[ImageAsset]:
    allowed = {asset.id: asset for asset in available_assets}
    selected = []
    seen_ids: set[str] = set()
    for image_id in requested_ids:
        asset = allowed.get(image_id)
        if asset is None or asset.id in seen_ids:
            continue
        selected.append(asset)
        seen_ids.add(asset.id)
        if len(selected) >= limit:
            return selected

    if selected or not available_assets:
        return selected

    # Models occasionally omit images even for visual procedures. Fall back
    # to one asset per section from the highest-ranked visual document instead
    # of leaking loosely related images from another guide.
    seen_sections: set[tuple[str, str]] = set()
    preferred_document = available_assets[0].document_path
    for asset in available_assets:
        if asset.document_path != preferred_document:
            continue
        section_key = (asset.map_id, asset.section)
        if section_key in seen_sections:
            continue
        selected.append(asset)
        seen_sections.add(section_key)
        if len(selected) >= min(limit, 6):
            break
    return selected


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
        **stats,
    )


@app.get("/maps", response_model=list[MapSummary])
async def maps(request: Request) -> list[MapSummary]:
    return _kb(request).map_summaries()


@app.get("/media/{image_id}", response_class=FileResponse)
async def media(
    image_id: str,
    request: Request,
    variant: Literal["thumb", "full"] = Query(default="thumb"),
) -> FileResponse:
    asset = _kb(request).get_image(image_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Unknown image.")

    service: MediaService = request.app.state.media
    try:
        file_path = await asyncio.to_thread(service.get_path, asset, variant)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    response = FileResponse(file_path)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    knowledge_base = _kb(request)
    if knowledge_base.errors:
        raise HTTPException(
            status_code=503,
            detail=(
                "The knowledge base has validation errors. Run `python -m scripts.validate_kb`."
            ),
        )

    search_engine: SearchEngine = request.app.state.search_engine
    history = history_without_duplicate_current_message(
        req.conversation_history,
        req.message,
        settings.max_history_messages,
    )
    retrieval = search_engine.search(
        query=req.message,
        active_map_id=req.active_map_id,
        limit=settings.max_retrieved_chunks,
    )

    llm: LLMService = request.app.state.llm
    if should_resolve_follow_up(
        req.message,
        history,
        req.active_map_id,
        retrieval,
    ):
        active_record = knowledge_base.maps.get(req.active_map_id or "")
        catalog = document_catalog(knowledge_base, req.active_map_id or "")
        if active_record is not None and catalog:
            deterministic_options = deterministic_follow_up_options(
                req.message,
                history,
                catalog,
            )
            if deterministic_options:
                return ChatResponse(
                    need_clarification=True,
                    clarification_question=clarification_for_options(
                        req.message,
                        active_record.display_name,
                        deterministic_options,
                        "Qual guia você quer consultar?",
                    ),
                    suggested_queries=[item.label for item in deterministic_options],
                    active_map_id=req.active_map_id,
                )

            anchored_query = source_anchored_query(
                req.message,
                history,
                catalog,
            )
            resolution_messages = build_resolution_messages(
                message=req.message,
                history=history,
                map_name=active_record.display_name,
                catalog=catalog,
            )
            try:
                resolution = await llm.resolve_query(resolution_messages)
            except (LLMUnavailableError, LLMResponseError):
                logger.warning("Could not resolve ambiguous follow-up", exc_info=True)
                if anchored_query:
                    anchored_retrieval = search_engine.search(
                        query=anchored_query,
                        active_map_id=req.active_map_id,
                        limit=settings.max_retrieved_chunks,
                    )
                    if not anchored_retrieval.needs_clarification:
                        retrieval = anchored_retrieval
            else:
                if resolution.need_clarification:
                    options = validated_document_options(
                        resolution.candidate_document_paths,
                        catalog,
                        req.message,
                    )
                    if options or not anchored_query:
                        return ChatResponse(
                            need_clarification=True,
                            clarification_question=clarification_for_options(
                                req.message,
                                active_record.display_name,
                                options,
                                resolution.clarification_question,
                            ),
                            suggested_queries=[item.label for item in options],
                            active_map_id=req.active_map_id,
                        )
                else:
                    resolved_retrieval = search_engine.search(
                        query=resolution.resolved_query,
                        active_map_id=req.active_map_id,
                        limit=settings.max_retrieved_chunks,
                    )
                    if not resolved_retrieval.needs_clarification:
                        retrieval = resolved_retrieval
                        anchored_query = ""

                if anchored_query:
                    anchored_retrieval = search_engine.search(
                        query=anchored_query,
                        active_map_id=req.active_map_id,
                        limit=settings.max_retrieved_chunks,
                    )
                    if not anchored_retrieval.needs_clarification:
                        retrieval = anchored_retrieval

    if retrieval.needs_clarification:
        return ChatResponse(
            need_clarification=True,
            clarification_question=retrieval.clarification_question,
            suggested_map_ids=list(retrieval.suggested_map_ids),
            active_map_id=retrieval.active_map_id or req.active_map_id,
        )

    prompt = build_answer_prompt(
        user_message=req.message,
        history=history,
        scored_chunks=retrieval.chunks,
        knowledge_base=knowledge_base,
        max_context_chars=settings.max_context_chars,
        max_candidate_images=settings.max_candidate_images,
    )

    try:
        generated = await llm.answer(prompt.messages)
    except LLMUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except LLMResponseError as error:
        logger.exception("Chat generation failed")
        raise HTTPException(
            status_code=502,
            detail="The model failed to generate a valid answer. Try again.",
        ) from error

    selected_assets = _select_image_assets(
        requested_ids=generated.image_ids,
        available_assets=prompt.images,
        limit=settings.max_response_images,
    )
    relevant_images: list[RelevantImage] = []
    for asset in selected_assets:
        relevant_images.append(
            RelevantImage(
                id=asset.id,
                map_id=asset.map_id,
                path=asset.path,
                caption=asset.caption,
                section=asset.section,
            )
        )
    sources = [
        SelectedSource(
            chunk_id=item.chunk.id,
            map_id=item.chunk.map_id,
            map_name=item.chunk.map_name,
            path=item.chunk.path,
            section=item.chunk.section_title,
            score=item.score,
        )
        for item in prompt.chunks
    ]

    return ChatResponse(
        answer=generated.answer,
        need_clarification=generated.need_clarification,
        clarification_question=generated.clarification_question,
        sources=sources,
        relevant_images=relevant_images,
        active_map_id=retrieval.active_map_id,
    )


app.mount(
    "/app",
    StaticFiles(directory=settings.frontend_dir, html=True),
    name="frontend",
)
