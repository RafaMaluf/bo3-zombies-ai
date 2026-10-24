import asyncio
from dataclasses import replace

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_chat_deadline_cancels_generation_and_returns_a_terminal_error(monkeypatch, caplog):
    cancelled = []

    async def stuck_generation(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    monkeypatch.setattr("app.main.answer_chat", stuck_generation)
    monkeypatch.setattr("app.main.settings", replace(settings, chat_timeout_seconds=0.03))
    with caplog.at_level("INFO", logger="uvicorn.error.krono.chat"):
        with TestClient(app) as client:
            response = client.post("/chat", json={"message": "EE completo de Origins"})
            assert client.get("/health").status_code == 200
    assert response.status_code == 504
    assert "tempo máximo" in response.json()["detail"]
    assert cancelled == [True]
    assert "status=504" in caplog.text
    assert "EE completo de Origins" not in caplog.text
