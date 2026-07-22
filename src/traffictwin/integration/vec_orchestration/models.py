"""Strict contracts for the one-click VEC execute-and-import orchestration.

This layer composes the accepted VEC-07 runner and the existing registry import
conventions. It defines no second evaluator, no new metric meaning, and no new
scientific claim: an imported execution stays structural evidence with
scientific admission explicitly unavailable, because the accepted VEC-09
admission binds the audited source run rather than any local execution.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.integration.vec_runner.models import (
    VecRunnerFileEvidence,
    VecRunRequest,
    VecRuntimeEvidence,
)

VEC_ORCHESTRATION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_ORCHESTRATION_METHOD_VERSION: Literal["vec-execute-and-import-1.0"] = (
    "vec-execute-and-import-1.0"
)
VEC_ORCHESTRATION_CAPABILITY_ID: Literal["VEC-10"] = "VEC-10"
SMOKE_RUN_ID = "vec-oneclick-smoke-two-step"
FULL_RUN_ID = "vec-oneclick-full-reproduction"
REVIEWED_WEEKEND_TRACE_FILE = "traces/trace_we_fullrsu.npz"
REVIEWED_WEEKEND_TRACE_SHA256 = "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be"
REVIEWED_WEEKEND_TRACE_STEPS = 32_400
SMOKE_MAX_STEPS = 2
SCIENTIFIC_ADMISSION_REASONS = (
    "vec09_admission_binds_audited_source_run_only",
    "local_execution_is_structural_evidence_not_metric_admission",
    "per_task_energy_absent",
    "eventual_physical_completion_absent",
    "action_is_not_transfer_proof",
)


class VecOrchestrationModel(BaseModel):
    """Strict finite base model for orchestration artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    def canonical_json(self) -> str:
        """Return deterministic canonical JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical JSON form."""

        return _sha256(self.canonical_json().encode())


class VecExecutionPreset(StrEnum):
    """Closed repository-defined execution presets; no free-form requests."""

    SMOKE_TWO_STEP = "smoke_two_step"
    FULL_REPRODUCTION = "full_reproduction"


class VecEvidenceGrade(StrEnum):
    """What a completed preset execution is allowed to claim."""

    STRUCTURAL_SMOKE_EXECUTION = "structural_smoke_execution"
    FULL_PROTOCOL_EXECUTION_UNVERIFIED_REPRODUCTION = (
        "full_protocol_execution_unverified_reproduction"
    )


class VecWorkflowStatus(StrEnum):
    """Terminal one-click workflow states; only completed_imported registers evidence."""

    COMPLETED_IMPORTED = "completed_imported"
    PREFLIGHT_REJECTED = "preflight_rejected"
    PREFLIGHT_UNAVAILABLE = "preflight_unavailable"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_TIMED_OUT = "execution_timed_out"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_REJECTED = "execution_rejected"
    IMPORT_REJECTED = "import_rejected"
    IMPORT_CONFLICT = "import_conflict"


class VecWorkflowStageName(StrEnum):
    """Ordered orchestration stages."""

    PREFLIGHT = "preflight"
    EXECUTION = "execution"
    VALIDATION = "validation"
    IMPORT = "import"


class VecWorkflowStageState(StrEnum):
    """Outcome of one orchestration stage."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPLETED = "completed"


class VecWorkflowStage(VecOrchestrationModel):
    """One deterministic stage outcome shown to the user."""

    stage: VecWorkflowStageName
    state: VecWorkflowStageState
    detail: str = Field(min_length=1, max_length=2_000)


class VecPresetWorkload(VecOrchestrationModel):
    """Factual request properties; never a runtime promise."""

    preset: VecExecutionPreset
    evaluator_steps: int = Field(ge=1)
    trace_file: str
    timeout_seconds_bound: int = Field(ge=1)
    foreground_only: Literal[True] = True
    background_execution: Literal[False] = False
    description: str = Field(min_length=1, max_length=1_000)


class VecWorkflowRequest(VecOrchestrationModel):
    """One complete, closed one-click request; paths are explicit and bounded."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-execute-and-import-1.0"] = VEC_ORCHESTRATION_METHOD_VERSION
    preset: VecExecutionPreset
    input_root: str = Field(min_length=1, max_length=1_000)
    vec_repo: str = Field(min_length=1, max_length=1_000)
    tos_data_repo: str = Field(min_length=1, max_length=1_000)
    output_dir: str = Field(min_length=1, max_length=1_000)
    registry_path: str = Field(min_length=1, max_length=1_000)
    confirm_full_run: bool = False

    @field_validator(
        "input_root",
        "vec_repo",
        "tos_data_repo",
        "output_dir",
        "registry_path",
    )
    @classmethod
    def validate_path_text(cls, value: str) -> str:
        if "\x00" in value or any(ord(char) < 32 for char in value):
            raise ValueError("paths must not contain control characters")
        return value

    @model_validator(mode="after")
    def validate_confirmation(self) -> VecWorkflowRequest:
        if self.preset is VecExecutionPreset.FULL_REPRODUCTION and not self.confirm_full_run:
            raise ValueError(
                "the full reproduction preset is a long foreground run and requires "
                "confirm_full_run=True"
            )
        return self


