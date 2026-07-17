"""Serialisable validation reports."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.validation.findings import Severity, ValidationFinding

VALIDATOR_VERSION = "phase2.1"


class ImportStatus(StrEnum):
    """Overall import status."""

    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    REJECTED = "rejected"


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


class ValidationReport(BaseModel):
    """Complete validation report for a run bundle."""

    model_config = ConfigDict(extra="forbid")

    bundle_id: str | None = None
    run_id: str | None = None
    status: ImportStatus = ImportStatus.REJECTED
    may_import: bool = False
    findings: list[ValidationFinding] = Field(default_factory=list)
    counts_by_severity: dict[str, int] = Field(default_factory=dict)
    files_inspected: list[str] = Field(default_factory=list)
    canonical_record_counts: dict[str, int] = Field(default_factory=dict)
    unavailable_evidence_categories: list[str] = Field(default_factory=list)
    available_evidence_categories: list[str] = Field(default_factory=list)
    import_timestamp: datetime = Field(default_factory=utc_now)
    validator_version: str = VALIDATOR_VERSION

    def add(self, finding: ValidationFinding) -> None:
        """Append a finding."""

        self.findings.append(finding)

    def finalise(self) -> None:
        """Update derived status and count fields."""

        self.counts_by_severity = {severity.value: 0 for severity in Severity}
        for finding in self.findings:
            self.counts_by_severity[finding.severity.value] += 1

        self.may_import = all(finding.may_continue for finding in self.findings)
        if not self.may_import:
            self.status = ImportStatus.REJECTED
        elif any(finding.severity is not Severity.INFO for finding in self.findings):
            self.status = ImportStatus.ACCEPTED_WITH_WARNINGS
        else:
            self.status = ImportStatus.ACCEPTED

    def to_json(self) -> str:
        """Return deterministic JSON output."""

        return self.model_dump_json(indent=2)
