from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.helpers import FIXED_TIME, fixed_clock
from traffictwin.diagnostics.threshold_sweep import (
    ThresholdSensitivityReport,
    ThresholdSweepReason,
    ThresholdSweepRequest,
    ThresholdSweepStatus,
    config_for_evaluated_point,
    evaluate_threshold_sweep,
    threshold_sensitivity_contract,
)
from traffictwin.domain.fairness import DEFAULT_OPERATIONAL_FAIRNESS_POLICY
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.models import RuleStatus
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def _metric(
    key: str,
    value: object,
    unit: str,
    metadata: dict[str, object] | None = None,
) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        scope="run",
        implementation_version="test",
        run_id="run-sweep",
        experiment_id="exp-sweep",
        seed_id="seed-sweep",
        algorithm="test",
        random_seed=7,
        synthetic=True,
        computed_at=FIXED_TIME,
        metadata=metadata or {},
    )


def _pack(*metrics: MetricValue) -> EvidencePack:
    return EvidencePack(
        pack_id="pack-sweep",
        generated_at=FIXED_TIME,
        synthetic=True,
        run_context={"run_id": "run-sweep"},
        source_bundle_fingerprint="source-sweep",
        validation_summary={"may_import": True, "counts_by_severity": {}},
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.AVAILABLE,
            vehicles=EvidenceStatus.AVAILABLE,
            infrastructure=EvidenceStatus.AVAILABLE,
            diagnosis=EvidenceStatus.AVAILABLE,
        ),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=MetricCollection(
            run_id="run-sweep",
            metric_version="test",
            results=list(metrics),
            unavailable_count=0,
            partial_count=0,
            generated_at=FIXED_TIME,
        ),
    )


def _synthetic_pack(tmp_path: Path, preset: str = "baseline") -> EvidencePack:
    result = validate_bundle(write_synthetic_bundle(preset_config(preset), tmp_path / preset))
    collection = compute_metrics_for_bundle(result, clock=fixed_clock)
    return build_evidence_pack(result, collection, clock=fixed_clock)


def _r5_pack() -> EvidencePack:
    return _pack(
        _metric("experiment.training_validation.pair_count", 3, "count"),
        _metric("experiment.training_validation.max_absolute_gap", 0.05, "ratio"),
    )


def _r7_pack() -> EvidencePack:
    policy = DEFAULT_OPERATIONAL_FAIRNESS_POLICY
    return _pack(
        _metric(
            "fairness.vehicle_tier.completion_rate.max_gap",
            0.5,
            "ratio",
            {
                "fairness_policy_version": policy.schema_version,
                "fairness_policy_fingerprint": policy.fingerprint(),
                "group_dimension": "vehicle_tier",
                "coverage_fraction": 1.0,
                "attribute_interpretation": ("operational_groups_only_not_protected_attributes"),
                "group_count": 2,
                "group_support_counts": {"high": 3, "low": 3},
            },
        )
    )


def test_threshold_sensitivity_contract_pins_bounded_non_persistent_grid() -> None:
    contract = threshold_sensitivity_contract()

    assert contract.capability == "DIA-06"
    assert contract.supported_threshold_parameters == {
        "R5": "r5.maximum_absolute_gap",
        "R7": "r7.minimum_outcome_gap",
        "R8": "r8.minimum_energy_per_completed_task_j",
    }
    assert contract.grid_method == "inclusive_linear_v1"
    assert contract.maximum_point_count == 101
    assert "session_only" in contract.persistence_policy


def test_r8_sweep_retains_full_grid_stability_boundaries_and_exact_flip(
    tmp_path: Path,
) -> None:
    pack = _synthetic_pack(tmp_path)
    config = RuleSetConfig()
    request = ThresholdSweepRequest(
        rule_id="r8",
        minimum_threshold=0.0,
        maximum_threshold=2.0,
        point_count=4,
    )
    pack_fingerprint = pack.fingerprint()
    config_payload = config.model_dump(mode="json")

    report = evaluate_threshold_sweep(pack, request, config, clock=fixed_clock)

    assert report.status is ThresholdSweepStatus.AVAILABLE
    assert report.reason_code is ThresholdSweepReason.AVAILABLE
    assert report.rule_id == "R8"
    assert report.source_threshold == 1.5
    assert report.source_threshold_injected is True
    assert report.requested_point_count == 4
    assert report.evaluated_point_count == 5
    assert [point.threshold for point in report.points] == [
        0.0,
        0.666666666667,
        1.333333333333,
        1.5,
        2.0,
    ]
    assert [point.status for point in report.points] == [
        RuleStatus.TRIGGERED,
        RuleStatus.TRIGGERED,
        RuleStatus.NOT_TRIGGERED,
        RuleStatus.NOT_TRIGGERED,
        RuleStatus.NOT_TRIGGERED,
    ]
    assert report.stability is not None
    assert report.stability.triggered_fraction == pytest.approx(0.4)
    assert report.stability.trigger_transition_count == 1
    assert report.stability.triggered_membership_monotonic_prefix is True
    assert len(report.flip_boundaries) == 1
    assert report.flip_boundaries[0].transition == "triggered_to_not_triggered"
    assert report.flip_boundaries[0].interpretation == "sampled_interval_not_exact_boundary"
    assert report.nearest_flip is not None
    assert report.nearest_flip.status.value == "available"
    assert report.nearest_flip.candidates[0].flip_value == pytest.approx(0.9941935483870968)
    assert pack.fingerprint() == pack_fingerprint
    assert config.model_dump(mode="json") == config_payload


