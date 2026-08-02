"""Focused app-shell tests for process-level source services."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import traffictwin.ui.app as app
from traffictwin.integration.manchester.national_highways_auto_refresh import (
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
