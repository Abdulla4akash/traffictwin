"""Process-local automatic refresh control for private BODS live overlays."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.bods_live_control import (
    BodsLiveControlError,
    coordinated_bods_live_refresh,
    load_bods_live_control_state,
)

BODS_AUTO_REFRESH_ENV = "TRAFFICTWIN_BODS_AUTO_REFRESH_SECONDS"
BODS_BOUNDING_BOX_ENV = "TRAFFICTWIN_BODS_BOUNDING_BOX"
BODS_AUTO_REFRESH_DEFAULT_SECONDS = 60
BODS_AUTO_REFRESH_MIN_SECONDS = 60
BODS_AUTO_REFRESH_MAX_SECONDS = 300


class BodsAutoRefreshError(RuntimeError):
    """Typed automatic-refresh refusal without key, coordinates, or private paths."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class BodsAutoRefreshStatus:
    """Secret-free process status for one private BODS workspace worker."""

    running: bool
    interval_seconds: int
    request_scope_fingerprint: str
    attempts_in_process: int = 0
    successes_in_process: int = 0
    failures_in_process: int = 0
    last_attempt_at_utc: datetime | None = None
    last_success_at_utc: datetime | None = None
    last_failure_code: str | None = None


def configured_bods_auto_refresh_seconds(
    environment: Mapping[str, str] | None = None,
) -> int | None:
    """Read the conservative process interval; zero or ``off`` disables it."""

    source = os.environ if environment is None else environment
    raw = source.get(BODS_AUTO_REFRESH_ENV)
    if raw is None or not raw.strip():
        return BODS_AUTO_REFRESH_DEFAULT_SECONDS
    value = raw.strip().lower()
    if value in {"0", "false", "no", "off"}:
        return None
    try:
        seconds = int(value)
    except ValueError as exc:
        raise BodsAutoRefreshError(
            "BODS_AUTO_REFRESH_INTERVAL_INVALID",
            f"{BODS_AUTO_REFRESH_ENV} must be an integer or off",
        ) from exc
    if not BODS_AUTO_REFRESH_MIN_SECONDS <= seconds <= BODS_AUTO_REFRESH_MAX_SECONDS:
        raise BodsAutoRefreshError(
            "BODS_AUTO_REFRESH_INTERVAL_INVALID",
            f"{BODS_AUTO_REFRESH_ENV} must be between {BODS_AUTO_REFRESH_MIN_SECONDS} and "
            f"{BODS_AUTO_REFRESH_MAX_SECONDS} seconds",
        )
    return seconds


def configured_bods_bounding_box(
    environment: Mapping[str, str] | None = None,
) -> BodsBoundingBox | None:
    """Parse the operator-supplied request box without inventing a default scope."""

    source = os.environ if environment is None else environment
    raw = source.get(BODS_BOUNDING_BOX_ENV)
    if raw is None or not raw.strip():
        return None
    parts = tuple(part.strip() for part in raw.split(","))
    if len(parts) != 4 or any(not part for part in parts):
        raise BodsAutoRefreshError(
            "BODS_AUTO_REFRESH_SCOPE_INVALID",
            f"{BODS_BOUNDING_BOX_ENV} must contain four comma-separated coordinates",
        )
    try:
        values = tuple(Decimal(part) for part in parts)
        return BodsBoundingBox(
            min_longitude=values[0],
            min_latitude=values[1],
            max_longitude=values[2],
            max_latitude=values[3],
        )
    except (InvalidOperation, ValidationError) as exc:
        raise BodsAutoRefreshError(
            "BODS_AUTO_REFRESH_SCOPE_INVALID",
            f"{BODS_BOUNDING_BOX_ENV} must contain valid ordered geographic coordinates",
        ) from exc


