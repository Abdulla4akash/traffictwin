# ruff: noqa: E501, ANN401
"""Tests for E3 comparison, task accounting, strategy semantics — no-results."""

from __future__ import annotations

import dataclasses
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


# --- Review-2 regression: negation phrasing via E3StrategySemantics (dataclasses.replace) ---


def test_negation_phrasing_rejected_via_strategy_semantics() -> None:
    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    phrases = [
        "there is no doubt kubernetes cluster is live",
        "never in doubt: supervisor approved this",
    ]
    fields = ["admission", "forwarding", "execution_placement"]
    for phrase in phrases:
        for field in fields:
            try:
                dataclasses.replace(canon, **{field: phrase})  # type: ignore[arg-type]
                raise AssertionError(f"expected ValueError for {field} with phrase {phrase!r}")
            except ValueError as exc:
                msg = str(exc).lower()
                assert (
                    "forbidden" in msg
                    or "claim" in msg
                    or "kubernetes" in msg
                    or "supervisor" in msg
                )
            except Exception as exc:  # pragma: no cover
                raise AssertionError(f"wrong exception for {field}: {exc}") from exc


def test_forbidden_families_rejected_via_strategy_semantics() -> None:
    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    families = [
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
    for phrase in families:
        for field in ["admission", "forwarding", "execution_placement"]:
            try:
                dataclasses.replace(canon, **{field: phrase})  # type: ignore[arg-type]
                raise AssertionError(f"expected rejection for {phrase!r} in {field}")
            except ValueError as exc:
                assert "forbidden" in str(exc).lower() or "claim" in str(exc).lower()


def test_unicode_variants_rejected_via_strategy_semantics() -> None:
    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    variants = [
        "kub\u0435rnetes",  # Cyrillic
        "kub\u200bernetes",  # zero-width
        "Ｋｕｂｅｒｎｅｔｅｓ",  # fullwidth
    ]
    for variant in variants:
        payload = f"test {variant} deployment"
        for field in ["admission", "execution_placement", "forwarding"]:
            try:
                dataclasses.replace(canon, **{field: payload})  # type: ignore[arg-type]
                raise AssertionError(f"expected rejection for unicode {variant!r}")
            except ValueError as exc:
                assert "forbidden" in str(exc).lower() or "claim" in str(exc).lower()


def test_allowlist_in_strategy_semantics_still_needs_explicit_check() -> None:
    # Strategy semantics should still reject allowlist+appended (allowlist only exempt in evidence package)
    # But we test that exact allowlist with appended is rejected
    from traffictwin.experiments.e3_research_evidence import ALLOWLISTED_DISCLAIMERS
    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    # allowlisted disclaimer appended with kubernetes should be rejected even in strategy semantics (since strategy uses same forbidden scanner)
    dis = ALLOWLISTED_DISCLAIMERS[0] + " kubernetes"
    for field in ["admission", "forwarding", "execution_placement"]:
        try:
            dataclasses.replace(canon, **{field: dis})  # type: ignore[arg-type]
            raise AssertionError("expected rejection for allowlist+appended in strategy")
        except ValueError:
            pass


def test_strategy_semantics_canonical_import() -> None:
    import pathlib

    text = pathlib.Path("src/traffictwin/experiments/e3_strategy_semantics.py").read_text(
        encoding="utf-8"
    )
    assert "from traffictwin.experiments.e3_research_evidence import" in text
    assert "_scan_forbidden_recursive" in text
    assert "_contains_affirming_forbidden_any" in text
    assert "def _scan_forbidden_recursive" not in text
    assert "def _scan_for_private_paths" not in text
    assert "def _scan_for_true_authorized" not in text


def test_strategy_semantics_neutering_still_fails() -> None:
    from traffictwin.experiments.e3_research_evidence import (
        _contains_affirming_forbidden_any,
        _scan_forbidden_recursive,
    )

    # direct checks that would fail if neutered
    assert _contains_affirming_forbidden_any("kubernetes") is not None
    assert _scan_forbidden_recursive({"a": "kubernetes"}) != []
    # also via strategy semantics construction with clean data should still pass
    from traffictwin.experiments.e3_strategy_semantics import e3_semantics_for

    sem = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    assert sem.placement_id == "per_task_dla"
    # and that a forbidden via strategy still raises
    try:
        dataclasses.replace(sem, **{"admission": "kubernetes is live"})  # type: ignore[arg-type]
        raise AssertionError("should have raised")
    except ValueError:
        pass


# --- Test gap: E3StrategySemantics constructor regressions ---
def test_strategy_semantics_constructor_regressions_hostile_fields() -> None:
    """Hostile text in admission, forwarding, execution_placement, human_label each rejected; all eight canonical still construct."""
    import dataclasses

    from traffictwin.experiments.e3_strategy_semantics import (
        E3StrategySemantics,
        e3_semantics_for,
        e3_strategy_semantics,
    )

    # All eight canonical instances still construct
    all_sems = e3_strategy_semantics()
    assert len(all_sems) == 8
    for sem in all_sems:
        assert sem.is_learned is False
        assert sem.is_deterministic is True

    # Hostile texts: family claims, confusable variants, negation phrasings
    hostile_texts = [
        "kubernetes cluster is live is true",  # family
        "supervisor approved this deployment",  # family
        "universally superior is proven",  # family
        "tasks as n is valid",  # family
        "manchester-wide inference is valid",  # family
        "monetary cost is low dollars",  # family
        "actor selects execution rsu is true",  # family
        "queue ceiling is compute is true",  # family
        "learned placement is active",  # learned
        "kub\u0435rnetes cluster",  # confusable Cyrillic
        "kub\u200bernetes deployment",  # zero-width
        "\uff2b\uff55\uff42\uff45\uff52\uff4e\uff45\uff54\uff45\uff53 cluster",  # fullwidth
        "there is no doubt kubernetes cluster is live",  # negation
        "never in doubt: supervisor approved this",  # negation
        "kuber\u2c81etes coptic",  # backstop Coptic
    ]
    fields = ["admission", "forwarding", "execution_placement", "human_label"]
    canon = e3_semantics_for("per_task_dla", "fixed_1x", 0)
    for hostile in hostile_texts:
        for field in fields:
            try:
                dataclasses.replace(canon, **{field: hostile})  # type: ignore[arg-type]
                raise AssertionError(f"expected rejection for hostile {hostile!r} in field {field}")
            except ValueError as exc:
                msg = str(exc).lower()
                assert (
                    "forbidden" in msg
                    or "mixed_script" in msg
                    or "claim" in msg
                    or "learned" in msg
                )

    # Also test direct constructor with hostile text should reject
    base_kwargs = {
        "placement_id": "per_task_dla",
        "scaling_id": "fixed_1x",
        "state_age_ms": 0,
        "human_label": "test human label that is long enough for validation and mentions queue vs compute properly and resource_unit_seconds and evidence state NOT_EXECUTED and more text to exceed ten chars",
        "radio_ingress": "test radio_ingress that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state and more words to be substantive length",
        "execution_placement": "test execution_placement that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state",
        "admission": "test admission that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state",
        "forwarding": "test forwarding that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state",
        "actor_authority": "test actor_authority that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state",
        "infrastructure_authority": "test infrastructure_authority that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state",
        "scaling_semantics": "test scaling_semantics that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state",
        "staleness_semantics": "test staleness_semantics that is long enough and mentions resource_unit_seconds and queue waiting and compute and is deterministic and mentions NOT_EXECUTED hold state",
        "queue_capacity_note": "Queue capacity is waiting-room tasks per RSU, strictly separate from compute service capacity, queue waiting",
        "compute_capacity_note": "Compute capacity is active units 1..3 per RSU, each drains 1000 work_ms per second",
        "resource_cost_note": "Resource cost is resource_unit_seconds = sum over RSU sum over interval active_units * interval_seconds, normalized usage not money, measured in resource_unit_seconds only.",
        "is_learned": False,
        "is_deterministic": True,
        "evidence_level": "IMPLEMENTATION-VERIFIED FACT NOT_EXECUTED NO_E3_RESEARCH_RESULTS_AVAILABLE and more text to be substantive",
        "limitations": "Bounded to staged design E3a; no E3 results. Tasks are accounting records, not replicates; waiting-room ceiling 6220 and compute service capacity separate and resource_unit_seconds and evidence state NOT_EXECUTED and more text to be substantive length.",
    }
    # Direct constructor with hostile human_label should reject
    try:
        E3StrategySemantics(
            **{
                **base_kwargs,
                "human_label": "kubernetes cluster is live is true and long enough to pass length but should be rejected for forbidden claim and also mentions queue waiting compute resource_unit_seconds and NOT_EXECUTED and more text to be substantive",
            }
        )
        raise AssertionError("expected rejection for direct constructor hostile human_label")
    except ValueError:
        pass
    # Direct constructor with clean should succeed
    clean = E3StrategySemantics(**base_kwargs)
    assert clean.placement_id == "per_task_dla"


def test_strategy_semantics_all_eight_canonical_still_construct() -> None:
    from traffictwin.experiments.e3_strategy_semantics import e3_strategy_semantics

    all_sems = e3_strategy_semantics()
    assert len(all_sems) == 8
    # Check that each placement/scaling/age triple is unique and valid
    seen = set()
    for sem in all_sems:
        key = (sem.placement_id, sem.scaling_id, sem.state_age_ms)
        assert key not in seen
        seen.add(key)
        # Each should have substantive fields
        assert len(sem.human_label) > 10
        assert "resource_unit_seconds" in sem.resource_cost_note.lower()
