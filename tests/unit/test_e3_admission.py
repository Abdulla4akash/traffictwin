# ruff: noqa: E501, ANN401
"""Focused tests for fail-closed E3 admission — typed truthful refusal."""

from __future__ import annotations

import json

from traffictwin.evidence_admission.e3_research import (
    LANE_09_HOLD,
    STANDING_REFUSED,
    E3ResearchAdmissionRefusal,
    admit_e3_research,
    validate_e3_package_for_admission,
)
from traffictwin.experiments.e3_research_artifact import (
    builtin_e3_research_json,
    load_builtin_e3_research,
)
from traffictwin.experiments.e3_research_evidence import (
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
    NOT_EXECUTED,
)


def _valid_pkg() -> object:
    return load_builtin_e3_research()


def test_admit_valid_package_returns_typed_refusal_not_exception() -> None:
    pkg = _valid_pkg()
    result = admit_e3_research(pkg)
    # Must be refusal, not exception
    assert isinstance(result, E3ResearchAdmissionRefusal)
    assert result.admitted is False
    assert result.status == "REFUSED"
    assert result.lane_09 == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    assert result.lane_09 == LANE_09_HOLD
    assert result.evidence_state == "NOT_EXECUTED"
    assert result.evidence_state == NOT_EXECUTED
    assert result.result_availability == "NO_E3_RESEARCH_RESULTS_AVAILABLE"
    assert result.result_availability == NO_E3_RESEARCH_RESULTS_AVAILABLE
    assert result.research_workloads_launched == 0
    assert result.standing == "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"
    assert result.standing == STANDING_REFUSED
    assert result.reason_code == "REFUSED_MISSING_FUTURE_ARTIFACT"
    assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" in result.reason_detail
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in result.reason_detail
    # Diagnostics explain
    assert isinstance(result.diagnostics, dict)
    # No partial admission
    assert result.admitted is False
    # Model is frozen
    assert result.model_config.get("frozen") is True


def test_admit_returns_refusal_for_every_current_input_even_with_fingerprints() -> None:
    pkg = _valid_pkg()
    # Even if we provide some fingerprints, still refusal because expected is None
    result = admit_e3_research(
        pkg, package_fingerprint="a" * 64, analysis_artifact_fingerprint="b" * 64
    )
    assert isinstance(result, E3ResearchAdmissionRefusal)
    assert result.admitted is False
    assert result.status == "REFUSED"
    # Reason should be future artifact mismatch
    assert "FUTURE_ARTIFACT" in result.reason_code or "REFUSED" in result.reason_code


def test_admit_identity_mismatch_is_refused_not_exception() -> None:
    pkg = _valid_pkg()
    bad = pkg.model_copy(update={"product_base_sha": "0" * 40})
    result = admit_e3_research(bad)
    assert isinstance(result, E3ResearchAdmissionRefusal)
    assert result.reason_code == "REFUSED_IDENTITY_MISMATCH"
    assert "product_base_sha" in result.reason_detail.lower()


def test_admit_vec_identity_mismatch_refused() -> None:
    pkg = _valid_pkg()
    bad_vec = pkg.vec_runtime.model_copy(update={"core_candidate": "0" * 40})
    bad = pkg.model_copy(update={"vec_runtime": bad_vec})
    result = admit_e3_research(bad)
    assert result.reason_code == "REFUSED_IDENTITY_MISMATCH"
    assert "vec_core" in result.reason_detail.lower()


def test_admit_wrong_fingerprint_type_refused() -> None:
    pkg = _valid_pkg()
    result = admit_e3_research(pkg, package_fingerprint="nothex")
    assert result.reason_code == "REFUSED_WRONG_FINGERPRINT_TYPE"
    assert "64 hex" in result.reason_detail.lower()

    result2 = admit_e3_research(pkg, analysis_artifact_fingerprint="123")
    assert result2.reason_code == "REFUSED_WRONG_FINGERPRINT_TYPE"


def test_admit_missing_package_refused() -> None:
    result = admit_e3_research(None)
    assert isinstance(result, E3ResearchAdmissionRefusal)
    assert result.reason_code == "REFUSED_MISSING_PACKAGE"
    assert result.admitted is False
    # Even dict missing
    result2 = admit_e3_research({})
    assert result2.admitted is False


