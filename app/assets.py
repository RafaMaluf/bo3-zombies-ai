from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote


class AssetManifestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AssetVariant:
    key: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    content_type: str


@dataclass(frozen=True, slots=True)
class AssetRecord:
    id: str
    map_id: str
    path: str
    original_sha256: str
    source_url: str | None
    variants: dict[str, AssetVariant]


class AssetManifest:
    def __init__(self, records: dict[str, AssetRecord], version: int = 1) -> None:
        self.version = version
        self.records = records

    @classmethod
    def empty(cls) -> AssetManifest:
        return cls({})

    @classmethod
    def load(cls, path: Path, *, required: bool = False) -> AssetManifest:
        if not path.is_file():
            if required:
                raise AssetManifestError(f"Asset manifest not found: {path}")
            return cls.empty()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AssetManifestError(f"Could not load asset manifest {path}: {error}") from error
        if not isinstance(payload, dict):
            raise AssetManifestError("Asset manifest root must be an object.")
        version = payload.get("version")
        if version != 1:
            raise AssetManifestError(f"Unsupported asset manifest version: {version}.")
        raw_assets = payload.get("assets")
        if not isinstance(raw_assets, dict):
            raise AssetManifestError("Asset manifest assets must be an object.")

        records: dict[str, AssetRecord] = {}
        for asset_id, raw_record in raw_assets.items():
            if not isinstance(asset_id, str) or not isinstance(raw_record, dict):
                raise AssetManifestError("Every asset entry must be an object keyed by image ID.")
            records[asset_id] = cls._parse_record(asset_id, raw_record)
        return cls(records, version=version)

    @staticmethod
    def _parse_record(asset_id: str, raw_record: dict[str, Any]) -> AssetRecord:
        map_id = _required_string(raw_record, "map_id", asset_id)
        path = _required_string(raw_record, "path", asset_id)
        original_sha256 = _sha256(raw_record.get("original_sha256"), asset_id)
        raw_source_url = raw_record.get("source_url")
        source_url = str(raw_source_url).strip() if raw_source_url else None
        raw_variants = raw_record.get("variants")
        if not isinstance(raw_variants, dict):
            raise AssetManifestError(f"{asset_id}.variants must be an object.")

        variants: dict[str, AssetVariant] = {}
        for name in ("original", "full", "thumb"):
            raw_variant = raw_variants.get(name)
            if not isinstance(raw_variant, dict):
                raise AssetManifestError(f"{asset_id}.variants.{name} is required.")
            key = _required_string(raw_variant, "key", f"{asset_id}.variants.{name}")
            _safe_object_key(key, f"{asset_id}.variants.{name}")
            variants[name] = AssetVariant(
                key=key,
                sha256=_sha256(raw_variant.get("sha256"), f"{asset_id}.variants.{name}"),
                size_bytes=_positive_int(
                    raw_variant.get("size_bytes"),
                    f"{asset_id}.variants.{name}.size_bytes",
                ),
                width=_positive_int(
                    raw_variant.get("width"),
                    f"{asset_id}.variants.{name}.width",
                ),
                height=_positive_int(
                    raw_variant.get("height"),
                    f"{asset_id}.variants.{name}.height",
                ),
                content_type=_required_string(
                    raw_variant,
                    "content_type",
                    f"{asset_id}.variants.{name}",
                ),
            )
        return AssetRecord(
            id=asset_id,
            map_id=map_id,
            path=path,
            original_sha256=original_sha256,
            source_url=source_url,
            variants=variants,
        )

    def get(self, image_id: str) -> AssetRecord | None:
        return self.records.get(image_id)

    def url(self, base_url: str, image_id: str, variant: str) -> str | None:
        record = self.get(image_id)
        if record is None:
            return None
        asset_variant = record.variants.get(variant)
        if asset_variant is None:
            return None
        encoded_key = "/".join(quote(part, safe="") for part in asset_variant.key.split("/"))
        return f"{base_url.rstrip('/')}/{encoded_key}"


def _required_string(payload: dict[str, Any], field: str, context: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AssetManifestError(f"{context}.{field} must be a non-empty string.")
    return value.strip()


def _sha256(value: Any, context: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise AssetManifestError(f"{context} must contain a SHA-256 digest.")
    return text


def _positive_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AssetManifestError(f"{context} must be a positive integer.")
    return value


def _safe_object_key(key: str, context: str) -> None:
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or "\\" in key:
        raise AssetManifestError(f"{context}.key is unsafe: {key}")
