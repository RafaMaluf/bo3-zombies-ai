from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from app.chunking import (
    extract_image_paths,
    normalize_image_path,
    slugify,
    split_markdown_by_sections,
)
from app.domain import (
    ImageAsset,
    KnowledgeChunk,
    MapRecord,
    ValidationIssue,
)
from app.schemas import MapSummary

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _image_id(map_id: str, path: str) -> str:
    digest = hashlib.blake2s(
        f"{map_id}:{path}".encode(),
        digest_size=8,
    ).hexdigest()
    return f"img_{digest}"


def _humanize_filename(
    path: str,
    section_title: str,
    image_position: int = 1,
    image_count: int = 1,
) -> str:
    stem = Path(path).stem
    stem = re.sub(r"^\d+[\s_-]*", "", stem)
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()

    # Old screenshots often have names such as "14fusesinserted". In those
    # cases the section heading is much more useful than pretending the
    # filename is a proper caption.
    filename_is_useful = len(stem.split()) >= 2 and len(stem) >= 6
    if not filename_is_useful:
        caption = section_title.strip() or "Gameplay reference"
        if image_count > 1:
            caption = f"{caption} ({image_position}/{image_count})"
        return caption

    caption = stem[0].upper() + stem[1:]
    if section_title and caption.lower() not in section_title.lower():
        return f"{section_title} — {caption}"
    return caption


