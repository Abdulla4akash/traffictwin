from __future__ import annotations

from tests.helpers import diagnostic_fixture_set, fixed_clock
from traffictwin.rules.evaluation import build_extended_fixture_set, evaluate_fixture_set


def test_fault_injection_evaluation_reports_precision_recall() -> None:
    report = evaluate_fixture_set(diagnostic_fixture_set(), clock=fixed_clock)

    assert report.case_count == 7
    assert report.split_counts == {"development": 3, "held_out": 4}
    supported = [summary for summary in report.per_rule if summary.support_count]
    assert all(summary.precision == 1.0 for summary in supported)
    assert all(summary.recall == 1.0 for summary in supported)
    assert all(summary.false_positive_rate == 0.0 for summary in report.per_rule)


def test_fault_injection_evaluation_has_no_nan() -> None:
    report = evaluate_fixture_set(diagnostic_fixture_set(), clock=fixed_clock)

    assert "NaN" not in report.to_json()
    assert "Infinity" not in report.to_json()


def test_extended_fault_matrix_covers_severity_seeds_r4_r5_and_robustness() -> None:
    fixtures = build_extended_fixture_set(diagnostic_fixture_set())
    report = evaluate_fixture_set(fixtures, clock=fixed_clock)

    assert report.case_count == 81
    assert {case.severity for case in fixtures.cases} == {"mild", "moderate", "severe"}
    assert {case.random_seed for case in fixtures.cases} == {1, 2, 3}
    by_rule = {summary.rule_id: summary for summary in report.per_rule}
    assert by_rule["R4"].support_count == 9
    assert by_rule["R5"].support_count == 9
    assert report.split_summaries
    assert report.robustness
    assert len(report.kpi_baseline_per_rule) == 6
