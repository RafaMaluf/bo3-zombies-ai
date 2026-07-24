from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.retrieval import SearchEngine, normalize_text


class EvaluationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    query: str
    active_map_id: str | None
    expected_map_id: str | None
    expected_document_paths: tuple[str, ...]
    expected_section_titles: tuple[str, ...]
    minimum_images: int | None
    expected_clarification: bool
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvalSuite:
    version: int
    description: str
    thresholds: dict[str, float]
    cases: tuple[EvalCase, ...]


@dataclass(frozen=True, slots=True)
class EvalCaseResult:
    id: str
    passed: bool
    latency_ms: float
    checks: dict[str, bool]
    query: str
    active_map_id: str | None
    expected_map_id: str | None
    actual_map_id: str | None
    expected_document_paths: tuple[str, ...]
    actual_document_paths: tuple[str, ...]
    expected_section_titles: tuple[str, ...]
    actual_section_titles: tuple[str, ...]
    expected_minimum_images: int | None
    actual_image_count_at_3: int
    expected_clarification: bool
    actual_clarification: bool


@dataclass(frozen=True, slots=True)
class EvalReport:
    total: int
    passed: int
    metrics: dict[str, float]
    thresholds: dict[str, float]
    threshold_failures: tuple[str, ...]
    cases: tuple[EvalCaseResult, ...]

    @property
    def successful(self) -> bool:
        return not self.threshold_failures

    def as_json(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "threshold_failures": list(self.threshold_failures),
            "cases": [asdict(case) for case in self.cases],
        }


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvaluationError(f"{field_name} must be a list of strings.")
    return tuple(item.strip() for item in value if item.strip())


def load_eval_suite(path: Path) -> EvalSuite:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationError(f"Could not load evaluation suite {path}: {error}") from error
    if not isinstance(payload, dict):
        raise EvaluationError("Evaluation suite root must be an object.")

    version = int(payload.get("version", 0))
    if version != 1:
        raise EvaluationError(f"Unsupported evaluation suite version: {version}.")
    raw_thresholds = payload.get("thresholds", {})
    if not isinstance(raw_thresholds, dict):
        raise EvaluationError("thresholds must be an object.")
    thresholds: dict[str, float] = {}
    for name, raw_value in raw_thresholds.items():
        value = float(raw_value)
        if not 0 <= value <= 1:
            raise EvaluationError(f"Threshold {name} must be between 0 and 1.")
        thresholds[str(name)] = value

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvaluationError("cases must be a non-empty list.")

    cases: list[EvalCase] = []
    seen_ids: set[str] = set()
    for position, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            raise EvaluationError(f"cases[{position}] must be an object.")
        case_id = str(raw_case.get("id", "")).strip()
        query = str(raw_case.get("query", "")).strip()
        if not case_id or not query:
            raise EvaluationError(f"cases[{position}] requires id and query.")
        if case_id in seen_ids:
            raise EvaluationError(f"Duplicate case id: {case_id}.")
        seen_ids.add(case_id)

        raw_minimum_images = raw_case.get("minimum_images")
        minimum_images = None if raw_minimum_images is None else int(raw_minimum_images)
        if minimum_images is not None and minimum_images < 0:
            raise EvaluationError(f"minimum_images cannot be negative in {case_id}.")
        active_map = raw_case.get("active_map_id")
        expected_map = raw_case.get("expected_map_id")
        cases.append(
            EvalCase(
                id=case_id,
                query=query,
                active_map_id=str(active_map).strip() if active_map else None,
                expected_map_id=str(expected_map).strip() if expected_map else None,
                expected_document_paths=_string_tuple(
                    raw_case.get("expected_document_paths"),
                    f"{case_id}.expected_document_paths",
                ),
                expected_section_titles=_string_tuple(
                    raw_case.get("expected_section_titles"),
                    f"{case_id}.expected_section_titles",
                ),
                minimum_images=minimum_images,
                expected_clarification=bool(raw_case.get("expected_clarification", False)),
                tags=_string_tuple(raw_case.get("tags"), f"{case_id}.tags"),
            )
        )

    return EvalSuite(
        version=version,
        description=str(payload.get("description", "")).strip(),
        thresholds=thresholds,
        cases=tuple(cases),
    )


