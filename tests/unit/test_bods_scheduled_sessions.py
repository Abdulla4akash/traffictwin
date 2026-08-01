"""Scheduled BODS session runner (platform slice 1, design §6 test list).

Everything here runs against an injected clock, an injected sleep, and a fake
acquisition callable — nothing opens a network connection, and no real
quarantine is read. The properties asserted are the design's run-once story:
window selection, the skip-late rule, completion-marker idempotency, the
pid-file singleton, ledger contents, and schedule-digest stamping — plus the
retention report's deletes-nothing contract.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import traffictwin.integration.manchester.bods_scheduled_sessions as scheduled_module
from traffictwin.integration.manchester.bods_acquisition import BodsAcquisitionError
from traffictwin.integration.manchester.bods_live_control import BodsLiveControlError
from traffictwin.integration.manchester.bods_scheduled_sessions import (
    AcquiredSnapshot,
    BodsScheduledSessionError,
    ScheduledWindow,
    SessionSchedule,
    WindowOccurrence,
    build_retention_report,
    load_schedule,
    occurrence_resolved,
    plan_next_action,
    run_refusal_tolerant_session_loop,
    run_scheduled_session,
    run_supervisor,
    session_directory,
    supervisor_singleton,
    write_skip_marker,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_SCHEDULE = REPO_ROOT / "docs" / "platform" / "bods_schedule.json"

#: A fixed non-UTC offset so local-time scheduling is exercised as local time.
TZ = timezone(timedelta(hours=1))

_DIGEST = "d" * 64


class FakeClock:
    """One advancing instant serving as both the local and the UTC clock."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def local(self) -> datetime:
        return self.now

    def utc(self) -> datetime:
        return self.now.astimezone(UTC)

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


def _snapshot(number: int) -> AcquiredSnapshot:
    return AcquiredSnapshot(
        snapshot_id=f"bods_siri_vm-fake-{number:04d}",
        records_accepted=10 + number,
        live_vehicle=number,
    )


class ScriptedAcquire:
    """Fake acquisition: each event is an accepted snapshot or a refusal.

    A refusal event ``(error, quarantine_id)`` mimics the real boundary by
    leaving the rejected bytes' quarantine id behind before raising; an
    accepted snapshot's id also appears in quarantine, exactly as promotion
    does.
    """

    def __init__(self, events: list[AcquiredSnapshot | tuple[Exception, str]]) -> None:
        self.events = list(events)
        self.quarantine: set[str] = set()
        self.calls = 0

    def __call__(self) -> AcquiredSnapshot:
        self.calls += 1
        event = self.events.pop(0)
        if isinstance(event, tuple):
            error, quarantine_id = event
            self.quarantine.add(quarantine_id)
            raise error
        self.quarantine.add(event.snapshot_id)
        return event

    def quarantine_ids(self) -> set[str]:
        return set(self.quarantine)


def _silent(message: str) -> None:
    del message


def _never_resolved(occurrence: WindowOccurrence) -> bool:
    del occurrence
    return False


def _schedule(
    *,
    windows: tuple[tuple[str, str, int], ...] = (("dawn", "05:30", 2), ("pm_peak", "16:30", 3)),
    late_tolerance_seconds: int = 300,
    retention_report_days: int = 14,
) -> SessionSchedule:
    return SessionSchedule(
        sessions=tuple(
            ScheduledWindow(label=label, start_local=start, snapshots=count)
            for label, start, count in windows
        ),
        interval_seconds=65,
        late_tolerance_seconds=late_tolerance_seconds,
        retention_report_days=retention_report_days,
    )


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "sessions": [
            {"label": "dawn", "start_local": "05:30", "snapshots": 2},
            {"label": "pm_peak", "start_local": "16:30", "snapshots": 3},
        ],
        "interval_seconds": 65,
        "late_tolerance_seconds": 300,
        "retention_report_days": 14,
    }


# --- schedule loading -------------------------------------------------------


