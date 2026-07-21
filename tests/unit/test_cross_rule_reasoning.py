from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers import diagnostic_report_for_case
from traffictwin.diagnostics.cross_rule import (
    CrossRuleOverlapBasis,
    CrossRuleReasoningReport,
    CrossRuleReasoningStatus,
    CrossRuleRelationType,
    cross_rule_reasoning_contract,
    evaluate_cross_rule_reasoning,
)
from traffictwin.metrics.results import JsonScalar
from traffictwin.rules.models import (
    Finding,
    FindingSupport,
    RuleResult,
    RuleStatus,
    result_from_findings,
)

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def test_contract_publishes_only_three_bounded_policies() -> None:
    contract = cross_rule_reasoning_contract()

    assert contract.policy_version == "1.0"
    assert [policy.relation_type for policy in contract.policies] == [
        CrossRuleRelationType.CONFLICT,
        CrossRuleRelationType.CORROBORATION,
        CrossRuleRelationType.SUPPRESSION,
    ]
    assert contract.precedence_tiers == {"data_readiness": 100, "ordinary_diagnostic": 50}
    assert "never deletes" in contract.retention_guarantee
    assert "do not calculate probability" in contract.confidence_semantics
    assert "No relationship is inferred" in contract.undeclared_pair_semantics


def test_mixed_fault_records_typed_conflict_and_retains_every_result() -> None:
    diagnostic = diagnostic_report_for_case("mixed_fault")
    analysis = diagnostic.cross_rule_analysis

    assert analysis is not None
    assert analysis.status is CrossRuleReasoningStatus.RELATIONSHIPS_RECORDED
    assert analysis.counts_by_type == {"conflict": 1, "corroboration": 0, "suppression": 0}
    relationship = analysis.relationships[0]
    assert relationship.relation_type is CrossRuleRelationType.CONFLICT
    assert (relationship.source_rule_id, relationship.target_rule_id) == ("R1", "R2")
    assert relationship.shared_evidence_keys == ["task.generated.count"]
    assert relationship.source_precedence == relationship.target_precedence == 50
    assert relationship.symmetric is True
    assert analysis.retained_rule_ids == [result.rule_id for result in diagnostic.results]
    assert analysis.suppressed_rule_ids == []
    assert len(analysis.original_result_fingerprints) == len(diagnostic.results)


def test_r0_suppression_is_additive_and_does_not_change_target_statuses() -> None:
    diagnostic = diagnostic_report_for_case("insufficient_evidence")
    before = [result.model_dump(mode="json") for result in diagnostic.results]
    analysis = diagnostic.cross_rule_analysis

    assert analysis is not None
    assert analysis.suppressed_rule_ids == ["R1", "R2", "R4"]
    assert analysis.counts_by_type["suppression"] == 3
    assert all(
        relationship.overlap_basis is CrossRuleOverlapBasis.EXPLICIT_BLOCKED_RULE
        for relationship in analysis.relationships
    )
    assert all(
        relationship.source_precedence > relationship.target_precedence
        for relationship in analysis.relationships
    )
    assert [result.model_dump(mode="json") for result in diagnostic.results] == before
    assert {
        result.rule_id: result.status
        for result in diagnostic.results
        if result.rule_id in analysis.suppressed_rule_ids
    } == {
        "R1": RuleStatus.INSUFFICIENT_EVIDENCE,
        "R2": RuleStatus.INSUFFICIENT_EVIDENCE,
        "R4": RuleStatus.INSUFFICIENT_EVIDENCE,
    }


