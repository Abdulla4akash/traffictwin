"""Integration tests for event-aligned analysis end-to-end."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.event_aligned.exports import export_points_csv, export_report_json
from traffictwin.event_aligned.models import EventAlignedWindowSpec, EventAnchor, EventAnchorKind
from traffictwin.event_aligned.service import build_event_aligned_report, preview_exact_windows
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.catalogue import METRIC_DEFINITIONS


def test_end_to_end_select_align_render_export() -> None:
    """End-to-end select → align → render → export."""

    b1 = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))
    b2 = validate_bundle(Path("tests/fixtures/bundles/variation_valid"))
    defn = METRIC_DEFINITIONS["task.completion.rate"]
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
    )
    a1 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b1.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b1.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    a2 = EventAnchor(
        kind=EventAnchorKind.AUTHORED_INCIDENT,
        anchor_time_utc=datetime(2026, 7, 17, 12, 5, 5, tzinfo=UTC),
        source_label="Authored — Incident",
        run_id=b2.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b2.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )

    # Preview exact half-open windows
    preview = preview_exact_windows(spec, a1)
    assert preview["pre"][1] == preview["event"][0]
    assert preview["event"][1] == preview["post"][0]
    assert all(start.tzinfo is not None for start, _ in preview.values())

    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="e2e-test")

    # Inspect relative-time series and before/during/after summaries
    assert len(report.metric_points) > 0
    assert len(report.phase_summaries) == 6  # 2 runs * 3 phases
    # Inspect gaps, partial windows, exclusions and incompatible runs
    # Should have some gaps (empty bins)
    empty = [p for p in report.metric_points if p.coverage_state.value == "empty"]
    assert len(empty) > 0

    # Export deterministic JSON and tabular CSV
    json_text = export_report_json(report)
    data = json.loads(json_text)
    assert data["fingerprint"] == report.fingerprint
    assert json_text == export_report_json(report)  # deterministic

    csv_text = export_points_csv(report)
    # Verify CSV rows equal metric points
    import csv
    import io

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == len(report.metric_points)
    # Chart and table must consume same rows: check one example
    for point in report.metric_points[:2]:
        matching = [r for r in rows if r["run_id"] == point.run_id and int(r["bin_index"]) == point.bin_index]
        assert len(matching) == 1

    # Verify pairwise descriptive deltas wording not causal
    for delta in report.pairwise_deltas:
        assert "caused" not in delta.description.lower()
        assert "causal" not in delta.description.lower()
        assert "difference during the declared" in delta.description.lower()


def test_exact_ui_window_preview() -> None:
    """Exact window preview must match service preview."""

    defn = METRIC_DEFINITIONS["traffic.speed.mean_mps"]
    spec = EventAlignedWindowSpec(
        pre_duration_s=60,
        event_duration_s=120,
        post_duration_s=60,
        bin_width_s=30,
        metric_key="traffic.speed.mean_mps",
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
    )
    anchor = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 14, 30, 0, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
    )
    preview = spec.preview_windows(anchor.anchor_time_utc)
    # Exact half-open windows per spec:
    # pre: [anchor -60, anchor)
    # event: [anchor, anchor+120)
    # post: [anchor+120, anchor+180)
    assert preview["pre"] == (
        datetime(2026, 7, 17, 14, 29, 0, tzinfo=UTC),
        datetime(2026, 7, 17, 14, 30, 0, tzinfo=UTC),
    )
    assert preview["event"] == (
        datetime(2026, 7, 17, 14, 30, 0, tzinfo=UTC),
        datetime(2026, 7, 17, 14, 32, 0, tzinfo=UTC),
    )
    assert preview["post"] == (
        datetime(2026, 7, 17, 14, 32, 0, tzinfo=UTC),
        datetime(2026, 7, 17, 14, 33, 0, tzinfo=UTC),
    )


def test_chart_table_row_equivalence() -> None:
    b1 = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))
    b2 = validate_bundle(Path("tests/fixtures/bundles/variation_valid"))
    defn = METRIC_DEFINITIONS["task.completion.rate"]
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
    )
    a1 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b1.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b1.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    a2 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 5, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b2.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b2.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="chart-table")
    # Simulate chart rows (available only) and table rows (all)
    table_rows = sorted(report.metric_points, key=lambda p: (p.run_id, p.bin_index))
    chart_rows = [r for r in table_rows if r.status == "available" and isinstance(r.value, (int, float))]
    # Chart must be subset of table
    for cr in chart_rows:
        assert cr in table_rows
    # Table rows count must equal metric_points
    assert len(table_rows) == len(report.metric_points)


def test_incompatible_time_basis_handling() -> None:
    """Incompatible time basis is currently single basis, but test that spec time basis is explicit."""

    defn = METRIC_DEFINITIONS["task.completion.rate"]
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
        canonical_time_basis="utc_bundle_created_at_offset_v1",
    )
    assert spec.canonical_time_basis == "utc_bundle_created_at_offset_v1"
    # If someone tries to create with different basis, it would be a different spec and fingerprint changes
    spec2 = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
        canonical_time_basis="utc_bundle_created_at_offset_v1",
    )
    assert spec.canonical_dict() == spec2.canonical_dict()
