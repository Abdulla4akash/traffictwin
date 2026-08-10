"""Tests for deterministic exports."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.event_aligned.exports import (
    export_phase_summaries_csv,
    export_points_csv,
    export_report_json,
)
from traffictwin.event_aligned.models import (
    EventAlignedReport,
    EventAlignedWindowSpec,
    EventAnchor,
    EventAnchorKind,
)
from traffictwin.event_aligned.service import build_event_aligned_report
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.catalogue import METRIC_DEFINITIONS

FIXTURES = Path("tests/fixtures/bundles")


def _build_report() -> EventAlignedReport:
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
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
    return build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="export-test")


def test_json_export_is_deterministic() -> None:
    report = _build_report()
    json1 = export_report_json(report)
    json2 = export_report_json(report)
    assert json1 == json2
    # Must be canonical sort_keys
    data = json.loads(json1)
    assert data["fingerprint"] == report.fingerprint
    # Ensure no wall clock leakage: fingerprint must equal computed
    assert report.verify_fingerprint()


def test_csv_points_not_zero_filled() -> None:
    report = _build_report()
    csv_text = export_points_csv(report)
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    # Find unavailable rows
    unavailable = [r for r in rows if r["status"] != "available"]
    assert len(unavailable) > 0
    for row in unavailable:
        assert row["value"] == "", "Missing bins must be empty string, not 0"
        assert row["value"] != "0"
        assert row["value"] != "0.0"


def test_csv_points_uses_same_rows_as_report() -> None:
    report = _build_report()
    csv_text = export_points_csv(report)
    reader = csv.DictReader(io.StringIO(csv_text))
    csv_rows = list(reader)
    assert len(csv_rows) == len(report.metric_points)
    # Check that every report point appears in CSV with same key fields
    for point in report.metric_points:
        matching = [r for r in csv_rows if r["run_id"] == point.run_id and int(r["bin_index"]) == point.bin_index]  # noqa: E501
        assert len(matching) == 1
        csv_row = matching[0]
        assert float(csv_row["relative_start_s"]) == point.relative_start_s
        assert float(csv_row["relative_end_s"]) == point.relative_end_s


def test_phase_summaries_csv() -> None:
    report = _build_report()
    csv_text = export_phase_summaries_csv(report)
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == len(report.phase_summaries)
    for row in rows:
        assert row["run_id"] in {r.run_id for r in report.accepted_runs}
        assert row["phase"] in {"pre", "event", "post"}


def test_timezone_canonicalisation() -> None:
    # Anchor with different timezone representation should canonicalise to same UTC and same fingerprint  # noqa: E501
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
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
    # 12:00Z and 13:00+01:00 are same instant
    anchor_utc = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b1.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b1.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    from datetime import timedelta, timezone

    plus_one = timezone(timedelta(hours=1))
    anchor_plus_one = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 13, 0, 5, tzinfo=plus_one),
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
    def fixed_clock() -> datetime:
        return datetime(2026, 7, 18, 12, 0, 0, tzinfo=UTC)

    report1 = build_event_aligned_report([(b1, anchor_utc), (b2, a2)], spec, clock=fixed_clock, report_id="tz-test")  # noqa: E501
    report2 = build_event_aligned_report([(b1, anchor_plus_one), (b2, a2)], spec, clock=fixed_clock, report_id="tz-test")  # noqa: E501
    assert report1.fingerprint == report2.fingerprint
    # Canonical JSON should use Z notation
    assert "Z" in report1.canonical_json()
    assert report1.canonical_json() == report2.canonical_json()
