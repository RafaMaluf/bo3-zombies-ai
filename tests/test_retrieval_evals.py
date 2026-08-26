import json
from pathlib import Path

import pytest

from app.domain import RetrievalResult
from scripts.retrieval_evals import EvaluationError, evaluate_suite, load_eval_suite

ROOT = Path(__file__).resolve().parent.parent


def test_original_maps_suite_has_fifteen_cases_per_map() -> None:
    suite = load_eval_suite(ROOT / "evals" / "queries.json")

    assert len(suite.cases) == 90
    cases_per_map: dict[str, int] = {}
    for case in suite.cases:
        assert case.expected_map_id
        cases_per_map[case.expected_map_id] = cases_per_map.get(case.expected_map_id, 0) + 1

    assert cases_per_map == {
        "der_eisendrache": 15,
        "gorod_krovi": 15,
        "revelations": 15,
        "shadows_of_evil": 15,
        "the_giant": 15,
        "zetsubou_no_shima": 15,
    }


def test_chronicles_suite_covers_every_map() -> None:
    suite = load_eval_suite(ROOT / "evals" / "chronicles_queries.json")

    assert len(suite.cases) == 49
    cases_per_map: dict[str, int] = {}
    for case in suite.cases:
        assert case.expected_map_id
        cases_per_map[case.expected_map_id] = cases_per_map.get(case.expected_map_id, 0) + 1

    assert cases_per_map == {
        "ascension": 6,
        "kino_der_toten": 6,
        "moon": 6,
        "nacht_der_untoten": 6,
        "origins": 6,
        "shangri_la": 7,
        "shi_no_numa": 6,
        "verruckt": 6,
    }


def test_multilingual_suite_has_complete_equivalent_groups() -> None:
    suite = load_eval_suite(ROOT / "evals" / "multilingual_queries.json")

    assert suite.version == 2
    assert suite.required_languages == ("pt-BR", "en", "fr")
    assert len(suite.cases) == 27

    languages_per_group: dict[str, set[str]] = {}
    for case in suite.cases:
        assert case.group_id
        assert case.language
        languages_per_group.setdefault(case.group_id, set()).add(case.language)

    assert len(languages_per_group) == 9
    assert all(
        languages == {"pt-BR", "en", "fr"}
        for languages in languages_per_group.values()
    )


def test_eval_suite_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "version": 1,
                "cases": [
                    {"id": "duplicate", "query": "First"},
                    {"id": "duplicate", "query": "Second"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationError, match="Duplicate case id"):
        load_eval_suite(suite_path)


def test_multilingual_suite_rejects_incomplete_group(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "version": 2,
                "required_languages": ["pt-BR", "en", "fr"],
                "cases": [
                    {
                        "id": "pap-pt",
                        "group_id": "pap",
                        "language": "pt-BR",
                        "query": "Como libero o Pack-a-Punch?",
                    },
                    {
                        "id": "pap-en",
                        "group_id": "pap",
                        "language": "en",
                        "query": "How do I unlock Pack-a-Punch?",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationError, match="incomplete; missing: fr"):
        load_eval_suite(suite_path)


def test_multilingual_suite_rejects_inconsistent_expectations(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "version": 2,
                "required_languages": ["pt-BR", "en"],
                "cases": [
                    {
                        "id": "quest-pt",
                        "group_id": "quest",
                        "language": "pt-BR",
                        "query": "Como faco a missao?",
                        "expected_map_id": "origins",
                    },
                    {
                        "id": "quest-en",
                        "group_id": "quest",
                        "language": "en",
                        "query": "How do I complete the quest?",
                        "expected_map_id": "moon",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationError, match="inconsistent expectations"):
        load_eval_suite(suite_path)


def test_multilingual_report_enforces_each_language_threshold(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "version": 2,
                "required_languages": ["pt-BR", "en"],
                "language_thresholds": {
                    "pt-BR": {"pass_rate": 1.0},
                    "en": {"pass_rate": 1.0},
                },
                "cases": [
                    {
                        "id": "pap-pt",
                        "group_id": "pap",
                        "language": "pt-BR",
                        "query": "pt",
                        "expected_clarification": True,
                    },
                    {
                        "id": "pap-en",
                        "group_id": "pap",
                        "language": "en",
                        "query": "en",
                        "expected_clarification": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    class StubSearchEngine:
        def search(
            self,
            query: str,
            active_map_id: str | None,
            limit: int,
        ) -> RetrievalResult:
            del active_map_id, limit
            return RetrievalResult(
                chunks=(),
                active_map_id=None,
                explicit_map_ids=(),
                needs_clarification=query == "pt",
                clarification_question="",
                suggested_map_ids=(),
            )

    report = evaluate_suite(StubSearchEngine(), load_eval_suite(suite_path))  # type: ignore[arg-type]

    assert report.language_metrics["pt-BR"]["pass_rate"] == 1.0
    assert report.language_metrics["en"]["pass_rate"] == 0.0
    assert report.threshold_failures == (
        "language[en].pass_rate=0.0000 < 1.0000",
    )
