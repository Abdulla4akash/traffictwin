"""Unit tests for event-aligned service reusing windowed engine."""

from __future__ import annotations

import tempfile
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from traffictwin.event_aligned.models import (
    CoverageState,
    EventAlignedPhase,
    EventAlignedWindowSpec,
    EventAnchor,
    EventAnchorKind,
)
from traffictwin.event_aligned.service import build_event_aligned_report
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.catalogue import METRIC_DEFINITIONS

FIXTURES = Path("tests/fixtures/bundles")


def _spec(metric_key: str = "task.completion.rate") -> EventAlignedWindowSpec:
    defn = METRIC_DEFINITIONS[metric_key]
    return EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key=metric_key,
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
    )


def _anchors_for_two_runs(kind: EventAnchorKind = EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP):
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
    a1 = EventAnchor(
        kind=kind,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label=kind.authored_label,
        run_id=b1.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b1.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    a2 = EventAnchor(
        kind=kind,
        anchor_time_utc=datetime(2026, 7, 17, 12, 5, 5, tzinfo=UTC),
        source_label=kind.authored_label,
        run_id=b2.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b2.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    return (b1, a1), (b2, a2)


def test_pre_event_post_exact_boundaries_half_open() -> None:
    """A row at the exact boundary must enter only one half-open window."""

    # Use service with known fixture where task at 0,5,8 and anchor at 12:00:05
    # Task at 0 absolute 12:00:00 is at boundary between pre bins, should be in bin1 not bin0.
    (b1, a1), (b2, a2) = _anchors_for_two_runs()
    report = build_event_aligned_report([(b1, a1), (b2, a2)], _spec(), report_id="half-open-test")
    # Find baseline points
    baseline_points = [p for p in report.metric_points if p.run_id == "run-baseline-001"]
    # Sort by bin_index
    baseline_points.sort(key=lambda p: p.bin_index)
    # bin0: [-10,-5) -> absolute 11:59:55-12:00:00 should be empty (no task at exactly 11:59:55)
    # bin1: [-5,0) -> 12:00:00-12:00:05 should contain task at 0
    assert baseline_points[0].coverage_state == CoverageState.EMPTY
    assert baseline_points[0].source_record_counts["tasks"] == 0
    assert baseline_points[1].source_record_counts["tasks"] == 1
    assert baseline_points[1].coverage_state == CoverageState.COMPLETE
    # bin2: [0,5) -> 12:00:05-12:00:10 should contain tasks at 5 and 8
    assert baseline_points[2].source_record_counts["tasks"] == 2
    # Ensure task at exactly 12:00:05 is not double-counted in bin1 and bin2
    total_tasks_across_bins = sum(p.source_record_counts["tasks"] for p in baseline_points)
    # Total tasks in fixture is 3, but they are spread across bins; check no double count:
    # bins: 0:0,1:1,2:2,3:0,4:0,5:0 => total 3
    assert total_tasks_across_bins == 3
    # Verify half-open: task at boundary 12:00:05 belongs to bin2 not bin1
    # If buggy inclusive end, bin1 would have 2 tasks (0 and 5?) but we have 1
    assert baseline_points[1].source_record_counts["tasks"] != 2


def test_naive_timestamp_rejection() -> None:
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
    naive = datetime(2026, 7, 17, 12, 0, 5)  # naive
    with pytest.raises(ValueError, match="timezone-aware"):
        EventAnchor(
            kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
            anchor_time_utc=naive,  # type: ignore[arg-type]
            source_label="Authored — Manual timestamp",
        )
    # Also via service: should raise
    # Create anchor via circumventing validation then pass to service? Instead test service directly with naive via model validation skipped
    # Use spec build with naive anchor should be caught before
    with pytest.raises(ValueError):
        build_event_aligned_report(
            [
                (
                    b1,
                    EventAnchor(
                        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
                        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
                        source_label="Authored — Manual timestamp",
                    ),
                ),
                (
                    b2,
                    # This will be created with naive but we try to bypass via direct dict? Use Validation
                    EventAnchor.model_validate(
                        {
                            "kind": "manual_authored_timestamp",
                            "anchor_time_utc": naive.isoformat(),
                            "source_label": "Authored — Manual timestamp",
                        }
                    ),
                ),
            ],
            _spec(),
        )


def test_two_equivalent_temporary_roots_produce_identical_fingerprint() -> None:
    """Two equivalent bundles at different temporary roots must yield identical fingerprint."""

    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        src = FIXTURES / "baseline_valid"
        dst1 = Path(td1) / "bundle1"
        dst2 = Path(td2) / "bundle2"
        shutil.copytree(src, dst1)
        shutil.copytree(src, dst2)
        # Also copy variation
        src2 = FIXTURES / "variation_valid"
        dst1_v = Path(td1) / "bundle2v"
        dst2_v = Path(td2) / "bundle2v"
        shutil.copytree(src2, dst1_v)
        shutil.copytree(src2, dst2_v)

        from datetime import timedelta

        b1_a = validate_bundle(dst1)
        b1_b = validate_bundle(dst2)
        b2_a = validate_bundle(dst1_v)
        b2_b = validate_bundle(dst2_v)

        spec = _spec()
        a1 = EventAnchor(
            kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
            anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
            source_label="Authored — Manual timestamp",
            run_id=b1_a.manifest.run.run_id,  # type: ignore[union-attr]
            bundle_id=b1_a.manifest.bundle.bundle_id,  # type: ignore[union-attr]
        )
        a1_b = EventAnchor(
            kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
            anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
            source_label="Authored — Manual timestamp",
            run_id=b1_b.manifest.run.run_id,  # type: ignore[union-attr]
            bundle_id=b1_b.manifest.bundle.bundle_id,  # type: ignore[union-attr]
        )
        a2 = EventAnchor(
            kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
            anchor_time_utc=datetime(2026, 7, 17, 12, 5, 5, tzinfo=UTC),
            source_label="Authored — Manual timestamp",
            run_id=b2_a.manifest.run.run_id,  # type: ignore[union-attr]
            bundle_id=b2_a.manifest.bundle.bundle_id,  # type: ignore[union-attr]
        )
        a2_b = EventAnchor(
            kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
            anchor_time_utc=datetime(2026, 7, 17, 12, 5, 5, tzinfo=UTC),
            source_label="Authored — Manual timestamp",
            run_id=b2_b.manifest.run.run_id,  # type: ignore[union-attr]
            bundle_id=b2_b.manifest.bundle.bundle_id,  # type: ignore[union-attr]
        )

        def fixed_clock() -> datetime:
            return datetime(2026, 7, 18, 12, 0, 0, tzinfo=UTC)

        report_a = build_event_aligned_report([(b1_a, a1), (b2_a, a2)], spec, clock=fixed_clock, report_id="identical-test")
        report_b = build_event_aligned_report([(b1_b, a1_b), (b2_b, a2_b)], spec, clock=fixed_clock, report_id="identical-test")
        assert report_a.fingerprint == report_b.fingerprint
        assert report_a.canonical_json() == report_b.canonical_json()


def test_event_anchor_change_alters_identity() -> None:
    (b1, a1), (b2, a2) = _anchors_for_two_runs()
    spec = _spec()
    report1 = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="anchor-change")
    # Change anchor by 1 second
    a1_changed = EventAnchor(
        kind=a1.kind,
        anchor_time_utc=a1.anchor_time_utc + timedelta(seconds=1),
        source_label=a1.source_label,
        run_id=a1.run_id,
        bundle_id=a1.bundle_id,
    )
    report2 = build_event_aligned_report([(b1, a1_changed), (b2, a2)], spec, report_id="anchor-change")
    assert report1.fingerprint != report2.fingerprint
    assert report1.canonical_json() != report2.canonical_json()


def test_metric_version_change_alters_identity() -> None:
    (b1, a1), (b2, a2) = _anchors_for_two_runs()
    spec1 = _spec()
    # Manually construct spec with different version
    spec2 = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="9.9",
        metric_unit="ratio",
    )
    report1 = build_event_aligned_report([(b1, a1), (b2, a2)], spec1, report_id="version-test")
    report2 = build_event_aligned_report([(b1, a1), (b2, a2)], spec2, report_id="version-test")
    assert report1.fingerprint != report2.fingerprint


