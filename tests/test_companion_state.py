from pathlib import Path

import pytest

from app.companion_models import CompanionCatalog, MatchState, Objective, ProgressChange
from app.companion_state import build_catalog, next_objective, transition, validate_state
from app.knowledge_base import KnowledgeBase


def catalog():
    return CompanionCatalog(
        map_id="map",
        map_name="Map",
        document_path="ee.md",
        version="v1",
        objectives=[
            Objective(
                id=str(i),
                title=f"Goal {i}",
                source_ids=[str(i)],
                requires=["1"] if i == 4 else [],
                implies=["1"] if i == 4 else [],
            )
            for i in range(1, 7)
        ],
    )


def state(**kwargs):
    return MatchState(map_id="map", catalog_version="v1", **kwargs)


def change(**kwargs):
    return ProgressChange(intent="progress", **kwargs)


def test_non_linear_completions_do_not_complete_earlier_indices():
    result = transition(state(), catalog(), change(completed=["2", "3", "5", "6"]))
    assert result.statuses == {i: "complete" for i in ["2", "3", "5", "6"]}
    assert result.focus == "1"
    assert result.statuses.get("4", "unknown") == "unknown"


def test_from_start_and_explicit_completion_choose_next_ready_objective():
    result = transition(state(), catalog(), change(from_start=True))
    assert result.focus == "1"
    assert set(result.statuses.values()) == {"pending"}
    result = transition(result, catalog(), change(completed=["1", "2", "3"]))
    assert result.focus == "4"


def test_consulting_advanced_objective_does_not_complete_prerequisites():
    result = transition(state(), catalog(), ProgressChange(intent="consult", focus="4"))
    assert result.focus == "4"
    assert not result.statuses


def test_completion_proves_only_explicit_unconditional_dependencies():
    result = transition(state(), catalog(), change(completed=["4"]))
    assert result.statuses == {"4": "complete", "1": "complete"}
    assert result.statuses.get("2") is None


def test_requiring_a_piece_does_not_prove_a_whole_grouped_recipe_complete():
    c = catalog()
    c.objectives[3].implies = []
    result = transition(state(), c, change(completed=["4"]))
    assert result.statuses["4"] == "complete"
    assert result.statuses.get("1", "unknown") == "unknown"


def test_question_before_position_does_not_start_or_finish_a_match():
    result = transition(state(), catalog(), ProgressChange(intent="question"))
    assert result.stage == "position"
    assert result.focus is None
    assert not result.statuses


def test_correction_requires_confirmation_before_affecting_completed_dependents():
    initial = transition(state(), catalog(), change(completed=["1", "4", "5"]))
    correction = change(pending=["1"])
    proposed = transition(initial, catalog(), correction)
    assert proposed.confirmation == correction
    assert proposed.statuses == initial.statuses
    final = transition(proposed, catalog(), proposed.confirmation, confirmed=True)
    assert final.statuses["1"] == final.statuses["4"] == "pending"
    assert final.statuses["5"] == "complete"


def test_partial_progress_corrects_a_complete_objective():
    initial = transition(state(), catalog(), change(completed=["2"]))
    result = transition(initial, catalog(), change(partial={"2": "Missing one piece"}))
    assert result.statuses["2"] == "pending"
    assert result.partial["2"] == "Missing one piece"


def test_explicit_partial_detail_wins_over_inferred_completion():
    result = transition(state(), catalog(), change(completed=["4"], partial={"1": "Missing piece"}))
    assert result.statuses["4"] == "complete"
    assert result.statuses["1"] == "pending"


def test_lateral_help_returns_to_the_original_objective():
    initial = state(focus="4", stage="active")
    help_state = transition(initial, catalog(), ProgressChange(intent="help", focus="2"))
    assert help_state.return_to == ["4"]
    result = transition(help_state, catalog(), change(completed=["2"]))
    assert result.focus == "4"
    assert result.return_to == []


@pytest.mark.parametrize(
    "update",
    [
        ProgressChange(completed=["1"]),
        ProgressChange(intent="consult", pending=["2"]),
        change(completed=["outside"]),
        change(applicability={"1": False}),
        change(completed=["1"], pending=["1"]),
    ],
)
def test_invalid_or_ungrounded_state_changes_are_rejected(update):
    with pytest.raises(ValueError):
        transition(state(), catalog(), update)


def test_catalog_mismatch_is_explicit_and_never_discards_saved_state():
    saved = state()
    saved.catalog_version = "old"
    with pytest.raises(ValueError, match="mudou"):
        validate_state(saved, catalog())
    assert saved.catalog_version == "old"


def test_all_complete_and_non_applicable_objectives_finish_match():
    c = catalog()
    c.objectives[-1].condition = "Only with four players"
    result = transition(
        state(), c, change(completed=["1", "2", "3", "4", "5"], applicability={"6": False})
    )
    assert result.stage == "finished"
    assert next_objective(result, c) is None


def test_state_roundtrip_keeps_progress_without_generated_text():
    initial = transition(state(player_count=2), catalog(), change(completed=["2", "5"]))
    restored = MatchState.model_validate_json(initial.model_dump_json())
    assert restored == initial
    assert "answer" not in restored.model_dump()


def test_player_correction_preserves_completed_actions_and_revisits_route_choices():
    c = catalog()
    c.objectives[-1].condition = "Depends on player count"
    saved = state(player_count=1, statuses={"2": "complete"}, applicability={"6": False})
    result = transition(saved, c, change(player_count=2))
    assert result.player_count == 2
    assert result.statuses["2"] == "complete"
    assert not result.applicability
    assert result.stage == "position"


def test_reviewed_catalogs_have_stable_ids_dependencies_and_sources_on_all_quest_maps():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    count = 0
    for map_id in kb.maps:
        if not any(c.map_id == map_id and c.category == "main_ee" for c in kb.chunks.values()):
            continue
        c = build_catalog(kb, map_id)
        same = build_catalog(kb, map_id, "en")
        assert c.version == same.version
        ids = {o.id for o in c.objectives}
        assert len(ids) == len(c.objectives)
        assert all(set(o.requires) <= ids and o.source_ids for o in c.objectives)
        assert any(o.main for o in c.objectives)
        count += 1
    assert count == 10
