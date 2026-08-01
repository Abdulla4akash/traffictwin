"""Scheduled BODS observation sessions (platform slice 1, decision P-D2).

Implements ``docs/platform/bods_scheduled_runner_design.md``: a long-lived
supervisor turns the four hand-run observation windows into a continuous
archive. The accepted acquisition boundary is inherited verbatim and none of
it is relaxed — >= 60 s between requests, one request in flight at a time
(the existing ``coordinated_bods_live_refresh`` lock, reached through the
injected acquisition callable), quarantine-with-manifest before any read,
a per-session in-process salt discarded at session end, aggregate-only
outputs, and the attended runner's refusal semantics reused as one shared
implementation rather than a second copy.

Run-once is guarded three ways, because this project's own Sparse-64
homecoming produced two launchd-relaunch deviations (a completed step
repeated 147 times, then — after the supervisor was repaired — one more
repeat, because the terminal record was written *after* a fallible cleanup
step):

1. a pid-file singleton — a second supervisor refuses to start;
2. a per-(date, window) completion marker written atomically by the session
   writer itself, **before** any fallible post-step, so an interruption can
   only lose post-processing (recoverable from quarantine), never the
   ran-once fact;
3. a window already past its start (beyond the declared tolerance) is
   skipped and ledgered, never run late — late data would silently shift the
   density point the window exists to measure.

Retention in this slice is a *report only*. The accepted retention boundary
(``bods_retention``) makes deletion of private raw snapshots owner-confirmed
and never automatic; an unattended supervisor deleting quarantine bytes would
relax that boundary, so this module surfaces which scheduled-session
snapshots are prune-eligible and deletes nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time as time_module
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from traffictwin.integration.manchester.bods_acquisition import BodsAcquisitionError
from traffictwin.integration.manchester.bods_live_control import BodsLiveControlError
from traffictwin.integration.manchester.bods_session_identity import (
    SessionExtractionResult,
    extract_session_observations,
    measure_session_cadence,
    measurement_to_json,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.snapshots import QUARANTINE_DIRECTORY_NAME

#: The committed design this module implements; stamped into every record.
DESIGN_REFERENCE = "docs/platform/bods_scheduled_runner_design.md"

#: Consecutive refusals that end a session — the attended runner's limit.
CONSECUTIVE_REFUSAL_LIMIT = 8

COMPLETION_MARKER_NAME = "completed.json"
SKIP_MARKER_NAME = "skipped.json"
CADENCE_MEASUREMENT_NAME = "cadence_measurement.json"
REFUSAL_LEDGER_NAME = "refusal_ledger.json"
SESSION_RECORD_NAME = "session_record.json"
RETENTION_REPORT_NAME = "retention_report.json"
SUPERVISOR_PID_NAME = "supervisor.pid"

_MAX_SCHEDULE_BYTES = 64 * 1024
_ERROR_TEXT_LIMIT = 300
_REFRESH_TOO_SOON_WAIT_SECONDS = 30.0
_SUPERVISOR_SLEEP_CHUNK_SECONDS = 60.0
_BODS_QUARANTINE_PREFIX = "bods_siri_vm-"

_REFUSAL_SEMANTICS = (
    "every refusal is fail-closed: the feed was never promoted and its bytes stay in "
    "quarantine. This runner continues the window instead of discarding it; it does not "
    "weaken, retry, or bypass the MAN-05 parser, which is lead-owned and untouched."
)
_SKIP_SEMANTICS = (
    "a window past its start is never run late: late data would silently shift the "
    "density point the window exists to measure, so the gap is recorded instead."
)
_MARKER_SEMANTICS = (
    "written atomically by the session writer before any fallible post-step; an "
    "interruption after this point can only lose post-processing (recoverable from "
    "quarantine), never the ran-once fact."
)
_RETENTION_SEMANTICS = (
    "report only: the accepted bods_retention boundary makes deletion of private raw "
    "snapshots owner-confirmed and never automatic, so this supervisor deletes nothing. "
    "Apply retention through the owner-invoked confirmed flow."
)


class BodsScheduledSessionError(RuntimeError):
    """Typed, display-safe scheduling refusal; never carries credentials."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ScheduledWindow(ManchesterSnapshotModel):
    """One daily observation window; the schedule is data, not code."""

    label: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    start_local: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    snapshots: int = Field(ge=1, le=120)

    def start_time(self) -> time:
        hour, minute = self.start_local.split(":")
        return time(int(hour), int(minute))


