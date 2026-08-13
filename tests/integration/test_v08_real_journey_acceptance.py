"""Real-journey acceptance — executable current-product proof
(serial/offline, no SUMO/VEC).

Proves via current committed code and isolated temporary workspaces:
- real current route resolution via UiPage + page_script_for and AppTest render
- generated non-default comparison pair via current what-if service
- exact identity continuity from What-If through Consequence and Compare/report
- transactional rollback to last valid pair without Path("") == "." corruption (AppTest)
- portable identity continuity via receipt_to_portable_dict
  (no absolute leakage, SYNTHETIC preserved)

Serial/offline with temporary workspaces and current committed fixtures.
No network provider or scientific runner launched. No historical compare.py import.
"""

from __future__ import annotations

import tempfile
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from streamlit.testing.v1 import AppTest

    from traffictwin.synthetic.whatif_pair import WhatIfPairReceipt, WhatIfPairRequest

# ---------------------------------------------------------------------------
# 1. Real route rendering via current registry and AppTest
# ---------------------------------------------------------------------------


def test_real_route_render_current_registry() -> None:
    """Every journey surface resolves through current route registry
    (page_script_for) and renders."""
    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.navigation_v07 import V07_PAGE_SPECS, page_script_for
    from traffictwin.ui.state import default_session_state

    required = [
        UiPage.HOME,
        UiPage.GUIDED_DEMO,
        UiPage.WHATIF_STUDIO,
        UiPage.CONSEQUENCE_LENSES,
        UiPage.COMPARE,
    ]
    for page in required:
        script = page_script_for(page)
        assert script, f"page_script_for({page}) returned empty"
        # script must exist under src/traffictwin/ui/
        full = Path(f"src/traffictwin/ui/{script}")
        assert full.exists(), f"script for {page} missing on disk: {full}"
        assert full.is_file()
    # Also validate V07_PAGE_SPECS covers all UiPage
    assert len(V07_PAGE_SPECS) == len(UiPage)

    # Load-bearing journey pages must render via AppTest (proves real session behavior)
    from streamlit.testing.v1 import AppTest

    for page in [UiPage.WHATIF_STUDIO, UiPage.COMPARE]:
        script = page_script_for(page)
        app = AppTest.from_file(f"src/traffictwin/ui/{script}")
        for k, v in deepcopy(default_session_state()).items():
            app.session_state[k] = v
        app.session_state["_v07_navigation_active"] = True
        app.run(timeout=25)
        assert not app.exception, f"AppTest render failed for {page}: {app.exception}"
        # Basic render check: title or at least one widget present
        assert len(app.title) >= 1 or len(app.text_input) >= 1 or len(app.markdown) >= 1

    # Additionally verify HOME and CONSEQUENCE_LENSES render (or at least resolve)
    # Use AppTest for CONSEQUENCE_LENSES as well — it is load-bearing for identity
    for page in [UiPage.CONSEQUENCE_LENSES, UiPage.HOME, UiPage.GUIDED_DEMO]:
        script = page_script_for(page)
        app = AppTest.from_file(f"src/traffictwin/ui/{script}")
        for k, v in deepcopy(default_session_state()).items():
            app.session_state[k] = v
        app.session_state["_v07_navigation_active"] = True
        # Provide minimal pair for consequence so it doesn't error on missing keys
        if page is UiPage.CONSEQUENCE_LENSES:
            app.session_state["selected_baseline_run"] = "tests/fixtures/bundles/baseline_valid"
            app.session_state["selected_variation_run"] = "tests/fixtures/bundles/variation_valid"
        app.run(timeout=25)
        assert not app.exception, f"AppTest render failed for {page}: {app.exception}"


# ---------------------------------------------------------------------------
# 2. What-If generates non-default pair in isolated temp workspace
# ---------------------------------------------------------------------------


