"""Acceptance cases from a map-by-map reading, independent of model answers."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.chat_service import answer_chat
from app.domain import KnowledgeChunk
from app.guide_dependencies import (
    DependencyError,
    DependencyIndex,
    compact_summary,
    map_catalog,
    source_digest,
)
from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine
from app.schemas import ChatRequest
from app.source_planning import PlanningContext, plan_violations
from tests.test_planned_chat import PlannedLLM

BASE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(BASE / "maps")


def resolve(kb, mid, path, scope=""):
    index = DependencyIndex.load(kb)
    context = PlanningContext(map_catalog(kb, mid), (), [], dependency_index=index)
    plan = index.resolve(index.root_sets[f"{mid}:{path}" + scope], context)
    assert not plan_violations(plan, context)
    assert len(plan.steps) <= 96
    sources = {c.id: c for c in context.candidates}
    selected = [sources[s.source_id] for s in plan.steps]
    assert len(selected) == len({s.id for s in selected})
    assert all(c.map_id == mid for c in selected)
    return plan, selected, context


@pytest.mark.parametrize("mid,path,required,excluded", [
    ("verruckt", "samantha_dolls.md", {"music_ee.md"}, set()),
    ("the_giant", "main_ee_annihilator.md", {"pap_teleporters.md"}, {"extra_perk.md"}),
    ("the_giant", "extra_perk.md", {"pap_teleporters.md"}, {"main_ee_annihilator.md"}),
    ("kino_der_toten", "film_reels.md", {"power_pap.md"}, {"samantha_sorrow.md"}),
    ("ascension", "main_ee.md", {"power_pap.md", "space_monkeys.md"}, {"samantha_sorrow.md"}),
    ("shangri_la", "main_ee.md", {"power_pap.md"}, {"samantha_hide_and_seek.md"}),
    ("moon", "main_ee.md", {"power_pap.md", "pes.md", "hacker.md", "qed.md"}, {"space_dog.md"}),
    ("moon", "space_dog.md", {"power_pap.md", "hacker.md"}, {"main_ee.md"}),
    ("shadows_of_evil", "main-ee.md", {"pap.md", "sword.md"},
     {"shield.md", "civil-protector.md", "wonder_weapon.md"}),
    ("shadows_of_evil", "wonder_weapon.md", {"pods.md"}, {"pap.md", "main-ee.md"}),
    ("der_eisendrache", "side_ee/plunger.md", {"fire_bow.md", "ragnarock.md"}, {"main_ee.md"}),
    ("gorod_krovi", "gauntlet.md", {"power_pap.md"}, {"dragon_strike.md", "shield.md"}),
    ("gorod_krovi", "main_ee.md", {"gauntlet.md", "dragon_strike.md", "shield.md"},
     {"side_ee/dragon_wings.md", "side_ee/shield_upgrade.md"}),
    ("revelations", "main_ee.md", {"pap.md", "keeper_protector.md", "pap_apothican_servant.md"},
     {"shield.md", "side_ee/masks.md", "side_ee/wisp.md", "side_ee/upgrade_lil_arnies.md"}),
    ("zetsubou_no_shima", "side_ee/free_widows_wine.md", {"kt4.md", "masamune.md"},
     {"trials.md", "skull_of_nan_sapwe.md", "shield.md", "main_ee.md"}),
    ("nacht_der_untoten", "samantha_dolls.md", set(), {"music_ee.md"}),
    ("shi_no_numa", "samantha_dolls.md", set(), {"music_ee.md"}),
])
def test_reviewed_chains_include_actual_requirements_not_unrelated_quests(
    kb, mid, path, required, excluded,
):
    _, selected, _ = resolve(kb, mid, path)
    paths = {c.path for c in selected}
    assert required <= paths
    assert not excluded & paths


def test_base_and_upgrades_and_partial_fire_wall_are_different_scopes(kb):
    _, base, _ = resolve(kb, "gorod_krovi", "dragon_strike.md")
    _, upgraded, _ = resolve(kb, "gorod_krovi", "dragon_strike.md", ":upgrade")
    assert not any("upgrade" in c.section_title.lower() for c in base)
    assert any("second lockdown" in c.section_title for c in upgraded)
    _, plunger, _ = resolve(kb, "der_eisendrache", "side_ee/plunger.md")
    fire = [c.section_title for c in plunger if c.path == "fire_bow.md"]
    assert fire == ["step 1 - start the quest"]


def test_de_bows_are_conditional_and_shield_upgrades_are_not_ee_gates(kb):
    plan, selected, _ = resolve(kb, "der_eisendrache", "main_ee.md")
    conditions = {s.source_id: s.condition for s in plan.steps}
    bows = [c for c in selected if c.path.endswith("_bow.md")]
    assert {c.path for c in bows} == {
        "fire_bow.md", "wolf_bow.md", "void_bow.md", "lightning_bow.md",
    }
    assert all("Alternative bow route" in conditions[c.id] for c in bows)
    assert all("Ranked" in conditions[c.id] for c in bows)
    _, gorod, _ = resolve(kb, "gorod_krovi", "main_ee.md")
    assert not any("upgrade" in c.section_title.lower() for c in gorod
                   if c.path in {"shield.md", "dragon_strike.md"})


def test_illustrations_do_not_require_gold_upgrades_or_main_quest(kb):
    plan, _, context = resolve(kb, "origins", "ice_staff.md")
    sources = {c.id: c for c in context.candidates}
    support = [sources[i] for s in plan.steps for i in s.supporting_ids]
    assert len(support) == 1
    assert "golden shovel" not in support[0].content.lower()
    assert len(support[0].image_ids) == 6
    parent = next(c for c in context.candidates if c.path == "shovel_upgrades.md"
                  and c.category != "reference")
    assert not set(parent.image_ids[6:]) & set(support[0].image_ids)
    plan, selected, context = resolve(kb, "shangri_la", "samantha_hide_and_seek.md")
    assert not any(c.category == "main_ee" for c in selected)
    sources = {c.id: c for c in context.candidates}
    support = [sources[i] for s in plan.steps for i in s.supporting_ids]
    assert len(support) == 1
    assert "gongs are located" in support[0].content
    assert "Fractalizer" not in support[0].content
    assert len(support[0].image_ids) == 8
    parent = next(c for c in context.candidates if c.path == "main_ee.md"
                  and c.section_title.startswith("Step 9"))
    assert support[0].image_ids == parent.image_ids[:8]
    assert not set(support[0].image_ids) & set(parent.image_ids[8:])


def test_normal_fruit_and_free_spider_perk_do_not_require_full_masamune(kb):
    index = DependencyIndex.load(kb)
    context = PlanningContext(map_catalog(kb, "zetsubou_no_shima"), (), [])
    fruit = next(c for c in context.candidates if c.section_title == "fruit plant")
    plan = index.resolve((fruit.id,), context)
    paths = {c.path for c in context.candidates if c.id in {s.source_id for s in plan.steps}}
    assert "buckets_water.md" in paths
    assert not {"kt4.md", "masamune.md", "side_ee/golden_bucket.md"} & paths
    _, selected, _ = resolve(kb, "zetsubou_no_shima", "side_ee/free_widows_wine.md")
    assert {c.section_title for c in selected if c.path == "masamune.md"} == {
        "part 1 - spider tooth",
    }


@pytest.mark.parametrize("mid,path,question,scope", [
    ("gorod_krovi", "shield.md", "Como faço a Tiamat's Maw?", "upgrade"),
    ("shadows_of_evil", "shield.md", "How do I get Goddard Apparatus?", "upgrade"),
    ("revelations", "side_ee/masks.md", "Como faço a máscara do Keeper?", "keeper"),
])
def test_named_equipment_selects_reviewed_state_without_file_ambiguity(
    kb, mid, path, question, scope,
):
    index = DependencyIndex.load(kb)
    candidates = map_catalog(kb, mid)
    seed = next(i for i, c in enumerate(candidates) if c.path == path)
    task = json.dumps({"question": question, "seed_sources": [str(seed)]})
    context = PlanningContext(candidates, (), [{}, {"content": "TASK\n" + task + "\n\n"}])
    assert index.roots(context) == tuple(index.root_sets[f"{mid}:{path}:{scope}"])


def test_redirect_objective_is_satisfied_by_canonical_upgrade_not_stub(kb):
    plan, _, context = resolve(kb, "gorod_krovi", "side_ee/shield_upgrade.md")
    context = replace(context, objective_paths=("side_ee/shield_upgrade.md",))
    assert not plan_violations(plan, context)
    assert not any(":side_ee/shield_upgrade.md:" in s.source_id for s in plan.steps)


def test_conditional_requirements_propagate_alternatives_and_unconditional_override():
    chunks = tuple(KnowledgeChunk(i, "map", "Map", i+".md", "equipment", "", i,
                                  "Requires the shared equipment.", (), 0) for i in "abcde")
    data = dict(version=1, source_digests={c.id: source_digest(c) for c in chunks},
                reviewed_documents=[], requirements=[
        dict(consumer=a, sources=[b], evidence="Requires the shared equipment.",
             condition=condition)
        for a, b, condition in [("a", "c", "Only route A"), ("b", "c", "Only route B"),
                                ("c", "d", ""), ("d", "e", "")]
    ])
    index = DependencyIndex(data)
    context = PlanningContext(chunks, (), [])
    plan = index.resolve(("a", "b"), context)
    for step in plan.steps:
        if step.source_id in "cde":
            assert "Only route A" in step.condition and "Only route B" in step.condition
            assert " OR " in step.condition
    plan = index.resolve(("a", "b", "c"), context)
    assert all(not s.condition for s in plan.steps if s.source_id in "cde")


def test_summary_of_transitive_setup_keeps_an_external_anchor():
    chunks = tuple(KnowledgeChunk(i, "map", "Map", "setup.md" if i != "c" else "goal.md",
                                  "equipment", "", i, "Requires the preceding setup.", (), n)
                   for n, i in enumerate("abc"))
    index = DependencyIndex(dict(
        version=1, reviewed_documents=[],
        source_digests={c.id: source_digest(c) for c in chunks}, requirements=[
            dict(consumer=consumer, sources=[target], evidence="Requires the preceding setup.")
            for consumer, target in [("c", "b"), ("b", "a")]
        ],
    ))
    context = PlanningContext(chunks, (), [])
    plan = compact_summary(index.resolve(("c",), context), context)
    assert len(plan.steps) == 2
    assert plan.steps[0].grouped_source_ids == ["b"]
    assert plan.steps[0].anchor_id == plan.steps[0].before_source_id == "c"
    assert not plan_violations(plan, context)


def test_reviewed_view_rejects_changed_parent_and_foreign_images(kb):
    data = json.loads((BASE / "assets/guide-dependencies.json").read_text("utf-8"))
    for defect in ("parent_digest", "image_ids"):
        modified = json.loads(json.dumps(data))
        modified["source_views"][0][defect] = (
            "outdated" if defect == "parent_digest" else ["foreign"]
        )
        original = kb._guide_dependencies
        try:
            kb._guide_dependencies = DependencyIndex(modified)
            with pytest.raises(DependencyError, match="desatualizado|imagens"):
                map_catalog(kb, "origins")
        finally:
            kb._guide_dependencies = original


@pytest.mark.asyncio
@pytest.mark.parametrize("mid", [
    "origins", "zetsubou_no_shima", "gorod_krovi", "der_eisendrache",
    "revelations", "shadows_of_evil", "ascension", "shangri_la", "moon", "the_giant",
])
async def test_main_quests_prepare_locally_without_model_planning(kb, mid):
    class NoPlanner(PlannedLLM):
        async def plan_sources(self, context):
            raise AssertionError("Reviewed main quest must not call model planning")

    llm = NoPlanner()
    response = await answer_chat(
        ChatRequest(message="Como faço o Easter Egg principal completo, sem resumir?",
                    active_map_id=mid),
        kb, SearchEngine(kb), llm, lambda i, v: f"/{i}/{v}",
    )
    assert not response.need_clarification
    assert response.blocks and llm.calls
    assert all(s.map_id == mid for s in response.sources)
