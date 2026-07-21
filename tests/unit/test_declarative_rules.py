from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.helpers import FIXED_TIME
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue
from traffictwin.rules.declarative import (
    MAX_RULE_YAML_BYTES,
    DeclarativeRuleError,
    DeclarativeRuleRegistry,
    PredicateTruth,
    declarative_rule_contract,
    evaluate_declarative_rule,
    parse_declarative_rule_yaml,
)
from traffictwin.rules.models import RuleStatus


def _metric(
    key: str,
    value: object,
    *,
    unit: str = "ratio",
    status: MetricStatus = MetricStatus.AVAILABLE,
    metadata: dict[str, object] | None = None,
) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=status,
        value=value,
        unit=unit,
        scope="run",
        implementation_version="test",
        run_id="run-declarative",
        experiment_id="exp-declarative",
        seed_id="seed-declarative",
        algorithm="test",
        random_seed=1,
        synthetic=True,
        computed_at=FIXED_TIME,
        metadata=metadata or {},
    )


def _pack(*metrics: MetricValue) -> EvidencePack:
    return EvidencePack(
        pack_id="pack-declarative",
        generated_at=FIXED_TIME,
        synthetic=True,
        run_context={"run_id": "run-declarative"},
        source_bundle_fingerprint="source-declarative",
        validation_summary={"may_import": True, "counts_by_severity": {}},
        evidence_availability=EvidenceAvailability(diagnosis=EvidenceStatus.AVAILABLE),
        metric_engine_config=MetricEngineConfig(),
        metric_collection=MetricCollection(
            run_id="run-declarative",
            metric_version="test",
            results=list(metrics),
            unavailable_count=sum(item.status is MetricStatus.UNAVAILABLE for item in metrics),
            partial_count=sum(item.status is MetricStatus.PARTIAL for item in metrics),
            generated_at=FIXED_TIME,
        ),
    )


def _rule_yaml(
    *,
    rule_id: str = "LOCAL_THRESHOLD",
    condition: str = "all",
    predicates: str | None = None,
) -> str:
    predicate_text = (
        predicates
        or """
  - kind: numeric_threshold
    predicate_id: COMPLETION_GAP
    metric_key: metric.gap
    reducer: scalar
    operator: gte
    threshold: 0.2
    expected_unit: ratio
    required_metadata:
      - key: contract_version
        expected: "1.0"
    statement: The admitted gap is compared with its configured threshold.
"""
    )
    return f"""
schema_version: "1.0"
grammar_version: "1.0"
rule_id: {rule_id}
rule_version: "1.0"
title: Local threshold
purpose: Exercise the bounded declarative threshold grammar.
condition: {condition}
predicates:
{predicate_text.rstrip()}
triggered_hypothesis: The admitted threshold condition is present.
alternative_explanations:
  - finite sample variation
recommendations:
  - action: repeat the comparison
    rationale: replication tests stability
    expected_direction: the observed condition becomes more or less stable
    prerequisite: compatible evidence
    verification_step: evaluate the same rule again
limitations:
  - This local threshold does not prove causality.
""".strip()


def test_contract_and_definition_are_versioned_bounded_and_fingerprinted() -> None:
    contract = declarative_rule_contract()
    first = parse_declarative_rule_yaml(_rule_yaml())
    second = parse_declarative_rule_yaml(_rule_yaml())

    assert contract.capability == "DIA-04"
    assert contract.maximum_yaml_bytes == MAX_RULE_YAML_BYTES
    assert contract.trust_boundary == "trusted_local_static_yaml_not_a_sandbox"
    assert "arbitrary expressions or reducers" in contract.excluded_language_features
    assert first.fingerprint() == second.fingerprint()


