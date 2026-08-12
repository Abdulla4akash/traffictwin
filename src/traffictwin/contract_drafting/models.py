"""Strict typed models for Multi-Sample Data Contract Drafting Assistant.

Portable identity excludes wall clock, rendering state, local paths and
secrets. All models use ``extra='forbid'`` at the boundary.

Consensus logic:
- field presence frequency
- observed logical types
- nullable frequency
- timestamp parse-state consistency
- timezone consistency
- numeric precision and scale ranges
- categorical distinct-count ranges
- structural aggregate hashes
- fields appearing/disappearing
- confidence
- unresolved disagreements

Portable outputs must not contain raw categorical values.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.data_contract.models import LogicalType

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]{0,127}$")
_SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-:]{0,127}$")

MAX_SAMPLES = 20
MIN_SAMPLES = 2
MAX_FIELD_NAME_LEN = 128


def _validate_field_name(value: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            "field_name must start with a letter and contain only letters, numbers, "
            "dots, underscores, or hyphens (1-128 chars)"
        )
    return value


class StrictModel(BaseModel):
    """Base model with strict validation."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class FrozenStrictModel(BaseModel):
    """Base model for frozen artifacts."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DraftingConfidence(StrEnum):
    """Confidence in a field or overall draft."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CONFLICTED = "conflicted"


class DraftingFindingSeverity(StrEnum):
    """Severity of a drafting finding."""

    INFO = "info"
    WARNING = "warning"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Request / Reference
# ---------------------------------------------------------------------------


class SampleProfileReference(StrictModel):
    """Reference to one profiled sample (portable, no raw paths)."""

    sample_index: int = Field(ge=0, le=19)
    observation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    redacted_label: str = Field(min_length=1, max_length=128)
    total_observed_rows: int = Field(ge=0)
    field_count: int = Field(ge=1)
    truncated: bool = False
    is_valid: bool = True
    error_code: str | None = Field(default=None, max_length=64)


class ContractDraftingRequest(StrictModel):
    """Bounded request to profile 2-20 local tabular samples.

    Paths are validated for workspace containment and suffix allowlist at
    service time. This model captures the validated request identity without
    persisting absolute paths in portable fingerprints.
    """

    # Use strings for paths to avoid Path contamination in fingerprint;
    # service resolves and validates.
    sample_paths: list[str] = Field(min_length=2, max_length=20)
    max_rows: int = Field(default=5000, ge=1, le=10000)
    max_bytes: int = Field(default=5_000_000, ge=1024, le=10_000_000)
    source_id_hint: str | None = Field(default=None, max_length=128)
    user_unit_suggestions: dict[str, str] | None = Field(default=None)
    authoritative_contract_source_id: str | None = Field(default=None, max_length=128)

    @field_validator("sample_paths")
    @classmethod
    def validate_paths_not_empty(cls, value: list[str]) -> list[str]:
        for p in value:
            if not p.strip():
                raise ValueError("sample_paths must contain non-empty strings")
        if len(value) != len(set(value)):
            raise ValueError("sample_paths must contain unique entries")
        return value

    @field_validator("source_id_hint")
    @classmethod
    def validate_source_hint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("source_id_hint must be non-empty when provided")
        if not _SOURCE_ID_RE.fullmatch(value.strip()):
            raise ValueError("source_id_hint must be alphanumeric identifier (1-128 chars)")
        return value.strip()

    @field_validator("user_unit_suggestions")
    @classmethod
    def validate_suggestions(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        if len(value) > 64:
            raise ValueError("user_unit_suggestions exceeds maximum 64 entries")
        for k, v in value.items():
            _validate_field_name(k)
            if not v.strip():
                raise ValueError(f"unit suggestion for {k!r} must be non-empty")
            if len(v.strip()) > 64:
                raise ValueError(f"unit suggestion for {k!r} exceeds 64 chars")
        return {k: v.strip() for k, v in value.items()}


# ---------------------------------------------------------------------------
# Consensus models
# ---------------------------------------------------------------------------


class FieldPresenceSummary(StrictModel):
    """Presence frequency for one field across samples."""

    field_name: str = Field(min_length=1, max_length=128)
    present_in_samples: int = Field(ge=0)
    total_samples: int = Field(ge=2, le=20)
    presence_frequency: float = Field(ge=0.0, le=1.0)
    is_stable: bool = False
    is_optional: bool = False
    appears_in: list[int] = Field(default_factory=list)
    missing_in: list[int] = Field(default_factory=list)

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)

    @model_validator(mode="after")
    def validate_consistency(self) -> FieldPresenceSummary:
        if self.present_in_samples > self.total_samples:
            raise ValueError("present_in_samples must not exceed total_samples")
        # Derive expectation: frequency should match count
        expected = self.present_in_samples / self.total_samples if self.total_samples > 0 else 0.0
        if abs(self.presence_frequency - expected) > 1e-9:
            raise ValueError("presence_frequency inconsistent with counts")
        return self


