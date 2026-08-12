"""Multi-Objective Trade-Off Explorer — deterministic Pareto/constraint explorer.

This module provides a within-study multi-objective comparison across compatible
policy arms. It computes per-arm feasibility, constraint violations, Pareto
dominance, and a descriptive non-dominated frontier without inventing a single
winner. No weighting or normalisation is applied silently and no numeric
aggregate is produced for an incompatible metric.

Evidence and authority boundaries are explicit: unknown compatibility remains
unavailable unless the input already carries an authoritative compatible
contract from main, and unadmitted evidence fails closed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import pathlib
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.metrics.results import JsonScalar

TRADEOFF_SCHEMA_VERSION: Literal["1.0"] = "1.0"
TRADEOFF_REPORT_VERSION: Literal["1.0"] = "1.0"

MIN_TRADEOFF_ARMS = 2
MAX_TRADEOFF_ARMS = 8
MIN_TRADEOFF_METRICS = 2
MAX_TRADEOFF_METRICS = 6

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TradeoffStatus(StrEnum):
    """Availability and feasibility status."""

    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"


class TradeoffDirection(StrEnum):
    """Optimisation direction for a metric (no implicit weight)."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class TradeoffConstraintOperator(StrEnum):
    """Operator for a hard constraint."""

    LE = "<="
    GE = ">="
    LT = "<"
    GT = ">"


class TradeoffEvidenceMode(StrEnum):
    """Evidence mode."""

    SYNTHETIC_DEMONSTRATION = "synthetic_demonstration"
    IMPORTED = "imported"
    HISTORICAL_OBSERVATION = "historical_observation"
    ADMITTED_RESEARCH = "admitted_research"
    UNADMITTED_RESEARCH = "unadmitted_research"
    UNAVAILABLE = "unavailable"


class TradeoffAdmissionState(StrEnum):
    """Admission state."""

    ADMITTED = "admitted"
    UNADMITTED = "unadmitted"
    SYNTHETIC_DEMONSTRATION = "synthetic_demonstration"
    REJECTED = "rejected"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"


class TradeoffDenominator(StrEnum):
    """Denominator for metric attainment."""

    OFFERED_TASKS = "offered_tasks"
    ADMITTED_TASKS = "admitted_tasks"
    COMPLETED_TASKS = "completed_tasks"
    REPLICATION = "replication"
    UNKNOWN = "unknown"


class TradeoffCompatibilityStatus(StrEnum):
    """Compatibility outcome."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TradeoffConstraint(BaseModel):
    """Hard constraint on a metric (optional per metric spec)."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str = Field(min_length=1, max_length=256)
    operator: TradeoffConstraintOperator
    threshold: float
    reason: str = Field(default="", max_length=512)

    def is_violated(self, value: float | None) -> bool | None:
        """Return True if violated, False if satisfied, None if unavailable."""
        if value is None:
            return None
        if self.operator == TradeoffConstraintOperator.LE:
            return not (value <= self.threshold)
        if self.operator == TradeoffConstraintOperator.GE:
            return not (value >= self.threshold)
        if self.operator == TradeoffConstraintOperator.LT:
            return not (value < self.threshold)
        if self.operator == TradeoffConstraintOperator.GT:
            return not (value > self.threshold)
        return None

    def describe(self) -> str:
        return f"{self.metric_key} {self.operator.value} {self.threshold:.6g}"


class TradeoffMetricSpec(BaseModel):
    """Typed metric specification — no implicit weight or normalisation."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str = Field(min_length=1, max_length=256)
    metric_version: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=64)
    denominator: TradeoffDenominator
    direction: TradeoffDirection
    hard_constraint: TradeoffConstraint | None = None
    description: str = Field(default="", max_length=512)
    per_replication_disclosed: bool = True

    @model_validator(mode="after")
    def validate_constraint_matches_key(self) -> TradeoffMetricSpec:
        if self.hard_constraint is not None and self.hard_constraint.metric_key != self.metric_key:
            raise ValueError("hard_constraint metric_key must match metric_spec metric_key")
        return self


class TradeoffObservation(BaseModel):
    """Per-arm observation for one metric (deterministic aggregate)."""

    model_config = ConfigDict(extra="forbid")

    arm_id: str = Field(min_length=1, max_length=128)
    metric_key: str = Field(min_length=1, max_length=256)
    metric_version: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=64)
    denominator: TradeoffDenominator
    value: float | None = None
    status: TradeoffStatus = TradeoffStatus.AVAILABLE
    per_replication_values: dict[str, float | None] = Field(default_factory=dict)
    replication_count: int = Field(ge=0, default=0)
    reason: str | None = Field(default=None, max_length=512)


class TradeoffArm(BaseModel):
    """One policy arm with observations for each declared metric."""

    model_config = ConfigDict(extra="forbid")

    arm_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=1024)
    strategy_type: str = Field(min_length=1, max_length=128, default="unknown")
    observations: list[TradeoffObservation] = Field(min_length=1)

    @field_validator("observations")
    @classmethod
    def validate_unique_metric_keys(
        cls, values: list[TradeoffObservation]
    ) -> list[TradeoffObservation]:
        seen: set[str] = set()
        for obs in values:
            if obs.metric_key in seen:
                raise ValueError(f"duplicate metric_key {obs.metric_key!r} in arm observations")
            seen.add(obs.metric_key)
        return values


class TradeoffStudy(BaseModel):
    """Validated multi-objective study with typed fingerprint identity."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = TRADEOFF_SCHEMA_VERSION
    study_id: str = Field(min_length=1, max_length=256)
    source_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    evidence_mode: TradeoffEvidenceMode = TradeoffEvidenceMode.SYNTHETIC_DEMONSTRATION
    admission_state: TradeoffAdmissionState = TradeoffAdmissionState.SYNTHETIC_DEMONSTRATION
    arms: list[TradeoffArm] = Field(min_length=MIN_TRADEOFF_ARMS, max_length=MAX_TRADEOFF_ARMS)
    metric_specs: list[TradeoffMetricSpec] = Field(
        min_length=MIN_TRADEOFF_METRICS, max_length=MAX_TRADEOFF_METRICS
    )
    matched_replication_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    generated_at: datetime | None = None

    @field_validator("arms")
    @classmethod
    def validate_unique_arm_ids(cls, values: list[TradeoffArm]) -> list[TradeoffArm]:
        seen: set[str] = set()
        for arm in values:
            if arm.arm_id in seen:
                raise ValueError(f"duplicate arm_id {arm.arm_id!r}")
            seen.add(arm.arm_id)
        return values

    @field_validator("metric_specs")
    @classmethod
    def validate_unique_metric_keys(
        cls, values: list[TradeoffMetricSpec]
    ) -> list[TradeoffMetricSpec]:
        seen: set[str] = set()
        for spec in values:
            if spec.metric_key in seen:
                raise ValueError(f"duplicate metric_key {spec.metric_key!r}")
            seen.add(spec.metric_key)
        return values

    @field_validator("matched_replication_ids")
    @classmethod
    def validate_sorted_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("matched_replication_ids must not contain duplicates")
        if values != sorted(values):
            raise ValueError("matched_replication_ids must be sorted")
        return values

    @model_validator(mode="after")
    def validate_study_invariants(self) -> TradeoffStudy:
        # Evidence/admission consistency
        if (
            self.evidence_mode == TradeoffEvidenceMode.SYNTHETIC_DEMONSTRATION
            and self.admission_state != TradeoffAdmissionState.SYNTHETIC_DEMONSTRATION
        ):
            raise ValueError(
                "synthetic_demonstration evidence_mode requires synthetic_demonstration admission_state"  # noqa: E501
            )
        if (
            self.admission_state == TradeoffAdmissionState.SYNTHETIC_DEMONSTRATION
            and self.evidence_mode != TradeoffEvidenceMode.SYNTHETIC_DEMONSTRATION
        ):
            raise ValueError(
                "synthetic_demonstration admission_state requires synthetic_demonstration evidence_mode"  # noqa: E501
            )
        if (
            self.evidence_mode == TradeoffEvidenceMode.ADMITTED_RESEARCH
            and self.admission_state != TradeoffAdmissionState.ADMITTED
        ):
            raise ValueError("admitted_research evidence_mode requires admitted admission_state")
        if (
            self.evidence_mode == TradeoffEvidenceMode.UNADMITTED_RESEARCH
            and self.admission_state != TradeoffAdmissionState.UNADMITTED
        ):
            raise ValueError(
                "unadmitted_research evidence_mode requires unadmitted admission_state"
            )

        # Observations must cover exactly declared metric_specs (allow missing as explicit unavailable)  # noqa: E501
        spec_keys = {s.metric_key for s in self.metric_specs}
        for arm in self.arms:
            obs_keys = {o.metric_key for o in arm.observations}
            # All spec keys must appear in observations; extra keys are not allowed
            if obs_keys != spec_keys:
                missing = spec_keys - obs_keys
                extra = obs_keys - spec_keys
                if missing:
                    raise ValueError(
                        f"arm {arm.arm_id!r} missing observations for {sorted(missing)!r}"
                    )
                if extra:
                    raise ValueError(
                        f"arm {arm.arm_id!r} has extra observations for {sorted(extra)!r}"
                    )
            # Each observation's version/unit/denominator should be consistent with spec where available  # noqa: E501
            # We allow observations to carry their own declared version but catalog is authoritative;  # noqa: E501
            # mismatch is signalled via compatibility later, not hard-fail here. Keep fail-closed only on structural.  # noqa: E501
        return self

    def canonical_payload(self) -> dict[str, Any]:
        arms_sorted = sorted(self.arms, key=lambda a: a.arm_id)
        specs_sorted = sorted(self.metric_specs, key=lambda s: s.metric_key)
        arms_payload = []
        for arm in arms_sorted:
            obs_sorted = sorted(arm.observations, key=lambda o: o.metric_key)
            arms_payload.append(
                {
                    "arm_id": arm.arm_id,
                    "description": arm.description,
                    "label": arm.label,
                    "observations": [
                        {
                            "arm_id": o.arm_id,
                            "denominator": o.denominator.value,
                            "metric_key": o.metric_key,
                            "metric_version": o.metric_version,
                            "per_replication_values": dict(
                                sorted(o.per_replication_values.items())
                            ),
                            "reason": o.reason,
                            "replication_count": o.replication_count,
                            "status": o.status.value,
                            "unit": o.unit,
                            "value": o.value,
                        }
                        for o in obs_sorted
                    ],
                    "strategy_type": arm.strategy_type,
                }
            )
        specs_payload = [s.model_dump(mode="json") for s in specs_sorted]
        # Sort provenance and limitations for determinism
        return {
            "admission_state": self.admission_state.value,
            "arms": arms_payload,
            "evidence_mode": self.evidence_mode.value,
            "limitations": sorted(self.limitations),
            "matched_replication_ids": sorted(self.matched_replication_ids),
            "metric_specs": specs_payload,
            "provenance": dict(sorted(self.provenance.items())),
            "schema_version": self.schema_version,
            "source_fingerprint": self.source_fingerprint,
            "study_id": self.study_id,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        payload = self.model_dump(mode="json")
        if payload.get("generated_at") is not None:
            payload["generated_at"] = None
        return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)


