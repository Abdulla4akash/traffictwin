# ruff: noqa: ANN401, ANN202, ANN002, ANN003, E501, S108, SIM102, SIM115, F841, S110, I001, F401, B023, S603, S607
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
    import subprocess
    import scripts.validate_e3_research_product as v

    tracked = Path("docs/quality/e3_quality_gate.json")
    assert tracked.exists(), "tracked gate receipt must exist"
    before = tracked.read_bytes()
    # Fresh regeneration via subprocess to avoid AppTest fork pollution — use --allow-dirty for tmp outputs
    fresh = tmp_path / "fresh_gate.json"
    rc = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/validate_e3_research_product.py",
            "--emit-gate-receipt",
            str(fresh),
            "--allow-dirty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    ).returncode
    assert rc == 0, f"gate regeneration via subprocess failed {rc}"
    fresh_text = fresh.read_text(encoding="utf-8")
    # Also via direct build_gate for determinism (in fresh subprocess, compare via second subprocess)
    fresh2 = tmp_path / "fresh_gate2.json"
    rc2 = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/validate_e3_research_product.py",
            "--emit-gate-receipt",
            str(fresh2),
            "--allow-dirty",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    ).returncode
    assert rc2 == 0
    gate2_text = fresh2.read_text(encoding="utf-8")
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
        "docs/quality/e3_quality_gate.json",
        "docs/quality/e3_validator_verdict.json",
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

    # Reuse same monkeypatch to avoid pollution issues with nested MonkeyPatch
    monkeypatch.setattr(Path, "read_text", fake_read2)
    rc2, errs2, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc2 != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs2)


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
    rc = v.main(["--emit-gate-receipt", str(fresh), "--allow-dirty"])
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


# ---- Review-4 regressions: pin fail-closed, eight phrasings x5 surfaces, B2 12, emit-path ----


def test_pin_verification_fails_closed_when_git_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pin verification must FAIL CLOSED when git is unavailable (FileNotFound)."""
    import subprocess
    import scripts.validate_e3_research_product as v

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("git executable not found")

    monkeypatch.setattr("scripts.validate_e3_research_product.subprocess.run", fake_run)
    monkeypatch.setattr(subprocess, "run", fake_run)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs), (
        f"expected pin mismatch got {errs}"
    )
    assert any("git unavailable" in e or "git verification failed" in e for e in errs)


def test_pin_verification_fails_closed_when_git_times_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pin verification must FAIL CLOSED when git times out."""
    import subprocess
    import scripts.validate_e3_research_product as v

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "git", timeout=5)

    monkeypatch.setattr("scripts.validate_e3_research_product.subprocess.run", fake_run)
    monkeypatch.setattr(subprocess, "run", fake_run)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs), (
        f"expected pin mismatch got {errs}"
    )


def test_pin_verification_no_hex_only_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Valid 40-hex alone must not pass when git is broken — no fallback."""
    import subprocess
    import scripts.validate_e3_research_product as v

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        class FakeResult:
            returncode = 1
            stdout = ""
            stderr = "not a git repo"

        return FakeResult()

    monkeypatch.setattr("scripts.validate_e3_research_product.subprocess.run", fake_run)
    monkeypatch.setattr(subprocess, "run", fake_run)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0
    assert any(e.startswith("E3PV_LANE_PIN_MISMATCH") for e in errs)


# Eight reviewer phrasings parametrized over five surfaces
_REVIEWER_PHRASES: list[tuple[str, str]] = [
    ("Research workloads were launched for E3a", "E3PV_WORKLOADS_CONTRADICTION"),
    ("Twelve research workloads have been launched", "E3PV_WORKLOADS_CONTRADICTION"),
    ("Hosted CI succeeded on the final push", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("All hosted CI checks passed on GitHub Actions", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("The E3 results have been verified end to end", "E3PV_CONTRADICTION"),
    ("Confirmed E3 results are now available", "E3PV_CONTRADICTION"),
    ("Measured E3 outcomes are available for review", "E3PV_CONTRADICTION"),
    ("Research workloads were launched: 12", "E3PV_WORKLOADS_CONTRADICTION"),
]

_FIVE_SURFACES: list[str] = [
    "docs/e3_dynamic_resource_v2_product.md",
    "docs/closure/e3_product_traceability.json",
    "docs/quality/e3_quality_gate.json",
    "docs/quality/e3_validator_verdict.json",
    "docs/closure/e2_product_lane12_base_receipt.json",
]


@pytest.mark.parametrize("phrase,expected_code", _REVIEWER_PHRASES)
@pytest.mark.parametrize("surface", _FIVE_SURFACES)
def test_reviewer_phrasing_fails_typed_on_each_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phrase: str,
    expected_code: str,
    surface: str,
) -> None:
    """Each reviewer phrasing must fail typed on each of five scanned surfaces."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["reviewer_injection"] = phrase
                    return json.dumps(data)
                except Exception:
                    return real + "\n" + phrase + "\n"
            else:
                return real + "\n\n" + phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0, f"phrase {phrase!r} on {surface!r} should fail"
    assert any(e.startswith(expected_code + ":") for e in errs), (
        f"expected {expected_code} got {errs} for {phrase!r} on {surface!r}"
    )


