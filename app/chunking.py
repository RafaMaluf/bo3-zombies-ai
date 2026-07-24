from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath

SECTION_PATTERN = re.compile(r"^(##\s+.+)$", flags=re.MULTILINE)
IMAGE_PATTERN = re.compile(
    r"images/[A-Za-z0-9_./-]+\.(?:jpg|jpeg|png|webp|gif)",
    flags=re.IGNORECASE,
)
IMAGE_ONLY_HEADING = re.compile(
    r"^(?:related\s+)?images?$",
    flags=re.IGNORECASE,
)
IMAGE_REFERENCE_LINE = re.compile(
    r"^\s*(?:-\s*)?(?:related\s+images?\s*:\s*)?"
    r"images/[A-Za-z0-9_./-]+\.(?:jpg|jpeg|png|webp|gif)\s*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class MarkdownSection:
    title: str
    content: str
    image_paths: tuple[str, ...]
    position: int


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "overview"


def normalize_image_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    normalized = str(PurePosixPath(normalized))
    return normalized.removeprefix("./")


def extract_image_paths(content: str) -> tuple[str, ...]:
    seen: set[str] = set()
    paths: list[str] = []
    for match in IMAGE_PATTERN.finditer(content):
        path = normalize_image_path(match.group(0))
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return tuple(paths)


def _remove_image_reference_lines(content: str) -> str:
    clean_lines: list[str] = []
    for line in content.splitlines():
        if IMAGE_REFERENCE_LINE.match(line):
            continue
        if line.strip().lower() in {"related image:", "related images:"}:
            continue
        clean_lines.append(line.rstrip())
    return "\n".join(clean_lines).strip()


def split_markdown_by_sections(content: str) -> list[MarkdownSection]:
    parts = SECTION_PATTERN.split(content)
    sections: list[MarkdownSection] = []
    position = 0

    pre_heading = parts[0].strip()
    if pre_heading and not re.fullmatch(r"#\s+.+", pre_heading):
        sections.append(
            MarkdownSection(
                title="overview",
                content=_remove_image_reference_lines(pre_heading),
                image_paths=extract_image_paths(pre_heading),
                position=position,
            )
        )
        position += 1

    index = 1
    while index < len(parts) - 1:
        heading_line = parts[index].strip()
        title = heading_line.lstrip("#").strip()
        body = parts[index + 1].strip()
        index += 2

        # Many legacy documents end with a duplicate gallery containing every
        # image in the file. Images are already attached to their real steps.
        if IMAGE_ONLY_HEADING.match(title):
            continue

        image_paths = extract_image_paths(body)
        clean_body = _remove_image_reference_lines(body)
        section_content = f"## {title}"
        if clean_body:
            section_content = f"{section_content}\n\n{clean_body}"

        sections.append(
            MarkdownSection(
                title=title,
                content=section_content,
                image_paths=image_paths,
                position=position,
            )
        )
        position += 1

    return sections
