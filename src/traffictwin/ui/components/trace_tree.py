"""Trace display components."""

from __future__ import annotations

import streamlit as st

from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.provenance.query import node_type_counts


def render_trace_summary(trace: ProvenanceTrace) -> None:
    """Render a compact provenance trace summary."""

    st.write(
        {
            "trace_id": trace.trace_id,
            "root": trace.root_node_id,
            "completeness": trace.completeness.overall.value,
            "synthetic": trace.synthetic,
            "source_fingerprint": trace.source_fingerprint or "Unavailable",
            "nodes": len(trace.nodes),
            "edges": len(trace.edges),
        }
    )
    if trace.warnings:
        st.warning("\n".join(trace.warnings))
    st.caption(
        "Provenance shows how TrafficTwin derived a result from available records and configured "
        "rules. It does not establish real-world causality."
    )


def render_trace_lineage(trace: ProvenanceTrace) -> None:
    """Render a readable edge list rather than a cluttered graph."""

    nodes = trace.by_id()
    rows = [
        {
            "source": nodes[edge.source_node_id].label,
            "relation": edge.relation.value,
            "target": nodes[edge.target_node_id].label,
            "confidence": edge.confidence.value,
        }
        for edge in trace.edges
    ]
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No lineage edges are available for this trace.")


def render_trace_nodes(trace: ProvenanceTrace) -> None:
    """Render grouped trace nodes."""

    counts = node_type_counts(trace)
    st.write({"node_type_counts": counts})
    for node_type in sorted(counts):
        with st.expander(f"{node_type} ({counts[node_type]})"):
            rows = [
                {
                    "node_id": node.node_id,
                    "label": node.label,
                    "status": node.status.value,
                    "description": node.description,
                }
                for node in trace.nodes
                if node.node_type.value == node_type
            ]
            st.dataframe(rows, width="stretch", hide_index=True)


def render_trace_completeness(trace: ProvenanceTrace) -> None:
    """Render completeness by provenance category."""

    rows = [
        {
            "category": category,
            "status": status.value,
            "reason": "; ".join(trace.completeness.reasons.get(category, [])),
        }
        for category, status in sorted(trace.completeness.categories.items())
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
