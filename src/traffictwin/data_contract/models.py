"""Strict typed models for the Data Contract & Schema Drift workbench.

Portable identity excludes wall clock, rendering state, local paths and
secrets. All models use ``extra='forbid'`` at the boundary.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]{0,127}$")
_SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-:]{0,127}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _validate_field_name(value: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            "field_name must start with a letter and contain only letters, numbers, "
            "dots, underscores, or hyphens (1-128 chars)"
        )
    return value


def _validate_source_id(value: str) -> str:
    if not _SOURCE_ID_RE.fullmatch(value):
        raise ValueError(
            "source_id must start with alphanumeric and contain only letters, numbers, "
            "dots, underscores, colons, hyphens (1-128 chars)"
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
    """Base model for frozen contracts (immutable after creation)."""

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


class LogicalType(StrEnum):
    """Logical type of a field."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DECIMAL = "decimal"
    CATEGORICAL = "categorical"


class TimeBasis(StrEnum):
    """Declared time basis for timestamp fields."""

    UNIX_EPOCH_SECONDS = "unix_epoch_seconds"
    UNIX_EPOCH_MILLISECONDS = "unix_epoch_milliseconds"
    ISO8601 = "iso8601"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class TimezoneSemantics(StrEnum):
    """Timezone semantics for timestamp fields."""

    UTC = "UTC"
    EUROPE_LONDON = "Europe/London"
    NAIVE_LOCAL = "naive_local"
    NAIVE_UTC_ASSUMED = "naive_utc_assumed"
    UNKNOWN = "unknown"


class PublicationClass(StrEnum):
    """Privacy / publication classification."""

    PRIVATE = "private"
    INTERNAL = "internal"
    AGGREGATED_ONLY = "aggregated_only"
    OPEN = "open"


class SchemaDriftSeverity(StrEnum):
    """Severity of a single drift finding."""

    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"
    COMPATIBLE = "compatible"


# ---------------------------------------------------------------------------
# Unit / Timestamp / Rights
# ---------------------------------------------------------------------------


class UnitContract(FrozenStrictModel):
    """Unit contract for a single field."""

    unit: str = Field(min_length=1, max_length=64)
    dimension: str | None = Field(default=None, max_length=64)

    @field_validator("unit", "dimension")
    @classmethod
    def validate_non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("unit/dimension must be non-empty when provided")
        return value.strip()

    def canonical_key(self) -> str:
        """Return canonical unit key for drift comparison."""
        dim = self.dimension.strip().lower() if self.dimension else ""
        u = self.unit.strip().lower()
        return f"{dim}:{u}" if dim else u


