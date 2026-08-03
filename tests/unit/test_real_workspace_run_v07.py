from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

import traffictwin.cli as cli_module
from traffictwin.cli import app
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.release.durable_workspace import (
    create_durable_v07_workspace,
    preview_durable_v07_workspace,
)
from traffictwin.release.real_workspace_run import (
    REAL_WORKSPACE_RUN_HOST,
    REAL_WORKSPACE_RUN_PORT,
    V07RealWorkspaceRunError,
    launch_real_v07_workspace,
    preflight_real_v07_workspace_run,
)


def _durable_workspace(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    parent = tmp_path / "private-owner-root"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    workspace = parent / "workspace-v0.7"
    preview = preview_durable_v07_workspace(workspace)
    create_durable_v07_workspace(
        workspace,
        expected_plan_fingerprint=preview.confirmation_fingerprint(),
    )
    return workspace


def _configured_environment() -> dict[str, str]:
    return {
        "BODS_API_KEY": "secret-bods-value",
        "TRAFFICTWIN_BODS_BOUNDING_BOX": "-2.60,53.30,-1.90,53.70",
        "NATIONAL_HIGHWAYS_API_KEY": "secret-highways-value",
    }


def _workspace_snapshot(workspace: Path) -> dict[str, tuple[str, int, str]]:
    result: dict[str, tuple[str, int, str]] = {}
    for item in sorted(workspace.rglob("*")):
        relative = item.relative_to(workspace).as_posix()
        mode = stat.S_IMODE(item.lstat().st_mode)
        if item.is_symlink():
            result[relative] = ("symlink", mode, os.readlink(item))
        elif item.is_dir():
            result[relative] = ("directory", mode, "")
        else:
            result[relative] = ("file", mode, hashlib.sha256(item.read_bytes()).hexdigest())
    return result


def test_preflight_is_secret_path_network_and_mutation_free(tmp_path: Path) -> None:
    workspace = _durable_workspace(tmp_path)
    before = _workspace_snapshot(workspace)

    plan = preflight_real_v07_workspace_run(
        workspace,
        environment=_configured_environment(),
        port_probe=lambda host, port: (
            host == REAL_WORKSPACE_RUN_HOST and port == REAL_WORKSPACE_RUN_PORT
        ),
    )

    assert plan.launchable is True
    assert plan.port == 8502
    assert plan.port_separated_from_synthetic_demo is True
    assert plan.bods.configuration_status == "configured"
    assert plan.bods.interval_seconds == 60
    assert plan.bods.enabled_for_process is True
    assert plan.national_highways.configuration_status == "configured"
    assert plan.national_highways.interval_seconds == 300
    assert plan.national_highways.enabled_for_process is True
    assert plan.bods.control_integrity == "absent_valid"
    assert plan.national_highways.control_integrity == "absent_valid"
    assert plan.network_request_performed is False
    assert _workspace_snapshot(workspace) == before
    rendered = plan.model_dump_json()
    assert str(workspace) not in rendered
    assert "secret-bods-value" not in rendered
    assert "secret-highways-value" not in rendered
    assert "-2.60" not in rendered


def test_missing_credentials_are_not_configured_without_false_outage(tmp_path: Path) -> None:
    workspace = _durable_workspace(tmp_path)

    plan = preflight_real_v07_workspace_run(
        workspace,
        environment={},
        port_probe=lambda _host, _port: True,
    )

    assert plan.launchable is True
    assert plan.bods.configuration_status == "not_configured"
    assert plan.bods.enabled_for_process is False
    assert plan.bods.last_terminal_status == "never"
    assert plan.national_highways.configuration_status == "not_configured"
    assert plan.national_highways.enabled_for_process is False
    assert plan.blockers == ()


def test_invalid_configuration_and_busy_port_block_launch(tmp_path: Path) -> None:
    workspace = _durable_workspace(tmp_path)
    environment = {
        "BODS_API_KEY": "one",
        "TRAFFICTWIN_BODS_BOUNDING_BOX": "Manchester",
        "TRAFFICTWIN_BODS_AUTO_REFRESH_SECONDS": "12",
        "NATIONAL_HIGHWAYS_API_KEY": "two",
        "TRAFFICTWIN_NATIONAL_HIGHWAYS_AUTO_REFRESH_SECONDS": "600",
    }

    plan = preflight_real_v07_workspace_run(
        workspace,
        environment=environment,
        port_probe=lambda _host, _port: False,
    )

    assert plan.launchable is False
    assert plan.bods.configuration_status == "invalid"
    assert plan.national_highways.configuration_status == "invalid"
    assert set(plan.blockers) == {
        "BODS_AUTO_REFRESH_INTERVAL_INVALID",
        "BODS_AUTO_REFRESH_SCOPE_INVALID",
        "NATIONAL_HIGHWAYS_AUTO_REFRESH_INTERVAL_INVALID",
        "PORT_8502_UNAVAILABLE",
    }


def test_corrupt_control_unsafe_scene_and_busy_lock_are_reported(tmp_path: Path) -> None:
    workspace = _durable_workspace(tmp_path)
    live = workspace / "manchester/live"
    live.mkdir(mode=0o700)
    live.chmod(0o700)
    control = live / "bods-refresh-state.json"
    control.write_bytes(b"not canonical state")
    control.chmod(0o600)
    scenes = workspace / "manchester/scenes"
    scenes.mkdir(mode=0o700)
    scenes.chmod(0o700)
    (scenes / "live_vehicles.json").symlink_to(control)
    lock = live / ".national-highways-refresh.lock"
    lock.touch(mode=0o600)
    lock.chmod(0o600)
    descriptor = os.open(lock, os.O_RDWR)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        plan = preflight_real_v07_workspace_run(
            workspace,
            environment={},
            port_probe=lambda _host, _port: True,
        )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    assert plan.launchable is False
    assert plan.bods.control_integrity == "invalid"
    assert plan.bods.scene_status == "invalid"
    assert plan.national_highways.lock_status == "busy"
    assert "BODS_CONTROL_INVALID" in plan.blockers
    assert "BODS_SCENE_INVALID" in plan.blockers
    assert "NATIONAL_HIGHWAYS_LOCK_BUSY" in plan.blockers


def test_plan_binds_scope_and_interval_but_never_credential_value(tmp_path: Path) -> None:
    workspace = _durable_workspace(tmp_path)
    first_environment = _configured_environment()
    first = preflight_real_v07_workspace_run(
        workspace,
        environment=first_environment,
        port_probe=lambda _host, _port: True,
    )
    rotated_environment = {
        **first_environment,
        "BODS_API_KEY": "rotated-bods-secret",
        "NATIONAL_HIGHWAYS_API_KEY": "rotated-highways-secret",
    }
    rotated = preflight_real_v07_workspace_run(
        workspace,
        environment=rotated_environment,
        port_probe=lambda _host, _port: True,
    )
    changed_scope = preflight_real_v07_workspace_run(
        workspace,
        environment={
            **rotated_environment,
            "TRAFFICTWIN_BODS_BOUNDING_BOX": "-2.50,53.30,-1.90,53.70",
        },
        port_probe=lambda _host, _port: True,
    )

    assert first.confirmation_fingerprint() == rotated.confirmation_fingerprint()
    assert first.confirmation_fingerprint() != changed_scope.confirmation_fingerprint()
    assert "rotated-bods-secret" not in rotated.canonical_json()
    assert "rotated-highways-secret" not in rotated.canonical_json()


def test_launch_requires_exact_plan_and_dry_run_is_non_mutating(tmp_path: Path) -> None:
    workspace = _durable_workspace(tmp_path)
    environment = _configured_environment()
    plan = preflight_real_v07_workspace_run(
        workspace,
        environment=environment,
        port_probe=lambda _host, _port: True,
    )
    before = _workspace_snapshot(workspace)

    with pytest.raises(V07RealWorkspaceRunError, match="REAL_RUN_PLAN_MISMATCH"):
        launch_real_v07_workspace(
            workspace,
            expected_plan_fingerprint="0" * 64,
            environment=environment,
            dry_run=True,
            port_probe=lambda _host, _port: True,
        )
    receipt = launch_real_v07_workspace(
        workspace,
        expected_plan_fingerprint=plan.confirmation_fingerprint(),
        environment=environment,
        dry_run=True,
        port_probe=lambda _host, _port: True,
    )

    assert receipt.dry_run is True
    assert receipt.process_started is False
    assert receipt.return_code is None
    assert _workspace_snapshot(workspace) == before
    assert str(workspace) not in receipt.model_dump_json()


def test_foreground_runner_receives_only_fixed_argv_and_child_environment(tmp_path: Path) -> None:
    workspace = _durable_workspace(tmp_path)
    environment = _configured_environment()
    plan = preflight_real_v07_workspace_run(
        workspace,
        environment=environment,
        port_probe=lambda _host, _port: True,
    )
    captured: dict[str, object] = {}

    def runner(command: Sequence[str], child_environment: Mapping[str, str]) -> int:
        captured["command"] = tuple(command)
        captured["environment"] = dict(child_environment)
        return 7

    receipt = launch_real_v07_workspace(
        workspace,
        expected_plan_fingerprint=plan.confirmation_fingerprint(),
        environment=environment,
        port_probe=lambda _host, _port: True,
        process_runner=runner,
    )

    command = captured["command"]
    assert isinstance(command, tuple)
    assert command[1:4] == ("-m", "streamlit", "run")
    assert command[-8:] == (
        "--server.address",
        "127.0.0.1",
        "--server.port",
        "8502",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    )
    child = captured["environment"]
    assert isinstance(child, dict)
    assert child["BODS_API_KEY"] == "secret-bods-value"
    assert child["NATIONAL_HIGHWAYS_API_KEY"] == "secret-highways-value"
    assert child["TRAFFICTWIN_WORKSPACE_PATH"] == str(workspace)
    assert child["TRAFFICTWIN_REGISTRY_PATH"] == str(workspace / "registry/traffictwin.sqlite")
    assert receipt.return_code == 7
    assert receipt.process_started is True
    assert "secret-bods-value" not in receipt.model_dump_json()
    assert str(workspace) not in receipt.model_dump_json()


def test_non_durable_or_moved_workspace_refuses_with_path_free_error(tmp_path: Path) -> None:
    plain = tmp_path / "plain-v0.7"
    initialise_v07_workspace(plain)
    with pytest.raises(V07RealWorkspaceRunError) as missing_receipt:
        preflight_real_v07_workspace_run(
            plain,
            environment={},
            port_probe=lambda _host, _port: True,
        )
    assert missing_receipt.value.code == "REAL_WORKSPACE_INVALID"
    assert str(plain) not in str(missing_receipt.value)

    workspace = _durable_workspace(tmp_path / "move-case")
    moved = workspace.parent / "moved-v0.7"
    workspace.rename(moved)
    with pytest.raises(V07RealWorkspaceRunError) as moved_error:
        preflight_real_v07_workspace_run(
            moved,
            environment={},
            port_probe=lambda _host, _port: True,
        )
    assert moved_error.value.code == "REAL_WORKSPACE_HANDLE_MISMATCH"
    assert str(moved) not in str(moved_error.value)


def test_cli_preflight_and_dry_launch_are_path_and_secret_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _durable_workspace(tmp_path)
    environment = _configured_environment()
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    def preflight(path: Path) -> object:
        return preflight_real_v07_workspace_run(
            path,
            environment=environment,
            port_probe=lambda _host, _port: True,
        )

    monkeypatch.setattr(cli_module, "preflight_real_v07_workspace_run", preflight)
    runner = CliRunner()
    preview = runner.invoke(
        app,
        ["release", "v07-real-preflight", str(workspace), "--format", "json"],
    )
    assert preview.exit_code == 0, preview.output
    payload = json.loads(preview.output)

    def launch(path: Path, *, expected_plan_fingerprint: str, dry_run: bool) -> object:
        return launch_real_v07_workspace(
            path,
            expected_plan_fingerprint=expected_plan_fingerprint,
            environment=environment,
            dry_run=dry_run,
            port_probe=lambda _host, _port: True,
        )

    monkeypatch.setattr(cli_module, "launch_real_v07_workspace", launch)
    launched = runner.invoke(
        app,
        [
            "release",
            "v07-real-launch",
            str(workspace),
            "--expected-plan",
            payload["plan_fingerprint"],
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert launched.exit_code == 0, launched.output
    assert str(workspace) not in preview.output + launched.output
    assert "secret-bods-value" not in preview.output + launched.output
    assert "secret-highways-value" not in preview.output + launched.output
