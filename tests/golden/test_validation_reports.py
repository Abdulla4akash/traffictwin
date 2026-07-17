from __future__ import annotations

import json
from pathlib import Path

from traffictwin.evidence.availability import EvidenceStatus
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.report import ImportStatus


def test_partial_bundle_golden_validation_codes() -> None:
    result = validate_bundle(Path("tests/fixtures/bundles/partial_valid"))
    codes = [finding.code for finding in result.report.findings]

    assert result.report.status is ImportStatus.ACCEPTED_WITH_WARNINGS
    assert codes == [
        ValidationCode.EVIDENCE_INFRA_UNAVAILABLE,
        ValidationCode.EVIDENCE_TRAFFIC_UNAVAILABLE,
        ValidationCode.EVIDENCE_TRIPS_UNAVAILABLE,
        ValidationCode.EVIDENCE_INSUFFICIENT_FOR_DIAGNOSIS,
    ]
    assert result.evidence.infrastructure is EvidenceStatus.UNAVAILABLE
    assert result.insufficient_evidence.diagnosis_allowed is False


def test_invalid_rows_golden_validation_codes() -> None:
    result = validate_bundle(Path("tests/fixtures/bundles/invalid_rows"))
    codes = [finding.code for finding in result.report.findings]

    assert result.report.status is ImportStatus.REJECTED
    assert codes == [
        ValidationCode.TASK_LATENCY_NEGATIVE,
        ValidationCode.UTILISATION_OUT_OF_RANGE,
        ValidationCode.TRIP_ARRIVAL_BEFORE_DEPARTURE,
        ValidationCode.TRIP_DURATION_INCONSISTENT,
        ValidationCode.TASK_ID_DUPLICATE,
        ValidationCode.EVIDENCE_TRAFFIC_UNAVAILABLE,
        ValidationCode.EVIDENCE_INSUFFICIENT_FOR_DIAGNOSIS,
    ]


def test_validation_report_json_structure() -> None:
    result = validate_bundle(Path("tests/fixtures/bundles/partial_valid"))
    payload = json.loads(result.report.to_json())

    assert payload["bundle_id"] == "bundle-partial-001"
    assert payload["run_id"] == "run-partial-001"
    assert payload["status"] == "accepted_with_warnings"
    assert "findings" in payload
    assert "counts_by_severity" in payload
    assert "unavailable_evidence_categories" in payload
