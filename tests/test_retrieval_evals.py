import json
from pathlib import Path

import pytest

from scripts.retrieval_evals import EvaluationError, load_eval_suite

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


def test_chronicles_suite_has_six_cases_per_map() -> None:
    suite = load_eval_suite(ROOT / "evals" / "chronicles_queries.json")

    assert len(suite.cases) == 48
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
        "shangri_la": 6,
        "shi_no_numa": 6,
        "verruckt": 6,
    }


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
