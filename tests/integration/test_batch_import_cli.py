from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.storage.registry import Registry


def test_batch_validate_cli_reports_partial_result_as_json() -> None:
    result = CliRunner().invoke(
        app,
        [
            "bundle",
            "batch-validate",
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/invalid_manifest",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["overall_status"] == "partial"
    assert payload["accepted_count"] == 1
    assert payload["rejected_count"] == 1


def test_batch_import_cli_isolates_rejected_bundle_and_is_idempotent(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.sqlite"
    runner = CliRunner()
    first = runner.invoke(
        app,
        [
            "bundle",
            "batch-import",
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/invalid_manifest",
            "tests/fixtures/bundles/variation_valid",
            "--registry",
            str(registry_path),
            "--format",
            "json",
        ],
    )

    assert first.exit_code == 1
    first_payload = json.loads(first.stdout)
    assert first_payload["created_count"] == 2
    assert first_payload["rejected_count"] == 1
    assert Registry(registry_path).inspect().bundle_import_count == 2

    repeated = runner.invoke(
        app,
        [
            "bundle",
            "batch-import",
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/variation_valid",
            "--registry",
            str(registry_path),
            "--format",
            "json",
        ],
    )

    assert repeated.exit_code == 0
    repeated_payload = json.loads(repeated.stdout)
    assert repeated_payload["idempotent_count"] == 2
    assert repeated_payload["overall_status"] == "complete"


def test_batch_validate_cli_writes_csv_summary(tmp_path: Path) -> None:
    output = tmp_path / "batch.csv"
    result = CliRunner().invoke(
        app,
        [
            "bundle",
            "batch-validate",
            "tests/fixtures/bundles/baseline_valid",
            "--format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "batch summary written" in result.stdout
    assert output.read_text(encoding="utf-8").splitlines()[0].startswith("source,matched_by")


def test_batch_validate_cli_rejects_unknown_output_format() -> None:
    result = CliRunner().invoke(
        app,
        [
            "bundle",
            "batch-validate",
            "tests/fixtures/bundles/baseline_valid",
            "--format",
            "yaml",
        ],
    )

    assert result.exit_code == 1
    assert "only --format text, json, or csv is supported" in result.stderr
