from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

EXPECTED = Path("tests/golden/expected/synthetic_energy_metrics.json")
ENERGY_KEYS = (
    "task.energy.mean_per_observed_task_j",
    "task.energy.per_completed_j",
    "task.energy_delay_product.mean_j_ms",
)


def test_synthetic_energy_metric_projection_is_exact(tmp_path: Path) -> None:
    bundle = validate_bundle(
        write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    )
    metrics = compute_metrics_for_bundle(bundle, clock=fixed_clock).by_key()
    projection = {
        "synthetic": True,
        "energy_contract": bundle.manifest.energy_contract.model_dump(mode="json")
        if bundle.manifest is not None and bundle.manifest.energy_contract is not None
        else None,
        "metrics": {
            key: {
                "status": metrics[key].status.value,
                "value": metrics[key].value,
                "unit": metrics[key].unit,
                "metadata": metrics[key].metadata,
                "warnings": metrics[key].warnings,
            }
            for key in ENERGY_KEYS
        },
    }

    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
