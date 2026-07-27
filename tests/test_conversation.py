from pathlib import Path

import pytest

from app.conversation import (
    build_resolution_messages,
    clarification_for_options,
    deterministic_follow_up_options,
    document_catalog,
    history_without_duplicate_current_message,
    should_resolve_follow_up,
    source_anchored_query,
    validated_document_options,
)
from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine
from app.schemas import ConversationMessage

ROOT = Path(__file__).resolve().parent.parent


def test_duplicate_current_message_is_removed_from_history() -> None:
    history = [
        ConversationMessage(role="assistant", content="Resposta anterior."),
        ConversationMessage(role="user", content="E os outros?"),
    ]

    selected = history_without_duplicate_current_message(
        history,
        "e os outros?",
        limit=10,
    )

    assert [item.role for item in selected] == ["assistant"]


def test_referential_follow_up_requests_resolution() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    retrieval = SearchEngine(knowledge_base).search(
        "e o terceiro?",
        active_map_id="der_eisendrache",
        limit=10,
    )
    history = [
        ConversationMessage(
            role="assistant",
            content="As duas primeiras peças ficam no castelo.",
            source_paths=["shield.md"],
        )
    ]

    assert should_resolve_follow_up(
        "e o terceiro?",
        history,
        "der_eisendrache",
        retrieval,
    )
    specific_retrieval = SearchEngine(knowledge_base).search(
        "Como consigo o arco de fogo em Der Eisendrache?",
        active_map_id="der_eisendrache",
        limit=10,
    )
    assert not should_resolve_follow_up(
        "Como consigo o arco de fogo em Der Eisendrache?",
        history,
        "der_eisendrache",
        specific_retrieval,
    )


@pytest.mark.parametrize(
    "message",
    [
        "pode com menos?",
        "pode com 2?",
        "com 2?",
        "e solo?",
    ],
)
def test_elliptical_constraints_request_context_resolution(message: str) -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    retrieval = SearchEngine(knowledge_base).search(
        message,
        active_map_id="shangri_la",
        limit=10,
    )
    history = [
        ConversationMessage(
            role="assistant",
            content="O Easter Egg principal exige quatro jogadores.",
            source_paths=["main_ee.md"],
        )
    ]

    assert should_resolve_follow_up(
        message,
        history,
        "shangri_la",
        retrieval,
    )
    query = source_anchored_query(
        message,
        history,
        document_catalog(knowledge_base, "shangri_la"),
    )
    anchored = SearchEngine(knowledge_base).search(
        query,
        active_map_id="shangri_la",
        limit=10,
    )
    assert {item.chunk.path for item in anchored.chunks} == {"main_ee.md"}


def test_resolution_prompt_uses_catalog_and_previous_sources() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "der_eisendrache")
    history = [
        ConversationMessage(
            role="assistant",
            content="Guia do arco de fogo.",
            source_paths=["fire_bow.md"],
        )
    ]

    messages = build_resolution_messages(
        message="e os outros?",
        history=history,
        map_name="Der Eisendrache",
        catalog=catalog,
    )

    assert "fire_bow.md" in messages[-1]["content"]
    assert "wolf_bow.md" in messages[-1]["content"]
    assert "[sources: fire_bow.md]" in messages[-1]["content"]


def test_document_options_reject_invented_paths_and_make_labels() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "der_eisendrache")

    options = validated_document_options(
        ["fire_bow.md", "invented.md", "fire_bow.md", "side_ee/brm_wallbuy.md"],
        catalog,
    )

    assert [(item.path, item.label) for item in options] == [
        ("fire_bow.md", "Fire Bow"),
        ("side_ee/brm_wallbuy.md", "BRM Wallbuy"),
    ]


def test_plural_variants_exclude_base_guide_and_build_safe_question() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "der_eisendrache")

    options = validated_document_options(
        [
            "wrath_of_the_ancients.md",
            "fire_bow.md",
            "lightning_bow.md",
            "void_bow.md",
            "wolf_bow.md",
        ],
        catalog,
        "e os arcos?",
    )
    question = clarification_for_options(
        "e os arcos?",
        "Der Eisendrache",
        options,
        "Qual deles?",
    )

    assert [item.path for item in options] == [
        "fire_bow.md",
        "lightning_bow.md",
        "void_bow.md",
        "wolf_bow.md",
    ]
    assert question.startswith("Encontrei 4 guias")


def test_broad_topic_options_are_derived_from_document_labels() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "der_eisendrache")

    options = deterministic_follow_up_options(
        "e os arcos?",
        [ConversationMessage(role="assistant", content="Resposta anterior.")],
        catalog,
    )

    assert [item.path for item in options] == [
        "fire_bow.md",
        "lightning_bow.md",
        "void_bow.md",
        "wolf_bow.md",
    ]


def test_other_options_are_siblings_of_the_previous_source() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "der_eisendrache")
    history = [
        ConversationMessage(
            role="assistant",
            content="Guia do arco de fogo.",
            source_paths=["fire_bow.md"],
        )
    ]

    options = deterministic_follow_up_options(
        "e os outros?",
        history,
        catalog,
    )

    assert [item.path for item in options] == [
        "wolf_bow.md",
        "lightning_bow.md",
        "void_bow.md",
    ]


def test_source_anchored_query_uses_previous_answer_document() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "der_eisendrache")
    history = [
        ConversationMessage(
            role="assistant",
            content="As peças do escudo ficam em três áreas.",
            source_paths=["shield.md"],
        )
    ]

    query = source_anchored_query("e onde monta?", history, catalog)
    retrieval = SearchEngine(knowledge_base).search(
        query,
        active_map_id="der_eisendrache",
        limit=10,
    )

    assert query == "e onde monta? Shield"
    assert {item.chunk.path for item in retrieval.chunks} == {"shield.md"}


def test_staff_family_excludes_generic_setup_and_final_stage() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "origins")

    options = deterministic_follow_up_options(
        "e os cajados?",
        [ConversationMessage(role="assistant", content="Resposta anterior.")],
        catalog,
    )

    assert [item.path for item in options] == [
        "fire_staff.md",
        "ice_staff.md",
        "lightning_staff.md",
        "wind_staff.md",
    ]


def test_other_staffs_are_siblings_of_the_previous_staff() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    catalog = document_catalog(knowledge_base, "origins")
    history = [
        ConversationMessage(
            role="assistant",
            content="Guia do cajado de fogo.",
            source_paths=["fire_staff.md"],
        )
    ]

    options = deterministic_follow_up_options(
        "e os outros?",
        history,
        catalog,
    )

    assert [item.path for item in options] == [
        "ice_staff.md",
        "lightning_staff.md",
        "wind_staff.md",
    ]
