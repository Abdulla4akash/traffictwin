"""Operator-triggered BODS live refresh coordination and aggregate history.

This boundary adds persistent frequency/concurrency control around the existing
single-fetch workflow.  It records only secret-free aggregate summaries, never
raw positions, vehicle tokens, response bodies, credentials, or private paths.
There is deliberately no timer, daemon, background task, or automatic source
polling: every network request still requires an explicit caller action.
"""

from __future__ import annotations

import fcntl
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.bods_live import (
    BodsLiveRefresh,
    BodsLiveRefreshSummary,
    refresh_bods_live_scene,
)
from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.map_layers import (
    ManchesterMapScene,
    MapLayerRequest,
    build_map_layer,
    build_map_scene,
)
from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    ManchesterValidationState,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

BODS_LIVE_CONTROL_SCHEMA_VERSION = "1.0"
BODS_LIVE_CONTROL_METHOD_VERSION = "manchester-bods-live-control-1.0"
BODS_LIVE_CONTROL_POLICY_VERSION = "bods-live-control-v1"
BODS_LIVE_CONTROL_RELATIVE_PATH = Path("manchester/live/bods-refresh-state.json")
BODS_LIVE_CONTROL_LOCK_RELATIVE_PATH = Path("manchester/live/.bods-refresh.lock")
BODS_LIVE_CONTROL_MAX_BYTES = 2 * 1024 * 1024
BODS_LIVE_MINIMUM_INTERVAL_SECONDS = 60
BODS_LIVE_HISTORY_MAX_ENTRIES = 240
BODS_LIVE_HISTORY_MAX_AGE_HOURS = 24


class BodsLiveControlError(RuntimeError):
    """Typed, display-safe coordination refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class BodsLiveControlPolicy(ManchesterSnapshotModel):
    """Fixed conservative frequency and aggregate-history bounds."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["manchester-bods-live-control-1.0"] = "manchester-bods-live-control-1.0"
    policy_version: Literal["bods-live-control-v1"] = "bods-live-control-v1"
    minimum_interval_seconds: Literal[60] = 60
    history_max_entries: Literal[240] = 240
    history_max_age_hours: Literal[24] = 24
    operator_triggered_only: Literal[True] = True
    automatic_source_polling_available: Literal[False] = False
    single_refresh_at_a_time: Literal[True] = True
    aggregate_history_only: Literal[True] = True
    raw_vehicle_identifiers_persisted: Literal[False] = False
    public_export_available: Literal[False] = False


