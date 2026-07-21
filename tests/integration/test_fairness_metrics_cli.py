from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def test_metrics_cli_exposes_operational_fairness_family(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    result = CliRunner().invoke(app, ["metrics", "compute", str(bundle)])

    assert result.exit_code == 0
    assert "fairness.vehicle_tier.completion_rate.max_gap: 0.16666666666666663" in result.stdout
    assert "fairness.vehicle_tier.completion_rate.jain: 0.993127147766323" in result.stdout
    assert "fairness.rsu.capacity_normalised_load.max_gap: 0.0" in result.stdout
    assert "infra.load_balance.jain_capacity_normalised: 1.0" in result.stdout
