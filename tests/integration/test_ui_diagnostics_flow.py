from __future__ import annotations

from traffictwin.ui.labels import DIAGNOSTIC_NOTICE, UiPage
from traffictwin.ui.services import validate_bundle_for_ui


def test_ui_service_builds_diagnostic_report_for_valid_bundle() -> None:
    analysis = validate_bundle_for_ui("tests/fixtures/bundles/baseline_valid")

    assert analysis.diagnostic_report is not None
    assert analysis.diagnostic_report.triggered_rule_ids == []
    assert "R3" in analysis.diagnostic_report.insufficient_rule_ids


def test_ui_labels_present_hypotheses_without_causal_proof_language() -> None:
    forbidden = ["proves", "definitely", "caused by", "the problem is"]

    assert UiPage.EVIDENCE.value == "Diagnostics & Evidence"
    assert "not proven root causes" in DIAGNOSTIC_NOTICE
    assert not any(term in DIAGNOSTIC_NOTICE.lower() for term in forbidden)
