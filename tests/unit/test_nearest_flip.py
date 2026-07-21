from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.helpers import FIXED_TIME, fixed_clock
from traffictwin.diagnostics.sensitivity import (
    NearestFlipAnalysis,
    NearestFlipReason,
    NearestFlipStatus,
    analyse_nearest_flip,
    nearest_flip_contract,
)
from traffictwin.domain.fairness import DEFAULT_OPERATIONAL_FAIRNESS_POLICY
from traffictwin.domain.spatial import DEFAULT_TASK_RSU_TARGET_CONTRACT
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
        run_id="run-nearest",
        experiment_id="exp-nearest",
        seed_id="seed-nearest",
        algorithm="test",
        random_seed=7,
        synthetic=True,
        computed_at=FIXED_TIME,
        metadata=metadata or {},
    )


def _pack(*metrics: MetricValue) -> EvidencePack:
    return EvidencePack(
        pack_id="pack-nearest",
        generated_at=FIXED_TIME,
        synthetic=True,
        run_context={"run_id": "run-nearest"},
        source_bundle_fingerprint="source-nearest",
        validation_summary={"may_import": True, "counts_by_severity": {}},
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.AVAILABLE,
            vehicles=EvidenceStatus.AVAILABLE,
            infrastructure=EvidenceStatus.AVAILABLE,
            diagnosis=EvidenceStatus.AVAILABLE,
        ),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=MetricCollection(
            run_id="run-nearest",
            metric_version="test",
            results=list(metrics),
            unavailable_count=0,
            partial_count=0,
            generated_at=FIXED_TIME,
        ),
    )


def _synthetic_pack(tmp_path: Path, preset: str) -> EvidencePack:
    result = validate_bundle(write_synthetic_bundle(preset_config(preset), tmp_path / preset))
    collection = compute_metrics_for_bundle(result, clock=fixed_clock)
    return build_evidence_pack(result, collection, clock=fixed_clock)


def _r5_pack(*, pair_count: int = 3, maximum_gap: float = 0.05) -> EvidencePack:
    return _pack(
        _metric("experiment.training_validation.pair_count", pair_count, "count"),
        _metric("experiment.training_validation.max_absolute_gap", maximum_gap, "ratio"),
    )


def _tier_pack(*, gap: float = 0.5, support: int = 3) -> EvidencePack:
    policy = DEFAULT_OPERATIONAL_FAIRNESS_POLICY
    return _pack(
        _metric(
            "fairness.vehicle_tier.completion_rate.max_gap",
            gap,
            "ratio",
            {
                "fairness_policy_version": policy.schema_version,
                "fairness_policy_fingerprint": policy.fingerprint(),
                "group_dimension": "vehicle_tier",
                "coverage_fraction": 1.0,
                "attribute_interpretation": ("operational_groups_only_not_protected_attributes"),
                "group_count": 2,
                "group_support_counts": {"high": support, "low": support},
            },
        )
    )


def _target_pack() -> EvidencePack:
    contract = DEFAULT_TASK_RSU_TARGET_CONTRACT
    return _pack(
        _metric(
            "spatial.rsu.task.completion_rate_by_target",
            {"rsu-a": 0.4, "rsu-b": 0.8},
            "ratio",
            {
                "task_rsu_target_contract_version": contract.schema_version,
                "task_rsu_target_contract_fingerprint": contract.fingerprint(),
                "target_semantics": contract.target_semantics,
                "target_join_method": contract.join_method,
                "coverage_fraction": 1.0,
                "attribution_interpretation": contract.attribution_interpretation,
                "group_count": 2,
                "group_support_counts": {"rsu-a": 4, "rsu-b": 4},
            },
        )
    )


def test_nearest_flip_contract_pins_supported_single_boundary_families() -> None:
    contract = nearest_flip_contract()

    assert contract.capability == "DIA-05"
    assert contract.analysis_version == "1.0"
    assert contract.supported_threshold_parameters == {
        "R5": "r5.maximum_absolute_gap",
        "R7": "r7.minimum_outcome_gap",
        "R8": "r8.minimum_energy_per_completed_task_j",
    }
    assert contract.discrete_constraint_policy == "report_but_never_change"
    assert "R6" in contract.unsupported_rule_ids


def test_r8_nearest_flip_is_exact_verified_and_does_not_mutate_inputs(tmp_path: Path) -> None:
    pack = _synthetic_pack(tmp_path, "baseline")
    config = RuleSetConfig()
    original_pack_fingerprint = pack.fingerprint()
    original_config = config.model_dump(mode="json")

    analysis = analyse_nearest_flip(pack, "r8", config, clock=fixed_clock)

    assert analysis.status is NearestFlipStatus.AVAILABLE
    assert analysis.reason_code is NearestFlipReason.AVAILABLE
    assert analysis.source_status is RuleStatus.NOT_TRIGGERED
    assert analysis.candidate_status is RuleStatus.TRIGGERED
    assert analysis.tie_count == 1
    candidate = analysis.candidates[0]
    assert candidate.parameter_path == "r8.minimum_energy_per_completed_task_j"
    assert candidate.current_value == 1.5
    assert candidate.flip_value == pytest.approx(0.9941935483870968)
    assert candidate.absolute_delta == pytest.approx(1.5 - candidate.flip_value)
    assert candidate.unit == "J/task"
    assert candidate.candidate_rule_config["minimum_completed_tasks"] == 10
    assert analysis.constraints[0].satisfied is True
    assert analysis.current_result_fingerprint != analysis.candidate_result_fingerprint
    assert pack.fingerprint() == original_pack_fingerprint
    assert config.model_dump(mode="json") == original_config


