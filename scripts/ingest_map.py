from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ingestion import IngestionError, ingest_manifest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and validate a Krono map from a source manifest."
    )
    parser.add_argument("manifest", type=Path, help="Path to the JSON manifest.")
    parser.add_argument(
        "--maps-dir",
        type=Path,
        default=ROOT / "maps",
        help="Knowledge-base maps directory.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / ".cache" / "ingestion",
        help="Staging and backup directory.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Archive and replace an existing map with the same map_id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and keep the result in staging without changing maps/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = ingest_manifest(
            args.manifest,
            maps_dir=args.maps_dir,
            cache_dir=args.cache_dir,
            replace=args.replace,
            dry_run=args.dry_run,
        )
    except IngestionError as error:
        print(f"Ingestion failed: {error}", file=sys.stderr)
        return 1

    payload = asdict(result)
    payload["destination"] = str(result.destination)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
