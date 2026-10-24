from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import BaseModel

from app.chat_progress import ProgressPhase, observe_progress
from app.schemas import ChatResponse


class ChatJobStatus(BaseModel):
    job_id: str
    state: str
    elapsed_seconds: int
    phase: ProgressPhase = "starting"
    response: ChatResponse | None = None
    error: str | None = None
    status_code: int | None = None


@dataclass
class ChatJob:
    id: str
    created: float
    task: asyncio.Task | None = None
    finished: float | None = None
    response: ChatResponse | None = None
    error: str | None = None
    status_code: int | None = None
    phase: ProgressPhase = "starting"

    def snapshot(self) -> ChatJobStatus:
        return ChatJobStatus(
            job_id=self.id,
            state="pending" if self.finished is None else "failed" if self.error else "completed",
            elapsed_seconds=max(0, int((self.finished or time.monotonic()) - self.created)),
            phase=(
                self.phase if self.finished is None else
                "cancelled" if self.status_code == 499 else
                "failed" if self.error else "completed"
            ),
            response=self.response,
            error=self.error,
            status_code=self.status_code,
        )


class ChatJobs:
    """Bounded, ephemeral jobs for a single app worker; no conversation persistence."""

    def __init__(self, *, max_active=4, max_retained=32, retention_seconds=900):
        self.jobs: OrderedDict[str, ChatJob] = OrderedDict()
        self.max_active = max_active
        self.max_retained = max_retained
        self.retention_seconds = retention_seconds

    def _prune(self):
        now = time.monotonic()
        for id_, job in list(self.jobs.items()):
            if job.finished is not None and now - job.finished >= self.retention_seconds:
                del self.jobs[id_]

    def start(self, generate: Callable[[], Awaitable[ChatResponse]]) -> ChatJobStatus:
        self._prune()
        if sum(job.finished is None for job in self.jobs.values()) >= self.max_active:
            raise HTTPException(429, "Há respostas em processamento. Aguarde uma delas terminar.")
        while len(self.jobs) >= self.max_retained:
            oldest = next((id_ for id_, job in self.jobs.items() if job.finished is not None), None)
            if oldest is None:
                raise HTTPException(429, "Há respostas em processamento. Tente novamente depois.")
            del self.jobs[oldest]
        job = ChatJob(uuid.uuid4().hex, time.monotonic())
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job, generate))
        return job.snapshot()

    async def _run(self, job, generate):
        try:
            with observe_progress(lambda phase: setattr(job, "phase", phase)):
                job.response = await generate()
            job.status_code = 200
        except HTTPException as error:
            job.error = str(error.detail)
            job.status_code = error.status_code
        except asyncio.CancelledError:
            job.error = "O processamento foi cancelado."
            job.status_code = 499
            raise
        except Exception:
            logging.getLogger("krono.jobs").exception("Chat job failed id=%s", job.id)
            job.error = "Não foi possível concluir a resposta. Tente novamente."
            job.status_code = 500
        finally:
            job.finished = time.monotonic()

    def get(self, id_) -> ChatJobStatus:
        self._prune()
        job = self.jobs.get(id_)
        if job is None:
            raise HTTPException(404, "O processamento expirou ou o servidor foi reiniciado.")
        return job.snapshot()

    async def cancel(self, id_) -> ChatJobStatus:
        self.get(id_)
        job = self.jobs[id_]
        if job.finished is None and job.task is not None:
            job.task.cancel()
            await asyncio.gather(job.task, return_exceptions=True)
            # A task cancelled before its first event-loop turn never enters _run.
            if job.finished is None:
                job.error, job.status_code = "O processamento foi cancelado.", 499
                job.finished = time.monotonic()
        return job.snapshot()

    async def close(self):
        tasks = [
            job.task for job in self.jobs.values()
            if job.task is not None and not job.task.done()
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.jobs.clear()
