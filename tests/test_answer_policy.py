from dataclasses import replace
from pathlib import Path

import pytest

from app.answer_policy import (
    AnswerContract,
    SourceRequirement,
    answer_violations,
    build_contract,
    expand_procedure,
    resolve_answer_intent,
    retrieval_query,
)
from app.assets import AssetManifest
from app.knowledge_base import KnowledgeBase
from app.llm import GeneratedBlock, LLMResponse
from app.retrieval import SearchEngine

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "query,detail,whole",
    [
        ("Como monto o escudo?", "detailed", True),
        ("Como monto o escudo e onde ficam as peças?", "detailed", True),
        ("escudo", "detailed", True),
        ("Passo a passo do escudo", "summary", True),
        ("Passo a passo do escudo sem resumir", "detailed", True),
        ("Me passa o EE de Origins", "summary", True),
        ("EE Origins", "summary", True),
        ("Me explica o EE explicadinho", "detailed", True),
        ("Quero o EE mastigado", "detailed", True),
        ("Guia do começo ao fim, sem pular nada", "detailed", True),
        ("Não resuma o guia", "detailed", True),
        ("Não quero resumo do EE", "detailed", True),
        ("Não quero o guia completo, só o resumo", "summary", True),
        ("Passo a passo do Maxis Drone", "summary", True),
        ("Passo a passo do Maxis Drone com todos os detalhes", "detailed", True),
        ("Onde está a terceira peça do escudo?", "direct", False),
        ("Como encontro o cérebro do Maxis Drone?", "direct", False),
        ("O EE de Origins pode ser feito solo?", "direct", False),
        ("Precisa de 4 jogadores para fazer o EE?", "direct", False),
        ("Como faço o EE de Origins solo?", "summary", True),
        ("Me explica por que o EE falha?", "direct", False),
        ("Explique essa fase sem resumir", "detailed", False),
        ("Resuma essa etapa", "summary", False),
        ("How do I complete the Origins Easter Egg?", "summary", True),
        ("Full guide without summarizing", "detailed", True),
        ("Without summary", "detailed", True),
        ("Step by step for the shield", "summary", True),
        ("Where is the shield part?", "direct", False),
        ("Guide complet sans résumé", "detailed", True),
    ],
)
def test_detail_and_scope_are_resolved_before_generation(query, detail, whole):
    intent = resolve_answer_intent(query)
    assert intent.detail == detail
    assert intent.whole_procedure is whole


@pytest.fixture(scope="module")
def knowledge():
    kb = KnowledgeBase(
        ROOT / "maps", asset_manifest=AssetManifest.load(ROOT / "assets" / "image-manifest.json")
    )
    return kb, SearchEngine(kb)


def test_whole_procedure_includes_all_parts_but_not_unrequested_shield_upgrade(knowledge):
    kb, search = knowledge
    query = "Como monto o escudo sem resumir?"
    result = search.search(query, "shadows_of_evil", 1)
    result = expand_procedure(result, kb, resolve_answer_intent(query), query)
    assert len(result.chunks) == 4
    assert sum(len(c.chunk.image_ids) for c in result.chunks) == 9
    assert not any("upgraded" in c.chunk.section_title for c in result.chunks)


def test_detailed_is_complete_within_one_guide_not_implicit_dependencies(knowledge):
    kb, search = knowledge
    query = "Passo a passo do Maxis Drone sem resumir"
    original = search.search(query, "origins", 1)
    result = expand_procedure(original, kb, resolve_answer_intent(query), query)
    assert {c.chunk.path for c in result.chunks} == {"maxis_drone.md"}
    expected = [
        c for c in kb.chunks.values() if c.map_id == "origins" and c.path == "maxis_drone.md"
    ]
    assert len(result.chunks) == len(expected)


def test_targeted_question_does_not_expand_to_the_entire_guide(knowledge):
    kb, search = knowledge
    query = "Onde fica a terceira peça do escudo?"
    original = search.search(query, "shadows_of_evil", 1)
    assert expand_procedure(original, kb, resolve_answer_intent(query), query) is original


def test_all_details_is_not_a_comparison_between_unrelated_guides(knowledge):
    kb, search = knowledge
    query = "Passo a passo do Maxis Drone sem resumir, com todos os detalhes."
    cleaned = retrieval_query(query)
    assert "todos" not in cleaned
    result = search.search(cleaned, "origins", 10)
    result = expand_procedure(result, kb, resolve_answer_intent(query), query)
    assert {c.chunk.path for c in result.chunks} == {"maxis_drone.md"}