def test_whatif_generates_non_default_pair_offline_serial() -> None:
    """Invoke current What-If service to generate a genuinely non-default pair."""
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.synthetic.whatif_pair import WhatIfPairRequest, WhatIfVariationOverrides
    from traffictwin.ui.services.models import ServiceError
    from traffictwin.ui.services.whatif_pair import generate_whatif_pair_for_ui

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws-whatif"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        # Non-default request: multiple variation overrides distinct from defaults
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="lane12-nondefault-acceptance",
            experiment_id="exp-lane12-accept",
            baseline_random_seed=11,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.9,
                vehicle_count=27,
                task_arrival_rate=0.21,
                rsu_count=5,
            ),
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(result, ServiceError), f"unexpected ServiceError: {result}"
        assert result.status == "ok"
        assert result.baseline_bundle_path is not None
        assert result.variation_bundle_path is not None
        b_path = Path(result.baseline_bundle_path)
        v_path = Path(result.variation_bundle_path)
        assert b_path.exists(), f"baseline bundle missing: {b_path}"
        assert v_path.exists(), f"variation bundle missing: {v_path}"
        assert str(b_path) != str(v_path)
        # Non-default proof: changed_parameters must contain our overrides
        param_keys = {p.field_path for p in result.changed_parameters}
        assert "congestion_multiplier" in param_keys
        assert "vehicle_count" in param_keys
        assert len(result.changed_parameters) >= 2
        # Not the committed fixtures — must be under temp workspace
        assert str(ws) in str(b_path)
        assert str(ws) in str(v_path)
        # Pair id deterministic from request
        assert result.pair_id
        assert result.pair_id.startswith("whatif-lane12-nondefault-acceptance")


# ---------------------------------------------------------------------------
# 3. Identity continuity: What-If -> Consequence -> Compare/report
# ---------------------------------------------------------------------------


def test_identity_continuity_whatif_through_consequence_and_compare() -> None:
    """Exact identity continuity: same pair identities survive
    What-If -> Consequence -> Compare/report."""
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.synthetic.whatif_pair import WhatIfPairRequest, WhatIfVariationOverrides
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report
    from traffictwin.ui.services import compare_runs_for_ui, validate_bundle_for_ui
    from traffictwin.ui.services.models import ServiceError
    from traffictwin.ui.services.whatif_pair import generate_whatif_pair_for_ui

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws-continuity"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="lane12-continuity-accept",
            experiment_id="exp-lane12-continuity",
            baseline_random_seed=13,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=2.0,
                vehicle_count=29,
                rsu_capacity=12,
            ),
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(result, ServiceError)
        assert result.status == "ok"
        b_path = str(result.baseline_bundle_path)
        v_path = str(result.variation_bundle_path)
        assert b_path and v_path

        # Validate through current services
        baseline = validate_bundle_for_ui(Path(b_path))
        variation = validate_bundle_for_ui(Path(v_path))
        assert not isinstance(baseline, ServiceError)
        assert not isinstance(variation, ServiceError)
        assert getattr(baseline, "analysis_ready", False) is True
        assert getattr(variation, "analysis_ready", False) is True

        # Compare/report — must succeed and preserve identities
        report = compare_runs_for_ui(baseline, variation)
        assert not isinstance(report, ServiceError), f"compare failed: {report}"
        # Pair identities in comparison report must match generated experiment
        assert report.baseline_context.get("experiment_id") == "exp-lane12-continuity"
        assert report.variation_context.get("experiment_id") == "exp-lane12-continuity"
        # Synthetic provenance preserved
        assert report.baseline_context.get("synthetic") is True
        assert report.variation_context.get("synthetic") is True
        # Changed parameters must include our non-default overrides (mapped to seed snapshot paths)
        changed_paths = {c.get("path") for c in report.changed_seed_parameters}
        # congestion_multiplier maps to demand.multiplier in seed snapshot
        assert "congestion_multiplier" in changed_paths or "demand.multiplier" in changed_paths
        assert "vehicle_count" in changed_paths or "fleet.count" in changed_paths

        # Consequence lenses built from same pair — identities must match compare
        consequence = build_consequence_lens_report(baseline, variation)
        assert not isinstance(consequence, ServiceError), f"consequence failed: {consequence}"
        # Same experiment identity across consequence and compare
        assert consequence.baseline_identity.get("experiment_id") == report.baseline_context.get(
            "experiment_id"
        )
        assert consequence.variation_identity.get("experiment_id") == report.variation_context.get(
            "experiment_id"
        )
        assert consequence.baseline_identity.get("synthetic") is True
        assert consequence.variation_identity.get("synthetic") is True
        # Fingerprint is deterministic and non-empty
        assert consequence.fingerprint
        assert len(consequence.fingerprint) == 64
        # Portable payload excludes absolute paths
        portable = consequence.to_portable_dict()
        assert str(ws) not in str(portable)
        assert tempfile.gettempdir() not in str(portable)
        # Ensure portable does not leak the temp workspace absolute path
        portable_str = str(portable)
        # The absolute ws path must not appear verbatim
        assert str(ws) not in portable_str


