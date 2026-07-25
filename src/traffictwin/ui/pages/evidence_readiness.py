"""Evidence & Diagnostic Hypotheses page."""

from __future__ import annotations

import streamlit as st

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.rendering.findings import (
    diagnostic_narrative_to_markdown,
    render_diagnostic_findings,
)
from traffictwin.rules.models import RuleStatus
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import render_fingerprint
from traffictwin.ui.labels import DIAGNOSTIC_NOTICE
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.tables import metric_rows, table_column_config


def render() -> None:
    """Render evidence readiness and deterministic hypotheses."""

    st.title("Evidence & Diagnostic Hypotheses")
    st.info(DIAGNOSTIC_NOTICE)
    analysis = load_selected_analysis()
    if analysis is None:
        return
    render_source_caption(analysis)
    validation_report = analysis.validation.report
    insufficient = analysis.validation.insufficient_evidence

    st.subheader("Validation status")
    with st.container(border=True):
        import_text = "may import" if validation_report.may_import else "may not import"
        st.markdown(
            f"{badge_markdown(validation_report.status.value)} — this bundle {import_text}."
        )
        severity_cols = st.columns(3)
        severity_cols[0].metric(
            "Errors", validation_report.counts_by_severity.get("error", 0), border=True
        )
        severity_cols[1].metric(
            "Warnings", validation_report.counts_by_severity.get("warning", 0), border=True
        )
        severity_cols[2].metric(
            "Fatal", validation_report.counts_by_severity.get("fatal", 0), border=True
        )
    with st.expander("Advanced: raw validation status JSON"):
        st.json(
            {
                "status": validation_report.status.value,
                "may_import": validation_report.may_import,
                "counts_by_severity": validation_report.counts_by_severity,
            }
        )

    st.subheader("Evidence availability")
    evidence_states = analysis.validation.evidence.model_dump(mode="json")
    grouped: dict[str, list[str]] = {}
    for category, state in evidence_states.items():
        grouped.setdefault(str(state), []).append(category.replace("_", " ").capitalize())
    # Group available, partial, blocked, and unavailable evidence separately so a
    # single flat dictionary no longer dominates. Every state stays visible.
    ordered_states = ["available", "partial", "blocked", "unavailable"]
    seen_states = [state for state in ordered_states if state in grouped]
    seen_states += [state for state in sorted(grouped) if state not in ordered_states]
    with st.container(border=True):
        summary = st.columns(len(seen_states) or 1)
        for column, state in zip(summary, seen_states, strict=False):
            column.metric(state.capitalize(), len(grouped[state]), border=True)
    # One badge table, ordered by state so the groups are visually contiguous.
    state_order = {state: index for index, state in enumerate(seen_states)}
    ordered_rows = sorted(
        evidence_states.items(),
        key=lambda item: (state_order.get(str(item[1]), len(seen_states)), item[0]),
    )
    st.table(
        [
            {
                "Group": str(state).capitalize(),
                "Evidence": category.replace("_", " ").capitalize(),
                "State": badge_markdown(str(state)),
            }
            for category, state in ordered_rows
        ]
    )
    with st.expander("Advanced: raw evidence availability JSON"):
        st.json(evidence_states)

    st.subheader("Diagnostic readiness")
    with st.container(border=True):
        if insufficient.diagnosis_allowed:
            st.markdown(f"{badge_markdown('available')} Deterministic diagnosis is allowed.")
        else:
            st.markdown(
                f"{badge_markdown('unavailable')} Deterministic diagnosis is not allowed "
                "for this bundle."
            )
        if insufficient.blocked_capabilities:
            st.markdown(
                "**Blocked capabilities:**\n"
                + "\n".join(f"- `{name}`" for name in insufficient.blocked_capabilities)
            )
        if insufficient.missing_evidence:
            st.markdown(
                "**Missing evidence:**\n"
                + "\n".join(f"- {item}" for item in insufficient.missing_evidence)
            )
    with st.expander("Advanced: raw diagnostic readiness JSON"):
        st.json(insufficient.model_dump(mode="json"))

    st.subheader("Metric collection summary")
    if analysis.metrics is not None:
        metric_cols = st.columns(3)
        metric_cols[0].metric("Metrics", len(analysis.metrics.results), border=True)
        metric_cols[1].metric("Unavailable", analysis.metrics.unavailable_count, border=True)
        metric_cols[2].metric("Partial", analysis.metrics.partial_count, border=True)
        with st.expander("Metric details"):
            detail_rows = metric_rows(analysis.metrics)
            st.dataframe(
                detail_rows,
                width="stretch",
                hide_index=True,
                column_config=table_column_config(detail_rows),
            )
        with st.expander("Advanced: metric collection identifiers"):
            st.code(
                f"run_id: {analysis.metrics.run_id}\n"
                f"metric_version: {analysis.metrics.metric_version}",
                language=None,
            )

    st.subheader("Evidence pack")
    if analysis.evidence_pack is None:
        st.info("Evidence pack is unavailable because the bundle was not accepted.")
    else:
        st.markdown(f"Evidence pack `{analysis.evidence_pack.pack_id}` is available.")
        render_fingerprint("Evidence pack fingerprint", analysis.evidence_pack.fingerprint())
        st.download_button(
            "Download EvidencePack JSON",
            data=analysis.evidence_pack.to_json(),
            file_name=f"{analysis.evidence_pack.pack_id}.json",
            mime="application/json",
        )

    st.subheader("Diagnostic report")
    if analysis.diagnostic_report is None:
        st.info("Diagnostic report is unavailable because the bundle was not accepted.")
        return

    diagnostic_report = analysis.diagnostic_report
    with st.container(border=True):
        st.markdown(
            f"**Overall readiness:** {badge_markdown(diagnostic_report.overall_readiness.value)}"
        )
        st.markdown(
            f"**Triggered:** {_rule_id_list(diagnostic_report.triggered_rule_ids)} · "
            f"**Insufficient:** {_rule_id_list(diagnostic_report.insufficient_rule_ids)} · "
            f"**Conflicting:** {_rule_id_list(diagnostic_report.conflicting_rule_ids)}"
        )
    with st.expander("Advanced: report identifiers"):
        st.code(
            f"report_id: {diagnostic_report.report_id}\n"
            f"ruleset_version: {diagnostic_report.ruleset_version}",
            language=None,
        )
    if diagnostic_report.conflict_observations:
        st.warning("\n".join(diagnostic_report.conflict_observations))
    with st.expander("Advanced: rule configuration thresholds"):
        st.json(diagnostic_report.rule_config.model_dump(mode="json"))

    _render_cross_rule_analysis(diagnostic_report)

    st.subheader("Original rule results")

    for result in diagnostic_report.results:
        label = f"{result.rule_id} - {result.title}"
        with st.expander(label, expanded=result.status is RuleStatus.TRIGGERED):
            st.markdown(
                f"{badge_markdown(result.status.value)} "
                f"**Confidence:** {badge_markdown(result.confidence.value)}"
            )
            st.caption(f"Rule version: {result.rule_version}")
            if result.hypothesis:
                st.markdown(f"**Candidate hypothesis:** {result.hypothesis}")
            if result.confidence_basis:
                st.markdown(
                    "**Confidence basis**\n"
                    + "\n".join(f"- {item}" for item in result.confidence_basis)
                )
            if result.supporting_evidence:
                st.markdown("**Supporting findings**")
                supporting_rows = [
                    finding.model_dump(mode="json") for finding in result.supporting_evidence
                ]
                st.dataframe(
                    supporting_rows,
                    width="stretch",
                    hide_index=True,
                    column_config=table_column_config(supporting_rows),
                )
            if result.contradicting_evidence:
                st.markdown("**Contradicting findings**")
                contradicting_rows = [
                    finding.model_dump(mode="json") for finding in result.contradicting_evidence
                ]
                st.dataframe(
                    contradicting_rows,
                    width="stretch",
                    hide_index=True,
                    column_config=table_column_config(contradicting_rows),
                )
            if result.missing_evidence:
                st.markdown(
                    "**Missing evidence**\n"
                    + "\n".join(f"- {item}" for item in result.missing_evidence)
                )
            if result.alternative_explanations:
                st.markdown(
                    "**Alternative explanations**\n"
                    + "\n".join(f"- {item}" for item in result.alternative_explanations)
                )
            if result.recommendations:
                st.markdown("**Conditional recommendations**")
                recommendation_rows = [
                    recommendation.model_dump(mode="json")
                    for recommendation in result.recommendations
                ]
                st.dataframe(
                    recommendation_rows,
                    width="stretch",
                    hide_index=True,
                    column_config=table_column_config(recommendation_rows),
                )
            if result.limitations:
                st.markdown(
                    "**Limitations**\n" + "\n".join(f"- {item}" for item in result.limitations)
                )

    st.download_button(
        "Download DiagnosticReport JSON",
        data=diagnostic_report.to_json(),
        file_name=f"{diagnostic_report.report_id}.json",
        mime="application/json",
    )
    with st.expander("Constrained deterministic narrative", expanded=False):
        narrative = render_diagnostic_findings(diagnostic_report)
        narrative_markdown = diagnostic_narrative_to_markdown(narrative)
        st.caption(
            "This renderer restates structured findings; it does not calculate metrics or add "
            "diagnostic claims."
        )
        display_markdown = narrative_markdown.replace(
            "# Deterministic Diagnostic Narrative",
            "### Deterministic Diagnostic Narrative",
            1,
        )
        st.markdown(display_markdown)
        st.download_button(
            "Download narrative Markdown",
            data=narrative_markdown,
            file_name=f"{diagnostic_report.report_id}-narrative.md",
        )


