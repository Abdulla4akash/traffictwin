"""Secret-free preflight and fixed foreground launch for a real v0.7 workspace.

The preflight reads only one exact owner-supplied durable workspace and local
process configuration. It does not call a provider, create control state, or
persist credentials. Launch uses a fixed loopback-only Streamlit argv and keeps
the existing BODS and National Highways worker lifecycle inside that foreground
process.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.integration.manchester.bods_acquisition import (
    BODS_ACQUISITION_METHOD_VERSION,
    BODS_ACQUISITION_SCHEMA_VERSION,
    BODS_FRESHNESS_POLICY_VERSION,
)
from traffictwin.integration.manchester.bods_auto_refresh import (
    BODS_AUTO_REFRESH_ENV,
    BODS_BOUNDING_BOX_ENV,
    BodsAutoRefreshError,
    configured_bods_auto_refresh_seconds,
    configured_bods_bounding_box,
)
from traffictwin.integration.manchester.bods_live import (
    BODS_LIVE_SCENE_MAX_BYTES,
    BODS_LIVE_SCENE_RELATIVE_PATH,
    BODS_LIVE_WORKFLOW_METHOD_VERSION,
)
from traffictwin.integration.manchester.bods_live_control import (
    BODS_LIVE_CONTROL_LOCK_RELATIVE_PATH,
    BODS_LIVE_CONTROL_METHOD_VERSION,
    BODS_LIVE_CONTROL_RELATIVE_PATH,
    BodsLiveControlError,
    load_bods_live_control_state,
)
from traffictwin.integration.manchester.map_layers import ManchesterMapScene
from traffictwin.integration.manchester.national_highways import (
    NATIONAL_HIGHWAYS_SCHEMA_VERSION,
)
from traffictwin.integration.manchester.national_highways_acquisition import (
    NATIONAL_HIGHWAYS_ACQUISITION_VERSION,
)
from traffictwin.integration.manchester.national_highways_auto_refresh import (
    NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV,
    NationalHighwaysAutoRefreshError,
    configured_national_highways_auto_refresh_seconds,
)
from traffictwin.integration.manchester.national_highways_live import (
    NATIONAL_HIGHWAYS_CONTROL_RELATIVE_PATH,
    NATIONAL_HIGHWAYS_CONTROL_VERSION,
    NATIONAL_HIGHWAYS_LATEST_OVERLAY,
    NATIONAL_HIGHWAYS_LIVE_OVERLAY,
    NATIONAL_HIGHWAYS_LOCK_RELATIVE_PATH,
    NationalHighwaysLiveError,
    load_national_highways_control_state,
)
from traffictwin.integration.manchester.scene_publication import MANCHESTER_SCENE_MAX_BYTES
from traffictwin.release.compatibility import (
    V07_ACTIVE_REGISTRY,
    V07CompatibilityError,
    inspect_v07_workspace,
)
from traffictwin.release.durable_workspace import (
    V07DurableWorkspaceError,
    load_durable_workspace_receipt,
)

REAL_WORKSPACE_RUN_SCHEMA_VERSION: Literal["traffictwin.real-workspace-run.v1"] = (
    "traffictwin.real-workspace-run.v1"
)
REAL_WORKSPACE_RUN_METHOD_VERSION: Literal["v07-real-workspace-run-1.0"] = (
    "v07-real-workspace-run-1.0"
)
REAL_WORKSPACE_RUN_HOST: Literal["127.0.0.1"] = "127.0.0.1"
REAL_WORKSPACE_RUN_PORT: Literal[8502] = 8502
REAL_WORKSPACE_ENVIRONMENT_NAMES = (
    "BODS_API_KEY",
    BODS_BOUNDING_BOX_ENV,
    BODS_AUTO_REFRESH_ENV,
    "NATIONAL_HIGHWAYS_API_KEY",
    NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV,
    "TRAFFICTWIN_WORKSPACE_PATH",
    "TRAFFICTWIN_REGISTRY_PATH",
)

PortProbe = Callable[[str, int], bool]
ProcessRunner = Callable[[Sequence[str], Mapping[str, str]], int]


class V07RealWorkspaceRunError(RuntimeError):
    """Typed path-free run-profile refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class V07SourceContractVersions(BaseModel):
    """Exact source/control/freshness versions read by one worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    acquisition: str = Field(min_length=1, max_length=96)
    source_schema: str = Field(min_length=1, max_length=96)
    live_scene: str = Field(min_length=1, max_length=96)
    control: str = Field(min_length=1, max_length=96)
    freshness: Literal["manchester-freshness-v1"] = "manchester-freshness-v1"


class V07SourceRunPreflight(BaseModel):
    """Secret-free local readiness for one process worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["bods", "national_highways"]
    configuration_status: Literal["configured", "disabled", "not_configured", "invalid"]
    credential_environment_name: Literal["BODS_API_KEY", "NATIONAL_HIGHWAYS_API_KEY"]
    credential_present: bool
    interval_environment_name: str
    interval_seconds: int | None = Field(default=None, ge=60, le=540)
    request_scope_status: Literal["valid", "missing", "not_applicable", "invalid"]
    request_scope_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    control_integrity: Literal["absent_valid", "valid", "invalid"]
    lock_status: Literal["available", "busy", "unsafe"]
    last_terminal_status: Literal["never", "succeeded", "failed", "in_progress"]
    last_terminal_state_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    scene_status: Literal["absent", "available", "partial", "invalid"]
    local_scene_count: int = Field(ge=0, le=2)
    contracts: V07SourceContractVersions
    enabled_for_process: bool
    operational_blockers: tuple[str, ...] = ()
    policy_blockers: tuple[str, ...]
    network_request_performed: Literal[False] = False
    credential_value_persisted: Literal[False] = False

    @model_validator(mode="after")
    def validate_source(self) -> V07SourceRunPreflight:
        if self.enabled_for_process != (self.configuration_status == "configured"):
            raise ValueError("worker enablement must match configured status")
        if self.request_scope_status == "valid" and self.request_scope_fingerprint is None:
            raise ValueError("a valid request scope requires its fingerprint")
        if self.request_scope_status != "valid" and self.request_scope_fingerprint is not None:
            raise ValueError("only a valid request scope may carry a fingerprint")
        if self.last_terminal_status in {"never", "in_progress"}:
            if self.last_terminal_state_fingerprint is not None:
                raise ValueError("non-terminal control state cannot carry a terminal fingerprint")
        elif self.last_terminal_state_fingerprint is None:
            raise ValueError("terminal control state requires a fingerprint")
        return self


