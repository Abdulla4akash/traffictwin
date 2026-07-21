"""R8 contract-gated completed-task energy anomaly candidate."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.domain.energy import DEFAULT_TASK_ENERGY_CONTRACT
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricStatus, MetricValue
from traffictwin.rules.base import DiagnosticRule, MetricLookup
from traffictwin.rules.config import R8Config, RuleSetConfig
from traffictwin.rules.models import (
    ConfidenceCategory,
    Finding,
    FindingSupport,
    Recommendation,
    RuleResult,
    RuleStatus,
    result_from_findings,
)

ENERGY_PER_COMPLETED_KEY: Literal["task.energy.per_completed_j"] = "task.energy.per_completed_j"
COMPLETED_COUNT_KEY: Literal["task.completed.count"] = "task.completed.count"
ENERGY_UNIT = "J/task"
COUNT_UNIT = "count"


class R8EnergyDiagnosisContract(BaseModel):
    """Machine-readable public boundary for DIA-03 energy diagnosis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    capability: Literal["DIA-03"] = "DIA-03"
    rule_id: Literal["R8"] = "R8"
    rule_version: Literal["1.0"] = "1.0"
    ruleset_version: Literal["1.3"] = "1.3"
    evidence_boundary: Literal["EvidencePack.metric_collection"] = "EvidencePack.metric_collection"
    metric_key: Literal["task.energy.per_completed_j"] = ENERGY_PER_COMPLETED_KEY
    denominator_metric_key: Literal["task.completed.count"] = COMPLETED_COUNT_KEY
    required_energy_contract_fingerprint: str
    default_r8_config: R8Config
    admission_requirements: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def r8_energy_diagnosis_contract() -> R8EnergyDiagnosisContract:
    """Return the static versioned DIA-03 contract."""

    return R8EnergyDiagnosisContract(
        required_energy_contract_fingerprint=DEFAULT_TASK_ENERGY_CONTRACT.fingerprint(),
        default_r8_config=R8Config(),
        admission_requirements=[
            "energy metric and completed-count denominator are available",
            "energy metric unit is J/task and denominator unit is count",
            "canonical task-energy contract version and fingerprint match exactly",
            "completed-task energy coverage is complete",
            "eligible, population, and completed-task counts are consistent",
        ],
        limitations=[
            "The default is a provisional synthetic-development threshold.",
            "R8 is a single-run diagnostic candidate, not a statistical anomaly test.",
            "R8 does not establish hardware efficiency, root cause, or external validity.",
        ],
    )


