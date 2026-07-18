from __future__ import annotations

import pytest

from tests.helpers import fixed_clock
from traffictwin.provenance.graph import ProvenanceGraphError, TraceGraph
from traffictwin.provenance.models import (
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    TraceCompleteness,
    TraceCompletenessSummary,
)


def test_graph_rejects_duplicate_node_payload() -> None:
    graph = TraceGraph()
    graph.add_node(ProvenanceNode(node_id="node:1", node_type=ProvenanceNodeType.RUN, label="A"))

    with pytest.raises(ProvenanceGraphError):
        graph.add_node(
            ProvenanceNode(node_id="node:1", node_type=ProvenanceNodeType.RUN, label="B")
        )


def test_graph_validates_edge_endpoints_and_orders_output() -> None:
    graph = TraceGraph()
    graph.add_node(ProvenanceNode(node_id="run:1", node_type=ProvenanceNodeType.RUN, label="Run"))
    graph.add_node(
        ProvenanceNode(
            node_id="manifest:1",
            node_type=ProvenanceNodeType.MANIFEST,
            label="Manifest",
        )
    )
    graph.add_edge("run:1", "manifest:1", ProvenanceRelation.GENERATED_FROM)

    trace = graph.to_trace(
        root_node_id="run:1",
        generated_at=fixed_clock(),
        source_fingerprint="abc",
        synthetic=True,
        completeness=TraceCompletenessSummary(overall=TraceCompleteness.COMPLETE),
    )

    assert [node.node_id for node in trace.nodes] == ["manifest:1", "run:1"]
    assert trace.edges[0].source_node_id == "run:1"

    with pytest.raises(ProvenanceGraphError):
        graph.add_edge("run:1", "missing", ProvenanceRelation.CONTAINS)
