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
from app.embeddings import EmbeddingError, EmbeddingIndex, VoyageEmbeddingClient  # noqa: E402
from app.knowledge_base import KnowledgeBase  # noqa: E402
from app.retrieval import SearchEngine  # noqa: E402
from scripts.retrieval_evals import (  # noqa: E402
    EvaluationError,
    evaluate_suite,
    load_eval_suite,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Krono's deterministic local retrieval.")
    parser.add_argument(
        "--suite",
        type=Path,
        default=ROOT / "evals" / "queries.json",
    )
    parser.add_argument(
        "--maps-dir",
        type=Path,
        default=ROOT / "maps",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / ".cache" / "reports" / "retrieval-eval.json",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Evaluate BM25 plus the configured persisted Voyage index.",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Write the report but ignore threshold failures.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        suite = load_eval_suite(args.suite)
        manifest = AssetManifest.load(args.maps_dir.parent / "assets" / "image-manifest.json")
        knowledge_base = KnowledgeBase(args.maps_dir, asset_manifest=manifest)
        if knowledge_base.errors:
            details = ", ".join(issue.code for issue in knowledge_base.errors)
            raise EvaluationError(f"Knowledge base is invalid: {details}")
        embedding_index = None
        embedding_client = None
        if args.hybrid:
            if not settings.embeddings_configured:
                raise EvaluationError("Voyage embeddings are not configured.")
            try:
                embedding_index = EmbeddingIndex.load(
                    settings.embedding_index_dir,
                    knowledge_base,
                    expected_model=settings.voyage_model,
                )
            except EmbeddingError as error:
                raise EvaluationError(str(error)) from error
            embedding_client = VoyageEmbeddingClient(
                settings.voyage_api_key,
                settings.voyage_model,
            )
        report = evaluate_suite(
            SearchEngine(knowledge_base, embedding_index, embedding_client),
            suite,
            limit=max(3, args.limit),
        )
    except EvaluationError as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 2

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report.as_json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Retrieval evaluation: {report.passed}/{report.total} cases passed "
        f"({report.metrics['pass_rate']:.1%})."
    )
    print(
        "Metrics: "
        f"map={report.metrics['map_accuracy']:.1%}, "
        f"document@1={report.metrics['document_hit_at_1']:.1%}, "
        f"documents@10={report.metrics['required_documents_hit_at_10']:.1%}, "
        f"section@3={report.metrics['section_hit_at_3']:.1%}, "
        f"images@3={report.metrics['image_hit_at_3']:.1%}, "
        f"p95={report.metrics['p95_latency_ms']:.3f}ms"
    )
    for language, metrics in report.language_metrics.items():
        print(
            f"Language {language}: pass={metrics['pass_rate']:.1%}, "
            f"map={metrics['map_accuracy']:.1%}, "
            f"document@1={metrics['document_hit_at_1']:.1%}, "
            f"documents@10={metrics['required_documents_hit_at_10']:.1%}, "
            f"section@3={metrics['section_hit_at_3']:.1%}"
        )
    for case in report.cases:
        if not case.passed:
            failed_checks = ", ".join(name for name, passed in case.checks.items() if not passed)
            print(f"FAIL {case.id}: {failed_checks} — {case.query}")
    print(f"Report: {args.report}")

    if report.threshold_failures:
        for failure in report.threshold_failures:
            print(f"THRESHOLD {failure}", file=sys.stderr)
        if not args.no_fail:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