# ---------------------------------------------------------------------------
# 4. Transactional rollback without Path("") == "." corruption (AppTest)
# ---------------------------------------------------------------------------


def test_transactional_rollback_without_path_dot_corruption() -> None:
    """Exercise actual Compare page rollback via AppTest —
    blank/invalid drafts preserve last valid pair."""
    from copy import deepcopy
    from pathlib import Path as _Path

    from streamlit.testing.v1 import AppTest

    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.navigation_v07 import page_script_for
    from traffictwin.ui.state import default_session_state

    fixture_baseline = "tests/fixtures/bundles/baseline_valid"
    fixture_variation = "tests/fixtures/bundles/variation_valid"
    script = page_script_for(UiPage.COMPARE)

    def _compare_app(baseline: str, variation: str) -> AppTest:
        app = AppTest.from_file(f"src/traffictwin/ui/{script}")
        for k, v in deepcopy(default_session_state()).items():
            app.session_state[k] = v
        app.session_state["selected_baseline_run"] = baseline
        app.session_state["selected_variation_run"] = variation
        app.session_state["_v07_navigation_active"] = True
        app.run(timeout=25)
        assert not app.exception, f"initial compare render failed: {app.exception}"
        return app

    def _get(app: AppTest, key: str) -> str:
        try:
            return str(app.session_state[key])
        except KeyError:
            return str(app.session_state._state[key])

    # Prove Path("") == Path(".") is the corruption we guard against
    assert _Path("") == _Path(".")

    # Initial valid authoritative pair
    app = _compare_app(fixture_baseline, fixture_variation)
    assert _get(app, "selected_baseline_run") == fixture_baseline
    assert _get(app, "selected_variation_run") == fixture_variation

    # Blank baseline (empty string) must preserve
    app2 = _compare_app(fixture_baseline, fixture_variation)
    next(w for w in app2.text_input if w.label == "Baseline bundle path").set_value("").run(
        timeout=25
    )
    assert not app2.exception
    assert _get(app2, "selected_baseline_run") == fixture_baseline
    assert _get(app2, "selected_variation_run") == fixture_variation
    assert _get(app2, "selected_baseline_run") != "."
    assert _get(app2, "selected_variation_run") != "."
    assert _get(app2, "selected_baseline_run").strip() != ""

    # Whitespace baseline must preserve
    app3 = _compare_app(fixture_baseline, fixture_variation)
    next(w for w in app3.text_input if w.label == "Baseline bundle path").set_value("   ").run(
        timeout=25
    )
    assert _get(app3, "selected_baseline_run") == fixture_baseline
    assert _get(app3, "selected_variation_run") == fixture_variation
    assert _get(app3, "selected_baseline_run") != "."

    # Blank variation must preserve
    app4 = _compare_app(fixture_baseline, fixture_variation)
    next(w for w in app4.text_input if w.label == "Variation bundle path").set_value("   ").run(
        timeout=25
    )
    assert _get(app4, "selected_baseline_run") == fixture_baseline
    assert _get(app4, "selected_variation_run") == fixture_variation
    assert _get(app4, "selected_variation_run") != "."

    # Invalid (non-existent) path must preserve
    app5 = _compare_app(fixture_baseline, fixture_variation)
    tmp_invalid = str(Path(tempfile.gettempdir()) / "does-not-exist-lane12-xyz")
    next(w for w in app5.text_input if w.label == "Baseline bundle path").set_value(
        tmp_invalid
    ).run(timeout=25)
    assert _get(app5, "selected_baseline_run") == fixture_baseline
    assert _get(app5, "selected_variation_run") == fixture_variation

    # Also prove invalid bundle (manifest {}) preserves
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "invalid"
        p.mkdir()
        (p / "manifest.json").write_text("{}", encoding="utf-8")
        app6 = _compare_app(fixture_baseline, fixture_variation)
        next(w for w in app6.text_input if w.label == "Baseline bundle path").set_value(str(p)).run(
            timeout=25
        )
        assert _get(app6, "selected_baseline_run") == fixture_baseline
        assert _get(app6, "selected_variation_run") == fixture_variation
        assert _get(app6, "selected_baseline_run") != "."


# ---------------------------------------------------------------------------
# 5. Portable identity and SYNTHETIC preservation across two workspaces
# ---------------------------------------------------------------------------


