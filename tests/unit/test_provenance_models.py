from __future__ import annotations

from pydantic import ValidationError

from tests.helpers import fixed_clock
from traffictwin.provenance.models import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    ProvenanceTrace,
    TraceCompleteness,
    TraceCompletenessSummary,
)


def test_trace_rejects_missing_edge_reference() -> None:
    node = ProvenanceNode(
        node_id="run:1",
        node_type=ProvenanceNodeType.RUN,
        label="Run 1",
    )

    try:
        ProvenanceTrace(
            trace_id="trace-1",
            root_node_id=node.node_id,
            nodes=[node],
            edges=[
                ProvenanceEdge(
                    source_node_id=node.node_id,
                    target_node_id="missing",
                    relation=ProvenanceRelation.CONTAINS,
                )
            ],
            generated_at=fixed_clock(),
            completeness=TraceCompletenessSummary(overall=TraceCompleteness.PARTIAL),
        )
    except ValidationError as exc:
        assert "edge target node is missing" in str(exc)
    else:
        raise AssertionError("missing edge target should fail validation")


def test_trace_canonical_json_normalises_generated_time() -> None:
    node = ProvenanceNode(
        node_id="run:1",
        node_type=ProvenanceNodeType.RUN,
        label="Run 1",
    )
    trace = ProvenanceTrace(
        trace_id="trace-1",
        root_node_id=node.node_id,
        nodes=[node],
        edges=[],
        generated_at=fixed_clock(),
        completeness=TraceCompletenessSummary(overall=TraceCompleteness.COMPLETE),
    )

    assert "<normalised>" in trace.canonical_json()
    assert trace.fingerprint() == trace.fingerprint()