class BodsLiveControlState(ManchesterSnapshotModel):
    """Private aggregate-only state for controlled live refreshes."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["manchester-bods-live-control-1.0"] = "manchester-bods-live-control-1.0"
    policy: BodsLiveControlPolicy = BodsLiveControlPolicy()
    attempts_total: int = Field(ge=0)
    successes_total: int = Field(ge=0)
    failures_total: int = Field(ge=0)
    last_attempt_at_utc: datetime | None = None
    last_attempt_status: Literal["never", "in_progress", "succeeded", "failed"] = "never"
    last_request_scope_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    last_failure_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]{1,96}$")
    latest_success: BodsLiveRefreshSummary | None = None
    history: tuple[BodsLiveRefreshSummary, ...] = ()
    history_entry_count: int = Field(ge=0, le=BODS_LIVE_HISTORY_MAX_ENTRIES)
    aggregate_history_only: Literal[True] = True
    raw_vehicle_identifiers_persisted: Literal[False] = False
    automatic_source_polling_performed: Literal[False] = False
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_state(self) -> BodsLiveControlState:
        in_progress = int(self.last_attempt_status == "in_progress")
        if self.attempts_total != self.successes_total + self.failures_total + in_progress:
            raise ValueError("attempt totals must reconcile with terminal and in-progress states")
        if self.history_entry_count != len(self.history):
            raise ValueError("history entry count must match the embedded history")
        if self.successes_total < len(self.history):
            raise ValueError("bounded history cannot exceed the lifetime success count")
        identities = tuple((item.evaluated_at_utc, item.snapshot_id) for item in self.history)
        if identities != tuple(sorted(identities)) or len(set(identities)) != len(identities):
            raise ValueError("live history must have sorted unique timestamp/snapshot identities")
        expected_latest = None if not self.history else self.history[-1]
        if self.latest_success != expected_latest:
            raise ValueError("latest success must equal the final bounded history entry")
        if self.last_attempt_status == "never":
            if (
                any(
                    value is not None
                    for value in (
                        self.last_attempt_at_utc,
                        self.last_request_scope_fingerprint,
                        self.last_failure_code,
                        self.latest_success,
                    )
                )
                or self.attempts_total
            ):
                raise ValueError("never-attempted state cannot carry attempt evidence")
        else:
            if self.last_attempt_at_utc is None or self.last_request_scope_fingerprint is None:
                raise ValueError("attempted state requires time and request-scope identity")
            if (
                self.last_attempt_at_utc.tzinfo is None
                or self.last_attempt_at_utc.utcoffset() != timedelta(0)
            ):
                raise ValueError("last attempt time must be UTC")
        if (self.last_attempt_status == "failed") != (self.last_failure_code is not None):
            raise ValueError("failure code must exist exactly for a failed last attempt")
        return self


@dataclass(frozen=True, slots=True)
class ControlledBodsLiveRefresh:
    """Successful live refresh plus its persisted aggregate-only control state."""

    refresh: BodsLiveRefresh
    state: BodsLiveControlState


def initial_bods_live_control_state() -> BodsLiveControlState:
    """Return the exact empty state without touching a workspace."""

    return BodsLiveControlState(
        attempts_total=0,
        successes_total=0,
        failures_total=0,
        history_entry_count=0,
    )


def load_bods_live_control_state(workspace_root: str | Path) -> BodsLiveControlState:
    """Load the validated aggregate history, or return an empty state if absent."""

    workspace = _validated_workspace(workspace_root)
    target = workspace / BODS_LIVE_CONTROL_RELATIVE_PATH
    if not target.exists():
        return initial_bods_live_control_state()
    if (
        target.is_symlink()
        or not target.is_file()
        or target.stat().st_size > BODS_LIVE_CONTROL_MAX_BYTES
    ):
        raise BodsLiveControlError(
            "CONTROL_STATE_INVALID", "live control state is missing or unsafe"
        )
    try:
        payload = target.read_bytes()
        state = BodsLiveControlState.model_validate_json(payload)
    except (OSError, ValueError) as exc:
        raise BodsLiveControlError(
            "CONTROL_STATE_INVALID", "live control state is invalid"
        ) from exc
    if state.canonical_json().encode("utf-8") != payload:
        raise BodsLiveControlError(
            "CONTROL_STATE_NON_CANONICAL", "live control state must use canonical JSON"
        )
    return state


def coordinated_bods_live_refresh(
    workspace_root: str | Path,
    bounding_box: BodsBoundingBox,
    *,
    api_key: str,
    synthetic: bool = False,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> ControlledBodsLiveRefresh:
    """Perform one explicit refresh under persisted rate and concurrency limits."""

    workspace = _validated_workspace(workspace_root)
    clock: Callable[[], datetime] = (lambda: datetime.now(UTC)) if utc_now is None else utc_now
    attempted_at = clock()
    if attempted_at.tzinfo is None or attempted_at.utcoffset() != timedelta(0):
        raise BodsLiveControlError("TIME_INVALID", "live control requires a UTC timestamp")
    lock_fd = _acquire_lock(workspace)
    try:
        previous = load_bods_live_control_state(workspace)
        if previous.last_attempt_at_utc is not None:
            elapsed = (attempted_at - previous.last_attempt_at_utc).total_seconds()
            if elapsed < 0:
                raise BodsLiveControlError(
                    "CLOCK_REGRESSION", "the control clock moved before the last recorded attempt"
                )
            if elapsed < previous.policy.minimum_interval_seconds:
                remaining = previous.policy.minimum_interval_seconds - int(elapsed)
                raise BodsLiveControlError(
                    "REFRESH_TOO_SOON",
                    f"wait at least {remaining} more seconds before another source request",
                )
        scope_fingerprint = bounding_box.fingerprint()
        settled_failures = previous.failures_total + int(
            previous.last_attempt_status == "in_progress"
        )
        in_progress = BodsLiveControlState(
            policy=previous.policy,
            attempts_total=previous.attempts_total + 1,
            successes_total=previous.successes_total,
            failures_total=settled_failures,
            last_attempt_at_utc=attempted_at,
            last_attempt_status="in_progress",
            last_request_scope_fingerprint=scope_fingerprint,
            latest_success=previous.latest_success,
            history=previous.history,
            history_entry_count=len(previous.history),
        )
        _store_state(workspace, in_progress)
        try:
            refresh = refresh_bods_live_scene(
                workspace,
                bounding_box,
                api_key=api_key,
                synthetic=synthetic,
                http_client=http_client,
                utc_now=utc_now,
            )
        except Exception as exc:
            failure_code = _safe_failure_code(exc)
            failed = BodsLiveControlState(
                policy=previous.policy,
                attempts_total=in_progress.attempts_total,
                successes_total=previous.successes_total,
                failures_total=settled_failures + 1,
                last_attempt_at_utc=attempted_at,
                last_attempt_status="failed",
                last_request_scope_fingerprint=scope_fingerprint,
                last_failure_code=failure_code,
                latest_success=previous.latest_success,
                history=previous.history,
                history_entry_count=len(previous.history),
            )
            _store_state(workspace, failed)
            raise
        history = _bounded_history(previous.history + (refresh.summary,), attempted_at)
        succeeded = BodsLiveControlState(
            policy=previous.policy,
            attempts_total=in_progress.attempts_total,
            successes_total=previous.successes_total + 1,
            failures_total=settled_failures,
            last_attempt_at_utc=attempted_at,
            last_attempt_status="succeeded",
            last_request_scope_fingerprint=scope_fingerprint,
            latest_success=history[-1],
            history=history,
            history_entry_count=len(history),
        )
        _store_state(workspace, succeeded)
        return ControlledBodsLiveRefresh(refresh=refresh, state=succeeded)
    finally:
        _release_lock(workspace, lock_fd)


def bods_live_history_rows(state: BodsLiveControlState) -> tuple[dict[str, object], ...]:
    """Project aggregate-only history rows for charts without raw position data."""

    return tuple(
        {
            "Observed at": item.evaluated_at_utc,
            "Bee Network buses": item.bee_network_franchised,
            "Other or unknown buses": item.non_franchised_or_unknown,
            "Live buses": item.live_vehicle,
            "Stale bus records": item.stale,
        }
        for item in state.history
    )


def project_bods_live_scene_for_display(
    scene: ManchesterMapScene,
    *,
    evaluated_at_utc: datetime,
) -> ManchesterMapScene:
    """Re-evaluate BODS freshness for local display without mutating stored evidence."""

    if scene.mode != "live_vehicles":
        raise BodsLiveControlError(
            "SCENE_MODE_MISMATCH", "only a live-vehicle scene can receive display-time freshness"
        )
    if evaluated_at_utc.tzinfo is None or evaluated_at_utc.utcoffset() != timedelta(0):
        raise BodsLiveControlError("TIME_INVALID", "display freshness requires a UTC timestamp")
    layers = []
    for layer in scene.layers:
        original = layer.request.freshness
        if layer.request.source != "bods_siri_vm" or original is None or layer.request.synthetic:
            layers.append(layer)
            continue
        refreshed = evaluate_source_freshness(
            FreshnessEvaluationRequest(
                source="bods_siri_vm",
                evidence_validation=ManchesterValidationState.ACCEPTED,
                snapshot_available=True,
                use_mode="live",
                evaluated_at_utc=evaluated_at_utc,
                observed_at_utc=original.observed_at_utc,
                valid_until_utc=original.valid_until_utc,
                synthetic=False,
            )
        )
        title = layer.request.title
        for suffix in (" · live", " · stale", " · stale cached"):
            if title.endswith(suffix):
                title = title[: -len(suffix)]
                break
        if refreshed.truth_state == "stale":
            title += " · stale cached"
        elif refreshed.truth_state == "live_vehicle":
            title += " · live"
        request_values = layer.request.model_dump(mode="python")
        request_values.update({"title": title, "freshness": refreshed})
        layers.append(build_map_layer(MapLayerRequest.model_validate(request_values)))
    return build_map_scene("live_vehicles", layers)


def _bounded_history(
    history: tuple[BodsLiveRefreshSummary, ...], evaluated_at: datetime
) -> tuple[BodsLiveRefreshSummary, ...]:
    cutoff = evaluated_at - timedelta(hours=BODS_LIVE_HISTORY_MAX_AGE_HOURS)
    retained = tuple(item for item in history if item.evaluated_at_utc >= cutoff)
    retained = tuple(sorted(retained, key=lambda item: (item.evaluated_at_utc, item.snapshot_id)))
    if len({(item.evaluated_at_utc, item.snapshot_id) for item in retained}) != len(retained):
        raise BodsLiveControlError("HISTORY_DUPLICATE", "live refresh history contains a duplicate")
    return retained[-BODS_LIVE_HISTORY_MAX_ENTRIES:]


def _safe_failure_code(exc: Exception) -> str:
    code = getattr(exc, "code", "LIVE_REFRESH_FAILED")
    if not isinstance(code, str) or not code or len(code) > 96:
        return "LIVE_REFRESH_FAILED"
    if any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in code):
        return "LIVE_REFRESH_FAILED"
    return code


def _store_state(workspace: Path, state: BodsLiveControlState) -> None:
    payload = state.canonical_json().encode("utf-8")
    if len(payload) > BODS_LIVE_CONTROL_MAX_BYTES:
        raise BodsLiveControlError(
            "CONTROL_STATE_TOO_LARGE", "bounded live control state is too large"
        )
    target = workspace / BODS_LIVE_CONTROL_RELATIVE_PATH
    parent = _live_directory(workspace)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise BodsLiveControlError("CONTROL_PATH_UNSAFE", "live control target is unsafe")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".bods-state-", dir=parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise BodsLiveControlError(
            "CONTROL_WRITE_FAILED", "live control state could not be stored"
        ) from exc


def _acquire_lock(workspace: Path) -> int:
    parent = _live_directory(workspace)
    lock = parent / BODS_LIVE_CONTROL_LOCK_RELATIVE_PATH.name
    if lock.is_symlink() or (lock.exists() and not lock.is_file()):
        raise BodsLiveControlError("CONTROL_PATH_UNSAFE", "live refresh lock path is unsafe")
    try:
        flags = os.O_WRONLY | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock, flags, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except BlockingIOError as exc:
        if "descriptor" in locals():
            os.close(descriptor)
        raise BodsLiveControlError(
            "REFRESH_BUSY", "another live refresh is already in progress"
        ) from exc
    except OSError as exc:
        raise BodsLiveControlError(
            "CONTROL_LOCK_FAILED", "live refresh lock could not be created"
        ) from exc


def _release_lock(workspace: Path, descriptor: int) -> None:
    del workspace
    fcntl.flock(descriptor, fcntl.LOCK_UN)
    os.close(descriptor)


def _live_directory(workspace: Path) -> Path:
    manchester = workspace / "manchester"
    if (
        manchester.is_symlink()
        or not manchester.is_dir()
        or manchester.parent.resolve(strict=True) != workspace.resolve(strict=True)
    ):
        raise BodsLiveControlError("CONTROL_PATH_UNSAFE", "Manchester workspace area is unsafe")
    live = manchester / "live"
    if live.exists() and (live.is_symlink() or not live.is_dir()):
        raise BodsLiveControlError("CONTROL_PATH_UNSAFE", "live control directory is unsafe")
    live.mkdir(mode=0o700, exist_ok=True)
    if live.resolve(strict=True).parent != manchester.resolve(strict=True):
        raise BodsLiveControlError("CONTROL_PATH_UNSAFE", "live control directory escaped")
    return live


def _validated_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise BodsLiveControlError(
            "WORKSPACE_INVALID", "configure a valid isolated v0.7 workspace first"
        ) from exc
    return workspace.resolve(strict=True)