def _rate(hits: int, total: int) -> float:
    return round(hits / total, 4) if total else 1.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[index], 3)


def evaluate_suite(
    search_engine: SearchEngine,
    suite: EvalSuite,
    *,
    limit: int = 10,
) -> EvalReport:
    case_results: list[EvalCaseResult] = []
    map_hits = 0
    map_total = 0
    document_hits = 0
    document_total = 0
    section_hits = 0
    section_total = 0
    image_hits = 0
    image_total = 0
    clarification_hits = 0

    for case in suite.cases:
        started = time.perf_counter()
        result = search_engine.search(
            case.query,
            active_map_id=case.active_map_id,
            limit=limit,
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        top_three = result.chunks[:3]
        actual_documents = tuple(item.chunk.path for item in result.chunks)
        actual_sections = tuple(item.chunk.section_title for item in result.chunks)
        top_three_sections = {normalize_text(item.chunk.section_title) for item in top_three}
        image_ids = {image_id for item in top_three for image_id in item.chunk.image_ids}

        checks: dict[str, bool] = {}
        clarification_ok = result.needs_clarification == case.expected_clarification
        checks["clarification"] = clarification_ok
        clarification_hits += int(clarification_ok)

        if case.expected_map_id is not None:
            map_total += 1
            map_ok = result.active_map_id == case.expected_map_id
            checks["map"] = map_ok
            map_hits += int(map_ok)

        if case.expected_document_paths:
            document_total += 1
            document_ok = bool(actual_documents) and (
                actual_documents[0] in set(case.expected_document_paths)
            )
            checks["document_at_1"] = document_ok
            document_hits += int(document_ok)

        if case.expected_section_titles:
            section_total += 1
            expected_sections = {normalize_text(title) for title in case.expected_section_titles}
            section_ok = bool(expected_sections & top_three_sections)
            checks["section_at_3"] = section_ok
            section_hits += int(section_ok)

        if case.minimum_images is not None:
            image_total += 1
            image_ok = len(image_ids) >= case.minimum_images
            checks["images_at_3"] = image_ok
            image_hits += int(image_ok)

        case_results.append(
            EvalCaseResult(
                id=case.id,
                passed=all(checks.values()),
                latency_ms=latency_ms,
                checks=checks,
                query=case.query,
                active_map_id=case.active_map_id,
                expected_map_id=case.expected_map_id,
                actual_map_id=result.active_map_id,
                expected_document_paths=case.expected_document_paths,
                actual_document_paths=actual_documents[:5],
                expected_section_titles=case.expected_section_titles,
                actual_section_titles=actual_sections[:5],
                expected_minimum_images=case.minimum_images,
                actual_image_count_at_3=len(image_ids),
                expected_clarification=case.expected_clarification,
                actual_clarification=result.needs_clarification,
            )
        )

    latencies = [case.latency_ms for case in case_results]
    passed = sum(case.passed for case in case_results)
    metrics = {
        "pass_rate": _rate(passed, len(case_results)),
        "map_accuracy": _rate(map_hits, map_total),
        "document_hit_at_1": _rate(document_hits, document_total),
        "section_hit_at_3": _rate(section_hits, section_total),
        "image_hit_at_3": _rate(image_hits, image_total),
        "clarification_accuracy": _rate(clarification_hits, len(case_results)),
        "median_latency_ms": _percentile(latencies, 0.5),
        "p95_latency_ms": _percentile(latencies, 0.95),
    }
    threshold_failures = tuple(
        f"{name}={metrics.get(name, 0):.4f} < {minimum:.4f}"
        for name, minimum in suite.thresholds.items()
        if metrics.get(name, 0) < minimum
    )
    return EvalReport(
        total=len(case_results),
        passed=passed,
        metrics=metrics,
        thresholds=suite.thresholds,
        threshold_failures=threshold_failures,
        cases=tuple(case_results),
    )
