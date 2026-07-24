from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image, ImageOps, UnidentifiedImageError

from app.chunking import slugify
from app.knowledge_base import KnowledgeBase

MAP_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
DEFAULT_REMOVE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "form",
    "svg",
    "aside",
    "[aria-hidden='true']",
)
MAX_HTML_BYTES = 12 * 1024 * 1024
MAX_IMAGE_BYTES = 25 * 1024 * 1024
USER_AGENT = "KronoGuideIngestor/1.0 (+private personal knowledge-base; contact: repository owner)"


class IngestionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    path: str
    category: str
    summary: str
    source_url: str
    title: str = ""
    content_selector: str = ""
    remove_selectors: tuple[str, ...] = ()
    include_image_url_patterns: tuple[str, ...] = ()
    exclude_image_url_patterns: tuple[str, ...] = ()
    min_image_width: int = 320
    min_image_height: int = 180
    max_images: int = 80


@dataclass(frozen=True, slots=True)
class MapManifest:
    map_id: str
    display_name: str
    aliases: tuple[str, ...]
    summary: str
    documents: tuple[DocumentSpec, ...]


@dataclass(frozen=True, slots=True)
class ImportedImage:
    path: str
    source_url: str
    document: str
    sha256: str
    width: int
    height: int
    caption: str


@dataclass(frozen=True, slots=True)
class ImportedSource:
    url: str
    document: str
    selector: str
    captured_at: str
    sha256: str


@dataclass(slots=True)
class IngestionResult:
    map_id: str
    destination: Path
    documents: int
    images: int
    duplicate_images: int
    skipped_images: int
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False


