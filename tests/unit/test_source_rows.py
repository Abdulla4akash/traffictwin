from __future__ import annotations

from tests.helpers import bundle_result
from traffictwin.provenance.models import ProvenanceStatus
from traffictwin.provenance.source_rows import get_source_row


def test_source_row_preview_includes_raw_and_canonical_values() -> None:
    result = bundle_result("baseline_valid")
    preview = get_source_row(
        "tests/fixtures/bundles/baseline_valid",
        "tasks.csv",
        2,
        canonical_tables=result.canonical,
        validation_report=result.report,
        manifest=result.manifest,
    )

    assert preview.status is ProvenanceStatus.AVAILABLE
    assert preview.raw_values["task_id"] == "t1"
    assert preview.canonical_record_type == "TaskRecord"
    assert preview.canonical_values["task_id"] == "t1"
    assert preview.inclusion_status == "included"
    assert preview.conversions["units"]["arrival_time"] == "s"


def test_source_row_preview_rejects_path_traversal() -> None:
    preview = get_source_row(
        "tests/fixtures/bundles/baseline_valid",
        "../manifest.yaml",
        1,
    )

    assert preview.status is ProvenanceStatus.UNAVAILABLE
    assert "bundle-relative" in preview.warnings[0]
