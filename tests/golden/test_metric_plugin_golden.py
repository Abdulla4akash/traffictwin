from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.unit.test_metric_plugins import PLUGIN_KEY, _compute, _registry

EXPECTED = Path("tests/golden/expected/metric_plugin_contract.json")


def test_metric_plugin_registry_and_result_match_golden_contract() -> None:
    registry = _registry()
    metric = _compute(registry).by_key()[PLUGIN_KEY]
    projection: dict[str, Any] = {
        "registry": registry.report().model_dump(mode="json"),
        "metric": {
            "metric_key": metric.metric_key,
            "status": metric.status.value,
            "value": metric.value,
            "unit": metric.unit,
            "scope": metric.scope,
            "implementation_version": metric.implementation_version,
            "reason_codes": [item.value for item in metric.reason_codes],
            "missing_evidence": metric.missing_evidence,
            "plugin_contract_fingerprint": metric.metadata["plugin_contract_fingerprint"],
            "plugin_input_record_counts": metric.metadata["plugin_input_record_counts"],
            "plugin_eligible_record_counts": metric.metadata["plugin_eligible_record_counts"],
            "plugin_determinism_verified": metric.metadata["plugin_determinism_verified"],
        },
    }

    assert projection == json.loads(EXPECTED.read_text(encoding="utf-8"))