class _BodsAutoRefreshWorker:
    def __init__(
        self,
        workspace: Path,
        bounding_box: BodsBoundingBox,
        *,
        api_key: str,
        interval_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.workspace = workspace
        self._bounding_box = bounding_box
        self._api_key = api_key
        self._interval_seconds = interval_seconds
        self._clock: Callable[[], datetime] = (
            (lambda: datetime.now(UTC)) if clock is None else clock
        )
        self._stop = threading.Event()
        self._status_lock = threading.Lock()
        self._status = BodsAutoRefreshStatus(
            running=True,
            interval_seconds=interval_seconds,
            request_scope_fingerprint=bounding_box.fingerprint(),
        )
        self._thread = threading.Thread(
            target=self._run,
            name=f"traffictwin-bods-{workspace.name}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def status(self) -> BodsAutoRefreshStatus:
        with self._status_lock:
            return self._status

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                if self._stop.wait(self._seconds_until_due()):
                    return
                attempted_at = self._clock()
                self._record_attempt(attempted_at)
                try:
                    coordinated_bods_live_refresh(
                        self.workspace,
                        self._bounding_box,
                        api_key=self._api_key,
                        trigger="automatic",
                    )
                except Exception as exc:  # survive provider, schema, and private-path refusals
                    self._record_failure(_failure_code(exc))
                else:
                    self._record_success(attempted_at)
        finally:
            self._record_stopped()

    def _seconds_until_due(self) -> float:
        process_attempt = self.status().last_attempt_at_utc
        try:
            state = load_bods_live_control_state(self.workspace)
        except (BodsLiveControlError, OSError, ValueError):
            last_attempt = process_attempt
        else:
            candidates = tuple(
                item for item in (state.last_attempt_at_utc, process_attempt) if item is not None
            )
            last_attempt = max(candidates) if candidates else None
        if last_attempt is None:
            return 0.0
        elapsed = (self._clock() - last_attempt).total_seconds()
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
_WORKERS: dict[Path, _BodsAutoRefreshWorker] = {}


def ensure_bods_auto_refresh(
    workspace_root: str | Path,
    bounding_box: BodsBoundingBox,
    *,
    api_key: str,
    interval_seconds: int = BODS_AUTO_REFRESH_DEFAULT_SECONDS,
) -> BodsAutoRefreshStatus:
    """Start one idempotent private BODS daemon for a validated workspace."""

    if not api_key.strip():
        raise BodsAutoRefreshError("BODS_AUTO_REFRESH_KEY_MISSING", "a BODS API key is required")
    if not BODS_AUTO_REFRESH_MIN_SECONDS <= interval_seconds <= BODS_AUTO_REFRESH_MAX_SECONDS:
        raise BodsAutoRefreshError(
            "BODS_AUTO_REFRESH_INTERVAL_INVALID", "automatic refresh interval is outside bounds"
        )
    workspace = Path(workspace_root).resolve(strict=True)
    load_bods_live_control_state(workspace)
    scope_fingerprint = bounding_box.fingerprint()
    with _WORKERS_LOCK:
        existing = _WORKERS.get(workspace)
        if existing is not None and existing.is_alive():
            status = existing.status()
            if (
                status.interval_seconds != interval_seconds
                or status.request_scope_fingerprint != scope_fingerprint
            ):
                raise BodsAutoRefreshError(
                    "BODS_AUTO_REFRESH_CONFIG_CONFLICT",
                    "restart the server to change the active BODS refresh configuration",
                )
            return status
        worker = _BodsAutoRefreshWorker(
            workspace,
            bounding_box,
            api_key=api_key,
            interval_seconds=interval_seconds,
        )
        _WORKERS[workspace] = worker
        worker.start()
        return worker.status()


def bods_auto_refresh_status(workspace_root: str | Path) -> BodsAutoRefreshStatus | None:
    """Return secret-free process status without opening the provider connection."""

    workspace = Path(workspace_root).resolve()
    with _WORKERS_LOCK:
        worker = _WORKERS.get(workspace)
        return None if worker is None else worker.status()


def _failure_code(exc: Exception) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value.isupper() and len(value) <= 96:
        return value
    return "BODS_AUTO_REFRESH_FAILED"


def _stop_bods_auto_refresh_workers_for_tests() -> None:
    """Stop process workers so focused tests do not leak daemon state."""

    with _WORKERS_LOCK:
        workers = tuple(_WORKERS.values())
        _WORKERS.clear()
    for worker in workers:
        worker.stop()
