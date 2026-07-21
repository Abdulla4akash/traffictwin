from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.helpers import FIXED_TIME
from traffictwin.canonical.records import TaskRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.diagnostics.temporal import temporal_diagnosis_contract
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.builder import attach_temporal_evidence
from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import (
    TemporalEvidenceConfig,
    TemporalEvidenceReason,
    TemporalEvidenceStatus,
    TemporalPointEligibility,
    build_temporal_evidence,
)
from traffictwin.metrics.engine import compute_metrics
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection, RunMetricContext
from traffictwin.metrics.windowed import (
    WindowedMetricConfig,
    WindowedMetricSeries,
    compute_windowed_metrics,
)
from traffictwin.rules.config import R6Config, RuleSetConfig
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleResult, RuleStatus

MISS_KEY = "task.deadline_miss.completed_observed_rate"
COMPLETION_KEY = "task.completion.rate"


def _context() -> RunMetricContext:
    return RunMetricContext(
        run_id="run-r6",
        experiment_id="experiment-r6",
        seed_id="seed-r6",
        algorithm="test-policy",
        random_seed=6,
        synthetic=True,
        source_bundle_fingerprint="source-r6",
    )


def _availability() -> EvidenceAvailability:
    return EvidenceAvailability(
        tasks=EvidenceStatus.AVAILABLE,
        diagnosis=EvidenceStatus.AVAILABLE,
    )


def _deadline_tables(rates: list[float | None]) -> CanonicalTables:
    tasks: list[TaskRecord] = []
    row = 2
    for window, rate in enumerate(rates):
        if rate is None:
            continue
        misses = round(rate * 10)
        for index in range(10):
            arrival = window * 10 + 1 + index / 100
            tasks.append(
                TaskRecord(
                    task_id=f"task-{window}-{index}",
                    vehicle_id=f"vehicle-{index}",
                    task_class=TaskClass.T1,
                    arrival_time_s=arrival,
                    deadline_ms=100,
                    decision=Decision.LOCAL,
                    completed=True,
                    completion_time_s=arrival + 0.2,
                    latency_ms=200 if index < misses else 50,
                    source_file="tasks.csv",
                    source_row=row,
                )
            )
            row += 1
    return CanonicalTables(tasks=tasks)


def _completion_tables(rates: list[float]) -> CanonicalTables:
    tasks: list[TaskRecord] = []
    row = 2
    for window, rate in enumerate(rates):
        completed = round(rate * 10)
        for index in range(10):
            arrival = window * 10 + 1 + index / 100
            is_completed = index < completed
            tasks.append(
                TaskRecord(
                    task_id=f"completion-{window}-{index}",
                    vehicle_id=f"vehicle-{index}",
                    task_class=TaskClass.T1,
                    arrival_time_s=arrival,
                    deadline_ms=100,
                    decision=Decision.LOCAL,
                    completed=is_completed,
                    completion_time_s=arrival + 0.05 if is_completed else None,
                    latency_ms=50 if is_completed else None,
                    source_file="tasks.csv",
                    source_row=row,
                )
            )
            row += 1
    return CanonicalTables(tasks=tasks)


def _series(
    tables: CanonicalTables,
    *,
    start_s: float = 0,
    end_s: float = 60,
    clock_time: datetime = FIXED_TIME,
) -> WindowedMetricSeries:
    return compute_windowed_metrics(
        tables,
        _context(),
        _availability(),
        WindowedMetricConfig(
            width_s=10,
            analysis_start_s=start_s,
            analysis_end_s=end_s,
        ),
        clock=lambda: clock_time,
    )


def _base_pack(tables: CanonicalTables) -> EvidencePack:
    metrics = compute_metrics(
        tables,
        _context(),
        _availability(),
        clock=lambda: FIXED_TIME,
    )
    return EvidencePack(
        pack_id="evidence-r6",
        generated_at=FIXED_TIME,
        synthetic=True,
        run_context={"run_id": "run-r6"},
        source_bundle_fingerprint="source-r6",
        validation_summary={"may_import": True, "counts_by_severity": {}},
        evidence_availability=_availability(),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=metrics,
    )


