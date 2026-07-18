"""Small internal provenance graph helper."""

from __future__ import annotations

from datetime import datetime

from traffictwin.provenance.models import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceRelation,
    ProvenanceTrace,
    ReferenceConfidence,
    TraceCompletenessSummary,
    stable_trace_id,
)


class ProvenanceGraphError(ValueError):
    """Raised when a trace graph is internally inconsistent."""


class TraceGraph:
    """Deterministic in-memory graph builder."""

    def __init__(self) -> None:
        self._nodes: dict[str, ProvenanceNode] = {}
        self._edges: list[ProvenanceEdge] = []

    def add_node(self, node: ProvenanceNode) -> ProvenanceNode:
        """Add or return a node by stable id."""

        existing = self._nodes.get(node.node_id)
        if existing is not None:
            if existing != node:
                msg = f"duplicate provenance node id with different payload: {node.node_id}"
                raise ProvenanceGraphError(msg)
            return existing
        self._nodes[node.node_id] = node
        return node

    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        relation: ProvenanceRelation,
        *,
        description: str | None = None,
        confidence: ReferenceConfidence = ReferenceConfidence.EXACT,
    ) -> ProvenanceEdge:
        """Add an edge after endpoint validation."""

        if source_node_id not in self._nodes:
            msg = f"edge source node is missing: {source_node_id}"
            raise ProvenanceGraphError(msg)
        if target_node_id not in self._nodes:
            msg = f"edge target node is missing: {target_node_id}"
            raise ProvenanceGraphError(msg)
        edge = ProvenanceEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation=relation,
            description=description,
            confidence=confidence,
        )
        if edge not in self._edges:
            self._edges.append(edge)
        return edge

    def has_node(self, node_id: str) -> bool:
        """Return whether a node has been added."""

        return node_id in self._nodes

    def to_trace(
        self,
        *,
        root_node_id: str,
        generated_at: datetime,
        source_fingerprint: str | None,
        synthetic: bool,
        completeness: TraceCompletenessSummary,
        warnings: list[str] | None = None,
    ) -> ProvenanceTrace:
        """Build a validated trace with stable ordering."""

        if root_node_id not in self._nodes:
            msg = f"root node is missing: {root_node_id}"
            raise ProvenanceGraphError(msg)
        nodes = [self._nodes[node_id] for node_id in sorted(self._nodes)]
        edges = sorted(
            self._edges,
            key=lambda edge: (
                edge.source_node_id,
                edge.relation.value,
                edge.target_node_id,
                edge.description or "",
            ),
        )
        return ProvenanceTrace(
            trace_id=stable_trace_id(
                root_node_id=root_node_id,
                source_fingerprint=source_fingerprint,
                generated_at=generated_at,
            ),
            root_node_id=root_node_id,
            nodes=nodes,
            edges=edges,
            warnings=warnings or [],
            generated_at=generated_at,
            source_fingerprint=source_fingerprint,
            synthetic=synthetic,
            completeness=completeness,
        )
