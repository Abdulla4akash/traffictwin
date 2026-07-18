from __future__ import annotations

import pytest

from tests.helpers import fixed_clock
from traffictwin.provenance.query import (
    ProvenanceQueryError,
    build_provenance_context,
    dependent_rules_for_metric,
    get_metric_provenance,
    get_rule_provenance,
    get_run_provenance,
    get_source_provenance,
    search_provenance,
)


def test_query_context_lists_and_searches_traceable_items() -> None:
    context = build_provenance_context(
        "tests/fixtures/bundles/baseline_valid",
        clock=fixed_clock,
    )

    assert context.analysis_ready
    assert context.diagnostic_report is not None
    assert "R1" in [result.rule_id for result in context.diagnostic_report.results]
    assert "task.completion.rate" in search_provenance(context, "completion")
    assert dependent_rules_for_metric("infra.utilisation.p95") == ["R2"]


def test_query_builds_run_metric_rule_and_source_views() -> None:
    context = build_provenance_context(
        "tests/fixtures/bundles/baseline_valid",
        clock=fixed_clock,
    )

    assert get_run_provenance(context, clock=fixed_clock).root_node_id == "run:run-baseline-001"
    assert (
        get_metric_provenance(context, "task.completion.rate", clock=fixed_clock).root_node_id
        == "metric_result:run-baseline-001:task.completion.rate"
    )
    assert get_rule_provenance(context, "R1", clock=fixed_clock).root_node_id == "rule_result:R1"
    assert get_source_provenance(context, "tasks.csv", 2).raw_values["task_id"] == "t1"


def test_metric_query_rejects_rejected_bundle() -> None:
    context = build_provenance_context("tests/fixtures/bundles/invalid_manifest")

    with pytest.raises(ProvenanceQueryError):
        get_metric_provenance(context, "task.completion.rate")
