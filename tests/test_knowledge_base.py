import json
from pathlib import Path

from PIL import Image

from app.knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent


def test_current_knowledge_base_is_consistent() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps", verify_images=True)

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


def _write_index(map_dir: Path, files: list[dict[str, str]]) -> None:
    (map_dir / "index.json").write_text(
        json.dumps(
            {
                "map_id": "test_map",
                "display_name": "Test Map",
                "aliases": ["test"],
                "summary": "Fixture",
                "files": files,
            }
        ),
        encoding="utf-8",
    )


def test_unsafe_document_path_is_rejected(tmp_path: Path) -> None:
    maps_dir = tmp_path / "maps"
    map_dir = maps_dir / "test_map"
    map_dir.mkdir(parents=True)
    (maps_dir / "outside.md").write_text("# Outside", encoding="utf-8")
    _write_index(
        map_dir,
        [{"path": "../outside.md", "category": "test", "summary": "Unsafe"}],
    )

    knowledge_base = KnowledgeBase(maps_dir)

    assert "unsafe-document-path" in {issue.code for issue in knowledge_base.errors}


def test_corrupt_referenced_image_is_detected_and_validation_is_idempotent(
    tmp_path: Path,
) -> None:
    maps_dir = tmp_path / "maps"
    map_dir = maps_dir / "test_map"
    image_dir = map_dir / "images"
    image_dir.mkdir(parents=True)
    _write_index(
        map_dir,
        [{"path": "guide.md", "category": "test", "summary": "Guide"}],
    )
    (map_dir / "guide.md").write_text(
        "# Guide\n\n## step\n\nRelated image: images/broken.jpg\n",
        encoding="utf-8",
    )
    (image_dir / "broken.jpg").write_bytes(b"not an image")

    knowledge_base = KnowledgeBase(maps_dir, verify_images=True)
    knowledge_base.validate_image_files()

    matching = [issue for issue in knowledge_base.errors if issue.code == "invalid-image-file"]
    assert len(matching) == 1


def test_orphan_image_is_reported(tmp_path: Path) -> None:
    maps_dir = tmp_path / "maps"
    map_dir = maps_dir / "test_map"
    image_dir = map_dir / "images"
    image_dir.mkdir(parents=True)
    _write_index(
        map_dir,
        [{"path": "guide.md", "category": "test", "summary": "Guide"}],
    )
    (map_dir / "guide.md").write_text("# Guide\n\n## step\n\nText.", encoding="utf-8")
    Image.new("RGB", (8, 8)).save(image_dir / "orphan.png")

    knowledge_base = KnowledgeBase(maps_dir)

    assert "image-not-referenced" in {issue.code for issue in knowledge_base.warnings}


def test_image_ids_are_stable_between_loads() -> None:
    first = KnowledgeBase(ROOT / "maps")
    second = KnowledgeBase(ROOT / "maps")

    assert set(first.images) == set(second.images)
