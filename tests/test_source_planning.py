from dataclasses import replace
from pathlib import Path

import pytest

from app.domain import KnowledgeChunk, RetrievalResult, ScoredChunk
from app.guide_dependencies import DependencyIndex
from app.knowledge_base import KnowledgeBase
from app.source_planning import (
    PlanCapacityError,
    PlannedSource,
    PlanningContext,
    SourcePlan,
    apply_plan,
    plan_violations,
    planning_context,
)


def chunk(id_, text, path="pap.md", images=()):
    return KnowledgeChunk(id_, "map", "Map", path, "pap", "", id_, text, images, 0)


def result(*chunks):
    return RetrievalResult(tuple(ScoredChunk(c, 1) for c in chunks), "map", (), False, "", ())


POWER = chunk("power", "Press the switch in the power room.", "power.md", ("power-photo",))
PAP = chunk("pap", "Turn on the power. Then assemble the machine.", images=("pap-photo",))
EXTRA = chunk("extra", "An unrelated side quest.", "side.md")
CONTEXT = PlanningContext((POWER, PAP, EXTRA), ("pap",), [])


def valid_plan():
    return SourcePlan(
        steps=[
            PlannedSource(
                source_id="power",
                role="prerequisite",
                anchor_id="pap",
                evidence="Turn on the power.",
            ),
            PlannedSource(source_id="pap", role="objective"),
        ]
    )


def test_plan_orders_dependencies_and_keeps_the_exact_source_images():
    plan = valid_plan()
    assert not plan_violations(plan, CONTEXT)
    selected = apply_plan(plan, CONTEXT, result(PAP))
    assert [s.chunk.path for s in selected.chunks] == ["power.md", "pap.md"]
    assert [s.chunk.image_ids for s in selected.chunks] == [("power-photo",), ("pap-photo",)]
    assert [s.chunk.position for s in selected.chunks] == [0, 1]
    assert not any(s.chunk.id == "extra" for s in selected.chunks)
    hidden = apply_plan(plan, CONTEXT, result(PAP), hide_images=True)
    assert all(not s.chunk.image_ids for s in hidden.chunks)


@pytest.mark.parametrize(
    "defect",
    [
        "unknown",
        "self-anchor",
        "unselected-anchor",
        "invented-quote",
        "empty-quote",
        "wrong-order",
        "missing-phase",
        "duplicate",
        "root-evidence",
        "empty",
        "cycle",
    ],
)
def test_invalid_dependencies_never_enter_the_answer_context(defect):
    plan = valid_plan()
    dep = plan.steps[0]
    if defect == "unknown":
        dep.source_id = "another-map:invented"
    elif defect == "self-anchor":
        dep.anchor_id = "power"
    elif defect == "unselected-anchor":
        dep.anchor_id = "extra"
    elif defect == "invented-quote":
        dep.evidence = "The shield is required for Pack-a-Punch."
    elif defect == "empty-quote":
        dep.evidence = ""
    elif defect == "wrong-order":
        plan.steps.reverse()
    elif defect == "missing-phase":
        plan.steps.pop()
    elif defect == "duplicate":
        plan.steps.append(plan.steps[1])
    elif defect == "root-evidence":
        plan.steps[1].evidence = "Not a dependency"
    elif defect == "empty":
        plan.steps = []
    else:
        plan.steps[1].role = "prerequisite"
        plan.steps[1].anchor_id = "power"
        plan.steps[1].evidence = POWER.content
    assert plan_violations(plan, CONTEXT)
    with pytest.raises(ValueError, match="invalid"):
        apply_plan(plan, CONTEXT, result(PAP))


def test_source_planner_schema_cannot_ask_the_player_to_choose_files():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SourcePlan(need_clarification=True, clarification_question="Qual arquivo devo usar?")


