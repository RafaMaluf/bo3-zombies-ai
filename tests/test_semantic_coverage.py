from dataclasses import replace

import pytest

from app.llm import LLMResponse, LLMResponseError
from app.source_planning import PlanningContext
from tests.test_llm_contract import CONTRACT, GOOD, MESSAGES, completion, service
from tests.test_source_planning import PAP, POWER


@pytest.mark.asyncio
async def test_semantic_audit_accepts_an_answer_without_regeneration():
    llm, scripted = service(completion({"missing_facts": [], "contradictions": []}))
    generated = LLMResponse.model_validate(GOOD)
    assert await llm.ensure_coverage(MESSAGES, generated, CONTRACT) is generated
    assert len(scripted.calls) == 1


@pytest.mark.asyncio
async def test_semantic_omission_triggers_a_bounded_full_batch_repair():
    llm, scripted = service(
        completion({"missing_facts": ["Explain the third possible spawn."], "contradictions": []}),
        completion(GOOD),
        completion({"missing_facts": [], "contradictions": []}),
    )
    result = await llm.ensure_coverage(MESSAGES, LLMResponse.model_validate(GOOD), CONTRACT)
    assert result.blocks
    assert len(scripted.calls) == 3
    assert "third possible spawn" in scripted.calls[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_failed_semantic_repair_is_an_error_not_a_partial_success():
    bad = completion({"missing_facts": [], "contradictions": ["Wrong number of pieces."]})
    llm, scripted = service(bad, completion(GOOD), bad)
    with pytest.raises(LLMResponseError, match="coverage audit failed"):
        await llm.ensure_coverage(MESSAGES, LLMResponse.model_validate(GOOD), CONTRACT)
    assert len(scripted.calls) == 3


@pytest.mark.asyncio
async def test_completion_is_grounded_in_explicit_user_statements():
    quote = "Já tenho a energia ligada."
    context = PlanningContext((POWER, PAP), (), [], user_statements=quote)
    llm, _ = service(completion({"claims": [{"source_ids": ["0"], "evidence": quote}]}))
    assert await llm.completed_sources(context) == (POWER.id,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "evidence,statements",
    [
        ("Já tenho a energia ligada.", "Como faço o escudo?"),
        ("Não, já tenho a energia ligada.", "Não, já tenho a energia ligada."),
        ("Quero ligar a energia.", "Quero ligar a energia."),
    ],
)
async def test_completion_cannot_be_inferred_from_assistant_or_negated_or_future_claims(
    evidence,
    statements,
):
    context = PlanningContext((POWER, PAP), (), [], user_statements=statements)
    llm, scripted = service(completion({"claims": [{"source_ids": ["0"], "evidence": evidence}]}))
    with pytest.raises(LLMResponseError):
        await llm.completed_sources(context)
    assert len(scripted.calls) == 2


@pytest.mark.asyncio
async def test_completion_cannot_mark_a_main_quest_phase_done():
    context = PlanningContext(
        (replace(POWER, category="main_ee"),), (), [], user_statements="Já fiz essa fase."
    )
    llm, _ = service(
        completion({"claims": [{"source_ids": ["0"], "evidence": "Já fiz essa fase."}]})
    )
    assert await llm.completed_sources(context) == ()
