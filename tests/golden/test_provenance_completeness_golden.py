from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.provenance.query import (
    build_provenance_context,
    get_report_provenance_completeness,
)


def test_baseline_provenance_completeness_projection_matches_golden() -> None:
    context = build_provenance_context(
        "tests/fixtures/bundles/baseline_valid",
        clock=fixed_clock,
    )
    report = get_report_provenance_completeness(context, clock=fixed_clock)
    actual = {
        "schema_version": report.schema_version,
        "capability_id": report.capability_id,
        "report_id": report.report_id,
        "report_type": report.report_type.value,
        "denominator_count": report.denominator_count,
        "source_row_complete_count": report.source_row_complete_count,
        "aggregate_only_count": report.aggregate_only_count,
        "unavailable_count": report.unavailable_count,
        "score": report.score,
        "aggregate_or_better_fraction": report.aggregate_or_better_fraction,
        "overall_status": report.overall_status.value,
        "classifications": {
            claim.artifact_key: {
                "status": claim.artifact_status,
                "classification": claim.classification.value,
                "trace_depth": claim.trace_depth.value,
                "candidate_rows": claim.candidate_source_row_count,
                "included_rows": claim.included_source_row_count,
            }
            for claim in report.claims
        },
    }
    expected = json.loads(
        Path("tests/golden/expected/provenance_completeness_baseline.json").read_text(
            encoding="utf-8"
        )
    )

    assert actual == expected
