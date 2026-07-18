"""Models for the read-only TOS Data package integration."""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.domain.enums import TaskClass
from traffictwin.metrics.results import JsonScalar

TOS_ADAPTER_VERSION = "0.2.0"
TOS_EXPECTED_ENGINE_VERSION = "v2_post_nrsus_fix"
TOS_SOURCE_METRIC_VERSION = "tos-source-summary-v2_post_nrsus_fix-1.0"
TOS_VEC_ENV_EVIDENCE_COMMIT = "e98441196270b8fd4cc0eede892df4a0053b2185"
TOS_SUMO_VERSION = "1.27.0"


class TosFindingSeverity(StrEnum):
    """Severity for package-specific validation findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TosValidationStatus(StrEnum):
    """Overall package validation status."""

    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    REJECTED = "rejected"


class TosEvaluationRun(BaseModel):
    """One row from ``evals/eval_results_master.csv``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    campaign: str = Field(min_length=1)
    cell: str = Field(min_length=1)
    eval_fleet: str = Field(min_length=1)
    fleet_seed: int = Field(ge=0)
    actor: str = Field(min_length=1)
    obs_variant: str = Field(min_length=1)
    completion: float
    t1_completion: float
    t2_completion: float
    t3_completion: float
    avg_energy_j_per_task: float = Field(ge=0)
    avg_latency_ms_per_task: float = Field(ge=0)
    p_local: float
    p_v2i: float
    p_v2v: float
    fleet_ev_share: float
    duration_s: int = Field(alias="T", gt=0)
    max_vehicle_slots: int = Field(alias="maxN", gt=0)
    trace: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    source_file: str = "evals/eval_results_master.csv"
    source_row: int = Field(ge=2)

    @field_validator(
        "completion",
        "t1_completion",
        "t2_completion",
        "t3_completion",
        "p_local",
        "p_v2i",
        "p_v2v",
        "fleet_ev_share",
    )
    @classmethod
    def validate_fraction(cls, value: float) -> float:
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("fraction must be finite and between 0 and 1")
        return value

    @model_validator(mode="after")
    def validate_action_shares(self) -> Self:
        total = self.p_local + self.p_v2i + self.p_v2v
        if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-6):
            raise ValueError(f"action shares must sum to 1; got {total:.9f}")
        return self

    @property
    def source_key(self) -> str:
        """Return the unabbreviated source lookup key for the evaluation row."""

        return f"{self.campaign}_{self.eval_fleet}_{self.cell}_fs{self.fleet_seed}"

    @property
    def run_id(self) -> str:
        """Return a stable TrafficTwin run identifier."""

        return f"tos:{self.campaign}:{self.cell}:{self.eval_fleet}:fs{self.fleet_seed}"

    @property
    def experiment_id(self) -> str:
        """Return a stable experiment grouping for cell and evaluation fleet."""

        return f"tos:{self.cell}:{self.eval_fleet}"

    @property
    def seed_id(self) -> str:
        """Return a stable source-scenario reference, not a fabricated seed snapshot."""

        return f"tos-seed:{self.cell}:{self.eval_fleet}"


