"""Report-export models."""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from traffictwin.annotations import (
    MAX_ANNOTATIONS_PER_REPORT,
    AnalystAnnotation,
    AnalystArtifactReference,
)


class ResearchReportType(StrEnum):
    """Supported typed report surfaces for claim inventories."""

    RUN = "run"
    DIAGNOSTICS = "diagnostics"
    COMPARISON = "comparison"
    FULL = "full"
    EXTERNAL = "external"


class ReportClaimKind(StrEnum):
    """Computed artifact kinds that count as report claims."""

    METRIC_RESULT = "metric_result"
    RULE_RESULT = "rule_result"
    METRIC_COMPARISON = "metric_comparison"


class ReportClaimAvailability(StrEnum):
    """Whether one typed report claim is eligible for exact structured comparison."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ReportClaimReference(BaseModel):
    """One typed computed claim included in a rendered report."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=1_024)
    claim_kind: ReportClaimKind
    artifact_key: str = Field(
        min_length=1,
        max_length=512,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    )
    section: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=4_000)

    @property
    def scientific_key(self) -> str:
        """Return the report-independent typed identity used by REP-03."""

        return f"{self.claim_kind.value}:{self.artifact_key}"


class ReportClaimSnapshot(BaseModel):
    """Renderer-independent typed scientific content for one report claim."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=1_024)
    claim_kind: ReportClaimKind
    artifact_key: str = Field(
        min_length=1,
        max_length=512,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    )
    section: str = Field(min_length=1, max_length=256)
    availability: ReportClaimAvailability
    status: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    value: Any = None
    unit: str | None = Field(default=None, max_length=128)
    reason_codes: list[str] = Field(default_factory=list, max_length=100)
    details: dict[str, Any] = Field(default_factory=dict, max_length=100)

    @property
    def scientific_key(self) -> str:
        """Return the report-independent typed identity used by REP-03."""

        return f"{self.claim_kind.value}:{self.artifact_key}"

    def scientific_payload(self) -> dict[str, Any]:
        """Return only deterministic typed content admitted to scientific diffing."""

        return {
            "availability": self.availability.value,
            "status": self.status,
            "value": self.value,
            "unit": self.unit,
            "reason_codes": self.reason_codes,
            "details": self.details,
        }

    @field_validator("value", "details")
    @classmethod
    def validate_json_content(cls, value: object) -> object:
        """Reject non-JSON and non-finite content at the report boundary."""

        _validate_json_content(value)
        return value

    @field_validator("reason_codes")
    @classmethod
    def validate_reason_codes(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 256 for item in value):
            msg = "report claim reason codes must contain 1 to 256 characters"
            raise ValueError(msg)
        return value


class ReportClaimExclusion(BaseModel):
    """One visible category intentionally excluded from the score denominator."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    examples: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Deterministic report payload rendered to Markdown or HTML."""

    model_config = ConfigDict(extra="forbid")

    payload_schema_version: str = Field(default="1.0", min_length=1, max_length=16)
    report_id: str
    title: str
    generated_at: datetime
    source_reference: str
    synthetic: bool
    sections: list[tuple[str, list[str]]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    report_type: ResearchReportType = ResearchReportType.EXTERNAL
    claim_denominator_definition: str = (
        "Typed computed metric, diagnostic, and comparison claims explicitly referenced by this "
        "report; headings, prose, metadata, warnings, and commands are excluded."
    )
    claim_references: list[ReportClaimReference] = Field(default_factory=list)
    claim_snapshots: list[ReportClaimSnapshot] = Field(default_factory=list, max_length=500)
    claim_exclusions: list[ReportClaimExclusion] = Field(default_factory=list)
    annotation_targets: list[AnalystArtifactReference] = Field(default_factory=list)
    analyst_annotations: list[AnalystAnnotation] = Field(
        default_factory=list,
        max_length=MAX_ANNOTATIONS_PER_REPORT,
    )


class ReportBuildError(RuntimeError):
    """Raised when a requested report cannot be built safely."""


def _validate_json_content(value: object, *, depth: int = 0) -> None:
    if depth > 10:
        msg = "report claim JSON content exceeds the maximum nesting depth"
        raise ValueError(msg)
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and len(value) > 4_000:
            msg = "report claim JSON strings cannot exceed 4,000 characters"
            raise ValueError(msg)
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = "report claim JSON numbers must be finite"
            raise ValueError(msg)
        return
    if isinstance(value, list):
        if len(value) > 1_000:
            msg = "report claim JSON lists cannot exceed 1,000 entries"
            raise ValueError(msg)
        for item in value:
            _validate_json_content(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 1_000 or any(not isinstance(key, str) for key in value):
            msg = "report claim JSON objects require string keys and at most 1,000 entries"
            raise ValueError(msg)
        for key, item in value.items():
            if len(key) > 256:
                msg = "report claim JSON keys cannot exceed 256 characters"
                raise ValueError(msg)
            _validate_json_content(item, depth=depth + 1)
        return
    msg = f"report claim content must be JSON-compatible, got {type(value).__name__}"
    raise ValueError(msg)
