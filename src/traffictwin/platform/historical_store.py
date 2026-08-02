"""Aggregate historical-store and feature-registry contracts.

This module implements the engine-neutral portion of
``docs/platform/historical_store_feature_registry_design.md``.  It is a
strict, local reference implementation used to settle the data, evidence,
privacy, versioning, idempotency and atomicity contracts before the owner
selects a persistent engine, workspace, retention policy, backup policy,
licence allowlist, or publication policy.

The reference backend deliberately keeps payloads in memory.  It accepts
only schema-registered aggregate JSON and safe derived metadata; it never
opens quarantine, acquires data, persists a salt or credential, or treats
registration as scientific admission.  A later persistent adapter must pass
the same contract tests without weakening any refusal.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

METHOD_VERSION: Literal["aggregate-historical-store-1.0"] = "aggregate-historical-store-1.0"
DESIGN_REFERENCE: Literal["docs/platform/historical_store_feature_registry_design.md"] = (
    "docs/platform/historical_store_feature_registry_design.md"
)
POLICY_CEILING: Literal["owner_approved_candidate"] = "owner_approved_candidate"

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_ID_PATTERN = r"^[a-z0-9][a-z0-9._:/-]{0,159}$"
_FEATURE_NAME_PATTERN = r"^[a-z][a-z0-9_.-]{0,127}$"

_PRODUCER_CITATION_KEYS = frozenset(
    {
        "environment_repository",
        "environment_pinned_commit",
        "trace_data_repository",
        "trace_data_audited_commit",
        "engine_version",
        "author",
        "requirements_record",
    }
)

_SECRET_KEYS = frozenset(
    {
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "privatekey",
        "salt",
        "secret",
        "token",
    }
)
_IDENTIFIER_KEYS = frozenset(
    {
        "crosssessionidentity",
        "identitymapping",
        "operatorid",
        "operatoridentifier",
        "operatorref",
        "rawidentifier",
        "rawref",
        "registrationnumber",
        "sessiontoken",
        "vehicleid",
        "vehicleidentifier",
        "vehicleref",
    }
)
_PARTICIPANT_KEYS = frozenset(
    {
        "participant",
        "participantcode",
        "participantdata",
        "participantid",
        "participantresponse",
    }
)
_RAW_SOURCE_KEYS = frozenset(
    {
        "rawbods",
        "rawbytes",
        "rawpayload",
        "servicedelivery",
        "siri",
        "vehicleactivity",
        "vehiclemonitoringdelivery",
    }
)
_PRIVATE_PATH_RE = re.compile(
    r"(?:^|[\s\"'])(?:/(?:Users|home|private|tmp|var)(?:/|$)|[A-Za-z]:[\\/]|file://)",
    re.IGNORECASE,
)
_ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s\"'=(])(?:/(?!/)[A-Za-z0-9._~-][^\s\"']*|[A-Za-z]:[\\/]|file://)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]+|"
    r"\b(?:BODS|ANTHROPIC|OPENAI)_API_KEY\s*=|"
    r"\b(?:api[_-]?key|password|secret|token)\s*[:=])",
    re.IGNORECASE,
)
_IDENTIFIER_VALUE_RE = re.compile(
    r"\b(?:VehicleRef|OperatorRef|session[_-]?token|raw[_-]?ref|"
    r"cross[_-]?session[_-]?identity|participant(?:[_-]?(?:id|code|response))?)\b",
    re.IGNORECASE,
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _reject_nonfinite_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


class PayloadClass(StrEnum):
    """Only payload classes approved by the aggregate-store design."""

    AGGREGATE_SESSION_MEASUREMENT = "aggregate_session_measurement"
    PUBLIC_DESCRIPTIVE_PROFILE = "public_descriptive_profile"
    MODEL_ARTIFACT = "model_artifact"
    SAFE_ANALYSIS_SUMMARY = "safe_analysis_summary"
    SCENARIO_METADATA = "scenario_metadata"


class EvidenceRole(StrEnum):
    """Roles stay separate even when their strength is compared."""

    PROTOCOL_CONFIRMED = "protocol_confirmed"
    POST_HOC = "post_hoc"
    EXPLORATORY = "exploratory"
    DESCRIPTIVE = "descriptive"
    EXECUTION_DEVIATED = "execution_deviated"
    NON_ADMITTED_DIAGNOSTIC = "non_admitted_diagnostic"
    PREDICTION = "prediction"
    FORECAST = "forecast"
    DRAFT = "draft"
    SOFTWARE_EVIDENCE = "software_evidence"


class AdmissionStatus(StrEnum):
    """Storage never changes these authoritative admission states."""

    ADMITTED = "admitted"
    NON_ADMITTED = "non_admitted"
    NOT_APPLICABLE = "not_applicable"


class CatalogueNamespace(StrEnum):
    """Namespaces make admitted and Sparse-64 lookup separation structural."""

    GENERAL = "general"
    ADMITTED_VEC = "admitted_vec"
    ADMITTED_SPARSE64_DEVIATED = "admitted_sparse64_deviated"
    NON_ADMITTED_SPARSE64 = "non_admitted_sparse64"


class ContentScope(StrEnum):
    AGGREGATE_PAYLOAD = "aggregate_payload"
    METADATA_ONLY = "metadata_only"


class SourceKind(StrEnum):
    AUTHORITATIVE_RECORD = "authoritative_record"
    HISTORICAL_DATASET = "historical_dataset"


class EvidenceRestriction(StrEnum):
    ADMITTED_ONLY = "admitted_only"
    ADMITTED_EXECUTION_DEVIATED_ONLY = "admitted_execution_deviated_only"
    NON_ADMITTED_ONLY = "non_admitted_only"
    ANY_SAFE = "any_safe"


class RefusalCode(StrEnum):
    """Typed refusal codes from the design plus strict boundary refinements."""

    RAW_SOURCE_FORBIDDEN = "RAW_SOURCE_FORBIDDEN"
    PRIVATE_PATH_DETECTED = "PRIVATE_PATH_DETECTED"
    IDENTIFIER_FIELD_FORBIDDEN = "IDENTIFIER_FIELD_FORBIDDEN"
    SECRET_DETECTED = "SECRET_DETECTED"  # noqa: S105 - refusal code, not a credential
    PARTICIPANT_DATA_FORBIDDEN = "PARTICIPANT_DATA_FORBIDDEN"
    SCHEMA_UNSUPPORTED = "SCHEMA_UNSUPPORTED"
    SCHEMA_DIGEST_MISMATCH = "SCHEMA_DIGEST_MISMATCH"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    LOGICAL_ID_CONFLICT = "LOGICAL_ID_CONFLICT"
    FEATURE_INCOMPATIBLE = "FEATURE_INCOMPATIBLE"
    FEATURE_VERSION_GAP = "FEATURE_VERSION_GAP"
    SNAPSHOT_CONFLICT = "SNAPSHOT_CONFLICT"
    STANDING_ESCALATION = "STANDING_ESCALATION"
    LICENCE_METADATA_MISSING = "LICENCE_METADATA_MISSING"
    LICENCE_NOT_ALLOWLISTED = "LICENCE_NOT_ALLOWLISTED"
    PARTIAL_COMMIT = "PARTIAL_COMMIT"
    SOURCE_RECORD_MISSING = "SOURCE_RECORD_MISSING"
    NON_ADMITTED_PROMOTION = "NON_ADMITTED_PROMOTION"


class StoreModel(BaseModel):
    """Strict immutable base with deterministic identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class EvidenceStanding(StoreModel):
    evidence_role: EvidenceRole
    admission_status: AdmissionStatus
    policy_ceiling: Literal["owner_approved_candidate"] = POLICY_CEILING
    evidence: bool
    causal: Literal[False] = False
    execution_deviation: bool = False

    @model_validator(mode="after")
    def validate_false_evidence_roles(self) -> EvidenceStanding:
        false_roles = {
            EvidenceRole.DRAFT,
            EvidenceRole.FORECAST,
            EvidenceRole.NON_ADMITTED_DIAGNOSTIC,
            EvidenceRole.PREDICTION,
        }
        if self.evidence_role in false_roles and self.evidence:
            raise ValueError(f"{self.evidence_role.value} must remain evidence=false")
        if self.admission_status is AdmissionStatus.NON_ADMITTED and self.evidence:
            raise ValueError("non-admitted material must remain evidence=false")
        if self.evidence_role is EvidenceRole.EXECUTION_DEVIATED and not self.execution_deviation:
            raise ValueError("execution_deviated role requires execution_deviation=true")
        return self


