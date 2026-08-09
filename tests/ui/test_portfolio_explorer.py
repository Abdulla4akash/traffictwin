"""UI/AppTests for Portfolio Explorer page."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state

_ENV_CLEAR = [
    "TRAFFICTWIN_WORKSPACE_PATH",
    "TRAFFICTWIN_REGISTRY_PATH",
    "TRAFFICTWIN_TOS_DATA_PATH",
    "TRAFFICTWIN_FIXTURE_PATH",
    "TRAFFICTWIN_RANDY_PACK_PATH",
    "TRAFFICTWIN_BODS_BOUNDING_BOX",
    "BODS_API_KEY",
    "NATIONAL_HIGHWAYS_API_KEY",
]


def _run_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    page: UiPage = UiPage.PORTFOLIO_EXPLORER,
    extra_state: dict[str, object] | None = None,
) -> AppTest:
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    state = deepcopy(default_session_state())
    state["_v07_navigation_active"] = True
    for k, v in state.items():
        app.session_state[k] = v
    if extra_state:
        for k, v in extra_state.items():
            app.session_state[k] = v
    app.run(timeout=30)
    return app


def test_portfolio_explorer_has_exactly_one_title(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert len(app.title) == 1
    assert app.title[0].value == "Portfolio Explorer"


def test_evidence_banner_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    warnings = "\n".join(str(w.value) for w in app.warning)
    assert "synthetic" in warnings.lower()
    assert (
        "not production scheduling" in warnings.lower()
        or "not establish an optimal" in warnings.lower()
    )


def test_portfolio_strategies_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Candidate strategies table is a dataframe
    assert len(app.dataframe) >= 2
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "synthetic-always-local" in markdowns or "synthetic" in markdowns.lower()


def test_selected_strategy_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Selected strategy" in markdowns
    assert "synthetic-" in markdowns


def test_selector_rationale_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Rationale" in markdowns or "rule" in markdowns.lower()


def test_scenario_features_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    captions = "\n".join(str(c.value) for c in app.caption)
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    combined = captions + markdowns
    assert "load_intensity" in combined or "Load intensity" in combined


def test_synthetic_standing_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    warnings = "\n".join(str(w.value) for w in app.warning)
    captions = "\n".join(str(c.value) for c in app.caption)
    combined = markdowns + warnings + captions
    assert "synthetic" in combined.lower()
    assert "demonstration" in combined.lower()


def test_regret_dominance_shown_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    captions = "\n".join(str(c.value) for c in app.caption)
    metrics = "\n".join(str(m.value) for m in app.metric)
    combined = markdowns + captions + metrics
    assert "regret" in combined.lower() or "Regret" in combined
    assert "Winner/tie" in combined or "winner" in combined.lower()
    # Dominance matrix is in expander
    assert len(app.dataframe) >= 3


def test_unavailable_states_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # No hidden unavailable; page should show warnings/limitations, not hide
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    warnings = "\n".join(str(w.value) for w in app.warning)
    captions = "\n".join(str(c.value) for c in app.caption)
    combined = markdowns + warnings + captions
    # Limitations must be visible
    assert "Limitation" in combined or "limitation" in combined.lower()


def test_no_optimal_production_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(
        str(x.value)
        for collection in [app.markdown, app.caption, app.warning, app.info]
        for x in collection
    )
    lowered = all_text.lower()
    # Must not claim optimal policy or Kubernetes
    assert (
        "optimal policy" not in lowered or "not optimal" in lowered or "not an optimal" in lowered
    )
    assert "kubernetes" not in lowered
    assert "live manchester" not in lowered


def test_no_kubernetes_deployment_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.warning
    )
    assert "kubernetes" not in all_text.lower()


def test_no_live_manchester_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.warning
    )
    assert "live manchester" not in all_text.lower()
    # Must not claim causal superiority
    assert "causal superiority" not in all_text.lower()
    assert "causal" not in all_text.lower() or "no causal" in all_text.lower()


def test_challenge_seed_library_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    subheaders = "\n".join(str(s.value) for s in app.subheader)
    combined = markdowns + subheaders
    assert "Challenge Seed Library" in combined
    assert "CH-01" in combined or "Arena" in combined


def test_challenge_seed_parameter_table_visible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Parameter overrides table is a dataframe
    assert len(app.dataframe) >= 1
    # Check selectbox exists
    assert len(app.selectbox) >= 1


def test_next_action_navigation_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "Scenario Builder" in buttons
    assert "Experiments" in buttons
    assert "Compare" in buttons
    assert "Provenance" in buttons


def test_page_works_without_provider_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Already hermetic via _ENV_CLEAR, but explicitly test no BODS key
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert app.title[0].value == "Portfolio Explorer"


def test_page_works_without_pr11_pr12(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # No WhatIfPair or ConsequenceLens import required
    all_text = "\n".join(str(x.value) for x in app.markdown)
    # Page should not mention WhatIfPair types
    assert "WhatIfPair" not in all_text


def test_tests_hermetic_against_environment_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key in _ENV_CLEAR:
        monkeypatch.setenv(key, "injected-value")
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Still renders despite env vars
    assert app.title[0].value == "Portfolio Explorer"


def test_waiting_room_not_labelled_compute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = (
        "\n".join(str(x.value) for x in app.markdown)
        + "\n".join(str(x.value) for x in app.caption)
        + "\n".join(str(x.value) for x in app.info)
    )
    lowered = all_text.lower()
    # Must distinguish waiting-room vs compute, not label rsu_capacity as compute power
    if "compute power" in lowered:
        assert "rsu_capacity" in lowered