def _rule_id_list(rule_ids: list[str]) -> str:
    """Return rule identifiers as inline code, keeping emptiness explicit."""

    if not rule_ids:
        return "none"
    return ", ".join(f"`{rule_id}`" for rule_id in rule_ids)


def _render_cross_rule_analysis(diagnostic_report: DiagnosticReport) -> None:
    """Render the typed additive relationship report without deriving relationships in the UI."""

    st.subheader("Cross-rule relationships")
    analysis = diagnostic_report.cross_rule_analysis
    if analysis is None:
        st.info("Typed DIA-07 cross-rule analysis is unavailable for this historical report.")
        return
    st.caption(
        "Relationships are deterministic context records, not probabilities or root-cause "
        "rankings. Every original RuleResult remains visible below."
    )
    summary = st.columns(4)
    summary[0].metric("Conflicts", analysis.counts_by_type["conflict"])
    summary[1].metric("Corroborations", analysis.counts_by_type["corroboration"])
    summary[2].metric("Suppressed for action", analysis.counts_by_type["suppression"])
    summary[3].metric("Retained results", len(analysis.retained_rule_ids))

    if analysis.suppressed_rule_ids:
        st.warning(
            "Presentation suppression applies to "
            f"{', '.join(analysis.suppressed_rule_ids)}. These results are retained below with "
            "their original status and reason."
        )
    if analysis.relationships:
        relationship_rows = [
            {
                "type": relationship.relation_type.value,
                "source": relationship.source_rule_id,
                "target": relationship.target_rule_id,
                "shared_evidence": ", ".join(relationship.shared_evidence_keys) or "—",
                "source_precedence": relationship.source_precedence,
                "target_precedence": relationship.target_precedence,
                "presentation_effect": relationship.presentation_effect,
                "statement": relationship.statement,
            }
            for relationship in analysis.relationships
        ]
        st.dataframe(
            relationship_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(relationship_rows),
        )
    else:
        st.info("No relationship was activated by the declared DIA-07 v1 policy.")
    if analysis.unclassified_triggered_rule_ids:
        st.caption(
            "Triggered rules with no declared relationship: "
            + ", ".join(analysis.unclassified_triggered_rule_ids)
            + ". No relationship is inferred."
        )
    with st.expander("Advanced: cross-rule policy, provenance, and limitations"):
        st.json(
            {
                "analysis_id": analysis.analysis_id,
                "policy_version": analysis.policy_version,
                "status": analysis.status.value,
                "provenance": analysis.provenance,
                "warnings": analysis.warnings,
                "limitations": analysis.limitations,
                "fingerprint": analysis.fingerprint(),
            }
        )
    st.download_button(
        "Download CrossRuleReasoningReport JSON",
        data=analysis.to_json(),
        file_name=f"{analysis.analysis_id}.json",
        mime="application/json",
    )
