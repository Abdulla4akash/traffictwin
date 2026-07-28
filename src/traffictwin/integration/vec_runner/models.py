"""Strict portable contracts for the allowlisted VEC-07 evaluator runner."""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VEC_RUNNER_SCHEMA_VERSION = "1.0"
VEC_RUNNER_METHOD_VERSION = "vec-evaluator-runner-1.0"
VEC_RUNNER_CAPABILITY_ID = "VEC-07"
PINNED_VEC_ENV_COMMIT = "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
PINNED_TOS_DATA_COMMIT = "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"

PINNED_EVALUATOR_FILES = {
    "eval/eval_sumo_stage1_mc.py": (
        "52490949e9d35cfaed2f9ba03ac92b08b475de503715a1967bc74950b689bf7c"
    ),
    "jaxmarl/env/vec_jax.py": ("4eed6b61f157b9a1ba203d0095acdecb0741f2da8d7fc4f411b6ee16a0bdd4f9"),
}
PINNED_ACTORS = {
    "baseline_model_c_17": (
        "checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz",
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208",
    ),
    "ukfleettrain_mappo_model_c_17": (
        "checkpoints/mappo_modelc_17dim_ukfleet2030__envs128__lr3e-3__seed100_actor_params.npz",
        "b3eca1685245c59d1a3e86bd11ede887300bda1b00ba211a1913e467ad3f5183",
    ),
}
PINNED_REVIEWED_TRACES = {
    "a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be": (
        "traces/trace_we_fullrsu.npz"
    ),
    # Gate-A-audited incident trace, admitted by ADR-062 after the identity
    # snapshot was measured to reconcile at the audited tos-data commit.
    "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056": (
        "traces/trace_inc_fullrsu.npz"
    ),
    # Gate-A-audited event-night trace, admitted by ADR-065 after the identity
    # snapshot was measured to reconcile at the audited tos-data commit.
    "70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208": (
        "traces/trace_ev_fullrsu.npz"
    ),
    # Gate-A-audited weekday peak traces, admitted by ADR-066 after both identity
    # snapshots were measured to reconcile at the audited tos-data commit.
    "5e36a7cb8b49afa9929574c9627216b7479a28ee0cbd83cc81ff852e647fd7ee": (
        "traces/trace_wd_am_fullrsu.npz"
    ),
    "848ba3cf278515f6a628bfb575892373454fae60ea6edf717da3b7683051ba9f": (
        "traces/trace_wd_pm_fullrsu.npz"
    ),
}

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")


class VecRunnerModel(BaseModel):
    """Strict finite base model for VEC-07 artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class VecFleet(StrEnum):
    """Closed fleet presets implemented by the pinned evaluator."""

    SYNTHETIC = "synthetic"
    UK_2030 = "uk2030"
    DE_2030 = "de2030"
    ID_2030 = "id2030"
    UK = "uk"
    DE = "de"
    ID = "id"


class VecTerminalStatus(StrEnum):
    """Terminal runner states; only completed results are published."""

    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class VecRunnerPreflightStatus(StrEnum):
    """Read-only VEC-07 preflight outcome."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class VecRunnerSeverity(StrEnum):
    """Closed deterministic finding severity vocabulary."""

    INFO = "info"
    ERROR = "error"


