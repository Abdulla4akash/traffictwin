from __future__ import annotations

from pathlib import Path

from tests.helpers import fixed_clock

from traffictwin.provenance.graph import TraceGraph
from traffictwin.provenance.graph_export import (
    build_provenance_graph_view,
    provenance_graph_to_dot,
    provenance_graph_to_graphml,
)
from traffictwin.provenance.models import (
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    SourceReference,
    TraceCompleteness,
    TraceCompletenessSummary,
)

EXPECTED = Path("tests/golden/expected")


def test_small_provenance_graph_exports_match_golden_files() -> None:
    graph = TraceGraph()
    graph.add_node(
        ProvenanceNode(
            node_id="metric_result:run-1:task.completion.rate",
            node_type=ProvenanceNodeType.METRIC_RESULT,
            label="task.completion.rate",
            attributes={"unit": "ratio", "value": 0.75},
            synthetic=True,
        )
    )
    graph.add_node(
        ProvenanceNode(
            node_id="canonical_table:tasks",
            node_type=ProvenanceNodeType.CANONICAL_TABLE,
            label="Canonical tasks",
            attributes={"record_count": 4},
            synthetic=True,
        )
    )
    graph.add_node(
        ProvenanceNode(
            node_id="source_file:tasks.csv",
            node_type=ProvenanceNodeType.SOURCE_FILE,
            label="tasks.csv",
            source_reference=SourceReference(
                bundle_reference="bundle-1",
                file="tasks.csv",
            ),
            synthetic=True,
        )
    )
    graph.add_edge(
        "metric_result:run-1:task.completion.rate",
        "canonical_table:tasks",
        ProvenanceRelation.COMPUTED_FROM,
    )
    graph.add_edge(
        "canonical_table:tasks",
        "source_file:tasks.csv",
        ProvenanceRelation.GENERATED_FROM,
    )
    trace = graph.to_trace(
        root_node_id="metric_result:run-1:task.completion.rate",
        generated_at=fixed_clock(),
        source_fingerprint="abc",
        synthetic=True,
        completeness=TraceCompletenessSummary(overall=TraceCompleteness.COMPLETE),
    )
    view = build_provenance_graph_view(trace)

    assert provenance_graph_to_dot(view) == (EXPECTED / "provenance_graph_small.dot").read_text(
        encoding="utf-8"
    )
    assert provenance_graph_to_graphml(view) == (
        EXPECTED / "provenance_graph_small.graphml"
    ).read_text(encoding="utf-8")