def test_admit_forbidden_queue_compute_conflation_refused() -> None:
    data = json.loads(builtin_e3_research_json())
    # Inject affirming conflation
    data["limitations"][0] = data["limitations"][0] + " queue ceiling is compute is true claim"
    result = admit_e3_research(data)
    # Could be package invalid or forbidden claim
    assert result.admitted is False
    assert "REFUSED" in result.reason_code
    assert "forbidden" in result.reason_detail.lower() or "queue" in result.reason_detail.lower()


def test_admit_forbidden_monetary_cost_refused() -> None:
    data = json.loads(builtin_e3_research_json())
    data["resource_cost"]["formula"] = "cost_dollars = 100 and resource_unit_seconds fake"
    # Ensure formula still passes shape but contains forbidden monetary phrase affirming
    result = admit_e3_research(data)
    assert result.admitted is False
    assert "REFUSED" in result.reason_code


def test_admit_forbidden_actor_selects_refused() -> None:
    data = json.loads(builtin_e3_research_json())
    data["non_claims"] = ["actor selects execution rsu is true"]
    result = admit_e3_research(data)
    assert result.admitted is False
    assert "REFUSED" in result.reason_code


def test_admit_forbidden_kubernetes_refused() -> None:
    data = json.loads(builtin_e3_research_json())
    data["provenance"][0]["note"] = "kubernetes deployment is true for test"
    result = admit_e3_research(data)
    assert result.admitted is False
    assert "REFUSED" in result.reason_code


def test_admit_tasks_as_n_refused() -> None:
    data = json.loads(builtin_e3_research_json())
    data["replication"]["replication_unit"] = "task"
    data["replication"]["n"] = 1000
    result = admit_e3_research(data)
    assert result.admitted is False
    assert "REFUSED" in result.reason_code


def test_admit_true_authorized_refused() -> None:
    data = json.loads(builtin_e3_research_json())
    data["execution_authority"]["e3a_authorized"] = True
    result = admit_e3_research(data)
    assert result.admitted is False
    assert "REFUSED" in result.reason_code
    # Must mention _authorized
    assert (
        "_authorized" in result.reason_detail.lower()
        or "authorized" in result.reason_detail.lower()
    )


def test_admit_no_exception_on_completely_invalid_dict() -> None:
    # Completely malformed should still be refusal not exception
    result = admit_e3_research({"not": "a package"})
    assert isinstance(result, E3ResearchAdmissionRefusal)
    assert result.admitted is False


def test_admit_never_raises_for_current_inputs() -> None:
    pkg = _valid_pkg()
    cases = [
        pkg,
        None,
        {},
        {"bad": 123},
        json.loads(builtin_e3_research_json()),
    ]
    for case in cases:
        result = admit_e3_research(case)  # type: ignore[arg-type]
        assert isinstance(result, E3ResearchAdmissionRefusal)
        assert result.admitted is False
        assert result.lane_09 == LANE_09_HOLD


def test_admit_refusal_contains_exact_frozen_identities() -> None:
    pkg = _valid_pkg()
    result = admit_e3_research(pkg)
    assert result.product_base_sha == "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c"
    assert result.research_promotion_sha == "342789434233e97cd87ea74e21a759878610ce40"
    assert result.approved_candidate_sha == "c5d66ef7e77f3b7d1f3fde084feea45a83f5c178"
    assert result.contract_checkpoint_sha == "211a6662151ccad43187f8a2ce3f75a57515408d"
    assert result.vec_promotion_sha == "dc606770059f0c4a413bac2217d7f38600b74fff"
    assert result.vec_core_sha == "53e34db6146da40118a6c816f6a1ffaa2596ddf3"
    assert result.vec_adapter_sha == "c37f97ea66b236dfc662bfdd6bee7eab1a775bbc"
    assert result.actor_sha256 == "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
    assert result.trace_sha256 == "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"


