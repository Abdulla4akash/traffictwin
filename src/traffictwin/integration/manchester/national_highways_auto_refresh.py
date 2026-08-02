"""Process-local automatic refresh control for National Highways overlays."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from traffictwin.integration.manchester.national_highways_live import (
    NationalHighwaysLiveError,
    coordinated_national_highways_refresh,
    load_national_highways_control_state,
)

NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV = "TRAFFICTWIN_NATIONAL_HIGHWAYS_AUTO_REFRESH_SECONDS"
NATIONAL_HIGHWAYS_AUTO_REFRESH_DEFAULT_SECONDS = 300
NATIONAL_HIGHWAYS_AUTO_REFRESH_MIN_SECONDS = 60
NATIONAL_HIGHWAYS_AUTO_REFRESH_MAX_SECONDS = 540


class NationalHighwaysAutoRefreshError(RuntimeError):
    """Typed configuration or process-worker refusal without secret material."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class NationalHighwaysAutoRefreshStatus:
    """Secret-free status for one process-local workspace worker."""

    running: bool
    interval_seconds: int
    event_type: Literal["planned", "unplanned"]
    attempts_in_process: int = 0
    successes_in_process: int = 0
    failures_in_process: int = 0
    last_attempt_at_utc: datetime | None = None
    last_success_at_utc: datetime | None = None
    last_failure_code: str | None = None


def configured_national_highways_auto_refresh_seconds(
    environment: Mapping[str, str] | None = None,
) -> int | None:
    """Read the bounded server-lifetime interval; zero or ``off`` disables it."""

    source = os.environ if environment is None else environment
    raw = source.get(NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV)
    if raw is None or not raw.strip():
        return NATIONAL_HIGHWAYS_AUTO_REFRESH_DEFAULT_SECONDS
    value = raw.strip().lower()
    if value in {"0", "false", "no", "off"}:
        return None
    try:
        seconds = int(value)
    except ValueError as exc:
        raise NationalHighwaysAutoRefreshError(
            "AUTO_REFRESH_INTERVAL_INVALID",
            f"{NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV} must be an integer or off",
        ) from exc
    if not (
        NATIONAL_HIGHWAYS_AUTO_REFRESH_MIN_SECONDS
        <= seconds
        <= NATIONAL_HIGHWAYS_AUTO_REFRESH_MAX_SECONDS
    ):
        raise NationalHighwaysAutoRefreshError(
            "AUTO_REFRESH_INTERVAL_INVALID",
            f"{NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV} must be between "
            f"{NATIONAL_HIGHWAYS_AUTO_REFRESH_MIN_SECONDS} and "
            f"{NATIONAL_HIGHWAYS_AUTO_REFRESH_MAX_SECONDS} seconds",
        )
    return seconds


