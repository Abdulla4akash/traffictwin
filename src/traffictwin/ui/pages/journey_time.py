"""Journey-Time Lens page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.metrics.results import MetricStatus
from traffictwin.ui.charts import bar_figure, trip_duration_rows
from traffictwin.ui.components.cards import metric_card
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import ServiceError, compare_runs_for_ui, validate_bundle_for_ui
from traffictwin.ui.tables import comparison_rows

TRIP_KEYS = {
    "Total trips": "trip.records.count",
    "Completed trips": "trip.completed.count",
    "Incomplete trips": "trip.incomplete.count",
    "Mean duration": "trip.duration.mean_s",
    "P50 duration": "trip.duration.p50_s",
    "P95 duration": "trip.duration.p95_s",
    "Min duration": "trip.duration.min_s",
    "Max duration": "trip.duration.max_s",
}


def render() -> None:
    """Render Journey-Time Lens."""

    st.title("Journey-Time Lens")
    analysis = load_selected_analysis()
    if analysis is None or analysis.metrics is None:
        return
    render_source_caption(analysis)
    st.caption(
        "Imported trip duration and simulated journey duration are not real Manchester predictions."
    )
    metrics = analysis.metrics.by_key()

    if metrics["trip.records.count"].status is not MetricStatus.AVAILABLE:
        render_metric_unavailable(metrics.get("trip.records.count"), "trips.csv")
        return

    for row_start in range(0, len(TRIP_KEYS), 4):
        cols = st.columns(4)
        for col, (title, key) in zip(
            cols,
            list(TRIP_KEYS.items())[row_start : row_start + 4],
            strict=False,
        ):
            with col:
                metric_card(title, metrics.get(key))

    rows = trip_duration_rows(analysis.validation.canonical)
    if rows:
        st.plotly_chart(
            bar_figure(
                [str(row["trip_id"]) for row in rows],
                [_duration_value(row["duration_s"]) for row in rows],
                title="Imported trip duration",
                y_title="Duration (s)",
            ),
            width="stretch",
        )
    else:
        render_metric_unavailable(metrics.get("trip.duration.mean_s"), "trips.csv")

    st.subheader("Baseline/Variation Journey-Time Comparison")
    baseline_path = Path(
        str(st.session_state.get("selected_baseline_run", "tests/fixtures/bundles/baseline_valid"))
    )
    variation_path = Path(
        str(
            st.session_state.get("selected_variation_run", "tests/fixtures/bundles/variation_valid")
        )
    )
    if baseline_path.exists() and variation_path.exists():
        report = compare_runs_for_ui(
            validate_bundle_for_ui(baseline_path),
            validate_bundle_for_ui(variation_path),
        )
        if isinstance(report, ServiceError):
            st.info(report.message)
        else:
            rows = [
                row for row in comparison_rows(report) if str(row["metric_key"]).startswith("trip.")
            ]
            st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Set baseline and variation bundle paths on the Compare page.")


def _duration_value(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return float(str(value))
