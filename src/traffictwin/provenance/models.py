"""Versioned provenance trace models."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.metrics.results import JsonValue

PROVENANCE_SCHEMA_VERSION = "1.0"


class ProvenanceNodeType(StrEnum):
    """Supported provenance node types."""

    DIAGNOSTIC_REPORT = "diagnostic_report"
    RULE_DEFINITION = "rule_definition"
    RULE_RESULT = "rule_result"
    FINDING = "finding"
    EVIDENCE_KEY = "evidence_key"
    METRIC_RESULT = "metric_result"
    METRIC_DEFINITION = "metric_definition"
    CANONICAL_TABLE = "canonical_table"
    CANONICAL_RECORD = "canonical_record"
    VALIDATION_FINDING = "validation_finding"
    SOURCE_FILE = "source_file"
    SOURCE_ROW = "source_row"
    MANIFEST = "manifest"
    RUN = "run"
    EXPERIMENT = "experiment"
    SCENARIO_SEED = "scenario_seed"
    ENVIRONMENT = "environment"
    CHECKPOINT = "checkpoint"
    BUNDLE = "bundle"
    FINGERPRINT = "fingerprint"
    EVIDENCE_PACK = "evidence_pack"
    UNAVAILABLE_REFERENCE = "unavailable_reference"


class ProvenanceStatus(StrEnum):
    """Node status values."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class ProvenanceRelation(StrEnum):
    """Supported provenance edge relations."""

    CONTAINS = "contains"
    GENERATED_FROM = "generated_from"
    CITES = "cites"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    COMPUTED_FROM = "computed_from"
    DEFINED_BY = "defined_by"
    REQUIRES = "requires"
    CANONICALISED_FROM = "canonicalised_from"
    VALIDATED_BY = "validated_by"
    LOCATED_IN = "located_in"
    BELONGS_TO = "belongs_to"
    CONFIGURED_BY = "configured_by"
    EXECUTED_WITH = "executed_with"
    IDENTIFIED_BY = "identified_by"
    UNAVAILABLE_BECAUSE = "unavailable_because"


class ReferenceConfidence(StrEnum):
    """How directly an edge can be established."""

    EXACT = "exact"
    DERIVED = "derived"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class TraceCompleteness(StrEnum):
    """Categorical completeness labels."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class SourceReference(BaseModel):
    """Bundle-relative source reference."""

    model_config = ConfigDict(extra="forbid")

    bundle_reference: str | None = None
    file: str | None = None
    row: int | None = Field(default=None, ge=1)
    field: str | None = None


class ProvenanceNode(BaseModel):
    """One typed provenance trace node."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    node_type: ProvenanceNodeType
    label: str = Field(min_length=1)
    description: str | None = None
    status: ProvenanceStatus = ProvenanceStatus.AVAILABLE
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    synthetic: bool = False
    source_reference: SourceReference | None = None
    created_at: datetime | None = None


class ProvenanceEdge(BaseModel):
    """One typed relation between provenance nodes."""

    model_config = ConfigDict(extra="forbid")

    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    relation: ProvenanceRelation
    description: str | None = None
    confidence: ReferenceConfidence = ReferenceConfidence.EXACT


class TraceCompletenessSummary(BaseModel):
    """Overall and category-level trace completeness."""

    model_config = ConfigDict(extra="forbid")

    overall: TraceCompleteness
    categories: dict[str, TraceCompleteness] = Field(default_factory=dict)
    reasons: dict[str, list[str]] = Field(default_factory=dict)


class SourceRow(BaseModel):
    """One raw CSV row in a source preview."""

    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=1)
    values: dict[str, str | None]


class SourceRowPreview(BaseModel):
    """Read-only source-row preview."""

    model_config = ConfigDict(extra="forbid")

    file: str
    row_number: int = Field(ge=1)
    status: ProvenanceStatus
    headers: list[str] = Field(default_factory=list)
    raw_values: dict[str, str | None] = Field(default_factory=dict)
    surrounding_rows: list[SourceRow] = Field(default_factory=list)
    canonical_record_type: str | None = None
    canonical_values: dict[str, JsonValue] = Field(default_factory=dict)
    conversions: dict[str, JsonValue] = Field(default_factory=dict)
    validation_findings: list[dict[str, JsonValue]] = Field(default_factory=list)
    inclusion_status: str = "unavailable"
    warnings: list[str] = Field(default_factory=list)


class ProvenanceTrace(BaseModel):
    """Versioned trace report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = PROVENANCE_SCHEMA_VERSION
    trace_id: str
    root_node_id: str
    nodes: list[ProvenanceNode]
    edges: list[ProvenanceEdge]
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
    source_fingerprint: str | None = None
    synthetic: bool = False
    completeness: TraceCompletenessSummary

    @model_validator(mode="after")
    def validate_edges(self) -> Self:
        """Ensure root and edge endpoints reference existing nodes."""

        node_ids = {node.node_id for node in self.nodes}
        if self.root_node_id not in node_ids:
            raise ValueError(f"root node is missing: {self.root_node_id}")
        for edge in self.edges:
            if edge.source_node_id not in node_ids:
                raise ValueError(f"edge source node is missing: {edge.source_node_id}")
            if edge.target_node_id not in node_ids:
                raise ValueError(f"edge target node is missing: {edge.target_node_id}")
        return self

    def by_id(self) -> dict[str, ProvenanceNode]:
        """Return nodes keyed by id."""

        return {node.node_id: node for node in self.nodes}

    def to_json(self) -> str:
        """Return pretty JSON."""

        return self.model_dump_json(indent=2)

    def canonical_json(self) -> str:
        """Return canonical JSON excluding volatile generated timestamps."""

        data = self.model_dump(mode="json")
        data["generated_at"] = "<normalised>"
        for node in data["nodes"]:
            if node.get("created_at") is not None:
                node["created_at"] = "<normalised>"
        return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Return a deterministic trace fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def stable_trace_id(
    *, root_node_id: str, source_fingerprint: str | None, generated_at: datetime
) -> str:
    """Build a deterministic trace id for fixed input and clock."""

    basis = f"{root_node_id}|{source_fingerprint or 'no-fingerprint'}|{generated_at.isoformat()}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
    return f"provenance-{digest}"