class SessionSchedule(ManchesterSnapshotModel):
    """The committed daily schedule mirroring the four measured density points."""

    schema_version: Literal["1.0"] = "1.0"
    sessions: tuple[ScheduledWindow, ...] = Field(min_length=1)
    interval_seconds: int = Field(ge=61, le=600)
    late_tolerance_seconds: int = Field(default=300, ge=60, le=1800)
    retention_report_days: int = Field(default=14, ge=1, le=365)

    @model_validator(mode="after")
    def validate_windows(self) -> SessionSchedule:
        labels = [window.label for window in self.sessions]
        if len(set(labels)) != len(labels):
            raise ValueError("window labels must be unique")
        starts = [window.start_local for window in self.sessions]
        if len(set(starts)) != len(starts):
            raise ValueError("window start times must be unique")
        return self


@dataclass(frozen=True)
class LoadedSchedule:
    """A validated schedule bound to the digest of its exact committed bytes."""

    schedule: SessionSchedule
    digest: str
    path: Path


def load_schedule(path: Path) -> LoadedSchedule:
    """Read, digest, and validate a schedule file; refusals are typed."""

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BodsScheduledSessionError(
            "SCHEDULE_UNREADABLE", f"schedule file {path.name} could not be read"
        ) from exc
    if len(raw) > _MAX_SCHEDULE_BYTES:
        raise BodsScheduledSessionError(
            "SCHEDULE_TOO_LARGE", f"schedule file exceeds {_MAX_SCHEDULE_BYTES} bytes"
        )
    digest = hashlib.sha256(raw).hexdigest()
    try:
        schedule = SessionSchedule.model_validate_json(raw)
    except ValidationError as exc:
        raise BodsScheduledSessionError(
            "SCHEDULE_INVALID", f"schedule file {path.name} failed validation"
        ) from exc
    return LoadedSchedule(schedule=schedule, digest=digest, path=path)


@dataclass(frozen=True)
class WindowOccurrence:
    """One (date, window) pair — the unit the run-once guards protect."""

    session_date: date
    window: ScheduledWindow

    def start_at(self, zone: tzinfo | None) -> datetime:
        return datetime.combine(self.session_date, self.window.start_time(), tzinfo=zone)


def scheduled_root(workspace_root: Path) -> Path:
    """Scheduled outputs live apart from the attended sessions' paths."""

    return workspace_root / "manchester" / "scheduled"


def session_directory(workspace_root: Path, occurrence: WindowOccurrence) -> Path:
    return (
        scheduled_root(workspace_root)
        / occurrence.session_date.isoformat()
        / occurrence.window.label
    )


def occurrence_resolved(workspace_root: Path, occurrence: WindowOccurrence) -> bool:
    """A window with a completion or skip marker is never touched again."""

    directory = session_directory(workspace_root, occurrence)
    return (directory / COMPLETION_MARKER_NAME).exists() or (directory / SKIP_MARKER_NAME).exists()


@dataclass(frozen=True)
class SupervisorPlan:
    """What one supervisor wake-up should do, decided by pure calendar logic."""

    late: tuple[WindowOccurrence, ...]
    run_now: WindowOccurrence | None
    sleep_until: datetime | None


