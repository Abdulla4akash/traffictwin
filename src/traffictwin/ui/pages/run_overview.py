"""Run Overview page."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.results import MetricStatus, MetricValue
from traffictwin.ui.charts import bar_figure, line_figure, metric_status_counts, task_event_series
from traffictwin.ui.components.cards import fingerprint_summary, metric_card
from traffictwin.ui.components.first_run import first_run_guidance
from traffictwin.ui.components.provenance import render_run_provenance
from traffictwin.ui.labels import UiPage
from traffictwin.ui.pages.helpers import (
    load_selected_analysis,
    render_source_caption,
    selected_bundle_path,
)
from traffictwin.ui.tables import metric_rows, table_column_config

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

# Display-only unit suffixes for KPI card labels; ratio metrics already render
# as percentages, and every card keeps the exact unit in its help tooltip.
KPI_UNIT_SUFFIXES = {
    "Latency P50": "ms",
    "Latency P95": "ms",
    "Latency P99": "ms",
}

PRIMARY_KPI_TITLES = (
    "Tasks completed",
    "Completion rate",
    "Latency P50",
    "Offload rate",
)

ENERGY_KPI_KEYS = {
    "Observed-task energy": "task.energy.mean_per_observed_task_j",
    "Completed-task energy": "task.energy.per_completed_j",
    "Energy-delay product": "task.energy_delay_product.mean_j_ms",
}

ENERGY_UNIT_SUFFIXES = {
    "Observed-task energy": "J",
    "Completed-task energy": "J",
    "Energy-delay product": "J·ms",
}


def _kpi_label(title: str) -> str:
    suffix = KPI_UNIT_SUFFIXES.get(title) or ENERGY_UNIT_SUFFIXES.get(title)
    return f"{title} ({suffix})" if suffix else title


def render() -> None:
    """Render Run Overview page."""

    st.title("Run Overview")
    analysis = load_selected_analysis()
    if analysis is None or analysis.metrics is None:
        # A missing selection on a fresh workspace deserves directions, not
        # only the error above; a rejected bundle keeps its error unadorned.
        if not selected_bundle_path().exists():
            first_run_guidance(
                actions=[
                    ("Start Guided Demo", UiPage.GUIDED_DEMO),
                    ("Import a Run Bundle", UiPage.BUNDLE_IMPORT),
                ],
                message=(
                    "No run bundle is selected yet. The guided demo creates and "
                    "analyses a synthetic run end to end, or import an existing "
                    "bundle to open it here."
                ),
                key_prefix="run_overview_first_run",
            )
        return
    render_source_caption(analysis)
    metrics = analysis.metrics.by_key()

    st.subheader("KPI summary")
    cols = st.columns(4)
    for col, title in zip(cols, PRIMARY_KPI_TITLES, strict=True):
        with col:
            metric_card(_kpi_label(title), metrics.get(KPI_KEYS[title]))
    secondary_titles = [title for title in KPI_KEYS if title not in PRIMARY_KPI_TITLES]
    with st.expander(f"All task KPIs ({len(secondary_titles)} more)"):
        for row_start in range(0, len(secondary_titles), 4):
            cols = st.columns(4)
            for col, title in zip(
                cols,
                secondary_titles[row_start : row_start + 4],
                strict=False,
            ):
                with col:
                    metric_card(_kpi_label(title), metrics.get(KPI_KEYS[title]))

    st.subheader("Energy evidence")
    energy_cols = st.columns(3)
    for col, (title, key) in zip(energy_cols, ENERGY_KPI_KEYS.items(), strict=True):
        with col:
            metric_card(_kpi_label(title), metrics.get(key))
    st.caption(_energy_evidence_caption(metrics))
    full_fingerprints = _energy_contract_fingerprints(metrics)
    if full_fingerprints:
        with st.expander("Advanced: full energy-contract fingerprints"):
            st.code("\n".join(sorted(full_fingerprints)), language=None)

    st.subheader("Task completion by class")
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

    st.subheader("Decision shares")
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

    st.subheader("Task arrivals and completions")
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

    st.subheader("Metric availability")
    counts = metric_status_counts(analysis.metrics)
    st.plotly_chart(
        bar_figure(
            list(counts), list(counts.values()), title="Metric status counts", y_title="Metrics"
        ),
        width="stretch",
    )
    with st.expander("Metric details"):
        detail_rows = metric_rows(analysis.metrics)
        st.dataframe(
            detail_rows,
            width="stretch",
            hide_index=True,
            column_config=table_column_config(detail_rows),
        )

    st.subheader("Context and provenance")
    with st.expander("Advanced: run identity and provenance"):
        render_run_provenance(analysis.validation, analysis.metrics)


def _energy_contract_fingerprints(metrics: dict[str, MetricValue]) -> set[str]:
    return {
        fingerprint
        for key in ENERGY_KPI_KEYS.values()
        if (metric := metrics.get(key)) is not None
        and isinstance(fingerprint := metric.metadata.get("energy_contract_fingerprint"), str)
    }


def _energy_evidence_caption(metrics: dict[str, MetricValue]) -> str:
    fingerprints = _energy_contract_fingerprints(metrics)
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
        fingerprint_text = ", ".join(
            fingerprint_summary(fingerprint) for fingerprint in sorted(fingerprints)
        )
        coverage_text = "; ".join(coverage) or "no eligible-row counts"
        return (
            f"Contract fingerprint: {fingerprint_text}. Eligibility coverage: {coverage_text}. "
            "Missing evidence is never treated as zero."
        )
    return (
        "Energy metrics require a declared task-energy contract. Unavailable or partial evidence "
        "is never treated as zero."
    )
