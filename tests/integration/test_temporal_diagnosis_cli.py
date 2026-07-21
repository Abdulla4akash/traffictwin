from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app


def test_temporal_diagnosis_cli_emits_evidencepack_and_r6_contract() -> None:
    result = CliRunner().invoke(
        app,
        [
            "diagnose",
            "temporal",
            "tests/fixtures/bundles/baseline_valid",
            "--width-s",
            "1",
            "--start-s",
            "0",
            "--end-s",
            "10",
            "--metric-key",
            "task.completion.rate",
            "--event-time-s",
            "5",
            "--event-label",
            "declared test event",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    temporal = payload["temporal_evidence"]
    r6 = payload["r6_result"]
    report = payload["diagnostic_report"]
    assert temporal["boundary"] == "[start,end)"
    assert temporal["metric_key"] == "task.completion.rate"
    assert temporal["event"]["event_window_ordinal"] == 5
    assert r6["rule_id"] == "R6"
    assert report["provenance"]["temporal_evidence_fingerprint"]


def test_temporal_diagnosis_cli_writes_json_and_rejects_event_label_without_time(
    tmp_path: Path,
) -> None:
    output = tmp_path / "r6.json"
    written = CliRunner().invoke(
        app,
        [
            "diagnose",
            "temporal",
            "tests/fixtures/bundles/baseline_valid",
            "--width-s",
            "1",
            "--start-s",
            "0",
            "--end-s",
            "10",
            "--metric-key",
            "task.completion.rate",
            "--output",
            str(output),
        ],
    )
    rejected = CliRunner().invoke(
        app,
        [
            "diagnose",
            "temporal",
            "tests/fixtures/bundles/baseline_valid",
            "--width-s",
            "1",
            "--event-label",
            "unanchored",
        ],
    )

    assert written.exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["r6_result"]["rule_id"] == "R6"
    assert rejected.exit_code == 1
    assert "event_label requires event_time_s" in rejected.stderr
