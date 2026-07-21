from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.ingestion.bundle import validate_bundle

EXAMPLE = Path("examples/synthetic_measurement_imperfections.yaml")


def test_measurement_impairment_contract_is_public_cli() -> None:
    result = CliRunner().invoke(app, ["synthetic", "measurement-contract"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["distribution"] == "bounded_uniform"
    assert payload["supported_dropout_tables"] == [
        "infra_state",
        "vehicle_state",
        "traffic_obs",
    ]
    assert payload["synthetic_only"] is True
    assert payload["calibrated_sensor_model"] is False
    assert payload["direct_launch_supported"] is False


def test_generate_config_cli_writes_valid_impaired_bundle(tmp_path: Path) -> None:
    output = tmp_path / "impaired"
    result = CliRunner().invoke(
        app,
        [
            "synthetic",
            "generate-config",
            "--config",
            str(EXAMPLE),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status: accepted" in result.output
    assert "synthetic: true" in result.output
    assert "measurement_imperfections: true" in result.output
    assert "measurement_rows_dropped: 28" in result.output
    validation = validate_bundle(output)
    assert validation.report.may_import
    assert validation.manifest is not None
    assert validation.manifest.synthetic_measurement_impairment is not None


def test_generate_config_cli_rejects_invalid_or_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    conflict = CliRunner().invoke(
        app,
        [
            "synthetic",
            "generate-config",
            "--config",
            str(EXAMPLE),
            "--output",
            str(output),
        ],
    )
    assert conflict.exit_code == 1
    assert "already exists" in conflict.output

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        "scenario_id: invalid\nname: Invalid\nmeasurement_imperfections:\n"
        "  vehicle_position_max_error_m: 101\n",
        encoding="utf-8",
    )
    rejected = CliRunner().invoke(
        app,
        [
            "synthetic",
            "generate-config",
            "--config",
            str(invalid),
            "--output",
            str(tmp_path / "not-written"),
        ],
    )
    assert rejected.exit_code == 1
    assert "invalid synthetic configuration" in rejected.output
    assert not (tmp_path / "not-written").exists()
