"""Regression checks for externally reviewed procedures and their image bindings."""
from pathlib import Path

import pytest

from app.guidance import guide_chunks
from app.guide_dependencies import DependencyIndex, map_catalog
from app.knowledge_base import KnowledgeBase
from app.source_planning import PlanningContext, plan_violations

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase(ROOT / "maps")


def resolve(kb, mid, path):
    index = DependencyIndex.load(kb)
    context = PlanningContext(map_catalog(kb, mid), (), [], dependency_index=index)
    plan = index.resolve(index.root_sets[f"{mid}:{path}"], context)
    assert not plan_violations(plan, context)
    catalog = {c.id: c for c in context.candidates}
    return [catalog[s.source_id] for s in plan.steps]


def test_shangri_recovered_procedures_and_photos_are_in_execution_order(kb):
    selected = resolve(kb, "shangri_la", "main_ee.md")
    quest = [c for c in selected if c.path == "main_ee.md"]
    assert [len(c.image_ids) for c in quest] == [0, 6, 1, 5, 6, 3, 14, 4, 10, 5]
    assert [c.section_title.split(" - ")[0] for c in quest[2:6]] == [
        "Step 3", "Step 4", "Step 5", "Step 6",
    ]
    assert "FOUR leaks" in quest[4].content
    assert "Trip Mines" in quest[5].content
    assert len({i for c in quest for i in c.image_ids}) == 54
    # Valve, mines, dials and gongs must no longer be attached to the finale.
    final_paths = {kb.images[i].path for i in quest[-1].image_ids}
    assert all(any(marker in path for marker in (
        "300efeb", "35d5fdb", "ec47256", "183cb84", "614789b",
    )) for path in final_paths)


@pytest.mark.parametrize("mid", ["ascension", "moon", "shangri_la"])
def test_image_cheatsheets_are_not_executable_quest_phases(kb, mid):
    chunks = guide_chunks(kb, mid, "main_ee.md")
    assert chunks
    assert not any("cheatsheet" in c.section_title.casefold() for c in chunks)


@pytest.mark.parametrize("path", [
    "shield.md", "lightning_bow.md", "wolf_bow.md", "side_ee/plunger.md",
    "side_ee/brm_wallbuy.md", "side_ee/death_machine.md",
])
def test_de_wallrun_recipes_include_the_four_plate_setup_first(kb, path):
    selected = resolve(kb, "der_eisendrache", path)
    anti = next(c for c in selected if c.section_title == "anti-gravity activation")
    assert "four small square floor plates" in anti.content
    consumer = next(c for c in selected if c.path == path and (
        "during anti-gravity" in c.content or "wait for anti-gravity" in c.content
        or "**anti-gravity** to activate" in c.content
        or "anti-gravity wall-run" in c.content
        or "anti-gravity sequence" in c.content
        or "Activate the pyramid room anti-gravity first" in c.content
    ) and c.section_title != "overview") if path not in {
        "side_ee/brm_wallbuy.md", "side_ee/death_machine.md",
    } else next(c for c in selected if c.path == path)
    assert selected.index(anti) < selected.index(consumer)


def test_golden_bucket_expands_only_the_four_ordinary_plant_recipes(kb):
    selected = resolve(kb, "zetsubou_no_shima", "side_ee/golden_bucket.md")
    assert {c.section_title for c in selected if c.path == "plants.md"} == {
        "blue water plant", "green water plant", "purple water plant", "fruit plant",
    }
    assert not {"kt4.md", "masamune.md"} & {c.path for c in selected}


def test_masamune_keeps_required_wall_images_and_excludes_friendly_thrasher(kb):
    selected = resolve(kb, "zetsubou_no_shima", "masamune.md")
    plant = next(c for c in selected if c.section_title == "part 2 - rainbow water plant")
    paths = {kb.images[i].path for i in plant.image_ids}
    assert {"images/masamune/5placestomesmerize1.jpg",
            "images/masamune/6placestomesmerize2.jpg",
            "images/masamune/8placestomesmerize4.jpg"} <= paths
    assert "images/masamune/7placestomesmerize3.jpg" not in paths
    assert not any(c.path == "side_ee/friendly_thrasher.md" for c in selected)
    friendly = resolve(kb, "zetsubou_no_shima", "side_ee/friendly_thrasher.md")
    assert any(kb.images[i].path.endswith("7placestomesmerize3.jpg")
               for c in friendly for i in c.image_ids)


def test_trials_have_six_medium_assignments_including_the_distinct_enrage_trial(kb):
    chunks = map_catalog(kb, "zetsubou_no_shima")
    medium = next(c for c in chunks if c.path == "trials.md"
                  and c.section_title == "medium trials")
    assert medium.content.count("### ") == 6
    assert "before it enrages" in medium.content
    hard = next(c for c in chunks if c.path == "trials.md" and c.section_title == "hard trials")
    assert hard.content.count("### ") == 5
    assert "while they are mutating" in hard.content
