from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.experiments.parameter_sweep import (
    ParameterSweepMode,
    ParameterSweepRequest,
    SweepAxis,
    SweepParameter,
    parameter_sweep_request_to_yaml,
)
from traffictwin.synthetic.scenarios import preset_config


def _request_file(path: Path) -> Path:
    request = ParameterSweepRequest(
        sweep_id="sweep-cli",
        title="CLI response surface",
        mode=ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES,
        base_synthetic_config=preset_config("baseline"),
        axes=[
            SweepAxis(
                parameter_path=SweepParameter.SYNTHETIC_TASK_ARRIVAL_RATE,
                values=[0.08, 0.12],
            )
        ],
        metric_keys=["task.completion.rate"],
    )
    path.write_text(parameter_sweep_request_to_yaml(request), encoding="utf-8")
    return path


def test_parameter_sweep_contract_is_public_cli() -> None:
    result = CliRunner().invoke(app, ["experiment", "parameter-sweep-contract"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["max_points"] == 256
    assert payload["direct_launch_supported"] is False
    assert payload["external_execution_status"] == "not_executed"


def test_parameter_sweep_cli_materialises_response_surface(tmp_path: Path) -> None:
    request_path = _request_file(tmp_path / "request.yaml")
    output = tmp_path / "sweep"

    result = CliRunner().invoke(
        app,
        [
            "experiment",
            "parameter-sweep",
            "--request",
            str(request_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status: completed_local_analysis" in result.output
    assert "points: 2" in result.output
    assert "response_rows: 2" in result.output
    assert "direct_launch_supported: false" in result.output
    payload = json.loads((output / "sweep_result.json").read_text(encoding="utf-8"))
    assert payload["synthetic_evaluation"] is True
    assert payload["point_count"] == 2
    rows = list(csv.DictReader(io.StringIO((output / "response_surface.csv").read_text())))
    assert len(rows) == 2


def test_parameter_sweep_cli_rejects_existing_destination(tmp_path: Path) -> None:
    request_path = _request_file(tmp_path / "request.yaml")
    output = tmp_path / "sweep"
    output.mkdir()

    result = CliRunner().invoke(
        app,
        [
            "experiment",
            "parameter-sweep",
            "--request",
            str(request_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "destination already exists" in result.output
