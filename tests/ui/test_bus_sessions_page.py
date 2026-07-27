"""AppTest coverage for the additive Bus Sessions page."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.integration.manchester.bods_session_identity import (
    SessionCadenceMeasurement,
    SessionProgressionMeasurement,
)
from traffictwin.ui.bus_sessions_services import (
    CADENCE_ARTIFACT_NAME,
    PROGRESSION_ARTIFACT_NAME,
)
from traffictwin.ui.state import default_session_state, load_ui_config


def _cadence() -> SessionCadenceMeasurement:
    return SessionCadenceMeasurement(
        snapshot_ids=("snap-a", "snap-b"),
        snapshot_count=2,
        vehicles_seen_total=5,
        vehicles_linked_across_snapshots=4,
        observation_count=9,
        repeated_identical_fix_count=1,
        update_delta_seconds_median=60.0,
        update_delta_seconds_p90=61.0,
        update_delta_seconds_max=62.0,
        displacement_m_median=140.0,
        displacement_m_p90=180.0,
        displacement_m_max=200.0,
        implied_speed_mps_max=3.4,
    )


def _progression() -> SessionProgressionMeasurement:
    return SessionProgressionMeasurement(
        snapshot_ids=("snap-a", "snap-b"),
        hour_utc=(9, 8),
        segment_count_by_hour=(40, 12),
        speed_mps_median_by_hour=(6.5, 4.25),
        speed_mps_p90_by_hour=(9.0, 7.5),
        vehicles_contributing_by_hour=(11, 4),
    )


def _app(monkeypatch: MonkeyPatch, workspace: Path) -> Any:  # noqa: ANN401 - AppTest is loaded dynamically
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/bus_sessions.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _seed(workspace: Path, *, cadence: bool = True, progression: bool = True) -> Path:
    directory = workspace / "manchester"
    directory.mkdir(parents=True, exist_ok=True)
    if cadence:
        (directory / CADENCE_ARTIFACT_NAME).write_text(
            _cadence().model_dump_json(), encoding="utf-8"
        )
    if progression:
        (directory / PROGRESSION_ARTIFACT_NAME).write_text(
            _progression().model_dump_json(), encoding="utf-8"
        )
    return workspace


def test_page_states_its_boundaries_before_any_data(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)

    assert not app.exception
    assert any(title.value == "Bus Sessions" for title in app.title)
    captions = " ".join(str(caption.value) for caption in app.caption)
    assert "Aggregates only" in captions
    assert "never road-traffic speed" in captions
    assert "buses are never general traffic" in captions.lower()


def test_an_absent_workspace_directory_is_an_honest_unavailable_state(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)

    assert not app.exception
    info_values = " ".join(str(info.value) for info in app.info)
    assert "no Manchester directory" in info_values
    # Nothing is filled in with zeros.
    assert not app.dataframe


def test_recorded_aggregates_render_with_their_support(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = _seed(tmp_path / "workspace")
    app = _app(monkeypatch, workspace)
    app.run(timeout=20)

    assert not app.exception
    subheaders = " ".join(str(header.value) for header in app.subheader)
    assert "Session cadence" in subheaders
    assert "Hourly bus progression" in subheaders
    assert len(app.dataframe) == 2
    captions = " ".join(str(caption.value) for caption in app.caption)
    assert "owner_approved_candidate" in captions
    assert "salt is never persisted" in captions
    assert "segment and vehicle support" in captions


def test_a_missing_progression_artifact_is_stated_not_hidden(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = _seed(tmp_path / "workspace", progression=False)
    app = _app(monkeypatch, workspace)
    app.run(timeout=20)

    assert not app.exception
    warnings = " ".join(str(warning.value) for warning in app.warning)
    assert "session progression measurement" in warnings
    assert "unavailable" in warnings
    # The cadence table still renders; only progression is missing.
    assert len(app.dataframe) == 1


def test_no_token_or_raw_reference_reaches_the_page(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    workspace = _seed(tmp_path / "workspace")
    app = _app(monkeypatch, workspace)
    app.run(timeout=20)

    assert not app.exception
    rendered = " ".join(
        [
            *(str(caption.value) for caption in app.caption),
            *(str(warning.value) for warning in app.warning),
            *(str(header.value) for header in app.subheader),
            *(str(info.value) for info in app.info),
        ]
    )
    for forbidden in ("VehicleRef", "vehicle_ref", "session_token", "salt=", "snap-a"):
        assert forbidden not in rendered
