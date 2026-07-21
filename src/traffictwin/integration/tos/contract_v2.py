"""Observed TOS/VEC source contract v2 with golden/negative fixture validation (VEC-02).

This module encodes the schemas and semantics observed by the accepted Gate A
audit (`VEC-01`): `docs/integration/randy-source-snapshot-audit-v0_6.md` and its
machine record `docs/reference/generated/vec_source_snapshot_audit.json`. It is
library-level VEC-02 work: strict contract models, typed row views, and
deterministic validators for the v2 artifact families, exercised by synthetic
golden and negative fixtures. Capability truth is reconciled by the integrating
agent; nothing here flips a capability or claims VEC-02 is implemented.

Audited semantics enforced here:

- occupancy spans use inclusive ``t_enter``/``t_exit`` time indices; a slot
  hosts one vehicle per second and a vehicle occupies one slot per second;
- ``task_met``/``done``/``completion`` are deadline success, never eventual
  physical completion, which remains unavailable;
- per-task energy is absent from the observed per-task schema and remains
  unavailable; an energy-like key is rejected with an explicit finding;
- ``veh_best_rsu``/``veh_best_v2v`` are eligible decision-time targets; ``-1``
  means no eligible target, and a selected action is never transfer proof;
- ``slot_tier``/``slot_is_ev`` are fixed per-slot operational assignments for a
  run (recycled vehicles inherit them) and are never protected attributes;
- trace time grids are contiguous one-second steps with ``dt == 1.0``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.domain.enums import Decision, TaskClass

TOS_CONTRACT_V2_SCHEMA_VERSION: Literal["2.0"] = "2.0"
TOS_CONTRACT_V2_EVIDENCE_STATE: Literal["audited"] = "audited"
VEC_ENV_AUDITED_COMMIT = "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
TOS_DATA_AUDITED_COMMIT = "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"
VEC01_AUDIT_DOCUMENT = "docs/integration/randy-source-snapshot-audit-v0_6.md"
VEC01_AUDIT_RECORD = "docs/reference/generated/vec_source_snapshot_audit.json"

TRACE_KEYS = (
    "T",
    "dt",
    "mask",
    "maxN",
    "pos_x",
    "pos_y",
    "rsu_xy",
    "speed",
    "sumo_seed",
    "times",
    "window",
)
PERSTEP_KEYS = (
    "active",
    "arrivals",
    "done",
    "lat_sum",
    "n_local",
    "n_v2i",
    "n_v2v",
    "rsu_busy_ms",
    "rsu_load",
    "slot_is_ev",
    "slot_tier",
    "times",
    "veh_action",
    "veh_best_rsu",
    "veh_best_v2v",
    "veh_done",
    "veh_k",
    "veh_queue_ms",
)
PERTASK_KEYS = ("task_active", "task_lat_ms", "task_met", "task_type")
OCCUPANCY_HEADER = ("sumo_vehicle_id", "slot", "t_enter", "t_exit")
RUN_SUMMARY_REQUIRED_KEYS = (
    "avg_latency_ms_per_task",
    "completion",
    "fleet_ev_share",
    "fleet_tier_hist",
    "p_local",
    "p_v2i",
    "p_v2v",
    "total_tasks",
)
MAX_TASKS_PER_VEHICLE_STEP = 5
TIER_MIN = 0
TIER_MAX = 2
TRACE_DT_SECONDS = 1.0
LATENCY_REL_TOL = 1e-5
LATENCY_ABS_TOL_MS = 1e-3
SHARE_ABS_TOL = 1e-9
FLOAT32_SHARE_ABS_TOL = 1e-6
_MAX_TEXT_LENGTH = 2_000
_ENERGY_KEY_MARKERS = ("energy", "joule")
_COMPLETION_KEY_MARKERS = ("physical", "eventual")


class ContractV2Model(BaseModel):
    """Strict, immutable base for contract-v2 models."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def canonical_json(self) -> str:
        """Return the canonical JSON form used for fingerprinting."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical JSON form."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _validate_bounded_text(value: str) -> str:
    if not 1 <= len(value) <= _MAX_TEXT_LENGTH:
        raise ValueError(f"text must be 1-{_MAX_TEXT_LENGTH} characters")
    if "\x00" in value or any(ord(char) < 32 for char in value):
        raise ValueError(f"text must not contain control characters: {value!r}")
    if value.startswith(("/", "~")) or "\\" in value or "file://" in value:
        raise ValueError(f"text must not carry local absolute paths: {value!r}")
    return value


def _validate_repo_relative_path(value: str) -> str:
    _validate_bounded_text(value)
    if any(segment in {"", ".", ".."} for segment in value.split("/")):
        raise ValueError(f"path must not contain empty, '.', or '..' segments: {value!r}")
    return value


class AuditedSourceFile(ContractV2Model):
    """One producer/evaluator source file pinned by the VEC-01 audit."""

    path: str
    purpose: str
    size_bytes: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _validate_repo_relative_path(value)

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, value: str) -> str:
        return _validate_bounded_text(value)


class ObservedArraySchema(ContractV2Model):
    """Observed dtype/shape statement for one array in a v2 artifact."""

    name: str
    artifact: str
    dtype: str
    shape: list[int | str] = Field(max_length=8)
    unit: str | None = None
    meaning: str

    @field_validator("name", "meaning")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_bounded_text(value)

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_bounded_text(value)

    @field_validator("artifact")
    @classmethod
    def validate_artifact(cls, value: str) -> str:
        return _validate_bounded_text(value)


class UnavailableField(ContractV2Model):
    """A field that must remain unavailable because the audit found no evidence."""

    name: str
    reason: str
    audit_blocker_id: str

    @field_validator("name", "reason", "audit_blocker_id")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_bounded_text(value)


class TosSourceContractV2(ContractV2Model):
    """Machine-readable observed contract for the audited v0.6 snapshots."""

    schema_version: Literal["2.0"] = TOS_CONTRACT_V2_SCHEMA_VERSION
    evidence_state: Literal["audited"] = TOS_CONTRACT_V2_EVIDENCE_STATE
    vec_env_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    tos_data_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audit_document: str
    audit_record: str
    source_files: list[AuditedSourceFile] = Field(min_length=1, max_length=32)
    arrays: list[ObservedArraySchema] = Field(min_length=1, max_length=128)
    semantics: list[str] = Field(min_length=1, max_length=64)
    unavailable_fields: list[UnavailableField] = Field(min_length=1, max_length=32)
    capabilities: dict[str, bool] = Field(min_length=1, max_length=32)
    blockers: list[str] = Field(min_length=1, max_length=32)

    @field_validator("audit_document", "audit_record")
    @classmethod
    def validate_paths(cls, value: str) -> str:
        return _validate_repo_relative_path(value)

    @field_validator("semantics", "blockers")
    @classmethod
    def validate_statements(cls, value: list[str]) -> list[str]:
        for item in value:
            _validate_bounded_text(item)
        return value

    @field_validator("source_files")
    @classmethod
    def sort_source_files(cls, value: list[AuditedSourceFile]) -> list[AuditedSourceFile]:
        return sorted(value, key=lambda item: item.path)

    @field_validator("arrays")
    @classmethod
    def sort_arrays(cls, value: list[ObservedArraySchema]) -> list[ObservedArraySchema]:
        return sorted(value, key=lambda item: (item.artifact, item.name))

    @field_validator("unavailable_fields")
    @classmethod
    def sort_unavailable(cls, value: list[UnavailableField]) -> list[UnavailableField]:
        return sorted(value, key=lambda item: item.name)

    @model_validator(mode="after")
    def validate_library_boundaries(self) -> Self:
        enabled = sorted(name for name, flag in self.capabilities.items() if flag)
        if enabled:
            raise ValueError(
                "the contract library cannot enable capabilities; capability truth is "
                f"reconciled by the integrating agent; enabled: {', '.join(enabled)}"
            )
        required_unavailable = {
            "per_task_energy_j",
            "eventual_physical_completion",
            "transfer_confirmation",
        }
        declared = {item.name for item in self.unavailable_fields}
        missing = sorted(required_unavailable - declared)
        if missing:
            raise ValueError(
                "the audited contract must keep the evidence-absent fields visibly "
                f"unavailable; missing: {', '.join(missing)}"
            )
        return self


def tos_source_contract_v2() -> TosSourceContractV2:
    """Return the observed v2 contract pinned by the accepted VEC-01 audit."""

    perstep = "instrumented/perstep/*_perstep.npz"
    pertask = "instrumented/pertask/*_pertask.npz"
    trace = "traces/trace_*.npz"
    occupancy = "occupancy/occupancy_*.csv"
    return TosSourceContractV2(
        vec_env_commit=VEC_ENV_AUDITED_COMMIT,
        tos_data_commit=TOS_DATA_AUDITED_COMMIT,
        audit_document=VEC01_AUDIT_DOCUMENT,
        audit_record=VEC01_AUDIT_RECORD,
        source_files=[
            AuditedSourceFile(
                path="eval/build_trace.py",
                purpose=(
                    "FCD/network-to-trace builder; writes dt=1.0 without deriving it "
                    "and starts with Manchester sensor RSU positions."
                ),
                size_bytes=6030,
                sha256="5af3aa9b284dd06a9e25989fbb7e9060227c7906a2754e9c5436ddd925090387",
            ),
            AuditedSourceFile(
                path="eval/eval_sumo_stage1_mc.py",
                purpose=(
                    "Headless evaluator and instrumented writer; contains a "
                    "non-portable hard-coded import path."
                ),
                size_bytes=21359,
                sha256="52490949e9d35cfaed2f9ba03ac92b08b475de503715a1967bc74950b689bf7c",
            ),
            AuditedSourceFile(
                path="eval/place_rsus_cover.py",
                purpose=(
                    "Deterministic greedy grid set-cover placement helper; reads only "
                    "a freshly produced trace in the accepted wrapper."
                ),
                size_bytes=3043,
                sha256="33928f4113988ee39f75ff06d99f2c01061182f9d0f17092e051a159a42840a0",
            ),
            AuditedSourceFile(
                path="eval/reconstruct_occupancy.py",
                purpose="Occupancy-span reconstruction source for the audited tables.",
                size_bytes=3665,
                sha256="019e75397d4889955b3b4608318297cd112e00e698281a06468dd8d683d5a6ad",
            ),
            AuditedSourceFile(
                path="jaxmarl/env/vec_jax.py",
                purpose=(
                    "Pure-JAX Model-C environment imported by the evaluator; an "
                    "executable VEC-07 source dependency."
                ),
                size_bytes=79253,
                sha256="4eed6b61f157b9a1ba203d0095acdecb0741f2da8d7fc4f411b6ee16a0bdd4f9",
            ),
        ],
        arrays=[
            ObservedArraySchema(
                name="T",
                artifact=trace,
                dtype="int32",
                shape=[],
                unit="timesteps",
                meaning="Trace timestep count.",
            ),
            ObservedArraySchema(
                name="dt",
                artifact=trace,
                dtype="float32",
                shape=[],
                unit="s",
                meaning="Declared trace timestep resolution; exactly 1.0.",
            ),
            ObservedArraySchema(
                name="maxN",
                artifact=trace,
                dtype="int32",
                shape=[],
                unit="slots",
                meaning="Dense vehicle-slot dimension.",
            ),
            ObservedArraySchema(
                name="sumo_seed",
                artifact=trace,
                dtype="int32",
                shape=[],
                unit="seed",
                meaning="SUMO seed declared by the trace builder.",
            ),
            ObservedArraySchema(
                name="window",
                artifact=trace,
                dtype="unicode",
                shape=[],
                unit=None,
                meaning="Source FCD filename label recorded by the trace builder.",
            ),
            ObservedArraySchema(
                name="times",
                artifact=trace,
                dtype="float32",
                shape=["T"],
                unit="s",
                meaning="Contiguous one-second SUMO timestamps.",
            ),
            ObservedArraySchema(
                name="mask",
                artifact=trace,
                dtype="bool",
                shape=["T", "maxN"],
                unit=None,
                meaning="Slot occupancy mask; matches inclusive occupancy spans exactly.",
            ),
            ObservedArraySchema(
                name="pos_x",
                artifact=trace,
                dtype="float32",
                shape=["T", "maxN"],
                unit="m",
                meaning="SUMO network x coordinate per occupied slot second.",
            ),
            ObservedArraySchema(
                name="pos_y",
                artifact=trace,
                dtype="float32",
                shape=["T", "maxN"],
                unit="m",
                meaning="SUMO network y coordinate per occupied slot second.",
            ),
            ObservedArraySchema(
                name="speed",
                artifact=trace,
                dtype="float32",
                shape=["T", "maxN"],
                unit="m/s",
                meaning="SUMO speed per occupied slot second.",
            ),
            ObservedArraySchema(
                name="rsu_xy",
                artifact=trace,
                dtype="float32",
                shape=["n_rsu", 2],
                unit="m",
                meaning="RSU positions encoded by the placement step.",
            ),
            ObservedArraySchema(
                name="times",
                artifact=perstep,
                dtype="float32",
                shape=["T"],
                unit="s",
                meaning="Exact copy of the trace time grid.",
            ),
            ObservedArraySchema(
                name="active",
                artifact=perstep,
                dtype="int32",
                shape=["T"],
                unit="slots",
                meaning="Active trace slots in each second.",
            ),
            ObservedArraySchema(
                name="arrivals",
                artifact=perstep,
                dtype="int32",
                shape=["T"],
                unit="tasks",
                meaning="Task arrivals in each second.",
            ),
            ObservedArraySchema(
                name="done",
                artifact=perstep,
                dtype="int32",
                shape=["T"],
                unit="tasks",
                meaning="Deadline-successful task arrivals in each second.",
            ),
            ObservedArraySchema(
                name="lat_sum",
                artifact=perstep,
                dtype="float32",
                shape=["T"],
                unit="ms",
                meaning="Sum of modelled task latency in each second.",
            ),
            ObservedArraySchema(
                name="n_local",
                artifact=perstep,
                dtype="int32",
                shape=["T"],
                unit="tasks",
                meaning="Task arrivals assigned the local action in each second.",
            ),
            ObservedArraySchema(
                name="n_v2i",
                artifact=perstep,
                dtype="int32",
                shape=["T"],
                unit="tasks",
                meaning="Task arrivals assigned the V2I action in each second.",
            ),
            ObservedArraySchema(
                name="n_v2v",
                artifact=perstep,
                dtype="int32",
                shape=["T"],
                unit="tasks",
                meaning="Task arrivals assigned the V2V action in each second.",
            ),
            ObservedArraySchema(
                name="slot_tier",
                artifact=perstep,
                dtype="int8",
                shape=["maxN"],
                unit="code",
                meaning=(
                    "Fixed per-slot compute-tier assignment in 0..2 for the run; "
                    "recycled vehicles inherit it."
                ),
            ),
            ObservedArraySchema(
                name="slot_is_ev",
                artifact=perstep,
                dtype="bool",
                shape=["maxN"],
                unit=None,
                meaning="Fixed per-slot EV assignment for the run; operational only.",
            ),
            ObservedArraySchema(
                name="veh_action",
                artifact=perstep,
                dtype="int8",
                shape=["T", "maxN"],
                unit="code",
                meaning="Selected decision: 0=local, 1=V2I, 2=V2V.",
            ),
            ObservedArraySchema(
                name="veh_best_rsu",
                artifact=perstep,
                dtype="int16",
                shape=["T", "maxN"],
                unit="index",
                meaning=(
                    "Eligible best RSU at decision time; -1 means no eligible target "
                    "and is never a completed offload."
                ),
            ),
            ObservedArraySchema(
                name="veh_best_v2v",
                artifact=perstep,
                dtype="int16",
                shape=["T", "maxN"],
                unit="index",
                meaning=(
                    "Eligible best V2V peer at decision time; -1 means no eligible "
                    "target; an eligible peer is never the source slot."
                ),
            ),
            ObservedArraySchema(
                name="veh_k",
                artifact=perstep,
                dtype="int8",
                shape=["T", "maxN"],
                unit="tasks",
                meaning="Tasks arriving at the slot this second, at most 5.",
            ),
            ObservedArraySchema(
                name="veh_done",
                artifact=perstep,
                dtype="int16",
                shape=["T", "maxN"],
                unit="tasks",
                meaning="Deadline-successful tasks at the slot this second.",
            ),
            ObservedArraySchema(
                name="veh_queue_ms",
                artifact=perstep,
                dtype="float32",
                shape=["T", "maxN"],
                unit="ms",
                meaning="Vehicle-local queue signal; finite and non-negative.",
            ),
            ObservedArraySchema(
                name="rsu_load",
                artifact=perstep,
                dtype="int32",
                shape=["T", "n_rsu"],
                unit="tasks",
                meaning="In-flight task count; not CPU utilisation or queue length.",
            ),
            ObservedArraySchema(
                name="rsu_busy_ms",
                artifact=perstep,
                dtype="float32",
                shape=["T", "n_rsu"],
                unit="ms",
                meaning="Remaining compute backlog; no utilisation denominator.",
            ),
            ObservedArraySchema(
                name="task_type",
                artifact=pertask,
                dtype="int8",
                shape=["T", "K", "maxN"],
                unit="code",
                meaning="Task class code 0=T1, 1=T2, 2=T3 for active task cells.",
            ),
            ObservedArraySchema(
                name="task_lat_ms",
                artifact=pertask,
                dtype="float32",
                shape=["T", "K", "maxN"],
                unit="ms",
                meaning="Modelled end-to-end latency for active task cells.",
            ),
            ObservedArraySchema(
                name="task_met",
                artifact=pertask,
                dtype="bool",
                shape=["T", "K", "maxN"],
                unit=None,
                meaning="Deadline success; never eventual physical completion.",
            ),
            ObservedArraySchema(
                name="task_active",
                artifact=pertask,
                dtype="bool",
                shape=["T", "K", "maxN"],
                unit=None,
                meaning="Whether the task cell holds a real task.",
            ),
            ObservedArraySchema(
                name="occupancy_row",
                artifact=occupancy,
                dtype="str",
                shape=[4],
                unit=None,
                meaning=(
                    "CSV row sumo_vehicle_id,slot,t_enter,t_exit with inclusive "
                    "integer time-index bounds."
                ),
            ),
        ],
        semantics=[
            "Occupancy t_enter/t_exit bounds are inclusive; visit seconds equal "
            "t_exit - t_enter + 1 and reconcile exactly with the trace mask.",
            "task_met, done, and completion are per-arrival deadline success only.",
            "A selected V2I/V2V action with target -1 has no eligible target and is "
            "not a completed offload.",
            "slot_tier and slot_is_ev are fixed operational per-slot assignments for "
            "a run and are never protected attributes.",
            "Trace time grids are contiguous one-second steps with dt exactly 1.0.",
            "_s102 rows keep the best-of-seeds label and reused evidence carries the "
            "v2_post_nrsus_fix engine label with both repositories cited.",
        ],
        unavailable_fields=[
            UnavailableField(
                name="per_task_energy_j",
                reason="The six audited per-task NPZ files contain no per-task energy field.",
                audit_blocker_id="per_task_energy_absent",
            ),
            UnavailableField(
                name="eventual_physical_completion",
                reason=(
                    "task_met/done/completion represent deadline success; no eventual "
                    "physical-completion field was observed."
                ),
                audit_blocker_id="eventual_physical_completion_absent",
            ),
            UnavailableField(
                name="transfer_confirmation",
                reason=(
                    "Targets are eligible decision-time values; 4,368 V2I and 55,658 "
                    "V2V decision rows have no eligible target."
                ),
                audit_blocker_id="action_is_not_transfer_proof",
            ),
        ],
        capabilities={
            "direct_launch": False,
            "occupancy_identity_join": False,
            "trip_join": False,
            "fcd_preprocessing": False,
        },
        blockers=[
            "eventual_physical_completion_absent: model completion fields as deadline "
            "success and keep eventual completion unavailable.",
            "action_is_not_transfer_proof: join targets only with eligibility-aware "
            "semantics and expose -1.",
            "per_task_energy_absent: do not publish per-task or denominator-sensitive "
            "energy metrics from these rows.",
        ],
    )


class OccupancySpan(ContractV2Model):
    """One audited-schema occupancy row with inclusive integer time bounds."""

    sumo_vehicle_id: str
    slot: int = Field(ge=0)
    t_enter: int = Field(ge=0)
    t_exit: int = Field(ge=0)
    scenario: str

    @field_validator("sumo_vehicle_id", "scenario")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_bounded_text(value)

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.t_exit < self.t_enter:
            raise ValueError(
                f"inclusive span requires t_exit >= t_enter; got [{self.t_enter}, {self.t_exit}]"
            )
        return self

    @property
    def visit_seconds(self) -> int:
        """Inclusive occupancy duration in seconds."""

        return self.t_exit - self.t_enter + 1


class VecVehicleAttributeObservation(ContractV2Model):
    """Occupancy-aligned fixed per-slot tier and EV assignment for one run."""

    sumo_vehicle_id: str
    slot: int = Field(ge=0)
    t_enter: int = Field(ge=0)
    t_exit: int = Field(ge=0)
    slot_tier: int = Field(ge=TIER_MIN, le=TIER_MAX)
    slot_is_ev: bool
    assignment_semantics: Literal["fixed_per_slot_per_run"] = "fixed_per_slot_per_run"
    protected_attribute: Literal[False] = False

    @field_validator("sumo_vehicle_id")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_bounded_text(value)

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.t_exit < self.t_enter:
            raise ValueError("inclusive span requires t_exit >= t_enter")
        return self


class VecTaskActionObservation(ContractV2Model):
    """One task/action row under audited eligibility-aware target semantics."""

    time_index: int = Field(ge=0)
    slot: int = Field(ge=0)
    sumo_vehicle_id: str
    task_class: TaskClass
    deadline_met: bool
    eventual_completion: Literal["unavailable"] = "unavailable"
    action: Decision
    eligible_best_rsu: int | None = Field(default=None, ge=-1)
    eligible_best_v2v: int | None = Field(default=None, ge=-1)
    target_semantics: Literal["eligible_decision_time_target"] = "eligible_decision_time_target"
    transfer_confirmed: Literal[False] = False

    @field_validator("sumo_vehicle_id")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_bounded_text(value)

    @model_validator(mode="after")
    def validate_targets(self) -> Self:
        if (
            self.action is Decision.V2V
            and self.eligible_best_v2v is not None
            and self.eligible_best_v2v == self.slot
        ):
            raise ValueError("an eligible V2V peer is never the source slot")
        return self


class TripJoinEligibility(StrEnum):
    """Audited trip-join eligibility states with no invented causes."""

    ELIGIBLE_COMPLETE = "eligible_complete"
    EXCLUDED_RIGHT_CENSORED_AT_BOUNDARY = "excluded_right_censored_at_boundary"
    EXCLUDED_MISSING_BEFORE_BOUNDARY = "excluded_missing_before_boundary"
    EXCLUDED_UNMATCHED = "excluded_unmatched"


class VecTripJoin(ContractV2Model):
    """One SUMO trip record joined to an exact vehicle under audited coverage."""

    sumo_vehicle_id: str
    scenario: str
    eligibility: TripJoinEligibility
    depart_s: float = Field(ge=0)
    arrival_s: float | None = Field(default=None, ge=0)
    duration_s: float | None = Field(default=None, ge=0)
    route_length_m: float | None = Field(default=None, ge=0)
    exclusion_reason: str | None = None

    @field_validator("sumo_vehicle_id", "scenario")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _validate_bounded_text(value)

    @field_validator("exclusion_reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_bounded_text(value)

    @model_validator(mode="after")
    def validate_eligibility(self) -> Self:
        for name, value in (
            ("depart_s", self.depart_s),
            ("arrival_s", self.arrival_s),
            ("duration_s", self.duration_s),
            ("route_length_m", self.route_length_m),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.eligibility is TripJoinEligibility.ELIGIBLE_COMPLETE:
            if self.arrival_s is None or self.duration_s is None:
                raise ValueError("an eligible complete trip requires arrival_s and duration_s")
            if self.exclusion_reason is not None:
                raise ValueError("an eligible complete trip cannot carry an exclusion_reason")
            if self.arrival_s <= self.depart_s:
                raise ValueError("arrival_s must be after depart_s")
            if not math.isclose(
                self.duration_s, self.arrival_s - self.depart_s, rel_tol=0, abs_tol=1e-6
            ):
                raise ValueError("duration_s must equal arrival_s - depart_s")
        else:
            if self.exclusion_reason is None:
                raise ValueError("an excluded trip join requires an exclusion_reason")
            if self.arrival_s is not None or self.duration_s is not None:
                raise ValueError(
                    "an excluded trip join must not carry arrival_s or duration_s; "
                    "missing values are not filled"
                )
        return self


class V2FindingCode(StrEnum):
    """Deterministic finding codes for v2 artifact validation."""

    MISSING_KEYS = "missing_keys"
    UNEXPECTED_KEYS = "unexpected_keys"
    ENERGY_FIELD_NOT_IN_CONTRACT = "energy_field_not_in_contract"
    COMPLETION_FIELD_NOT_IN_CONTRACT = "completion_field_not_in_contract"
    DTYPE_MISMATCH = "dtype_mismatch"
    SHAPE_MISMATCH = "shape_mismatch"
    TIME_GRID_INVALID = "time_grid_invalid"
    VALUE_RANGE_INVALID = "value_range_invalid"
    TARGET_RANGE_INVALID = "target_range_invalid"
    SELF_V2V_TARGET = "self_v2v_target"
    TIER_RANGE_INVALID = "tier_range_invalid"
    INTERNAL_COUNTS_INCONSISTENT = "internal_counts_inconsistent"
    AGGREGATE_MISMATCH = "aggregate_mismatch"
    ACTIVE_MASK_MISMATCH = "active_mask_mismatch"
    HEADER_MISMATCH = "header_mismatch"
    SPAN_BOUNDS_INVALID = "span_bounds_invalid"
    SLOT_OVERLAP = "slot_overlap"
    VEHICLE_OVERLAP = "vehicle_overlap"
    DUPLICATE_SPAN = "duplicate_span"
    RANGE_OUT_OF_TRACE = "range_out_of_trace"
    SHARE_SUM_INVALID = "share_sum_invalid"
    TIER_HIST_INVALID = "tier_hist_invalid"
    UPSTREAM_ARTIFACT_INVALID = "upstream_artifact_invalid"


class V2Finding(ContractV2Model):
    """One deterministic validation finding."""

    code: V2FindingCode
    detail: str

    @field_validator("detail")
    @classmethod
    def validate_detail(cls, value: str) -> str:
        return _validate_bounded_text(value)


class ArtifactValidationReport(ContractV2Model):
    """Deterministic validation outcome for one v2 artifact."""

    artifact: str
    status: Literal["accepted", "rejected"]
    findings: list[V2Finding]

    @field_validator("artifact")
    @classmethod
    def validate_artifact(cls, value: str) -> str:
        return _validate_bounded_text(value)


def _report(artifact: str, findings: list[V2Finding]) -> ArtifactValidationReport:
    ordered = sorted(findings, key=lambda finding: (finding.code.value, finding.detail))
    return ArtifactValidationReport(
        artifact=artifact,
        status="accepted" if not ordered else "rejected",
        findings=ordered,
    )


def _key_findings(observed: set[str], expected: tuple[str, ...], findings: list[V2Finding]) -> bool:
    expected_set = set(expected)
    missing = sorted(expected_set - observed)
    unexpected = sorted(observed - expected_set)
    if missing:
        findings.append(
            V2Finding(
                code=V2FindingCode.MISSING_KEYS,
                detail=f"missing keys: {', '.join(missing)}",
            )
        )
    for key in unexpected:
        lowered = key.lower()
        if any(marker in lowered for marker in _ENERGY_KEY_MARKERS):
            findings.append(
                V2Finding(
                    code=V2FindingCode.ENERGY_FIELD_NOT_IN_CONTRACT,
                    detail=(
                        f"key {key!r} is not in the audited contract; per-task energy "
                        "remains unavailable (per_task_energy_absent)"
                    ),
                )
            )
        elif any(marker in lowered for marker in _COMPLETION_KEY_MARKERS):
            findings.append(
                V2Finding(
                    code=V2FindingCode.COMPLETION_FIELD_NOT_IN_CONTRACT,
                    detail=(
                        f"key {key!r} is not in the audited contract; eventual physical "
                        "completion remains unavailable "
                        "(eventual_physical_completion_absent)"
                    ),
                )
            )
        else:
            findings.append(
                V2Finding(
                    code=V2FindingCode.UNEXPECTED_KEYS,
                    detail=f"unexpected key: {key}",
                )
            )
    return not missing and not unexpected


def validate_trace_arrays(arrays: Mapping[str, Any]) -> ArtifactValidationReport:
    """Validate one trace NPZ mapping against the audited schema."""

    import numpy as np

    findings: list[V2Finding] = []
    if not _key_findings(set(arrays), TRACE_KEYS, findings):
        return _report("trace", findings)

    materialised = {key: np.asarray(arrays[key]) for key in TRACE_KEYS}
    expected_dtypes = {
        "T": "int32",
        "dt": "float32",
        "mask": "bool",
        "maxN": "int32",
        "pos_x": "float32",
        "pos_y": "float32",
        "rsu_xy": "float32",
        "speed": "float32",
        "sumo_seed": "int32",
        "times": "float32",
    }
    for key, expected_dtype in expected_dtypes.items():
        if str(materialised[key].dtype) != expected_dtype:
            findings.append(
                V2Finding(
                    code=V2FindingCode.DTYPE_MISMATCH,
                    detail=f"{key} must have audited dtype {expected_dtype}",
                )
            )
    if materialised["window"].dtype.kind != "U":
        findings.append(
            V2Finding(
                code=V2FindingCode.DTYPE_MISMATCH,
                detail="window must have an audited NumPy unicode dtype",
            )
        )
    for key in ("T", "dt", "maxN", "sumo_seed", "window"):
        if materialised[key].shape != ():
            findings.append(
                V2Finding(
                    code=V2FindingCode.SHAPE_MISMATCH,
                    detail=f"{key} must be a scalar array",
                )
            )
    if findings:
        return _report("trace", findings)

    t_count = int(materialised["T"])
    max_n = int(materialised["maxN"])
    times = materialised["times"]
    mask = materialised["mask"]
    if t_count < 1 or max_n < 1:
        findings.append(
            V2Finding(
                code=V2FindingCode.SHAPE_MISMATCH,
                detail=f"T and maxN must be positive; got T={t_count}, maxN={max_n}",
            )
        )
        return _report("trace", findings)
    if float(materialised["dt"]) != TRACE_DT_SECONDS:
        findings.append(
            V2Finding(
                code=V2FindingCode.TIME_GRID_INVALID,
                detail=f"dt must be exactly {TRACE_DT_SECONDS}; got {float(materialised['dt'])}",
            )
        )
    if times.shape != (t_count,) or (
        times.size > 1 and not bool(np.all(np.diff(times) == TRACE_DT_SECONDS))
    ):
        findings.append(
            V2Finding(
                code=V2FindingCode.TIME_GRID_INVALID,
                detail="times must be contiguous one-second steps of length T",
            )
        )
    if mask.shape != (t_count, max_n):
        findings.append(
            V2Finding(
                code=V2FindingCode.SHAPE_MISMATCH,
                detail="mask must be a boolean array of shape (T, maxN)",
            )
        )
    for key in ("pos_x", "pos_y", "speed"):
        array = materialised[key]
        if array.shape != (t_count, max_n):
            findings.append(
                V2Finding(
                    code=V2FindingCode.SHAPE_MISMATCH,
                    detail=f"{key} must have shape (T, maxN)",
                )
            )
    rsu_xy = materialised["rsu_xy"]
    if rsu_xy.ndim != 2 or rsu_xy.shape[0] < 1 or rsu_xy.shape[1] != 2:
        findings.append(
            V2Finding(
                code=V2FindingCode.SHAPE_MISMATCH,
                detail="rsu_xy must have shape (n_rsu, 2) with n_rsu >= 1",
            )
        )
    numeric = [times, materialised["pos_x"], materialised["pos_y"], materialised["speed"], rsu_xy]
    if not all(bool(np.all(np.isfinite(array))) for array in numeric):
        findings.append(
            V2Finding(
                code=V2FindingCode.VALUE_RANGE_INVALID,
                detail="trace times, coordinates, speed, and RSU coordinates must be finite",
            )
        )
    if bool(np.any(materialised["speed"] < 0)) or int(materialised["sumo_seed"]) < 0:
        findings.append(
            V2Finding(
                code=V2FindingCode.VALUE_RANGE_INVALID,
                detail="trace speed and sumo_seed must be non-negative",
            )
        )
    window = str(materialised["window"])
    if not window or len(window) > 256 or any(ord(char) < 32 for char in window):
        findings.append(
            V2Finding(
                code=V2FindingCode.VALUE_RANGE_INVALID,
                detail="trace window must be a bounded non-empty printable label",
            )
        )
    return _report("trace", findings)


def validate_perstep_arrays(
    arrays: Mapping[str, Any],
    trace_arrays: Mapping[str, Any],
    run_summary: Mapping[str, Any] | None = None,
) -> ArtifactValidationReport:
    """Validate one per-step NPZ mapping against the audited 18-key schema."""

    import numpy as np

    findings: list[V2Finding] = []
    trace_report = validate_trace_arrays(trace_arrays)
    if trace_report.status != "accepted":
        return _report(
            "perstep",
            [
                V2Finding(
                    code=V2FindingCode.UPSTREAM_ARTIFACT_INVALID,
                    detail="trace arrays must pass the VEC-02 trace contract first",
                )
            ],
        )
    if not _key_findings(set(arrays), PERSTEP_KEYS, findings):
        return _report("perstep", findings)
    t_count = int(trace_arrays["T"])
    max_n = int(trace_arrays["maxN"])
    rsu_count = int(np.asarray(trace_arrays["rsu_xy"]).shape[0])
    materialised = {key: np.asarray(arrays[key]) for key in PERSTEP_KEYS}
    shape_expectations: dict[str, tuple[int, ...]] = {
        "times": (t_count,),
        "slot_tier": (max_n,),
        "slot_is_ev": (max_n,),
        **dict.fromkeys(
            ("active", "arrivals", "done", "lat_sum", "n_local", "n_v2i", "n_v2v"),
            (t_count,),
        ),
        **dict.fromkeys(
            (
                "veh_action",
                "veh_best_rsu",
                "veh_best_v2v",
                "veh_done",
                "veh_k",
                "veh_queue_ms",
            ),
            (t_count, max_n),
        ),
        **dict.fromkeys(("rsu_busy_ms", "rsu_load"), (t_count, rsu_count)),
    }
    for key, expected_shape in sorted(shape_expectations.items()):
        if materialised[key].shape != expected_shape:
            findings.append(
                V2Finding(
                    code=V2FindingCode.SHAPE_MISMATCH,
                    detail=f"{key} must have shape {expected_shape}",
                )
            )
    dtype_expectations = {
        "active": "int32",
        "arrivals": "int32",
        "done": "int32",
        "lat_sum": "float32",
        "n_local": "int32",
        "n_v2i": "int32",
        "n_v2v": "int32",
        "rsu_busy_ms": "float32",
        "rsu_load": "int32",
        "slot_is_ev": "bool",
        "slot_tier": "int8",
        "times": "float32",
        "veh_action": "int8",
        "veh_best_rsu": "int16",
        "veh_best_v2v": "int16",
        "veh_done": "int16",
        "veh_k": "int8",
        "veh_queue_ms": "float32",
    }
    for key, expected_dtype in sorted(dtype_expectations.items()):
        if str(materialised[key].dtype) != expected_dtype:
            findings.append(
                V2Finding(
                    code=V2FindingCode.DTYPE_MISMATCH,
                    detail=f"{key} must have audited dtype {expected_dtype}",
                )
            )
    if findings:
        return _report("perstep", findings)
    if not bool(np.array_equal(materialised["times"], trace_arrays["times"])):
        findings.append(
            V2Finding(
                code=V2FindingCode.TIME_GRID_INVALID,
                detail="perstep times must equal the trace times exactly",
            )
        )
    mask_true = int(np.sum(np.asarray(trace_arrays["mask"]), dtype=np.int64))
    active_total = int(np.sum(materialised["active"], dtype=np.int64))
    if active_total != mask_true:
        findings.append(
            V2Finding(
                code=V2FindingCode.ACTIVE_MASK_MISMATCH,
                detail=(f"active total {active_total} must equal the trace mask count {mask_true}"),
            )
        )
    tier = materialised["slot_tier"]
    tier_ok = bool(np.all((tier >= TIER_MIN) & (tier <= TIER_MAX)))
    if not tier_ok:
        findings.append(
            V2Finding(
                code=V2FindingCode.TIER_RANGE_INVALID,
                detail=f"slot_tier values must be in {TIER_MIN}..{TIER_MAX}",
            )
        )
    action = materialised["veh_action"]
    veh_k = materialised["veh_k"]
    veh_done = materialised["veh_done"]
    nonnegative_counts = (
        "active",
        "arrivals",
        "done",
        "n_local",
        "n_v2i",
        "n_v2v",
        "rsu_load",
    )
    if not bool(
        np.all((action >= 0) & (action <= 2))
        and np.all((veh_k >= 0) & (veh_k <= MAX_TASKS_PER_VEHICLE_STEP))
        and np.all((veh_done >= 0) & (veh_done <= veh_k))
        and all(np.all(materialised[key] >= 0) for key in nonnegative_counts)
        and np.all(np.isfinite(materialised["lat_sum"]))
        and np.all(materialised["lat_sum"] >= 0)
        and np.all(np.isfinite(materialised["veh_queue_ms"]))
        and np.all(materialised["veh_queue_ms"] >= 0)
        and np.all(np.isfinite(materialised["rsu_busy_ms"]))
        and np.all(materialised["rsu_busy_ms"] >= 0)
    ):
        findings.append(
            V2Finding(
                code=V2FindingCode.VALUE_RANGE_INVALID,
                detail=(
                    "veh_action in 0..2, veh_k in 0..5, veh_done <= veh_k, and "
                    "queue/busy/load must be finite and non-negative"
                ),
            )
        )
    best_rsu = materialised["veh_best_rsu"]
    best_v2v = materialised["veh_best_v2v"]
    if not bool(
        np.all((best_rsu >= -1) & (best_rsu < rsu_count))
        and np.all((best_v2v >= -1) & (best_v2v < max_n))
    ):
        findings.append(
            V2Finding(
                code=V2FindingCode.TARGET_RANGE_INVALID,
                detail="targets must be -1 (no eligible target) or a valid index",
            )
        )
    columns: Any = np.arange(max_n, dtype=np.int64)[None, :]
    if not bool(np.all((best_v2v < 0) | (best_v2v != columns))):
        findings.append(
            V2Finding(
                code=V2FindingCode.SELF_V2V_TARGET,
                detail="an eligible V2V peer must never be the source slot",
            )
        )
    arrivals = int(np.sum(materialised["arrivals"], dtype=np.int64))
    done = int(np.sum(materialised["done"], dtype=np.int64))
    local = int(np.sum(materialised["n_local"], dtype=np.int64))
    v2i = int(np.sum(materialised["n_v2i"], dtype=np.int64))
    v2v = int(np.sum(materialised["n_v2v"], dtype=np.int64))
    vehicle_arrivals = int(np.sum(veh_k, dtype=np.int64))
    vehicle_done = int(np.sum(veh_done, dtype=np.int64))
    weighted = tuple(int(np.sum(veh_k * (action == code), dtype=np.int64)) for code in (0, 1, 2))
    if not (
        vehicle_arrivals == arrivals
        and vehicle_done == done
        and local + v2i + v2v == arrivals
        and weighted == (local, v2i, v2v)
    ):
        findings.append(
            V2Finding(
                code=V2FindingCode.INTERNAL_COUNTS_INCONSISTENT,
                detail=(
                    "per-step task, completion, and action counts must reconcile with "
                    "the per-vehicle arrays"
                ),
            )
        )
    if run_summary is not None and arrivals > 0 and tier_ok:
        summary_findings = _reconcile_run_summary(
            run_summary,
            arrivals=arrivals,
            done=done,
            latency_sum=float(np.sum(materialised["lat_sum"], dtype=np.float64)),
            local=local,
            v2i=v2i,
            v2v=v2v,
            ev_share=float(np.mean(materialised["slot_is_ev"])),
            tier_hist=[int(v) for v in np.bincount(tier, minlength=3)],
        )
        findings.extend(summary_findings)
    return _report("perstep", findings)


def _reconcile_run_summary(
    run_summary: Mapping[str, Any],
    *,
    arrivals: int,
    done: int,
    latency_sum: float,
    local: int,
    v2i: int,
    v2v: int,
    ev_share: float,
    tier_hist: list[int],
) -> list[V2Finding]:
    findings: list[V2Finding] = []
    missing = sorted(set(RUN_SUMMARY_REQUIRED_KEYS) - set(run_summary))
    if missing:
        findings.append(
            V2Finding(
                code=V2FindingCode.MISSING_KEYS,
                detail=f"run summary missing keys: {', '.join(missing)}",
            )
        )
        return findings
    if arrivals != int(run_summary["total_tasks"]):
        findings.append(
            V2Finding(
                code=V2FindingCode.AGGREGATE_MISMATCH,
                detail="per-step arrivals must equal the run summary total_tasks",
            )
        )
    checks = (
        ("completion", done / arrivals),
        ("p_local", local / arrivals),
        ("p_v2i", v2i / arrivals),
        ("p_v2v", v2v / arrivals),
    )
    for key, computed in checks:
        if not math.isclose(computed, float(run_summary[key]), rel_tol=1e-9, abs_tol=SHARE_ABS_TOL):
            findings.append(
                V2Finding(
                    code=V2FindingCode.AGGREGATE_MISMATCH,
                    detail=f"per-step {key} must reconcile with the run summary",
                )
            )
    # The audited evaluator computes this mean through JAX float32 while the
    # validator derives the exact boolean ratio. Permit only float32 rounding.
    if not math.isclose(
        ev_share,
        float(run_summary["fleet_ev_share"]),
        rel_tol=0,
        abs_tol=FLOAT32_SHARE_ABS_TOL,
    ):
        findings.append(
            V2Finding(
                code=V2FindingCode.AGGREGATE_MISMATCH,
                detail="per-step fleet_ev_share must reconcile with the run summary",
            )
        )
    if not math.isclose(
        latency_sum / arrivals,
        float(run_summary["avg_latency_ms_per_task"]),
        rel_tol=LATENCY_REL_TOL,
        abs_tol=LATENCY_ABS_TOL_MS,
    ):
        findings.append(
            V2Finding(
                code=V2FindingCode.AGGREGATE_MISMATCH,
                detail=(
                    "per-step latency must reconcile with the run summary within the "
                    "declared accumulation tolerance"
                ),
            )
        )
    hist = run_summary["fleet_tier_hist"]
    if list(hist) != tier_hist:
        findings.append(
            V2Finding(
                code=V2FindingCode.TIER_HIST_INVALID,
                detail="slot_tier histogram must equal the run summary fleet_tier_hist",
            )
        )
    shares = [float(run_summary[key]) for key in ("p_local", "p_v2i", "p_v2v")]
    if not math.isclose(sum(shares), 1.0, rel_tol=0, abs_tol=1e-6):
        findings.append(
            V2Finding(
                code=V2FindingCode.SHARE_SUM_INVALID,
                detail="run summary action shares must sum to 1",
            )
        )
    return findings


def validate_pertask_arrays(
    arrays: Mapping[str, Any],
    trace_arrays: Mapping[str, Any],
) -> ArtifactValidationReport:
    """Validate one per-task NPZ mapping against the audited four-key schema."""

    import numpy as np

    findings: list[V2Finding] = []
    trace_report = validate_trace_arrays(trace_arrays)
    if trace_report.status != "accepted":
        return _report(
            "pertask",
            [
                V2Finding(
                    code=V2FindingCode.UPSTREAM_ARTIFACT_INVALID,
                    detail="trace arrays must pass the VEC-02 trace contract first",
                )
            ],
        )
    if not _key_findings(set(arrays), PERTASK_KEYS, findings):
        return _report("pertask", findings)
    t_count = int(trace_arrays["T"])
    max_n = int(trace_arrays["maxN"])
    expected_shape = (t_count, MAX_TASKS_PER_VEHICLE_STEP, max_n)
    materialised = {key: np.asarray(arrays[key]) for key in PERTASK_KEYS}
    for key in PERTASK_KEYS:
        if materialised[key].shape != expected_shape:
            findings.append(
                V2Finding(
                    code=V2FindingCode.SHAPE_MISMATCH,
                    detail=f"{key} must have shape (T, {MAX_TASKS_PER_VEHICLE_STEP}, maxN)",
                )
            )
    dtype_expectations = {
        "task_active": "bool",
        "task_lat_ms": "float32",
        "task_met": "bool",
        "task_type": "int8",
    }
    for key, expected_dtype in sorted(dtype_expectations.items()):
        if str(materialised[key].dtype) != expected_dtype:
            findings.append(
                V2Finding(
                    code=V2FindingCode.DTYPE_MISMATCH,
                    detail=f"{key} must have audited dtype {expected_dtype}",
                )
            )
    if findings:
        return _report("pertask", findings)
    task_type = materialised["task_type"]
    task_active = materialised["task_active"]
    task_met = materialised["task_met"]
    task_lat = materialised["task_lat_ms"]
    if not bool(np.all((task_type[task_active] >= 0) & (task_type[task_active] <= 2))):
        findings.append(
            V2Finding(
                code=V2FindingCode.VALUE_RANGE_INVALID,
                detail="active task_type codes must be 0 (T1), 1 (T2), or 2 (T3)",
            )
        )
    if bool(np.any(task_met & ~task_active)):
        findings.append(
            V2Finding(
                code=V2FindingCode.VALUE_RANGE_INVALID,
                detail="task_met (deadline success) cannot be set on inactive cells",
            )
        )
    active_latency = task_lat[task_active]
    if active_latency.size and not bool(
        np.all(np.isfinite(active_latency)) and np.all(active_latency >= 0)
    ):
        findings.append(
            V2Finding(
                code=V2FindingCode.VALUE_RANGE_INVALID,
                detail="active task_lat_ms values must be finite and non-negative",
            )
        )
    return _report("pertask", findings)


def parse_occupancy_rows(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    scenario: str,
) -> tuple[list[OccupancySpan], list[V2Finding]]:
    """Parse audited-schema occupancy CSV content into typed spans."""

    findings: list[V2Finding] = []
    if tuple(header) != OCCUPANCY_HEADER:
        findings.append(
            V2Finding(
                code=V2FindingCode.HEADER_MISMATCH,
                detail=(
                    "occupancy header must be exactly "
                    f"{','.join(OCCUPANCY_HEADER)}; got {','.join(header)}"
                ),
            )
        )
        return [], findings
    spans: list[OccupancySpan] = []
    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(OCCUPANCY_HEADER):
            findings.append(
                V2Finding(
                    code=V2FindingCode.SPAN_BOUNDS_INVALID,
                    detail=f"row {row_number} must have exactly {len(OCCUPANCY_HEADER)} fields",
                )
            )
            continue
        try:
            spans.append(
                OccupancySpan(
                    sumo_vehicle_id=row[0],
                    slot=int(row[1]),
                    t_enter=int(row[2]),
                    t_exit=int(row[3]),
                    scenario=scenario,
                )
            )
        except (ValueError, TypeError) as exc:
            reason = " ".join(str(exc).split())[:300]
            findings.append(
                V2Finding(
                    code=V2FindingCode.SPAN_BOUNDS_INVALID,
                    detail=f"row {row_number} is not a valid inclusive span: {reason}",
                )
            )
    return spans, findings


class OccupancyReconciliationReport(ContractV2Model):
    """Deterministic consistency report for an audited-schema span set."""

    status: Literal["accepted", "rejected"]
    span_count: int = Field(ge=0)
    distinct_vehicles: int = Field(ge=0)
    distinct_slots: int = Field(ge=0)
    inclusive_visit_seconds: int = Field(ge=0)
    findings: list[V2Finding]


def reconcile_occupancy_spans(
    spans: Sequence[OccupancySpan],
    *,
    t_count: int | None = None,
    max_n: int | None = None,
    mask_true_count: int | None = None,
) -> OccupancyReconciliationReport:
    """Check inclusive spans for duplicates, overlap, bounds, and mask totals.

    Inclusive bounds mean spans sharing a boundary second DO conflict. When
    trace dimensions are supplied, slots and time indices must stay in range;
    when the trace mask count is supplied, total inclusive visit seconds must
    reconcile exactly. This validates span-set consistency only; the VEC-03
    identity join is out of scope.
    """

    findings: list[V2Finding] = []
    seen: dict[tuple[str, int, int, int, str], int] = {}
    for index, span in enumerate(spans):
        key = (span.sumo_vehicle_id, span.slot, span.t_enter, span.t_exit, span.scenario)
        if key in seen:
            findings.append(
                V2Finding(
                    code=V2FindingCode.DUPLICATE_SPAN,
                    detail=(
                        f"spans {seen[key]} and {index} duplicate vehicle "
                        f"{span.sumo_vehicle_id!r} slot {span.slot}"
                    ),
                )
            )
        else:
            seen[key] = index
        if max_n is not None and span.slot >= max_n:
            findings.append(
                V2Finding(
                    code=V2FindingCode.RANGE_OUT_OF_TRACE,
                    detail=f"span {index} slot {span.slot} exceeds maxN-1 = {max_n - 1}",
                )
            )
        if t_count is not None and span.t_exit >= t_count:
            findings.append(
                V2Finding(
                    code=V2FindingCode.RANGE_OUT_OF_TRACE,
                    detail=f"span {index} t_exit {span.t_exit} exceeds T-1 = {t_count - 1}",
                )
            )
    for first_index in range(len(spans)):
        for second_index in range(first_index + 1, len(spans)):
            first = spans[first_index]
            second = spans[second_index]
            if first.scenario != second.scenario:
                continue
            overlap = first.t_enter <= second.t_exit and second.t_enter <= first.t_exit
            if not overlap:
                continue
            if first.slot == second.slot:
                findings.append(
                    V2Finding(
                        code=V2FindingCode.SLOT_OVERLAP,
                        detail=(
                            f"slot {first.slot} hosts spans {first_index} and "
                            f"{second_index} in the same inclusive second"
                        ),
                    )
                )
            if first.sumo_vehicle_id == second.sumo_vehicle_id and first.slot != second.slot:
                findings.append(
                    V2Finding(
                        code=V2FindingCode.VEHICLE_OVERLAP,
                        detail=(
                            f"vehicle {first.sumo_vehicle_id!r} occupies slots "
                            f"{first.slot} and {second.slot} in the same inclusive second"
                        ),
                    )
                )
    visit_seconds = sum(span.visit_seconds for span in spans)
    if mask_true_count is not None and visit_seconds != mask_true_count:
        findings.append(
            V2Finding(
                code=V2FindingCode.ACTIVE_MASK_MISMATCH,
                detail=(
                    f"inclusive visit seconds {visit_seconds} must equal the trace "
                    f"mask count {mask_true_count}"
                ),
            )
        )
    ordered = sorted(findings, key=lambda finding: (finding.code.value, finding.detail))
    return OccupancyReconciliationReport(
        status="accepted" if not ordered else "rejected",
        span_count=len(spans),
        distinct_vehicles=len({span.sumo_vehicle_id for span in spans}),
        distinct_slots=len({span.slot for span in spans}),
        inclusive_visit_seconds=visit_seconds,
        findings=ordered,
    )
