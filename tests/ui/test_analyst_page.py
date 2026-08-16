"""AppTest coverage for the additive TrafficTwin Analyst route."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from traffictwin.analyst.prose import AnalystProseError
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.navigation_v07 import ANALYST_PAGE_SPEC, validate_v07_page_specs
from traffictwin.ui.state import default_session_state, load_ui_config

ANALYST_APP = "src/traffictwin/ui/app_pages/analyst.py"


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("analyst-ui") / "demo"
    initialise_workspace(workspace)
    return workspace


def _app(
    *,
    baseline: str | None = None,
    variation: str | None = None,
) -> Any:  # noqa: ANN401 - house pattern for the dynamic AppTest import
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(ANALYST_APP)
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.session_state["selected_baseline_run"] = baseline or ""
    app.session_state["selected_variation_run"] = variation or ""
    return app


def _markdown(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(item.value) for item in app.markdown)


def _captions(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(item.value) for item in app.caption)


def test_the_analyst_route_is_additive_and_registered() -> None:
    validate_v07_page_specs()
    assert ANALYST_PAGE_SPEC.group == "Platform"
    assert ANALYST_PAGE_SPEC.url_path == "analyst"
    assert ANALYST_PAGE_SPEC.script == "app_pages/analyst.py"


def test_the_analyst_modules_contain_no_execution_surface() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "traffictwin"
    sources = [
        root / "analyst" / "models.py",
        root / "analyst" / "packet.py",
        root / "analyst" / "classify.py",
        root / "analyst" / "prose.py",
        root / "ui" / "pages" / "analyst.py",
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "vec_campaign",
            "execute_campaign",
            "run_vec_evaluator",
            "randomTrips",
            "netconvert",
            "posix_spawn",
            "coordinated_bods_live_refresh",
            "retrain",
        ):
            assert forbidden not in text, f"{source.name} references {forbidden}"


def test_without_llm_configuration_the_analysis_is_complete(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Infrastructure-side signal" in markdown
    assert any("LLM_NOT_CONFIGURED" in str(item.value) for item in app.info)
    assert "SYNTHETIC" in markdown
    assert "ADMITTED RESEARCH" not in markdown
    labels = [button.label for button in app.button]
    assert len(labels) == len(set(labels)), "button labels must stay unique"
    assert any(metric.label for metric in app.metric)


def test_an_empty_selection_shows_the_typed_refusal(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app().run(timeout=60)
    assert not app.exception
    assert "Analyst has no selected evidence" in _markdown(app)
    assert "NO_SELECTED_RUN" in _captions(app)


def test_a_causal_question_is_refused_typed(monkeypatch: MonkeyPatch, demo_workspace: Path) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(baseline=str(demo_workspace / "bundles" / "baseline")).run(timeout=60)
    free_text = next(
        item for item in app.text_input if item.label == "Ask in your own words (optional)"
    )
    free_text.set_value("prove what caused this").run(timeout=60)
    assert not app.exception
    assert any("UNSUPPORTED_CAUSAL_REQUEST" in str(item.value) for item in app.warning)


def test_llm_failure_falls_back_to_the_deterministic_result(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture" + "-analyst-key")

    def _refuse(*args: object, **kwargs: object) -> object:
        raise AnalystProseError("LLM_TIMEOUT", "DeepSeek could not be reached")

    monkeypatch.setattr("traffictwin.ui.pages.analyst.render_analyst_prose", _refuse)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "under_offloading"),
    ).run(timeout=90)
    next(item for item in app.checkbox if item.key == "analyst_llm_consent").check().run(timeout=60)
    next(item for item in app.button if item.key == "analyst_llm_explain").click().run(timeout=60)
    assert not app.exception
    assert any("LLM_TIMEOUT" in str(item.value) for item in app.warning)
    assert "Model-side signal" in _markdown(app), "deterministic finding must remain"


def test_an_incompatible_pair_is_refused_on_the_page(
    monkeypatch: MonkeyPatch, demo_workspace: Path, tmp_path: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from traffictwin.synthetic.bundles import write_synthetic_bundle
    from traffictwin.synthetic.scenarios import preset_config

    other = write_synthetic_bundle(
        preset_config("baseline", random_seed=9), tmp_path / "baseline-seed9"
    )
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(other),
    ).run(timeout=90)
    assert not app.exception
    assert "INCOMPATIBLE_PAIR" in _captions(app)
    assert "Infrastructure-side signal" not in _markdown(app)
