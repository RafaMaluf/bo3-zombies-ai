import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from app import chat_service
from app.knowledge_base import KnowledgeBase
from app.llm import LLMResponseError
from app.retrieval import SearchEngine
from app.schemas import ChatRequest
from tests.test_planned_chat import PlannedLLM


@pytest.fixture(scope="module")
def services():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    return kb, SearchEngine(kb)


@pytest.mark.asyncio
async def test_strategies_preserve_order_and_images_and_parallel_really_overlaps(
    services, monkeypatch,
):
    kb, search = services
    original = chat_service._generate_plan
    monkeypatch.setattr(chat_service, "settings", replace(
        chat_service.settings, answer_audit_enabled=False,
    ))
    outputs = []
    counts = []
    for mode in ("sequential", "single", "parallel"):
        class OverlapLLM(PlannedLLM):
            active = 0
            peak = 0

            async def answer(self, messages, **kwargs):
                self.active += 1
                self.peak = max(self.peak, self.active)
                try:
                    await asyncio.sleep(0.01)
                    return await super().answer(messages, **kwargs)
                finally:
                    self.active -= 1

        async def generate(*args, mode=mode, **kwargs):
            if len(args) <= 9:
                kwargs["_batch_mode"] = mode
            return await original(*args, **kwargs)

        monkeypatch.setattr(chat_service, "_generate_plan", generate)
        llm = OverlapLLM()
        response = await chat_service.answer_chat(
            ChatRequest(
                message="EE de Origins completo", active_map_id="origins",
                response_mode="complete",
            ),
            kb, search, llm, lambda i, v: f"/{i}/{v}",
        )
        outputs.append((
            [b.source_ids for b in response.blocks],
            [i.id for i in response.relevant_images],
        ))
        counts.append(len(llm.calls))
        assert llm.active == 0
        assert llm.peak == (4 if mode == "parallel" else 1)
        if mode == "single":
            prompt = str(llm.calls[0])
            assert "ENTIRE answer" in prompt
            assert "Other batches cover" not in prompt
    assert outputs[0] == outputs[1] == outputs[2]
    assert counts == [4, 1, 4]


@pytest.mark.asyncio
async def test_parallel_failure_cancels_other_generations(services, monkeypatch):
    kb, search = services
    original = chat_service._generate_plan

    async def generate(*args, **kwargs):
        if len(args) <= 9:
            kwargs["_batch_mode"] = "parallel"
        return await original(*args, **kwargs)

    monkeypatch.setattr(chat_service, "_generate_plan", generate)

    class FailureLLM(PlannedLLM):
        active = 0
        entered = 0

        async def answer(self, messages, **kwargs):
            self.active += 1
            self.entered += 1
            position = self.entered
            try:
                await asyncio.sleep(0.01 if position == 1 else 5)
                raise LLMResponseError("Experiment failure")
            finally:
                self.active -= 1

    llm = FailureLLM()
    with pytest.raises(Exception, match="502"):
        await chat_service.answer_chat(
            ChatRequest(
                message="EE de Origins completo", active_map_id="origins",
                response_mode="complete",
            ),
            kb, search, llm, lambda i, v: f"/{i}/{v}",
        )
    assert llm.entered == 4
    assert llm.active == 0
