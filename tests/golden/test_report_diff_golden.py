from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.reporting.diffing import compare_structured_reports
from traffictwin.reporting.models import (
    ReportClaimAvailability,
    ReportClaimKind,
    ReportClaimReference,
    ReportClaimSnapshot,
    ResearchReport,
    ResearchReportType,
)

EXPECTED = Path("tests/golden/expected/structured_report_diff.json")
NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def test_structured_report_diff_matches_golden() -> None:
    baseline = _report("report-baseline", 0.8, ["baseline rendered prose"])
    variation = _report("report-variation", 0.7, ["different rendered prose"])

    actual = compare_structured_reports(baseline, variation).model_dump(mode="json")

    assert actual == json.loads(EXPECTED.read_text(encoding="utf-8"))


def _report(report_id: str, value: float, narrative: list[str]) -> ResearchReport:
    claim_id = f"{report_id}:metric:task.completion.rate"
    return ResearchReport(
        report_id=report_id,
        title="Golden structured report",
        generated_at=NOW,
        source_reference="golden-fixture",
        synthetic=True,
        sections=[("Metrics", [f"formatted completion={value}"]), ("Notes", narrative)],
        report_type=ResearchReportType.RUN,
        claim_references=[
            ReportClaimReference(
                claim_id=claim_id,
                claim_kind=ReportClaimKind.METRIC_RESULT,
                artifact_key="task.completion.rate",
                section="Metrics",
                label="Completion rate",
            )
        ],
        claim_snapshots=[
            ReportClaimSnapshot(
                claim_id=claim_id,
                claim_kind=ReportClaimKind.METRIC_RESULT,
                artifact_key="task.completion.rate",
                section="Metrics",
                availability=ReportClaimAvailability.AVAILABLE,
                status="available",
                value=value,
                unit="ratio",
                details={
                    "implementation_version": "1.0",
                    "scope": "run",
                    "dimensions": {},
                },
            )
        ],
    )
