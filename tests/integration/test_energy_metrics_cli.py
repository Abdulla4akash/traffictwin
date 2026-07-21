from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def test_energy_metric_family_is_exposed_by_cli(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    report_result = CliRunner().invoke(app, ["metrics", "report", str(bundle), "--format", "json"])

    assert report_result.exit_code == 0
    payload = json.loads(report_result.stdout)
    by_key = {metric["metric_key"]: metric for metric in payload["results"]}
    assert by_key["task.energy.mean_per_observed_task_j"]["value"] == 0.9941935483870968
    assert by_key["task.energy.per_completed_j"]["value"] == 0.9941935483870968
    assert by_key["task.energy_delay_product.mean_j_ms"]["value"] == 215.2725101612903
    assert (
        by_key["task.energy.per_completed_j"]["metadata"]["energy_contract_fingerprint"]
        == "d71e4d10bb37aded7a6c8cdfc5b9cde4c59ef41b88c51facb54930ae9664ebaa"
    )

    summary_result = CliRunner().invoke(app, ["metrics", "compute", str(bundle)])
    assert summary_result.exit_code == 0
    assert "task.energy.per_completed_j: 0.9941935483870968" in summary_result.stdout
    assert "task.energy_delay_product.mean_j_ms: 215.2725101612903" in summary_result.stdout