class KnowledgeBase:
    def __init__(self, maps_dir: Path, *, verify_images: bool = False) -> None:
        self.maps_dir = maps_dir.resolve()
        self.maps: dict[str, MapRecord] = {}
        self.chunks: dict[str, KnowledgeChunk] = {}
        self.images: dict[str, ImageAsset] = {}
        self.issues: list[ValidationIssue] = []
        self._document_count = 0
        self._verified_image_ids: set[str] = set()
        self._load()
        if verify_images:
            self.validate_image_files()

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def stats(self) -> dict[str, int]:
        return {
            "maps": len(self.maps),
            "documents": self._document_count,
            "chunks": len(self.chunks),
            "images": len(self.images),
            "validation_errors": len(self.errors),
            "validation_warnings": len(self.warnings),
        }

    def map_summaries(self) -> list[MapSummary]:
        summaries: list[MapSummary] = []
        for record in sorted(self.maps.values(), key=lambda item: item.display_name):
            cover_candidates = [
                self.images[image_id]
                for image_id in sorted(record.image_ids)
                if image_id in self.images
            ]
            cover = next(
                (asset for asset in cover_candidates if "/general/" in f"/{asset.path.lower()}"),
                cover_candidates[0] if cover_candidates else None,
            )
            summaries.append(
                MapSummary(
                    map_id=record.map_id,
                    display_name=record.display_name,
                    summary=record.summary,
                    aliases=list(record.aliases),
                    document_count=len(record.document_paths),
                    chunk_count=len(record.chunk_ids),
                    image_count=len(record.image_ids),
                    cover_image_id=cover.id if cover else None,
                )
            )
        return summaries

    def get_image(self, image_id: str) -> ImageAsset | None:
        return self.images.get(image_id)

    def validate_image_files(self) -> None:
        """Decode every registered image once and record corrupt assets."""
        for asset in self.images.values():
            if asset.id in self._verified_image_ids:
                continue
            self._verified_image_ids.add(asset.id)
            try:
                with Image.open(asset.source_file) as image:
                    if image.width <= 0 or image.height <= 0:
                        raise ValueError("Image has invalid dimensions.")
                    image.verify()
            except (OSError, ValueError, UnidentifiedImageError) as error:
                self._issue(
                    "error",
                    "invalid-image-file",
                    f"Image cannot be decoded: {error}",
                    asset.source_file,
                )

    def _issue(
        self,
        severity: str,
        code: str,
        message: str,
        path: Path | str = "",
    ) -> None:
        display_path = str(path)
        try:
            display_path = str(Path(path).resolve().relative_to(self.maps_dir.parent))
        except (TypeError, ValueError, OSError):
            pass
        self.issues.append(
            ValidationIssue(
                severity=severity,
                code=code,
                message=message,
                path=display_path,
            )
        )

    def _load(self) -> None:
        if not self.maps_dir.exists():
            self._issue("error", "maps-directory-missing", "Maps directory not found.")
            return

        for map_dir in sorted(self.maps_dir.iterdir()):
            if map_dir.is_dir():
                self._load_map(map_dir)

    def _load_map(self, map_dir: Path) -> None:
        index_path = map_dir / "index.json"
        if not index_path.exists():
            self._issue(
                "warning",
                "map-without-index",
                "Directory is ignored because index.json is missing.",
                map_dir,
            )
            return

        try:
            index_data: dict[str, Any] = json.loads(index_path.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._issue(
                "error",
                "invalid-index",
                f"Could not parse index.json: {error}",
                index_path,
            )
            return

        map_id = str(index_data.get("map_id", "")).strip()
        display_name = str(index_data.get("display_name", "")).strip()
        if not map_id or not display_name:
            self._issue(
                "error",
                "invalid-map-metadata",
                "index.json requires map_id and display_name.",
                index_path,
            )
            return
        if map_id in self.maps:
            self._issue(
                "error",
                "duplicate-map-id",
                f"Duplicate map_id: {map_id}",
                index_path,
            )
            return

        aliases = self._build_aliases(map_id, display_name, index_data.get("aliases", []))
        file_entries = index_data.get("files", [])
        if not isinstance(file_entries, list):
            self._issue(
                "error",
                "invalid-file-index",
                "The files field must be a list.",
                index_path,
            )
            return

        indexed_paths: list[str] = []
        record = MapRecord(
            map_id=map_id,
            display_name=display_name,
            summary=str(index_data.get("summary", "")).strip(),
            aliases=aliases,
            directory=map_dir.resolve(),
            document_paths=(),
        )
        self.maps[map_id] = record

        for file_entry in file_entries:
            if not isinstance(file_entry, dict):
                self._issue(
                    "error",
                    "invalid-file-entry",
                    "Every file entry must be an object.",
                    index_path,
                )
                continue
            raw_path = str(file_entry.get("path", "")).strip()
            if not raw_path:
                self._issue(
                    "error",
                    "missing-file-path",
                    "A file entry is missing its path.",
                    index_path,
                )
                continue
            relative_path = normalize_image_path(raw_path)
            indexed_paths.append(relative_path)
            self._load_document(
                record=record,
                relative_path=relative_path,
                category=str(file_entry.get("category", "general")).strip() or "general",
                file_summary=str(file_entry.get("summary", "")).strip(),
            )

        record.document_paths = tuple(indexed_paths)
        self._validate_unindexed_documents(record)
        self._validate_orphan_images(record)

    @staticmethod
    def _build_aliases(
        map_id: str,
        display_name: str,
        raw_aliases: Any,
    ) -> tuple[str, ...]:
        candidates = [map_id, map_id.replace("_", " "), display_name]
        if isinstance(raw_aliases, list):
            candidates.extend(str(alias) for alias in raw_aliases)

        aliases: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            alias = re.sub(r"\s+", " ", candidate.strip().lower())
            if alias and alias not in seen:
                seen.add(alias)
                aliases.append(alias)
        return tuple(aliases)

    def _safe_child(self, base: Path, relative_path: str) -> Path | None:
        candidate = (base / relative_path).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError:
            return None
        return candidate

    def _load_document(
        self,
        record: MapRecord,
        relative_path: str,
        category: str,
        file_summary: str,
    ) -> None:
        file_path = self._safe_child(record.directory, relative_path)
        if file_path is None:
            self._issue(
                "error",
                "unsafe-document-path",
                f"Document path escapes its map directory: {relative_path}",
                record.directory,
            )
            return
        if not file_path.is_file():
            self._issue(
                "error",
                "indexed-document-missing",
                f"Indexed document does not exist: {relative_path}",
                file_path,
            )
            return

        try:
            content = file_path.read_text("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            self._issue(
                "error",
                "document-read-failed",
                f"Could not read document: {error}",
                file_path,
            )
            return

        self._document_count += 1
        sections = split_markdown_by_sections(content)
        if not sections:
            self._issue(
                "warning",
                "document-without-sections",
                "Document did not produce any searchable sections.",
                file_path,
            )
            return

        section_image_paths = {
            image_path for section in sections for image_path in section.image_paths
        }
        unassigned_image_ids: list[str] = []
        unassigned_paths = [
            image_path
            for image_path in extract_image_paths(content)
            if image_path not in section_image_paths
        ]
        for image_position, image_path in enumerate(unassigned_paths, start=1):
            asset = self._register_image(
                record=record,
                image_path=image_path,
                section_title=file_summary or Path(relative_path).stem,
                document_path=file_path,
                image_position=image_position,
                image_count=len(unassigned_paths),
            )
            if asset is not None:
                unassigned_image_ids.append(asset.id)

        for section_index, section in enumerate(sections):
            image_ids: list[str] = []
            for image_position, image_path in enumerate(
                section.image_paths,
                start=1,
            ):
                asset = self._register_image(
                    record=record,
                    image_path=image_path,
                    section_title=section.title,
                    document_path=file_path,
                    image_position=image_position,
                    image_count=len(section.image_paths),
                )
                if asset is not None:
                    image_ids.append(asset.id)
            if section_index == 0:
                image_ids.extend(
                    image_id for image_id in unassigned_image_ids if image_id not in image_ids
                )

            chunk_id = (
                f"{record.map_id}:{relative_path}:{slugify(section.title)}:{section.position}"
            )
            chunk = KnowledgeChunk(
                id=chunk_id,
                map_id=record.map_id,
                map_name=record.display_name,
                path=relative_path,
                category=category,
                file_summary=file_summary,
                section_title=section.title,
                content=section.content,
                image_ids=tuple(image_ids),
                position=section.position,
            )
            if chunk_id in self.chunks:
                self._issue(
                    "error",
                    "duplicate-chunk-id",
                    f"Duplicate chunk id: {chunk_id}",
                    file_path,
                )
                continue
            self.chunks[chunk_id] = chunk
            record.chunk_ids.append(chunk_id)

    def _register_image(
        self,
        record: MapRecord,
        image_path: str,
        section_title: str,
        document_path: Path,
        image_position: int = 1,
        image_count: int = 1,
    ) -> ImageAsset | None:
        normalized_path = normalize_image_path(image_path)
        file_path = self._safe_child(record.directory, normalized_path)
        if file_path is None:
            self._issue(
                "error",
                "unsafe-image-path",
                f"Image path escapes its map directory: {normalized_path}",
                document_path,
            )
            return None
        if not file_path.is_file():
            self._issue(
                "error",
                "referenced-image-missing",
                f"Referenced image does not exist: {normalized_path}",
                document_path,
            )
            return None

        asset_id = _image_id(record.map_id, normalized_path)
        asset = self.images.get(asset_id)
        if asset is None:
            asset = ImageAsset(
                id=asset_id,
                map_id=record.map_id,
                path=normalized_path,
                caption=_humanize_filename(
                    normalized_path,
                    section_title,
                    image_position=image_position,
                    image_count=image_count,
                ),
                section=section_title,
                document_path=document_path.relative_to(record.directory).as_posix(),
                source_file=file_path,
            )
            self.images[asset_id] = asset
        record.image_ids.add(asset_id)
        return asset

    def _validate_unindexed_documents(self, record: MapRecord) -> None:
        indexed = set(record.document_paths)
        for file_path in record.directory.rglob("*.md"):
            relative_path = file_path.relative_to(record.directory).as_posix()
            if relative_path not in indexed:
                self._issue(
                    "error",
                    "document-not-indexed",
                    f"Markdown document is not listed in index.json: {relative_path}",
                    file_path,
                )

    def _validate_orphan_images(self, record: MapRecord) -> None:
        referenced_paths = {
            self.images[image_id].source_file.resolve()
            for image_id in record.image_ids
            if image_id in self.images
        }
        for file_path in record.directory.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            if file_path.resolve() not in referenced_paths:
                self._issue(
                    "warning",
                    "image-not-referenced",
                    "Image is not referenced by any indexed document.",
                    file_path,
                )
