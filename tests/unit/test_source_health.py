from __future__ import annotations

import hashlib
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffictwin.integration.manchester.bods_live_control import (
    BODS_LIVE_CONTROL_RELATIVE_PATH,
)
from traffictwin.integration.manchester.operational_history import (
    OPERATIONAL_JOURNAL_RELATIVE_PATH,
)
from traffictwin.release.durable_workspace import (
    create_durable_v07_workspace,
    preview_durable_v07_workspace,
)
from traffictwin.ui.source_health import SourceHealthError, load_source_health

NOW = datetime(2026, 8, 3, 12, tzinfo=UTC)


def _workspace(tmp_path: Path) -> Path:
    parent = tmp_path / "private-owner-root"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    workspace = parent / "workspace-v0.7"
    preview = preview_durable_v07_workspace(workspace)
    create_durable_v07_workspace(
        workspace,
        expected_plan_fingerprint=preview.confirmation_fingerprint(),
        clock=lambda: NOW,
    )
    return workspace


def _configured() -> dict[str, str]:
    return {
        "BODS_API_KEY": "secret-bods-value",
        "TRAFFICTWIN_BODS_BOUNDING_BOX": "-2.60,53.30,-1.90,53.70",
        "NATIONAL_HIGHWAYS_API_KEY": "secret-highways-value",
    }


def _snapshot(workspace: Path) -> dict[str, tuple[str, int, str]]:
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


def test_configured_health_is_path_secret_identifier_network_and_mutation_free(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    before = _snapshot(workspace)

    report = load_source_health(workspace, environment=_configured(), clock=lambda: NOW)

    assert [row.source for row in report.sources] == ["BODS", "National Highways"]
    assert all(row.configuration_status == "configured" for row in report.sources)
    assert all(row.credential_present for row in report.sources)
    assert all(row.worker_status == "stopped" for row in report.sources)
    assert all(row.truth_state == "never" for row in report.sources)
    assert report.aggregate_journal_integrity == "absent_valid"
    assert report.network_request_performed is False
    assert report.workspace_mutated is False
    assert _snapshot(workspace) == before

    rendered = report.download_json()
    for excluded in (
        str(workspace),
        "secret-bods-value",
        "secret-highways-value",
        "-2.60",
        "request_scope_fingerprint",
        "workspace_handle",
    ):
        assert excluded not in rendered
    assert '"credential_presence_only":true' in rendered
    assert '"private_path_present":false' in rendered
    assert '"raw_identifier_present":false' in rendered


def test_absent_credentials_are_not_misreported_as_outages(tmp_path: Path) -> None:
    report = load_source_health(_workspace(tmp_path), environment={}, clock=lambda: NOW)

    assert all(row.configuration_status == "not_configured" for row in report.sources)
    assert all(row.worker_status == "not_configured" for row in report.sources)
    assert all(row.truth_state == "never" for row in report.sources)
    assert all(row.safe_failure_code is None for row in report.sources)


def test_invalid_control_and_journal_remain_explicit_without_leaking_content(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    control = workspace / BODS_LIVE_CONTROL_RELATIVE_PATH
    control.parent.mkdir(parents=True, exist_ok=True)
    control.write_text("private-control-garbage", encoding="utf-8")
    journal = workspace / OPERATIONAL_JOURNAL_RELATIVE_PATH
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("private-journal-garbage", encoding="utf-8")
    before = _snapshot(workspace)

    report = load_source_health(workspace, environment=_configured(), clock=lambda: NOW)

    bods, highways = report.sources
    assert bods.truth_state == "invalid"
    assert bods.worker_status == "degraded"
    assert "CONTROL_INVALID" in bods.operational_blockers
    assert report.aggregate_journal_integrity == "invalid"
    assert bods.long_term_integrity == "invalid"
    assert highways.long_term_integrity == "invalid"
    assert "private-control-garbage" not in report.download_json()
    assert "private-journal-garbage" not in report.download_json()
    assert _snapshot(workspace) == before


def test_unverified_workspace_fails_with_a_display_safe_error(tmp_path: Path) -> None:
    unsafe = tmp_path / "not-a-workspace"
    unsafe.mkdir()

    with pytest.raises(SourceHealthError) as raised:
        load_source_health(unsafe, environment={}, clock=lambda: NOW)

    assert raised.value.code == "SOURCE_HEALTH_WORKSPACE_INVALID"
    assert str(unsafe) not in str(raised.value)


def test_naive_health_clock_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SourceHealthError) as raised:
        load_source_health(
            _workspace(tmp_path),
            environment={},
            clock=lambda: datetime(2026, 8, 3, 12),
        )

    assert raised.value.code == "SOURCE_HEALTH_TIME_INVALID"
