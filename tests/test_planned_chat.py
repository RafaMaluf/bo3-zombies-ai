import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.chat_service import answer_chat
from app.config import settings
from app.guide_dependencies import map_catalog
from app.knowledge_base import KnowledgeBase
from app.llm import GeneratedBlock, LLMResponse, LLMResponseError, LLMUnavailableError
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, ConversationMessage
from app.source_planning import PlannedSource, SourcePlan


class PlannedLLM:
    def __init__(self, plan=None, error=None, fail_batch=None):
        self.plan = plan
        self.error = error
        self.fail_batch = fail_batch
        self.calls = []

    async def plan_sources(self, context):
        self.context = context
        if self.error:
            raise self.error
        return self.plan or SourcePlan(
            steps=[PlannedSource(source_id=id_, role="objective") for id_ in context.required_ids]
        )

    async def answer(self, messages, **kwargs):
        self.calls.append(messages)
        if self.fail_batch == len(self.calls):
            raise LLMResponseError("Failed batch")
        ids = re.findall(r"\[SOURCE ([^\]]+)\]", messages[-1]["content"])
        return LLMResponse(
            answer="Introdução." if len(self.calls) == 1 else "",
            blocks=[
                GeneratedBlock(title="Etapa", body="Explicação.", source_ids=[id_]) for id_ in ids
            ],
        )


@pytest.fixture(scope="module")
def services():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    return kb, SearchEngine(kb)


@pytest.mark.asyncio
@pytest.mark.parametrize("map_id", ["der_eisendrache", "origins"])
async def test_easter_egg_roadmap_keeps_images_from_main_and_dependency_guides(services, map_id):
    kb, search = services
    response = await answer_chat(
        ChatRequest(
            response_mode="complete",
            message="Como faço o Easter Egg principal?",
            active_map_id=map_id,
        ),
        kb,
        search,
        PlannedLLM(),
        lambda i, v: f"/{i}/{v}",
    )
    assert response.guide.mode == "overview"
    assert response.blocks
    assert response.relevant_images
    assert all(image.thumbnail_url for image in response.relevant_images)
    assert len({source.path for source in response.sources}) > 1
    assert any(block.images for block in response.blocks)
    main_paths = {"main_ee.md", "main-ee.md"}
    main_ids = {source.chunk_id for source in response.sources if source.path in main_paths}
    assert any(block.images and set(block.source_ids) & main_ids for block in response.blocks)
    assert any(block.images and not set(block.source_ids) & main_ids for block in response.blocks)


@pytest.mark.asyncio
async def test_pack_a_punch_excludes_unrelated_sections_and_attaches_location_support(services):
    kb, search = services
    sections = {
        c.section_title: c
        for c in kb.chunks.values()
        if c.map_id == "der_eisendrache" and c.path == "power_pap_teleporter.md"
    }
    power = sections["power"]
    pap = sections["how to rebuild Pack-a-Punch"]
    photos = [c.id for c in sections.values() if "Pack-a-Punch location" in c.section_title]
    plan = SourcePlan(
        steps=[
            PlannedSource(
                source_id=power.id,
                role="prerequisite",
                anchor_id=pap.id,
                evidence="Turn on the power.",
            ),
            PlannedSource(source_id=pap.id, role="objective", supporting_ids=photos),
        ]
    )
    llm = PlannedLLM(plan)
    request = ChatRequest(
        response_mode="complete",
        message="Como libero o Pack-a-Punch?",
        active_map_id="der_eisendrache",
        conversation_history=[
            ConversationMessage(
                role="assistant", content="Falamos dos arcos.", source_paths=["fire_bow.md"]
            )
        ],
    )
    response = await answer_chat(request, kb, search, llm, lambda i, v: f"/{i}/{v}")
    assert len(response.blocks) == 3
    assert len(response.relevant_images) == 6
    assert set(photos) <= {s.chunk_id for s in response.sources}
    assert not any("Wundersphere" in s.section for s in response.sources)
    assert all(s.path == "power_pap_teleporter.md" for s in response.sources)