class VecExecutionImportRecord(VecOrchestrationModel):
    """Immutable, source-specific registry evidence for one completed execution.

    Semantic guards are literal: deadline success is never physical completion,
    a selected action is never a confirmed transfer, aggregate energy is never
    per-task energy, and smoke output is never a scientific finding.
    """

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-10"] = VEC_ORCHESTRATION_CAPABILITY_ID
    importer_version: Literal["vec-execute-and-import-1.0"] = VEC_ORCHESTRATION_METHOD_VERSION
    preset: VecExecutionPreset
    evidence_grade: VecEvidenceGrade
    request: VecRunRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    vec_env_commit: Literal["068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"] = (
        "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
    )
    tos_data_commit: Literal["f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"] = (
        "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"
    )
    runtime: VecRuntimeEvidence
    outputs: list[VecRunnerFileEvidence] = Field(min_length=1)
    started_at_utc: str
    finished_at_utc: str
    elapsed_seconds: float = Field(ge=0)
    imported_at_utc: str
    registry_run_id: str = Field(min_length=1, max_length=200)
    registry_bundle_id: str = Field(min_length=1, max_length=200)
    scientific_admission_status: Literal["unavailable"] = "unavailable"
    scientific_admission_reasons: list[str] = Field(min_length=1, max_length=16)
    publication_status: Literal["not_authorised_by_execution"] = "not_authorised_by_execution"
    deadline_success_is_physical_completion: Literal[False] = False
    action_selection_is_confirmed_transfer: Literal[False] = False
    aggregate_energy_is_per_task_energy: Literal[False] = False
    smoke_output_is_scientific_finding: Literal[False] = False
    limitations: list[str] = Field(min_length=1, max_length=16)

    @field_validator("scientific_admission_reasons", "limitations")
    @classmethod
    def validate_statements(cls, value: list[str]) -> list[str]:
        for item in value:
            if not 1 <= len(item) <= 1_000:
                raise ValueError("statements must be 1-1000 characters")
        return value

    @field_validator("outputs")
    @classmethod
    def sort_outputs(cls, value: list[VecRunnerFileEvidence]) -> list[VecRunnerFileEvidence]:
        return sorted(value, key=lambda item: item.path)

    @model_validator(mode="after")
    def validate_preset_semantics(self) -> VecExecutionImportRecord:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        expected_grade = {
            VecExecutionPreset.SMOKE_TWO_STEP: VecEvidenceGrade.STRUCTURAL_SMOKE_EXECUTION,
            VecExecutionPreset.FULL_REPRODUCTION: (
                VecEvidenceGrade.FULL_PROTOCOL_EXECUTION_UNVERIFIED_REPRODUCTION
            ),
        }[self.preset]
        if self.evidence_grade is not expected_grade:
            raise ValueError(
                f"preset {self.preset.value} requires evidence grade {expected_grade.value}"
            )
        required_reasons = set(SCIENTIFIC_ADMISSION_REASONS)
        if not required_reasons.issubset(self.scientific_admission_reasons):
            missing = sorted(required_reasons - set(self.scientific_admission_reasons))
            raise ValueError(
                "scientific admission reasons must retain the standing codes; "
                f"missing: {', '.join(missing)}"
            )
        return self

    def stable_fingerprint(self) -> str:
        """Fingerprint the import identity excluding the import wall-clock time."""

        payload = self.model_dump(mode="json")
        del payload["imported_at_utc"]
        return _sha256(_canonical_json(payload).encode())


class VecImportOutcome(VecOrchestrationModel):
    """Registry outcome for one import attempt."""

    created: bool
    idempotent: bool
    registry_run_id: str
    registry_bundle_id: str
    stable_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_reference: str = Field(min_length=1, max_length=300)

    @field_validator("registry_reference")
    @classmethod
    def validate_reference(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute():
            raise ValueError("registry reference must not expose an absolute path")
        return value

    @model_validator(mode="after")
    def validate_flags(self) -> VecImportOutcome:
        if self.created and self.idempotent:
            raise ValueError("an import is either newly created or idempotent, not both")
        return self


class VecWorkflowReceipt(VecOrchestrationModel):
    """Complete typed evidence for one one-click workflow invocation."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-10"] = VEC_ORCHESTRATION_CAPABILITY_ID
    method_version: Literal["vec-execute-and-import-1.0"] = VEC_ORCHESTRATION_METHOD_VERSION
    status: VecWorkflowStatus
    preset: VecExecutionPreset
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    stages: list[VecWorkflowStage] = Field(min_length=1)
    preflight_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    receipt_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    external_repositories_verified_unchanged: bool
    raw_inputs_verified_unchanged: bool
    import_outcome: VecImportOutcome | None = None
    import_record_stable_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    outputs: list[VecRunnerFileEvidence] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("findings")
    @classmethod
    def validate_findings(cls, value: list[str]) -> list[str]:
        for item in value:
            if not 1 <= len(item) <= 2_000:
                raise ValueError("findings must be 1-2000 characters")
        return value

    @model_validator(mode="after")
    def validate_terminal_state(self) -> VecWorkflowReceipt:
        imported = self.status is VecWorkflowStatus.COMPLETED_IMPORTED
        if imported:
            if self.import_outcome is None or self.import_record_stable_fingerprint is None:
                raise ValueError("completed_imported requires a registry import outcome")
            if self.receipt_fingerprint is None or self.output_fingerprint is None:
                raise ValueError("completed_imported requires execution evidence")
            if not (
                self.external_repositories_verified_unchanged and self.raw_inputs_verified_unchanged
            ):
                raise ValueError("completed_imported requires verified immutable sources")
        elif self.import_outcome is not None:
            raise ValueError("only completed_imported may carry a registry import outcome")
        return self


class VecOrchestrationContract(VecOrchestrationModel):
    """Machine-readable public boundary for the one-click workflow."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-10"] = VEC_ORCHESTRATION_CAPABILITY_ID
    method_version: Literal["vec-execute-and-import-1.0"] = VEC_ORCHESTRATION_METHOD_VERSION
    presets: list[VecPresetWorkload]
    operations: list[str]
    import_bindings: list[str]
    refusals: list[str]
    interpretation_limits: list[str]


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