def test_validate_helper_returns_list_and_is_pure() -> None:
    pkg = _valid_pkg()
    errs = validate_e3_package_for_admission(pkg)
    # Valid pkg should have no pre-errors (except admission will still refuse due to missing future artifact)
    # But validate_e3_package_for_admission should return empty for valid pkg
    assert errs == []
    # Bad package should return non-empty
    bad = pkg.model_copy(update={"product_base_sha": "0" * 40})
    errs2 = validate_e3_package_for_admission(bad)
    assert len(errs2) > 0
    assert "identity_mismatch" in errs2[0].lower()


def test_no_supervisor_approval_in_refusal() -> None:
    pkg = _valid_pkg()
    result = admit_e3_research(pkg)
    dumped = json.dumps(result.model_dump(mode="json")).lower()
    assert "supervisor approved" not in dumped
    assert "randy confirmed" not in dumped


def test_refusal_is_deterministic() -> None:
    pkg = _valid_pkg()
    r1 = admit_e3_research(pkg)
    r2 = admit_e3_research(pkg)
    assert r1.model_dump(mode="json") == r2.model_dump(mode="json")


# --- Blocker 2 deep-nested via admission ---
def test_admission_bypass_strings_rejected() -> None:
    for payload in [
        "there is no doubt kubernetes cluster is live",
        "never in doubt: supervisor approved this",
    ]:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = payload
        # validate via admission helper should return forbidden errors
        errs = validate_e3_package_for_admission(data)
        # Should be non-empty and contain forbidden
        assert len(errs) > 0
        assert any("forbidden" in e.lower() for e in errs)
        # admit should also refuse
        result = admit_e3_research(data)
        assert result.admitted is False
        assert "REFUSED" in result.reason_code


def test_admission_forbidden_families_deep_nested() -> None:
    families = [
        ("kubernetes deep via admission is true", "kubernetes"),
        ("supervisor approved deep via admission is true", "supervisor approved"),
        ("universal_superiority deep via admission is true", "universal_superiority"),
        ("tasks_as_n deep via admission is true", "tasks_as_n"),
        ("manchester_wide deep via admission is true", "manchester_wide"),
        ("monetary_cost deep via admission is true", "monetary_cost"),
        ("actor_selects_rsu deep via admission is true", "actor_selects"),
        ("cost_dollars deep via admission is true", "cost_dollars"),
        ("randy confirmed deep via admission is true", "randy confirmed"),
        ("queue ceiling is compute deep via admission is true", "queue ceiling is"),
    ]
    for phrase, needle in families:
        pkg = load_builtin_e3_research()
        # Forge package with deep nested forbidden via model_copy (bypasses validation)
        new_factors = dict(pkg.factors)
        new_factors["deep_admission"] = {"inner": {"deepest": phrase}}  # type: ignore[assignment]
        forged = pkg.model_copy(update={"factors": new_factors})
        errs = validate_e3_package_for_admission(forged)
        assert len(errs) > 0
        assert any(needle in e.lower() for e in errs), f"expected {needle!r} in {errs!r}"


def test_admission_allowlisted_disclaimers_pass_precheck() -> None:
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

    for dis in ALLOWLISTED_DISCLAIMERS:
        # Use a valid package and set one limitation to the exact allowlisted disclaimer
        # Pre-check should not flag it as forbidden
        data = json.loads(builtin_e3_research_json())
        # Only test disclaimers that are in non_claims - put as non_claim entry
        data["non_claims"][0] = dis
        # Need to ensure other non_claims are not causing extra forbidden - they are already allowlisted
        # For this test, we just check that a package with that dis still has no forbidden pre-errors beyond the expected missing future artifact
        # validate_e3_package_for_admission should return empty (no forbidden) for allowlisted, because allowlisted is exempt
        # But other fields may still be valid, so we check that errs do not contain forbidden
        errs = validate_e3_package_for_admission(data)
        # Filter forbidden errors
        forbidden_errs = [e for e in errs if "forbidden" in e.lower()]
        assert forbidden_errs == [], (
            f"allowlisted disclaimer incorrectly flagged: {dis!r} -> {forbidden_errs}"
        )


