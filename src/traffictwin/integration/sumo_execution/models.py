"""Strict contracts for the controlled one-click SUMO execution workflow.

This is a bounded post-v0.6 extension over the accepted import-only SUMO
adapter (`ING-01`). It defines one closed repository-owned synthetic preset,
read-only preflight evidence, a typed execution receipt, and an immutable
import record. It is not a general-purpose SUMO launcher: no arbitrary
executable, flag, environment variable, script, URL, GUI, or Randy/VEC control
is representable, generic ``direct_launch`` stays false, and a synthetic run
is never Manchester traffic, Randy evidence, or real-world validation.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SUMO_EXECUTION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
SUMO_EXECUTION_METHOD_VERSION: Literal["sumo-execute-and-import-1.0"] = (
    "sumo-execute-and-import-1.0"
)
SUMO_EXECUTION_CAPABILITY: Literal["controlled_sumo_execution"] = "controlled_sumo_execution"
SUPPORTED_SUMO_VERSION_PREFIX: Literal["1.27."] = "1.27."
SCENARIO_DIRECTORY: Literal["scenario_synthetic_square"] = "scenario_synthetic_square"
SCENARIO_CONFIG_FILE: Literal["square.sumocfg"] = "square.sumocfg"
SCENARIO_NET_FILE = "square.net.xml"
SCENARIO_ROUTE_FILE = "square.rou.xml"
EXPECTED_OUTPUT_FILES = ("summary.xml", "tripinfo.xml")
RESULT_MANIFEST_FILE = "sumo-source.yaml"
RESULT_RECEIPT_FILE = "execution_receipt.json"
RESULT_IMPORT_RECORD_FILE = "execution_import_record.json"
IMPORT_BUNDLE_PREFIX = "sumo-exec-"
SYNTHETIC_LIMITATIONS = (
    "Synthetic TrafficTwin-authored smoke scenario: not Manchester traffic, not Randy/VEC "
    "evidence, and not real-world validation.",
    "SUMO summary occupancy is never mapped to canonical traffic counts; no FCD, task, RSU, "
    "offloading, energy, or VEC quantity is invented.",
    "A completed run proves controlled local software execution only; scenario realism and "
    "scientific claims are out of scope.",
)


class SumoExecutionModel(BaseModel):
    """Strict finite base model for controlled-execution artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    def canonical_json(self) -> str:
        """Return deterministic canonical JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical JSON form."""

        return _sha256(self.canonical_json().encode())


class SumoExecutionPreset(StrEnum):
    """Closed repository-owned execution presets; no free-form scenarios."""

    SYNTHETIC_SQUARE_SMOKE = "synthetic_square_smoke"


class SumoScenarioInput(SumoExecutionModel):
    """One admitted scenario input with its pinned identity."""

    name: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or len(path.parts) != 1 or value in {".", ".."}:
            raise ValueError("scenario inputs are single safe file names")
        return value


class SumoRunPreset(SumoExecutionModel):
    """Complete immutable definition of one closed preset."""

    preset: SumoExecutionPreset
    scenario_directory: Literal["scenario_synthetic_square"] = SCENARIO_DIRECTORY
    config_file: Literal["square.sumocfg"] = SCENARIO_CONFIG_FILE
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inputs: list[SumoScenarioInput] = Field(min_length=1, max_length=16)
    random_seed: int = Field(ge=0, le=2_147_483_647)
    begin_s: int = Field(ge=0)
    end_s: int = Field(gt=0)
    vehicle_count: int = Field(ge=1, le=1_000)
    supported_sumo_version_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX
    expected_outputs: list[str] = Field(min_length=1, max_length=8)
    synthetic: Literal[True] = True
    manchester_traffic: Literal[False] = False
    randy_vec_evidence: Literal[False] = False
    real_world_validation: Literal[False] = False
    provenance: str = Field(min_length=10, max_length=1_000)
    licence_statement: str = Field(min_length=10, max_length=1_000)
    description: str = Field(min_length=10, max_length=1_000)

    @model_validator(mode="after")
    def validate_bounds(self) -> SumoRunPreset:
        if self.end_s <= self.begin_s:
            raise ValueError("end_s must be after begin_s")
        names = [item.name for item in self.inputs]
        if len(set(names)) != len(names):
            raise ValueError("scenario inputs must not repeat a name")
        if self.config_file not in names:
            raise ValueError("the configuration file must be part of the admitted inventory")
        return self


