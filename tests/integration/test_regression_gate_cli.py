from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collection,
    study_collections,
)
from typer.testing import CliRunner, Result

from traffictwin.cli import app
from traffictwin.experiments.statistical_study import evaluate_paired_statistical_study
from traffictwin.metrics.results import MetricStatus
from traffictwin.storage.registry import Registry


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    subjects = [
        study_collection("baseline", 1, 0.8, run_id="run-golden"),
        study_collection("baseline", 2, 0.805, run_id="run-pass"),
        study_collection("baseline", 3, 0.9, run_id="run-fail"),
        study_collection(
            "baseline",
            4,
            None,
            run_id="run-unavailable",
            metric_status=MetricStatus.UNAVAILABLE,
        ),
    ]
    for collection in subjects:
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    return path


def _write_approved_metric_golden(tmp_path: Path, registry: Path) -> Path:
    output = tmp_path / "golden.json"
    result = CliRunner().invoke(
        app,
        [
            "experiment",
            "regression-golden",
            "run-golden",
            "--registry",
            str(registry),
            "--contract-id",
            "completion-ci",
            "--contract-version",
            "1.0.0",
            "--tolerance",
            "task.completion.rate=0.01,0",
            "--source-identity-policy",
            "compatible_context",
            "--approval-status",
            "approved",
            "--approved-by",
            "repository-owner",
            "--approval-note",
            "Approved synthetic fixture boundary for CLI verification",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    return output


def test_regression_contract_and_candidate_generation_cli(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    method = CliRunner().invoke(
        app,
        ["experiment", "regression-contract", "--format", "json"],
    )
    candidate = CliRunner().invoke(
        app,
        [
            "experiment",
            "regression-golden",
            "run-golden",
            "--registry",
            str(registry),
            "--contract-id",
            "completion-candidate",
            "--contract-version",
            "1.0.0",
            "--tolerance",
            "task.completion.rate=0.01,0.02",
        ],
    )

    assert method.exit_code == 0, method.output
    assert json.loads(method.output)["ci_exit_codes"] == {
        "passed": 0,
        "failed": 1,
        "unavailable": 2,
    }
    assert candidate.exit_code == 0, candidate.output
    payload = json.loads(candidate.output)
    assert payload["approval_status"] == "candidate"
    assert payload["assertions"][0]["expected_value"] == 0.8


def test_metric_regression_gate_distinguishes_pass_fail_and_unavailable_exit_codes(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)
    golden = _write_approved_metric_golden(tmp_path, registry)

    def run(subject: str) -> Result:
        return CliRunner().invoke(
            app,
            [
                "experiment",
                "regression-gate",
                subject,
                "--registry",
                str(registry),
                "--golden",
                str(golden),
            ],
        )

    passed = run("run-pass")
    failed = run("run-fail")
    unavailable = run("run-unavailable")

    assert passed.exit_code == 0, passed.output
    assert json.loads(passed.output)["status"] == "passed"
    assert failed.exit_code == 1
    assert json.loads(failed.output)["status"] == "failed"
    assert unavailable.exit_code == 2
    assert json.loads(unavailable.output)["status"] == "unavailable"


def test_regression_gate_exports_markdown_and_csv_cli(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    golden = _write_approved_metric_golden(tmp_path, registry)
    markdown_path = tmp_path / "gate.md"
    markdown = CliRunner().invoke(
        app,
        [
            "experiment",
            "regression-gate",
            "run-pass",
            "--registry",
            str(registry),
            "--golden",
            str(golden),
            "--format",
            "markdown",
            "--output",
            str(markdown_path),
        ],
    )
    csv_result = CliRunner().invoke(
        app,
        [
            "experiment",
            "regression-gate",
            "run-pass",
            "--registry",
            str(registry),
            "--golden",
            str(golden),
            "--format",
            "csv",
        ],
    )

    assert markdown.exit_code == 0, markdown.output
    assert "# TrafficTwin Regression Gate" in markdown_path.read_text(encoding="utf-8")
    assert csv_result.exit_code == 0, csv_result.output
    assert "ASSERTION_PASSED" in csv_result.output


def test_paired_statistical_study_golden_and_gate_cli(tmp_path: Path) -> None:
    study = evaluate_paired_statistical_study(
        study_collections([-0.1, 0.0, 0.2]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    subject_path = tmp_path / "study.json"
    subject_path.write_text(study.to_json(), encoding="utf-8")
    golden_path = tmp_path / "study-golden.json"
    golden = CliRunner().invoke(
        app,
        [
            "experiment",
            "regression-golden",
            str(subject_path),
            "--subject-kind",
            "paired_statistical_study",
            "--contract-id",
            "paired-study-ci",
            "--contract-version",
            "1.0.0",
            "--tolerance",
            "estimate.mean_paired_difference=0.01,0",
            "--approval-status",
            "approved",
            "--approved-by",
            "repository-owner",
            "--approval-note",
            "Approved synthetic paired-study fixture for CLI verification",
            "--output",
            str(golden_path),
        ],
    )
    gate = CliRunner().invoke(
        app,
        [
            "experiment",
            "regression-gate",
            str(subject_path),
            "--golden",
            str(golden_path),
        ],
    )

    assert golden.exit_code == 0, golden.output
    assert gate.exit_code == 0, gate.output
    payload = json.loads(gate.output)
    assert payload["subject_kind"] == "paired_statistical_study"
    assert payload["status"] == "passed"
