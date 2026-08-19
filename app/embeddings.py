from __future__ import annotations

import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.request
from array import array
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from app.domain import KnowledgeChunk
from app.knowledge_base import KnowledgeBase

INDEX_VERSION = 1
VECTOR_FILENAME = "vectors.f32"
MANIFEST_FILENAME = "manifest.json"
VOYAGE_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"


class EmbeddingError(RuntimeError):
    pass


def embedding_text(chunk: KnowledgeChunk) -> str:
    return "\n".join(
        (
            f"Map: {chunk.map_name}",
            f"Category: {chunk.category}",
            f"Guide: {chunk.path.replace('_', ' ').replace('/', ' / ')}",
            f"Section: {chunk.section_title}",
            f"Summary: {chunk.file_summary}",
            chunk.content,
        )
    )


def ordered_chunks(knowledge_base: KnowledgeBase) -> tuple[KnowledgeChunk, ...]:
    return tuple(sorted(knowledge_base.chunks.values(), key=lambda chunk: chunk.id))


def knowledge_base_fingerprint(chunks: Iterable[KnowledgeChunk]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(embedding_text(chunk).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _normalized(values: list[float]) -> list[float]:
    if not values or not all(math.isfinite(value) for value in values):
        raise EmbeddingError("Embedding contains missing or non-finite values.")
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0:
        raise EmbeddingError("Embedding has zero length.")
    return [value / norm for value in values]


@dataclass(slots=True, eq=False)
class VoyageEmbeddingClient:
    api_key: str
    model: str = "voyage-4-large"
    timeout_seconds: float = 45.0
    max_retries: int = 4
    _query_cache: dict[str, tuple[float, ...]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _cache_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingError("VOYAGE_API_KEY is not configured.")
        if not texts:
            return []
        payload = json.dumps(
            {
                "input": texts,
                "model": self.model,
                "input_type": input_type,
                "output_dimension": 1024,
                "output_dtype": "float",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            VOYAGE_EMBEDDINGS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw_body = response.read().decode("utf-8")
                try:
                    body = json.loads(raw_body)
                    data = body.get("data")
                    if not isinstance(data, list) or len(data) != len(texts):
                        raise EmbeddingError("Voyage returned an unexpected embedding count.")
                    ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
                    vectors = [item.get("embedding") for item in ordered]
                    if not all(isinstance(vector, list) for vector in vectors):
                        raise EmbeddingError("Voyage returned an invalid embedding payload.")
                    return [_normalized([float(value) for value in vector]) for vector in vectors]
                except (AttributeError, json.JSONDecodeError, TypeError, ValueError) as error:
                    raise EmbeddingError("Voyage returned an invalid embedding payload.") from error
            except urllib.error.HTTPError as error:
                retryable = error.code == 429 or error.code >= 500
                if not retryable or attempt >= self.max_retries:
                    detail = error.read().decode("utf-8", errors="replace")[:500]
                    raise EmbeddingError(
                        f"Voyage embedding request failed ({error.code}): {detail}"
                    ) from error
            except (urllib.error.URLError, TimeoutError) as error:
                if attempt >= self.max_retries:
                    raise EmbeddingError(f"Voyage embedding request failed: {error}") from error
            time.sleep(min(2**attempt, 8))
        raise EmbeddingError("Voyage embedding request exhausted all retries.")

    def embed_query(self, text: str) -> tuple[float, ...]:
        with self._cache_lock:
            cached = self._query_cache.get(text)
        if cached is not None:
            return cached
        vectors = self.embed([text], input_type="query")
        result = tuple(vectors[0])
        with self._cache_lock:
            if len(self._query_cache) >= 256:
                self._query_cache.pop(next(iter(self._query_cache)))
            self._query_cache[text] = result
        return result


@dataclass(frozen=True, slots=True)
class EmbeddingIndex:
    model: str
    dimensions: int
    chunk_ids: tuple[str, ...]
    vectors: tuple[tuple[float, ...], ...]
    knowledge_base_hash: str
    created_at: str

    @classmethod
    def load(
        cls,
        directory: Path,
        knowledge_base: KnowledgeBase,
        *,
        expected_model: str,
    ) -> EmbeddingIndex:
        manifest_path = directory / MANIFEST_FILENAME
        vector_path = directory / VECTOR_FILENAME
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EmbeddingError(f"Could not load embedding manifest: {error}") from error

        if not isinstance(manifest, dict):
            raise EmbeddingError("Embedding manifest must be a JSON object.")

        chunks = ordered_chunks(knowledge_base)
        raw_chunk_ids = manifest.get("chunk_ids")
        if not isinstance(raw_chunk_ids, list):
            raise EmbeddingError("Embedding manifest chunk IDs are invalid.")
        chunk_ids = tuple(str(value) for value in raw_chunk_ids)
        expected_ids = tuple(chunk.id for chunk in chunks)
        try:
            version = int(manifest.get("version", 0))
            dimensions = int(manifest.get("dimensions", 0))
        except (TypeError, ValueError) as error:
            raise EmbeddingError("Embedding manifest contains invalid numeric fields.") from error
        model = str(manifest.get("model", ""))
        fingerprint = knowledge_base_fingerprint(chunks)
        if version != INDEX_VERSION:
            raise EmbeddingError("Embedding index version is unsupported.")
        if model != expected_model:
            raise EmbeddingError(
                f"Embedding model mismatch: index={model}, configured={expected_model}."
            )
        if chunk_ids != expected_ids:
            raise EmbeddingError("Embedding index chunk IDs do not match the knowledge base.")
        if manifest.get("knowledge_base_hash") != fingerprint:
            raise EmbeddingError("Embedding index is stale for the current knowledge base.")
        if dimensions <= 0:
            raise EmbeddingError("Embedding index dimensions are invalid.")

        try:
            raw = vector_path.read_bytes()
        except OSError as error:
            raise EmbeddingError(f"Could not load embedding vectors: {error}") from error
        expected_bytes = len(chunk_ids) * dimensions * 4
        if len(raw) != expected_bytes:
            raise EmbeddingError(
                f"Embedding vector size mismatch: expected {expected_bytes}, found {len(raw)}."
            )
        values = array("f")
        values.frombytes(raw)
        if sys.byteorder != "little":
            values.byteswap()
        vectors: list[tuple[float, ...]] = []
        for offset in range(0, len(values), dimensions):
            vector = tuple(values[offset : offset + dimensions])
            if not all(math.isfinite(value) for value in vector):
                raise EmbeddingError("Embedding index contains non-finite values.")
            norm = math.sqrt(sum(value * value for value in vector))
            if not 0.98 <= norm <= 1.02:
                raise EmbeddingError(
                    f"Embedding index contains a non-normalized vector ({norm:.4f})."
                )
            vectors.append(vector)
        return cls(
            model=model,
            dimensions=dimensions,
            chunk_ids=chunk_ids,
            vectors=tuple(vectors),
            knowledge_base_hash=fingerprint,
            created_at=str(manifest.get("created_at", "")),
        )

    def score(self, query_vector: tuple[float, ...]) -> dict[str, float]:
        if len(query_vector) != self.dimensions:
            raise EmbeddingError(
                f"Query embedding has {len(query_vector)} dimensions; expected {self.dimensions}."
            )
        return {
            chunk_id: sum(left * right for left, right in zip(query_vector, vector, strict=True))
            for chunk_id, vector in zip(self.chunk_ids, self.vectors, strict=True)
        }


def write_embedding_index(
    directory: Path,
    knowledge_base: KnowledgeBase,
    *,
    client: VoyageEmbeddingClient,
    batch_size: int = 128,
) -> dict[str, object]:
    chunks = ordered_chunks(knowledge_base)
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors.extend(
            client.embed([embedding_text(chunk) for chunk in batch], input_type="document")
        )
        print(f"Embedded {len(vectors)}/{len(chunks)} chunks.", flush=True)

    if len(vectors) != len(chunks):
        raise EmbeddingError("Generated vector count does not match the knowledge base.")
    dimensions = len(vectors[0]) if vectors else 0
    if dimensions <= 0 or any(len(vector) != dimensions for vector in vectors):
        raise EmbeddingError("Generated embeddings have inconsistent dimensions.")

    directory.mkdir(parents=True, exist_ok=True)
    flattened = array("f", (value for vector in vectors for value in vector))
    if sys.byteorder != "little":
        flattened.byteswap()
    (directory / VECTOR_FILENAME).write_bytes(flattened.tobytes())
    manifest: dict[str, object] = {
        "version": INDEX_VERSION,
        "provider": "voyage",
        "model": client.model,
        "dimensions": dimensions,
        "chunk_count": len(chunks),
        "chunk_ids": [chunk.id for chunk in chunks],
        "knowledge_base_hash": knowledge_base_fingerprint(chunks),
        "created_at": datetime.now(UTC).isoformat(),
        "vector_file": VECTOR_FILENAME,
    }
    (directory / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    cls = EmbeddingIndex.load(
        directory,
        knowledge_base,
        expected_model=client.model,
    )
    manifest["validated_vectors"] = len(cls.vectors)
    return manifest
