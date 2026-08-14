# ruff: noqa: E501, ANN401
"""Tests for E3 comparison, task accounting, strategy semantics — no-results."""

from __future__ import annotations

import json

from traffictwin.experiments.e3_comparison import build_e3_comparison_view
from traffictwin.experiments.e3_research_artifact import load_builtin_e3_research
from traffictwin.experiments.e3_research_evidence import (
    LANE_09,
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
    NOT_EXECUTED,
)
from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for, e3_strategy_semantics
from traffictwin.experiments.e3_task_accounting import build_e3_task_accounting_view


def _pkg() -> object:
    return load_builtin_e3_research()


def test_e3_comparison_view_is_no_results_typed() -> None:
    pkg = _pkg()
    view = build_e3_comparison_view(pkg)
    assert view.lane_09 == LANE_09
    assert view.e3a.replication_unit == "fleet_draw"
    assert view.e3a.n_fleet_draws == 4
    assert view.e3a.fleet_seeds == (1, 2, 3, 4)
    assert view.e3a.evaluator_seed == 0
    assert view.e3a.degrees_of_freedom == 3
    assert 3.18 < view.e3a.critical_value < 3.19  # type: ignore[attr-defined]
    assert "Student-t" in view.e3a.method
    assert view.e3a.tasks_are_not_replicates is True
    assert view.e3a.manchester_wide_inference_forbidden is True
    assert view.e3a.universal_superiority_forbidden is True
    assert view.e3a.evidence_state == NOT_EXECUTED
    assert view.e3a.result_availability == NO_E3_RESEARCH_RESULTS_AVAILABLE
    # paired differences are unavailable
    for pd in view.e3a.paired_differences:
        assert pd.per_seed_values is None
        assert pd.mean is None
        assert "NO_E3_RESEARCH_RESULTS_AVAILABLE" in pd.unavailable_reason
        assert pd.replication_unit == "fleet_draw"
        assert pd.n == 4
    # E3b and E3c similarly
    assert view.e3b.n_fleet_draws == 4  # type: ignore[attr-defined]
    assert view.e3c.n_fleet_draws == 4  # type: ignore[attr-defined]
    for pd in view.e3b.paired_differences:
        assert pd.per_seed_values is None
    for pd in view.e3c.paired_differences:
        assert pd.per_seed_values is None


def test_e3_comparison_estimands_match_staged_design() -> None:
    pkg = _pkg()
    view = build_e3_comparison_view(pkg)
    # E3a has p2c vs per_task primary
    estimands_e3a = [e.estimand for e in view.e3a.estimands]
    assert any("p2c_dla" in s and "per_task_dla" in s for s in estimands_e3a)
    # E3b has 4 scalers
    assert len(view.e3b.estimands) >= 4  # type: ignore[attr-defined]
    # E3c has staleness
    assert any("reactive" in e.estimand and "proactive" in e.estimand for e in view.e3c.estimands)


def test_task_accounting_view_null_with_reasons() -> None:
    view = build_e3_task_accounting_view()
    assert view.evidence_state == NOT_EXECUTED
    assert view.result_availability == NO_E3_RESEARCH_RESULTS_AVAILABLE
    assert view.research_workloads_launched == 0
    assert view.offered is None
    assert view.admitted is None
    assert view.rejected_total is None
    assert view.forwarded is None
    assert view.deadline_success is None
    assert view.started is None
    assert view.compute_completed is None
    assert view.returned is None
    assert view.dropped is None
    assert "UNAVAILABLE" in view.offered_reason
    assert "UNAVAILABLE" in view.started_reason
    # queue vs compute separation
    assert view.queue_vs_compute.is_separate is True
    assert view.queue_vs_compute.queue_is_not_compute is True
    assert view.resource_cost.metric == "resource_unit_seconds"
    assert view.resource_cost.monetary is False
    assert view.resource_cost.value is None
    # genuine classes
    assert set(view.genuine_rejection_classes) == {
        "v2i_gate_rejected",
        "v2i_cap_rejected",
        "local_mqd_rejected",
        "v2v_mqd_rejected",
        "v2i_unavailable",
        "v2v_unavailable",
    }
    # unavailable map
    assert "started" in view.unavailable
    assert "UNAVAILABLE" in view.unavailable["started"].reason
    # scaling receipts null
    assert view.scaling_receipts.receipts is None
    assert "UNAVAILABLE" in view.scaling_receipts.reason


