from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.assets import AssetManifest  # noqa: E402
from app.config import settings  # noqa: E402
from app.embeddings import (  # noqa: E402
    EmbeddingError,
    VoyageEmbeddingClient,
    write_embedding_index,
)
from app.knowledge_base import KnowledgeBase  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Krono's Voyage embedding index.")
    parser.add_argument("--maps-dir", type=Path, default=settings.maps_dir)
    parser.add_argument("--output-dir", type=Path, default=settings.embedding_index_dir)
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not settings.voyage_api_key:
        print("VOYAGE_API_KEY is not configured.", file=sys.stderr)
        return 2
    manifest = AssetManifest.load(args.maps_dir.parent / "assets" / "image-manifest.json")
    knowledge_base = KnowledgeBase(args.maps_dir, asset_manifest=manifest)
    if knowledge_base.errors:
        print("Knowledge base has validation errors.", file=sys.stderr)
        return 2
    client = VoyageEmbeddingClient(settings.voyage_api_key, settings.voyage_model)
    try:
        manifest = write_embedding_index(
            args.output_dir,
            knowledge_base,
            client=client,
            batch_size=max(1, args.batch_size),
        )
    except EmbeddingError as error:
        print(f"Embedding index failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
