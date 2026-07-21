"""Strict evidence models for VEC tier/EV/task/action/target joins (VEC-04)."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT


class VecTaskJoinModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class VecTargetAvailability(StrEnum):
    NOT_APPLICABLE_LOCAL = "not_applicable_local"
    ELIGIBLE_TARGET = "eligible_target"
    NO_ELIGIBLE_TARGET = "no_eligible_target"


class VecSelectedTargetKind(StrEnum):
    NONE = "none"
    RSU_INDEX = "rsu_index"
    VEHICLE_SLOT_INDEX = "vehicle_slot_index"


class VecJoinedTaskObservation(VecTaskJoinModel):
    """One task with source identity and eligibility-aware decision evidence."""

    scenario: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    run_label: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.-]+$")
    time_index: int = Field(ge=0)
    trace_time_s: float
    slot: int = Field(ge=0)
    sumo_vehicle_id: str = Field(min_length=1, max_length=256)
    task_index: int = Field(ge=0, le=4)
    task_class: TaskClass
    latency_ms: float = Field(ge=0)
    deadline_met: bool
    eventual_completion: Literal["unavailable"] = "unavailable"
    slot_tier: int = Field(ge=0, le=2)
    slot_is_ev: bool
    slot_attribute_semantics: Literal["fixed_per_slot_per_run"] = "fixed_per_slot_per_run"
    protected_attribute: Literal[False] = False
    action: Decision
    eligible_best_rsu: int | None = Field(default=None, ge=0)
    eligible_best_v2v: int | None = Field(default=None, ge=0)
    target_availability: VecTargetAvailability
    selected_target_kind: VecSelectedTargetKind
    selected_target_index: int | None = Field(default=None, ge=0)
    target_semantics: Literal["eligible_decision_time_target"] = "eligible_decision_time_target"
    transfer_confirmed: Literal[False] = False
    failure_inferred: Literal[False] = False
    link_quality: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        numeric = (self.trace_time_s, self.latency_ms)
        if not all(math.isfinite(value) for value in numeric):
            raise ValueError("task time and latency must be finite")
        if self.eligible_best_v2v == self.slot:
            raise ValueError("an eligible V2V peer cannot be the source slot")
        expected: tuple[VecTargetAvailability, VecSelectedTargetKind, int | None]
        if self.action is Decision.LOCAL:
            expected = (
                VecTargetAvailability.NOT_APPLICABLE_LOCAL,
                VecSelectedTargetKind.NONE,
                None,
            )
        elif self.action is Decision.V2I:
            expected = (
                VecTargetAvailability.ELIGIBLE_TARGET
                if self.eligible_best_rsu is not None
                else VecTargetAvailability.NO_ELIGIBLE_TARGET,
                VecSelectedTargetKind.RSU_INDEX
                if self.eligible_best_rsu is not None
                else VecSelectedTargetKind.NONE,
                self.eligible_best_rsu,
            )
        elif self.action is Decision.V2V:
            expected = (
                VecTargetAvailability.ELIGIBLE_TARGET
                if self.eligible_best_v2v is not None
                else VecTargetAvailability.NO_ELIGIBLE_TARGET,
                VecSelectedTargetKind.VEHICLE_SLOT_INDEX
                if self.eligible_best_v2v is not None
                else VecSelectedTargetKind.NONE,
                self.eligible_best_v2v,
            )
        else:
            raise ValueError("unknown actions are not admitted by the audited VEC contract")
        if (
            self.target_availability,
            self.selected_target_kind,
            self.selected_target_index,
        ) != expected:
            raise ValueError("selected target fields must exactly follow action eligibility")
        return self


class VecTaskJoinReport(VecTaskJoinModel):
    """Complete count and semantic reconciliation for one matched artifact set."""

    schema_version: Literal["1.0"] = "1.0"
    scenario: str
    run_label: str
    status: Literal["accepted"] = "accepted"
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    identity_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    trace_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    perstep_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    pertask_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_vehicle_seconds: int = Field(ge=0)
    total_tasks: int = Field(ge=0)
    deadline_met_tasks: int = Field(ge=0)
    task_class_counts: dict[TaskClass, int]
    action_counts: dict[Decision, int]
    target_availability_counts: dict[VecTargetAvailability, int]
    no_target_is_failure: Literal[False] = False
    action_is_transfer_confirmation: Literal[False] = False
    eventual_completion_available: Literal[False] = False
    link_quality_available: Literal[False] = False
    per_task_energy_available: Literal[False] = False

    @model_validator(mode="after")
    def reconcile_counts(self) -> Self:
        if set(self.task_class_counts) != {TaskClass.T1, TaskClass.T2, TaskClass.T3}:
            raise ValueError("task class counts must contain exactly T1, T2, and T3")
        if set(self.action_counts) != {Decision.LOCAL, Decision.V2I, Decision.V2V}:
            raise ValueError("action counts must contain exactly local, V2I, and V2V")
        if set(self.target_availability_counts) != set(VecTargetAvailability):
            raise ValueError("all target availability states must be counted")
        for counts in (
            self.task_class_counts,
            self.action_counts,
            self.target_availability_counts,
        ):
            if (
                any(value < 0 for value in counts.values())
                or sum(counts.values()) != self.total_tasks
            ):
                raise ValueError("every count family must be non-negative and sum to total_tasks")
        if self.deadline_met_tasks > self.total_tasks:
            raise ValueError("deadline-met task count cannot exceed total tasks")
        return self


class VecTaskJoinContract(VecTaskJoinModel):
    schema_version: Literal["1.0"] = "1.0"
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    task_type_codes: dict[int, TaskClass] = {0: TaskClass.T1, 1: TaskClass.T2, 2: TaskClass.T3}
    action_codes: dict[int, Decision] = {0: Decision.LOCAL, 1: Decision.V2I, 2: Decision.V2V}
    latency_reconciliation_abs_tolerance_ms: float = 0.00390625
    latency_reconciliation_rel_tolerance: float = 3e-7
    semantics: tuple[str, ...] = (
        "one vehicle action applies to every task arriving for that vehicle-second",
        "-1 means no eligible target and does not establish transfer failure",
        "task_met is deadline success, not eventual physical completion",
        "tier and EV are fixed per-slot operational assignments for one run",
    )
    unavailable_claims: tuple[str, ...] = (
        "transfer confirmation",
        "eventual physical completion",
        "link quality",
        "per-task energy",
        "protected or demographic attribute status",
    )


def vec_task_join_contract() -> VecTaskJoinContract:
    return VecTaskJoinContract()
