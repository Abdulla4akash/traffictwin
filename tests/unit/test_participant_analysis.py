from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.evaluation.participants import (
    MockParticipantDataset,
    analyse_participant_results,
    load_mock_participant_dataset,
    participant_analysis_to_csv,
)


def test_mock_participant_analysis_excludes_withdrawn_records() -> None:
    dataset = load_mock_participant_dataset("docs/evaluation/mock_results.json")

    report = analyse_participant_results(dataset)

    assert report.labelled_mock_data is True
    assert report.total_records == 4
    assert report.included_records == 3
    assert report.withdrawn_records_excluded == 1
    tasks = {row.task_id: row for row in report.task_aggregates}
    assert tasks["T1"].success_rate == 1.0
    assert tasks["T2"].success_rate == pytest.approx(2 / 3)
    assert "excluded_mock_code" not in report.coded_comment_counts
    assert participant_analysis_to_csv(report).startswith("section,identifier,measure,value")


def test_participant_dataset_requires_explicit_mock_label() -> None:
    payload = json.loads(Path("docs/evaluation/mock_results.json").read_text(encoding="utf-8"))
    payload["dataset_mode"] = "collected"

    with pytest.raises(ValidationError):
        MockParticipantDataset.model_validate(payload)


def test_participant_analysis_cli_emits_labelled_json() -> None:
    result = CliRunner().invoke(
        app,
        ["participant-evaluation", "analyse-mock", "docs/evaluation/mock_results.json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["source_mode"] == "synthetic_mock"
    assert payload["withdrawn_records_excluded"] == 1
