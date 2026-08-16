"""AppTest coverage for the additive What-If Challenge route."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

from traffictwin.analyst.prose import AnalystProseError
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.challenge_whatif_bridge import (
    PENDING_WHATIF_CHALLENGE_DRAFT_KEY,
    is_valid_handoff_dict,
)
from traffictwin.ui.navigation_v07 import (
    WHATIF_CHALLENGE_PAGE_SPEC,
    validate_v07_page_specs,
)
from traffictwin.ui.state import default_session_state, load_ui_config

PAGE_APP = "src/traffictwin/ui/app_pages/whatif_challenge.py"


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("whatif-challenge-ui") / "demo"
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
    assert WHATIF_CHALLENGE_PAGE_SPEC.group == "Platform"
    assert WHATIF_CHALLENGE_PAGE_SPEC.url_path == "whatif-challenge"
    assert WHATIF_CHALLENGE_PAGE_SPEC.script == "app_pages/whatif_challenge.py"


def test_the_feature_modules_contain_no_execution_surface() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "traffictwin"
    sources = [
        root / "analyst" / "challenge.py",
        root / "analyst" / "challenge_prose.py",
        root / "ui" / "pages" / "whatif_challenge.py",
    ]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for forbidden in (
            "subprocess",
            "vec_campaign",
            "execute_campaign",
            "run_vec_evaluator",
            "generate_whatif_pair",
            "generate_synthetic_bundle",
            "coordinated_bods_live_refresh",
            "randomTrips",
            "netconvert",
        ):
            assert forbidden not in text, f"{source.name} references {forbidden}"


def test_capacity_challenge_renders_completely_without_llm(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Vary service capacity under a fixed model and scenario" in markdown
    assert "Variable under investigation" in markdown
    assert "policy_profile" in markdown, "held-fixed controls must be visible"
    assert any("LLM_NOT_CONFIGURED" in str(item.value) for item in app.info)
    labels = [button.label for button in app.button]
    assert len(labels) == len(set(labels)), "button labels must stay unique"
    for forbidden in ("Run", "Execute experiment", "Start simulation"):
        assert forbidden not in labels
    assert "Prepare in What-If Studio" in labels


def test_model_challenge_requires_a_registered_profile_choice(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "under_offloading"),
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Compare registered offloading-policy profiles" in markdown
    assert "NEEDS_USER_INPUT" in _captions(app)
    labels = [button.label for button in app.button]
    assert "Prepare in What-If Studio" not in labels, (
        "an unresolved choice must block the prefill handoff"
    )


def test_scenario_challenge_gates_on_the_dimension_choice(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "stressed_demand"),
    ).run(timeout=90)
    assert not app.exception
    assert "Vary one scenario dimension" in _markdown(app)
    assert "NEEDS_USER_INPUT" in _captions(app)


def test_no_actionable_case_manufactures_no_challenge(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(baseline=str(demo_workspace / "bundles" / "baseline")).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "No actionable What-If challenge is justified" in markdown
    assert "Prepare in What-If Studio" not in [button.label for button in app.button]


def test_the_prepare_handoff_writes_a_valid_draft_and_executes_nothing(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    workspace_before = sorted(str(path) for path in (demo_workspace / "bundles").iterdir())
    next(
        button for button in app.button if button.label == "Prepare in What-If Studio"
    ).click().run(timeout=90)
    assert not app.exception
    pending = app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY]
    assert is_valid_handoff_dict(pending)
    assert pending["challenge_id"].startswith("whatif-challenge-")
    assert pending["whatif_overrides"] == {"rsu_capacity": 22.0}
    assert app.session_state["_v07_pending_page"] == "What-If Studio"
    workspace_after = sorted(str(path) for path in (demo_workspace / "bundles").iterdir())
    assert workspace_after == workspace_before, "the handoff must not generate bundles"


def test_the_studio_shows_the_prepared_draft_without_running(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    next(
        button for button in app.button if button.label == "Prepare in What-If Studio"
    ).click().run(timeout=90)
    pending = app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY]

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    studio = app_test.from_file("src/traffictwin/ui/app_pages/whatif_studio.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        studio.session_state[key] = value
    studio.session_state["_v07_navigation_active"] = True
    studio.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = pending
    studio.run(timeout=90)
    assert not studio.exception
    studio_markdown = " ".join(str(item.value) for item in studio.markdown)
    assert "Prepared from whatif-challenge-" in studio_markdown
    assert studio.session_state["whatif_challenge_prefill_applied"] is True
    assert studio.session_state["whatif_rsu_capacity"] == 22.0


def test_llm_failure_preserves_the_deterministic_challenge(
    monkeypatch: MonkeyPatch, demo_workspace: Path
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture" + "-challenge-page-key")

    def _refuse(*args: object, **kwargs: object) -> object:
        raise AnalystProseError("LLM_TIMEOUT", "DeepSeek could not be reached")

    monkeypatch.setattr("traffictwin.ui.pages.whatif_challenge.render_challenge_prose", _refuse)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    next(item for item in app.checkbox if item.key == "whatif_challenge_llm_consent").check().run(
        timeout=60
    )
    next(item for item in app.button if item.key == "whatif_challenge_llm_explain").click().run(
        timeout=60
    )
    assert not app.exception
    assert any("LLM_TIMEOUT" in str(item.value) for item in app.warning)
    assert "Vary service capacity under a fixed model and scenario" in _markdown(app)


def test_provenance_chain_is_shown(monkeypatch: MonkeyPatch, demo_workspace: Path) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = _app(
        baseline=str(demo_workspace / "bundles" / "baseline"),
        variation=str(demo_workspace / "bundles" / "infrastructure_bottleneck"),
    ).run(timeout=90)
    markdown = _markdown(app)
    assert "Analyst packet:" in markdown
    assert "Recommendation packet:" in markdown
    assert "Challenge specification:" in markdown
    assert any(
        button.label == "Download challenge specification (JSON)" for button in app.download_button
    )