def test_retrieval_preserves_real_comparisons_and_named_objectives():
    assert "todos os mapas" in retrieval_query("Compare todos os mapas")
    assert "g strike" in retrieval_query("G-Strike e Maxis Drone, com todos os detalhes")
    assert "maxis drone" in retrieval_query("G-Strike e Maxis Drone, com todos os detalhes")


def test_all_parts_of_a_named_shield_does_not_require_unrelated_guides(knowledge):
    kb, search = knowledge
    query = "Como monto o escudo? Quero os locais de todas as peças."
    result = search.search(retrieval_query(query), "shadows_of_evil", 10)
    paths = search.explicit_document_paths(query, "shadows_of_evil")
    assert paths == ("shield.md",)
    result = expand_procedure(result, kb, resolve_answer_intent(query), query, paths)
    assert {c.chunk.path for c in result.chunks} == {"shield.md"}
    assert sum(len(c.chunk.image_ids) for c in result.chunks) == 9


def test_summary_contract_keeps_source_coverage_but_not_detailed_list_counts(knowledge):
    kb, search = knowledge
    query = "Passo a passo do escudo"
    result = expand_procedure(
        search.search(query, "shadows_of_evil", 1), kb, resolve_answer_intent(query), query
    )
    contract = build_contract(result.chunks, "summary", ordered=True)
    assert len(contract.requirements) == 4
    assert all(r.minimum_items == 0 for r in contract.requirements)
    detailed = build_contract(result.chunks, "detailed", ordered=True)
    assert all(r.minimum_items == 0 for r in detailed.requirements)


def sample_contract():
    return AnswerContract(
        "detailed",
        ("one", "two"),
        (SourceRequirement("one", 6, 2), SourceRequirement("two", 6, 0)),
        ordered=True,
    )


def good_answer():
    return LLMResponse(
        blocks=[
            GeneratedBlock(
                body="- Primeiro local possível fica junto à escada.\n"
                "- Segundo local possível fica perto da porta.",
                source_ids=["one"],
            ),
            GeneratedBlock(
                body="Depois de recolher todas as peças, monte o escudo na bancada.",
                source_ids=["two"],
            ),
        ]
    )


def test_complete_grounded_ordered_answer_passes():
    assert not answer_violations(good_answer(), sample_contract())


@pytest.mark.parametrize("defect", ["missing", "brief", "items", "unknown", "order", "merged"])
def test_measurable_incompleteness_and_invalid_references_are_rejected(defect):
    answer = good_answer()
    if defect == "missing":
        answer.blocks.pop()
    elif defect == "brief":
        answer.blocks[1].body = "Pronto."
    elif defect == "items":
        answer.blocks[
            0
        ].body = "Os dois locais ficam próximos da escada e da porta, respectivamente."
    elif defect == "unknown":
        answer.blocks[0].source_ids = ["invented"]
    elif defect == "order":
        answer.blocks.reverse()
    else:
        answer.blocks[0].source_ids = ["one", "two"]
    assert answer_violations(answer, sample_contract())


def test_clarification_and_brief_completion_are_explicit_exceptions():
    clarification = LLMResponse(need_clarification=True, clarification_question="Qual mapa?")
    assert answer_violations(clarification, sample_contract())
    assert not answer_violations(clarification, replace(sample_contract(), detail="direct"))
    assert not answer_violations(
        LLMResponse(answer="Última fase concluída."),
        replace(sample_contract(), allow_brief_completion=True),
    )


def test_summary_word_budget_guides_style_without_discarding_valid_sections():
    contract = replace(
        sample_contract(),
        detail="summary",
        requirements=(
            SourceRequirement("one", 3, 0, maximum_words=10),
            SourceRequirement("two", 3, 0, maximum_words=10),
        ),
    )
    assert "aim for at most 10 words" in contract.instructions()
    assert not answer_violations(good_answer(), contract)
    missing = good_answer()
    missing.blocks.pop()
    assert answer_violations(missing, contract)
    answer = good_answer()
    answer.blocks[0].body = "Recolha as peças nos locais indicados."
    answer.blocks[1].body = "Monte o escudo na bancada."
    assert not answer_violations(answer, contract)
