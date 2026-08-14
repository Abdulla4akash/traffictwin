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
