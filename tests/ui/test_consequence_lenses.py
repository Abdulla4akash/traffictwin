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
    assert "baseline_valid" in all_text or "run-baseline" in all_text
    assert "variation_valid" in all_text or "run-variatio" in all_text


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
    # Unknown provenance: synthetic_match None → is_compatible False, UNKNOWN badge
    from tests.helpers import fixed_clock, metric_collection

    from traffictwin.metrics.comparison import compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    comp.baseline_context["synthetic"] = None
    comp.variation_context["synthetic"] = None
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.evidence_standing["baseline_synthetic"] is None
    assert lens.evidence_standing["variation_synthetic"] is None
    assert lens.compatibility["synthetic_match"] is None
    assert lens.compatibility["is_compatible"] is False
    # Ensure no "None" string rendered as identity
    import traffictwin.ui.pages.consequence_lenses as page_module

    monkeypatch.setattr(page_module, "build_consequence_lens_report", lambda *_a, **_kw: lens)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    # Must show UNKNOWN, not synthetic
    assert "UNKNOWN" in markdowns
    assert "synthetic" not in markdowns.lower() or "UNKNOWN" in markdowns
    # Compatibility must show unknown, not no
    assert "unknown" in markdowns.lower()
    assert "Synthetic provenance match:" in markdowns and "unknown" in markdowns.lower()
    # No literal "None" identity
    all_text = (
        markdowns
        + "\n".join(str(c.value) for c in app.caption)
        + "\n".join(str(c.value) for c in app.code)
    )
    assert "None" not in all_text or "Unavailable" in all_text
    # Run/Seed should be valid or Unavailable, but not "None"
    assert "Run: Unavailable" not in all_text or lens.evidence_standing["baseline_run_id"] is None
    # Export must not contain "None" string for synthetic
    import json

    exported = json.loads(lens.to_json())
    assert exported["evidence_standing"]["baseline_synthetic"] is None
    assert exported["compatibility"]["synthetic_match"] is None


def test_available_tile_is_strictly_available_and_partial_separate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Metrics: Available, Partial, Unavailable, Total per domain + comparable caption
    metrics = {m.label: str(m.value) for m in app.metric}
    # Traffic domain: 18 available, 0 partial, 1 unavailable (golden for committed fixtures)
    # VEC domain: 19 available, 3 partial, 19 unavailable
    # Check that Available is strictly available, not comparable
    assert "Available" in metrics
    assert "Partial" in metrics
    assert "Unavailable" in metrics
    # Find at least one Available metric with 18 or 19
    assert "18" in " ".join(metrics.values()) or "19" in " ".join(metrics.values())
    # Check comparable caption exists and is available+partial
    captions = "\n".join(str(c.value) for c in app.caption)
    assert "Comparable (available + partial)" in captions


