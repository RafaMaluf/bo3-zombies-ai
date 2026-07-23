from pathlib import Path

from app.knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent


def test_current_knowledge_base_is_consistent() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")

    assert not knowledge_base.errors
    assert not knowledge_base.warnings
    assert knowledge_base.stats["maps"] == 6
    assert knowledge_base.stats["documents"] == 99
    assert knowledge_base.stats["chunks"] > 250
    assert knowledge_base.stats["images"] == 626


def test_every_registered_image_stays_inside_its_map() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")

    for asset in knowledge_base.images.values():
        map_root = knowledge_base.maps[asset.map_id].directory
        asset.source_file.resolve().relative_to(map_root)


def test_multiple_images_in_one_step_have_distinct_captions() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    chunk = next(
        chunk
        for chunk in knowledge_base.chunks.values()
        if chunk.map_id == "der_eisendrache"
        and chunk.path == "shield.md"
        and chunk.section_title == "part 3 - underground frame"
    )

    captions = [knowledge_base.images[image_id].caption for image_id in chunk.image_ids]
    assert len(captions) == 3
    assert len(set(captions)) == 3
