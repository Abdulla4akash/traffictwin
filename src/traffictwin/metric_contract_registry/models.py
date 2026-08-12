"""Strict typed models for Metric Contract Registry.

Portable identity excludes wall clock, rendering state, local paths and secrets.
All models use ``extra='forbid'`` at the boundary. No executable formulas,
code, expressions, import paths, callbacks, or evaluation rules are accepted.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REGISTRY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
REGISTRY_MAX_CONTRACTS: int = 128

_METRIC_KEY_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-:]{0,255}$")
_VERSION_RE = re.compile(r"^[0-9A-Za-z._\-]{1,64}$")
_UNIT_RE = re.compile(r"^[^\s]{1,64}$")
# Contract version semantic: allow X.Y or X.Y.Z
_CONTRACT_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$")

_FORBIDDEN_SUBSTRINGS = (
    "import ",
    "import\t",
    "__import__",
    "eval(",
    "exec(",
    "compile(",
    "open(",
    "subprocess",
    "os.",
    "sys.",
    "lambda ",
    "def ",
    "class ",
    "__",
)


def _check_no_code(value: str, field_name: str) -> str:
    lowered = value.lower()
    for substr in _FORBIDDEN_SUBSTRINGS:
        if substr in lowered:
            raise ValueError(f"{field_name} must not contain executable code pattern {substr!r}")
    # No path contamination: forbid absolute paths and home references
    if value.startswith("/") or value.startswith("~") or "://" in value:
        raise ValueError(f"{field_name} must not contain local paths or URLs")
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
    """Immutable strict model."""

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


class MetricContractDenominator(StrEnum):
    """Denominator for metric attainment — mirrors resource-strategy denominators."""

    OFFERED_TASKS = "offered_tasks"
    ADMITTED_TASKS = "admitted_tasks"
    COMPLETED_TASKS = "completed_tasks"
    REPLICATION = "replication"
    UNKNOWN = "unknown"


class MetricContractDirection(StrEnum):
    """Direction for optimisation interpretation."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"


