from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import FIXED_TIME, fixed_clock
from traffictwin.canonical.records import InfrastructureRecord, TaskRecord, VehicleStateRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.domain.fairness import (
    DEFAULT_OPERATIONAL_FAIRNESS_POLICY,
    OperationalFairnessPolicy,
)
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.comparison import (
    ComparisonRequest,
    ComparisonStatus,
    compare_metric_collections,
)
from traffictwin.metrics.engine import compute_metrics
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    MetricCollection,
    MetricStatus,
    RunMetricContext,
    UnavailableReason,
)
from traffictwin.metrics.windowed import WindowedMetricConfig, compute_windowed_metrics
from traffictwin.provenance.query import build_provenance_context, get_metric_contributions
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

POLICY_FINGERPRINT = "7518652f882ea2928b4fcc6c500af9fa81e2bf6d88fcb0ed655d7be46ede0e6e"
VEHICLE_KEYS = (
    "task.completion.rate_by_vehicle_tier",
    "fairness.vehicle_tier.completion_rate.max_gap",
    "fairness.vehicle_tier.completion_rate.jain",
)
RSU_KEYS = (
    "fairness.rsu.capacity_normalised_load.by_group",
    "fairness.rsu.capacity_normalised_load.max_gap",
    "infra.load_balance.jain_capacity_normalised",
)


def _context(run_id: str = "run-fairness") -> RunMetricContext:
    return RunMetricContext(
        run_id=run_id,
        experiment_id="exp-fairness",
        seed_id="seed-fairness",
        algorithm="synthetic-test",
        random_seed=7,
        synthetic=True,
    )


def _evidence() -> EvidenceAvailability:
    return EvidenceAvailability(
        tasks=EvidenceStatus.AVAILABLE,
        vehicles=EvidenceStatus.AVAILABLE,
        infrastructure=EvidenceStatus.AVAILABLE,
    )


def _task(task_id: str, vehicle_id: str, completed: bool, row: int) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        vehicle_id=vehicle_id,
        task_class=TaskClass.T1,
        arrival_time_s=float(row),
        deadline_ms=100,
        decision=Decision.LOCAL,
        completed=completed,
        source_file="tasks.csv",
        source_row=row,
    )


def _vehicle(vehicle_id: str, tier: str, row: int) -> VehicleStateRecord:
    return VehicleStateRecord(
        timestamp_s=0,
        vehicle_id=vehicle_id,
        tier=tier,
        source_file="vehicles.csv",
        source_row=row,
    )


def _infra(rsu_id: str, active: int | None, capacity: float, row: int) -> InfrastructureRecord:
    return InfrastructureRecord(
        timestamp_s=float(row),
        rsu_id=rsu_id,
        active_tasks=active,
        capacity=capacity,
        source_file="infra.csv",
        source_row=row,
    )


def _tables() -> CanonicalTables:
    return CanonicalTables(
        tasks=[
            _task("t1", "veh-low", True, 1),
            _task("t2", "veh-low", False, 2),
            _task("t3", "veh-high", True, 3),
            _task("t4", "veh-high", True, 4),
        ],
        vehicles=[
            _vehicle("veh-low", "low", 1),
            _vehicle("veh-high", "high", 2),
        ],
        infrastructure=[
            _infra("rsu-1", 2, 10, 1),
            _infra("rsu-1", 4, 10, 2),
            _infra("rsu-2", 6, 10, 3),
            _infra("rsu-2", 8, 10, 4),
        ],
    )


def _metrics(
    tables: CanonicalTables | None = None, run_id: str = "run-fairness"
) -> MetricCollection:
    return compute_metrics(
        tables or _tables(),
        _context(run_id),
        _evidence(),
        MetricEngineConfig(),
        clock=lambda: FIXED_TIME,
    )


def test_operational_fairness_policy_is_strict_versioned_and_fingerprinted() -> None:
    assert DEFAULT_OPERATIONAL_FAIRNESS_POLICY.fingerprint() == POLICY_FINGERPRINT
    with pytest.raises(ValueError):
        OperationalFairnessPolicy(minimum_group_support=1)


def test_fairness_family_has_exact_group_values_gaps_jain_and_support() -> None:
    metrics = _metrics().by_key()

    assert metrics["task.completion.rate_by_vehicle_tier"].value == {
        "high": 1.0,
        "low": 0.5,
    }
    assert metrics["fairness.vehicle_tier.completion_rate.max_gap"].value == 0.5
    assert metrics["fairness.vehicle_tier.completion_rate.jain"].value == 0.9
    assert metrics["fairness.rsu.capacity_normalised_load.by_group"].value == {
        "rsu-1": pytest.approx(0.3),
        "rsu-2": pytest.approx(0.7),
    }
    assert metrics["fairness.rsu.capacity_normalised_load.max_gap"].value == pytest.approx(0.4)
    assert metrics["infra.load_balance.jain_capacity_normalised"].value == pytest.approx(1 / 1.16)
    for key in (*VEHICLE_KEYS, *RSU_KEYS):
        assert metrics[key].status is MetricStatus.AVAILABLE
        assert metrics[key].metadata["fairness_policy_fingerprint"] == POLICY_FINGERPRINT
        assert metrics[key].metadata["coverage_fraction"] == 1.0
    assert metrics["task.completion.rate_by_vehicle_tier"].metadata["group_support_counts"] == {
        "high": 2,
        "low": 2,
    }


