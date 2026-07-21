from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.storage.registry import Registry


def test_stream_validate_cli_emits_typed_json() -> None:
    result = CliRunner().invoke(
        app,
        [
            "bundle",
            "stream-validate",
            "tests/fixtures/bundles/baseline_valid",
            "--chunk-rows",
            "1",
            "--max-chunk-bytes",
            "1024",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["report"]["status"] == "accepted"
    assert payload["streaming"]["chunk_count"] == 11
    assert payload["streaming"]["max_observed_chunk_source_rows"] == 1
    assert payload["streaming"]["canonical_record_counts"]["tasks"] == 3


def test_stream_import_cli_preserves_registry_idempotency(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    command = [
        "bundle",
        "stream-import",
        "tests/fixtures/bundles/baseline_valid",
        "--registry",
        str(registry_path),
        "--chunk-rows",
        "2",
        "--max-chunk-bytes",
        "1024",
        "--format",
        "json",
    ]
    runner = CliRunner()

    first = runner.invoke(app, command)
    repeated = runner.invoke(app, command)

    assert first.exit_code == 0
    assert json.loads(first.stdout)["registry"]["created"] is True
    assert repeated.exit_code == 0
    assert json.loads(repeated.stdout)["registry"]["idempotent"] is True
    assert Registry(registry_path).inspect().bundle_import_count == 1


def test_stream_validate_cli_rejects_inconsistent_limits() -> None:
    result = CliRunner().invoke(
        app,
        [
            "bundle",
            "stream-validate",
            "tests/fixtures/bundles/baseline_valid",
            "--max-chunk-bytes",
            "2048",
            "--max-table-bytes",
            "1024",
        ],
    )

    assert result.exit_code == 1
    assert "invalid streaming configuration" in result.stderr


def test_stream_validate_cli_writes_summary(tmp_path: Path) -> None:
    output = tmp_path / "streaming.json"
    result = CliRunner().invoke(
        app,
        [
            "bundle",
            "stream-validate",
            "tests/fixtures/bundles/baseline_valid",
            "--format",
            "json",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "streaming validation summary written" in result.stdout
    assert json.loads(output.read_text(encoding="utf-8"))["report"]["may_import"] is True
