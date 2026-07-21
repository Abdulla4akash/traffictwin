"""Synthetic fault-injection evaluation utilities for deterministic rules."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    JsonValue,
    MetricCollection,
    MetricStatus,
    MetricValue,
    UnavailableReason,
)
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.engine import evaluate_rules


class SyntheticDiagnosticCase(BaseModel):
    """Hand-auditable synthetic diagnostic case definition."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    split: str
    fault_family: str = "unspecified"
    severity: str = "nominal"
    random_seed: int = Field(default=7, ge=0)
    metrics: dict[str, JsonValue] = Field(default_factory=dict)
    unavailable_metrics: list[str] = Field(default_factory=list)
    evidence_availability: dict[str, str] = Field(default_factory=dict)
    validation_counts: dict[str, int] = Field(
        default_factory=lambda: {"info": 0, "warning": 0, "error": 0, "fatal": 0}
    )
    may_import: bool = True
    expected_triggered_rules: list[str] = Field(default_factory=list)
    expected_insufficient_rules: list[str] = Field(default_factory=list)
    acceptable_alternatives: list[str] = Field(default_factory=list)
    synthetic_faults: list[str] = Field(default_factory=list)
    notes: str = ""


class SyntheticFixtureSet(BaseModel):
    """Container for labelled diagnostic cases."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    description: str
    cases: list[SyntheticDiagnosticCase]


class RuleEvaluationCounts(BaseModel):
    """Per-rule evaluation counts."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    support_count: int = 0
    precision: float | None = None
    recall: float | None = None
    false_positive_rate: float | None = None
    specificity: float | None = None


class CaseEvaluationOutcome(BaseModel):
    """Expected and observed labels for one synthetic case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    split: str
    fault_family: str
    severity: str
    random_seed: int
    expected_triggered_rules: list[str]
    actual_triggered_rules: list[str]
    exact_match: bool


class SplitEvaluationSummary(BaseModel):
    """Aggregate deterministic classification quality for one split."""

    model_config = ConfigDict(extra="forbid")

    split: str
    case_count: int = Field(ge=0)
    exact_match_count: int = Field(ge=0)
    exact_match_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    macro_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    macro_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    false_positive_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class RobustnessSummary(BaseModel):
    """Trigger stability for one expected rule across severity/seed replicates."""

    model_config = ConfigDict(extra="forbid")

    fault_family: str
    rule_id: str
    severity: str
    replicate_count: int = Field(ge=1)
    trigger_rate: float = Field(ge=0.0, le=1.0)


class EvaluationMode(StrEnum):
    """Supported deterministic synthetic evaluation modes."""

    DECLARED = "declared"
    EXTENDED_MATRIX = "extended_matrix"


class FaultInjectionEvaluationReport(BaseModel):
    """Evaluation summary for labelled synthetic diagnostic cases."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime
    case_count: int
    split_counts: dict[str, int]
    per_rule: list[RuleEvaluationCounts]
    kpi_baseline_per_rule: list[RuleEvaluationCounts]
    confusion_table: dict[str, dict[str, int]]
    split_summaries: list[SplitEvaluationSummary]
    robustness: list[RobustnessSummary]
    case_outcomes: list[CaseEvaluationOutcome]
    failure_case_ids: list[str]
    limitations: list[str]

    def to_json(self) -> str:
        """Return JSON output."""

        return self.model_dump_json(indent=2)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def load_fixture_set(path: str | Path) -> SyntheticFixtureSet:
    """Load a synthetic fixture set from JSON."""

    return SyntheticFixtureSet.model_validate_json(Path(path).read_text(encoding="utf-8"))


