from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.retrieval import SearchEngine, normalize_text


class EvaluationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    group_id: str | None
    language: str | None
    query: str
    active_map_id: str | None
    expected_map_id: str | None
    expected_document_paths: tuple[str, ...]
    required_document_paths: tuple[str, ...]
    expected_section_titles: tuple[str, ...]
    minimum_images: int | None
    expected_clarification: bool
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvalSuite:
    version: int
    description: str
    thresholds: dict[str, float]
    required_languages: tuple[str, ...]
    language_thresholds: dict[str, dict[str, float]]
    cases: tuple[EvalCase, ...]


@dataclass(frozen=True, slots=True)
class EvalCaseResult:
    id: str
    group_id: str | None
    language: str | None
    passed: bool
    latency_ms: float
    checks: dict[str, bool]
    query: str
    active_map_id: str | None
    expected_map_id: str | None
    actual_map_id: str | None
    expected_document_paths: tuple[str, ...]
    required_document_paths: tuple[str, ...]
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
    language_metrics: dict[str, dict[str, float]]
    thresholds: dict[str, float]
    language_thresholds: dict[str, dict[str, float]]
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
            "language_metrics": self.language_metrics,
            "thresholds": self.thresholds,
            "language_thresholds": self.language_thresholds,
            "threshold_failures": list(self.threshold_failures),
            "cases": [asdict(case) for case in self.cases],
        }


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvaluationError(f"{field_name} must be a list of strings.")
    return tuple(item.strip() for item in value if item.strip())