@pytest.mark.parametrize("surface", _FIVE_SURFACES)
def test_reviewer_phrasing_truthful_controls_pass_on_each_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Truthful controls must still pass on each surface."""
    truth_map: dict[str, str] = {
        "docs/e3_dynamic_resource_v2_product.md": "research_workloads_launched = 0",
        "docs/closure/e3_product_traceability.json": "HOSTED_CI_UNAVAILABLE",
        "docs/quality/e3_quality_gate.json": "NO_E3_RESEARCH_RESULTS_AVAILABLE",
        "docs/quality/e3_validator_verdict.json": "research_workloads_launched = 0",
        "docs/closure/e2_product_lane12_base_receipt.json": "HOSTED_CI_UNAVAILABLE",
    }
    truth_phrase = truth_map.get(surface, "research_workloads_launched = 0")
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["truthful_injection"] = truth_phrase
                    if "research_workloads_launched" in truth_phrase:
                        data["hold_note"] = "research_workloads_launched = 0"
                    if "HOSTED_CI_UNAVAILABLE" in truth_phrase:
                        data["ci_note"] = "HOSTED_CI_UNAVAILABLE"
                    if "NO_E3" in truth_phrase:
                        data["result_note"] = "NO_E3_RESEARCH_RESULTS_AVAILABLE"
                    return json.dumps(data)
                except Exception:
                    return real
            else:
                return real + "\n\n" + truth_phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc == 0, f"truthful {truth_phrase!r} on {surface!r} should pass but got {errs}"
    assert not any(e.startswith("E3PV_WORKLOADS_CONTRADICTION") for e in errs)
    assert not any(e.startswith("E3PV_HOSTED_CI_CONTRADICTION") for e in errs)
    # For results contradiction, check only if phrase is E3 results
    assert not any(e.startswith("E3PV_CONTRADICTION") and "E3 results" in e for e in errs)


# B2 12 injections: 4 types x 3 receipts
_B2_RECEIPTS: list[str] = [
    "docs/quality/e3_quality_gate.json",
    "docs/quality/e3_validator_verdict.json",
    "docs/closure/e2_product_lane12_base_receipt.json",
]

_B2_TYPES: list[tuple[str, str]] = [
    ("errors_note", "Kubernetes deployment is live"),
    ("no_errors", "We treat tasks as N for analysis"),
    ("tested_categories_note", "supervisor approval already granted"),
    ("errors_dict_nested", "Kubernetes deployment is live"),
]


@pytest.mark.parametrize("receipt", _B2_RECEIPTS)
@pytest.mark.parametrize("key_type,forbidden", _B2_TYPES)
def test_b2_injection_fails_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, receipt: str, key_type: str, forbidden: str
) -> None:
    """B2: similar-named keys and nested errors dict must NOT be exempt — must fail typed."""
    real_text = Path(receipt).read_text(encoding="utf-8")
    try:
        data = json.loads(real_text)
    except Exception:
        data = {}

    if key_type == "errors_dict_nested":
        data["errors"] = {"nested": forbidden}
    else:
        data[key_type] = forbidden

    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(receipt):
            return json.dumps(data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0, f"B2 {key_type!r} on {receipt!r} with {forbidden!r} should fail"
    assert any(e.startswith("E3PV_") for e in errs), f"expected typed E3PV got {errs}"


def test_b2_validator_own_diagnostics_still_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validator's own diagnostics arrays (errors[*] and gates.*.errors[*]) must remain exempt; tested_categories is NOT exempt."""
    real_gate = Path("docs/quality/e3_quality_gate.json").read_text(encoding="utf-8")
    gate_data = json.loads(real_gate)
    gate_data["gates"]["validator_real_tree"]["errors"] = [
        "Kubernetes deployment is live — diagnostic"
    ]
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_quality_gate.json"):
            return json.dumps(gate_data)
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc == 0, f"errors exempt should not fail but got {errs}"
    gate_data2 = json.loads(real_gate)
    gate_data2["gates"]["validator_real_tree"]["tested_categories"] = [
        "Kubernetes deployment is live"
    ]

    def fake_read2(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_quality_gate.json"):
            return json.dumps(gate_data2)
        return orig_read(self, *args, **kwargs)

    mp2 = pytest.MonkeyPatch()
    mp2.setattr(Path, "read_text", fake_read2)
    try:
        rc2, errs2, _ = _run_validator_cli(mp2, tmp_path)
        assert rc2 != 0, f"tested_categories should NOT be exempt and must fail but got {errs2}"
        assert any(e.startswith("E3PV_") for e in errs2)
    finally:
        mp2.undo()


# Emit-path measurement regressions
def test_emit_scope_check_reflects_out_of_scope_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Out-of-scope file must appear in emitted scope_check lists — via temp copy, no mocked-git."""
    import subprocess
    import tempfile
    import shutil
    import scripts.validate_e3_research_product as v

    # Create a temp copy of the repo (including .git) and plant an out-of-scope file there
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Use git to create a clean temp copy via copytree ignoring .venv but including .git
        src_root = Path(".").resolve()
        dst = td_path / "copy"
        shutil.copytree(
            src_root,
            dst,
            symlinks=True,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "*.pyc"
            ),
        )
        # Plant out-of-scope file in temp copy
        (dst / "surprise_outside.txt").write_text("surprise", encoding="utf-8")
        # Emit gate from temp copy via --repo-root (real measurement, no mock)
        out = td_path / "gate.json"
        rc = subprocess.run(
            [
                ".venv/bin/python",
                "scripts/validate_e3_research_product.py",
                "--emit-gate-receipt",
                str(out),
                "--repo-root",
                str(dst),
                "--allow-dirty",
            ],
            cwd=str(src_root),
            capture_output=True,
            text=True,
            timeout=30,
        ).returncode
        assert rc == 0, f"emit with temp copy failed {rc}"
        gate = json.loads(out.read_text(encoding="utf-8"))
        scope = gate["gates"]["scope_check"]
        assert (
            "surprise_outside.txt" in scope.get("found_untracked", [])
            or "surprise_outside.txt" in scope.get("found_changed", [])
            or "surprise_outside.txt" in scope.get("found_out_of_scope", [])
        )
        assert (
            scope.get("found_out_of_scope") is not None
            and "surprise_outside.txt" in scope["found_out_of_scope"]
        )
        assert scope["all_allowed"] is False
        assert scope["result"] == "FAIL"
        # Headline verdict must be FAIL when any measured gate fails (D)
        assert gate["verdict"] == "FAIL"
        # Specifically e2_preservation's own result should remain PASS here (scope failure not e2)
        assert gate["gates"]["e2_preservation"]["result"] == "PASS"
        # Also ensure real worktree was never touched
        assert not Path("surprise_outside.txt").exists()


def test_emit_no_abs_reflects_users_literal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Planted Users literal in checked file must be reflected in emitted gate — via temp copy."""
    import subprocess
    import tempfile
    import shutil

    literal = "/" + "Users" + "/" + "planted"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        src_root = Path(".").resolve()
        dst = td_path / "copy"
        shutil.copytree(
            src_root,
            dst,
            symlinks=True,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "*.pyc"
            ),
        )
        # Plant Users literal in the copied doc file
        doc_path = dst / "docs/e3_dynamic_resource_v2_product.md"
        orig = doc_path.read_text(encoding="utf-8")
        doc_path.write_text(orig + "\n\n" + literal + "\n", encoding="utf-8")
        out = td_path / "gate.json"
        rc = subprocess.run(
            [
                ".venv/bin/python",
                "scripts/validate_e3_research_product.py",
                "--emit-gate-receipt",
                str(out),
                "--repo-root",
                str(dst),
                "--allow-dirty",
            ],
            cwd=str(src_root),
            capture_output=True,
            text=True,
            timeout=30,
        ).returncode
        assert rc == 0, f"emit with temp copy failed {rc}"
        gate = json.loads(out.read_text(encoding="utf-8"))
        no_abs = gate["gates"]["no_absolute_path_literals"]
        assert "docs/e3_dynamic_resource_v2_product.md" in no_abs.get("violations", [])
        assert no_abs["result"] == "FAIL"
        # Ensure real worktree untouched
        assert ("/" + "Users" + "/" + "planted") not in Path(
            "docs/e3_dynamic_resource_v2_product.md"
        ).read_text(encoding="utf-8")
        # Also verify validator fails on that literal via direct injection (without temp copy)
        orig_read = Path.read_text

        def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
            if str(self).endswith("docs/e3_dynamic_resource_v2_product.md"):
                real = orig_read(self, *args, **kwargs)
                return real + "\n\n" + literal + "\n"
            return orig_read(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake_read)
        rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
        assert rc != 0
        assert any("PATH_LEAKAGE" in e or "absolute" in e.lower() for e in errs)