def plan_next_action(
    schedule: SessionSchedule,
    now: datetime,
    is_resolved: Callable[[WindowOccurrence], bool],
) -> SupervisorPlan:
    """Classify today's and tomorrow's windows as late, due, or future.

    Only today and tomorrow are considered: older unresolved windows are the
    "machine was asleep" case, and the design's answer to those is a silent
    gap surfaced by the inventory page, not retroactive markers.
    """

    today = now.date()
    late: list[WindowOccurrence] = []
    due: list[WindowOccurrence] = []
    future: list[WindowOccurrence] = []
    for day in (today, today + timedelta(days=1)):
        for window in schedule.sessions:
            occurrence = WindowOccurrence(session_date=day, window=window)
            if is_resolved(occurrence):
                continue
            lateness = (now - occurrence.start_at(now.tzinfo)).total_seconds()
            if lateness < 0:
                future.append(occurrence)
            elif lateness <= schedule.late_tolerance_seconds:
                due.append(occurrence)
            else:
                late.append(occurrence)
    run_now = min(due, key=lambda item: item.start_at(now.tzinfo)) if due else None
    sleep_until: datetime | None = None
    if run_now is None and future:
        sleep_until = min(item.start_at(now.tzinfo) for item in future)
    return SupervisorPlan(late=tuple(late), run_now=run_now, sleep_until=sleep_until)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    """Write-then-rename so the file either exists complete or not at all."""

    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(serialized, encoding="utf-8")
    os.replace(temporary, path)


def write_skip_marker(
    workspace_root: Path,
    occurrence: WindowOccurrence,
    *,
    schedule_digest: str,
    decided_at: datetime,
    reason: str = "late",
) -> Path:
    """Ledger a window that will never run; the marker also blocks re-runs."""

    path = session_directory(workspace_root, occurrence) / SKIP_MARKER_NAME
    _write_json_atomic(
        path,
        {
            "record_type": "scheduled_bods_session_skip",
            "design_reference": DESIGN_REFERENCE,
            "session_date": occurrence.session_date.isoformat(),
            "label": occurrence.window.label,
            "scheduled_start_local": occurrence.window.start_local,
            "snapshots_requested": occurrence.window.snapshots,
            "reason": reason,
            "decided_at": decided_at.isoformat(),
            "schedule_digest": schedule_digest,
            "skip_semantics": _SKIP_SEMANTICS,
        },
    )
    return path


@dataclass(frozen=True)
class AcquiredSnapshot:
    """The aggregate-only summary of one accepted snapshot."""

    snapshot_id: str
    records_accepted: int
    live_vehicle: int


@dataclass(frozen=True)
class SessionRefusal:
    """One fail-closed refusal, recorded exactly as the attended ledger does."""

    attempt: int
    attempted_at_utc: str
    error: str
    quarantined_but_not_promoted: tuple[str, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "attempted_at_utc": self.attempted_at_utc,
            "error": self.error,
            "quarantined_but_not_promoted": list(self.quarantined_but_not_promoted),
        }


@dataclass(frozen=True)
class SessionLoopResult:
    """Everything one snapshot loop produced, for either kind of caller."""

    accepted: tuple[AcquiredSnapshot, ...]
    refusals: tuple[SessionRefusal, ...]
    started_at_utc: str
    finished_at_utc: str
    ended_by_refusal_limit: bool

    @property
    def accepted_snapshot_ids(self) -> tuple[str, ...]:
        return tuple(snapshot.snapshot_id for snapshot in self.accepted)


def list_bods_quarantine_ids(workspace_root: Path) -> set[str]:
    """Names of quarantined BODS snapshots, for refusal-diff bookkeeping."""

    directory = workspace_root / QUARANTINE_DIRECTORY_NAME
    if not directory.is_dir():
        return set()
    return {
        path.name for path in directory.iterdir() if path.name.startswith(_BODS_QUARANTINE_PREFIX)
    }


