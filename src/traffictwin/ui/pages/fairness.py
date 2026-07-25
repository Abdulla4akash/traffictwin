"""Operational-group fairness evidence page."""

from __future__ import annotations

import streamlit as st

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricValue
from traffictwin.rules.models import RuleStatus
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary, metric_card, section_header
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import ServiceError, evaluate_fairness_diagnostic_for_ui
from traffictwin.ui.tables import table_column_config

DISPARITY_CARDS: tuple[tuple[str, str], ...] = (
    ("Vehicle-tier completion gap", "fairness.vehicle_tier.completion_rate.max_gap"),
    ("Vehicle-tier completion Jain index", "fairness.vehicle_tier.completion_rate.jain"),
    ("RSU normalised-load gap", "fairness.rsu.capacity_normalised_load.max_gap"),
    ("RSU normalised-load Jain index", "infra.load_balance.jain_capacity_normalised"),
)


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

    tier_metric = metrics.get("task.completion.rate_by_vehicle_tier")
    rsu_metric = metrics.get("fairness.rsu.capacity_normalised_load.by_group")
    _render_group_coverage(tier_metric, rsu_metric)

    section_header("Disparity Summary")
    columns = st.columns(4)
    for column, (title, key) in zip(columns, DISPARITY_CARDS, strict=True):
        with column:
            metric_card(title, metrics.get(key))
    st.caption(
        "TrafficTwin never labels a policy fair or unfair. It reports operational disparities only "
        "when the predeclared fairness contract and sufficient group evidence are both present; a "
        "gap alone is a description, not a verdict."
    )

    section_header("Vehicle-Tier Completion Groups")
    tier_rows = _group_rows(tier_metric, value_label="completion_rate")
    if tier_rows:
        st.dataframe(
            tier_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                tier_rows,
                number_formats={"completion_rate": "%.3f", "coverage_fraction": "%.3f"},
            ),
        )
        _render_group_chart(
            tier_metric,
            axis_label="Vehicle tier",
            value_label="Completion rate",
            title="Completion rate by vehicle tier",
        )
    else:
        render_metric_unavailable(tier_metric, "stable vehicle tiers joined to every task")

    section_header("RSU Capacity-Normalised Load Groups")
    rsu_rows = _group_rows(rsu_metric, value_label="mean_active_tasks_per_capacity")
    if rsu_rows:
        st.dataframe(
            rsu_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                rsu_rows,
                number_formats={
                    "mean_active_tasks_per_capacity": "%.3f",
                    "coverage_fraction": "%.3f",
                },
            ),
        )
    else:
        render_metric_unavailable(
            rsu_metric,
            "at least two RSUs with complete positive-capacity and active-task evidence",
        )

    _render_exclusions(tier_metric, rsu_metric)

    policy_metric = tier_metric if tier_metric is not None else rsu_metric
    if policy_metric is not None:
        _render_policy_identity(policy_metric)

    _render_r7(analysis.evidence_pack)


def _render_group_coverage(tier_metric: MetricValue | None, rsu_metric: MetricValue | None) -> None:
    """Render an eligibility/denominator KPI row over the operational groups."""

    with st.container(border=True):
        st.markdown("**Eligible-group coverage**")
        columns = st.columns(3)
        columns[0].metric(
            "Eligible vehicle-tier groups",
            _group_count(tier_metric),
            help="Distinct vehicle tiers with sufficient joined support.",
            border=True,
        )
        columns[1].metric(
            "Eligible RSU groups",
            _group_count(rsu_metric),
            help="Distinct RSUs with complete positive-capacity and active-task evidence.",
            border=True,
        )
        columns[2].metric(
            "Group coverage (%)",
            _coverage_percentage(tier_metric if tier_metric is not None else rsu_metric),
            help="Share of the population represented by eligible groups; never inferred.",
            border=True,
        )
        st.caption(
            "Denominators are the eligible-group counts above. Groups below the predeclared "
            "minimum support are excluded from disparities rather than shown as zero."
        )


