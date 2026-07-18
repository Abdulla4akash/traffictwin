from __future__ import annotations

from tests.helpers import bundle_result, fixed_clock, metric_collection
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.provenance.builder import build_metric_trace, build_rule_trace
from traffictwin.provenance.models import ProvenanceNodeType, ProvenanceRelation
from traffictwin.rules.engine import evaluate_rules


def test_metric_trace_reaches_definition_table_and_source_row() -> None:
    result = bundle_result("baseline_valid")
    metrics = metric_collection("baseline_valid")
    trace = build_metric_trace(
        "task.completion.rate",
        result,
        metrics,
        clock=fixed_clock,
    )
    node_ids = {node.node_id for node in trace.nodes}

    assert trace.root_node_id == "metric_result:run-baseline-001:task.completion.rate"
    assert "metric_definition:task.completion.rate" in node_ids
    assert "canonical_table:tasks" in node_ids
    assert "source_file:tasks.csv" in node_ids
    assert any(node.node_type is ProvenanceNodeType.SOURCE_ROW for node in trace.nodes)
    assert any(edge.relation is ProvenanceRelation.COMPUTED_FROM for edge in trace.edges)
    assert "/Users/" not in trace.to_json()


def test_rule_trace_reaches_cited_metric_keys() -> None:
    result = bundle_result("variation_valid")
    metrics = metric_collection("variation_valid")
    pack = build_evidence_pack(result, metrics, MetricEngineConfig(), clock=fixed_clock)
    report = evaluate_rules(pack, clock=fixed_clock)
    trace = build_rule_trace("R2", result, metrics, pack, report, clock=fixed_clock)
    node_ids = {node.node_id for node in trace.nodes}

    assert trace.root_node_id == "rule_result:R2"
    assert any(node_id.startswith("diagnostic_report:") for node_id in node_ids)
    assert "metric_result:run-variation-001:infra.utilisation.p95" in node_ids
    assert any(node.node_type is ProvenanceNodeType.FINDING for node in trace.nodes)
    assert "/Users/" not in trace.to_json()