class TradeoffCompatibilityAudit(BaseModel):
    """Compatibility finding for one metric."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    status: TradeoffCompatibilityStatus
    finding: str = Field(default="")
    expected_version: str | None = None
    expected_unit: str | None = None
    expected_denominator: TradeoffDenominator | None = None
    versions: list[str] = Field(default_factory=list)
    unit: str | None = None
    denominator: TradeoffDenominator | None = None


class TradeoffFeasibility(BaseModel):
    """Per-arm feasibility including violations and missingness."""

    model_config = ConfigDict(extra="forbid")

    arm_id: str
    status: TradeoffStatus
    is_feasible: bool
    violations: list[TradeoffConstraint] = Field(default_factory=list)
    violation_messages: list[str] = Field(default_factory=list)
    unavailable_metrics: list[str] = Field(default_factory=list)
    incompatible_metrics: list[str] = Field(default_factory=list)
    reason: str = Field(default="")


class TradeoffDominance(BaseModel):
    """Dominance relationship between two arms under declared metrics."""

    model_config = ConfigDict(extra="forbid")

    dominator_arm_id: str
    dominated_arm_id: str
    dominates: bool
    comparisons: dict[str, str] = Field(default_factory=dict)
    reason: str = Field(default="")


class TradeoffFrontier(BaseModel):
    """Descriptive non-dominated frontier (feasible arms only)."""

    model_config = ConfigDict(extra="forbid")

    frontier_arm_ids: list[str] = Field(default_factory=list)
    dominated_arm_ids: list[str] = Field(default_factory=list)
    dominated_by: dict[str, list[str]] = Field(default_factory=dict)
    description: str = Field(
        default="descriptive frontier; non-dominated under declared metrics and feasible constraints"  # noqa: E501
    )
    all_feasible_arm_ids: list[str] = Field(default_factory=list)


class TradeoffFinding(BaseModel):
    """Typed finding for missing/incompatible/stability notices."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=128)
    metric_key: str | None = None
    arm_id: str | None = None
    message: str = Field(min_length=1, max_length=1024)
    severity: str = Field(default="info", max_length=32)


