from __future__ import annotations

import pytest
import streamlit as st

from traffictwin.ui.guided import (
    DemoTrack,
    GuidedCompletionMode,
    GuidedDemoProgress,
    start_guided_progress,
    steps_for_track,
)
from traffictwin.ui.guided_runtime import (
    GUIDED_LEGACY_PENDING_PAGE_KEY,
    complete_guided_action,
    consume_guided_legacy_navigation,
    load_guided_progress,
    start_guided_workflow,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import V07_PENDING_PAGE_KEY, redirect_pending_v07_page
from traffictwin.ui.navigation_v07 import page_script_for


def test_guided_tracks_define_exact_action_and_review_completion() -> None:
    standalone = steps_for_track(DemoTrack.STANDALONE)
    tos = steps_for_track(DemoTrack.TOS)

    assert standalone[0].completion_mode is GuidedCompletionMode.ACTION
    assert standalone[0].completion_action == "register_experiment_plan"
    assert standalone[-1].completion_mode is GuidedCompletionMode.ACTION
    assert standalone[-1].completion_action == "regenerate_report"
    assert all(step.instruction for step in standalone + tos)
    assert all(
        step.completion_action is None
        for step in standalone + tos
        if step.completion_mode is GuidedCompletionMode.REVIEW
    )


def test_guided_progress_reconciles_completed_skipped_and_previous() -> None:
    progress = start_guided_progress(DemoTrack.STANDALONE)
    after_plan = progress.complete_current()
    after_skip = after_plan.skip_current()
    previous = after_skip.previous()

    assert after_plan.step_index == 1
    assert after_plan.completed_step_keys == ("plan",)
    assert after_skip.step_index == 2
    assert after_skip.skipped_step_keys == ("validate",)
    assert previous.step_index == 1
    assert previous.completed_step_keys == ("plan",)
    assert previous.skipped_step_keys == ("validate",)


def test_guided_progress_finishes_only_after_final_stage_outcome() -> None:
    progress = start_guided_progress(DemoTrack.STANDALONE)
    for _ in range(len(steps_for_track(DemoTrack.STANDALONE)) - 1):
        progress = progress.complete_current()

    finished = progress.complete_current()

    assert finished.finished is True
    assert finished.active is False
    assert finished.completed_step_keys == tuple(
        step.key for step in steps_for_track(DemoTrack.STANDALONE)
    )
    assert finished.current_step.key == "report"


@pytest.mark.parametrize(
    "payload",
    [
        {"track": DemoTrack.STANDALONE, "step_index": 99},
        {
            "track": DemoTrack.STANDALONE,
            "completed_step_keys": ["unknown"],
        },
        {
            "track": DemoTrack.STANDALONE,
            "completed_step_keys": ["plan"],
            "skipped_step_keys": ["plan"],
        },
        {
            "track": DemoTrack.STANDALONE,
            "active": True,
            "finished": True,
            "step_index": 7,
        },
        {
            "track": DemoTrack.STANDALONE,
            "step_index": 2,
            "completed_step_keys": ["plan"],
        },
    ],
)
def test_guided_progress_rejects_inconsistent_persisted_state(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        GuidedDemoProgress.model_validate(payload)


def test_loading_invalid_progress_clears_the_session_value() -> None:
    state: dict[str, object] = {"guided_demo_progress": "not-a-progress-record"}

    assert load_guided_progress(state) is None
    assert "guided_demo_progress" not in state


def test_action_completion_switches_to_next_registered_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {"_v07_navigation_active": True}
    switched: list[str] = []
    reruns: list[bool] = []
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "switch_page", switched.append)
    monkeypatch.setattr(st, "rerun", lambda: reruns.append(True))
    start_guided_workflow(DemoTrack.STANDALONE)

    assert complete_guided_action(UiPage.REPORTS, "regenerate_report") is False
    assert complete_guided_action(
        UiPage.EXPERIMENT_PLANNER,
        "register_experiment_plan",
    )

    progress = load_guided_progress(state)
    assert progress is not None
    assert progress.completed_step_keys == ("plan",)
    assert progress.current_step.key == "validate"
    assert reruns == [True]
    assert state[V07_PENDING_PAGE_KEY] == UiPage.BUNDLE_IMPORT.value

    redirect_pending_v07_page(UiPage.EXPERIMENT_PLANNER)

    assert switched == [page_script_for(UiPage.BUNDLE_IMPORT)]
    assert V07_PENDING_PAGE_KEY not in state
    assert GUIDED_LEGACY_PENDING_PAGE_KEY not in state


def test_action_completion_routes_legacy_navigation_before_radio_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {"_v07_navigation_active": False}
    reruns: list[bool] = []
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "rerun", lambda: reruns.append(True))
    start_guided_workflow(DemoTrack.STANDALONE)

    assert complete_guided_action(
        UiPage.EXPERIMENT_PLANNER,
        "register_experiment_plan",
    )
    assert state[GUIDED_LEGACY_PENDING_PAGE_KEY] == UiPage.BUNDLE_IMPORT.value

    consume_guided_legacy_navigation()

    assert reruns == [True]
    assert state["active_page"] == UiPage.BUNDLE_IMPORT.value
    assert GUIDED_LEGACY_PENDING_PAGE_KEY not in state
