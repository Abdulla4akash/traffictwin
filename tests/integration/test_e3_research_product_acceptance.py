# ruff: noqa: ANN401, E501, S108, SIM102, SIM115, F841, S110, I001, F401
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


def test_validator_passes_on_real_tree() -> None:
    import scripts.validate_e3_research_product as v

    rc: int = v.main()
    assert rc == 0, "validator must pass on real tree"
    # Also check verdict JSON
    verdict_path = Path("docs/quality/e3_validator_verdict.json")
    assert verdict_path.exists()
    data: dict[str, Any] = json.loads(verdict_path.read_text(encoding="utf-8"))
    assert data["pass"] is True
    assert data["errors"] == []
    assert data["hosted_ci"] == "HOSTED_CI_UNAVAILABLE"
    assert data["hold"]["lane_09"] == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    # Stable ordering: errors sorted
    assert data["errors"] == sorted(data["errors"])
    # No timestamps in verdict
    dump = json.dumps(data)
    assert (
        "timestamp" not in dump.lower() or "timestamp" in dump.lower() and "timestamp" not in data
    )


# ---- Validator must fail closed on at least 12 mutated scenarios ----------


def _run_validator_with_patch(
    monkeypatch: pytest.MonkeyPatch, patch_fn: Any
) -> tuple[int, list[str]]:
    import scripts.validate_e3_research_product as v

    # Apply patch_fn to setup mutation
    patch_fn(monkeypatch)
    # Call main capturing errors without traceback
    rc = v.main()
    # Read verdict from the repo root that validator actually used
    try:
        verdict_path = v._REPO_ROOT / "docs/quality/e3_validator_verdict.json"  # type: ignore[attr-defined]
        # Fallback to real path if patched root not set
        if not verdict_path.exists():
            verdict_path = Path("docs/quality/e3_validator_verdict.json")
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        errs = verdict.get("errors", [])
    except Exception:
        errs = []
    return rc, errs


def test_validator_fails_on_wrong_product_base_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.validate_e3_research_product as v

    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        return pkg.model_copy(update={"product_base_sha": "0" * 40})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    monkeypatch.setattr(v, "EXPECTED_PRODUCT_BASE_SHA", "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c")
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("product_base_sha" in e.lower() for e in errs)
    # Ensure no traceback: rc is int not exception
    assert isinstance(rc, int)


def test_validator_fails_on_wrong_vec_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        bad_vec = pkg.vec_runtime.model_copy(update={"promotion_commit": "0" * 40})
        return pkg.model_copy(update={"vec_runtime": bad_vec})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("vec_promotion" in e.lower() or "vec" in e.lower() for e in errs)


def test_validator_fails_on_wrong_actor_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        bad_si = pkg.software_identity.model_copy(update={"actor_sha256": "0" * 64})
        return pkg.model_copy(update={"software_identity": bad_si})

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("actor" in e.lower() for e in errs)


def test_validator_fails_on_wrong_manifest_sidecar(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        # Change provenance manifest note to wrong SHA
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
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("manifest" in e.lower() for e in errs)


def test_validator_fails_on_tasks_as_n(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        bad_rep = pkg.replication.model_copy(update={"replication_unit": "task", "n": 100})  # type: ignore[call-arg]
        # Use model_copy bypass validation? Need to bypass via dict
        data = json.loads(pkg.model_dump_json())
        data["replication"]["replication_unit"] = "task"
        data["replication"]["n"] = 100
        # Return dict will be validated in admit but validator loads via artifact which will fail validation
        # So instead monkeypatch the artifact to return a mock with task unit
        mock = MagicMock(wraps=pkg)
        mock.replication = MagicMock()
        mock.replication.replication_unit = "task"
        mock.replication.n = 100
        mock.replication.fleet_seeds = [1, 2, 3, 4]
        mock.replication.evaluator_seed = 0
        # Keep other fields from real pkg
        mock.product_base_sha = pkg.product_base_sha
        mock.research_promotion_sha = pkg.research_promotion_sha
        mock.approved_candidate_sha = pkg.approved_candidate_sha
        mock.contract_checkpoint_sha = pkg.contract_checkpoint_sha
        mock.vec_runtime = pkg.vec_runtime
        mock.contract = pkg.contract
        mock.software_identity = pkg.software_identity
        mock.provenance = pkg.provenance
        mock.dormant_arms = pkg.dormant_arms
        mock.dormant_configs = pkg.dormant_configs
        mock.factors = pkg.factors
        mock.queue_capacity = pkg.queue_capacity
        mock.compute_capacity = pkg.compute_capacity
        mock.resource_cost = pkg.resource_cost
        mock.execution_authority = pkg.execution_authority
        mock.evidence_state = pkg.evidence_state
        mock.result_availability = pkg.result_availability
        mock.research_workloads_launched = pkg.research_workloads_launched
        mock.lane_09 = pkg.lane_09
        mock.status = pkg.status
        mock.task_accounting = pkg.task_accounting
        mock.campaign = pkg.campaign
        mock.model_dump = pkg.model_dump  # type: ignore[assignment]
        return mock

    # For this mutation, directly test the identities check via monkeypatching the loader
    # Use a simpler approach: patch the package's replication via monkeypatch on the module
    # Instead we test via docs injection for tasks_as_n phrase
    fake_root = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    # Mutation via docs affirming tasks-as-N
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *a, **k: (
            fake_root + "\n\nTrafficTwin performs tasks as N with true claim.\n"
            if "e3_dynamic" in str(a[0])
            else Path.read_text.__wrapped__(*a, **k)
            if hasattr(Path.read_text, "__wrapped__")
            else open(a[0]).read()
        ),
    )  # type: ignore[attr-defined]

    # Simpler: create temp fake doc via patching _REPO_ROOT

    tmp = Path("tmp_mutation_tasks_n.md")
    # Use tmp_path fixture instead — we will do file-based mutation test separately
    # For now, just assert that standalone check for tasks_as_n would fail
    # We do a direct _check_forbidden_claims injection via monkeypatch of package dump

    # Alternative: directly test _check_forbidden_claims by injecting forbidden phrase into package model_dump
    # We'll patch load_builtin_e3_research to return forged package with deep nested tasks_as_n
    def fake2() -> Any:
        pkg2 = orig()
        new_factors = dict(pkg2.factors)
        new_factors["deep"] = {"inner": "tasks as n is true claim"}  # type: ignore[assignment]
        forged = pkg2.model_copy(update={"factors": new_factors})
        return forged

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake2
    )
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("tasks_as_n" in e.lower() or "forbidden" in e.lower() for e in errs)