class MetricContractStatus(StrEnum):
    """Lifecycle status of a metric contract."""

    DRAFT = "draft"
    VALID = "valid"
    REGISTERED = "registered"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class MetricContractCompatibilityStatus(StrEnum):
    """Compatibility outcome for a metric across arms."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNAVAILABLE = "unavailable"


class MetricContractFindingSeverity(StrEnum):
    """Severity of a registry finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class MetricContract(FrozenStrictModel):
    """Closed metadata contract for one metric — not an executable formula."""

    metric_key: str = Field(min_length=1, max_length=256)
    metric_version: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=64)
    denominator: MetricContractDenominator
    description: str = Field(min_length=1, max_length=1024)
    higher_is_better: bool | None = Field(default=None)
    direction: MetricContractDirection | None = Field(default=None)
    time_window_applicable: bool = False
    minimum: float | None = Field(default=None)
    maximum: float | None = Field(default=None)
    allowed_statuses: list[str] | None = Field(default=None)
    provenance: str | None = Field(default=None, max_length=1024)
    citation: str | None = Field(default=None, max_length=1024)
    contract_version: str = Field(default="1.0", min_length=1, max_length=32)

    @field_validator("metric_key")
    @classmethod
    def validate_metric_key(cls, value: str) -> str:
        if not _METRIC_KEY_RE.fullmatch(value):
            raise ValueError(
                "metric_key must start with a letter and contain only letters, numbers, "
                "'.', '_', '-', ':' (1-256 chars)"
            )
        _check_no_code(value, "metric_key")
        return value

    @field_validator("metric_version")
    @classmethod
    def validate_metric_version(cls, value: str) -> str:
        if not _VERSION_RE.fullmatch(value):
            raise ValueError("metric_version must be 1-64 chars: letters, numbers, '.', '_', '-'")
        _check_no_code(value, "metric_version")
        return value

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("unit must be non-empty")
        if not _UNIT_RE.fullmatch(value):
            raise ValueError("unit must be 1-64 non-space chars")
        _check_no_code(value, "unit")
        return value.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must be non-empty")
        _check_no_code(value, "description")
        return value.strip()

    @field_validator("provenance", "citation")
    @classmethod
    def validate_provenance_citation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("provenance/citation must be non-empty when provided")
        _check_no_code(value, "provenance/citation")
        # No local path contamination
        if value.strip().startswith("/"):
            raise ValueError("provenance/citation must not be a local path")
        return value.strip()

    @field_validator("contract_version")
    @classmethod
    def validate_contract_version(cls, value: str) -> str:
        if not _CONTRACT_VERSION_RE.fullmatch(value.strip()):
            raise ValueError("contract_version must be semantic version X.Y or X.Y.Z")
        _check_no_code(value, "contract_version")
        return value.strip()

    @field_validator("allowed_statuses")
    @classmethod
    def validate_allowed_statuses(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 32:
            raise ValueError("allowed_statuses must contain at most 32 entries")
        if len(value) != len(set(value)):
            raise ValueError("allowed_statuses must be unique")
        cleaned: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise ValueError("allowed_statuses entries must be strings")
            if not entry.strip():
                raise ValueError("allowed_statuses entries must be non-empty")
            if len(entry) > 64:
                raise ValueError("allowed_statuses entries must be at most 64 chars")
            _check_no_code(entry, "allowed_statuses entry")
            cleaned.append(entry.strip())
        return sorted(cleaned)

    @field_validator("minimum", "maximum")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("minimum/maximum must be finite numbers")
        fv = float(value)
        if not (fv == fv and fv != float("inf") and fv != float("-inf")):
            raise ValueError("minimum/maximum must be finite")
        return fv

    @model_validator(mode="after")
    def validate_direction_and_bounds(self) -> MetricContract:
        # At least one of higher_is_better or direction should be provided for clarity,
        # but allow both None as neutral with explicit flag? Enforce at least one.
        if self.higher_is_better is None and self.direction is None:
            # Allow neutral implicitly but require explicit for strict registry;
            # treat as neutral? For now enforce explicit.
            raise ValueError(
                "MetricContract requires higher_is_better or direction to be set "
                "(use direction='neutral' if neither)"
            )
        if self.higher_is_better is not None and self.direction is not None:
            # Consistency check
            expected = (
                MetricContractDirection.HIGHER_IS_BETTER
                if self.higher_is_better
                else MetricContractDirection.LOWER_IS_BETTER
            )
            # Allow neutral direction with any higher_is_better? Neutral means either
            if self.direction != expected and self.direction != MetricContractDirection.NEUTRAL:
                raise ValueError(
                    f"higher_is_better={self.higher_is_better} inconsistent with direction={self.direction!r}"  # noqa: E501
                )
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:  # noqa: SIM102
            raise ValueError("minimum must not exceed maximum")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Return deterministic payload for fingerprinting."""
        return {
            "metric_key": self.metric_key,
            "metric_version": self.metric_version,
            "unit": self.unit,
            "denominator": self.denominator.value,
            "description": self.description,
            "higher_is_better": self.higher_is_better,
            "direction": self.direction.value if self.direction is not None else None,
            "time_window_applicable": self.time_window_applicable,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "allowed_statuses": sorted(self.allowed_statuses)
            if self.allowed_statuses is not None
            else None,
            "provenance": self.provenance,
            "citation": self.citation,
            "contract_version": self.contract_version,
        }


class MetricContractSupersession(FrozenStrictModel):
    """Explicit lineage: one contract supersedes another."""

    predecessor_metric_key: str = Field(min_length=1, max_length=256)
    predecessor_metric_version: str = Field(min_length=1, max_length=64)
    successor_metric_key: str = Field(min_length=1, max_length=256)
    successor_metric_version: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=512)

    @field_validator("predecessor_metric_key", "successor_metric_key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not _METRIC_KEY_RE.fullmatch(value):
            raise ValueError("metric_key invalid")
        _check_no_code(value, "metric_key")
        return value

    @field_validator("predecessor_metric_version", "successor_metric_version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not _VERSION_RE.fullmatch(value):
            raise ValueError("metric_version invalid")
        return value

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason must be non-empty")
        return value.strip()


# ---------------------------------------------------------------------------
# Findings / Compatibility / Receipt
# ---------------------------------------------------------------------------


class MetricContractFinding(StrictModel):
    """Typed finding from registry validation or compatibility audit."""

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9_]+$")
    severity: MetricContractFindingSeverity = MetricContractFindingSeverity.INFO
    message: str = Field(min_length=1, max_length=512)
    metric_key: str | None = Field(default=None, max_length=256)
    metric_version: str | None = Field(default=None, max_length=64)
    details: dict[str, str | int | float | bool | None] | None = None


class MetricContractCompatibility(StrictModel):
    """Compatibility outcome for a metric across arms or against a contract."""

    metric_key: str = Field(min_length=1, max_length=256)
    metric_version: str = Field(min_length=1, max_length=64)
    status: MetricContractCompatibilityStatus
    unit: str | None = Field(default=None, max_length=64)
    denominator: MetricContractDenominator | None = None
    finding: str = Field(default="", max_length=1024)
    arm_versions: list[str] = Field(default_factory=list)
    arm_units: list[str] = Field(default_factory=list)
    arm_denominators: list[str] = Field(default_factory=list)


class MetricContractRegistryReceipt(StrictModel):
    """Receipt for registry validation, merge, or fingerprint operations."""

    registry_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_version: str = Field(min_length=1, max_length=32)
    contract_count: int = Field(ge=0, le=REGISTRY_MAX_CONTRACTS)
    status: MetricContractStatus = MetricContractStatus.VALID
    findings: list[MetricContractFinding] = Field(default_factory=list)
    supersession_count: int = Field(default=0, ge=0)
    built_in_conflicts: list[str] = Field(default_factory=list)
    is_deterministic: bool = True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class MetricContractRegistry(FrozenStrictModel):
    """Deterministic registry of metric contracts."""

    schema_version: Literal["1.0"] = REGISTRY_SCHEMA_VERSION
    registry_version: str = Field(default="1.0", min_length=1, max_length=32)
    contracts: list[MetricContract] = Field(default_factory=list)
    supersession: list[MetricContractSupersession] = Field(default_factory=list)

    @field_validator("registry_version")
    @classmethod
    def validate_registry_version(cls, value: str) -> str:
        if not _CONTRACT_VERSION_RE.fullmatch(value.strip()):
            raise ValueError("registry_version must be semantic version X.Y or X.Y.Z")
        return value.strip()

    @field_validator("contracts")
    @classmethod
    def validate_contracts_bounded(cls, value: list[MetricContract]) -> list[MetricContract]:
        if len(value) > REGISTRY_MAX_CONTRACTS:
            raise ValueError(f"registry must contain at most {REGISTRY_MAX_CONTRACTS} contracts")
        return value

    @field_validator("supersession")
    @classmethod
    def validate_supersession_bounded(
        cls, value: list[MetricContractSupersession]
    ) -> list[MetricContractSupersession]:
        if len(value) > REGISTRY_MAX_CONTRACTS:
            raise ValueError("supersession lineage too large")
        return value

    @model_validator(mode="after")
    def validate_unique_and_lineage(self) -> MetricContractRegistry:
        # Unique metric_key/version
        seen: dict[tuple[str, str], MetricContract] = {}
        for contract in self.contracts:
            key = (contract.metric_key, contract.metric_version)
            if key in seen:
                # Check if identical duplicate (all fields same) — allowed as redundant,
                # but we still need to ensure they are exactly identical to be deduplicated.
                # For strict validation, conflicting duplicate (same key/version but different content)  # noqa: E501
                # must fail. Identical duplicate is allowed but will be deduplicated in canonical form.  # noqa: E501
                existing = seen[key]
                if existing.canonical_payload() != contract.canonical_payload():
                    raise ValueError(
                        f"conflicting duplicate contract for {contract.metric_key!r} "
                        f"version {contract.metric_version!r}: definitions differ"
                    )
                # Identical duplicate — will be deduplicated later, but allow
            else:
                seen[key] = contract
        # Validate supersession references exist
        contract_keys = {(c.metric_key, c.metric_version) for c in self.contracts}
        for lineage in self.supersession:
            pred = (lineage.predecessor_metric_key, lineage.predecessor_metric_version)
            succ = (lineage.successor_metric_key, lineage.successor_metric_version)
            if pred not in contract_keys:
                raise ValueError(f"supersession predecessor {pred!r} not in registry")
            if succ not in contract_keys:
                raise ValueError(f"supersession successor {succ!r} not in registry")
            if pred == succ:
                raise ValueError("supersession predecessor and successor must differ")
        # No duplicate lineage entries
        lineage_keys = [
            (
                lineage.predecessor_metric_key,
                lineage.predecessor_metric_version,
                lineage.successor_metric_key,
                lineage.successor_metric_version,
            )
            for lineage in self.supersession
        ]
        if len(lineage_keys) != len(set(lineage_keys)):
            raise ValueError("supersession lineage must not contain duplicates")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Return deterministic payload for fingerprinting."""
        # Deduplicate identical contracts by key/version, keep first occurrence
        # Sort by (metric_key, metric_version)
        unique: dict[tuple[str, str], MetricContract] = {}
        for contract in self.contracts:
            key = (contract.metric_key, contract.metric_version)
            if key not in unique:
                unique[key] = contract
        sorted_contracts = sorted(unique.values(), key=lambda c: (c.metric_key, c.metric_version))
        sorted_supersession = sorted(
            self.supersession,
            key=lambda s: (
                s.predecessor_metric_key,
                s.predecessor_metric_version,
                s.successor_metric_key,
                s.successor_metric_version,
            ),
        )
        return {
            "schema_version": self.schema_version,
            "registry_version": self.registry_version,
            "contracts": [c.canonical_payload() for c in sorted_contracts],
            "supersession": [
                {
                    "predecessor_metric_key": lineage.predecessor_metric_key,
                    "predecessor_metric_version": lineage.predecessor_metric_version,
                    "successor_metric_key": lineage.successor_metric_key,
                    "successor_metric_version": lineage.successor_metric_version,
                    "reason": lineage.reason,
                }
                for lineage in sorted_supersession
            ],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        # Ensure deterministic ordering for portable export
        # Use canonical payload plus human-friendly ordering
        canonical = self.canonical_payload()
        return json.dumps(
            {
                "schema_version": canonical["schema_version"],
                "registry_version": canonical["registry_version"],
                "contracts": canonical["contracts"],
                "supersession": canonical["supersession"],
                "fingerprint": self.fingerprint(),
            },
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )

    def get_contract(self, metric_key: str, metric_version: str) -> MetricContract | None:
        for contract in self.contracts:
            if contract.metric_key == metric_key and contract.metric_version == metric_version:
                return contract
        return None

    def find_by_key(self, metric_key: str) -> list[MetricContract]:
        return [c for c in self.contracts if c.metric_key == metric_key]

    def deduplicated_contracts(self) -> list[MetricContract]:
        unique: dict[tuple[str, str], MetricContract] = {}
        for contract in self.contracts:
            key = (contract.metric_key, contract.metric_version)
            if key not in unique:
                unique[key] = contract
        return sorted(unique.values(), key=lambda c: (c.metric_key, c.metric_version))