def test_vehicle_tier_family_rejects_incomplete_or_conflicting_membership() -> None:
    tables = _tables()
    tables.tasks.append(_task("t5", "veh-unknown", True, 5))
    metrics = _metrics(tables).by_key()

    for key in VEHICLE_KEYS:
        assert metrics[key].status is MetricStatus.UNAVAILABLE
        assert metrics[key].reason_codes == [UnavailableReason.GROUP_COVERAGE_INSUFFICIENT]
        assert metrics[key].metadata["coverage_fraction"] == 0.8

    conflicting = _tables()
    conflicting.vehicles.append(_vehicle("veh-low", "high", 3))
    conflict_metrics = _metrics(conflicting).by_key()
    assert conflict_metrics[VEHICLE_KEYS[0]].reason_codes == [
        UnavailableReason.GROUP_COVERAGE_INSUFFICIENT
    ]
    assert conflict_metrics[VEHICLE_KEYS[0]].metadata["conflicting_vehicle_count"] == 1


def test_fairness_requires_two_groups_and_two_observations_per_group() -> None:
    one_group = _tables()
    one_group.vehicles = [
        _vehicle("veh-low", "low", 1),
        _vehicle("veh-high", "low", 2),
    ]
    one_group_metrics = _metrics(one_group).by_key()
    assert one_group_metrics[VEHICLE_KEYS[0]].reason_codes == [
        UnavailableReason.INSUFFICIENT_GROUP_COUNT
    ]

    singleton = _tables()
    singleton.tasks = singleton.tasks[:3]
    singleton_metrics = _metrics(singleton).by_key()
    assert singleton_metrics[VEHICLE_KEYS[0]].reason_codes == [
        UnavailableReason.INSUFFICIENT_GROUP_SUPPORT
    ]


def test_rsu_family_rejects_incomplete_capacity_load_coverage() -> None:
    tables = _tables()
    tables.infrastructure[0] = _infra("rsu-1", None, 10, 1)
    metrics = _metrics(tables).by_key()

    for key in RSU_KEYS:
        assert metrics[key].status is MetricStatus.UNAVAILABLE
        assert metrics[key].reason_codes == [UnavailableReason.GROUP_COVERAGE_INSUFFICIENT]
        assert metrics[key].metadata["coverage_fraction"] == 0.75


def test_zero_group_outcomes_keep_gap_but_make_jain_undefined() -> None:
    tables = _tables()
    tables.tasks = [task.model_copy(update={"completed": False}) for task in tables.tasks]
    metrics = _metrics(tables).by_key()

    assert metrics["fairness.vehicle_tier.completion_rate.max_gap"].value == 0.0
    jain = metrics["fairness.vehicle_tier.completion_rate.jain"]
    assert jain.status is MetricStatus.UNAVAILABLE
    assert jain.reason_codes == [UnavailableReason.METRIC_NOT_APPLICABLE]


def test_windowed_fairness_reuses_scope_filtered_evidence_and_policy() -> None:
    series = compute_windowed_metrics(
        _tables(),
        _context(),
        _evidence(),
        WindowedMetricConfig(width_s=60, analysis_start_s=0, analysis_end_s=60),
        clock=lambda: FIXED_TIME,
    )
    metrics = series.slices[0].metrics

    assert metrics is not None
    assert metrics.by_key()["fairness.vehicle_tier.completion_rate.max_gap"].value == 0.5
    assert metrics.by_key()["fairness.rsu.capacity_normalised_load.max_gap"].value == pytest.approx(
        0.4
    )


def test_fairness_comparison_requires_matching_policy_and_group_set() -> None:
    baseline = _metrics(run_id="baseline")
    variation_tables = _tables()
    variation_tables.tasks[1] = variation_tables.tasks[1].model_copy(update={"completed": True})
    variation = _metrics(variation_tables, run_id="variation")
    request = ComparisonRequest(
        baseline_run_id="baseline",
        variation_run_id="variation",
        requested_metric_keys=["fairness.vehicle_tier.completion_rate.max_gap"],
    )

    compatible = compare_metric_collections(baseline, variation, request, clock=fixed_clock)
    assert compatible.comparable_metrics[0].status is ComparisonStatus.AVAILABLE

    changed_results = []
    for metric in variation.results:
        if metric.metric_key == "fairness.vehicle_tier.completion_rate.max_gap":
            metadata = dict(metric.metadata)
            metadata["group_set_fingerprint"] = "different-groups"
            metric = metric.model_copy(update={"metadata": metadata})
        changed_results.append(metric)
    incompatible = compare_metric_collections(
        baseline,
        variation.model_copy(update={"results": changed_results}),
        request,
        clock=fixed_clock,
    )
    assert incompatible.unavailable_comparisons[0].status is ComparisonStatus.UNAVAILABLE
    assert UnavailableReason.COMPARISON_PAIR_INCOMPATIBLE in (
        incompatible.unavailable_comparisons[0].reason_codes
    )


def test_fairness_contribution_ledgers_preserve_group_eligibility(tmp_path: Path) -> None:
    bundle_path = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    context = build_provenance_context(bundle_path, clock=fixed_clock)

    tier = get_metric_contributions(context, "fairness.vehicle_tier.completion_rate.max_gap")
    rsu = get_metric_contributions(context, "fairness.rsu.capacity_normalised_load.max_gap")

    assert tier.complete_row_ledger
    assert tier.included_row_count == tier.candidate_row_count
    assert rsu.complete_row_ledger
    assert rsu.included_row_count == rsu.candidate_row_count == 22
    assert validate_bundle(bundle_path).report.may_import
