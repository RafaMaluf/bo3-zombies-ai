from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.knowledge_base import KnowledgeBase  # noqa: E402
from app.media import MediaService  # noqa: E402


def main() -> int:
    knowledge_base = KnowledgeBase(settings.maps_dir)
    if knowledge_base.errors:
        print("Knowledge-base validation failed; thumbnails were not generated.")
        return 1

    media = MediaService(settings.cache_dir)
    assets = list(knowledge_base.images.values())
    for index, asset in enumerate(assets, start=1):
        media.get_path(asset, "thumb")
        if index % 50 == 0 or index == len(assets):
            print(f"Generated {index}/{len(assets)} thumbnails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
