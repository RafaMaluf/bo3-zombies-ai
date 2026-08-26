from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from botocore.exceptions import ClientError
from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError

from app.assets import AssetManifest
from app.config import BASE_DIR
from app.knowledge_base import KnowledgeBase

FULL_MAX_SIZE = (2560, 2560)
THUMBNAIL_SIZE = (960, 640)
FULL_QUALITY = 88
THUMBNAIL_QUALITY = 80
CACHE_CONTROL = "public, max-age=31536000, immutable"
MANIFEST_CACHE_CONTROL = "no-cache, max-age=0, must-revalidate"


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LocalObject:
    key: str
    source_file: Path
    sha256: str
    size_bytes: int
    content_type: str
    variant: str
    original_sha256: str


@dataclass(frozen=True, slots=True)
class OperationStats:
    total: int
    changed: int
    skipped: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source_urls(maps_dir: Path) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    for map_dir in sorted(path for path in maps_dir.iterdir() if path.is_dir()):
        source_manifest = map_dir / "sources.json"
        if not source_manifest.is_file():
            continue
        try:
            payload = json.loads(source_manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MigrationError(f"Could not parse {source_manifest}: {error}") from error
        for image in payload.get("images", []):
            if not isinstance(image, dict):
                continue
            path = str(image.get("path", "")).strip().replace("\\", "/")
            url = str(image.get("source_url", "")).strip()
            if path and url:
                lookup[(map_dir.name, path)] = url
    return lookup


def _content_type(path: Path, image_format: str | None = None) -> str:
    if image_format:
        detected = Image.MIME.get(image_format.upper())
        if detected:
            return detected
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _original_extension(path: Path, content_type: str) -> str:
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    if content_type == "image/gif":
        return ".gif"
    suffix = path.suffix.lower()
    return suffix if suffix else ".bin"


def _save_webp(image: Image.Image, destination: Path, *, quality: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.webp")
    try:
        image.save(
            temporary,
            format="WEBP",
            quality=quality,
            method=4,
            optimize=True,
        )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _webp_dimensions(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            if image.format != "WEBP" or image.width <= 0 or image.height <= 0:
                raise MigrationError(f"Invalid staged WebP: {path}")
            return image.width, image.height
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise MigrationError(f"Could not validate staged image {path}: {error}") from error


def _build_variants(
    source: Path,
    destination_dir: Path,
    original_sha256: str | None = None,
) -> dict[str, dict[str, Any]]:
    try:
        with Image.open(source) as opened:
            image_format = opened.format
            if getattr(opened, "is_animated", False):
                opened.seek(0)
            normalized = ImageOps.exif_transpose(opened).convert("RGB")
            original_width, original_height = normalized.size

            full_path = destination_dir / "full.webp"
            thumb_path = destination_dir / "thumb.webp"
            if not full_path.is_file():
                full = normalized.copy()
                full.thumbnail(FULL_MAX_SIZE, Image.Resampling.LANCZOS)
                _save_webp(full, full_path, quality=FULL_QUALITY)
            if not thumb_path.is_file():
                thumb = normalized.copy()
                thumb.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                _save_webp(thumb, thumb_path, quality=THUMBNAIL_QUALITY)
    except (OSError, ValueError, UnidentifiedImageError) as error:
        raise MigrationError(f"Could not process image {source}: {error}") from error

    full_width, full_height = _webp_dimensions(full_path)
    thumb_width, thumb_height = _webp_dimensions(thumb_path)
    original_content_type = _content_type(source, image_format)
    original_sha256 = original_sha256 or sha256_file(source)
    base_key = f"images/v1/{original_sha256}"
    original_extension = _original_extension(source, original_content_type)
    return {
        "original": {
            "key": f"{base_key}/original{original_extension}",
            "sha256": original_sha256,
            "size_bytes": source.stat().st_size,
            "width": original_width,
            "height": original_height,
            "content_type": original_content_type,
        },
        "full": {
            "key": f"{base_key}/full.webp",
            "sha256": sha256_file(full_path),
            "size_bytes": full_path.stat().st_size,
            "width": full_width,
            "height": full_height,
            "content_type": "image/webp",
        },
        "thumb": {
            "key": f"{base_key}/thumb.webp",
            "sha256": sha256_file(thumb_path),
            "size_bytes": thumb_path.stat().st_size,
            "width": thumb_width,
            "height": thumb_height,
            "content_type": "image/webp",
        },
    }


def build_manifest(
    maps_dir: Path,
    manifest_path: Path,
    staging_dir: Path,
) -> dict[str, Any]:
    knowledge_base = KnowledgeBase(maps_dir)
    if knowledge_base.errors:
        messages = "; ".join(f"{issue.path}: {issue.message}" for issue in knowledge_base.errors)
        raise MigrationError(f"Knowledge base contains invalid images: {messages}")

    source_urls = _source_urls(maps_dir)
    variants_by_sha256: dict[str, dict[str, Any]] = {}
    assets: dict[str, dict[str, Any]] = {}
    total = len(knowledge_base.images)
    for position, asset in enumerate(sorted(knowledge_base.images.values(), key=lambda x: x.id), 1):
        if asset.source_file is None:
            raise MigrationError(f"Local source is unavailable for {asset.id}.")
        original_sha256 = sha256_file(asset.source_file)
        variants = variants_by_sha256.get(original_sha256)
        if variants is None:
            variants = _build_variants(
                asset.source_file,
                staging_dir / original_sha256,
                original_sha256,
            )
            variants_by_sha256[original_sha256] = variants
        assets[asset.id] = {
            "map_id": asset.map_id,
            "path": asset.path,
            "document_path": asset.document_path,
            "caption": asset.caption,
            "section": asset.section,
            "source_url": source_urls.get((asset.map_id, asset.path)),
            "original_sha256": original_sha256,
            "variants": variants,
        }
        if position % 50 == 0 or position == total:
            print(f"Built {position}/{total} image records.", flush=True)

    payload = {
        "version": 1,
        "generator": {
            "full_max_size": list(FULL_MAX_SIZE),
            "full_quality": FULL_QUALITY,
            "thumbnail_max_size": list(THUMBNAIL_SIZE),
            "thumbnail_quality": THUMBNAIL_QUALITY,
            "object_prefix": "images/v1",
        },
        "counts": {
            "assets": len(assets),
            "unique_originals": len(variants_by_sha256),
            "objects": len(variants_by_sha256) * 3,
        },
        "assets": assets,
    }
    serialized = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if not manifest_path.is_file() or manifest_path.read_text(encoding="utf-8") != serialized:
        manifest_path.write_text(serialized, encoding="utf-8", newline="\n")
    print(
        f"Manifest: {len(assets)} assets, {len(variants_by_sha256)} unique originals, "
        f"{len(variants_by_sha256) * 3} objects.",
        flush=True,
    )
    return payload


def _local_objects(
    payload: dict[str, Any],
    maps_dir: Path,
    staging_dir: Path,
) -> list[LocalObject]:
    objects: dict[str, LocalObject] = {}
    for raw_record in payload["assets"].values():
        map_id = str(raw_record["map_id"])
        relative_path = str(raw_record["path"])
        original_sha256 = str(raw_record["original_sha256"])
        for variant_name, raw_variant in raw_record["variants"].items():
            if variant_name == "original":
                source_file = maps_dir / map_id / relative_path
            else:
                source_file = staging_dir / original_sha256 / f"{variant_name}.webp"
            item = LocalObject(
                key=str(raw_variant["key"]),
                source_file=source_file,
                sha256=str(raw_variant["sha256"]),
                size_bytes=int(raw_variant["size_bytes"]),
                content_type=str(raw_variant["content_type"]),
                variant=str(variant_name),
                original_sha256=original_sha256,
            )
            previous = objects.setdefault(item.key, item)
            if previous.sha256 != item.sha256 or previous.size_bytes != item.size_bytes:
                raise MigrationError(f"Object key collision: {item.key}")
    return sorted(objects.values(), key=lambda item: item.key)


def _r2_client() -> tuple[Any, str]:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:
        raise MigrationError("Install development dependencies before using R2.") from error

    required = {
        "R2_ENDPOINT": os.getenv("R2_ENDPOINT", "").strip().rstrip("/"),
        "R2_BUCKET_NAME": os.getenv("R2_BUCKET_NAME", "").strip(),
        "R2_ACCESS_KEY_ID": os.getenv("R2_ACCESS_KEY_ID", "").strip(),
        "R2_SECRET_ACCESS_KEY": os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise MigrationError("Missing R2 configuration: " + ", ".join(missing))
    endpoint = required["R2_ENDPOINT"]
    bucket = required["R2_BUCKET_NAME"]
    if endpoint.endswith(f"/{bucket}"):
        raise MigrationError("R2_ENDPOINT must not include the bucket name.")
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=required["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=required["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
    )
    return client, bucket


def _head_matches(client: Any, bucket: str, item: LocalObject) -> bool:
    try:
        response = client.head_object(Bucket=bucket, Key=item.key)
    except ClientError as error:
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 404:
            return False
        raise
    metadata = {str(key).lower(): str(value) for key, value in response.get("Metadata", {}).items()}
    return (
        int(response.get("ContentLength", -1)) == item.size_bytes
        and metadata.get("sha256") == item.sha256
        and metadata.get("original-sha256") == item.original_sha256
        and metadata.get("variant") == item.variant
    )


def upload_objects(objects: Iterable[LocalObject], *, workers: int) -> OperationStats:
    client, bucket = _r2_client()
    items = list(objects)
    changed = 0
    skipped = 0
    lock = Lock()

    def upload(item: LocalObject) -> str:
        if not item.source_file.is_file():
            raise MigrationError(f"Staged object is missing: {item.source_file}")
        if item.source_file.stat().st_size != item.size_bytes:
            raise MigrationError(f"Staged object size changed: {item.source_file}")
        if _head_matches(client, bucket, item):
            return "skipped"
        client.upload_file(
            str(item.source_file),
            bucket,
            item.key,
            ExtraArgs={
                "ContentType": item.content_type,
                "CacheControl": CACHE_CONTROL,
                "Metadata": {
                    "sha256": item.sha256,
                    "original-sha256": item.original_sha256,
                    "variant": item.variant,
                },
            },
        )
        return "changed"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(upload, item): item for item in items}
        for position, future in enumerate(as_completed(futures), 1):
            result = future.result()
            with lock:
                if result == "changed":
                    changed += 1
                else:
                    skipped += 1
            if position % 50 == 0 or position == len(items):
                print(
                    f"Uploaded/checked {position}/{len(items)} objects "
                    f"({changed} changed, {skipped} unchanged).",
                    flush=True,
                )
    return OperationStats(total=len(items), changed=changed, skipped=skipped)


def verify_objects(objects: Iterable[LocalObject], *, workers: int) -> OperationStats:
    client, bucket = _r2_client()
    items = list(objects)

    def verify(item: LocalObject) -> None:
        if not _head_matches(client, bucket, item):
            raise MigrationError(f"Remote object does not match the manifest: {item.key}")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(verify, item): item for item in items}
        for position, future in enumerate(as_completed(futures), 1):
            future.result()
            if position % 100 == 0 or position == len(items):
                print(f"Verified {position}/{len(items)} remote objects.", flush=True)
    return OperationStats(total=len(items), changed=0, skipped=len(items))


def upload_manifest(manifest_path: Path) -> None:
    client, bucket = _r2_client()
    client.upload_file(
        str(manifest_path),
        bucket,
        "manifests/image-manifest.json",
        ExtraArgs={
            "ContentType": "application/json",
            "CacheControl": MANIFEST_CACHE_CONTROL,
            "Metadata": {"sha256": sha256_file(manifest_path)},
        },
    )


def _load_payload(manifest_path: Path) -> dict[str, Any]:
    AssetManifest.load(manifest_path, required=True)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and migrate Kronochat image assets to R2.")
    parser.add_argument("command", choices=("build", "upload", "verify", "all"))
    parser.add_argument("--maps-dir", type=Path, default=BASE_DIR / "maps")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=BASE_DIR / "assets" / "image-manifest.json",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=BASE_DIR / ".cache" / "r2-assets",
    )
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(BASE_DIR / ".env")
    if args.command in {"build", "all"}:
        payload = build_manifest(args.maps_dir, args.manifest, args.staging_dir)
    else:
        payload = _load_payload(args.manifest)
    objects = _local_objects(payload, args.maps_dir, args.staging_dir)
    if args.command in {"upload", "all"}:
        stats = upload_objects(objects, workers=args.workers)
        upload_manifest(args.manifest)
        print(f"Upload complete: {stats.changed} changed, {stats.skipped} unchanged.")
    if args.command in {"verify", "all"}:
        stats = verify_objects(objects, workers=args.workers)
        print(f"Verification complete: {stats.total} objects match the manifest.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MigrationError as error:
        raise SystemExit(f"Image migration failed: {error}") from error
