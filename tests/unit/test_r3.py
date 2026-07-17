from __future__ import annotations

from tests.helpers import diagnostic_report_for_case
from traffictwin.rules.models import ConfidenceCategory, RuleResult, RuleStatus


def _r3(case_id: str) -> RuleResult:
    return diagnostic_report_for_case(case_id).results[3]


def test_r3_triggers_only_with_experiment_level_evidence() -> None:
    result = _r3("trivial_scenario")

    assert result.status is RuleStatus.TRIGGERED
    assert result.confidence is ConfidenceCategory.MODERATE
    assert "experiment.cross_algorithm_dispersion" in result.evidence_keys


def test_r3_insufficient_for_single_run_evidence() -> None:
    result = _r3("baseline_no_strong_hypothesis")

    assert result.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence == [
        "experiment.algorithm.count",
        "experiment.cross_algorithm_dispersion",
    ]
