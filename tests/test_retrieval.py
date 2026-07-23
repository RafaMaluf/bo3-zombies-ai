from pathlib import Path

from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine

ROOT = Path(__file__).resolve().parent.parent


def _search_engine() -> SearchEngine:
    return SearchEngine(KnowledgeBase(ROOT / "maps"))


def test_specific_item_can_infer_the_map() -> None:
    result = _search_engine().search(
        "How do I upgrade the KT-4 into the Masamune?",
        active_map_id=None,
        limit=6,
    )

    assert not result.needs_clarification
    assert result.active_map_id == "zetsubou_no_shima"
    assert result.chunks[0].chunk.path == "masamune.md"


def test_generic_pack_a_punch_question_requests_a_map() -> None:
    result = _search_engine().search(
        "How do I unlock Pack-a-Punch?",
        active_map_id=None,
        limit=6,
    )

    assert result.needs_clarification
    assert len(result.suggested_map_ids) > 1


def test_active_map_keeps_follow_up_in_context() -> None:
    result = _search_engine().search(
        "Where is the third shield part?",
        active_map_id="der_eisendrache",
        limit=6,
    )

    assert not result.needs_clarification
    assert result.active_map_id == "der_eisendrache"
    assert all(scored.chunk.map_id == "der_eisendrache" for scored in result.chunks)
    assert result.chunks[0].chunk.section_title == "part 3 - underground frame"


def test_portuguese_ordinal_finds_the_correct_part_and_images() -> None:
    result = _search_engine().search(
        "Onde fica a terceira peça do escudo?",
        active_map_id="der_eisendrache",
        limit=6,
    )

    assert not result.needs_clarification
    assert result.chunks[0].chunk.section_title == "part 3 - underground frame"
    assert result.chunks[0].chunk.image_ids
    assert {scored.chunk.path for scored in result.chunks} == {"shield.md"}


def test_relative_score_cutoff_removes_loose_rocket_matches() -> None:
    result = _search_engine().search(
        "Como monto o Rocket Shield em Der Eisendrache?",
        active_map_id=None,
        limit=8,
    )

    assert not result.needs_clarification
    assert {scored.chunk.path for scored in result.chunks} == {"shield.md"}


def test_portuguese_topic_expansion_finds_shield() -> None:
    result = _search_engine().search(
        "como eu monto o escudo no gorod krovi?",
        active_map_id=None,
        limit=5,
    )

    assert not result.needs_clarification
    assert result.active_map_id == "gorod_krovi"
    assert any(scored.chunk.path == "shield.md" for scored in result.chunks)
