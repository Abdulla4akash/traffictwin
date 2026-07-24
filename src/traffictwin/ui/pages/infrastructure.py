"""Infrastructure & Congestion page."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricValue
from traffictwin.ui.charts import infrastructure_series
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import metric_card, section_header
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import BundleAnalysis
from traffictwin.ui.tables import table_column_config


def render(config: MetricEngineConfig) -> None:
    """Render infrastructure view."""

    st.title("Infrastructure & Congestion")
    analysis = load_selected_analysis()
    if analysis is None or analysis.metrics is None:
        return
    render_source_caption(analysis)
    st.info(
        f"Demo threshold: {config.saturation_threshold:.2f}. "
        "This threshold is configurable and is not yet a validated research threshold."
    )

    _render_provenance_and_window(analysis)

    records = analysis.validation.canonical.infrastructure
    rsu_ids = sorted({record.rsu_id for record in records})
    selected = st.selectbox("RSU selector", ["All RSUs", *rsu_ids]) if rsu_ids else "All RSUs"
    rows = infrastructure_series(
        analysis.validation.canonical,
        None if selected == "All RSUs" else str(selected),
    )
    section_header("Queue and Utilisation Over the Observed Window")
    if rows:
        st.line_chart(
            rows,
            x="timestamp_s",
            y="queue_length",
            color="rsu_id",
            x_label="Simulation time (s)",
            y_label="Queued tasks",
        )
        st.line_chart(
            rows,
            x="timestamp_s",
            y="utilisation_fraction",
            color="rsu_id",
            x_label="Simulation time (s)",
            y_label="Utilisation fraction",
        )
        st.caption(
            "Native time-series over already-computed canonical infrastructure observations; each "
            "line is one source/synthetic RSU slot, not a verified Manchester roadside unit."
        )
    else:
        render_metric_unavailable(
            analysis.metrics.by_key().get("infra.queue_length.mean"),
            "infra_state.csv",
        )

    metrics = analysis.metrics.by_key()
    section_header("Capacity, Pressure and Utilisation")
    cols = st.columns(4)
    with cols[0]:
        metric_card("P95 utilisation (fraction)", metrics.get("infra.utilisation.p95"))
    with cols[1]:
        metric_card("Max queue (tasks)", metrics.get("infra.queue_length.max"))
    with cols[2]:
        metric_card("Saturation episodes (count)", metrics.get("infra.saturation.episode_count"))
    with cols[3]:
        metric_card("Saturation duration (s)", metrics.get("infra.saturation.duration_s"))

    section_header("Load Balance")
    balance_columns = st.columns(2)
    metric = metrics.get("infra.load_balance.jain_capacity_normalised")
    with balance_columns[0]:
        if metric is not None and metric.value is not None:
            metric_card("Capacity-normalised load Jain index", metric)
        else:
            render_metric_unavailable(metric, "infra_state.csv with capacity and active_tasks")
    with balance_columns[1]:
        metric_card(
            "Capacity-normalised load maximum gap",
            metrics.get("fairness.rsu.capacity_normalised_load.max_gap"),
        )
    st.caption(
        "Operational RSU balance requires complete coverage, two RSUs, and two eligible "
        "observations per RSU. It does not establish task-outcome fairness."
    )

    _render_per_rsu_summary(metrics.get("infra.rsu.summary"))


def _render_provenance_and_window(analysis: BundleAnalysis) -> None:
    """Separate canonical evidence from synthetic/source infrastructure and show the window."""

    records = analysis.validation.canonical.infrastructure
    manifest = analysis.validation.manifest
    synthetic = manifest is not None and manifest.environment.name == "synthetic"
    provenance = "synthetic" if synthetic else "imported"
    timestamps = [record.timestamp_s for record in records]
    with st.container(border=True):
        st.markdown(f"**Infrastructure provenance:** {badge_markdown(provenance)}")
        columns = st.columns(3)
        columns[0].metric(
            "Observed RSU slots", len({record.rsu_id for record in records}), border=True
        )
        columns[1].metric("Infrastructure observations", len(records), border=True)
        columns[2].metric(
            "Observation window (s)",
            f"{min(timestamps):.0f}–{max(timestamps):.0f}" if timestamps else "Unavailable",
            border=True,
        )
        st.caption(
            "RSU identifiers are source or synthetic slots, not verified Manchester roadside "
            "infrastructure. Missing capacity, mapping, or canonical-identity evidence stays "
            "unavailable rather than assumed."
        )


def _render_per_rsu_summary(summary: MetricValue | None) -> None:
    """Render the per-RSU summary as a structured table; keep the raw dict in Advanced/Evidence."""

    section_header("Per-RSU Summary")
    if summary is None or not isinstance(summary.value, dict):
        render_metric_unavailable(summary, "infra_state.csv")
        return
    rows = [_summary_row(str(rsu_id), value) for rsu_id, value in sorted(summary.value.items())]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(rows, hide_machine_ids=False),
    )
    st.caption(
        "Per-RSU capacity and pressure summary over canonical infrastructure observations only; "
        "unmapped or capacity-free RSUs stay unavailable rather than defaulted."
    )
    with st.expander("Advanced/Evidence: raw per-RSU summary"):
        st.json(summary.value)


def _summary_row(rsu_id: str, value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {"rsu_id": rsu_id, **value}
    return {"rsu_id": rsu_id, "summary": value}