def test_committed_schedule_matches_the_design() -> None:
    loaded = load_schedule(COMMITTED_SCHEDULE)
    windows = {
        (window.label, window.start_local, window.snapshots) for window in loaded.schedule.sessions
    }
    assert windows == {
        ("night", "23:30", 15),
        ("dawn", "05:30", 52),
        ("am_peak", "08:00", 52),
        ("pm_peak", "16:30", 85),
    }
    assert loaded.schedule.interval_seconds == 65
    assert loaded.digest == hashlib.sha256(COMMITTED_SCHEDULE.read_bytes()).hexdigest()


def test_schedule_refuses_invalid_shapes(tmp_path: Path) -> None:
    mutations: list[Callable[[dict[str, object]], None]] = []

    def _interval_too_small(payload: dict[str, object]) -> None:
        payload["interval_seconds"] = 60

    def _duplicate_labels(payload: dict[str, object]) -> None:
        payload["sessions"] = [
            {"label": "dawn", "start_local": "05:30", "snapshots": 2},
            {"label": "dawn", "start_local": "06:30", "snapshots": 2},
        ]

    def _bad_start(payload: dict[str, object]) -> None:
        payload["sessions"] = [{"label": "dawn", "start_local": "24:99", "snapshots": 2}]

    def _empty_sessions(payload: dict[str, object]) -> None:
        payload["sessions"] = []

    mutations = [_interval_too_small, _duplicate_labels, _bad_start, _empty_sessions]
    for index, mutate in enumerate(mutations):
        payload = _valid_payload()
        mutate(payload)
        path = tmp_path / f"schedule-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(BodsScheduledSessionError) as excinfo:
            load_schedule(path)
        assert excinfo.value.code == "SCHEDULE_INVALID"


def test_schedule_missing_file_is_a_typed_refusal(tmp_path: Path) -> None:
    with pytest.raises(BodsScheduledSessionError) as excinfo:
        load_schedule(tmp_path / "absent.json")
    assert excinfo.value.code == "SCHEDULE_UNREADABLE"


# --- window selection (pure planning) ---------------------------------------


def test_plan_sleeps_until_the_next_future_window() -> None:
    plan = plan_next_action(_schedule(), datetime(2026, 8, 1, 5, 0, tzinfo=TZ), _never_resolved)
    assert plan.run_now is None
    assert plan.late == ()
    assert plan.sleep_until == datetime(2026, 8, 1, 5, 30, tzinfo=TZ)


def test_plan_runs_a_window_within_the_late_tolerance() -> None:
    plan = plan_next_action(_schedule(), datetime(2026, 8, 1, 5, 33, tzinfo=TZ), _never_resolved)
    assert plan.run_now is not None
    assert plan.run_now.window.label == "dawn"
    assert plan.run_now.session_date == date(2026, 8, 1)
    assert plan.late == ()


def test_plan_skips_a_window_past_tolerance_and_never_runs_it_late() -> None:
    plan = plan_next_action(_schedule(), datetime(2026, 8, 1, 6, 0, tzinfo=TZ), _never_resolved)
    assert plan.run_now is None
    assert [occurrence.window.label for occurrence in plan.late] == ["dawn"]
    assert plan.sleep_until == datetime(2026, 8, 1, 16, 30, tzinfo=TZ)


def test_plan_ignores_resolved_windows_and_rolls_to_tomorrow() -> None:
    today = date(2026, 8, 1)

    def _today_resolved(occurrence: WindowOccurrence) -> bool:
        return occurrence.session_date == today

    plan = plan_next_action(_schedule(), datetime(2026, 8, 1, 20, 0, tzinfo=TZ), _today_resolved)
    assert plan.run_now is None
    assert plan.late == ()
    assert plan.sleep_until == datetime(2026, 8, 2, 5, 30, tzinfo=TZ)


def test_plan_ledgers_every_unresolved_past_window() -> None:
    plan = plan_next_action(_schedule(), datetime(2026, 8, 1, 20, 0, tzinfo=TZ), _never_resolved)
    assert {occurrence.window.label for occurrence in plan.late} == {"dawn", "pm_peak"}
    assert plan.sleep_until == datetime(2026, 8, 2, 5, 30, tzinfo=TZ)


# --- the shared refusal-tolerant loop ---------------------------------------


