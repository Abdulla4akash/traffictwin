"""Process-lifetime National Highways automatic-refresh control tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

import traffictwin.integration.manchester.national_highways_auto_refresh as auto
from traffictwin.integration.manchester.national_highways_live import (
    initial_national_highways_control_state,
)


@pytest.fixture(autouse=True)
def stop_workers() -> Iterator[None]:
    auto._stop_national_highways_auto_refresh_workers_for_tests()
    yield
    auto._stop_national_highways_auto_refresh_workers_for_tests()


def test_interval_defaults_disables_and_rejects_stale_configuration() -> None:
    assert auto.configured_national_highways_auto_refresh_seconds({}) == 300
    assert (
        auto.configured_national_highways_auto_refresh_seconds(
            {auto.NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV: "off"}
        )
        is None
    )
    assert (
        auto.configured_national_highways_auto_refresh_seconds(
            {auto.NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV: "60"}
        )
        == 60
    )
    with pytest.raises(auto.NationalHighwaysAutoRefreshError) as raised:
        auto.configured_national_highways_auto_refresh_seconds(
            {auto.NATIONAL_HIGHWAYS_AUTO_REFRESH_ENV: "600"}
        )
    assert raised.value.code == "AUTO_REFRESH_INTERVAL_INVALID"


def test_worker_starts_once_and_uses_automatic_trigger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace-v0.7"
    workspace.mkdir()
    refreshed = threading.Event()
    last_attempt: list[datetime | None] = [None]
    calls: list[tuple[Path, str, str]] = []

    def load_state(_workspace: str | Path) -> object:
        return initial_national_highways_control_state().model_copy(
            update={"last_attempt_at_utc": last_attempt[0]}
        )

    def refresh(
        workspace_root: str | Path,
        *,
        subscription_key: str,
        event_type: str,
        trigger: str,
    ) -> None:
        calls.append((Path(workspace_root), event_type, trigger))
        assert subscription_key == "secret-test-key"
        last_attempt[0] = datetime.now(UTC)
        refreshed.set()

    monkeypatch.setattr(auto, "load_national_highways_control_state", load_state)
    monkeypatch.setattr(auto, "coordinated_national_highways_refresh", refresh)

    first = auto.ensure_national_highways_auto_refresh(
        workspace,
        subscription_key="secret-test-key",
        interval_seconds=60,
    )
    second = auto.ensure_national_highways_auto_refresh(
        workspace,
        subscription_key="secret-test-key",
        interval_seconds=60,
    )

    assert first.running is True
    assert second.running is True
    assert refreshed.wait(timeout=1)
    deadline = time.monotonic() + 1
    status = auto.national_highways_auto_refresh_status(workspace)
    while status is not None and status.successes_in_process != 1 and time.monotonic() < deadline:
        time.sleep(0.01)
        status = auto.national_highways_auto_refresh_status(workspace)
    assert calls == [(workspace.resolve(), "unplanned", "automatic")]
    assert status is not None and status.successes_in_process == 1
    assert "secret-test-key" not in repr(status)
