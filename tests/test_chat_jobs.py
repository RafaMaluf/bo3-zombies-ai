import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.chat_jobs import ChatJobs
from app.main import app
from app.schemas import ChatResponse


@pytest.mark.asyncio
async def test_pending_job_is_not_evicted_and_capacity_releases_after_cancellation():
    jobs = ChatJobs(max_active=1, max_retained=1, retention_seconds=0)
    cancelled = []

    async def generate():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    job = jobs.start(generate)
    await asyncio.sleep(0)
    assert jobs.get(job.job_id).state == "pending"
    with pytest.raises(HTTPException) as caught:
        jobs.start(generate)
    assert caught.value.status_code == 429
    assert (await jobs.cancel(job.job_id)).status_code == 499
    assert cancelled == [True]
    replacement = jobs.start(generate)
    assert replacement.job_id != job.job_id
    await jobs.close()
    assert not jobs.jobs


@pytest.mark.asyncio
async def test_job_retains_full_result_and_preserves_provider_errors():
    jobs = ChatJobs(max_retained=1)

    async def success():
        return ChatResponse(answer="Resposta completa.")

    first = jobs.start(success)
    await jobs.jobs[first.job_id].task
    result = jobs.get(first.job_id)
    assert result.state == "completed"
    assert result.response.answer == "Resposta completa."

    async def failure():
        raise HTTPException(503, "Limite gratuito atingido. Tente novamente amanhã.")

    second = jobs.start(failure)
    await jobs.jobs[second.job_id].task
    result = jobs.get(second.job_id)
    assert result.state == "failed"
    assert result.status_code == 503
    assert "amanhã" in result.error
    with pytest.raises(HTTPException) as caught:
        jobs.get(first.job_id)
    assert caught.value.status_code == 404
    await jobs.close()


def test_job_http_transport_returns_promptly_and_can_cancel_without_blocking_health(monkeypatch):
    cancelled = []

    async def generate(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    monkeypatch.setattr("app.main.answer_chat", generate)
    with TestClient(app) as client:
        response = client.post("/chat/jobs", json={"message": "EE de Origins"})
        assert response.status_code == 202
        assert response.headers["cache-control"] == "no-store"
        id_ = response.json()["job_id"]
        assert client.get("/health").status_code == 200
        assert client.get(f"/chat/jobs/{id_}").json()["state"] == "pending"
        assert client.delete(f"/chat/jobs/{id_}").json()["status_code"] == 499
        assert cancelled == [True]
        assert client.get(f"/chat/jobs/{id_}").json()["state"] == "failed"
        assert client.get("/chat/jobs/unknown").status_code == 404


def test_job_http_result_matches_the_existing_chat_contract(monkeypatch):
    async def generate(*args):
        return ChatResponse(answer="Guia concluído.", active_map_id="origins")

    monkeypatch.setattr("app.main.answer_chat", generate)
    with TestClient(app) as client:
        id_ = client.post("/chat/jobs", json={"message": "EE de Origins"}).json()["job_id"]
        result = client.get(f"/chat/jobs/{id_}").json()
        assert result["state"] == "completed"
        assert result["response"]["answer"] == "Guia concluído."
        assert result["response"]["active_map_id"] == "origins"