def test_row_order_not_altering_identity() -> None:
    (b1, a1), (b2, a2) = _anchors_for_two_runs()
    spec = _spec()
    report_ordered = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="order-test")
    report_reversed = build_event_aligned_report([(b2, a2), (b1, a1)], spec, report_id="order-test")
    assert report_ordered.fingerprint == report_reversed.fingerprint
    assert report_ordered.canonical_json() == report_reversed.canonical_json()


def test_partial_and_empty_coverage() -> None:
    # Use durations not divisible by bin width to force partial
    defn = METRIC_DEFINITIONS["task.completion.rate"]
    spec = EventAlignedWindowSpec(
        pre_duration_s=7,  # 7 with bin 5 => bins: 5 + 2 partial
        event_duration_s=7,
        post_duration_s=7,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version=defn.implementation_version,
        metric_unit=defn.unit,
    )
    (b1, a1), (b2, a2) = _anchors_for_two_runs()
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="partial-test")
    # Check that some bins are partial
    partials = [p for p in report.metric_points if p.coverage_state == CoverageState.PARTIAL]
    empties = [p for p in report.metric_points if p.coverage_state == CoverageState.EMPTY]
    completes = [p for p in report.metric_points if p.coverage_state == CoverageState.COMPLETE]
    assert len(partials) > 0, "Expected at least one partial bin"
    assert len(empties) > 0, "Expected at least one empty bin"
    assert len(completes) > 0, "Expected at least one complete bin"
    # Partial bins should have coverage_fraction <1
    for p in partials:
        assert p.coverage_fraction < 1.0
        assert p.coverage_fraction > 0


