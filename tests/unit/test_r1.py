from __future__ import annotations

from tests.helpers import diagnostic_report_for_case
from traffictwin.rules.models import ConfidenceCategory, RuleResult, RuleStatus


def _r1(case_id: str) -> RuleResult:
    return diagnostic_report_for_case(case_id).results[1]


def test_r1_triggers_under_offloading_candidate() -> None:
    result = _r1("under_offloading")

    assert result.status is RuleStatus.TRIGGERED
    assert result.confidence is ConfidenceCategory.MODERATE
    assert "task.offload.rate" in result.evidence_keys
    assert "low-tier vehicle breakdown" in result.missing_evidence


def test_r1_not_triggered_for_baseline() -> None:
    result = _r1("baseline_no_strong_hypothesis")

    assert result.status is RuleStatus.NOT_TRIGGERED


def test_r1_returns_conflicting_evidence_for_low_offload_but_high_utilisation() -> None:
    result = _r1("contradictory_evidence")

    assert result.status is RuleStatus.CONFLICTING_EVIDENCE
    assert result.confidence is ConfidenceCategory.LOW
