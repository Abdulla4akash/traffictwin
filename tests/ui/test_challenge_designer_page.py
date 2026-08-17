"""AppTest coverage for the additive Challenge Designer route."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from typing import Any

from traffictwin.ui.challenge_whatif_bridge import (
    PENDING_WHATIF_CHALLENGE_DRAFT_KEY,
    is_valid_handoff_dict,
)
from traffictwin.ui.navigation_v07 import (
    CHALLENGE_DESIGNER_PAGE_SPEC,
    validate_v07_page_specs,
)
from traffictwin.ui.state import default_session_state, load_ui_config

PAGE_APP = "src/traffictwin/ui/app_pages/challenge_designer.py"


def _app() -> Any:  # noqa: ANN401 - house pattern for the dynamic AppTest import
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(PAGE_APP)
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _markdown(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(item.value) for item in app.markdown)


def _captions(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(item.value) for item in app.caption)


def test_the_route_is_additive_and_registered() -> None:
    validate_v07_page_specs()
    assert CHALLENGE_DESIGNER_PAGE_SPEC.group == "Platform"
    assert CHALLENGE_DESIGNER_PAGE_SPEC.url_path == "challenge-designer"


def test_make_harder_renders_three_distinct_bounded_candidates() -> None:
    app = _app().run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Task-arrival pressure" in markdown
    assert "Traffic-demand pressure" in markdown
    assert "Service-capacity pressure" in markdown
    prepare_buttons = [
        button for button in app.button if button.label == "Prepare in What-If Studio"
    ]
    assert len(prepare_buttons) == 3
    labels = [button.key for button in app.button]
    assert len(labels) == len(set(labels)), "button keys must stay unique"
    captions = _captions(app)
    assert "Prediction unavailable" in captions
    assert "OUTSIDE_SUPPORTED_ENVELOPE" in captions


def test_surprise_me_renders_distinct_mechanisms() -> None:
    app = _app()
    app.run(timeout=90)
    app.radio(key="challenge_designer_mode").set_value("Surprise me").run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "Policy/infrastructure interaction stress" in markdown
    assert "Localised incident pressure" in markdown
    assert "Demanding task-mix shift" in markdown


def test_placement_hypothesis_is_refused_not_approximated() -> None:
    app = _app()
    app.run(timeout=90)
    app.radio(key="challenge_designer_mode").set_value("Test a hypothesis").run(timeout=90)
    app.text_input(key="challenge_designer_free_text").set_value(
        "Create a scenario where infrastructure placement matters."
    ).run(timeout=90)
    assert not app.exception
    markdown = _markdown(app)
    assert "not currently representable" in markdown
    assert "Prepare in What-If Studio" not in [button.label for button in app.button]
    captions = _captions(app)
    assert "substitut" in captions.lower()


def test_unmatched_hypothesis_text_reports_insufficient_context() -> None:
    app = _app()
    app.run(timeout=90)
    app.radio(key="challenge_designer_mode").set_value("Test a hypothesis").run(timeout=90)
    app.text_input(key="challenge_designer_free_text").set_value("just make something fun").run(
        timeout=90
    )
    assert not app.exception
    assert "did not match the bounded hypothesis vocabulary" in _markdown(app)


def test_prepare_handoff_writes_a_valid_draft_and_requires_user_action() -> None:
    app = _app().run(timeout=90)
    assert app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] is None
    next(
        button for button in app.button if button.label == "Prepare in What-If Studio"
    ).click().run(timeout=90)
    assert not app.exception
    pending = app.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY]
    assert is_valid_handoff_dict(pending)
    assert pending["challenge_id"].startswith("challenge-candidate-")
    assert pending["whatif_overrides"] == {"task_arrival_rate": 0.225}
    assert pending["evidence_standing"].startswith("synthetic what-if proposal")
    assert app.session_state["_v07_pending_page"] == "What-If Studio"


def test_the_studio_shows_the_prepared_candidate_without_running() -> None:
    app = _app().run(timeout=90)
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
    assert "Prepared from challenge-candidate-" in studio_markdown
    assert studio.session_state["whatif_challenge_prefill_applied"] is True
    assert studio.session_state["whatif_task_arrival_rate"] == 0.225
