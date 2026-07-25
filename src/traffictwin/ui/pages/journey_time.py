"""Journey-Time Lens page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.metrics.results import MetricStatus, MetricValue
from traffictwin.ui.charts import trip_duration_rows
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import metric_card, section_header
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import ServiceError, compare_runs_for_ui, validate_bundle_for_ui
from traffictwin.ui.tables import comparison_rows, table_column_config

DURATION_KEYS: dict[str, str] = {
    "Mean duration (s)": "trip.duration.mean_s",
    "P50 duration (s)": "trip.duration.p50_s",
    "P95 duration (s)": "trip.duration.p95_s",
    "Min duration (s)": "trip.duration.min_s",
    "Max duration (s)": "trip.duration.max_s",
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

    _render_cohort_coverage(metrics)

    section_header("Trip duration evidence")
    columns = st.columns(len(DURATION_KEYS))
    for column, (title, key) in zip(columns, DURATION_KEYS.items(), strict=True):
        with column:
            metric_card(title, metrics.get(key))

    rows = trip_duration_rows(analysis.validation.canonical)
    if rows:
        chart_rows = [
            {"trip_id": str(row["trip_id"]), "Duration (s)": _duration_value(row["duration_s"])}
            for row in rows
        ]
        st.bar_chart(
            chart_rows, x="trip_id", y="Duration (s)", x_label="Trip", y_label="Duration (s)"
        )
        st.caption(
            "Descriptive distribution of imported or synthetic per-trip durations. Incomplete or "
            "missing journeys are excluded from this chart and are never plotted as zero."
        )
    else:
        render_metric_unavailable(metrics.get("trip.duration.mean_s"), "trips.csv")

    _render_completion_and_exclusions(metrics)
    _render_comparison()


def _render_cohort_coverage(metrics: dict[str, MetricValue]) -> None:
    """Render a cohort-coverage KPI row with completion status."""

    incomplete = metrics.get("trip.incomplete.count")
    incomplete_value = incomplete.value if incomplete is not None else None
    has_incomplete = isinstance(incomplete_value, int | float) and incomplete_value > 0
    status = "partial" if has_incomplete else "available"
    with st.container(border=True):
        st.markdown(f"**Trip cohort completion:** {badge_markdown(status)}")
        columns = st.columns(3)
        columns[0].metric(
            "Total trips (count)", _count(metrics.get("trip.records.count")), border=True
        )
        columns[1].metric(
            "Completed trips (count)", _count(metrics.get("trip.completed.count")), border=True
        )
        columns[2].metric(
            "Incomplete trips (count)", _count(metrics.get("trip.incomplete.count")), border=True
        )
        st.caption(
            "Completion counts are the coverage denominators. Incomplete and missing journeys are "
            "kept as their own count and are never converted to a zero duration."
        )


def _render_completion_and_exclusions(metrics: dict[str, MetricValue]) -> None:
    """Show incomplete journeys and missing trip joins explicitly."""

    section_header("Completion and exclusions")
    incomplete = metrics.get("trip.incomplete.count")
    mean_duration = metrics.get("trip.duration.mean_s")
    incomplete_state = "available" if incomplete is not None else "unavailable"
    join_state = (
        "available"
        if mean_duration is not None and mean_duration.status is MetricStatus.AVAILABLE
        else "unavailable"
    )
    st.markdown(
        f"**Incomplete journeys:** {badge_markdown(incomplete_state)} · "
        f"**Trip-duration joins:** {badge_markdown(join_state)}"
    )
    if mean_duration is not None and mean_duration.status is not MetricStatus.AVAILABLE:
        st.caption(
            "Trip-duration joins are incomplete, so duration statistics stay unavailable rather "
            "than being computed over partial or zero-filled journeys."
        )
    st.markdown(
        "- Incomplete journeys are reported as a count and excluded from duration statistics.\n"
        "- Missing trip joins keep the affected durations unavailable, never zero.\n"
        "- Journey-time differences are descriptive and do not establish that any offloading "
        "policy caused a change in journey time."
    )


def _render_comparison() -> None:
    section_header("Baseline/variation journey-time comparison")
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
            st.dataframe(
                rows,
                width="stretch",
                hide_index=True,
                column_config=table_column_config(rows),
            )
            st.caption(
                "A baseline/variation difference is a description of two runs, not evidence "
                "that an offloading policy caused the difference in journey time."
            )
    else:
        st.info("Set baseline and variation bundle paths on the Compare page.")


def _count(metric: MetricValue | None) -> str:
    if metric is None or metric.status is not MetricStatus.AVAILABLE:
        return "Unavailable"
    if isinstance(metric.value, int | float) and not isinstance(metric.value, bool):
        return str(int(metric.value))
    return "Unavailable"


def _duration_value(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return float(str(value))
