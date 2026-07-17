from __future__ import annotations

from traffictwin.rules.models import Finding, FindingSupport, Recommendation, RuleResult


def test_rule_result_has_no_proven_cause_field() -> None:
    fields = set(RuleResult.model_fields)

    assert "proven_cause" not in fields


def test_recommendations_are_conditional_by_default() -> None:
    recommendation = Recommendation(
        action="inspect action availability",
        rationale="external actions need evidence",
        expected_direction="readiness improves",
        prerequisite="decision-time log",
        verification_step="rerun diagnostics",
    )

    assert recommendation.conditional is True


def test_finding_support_values_are_stable() -> None:
    finding = Finding(
        finding_id="F1",
        statement="example",
        evidence_keys=["task.generated.count"],
        expected_condition="condition",
        support=FindingSupport.SUPPORTS,
    )

    assert finding.support.value == "supports"
