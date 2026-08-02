"""Incremental analytics monitor (post-v1 A-1, design §9 verification list).

Synthetic aggregates only. Tested: idempotent retry, crash-before-commit
recovery, deterministic and order-independent materialisation, changed-bytes
refusal, local-time metadata refusal, unavailable-progression warnings,
missing-is-not-zero reporting, standing inheritance, and the absence of any
raw-data or runner surface.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffictwin.platform.analytics_monitor import (
    AnalyticsMonitorError,
    AnalyticsOperationalPolicy,
    IncrementalAnalyticsMonitor,
    LocalQualityReportStore,
    SourceQualityContext,
    build_operational_quality_report,
    build_quality_report,
    materialise,
    next_scheduled_run,
    read_readiness,
    scheduled_readiness_cells,
)
from traffictwin.platform.bus_prediction import (
    BuildRules,
    LoadedAggregate,
    load_activity_aggregates,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES = BuildRules(min_snapshots_per_session=3, min_interval_support_dates=5)


def _payload(
    session_date: str,
    label: str,
    *,
    live: dict[int | None, list[int]] | None = None,
    speeds: dict[int, tuple[float, int]] | None = None,
) -> dict[str, object]:
    live = live if live is not None else {5: [40, 42, 44]}
    per_snapshot = []
    index = 0
    for hour, values in live.items():
        for value in values:
            per_snapshot.append(
                {
                    "snapshot_id": f"bods_siri_vm-{session_date}-{label}-{index:04d}",
                    "hour_utc": hour if hour is not None else None,
                    "hour_local": hour,
                    "live_vehicle": value,
                }
            )
            index += 1
    progression = [
        {
            "hour_utc": hour,
            "hour_local": hour,
            "segment_count": segments,
            "speed_mps_median": speed,
            "speed_mps_p90": speed * 1.5,
            "vehicles_contributing": max(1, segments // 2),
        }
        for hour, (speed, segments) in (speeds or {}).items()
    ]
    return {
        "record_type": "bods_session_activity_aggregate",
        "schema_version": "1.0",
        "design_reference": "docs/platform/bus_prediction_design.md",
        "session_kind": "scheduled",
        "label": label,
        "session_date_local": session_date,
        "utc_offset_seconds_applied": 0,
        "timezone_note": "fixture",
        "schedule_digest": None,
        "snapshot_count": len(per_snapshot),
        "concurrency_source": "parser_live_vehicle",
        "per_snapshot_live_vehicle": per_snapshot,
        "progression_available": bool(progression),
        "progression_unavailable_reason": None if progression else "NO_PROGRESSION: fixture",
        "hourly_progression": progression,
        "aggregates_only": True,
        "raw_identifiers_published": False,
        "bus_progression_only": True,
        "road_traffic_speed_available": False,
        "session_salt_discarded": True,
    }


def _load_one(tmp_path: Path, name: str, payload: dict[str, object]) -> LoadedAggregate:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return load_activity_aggregates([path])[0]


def _context(
    item: LoadedAggregate,
    *,
    first: str,
    last: str,
    expected: int = 3,
    total_segments: int = 10,
    excluded_segments: int = 0,
    stream: str = "bods-scheduled",
    schema_version: str = "1.0",
) -> SourceQualityContext:
    return SourceQualityContext(
        logical_id=item.logical_id,
        source_sha256=item.sha256,
        source_stream=stream,
        source_schema_version=schema_version,
        first_snapshot_at_utc=datetime.fromisoformat(first),
        last_snapshot_at_utc=datetime.fromisoformat(last),
        expected_snapshot_count=expected,
        progression_segments_total=total_segments,
        progression_segments_excluded=excluded_segments,
    )


def test_apply_is_exactly_once_with_idempotent_replay(tmp_path: Path) -> None:
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    item = _load_one(tmp_path, "a.json", _payload("2026-08-03", "night"))
    first = monitor.apply_increment(item)
    replay = monitor.apply_increment(item)
    assert not first.idempotent_replay
    assert replay.idempotent_replay
    assert replay.materialisation_digest == first.materialisation_digest
    assert first.evidence is False


def test_restart_replays_materialisation_and_logical_digest_state(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    item = _load_one(tmp_path, "a.json", _payload("2026-08-03", "night"))
    first = IncrementalAnalyticsMonitor(checkpoint)
    receipt = first.apply_increment(item)

    replayed = IncrementalAnalyticsMonitor(checkpoint)
    assert replayed.materialisation_digests() == first.materialisation_digests()
    assert replayed.materialisation("2026-08-03/night") is not None
    assert replayed.apply_increment(item).model_copy(update={"idempotent_replay": False}) == receipt

    changed = _load_one(
        tmp_path / "changed",
        "a.json",
        _payload("2026-08-03", "night", live={5: [41, 43, 45]}),
    )
    with pytest.raises(AnalyticsMonitorError) as excinfo:
        replayed.apply_increment(changed)
    assert excinfo.value.code == "DUPLICATE_LOGICAL_SOURCE"


def test_corrupt_or_legacy_commit_cannot_silently_replay(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(
        json.dumps(
            {
                "_kind": "commit",
                "work_key": "0" * 64,
                "logical_id": "2026-08-03/night",
                "materialisation_digest": "1" * 64,
                "analytics_version": "incremental-analytics-1.0",
                "evidence": False,
                "idempotent_replay": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(AnalyticsMonitorError) as excinfo:
        IncrementalAnalyticsMonitor(checkpoint)
    assert excinfo.value.code == "CHECKPOINT_CONFLICT"


def test_crash_before_commit_stays_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    item = _load_one(tmp_path, "a.json", _payload("2026-08-03", "night"))

    import traffictwin.platform.analytics_monitor as module

    def _boom(argument: object) -> object:
        raise RuntimeError("crash mid-computation")

    monkeypatch.setattr(module, "materialise", _boom)
    with pytest.raises(RuntimeError):
        monitor.apply_increment(item)
    monkeypatch.undo()
    # A fresh monitor replays the checkpoint: the reservation is visible and
    # retryable, no commit was written, and the retry succeeds.
    reloaded = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    assert reloaded.retryable_reservations()
    receipt = reloaded.apply_increment(item)
    assert not receipt.idempotent_replay


def test_changed_bytes_under_the_same_logical_id_refuse(tmp_path: Path) -> None:
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    original = _load_one(tmp_path, "a.json", _payload("2026-08-03", "night"))
    monitor.apply_increment(original)
    changed = _load_one(
        tmp_path / "changed",
        "a.json",
        _payload("2026-08-03", "night", live={5: [40, 42, 44], 6: [50, 52, 54]}),
    )
    with pytest.raises(AnalyticsMonitorError) as excinfo:
        monitor.apply_increment(changed)
    assert excinfo.value.code == "DUPLICATE_LOGICAL_SOURCE"


def test_materialisation_is_deterministic_and_order_independent(tmp_path: Path) -> None:
    first_a = _load_one(tmp_path / "one", "a.json", _payload("2026-08-03", "night"))
    first_b = _load_one(
        tmp_path / "one", "b.json", _payload("2026-08-04", "dawn", speeds={6: (4.5, 12)})
    )
    forward = IncrementalAnalyticsMonitor(tmp_path / "forward.jsonl")
    forward.apply_increment(first_a)
    forward.apply_increment(first_b)
    backward = IncrementalAnalyticsMonitor(tmp_path / "backward.jsonl")
    backward.apply_increment(first_b)
    backward.apply_increment(first_a)
    assert forward.materialisation_digests() == backward.materialisation_digests()


def test_the_declared_measures_only_and_the_metric_trap_avoided(tmp_path: Path) -> None:
    item = _load_one(tmp_path, "a.json", _payload("2026-08-03", "night", speeds={5: (3.5, 8)}))
    snapshot = materialise(item)
    row = snapshot.hourly[0]
    assert row.concurrency_median == 42.0
    assert row.concurrency_max == 44
    assert row.progression_speed_mps_median == 3.5
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "analytics_monitor.py").read_text(
        encoding="utf-8"
    )
    # The session-support count never substitutes for concurrency, raw
    # quarantine is never opened, and no salt is created here.
    assert "vehicles_linked_across_snapshots" not in source.replace(
        "``vehicles_linked_across_snapshots``", ""
    )
    assert "quarantine" not in source.replace("raw quarantine", "")
    assert "secrets" not in source


def test_missing_local_time_metadata_refuses(tmp_path: Path) -> None:
    item = _load_one(tmp_path, "a.json", _payload("2026-08-03", "night", live={None: [40, 42]}))
    with pytest.raises(AnalyticsMonitorError) as excinfo:
        materialise(item)
    assert excinfo.value.code == "LOCAL_TIME_METADATA_MISSING"


def test_quality_report_separates_states_and_missing_is_not_zero(
    tmp_path: Path,
) -> None:
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    processed = _load_one(tmp_path / "one", "a.json", _payload("2026-08-03", "night"))
    thin = _load_one(tmp_path / "one", "b.json", _payload("2026-08-04", "dawn", live={6: [50]}))
    unprocessed = _load_one(tmp_path / "one", "c.json", _payload("2026-08-05", "peak"))
    monitor.apply_increment(processed)
    monitor.apply_increment(thin)
    report = build_quality_report(monitor, (processed, thin, unprocessed), RULES)
    assert "2026-08-03/night" in report.accepted
    assert any(observation.rule == "incomplete_session_window" for observation in report.warned)
    assert any(observation.rule == "progression_unavailable" for observation in report.warned)
    assert any("not a zero" in entry for entry in report.not_observed)
    assert report.evidence is False
    assert "operational severity" in report.standing_note


def test_standing_escalation_refuses(tmp_path: Path) -> None:
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    assert monitor.label_output("owner_approved_candidate") == "owner_approved_candidate"
    for stronger in ("admitted", "scientifically_validated", "evidence"):
        with pytest.raises(AnalyticsMonitorError) as excinfo:
            monitor.label_output(stronger)
        assert excinfo.value.code == "STANDING_ESCALATION"


def test_readiness_wraps_the_predictor_report_with_the_standing_note(
    tmp_path: Path,
) -> None:
    item = _load_one(tmp_path, "a.json", _payload("2026-08-03", "night"))
    report = read_readiness((item,), RULES)
    assert report["standing_note"] == "forecast-readiness is not forecast validity"
    assert report["progression_target_available"] is False


def test_owner_selected_operational_policy_is_exact_and_digest_bound() -> None:
    policy = AnalyticsOperationalPolicy()
    assert policy.cadence_minutes == 15
    assert policy.freshness_warning_minutes == 30
    assert policy.freshness_refusal_minutes == 60
    assert policy.completeness_warning_ratio == 0.95
    assert policy.completeness_refusal_ratio == 0.8
    assert policy.exclusion_warning_ratio == 0.1
    assert policy.exclusion_refusal_ratio == 0.25
    assert policy.local_dashboard_alerts
    assert policy.local_report_receipts
    assert not policy.external_notifications
    assert policy.retention == "indefinite"
    assert not policy.automatic_deletion
    assert len(policy.digest()) == 64


def test_schedule_is_strictly_15_minute_and_dst_safe() -> None:
    policy = AnalyticsOperationalPolicy()
    next_cell = next_scheduled_run(datetime(2026, 10, 25, 0, 45, tzinfo=UTC), policy)
    assert next_cell.scheduled_at_utc == datetime(2026, 10, 25, 1, 0, tzinfo=UTC)
    assert next_cell.service_date_local == "2026-10-25"
    assert next_cell.hour_local == 1
    assert next_cell.minute_local == 0
    assert next_cell.utc_offset_seconds == 0
    assert next_cell.fold == 1

    cells = scheduled_readiness_cells(
        datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
        datetime(2026, 10, 25, 1, 15, tzinfo=UTC),
        policy,
    )
    assert [cell.scheduled_at_utc.minute for cell in cells] == [45, 0, 15]
    assert [cell.fold for cell in cells] == [0, 1, 1]


def test_operational_report_applies_freshness_completeness_and_exclusion_policy(
    tmp_path: Path,
) -> None:
    policy = AnalyticsOperationalPolicy()
    fresh = _load_one(tmp_path / "inputs", "fresh.json", _payload("2026-08-03", "fresh"))
    warned = _load_one(
        tmp_path / "inputs",
        "warned.json",
        _payload("2026-08-04", "warned", live={6: list(range(9))}),
    )
    refused = _load_one(
        tmp_path / "inputs",
        "refused.json",
        _payload("2026-08-05", "refused", live={7: list(range(3))}),
    )
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    for item in (fresh, warned, refused):
        monitor.apply_increment(item)
    contexts = (
        _context(
            fresh,
            first="2026-08-06T11:45:00+00:00",
            last="2026-08-06T11:55:00+00:00",
        ),
        _context(
            warned,
            first="2026-08-06T10:45:00+00:00",
            last="2026-08-06T11:15:00+00:00",
            expected=10,
            excluded_segments=2,
        ),
        _context(
            refused,
            first="2026-08-06T09:30:00+00:00",
            last="2026-08-06T10:30:00+00:00",
            expected=4,
            excluded_segments=3,
        ),
    )
    report = build_operational_quality_report(
        monitor,
        (fresh, warned, refused),
        contexts,
        RULES,
        as_of_utc=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
        policy=policy,
    )
    assert report.accepted == (
        fresh.logical_id,
        warned.logical_id,
    )
    assert report.operational_policy_digest == policy.digest()
    assert report.notification_surface == ("local_dashboard", "local_report_receipt")
    assert report.retention_policy == "indefinite; no automatic deletion"
    assert {entry.rule for entry in report.warned} >= {
        "source_stale",
        "session_completeness",
        "progression_exclusion_share",
    }
    assert {entry.rule for entry in report.refused} >= {
        "source_stale",
        "session_completeness",
        "progression_exclusion_share",
    }
    assert all(entry.rule_version == "2.0" for entry in report.informational)


def test_operational_report_refuses_overlap_digest_and_schema_change(
    tmp_path: Path,
) -> None:
    first = _load_one(tmp_path / "inputs", "a.json", _payload("2026-08-03", "a"))
    second = _load_one(tmp_path / "inputs", "b.json", _payload("2026-08-04", "b"))
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    for item in (first, second):
        monitor.apply_increment(item)
    first_context = _context(
        first,
        first="2026-08-06T11:30:00+00:00",
        last="2026-08-06T11:50:00+00:00",
    )
    second_context = _context(
        second,
        first="2026-08-06T11:45:00+00:00",
        last="2026-08-06T11:55:00+00:00",
        schema_version="2.0",
    ).model_copy(update={"source_sha256": "f" * 64})
    report = build_operational_quality_report(
        monitor,
        (first, second),
        (first_context, second_context),
        RULES,
        as_of_utc=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
    )
    rules = {entry.rule for entry in report.refused}
    assert {"session_overlap", "digest_mismatch", "unexpected_schema_version"} <= rules
    assert report.accepted == ()


def test_local_report_store_is_atomic_idempotent_and_indefinite(tmp_path: Path) -> None:
    policy = AnalyticsOperationalPolicy()
    item = _load_one(tmp_path / "inputs", "a.json", _payload("2026-08-03", "night"))
    monitor = IncrementalAnalyticsMonitor(tmp_path / "checkpoint.jsonl")
    monitor.apply_increment(item)
    report = build_operational_quality_report(
        monitor,
        (item,),
        (
            _context(
                item,
                first="2026-08-06T11:45:00+00:00",
                last="2026-08-06T11:55:00+00:00",
            ),
        ),
        RULES,
        as_of_utc=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
        policy=policy,
    )
    store = LocalQualityReportStore(tmp_path / "quality-reports")
    first = store.publish(report, policy)
    replay = store.publish(report, policy)
    assert not first.idempotent_replay
    assert replay.idempotent_replay
    assert replay.report_digest == first.report_digest
    assert store.reports() == (report,)
    assert store.retention_candidates() == ()
    assert not hasattr(store, "delete")
