from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.helpers import fixed_clock

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.spatial import RSU_TASK_BREAKDOWN_KEYS, VEHICLE_GRID_KEYS
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

EXPECTED = Path("tests/golden/expected/synthetic_spatial_metrics.json")


def test_synthetic_spatial_family_matches_golden_projection(tmp_path: Path) -> None:
    bundle = validate_bundle(
        write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    )
    metrics = compute_metrics_for_bundle(bundle, clock=fixed_clock).by_key()

    assert _projection(metrics) == json.loads(EXPECTED.read_text(encoding="utf-8"))


def _projection(metrics: dict[str, Any]) -> dict[str, Any]:
    target = metrics[RSU_TASK_BREAKDOWN_KEYS[0]]
    grid = metrics[VEHICLE_GRID_KEYS[0]]
    return {
        "run_id": target.run_id,
        "target_metrics": {
            key: {
                "status": metrics[key].status.value,
                "value": metrics[key].value,
                "unit": metrics[key].unit,
                "coverage_fraction": metrics[key].metadata["coverage_fraction"],
                "group_support_counts": metrics[key].metadata["group_support_counts"],
                "group_set_fingerprint": metrics[key].metadata["group_set_fingerprint"],
            }
            for key in RSU_TASK_BREAKDOWN_KEYS
        },
        "grid_metrics": {
            key: {
                "status": metrics[key].status.value,
                "value": metrics[key].value,
                "unit": metrics[key].unit,
                "coverage_fraction": metrics[key].metadata["coverage_fraction"],
                "cell_support_counts": metrics[key].metadata["cell_support_counts"],
                "group_set_fingerprint": metrics[key].metadata["group_set_fingerprint"],
            }
            for key in VEHICLE_GRID_KEYS
        },
        "task_rsu_target_contract_fingerprint": target.metadata[
            "task_rsu_target_contract_fingerprint"
        ],
        "vehicle_spatial_grid_contract_fingerprint": grid.metadata[
            "vehicle_spatial_grid_contract_fingerprint"
        ],
    }