class TypeConsensus(StrictModel):
    """Observed logical types for one field."""

    field_name: str = Field(min_length=1, max_length=128)
    observed_types: list[LogicalType] = Field(min_length=1)
    type_frequencies: dict[str, int] = Field(default_factory=dict)
    consensus_type: LogicalType | None = None
    is_conflicting: bool = False
    is_unresolved: bool = False

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)

    @field_validator("observed_types")
    @classmethod
    def validate_types(cls, value: list[LogicalType]) -> list[LogicalType]:
        if len(value) != len(set(value)):
            raise ValueError("observed_types must be unique")
        return value


class TimestampConsensus(StrictModel):
    """Timestamp parse-state and timezone consistency per field."""

    field_name: str = Field(min_length=1, max_length=128)
    parse_states: list[str] = Field(default_factory=list)
    parse_state_frequencies: dict[str, int] = Field(default_factory=dict)
    observed_timezones: list[str] = Field(default_factory=list)
    is_mixed_timezone: bool = False
    is_ambiguous: bool = False
    is_consistent: bool = True

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)


class NumericConsensus(StrictModel):
    """Numeric precision/scale ranges per field."""

    field_name: str = Field(min_length=1, max_length=128)
    has_numeric_observations: bool = False
    precision_min: int | None = Field(default=None, ge=0)
    precision_max: int | None = Field(default=None, ge=0)
    scale_min: int | None = Field(default=None, ge=0)
    scale_max: int | None = Field(default=None, ge=0)
    precision_range: list[int] | None = None
    scale_range: list[int] | None = None
    is_unavailable: bool = False
    # min/max values only where safe — we do not store raw extrema if unavailable
    observed_min: float | None = None
    observed_max: float | None = None
    is_min_max_available: bool = False

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)

    @model_validator(mode="after")
    def validate_ranges(self) -> NumericConsensus:
        if (
            self.precision_min is not None
            and self.precision_max is not None
            and self.precision_min > self.precision_max
        ):
            raise ValueError("precision_min must not exceed precision_max")
        if (
            self.scale_min is not None
            and self.scale_max is not None
            and self.scale_min > self.scale_max
        ):
            raise ValueError("scale_min must not exceed scale_max")
        return self


class CategoricalConsensus(StrictModel):
    """Categorical distinct-count ranges and structural aggregate hashes.

    Portable output must not contain raw categorical values — only counts and
    deterministic SHA-256 hashes over sorted distinct values.
    """

    field_name: str = Field(min_length=1, max_length=128)
    has_categorical_observations: bool = False
    distinct_count_min: int | None = Field(default=None, ge=0)
    distinct_count_max: int | None = Field(default=None, ge=0)
    distinct_count_range: list[int] | None = None
    aggregate_hashes: list[str] = Field(default_factory=list)
    is_hash_stable: bool = False
    is_unavailable: bool = False

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)

    @field_validator("aggregate_hashes")
    @classmethod
    def validate_hashes(cls, value: list[str]) -> list[str]:
        for h in value:
            if not re.fullmatch(r"[0-9a-f]{64}", h):
                raise ValueError("aggregate hash must be 64 hex chars")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> CategoricalConsensus:
        if (
            self.distinct_count_min is not None
            and self.distinct_count_max is not None
            and self.distinct_count_min > self.distinct_count_max
        ):
            raise ValueError("distinct_count_min must not exceed distinct_count_max")
        return self


