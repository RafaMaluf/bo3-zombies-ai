"""Incident regression: wolf paintings -> arrow location must not become lightning."""

from pathlib import Path

import pytest

from app.answer_policy import answer_violations, build_contract
from app.chat_service import answer_chat
from app.conversation import continuation_document_paths, document_catalog
from app.knowledge_base import KnowledgeBase
from app.llm import GeneratedBlock, LLMResponse
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, ConversationMessage
from tests.test_planned_chat import PlannedLLM


@pytest.fixture(scope="module")
def services():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    return kb, SearchEngine(kb)


def wolf_history():
    return [
        ConversationMessage(role="user", content="musica de"),
        ConversationMessage(
            role="assistant", content="Dead Again.", source_paths=["side_ee/music_1_dead_again.md"]
        ),
        ConversationMessage(role="user", content="arco do lobo, ordem"),
        ConversationMessage(
            role="assistant",
            content="Interaja com as quatro pinturas.",
            source_paths=["wolf_bow.md", "wolf_bow.md"],
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["quick", "complete"])
@pytest.mark.parametrize(
    "question",
    [
        "onde eu pego a flecha?",
        "e a flecha?",
        "como pego a flecha?",
        "where do I get the arrow?",
        "donde consigo la flecha?",
    ],
)
async def test_arrow_follow_up_uses_only_wolf_sources_and_images(services, mode, question):
    kb, search = services
    llm = PlannedLLM()  # no resolver: this continuation needs no extra model call
    result = await answer_chat(
        ChatRequest(
            message=question,
            active_map_id="der_eisendrache",
            response_mode=mode,
            conversation_history=wolf_history(),
        ),
        kb,
        search,
        llm,
        lambda i, v: f"/{i}/{v}",
    )
    assert not result.need_clarification
    paths = {s.path for s in result.sources}
    assert "wolf_bow.md" in paths
    assert paths <= {"wolf_bow.md", "wrath_of_the_ancients.md", "power_pap_teleporter.md"}
    if mode == "quick" or question != "como pego a flecha?":
        assert paths == {"wolf_bow.md"}
    assert any("step 2" in s.section for s in result.sources)
    assert result.relevant_images
    assert all(kb.get_image(i.id).document_path in paths for i in result.relevant_images)
    for call in llm.calls:
        excerpts = call[-1]["content"]
        assert "wolf_bow.md" in excerpts
        assert "lightning_bow.md" not in excerpts
        assert "weathercock" not in excerpts.casefold()
    assert any("broken wall" in call[-1]["content"].casefold() for call in llm.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,path",
    [
        ("Como faço o arco elétrico?", "lightning_bow.md"),
        ("Como monto o escudo?", "shield.md"),
        ("Como libero o Pack-a-Punch?", "power_pap_teleporter.md"),
    ],
)
async def test_explicit_new_objective_overrides_previous_wolf(services, question, path):
    kb, search = services
    result = await answer_chat(
        ChatRequest(
            message=question, active_map_id="der_eisendrache", conversation_history=wolf_history()
        ),
        kb,
        search,
        PlannedLLM(),
        lambda i, v: f"/{i}/{v}",
    )
    assert {s.path for s in result.sources} == {path}


def test_ambiguous_history_and_family_requests_are_not_pinned(services):
    kb, _ = services
    catalog = document_catalog(kb, "der_eisendrache")
    for message in ["e os outros?", "e os arcos?", "como ativo a música?"]:
        assert not continuation_document_paths(message, wolf_history(), catalog)
    for sources in [[], ["wolf_bow.md", "lightning_bow.md"], ["invented.md"]]:
        history = wolf_history() + [
            ConversationMessage(role="assistant", content="Qual?", source_paths=sources)
        ]
        assert not continuation_document_paths("onde pego?", history, catalog)
    # A document belonging only to another map must never be resurrected.
    assert not continuation_document_paths(
        "onde pego?", wolf_history(), document_catalog(kb, "origins")
    )


@pytest.mark.parametrize("semantic", [False, True])
def test_scoped_ranking_never_leaks_other_guides_even_when_they_rank_higher(
    services, monkeypatch, semantic
):
    from app.domain import ScoredChunk

    kb, search = services
    if semantic:
        rank = search._rank_chunks
        wrong = next(
            c
            for c in kb.chunks.values()
            if c.map_id == "der_eisendrache" and c.path == "lightning_bow.md"
        )
        monkeypatch.setattr(
            search,
            "_rank_chunks",
            lambda *args: [ScoredChunk(chunk=wrong, score=100_000), *rank(*args)],
        )
    # Deliberately use the competing bow's unique vocabulary.
    result = search.search(
        "weathercock arrow lightning", "der_eisendrache", 10, document_paths=("wolf_bow.md",)
    )
    assert result.chunks
    assert {c.chunk.path for c in result.chunks} == {"wolf_bow.md"}


@pytest.mark.parametrize("detail", ["direct", "summary", "detailed"])
def test_point_contract_allows_the_relevant_excerpt_instead_of_forcing_the_first(services, detail):
    kb, search = services
    result = search.search(
        "onde pego a flecha? Wolf Bow", "der_eisendrache", 10, document_paths=("wolf_bow.md",)
    )
    arrow = next(c.chunk for c in result.chunks if "step 2" in c.chunk.section_title)
    assert result.chunks[0].chunk.id != arrow.id
    contract = build_contract(result.chunks, detail, ordered=False)
    response = LLMResponse(
        blocks=[
            GeneratedBlock(
                title="Flecha inicial",
                body="Desça e procure a parede quebrada à esquerda da escada.",
                source_ids=[arrow.id],
            )
        ]
    )
    assert not contract.requirements
    assert not answer_violations(response, contract)
    assert answer_violations(
        LLMResponse(blocks=[GeneratedBlock(body="Resposta inventada.", source_ids=["unknown"])]),
        contract,
    )
    assert answer_violations(LLMResponse(answer="Só introdução."), contract)
    assert answer_violations(
        LLMResponse(blocks=[GeneratedBlock(body="Sem fonte.", source_ids=[])]), contract
    )
