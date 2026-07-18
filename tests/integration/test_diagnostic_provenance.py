from __future__ import annotations

from tests.helpers import diagnostic_case, fixed_clock

from traffictwin.provenance.builder import build_evidence_rule_trace
from traffictwin.provenance.models import ProvenanceNodeType
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.evaluation import evidence_pack_from_case


def test_under_offloading_evidence_pack_trace_marks_source_rows_unavailable() -> None:
    pack = evidence_pack_from_case(diagnostic_case("under_offloading"), clock=fixed_clock)
    report = evaluate_rules(pack, clock=fixed_clock)
    trace = build_evidence_rule_trace("R1", pack, report, clock=fixed_clock)

    assert trace.root_node_id == "rule_result:R1"
    assert "R1" in report.triggered_rule_ids
    assert any(node.node_id.endswith("task.offload.rate") for node in trace.nodes)
    assert any(
        node.node_type is ProvenanceNodeType.UNAVAILABLE_REFERENCE and "Source rows" in node.label
        for node in trace.nodes
    )


def test_infrastructure_bottleneck_evidence_pack_trace_reaches_r2_metrics() -> None:
    pack = evidence_pack_from_case(diagnostic_case("infrastructure_bottleneck"), clock=fixed_clock)
    report = evaluate_rules(pack, clock=fixed_clock)
    trace = build_evidence_rule_trace("R2", pack, report, clock=fixed_clock)
    node_ids = {node.node_id for node in trace.nodes}

    assert trace.root_node_id == "rule_result:R2"
    assert "R2" in report.triggered_rule_ids
    assert "metric_result:run-infrastructure_bottleneck:infra.utilisation.p95" in node_ids
    assert "canonical_table:infrastructure" in node_ids