def run_refusal_tolerant_session_loop(
    *,
    snapshots: int,
    interval_seconds: int,
    acquire: Callable[[], AcquiredSnapshot],
    quarantine_ids: Callable[[], set[str]],
    utc_now: Callable[[], datetime],
    sleep: Callable[[float], None],
    report: Callable[[str], None],
    consecutive_refusal_limit: int = CONSECUTIVE_REFUSAL_LIMIT,
) -> SessionLoopResult:
    """The attended runner's session loop as one shared implementation.

    Semantics preserved exactly: a fail-closed refusal is recorded and the
    session continues; a ``REFRESH_TOO_SOON`` coordination refusal waits 30 s
    and retries once; the session ends after ``consecutive_refusal_limit``
    refusals in a row; the interval sleep runs between attempts, not after
    the last one.
    """

    accepted: list[AcquiredSnapshot] = []
    refusals: list[SessionRefusal] = []
    consecutive = 0
    ended_by_refusal_limit = False
    started_at = utc_now().isoformat()
    for index in range(snapshots):
        before = quarantine_ids()
        attempted_at = utc_now().isoformat()
        outcome: AcquiredSnapshot | None = None
        refusal_error: Exception | None = None
        try:
            outcome = acquire()
        except BodsLiveControlError as error:
            if error.code == "REFRESH_TOO_SOON":
                report("  interval not yet elapsed; waiting 30 s and retrying once")
                sleep(_REFRESH_TOO_SOON_WAIT_SECONDS)
                try:
                    outcome = acquire()
                except (BodsLiveControlError, BodsAcquisitionError) as retry_error:
                    refusal_error = retry_error
            else:
                refusal_error = error
        except BodsAcquisitionError as error:
            refusal_error = error
        if outcome is None:
            consecutive += 1
            refusals.append(
                SessionRefusal(
                    attempt=index + 1,
                    attempted_at_utc=attempted_at,
                    error=str(refusal_error)[:_ERROR_TEXT_LIMIT],
                    quarantined_but_not_promoted=tuple(sorted(quarantine_ids() - before)),
                )
            )
            report(f"  [{index + 1}] refused: {refusal_error}")
            if consecutive >= consecutive_refusal_limit:
                report("  refusal limit reached; ending session")
                ended_by_refusal_limit = True
                break
        else:
            consecutive = 0
            accepted.append(outcome)
            report(
                f"  [{index + 1}/{snapshots}] {outcome.snapshot_id} "
                f"(accepted={outcome.records_accepted}, live={outcome.live_vehicle})"
            )
        if index + 1 < snapshots:
            sleep(float(interval_seconds))
    finished_at = utc_now().isoformat()
    return SessionLoopResult(
        accepted=tuple(accepted),
        refusals=tuple(refusals),
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        ended_by_refusal_limit=ended_by_refusal_limit,
    )


@dataclass(frozen=True)
class ScheduledSessionOutcome:
    """What one scheduled session left on disk, including post-step failures."""

    marker_path: Path
    accepted_count: int
    refused_count: int
    measurement_written: bool
    measurement_skipped_reason: str | None
    post_step_errors: tuple[str, ...]