class TimestampContract(FrozenStrictModel):
    """Timestamp semantics contract."""

    time_basis: TimeBasis = TimeBasis.UNKNOWN
    timezone: TimezoneSemantics = TimezoneSemantics.UNKNOWN
    format_hint: str | None = Field(default=None, max_length=128)
    requires_timezone: bool = False

    @field_validator("format_hint")
    @classmethod
    def validate_format_hint(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("format_hint must be non-empty when provided")
        return value.strip()


class RightsAndRetentionContract(FrozenStrictModel):
    """Privacy / publication and retention contract."""

    publication_class: PublicationClass = PublicationClass.PRIVATE
    contains_personal_data: bool = False
    retention_days: int | None = Field(default=None, ge=1, le=36500)
    legal_basis: str | None = Field(default=None, max_length=256)

    @field_validator("legal_basis")
    @classmethod
    def validate_legal_basis(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("legal_basis must be non-empty when provided")
        return value.strip()

    def is_weakening(self, other: RightsAndRetentionContract) -> bool:
        """Return True if ``other`` weakens publication/privacy versus self.

        Weakening means moving toward more open publication or reducing
        protection. ``PRIVATE < INTERNAL < AGGREGATED_ONLY < OPEN`` is the
        openness order. Reducing ``contains_personal_data`` from True to
        False is not a weakening; increasing openness is.
        """
        order = {
            PublicationClass.PRIVATE: 0,
            PublicationClass.INTERNAL: 1,
            PublicationClass.AGGREGATED_ONLY: 2,
            PublicationClass.OPEN: 3,
        }
        return order[other.publication_class] > order[self.publication_class]


# ---------------------------------------------------------------------------
# Field & Source contracts
# ---------------------------------------------------------------------------


class FieldContract(FrozenStrictModel):
    """Contract for a single field."""

    field_name: str = Field(min_length=1, max_length=128)
    required: bool = True
    logical_type: LogicalType = LogicalType.STRING
    unit: UnitContract | None = None
    timestamp: TimestampContract | None = None
    description: str | None = Field(default=None, max_length=512)

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("description must be non-empty when provided")
        return value.strip()

    @model_validator(mode="after")
    def validate_timestamp_consistency(self) -> FieldContract:
        if self.logical_type is LogicalType.TIMESTAMP and self.timestamp is None:
            raise ValueError("timestamp contract required when logical_type is timestamp")
        if self.logical_type is not LogicalType.TIMESTAMP and self.timestamp is not None:
            raise ValueError("timestamp contract only allowed for timestamp logical type")
        # Units allowed for numeric and timestamp types only; categorical/string should not carry units  # noqa: E501
        if self.unit is not None and self.logical_type in {
            LogicalType.STRING,
            LogicalType.BOOLEAN,
            LogicalType.CATEGORICAL,
        }:
            # Allow categorical with no unit; but string/boolean/categorical with unit is suspicious
            # We permit it but drift will flag incompatible unit changes; keep validation permissive here.  # noqa: E501
            pass
        return self


class SourceDataContract(FrozenStrictModel):
    """Authored source contract (portable, excludes runtime paths/clocks)."""

    schema_version: Literal["1.0"] = "1.0"
    source_id: str = Field(min_length=1, max_length=128)
    contract_version: str = Field(min_length=1, max_length=32)
    fields: list[FieldContract] = Field(min_length=1)
    rights: RightsAndRetentionContract = Field(default_factory=RightsAndRetentionContract)
    notes: str | None = Field(default=None, max_length=1024)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _validate_source_id(value)

    @field_validator("contract_version")
    @classmethod
    def validate_contract_version(cls, value: str) -> str:
        if not _VERSION_RE.fullmatch(value.strip()):
            raise ValueError("contract_version must be semantic version X.Y.Z (e.g. 1.0.0)")
        return value.strip()

    @field_validator("fields")
    @classmethod
    def validate_unique_fields(cls, value: list[FieldContract]) -> list[FieldContract]:
        names = [f.field_name for f in value]
        if len(names) != len(set(names)):
            raise ValueError("fields must have unique field_name values")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("notes must be non-empty when provided")
        return value.strip()

    def field_map(self) -> dict[str, FieldContract]:
        """Return field_name -> FieldContract."""
        return {f.field_name: f for f in self.fields}

    def required_field_names(self) -> set[str]:
        """Return required field names."""
        return {f.field_name for f in self.fields if f.required}


class SourceContractVersion(StrictModel):
    """Frozen version wrapper with immutability and lineage."""

    schema_version: Literal["1.0"] = "1.0"
    version: str = Field(min_length=1, max_length=32)
    contract: SourceDataContract
    parent_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", description="hex sha256 of parent version"
    )
    amendment_reason: str | None = Field(default=None, max_length=512)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    is_frozen: bool = True

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=True,
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _VERSION_RE.fullmatch(value.strip()):
            raise ValueError("version must be semantic version X.Y.Z")
        return value.strip()

    @field_validator("amendment_reason")
    @classmethod
    def validate_amendment(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("amendment_reason must be non-empty when provided")
        return value.strip()

    @model_validator(mode="after")
    def validate_lineage(self) -> SourceContractVersion:
        if self.parent_fingerprint is None and self.amendment_reason is not None:
            # First version should not have amendment reason without parent, but allow with warning?
            # Enforce: amendment_reason requires parent_fingerprint
            raise ValueError("amendment_reason requires parent_fingerprint")
        if self.parent_fingerprint is not None and self.amendment_reason is None:
            raise ValueError("parent_fingerprint requires amendment_reason")
        return self


# ---------------------------------------------------------------------------
# Schema observation
# ---------------------------------------------------------------------------


class FieldObservation(StrictModel):
    """Deterministic observation for one field."""

    field_name: str = Field(min_length=1, max_length=128)
    observed_logical_type: LogicalType = LogicalType.STRING
    nullable: bool = False
    observed_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    timestamp_parse_state: str | None = Field(default=None, max_length=64)
    categorical_digest: list[str] | None = Field(default=None, max_length=32)
    precision: int | None = Field(default=None, ge=0)
    scale: int | None = Field(default=None, ge=0)

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        return _validate_field_name(value)

    @field_validator("timestamp_parse_state")
    @classmethod
    def validate_parse_state(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed = {
            "not_timestamp",
            "parsed_utc",
            "parsed_naive",
            "parsed_with_tz",
            "parse_failed",
            "parse_ambiguous",
        }
        if value not in allowed:
            raise ValueError(f"timestamp_parse_state must be one of {sorted(allowed)}")
        return value

    @field_validator("categorical_digest")
    @classmethod
    def validate_digest(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if len(set(value)) != len(value):
            raise ValueError("categorical_digest must have unique values")
        return sorted(value)

    @model_validator(mode="after")
    def validate_counts(self) -> FieldObservation:
        if self.null_count > self.observed_count:
            raise ValueError("null_count must not exceed observed_count")
        return self


class SchemaObservation(StrictModel):
    """Bounded deterministic schema-only observation.

    Portable identity excludes sample path, retrieval clock, and secrets.
    """

    schema_version: Literal["1.0"] = "1.0"
    observation_id: str = Field(min_length=1, max_length=64)
    source_label_redacted: str = Field(min_length=1, max_length=128)
    total_observed_rows: int = Field(ge=0)
    field_observations: list[FieldObservation] = Field(min_length=1)
    truncated: bool = False
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("observation_id")
    @classmethod
    def validate_observation_id(cls, value: str) -> str:
        if not _SOURCE_ID_RE.fullmatch(value.strip()):
            raise ValueError("observation_id must be alphanumeric identifier")
        return value.strip()

    @field_validator("field_observations")
    @classmethod
    def validate_unique(cls, value: list[FieldObservation]) -> list[FieldObservation]:
        names = [f.field_name for f in value]
        if len(names) != len(set(names)):
            raise ValueError("field_observations must have unique field_name")
        # Keep original header order for drift detection; sorting for fingerprint
        # is handled during canonical serialisation, not here.
        return value

    def field_map(self) -> dict[str, FieldObservation]:
        """Return field_name -> FieldObservation."""
        return {f.field_name: f for f in self.field_observations}


# ---------------------------------------------------------------------------
# Drift findings
# ---------------------------------------------------------------------------


class SchemaDriftFinding(StrictModel):
    """One typed drift finding."""

    field_name: str | None = Field(default=None, max_length=128)
    severity: SchemaDriftSeverity = SchemaDriftSeverity.COMPATIBLE
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9_]+$")
    message: str = Field(min_length=1, max_length=512)
    details: dict[str, str] | None = None

    @field_validator("field_name")
    @classmethod
    def validate_field(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_field_name(value)


class SchemaDriftReport(StrictModel):
    """Deterministic drift report comparing a frozen contract to a candidate."""

    schema_version: Literal["1.0"] = "1.0"
    contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_version: str = Field(min_length=1, max_length=32)
    source_id: str = Field(min_length=1, max_length=128)
    overall_severity: SchemaDriftSeverity = SchemaDriftSeverity.COMPATIBLE
    findings: list[SchemaDriftFinding] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("contract_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _VERSION_RE.fullmatch(value.strip()):
            raise ValueError("contract_version must be semantic version X.Y.Z")
        return value.strip()

    @field_validator("source_id")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return _validate_source_id(value)

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: dict[str, int]) -> dict[str, int]:
        allowed = {"blocked", "review_required", "compatible", "total"}
        if set(value.keys()) - allowed:
            raise ValueError(f"summary keys must be subset of {allowed}")
        for k, v in value.items():
            if v < 0:
                raise ValueError("summary counts must be non-negative")
        return value
