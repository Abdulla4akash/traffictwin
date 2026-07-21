"""Operational-group fairness evidence page."""

from __future__ import annotations

import streamlit as st

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricValue
from traffictwin.rules.models import RuleStatus
from traffictwin.ui.components.cards import metric_card
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import ServiceError, evaluate_fairness_diagnostic_for_ui


def render() -> None:
    """Render evidence-gated vehicle-tier and RSU disparity outputs."""

    st.title("Fairness Evidence")
    analysis = load_selected_analysis()
    if analysis is None or analysis.metrics is None:
        return
    render_source_caption(analysis)
    metrics = analysis.metrics.by_key()
    st.info(
        "These are operational vehicle-tier and RSU resource-group measures only. TrafficTwin "
        "does not infer protected or demographic attributes, and equal poor outcomes are not "
        "evidence of good performance."
    )

    st.subheader("Disparity Summary")
    cards = (
        (
            "Vehicle-tier completion gap",
            "fairness.vehicle_tier.completion_rate.max_gap",
        ),
        (
            "Vehicle-tier completion Jain index",
            "fairness.vehicle_tier.completion_rate.jain",
        ),
        (
            "RSU normalised-load gap",
            "fairness.rsu.capacity_normalised_load.max_gap",
        ),
        (
            "RSU normalised-load Jain index",
            "infra.load_balance.jain_capacity_normalised",
        ),
    )
    columns = st.columns(4)
    for column, (title, key) in zip(columns, cards, strict=True):
        with column:
            metric_card(title, metrics.get(key))

    tier_metric = metrics.get("task.completion.rate_by_vehicle_tier")
    st.subheader("Vehicle-Tier Completion Groups")
    tier_rows = _group_rows(tier_metric, value_label="completion_rate")
    if tier_rows:
        st.dataframe(tier_rows, hide_index=True, width="stretch")
    else:
        render_metric_unavailable(tier_metric, "stable vehicle tiers joined to every task")

    rsu_metric = metrics.get("fairness.rsu.capacity_normalised_load.by_group")
    st.subheader("RSU Capacity-Normalised Load Groups")
    rsu_rows = _group_rows(rsu_metric, value_label="mean_active_tasks_per_capacity")
    if rsu_rows:
        st.dataframe(rsu_rows, hide_index=True, width="stretch")
    else:
        render_metric_unavailable(
            rsu_metric,
            "at least two RSUs with complete positive-capacity and active-task evidence",
        )

    policy_metric = tier_metric if tier_metric is not None else rsu_metric
    if policy_metric is not None:
        st.caption(_policy_caption(policy_metric))

    _render_r7(analysis.evidence_pack)


def _render_r7(evidence_pack: EvidencePack | None) -> None:
    st.subheader("R7 Operational Outcome Disparity")
    st.caption(
        "Select exactly one operational dimension. The 0.20 default is a provisional synthetic-"
        "development threshold, not a fairness standard. R7 reports a candidate pattern and "
        "cannot establish discrimination, geography, significance, or causality."
    )
    if not isinstance(evidence_pack, EvidencePack):
        st.info("An EvidencePack is required before R7 can be evaluated.")
        return
    controls = st.columns(3)
    label = controls[0].selectbox(
        "R7 dimension",
        ["Vehicle-tier completion", "Exact target-RSU completion"],
    )
    dimension = (
        "vehicle_tier_completion" if label == "Vehicle-tier completion" else "target_rsu_completion"
    )
    minimum_gap = float(
        controls[1].number_input(
            "Minimum outcome gap",
            min_value=0.0,
            max_value=1.0,
            value=0.20,
            step=0.05,
            format="%.2f",
        )
    )
    minimum_support = int(
        controls[2].number_input(
            "Minimum support per group",
            min_value=1,
            value=2,
            step=1,
        )
    )
    result = evaluate_fairness_diagnostic_for_ui(
        evidence_pack,
        dimension=dimension,
        minimum_outcome_gap=minimum_gap,
        minimum_group_support=minimum_support,
    )
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            st.code(result.detail)
        return
    summary = st.columns(3)
    summary[0].metric("R7 status", result.status.value)
    summary[1].metric("Selected dimension", dimension)
    summary[2].metric("Categorical confidence", result.confidence.value)
    if result.status is RuleStatus.TRIGGERED:
        st.warning(result.hypothesis or "R7 identified the configured candidate pattern.")
    elif result.status is RuleStatus.INSUFFICIENT_EVIDENCE:
        st.info("R7 is unavailable for this selection; missing evidence is shown below.")
    else:
        st.success("R7 did not identify the configured candidate pattern.")
    with st.expander("R7 evidence, alternatives, and limitations"):
        for finding in result.findings:
            st.write(f"{finding.finding_id} — {finding.support.value}: {finding.statement}")
        if result.missing_evidence:
            st.write({"missing_evidence": result.missing_evidence})
        st.write(
            {
                "alternative_explanations": result.alternative_explanations,
                "limitations": result.limitations,
                "metadata": result.metadata,
            }
        )
    st.download_button(
        "Download R7 result (JSON)",
        data=result.model_dump_json(indent=2),
        file_name=f"{evidence_pack.pack_id}-r7.json",
        mime="application/json",
    )


def _group_rows(metric: MetricValue | None, *, value_label: str) -> list[dict[str, object]]:
    if metric is None or not isinstance(metric.value, dict):
        return []
    support = metric.metadata.get("group_support_counts")
    support_by_group = support if isinstance(support, dict) else {}
    return [
        {
            "operational_group": group,
            value_label: value,
            "eligible_support": support_by_group.get(group),
            "coverage_fraction": metric.metadata.get("coverage_fraction"),
        }
        for group, value in sorted(metric.value.items())
    ]


def _policy_caption(metric: MetricValue) -> str:
    metadata = metric.metadata
    return (
        f"Fairness policy {metadata.get('fairness_policy_version', 'unavailable')}; "
        f"fingerprint {metadata.get('fairness_policy_fingerprint', 'unavailable')}; "
        f"minimum groups {metadata.get('minimum_group_count', 'unavailable')}; "
        f"minimum support {metadata.get('minimum_group_support', 'unavailable')}; "
        f"required coverage {metadata.get('minimum_coverage_fraction', 'unavailable')}."
    )
