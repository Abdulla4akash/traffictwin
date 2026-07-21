"""Deterministic prose rendering of structured diagnostic findings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.rules.models import RuleResult, RuleStatus


class RenderedRuleNarrative(BaseModel):
    """Prose for one rule, traceable only to fields in its structured result."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title: str
    status: str
    summary: str
    finding_sentences: list[str] = Field(default_factory=list)
    conditional_actions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    confidence_basis: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DiagnosticNarrative(BaseModel):
    """Constrained narrative view over one immutable diagnostic report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    source_report_id: str
    overall_readiness: str
    synthetic: bool
    introduction: str
    cross_rule_relationships: list[str] = Field(default_factory=list)
    suppressed_rule_ids: list[str] = Field(default_factory=list)
    rules: list[RenderedRuleNarrative]
    limitations: list[str]

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)


def render_diagnostic_findings(report: DiagnosticReport) -> DiagnosticNarrative:
    """Render findings without calculating metrics or adding hypotheses."""

    cross_rule = report.cross_rule_analysis
    return DiagnosticNarrative(
        source_report_id=report.report_id,
        overall_readiness=report.overall_readiness.value,
        synthetic=report.synthetic,
        introduction=(
            "This text restates deterministic rule outputs. It performs no metric calculation, "
            "causal inference, or evidence generation."
        ),
        cross_rule_relationships=(
            [
                f"{relationship.relation_type.value}: {relationship.source_rule_id}/"
                f"{relationship.target_rule_id}: {relationship.statement} "
                f"[policy: {relationship.policy_id} {relationship.policy_version}]"
                for relationship in cross_rule.relationships
            ]
            if cross_rule is not None
            else []
        ),
        suppressed_rule_ids=(cross_rule.suppressed_rule_ids if cross_rule is not None else []),
        rules=[_render_rule(result) for result in report.results],
        limitations=[
            "Every finding sentence cites its source finding identifier and evidence keys.",
            "Recommendations remain conditional and reproduce declared prerequisites and checks.",
            "A triggered hypothesis is a diagnostic candidate, not a proven cause.",
            "Cross-rule relationships restate the typed policy output and retain every rule "
            "result.",
        ],
    )


def diagnostic_narrative_to_markdown(narrative: DiagnosticNarrative) -> str:
    """Render a constrained narrative as Markdown."""

    lines = [
        "# Deterministic Diagnostic Narrative",
        "",
        f"- Source report: `{narrative.source_report_id}`",
        f"- Overall readiness: `{narrative.overall_readiness}`",
        f"- Synthetic: `{narrative.synthetic}`",
        "",
        narrative.introduction,
        "",
    ]
    if narrative.cross_rule_relationships or narrative.suppressed_rule_ids:
        lines.extend(["## Cross-Rule Relationships", ""])
        lines.extend(f"- {item}" for item in narrative.cross_rule_relationships)
        if narrative.suppressed_rule_ids:
            lines.append(
                "- Suppressed for action only; original results retained: "
                + ", ".join(narrative.suppressed_rule_ids)
            )
        lines.append("")
    for rule in narrative.rules:
        lines.extend([f"## {rule.rule_id}: {rule.title}", "", rule.summary, ""])
        for sentence in rule.finding_sentences:
            lines.append(f"- {sentence}")
        for action in rule.conditional_actions:
            lines.append(f"- {action}")
        for item in rule.missing_evidence:
            lines.append(f"- Missing evidence: {item}")
        for item in rule.alternative_explanations:
            lines.append(f"- Alternative explanation: {item}")
        for item in rule.confidence_basis:
            lines.append(f"- Confidence basis: {item}")
        for limitation in rule.limitations:
            lines.append(f"- Limitation: {limitation}")
        lines.append("")
    lines.extend(["## Renderer Limitations", ""])
    lines.extend(f"- {item}" for item in narrative.limitations)
    return "\n".join(lines).rstrip() + "\n"


def _render_rule(result: RuleResult) -> RenderedRuleNarrative:
    asserts_hypothesis = result.status in {
        RuleStatus.TRIGGERED,
        RuleStatus.CONFLICTING_EVIDENCE,
    }
    if asserts_hypothesis and result.hypothesis:
        summary = (
            f"Status `{result.status.value}` with `{result.confidence.value}` confidence category. "
            f"Declared hypothesis: {result.hypothesis}"
        )
    else:
        summary = (
            f"Status `{result.status.value}` with `{result.confidence.value}` confidence category. "
            "No diagnostic hypothesis is asserted for this result."
        )
    findings = []
    for finding in result.findings:
        evidence = ", ".join(finding.evidence_keys) or "none"
        findings.append(
            f"{finding.statement} [finding: {finding.finding_id}; evidence: {evidence}; "
            f"support: {finding.support.value}]"
        )
    actions = [
        (
            f"Conditional action: {recommendation.action} Prerequisite: "
            f"{recommendation.prerequisite} Rationale: {recommendation.rationale} Expected "
            f"direction: {recommendation.expected_direction} Verification: "
            f"{recommendation.verification_step}"
        )
        for recommendation in result.recommendations
    ]
    return RenderedRuleNarrative(
        rule_id=result.rule_id,
        title=result.title,
        status=result.status.value,
        summary=summary,
        finding_sentences=findings,
        conditional_actions=actions,
        missing_evidence=result.missing_evidence,
        alternative_explanations=result.alternative_explanations,
        confidence_basis=result.confidence_basis,
        limitations=result.limitations,
    )