def _render_group_chart(
    metric: MetricValue | None, *, axis_label: str, value_label: str, title: str
) -> None:
    """Chart a single compatible group metric descriptively."""

    if metric is None or not isinstance(metric.value, dict):
        return
    rows = [
        {axis_label: str(group), value_label: float(value)}
        for group, value in sorted(metric.value.items())
        if isinstance(value, int | float) and not isinstance(value, bool)
    ]
    if not rows:
        return
    st.bar_chart(rows, x=axis_label, y=value_label, x_label=axis_label, y_label=value_label)
    st.caption(
        "Descriptive per-group values under the declared policy; a visible disparity is not a "
        "fairness verdict, and excluded groups are omitted rather than plotted as zero."
    )


def _render_exclusions(tier_metric: MetricValue | None, rsu_metric: MetricValue | None) -> None:
    """Keep insufficient groups and protected-attribute limitations visible."""

    section_header("Exclusions & Limitations")
    for label, metric in (
        ("Vehicle-tier groups", tier_metric),
        ("RSU groups", rsu_metric),
    ):
        available = metric is not None and isinstance(metric.value, dict)
        state = "available" if available else "unavailable"
        st.markdown(f"**{label}:** {badge_markdown(state)}")
        if metric is not None and metric.missing_evidence:
            st.caption("Missing evidence: " + "; ".join(metric.missing_evidence))
    st.markdown(
        "- Protected or demographic attributes are **not represented** in these operational groups "
        "and are never inferred.\n"
        "- Groups below the predeclared minimum support are **excluded**, not zero-filled.\n"
        "- Equal poor outcomes across groups are not evidence of good or fair performance."
    )


def _render_policy_identity(metric: MetricValue) -> None:
    """Show a truncated policy fingerprint; keep the complete value in Advanced/Evidence."""

    metadata = metric.metadata
    fingerprint = metadata.get("fairness_policy_fingerprint")
    short = fingerprint_summary(fingerprint if isinstance(fingerprint, str) else None)
    st.caption(
        f"Fairness policy {metadata.get('fairness_policy_version', 'unavailable')}; "
        f"fingerprint `{short}`; "
        f"minimum groups {metadata.get('minimum_group_count', 'unavailable')}; "
        f"minimum support {metadata.get('minimum_group_support', 'unavailable')}; "
        f"required coverage {metadata.get('minimum_coverage_fraction', 'unavailable')}."
    )
    with st.expander("Advanced: fairness policy identity"):
        st.caption(
            f"Complete fairness policy fingerprint: {fingerprint if fingerprint else 'unavailable'}"
        )
        st.code(
            f"fairness_policy_version: {metadata.get('fairness_policy_version')}\n"
            f"fairness_policy_fingerprint: {fingerprint}\n"
            f"minimum_group_count: {metadata.get('minimum_group_count')}\n"
            f"minimum_group_support: {metadata.get('minimum_group_support')}\n"
            f"minimum_coverage_fraction: {metadata.get('minimum_coverage_fraction')}",
            language=None,
        )


def _render_r7(evidence_pack: EvidencePack | None) -> None:
    section_header("R7 Operational Outcome Disparity")
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
    with st.container(border=True):
        st.markdown(
            f"**R7 status:** {badge_markdown(result.status.value)} · "
            f"**Selected dimension:** {badge_markdown(dimension)} · "
            f"**Categorical confidence:** {badge_markdown(result.confidence.value)}"
        )
    if result.status is RuleStatus.TRIGGERED:
        st.warning(result.hypothesis or "R7 identified the configured candidate pattern.")
    elif result.status is RuleStatus.INSUFFICIENT_EVIDENCE:
        st.info("R7 is unavailable for this selection; missing evidence is shown below.")
    else:
        st.success("R7 did not identify the configured candidate pattern.")
    with st.expander("Advanced: R7 evidence, alternatives, and limitations"):
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


def _group_count(metric: MetricValue | None) -> int:
    if metric is None or not isinstance(metric.value, dict):
        return 0
    return len(metric.value)


def _coverage_percentage(metric: MetricValue | None) -> str:
    if metric is None:
        return "Unavailable"
    coverage = metric.metadata.get("coverage_fraction")
    if isinstance(coverage, int | float) and not isinstance(coverage, bool):
        return f"{100 * float(coverage):.1f}%"
    return "Unavailable"
