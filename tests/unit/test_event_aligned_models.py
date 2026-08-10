"""Unit tests for event-aligned typed models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from traffictwin.event_aligned.models import (
    CoverageState,
    EventAlignedPhase,
    EventAlignedWindowSpec,
    EventAnchor,
    EventAnchorKind,
)


def test_event_anchor_requires_timezone_aware() -> None:
    naive = datetime(2026, 7, 17, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        EventAnchor(
            kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
            anchor_time_utc=naive,  # type: ignore[arg-type]
            source_label="Authored — Manual timestamp",
        )


def test_event_anchor_normalises_to_utc() -> None:
    # 13:00+01:00 == 12:00Z
    # Use +01:00 explicit
    from datetime import timezone

    plus_one = timezone(timedelta(hours=1))
    dt_plus = datetime(2026, 7, 17, 13, 0, 0, tzinfo=plus_one)
    anchor = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=dt_plus,
        source_label="Authored — Manual timestamp",
    )
    assert anchor.anchor_time_utc.tzinfo == UTC
    assert anchor.anchor_time_utc.hour == 12


def test_event_anchor_rejects_observed_label() -> None:
    with pytest.raises(ValueError, match="must not be labelled observed"):
        EventAnchor(
            kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
            anchor_time_utc=datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC),
            source_label="Observed incident",
        )


def test_event_anchor_kinds_are_all_authored() -> None:
    for kind in EventAnchorKind:
        assert kind.is_authored is True
        assert "Authored" in kind.authored_label
        assert "Observed" not in kind.authored_label
        assert "observed" not in kind.authored_label.lower() or "not observed" in kind.authored_label.lower()  # noqa: E501
        # Direct label check
        if kind == EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP:
            assert kind.authored_label == "Authored — Manual timestamp"
        elif kind == EventAnchorKind.AUTHORED_INCIDENT:
            assert kind.authored_label == "Authored — Incident"
        elif kind == EventAnchorKind.BUNDLE_DECLARED_EVENT:
            assert kind.authored_label == "Authored — Bundle declared event"


def test_window_spec_preview_exact_half_open_windows() -> None:
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
    )
    anchor = datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)
    preview = spec.preview_windows(anchor)
    assert preview["pre"][0] == datetime(2026, 7, 17, 11, 59, 50, tzinfo=UTC)
    assert preview["pre"][1] == datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)
    assert preview["event"][0] == datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)
    assert preview["event"][1] == datetime(2026, 7, 17, 12, 0, 10, tzinfo=UTC)
    assert preview["post"][0] == datetime(2026, 7, 17, 12, 0, 10, tzinfo=UTC)
    assert preview["post"][1] == datetime(2026, 7, 17, 12, 0, 20, tzinfo=UTC)
    # Check half-open semantics: pre end == event start, event end == post start
    assert preview["pre"][1] == preview["event"][0]
    assert preview["event"][1] == preview["post"][0]
    # Total bins
    assert spec.total_bins() == 6


def test_window_spec_rejects_zero_bin_width() -> None:
    with pytest.raises(ValueError):
        EventAlignedWindowSpec(
            pre_duration_s=10,
            event_duration_s=10,
            post_duration_s=10,
            bin_width_s=0,
            metric_key="task.completion.rate",
            metric_version="1.0",
            metric_unit="ratio",
        )


def test_phase_enum_values() -> None:
    assert EventAlignedPhase.PRE.value == "pre"
    assert EventAlignedPhase.EVENT.value == "event"
    assert EventAlignedPhase.POST.value == "post"


def test_coverage_state_values() -> None:
    assert CoverageState.COMPLETE.value == "complete"
    assert CoverageState.EMPTY.value == "empty"
    assert CoverageState.PARTIAL.value == "partial"
    # EXCLUDED removed: exclusions are via ExcludedRun, not CoverageState
