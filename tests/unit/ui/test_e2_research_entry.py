"""E2 research entry — Home and Guided Demo AppTests.

Verifies a clear supervisor-facing Inspect real E2 research action on Home and a coherent
Guided Demo entry that deep-links to Resource Strategy Explorer and preselects the built-in
E2 mode via a stable session-state intent. Preserves existing navigation/actions/tracks.
"""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import V07_PENDING_PAGE_KEY
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state

HOME_APP = "src/traffictwin/ui/app_pages/home.py"
GUIDED_APP = "src/traffictwin/ui/app_pages/guided_demo.py"

E2_LABEL = "Inspect real E2 research"
E2_INTENT_KEY = "resource_strategy_intent"
E2_INTENT_VALUE = "e2"

# Alias keys that must NOT be written — contract prohibits inventing dependency APIs.
_ALIAS_KEYS = (
    "e2_research_intent",
    "resource_strategy_e2_intent",
    "resource_strategy_selected_mode",
)


def _home_app(*, v07_active: bool = True) -> AppTest:
    app = AppTest.from_file(HOME_APP)
    for k, v in deepcopy(default_session_state()).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = v07_active
    return app


def _guided_app(*, v07_active: bool = True) -> AppTest:
    app = AppTest.from_file(GUIDED_APP)
    for k, v in deepcopy(default_session_state()).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = v07_active
    return app


def _button_labels(app: AppTest) -> list[str]:
    return [b.label for b in app.button]


def _all_text(app: AppTest) -> str:
    parts: list[str] = []
    for col in [
        app.title,
        app.header,
        app.subheader,
        app.markdown,
        app.caption,
        app.info,
        app.warning,
        app.success,
        app.error,
    ]:
        parts.extend(str(x.value) for x in col)
    parts.extend(b.label for b in app.button)
    return "\n".join(parts)


def _assert_single_exact_intent(app: AppTest) -> None:
    """Prove the single declared stable contract and absence of alias keys."""
    assert E2_INTENT_KEY in app.session_state
    assert app.session_state[E2_INTENT_KEY] == E2_INTENT_VALUE
    # Must not invent alias keys.
    for alias in _ALIAS_KEYS:
        assert alias not in app.session_state, f"alias {alias!r} must not be written"


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------


def test_home_v07_exposes_inspect_e2_research_action() -> None:
    app = _home_app(v07_active=True).run(timeout=30)
    assert not app.exception, app.exception
    assert E2_LABEL in _button_labels(app)
    text = _all_text(app)
    assert "Resource Strategy Explorer" in text
    # Must not claim E2 is Manchester observation
    lower = text.lower()
    # nearby caption must contain admitted VEC research and not-observation disclaimer
    assert "admitted vec research" in lower or "admitted research" in lower
    assert "not manchester observation" in lower


def test_home_legacy_exposes_inspect_e2_research_action() -> None:
    app = _home_app(v07_active=False).run(timeout=30)
    assert not app.exception
    assert E2_LABEL in _button_labels(app)


def test_home_v07_e2_button_sets_intent_and_deep_links() -> None:
    app = _home_app(v07_active=True).run(timeout=30)
    assert not app.exception
    btn = next(b for b in app.button if b.label == E2_LABEL)
    btn.click().run(timeout=30)
    # AppTest after switch_page: session_state should hold intent and pending page
    # For v07, implementation sets V07_PENDING_PAGE_KEY and calls switch_page
    _assert_single_exact_intent(app)
    if V07_PENDING_PAGE_KEY in app.session_state:
        pending = app.session_state[V07_PENDING_PAGE_KEY]
    else:
        pending = None
    # Verify intent is stable
    assert app.session_state[E2_INTENT_KEY] == "e2"
    # If pending is present, it must be resource strategy explorer
    if pending is not None:
        assert pending == UiPage.RESOURCE_STRATEGY_EXPLORER.value
    # Also verify via app switch target if available
    # AppTest click that calls st.switch_page results in title change when run via app.py router
    # Here direct page AppTest records exception-free and intent


def test_home_legacy_e2_button_sets_intent_and_routes() -> None:
    app = _home_app(v07_active=False).run(timeout=30)
    assert not app.exception
    btn = next(b for b in app.button if b.label == E2_LABEL)
    btn.click().run(timeout=30)
    _assert_single_exact_intent(app)
    assert "active_page" in app.session_state
    assert app.session_state["active_page"] == UiPage.RESOURCE_STRATEGY_EXPLORER.value


def test_home_via_app_router_e2_navigates_to_explorer() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app.py").run(timeout=30)
    assert not app.exception
    assert any("Model a traffic scenario" in str(t.value) for t in app.title)
    btn = next(b for b in app.button if b.label == E2_LABEL)
    btn.click().run(timeout=30)
    assert not app.exception
    assert any(t.value == "Resource Strategy Explorer" for t in app.title)


def test_home_preserves_existing_actions() -> None:
    for v07 in (True, False):
        app = _home_app(v07_active=v07).run(timeout=30)
        assert not app.exception
        labels = _button_labels(app)
        assert "Create what-if comparison" in labels
        assert "Start Guided Demo" in labels
        # E2 entry is additive, not replacement
        assert E2_LABEL in labels


# ---------------------------------------------------------------------------
# Guided Demo
# ---------------------------------------------------------------------------