class CitationEntry(StoreModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    value: str = Field(min_length=1, max_length=500)


class SupportCount(StoreModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    value: int = Field(ge=0)


class SourceBinding(StoreModel):
    source_kind: SourceKind
    source_id: str = Field(pattern=_ID_PATTERN)
    expected_record_digest: str = Field(pattern=_DIGEST_PATTERN)
    expected_payload_digest: str = Field(pattern=_DIGEST_PATTERN)


class AuthoritativeSourceRecord(StoreModel):
    """Safe metadata supplied by an existing admission/provenance authority."""

    source_record_id: str = Field(pattern=_ID_PATTERN)
    record_digest: str = Field(pattern=_DIGEST_PATTERN)
    payload_digest: str = Field(pattern=_DIGEST_PATTERN)
    schema_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    schema_version: int = Field(ge=1)
    payload_class: PayloadClass
    standing: EvidenceStanding
    sparse64: bool = False
    metadata_only: bool = False
    safe_metadata_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_sparse64_standing(self) -> AuthoritativeSourceRecord:
        if not self.sparse64:
            return self
        if not self.metadata_only:
            raise ValueError("Sparse-64 authority records must remain metadata-only")
        if self.standing.admission_status is AdmissionStatus.NON_ADMITTED:
            if self.standing.evidence:
                raise ValueError("non-admitted Sparse-64 authority must remain evidence=false")
            return self
        if self.standing.admission_status is AdmissionStatus.ADMITTED:
            if (
                self.standing.evidence_role is not EvidenceRole.EXECUTION_DEVIATED
                or not self.standing.execution_deviation
                or not self.standing.evidence
            ):
                raise ValueError(
                    "admitted Sparse-64 authority must preserve its execution deviation"
                )
            return self
        raise ValueError("Sparse-64 authority requires an explicit admission status")


class SchemaLiteral(StoreModel):
    field: str = Field(min_length=1, max_length=80)
    value: str | int | bool


class DatasetSchemaContract(StoreModel):
    """Engine-neutral schema gate for one exact aggregate JSON version."""

    schema_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    schema_version: int = Field(ge=1)
    payload_class: PayloadClass
    required_top_level_keys: tuple[str, ...] = ()
    allowed_top_level_keys: tuple[str, ...] = ()
    required_literals: tuple[SchemaLiteral, ...] = ()
    sparse64_metadata_compatible: bool = False
    sparse64_admitted_aggregate_compatible: bool = False

    @model_validator(mode="after")
    def validate_keys(self) -> DatasetSchemaContract:
        required = set(self.required_top_level_keys)
        allowed = set(self.allowed_top_level_keys)
        if len(required) != len(self.required_top_level_keys):
            raise ValueError("required_top_level_keys must be unique")
        if allowed and len(allowed) != len(self.allowed_top_level_keys):
            raise ValueError("allowed_top_level_keys must be unique")
        if allowed and not required <= allowed:
            raise ValueError("required_top_level_keys must be allowed")
        literal_fields = [item.field for item in self.required_literals]
        if len(set(literal_fields)) != len(literal_fields):
            raise ValueError("required literal fields must be unique")
        if allowed and not set(literal_fields) <= allowed:
            raise ValueError("required literal fields must be allowed")
        if self.sparse64_metadata_compatible and self.sparse64_admitted_aggregate_compatible:
            raise ValueError("a Sparse-64 schema must target exactly one standing namespace")
        return self


class HistoricalDatasetRecord(StoreModel):
    """Immutable catalogue metadata for one safe aggregate payload."""

    record_type: Literal["historical_dataset"] = "historical_dataset"
    method_version: Literal["aggregate-historical-store-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/historical_store_feature_registry_design.md"] = (
        DESIGN_REFERENCE
    )
    dataset_id: str = Field(pattern=_ID_PATTERN)
    logical_source_id: str = Field(pattern=_ID_PATTERN)
    payload_class: PayloadClass
    schema_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    schema_version: int = Field(ge=1)
    schema_digest: str = Field(pattern=_DIGEST_PATTERN)
    payload_digest: str = Field(pattern=_DIGEST_PATTERN)
    payload_handle: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_bindings: tuple[SourceBinding, ...] = Field(min_length=1)
    created_at_utc: datetime
    event_time_start_utc: datetime | None = None
    event_time_end_utc: datetime | None = None
    local_service_dates: tuple[str, ...] = ()
    timezone: str | None = None
    support: tuple[SupportCount, ...] = ()
    exclusions: tuple[str, ...] = ()
    refusal_count: int = Field(default=0, ge=0)
    standing: EvidenceStanding
    citation_bundle: tuple[CitationEntry, ...] = Field(min_length=1)
    producer_derived: bool = False
    licence_class: str = Field(min_length=1, max_length=120)
    namespace: CatalogueNamespace
    content_scope: ContentScope = ContentScope.AGGREGATE_PAYLOAD
    sparse64: bool = False
    aggregate_only: Literal[True] = True
    raw_identifiers_present: Literal[False] = False
    participant_data_present: Literal[False] = False
    immutable: Literal[True] = True

    @field_validator("created_at_utc", "event_time_start_utc", "event_time_end_utc")
    @classmethod
    def require_aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must be timezone-aware")
        return value

    @field_validator("local_service_dates")
    @classmethod
    def validate_service_dates(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("local_service_dates must be unique")
        for value in values:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("local service dates must use YYYY-MM-DD")
        return values

    @model_validator(mode="after")
    def validate_boundaries(self) -> HistoricalDatasetRecord:
        if self.payload_handle != f"sha256:{self.payload_digest}":
            raise ValueError("payload_handle must be the payload content address")
        if (self.event_time_start_utc is None) != (self.event_time_end_utc is None):
            raise ValueError("event-time bounds must be supplied together")
        if (
            self.event_time_start_utc is not None
            and self.event_time_end_utc is not None
            and self.event_time_end_utc < self.event_time_start_utc
        ):
            raise ValueError("event_time_end_utc precedes event_time_start_utc")
        if self.local_service_dates and not self.timezone:
            raise ValueError("local service dates require explicit timezone metadata")
        if len({item.name for item in self.support}) != len(self.support):
            raise ValueError("support names must be unique")
        if len({item.key for item in self.citation_bundle}) != len(self.citation_bundle):
            raise ValueError("citation keys must be unique")
        if self.producer_derived:
            keys = {item.key for item in self.citation_bundle}
            missing = _PRODUCER_CITATION_KEYS - keys
            if missing:
                raise ValueError(f"producer-derived record lacks citation keys: {sorted(missing)}")
        if self.sparse64:
            non_admitted = (
                self.namespace is CatalogueNamespace.NON_ADMITTED_SPARSE64
                and self.content_scope is ContentScope.METADATA_ONLY
                and self.standing.admission_status is AdmissionStatus.NON_ADMITTED
                and not self.standing.evidence
            )
            admitted_with_deviation = (
                self.namespace is CatalogueNamespace.ADMITTED_SPARSE64_DEVIATED
                and self.content_scope is ContentScope.AGGREGATE_PAYLOAD
                and self.standing.admission_status is AdmissionStatus.ADMITTED
                and self.standing.evidence_role is EvidenceRole.EXECUTION_DEVIATED
                and self.standing.execution_deviation
                and self.standing.evidence
            )
            if not non_admitted and not admitted_with_deviation:
                raise ValueError(
                    "Sparse-64 records must use their segregated non-admitted or "
                    "admitted-with-deviation namespace"
                )
        elif self.namespace in {
            CatalogueNamespace.NON_ADMITTED_SPARSE64,
            CatalogueNamespace.ADMITTED_SPARSE64_DEVIATED,
        }:
            raise ValueError("Sparse-64 namespaces require sparse64=true")
        if (
            self.namespace is CatalogueNamespace.ADMITTED_VEC
            and self.standing.admission_status is not AdmissionStatus.ADMITTED
        ):
            raise ValueError("the admitted VEC namespace accepts admitted records only")
        return self

    def support_value(self, name: str) -> int | None:
        for item in self.support:
            if item.name == name:
                return item.value
        return None


class FeatureInputRequirement(StoreModel):
    schema_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    minimum_schema_version: int = Field(ge=1)
    maximum_schema_version: int = Field(ge=1)
    minimum_support: tuple[SupportCount, ...] = ()

    @model_validator(mode="after")
    def validate_range(self) -> FeatureInputRequirement:
        if self.maximum_schema_version < self.minimum_schema_version:
            raise ValueError("maximum schema version precedes minimum")
        if len({item.name for item in self.minimum_support}) != len(self.minimum_support):
            raise ValueError("minimum support names must be unique")
        return self


class FeatureDefinition(StoreModel):
    """One immutable, monotonically versioned feature definition."""

    record_type: Literal["feature_definition"] = "feature_definition"
    method_version: Literal["aggregate-historical-store-1.0"] = METHOD_VERSION
    feature_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    definition_version: int = Field(ge=1)
    supersedes_version: int | None = Field(default=None, ge=1)
    value_type: Literal["integer", "float", "string", "boolean", "timestamp"]
    units: str = Field(min_length=1, max_length=80)
    null_semantics: Literal["forbidden", "missing", "unavailable", "not_applicable"]
    aggregation_grain: str = Field(min_length=1, max_length=160)
    transformation_id: str = Field(pattern=_ID_PATTERN)
    implementation_digest: str = Field(pattern=_DIGEST_PATTERN)
    required_inputs: tuple[FeatureInputRequirement, ...] = Field(min_length=1)
    leakage_boundary: str = Field(min_length=1, max_length=500)
    evidence_restriction: EvidenceRestriction
    namespace: CatalogueNamespace
    deprecated: bool = False
    immutable: Literal[True] = True

    @model_validator(mode="after")
    def validate_version_relation(self) -> FeatureDefinition:
        if self.definition_version == 1 and self.supersedes_version is not None:
            raise ValueError("feature version 1 cannot supersede another version")
        if self.definition_version > 1 and self.supersedes_version != self.definition_version - 1:
            raise ValueError("feature versions must supersede the immediately prior version")
        if (
            self.evidence_restriction is EvidenceRestriction.ADMITTED_ONLY
            and self.namespace is not CatalogueNamespace.ADMITTED_VEC
        ):
            raise ValueError("admitted-only features must use the admitted VEC namespace")
        if (
            self.evidence_restriction is EvidenceRestriction.NON_ADMITTED_ONLY
            and self.namespace is not CatalogueNamespace.NON_ADMITTED_SPARSE64
        ):
            raise ValueError("non-admitted-only features must use the segregated namespace")
        if (
            self.evidence_restriction is EvidenceRestriction.ADMITTED_EXECUTION_DEVIATED_ONLY
            and self.namespace is not CatalogueNamespace.ADMITTED_SPARSE64_DEVIATED
        ):
            raise ValueError(
                "admitted execution-deviated features must use their segregated namespace"
            )
        return self

    @property
    def definition_digest(self) -> str:
        return self.fingerprint()


class DatasetDigestBinding(StoreModel):
    dataset_id: str = Field(pattern=_ID_PATTERN)
    expected_record_digest: str = Field(pattern=_DIGEST_PATTERN)
    expected_payload_digest: str = Field(pattern=_DIGEST_PATTERN)


class FeatureMaterialisationRequest(StoreModel):
    snapshot_id: str = Field(pattern=_ID_PATTERN)
    feature_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    feature_version: int = Field(ge=1)
    definition_digest: str = Field(pattern=_DIGEST_PATTERN)
    dataset_bindings: tuple[DatasetDigestBinding, ...] = Field(min_length=1)
    values_digest: str = Field(pattern=_DIGEST_PATTERN)
    row_count: int = Field(ge=0)
    coverage: tuple[SupportCount, ...] = ()
    exclusions: tuple[str, ...] = ()
    created_at_utc: datetime
    namespace: CatalogueNamespace

    @field_validator("created_at_utc")
    @classmethod
    def require_aware_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at_utc must be timezone-aware")
        return value


def _snapshot_identity_payload(
    *,
    snapshot_id: str,
    feature_name: str,
    feature_version: int,
    definition_digest: str,
    dataset_bindings: Sequence[DatasetDigestBinding],
    values_digest: str,
    row_count: int,
    coverage: Sequence[SupportCount],
    exclusions: Sequence[str],
    created_at_utc: datetime,
    standing: EvidenceStanding,
    namespace: CatalogueNamespace,
) -> dict[str, object]:
    return {
        "snapshot_id": snapshot_id,
        "feature_name": feature_name,
        "feature_version": feature_version,
        "definition_digest": definition_digest,
        "dataset_bindings": [item.model_dump(mode="json") for item in dataset_bindings],
        "values_digest": values_digest,
        "row_count": row_count,
        "coverage": [item.model_dump(mode="json") for item in coverage],
        "exclusions": list(exclusions),
        "created_at_utc": created_at_utc.isoformat(),
        "standing": standing.model_dump(mode="json"),
        "namespace": namespace.value,
    }


class FeatureSnapshot(StoreModel):
    """Immutable binding of values, inputs and one feature-definition version."""

    record_type: Literal["feature_snapshot"] = "feature_snapshot"
    method_version: Literal["aggregate-historical-store-1.0"] = METHOD_VERSION
    snapshot_id: str = Field(pattern=_ID_PATTERN)
    feature_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    feature_version: int = Field(ge=1)
    definition_digest: str = Field(pattern=_DIGEST_PATTERN)
    dataset_bindings: tuple[DatasetDigestBinding, ...]
    values_digest: str = Field(pattern=_DIGEST_PATTERN)
    values_handle: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    coverage: tuple[SupportCount, ...]
    exclusions: tuple[str, ...]
    created_at_utc: datetime
    standing: EvidenceStanding
    namespace: CatalogueNamespace
    snapshot_digest: str = Field(pattern=_DIGEST_PATTERN)
    aggregate_only: Literal[True] = True
    immutable: Literal[True] = True

    @field_validator("created_at_utc")
    @classmethod
    def require_aware_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at_utc must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_value_handle(self) -> FeatureSnapshot:
        if self.values_handle != f"sha256:{self.values_digest}":
            raise ValueError("values_handle must be the values content address")
        expected = _fingerprint(
            _snapshot_identity_payload(
                snapshot_id=self.snapshot_id,
                feature_name=self.feature_name,
                feature_version=self.feature_version,
                definition_digest=self.definition_digest,
                dataset_bindings=self.dataset_bindings,
                values_digest=self.values_digest,
                row_count=self.row_count,
                coverage=self.coverage,
                exclusions=self.exclusions,
                created_at_utc=self.created_at_utc,
                standing=self.standing,
                namespace=self.namespace,
            )
        )
        if self.snapshot_digest != expected:
            raise ValueError("snapshot digest does not bind the immutable snapshot fields")
        return self


class StoreReceipt(StoreModel):
    operation: Literal["register_dataset"] = "register_dataset"
    dataset_id: str
    payload_digest: str = Field(pattern=_DIGEST_PATTERN)
    record_digest: str = Field(pattern=_DIGEST_PATTERN)
    idempotent_retry: bool
    atomic_commit: Literal[True] = True
    evidence_upgrade_performed: Literal[False] = False
    state_digest: str = Field(pattern=_DIGEST_PATTERN)


class FeatureReceipt(StoreModel):
    operation: Literal["register_feature"] = "register_feature"
    feature_name: str
    definition_version: int
    definition_digest: str = Field(pattern=_DIGEST_PATTERN)
    idempotent_retry: bool
    atomic_commit: Literal[True] = True
    state_digest: str = Field(pattern=_DIGEST_PATTERN)


class StoreRefusal(StoreModel):
    operation: Literal[
        "register_dataset",
        "register_feature",
        "materialise_snapshot",
        "get_dataset",
        "provenance_walk",
    ]
    code: RefusalCode
    message: str
    subject_id: str
    state_digest_before: str = Field(pattern=_DIGEST_PATTERN)
    state_digest_after: str = Field(pattern=_DIGEST_PATTERN)
    state_changed: Literal[False] = False
    evidence: Literal[False] = False


class CatalogueQuery(StoreModel):
    """Allowlisted query fields; no SQL, path, sort expression or newest-version shortcut."""

    schema_name: str = Field(pattern=_FEATURE_NAME_PATTERN)
    minimum_schema_version: int = Field(ge=1)
    maximum_schema_version: int = Field(ge=1)
    namespace: CatalogueNamespace
    payload_class: PayloadClass | None = None
    evidence_role: EvidenceRole | None = None
    admission_status: AdmissionStatus | None = None

    @model_validator(mode="after")
    def validate_range(self) -> CatalogueQuery:
        if self.maximum_schema_version < self.minimum_schema_version:
            raise ValueError("maximum schema version precedes minimum")
        return self


class ProvenanceWalk(StoreModel):
    snapshot: FeatureSnapshot
    feature_definition: FeatureDefinition
    datasets: tuple[HistoricalDatasetRecord, ...]
    authoritative_sources: tuple[AuthoritativeSourceRecord, ...]
    complete: Literal[True] = True


class MigrationDryRunFinding(StoreModel):
    dataset_id: str
    status: Literal["would_register", "would_reuse", "would_refuse"]
    refusal_code: RefusalCode | None = None


class MigrationDryRunReport(StoreModel):
    method_version: Literal["aggregate-historical-store-1.0"] = METHOD_VERSION
    dry_run: Literal[True] = True
    datasets_examined: int = Field(ge=0)
    would_register: int = Field(ge=0)
    would_reuse: int = Field(ge=0)
    would_refuse: int = Field(ge=0)
    findings: tuple[MigrationDryRunFinding, ...]
    source_payload_digests_before: tuple[str, ...]
    source_payload_digests_after: tuple[str, ...]
    source_bytes_unchanged: Literal[True] = True
    source_records_unchanged: Literal[True] = True
    store_state_digest_before: str = Field(pattern=_DIGEST_PATTERN)
    store_state_digest_after: str = Field(pattern=_DIGEST_PATTERN)
    store_unchanged: Literal[True] = True


@dataclass(frozen=True)
class DatasetRegistrationCandidate:
    """A record plus exact aggregate payload bytes; bytes are never printed."""

    record: HistoricalDatasetRecord
    payload: bytes = field(repr=False)


@dataclass(frozen=True)
class FeatureSnapshotCandidate:
    request: FeatureMaterialisationRequest
    values_payload: bytes = field(repr=False)


@dataclass(frozen=True)
class _StoreState:
    datasets: dict[str, HistoricalDatasetRecord]
    payloads: dict[str, bytes]
    features: dict[tuple[str, int], FeatureDefinition]
    snapshots: dict[str, FeatureSnapshot]


class _Rejected(RuntimeError):  # noqa: N818 - private validation sentinel, never public API
    def __init__(self, code: RefusalCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


def _screen_value(value: object, *, screen_keys: bool = True) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise _Rejected(RefusalCode.SCHEMA_UNSUPPORTED, "JSON object keys must be strings")
            key = _normalise_key(raw_key)
            if screen_keys:
                if key in _SECRET_KEYS or key.endswith(
                    ("apikey", "credential", "password", "salt", "secret", "token")
                ):
                    raise _Rejected(RefusalCode.SECRET_DETECTED, "secret-bearing field refused")
                if key in _IDENTIFIER_KEYS or key.rstrip("s") in _IDENTIFIER_KEYS:
                    raise _Rejected(
                        RefusalCode.IDENTIFIER_FIELD_FORBIDDEN,
                        "raw or cross-session identifier field refused",
                    )
                if key in _PARTICIPANT_KEYS or key.startswith("participant"):
                    raise _Rejected(
                        RefusalCode.PARTICIPANT_DATA_FORBIDDEN,
                        "participant field refused",
                    )
                if key in _RAW_SOURCE_KEYS:
                    raise _Rejected(
                        RefusalCode.RAW_SOURCE_FORBIDDEN,
                        "raw source field refused",
                    )
            _screen_value(item, screen_keys=screen_keys)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _screen_value(item, screen_keys=screen_keys)
        return
    if isinstance(value, str):
        if _ABSOLUTE_PATH_RE.search(value) or _PRIVATE_PATH_RE.search(value):
            raise _Rejected(
                RefusalCode.PRIVATE_PATH_DETECTED,
                "private or absolute path content refused",
            )
        if _SECRET_VALUE_RE.search(value):
            raise _Rejected(RefusalCode.SECRET_DETECTED, "secret-like content refused")
        if _IDENTIFIER_VALUE_RE.search(value):
            raise _Rejected(
                RefusalCode.IDENTIFIER_FIELD_FORBIDDEN,
                "raw or cross-session identifier content refused",
            )
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise _Rejected(RefusalCode.SCHEMA_UNSUPPORTED, "non-finite number refused")


def _parse_aggregate_json(payload: bytes) -> dict[str, object]:
    if payload.startswith((b"\x1f\x8b", b"PK\x03\x04")):
        raise _Rejected(RefusalCode.RAW_SOURCE_FORBIDDEN, "compressed/archive bytes refused")
    if payload.lstrip().startswith(b"<"):
        raise _Rejected(RefusalCode.RAW_SOURCE_FORBIDDEN, "XML/raw feed bytes refused")
    try:
        decoded = payload.decode("utf-8")
        parsed = cast(
            object,
            json.loads(decoded, parse_constant=_reject_nonfinite_constant),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _Rejected(
            RefusalCode.SCHEMA_UNSUPPORTED,
            "payload must be finite UTF-8 aggregate JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise _Rejected(
            RefusalCode.SCHEMA_UNSUPPORTED,
            "aggregate payload must be a top-level JSON object",
        )
    result = cast(dict[str, object], parsed)
    _screen_value(result)
    return result


_ROLE_STRENGTH = {
    EvidenceRole.EXECUTION_DEVIATED: 0,
    EvidenceRole.NON_ADMITTED_DIAGNOSTIC: 0,
    EvidenceRole.DRAFT: 0,
    EvidenceRole.PREDICTION: 0,
    EvidenceRole.FORECAST: 0,
    EvidenceRole.DESCRIPTIVE: 1,
    EvidenceRole.SOFTWARE_EVIDENCE: 1,
    EvidenceRole.EXPLORATORY: 2,
    EvidenceRole.POST_HOC: 3,
    EvidenceRole.PROTOCOL_CONFIRMED: 4,
}
_ADMISSION_STRENGTH = {
    AdmissionStatus.NON_ADMITTED: 0,
    AdmissionStatus.NOT_APPLICABLE: 1,
    AdmissionStatus.ADMITTED: 2,
}


def _ensure_standing_not_stronger(
    candidate: EvidenceStanding,
    sources: Sequence[EvidenceStanding],
) -> None:
    if not sources:
        raise _Rejected(RefusalCode.SOURCE_RECORD_MISSING, "no source standing available")
    if candidate.evidence and any(not source.evidence for source in sources):
        raise _Rejected(
            RefusalCode.STANDING_ESCALATION,
            "evidence=false cannot become evidence=true",
        )
    if _ADMISSION_STRENGTH[candidate.admission_status] > min(
        _ADMISSION_STRENGTH[source.admission_status] for source in sources
    ):
        raise _Rejected(RefusalCode.STANDING_ESCALATION, "admission standing escalation refused")
    if _ROLE_STRENGTH[candidate.evidence_role] > min(
        _ROLE_STRENGTH[source.evidence_role] for source in sources
    ):
        raise _Rejected(RefusalCode.STANDING_ESCALATION, "evidence-role escalation refused")
    if any(source.execution_deviation for source in sources) and not candidate.execution_deviation:
        raise _Rejected(
            RefusalCode.STANDING_ESCALATION,
            "execution deviation cannot be cleared by registration",
        )


def _weakest_standing(sources: Sequence[EvidenceStanding]) -> EvidenceStanding:
    if not sources:
        raise _Rejected(RefusalCode.SOURCE_RECORD_MISSING, "no source standing available")
    weakest_role = min(sources, key=lambda item: _ROLE_STRENGTH[item.evidence_role]).evidence_role
    weakest_admission = min(
        sources,
        key=lambda item: _ADMISSION_STRENGTH[item.admission_status],
    ).admission_status
    return EvidenceStanding(
        evidence_role=weakest_role,
        admission_status=weakest_admission,
        evidence=all(item.evidence for item in sources),
        execution_deviation=any(item.execution_deviation for item in sources),
    )


class InMemoryHistoricalStore:
    """Transactional reference backend for the engine-neutral contract.

    No persistent-engine or workspace decision is encoded here.  Every write
    validates into copied state and publishes with one state-reference swap.
    An injected ``before_commit`` callback exists solely for crash/rollback
    contract tests; a callback failure returns ``PARTIAL_COMMIT`` while the
    original state remains byte-identical.
    """

    def __init__(
        self,
        *,
        schemas: Sequence[DatasetSchemaContract],
        authoritative_sources: Sequence[AuthoritativeSourceRecord],
        licence_allowlist: frozenset[str],
        before_commit: Callable[[str], None] | None = None,
    ) -> None:
        schema_map = {(item.schema_name, item.schema_version): item for item in schemas}
        if len(schema_map) != len(schemas):
            raise ValueError("schema identities must be unique")
        source_map = {item.source_record_id: item for item in authoritative_sources}
        if len(source_map) != len(authoritative_sources):
            raise ValueError("authoritative source ids must be unique")
        if not licence_allowlist:
            raise ValueError("a caller-supplied licence allowlist is required")
        self._schemas = schema_map
        self._authoritative_sources = source_map
        self._licence_allowlist = licence_allowlist
        self._before_commit = before_commit
        self._lock = threading.RLock()
        self._state = _StoreState(datasets={}, payloads={}, features={}, snapshots={})

    def state_digest(self) -> str:
        """Return a content identity without exposing payload bytes."""

        with self._lock:
            return self._state_digest(self._state)

    @staticmethod
    def _state_digest(state: _StoreState) -> str:
        value = {
            "datasets": {
                key: item.model_dump(mode="json") for key, item in sorted(state.datasets.items())
            },
            "features": {
                f"{name}@{version}": item.model_dump(mode="json")
                for (name, version), item in sorted(state.features.items())
            },
            "payload_digests": sorted(state.payloads),
            "snapshots": {
                key: item.model_dump(mode="json") for key, item in sorted(state.snapshots.items())
            },
        }
        return _fingerprint(value)

    def _refusal(
        self,
        *,
        operation: Literal[
            "register_dataset",
            "register_feature",
            "materialise_snapshot",
            "get_dataset",
            "provenance_walk",
        ],
        code: RefusalCode,
        message: str,
        subject_id: str,
        before: str,
    ) -> StoreRefusal:
        after = self._state_digest(self._state)
        if after != before:
            raise RuntimeError("refusal path changed store state")
        return StoreRefusal(
            operation=operation,
            code=code,
            message=message,
            subject_id=subject_id,
            state_digest_before=before,
            state_digest_after=after,
        )

    def _source_records_for(
        self,
        bindings: Sequence[SourceBinding],
    ) -> tuple[AuthoritativeSourceRecord | HistoricalDatasetRecord, ...]:
        records: list[AuthoritativeSourceRecord | HistoricalDatasetRecord] = []
        for binding in bindings:
            if binding.source_kind is SourceKind.AUTHORITATIVE_RECORD:
                authoritative = self._authoritative_sources.get(binding.source_id)
                if authoritative is None:
                    raise _Rejected(
                        RefusalCode.SOURCE_RECORD_MISSING,
                        "authoritative source record is not registered",
                    )
                resolved: AuthoritativeSourceRecord | HistoricalDatasetRecord = authoritative
                record_digest = authoritative.record_digest
                payload_digest = authoritative.payload_digest
            else:
                dataset = self._state.datasets.get(binding.source_id)
                if dataset is None:
                    raise _Rejected(
                        RefusalCode.SOURCE_RECORD_MISSING,
                        "historical source dataset is not registered",
                    )
                resolved = dataset
                record_digest = dataset.fingerprint()
                payload_digest = dataset.payload_digest
            if record_digest != binding.expected_record_digest:
                raise _Rejected(RefusalCode.DIGEST_MISMATCH, "source record digest mismatch")
            if payload_digest != binding.expected_payload_digest:
                raise _Rejected(RefusalCode.DIGEST_MISMATCH, "source payload digest mismatch")
            records.append(resolved)
        return tuple(records)

    def _validate_dataset(self, candidate: DatasetRegistrationCandidate) -> None:
        record = candidate.record
        observed_digest = hashlib.sha256(candidate.payload).hexdigest()
        if observed_digest != record.payload_digest:
            raise _Rejected(RefusalCode.DIGEST_MISMATCH, "payload digest mismatch")
        parsed = _parse_aggregate_json(candidate.payload)
        _screen_value(record.model_dump(mode="json"), screen_keys=False)
        schema = self._schemas.get((record.schema_name, record.schema_version))
        if schema is None:
            raise _Rejected(RefusalCode.SCHEMA_UNSUPPORTED, "dataset schema is not registered")
        if schema.fingerprint() != record.schema_digest:
            raise _Rejected(
                RefusalCode.SCHEMA_DIGEST_MISMATCH,
                "dataset schema digest does not match the registered contract",
            )
        if schema.payload_class is not record.payload_class:
            raise _Rejected(RefusalCode.SCHEMA_UNSUPPORTED, "payload class conflicts with schema")
        keys = set(parsed)
        required = set(schema.required_top_level_keys)
        if not required <= keys:
            raise _Rejected(RefusalCode.SCHEMA_UNSUPPORTED, "required aggregate fields are missing")
        allowed = set(schema.allowed_top_level_keys)
        if allowed and not keys <= allowed:
            raise _Rejected(RefusalCode.SCHEMA_UNSUPPORTED, "unexpected aggregate field refused")
        for requirement in schema.required_literals:
            observed = parsed.get(requirement.field)
            if type(observed) is not type(requirement.value) or observed != requirement.value:
                raise _Rejected(RefusalCode.SCHEMA_UNSUPPORTED, "schema literal mismatch")
        if not record.licence_class.strip():
            raise _Rejected(
                RefusalCode.LICENCE_METADATA_MISSING,
                "licence metadata is required",
            )
        if record.licence_class not in self._licence_allowlist:
            raise _Rejected(
                RefusalCode.LICENCE_NOT_ALLOWLISTED,
                "licence class is not present in the caller-approved allowlist",
            )
        sources = self._source_records_for(record.source_bindings)
        source_standings = [item.standing for item in sources]
        _ensure_standing_not_stronger(record.standing, source_standings)
        sparse_sources = any(
            item.sparse64 if isinstance(item, AuthoritativeSourceRecord) else item.sparse64
            for item in sources
        )
        if sparse_sources and not record.sparse64:
            raise _Rejected(
                RefusalCode.NON_ADMITTED_PROMOTION,
                "Sparse-64 source must remain in its segregated namespace",
            )
        if record.sparse64:
            schema_allowed = (
                record.namespace is CatalogueNamespace.NON_ADMITTED_SPARSE64
                and schema.sparse64_metadata_compatible
            ) or (
                record.namespace is CatalogueNamespace.ADMITTED_SPARSE64_DEVIATED
                and schema.sparse64_admitted_aggregate_compatible
            )
            if not schema_allowed:
                raise _Rejected(
                    RefusalCode.NON_ADMITTED_PROMOTION,
                    "schema is not approved for the selected Sparse-64 namespace",
                )

    def register_dataset(
        self,
        candidate: DatasetRegistrationCandidate,
    ) -> StoreReceipt | StoreRefusal:
        """Validate and atomically register one exact aggregate payload."""

        with self._lock:
            before = self._state_digest(self._state)
            record = candidate.record
            try:
                self._validate_dataset(candidate)
                existing = self._state.datasets.get(record.dataset_id)
                if existing is not None:
                    if existing.fingerprint() != record.fingerprint():
                        raise _Rejected(
                            RefusalCode.LOGICAL_ID_CONFLICT,
                            "dataset id already binds different immutable content",
                        )
                    return StoreReceipt(
                        dataset_id=record.dataset_id,
                        payload_digest=record.payload_digest,
                        record_digest=record.fingerprint(),
                        idempotent_retry=True,
                        state_digest=before,
                    )
                staged = _StoreState(
                    datasets={**self._state.datasets, record.dataset_id: record},
                    payloads={**self._state.payloads, record.payload_digest: candidate.payload},
                    features=dict(self._state.features),
                    snapshots=dict(self._state.snapshots),
                )
                if self._before_commit is not None:
                    self._before_commit("register_dataset")
                self._state = staged
            except _Rejected as exc:
                return self._refusal(
                    operation="register_dataset",
                    code=exc.code,
                    message=exc.safe_message,
                    subject_id=record.dataset_id,
                    before=before,
                )
            except Exception:
                return self._refusal(
                    operation="register_dataset",
                    code=RefusalCode.PARTIAL_COMMIT,
                    message="transaction aborted before atomic publication",
                    subject_id=record.dataset_id,
                    before=before,
                )
            return StoreReceipt(
                dataset_id=record.dataset_id,
                payload_digest=record.payload_digest,
                record_digest=record.fingerprint(),
                idempotent_retry=False,
                state_digest=self._state_digest(self._state),
            )

    def register_feature(self, definition: FeatureDefinition) -> FeatureReceipt | StoreRefusal:
        """Register an immutable definition in a gap-free version sequence."""

        with self._lock:
            before = self._state_digest(self._state)
            subject = f"{definition.feature_name}@{definition.definition_version}"
            try:
                _screen_value(definition.model_dump(mode="json"), screen_keys=False)
                key = (definition.feature_name, definition.definition_version)
                existing = self._state.features.get(key)
                if existing is not None:
                    if existing.definition_digest != definition.definition_digest:
                        raise _Rejected(
                            RefusalCode.LOGICAL_ID_CONFLICT,
                            "feature version already binds different immutable content",
                        )
                    return FeatureReceipt(
                        feature_name=definition.feature_name,
                        definition_version=definition.definition_version,
                        definition_digest=definition.definition_digest,
                        idempotent_retry=True,
                        state_digest=before,
                    )
                versions = [
                    version
                    for name, version in self._state.features
                    if name == definition.feature_name
                ]
                expected = max(versions, default=0) + 1
                if definition.definition_version != expected:
                    raise _Rejected(
                        RefusalCode.FEATURE_VERSION_GAP,
                        "feature definitions must be registered in monotonic gap-free order",
                    )
                for requirement in definition.required_inputs:
                    if not any(
                        name == requirement.schema_name
                        and requirement.minimum_schema_version
                        <= version
                        <= requirement.maximum_schema_version
                        for name, version in self._schemas
                    ):
                        raise _Rejected(
                            RefusalCode.FEATURE_INCOMPATIBLE,
                            "feature input schema range is not registered",
                        )
                staged = _StoreState(
                    datasets=dict(self._state.datasets),
                    payloads=dict(self._state.payloads),
                    features={**self._state.features, key: definition},
                    snapshots=dict(self._state.snapshots),
                )
                if self._before_commit is not None:
                    self._before_commit("register_feature")
                self._state = staged
            except _Rejected as exc:
                return self._refusal(
                    operation="register_feature",
                    code=exc.code,
                    message=exc.safe_message,
                    subject_id=subject,
                    before=before,
                )
            except Exception:
                return self._refusal(
                    operation="register_feature",
                    code=RefusalCode.PARTIAL_COMMIT,
                    message="transaction aborted before atomic publication",
                    subject_id=subject,
                    before=before,
                )
            return FeatureReceipt(
                feature_name=definition.feature_name,
                definition_version=definition.definition_version,
                definition_digest=definition.definition_digest,
                idempotent_retry=False,
                state_digest=self._state_digest(self._state),
            )

    def _validate_feature_inputs(
        self,
        definition: FeatureDefinition,
        bindings: Sequence[DatasetDigestBinding],
    ) -> tuple[HistoricalDatasetRecord, ...]:
        datasets: list[HistoricalDatasetRecord] = []
        for binding in bindings:
            dataset = self._state.datasets.get(binding.dataset_id)
            if dataset is None:
                raise _Rejected(
                    RefusalCode.SOURCE_RECORD_MISSING,
                    "feature input dataset is not registered",
                )
            if dataset.fingerprint() != binding.expected_record_digest:
                raise _Rejected(RefusalCode.DIGEST_MISMATCH, "feature input record mismatch")
            if dataset.payload_digest != binding.expected_payload_digest:
                raise _Rejected(RefusalCode.DIGEST_MISMATCH, "feature input payload mismatch")
            if dataset.namespace is not definition.namespace:
                raise _Rejected(
                    RefusalCode.FEATURE_INCOMPATIBLE,
                    "feature and dataset namespaces must match exactly",
                )
            matching = [
                requirement
                for requirement in definition.required_inputs
                if requirement.schema_name == dataset.schema_name
                and requirement.minimum_schema_version
                <= dataset.schema_version
                <= requirement.maximum_schema_version
            ]
            if not matching:
                raise _Rejected(
                    RefusalCode.FEATURE_INCOMPATIBLE,
                    "dataset schema/version is incompatible with the feature definition",
                )
            for requirement in matching:
                for minimum in requirement.minimum_support:
                    observed = dataset.support_value(minimum.name)
                    if observed is None or observed < minimum.value:
                        raise _Rejected(
                            RefusalCode.FEATURE_INCOMPATIBLE,
                            "dataset does not meet the feature's declared minimum support",
                        )
            datasets.append(dataset)
        for requirement in definition.required_inputs:
            if not any(
                dataset.schema_name == requirement.schema_name
                and requirement.minimum_schema_version
                <= dataset.schema_version
                <= requirement.maximum_schema_version
                for dataset in datasets
            ):
                raise _Rejected(
                    RefusalCode.FEATURE_INCOMPATIBLE,
                    "a required feature input schema is absent",
                )
        statuses = {dataset.standing.admission_status for dataset in datasets}
        if definition.evidence_restriction is EvidenceRestriction.ADMITTED_ONLY and statuses != {
            AdmissionStatus.ADMITTED
        }:
            raise _Rejected(
                RefusalCode.NON_ADMITTED_PROMOTION,
                "admitted feature namespace cannot consume non-admitted material",
            )
        if (
            definition.evidence_restriction is EvidenceRestriction.NON_ADMITTED_ONLY
            and statuses != {AdmissionStatus.NON_ADMITTED}
        ):
            raise _Rejected(
                RefusalCode.FEATURE_INCOMPATIBLE,
                "non-admitted feature requires only non-admitted inputs",
            )
        if (
            definition.evidence_restriction is EvidenceRestriction.ADMITTED_EXECUTION_DEVIATED_ONLY
            and (
                statuses != {AdmissionStatus.ADMITTED}
                or any(not dataset.standing.execution_deviation for dataset in datasets)
            )
        ):
            raise _Rejected(
                RefusalCode.FEATURE_INCOMPATIBLE,
                "execution-deviated feature requires admitted inputs retaining deviations",
            )
        return tuple(datasets)

    def materialise_snapshot(
        self,
        candidate: FeatureSnapshotCandidate,
    ) -> FeatureSnapshot | StoreRefusal:
        """Create one immutable feature snapshot or return a state-preserving refusal."""

        with self._lock:
            before = self._state_digest(self._state)
            request = candidate.request
            try:
                _screen_value(request.model_dump(mode="json"), screen_keys=False)
                observed_digest = hashlib.sha256(candidate.values_payload).hexdigest()
                if observed_digest != request.values_digest:
                    raise _Rejected(RefusalCode.DIGEST_MISMATCH, "feature values digest mismatch")
                parsed_values = _parse_aggregate_json(candidate.values_payload)
                if parsed_values.get("aggregates_only") is not True:
                    raise _Rejected(
                        RefusalCode.SCHEMA_UNSUPPORTED,
                        "feature values must declare aggregates_only=true",
                    )
                definition = self._state.features.get(
                    (request.feature_name, request.feature_version)
                )
                if definition is None:
                    raise _Rejected(
                        RefusalCode.SOURCE_RECORD_MISSING,
                        "feature definition is not registered",
                    )
                if definition.definition_digest != request.definition_digest:
                    raise _Rejected(
                        RefusalCode.DIGEST_MISMATCH,
                        "feature definition digest mismatch",
                    )
                if request.namespace is not definition.namespace:
                    raise _Rejected(
                        RefusalCode.FEATURE_INCOMPATIBLE,
                        "snapshot namespace conflicts with the feature definition",
                    )
                datasets = self._validate_feature_inputs(definition, request.dataset_bindings)
                standing = _weakest_standing([dataset.standing for dataset in datasets])
                snapshot_fields = _snapshot_identity_payload(
                    snapshot_id=request.snapshot_id,
                    feature_name=request.feature_name,
                    feature_version=request.feature_version,
                    definition_digest=request.definition_digest,
                    dataset_bindings=request.dataset_bindings,
                    values_digest=request.values_digest,
                    row_count=request.row_count,
                    coverage=request.coverage,
                    exclusions=request.exclusions,
                    created_at_utc=request.created_at_utc,
                    standing=standing,
                    namespace=request.namespace,
                )
                snapshot = FeatureSnapshot(
                    snapshot_id=request.snapshot_id,
                    feature_name=request.feature_name,
                    feature_version=request.feature_version,
                    definition_digest=request.definition_digest,
                    dataset_bindings=request.dataset_bindings,
                    values_digest=request.values_digest,
                    values_handle=f"sha256:{request.values_digest}",
                    row_count=request.row_count,
                    coverage=request.coverage,
                    exclusions=request.exclusions,
                    created_at_utc=request.created_at_utc,
                    standing=standing,
                    namespace=request.namespace,
                    snapshot_digest=_fingerprint(snapshot_fields),
                )
                existing = self._state.snapshots.get(request.snapshot_id)
                if existing is not None:
                    if existing.fingerprint() != snapshot.fingerprint():
                        raise _Rejected(
                            RefusalCode.SNAPSHOT_CONFLICT,
                            "snapshot id already binds different immutable content",
                        )
                    return existing
                staged = _StoreState(
                    datasets=dict(self._state.datasets),
                    payloads={
                        **self._state.payloads,
                        request.values_digest: candidate.values_payload,
                    },
                    features=dict(self._state.features),
                    snapshots={**self._state.snapshots, request.snapshot_id: snapshot},
                )
                if self._before_commit is not None:
                    self._before_commit("materialise_snapshot")
                self._state = staged
            except _Rejected as exc:
                return self._refusal(
                    operation="materialise_snapshot",
                    code=exc.code,
                    message=exc.safe_message,
                    subject_id=request.snapshot_id,
                    before=before,
                )
            except Exception:
                return self._refusal(
                    operation="materialise_snapshot",
                    code=RefusalCode.PARTIAL_COMMIT,
                    message="transaction aborted before atomic publication",
                    subject_id=request.snapshot_id,
                    before=before,
                )
            return snapshot

    def get_dataset(
        self,
        dataset_id: str,
        expected_digest: str,
    ) -> HistoricalDatasetRecord | StoreRefusal:
        """Return metadata only, pinned to an exact payload digest."""

        with self._lock:
            before = self._state_digest(self._state)
            record = self._state.datasets.get(dataset_id)
            if record is None:
                return self._refusal(
                    operation="get_dataset",
                    code=RefusalCode.SOURCE_RECORD_MISSING,
                    message="dataset is not registered",
                    subject_id=dataset_id,
                    before=before,
                )
            if record.payload_digest != expected_digest:
                return self._refusal(
                    operation="get_dataset",
                    code=RefusalCode.DIGEST_MISMATCH,
                    message="requested dataset digest does not match",
                    subject_id=dataset_id,
                    before=before,
                )
            return record

    def query_catalogue(self, query: CatalogueQuery) -> tuple[HistoricalDatasetRecord, ...]:
        """Run an allowlisted metadata query with explicit schema/version/namespace."""

        with self._lock:
            matches = [
                record
                for record in self._state.datasets.values()
                if record.schema_name == query.schema_name
                and query.minimum_schema_version
                <= record.schema_version
                <= query.maximum_schema_version
                and record.namespace is query.namespace
                and (query.payload_class is None or record.payload_class is query.payload_class)
                and (
                    query.evidence_role is None
                    or record.standing.evidence_role is query.evidence_role
                )
                and (
                    query.admission_status is None
                    or record.standing.admission_status is query.admission_status
                )
            ]
            return tuple(sorted(matches, key=lambda item: (item.dataset_id, item.payload_digest)))

    def provenance_walk(self, snapshot_id: str) -> ProvenanceWalk | StoreRefusal:
        """Walk a snapshot to every input definition, dataset and root source record."""

        with self._lock:
            before = self._state_digest(self._state)
            snapshot = self._state.snapshots.get(snapshot_id)
            if snapshot is None:
                return self._refusal(
                    operation="provenance_walk",
                    code=RefusalCode.SOURCE_RECORD_MISSING,
                    message="feature snapshot is not registered",
                    subject_id=snapshot_id,
                    before=before,
                )
            definition = self._state.features.get((snapshot.feature_name, snapshot.feature_version))
            if definition is None or definition.definition_digest != snapshot.definition_digest:
                return self._refusal(
                    operation="provenance_walk",
                    code=RefusalCode.DIGEST_MISMATCH,
                    message="snapshot feature definition no longer reconciles",
                    subject_id=snapshot_id,
                    before=before,
                )
            datasets: list[HistoricalDatasetRecord] = []
            roots: dict[str, AuthoritativeSourceRecord] = {}
            pending = [binding.dataset_id for binding in snapshot.dataset_bindings]
            seen: set[str] = set()
            while pending:
                dataset_id = pending.pop()
                if dataset_id in seen:
                    continue
                seen.add(dataset_id)
                dataset = self._state.datasets.get(dataset_id)
                if dataset is None:
                    return self._refusal(
                        operation="provenance_walk",
                        code=RefusalCode.SOURCE_RECORD_MISSING,
                        message="snapshot source dataset is missing",
                        subject_id=snapshot_id,
                        before=before,
                    )
                datasets.append(dataset)
                for binding in dataset.source_bindings:
                    if binding.source_kind is SourceKind.AUTHORITATIVE_RECORD:
                        source = self._authoritative_sources.get(binding.source_id)
                        if source is None:
                            return self._refusal(
                                operation="provenance_walk",
                                code=RefusalCode.SOURCE_RECORD_MISSING,
                                message="authoritative root source is missing",
                                subject_id=snapshot_id,
                                before=before,
                            )
                        roots[source.source_record_id] = source
                    else:
                        pending.append(binding.source_id)
            return ProvenanceWalk(
                snapshot=snapshot,
                feature_definition=definition,
                datasets=tuple(sorted(datasets, key=lambda item: item.dataset_id)),
                authoritative_sources=tuple(
                    sorted(roots.values(), key=lambda item: item.source_record_id)
                ),
            )

    def dry_run_migration(
        self,
        candidates: Sequence[DatasetRegistrationCandidate],
    ) -> MigrationDryRunReport:
        """Validate a migration on a cloned state without changing source or store bytes."""

        with self._lock:
            store_before = self._state_digest(self._state)
            payloads_before = tuple(hashlib.sha256(item.payload).hexdigest() for item in candidates)
            sources_before = tuple(
                source.fingerprint()
                for source in sorted(
                    self._authoritative_sources.values(),
                    key=lambda item: item.source_record_id,
                )
            )
            clone = InMemoryHistoricalStore(
                schemas=tuple(self._schemas.values()),
                authoritative_sources=tuple(self._authoritative_sources.values()),
                licence_allowlist=self._licence_allowlist,
            )
            clone._state = _StoreState(
                datasets=dict(self._state.datasets),
                payloads=dict(self._state.payloads),
                features=dict(self._state.features),
                snapshots=dict(self._state.snapshots),
            )
            findings: list[MigrationDryRunFinding] = []
            for candidate in candidates:
                result = clone.register_dataset(candidate)
                if isinstance(result, StoreRefusal):
                    findings.append(
                        MigrationDryRunFinding(
                            dataset_id=candidate.record.dataset_id,
                            status="would_refuse",
                            refusal_code=result.code,
                        )
                    )
                else:
                    findings.append(
                        MigrationDryRunFinding(
                            dataset_id=candidate.record.dataset_id,
                            status="would_reuse" if result.idempotent_retry else "would_register",
                        )
                    )
            payloads_after = tuple(hashlib.sha256(item.payload).hexdigest() for item in candidates)
            sources_after = tuple(
                source.fingerprint()
                for source in sorted(
                    self._authoritative_sources.values(),
                    key=lambda item: item.source_record_id,
                )
            )
            store_after = self._state_digest(self._state)
            if payloads_before != payloads_after or sources_before != sources_after:
                raise RuntimeError("migration dry run mutated source material")
            if store_before != store_after:
                raise RuntimeError("migration dry run mutated the live store")
            return MigrationDryRunReport(
                datasets_examined=len(candidates),
                would_register=sum(item.status == "would_register" for item in findings),
                would_reuse=sum(item.status == "would_reuse" for item in findings),
                would_refuse=sum(item.status == "would_refuse" for item in findings),
                findings=tuple(findings),
                source_payload_digests_before=payloads_before,
                source_payload_digests_after=payloads_after,
                store_state_digest_before=store_before,
                store_state_digest_after=store_after,
            )
