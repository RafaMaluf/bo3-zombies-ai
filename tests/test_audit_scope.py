import json
from dataclasses import replace

import pytest

from app.domain import ScoredChunk
from app.llm import LLMResponse
from tests.test_llm_contract import CONTRACT, GOOD, completion, service
from tests.test_source_planning import POWER


@pytest.mark.asyncio
async def test_auditor_receives_local_sources_not_the_global_multi_objective_question():
    question = "Explain the shield AND Pack-a-Punch; another batch covers the latter."
    llm, scripted = service(completion({"missing_facts": [], "contradictions": []}))
    source = replace(POWER, id="guide:part-1")
    generated = LLMResponse.model_validate(GOOD)
    await llm.ensure_coverage(
        [{"role": "user", "content": question}],
        generated,
        CONTRACT,
        sources=[ScoredChunk(source, 1)],
    )
    payload = scripted.calls[0]["messages"][-1]["content"]
    assert question not in payload
    assert json.loads(payload)["AUDIT ONLY THESE SOURCES"][0]["content"] == source.content
