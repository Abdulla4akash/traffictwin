from __future__ import annotations

import json
from pathlib import Path

from traffictwin.ingestion.batch import validate_bundle_batch

EXPECTED = Path("tests/golden/expected/batch_validation_mixed.json")


def test_mixed_batch_validation_matches_golden_summary() -> None:
    summary = validate_bundle_batch(
        [
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/invalid_manifest",
        ]
    )
    projection = {
        "schema_version": summary.schema_version,
        "operation": summary.operation.value,
        "overall_status": summary.overall_status.value,
        "matched_bundle_count": summary.matched_bundle_count,
        "processed_bundle_count": summary.processed_bundle_count,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
        "input_issues": [issue.model_dump(mode="json") for issue in summary.input_issues],
        "results": [
            {
                "source_name": Path(result.source).name,
                "bundle_id": result.bundle_id,
                "run_id": result.run_id,
                "validation_status": result.validation_status.value,
                "may_import": result.may_import,
                "finding_count": result.finding_count,
                "warning_count": result.warning_count,
                "error_count": result.error_count,
                "import_state": result.import_state.value,
            }
            for result in summary.results
        ],
    }

    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
