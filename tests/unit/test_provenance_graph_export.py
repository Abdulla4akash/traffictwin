from __future__ import annotations

from datetime import UTC, datetime
from xml.etree import ElementTree

import pytest

from tests.helpers import fixed_clock
from traffictwin.provenance.graph import TraceGraph
from traffictwin.provenance.graph_export import (
    ABSOLUTE_PATH_REDACTION,
    DEFAULT_GRAPH_EDGE_LIMIT,
    DEFAULT_GRAPH_NODE_LIMIT,
    MAX_GRAPH_EDGE_LIMIT,
    MAX_GRAPH_NODE_LIMIT,
    GraphExportError,
    GraphRedactionMode,
    build_provenance_graph_view,
    provenance_graph_export_contract,
    provenance_graph_to_dot,
    provenance_graph_to_graphml,
)
from traffictwin.provenance.models import (
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    ProvenanceTrace,
    SourceReference,
    TraceCompleteness,
    TraceCompletenessSummary,
)
from traffictwin.provenance.query import build_provenance_context, get_run_provenance


def _baseline_trace() -> ProvenanceTrace:
    context = build_provenance_context(
        "tests/fixtures/bundles/baseline_valid",
        clock=fixed_clock,
    )
    return get_run_provenance(context, clock=fixed_clock)


def test_bounded_view_is_root_centred_and_reports_exact_omissions() -> None:
    trace = _baseline_trace()

    view = build_provenance_graph_view(trace, node_limit=5, edge_limit=3)

    assert view.root_node_id == trace.root_node_id
    assert view.nodes[0].node_id == trace.root_node_id
    assert len(view.nodes) == 5
    assert len(view.edges) == 3
    assert view.omitted_node_count == len(trace.nodes) - 5
    assert view.omitted_edge_count == len(trace.edges) - 3
    assert view.truncated is True
    assert all(
        edge.source_node_id in {node.node_id for node in view.nodes}
        and edge.target_node_id in {node.node_id for node in view.nodes}
        for edge in view.edges
    )


def test_graph_identity_ignores_limits_and_volatile_trace_timestamps() -> None:
    trace = _baseline_trace()
    changed_time = datetime(2035, 1, 2, tzinfo=UTC)
    changed = trace.model_copy(
        update={
            "trace_id": "different-volatile-trace-id",
            "generated_at": changed_time,
            "nodes": [node.model_copy(update={"created_at": changed_time}) for node in trace.nodes],
        }
    )

    small = build_provenance_graph_view(trace, node_limit=5, edge_limit=5)
    large = build_provenance_graph_view(trace, node_limit=40, edge_limit=40)
    changed_view = build_provenance_graph_view(changed, node_limit=5, edge_limit=5)

    assert small.graph_id == large.graph_id == changed_view.graph_id
    assert small.canonical_json() == changed_view.canonical_json()
    assert small.fingerprint() == changed_view.fingerprint()


def test_dot_and_graphml_are_deterministic_and_graphml_parses() -> None:
    view = build_provenance_graph_view(_baseline_trace(), node_limit=20, edge_limit=30)

    first_dot = provenance_graph_to_dot(view)
    first_graphml = provenance_graph_to_graphml(view)

    assert first_dot == provenance_graph_to_dot(view)
    assert first_graphml == provenance_graph_to_graphml(view)
    assert first_dot.startswith("digraph TrafficTwinProvenance")
    parsed = ElementTree.fromstring(first_graphml)  # noqa: S314 - parses local serializer output
    namespace = {"g": "http://graphml.graphdrawing.org/xmlns"}
    assert len(parsed.findall(".//g:node", namespace)) == len(view.nodes)
    assert len(parsed.findall(".//g:edge", namespace)) == len(view.edges)


def test_local_paths_are_redacted_and_dot_xml_text_is_escaped() -> None:
    graph = TraceGraph()
    graph.add_node(
        ProvenanceNode(
            node_id="source_file:/Users/alice/private/input.csv",
            node_type=ProvenanceNodeType.SOURCE_FILE,
            label='Private "/Users/alice/private/input.csv"',
            description=r"C:\Users\alice\private\input.csv",
            attributes={
                "uri": "file:///Users/alice/private/input.csv",
                "relative": "tables/tasks.csv",
            },
            source_reference=SourceReference(
                bundle_reference="bundle-1",
                file="/srv/private/input.csv",
            ),
        )
    )
    graph.add_node(
        ProvenanceNode(
            node_id="run:safe",
            node_type=ProvenanceNodeType.RUN,
            label="Run <safe> & review",
        )
    )
    graph.add_edge(
        "source_file:/Users/alice/private/input.csv",
        "run:safe",
        ProvenanceRelation.GENERATED_FROM,
        description="See ~/private/note.txt",
    )
    trace = graph.to_trace(
        root_node_id="source_file:/Users/alice/private/input.csv",
        generated_at=fixed_clock(),
        source_fingerprint="abc",
        synthetic=False,
        completeness=TraceCompletenessSummary(overall=TraceCompleteness.PARTIAL),
    )

    view = build_provenance_graph_view(trace)
    dot = provenance_graph_to_dot(view)
    graphml = provenance_graph_to_graphml(view)

    assert view.root_node_id == "provenance-redacted-node-0001"
    assert view.redaction_count >= 5
    assert ABSOLUTE_PATH_REDACTION in dot
    assert "tables/tasks.csv" in graphml
    for secret in ["/Users/alice", r"C:\Users\alice", "file:///Users", "~/private", "/srv/private"]:
        assert secret not in dot
        assert secret not in graphml
    ElementTree.fromstring(graphml)  # noqa: S314 - parses local serializer output
    assert r"\"" in dot
    assert "&lt;safe&gt;" in graphml


def test_structure_only_removes_details_but_preserves_graph_shape() -> None:
    trace = _baseline_trace()
    safe = build_provenance_graph_view(trace, redaction_mode=GraphRedactionMode.SAFE)
    structural = build_provenance_graph_view(
        trace,
        redaction_mode=GraphRedactionMode.STRUCTURE_ONLY,
    )

    assert [node.node_id for node in safe.nodes] == [node.node_id for node in structural.nodes]
    assert [edge.source_node_id for edge in safe.edges] == [
        edge.source_node_id for edge in structural.edges
    ]
    assert all(not node.attributes for node in structural.nodes)
    assert all(node.description is None for node in structural.nodes)
    assert all(node.source_reference is None for node in structural.nodes)
    assert all(edge.description is None for edge in structural.edges)
    assert structural.redaction_count > safe.redaction_count


def test_graph_export_contract_and_limit_validation_are_explicit() -> None:
    contract = provenance_graph_export_contract()
    trace = _baseline_trace()

    assert contract.capability_id == "PRO-02"
    assert contract.formats == ["dot", "graphml"]
    assert contract.default_node_limit == DEFAULT_GRAPH_NODE_LIMIT
    assert contract.default_edge_limit == DEFAULT_GRAPH_EDGE_LIMIT
    assert contract.maximum_node_limit == MAX_GRAPH_NODE_LIMIT
    assert contract.maximum_edge_limit == MAX_GRAPH_EDGE_LIMIT
    with pytest.raises(GraphExportError, match="node_limit"):
        build_provenance_graph_view(trace, node_limit=0)
    with pytest.raises(GraphExportError, match="edge_limit"):
        build_provenance_graph_view(trace, edge_limit=MAX_GRAPH_EDGE_LIMIT + 1)
    with pytest.raises(GraphExportError, match="redaction_mode"):
        build_provenance_graph_view(trace, redaction_mode="unsafe")