class V07RealWorkspaceRunPreflight(BaseModel):
    """Mutation-free, network-free, path-free plan for local port 8502."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["traffictwin.real-workspace-run.v1"] = REAL_WORKSPACE_RUN_SCHEMA_VERSION
    method_version: Literal["v07-real-workspace-run-1.0"] = REAL_WORKSPACE_RUN_METHOD_VERSION
    capability_ids: tuple[Literal["REL-01", "MAN-05", "MAN-08"], ...] = (
        "REL-01",
        "MAN-05",
        "MAN-08",
    )
    capability_status: Literal["planned"] = "planned"
    operation: Literal["foreground_local_real_workspace"] = "foreground_local_real_workspace"
    workspace_handle: str = Field(pattern=r"^workspace-[0-9a-f]{16}$")
    durable_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    active_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    application_entrypoint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bind_host: Literal["127.0.0.1"] = REAL_WORKSPACE_RUN_HOST
    port: Literal[8502] = REAL_WORKSPACE_RUN_PORT
    port_available: bool
    synthetic_demo_expected_port: Literal[8501] = 8501
    port_separated_from_synthetic_demo: Literal[True] = True
    foreground_only: Literal[True] = True
    loopback_only: Literal[True] = True
    public_hosting_available: Literal[False] = False
    environment_variable_names: tuple[str, ...] = REAL_WORKSPACE_ENVIRONMENT_NAMES
    bods: V07SourceRunPreflight
    national_highways: V07SourceRunPreflight
    blockers: tuple[str, ...] = ()
    launchable: bool
    network_request_performed: Literal[False] = False
    workspace_mutated: Literal[False] = False
    credential_value_persisted: Literal[False] = False
    private_path_persisted: Literal[False] = False

    @model_validator(mode="after")
    def validate_preflight(self) -> V07RealWorkspaceRunPreflight:
        expected = self.port_available and not self.blockers
        if self.launchable != expected:
            raise ValueError("launchable must reconcile port and blockers")
        if self.bods.source != "bods" or self.national_highways.source != "national_highways":
            raise ValueError("source preflights are in the wrong slots")
        return self

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def confirmation_fingerprint(self) -> str:
        return _sha256_bytes(self.canonical_json().encode("utf-8"))


class V07RealWorkspaceLaunchReceipt(BaseModel):
    """Safe terminal result for a dry run or completed foreground process."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["traffictwin.real-workspace-run.v1"] = REAL_WORKSPACE_RUN_SCHEMA_VERSION
    method_version: Literal["v07-real-workspace-run-1.0"] = REAL_WORKSPACE_RUN_METHOD_VERSION
    workspace_handle: str = Field(pattern=r"^workspace-[0-9a-f]{16}$")
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    bind_host: Literal["127.0.0.1"] = REAL_WORKSPACE_RUN_HOST
    port: Literal[8502] = REAL_WORKSPACE_RUN_PORT
    fixed_argv: Literal[True] = True
    shell_used: Literal[False] = False
    foreground_only: Literal[True] = True
    dry_run: bool
    process_started: bool
    foreground_process_completed: bool
    return_code: int | None = None
    credential_value_persisted: Literal[False] = False
    private_path_persisted: Literal[False] = False

    @model_validator(mode="after")
    def validate_launch(self) -> V07RealWorkspaceLaunchReceipt:
        if self.dry_run:
            if (
                self.process_started
                or self.foreground_process_completed
                or self.return_code is not None
            ):
                raise ValueError("dry run cannot contain process execution state")
        elif not self.process_started or not self.foreground_process_completed:
            raise ValueError("non-dry launch must describe the completed foreground process")
        return self