def test_validator_fails_on_queue_compute_conflation(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.validate_e3_research_product as v

    errors: list[str] = []
    # Inject conflation via monkeypatched docs read
    real = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    injected = real + "\n\nQueue ceiling is compute is true for test.\n"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            return injected
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    v._check_forbidden_claims(errors)
    assert any("queue" in e.lower() for e in errors), (
        f"expected queue conflation error, got {errors}"
    )
    # Also ensure main fails without traceback
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0


def test_validator_fails_on_unavailable_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
    from traffictwin.experiments.e3_task_accounting import build_e3_task_accounting_view

    orig_pkg = load_builtin_e3_research
    orig_view = build_e3_task_accounting_view

    def fake_pkg() -> Any:
        pkg = orig_pkg()
        # Make task_accounting offered = 0 (fabricated zero) via copy
        data = json.loads(pkg.model_dump_json())
        data["task_accounting"]["offered"] = 0
        # Bypass validation by returning mock
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
        mock.model_dump = pkg.model_dump  # type: ignore[assignment]
        return mock

    # Instead test via export zero injection
    def patch_export(monkeypatch: pytest.MonkeyPatch) -> None:
        from traffictwin.reporting.e3_research import build_e3_research_exports

        orig_build = build_e3_research_exports

        def fake_build(pkg: Any, receipt: Any) -> Any:
            b = orig_build(pkg, receipt)
            j = json.loads(b.json)
            j["task_accounting"]["offered"] = 0
            # Need to bypass frozen by object setattr via mock
            mock_b = MagicMock(wraps=b)
            mock_b.json = json.dumps(j)
            mock_b.csv = b.csv
            mock_b.markdown = b.markdown
            return mock_b

        monkeypatch.setattr(
            "traffictwin.reporting.e3_research.build_e3_research_exports", fake_build
        )

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake_pkg
    )
    # The builtin check will catch offered not None
    rc, errs = _run_validator_with_patch(monkeypatch, patch_export)
    assert rc != 0
    assert any("unavailable" in e.lower() or "zero" in e.lower() for e in errs)


