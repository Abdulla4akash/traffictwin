from __future__ import annotations

from tests.helpers import bundle_result

from traffictwin.ui.state import (
    ensure_session_state,
    replay_clock_from_tables,
    replay_window_counts,
)


def test_session_state_defaults_are_populated() -> None:
    state: dict[str, object] = {}

    ensure_session_state(state)

    assert state["selected_bundle_path"] == "tests/fixtures/bundles/baseline_valid"
    assert state["data_mode_label"] == "SYNTHETIC"


def test_replay_clock_bounds_and_window_counts() -> None:
    tables = bundle_result("baseline_valid").canonical
    clock = replay_clock_from_tables(tables)

    assert clock.min_timestamp_s == 0
    assert clock.max_timestamp_s == 690
    assert clock.step(10).current_timestamp_s == 10
    assert clock.reset().current_timestamp_s == 0
    assert replay_window_counts(tables, 10)["task_arrivals"] == 3
