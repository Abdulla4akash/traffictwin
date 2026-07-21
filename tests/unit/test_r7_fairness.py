from __future__ import annotations

import pytest

from tests.helpers import FIXED_TIME
from traffictwin.domain.fairness import DEFAULT_OPERATIONAL_FAIRNESS_POLICY
from traffictwin.domain.spatial import DEFAULT_TASK_RSU_TARGET_CONTRACT
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue
from traffictwin.rules.config import R7Config, RuleSetConfig
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleResult, RuleStatus
from traffictwin.rules.r7_fairness import r7_rule_definition

TIER_KEY = "fairness.vehicle_tier.completion_rate.max_gap"
TARGET_KEY = "spatial.rsu.task.completion_rate_by_target"


def _metric(key: str, value: object, metadata: dict[str, object]) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit="ratio",
        scope="run",
        implementation_version="test",
        run_id="run-r7",
        experiment_id="exp-r7",
        seed_id="seed-r7",
        algorithm="test",
        random_seed=7,
        synthetic=True,
        computed_at=FIXED_TIME,
        metadata=metadata,
    )


def _pack(*metrics: MetricValue) -> EvidencePack:
    return EvidencePack(
        pack_id="pack-r7",
        generated_at=FIXED_TIME,
        synthetic=True,
        run_context={"run_id": "run-r7"},
        source_bundle_fingerprint="source-r7",
        validation_summary={"may_import": True, "counts_by_severity": {}},
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.AVAILABLE,
            vehicles=EvidenceStatus.AVAILABLE,
            infrastructure=EvidenceStatus.AVAILABLE,
            diagnosis=EvidenceStatus.AVAILABLE,
        ),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=MetricCollection(
            run_id="run-r7",
            metric_version="test",
            results=list(metrics),
            unavailable_count=0,
            partial_count=0,
            generated_at=FIXED_TIME,
        ),
    )


def _config(**updates: object) -> RuleSetConfig:
    return RuleSetConfig.model_validate(
        {
            "r0": {"enabled": False},
            "r1": {"enabled": False},
            "r2": {"enabled": False},
            "r3": {"enabled": False},
            "r4": {"enabled": False},
            "r5": {"enabled": False},
            "r6": {"enabled": False},
            "r7": {"enabled": True, **updates},
            "r8": {"enabled": False},
        }
    )


def _tier_metric(*, gap: float = 0.5, support: int = 2) -> MetricValue:
    policy = DEFAULT_OPERATIONAL_FAIRNESS_POLICY
    return _metric(
        TIER_KEY,
        gap,
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


def _target_metric(*, support: int = 2) -> MetricValue:
    contract = DEFAULT_TASK_RSU_TARGET_CONTRACT
    return _metric(
        TARGET_KEY,
        {"rsu-a": 0.0, "rsu-b": 1.0},
        {
            "task_rsu_target_contract_version": contract.schema_version,
            "task_rsu_target_contract_fingerprint": contract.fingerprint(),
            "target_semantics": contract.target_semantics,
            "target_join_method": contract.join_method,
            "coverage_fraction": 1.0,
            "attribution_interpretation": contract.attribution_interpretation,
            "group_count": 2,
            "group_support_counts": {"rsu-a": support, "rsu-b": support},
        },
    )


def _evaluate(pack: EvidencePack, **updates: object) -> RuleResult:
    report = evaluate_rules(pack, _config(**updates), clock=lambda: FIXED_TIME)
    assert [item.rule_id for item in report.results] == ["R7"]
    return report.results[0]


def test_vehicle_tier_r7_triggers_at_boundary_and_records_definition() -> None:
    result = _evaluate(_pack(_tier_metric(gap=0.2)))
    definition = r7_rule_definition()

    assert result.status is RuleStatus.TRIGGERED
    assert result.evidence_keys == [TIER_KEY]
    assert result.metadata["r7_dimension"] == "vehicle_tier_completion"
    assert result.metadata["declarative_definition_fingerprint"] == (definition.fingerprint())
    assert "protected or demographic" in result.limitations[0]
    assert result.confidence.value == "moderate"


def test_vehicle_tier_r7_can_be_not_triggered_or_insufficient() -> None:
    not_triggered = _evaluate(
        _pack(_tier_metric(gap=0.5)),
        minimum_outcome_gap=0.6,
    )
    thin = _evaluate(_pack(_tier_metric(gap=0.5, support=1)))
    missing = _evaluate(_pack())

    assert not_triggered.status is RuleStatus.NOT_TRIGGERED
    assert thin.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert "minimum group support" in thin.missing_evidence[0]
    assert missing.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert TIER_KEY in missing.missing_evidence[0]


def test_exact_target_rsu_dimension_uses_only_its_selected_metric() -> None:
    result = _evaluate(
        _pack(_tier_metric(gap=0.0), _target_metric()),
        dimension="target_rsu_completion",
    )
    thin = _evaluate(
        _pack(_target_metric(support=1)),
        dimension="target_rsu_completion",
    )

    assert result.status is RuleStatus.TRIGGERED
    assert result.evidence_keys == [TARGET_KEY]
    assert result.metadata["r7_dimension"] == "target_rsu_completion"
    assert result.findings[0].observed_values["observed_value"] == pytest.approx(1.0)
    assert thin.status is RuleStatus.INSUFFICIENT_EVIDENCE


def test_r7_config_is_bounded_and_the_definitions_are_distinct() -> None:
    tier = r7_rule_definition(R7Config(dimension="vehicle_tier_completion"))
    target = r7_rule_definition(R7Config(dimension="target_rsu_completion"))

    assert tier.predicates[0].metric_key == TIER_KEY
    assert target.predicates[0].metric_key == TARGET_KEY
    assert tier.fingerprint() != target.fingerprint()
