from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.knowledge_base import KnowledgeBase  # noqa: E402


def main() -> int:
    knowledge_base = KnowledgeBase(settings.maps_dir)
    stats = knowledge_base.stats

    print(
        "Knowledge base: "
        f"{stats['maps']} maps, "
        f"{stats['documents']} documents, "
        f"{stats['chunks']} chunks, "
        f"{stats['images']} images"
    )

    for issue in knowledge_base.issues:
        print(f"{issue.severity.upper():7} {issue.code:26} {issue.path} — {issue.message}")

    report_dir = settings.cache_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "knowledge-base-validation.json"
    report_path.write_text(
        json.dumps(
            {
                "stats": stats,
                "issues": [asdict(issue) for issue in knowledge_base.issues],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Report: {report_path}")

    if knowledge_base.errors:
        print(f"Validation failed with {len(knowledge_base.errors)} error(s).")
        return 1
    print(f"Validation passed with {len(knowledge_base.warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
