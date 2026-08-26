import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from PIL import Image

from app.assets import AssetManifest, AssetManifestError
from scripts import migrate_images
from scripts.migrate_images import (
    FULL_MAX_SIZE,
    THUMBNAIL_SIZE,
    LocalObject,
    MigrationError,
    _build_variants,
    upload_objects,
    verify_objects,
)


def _variant(key: str, sha256: str = "a" * 64) -> dict[str, object]:
    return {
        "key": key,
        "sha256": sha256,
        "size_bytes": 100,
        "width": 20,
        "height": 10,
        "content_type": "image/webp",
    }


def _manifest_payload() -> dict[str, object]:
    return {
        "version": 1,
        "assets": {
            "img_1234567890abcdef": {
                "map_id": "test_map",
                "path": "images/example.png",
                "original_sha256": "a" * 64,
                "source_url": "https://example.com/source.png",
                "variants": {
                    "original": _variant("images/v1/hash/original.png"),
                    "full": _variant("images/v1/hash/full.webp"),
                    "thumb": _variant("images/v1/hash/thumb.webp"),
                },
            }
        },
    }


def test_asset_manifest_builds_encoded_immutable_url(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest_payload()), encoding="utf-8")

    manifest = AssetManifest.load(manifest_path, required=True)

    assert manifest.url(
        "https://assets.example.com/",
        "img_1234567890abcdef",
        "thumb",
    ) == "https://assets.example.com/images/v1/hash/thumb.webp"


def test_asset_manifest_rejects_unsafe_object_key(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["assets"]["img_1234567890abcdef"]["variants"]["thumb"]["key"] = "../x"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AssetManifestError, match="unsafe"):
        AssetManifest.load(manifest_path, required=True)


def test_variant_builder_preserves_original_and_bounds_webp_sizes(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (3200, 1800), color=(20, 40, 60)).save(source)

    variants = _build_variants(source, tmp_path / "generated")

    assert variants["original"]["size_bytes"] == source.stat().st_size
    assert variants["original"]["width"] == 3200
    assert variants["original"]["height"] == 1800
    assert variants["full"]["width"] <= FULL_MAX_SIZE[0]
    assert variants["full"]["height"] <= FULL_MAX_SIZE[1]
    assert variants["thumb"]["width"] <= THUMBNAIL_SIZE[0]
    assert variants["thumb"]["height"] <= THUMBNAIL_SIZE[1]
    assert (tmp_path / "generated" / "full.webp").is_file()
    assert (tmp_path / "generated" / "thumb.webp").is_file()


class FakeR2Client:
    def __init__(self, *, exists: bool) -> None:
        self.exists = exists
        self.uploads = 0

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        del Bucket, Key
        if not self.exists:
            raise ClientError(
                {
                    "Error": {"Code": "404", "Message": "Not Found"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                "HeadObject",
            )
        return {
            "ContentLength": 4,
            "Metadata": {
                "sha256": "a" * 64,
                "original-sha256": "b" * 64,
                "variant": "thumb",
            },
        }

    def upload_file(self, *_: object, **__: object) -> None:
        self.uploads += 1


def _local_object(tmp_path: Path) -> LocalObject:
    source = tmp_path / "thumb.webp"
    source.write_bytes(b"test")
    return LocalObject(
        key="images/v1/hash/thumb.webp",
        source_file=source,
        sha256="a" * 64,
        size_bytes=4,
        content_type="image/webp",
        variant="thumb",
        original_sha256="b" * 64,
    )


def test_upload_skips_object_that_already_matches_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeR2Client(exists=True)
    monkeypatch.setattr(migrate_images, "_r2_client", lambda: (client, "bucket"))

    stats = upload_objects([_local_object(tmp_path)], workers=1)

    assert stats.changed == 0
    assert stats.skipped == 1
    assert client.uploads == 0


def test_remote_verification_detects_missing_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeR2Client(exists=False)
    monkeypatch.setattr(migrate_images, "_r2_client", lambda: (client, "bucket"))

    with pytest.raises(MigrationError, match="does not match"):
        verify_objects([_local_object(tmp_path)], workers=1)