def test_runs_with_different_anchor_sources() -> None:
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
    a1 = EventAnchor(
        kind=EventAnchorKind.BUNDLE_DECLARED_EVENT,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Bundle declared event",
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
    report = build_event_aligned_report([(b1, a1), (b2, a2)], _spec(), report_id="different-sources")
    assert len(report.accepted_runs) == 2
    kinds = {r.anchor.kind for r in report.accepted_runs}
    assert EventAnchorKind.BUNDLE_DECLARED_EVENT in kinds
    assert EventAnchorKind.AUTHORED_INCIDENT in kinds
    # All labels must be authored
    for run in report.accepted_runs:
        assert "Authored" in run.anchor.source_label
        assert "observed" not in run.anchor.source_label.lower()


def test_incompatible_metric_version_rejected() -> None:
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="9.9.9",  # incompatible
        metric_unit="ratio",
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
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="incompat-version")
    assert len(report.excluded_runs) == 2
    assert len(report.accepted_runs) == 0
    for excl in report.excluded_runs:
        assert excl.reason_code == "METRIC_VERSION_MISMATCH"
        assert "does not match spec version" in excl.reason_detail


def test_incompatible_unit_rejected() -> None:
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="seconds",  # wrong unit
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
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="incompat-unit")
    assert len(report.excluded_runs) == 2
    assert all(e.reason_code == "UNIT_MISMATCH" for e in report.excluded_runs)


def test_missing_bins_not_zero_filled() -> None:
    (b1, a1), (b2, a2) = _anchors_for_two_runs()
    report = build_event_aligned_report([(b1, a1), (b2, a2)], _spec(), report_id="zero-fill")
    # Find unavailable points
    unavailable = [p for p in report.metric_points if p.status != "available"]
    assert len(unavailable) > 0
    for p in unavailable:
        assert p.value is None, "Missing bins must be None, not zero-filled"
        assert p.value != 0 or p.value is None  # Explicit: not zero
        # Ensure we don't silently have value 0 for unavailable
        if p.status == "unavailable":
            assert p.value is None