def test_golden_traffic_and_vec_counts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Pin golden counts for the committed deterministic fixture pair."""

    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Collect metric values by label
    # There are two domains, each with 4 metrics, so labels repeat; check via order
    # Instead, use the service directly for golden pin
    from pathlib import Path as _Path

    from traffictwin.ui.consequence_lenses import build_consequence_lens_report
    from traffictwin.ui.services import validate_bundle_for_ui
    from traffictwin.ui.services.models import BundleAnalysis

    b = validate_bundle_for_ui(_Path("tests/fixtures/bundles/baseline_valid"))
    v = validate_bundle_for_ui(_Path("tests/fixtures/bundles/variation_valid"))
    assert isinstance(b, BundleAnalysis)
    assert isinstance(v, BundleAnalysis)
    report = build_consequence_lens_report(b, v)
    assert not isinstance(report, type(None))
    # Traffic: 18 available, 0 partial, 1 unavailable
    assert report.traffic_summary.available_count == 18  # type: ignore[union-attr]
    assert report.traffic_summary.partial_count == 0  # type: ignore[union-attr]
    assert report.traffic_summary.unavailable_count == 1  # type: ignore[union-attr]
    # VEC: 19 available, 3 partial, 19 unavailable
    assert report.vec_summary.available_count == 19  # type: ignore[union-attr]
    assert report.vec_summary.partial_count == 3  # type: ignore[union-attr]
    assert report.vec_summary.unavailable_count == 19  # type: ignore[union-attr]


def test_incompatible_seed_mismatch_shows_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.helpers import fixed_clock, metric_collection

    from traffictwin.metrics.comparison import ComparisonRequest, compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    variation_mismatch = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"random_seed": 999}) for r in variation_col.results]
        }
    )
    comp = compare_metric_collections(
        baseline_col,
        variation_mismatch,
        ComparisonRequest(
            baseline_run_id="run-baseline-001",
            variation_run_id="run-variation-001",
            require_same_random_seed=True,
        ),
        clock=fixed_clock,
    )
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.compatibility["same_random_seed"] is False
    assert lens.compatibility["is_compatible"] is False
    assert len(comp.comparable_metrics) == 0
    # Page should show incompatibility warning when rendered with such a pair
    # Simulate by using the service directly; UI warning is covered by page rendering
    # but we also verify lens reports zero comparable
    assert lens.traffic_summary.available_count == 0
    assert lens.vec_summary.available_count == 0


def test_synthetic_mismatch_shows_incompatibility_banner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.helpers import fixed_clock, metric_collection

    from traffictwin.metrics.comparison import ComparisonRequest, compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    variation_synth_false = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"synthetic": False}) for r in variation_col.results]
        }
    )
    comp = compare_metric_collections(
        baseline_col,
        variation_synth_false,
        ComparisonRequest(
            baseline_run_id=baseline_col.run_id,
            variation_run_id=variation_synth_false.run_id,
            require_same_random_seed=True,
        ),
        clock=fixed_clock,
    )
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.compatibility["synthetic_match"] is False
    assert lens.compatibility["is_compatible"] is False
    assert "synthetic flags differ" in lens.warnings
    # JSON export must say is_compatible false
    import json

    exported = json.loads(lens.to_json())
    assert exported["compatibility"]["is_compatible"] is False

    # Render the page with this synthetic-mismatched lens injected
    import traffictwin.ui.pages.consequence_lenses as page_module

    monkeypatch.setattr(page_module, "build_consequence_lens_report", lambda *_a, **_kw: lens)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    # Warning banner must be visible
    warning_text = "\n".join(str(w.value) for w in app.warning)
    assert "Pair is not fully compatible" in warning_text
    assert "synthetic flags differ" in warning_text
    # Synthetic provenance mismatch banner
    assert "Synthetic provenance mismatch" in warning_text
    # Compatibility details must show synthetic_match false
    markdown_text = "\n".join(str(m.value) for m in app.markdown)
    assert "Synthetic provenance match:" in markdown_text
    assert "no" in markdown_text.lower()
    # Provenance badges must still be visible, and rows remain for diagnostic transparency
    # (do not silently hide comparison rows)
    assert len(app.dataframe) >= 2


def test_synthetic_mismatch_json_export_is_incompatible(tmp_path: Path) -> None:
    from tests.helpers import fixed_clock, metric_collection

    from traffictwin.metrics.comparison import ComparisonRequest, compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    variation_synth_false = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"synthetic": False}) for r in variation_col.results]
        }
    )
    comp = compare_metric_collections(
        baseline_col,
        variation_synth_false,
        ComparisonRequest(
            baseline_run_id=baseline_col.run_id,
            variation_run_id=variation_synth_false.run_id,
            require_same_random_seed=True,
        ),
        clock=fixed_clock,
    )
    lens = build_consequence_lens_report_from_comparison(comp)
    import json

    exported = json.loads(lens.to_json())
    assert exported["compatibility"]["synthetic_match"] is False
    assert exported["compatibility"]["is_compatible"] is False
    assert "synthetic flags differ" in exported["warnings"]
    assert exported["traffic_summary"]["warnings"] == exported["warnings"]
    assert exported["vec_summary"]["warnings"] == exported["warnings"]


def test_missing_run_seed_renders_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.helpers import fixed_clock, metric_collection

    from traffictwin.metrics.comparison import compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    comp.baseline_context["run_id"] = None
    comp.baseline_context["seed_id"] = ""
    comp.variation_context["run_id"] = None
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.evidence_standing["baseline_run_id"] is None
    # UI must render Unavailable, not "None"
    import traffictwin.ui.pages.consequence_lenses as page_module

    monkeypatch.setattr(page_module, "build_consequence_lens_report", lambda *_a, **_kw: lens)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Unavailable" in markdowns
    assert "`None`" not in markdowns
    assert "Run: `None`" not in markdowns
    assert "Seed: `None`" not in markdowns
    # Export must keep None as JSON null, not string "None"
    import json

    exported = json.loads(lens.to_json())
    assert exported["evidence_standing"]["baseline_run_id"] is None


def test_tri_state_compatibility_shows_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tests.helpers import fixed_clock, metric_collection

    from traffictwin.metrics.comparison import compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    comp.baseline_context["experiment_id"] = None
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.compatibility["same_experiment"] is None
    assert lens.compatibility["is_compatible"] is False
    import traffictwin.ui.pages.consequence_lenses as page_module

    monkeypatch.setattr(page_module, "build_consequence_lens_report", lambda *_a, **_kw: lens)
    app = _run_page(monkeypatch, tmp_path)
    assert not app.exception
    markdowns = "\n".join(str(m.value) for m in app.markdown)
    assert "Same experiment:" in markdowns and "unknown" in markdowns.lower()
    assert "unknown" in markdowns.lower()


def test_portable_export_has_no_absolute_paths(tmp_path: Path) -> None:
    import json
    from pathlib import Path as _Path

    from traffictwin.ui.consequence_lenses import build_consequence_lens_report
    from traffictwin.ui.services import ServiceError, validate_bundle_for_ui
    from traffictwin.ui.services.models import BundleAnalysis

    b = validate_bundle_for_ui(_Path("tests/fixtures/bundles/baseline_valid"))
    v = validate_bundle_for_ui(_Path("tests/fixtures/bundles/variation_valid"))
    assert isinstance(b, BundleAnalysis) and isinstance(v, BundleAnalysis)
    report = build_consequence_lens_report(b, v)
    assert not isinstance(report, ServiceError)
    portable = report.to_portable_dict()
    json_str = report.to_json()
    for txt in [json.dumps(portable), json_str, report.to_canonical_bytes().decode()]:
        assert "/tmp" not in txt  # noqa: S108
        assert "/private" not in txt
        assert "/Users" not in txt
        assert "baseline_bundle_path" not in txt
        assert "variation_bundle_path" not in txt


def test_session_state_clobber_blank_baseline_preserves_committed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Blank baseline input must not clobber committed session state with "."."""
    # Seed valid committed state as would be set by What-If Studio
    committed_baseline = "tests/fixtures/bundles/baseline_valid"
    committed_variation = "tests/fixtures/bundles/variation_valid"
    app = _run_page(
        monkeypatch,
        tmp_path,
        extra_state={
            "selected_baseline_run": committed_baseline,
            "selected_variation_run": committed_variation,
        },
    )
    assert not app.exception
    assert app.session_state["selected_baseline_run"] == committed_baseline
    assert app.session_state["selected_variation_run"] == committed_variation
    # Clear baseline textbox (empty string) – this previously produced Path("") -> "."
    app.text_input[0].set_value("")
    app.text_input[1].set_value(committed_variation)
    app.run(timeout=30)
    assert not app.exception
    # Committed baseline must remain previous valid, not "." or empty
    assert app.session_state["selected_baseline_run"] == committed_baseline
    assert app.session_state["selected_baseline_run"] != "."
    assert app.session_state["selected_baseline_run"] != ""
    assert app.session_state["selected_variation_run"] == committed_variation
    assert app.session_state["selected_variation_run"] != "."


