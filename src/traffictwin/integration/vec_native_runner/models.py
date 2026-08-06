"""Strict manifest and report contracts for future-native VEC runner sidecars."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.integration.vec_dispatch import VecDispatchBatchReport, VecDispatchPolicy
from traffictwin.integration.vec_task_lifecycle import VecTaskLifecycleReport

VEC_NATIVE_RUNNER_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_NATIVE_RUNNER_METHOD_VERSION: Literal["vec-native-runner-sidecar-1.0"] = (
    "vec-native-runner-sidecar-1.0"
)
VEC_NATIVE_RUNNER_RESEARCH_STATUS: Literal["provisional_structural_integration"] = (
    "provisional_structural_integration"
)

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class VecNativeRunnerModel(BaseModel):
    """Frozen deterministic base for sidecar artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class VecNativeFileRole(StrEnum):
    """Exact sidecar file roles."""

    LIFECYCLE_EVENTS = "lifecycle_events"
    DISPATCH_REQUESTS = "dispatch_requests"
    DISPATCH_DECISIONS = "dispatch_decisions"


class VecNativeProducerKind(StrEnum):
    """Declared, not authenticated, origin of native-shaped records."""

    SYNTHETIC_FIXTURE = "synthetic_fixture"
    REVIEWED_ADAPTER = "reviewed_adapter"
    NATIVE_EVALUATOR = "native_evaluator"


class VecNativeSemanticsStatus(StrEnum):
    """How producer semantics were declared by the manifest author."""

    PROVISIONAL_DECLARED = "provisional_declared"
    UPSTREAM_CONFIRMED = "upstream_confirmed"


class VecUnavailableLifecycleSemantics(StrEnum):
    """Explicit v1 mapping for a dispatcher with no execution target."""

    EXPLICIT_REJECTION = "explicit_rejection"


class VecNativeFileBinding(VecNativeRunnerModel):
    """Exact identity and safe relative location for one JSONL sidecar."""

    role: VecNativeFileRole
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1, le=256_000_000)
    media_type: Literal["application/x-ndjson"] = "application/x-ndjson"

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if len(value) > 256 or "\\" in value:
            raise ValueError("sidecar paths must be bounded POSIX relative paths")
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.lower() != ".jsonl"
        ):
            raise ValueError("sidecar paths must be safe relative JSONL files")
        return path.as_posix()


class VecNativeRunnerManifest(VecNativeRunnerModel):
    """Digest-bound native-shaped sidecars attached to one successful VEC-07 receipt."""

    schema_version: Literal["1.0"] = VEC_NATIVE_RUNNER_SCHEMA_VERSION
    method_version: Literal["vec-native-runner-sidecar-1.0"] = VEC_NATIVE_RUNNER_METHOD_VERSION
    research_status: Literal["provisional_structural_integration"] = (
        VEC_NATIVE_RUNNER_RESEARCH_STATUS
    )
    run_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    producer_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    producer_version: str = Field(pattern=_IDENTIFIER_PATTERN)
    producer_kind: VecNativeProducerKind
    semantics_status: VecNativeSemanticsStatus
    dispatch_policy: VecDispatchPolicy
    unavailable_lifecycle_semantics: Literal[
        VecUnavailableLifecycleSemantics.EXPLICIT_REJECTION
    ] = VecUnavailableLifecycleSemantics.EXPLICIT_REJECTION
    runner_request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: tuple[VecNativeFileBinding, VecNativeFileBinding, VecNativeFileBinding]
    current_pinned_evaluator_emits_sidecars: Literal[False] = False
    producer_authenticated: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @field_validator("files")
    @classmethod
    def canonicalise_files(
        cls,
        files: tuple[VecNativeFileBinding, VecNativeFileBinding, VecNativeFileBinding],
    ) -> tuple[VecNativeFileBinding, VecNativeFileBinding, VecNativeFileBinding]:
        ordered = tuple(sorted(files, key=lambda item: item.role.value))
        return cast(
            tuple[VecNativeFileBinding, VecNativeFileBinding, VecNativeFileBinding],
            ordered,
        )

    @model_validator(mode="after")
    def validate_file_roles(self) -> Self:
        roles = [item.role for item in self.files]
        paths = [item.path for item in self.files]
        if set(roles) != set(VecNativeFileRole):
            raise ValueError("manifest must bind exactly one file for every native sidecar role")
        if len(paths) != len(set(paths)):
            raise ValueError("native sidecar file paths must be unique")
        return self


