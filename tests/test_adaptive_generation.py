import re
from pathlib import Path

import pytest

from app.chat_service import answer_chat
from app.knowledge_base import KnowledgeBase
from app.llm import LLMContentError
from app.retrieval import SearchEngine
from app.schemas import ChatRequest
from tests.test_planned_chat import PlannedLLM


@pytest.mark.asyncio
async def test_incomplete_large_batch_is_split_without_changing_detail_or_dropping_sources():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")

    class DifficultBatch(PlannedLLM):
        failed = False

        async def answer(self, messages, **kwargs):
            ids = re.findall(r"\[SOURCE ([^\]]+)\]", messages[-1]["content"])
            if len(ids) > 1 and not self.failed:
                self.failed = True
                raise LLMContentError("A required section was omitted after correction.")
            assert kwargs["contract"].detail == "detailed"
            return await super().answer(messages, **kwargs)

    llm = DifficultBatch()
    response = await answer_chat(
        ChatRequest(message="Como libero o Pack-a-Punch?", active_map_id="shadows_of_evil"),
        kb,
        SearchEngine(kb),
        llm,
        lambda i, v: f"/{i}/{v}",
    )
    assert llm.failed
    assert len(response.blocks) == 6
    assert len(response.relevant_images) == 17
    assert len({s for b in response.blocks for s in b.source_ids}) == 6