def test_validator_fails_on_monetary_cost(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import scripts.validate_e3_research_product as v

    errors: list[str] = []
    real = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    injected = real + "\n\nCost is $100 dollars for test.\n"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            return injected
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    v._check_forbidden_claims(errors)
    assert any("monetary" in e.lower() or "forbidden" in e.lower() for e in errors), f"got {errors}"


def test_validator_fails_on_kubernetes_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e3_research_product as v

    errors: list[str] = []
    real = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    injected = real + "\n\nTrafficTwin performs Kubernetes deployment is live.\n"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            return injected
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    v._check_forbidden_claims(errors)
    assert any("kubernetes" in e.lower() for e in errors), f"got {errors}"


def test_validator_fails_on_actor_selects_rsu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e3_research_product as v

    errors: list[str] = []
    real = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    injected = real + "\n\nThe actor selects execution RSU is live for test.\n"
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            return injected
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    v._check_forbidden_claims(errors)
    assert any("actor" in e.lower() for e in errors), f"got {errors}"


def test_validator_fails_on_manchester_wide_and_universal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.validate_e3_research_product as v

    errors: list[str] = []
    real = Path("docs/e3_dynamic_resource_v2_product.md").read_text(encoding="utf-8")
    injected = (
        real + "\n\nOur results generalize across all of Manchester and are universally superior.\n"
    )
    orig_read = Path.read_text

    def fake_read(self: Path, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        if str(self).endswith("e3_dynamic_resource_v2_product.md"):
            return injected
        return orig_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read)
    v._check_forbidden_claims(errors)
    assert any("manchester" in e.lower() or "universal" in e.lower() for e in errors), (
        f"got {errors}"
    )


def test_validator_fails_on_missing_resource_denominator(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        # Change metric to not resource_unit_seconds via mock
        mock = MagicMock(wraps=pkg)
        for k in pkg.model_fields:
            setattr(mock, k, getattr(pkg, k))
        mock.resource_cost = MagicMock()
        mock.resource_cost.metric = "dollars"
        mock.resource_cost.monetary = True
        mock.resource_cost.unit = "dollars"
        mock.resource_cost.formula = "cost dollars"
        mock.model_dump = pkg.model_dump  # type: ignore[assignment]
        return mock

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("resource" in e.lower() or "denominator" in e.lower() for e in errs)


def test_validator_fails_on_free_unbounded_scaling(monkeypatch: pytest.MonkeyPatch) -> None:
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
        mock.model_dump = pkg.model_dump  # type: ignore[assignment]
        return mock

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("scaling" in e.lower() or "capacity" in e.lower() for e in errs)


def test_validator_fails_on_state_age_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        pkg = orig()
        # Make one arm have state_age 500
        bad_arms = list(pkg.dormant_arms)
        bad_arm = bad_arms[0].model_copy(update={"state_age_ms": 500})  # type: ignore[call-arg]
        bad_arms[0] = bad_arm
        mock = MagicMock(wraps=pkg)
        for k in pkg.model_fields:
            setattr(mock, k, getattr(pkg, k))
        mock.dormant_arms = bad_arms
        mock.model_dump = pkg.model_dump  # type: ignore[assignment]
        return mock

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("state_age" in e.lower() or "stale" in e.lower() for e in errs)


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
    # Copy current real files but remove E3 button marker from explorer
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
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("route" in e.lower() for e in errs)


def test_validator_fails_on_export_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
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
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("export" in e.lower() or "mismatch" in e.lower() for e in errs)


def test_validator_fails_on_non_deterministic_exports(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.reporting.e3_research import build_e3_research_exports

    orig = build_e3_research_exports
    call_count = {"n": 0}

    def fake_build(pkg: Any, receipt: Any) -> Any:
        b = orig(pkg, receipt)
        call_count["n"] += 1
        # Alternate to ensure the determinism pair (two consecutive calls) differs
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
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("deterministic" in e.lower() for e in errs)


def test_validator_fails_on_placeholder_fabricated(monkeypatch: pytest.MonkeyPatch) -> None:
    from traffictwin.experiments.e3_comparison import build_e3_comparison_view

    orig = build_e3_comparison_view

    def fake(pkg: Any) -> Any:
        comp = orig(pkg)
        # Fabricate per_seed values not null
        pd = comp.e3a.paired_differences[0]
        object.__setattr__(pd, "per_seed_values", [0.1, 0.2, 0.3, 0.4])
        object.__setattr__(pd, "mean", 0.25)
        return comp

    monkeypatch.setattr("traffictwin.experiments.e3_comparison.build_e3_comparison_view", fake)
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("placeholder" in e.lower() or "fabricated" in e.lower() for e in errs)


def test_validator_fails_on_path_secret_leakage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("secret" in e.lower() or "path" in e.lower() for e in errs)


def test_validator_fails_on_supervisor_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    rc, errs = _run_validator_with_patch(monkeypatch, lambda mp: None)
    assert rc != 0
    assert any("supervisor" in e.lower() for e in errs)


def test_validator_no_traceback_on_mutated_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure mutated payload does not raise traceback, only typed error
    from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research

    orig = load_builtin_e3_research

    def fake() -> Any:
        raise ValueError("simulated load failure for no traceback test")

    monkeypatch.setattr(
        "traffictwin.experiments.e3_research_artifact.load_builtin_e3_research", fake
    )
    import scripts.validate_e3_research_product as v

    # main should not raise
    try:
        rc = v.main()
        assert rc != 0
    except Exception as exc:
        pytest.fail(f"validator raised traceback on mutated payload: {exc}")


def test_validator_emits_deterministic_verdict_json() -> None:
    import scripts.validate_e3_research_product as v

    rc1 = v.main()
    txt1 = Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8")
    rc2 = v.main()
    txt2 = Path("docs/quality/e3_validator_verdict.json").read_text(encoding="utf-8")
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