def test_nearest_flip_fingerprint_normalises_only_analysis_time(tmp_path: Path) -> None:
    pack = _synthetic_pack(tmp_path, "baseline")
    later = datetime(2030, 1, 1, tzinfo=UTC)

    first = analyse_nearest_flip(pack, "R8", clock=fixed_clock)
    second = analyse_nearest_flip(pack, "R8", clock=lambda: later)

    assert first.analysis_id == second.analysis_id
    assert first.analysed_at != second.analysed_at
    assert first.fingerprint() == second.fingerprint()
    NearestFlipAnalysis.model_validate_json(first.to_json())


def test_r8_does_not_lower_thin_completed_task_support(tmp_path: Path) -> None:
    pack = _synthetic_pack(tmp_path, "baseline")
    config = RuleSetConfig.model_validate({"r8": {"minimum_completed_tasks": 100}})

    analysis = analyse_nearest_flip(pack, "R8", config, clock=fixed_clock)

    assert analysis.status is NearestFlipStatus.NOT_APPLICABLE
    assert analysis.reason_code is NearestFlipReason.DISCRETE_CONSTRAINT_UNMET
    assert analysis.constraints[0].observed_value == 31
    assert analysis.constraints[0].required_minimum == 100
    assert analysis.candidates == []


def test_r5_nearest_flip_uses_gap_and_preserves_pair_support() -> None:
    analysis = analyse_nearest_flip(_r5_pack(), "R5", clock=fixed_clock)

    assert analysis.status is NearestFlipStatus.AVAILABLE
    assert analysis.candidates[0].parameter_path == "r5.maximum_absolute_gap"
    assert analysis.candidates[0].flip_value == pytest.approx(0.05)
    assert analysis.candidates[0].absolute_delta == pytest.approx(0.05)
    assert analysis.constraints[0].observed_value == 3
    assert analysis.constraints[0].satisfied is True


def test_r5_with_too_few_pairs_has_no_flip() -> None:
    analysis = analyse_nearest_flip(
        _r5_pack(pair_count=1),
        "R5",
        clock=fixed_clock,
    )

    assert analysis.status is NearestFlipStatus.NOT_APPLICABLE
    assert analysis.reason_code is NearestFlipReason.DISCRETE_CONSTRAINT_UNMET
    assert analysis.constraints[0].satisfied is False


def test_r7_tier_and_target_dimensions_use_the_admitted_rule_observation() -> None:
    tier_config = RuleSetConfig.model_validate({"r7": {"minimum_outcome_gap": 0.6}})
    target_config = RuleSetConfig.model_validate(
        {
            "r7": {
                "dimension": "target_rsu_completion",
                "minimum_outcome_gap": 0.6,
            }
        }
    )

    tier = analyse_nearest_flip(_tier_pack(), "R7", tier_config, clock=fixed_clock)
    target = analyse_nearest_flip(_target_pack(), "R7", target_config, clock=fixed_clock)

    assert tier.status is NearestFlipStatus.AVAILABLE
    assert tier.candidates[0].flip_value == pytest.approx(0.5)
    assert [item.observed_value for item in tier.constraints] == [2, 3]
    assert target.status is NearestFlipStatus.AVAILABLE
    assert target.candidates[0].flip_value == pytest.approx(0.4)
    assert target.candidates[0].candidate_rule_config["dimension"] == ("target_rsu_completion")


def test_triggered_insufficient_disabled_and_unsupported_rules_are_explicit(
    tmp_path: Path,
) -> None:
    triggered = analyse_nearest_flip(
        _synthetic_pack(tmp_path, "infrastructure_bottleneck"),
        "R8",
        clock=fixed_clock,
    )
    insufficient = analyse_nearest_flip(_pack(), "R5", clock=fixed_clock)
    disabled = analyse_nearest_flip(
        _synthetic_pack(tmp_path, "baseline"),
        "R8",
        RuleSetConfig.model_validate({"r8": {"enabled": False}}),
        clock=fixed_clock,
    )
    unsupported = analyse_nearest_flip(_pack(), "R4", clock=fixed_clock)

    assert triggered.reason_code is NearestFlipReason.SOURCE_RULE_NOT_NOT_TRIGGERED
    assert triggered.source_status is RuleStatus.TRIGGERED
    assert insufficient.source_status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert disabled.reason_code is NearestFlipReason.RULE_DISABLED
    assert disabled.current_result_fingerprint is None
    assert unsupported.status is NearestFlipStatus.UNSUPPORTED
    assert unsupported.reason_code is NearestFlipReason.UNSUPPORTED_RULE
    assert unsupported.source_status is None