def test_portable_identity_and_synthetic_preservation() -> None:
    """Portable canonical export via receipt_to_portable_dict:
    stable fingerprint, no leakage, SYNTHETIC preserved."""
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.synthetic.whatif_pair import (
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        receipt_to_portable_dict,
    )
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report
    from traffictwin.ui.services import compare_runs_for_ui, validate_bundle_for_ui
    from traffictwin.ui.services.models import ServiceError
    from traffictwin.ui.services.whatif_pair import generate_whatif_pair_for_ui

    def _generate_in(ws: Path, suffix: str) -> tuple[WhatIfPairReceipt, WhatIfPairRequest]:
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="lane12-portable-accept",
            experiment_id="exp-lane12-portable",
            baseline_random_seed=17,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.7,
                vehicle_count=23,
            ),
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(result, ServiceError), f"generate failed in {ws}: {result}"
        assert result.status == "ok"
        return result, req

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ws1 = tmp_path / "ws1-portable"
        ws2 = tmp_path / "ws2-portable"

        res1, _ = _generate_in(ws1, "ws1")
        res2, _ = _generate_in(ws2, "ws2")

        # Portable dicts must not leak absolute workspace paths
        portable1 = receipt_to_portable_dict(res1, workspace_path=ws1)
        portable2 = receipt_to_portable_dict(res2, workspace_path=ws2)

        for portable, ws in [(portable1, ws1), (portable2, ws2)]:
            # No absolute workspace leakage
            assert str(ws) not in str(portable), f"absolute ws leaked in portable: {ws}"
            assert tempfile.gettempdir() not in portable.get("baseline_bundle_path", "")
            assert "/private" not in portable.get("baseline_bundle_path", "")
            # Paths are portable relative (pair_id/baseline form)
            assert not portable["baseline_bundle_path"].startswith("/")
            assert not portable["variation_bundle_path"].startswith("/")
            assert res1.pair_id in portable["baseline_bundle_path"]
            assert res1.pair_id in portable["variation_bundle_path"]

        # Stable logical identity: same request -> same pair_id / fingerprints
        assert res1.pair_id == res2.pair_id
        assert res1.request_fingerprint == res2.request_fingerprint
        assert res1.pair_fingerprint == res2.pair_fingerprint
        # Portable payloads must be identical (workspace-agnostic)
        assert portable1["pair_id"] == portable2["pair_id"]
        assert portable1["request_fingerprint"] == portable2["request_fingerprint"]
        assert portable1["pair_fingerprint"] == portable2["pair_fingerprint"]
        # Pair-relative paths identical
        assert portable1["baseline_bundle_path"] == portable2["baseline_bundle_path"]
        assert portable1["variation_bundle_path"] == portable2["variation_bundle_path"]

        # SYNTHETIC preservation through Consequence/Compare chain
        b1 = validate_bundle_for_ui(Path(str(res1.baseline_bundle_path)))
        v1 = validate_bundle_for_ui(Path(str(res1.variation_bundle_path)))
        assert not isinstance(b1, ServiceError)
        assert not isinstance(v1, ServiceError)
        cmp1 = compare_runs_for_ui(b1, v1)
        assert not isinstance(cmp1, ServiceError)
        assert cmp1.baseline_context.get("synthetic") is True
        assert cmp1.variation_context.get("synthetic") is True
        # Also check Consequence fingerprint stable and no leakage
        cons1 = build_consequence_lens_report(b1, v1)
        assert not isinstance(cons1, ServiceError)
        assert cons1.baseline_identity.get("synthetic") is True
        assert cons1.fingerprint
        # Second workspace consequence must have same fingerprint (logical identity)
        b2 = validate_bundle_for_ui(Path(str(res2.baseline_bundle_path)))
        v2 = validate_bundle_for_ui(Path(str(res2.variation_bundle_path)))
        cons2 = build_consequence_lens_report(b2, v2)
        assert not isinstance(cons2, ServiceError)
        assert cons1.fingerprint == cons2.fingerprint
        assert str(ws1) not in str(cons1.to_portable_dict())
        assert str(ws2) not in str(cons2.to_portable_dict())


# ---------------------------------------------------------------------------
# 6. Temp-copy executable journey mutation — forced import root verification
# ---------------------------------------------------------------------------


