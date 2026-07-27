"""AppTest coverage for the additive RSU Monitor page."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch
from tests.tos_helpers import write_tos_package

from traffictwin.ui.services import ServiceError, inspect_tos_for_ui
from traffictwin.ui.state import default_session_state, load_ui_config

RUN_KEY = "baseline_uk2030_wd_am_fs0"


def _app(monkeypatch: MonkeyPatch, tmp_path: Path) -> Any:  # noqa: ANN401 - AppTest is loaded dynamically
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(tmp_path / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path / "workspace"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/rsu_monitor.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _app_with_package(monkeypatch: MonkeyPatch, tmp_path: Path) -> Any:  # noqa: ANN401 - AppTest is loaded dynamically
    package = write_tos_package(tmp_path / "tos")
    view = inspect_tos_for_ui(package, deep=False)
    assert not isinstance(view, ServiceError)
    app = _app(monkeypatch, tmp_path)
    app.session_state["latest_tos_package_view"] = view
    app.session_state["selected_tos_data_path"] = str(package)
    return app


def test_page_states_it_is_replay_and_asks_for_a_package_first(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path)
    app.run(timeout=20)

    assert not app.exception
    assert any(title.value == "RSU Monitor" for title in app.title)
    captions = " ".join(str(caption.value) for caption in app.caption)
    assert "not CPU utilisation" in captions
    assert "never live" in captions or "not live" in captions.lower()
    info_values = " ".join(str(info.value) for info in app.info)
    assert "TOS Data package" in info_values


def test_page_renders_per_rsu_load_for_an_imported_run(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app_with_package(monkeypatch, tmp_path)
    # Stride 1 keeps every recorded step of the three-step house fixture.
    app.session_state["rsu_monitor_stride"] = 1
    app.run(timeout=30)

    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    # The house fixture records a single RSU whose load runs 1, 2, 1.
    assert metrics["RSUs in window"] == "1"
    assert metrics["Sampled points"] == "3"
    assert metrics["Peak in-flight tasks"] == "2"
    captions = " ".join(str(caption.value) for caption in app.caption)
    assert RUN_KEY in captions
    assert "single RSU" in captions
    subheaders = " ".join(str(header.value) for header in app.subheader)
    assert "Load asymmetry across all RSUs" in subheaders
    assert "One RSU over the window" in subheaders


def test_stride_downsamples_the_window_without_interpolating(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app_with_package(monkeypatch, tmp_path)
    app.run(timeout=30)

    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    # The default stride of 10 over a three-step fixture keeps only step 0;
    # the page reports exactly what it sampled rather than filling the gap.
    assert metrics["Stride"] == "10"
    assert metrics["Sampled points"] == "1"
    assert metrics["Peak in-flight tasks"] == "1"


def test_selection_control_lists_the_windows_rsus(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    app = _app_with_package(monkeypatch, tmp_path)
    app.run(timeout=30)

    assert not app.exception
    selector = next(box for box in app.selectbox if box.label.startswith("RSU (listed busiest"))
    assert list(selector.options) == ["rsu-index:0"]
    run_selector = next(box for box in app.selectbox if box.label == "Instrumented run")
    assert RUN_KEY in list(run_selector.options)


def test_absent_measurements_are_stated_not_filled(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app_with_package(monkeypatch, tmp_path)
    app.run(timeout=30)

    assert not app.exception
    warnings = " ".join(str(warning.value) for warning in app.warning)
    assert "per-RSU energy over the window" in warnings
    assert "per-RSU processed-task count" in warnings
    assert "unavailable" in warnings