def preflight_real_v07_workspace_run(
    path: str | Path,
    *,
    environment: Mapping[str, str] | None = None,
    port_probe: PortProbe | None = None,
) -> V07RealWorkspaceRunPreflight:
    """Inspect one durable workspace and local configuration without mutation or network I/O."""

    try:
        return _preflight_real_v07_workspace_run(
            path,
            environment=os.environ if environment is None else environment,
            port_probe=_loopback_port_available if port_probe is None else port_probe,
        )
    except V07RealWorkspaceRunError:
        raise
    except (V07CompatibilityError, V07DurableWorkspaceError) as exc:
        raise V07RealWorkspaceRunError(
            "REAL_WORKSPACE_INVALID", "a verified durable v0.7 workspace is required"
        ) from exc
    except OSError as exc:
        raise V07RealWorkspaceRunError(
            "REAL_RUN_PREFLIGHT_IO_FAILED", "local real-run preflight could not complete"
        ) from exc


def launch_real_v07_workspace(
    path: str | Path,
    *,
    expected_plan_fingerprint: str,
    environment: Mapping[str, str] | None = None,
    dry_run: bool = False,
    port_probe: PortProbe | None = None,
    process_runner: ProcessRunner | None = None,
) -> V07RealWorkspaceLaunchReceipt:
    """Confirm the current plan and run the fixed Streamlit process in the foreground."""

    source_environment = os.environ if environment is None else environment
    preflight = preflight_real_v07_workspace_run(
        path,
        environment=source_environment,
        port_probe=port_probe,
    )
    fingerprint = preflight.confirmation_fingerprint()
    if fingerprint != expected_plan_fingerprint:
        raise V07RealWorkspaceRunError(
            "REAL_RUN_PLAN_MISMATCH", "the current local run plan was not confirmed exactly"
        )
    if not preflight.launchable:
        raise V07RealWorkspaceRunError(
            "REAL_RUN_BLOCKED", "the confirmed local run plan has unresolved blockers"
        )
    if dry_run:
        return V07RealWorkspaceLaunchReceipt(
            workspace_handle=preflight.workspace_handle,
            plan_fingerprint=fingerprint,
            dry_run=True,
            process_started=False,
            foreground_process_completed=False,
        )
    try:
        workspace = Path(path).resolve(strict=True)
    except OSError as exc:
        raise V07RealWorkspaceRunError(
            "REAL_RUN_WORKSPACE_UNAVAILABLE", "the confirmed durable workspace is unavailable"
        ) from exc
    runtime_environment = dict(source_environment)
    runtime_environment["TRAFFICTWIN_WORKSPACE_PATH"] = str(workspace)
    runtime_environment["TRAFFICTWIN_REGISTRY_PATH"] = str(workspace / V07_ACTIVE_REGISTRY)
    command = _fixed_streamlit_command()
    runner = _run_foreground_process if process_runner is None else process_runner
    try:
        return_code = runner(command, runtime_environment)
    except OSError as exc:
        raise V07RealWorkspaceRunError(
            "REAL_RUN_PROCESS_FAILED", "the foreground Streamlit process could not start"
        ) from exc
    return V07RealWorkspaceLaunchReceipt(
        workspace_handle=preflight.workspace_handle,
        plan_fingerprint=fingerprint,
        dry_run=False,
        process_started=True,
        foreground_process_completed=True,
        return_code=return_code,
    )