def test_compact_source_aliases_are_converted_to_canonical_ids():
    plan = SourcePlan(
        steps=[
            PlannedSource(
                source_id="0", role="prerequisite", anchor_id="1", evidence="Turn on the power."
            ),
            PlannedSource(source_id="1", role="objective"),
        ]
    )
    canonical = CONTEXT.canonical_plan(plan)
    assert not plan_violations(canonical, CONTEXT)
    assert canonical.steps[0].source_id == "power"
    assert canonical.steps[0].anchor_id == "pap"
    assert plan.steps[0].source_id == "0"


def test_supporting_sections_attach_their_text_and_images_to_the_relevant_step():
    location = replace(EXTRA, content="The piece is beside the stairs.", image_ids=("location",))
    ctx = replace(CONTEXT, candidates=(POWER, PAP, location))
    plan = valid_plan()
    plan.steps[1].supporting_ids = ["extra"]
    answer = apply_plan(plan, ctx, result(PAP))
    step = answer.chunks[1].chunk
    assert "beside the stairs" in step.content
    assert step.image_ids == ("pap-photo", "location")
    assert PAP.content == "Turn on the power. Then assemble the machine."


@pytest.mark.parametrize("support", [["not-in-map"], ["pap"], ["extra", "extra"]])
def test_supporting_sections_cannot_inject_unknown_or_repeated_sources(support):
    plan = valid_plan()
    plan.steps[1].supporting_ids = support
    assert plan_violations(plan, CONTEXT)


def test_phase_plan_cannot_pull_a_later_main_quest_phase_even_as_support():
    later = replace(EXTRA, category="main_ee")
    ctx = replace(CONTEXT, candidates=(POWER, PAP, later), phase_mode=True)
    plan = valid_plan()
    plan.steps[1].supporting_ids = ["extra"]
    assert plan_violations(plan, ctx)


def test_required_phases_keep_their_relative_order():
    ctx = replace(CONTEXT, required_ids=("pap", "power"))
    assert plan_violations(valid_plan(), ctx)


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")


def test_every_map_catalog_is_available_within_the_default_planning_budget(kb):
    for map_id in kb.maps:
        seed = next(c for c in kb.chunks.values() if c.map_id == map_id)
        ctx = planning_context(kb, result(seed), "Como faço?", "detailed", "pt-BR")
        assert {c.path for c in ctx.candidates} == set(kb.maps[map_id].document_paths)
        assert all(c.map_id == map_id for c in ctx.candidates)
        assert sum(len(m["content"]) for m in ctx.messages) <= 22_000
        views = {v["id"] for v in DependencyIndex.load(kb).source_views}
        assert all(c.id in kb.chunks or ":phase-" in c.id or c.id in views
                   for c in ctx.candidates)


def test_zetsubou_references_expose_trials_and_electric_shield_relationship(kb):
    roots = tuple(
        c for c in kb.chunks.values() if c.map_id == "zetsubou_no_shima" and c.path == "main_ee.md"
    )
    context = planning_context(kb, result(*roots), "EE completo", "detailed", "pt-BR")
    hints = context.messages[-1]["content"].split("LOCAL REFERENCE EXCERPTS", 1)[1]
    assert "After completing **all 3 trials** and collecting **all 3 rewards**" in hints
    assert "electrifying the shield after all trials are completed" in hints


def test_planning_excerpt_budget_never_truncates_answer_source_content(kb):
    seed = next(c for c in kb.chunks.values() if c.map_id == "origins" and c.path == "main_ee.md")
    ctx = planning_context(kb, result(seed), "EE completo", "detailed", "pt-BR")
    assert any(c.content for c in ctx.candidates)
    # Original monolithic source is retained as a seed alongside runtime phases.
    selected = next(c for c in ctx.candidates if c.id == seed.id)
    assert selected.content == seed.content
    with pytest.raises(PlanCapacityError):
        planning_context(kb, result(seed), "EE", "detailed", "pt-BR", max_chars=100)
    with pytest.raises(PlanCapacityError):
        planning_context(kb, result(seed, replace(seed, map_id="other")), "EE", "detailed", "pt-BR")
