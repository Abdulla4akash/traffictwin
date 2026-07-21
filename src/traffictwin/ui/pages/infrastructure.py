"""Infrastructure & Congestion page."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.ui.charts import infrastructure_series, line_figure
from traffictwin.ui.components.cards import metric_card
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption


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

    records = analysis.validation.canonical.infrastructure
    rsu_ids = sorted({record.rsu_id for record in records})
    selected = st.selectbox("RSU selector", ["All RSUs", *rsu_ids]) if rsu_ids else "All RSUs"
    rows = infrastructure_series(
        analysis.validation.canonical,
        None if selected == "All RSUs" else str(selected),
    )
    if rows:
        st.plotly_chart(
            line_figure(
                rows,
                x_key="timestamp_s",
                y_keys=["queue_length"],
                title="Queue length over time",
                y_title="Queued tasks",
            ),
            width="stretch",
        )
        st.plotly_chart(
            line_figure(
                rows,
                x_key="timestamp_s",
                y_keys=["utilisation_fraction"],
                title="Utilisation over time",
                y_title="Utilisation fraction",
            ),
            width="stretch",
        )
    else:
        render_metric_unavailable(
            analysis.metrics.by_key().get("infra.queue_length.mean"),
            "infra_state.csv",
        )

    metrics = analysis.metrics.by_key()
    cols = st.columns(4)
    with cols[0]:
        metric_card("P95 utilisation", metrics.get("infra.utilisation.p95"))
    with cols[1]:
        metric_card("Max queue", metrics.get("infra.queue_length.max"))
    with cols[2]:
        metric_card("Saturation episodes", metrics.get("infra.saturation.episode_count"))
    with cols[3]:
        metric_card("Saturation duration", metrics.get("infra.saturation.duration_s"))

    st.subheader("Load Balance")
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

    st.subheader("Per-RSU Summary")
    summary = metrics.get("infra.rsu.summary")
    if summary is not None and isinstance(summary.value, dict):
        st.json(summary.value)
    else:
        render_metric_unavailable(summary, "infra_state.csv")