def test_temp_copy_executable_journey_forces_import_root() -> None:
    """Temp-copy mutation proves import from temp root via in-process
    traffictwin.__file__ check; prevents editable-install shadowing of
    the temp mutation probe without spawning a subprocess."""
    import hashlib
    import importlib
    import importlib.util
    import os
    import shutil
    import sys
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[2]
    original_compare = (repo_root / "src/traffictwin/ui/pages/compare.py").read_text(
        encoding="utf-8"
    )
    original_hash = hashlib.sha256(original_compare.encode()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = _Path(tmp) / "repo"
        # Copy minimal repo structure needed for import and validator
        for rel in [
            "src/traffictwin",
            "src/traffictwin/ui/pages/compare.py",
            "src/traffictwin/ui/navigation_v07.py",
            "src/traffictwin/ui/labels.py",
            "scripts/validate_v08_requirements_closure.py",
        ]:
            src = repo_root / rel
            dst = tmp_root / rel
            if src.is_dir():
                shutil.copytree(
                    src,
                    dst,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            elif src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        # Also copy package metadata for import
        for extra in ["pyproject.toml", "src/traffictwin/__init__.py"]:
            src = repo_root / extra
            dst = tmp_root / extra
            if src.exists() and src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        # Mutate compare.py in temp copy: remove strip guard
        comp_path = tmp_root / "src/traffictwin/ui/pages/compare.py"
        if comp_path.exists():
            txt = comp_path.read_text(encoding="utf-8")
            mutated = (
                txt.replace(".strip()", ".strip_without_guard()")
                if ".strip()" in txt
                else txt.replace("strip()", "no_strip()")
            )
            comp_path.write_text(mutated, encoding="utf-8")
        # Prove mutation present in temp copy (separately from import check)
        mutated_text = comp_path.read_text(encoding="utf-8")
        assert ".strip_without_guard()" in mutated_text or "no_strip()" in mutated_text, (
            "mutation not present in temp copy"
        )
        # Copy docs needed for validator
        for rel in [
            "docs/closure/v08_alignment",
            "scripts",
        ]:
            src = repo_root / rel
            dst = tmp_root / rel
            if src.is_dir():
                shutil.copytree(
                    src,
                    dst,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            elif src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        # In-process import-origin proof — deterministic, no subprocess
        saved_path = list(sys.path)
        saved_module = sys.modules.get("traffictwin")
        try:
            if "traffictwin" in sys.modules:
                del sys.modules["traffictwin"]
            sys.path.insert(0, str(tmp_root / "src"))
            importlib.invalidate_caches()
            import traffictwin as _temp_traffictwin

            assert _temp_traffictwin.__file__ is not None, "traffictwin.__file__ is None"
            assert str(tmp_root) in _temp_traffictwin.__file__, (
                f"traffictwin not from temp: {_temp_traffictwin.__file__}"
            )
            assert _Path(_temp_traffictwin.__file__).resolve().is_relative_to(tmp_root.resolve()), (
                f"traffictwin.__file__ not under temp root: {_temp_traffictwin.__file__}"
            )
        finally:
            if "traffictwin" in sys.modules:
                del sys.modules["traffictwin"]
            if saved_module is not None:
                sys.modules["traffictwin"] = saved_module
            sys.path[:] = saved_path
            importlib.invalidate_caches()
        # Verify validator detects the mutation on temp copy (in-process, no subprocess)
        env_key = "V08_VALIDATOR_ROOT"
        old_env = os.environ.get(env_key)
        old_validator = sys.modules.get("validate_v08_requirements_closure")
        try:
            os.environ[env_key] = str(tmp_root)
            for key in list(sys.modules):
                if key == "validate_v08_requirements_closure" or key.startswith("validate_v08"):
                    del sys.modules[key]
            spec = importlib.util.spec_from_file_location(
                "validate_v08_requirements_closure",
                tmp_root / "scripts/validate_v08_requirements_closure.py",
            )
            assert spec is not None and spec.loader is not None, "validator spec not found"
            mod = importlib.util.module_from_spec(spec)
            sys.modules["validate_v08_requirements_closure"] = mod
            spec.loader.exec_module(mod)
            errors = mod.validate()
            assert errors, "temp validator should fail on mutated compare.py"
            assert any("strip" in e.lower() or "rollback" in e.lower() for e in errors), (
                f"validator errors missing strip/rollback: {errors}"
            )
        finally:
            if "validate_v08_requirements_closure" in sys.modules:
                del sys.modules["validate_v08_requirements_closure"]
            if old_validator is not None:
                sys.modules["validate_v08_requirements_closure"] = old_validator
            if old_env is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = old_env
            importlib.invalidate_caches()
        # Prove real working tree stays byte-for-byte clean
        after = (repo_root / "src/traffictwin/ui/pages/compare.py").read_text(encoding="utf-8")
        assert after == original_compare, "real compare.py was mutated"
        assert hashlib.sha256(after.encode()).hexdigest() == original_hash