def evidence_pack_from_case(
    case: SyntheticDiagnosticCase,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> EvidencePack:
    """Build an EvidencePack fixture from one labelled synthetic case."""

    generated_at = clock()
    context = {
        "run_id": f"run-{case.case_id}",
        "experiment_id": "exp-diagnostic-fixtures",
        "seed_id": f"seed-{case.case_id}",
        "algorithm": "synthetic-policy",
        "checkpoint": None,
        "random_seed": case.random_seed,
        "environment": "synthetic",
        "environment_version": "diagnostic-fixtures-1.0",
        "environment_commit": None,
    }
    results = [
        _metric_value(key, value, context, generated_at)
        for key, value in sorted(case.metrics.items())
    ]
    results.extend(
        _unavailable_metric_value(key, context, generated_at)
        for key in sorted(case.unavailable_metrics)
        if key not in case.metrics
    )
    collection = MetricCollection(
        run_id=str(context["run_id"]),
        metric_version="diagnostic-fixture-1.0",
        results=sorted(results, key=lambda item: item.metric_key),
        unavailable_count=sum(1 for metric in results if metric.status is MetricStatus.UNAVAILABLE),
        partial_count=0,
        generated_at=generated_at,
        input_fingerprint=f"synthetic-{case.case_id}",
    )
    return EvidencePack(
        pack_id=f"evidence-{case.case_id}",
        generated_at=generated_at,
        synthetic=True,
        run_context=context,
        source_bundle_fingerprint=f"synthetic-{case.case_id}",
        validation_summary={
            "status": "accepted" if case.may_import else "rejected",
            "may_import": case.may_import,
            "finding_count": sum(case.validation_counts.values()),
            "counts_by_severity": case.validation_counts,
            "validator_version": "synthetic-diagnostic-fixture",
        },
        evidence_availability=_availability(case.evidence_availability),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=collection,
        excluded_record_counts={},
        warnings=[],
        provenance={
            "case_id": case.case_id,
            "split": case.split,
            "fault_family": case.fault_family,
            "severity": case.severity,
            "synthetic_faults": ",".join(case.synthetic_faults),
        },
    )


def evaluate_fixture_set(
    fixture_set: SyntheticFixtureSet,
    rule_config: RuleSetConfig | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> FaultInjectionEvaluationReport:
    """Evaluate labelled synthetic cases and return engineering metrics."""

    rule_ids = ("R0", "R1", "R2", "R3", "R4", "R5")
    counts = {rule_id: RuleEvaluationCounts(rule_id=rule_id) for rule_id in rule_ids}
    baseline_counts = {rule_id: RuleEvaluationCounts(rule_id=rule_id) for rule_id in rule_ids}
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    split_counts: dict[str, int] = defaultdict(int)
    outcomes: list[CaseEvaluationOutcome] = []
    for case in fixture_set.cases:
        split_counts[case.split] += 1
        report = evaluate_rules(
            evidence_pack_from_case(case, clock=clock), rule_config, clock=clock
        )
        actual_triggered = set(report.triggered_rule_ids)
        expected_triggered = set(case.expected_triggered_rules)
        baseline_triggered = _kpi_baseline(case)
        outcomes.append(
            CaseEvaluationOutcome(
                case_id=case.case_id,
                split=case.split,
                fault_family=case.fault_family,
                severity=case.severity,
                random_seed=case.random_seed,
                expected_triggered_rules=sorted(expected_triggered),
                actual_triggered_rules=sorted(actual_triggered),
                exact_match=actual_triggered == expected_triggered,
            )
        )
        for rule_id, rule_counts in counts.items():
            expected = rule_id in expected_triggered
            actual = rule_id in actual_triggered
            confusion[rule_id][_label(expected, actual)] += 1
            _update_counts(rule_counts, expected=expected, actual=actual)
            _update_counts(
                baseline_counts[rule_id],
                expected=expected,
                actual=rule_id in baseline_triggered,
            )
    per_rule = [_finalise_counts(counts[rule_id]) for rule_id in sorted(counts)]
    baseline_per_rule = [
        _finalise_counts(baseline_counts[rule_id]) for rule_id in sorted(baseline_counts)
    ]
    return FaultInjectionEvaluationReport(
        generated_at=clock(),
        case_count=len(fixture_set.cases),
        split_counts=dict(sorted(split_counts.items())),
        per_rule=per_rule,
        kpi_baseline_per_rule=baseline_per_rule,
        confusion_table={
            rule_id: dict(sorted(values.items())) for rule_id, values in sorted(confusion.items())
        },
        split_summaries=_split_summaries(fixture_set.cases, outcomes, rule_config, clock),
        robustness=_robustness(outcomes),
        case_outcomes=outcomes,
        failure_case_ids=sorted(outcome.case_id for outcome in outcomes if not outcome.exact_match),
        limitations=[
            "Synthetic fault injection validates deterministic implementation behavior, "
            "not external validity.",
            "Thresholds are provisional and were not calibrated on held-out real-world evidence.",
        ],
    )


def build_extended_fixture_set(
    fixture_set: SyntheticFixtureSet,
    *,
    severities: tuple[str, ...] = ("mild", "moderate", "severe"),
    random_seeds: tuple[int, ...] = (1, 2, 3),
) -> SyntheticFixtureSet:
    """Expand declared cases into deterministic severity/seed replicates, including R4/R5."""

    if not severities or not random_seeds:
        raise ValueError("extended fixture matrix requires severities and random seeds")
    if len(set(severities)) != len(severities) or len(set(random_seeds)) != len(random_seeds):
        raise ValueError("extended fixture matrix inputs must not contain duplicates")
    if any(seed < 0 for seed in random_seeds):
        raise ValueError("extended fixture random seeds must be non-negative")
    bases = [*fixture_set.cases, _r4_case(), _r5_case()]
    expanded: list[SyntheticDiagnosticCase] = []
    for case in bases:
        family = case.fault_family if case.fault_family != "unspecified" else _fault_family(case)
        for severity in severities:
            for random_seed in random_seeds:
                expanded.append(
                    case.model_copy(
                        update={
                            "case_id": f"{case.case_id}-{severity}-seed-{random_seed}",
                            "fault_family": family,
                            "severity": severity,
                            "random_seed": random_seed,
                            "metrics": _severity_metrics(
                                case.metrics,
                                case.expected_triggered_rules,
                                severity,
                                random_seed,
                            ),
                            "notes": (
                                f"{case.notes} Deterministic {severity} severity replicate "
                                f"for random seed {random_seed}."
                            ).strip(),
                        }
                    )
                )
    return SyntheticFixtureSet(
        description=(
            fixture_set.description
            + " Expanded deterministically across severity levels and random seeds; includes "
            "synthetic R4/R5 fixtures."
        ),
        cases=expanded,
    )


def _metric_value(
    key: str,
    value: JsonValue,
    context: dict[str, JsonValue],
    computed_at: datetime,
) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=_unit_for_key(key),
        scope="run" if not key.startswith("experiment.") else "experiment",
        dimensions={},
        required_evidence=[],
        missing_evidence=[],
        reason_codes=[],
        warnings=[],
        implementation_version="diagnostic-fixture-1.0",
        run_id=str(context["run_id"]),
        experiment_id=str(context["experiment_id"]),
        seed_id=str(context["seed_id"]),
        algorithm=str(context["algorithm"]),
        checkpoint=None,
        random_seed=int(context["random_seed"]),
        synthetic=True,
        computed_at=computed_at,
        metadata={"fixture_metric": True},
    )


def _unavailable_metric_value(
    key: str,
    context: dict[str, JsonValue],
    computed_at: datetime,
) -> MetricValue:
    metric = _metric_value(key, None, context, computed_at)
    return metric.model_copy(
        update={
            "status": MetricStatus.UNAVAILABLE,
            "reason_codes": [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
            "missing_evidence": [key],
        }
    )


def _availability(values: dict[str, str]) -> EvidenceAvailability:
    defaults = {
        "tasks": EvidenceStatus.AVAILABLE,
        "infrastructure": EvidenceStatus.AVAILABLE,
        "vehicles": EvidenceStatus.UNAVAILABLE,
        "traffic": EvidenceStatus.UNAVAILABLE,
        "trips": EvidenceStatus.UNAVAILABLE,
        "incidents": EvidenceStatus.UNAVAILABLE,
        "diagnosis": EvidenceStatus.AVAILABLE,
    }
    for key, value in values.items():
        defaults[key] = EvidenceStatus(value)
    return EvidenceAvailability.model_validate(defaults)


def _unit_for_key(key: str) -> str:
    if key.endswith(".count") or key.endswith("episode_count"):
        return "count"
    if key.endswith("_s") or key.endswith(".duration_s"):
        return "s"
    if "utilisation" in key or "rate" in key or "dispersion" in key or "gap" in key:
        return "ratio"
    if "queue_length" in key:
        return "tasks"
    return "dimensionless"


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _update_counts(counts: RuleEvaluationCounts, *, expected: bool, actual: bool) -> None:
    if expected:
        counts.support_count += 1
    if expected and actual:
        counts.true_positives += 1
    elif not expected and actual:
        counts.false_positives += 1
    elif expected and not actual:
        counts.false_negatives += 1
    else:
        counts.true_negatives += 1


def _finalise_counts(counts: RuleEvaluationCounts) -> RuleEvaluationCounts:
    counts.precision = _safe_ratio(
        counts.true_positives,
        counts.true_positives + counts.false_positives,
    )
    counts.recall = _safe_ratio(
        counts.true_positives,
        counts.true_positives + counts.false_negatives,
    )
    counts.false_positive_rate = _safe_ratio(
        counts.false_positives,
        counts.false_positives + counts.true_negatives,
    )
    specificity = _safe_ratio(
        counts.true_negatives,
        counts.true_negatives + counts.false_positives,
    )
    counts.specificity = specificity
    return counts


def _split_summaries(
    cases: list[SyntheticDiagnosticCase],
    outcomes: list[CaseEvaluationOutcome],
    rule_config: RuleSetConfig | None,
    clock: Callable[[], datetime],
) -> list[SplitEvaluationSummary]:
    summaries: list[SplitEvaluationSummary] = []
    for split in sorted({case.split for case in cases}):
        split_cases = [case for case in cases if case.split == split]
        split_outcomes = [outcome for outcome in outcomes if outcome.split == split]
        counts = {
            rule_id: RuleEvaluationCounts(rule_id=rule_id)
            for rule_id in ("R0", "R1", "R2", "R3", "R4", "R5")
        }
        for case in split_cases:
            report = evaluate_rules(
                evidence_pack_from_case(case, clock=clock),
                rule_config,
                clock=clock,
            )
            actual = set(report.triggered_rule_ids)
            expected = set(case.expected_triggered_rules)
            for rule_id, rule_counts in counts.items():
                _update_counts(
                    rule_counts,
                    expected=rule_id in expected,
                    actual=rule_id in actual,
                )
        final = [_finalise_counts(value) for value in counts.values()]
        precisions = [value.precision for value in final if value.precision is not None]
        recalls = [value.recall for value in final if value.recall is not None]
        false_positive_numerator = sum(value.false_positives for value in final)
        false_positive_denominator = false_positive_numerator + sum(
            value.true_negatives for value in final
        )
        exact_count = sum(int(outcome.exact_match) for outcome in split_outcomes)
        summaries.append(
            SplitEvaluationSummary(
                split=split,
                case_count=len(split_cases),
                exact_match_count=exact_count,
                exact_match_rate=_safe_ratio(exact_count, len(split_cases)),
                macro_precision=(sum(precisions) / len(precisions) if precisions else None),
                macro_recall=(sum(recalls) / len(recalls) if recalls else None),
                false_positive_rate=_safe_ratio(
                    false_positive_numerator,
                    false_positive_denominator,
                ),
            )
        )
    return summaries


def _robustness(outcomes: list[CaseEvaluationOutcome]) -> list[RobustnessSummary]:
    grouped: dict[tuple[str, str, str], list[bool]] = defaultdict(list)
    for outcome in outcomes:
        for rule_id in outcome.expected_triggered_rules:
            grouped[(outcome.fault_family, rule_id, outcome.severity)].append(
                rule_id in outcome.actual_triggered_rules
            )
    return [
        RobustnessSummary(
            fault_family=family,
            rule_id=rule_id,
            severity=severity,
            replicate_count=len(values),
            trigger_rate=sum(int(value) for value in values) / len(values),
        )
        for (family, rule_id, severity), values in sorted(grouped.items())
    ]


def _kpi_baseline(case: SyntheticDiagnosticCase) -> set[str]:
    """Return a deliberately simple, documented threshold baseline."""

    metrics = case.metrics
    triggered: set[str] = set()
    if not case.may_import or case.evidence_availability.get("diagnosis") == "unavailable":
        triggered.add("R0")
    incomplete = _number(metrics.get("task.incomplete.rate"))
    offload = _number(metrics.get("task.offload.rate"))
    if incomplete is not None and offload is not None and incomplete >= 0.20 and offload <= 0.20:
        triggered.add("R1")
    utilisation = _number(metrics.get("infra.utilisation.p95"))
    queue = _number(metrics.get("infra.queue_length.max"))
    if (utilisation is not None and utilisation >= 0.90) or (queue is not None and queue >= 5):
        triggered.add("R2")
    dispersion = _number(metrics.get("experiment.cross_algorithm_dispersion"))
    if dispersion is not None and dispersion <= 0.02:
        triggered.add("R3")
    jain = _number(metrics.get("infra.load_balance.jain_capacity_normalised"))
    if jain is not None and jain <= 0.80:
        triggered.add("R4")
    gap = _number(metrics.get("experiment.training_validation.max_absolute_gap"))
    if gap is not None and gap >= 0.10:
        triggered.add("R5")
    return triggered


def _number(value: JsonValue) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _fault_family(case: SyntheticDiagnosticCase) -> str:
    if case.expected_triggered_rules:
        return "+".join(sorted(case.expected_triggered_rules))
    return "control"


def _severity_metrics(
    metrics: dict[str, JsonValue],
    expected_rules: list[str],
    severity: str,
    random_seed: int,
) -> dict[str, JsonValue]:
    factors = {"mild": 0.90, "moderate": 1.0, "severe": 1.10}
    if severity not in factors:
        raise ValueError(f"unsupported synthetic severity: {severity}")
    factor = factors[severity]
    digest = hashlib.sha256(f"{severity}:{random_seed}".encode()).digest()
    jitter = (digest[0] / 255.0 - 0.5) * 0.01
    values = dict(metrics)

    def scale(key: str, *, inverse: bool = False, maximum: float | None = None) -> None:
        value = _number(values.get(key))
        if value is None:
            return
        adjusted = value * ((2.0 - factor) if inverse else factor) + jitter
        if maximum is not None:
            adjusted = min(maximum, adjusted)
        values[key] = max(0.0, adjusted)

    if "R1" in expected_rules:
        scale("task.incomplete.rate", maximum=1.0)
        scale("task.offload.rate", inverse=True, maximum=1.0)
    if "R2" in expected_rules:
        scale("infra.utilisation.p95", maximum=1.0)
        scale("infra.queue_length.max")
        scale("infra.saturation.duration_s")
    if "R3" in expected_rules:
        scale("experiment.cross_algorithm_dispersion", inverse=True)
        scale("experiment.always_local_gap_from_best", inverse=True)
    if "R4" in expected_rules:
        scale("infra.load_balance.jain_capacity_normalised", inverse=True, maximum=1.0)
    if "R5" in expected_rules:
        scale("experiment.training_validation.max_absolute_gap")
        scale("experiment.training_validation.mean_absolute_gap")
    return values


def _r4_case() -> SyntheticDiagnosticCase:
    return SyntheticDiagnosticCase(
        case_id="load_imbalance",
        split="held_out",
        fault_family="R4",
        metrics={
            "infra.load_balance.jain_capacity_normalised": 0.62,
            "infra.utilisation.mean": 0.55,
            "infra.observed_rsu.count": 3,
        },
        expected_triggered_rules=["R4"],
        synthetic_faults=["uneven_capacity_normalised_load"],
        notes="Synthetic R4 support pattern.",
    )


def _r5_case() -> SyntheticDiagnosticCase:
    return SyntheticDiagnosticCase(
        case_id="training_validation_drift",
        split="held_out",
        fault_family="R5",
        metrics={
            "experiment.training_validation.pair_count": 3,
            "experiment.training_validation.max_absolute_gap": 0.18,
            "experiment.training_validation.mean_absolute_gap": 0.14,
            "experiment.training_validation.mean_signed_gap": -0.14,
        },
        expected_triggered_rules=["R5"],
        synthetic_faults=["declared_training_validation_gap"],
        notes="Synthetic R5 support pattern with explicit aggregate pair evidence.",
    )


def _label(expected: bool, actual: bool) -> str:
    if expected and actual:
        return "true_positive"
    if not expected and actual:
        return "false_positive"
    if expected and not actual:
        return "false_negative"
    return "true_negative"