class SumoRuntimeStatus(SumoExecutionModel):
    """Discovered SUMO runtime readiness; portable and path-free."""

    available: bool
    executable_name: str | None = Field(default=None, min_length=1, max_length=100)
    executable_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    version: str | None = Field(default=None, min_length=1, max_length=50)
    supported: bool
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_support(self) -> SumoRuntimeStatus:
        if self.supported and not self.available:
            raise ValueError("a supported runtime must be available")
        if self.supported and (self.version is None or self.executable_sha256 is None):
            raise ValueError("a supported runtime requires version and executable identity")
        return self


class SumoRunRequest(SumoExecutionModel):
    """One resolved, bounded execution request for a closed preset."""

    schema_version: Literal["1.0"] = SUMO_EXECUTION_SCHEMA_VERSION
    method_version: Literal["sumo-execute-and-import-1.0"] = SUMO_EXECUTION_METHOD_VERSION
    preset: SumoExecutionPreset
    config_file: str = Field(min_length=1, max_length=200)
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inputs: list[SumoScenarioInput] = Field(min_length=1, max_length=16)
    sumo_executable_name: str = Field(min_length=1, max_length=100)
    sumo_executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sumo_version: str = Field(min_length=1, max_length=50)
    random_seed: int = Field(ge=0, le=2_147_483_647)
    begin_s: int = Field(ge=0)
    end_s: int = Field(gt=0)
    timeout_seconds: int = Field(ge=1, le=600)

    @model_validator(mode="after")
    def validate_request(self) -> SumoRunRequest:
        if not self.sumo_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
            raise ValueError(
                f"only SUMO {SUPPORTED_SUMO_VERSION_PREFIX}x is supported; got {self.sumo_version}"
            )
        if self.end_s <= self.begin_s:
            raise ValueError("end_s must be after begin_s")
        return self


class SumoWorkflowRequest(SumoExecutionModel):
    """User-facing one-click request; paths are explicit and bounded."""

    schema_version: Literal["1.0"] = SUMO_EXECUTION_SCHEMA_VERSION
    method_version: Literal["sumo-execute-and-import-1.0"] = SUMO_EXECUTION_METHOD_VERSION
    preset: SumoExecutionPreset
    output_dir: str = Field(min_length=1, max_length=1_000)
    registry_path: str = Field(min_length=1, max_length=1_000)
    timeout_seconds: int = Field(default=120, ge=1, le=600)

    @field_validator("output_dir", "registry_path")
    @classmethod
    def validate_path_text(cls, value: str) -> str:
        if "\x00" in value or any(ord(char) < 32 for char in value):
            raise ValueError("paths must not contain control characters")
        return value


class SumoFinding(SumoExecutionModel):
    """One deterministic preflight or workflow finding."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$")
    severity: Literal["info", "error"]
    message: str = Field(min_length=1, max_length=1_000)


class SumoPreflightStatus(StrEnum):
    """Read-only preflight outcome."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class SumoPreflightReport(SumoExecutionModel):
    """Complete read-only admission decision for one request."""

    schema_version: Literal["1.0"] = SUMO_EXECUTION_SCHEMA_VERSION
    method_version: Literal["sumo-execute-and-import-1.0"] = SUMO_EXECUTION_METHOD_VERSION
    status: SumoPreflightStatus
    preset: SumoExecutionPreset
    runtime: SumoRuntimeStatus
    request: SumoRunRequest | None
    request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    findings: list[SumoFinding]
    read_only: Literal[True] = True
    mutations_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_outcome(self) -> SumoPreflightReport:
        has_error = any(item.severity == "error" for item in self.findings)
        if self.status is SumoPreflightStatus.ACCEPTED:
            if has_error:
                raise ValueError("accepted preflight cannot contain errors")
            if self.request is None or self.request_fingerprint is None:
                raise ValueError("accepted preflight requires a resolved request")
            if self.request_fingerprint != self.request.fingerprint():
                raise ValueError("request fingerprint mismatch")
        return self


class SumoFileEvidence(SumoExecutionModel):
    """Portable identity for one input, log, or output file."""

    path: str = Field(min_length=1, max_length=300)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("evidence paths must be safe and relative")
        return path.as_posix()


