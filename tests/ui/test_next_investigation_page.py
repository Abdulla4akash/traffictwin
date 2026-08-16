"""AppTest coverage for the additive Next Investigation route."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from traffictwin.analyst.prose import AnalystProseError
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.navigation_v07 import (
    NEXT_INVESTIGATION_PAGE_SPEC,
    validate_v07_page_specs,
)
from traffictwin.ui.state import default_session_state, load_ui_config

PAGE_APP = "src/traffictwin/ui/app_pages/next_investigation.py"


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("next-investigation-ui") / "demo"
    initialise_workspace(workspace)
    return workspace


def _app(
    *,
    baseline: str | None = None,
    variation: str | None = None,
) -> Any:  # noqa: ANN401 - house pattern for the dynamic AppTest import
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(PAGE_APP)
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


def test_the_route_is_additive_and_registered() -> None:
    validate_v07_page_specs()
    assert NEXT_INVESTIGATION_PAGE_SPEC.group == "Platform"
    assert NEXT_INVESTIGATION_PAGE_SPEC.url_path == "next-investigation"
    assert NEXT_INVESTIGATION_PAGE_SPEC.script == "app_pages/next_investigation.py"


def test_the_feature_modules_contain_no_execution_surface() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "traffictwin"
    sources = [
        root / "analyst" / "recommendation.py",
        root / "analyst" / "recommendation_prose.py",
        root / "ui" / "pages" / "next_investigation.py",
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "vec_campaign",
            "execute_campaign",
            "run_vec_evaluator",
            "generate_whatif_pair",
            "coordinated_bods_live_refresh",
            "randomTrips",
            "netconvert",
        ):
            assert forbidden not in text, f"{source.name} references {forbidden}"


def test_infrastructure_case_renders_completely_without_llm(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Analyst finding: Infrastructure-side signal" in markdown
    assert "Investigate infrastructure capacity constraints" in markdown
    assert "R2:" in markdown
    assert any("LLM_NOT_CONFIGURED" in str(item.value) for item in app.info)
    labels = [button.label for button in app.button]
    assert len(labels) == len(set(labels)), "button labels must stay unique"
    assert "Open Analyst" in labels


def test_model_side_case_renders_the_model_track(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "under_offloading"),
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Investigate the learned offloading policy" in markdown
    assert "Model-side track" in markdown
    lowered = markdown.lower()
    assert "must retrain" not in lowered
    assert "should be retrained" not in lowered
    assert "does not establish that retraining is required" in lowered


def test_unattributed_case_recommends_a_controlled_comparison(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "stressed_demand"),
    ).run(timeout=90)
    assert not app.exception
    assert "Investigate via a controlled scenario comparison" in _markdown(app)


def test_no_material_problem_fabricates_nothing(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(baseline=str(demo_workspace / "bundles" / "baseline")).run(timeout=90)
    assert not app.exception
    assert "No actionable problem detected" in _markdown(app)
    assert "No intervention is recommended" in _captions(app)


def test_an_empty_selection_shows_the_typed_refusal(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app().run(timeout=60)
    assert not app.exception
    assert "No evidence subject is selected" in _markdown(app)
    assert "NO_SELECTED_RUN" in _captions(app)


def test_an_incompatible_pair_fails_closed(
    monkeypatch: MonkeyPatch, demo_workspace: Path, tmp_path: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from traffictwin.synthetic.bundles import write_synthetic_bundle
    from traffictwin.synthetic.scenarios import preset_config

    other = write_synthetic_bundle(
        preset_config("baseline", random_seed=12), tmp_path / "baseline-seed12"
    )
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(other),
    ).run(timeout=90)
    assert not app.exception
    assert "INCOMPATIBLE_PAIR" in _captions(app)
    assert "Investigate" not in _markdown(app)


def test_llm_failure_preserves_the_deterministic_recommendation(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture" + "-page-key")

    def _refuse(*args: object, **kwargs: object) -> object:
        raise AnalystProseError("LLM_TIMEOUT", "DeepSeek could not be reached")

    monkeypatch.setattr(
        "traffictwin.ui.pages.next_investigation.render_recommendation_prose", _refuse
    )
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    next(item for item in app.checkbox if item.key == "next_investigation_llm_consent").check().run(
        timeout=60
    )
    next(item for item in app.button if item.key == "next_investigation_llm_explain").click().run(
        timeout=60
    )
    assert not app.exception
    assert any("LLM_TIMEOUT" in str(item.value) for item in app.warning)
    assert "Investigate infrastructure capacity constraints" in _markdown(app)


def test_provenance_and_fingerprints_are_shown(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    markdown = _markdown(app)
    assert "analyst_packet:" in markdown
    assert "baseline_bundle:" in markdown
    assert any(
        button.label == "Download recommendation packet (JSON)" for button in app.download_button
    )
    captions = _captions(app)
    assert "Prepare a What-If: Deferred" in captions
