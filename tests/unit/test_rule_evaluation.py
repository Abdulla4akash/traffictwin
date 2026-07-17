from __future__ import annotations

from tests.helpers import diagnostic_fixture_set, fixed_clock
from traffictwin.rules.evaluation import evaluate_fixture_set


def test_fault_injection_evaluation_reports_precision_recall() -> None:
    report = evaluate_fixture_set(diagnostic_fixture_set(), clock=fixed_clock)

    assert report.case_count == 7
    assert report.split_counts == {"development": 3, "held_out": 4}
    assert all(summary.precision == 1.0 for summary in report.per_rule)
    assert all(summary.recall == 1.0 for summary in report.per_rule)


def test_fault_injection_evaluation_has_no_nan() -> None:
    report = evaluate_fixture_set(diagnostic_fixture_set(), clock=fixed_clock)

    assert "NaN" not in report.to_json()
    assert "Infinity" not in report.to_json()
