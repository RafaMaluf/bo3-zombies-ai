from __future__ import annotations

import io
import json
import urllib.error
from array import array
from pathlib import Path

import pytest

from app.embeddings import (
    EmbeddingError,
    EmbeddingIndex,
    VoyageEmbeddingClient,
    knowledge_base_fingerprint,
    ordered_chunks,
    write_embedding_index,
)
from app.knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent


class StaticEmbeddingClient:
    model = "test-embedding-model"

    def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        assert input_type == "document"
        return [[1.0, 0.0] for _ in texts]


def test_versioned_embedding_index_matches_current_knowledge_base() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")

    index = EmbeddingIndex.load(
        ROOT / "embeddings",
        knowledge_base,
        expected_model="voyage-4-large",
    )

    assert len(index.chunk_ids) == knowledge_base.stats["chunks"] == 602
    assert index.dimensions == 1024
    assert index.knowledge_base_hash == knowledge_base_fingerprint(
        ordered_chunks(knowledge_base)
    )


def test_write_and_score_embedding_index(tmp_path: Path) -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")

    manifest = write_embedding_index(
        tmp_path,
        knowledge_base,
        client=StaticEmbeddingClient(),  # type: ignore[arg-type]
        batch_size=200,
    )
    index = EmbeddingIndex.load(
        tmp_path,
        knowledge_base,
        expected_model=StaticEmbeddingClient.model,
    )

    assert manifest["validated_vectors"] == 602
    assert set(index.score((1.0, 0.0)).values()) == {1.0}
    with pytest.raises(EmbeddingError, match="expected 2"):
        index.score((1.0,))


def test_embedding_index_rejects_stale_or_damaged_files(tmp_path: Path) -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    chunks = ordered_chunks(knowledge_base)
    manifest = {
        "version": 1,
        "model": "test-model",
        "dimensions": 2,
        "chunk_ids": [chunk.id for chunk in chunks],
        "knowledge_base_hash": knowledge_base_fingerprint(chunks),
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    values = array("f", [1.0, 0.0] * len(chunks))
    (tmp_path / "vectors.f32").write_bytes(values.tobytes())

    manifest["knowledge_base_hash"] = "stale"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(EmbeddingError, match="stale"):
        EmbeddingIndex.load(tmp_path, knowledge_base, expected_model="test-model")

    manifest["knowledge_base_hash"] = knowledge_base_fingerprint(chunks)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "vectors.f32").write_bytes(b"broken")
    with pytest.raises(EmbeddingError, match="size mismatch"):
        EmbeddingIndex.load(tmp_path, knowledge_base, expected_model="test-model")


def test_embedding_index_rejects_malformed_manifest(tmp_path: Path) -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    (tmp_path / "manifest.json").write_text(
        '{"version": 1, "dimensions": "invalid", "chunk_ids": []}',
        encoding="utf-8",
    )

    with pytest.raises(EmbeddingError, match="numeric fields"):
        EmbeddingIndex.load(tmp_path, knowledge_base, expected_model="test-model")


def test_voyage_client_normalizes_and_caches_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"data": [{"index": 0, "embedding": [3.0, 4.0]}]}).encode()

    def fake_urlopen(request: object, timeout: float):
        nonlocal calls
        calls += 1
        return Response()

    monkeypatch.setattr("app.embeddings.urllib.request.urlopen", fake_urlopen)
    client = VoyageEmbeddingClient("secret", "test-model")

    assert client.embed_query("power") == pytest.approx((0.6, 0.8))
    assert client.embed_query("power") == pytest.approx((0.6, 0.8))
    assert calls == 1


def test_voyage_client_surfaces_non_retryable_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: float):
        raise urllib.error.HTTPError(
            "https://example.test",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"detail":"invalid key"}'),
        )

    monkeypatch.setattr("app.embeddings.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(EmbeddingError, match="401"):
        VoyageEmbeddingClient("invalid", max_retries=0).embed(["query"], input_type="query")


def test_voyage_client_rejects_malformed_success_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr(
        "app.embeddings.urllib.request.urlopen",
        lambda request, timeout: Response(),
    )

    with pytest.raises(EmbeddingError, match="invalid embedding payload"):
        VoyageEmbeddingClient("secret", max_retries=0).embed(["query"], input_type="query")
