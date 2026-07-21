"""Contract-gated task-energy evidence and R8 page."""

from __future__ import annotations

import streamlit as st

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricValue
from traffictwin.rules.models import RuleStatus
from traffictwin.ui.components.cards import metric_card
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import ServiceError, evaluate_energy_diagnostic_for_ui

ENERGY_METRICS = {
    "Observed-task energy": "task.energy.mean_per_observed_task_j",
    "Completed-task energy": "task.energy.per_completed_j",
    "Energy-delay product": "task.energy_delay_product.mean_j_ms",
}


def render() -> None:
    """Render exact energy evidence and library-evaluated R8 controls."""

    st.title("Energy Evidence")
    analysis = load_selected_analysis()
    if analysis is None or analysis.metrics is None:
        return
    render_source_caption(analysis)
    metrics = analysis.metrics.by_key()
    st.info(
        "Energy metrics and R8 require the exact canonical task-energy contract. Missing, partial, "
        "or differently defined energy is unavailable and is never treated as zero or converted."
    )

    st.subheader("Contract-Gated Energy Metrics")
    columns = st.columns(3)
    for column, (title, key) in zip(columns, ENERGY_METRICS.items(), strict=True):
        with column:
            metric_card(title, metrics.get(key))
    st.caption(_coverage_caption(metrics))

    _render_r8(analysis.evidence_pack)


def _render_r8(evidence_pack: EvidencePack | None) -> None:
    st.subheader("R8 Completed-Task Energy Candidate")
    st.caption(
        "The 1.50 J/task default and 10-task support minimum are provisional synthetic-development "
        "configuration, not a hardware benchmark, statistical anomaly test, or efficiency standard."
    )
    if not isinstance(evidence_pack, EvidencePack):
        st.info("An EvidencePack is required before R8 can be evaluated.")
        return
    controls = st.columns(2)
    threshold = float(
        controls[0].number_input(
            "Minimum energy per completed task (J/task)",
            min_value=0.0,
            value=1.50,
            step=0.10,
            format="%.2f",
        )
    )
    minimum_tasks = int(
        controls[1].number_input(
            "Minimum completed-task support",
            min_value=1,
            value=10,
            step=1,
        )
    )
    result = evaluate_energy_diagnostic_for_ui(
        evidence_pack,
        minimum_energy_per_completed_task_j=threshold,
        minimum_completed_tasks=minimum_tasks,
    )
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            st.code(result.detail)
        return
    summary = st.columns(3)
    summary[0].metric("R8 status", result.status.value)
    summary[1].metric(
        "Observed completed-task energy",
        _display_value(result.metadata.get("r8_observed_energy_per_completed_task_j")),
    )
    summary[2].metric("Categorical confidence", result.confidence.value)
    if result.status is RuleStatus.TRIGGERED:
        st.warning(result.hypothesis or "R8 identified the configured candidate pattern.")
    elif result.status is RuleStatus.CONFLICTING_EVIDENCE:
        st.info(result.hypothesis or "R8 found a high value with insufficient completed support.")
    elif result.status is RuleStatus.INSUFFICIENT_EVIDENCE:
        st.info("R8 admission failed; incompatible or missing evidence is shown below.")
    else:
        st.success("R8 did not identify the configured candidate pattern.")
    with st.expander("R8 evidence, alternatives, and limitations"):
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
        "Download R8 result (JSON)",
        data=result.model_dump_json(indent=2),
        file_name=f"{evidence_pack.pack_id}-r8.json",
        mime="application/json",
    )


def _coverage_caption(metrics: dict[str, MetricValue]) -> str:
    metric = metrics.get("task.energy.per_completed_j")
    if metric is None:
        return "Completed-task energy evidence is absent."
    fingerprint = metric.metadata.get("energy_contract_fingerprint", "unavailable")
    eligible = metric.metadata.get("eligible_count", "unavailable")
    population = metric.metadata.get("population_count", "unavailable")
    coverage = metric.metadata.get("coverage_fraction", "unavailable")
    return (
        f"Contract fingerprint: {fingerprint}. Completed-task eligibility: "
        f"{eligible}/{population}; "
        f"coverage: {coverage}."
    )


def _display_value(value: object) -> str:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f"{float(value):.6f} J/task"
    return "Unavailable"