def test_r1_r4_corroboration_requires_the_declared_exact_key() -> None:
    r1 = _result("R1", ["infra.utilisation.mean", "task.generated.count"])
    r4 = _result("R4", ["infra.load_balance.jain_capacity_normalised", "infra.utilisation.mean"])
    analysis = _analyse([r4, r1])

    assert analysis.counts_by_type["corroboration"] == 1
    relationship = analysis.relationships[0]
    assert relationship.relation_type is CrossRuleRelationType.CORROBORATION
    assert relationship.shared_evidence_keys == ["infra.utilisation.mean"]
    assert relationship.presentation_effect == (
        "retain both candidates as contextual corroboration"
    )

    without_overlap = _analyse(
        [
            _result("R1", ["task.generated.count"]),
            _result("R4", ["infra.load_balance.jain_capacity_normalised"]),
        ]
    )
    assert without_overlap.status is CrossRuleReasoningStatus.NO_RELATIONSHIPS
    assert without_overlap.unclassified_triggered_rule_ids == ["R1", "R4"]


def test_undeclared_triggered_rules_remain_unclassified() -> None:
    analysis = _analyse([_result("R8", ["task.energy.per_completed_j"])])

    assert analysis.relationships == []
    assert analysis.unclassified_triggered_rule_ids == ["R8"]


def test_unresolved_blocker_reference_is_visible() -> None:
    r0 = _result("R0", [], metadata={"blocked_rules": "R1,R99"})
    r1 = _result("R1", [], status=RuleStatus.INSUFFICIENT_EVIDENCE)
    analysis = _analyse([r0, r1])

    assert analysis.suppressed_rule_ids == ["R1"]
    assert analysis.unresolved_blocked_rule_ids == ["R99"]
    assert "R99" in analysis.warnings[0]


def test_duplicate_rule_ids_and_inconsistent_source_labels_are_rejected() -> None:
    result = _result("R1", ["task.generated.count"])
    with pytest.raises(ValueError, match="unique"):
        _analyse([result, result])

    incompatible = result.model_copy(update={"synthetic": False})
    with pytest.raises(ValueError, match="synthetic"):
        _analyse([incompatible])


def test_order_and_timestamps_do_not_change_fingerprint_or_inputs() -> None:
    r1 = _result("R1", ["task.generated.count"])
    r2 = _result("R2", ["task.generated.count"])
    before = [result.model_dump(mode="json") for result in (r1, r2)]
    first = _analyse([r1, r2], generated_at=NOW)
    later_results = [
        result.model_copy(update={"evaluated_at": result.evaluated_at + timedelta(days=1)})
        for result in (r2, r1)
    ]
    second = _analyse(later_results, generated_at=NOW + timedelta(days=1))

    assert first.analysis_id == second.analysis_id
    assert first.fingerprint() == second.fingerprint()
    assert [result.model_dump(mode="json") for result in (r1, r2)] == before


def _result(
    rule_id: str,
    evidence_keys: list[str],
    *,
    status: RuleStatus = RuleStatus.TRIGGERED,
    metadata: dict[str, JsonScalar] | None = None,
) -> RuleResult:
    findings = [
        Finding(
            finding_id=f"{rule_id}-TEST-{index}",
            statement="Constructed deterministic test finding.",
            evidence_keys=[key],
            observed_values={"value": index},
            expected_condition="constructed condition",
            support=FindingSupport.SUPPORTS,
        )
        for index, key in enumerate(evidence_keys)
    ]
    return result_from_findings(
        rule_id=rule_id,
        rule_version="test",
        title=f"{rule_id} test",
        status=status,
        synthetic=True,
        evaluated_at=NOW,
        hypothesis="Constructed hypothesis" if status is RuleStatus.TRIGGERED else None,
        findings=findings,
        metadata=metadata,
    )


def _analyse(
    results: list[RuleResult],
    *,
    generated_at: datetime = NOW,
) -> CrossRuleReasoningReport:
    return evaluate_cross_rule_reasoning(
        results,
        diagnostic_report_id="diagnostic-test",
        evidence_pack_id="evidence-test",
        ruleset_version="test",
        source_evidence_fingerprint="evidence-fingerprint",
        synthetic=True,
        generated_at=generated_at,
    )
