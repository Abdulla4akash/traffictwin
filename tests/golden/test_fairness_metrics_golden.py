from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.helpers import fixed_clock

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

EXPECTED = Path("tests/golden/expected/synthetic_fairness_metrics.json")
KEYS = (
    "task.completion.rate_by_vehicle_tier",
    "fairness.vehicle_tier.completion_rate.max_gap",
    "fairness.vehicle_tier.completion_rate.jain",
    "fairness.rsu.capacity_normalised_load.by_group",
    "fairness.rsu.capacity_normalised_load.max_gap",
    "infra.load_balance.jain_capacity_normalised",
)


def test_synthetic_fairness_family_matches_golden_projection(tmp_path: Path) -> None:
    bundle = validate_bundle(
        write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    )
    metrics = compute_metrics_for_bundle(bundle, clock=fixed_clock)

    assert _projection(metrics.by_key()) == json.loads(EXPECTED.read_text(encoding="utf-8"))


def _projection(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": metrics[KEYS[0]].run_id,
        "metrics": {
            key: {
                "status": metrics[key].status.value,
                "value": metrics[key].value,
                "unit": metrics[key].unit,
                "coverage_fraction": metrics[key].metadata["coverage_fraction"],
                "group_support_counts": metrics[key].metadata["group_support_counts"],
                "group_set_fingerprint": metrics[key].metadata["group_set_fingerprint"],
            }
            for key in KEYS
        },
        "fairness_policy_fingerprint": metrics[KEYS[0]].metadata["fairness_policy_fingerprint"],
    }