class R8EnergyAnomalyRule(DiagnosticRule):
    """Identify high completed-task energy under one exact semantic contract."""

    rule_id = "R8"
    rule_version = "1.0"
    title = "Completed-task energy anomaly candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R8 without reading or recomputing raw task evidence."""

        cfg = config.r8
        lookup = MetricLookup(evidence_pack)
        energy_metric = lookup.metric(ENERGY_PER_COMPLETED_KEY)
        completed_metric = lookup.metric(COMPLETED_COUNT_KEY)
        failures = _admission_failures(energy_metric, completed_metric)
        if failures:
            return _insufficient(
                self,
                evidence_pack,
                evaluated_at,
                failures,
                energy_metric,
                completed_metric,
            )

        assert energy_metric is not None and completed_metric is not None
        energy_value = _finite_number(energy_metric.value)
        completed_count = _whole_number(completed_metric.value)
        eligible_count = _strict_non_negative_int(energy_metric.metadata.get("eligible_count"))
        population_count = _strict_non_negative_int(energy_metric.metadata.get("population_count"))
        coverage = _finite_number(energy_metric.metadata.get("coverage_fraction"))
        assert energy_value is not None
        assert completed_count is not None
        assert eligible_count is not None and population_count is not None
        assert coverage is not None

        threshold_met = energy_value >= cfg.minimum_energy_per_completed_task_j
        support_met = completed_count >= cfg.minimum_completed_tasks
        findings = [
            Finding(
                finding_id="R8-F1",
                statement=(
                    "Mean energy per completed task is compared with the configured candidate "
                    "boundary."
                ),
                evidence_keys=[ENERGY_PER_COMPLETED_KEY],
                observed_values={"energy_per_completed_task_j": energy_value},
                expected_condition=(
                    f"energy per completed task >= {cfg.minimum_energy_per_completed_task_j} J/task"
                ),
                support=_support(threshold_met),
            ),
            Finding(
                finding_id="R8-F2",
                statement=(
                    "The completed-task denominator is checked against the configured minimum "
                    "support."
                ),
                evidence_keys=[COMPLETED_COUNT_KEY, ENERGY_PER_COMPLETED_KEY],
                observed_values={
                    "completed_task_count": completed_count,
                    "energy_eligible_count": eligible_count,
                    "energy_population_count": population_count,
                },
                expected_condition=f"completed task count >= {cfg.minimum_completed_tasks}",
                support=_support(support_met),
            ),
            Finding(
                finding_id="R8-F3",
                statement=(
                    "Energy quantity, unit, eligibility, semantic contract, and complete coverage "
                    "were admitted before threshold evaluation."
                ),
                evidence_keys=[ENERGY_PER_COMPLETED_KEY],
                observed_values={
                    "energy_contract_fingerprint": str(
                        energy_metric.metadata["energy_contract_fingerprint"]
                    ),
                    "coverage_fraction": coverage,
                },
                expected_condition="exact canonical v1.0 contract and complete coverage",
                support=FindingSupport.SUPPORTS,
            ),
        ]
        if threshold_met and support_met:
            status = RuleStatus.TRIGGERED
            hypothesis = (
                "Completed work has high mean energy cost under the configured provisional "
                "boundary."
            )
            confidence = ConfidenceCategory.MODERATE
        elif threshold_met:
            status = RuleStatus.CONFLICTING_EVIDENCE
            hypothesis = (
                "The observed completed-task energy meets the boundary, but too few completed "
                "tasks support the candidate."
            )
            confidence = ConfidenceCategory.LOW
        else:
            status = RuleStatus.NOT_TRIGGERED
            hypothesis = None
            confidence = ConfidenceCategory.UNAVAILABLE

        return result_from_findings(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            title=self.title,
            status=status,
            synthetic=evidence_pack.synthetic,
            evaluated_at=evaluated_at,
            hypothesis=hypothesis,
            findings=findings,
            missing_evidence=[
                "matched baseline or externally calibrated energy distribution",
                "task-class, workload, offload-decision, and hardware context",
            ],
            alternative_explanations=[
                "a heavier completed-task class or workload mix",
                "different local, V2I, or V2V execution decisions",
                "longer task latency or different resource constraints",
                "finite synthetic or imported sample variation",
                "the labelled synthetic energy model rather than measured hardware energy",
            ],
            recommendations=[
                Recommendation(
                    action="compare completed-task energy across matched common-seed repetitions",
                    rationale=(
                        "replication can show whether the energy-cost candidate is stable across "
                        "compatible runs"
                    ),
                    expected_direction="energy differences and their variability become measurable",
                    prerequisite=(
                        "identical task-energy contract, policy context, workload, and seed design"
                    ),
                    verification_step=(
                        "recompute MET-03 and R8 with the threshold declared before comparison"
                    ),
                )
            ],
            confidence=confidence,
            confidence_basis=[
                "categorical confidence reflects exact contract admission, complete coverage, "
                "denominator consistency, and completed-task support; it is not a probability"
            ],
            limitations=[
                "The 1.50 J/task default is a provisional synthetic-development value, not a "
                "hardware or operational efficiency standard.",
                "R8 is a single-run threshold candidate, not a statistical outlier test.",
                "R8 does not establish root cause, hardware efficiency, external validity, or an "
                "energy-saving recommendation.",
                "Calculation lineage identifies eligible contributors and does not attribute "
                "causal energy use.",
            ],
            metadata={
                "r8_minimum_energy_per_completed_task_j": (cfg.minimum_energy_per_completed_task_j),
                "r8_minimum_completed_tasks": cfg.minimum_completed_tasks,
                "r8_observed_energy_per_completed_task_j": energy_value,
                "r8_completed_task_count": completed_count,
                "r8_energy_eligible_count": eligible_count,
                "r8_energy_population_count": population_count,
                "r8_coverage_fraction": coverage,
                "r8_energy_contract_fingerprint": str(
                    energy_metric.metadata["energy_contract_fingerprint"]
                ),
                "r8_boundary": "greater_than_or_equal",
                "r8_denominator_policy": "exact_completed_task_population",
            },
        )