def _thresholds(value: Any, field_name: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise EvaluationError(f"{field_name} must be an object.")
    parsed: dict[str, float] = {}
    for name, raw_value in value.items():
        threshold = float(raw_value)
        if not 0 <= threshold <= 1:
            raise EvaluationError(f"Threshold {field_name}.{name} must be between 0 and 1.")
        parsed[str(name)] = threshold
    return parsed


def load_eval_suite(path: Path) -> EvalSuite:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationError(f"Could not load evaluation suite {path}: {error}") from error
    if not isinstance(payload, dict):
        raise EvaluationError("Evaluation suite root must be an object.")

    version = int(payload.get("version", 0))
    if version not in {1, 2}:
        raise EvaluationError(f"Unsupported evaluation suite version: {version}.")
    thresholds = _thresholds(payload.get("thresholds"), "thresholds")
    required_languages = _string_tuple(
        payload.get("required_languages"),
        "required_languages",
    )
    raw_language_thresholds = payload.get("language_thresholds", {})
    if not isinstance(raw_language_thresholds, dict):
        raise EvaluationError("language_thresholds must be an object.")
    language_thresholds = {
        str(language): _thresholds(values, f"language_thresholds.{language}")
        for language, values in raw_language_thresholds.items()
    }
    if version == 2 and not required_languages:
        raise EvaluationError("Version 2 suites require required_languages.")
    unknown_threshold_languages = set(language_thresholds) - set(required_languages)
    if unknown_threshold_languages:
        raise EvaluationError(
            "language_thresholds contains unsupported languages: "
            + ", ".join(sorted(unknown_threshold_languages))
        )

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
                group_id=(
                    str(raw_case.get("group_id", "")).strip()
                    or None
                ),
                language=(
                    str(raw_case.get("language", "")).strip()
                    or None
                ),
                query=query,
                active_map_id=str(active_map).strip() if active_map else None,
                expected_map_id=str(expected_map).strip() if expected_map else None,
                expected_document_paths=_string_tuple(
                    raw_case.get("expected_document_paths"),
                    f"{case_id}.expected_document_paths",
                ),
                required_document_paths=_string_tuple(
                    raw_case.get("required_document_paths"),
                    f"{case_id}.required_document_paths",
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

    if required_languages:
        languages_by_group: dict[str, set[str]] = defaultdict(set)
        signature_by_group: dict[str, tuple[Any, ...]] = {}
        for case in cases:
            if not case.group_id or not case.language:
                raise EvaluationError(
                    f"{case.id} requires group_id and language in a multilingual suite."
                )
            if case.language not in required_languages:
                raise EvaluationError(
                    f"{case.id} uses unsupported language {case.language}."
                )
            if case.language in languages_by_group[case.group_id]:
                raise EvaluationError(
                    f"Duplicate language {case.language} in group {case.group_id}."
                )
            languages_by_group[case.group_id].add(case.language)
            signature = (
                case.active_map_id,
                case.expected_map_id,
                case.expected_document_paths,
                case.required_document_paths,
                case.expected_section_titles,
                case.minimum_images,
                case.expected_clarification,
            )
            previous_signature = signature_by_group.setdefault(case.group_id, signature)
            if signature != previous_signature:
                raise EvaluationError(
                    f"Equivalent group {case.group_id} has inconsistent expectations."
                )
        expected_languages = set(required_languages)
        for group_id, languages in languages_by_group.items():
            if languages != expected_languages:
                missing = ", ".join(sorted(expected_languages - languages)) or "none"
                raise EvaluationError(
                    f"Equivalent group {group_id} is incomplete; missing: {missing}."
                )

    return EvalSuite(
        version=version,
        description=str(payload.get("description", "")).strip(),
        thresholds=thresholds,
        required_languages=required_languages,
        language_thresholds=language_thresholds,
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


def _summarize(case_results: list[EvalCaseResult]) -> dict[str, float]:
    def check_rate(name: str) -> float:
        relevant = [case for case in case_results if name in case.checks]
        return _rate(sum(case.checks[name] for case in relevant), len(relevant))

    latencies = [case.latency_ms for case in case_results]
    return {
        "pass_rate": _rate(sum(case.passed for case in case_results), len(case_results)),
        "map_accuracy": check_rate("map"),
        "document_hit_at_1": check_rate("document_at_1"),
        "required_documents_hit_at_10": check_rate("documents_at_10"),
        "section_hit_at_3": check_rate("section_at_3"),
        "image_hit_at_3": check_rate("images_at_3"),
        "clarification_accuracy": check_rate("clarification"),
        "median_latency_ms": _percentile(latencies, 0.5),
        "p95_latency_ms": _percentile(latencies, 0.95),
    }


def evaluate_suite(
    search_engine: SearchEngine,
    suite: EvalSuite,
    *,
    limit: int = 10,
) -> EvalReport:
    case_results: list[EvalCaseResult] = []
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

        if case.expected_map_id is not None:
            map_ok = result.active_map_id == case.expected_map_id
            checks["map"] = map_ok

        if case.expected_document_paths:
            document_ok = bool(actual_documents) and (
                actual_documents[0] in set(case.expected_document_paths)
            )
            checks["document_at_1"] = document_ok

        if case.required_document_paths:
            required_documents_ok = set(case.required_document_paths).issubset(
                set(actual_documents[:10])
            )
            checks["documents_at_10"] = required_documents_ok

        if case.expected_section_titles:
            expected_sections = {normalize_text(title) for title in case.expected_section_titles}
            section_ok = bool(expected_sections & top_three_sections)
            checks["section_at_3"] = section_ok

        if case.minimum_images is not None:
            image_ok = len(image_ids) >= case.minimum_images
            checks["images_at_3"] = image_ok

        case_results.append(
            EvalCaseResult(
                id=case.id,
                group_id=case.group_id,
                language=case.language,
                passed=all(checks.values()),
                latency_ms=latency_ms,
                checks=checks,
                query=case.query,
                active_map_id=case.active_map_id,
                expected_map_id=case.expected_map_id,
                actual_map_id=result.active_map_id,
                expected_document_paths=case.expected_document_paths,
                required_document_paths=case.required_document_paths,
                actual_document_paths=actual_documents[:5],
                expected_section_titles=case.expected_section_titles,
                actual_section_titles=actual_sections[:5],
                expected_minimum_images=case.minimum_images,
                actual_image_count_at_3=len(image_ids),
                expected_clarification=case.expected_clarification,
                actual_clarification=result.needs_clarification,
            )
        )

    passed = sum(case.passed for case in case_results)
    metrics = _summarize(case_results)
    grouped_results: dict[str, list[EvalCaseResult]] = defaultdict(list)
    language_results: dict[str, list[EvalCaseResult]] = defaultdict(list)
    for case_result in case_results:
        if case_result.group_id:
            grouped_results[case_result.group_id].append(case_result)
        if case_result.language:
            language_results[case_result.language].append(case_result)
    if grouped_results:
        metrics["equivalent_group_pass_rate"] = _rate(
            sum(all(case.passed for case in group) for group in grouped_results.values()),
            len(grouped_results),
        )
    language_metrics = {
        language: _summarize(results)
        for language, results in sorted(language_results.items())
    }
    threshold_failures = [
        f"{name}={metrics.get(name, 0):.4f} < {minimum:.4f}"
        for name, minimum in suite.thresholds.items()
        if metrics.get(name, 0) < minimum
    ]
    for language, thresholds in suite.language_thresholds.items():
        actual_metrics = language_metrics.get(language, {})
        threshold_failures.extend(
            f"language[{language}].{name}={actual_metrics.get(name, 0):.4f} < {minimum:.4f}"
            for name, minimum in thresholds.items()
            if actual_metrics.get(name, 0) < minimum
        )
    return EvalReport(
        total=len(case_results),
        passed=passed,
        metrics=metrics,
        language_metrics=language_metrics,
        thresholds=suite.thresholds,
        language_thresholds=suite.language_thresholds,
        threshold_failures=tuple(threshold_failures),
        cases=tuple(case_results),
    )