class TosSummary(BaseModel):
    """One instrumented-run JSON summary."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    trace: str
    actor: str
    model: str
    duration_s: int = Field(alias="T", gt=0)
    max_vehicle_slots: int = Field(alias="maxN", gt=0)
    rsu_max_concurrent: int = Field(gt=0)
    fleet: str
    fleet_seed: int = Field(ge=0)
    obs_variant: str
    fleet_ev_share: float = Field(ge=0, le=1)
    fleet_tier_hist: list[int]
    completion: float = Field(ge=0, le=1)
    t1_completion: float = Field(ge=0, le=1)
    t2_completion: float = Field(ge=0, le=1)
    t3_completion: float = Field(ge=0, le=1)
    avg_energy_j_per_task: float = Field(ge=0)
    avg_latency_ms_per_task: float = Field(ge=0)
    p_local: float = Field(ge=0, le=1)
    p_v2i: float = Field(ge=0, le=1)
    p_v2v: float = Field(ge=0, le=1)
    t1_share: float = Field(ge=0, le=1)
    t2_share: float = Field(ge=0, le=1)
    t3_share: float = Field(ge=0, le=1)
    total_tasks: float = Field(ge=0)
    wall_s: float = Field(ge=0)


class NpzArrayHeader(BaseModel):
    """NPY member metadata read without loading its array payload."""

    model_config = ConfigDict(extra="forbid")

    name: str
    shape: list[int]
    dtype: str
    fortran_order: bool
    uncompressed_bytes: int = Field(ge=0)


class TosPackageInventory(BaseModel):
    """Counts of artifact types in a TOS Data package."""

    model_config = ConfigDict(extra="forbid")

    evaluation_rows: int = Field(ge=0)
    training_csv_files: int = Field(ge=0)
    training_summary_files: int = Field(ge=0)
    perstep_files: int = Field(ge=0)
    pertask_files: int = Field(ge=0)
    instrumented_summary_files: int = Field(ge=0)
    trace_files: int = Field(ge=0)
    training_record_files: int = Field(ge=0)


class TosValidationFinding(BaseModel):
    """Machine-readable TOS package validation finding."""

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: TosFindingSeverity
    message: str
    file: str | None = None
    field: str | None = None
    row: int | None = Field(default=None, ge=1)
    blocks_import: bool = False
    affected_capabilities: list[str] = Field(default_factory=list)


class TosIntegrationCapabilities(BaseModel):
    """Evidenced read-only features of this package adapter."""

    model_config = ConfigDict(extra="forbid")

    evaluation_summary_import: bool = True
    instrumented_historical_replay: bool = True
    per_task_showcase_inspection: bool = True
    trace_units_confirmed: bool = True
    rsu_state_semantics_confirmed: bool = True
    task_decision_join: bool = True
    load_pressure_inspection: bool = True
    source_evaluation_contract_documented: bool = True
    instrumented_writer_reproducible: bool = False
    direct_launch: bool = False
    asynchronous_launch: bool = False
    standard_bundle_conversion: bool = False
    canonical_task_conversion: bool = False
    infrastructure_metric_mapping: bool = False
    trip_metrics: bool = False


class TosValidationReport(BaseModel):
    """Read-only package inspection and import-readiness report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    adapter_version: str = TOS_ADAPTER_VERSION
    status: TosValidationStatus
    may_import_summaries: bool
    package_fingerprint: str | None
    package_commit: str | None
    semantics_source_commit: str = TOS_VEC_ENV_EVIDENCE_COMMIT
    engine_versions: list[str]
    inventory: TosPackageInventory
    findings: list[TosValidationFinding]
    capabilities: TosIntegrationCapabilities = Field(default_factory=TosIntegrationCapabilities)
    inspected_at: datetime

    def to_json(self) -> str:
        """Return a formatted machine-readable report."""

        return self.model_dump_json(indent=2)


class TosReplayPoint(BaseModel):
    """One documented per-second aggregate replay point."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    timestamp_s: float
    arrivals: int = Field(ge=0)
    deadline_met: int = Field(ge=0)
    latency_sum_ms: float = Field(ge=0)
    active_vehicle_slots: int = Field(ge=0)
    local_decisions: int = Field(ge=0)
    v2i_decisions: int = Field(ge=0)
    v2v_decisions: int = Field(ge=0)


class TosVehicleSlotState(BaseModel):
    """Time-local trace state for one padded vehicle slot."""

    model_config = ConfigDict(extra="forbid")

    slot_reference: str
    slot_index: int = Field(ge=0)
    position_x_source_units: float
    position_y_source_units: float
    speed_source_units: float = Field(ge=0)
    position_unit: str = "m"
    speed_unit: str = "m/s"
    identity_scope: str = "time_local_recycled_slot"
    action: str | None = None
    arrivals: int | None = Field(default=None, ge=0)
    deadline_met: int | None = Field(default=None, ge=0)
    queue_delay_ms: float | None = Field(default=None, ge=0)


class TosRsuSourceState(BaseModel):
    """Source RSU state with code-evidenced semantics."""

    model_config = ConfigDict(extra="forbid")

    rsu_reference: str
    rsu_index: int = Field(ge=0)
    position_x_source_units: float
    position_y_source_units: float
    position_unit: str = "m"
    rsu_load_source_value: int = Field(ge=0)
    rsu_busy_ms_source_value: float = Field(ge=0)
    rsu_max_concurrent_source_value: int = Field(gt=0)
    load_pressure_fraction: float = Field(ge=0, le=1)
    load_semantics: str = "in_flight_task_count"
    busy_semantics: str = "remaining_compute_backlog_ms"
    capacity_semantics: str = "maximum_concurrent_in_flight_tasks"
    pressure_semantics: str = "in_flight_tasks_divided_by_maximum_concurrent_tasks"
    semantics_status: str = "confirmed_from_vec_env_source"


class TosRsuReplayPoint(BaseModel):
    """One interpreted per-RSU source point for historical replay."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    timestamp_s: float
    rsu_reference: str
    rsu_index: int = Field(ge=0)
    active_task_count: int = Field(ge=0)
    remaining_compute_backlog_ms: float = Field(ge=0)
    max_concurrent_tasks: int = Field(gt=0)
    concurrency_pressure_fraction: float = Field(ge=0, le=1)
    source_file: str
    semantics_evidence_commit: str = TOS_VEC_ENV_EVIDENCE_COMMIT


