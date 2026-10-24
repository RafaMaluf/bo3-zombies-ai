from pathlib import Path

import pytest
from pydantic import ValidationError

from app.chat_service import answer_chat
from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, GuideState
from tests.test_planned_chat import PlannedLLM


@pytest.fixture(scope="module")
def services():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    return kb, SearchEngine(kb)


def test_default_is_quick_and_unknown_modes_are_rejected():
    assert ChatRequest(message="Oi").response_mode == "quick"
    with pytest.raises(ValidationError):
        ChatRequest(message="Oi", response_mode="turbo")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["quick", "complete"])
async def test_quest_scope_changes_without_changing_summary_detail(services, mode):
    kb, search = services
    llm = PlannedLLM()
    response = await answer_chat(
        ChatRequest(message="Resuma o EE de Origins", response_mode=mode),
        kb,
        search,
        llm,
        lambda i, v: f"/{i}/{v}",
    )
    paths = {s.path for s in response.sources}
    main = {s.chunk_id for s in response.sources if s.path == "main_ee.md"}
    assert len(main) == 9
    assert response.relevant_images
    assert response.offer_complete == (mode == "quick")
    assert all(
        "ANSWER DETAIL: SUMMARY" in " ".join(m["content"] for m in call) for call in llm.calls
    )
    if mode == "quick":
        assert paths == {"main_ee.md"}
        assert not hasattr(llm, "context")  # no semantic dependency-planning call
    else:
        assert len(paths) > 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "Como monto o escudo de Shadows of Evil sem resumir?",
        "How do I build the shield in Shadows of Evil in detail?",
    ],
)
async def test_quick_shield_preserves_all_locations_images_and_detail(services, message):
    kb, search = services
    llm = PlannedLLM()
    response = await answer_chat(
        ChatRequest(message=message), kb, search, llm, lambda i, v: f"/{i}/{v}"
    )
    assert {s.path for s in response.sources} == {"shield.md"}
    assert len(response.relevant_images) == 9
    assert len({i.id for i in response.relevant_images}) == 9
    assert all(len(b.images) == b.available_image_count for b in response.blocks)
    assert response.offer_complete  # workbench photographs belong to a separate guide
    assert all(
        "ANSWER DETAIL: DETAILED" in " ".join(m["content"] for m in call) for call in llm.calls
    )


@pytest.mark.asyncio
async def test_quick_pap_keeps_location_support_but_excludes_other_file_topics(services):
    kb, search = services
    response = await answer_chat(
        ChatRequest(message="Como libero o Pack-a-Punch?", active_map_id="der_eisendrache"),
        kb,
        search,
        PlannedLLM(),
        lambda i, v: f"/{i}/{v}",
    )
    assert {s.path for s in response.sources} == {"power_pap_teleporter.md"}
    assert len(response.relevant_images) == 6
    assert not any("Wundersphere" in s.section for s in response.sources)


@pytest.mark.asyncio
async def test_quick_detailed_quest_still_explains_all_main_phases(services):
    kb, search = services
    llm = PlannedLLM()
    response = await answer_chat(
        ChatRequest(message="EE de Origins sem resumir"),
        kb,
        search,
        llm,
        lambda i, v: f"/{i}/{v}",
    )
    assert {s.path for s in response.sources} == {"main_ee.md"}
    assert len(response.blocks) == 9
    assert response.offer_complete
    assert all(
        "ANSWER DETAIL: DETAILED" in " ".join(m["content"] for m in call) for call in llm.calls
    )


@pytest.mark.asyncio
async def test_multiple_objectives_in_quick_offer_expansion_without_silent_mode_change(services):
    kb, search = services
    response = await answer_chat(
        ChatRequest(
            message="Como faço o escudo e libero o Pack-a-Punch?", active_map_id="shadows_of_evil"
        ),
        kb,
        search,
        PlannedLLM(),
        lambda i, v: f"/{i}/{v}",
    )
    assert len({s.path for s in response.sources}) == 1
    assert response.offer_complete


@pytest.mark.asyncio
async def test_legacy_guide_action_does_not_limit_companion_to_one_file(services):
    kb, search = services
    response = await answer_chat(
        ChatRequest(
            message="EE Origins",
            active_map_id="origins",
            guide_action="full",
            guide_state=GuideState(map_id="origins", document_path="main_ee.md"),
        ),
        kb,
        search,
        PlannedLLM(),
        lambda i, v: f"/{i}/{v}",
    )
    assert len({s.path for s in response.sources}) > 1
    assert not response.offer_complete