def test_admission_deep_nested_forbidden_via_package_object() -> None:
    pkg = load_builtin_e3_research()
    new_factors = dict(pkg.factors)
    new_factors["deep5"] = {"level2": {"deepest": "kubernetes deep via package object is true"}}  # type: ignore[assignment]
    forged = pkg.model_copy(update={"factors": new_factors})
    errs = validate_e3_package_for_admission(forged)
    assert len(errs) > 0
    assert any("kubernetes" in e.lower() for e in errs)
    result = admit_e3_research(forged)
    assert result.admitted is False
    assert "FORBIDDEN" in result.reason_code or "REFUSED" in result.reason_code


def test_admission_deep_nested_true_authorized_via_package_object() -> None:
    pkg = load_builtin_e3_research()
    new_factors = dict(pkg.factors)
    new_factors["deep6"] = {"level2": {"my_authorized": True}}  # type: ignore[assignment]
    forged = pkg.model_copy(update={"factors": new_factors})
    errs = validate_e3_package_for_admission(forged)
    assert len(errs) > 0
    assert any("_authorized" in e.lower() for e in errs)


def test_admission_deep_nested_private_path_via_package_object() -> None:
    pkg = load_builtin_e3_research()
    new_factors = dict(pkg.factors)
    new_factors["deep7"] = {"deep": {"path": "/tmp/evil_via_admission"}}  # type: ignore[assignment]  # noqa: S108
    forged = pkg.model_copy(update={"factors": new_factors})
    errs = validate_e3_package_for_admission(forged)
    assert len(errs) > 0
    assert any("private" in e.lower() for e in errs)


def test_scan_forbidden_recursive_direct() -> None:
    from traffictwin.evidence_admission.e3_research import _scan_forbidden_recursive

    deep = {"a": {"b": {"c": "kubernetes deep direct is true"}}}
    errs = _scan_forbidden_recursive(deep)
    assert any("kubernetes" in e.lower() for e in errs)


# --- Review-2 regression: provenance position-independence via admission ---
_SUPERSEDED_SHA_ADM = "ac8e410f7708188a9dd6e13e1c0311297176839d"
_PROVENANCE_SHAPES_ADM = [
    f"{_SUPERSEDED_SHA_ADM} promotion commit for the research merge",
    "promotion commit " + "x" * 25 + f" {_SUPERSEDED_SHA_ADM}",
    f"promotion commit for the research merge is {_SUPERSEDED_SHA_ADM}",
    f"runner build {_SUPERSEDED_SHA_ADM}",
    f"signed off by reviewer, runner SHA {_SUPERSEDED_SHA_ADM}",
]


def test_provenance_position_independence_via_admission() -> None:
    for note in _PROVENANCE_SHAPES_ADM:
        data = json.loads(builtin_e3_research_json())
        data["provenance"][0]["note"] = note
        errs = validate_e3_package_for_admission(data)
        assert len(errs) > 0, f"expected rejection for note {note!r}, got {errs}"
        assert any(
            "provenance" in e.lower() or "mismatch" in e.lower() or "prefix" in e.lower()
            for e in errs
        ), errs
        result = admit_e3_research(data)
        assert result.admitted is False
        assert "REFUSED" in result.reason_code


def test_provenance_shipped_still_passes_via_admission() -> None:
    pkg = load_builtin_e3_research()
    errs = validate_e3_package_for_admission(pkg)
    assert errs == []
    result = admit_e3_research(pkg)
    # still refused for missing future artifact, but not for provenance mismatch
    assert result.reason_code == "REFUSED_MISSING_FUTURE_ARTIFACT"
    assert (
        "forbidden" not in result.reason_detail.lower()
        or "provenance" not in result.reason_detail.lower()
    )


# --- Review-2 regression: forbidden families via admission (top-level + deep via package object) ---
_FORBIDDEN_FAMILIES_ADM = [
    "the k8s cluster is live",
    "K8S deployment is running in production",
    "we have supervisor approval",
    "approved by the supervisor",
    "Randy approved",
    "universally superior",
    "N is the number of tasks, task-level replication used",
    "results generalize across all of Manchester",
    "42 dollars per hour",
    "£3,000 GBP billing for compute",
    "the actor chooses the execution RSU based on load",
]


