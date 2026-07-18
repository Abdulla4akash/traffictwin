"""Deterministic Markdown export for provenance traces."""

from __future__ import annotations

from traffictwin.provenance.models import (
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    ProvenanceTrace,
)


def trace_to_markdown(trace: ProvenanceTrace) -> str:
    """Render a compact Markdown trace report."""

    nodes = trace.by_id()
    root = nodes[trace.root_node_id]
    lines = [
        "# TrafficTwin Provenance Trace",
        "",
        "## Trace Summary",
        "",
        f"- Trace ID: `{trace.trace_id}`",
        f"- Root: `{root.node_id}` ({root.node_type.value})",
        f"- Completeness: `{trace.completeness.overall.value}`",
        f"- Synthetic: `{str(trace.synthetic).lower()}`",
        f"- Source fingerprint: `{trace.source_fingerprint or 'unavailable'}`",
        "",
        "Provenance shows how TrafficTwin derived a result from available records and "
        "configured rules. It does not establish real-world causality.",
        "",
    ]
    lines.extend(_section("Run Context", _node_lines(trace, ProvenanceNodeType.RUN)))
    lines.extend(_section("Root Result", [_format_node(root)]))
    lines.extend(_section("Lineage", _edge_lines(trace)))
    lines.extend(
        _section("Metric Definition", _node_lines(trace, ProvenanceNodeType.METRIC_DEFINITION))
    )
    lines.extend(_section("Evidence Used", _node_lines(trace, ProvenanceNodeType.EVIDENCE_KEY)))
    lines.extend(_section("Canonical Records", _canonical_summary_lines(trace)))
    lines.extend(
        _section("Validation Findings", _node_lines(trace, ProvenanceNodeType.VALIDATION_FINDING))
    )
    lines.extend(_section("Source Rows", _node_lines(trace, ProvenanceNodeType.SOURCE_ROW)))
    missing = _node_lines(trace, ProvenanceNodeType.UNAVAILABLE_REFERENCE)
    lines.extend(
        _section("Missing Links", missing if missing else ["No unavailable references recorded."])
    )
    limitation_lines = list(trace.warnings)
    for category, reasons in trace.completeness.reasons.items():
        for reason in reasons:
            limitation_lines.append(f"{category}: {reason}")
    lines.extend(
        _section(
            "Limitations",
            limitation_lines if limitation_lines else ["No additional trace limitations recorded."],
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def _section(title: str, rows: list[str]) -> list[str]:
    return [f"## {title}", "", *[f"- {row}" for row in rows], ""]


def _node_lines(trace: ProvenanceTrace, node_type: ProvenanceNodeType) -> list[str]:
    return [_format_node(node) for node in trace.nodes if node.node_type is node_type]


def _format_node(node: ProvenanceNode) -> str:
    return f"`{node.node_id}` - {node.label} [{node.status.value}]"


def _edge_lines(trace: ProvenanceTrace) -> list[str]:
    nodes = trace.by_id()
    rows: list[str] = []
    for edge in trace.edges:
        source = nodes[edge.source_node_id].label
        target = nodes[edge.target_node_id].label
        relation = _relation_label(edge.relation)
        rows.append(f"{source} {relation} {target} (`{edge.confidence.value}`)")
    return rows


def _relation_label(relation: ProvenanceRelation) -> str:
    return relation.value.replace("_", " ")


def _canonical_summary_lines(trace: ProvenanceTrace) -> list[str]:
    rows: list[str] = []
    for node in trace.nodes:
        if node.node_type is ProvenanceNodeType.CANONICAL_TABLE:
            count = node.attributes.get("record_count", "unknown")
            rows.append(f"`{node.node_id}` - {count} eligible records")
    return rows or ["No canonical table lineage recorded."]
