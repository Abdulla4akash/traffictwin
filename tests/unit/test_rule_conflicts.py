from __future__ import annotations

from tests.helpers import diagnostic_report_for_case


def test_mixed_fault_preserves_multiple_hypotheses() -> None:
    report = diagnostic_report_for_case("mixed_fault")

    assert report.triggered_rule_ids == ["R1", "R2"]
    assert any("does not choose" in observation for observation in report.conflict_observations)


def test_conflicting_evidence_is_reported_without_suppressing_r2() -> None:
    report = diagnostic_report_for_case("contradictory_evidence")

    assert report.conflicting_rule_ids == ["R1"]
    assert report.triggered_rule_ids == ["R2"]
