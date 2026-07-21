"""Typed, source-neutral contracts for evidence-gated external adapters."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.config.capabilities import CapabilityManifest

EXTERNAL_SOURCE_SCHEMA_VERSION = "1.0"
EXTERNAL_SOURCE_CONTRACT_VERSION = "traffictwin-external-source-v1"
EXTERNAL_SOURCE_CAPABILITY_ID = "OPS-05"


class ExternalSourceModel(BaseModel):
    """Strict base for portable external-source artifacts."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        allow_inf_nan=False,
    )


class DiscoveryStatus(StrEnum):
    """Outcome of applying one adapter's non-mutating marker rules."""

    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    BLOCKED = "blocked"


class DiscoveryReportStatus(StrEnum):
    """Selection state across every registered adapter."""

    ONE_MATCH = "one_match"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"


class MarkerKind(StrEnum):
    """Filesystem object type required by a discovery marker."""

    FILE = "file"
    DIRECTORY = "directory"


class ValidationOutcome(StrEnum):
    """Normalised validation outcome without erasing source-specific reports."""

    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class SemanticStatus(StrEnum):
    """Strength of evidence for a semantic or provenance statement."""

    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class ConversionLevel(StrEnum):
    """Non-ordinal description of the adapter's actual output boundary."""

    NONE = "none"
    SOURCE_SPECIFIC = "source_specific"
    AGGREGATE_SUMMARY = "aggregate_summary"
    PARTIAL_CANONICAL = "partial_canonical"
    CANONICAL_BUNDLE = "canonical_bundle"


class SourceMarker(ExternalSourceModel):
    """One exact, safe, relative marker used only for discovery."""

    relative_path: str = Field(min_length=1)
    kind: MarkerKind
    required: bool
    meaning: str = Field(min_length=1)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        normalised = value.replace("\\", "/")
        parts = normalised.split("/")
        if normalised.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise ValueError("discovery marker must be an exact safe relative path")
        return normalised


class ExternalFieldSemantic(ExternalSourceModel):
    """Evidence-backed meaning for one source field or field family."""

    source_field: str = Field(min_length=1)
    artifact: str = Field(min_length=1)
    meaning: str = Field(min_length=1)
    unit: str | None = None
    status: SemanticStatus
    canonical_target: str | None = None
    evidence: list[str] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class ExternalProvenanceRequirement(ExternalSourceModel):
    """One provenance item required or recommended by an adapter contract."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    description: str = Field(min_length=1)
    required: bool
    evidence_rule: str = Field(min_length=1)


class ExternalProvenanceObservation(ExternalSourceModel):
    """One observed provenance value, including explicit unknown states."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    status: SemanticStatus
    value: str | int | bool | list[str] | None = None
    evidence: list[str] = Field(default_factory=list)
    limitation: str | None = None

    @model_validator(mode="after")
    def validate_status_and_value(self) -> ExternalProvenanceObservation:
        if self.status is SemanticStatus.CONFIRMED and self.value is None:
            raise ValueError("confirmed provenance requires an observed value")
        if (
            self.status in {SemanticStatus.UNKNOWN, SemanticStatus.UNSUPPORTED}
            and self.value is not None
        ):
            raise ValueError("unknown or unsupported provenance cannot carry a claimed value")
        return self


class ExternalConversionProfile(ExternalSourceModel):
    """Exact outputs and exclusions for one adapter; levels are not a quality ranking."""

    level: ConversionLevel
    canonical_outputs: list[str] = Field(default_factory=list)
    source_specific_outputs: list[str] = Field(default_factory=list)
    registry_outputs: list[str] = Field(default_factory=list)
    unavailable_outputs: list[str] = Field(default_factory=list)
    rules: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_level(self) -> ExternalConversionProfile:
        if self.level is ConversionLevel.NONE and (
            self.canonical_outputs or self.source_specific_outputs or self.registry_outputs
        ):
            raise ValueError("none conversion cannot declare produced outputs")
        if self.level is ConversionLevel.PARTIAL_CANONICAL and not self.canonical_outputs:
            raise ValueError("partial canonical conversion requires at least one canonical output")
        if self.level is ConversionLevel.AGGREGATE_SUMMARY and not self.source_specific_outputs:
            raise ValueError("aggregate-summary conversion requires source-specific outputs")
        return self


