from pathlib import Path

import pytest

from app.chat_service import answer_chat
from app.dependency_discovery import procedure_members
from app.guide_dependencies import DependencyIndex, map_catalog
from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine
from app.schemas import ChatRequest
from app.source_planning import PlanningContext
from tests.test_planned_chat import PlannedLLM


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")


def test_unknown_equipment_resolves_the_full_recipe_and_general_pap_redirects(kb):
    cs = map_catalog(kb, "revelations")
    ctx = PlanningContext(cs, (), [], dependency_index=DependencyIndex.load(kb))
    keeper = next(
        c
        for c in cs
        if c.path == "keeper_protector.md" and c.section_title == "altar build locations"
    )
    members = procedure_members(keeper, ctx, "Keeper Protector altar built")
    assert {"part 1 - flag", "part 2 - skull of nan sapwe", "part 3 - purple gem"} <= {
        c.section_title for c in members
    }
    general = next(c for c in cs if c.path == "general.md" and c.section_title == "Pack-a-Punch")
    pap = procedure_members(general, ctx, "Requires Pack-a-Punch unlocked.")
    assert {c.path for c in pap} == {"pap.md"}


@pytest.mark.asyncio
async def test_two_explicit_objectives_are_both_answered_without_a_file_choice(kb):
    response = await answer_chat(
        ChatRequest(
            message="Como faço o escudo e libero o Pack-a-Punch?",
            active_map_id="shadows_of_evil",
            response_mode="complete",
        ),
        kb,
        SearchEngine(kb),
        PlannedLLM(),
        lambda i, v: f"/{i}/{v}",
    )
    assert not response.need_clarification
    assert {s.path for s in response.sources} == {"shield.md", "pap.md", "build-table.md"}
    assert len(response.relevant_images) == 29


@pytest.mark.asyncio
async def test_explain_better_does_not_mean_upgrade_the_shield(kb):
    response = await answer_chat(
        ChatRequest(message="Explique melhor como monto o escudo", active_map_id="gorod_krovi"),
        kb,
        SearchEngine(kb),
        PlannedLLM(),
        lambda i, v: f"/{i}/{v}",
    )
    assert not any("upgrade" in s.section.lower() for s in response.sources)