def _r6_only_config(**r6_updates: object) -> RuleSetConfig:
    return RuleSetConfig.model_validate(
        {
            "r0": {"enabled": False},
            "r1": {"enabled": False},
            "r2": {"enabled": False},
            "r3": {"enabled": False},
            "r4": {"enabled": False},
            "r5": {"enabled": False},
            "r6": {"enabled": True, **r6_updates},
        }
    )


def _evaluate(
    tables: CanonicalTables,
    temporal_config: TemporalEvidenceConfig,
    **r6_updates: object,
) -> tuple[EvidencePack, RuleResult]:
    pack = attach_temporal_evidence(_base_pack(tables), _series(tables), temporal_config)
    report = evaluate_rules(pack, _r6_only_config(**r6_updates), clock=lambda: FIXED_TIME)
    return pack, report.results[0]


def test_temporal_evidence_preserves_grid_direction_event_and_fingerprint() -> None:
    tables = _deadline_tables([0.1, 0.1, 0.3, 0.4, 0.1, 0.1])
    config = TemporalEvidenceConfig(metric_key=MISS_KEY, event_time_s=20, event_label="incident")
    first = build_temporal_evidence(_series(tables), config)
    shifted_clock = datetime(2026, 7, 20, 13, 0, tzinfo=UTC)
    second = build_temporal_evidence(_series(tables, clock_time=shifted_clock), config)

    assert first.status is TemporalEvidenceStatus.AVAILABLE
    assert first.higher_is_better is False
    assert first.event is not None
    assert first.event.event_window_ordinal == 2
    assert first.points[2].value == pytest.approx(0.3)
    assert first.fingerprint() == second.fingerprint()

    contract = temporal_diagnosis_contract()
    assert contract.ruleset_version == "1.3"
    assert contract.missing_interval_policy == "visible_breaks_consecutive_runs_never_zero"
    assert "recovered" in contract.recovery_states


def test_r6_detects_sustained_deterioration_and_recovery() -> None:
    tables = _deadline_tables([0.1, 0.1, 0.3, 0.4, 0.1, 0.1])
    pack, result = _evaluate(
        tables,
        TemporalEvidenceConfig(metric_key=MISS_KEY, event_time_s=20, event_label="incident"),
    )

    assert result.status is RuleStatus.TRIGGERED
    assert result.metadata["baseline_mean"] == pytest.approx(0.1)
    assert result.metadata["episode_start_ordinal"] == 2
    assert result.metadata["episode_end_ordinal"] == 3
    assert result.metadata["recovery_assessment"] == "recovered"
    assert result.metadata["recovery_window_ordinal"] == 4
    assert pack.temporal_evidence is not None
    assert result.metadata["temporal_evidence_fingerprint"] == (
        pack.temporal_evidence.fingerprint()
    )


def test_r6_uses_declared_higher_is_better_direction() -> None:
    tables = _completion_tables([1.0, 1.0, 0.7, 0.6, 1.0, 1.0])
    _, result = _evaluate(
        tables,
        TemporalEvidenceConfig(
            metric_key=COMPLETION_KEY,
            event_time_s=20,
            event_label="demand change",
        ),
        minimum_deterioration_delta=0.2,
    )

    assert result.status is RuleStatus.TRIGGERED
    assert result.metadata["higher_is_better"] is True
    assert result.metadata["peak_adverse_delta"] == pytest.approx(0.4)
    assert result.metadata["recovery_assessment"] == "recovered"


def test_missing_observation_is_not_deterioration_or_a_supported_non_trigger() -> None:
    tables = _deadline_tables([0.1, 0.1, None, 0.4, 0.1, 0.1])
    _, result = _evaluate(tables, TemporalEvidenceConfig(metric_key=MISS_KEY))

    assert result.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert result.metadata["episode_start_ordinal"] is None
    assert result.metadata["missing_observation_ordinals"] == "2"
    assert any("window ordinals: 2" in item for item in result.missing_evidence)