def run_scheduled_session(
    workspace_root: Path,
    occurrence: WindowOccurrence,
    schedule: SessionSchedule,
    schedule_digest: str,
    *,
    acquire: Callable[[], AcquiredSnapshot],
    utc_now: Callable[[], datetime],
    sleep: Callable[[float], None],
    report: Callable[[str], None],
) -> ScheduledSessionOutcome:
    """Run one window: acquire, mark completion atomically, then post-process.

    The completion marker is the ran-once fact and is written before the
    refusal ledger, the measurement, and the session record — every one of
    those is recoverable from quarantine; the marker is not.
    """

    directory = session_directory(workspace_root, occurrence)
    if (directory / COMPLETION_MARKER_NAME).exists():
        raise BodsScheduledSessionError(
            "WINDOW_ALREADY_COMPLETED",
            f"{occurrence.session_date.isoformat()}/{occurrence.window.label} already ran",
        )
    window = occurrence.window
    report(
        f"scheduled session '{window.label}' for {occurrence.session_date.isoformat()}: "
        f"{window.snapshots} snapshots at >= {schedule.interval_seconds} s"
    )
    session_salt = secrets.token_bytes(32)
    loop = run_refusal_tolerant_session_loop(
        snapshots=window.snapshots,
        interval_seconds=schedule.interval_seconds,
        acquire=acquire,
        quarantine_ids=lambda: list_bods_quarantine_ids(workspace_root),
        utc_now=utc_now,
        sleep=sleep,
        report=report,
    )
    report(f"session complete: {len(loop.accepted)} accepted, {len(loop.refusals)} refused")

    marker_path = directory / COMPLETION_MARKER_NAME
    _write_json_atomic(
        marker_path,
        {
            "record_type": "scheduled_bods_session_completion",
            "design_reference": DESIGN_REFERENCE,
            "triggered_by": "schedule",
            "schedule_digest": schedule_digest,
            "session_date": occurrence.session_date.isoformat(),
            "label": window.label,
            "scheduled_start_local": window.start_local,
            "started_at_utc": loop.started_at_utc,
            "finished_at_utc": loop.finished_at_utc,
            "snapshots_requested": window.snapshots,
            "snapshots_accepted": len(loop.accepted),
            "snapshots_refused": len(loop.refusals),
            "accepted_snapshot_ids": list(loop.accepted_snapshot_ids),
            "ended_by_refusal_limit": loop.ended_by_refusal_limit,
            "marker_semantics": _MARKER_SEMANTICS,
        },
    )

    post_step_errors: list[str] = []

    def _post_step(name: str, step: Callable[[], None]) -> None:
        try:
            step()
        except Exception as error:
            # The marker is already durable; a post-step failure must not take
            # down the supervisor, and every post-step artifact is recoverable
            # from quarantine.
            post_step_errors.append(f"{name}: {str(error)[:_ERROR_TEXT_LIMIT]}")
            report(f"  post-step '{name}' failed (recoverable from quarantine): {error}")

    def _write_ledger() -> None:
        _write_json_atomic(
            directory / REFUSAL_LEDGER_NAME,
            {
                "record_type": "scheduled_bods_session_refusal_ledger",
                "design_reference": DESIGN_REFERENCE,
                "triggered_by": "schedule",
                "schedule_digest": schedule_digest,
                "session_date": occurrence.session_date.isoformat(),
                "label": window.label,
                "started_at_utc": loop.started_at_utc,
                "finished_at_utc": loop.finished_at_utc,
                "snapshots_requested": window.snapshots,
                "snapshots_accepted": len(loop.accepted),
                "snapshots_refused": len(loop.refusals),
                "accepted_snapshot_ids": list(loop.accepted_snapshot_ids),
                "refusals": [refusal.as_payload() for refusal in loop.refusals],
                "refusal_semantics": _REFUSAL_SEMANTICS,
            },
        )

    measurement_written = False
    measurement_skipped_reason: str | None = None

    def _write_measurement() -> None:
        nonlocal measurement_written
        results: list[SessionExtractionResult] = []
        for snapshot_id in loop.accepted_snapshot_ids:
            result = extract_session_observations(
                workspace_root, snapshot_id, session_salt=session_salt
            )
            results.append(result)
            report(
                f"  extracted {result.observations_extracted}/{result.activities_seen} "
                f"({result.malformed_skipped} malformed) from {snapshot_id}"
            )
        measurement = measure_session_cadence(results)
        path = directory / CADENCE_MEASUREMENT_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(measurement_to_json(measurement) + "\n", encoding="utf-8")
        measurement_written = True

    def _write_record() -> None:
        _write_json_atomic(
            directory / SESSION_RECORD_NAME,
            {
                "record_type": "scheduled_bods_session_record",
                "design_reference": DESIGN_REFERENCE,
                "triggered_by": "schedule",
                "schedule_digest": schedule_digest,
                "session_date": occurrence.session_date.isoformat(),
                "label": window.label,
                "scheduled_start_local": window.start_local,
                "interval_seconds": schedule.interval_seconds,
                "started_at_utc": loop.started_at_utc,
                "finished_at_utc": loop.finished_at_utc,
                "snapshots_requested": window.snapshots,
                "snapshots_accepted": len(loop.accepted),
                "snapshots_refused": len(loop.refusals),
                "ended_by_refusal_limit": loop.ended_by_refusal_limit,
                "measurement_written": measurement_written,
                "measurement_skipped_reason": measurement_skipped_reason,
                "post_step_errors": list(post_step_errors),
                "artifacts": {
                    "completion_marker": COMPLETION_MARKER_NAME,
                    "refusal_ledger": REFUSAL_LEDGER_NAME,
                    "cadence_measurement": (
                        CADENCE_MEASUREMENT_NAME if measurement_written else None
                    ),
                },
            },
        )

    _post_step("refusal_ledger", _write_ledger)
    if len(loop.accepted) >= 2:
        _post_step("cadence_measurement", _write_measurement)
    else:
        measurement_skipped_reason = "fewer than two accepted snapshots"
        report("  fewer than two accepted snapshots; no cadence measurement")
    _post_step("session_record", _write_record)

    return ScheduledSessionOutcome(
        marker_path=marker_path,
        accepted_count=len(loop.accepted),
        refused_count=len(loop.refusals),
        measurement_written=measurement_written,
        measurement_skipped_reason=measurement_skipped_reason,
        post_step_errors=tuple(post_step_errors),
    )


