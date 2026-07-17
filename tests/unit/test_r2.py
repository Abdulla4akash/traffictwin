from __future__ import annotations

from tests.helpers import diagnostic_report_for_case
from traffictwin.rules.models import ConfidenceCategory, RuleResult, RuleStatus


def _r2(case_id: str) -> RuleResult:
    return diagnostic_report_for_case(case_id).results[2]


def test_r2_triggers_infrastructure_bottleneck_candidate() -> None:
    result = _r2("infrastructure_bottleneck")

    assert result.status is RuleStatus.TRIGGERED
    assert result.confidence is ConfidenceCategory.MODERATE
    assert "infra.saturation.duration_s" in result.evidence_keys


def test_r2_not_triggered_for_under_offloading_fixture() -> None:
    result = _r2("under_offloading")

    assert result.status is RuleStatus.NOT_TRIGGERED


def test_r2_insufficient_without_infrastructure_metrics() -> None:
    result = _r2("insufficient_evidence")

    assert result.status is RuleStatus.INSUFFICIENT_EVIDENCE
    assert "infra.utilisation.p95" in result.missing_evidence
