"""Minimal R0-compatible insufficient-evidence output."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.validation.report import ValidationReport


class InsufficientEvidenceSummary(BaseModel):
    """Minimal compatibility structure for future R0."""

    model_config = ConfigDict(extra="forbid")

    diagnosis_allowed: bool
    blocked_capabilities: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    validation_summary: dict[str, int] = Field(default_factory=dict)


def build_insufficient_evidence_summary(
    report: ValidationReport,
    evidence: EvidenceAvailability,
) -> InsufficientEvidenceSummary:
    """Convert validation and evidence state into future R0-compatible output."""

    missing = evidence.unavailable_categories()
    blocked = sorted(
        {capability for finding in report.findings for capability in finding.affected_capabilities}
    )
    diagnosis_allowed = (
        report.may_import and evidence.diagnosis is EvidenceStatus.AVAILABLE and not missing
    )
    return InsufficientEvidenceSummary(
        diagnosis_allowed=diagnosis_allowed,
        blocked_capabilities=blocked,
        missing_evidence=missing,
        validation_summary=report.counts_by_severity,
    )
