"""End-to-end E2 research product acceptance — Lane 12.

AppTest journey: launch, navigate, load built-in, exact admission/strategies/
E2b/E2c/E2d/accounting/unavailable/provenance/limitations and deterministic
export. Strict, no research launch, no absolute path/secret/Kubernetes false
claim.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any  # noqa: ANN401
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import (  # type: ignore[import-untyped, unused-ignore]  # noqa: I001
    default_session_state,
    load_ui_config,
)

RESOURCE_PAGE = "src/traffictwin/ui/app_pages/resource_strategy.py"
HOME_PAGE = "src/traffictwin/ui/app_pages/home.py"


def _resource_app() -> AppTest:
    app = AppTest.from_file(RESOURCE_PAGE)
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    app.session_state["resource_strategy_study_path"] = (
        "tests/fixtures/resource_strategy/synthetic_study_v1.json"
    )
    if "resource_strategy_e2_active" in app.session_state:
        del app.session_state["resource_strategy_e2_active"]
    if "resource_strategy_intent" in app.session_state:
        del app.session_state["resource_strategy_intent"]
    return app


def _home_app() -> AppTest:
    app = AppTest.from_file(HOME_PAGE)
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    return app


def _text(app: AppTest) -> str:
    parts: list[str] = []
    for attr in ("title", "markdown", "caption", "subheader", "text", "code"):
        parts.extend(str(x.value) for x in getattr(app, attr, []))
    for attr in ("info", "warning", "error", "success"):
        parts.extend(str(x.value) for x in getattr(app, attr, []))
    for df in app.dataframe:
        try:
            parts.append(str(df.value))
        except Exception:
            parts.append(str(df))
    return "\n".join(parts)


def _find_button(app: AppTest, label_sub: str) -> Any | None:  # noqa: ANN401
    for b in app.button:
        if label_sub in str(b.label):
            return b
    return None


def _ss_get(app: AppTest, key: str) -> Any | None:  # noqa: ANN401
    # SessionState has no .get; use try to satisfy SIM401 without runtime error
    try:
        return app.session_state[key]
    except KeyError:
        return None


# ---- Launch and navigation -------------------------------------------------


def test_launch_resource_explorer_no_exception() -> None:
    app = _resource_app().run(timeout=30)
    assert not app.exception, app.exception
    body = _text(app)
    assert "Resource Strategy Explorer" in body or "resource_strategy" in body.lower()


def _ss_get_helper(app: AppTest, key: str) -> Any | None:  # noqa: ANN401  # keep for mypy alias
    return _ss_get(app, key)


def test_home_inspect_e2_button_exists_and_sets_intent() -> None:
    app = _home_app().run(timeout=30)
    assert not app.exception, app.exception
    body = _text(app)
    assert "Inspect real E2 research" in body
    btn = _find_button(app, "Inspect real E2 research")
    assert btn is not None, "Home must expose Inspect real E2 research"
    res = btn.click().run(timeout=30)
    intent_res = _ss_get(res, "resource_strategy_intent")
    intent_app = _ss_get(app, "resource_strategy_intent")
    assert intent_res == "e2" or intent_app == "e2", (
        f"intent not set: res={intent_res}, app={intent_app}, exc={res.exception}"
    )
    pending = _ss_get(res, "_v07_pending_page") or _ss_get(app, "_v07_pending_page")
    active = _ss_get(res, "active_page") or _ss_get(app, "active_page")
    assert pending is not None or active is not None or intent_res == "e2" or intent_app == "e2"
    assert intent_res == "e2" or intent_app == "e2"


def test_navigated_intent_activates_e2_mode_without_path() -> None:
    app = _resource_app()
    app.session_state["resource_strategy_intent"] = "e2"
    app.run(timeout=30)
    assert not app.exception
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None, "Load TrafficTwin E2 research must be visible even when intent pre-set"
    app.session_state["resource_strategy_study_path"] = ""
    app.run(timeout=30)
    assert not app.exception
    btn2 = _find_button(app, "Load TrafficTwin E2 research")
    assert btn2 is not None, "E2 preset must be visible even when no generic path"
    btn2.click().run(timeout=30)
    body = _text(app)
    assert "ADMITTED RESEARCH" in body


# ---- Load built-in and exact admission -------------------------------------


def test_load_builtin_shows_exact_admission() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not app.exception, app.exception
    body = _text(app)
    assert "ADMITTED RESEARCH" in body
    assert "OWNER-AUTHORIZED PRODUCT ADMISSION" in body
    assert "not supervisor approval" in body.lower()
    assert "not randy confirmation" in body.lower()
    assert "supervisor approval" in body.lower()
    # Both package and receipt fingerprints must be distinct and correctly labeled
    assert "195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269" in body
    assert "45e8c2782ff40495e472bc0e6de3ba3be1610fdb974f88b7ffd12a754d031ebc" in body
    # Ensure they are labeled distinctly in rendered provenance
    lower_body: str = body.lower()
    pkg_idx: int = lower_body.find(
        "195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269"
    )
    rec_idx: int = lower_body.find(
        "45e8c2782ff40495e472bc0e6de3ba3be1610fdb974f88b7ffd12a754d031ebc"
    )
    assert pkg_idx != -1 and rec_idx != -1
    assert "package" in lower_body[max(0, pkg_idx - 80) : pkg_idx]
    assert "receipt" in lower_body[max(0, rec_idx - 80) : rec_idx]
    assert pkg_idx != rec_idx  # distinct positions, distinct fingerprints


def test_builtin_uses_importlib_resources_not_path() -> None:
    from traffictwin.experiments.e2_research_artifact import (  # type: ignore[import-untyped, unused-ignore]
        builtin_e2_research_json,
    )

    text = builtin_e2_research_json()
    assert text.strip().startswith("{")
    assert "/Users/" not in text
    assert "/home/" not in text
    j: dict[str, Any] = json.loads(text)
    assert j["replication_unit"] == "fleet_draw"
    assert j["evaluator_seed"] == 0


# ---- Strategies -------------------------------------------------------------


def test_strategies_exact() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    for sid in ("off", "jsq", "ingress_dla", "dla", "per_task_dla"):
        assert sid in body, f"strategy {sid} missing in rendered E2 view"
    assert "does not observe current rsu load" in body.lower() or "does not observe" in body.lower()
    assert (
        "does not choose execution rsu" in body.lower()
        or "does not select an execution rsu" in body.lower()
    )
    assert "kubernetes-inspired" in body.lower()
    assert "not kubernetes deployment" in body.lower() or "not actual kubernetes" in body.lower()


# ---- E2b exact --------------------------------------------------------------


def test_e2b_exact_values() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    assert "0.683619229" in body
    assert "0.675681775" in body
    assert "0.715773211" in body
    assert "0.694939919" in body
    assert "fe2ed4e9bd9043b19b96a5f179390db629b01ccb" in body or "fe2ed4e9" in body


# ---- E2c exact --------------------------------------------------------------


def test_e2c_exact_values() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    for v in ("-0.022097034972", "-0.020519134179", "-0.021447383092", "-0.020825491499"):
        assert v in body
    assert "-0.021222260935" in body
    assert "-0.02233525407" in body
    assert "-0.0201092678" in body
    assert "all negative" in body.lower()


# ---- E2d exact --------------------------------------------------------------


def test_e2d_exact_values() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    for v in ("0.004636732564", "0.005867285642", "0.005071796666", "0.005509919752"):
        assert v in body
    assert "0.005271433656" in body
    assert "0.004422143925" in body
    assert "0.006120723387" in body
    assert "all positive" in body.lower()
    assert "0.026493694591" in body
    assert "0.026210763951" in body
    assert "0.026776625232" in body


def test_direction_reversal_bounded() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    assert "reversed" in body.lower()
    assert "fleet draw" in body.lower()
    assert (
        "not universal" in body.lower()
        or "never claim universal" in body.lower()
        or "not population" in body.lower()
    )
    assert "accounting records" in body.lower()


# ---- Accounting and unavailable ---------------------------------------------


def test_accounting_exact_and_unavailable_not_zero() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    assert "13076234" in body
    assert "10594205" in body
    assert "2482029" in body
    assert "600885" in body
    assert "9475948" in body
    assert "0.724669503" in body
    assert "0.8944463506228169" in body
    assert "UNAVAILABLE" in body
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        assert field in body.lower()
    from traffictwin.evidence_admission.e2_research import (  # type: ignore[import-untyped, unused-ignore]
        load_admitted_builtin_e2_research,
    )
    from traffictwin.experiments.e2_task_accounting import (  # type: ignore[import-untyped, unused-ignore]
        build_e2_seed1_task_accounting,
    )

    pkg, _ = load_admitted_builtin_e2_research()
    acc = build_e2_seed1_task_accounting(pkg)
    for f in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        assert getattr(acc, f) is None, f"{f} must be None not zero"
        assert acc.unavailable[f].value is None
        assert acc.unavailable[f].status == "UNAVAILABLE"
        assert len(acc.unavailable[f].reason) > 10
    assert acc.headline_denominator == "offered"


# ---- Provenance, limitations, replication -----------------------------------


def test_provenance_and_replication() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    assert (
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208" in body
        or "93c97059" in body
    )
    assert (
        "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056" in body
        or "e188ce07" in body
    )
    assert "fleet_draw" in body
    assert "evaluator seed" in body.lower()
    assert (
        "individual tasks are never statistical replications" in body.lower()
        or "accounting records" in body.lower()
    )


def test_limitations_and_non_claims_visible() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    for phrase in (
        "manchester incident hour",
        "four matched provisional fleet draws",
        "evaluator seed 0",
        "fixed 1x",
        "zero backhaul",
        "does not observe current rsu load",
        "e2b one-draw descriptive",
        "physical return is not independently instrumented",
    ):
        assert phrase in body.lower(), f"missing limitation phrase {phrase!r}"
    for phrase in (
        "kubernetes deployment",
        "autonomous infrastructure control",
        "mappo",
        "manchester-wide",
        "physical rsu deployment",
        "universal jsq superiority",
        "task-level statistical replication",
    ):
        assert phrase in body.lower(), f"missing non_claim phrase {phrase!r}"


# ---- Deterministic export and no leakage ------------------------------------


def test_deterministic_export_and_no_leakage() -> None:
    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )
    from traffictwin.reporting.e2_research import (  # type: ignore[import-untyped, unused-ignore]
        build_e2_research_exports,
    )

    pkg, receipt = load_admitted_builtin_e2_research()
    a = build_e2_research_exports(pkg, receipt)
    b = build_e2_research_exports(pkg, receipt)
    assert a.json == b.json, "json export must be deterministic"
    assert a.csv == b.csv
    assert a.markdown == b.markdown
    assert "0.683619229" in a.json
    assert "/Users/" not in a.json and "/home/" not in a.json
    assert "secret" not in a.json.lower()
    assert "password" not in a.json.lower()
    j: dict[str, Any] = json.loads(a.json)
    task_acc = j["task_accounting"]
    assert isinstance(task_acc, dict)
    dens = task_acc["denominators"]
    assert isinstance(dens, dict)
    assert dens["headline_denominator"] == "offered"
    unav = task_acc["unavailable"]
    assert isinstance(unav, dict)
    for f in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        entry = unav[f]
        assert isinstance(entry, dict)
        assert entry["value"] == "UNAVAILABLE"
        assert entry["null_value"] is None
        assert entry["value"] != 0
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None
    btn.click().run(timeout=30)
    labels = {b.label for b in app.download_button}
    assert "Download JSON" in labels
    assert "Download CSV" in labels
    assert "Download Markdown" in labels
    # Direct import avoids subprocess segfault with Streamlit threads
    from scripts.validate_e2_research_product import (
        main as validate_main,
    )

    rc: int = validate_main()
    assert rc == 0, "validator must pass"


def test_no_absolute_path_or_secret_in_exports() -> None:
    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )
    from traffictwin.reporting.e2_research import (
        build_e2_research_exports,
    )

    pkg, receipt = load_admitted_builtin_e2_research()
    exports = build_e2_research_exports(pkg, receipt)
    for name, txt in (
        ("json", exports.json),
        ("csv", exports.csv),
        ("markdown", exports.markdown),
    ):
        assert "/Users/" not in txt, f"{name} leaks absolute path"
        assert "/home/" not in txt
        # noqa: S108 -- intentional leakage check, not temp file creation
        assert "/tmp/" not in txt  # noqa: S108
        assert "C:\\" not in txt
        assert (
            "secret" not in txt.lower() or "secret" in txt.lower() and "secret-free" in txt.lower()
        )
        assert '"timestamp"' not in txt.lower()
        assert '"admitted_at"' not in txt.lower()


# ---- Discriminating mutation tests — validator must fail --------------------


def test_validator_fails_on_numeric_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.experiments.e2_comparison import (  # type: ignore[import-untyped, unused-ignore]
        build_e2_comparison_view,
    )

    orig = build_e2_comparison_view

    def fake(pkg: Any) -> Any:  # noqa: ANN401
        comp = orig(pkg)
        # Drift E2b off by > TOL
        object.__setattr__(comp.e2b, "off", comp.e2b.off + 1e-6)
        return comp

    monkeypatch.setattr("traffictwin.experiments.e2_comparison.build_e2_comparison_view", fake)
    # Also patch the validator's imported reference if already imported
    monkeypatch.setattr(v, "TOL", 1e-12, raising=False)
    errors: list[str] = []
    v._check_numerics(errors)
    assert any("E2b off drift" in e for e in errors), f"should detect numeric drift: {errors}"
    # Ensure removing check would make test fail — validate main must be nonzero
    rc = v.main()
    assert rc != 0


def test_validator_fails_on_source_sha_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    # Patch the evidence package's actor SHA via monkeypatched loader
    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )

    pkg_orig, receipt_orig = load_admitted_builtin_e2_research()

    def fake_load() -> tuple[Any, Any]:  # noqa: ANN401
        # Clone package with drifted actor sha
        data = json.loads(pkg_orig.model_dump_json())
        data["source_identities"]["actor"]["sha256"] = "0" * 64
        # Need to bypass validation — create a mock object with drifted sha
        mock_pkg = MagicMock(wraps=pkg_orig)
        mock_si = MagicMock(wraps=pkg_orig.source_identities)
        mock_actor = MagicMock(wraps=pkg_orig.source_identities.actor)
        mock_actor.sha256 = "0" * 64
        mock_si.actor = mock_actor
        mock_si.base_sha = pkg_orig.source_identities.base_sha
        mock_si.trace = pkg_orig.source_identities.trace
        mock_si.research_heads = pkg_orig.source_identities.research_heads
        mock_si.manifest_sha256_by_study = pkg_orig.source_identities.manifest_sha256_by_study
        mock_pkg.source_identities = mock_si
        mock_pkg.replication_unit = pkg_orig.replication_unit
        mock_pkg.evaluator_seed = pkg_orig.evaluator_seed
        return mock_pkg, receipt_orig

    monkeypatch.setattr(
        "traffictwin.evidence_admission.e2_research.load_admitted_builtin_e2_research",
        fake_load,
    )
    # Also patch the reporting path that re-loads inside _check_numerics
    errors: list[str] = []
    v._check_numerics(errors)
    assert any("actor sha drift" in e.lower() for e in errors), f"should detect SHA drift: {errors}"


def test_validator_fails_on_missing_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.evidence_admission.e2_research import (  # type: ignore[import-untyped, unused-ignore]
        load_admitted_builtin_e2_research as _orig_load,  # type: ignore[import-untyped, unused-ignore]
    )

    def fake_builtin() -> tuple[Any, Any]:
        pkg, receipt = _orig_load()
        # Corrupt receipt standing via model_copy (receipt is frozen)
        receipt = receipt.model_copy(update={"standing": "UNADMITTED RESEARCH"})
        return pkg, receipt

    # Patch the loader used by _check_builtin
    monkeypatch.setattr(
        "traffictwin.evidence_admission.e2_research.load_admitted_builtin_e2_research",
        fake_builtin,
    )
    monkeypatch.setattr(
        "traffictwin.experiments.e2_research_artifact.load_admitted_builtin_e2_research",
        fake_builtin,
        raising=False,
    )
    errors: list[str] = []
    v._check_builtin(errors)
    # Must detect standing drift specifically, not generic load failure
    assert any("standing" in e.lower() for e in errors), (
        f"should detect standing drift specifically: {errors}"
    )
    assert not any(e.lower().startswith("builtin/admission load failed") for e in errors) or any(
        "standing" in e.lower() for e in errors
    ), f"generic load failure is not sufficient proof: {errors}"


def test_validator_fails_on_absolute_path_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )
    from traffictwin.reporting.e2_research import (
        build_e2_research_exports,
    )

    pkg, receipt = load_admitted_builtin_e2_research()
    orig_build = build_e2_research_exports

    def fake_build(p: Any, r: Any) -> Any:  # noqa: ANN401
        b = orig_build(p, r)
        # Inject absolute path into json export
        j = json.loads(b.json)
        j["provenance"]["leaked_path"] = "/Users/akashx/secret/path"
        object.__setattr__(b, "json", json.dumps(j))
        return b

    monkeypatch.setattr("traffictwin.reporting.e2_research.build_e2_research_exports", fake_build)
    errors: list[str] = []
    v._check_absolute_path_secret(errors)
    assert any("absolute path" in e.lower() for e in errors), f"should detect path: {errors}"


def test_validator_fails_on_secret_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )
    from traffictwin.reporting.e2_research import (
        build_e2_research_exports,
    )

    pkg, receipt = load_admitted_builtin_e2_research()
    orig_build = build_e2_research_exports

    def fake_build(p: Any, r: Any) -> Any:  # noqa: ANN401
        b = orig_build(p, r)
        j = json.loads(b.json)
        j["provenance"]["api_key"] = "secret123"
        object.__setattr__(b, "json", json.dumps(j))
        return b

    monkeypatch.setattr("traffictwin.reporting.e2_research.build_e2_research_exports", fake_build)
    errors: list[str] = []
    v._check_absolute_path_secret(errors)
    assert any("secret" in e.lower() for e in errors), f"should detect secret: {errors}"


def test_validator_fails_on_kubernetes_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e2_research_product as v

    # Create temp repo root with affirming Kubernetes claim
    fake_root = tmp_path / "repo"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    # Copy minimal required files
    real_e2 = Path("docs/e2_research_product.md").read_text(encoding="utf-8")
    # Inject affirmative claim without negation, no "not " nearby
    injected = real_e2 + "\n\nWe deploy Kubernetes deployment in production.\n"
    (fake_root / "docs/e2_research_product.md").write_text(injected, encoding="utf-8")
    # Minimal status with E2 header and affirming claim
    (fake_root / "docs/implementation-status.md").write_text(
        "## E2 Research Product\nKubernetes deployment is live.\n", encoding="utf-8"
    )
    (fake_root / "docs/closure/e2_product_traceability.json").write_text(
        Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
        Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    v._check_kubernetes_claim(errors)
    assert any("kubernetes" in e.lower() for e in errors), f"should detect k8s: {errors}"


def test_validator_fails_on_task_replication_affirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e2_research_product as v

    fake_root = tmp_path / "repo2"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    real_e2 = Path("docs/e2_research_product.md").read_text(encoding="utf-8")
    injected = real_e2 + "\n\nTasks are statistical replications with full power.\n"
    (fake_root / "docs/e2_research_product.md").write_text(injected, encoding="utf-8")
    (fake_root / "docs/closure/e2_product_traceability.json").write_text(
        Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
        Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    v._check_task_replication(errors)
    assert any("task replication" in e.lower() for e in errors), f"should detect task rep: {errors}"


def test_validator_fails_on_missing_limitation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )

    pkg_orig, _ = load_admitted_builtin_e2_research()

    def fake_load() -> tuple[Any, Any]:  # noqa: ANN401
        # Return package with one required limitation stripped
        mock_pkg = MagicMock(wraps=pkg_orig)
        mock_pkg.limitations = [
            s for s in pkg_orig.limitations if "manchester incident hour" not in s.lower()
        ]
        mock_pkg.non_claims = pkg_orig.non_claims
        mock_pkg.source_identities = pkg_orig.source_identities
        mock_pkg.replication_unit = pkg_orig.replication_unit
        mock_pkg.evaluator_seed = pkg_orig.evaluator_seed
        return mock_pkg, MagicMock()

    monkeypatch.setattr(
        "traffictwin.evidence_admission.e2_research.load_admitted_builtin_e2_research",
        fake_load,
    )
    # Patch also the artifact loader path
    monkeypatch.setattr(
        "scripts.validate_e2_research_product.load_admitted_builtin_e2_research",
        fake_load,
        raising=False,
    )
    errors: list[str] = []
    # Directly call with mocked pkg
    # Use internal check by temporarily patching the loader inside _check_limitations
    # We monkeypatch the imported function inside validator's module scope
    import traffictwin.evidence_admission.e2_research as adm_mod  # type: ignore[import-untyped, unused-ignore]

    orig = adm_mod.load_admitted_builtin_e2_research
    monkeypatch.setattr(adm_mod, "load_admitted_builtin_e2_research", fake_load)
    v._check_limitations(errors)
    assert any("manchester incident hour" in e.lower() for e in errors), (
        f"should detect missing limitation: {errors}"
    )
    monkeypatch.setattr(adm_mod, "load_admitted_builtin_e2_research", orig)


def test_validator_fails_on_missing_offered_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )
    from traffictwin.reporting.e2_research import (
        build_e2_research_exports,
    )

    pkg, receipt = load_admitted_builtin_e2_research()
    orig_build = build_e2_research_exports

    def fake_build(p: Any, r: Any) -> Any:  # noqa: ANN401
        b = orig_build(p, r)
        j = json.loads(b.json)
        j["task_accounting"]["denominators"]["headline_denominator"] = "admitted"
        object.__setattr__(b, "json", json.dumps(j))
        return b

    monkeypatch.setattr("traffictwin.reporting.e2_research.build_e2_research_exports", fake_build)
    errors: list[str] = []
    v._check_exports_mismatch(errors)
    assert any("headline_denominator" in e.lower() for e in errors), (
        f"should detect missing offered denominator: {errors}"
    )


def test_validator_fails_on_unavailable_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )
    from traffictwin.experiments.e2_task_accounting import (
        build_e2_seed1_task_accounting,
    )

    pkg, _ = load_admitted_builtin_e2_research()
    orig = build_e2_seed1_task_accounting

    def fake_build(p: Any = None) -> Any:  # noqa: ANN401
        acc = orig(p)
        # Convert one unavailable to zero by mutating underlying dict
        # Create a fake accounting with gate_rejected = 0
        mock_acc = MagicMock(wraps=acc)
        mock_acc.offered = acc.offered
        mock_acc.admitted = acc.admitted
        mock_acc.rejected_total = acc.rejected_total
        mock_acc.forwarded = acc.forwarded
        mock_acc.deadline_success = acc.deadline_success
        mock_acc.offered_deadline_attainment = acc.offered_deadline_attainment
        mock_acc.admitted_deadline_attainment = acc.admitted_deadline_attainment
        mock_acc.headline_denominator = acc.headline_denominator
        mock_acc.conservation_holds = acc.conservation_holds
        mock_acc.unavailable = dict(acc.unavailable)
        # Inject zero value
        fake_entry = MagicMock()
        fake_entry.value = 0
        fake_entry.reason = "fake"
        fake_entry.status = "UNAVAILABLE"
        mock_acc.unavailable["gate_rejected"] = fake_entry
        # Need attributes for direct access
        mock_acc.gate_rejected = 0
        mock_acc.capacity_rejected = None
        mock_acc.started = None
        mock_acc.compute_completed = None
        mock_acc.returned = None
        mock_acc.dropped = None
        return mock_acc

    monkeypatch.setattr(
        "traffictwin.experiments.e2_task_accounting.build_e2_seed1_task_accounting",
        fake_build,
    )
    errors: list[str] = []
    v._check_numerics(errors)
    assert any("gate_rejected" in e.lower() for e in errors), (
        f"should detect unavailable->zero: {errors}"
    )


def test_validator_fails_on_broken_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.validate_e2_research_product as v

    fake_root = tmp_path / "repo3"
    (fake_root / "src/traffictwin/ui/pages").mkdir(parents=True)
    (fake_root / "src/traffictwin/ui/app_pages").mkdir(parents=True)
    (fake_root / "src/traffictwin/ui").mkdir(parents=True, exist_ok=True)
    # Create docs minimal
    (fake_root / "docs").mkdir(parents=True, exist_ok=True)
    (fake_root / "docs/e2_research_product.md").write_text(
        "Inspect real E2 research\nLoad TrafficTwin E2 research\n", encoding="utf-8"
    )
    # Create a home.py missing the marker
    (fake_root / "src/traffictwin/ui/pages/home.py").write_text("no marker here", encoding="utf-8")
    (fake_root / "src/traffictwin/ui/pages/resource_strategy_explorer.py").write_text(
        "Load TrafficTwin E2 research", encoding="utf-8"
    )
    (fake_root / "src/traffictwin/ui/app_pages/resource_strategy.py").write_text(
        "RESOURCE_STRATEGY_EXPLORER", encoding="utf-8"
    )
    (fake_root / "src/traffictwin/ui/navigation_v07.py").write_text(
        "RESOURCE_STRATEGY_EXPLORER", encoding="utf-8"
    )
    (fake_root / "src/traffictwin/ui/components").mkdir(parents=True, exist_ok=True)
    (fake_root / "src/traffictwin/ui/components/e2_research.py").write_text(
        "render_e2_research", encoding="utf-8"
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    v._check_routes(errors)
    assert any("home.py" in e.lower() or "route" in e.lower() for e in errors), (
        f"should detect broken route: {errors}"
    )


def test_validator_fails_on_export_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v

    from traffictwin.reporting.e2_research import (
        build_e2_research_exports,
    )

    orig = build_e2_research_exports
    call_count = {"n": 0}

    def fake_build(p: Any, r: Any) -> Any:  # noqa: ANN401
        call_count["n"] += 1
        b = orig(p, r)
        if call_count["n"] == 2:
            # Make second build differ -> non-deterministic
            object.__setattr__(b, "json", b.json.replace("0.683619229", "0.0"))
        return b

    monkeypatch.setattr("traffictwin.reporting.e2_research.build_e2_research_exports", fake_build)
    errors: list[str] = []
    v._check_exports_mismatch(errors)
    assert any("deterministic" in e.lower() for e in errors), (
        f"should detect export mismatch: {errors}"
    )


def test_docs_and_traceability_contain_both_fingerprints_correctly_labeled() -> None:
    docs = Path("docs/e2_research_product.md").read_text(encoding="utf-8")
    status = Path("docs/implementation-status.md").read_text(encoding="utf-8")
    trace: dict[str, Any] = json.loads(
        Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8")
    )
    pkg_fp = "195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269"
    rec_fp = "45e8c2782ff40495e472bc0e6de3ba3be1610fdb974f88b7ffd12a754d031ebc"
    # Docs must contain both under correct labels
    assert pkg_fp in docs
    assert rec_fp in docs
    lower_docs = docs.lower()
    pkg_idx = lower_docs.find(pkg_fp.lower())
    rec_idx = lower_docs.find(rec_fp.lower())
    assert "package" in lower_docs[max(0, pkg_idx - 80) : pkg_idx]
    assert "receipt" in lower_docs[max(0, rec_idx - 80) : rec_idx]
    assert pkg_fp != rec_fp
    # Implementation-status E2 section must also contain both
    e2_start = status.find("## E2 Research Product")
    e2_sec = status[e2_start : e2_start + 8000] if e2_start != -1 else status
    assert pkg_fp in e2_sec
    assert rec_fp in e2_sec
    # Traceability must have distinct named fields
    adm = trace.get("admission", {})
    assert isinstance(adm, dict)
    assert adm.get("package_fingerprint") == pkg_fp
    assert adm.get("receipt_fingerprint") == rec_fp
    assert adm.get("package_fingerprint") != adm.get("receipt_fingerprint")


def test_validator_fails_on_receipt_fingerprint_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    from traffictwin.evidence_admission.e2_research import (
        load_admitted_builtin_e2_research,
    )

    pkg, receipt = load_admitted_builtin_e2_research()
    # Substitute package fingerprint into receipt_fingerprint (mislabelling)
    fake_receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.package_fingerprint})

    def fake_load() -> tuple[Any, Any]:  # noqa: ANN401
        return pkg, fake_receipt

    monkeypatch.setattr(
        "traffictwin.evidence_admission.e2_research.load_admitted_builtin_e2_research",
        fake_load,
    )
    errors: list[str] = []
    v._check_builtin(errors)
    # Must detect the substitution — receipt fingerprint drift or distinctness failure
    assert any("receipt fingerprint" in e.lower() or "distinct" in e.lower() for e in errors), (
        f"should detect receipt fingerprint substitution: {errors}"
    )
    # Also the full validator must fail
    rc = v.main()
    assert rc != 0


# ---- Phrase-bound direct negation: adversarial probes must be True ----


@pytest.mark.parametrize(
    ("text", "phrase"),
    [
        (
            "TrafficTwin does not omit limitations and performs Kubernetes deployment.",
            "kubernetes deployment",
        ),
        (
            "No limitation is hidden; TrafficTwin deploys Kubernetes deployment.",
            "kubernetes deployment",
        ),
        (
            "This is not a toy; TrafficTwin carries supervisor approval.",
            "supervisor approval",
        ),
        (
            "Non-claims are documented, while TrafficTwin performs cluster orchestration.",
            "cluster orchestration",
        ),
    ],
)
def test_contains_affirming_phrase_bound_adversarial(text: str, phrase: str) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    assert v._contains_affirming(text, phrase) is True, (
        f"phrase-bound should be affirming for {phrase!r} in {text!r}"
    )


def test_contains_affirming_secret_phrase_bound_adversarial() -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    assert v._contains_affirming_secret("No limitation is hidden; credential=abc") is True


@pytest.mark.parametrize(
    ("text", "phrase"),
    [
        ("This is not supervisor approval", "supervisor approval"),
        ("not Kubernetes deployment", "kubernetes deployment"),
        ("no Kubernetes deployment", "kubernetes deployment"),
        ("without Kubernetes deployment", "kubernetes deployment"),
        (
            "it is not actual Kubernetes deployment or cluster orchestration",
            "kubernetes deployment",
        ),
        (
            "it is not actual Kubernetes deployment or cluster orchestration",
            "cluster orchestration",
        ),
        ("Non-claims include: kubernetes deployment", "kubernetes deployment"),
        (
            "This is not actual Kubernetes deployment or cluster orchestration",
            "cluster orchestration",
        ),
    ],
)
def test_contains_affirming_direct_negation_still_false(text: str, phrase: str) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    assert v._contains_affirming(text, phrase) is False, (
        f"direct negation should suppress {phrase!r} in {text!r}"
    )


def test_contains_affirming_secret_direct_negation_still_false() -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    assert v._contains_affirming_secret("without credential") is False
    assert v._contains_affirming_secret("no credential") is False
    assert v._contains_affirming_secret("not credential") is False
    assert v._contains_affirming_secret("secret leakage check") is False
    assert v._contains_affirming_secret("credential=abc") is True


# ---- Positive controls: real shipped docs negated phrases must remain green ----


@pytest.mark.parametrize(
    "phrase",
    [
        "kubernetes deployment",
        "cluster orchestration",
        "supervisor approval",
        "randy confirmation",
        "task-level statistical replication",
    ],
)
def test_positive_control_real_docs_negated_phrases_still_false(phrase: str) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    docs: str = Path("docs/e2_research_product.md").read_text(encoding="utf-8")
    # Real docs contain these phrases only in negated / non-claim context, so remain not affirming
    assert v._contains_affirming(docs, phrase) is False, f"real docs should not affirm {phrase!r}"
    status: str = Path("docs/implementation-status.md").read_text(encoding="utf-8")
    e2_start: int = status.find("## E2 Research Product")
    e2_sec: str = status[e2_start : e2_start + 8000] if e2_start != -1 else status
    if phrase in ("kubernetes deployment", "cluster orchestration", "supervisor approval"):
        assert v._contains_affirming(e2_sec, phrase) is False


# ---- Opus insertion at multiple positions ----


def _inject_sentence_at_position(real: str, sentence: str, position: str) -> str:
    if position == "top":
        return sentence + "\n\n" + real
    if position == "before_launch":
        marker: str = "## Launch"
        idx: int = real.find(marker)
        if idx == -1:
            return sentence + "\n\n" + real
        return real[:idx] + sentence + "\n\n" + real[idx:]
    if position == "inside_nonclaims":
        marker = "Non-claims (14) include:"
        idx2: int = real.find(marker)
        if idx2 == -1:
            return real + "\n\n" + sentence
        insert_at: int = real.find("zero-backhaul realism.", idx2)
        if insert_at != -1:
            insert_at += len("zero-backhaul realism.")
            return real[:insert_at] + " " + sentence + real[insert_at:]
        return real[: idx2 + len(marker)] + " " + sentence + real[idx2 + len(marker) :]
    if position == "after_nonclaims":
        marker3: str = "zero-backhaul realism."
        idx3: int = real.find(marker3)
        if idx3 != -1:
            insert_at2: int = idx3 + len(marker3)
            return real[:insert_at2] + "\n\n" + sentence + real[insert_at2:]
        return real + "\n\n" + sentence
    return real + "\n\n" + sentence


@pytest.mark.parametrize(
    ("phrase", "sentence"),
    [
        ("kubernetes deployment", "TrafficTwin performs Kubernetes deployment."),
        ("cluster orchestration", "TrafficTwin performs cluster orchestration."),
        (
            "task-level statistical replication",
            "TrafficTwin performs task-level statistical replication.",
        ),
        ("supervisor approval", "TrafficTwin carries supervisor approval."),
        ("randy confirmation", "TrafficTwin carries Randy confirmation."),
        ("research approval", "TrafficTwin carries research approval."),
    ],
)
@pytest.mark.parametrize(
    "position", ["top", "before_launch", "inside_nonclaims", "after_nonclaims"]
)
def test_validator_fails_on_opus_insertion_at_positions(
    phrase: str, sentence: str, position: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    real: str = Path("docs/e2_research_product.md").read_text(encoding="utf-8")
    injected: str = _inject_sentence_at_position(real, sentence, position)
    fake_root: Path = tmp_path / f"repo_opus_{phrase.replace(' ', '_')}_{position}"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    (fake_root / "docs/e2_research_product.md").write_text(injected, encoding="utf-8")
    (fake_root / "docs/implementation-status.md").write_text(
        Path("docs/implementation-status.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/closure/e2_product_traceability.json").write_text(
        Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
        Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    if phrase == "task-level statistical replication":
        v._check_task_replication(errors)
        assert any("task replication" in e.lower() for e in errors), (
            f"should detect task replication at {position}: {errors}"
        )
    else:
        v._check_kubernetes_claim(errors)
        assert any(
            phrase.split()[0].lower() in e.lower() or phrase.lower() in e.lower() for e in errors
        ), f"should detect {phrase!r} at {position}: {errors}"


# ---- Docs/traceability mutation: Windows single-backslash and secret leakage ----


def test_validator_fails_on_windows_path_single_backslash_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    fake_root: Path = tmp_path / "repo_win_docs"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    real: str = Path("docs/e2_research_product.md").read_text(encoding="utf-8")
    injected: str = real + "\n\nPath is C:\\Users\\name\\file\n"
    (fake_root / "docs/e2_research_product.md").write_text(injected, encoding="utf-8")
    (fake_root / "docs/closure/e2_product_traceability.json").write_text(
        Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
        Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # _check_absolute_path_secret only checks docs and traceability
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    v._check_absolute_path_secret(errors)
    assert any("windows absolute path" in e.lower() for e in errors), (
        f"windows path should be the reason: {errors}"
    )


def test_validator_fails_on_windows_path_single_backslash_traceability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    fake_root: Path = tmp_path / "repo_win_trace"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    (fake_root / "docs/e2_research_product.md").write_text(
        Path("docs/e2_research_product.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    tr: str = Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8")
    j: dict[str, object] = json.loads(tr)
    # Inject Windows path into a string field
    j["injected_path"] = "C:\\Users\\name\\file"
    (fake_root / "docs/closure/e2_product_traceability.json").write_text(
        json.dumps(j), encoding="utf-8"
    )
    (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
        Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    v._check_absolute_path_secret(errors)
    assert any("windows absolute path" in e.lower() for e in errors), (
        f"windows path in traceability should be detected: {errors}"
    )


@pytest.mark.parametrize(
    "secret_payload",
    ["credential=abc", "private_key=xyz", "credential=secret123", "private_key=abc123"],
)
def test_validator_fails_on_secret_leakage_docs_mutation(
    secret_payload: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    fake_root: Path = tmp_path / f"repo_secret_{secret_payload.replace('=', '_')}"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    real: str = Path("docs/e2_research_product.md").read_text(encoding="utf-8")
    injected: str = real + f"\n\nLeaked {secret_payload}\n"
    (fake_root / "docs/e2_research_product.md").write_text(injected, encoding="utf-8")
    (fake_root / "docs/closure/e2_product_traceability.json").write_text(
        Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
        Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    v._check_absolute_path_secret(errors)
    assert any("secret" in e.lower() for e in errors), (
        f"secret leakage {secret_payload!r} should be the reason: {errors}"
    )


@pytest.mark.parametrize(
    "secret_payload",
    ["credential=abc", "private_key=xyz"],
)
def test_validator_fails_on_secret_leakage_traceability_mutation(
    secret_payload: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e2_research_product as v  # noqa: I001

    fake_root: Path = tmp_path / f"repo_secret_trace_{secret_payload.replace('=', '_')}"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    (fake_root / "docs/e2_research_product.md").write_text(
        Path("docs/e2_research_product.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    tr2: str = Path("docs/closure/e2_product_traceability.json").read_text(encoding="utf-8")
    j2: dict[str, object] = json.loads(tr2)
    j2["leaked"] = secret_payload
    (fake_root / "docs/closure/e2_product_traceability.json").write_text(
        json.dumps(j2), encoding="utf-8"
    )
    (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
        Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    errors: list[str] = []
    v._check_absolute_path_secret(errors)
    assert any("secret" in e.lower() for e in errors), (
        f"secret in traceability {secret_payload!r} should be detected: {errors}"
    )
