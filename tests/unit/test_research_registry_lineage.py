"""Strong lineage graph tests."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from traffictwin.research_registry.lineage import (
    LineageEdge,
    LineageGraph,
    RelationshipType,
    StudyVersionIdentity,
)


def _edge(
    source_study: str = "E2b",
    source_version: str = "1.0",
    target_study: str = "E2c",
    target_version: str = "1.0",
    relationship: RelationshipType = RelationshipType.EXTENDS,
    declared_source: str = "docs/src.md",
    provenance_identity: str = "a" * 40,
    rationale: str = "Valid rationale with sufficient length for testing lineage edge.",
) -> LineageEdge:
    return LineageEdge.build(
        source_study=source_study,
        source_version=source_version,
        target_study=target_study,
        target_version=target_version,
        relationship=relationship,
        declared_source=declared_source,
        provenance_identity=provenance_identity,
        rationale=rationale,
    )


def _node(study: str, version: str) -> StudyVersionIdentity:
    return StudyVersionIdentity(study=study, version=version)


# ---------------------------------------------------------------------------
# Valid cases
# ---------------------------------------------------------------------------


def test_relationship_enum_has_required_members() -> None:
    assert RelationshipType.SUPERSEDES == "SUPERSEDES"
    assert RelationshipType.EXTENDS == "EXTENDS"
    assert RelationshipType.CORRECTS == "CORRECTS"
    assert RelationshipType.ROBUSTNESS_CHECK == "ROBUSTNESS_CHECK"
    assert RelationshipType.REPLICATION == "REPLICATION"
    assert RelationshipType.CONSTRUCT_VALIDITY == "CONSTRUCT_VALIDITY"
    assert RelationshipType.PRODUCT_ADMISSION == "PRODUCT_ADMISSION"


def test_valid_edge_fingerprint_deterministic() -> None:
    e1 = _edge()
    e2 = _edge()
    assert e1.fingerprint == e2.fingerprint
    assert len(e1.fingerprint) == 64
    # Computed equals stored
    assert e1.computed_fingerprint() == e1.fingerprint


def test_valid_graph_sorted_and_frozen() -> None:
    n1 = _node("E2b", "1.0")
    n2 = _node("E2c", "1.0")
    n3 = _node("E2d", "1.0")
    e1 = _edge(source_study="E2b", target_study="E2c", relationship=RelationshipType.EXTENDS)
    e2 = _edge(
        source_study="E2c", target_study="E2d", relationship=RelationshipType.CONSTRUCT_VALIDITY
    )
    g = LineageGraph.build([n3, n1, n2], [e2, e1])
    # Normalized sorted
    assert g.nodes[0].study == "E2b"
    assert g.edges[0].source_study == "E2b"
    assert g.fingerprint() == hashlib.sha256(g.canonical_json().encode()).hexdigest()
    # Frozen
    with pytest.raises((ValidationError, AttributeError, TypeError)):
        g.nodes = []  # type: ignore[misc]


def test_graph_ancestors_successors_topological() -> None:
    n1 = _node("A", "1.0")
    n2 = _node("B", "1.0")
    n3 = _node("C", "1.0")
    e1 = _edge(source_study="A", source_version="1.0", target_study="B", target_version="1.0")
    e2 = _edge(source_study="B", source_version="1.0", target_study="C", target_version="1.0")
    g = LineageGraph.build([n1, n2, n3], [e1, e2])
    # Successors
    succ = g.successors("A", "1.0")
    assert len(succ) == 1 and succ[0].study == "B"
    # Ancestors of C includes A and B
    ancestors = g.ancestors("C", "1.0")
    assert {a.study for a in ancestors} == {"A", "B"}
    # Descendants of A includes B,C
    desc = g.descendants("A", "1.0")
    assert {d.study for d in desc} == {"B", "C"}
    # Topological order deterministic
    order = g.topological_order()
    assert [n.study for n in order] == ["A", "B", "C"]
    # Second call same
    assert g.topological_order() == order


def test_graph_deterministic_fingerprint_roundtrip() -> None:
    n1 = _node("E2b", "1.0")
    n2 = _node("E2c", "1.0")
    e1 = _edge()
    g1 = LineageGraph.build([n1, n2], [e1])
    g2 = LineageGraph.model_validate(json.loads(g1.canonical_json()))
    assert g1.fingerprint() == g2.fingerprint()


# ---------------------------------------------------------------------------
# Fail closed: duplicate, unknown endpoint, self-edge, cycle
# ---------------------------------------------------------------------------


def test_duplicate_edge_rejected() -> None:
    n1 = _node("E2b", "1.0")
    n2 = _node("E2c", "1.0")
    e1 = _edge()
    # Build with duplicate same edge twice (same fingerprint)
    with pytest.raises(ValidationError, match="duplicate"):
        LineageGraph.build([n1, n2], [e1, e1])


def test_duplicate_node_rejected() -> None:
    n1 = _node("E2b", "1.0")
    with pytest.raises(ValidationError, match="duplicate"):
        LineageGraph(nodes=[n1, n1], edges=[])


def test_unknown_endpoint_rejected() -> None:
    n1 = _node("E2b", "1.0")
    # Edge references missing target
    e = _edge(source_study="E2b", target_study="E2c")
    with pytest.raises(ValidationError, match="not in nodes"):
        LineageGraph.build([n1], [e])


def test_self_edge_rejected() -> None:
    with pytest.raises(ValidationError, match="self-edge"):
        _edge(source_study="E2b", target_study="E2b", source_version="1.0", target_version="1.0")


def test_cycle_rejected_where_dag_required() -> None:
    n1 = _node("A", "1.0")
    n2 = _node("B", "1.0")
    n3 = _node("C", "1.0")
    e1 = _edge(source_study="A", target_study="B", relationship=RelationshipType.EXTENDS)
    e2 = _edge(source_study="B", target_study="C", relationship=RelationshipType.EXTENDS)
    e3 = _edge(source_study="C", target_study="A", relationship=RelationshipType.EXTENDS)
    with pytest.raises(ValidationError, match="cycle"):
        LineageGraph.build([n1, n2, n3], [e1, e2, e3])


def test_relationship_mutation_fails_fingerprint() -> None:
    e = _edge(relationship=RelationshipType.EXTENDS)
    # Mutate relationship but keep old fingerprint should fail
    payload = e.model_dump(mode="json")
    payload["relationship"] = RelationshipType.SUPERSEDES.value
    # Fingerprint still old, so validation should fail due to drift
    with pytest.raises(ValidationError, match="fingerprint drift"):
        LineageEdge.model_validate(payload)


def test_extra_fields_forbidden() -> None:
    e = _edge()
    payload = e.model_dump(mode="json")
    payload["extra_field"] = "oops"
    with pytest.raises(ValidationError, match="extra"):
        LineageEdge.model_validate(payload)


def test_private_path_rejected() -> None:
    with pytest.raises(ValidationError, match="private"):
        _edge(rationale="see /Users/alice/data for details, needs longer rationale text")


def test_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="secret"):
        _edge(declared_source="api_key=sk-123456789")


def test_edges_must_be_sorted() -> None:
    n1 = _node("A", "1.0")
    n2 = _node("B", "1.0")
    n3 = _node("C", "1.0")
    e1 = _edge(source_study="A", target_study="B")
    e2 = _edge(source_study="B", target_study="C")
    # Pass unsorted order should still be normalized by build, but direct validation with unsorted should fail  # noqa: E501
    # Build normalizes, so test direct model_validate with unsorted
    with pytest.raises(ValidationError, match="sorted"):
        LineageGraph.model_validate(
            {
                "nodes": [n3.model_dump(), n1.model_dump(), n2.model_dump()],
                "edges": [e2.model_dump(), e1.model_dump()],
            }
        )


def test_model_copy_bypass_defeated() -> None:
    e = _edge()
    # Use model_copy with bypass? In pydantic frozen, copy still validates on assignment? We simulate bypass via object.__setattr__  # noqa: E501
    copied = e.model_copy(deep=True)
    # Mutate via object.__setattr__ to bypass frozen
    object.__setattr__(copied, "rationale", "mutated rationale without updating fingerprint")
    # Now revalidate at graph boundary should fail because fingerprint drift
    n1 = _node("E2b", "1.0")
    n2 = _node("E2c", "1.0")
    with pytest.raises(ValidationError, match="fingerprint drift"):
        LineageGraph.build([n1, n2], [copied])


def test_no_inferred_edge() -> None:
    # Graph with A->B and B->C should not automatically imply A->C; ancestors should be computed but no edge inferred  # noqa: E501
    n1 = _node("A", "1.0")
    n2 = _node("B", "1.0")
    n3 = _node("C", "1.0")
    e1 = _edge(source_study="A", target_study="B")
    e2 = _edge(source_study="B", target_study="C")
    g = LineageGraph.build([n1, n2, n3], [e1, e2])
    # Direct edge A->C does not exist
    assert all(not (e.source_study == "A" and e.target_study == "C") for e in g.edges)
    # But ancestor relation exists deterministically
    assert any(a.study == "A" for a in g.ancestors("C", "1.0"))
