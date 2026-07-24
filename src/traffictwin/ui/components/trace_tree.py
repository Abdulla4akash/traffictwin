"""Trace display components."""

from __future__ import annotations

import streamlit as st

from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.provenance.query import node_type_counts
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.tables import table_column_config


def render_trace_summary(trace: ProvenanceTrace) -> None:
    """Render a compact provenance trace summary."""

    with st.container(border=True):
        badges = [badge_markdown(trace.completeness.overall.value)]
        if trace.synthetic:
            badges.append(badge_markdown("synthetic"))
        st.markdown(" ".join(badges))
        st.markdown(
            f"**Nodes:** {len(trace.nodes)} · **Edges:** {len(trace.edges)} · "
            f"**Root:** `{trace.root_node_id}`"
        )
        st.caption(
            f"Trace `{trace.trace_id}` · Source fingerprint: "
            f"`{fingerprint_summary(trace.source_fingerprint)}`"
        )
        with st.expander("Advanced: full identifiers"):
            st.code(
                f"trace_id: {trace.trace_id}\n"
                f"root_node_id: {trace.root_node_id}\n"
                f"source_fingerprint: {trace.source_fingerprint or 'Unavailable'}",
                language=None,
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
        st.dataframe(
            rows,
            width="stretch",
            hide_index=True,
            column_config=table_column_config(rows),
        )
    else:
        st.info("No lineage edges are available for this trace.")


def render_trace_nodes(trace: ProvenanceTrace) -> None:
    """Render grouped trace nodes."""

    counts = node_type_counts(trace)
    st.caption(
        "Node types: "
        + " · ".join(f"{node_type} ({counts[node_type]})" for node_type in sorted(counts))
    )
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
            st.dataframe(
                rows,
                width="stretch",
                hide_index=True,
                column_config=table_column_config(rows, hide_machine_ids=False),
            )


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
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config=table_column_config(rows),
    )
