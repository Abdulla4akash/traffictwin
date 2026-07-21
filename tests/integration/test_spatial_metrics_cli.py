from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def test_metrics_cli_exposes_spatial_and_per_rsu_family(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    result = CliRunner().invoke(app, ["metrics", "compute", str(bundle)])

    assert result.exit_code == 0
    assert "spatial.rsu.task.count_by_target:" in result.stdout
    assert "spatial.rsu.task.completion_rate_by_target:" in result.stdout
    assert "spatial.vehicle.observation_count_by_grid_cell:" in result.stdout
    assert "spatial.vehicle.speed.mean_mps_by_grid_cell:" in result.stdout
