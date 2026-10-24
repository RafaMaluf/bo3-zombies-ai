import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.dependency_discovery import (
    DependencyReview,
    DiscoveredRequirement,
    MissingProcedure,
    discover_dependencies,
)
from app.domain import KnowledgeChunk, RetrievalResult, ScoredChunk
from app.guide_dependencies import (
    DependencyError,
    DependencyIndex,
    Requirement,
    map_catalog,
    source_digest,
)
from app.knowledge_base import KnowledgeBase
from app.source_planning import (
    PlannedSource,
    PlanningContext,
    SourcePlan,
    apply_plan,
    plan_violations,
    planning_context,
)

BASE = Path(__file__).resolve().parent.parent
CASES = json.loads((BASE / "tests/fixtures/guide_completeness.json").read_text())["cases"]


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(BASE / "maps")


def retrieval(chunks):
    return RetrievalResult(
        tuple(ScoredChunk(c, 1) for c in chunks), chunks[0].map_id, (), False, "", ()
    )


def plan_case(kb, case, detail="detailed"):
    index = DependencyIndex.load(kb)
    path = "main_ee.md" if case["id"].endswith("full") else case["required_paths"][0]
    roots = index.root_sets[f"{case['map_id']}:{path}"]
    catalog = {c.id: c for c in map_catalog(kb, case["map_id"])}
    result = retrieval([catalog[id_] for id_ in roots])
    context = planning_context(
        kb,
        result,
        case["message"],
        detail,
        "pt-BR",
        required_ids=tuple(roots) if path == "main_ee.md" else (),
    )
    selected_roots = index.roots(context)
    plan = index.resolve(selected_roots, context)
    assert not plan_violations(plan, context)
    return plan, context, apply_plan(plan, context, result)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_reference_cases_cover_requirements_without_unrelated_side_quests(kb, case):
    plan, context, result = plan_case(kb, case)
    chunks = [s.chunk for s in result.chunks]
    paths = {c.path for c in chunks}
    assert set(case["required_paths"]) <= paths
    assert not set(case["excluded_paths"]) & paths
    for path, titles in case.get("required_sections", {}).items():
        assert set(titles) <= {c.section_title for c in chunks if c.path == path}
    for pattern in case.get("excluded_title_patterns", []):
        assert not any(pattern in c.section_title.lower() for c in chunks)
    for earlier, later in case["before_paths"]:
        assert max(i for i, c in enumerate(chunks) if c.path == earlier) < min(
            i for i, c in enumerate(chunks) if c.path == later
        )
    for path_a, title_a, path_b, title_b in case.get("before_sections", []):
        assert next(
            i for i, c in enumerate(chunks) if (c.path, c.section_title) == (path_a, title_a)
        ) < next(i for i, c in enumerate(chunks) if (c.path, c.section_title) == (path_b, title_b))
    catalog = {c.id: c for c in context.candidates}
    assert len(chunks) == len({c.id for c in chunks})
    assert {i for c in chunks for i in c.image_ids} == {
        i for s in plan.steps
        for id_ in [s.source_id, *s.supporting_ids, *s.grouped_source_ids]
        for i in catalog[id_].image_ids
    }


def test_summary_and_full_have_the_same_required_sources(kb):
    full, _, _ = plan_case(kb, CASES[0])
    summary, _, _ = plan_case(kb, CASES[0], "summary")
    assert {s.source_id for s in full.steps} == {s.source_id for s in summary.steps}


def test_summary_compaction_keeps_every_source_and_dependency_order(kb):
    from app.guide_dependencies import compact_summary

    full, context, _ = plan_case(kb, CASES[0])
    compact = compact_summary(full, context)
    assert len(compact.steps) < len(full.steps)
    assert {
        id_
        for s in compact.steps
        for id_ in [s.source_id, *s.supporting_ids, *s.grouped_source_ids]
    } == {
        id_ for s in full.steps
        for id_ in [s.source_id, *s.supporting_ids, *s.grouped_source_ids]
    }
    assert not plan_violations(compact, context)


