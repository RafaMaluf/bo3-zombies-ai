from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    path: str = ""


@dataclass(frozen=True, slots=True)
class ImageAsset:
    id: str
    map_id: str
    path: str
    caption: str
    section: str
    document_path: str
    source_file: Path


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    id: str
    map_id: str
    map_name: str
    path: str
    category: str
    file_summary: str
    section_title: str
    content: str
    image_ids: tuple[str, ...]
    position: int


@dataclass(slots=True)
class MapRecord:
    map_id: str
    display_name: str
    summary: str
    aliases: tuple[str, ...]
    directory: Path
    document_paths: tuple[str, ...]
    chunk_ids: list[str] = field(default_factory=list)
    image_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    chunk: KnowledgeChunk
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    chunks: tuple[ScoredChunk, ...]
    active_map_id: str | None
    explicit_map_ids: tuple[str, ...]
    needs_clarification: bool
    clarification_question: str
    suggested_map_ids: tuple[str, ...]