def _admission_failures(
    energy_metric: MetricValue | None,
    completed_metric: MetricValue | None,
) -> list[str]:
    failures: list[str] = []
    if energy_metric is None:
        failures.append(f"{ENERGY_PER_COMPLETED_KEY}: metric is absent")
    elif energy_metric.status is not MetricStatus.AVAILABLE:
        failures.append(
            f"{ENERGY_PER_COMPLETED_KEY}: metric status is {energy_metric.status.value}"
        )
    else:
        if energy_metric.unit != ENERGY_UNIT:
            failures.append(
                f"{ENERGY_PER_COMPLETED_KEY}: unit {energy_metric.unit!r} is not {ENERGY_UNIT!r}"
            )
        energy_value = _finite_number(energy_metric.value)
        if energy_value is None or energy_value < 0:
            failures.append(f"{ENERGY_PER_COMPLETED_KEY}: value is not finite non-negative energy")
        expected_metadata: dict[str, object] = {
            "energy_family_version": "1.0",
            "energy_contract_fingerprint": DEFAULT_TASK_ENERGY_CONTRACT.fingerprint(),
            "energy_contract_version": "1.0",
            "energy_quantity": "per_task_total_energy",
            "energy_unit": "J",
            "eligibility_policy": "completed_and_finite_non_negative_energy",
        }
        for key, expected in expected_metadata.items():
            if energy_metric.metadata.get(key) != expected:
                failures.append(
                    f"{ENERGY_PER_COMPLETED_KEY}: metadata {key!r} is absent or incompatible"
                )
        coverage = _finite_number(energy_metric.metadata.get("coverage_fraction"))
        if coverage != 1.0:
            failures.append(
                f"{ENERGY_PER_COMPLETED_KEY}: completed-task energy coverage is not complete"
            )
        eligible_count = _strict_non_negative_int(energy_metric.metadata.get("eligible_count"))
        population_count = _strict_non_negative_int(energy_metric.metadata.get("population_count"))
        if eligible_count is None or population_count is None:
            failures.append(f"{ENERGY_PER_COMPLETED_KEY}: eligibility counts are absent or invalid")
        elif eligible_count != population_count:
            failures.append(f"{ENERGY_PER_COMPLETED_KEY}: eligible and population counts differ")
        elif population_count == 0:
            failures.append(f"{ENERGY_PER_COMPLETED_KEY}: completed-task population is empty")

    if completed_metric is None:
        failures.append(f"{COMPLETED_COUNT_KEY}: metric is absent")
    elif completed_metric.status is not MetricStatus.AVAILABLE:
        failures.append(f"{COMPLETED_COUNT_KEY}: metric status is {completed_metric.status.value}")
    else:
        if completed_metric.unit != COUNT_UNIT:
            failures.append(
                f"{COMPLETED_COUNT_KEY}: unit {completed_metric.unit!r} is not {COUNT_UNIT!r}"
            )
        completed_count = _whole_number(completed_metric.value)
        if completed_count is None:
            failures.append(f"{COMPLETED_COUNT_KEY}: value is not a non-negative whole count")
        if energy_metric is not None and energy_metric.status is MetricStatus.AVAILABLE:
            population_count = _strict_non_negative_int(
                energy_metric.metadata.get("population_count")
            )
            if (
                completed_count is not None
                and population_count is not None
                and completed_count != population_count
            ):
                failures.append(
                    "completed-task denominator conflicts with energy population metadata"
                )
    return sorted(set(failures))


def _insufficient(
    rule: R8EnergyAnomalyRule,
    evidence_pack: EvidencePack,
    evaluated_at: datetime,
    failures: list[str],
    energy_metric: MetricValue | None,
    completed_metric: MetricValue | None,
) -> RuleResult:
    evidence_keys = [
        key
        for key, metric in (
            (ENERGY_PER_COMPLETED_KEY, energy_metric),
            (COMPLETED_COUNT_KEY, completed_metric),
        )
        if metric is not None
    ]
    return result_from_findings(
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        title=rule.title,
        status=RuleStatus.INSUFFICIENT_EVIDENCE,
        synthetic=evidence_pack.synthetic,
        evaluated_at=evaluated_at,
        findings=[
            Finding(
                finding_id="R8-F0",
                statement=(
                    "R8 admission failed before the energy boundary was evaluated; unavailable "
                    "or incompatible evidence was not treated as zero."
                ),
                evidence_keys=evidence_keys,
                observed_values={"admission_failure_count": len(failures)},
                expected_condition="exact compatible completed-task energy evidence",
                support=FindingSupport.NEUTRAL,
            )
        ],
        missing_evidence=failures,
        recommendations=[
            Recommendation(
                action="provide complete contract-compatible per-completed-task energy evidence",
                rationale="R8 cannot compare absent, partial, mixed-unit, or inconsistent evidence",
                expected_direction="R8 admission should become evaluable",
                prerequisite="canonical v1.0 task-energy contract and completed-task denominator",
                verification_step="recompute MET-03 and rerun R8",
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["required energy evidence for R8 is incomplete or incompatible"],
        limitations=[
            "R8 does not convert unsupported energy units or infer energy semantics.",
            "Missing or partial energy is never treated as zero.",
        ],
        metadata={
            "r8_required_energy_contract_fingerprint": (DEFAULT_TASK_ENERGY_CONTRACT.fingerprint()),
            "r8_admission_failure_count": len(failures),
        },
    )


def _finite_number(value: object) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _whole_number(value: object) -> int | None:
    number = _finite_number(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def _strict_non_negative_int(value: object) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        return None
    return value


def _support(condition: bool) -> FindingSupport:
    return FindingSupport.SUPPORTS if condition else FindingSupport.CONTRADICTS