class TosReplayFrame(BaseModel):
    """A bounded replay frame joined by timestamp and vehicle-slot index."""

    model_config = ConfigDict(extra="forbid")

    run_key: str
    source_file: str
    trace_file: str
    point: TosReplayPoint
    vehicles: list[TosVehicleSlotState]
    rsus: list[TosRsuSourceState]
    total_active_vehicle_slots: int = Field(ge=0)
    truncated: bool
    semantics_evidence_commit: str = TOS_VEC_ENV_EVIDENCE_COMMIT
    warnings: list[str] = Field(default_factory=list)


class TosTaskObservation(BaseModel):
    """One active per-task array entry, kept distinct from canonical TaskRecord."""

    model_config = ConfigDict(extra="forbid")

    task_reference: str
    run_key: str
    time_index: int = Field(ge=0)
    task_slot: int = Field(ge=0)
    vehicle_slot: int = Field(ge=0)
    arrival_time_s: float
    task_class: TaskClass
    decision: str
    deadline_met: bool
    latency_ms: float = Field(ge=0)
    deadline_ms: float = Field(gt=0)
    source_file: str
    source_index: str
    decision_source_file: str
    decision_source_index: str
    vehicle_identity_scope: str = "time_local_recycled_slot"
    outcome_semantics: str = "modelled_latency_within_class_deadline"


class TosTaskSample(BaseModel):
    """Bounded read-only sample from a per-task showcase file."""

    model_config = ConfigDict(extra="forbid")

    run_key: str
    source_file: str
    observations: list[TosTaskObservation]
    total_active_entries: int = Field(ge=0)
    sample_limit: int = Field(gt=0)
    truncated: bool
    deadline_consistency_verified: bool
    warnings: list[str] = Field(default_factory=list)


class TosImportSummary(BaseModel):
    """Outcome of importing evaluation summaries into the metadata registry."""

    model_config = ConfigDict(extra="forbid")

    package_fingerprint: str
    registry_reference: str
    experiments_created: int = Field(ge=0)
    experiments_existing: int = Field(ge=0)
    runs_created: int = Field(ge=0)
    runs_existing: int = Field(ge=0)
    metric_collections_stored: int = Field(ge=0)
    evidence_packs_stored: int = Field(ge=0)
    run_ids: list[str]
    warnings: list[str] = Field(default_factory=list)


def action_label(value: int) -> str | None:
    """Map an evidenced source action code to a display label."""

    return {0: "local", 1: "v2i", 2: "v2v"}.get(value)


def task_class_from_code(value: int) -> TaskClass:
    """Map the empirically verified task-type encoding."""

    return {0: TaskClass.T1, 1: TaskClass.T2, 2: TaskClass.T3}.get(value, TaskClass.UNKNOWN)


def task_deadline_ms(task_class: TaskClass) -> float:
    """Return package-documented task deadlines."""

    return 500.0 if task_class is TaskClass.T2 else 100.0


def scalar_attributes(**values: JsonScalar) -> dict[str, JsonScalar]:
    """Return a typed scalar attribute mapping."""

    return values