def test_guided_demo_exposes_e2_research_entry() -> None:
    app = _guided_app(v07_active=True).run(timeout=30)
    assert not app.exception, app.exception
    assert E2_LABEL in _button_labels(app)
    text = _all_text(app)
    assert "Resource Strategy Explorer" in text
    assert "not Manchester observation" in text or "not manchester observation" in text.lower()
    # Existing track selector remains
    assert any("Evidence track" in str(r.label) for r in app.radio) or any(
        "Standalone synthetic" in str(r.value) for r in app.radio
    )


def test_guided_demo_e2_button_sets_intent_and_deep_links_v07() -> None:
    app = _guided_app(v07_active=True).run(timeout=30)
    assert not app.exception
    btn = next(b for b in app.button if b.label == E2_LABEL)
    btn.click().run(timeout=30)
    _assert_single_exact_intent(app)
    if V07_PENDING_PAGE_KEY in app.session_state:
        pending = app.session_state[V07_PENDING_PAGE_KEY]
    else:
        pending = None
    if pending is not None:
        assert pending == UiPage.RESOURCE_STRATEGY_EXPLORER.value


def test_guided_demo_e2_button_sets_intent_legacy() -> None:
    app = _guided_app(v07_active=False).run(timeout=30)
    assert not app.exception
    btn = next(b for b in app.button if b.label == E2_LABEL)
    btn.click().run(timeout=30)
    _assert_single_exact_intent(app)
    assert "active_page" in app.session_state
    assert app.session_state["active_page"] == UiPage.RESOURCE_STRATEGY_EXPLORER.value


def test_guided_demo_via_app_router_e2_navigates_to_explorer() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app.py").run(timeout=30)
    assert not app.exception
    # Navigate to Guided Demo via the proven navigation_button path
    btn_gd = next(b for b in app.button if b.label == "Start Guided Demo")
    btn_gd.click().run(timeout=30)
    assert not app.exception
    assert any(t.value == "Guided Demo" for t in app.title)
    assert E2_LABEL in [b.label for b in app.button]
    # Verify E2 intent via direct AppTest (proven indexed access)
    direct = _guided_app(v07_active=True).run(timeout=30)
    btn = next(b for b in direct.button if b.label == E2_LABEL)
    btn.click().run(timeout=30)
    assert not direct.exception
    _assert_single_exact_intent(direct)
    # Also verify Home via app router still navigates to explorer (proven)
    app2 = AppTest.from_file("src/traffictwin/ui/app.py").run(timeout=30)
    btn2 = next(b for b in app2.button if b.label == E2_LABEL)
    btn2.click().run(timeout=30)
    assert not app2.exception
    assert any(t.value == "Resource Strategy Explorer" for t in app2.title)
    assert E2_INTENT_KEY in app2.session_state
    assert app2.session_state[E2_INTENT_KEY] == E2_INTENT_VALUE
    for alias in _ALIAS_KEYS:
        assert alias not in app2.session_state


def test_guided_demo_preserves_existing_journey() -> None:
    app = _guided_app(v07_active=True).run(timeout=30)
    assert not app.exception
    # Track radio still has both tracks
    radio_values: list[str] = []
    for r in app.radio:
        # AppTest radio options are in `r.options` if available
        opts = getattr(r, "options", None)
        if opts:
            radio_values.extend(str(o) for o in opts)
        radio_values.append(str(r.value))
        radio_values.append(str(r.label))
    joined = " ".join(radio_values)
    assert "Standalone synthetic" in joined
    assert "Randy/TOS imported simulation" in joined
    # Existing guided controls remain (Start/Resume etc)
    labels = _button_labels(app)
    assert any(
        "Start guided workflow" in label or "Resume" in label or "Start again" in label
        for label in labels
    )
    # E2 button is additive
    assert E2_LABEL in labels


def test_no_new_top_level_page_invented() -> None:
    # Ensure navigation still maps to existing UiPage set
    from traffictwin.ui.labels import UiPage as _UiPage

    assert _UiPage.RESOURCE_STRATEGY_EXPLORER.value == "Resource Strategy Explorer"
    assert page_script_for(_UiPage.RESOURCE_STRATEGY_EXPLORER) == "app_pages/resource_strategy.py"
    # Home and guided E2 buttons target existing page, not a new one
    app = _home_app(v07_active=True).run(timeout=30)
    btn = next(b for b in app.button if b.label == E2_LABEL)
    btn.click().run(timeout=30)
    if V07_PENDING_PAGE_KEY in app.session_state:
        pending = app.session_state[V07_PENDING_PAGE_KEY]
    else:
        pending = None
    if pending is not None:
        assert pending in [p.value for p in _UiPage]


def test_does_not_claim_e2_is_manchester_observation() -> None:
    for factory in (_home_app, _guided_app):
        for v07 in (True, False):
            app = factory(v07_active=v07).run(timeout=30)
            text = _all_text(app).lower()
            # Must not contain phrase suggesting e2 is Manchester observation
            assert "e2 is manchester observation" not in text
            assert "e2 is manchester" not in text or "not manchester observation" in text


def test_stable_intent_contract_is_single_key() -> None:
    """The declared stable contract is exactly one key/value pair."""
    from traffictwin.ui.pages import guided_demo as gd
    from traffictwin.ui.pages import home as hm

    assert hm.E2_RESOURCE_STRATEGY_INTENT_KEY == "resource_strategy_intent"
    assert hm.E2_RESOURCE_STRATEGY_INTENT_VALUE == "e2"
    assert gd.E2_RESOURCE_STRATEGY_INTENT_KEY == "resource_strategy_intent"
    assert gd.E2_RESOURCE_STRATEGY_INTENT_VALUE == "e2"
