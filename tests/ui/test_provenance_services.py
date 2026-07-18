from __future__ import annotations

from traffictwin.ui.labels import UiPage
from traffictwin.ui.pages.provenance_explorer import PROVENANCE_NOTICE
from traffictwin.ui.services import (
    metric_provenance_for_ui,
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
