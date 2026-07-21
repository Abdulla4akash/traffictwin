"""Run Overview page."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.results import MetricStatus, MetricValue
from traffictwin.ui.charts import bar_figure, line_figure, metric_status_counts, task_event_series
from traffictwin.ui.components.cards import metric_card
from traffictwin.ui.components.provenance import render_run_provenance
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.tables import metric_rows

KPI_KEYS = {
    "Tasks generated": "task.generated.count",
    "Tasks completed": "task.completed.count",
    "Completion rate": "task.completion.rate",
    "Incomplete rate": "task.incomplete.rate",
    "Observed deadline-miss rate": "task.deadline_miss.completed_observed_rate",
    "Latency P50": "task.latency.p50_ms",
    "Latency P95": "task.latency.p95_ms",
    "Latency P99": "task.latency.p99_ms",
    "Offload rate": "task.offload.rate",
}

ENERGY_KPI_KEYS = {
    "Observed-task energy": "task.energy.mean_per_observed_task_j",
    "Completed-task energy": "task.energy.per_completed_j",
    "Energy-delay product": "task.energy_delay_product.mean_j_ms",
}


def render() -> None:
    """Render Run Overview page."""

    st.title("Run Overview")
    analysis = load_selected_analysis()
    if analysis is None or analysis.metrics is None:
        return
    render_source_caption(analysis)
    metrics = analysis.metrics.by_key()

    st.subheader("KPI Summary")
    for row_start in range(0, len(KPI_KEYS), 4):
        cols = st.columns(4)
        for col, (title, key) in zip(
            cols,
            list(KPI_KEYS.items())[row_start : row_start + 4],
            strict=False,
        ):
            with col:
                metric_card(title, metrics.get(key))

    st.subheader("Energy Evidence")
    energy_cols = st.columns(3)
    for col, (title, key) in zip(energy_cols, ENERGY_KPI_KEYS.items(), strict=True):
        with col:
            metric_card(title, metrics.get(key))
    st.caption(_energy_evidence_caption(metrics))

    st.subheader("Task Completion By Class")
    class_metric = metrics.get("task.completion.rate_by_class")
    if class_metric is not None and class_metric.status is MetricStatus.AVAILABLE:
        values = class_metric.value
        if isinstance(values, dict):
            st.plotly_chart(
                bar_figure(
                    list(values),
                    [float(value or 0) for value in values.values()],
                    title="Completion rate by task class",
                    y_title="Completion rate",
                ),
                width="stretch",
            )
    else:
        st.info("Task-class completion is unavailable.")

    st.subheader("Decision Shares")
    share_keys = [
        "task.decision_share.local",
        "task.decision_share.v2i",
        "task.decision_share.v2v",
        "task.decision_share.unknown",
    ]
    available_shares = [
        (key.rsplit(".", 1)[-1], float(metrics[key].value))
        for key in share_keys
        if metrics[key].status is MetricStatus.AVAILABLE and metrics[key].value is not None
    ]
    if available_shares:
        st.plotly_chart(
            bar_figure(
                [label for label, _ in available_shares],
                [value for _, value in available_shares],
                title="Decision shares",
                y_title="Share",
            ),
            width="stretch",
        )
    else:
        st.info("Decision share metrics are unavailable.")

    st.subheader("Task Arrivals And Completions")
    task_rows = task_event_series(analysis.validation.canonical)
    if task_rows:
        st.plotly_chart(
            line_figure(
                task_rows,
                x_key="timestamp_s",
                y_keys=["arrivals", "completions"],
                title="Task events over time",
                y_title="Tasks",
            ),
            width="stretch",
        )
    else:
        st.info("Task event timeline is unavailable.")

    st.subheader("Metric Availability")
    counts = metric_status_counts(analysis.metrics)
    st.plotly_chart(
        bar_figure(
            list(counts), list(counts.values()), title="Metric status counts", y_title="Metrics"
        ),
        width="stretch",
    )
    with st.expander("Metric details"):
        st.dataframe(metric_rows(analysis.metrics), width="stretch", hide_index=True)

    st.subheader("Context And Provenance")
    render_run_provenance(analysis.validation, analysis.metrics)


def _energy_evidence_caption(metrics: dict[str, MetricValue]) -> str:
    fingerprints = {
        fingerprint
        for key in ENERGY_KPI_KEYS.values()
        if (metric := metrics.get(key)) is not None
        and isinstance(fingerprint := metric.metadata.get("energy_contract_fingerprint"), str)
    }
    coverage = []
    for title, key in ENERGY_KPI_KEYS.items():
        metric = metrics.get(key)
        if metric is None:
            continue
        eligible = metric.metadata.get("eligible_count")
        population = metric.metadata.get("population_count")
        if isinstance(eligible, int) and isinstance(population, int):
            coverage.append(f"{title}: {eligible}/{population}")
    if fingerprints:
        fingerprint_text = ", ".join(sorted(fingerprints))
        coverage_text = "; ".join(coverage) or "no eligible-row counts"
        return (
            f"Contract fingerprint: {fingerprint_text}. Eligibility coverage: {coverage_text}. "
            "Missing evidence is never treated as zero."
        )
    return (
        "Energy metrics require a declared task-energy contract. Unavailable or partial evidence "
        "is never treated as zero."
    )
