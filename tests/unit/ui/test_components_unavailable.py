"""Tests for the unavailable-evidence panels."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _panel_text(at: AppTest) -> str:
    parts = [str(block.value) for block in at.markdown]
    parts.extend(str(caption.value) for caption in at.caption)
    return "\n".join(parts)


def _render_panel_with_evidence() -> None:
    from traffictwin.ui.components.unavailable import render_unavailable_panel

    render_unavailable_panel(
        "Energy evidence unavailable",
        ["per-task energy table"],
        ["REQUIRED_TABLE_UNAVAILABLE", "NO_VALID_ROWS"],
    )


def _render_panel_with_defaults() -> None:
    from traffictwin.ui.components.unavailable import render_unavailable_panel

    render_unavailable_panel("Metric unavailable", [], [])


def _render_metric_none() -> None:
    from traffictwin.ui.components.unavailable import render_metric_unavailable

    render_metric_unavailable(None, "trips.csv")


def _render_metric_value() -> None:
    from datetime import UTC, datetime

    from traffictwin.metrics.results import MetricStatus, MetricValue, UnavailableReason
    from traffictwin.ui.components.unavailable import render_metric_unavailable

    metric = MetricValue(
        metric_key="task.energy.per_completed_j",
        status=MetricStatus.UNAVAILABLE,
        unit="J",
        scope="run",
        missing_evidence=["per-task energy table"],
        reason_codes=[UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
        implementation_version="test",
        run_id="run-1",
        experiment_id=None,
        seed_id="seed-1",
        algorithm="baseline",
        random_seed=7,
        synthetic=True,
        computed_at=datetime(2026, 7, 24, tzinfo=UTC),
    )
    render_metric_unavailable(metric, "energy.csv")


def test_panel_keeps_title_evidence_and_exact_reason_codes() -> None:
    at = AppTest.from_function(_render_panel_with_evidence)
    at.run()
    assert not at.exception
    text = _panel_text(at)
    assert "Energy evidence unavailable" in text
    assert "per-task energy table" in text
    assert "REQUIRED_TABLE_UNAVAILABLE" in text
    assert "NO_VALID_ROWS" in text
    # The panel explains itself and never substitutes a zero value.
    assert "unavailable" in text.lower()
    assert "zero" in text.lower()


def test_panel_preserves_default_missing_evidence_and_reason_code() -> None:
    at = AppTest.from_function(_render_panel_with_defaults)
    at.run()
    assert not at.exception
    text = _panel_text(at)
    assert "not declared or not valid" in text
    assert "REQUIRED_TABLE_UNAVAILABLE" in text


def test_panel_no_longer_renders_a_raw_dictionary_dump() -> None:
    at = AppTest.from_function(_render_panel_with_evidence)
    at.run()
    assert not at.exception
    assert len(at.json) == 0
    text = _panel_text(at)
    assert "missing_evidence" not in text
    assert "{" not in text


def test_metric_unavailable_without_metric_uses_not_applicable_code() -> None:
    at = AppTest.from_function(_render_metric_none)
    at.run()
    assert not at.exception
    text = _panel_text(at)
    assert "Metric unavailable" in text
    assert "trips.csv" in text
    assert "METRIC_NOT_APPLICABLE" in text


def test_metric_unavailable_with_metric_keeps_key_and_reasons() -> None:
    at = AppTest.from_function(_render_metric_value)
    at.run()
    assert not at.exception
    text = _panel_text(at)
    assert "task.energy.per_completed_j" in text
    assert "per-task energy table" in text
    assert "REQUIRED_TABLE_UNAVAILABLE" in text