def _preflight_real_v07_workspace_run(
    path: str | Path,
    *,
    environment: Mapping[str, str],
    port_probe: PortProbe,
) -> V07RealWorkspaceRunPreflight:
    workspace = Path(path).resolve(strict=True)
    inspection = inspect_v07_workspace(workspace)
    receipt = load_durable_workspace_receipt(workspace)
    expected_handle = _workspace_handle(workspace)
    if receipt.workspace_handle != expected_handle:
        raise V07RealWorkspaceRunError(
            "REAL_WORKSPACE_HANDLE_MISMATCH", "durable workspace identity changed"
        )
    if receipt.manifest_sha256 != inspection.manifest_sha256:
        raise V07RealWorkspaceRunError(
            "REAL_WORKSPACE_MANIFEST_MISMATCH", "durable workspace manifest changed"
        )
    blockers: list[str] = []
    bods = _bods_preflight(workspace, environment)
    national_highways = _national_highways_preflight(workspace, environment)
    blockers.extend(bods.operational_blockers)
    blockers.extend(national_highways.operational_blockers)
    available = port_probe(REAL_WORKSPACE_RUN_HOST, REAL_WORKSPACE_RUN_PORT)
    if not available:
        blockers.append("PORT_8502_UNAVAILABLE")
    app_path = _application_path()
    blocker_tuple = tuple(sorted(set(blockers)))
    return V07RealWorkspaceRunPreflight(
        workspace_handle=receipt.workspace_handle,
        durable_receipt_fingerprint=receipt.fingerprint(),
        workspace_manifest_sha256=inspection.manifest_sha256,
        active_registry_sha256=inspection.active_registry_sha256,
        application_entrypoint_sha256=_sha256_file(app_path),
        port_available=available,
        bods=bods,
        national_highways=national_highways,
        blockers=blocker_tuple,
        launchable=available and not blocker_tuple,
    )


