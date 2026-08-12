"""Integration flow for Calibration Workbench — study -> report -> exports."""

from __future__ import annotations

import json

from traffictwin.calibration.fixtures import make_three_candidate_study
from traffictwin.calibration.service import (
    build_calibration_report,
    calibration_report_to_json,
    export_candidate_summary_csv,
    export_metric_results_csv,
    export_residuals_csv,
)


def test_integration_flow() -> None:
    study = make_three_candidate_study()
    report = build_calibration_report(study)
    # JSON export deterministic
    j = calibration_report_to_json(report)
    parsed = json.loads(j)
    assert parsed["fingerprint"] == report.fingerprint
    assert parsed["evidence_boundary"] == report.evidence_boundary
    # CSV exports
    residuals_csv = export_residuals_csv(report)
    assert "candidate_id" in residuals_csv.splitlines()[0]
    summary_csv = export_candidate_summary_csv(report)
    assert "weighted_objective" in summary_csv.splitlines()[0]
    metrics_csv = export_metric_results_csv(report)
    assert "normalized_mae" in metrics_csv.splitlines()[0]
    assert "objective_scale" in metrics_csv.splitlines()[0]
    # Ranking language dimensionless
    assert report.ranking is not None
