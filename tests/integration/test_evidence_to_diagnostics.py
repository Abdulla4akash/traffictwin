from __future__ import annotations

from tests.helpers import bundle_result, fixed_clock, metric_collection

from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.rules.engine import evaluate_rules


def test_bundle_to_evidence_to_diagnostics() -> None:
    pack = build_evidence_pack(
        bundle_result("baseline_valid"),
        metric_collection("baseline_valid"),
        clock=fixed_clock,
    )

    report = evaluate_rules(pack, clock=fixed_clock)

    assert report.evidence_pack_id == pack.pack_id
    assert report.triggered_rule_ids == []
    assert "R3" in report.insufficient_rule_ids


def test_rejected_bundle_yields_blocked_report_not_ordinary_hypotheses() -> None:
    pack = build_evidence_pack(
        bundle_result("invalid_rows"),
        metric_collection("invalid_rows"),
        clock=fixed_clock,
    )

    report = evaluate_rules(pack, clock=fixed_clock)

    assert report.overall_readiness.value == "invalid"
    assert report.triggered_rule_ids == ["R0"]
    assert "R1" in report.insufficient_rule_ids
    assert "R2" in report.insufficient_rule_ids
