"""Typed models for Local Real-Workspace Activation Wizard.

All models are strict (extra="forbid"), deterministic canonical serialization,
stable SHA-256 fingerprint where identity matters, no path or wall-clock
contamination in semantic identity, explicit unavailable/refused states.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACTIVATION_METHOD_VERSION: Literal["workspace-activation-1.0"] = "workspace-activation-1.0"
_MAX_PATH_LENGTH = 4096
_MAX_WORKERS = 8
_MAX_FINDINGS = 64


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_json(value: object) -> str:
    return _digest_bytes(_canonical_json(value).encode("utf-8"))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ProviderKind(StrEnum):
    BODS = "bods"
    NATIONAL_HIGHWAYS = "national_highways"


class ProviderStatus(StrEnum):
    READY = "ready"
    DISABLED = "disabled"
    MISSING_CONFIGURATION = "missing_configuration"
    MISSING_CREDENTIAL = "missing_credential"
    UNAVAILABLE = "unavailable"


class ActionKind(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    CREATE_FILE = "create_file"
    INITIALIZE_DATABASE = "initialize_database"
    WRITE_MARKER = "write_marker"
    WRITE_RECEIPT = "write_receipt"
    CONFIGURE_PROVIDER = "configure_provider"
    START_WORKER = "start_worker"
    BACKUP = "backup"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CredentialPresence(StrictModel):
    """Credential presence only — never contains secret values."""

    name: str = Field(min_length=1, max_length=128, description="Credential logical name")
    env_var: str = Field(min_length=1, max_length=128, description="Environment variable name")
    present: bool = Field(description="True if credential is present (value never stored)")
    source: Literal["environment", "unavailable"] = Field(description="Where presence was checked")

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _digest_json(self.model_dump(mode="json"))


class ProviderReadiness(StrictModel):
    """Provider readiness without network calls."""

    provider: ProviderKind = Field(description="Provider kind")
    configured: bool = Field(description="Configuration file/env presence")
    credential_present: bool = Field(description="Credential present (no value)")
    enabled: bool = Field(description="Requested enabled state")
    status: ProviderStatus = Field(description="Computed readiness status")
    detail: str = Field(max_length=500, description="Human detail without secrets")

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _digest_json(self.model_dump(mode="json"))


class RetentionPolicy(StrictModel):
    """Retention/privacy configuration."""

    retention_days: int = Field(ge=1, le=3650, description="Retention window in days")
    anonymize: bool = Field(description="Whether PII is anonymized")
    allow_export: bool = Field(description="Whether raw export is allowed")
    policy_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    max_storage_mb: int | None = Field(default=None, ge=1, le=1_000_000)

    @field_validator("policy_version")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+$", v):
            raise ValueError("policy_version must be X.Y")
        return v

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _digest_json(self.model_dump(mode="json"))


class ActivationFinding(StrictModel):
    """One preflight finding."""

    code: str = Field(pattern=r"^[A-Z_]{3,64}$", description="Machine code")
    severity: FindingSeverity = Field(description="Severity")
    message: str = Field(min_length=1, max_length=500)
    category: str = Field(min_length=1, max_length=64)

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))


class WorkspaceActivationRequest(StrictModel):
    """User request for workspace activation — bounded, no secrets."""

    destination_path: str = Field(min_length=1, max_length=_MAX_PATH_LENGTH)
    bods_enabled: bool = Field(default=False)
    national_highways_enabled: bool = Field(default=False)
    retention_policy: RetentionPolicy = Field(
        default_factory=lambda: RetentionPolicy(
            retention_days=30, anonymize=True, allow_export=False
        )
    )
    backup_destination: str | None = Field(default=None, max_length=_MAX_PATH_LENGTH)
    start_workers: bool = Field(default=False)
    allowlisted_workers: list[str] = Field(default_factory=list, max_length=_MAX_WORKERS)
    package_version: str | None = Field(default=None, max_length=64)

    @field_validator("destination_path", "backup_destination")
    @classmethod
    def _validate_path_string(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("path must be non-empty")
        if "\x00" in v:
            raise ValueError("path contains null byte")
        return v.strip()

    @field_validator("allowlisted_workers")
    @classmethod
    def _validate_workers(cls, v: list[str]) -> list[str]:
        if len(v) > _MAX_WORKERS:
            raise ValueError(f"too many workers: {len(v)} > {_MAX_WORKERS}")
        for item in v:
            if not item or len(item) > 64:
                raise ValueError("worker name must be 1..64 chars")
            if not re.match(r"^[a-z0-9][a-z0-9._-]*$", item):
                raise ValueError(f"invalid worker name: {item!r}")
        if len(set(v)) != len(v):
            raise ValueError("duplicate worker names")
        return sorted(v)

    @field_validator("package_version")
    @classmethod
    def _validate_version_opt(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[0-9A-Za-z._-]+$", v):
            raise ValueError("invalid package_version")
        return v

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _digest_json(self.model_dump(mode="json"))

    def to_csv_row(self) -> dict[str, str]:
        return {
            "destination_path": self.destination_path,
            "bods_enabled": str(self.bods_enabled),
            "national_highways_enabled": str(self.national_highways_enabled),
            "retention_days": str(self.retention_policy.retention_days),
            "backup_destination": self.backup_destination or "",
            "start_workers": str(self.start_workers),
            "allowlisted_workers": ",".join(self.allowlisted_workers),
        }


class WorkspaceActivationPreflight(StrictModel):
    """Result of dry-run preflight checks — no secrets, no network."""

    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    destination_path: str
    is_managed: bool
    is_empty: bool
    path_valid: bool
    disk_available_bytes: int | None = Field(default=None, ge=0)
    disk_required_bytes: int = Field(ge=0)
    findings: list[ActivationFinding] = Field(max_length=_MAX_FINDINGS)
    credential_presence: list[CredentialPresence]
    provider_readiness: list[ProviderReadiness]
    retention_policy: RetentionPolicy
    aggregate_store_ready: bool
    backup_ready: bool
    worker_readiness: list[ActivationFinding]
    ready_to_plan: bool
    version_ok: bool

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _digest_json(self.model_dump(mode="json"))

    def to_csv_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for f in self.findings:
            rows.append(
                {
                    "code": f.code,
                    "severity": f.severity.value,
                    "category": f.category,
                    "message": f.message,
                }
            )
        return rows


class WorkspaceActivationAction(StrictModel):
    """One deterministic action in the activation plan."""

    kind: ActionKind
    target: str = Field(min_length=1, max_length=1024)
    detail: str = Field(max_length=1024)
    required: bool = Field(default=True)

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))


class WorkspaceActivationPlan(StrictModel):
    """Deterministic activation plan with exact confirmation digest.

    The authoritative identity is `confirmation_digest`, which is the SHA-256
    of the canonical semantic payload (all fields except `created_at` and
    `confirmation_digest` itself). `fingerprint()` and `expected_digest()` are
    aliases for the same value and exist for API compatibility; they are not
    independent integrity layers.
    """

    plan_version: str = Field(
        default=_ACTIVATION_METHOD_VERSION, pattern=r"^workspace-activation-\d+\.\d+$"
    )
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    destination_path: str
    directories_to_create: list[str]
    files_to_create: list[str]
    database_initialization: list[str]
    provider_configurations: list[ProviderReadiness]
    retention_settings: RetentionPolicy
    worker_start_options: list[str]
    backup_plan: str = Field(max_length=2000)
    rollback_plan: str = Field(max_length=2000)
    actions: list[WorkspaceActivationAction]
    confirmation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str = Field(
        description="ISO timestamp, excluded from semantic identity but present for audit"
    )

    @model_validator(mode="after")
    def _validate_sorted(self) -> WorkspaceActivationPlan:
        if self.directories_to_create != sorted(self.directories_to_create):
            raise ValueError("directories_to_create must be sorted")
        if self.files_to_create != sorted(self.files_to_create):
            raise ValueError("files_to_create must be sorted")
        if self.database_initialization != sorted(self.database_initialization):
            raise ValueError("database_initialization must be sorted")
        if self.worker_start_options != sorted(self.worker_start_options):
            raise ValueError("worker_start_options must be sorted")
        return self

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Canonical plan fingerprint (alias for confirmation_digest's preimage)."""
        payload = self.model_dump(mode="json")
        payload.pop("created_at", None)
        payload.pop("confirmation_digest", None)
        return _digest_json(payload)

    def semantic_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("created_at", None)
        payload.pop("confirmation_digest", None)
        return payload

    def expected_digest(self) -> str:
        """Alias for fingerprint() — same semantic identity, kept for compatibility."""
        return self.fingerprint()


