from __future__ import annotations

from tests.helpers import bundle_result, fixed_clock, metric_collection
from traffictwin.provenance.builder import build_metric_trace
from traffictwin.provenance.markdown import trace_to_markdown


def test_markdown_export_contains_lineage_and_disclaimer() -> None:
    trace = build_metric_trace(
        "task.completion.rate",
        bundle_result("baseline_valid"),
        metric_collection("baseline_valid"),
        clock=fixed_clock,
    )
    markdown = trace_to_markdown(trace)

    assert "# TrafficTwin Provenance Trace" in markdown
    assert "does not establish real-world causality" in markdown
    assert "task.completion.rate" in markdown
    assert "Source Rows" in markdown