def _bods_preflight(workspace: Path, environment: Mapping[str, str]) -> V07SourceRunPreflight:
    blockers: list[str] = []
    credential_present = _environment_value_present(environment, "BODS_API_KEY")
    try:
        interval = configured_bods_auto_refresh_seconds(environment)
    except BodsAutoRefreshError:
        interval = None
        interval_valid = False
        blockers.append("BODS_AUTO_REFRESH_INTERVAL_INVALID")
    else:
        interval_valid = True
    try:
        box = configured_bods_bounding_box(environment)
    except BodsAutoRefreshError:
        box = None
        scope_status: Literal["valid", "missing", "not_applicable", "invalid"] = "invalid"
        blockers.append("BODS_AUTO_REFRESH_SCOPE_INVALID")
    else:
        scope_status = "missing" if box is None else "valid"
    if not interval_valid or scope_status == "invalid":
        configuration_status: Literal["configured", "disabled", "not_configured", "invalid"] = (
            "invalid"
        )
    elif interval is None:
        configuration_status = "disabled"
    elif not credential_present or box is None:
        configuration_status = "not_configured"
    else:
        configuration_status = "configured"
    control_path = workspace / BODS_LIVE_CONTROL_RELATIVE_PATH
    try:
        state = load_bods_live_control_state(workspace)
        if os.path.lexists(control_path) and not _private_regular_file(control_path):
            raise BodsLiveControlError("CONTROL_STATE_INVALID", "control state is unsafe")
    except (BodsLiveControlError, OSError, ValueError):
        control_integrity: Literal["absent_valid", "valid", "invalid"] = "invalid"
        last_status: Literal["never", "succeeded", "failed", "in_progress"] = "never"
        last_fingerprint = None
        blockers.append("BODS_CONTROL_INVALID")
    else:
        control_integrity = "valid" if os.path.lexists(control_path) else "absent_valid"
        last_status = state.last_attempt_status
        last_fingerprint = (
            state.fingerprint() if state.last_attempt_status in {"succeeded", "failed"} else None
        )
    lock_status = _lock_status(workspace, BODS_LIVE_CONTROL_LOCK_RELATIVE_PATH)
    if lock_status != "available":
        blockers.append(f"BODS_LOCK_{lock_status.upper()}")
    scene_status, scene_count = _scene_status(
        workspace,
        ((BODS_LIVE_SCENE_RELATIVE_PATH, "live_vehicles", BODS_LIVE_SCENE_MAX_BYTES),),
    )
    if scene_status == "invalid":
        blockers.append("BODS_SCENE_INVALID")
    return V07SourceRunPreflight(
        source="bods",
        configuration_status=configuration_status,
        credential_environment_name="BODS_API_KEY",
        credential_present=credential_present,
        interval_environment_name=BODS_AUTO_REFRESH_ENV,
        interval_seconds=interval,
        request_scope_status=scope_status,
        request_scope_fingerprint=None if box is None else box.fingerprint(),
        control_integrity=control_integrity,
        lock_status=lock_status,
        last_terminal_status=last_status,
        last_terminal_state_fingerprint=last_fingerprint,
        scene_status=scene_status,
        local_scene_count=scene_count,
        contracts=V07SourceContractVersions(
            acquisition=BODS_ACQUISITION_METHOD_VERSION,
            source_schema=BODS_ACQUISITION_SCHEMA_VERSION,
            live_scene=BODS_LIVE_WORKFLOW_METHOD_VERSION,
            control=BODS_LIVE_CONTROL_METHOD_VERSION,
            freshness=BODS_FRESHNESS_POLICY_VERSION,
        ),
        enabled_for_process=configuration_status == "configured",
        operational_blockers=tuple(sorted(set(blockers))),
        policy_blockers=(
            "BODS_MULTI_DAY_IDENTIFIER_RETENTION_UNAPPROVED",
            "BODS_PUBLIC_ROW_OUTPUT_UNAPPROVED",
            "BODS_COMPLETE_BEE_SCOPE_UNAVAILABLE",
        ),
    )


def _national_highways_preflight(
    workspace: Path, environment: Mapping[str, str]
) -> V07SourceRunPreflight:
    blockers: list[str] = []
    credential_present = _environment_value_present(environment, "NATIONAL_HIGHWAYS_API_KEY")
    try:
        interval = configured_national_highways_auto_refresh_seconds(environment)
    except NationalHighwaysAutoRefreshError:
        interval = None
        interval_valid = False
        blockers.append("NATIONAL_HIGHWAYS_AUTO_REFRESH_INTERVAL_INVALID")
    else:
        interval_valid = True
    if not interval_valid:
        configuration_status: Literal["configured", "disabled", "not_configured", "invalid"] = (
            "invalid"
        )
    elif interval is None:
        configuration_status = "disabled"
    elif not credential_present:
        configuration_status = "not_configured"
    else:
        configuration_status = "configured"
    control_path = workspace / NATIONAL_HIGHWAYS_CONTROL_RELATIVE_PATH
    try:
        state = load_national_highways_control_state(workspace)
        if os.path.lexists(control_path) and not _private_regular_file(control_path):
            raise NationalHighwaysLiveError("CONTROL_STATE_INVALID", "control state is unsafe")
    except (NationalHighwaysLiveError, OSError, ValueError):
        control_integrity: Literal["absent_valid", "valid", "invalid"] = "invalid"
        last_status: Literal["never", "succeeded", "failed", "in_progress"] = "never"
        last_fingerprint = None
        blockers.append("NATIONAL_HIGHWAYS_CONTROL_INVALID")
    else:
        control_integrity = "valid" if os.path.lexists(control_path) else "absent_valid"
        last_status = state.last_attempt_status
        last_fingerprint = (
            state.fingerprint() if state.last_attempt_status in {"succeeded", "failed"} else None
        )
    lock_status = _lock_status(workspace, NATIONAL_HIGHWAYS_LOCK_RELATIVE_PATH)
    if lock_status != "available":
        blockers.append(f"NATIONAL_HIGHWAYS_LOCK_{lock_status.upper()}")
    scene_status, scene_count = _scene_status(
        workspace,
        (
            (NATIONAL_HIGHWAYS_LATEST_OVERLAY, "latest_available", MANCHESTER_SCENE_MAX_BYTES),
            (NATIONAL_HIGHWAYS_LIVE_OVERLAY, "live_vehicles", MANCHESTER_SCENE_MAX_BYTES),
        ),
    )
    if scene_status == "invalid":
        blockers.append("NATIONAL_HIGHWAYS_SCENE_INVALID")
    return V07SourceRunPreflight(
        source="national_highways",
        configuration_status=configuration_status,
        credential_environment_name="NATIONAL_HIGHWAYS_API_KEY",
        credential_present=credential_present,
        interval_environment_name=NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV,
        interval_seconds=interval,
        request_scope_status="not_applicable",
        control_integrity=control_integrity,
        lock_status=lock_status,
        last_terminal_status=last_status,
        last_terminal_state_fingerprint=last_fingerprint,
        scene_status=scene_status,
        local_scene_count=scene_count,
        contracts=V07SourceContractVersions(
            acquisition=NATIONAL_HIGHWAYS_ACQUISITION_VERSION,
            source_schema=NATIONAL_HIGHWAYS_SCHEMA_VERSION,
            live_scene=NATIONAL_HIGHWAYS_CONTROL_VERSION,
            control=NATIONAL_HIGHWAYS_CONTROL_VERSION,
        ),
        enabled_for_process=configuration_status == "configured",
        operational_blockers=tuple(sorted(set(blockers))),
        policy_blockers=(
            "NATIONAL_HIGHWAYS_STRATEGIC_ROAD_NETWORK_ONLY",
            "NATIONAL_HIGHWAYS_PROVIDER_SLA_UNAVAILABLE",
            "PUBLIC_HOSTING_UNAPPROVED",
        ),
    )


