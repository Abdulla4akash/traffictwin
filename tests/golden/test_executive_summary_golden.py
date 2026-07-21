from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.reporting.builder import build_run_report
from traffictwin.reporting.executive import project_executive_summary

BASELINE = Path("tests/fixtures/bundles/baseline_valid")
EXPECTED = Path("tests/golden/expected/executive_summary_baseline.json")
NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def test_executive_summary_baseline_matches_golden_projection() -> None:
    report = build_run_report(BASELINE, clock=lambda: NOW)
    summary = project_executive_summary(report, source_report_reference="baseline.json")

    assert summary.model_dump(mode="json") == json.loads(EXPECTED.read_text(encoding="utf-8"))
