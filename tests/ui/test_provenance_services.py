from __future__ import annotations

from traffictwin.provenance.completeness import ProvenanceCompletenessReport
from traffictwin.provenance.differences import DifferenceContributionReport
from traffictwin.provenance.graph_export import ProvenanceGraphView
from traffictwin.ui.labels import UiPage
from traffictwin.ui.pages.provenance_explorer import PROVENANCE_NOTICE
from traffictwin.ui.services import (
    comparison_provenance_completeness_for_ui,
    difference_contributions_for_ui,
    metric_provenance_for_ui,
    provenance_graph_for_ui,
    report_provenance_completeness_for_ui,
    rule_provenance_for_ui,
    source_preview_for_ui,
    validate_bundle_for_ui,
)


def test_provenance_ui_services_build_traces_without_recomputing_in_page() -> None:
    analysis = validate_bundle_for_ui("tests/fixtures/bundles/baseline_valid")

    metric_trace = metric_provenance_for_ui(analysis, "task.completion.rate")
    rule_trace = rule_provenance_for_ui(analysis, "R1")
    preview = source_preview_for_ui(analysis, "tasks.csv", 2)

    assert metric_trace.root_node_id == "metric_result:run-baseline-001:task.completion.rate"
    assert rule_trace.root_node_id == "rule_result:R1"
    assert preview.raw_values["task_id"] == "t1"


def test_provenance_page_label_and_notice_are_causal_safe() -> None:
    forbidden = ["proves", "caused by", "definitely", "root cause is"]

    assert UiPage.PROVENANCE.value == "Provenance Explorer"
    assert "does not establish real-world causality" in PROVENANCE_NOTICE
    assert not any(term in PROVENANCE_NOTICE.lower() for term in forbidden)


def test_provenance_graph_ui_service_returns_typed_bounded_view() -> None:
    analysis = validate_bundle_for_ui("tests/fixtures/bundles/baseline_valid")
    trace = metric_provenance_for_ui(analysis, "task.completion.rate")

    view = provenance_graph_for_ui(
        trace,
        node_limit=7,
        edge_limit=8,
        redaction_mode="structure_only",
    )

    assert isinstance(view, ProvenanceGraphView)
    assert len(view.nodes) == 7
    assert view.root_node_id == trace.root_node_id
    assert all(not node.attributes for node in view.nodes)


def test_difference_provenance_ui_service_uses_typed_core() -> None:
    baseline = validate_bundle_for_ui("tests/fixtures/bundles/baseline_valid")
    variation = validate_bundle_for_ui("tests/fixtures/bundles/variation_valid")

    report = difference_contributions_for_ui(
        baseline,
        variation,
        "task.completion.rate",
    )

    assert isinstance(report, DifferenceContributionReport)
    assert report.status.value == "arithmetic"
    assert report.reconciles_to_absolute_delta is True


def test_provenance_completeness_ui_services_use_typed_core() -> None:
    baseline = validate_bundle_for_ui("tests/fixtures/bundles/baseline_valid")
    variation = validate_bundle_for_ui("tests/fixtures/bundles/variation_valid")

    run_report = report_provenance_completeness_for_ui(baseline, "run")
    comparison = comparison_provenance_completeness_for_ui(baseline, variation)

    assert isinstance(run_report, ProvenanceCompletenessReport)
    assert run_report.denominator_count == 33
    assert run_report.unavailable_count == 20
    assert isinstance(comparison, ProvenanceCompletenessReport)
    assert comparison.denominator_count == 14
    assert comparison.score == 0.5
