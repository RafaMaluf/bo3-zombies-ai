import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.knowledge_base import KnowledgeBase
from scripts.ingestion import IngestionError, ingest_manifest, load_manifest


def _image_bytes(size: tuple[int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color=(28, 74, 110)).save(output, format="PNG")
    return output.getvalue()


def _write_manifest(path: Path, *, document_path: str = "guide.md") -> None:
    path.write_text(
        json.dumps(
            {
                "map_id": "test_map",
                "display_name": "Test Map",
                "aliases": ["tm"],
                "summary": "A generated test map.",
                "documents": [
                    {
                        "path": document_path,
                        "category": "setup",
                        "summary": "How to complete the generated setup.",
                        "source_url": "https://guides.example/map",
                        "content_selector": "article.guide",
                        "remove_selectors": [".advertisement"],
                        "min_image_width": 100,
                        "min_image_height": 100,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_ingestion_builds_valid_map_deduplicates_and_normalizes_images(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path)
    large_image = _image_bytes((800, 450))
    tiny_image = _image_bytes((32, 32))
    html = b"""
    <html><body>
      <nav>Navigation noise</nav>
      <article class="guide">
        <h1>Test Map Setup</h1>
        <div class="advertisement"><p>Buy something unrelated.</p></div>
        <h2>Turn on power</h2>
        <p>Open the first door and use the switch.</p>
        <img src="/screens/power.png" alt="Power switch">
        <h2>Finish setup</h2>
        <ol><li>Return to spawn.</li><li>Use the console.</li></ol>
        <img src="/screens/power-copy.png" alt="Same power switch">
        <img src="/icons/tiny.png" alt="Tiny icon">
      </article>
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://guides.example/map":
            return httpx.Response(200, content=html, request=request)
        if request.url.path in {"/screens/power.png", "/screens/power-copy.png"}:
            return httpx.Response(200, content=large_image, request=request)
        if request.url.path == "/icons/tiny.png":
            return httpx.Response(200, content=tiny_image, request=request)
        return httpx.Response(404, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ingest_manifest(
            manifest_path,
            maps_dir=tmp_path / "maps",
            cache_dir=tmp_path / "cache",
            client=client,
        )

    assert result.documents == 1
    assert result.images == 1
    assert result.duplicate_images == 1
    assert result.skipped_images == 1
    assert result.destination == (tmp_path / "maps" / "test_map").resolve()

    markdown = (result.destination / "guide.md").read_text(encoding="utf-8")
    assert "## Turn on power" in markdown
    assert "Buy something unrelated" not in markdown
    assert markdown.count("images/guide/power-switch-") == 2

    provenance = json.loads((result.destination / "sources.json").read_text(encoding="utf-8"))
    assert provenance["sources"][0]["url"] == "https://guides.example/map"
    assert provenance["images"][0]["path"].endswith(".webp")
    assert provenance["images"][0]["source_url"].endswith("/screens/power.png")

    knowledge_base = KnowledgeBase(tmp_path / "maps", verify_images=True)
    assert not knowledge_base.issues
    assert knowledge_base.stats == {
        "maps": 1,
        "documents": 1,
        "chunks": 2,
        "images": 1,
        "validation_errors": 0,
        "validation_warnings": 0,
    }


def test_manifest_rejects_unsafe_document_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, document_path="../outside.md")

    with pytest.raises(IngestionError, match="Unsafe or invalid"):
        load_manifest(manifest_path)


def test_ingestion_fails_when_content_selector_does_not_match(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html><body><main>Nothing here</main></body></html>",
            request=request,
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(IngestionError, match="did not match"),
    ):
        ingest_manifest(
            manifest_path,
            maps_dir=tmp_path / "maps",
            cache_dir=tmp_path / "cache",
            client=client,
        )