def test_strategy_semantics_typed_and_queue_compute_distinct() -> None:
    sems = e3_strategy_semantics()
    assert len(sems) >= 6
    for sem in sems:
        assert sem.placement_id in ("ingress_dla", "per_task_dla", "p2c_dla")
        assert sem.scaling_id in ("fixed_1x", "static_overprovisioned", "reactive", "proactive")
        assert type(sem.state_age_ms) is int
        assert sem.state_age_ms in (0, 1000, 3000)
        assert sem.is_learned is False
        assert sem.is_deterministic is True
        assert "resource_unit_seconds" in sem.resource_cost_note.lower()
        assert (
            "queue" in sem.queue_capacity_note.lower()
            or "waiting" in sem.queue_capacity_note.lower()
        )
        assert "compute" in sem.compute_capacity_note.lower()
        # queue vs compute not conflated
        assert "queue ceiling is compute" not in sem.queue_capacity_note.lower()
        assert (
            "kubernetes" not in sem.infrastructure_authority.lower()
            or "not" in sem.infrastructure_authority.lower()
        )
        # evidence level mentions hold
        assert (
            NOT_EXECUTED in sem.evidence_level
            or NO_E3_RESEARCH_RESULTS_AVAILABLE in sem.evidence_level
        )


def test_strategy_lookup_exact() -> None:
    sem = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    assert sem.placement_id == "per_task_dla"
    assert sem.scaling_id == "fixed_1x"
    assert sem.state_age_ms == 0
    # stale variant
    sem2 = e3_semantics_for("per_task_dla", "fixed_1x", 1000)
    assert sem2.state_age_ms == 1000
    assert "1000" in sem2.human_label


def test_resource_cost_is_not_money() -> None:
    pkg = _pkg()
    assert pkg.resource_cost.metric == "resource_unit_seconds"
    assert pkg.resource_cost.monetary is False
    # non_claims must mention resource_unit_seconds and not money
    joined = " ".join(pkg.non_claims).lower()
    assert "resource_unit_seconds" in joined
    # Should not contain affirming monetary claim
    assert "cost dollars is true" not in joined


def test_provenance_limitations_missingness_first_class() -> None:
    pkg = _pkg()
    assert len(pkg.provenance) >= 1
    assert len(pkg.limitations) >= 1
    assert len(pkg.missingness) >= 1
    assert any("NO_E3_RESEARCH_RESULTS_AVAILABLE" in s for s in pkg.limitations)
    assert any("fleet_draw" in s.lower() for s in pkg.non_claims)


def test_no_tasks_as_n_in_comparison() -> None:
    pkg = _pkg()
    view = build_e3_comparison_view(pkg)
    dumped = json.dumps(view.model_dump(mode="json")).lower()
    # Should not claim tasks as N affirmatively
    assert "task as n is true" not in dumped
    # Should contain tasks_are_not_replicates true
    assert view.e3a.tasks_are_not_replicates is True  # type: ignore[attr-defined]


def test_e3a_b_c_stage_counts_match_package() -> None:
    pkg = _pkg()
    _ = build_e3_comparison_view(pkg)
    assert pkg.staged_design.e3a.stage_listed_cells == 12
    assert pkg.staged_design.e3b.stage_listed_cells == 16  # type: ignore[union-attr]
    assert pkg.staged_design.e3c.stale_variant_cells_max == 32
    # comparison view should reflect same dormancy
    assert pkg.staged_design.maximum_candidate_unique_cells == 56
