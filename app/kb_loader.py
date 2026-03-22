import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from app.chunking import split_markdown_by_sections
from app.config import MAPS_DIR, MAX_FILE_CHARS, MAX_TOTAL_CONTEXT_CHARS
from app.schemas import SelectedFile


def load_all_map_indexes() -> Dict[str, dict]:
    """
    Load all map index.json files from maps/*/index.json.
    Also pre-computes and stores markdown chunks for every file in each index.
    """
    indexes: Dict[str, dict] = {}

    if not MAPS_DIR.exists():
        return indexes

    for map_dir in MAPS_DIR.iterdir():
        if not map_dir.is_dir():
            continue

        index_path = map_dir / "index.json"
        if not index_path.exists():
            continue

        with index_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        map_id = data["map_id"]

        # Pre-compute chunks for each file so retrieval can use them later
        for file_info in data.get("files", []):
            file_path = map_dir / file_info["path"]
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                file_info["chunks"] = split_markdown_by_sections(content)
            else:
                file_info["chunks"] = []

        indexes[map_id] = data

    return indexes


def build_catalog_for_selection(indexes: Dict[str, dict]) -> str:
    """
    Build a compact text catalog that the model uses in step 1
    to decide which files are relevant.

    Sends only minimal metadata: display_name, map_id, and file count.
    """
    lines: List[str] = []
    lines.append("AVAILABLE KNOWLEDGE BASE")
    lines.append("")

    for map_id, index_data in indexes.items():
        display_name = index_data.get("display_name", map_id)
        file_count = len(index_data.get("files", []))
        lines.append(f"MAP: {display_name} ({map_id}) - {file_count} files")

    return "\n".join(lines)


def get_file_info(indexes: Dict[str, dict], map_id: str, path: str) -> dict | None:
    index_data = indexes.get(map_id)
    if not index_data:
        return None

    for file_info in index_data.get("files", []):
        if file_info["path"] == path:
            return file_info
    return None


def read_selected_files(indexes: Dict[str, dict], selected_files: List[SelectedFile]) -> Tuple[str, List[str]]:
    """
    Read selected .md files and extract image paths.
    Returns:
      - combined context text
      - list of extracted image paths
    """
    chunks: List[str] = []
    used_images: List[str] = []
    total_chars = 0

    for sf in selected_files:
        info = get_file_info(indexes, sf.map_id, sf.path)
        if info is None:
            continue

        file_path = MAPS_DIR / sf.map_id / sf.path
        if not file_path.exists():
            continue

        content = file_path.read_text(encoding="utf-8")

        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n\n[TRUNCATED]"

        content_images = extract_image_paths(content)
        used_images.extend(content_images)

        chunk = (
            f"MAP: {sf.map_id}\n"
            f"FILE: {sf.path}\n"
            f"CATEGORY: {info.get('category', 'unknown')}\n"
            f"SUMMARY: {info.get('summary', '')}\n\n"
            f"{content}\n"
        )

        if total_chars + len(chunk) > MAX_TOTAL_CONTEXT_CHARS:
            break

        chunks.append(chunk)
        total_chars += len(chunk)

    return "\n\n---\n\n".join(chunks), dedupe_preserve_order(used_images)


def extract_image_paths(content: str) -> List[str]:
    """
    Extract image paths from markdown content using simple patterns:
    - Related image: images/...
    - - images/...
    """
    paths: List[str] = []

    pattern_related = re.findall(r"Related image:\s*([^\s]+)", content)
    paths.extend(pattern_related)

    pattern_list = re.findall(r"^\-\s+(images/[^\s]+)$", content, flags=re.MULTILINE)
    paths.extend(pattern_list)

    return dedupe_preserve_order(paths)


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output