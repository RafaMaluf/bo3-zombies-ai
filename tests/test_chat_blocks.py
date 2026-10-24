import re
from pathlib import Path

import pytest
from planning_fakes import SeedPlanner

from app.assets import AssetManifest
from app.chat_service import answer_chat
from app.knowledge_base import KnowledgeBase
from app.llm import GeneratedBlock, LLMResponse
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, GuideState

ROOT = Path(__file__).resolve().parent.parent


class GroundedLLM(SeedPlanner):
    async def answer(self, messages, **kwargs):
        self.last_messages = messages
        self.last_contract = kwargs.get("contract")
        source_ids = re.findall(r"\[SOURCE ([^\]]+)\]", messages[-1]["content"])
        return LLMResponse(
            answer="Introdução.",
            blocks=[
                GeneratedBlock(
                    title=f"Etapa {index + 1}", body="Instruções da etapa.", source_ids=[source_id]
                )
                for index, source_id in enumerate(source_ids)
            ],
        )


@pytest.fixture(scope="module")
def services():
    kb = KnowledgeBase(
        ROOT / "maps", asset_manifest=AssetManifest.load(ROOT / "assets" / "image-manifest.json")
    )
    return kb, SearchEngine(kb), GroundedLLM(), lambda i, v: f"/media/{i}?variant={v}"


@pytest.mark.asyncio
async def test_chat_returns_shield_images_inside_each_part_and_plain_text_compatibility(services):
    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Como monto o escudo?",
            active_map_id="shadows_of_evil",
        ),
        *services,
    )
    illustrated = [b for b in response.blocks if b.images]
    # Three workbench locations supplement the three complete part groups.
    assert [len(b.images) for b in illustrated] == [3, 3, 3, 3]
    assert len(response.relevant_images) == 12
    assert response.introduction == "Introdução."
    assert "Instruções da etapa." in response.answer
    assert response.guide is None


@pytest.mark.asyncio
async def test_roadmap_start_help_completion_and_full_guide_keep_consistent_state(services):
    response = await answer_chat(
        ChatRequest(
            response_mode="complete", message="Como faço o EE de Origins?", active_map_id="origins"
        ),
        *services,
    )
    assert response.guide.mode == "overview"
    assert len([s for s in response.sources if s.path == "main_ee.md"]) == 9
    assert "staff_final_upgrade.md" in {s.path for s in response.sources}
    assert response.relevant_images
    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Começar",
            active_map_id="origins",
            guide_state=response.guide.state,
            guide_action="start",
        ),
        *services,
    )
    assert response.guide.mode == "phase"
    assert {s.path for s in response.sources} == {"main_ee.md", "power_pap.md"}
    assert response.guide.state.completed_phases == []
    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Concluí",
            active_map_id="origins",
            guide_state=response.guide.state,
            guide_action="complete",
        ),
        *services,
    )
    assert response.guide.state.phase == 1
    assert response.guide.state.completed_phases == [0]

    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Pode explicar melhor?",
            active_map_id="origins",
            guide_state=response.guide.state,
        ),
        *services,
    )
    assert response.guide.state.phase == 1
    assert response.guide.state.completed_phases == [0]
    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Ver guia completo",
            active_map_id="origins",
            guide_state=response.guide.state,
            guide_action="full",
        ),
        *services,
    )
    assert response.guide.mode == "full"
    assert len([s for s in response.sources if s.path == "main_ee.md"]) == 9
    assert len(response.relevant_images) > 8
    assert response.guide.state.completed_phases == [0]


@pytest.mark.asyncio
async def test_navigation_requests_next_instructions_instead_of_acknowledging_a_button(services):
    state = GuideState(map_id="origins", document_path="main_ee.md", phase=3, language="pt-BR")
    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Concluí esta fase",
            active_map_id="origins",
            guide_state=state,
            guide_action="complete",
        ),
        *services,
    )
    llm = services[2]
    question = llm.last_messages[-1]["content"].split("USER QUESTION\n", 1)[1]
    assert "Explain the CURRENT PHASE" in question
    assert "Concluí esta fase" not in question
    assert llm.last_contract.detail == "detailed"
    assert any(r.id.endswith("phase-4") for r in llm.last_contract.requirements)
    assert all(
        r.id.endswith("phase-4") for r in llm.last_contract.requirements if ":main_ee.md:" in r.id
    )
    assert "maxis_drone.md" in {s.path for s in response.sources}
    assert response.guide.state.completed_phases == [3]
    assert state.completed_phases == []


@pytest.mark.asyncio
async def test_requesting_all_shield_parts_stays_with_the_named_guide(services):
    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Como monto o escudo? Quero os locais de todas as peças.",
            active_map_id="shadows_of_evil",
        ),
        *services,
    )
    assert {s.path for s in response.sources} == {"shield.md", "build-table.md"}
    assert len(response.relevant_images) == 12
    assert [r.minimum_items for r in services[2].last_contract.requirements] == [0, 0, 0, 0]


@pytest.mark.asyncio
async def test_non_quest_detail_request_changes_contract_without_expanding_other_guides(services):
    for query, expected in [
        ("Passo a passo do Maxis Drone", "summary"),
        ("Passo a passo do Maxis Drone sem resumir, com todos os detalhes", "detailed"),
    ]:
        response = await answer_chat(
            ChatRequest(response_mode="complete", message=query, active_map_id="origins"), *services
        )
        assert services[2].last_contract.detail == expected
        assert {s.path for s in response.sources} == {"maxis_drone.md"}