@pytest.mark.asyncio
async def test_full_guide_batches_return_one_complete_response_in_execution_order(services):
    kb, search = services
    llm = PlannedLLM()
    response = await answer_chat(
        ChatRequest(
            response_mode="complete", message="EE de Origins completo", active_map_id="origins"
        ),
        kb,
        search,
        llm,
        lambda i, v: f"/{i}/{v}",
    )
    assert len(llm.calls) >= 2
    assert response.introduction == "Introdução."
    main_ids = [s for b in response.blocks for s in b.source_ids if ":main_ee.md:" in s]
    assert len(main_ids) == 9
    assert all(main_ids[i].endswith(f"phase-{i}") for i in range(9))
    assert "staff_final_upgrade.md" in {s.path for s in response.sources}
    assert len(response.guide.phases) == 9
    assert response.guide.state.completed_phases == []


@pytest.mark.asyncio
async def test_multi_guide_images_are_not_cut_at_the_legacy_36_image_budget(services):
    class StaffPlanner(PlannedLLM):
        async def plan_sources(self, context):
            roots = list(context.required_ids)
            dependencies = [
                c for c in context.candidates if c.path in {"fire_staff.md", "ice_staff.md"}
            ]
            self.expected_images = {
                i
                for c in context.candidates
                if c.id in roots or c in dependencies
                for i in c.image_ids
            }
            return SourcePlan(
                steps=[
                    PlannedSource(source_id=roots[0], role="objective"),
                    *(
                        PlannedSource(
                            source_id=c.id,
                            role="prerequisite",
                            anchor_id=roots[1],
                            evidence="Craft and upgrade all the 4 staffs.",
                        )
                        for c in dependencies
                    ),
                    *(PlannedSource(source_id=id_, role="objective") for id_ in roots[1:]),
                ]
            )

    kb, search = services
    llm = StaffPlanner()
    response = await answer_chat(
        ChatRequest(
            response_mode="complete", message="EE de Origins completo", active_map_id="origins"
        ),
        kb,
        search,
        llm,
        lambda i, v: f"/{i}/{v}",
    )
    ids = [image.id for image in response.relevant_images]
    assert len(ids) > 36
    assert len(ids) == len(set(ids))
    required_paths = {
        "power_pap.md",
        "staff_setup.md",
        "fire_staff.md",
        "ice_staff.md",
        "lightning_staff.md",
        "wind_staff.md",
        "staff_final_upgrade.md",
        "g_strike.md",
        "maxis_drone.md",
        "one_inch_punch.md",
        "main_ee.md",
    }
    expected = {
        i for c in map_catalog(kb, "origins") if c.path in required_paths for i in c.image_ids
    }
    expected.update(
        i
        for c in map_catalog(kb, "origins")
        if c.section_title == "Normal shovel and snowy digs"
        for i in c.image_ids
    )
    assert set(ids) == expected


@pytest.mark.asyncio
async def test_a_failed_parallel_batch_does_not_return_a_complete_guide(services):
    kb, search = services
    llm = PlannedLLM(fail_batch=2)
    with pytest.raises(HTTPException) as error:
        await answer_chat(
            ChatRequest(
                response_mode="complete", message="EE de Origins completo", active_map_id="origins"
            ),
            kb,
            search,
            llm,
            lambda i, v: "",
        )
    # Already-started siblings are cancelled, never returned as complete.
    assert len(llm.calls) == 4
    assert error.value.status_code == 502


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,status",
    [
        (LLMUnavailableError("Provider unavailable"), 503),
        (LLMResponseError("Invalid plan"), 502),
    ],
)
async def test_planning_failures_have_explicit_http_errors(services, error, status, monkeypatch):
    kb, search = services
    # Force unknown coverage: Revelations now has reviewed local requirements.
    monkeypatch.setattr("app.guide_dependencies.DependencyIndex.covers", lambda *args: False)
    with pytest.raises(HTTPException) as caught:
        await answer_chat(
            ChatRequest(
                response_mode="complete", message="EE Revelations", active_map_id="revelations"
            ),
            kb,
            search,
            PlannedLLM(error=error),
            lambda i, v: "",
        )
    assert caught.value.status_code == status


@pytest.mark.asyncio
async def test_plan_capacity_limits_are_explicit_and_do_not_generate_an_answer(
    services, monkeypatch
):
    kb, search = services
    llm = PlannedLLM()
    monkeypatch.setattr(type(settings), "max_plan_sources", 1)
    with pytest.raises(HTTPException) as caught:
        await answer_chat(
            ChatRequest(response_mode="complete", message="EE Origins", active_map_id="origins"),
            kb,
            search,
            llm,
            lambda i, v: "",
        )
    assert caught.value.status_code == 422
    assert not llm.calls