def test_session_loop_records_refusals_exactly_like_the_attended_ledger() -> None:
    long_message = "x" * 400
    acquire = ScriptedAcquire(
        [
            _snapshot(1),
            (BodsAcquisitionError("PARSE_REJECTED", long_message), "bods_siri_vm-rejected-0002"),
            _snapshot(3),
        ]
    )
    sleeps: list[float] = []
    result = run_refusal_tolerant_session_loop(
        snapshots=3,
        interval_seconds=65,
        acquire=acquire,
        quarantine_ids=acquire.quarantine_ids,
        utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
        sleep=sleeps.append,
        report=_silent,
    )
    assert result.accepted_snapshot_ids == ("bods_siri_vm-fake-0001", "bods_siri_vm-fake-0003")
    assert not result.ended_by_refusal_limit
    assert len(result.refusals) == 1
    refusal = result.refusals[0]
    assert refusal.attempt == 2
    assert refusal.error == f"PARSE_REJECTED: {long_message}"[:300]
    assert len(refusal.error) == 300
    assert refusal.quarantined_but_not_promoted == ("bods_siri_vm-rejected-0002",)
    payload = refusal.as_payload()
    assert list(payload.keys()) == [
        "attempt",
        "attempted_at_utc",
        "error",
        "quarantined_but_not_promoted",
    ]
    assert sleeps == [65.0, 65.0]


def test_session_loop_stops_at_eight_consecutive_refusals() -> None:
    events: list[AcquiredSnapshot | tuple[Exception, str]] = [
        (BodsAcquisitionError("PARSE_REJECTED", "refused"), f"bods_siri_vm-rej-{n:04d}")
        for n in range(9)
    ]
    acquire = ScriptedAcquire(events)
    result = run_refusal_tolerant_session_loop(
        snapshots=20,
        interval_seconds=65,
        acquire=acquire,
        quarantine_ids=acquire.quarantine_ids,
        utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
        sleep=lambda seconds: None,
        report=_silent,
    )
    assert result.ended_by_refusal_limit
    assert len(result.refusals) == 8
    assert acquire.calls == 8
    assert result.accepted == ()


def test_session_loop_retries_refresh_too_soon_once_without_a_refusal() -> None:
    acquire = ScriptedAcquire(
        [
            (BodsLiveControlError("REFRESH_TOO_SOON", "interval not elapsed"), ""),
            _snapshot(1),
            _snapshot(2),
        ]
    )
    sleeps: list[float] = []
    result = run_refusal_tolerant_session_loop(
        snapshots=2,
        interval_seconds=65,
        acquire=acquire,
        quarantine_ids=acquire.quarantine_ids,
        utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
        sleep=sleeps.append,
        report=_silent,
    )
    assert result.refusals == ()
    assert len(result.accepted) == 2
    assert sleeps[0] == 30.0
    assert sleeps[1:] == [65.0]


# --- one scheduled session --------------------------------------------------


def _occurrence(schedule: SessionSchedule, day: date, index: int = 0) -> WindowOccurrence:
    return WindowOccurrence(session_date=day, window=schedule.sessions[index])


def test_scheduled_session_writes_the_marker_before_fallible_post_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken_extract(*args: object, **kwargs: object) -> object:
        raise RuntimeError("post-step boom")

    monkeypatch.setattr(scheduled_module, "extract_session_observations", _broken_extract)
    schedule = _schedule()
    acquire = ScriptedAcquire([_snapshot(1), _snapshot(2)])
    outcome = run_scheduled_session(
        tmp_path,
        _occurrence(schedule, date(2026, 8, 1)),
        schedule,
        _DIGEST,
        acquire=acquire,
        utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
        sleep=lambda seconds: None,
        report=_silent,
    )
    directory = outcome.marker_path.parent
    assert outcome.marker_path.is_file()
    assert not outcome.measurement_written
    assert any(error.startswith("cadence_measurement:") for error in outcome.post_step_errors)
    assert not (directory / "cadence_measurement.json").exists()
    ledger = json.loads((directory / "refusal_ledger.json").read_text(encoding="utf-8"))
    assert ledger["schedule_digest"] == _DIGEST
    record = json.loads((directory / "session_record.json").read_text(encoding="utf-8"))
    assert record["post_step_errors"] == list(outcome.post_step_errors)
    marker = json.loads(outcome.marker_path.read_text(encoding="utf-8"))
    assert marker["triggered_by"] == "schedule"
    assert marker["schedule_digest"] == _DIGEST
    assert marker["accepted_snapshot_ids"] == [
        "bods_siri_vm-fake-0001",
        "bods_siri_vm-fake-0002",
    ]


