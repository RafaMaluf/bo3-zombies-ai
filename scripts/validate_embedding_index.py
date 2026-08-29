from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.assets import AssetManifest  # noqa: E402
from app.config import settings  # noqa: E402
from app.embeddings import EmbeddingError, EmbeddingIndex  # noqa: E402
from app.knowledge_base import KnowledgeBase  # noqa: E402


def main() -> int:
    asset_manifest = AssetManifest.load(settings.asset_manifest_path)
    knowledge_base = KnowledgeBase(settings.maps_dir, asset_manifest=asset_manifest)
    if knowledge_base.errors:
        print("Knowledge base has validation errors; embedding index cannot be verified.")
        return 1
    try:
        index = EmbeddingIndex.load(
            settings.embedding_index_dir,
            knowledge_base,
            expected_model=settings.voyage_model,
        )
    except EmbeddingError as error:
        print(f"Embedding index validation failed: {error}")
        return 1
    print(
        "Embedding index valid: "
        f"model={index.model}, dimensions={index.dimensions}, "
        f"vectors={len(index.vectors)}, knowledge_base_hash={index.knowledge_base_hash}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