class TradeoffReport(BaseModel):
    """Deterministic trade-off report derived from a validated study."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = TRADEOFF_REPORT_VERSION
    study_id: str
    study_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_mode: TradeoffEvidenceMode
    admission_state: TradeoffAdmissionState
    metric_specs: list[TradeoffMetricSpec] = Field(default_factory=list)
    matched_replication_ids: list[str] = Field(default_factory=list)
    compatibility: list[TradeoffCompatibilityAudit] = Field(default_factory=list)
    feasibility: list[TradeoffFeasibility] = Field(default_factory=list)
    dominance: list[TradeoffDominance] = Field(default_factory=list)
    frontier: TradeoffFrontier = Field(default_factory=TradeoffFrontier)
    findings: list[TradeoffFinding] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    replication_stability: dict[str, float | None] = Field(default_factory=dict)
    sensitivity: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None
    report_fingerprint: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")

    def canonical_payload(self) -> dict[str, Any]:
        specs = sorted(self.metric_specs, key=lambda s: s.metric_key)
        compat = sorted(
            [c.model_dump(mode="json") for c in self.compatibility], key=lambda x: x["metric_key"]
        )
        feas = sorted(
            [f.model_dump(mode="json") for f in self.feasibility], key=lambda x: x["arm_id"]
        )
        dom = sorted(
            [d.model_dump(mode="json") for d in self.dominance],
            key=lambda x: (x["dominator_arm_id"], x["dominated_arm_id"]),
        )
        findings_sorted = sorted(
            [f.model_dump(mode="json") for f in self.findings],
            key=lambda x: (x["code"], x.get("arm_id") or "", x.get("metric_key") or ""),
        )
        return {
            "admission_state": self.admission_state.value,
            "compatibility": compat,
            "dominance": dom,
            "evidence_mode": self.evidence_mode.value,
            "feasibility": feas,
            "findings": findings_sorted,
            "frontier": self.frontier.model_dump(mode="json"),
            "limitations": sorted(self.limitations),
            "matched_replication_ids": sorted(self.matched_replication_ids),
            "metric_specs": [s.model_dump(mode="json") for s in specs],
            "provenance": dict(sorted(self.provenance.items())),
            "replication_stability": dict(sorted(self.replication_stability.items())),
            "schema_version": self.schema_version,
            "sensitivity": dict(sorted(self.sensitivity.items())) if self.sensitivity else {},
            "source_fingerprint": self.source_fingerprint,
            "study_fingerprint": self.study_fingerprint,
            "study_id": self.study_id,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        payload = self.model_dump(mode="json")
        if payload.get("generated_at") is not None:
            payload["generated_at"] = None
        return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _is_better(value_a: float, value_b: float, direction: TradeoffDirection) -> tuple[bool, bool]:
    """Return (a_better_than_b, strictly_better). Equality is not better."""
    if direction == TradeoffDirection.MAXIMIZE:
        if value_a > value_b:
            return True, True
        if value_a == value_b:
            return True, False
        return False, False
    # MINIMIZE
    if value_a < value_b:
        return True, True
    if value_a == value_b:
        return True, False
    return False, False


# Expected contract from resource strategy for known keys (authoritative on main)
_EXPECTED_TRADEOFF_CONTRACT: dict[str, tuple[str, str, TradeoffDenominator]] = {
    "task.completion.rate_offered": ("1.0", "ratio", TradeoffDenominator.OFFERED_TASKS),
    "task.completion.rate_admitted": ("1.0", "ratio", TradeoffDenominator.ADMITTED_TASKS),
    "task.deadline_success.rate_offered": ("1.0", "ratio", TradeoffDenominator.OFFERED_TASKS),
    "task.deadline_success.rate_admitted": ("1.0", "ratio", TradeoffDenominator.ADMITTED_TASKS),
    "task.latency.mean_ms": ("1.0", "ms", TradeoffDenominator.COMPLETED_TASKS),
    "task.latency.p95_ms": ("1.0", "ms", TradeoffDenominator.COMPLETED_TASKS),
    "infra.queue_length.mean": ("1.0", "tasks", TradeoffDenominator.REPLICATION),
    "infra.load_balance.jain": ("1.0", "ratio", TradeoffDenominator.REPLICATION),
    "infra.utilisation.mean": ("1.0", "fraction", TradeoffDenominator.REPLICATION),
    "task.energy.mean_j": ("1.0", "J", TradeoffDenominator.COMPLETED_TASKS),
    "resource.cost.units": ("1.0", "cost_units", TradeoffDenominator.REPLICATION),
    "task.offered.count": ("1.0", "tasks", TradeoffDenominator.OFFERED_TASKS),
    "task.admitted.count": ("1.0", "tasks", TradeoffDenominator.ADMITTED_TASKS),
    "task.rejected.count": ("1.0", "tasks", TradeoffDenominator.OFFERED_TASKS),
    "task.forwarded.count": ("1.0", "tasks", TradeoffDenominator.ADMITTED_TASKS),
    "task.started.count": ("1.0", "tasks", TradeoffDenominator.ADMITTED_TASKS),
    "task.compute_completed.count": ("1.0", "tasks", TradeoffDenominator.ADMITTED_TASKS),
    "task.returned.count": ("1.0", "tasks", TradeoffDenominator.COMPLETED_TASKS),
    "task.dropped.count": ("1.0", "tasks", TradeoffDenominator.ADMITTED_TASKS),
    "task.deadline_success.count": ("1.0", "tasks", TradeoffDenominator.OFFERED_TASKS),
}


def _compatibility_for_spec(spec: TradeoffMetricSpec) -> TradeoffCompatibilityAudit:
    expected = _EXPECTED_TRADEOFF_CONTRACT.get(spec.metric_key)
    if expected is None:
        # Check metric catalogue from main (reuse authoritative definition if present)
        try:
            from traffictwin.metrics.catalogue import METRIC_DEFINITIONS  # noqa: PLC0415

            definition = METRIC_DEFINITIONS.get(spec.metric_key)
            if definition is not None:
                exp_version = definition.implementation_version
                exp_unit = definition.unit
                mismatches: list[str] = []
                if spec.metric_version != exp_version:
                    mismatches.append(
                        f"version {spec.metric_version!r} != expected {exp_version!r}"
                    )
                if spec.unit != exp_unit:
                    mismatches.append(f"unit {spec.unit!r} != expected {exp_unit!r}")
                if mismatches:
                    return TradeoffCompatibilityAudit(
                        metric_key=spec.metric_key,
                        status=TradeoffCompatibilityStatus.INCOMPATIBLE,
                        finding="; ".join(mismatches),
                        expected_version=exp_version,
                        expected_unit=exp_unit,
                        versions=[spec.metric_version],
                        unit=spec.unit,
                        denominator=spec.denominator,
                    )
                return TradeoffCompatibilityAudit(
                    metric_key=spec.metric_key,
                    status=TradeoffCompatibilityStatus.COMPATIBLE,
                    finding="compatible with registered metric definition",
                    expected_version=exp_version,
                    expected_unit=exp_unit,
                    expected_denominator=None,
                    versions=[spec.metric_version],
                    unit=spec.unit,
                    denominator=spec.denominator,
                )
        except Exception:  # noqa: S110  # pragma: no cover - defensive
            pass
        return TradeoffCompatibilityAudit(
            metric_key=spec.metric_key,
            status=TradeoffCompatibilityStatus.UNAVAILABLE,
            finding="no registered compatibility contract; metric comparison not verified",
            versions=[spec.metric_version],
            unit=spec.unit,
            denominator=spec.denominator,
        )
    exp_version, exp_unit, exp_denom = expected
    mismatches2: list[str] = []
    if spec.metric_version != exp_version:
        mismatches2.append(f"version {spec.metric_version!r} != expected {exp_version!r}")
    if spec.unit != exp_unit:
        mismatches2.append(f"unit {spec.unit!r} != expected {exp_unit!r}")
    if spec.denominator != exp_denom:
        mismatches2.append(
            f"denominator {spec.denominator.value!r} != expected {exp_denom.value!r}"
        )
    if mismatches2:
        return TradeoffCompatibilityAudit(
            metric_key=spec.metric_key,
            status=TradeoffCompatibilityStatus.INCOMPATIBLE,
            finding="; ".join(mismatches2),
            expected_version=exp_version,
            expected_unit=exp_unit,
            expected_denominator=exp_denom,
            versions=[spec.metric_version],
            unit=spec.unit,
            denominator=spec.denominator,
        )
    return TradeoffCompatibilityAudit(
        metric_key=spec.metric_key,
        status=TradeoffCompatibilityStatus.COMPATIBLE,
        finding="compatible with expected contract",
        expected_version=exp_version,
        expected_unit=exp_unit,
        expected_denominator=exp_denom,
        versions=[spec.metric_version],
        unit=spec.unit,
        denominator=spec.denominator,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Service: build report
# ---------------------------------------------------------------------------


def build_tradeoff_report(
    study: TradeoffStudy,
    *,
    clock: Callable[[], datetime] | None = _utc_now,
) -> TradeoffReport:
    """Build deterministic trade-off report from a validated study.

    Fails closed on unadmitted evidence, incompatible metric handling, and
    bounded input violations. No weighting or normalisation is applied.
    """
    # Admission guard
    if study.admission_state == TradeoffAdmissionState.UNADMITTED:
        raise ValueError("UNADMITTED_EVIDENCE: study admission_state is unadmitted")
    if study.admission_state == TradeoffAdmissionState.REJECTED:
        raise ValueError("REJECTED_EVIDENCE: study admission_state is rejected")
    if study.admission_state == TradeoffAdmissionState.PENDING:
        raise ValueError("PENDING_EVIDENCE: study admission_state is pending")
    if study.admission_state == TradeoffAdmissionState.UNAVAILABLE:
        raise ValueError("UNAVAILABLE_EVIDENCE: study admission_state is unavailable")

    # Compatibility audit
    compatibility: list[TradeoffCompatibilityAudit] = []
    incompatible_keys: set[str] = set()
    unavailable_keys: set[str] = set()
    for spec in sorted(study.metric_specs, key=lambda s: s.metric_key):
        audit = _compatibility_for_spec(spec)
        compatibility.append(audit)
        if audit.status == TradeoffCompatibilityStatus.INCOMPATIBLE:
            incompatible_keys.add(spec.metric_key)
        elif audit.status == TradeoffCompatibilityStatus.UNAVAILABLE:
            unavailable_keys.add(spec.metric_key)

    # Map spec by key for fast lookup (removed unused)

    # Per-arm feasibility
    feasibility: list[TradeoffFeasibility] = []
    findings: list[TradeoffFinding] = []
    # For missing/incompatible reporting
    feasible_arm_ids: list[str] = []
    arm_value_map: dict[str, dict[str, float | None]] = {}
    arm_status_map: dict[str, dict[str, TradeoffStatus]] = {}

    for arm in sorted(study.arms, key=lambda a: a.arm_id):
        obs_by_key = {o.metric_key: o for o in arm.observations}
        values: dict[str, float | None] = {}
        statuses: dict[str, TradeoffStatus] = {}
        unavailable_metrics: list[str] = []
        incompatible_metrics: list[str] = []
        violation_messages: list[str] = []
        violations: list[TradeoffConstraint] = []
        has_unavailable = False

        for spec in sorted(study.metric_specs, key=lambda s: s.metric_key):
            key = spec.metric_key
            # Incompatible metrics produce no numeric aggregate
            if key in incompatible_keys:
                incompatible_metrics.append(key)
                values[key] = None
                statuses[key] = TradeoffStatus.INCOMPATIBLE
                findings.append(
                    TradeoffFinding(
                        code="INCOMPATIBLE_METRIC_WITHHELD",
                        metric_key=key,
                        arm_id=arm.arm_id,
                        message=f"Metric {key!r} is incompatible ({next(c.finding for c in compatibility if c.metric_key == key)}); numeric aggregate withheld",  # noqa: E501
                        severity="warning",
                    )
                )
                continue
            if key in unavailable_keys:
                # Compatibility UNAVAILABLE: no registered contract; metric excluded from
                # feasibility, constraints, and dominance (compatibility first, analysis second)  # noqa: E501
                unavailable_metrics.append(key)
                values[key] = None
                statuses[key] = TradeoffStatus.UNAVAILABLE
                has_unavailable = True
                findings.append(
                    TradeoffFinding(
                        code="UNAVAILABLE_METRIC_EXCLUDED",
                        metric_key=key,
                        arm_id=arm.arm_id,
                        message=f"Metric {key!r} has no registered compatibility contract; metric excluded from feasibility, constraints and dominance",  # noqa: E501
                        severity="warning",
                    )
                )
                continue
            # Compatible path — check observation availability
            obs = obs_by_key.get(key)
            if obs is None or obs.status != TradeoffStatus.AVAILABLE or obs.value is None:
                unavailable_metrics.append(key)
                values[key] = None
                statuses[key] = TradeoffStatus.UNAVAILABLE
                findings.append(
                    TradeoffFinding(
                        code="MISSING_METRIC_UNAVAILABLE",
                        metric_key=key,
                        arm_id=arm.arm_id,
                        message=f"Metric {key!r} unavailable for arm {arm.arm_id!r}; reason: {obs.reason if obs and obs.reason else 'value missing'}",  # noqa: E501
                        severity="info",
                    )
                )
                has_unavailable = True
                continue
            # Value is available and compatible
            values[key] = obs.value
            statuses[key] = TradeoffStatus.AVAILABLE
            # Check hard constraint for this metric if present
            if spec.hard_constraint is not None:
                violated = spec.hard_constraint.is_violated(obs.value)
                if violated:
                    violations.append(spec.hard_constraint)
                    msg = f"violates declared constraint {spec.hard_constraint.describe()} (value {obs.value:.6g} {spec.unit})"  # noqa: E501
                    violation_messages.append(msg)
                    findings.append(
                        TradeoffFinding(
                            code="CONSTRAINT_VIOLATED",
                            metric_key=key,
                            arm_id=arm.arm_id,
                            message=f"Arm {arm.arm_id!r} {msg}",
                            severity="warning",
                        )
                    )

        arm_value_map[arm.arm_id] = values
        arm_status_map[arm.arm_id] = statuses

        # Determine feasibility
        if incompatible_metrics:
            # Incompatible metrics make arm not feasible for trade-off (exclude from frontier)
            status = TradeoffStatus.INCOMPATIBLE
            is_feasible = False
            reason = f"incompatible metrics: {', '.join(sorted(incompatible_metrics))}"
        elif has_unavailable or unavailable_metrics:
            # Missing metrics -> unavailable; arm cannot be feasible but remains descriptive
            status = TradeoffStatus.UNAVAILABLE
            is_feasible = False
            reason = f"missing metrics: {', '.join(sorted(unavailable_metrics))}"
        elif violation_messages:
            status = TradeoffStatus.INFEASIBLE
            is_feasible = False
            reason = f"violates declared constraint: {'; '.join(violation_messages)}"
        else:
            status = TradeoffStatus.FEASIBLE
            is_feasible = True
            reason = "feasible under declared metrics and constraints"
            feasible_arm_ids.append(arm.arm_id)

        feasibility.append(
            TradeoffFeasibility(
                arm_id=arm.arm_id,
                status=status,
                is_feasible=is_feasible,
                violations=violations,
                violation_messages=violation_messages,
                unavailable_metrics=sorted(unavailable_metrics),
                incompatible_metrics=sorted(incompatible_metrics),
                reason=reason,
            )
        )

    # Pareto dominance among feasible arms only
    dominance: list[TradeoffDominance] = []
    # Only COMPATIBLE metrics enter dominance (compatibility first)  # noqa: E501
    compatible_keys = {
        c.metric_key for c in compatibility if c.status == TradeoffCompatibilityStatus.COMPATIBLE
    }
    compatible_feasible_specs = [
        s
        for s in sorted(study.metric_specs, key=lambda s: s.metric_key)
        if s.metric_key in compatible_keys
    ]
    dominated_by: dict[str, list[str]] = defaultdict(list)
    # Compute pairwise dominance
    feasible_ids_sorted = sorted(feasible_arm_ids)
    # For deterministic output, compare all feasible pairs
    for a_id in feasible_ids_sorted:
        for b_id in feasible_ids_sorted:
            if a_id == b_id:
                continue
            # Does a dominate b?
            a_vals = arm_value_map[a_id]
            b_vals = arm_value_map[b_id]
            # Check all metrics where both have values
            at_least_as_good = True
            strictly_better = False
            comparisons: dict[str, str] = {}
            missing_for_pair = False
            for spec in compatible_feasible_specs:
                key = spec.metric_key
                va = a_vals.get(key)
                vb = b_vals.get(key)
                if va is None or vb is None:
                    missing_for_pair = True
                    comparisons[key] = "unavailable"
                    # If any metric missing for this pair, cannot assert dominance across that metric  # noqa: E501
                    # For strict Pareto we require at least as good on all declared metrics where both are comparable.  # noqa: E501
                    # If missing, treat as not comparable — then dominance cannot be established (fail-closed).  # noqa: E501
                    at_least_as_good = False
                    break
                better, strict = _is_better(va, vb, spec.direction)
                if better and strict:
                    comparisons[key] = "dominator_better"
                    strictly_better = True
                elif better and not strict:
                    comparisons[key] = "equal"
                else:
                    comparisons[key] = "dominator_worse"
                    at_least_as_good = False
                    # Do not break immediately to keep comparisons populated for all keys up to fail, but we have metric-level reason.  # noqa: E501
                    # Continue to mark remaining as not comparable? Better continue to fill.
                    # But for dominance decision, one worse is enough to fail.

            dominates = at_least_as_good and strictly_better and not missing_for_pair
            # Need to continue filling remaining keys if we broke early
            if dominates:
                # All comparisons already set via loop; for any not yet set, fill equal/better already  # noqa: E501
                pass
            elif missing_for_pair:
                # Fill remaining keys as unavailable for completeness
                for spec in compatible_feasible_specs:
                    if spec.metric_key not in comparisons:
                        comparisons[spec.metric_key] = "unavailable"
            else:
                # Fill missing entries that may not have been set due to early fail? Actually loop already filled all.  # noqa: E501
                for spec in compatible_feasible_specs:
                    if spec.metric_key not in comparisons:
                        # Re-evaluate? Should have been set
                        va = a_vals.get(spec.metric_key)
                        vb = b_vals.get(spec.metric_key)
                        if va is None or vb is None:
                            comparisons[spec.metric_key] = "unavailable"
                        else:
                            better, strict = _is_better(va, vb, spec.direction)
                            if better and strict:
                                comparisons[spec.metric_key] = "dominator_better"
                            elif better and not strict:
                                comparisons[spec.metric_key] = "equal"
                            else:
                                comparisons[spec.metric_key] = "dominator_worse"

            reason_parts: list[str] = []
            if dominates:
                reason_parts.append("dominates under declared metrics")
                dominated_by[b_id].append(a_id)
            else:
                if missing_for_pair:
                    reason_parts.append("not comparable due to unavailable metric")
                else:
                    reason_parts.append("does not dominate under declared metrics")

            dominance.append(
                TradeoffDominance(
                    dominator_arm_id=a_id,
                    dominated_arm_id=b_id,
                    dominates=dominates,
                    comparisons=comparisons,
                    reason="; ".join(reason_parts),
                )
            )

    # Frontier: non-dominated feasible arms
    dominated_ids: set[str] = {d.dominated_arm_id for d in dominance if d.dominates}
    frontier_ids = [aid for aid in feasible_ids_sorted if aid not in dominated_ids]
    # Sort deterministic
    frontier_ids_sorted = sorted(frontier_ids)
    dominated_ids_sorted = sorted(dominated_ids)
    dominated_by_sorted: dict[str, list[str]] = {
        k: sorted(v) for k, v in sorted(dominated_by.items())
    }
    # Ensure every dominated has entry, every frontier not in dominated_by
    for fid in frontier_ids_sorted:
        dominated_by_sorted.setdefault(fid, [])

    frontier = TradeoffFrontier(
        frontier_arm_ids=frontier_ids_sorted,
        dominated_arm_ids=dominated_ids_sorted,
        dominated_by=dominated_by_sorted,
        description="descriptive frontier; non-dominated and feasible under declared metrics",
        all_feasible_arm_ids=feasible_ids_sorted,
    )

    # Matched-replication robustness
    replication_stability: dict[str, float | None] = {}
    if study.matched_replication_ids and any(
        any(v is not None for v in obs.per_replication_values.values())
        for arm in study.arms
        for obs in arm.observations
        if obs.per_replication_values
    ):
        # Compute per-replication frontier
        rep_counts: dict[str, int] = defaultdict(int)
        rep_frontier_counts: dict[str, int] = defaultdict(int)
        total_reps_with_data = 0
        for rid in sorted(study.matched_replication_ids):
            # Gather per-replication values for feasible arms only, for compatible metrics
            per_rep_values: dict[str, dict[str, float | None]] = {}
            for arm in study.arms:
                if arm.arm_id not in feasible_ids_sorted:
                    continue
                vals: dict[str, float | None] = {}
                for spec in compatible_feasible_specs:
                    obs = next(
                        (o for o in arm.observations if o.metric_key == spec.metric_key), None
                    )
                    if obs is None:
                        vals[spec.metric_key] = None
                    else:
                        v = obs.per_replication_values.get(rid)
                        if v is None:
                            vals[spec.metric_key] = None
                        else:
                            vals[spec.metric_key] = v
                per_rep_values[arm.arm_id] = vals
            # Check if all needed values present
            all_present = True
            for arm_id in feasible_ids_sorted:
                for spec in compatible_feasible_specs:
                    if per_rep_values.get(arm_id, {}).get(spec.metric_key) is None:
                        all_present = False
                        break
                if not all_present:
                    break
            if not all_present:
                continue
            # Check constraints per rep
            feasible_per_rep: list[str] = []
            for arm_id in feasible_ids_sorted:
                vals = per_rep_values[arm_id]
                violates = False
                for spec in compatible_feasible_specs:
                    if spec.hard_constraint is not None:
                        v = vals[spec.metric_key]
                        if v is not None and spec.hard_constraint.is_violated(v):
                            violates = True
                            break
                if not violates:
                    feasible_per_rep.append(arm_id)
            if not feasible_per_rep:
                continue
            total_reps_with_data += 1
            # Compute frontier per rep among feasible_per_rep
            dominated_per_rep: set[str] = set()
            feasible_per_rep_sorted = sorted(feasible_per_rep)
            for a_id in feasible_per_rep_sorted:
                for b_id in feasible_per_rep_sorted:
                    if a_id == b_id or b_id in dominated_per_rep:
                        continue
                    # Does a dominate b per rep?
                    at_least = True
                    strict = False
                    for spec in compatible_feasible_specs:
                        va = per_rep_values[a_id][spec.metric_key]
                        vb = per_rep_values[b_id][spec.metric_key]
                        assert va is not None and vb is not None
                        better, is_strict = _is_better(va, vb, spec.direction)
                        if not better:
                            at_least = False
                            break
                        if is_strict:
                            strict = True
                    if at_least and strict:
                        dominated_per_rep.add(b_id)
            frontier_per_rep = [
                aid for aid in feasible_per_rep_sorted if aid not in dominated_per_rep
            ]
            for aid in feasible_per_rep_sorted:
                rep_counts[aid] += 1
            for aid in frontier_per_rep:
                rep_frontier_counts[aid] += 1
        for aid in feasible_ids_sorted:
            cnt = rep_counts.get(aid, 0)
            front = rep_frontier_counts.get(aid, 0)
            if cnt > 0 and total_reps_with_data > 0:
                # Stability = proportion of replications where arm was on frontier (genuine zero if never)  # noqa: E501
                replication_stability[aid] = front / total_reps_with_data
            else:
                # No eligible frontier data for this arm -> unavailable, not 0.0
                replication_stability[aid] = None
        if total_reps_with_data == 0:
            # No complete eligible replication -> stability unavailable (not 0.0)
            for aid in feasible_ids_sorted:
                replication_stability[aid] = None
            findings.append(
                TradeoffFinding(
                    code="REPLICATION_STABILITY_UNAVAILABLE",
                    message="Matched-replication stability unavailable: no complete per-replication data for feasible arms",  # noqa: E501
                    severity="info",
                )
            )
        else:
            for aid, stab in sorted(replication_stability.items()):
                # Only emit numeric stability where computed; None remains unavailable
                if stab is None:
                    continue
                findings.append(
                    TradeoffFinding(
                        code="REPLICATION_STABILITY",
                        arm_id=aid,
                        message=f"Matched-replication stability for {aid!r}: {stab:.3f} of {total_reps_with_data} replications on descriptive frontier",  # noqa: E501
                        severity="info",
                    )
                )
    else:
        # No matched replication ids or no per-replication data -> unavailable, not 0.0
        for aid in feasible_ids_sorted:
            replication_stability[aid] = None
        if study.matched_replication_ids:
            findings.append(
                TradeoffFinding(
                    code="REPLICATION_STABILITY_UNAVAILABLE",
                    message="Per-replication values not disclosed; matched-replication robustness unavailable",  # noqa: E501
                    severity="info",
                )
            )
        else:
            findings.append(
                TradeoffFinding(
                    code="REPLICATION_STABILITY_UNAVAILABLE",
                    message="Matched-replication stability unavailable: no matched replication IDs declared",  # noqa: E501
                    severity="info",
                )
            )

    # Sensitivity: frontier without constraints (only when all constraint-bearing metrics are COMPATIBLE)  # noqa: E501
    sensitivity: dict[str, Any] = {}
    if any(s.hard_constraint is not None for s in study.metric_specs):
        # If any declared constrained metric is not COMPATIBLE, sensitivity is unavailable  # noqa: E501
        constrained_keys = {
            s.metric_key for s in study.metric_specs if s.hard_constraint is not None
        }
        unavailable_constrained = constrained_keys - compatible_keys
        incompatible_constrained = constrained_keys & incompatible_keys
        if unavailable_constrained or incompatible_constrained:
            sensitivity = {}
            findings.append(
                TradeoffFinding(
                    code="CONSTRAINT_SENSITIVITY_UNAVAILABLE",
                    message=f"Constraint sensitivity unavailable: constrained metric(s) not COMPATIBLE: {sorted(unavailable_constrained | incompatible_constrained)}; no with/without comparison made",  # noqa: E501
                    severity="info",
                )
            )
        else:
            # Compute frontier ignoring constraints (but still respecting compatibility)
            # All arms that are not unavailable/incompatible (i.e., feasible or infeasible due only to constraints) become candidates  # noqa: E501
            candidates = []
            for f in feasibility:
                if f.status in (TradeoffStatus.FEASIBLE, TradeoffStatus.INFEASIBLE):
                    candidates.append(f.arm_id)
            candidates_sorted = sorted(candidates)
            # Use same dominance logic but over candidates ignoring violations
            dominated_no_constraint: set[str] = set()
            for a_id in candidates_sorted:
                for b_id in candidates_sorted:
                    if a_id == b_id or b_id in dominated_no_constraint:
                        continue
                    a_vals = arm_value_map[a_id]
                    b_vals = arm_value_map[b_id]
                    at_least2 = True
                    strict2 = False
                    missing2 = False
                    for spec in compatible_feasible_specs:
                        va = a_vals.get(spec.metric_key)
                        vb = b_vals.get(spec.metric_key)
                        if va is None or vb is None:
                            missing2 = True
                            at_least2 = False
                            break
                        better2, strict_b2 = _is_better(va, vb, spec.direction)
                        if not better2:
                            at_least2 = False
                            break
                        if strict_b2:
                            strict2 = True
                    if at_least2 and strict2 and not missing2:
                        dominated_no_constraint.add(b_id)
            frontier_no_constraint = [
                aid for aid in candidates_sorted if aid not in dominated_no_constraint
            ]
            sensitivity["frontier_without_constraints"] = sorted(frontier_no_constraint)
            sensitivity["frontier_with_constraints"] = frontier_ids_sorted
            if sorted(frontier_no_constraint) != frontier_ids_sorted:
                findings.append(
                    TradeoffFinding(
                        code="SENSITIVITY_CONSTRAINT_IMPACT",
                        message=f"Descriptive frontier changes when declared constraints are removed: with={frontier_ids_sorted} without={sorted(frontier_no_constraint)}",  # noqa: E501
                        severity="info",
                    )
                )
            else:
                findings.append(
                    TradeoffFinding(
                        code="SENSITIVITY_CONSTRAINT_NO_IMPACT",
                        message="Descriptive frontier unchanged when declared constraints are removed",  # noqa: E501
                        severity="info",
                    )
                )

    # Assemble report
    generated_at_val: datetime | None = None
    try:
        generated_at_val = clock() if callable(clock) else None
        if generated_at_val is not None and not isinstance(generated_at_val, datetime):
            generated_at_val = None
    except Exception:
        generated_at_val = None

    report = TradeoffReport(
        schema_version=TRADEOFF_REPORT_VERSION,
        study_id=study.study_id,
        study_fingerprint=study.fingerprint(),
        source_fingerprint=study.source_fingerprint,
        evidence_mode=study.evidence_mode,
        admission_state=study.admission_state,
        metric_specs=list(study.metric_specs),
        matched_replication_ids=list(study.matched_replication_ids),
        compatibility=compatibility,
        feasibility=feasibility,
        dominance=dominance,
        frontier=frontier,
        findings=findings,
        limitations=list(study.limitations),
        provenance=dict(study.provenance),
        replication_stability=dict(sorted(replication_stability.items())),
        sensitivity=sensitivity,
        generated_at=generated_at_val,
        report_fingerprint="",
    )
    report.report_fingerprint = report.fingerprint()
    return report


# ---------------------------------------------------------------------------
# Validation and loading
# ---------------------------------------------------------------------------


def validate_tradeoff_study_dict(payload: dict[str, Any]) -> TradeoffStudy:
    return TradeoffStudy.model_validate(payload)


def load_tradeoff_study_from_dict(payload: dict[str, Any]) -> TradeoffStudy:
    return validate_tradeoff_study_dict(payload)


def load_tradeoff_study_from_json(text: str) -> TradeoffStudy:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("study JSON must be an object")
    return validate_tradeoff_study_dict(data)


def load_tradeoff_study_file(path: str | pathlib.Path) -> TradeoffStudy:
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8")
    return load_tradeoff_study_from_json(text)


# ---------------------------------------------------------------------------
# Adapter for existing Resource Strategy artifacts
# ---------------------------------------------------------------------------


def tradeoff_study_from_resource_strategy_study(
    rs_study: object,
    *,
    metric_keys: list[str] | None = None,
    directions: dict[str, TradeoffDirection] | None = None,
    constraints: dict[str, TradeoffConstraint] | None = None,
) -> TradeoffStudy:
    """Adapt a ResourceStrategyStudy into a TradeoffStudy.

    The input must already carry an authoritative compatible contract from main.
    Unknown compatibility without such a contract remains unavailable.

    Args:
        rs_study: ResourceStrategyStudy instance from
            traffictwin.experiments.resource_strategy
        metric_keys: optional subset of 2-6 metric keys to compare.
            If None, uses all catalog keys that are compatible.
        directions: explicit direction per metric_key. If omitted,
            authoritative direction is inferred from metrics catalogue or
            known resource contracts.
        constraints: optional hard constraints per metric_key.
    """
    # Lazy import to avoid hard dependency
    from traffictwin.experiments.resource_strategy import (  # noqa: PLC0415
        ResourceStrategyStudy,
    )

    if not isinstance(rs_study, ResourceStrategyStudy):
        raise TypeError("rs_study must be a ResourceStrategyStudy")

    # Build mapping from metric_key to aggregate values
    # Use already-computed ResourceStrategyReport aggregates if needed; but we can compute similarly.  # noqa: E501
    # For deterministic adapter, we build observations from ResourceStrategyReport.
    from traffictwin.experiments.resource_strategy import (  # noqa: PLC0415
        build_resource_strategy_report,
    )

    rs_report = build_resource_strategy_report(rs_study)
    # Map metric_key -> unit/denominator/version from catalog
    catalog_by_key = {m.metric_key: m for m in rs_study.metric_catalog}

    # Determine keys
    if metric_keys is None:
        # Use all compatible keys (status compatible) from rs_report compatibility
        from traffictwin.experiments.resource_strategy import (
            ResourceStrategyCompatibilityStatus,  # noqa: PLC0415
        )

        compatible_keys = [
            c.metric_key
            for c in rs_report.compatibility
            if c.status == ResourceStrategyCompatibilityStatus.COMPATIBLE
        ]
        # If none, fallback to all catalog keys
        if not compatible_keys:
            compatible_keys = list(catalog_by_key.keys())
        # Bound 2-6: take sorted first 6 if more, which maintains determinism
        compatible_keys_sorted = sorted(compatible_keys)
        if len(compatible_keys_sorted) > MAX_TRADEOFF_METRICS:
            compatible_keys_sorted = compatible_keys_sorted[:MAX_TRADEOFF_METRICS]
        if len(compatible_keys_sorted) < MIN_TRADEOFF_METRICS:
            raise ValueError(
                f"ResourceStrategy study supplies only {len(compatible_keys_sorted)} compatible metrics; need at least {MIN_TRADEOFF_METRICS}"  # noqa: E501
            )
        selected_keys = compatible_keys_sorted
    else:
        selected_keys = sorted(set(metric_keys))
        if not (MIN_TRADEOFF_METRICS <= len(selected_keys) <= MAX_TRADEOFF_METRICS):
            raise ValueError(
                f"metric_keys must contain {MIN_TRADEOFF_METRICS}-{MAX_TRADEOFF_METRICS} keys"
            )
        for k in selected_keys:
            if k not in catalog_by_key:
                raise ValueError(f"metric_key {k!r} not in ResourceStrategy catalog")

    # Infer directions
    def _infer_direction(key: str) -> TradeoffDirection:
        if directions is not None and key in directions:
            return directions[key]
        # Try metrics catalogue authoritative higher_is_better
        try:
            from traffictwin.metrics.catalogue import METRIC_DEFINITIONS  # noqa: PLC0415

            defn = METRIC_DEFINITIONS.get(key)
            if defn is not None and defn.higher_is_better is not None:
                return (
                    TradeoffDirection.MAXIMIZE
                    if defn.higher_is_better
                    else TradeoffDirection.MINIMIZE
                )
        except Exception:  # noqa: S110
            pass
        # Resource-specific known directions
        known_minimize = {
            "task.latency.mean_ms",
            "task.latency.p95_ms",
            "infra.queue_length.mean",
            "task.energy.mean_j",
            "resource.cost.units",
        }
        known_maximize = {
            "task.completion.rate_offered",
            "task.completion.rate_admitted",
            "task.deadline_success.rate_offered",
            "task.deadline_success.rate_admitted",
            "infra.load_balance.jain",
            "infra.utilisation.mean",
        }
        if key in known_minimize:
            return TradeoffDirection.MINIMIZE
        if key in known_maximize:
            return TradeoffDirection.MAXIMIZE
        # Fallback: latency/energy/cost/jain heuristics
        lower = key.lower()
        if (
            any(x in lower for x in ("latency", "energy", "cost", "queue", "miss", "gap"))
            and "jain" not in lower
        ):
            return TradeoffDirection.MINIMIZE
        return TradeoffDirection.MAXIMIZE

    # Build metric specs
    specs: list[TradeoffMetricSpec] = []
    for key in selected_keys:
        cat = catalog_by_key[key]
        # Map denominator string to enum
        denom_str = (
            cat.denominator.value if hasattr(cat.denominator, "value") else str(cat.denominator)
        )
        try:
            denom = TradeoffDenominator(denom_str)
        except ValueError:
            denom = TradeoffDenominator.UNKNOWN
        direction = _infer_direction(key)
        hc = None
        if constraints is not None and key in constraints:
            hc = constraints[key]
            if hc.metric_key != key:
                raise ValueError(f"constraint metric_key mismatch for {key!r}")
        specs.append(
            TradeoffMetricSpec(
                metric_key=key,
                metric_version=cat.metric_version,
                unit=cat.unit,
                denominator=denom,
                direction=direction,
                hard_constraint=hc,
                description=cat.description if hasattr(cat, "description") else "",
            )
        )

    # Build arms with observations from rs_report aggregates
    arms: list[TradeoffArm] = []
    # Map (arm_id, metric_key) -> aggregate
    agg_map: dict[tuple[str, str], Any] = {}
    for arm_summary in rs_report.arm_summaries:
        for agg in arm_summary.metric_aggregates:
            agg_map[(arm_summary.arm_id, agg.metric_key)] = agg
    # Also need per-replication values: from rs_report arm_summaries per_replication_values
    for rs_arm in rs_report.arm_summaries:
        observations: list[TradeoffObservation] = []
        for key in selected_keys:
            agg_any: Any = agg_map.get((rs_arm.arm_id, key))
            agg = agg_any
            if agg is None:
                # Missing metric -> unavailable
                cat = catalog_by_key[key]
                denom_str2 = (
                    cat.denominator.value
                    if hasattr(cat.denominator, "value")
                    else str(cat.denominator)
                )
                try:
                    denom2 = TradeoffDenominator(denom_str2)
                except ValueError:
                    denom2 = TradeoffDenominator.UNKNOWN
                observations.append(
                    TradeoffObservation(
                        arm_id=rs_arm.arm_id,
                        metric_key=key,
                        metric_version=cat.metric_version,
                        unit=cat.unit,
                        denominator=denom2,
                        value=None,
                        status=TradeoffStatus.UNAVAILABLE,
                        per_replication_values={},
                        replication_count=0,
                        reason="metric not available in ResourceStrategy report for this arm",
                    )
                )
                continue
            # Determine status mapping
            if hasattr(agg, "status"):
                rs_status = agg.status.value if hasattr(agg.status, "value") else str(agg.status)
                if rs_status == "available":
                    t_status = TradeoffStatus.AVAILABLE
                elif rs_status == "partial":
                    # Partial still considered available for descriptive frontier but flagged; treat as available with reason  # noqa: E501
                    t_status = TradeoffStatus.AVAILABLE
                elif rs_status == "unavailable":
                    t_status = TradeoffStatus.UNAVAILABLE
                else:
                    t_status = TradeoffStatus.UNAVAILABLE
            else:
                t_status = TradeoffStatus.AVAILABLE
            # Incompatible metrics must be withheld per resource strategy
            # Check compatibility list for this key
            from traffictwin.experiments.resource_strategy import (
                ResourceStrategyCompatibilityStatus as _RSCompStatus,
            )  # noqa: PLC0415

            comp = next((c for c in rs_report.compatibility if c.metric_key == key), None)
            if comp is not None and comp.status == _RSCompStatus.INCOMPATIBLE:
                t_status = TradeoffStatus.INCOMPATIBLE
                # Withhold numeric aggregate per spec
                observations.append(
                    TradeoffObservation(
                        arm_id=rs_arm.arm_id,
                        metric_key=key,
                        metric_version=agg.metric_version,
                        unit=agg.unit,
                        denominator=TradeoffDenominator(agg.denominator.value)
                        if hasattr(agg.denominator, "value")
                        else TradeoffDenominator.UNKNOWN,
                        value=None,
                        status=TradeoffStatus.INCOMPATIBLE,
                        per_replication_values={},
                        replication_count=agg.replication_count,
                        reason=f"incompatible metric version/unit/denominator: {comp.finding}",
                    )
                )
                continue
            # Use aggregate_mean as observation value
            denom_val = (
                agg.denominator.value if hasattr(agg.denominator, "value") else str(agg.denominator)
            )
            try:
                denom_enum = TradeoffDenominator(denom_val)
            except ValueError:
                denom_enum = TradeoffDenominator.UNKNOWN
            # per_replication_values: use agg.per_replication_values if available
            per_rep = dict(getattr(agg, "per_replication_values", {}) or {})
            # Ensure keys are strings sorted via dict
            observations.append(
                TradeoffObservation(
                    arm_id=rs_arm.arm_id,
                    metric_key=key,
                    metric_version=agg.metric_version,
                    unit=agg.unit,
                    denominator=denom_enum,
                    value=agg.aggregate_mean,
                    status=t_status,
                    per_replication_values=per_rep,
                    replication_count=agg.replication_count,
                    reason=agg.reason if getattr(agg, "reason", None) else None,
                )
            )
        arms.append(
            TradeoffArm(
                arm_id=rs_arm.arm_id,
                label=rs_arm.label,
                description=f"{rs_arm.strategy_type} — adapted from ResourceStrategy",
                strategy_type=rs_arm.strategy_type,
                observations=sorted(observations, key=lambda o: o.metric_key),
            )
        )

    arms_sorted = sorted(arms, key=lambda a: a.arm_id)
    specs_sorted = sorted(specs, key=lambda s: s.metric_key)

    # Map provenance and limitations
    # Evidence mode mapping
    mode_map = {
        "synthetic_demonstration": TradeoffEvidenceMode.SYNTHETIC_DEMONSTRATION,
        "imported": TradeoffEvidenceMode.IMPORTED,
        "historical_observation": TradeoffEvidenceMode.HISTORICAL_OBSERVATION,
        "admitted_research": TradeoffEvidenceMode.ADMITTED_RESEARCH,
        "unadmitted_research": TradeoffEvidenceMode.UNADMITTED_RESEARCH,
        "unavailable": TradeoffEvidenceMode.UNAVAILABLE,
    }
    admission_map = {
        "synthetic_demonstration": TradeoffAdmissionState.SYNTHETIC_DEMONSTRATION,
        "admitted": TradeoffAdmissionState.ADMITTED,
        "unadmitted": TradeoffAdmissionState.UNADMITTED,
        "rejected": TradeoffAdmissionState.REJECTED,
        "pending": TradeoffAdmissionState.PENDING,
        "unavailable": TradeoffAdmissionState.UNAVAILABLE,
    }
    ev_mode = mode_map.get(
        rs_study.evidence_mode.value
        if hasattr(rs_study.evidence_mode, "value")
        else str(rs_study.evidence_mode),
        TradeoffEvidenceMode.SYNTHETIC_DEMONSTRATION,
    )
    ad_state = admission_map.get(
        rs_study.admission_state.value
        if hasattr(rs_study.admission_state, "value")
        else str(rs_study.admission_state),
        TradeoffAdmissionState.SYNTHETIC_DEMONSTRATION,
    )

    return TradeoffStudy(
        schema_version=TRADEOFF_SCHEMA_VERSION,
        study_id=rs_study.study_id,
        source_fingerprint=rs_study.source_fingerprint,
        evidence_mode=ev_mode,
        admission_state=ad_state,
        arms=arms_sorted,
        metric_specs=specs_sorted,
        matched_replication_ids=sorted(rs_study.common_matched_replication_ids),
        limitations=list(rs_study.limitations),
        provenance=dict(rs_study.provenance),
        generated_at=None,
    )


def load_tradeoff_study_from_resource_strategy_json(
    text: str,
    *,
    metric_keys: list[str] | None = None,
    directions: dict[str, TradeoffDirection] | None = None,
    constraints: dict[str, TradeoffConstraint] | None = None,
) -> TradeoffStudy:
    from traffictwin.experiments.resource_strategy import (
        load_resource_strategy_study_from_json,  # noqa: PLC0415
    )

    rs_study = load_resource_strategy_study_from_json(text)
    return tradeoff_study_from_resource_strategy_study(
        rs_study, metric_keys=metric_keys, directions=directions, constraints=constraints
    )


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def tradeoff_study_to_json(study: TradeoffStudy) -> str:
    return study.to_json()


def tradeoff_report_to_json(report: TradeoffReport) -> str:
    return report.to_json()


def tradeoff_report_to_markdown(report: TradeoffReport) -> str:
    lines = [
        "# Multi-Objective Trade-Off Report",
        "",
        f"- Study: `{_cell(report.study_id)}`",
        f"- Source fingerprint: `{report.source_fingerprint}`",
        f"- Study fingerprint: `{report.study_fingerprint}`",
        f"- Report fingerprint: `{report.report_fingerprint}`",
        f"- Evidence mode: `{report.evidence_mode.value}`",
        f"- Admission state: `{report.admission_state.value}`",
        f"- Matched replications: {len(report.matched_replication_ids)}",
        f"- Descriptive frontier: {', '.join(report.frontier.frontier_arm_ids) if report.frontier.frontier_arm_ids else 'none (all infeasible or no feasible arms)'}",  # noqa: E501
        "",
        "## Limitations",
        "",
    ]
    if report.limitations:
        lines.extend(f"- {lim}" for lim in report.limitations)
    else:
        lines.append("No limitations declared.")
    lines.extend(["", "## Metric Specs (declared, no implicit weight)", ""])
    lines.append("| Metric | Version | Unit | Denominator | Direction | Constraint |")
    lines.append("|---|---|---|---|---|---|")
    for spec in sorted(report.metric_specs, key=lambda s: s.metric_key):
        hc = spec.hard_constraint.describe() if spec.hard_constraint else "none"
        lines.append(
            f"| {_cell(spec.metric_key)} | {_cell(spec.metric_version)} | {_cell(spec.unit)} | {_cell(spec.denominator.value)} | {_cell(spec.direction.value)} | {_cell(hc)} |"  # noqa: E501
        )
    lines.extend(["", "## Compatibility Audit", ""])
    for comp in sorted(report.compatibility, key=lambda c: c.metric_key):
        lines.append(f"- `{_cell(comp.metric_key)}`: {comp.status.value} — {_cell(comp.finding)}")
    lines.extend(["", "## Per-Arm Feasibility", ""])
    lines.append("| Arm | Status | Feasible | Violations | Unavailable | Incompatible | Reason |")
    lines.append("|---|---|---|---|---|---|---|")
    for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
        lines.append(
            f"| {_cell(feas.arm_id)} | {_cell(feas.status.value)} | {_cell(str(feas.is_feasible))} | {_cell('; '.join(feas.violation_messages) or 'none')} | {_cell(', '.join(feas.unavailable_metrics) or 'none')} | {_cell(', '.join(feas.incompatible_metrics) or 'none')} | {_cell(feas.reason)} |"  # noqa: E501
        )
    lines.extend(["", "## Descriptive Frontier (non-dominated, feasible)", ""])
    lines.append(
        f"Frontier arms: {', '.join(report.frontier.frontier_arm_ids) if report.frontier.frontier_arm_ids else 'none'}"  # noqa: E501
    )
    lines.append(
        f"Dominated arms: {', '.join(report.frontier.dominated_arm_ids) if report.frontier.dominated_arm_ids else 'none'}"  # noqa: E501
    )
    if report.frontier.dominated_by:
        lines.append("")
        lines.append("| Arm | Dominated by |")
        lines.append("|---|---|")
        for arm_id, by_list in sorted(report.frontier.dominated_by.items()):
            if by_list:
                lines.append(f"| {_cell(arm_id)} | {_cell(', '.join(by_list))} |")
    lines.extend(["", "## Dominance Matrix (feasible arms only, descriptive)", ""])
    lines.append(
        "Descriptive dominance only; no best, optimal, winner, or recommended claim is made unless a declared scalar decision rule explicitly selects one."  # noqa: E501
    )
    lines.append("")
    if report.dominance:
        lines.append("| Dominator | Dominated | Dominates under declared metrics | Reason |")
        lines.append("|---|---|---|---|")
        for dom in sorted(report.dominance, key=lambda d: (d.dominator_arm_id, d.dominated_arm_id)):
            lines.append(
                f"| {_cell(dom.dominator_arm_id)} | {_cell(dom.dominated_arm_id)} | {_cell(str(dom.dominates))} | {_cell(dom.reason)} |"  # noqa: E501
            )
    else:
        lines.append("No dominance relationships (fewer than two feasible arms).")
    lines.extend(["", "## Matched-Replication Stability", ""])
    # Distinguish None (unavailable) from 0.0 (genuine zero)
    numeric_stabs = {k: v for k, v in report.replication_stability.items() if v is not None}
    if numeric_stabs:
        for arm_id, stab in sorted(report.replication_stability.items()):
            if stab is None:
                lines.append(f"- `{_cell(arm_id)}`: stability unavailable")
            else:
                lines.append(f"- `{_cell(arm_id)}`: stability {stab:.3f}")
    else:
        # No numeric stability -> check if any entries are None (unavailable) vs empty
        if report.replication_stability:
            for arm_id, _stab in sorted(report.replication_stability.items()):
                lines.append(f"- `{_cell(arm_id)}`: stability unavailable")
        else:
            lines.append("Stability not available.")
    if report.sensitivity:
        lines.extend(["", "## Sensitivity to Declared Constraints", ""])
        lines.append(
            f"- With constraints frontier: {report.sensitivity.get('frontier_with_constraints')}"
        )
        lines.append(
            f"- Without constraints frontier: {report.sensitivity.get('frontier_without_constraints')}"  # noqa: E501
        )
    lines.extend(["", "## Findings", ""])
    if report.findings:
        for finding in sorted(
            report.findings, key=lambda f: (f.code, f.arm_id or "", f.metric_key or "")
        ):
            lines.append(
                f"- `{_cell(finding.code)}` ({_cell(finding.severity)}): {_cell(finding.message)}"
            )
    else:
        lines.append("No findings.")
    lines.extend(["", "## Provenance", ""])
    if report.provenance:
        for key in sorted(report.provenance):
            lines.append(f"- `{_cell(key)}`: `{_cell(str(report.provenance[key]))}`")
    else:
        lines.append("No provenance references.")
    return "\n".join(lines)


def tradeoff_report_to_csv(report: TradeoffReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "study_id",
            "arm_id",
            "metric_key",
            "metric_version",
            "unit",
            "denominator",
            "direction",
            "status",
            "value",
            "hard_constraint",
            "feasibility_status",
            "is_feasible",
            "on_frontier",
            "stability",
        ]
    )
    frontier_set = set(report.frontier.frontier_arm_ids)
    # Map observations from report? We don't store per-arm observations in report's top level; reconstruct from feasibility + metric specs + dominance values?  # noqa: E501
    # For CSV we emit metric spec + feasibility per arm-metric intersection using report's metric_specs and feasibility  # noqa: E501
    # We need arm_value_map; but report does not retain per-arm numeric values directly. Use findings? Instead emit per-arm per-metric using dominance comparisons is insufficient.  # noqa: E501
    # To provide meaningful CSV, we emit feasibility rows per metric: value is not stored in report payload beyond per-replication; for portability we emit aggregate value via separate lookup is not available.  # noqa: E501
    # Fallback: emit one row per arm per metric with status and constraint without numeric value; numeric value is available in the underlying study, but for report we include stability.  # noqa: E501
    # For now emit feasibility status per arm with blank value; consumer can join with study JSON for values.  # noqa: E501
    for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
        for spec in sorted(report.metric_specs, key=lambda s: s.metric_key):
            stab = report.replication_stability.get(feas.arm_id)
            stab_str = f"{stab:.6g}" if stab is not None else ""
            writer.writerow(
                [
                    report.study_id,
                    feas.arm_id,
                    spec.metric_key,
                    spec.metric_version,
                    spec.unit,
                    spec.denominator.value,
                    spec.direction.value,
                    feas.status.value,
                    "",  # value not duplicated in report; see study JSON
                    spec.hard_constraint.describe() if spec.hard_constraint else "",
                    feas.status.value,
                    str(feas.is_feasible),
                    str(feas.arm_id in frontier_set),
                    stab_str,
                ]
            )
    return output.getvalue()


def tradeoff_frontier_to_csv(report: TradeoffReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["arm_id", "on_frontier", "feasible", "dominated_by", "stability"])
    frontier_set = set(report.frontier.frontier_arm_ids)
    for feas in sorted(report.feasibility, key=lambda f: f.arm_id):
        stab2 = report.replication_stability.get(feas.arm_id)
        stab2_str = f"{stab2:.6g}" if stab2 is not None else ""
        writer.writerow(
            [
                feas.arm_id,
                str(feas.arm_id in frontier_set),
                str(feas.is_feasible),
                ";".join(report.frontier.dominated_by.get(feas.arm_id, [])),
                stab2_str,
            ]
        )
    return output.getvalue()


# ---------------------------------------------------------------------------
# Internal helpers for exports
# ---------------------------------------------------------------------------


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _num(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.6g}"
