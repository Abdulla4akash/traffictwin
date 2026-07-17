from __future__ import annotations

from pathlib import Path

from traffictwin.evidence.availability import EvidenceStatus
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.validation.report import ImportStatus


def test_baseline_bundle_golden_counts_and_evidence() -> None:
    result = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))

    assert result.report.status is ImportStatus.ACCEPTED
    assert result.report.canonical_record_counts == {
        "tasks": 3,
        "infrastructure": 4,
        "vehicles": 0,
        "traffic": 2,
        "trips": 2,
        "incidents": 0,
    }
    assert result.evidence.tasks is EvidenceStatus.AVAILABLE
    assert result.evidence.infrastructure is EvidenceStatus.AVAILABLE
    assert result.evidence.traffic is EvidenceStatus.AVAILABLE
    assert result.evidence.trips is EvidenceStatus.AVAILABLE


def test_variation_bundle_golden_counts() -> None:
    result = validate_bundle(Path("tests/fixtures/bundles/variation_valid"))

    assert result.report.status is ImportStatus.ACCEPTED
    assert result.report.canonical_record_counts["tasks"] == 4
    assert result.report.canonical_record_counts["infrastructure"] == 4
    assert result.canonical.tasks[-1].completed is False
