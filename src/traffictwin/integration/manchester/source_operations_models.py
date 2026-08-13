"""Frozen, privacy-safe contracts for Manchester source operations.

The operations surface composes the existing provider adapters and immutable
snapshot contracts.  It does not acquire data, inspect workspaces, or infer
readiness from a directory.  Varying values are supplied by a caller that has
already verified them; source meaning and evidence ceilings remain fixed here.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

SOURCE_OPERATIONS_SCHEMA_VERSION = "1.0"
SOURCE_OPERATIONS_METHOD_VERSION = "manchester-source-operations-1.0"

_SAFE_LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$"
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]{4,})"
)


def _screen_portable_text(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    if _SECRET_VALUE_RE.search(value):
        raise ValueError(f"{label} must not contain a credential or secret value")
    return value


def _require_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value


class SourceFamily(StrEnum):
    """The eight explicitly supported source-operation families."""

    BODS = "bods"
    DFT = "dft"
    WEBTRIS = "webtris"
    NATIONAL_HIGHWAYS = "national_highways"
    TFGM = "tfgm"
    SUMO = "sumo"
    MANUAL_INCIDENT = "manual_incident"
    STATIC_MANCHESTER_GEOGRAPHY = "static_manchester_geography"


SOURCE_FAMILY_ORDER: tuple[SourceFamily, ...] = (
    SourceFamily.BODS,
    SourceFamily.DFT,
    SourceFamily.WEBTRIS,
    SourceFamily.NATIONAL_HIGHWAYS,
    SourceFamily.TFGM,
    SourceFamily.SUMO,
    SourceFamily.MANUAL_INCIDENT,
    SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
)


class EvidenceStanding(StrEnum):
    """Exact v0.8 Manchester evidence vocabulary."""

    REAL_MANCHESTER_DATA = "REAL MANCHESTER DATA"
    REAL_EXTERNAL_NON_MANCHESTER_DATA = "REAL EXTERNAL NON-MANCHESTER DATA"
    SYNTHETIC_DATA = "SYNTHETIC DATA"
    SIMULATION_OUTPUT = "SIMULATION OUTPUT"
    DESIGN_ONLY_CAPABILITY = "DESIGN-ONLY CAPABILITY"


class SnapshotValidationState(StrEnum):
    """Validation outcome for one immutable snapshot."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SourceCurrentStanding(StrEnum):
    """Operational availability, kept separate from evidence standing."""

    AVAILABLE = "available"
    HISTORICAL_ONLY = "historical_only"
    CREDENTIAL_REQUIRED = "credential_required"
    PROVIDER_DATA_REQUIRED = "provider_data_required"
    INSTALLATION_DETECTED = "installation_detected"
    NOT_DETECTED = "not_detected"
    SYNTHETIC_AVAILABLE = "synthetic_available"
    STATIC_AVAILABLE = "static_available"
    UNAVAILABLE = "unavailable"


class CredentialPresence(StrEnum):
    """Credential presence only; the model has no credential-value field."""

    PRESENT = "present"
    ABSENT = "absent"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class RightsStanding(StrEnum):
    CONFIRMED = "confirmed"
    PROVIDER_CONTRACT_REQUIRED = "provider_contract_required"
    PROJECT_AUTHORED = "project_authored"
    UNKNOWN = "unknown"


class SourceFreshnessStanding(StrEnum):
    HISTORICAL = "historical"
    NEAR_LIVE = "near_live"
    LIVE_VEHICLE = "live_vehicle"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    SYNTHETIC = "synthetic"
    STATIC = "static"
    SIMULATION_TIME = "simulation_time"


