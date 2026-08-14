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
    from traffictwin.experiments.e3_research_evidence import _scan_for_private_paths

    deep = {"a": {"b": {"c": "/tmp/direct_private"}}}  # noqa: S108
    violations = _scan_for_private_paths(deep)
    assert any("private path" in v.lower() for v in violations)
    # Secret via password keyword (no assignment) should be caught only by this scan
    deep_secret = {"x": {"y": "my password is foo"}}
    violations2 = _scan_for_private_paths(deep_secret)
    assert any("secret" in v.lower() for v in violations2)


def test_scan_for_true_authorized_direct() -> None:
    from traffictwin.experiments.e3_research_evidence import _scan_for_true_authorized

    deep_true = {"a": {"b": {"my_authorized": True}}}
    violations = _scan_for_true_authorized(deep_true)
    assert any("_authorized" in v.lower() for v in violations)
    # Non-bool authorized should also be caught only by this scan
    deep_nobool = {"a": {"b": {"other_authorized": "yes"}}}
    violations2 = _scan_for_true_authorized(deep_nobool)
    assert any("_authorized" in v.lower() for v in violations2)


def test_assert_no_private_paths_direct() -> None:
    from traffictwin.experiments.e3_research_artifact import _assert_no_private_paths_or_secrets

    with pytest.raises((ValidationError, ValueError)):
        _assert_no_private_paths_or_secrets("prefix /tmp/private is here")
    with pytest.raises((ValidationError, ValueError)):
        _assert_no_private_paths_or_secrets("api_key: secret123")
