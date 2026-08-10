"""Integration test for resource strategy load → build → render → export."""

from __future__ import annotations

import json
from pathlib import Path

from traffictwin.experiments.resource_strategy import (
    build_resource_strategy_report,
    load_resource_strategy_study_file,
    resource_strategy_report_to_csv,
    resource_strategy_report_to_markdown,
)


def test_load_build_export_flow() -> None:
    study_path = Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    study = load_resource_strategy_study_file(study_path)
    assert study.study_id == "synthetic_resource_strategy_v1"
    report = build_resource_strategy_report(study)
    # Ensure report can be serialized and deserialized without loss
    json_text = report.to_json()
    data = json.loads(json_text)
    assert data["study_id"] == study.study_id
    assert data["report_fingerprint"] == report.report_fingerprint
    csv_text = resource_strategy_report_to_csv(report)
    assert "task.completion.rate_offered" in csv_text
    md_text = resource_strategy_report_to_markdown(report)
    assert "Resource Strategy Report" in md_text
    assert "Descriptive differences only" in md_text
    # Verify denominators distinct
    assert "offered_tasks" in json_text
    assert "admitted_tasks" in json_text


def test_integration_matched_cohort_exclusions() -> None:
    study = load_resource_strategy_study_file(
        Path("tests/fixtures/resource_strategy/synthetic_study_v1.json")
    )
    report = build_resource_strategy_report(study)
    assert report.common_matched_replication_ids == ["rep_001", "rep_002", "rep_003", "rep_004"]
    assert len(report.excluded_replication_ids) == 1
    assert report.excluded_replication_ids[0].replication_id == "rep_005"
    for arm in report.arm_summaries:
        assert arm.replication_count_matched == 4
        assert arm.replication_count_total == 5