class SumoTerminalStatus(StrEnum):
    """Terminal runner states; only completed results are published."""

    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class SumoExecutionReceipt(SumoExecutionModel):
    """Typed terminal evidence for one controlled SUMO invocation."""

    schema_version: Literal["1.0"] = SUMO_EXECUTION_SCHEMA_VERSION
    method_version: Literal["sumo-execute-and-import-1.0"] = SUMO_EXECUTION_METHOD_VERSION
    status: SumoTerminalStatus
    request: SumoRunRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    argv: list[str] = Field(min_length=2, max_length=32)
    working_directory: Literal["{PRIVATE_WORKSPACE}"] = "{PRIVATE_WORKSPACE}"
    started_at_utc: str
    finished_at_utc: str
    elapsed_seconds: float = Field(ge=0)
    exit_code: int | None
    timed_out: bool
    cancellation_requested: bool
    inputs_before: list[SumoFileEvidence]
    inputs_after: list[SumoFileEvidence]
    stdout_excerpt: str = Field(max_length=64_000)
    stderr_excerpt: str = Field(max_length=64_000)
    outputs: list[SumoFileEvidence]
    output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    inputs_modified: bool
    published: bool
    limitations: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_terminal_state(self) -> SumoExecutionReceipt:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        if self.argv and PurePosixPath(self.argv[0]).name != self.argv[0]:
            raise ValueError("receipt argv must redact the executable to its base name")
        if self.status is SumoTerminalStatus.COMPLETED:
            if self.exit_code != 0 or not self.published or not self.outputs:
                raise ValueError("completed receipt requires successful published outputs")
            if self.inputs_modified:
                raise ValueError("completed receipt requires verified immutable inputs")
            if self.output_fingerprint != sumo_output_fingerprint(self.outputs):
                raise ValueError("output fingerprint mismatch")
            if self.inputs_before != self.inputs_after:
                raise ValueError("completed receipt requires byte-identical inputs before/after")
        elif self.published or self.outputs or self.output_fingerprint is not None:
            raise ValueError("unsuccessful terminal states cannot publish outputs")
        if self.timed_out != (self.status is SumoTerminalStatus.TIMED_OUT):
            raise ValueError("timeout flag must match terminal status")
        if self.cancellation_requested != (self.status is SumoTerminalStatus.CANCELLED):
            raise ValueError("cancellation flag must match terminal status")
        return self


class SumoWorkflowStatus(StrEnum):
    """Terminal one-click states; only completed_imported registers evidence."""

    COMPLETED_IMPORTED = "completed_imported"
    PREFLIGHT_REJECTED = "preflight_rejected"
    PREFLIGHT_UNAVAILABLE = "preflight_unavailable"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_TIMED_OUT = "execution_timed_out"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_REJECTED = "execution_rejected"
    VALIDATION_REJECTED = "validation_rejected"
    IMPORT_REJECTED = "import_rejected"
    IMPORT_CONFLICT = "import_conflict"


class SumoWorkflowStageName(StrEnum):
    """Ordered orchestration stages."""

    PREFLIGHT = "preflight"
    EXECUTION = "execution"
    VALIDATION = "validation"
    IMPORT = "import"


