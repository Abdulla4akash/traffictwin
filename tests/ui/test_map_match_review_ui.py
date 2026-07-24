"""Thin UI tests for the synthetic MAN-09 map-match review demonstration."""

from __future__ import annotations

from importlib import import_module

import pytest

from traffictwin.ui.map_match_review import (
    REJECT_ALL_SENTINEL,
    eligible_candidates_by_point,
    synthetic_map_match_demo_report,
)


def test_review_demo_renders_blockers_and_complete_candidate_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=25)

    assert not app.exception
    warnings = "\n".join(str(item.value) for item in app.warning)
    assert "Synthetic demonstration only" in warnings
    assert "MANCHESTER_NETWORK_LICENCE_UNAPPROVED" in warnings
    captions = "\n".join(str(item.value) for item in app.caption)
    assert "complete Cartesian reconciliation" in captions
    # One explicit decision control per demonstration observation.
    review_boxes = [
        item for item in app.selectbox if str(item.key).startswith("manchester_ops_map_match_")
    ]
    assert len(review_boxes) == 3


def test_review_demo_records_explicit_decisions_and_stays_synthetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    report = synthetic_map_match_demo_report()
    eligible = eligible_candidates_by_point(report)
    selected = eligible["synthetic:obs-clear"][0].fingerprint()

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=25)
    assert not app.exception
    app.selectbox(key="manchester_ops_map_match_synthetic:obs-clear").set_value(selected)
    app.selectbox(key="manchester_ops_map_match_synthetic:obs-ambiguous").set_value(
        REJECT_ALL_SENTINEL
    )
    app.selectbox(key="manchester_ops_map_match_synthetic:obs-distant").set_value(
        REJECT_ALL_SENTINEL
    )
    submit = next(button for button in app.button if button.label == "Record synthetic review")
    submit.click()
    app = app.run(timeout=25)

    assert not app.exception
    successes = "\n".join(str(item.value) for item in app.success)
    assert "1 selected, 2 rejected across 3 observations" in successes
    captions = "\n".join(str(item.value) for item in app.caption)
    assert "accepts no real map match" in captions