def test_scheduled_session_full_post_processing_with_a_fresh_salt_per_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    salts: list[bytes] = []

    def _fake_extract(
        workspace_root: object, snapshot_id: str, *, session_salt: bytes
    ) -> SimpleNamespace:
        salts.append(session_salt)
        return SimpleNamespace(
            observations_extracted=3,
            activities_seen=4,
            malformed_skipped=1,
            snapshot_id=snapshot_id,
        )

    def _fake_measure(results: list[SimpleNamespace]) -> dict[str, int]:
        return {"snapshots": len(results)}

    def _fake_to_json(measurement: dict[str, int]) -> str:
        return json.dumps({"stub_measurement": measurement}, sort_keys=True)

    monkeypatch.setattr(scheduled_module, "extract_session_observations", _fake_extract)
    monkeypatch.setattr(scheduled_module, "measure_session_cadence", _fake_measure)
    monkeypatch.setattr(scheduled_module, "measurement_to_json", _fake_to_json)

    schedule = _schedule()
    for day in (date(2026, 8, 1), date(2026, 8, 2)):
        acquire = ScriptedAcquire([_snapshot(1), _snapshot(2)])
        outcome = run_scheduled_session(
            tmp_path,
            _occurrence(schedule, day),
            schedule,
            _DIGEST,
            acquire=acquire,
            utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
            sleep=lambda seconds: None,
            report=_silent,
        )
        assert outcome.measurement_written
        assert outcome.post_step_errors == ()
        directory = outcome.marker_path.parent
        measurement = json.loads(
            (directory / "cadence_measurement.json").read_text(encoding="utf-8")
        )
        assert measurement == {"stub_measurement": {"snapshots": 2}}
        record = json.loads((directory / "session_record.json").read_text(encoding="utf-8"))
        assert record["triggered_by"] == "schedule"
        assert record["schedule_digest"] == _DIGEST
        assert record["measurement_written"] is True

    # One salt per extraction, identical within a session, fresh across
    # sessions, never trivially short.
    assert len(salts) == 4
    assert salts[0] == salts[1]
    assert salts[2] == salts[3]
    assert salts[0] != salts[2]
    assert all(len(salt) >= 16 for salt in salts)


def test_scheduled_session_skips_measurement_below_two_accepted_snapshots(
    tmp_path: Path,
) -> None:
    schedule = _schedule(windows=(("smoke", "05:30", 1),))
    acquire = ScriptedAcquire([_snapshot(1)])
    outcome = run_scheduled_session(
        tmp_path,
        _occurrence(schedule, date(2026, 8, 1)),
        schedule,
        _DIGEST,
        acquire=acquire,
        utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
        sleep=lambda seconds: None,
        report=_silent,
    )
    assert outcome.marker_path.is_file()
    assert not outcome.measurement_written
    assert outcome.measurement_skipped_reason == "fewer than two accepted snapshots"
    assert not (outcome.marker_path.parent / "cadence_measurement.json").exists()


def test_scheduled_session_refuses_to_run_a_completed_window_again(tmp_path: Path) -> None:
    schedule = _schedule()
    occurrence = _occurrence(schedule, date(2026, 8, 1))
    acquire = ScriptedAcquire([_snapshot(1), _snapshot(2)])
    run_scheduled_session(
        tmp_path,
        occurrence,
        schedule,
        _DIGEST,
        acquire=acquire,
        utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
        sleep=lambda seconds: None,
        report=_silent,
    )
    with pytest.raises(BodsScheduledSessionError) as excinfo:
        run_scheduled_session(
            tmp_path,
            occurrence,
            schedule,
            _DIGEST,
            acquire=acquire,
            utc_now=lambda: datetime(2026, 8, 1, 5, 30, tzinfo=UTC),
            sleep=lambda seconds: None,
            report=_silent,
        )
    assert excinfo.value.code == "WINDOW_ALREADY_COMPLETED"