def test_fingerprint_excludes_generated_at_and_local_path() -> None:
    (b1, a1), (b2, a2) = _anchors_for_two_runs()
    spec = _spec()

    def clock1() -> datetime:
        return datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC)

    def clock2() -> datetime:
        return datetime(2026, 8, 10, 15, 30, 0, tzinfo=UTC)

    report1 = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="fp-excludes-wc", clock=clock1)
    report2 = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="fp-excludes-wc", clock=clock2)
    # Fingerprint must be identical despite different generated_at
    assert report1.fingerprint == report2.fingerprint
    assert report1.canonical_json() == report2.canonical_json()
    # Also local path should not affect: copy bundle to different temp paths and ensure same fingerprint
    import tempfile
    import shutil

    with tempfile.TemporaryDirectory() as td:
        src = FIXTURES / "baseline_valid"
        dst = Path(td) / "different_path_bundle"
        shutil.copytree(src, dst)
        b1_alt = validate_bundle(dst)
        # Use same anchor times
        a1_alt = EventAnchor(
            kind=a1.kind,
            anchor_time_utc=a1.anchor_time_utc,
            source_label=a1.source_label,
            run_id=b1_alt.manifest.run.run_id,  # type: ignore[union-attr]
            bundle_id=b1_alt.manifest.bundle.bundle_id,  # type: ignore[union-attr]
        )
        report3 = build_event_aligned_report([(b1_alt, a1_alt), (b2, a2)], spec, report_id="fp-excludes-wc", clock=clock1)
        # Fingerprint should still be identical because fingerprint excludes local path; but bundle fingerprint may differ due to? Actually bundle fingerprint is hash of bundle contents, not path, so should be same as original if contents same.
        # The key is local path string not in canonical json
        assert "different_path_bundle" not in report3.canonical_json()
        assert report1.fingerprint == report3.fingerprint


def test_authored_anchor_labelling() -> None:
    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
    for kind in EventAnchorKind:
        anchor = EventAnchor(
            kind=kind,
            anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
            source_label=kind.authored_label,
            run_id=b1.manifest.run.run_id,  # type: ignore[union-attr]
            bundle_id=b1.manifest.bundle.bundle_id,  # type: ignore[union-attr]
        )
        assert "Authored" in anchor.display_label()
        assert "observed" not in anchor.display_label().lower()
        # Also test that anchor's source_label is authored
        assert "Authored" in anchor.source_label


def test_insufficient_temporal_range_exclusion() -> None:
    # Create a bundle with no canonical timestamps? Use a fabricated empty canonical?
    # Instead test that a run with empty canonical would be excluded.
    # We'll simulate by using a bundle that has data but anchor far outside range -> should not be excluded, but empty bins.
    # The insufficient range case is when bundle has no timestamps at all.
    from traffictwin.canonical.tables import CanonicalTables
    from traffictwin.ingestion.bundle import BundleValidationResult
    from traffictwin.evidence.availability import EvidenceAvailability
    from traffictwin.validation.report import ValidationReport
    from traffictwin.ingestion.manifest import BundleManifest, BundleInfo, RunInfo, EnvironmentInfo, ProvenanceInfo
    from datetime import timezone

    # Use valid bundles but also test empty canonical scenario
    # Create minimal manifest
    manifest = BundleManifest(
        schema_version="1.0",
        bundle=BundleInfo(bundle_id="bundle-empty", created_at=datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC), source="synthetic"),
        run=RunInfo(run_id="run-empty", experiment_id="exp-1", seed_id="seed-1", algorithm="alg", random_seed=0),
        environment=EnvironmentInfo(name="synthetic"),
        files={},
        provenance=ProvenanceInfo(producer="test"),
    )
    empty_canonical = CanonicalTables()
    result = BundleValidationResult(
        source=Path("empty"),
        fingerprint="a" * 64,
        manifest=manifest,
        seed=None,
        canonical=empty_canonical,
        evidence=EvidenceAvailability(),
        insufficient_evidence=None,  # type: ignore[arg-type]
        report=ValidationReport(),
    )
    # Need second valid run to meet 2-run minimum
    b2 = validate_bundle(FIXTURES / "baseline_valid")
    a_empty = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id="run-empty",
        bundle_id="bundle-empty",
    )
    a2 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b2.manifest.run.run_id,  # type: ignore[union-attr]
        bundle_id=b2.manifest.bundle.bundle_id,  # type: ignore[union-attr]
    )
    report = build_event_aligned_report([(result, a_empty), (b2, a2)], _spec(), report_id="insufficient")
    # Empty canonical run should be excluded with INSUFFICIENT_TEMPORAL_RANGE
    assert any(r.run_id == "run-empty" and r.reason_code == "INSUFFICIENT_TEMPORAL_RANGE" for r in report.excluded_runs)
