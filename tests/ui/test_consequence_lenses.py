"""UI/AppTests for Consequence Lenses page."""

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
    page: UiPage = UiPage.CONSEQUENCE_LENSES,
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


def test_consequence_lenses_has_exactly_one_title(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert len(app.title) == 1
    assert app.title[0].value == "Consequence Lenses"


def test_no_pair_state_shows_guidance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Use widget manipulation to simulate missing paths
    app.text_input[0].set_value(str(tmp_path / "missing-baseline"))
    app.text_input[1].set_value(str(tmp_path / "missing-variation"))
    app.run(timeout=30)
    assert not app.exception
    assert any(
        "do not exist" in str(e.value) or "must exist" in str(e.value) for e in app.error
    ) or any("must be selected" in str(e.value) for e in app.error)
    labels = [b.label for b in app.button]
    assert "Start Guided Demo" in labels or "Import a Run Bundle" in labels


def test_baseline_only_state_identifies_missing_variation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    app.text_input[0].set_value("tests/fixtures/bundles/baseline_valid")
    app.text_input[1].set_value(str(tmp_path / "missing-variation"))
    app.run(timeout=30)
    assert not app.exception
    assert any("Variation" in str(e.value) and "does not exist" in str(e.value) for e in app.error)


def test_variation_only_state_identifies_missing_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    app.text_input[0].set_value(str(tmp_path / "missing-baseline"))
    app.text_input[1].set_value("tests/fixtures/bundles/variation_valid")
    app.run(timeout=30)
    assert not app.exception
    assert any("Baseline" in str(e.value) and "does not exist" in str(e.value) for e in app.error)


def test_valid_synthetic_example_pair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert len(app.error) == 0
    captions = "\n".join(str(c.value) for c in app.caption)
    code_blocks = "\n".join(str(c.value) for c in app.code)
    all_text = captions + code_blocks + "\n".join(str(m.value) for m in app.markdown)
    assert "baseline_valid" in all_text or "run-baseline-001" in all_text
    assert "variation_valid" in all_text or "run-variation-001" in all_text


def test_pair_identities_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    subheaders = [s.value for s in app.subheader]
    assert "Pair identity" in subheaders
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Baseline" in markdowns
    assert "Variation" in markdowns


def test_compatibility_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    subheaders = [s.value for s in app.subheader]
    assert "Compatibility" in subheaders
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Same experiment" in markdowns
    assert "Same random seed" in markdowns


def test_traffic_and_vec_sections_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    subheaders = [s.value for s in app.subheader]
    assert "Traffic consequences" in subheaders
    assert "VEC consequences" in subheaders


def test_changed_parameter_table_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    subheaders = [s.value for s in app.subheader]
    assert "Changed scenario parameters" in subheaders
    assert len(app.dataframe) >= 3
    found = False
    for df in app.dataframe:
        val = str(df.value)
        if "demand.multiplier" in val:
            found = True
            break
    assert found, "changed parameter table should contain demand.multiplier"


def test_unavailable_reasons_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    captions = "\n".join(str(c.value) for c in app.caption)
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    all_text = captions + markdowns + "\n".join(str(e.label) for e in app.expander)
    assert "unavailable" in all_text.lower()
    # Check dataframes for reason codes via DataFrame column to avoid string truncation
    found_reason = False
    for df in app.dataframe:
        df_val = df.value
        if hasattr(df_val, "columns") and "reason_codes" in df_val.columns:
            for val in df_val["reason_codes"]:
                if "METRIC_NOT_APPLICABLE" in str(val) or "BASELINE_ZERO" in str(val):
                    found_reason = True
                    break
        else:
            s = str(df_val)
            if "METRIC_NOT_APPLICABLE" in s or "BASELINE_ZERO" in s:
                found_reason = True
                break
        if found_reason:
            break
    assert found_reason, "at least one dataframe should contain reason codes"


def test_non_causality_wording_visible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    infos = "\n".join(str(i.value) for i in app.info)
    captions = "\n".join(str(c.value) for c in app.caption)
    all_text = infos + captions + "\n".join(str(m.value) for m in app.markdown)
    assert "not a live Manchester forecast" in all_text
    assert "do not prove that an algorithm" in all_text
    assert "Variation − baseline" in all_text


def test_no_live_manchester_forecast_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = " ".join(
        [str(i.value) for i in app.info]
        + [str(c.value) for c in app.caption]
        + [str(m.value) for m in app.markdown]
        + [str(t.value) for t in app.title]
    ).lower()
    assert all_text.count("forecast") == 1
    assert "not a live manchester forecast" in all_text


def test_no_optimal_policy_claim(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    all_text = " ".join(
        [str(i.value) for i in app.info]
        + [str(c.value) for c in app.caption]
        + [str(m.value) for m in app.markdown]
        + [str(h.value) for h in app.subheader]
    ).lower()
    assert "optimal" not in all_text
    assert "better" not in all_text
    assert "worse" not in all_text


def test_full_compare_action_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "Open full Compare" in labels


def test_provenance_and_reports_actions_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "Open Provenance" in labels
    assert "Open Reports" in labels


def test_selected_keys_are_consumed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    assert "selected_baseline_run" in app.session_state
    assert "selected_variation_run" in app.session_state
    app.text_input[0].set_value("tests/fixtures/bundles/baseline_valid")
    app.text_input[1].set_value("tests/fixtures/bundles/variation_valid")
    app.run(timeout=30)
    assert not app.exception
    inputs = [ti.value for ti in app.text_input]
    assert any("baseline_valid" in str(v) for v in inputs)
    assert any("variation_valid" in str(v) for v in inputs)
    # Session state should reflect widget values
    assert "baseline_valid" in str(app.session_state["selected_baseline_run"])
    assert "variation_valid" in str(app.session_state["selected_variation_run"])


def test_hermetic_against_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Set env vars to nonsense and ensure page still works with tmp_path
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path / "nonexistent_workspace"))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(tmp_path / "nonexistent_registry.sqlite"))
    monkeypatch.setenv("BODS_API_KEY", "fake-key-should-not-be-used")  # noqa: S105
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "fake-key-2")  # noqa: S105
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(tmp_path / "fake_fixture"))
    monkeypatch.setenv("TRAFFICTWIN_TOS_DATA_PATH", str(tmp_path / "fake_tos"))
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    subheaders = [s.value for s in app.subheader]
    assert "Traffic consequences" in subheaders


def test_invalid_bundle_shows_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad_bundle"
    bad.mkdir()
    (bad / "manifest.yaml").write_text("invalid: yaml: [", encoding="utf-8")
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    app.text_input[0].set_value(str(bad))
    app.text_input[1].set_value("tests/fixtures/bundles/variation_valid")
    app.run(timeout=30)
    assert not app.exception
    assert any("invalid" in str(e.value).lower() for e in app.error)


def test_compatible_pair_with_partial_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    captions = "\n".join(str(c.value) for c in app.caption)
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    all_text = captions + markdowns
    assert "Unavailable" in all_text or "unavailable" in all_text.lower()
    statuses = set()
    for df in app.dataframe:
        val = str(df.value).lower()
        if "available" in val:
            statuses.add("available")
        if "unavailable" in val:
            statuses.add("unavailable")
        if "partial" in val:
            statuses.add("partial")
    assert "available" in statuses
    assert "unavailable" in statuses


def test_unknown_provenance_remains_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Default fixtures are synthetic; unknown is not promoted to synthetic.
    # Service handling is tested in unit; here we ensure page shows badges.
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    # Should contain synthetic badge (lowercase in badge markdown)
    assert "synthetic" in markdowns.lower()