# --- the pid-file singleton -------------------------------------------------


def test_singleton_refuses_a_second_supervisor_and_cleans_up(tmp_path: Path) -> None:
    with supervisor_singleton(tmp_path) as pid_path:
        assert pid_path.read_text(encoding="utf-8").strip() == str(os.getpid())
        with (
            pytest.raises(BodsScheduledSessionError) as excinfo,
            supervisor_singleton(tmp_path),
        ):
            pytest.fail("a second supervisor must never start")
        assert excinfo.value.code == "SUPERVISOR_ALREADY_RUNNING"
        assert pid_path.read_text(encoding="utf-8").strip() == str(os.getpid())
    assert not pid_path.exists()


def test_singleton_reclaims_a_stale_pid_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_path = tmp_path / "manchester" / "scheduled" / "supervisor.pid"
    pid_path.parent.mkdir(parents=True)
    pid_path.write_text("999999\n", encoding="utf-8")
    monkeypatch.setattr(scheduled_module, "_pid_alive", lambda pid: False)
    with supervisor_singleton(tmp_path) as reclaimed:
        assert reclaimed.read_text(encoding="utf-8").strip() == str(os.getpid())
    assert not pid_path.exists()


def test_pid_alive_probe() -> None:
    assert scheduled_module._pid_alive(os.getpid())
    assert not scheduled_module._pid_alive(-5)


# --- the supervisor loop ----------------------------------------------------