def test_scalar_threshold_has_trigger_non_trigger_and_strict_evidence_checks() -> None:
    definition = parse_declarative_rule_yaml(_rule_yaml())

    triggered = evaluate_declarative_rule(
        definition,
        _pack(_metric("metric.gap", 0.2, metadata={"contract_version": "1.0"})),
        evaluated_at=FIXED_TIME,
    )
    not_triggered = evaluate_declarative_rule(
        definition,
        _pack(_metric("metric.gap", 0.19, metadata={"contract_version": "1.0"})),
        evaluated_at=FIXED_TIME,
    )
    wrong_unit = evaluate_declarative_rule(
        definition,
        _pack(
            _metric(
                "metric.gap",
                0.9,
                unit="percent",
                metadata={"contract_version": "1.0"},
            )
        ),
        evaluated_at=FIXED_TIME,
    )
    missing_metadata = evaluate_declarative_rule(
        definition,
        _pack(_metric("metric.gap", 0.9)),
        evaluated_at=FIXED_TIME,
    )

    assert triggered.status is RuleStatus.TRIGGERED
    assert triggered.findings[0].observed_values["observed_value"] == pytest.approx(0.2)
    assert triggered.metadata["declarative_definition_fingerprint"] == (definition.fingerprint())
    assert not_triggered.status is RuleStatus.NOT_TRIGGERED
    assert wrong_unit.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert "does not match" in wrong_unit.missing_evidence[0]
    assert missing_metadata.status is RuleStatus.INSUFFICIENT_EVIDENCE


def test_mapping_gap_requires_exact_complete_groups_and_minimum_support() -> None:
    definition = parse_declarative_rule_yaml(
        _rule_yaml(
            predicates="""
  - kind: numeric_threshold
    predicate_id: GROUP_GAP
    metric_key: metric.by_group
    reducer: mapping_max_gap
    operator: gte
    threshold: 0.2
    expected_unit: ratio
    minimum_group_count: 2
    group_count_metadata_key: group_count
    minimum_group_support: 2
    group_support_metadata_key: group_support_counts
    statement: The admitted group range is compared with its configured threshold.
"""
        )
    )
    metadata = {"group_count": 2, "group_support_counts": {"a": 2, "b": 3}}

    triggered = evaluate_declarative_rule(
        definition,
        _pack(_metric("metric.by_group", {"a": 0.2, "b": 0.8}, metadata=metadata)),
        evaluated_at=FIXED_TIME,
    )
    thin = evaluate_declarative_rule(
        definition,
        _pack(
            _metric(
                "metric.by_group",
                {"a": 0.2, "b": 0.8},
                metadata={"group_count": 2, "group_support_counts": {"a": 1, "b": 3}},
            )
        ),
        evaluated_at=FIXED_TIME,
    )
    wrong_groups = evaluate_declarative_rule(
        definition,
        _pack(
            _metric(
                "metric.by_group",
                {"a": 0.2, "b": 0.8},
                metadata={"group_count": 2, "group_support_counts": {"a": 2, "c": 3}},
            )
        ),
        evaluated_at=FIXED_TIME,
    )
    null_group = evaluate_declarative_rule(
        definition,
        _pack(_metric("metric.by_group", {"a": 0.2, "b": None}, metadata=metadata)),
        evaluated_at=FIXED_TIME,
    )

    assert triggered.status is RuleStatus.TRIGGERED
    assert triggered.findings[0].observed_values["observed_value"] == pytest.approx(0.6)
    assert thin.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert "minimum group support" in thin.missing_evidence[0]
    assert wrong_groups.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert "keys do not match" in wrong_groups.missing_evidence[0]
    assert null_group.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert "null or non-numeric" in null_group.missing_evidence[0]