class WorkspaceActivationConfirmation(StrictModel):
    """Caller-supplied confirmation — must match plan's exact digest.

    The load-bearing gate through UI/CLI is `confirmation_digest`.
    `request_fingerprint` is defense-in-depth for direct service callers
    who can construct typed confirmations; UI/CLI derive it from the same
    request, so a mismatch via those surfaces is not independently user-
    controlled, but direct callers can still be tested for stale requests.
    """

    confirmation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))


class WorkspaceActivationReceipt(StrictModel):
    """Receipt for successful activation.

    `plan_fingerprint` is the authoritative plan identity and equals the
    `confirmation_digest` of the plan that authorized this activation.
    """

    receipt_version: str = Field(default=_ACTIVATION_METHOD_VERSION)
    destination_path: str
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    activated_at: str
    directories_created: list[str]
    files_created: list[str]
    providers_enabled: list[str]
    retention_policy: RetentionPolicy
    workers_started: list[str]
    backup_location: str | None
    marker_path: str
    receipt_path: str
    status: Literal["activated", "already_active"] = Field(default="activated")

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("activated_at", None)
        return _digest_json(payload)

    def to_csv_row(self) -> dict[str, str]:
        return {
            "destination_path": self.destination_path,
            "request_fingerprint": self.request_fingerprint,
            "confirmation_digest": self.confirmation_digest,
            "status": self.status,
            "marker_path": self.marker_path,
        }


class WorkspaceActivationStatus(StrictModel):
    """Current status of a workspace path."""

    destination_path: str
    exists: bool
    is_managed: bool
    is_active: bool
    receipt: WorkspaceActivationReceipt | None = None
    marker_present: bool
    findings: list[ActivationFinding]
    providers: list[ProviderReadiness]

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))


class WorkspaceDeactivationReceipt(StrictModel):
    """Receipt for deactivation — never deletes raw data automatically.

    Policy: verify managed, refuse unmanaged, stop only activation-managed
    workers (recorded, not launched in V1), remove/marker only via
    confirmation, emit receipt, preserve evidence/DB/config/aggregate data.
    Workers are recorded in V1 and not actually launched, so deactivation
    records which would be stopped.
    """

    receipt_version: str = Field(default=_ACTIVATION_METHOD_VERSION)
    destination_path: str
    request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    deactivated_at: str
    marker_removed: bool
    workers_stopped: list[str]
    preserved_paths: list[str]
    status: Literal["deactivated", "not_active", "refused"] = Field(default="deactivated")

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("deactivated_at", None)
        return _digest_json(payload)
