from pathlib import Path

import pytest

from app.assets import AssetManifest
from app.guidance import guide_chunks, prepare_guidance
from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, GuideState

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def knowledge() -> tuple[KnowledgeBase, SearchEngine]:
    kb = KnowledgeBase(
        ROOT / "maps", asset_manifest=AssetManifest.load(ROOT / "assets" / "image-manifest.json")
    )
    return kb, SearchEngine(kb)


def request(message: str = "Como faço o EE de Origins?", **kwargs: object) -> ChatRequest:
    return ChatRequest(message=message, active_map_id="origins", **kwargs)


def test_origins_legacy_document_is_split_without_changing_the_index(knowledge):
    kb, _ = knowledge
    chunks = guide_chunks(kb, "origins", "main_ee.md")
    assert len(chunks) == 9
    assert len({c.id for c in chunks}) == 9
    assert not chunks[0].image_ids
    assert "G-strike" in chunks[3].content
    assert "Step four" not in chunks[3].content
    assert len(chunks[3].image_ids) == 2
    raw = (kb.maps["origins"].directory / "main_ee.md").read_text("utf-8")
    original_phase = raw.split("Step three:", 1)[1].split("Step four:", 1)[0]
    assert all(kb.images[i].path in original_phase for i in chunks[3].image_ids)
    assert all(kb.images[i].path not in chunks[3].content for i in chunks[3].image_ids)
    assert all(c.id not in kb.chunks for c in chunks)


@pytest.mark.parametrize(
    "query",
    [
        "Como faço o EE de Origins?",
        "How do I complete the main Easter Egg in Origins?",
        "Como faço o EE de Origins solo?",
    ],
)
def test_broad_quest_starts_with_roadmap(knowledge, query):
    context = prepare_guidance(request(query), *knowledge, "pt-BR")
    assert context.progress.mode == "overview"
    assert context.progress.state.completed_phases == []
    assert len(context.retrieval.chunks) == 9
    assert any(c.chunk.image_ids for c in context.retrieval.chunks)


def test_explicit_full_guide_contains_every_phase_and_images(knowledge):
    context = prepare_guidance(
        request("Me passe o guia completo do EE de Origins"), *knowledge, "pt-BR"
    )
    assert context.progress.mode == "full"
    assert len(context.retrieval.chunks) == 9
    assert sum(len(c.chunk.image_ids) for c in context.retrieval.chunks) > 8


def test_questions_do_not_advance_or_complete_a_phase(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md", phase=3)
    context = prepare_guidance(
        request("Onde fica a pedra?", guide_state=state), *knowledge, "pt-BR"
    )
    assert context.progress.state.phase == 3
    assert context.progress.state.completed_phases == []
    assert len(context.retrieval.chunks) == 1
    assert state.phase == 3


def test_completion_advances_only_the_explicit_current_phase(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md", phase=3)
    context = prepare_guidance(
        request("Concluí", guide_state=state, guide_action="complete"), *knowledge, "pt-BR"
    )
    assert context.progress.state.phase == 4
    assert context.progress.state.completed_phases == [3]
    assert state.completed_phases == []


def test_jump_does_not_mark_skipped_phases_complete(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md")
    context = prepare_guidance(
        request("Já estou na fase 6", guide_state=state, guide_action="jump", guide_phase=5),
        *knowledge,
        "pt-BR",
    )
    assert context.progress.state.phase == 5
    assert context.progress.state.completed_phases == []


def test_final_phase_does_not_advance_out_of_bounds(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md", phase=8)
    context = prepare_guidance(
        request("Concluí", guide_state=state, guide_action="complete"), *knowledge, "pt-BR"
    )
    assert context.progress.mode == "finished"
    assert context.progress.state.phase == 8
    assert context.progress.state.completed_phases == [8]


@pytest.mark.parametrize(
    "state,phase",
    [
        (GuideState(map_id="origins", document_path="../../.env"), 0),
        (GuideState(map_id="origins", document_path="shield.md"), 0),
        (GuideState(map_id="origins", document_path="main_ee.md"), 99),
    ],
)
def test_unknown_sources_and_phase_indices_are_rejected(knowledge, state, phase):
    with pytest.raises(ValueError):
        prepare_guidance(
            request("Ir para fase", guide_state=state, guide_action="jump", guide_phase=phase),
            *knowledge,
            "pt-BR",
        )


def test_other_objective_uses_normal_retrieval_without_losing_progress(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md", phase=3)
    assert (
        prepare_guidance(
            request("Como faço o Maxis Drone?", guide_state=state), *knowledge, "pt-BR"
        )
        is None
    )
    assert state.phase == 3


def test_other_map_cannot_use_previous_guide_actions(knowledge):
    state = GuideState(map_id="shadows_of_evil", document_path="main-ee.md")
    with pytest.raises(ValueError):
        prepare_guidance(
            request("Começar", guide_state=state, guide_action="start"), *knowledge, "pt-BR"
        )


def test_player_count_is_carried_into_phase_instructions(knowledge):
    context = prepare_guidance(
        request("Como faço o EE de Origins? Somos 2 jogadores"), *knowledge, "pt-BR"
    )
    assert context.progress.state.player_count == 2
    assert "PLAYERS: 2" in context.instructions


def test_navigation_keeps_guide_language_despite_ambiguous_button_text(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md", language="pt-BR")
    context = prepare_guidance(
        request("Concluí esta fase", guide_state=state, guide_action="complete"),
        *knowledge,
        "en",
    )
    assert context.progress.state.language == "pt-BR"
    assert context.progress.phases[0].title == "Preparação"


def test_question_about_solo_does_not_change_known_party_size(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md", player_count=2)
    context = prepare_guidance(
        request("Dá para fazer solo?", guide_state=state), *knowledge, "pt-BR"
    )
    assert context.progress.state.player_count == 2


def test_pack_a_punch_question_leaves_main_quest_scope_without_advancing_it(knowledge):
    state = GuideState(map_id="origins", document_path="main_ee.md", phase=3)
    assert (
        prepare_guidance(
            request("Como libero o Pack-a-Punch?", guide_state=state), *knowledge, "pt-BR"
        )
        is None
    )
    assert state.phase == 3