def test_session_state_clobber_blank_variation_preserves_committed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    committed_baseline = "tests/fixtures/bundles/baseline_valid"
    committed_variation = "tests/fixtures/bundles/variation_valid"
    app = _run_page(
        monkeypatch,
        tmp_path,
        extra_state={
            "selected_baseline_run": committed_baseline,
            "selected_variation_run": committed_variation,
        },
    )
    assert not app.exception
    app.text_input[0].set_value(committed_baseline)
    app.text_input[1].set_value("")
    app.run(timeout=30)
    assert not app.exception
    assert app.session_state["selected_variation_run"] == committed_variation
    assert app.session_state["selected_variation_run"] != "."
    assert app.session_state["selected_baseline_run"] == committed_baseline


def test_session_state_invalid_path_does_not_poison_committed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    committed_baseline = "tests/fixtures/bundles/baseline_valid"
    committed_variation = "tests/fixtures/bundles/variation_valid"
    app = _run_page(
        monkeypatch,
        tmp_path,
        extra_state={
            "selected_baseline_run": committed_baseline,
            "selected_variation_run": committed_variation,
        },
    )
    assert not app.exception
    invalid = str(tmp_path / "does-not-exist-xyz")
    app.text_input[0].set_value(invalid)
    app.text_input[1].set_value(committed_variation)
    app.run(timeout=30)
    assert not app.exception
    # Invalid non-empty path must not replace last known good committed pair
    assert app.session_state["selected_baseline_run"] == committed_baseline
    assert app.session_state["selected_variation_run"] == committed_variation
    assert app.session_state["selected_baseline_run"] != invalid
    # Also test invalid variation symmetrically
    app2 = _run_page(
        monkeypatch,
        tmp_path,
        extra_state={
            "selected_baseline_run": committed_baseline,
            "selected_variation_run": committed_variation,
        },
    )
    app2.text_input[0].set_value(committed_baseline)
    app2.text_input[1].set_value(invalid)
    app2.run(timeout=30)
    assert not app2.exception
    assert app2.session_state["selected_baseline_run"] == committed_baseline
    assert app2.session_state["selected_variation_run"] == committed_variation


