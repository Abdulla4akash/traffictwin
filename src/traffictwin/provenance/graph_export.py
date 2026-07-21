"""Deterministic, bounded, path-safe exports for provenance trace DAGs."""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from collections.abc import Iterable
from enum import StrEnum
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.metrics.results import JsonValue
from traffictwin.provenance.models import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    ProvenanceStatus,
    ProvenanceTrace,
    ReferenceConfidence,
    SourceReference,
)

GRAPH_EXPORT_SCHEMA_VERSION = "1.0"
GRAPH_EXPORT_CAPABILITY_ID = "PRO-02"
DEFAULT_GRAPH_NODE_LIMIT = 120
DEFAULT_GRAPH_EDGE_LIMIT = 240
MAX_GRAPH_NODE_LIMIT = 500
MAX_GRAPH_EDGE_LIMIT = 2_000
ABSOLUTE_PATH_REDACTION = "[redacted absolute path]"

_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)")
_FILE_URI = re.compile(r"(?i)file://[^\s\"'<>]+")
_HOME_PATH = re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+")
_POSIX_PATH = re.compile(r"(?<![/\w])/(?!/)[^\s\"'<>]+")
_XML_INVALID = re.compile("[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


class GraphRedactionMode(StrEnum):
    """Supported disclosure profiles for exported graph content."""

    SAFE = "safe"
    STRUCTURE_ONLY = "structure_only"


class GraphExportError(ValueError):
    """Raised when a bounded graph export cannot be built safely."""


class GraphExportNode(BaseModel):
    """One path-safe node in a bounded export view."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    node_type: ProvenanceNodeType
    label: str = Field(min_length=1)
    description: str | None = None
    status: ProvenanceStatus
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    synthetic: bool = False
    source_reference: SourceReference | None = None
    is_root: bool = False


class GraphExportEdge(BaseModel):
    """One stable directed edge in a bounded export view."""

    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    relation: ProvenanceRelation
    description: str | None = None
    confidence: ReferenceConfidence


class ProvenanceGraphView(BaseModel):
    """Bounded, sanitised projection of an existing provenance trace."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = GRAPH_EXPORT_SCHEMA_VERSION
    capability_id: str = GRAPH_EXPORT_CAPABILITY_ID
    graph_id: str
    root_node_id: str
    redaction_mode: GraphRedactionMode
    traversal_policy: str = "root-centred undirected breadth-first, then lexical disconnected nodes"
    node_limit: int = Field(ge=1, le=MAX_GRAPH_NODE_LIMIT)
    edge_limit: int = Field(ge=0, le=MAX_GRAPH_EDGE_LIMIT)
    total_node_count: int = Field(ge=1)
    total_edge_count: int = Field(ge=0)
    omitted_node_count: int = Field(ge=0)
    omitted_edge_count: int = Field(ge=0)
    redaction_count: int = Field(ge=0)
    truncated: bool
    nodes: list[GraphExportNode]
    edges: list[GraphExportEdge]
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_view(self) -> ProvenanceGraphView:
        """Validate counts, root presence, unique IDs, and retained endpoints."""

        node_ids = [node.node_id for node in self.nodes]
        edge_ids = [edge.edge_id for edge in self.edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("graph export node IDs must be unique")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("graph export edge IDs must be unique")
        if self.root_node_id not in set(node_ids):
            raise ValueError("graph export root must be retained")
        for edge in self.edges:
            if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
                raise ValueError("graph export edge endpoint is not retained")
        if self.total_node_count != len(self.nodes) + self.omitted_node_count:
            raise ValueError("graph export node counts do not reconcile")
        if self.total_edge_count != len(self.edges) + self.omitted_edge_count:
            raise ValueError("graph export edge counts do not reconcile")
        if self.truncated != bool(self.omitted_node_count or self.omitted_edge_count):
            raise ValueError("graph export truncated flag does not match omitted counts")
        return self

    def canonical_json(self) -> str:
        """Return a deterministic representation of this exact bounded view."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Fingerprint this exact bounded and redacted view."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ProvenanceGraphExportContract(BaseModel):
    """Published PRO-02 v1.0 export, stability, redaction, and bounding contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = GRAPH_EXPORT_SCHEMA_VERSION
    capability_id: str = GRAPH_EXPORT_CAPABILITY_ID
    formats: list[str]
    default_node_limit: int
    default_edge_limit: int
    maximum_node_limit: int
    maximum_edge_limit: int
    traversal_policy: str
    node_id_policy: str
    edge_id_policy: str
    redaction_modes: dict[str, str]
    default_redaction_mode: GraphRedactionMode
    path_safety_rules: list[str]
    deterministic_output_rules: list[str]
    limitations: list[str]


def provenance_graph_export_contract() -> ProvenanceGraphExportContract:
    """Return the immutable PRO-02 graph export contract."""

    return ProvenanceGraphExportContract(
        formats=["dot", "graphml"],
        default_node_limit=DEFAULT_GRAPH_NODE_LIMIT,
        default_edge_limit=DEFAULT_GRAPH_EDGE_LIMIT,
        maximum_node_limit=MAX_GRAPH_NODE_LIMIT,
        maximum_edge_limit=MAX_GRAPH_EDGE_LIMIT,
        traversal_policy=(
            "root-centred undirected breadth-first, ordered by stable edge fields, followed by "
            "lexically ordered disconnected nodes when capacity remains"
        ),
        node_id_policy=(
            "existing stable trace node IDs are retained unless they contain a local absolute "
            "path; unsafe IDs receive deterministic redacted aliases"
        ),
        edge_id_policy=(
            "edge:<first 20 hexadecimal SHA-256 characters of the sanitised typed edge>; "
            "deterministic numeric suffixes distinguish otherwise identical retained relations"
        ),
        redaction_modes={
            GraphRedactionMode.SAFE.value: (
                "retain typed descriptions, attributes, and bundle-relative source references "
                "after recursive local-path redaction"
            ),
            GraphRedactionMode.STRUCTURE_ONLY.value: (
                "retain IDs, types, labels, statuses, synthetic flags, and relations only"
            ),
        },
        default_redaction_mode=GraphRedactionMode.SAFE,
        path_safety_rules=[
            "POSIX, Windows, home-relative, and file-URI local paths are redacted from all text.",
            "Bundle-relative source references may remain in safe exports.",
            "Invalid XML control characters are replaced before DOT or GraphML serialization.",
            "No exporter opens a node path, follows a link, or reads source evidence.",
        ],
        deterministic_output_rules=[
            "volatile trace and node timestamps are not exported",
            "nodes and edges use stable deterministic ordering",
            "DOT escaping and GraphML key order are fixed",
            "graph identity is derived from the complete sanitised graph, not the selected limits",
        ],
        limitations=[
            "The graph records calculation lineage, not real-world causality.",
            "A bounded view may omit nodes or edges and reports exact omitted counts.",
            "Safe mode does not anonymise ordinary domain identifiers or canonical scalar values.",
            "Graph layout is renderer-dependent and is not part of the deterministic artifact.",
        ],
    )


def build_provenance_graph_view(
    trace: ProvenanceTrace,
    *,
    node_limit: int = DEFAULT_GRAPH_NODE_LIMIT,
    edge_limit: int = DEFAULT_GRAPH_EDGE_LIMIT,
    redaction_mode: GraphRedactionMode | str = GraphRedactionMode.SAFE,
) -> ProvenanceGraphView:
    """Build a deterministic bounded projection without recomputing provenance."""

    mode = _redaction_mode(redaction_mode)
    _validate_limits(node_limit, edge_limit)
    original_nodes = {node.node_id: node for node in trace.nodes}
    if len(original_nodes) != len(trace.nodes):
        raise GraphExportError("provenance trace contains duplicate node IDs")
    if trace.root_node_id not in original_nodes:
        raise GraphExportError("provenance trace root is missing")

    sanitizer = _Sanitizer(mode)
    node_id_map = _safe_node_id_map(trace.nodes, sanitizer)
    safe_nodes = {
        node.node_id: _safe_node(
            node,
            safe_id=node_id_map[node.node_id],
            root=node.node_id == trace.root_node_id,
            sanitizer=sanitizer,
        )
        for node in trace.nodes
    }
    ordered_edges = sorted(trace.edges, key=_original_edge_key)
    safe_edges = [
        _safe_edge(edge, node_id_map=node_id_map, sanitizer=sanitizer) for edge in ordered_edges
    ]
    safe_edges = _unique_edge_ids(safe_edges)
    graph_id = _stable_graph_id(
        root_node_id=node_id_map[trace.root_node_id],
        nodes=safe_nodes.values(),
        edges=safe_edges,
        mode=mode,
    )

    selected_original_ids = _bounded_node_ids(trace, node_limit)
    selected_set = set(selected_original_ids)
    selected_nodes = [safe_nodes[node_id] for node_id in selected_original_ids]
    selected_edges = [
        safe_edge
        for original_edge, safe_edge in zip(ordered_edges, safe_edges, strict=True)
        if original_edge.source_node_id in selected_set
        and original_edge.target_node_id in selected_set
    ]
    selected_edges.sort(key=_export_edge_key)
    selected_edges = selected_edges[:edge_limit]
    omitted_nodes = len(trace.nodes) - len(selected_nodes)
    omitted_edges = len(trace.edges) - len(selected_edges)

    return ProvenanceGraphView(
        graph_id=graph_id,
        root_node_id=node_id_map[trace.root_node_id],
        redaction_mode=mode,
        node_limit=node_limit,
        edge_limit=edge_limit,
        total_node_count=len(trace.nodes),
        total_edge_count=len(trace.edges),
        omitted_node_count=omitted_nodes,
        omitted_edge_count=omitted_edges,
        redaction_count=sanitizer.redaction_count,
        truncated=bool(omitted_nodes or omitted_edges),
        nodes=selected_nodes,
        edges=selected_edges,
        limitations=[
            "This bounded graph is a projection of an existing ProvenanceTrace; it does not "
            "recalculate metrics, findings, or lineage.",
            "The graph records deterministic lineage and does not establish causality.",
            "Safe mode retains ordinary identifiers and scalar attributes; use structure_only "
            "when those details should not be disclosed.",
        ],
    )


def provenance_graph_to_dot(view: ProvenanceGraphView) -> str:
    """Serialize a bounded view as deterministic escaped Graphviz DOT."""

    lines = [
        "digraph TrafficTwinProvenance {",
        f'  graph [id="{_dot_escape(view.graph_id)}", rankdir="LR", labelloc="t", '
        f'label="TrafficTwin provenance ({len(view.nodes)} nodes, {len(view.edges)} edges)"];',
        '  node [shape="box", style="rounded,filled", fontname="Helvetica"];',
        '  edge [fontname="Helvetica", fontsize="9"];',
    ]
    for node in view.nodes:
        label = f"{node.label}\n[{node.node_type.value}]"
        lines.append(
            f'  "{_dot_escape(node.node_id)}" '
            f'[label="{_dot_escape(label)}", fillcolor="{_status_colour(node.status)}", '
            f'color="{_node_border(node)}", penwidth="{2 if node.is_root else 1}"];'
        )
    for edge in view.edges:
        lines.append(
            f'  "{_dot_escape(edge.source_node_id)}" -> '
            f'"{_dot_escape(edge.target_node_id)}" '
            f'[id="{_dot_escape(edge.edge_id)}", label="{_dot_escape(edge.relation.value)}", '
            f'style="{_edge_style(edge.confidence)}"];'
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def provenance_graph_to_graphml(view: ProvenanceGraphView) -> str:
    """Serialize a bounded view as deterministic GraphML 1.0 XML."""

    namespace = "http://graphml.graphdrawing.org/xmlns"
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    ElementTree.register_namespace("", namespace)
    ElementTree.register_namespace("xsi", xsi)
    root = ElementTree.Element(
        f"{{{namespace}}}graphml",
        {
            f"{{{xsi}}}schemaLocation": (
                "http://graphml.graphdrawing.org/xmlns "
                "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
            )
        },
    )
    key_specs = [
        ("g_schema", "graph", "schema_version", "string"),
        ("g_capability", "graph", "capability_id", "string"),
        ("g_root", "graph", "root_node_id", "string"),
        ("g_redaction", "graph", "redaction_mode", "string"),
        ("g_total_nodes", "graph", "total_node_count", "int"),
        ("g_total_edges", "graph", "total_edge_count", "int"),
        ("g_omitted_nodes", "graph", "omitted_node_count", "int"),
        ("g_omitted_edges", "graph", "omitted_edge_count", "int"),
        ("g_redactions", "graph", "redaction_count", "int"),
        ("n_type", "node", "node_type", "string"),
        ("n_label", "node", "label", "string"),
        ("n_description", "node", "description", "string"),
        ("n_status", "node", "status", "string"),
        ("n_synthetic", "node", "synthetic", "boolean"),
        ("n_root", "node", "is_root", "boolean"),
        ("n_attributes", "node", "attributes_json", "string"),
        ("n_source", "node", "source_reference_json", "string"),
        ("e_relation", "edge", "relation", "string"),
        ("e_description", "edge", "description", "string"),
        ("e_confidence", "edge", "confidence", "string"),
    ]
    for key_id, target, name, value_type in key_specs:
        ElementTree.SubElement(
            root,
            f"{{{namespace}}}key",
            {
                "id": key_id,
                "for": target,
                "attr.name": name,
                "attr.type": value_type,
            },
        )
    graph = ElementTree.SubElement(
        root,
        f"{{{namespace}}}graph",
        {"id": view.graph_id, "edgedefault": "directed"},
    )
    graph_data = [
        ("g_schema", view.schema_version),
        ("g_capability", view.capability_id),
        ("g_root", view.root_node_id),
        ("g_redaction", view.redaction_mode.value),
        ("g_total_nodes", str(view.total_node_count)),
        ("g_total_edges", str(view.total_edge_count)),
        ("g_omitted_nodes", str(view.omitted_node_count)),
        ("g_omitted_edges", str(view.omitted_edge_count)),
        ("g_redactions", str(view.redaction_count)),
    ]
    for key, value in graph_data:
        _xml_data(graph, namespace, key, value)
    for node in view.nodes:
        element = ElementTree.SubElement(
            graph,
            f"{{{namespace}}}node",
            {"id": node.node_id},
        )
        _xml_data(element, namespace, "n_type", node.node_type.value)
        _xml_data(element, namespace, "n_label", node.label)
        _xml_data(element, namespace, "n_description", node.description or "")
        _xml_data(element, namespace, "n_status", node.status.value)
        _xml_data(element, namespace, "n_synthetic", str(node.synthetic).lower())
        _xml_data(element, namespace, "n_root", str(node.is_root).lower())
        _xml_data(
            element,
            namespace,
            "n_attributes",
            json.dumps(node.attributes, sort_keys=True, separators=(",", ":"), allow_nan=False),
        )
        _xml_data(
            element,
            namespace,
            "n_source",
            (
                json.dumps(
                    node.source_reference.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                if node.source_reference is not None
                else ""
            ),
        )
    for edge in view.edges:
        element = ElementTree.SubElement(
            graph,
            f"{{{namespace}}}edge",
            {
                "id": edge.edge_id,
                "source": edge.source_node_id,
                "target": edge.target_node_id,
            },
        )
        _xml_data(element, namespace, "e_relation", edge.relation.value)
        _xml_data(element, namespace, "e_description", edge.description or "")
        _xml_data(element, namespace, "e_confidence", edge.confidence.value)
    ElementTree.indent(root, space="  ")
    payload = ElementTree.tostring(root, encoding="unicode", xml_declaration=True)
    return payload + ("" if payload.endswith("\n") else "\n")


class _Sanitizer:
    def __init__(self, mode: GraphRedactionMode) -> None:
        self.mode = mode
        self.redaction_count = 0

    def text(self, value: str) -> str:
        result = _XML_INVALID.sub("�", value)
        for pattern in (_FILE_URI, _WINDOWS_PATH, _HOME_PATH, _POSIX_PATH):
            result, count = pattern.subn(ABSOLUTE_PATH_REDACTION, result)
            self.redaction_count += count
        if result != value and not any(
            pattern.search(value) for pattern in (_FILE_URI, _WINDOWS_PATH, _HOME_PATH, _POSIX_PATH)
        ):
            self.redaction_count += 1
        return result

    def value(self, value: JsonValue) -> JsonValue:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.value(item) for item in value]
        if isinstance(value, dict):
            return {self.text(str(key)): self.value(item) for key, item in sorted(value.items())}
        return value

    def omit(self, value: object) -> None:
        if value not in (None, {}, [], ""):
            self.redaction_count += 1


def _safe_node_id_map(
    nodes: list[ProvenanceNode],
    sanitizer: _Sanitizer,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    redacted_index = 0
    for node in sorted(nodes, key=lambda item: item.node_id):
        safe = sanitizer.text(node.node_id)
        if safe != node.node_id:
            redacted_index += 1
            safe = f"provenance-redacted-node-{redacted_index:04d}"
        candidate = safe
        suffix = 1
        while candidate in used:
            suffix += 1
            candidate = f"{safe}-{suffix}"
        mapping[node.node_id] = candidate
        used.add(candidate)
    return mapping


def _safe_node(
    node: ProvenanceNode,
    *,
    safe_id: str,
    root: bool,
    sanitizer: _Sanitizer,
) -> GraphExportNode:
    label = sanitizer.text(node.label)
    if not label:
        label = "[unlabelled]"
        sanitizer.redaction_count += 1
    if sanitizer.mode is GraphRedactionMode.STRUCTURE_ONLY:
        sanitizer.omit(node.description)
        sanitizer.omit(node.attributes)
        sanitizer.omit(node.source_reference)
        description = None
        attributes: dict[str, JsonValue] = {}
        source_reference = None
    else:
        description = sanitizer.text(node.description) if node.description is not None else None
        attributes = sanitizer.value(node.attributes)
        source_reference = _safe_source_reference(node.source_reference, sanitizer)
    return GraphExportNode(
        node_id=safe_id,
        node_type=node.node_type,
        label=label,
        description=description,
        status=node.status,
        attributes=attributes,
        synthetic=node.synthetic,
        source_reference=source_reference,
        is_root=root,
    )


def _safe_source_reference(
    source: SourceReference | None,
    sanitizer: _Sanitizer,
) -> SourceReference | None:
    if source is None:
        return None
    return SourceReference(
        bundle_reference=(
            sanitizer.text(source.bundle_reference) if source.bundle_reference is not None else None
        ),
        file=sanitizer.text(source.file) if source.file is not None else None,
        row=source.row,
        field=sanitizer.text(source.field) if source.field is not None else None,
    )


def _safe_edge(
    edge: ProvenanceEdge,
    *,
    node_id_map: dict[str, str],
    sanitizer: _Sanitizer,
) -> GraphExportEdge:
    if edge.source_node_id not in node_id_map or edge.target_node_id not in node_id_map:
        raise GraphExportError("provenance edge endpoint is missing")
    description: str | None
    if sanitizer.mode is GraphRedactionMode.STRUCTURE_ONLY:
        sanitizer.omit(edge.description)
        description = None
    else:
        description = sanitizer.text(edge.description) if edge.description is not None else None
    basis = json.dumps(
        {
            "source_node_id": node_id_map[edge.source_node_id],
            "target_node_id": node_id_map[edge.target_node_id],
            "relation": edge.relation.value,
            "description": description,
            "confidence": edge.confidence.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    edge_id = f"edge:{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:20]}"
    return GraphExportEdge(
        edge_id=edge_id,
        source_node_id=node_id_map[edge.source_node_id],
        target_node_id=node_id_map[edge.target_node_id],
        relation=edge.relation.value,
        description=description,
        confidence=edge.confidence,
    )


def _bounded_node_ids(trace: ProvenanceTrace, limit: int) -> list[str]:
    node_ids = {node.node_id for node in trace.nodes}
    incident: dict[str, list[tuple[str, str, str, str, str]]] = {
        node_id: [] for node_id in node_ids
    }
    for edge in trace.edges:
        if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
            raise GraphExportError("provenance edge endpoint is missing")
        incident[edge.source_node_id].append(
            (
                "out",
                edge.relation.value,
                edge.target_node_id,
                edge.description or "",
                edge.target_node_id,
            )
        )
        incident[edge.target_node_id].append(
            (
                "in",
                edge.relation.value,
                edge.source_node_id,
                edge.description or "",
                edge.source_node_id,
            )
        )
    selected: list[str] = []
    seen = {trace.root_node_id}
    queue: deque[str] = deque([trace.root_node_id])
    while queue and len(selected) < limit:
        current = queue.popleft()
        selected.append(current)
        for _, _, _, _, neighbour in sorted(incident[current]):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    if len(selected) < limit:
        selected.extend(sorted(node_ids - set(selected))[: limit - len(selected)])
    return selected


def _stable_graph_id(
    *,
    root_node_id: str,
    nodes: Iterable[GraphExportNode],
    edges: list[GraphExportEdge],
    mode: GraphRedactionMode,
) -> str:
    node_list = sorted(nodes, key=lambda node: node.node_id)
    payload = {
        "schema_version": GRAPH_EXPORT_SCHEMA_VERSION,
        "root_node_id": root_node_id,
        "redaction_mode": mode.value,
        "nodes": [node.model_dump(mode="json") for node in node_list],
        "edges": [edge.model_dump(mode="json") for edge in sorted(edges, key=_export_edge_key)],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"provenance-graph:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]}"


def _export_edge_key(edge: GraphExportEdge) -> tuple[str, str, str, str]:
    return (edge.source_node_id, edge.relation.value, edge.target_node_id, edge.edge_id)


def _original_edge_key(edge: ProvenanceEdge) -> tuple[str, str, str, str, str]:
    return (
        edge.source_node_id,
        edge.relation.value,
        edge.target_node_id,
        edge.description or "",
        edge.confidence.value,
    )


def _unique_edge_ids(edges: list[GraphExportEdge]) -> list[GraphExportEdge]:
    counts: dict[str, int] = {}
    unique: list[GraphExportEdge] = []
    for edge in edges:
        count = counts.get(edge.edge_id, 0) + 1
        counts[edge.edge_id] = count
        unique.append(
            edge if count == 1 else edge.model_copy(update={"edge_id": f"{edge.edge_id}-{count}"})
        )
    return unique


def _redaction_mode(value: GraphRedactionMode | str) -> GraphRedactionMode:
    try:
        return GraphRedactionMode(value)
    except ValueError as exc:
        choices = ", ".join(mode.value for mode in GraphRedactionMode)
        raise GraphExportError(f"redaction_mode must be one of: {choices}") from exc


def _validate_limits(node_limit: int, edge_limit: int) -> None:
    if node_limit < 1 or node_limit > MAX_GRAPH_NODE_LIMIT:
        raise GraphExportError(f"node_limit must be between 1 and {MAX_GRAPH_NODE_LIMIT}")
    if edge_limit < 0 or edge_limit > MAX_GRAPH_EDGE_LIMIT:
        raise GraphExportError(f"edge_limit must be between 0 and {MAX_GRAPH_EDGE_LIMIT}")


def _dot_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")


def _status_colour(status: ProvenanceStatus) -> str:
    return {
        ProvenanceStatus.AVAILABLE: "#DCFCE7",
        ProvenanceStatus.PARTIAL: "#FEF3C7",
        ProvenanceStatus.UNAVAILABLE: "#E5E7EB",
        ProvenanceStatus.INVALID: "#FEE2E2",
    }[status]


def _node_border(node: GraphExportNode) -> str:
    return "#2563EB" if node.is_root else "#475569"


def _edge_style(confidence: ReferenceConfidence) -> str:
    return "solid" if confidence is ReferenceConfidence.EXACT else "dashed"


def _xml_data(parent: ElementTree.Element, namespace: str, key: str, value: str) -> None:
    element = ElementTree.SubElement(parent, f"{{{namespace}}}data", {"key": key})
    element.text = value