def test_thin_support_retains_conflicting_and_not_triggered_points_without_flip(
    tmp_path: Path,
) -> None:
    pack = _synthetic_pack(tmp_path)
    config = RuleSetConfig.model_validate({"r8": {"minimum_completed_tasks": 100}})
    request = ThresholdSweepRequest(
        rule_id="R8",
        minimum_threshold=0.0,
        maximum_threshold=2.0,
        point_count=3,
    )

    report = evaluate_threshold_sweep(pack, request, config, clock=fixed_clock)

    assert report.stability is not None
    assert report.stability.status_counts == {
        "conflicting_evidence": 1,
        "not_triggered": 3,
    }
    assert report.stability.triggered_point_count == 0
    assert report.flip_boundaries == []
    assert report.nearest_flip is not None
    assert report.nearest_flip.reason_code.value == "DISCRETE_CONSTRAINT_UNMET"


@pytest.mark.parametrize(
    ("pack", "sweep_request", "expected_statuses"),
    [
        (
            _r5_pack(),
            ThresholdSweepRequest(
                rule_id="R5", minimum_threshold=0.0, maximum_threshold=0.1, point_count=3
            ),
            ["triggered", "triggered", "not_triggered"],
        ),
        (
            _r7_pack(),
            ThresholdSweepRequest(
                rule_id="R7", minimum_threshold=0.0, maximum_threshold=1.0, point_count=3
            ),
            ["triggered", "triggered", "triggered", "not_triggered"],
        ),
    ],
)
def test_r5_and_r7_sweeps_use_their_contract_axis(
    pack: EvidencePack,
    sweep_request: ThresholdSweepRequest,
    expected_statuses: list[str],
) -> None:
    report = evaluate_threshold_sweep(pack, sweep_request, clock=fixed_clock)

    assert [point.status.value for point in report.points] == expected_statuses
    assert report.parameter_path is not None
    assert report.points[0].rule_config[report.parameter_path.split(".")[-1]] == 0.0
    assert report.fixed_rule_config


def test_unsupported_disabled_and_invalid_requests_are_explicit() -> None:
    unsupported = evaluate_threshold_sweep(
        _r5_pack(),
        ThresholdSweepRequest(
            rule_id="R4", minimum_threshold=0.0, maximum_threshold=1.0, point_count=2
        ),
        clock=fixed_clock,
    )
    disabled_config = RuleSetConfig.model_validate({"r5": {"enabled": False}})
    disabled = evaluate_threshold_sweep(
        _r5_pack(),
        ThresholdSweepRequest(
            rule_id="R5", minimum_threshold=0.0, maximum_threshold=1.0, point_count=2
        ),
        disabled_config,
        clock=fixed_clock,
    )

    assert unsupported.status is ThresholdSweepStatus.UNSUPPORTED
    assert unsupported.points == []
    assert disabled.status is ThresholdSweepStatus.NOT_APPLICABLE
    assert disabled.reason_code is ThresholdSweepReason.RULE_DISABLED
    with pytest.raises(ValidationError):
        ThresholdSweepRequest(
            rule_id="R8", minimum_threshold=1.0, maximum_threshold=1.0, point_count=2
        )
    with pytest.raises(ValueError, match="R7 maximum_threshold"):
        evaluate_threshold_sweep(
            _r7_pack(),
            ThresholdSweepRequest(
                rule_id="R7", minimum_threshold=0.0, maximum_threshold=1.1, point_count=2
            ),
            clock=fixed_clock,
        )


def test_explicit_point_export_requires_the_exact_source_config_and_grid_point() -> None:
    source = RuleSetConfig.model_validate({"r5": {"minimum_pair_count": 3}})
    report = evaluate_threshold_sweep(
        _r5_pack(),
        ThresholdSweepRequest(
            rule_id="R5", minimum_threshold=0.0, maximum_threshold=0.2, point_count=3
        ),
        source,
        clock=fixed_clock,
    )

    exported = config_for_evaluated_point(report, source, 0.2)

    assert exported.r5.maximum_absolute_gap == 0.2
    assert exported.r5.minimum_pair_count == 3
    assert source.r5.maximum_absolute_gap == 0.1
    with pytest.raises(ValueError, match="not evaluated"):
        config_for_evaluated_point(report, source, 0.19)
    with pytest.raises(ValueError, match="does not match"):
        config_for_evaluated_point(report, RuleSetConfig(), 0.2)


def test_sweep_fingerprint_normalises_report_and_nearest_flip_timestamps(
    tmp_path: Path,
) -> None:
    pack = _synthetic_pack(tmp_path)
    request = ThresholdSweepRequest(
        rule_id="R8",
        minimum_threshold=0.0,
        maximum_threshold=2.0,
        point_count=3,
    )
    later = datetime(2030, 1, 1, tzinfo=UTC)

    first = evaluate_threshold_sweep(pack, request, clock=fixed_clock)
    second = evaluate_threshold_sweep(pack, request, clock=lambda: later)
    lower_case = evaluate_threshold_sweep(
        pack,
        request.model_copy(update={"rule_id": "r8"}),
        clock=fixed_clock,
    )

    assert first.analysis_id == second.analysis_id
    assert first.analysis_id == lower_case.analysis_id
    assert first.analysed_at != second.analysed_at
    assert first.fingerprint() == second.fingerprint()
    assert first.fingerprint() == lower_case.fingerprint()
    ThresholdSensitivityReport.model_validate_json(first.to_json())