def test_boolean_and_three_valued_all_any_semantics_are_conservative() -> None:
    predicates = """
  - kind: boolean_equals
    predicate_id: BOOL
    metric_key: metric.flag
    expected: true
    expected_unit: boolean
    statement: The admitted flag is true.
  - kind: numeric_threshold
    predicate_id: GAP
    metric_key: metric.missing
    reducer: scalar
    operator: gte
    threshold: 0.2
    expected_unit: ratio
    statement: The admitted gap crosses its threshold.
"""
    any_definition = parse_declarative_rule_yaml(_rule_yaml(condition="any", predicates=predicates))
    all_definition = parse_declarative_rule_yaml(_rule_yaml(condition="all", predicates=predicates))
    true_pack = _pack(_metric("metric.flag", True, unit="boolean"))
    false_pack = _pack(_metric("metric.flag", False, unit="boolean"))

    any_true = evaluate_declarative_rule(any_definition, true_pack, evaluated_at=FIXED_TIME)
    any_unknown = evaluate_declarative_rule(any_definition, false_pack, evaluated_at=FIXED_TIME)
    all_false = evaluate_declarative_rule(all_definition, false_pack, evaluated_at=FIXED_TIME)

    assert any_true.status is RuleStatus.TRIGGERED
    assert any_true.confidence.value == "low"
    assert any_unknown.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert all_false.status is RuleStatus.NOT_TRIGGERED
    assert all_false.findings[0].observed_values["predicate_truth"] == PredicateTruth.FALSE


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("a: 1\na: 2", "duplicate key"),
        ("a: &value 1", "anchors and aliases"),
        ("a: !python/object 1", "custom tag"),
        ("a: 1\n---\na: 2", "single document"),
    ],
)
def test_unsafe_or_ambiguous_yaml_features_are_rejected(
    payload: str,
    expected: str,
) -> None:
    with pytest.raises(DeclarativeRuleError, match=expected):
        parse_declarative_rule_yaml(payload)


def test_closed_schema_ids_and_size_bound_are_enforced() -> None:
    with pytest.raises(DeclarativeRuleError, match="exceeds"):
        parse_declarative_rule_yaml("x" * (MAX_RULE_YAML_BYTES + 1))
    with pytest.raises(DeclarativeRuleError, match="reserved core"):
        parse_declarative_rule_yaml(_rule_yaml(rule_id="R7"))
    with pytest.raises(DeclarativeRuleError, match="must start"):
        parse_declarative_rule_yaml(_rule_yaml(rule_id="CUSTOM_THRESHOLD"))
    with pytest.raises(DeclarativeRuleError, match="extra"):
        parse_declarative_rule_yaml(f"{_rule_yaml()}\nunknown_field: true")


def test_registry_rejects_duplicates_and_has_stable_inventory() -> None:
    first = parse_declarative_rule_yaml(_rule_yaml(rule_id="LOCAL_B"))
    second = parse_declarative_rule_yaml(_rule_yaml(rule_id="LOCAL_A"))
    registry = DeclarativeRuleRegistry()
    registry.register(first)
    registry.register(second)

    assert [item.rule_id for item in registry.definitions()] == ["LOCAL_A", "LOCAL_B"]
    assert len(registry.report().registry_fingerprint) == 64
    with pytest.raises(DeclarativeRuleError, match="duplicate"):
        registry.register(first)


def test_models_reject_non_finite_thresholds() -> None:
    definition = parse_declarative_rule_yaml(_rule_yaml())
    predicate = definition.predicates[0]
    with pytest.raises(ValidationError):
        predicate.model_copy(update={"threshold": float("inf")}).__class__.model_validate(
            {**predicate.model_dump(), "threshold": float("inf")}
        )


def test_yaml_numeric_boolean_and_metadata_types_are_not_string_coerced() -> None:
    with pytest.raises(DeclarativeRuleError, match="valid number"):
        parse_declarative_rule_yaml(_rule_yaml().replace("threshold: 0.2", 'threshold: "0.2"'))
    boolean_rule = _rule_yaml(
        predicates="""
  - kind: boolean_equals
    predicate_id: BOOL
    metric_key: metric.flag
    expected: "true"
    expected_unit: boolean
    statement: The admitted flag is true.
"""
    )
    with pytest.raises(DeclarativeRuleError, match="valid boolean"):
        parse_declarative_rule_yaml(boolean_rule)
    with pytest.raises(DeclarativeRuleError, match="finite"):
        parse_declarative_rule_yaml(_rule_yaml().replace('expected: "1.0"', "expected: .nan"))


def test_default_timestamp_is_aware_when_caller_does_not_supply_one() -> None:
    result = evaluate_declarative_rule(
        parse_declarative_rule_yaml(_rule_yaml()),
        _pack(_metric("metric.gap", 0.3, metadata={"contract_version": "1.0"})),
    )

    assert result.evaluated_at.tzinfo is not None
    assert result.evaluated_at <= datetime.now(UTC)