class _NationalHighwaysAutoRefreshWorker:
    def __init__(
        self,
        workspace: Path,
        *,
        subscription_key: str,
        interval_seconds: int,
        event_type: Literal["planned", "unplanned"],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.workspace = workspace
        self._subscription_key = subscription_key
        self._interval_seconds = interval_seconds
        self._event_type = event_type
        self._clock: Callable[[], datetime] = (
            (lambda: datetime.now(UTC)) if clock is None else clock
        )
        self._stop = threading.Event()
        self._status_lock = threading.Lock()
        self._status = NationalHighwaysAutoRefreshStatus(
            running=True,
            interval_seconds=interval_seconds,
            event_type=event_type,
        )
        self._thread = threading.Thread(
            target=self._run,
            name=f"traffictwin-national-highways-{workspace.name}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def status(self) -> NationalHighwaysAutoRefreshStatus:
        with self._status_lock:
            return self._status

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                delay = self._seconds_until_due()
                if self._stop.wait(delay):
                    return
                attempted_at = self._clock()
                self._record_attempt(attempted_at)
                try:
                    coordinated_national_highways_refresh(
                        self.workspace,
                        subscription_key=self._subscription_key,
                        event_type=self._event_type,
                        trigger="automatic",
                    )
                except Exception as exc:  # the daemon must survive provider and schema failures
                    self._record_failure(_failure_code(exc))
                else:
                    self._record_success(attempted_at)
        finally:
            self._record_stopped()

    def _seconds_until_due(self) -> float:
        process_attempt = self.status().last_attempt_at_utc
        try:
            state = load_national_highways_control_state(self.workspace)
        except (NationalHighwaysLiveError, OSError, ValueError):
            last_attempt = process_attempt
        else:
            candidates = tuple(
                item for item in (state.last_attempt_at_utc, process_attempt) if item is not None
            )
            last_attempt = max(candidates) if candidates else None
        if last_attempt is None:
            return 0.0
        now = self._clock()
        elapsed = (now - last_attempt).total_seconds()
        return float(max(0, self._interval_seconds - elapsed))

    def _record_attempt(self, attempted_at: datetime) -> None:
        with self._status_lock:
            self._status = replace(
                self._status,
                attempts_in_process=self._status.attempts_in_process + 1,
                last_attempt_at_utc=attempted_at,
                last_failure_code=None,
            )

    def _record_failure(self, code: str) -> None:
        with self._status_lock:
            self._status = replace(
                self._status,
                failures_in_process=self._status.failures_in_process + 1,
                last_failure_code=code,
            )

    def _record_success(self, attempted_at: datetime) -> None:
        with self._status_lock:
            self._status = replace(
                self._status,
                successes_in_process=self._status.successes_in_process + 1,
                last_success_at_utc=attempted_at,
                last_failure_code=None,
            )

    def _record_stopped(self) -> None:
        with self._status_lock:
            self._status = replace(self._status, running=False)


_WORKERS_LOCK = threading.Lock()
_WORKERS: dict[Path, _NationalHighwaysAutoRefreshWorker] = {}


def ensure_national_highways_auto_refresh(
    workspace_root: str | Path,
    *,
    subscription_key: str,
    interval_seconds: int = NATIONAL_HIGHWAYS_AUTO_REFRESH_DEFAULT_SECONDS,
    event_type: Literal["planned", "unplanned"] = "unplanned",
) -> NationalHighwaysAutoRefreshStatus:
    """Start one idempotent daemon for a validated workspace in this process."""

    if not subscription_key.strip():
        raise NationalHighwaysAutoRefreshError(
            "AUTO_REFRESH_KEY_MISSING", "a National Highways subscription key is required"
        )
    if not (
        NATIONAL_HIGHWAYS_AUTO_REFRESH_MIN_SECONDS
        <= interval_seconds
        <= NATIONAL_HIGHWAYS_AUTO_REFRESH_MAX_SECONDS
    ):
        raise NationalHighwaysAutoRefreshError(
            "AUTO_REFRESH_INTERVAL_INVALID", "automatic refresh interval is outside its bounds"
        )
    workspace = Path(workspace_root).resolve(strict=True)
    load_national_highways_control_state(workspace)
    with _WORKERS_LOCK:
        existing = _WORKERS.get(workspace)
        if existing is not None and existing.is_alive():
            status = existing.status()
            if status.interval_seconds != interval_seconds or status.event_type != event_type:
                raise NationalHighwaysAutoRefreshError(
                    "AUTO_REFRESH_CONFIG_CONFLICT",
                    "restart the server to change the active automatic refresh configuration",
                )
            return status
        worker = _NationalHighwaysAutoRefreshWorker(
            workspace,
            subscription_key=subscription_key,
            interval_seconds=interval_seconds,
            event_type=event_type,
        )
        _WORKERS[workspace] = worker
        worker.start()
        return worker.status()


def national_highways_auto_refresh_status(
    workspace_root: str | Path,
) -> NationalHighwaysAutoRefreshStatus | None:
    """Return secret-free process status without opening a source connection."""

    workspace = Path(workspace_root).resolve()
    with _WORKERS_LOCK:
        worker = _WORKERS.get(workspace)
        return None if worker is None else worker.status()


def _failure_code(exc: Exception) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value.isupper() and len(value) <= 96:
        return value
    return "NATIONAL_HIGHWAYS_AUTO_REFRESH_FAILED"


def _stop_national_highways_auto_refresh_workers_for_tests() -> None:
    """Stop process workers so focused tests do not leak daemon state."""

    with _WORKERS_LOCK:
        workers = tuple(_WORKERS.values())
        _WORKERS.clear()
    for worker in workers:
        worker.stop()
