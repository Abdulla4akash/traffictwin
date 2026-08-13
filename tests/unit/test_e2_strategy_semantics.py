"""Unit tests for Lane 05 strategy semantics service.

Validates the happy path for the five declared strategies and that hard
mutation guards reject: common-target DLA as canonical per-task JSQ,
MAPPO execution-RSU credit or current load observation, learned deterministic
placement, and managed-cluster deployment claims.
"""

from __future__ import annotations

import dataclasses

import pytest

from traffictwin.experiments.e2_strategy_semantics import (
    E2StrategySemantics,
    e2_strategy_semantics,
)


def test_declared_api_returns_five_in_order() -> None:
    strategies = e2_strategy_semantics()
    assert isinstance(strategies, tuple)
    assert len(strategies) == 5
    assert [s.strategy_id for s in strategies] == [
        "off",
        "jsq",
        "ingress_dla",
        "dla",
        "per_task_dla",
    ]
    # Frozen dataclass.
    for s in strategies:
        assert isinstance(s, E2StrategySemantics)
        assert s.is_deterministic is True
        assert s.is_learned is False


def test_each_covers_required_dimensions() -> None:
    for s in e2_strategy_semantics():
        # Radio ingress
        assert "strongest-link" in s.radio_ingress.lower() or "best_rsu" in s.radio_ingress.lower()
        # Execution placement
        assert len(s.execution_placement) > 30
        # Admission
        assert len(s.admission) > 30
        # Forwarding
        assert len(s.forwarding) > 30
        # Actor / infrastructure authority
        assert "mappo" in s.actor_authority.lower()
        assert "does not" in s.actor_authority.lower() or "has no" in s.actor_authority.lower()
        assert len(s.infrastructure_authority) > 20
        # Evidence and limitations
        assert len(s.evidence_level) > 20
        assert len(s.limitations) > 20


def test_off_is_strongest_link_no_load_balancing() -> None:
    off = next(s for s in e2_strategy_semantics() if s.strategy_id == "off")
    assert (
        "no jsq" in off.execution_placement.lower() or "no load" in off.execution_placement.lower()
    )
    assert (
        "no deadline-aware gate" in off.admission.lower() or "no deadline" in off.admission.lower()
    )
    assert "never" in off.forwarding.lower() or off.forwarding.lower().count("0.0") >= 1
    # Actor does not select RSU / observe load
    assert "does not select" in off.actor_authority.lower()
    assert (
        "does not observe" in off.actor_authority.lower()
        or "no current" in off.actor_authority.lower()
    )


def test_jsq_is_least_busy_common_target_without_gate() -> None:
    jsq = next(s for s in e2_strategy_semantics() if s.strategy_id == "jsq")
    low = jsq.execution_placement.lower()
    assert "argmin" in low or "least-busy" in low
    assert "common target" in low
    assert (
        "not sequential per-task" in low
        or "not task-count" in low
        or "not canonical" in low
        or "common-target per substep" in low
    )
    # No gate
    assert "no" in jsq.admission.lower() and "gate" in jsq.admission.lower()


def test_ingress_dla_is_strongest_link_with_gate_no_placement() -> None:
    ingress = next(s for s in e2_strategy_semantics() if s.strategy_id == "ingress_dla")
    assert "strongest-link execution" in ingress.execution_placement.lower()
    assert (
        "no argmin" in ingress.execution_placement.lower()
        or "no load" in ingress.execution_placement.lower()
    )
    assert "effective_busy_ms" in ingress.admission
    assert "forward" in ingress.forwarding.lower() and "never" in ingress.forwarding.lower()


def test_dla_is_common_target_per_substep_not_per_task_jsq() -> None:
    dla = next(s for s in e2_strategy_semantics() if s.strategy_id == "dla")
    low = dla.execution_placement.lower()
    assert "common-target" in low
    assert "per substep" in low
    # Must explicitly distinguish from sequential per-task JSQ
    assert (
        "not sequential per-task" in low
        or "not sequential per-task" in low
        or "not canonical" in low
        or "not sequential" in low
    )
    # Admission has gate
    assert "effective_busy_ms" in dla.admission
    # Forwarding shows concentration
    assert "forward" in dla.forwarding.lower()


