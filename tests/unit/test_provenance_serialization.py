from __future__ import annotations

import json

from tests.helpers import bundle_result, fixed_clock, metric_collection
from traffictwin.provenance.builder import build_metric_trace
from traffictwin.provenance.serialization import trace_to_json


def test_trace_json_is_finite_and_machine_readable() -> None:
    trace = build_metric_trace(
        "task.completion.rate",
        bundle_result("baseline_valid"),
        metric_collection("baseline_valid"),
        clock=fixed_clock,
    )
    payload = trace_to_json(trace)
    data = json.loads(payload)

    assert data["schema_version"] == "1.0"
    assert data["root_node_id"] == "metric_result:run-baseline-001:task.completion.rate"
    assert "NaN" not in payload
    assert "Infinity" not in payload
