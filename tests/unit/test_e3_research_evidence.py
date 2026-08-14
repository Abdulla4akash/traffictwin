# ruff: noqa: E501, ANN401
"""Focused tests for E3 research evidence model — Lane 10 typed hold."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from traffictwin.experiments.e3_research_artifact import (
    builtin_e3_research_json,
    load_builtin_e3_research,
)
from traffictwin.experiments.e3_research_evidence import (
    ACTOR_SHA256,
    APPROVED_CANDIDATE_SHA,
    CONTRACT_CHECKPOINT_SHA,
    CONTRACT_SHA256,
    E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED,
    LANE_09,
    MANIFEST_SIDECAR_SHA256,
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
    NOT_EXECUTED,
    TRACE_SHA256,
    TRAFFICTWIN_PRODUCT_BASE_SHA,
    TRAFFICTWIN_RESEARCH_PROMOTION_SHA,
    VEC_ADAPTER_SHA,
    VEC_CORE_SHA,
    VEC_PROMOTION_SHA,
    E3ResearchEvidencePackage,
    load_e3_research_evidence_json,
)


def _valid_pkg() -> E3ResearchEvidencePackage:
    return load_builtin_e3_research()


def test_valid_package_has_immutable_hold_verbatim() -> None:
    pkg = _valid_pkg()
    assert pkg.lane_09 == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    assert pkg.lane_09 == LANE_09
    assert pkg.status == "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"
    assert pkg.status == E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
    assert pkg.evidence_state == "NOT_EXECUTED"
    assert pkg.evidence_state == NOT_EXECUTED
    assert pkg.result_availability == "NO_E3_RESEARCH_RESULTS_AVAILABLE"
    assert pkg.result_availability == NO_E3_RESEARCH_RESULTS_AVAILABLE
    assert pkg.research_workloads_launched == 0
    # Also in execution_authority
    ea = pkg.execution_authority
    assert ea.lane_09 == LANE_09
    assert ea.status == E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
    assert ea.evidence_state == NOT_EXECUTED
    assert ea.result_availability == NO_E3_RESEARCH_RESULTS_AVAILABLE
    assert ea.research_workloads_launched == 0
    # Check raw JSON contains verbatim
    raw = builtin_e3_research_json()
    assert "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD" in raw
    assert "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED" in raw
    assert '"evidence_state": "NOT_EXECUTED"' in raw
    assert '"result_availability": "NO_E3_RESEARCH_RESULTS_AVAILABLE"' in raw
    assert '"research_workloads_launched": 0' in raw


def test_valid_package_pins_exact_frozen_identities() -> None:
    pkg = _valid_pkg()
    assert (
        pkg.product_base_sha
        == TRAFFICTWIN_PRODUCT_BASE_SHA
        == "2b6d4675658b426f96a79c41ac7f0b8f2a82bc5c"
    )
    assert (
        pkg.research_promotion_sha
        == TRAFFICTWIN_RESEARCH_PROMOTION_SHA
        == "342789434233e97cd87ea74e21a759878610ce40"
    )
    assert (
        pkg.approved_candidate_sha
        == APPROVED_CANDIDATE_SHA
        == "c5d66ef7e77f3b7d1f3fde084feea45a83f5c178"
    )
    assert (
        pkg.contract_checkpoint_sha
        == CONTRACT_CHECKPOINT_SHA
        == "211a6662151ccad43187f8a2ce3f75a57515408d"
    )
    assert (
        pkg.vec_runtime.promotion_commit
        == VEC_PROMOTION_SHA
        == "dc606770059f0c4a413bac2217d7f38600b74fff"
    )
    assert (
        pkg.vec_runtime.core_candidate == VEC_CORE_SHA == "53e34db6146da40118a6c816f6a1ffaa2596ddf3"
    )
    assert (
        pkg.vec_runtime.adapter_candidate
        == VEC_ADAPTER_SHA
        == "c37f97ea66b236dfc662bfdd6bee7eab1a775bbc"
    )
    assert (
        pkg.contract.sha256
        == CONTRACT_SHA256
        == "f0d6eb913df6c2165a63ddcb0fd4980368e9bb80bbd38db964273ba3925f4870"
    )
    assert pkg.software_identity.actor_sha256 == ACTOR_SHA256
    assert pkg.software_identity.trace_sha256 == TRACE_SHA256
    # sidecar is constant also
    assert (
        MANIFEST_SIDECAR_SHA256
        == "39862882ae34e71260ce5b466fcd4a93d61da783c4dd16fc987be562ea396438"
    )


def test_valid_package_never_placeholder_sample_synthetic() -> None:
    raw = builtin_e3_research_json().lower()
    assert "placeholder" not in raw
    # synthetic is allowed in notes about not synthetic? but our artifact must not contain synthetic results phrase
    assert "synthetic result" not in raw
    assert "sample result" not in raw
    # Must declare no-results truth
    assert "no_e3_research_results_available" in raw


def test_valid_package_replication_is_fleet_draw_n4() -> None:
    pkg = _valid_pkg()
    rep = pkg.replication
    assert rep.replication_unit == "fleet_draw"
    assert rep.fleet_seeds == [1, 2, 3, 4]
    assert rep.evaluator_seed == 0
    assert rep.n == 4
    assert rep.replication_key == "fleet_seed"
    assert rep.tasks_are_not_replicates is True
    assert rep.seed_0_in_primary is False
    assert rep.degrees_of_freedom == 3
    assert 3.18 < rep.critical_value < 3.19
    assert "Student-t" in rep.method or "Student-t" in rep.interval


def test_state_age_ms_typed_integer_milliseconds() -> None:
    pkg = _valid_pkg()
    for arm in pkg.dormant_arms:
        assert type(arm.state_age_ms) is int
        assert arm.state_age_ms in (0, 1000, 3000)
    for cfg in pkg.dormant_configs:
        assert type(cfg.state_age_ms) is int
        assert cfg.state_age_ms in (0, 1000, 3000)
    assert set(pkg.factors["state_age_ms_values"]) == {0, 1000, 3000}


def test_placement_scaling_factor_sets_exact() -> None:
    pkg = _valid_pkg()
    assert set(pkg.factors["placements"]) == {"ingress_dla", "per_task_dla", "p2c_dla"}
    assert set(pkg.factors["scalings"]) == {
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive",
    }
    # E3a
    assert set(pkg.staged_design.e3a.placement) == {"ingress_dla", "per_task_dla", "p2c_dla"}  # type: ignore[attr-defined]
    assert pkg.staged_design.e3a.scaling == ["fixed_1x"]  # type: ignore[union-attr]
    assert pkg.staged_design.e3a.state_age_ms == [0]
    # E3b
    e3b = pkg.staged_design.e3b
    assert {p.value for p in e3b.placement} == {"per_task_dla"}  # type: ignore[attr-defined]
    assert {p.value for p in e3b.scaling} == {
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive",
    }  # type: ignore[attr-defined]
    assert e3b.state_age_ms == [0]
    assert e3b.stage_listed_cells == 16
    assert e3b.unique_cells == 12
    # E3c
    e3c = pkg.staged_design.e3c
    assert e3c.stale_variant_cells_max == 32
    assert e3c.total_contrast_observations == 48
    assert e3c.fresh_observations_reused == 16
    assert len(e3c.contrasts) == 2


def test_e3a_b_c_structure_exact_counts() -> None:
    pkg = _valid_pkg()
    assert len(pkg.dormant_arms) == 14
    assert len(pkg.dormant_configs) == 56
    assert pkg.staged_design.maximum_candidate_unique_cells == 56
    assert pkg.staged_design.stage_listed_cells == 60
    assert pkg.staged_design.e3a.stage_listed_cells == 12
    assert pkg.staged_design.e3a.unique_cells == 12
    assert pkg.staged_design.e3b.unique_cells == 12  # type: ignore[union-attr]
    # uniqueness
    assert len({a.arm_id for a in pkg.dormant_arms}) == 14
    assert len({c.config_id for c in pkg.dormant_configs}) == 56
    # sorted
    arm_ids = [a.arm_id for a in pkg.dormant_arms]
    assert arm_ids == sorted(arm_ids)
    cfg_ids = [c.config_id for c in pkg.dormant_configs]
    assert cfg_ids == sorted(cfg_ids)


def test_task_accounting_unavailable_stays_null_not_zero() -> None:
    pkg = _valid_pkg()
    ta = pkg.task_accounting
    assert ta.offered is None
    assert ta.admitted is None
    assert ta.rejected_total is None
    assert ta.forwarded is None
    assert ta.deadline_success is None
    assert ta.started is None
    assert ta.compute_completed is None
    assert ta.returned is None
    assert ta.dropped is None
    # reasons exist and never coerce to zero
    for field in ("started", "compute_completed", "returned", "dropped"):
        reason = ta.unavailable_reasons[field]
        assert isinstance(reason, str) and len(reason) > 10
        assert reason.strip().lower() not in ("0", "zero")
        assert "UNAVAILABLE" in reason
    # genuine classes
    assert set(ta.genuine_rejection_classes) == {
        "v2i_gate_rejected",
        "v2i_cap_rejected",
        "local_mqd_rejected",
        "v2v_mqd_rejected",
        "v2i_unavailable",
        "v2v_unavailable",
    }


def test_queue_vs_compute_separate_and_cost_is_resource_unit_seconds() -> None:
    pkg = _valid_pkg()
    assert pkg.queue_capacity.is_queue_not_compute is True
    assert pkg.compute_capacity.is_compute_not_queue is True
    assert pkg.queue_capacity.capacity_per_rsu == 6220
    assert pkg.compute_capacity.max_units == 3
    assert pkg.compute_capacity.min_units == 1
    assert pkg.resource_cost.metric == "resource_unit_seconds"
    assert pkg.resource_cost.monetary is False
    assert "resource_unit_seconds" in pkg.resource_cost.formula
    # scaling receipts null with reasons
    assert pkg.scaling_receipts.receipts_when_not_executed_null_reason.strip() != ""
    assert pkg.scaling_receipts.per_rsu_summaries_null_reason is not None


def test_fingerprint_is_deterministic_64hex() -> None:
    pkg = _valid_pkg()
    fp1 = pkg.fingerprint()
    fp2 = pkg.fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 64
    assert all(c in "0123456789abcdef" for c in fp1)
    # Different after mutation
    data = json.loads(builtin_e3_research_json())
    data["limitations"] = data["limitations"] + ["extra"]
    mutated = load_e3_research_evidence_json(json.dumps(data))
    assert mutated.fingerprint() != fp1


def test_no_supervisor_approval_claim() -> None:
    raw = builtin_e3_research_json().lower()
    assert "supervisor approved" not in raw
    assert "randy confirmed" not in raw
    pkg = _valid_pkg()
    dumped = json.dumps(pkg.model_dump(mode="json")).lower()
    assert "supervisor approved" not in dumped
    assert "randy confirmed" not in dumped


def test_no_private_absolute_paths_in_artifact() -> None:
    raw = builtin_e3_research_json()
    # Check raw does not contain private prefixes with contiguous literal
    assert "private" not in raw.lower() or "/private/" not in raw  # allow the word but not path
    # Our loader should reject if private path introduced
    data = json.loads(raw)
    data["provenance"][0]["note"] = "/" + "Users" + "/" + "example"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))


def test_forbidden_claims_are_rejected() -> None:
    # Queue/compute conflation
    data = json.loads(builtin_e3_research_json())
    data["limitations"][0] = data["limitations"][0] + " queue ceiling is compute is true"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    # Actor selects
    data = json.loads(builtin_e3_research_json())
    data["non_claims"][0] = "actor selects execution rsu is true"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    # Monetary cost
    data = json.loads(builtin_e3_research_json())
    data["resource_cost"]["formula"] = "cost_dollars = 100"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    # true _authorized
    data = json.loads(builtin_e3_research_json())
    data["execution_authority"]["e3a_authorized"] = True
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))


def test_wrong_identity_is_rejected() -> None:
    data = json.loads(builtin_e3_research_json())
    data["product_base_sha"] = "0" * 40
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    data = json.loads(builtin_e3_research_json())
    data["vec_runtime"]["core_candidate"] = "0" * 40
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))


def test_wrong_fingerprint_type_rejected() -> None:
    data = json.loads(builtin_e3_research_json())
    data["contract"]["sha256"] = "nothex"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))


def test_tasks_as_n_is_rejected() -> None:
    data = json.loads(builtin_e3_research_json())
    data["replication"]["replication_unit"] = "task"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    data = json.loads(builtin_e3_research_json())
    data["replication"]["n"] = 1000
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))


def test_provenance_limitations_missingness_are_first_class() -> None:
    pkg = _valid_pkg()
    assert len(pkg.provenance) >= 1
    assert len(pkg.limitations) >= 1
    assert len(pkg.missingness) >= 1
    assert len(pkg.non_claims) >= 1
    for entry in pkg.provenance:
        assert len(entry.artifact) > 5
        assert len(entry.note) > 10
    for miss in pkg.missingness:
        assert len(miss.field) > 1
        assert len(miss.reason) > 10


# --- Blocker 1 regressions ---
def test_provenance_wrong_ac8e410_rejected() -> None:
    data = json.loads(builtin_e3_research_json())
    for entry in data["provenance"]:
        if entry["kind"] == "runner":
            entry["note"] = "approved candidate ac8e410... and promotion 342789..."
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    msg = str(exc.value).lower()
    assert "approval" in msg or "provenance" in msg or "mismatch" in msg


def test_provenance_corrected_passes() -> None:
    data = json.loads(builtin_e3_research_json())
    for entry in data["provenance"]:
        if entry["kind"] == "runner":
            entry["note"] = (
                "approved candidate c5d66ef7e77f3b7d1f3fde084feea45a83f5c178 and promotion 342789434233e97cd87ea74e21a759878610ce40"
            )
    pkg = load_e3_research_evidence_json(json.dumps(data))
    assert pkg.approved_candidate_sha == "c5d66ef7e77f3b7d1f3fde084feea45a83f5c178"
    assert pkg.research_promotion_sha == "342789434233e97cd87ea74e21a759878610ce40"


def test_provenance_wrong_promotion_rejected() -> None:
    data = json.loads(builtin_e3_research_json())
    for entry in data["provenance"]:
        if entry["kind"] == "runner":
            entry["note"] = (
                "approved candidate c5d66ef7e77f3b7d1f3fde084feea45a83f5c178 and promotion deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            )
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    msg = str(exc.value).lower()
    assert "promotion" in msg or "mismatch" in msg


# --- Blocker 2 fail-closed regressions ---
def test_bypass_strings_are_rejected() -> None:
    # Measured bypasses that previously slipped via negation window
    for payload in [
        "there is no doubt kubernetes cluster is live",
        "never in doubt: supervisor approved this",
    ]:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = payload
        with pytest.raises((ValidationError, ValueError)):
            load_e3_research_evidence_json(json.dumps(data))


def test_forbidden_families_top_level_rejected() -> None:
    families = [
        "kubernetes cluster is live is true",
        "supervisor approved this deployment is true",
        "universal superiority is proven is true",
        "tasks as n is valid is true",
        "manchester-wide inference is valid is true",
        "monetary cost is low is true",
        "actor selects execution rsu is true",
        "cost_dollars = 100 is true",
        "randy confirmed this is true",
        "queue ceiling is compute is true",
    ]
    for phrase in families:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = phrase
        with pytest.raises((ValidationError, ValueError)) as exc:
            load_e3_research_evidence_json(json.dumps(data))
        assert "forbidden" in str(exc.value).lower() or "claim" in str(exc.value).lower()


def test_forbidden_families_deep_nested_rejected() -> None:
    families = [
        ("kubernetes is live deep", "kubernetes"),
        ("supervisor approved deep", "supervisor approved"),
        ("universal superiority deep", "universal superiority"),
        ("tasks_as_n deep", "tasks_as_n"),
        ("manchester_wide deep", "manchester_wide"),
        ("monetary cost deep", "monetary cost"),
        ("actor_selects_rsu deep", "actor_selects_rsu"),
        ("cost_dollars deep", "cost_dollars"),
        ("randy confirmed deep", "randy confirmed"),
        ("queue ceiling is compute deep", "queue ceiling is"),
    ]
    for phrase, needle in families:
        data = json.loads(builtin_e3_research_json())
        # deep-nested under factors extra with neutral key
        data["factors"]["deep_nested"] = {"level2": {"level3": phrase}}  # type: ignore[assignment]
        with pytest.raises((ValidationError, ValueError)) as exc:
            load_e3_research_evidence_json(json.dumps(data))
        msg = str(exc.value).lower()
        assert needle in msg


def test_allowlisted_disclaimers_still_pass() -> None:
    # Exact allowlisted disclaimers must be accepted even though they contain forbidden substrings
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

    for disclaimer in ALLOWLISTED_DISCLAIMERS:
        data = json.loads(builtin_e3_research_json())
        # Place disclaimer as a whole non_claim entry (exact byte-equal) - should be exempt
        # Replace index 1 (not the fleet_draw entry at 0) to keep fleet_draw mention
        data["non_claims"][1] = disclaimer
        pkg = load_e3_research_evidence_json(json.dumps(data))
        assert pkg is not None
    # Also test that a string containing allowlisted disclaimer as substring but with extra suffix is rejected
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

    data = json.loads(builtin_e3_research_json())
    dis = ALLOWLISTED_DISCLAIMERS[0]
    data["limitations"][0] = dis + " extra suffix to break exact match kubernetes is live"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))


# --- Blocker 3 recursive scan coverage ---
def test_deep_nested_private_path_caught_by_scan() -> None:
    data = json.loads(builtin_e3_research_json())
    # Private path deep under factors extra nested - field validator for factors does not check private path for nested, only scan does
    # Use neutral extra key that does not contain 'private' to isolate scan vs extra error
    data["factors"]["deep1"] = {"a": {"b": "/tmp/evil_private_path"}}  # type: ignore[assignment]  # noqa: S108
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    assert "private" in str(exc.value).lower()


def test_deep_nested_true_authorized_caught_by_scan() -> None:
    data = json.loads(builtin_e3_research_json())
    # Deep-nested true _authorized under factors (field validator does not check _authorized)
    data["factors"]["deep2"] = {"level2": {"my_authorized": True}}  # type: ignore[assignment]
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    msg = str(exc.value).lower()
    assert "_authorized" in msg


def test_deep_nested_forbidden_via_evidence_scan() -> None:
    data = json.loads(builtin_e3_research_json())
    data["factors"]["deep3"] = {"x": {"y": "kubernetes deep forbidden claim is true"}}  # type: ignore[assignment]
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    assert "kubernetes" in str(exc.value).lower()


def test_artifact_private_path_secret_via_artifact_api() -> None:
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact

    raw = builtin_e3_research_json()
    data = json.loads(raw)
    # Inject private path as a key (not value) deep inside factors to isolate artifact raw check
    # Key containing private path will be caught by artifact raw text check but not by evidence dict scan (which doesn't check keys for private path)
    data["factors"]["evil_key"] = {"/tmp/evil_key": 123}  # type: ignore[assignment]  # noqa: S108
    injected = json.dumps(data)
    with pytest.raises((ValidationError, ValueError)) as exc:
        validate_e3_research_artifact(injected)
    assert "private path" in str(exc.value).lower()


# --- Secondary 1 factors strict ---
def test_factors_extra_result_like_numeric_rejected() -> None:
    data = json.loads(builtin_e3_research_json())
    data["factors"]["e3a_mean_diff"] = 0.062  # type: ignore[assignment]
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    assert "extra" in str(exc.value).lower() or "factors" in str(exc.value).lower()


def test_factors_allows_all_declared_keys() -> None:
    data = json.loads(builtin_e3_research_json())
    # Should pass with all declared keys present
    pkg = load_e3_research_evidence_json(json.dumps(data))
    assert pkg.factors["padded_fleet_width"] == 2488
    assert pkg.factors["smoke_ticks"] == 10


# --- Secondary 4 manifest sidecar ---
def test_manifest_sidecar_mismatch_rejected() -> None:
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact

    raw = builtin_e3_research_json()
    data = json.loads(raw)
    # Corrupt manifest sidecar SHA in provenance
    for entry in data["provenance"]:
        if entry["kind"] == "manifest":
            entry["note"] = entry["note"].replace(
                "39862882ae34e71260ce5b466fcd4a93d61da783c4dd16fc987be562ea396438",
                "0000000000000000000000000000000000000000000000000000000000000000",
            )
    with pytest.raises((ValidationError, ValueError)) as exc:
        validate_e3_research_artifact(json.dumps(data))
    assert "manifest" in str(exc.value).lower() or "sidecar" in str(exc.value).lower()


# --- Blocker 3 direct scan unit tests ---
def test_scan_for_private_paths_direct() -> None:
    from traffictwin.experiments.e3_research_evidence import _scan_forbidden_recursive

    deep = {"a": {"b": {"c": "/tmp/direct_private"}}}  # noqa: S108
    violations = _scan_forbidden_recursive(deep)
    assert any("private path" in v.lower() for v in violations)
    # Secret via password keyword (no assignment) should be caught only by this scan
    deep_secret = {"x": {"y": "my password is foo"}}
    violations2 = _scan_forbidden_recursive(deep_secret)
    assert any("secret" in v.lower() for v in violations2)


def test_scan_for_true_authorized_direct() -> None:
    from traffictwin.experiments.e3_research_evidence import _scan_forbidden_recursive

    deep_true = {"a": {"b": {"my_authorized": True}}}
    violations = _scan_forbidden_recursive(deep_true)
    assert any("_authorized" in v.lower() for v in violations)
    # Non-bool authorized should also be caught only by this scan
    deep_nobool = {"a": {"b": {"other_authorized": "yes"}}}
    violations2 = _scan_forbidden_recursive(deep_nobool)
    assert any("_authorized" in v.lower() for v in violations2)


def test_assert_no_private_paths_direct() -> None:
    from traffictwin.experiments.e3_research_artifact import _assert_no_private_paths_or_secrets

    with pytest.raises((ValidationError, ValueError)):
        _assert_no_private_paths_or_secrets("prefix /tmp/private is here")
    with pytest.raises((ValidationError, ValueError)):
        _assert_no_private_paths_or_secrets("api_key: secret123")


# --- Review-2 regression: provenance position-independence (superseded SHA ac8e410f...) ---
_SUPERSEDED_SHA = "ac8e410f7708188a9dd6e13e1c0311297176839d"

_PROVENANCE_SHAPES = [
    # SHA-before-keyword
    f"{_SUPERSEDED_SHA} promotion commit for the research merge",
    # keyword more than 20 chars away (25 filler chars)
    "promotion commit " + "x" * 25 + f" {_SUPERSEDED_SHA}",
    # exact phrase "promotion commit for the research merge is <sha>"
    f"promotion commit for the research merge is {_SUPERSEDED_SHA}",
    # "runner build <sha>"
    f"runner build {_SUPERSEDED_SHA}",
    # "signed off by reviewer, runner SHA <sha>"
    f"signed off by reviewer, runner SHA {_SUPERSEDED_SHA}",
]


@pytest.mark.parametrize("note", _PROVENANCE_SHAPES)
def test_provenance_superseded_sha_position_independence_rejected(note: str) -> None:
    data = json.loads(builtin_e3_research_json())
    # inject into provenance note (first manifest entry) to test position-independent hex validation
    data["provenance"][0]["note"] = note
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    msg = str(exc.value).lower()
    assert "provenance" in msg or "mismatch" in msg or "prefix" in msg or "approval" in msg


def test_provenance_superseded_sha_end_to_end_via_artifact_and_admission() -> None:
    # At least one shape end-to-end through artifact validation and admission
    from traffictwin.evidence_admission.e3_research import (
        admit_e3_research,
        validate_e3_package_for_admission,
    )
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact

    note = f"signed off by reviewer, runner SHA {_SUPERSEDED_SHA}"
    data = json.loads(builtin_e3_research_json())
    data["provenance"][0]["note"] = note
    text = json.dumps(data)
    # artifact validation
    with pytest.raises((ValidationError, ValueError)):
        validate_e3_research_artifact(text)
    # loader
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(text)
    # admission via dict (validate helper)
    errs = validate_e3_package_for_admission(data)
    assert len(errs) > 0
    assert any(
        "provenance" in e.lower() or "mismatch" in e.lower() or "prefix" in e.lower() for e in errs
    )
    result = admit_e3_research(data)
    assert result.admitted is False
    assert "REFUSED" in result.reason_code


def test_shipped_provenance_notes_still_pass() -> None:
    # Shipped notes must still validate (no false positive on allowed SHAs)
    pkg = load_builtin_e3_research()
    assert len(pkg.provenance) >= 4
    # each note should not contain superseded SHA and should validate
    for entry in pkg.provenance:
        assert _SUPERSEDED_SHA not in entry.note.lower()
    # full load still passes
    raw = builtin_e3_research_json()
    pkg2 = load_e3_research_evidence_json(raw)
    assert pkg2.product_base_sha == pkg.product_base_sha
    # also via artifact
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact

    validated = validate_e3_research_artifact(raw)
    assert validated.fingerprint() == pkg.fingerprint()


# --- Review-2 regression: forbidden-claim families via package loader (11 families) ---
_FORBIDDEN_FAMILIES = [
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


@pytest.mark.parametrize("phrase", _FORBIDDEN_FAMILIES)
def test_forbidden_families_rejected_top_level_via_loader(phrase: str) -> None:
    data = json.loads(builtin_e3_research_json())
    # top-level free-text field: limitations[0]
    data["limitations"][0] = phrase
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    msg = str(exc.value).lower()
    assert "forbidden" in msg or "claim" in msg


@pytest.mark.parametrize("phrase", _FORBIDDEN_FAMILIES)
def test_forbidden_families_rejected_deep_nested_via_loader(phrase: str) -> None:
    data = json.loads(builtin_e3_research_json())
    # deep-nested under factors (scan occurs before extra keys validator for forbidden content)
    data["factors"]["deep_nested"] = {"level2": {"level3": phrase}}  # type: ignore[assignment]
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    msg = str(exc.value).lower()
    # should mention forbidden claim (scan) rather than extra keys
    assert "forbidden" in msg or "claim" in msg


# --- Review-2 regression: Unicode normalization (Cyrillic, zero-width, fullwidth) ---
_UNICODE_VARIANTS = [
    ("cyrillic-e kubеrnetes", "kub\u0435rnetes"),  # Cyrillic е U+0435
    ("zero-width kub\u200bernetes", "kub\u200bernetes"),  # ZERO WIDTH SPACE U+200B
    ("fullwidth Ｋｕｂｅｒｎｅｔｅｓ", "Ｋｕｂｅｒｎｅｔｅｓ"),
]


@pytest.mark.parametrize("label,phrase", _UNICODE_VARIANTS)
def test_unicode_normalization_variants_rejected(label: str, phrase: str) -> None:  # noqa: ARG001
    data = json.loads(builtin_e3_research_json())
    # Embed variant inside a sentence to ensure pattern still matches after normalization
    payload = f"this is {phrase} cluster live"
    data["limitations"][0] = payload
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    msg = str(exc.value).lower()
    assert "forbidden" in msg or "claim" in msg or "kubernetes" in msg


# --- Review-2 regression: negation phrasing via loader ---
_NEGATION_PHRASES = [
    "there is no doubt kubernetes cluster is live",
    "never in doubt: supervisor approved this",
]


@pytest.mark.parametrize("phrase", _NEGATION_PHRASES)
def test_negation_phrasing_rejected_via_loader(phrase: str) -> None:
    data = json.loads(builtin_e3_research_json())
    data["limitations"][0] = phrase
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))


# --- Review-2 regression: allowlist integrity ---
def test_allowlist_exact_still_passes_and_appended_rejected() -> None:
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS

    # exact pass: each allowlisted disclaimer as a whole non_claim entry
    for dis in ALLOWLISTED_DISCLAIMERS:
        data = json.loads(builtin_e3_research_json())
        data["non_claims"][1] = dis
        pkg = load_e3_research_evidence_json(json.dumps(data))
        assert pkg is not None

    # appended claim should be rejected (exact allowlist is byte-equal exempt only)
    for dis in ALLOWLISTED_DISCLAIMERS:
        data = json.loads(builtin_e3_research_json())
        # append a forbidden claim to the allowlisted disclaimer
        data["limitations"][0] = dis + " kubernetes is live"
        with pytest.raises((ValidationError, ValueError)):
            load_e3_research_evidence_json(json.dumps(data))
        # also test via non_claims appended
        data2 = json.loads(builtin_e3_research_json())
        data2["non_claims"][1] = dis + " supervisor approved"
        with pytest.raises((ValidationError, ValueError)):
            load_e3_research_evidence_json(json.dumps(data2))


# --- Review-2 regression: consolidation structure (single scanner) ---
def test_consolidation_single_recursive_scanner_and_canonical_imports() -> None:
    import pathlib

    lane_files = [
        "src/traffictwin/experiments/e3_research_evidence.py",
        "src/traffictwin/experiments/e3_research_artifact.py",
        "src/traffictwin/experiments/e3_strategy_semantics.py",
        "src/traffictwin/evidence_admission/e3_research.py",
        "src/traffictwin/experiments/e3_comparison.py",
        "src/traffictwin/experiments/e3_task_accounting.py",
    ]
    total_defs = 0
    for rel in lane_files:
        text = pathlib.Path(rel).read_text(encoding="utf-8")
        # count definitions of the canonical recursive scanner
        count = text.count("def _scan_forbidden_recursive")
        total_defs += count
    assert total_defs == 1, (
        f"expected exactly one def _scan_forbidden_recursive across lane files, got {total_defs}"
    )

    # e3_strategy_semantics and evidence_admission must reference canonical, not define own
    for rel in [
        "src/traffictwin/experiments/e3_strategy_semantics.py",
        "src/traffictwin/evidence_admission/e3_research.py",
    ]:
        text = pathlib.Path(rel).read_text(encoding="utf-8")
        assert "def _scan_forbidden_recursive" not in text, f"{rel} should not define scanner"
        assert "from traffictwin.experiments.e3_research_evidence import" in text
        assert "_scan_forbidden_recursive" in text

    # also ensure artifact file does not define scanner but defines _assert_no_private_paths
    art_text = pathlib.Path("src/traffictwin/experiments/e3_research_artifact.py").read_text(
        encoding="utf-8"
    )
    assert "def _scan_forbidden_recursive" not in art_text
    assert "_assert_no_private_paths_or_secrets" in art_text


# --- Review-2 regression: neutering coverage (canonical functions) ---
def test_scan_forbidden_recursive_direct_canonical() -> None:
    from traffictwin.experiments.e3_research_evidence import _scan_forbidden_recursive

    payload = {"a": {"b": "kubernetes is live direct"}}
    violations = _scan_forbidden_recursive(payload)
    assert any("kubernetes" in v.lower() for v in violations)
    # private path
    payload2 = {"x": "/tmp/neuter_test"}  # noqa: S108
    violations2 = _scan_forbidden_recursive(payload2)
    assert any("private" in v.lower() for v in violations2)
    # _authorized true
    payload3 = {"deep": {"my_authorized": True}}
    violations3 = _scan_forbidden_recursive(payload3)
    assert any("_authorized" in v.lower() for v in violations3)
    # hex mismatch
    payload4 = {"note": f"note with {_SUPERSEDED_SHA}"}
    violations4 = _scan_forbidden_recursive(payload4)
    assert any("provenance" in v.lower() or "mismatch" in v.lower() for v in violations4)


def test_contains_affirming_forbidden_any_direct() -> None:
    from traffictwin.experiments.e3_research_evidence import (
        ALLOWLISTED_DISCLAIMERS,
        _contains_affirming_forbidden_any,
    )

    # forbidden should return non-None
    assert _contains_affirming_forbidden_any("kubernetes is live") is not None
    assert _contains_affirming_forbidden_any("supervisor approved") is not None
    assert _contains_affirming_forbidden_any("42 dollars per hour") is not None
    # allowlisted exact should return None
    for dis in ALLOWLISTED_DISCLAIMERS:
        assert _contains_affirming_forbidden_any(dis) is None
    # allowlisted with extra should be flagged
    assert _contains_affirming_forbidden_any(ALLOWLISTED_DISCLAIMERS[0] + " kubernetes") is not None
    # unicode normalized should be flagged
    assert _contains_affirming_forbidden_any("kub\u0435rnetes") is not None
    assert _contains_affirming_forbidden_any("kub\u200bernetes") is not None
    assert _contains_affirming_forbidden_any("Ｋｕｂｅｒｎｅｔｅｓ") is not None


def test_scan_for_private_paths_alias_is_canonical() -> None:
    # Alias was deleted as dead code; canonical is _scan_forbidden_recursive
    from traffictwin.experiments.e3_research_evidence import _scan_forbidden_recursive

    violations = _scan_forbidden_recursive({"a": "/tmp/alias_test"})  # noqa: S108
    assert any("private" in v.lower() for v in violations)


def test_scan_for_true_authorized_alias_is_canonical() -> None:
    # Alias was deleted as dead code; canonical is _scan_forbidden_recursive
    from traffictwin.experiments.e3_research_evidence import _scan_forbidden_recursive

    violations = _scan_forbidden_recursive({"a": {"my_authorized": True}})
    assert any("_authorized" in v.lower() for v in violations)


def test_assert_no_private_paths_or_secrets_direct_still_guards() -> None:
    from traffictwin.experiments.e3_research_artifact import _assert_no_private_paths_or_secrets

    with pytest.raises((ValidationError, ValueError)):
        _assert_no_private_paths_or_secrets("/tmp/private_still_caught")  # noqa: S108
    with pytest.raises((ValidationError, ValueError)):
        _assert_no_private_paths_or_secrets("token: secret assignment test api_key: xyz")
    # clean text should not raise
    _assert_no_private_paths_or_secrets("this is a clean artifact text with no secrets")


# --- Review-3 Blocker A: confusable folding must be class-killing, not hand-rolled list ---
_REVIEW3_BYPASSES = [
    "кubеrnеtеs cluster is live and orchestrating in production",
    "ѕupervisor approval was granted for E3 execution",
    "universally ѕuperior",
    "the actor ѕelects the execution RSU",
]

# Four NEW single-substitution variants using characters NOT mapped explicitly (proving backstop e.g. Coptic/Armenian)
_NEW_BACKSTOP_VARIANTS = [
    "kuber\u2c81etes cluster is live",  # Coptic Alfa U+2C81 not in map - no literal kubernetes
    "super\u0561visor approval was granted",  # Armenian AYB U+0561 - no literal supervisor
    "kuber\u03f2etes cluster is live",  # Greek Lunate Sigma U+03F2 not in map - no literal
    "\u13daelects the execution RSU",  # Cherokee Letter Du U+13DA - no literal actor
]


def test_review3_bypasses_rejected_via_loader() -> None:
    for payload in _REVIEW3_BYPASSES:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = data["limitations"][0] + " " + payload
        with pytest.raises((ValidationError, ValueError)) as exc:
            load_e3_research_evidence_json(json.dumps(data))
        msg = str(exc.value).lower()
        assert "forbidden" in msg or "mixed_script" in msg or "claim" in msg


def test_review3_bypasses_rejected_via_artifact() -> None:
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact

    for payload in _REVIEW3_BYPASSES:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = data["limitations"][0] + " " + payload
        with pytest.raises((ValidationError, ValueError)) as exc:
            validate_e3_research_artifact(json.dumps(data))
        assert "forbidden" in str(exc.value).lower() or "mixed_script" in str(exc.value).lower()


def test_review3_bypasses_rejected_via_admission_pre_errors() -> None:
    from traffictwin.evidence_admission.e3_research import (
        admit_e3_research,
        validate_e3_package_for_admission,
    )

    for payload in _REVIEW3_BYPASSES:
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = data["limitations"][0] + " " + payload
        errs = validate_e3_package_for_admission(data)
        assert any("forbidden" in e.lower() for e in errs), f"expected forbidden in {errs}"
        result = admit_e3_research(data)
        assert result.reason_code == "REFUSED_FORBIDDEN_CLAIM", (
            f"got {result.reason_code} {result.reason_detail}"
        )


def test_review3_bypasses_rejected_via_strategy_semantics() -> None:
    import dataclasses

    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    for payload in _REVIEW3_BYPASSES:
        for field in ["admission", "forwarding", "execution_placement", "human_label"]:
            canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
            try:
                dataclasses.replace(canon, **{field: payload})  # type: ignore[arg-type]
                raise AssertionError(f"expected rejection for {payload!r} in {field}")
            except ValueError as exc:
                assert "forbidden" in str(exc).lower() or "mixed_script" in str(exc).lower()


def test_new_backstop_variants_rejected_via_all_surfaces() -> None:
    import dataclasses

    from traffictwin.evidence_admission.e3_research import (
        admit_e3_research,
        validate_e3_package_for_admission,
    )
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact
    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    for payload in _NEW_BACKSTOP_VARIANTS:
        # loader
        data = json.loads(builtin_e3_research_json())
        data["limitations"][0] = data["limitations"][0] + " " + payload
        with pytest.raises((ValidationError, ValueError)):
            load_e3_research_evidence_json(json.dumps(data))
        # artifact
        with pytest.raises((ValidationError, ValueError)):
            validate_e3_research_artifact(json.dumps(data))
        # admission
        data2 = json.loads(builtin_e3_research_json())
        data2["limitations"][0] = data2["limitations"][0] + " " + payload
        errs = validate_e3_package_for_admission(data2)
        assert any("forbidden" in e.lower() or "mixed_script" in e.lower() for e in errs)
        result = admit_e3_research(data2)
        assert result.reason_code == "REFUSED_FORBIDDEN_CLAIM"
        # strategy semantics
        for field in ["admission", "forwarding", "execution_placement", "human_label"]:
            canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
            try:
                dataclasses.replace(canon, **{field: payload})  # type: ignore[arg-type]
                raise AssertionError(f"expected rejection for backstop {payload!r} in {field}")
            except ValueError:
                pass


def test_shipped_json_semantics_disclaimers_still_load() -> None:
    # Shipped JSON must still load (pure single-script Latin)
    raw = builtin_e3_research_json()
    pkg = load_e3_research_evidence_json(raw)
    assert pkg.lane_09 == LANE_09
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact

    validated = validate_e3_research_artifact(raw)
    assert validated.lane_09 == LANE_09
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS
    from traffictwin.experiments.e3_strategy_semantics import e3_strategy_semantics

    for sem in e3_strategy_semantics():
        assert sem.placement_id in ("ingress_dla", "per_task_dla", "p2c_dla")
    # disclaimers are pure ASCII, not mixed (fold-to-ASCII-or-reject)
    for dis in ALLOWLISTED_DISCLAIMERS:
        from traffictwin.experiments.e3_research_evidence import (
            _contains_affirming_forbidden_any,
            _fold_to_ascii_or_reject,
        )

        assert _contains_affirming_forbidden_any(dis) is None
        # Fold should not raise for allowlisted disclaimers (they are pure ASCII)
        assert _fold_to_ascii_or_reject(dis) is not None


# --- Blocker B+C: one hex validator and mutation coverage for forbidden detection and hex ---
def test_forbidden_detection_rejected_via_dormant_arm_public_surface() -> None:
    from traffictwin.experiments.e3_research_evidence import DormantArm

    # Use a valid placement/scaling but inject forbidden claim into arm_id via the validator's forbidden check.
    # We use an arm_id that is not canonical but contains forbidden, so it should be rejected for forbidden before canonical.
    # The validator checks forbidden first, then canonical, so we assert forbidden in message.
    with pytest.raises(ValidationError) as exc:
        DormantArm(
            arm_id="forbidden kubernetes claim is here",
            placement="ingress_dla",
            scaling="fixed_1x",
            state_age_ms=0,
        )
    assert "forbidden" in str(exc.value).lower()


def test_remaining_validators_direct_wiring() -> None:
    """Direct wiring to cover remaining validators that were survivors in sweep."""
    from traffictwin.experiments.e3_research_evidence import (
        ContractIdentity,
        DormantArm,
        DormantConfig,
        E3aDesign,
        E3bDesign,
        E3cContrastSpec,
        E3cDesign,
        ReplicationSpec,
        ResourceCostSpec,
        ScalingReceiptSpec,
        SoftwareIdentity,
        TaskAccountingSpec,
        TraffictwinRuntime,
        VecRuntime,
    )

    # VecRuntime
    with pytest.raises(ValidationError):
        VecRuntime(
            promotion_commit="0" * 40,
            core_candidate="53e34db6146da40118a6c816f6a1ffaa2596ddf3",
            adapter_candidate="c37f97ea66b236dfc662bfdd6bee7eab1a775bbc",
        )
    with pytest.raises(ValidationError):
        VecRuntime(
            promotion_commit="dc606770059f0c4a413bac2217d7f38600b74fff",
            core_candidate="nothex",
            adapter_candidate="c37f97ea66b236dfc662bfdd6bee7eab1a775bbc",
        )
    # TraffictwinRuntime
    with pytest.raises(ValidationError):
        TraffictwinRuntime(base_commit="0" * 40)
    with pytest.raises(ValidationError):
        TraffictwinRuntime(base_commit="nothex")
    # ContractIdentity path
    with pytest.raises(ValidationError):
        ContractIdentity(
            schema_version="e3_dynamic_resource_v2_contract_v2",
            sha256="f0d6eb913df6c2165a63ddcb0fd4980368e9bb80bbd38db964273ba3925f4870",
            path="wrong/path.json",
        )
    # SoftwareIdentity
    with pytest.raises(ValidationError):
        SoftwareIdentity(
            actor_sha256="0" * 64,
            trace_sha256="e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
            e2d_manifest_sha256="f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
            vec_promoted_base="b2abcee2b4c2628e604fff0811110b8c61a22b23",
            traffictwin_contract_head="211a6662151ccad43187f8a2ce3f75a57515408d",
            vec_core_candidate_sha="53e34db6146da40118a6c816f6a1ffaa2596ddf3",
        )
    with pytest.raises(ValidationError):
        SoftwareIdentity(
            actor_sha256="93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208",
            trace_sha256="e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056",
            e2d_manifest_sha256="f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
            vec_promoted_base="nothex",
            traffictwin_contract_head="211a6662151ccad43187f8a2ce3f75a57515408d",
            vec_core_candidate_sha="53e34db6146da40118a6c816f6a1ffaa2596ddf3",
        )
    # DormantArm
    with pytest.raises(ValidationError):
        DormantArm(
            arm_id="ingress_dla__fixed_1x__age_999ms",
            placement="ingress_dla",
            scaling="fixed_1x",
            state_age_ms=999,
        )
    with pytest.raises(ValidationError):
        DormantArm(arm_id="bad", placement="ingress_dla", scaling="fixed_1x", state_age_ms=0)
    with pytest.raises(ValidationError):
        DormantArm(
            arm_id="ingress_dla__fixed_1x__age_0ms",
            placement="per_task_dla",
            scaling="fixed_1x",
            state_age_ms=0,
        )
    # DormantConfig
    with pytest.raises(ValidationError):
        DormantConfig(
            config_id="per_task_dla__fixed_1x__age_0ms__eval_0__fleet_1__rsus_10",
            arm_id="per_task_dla__fixed_1x__age_0ms",
            placement="per_task_dla",
            scaling="fixed_1x",
            state_age_ms=999,
            evaluator_seed=0,
            fleet_seed=1,
            num_rsus=10,
        )
    with pytest.raises(ValidationError):
        DormantConfig(
            config_id="per_task_dla__fixed_1x__age_0ms__eval_0__fleet_99__rsus_10",
            arm_id="per_task_dla__fixed_1x__age_0ms",
            placement="per_task_dla",
            scaling="fixed_1x",
            state_age_ms=0,
            evaluator_seed=0,
            fleet_seed=99,
            num_rsus=10,
        )
    with pytest.raises(ValidationError):
        DormantConfig(
            config_id="bad",
            arm_id="per_task_dla__fixed_1x__age_0ms",
            placement="per_task_dla",
            scaling="fixed_1x",
            state_age_ms=0,
            evaluator_seed=0,
            fleet_seed=1,
            num_rsus=10,
        )
    # E3a
    with pytest.raises(ValidationError):
        E3aDesign(
            stage="E3a",
            placement=["ingress_dla"],
            scaling=["fixed_1x"],
            state_age_ms=[999],
            fleet_seeds=[1, 2, 3, 4],
            evaluator_seed=0,
            replication_unit="fleet_draw",
            n=4,
            stage_listed_cells=12,
            unique_cells=12,
            equation="x",
        )
    with pytest.raises(ValidationError):
        E3aDesign(
            stage="E3a",
            placement=["ingress_dla", "per_task_dla", "p2c_dla"],
            scaling=["fixed_1x"],
            state_age_ms=[0],
            fleet_seeds=[1, 2, 3],
            evaluator_seed=0,
            replication_unit="fleet_draw",
            n=4,
            stage_listed_cells=12,
            unique_cells=12,
            equation="x",
        )
    with pytest.raises(ValidationError):
        E3aDesign(
            stage="E3a",
            placement=["bad"],
            scaling=["fixed_1x"],
            state_age_ms=[0],
            fleet_seeds=[1, 2, 3, 4],
            evaluator_seed=0,
            replication_unit="fleet_draw",
            n=4,
            stage_listed_cells=12,
            unique_cells=12,
            equation="x",
        )
    # E3b
    with pytest.raises(ValidationError):
        E3bDesign(
            stage="E3b",
            placement=["per_task_dla"],
            scaling=["fixed_1x"],
            state_age_ms=[999],
            fleet_seeds=[1, 2, 3, 4],
            evaluator_seed=0,
            replication_unit="fleet_draw",
            n=4,
            stage_listed_cells=16,
            unique_cells=12,
            unique_additional=12,
            overlap_with_e3a=4,
            equation="x",
        )
    with pytest.raises(ValidationError):
        E3bDesign(
            stage="E3b",
            placement=["per_task_dla"],
            scaling=["fixed_1x"],
            state_age_ms=[0],
            fleet_seeds=[1, 2, 3],
            evaluator_seed=0,
            replication_unit="fleet_draw",
            n=4,
            stage_listed_cells=16,
            unique_cells=12,
            unique_additional=12,
            overlap_with_e3a=4,
            equation="x",
        )
    # E3c
    with pytest.raises(ValidationError):
        E3cContrastSpec(comparison="x", over_stale_ms=[999], fixed="y", fixed_placement=None)
    with pytest.raises(ValidationError):
        E3cDesign(
            stage="E3c",
            contrasts=[
                E3cContrastSpec(
                    comparison="x", over_stale_ms=[0, 1000, 3000], fixed="y", fixed_placement=None
                )
            ],
            state_age_ms_values=[999],
            stale_variant_cells_max=32,
            total_contrast_observations=48,
            fresh_observations_reused=16,
            state_is_view_parameter=True,
            reuses_identical_fresh_cells=True,
        )
    with pytest.raises(ValidationError):
        E3cDesign(
            stage="E3c",
            contrasts=[
                E3cContrastSpec(
                    comparison="x", over_stale_ms=[0, 1000, 3000], fixed="y", fixed_placement=None
                )
            ],
            state_age_ms_values=[0, 1000, 3000],
            stale_variant_cells_max=32,
            total_contrast_observations=48,
            fresh_observations_reused=16,
            state_is_view_parameter=True,
            reuses_identical_fresh_cells=True,
        )
    # ReplicationSpec
    with pytest.raises(ValidationError):
        ReplicationSpec(
            replication_unit="fleet_draw",
            fleet_seeds=[1, 2, 3],
            evaluator_seed=0,
            n=4,
            replication_key="fleet_seed",
            tasks_are_not_replicates=True,
            seed_0_in_primary=False,
            interval="Student-t 95% interval, df=3, t=3.182",
            method="two-sided Student-t 95% interval",
            degrees_of_freedom=3,
            critical_value=3.182,
        )
    with pytest.raises(ValidationError):
        ReplicationSpec(
            replication_unit="fleet_draw",
            fleet_seeds=[1, 2, 3, 4],
            evaluator_seed=0,
            n=4,
            replication_key="fleet_seed",
            tasks_are_not_replicates=True,
            seed_0_in_primary=False,
            interval="bad interval",
            method="bad method",
            degrees_of_freedom=3,
            critical_value=3.182,
        )
    # Queue, Compute, Resource, Scaling, Task, Provenance
    from traffictwin.experiments.e3_research_evidence import (
        ComputeCapacitySpec,
        ProvenanceEntry,
        QueueCapacitySpec,
    )

    with pytest.raises(ValidationError):
        QueueCapacitySpec(
            unit="waiting_room_task_slots", capacity_per_rsu=0, is_queue_not_compute=True
        )
    with pytest.raises(ValidationError):
        QueueCapacitySpec(
            unit="waiting_room_task_slots", capacity_per_rsu="notint", is_queue_not_compute=True
        )  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ComputeCapacitySpec(
            unit="compute_unit",
            min_units=1,
            max_units=3,
            active_units_per_rsu_range=[99],
            is_compute_not_queue=True,
            max_pending_actions=1,
        )
    with pytest.raises(ValidationError):
        ResourceCostSpec(
            metric="resource_unit_seconds",
            formula="bad",
            monetary=False,
            unit="resource_unit_seconds",
            interval_seconds=1,
        )
    with pytest.raises(ValidationError):
        ScalingReceiptSpec(
            has_receipts_when_executed=False, receipts_when_not_executed_null_reason=""
        )
    with pytest.raises(ValidationError):
        ScalingReceiptSpec(
            has_receipts_when_executed=False,
            receipts_when_not_executed_null_reason="kubernetes is live",
        )
    with pytest.raises(ValidationError):
        TaskAccountingSpec(
            unavailable_reasons={
                "started": "reason",
                "compute_completed": "reason",
                "returned": "reason",
                "dropped": "reason",
            },
            conservation_reason="reason",
            genuine_rejection_classes=["wrong"],
        )
    with pytest.raises(ValidationError):
        TaskAccountingSpec(
            unavailable_reasons={
                "started": "UNAVAILABLE reason",
                "compute_completed": "reason",
                "returned": "reason",
                "dropped": "reason",
            },
            conservation_reason="reason",
            genuine_rejection_classes=[
                "v2i_gate_rejected",
                "v2i_cap_rejected",
                "local_mqd_rejected",
                "v2v_mqd_rejected",
                "v2i_unavailable",
                "v2v_unavailable",
            ],
            offered=1,
        )
    with pytest.raises(ValidationError):
        ProvenanceEntry(artifact="a", kind="b", note="/tmp/private")  # noqa: S108
    with pytest.raises(ValidationError):
        ProvenanceEntry(
            artifact="a", kind="b", note="bad sha 0000000000000000000000000000000000000000"
        )


def test_e3_package_cross_swapped_shas_and_unsorted_rejected() -> None:
    """Cross-field consistency only caught by E3ResearchEvidencePackage.validate_cross."""
    # Swapped SHAs: both values are in allowed set, so hex scanner passes, only cross catches misassignment
    data = json.loads(builtin_e3_research_json())
    data["product_base_sha"], data["research_promotion_sha"] = (
        data["research_promotion_sha"],
        data["product_base_sha"],
    )
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    assert "product_base_sha" in str(exc.value).lower() or "mismatch" in str(exc.value).lower()

    # Unsorted dormant_arms: field validators allow any order, only cross enforces sorted
    data2 = json.loads(builtin_e3_research_json())
    data2["dormant_arms"] = list(reversed(data2["dormant_arms"]))
    with pytest.raises((ValidationError, ValueError)) as exc2:
        load_e3_research_evidence_json(json.dumps(data2))
    assert "sorted" in str(exc2.value).lower() or "arm_id" in str(exc2.value).lower()

    # Limitations without NOT_EXECUTED magic words: field validator only checks non-empty/forbidden, cross checks hold mention
    data3 = json.loads(builtin_e3_research_json())
    data3["limitations"] = ["just a generic limitation without the required hold phrases"]
    with pytest.raises((ValidationError, ValueError)) as exc3:
        load_e3_research_evidence_json(json.dumps(data3))
    assert "limitations" in str(exc3.value).lower() or "not_executed" in str(exc3.value).lower()

    # Also via artifact and admission surfaces
    from traffictwin.evidence_admission.e3_research import validate_e3_package_for_admission
    from traffictwin.experiments.e3_research_artifact import validate_e3_research_artifact

    data4 = json.loads(builtin_e3_research_json())
    data4["product_base_sha"], data4["research_promotion_sha"] = (
        data4["research_promotion_sha"],
        data4["product_base_sha"],
    )
    with pytest.raises((ValidationError, ValueError)):
        validate_e3_research_artifact(json.dumps(data4))
    errs = validate_e3_package_for_admission(data4)
    assert len(errs) > 0


def test_hex_validator_consolidated_single_function() -> None:
    import pathlib as _pathlib

    text = _pathlib.Path("src/traffictwin/experiments/e3_research_evidence.py").read_text()
    # Only one hex loop definition should exist (inside _hex_violations_for_string)
    assert text.count("_HEX40_TOKEN_RE.finditer") == 1
    assert text.count("_HEX64_TOKEN_RE.finditer") == 1
    assert text.count("def _hex_violations_for_string") == 1
    # _validate_hex_tokens_in_package should exist but not contain duplicate loop
    assert "def _validate_hex_tokens_in_package" in text
    # provenance validator should call helper, not contain duplicate loop
    assert text.count("provenance approval/promotion SHA mismatch") == 1  # only in helper
    assert (
        text.count("_hex_violations_for_string") >= 4
    )  # helper def + 3 call sites + helper internal


def test_hex_validator_mutation_public_surface() -> None:
    # Through package loader, a bad 40-hex not in allowed should be rejected via hex validator (provenance or scan)
    data = json.loads(builtin_e3_research_json())
    data["provenance"][0]["note"] = "bad sha 0000000000000000000000000000000000000000"
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    assert "provenance" in str(exc.value).lower() or "mismatch" in str(exc.value).lower()


def test_forbidden_detection_mutation_neuter_fails_via_public_loader() -> None:
    # Re-expressed via public loader/semantics surface (was direct private alias test)
    data = json.loads(builtin_e3_research_json())
    data["provenance"][0]["note"] = "kubernetes is here"
    with pytest.raises((ValidationError, ValueError)) as exc:
        load_e3_research_evidence_json(json.dumps(data))
    assert "forbidden" in str(exc.value).lower() or "kubernetes" in str(exc.value).lower()
    # hello world should pass
    data2 = json.loads(builtin_e3_research_json())
    data2["provenance"][0]["note"] = "hello world"
    # Should not raise for benign note (hello world is benign and not forbidden)
    pkg = load_e3_research_evidence_json(json.dumps(data2))
    assert pkg is not None


def test_hex_validator_mutation_neuter_fails_direct() -> None:
    from traffictwin.experiments.e3_research_evidence import _hex_violations_for_string

    violations = _hex_violations_for_string("bad sha 0000000000000000000000000000000000000000", "$")
    assert len(violations) > 0
    violations2 = _hex_violations_for_string(
        f"approved candidate {'c5d66ef7e77f3b7d1f3fde084feea45a83f5c178'}", "$"
    )
    assert len(violations2) == 0


# --- Blocker E: learned pattern ---
def test_learned_claim_rejected_via_strategy_semantics() -> None:
    import dataclasses

    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    for phrase in [
        "learned placement is active",
        "learned scheduler is used",
        "learned scheduler is used",
    ]:
        for field in ["admission", "forwarding", "execution_placement", "human_label"]:
            try:
                dataclasses.replace(canon, **{field: phrase})  # type: ignore[arg-type]
                raise AssertionError(f"expected rejection for learned {phrase!r} in {field}")
            except ValueError as exc:
                assert "forbidden" in str(exc).lower() or "learned" in str(exc).lower()


def test_validate_hex_tokens_in_package_is_load_bearing() -> None:
    from traffictwin.experiments.e3_research_evidence import _validate_hex_tokens_in_package

    # Hex in dict keys is only caught by _validate_hex_tokens_in_package, not by _scan_forbidden_recursive
    violations = _validate_hex_tokens_in_package(
        {"bad_0000000000000000000000000000000000000000": "value"}
    )
    assert len(violations) > 0
    assert any("mismatch" in v.lower() or "provenance" in v.lower() for v in violations)
    # Allowed SHA should not trigger
    from traffictwin.experiments.e3_research_evidence import TRAFFICTWIN_PRODUCT_BASE_SHA

    violations2 = _validate_hex_tokens_in_package({TRAFFICTWIN_PRODUCT_BASE_SHA: "value"})
    # This is a valid SHA, should be allowed (it's in allowed set) - but key contains allowed SHA, so no violation
    # Actually _validate checks if token not in allowed, so allowed should give 0
    assert len(violations2) == 0

    # Also test via package-level string that _validate is used in model_validator: inject bad hex via provenance note prefix?
    # Already covered by loader, but this ensures package scanner works


# Template for new tests - will be appended


def test_lane10_e3c_over_stale_ms_rejected_via_all_surfaces() -> None:
    """Regression for E3cContrastSpec.validate_age_list (survivor at :765) - must fail when neutered to return v."""
    import json

    import pytest
    from pydantic import ValidationError

    from traffictwin.evidence_admission.e3_research import validate_e3_package_for_admission
    from traffictwin.experiments.e3_research_artifact import (
        builtin_e3_research_json,
        validate_e3_research_artifact,
    )
    from traffictwin.experiments.e3_research_evidence import (
        E3cContrastSpec,
        E3cDesign,
        load_e3_research_evidence_json,
    )

    # Direct semantics construction: bad over_stale_ms [999] rejected only by this validator (typing accepts [999])
    with pytest.raises(ValidationError):
        E3cContrastSpec(
            comparison="per_task_dla vs p2c_dla",
            over_stale_ms=[999],
            fixed="x",
            fixed_placement=None,
        )
    with pytest.raises(ValidationError):
        E3cContrastSpec(
            comparison="x", over_stale_ms=[0, 1000], fixed="y", fixed_placement=None
        )  # missing 3000
    with pytest.raises(ValidationError):
        E3cContrastSpec(
            comparison="x", over_stale_ms=[0, 1000, 3000, 3000], fixed="y", fixed_placement=None
        )  # duplicate
    # Valid still passes
    E3cContrastSpec(
        comparison="per_task_dla vs p2c_dla",
        over_stale_ms=[0, 1000, 3000],
        fixed="x",
        fixed_placement=None,
    )
    # Also via E3cDesign
    with pytest.raises(ValidationError):
        E3cDesign(
            stage="E3c",
            contrasts=[
                E3cContrastSpec(
                    comparison="per_task_dla vs p2c_dla",
                    over_stale_ms=[999],
                    fixed="x",
                    fixed_placement=None,
                )
            ],
            state_age_ms_values=[0, 1000, 3000],
            stale_variant_cells_max=32,
            total_contrast_observations=48,
            fresh_observations_reused=16,
            state_is_view_parameter=True,
            reuses_identical_fresh_cells=True,
        )

    # Via package loader - modify staged_design.e3c.contrasts[0].over_stale_ms
    data = json.loads(builtin_e3_research_json())
    data["staged_design"]["e3c"]["contrasts"][0]["over_stale_ms"] = [999]
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    with pytest.raises((ValidationError, ValueError)):
        validate_e3_research_artifact(json.dumps(data))
    errs = validate_e3_package_for_admission(data)
    assert len(errs) > 0


def test_lane10_queue_capacity_int_strict_via_all_surfaces() -> None:
    """Regression for QueueCapacitySpec.validate_int_strict (survivor at :857) - strict int before coercion."""
    import json

    import pytest
    from pydantic import ValidationError

    from traffictwin.evidence_admission.e3_research import validate_e3_package_for_admission
    from traffictwin.experiments.e3_research_artifact import (
        builtin_e3_research_json,
        validate_e3_research_artifact,
    )
    from traffictwin.experiments.e3_research_evidence import (
        QueueCapacitySpec,
        load_e3_research_evidence_json,
    )

    # Direct semantics: True and "5" are only caught by validator (typing would coerce/accept)
    with pytest.raises(ValidationError):
        QueueCapacitySpec(
            unit="waiting_room_task_slots", capacity_per_rsu=True, is_queue_not_compute=True
        )  # bool must be rejected
    with pytest.raises(ValidationError):
        QueueCapacitySpec(
            unit="waiting_room_task_slots", capacity_per_rsu="5", is_queue_not_compute=True
        )  # type: ignore[arg-type]  # string must be rejected before coercion
    with pytest.raises(ValidationError):
        QueueCapacitySpec(
            unit="waiting_room_task_slots", capacity_per_rsu=0, is_queue_not_compute=True
        )
    with pytest.raises(ValidationError):
        QueueCapacitySpec(
            unit="waiting_room_task_slots", capacity_per_rsu=3.5, is_queue_not_compute=True
        )  # type: ignore[arg-type]

    # Valid passes
    QueueCapacitySpec(unit="waiting_room_task_slots", capacity_per_rsu=1, is_queue_not_compute=True)
    QueueCapacitySpec(
        unit="waiting_room_task_slots", capacity_per_rsu=10, is_queue_not_compute=True
    )

    # Via package loader surfaces - use True (bool) and string
    for bad_val in [True, "5"]:
        data = json.loads(builtin_e3_research_json())
        data["queue_capacity"]["capacity_per_rsu"] = bad_val
        with pytest.raises((ValidationError, ValueError)):
            load_e3_research_evidence_json(json.dumps(data))
        with pytest.raises((ValidationError, ValueError)):
            validate_e3_research_artifact(json.dumps(data))
        errs = validate_e3_package_for_admission(data)
        assert len(errs) > 0


def test_lane10_task_accounting_reasons_via_all_surfaces() -> None:
    """Regression for TaskAccountingSpec.validate_reasons (survivor at :950)."""
    import json

    import pytest
    from pydantic import ValidationError

    from traffictwin.evidence_admission.e3_research import validate_e3_package_for_admission
    from traffictwin.experiments.e3_research_artifact import (
        builtin_e3_research_json,
        validate_e3_research_artifact,
    )
    from traffictwin.experiments.e3_research_evidence import (
        REJECTION_CLASSES,
        TaskAccountingSpec,
        load_e3_research_evidence_json,
    )

    base_kwargs = {
        "conservation_reason": "not executed - no workloads launched",
        "genuine_rejection_classes": list(REJECTION_CLASSES),
    }
    # Missing required key
    with pytest.raises(ValidationError):
        TaskAccountingSpec(unavailable_reasons={"started": "r"}, **base_kwargs)  # type: ignore[arg-type]
    # Empty reason
    with pytest.raises(ValidationError):
        TaskAccountingSpec(
            unavailable_reasons={
                "started": "",
                "compute_completed": "r",
                "returned": "r",
                "dropped": "r",
            },
            **base_kwargs,
        )
    # Zero coercion
    with pytest.raises(ValidationError):
        TaskAccountingSpec(
            unavailable_reasons={
                "started": "0",
                "compute_completed": "r",
                "returned": "r",
                "dropped": "r",
            },
            **base_kwargs,
        )
    with pytest.raises(ValidationError):
        TaskAccountingSpec(
            unavailable_reasons={
                "started": "zero",
                "compute_completed": "r",
                "returned": "r",
                "dropped": "r",
            },
            **base_kwargs,
        )
    # Forbidden claim
    with pytest.raises(ValidationError):
        TaskAccountingSpec(
            unavailable_reasons={
                "started": "kubernetes is live",
                "compute_completed": "r",
                "returned": "r",
                "dropped": "r",
            },
            **base_kwargs,
        )

    # Valid passes
    TaskAccountingSpec(
        unavailable_reasons={
            "started": "r1",
            "compute_completed": "r2",
            "returned": "r3",
            "dropped": "r4",
        },
        **base_kwargs,
    )

    # Via package loader
    data = json.loads(builtin_e3_research_json())
    data["task_accounting"]["unavailable_reasons"]["started"] = "0"
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    with pytest.raises((ValidationError, ValueError)):
        validate_e3_research_artifact(json.dumps(data))
    errs = validate_e3_package_for_admission(data)
    assert len(errs) > 0

    data2 = json.loads(builtin_e3_research_json())
    data2["task_accounting"]["unavailable_reasons"] = {"started": "r"}  # missing
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data2))


def test_lane10_task_accounting_nulls_via_all_surfaces() -> None:
    """Regression for TaskAccountingSpec.validate_nulls (survivor at :965) - unexpected key isolates validator from typed None."""
    import json

    import pytest
    from pydantic import ValidationError

    from traffictwin.evidence_admission.e3_research import validate_e3_package_for_admission
    from traffictwin.experiments.e3_research_artifact import (
        builtin_e3_research_json,
        validate_e3_research_artifact,
    )
    from traffictwin.experiments.e3_research_evidence import (
        REJECTION_CLASSES,
        TaskAccountingSpec,
        load_e3_research_evidence_json,
    )

    base_unavailable = {"started": "r", "compute_completed": "r", "returned": "r", "dropped": "r"}
    base_kwargs = {
        "unavailable_reasons": base_unavailable,
        "conservation_reason": "not executed",
        "genuine_rejection_classes": list(REJECTION_CLASSES),
    }
    # Unexpected rejection class key - typing dict[str, None] accepts any string, only validator rejects
    with pytest.raises(ValidationError) as exc:
        TaskAccountingSpec(rejected_by_class={"unexpected_key": None}, **base_kwargs)  # type: ignore[arg-type]
    assert "unexpected" in str(exc.value).lower() or "rejection" in str(exc.value).lower()

    with pytest.raises(ValidationError):
        TaskAccountingSpec(
            rejected_by_class={"v2i_gate_rejected": None, "bogus": None}, **base_kwargs
        )  # type: ignore[arg-type]

    # Valid with None still passes
    TaskAccountingSpec(rejected_by_class=None, **base_kwargs)
    TaskAccountingSpec(rejected_by_class={"v2i_gate_rejected": None}, **base_kwargs)

    # Via package loader - unexpected key in task_accounting.rejected_by_class
    data = json.loads(builtin_e3_research_json())
    # Ensure rejected_by_class exists; if None in shipped json, set to dict with unexpected
    data["task_accounting"]["rejected_by_class"] = {"unexpected_key": None}
    with pytest.raises((ValidationError, ValueError)):
        load_e3_research_evidence_json(json.dumps(data))
    with pytest.raises((ValidationError, ValueError)):
        validate_e3_research_artifact(json.dumps(data))
    errs = validate_e3_package_for_admission(data)
    assert len(errs) > 0