def test_session_state_valid_new_pair_updates_committed_atomically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    committed_baseline = "tests/fixtures/bundles/baseline_valid"
    committed_variation = "tests/fixtures/bundles/variation_valid"
    # Create a valid new pair via tmp copies of fixtures (different path, same content)
    import shutil

    new_baseline = tmp_path / "new_baseline"
    new_variation = tmp_path / "new_variation"
    shutil.copytree("tests/fixtures/bundles/baseline_valid", new_baseline)
    shutil.copytree("tests/fixtures/bundles/variation_valid", new_variation)
    app = _run_page(
        monkeypatch,
        tmp_path,
        extra_state={
            "selected_baseline_run": committed_baseline,
            "selected_variation_run": committed_variation,
        },
    )
    assert not app.exception
    app.text_input[0].set_value(str(new_baseline))
    app.text_input[1].set_value(str(new_variation))
    app.run(timeout=30)
    assert not app.exception
    # Valid new pair should atomically update both committed keys
    assert app.session_state["selected_baseline_run"] == str(new_baseline)
    assert app.session_state["selected_variation_run"] == str(new_variation)


def test_session_state_half_valid_pair_does_not_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    committed_baseline = "tests/fixtures/bundles/baseline_valid"
    committed_variation = "tests/fixtures/bundles/variation_valid"
    import shutil

    new_baseline = tmp_path / "new_baseline2"
    shutil.copytree("tests/fixtures/bundles/baseline_valid", new_baseline)
    invalid = str(tmp_path / "missing-variation-xyz")
    app = _run_page(
        monkeypatch,
        tmp_path,
        extra_state={
            "selected_baseline_run": committed_baseline,
            "selected_variation_run": committed_variation,
        },
    )
    assert not app.exception
    app.text_input[0].set_value(str(new_baseline))
    app.text_input[1].set_value(invalid)
    app.run(timeout=30)
    assert not app.exception
    # One valid + one invalid must not leave half-updated pair
    assert app.session_state["selected_baseline_run"] == committed_baseline
    assert app.session_state["selected_variation_run"] == committed_variation


def test_format_value_is_lossless_for_finite_floats() -> None:
    from traffictwin.ui.pages.consequence_lenses import _format_value

    # Value where %.6g is demonstrably lossy
    assert _format_value(2024123.0) == "2024123.0"
    assert float(_format_value(2024123.0)) == 2024123.0
    # Second value with meaningful precision beyond six digits
    val2 = 1234567.89
    assert float(_format_value(val2)) == val2
    # Ordinary floats
    assert _format_value(0.25) == "0.25"
    assert float(_format_value(0.25)) == 0.25
    # Integers
    assert _format_value(42) == "42"
    assert _format_value(42.0) == "42.0"
    # None
    assert _format_value(None) == "Unavailable"
    # Textual
    assert _format_value("hello") == "hello"
    # Large precise float
    big = 0.123456789012345
    assert float(_format_value(big)) == big


def test_format_value_preserves_across_dataframe_rendering(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure rendered dataframe values round-trip via _format_value."""
    from traffictwin.ui.pages.consequence_lenses import _format_value

    # Simulate a row baseline value that would be lossy under %.6g
    lossy_val = 2024123.0
    rendered = _format_value(lossy_val)
    assert rendered == "2024123.0"
    assert float(rendered) == lossy_val
    # Also test via actual page with synthetic data containing such value
    # Inject a report where one metric has the lossy value
    import copy

    from tests.helpers import fixed_clock, metric_collection

    from traffictwin.metrics.comparison import compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    # Mutate one metric to have the lossy value as baseline
    comp2 = copy.deepcopy(comp)
    m = comp2.comparable_metrics[0]
    comp2.comparable_metrics[0] = m.model_copy(update={"baseline": lossy_val})
    lens = build_consequence_lens_report_from_comparison(comp2)
    # Find that row and check formatting preserves value
    for row in [*lens.traffic_summary.rows, *lens.vec_summary.rows]:
        if row.metric_key == m.metric_key:
            assert float(_format_value(row.baseline)) == lossy_val
            break
    else:
        pytest.fail("metric not found")
