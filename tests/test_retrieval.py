from pathlib import Path

import pytest

from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def search_engine() -> SearchEngine:
    return SearchEngine(KnowledgeBase(ROOT / "maps"))


def test_specific_item_can_infer_the_map(search_engine: SearchEngine) -> None:
    result = search_engine.search(
        "How do I upgrade the KT-4 into the Masamune?",
        active_map_id=None,
        limit=6,
    )

    assert not result.needs_clarification
    assert result.active_map_id == "zetsubou_no_shima"
    assert result.chunks[0].chunk.path == "masamune.md"


def test_generic_pack_a_punch_question_requests_a_map(search_engine: SearchEngine) -> None:
    result = search_engine.search(
        "How do I unlock Pack-a-Punch?",
        active_map_id=None,
        limit=6,
    )

    assert result.needs_clarification
    assert set(result.suggested_map_ids) == set(search_engine.knowledge_base.maps)


def test_missing_topic_in_active_map_does_not_suggest_same_map(
    search_engine: SearchEngine,
) -> None:
    result = search_engine.search(
        "assunto completamente inexistente xyz",
        active_map_id="der_eisendrache",
        limit=6,
    )

    assert result.needs_clarification
    assert result.suggested_map_ids == ()


def test_active_map_keeps_follow_up_in_context(search_engine: SearchEngine) -> None:
    result = search_engine.search(
        "Where is the third shield part?",
        active_map_id="der_eisendrache",
        limit=6,
    )

    assert not result.needs_clarification
    assert result.active_map_id == "der_eisendrache"
    assert all(scored.chunk.map_id == "der_eisendrache" for scored in result.chunks)
    assert result.chunks[0].chunk.section_title == "part 3 - underground frame"


def test_active_map_wins_when_an_area_name_is_also_another_map(
    search_engine: SearchEngine,
) -> None:
    result = search_engine.search(
        "Onde fica a peça do Dragon Shield na área de Origins?",
        active_map_id="revelations",
        limit=6,
    )

    assert not result.needs_clarification
    assert result.active_map_id == "revelations"
    assert result.chunks[0].chunk.path == "shield.md"
    assert result.chunks[0].chunk.section_title == "part 1 - origins area piece"


def test_portuguese_ordinal_finds_the_correct_part_and_images(
    search_engine: SearchEngine,
) -> None:
    result = search_engine.search(
        "Onde fica a terceira peça do escudo?",
        active_map_id="der_eisendrache",
        limit=6,
    )

    assert not result.needs_clarification
    assert result.chunks[0].chunk.section_title == "part 3 - underground frame"
    assert result.chunks[0].chunk.image_ids
    assert {scored.chunk.path for scored in result.chunks} == {"shield.md"}


def test_dominant_document_removes_loose_rocket_matches(search_engine: SearchEngine) -> None:
    result = search_engine.search(
        "Como monto o Rocket Shield em Der Eisendrache?",
        active_map_id=None,
        limit=8,
    )

    assert not result.needs_clarification
    assert {scored.chunk.path for scored in result.chunks} == {"shield.md"}


def test_portuguese_topic_expansion_finds_shield(search_engine: SearchEngine) -> None:
    result = search_engine.search(
        "como eu monto o escudo no gorod krovi?",
        active_map_id=None,
        limit=5,
    )

    assert not result.needs_clarification
    assert result.active_map_id == "gorod_krovi"
    assert any(scored.chunk.path == "shield.md" for scored in result.chunks)


@pytest.mark.parametrize(
    ("query", "active_map_id", "expected_map_id", "expected_path"),
    [
        (
            "Como consigo o arco elétrico em Der Eisendrache?",
            None,
            "der_eisendrache",
            "lightning_bow.md",
        ),
        (
            "Where do I find the gramophones in Der Eisendrache?",
            None,
            "der_eisendrache",
            "side_ee/music_2_gramophones.md",
        ),
        (
            "Como faço a manopla do Siegfried no Gorod Krovi?",
            None,
            "gorod_krovi",
            "gauntlet.md",
        ),
        ("How do I unlock Dragon Strike in GK?", None, "gorod_krovi", "dragon_strike.md"),
        (
            "Onde ficam as garrafas de vodka?",
            "gorod_krovi",
            "gorod_krovi",
            "side_ee/music_1.md",
        ),
        (
            "Como entro no Apothicon e abro o Pack-a-Punch em Revelations?",
            None,
            "revelations",
            "pap.md",
        ),
        (
            "How do I build the Keeper Protector in Rev?",
            None,
            "revelations",
            "keeper_protector.md",
        ),
        (
            "Como pego a máscara viking?",
            "revelations",
            "revelations",
            "side_ee/masks.md",
        ),
        (
            "Como faço os quatro rituais de Shadows of Evil?",
            None,
            "shadows_of_evil",
            "pap.md",
        ),
        (
            "Where are the Civil Protector fuses?",
            "shadows_of_evil",
            "shadows_of_evil",
            "civil-protector.md",
        ),
        (
            "Como ativo o modo noir?",
            "shadows_of_evil",
            "shadows_of_evil",
            "side_ee/noir-mode.md",
        ),
        (
            "How do I unlock the Annihilator in The Giant?",
            None,
            "the_giant",
            "main_ee_annihilator.md",
        ),
        ("Como libero o perk extra no The Giant?", None, "the_giant", "extra_perk.md"),
        ("Como pego a KT-4 em Zetsubou?", None, "zetsubou_no_shima", "kt4.md"),
        (
            "Where do I get rainbow water?",
            "zetsubou_no_shima",
            "zetsubou_no_shima",
            "buckets_water.md",
        ),
        (
            "Como viro uma aranha?",
            "zetsubou_no_shima",
            "zetsubou_no_shima",
            "side_ee/spider_transformation.md",
        ),
    ],
)
def test_retrieval_regression_matrix(
    search_engine: SearchEngine,
    query: str,
    active_map_id: str | None,
    expected_map_id: str,
    expected_path: str,
) -> None:
    result = search_engine.search(query, active_map_id=active_map_id, limit=10)

    assert not result.needs_clarification
    assert result.active_map_id == expected_map_id
    assert result.chunks
    assert {item.chunk.path for item in result.chunks} == {expected_path}


def test_comprehensive_ritual_query_keeps_all_four_rituals(
    search_engine: SearchEngine,
) -> None:
    result = search_engine.search(
        "Como faço os quatro rituais de Shadows of Evil?",
        active_map_id=None,
        limit=10,
    )
    titles = {item.chunk.section_title for item in result.chunks}

    assert "get the summoning key + Nero setup" in titles
    assert "Jackie's ritual / Canals" in titles
    assert "Jessica's ritual / Footlight" in titles
    assert "Floyd's ritual / Waterfront" in titles


def test_comparison_query_can_keep_multiple_maps(search_engine: SearchEngine) -> None:
    result = search_engine.search(
        "Compare os escudos de Gorod Krovi e Der Eisendrache",
        active_map_id=None,
        limit=10,
    )

    assert not result.needs_clarification
    assert set(result.explicit_map_ids) == {"gorod_krovi", "der_eisendrache"}
    assert {item.chunk.map_id for item in result.chunks} == {
        "gorod_krovi",
        "der_eisendrache",
    }