def test_forbidden_families_top_level_via_admission_dict() -> None:
    for phrase in _FORBIDDEN_FAMILIES_ADM:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = phrase
        errs = validate_e3_package_for_admission(data)
        assert len(errs) > 0
        assert any("forbidden" in e.lower() for e in errs), (
            f"phrase {phrase!r} not flagged as forbidden: {errs}"
        )
        result = admit_e3_research(data)
        assert result.admitted is False
        assert "REFUSED" in result.reason_code


def test_forbidden_families_deep_nested_via_admission_package_object() -> None:
    for phrase in _FORBIDDEN_FAMILIES_ADM:
        pkg = load_builtin_e3_research()
        new_factors = dict(pkg.factors)
        new_factors["deep_adm"] = {"inner": {"deepest": phrase}}  # type: ignore[assignment]
        forged = pkg.model_copy(update={"factors": new_factors})
        errs = validate_e3_package_for_admission(forged)
        assert len(errs) > 0
        assert any("forbidden" in e.lower() for e in errs), (
            f"deep phrase {phrase!r} not flagged: {errs}"
        )
        result = admit_e3_research(forged)
        assert result.admitted is False


# --- Review-2 regression: Unicode normalization via admission ---
_UNICODE_VARIANTS_ADM = [
    "kub\u0435rnetes",
    "kub\u200bernetes",
    "Ｋｕｂｅｒｎｅｔｅｓ",
]


def test_unicode_variants_rejected_via_admission() -> None:
    for variant in _UNICODE_VARIANTS_ADM:
        data = json.loads(builtin_e3_research_json())
        payload = f"test {variant} cluster"
        data["limitations"][0] = payload
        errs = validate_e3_package_for_admission(data)
        assert len(errs) > 0
        assert any("forbidden" in e.lower() for e in errs)
        # also via package object deep
        pkg = load_builtin_e3_research()
        new_factors = dict(pkg.factors)
        new_factors["deep_unicode"] = {"a": {"b": payload}}  # type: ignore[assignment]
        forged = pkg.model_copy(update={"factors": new_factors})
        errs2 = validate_e3_package_for_admission(forged)
        assert len(errs2) > 0


# --- Review-2 regression: negation phrasing via admission ---
_NEGATION_PHRASES_ADM = [
    "there is no doubt kubernetes cluster is live",
    "never in doubt: supervisor approved this",
]


def test_negation_phrasing_rejected_via_admission() -> None:
    for phrase in _NEGATION_PHRASES_ADM:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = phrase
        errs = validate_e3_package_for_admission(data)
        assert len(errs) > 0
        assert any("forbidden" in e.lower() for e in errs)
        result = admit_e3_research(data)
        assert result.admitted is False


# --- Review-2 regression: allowlist integrity via admission ---
def test_allowlist_integrity_via_admission() -> None:
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

    for dis in ALLOWLISTED_DISCLAIMERS:
        data = json.loads(builtin_e3_research_json())
        data["non_claims"][1] = dis
        errs = validate_e3_package_for_admission(data)
        # allowlisted exact should not produce forbidden errors
        assert not any("forbidden" in e.lower() for e in errs), (
            f"allowlist incorrectly flagged: {dis!r} {errs}"
        )
        # appended should be rejected
        data2 = json.loads(builtin_e3_research_json())
        data2["limitations"][0] = dis + " kubernetes is live"
        errs2 = validate_e3_package_for_admission(data2)
        assert len(errs2) > 0
        assert any("forbidden" in e.lower() for e in errs2)


# --- Review-2 regression: neutering coverage for admission scanner ---
def test_admission_scan_alias_is_canonical() -> None:
    from traffictwin.evidence_admission.e3_research import _scan_forbidden_recursive as adm_scan
    from traffictwin.experiments.e3_research_evidence import _scan_forbidden_recursive as canon_scan

    assert adm_scan is canon_scan
    # direct check that it still detects
    errs = adm_scan({"a": "kubernetes test"})
    assert any("kubernetes" in e.lower() for e in errs)


def test_admission_contains_affirming_still_guards() -> None:
    from traffictwin.experiments.e3_research_evidence import _contains_affirming_forbidden_any

    assert _contains_affirming_forbidden_any("the k8s cluster is live") is not None
    assert _contains_affirming_forbidden_any("approved by the supervisor") is not None