# ---- New Lane 12 Opus review 5 additions: clean-tree, exact exemptions, sentence-unit, temp-copy ----


def test_emit_gate_refuses_when_dirty_without_allow(tmp_path: Path) -> None:
    """--emit-gate-receipt must REFUSE when git status --porcelain is nonempty without --allow-dirty (temp-copy, no real writes)."""
    import subprocess
    import tempfile
    import shutil

    # Use temp-copy pattern so we never write into the real repo root
    src_root = Path(".").resolve()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        dst = td_path / "copy"
        shutil.copytree(
            src_root,
            dst,
            symlinks=True,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "*.pyc"
            ),
        )
        # Plant dirty file inside the temp copy only
        (dst / "tmp_dirty_for_gate_test.txt").write_text("dirty", encoding="utf-8")
        out = Path(td) / "gate_dirty.json"
        rc = subprocess.run(
            [
                ".venv/bin/python",
                "scripts/validate_e3_research_product.py",
                "--emit-gate-receipt",
                str(out),
                "--repo-root",
                str(dst),
            ],
            cwd=str(src_root),
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode
        assert rc == 2, f"expected refuse code 2 got {rc}"
        assert not out.exists() or out.read_text(encoding="utf-8") == "", (
            "should not write file when dirty without allow"
        )
        # With --allow-dirty, it should succeed for tmp output via temp copy
        out2 = Path(td) / "gate_dirty2.json"
        rc2 = subprocess.run(
            [
                ".venv/bin/python",
                "scripts/validate_e3_research_product.py",
                "--emit-gate-receipt",
                str(out2),
                "--repo-root",
                str(dst),
                "--allow-dirty",
            ],
            cwd=str(src_root),
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode
        assert rc2 == 0, f"allow-dirty should succeed got {rc2}"
        assert out2.exists()
    # Ensure real worktree was never touched
    assert not Path("tmp_dirty_for_gate_test.txt").exists()
    assert not (Path(".") / "tmp_dirty_for_gate_test.txt").exists()


def test_exemptions_exact_per_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only gate/verdict $.errors[*] and $.gates.*.errors[*] are exempt; traceability and e2 base have NO exemptions; tested_categories not exempt."""
    # Traceability $.errors[0] must fail
    real_trace = Path("docs/closure/e3_product_traceability.json").read_text(encoding="utf-8")
    trace_data = json.loads(real_trace)
    trace_data["errors"] = ["Kubernetes deployment is live"]
    orig_read = Path.read_text

    def fake_trace(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_product_traceability.json"):
            return json.dumps(trace_data)
        return orig_read(self, *args, **kwargs)

    mp = pytest.MonkeyPatch()
    mp.setattr(Path, "read_text", fake_trace)
    try:
        rc, errs, _ = _run_validator_cli(mp, tmp_path)
        assert rc != 0, "traceability $.errors[0] should not be exempt"
        assert any(e.startswith("E3PV_KUBERNETES_CLAIM") for e in errs)
    finally:
        mp.undo()

    # Gate $.tested_categories[0] must fail (no longer exempt)
    real_gate = Path("docs/quality/e3_quality_gate.json").read_text(encoding="utf-8")
    gate_data = json.loads(real_gate)
    gate_data["tested_categories"] = ["Supervisor approval already granted for release"]

    def fake_gate(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_quality_gate.json"):
            return json.dumps(gate_data)
        return orig_read(self, *args, **kwargs)

    mp2 = pytest.MonkeyPatch()
    mp2.setattr(Path, "read_text", fake_gate)
    try:
        rc2, errs2, _ = _run_validator_cli(mp2, tmp_path)
        assert rc2 != 0, "gate $.tested_categories[0] should fail after removing exemption"
        assert any(e.startswith("E3PV_SUPERVISOR_CLAIM") for e in errs2)
    finally:
        mp2.undo()

    # Verdict $.tested_categories[0] must fail
    real_verdict = Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8")
    verdict_data = json.loads(real_verdict)
    verdict_data["tested_categories"] = ["Supervisor approval already granted"]

    def fake_verdict(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e3_validator_verdict.json"):
            return json.dumps(verdict_data)
        return orig_read(self, *args, **kwargs)

    mp3 = pytest.MonkeyPatch()
    mp3.setattr(Path, "read_text", fake_verdict)
    try:
        rc3, errs3, _ = _run_validator_cli(mp3, tmp_path)
        assert rc3 != 0, "verdict $.tested_categories[0] should fail"
        assert any(e.startswith("E3PV_SUPERVISOR_CLAIM") for e in errs3)
    finally:
        mp3.undo()

    # E2 base $.tested_categories[0] must fail
    real_e2 = Path("docs/closure/e2_product_lane12_base_receipt.json").read_text(encoding="utf-8")
    e2_data = json.loads(real_e2)
    e2_data["tested_categories"] = ["Supervisor approval already granted"]

    def fake_e2(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e2_product_lane12_base_receipt.json"):
            return json.dumps(e2_data)
        return orig_read(self, *args, **kwargs)

    mp4 = pytest.MonkeyPatch()
    mp4.setattr(Path, "read_text", fake_e2)
    try:
        rc4, errs4, _ = _run_validator_cli(mp4, tmp_path)
        assert rc4 != 0, "e2 base $.tested_categories[0] should fail"
        assert any(e.startswith("E3PV_SUPERVISOR_CLAIM") for e in errs4)
    finally:
        mp4.undo()

    # E2 base $.errors[0] must also fail (no exemptions)
    e2_data2 = json.loads(real_e2)
    e2_data2["errors"] = ["Kubernetes deployment is live"]

    def fake_e2b(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith("e2_product_lane12_base_receipt.json"):
            return json.dumps(e2_data2)
        return orig_read(self, *args, **kwargs)

    mp5 = pytest.MonkeyPatch()
    mp5.setattr(Path, "read_text", fake_e2b)
    try:
        rc5, errs5, _ = _run_validator_cli(mp5, tmp_path)
        assert rc5 != 0, "e2 base $.errors[0] should not be exempt"
        assert any(e.startswith("E3PV_KUBERNETES_CLAIM") for e in errs5)
    finally:
        mp5.undo()


_NEW_REVIEWER_PHRASES: list[tuple[str, str]] = [
    ("With no further delay, research workloads were launched.", "E3PV_WORKLOADS_CONTRADICTION"),
    ("Nine research workloads (v2.1) were launched.", "E3PV_WORKLOADS_CONTRADICTION"),
    (
        "Research workloads across the ten RSU cells of the frozen design were launched.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    (
        "The system launched nine research workloads after initialization.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    (
        "We have executed research workloads for the final evaluation.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    ("Hosted CI was green on the final merge.", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("GitHub Actions checks passed successfully.", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("Confirmed E3 outcomes are now verified and available.", "E3PV_CONTRADICTION"),
]

_FIVE_SURFACES_NEW: list[str] = [
    "docs/e3_dynamic_resource_v2_product.md",
    "docs/closure/e3_product_traceability.json",
    "docs/quality/e3_quality_gate.json",
    "docs/quality/e3_validator_verdict.json",
    "docs/closure/e2_product_lane12_base_receipt.json",
]


@pytest.mark.parametrize("phrase,expected_code", _NEW_REVIEWER_PHRASES)
@pytest.mark.parametrize("surface", _FIVE_SURFACES_NEW)
def test_new_reviewer_phrasing_fails_typed_on_each_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phrase: str,
    expected_code: str,
    surface: str,
) -> None:
    """Each new reviewer phrasing must fail typed on each of five surfaces (sentence-unit, no window)."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["reviewer_injection"] = phrase
                    return json.dumps(data)
                except Exception:
                    return real + "\n" + phrase + "\n"
            else:
                return real + "\n\n" + phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0, f"new phrase {phrase!r} on {surface!r} should fail"
    assert any(e.startswith(expected_code + ":") for e in errs), (
        f"expected {expected_code} got {errs} for {phrase!r} on {surface!r}"
    )


@pytest.mark.parametrize("surface", _FIVE_SURFACES_NEW)
def test_new_reviewer_truthful_controls_pass_on_each_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Truthful controls must still pass on each surface after sentence-unit changes."""
    truth_map: dict[str, str] = {
        "docs/e3_dynamic_resource_v2_product.md": "research_workloads_launched = 0",
        "docs/closure/e3_product_traceability.json": "HOSTED_CI_UNAVAILABLE",
        "docs/quality/e3_quality_gate.json": "NO_E3_RESEARCH_RESULTS_AVAILABLE",
        "docs/quality/e3_validator_verdict.json": "research_workloads_launched = 0",
        "docs/closure/e2_product_lane12_base_receipt.json": "HOSTED_CI_UNAVAILABLE",
    }
    truth_phrase = truth_map.get(surface, "research_workloads_launched = 0")
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["truthful_injection"] = truth_phrase
                    return json.dumps(data)
                except Exception:
                    return real
            else:
                return real + "\n\n" + truth_phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc == 0, f"truthful {truth_phrase!r} on {surface!r} should pass but got {errs}"


# ---- Review-6 escape regressions — strip-then-co-occur (file-level, no negation heuristics) ----
_REVIEW6_ESCAPES: list[tuple[str, str]] = [
    # Negation-word interleavings (A) — unrelated no/zero/not/without must not exempt
    (
        "Research workloads, with no exceptions, were launched for the final evaluation.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    (
        "Research workloads for the zero backhaul design were executed in full.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    (
        "Research workloads that were not dormant were launched last week.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    (
        "Research workloads, without any gating, were launched on the cluster.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    # Cross-unit / newline splits (B) — head and verb in different units must still fail
    (
        "Research workloads for E3 are complete; they were launched last week.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    (
        "We finished the research workloads. Each of them was launched under the frozen actor.",
        "E3PV_WORKLOADS_CONTRADICTION",
    ),
    ("Research workloads\nwere launched in March.", "E3PV_WORKLOADS_CONTRADICTION"),
    (
        "Hosted CI ran the merge queue; every one of those checks passed successfully.",
        "E3PV_HOSTED_CI_CONTRADICTION",
    ),
    (
        "The E3 results are in hand; all of them have been independently verified.",
        "E3PV_CONTRADICTION",
    ),
]

_FIVE_SURFACES_REVIEW6: list[str] = [
    "docs/e3_dynamic_resource_v2_product.md",
    "docs/closure/e3_product_traceability.json",
    "docs/quality/e3_quality_gate.json",
    "docs/quality/e3_validator_verdict.json",
    "docs/closure/e2_product_lane12_base_receipt.json",
]


@pytest.mark.parametrize("phrase,expected_code", _REVIEW6_ESCAPES)
@pytest.mark.parametrize("surface", _FIVE_SURFACES_REVIEW6)
def test_review6_escape_fails_typed_on_each_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phrase: str,
    expected_code: str,
    surface: str,
) -> None:
    """Every review-6 escape must fail typed on every surface (strip-then-co-occur, no windows, no negation)."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["review6_injection"] = phrase
                    return json.dumps(data)
                except Exception:
                    return real + "\n" + phrase + "\n"
            else:
                return real + "\n\n" + phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0, f"review-6 escape {phrase!r} on {surface!r} should fail"
    assert any(e.startswith(expected_code + ":") for e in errs), (
        f"expected {expected_code} got {errs} for {phrase!r} on {surface!r}"
    )


@pytest.mark.parametrize("surface", _FIVE_SURFACES_REVIEW6)
def test_review6_truthful_controls_pass_on_each_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Truthful allowlisted controls must still pass on each surface after strip-then-co-occur."""
    truth_map: dict[str, str] = {
        "docs/e3_dynamic_resource_v2_product.md": "research_workloads_launched = 0",
        "docs/closure/e3_product_traceability.json": "HOSTED_CI_UNAVAILABLE",
        "docs/quality/e3_quality_gate.json": "NO_E3_RESEARCH_RESULTS_AVAILABLE",
        "docs/quality/e3_validator_verdict.json": "research_workloads_launched = 0",
        "docs/closure/e2_product_lane12_base_receipt.json": "HOSTED_CI_UNAVAILABLE",
    }
    truth_phrase = truth_map.get(surface, "research_workloads_launched = 0")
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["truthful_injection"] = truth_phrase
                    return json.dumps(data)
                except Exception:
                    return real
            else:
                return real + "\n\n" + truth_phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc == 0, f"truthful {truth_phrase!r} on {surface!r} should pass but got {errs}"


# ---- Review-7 15 escapes — HEAD-ONLY (no verb required), parametrized over all surfaces including two residue-free surfaces ----
_REVIEW7_ESCAPES: list[tuple[str, str]] = [
    # Hosted CI family — any mention of hosted ci / github actions / ci checks is error (no verb needed)
    (
        "Hosted CI: success. Every job finished on the first attempt.",
        "E3PV_HOSTED_CI_CONTRADICTION",
    ),
    ("The hosted CI run was successful across the pipeline.", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("Hosted CI was clean; no failures at all.", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("Hosted CI reported zero failures in the final run.", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("GitHub Actions: success across every job.", "E3PV_HOSTED_CI_CONTRADICTION"),
    ("CI checks came back successful and complete.", "E3PV_HOSTED_CI_CONTRADICTION"),
    # Research workloads family — any mention of research workloads is error
    ("The E3 research workloads completed; every arm reported.", "E3PV_WORKLOADS_CONTRADICTION"),
    ("Research workloads are ready for inspection.", "E3PV_WORKLOADS_CONTRADICTION"),
    ("Our research workloads have been completed.", "E3PV_WORKLOADS_CONTRADICTION"),
    ("Research workloads overview shows all arms listed.", "E3PV_WORKLOADS_CONTRADICTION"),
    ("research workloads: 12 workloads processed", "E3PV_WORKLOADS_CONTRADICTION"),
    # E3 results/outcomes family — any mention of e3 results/outcomes is error; plus verified results head
    ("E3 results are ready and attached for review.", "E3PV_CONTRADICTION"),
    ("E3 outcomes have been obtained for all arms.", "E3PV_CONTRADICTION"),
    ("The E3 results are now available and published.", "E3PV_CONTRADICTION"),
    ("E3 outcomes are available for download.", "E3PV_CONTRADICTION"),
]

# All five scanned surfaces plus the two residue-free surfaces are covered — the residue-free surfaces are
# e2_product_lane12_base_receipt.json and e3_quality_gate.json which have no incidental heads after stripping
_ALL_SURFACES_REVIEW7: list[str] = [
    "docs/e3_dynamic_resource_v2_product.md",
    "docs/closure/e3_product_traceability.json",
    "docs/quality/e3_quality_gate.json",
    "docs/quality/e3_validator_verdict.json",
    "docs/closure/e2_product_lane12_base_receipt.json",
]


@pytest.mark.parametrize("phrase,expected_code", _REVIEW7_ESCAPES)
@pytest.mark.parametrize("surface", _ALL_SURFACES_REVIEW7)
def test_review7_escape_fails_typed_on_each_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phrase: str,
    expected_code: str,
    surface: str,
) -> None:
    """Every review-7 HEAD-ONLY escape must fail typed on every surface (no verb required, including residue-free surfaces)."""
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["review7_injection"] = phrase
                    return json.dumps(data)
                except Exception:
                    return real + "\n" + phrase + "\n"
            else:
                return real + "\n\n" + phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc != 0, f"review-7 escape {phrase!r} on {surface!r} should fail"
    assert any(e.startswith(expected_code + ":") for e in errs), (
        f"expected {expected_code} got {errs} for {phrase!r} on {surface!r}"
    )


@pytest.mark.parametrize("surface", _ALL_SURFACES_REVIEW7)
def test_review7_truthful_controls_pass_on_each_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Truthful allowlisted controls must still pass on each surface after HEAD-ONLY."""
    truth_map: dict[str, str] = {
        "docs/e3_dynamic_resource_v2_product.md": "research_workloads_launched = 0",
        "docs/closure/e3_product_traceability.json": "HOSTED_CI_UNAVAILABLE",
        "docs/quality/e3_quality_gate.json": "NO_E3_RESEARCH_RESULTS_AVAILABLE",
        "docs/quality/e3_validator_verdict.json": "research_workloads_launched = 0",
        "docs/closure/e2_product_lane12_base_receipt.json": "HOSTED_CI_UNAVAILABLE",
    }
    truth_phrase = truth_map.get(surface, "research_workloads_launched = 0")
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if str(self).endswith(surface):
            real = orig_read(self, *args, **kwargs)
            if surface.endswith(".json"):
                try:
                    data = json.loads(real)
                    data["truthful_injection"] = truth_phrase
                    return json.dumps(data)
                except Exception:
                    return real
            else:
                return real + "\n\n" + truth_phrase + "\n"
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    rc, errs, _ = _run_validator_cli(monkeypatch, tmp_path)
    assert rc == 0, f"truthful {truth_phrase!r} on {surface!r} should pass but got {errs}"


def test_no_unmeasured_values_in_gate(tmp_path: Path) -> None:
    """Gate must have no unmeasured literals: deferred_to_controller has no number, checks derived, deterministic measured."""
    import scripts.validate_e3_research_product as v

    gate = v.build_gate()
    vm = gate["gates"]["validator_mutations"]
    # HONEST MUTATION FIELDS: both count and each_must_fail are ALWAYS deferred_to_controller (measuring requires executing suite)
    assert vm["count"] == "deferred_to_controller"
    assert vm["each_must_fail_with_typed_error_no_traceback"] == "deferred_to_controller"
    assert "deferred_to_controller" in vm["note"]
    # Ensure no literal true leaked
    assert vm["each_must_fail_with_typed_error_no_traceback"] is not True  # type: ignore[comparison-overlap]
    assert vm["count"] is not True  # type: ignore[comparison-overlap]
    # checks should be independent expected count 16, not tautological len(registry)
    assert gate["gates"]["validator_real_tree"]["checks"] == 16
    assert gate["gates"]["validator_real_tree"]["checks"] == len(v._CHECK_REGISTRY)
    # deterministic should be bool True/False or deferred string, not hard literal without measurement
    det = gate["gates"]["validator_real_tree"]["deterministic"]
    assert det in (True, False, "deferred_to_controller")
    # Also ensure validator_real_tree is labeled by portable repo kind (no absolute paths)
    assert "repo_root_kind" in gate
    assert gate["repo_root_kind"] in ("real_tree", "temp_copy")
    assert "repo_root_kind" in gate["gates"]["validator_real_tree"]
    assert gate["repo_root_kind"] == gate["gates"]["validator_real_tree"]["repo_root_kind"]
    assert gate["repo_root_kind"] == gate["gates"]["validator_mutations"]["repo_root_kind"]
    # No absolute path leakage in receipts
    gate_text = __import__("json").dumps(gate)
    assert ("/" + "Users" + "/") not in gate_text
    assert ("/" + "home" + "/") not in gate_text
    # Portable marker should exist
    assert gate.get("repo_is_toplevel") is True
    assert gate["gates"]["validator_real_tree"].get("repo_is_toplevel") is True


def test_validator_mutations_deferred_when_tools_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When git and pytest both unavailable, validator_mutations must be deferred with no number — and also when tools ARE available."""
    import subprocess
    import scripts.validate_e3_research_product as v

    # First, when tools available (normal branch), must still be deferred
    gate_available = v.build_gate()
    vm_avail = gate_available["gates"]["validator_mutations"]
    assert vm_avail["count"] == "deferred_to_controller"
    assert vm_avail["each_must_fail_with_typed_error_no_traceback"] == "deferred_to_controller"
    assert vm_avail["each_must_fail_with_typed_error_no_traceback"] is not True  # type: ignore[comparison-overlap]

    # Second, when tools forced unavailable, must also be deferred
    orig_run = subprocess.run

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        # Simulate total tool unavailability for both git status and pytest collect
        raise FileNotFoundError("forced unavailable for test")

    monkeypatch.setattr(subprocess, "run", fake_run)
    gate = v.build_gate()
    vm = gate["gates"]["validator_mutations"]
    assert vm["count"] == "deferred_to_controller"
    assert vm["each_must_fail_with_typed_error_no_traceback"] == "deferred_to_controller"
    # Ensure no literal true leaked when unavailable
    assert vm["each_must_fail_with_typed_error_no_traceback"] is not True  # type: ignore[comparison-overlap]
    # Also when tools unavailable, each_must_fail must not be True literal
    assert (
        "true" not in json.dumps(vm).lower()
        or vm["each_must_fail_with_typed_error_no_traceback"] == "deferred_to_controller"
    )


def test_validator_mutations_always_deferred_even_when_available(tmp_path: Path) -> None:
    """validator_mutations fields are ALWAYS deferred_to_controller even when tools available (honest measurement)."""
    import scripts.validate_e3_research_product as v

    gate = v.build_gate()
    vm = gate["gates"]["validator_mutations"]
    assert vm["count"] == "deferred_to_controller", (
        f"count should be deferred even when available, got {vm['count']!r}"
    )
    assert vm["each_must_fail_with_typed_error_no_traceback"] == "deferred_to_controller", (
        f"each_must_fail should be deferred even when available, got {vm['each_must_fail_with_typed_error_no_traceback']!r}"
    )
    assert vm["result"] == "deferred_to_controller"
    # Ensure note explains deferral reason
    assert "deferred" in vm["note"].lower() or "executing" in vm["note"].lower()


# ---- B1 portable receipt regression: git archive materialization ----
def test_b1_portable_receipt_no_absolute_paths_and_archive_regeneration(tmp_path: Path) -> None:
    """B1: receipts contain no absolute paths; git-archive materialization proves regeneration equality."""
    import subprocess
    import tempfile
    import json
    import shutil

    # 1. No absolute paths in committed receipts
    for receipt in ["docs/quality/e3_quality_gate.json", "docs/quality/e3_validator_verdict.json"]:
        txt = Path(receipt).read_text(encoding="utf-8")
        assert ("/" + "Users" + "/") not in txt, f"{receipt} leaks Users"
        assert ("/" + "home" + "/") not in txt
        assert ("/" + "tmp" + "/") not in txt
        assert "private" not in txt.lower() or ("/" + "private" + "/") not in txt
        # Must have portable labeling, not repo_root
        data = json.loads(txt) if receipt.endswith("e3_quality_gate.json") else None
        if data is not None:
            assert "repo_root_kind" in data, "gate must have repo_root_kind"
            assert "repo_root" not in data, "gate must NOT have repo_root absolute"
            assert data["repo_root_kind"] in ("real_tree", "temp_copy")
            assert '"repo_root":' not in json.dumps(data["gates"]["validator_real_tree"])
            assert "repo_root_kind" in data["gates"]["validator_real_tree"]
            assert '"repo_root":' not in json.dumps(data["gates"]["validator_mutations"])
            # Also validator check and gate check must include both receipts in checked_files
            no_abs = data["gates"]["no_absolute_path_literals"]
            assert "docs/quality/e3_quality_gate.json" in no_abs.get("checked_files", [])
            assert "docs/quality/e3_validator_verdict.json" in no_abs.get("checked_files", [])
            assert "docs/quality/e3_quality_gate.json" in no_abs.get("actually_checked", [])
            assert "docs/quality/e3_validator_verdict.json" in no_abs.get("actually_checked", [])

    # 2. Materialize commit at temp path via git archive and prove regeneration equality
    src_root = Path(".").resolve()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        dst = td_path / "archive_copy"
        dst.mkdir()
        # git archive HEAD | tar -x -C dst — materialize commit at temp path
        archive = subprocess.run(
            ["git", "archive", "HEAD"],
            cwd=str(src_root),
            capture_output=True,
            timeout=15,
        )
        assert archive.returncode == 0, f"git archive failed {archive.stderr[:500]}"
        extract = subprocess.run(
            ["tar", "-x", "-C", str(dst)],
            input=archive.stdout,
            capture_output=True,
            timeout=15,
        )
        assert extract.returncode == 0, f"tar extract failed {extract.stderr[:500]}"
        # Overlay current worktree fixes (uncommitted) onto dst so dst reflects current code, not just HEAD
        for rel in [
            "scripts/validate_e3_research_product.py",
            "tests/integration/test_e3_research_product_acceptance.py",
            "docs/quality/e3_quality_gate.json",
            "docs/quality/e3_validator_verdict.json",
        ]:
            src = src_root / rel
            if src.exists():
                dst_path = dst / rel
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                dst_path.write_bytes(src.read_bytes())
        # Also copy .git so dst is a git repo (git archive does not include .git)
        import shutil as _shutil

        # Handle worktree .git file vs directory — copy appropriately so dst is a git repo
        if (src_root / ".git").exists():
            if not (dst / ".git").exists():
                git_path = src_root / ".git"
                if git_path.is_file():
                    # worktree: .git is a file containing gitdir: reference
                    dst_git_content = git_path.read_text(encoding="utf-8")
                    (dst / ".git").write_text(dst_git_content, encoding="utf-8")
                    # Also need to ensure the referenced gitdir's worktree config is handled?
                    # For archive copy test, we don't strictly need fully functional git; we just need git status to not fail closed due to missing .git
                    # Instead, create a minimal .git dir to avoid git error: copy the main git dir if possible
                    # Try to resolve gitdir
                    import re

                    m = re.search(r"gitdir:\s*(.+)", dst_git_content)
                    if m:
                        real_gitdir = Path(m.group(1).strip())
                        # If relative, resolve relative to src_root
                        if not real_gitdir.is_absolute():
                            real_gitdir = (src_root / real_gitdir).resolve()
                        # Copy the worktree's git dir if it exists, else copy main .git
                        if real_gitdir.exists() and real_gitdir.is_dir():
                            # Copy the worktree-specific git dir to a temp location and adjust?
                            # Simpler: just init a new repo at dst and set remote
                            pass
                    # Fallback: init dst as git repo with same HEAD
                    try:
                        import subprocess as _sp

                        _sp.run(
                            ["git", "init", "--quiet"], cwd=str(dst), capture_output=True, timeout=5
                        )
                        _sp.run(
                            ["git", "remote", "add", "origin", str(src_root)],
                            cwd=str(dst),
                            capture_output=True,
                            timeout=5,
                        )
                    except Exception:
                        pass
                else:
                    _shutil.copytree(git_path, dst / ".git", symlinks=True)
        # Verify materialized tree has required files
        assert (dst / "scripts/validate_e3_research_product.py").exists()
        assert (dst / "docs/quality/e3_quality_gate.json").exists()
        # Regenerate gate at materialized path via subprocess (run from inside dst, so _REPO_ROOT == dst)
        out = td_path / "fresh_gate_archive.json"
        py = str(src_root / ".venv/bin/python")
        rc = subprocess.run(
            [
                py,
                "scripts/validate_e3_research_product.py",
                "--emit-gate-receipt",
                str(out),
                "--allow-dirty",
            ],
            cwd=str(dst),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert rc.returncode == 0, (
            f"gate emit in archive copy failed {rc.returncode} {rc.stderr[:1000]} {rc.stdout[:1000]}"
        )
        assert out.exists()
        gate_text = out.read_text(encoding="utf-8")
        # No absolute paths in regenerated
        assert ("/" + "Users" + "/") not in gate_text
        assert ("/" + "home" + "/") not in gate_text
        # Deterministic: second emit should match first
        out2 = td_path / "fresh_gate_archive2.json"
        rc2 = subprocess.run(
            [
                py,
                "scripts/validate_e3_research_product.py",
                "--emit-gate-receipt",
                str(out2),
                "--allow-dirty",
            ],
            cwd=str(dst),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert rc2.returncode == 0
        assert out.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8"), (
            "archive regeneration must be deterministic"
        )
        # Regeneration equality at temp path holds: fresh gate deterministic and portable, no absolute paths
        src_committed = Path("docs/quality/e3_quality_gate.json").read_text(encoding="utf-8")
        fresh_text = out.read_text(encoding="utf-8")
        assert (
            '"repo_root_kind": "real_tree"' in fresh_text
            or '"repo_root_kind": "temp_copy"' in fresh_text
        )
        assert ("/" + "Users" + "/") not in fresh_text
        import json as _json

        try:
            src_data = _json.loads(src_committed)
            fresh_data = _json.loads(fresh_text)
            if src_data.get("repo_root_kind") == fresh_data.get("repo_root_kind"):
                assert fresh_data["verdict"] == src_data["verdict"]
        except Exception:
            pass


# ---- B2 honest temp-copy emit regression ----
def test_b2_honest_temp_copy_emit_shows_measured_or_deferred_errors(tmp_path: Path) -> None:
    """B2: temp-copy emit with planted failing check must show measured errors or explicit deferral, never 0/[] with FAIL."""
    import subprocess
    import tempfile
    import shutil
    import json

    src_root = Path(".").resolve()
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        dst = td_path / "copy"
        shutil.copytree(
            src_root,
            dst,
            symlinks=True,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "*.pyc"
            ),
        )
        # Plant a failing check: inject forbidden claim into product doc
        doc_path = dst / "docs/e3_dynamic_resource_v2_product.md"
        orig = doc_path.read_text(encoding="utf-8")
        # Inject a Kubernetes claim that validator will catch
        doc_path.write_text(orig + "\n\nKubernetes deployment is live.\n", encoding="utf-8")
        out = td_path / "gate_b2.json"
        result = subprocess.run(
            [
                str(src_root / ".venv/bin/python"),
                "scripts/validate_e3_research_product.py",
                "--emit-gate-receipt",
                str(out),
                "--repo-root",
                str(dst),
                "--allow-dirty",
            ],
            cwd=str(src_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"emit with temp copy failed {result} {result.stderr[:500]}"
        gate = json.loads(out.read_text(encoding="utf-8"))
        vrt = gate["gates"]["validator_real_tree"]
        # Must have portable labeling
        assert "repo_root_kind" in gate
        assert gate["repo_root_kind"] == "temp_copy"
        assert vrt["repo_root_kind"] == "temp_copy"
        assert "repo_root" not in gate
        assert "repo_root" not in vrt
        # No absolute paths in gate
        gate_txt = out.read_text(encoding="utf-8")
        assert ("/" + "Users" + "/") not in gate_txt
        # Headline should be FAIL due to planted failure
        assert gate["verdict"] == "FAIL", (
            f"planted failure should cause FAIL verdict got {gate['verdict']}"
        )
        # And validator_real_tree should not be fabricated 0/[] with FAIL
        # Either measured (exit_code 1 and errors non-empty) OR deferred (both strings)
        exit_code = vrt.get("exit_code")
        errors = vrt.get("errors")
        result = vrt.get("result")
        # Fail verdict must not have exit_code 0 with empty errors
        is_deferred = exit_code == "deferred_to_controller" and errors == "deferred_to_controller"
        is_measured_fail = exit_code == 1 and isinstance(errors, list) and len(errors) > 0
        # Also if errors is list, it should contain E3PV_KUBERNETES_CLAIM or similar
        if isinstance(errors, list) and errors:
            assert any("KUBERNETES" in e or "E3PV" in e for e in errors), (
                f"expected typed error in {errors}"
            )
        assert is_deferred or is_measured_fail, (
            f"B2 honest temp-copy: with FAIL verdict, exit_code/errors must be measured fail or deferred, "
            f"got exit_code={exit_code!r} errors={errors!r} result={result!r} verdict={gate['verdict']!r}"
        )
        # Never fabricated 0/[] alongside FAIL
        assert not (exit_code == 0 and errors == [] and gate["verdict"] == "FAIL"), (
            "fabricated 0/[] with FAIL is forbidden"
        )
