"""Versioned scientific-admission decisions for audited VEC evidence (VEC-09)."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.evidence.pack import EvidencePack
from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.metrics.results import MetricStatus


class VecScienceModel(BaseModel):
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


class VecMetricAdmissionStatus(StrEnum):
    ADMITTED_EXISTING = "admitted_existing"
    ADMITTED_SOURCE_SPECIFIC = "admitted_source_specific"
    UNAVAILABLE = "unavailable"


class VecRuleReadinessStatus(StrEnum):
    READY = "ready"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


class VecMetricAdmissionDecision(VecScienceModel):
    metric_key: str
    status: VecMetricAdmissionStatus
    evidence: tuple[str, ...]
    semantics: str
    blocker: str | None = None

    @model_validator(mode="after")
    def require_blocker_only_when_unavailable(self) -> Self:
        if (self.status is VecMetricAdmissionStatus.UNAVAILABLE) != (self.blocker is not None):
            raise ValueError("only unavailable metrics must carry a blocker")
        return self


class VecRuleReadiness(VecScienceModel):
    rule_id: str
    status: VecRuleReadinessStatus
    admitted_evidence: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    threshold_evaluated: Literal[False] = False
    finding_emitted: Literal[False] = False
    rationale: str


class VecScientificAdmissionReport(VecScienceModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["accepted"] = "accepted"
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    run_label: str
    scenario: str
    task_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    trip_join_report_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reproduction_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    reproduction_grade: Literal["numerically_equivalent"] = "numerically_equivalent"
    metric_decisions: tuple[VecMetricAdmissionDecision, ...]
    rule_readiness: tuple[VecRuleReadiness, ...]
    evidence_pack: EvidencePack
    thresholds_calibrated_on_evaluation: Literal[False] = False
    per_task_energy_available: Literal[False] = False
    physical_completion_available: Literal[False] = False
    transfer_confirmation_available: Literal[False] = False
    canonical_rsu_utilisation_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_catalogues(self) -> Self:
        metric_keys = [item.metric_key for item in self.metric_decisions]
        if metric_keys != sorted(set(metric_keys)):
            raise ValueError("metric decisions must be unique and sorted")
        metrics = self.evidence_pack.metric_collection.by_key()
        if set(metric_keys) != set(metrics):
            raise ValueError("metric decisions must exactly cover the EvidencePack metrics")
        for decision in self.metric_decisions:
            unavailable = metrics[decision.metric_key].status is MetricStatus.UNAVAILABLE
            if unavailable != (decision.status is VecMetricAdmissionStatus.UNAVAILABLE):
                raise ValueError("metric admission status must match the EvidencePack metric")
        rule_ids = [item.rule_id for item in self.rule_readiness]
        if rule_ids != sorted(set(rule_ids)):
            raise ValueError("rule readiness entries must be unique and sorted")
        return self


class VecScientificAdmissionContract(VecScienceModel):
    schema_version: Literal["1.0"] = "1.0"
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    admitted_existing_metrics: tuple[str, ...] = (
        "task.decision_share.local",
        "task.decision_share.unknown",
        "task.decision_share.v2i",
        "task.decision_share.v2v",
        "task.generated.count",
        "task.latency.mean_ms",
        "task.offload.rate",
        "trip.duration.count",
        "trip.duration.max_s",
        "trip.duration.mean_s",
        "trip.duration.min_s",
        "trip.duration.p50_s",
        "trip.duration.p95_s",
    )
    admitted_source_specific_metrics: tuple[str, ...] = (
        "tos.operational.slot_tier.deadline_success.max_gap",
        "tos.task.deadline_success.rate",
        "tos.task.deadline_success.rate_by_class",
        "tos.task.deadline_success.rate_by_slot_tier",
        "tos.task.no_eligible_target.rate_among_offload",
    )
    mandatory_unavailable_families: tuple[str, ...] = (
        "physical task completion",
        "per-task energy and energy-delay product",
        "canonical CPU utilisation and queue length",
        "execution-target or transfer-confirmed RSU metrics",
        "protected-attribute fairness",
        "trip completion metrics over the occupancy cohort",
    )
    rule_scope: tuple[str, ...] = ("R1", "R2", "R6", "R7")
    evaluation_policy: str = (
        "No diagnostic threshold is calibrated or evaluated on the run used for admission."
    )


def vec_scientific_admission_contract() -> VecScientificAdmissionContract:
    return VecScientificAdmissionContract()
