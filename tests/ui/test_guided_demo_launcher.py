"""AppTest coverage for the three-mode Guided Demo launcher."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

import httpx
from pytest import MonkeyPatch
from tests.unit.test_manchester_bods_acquisition import (
    API_KEY,
    BOX,
    make_clock,
    make_transport,
    siri_xml,
)
from tests.unit.test_manchester_webtris_acquisition import acquire, make_request

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.integration.manchester.bods_live_control import (
    coordinated_bods_live_refresh,
)
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.release.durable_workspace import (
    create_durable_v07_workspace,
    preview_durable_v07_workspace,
)
from traffictwin.ui.guided_demo_modes import (
    HistoricalDemoAssessment,
    LiveBusDemoAssessment,
)
from traffictwin.ui.guided_tour import (
    HISTORICAL_TOUR_STAGES,
    SYNTHETIC_TOUR_STAGES,
)
from traffictwin.ui.manchester_operations import (
    accepted_webtris_daily_options,
    load_local_webtris_catalogue,
    load_local_webtris_timeseries,
)
from traffictwin.ui.navigation_v07 import V07_PAGE_SPECS, validate_v07_page_specs
from traffictwin.ui.state import default_session_state, load_ui_config

GUIDED_APP = "src/traffictwin/ui/app_pages/guided_demo.py"

_MODE_BUTTON_LABELS = {
    "Start Synthetic Demo",
    "Start Live Bus Demo",
    "Start Historical Demo",
}


def _clean_bods_env(monkeypatch: MonkeyPatch) -> None:
    for name in (
        "BODS_API_KEY",
        "TRAFFICTWIN_BODS_BOUNDING_BOX",
        "TRAFFICTWIN_BODS_AUTO_REFRESH_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def _app() -> Any:  # noqa: ANN401 - house pattern for the dynamic AppTest import
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(GUIDED_APP)
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _click(app: Any, label: str) -> Any:  # noqa: ANN401
    return next(button for button in app.button if button.label == label).click().run(timeout=30)


def _markdown_text(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(item.value) for item in app.markdown)


def _caption_text(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(item.value) for item in app.caption)


def _durable_workspace(tmp_path: Path) -> Path:
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    workspace = parent / "workspace-v0.7"
    preview = preview_durable_v07_workspace(workspace)
    create_durable_v07_workspace(
        workspace,
        expected_plan_fingerprint=preview.confirmation_fingerprint(),
    )
    return workspace


class TestTheLandingPage:
    def test_exactly_three_demo_modes_are_offered(self, monkeypatch: MonkeyPatch) -> None:
        _clean_bods_env(monkeypatch)
        app = _app().run(timeout=40)
        assert not app.exception
        mode_buttons = [
            button for button in app.button if str(button.key).startswith("guided_demo_mode_")
        ]
        assert {button.label for button in mode_buttons} == _MODE_BUTTON_LABELS
        assert len(mode_buttons) == 3

    def test_the_manual_workflow_and_research_entries_stay_available(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        _clean_bods_env(monkeypatch)
        app = _app().run(timeout=40)
        labels = [button.label for button in app.button]
        assert "Start guided workflow" in labels
        assert "Inspect real E2 research" in labels
        assert "Inspect E3 Dynamic Resource V2" in labels
        assert any(radio.label == "Evidence track" for radio in app.radio)
        assert any(
            item.value == "Stage 1 of 9: Frame a reproducible experiment" for item in app.subheader
        )
        assert any(item.value == "Explore manually" for item in app.subheader)

    def test_the_grouped_navigation_contract_is_unchanged(self) -> None:
        validate_v07_page_specs()
        spec = next(spec for spec in V07_PAGE_SPECS if spec.script == "app_pages/guided_demo.py")
        assert spec.group == "Overview"
        assert spec.url_path == "guided-workflow"

    def test_the_page_modules_launch_no_research_workload(self) -> None:
        root = Path(__file__).resolve().parents[2] / "src" / "traffictwin" / "ui"
        sources = [
            root / "pages" / "guided_demo.py",
            root / "guided_demo_modes.py",
            root / "guided_tour.py",
            root / "guided_tour_runtime.py",
        ]
        for source in sources:
            text = source.read_text(encoding="utf-8")
            for forbidden in (
                "vec_campaign",
                "execute_campaign",
                "run_vec_evaluator",
                "subprocess",
                "time.sleep",
            ):
                assert forbidden not in text, f"{source.name} references {forbidden}"


class TestTheSyntheticDemo:
    def test_it_runs_without_any_bods_configuration(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        _clean_bods_env(monkeypatch)
        workspace = tmp_path / "demo"
        initialise_workspace(workspace)
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
        app = _app().run(timeout=40)
        app = _click(app, "Start Synthetic Demo")
        assert not app.exception
        state = app.session_state["guided_demo_tour"]
        assert state.mode.value == "synthetic"
        assert state.stage_index == 0
        markdown = _markdown_text(app)
        assert SYNTHETIC_TOUR_STAGES[0].title in markdown
        assert "SYNTHETIC" in markdown
        assert "LIVE BODS" not in markdown
        assert any(metric.label == "Trip record count" for metric in app.metric)

    def test_stages_progress_deterministically_with_next(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        _clean_bods_env(monkeypatch)
        workspace = tmp_path / "demo"
        initialise_workspace(workspace)
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
        app = _app().run(timeout=40)
        app = _click(app, "Start Synthetic Demo")
        for expected_index in range(1, len(SYNTHETIC_TOUR_STAGES)):
            app = _click(app, "Next")
            assert not app.exception
            state = app.session_state["guided_demo_tour"]
            assert state.stage_index == expected_index
            assert SYNTHETIC_TOUR_STAGES[expected_index].title in _markdown_text(app)
        app = _click(app, "Next")
        assert app.session_state["guided_demo_tour"].stage_index == (len(SYNTHETIC_TOUR_STAGES) - 1)

    def test_pause_stops_automatic_progression_and_previous_restart_work(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        _clean_bods_env(monkeypatch)
        workspace = tmp_path / "demo"
        initialise_workspace(workspace)
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
        app = _app().run(timeout=40)
        app = _click(app, "Start Synthetic Demo")
        app = _click(app, "Next")
        app = _click(app, "Pause")
        paused = app.session_state["guided_demo_tour"]
        assert paused.playing is False
        for _ in range(3):
            app = app.run(timeout=30)
        held = app.session_state["guided_demo_tour"]
        assert held.stage_index == paused.stage_index
        assert held.elapsed_in_stage_seconds == paused.elapsed_in_stage_seconds
        app = _click(app, "Previous")
        assert app.session_state["guided_demo_tour"].stage_index == 0
        app = _click(app, "Play")
        assert app.session_state["guided_demo_tour"].playing is True
        app = _click(app, "Next")
        app = _click(app, "Restart")
        restarted = app.session_state["guided_demo_tour"]
        assert restarted.stage_index == 0
        assert restarted.playing is True
        app = _click(app, "Exit demo")
        assert "guided_demo_tour" not in app.session_state
        assert any(button.label == "Start Synthetic Demo" for button in app.button)


class TestTheLiveBusDemo:
    def test_it_fails_closed_without_bods_configuration(self, monkeypatch: MonkeyPatch) -> None:
        _clean_bods_env(monkeypatch)
        monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
        app = _app().run(timeout=40)
        app = _click(app, "Start Live Bus Demo")
        assert not app.exception
        markdown = _markdown_text(app)
        assert "Live Bus Demo unavailable" in markdown
        assert "BODS is not currently configured for this workspace." in markdown
        labels = [button.label for button in app.button]
        assert "Open Source Health" in labels
        assert "Open Manchester Operations" in labels
        assert "Exit demo" in labels

    def test_it_never_silently_uses_synthetic_evidence(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        workspace = _durable_workspace(tmp_path)
        with httpx.Client(transport=make_transport(siri_xml(), [])) as client:
            coordinated_bods_live_refresh(
                workspace,
                BOX,
                api_key=API_KEY,
                synthetic=True,
                http_client=client,
                utc_now=make_clock(),
            )
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        monkeypatch.setenv("BODS_API_KEY", "launcher-test-secret")
        monkeypatch.setenv("TRAFFICTWIN_BODS_BOUNDING_BOX", "-2.4,53.3,-2.1,53.6")
        app = _app().run(timeout=40)
        app = _click(app, "Start Live Bus Demo")
        assert not app.exception
        markdown = _markdown_text(app)
        assert "Live Bus Demo unavailable" in markdown
        assert "SYNTHETIC_EVIDENCE_REFUSED" in _caption_text(app)
        assert "never falls back to synthetic" in _caption_text(app)
        assert not app.metric
        rendered = markdown + _caption_text(app)
        assert "launcher-test-secret" not in rendered
        assert str(workspace) not in rendered

    def test_the_ready_display_labels_accepted_snapshots_honestly(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """Display-path test: the gate is stubbed, the rendering is real."""

        workspace = _durable_workspace(tmp_path)
        with httpx.Client(transport=make_transport(siri_xml(), [])) as client:
            refresh = coordinated_bods_live_refresh(
                workspace,
                BOX,
                api_key=API_KEY,
                synthetic=True,
                http_client=client,
                utc_now=make_clock(),
            )
        stub = LiveBusDemoAssessment(
            status="ready",
            reason="ready",
            message="stubbed for display testing",
            summary=refresh.refresh.summary,
            scene=refresh.refresh.scene,
            scope_configured=True,
            auto_refresh_interval_seconds=60,
        )
        monkeypatch.setattr(
            "traffictwin.ui.pages.guided_demo.assess_live_bus_demo",
            lambda *args, **kwargs: stub,
        )
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        app = _app().run(timeout=40)
        app = _click(app, "Start Live Bus Demo")
        assert not app.exception
        assert any(metric.label == "Accepted bus positions" for metric in app.metric)
        captions = _caption_text(app)
        assert "Latest accepted source snapshot evaluated at" in captions
        assert "not a new provider observation" in captions
        markdown = _markdown_text(app)
        assert "LIVE BODS" in markdown
        assert "BUS POSITIONS ONLY" in markdown
        assert "DETERMINISTIC" not in markdown


class TestTheHistoricalDemo:
    def test_it_fails_closed_without_accepted_evidence(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        _clean_bods_env(monkeypatch)
        workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        app = _app().run(timeout=40)
        app = _click(app, "Start Historical Demo")
        assert not app.exception
        markdown = _markdown_text(app)
        assert "Historical Demo unavailable" in markdown
        assert "No accepted historical evidence is currently available." in markdown
        labels = [button.label for button in app.button]
        assert "Open Manchester Operations" in labels
        assert "Exit demo" in labels

    def test_it_refuses_synthetic_flagged_evidence(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        _clean_bods_env(monkeypatch)
        workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
        acquire(workspace, make_request())
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        app = _app().run(timeout=40)
        app = _click(app, "Start Historical Demo")
        assert not app.exception
        assert "Historical Demo unavailable" in _markdown_text(app)
        assert "SYNTHETIC_ONLY_EVIDENCE" in _caption_text(app)
        assert "never substitutes synthetic data" in _caption_text(app)

    def test_the_ready_display_walks_all_six_stages(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """Display-path test: the gate is stubbed, the rendering is real."""

        workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
        acquire(workspace, make_request())
        catalogue = load_local_webtris_catalogue(workspace)
        assert catalogue.catalogue is not None
        snapshot = accepted_webtris_daily_options(catalogue.catalogue)[0]
        loaded = load_local_webtris_timeseries(
            workspace, snapshot.snapshot_id, ("observed", "missing")
        )
        assert loaded.result is not None
        stub = HistoricalDemoAssessment(
            status="ready",
            reason="ready",
            message="stubbed for display testing",
            snapshot=snapshot,
            timeseries=loaded.result,
        )
        monkeypatch.setattr(
            "traffictwin.ui.pages.guided_demo.assess_historical_demo",
            lambda *args, **kwargs: stub,
        )
        monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
        app = _app().run(timeout=40)
        app = _click(app, "Start Historical Demo")
        assert not app.exception
        markdown = _markdown_text(app)
        assert HISTORICAL_TOUR_STAGES[0].title in markdown
        assert "HISTORICAL" in markdown
        assert "Accepted historical source" in markdown
        for expected_index in range(1, len(HISTORICAL_TOUR_STAGES)):
            app = _click(app, "Next")
            assert not app.exception
            assert HISTORICAL_TOUR_STAGES[expected_index].title in _markdown_text(app)
        assert "Interpretation" in _markdown_text(app)
        assert "not synthetic" in _caption_text(app)