def _write_schedule_file(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_supervisor_runs_a_window_once_and_never_again(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    schedule_path = tmp_path / "schedule.json"
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "sessions": [{"label": "smoke", "start_local": "05:30", "snapshots": 2}],
        "interval_seconds": 65,
        "late_tolerance_seconds": 300,
        "retention_report_days": 14,
    }
    digest = _write_schedule_file(schedule_path, payload)
    clock = FakeClock(datetime(2026, 8, 1, 5, 29, tzinfo=TZ))
    acquire = ScriptedAcquire([_snapshot(1), _snapshot(2)])
    sessions = run_supervisor(
        workspace,
        schedule_path,
        acquire=acquire,
        local_now=clock.local,
        utc_now=clock.utc,
        sleep=clock.advance,
        report=_silent,
        max_iterations=10,
        max_sessions=1,
    )
    assert sessions == 1
    assert acquire.calls == 2
    occurrence = WindowOccurrence(
        session_date=date(2026, 8, 1),
        window=ScheduledWindow(label="smoke", start_local="05:30", snapshots=2),
    )
    directory = session_directory(workspace, occurrence)
    marker = json.loads((directory / "completed.json").read_text(encoding="utf-8"))
    assert marker["schedule_digest"] == digest
    assert marker["triggered_by"] == "schedule"
    assert marker["accepted_snapshot_ids"] == [
        "bods_siri_vm-fake-0001",
        "bods_siri_vm-fake-0002",
    ]
    assert not (workspace / "manchester" / "scheduled" / "supervisor.pid").exists()

    # Completion-marker idempotency: a fresh supervisor never re-runs it.
    again = run_supervisor(
        workspace,
        schedule_path,
        acquire=acquire,
        local_now=clock.local,
        utc_now=clock.utc,
        sleep=clock.advance,
        report=_silent,
        max_iterations=3,
        max_sessions=1,
    )
    assert again == 0
    assert acquire.calls == 2


def test_supervisor_skip_ledgers_a_late_window_without_acquiring(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    schedule_path = tmp_path / "schedule.json"
    digest = _write_schedule_file(
        schedule_path,
        {
            "schema_version": "1.0",
            "sessions": [{"label": "dawn", "start_local": "05:30", "snapshots": 2}],
            "interval_seconds": 65,
            "late_tolerance_seconds": 300,
            "retention_report_days": 14,
        },
    )
    clock = FakeClock(datetime(2026, 8, 1, 6, 0, tzinfo=TZ))
    acquire = ScriptedAcquire([])
    sessions = run_supervisor(
        workspace,
        schedule_path,
        acquire=acquire,
        local_now=clock.local,
        utc_now=clock.utc,
        sleep=clock.advance,
        report=_silent,
        max_iterations=1,
    )
    assert sessions == 0
    assert acquire.calls == 0
    occurrence = WindowOccurrence(
        session_date=date(2026, 8, 1),
        window=ScheduledWindow(label="dawn", start_local="05:30", snapshots=2),
    )
    skip = json.loads(
        (session_directory(workspace, occurrence) / "skipped.json").read_text(encoding="utf-8")
    )
    assert skip["reason"] == "late"
    assert skip["schedule_digest"] == digest
    assert "never run late" in skip["skip_semantics"]
    assert occurrence_resolved(workspace, occurrence)


def test_skip_marker_blocks_planning(tmp_path: Path) -> None:
    schedule = _schedule()
    occurrence = _occurrence(schedule, date(2026, 8, 1))
    write_skip_marker(
        tmp_path,
        occurrence,
        schedule_digest=_DIGEST,
        decided_at=datetime(2026, 8, 1, 6, 0, tzinfo=TZ),
    )
    plan = plan_next_action(
        schedule,
        datetime(2026, 8, 1, 6, 0, tzinfo=TZ),
        lambda item: occurrence_resolved(tmp_path, item),
    )
    assert plan.late == ()
    assert plan.run_now is None


# --- the retention report ---------------------------------------------------


def _fake_completed_session(
    workspace: Path,
    day: str,
    label: str,
    finished_at_utc: str,
    snapshot_ids: list[str],
    *,
    with_measurement: bool,
) -> None:
    directory = workspace / "manchester" / "scheduled" / day / label
    directory.mkdir(parents=True)
    (directory / "completed.json").write_text(
        json.dumps(
            {
                "record_type": "scheduled_bods_session_completion",
                "session_date": day,
                "label": label,
                "finished_at_utc": finished_at_utc,
                "accepted_snapshot_ids": snapshot_ids,
            }
        ),
        encoding="utf-8",
    )
    if with_measurement:
        (directory / "cadence_measurement.json").write_text("{}", encoding="utf-8")


def test_retention_report_lists_only_eligible_sessions_and_deletes_nothing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    _fake_completed_session(
        workspace,
        "2026-08-01",
        "dawn",
        "2026-08-01T06:00:00+00:00",
        ["bods_siri_vm-old-0001", "bods_siri_vm-old-0002"],
        with_measurement=True,
    )
    _fake_completed_session(
        workspace,
        "2026-08-20",
        "dawn",
        "2026-08-20T06:00:00+00:00",
        ["bods_siri_vm-young-0001"],
        with_measurement=True,
    )
    _fake_completed_session(
        workspace,
        "2026-08-02",
        "dawn",
        "2026-08-02T06:00:00+00:00",
        ["bods_siri_vm-nomeas-0001"],
        with_measurement=False,
    )
    quarantine = workspace / "quarantine"
    for present in ("bods_siri_vm-old-0001", "bods_siri_vm-young-0001", "bods_siri_vm-nomeas-0001"):
        (quarantine / present).mkdir(parents=True)

    report = build_retention_report(
        workspace,
        _schedule(retention_report_days=14),
        utc_now=lambda: datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    sessions = report["eligible_sessions"]
    assert isinstance(sessions, list)
    assert len(sessions) == 1
    assert sessions[0]["label"] == "dawn"
    assert sessions[0]["session_date"] == "2026-08-01"
    # Only the id still present in quarantine is listed; the missing one is not.
    assert sessions[0]["prunable_snapshot_ids"] == ["bods_siri_vm-old-0001"]
    assert report["eligible_snapshot_count"] == 1
    semantics = report["deletion_semantics"]
    assert isinstance(semantics, str)
    assert "never automatic" in semantics
    # Deletes nothing — every quarantine directory is untouched.
    for present in ("bods_siri_vm-old-0001", "bods_siri_vm-young-0001", "bods_siri_vm-nomeas-0001"):
        assert (quarantine / present).is_dir()
