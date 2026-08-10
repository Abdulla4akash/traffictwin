"""Blocker regressions for Event-Aligned defects (M1-M9)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffictwin.canonical.records import TaskRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.energy import TaskEnergyContract
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.event_aligned.exports import (
    export_phase_summaries_csv,
    export_points_csv,
    export_report_json,
)
from traffictwin.event_aligned.models import (
    CoverageState,
    EventAlignedWindowSpec,
    EventAnchor,
    EventAnchorKind,
)
from traffictwin.event_aligned.service import build_event_aligned_report
from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.ingestion.manifest import (
    BundleInfo,
    BundleManifest,
    EnvironmentInfo,
    ProvenanceInfo,
    RunInfo,
)
from traffictwin.metrics.catalogue import METRIC_DEFINITIONS
from traffictwin.validation.report import ImportStatus, ValidationReport

FIXTURES = Path("tests/fixtures/bundles")


def _spec(metric_key: str = "task.completion.rate") -> EventAlignedWindowSpec:
    d = METRIC_DEFINITIONS[metric_key]
    return EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key=metric_key,
        metric_version=d.implementation_version,
        metric_unit=d.unit,
    )


def _anchors() -> tuple[
    tuple[BundleValidationResult, EventAnchor], tuple[BundleValidationResult, EventAnchor]
]:
    from traffictwin.ingestion.bundle import validate_bundle

    b1 = validate_bundle(FIXTURES / "baseline_valid")
    b2 = validate_bundle(FIXTURES / "variation_valid")
    a1 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b1.manifest.run.run_id,  # type: ignore
        bundle_id=b1.manifest.bundle.bundle_id,  # type: ignore
    )
    a2 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 5, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=b2.manifest.run.run_id,  # type: ignore
        bundle_id=b2.manifest.bundle.bundle_id,  # type: ignore
    )
    return (b1, a1), (b2, a2)


def _make_partial_energy_bundle(
    run_id: str = "run-partial-energy",
    bundle_id: str = "bundle-partial-energy",
    arrival_offset: float = 2.0,
) -> tuple[BundleValidationResult, EventAnchor]:
    """Create a bundle where task.energy.per_completed_j is PARTIAL via real engine.

    Two tasks in same bin (0..5 relative to anchor): one with energy,
    one missing → PARTIAL with numeric value 1.0.
    Returned anchor places both tasks in event bin.
    """
    contract = TaskEnergyContract()
    # Both tasks arrive at 2 and 2.5 seconds after created_at (absolute 12:00:02 and 12:00:02.5)
    # Anchor at 12:00:01 → relative 1 and 1.5 → both in event bin 0..5
    tasks = [
        TaskRecord(
            source_file="tasks.csv",
            source_row=1,
            task_id="t1",
            vehicle_id="veh-1",
            task_class=TaskClass.T1,
            arrival_time_s=arrival_offset,
            deadline_ms=100,
            decision=Decision.V2I,
            completed=True,
            completion_time_s=arrival_offset + 0.5,
            latency_ms=50,
            energy_j=1.0,
        ),
        TaskRecord(
            source_file="tasks.csv",
            source_row=2,
            task_id="t2",
            vehicle_id="veh-2",
            task_class=TaskClass.T2,
            arrival_time_s=arrival_offset + 0.5,
            deadline_ms=100,
            decision=Decision.LOCAL,
            completed=True,
            completion_time_s=arrival_offset + 1.0,
            latency_ms=60,
            energy_j=None,
        ),
    ]
    canonical = CanonicalTables(tasks=tasks)
    manifest = BundleManifest(
        schema_version="1.0",
        bundle=BundleInfo(
            bundle_id=bundle_id,
            created_at=datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC),
            source="synthetic",
        ),
        run=RunInfo(
            run_id=run_id, experiment_id="exp-1", seed_id="seed-1", algorithm="alg", random_seed=0
        ),
        environment=EnvironmentInfo(name="synthetic"),
        files={
            "tasks": {
                "path": "tasks.csv",
                "schema_version": "1.0",
                "required_columns": [
                    "task_id",
                    "vehicle_id",
                    "task_class",
                    "arrival_time",
                    "deadline_ms",
                    "decision",
                    "completed",
                ],
                "units": {"energy_j": "J"},
            }
        },
        provenance=ProvenanceInfo(producer="test"),
        energy_contract=contract,
    )
    result = BundleValidationResult(
        source=Path("partial"),
        fingerprint="b" * 64,
        manifest=manifest,
        seed=None,
        canonical=canonical,
        evidence=EvidenceAvailability(tasks="available"),
        insufficient_evidence=None,  # type: ignore
        report=ValidationReport(may_import=True, status=ImportStatus.ACCEPTED),
    )
    anchor = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 1, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=run_id,
        bundle_id=bundle_id,
    )
    return result, anchor


# M1: naive bundle.created_at must fail closed, not fallback to 1970
def test_M1_naive_bundle_time_basis_excluded() -> None:  # noqa: N802
    from traffictwin.ingestion.bundle import validate_bundle

    b_valid = validate_bundle(FIXTURES / "baseline_valid")
    manifest = b_valid.manifest
    naive_created = datetime(2026, 7, 17, 12, 0, 0)  # naive, no tzinfo
    naive_manifest = BundleManifest.model_validate(
        {
            "schema_version": "1.0",
            "bundle": {
                "bundle_id": manifest.bundle.bundle_id,  # type: ignore
                "created_at": naive_created.isoformat(),  # naive
                "source": manifest.bundle.source,  # type: ignore
            },
            "run": {
                "run_id": manifest.run.run_id,  # type: ignore
                "experiment_id": manifest.run.experiment_id,  # type: ignore
                "seed_id": manifest.run.seed_id,  # type: ignore
                "algorithm": manifest.run.algorithm,  # type: ignore
                "random_seed": manifest.run.random_seed,  # type: ignore
            },
            "environment": {"name": "synthetic"},
            "files": {},
            "provenance": {"producer": "test"},
        }
    )
    naive_result = BundleValidationResult(
        source=Path("naive"),
        fingerprint="a" * 64,
        manifest=naive_manifest,
        seed=None,
        canonical=b_valid.canonical,
        evidence=b_valid.evidence,
        insufficient_evidence=b_valid.insufficient_evidence,
        report=ValidationReport(),
    )
    b2, a2 = _anchors()[1]
    a_naive = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 5, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id=naive_manifest.run.run_id,
        bundle_id=naive_manifest.bundle.bundle_id,
    )
    report = build_event_aligned_report(
        [(naive_result, a_naive), (b2, a2)], _spec(), report_id="m1"
    )  # noqa: E501
    assert len(report.excluded_runs) == 1
    assert report.excluded_runs[0].run_id == naive_manifest.run.run_id
    assert report.excluded_runs[0].reason_code == "INVALID_TIME_BASIS"
    assert (
        "naive" in report.excluded_runs[0].reason_detail.lower()
        or "timezone-aware" in report.excluded_runs[0].reason_detail.lower()
    )  # noqa: E501
    assert len(report.accepted_runs) == 1
    assert all(p.run_id != naive_manifest.run.run_id for p in report.metric_points)


def test_M1_tz_aware_accepted() -> None:  # noqa: N802
    (b1, a1), (b2, a2) = _anchors()
    report = build_event_aligned_report([(b1, a1), (b2, a2)], _spec(), report_id="m1-aware")
    assert len(report.accepted_runs) == 2
    assert len(report.excluded_runs) == 0


# M2: max_bins preflight before materialisation (structural bomb)
def test_M2_max_bins_preflight_before_materialisation() -> None:  # noqa: N802
    (b1, a1), (b2, a2) = _anchors()
    spec_ok = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
        max_bins=6,
    )
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec_ok, report_id="m2-ok")
    assert len(report.metric_points) == 12  # 6 bins *2 runs

    spec_over = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
        max_bins=5,
    )
    with pytest.raises(ValueError, match="configured maximum is 5"):
        build_event_aligned_report([(b1, a1), (b2, a2)], spec_over, report_id="m2-over")

    # Structural bomb: ensure huge spec fails BEFORE _build_bins_for_spec is invoked
    spec_path = EventAlignedWindowSpec(
        pre_duration_s=100000,
        event_duration_s=100,
        post_duration_s=100,
        bin_width_s=0.001,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
        max_bins=10000,
    )

    from unittest.mock import patch

    def bomb_build_bins(*args: object, **kwargs: object) -> None:  # noqa: ANN002
        pytest.fail("bin materialisation was reached before max_bins preflight")

    # Patch at service module where _build_bins_for_spec is defined and used
    with (
        patch(
            "traffictwin.event_aligned.service._build_bins_for_spec", side_effect=bomb_build_bins
        ),
        pytest.raises(ValueError, match="configured maximum|exceeds overall"),
    ):
        build_event_aligned_report([(b1, a1), (b2, a2)], spec_path, report_id="m2-path-bomb")
    # Also direct _build_bins_for_spec early rejection
    from traffictwin.event_aligned.service import _build_bins_for_spec

    spec_small = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
        max_bins=3,
    )
    with pytest.raises(ValueError):
        _build_bins_for_spec(spec_small, datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC))


# M3: PARTIAL numeric preservation via real service path (must hit build_event_aligned_report)
def test_M3_partial_numeric_preserved() -> None:  # noqa: N802
    result, a_partial = _make_partial_energy_bundle(
        run_id="run-partial-m3", bundle_id="bundle-partial-m3", arrival_offset=2.0
    )
    result2, a_partial2 = _make_partial_energy_bundle(
        run_id="run-partial-m3b", bundle_id="bundle-partial-m3b", arrival_offset=2.0
    )
    spec = EventAlignedWindowSpec(
        pre_duration_s=5,
        event_duration_s=5,
        post_duration_s=5,
        bin_width_s=5,
        metric_key="task.energy.per_completed_j",
        metric_version="1.0",
        metric_unit="J/task",
    )
    report = build_event_aligned_report(
        [(result, a_partial), (result2, a_partial2)], spec, report_id="m3"
    )
    # Must have at least one real PARTIAL point via service
    partial_points = [p for p in report.metric_points if p.status == "partial"]
    assert partial_points, "expected at least one real PARTIAL point via build_event_aligned_report"
    # All partial points must retain numeric, finite value and remain partial status
    for p in partial_points:
        assert p.status == "partial"
        assert p.value is not None, "PARTIAL must retain numeric value"
        assert isinstance(p.value, float)
        assert p.value == pytest.approx(1.0)
        import math

        assert math.isfinite(p.value)

    # Phase summary must include partial numeric in aggregation
    summaries = [
        s
        for s in report.phase_summaries
        if s.run_id == "run-partial-m3" and s.phase.value == "event"
    ]
    assert summaries
    s = summaries[0]
    assert s.partial_count == 1, f"expected partial_count 1 for event phase, got {s.partial_count}"
    assert s.bin_count == 1
    assert s.mean_value == pytest.approx(1.0)
    assert s.min_value == pytest.approx(1.0)
    assert s.max_value == pytest.approx(1.0)
    # Pairwise delta must be present and finite (both runs have same partial value)
    assert len(report.pairwise_deltas) >= 1
    # Find delta for event phase
    deltas_event = [d for d in report.pairwise_deltas if d.phase.value == "event"]
    assert deltas_event
    for d in deltas_event:
        assert d.baseline_mean == pytest.approx(1.0)
        assert d.variation_mean == pytest.approx(1.0)
        assert d.absolute_difference == pytest.approx(0.0)

    # CSV must contain numeric value not blank
    csv_points = export_points_csv(report)
    assert "1.0" in csv_points or "1" in csv_points
    # Ensure partial row not blank
    lines = csv_points.splitlines()
    # header + rows
    partial_rows = [row for row in lines if "partial" in row]
    assert partial_rows
    for row in partial_rows:
        # value column should not be empty (last check: value field present)
        # CSV columns: run_id,phase,bin_index,...,status,value,...
        # Check that row contains 1.0
        assert "1.0" in row

    # Portable JSON must retain numeric
    j = export_report_json(report)
    assert "1.0" in j
    assert report.fingerprint is not None
    # Empty/unavailable must remain None
    unavailable = [p for p in report.metric_points if p.status == "unavailable"]
    for p in unavailable:
        assert p.value is None

    # Also verify coverage state for these partial points is complete (metric partial only, not coverage)  # noqa: E501
    for p in partial_points:
        assert (
            p.coverage_state == CoverageState.COMPLETE or p.coverage_state == CoverageState.PARTIAL
        )


# M4: non-window metric guard
def test_M4_non_window_metric_rejected() -> None:  # noqa: N802
    (b1, a1), (b2, a2) = _anchors()
    non_window_keys = [k for k, d in METRIC_DEFINITIONS.items() if not d.time_window_applicable]
    assert len(non_window_keys) > 0
    for key in non_window_keys[:3]:  # test 3
        d = METRIC_DEFINITIONS[key]
        spec = EventAlignedWindowSpec(
            pre_duration_s=10,
            event_duration_s=10,
            post_duration_s=10,
            bin_width_s=5,
            metric_key=key,
            metric_version=d.implementation_version,
            metric_unit=d.unit,
        )
        with pytest.raises(ValueError, match="not window-applicable"):
            build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="m4")
        from traffictwin.ui.services.event_aligned import compute_event_aligned_for_ui

        res = compute_event_aligned_for_ui(
            bundle_paths=[
                "tests/fixtures/bundles/baseline_valid",
                "tests/fixtures/bundles/variation_valid",
            ],  # noqa: E501
            metric_key=key,
            pre_duration_s=10,
            event_duration_s=10,
            post_duration_s=10,
            bin_width_s=5,
            anchor_kind="manual_authored_timestamp",
            anchor_timestamps=["2026-07-17T12:00:05Z", "2026-07-17T12:05:05Z"],
        )
        from traffictwin.ui.services.models import ServiceError

        assert isinstance(res, ServiceError)
        assert res.detail is not None
        assert "not window-applicable" in res.detail.lower() or "not window" in res.message.lower()

    ok_spec = _spec("task.completion.rate")
    report = build_event_aligned_report([(b1, a1), (b2, a2)], ok_spec, report_id="m4-ok")
    assert len(report.accepted_runs) == 2


# M5: JSON determinism across clocks
def test_M5_json_determinism_across_clocks() -> None:  # noqa: N802
    (b1, a1), (b2, a2) = _anchors()
    spec = _spec()

    def clock1() -> datetime:
        return datetime(2026, 7, 18, 12, 0, 0, tzinfo=UTC)

    def clock2() -> datetime:
        return datetime(2026, 8, 10, 15, 30, 0, tzinfo=UTC)

    r1 = build_event_aligned_report([(b1, a1), (b2, a2)], spec, clock=clock1, report_id="m5")
    r2 = build_event_aligned_report([(b1, a1), (b2, a2)], spec, clock=clock2, report_id="m5")
    assert r1.fingerprint == r2.fingerprint
    j1 = export_report_json(r1)
    j2 = export_report_json(r2)
    assert j1 == j2
    assert "created_at_utc" not in j1
    assert "created_at_utc" not in j2
    a1_alt = EventAnchor(
        kind=a1.kind,
        anchor_time_utc=a1.anchor_time_utc.replace(day=18),
        source_label=a1.source_label,
        run_id=a1.run_id,
        bundle_id=a1.bundle_id,
    )
    r3 = build_event_aligned_report([(b1, a1_alt), (b2, a2)], spec, clock=clock1, report_id="m5")
    j3 = export_report_json(r3)
    assert j3 != j1


# M6: compatibility is engine-contract, not per-run fake
def test_M6_compatibility_engine_contract() -> None:  # noqa: N802
    (b1, a1), (b2, a2) = _anchors()
    bad_spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="9.9",
        metric_unit="ratio",
    )
    with pytest.raises(ValueError, match="does not match authoritative"):
        build_event_aligned_report([(b1, a1), (b2, a2)], bad_spec, report_id="m6")
    report = build_event_aligned_report([(b1, a1), (b2, a2)], _spec(), report_id="m6-ok")
    assert any("single current engine contract" in w for w in report.warnings)
    assert not any("enforced per run" in w for w in report.warnings)


# M7: run_context hoisted (call count)
def test_M7_run_context_hoisted() -> None:  # noqa: N802
    from unittest.mock import patch

    (b1, a1), (b2, a2) = _anchors()
    spec = EventAlignedWindowSpec(
        pre_duration_s=10,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=2,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
    )
    total_bins = spec.total_bins()  # 15 bins
    with patch("traffictwin.event_aligned.service.run_context_from_bundle") as mock_rc:
        from traffictwin.metrics.engine import run_context_from_bundle as real_rc

        def side_effect(result: BundleValidationResult) -> object:
            return real_rc(result)

        mock_rc.side_effect = side_effect
        _report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="m7")  # noqa: F841
        assert mock_rc.call_count == 2, (
            f"expected 2 calls, got {mock_rc.call_count} (would be {total_bins * 2} if per-bin)"
        )  # noqa: E501


# M8: warning ownership consistent
def test_m8_warning_ownership() -> None:
    (b1, a1), (b2, a2) = _anchors()
    spec = EventAlignedWindowSpec(
        pre_duration_s=100,
        event_duration_s=10,
        post_duration_s=10,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
    )
    a1_far = EventAnchor(
        kind=a1.kind,
        anchor_time_utc=datetime(2026, 7, 17, 15, 0, 0, tzinfo=UTC),
        source_label=a1.source_label,
        run_id=a1.run_id,
        bundle_id=a1.bundle_id,
    )
    report = build_event_aligned_report([(b1, a1_far), (b2, a2)], spec, report_id="m8")
    for w in report.warnings:
        assert "has no available numeric values for" not in w
    summaries_with_warnings = [s for s in report.phase_summaries if s.warnings]
    assert len(summaries_with_warnings) > 0
    for s in summaries_with_warnings:
        assert any("No available numeric values" in w for w in s.warnings)


# M9: partial_count double increment must be once per bin (both conditions true)
def test_M9_partial_count_double_increment() -> None:  # noqa: N802
    # Create a bin that is BOTH metric PARTIAL and coverage PARTIAL
    # Use energy partial with bin_width that leaves partial coverage for that same bin
    contract = TaskEnergyContract()
    tasks = [
        TaskRecord(
            source_file="tasks.csv",
            source_row=1,
            task_id="t1",
            vehicle_id="veh-1",
            task_class=TaskClass.T1,
            arrival_time_s=2,
            deadline_ms=100,
            decision=Decision.V2I,
            completed=True,
            completion_time_s=2.5,
            latency_ms=50,
            energy_j=1.0,
        ),
        TaskRecord(
            source_file="tasks.csv",
            source_row=2,
            task_id="t2",
            vehicle_id="veh-2",
            task_class=TaskClass.T2,
            arrival_time_s=2.2,
            deadline_ms=100,
            decision=Decision.LOCAL,
            completed=True,
            completion_time_s=2.6,
            latency_ms=60,
            energy_j=None,
        ),
    ]
    canonical = CanonicalTables(tasks=tasks)
    manifest = BundleManifest(
        schema_version="1.0",
        bundle=BundleInfo(
            bundle_id="bundle-m9",
            created_at=datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC),
            source="synthetic",
        ),
        run=RunInfo(
            run_id="run-m9", experiment_id="exp-1", seed_id="seed-1", algorithm="alg", random_seed=0
        ),
        environment=EnvironmentInfo(name="synthetic"),
        files={
            "tasks": {
                "path": "tasks.csv",
                "schema_version": "1.0",
                "required_columns": ["task_id"],
                "units": {"energy_j": "J"},
            }
        },
        provenance=ProvenanceInfo(producer="test"),
        energy_contract=contract,
    )
    result = BundleValidationResult(
        source=Path("m9"),
        fingerprint="d" * 64,
        manifest=manifest,
        seed=None,
        canonical=canonical,
        evidence=EvidenceAvailability(tasks="available"),
        insufficient_evidence=None,  # type: ignore
        report=ValidationReport(may_import=True, status=ImportStatus.ACCEPTED),
    )
    manifest2 = BundleManifest(
        schema_version="1.0",
        bundle=BundleInfo(
            bundle_id="bundle-m9b",
            created_at=datetime(2026, 7, 17, 12, 0, 0, tzinfo=UTC),
            source="synthetic",
        ),
        run=RunInfo(
            run_id="run-m9b",
            experiment_id="exp-1",
            seed_id="seed-1",
            algorithm="alg",
            random_seed=1,
        ),
        environment=EnvironmentInfo(name="synthetic"),
        files={
            "tasks": {
                "path": "tasks.csv",
                "schema_version": "1.0",
                "required_columns": ["task_id"],
                "units": {"energy_j": "J"},
            }
        },
        provenance=ProvenanceInfo(producer="test"),
        energy_contract=contract,
    )
    result2 = BundleValidationResult(
        source=Path("m9b"),
        fingerprint="e" * 64,
        manifest=manifest2,
        seed=None,
        canonical=canonical,
        evidence=EvidenceAvailability(tasks="available"),
        insufficient_evidence=None,  # type: ignore
        report=ValidationReport(may_import=True, status=ImportStatus.ACCEPTED),
    )
    # Spec with 7s duration and 5s bin → second bin partial coverage (2/5)
    # Place tasks in the second bin which is partial coverage (event second bin)
    # Event phase 0..7 with 5s bins: bin 0-5 complete, bin 5-7 partial (2s)
    spec = EventAlignedWindowSpec(
        pre_duration_s=5,
        event_duration_s=7,
        post_duration_s=5,
        bin_width_s=5,
        metric_key="task.energy.per_completed_j",
        metric_version="1.0",
        metric_unit="J/task",
    )
    # Anchor at 12:00:01, tasks at 12:00:06 and 12:00:06.2 → relative 5 and 5.2 → in bin 5-7 (partial)  # noqa: E501
    anchor = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 1, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id="run-m9",
        bundle_id="bundle-m9",
    )
    anchor2 = EventAnchor(
        kind=EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP,
        anchor_time_utc=datetime(2026, 7, 17, 12, 0, 1, tzinfo=UTC),
        source_label="Authored — Manual timestamp",
        run_id="run-m9b",
        bundle_id="bundle-m9b",
    )
    # Adjust tasks to be in partial bin: arrival 7 = anchor+5? Actually created_at 12:00:00, tasks 7 and 7.2 -> absolute 12:00:07, relative to anchor 6 → in 5-7 partial bin  # noqa: E501
    # We already have tasks 2 and 2.2 relative to created_at 2, need them to be relative 6 to anchor: set arrival 7  # noqa: E501
    # Recreate with correct arrival (both tasks in partial bin 5-7)
    tasks_partial_bin = [
        TaskRecord(
            source_file="tasks.csv",
            source_row=1,
            task_id="t1",
            vehicle_id="veh-1",
            task_class=TaskClass.T1,
            arrival_time_s=7,
            deadline_ms=100,
            decision=Decision.V2I,
            completed=True,
            completion_time_s=7.5,
            latency_ms=50,
            energy_j=1.0,
        ),
        TaskRecord(
            source_file="tasks.csv",
            source_row=2,
            task_id="t2",
            vehicle_id="veh-2",
            task_class=TaskClass.T2,
            arrival_time_s=7.2,
            deadline_ms=100,
            decision=Decision.LOCAL,
            completed=True,
            completion_time_s=7.6,
            latency_ms=60,
            energy_j=None,
        ),
    ]
    canonical2 = CanonicalTables(tasks=tasks_partial_bin)
    # Recreate results with correct canonical (frozen dataclass)
    result = BundleValidationResult(
        source=Path("m9"),
        fingerprint="d" * 64,
        manifest=manifest,
        seed=None,
        canonical=canonical2,
        evidence=EvidenceAvailability(tasks="available"),
        insufficient_evidence=None,  # type: ignore
        report=ValidationReport(may_import=True, status=ImportStatus.ACCEPTED),
    )
    result2 = BundleValidationResult(
        source=Path("m9b"),
        fingerprint="e" * 64,
        manifest=manifest2,
        seed=None,
        canonical=canonical2,
        evidence=EvidenceAvailability(tasks="available"),
        insufficient_evidence=None,  # type: ignore
        report=ValidationReport(may_import=True, status=ImportStatus.ACCEPTED),
    )
    report = build_event_aligned_report(
        [(result, anchor), (result2, anchor2)], spec, report_id="m9"
    )
    # Find the bin that is both metric partial and coverage partial
    both = [
        p
        for p in report.metric_points
        if p.status == "partial" and p.coverage_state == CoverageState.PARTIAL
    ]
    assert both, "expected at least one bin both metric PARTIAL and coverage PARTIAL"
    for p in both:
        assert p.value is not None
    # Summary for that run/phase should have bin_count 1? Actually event phase has 2 bins (5 and 2), but our tasks only in second partial bin, first bin empty  # noqa: E501
    # For m9 we check the specific phase where both occurs: event
    summaries = [
        s for s in report.phase_summaries if s.run_id == "run-m9" and s.phase.value == "event"
    ]
    assert summaries
    s = summaries[0]
    # Event has 2 bins, one empty, one partial (both conditions) → bin_count 2, partial_count should be 1 (not 2)  # noqa: E501
    # Our current sample: both points: empty bin (status unavailable coverage complete) + partial bin (partial+partial)  # noqa: E501
    # So bin_count 2, partial 1, empty 1
    assert s.bin_count == 2, f"bin_count {s.bin_count}"
    assert s.partial_count == 1, (
        f"partial_count should be 1 not {s.partial_count} (double count regression)"
    )
    assert s.partial_count <= s.bin_count
    # Also check second run same
    s2 = [s for s in report.phase_summaries if s.run_id == "run-m9b" and s.phase.value == "event"][
        0
    ]
    assert s2.partial_count == 1
    # Invariant across all summaries
    for summ in report.phase_summaries:
        assert 0 <= summ.partial_count <= summ.bin_count, (
            f"partial {summ.partial_count} > bin {summ.bin_count}"
        )
    # Export proof
    csv_s = export_phase_summaries_csv(report)
    assert "run-m9" in csv_s
    # Check partial_count in JSON/canonical
    j = export_report_json(report)
    assert j is not None
    # Fingerprint deterministic
    from traffictwin.event_aligned.exports import export_report_json as ej

    assert ej(report) == j


# Additional partial_count semantics tests
def test_partial_count_metric_only() -> None:  # noqa: N802
    result, anchor = _make_partial_energy_bundle(
        run_id="run-metric-only", bundle_id="bundle-metric-only", arrival_offset=2.0
    )
    result2, anchor2 = _make_partial_energy_bundle(
        run_id="run-metric-only2", bundle_id="bundle-metric-only2", arrival_offset=2.0
    )
    spec = EventAlignedWindowSpec(
        pre_duration_s=5,
        event_duration_s=5,
        post_duration_s=5,
        bin_width_s=5,
        metric_key="task.energy.per_completed_j",
        metric_version="1.0",
        metric_unit="J/task",
    )
    report = build_event_aligned_report(
        [(result, anchor), (result2, anchor2)], spec, report_id="metric-only"
    )
    metric_only = [
        p
        for p in report.metric_points
        if p.status == "partial" and p.coverage_state == CoverageState.COMPLETE
    ]
    assert metric_only, "metric-only partial (complete coverage) expected"
    for p in metric_only:
        assert p.value is not None
    s = [
        s
        for s in report.phase_summaries
        if s.run_id == "run-metric-only" and s.phase.value == "event"
    ][0]
    assert s.partial_count == 1
    assert s.bin_count == 1


def test_partial_count_coverage_only() -> None:  # noqa: N802
    # Coverage partial only: use available metric but bin width leaves partial coverage
    (b1, a1), (b2, a2) = _anchors()
    spec = EventAlignedWindowSpec(
        pre_duration_s=5,
        event_duration_s=7,
        post_duration_s=5,
        bin_width_s=5,
        metric_key="task.completion.rate",
        metric_version="1.0",
        metric_unit="ratio",
    )
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="coverage-only")
    coverage_only = [
        p
        for p in report.metric_points
        if p.coverage_state == CoverageState.PARTIAL and p.status == "available"
    ]
    # May or may not exist depending on data, but if exists check partial_count logic
    if coverage_only:
        # Find summary for that phase
        for p in coverage_only:
            s = [s for s in report.phase_summaries if s.run_id == p.run_id and s.phase == p.phase][
                0
            ]
            assert s.partial_count >= 1
            assert s.partial_count <= s.bin_count
    # Always invariant
    for s in report.phase_summaries:
        assert 0 <= s.partial_count <= s.bin_count


def test_partial_count_neither() -> None:  # noqa: N802
    (b1, a1), (b2, a2) = _anchors()
    spec = _spec()
    report = build_event_aligned_report([(b1, a1), (b2, a2)], spec, report_id="neither")
    neither = [
        p
        for p in report.metric_points
        if p.status == "available" and p.coverage_state == CoverageState.COMPLETE
    ]
    assert neither
    # Pick a phase where all bins are complete+available or empty
    # Just check invariant still
    for s in report.phase_summaries:
        assert 0 <= s.partial_count <= s.bin_count
    # And specific: a complete available point should not contribute to partial
    # Find a run/phase where all points are available+complete and check partial 0
    # Our _spec 10/10/10 with 5 bins gives 6 bins, all complete, some available some unavailable
    # At least one summary should have partial 0
    assert any(s.partial_count == 0 for s in report.phase_summaries)


def test_partial_count_invariant_across_report() -> None:  # noqa: N802
    result, anchor = _make_partial_energy_bundle()
    result2, anchor2 = _make_partial_energy_bundle(run_id="run-inv2", bundle_id="bundle-inv2")
    spec = EventAlignedWindowSpec(
        pre_duration_s=5,
        event_duration_s=5,
        post_duration_s=5,
        bin_width_s=5,
        metric_key="task.energy.per_completed_j",
        metric_version="1.0",
        metric_unit="J/task",
    )
    report = build_event_aligned_report(
        [(result, anchor), (result2, anchor2)], spec, report_id="inv"
    )
    for s in report.phase_summaries:
        assert 0 <= s.partial_count <= s.bin_count, (
            f"{s.run_id} {s.phase} partial {s.partial_count} > bin {s.bin_count}"
        )
