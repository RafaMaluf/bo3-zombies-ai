import json
import re
from pathlib import Path, PurePosixPath

from PIL import Image

from app.assets import AssetManifest
from app.knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent


def test_current_knowledge_base_is_consistent() -> None:
    manifest = AssetManifest.load(ROOT / "assets" / "image-manifest.json", required=True)
    knowledge_base = KnowledgeBase(
        ROOT / "maps",
        verify_images=True,
        asset_manifest=manifest,
    )

    assert not knowledge_base.errors
    assert not knowledge_base.warnings
    assert knowledge_base.stats["maps"] == 14
    assert knowledge_base.stats["documents"] == 166
    assert knowledge_base.stats["chunks"] > 590
    assert knowledge_base.stats["images"] == 1084


def test_every_registered_image_stays_inside_its_map() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")

    for asset in knowledge_base.images.values():
        map_root = knowledge_base.maps[asset.map_id].directory
        if asset.source_file is not None:
            asset.source_file.resolve().relative_to(map_root)
            continue
        relative_path = PurePosixPath(asset.path)
        assert not relative_path.is_absolute()
        assert ".." not in relative_path.parts
        assert knowledge_base.asset_manifest.get(asset.id) is not None


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


def test_content_addressed_chronicles_images_use_section_captions() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    assets = [
        asset
        for asset in knowledge_base.images.values()
        if asset.map_id == "shangri_la" and asset.document_path == "main_ee.md"
    ]

    assert assets
    assert all(
        not re.search(r"\b[a-f0-9]{20,}\b", asset.caption, re.IGNORECASE) for asset in assets
    )
    assert any("Main easter egg quest" in asset.caption for asset in assets)


def test_shangri_la_player_count_section_distinguishes_vanilla_and_solo_mod() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    chunk = next(
        chunk
        for chunk in knowledge_base.chunks.values()
        if chunk.map_id == "shangri_la"
        and chunk.path == "main_ee.md"
        and chunk.section_title == "Player-count requirement"
    )

    assert "4 players" in chunk.content
    assert "1 player" in chunk.content
    assert "2 or 3 players" in chunk.content
    assert "Solo Easter Egg mod" in chunk.content


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


def test_manifest_keeps_referenced_image_valid_without_local_binary(tmp_path: Path) -> None:
    maps_dir = tmp_path / "maps"
    map_dir = maps_dir / "test_map"
    image_dir = map_dir / "images"
    image_dir.mkdir(parents=True)
    _write_index(
        map_dir,
        [{"path": "guide.md", "category": "test", "summary": "Guide"}],
    )
    (map_dir / "guide.md").write_text(
        "# Guide\n\n## step\n\nRelated image: images/example.png\n",
        encoding="utf-8",
    )
    source = image_dir / "example.png"
    Image.new("RGB", (8, 8)).save(source)
    local = KnowledgeBase(maps_dir)
    image_id = next(iter(local.images))
    variant = {
        "key": "images/v1/hash/image.webp",
        "sha256": "a" * 64,
        "size_bytes": 100,
        "width": 8,
        "height": 8,
        "content_type": "image/webp",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "assets": {
                    image_id: {
                        "map_id": "test_map",
                        "path": "images/example.png",
                        "original_sha256": "a" * 64,
                        "source_url": None,
                        "variants": {
                            "original": variant,
                            "full": variant,
                            "thumb": variant,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    source.unlink()

    remote = KnowledgeBase(
        maps_dir,
        verify_images=True,
        asset_manifest=AssetManifest.load(manifest_path, required=True),
    )

    assert not remote.errors
    assert remote.images[image_id].source_file is None