class SourceOperationsModel(ManchesterSnapshotModel):
    """Strict frozen base that also screens every persisted free-text value."""

    @model_validator(mode="after")
    def reject_nonportable_or_secret_text(self) -> Self:
        def visit(value: object) -> None:
            if isinstance(value, str):
                _screen_portable_text(value, "source operations metadata")
            elif isinstance(value, dict):
                for key, item in value.items():
                    visit(key)
                    visit(item)
            elif isinstance(value, (list, tuple, set, frozenset)):
                for item in value:
                    visit(item)

        visit(self.model_dump(mode="python"))
        return self


class SourceDefinition(SourceOperationsModel):
    """Non-negotiable meaning and evidence ceiling for one source family."""

    family: SourceFamily
    provider: str = Field(min_length=1, max_length=120)
    semantic_role: str = Field(pattern=_SAFE_LABEL_PATTERN)
    evidence_standing: EvidenceStanding
    rights_standing: RightsStanding
    licence_id: str | None = Field(default=None, pattern=_SAFE_LABEL_PATTERN)
    retention_rule: str = Field(min_length=1, max_length=300)
    supported_geography: str = Field(min_length=1, max_length=300)
    can_infer: tuple[str, ...] = Field(min_length=1)
    cannot_infer: tuple[str, ...] = Field(min_length=1)
    allowed_current_standings: tuple[SourceCurrentStanding, ...] = Field(min_length=1)
    allowed_freshness: tuple[SourceFreshnessStanding, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_sets(self) -> Self:
        for label, values in (
            ("can_infer", self.can_infer),
            ("cannot_infer", self.cannot_infer),
            ("allowed_current_standings", self.allowed_current_standings),
            ("allowed_freshness", self.allowed_freshness),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} must be unique and ordered")
        return self


class OperationalReceipt(SourceOperationsModel):
    """Portable identity of a verified operational check, never its private path."""

    receipt_id: str = Field(pattern=_SAFE_LABEL_PATTERN)
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at_utc: datetime

    @field_validator("observed_at_utc")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _require_utc(value, "receipt observation time")


class SourceRuntimeMetadata(SourceOperationsModel):
    """Caller-supplied, already-verified operational metadata.

    Deliberately absent: a path, credential value, environment-variable value,
    or arbitrary provider payload.
    """

    source_family: SourceFamily
    current_standing: SourceCurrentStanding
    credential_presence: CredentialPresence
    freshness: SourceFreshnessStanding
    schema_version: str | None = Field(default=None, pattern=_SAFE_LABEL_PATTERN)
    operational_receipt: OperationalReceipt | None = None
    blocker: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{2,95}$")
    owner_action: str | None = Field(default=None, min_length=1, max_length=300)
    tool_version: str | None = Field(default=None, pattern=_SAFE_LABEL_PATTERN)

    @model_validator(mode="after")
    def validate_against_frozen_source(self) -> Self:
        definition = source_definition(self.source_family)
        if self.current_standing not in definition.allowed_current_standings:
            raise ValueError("current standing exceeds the frozen source policy")
        if self.freshness not in definition.allowed_freshness:
            raise ValueError("freshness exceeds the frozen source policy")

        blocked = self.current_standing in {
            SourceCurrentStanding.CREDENTIAL_REQUIRED,
            SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            SourceCurrentStanding.NOT_DETECTED,
            SourceCurrentStanding.UNAVAILABLE,
        }
        if blocked != (self.blocker is not None and self.owner_action is not None):
            raise ValueError("blocked standing requires both blocker and owner action")

        if (
            self.current_standing is SourceCurrentStanding.CREDENTIAL_REQUIRED
            and self.credential_presence is not CredentialPresence.ABSENT
        ):
            raise ValueError("credential-required standing requires absent credential")
        if self.source_family is SourceFamily.TFGM and (
            self.current_standing is not SourceCurrentStanding.PROVIDER_DATA_REQUIRED
            or self.credential_presence is not CredentialPresence.UNKNOWN
        ):
            raise ValueError("TfGM measured traffic remains provider-data-required")
        if self.source_family in {SourceFamily.DFT, SourceFamily.WEBTRIS} and (
            self.credential_presence is not CredentialPresence.NOT_REQUIRED
        ):
            raise ValueError("the frozen public historical source does not take credentials")
        if (
            self.source_family
            in {
                SourceFamily.SUMO,
                SourceFamily.MANUAL_INCIDENT,
                SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            }
            and self.credential_presence is not CredentialPresence.NOT_REQUIRED
        ):
            raise ValueError("this source family does not take provider credentials")

        if self.current_standing is SourceCurrentStanding.INSTALLATION_DETECTED:
            if self.tool_version is None or self.operational_receipt is None:
                raise ValueError("detected SUMO requires version and verified receipt")
        elif self.tool_version is not None:
            raise ValueError("tool version is valid only for a detected SUMO installation")
        if self.source_family is not SourceFamily.SUMO and self.current_standing in {
            SourceCurrentStanding.INSTALLATION_DETECTED,
            SourceCurrentStanding.NOT_DETECTED,
        }:
            raise ValueError("installation standing is reserved for SUMO")
        return self


class SnapshotPointer(SourceOperationsModel):
    """Minimal portable reference to one immutable registry record."""

    source_family: SourceFamily
    validation_state: SnapshotValidationState
    registration_id: str = Field(pattern=_SAFE_LABEL_PATTERN)
    snapshot_identity: str = Field(pattern=_SAFE_LABEL_PATTERN)
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at_utc: datetime
    validation_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("retrieved_at_utc")
    @classmethod
    def validate_retrieved_at(cls, value: datetime) -> datetime:
        return _require_utc(value, "snapshot retrieval time")


class SourceReadiness(SourceOperationsModel):
    """Complete truthful source row for an operational UI or report."""

    source: SourceDefinition
    current_standing: SourceCurrentStanding
    credential_presence: CredentialPresence
    freshness: SourceFreshnessStanding
    latest_retrieval_at_utc: datetime | None
    latest_accepted_snapshot: SnapshotPointer | None
    latest_rejected_snapshot: SnapshotPointer | None
    schema_version: str | None = Field(default=None, pattern=_SAFE_LABEL_PATTERN)
    receipt: OperationalReceipt | None
    blocker: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{2,95}$")
    owner_action: str | None = Field(default=None, min_length=1, max_length=300)
    tool_version: str | None = Field(default=None, pattern=_SAFE_LABEL_PATTERN)

    @field_validator("latest_retrieval_at_utc")
    @classmethod
    def validate_latest_retrieval(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        return _require_utc(value, "latest retrieval time")

    @model_validator(mode="after")
    def preserve_source_ceiling(self) -> Self:
        frozen = source_definition(self.source.family)
        if self.source != frozen:
            raise ValueError("source definition must match frozen contract")
        if self.current_standing not in self.source.allowed_current_standings:
            raise ValueError("readiness standing exceeds the source ceiling")
        if self.freshness not in self.source.allowed_freshness:
            raise ValueError("readiness freshness exceeds the source ceiling")
        if self.source.family is SourceFamily.TFGM and self.latest_accepted_snapshot is not None:
            raise ValueError("TfGM measured traffic has no accepted provider snapshot")
        if self.latest_retrieval_at_utc is None and (
            self.latest_accepted_snapshot is not None or self.latest_rejected_snapshot is not None
        ):
            raise ValueError("snapshot pointers require a latest retrieval time")

        # Cross-field runtime rules re-enforced at persistence boundary
        blocked = self.current_standing in {
            SourceCurrentStanding.CREDENTIAL_REQUIRED,
            SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            SourceCurrentStanding.NOT_DETECTED,
            SourceCurrentStanding.UNAVAILABLE,
        }
        if blocked != (self.blocker is not None and self.owner_action is not None):
            raise ValueError("blocked standing requires both blocker and owner action")
        if (
            self.current_standing is SourceCurrentStanding.CREDENTIAL_REQUIRED
            and self.credential_presence is not CredentialPresence.ABSENT
        ):
            raise ValueError("credential-required standing requires absent credential")
        if self.source.family is SourceFamily.TFGM:
            if self.current_standing is not SourceCurrentStanding.PROVIDER_DATA_REQUIRED:
                raise ValueError("TfGM measured traffic remains provider-data-required")
            if self.credential_presence is not CredentialPresence.UNKNOWN:
                raise ValueError("TfGM measured traffic remains provider-data-required")
        if self.source.family in {SourceFamily.DFT, SourceFamily.WEBTRIS} and (
            self.credential_presence is not CredentialPresence.NOT_REQUIRED
        ):
            raise ValueError("the frozen public historical source does not take credentials")
        if (
            self.source.family
            in {
                SourceFamily.SUMO,
                SourceFamily.MANUAL_INCIDENT,
                SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            }
            and self.credential_presence is not CredentialPresence.NOT_REQUIRED
        ):
            raise ValueError("this source family does not take provider credentials")

        if self.current_standing is SourceCurrentStanding.INSTALLATION_DETECTED:
            if self.tool_version is None or self.receipt is None:
                raise ValueError("detected SUMO requires version and verified receipt")
        elif self.tool_version is not None:
            raise ValueError("tool version is valid only for a detected SUMO installation")
        if self.source.family is not SourceFamily.SUMO and self.current_standing in {
            SourceCurrentStanding.INSTALLATION_DETECTED,
            SourceCurrentStanding.NOT_DETECTED,
        }:
            raise ValueError("installation standing is reserved for SUMO")

        # Pointer family and validation_state binding
        if self.latest_accepted_snapshot is not None:
            if self.latest_accepted_snapshot.source_family is not self.source.family:
                raise ValueError("accepted pointer family must match row family")
            if (
                self.latest_accepted_snapshot.validation_state
                is not SnapshotValidationState.ACCEPTED
            ):
                raise ValueError("accepted pointer must carry accepted validation state")
        if self.latest_rejected_snapshot is not None:
            if self.latest_rejected_snapshot.source_family is not self.source.family:
                raise ValueError("rejected pointer family must match row family")
            if (
                self.latest_rejected_snapshot.validation_state
                is not SnapshotValidationState.REJECTED
            ):
                raise ValueError("rejected pointer must carry rejected validation state")

        # latest_retrieval_at must equal max pointer time when pointers exist
        candidates: list[datetime] = []
        if self.latest_accepted_snapshot is not None:
            candidates.append(self.latest_accepted_snapshot.retrieved_at_utc)
        if self.latest_rejected_snapshot is not None:
            candidates.append(self.latest_rejected_snapshot.retrieved_at_utc)
        if candidates:
            if self.latest_retrieval_at_utc is None:
                raise ValueError("latest retrieval must equal max pointer time")
            expected = max(candidates)
            if self.latest_retrieval_at_utc != expected:
                raise ValueError("latest retrieval must equal maximum pointer time")
        else:
            if self.latest_retrieval_at_utc is not None:
                raise ValueError("latest retrieval must be None when no pointers exist")

        # BODS unavailable with credentials present and no blocker must fail
        if (
            self.source.family is SourceFamily.BODS
            and self.current_standing is SourceCurrentStanding.UNAVAILABLE
            and self.credential_presence is CredentialPresence.PRESENT
            and self.blocker is None
        ):
            raise ValueError("BODS unavailable with credentials present requires blocker")

        return self


class SourceOperationsCatalogue(SourceOperationsModel):
    """All eight source rows, exactly once and in stable display order."""

    schema_version: str = SOURCE_OPERATIONS_SCHEMA_VERSION
    method_version: str = SOURCE_OPERATIONS_METHOD_VERSION
    evaluated_at_utc: datetime
    snapshot_registry_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sources: tuple[SourceReadiness, ...] = Field(min_length=8, max_length=8)
    network_access_performed: bool = False
    credential_values_present: bool = False
    directory_presence_used_as_acceptance: bool = False

    @field_validator("evaluated_at_utc")
    @classmethod
    def validate_evaluated_at(cls, value: datetime) -> datetime:
        return _require_utc(value, "catalogue evaluation time")

    @model_validator(mode="after")
    def validate_complete_catalogue(self) -> Self:
        observed = tuple(item.source.family for item in self.sources)
        if observed != SOURCE_FAMILY_ORDER:
            raise ValueError("catalogue must contain all source families in frozen order")
        if (
            self.network_access_performed
            or self.credential_values_present
            or self.directory_presence_used_as_acceptance
        ):
            raise ValueError("source operations catalogue must remain metadata-only")
        # Future-evidence guard: no pointer/receipt/latest after evaluated_at
        for row in self.sources:
            if (
                row.latest_retrieval_at_utc is not None
                and row.latest_retrieval_at_utc > self.evaluated_at_utc
            ):
                raise ValueError("latest retrieval must not be later than evaluated_at")
            if (
                row.latest_accepted_snapshot is not None
                and row.latest_accepted_snapshot.retrieved_at_utc > self.evaluated_at_utc
            ):
                raise ValueError("pointer time must not be later than evaluated_at")
            if (
                row.latest_rejected_snapshot is not None
                and row.latest_rejected_snapshot.retrieved_at_utc > self.evaluated_at_utc
            ):
                raise ValueError("pointer time must not be later than evaluated_at")
            if row.receipt is not None and row.receipt.observed_at_utc > self.evaluated_at_utc:
                raise ValueError("receipt time must not be later than evaluated_at")
        return self


_SOURCE_DEFINITIONS: dict[SourceFamily, SourceDefinition] = {
    SourceFamily.BODS: SourceDefinition(
        family=SourceFamily.BODS,
        provider="Department for Transport Bus Open Data Service",
        semantic_role="bus_vehicle_positions",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        rights_standing=RightsStanding.PROVIDER_CONTRACT_REQUIRED,
        licence_id="OGL-v3.0",
        retention_rule=(
            "Private snapshots use the bounded BODS retention "
            "policy; owner approval remains required."
        ),
        supported_geography="Caller-bounded Greater Manchester bus observations only.",
        can_infer=("Bus/transit vehicle positions within the admitted request scope.",),
        cannot_infer=(
            "General or private-vehicle road traffic.",
            "Complete fleet, congestion, traffic volume, or city-wide traffic state.",
        ),
        allowed_current_standings=(
            SourceCurrentStanding.AVAILABLE,
            SourceCurrentStanding.HISTORICAL_ONLY,
            SourceCurrentStanding.CREDENTIAL_REQUIRED,
            SourceCurrentStanding.UNAVAILABLE,
        ),
        allowed_freshness=(
            SourceFreshnessStanding.LIVE_VEHICLE,
            SourceFreshnessStanding.HISTORICAL,
            SourceFreshnessStanding.STALE,
            SourceFreshnessStanding.UNAVAILABLE,
        ),
    ),
    SourceFamily.DFT: SourceDefinition(
        family=SourceFamily.DFT,
        provider="Department for Transport Road Traffic Statistics",
        semantic_role="historical_road_traffic_counts",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        rights_standing=RightsStanding.CONFIRMED,
        licence_id="OGL-v3.0",
        retention_rule=(
            "Immutable source snapshots retain the declared publication class and attribution."
        ),
        supported_geography=(
            "Admitted DfT count points in Manchester; bounded historical acquisition."
        ),
        can_infer=("Historical surveyed counts and AADF values at admitted count points.",),
        cannot_infer=("Live or near-live traffic state.", "Complete Manchester road coverage."),
        allowed_current_standings=(
            SourceCurrentStanding.HISTORICAL_ONLY,
            SourceCurrentStanding.UNAVAILABLE,
        ),
        allowed_freshness=(
            SourceFreshnessStanding.HISTORICAL,
            SourceFreshnessStanding.UNAVAILABLE,
        ),
    ),
    SourceFamily.WEBTRIS: SourceDefinition(
        family=SourceFamily.WEBTRIS,
        provider="National Highways WebTRIS",
        semantic_role="historical_strategic_road_reports",
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
        rights_standing=RightsStanding.CONFIRMED,
        licence_id="OGL",
        retention_rule="Immutable snapshots retain OGL attribution and source-time limitations.",
        supported_geography=(
            "Selected strategic-road sites only; external to Manchester city-road coverage."
        ),
        can_infer=("Historical measurements for an explicitly admitted strategic-road site/day.",),
        cannot_infer=(
            "Near-live or live traffic state.",
            "Manchester city-road or complete strategic-road conditions.",
        ),
        allowed_current_standings=(
            SourceCurrentStanding.HISTORICAL_ONLY,
            SourceCurrentStanding.UNAVAILABLE,
        ),
        allowed_freshness=(
            SourceFreshnessStanding.HISTORICAL,
            SourceFreshnessStanding.UNAVAILABLE,
        ),
    ),
    SourceFamily.NATIONAL_HIGHWAYS: SourceDefinition(
        family=SourceFamily.NATIONAL_HIGHWAYS,
        provider="National Highways Transport Data Feeds",
        semantic_role="strategic_road_operational_status",
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
        rights_standing=RightsStanding.PROVIDER_CONTRACT_REQUIRED,
        licence_id="NH-Transport-Data-Feeds",
        retention_rule=(
            "Private snapshots remain provider-contract-bound and metadata-only for public use."
        ),
        supported_geography="National Highways strategic road network, not Manchester city roads.",
        can_infer=(
            "Published closures, temporary restrictions, and VMS status in the admitted envelope.",
        ),
        cannot_infer=(
            "Measured speed, traffic volume, congestion, or Manchester city-road state.",
            "Complete Manchester coverage.",
        ),
        allowed_current_standings=(
            SourceCurrentStanding.AVAILABLE,
            SourceCurrentStanding.HISTORICAL_ONLY,
            SourceCurrentStanding.CREDENTIAL_REQUIRED,
            SourceCurrentStanding.UNAVAILABLE,
        ),
        allowed_freshness=(
            SourceFreshnessStanding.NEAR_LIVE,
            SourceFreshnessStanding.HISTORICAL,
            SourceFreshnessStanding.STALE,
            SourceFreshnessStanding.UNAVAILABLE,
        ),
    ),
    SourceFamily.TFGM: SourceDefinition(
        family=SourceFamily.TFGM,
        provider="Transport for Greater Manchester",
        semantic_role="measured_general_road_traffic",
        evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
        rights_standing=RightsStanding.UNKNOWN,
        licence_id=None,
        retention_rule="Provider terms and retention authority are required before intake.",
        supported_geography=(
            "Requested Manchester measured-traffic scope; provider evidence unavailable."
        ),
        can_infer=(
            "Nothing until exact provider evidence, rights, schema, and access are admitted.",
        ),
        cannot_infer=(
            "Measured Manchester traffic availability from the existing static "
            "signal-location adapter.",
            "Traffic volume, live signal state, queues, or general-road conditions.",
        ),
        allowed_current_standings=(SourceCurrentStanding.PROVIDER_DATA_REQUIRED,),
        allowed_freshness=(SourceFreshnessStanding.UNAVAILABLE,),
    ),
    SourceFamily.SUMO: SourceDefinition(
        family=SourceFamily.SUMO,
        provider="Eclipse SUMO",
        semantic_role="controlled_local_simulation",
        evidence_standing=EvidenceStanding.SIMULATION_OUTPUT,
        rights_standing=RightsStanding.CONFIRMED,
        licence_id="EPL-2.0",
        retention_rule=(
            "Generated run artifacts follow the explicit isolated output-package policy."
        ),
        supported_geography="Only the exact input network package declared by a controlled run.",
        can_infer=(
            "Configured executable identity and simulation outputs from an exact run receipt.",
        ),
        cannot_infer=(
            "Observed Manchester traffic, calibration, scientific acceptance, or "
            "VEC task outcomes.",
        ),
        allowed_current_standings=(
            SourceCurrentStanding.INSTALLATION_DETECTED,
            SourceCurrentStanding.NOT_DETECTED,
            SourceCurrentStanding.UNAVAILABLE,
        ),
        allowed_freshness=(
            SourceFreshnessStanding.SIMULATION_TIME,
            SourceFreshnessStanding.UNAVAILABLE,
        ),
    ),
    SourceFamily.MANUAL_INCIDENT: SourceDefinition(
        family=SourceFamily.MANUAL_INCIDENT,
        provider="TrafficTwin operator-authored input",
        semantic_role="authored_scenario_incident",
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        rights_standing=RightsStanding.PROJECT_AUTHORED,
        licence_id="TrafficTwin-authored",
        retention_rule="Retain the immutable authored scenario and its canonical fingerprint.",
        supported_geography=(
            "Only the explicit scenario/network extent named by the authored artifact."
        ),
        can_infer=("The exact declared synthetic incident parameters.",),
        cannot_infer=(
            "A real incident, observed traffic disruption, or causal real-world effect.",
        ),
        allowed_current_standings=(
            SourceCurrentStanding.SYNTHETIC_AVAILABLE,
            SourceCurrentStanding.UNAVAILABLE,
        ),
        allowed_freshness=(
            SourceFreshnessStanding.SYNTHETIC,
            SourceFreshnessStanding.UNAVAILABLE,
        ),
    ),
    SourceFamily.STATIC_MANCHESTER_GEOGRAPHY: SourceDefinition(
        family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
        provider="Office for National Statistics",
        semantic_role="static_boundary_context",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        rights_standing=RightsStanding.CONFIRMED,
        licence_id="OGL-3.0",
        retention_rule=(
            "Packaged, fingerprinted boundary derivatives retain ONS and OS attribution."
        ),
        supported_geography=(
            "Manchester local authority and Greater Manchester combined-authority boundaries."
        ),
        can_infer=("Static display context for the exact packaged December 2025 boundaries.",),
        cannot_infer=(
            "Road network, sensor coverage, traffic state, or scientific clipping accuracy.",
        ),
        allowed_current_standings=(
            SourceCurrentStanding.STATIC_AVAILABLE,
            SourceCurrentStanding.UNAVAILABLE,
        ),
        allowed_freshness=(
            SourceFreshnessStanding.STATIC,
            SourceFreshnessStanding.UNAVAILABLE,
        ),
    ),
}


def source_definition(family: SourceFamily) -> SourceDefinition:
    """Return the immutable definition for ``family``."""

    return _SOURCE_DEFINITIONS[family]


def all_source_definitions() -> tuple[SourceDefinition, ...]:
    """Return all frozen definitions in stable product order."""

    return tuple(_SOURCE_DEFINITIONS[family] for family in SOURCE_FAMILY_ORDER)


__all__ = [
    "CredentialPresence",
    "EvidenceStanding",
    "OperationalReceipt",
    "RightsStanding",
    "SOURCE_FAMILY_ORDER",
    "SOURCE_OPERATIONS_METHOD_VERSION",
    "SOURCE_OPERATIONS_SCHEMA_VERSION",
    "SnapshotPointer",
    "SnapshotValidationState",
    "SourceCurrentStanding",
    "SourceDefinition",
    "SourceFamily",
    "SourceFreshnessStanding",
    "SourceOperationsCatalogue",
    "SourceReadiness",
    "SourceRuntimeMetadata",
    "all_source_definitions",
    "source_definition",
]
