"""Synthetic fault-injection evaluation utilities for deterministic rules."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
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
    support_count: int = 0
    precision: float | None = None
    recall: float | None = None


class FaultInjectionEvaluationReport(BaseModel):
    """Evaluation summary for labelled synthetic diagnostic cases."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime
    case_count: int
    split_counts: dict[str, int]
    per_rule: list[RuleEvaluationCounts]
    confusion_table: dict[str, dict[str, int]]
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
        "random_seed": 7,
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

    counts: dict[str, RuleEvaluationCounts] = {
        rule_id: RuleEvaluationCounts(rule_id=rule_id) for rule_id in ("R0", "R1", "R2", "R3")
    }
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    split_counts: dict[str, int] = defaultdict(int)
    for case in fixture_set.cases:
        split_counts[case.split] += 1
        report = evaluate_rules(
            evidence_pack_from_case(case, clock=clock), rule_config, clock=clock
        )
        actual_triggered = set(report.triggered_rule_ids)
        expected_triggered = set(case.expected_triggered_rules)
        for rule_id, rule_counts in counts.items():
            expected = rule_id in expected_triggered
            actual = rule_id in actual_triggered
            confusion[rule_id][_label(expected, actual)] += 1
            if expected:
                rule_counts.support_count += 1
            if expected and actual:
                rule_counts.true_positives += 1
            elif not expected and actual:
                rule_counts.false_positives += 1
            elif expected and not actual:
                rule_counts.false_negatives += 1
    per_rule: list[RuleEvaluationCounts] = []
    for rule_id in sorted(counts):
        rule_counts = counts[rule_id]
        rule_counts.precision = _safe_ratio(
            rule_counts.true_positives,
            rule_counts.true_positives + rule_counts.false_positives,
        )
        rule_counts.recall = _safe_ratio(
            rule_counts.true_positives,
            rule_counts.true_positives + rule_counts.false_negatives,
        )
        per_rule.append(rule_counts)
    return FaultInjectionEvaluationReport(
        generated_at=clock(),
        case_count=len(fixture_set.cases),
        split_counts=dict(sorted(split_counts.items())),
        per_rule=per_rule,
        confusion_table={
            rule_id: dict(sorted(values.items())) for rule_id, values in sorted(confusion.items())
        },
        limitations=[
            "Synthetic fault injection validates deterministic implementation behavior, "
            "not external validity.",
            "Thresholds are provisional and were not calibrated on held-out real-world evidence.",
        ],
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
        random_seed=7,
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


def _label(expected: bool, actual: bool) -> str:
    if expected and actual:
        return "true_positive"
    if not expected and actual:
        return "false_positive"
    if expected and not actual:
        return "false_negative"
    return "true_negative"
