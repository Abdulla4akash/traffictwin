from __future__ import annotations

from traffictwin.provenance.query import build_provenance_context
from traffictwin.rendering.findings import (
    diagnostic_narrative_to_markdown,
    render_diagnostic_findings,
)
from traffictwin.rules.models import RuleStatus


def test_renderer_only_restates_structured_findings_and_actions() -> None:
    context = build_provenance_context("tests/fixtures/bundles/baseline_valid")
    report = context.diagnostic_report
    assert report is not None

    narrative = render_diagnostic_findings(report)
    markdown = diagnostic_narrative_to_markdown(narrative)

    assert narrative.source_report_id == report.report_id
    assert "performs no metric calculation" in narrative.introduction
    assert narrative.suppressed_rule_ids == (
        report.cross_rule_analysis.suppressed_rule_ids
        if report.cross_rule_analysis is not None
        else []
    )
    if report.cross_rule_analysis is not None:
        assert len(narrative.cross_rule_relationships) == len(
            report.cross_rule_analysis.relationships
        )
    for result, rendered in zip(report.results, narrative.rules, strict=True):
        assert rendered.rule_id == result.rule_id
        assert len(rendered.finding_sentences) == len(result.findings)
        for finding, sentence in zip(result.findings, rendered.finding_sentences, strict=True):
            assert finding.finding_id in sentence
            assert all(key in sentence for key in finding.evidence_keys)
            assert finding.statement in sentence
        if result.status not in {RuleStatus.TRIGGERED, RuleStatus.CONFLICTING_EVIDENCE}:
            assert "No diagnostic hypothesis is asserted" in rendered.summary
        assert len(rendered.conditional_actions) == len(result.recommendations)
        assert rendered.missing_evidence == result.missing_evidence
        assert rendered.alternative_explanations == result.alternative_explanations
        assert rendered.confidence_basis == result.confidence_basis
    assert markdown == diagnostic_narrative_to_markdown(narrative)