class ExternalBlocker(ExternalSourceModel):
    """Evidence-backed reason an output or action remains unavailable."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    status: SemanticStatus
    affected_capabilities: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(min_length=1)


class ExternalAdapterContract(ExternalSourceModel):
    """Portable contract implemented by one external evidence adapter."""

    schema_version: str = EXTERNAL_SOURCE_SCHEMA_VERSION
    capability_id: str = EXTERNAL_SOURCE_CAPABILITY_ID
    contract_version: str = EXTERNAL_SOURCE_CONTRACT_VERSION
    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    adapter_version: str = Field(min_length=1)
    source_family: str = Field(min_length=1)
    interface_operations: list[str]
    discovery_markers: list[SourceMarker] = Field(min_length=1)
    field_semantics: list[ExternalFieldSemantic] = Field(min_length=1)
    capabilities: CapabilityManifest
    provenance_requirements: list[ExternalProvenanceRequirement] = Field(min_length=1)
    conversion: ExternalConversionProfile
    blockers: list[ExternalBlocker]
    interpretation_limits: list[str] = Field(min_length=1)
    inspection_is_read_only: bool = True
    direct_launch_is_out_of_scope: bool = True

    @model_validator(mode="after")
    def validate_contract(self) -> ExternalAdapterContract:
        expected_operations = ["discover", "contract", "validate", "inspect"]
        if self.interface_operations != expected_operations:
            raise ValueError(f"interface operations must be {expected_operations!r}")
        if self.capabilities.adapter != self.adapter_id:
            raise ValueError("capability manifest adapter must match adapter_id")
        _require_unique(
            [marker.relative_path for marker in self.discovery_markers],
            "discovery marker",
        )
        _require_unique(
            [field.source_field for field in self.field_semantics],
            "source semantic",
        )
        _require_unique(
            [requirement.key for requirement in self.provenance_requirements],
            "provenance requirement",
        )
        _require_unique([blocker.code for blocker in self.blockers], "blocker")
        if not any(marker.required for marker in self.discovery_markers):
            raise ValueError("at least one discovery marker must be required")
        return self

    def canonical_json(self) -> str:
        """Return stable contract JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete adapter contract."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ExternalSourceDiscovery(ExternalSourceModel):
    """One adapter's deterministic marker result."""

    adapter_id: str
    adapter_version: str
    status: DiscoveryStatus
    matched_markers: list[str] = Field(default_factory=list)
    missing_required_markers: list[str] = Field(default_factory=list)
    unsafe_markers: list[str] = Field(default_factory=list)
    detail: str


class ExternalDiscoveryReport(ExternalSourceModel):
    """Deterministic discovery report across the registered adapter set."""

    schema_version: str = EXTERNAL_SOURCE_SCHEMA_VERSION
    capability_id: str = EXTERNAL_SOURCE_CAPABILITY_ID
    contract_version: str = EXTERNAL_SOURCE_CONTRACT_VERSION
    source_label: str
    status: DiscoveryReportStatus
    results: list[ExternalSourceDiscovery]
    candidate_adapter_ids: list[str]
    read_only: bool = True
    mutations_performed: bool = False

    @model_validator(mode="after")
    def validate_candidates(self) -> ExternalDiscoveryReport:
        expected = sorted(
            result.adapter_id for result in self.results if result.status is DiscoveryStatus.MATCHED
        )
        if self.candidate_adapter_ids != expected:
            raise ValueError("candidate adapters must be sorted matched results")
        return self

    def canonical_json(self) -> str:
        """Return stable discovery JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the portable discovery report."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ExternalValidationSummary(ExternalSourceModel):
    """Source-neutral validation summary that retains its source report identity."""

    outcome: ValidationOutcome
    accepted_for_declared_import: bool
    validator_version: str
    source_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    finding_counts: dict[str, int]
    finding_codes: list[str]
    output_counts: dict[str, int]
    source_report_type: str

    @field_validator("finding_counts", "output_counts")
    @classmethod
    def validate_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("validation counts must be non-negative")
        return dict(sorted(value.items()))


class ExternalSourceInspection(ExternalSourceModel):
    """Complete read-only inspection through one selected external adapter."""

    schema_version: str = EXTERNAL_SOURCE_SCHEMA_VERSION
    capability_id: str = EXTERNAL_SOURCE_CAPABILITY_ID
    contract_version: str = EXTERNAL_SOURCE_CONTRACT_VERSION
    source_label: str
    adapter_id: str
    adapter_version: str
    contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    discovery: ExternalSourceDiscovery
    validation: ExternalValidationSummary
    observed_provenance: list[ExternalProvenanceObservation]
    conversion: ExternalConversionProfile
    blockers: list[ExternalBlocker]
    interpretation_limits: list[str]
    read_only: bool = True
    mutations_performed: bool = False

    @model_validator(mode="after")
    def validate_adapter_identity(self) -> ExternalSourceInspection:
        if self.discovery.adapter_id != self.adapter_id:
            raise ValueError("discovery adapter must match inspection adapter")
        if self.discovery.status is not DiscoveryStatus.MATCHED:
            raise ValueError("inspection requires a matched adapter discovery")
        _require_unique([item.key for item in self.observed_provenance], "observed provenance")
        return self

    def canonical_json(self) -> str:
        """Return stable, path-free inspection JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete portable inspection."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ExternalSourceCatalogue(ExternalSourceModel):
    """Published shared interface and all registered reference contracts."""

    schema_version: str = EXTERNAL_SOURCE_SCHEMA_VERSION
    capability_id: str = EXTERNAL_SOURCE_CAPABILITY_ID
    contract_version: str = EXTERNAL_SOURCE_CONTRACT_VERSION
    protocol_methods: list[str]
    selection_policy: list[str]
    validation_policy: list[str]
    semantics_policy: list[str]
    conversion_level_semantics: dict[str, str]
    adapters: list[ExternalAdapterContract]
    exclusions: list[str]
    limitations: list[str]

    @model_validator(mode="after")
    def validate_catalogue(self) -> ExternalSourceCatalogue:
        expected = ["discover", "contract", "validate", "inspect"]
        if self.protocol_methods != expected:
            raise ValueError(f"protocol methods must be {expected!r}")
        if self.adapters != sorted(self.adapters, key=lambda item: item.adapter_id):
            raise ValueError("adapter contracts must be sorted by adapter_id")
        _require_unique([adapter.adapter_id for adapter in self.adapters], "adapter")
        if set(self.conversion_level_semantics) != {item.value for item in ConversionLevel}:
            raise ValueError("conversion-level semantics must describe every level")
        return self

    def canonical_json(self) -> str:
        """Return stable public catalogue JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint the complete public catalogue."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} identifiers must be unique")