def test_explicitly_completed_staffs_skip_builds_without_advancing_the_quest(kb):
    full, context, _ = plan_case(kb, CASES[0])
    completed = [
        s.source_id for s in full.steps if any(token in s.source_id for token in ("staff",))
    ]
    plan = DependencyIndex.load(kb).resolve(context.required_ids, context, completed=completed)
    assert not set(completed) & {s.source_id for s in plan.steps}
    assert [s.source_id for s in plan.steps if ":main_ee.md:" in s.source_id] == list(
        context.required_ids
    )
    assert set(plan.completed_source_ids) == set(completed)


def test_completed_upgraded_states_include_base_and_shared_finalization(kb):
    _, context, _ = plan_case(kb, CASES[0])
    index = DependencyIndex.load(kb)
    upgrades = [
        c.id
        for c in context.candidates
        if c.path in {"fire_staff.md", "ice_staff.md", "lightning_staff.md", "wind_staff.md"}
        and "upgraded" in c.section_title.lower()
    ]
    completed = index.complete_requirements(upgrades, context)
    paths = {c.path for c in context.candidates if c.id in completed}
    assert {"staff_setup.md", "staff_final_upgrade.md"} <= paths
    assert len(completed) == 10
    single = index.complete_requirements(upgrades[:1], context)
    assert not any(c.path == "staff_final_upgrade.md" for c in context.candidates if c.id in single)


@pytest.mark.asyncio
async def test_guided_roots_are_not_reselected_by_the_model():
    from app.config import Settings
    from app.llm import LLMService

    c = section("a", "Self contained instructions.")
    context = PlanningContext(
        (c,), ("a",), [], inspect_dependencies=True, dependency_index=tiny_index((c,))
    )

    class Reader(LLMService):
        async def _validated_completion(self, messages, model, validate, contract=None):
            assert model is DependencyReview
            return DependencyReview()

    plan = await Reader(Settings(groq_api_key="")).plan_sources(context)
    assert [s.source_id for s in plan.steps] == ["a"]


def test_single_guide_phase_expands_only_its_requirements(kb):
    index = DependencyIndex.load(kb)
    phases = index.root_sets["origins:main_ee.md"]
    catalog = {c.id: c for c in map_catalog(kb, "origins")}
    context = PlanningContext(tuple(catalog.values()), (phases[1],), [], phase_mode=True)
    plan = index.resolve(context.required_ids, context)
    assert not plan_violations(plan, context)
    assert [s.source_id for s in plan.steps if catalog[s.source_id].category == "main_ee"] == [
        phases[1]
    ]
    assert any(catalog[s.source_id].path == "staff_final_upgrade.md" for s in plan.steps)


def test_changed_source_invalidates_the_derived_relationship(kb):
    _, context, _ = plan_case(kb, CASES[0])
    first = context.required_ids[0]
    stale = replace(
        context,
        candidates=tuple(
            replace(c, content=c.content + " changed") if c.id == first else c
            for c in context.candidates
        ),
    )
    with pytest.raises(DependencyError, match="desatualizado"):
        DependencyIndex.load(kb).resolve(stale.required_ids, stale)


def tiny_index(chunks):
    return DependencyIndex(
        dict(
            version=1,
            source_digests={c.id: source_digest(c) for c in chunks},
            reviewed_documents=[],
            requirements=[],
        )
    )


def section(id_, content):
    return KnowledgeChunk(id_, "map", "Map", id_ + ".md", "buildable", "", id_, content, (), 0)


def test_cycles_cross_map_ids_and_false_quotes_are_rejected():
    a = section("a", "Requires the other equipment.")
    b = section("b", "Requires the first equipment.")
    ctx = PlanningContext((a, b), (), [])
    index = tiny_index((a, b))
    with pytest.raises(DependencyError, match="Ciclo"):
        index.resolve(
            ("a",),
            ctx,
            discoveries=(
                Requirement("a", ("b",), a.content),
                Requirement("b", ("a",), b.content),
            ),
        )
    with pytest.raises(DependencyError, match="fora do mapa"):
        index.resolve(("a",), ctx, discoveries=(Requirement("a", ("elsewhere",), a.content),))
    with pytest.raises(DependencyError, match="evidência"):
        index.resolve(("a",), ctx, discoveries=(Requirement("a", ("b",), "Invented evidence."),))


