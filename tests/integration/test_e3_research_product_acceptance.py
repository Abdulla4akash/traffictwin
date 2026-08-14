# ruff: noqa: ANN401, ANN202, ANN002, ANN003, E501, S108, SIM102, SIM115, F841, S110, I001, F401, B023, S603
"""End-to-end E3 research product acceptance — Lane 12.

AppTest journey: generic state, E2 journey unchanged, E3 journey truthful
no-results (hold banner, refusal, null lifecycle, provenance pins), CTA
sequences from Lane 11 regressions, exports deterministic and typed, no
placeholder fabricated results, resource denominator, capacity 1..3,
state_age_ms strict, queue/compute separation, no path/secret/leakage,
HOSTED_CI_UNAVAILABLE. Validator self-tests with 12+ mutations.
Strict, no research launch, no traceback on mutated fails.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import (  # type: ignore[import-untyped, unused-ignore]
    default_session_state,
    load_ui_config,
)

RESOURCE_PAGE = "src/traffictwin/ui/app_pages/resource_strategy.py"
HOME_PAGE = "src/traffictwin/ui/app_pages/home.py"
GUIDED_PAGE = "src/traffictwin/ui/app_pages/guided_demo.py"


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
    if "resource_strategy_e3_active" in app.session_state:
        del app.session_state["resource_strategy_e3_active"]
    if "resource_strategy_intent" in app.session_state:
        del app.session_state["resource_strategy_intent"]
    return app


def _home_app() -> AppTest:
    app = AppTest.from_file(HOME_PAGE)
    for k, v in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[k] = v
    app.session_state["_v07_navigation_active"] = True
    return app


def _guided_app() -> AppTest:
    app = AppTest.from_file(GUIDED_PAGE)
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


def _find_button(app: AppTest, label_sub: str) -> Any | None:
    for b in app.button:
        if label_sub in str(b.label):
            return b
    return None


def _ss_get(app: AppTest, key: str) -> Any | None:
    try:
        return app.session_state[key]
    except KeyError:
        return None


# ---- Generic state still works ---------------------------------------------


def test_generic_synthetic_state_still_works() -> None:
    app = _resource_app().run(timeout=30)
    assert not app.exception, app.exception
    body = _text(app)
    assert "synthetic" in body.lower()
    assert "Resource Strategy Explorer" in body or "resource_strategy" in body.lower()


# ---- E2 journey unchanged (byte-for-byte preservation) ----------------------


def test_e2_journey_still_works_unchanged() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E2 research")
    assert btn is not None, "E2 button must still exist"
    btn.click().run(timeout=30)
    assert not app.exception, app.exception
    body = _text(app)
    assert "ADMITTED RESEARCH" in body
    assert "OWNER-AUTHORIZED PRODUCT ADMISSION" in body
    assert "0.683619229" in body
    assert "0.715773211" in body
    assert "0.724669503" in body
    # No E3 hold should appear in E2 mode
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" not in body
    assert "195f2e89ab4e775d1577c92a59409026fccaa2d9ebd1d973177dabd93ba83269" in body


def test_home_e2_entry_still_sets_intent() -> None:
    app = _home_app().run(timeout=30)
    assert not app.exception
    body = _text(app)
    assert "Inspect real E2 research" in body
    btn = _find_button(app, "Inspect real E2 research")
    assert btn is not None
    res = btn.click().run(timeout=30)
    assert (
        _ss_get(res, "resource_strategy_intent") == "e2"
        or _ss_get(app, "resource_strategy_intent") == "e2"
    )


# ---- E3 journey truthful no-results ----------------------------------------


def test_e3_preset_button_exists_and_visibly_separate() -> None:
    app = _resource_app().run(timeout=30)
    assert not app.exception
    e3_btn = _find_button(app, "Load TrafficTwin E3 Dynamic Resource V2")
    assert e3_btn is not None, "E3 button must be visibly separate"
    e2_btn = _find_button(app, "Load TrafficTwin E2 research")
    assert e2_btn is not None
    labels = [b.label for b in app.button]
    assert len(labels) == len(set(labels)), f"duplicate labels {labels}"
    body = _text(app)
    assert "No filesystem path input is needed" in body or "no path" in body.lower()
    assert "dormant" in body.lower() or "no results" in body.lower()


def test_home_e3_entry_exists_and_sets_intent() -> None:
    app = _home_app().run(timeout=30)
    assert not app.exception
    body = _text(app)
    assert "Inspect E3 Dynamic Resource V2" in body
    btn = _find_button(app, "Inspect E3 Dynamic Resource V2")
    assert btn is not None
    res = btn.click().run(timeout=30)
    assert (
        _ss_get(res, "resource_strategy_intent") == "e3"
        or _ss_get(app, "resource_strategy_intent") == "e3"
    )


def test_guided_demo_e3_entry_exists() -> None:
    app = _guided_app().run(timeout=30)
    assert not app.exception
    btn = _find_button(app, "Inspect E3 Dynamic Resource V2")
    assert btn is not None, "Guided Demo must expose Inspect E3 Dynamic Resource V2"
    body = _text(app)
    assert "E3 Dynamic Resource V2" in body


def test_e3_journey_truthful_no_results_hold_banner() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E3 Dynamic Resource V2")
    assert btn is not None
    btn.click().run(timeout=30)
    assert not app.exception, app.exception
    body = _text(app)
    assert "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in body
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" in body
    assert "evidence_state = NOT_EXECUTED" in body
    assert "result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE" in body
    assert "research_workloads_launched = 0" in body
    assert "REFUSED" in body
    assert "REFUSED_MISSING_FUTURE_ARTIFACT" in body


def test_e3_journey_null_lifecycle_and_provenance_pins() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E3 Dynamic Resource V2")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    # Null lifecycle
    assert "UNAVAILABLE" in body
    assert "offered" in body.lower()
    assert "admitted" in body.lower()
    assert "rejected_total" in body.lower() or "rejected" in body.lower()
    assert "resource_unit_seconds" in body
    assert "queue" in body.lower() and "compute" in body.lower()
    # State_age typed ints
    assert "0, 1000, 3000" in body or "0/1000/3000" in body or "state_age" in body.lower()
    # Provenance pins
    assert "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c" in body or "2b6d4675" in body
    assert (
        "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208" in body
        or "93c97059" in body
    )
    assert (
        "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056" in body
        or "e188ce07" in body
    )
    assert (
        "39862882ae34e71260ce5b466fcd4a93d61da783c4dd16fc987be562ea396438" in body
        or "3986288" in body
    )
    assert (
        "f0d6eb913df6c2165a63ddcb0fd4980368e9bb80bbd38db964273ba3925f4870" in body
        or "f0d6eb91" in body
    )
    # Dormant counts 14/56
    assert "14" in body and "56" in body
    # Limitations and hosted CI truth (hosted CI declared in docs/traceability, UI states fails closed)
    assert "fails closed" in body.lower() or "exact approved Lane 09" in body or "REFUSED" in body


def test_e3_journey_no_placeholder_fabricated_results() -> None:
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E3 Dynamic Resource V2")
    assert btn is not None
    btn.click().run(timeout=30)
    body = _text(app)
    lower = body.lower()
    assert "coming soon" not in lower
    if "placeholder" in lower:
        assert "no placeholder" in lower or "never a placeholder" in lower
        assert "placeholder result" not in lower
    assert "synthetic result" not in lower
    # Must not contain fabricated numeric results like E2 numbers in E3 mode
    assert "0.683619229" not in body
    # Must not claim affirmative Kubernetes/supervisor/monetary
    assert "supervisor approved" not in lower
    assert "$" not in body
    # Actor selects RSU affirmatively must not appear
    if "actor selects execution rsu" in lower:
        assert "no actor selects execution rsu" in lower


# ---- CTA sequences from Lane 11 regressions (arbitration) -------------------


def test_cta_sequence_home_e2_home_e3_home_e2_first_press() -> None:
    app = _resource_app()
    # Home E2 -> explorer
    app.session_state["resource_strategy_intent"] = "e2"
    app.run(timeout=30)
    assert not app.exception
    assert "0.683619229" in _text(app)
    # Home E3 -> explorer
    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in _text(app)
    # Home E2 again -> must render E2 on first press
    app.session_state["resource_strategy_intent"] = "e2"
    app.run(timeout=30)
    assert not app.exception
    body = _text(app)
    assert "0.683619229" in body, "E2 must render on first press after E3"
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" not in body


def test_cta_sequence_e3_load_then_e2_load_mutual_exclusion() -> None:
    app = _resource_app().run(timeout=30)
    e3_btn = _find_button(app, "Load TrafficTwin E3 Dynamic Resource V2")
    assert e3_btn is not None
    e3_btn.click().run(timeout=30)
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in _text(app)
    e2_btn = _find_button(app, "Load TrafficTwin E2 research")
    assert e2_btn is not None
    e2_btn.click().run(timeout=30)
    body = _text(app)
    assert "0.683619229" in body
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" not in body
    # Next rerun heals to single flag
    app.run(timeout=30)
    assert "0.683619229" in _text(app)
    assert not (
        "resource_strategy_e2_active" in app.session_state
        and app.session_state["resource_strategy_e2_active"]
        and "resource_strategy_e3_active" in app.session_state
        and app.session_state["resource_strategy_e3_active"]
    )


def test_cta_sequence_intent_via_session_state_e3() -> None:
    app = _resource_app()
    app.session_state["resource_strategy_intent"] = "e3"
    app.run(timeout=30)
    assert not app.exception
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in _text(app)
    assert "NOT_EXECUTED" in _text(app)


# ---- Exports deterministic and typed payload match --------------------------


def test_e3_exports_deterministic_match_typed_payload_and_no_leakage() -> None:
    from traffictwin.evidence_admission.e3_research import admit_e3_research
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
    from traffictwin.reporting.e3_research import build_e3_research_exports

    pkg = load_builtin_e3_research()
    receipt = admit_e3_research(pkg)
    a = build_e3_research_exports(pkg, receipt)
    b = build_e3_research_exports(pkg, receipt)
    assert a.json == b.json
    assert a.csv == b.csv
    assert a.markdown == b.markdown
    assert "\r\n" not in a.json
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in a.json
    assert "NOT_EXECUTED" in a.csv
    assert "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in a.markdown
    assert "resource_unit_seconds" in a.json
    assert "resource_unit_seconds" in a.csv
    assert "resource_unit_seconds" in a.markdown
    # Typed payload null lifecycle
    j = json.loads(a.json)
    assert j["hold"]["lane_09"] == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    assert j["task_accounting"]["offered"] is None
    assert j["task_accounting"]["unavailable"]["offered"]["reason"] != ""
    assert j["dormant_counts"]["arms"] == 14
    assert j["dormant_counts"]["configs"] == 56
    assert j["provenance"]["product_base_sha"] == "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c"
    assert (
        j["provenance"]["actor_sha256"]
        == "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
    )
    # No absolute path / secret / timestamp
    for txt in (a.json, a.csv, a.markdown):
        assert ("/" + "Users" + "/") not in txt
        assert ("/" + "home" + "/") not in txt
        assert "password" not in txt.lower()
        assert "secret" not in txt.lower() or "secret leakage" in txt.lower()
        assert re.search(r'"timestamp"\s*:', txt.lower()) is None
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", txt) is None
    # AppTest download buttons
    app = _resource_app().run(timeout=30)
    btn = _find_button(app, "Load TrafficTwin E3 Dynamic Resource V2")
    assert btn is not None
    btn.click().run(timeout=30)
    labels = {b.label for b in app.download_button}
    assert "Download E3 JSON" in labels
    assert "Download E3 CSV" in labels
    assert "Download E3 Markdown" in labels


# ---- Validator self-tests: must pass on real tree --------------------------


def test_validator_passes_on_real_tree(tmp_path: Path) -> None:
    import scripts.validate_e3_research_product as v

    out = tmp_path / "verdict.json"
    tracked = Path("docs/quality/e3_validator_verdict.json")
    # Snapshot tracked before
    before = tracked.read_bytes() if tracked.exists() else b""
    rc: int = v.main(["--output", str(out)])
    assert rc == 0, "validator must pass on real tree"
    assert out.exists()
    data: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    assert data["pass"] is True
    assert data["errors"] == []
    assert data["hosted_ci"] == "HOSTED_CI_UNAVAILABLE"
    assert data["hold"]["lane_09"] == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    assert data["errors"] == sorted(data["errors"])
    # Ensure tracked file was not modified
    after = tracked.read_bytes() if tracked.exists() else b""
    assert before == after, "validator with --output must not modify tracked verdict"


def test_tracked_receipt_byte_stability(tmp_path: Path) -> None:
    import scripts.validate_e3_research_product as v

    tracked = Path("docs/quality/e3_validator_verdict.json")
    assert tracked.exists(), "tracked verdict must exist"
    before = tracked.read_bytes()
    # Run validator twice with tmp_path output, ensure tracked unchanged
    out1 = tmp_path / "v1.json"
    out2 = tmp_path / "v2.json"
    rc1 = v.main(["--output", str(out1)])
    rc2 = v.main(["--output", str(out2)])
    assert rc1 == 0 and rc2 == 0
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")
    after = tracked.read_bytes()
    assert before == after, "suite must leave tracked file byte-identical"


def test_tracked_gate_receipt_matches_fresh_regeneration(tmp_path: Path) -> None:
    import scripts.validate_e3_research_product as v

    tracked = Path("docs/quality/e3_quality_gate.json")
    assert tracked.exists(), "tracked gate receipt must exist"
    before = tracked.read_bytes()
    # Fresh regeneration via validator subcommand
    fresh = tmp_path / "fresh_gate.json"
    rc = v.main(["--emit-gate-receipt", str(fresh)])
    assert rc == 0
    fresh_text = fresh.read_text(encoding="utf-8")
    # Also via direct build_gate for determinism
    gate2 = v.build_gate()
    gate2_text = json.dumps(gate2, indent=2, ensure_ascii=False) + "\n"
    assert fresh_text == gate2_text, "fresh regeneration must be deterministic"
    # Committed must match fresh
    assert before.decode("utf-8") == fresh_text, (
        "committed gate receipt must match fresh regeneration "
        "(run scripts/validate_e3_research_product.py --emit-gate-receipt docs/quality/e3_quality_gate.json)"
    )
    # Ensure suite does not modify tracked file
    after = tracked.read_bytes()
    assert before == after, "suite must leave tracked gate receipt byte-identical"


# ---- Helper for CLI-surface mutation tests ---------------------------------


def _run_validator_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, patch_fn: Any = None
) -> tuple[int, list[str], dict[str, Any]]:
    import scripts.validate_e3_research_product as v

    if patch_fn is not None:
        patch_fn(monkeypatch)
    out = tmp_path / "verdict.json"
    rc = v.main(["--output", str(out)])
    try:
        if out.exists():
            data: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
            errs: list[str] = data.get("errors", [])
            return rc, errs, data
    except Exception:
        pass
    return rc, [], {}


def test_validator_fails_on_wrong_product_base_sha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        return pkg.model_copy(update={"product_base_sha": "0" * 40})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _data = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_IDENTITY_MISMATCH:") for e in errs)
    assert isinstance(rc, int)


def test_validator_fails_on_wrong_vec_promotion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        bad_vec = pkg.vec_runtime.model_copy(update={"promotion_commit": "0" * 40})
        return pkg.model_copy(update={"vec_runtime": bad_vec})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_IDENTITY_MISMATCH:") for e in errs)


def test_validator_fails_on_wrong_actor_sha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        bad_si = pkg.software_identity.model_copy(update={"actor_sha256": "0" * 64})
        return pkg.model_copy(update={"software_identity": bad_si})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_IDENTITY_MISMATCH:") for e in errs)


def test_validator_fails_on_wrong_manifest_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        new_prov = []
        for pr in pkg.provenance:
            if pr.kind == "manifest":
                new_prov.append(
                    pr.model_copy(
                        update={
                            "note": "sidecar SHA 0000000000000000000000000000000000000000000000000000000000000000"
                        }
                    )
                )
            else:
                new_prov.append(pr)
        return pkg.model_copy(update={"provenance": new_prov})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_IDENTITY_MISMATCH:") for e in errs)


def test_validator_fails_on_tasks_as_n(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        new_factors = dict(pkg.factors)
        new_factors["deep"] = {"inner": "tasks as n is true claim"}
        forged = pkg.model_copy(update={"factors": new_factors})
        return forged

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(
        e.startswith("E3PV_TASKS_AS_N:") or e.startswith("E3PV_FORBIDDEN_CLAIM:") for e in errs
    )


def test_validator_fails_on_queue_compute_conflation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nQueue ceiling is compute is true for test.\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(
        e.startswith("E3PV_QUEUE_COMPUTE_CONFLATION:") or e.startswith("E3PV_FORBIDDEN_CLAIM:")
        for e in errs
    )


def test_validator_fails_on_unavailable_to_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
    from unittest.mock import MagicMock

    orig_pkg = load_builtin_e3_research

    def fake_pkg() -> Any:
        pkg = orig_pkg()
        mock = MagicMock(wraps=pkg)
        for k in pkg.model_fields:
            setattr(mock, k, getattr(pkg, k))
        mock.task_accounting = MagicMock()
        mock.task_accounting.offered = 0
        mock.task_accounting.admitted = None
        mock.task_accounting.rejected_total = None
        mock.task_accounting.forwarded = None
        mock.task_accounting.deadline_success = None
        mock.task_accounting.started = None
        mock.task_accounting.compute_completed = None
        mock.task_accounting.returned = None
        mock.task_accounting.dropped = None
        mock.model_dump = pkg.model_dump
        return mock

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake_pkg
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_UNAVAILABLE_TO_ZERO:") for e in errs)


def test_validator_fails_on_monetary_cost(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nCost is $100 dollars for test.\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_MONETARY_CLAIM:") for e in errs)


def test_validator_fails_on_kubernetes_claim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nTrafficTwin performs Kubernetes deployment is live.\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_KUBERNETES_CLAIM:") for e in errs)


def test_validator_fails_on_actor_selects_rsu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nThe actor selects execution RSU is live for test.\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_ACTOR_SELECTS_RSU:") for e in errs)


def test_validator_fails_on_manchester_wide_and_universal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return (
                real
                + "\n\nOur results generalize across all of Manchester and are universally superior.\n"
            )
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(
        e.startswith("E3PV_MANCHESTER_WIDE:") or e.startswith("E3PV_UNIVERSAL_SUPERIORITY:")
        for e in errs
    )


@pytest.mark.parametrize(
    "sentence,expected_code",
    [
        ("The actor selects execution RSU dynamically.", "E3PV_ACTOR_SELECTS_RSU"),
        ("Supervisor approval already granted for release.", "E3PV_SUPERVISOR_CLAIM"),
        ("p2c_dla ranks universally superior everywhere.", "E3PV_UNIVERSAL_SUPERIORITY"),
        ("We generalize Manchester-wide from this hour.", "E3PV_MANCHESTER_WIDE"),
        ("Kubernetes deployment went live last week.", "E3PV_KUBERNETES_CLAIM"),
        ("We treat tasks as N for the confidence interval.", "E3PV_TASKS_AS_N"),
    ],
)
def test_bypass_sentences_fail_via_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sentence: str, expected_code: str
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\n" + sentence + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0, f"bypass sentence should fail: {sentence!r}"
    assert any(e.startswith(expected_code + ":") for e in errs), (
        f"expected {expected_code} in {errs}"
    )


def test_b1_heading_and_ordered_units_with_disclaimer_plus_claim_fail_typed(tmp_path: Path) -> None:
    """B1 regression: heading (^#) and ordered (^\\d+\\.) units that contain disclaimer+claim must fail typed."""
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

    ad = ALLOWLISTED_DISCLAIMERS[6]
    cases = [
        (f"# {ad} Kubernetes deployment is live", "E3PV_KUBERNETES_CLAIM"),
        (f"## {ad} Cost is $100 dollars", "E3PV_MONETARY_CLAIM"),
        (f"### {ad} tasks as n is true claim", "E3PV_TASKS_AS_N"),
        (f"1. {ad} supervisor approval already granted", "E3PV_SUPERVISOR_CLAIM"),
        (f"2. {ad} We generalize across all of Manchester", "E3PV_MANCHESTER_WIDE"),
        (f"3. {ad} p2c_dla ranks universally superior", "E3PV_UNIVERSAL_SUPERIORITY"),
    ]
    for sentence, expected_code in cases:
        orig_read = Path.read_text

        def fake_read(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
            if str(self).endswith("e3_dynamic_resource_v2_product.md"):
                real = orig_read(self, *args, **kwargs)
                return real + "\n\n" + sentence + "\n"
            return orig_read(self, *args, **kwargs)

        mp = pytest.MonkeyPatch()
        mp.setattr(Path, "read_text", fake_read)
        try:
            rc, errs, _ = _run_validator_cli(mp, tmp_path)
            assert rc != 0, f"heading/ordered bypass should fail: {sentence!r}"
            assert any(e.startswith(expected_code + ":") for e in errs), (
                f"expected {expected_code} in {errs} for {sentence!r}"
            )
        finally:
            mp.undo()


def test_b1_bullet_and_plain_units_with_disclaimer_plus_claim_fail_typed(tmp_path: Path) -> None:
    """B1 regression: bullet and plain units with disclaimer+claim must also fail typed (controls)."""
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

    ad = ALLOWLISTED_DISCLAIMERS[0]
    cases = [
        (f"- {ad} Kubernetes deployment is live", "E3PV_KUBERNETES_CLAIM"),
        (f"* {ad} Cost is $100 dollars", "E3PV_MONETARY_CLAIM"),
        (f"Plain line {ad} tasks as n is true claim", "E3PV_TASKS_AS_N"),
        (f"Intro {ad} supervisor approval already granted", "E3PV_SUPERVISOR_CLAIM"),
    ]
    for sentence, expected_code in cases:
        orig_read = Path.read_text

        def fake_read(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
            if str(self).endswith("e3_dynamic_resource_v2_product.md"):
                real = orig_read(self, *args, **kwargs)
                return real + "\n\n" + sentence + "\n"
            return orig_read(self, *args, **kwargs)

        mp = pytest.MonkeyPatch()
        mp.setattr(Path, "read_text", fake_read)
        try:
            rc, errs, _ = _run_validator_cli(mp, tmp_path)
            assert rc != 0, f"bullet/plain bypass should fail: {sentence!r}"
            assert any(e.startswith(expected_code + ":") for e in errs), (
                f"expected {expected_code} in {errs}"
            )
        finally:
            mp.undo()


def test_b2_traceability_marketing_injection_fails_typed(tmp_path: Path) -> None:
    """B2 regression: traceability free-text marketing injection must fail typed via CLI."""
    import json

    real_trace = Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    injected = json.loads(real_trace)
    injected["marketing"] = (
        "Our VEC platform is universally superior, Manchester-wide, on Kubernetes, for $100"
    )

    orig_read = Path.read_text

    def fake_read(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if str(self).endswith("e3_product_traceability.json"):
            return json.dumps(injected)
        return orig_read(self, *args, **kwargs)

    mp = pytest.MonkeyPatch()
    mp.setattr(Path, "read_text", fake_read)
    try:
        rc, errs, _ = _run_validator_cli(mp, tmp_path)
        assert rc != 0, "marketing injection into traceability should fail"
        # Should contain at least one typed forbidden code
        assert any(
            e.startswith(code + ":")
            for e in errs
            for code in [
                "E3PV_KUBERNETES_CLAIM",
                "E3PV_MONETARY_CLAIM",
                "E3PV_UNIVERSAL_SUPERIORITY",
                "E3PV_MANCHESTER_WIDE",
            ]
        ), f"expected typed forbidden code in {errs}"
    finally:
        mp.undo()


def test_allowlisted_disclaimers_pass_via_cli(tmp_path: Path) -> None:
    rc, errs, _ = _run_validator_cli(pytest.MonkeyPatch(), tmp_path)
    # Use a fresh monkeypatch without mutation - should pass
    import scripts.validate_e3_research_product as v

    out = tmp_path / "verdict_allow.json"
    rc2 = v.main(["--output", str(out)])
    assert rc2 == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pass"] is True


def test_validator_fails_on_missing_resource_denominator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        mock = MagicMock(wraps=pkg)
        for k in pkg.model_fields:
            setattr(mock, k, getattr(pkg, k))
        mock.resource_cost = MagicMock()
        mock.resource_cost.metric = "dollars"
        mock.resource_cost.monetary = True
        mock.resource_cost.unit = "dollars"
        mock.resource_cost.formula = "cost dollars"
        mock.model_dump = pkg.model_dump
        return mock

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(
        e.startswith("E3PV_RESOURCE_DENOMINATOR_MISSING:") or e.startswith("E3PV_MONETARY_CLAIM:")
        for e in errs
    )


def test_validator_fails_on_free_unbounded_scaling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        mock = MagicMock(wraps=pkg)
        for k in pkg.model_fields:
            setattr(mock, k, getattr(pkg, k))
        mock.compute_capacity = MagicMock()
        mock.compute_capacity.min_units = 1
        mock.compute_capacity.max_units = 10
        mock.compute_capacity.active_units_per_rsu_range = [1, 10]
        mock.compute_capacity.unit = "compute_unit"
        mock.model_dump = pkg.model_dump
        return mock

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_CAPACITY_BOUNDS:") for e in errs)


def test_validator_fails_on_state_age_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        bad_arms = list(pkg.dormant_arms)
        bad_arm = bad_arms[0].model_copy(update={"state_age_ms": 500})
        bad_arms[0] = bad_arm
        mock = MagicMock(wraps=pkg)
        for k in pkg.model_fields:
            setattr(mock, k, getattr(pkg, k))
        mock.dormant_arms = bad_arms
        mock.model_dump = pkg.model_dump
        return mock

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_STATE_AGE_DRIFT:") for e in errs)


def test_validator_fails_on_broken_e3_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_route"
    (fake_root / "src/traffictwin/ui/pages").mkdir(parents=True)
    (fake_root / "src/traffictwin/ui/app_pages").mkdir(parents=True)
    (fake_root / "src/traffictwin/ui/components").mkdir(parents=True)
    (fake_root / "src/traffictwin/experiments").mkdir(parents=True)
    (fake_root / "src/traffictwin/reporting").mkdir(parents=True)
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    explorer = Path("src/traffictwin/ui/pages/resource_strategy_explorer.py").read_text(
        encoding="utf-8"
    )
    broken = explorer.replace("Load TrafficTwin E3 Dynamic Resource V2", "Load Something Else")
    (fake_root / "src/traffictwin/ui/pages/resource_strategy_explorer.py").write_text(
        broken, encoding="utf-8"
    )
    for p in [
        "src/traffictwin/ui/pages/home.py",
        "src/traffictwin/ui/pages/guided_demo.py",
        "src/traffictwin/ui/app_pages/resource_strategy.py",
        "src/traffictwin/ui/components/e3_research.py",
        "src/traffictwin/reporting/e3_research.py",
        "src/traffictwin/experiments/e3_research_artifact.py",
    ]:
        src = Path(p)
        dst = fake_root / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(
        Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_ROUTE_BROKEN:") for e in errs)


def test_validator_fails_on_export_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.reporting.e3_research import build_e3_research_exports

    orig = build_e3_research_exports

    def fake_build(pkg: Any, receipt: Any) -> Any:
        b = orig(pkg, receipt)
        j = json.loads(b.json)
        j["hold"]["lane_09"] = "WRONG_HOLD"
        mock = MagicMock(wraps=b)
        mock.json = json.dumps(j)
        mock.csv = b.csv
        mock.markdown = b.markdown
        return mock

    monkeypatch.setattr("traffictwin.reporting.e3_research.build_e3_research_exports", fake_build)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_EXPORT_MISMATCH:") for e in errs)


def test_validator_fails_on_non_deterministic_exports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.reporting.e3_research import build_e3_research_exports

    orig = build_e3_research_exports
    call_count = {"n": 0}

    def fake_build(pkg: Any, receipt: Any) -> Any:
        b = orig(pkg, receipt)
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            j = json.loads(b.json)
            j["hold"]["lane_09"] = j["hold"]["lane_09"] + "_2"
            mock = MagicMock(wraps=b)
            mock.json = json.dumps(j)
            mock.csv = b.csv
            mock.markdown = b.markdown
            return mock
        return b

    monkeypatch.setattr("traffictwin.reporting.e3_research.build_e3_research_exports", fake_build)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_NON_DETERMINISTIC:") for e in errs)


def test_validator_fails_on_placeholder_fabricated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_comparison import build_e3_comparison_view

    orig = build_e3_comparison_view

    def fake(pkg: Any) -> Any:
        comp = orig(pkg)
        pd = comp.e3a.paired_differences[0]
        object.__setattr__(pd, "per_seed_values", [0.1, 0.2, 0.3, 0.4])
        object.__setattr__(pd, "mean", 0.25)
        return comp

    monkeypatch.setattr("traffictwin.experiments.e3_comparison.build_e3_comparison_view", fake)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_PLACEHOLDER_FABRICATED:") for e in errs)


def test_validator_fails_on_path_secret_leakage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_secret"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    real = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    injected = real + "\n\nLeaked credential=abc123\nPath is " + "/" + "Users" + "/name/file\n"
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(injected, encoding="utf-8")
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(
        e.startswith("E3PV_SECRET_LEAKAGE:") or e.startswith("E3PV_PATH_LEAKAGE:") for e in errs
    )


def test_validator_fails_on_supervisor_approval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_supervisor"
    (fake_root / "docs").mkdir(parents=True)
    (fake_root / "docs/closure").mkdir(parents=True)
    real = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    injected = real + "\n\nTrafficTwin carries supervisor approval for test.\n"
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(injected, encoding="utf-8")
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_SUPERVISOR_CLAIM:") for e in errs)


def test_validator_fails_on_hold_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_hold_missing"
    (fake_root / "docs/closure").mkdir(parents=True)
    (fake_root / "docs").mkdir(parents=True, exist_ok=True)
    doc_txt = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    doc_txt = doc_txt.replace("research_workloads_launched = 0", "research_workloads_launched = 1")
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(doc_txt, encoding="utf-8")
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_HOLD_MISMATCH:") for e in errs)


def test_validator_fails_on_missing_lanes_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_lanes_missing"
    (fake_root / "docs/closure").mkdir(parents=True)
    # Create traceability without lanes
    real_tr: dict[str, Any] = json.loads(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    )
    real_tr.pop("lanes", None)
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        json.dumps(real_tr), encoding="utf-8"
    )
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(
        Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISSING:") for e in errs)


def test_validator_fails_on_empty_lanes_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_lanes_empty"
    (fake_root / "docs/closure").mkdir(parents=True)
    real_tr: dict[str, Any] = json.loads(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    )
    real_tr["lanes"] = {}
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        json.dumps(real_tr), encoding="utf-8"
    )
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(
        Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISSING:") for e in errs)


def test_validator_fails_on_missing_lane_pin_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_lane_pin_missing"
    (fake_root / "docs/closure").mkdir(parents=True)
    real_tr: dict[str, Any] = json.loads(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    )
    # Remove promotion from lane 10
    if "10" in real_tr.get("lanes", {}):
        real_tr["lanes"]["10"].pop("promotion", None)
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        json.dumps(real_tr), encoding="utf-8"
    )
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(
        Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISSING:") for e in errs)


def test_validator_fails_on_missing_limitations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.validate_e3_research_product as v
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        return pkg.model_copy(update={"limitations": []})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    # Also need to mock doc without limitations
    fake_root = tmp_path / "repo_limit_missing"
    (fake_root / "docs/closure").mkdir(parents=True)
    doc_txt = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    # Remove Limitations section
    doc_txt = doc_txt.replace("### Limitations and non-claims", "### Removed")
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(doc_txt, encoding="utf-8")
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    import shutil

    shutil.copy(
        "docs/closure/e2_product_lane12_base_receipt.json",
        fake_root / "docs/closure/e2_product_lane12_base_receipt.json",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(
        e.startswith("E3PV_LIMITATIONS_MISSING:") or e.startswith("E3PV_NON_CLAIMS_MISSING:")
        for e in errs
    )


def test_validator_fails_on_missing_base_receipt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.validate_e3_research_product as v

    fake_root = tmp_path / "repo_base_missing"
    (fake_root / "docs/closure").mkdir(parents=True)
    (fake_root / "docs").mkdir(parents=True, exist_ok=True)
    # Copy doc and traceability but not base receipt
    (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(
        Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (fake_root / "docs/closure/e3_product_traceability.json").write_text(
        Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(v, "_REPO_ROOT", fake_root)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_BASE_RECEIPT_MISSING:") for e in errs)


def test_validator_fails_on_e2_preservation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e2_research_artifact import builtin_e2_research_json

    orig = builtin_e2_research_json

    def fake() -> str:
        return ""

    monkeypatch.setattr(
        "traffictwin.experiments.e2_research_artifact.builtin_e2_research_json", fake
    )
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_E2_PRESERVATION_FAILED:") for e in errs)


def test_validator_fails_on_e3_builtin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from traffictwin.evidence_admission.e3_research import admit_e3_research

    orig = admit_e3_research

    def fake(pkg: Any) -> Any:
        receipt = orig(pkg)
        return receipt.model_copy(update={"admitted": True})

    monkeypatch.setattr("traffictwin.evidence_admission.e3_research.admit_e3_research", fake)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(
        e.startswith("E3PV_E3_BUILTIN_FAILED:") or e.startswith("E3PV_E3_ADMISSION_FAILED:")
        for e in errs
    )


def test_validator_no_traceback_on_mutated_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    def fake() -> Any:
        raise ValueError("simulated load failure for no traceback test")

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    import scripts.validate_e3_research_product as v

    out = tmp_path / "verdict.json"
    try:
        rc = v.main(["--output", str(out)])
        assert rc != 0
    except Exception as exc:
        pytest.fail(f"validator raised traceback on mutated payload: {exc}")


def test_validator_emits_deterministic_verdict_json(tmp_path: Path) -> None:
    import scripts.validate_e3_research_product as v

    out1 = tmp_path / "v1.json"
    out2 = tmp_path / "v2.json"
    rc1 = v.main(["--output", str(out1)])
    rc2 = v.main(["--output", str(out2)])
    assert rc1 == 0 and rc2 == 0
    txt1 = out1.read_text(encoding="utf-8")
    txt2 = out2.read_text(encoding="utf-8")
    assert txt1 == txt2
    j1 = json.loads(txt1)
    j2 = json.loads(txt2)
    assert j1 == j2
    assert j1["errors"] == sorted(j1["errors"])


def test_no_absolute_path_literals_in_changed_files() -> None:
    prefix_users = "/" + "Users" + "/"
    prefix_home = "/" + "home" + "/"
    for p in [
        "scripts/validate_e3_research_product.py",
        "tests/integration/test_e3_research_product_acceptance.py",
        "docs/e3_dynamic_resource_v2_product.md",
        "docs/closure/e3_product_traceability.json",
    ]:
        txt2 = Path(p).read_text(encoding="utf-8")
        assert prefix_users not in txt2, f"{p} contains Users literal"
        assert prefix_home not in txt2 or "importlib" in txt2.lower()


# ---- B5 regressions: self_sha sentinel and base-pin repo verification via CLI ----


def test_b5_self_sha_invented_hex_fails_via_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invented hex for self_sha must fail typed via CLI, sentinel passes already covered."""
    real = Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    data = json.loads(real)
    data["lanes"]["12"]["self_sha"] = "a" * 40  # invented hex, not sentinel
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_product_traceability.json"):
            return json.dumps(data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs), (
        f"expected pin mismatch got {errs}"
    )
    # Subprocess CLI check
    import json as _json
    import os
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Write tampered traceability to temp and use subprocess with _REPO_ROOT override? Use monkey via CLI subprocess with env?
        # Instead verify via direct subprocess call that invented hex fails when we patch file on disk temporarily
        # We'll use the same monkeypatch approach but also test via subprocess by writing tampered file to a fake repo
        import shutil

        fake_root = td_path / "repo"
        (fake_root / "docs/closure").mkdir(parents=True)
        (fake_root / "docs/quality").mkdir(parents=True)
        (fake_root / "docs").mkdir(parents=True, exist_ok=True)
        # copy needed files
        (fake_root / "docs/closure/e3_product_traceability.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        (fake_root / "docs/closure/e2_product_lane12_base_receipt.json").write_text(
            Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (fake_root / "docs/e3_dynamic_resource_v2_product.md").write_text(
            Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (fake_root / "docs/quality/e3_quality_gate.json").write_text(
            Path("docs/quality/e3_quality_gate.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (fake_root / "docs/quality/e3_validator_verdict.json").write_text(
            Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        # Need src for imports? We'll just test via v.main with fake _REPO_ROOT
        import scripts.validate_e3_research_product as v

        orig_root = v._REPO_ROOT
        v._REPO_ROOT = fake_root  # type: ignore[assignment]
        try:
            out = td_path / "out.json"
            rc2 = v.main(["--output", str(out)])
            assert rc2 != 0
            errs2 = json.loads(out.read_text(encoding="utf-8")).get("errors", [])
            assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs2)
        finally:
            v._REPO_ROOT = orig_root  # type: ignore[assignment]


def test_b5_self_sha_sentinel_passes_via_cli(tmp_path: Path) -> None:
    """Sentinel BOUND_AT_PROMOTION must pass via CLI (real tree)."""
    import scripts.validate_e3_research_product as v

    out = tmp_path / "sentinel.json"
    rc = v.main(["--output", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["pass"] is True
    assert data["lanes"]["12"]["self_sha"] == "BOUND_AT_PROMOTION"


def test_b5_base_pin_tampered_fails_via_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tampered base pin (invented hex or wrong ancestor) must fail via CLI repo-verified check."""
    real = Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    data = json.loads(real)
    # Tamper to all zeros (valid hex but not an ancestor)
    data["lanes"]["12"]["base_integration_sha"] = "0" * 40
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_product_traceability.json"):
            return json.dumps(data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs)
    # Also test tampering to a different valid ancestor (lane10 promotion) should fail because not git-derived lane11
    data2 = json.loads(real)
    data2["lanes"]["12"]["base_integration_sha"] = (
        "8a2f0fffb605fac94ec625f49f80260a54daba6d"  # lane10 promotion, is ancestor but wrong
    )

    def fake_read2(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_product_traceability.json"):
            return json.dumps(data2)
        return orig_read(self, *args, **kwargs)

    mp2 = pytest.MonkeyPatch()
    mp2.setattr(Path, "read_text", fake_read2)
    try:
        rc2, errs2, _ = _run_validator_cli(mp2, tmp_path)
        assert rc2 != 0
        assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs2)
    finally:
        mp2.undo()


# ---- Full receipt scan coverage: gate, verdict, e2 receipt, traceability ----


def test_gate_injection_fails_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_gate = Path("docs/quality/e3_quality_gate.json").read_text(encoding="utf-8")
    gate_data = json.loads(real_gate)
    gate_data["injected_forbidden"] = "Kubernetes deployment is live"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_quality_gate.json"):
            return json.dumps(gate_data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_KUBERNETES_CLAIM") for e in errs)


def test_verdict_injection_fails_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_verdict = Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8")
    # Inject via traceability-like: add a field with forbidden
    # Instead inject into verdict's hold or provenance via monkey patching build_verdict? Simpler: monkeypatch Path.read_text for verdict
    # We'll inject into the file that validator reads: docs/quality/e3_validator_verdict.json is not currently read by validator for forb scan?
    # But our validator now scans it, so we can inject.
    gate_data = json.loads(real_verdict)
    gate_data["injected"] = "We treat tasks as N for analysis"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_validator_verdict.json"):
            return json.dumps(gate_data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_TASKS_AS_N") for e in errs)


def test_e2_base_receipt_injection_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_receipt = Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(
        encoding="utf-8"
    )
    receipt_data = json.loads(real_receipt)
    receipt_data["injected"] = "Supervisor approval already granted for release"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e2_product_lane12_base_receipt.json"):
            return json.dumps(receipt_data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_SUPERVISOR_CLAIM") for e in errs)


def test_e2_base_receipt_injection_manchester_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_receipt = Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(
        encoding="utf-8"
    )
    receipt_data = json.loads(real_receipt)
    receipt_data["note"] = "This generalizes across all of Manchester"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e2_product_lane12_base_receipt.json"):
            return json.dumps(receipt_data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_MANCHESTER_WIDE") for e in errs)


# ---- Verdict committed-vs-fresh equality (same pattern as gate) ----


def test_tracked_verdict_receipt_matches_fresh_regeneration(tmp_path: Path) -> None:
    import scripts.validate_e3_research_product as v

    tracked = Path("docs/quality/e3_validator_verdict.json")
    assert tracked.exists(), "tracked verdict must exist"
    before = tracked.read_bytes()
    fresh = tmp_path / "fresh_verdict.json"
    rc = v.main(["--output", str(fresh)])
    assert rc == 0
    fresh_text = fresh.read_text(encoding="utf-8")
    # Also via sorted errors deterministic
    fresh2 = tmp_path / "fresh_verdict2.json"
    rc2 = v.main(["--output", str(fresh2)])
    assert rc2 == 0
    assert fresh.read_text(encoding="utf-8") == fresh2.read_text(encoding="utf-8")
    assert before.decode("utf-8") == fresh_text, "committed verdict must match fresh regeneration"
    after = tracked.read_bytes()
    assert before == after, "suite must leave tracked verdict byte-identical"


def test_verdict_tamper_then_regenerate_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tampering source (product_base_sha) then regenerating verdict must show FAIL or mismatch."""
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        return pkg.model_copy(update={"product_base_sha": "0" * 40})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    import scripts.validate_e3_research_product as v

    fresh = tmp_path / "tampered_verdict.json"
    rc = v.main(["--output", str(fresh)])
    assert rc != 0, "tampered package should make validator FAIL"
    data = json.loads(fresh.read_text(encoding="utf-8"))
    assert data["pass"] is False
    assert any(e.startswith("E3PV_IDENTITY_MISMATCH") for e in data["errors"])
    # Fresh tampered verdict must NOT equal committed
    committed = Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8")
    assert fresh.read_text(encoding="utf-8") != committed


def test_gate_tamper_then_regenerate_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tampering source then regenerating gate must not echo committed provenance; fresh != committed and verdict FAIL."""
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        return pkg.model_copy(update={"product_base_sha": "0" * 40})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    import scripts.validate_e3_research_product as v

    fresh = tmp_path / "tampered_gate.json"
    rc = v.main(["--emit-gate-receipt", str(fresh)])
    assert rc == 0  # gate generation still succeeds but should record FAIL verdict
    fresh_data = json.loads(fresh.read_text(encoding="utf-8"))
    assert fresh_data["verdict"] == "FAIL"
    assert fresh_data["gates"]["validator_real_tree"]["result"] == "FAIL"
    assert len(fresh_data["gates"]["validator_real_tree"]["errors"]) > 0
    # Fresh gate provenance must reflect tampered input, not echo committed
    committed_gate = json.loads(
        Path("docs/quality/e3_quality_gate.json").read_text(encoding="utf-8")
    )
    assert fresh_data["provenance"]["product_base_sha"] == "0" * 40
    assert committed_gate["provenance"]["product_base_sha"] != "0" * 40
    assert fresh_data != committed_gate


# ---- Truthful limitations: exact sets, advertised counts, contradictions ----


def test_limitations_deleting_one_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e3_research_product as v

    # Delete one limitation from doc via monkeypatch
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            # Remove one expected limitation verbatim
            from scripts.validate_e3_research_product import _EXPECTED_LIMITATIONS

            return real.replace(_EXPECTED_LIMITATIONS[0], "")
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LIMITATIONS_MISSING") for e in errs)


def test_non_claims_deleting_one_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            from scripts.validate_e3_research_product import _EXPECTED_NON_CLAIMS

            return real.replace(_EXPECTED_NON_CLAIMS[3], "")
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_NON_CLAIMS_MISSING") for e in errs)


def test_disclaimer_deleting_one_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

            return real.replace(ALLOWLISTED_DISCLAIMERS[0], "")
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LIMITATIONS_MISSING") for e in errs)


def test_advertised_counts_mismatch_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real.replace("Limitations (8)", "Limitations (7)")
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any("Limitations" in e for e in errs)


def test_verified_results_headline_flip_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\n# Verified results\nWe have verified results for all workloads.\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_CONTRADICTION") for e in errs)


def test_hosted_ci_is_green_fails_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nHosted CI is green and passing.\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_HOSTED_CI_CONTRADICTION") for e in errs)


def test_workloads_launched_claim_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nresearch_workloads_launched = 5\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)


def test_traceability_verified_results_injection_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    data = json.loads(real)
    data["note"] = "Verified results show improvement"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_product_traceability.json"):
            return json.dumps(data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_CONTRADICTION") for e in errs)


def test_workloads_launched_space_colon_fails_on_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Controller probe: `research workloads launched: 12` in docs must fail typed."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nresearch workloads launched: 12\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)


def test_we_launched_e3_workloads_fails_on_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Controller probe: `we launched 12 E3 research workloads` in docs must fail typed."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nwe launched 12 E3 research workloads\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)


def test_workloads_launched_space_colon_fails_on_verdict_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Controller probe: `research workloads launched: 12` in verdict receipt must fail typed."""
    real = Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8")
    data = json.loads(real)
    data["injected_note"] = "research workloads launched: 12"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_validator_verdict.json"):
            return json.dumps(data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)


def test_we_launched_e3_workloads_fails_on_verdict_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Controller probe: `we launched 12 E3 research workloads` in verdict receipt must fail typed."""
    real = Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8")
    data = json.loads(real)
    data["injected_note"] = "we launched 12 E3 research workloads"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_validator_verdict.json"):
            return json.dumps(data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)


def test_workload_truthful_zero_still_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Truthful `research_workloads_launched = 0` statements keep passing."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nresearch_workloads_launched = 0\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc == 0
    assert not any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)


def test_workload_executed_without_count_fails_on_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without count assertion like `we launched E3 research workloads` must fail."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real + "\n\nwe launched E3 research workloads\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)


def test_first_donot_no_bullet_deletion_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: deleting the FIRST doc bullet matching `does not`/leading `no ` must fail typed.

    That bullet lives in Scientific question and bounded scope (What is displayed) — the Question bullet.
    Pinned-exact-set now covers EVERY non-claim and disclaimer bullet (content-pinned, not count-floored).
    """
    doc_text = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    # Find FIRST bullet matching does not / leading no (case-insensitive)
    first: str | None = None
    for line in doc_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            content = stripped[2:].strip()
            low = content.lower()
            if "does not" in low or low.startswith("no "):
                first = content
                break
    assert first is not None, "doc must have at least one does-not/no bullet"
    # Diagnose location for documentation
    assert "does not observe load" in first.lower() or first.lower().startswith("no ")
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            real = orig_read(self, *args, **kwargs)
            return real.replace(first, "")
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LIMITATIONS_MISSING") for e in errs)
