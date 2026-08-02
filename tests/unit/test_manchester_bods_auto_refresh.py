"""Process-lifetime BODS automatic-refresh control tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

import traffictwin.integration.manchester.bods_auto_refresh as auto
from tests.unit.test_manchester_bods_acquisition import BOX
from traffictwin.integration.manchester.bods_live_control import (
    initial_bods_live_control_state,
)


@pytest.fixture(autouse=True)
def stop_workers() -> Iterator[None]:
    auto._stop_bods_auto_refresh_workers_for_tests()
    yield
    auto._stop_bods_auto_refresh_workers_for_tests()


def test_interval_defaults_disables_and_rejects_unsafe_configuration() -> None:
    assert auto.configured_bods_auto_refresh_seconds({}) == 60
    assert auto.configured_bods_auto_refresh_seconds({auto.BODS_AUTO_REFRESH_ENV: "off"}) is None
    assert auto.configured_bods_auto_refresh_seconds({auto.BODS_AUTO_REFRESH_ENV: "300"}) == 300
    for value in ("59", "301", "sometimes"):
        with pytest.raises(auto.BodsAutoRefreshError) as raised:
            auto.configured_bods_auto_refresh_seconds({auto.BODS_AUTO_REFRESH_ENV: value})
        assert raised.value.code == "BODS_AUTO_REFRESH_INTERVAL_INVALID"


def test_explicit_bounding_box_is_required_and_validated() -> None:
    assert auto.configured_bods_bounding_box({}) is None
    parsed = auto.configured_bods_bounding_box(
        {auto.BODS_BOUNDING_BOX_ENV: "-2.60, 53.30, -1.90, 53.70"}
    )
    assert parsed is not None
    assert parsed.fingerprint()
    for value in ("Manchester", "-1,53,-2,54"):
        with pytest.raises(auto.BodsAutoRefreshError) as raised:
            auto.configured_bods_bounding_box({auto.BODS_BOUNDING_BOX_ENV: value})
        assert raised.value.code == "BODS_AUTO_REFRESH_SCOPE_INVALID"


def test_worker_starts_once_and_uses_automatic_trigger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace-v0.7"
    workspace.mkdir()
    refreshed = threading.Event()
    last_attempt: list[datetime | None] = [None]
    calls: list[tuple[Path, str]] = []

    def load_state(_workspace: str | Path) -> object:
        return initial_bods_live_control_state().model_copy(
            update={"last_attempt_at_utc": last_attempt[0]}
        )

    def refresh(
        workspace_root: str | Path,
        _bounding_box: object,
        *,
        api_key: str,
        trigger: str,
    ) -> None:
        calls.append((Path(workspace_root), trigger))
        assert api_key == "secret-test-key"
        last_attempt[0] = datetime.now(UTC)
        refreshed.set()

    monkeypatch.setattr(auto, "load_bods_live_control_state", load_state)
    monkeypatch.setattr(auto, "coordinated_bods_live_refresh", refresh)

    first = auto.ensure_bods_auto_refresh(
        workspace,
        BOX,
        api_key="secret-test-key",
        interval_seconds=60,
    )
    second = auto.ensure_bods_auto_refresh(
        workspace,
        BOX,
        api_key="secret-test-key",
        interval_seconds=60,
    )

    assert first.running is True
    assert second.running is True
    assert refreshed.wait(timeout=1)
    deadline = time.monotonic() + 1
    status = auto.bods_auto_refresh_status(workspace)
    while status is not None and status.successes_in_process != 1 and time.monotonic() < deadline:
        time.sleep(0.01)
        status = auto.bods_auto_refresh_status(workspace)
    assert calls == [(workspace.resolve(), "automatic")]
    assert status is not None and status.successes_in_process == 1
    assert "secret-test-key" not in repr(status)