class SumoWorkflowStageState(StrEnum):
    """Outcome of one orchestration stage."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPLETED = "completed"


class SumoWorkflowStage(SumoExecutionModel):
    """One deterministic stage outcome shown to the user."""

    stage: SumoWorkflowStageName
    state: SumoWorkflowStageState
    detail: str = Field(min_length=1, max_length=2_000)


class SumoImportOutcome(SumoExecutionModel):
    """Registry outcome for one import attempt through the existing adapter."""

    created: bool
    idempotent: bool
    bundle_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    adapter_status: str = Field(min_length=1, max_length=100)
    metrics_stored: bool
    registry_reference: str = Field(min_length=1, max_length=300)

    @field_validator("registry_reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        if PurePosixPath(value).is_absolute():
            raise ValueError("registry reference must not expose an absolute path")
        return value

    @model_validator(mode="after")
    def validate_flags(self) -> SumoImportOutcome:
        if self.created and self.idempotent:
            raise ValueError("an import is either newly created or idempotent, not both")
        return self


class SumoExecutionImportRecord(SumoExecutionModel):
    """Immutable typed evidence binding one execution to its accepted import."""

    schema_version: Literal["1.0"] = SUMO_EXECUTION_SCHEMA_VERSION
    importer_version: Literal["sumo-execute-and-import-1.0"] = SUMO_EXECUTION_METHOD_VERSION
    capability: Literal["controlled_sumo_execution"] = SUMO_EXECUTION_CAPABILITY
    preset: SumoExecutionPreset
    request: SumoRunRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sumo_version: str = Field(min_length=1, max_length=50)
    validation_bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    imported_at_utc: str
    synthetic: Literal[True] = True
    manchester_traffic: Literal[False] = False
    randy_vec_evidence: Literal[False] = False
    real_world_validation: Literal[False] = False
    limitations: list[str] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_identities(self) -> SumoExecutionImportRecord:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        if not self.bundle_id.startswith(IMPORT_BUNDLE_PREFIX):
            raise ValueError(f"bundle_id must use the {IMPORT_BUNDLE_PREFIX} identity prefix")
        return self

    def stable_fingerprint(self) -> str:
        """Fingerprint the import identity excluding wall-clock-varying fields."""

        payload = self.model_dump(mode="json")
        del payload["imported_at_utc"]
        del payload["validation_report_sha256"]
        return _sha256(_canonical_json(payload).encode())


class SumoWorkflowReceipt(SumoExecutionModel):
    """Complete typed evidence for one one-click workflow invocation."""

    schema_version: Literal["1.0"] = SUMO_EXECUTION_SCHEMA_VERSION
    method_version: Literal["sumo-execute-and-import-1.0"] = SUMO_EXECUTION_METHOD_VERSION
    status: SumoWorkflowStatus
    preset: SumoExecutionPreset
    stages: list[SumoWorkflowStage] = Field(min_length=1)
    runtime: SumoRuntimeStatus
    request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    preflight_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    receipt_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    inputs_verified_unchanged: bool
    import_outcome: SumoImportOutcome | None = None
    import_record_stable_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    outputs: list[SumoFileEvidence] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("findings")
    @classmethod
    def validate_findings(cls, value: list[str]) -> list[str]:
        for item in value:
            if not 1 <= len(item) <= 2_000:
                raise ValueError("findings must be 1-2000 characters")
        return value

    @model_validator(mode="after")
    def validate_terminal_state(self) -> SumoWorkflowReceipt:
        imported = self.status is SumoWorkflowStatus.COMPLETED_IMPORTED
        if imported:
            if self.import_outcome is None or self.import_record_stable_fingerprint is None:
                raise ValueError("completed_imported requires a registry import outcome")
            if self.receipt_fingerprint is None or self.output_fingerprint is None:
                raise ValueError("completed_imported requires execution evidence")
            if not self.inputs_verified_unchanged:
                raise ValueError("completed_imported requires verified immutable inputs")
        elif self.import_outcome is not None:
            raise ValueError("only completed_imported may carry a registry import outcome")
        return self


class SumoImportedExecutionSummary(SumoExecutionModel):
    """Registry-backed summary of one imported controlled execution."""

    bundle_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    imported_at: str = Field(min_length=1, max_length=64)
    source_reference: str = Field(min_length=1, max_length=1_000)
    scenario_id: str = Field(min_length=1, max_length=200)
    sumo_version: str = Field(min_length=1, max_length=50)
    synthetic: bool


class SumoRunnerContract(SumoExecutionModel):
    """Machine-readable public boundary for the controlled SUMO workflow."""

    schema_version: Literal["1.0"] = SUMO_EXECUTION_SCHEMA_VERSION
    method_version: Literal["sumo-execute-and-import-1.0"] = SUMO_EXECUTION_METHOD_VERSION
    capability: Literal["controlled_sumo_execution"] = SUMO_EXECUTION_CAPABILITY
    capability_state: Literal["conditional_on_request_specific_preflight"] = (
        "conditional_on_request_specific_preflight"
    )
    generic_direct_launch: Literal[False] = False
    presets: list[SumoRunPreset] = Field(min_length=1)
    supported_sumo_version_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX
    operations: list[str]
    allowed_arguments: list[str]
    refusals: list[str]
    security_controls: list[str]
    interpretation_limits: list[str]


def sumo_output_fingerprint(outputs: list[SumoFileEvidence]) -> str:
    """Fingerprint a sorted portable output inventory."""

    payload = [
        item.model_dump(mode="json") for item in sorted(outputs, key=lambda evidence: evidence.path)
    ]
    return _sha256(_canonical_json(payload).encode())


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