def test_per_task_dla_is_sequential_per_task_with_reservation() -> None:
    ptd = next(s for s in e2_strategy_semantics() if s.strategy_id == "per_task_dla")
    low = ptd.execution_placement.lower()
    assert "per-task" in low and "recompute" in low
    assert "argmin" in low
    assert "lowest rsu index" in low
    assert "immediate" in ptd.admission.lower() or "immediately" in ptd.admission.lower()
    assert "effective_busy_ms" in ptd.admission


def test_actor_never_credited_with_rsu_selection_or_load_observation() -> None:
    for s in e2_strategy_semantics():
        actor_low = s.actor_authority.lower()
        # Honest strings must say actor does NOT select / does NOT observe.
        assert "does not select" in actor_low or "has no" in actor_low or "not select" in actor_low
        assert "does not observe" in actor_low or "no current" in actor_low or "has no" in actor_low
        # No affirmative MAPPO selects
        assert "mappo selects execution" not in actor_low
        assert "mappo observes current load" not in actor_low


def test_deterministic_not_learned() -> None:
    for s in e2_strategy_semantics():
        assert s.is_deterministic is True
        assert s.is_learned is False
        combined = (
            s.execution_placement + " " + s.infrastructure_authority + " " + s.actor_authority
        ).lower()
        # Must not affirm learned placement
        assert "learned placement" not in combined or "not learned" in combined


def test_no_kubernetes_deployment_claim() -> None:
    for s in e2_strategy_semantics():
        combined = (
            s.execution_placement + " " + s.infrastructure_authority + " " + s.limitations
        ).lower()
        # Affirmative deployment/orchestration must be absent; negated is
        # allowed via validator logic,
        # but honest strings should not affirm deployment.
        assert "kubernetes deployment" not in combined or "not " in combined or "no " in combined
        # Optionally inspired phrase is allowed; actual deployment must be denied.
        if "kubernetes" in combined:
            # If kubernetes appears, it must be in "kubernetes-inspired" context, not deployment.
            assert "kubernetes-inspired" in combined


