from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tests.helpers import fixed_clock

from traffictwin.provenance.markdown import trace_to_markdown
from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.provenance.query import (
    build_provenance_context,
    get_metric_provenance,
    get_rule_provenance,
)

EXPECTED = Path("tests/golden/expected")


def test_baseline_completion_rate_trace_matches_golden_projection() -> None:
    context = build_provenance_context("tests/fixtures/bundles/baseline_valid", clock=fixed_clock)
    trace = get_metric_provenance(context, "task.completion.rate", clock=fixed_clock)

    assert _projection(trace) == _read_expected("provenance_metric_trace.json")


def test_variation_infrastructure_trace_matches_golden_projection() -> None:
    context = build_provenance_context("tests/fixtures/bundles/variation_valid", clock=fixed_clock)
    trace = get_metric_provenance(context, "infra.utilisation.p95", clock=fixed_clock)

    assert _projection(trace) == _read_expected("provenance_infra_trace.json")


def test_variation_journey_time_trace_matches_golden_projection() -> None:
    context = build_provenance_context("tests/fixtures/bundles/variation_valid", clock=fixed_clock)
    trace = get_metric_provenance(context, "trip.duration.p95_s", clock=fixed_clock)

    assert _projection(trace) == _read_expected("provenance_journey_trace.json")


def test_diagnostic_trace_matches_golden_projection() -> None:
    context = build_provenance_context("tests/fixtures/bundles/variation_valid", clock=fixed_clock)
    trace = get_rule_provenance(context, "R2", clock=fixed_clock)

    assert _projection(trace) == _read_expected("provenance_diagnostic_trace.json")


def test_partial_bundle_missing_evidence_trace_matches_golden_projection() -> None:
    context = build_provenance_context("tests/fixtures/bundles/partial_valid", clock=fixed_clock)
    trace = get_metric_provenance(context, "infra.utilisation.p95", clock=fixed_clock)

    assert _projection(trace) == _read_expected("provenance_missing_link.json")


def test_markdown_trace_matches_golden() -> None:
    context = build_provenance_context("tests/fixtures/bundles/baseline_valid", clock=fixed_clock)
    trace = get_metric_provenance(context, "task.completion.rate", clock=fixed_clock)

    assert trace_to_markdown(trace) == (EXPECTED / "provenance_trace.md").read_text(
        encoding="utf-8"
    )


def _projection(trace: ProvenanceTrace) -> dict[str, object]:
    nodes = trace.nodes
    edges = trace.edges
    return {
        "root_node_id": trace.root_node_id,
        "completeness": trace.completeness.overall.value,
        "node_types": {
            node_type: sum(1 for node in nodes if node.node_type.value == node_type)
            for node_type in sorted({node.node_type.value for node in nodes})
        },
        "required_nodes": [
            node_id
            for node_id in [
                "metric_definition:task.completion.rate",
                "metric_definition:infra.utilisation.p95",
                "metric_definition:trip.duration.p95_s",
                "canonical_table:tasks",
                "canonical_table:infrastructure",
                "canonical_table:trips",
                "source_file:tasks.csv",
                "source_file:infra_state.csv",
                "source_file:trips.csv",
                "rule_result:R2",
            ]
            if any(node.node_id == node_id for node in nodes)
        ],
        "relations": sorted({edge.relation.value for edge in edges}),
        "source_rows": sum(1 for node in nodes if node.node_type.value == "source_row"),
        "unavailable": sorted(
            node.label for node in nodes if node.node_type.value == "unavailable_reference"
        ),
    }


def _read_expected(filename: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads((EXPECTED / filename).read_text(encoding="utf-8")))
