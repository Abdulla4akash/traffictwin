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
