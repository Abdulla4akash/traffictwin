"""Tests for source-preview, trace, and card display components."""

from __future__ import annotations

from datetime import UTC, datetime

from streamlit.testing.v1 import AppTest

from traffictwin.provenance.models import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceRelation,
    ProvenanceStatus,
    ProvenanceTrace,
    SourceRowPreview,
    TraceCompleteness,
    TraceCompletenessSummary,
)
from traffictwin.ui.components.cards import fingerprint_summary

FULL_FINGERPRINT = "b778c4c3a9e14f02aa10cc93fe8d1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f"


def _trace() -> ProvenanceTrace:
    return ProvenanceTrace(
        trace_id="trace-1",
        root_node_id="node-root",
        nodes=[
            ProvenanceNode(
                node_id="node-root",
                node_type=ProvenanceNodeType.METRIC_RESULT,
                label="Metric result",
            ),
            ProvenanceNode(
                node_id="node-source",
                node_type=ProvenanceNodeType.SOURCE_FILE,
                label="trips.csv",
            ),
        ],
        edges=[
            ProvenanceEdge(
                source_node_id="node-root",
                target_node_id="node-source",
                relation=ProvenanceRelation.COMPUTED_FROM,
            )
        ],
        generated_at=datetime(2026, 7, 24, tzinfo=UTC),
        source_fingerprint=FULL_FINGERPRINT,
        completeness=TraceCompletenessSummary(
            overall=TraceCompleteness.PARTIAL,
            categories={"metrics": TraceCompleteness.PARTIAL},
            reasons={"metrics": ["one metric unavailable"]},
        ),
    )


def _preview() -> SourceRowPreview:
    return SourceRowPreview(
        file="trips.csv",
        row_number=42,
        status=ProvenanceStatus.AVAILABLE,
        raw_values={"vehicle_id": "veh-1", "duration_s": "12.5"},
        canonical_record_type="TripRecord",
        inclusion_status="included",
    )


def _collect_text(at: AppTest) -> str:
    parts = [str(block.value) for block in at.markdown]
    parts.extend(str(caption.value) for caption in at.caption)
    parts.extend(str(code.value) for code in at.code)
    return "\n".join(parts)


def _render_trace_summary() -> None:
    from tests.unit.ui.test_components_displays import _trace
    from traffictwin.ui.components.trace_tree import render_trace_summary

    render_trace_summary(_trace())


def _render_trace_details() -> None:
    from tests.unit.ui.test_components_displays import _trace
    from traffictwin.ui.components.trace_tree import (
        render_trace_completeness,
        render_trace_lineage,
        render_trace_nodes,
    )

    trace = _trace()
    render_trace_lineage(trace)
    render_trace_nodes(trace)
    render_trace_completeness(trace)


def _render_source_preview() -> None:
    from tests.unit.ui.test_components_displays import _preview
    from traffictwin.ui.components.source_preview import render_source_row_preview

    render_source_row_preview(_preview())


def _render_fingerprint_card() -> None:
    from tests.unit.ui.test_components_displays import FULL_FINGERPRINT
    from traffictwin.ui.components.cards import metric_card, render_fingerprint, text_card

    render_fingerprint("Source fingerprint", FULL_FINGERPRINT)
    render_fingerprint("Source fingerprint", None)
    metric_card("Latency P50 (ms)", None)
    text_card("Design version", "v0.7")


def test_fingerprint_summary_truncates_and_preserves_unavailable() -> None:
    assert fingerprint_summary(FULL_FINGERPRINT) == f"{FULL_FINGERPRINT[:12]}…"
    assert fingerprint_summary(None) == "Unavailable"
    assert fingerprint_summary("  ") == "Unavailable"
    assert fingerprint_summary("abc123") == "abc123"


def test_trace_summary_truncates_fingerprint_and_keeps_full_value_advanced() -> None:
    at = AppTest.from_function(_render_trace_summary)
    at.run()
    assert not at.exception
    text = _collect_text(at)
    assert f"{FULL_FINGERPRINT[:12]}…" in text
    assert FULL_FINGERPRINT in text  # full value stays reachable in the expander
    assert "does not establish real-world causality" in text
    assert len(at.json) == 0


def test_trace_summary_shows_completeness_and_counts_without_dict_dump() -> None:
    at = AppTest.from_function(_render_trace_summary)
    at.run()
    assert not at.exception
    text = _collect_text(at)
    assert "partial" in text.lower()
    assert "Nodes:" in text
    assert "Edges:" in text
    assert "node_type_counts" not in text


def test_trace_details_render_tables_without_exception() -> None:
    at = AppTest.from_function(_render_trace_details)
    at.run()
    assert not at.exception
    assert len(at.dataframe) >= 3
    assert len(at.json) == 0


def test_source_preview_renders_labels_and_no_primary_dict_dump() -> None:
    at = AppTest.from_function(_render_source_preview)
    at.run()
    assert not at.exception
    text = _collect_text(at)
    assert "trips.csv" in text
    assert "row 42" in text
    assert "included" in text
    assert "TripRecord" in text
    assert len(at.json) == 0


def test_fingerprint_card_helpers_render_without_exception() -> None:
    at = AppTest.from_function(_render_fingerprint_card)
    at.run()
    assert not at.exception
    text = _collect_text(at)
    assert f"{FULL_FINGERPRINT[:12]}…" in text
    assert FULL_FINGERPRINT in text
    assert "Unavailable" in text
    assert len(at.metric) == 2
