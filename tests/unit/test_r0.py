from __future__ import annotations

from tests.helpers import diagnostic_report_for_case
from traffictwin.rules.models import RuleStatus


def test_r0_not_triggered_for_complete_baseline_case() -> None:
    report = diagnostic_report_for_case("baseline_no_strong_hypothesis")
    r0 = report.results[0]

    assert r0.rule_id == "R0"
    assert r0.status is RuleStatus.NOT_TRIGGERED


def test_r0_triggers_when_infrastructure_evidence_is_missing() -> None:
    report = diagnostic_report_for_case("insufficient_evidence")
    r0 = report.results[0]

    assert r0.status is RuleStatus.TRIGGERED
    assert "R1" in report.blocked_rules
    assert "R2" in report.blocked_rules