def test_frozen_no_mutation() -> None:
    s = e2_strategy_semantics()[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.strategy_id = "jsq"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Mutation guards — each must be rejected by validation.
# ---------------------------------------------------------------------------


def test_mutant_rejects_common_target_as_canonical_per_task_jsq() -> None:
    dla = next(s for s in e2_strategy_semantics() if s.strategy_id == "dla")
    with pytest.raises(ValueError, match="canonical"):
        E2StrategySemantics(
            strategy_id=dla.strategy_id,
            human_label=dla.human_label,
            radio_ingress=dla.radio_ingress,
            execution_placement="Canonical per-task JSQ selects execution RSU each task",
            admission=dla.admission,
            forwarding=dla.forwarding,
            actor_authority=dla.actor_authority,
            infrastructure_authority=dla.infrastructure_authority,
            is_learned=dla.is_learned,
            is_deterministic=dla.is_deterministic,
            evidence_level=dla.evidence_level,
            limitations=dla.limitations,
        )


def test_mutant_rejects_mappo_execution_rsu_credit() -> None:
    jsq = next(s for s in e2_strategy_semantics() if s.strategy_id == "jsq")
    with pytest.raises(ValueError, match="actor-RSU|mappo selects|forbidden"):
        E2StrategySemantics(
            strategy_id=jsq.strategy_id,
            human_label=jsq.human_label,
            radio_ingress=jsq.radio_ingress,
            execution_placement=jsq.execution_placement,
            admission=jsq.admission,
            forwarding=jsq.forwarding,
            actor_authority=(
                "MAPPO selects execution RSU and observes current RSU load to choose target"
            ),
            infrastructure_authority=jsq.infrastructure_authority,
            is_learned=jsq.is_learned,
            is_deterministic=jsq.is_deterministic,
            evidence_level=jsq.evidence_level,
            limitations=jsq.limitations,
        )


def test_mutant_rejects_mappo_current_load_observation() -> None:
    off = next(s for s in e2_strategy_semantics() if s.strategy_id == "off")
    with pytest.raises(ValueError, match="observes|actor-RSU"):
        E2StrategySemantics(
            strategy_id=off.strategy_id,
            human_label=off.human_label,
            radio_ingress=off.radio_ingress,
            execution_placement=off.execution_placement,
            admission=off.admission,
            forwarding=off.forwarding,
            actor_authority="Frozen MAPPO observes current load to select RSU",
            infrastructure_authority=off.infrastructure_authority,
            is_learned=off.is_learned,
            is_deterministic=off.is_deterministic,
            evidence_level=off.evidence_level,
            limitations=off.limitations,
        )


def test_mutant_rejects_deterministic_as_learned_flag() -> None:
    ingress = next(s for s in e2_strategy_semantics() if s.strategy_id == "ingress_dla")
    with pytest.raises(ValueError, match="is_learned|learned"):
        E2StrategySemantics(
            strategy_id=ingress.strategy_id,
            human_label=ingress.human_label,
            radio_ingress=ingress.radio_ingress,
            execution_placement=ingress.execution_placement,
            admission=ingress.admission,
            forwarding=ingress.forwarding,
            actor_authority=ingress.actor_authority,
            infrastructure_authority=ingress.infrastructure_authority,
            is_learned=True,
            is_deterministic=True,
            evidence_level=ingress.evidence_level,
            limitations=ingress.limitations,
        )


def test_mutant_rejects_learned_placement_phrase() -> None:
    ptd = next(s for s in e2_strategy_semantics() if s.strategy_id == "per_task_dla")
    with pytest.raises(ValueError, match="learned"):
        E2StrategySemantics(
            strategy_id=ptd.strategy_id,
            human_label=ptd.human_label,
            radio_ingress=ptd.radio_ingress,
            execution_placement="Learned placement selects least-busy RSU via trained scheduler",
            admission=ptd.admission,
            forwarding=ptd.forwarding,
            actor_authority=ptd.actor_authority,
            infrastructure_authority=ptd.infrastructure_authority,
            is_learned=ptd.is_learned,
            is_deterministic=ptd.is_deterministic,
            evidence_level=ptd.evidence_level,
            limitations=ptd.limitations,
        )


def test_mutant_rejects_kubernetes_deployment_description() -> None:
    dla = next(s for s in e2_strategy_semantics() if s.strategy_id == "dla")
    with pytest.raises(ValueError, match="kubernetes deployment|cluster orchestration"):
        E2StrategySemantics(
            strategy_id=dla.strategy_id,
            human_label=dla.human_label,
            radio_ingress=dla.radio_ingress,
            execution_placement=dla.execution_placement,
            admission=dla.admission,
            forwarding=dla.forwarding,
            actor_authority=dla.actor_authority,
            infrastructure_authority=(
                "Infrastructure performs Kubernetes deployment and cluster "
                "orchestration to scale RSUs"
            ),
            is_learned=dla.is_learned,
            is_deterministic=dla.is_deterministic,
            evidence_level=dla.evidence_level,
            limitations=dla.limitations,
        )


def test_mutant_rejects_cluster_orchestration() -> None:
    ptd = next(s for s in e2_strategy_semantics() if s.strategy_id == "per_task_dla")
    with pytest.raises(ValueError, match="cluster orchestration"):
        E2StrategySemantics(
            strategy_id=ptd.strategy_id,
            human_label=ptd.human_label,
            radio_ingress=ptd.radio_ingress,
            execution_placement=ptd.execution_placement,
            admission=ptd.admission,
            forwarding=ptd.forwarding,
            actor_authority=ptd.actor_authority,
            infrastructure_authority="Kubernetes cluster orchestration manages RSU placement",
            is_learned=ptd.is_learned,
            is_deterministic=ptd.is_deterministic,
            evidence_level=ptd.evidence_level,
            limitations=ptd.limitations,
        )
