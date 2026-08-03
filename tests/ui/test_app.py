"""Focused app-shell tests for process-level source services."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.unit.test_manchester_bods_acquisition import BOX

import traffictwin.ui.app as app
from traffictwin.integration.manchester.bods_auto_refresh import (
    BodsAutoRefreshStatus,
)
from traffictwin.integration.manchester.national_highways_auto_refresh import (
    NationalHighwaysAutoRefreshError,
    NationalHighwaysAutoRefreshStatus,
)
from traffictwin.ui.state import UiConfig


def test_app_starts_secret_free_national_highways_worker_once_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace-v0.7"
    workspace.mkdir()
    session_state: dict[str, object] = {}
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state=session_state))
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "secret-test-key")
    monkeypatch.setattr(
        app,
        "configured_national_highways_auto_refresh_seconds",
        lambda: 300,
    )
    captured: dict[str, object] = {}
    expected = NationalHighwaysAutoRefreshStatus(
        running=True,
        interval_seconds=300,
        event_type="unplanned",
    )

    def ensure(
        workspace_root: str | Path,
        *,
        subscription_key: str,
        interval_seconds: int,
    ) -> NationalHighwaysAutoRefreshStatus:
        captured.update(
            workspace=workspace_root,
            subscription_key=subscription_key,
            interval_seconds=interval_seconds,
        )
        return expected

    monkeypatch.setattr(app, "ensure_national_highways_auto_refresh", ensure)

    status = app._ensure_configured_national_highways_auto_refresh(
        UiConfig(workspace_path=workspace)
    )

    assert status == expected
    assert captured == {
        "workspace": workspace,
        "subscription_key": "secret-test-key",
        "interval_seconds": 300,
    }
    assert "secret-test-key" not in repr(session_state)


def test_app_does_not_start_worker_without_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace-v0.7"
    workspace.mkdir()
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state={}))
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)

    assert (
        app._ensure_configured_national_highways_auto_refresh(UiConfig(workspace_path=workspace))
        is None
    )


def test_app_starts_secret_free_bods_worker_once_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace-v0.7"
    workspace.mkdir()
    session_state: dict[str, object] = {}
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state=session_state))
    monkeypatch.setenv("BODS_API_KEY", "secret-bods-key")
    monkeypatch.setattr(app, "configured_bods_auto_refresh_seconds", lambda: 60)
    monkeypatch.setattr(app, "configured_bods_bounding_box", lambda: BOX)
    captured: dict[str, object] = {}
    expected = BodsAutoRefreshStatus(
        running=True,
        interval_seconds=60,
        request_scope_fingerprint=BOX.fingerprint(),
    )

    def ensure(
        workspace_root: str | Path,
        bounding_box: object,
        *,
        api_key: str,
        interval_seconds: int,
    ) -> BodsAutoRefreshStatus:
        captured.update(
            workspace=workspace_root,
            bounding_box=bounding_box,
            api_key=api_key,
            interval_seconds=interval_seconds,
        )
        return expected

    monkeypatch.setattr(app, "ensure_bods_auto_refresh", ensure)

    status = app._ensure_configured_bods_auto_refresh(UiConfig(workspace_path=workspace))

    assert status == expected
    assert captured == {
        "workspace": workspace,
        "bounding_box": BOX,
        "api_key": "secret-bods-key",
        "interval_seconds": 60,
    }
    assert "secret-bods-key" not in repr(session_state)


def test_app_does_not_start_bods_worker_without_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace-v0.7"
    workspace.mkdir()
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state={}))
    monkeypatch.delenv("BODS_API_KEY", raising=False)

    assert app._ensure_configured_bods_auto_refresh(UiConfig(workspace_path=workspace)) is None


def test_one_source_worker_start_failure_does_not_block_the_other(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace-v0.7"
    workspace.mkdir()
    session_state: dict[str, object] = {}
    monkeypatch.setattr(app, "st", SimpleNamespace(session_state=session_state))
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "secret-highways-key")
    monkeypatch.setenv("BODS_API_KEY", "secret-bods-key")
    monkeypatch.setattr(app, "configured_national_highways_auto_refresh_seconds", lambda: 300)
    monkeypatch.setattr(app, "configured_bods_auto_refresh_seconds", lambda: 60)
    monkeypatch.setattr(app, "configured_bods_bounding_box", lambda: BOX)

    def fail_highways(*_args: object, **_kwargs: object) -> object:
        raise NationalHighwaysAutoRefreshError("TEST_HIGHWAYS_FAILURE", "safe failure")

    expected = BodsAutoRefreshStatus(
        running=True,
        interval_seconds=60,
        request_scope_fingerprint=BOX.fingerprint(),
    )
    monkeypatch.setattr(app, "ensure_national_highways_auto_refresh", fail_highways)
    monkeypatch.setattr(app, "ensure_bods_auto_refresh", lambda *_args, **_kwargs: expected)

    highways = app._ensure_configured_national_highways_auto_refresh(
        UiConfig(workspace_path=workspace)
    )
    bods = app._ensure_configured_bods_auto_refresh(UiConfig(workspace_path=workspace))

    assert highways is None
    assert bods == expected
    assert session_state["_national_highways_auto_refresh_error"] == "TEST_HIGHWAYS_FAILURE"
    assert "_bods_auto_refresh_error" not in session_state
    assert "secret-highways-key" not in repr(session_state)
    assert "secret-bods-key" not in repr(session_state)