def build_retention_report(
    workspace_root: Path,
    schedule: SessionSchedule,
    *,
    utc_now: Callable[[], datetime],
) -> dict[str, object]:
    """List scheduled-session snapshots that are prune-eligible. Deletes nothing.

    A session is eligible once it finished more than ``retention_report_days``
    ago *and* its aggregate measurement exists — the design's "once aggregates
    are committed" condition. Only snapshot ids named by scheduled completion
    markers are ever listed, so attended sessions can never appear here.
    """

    now = utc_now()
    eligible: list[dict[str, object]] = []
    eligible_snapshot_count = 0
    unreadable_markers = 0
    root = scheduled_root(workspace_root)
    quarantine = workspace_root / QUARANTINE_DIRECTORY_NAME
    if root.is_dir():
        for marker_path in sorted(root.glob(f"*/*/{COMPLETION_MARKER_NAME}")):
            try:
                marker = json.loads(marker_path.read_text(encoding="utf-8"))
                finished_at = datetime.fromisoformat(str(marker["finished_at_utc"]))
                snapshot_ids = [str(item) for item in marker["accepted_snapshot_ids"]]
            except (OSError, ValueError, KeyError, TypeError):
                unreadable_markers += 1
                continue
            if finished_at.tzinfo is None:
                unreadable_markers += 1
                continue
            if (now - finished_at) < timedelta(days=schedule.retention_report_days):
                continue
            if not (marker_path.parent / CADENCE_MEASUREMENT_NAME).is_file():
                continue
            present = [
                snapshot_id
                for snapshot_id in snapshot_ids
                if snapshot_id.startswith(_BODS_QUARANTINE_PREFIX)
                and (quarantine / snapshot_id).is_dir()
            ]
            if not present:
                continue
            eligible.append(
                {
                    "session_date": str(marker.get("session_date", "")),
                    "label": str(marker.get("label", "")),
                    "finished_at_utc": finished_at.isoformat(),
                    "prunable_snapshot_ids": present,
                }
            )
            eligible_snapshot_count += len(present)
    return {
        "record_type": "scheduled_bods_retention_report",
        "design_reference": DESIGN_REFERENCE,
        "generated_at_utc": now.isoformat(),
        "retention_report_days": schedule.retention_report_days,
        "eligible_sessions": eligible,
        "eligible_snapshot_count": eligible_snapshot_count,
        "unreadable_markers": unreadable_markers,
        "deletion_semantics": _RETENTION_SEMANTICS,
    }


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def supervisor_singleton(workspace_root: Path) -> Iterator[Path]:
    """Pid-file singleton: a second supervisor refuses to start."""

    path = scheduled_root(workspace_root) / SUPERVISOR_PID_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            existing = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing = -1
        if _pid_alive(existing):
            raise BodsScheduledSessionError(
                "SUPERVISOR_ALREADY_RUNNING",
                f"pid file records live supervisor pid {existing}; not starting a second one",
            )
    path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    try:
        yield path
    finally:
        try:
            recorded = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            recorded = -1
        if recorded == os.getpid():
            path.unlink(missing_ok=True)


