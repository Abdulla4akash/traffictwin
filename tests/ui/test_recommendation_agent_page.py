"""AppTest coverage for the additive Recommendation Agent route."""

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
    RECOMMENDATION_AGENT_PAGE_SPEC,
    validate_v07_page_specs,
)
from traffictwin.ui.state import default_session_state, load_ui_config

PAGE_APP = "src/traffictwin/ui/app_pages/recommendation_agent.py"


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("recommendation-agent-ui") / "demo"
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


def _subheaders(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(item.value) for item in app.subheader)


def test_the_route_is_additive_and_registered() -> None:
    validate_v07_page_specs()
    assert RECOMMENDATION_AGENT_PAGE_SPEC.group == "Platform"
    assert RECOMMENDATION_AGENT_PAGE_SPEC.url_path == "recommendation-agent"
    assert RECOMMENDATION_AGENT_PAGE_SPEC.script == "app_pages/recommendation_agent.py"


def test_the_feature_modules_contain_no_execution_surface() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "traffictwin"
    sources = [
        root / "analyst" / "decision.py",
        root / "analyst" / "decision_questions.py",
        root / "analyst" / "decision_prose.py",
        root / "ui" / "pages" / "recommendation_agent.py",
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
            "bods",
            "randomTrips",
            "netconvert",
            "kubernetes",
            "def train",
            "torch",
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
    assert "Current finding: Infrastructure/resource-side investigation" in markdown
    assert "Why this is first" in markdown
    assert "Investigate capacity or service provision" in markdown
    assert "Why not retrain yet?" in _subheaders(app)
    assert "infrastructure_explanation_excluded" in markdown
    assert any("LLM_NOT_CONFIGURED" in str(item.value) for item in app.info)
    labels = [button.label for button in app.button]
    assert len(labels) == len(set(labels)), "button labels must stay unique"
    assert len(app.title) == 1


def test_model_case_never_commands_retraining(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "under_offloading"),
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Current finding: Model/policy-side investigation" in markdown
    assert "offloading decision distribution" in markdown
    lowered = markdown.lower()
    assert "must retrain" not in lowered
    assert "retraining is required" not in lowered
    assert "last resort" in lowered


def test_no_material_problem_recommends_no_change(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(baseline=str(demo_workspace / "bundles" / "baseline")).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Current finding: No intervention signal" in markdown
    assert "No change: no intervention is indicated" in markdown


def test_insufficient_case_recommends_a_controlled_comparison(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "stressed_demand"),
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Current finding: Insufficient evidence" in markdown
    assert "Run a controlled scenario comparison" in markdown


def test_an_empty_selection_shows_the_typed_refusal(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app().run(timeout=60)
    assert not app.exception
    assert "No evidence subject is selected" in _markdown(app)
    assert "NO_SELECTED_RUN" in _captions(app)


def test_bounded_question_answers_from_the_decision(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    select = next(
        item for item in app.selectbox if item.key == "recommendation_agent_question_preset"
    )
    select.select("Should I retrain the model?").run(timeout=60)
    next(
        item for item in app.button if item.key == "recommendation_agent_question_answer"
    ).click().run(timeout=60)
    assert not app.exception
    markdown = _markdown(app)
    assert "Should I retrain the model?" in markdown
    assert (
        "Not on the current evidence" in " ".join(str(item.value) for item in app.text) + markdown
    )


def test_an_unrecognised_free_text_question_is_refused(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    text_input = next(
        item for item in app.text_input if item.key == "recommendation_agent_question_text"
    )
    text_input.set_value("please deploy this to production").run(timeout=60)
    next(
        item for item in app.button if item.key == "recommendation_agent_question_answer"
    ).click().run(timeout=60)
    assert not app.exception
    assert any("UNRECOGNISED_QUESTION" in str(item.value) for item in app.warning)


def test_whatif_handoff_is_a_reviewable_proposal_only(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Open What-If Challenge to prepare this" in labels
    captions = _captions(app)
    assert "generation stays an explicit human act" in captions


def test_llm_failure_preserves_the_deterministic_decision(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture" + "-page-key")

    def _refuse(*args: object, **kwargs: object) -> object:
        raise AnalystProseError("LLM_TIMEOUT", "DeepSeek could not be reached")

    monkeypatch.setattr("traffictwin.ui.pages.recommendation_agent.render_decision_prose", _refuse)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    next(
        item for item in app.checkbox if item.key == "recommendation_agent_llm_consent"
    ).check().run(timeout=60)
    next(item for item in app.button if item.key == "recommendation_agent_llm_explain").click().run(
        timeout=60
    )
    assert not app.exception
    assert any("LLM_TIMEOUT" in str(item.value) for item in app.warning)
    assert "Current finding: Infrastructure/resource-side investigation" in _markdown(app)


def test_provenance_authority_and_download_are_shown(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    markdown = _markdown(app)
    assert "analyst_packet:" in markdown
    assert "recommendation_packet:" in markdown
    assert "EXECUTION AUTHORITY: NONE" in markdown
    assert any(button.label == "Download decision (JSON)" for button in app.download_button)
