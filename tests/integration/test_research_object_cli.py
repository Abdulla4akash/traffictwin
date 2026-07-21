from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "bundles"
BASELINE = FIXTURES / "baseline_valid"


def test_archive_cli_contract_create_and_verify(tmp_path: Path) -> None:
    contract_result = CliRunner().invoke(
        app,
        ["archive", "contract", "--format", "json"],
    )
    archive = tmp_path / "baseline-ro-crate.zip"
    create_result = CliRunner().invoke(
        app,
        [
            "archive",
            "create",
            str(BASELINE),
            str(archive),
            "--publication-date",
            "2026-07-21",
            "--raw-evidence",
            "embed",
            "--format",
            "json",
        ],
    )
    verify_result = CliRunner().invoke(
        app,
        ["archive", "verify", str(archive), "--format", "json"],
    )

    assert contract_result.exit_code == 0, contract_result.output
    assert create_result.exit_code == 0, create_result.output
    assert verify_result.exit_code == 0, verify_result.output
    assert json.loads(contract_result.output)["capability_id"] == "OPS-04"
    receipt = json.loads(create_result.output)
    verification = json.loads(verify_result.output)
    assert archive.is_file()
    assert receipt["verified_before_publication"] is True
    assert receipt["archive_sha256"] == verification["archive_sha256"]
    assert verification["valid"] is True


def test_archive_cli_rejects_invalid_policy_without_publishing(tmp_path: Path) -> None:
    archive = tmp_path / "invalid.zip"

    result = CliRunner().invoke(
        app,
        [
            "archive",
            "create",
            str(BASELINE),
            str(archive),
            "--publication-date",
            "not-a-date",
        ],
    )

    assert result.exit_code == 1
    assert archive.exists() is False
