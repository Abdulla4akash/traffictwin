"""Versioned models for read-only analysis of evidenced TOS artifacts."""

from __future__ import annotations

import math
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TOS_ANALYSIS_VERSION = "1.0"


class TosAnalysisMeasureDefinition(BaseModel):
    """Definition of one source-specific evaluation measure."""

    model_config = ConfigDict(extra="forbid")

    key: str
    human_name: str
    description: str
    unit: str
    source_fields: list[str]
    higher_is_better: bool | None = None
    limitations: list[str] = Field(default_factory=list)


class TosDescriptiveStatistics(BaseModel):
    """Deterministic descriptive statistics with no implicit NaN values."""

    model_config = ConfigDict(extra="forbid")

    n: int = Field(ge=0)
    mean: float | None = None
    sample_sd: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    p50: float | None = None

    @field_validator("mean", "sample_sd", "minimum", "maximum", "p50")
    @classmethod
    def finite_when_present(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("statistics must be finite when present")
        return value


class TosAggregateCell(BaseModel):
    """One campaign/cell/fleet aggregate over compatible fleet seeds."""

    model_config = ConfigDict(extra="forbid")

    campaign: str
    cell: str
    evaluation_fleet: str
    measure_key: str
    values_by_fleet_seed: dict[int, float]
    statistics: TosDescriptiveStatistics
    source_rows: list[int]
    engine_versions: list[str]


class TosEvaluationMatrix(BaseModel):
    """Source evaluation matrix used by the UI, reports, and static atlas."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    analysis_version: str = TOS_ANALYSIS_VERSION
    measure: TosAnalysisMeasureDefinition
    evaluation_fleet: str
    campaigns: list[str]
    cells: list[str]
    entries: list[TosAggregateCell]
    package_fingerprint: str
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return deterministic, finite JSON."""

        return self.model_dump_json(indent=2)


class TosPairedObservation(BaseModel):
    """One common-fleet-seed variation-minus-baseline observation."""

    model_config = ConfigDict(extra="forbid")

    fleet_seed: int = Field(ge=0)
    baseline: float
    variation: float
    absolute_delta: float
    relative_delta: float | None
    relative_delta_reason: str | None = None
    baseline_source_row: int = Field(ge=2)
    variation_source_row: int = Field(ge=2)

    @field_validator("baseline", "variation", "absolute_delta", "relative_delta")
    @classmethod
    def finite_when_present(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("comparison values must be finite")
        return value


class TosPairedMeasureComparison(BaseModel):
    """Paired comparison for one measure and one source scenario cell."""

    model_config = ConfigDict(extra="forbid")

    measure: TosAnalysisMeasureDefinition
    cell: str
    evaluation_fleet: str
    baseline_campaign: str
    variation_campaign: str
    baseline_statistics: TosDescriptiveStatistics
    variation_statistics: TosDescriptiveStatistics
    paired_difference_statistics: TosDescriptiveStatistics
    observations: list[TosPairedObservation]
    unmatched_baseline_fleet_seeds: list[int] = Field(default_factory=list)
    unmatched_variation_fleet_seeds: list[int] = Field(default_factory=list)
    compatibility_findings: list[str] = Field(default_factory=list)


class TosCampaignComparisonReport(BaseModel):
    """Versioned paired campaign comparison across source scenario cells."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    analysis_version: str = TOS_ANALYSIS_VERSION
    baseline_campaign: str
    variation_campaign: str
    evaluation_fleet: str
    comparisons: list[TosPairedMeasureComparison]
    package_fingerprint: str
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return deterministic, finite JSON."""

        return self.model_dump_json(indent=2)


class TosEvaluationDomain(StrEnum):
    """Source-documented relationship between training and evaluation mobility."""

    IN_DOMAIN = "in_domain"
    HELD_OUT = "held_out"
    UNKNOWN = "unknown"


class TosGeneralisationEntry(BaseModel):
    """One source-evidenced campaign/cell domain classification."""

    model_config = ConfigDict(extra="forbid")

    campaign: str
    cell: str
    evaluation_domain: TosEvaluationDomain
    evidence_file: str | None = None
    evidence_statement: str
    limitations: list[str] = Field(default_factory=list)


class TosGeneralisationMatrix(BaseModel):
    """Domain labels kept separate from measured performance values."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    analysis_version: str = TOS_ANALYSIS_VERSION
    entries: list[TosGeneralisationEntry]
    warnings: list[str] = Field(default_factory=list)


class TosTrainingPoint(BaseModel):
    """One row from a source training-history CSV."""

    model_config = ConfigDict(extra="forbid")

    update: int = Field(ge=0)
    env_step: int = Field(ge=0)
    mean_return: float | None = None
    mean_completion: float | None = None
    p_local: float | None = None
    p_v2i: float | None = None
    p_v2v: float | None = None
    avg_energy_j: float | None = Field(default=None, ge=0)
    avg_latency_ms: float | None = Field(default=None, ge=0)
    type_1_completion: float | None = None
    type_2_completion: float | None = None
    type_3_completion: float | None = None
    elapsed_s: float = Field(ge=0)
    sps: float = Field(ge=0)
    source_file: str
    source_row: int = Field(ge=2)

    @field_validator(
        "mean_return",
        "mean_completion",
        "p_local",
        "p_v2i",
        "p_v2v",
        "avg_energy_j",
        "avg_latency_ms",
        "type_1_completion",
        "type_2_completion",
        "type_3_completion",
    )
    @classmethod
    def finite_when_present(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("training values must be finite when present")
        return value

    @field_validator(
        "mean_completion",
        "p_local",
        "p_v2i",
        "p_v2v",
        "type_1_completion",
        "type_2_completion",
        "type_3_completion",
    )
    @classmethod
    def fractions_when_present(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("training fractions must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def action_shares_when_present(self) -> Self:
        values = (self.p_local, self.p_v2i, self.p_v2v)
        if all(value is not None for value in values):
            total = sum(float(value) for value in values if value is not None)
            if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-3):
                raise ValueError("training action shares must sum to 1 within source rounding")
        return self


class TosGreedyEvaluationSummary(BaseModel):
    """One source greedy-evaluation JSON summary."""

    model_config = ConfigDict(extra="forbid")

    mean_completion: float = Field(ge=0, le=1)
    std_completion: float = Field(ge=0)
    type_1_completion: float = Field(ge=0, le=1)
    type_2_completion: float = Field(ge=0, le=1)
    type_3_completion: float = Field(ge=0, le=1)
    p_local: float = Field(ge=0, le=1)
    p_v2i: float = Field(ge=0, le=1)
    p_v2v: float = Field(ge=0, le=1)
    avg_energy_j: float = Field(ge=0)
    avg_latency_ms: float = Field(ge=0)
    n_eval_episodes: int = Field(gt=0)
    elapsed_s: float = Field(ge=0)
    source_file: str


class TosTrainingRunSummary(BaseModel):
    """Small index entry for one source training history."""

    model_config = ConfigDict(extra="forbid")

    training_id: str
    policy_label: str
    training_seed: int | None = Field(default=None, ge=0)
    source_file: str
    point_count: int = Field(ge=0)
    measured_point_count: int = Field(ge=0)
    warmup_unavailable_count: int = Field(ge=0)
    final_env_step: int = Field(ge=0)
    final_mean_completion: float | None = None
    greedy_summary_file: str | None = None
    machine_record_file: str | None = None
    warnings: list[str] = Field(default_factory=list)


class TosTrainingRun(BaseModel):
    """Bounded source training history with optional greedy evaluation."""

    model_config = ConfigDict(extra="forbid")

    summary: TosTrainingRunSummary
    points: list[TosTrainingPoint]
    greedy_evaluation: TosGreedyEvaluationSummary | None = None
    downsampled: bool = False


class TosTraceProfilePoint(BaseModel):
    """One bounded processed-FCD profile point."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    timestamp_s: float
    active_vehicle_slots: int = Field(ge=0)
    mean_speed_mps: float | None = Field(default=None, ge=0)
    p50_speed_mps: float | None = Field(default=None, ge=0)


class TosTraceSummary(BaseModel):
    """Descriptive profile of one processed SUMO FCD trace."""

    model_config = ConfigDict(extra="forbid")

    trace_file: str
    observation_count: int = Field(ge=0)
    timeline_point_count: int = Field(ge=0)
    first_timestamp_s: float
    last_timestamp_s: float
    duration_s: float = Field(ge=0)
    active_vehicle_slots: TosDescriptiveStatistics
    speed_mps: TosDescriptiveStatistics
    minimum_x_m: float | None = None
    maximum_x_m: float | None = None
    minimum_y_m: float | None = None
    maximum_y_m: float | None = None
    profile: list[TosTraceProfilePoint]
    warnings: list[str] = Field(default_factory=list)


class TosRsuSourceSummary(BaseModel):
    """Descriptive source-state summary for one RSU."""

    model_config = ConfigDict(extra="forbid")

    rsu_reference: str
    observation_count: int = Field(ge=0)
    active_task_count: TosDescriptiveStatistics
    concurrency_pressure_fraction: TosDescriptiveStatistics
    remaining_compute_backlog_ms: TosDescriptiveStatistics
    peak_pressure_timestamp_s: float
    peak_backlog_timestamp_s: float


class TosRsuRunSummary(BaseModel):
    """RSU source-state summaries kept outside canonical infrastructure metrics."""

    model_config = ConfigDict(extra="forbid")

    run_key: str
    source_file: str
    maximum_concurrent_tasks: int = Field(gt=0)
    rsus: list[TosRsuSourceSummary]
    warnings: list[str] = Field(default_factory=list)


class TosTaskOutcomeBreakdown(BaseModel):
    """Task outcome and latency summary for one class or decision group."""

    model_config = ConfigDict(extra="forbid")

    group: str
    task_count: int = Field(ge=0)
    deadline_success_count: int = Field(ge=0)
    deadline_success_rate: float | None = Field(default=None, ge=0, le=1)
    latency_ms: TosDescriptiveStatistics


class TosTaskOutcomeSummary(BaseModel):
    """Exact aggregate summary over one per-task showcase array."""

    model_config = ConfigDict(extra="forbid")

    run_key: str
    source_file: str
    decision_source_file: str
    task_count: int = Field(ge=0)
    deadline_success_count: int = Field(ge=0)
    deadline_success_rate: float | None = Field(default=None, ge=0, le=1)
    latency_ms: TosDescriptiveStatistics
    by_task_class: list[TosTaskOutcomeBreakdown]
    by_decision: list[TosTaskOutcomeBreakdown]
    deadline_consistency_verified: bool
    warnings: list[str] = Field(default_factory=list)


class TosAuditStatus(StrEnum):
    """Status of one reproducibility audit check."""

    PASS = "pass"  # noqa: S105 - audit status, not a credential
    INFORMATION = "information"
    WARNING = "warning"
    BLOCKED = "blocked"


class TosAuditCheck(BaseModel):
    """One reproducibility or artifact-coverage check."""

    model_config = ConfigDict(extra="forbid")

    code: str
    status: TosAuditStatus
    message: str
    evidence: list[str] = Field(default_factory=list)
    affected_capabilities: list[str] = Field(default_factory=list)


class TosReproducibilityAudit(BaseModel):
    """Read-only audit linking package artifacts and known missing dependencies."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    analysis_version: str = TOS_ANALYSIS_VERSION
    package_fingerprint: str
    package_commit: str | None
    semantics_source_commit: str
    evaluation_run_count: int = Field(ge=0)
    unique_actor_reference_count: int = Field(ge=0)
    actor_checkpoint_file_count: int = Field(ge=0)
    actor_training_history_match_count: int = Field(ge=0)
    training_history_count: int = Field(ge=0)
    training_summary_count: int = Field(ge=0)
    instrumented_run_count: int = Field(ge=0)
    per_task_run_count: int = Field(ge=0)
    trace_count: int = Field(ge=0)
    checks: list[TosAuditCheck]
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return deterministic, finite JSON."""

        return self.model_dump_json(indent=2)
