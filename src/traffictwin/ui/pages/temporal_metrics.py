"""Fixed-window metric exploration over a validated selected bundle."""

from __future__ import annotations

import streamlit as st

from traffictwin.diagnostics.temporal import TemporalDiagnosticAnalysis
from traffictwin.metrics.results import MetricStatus
from traffictwin.metrics.windowed import WindowDisposition, WindowedMetricSeries
from traffictwin.ui.charts import line_figure
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import (
    ServiceError,
    compute_windowed_metrics_for_ui,
    evaluate_temporal_diagnostics_for_ui,
)
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def render() -> None:
    """Render thin controls and typed fixed-window metric output."""

    st.title("Temporal Metrics")
    analysis = load_selected_analysis()
    if analysis is None:
        return
    render_source_caption(analysis)
    st.caption(
        "Windows use [start, end). Tasks are assigned by arrival, trips by departure, and "
        "state/traffic/incident records by timestamp. Coverage is requested-range overlap, not "
        "inferred sensor completeness."
    )

    controls = st.columns(3)
    width_s = float(
        controls[0].number_input("Window width (seconds)", min_value=0.001, value=60.0, step=10.0)
    )
    origin_s = float(controls[1].number_input("Alignment origin (seconds)", value=0.0, step=10.0))
    partial_policy = controls[2].selectbox("Partial edge windows", ["include", "exclude"], index=0)
    explicit_range = st.toggle("Use an explicit analysis range", value=False)
    start_s: float | None = None
    end_s: float | None = None
    if explicit_range:
        range_columns = st.columns(2)
        start_s = float(range_columns[0].number_input("Range start (seconds)", value=0.0))
        end_s = float(range_columns[1].number_input("Range end (seconds)", value=360.0))

    if st.button("Compute Windowed Metrics", type="primary"):
        st.session_state["windowed_metric_series"] = compute_windowed_metrics_for_ui(
            analysis.validation,
            width_s=width_s,
            alignment_origin_s=origin_s,
            analysis_start_s=start_s,
            analysis_end_s=end_s,
            partial_window_policy=str(partial_policy),
        )

    result = st.session_state.get("windowed_metric_series")
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            st.code(result.detail)
        return
    if not isinstance(result, WindowedMetricSeries):
        st.info("Choose the temporal contract and compute the windowed series.")
        return

    with st.container(border=True):
        st.markdown("**Window reconciliation**")
        summary = st.columns(4)
        summary[0].metric("Included windows", result.included_window_count, border=True)
        summary[1].metric("Excluded partial", result.excluded_partial_window_count, border=True)
        summary[2].metric("Empty windows", result.included_empty_window_count, border=True)
        summary[3].metric("Applicable metrics", len(result.applicable_metric_keys), border=True)
        st.caption(
            f"Analysis range: {result.analysis_start_s}–{result.analysis_end_s} s "
            f"(source: {result.range_source.value}, boundary: {result.boundary}). "
            "Empty windows stay visible; a missing metric is never filled with zero."
        )

    metric_key = st.selectbox(
        "Metric",
        result.applicable_metric_keys,
        index=(
            result.applicable_metric_keys.index("task.completion.rate")
            if "task.completion.rate" in result.applicable_metric_keys
            else 0
        ),
    )
    rows = _metric_rows(result, str(metric_key))
    st.caption(
        f"One row per fixed window for `{metric_key}`. Coverage is the requested-range overlap "
        "fraction. A blank value is an unavailable or excluded window, not a zero measurement."
    )
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            rows,
            hide_machine_ids=False,
            units={
                "window_start_s": "s",
                "window_end_s": "s",
                "effective_start_s": "s",
                "effective_end_s": "s",
            },
            number_formats={"coverage": "%.3f"},
            overrides={
                "window": ColumnDisplay(key="window", label="Window", hidden=False),
                "value": ColumnDisplay(key="value", label="Metric value", hidden=False),
            },
        ),
    )
    chart_rows = [
        row
        for row in rows
        if row["status"] == MetricStatus.AVAILABLE.value and isinstance(row["value"], int | float)
    ]
    if chart_rows:
        st.plotly_chart(
            line_figure(
                chart_rows,
                x_key="window_start_s",
                y_keys=["value"],
                title=f"{metric_key} by fixed window",
                y_title="Metric value",
            ),
            width="stretch",
        )
        st.caption("Chart plots only available windows over already-computed values.")
    else:
        st.info("No available numeric windows to chart for this metric.", icon=":material/info:")
    for warning in result.warnings:
        st.warning(warning)

    st.subheader("R6 Temporal Degradation")
    st.caption(
        "R6 compares exact consecutive windows with a declared baseline. Missing or low-coverage "
        "windows break episodes; event context is optional and never inferred. Defaults are "
        "provisional synthetic-development thresholds."
    )
    evidence_columns = st.columns(2)
    minimum_coverage = float(
        evidence_columns[0].number_input(
            "Minimum window coverage",
            min_value=0.0,
            max_value=1.0,
            value=1.0,
            step=0.05,
        )
    )
    use_event = evidence_columns[1].toggle("Declare an event for recovery analysis", value=False)
    event_time_s: float | None = None
    event_label: str | None = None
    if use_event:
        event_columns = st.columns(2)
        event_time_s = float(
            event_columns[0].number_input(
                "Declared event time (seconds)",
                value=float(result.analysis_start_s or 0.0),
            )
        )
        event_label = event_columns[1].text_input("Event label", value="declared event")
    with st.expander("R6 provisional thresholds"):
        threshold_columns = st.columns(3)
        baseline_windows = int(
            threshold_columns[0].number_input("Baseline windows", min_value=1, value=2)
        )
        sustained_windows = int(
            threshold_columns[1].number_input("Sustained windows", min_value=1, value=2)
        )
        minimum_windows = int(
            threshold_columns[2].number_input("Minimum evaluable windows", min_value=2, value=4)
        )
        delta_columns = st.columns(3)
        deterioration_delta = float(
            delta_columns[0].number_input(
                "Deterioration delta",
                min_value=0.000001,
                value=0.10,
                format="%.6f",
            )
        )
        recovery_tolerance = float(
            delta_columns[1].number_input(
                "Recovery tolerance",
                min_value=0.0,
                value=0.05,
                format="%.6f",
            )
        )
        recovery_horizon = int(
            delta_columns[2].number_input("Recovery horizon windows", min_value=1, value=4)
        )
    if st.button("Evaluate R6", type="primary"):
        st.session_state["temporal_diagnostic_analysis"] = evaluate_temporal_diagnostics_for_ui(
            analysis.validation,
            result,
            metric_key=str(metric_key),
            minimum_window_coverage=minimum_coverage,
            event_time_s=event_time_s,
            event_label=event_label,
            baseline_window_count=baseline_windows,
            minimum_evaluable_windows=minimum_windows,
            minimum_deterioration_delta=deterioration_delta,
            sustained_window_count=sustained_windows,
            recovery_tolerance=recovery_tolerance,
            recovery_horizon_windows=recovery_horizon,
        )
    diagnosis = st.session_state.get("temporal_diagnostic_analysis")
    if isinstance(diagnosis, ServiceError):
        st.error(diagnosis.message)
        if diagnosis.detail:
            st.code(diagnosis.detail)
    elif isinstance(diagnosis, TemporalDiagnosticAnalysis):
        r6 = diagnosis.r6_result
        episode = (
            f"{r6.metadata.get('episode_start_ordinal')}–{r6.metadata.get('episode_end_ordinal')}"
            if r6.metadata.get("episode_start_ordinal") is not None
            else "none"
        )
        recovery = str(r6.metadata.get("recovery_assessment", "unavailable"))
        with st.container(border=True):
            st.markdown(
                f"**R6 status:** {badge_markdown(r6.status.value)} · "
                f"**Episode (window ordinals):** {episode} · "
                f"**Recovery:** {badge_markdown(recovery)}"
            )
            st.metric(
                "Eligible windows",
                diagnosis.temporal_evidence.eligible_window_count,
                border=True,
            )
        if r6.hypothesis:
            st.warning(r6.hypothesis)
        if r6.findings:
            finding_rows = [
                {"finding": finding.finding_id, "statement": finding.statement}
                for finding in r6.findings
            ]
            st.dataframe(
                finding_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(finding_rows),
            )
        if r6.limitations:
            st.caption("Limitations: " + "; ".join(r6.limitations))
        with st.expander("Advanced: R6 evidence, configuration, and limitations (raw)"):
            st.json(
                {
                    "temporal_evidence": diagnosis.temporal_evidence.model_dump(mode="json"),
                    "rule_config": diagnosis.diagnostic_report.rule_config.r6.model_dump(
                        mode="json"
                    ),
                    "limitations": r6.limitations,
                }
            )
        st.download_button(
            "Download temporal diagnosis (JSON)",
            data=diagnosis.to_json(),
            file_name=f"{result.run_id}-r6-temporal-diagnosis.json",
            mime="application/json",
        )
    with st.expander("Advanced: window contract and anchors (raw)"):
        st.json(
            {
                "config": result.config.model_dump(mode="json"),
                "anchor_policy_version": result.anchor_policy_version,
                "anchor_fields": result.anchor_fields,
                "coverage_semantics": result.coverage_semantics,
                "empty_window_semantics": result.empty_window_semantics,
            }
        )
    st.download_button(
        "Download windowed metrics (JSON)",
        data=result.to_json(),
        file_name=f"{result.run_id}-windowed-metrics.json",
        mime="application/json",
    )


def _metric_rows(series: WindowedMetricSeries, metric_key: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in series.slices:
        metric = item.metrics.by_key().get(metric_key) if item.metrics is not None else None
        rows.append(
            {
                "window": item.window.ordinal,
                "window_start_s": item.window.start_s,
                "window_end_s": item.window.end_s,
                "effective_start_s": item.window.effective_start_s,
                "effective_end_s": item.window.effective_end_s,
                "coverage": item.window.requested_interval_coverage_fraction,
                "partial": item.window.is_partial,
                "disposition": item.disposition.value,
                "source_records": sum(item.source_record_counts.values()),
                "status": (
                    metric.status.value
                    if metric is not None
                    else (
                        "excluded"
                        if item.disposition is WindowDisposition.EXCLUDED_PARTIAL
                        else "unavailable"
                    )
                ),
                "value": metric.value if metric is not None else None,
                "reason_codes": (
                    ", ".join(reason.value for reason in metric.reason_codes)
                    if metric is not None
                    else ""
                ),
            }
        )
    return rows
