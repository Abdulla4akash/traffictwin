"""Strict thin-interface contracts for completed VEC services (VEC-10)."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.integration.vec_runner import (
    PINNED_TOS_DATA_COMMIT,
    PINNED_VEC_ENV_COMMIT,
)


class VecInterfaceModel(BaseModel):
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


class VecInterfaceAvailability(StrEnum):
    READY = "ready"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


VecOperationName: TypeAlias = Literal[
    "snapshot",
    "validate",
    "preprocess",
    "run",
    "monitor_current_process",
    "inspect",
    "compare",
    "export",
]
VecArtifactType: TypeAlias = Literal[
    "fcd_preprocess_receipt",
    "execution_receipt",
    "reproduction_report",
    "scientific_admission_report",
]


class VecRepositorySnapshot(VecInterfaceModel):
    repository: Literal["vec_env", "tos-data"]
    audited_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    worktree_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    origin_main: str = Field(pattern=r"^[0-9a-f]{40}$")
    clean: bool
    audited_commit_available: bool
    ready_for_exact_blob_access: bool

    @model_validator(mode="after")
    def reconcile_readiness(self) -> Self:
        expected = (
            self.clean and self.audited_commit_available and self.origin_main == self.audited_commit
        )
        if self.ready_for_exact_blob_access != expected:
            raise ValueError("repository readiness does not match observed source state")
        return self


class VecOperationStatus(VecInterfaceModel):
    operation: VecOperationName
    availability: VecInterfaceAvailability
    reason: str


class VecInterfaceSnapshot(VecInterfaceModel):
    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-10"] = "VEC-10"
    repositories: tuple[VecRepositorySnapshot, VecRepositorySnapshot]
    operations: tuple[VecOperationStatus, ...]
    import_first_available: Literal[True] = True
    arbitrary_command_execution: Literal[False] = False
    persistent_async_queue: Literal[False] = False
    public_publication_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_catalogue(self) -> Self:
        names = [item.repository for item in self.repositories]
        if names != ["vec_env", "tos-data"]:
            raise ValueError("repository snapshots must be ordered vec_env then tos-data")
        operations = [item.operation for item in self.operations]
        expected = [
            "snapshot",
            "validate",
            "preprocess",
            "run",
            "monitor_current_process",
            "inspect",
            "compare",
            "export",
        ]
        if operations != expected:
            raise ValueError("operation statuses must be complete and ordered")
        return self


class VecMetricDelta(VecInterfaceModel):
    metric_key: str
    unit: str
    scope: str
    baseline: int | float
    variation: int | float
    variation_minus_baseline: float


class VecAdmissionComparison(VecInterfaceModel):
    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-10"] = "VEC-10"
    baseline_run_label: str
    variation_run_label: str
    baseline_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    variation_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    comparable_metrics: tuple[VecMetricDelta, ...]
    unavailable_or_incompatible_metrics: tuple[str, ...]
    causal_interpretation: Literal[False] = False
    interpretation: Literal[
        "deterministic descriptive variation-minus-baseline differences only"
    ] = "deterministic descriptive variation-minus-baseline differences only"


class VecArtifactInspection(VecInterfaceModel):
    schema_version: Literal["1.0"] = "1.0"
    capability_id: str
    artifact_type: VecArtifactType
    status: str
    artifact_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary: dict[str, str | int | float | bool | None]


class VecInterfaceContract(VecInterfaceModel):
    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-10"] = "VEC-10"
    audited_commits: dict[str, str]
    operations: tuple[str, ...]
    execution_mode: Literal["foreground_current_process_only"] = "foreground_current_process_only"
    request_formats: tuple[str, ...]
    export_formats: tuple[str, ...]
    conditional_controls: tuple[str, ...]
    prohibited_controls: tuple[str, ...]
    scientific_limits: tuple[str, ...]


def vec_interface_contract() -> VecInterfaceContract:
    return VecInterfaceContract(
        audited_commits={
            "vec_env": PINNED_VEC_ENV_COMMIT,
            "tos-data": PINNED_TOS_DATA_COMMIT,
        },
        operations=(
            "snapshot",
            "validate_preprocess_request",
            "validate_run_request",
            "preprocess",
            "run_foreground",
            "monitor_current_process",
            "inspect",
            "compare_admissions",
            "export_admission",
        ),
        request_formats=("VecFcdPreprocessRequest JSON", "VecRunRequest JSON"),
        export_formats=("json", "csv", "markdown"),
        conditional_controls=(
            "preprocess requires an accepted VEC-06 preflight",
            "run requires an accepted VEC-07 preflight and exact pinned runtime",
            "monitoring is limited to the foreground operation in the current process",
            "comparison requires two accepted VEC-09 reports with compatible scalar metrics",
        ),
        prohibited_controls=(
            "arbitrary command or flags",
            "background or persistent asynchronous queue",
            "SLURM, remote execution, training, or dependency installation",
            "source repository mutation or overwrite",
            "public publication before VEC-11/VEC-12",
        ),
        scientific_limits=(
            "the interface performs no scientific calculations outside tested library services",
            "metric differences are descriptive and non-causal",
            "unavailable VEC-09 metrics remain unavailable",
            "no diagnostic threshold is calibrated or evaluated",
        ),
    )
