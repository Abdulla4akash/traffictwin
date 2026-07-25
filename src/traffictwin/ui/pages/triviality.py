"""Experiment-level Triviality, winner-map, and portfolio view."""

from __future__ import annotations

import streamlit as st

from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.rules.models import RuleStatus
from traffictwin.ui.charts import bar_figure
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    build_training_validation_pairs_for_ui,
    load_research_analysis_catalog,
    load_research_analysis_view,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import table_column_config


def render(config: UiConfig) -> None:
    """Render reusable experiment evidence without recomputing findings in the page."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.TRIVIALITY))
    st.info(
        "Synthetic policy profiles verify the workflow only. Winner maps and portfolio results "
        "must not be reported as trained-algorithm performance."
    )
    experiment_id = st.text_input(
        "Experiment ID",
        value="exp-synthetic-portfolio-study",
        help="Uses metric collections already stored in the active registry.",
    )
    catalog = load_research_analysis_catalog(config.registry_path, experiment_id)
    if isinstance(catalog, ServiceError):
        st.warning(catalog.message)
        if catalog.detail:
            st.caption(catalog.detail)
        return
    cols = st.columns(2)
    default_metric = (
        catalog.metric_keys.index("task.completion.rate")
        if "task.completion.rate" in catalog.metric_keys
        else 0
    )
    metric_key = cols[0].selectbox(
        "Primary scalar metric",
        catalog.metric_keys,
        index=default_metric,
    )
    objective = ObjectiveDirection(
        cols[1].selectbox(
            "Objective direction",
            [item.value for item in ObjectiveDirection],
        )
    )

    section_header("Explicit Training–Validation Pairs")
    st.caption(
        "Selections are paired by position. Each pair must match algorithm, checkpoint, random "
        "seed, metric definition, and unit; environment provenance remains explicit."
    )
    cols = st.columns(2)
    training_runs = cols[0].multiselect("Training runs", catalog.run_ids)
    validation_runs = cols[1].multiselect("Validation runs", catalog.run_ids)
    pairs = build_training_validation_pairs_for_ui(
        config.registry_path,
        training_runs,
        validation_runs,
        metric_key,
    )
    if isinstance(pairs, ServiceError):
        st.warning(pairs.message)
        if pairs.detail:
            st.caption(pairs.detail)
        return

    view = load_research_analysis_view(
        config.registry_path,
        experiment_id,
        metric_key=metric_key,
        objective=objective,
        training_validation=pairs,
    )
    if isinstance(view, ServiceError):
        st.warning(view.message)
        if view.detail:
            st.caption(view.detail)
        return

    r3 = next(
        (result for result in view.diagnostic_report.results if result.rule_id == "R3"),
        None,
    )
    r5 = next(
        (result for result in view.diagnostic_report.results if result.rule_id == "R5"),
        None,
    )
    with st.container(border=True):
        summary = st.columns(2)
        summary[0].metric("Source runs", view.source_collection_count, border=True)
        summary[1].metric("Seed families", len(view.winner_map.entries), border=True)
        st.markdown(
            f"**Winner-map metric:** `{view.winner_map.metric_key}` · "
            f"**R3 (triviality):** {badge_markdown(r3.status.value if r3 else 'unavailable')} · "
            f"**R5 (drift):** {badge_markdown(r5.status.value if r5 else 'unavailable')}"
        )
        st.caption(
            "A winner or tie within one seed family is not a universal ranking; incompatible or "
            "missing cohorts stay excluded rather than ranked."
        )

    section_header("Triviality Evidence")
    experiment_metrics = view.evidence_pack.metric_collection.by_key()
    triviality_rows = [
        {
            "metric_key": key,
            "status": metric.status.value,
            "value": metric.value,
            "unit": metric.unit,
        }
        for key, metric in sorted(experiment_metrics.items())
        if key.startswith("experiment.")
    ]
    st.dataframe(
        triviality_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(triviality_rows),
    )
    if r3 is not None:
        if r3.status is RuleStatus.TRIGGERED:
            st.warning(r3.hypothesis or "R3 triggered.")
        elif r3.status is RuleStatus.INSUFFICIENT_EVIDENCE:
            st.info("R3 needs more compatible multi-policy evidence.")
        else:
            st.success("R3 did not identify the configured triviality pattern.")
        with st.expander("Advanced: R3 evidence and limitations"):
            st.json(r3.model_dump(mode="json"))
    if r5 is not None:
        if r5.status is RuleStatus.TRIGGERED:
            st.warning(r5.hypothesis or "R5 triggered.")
        elif r5.status is RuleStatus.INSUFFICIENT_EVIDENCE:
            st.info("R5 needs at least two compatible explicit pairs by default.")
        elif r5.status is RuleStatus.CONFLICTING_EVIDENCE:
            st.warning(r5.hypothesis or "R5 has conflicting evidence.")
        else:
            st.success("R5 did not identify the configured drift pattern.")
        with st.expander("Advanced: R5 evidence and limitations"):
            st.json(r5.model_dump(mode="json"))

    section_header("Per-Seed Winner Map")
    rows = [
        {
            "seed_family": entry.seed_id,
            "algorithm": score.algorithm,
            "mean": score.mean,
            "rank": score.rank,
            "regret": score.regret,
            "winner": score.winner,
            "observations": score.observation_count,
        }
        for entry in view.winner_map.entries
        for score in entry.policy_scores
    ]
    if rows:
        st.dataframe(
            rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(rows),
        )
        chart_rows = [row for row in rows if isinstance(row["mean"], int | float)]
        if chart_rows:
            labels = [f"{row['seed_family']}/{row['algorithm']}" for row in chart_rows]
            values = [float(row["mean"]) for row in chart_rows]  # type: ignore[arg-type]
            st.plotly_chart(
                bar_figure(
                    labels,
                    values,
                    title=f"Mean {view.winner_map.metric_key} by seed family and policy",
                    y_title="Mean (per compatible cohort)",
                ),
                width="stretch",
            )
            st.caption(
                "Descriptive per-cohort means over already-computed scores; bar height is not a "
                "cross-family ranking or a claim that any policy is universally best."
            )
    else:
        st.info("No compatible scalar observations are available for a winner map.")
    for warning in view.winner_map.warnings:
        st.caption(warning)

    section_header("Transparent Portfolio Prototype")
    cols = st.columns(3)
    cols[0].metric("Evaluated seed families", view.portfolio.evaluated_seed_count)
    cols[1].metric(
        "Winner/tie rate",
        "unavailable"
        if view.portfolio.winner_or_tie_rate is None
        else f"{view.portfolio.winner_or_tie_rate:.3f}",
    )
    cols[2].metric(
        "Mean regret",
        "unavailable"
        if view.portfolio.mean_regret is None
        else f"{view.portfolio.mean_regret:.4f}",
    )
    portfolio_rows = [row.model_dump(mode="json") for row in view.portfolio.rows]
    st.dataframe(
        portfolio_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(portfolio_rows),
    )
    for warning in view.portfolio.warnings:
        st.caption(warning)

    if view.portfolio_study is not None:
        section_header("Fixed Held-out Portfolio Study")
        st.caption(
            "The transparent rules are fixed before evaluation on the S5/S6 synthetic seed "
            "families. This is a workflow verification, not external validation."
        )
        cols = st.columns(4)
        held_out = view.portfolio_study.held_out_evaluation
        cols[0].metric("Development seeds", len(view.portfolio_study.development_seed_ids))
        cols[1].metric("Held-out seeds", len(view.portfolio_study.held_out_seed_ids))
        cols[2].metric(
            "Held-out selector win/tie",
            "unavailable"
            if held_out.winner_or_tie_rate is None
            else f"{held_out.winner_or_tie_rate:.3f}",
        )
        cols[3].metric(
            "Held-out selector regret",
            "unavailable" if held_out.mean_regret is None else f"{held_out.mean_regret:.4f}",
        )
        held_out_rows = [
            row.model_dump(mode="json") for row in view.portfolio_study.held_out_constituents
        ]
        st.dataframe(
            held_out_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(held_out_rows),
        )
        for warning in view.portfolio_study.warnings:
            st.caption(warning)

    section_header("Exports")
    cols = st.columns(4)
    cols[0].download_button(
        "Experiment EvidencePack",
        data=view.evidence_pack.to_json(),
        file_name=f"{view.evidence_pack.pack_id}.json",
        mime="application/json",
    )
    cols[1].download_button(
        "Winner Map",
        data=view.winner_map.to_json(),
        file_name=f"{experiment_id}-winner-map.json",
        mime="application/json",
    )
    cols[2].download_button(
        "Portfolio Evaluation",
        data=view.portfolio.to_json(),
        file_name=f"{experiment_id}-portfolio.json",
        mime="application/json",
    )
    if view.portfolio_study is not None:
        cols[3].download_button(
            "Held-out Study",
            data=view.portfolio_study.to_json(),
            file_name=f"{experiment_id}-held-out-study.json",
            mime="application/json",
        )
