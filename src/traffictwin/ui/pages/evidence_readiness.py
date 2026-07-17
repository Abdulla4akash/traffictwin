"""Evidence & Diagnostic Hypotheses page."""

from __future__ import annotations

import streamlit as st

from traffictwin.rules.models import RuleStatus
from traffictwin.ui.labels import DIAGNOSTIC_NOTICE
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.tables import metric_rows


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

    st.subheader("Validation Status")
    st.json(
        {
            "status": validation_report.status.value,
            "may_import": validation_report.may_import,
            "counts_by_severity": validation_report.counts_by_severity,
        }
    )

    st.subheader("Evidence Availability")
    st.json(analysis.validation.evidence.model_dump(mode="json"))

    st.subheader("Diagnostic Readiness")
    st.json(insufficient.model_dump(mode="json"))

    st.subheader("Metric Collection Summary")
    if analysis.metrics is not None:
        st.write(
            {
                "run_id": analysis.metrics.run_id,
                "metric_version": analysis.metrics.metric_version,
                "metric_count": len(analysis.metrics.results),
                "unavailable_count": analysis.metrics.unavailable_count,
                "partial_count": analysis.metrics.partial_count,
            }
        )
        with st.expander("Metric details"):
            st.dataframe(metric_rows(analysis.metrics), width="stretch", hide_index=True)

    st.subheader("Evidence Pack")
    if analysis.evidence_pack is None:
        st.info("Evidence pack is unavailable because the bundle was not accepted.")
    else:
        st.write(
            {
                "pack_id": analysis.evidence_pack.pack_id,
                "fingerprint": analysis.evidence_pack.fingerprint(),
            }
        )
        st.download_button(
            "Download EvidencePack JSON",
            data=analysis.evidence_pack.to_json(),
            file_name=f"{analysis.evidence_pack.pack_id}.json",
            mime="application/json",
        )

    st.subheader("Rule Results")
    if analysis.diagnostic_report is None:
        st.info("Diagnostic report is unavailable because the bundle was not accepted.")
        return

    diagnostic_report = analysis.diagnostic_report
    st.write(
        {
            "report_id": diagnostic_report.report_id,
            "overall_readiness": diagnostic_report.overall_readiness.value,
            "ruleset_version": diagnostic_report.ruleset_version,
            "triggered": diagnostic_report.triggered_rule_ids,
            "insufficient": diagnostic_report.insufficient_rule_ids,
            "conflicting": diagnostic_report.conflicting_rule_ids,
        }
    )
    if diagnostic_report.conflict_observations:
        st.warning("\n".join(diagnostic_report.conflict_observations))
    with st.expander("Rule configuration thresholds"):
        st.json(diagnostic_report.rule_config.model_dump(mode="json"))

    for result in diagnostic_report.results:
        label = f"{result.rule_id} - {result.title}"
        with st.expander(label, expanded=result.status is RuleStatus.TRIGGERED):
            st.write(
                {
                    "status": result.status.value,
                    "confidence": result.confidence.value,
                    "rule_version": result.rule_version,
                }
            )
            if result.hypothesis:
                st.markdown(f"**Candidate hypothesis:** {result.hypothesis}")
            if result.confidence_basis:
                st.markdown("**Confidence basis**")
                st.write(result.confidence_basis)
            if result.supporting_evidence:
                st.markdown("**Supporting findings**")
                st.write(
                    [finding.model_dump(mode="json") for finding in result.supporting_evidence]
                )
            if result.contradicting_evidence:
                st.markdown("**Contradicting findings**")
                st.write(
                    [finding.model_dump(mode="json") for finding in result.contradicting_evidence]
                )
            if result.missing_evidence:
                st.markdown("**Missing evidence**")
                st.write(result.missing_evidence)
            if result.alternative_explanations:
                st.markdown("**Alternative explanations**")
                st.write(result.alternative_explanations)
            if result.recommendations:
                st.markdown("**Conditional recommendations**")
                st.write(
                    [
                        recommendation.model_dump(mode="json")
                        for recommendation in result.recommendations
                    ]
                )
            if result.limitations:
                st.markdown("**Limitations**")
                st.write(result.limitations)

    st.download_button(
        "Download DiagnosticReport JSON",
        data=diagnostic_report.to_json(),
        file_name=f"{diagnostic_report.report_id}.json",
        mime="application/json",
    )
