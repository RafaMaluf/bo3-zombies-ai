from dataclasses import replace
from pathlib import Path

import pytest

from app.chat_service import answer_chat
from app.config import Settings, settings
from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine
from app.schemas import ChatRequest
from tests.test_planned_chat import PlannedLLM


@pytest.fixture(scope="module")
def services():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    return kb, SearchEngine(kb)


def test_semantic_audit_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_ANSWER_AUDIT", raising=False)
    assert not Settings().answer_audit_enabled


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_audit_can_be_removed_without_losing_source_blocks_or_images(
    enabled, services, monkeypatch
):
    kb, search = services
    monkeypatch.setattr(
        "app.chat_service.settings", replace(settings, answer_audit_enabled=enabled)
    )

    class CountingAudit(PlannedLLM):
        audit_calls = 0

        async def ensure_coverage(self, messages, result, contract, **kwargs):
            self.audit_calls += 1
            return result

    llm = CountingAudit()
    response = await answer_chat(
        ChatRequest(message="Como monto o escudo?", active_map_id="gorod_krovi"),
        kb, search, llm, lambda id_, variant: f"/media/{id_}?variant={variant}",
    )
    assert len(response.blocks) == 4
    assert len(response.relevant_images) == 10
    assert llm.audit_calls == (len(llm.calls) if enabled else 0)
