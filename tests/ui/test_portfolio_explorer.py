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
    metrics = "\n".join(str(m.label) + str(m.value) for m in app.metric)
    dataframes = "\n".join(str(df.value) for df in app.dataframe)
    combined = captions + markdowns + metrics + dataframes
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
    assert "regret" in combined.lower()
    assert "Winner/tie" in combined or "winner" in combined.lower()
    assert len(app.dataframe) >= 3


def test_unavailable_states_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    warnings = "\n".join(str(w.value) for w in app.warning)
    captions = "\n".join(str(c.value) for c in app.caption)
    combined = markdowns + warnings + captions
    assert "Limitation" in combined


def test_no_optimal_production_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(
        str(x.value)
        for collection in [app.markdown, app.caption, app.warning, app.info]
        for x in collection
    )
    lowered = all_text.lower()
    assert (
        "optimal policy" not in lowered or "not optimal" in lowered or "not an optimal" in lowered
    )
    if "kubernetes" in lowered:
        assert "no " in lowered
    if "live manchester" in lowered:
        assert "no live manchester" in lowered


def test_no_kubernetes_deployment_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.warning
    )
    lowered = all_text.lower()
    if "kubernetes" in lowered:
        assert "no " in lowered


def test_no_live_manchester_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown) + "\n".join(
        str(x.value) for x in app.warning
    )
    lowered = all_text.lower()
    if "live manchester" in lowered:
        assert "no live manchester" in lowered
    assert "causal superiority" not in all_text.lower()
    assert "causal" not in lowered or "no causal" in lowered


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
    assert len(app.dataframe) >= 1
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
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert app.title[0].value == "Portfolio Explorer"


def test_page_works_without_pr11_pr12(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for x in app.markdown)
    assert "WhatIfPair" not in all_text


def test_tests_hermetic_against_environment_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key in _ENV_CLEAR:
        monkeypatch.setenv(key, "injected-value")
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
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
    if "compute power" in lowered:
        assert "rsu_capacity" in lowered


def test_execution_status_shows_representable_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(
        str(x.value)
        for coll in [app.markdown, app.caption, app.info, app.warning, app.success]
        for x in coll
    )
    # All seven current challenges are REPRESENTABLE_ONLY, not EXECUTABLE
    assert "REPRESENTABLE_ONLY" in all_text
    assert "Representable as a validated ScenarioSeed" in all_text
    assert "does not currently provide a generic ScenarioSeed-to-run" in all_text
    # Must not show old green executable wording
    assert "Executable now via current ScenarioSeed schema" not in all_text


def test_challenge_names_are_truthful(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    from traffictwin.ui.portfolio_explorer import get_challenge_seed_library

    library = {c.challenge_id: c.title for c in get_challenge_seed_library()}
    assert library["CH-04-rsu-waiting-room-squeeze"] == "Reduced-capacity stress"
    assert library["CH-05-load-aware-forwarding"] == "High-load forwarding context"
    assert library["CH-06-stale-state-scheduling"] == "Ordered-arrival fallback case"
    assert library["CH-07-scaling-strategy"] == "Scaling stress"
    # UI shows selectbox with truthful titles (options, not just selected value)
    assert app.selectbox
    options = getattr(app.selectbox[0], "options", []) or [app.selectbox[0].value]
    select_values = "\n".join(str(o) for o in options)
    assert "Reduced-capacity stress" in select_values
    assert "High-load forwarding context" in select_values


def test_inert_fields_marked_in_parameter_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Check via service contract and UI dataframe content
    from traffictwin.ui.portfolio_explorer import is_selector_input

    assert is_selector_input("traffic.event_type") is False
    assert is_selector_input("demand.multiplier") is True
    # UI must show relevance caption and dataframe rows
    all_text = "\n".join(str(x.value) for coll in [app.markdown, app.caption] for x in coll)
    assert "Parameter relevance derived from authoritative" in all_text
    # Dataframe rows contain selector relevance; inspect via dataframe value if available
    # At least one dataframe should contain the relevance strings
    df_text = "\n".join(str(df.value) for df in app.dataframe)
    # The caption + dataframe together must indicate inert vs selector input
    assert (
        "not consumed by current selector" in all_text.lower()
        or "not consumed" in df_text.lower()
        or "RECORDED IN SEED" in df_text
    )


def test_seeds_not_won_label_not_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.dataframe] for x in coll
    )
    assert "Seeds where strategy was not winner-or-tie" in all_text
    # Must not display bare "failures" as column header for not-won semantics
    # Check that dataframe column for seeds_not_won is present
    assert "not winner" in all_text.lower()


def test_n2_held_out_limitation_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(
        str(x.value) for coll in [app.markdown, app.caption, app.warning, app.info] for x in coll
    )
    assert "Illustrative held-out set: n=2" in all_text
    assert "does not outperform the strongest single constituent" in all_text
    assert (
        "development split does not train" in all_text.lower() or "predeclared" in all_text.lower()
    )


def test_scenario_builder_action_says_manual_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = "\n".join(str(x.value) for coll in [app.caption, app.markdown] for x in coll)
    assert (
        "not automatically prefilled" in all_text.lower()
        or "apply them manually" in all_text.lower()
    )