def _lock_status(workspace: Path, relative_path: Path) -> Literal["available", "busy", "unsafe"]:
    parent = workspace / relative_path.parent
    if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
        return "unsafe"
    target = workspace / relative_path
    if not os.path.lexists(target):
        return "available"
    if not _private_regular_file(target):
        return "unsafe"
    descriptor: int | None = None
    try:
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return "busy"
    except OSError:
        return "unsafe"
    finally:
        if descriptor is not None:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
    return "available"


def _scene_status(
    workspace: Path,
    scenes: Sequence[tuple[Path, Literal["latest_available", "live_vehicles"], int]],
) -> tuple[Literal["absent", "available", "partial", "invalid"], int]:
    found = 0
    for relative, expected_mode, maximum_bytes in scenes:
        target = workspace / relative
        if not _safe_workspace_parent(workspace, target.parent):
            return "invalid", found
        if not os.path.lexists(target):
            continue
        if not _private_regular_file(target) or target.stat().st_size > maximum_bytes:
            return "invalid", found
        try:
            payload = target.read_bytes()
            scene = ManchesterMapScene.model_validate_json(payload)
        except (OSError, ValueError):
            return "invalid", found
        if scene.mode != expected_mode or scene.canonical_json().encode("utf-8") != payload:
            return "invalid", found
        found += 1
    if not found:
        return "absent", 0
    if found == len(scenes):
        return "available", found
    return "partial", found


def _safe_workspace_parent(workspace: Path, parent: Path) -> bool:
    try:
        relative = parent.relative_to(workspace)
    except ValueError:
        return False
    cursor = workspace
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink() or (cursor.exists() and not cursor.is_dir()):
            return False
        if not cursor.exists():
            return True
    return True


def _private_regular_file(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    details = path.stat()
    return details.st_uid == os.getuid() and stat.S_IMODE(details.st_mode) & 0o077 == 0


def _environment_value_present(environment: Mapping[str, str], name: str) -> bool:
    value = environment.get(name)
    return value is not None and bool(value.strip())


def _loopback_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        try:
            candidate.bind((host, port))
        except OSError:
            return False
    return True


def _application_path() -> Path:
    return Path(__file__).resolve().parents[1] / "ui" / "app.py"


def _fixed_streamlit_command() -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(_application_path()),
        "--server.address",
        REAL_WORKSPACE_RUN_HOST,
        "--server.port",
        str(REAL_WORKSPACE_RUN_PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    )


def _run_foreground_process(command: Sequence[str], environment: Mapping[str, str]) -> int:
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell or caller command input.
        list(command),
        env=dict(environment),
        check=False,
    )
    return completed.returncode


def _workspace_handle(path: Path) -> str:
    return f"workspace-{_sha256_bytes(str(path).encode())[:16]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