def test_missing_exact_baseline_is_insufficient() -> None:
    tables = _deadline_tables([0.1, None, 0.3, 0.4, 0.1, 0.1])
    _, result = _evaluate(
        tables,
        TemporalEvidenceConfig(metric_key=MISS_KEY, event_time_s=20),
    )

    assert result.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert any("baseline windows" in item for item in result.missing_evidence)


def test_general_degradation_without_event_does_not_claim_recovery() -> None:
    tables = _deadline_tables([0.1, 0.1, 0.3, 0.4, 0.1, 0.1])
    _, result = _evaluate(tables, TemporalEvidenceConfig(metric_key=MISS_KEY))

    assert result.status is RuleStatus.TRIGGERED
    assert result.metadata["recovery_assessment"] == "not_applicable_no_event"
    assert any("event context" in item for item in result.missing_evidence)


def test_complete_stable_series_is_not_triggered() -> None:
    tables = _deadline_tables([0.1, 0.1, 0.1, 0.2, 0.1, 0.1])
    _, result = _evaluate(tables, TemporalEvidenceConfig(metric_key=MISS_KEY))

    assert result.status is RuleStatus.NOT_TRIGGERED
    assert result.metadata["episode_start_ordinal"] is None


def test_event_outside_range_and_unknown_direction_remain_unavailable() -> None:
    tables = _deadline_tables([0.1, 0.1, 0.3, 0.4, 0.1, 0.1])
    outside = build_temporal_evidence(
        _series(tables),
        TemporalEvidenceConfig(metric_key=MISS_KEY, event_time_s=60),
    )
    count_metric = build_temporal_evidence(
        _series(tables),
        TemporalEvidenceConfig(metric_key="task.generated.count"),
    )

    assert outside.status is TemporalEvidenceStatus.UNAVAILABLE
    assert TemporalEvidenceReason.EVENT_OUTSIDE_ANALYSIS_RANGE in outside.reason_codes
    assert count_metric.status is TemporalEvidenceStatus.UNAVAILABLE
    assert TemporalEvidenceReason.METRIC_DIRECTION_UNDECLARED in count_metric.reason_codes


def test_low_coverage_and_pack_mismatch_stay_explicit() -> None:
    tables = _deadline_tables([0.1, 0.1, 0.3, 0.4, 0.1, 0.1])
    partial = build_temporal_evidence(
        _series(tables, start_s=5, end_s=55),
        TemporalEvidenceConfig(metric_key=MISS_KEY, minimum_window_coverage=1.0),
    )
    pack = _base_pack(tables)
    mismatched_collection: MetricCollection = pack.metric_collection.model_copy(
        update={"run_id": "another-run"},
        deep=True,
    )
    mismatched = attach_temporal_evidence(
        pack.model_copy(update={"metric_collection": mismatched_collection}, deep=True),
        _series(tables),
        TemporalEvidenceConfig(metric_key=MISS_KEY),
    )

    assert partial.points[0].eligibility is TemporalPointEligibility.LOW_COVERAGE
    assert partial.points[-1].eligibility is TemporalPointEligibility.LOW_COVERAGE
    assert mismatched.temporal_evidence is not None
    assert mismatched.temporal_evidence.status is TemporalEvidenceStatus.INVALID
    assert TemporalEvidenceReason.RUN_MISMATCH in mismatched.temporal_evidence.reason_codes


def test_r6_configuration_rejects_impossible_minimums() -> None:
    with pytest.raises(ValidationError, match="cover baseline and sustained"):
        R6Config(
            baseline_window_count=3,
            sustained_window_count=2,
            minimum_evaluable_windows=4,
        )
    with pytest.raises(ValidationError, match="cover the sustained"):
        R6Config(
            sustained_window_count=3,
            minimum_evaluable_windows=5,
            recovery_horizon_windows=2,
        )