class VecNativeRunnerReport(VecNativeRunnerModel):
    """Complete structural replay and lifecycle/dispatch join report."""

    schema_version: Literal["1.0"] = VEC_NATIVE_RUNNER_SCHEMA_VERSION
    method_version: Literal["vec-native-runner-sidecar-1.0"] = VEC_NATIVE_RUNNER_METHOD_VERSION
    research_status: Literal["provisional_structural_integration"] = (
        VEC_NATIVE_RUNNER_RESEARCH_STATUS
    )
    run_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    runner_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    producer_version: str = Field(pattern=_IDENTIFIER_PATTERN)
    producer_kind: VecNativeProducerKind
    semantics_status: VecNativeSemanticsStatus
    bytes_read: int = Field(ge=1)
    lifecycle_report: VecTaskLifecycleReport
    dispatch_report: VecDispatchBatchReport
    v2i_task_count: int = Field(ge=1)
    selected_path_count: int = Field(ge=0)
    unavailable_rejection_count: int = Field(ge=0)
    all_v2i_tasks_joined: Literal[True] = True
    task_count_conservation_holds: Literal[True] = True
    dispatcher_replay_matches: Literal[True] = True
    lifecycle_path_matches: Literal[True] = True
    current_pinned_evaluator_emits_sidecars: Literal[False] = False
    producer_authenticated: Literal[False] = False
    scientific_evidence: Literal[False] = False
    limitations: tuple[str, ...] = (
        "the current pinned evaluator does not emit these native sidecars",
        "digest and structural validation do not authenticate the declared producer",
        "no events are inferred from legacy task_met or modelled-latency arrays",
        "unavailable dispatch maps to explicit rejection only by declared provisional semantics",
        "artifact consistency does not demonstrate physical or scheduler performance",
    )

    @model_validator(mode="after")
    def reconcile_join_counts(self) -> Self:
        if self.v2i_task_count != self.dispatch_report.request_count:
            raise ValueError("every V2I task must have one dispatcher request and decision")
        if self.v2i_task_count != self.selected_path_count + self.unavailable_rejection_count:
            raise ValueError("joined V2I tasks must reconcile into selected paths or rejections")
        if self.selected_path_count != self.dispatch_report.selected_count:
            raise ValueError("selected lifecycle paths must reconcile with dispatcher selections")
        if self.unavailable_rejection_count != self.dispatch_report.unavailable_count:
            raise ValueError("explicit rejections must reconcile with unavailable dispatches")
        return self


class VecNativeRunnerContract(VecNativeRunnerModel):
    """Machine-readable safety and interpretation boundary for sidecar v1."""

    schema_version: Literal["1.0"] = VEC_NATIVE_RUNNER_SCHEMA_VERSION
    method_version: Literal["vec-native-runner-sidecar-1.0"] = VEC_NATIVE_RUNNER_METHOD_VERSION
    research_status: Literal["provisional_structural_integration"] = (
        VEC_NATIVE_RUNNER_RESEARCH_STATUS
    )
    file_roles: tuple[VecNativeFileRole, ...] = tuple(VecNativeFileRole)
    unavailable_lifecycle_semantics: Literal[
        VecUnavailableLifecycleSemantics.EXPLICIT_REJECTION
    ] = VecUnavailableLifecycleSemantics.EXPLICIT_REJECTION
    bounded_read_only: Literal[True] = True
    runner_receipt_binding_required: Literal[True] = True
    lifecycle_replay_required: Literal[True] = True
    dispatcher_replay_required: Literal[True] = True
    current_pinned_evaluator_emits_sidecars: Literal[False] = False
    legacy_array_inference_allowed: Literal[False] = False
    producer_authenticated: Literal[False] = False
    scientific_evidence: Literal[False] = False


def vec_native_runner_contract() -> VecNativeRunnerContract:
    """Return the deterministic native-sidecar integration contract."""

    return VecNativeRunnerContract()