def _print_flush(message: str) -> None:
    print(message, flush=True)


def run_supervisor(
    workspace_root: Path,
    schedule_path: Path,
    *,
    acquire: Callable[[], AcquiredSnapshot],
    local_now: Callable[[], datetime] | None = None,
    utc_now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] | None = None,
    report: Callable[[str], None] | None = None,
    max_iterations: int | None = None,
    max_sessions: int | None = None,
) -> int:
    """Supervise the schedule until stopped; returns how many sessions ran.

    ``max_iterations``/``max_sessions`` bound the loop for tests and for the
    owner-attended smoke (``--once``); production runs leave both unset.
    Sleeping happens in short chunks with a fresh plan each wake-up, so a
    machine that slept through a window skips it on wake instead of running
    it late.
    """

    loaded = load_schedule(schedule_path)
    local_clock = local_now if local_now is not None else _default_local_now
    utc_clock = utc_now if utc_now is not None else _default_utc_now
    sleeper = sleep if sleep is not None else time_module.sleep
    reporter = report if report is not None else _print_flush
    sessions_run = 0
    iterations = 0
    with supervisor_singleton(workspace_root):
        reporter(
            f"supervisor started: {len(loaded.schedule.sessions)} windows/day, "
            f"schedule digest {loaded.digest[:16]}…"
        )
        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            now = local_clock()
            plan = plan_next_action(
                loaded.schedule,
                now,
                lambda occurrence: occurrence_resolved(workspace_root, occurrence),
            )
            for occurrence in plan.late:
                write_skip_marker(
                    workspace_root,
                    occurrence,
                    schedule_digest=loaded.digest,
                    decided_at=now,
                )
                reporter(
                    f"skipped late window {occurrence.session_date.isoformat()}/"
                    f"{occurrence.window.label} (start {occurrence.window.start_local}; "
                    "never run late)"
                )
            if plan.run_now is not None:
                run_scheduled_session(
                    workspace_root,
                    plan.run_now,
                    loaded.schedule,
                    loaded.digest,
                    acquire=acquire,
                    utc_now=utc_clock,
                    sleep=sleeper,
                    report=reporter,
                )
                sessions_run += 1
                try:
                    _write_json_atomic(
                        scheduled_root(workspace_root) / RETENTION_REPORT_NAME,
                        build_retention_report(workspace_root, loaded.schedule, utc_now=utc_clock),
                    )
                except Exception as error:
                    # Report-only artifact; its failure never stops supervision.
                    reporter(f"retention report failed (report-only artifact): {error}")
                if max_sessions is not None and sessions_run >= max_sessions:
                    break
            elif plan.sleep_until is not None:
                remaining = (plan.sleep_until - now).total_seconds()
                sleeper(max(0.0, min(_SUPERVISOR_SLEEP_CHUNK_SECONDS, remaining)))
            else:
                sleeper(_SUPERVISOR_SLEEP_CHUNK_SECONDS)
    return sessions_run


def _default_local_now() -> datetime:
    return datetime.now(UTC).astimezone()


def _default_utc_now() -> datetime:
    return datetime.now(UTC)