class FieldConsensus(StrictModel):
    """Aggregated consensus for one field across all samples."""

    field_name: str = Field(min_length=1, max_length=128)
    presence: FieldPresenceSummary
    type_consensus: TypeConsensus
    timestamp_consensus: TimestampConsensus | None = None
    numeric_consensus: NumericConsensus | None = None
    categorical_consensus: CategoricalConsensus | None = None
    nullable_frequency: float = Field(ge=0.0, le=1.0)
    nullable_in_samples: int = Field(ge=0)
    total_observed_samples: int = Field(ge=0)
    structural_aggregate_hashes: list[str] = Field(default_factory=list)
    is_unresolved: bool = False

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)


class DraftingFinding(StrictModel):
    """One unresolved disagreement or observation."""

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9_]+$")
    field_name: str | None = Field(default=None, max_length=128)
    severity: DraftingFindingSeverity = DraftingFindingSeverity.INFO
    message: str = Field(min_length=1, max_length=512)
    details: dict[str, str | int | float | bool | None] | None = None

    @field_validator("field_name")
    @classmethod
    def validate_field(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_field_name(value)


class DraftFieldRecommendation(StrictModel):
    """Recommended but not asserted draft for one field.

    Units must remain ``unknown`` or user-supplied suggestion unless
    explicitly present in an authoritative input contract.
    """

    field_name: str = Field(min_length=1, max_length=128)
    recommended_required: bool = False
    candidate_logical_type: LogicalType = LogicalType.STRING
    recommended_nullable: bool = False
    timestamp_semantics: TimestampConsensus | None = None
    # For draft: expose TimestampContract-like semantics separately
    timestamp_contract: dict[str, str | bool | None] | None = None
    numeric_precision: int | None = Field(default=None, ge=0)
    numeric_scale: int | None = Field(default=None, ge=0)
    unit: str = Field(default="unknown", max_length=64)
    privacy_review_required: bool = False
    confidence: DraftingConfidence = DraftingConfidence.MEDIUM
    rationale: str = Field(min_length=1, max_length=1024)

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("unit must be non-empty")
        return value.strip()


class ContractDraftReport(StrictModel):
    """Reviewable draft report profiling 2-20 samples.

    Portable identity excludes wall clock, absolute paths, and raw categorical
    values. Fingerprint is deterministic and order-independent.
    """

    schema_version: Literal["1.0"] = "1.0"
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_references: list[SampleProfileReference] = Field(min_length=2, max_length=20)
    field_consensus: list[FieldConsensus] = Field(min_length=1)
    draft_fields: list[DraftFieldRecommendation] = Field(min_length=1)
    findings: list[DraftingFinding] = Field(default_factory=list)
    overall_confidence: DraftingConfidence = DraftingConfidence.MEDIUM
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_only: bool = True
    freeze_executed: bool = False
    human_review_required: bool = True
    total_samples: int = Field(ge=2, le=20)
    # Structural hashes for portable verification
    structural_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("sample_references")
    @classmethod
    def validate_refs(cls, value: list[SampleProfileReference]) -> list[SampleProfileReference]:
        indices = [r.sample_index for r in value]
        if len(indices) != len(set(indices)):
            raise ValueError("sample_references must have unique sample_index")
        return value


class DraftContractHandoff(StrictModel):
    """Handoff exporting a draft compatible with SourceDataContract editing.

    Must state draft_only=True, freeze_executed=False, human_review_required=True
    and must not call freeze service automatically.
    """

    schema_version: Literal["1.0"] = "1.0"
    handoff_id: str = Field(min_length=1, max_length=64)
    report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_contract: dict[str, object] = Field(description="SourceDataContract JSON-serialised")
    draft_only: Literal[True] = True
    freeze_executed: Literal[False] = False
    human_review_required: Literal[True] = True
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_from_samples: int = Field(ge=2, le=20)
    notes: str | None = Field(default=None, max_length=1024)