def _string_list(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise IngestionError(f"{field_name} must be a list of strings.")
    return tuple(item.strip() for item in value if item.strip())


def _safe_document_path(value: Any) -> str:
    path = str(value or "").strip().replace("\\", "/")
    pure_path = PurePosixPath(path)
    if (
        not path
        or pure_path.is_absolute()
        or ".." in pure_path.parts
        or pure_path.suffix.lower() != ".md"
    ):
        raise IngestionError(f"Unsafe or invalid Markdown path: {path!r}.")
    return pure_path.as_posix()


def _http_url(value: Any, field_name: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IngestionError(f"{field_name} must be an absolute HTTP(S) URL.")
    return url


def load_manifest(path: Path) -> MapManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IngestionError(f"Could not read manifest {path}: {error}") from error
    if not isinstance(payload, dict):
        raise IngestionError("Manifest root must be a JSON object.")

    map_id = str(payload.get("map_id", "")).strip()
    if not MAP_ID_PATTERN.fullmatch(map_id):
        raise IngestionError("map_id must be lower snake_case.")
    display_name = str(payload.get("display_name", "")).strip()
    summary = str(payload.get("summary", "")).strip()
    if not display_name or not summary:
        raise IngestionError("display_name and summary are required.")

    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise IngestionError("documents must be a non-empty list.")

    documents: list[DocumentSpec] = []
    seen_paths: set[str] = set()
    for position, raw_document in enumerate(raw_documents, start=1):
        if not isinstance(raw_document, dict):
            raise IngestionError(f"documents[{position}] must be an object.")
        document_path = _safe_document_path(raw_document.get("path"))
        if document_path in seen_paths:
            raise IngestionError(f"Duplicate document path: {document_path}.")
        seen_paths.add(document_path)

        category = str(raw_document.get("category", "")).strip()
        document_summary = str(raw_document.get("summary", "")).strip()
        if not category or not document_summary:
            raise IngestionError(f"documents[{position}] requires category and summary.")

        min_width = int(raw_document.get("min_image_width", 320))
        min_height = int(raw_document.get("min_image_height", 180))
        max_images = int(raw_document.get("max_images", 80))
        if min_width < 1 or min_height < 1 or max_images < 0:
            raise IngestionError(f"Invalid image limits in documents[{position}].")

        documents.append(
            DocumentSpec(
                path=document_path,
                category=category,
                summary=document_summary,
                source_url=_http_url(
                    raw_document.get("source_url"),
                    f"documents[{position}].source_url",
                ),
                title=str(raw_document.get("title", "")).strip(),
                content_selector=str(raw_document.get("content_selector", "")).strip(),
                remove_selectors=_string_list(
                    raw_document.get("remove_selectors"),
                    f"documents[{position}].remove_selectors",
                ),
                include_image_url_patterns=_string_list(
                    raw_document.get("include_image_url_patterns"),
                    f"documents[{position}].include_image_url_patterns",
                ),
                exclude_image_url_patterns=_string_list(
                    raw_document.get("exclude_image_url_patterns"),
                    f"documents[{position}].exclude_image_url_patterns",
                ),
                min_image_width=min_width,
                min_image_height=min_height,
                max_images=max_images,
            )
        )

    return MapManifest(
        map_id=map_id,
        display_name=display_name,
        aliases=_string_list(payload.get("aliases"), "aliases"),
        summary=summary,
        documents=tuple(documents),
    )


def _fetch(
    client: httpx.Client,
    url: str,
    *,
    maximum_bytes: int,
    expected_kind: str,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = client.get(url)
            response.raise_for_status()
            if len(response.content) > maximum_bytes:
                raise IngestionError(
                    f"{expected_kind.capitalize()} exceeds {maximum_bytes} bytes: {url}"
                )
            return response
        except (httpx.HTTPError, IngestionError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(0.35 * (2**attempt))
    raise IngestionError(f"Could not download {expected_kind} {url}: {last_error}")


def _content_root(soup: BeautifulSoup, selector: str) -> Tag:
    if selector:
        try:
            selected = soup.select_one(selector)
        except Exception as error:
            raise IngestionError(f"Invalid content_selector {selector!r}: {error}") from error
        if selected is None:
            raise IngestionError(f"content_selector did not match: {selector!r}.")
        return selected
    for candidate in ("article", "main", "[role='main']", "body"):
        selected = soup.select_one(candidate)
        if selected is not None:
            return selected
    raise IngestionError("Downloaded HTML has no usable content root.")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _image_url(tag: Tag, page_url: str) -> str:
    srcset = tag.get("srcset") or tag.get("data-srcset")
    if isinstance(srcset, str) and srcset.strip():
        last_candidate = srcset.split(",")[-1].strip().split(" ")[0]
        return urljoin(page_url, last_candidate)
    candidates = (
        tag.get("data-src"),
        tag.get("data-lazy-src"),
        tag.get("data-original"),
        tag.get("src"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return urljoin(page_url, candidate.strip())
    return ""


def _matches_image_filters(url: str, spec: DocumentSpec) -> bool:
    if spec.include_image_url_patterns and not any(
        re.search(pattern, url, re.IGNORECASE) for pattern in spec.include_image_url_patterns
    ):
        return False
    return not any(
        re.search(pattern, url, re.IGNORECASE) for pattern in spec.exclude_image_url_patterns
    )


def _inline_text(tag: Tag) -> str:
    parts: list[str] = []
    for node in tag.descendants:
        if not isinstance(node, NavigableString):
            continue
        parent = node.parent
        if parent and parent.name in {"script", "style", "noscript"}:
            continue
        text = _clean_text(str(node))
        if text:
            parts.append(text)
    return _clean_text(" ".join(parts))


def _table_markdown(table: Tag) -> str:
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if cells and any(cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in normalized[1:])
    return "\n".join(lines)


class ImageImporter:
    def __init__(
        self,
        *,
        map_dir: Path,
        client: httpx.Client,
        maximum_dimension: int = 1600,
        webp_quality: int = 84,
    ) -> None:
        self.map_dir = map_dir
        self.client = client
        self.maximum_dimension = maximum_dimension
        self.webp_quality = webp_quality
        self.assets: list[ImportedImage] = []
        self.warnings: list[str] = []
        self.duplicate_count = 0
        self.skipped_count = 0
        self._digest_paths: dict[str, str] = {}
        self._source_paths: dict[str, str] = {}

    def import_tag(
        self,
        tag: Tag,
        *,
        page_url: str,
        document: DocumentSpec,
    ) -> str:
        source_url = _image_url(tag, page_url)
        if (
            not source_url
            or urlparse(source_url).scheme not in {"http", "https"}
            or not _matches_image_filters(source_url, document)
        ):
            self.skipped_count += 1
            return ""
        if source_url in self._source_paths:
            self.duplicate_count += 1
            return self._source_paths[source_url]
        document_images = sum(item.document == document.path for item in self.assets)
        if document_images >= document.max_images:
            self.skipped_count += 1
            return ""

        try:
            response = _fetch(
                self.client,
                source_url,
                maximum_bytes=MAX_IMAGE_BYTES,
                expected_kind="image",
            )
            with Image.open(BytesIO(response.content)) as opened:
                image = ImageOps.exif_transpose(opened)
                image.load()
                if (
                    image.width < document.min_image_width
                    or image.height < document.min_image_height
                ):
                    self.skipped_count += 1
                    return ""
                image.thumbnail(
                    (self.maximum_dimension, self.maximum_dimension),
                    Image.Resampling.LANCZOS,
                )
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "transparency" in image.info else "RGB")
                output = BytesIO()
                image.save(
                    output,
                    format="WEBP",
                    quality=self.webp_quality,
                    method=6,
                )
                encoded = output.getvalue()
                width, height = image.size
        except (IngestionError, OSError, ValueError, UnidentifiedImageError) as error:
            self.skipped_count += 1
            self.warnings.append(f"Skipped image {source_url}: {error}")
            return ""

        digest = hashlib.sha256(encoded).hexdigest()
        if digest in self._digest_paths:
            self.duplicate_count += 1
            relative_path = self._digest_paths[digest]
            self._source_paths[source_url] = relative_path
            return relative_path

        caption = _clean_text(str(tag.get("alt") or tag.get("title") or ""))
        source_stem = Path(urlparse(source_url).path).stem
        base_name = slugify(caption or source_stem or "screenshot")[:48]
        document_directory = slugify(Path(document.path).stem)
        relative_path = (
            PurePosixPath("images") / document_directory / f"{base_name}-{digest[:10]}.webp"
        ).as_posix()
        output_path = self.map_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(encoded)

        self._digest_paths[digest] = relative_path
        self._source_paths[source_url] = relative_path
        self.assets.append(
            ImportedImage(
                path=relative_path,
                source_url=source_url,
                document=document.path,
                sha256=digest,
                width=width,
                height=height,
                caption=caption,
            )
        )
        return relative_path


def _render_document(
    root: Tag,
    *,
    title: str,
    page_url: str,
    spec: DocumentSpec,
    image_importer: ImageImporter,
) -> str:
    blocks: list[str] = [f"# {title}"]
    seen_first_heading = False

    def render(tag: Tag) -> None:
        nonlocal seen_first_heading
        name = tag.name.lower()
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            heading = _clean_text(tag.get_text(" ", strip=True))
            if not heading:
                return
            if not seen_first_heading and name == "h1":
                seen_first_heading = True
                if heading.casefold() == title.casefold():
                    return
            level = 2 if name in {"h1", "h2"} else 3
            blocks.append(f"{'#' * level} {heading}")
            return
        if name == "img":
            path = image_importer.import_tag(
                tag,
                page_url=page_url,
                document=spec,
            )
            if path:
                blocks.append(f"Related image: {path}")
            return
        if name in {"p", "figcaption"}:
            text = _inline_text(tag)
            if text:
                blocks.append(text)
            for image in tag.find_all("img"):
                render(image)
            return
        if name in {"ul", "ol"}:
            ordered = name == "ol"
            lines: list[str] = []
            for position, item in enumerate(tag.find_all("li", recursive=False), start=1):
                text = _clean_text(item.get_text(" ", strip=True))
                if text:
                    marker = f"{position}." if ordered else "-"
                    lines.append(f"{marker} {text}")
                for image in item.find_all("img"):
                    path = image_importer.import_tag(
                        image,
                        page_url=page_url,
                        document=spec,
                    )
                    if path:
                        lines.append(f"  Related image: {path}")
            if lines:
                blocks.append("\n".join(lines))
            return
        if name == "table":
            table = _table_markdown(tag)
            if table:
                blocks.append(table)
            return
        if name == "pre":
            text = tag.get_text("\n", strip=True)
            if text:
                blocks.append(f"```\n{text}\n```")
            return
        if name == "blockquote":
            text = tag.get_text("\n", strip=True)
            if text:
                blocks.append("\n".join(f"> {line}" for line in text.splitlines()))
            return
        for child in tag.children:
            if isinstance(child, Tag):
                render(child)

    for child in root.children:
        if isinstance(child, Tag):
            render(child)

    compact: list[str] = []
    for block in blocks:
        cleaned = block.strip()
        if cleaned and (not compact or cleaned != compact[-1]):
            compact.append(cleaned)
    return "\n\n".join(compact).strip() + "\n"


def _document_title(root: Tag, spec: DocumentSpec, fallback: str) -> str:
    if spec.title:
        return spec.title
    heading = root.find(["h1", "h2"])
    if heading:
        title = _clean_text(heading.get_text(" ", strip=True))
        if title:
            return title
    return fallback


def build_map(
    manifest: MapManifest,
    map_dir: Path,
    *,
    client: httpx.Client,
) -> IngestionResult:
    map_dir.mkdir(parents=True, exist_ok=False)
    image_importer = ImageImporter(map_dir=map_dir, client=client)
    imported_sources: list[ImportedSource] = []
    index_files: list[dict[str, str]] = []

    for spec in manifest.documents:
        response = _fetch(
            client,
            spec.source_url,
            maximum_bytes=MAX_HTML_BYTES,
            expected_kind="page",
        )
        soup = BeautifulSoup(response.content, "html.parser")
        root = _content_root(soup, spec.content_selector)
        for selector in (*DEFAULT_REMOVE_SELECTORS, *spec.remove_selectors):
            try:
                for unwanted in root.select(selector):
                    unwanted.decompose()
            except Exception as error:
                raise IngestionError(f"Invalid remove selector {selector!r}: {error}") from error

        title = _document_title(root, spec, manifest.display_name)
        markdown = _render_document(
            root,
            title=title,
            page_url=str(response.url),
            spec=spec,
            image_importer=image_importer,
        )
        if "\n## " not in markdown:
            markdown = markdown.rstrip() + "\n\n## overview\n\n" + spec.summary + "\n"

        document_path = map_dir / spec.path
        document_path.parent.mkdir(parents=True, exist_ok=True)
        document_path.write_text(markdown, encoding="utf-8")
        imported_sources.append(
            ImportedSource(
                url=spec.source_url,
                document=spec.path,
                selector=spec.content_selector or "auto",
                captured_at=datetime.now(UTC).isoformat(),
                sha256=hashlib.sha256(response.content).hexdigest(),
            )
        )
        index_files.append(
            {
                "path": spec.path,
                "category": spec.category,
                "summary": spec.summary,
            }
        )

    index = {
        "map_id": manifest.map_id,
        "display_name": manifest.display_name,
        "aliases": list(manifest.aliases),
        "summary": manifest.summary,
        "files": index_files,
    }
    (map_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    provenance = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "sources": [asdict(item) for item in imported_sources],
        "images": [asdict(item) for item in image_importer.assets],
    }
    (map_dir / "sources.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return IngestionResult(
        map_id=manifest.map_id,
        destination=map_dir,
        documents=len(manifest.documents),
        images=len(image_importer.assets),
        duplicate_images=image_importer.duplicate_count,
        skipped_images=image_importer.skipped_count,
        warnings=image_importer.warnings,
    )


def ingest_manifest(
    manifest_path: Path,
    *,
    maps_dir: Path,
    cache_dir: Path,
    replace: bool = False,
    dry_run: bool = False,
    client: httpx.Client | None = None,
) -> IngestionResult:
    manifest = load_manifest(manifest_path)
    target = maps_dir.resolve() / manifest.map_id
    if target.exists() and not replace:
        raise IngestionError(f"{target} already exists. Use --replace to archive and replace it.")

    run_root = cache_dir.resolve() / f"{manifest.map_id}-{uuid.uuid4().hex[:10]}"
    stage_maps = run_root / "maps"
    stage_map = stage_maps / manifest.map_id
    stage_maps.mkdir(parents=True)

    owns_client = client is None
    active_client = client or httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,image/*;q=0.9,*/*;q=0.8"},
    )
    try:
        result = build_map(manifest, stage_map, client=active_client)
        knowledge_base = KnowledgeBase(stage_maps, verify_images=True)
        if knowledge_base.errors or knowledge_base.warnings:
            details = "; ".join(
                f"{issue.severity}:{issue.code}:{issue.path}" for issue in knowledge_base.issues
            )
            raise IngestionError(f"Generated map failed validation: {details}")

        if dry_run:
            result.dry_run = True
            result.destination = stage_map
            return result

        maps_dir.mkdir(parents=True, exist_ok=True)
        backup: Path | None = None
        if target.exists():
            backup_root = cache_dir.resolve() / "backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup = backup_root / f"{manifest.map_id}-{timestamp}"
            os.replace(target, backup)
        try:
            os.replace(stage_map, target)
        except OSError:
            if backup is not None and backup.exists() and not target.exists():
                os.replace(backup, target)
            raise
        result.destination = target
        shutil.rmtree(run_root, ignore_errors=True)
        return result
    except Exception:
        if not dry_run:
            shutil.rmtree(run_root, ignore_errors=True)
        raise
    finally:
        if owns_client:
            active_client.close()
