"""Diagnostic rule result models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.metrics.results import JsonScalar, JsonValue


class RuleStatus(StrEnum):
    """Rule evaluation status."""

    TRIGGERED = "triggered"
    NOT_TRIGGERED = "not_triggered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    INVALID = "invalid"


class ConfidenceCategory(StrEnum):
    """Categorical confidence derived from evidence completeness, not probability."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNAVAILABLE = "unavailable"


class FindingSupport(StrEnum):
    """Direction of a finding relative to a rule hypothesis."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class Finding(BaseModel):
    """One evidence-linked rule finding."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    statement: str
    evidence_keys: list[str] = Field(default_factory=list)
    observed_values: dict[str, JsonValue] = Field(default_factory=dict)
    expected_condition: str
    support: FindingSupport


class Recommendation(BaseModel):
    """Conditional follow-up action suggested by a deterministic rule."""

    model_config = ConfigDict(extra="forbid")

    action: str
    rationale: str
    expected_direction: str
    prerequisite: str
    verification_step: str
    conditional: bool = True


class RuleResult(BaseModel):
    """Structured result from one deterministic diagnostic rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_version: str
    title: str
    status: RuleStatus
    hypothesis: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    evidence_keys: list[str] = Field(default_factory=list)
    supporting_evidence: list[Finding] = Field(default_factory=list)
    contradicting_evidence: list[Finding] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    confidence: ConfidenceCategory = ConfidenceCategory.UNAVAILABLE
    confidence_basis: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    synthetic: bool
    evaluated_at: datetime
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)


def result_from_findings(
    *,
    rule_id: str,
    rule_version: str,
    title: str,
    status: RuleStatus,
    synthetic: bool,
    evaluated_at: datetime,
    hypothesis: str | None = None,
    findings: list[Finding] | None = None,
    missing_evidence: list[str] | None = None,
    alternative_explanations: list[str] | None = None,
    recommendations: list[Recommendation] | None = None,
    confidence: ConfidenceCategory = ConfidenceCategory.UNAVAILABLE,
    confidence_basis: list[str] | None = None,
    limitations: list[str] | None = None,
    metadata: dict[str, JsonScalar] | None = None,
) -> RuleResult:
    """Build a result with derived evidence-key and support lists."""

    all_findings = findings or []
    supporting = [finding for finding in all_findings if finding.support is FindingSupport.SUPPORTS]
    contradicting = [
        finding for finding in all_findings if finding.support is FindingSupport.CONTRADICTS
    ]
    evidence_keys = sorted({key for finding in all_findings for key in finding.evidence_keys})
    return RuleResult(
        rule_id=rule_id,
        rule_version=rule_version,
        title=title,
        status=status,
        hypothesis=hypothesis,
        findings=all_findings,
        evidence_keys=evidence_keys,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        missing_evidence=missing_evidence or [],
        alternative_explanations=alternative_explanations or [],
        recommendations=recommendations or [],
        confidence=confidence,
        confidence_basis=confidence_basis or [],
        limitations=limitations or [],
        synthetic=synthetic,
        evaluated_at=evaluated_at,
        metadata=metadata or {},
    )