class VecRunRequest(VecRunnerModel):
    """One bounded request for the exact audited Model-C evaluator."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-07"] = "VEC-07"
    run_id: str
    trace_file: str
    trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preprocessing_receipt_file: str | None = None
    preprocessing_receipt_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    actor_id: Literal[
        "baseline_model_c_17",
        "ukfleettrain_mappo_model_c_17",
    ]
    evaluator_seed: int = Field(default=0, ge=0, le=2_147_483_647)
    fleet: VecFleet = VecFleet.UK_2030
    fleet_seed: int = Field(default=0, ge=0, le=2_147_483_647)
    rsu_capacity_per_vehicle: float = Field(default=2.5, gt=0.0, le=1_000.0)
    max_steps: int = Field(default=2, ge=1, le=100_000)
    timeout_seconds: int = Field(default=300, ge=1, le=7_200)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        if not _LABEL_RE.fullmatch(value):
            raise ValueError("run_id must use 1-96 ASCII letters, numbers, '.', '_' or '-'")
        return value

    @field_validator("trace_file", "preprocessing_receipt_file")
    @classmethod
    def validate_relative_file(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) > 256 or "\\" in value:
            raise ValueError("input files must be bounded POSIX relative paths")
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("input files must be safe relative paths")
        return path.as_posix()

    @model_validator(mode="after")
    def validate_provenance_pair(self) -> VecRunRequest:
        supplied = self.preprocessing_receipt_file is not None
        hashed = self.preprocessing_receipt_sha256 is not None
        if supplied != hashed:
            raise ValueError("preprocessing receipt path and SHA-256 must be supplied together")
        if not self.trace_file.lower().endswith(".npz"):
            raise ValueError("trace_file must name an NPZ artifact")
        if not math.isfinite(self.rsu_capacity_per_vehicle):
            raise ValueError("rsu capacity must be finite")
        return self

    def canonical_json(self) -> str:
        """Return deterministic path-safe request JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Fingerprint every declared execution control and input identity."""

        return _sha256(self.canonical_json().encode())


class VecRunnerFinding(VecRunnerModel):
    """One deterministic preflight or terminal finding."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$")
    severity: VecRunnerSeverity
    message: str = Field(min_length=1, max_length=1_000)
    artifact: str | None = None


class VecRunnerFileEvidence(VecRunnerModel):
    """Portable identity for one source, input, log, or output file."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str
    read_only: bool

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("evidence paths must be safe and relative")
        return path.as_posix()


class VecRepositoryEvidence(VecRunnerModel):
    """Before/after identity for one audited external repository."""

    repository: Literal["vec_env", "tos-data"]
    audited_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    worktree_head_before: str = Field(pattern=r"^[0-9a-f]{40}$")
    worktree_head_after: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    origin_main_before: str = Field(pattern=r"^[0-9a-f]{40}$")
    origin_main_after: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    clean_before: bool
    clean_after: bool | None = None
    source_files: list[VecRunnerFileEvidence]


class VecRuntimeEvidence(VecRunnerModel):
    """Relevant controlled runtime and hardware evidence."""

    python: str
    numpy: str
    jax: str
    jaxlib: str
    jax_backend: str
    jax_device_count: int = Field(ge=1)
    platform: str
    machine: str
    processor: str
    environment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class VecRunnerPreflightReport(VecRunnerModel):
    """Complete read-only VEC-07 admission decision."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-07"] = "VEC-07"
    method_version: Literal["vec-evaluator-runner-1.0"] = "vec-evaluator-runner-1.0"
    status: VecRunnerPreflightStatus
    request: VecRunRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    repositories: list[VecRepositoryEvidence]
    inputs: list[VecRunnerFileEvidence]
    runtime: VecRuntimeEvidence | None
    trace_steps: int | None = Field(default=None, ge=1)
    trace_slots: int | None = Field(default=None, ge=1)
    findings: list[VecRunnerFinding]
    read_only: Literal[True] = True
    mutations_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_outcome(self) -> VecRunnerPreflightReport:
        has_error = any(item.severity is VecRunnerSeverity.ERROR for item in self.findings)
        if self.status is VecRunnerPreflightStatus.ACCEPTED and has_error:
            raise ValueError("accepted preflight cannot contain errors")
        if self.status is VecRunnerPreflightStatus.ACCEPTED and (
            self.runtime is None or self.trace_steps is None or self.trace_slots is None
        ):
            raise ValueError("accepted preflight requires runtime and trace evidence")
        return self

    def fingerprint(self) -> str:
        """Fingerprint the complete admission decision."""

        return _sha256(_canonical_json(self.model_dump(mode="json")).encode())


