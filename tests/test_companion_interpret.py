from pathlib import Path

import pytest

from app.companion_interpret import interpret_progress
from app.companion_models import MatchState
from app.companion_state import build_catalog
from app.knowledge_base import KnowledgeBase
from app.llm import LLMContentError
from tests.test_llm_contract import completion, service


@pytest.fixture(scope="module")
def context():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    catalog = build_catalog(kb, "origins")
    state = MatchState(map_id="origins", catalog_version=catalog.version)
    return kb, catalog, state


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["Do início", "From the beginning", "Desde el principio"])
async def test_explicit_start_needs_no_model_call(context, text):
    kb, catalog, state = context
    change = await interpret_progress(None, text, state, catalog, kb)
    assert change.from_start
    assert change.evidence == text


@pytest.mark.asyncio
async def test_multilingual_consultation_changes_focus_without_completion(context):
    kb, catalog, state = context
    llm, calls = service(completion({"intent": "consult", "focus": "6"}))
    change = await interpret_progress(llm, "Montre-moi la phase 6", state, catalog, kb)
    assert change.focus == next(o.id for o in catalog.objectives if o.number == 6)
    assert not change.completed and not change.pending
    assert len(calls.calls) == 1


@pytest.mark.asyncio
async def test_multiple_explicit_completions_are_bound_to_catalog_ids(context):
    kb, catalog, state = context
    text = "Já fizemos 2, 3 e 5."
    llm, _ = service(
        completion({"intent": "progress", "completed": ["2", "3", "5"], "evidence": text})
    )
    change = await interpret_progress(llm, text, state, catalog, kb)
    assert change.completed == [
        next(o.id for o in catalog.objectives if o.number == i) for i in [2, 3, 5]
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "progress", "completed": ["999"], "evidence": "feito"},
        {"intent": "progress", "completed": ["2"], "evidence": "invented"},
        {"intent": "question", "completed": ["2"], "evidence": "feito"},
        {"intent": "progress", "completed": ["2"], "clarification": "Which?", "evidence": "feito"},
    ],
)
async def test_invalid_claims_are_repaired_once_then_rejected(context, payload):
    kb, catalog, state = context
    llm, calls = service(completion(payload))
    with pytest.raises(LLMContentError):
        await interpret_progress(llm, "feito", state, catalog, kb)
    assert len(calls.calls) == 2
    assert not state.statuses


def test_optional_equipment_does_not_block_the_main_quest(context):
    _, catalog, _ = context
    shields = [o for o in catalog.objectives if "shield.md" in o.id]
    assert shields and shields[0].optional