@pytest.mark.asyncio
async def test_unknown_dependencies_are_read_in_full_and_expanded_transitively():
    a = section("a", "Requires second equipment. " + "Full instructions. " * 200)
    b = section("b", "Requires third equipment.")
    c = section("c", "Build the third equipment using these instructions.")
    index = tiny_index((a, b, c))
    context = PlanningContext((a, b, c), (), [], inspect_dependencies=True, dependency_index=index)

    class Reader:
        def __init__(self):
            self.seen = []

        async def _validated_completion(self, messages, model, validate):
            full = json.loads(messages[1]["content"])["full_sections"]
            self.seen.extend("\n".join(s["lines"].values()) for s in full)
            rules = []
            for s in full:
                if s["id"] in ("0", "1"):
                    rules.append(
                        DiscoveredRequirement(
                            consumer_id=s["id"],
                            source_ids=[str(int(s["id"]) + 1)],
                            evidence_start_line=1,
                            evidence_end_line=1,
                        )
                    )
            review = DependencyReview(requirements=rules)
            assert not validate(review)
            return review

    reader = Reader()
    plan = await discover_dependencies(
        reader, context, SourcePlan(steps=[PlannedSource(source_id="a", role="objective")])
    )
    assert [s.source_id for s in plan.steps] == ["c", "b", "a"]
    assert a.content in reader.seen
    assert b.content in reader.seen and c.content in reader.seen
    assert not plan_violations(plan, context)


@pytest.mark.asyncio
async def test_discovery_does_not_promote_future_phases_optional_gear_or_base_item_upgrades():
    a = replace(
        section("a", "Requires the base item.\nRecommended optional equipment."), category="main_ee"
    )
    b = replace(section("b", "Continue with the next main phase."), category="main_ee")
    upgrade = replace(section("upgrade", "Upgrade the base item."), path="side_ee/upgrade_item.md")
    optional = section("optional", "Obtain optional equipment.")
    cs = (a, b, upgrade, optional)
    ctx = PlanningContext(
        cs, ("a", "b"), [], inspect_dependencies=True, dependency_index=tiny_index(cs)
    )

    class Reader:
        async def _validated_completion(self, messages, model, validate):
            review = DependencyReview(
                requirements=[
                    DiscoveredRequirement(
                        consumer_id="0",
                        source_ids=["1", "2"],
                        evidence_start_line=1,
                        evidence_end_line=1,
                    ),
                    DiscoveredRequirement(
                        consumer_id="0",
                        source_ids=["3"],
                        evidence_start_line=2,
                        evidence_end_line=2,
                    ),
                ]
            )
            assert not validate(review)
            return review

    plan = await discover_dependencies(
        Reader(),
        ctx,
        SourcePlan(steps=[PlannedSource(source_id=s, role="objective") for s in ctx.required_ids]),
    )
    assert [s.source_id for s in plan.steps] == ["a", "b"]


@pytest.mark.asyncio
async def test_actual_missing_delegated_guide_returns_an_explicit_error():
    a = section("a", "See the dedicated missing portal guide before continuing.")
    ctx = PlanningContext(
        (a,), (), [], inspect_dependencies=True, dependency_index=tiny_index((a,))
    )

    class Reader:
        async def _validated_completion(self, messages, model, validate):
            review = DependencyReview(
                unresolved=[
                    MissingProcedure(
                        consumer_id="0",
                        reference_name="missing portal guide",
                        evidence_start_line=1,
                        evidence_end_line=1,
                    )
                ]
            )
            assert not validate(review)
            return review

    with pytest.raises(DependencyError, match="missing portal guide"):
        await discover_dependencies(
            Reader(), ctx, SourcePlan(steps=[PlannedSource(source_id="a", role="objective")])
        )