class VecExecutionReceipt(VecRunnerModel):
    """Typed terminal evidence for one VEC-07 invocation."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-07"] = "VEC-07"
    method_version: Literal["vec-evaluator-runner-1.0"] = "vec-evaluator-runner-1.0"
    status: VecTerminalStatus
    request: VecRunRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    argv: list[str]
    working_directory: Literal["{PRIVATE_WORKSPACE}"] = "{PRIVATE_WORKSPACE}"
    started_at_utc: str
    finished_at_utc: str
    elapsed_seconds: float = Field(ge=0)
    exit_code: int | None
    timed_out: bool
    cancellation_requested: bool
    runtime: VecRuntimeEvidence
    repositories: list[VecRepositoryEvidence]
    inputs_before: list[VecRunnerFileEvidence]
    inputs_after: list[VecRunnerFileEvidence]
    logs: list[VecRunnerFileEvidence]
    stdout_excerpt: str = Field(max_length=256_000)
    stderr_excerpt: str = Field(max_length=256_000)
    outputs: list[VecRunnerFileEvidence]
    findings: list[VecRunnerFinding]
    output_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    external_repositories_modified: bool
    raw_inputs_modified: bool
    published: bool
    scientific_admission: Literal[False] = False

    @model_validator(mode="after")
    def validate_terminal_state(self) -> VecExecutionReceipt:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        if self.status is VecTerminalStatus.COMPLETED:
            if self.exit_code != 0 or not self.published or not self.outputs:
                raise ValueError("completed receipt requires successful published outputs")
            if self.external_repositories_modified or self.raw_inputs_modified:
                raise ValueError("completed receipt requires verified immutable sources and inputs")
            if self.output_fingerprint != output_fingerprint(self.outputs):
                raise ValueError("output fingerprint mismatch")
        elif self.published or self.outputs or self.output_fingerprint is not None:
            raise ValueError("unsuccessful terminal states cannot publish outputs")
        if self.timed_out != (self.status is VecTerminalStatus.TIMED_OUT):
            raise ValueError("timeout flag must match terminal status")
        if self.cancellation_requested != (self.status is VecTerminalStatus.CANCELLED):
            raise ValueError("cancellation flag must match terminal status")
        return self

    def fingerprint(self) -> str:
        """Fingerprint the complete terminal execution evidence."""

        return _sha256(_canonical_json(self.model_dump(mode="json")).encode())


class VecRunnerContract(VecRunnerModel):
    """Machine-readable public boundary for the VEC-07 runner."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-07"] = "VEC-07"
    method_version: Literal["vec-evaluator-runner-1.0"] = "vec-evaluator-runner-1.0"
    audited_commits: dict[str, str]
    source_files: dict[str, str]
    actors: dict[str, dict[str, str]]
    operations: list[str]
    required_dependencies: dict[str, str]
    allowed_flags: list[str]
    outputs: list[str]
    security_controls: list[str]
    interpretation_limits: list[str]

    def fingerprint(self) -> str:
        """Fingerprint the published runner boundary."""

        return _sha256(_canonical_json(self.model_dump(mode="json")).encode())


def vec_runner_contract() -> VecRunnerContract:
    """Return the immutable public VEC-07 safety contract."""

    return VecRunnerContract(
        audited_commits={"vec_env": PINNED_VEC_ENV_COMMIT, "tos-data": PINNED_TOS_DATA_COMMIT},
        source_files=dict(PINNED_EVALUATOR_FILES),
        actors={
            key: {"path": value[0], "sha256": value[1]}
            for key, value in sorted(PINNED_ACTORS.items())
        },
        operations=["preflight_vec_run", "run_vec_evaluator"],
        required_dependencies={"jax": "==0.4.30", "jaxlib": "==0.4.30", "numpy": ">=1.26"},
        allowed_flags=[
            "--trace",
            "--actor",
            "--rsu-cap-per-veh",
            "--max-steps",
            "--seed",
            "--fleet",
            "--fleet-seed",
            "--per-step-out",
            "--per-task-out",
            "--out-json",
        ],
        outputs=[
            "run.json",
            "per-step.npz",
            "per-task.npz",
            "logs/stdout.txt",
            "logs/stderr.txt",
            "execution_receipt.json",
        ],
        security_controls=[
            "exact Git blobs only; external repositories remain read-only",
            "fixed argv without a shell, controlled environment, and CPU-only JAX",
            "regular non-symlink inputs, bounded controls, private staging, and new-only publish",
            "timeout and process-group cancellation never publish partial outputs",
            "source and input identities are rechecked after execution",
        ],
        interpretation_limits=[
            "VEC-07 proves safe local execution, not scientific reproduction",
            "VEC-08 must reconcile numerical outputs before direct launch can become available",
            "selected actions and eligible targets are not proof of completed data transfer",
        ],
    )


def output_fingerprint(outputs: list[VecRunnerFileEvidence]) -> str:
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
