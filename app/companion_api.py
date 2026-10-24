"""Small HTTP surface for local match transitions and independent explanation jobs."""

import asyncio

from fastapi import APIRouter, HTTPException, Request, Response

from app.companion_models import (
    CompanionExplanation,
    CompanionRequest,
    CompanionStart,
    CompanionView,
)
from app.companion_service import explain_companion, start_companion, update_companion
from app.companion_state import build_catalog, validate_state
from app.config import settings
from app.llm import LLMResponseError, LLMUnavailableError


async def checked(awaitable):
    try:
        return await asyncio.wait_for(awaitable, timeout=settings.chat_timeout_seconds)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except LLMUnavailableError as error:
        raise HTTPException(503, str(error)) from error
    except LLMResponseError as error:
        raise HTTPException(
            502, "Não foi possível interpretar ou explicar esta etapa. Tente novamente."
        ) from error
    except asyncio.TimeoutError as error:
        raise HTTPException(
            504, "O tempo de espera terminou. Seu progresso salvo foi preservado."
        ) from error


def companion_router(asset_url):
    router = APIRouter(prefix="/companion", tags=["companion"])

    @router.post("/start", response_model=CompanionView)
    async def start(req: CompanionStart, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return await checked(
            start_companion(req, request.app.state.knowledge_base, request.app.state.llm)
        )

    @router.post("/action", response_model=CompanionView)
    async def action(req: CompanionRequest, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return await checked(
            update_companion(req, request.app.state.knowledge_base, request.app.state.llm)
        )

    @router.post("/explain/jobs", status_code=202)
    async def explain(req: CompanionExplanation, request: Request, response: Response):
        kb = request.app.state.knowledge_base
        try:
            validate_state(req.state, build_catalog(kb, req.state.map_id, req.state.language))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        response.headers["Cache-Control"] = "no-store"
        return request.app.state.chat_jobs.start(
            lambda: checked(
                explain_companion(
                    req,
                    kb,
                    request.app.state.llm,
                    lambda image_id, variant: asset_url(request, image_id, variant),
                )
            )
        )

    return router
