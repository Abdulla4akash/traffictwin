"""Contract-gated task-energy evidence and R8 page."""

from __future__ import annotations

import streamlit as st

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricStatus, MetricValue
from traffictwin.rules.models import RuleStatus
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import metric_card, section_header
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import ServiceError, evaluate_energy_diagnostic_for_ui

# Human label (with explicit unit), metric key, and the unit token used to group
# comparable measures on the descriptive chart. The unit lives in the label so
# every energy card is a numeric-with-units st.metric.
ENERGY_FAMILY: tuple[tuple[str, str, str], ...] = (
    ("Observed-task energy (J)", "task.energy.mean_per_observed_task_j", "J"),
    ("Completed-task energy (J)", "task.energy.per_completed_j", "J"),
    ("Energy-delay product (J·ms)", "task.energy_delay_product.mean_j_ms", "J·ms"),
)


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

    _render_coverage_dashboard(metrics)
    _render_family_states(metrics)

    section_header("Contract-gated energy metrics")
    columns = st.columns(3)
    for column, (title, key, _unit) in zip(columns, ENERGY_FAMILY, strict=True):
        with column:
            metric_card(title, metrics.get(key))
    _render_joule_comparison(metrics)
    st.caption(_coverage_caption(metrics))

    _render_r8(analysis.evidence_pack)


def _render_coverage_dashboard(metrics: dict[str, MetricValue]) -> None:
    """Render a coverage-first KPI row over the energy family."""

    states = [_state_of(metrics.get(key)) for _title, key, _unit in ENERGY_FAMILY]
    completed = metrics.get("task.energy.per_completed_j")
    with st.container(border=True):
        st.markdown("**Energy-family coverage**")
        columns = st.columns(4)
        columns[0].metric("Available (metrics)", states.count("available"), border=True)
        columns[1].metric("Partial (metrics)", states.count("partial"), border=True)
        columns[2].metric(
            "Unavailable (metrics)",
            states.count("unavailable") + states.count("invalid"),
            border=True,
        )
        columns[3].metric(
            "Completed-task coverage (%)",
            _coverage_percentage(completed),
            help="Eligible completed tasks / population; not inferred when the contract is absent.",
            border=True,
        )
        st.caption(
            "Coverage counts describe how much of the declared energy contract is satisfied. A "
            "lower energy value is never, alone, evidence of efficiency or of a superior policy."
        )


def _render_family_states(metrics: dict[str, MetricValue]) -> None:
    """Separate the energy family into available, partial, and unavailable groups."""

    grouped: dict[str, list[str]] = {"available": [], "partial": [], "unavailable": []}
    for title, key, _unit in ENERGY_FAMILY:
        state = _state_of(metrics.get(key))
        bucket = "unavailable" if state in {"unavailable", "invalid"} else state
        grouped.setdefault(bucket, []).append(title)
    section_header("Energy families by evidence state")
    for state, label in (
        ("available", "Available"),
        ("partial", "Partial"),
        ("unavailable", "Unavailable"),
    ):
        members = grouped.get(state, [])
        badges = " ".join(badge_markdown(state) for _ in members) if members else ""
        listed = ", ".join(members) if members else "none"
        st.markdown(f"**{label}:** {badges} {listed}".rstrip())
    st.caption(
        "Randy/TOS per-task physical energy is not a supported measure; it stays unavailable "
        "wherever the canonical task-energy contract does not define it, rather than being filled."
    )


def _render_joule_comparison(metrics: dict[str, MetricValue]) -> None:
    """Chart the two joule-denominated energies when both are available and numeric."""

    rows = [
        {"Energy measure": title.replace(" (J)", ""), "Energy (J)": float(metric.value)}
        for title, key, unit in ENERGY_FAMILY
        if unit == "J"
        and (metric := metrics.get(key)) is not None
        and metric.status is MetricStatus.AVAILABLE
        and isinstance(metric.value, int | float)
        and not isinstance(metric.value, bool)
    ]
    if not rows:
        st.caption(
            "No joule-denominated energy value is available, so the descriptive comparison chart "
            "is omitted rather than drawn from missing or defaulted values."
        )
        return
    st.bar_chart(rows, x="Energy measure", y="Energy (J)", x_label="", y_label="Energy (J)")
    st.caption(
        "Descriptive comparison of already-computed joule values; the energy-delay product uses a "
        "different unit (J·ms) and is shown only as a metric. Bar height is not an efficiency or "
        "superiority ranking."
    )


def _render_r8(evidence_pack: EvidencePack | None) -> None:
    section_header("R8 completed-task energy candidate")
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
    with st.container(border=True):
        st.markdown(
            f"**R8 status:** {badge_markdown(result.status.value)} · "
            f"**Categorical confidence:** {badge_markdown(result.confidence.value)}"
        )
        st.metric(
            "Observed completed-task energy (J/task)",
            _display_value(result.metadata.get("r8_observed_energy_per_completed_task_j")),
            border=True,
        )
    if result.status is RuleStatus.TRIGGERED:
        st.warning(result.hypothesis or "R8 identified the configured candidate pattern.")
    elif result.status is RuleStatus.CONFLICTING_EVIDENCE:
        st.info(result.hypothesis or "R8 found a high value with insufficient completed support.")
    elif result.status is RuleStatus.INSUFFICIENT_EVIDENCE:
        st.info("R8 admission failed; incompatible or missing evidence is shown below.")
    else:
        st.success("R8 did not identify the configured candidate pattern.")
    with st.expander("Advanced: R8 evidence, alternatives, and limitations"):
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


def _state_of(metric: MetricValue | None) -> str:
    if metric is None:
        return "unavailable"
    return metric.status.value


def _coverage_percentage(metric: MetricValue | None) -> str:
    if metric is None:
        return "Unavailable"
    coverage = metric.metadata.get("coverage_fraction")
    if isinstance(coverage, int | float) and not isinstance(coverage, bool):
        return f"{100 * float(coverage):.1f}%"
    return "Unavailable"


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
