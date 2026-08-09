# ruff: noqa: ANN001,ANN201,ANN401,S108
"""Compare draft vs committed lifecycle — preserves vs commits."""  # noqa: E501

from __future__ import annotations

import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import mock

from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import default_session_state

FIXTURE_BASELINE = "tests/fixtures/bundles/baseline_valid"
FIXTURE_VARIATION = "tests/fixtures/bundles/variation_valid"


def _compare_app(baseline: str, variation: str) -> Any:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/compare.py")
    for k, v in deepcopy(default_session_state()).items():
        app.session_state[k] = v
    app.session_state["selected_baseline_run"] = baseline
    app.session_state["selected_variation_run"] = variation
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=25)
    assert not app.exception, app.exception
    return app


def _get(app: Any, key: str) -> str:
    try:
        return str(app.session_state[key])
    except KeyError:
        return str(app.session_state._state[key])


def _assert_preserves(app: Any) -> None:
    assert _get(app, "selected_baseline_run") == FIXTURE_BASELINE
    assert _get(app, "selected_variation_run") == FIXTURE_VARIATION
    assert _get(app, "selected_baseline_run") != "."
    assert _get(app, "selected_variation_run") != "."
    assert _get(app, "selected_baseline_run").strip() != ""
    assert _get(app, "selected_variation_run").strip() != ""


def test_committed_valid_renders_unchanged() -> None:
    app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
    assert _get(app, "selected_baseline_run") == FIXTURE_BASELINE
    assert _get(app, "selected_variation_run") == FIXTURE_VARIATION
    assert not app.exception
    # inputs reflect committed
    assert (
        next(w for w in app.text_input if w.label == "Baseline bundle path").value
        == FIXTURE_BASELINE
    )  # noqa: E501
    assert (
        next(w for w in app.text_input if w.label == "Variation bundle path").value
        == FIXTURE_VARIATION
    )  # noqa: E501


def test_blank_baseline_preserves() -> None:
    app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
    next(w for w in app.text_input if w.label == "Baseline bundle path").set_value("").run(
        timeout=25
    )
    _assert_preserves(app)


def test_whitespace_baseline_preserves() -> None:
    app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
    next(w for w in app.text_input if w.label == "Baseline bundle path").set_value("   ").run(
        timeout=25
    )
    _assert_preserves(app)


def test_blank_variation_preserves() -> None:
    app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
    next(w for w in app.text_input if w.label == "Variation bundle path").set_value("").run(
        timeout=25
    )
    _assert_preserves(app)


def test_whitespace_variation_preserves() -> None:
    app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
    next(w for w in app.text_input if w.label == "Variation bundle path").set_value("   ").run(
        timeout=25
    )
    _assert_preserves(app)


def test_missing_baseline_preserves() -> None:
    app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
    next(w for w in app.text_input if w.label == "Baseline bundle path").set_value(
        "/tmp/does-not-exist-xyz-compare-abc"
    ).run(timeout=25)
    _assert_preserves(app)


def test_missing_variation_preserves() -> None:
    app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
    next(w for w in app.text_input if w.label == "Variation bundle path").set_value(
        "/tmp/does-not-exist-xyz-compare-abc"
    ).run(timeout=25)
    _assert_preserves(app)


def test_invalid_baseline_preserves() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "invalid"
        p.mkdir()
        (p / "manifest.json").write_text("{}", encoding="utf-8")
        app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
        next(w for w in app.text_input if w.label == "Baseline bundle path").set_value(str(p)).run(
            timeout=25
        )
        _assert_preserves(app)


def test_invalid_variation_preserves() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "invalid"
        p.mkdir()
        (p / "manifest.json").write_text("{}", encoding="utf-8")
        app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
        next(w for w in app.text_input if w.label == "Variation bundle path").set_value(str(p)).run(
            timeout=25
        )
        _assert_preserves(app)


def test_half_valid_preserves_both() -> None:
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "half-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="compare-half-valid",
            experiment_id="exp-compare-half",
            baseline_random_seed=99,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.6, vehicle_count=19, policy_profile="synthetic-balanced"
            ),
            output_root=None,
        )
        res = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(res, ServiceError)
        new_baseline = str(res.baseline_bundle_path)
        with tempfile.TemporaryDirectory() as tmp2:
            inv = Path(tmp2) / "inv"
            inv.mkdir()
            (inv / "manifest.json").write_text("{}", encoding="utf-8")
            app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
            bw = next(w for w in app.text_input if w.label == "Baseline bundle path")
            vw = next(w for w in app.text_input if w.label == "Variation bundle path")
            bw.set_value(new_baseline)
            vw.set_value(str(inv)).run(timeout=25)
            _assert_preserves(app)


def test_valid_new_pair_commits_both() -> None:
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "valid-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="compare-valid-new",
            experiment_id="exp-compare-valid",
            baseline_random_seed=100,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.7, vehicle_count=20, policy_profile="synthetic-balanced"
            ),
            output_root=None,
        )
        res = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(res, ServiceError)
        nb = str(res.baseline_bundle_path)
        nv = str(res.variation_bundle_path)
        app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
        bw = next(w for w in app.text_input if w.label == "Baseline bundle path")
        vw = next(w for w in app.text_input if w.label == "Variation bundle path")
        bw.set_value(nb)
        vw.set_value(nv).run(timeout=25)
        assert _get(app, "selected_baseline_run") == nb
        assert _get(app, "selected_variation_run") == nv


def test_comparison_service_error_preserves() -> None:
    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.ui.services import (
        ServiceError,
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        generate_whatif_pair_for_ui,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "svc-err-ws"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="compare-svc-err",
            experiment_id="exp-compare-svc-err",
            baseline_random_seed=101,
            variation_overrides=WhatIfVariationOverrides(
                congestion_multiplier=1.8, vehicle_count=21, policy_profile="synthetic-balanced"
            ),
            output_root=None,
        )
        res = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert not isinstance(res, ServiceError)
        nb = str(res.baseline_bundle_path)
        nv = str(res.variation_bundle_path)
        import traffictwin.ui.pages.compare as _cmp

        app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
        with mock.patch.object(
            _cmp,
            "compare_runs_for_ui",
            return_value=ServiceError("injected comparison failure", "injected"),
        ):
            bw = next(w for w in app.text_input if w.label == "Baseline bundle path")
            vw = next(w for w in app.text_input if w.label == "Variation bundle path")
            bw.set_value(nb)
            vw.set_value(nv).run(timeout=25)
            _assert_preserves(app)
            assert any("injected" in str(e.value).lower() for e in app.error)


def test_no_dot_write() -> None:
    for draft in ["", "   ", ".", " ./", " . "]:
        app = _compare_app(FIXTURE_BASELINE, FIXTURE_VARIATION)
        bw = next(w for w in app.text_input if w.label == "Baseline bundle path")
        bw.set_value(draft).run(timeout=25)
        assert _get(app, "selected_baseline_run") != "."
        assert _get(app, "selected_variation_run") != "."
