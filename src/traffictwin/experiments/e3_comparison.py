# ruff: noqa: E501, ANN401
"""Matched-draw uncertainty service for E3a / E3b / E3c — no results.

Strict typed view built directly from the admitted E3ResearchEvidencePackage in
NOT_EXECUTED state. No optional package, no Any, no guessed shapes. Any
inconsistent, missing, or drifted identity, seed, or replication value fails
closed with an exception.

Replication unit is fleet_draw, fleet_seeds 1-4, evaluator_seed 0, N=4. Paired
differences use bounded E2-compatible 95% Student-t interval (df=3, t=3.182).
Tasks are never N, Manchester-wide inference never, universal superiority never.
All per-draw values are unavailable with reasons while hold is active.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.experiments.e3_research_evidence import (
    E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED,
    LANE_09,
    NO_E3_RESEARCH_RESULTS_AVAILABLE,
    NOT_EXECUTED,
    E3ResearchEvidencePackage,
)

ACTOR_SHA256: str = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
TRACE_SHA256: str = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
CONTRACT_SHA256: str = "f0d6eb913df6c2165a63ddcb0fd4980368e9bb80bbd38db964273ba3925f4870"

EVALUATOR_SEED: Literal[0] = 0
REPLICATION_UNIT: Literal["fleet_draw"] = "fleet_draw"
FLEET_SEEDS: tuple[int, int, int, int] = (1, 2, 3, 4)
N_FLEET_DRAWS: Literal[4] = 4
DEGREES_OF_FREEDOM: Literal[3] = 3
CRITICAL_T_95_DF3: float = 3.182446305284263
METHOD: str = "two-sided Student-t 95% interval over fleet-draw differences (df=3, t=3.182)"

SCENARIO: str = "Manchester incident hour 2024-03-15 20:00-21:00 Europe/London, provisional uk2030 fleet, 10 RSUs, 3600 ticks (dormant)"

# Bounded decision labels compatible with E2
DECISION_BELOW: str = "directional_deficit_for_treatment_within_bounded_draws"
DECISION_ABOVE: str = "directional_advantage_for_treatment_within_bounded_draws"
DECISION_INCONCLUSIVE: str = "inconclusive_at_this_replication_size"


def _check_package_hold(pkg: E3ResearchEvidencePackage) -> None:
    if pkg.evidence_state != NOT_EXECUTED:
        raise ValueError(f"evidence_state must be {NOT_EXECUTED}, got {pkg.evidence_state!r}")
    if pkg.result_availability != NO_E3_RESEARCH_RESULTS_AVAILABLE:
        raise ValueError(
            f"result_availability must be {NO_E3_RESEARCH_RESULTS_AVAILABLE}, got {pkg.result_availability!r}"
        )
    if pkg.research_workloads_launched != 0:
        raise ValueError("research_workloads_launched must be 0")
    if pkg.lane_09 != LANE_09:
        raise ValueError(f"lane_09 must be {LANE_09}, got {pkg.lane_09!r}")
    if pkg.status != E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED:
        raise ValueError(
            f"status must be {E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, got {pkg.status!r}"
        )
    if pkg.replication.replication_unit != REPLICATION_UNIT:
        raise ValueError(
            f"replication_unit must be {REPLICATION_UNIT}, got {pkg.replication.replication_unit!r}"
        )
    if pkg.replication.n != N_FLEET_DRAWS:
        raise ValueError(f"replication n must be {N_FLEET_DRAWS}, got {pkg.replication.n!r}")
    if tuple(pkg.replication.fleet_seeds) != FLEET_SEEDS:
        raise ValueError(f"fleet_seeds must be {FLEET_SEEDS}, got {pkg.replication.fleet_seeds!r}")
    if pkg.replication.evaluator_seed != EVALUATOR_SEED:
        raise ValueError(
            f"evaluator_seed must be {EVALUATOR_SEED}, got {pkg.replication.evaluator_seed!r}"
        )


class EstimandSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    estimand: str = Field(min_length=1)
    treatment: str = Field(min_length=1)
    control: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    state_age_ms: int | None = Field(default=None)


class PairedDifferenceUnavailable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_id: str = Field(min_length=1)
    replication_unit: Literal["fleet_draw"] = REPLICATION_UNIT
    fleet_seeds: tuple[int, int, int, int] = FLEET_SEEDS
    evaluator_seed: Literal[0] = EVALUATOR_SEED
    n: Literal[4] = N_FLEET_DRAWS
    per_seed_values: None = Field(default=None)
    unavailable_reason: str = Field(min_length=1)
    method: str = Field(default=METHOD)
    degrees_of_freedom: Literal[3] = DEGREES_OF_FREEDOM
    critical_value: float = Field(default=CRITICAL_T_95_DF3)
    mean: None = Field(default=None)
    lower: None = Field(default=None)
    upper: None = Field(default=None)
    includes_zero: None = Field(default=None)
    decision: None = Field(default=None)


class NoResultsComparisonView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: str = Field(min_length=1)
    replication_unit: Literal["fleet_draw"] = REPLICATION_UNIT
    n_fleet_draws: Literal[4] = N_FLEET_DRAWS
    fleet_seeds: tuple[int, int, int, int] = FLEET_SEEDS
    evaluator_seed: Literal[0] = EVALUATOR_SEED
    method: str = Field(default=METHOD)
    degrees_of_freedom: Literal[3] = DEGREES_OF_FREEDOM
    critical_value: float = Field(default=CRITICAL_T_95_DF3)
    estimands: list[EstimandSpec] = Field(min_length=1)
    paired_differences: list[PairedDifferenceUnavailable] = Field(min_length=1)
    tasks_are_not_replicates: Literal[True] = True
    manchester_wide_inference_forbidden: Literal[True] = True
    universal_superiority_forbidden: Literal[True] = True
    evidence_state: Literal["NOT_EXECUTED"] = NOT_EXECUTED
    result_availability: Literal["NO_E3_RESEARCH_RESULTS_AVAILABLE"] = (
        NO_E3_RESEARCH_RESULTS_AVAILABLE
    )
    unavailable_reason: str = Field(min_length=1)


class E3ResearchComparisonView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    e3a: NoResultsComparisonView
    e3b: NoResultsComparisonView
    e3c: NoResultsComparisonView
    lane_09: Literal["BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"] = LANE_09
    status: Literal["E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"] = (
        E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
    )
    scenario: str = Field(default=SCENARIO)


def build_e3_comparison_view(pkg: E3ResearchEvidencePackage) -> E3ResearchComparisonView:
    """Build the typed no-results comparison view from the admitted package."""
    _check_package_hold(pkg)

    # Verify staged designs are exact (already validated in package, but re-check identity)
    if pkg.staged_design.e3a.stage != "E3a":
        raise ValueError("staged_design e3a must be E3a")
    if pkg.staged_design.e3b.stage != "E3b":
        raise ValueError("staged_design e3b must be E3b")
    if pkg.staged_design.e3c.stage != "E3c":
        raise ValueError("staged_design e3c must be E3c")

    # Common unavailable reason
    base_reason = (
        f"{NO_E3_RESEARCH_RESULTS_AVAILABLE}: research_workloads_launched = 0, "
        f"evidence_state = {NOT_EXECUTED}, {E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED}, "
        f"{LANE_09}. Paired differences are null with reasons; never tasks_as_N."
    )

    e3a_estimands = [
        EstimandSpec(
            estimand="p2c_dla minus per_task_dla offered deadline attainment at fixed_1x stale=0",
            treatment="p2c_dla",
            control="per_task_dla",
            metric="offered deadline attainment",
            state_age_ms=0,
        ),
        EstimandSpec(
            estimand="p2c_dla minus ingress_dla offered deadline attainment at fixed_1x stale=0 (secondary)",
            treatment="p2c_dla",
            control="ingress_dla",
            metric="offered deadline attainment",
            state_age_ms=0,
        ),
    ]
    e3a_paired = [
        PairedDifferenceUnavailable(
            comparison_id="E3a_p2c_dla-minus-per_task_dla__fixed_1x__age_0ms",
            unavailable_reason=base_reason + " E3a primary not yet executed.",
        ),
        PairedDifferenceUnavailable(
            comparison_id="E3a_p2c_dla-minus-ingress_dla__fixed_1x__age_0ms",
            unavailable_reason=base_reason + " E3a secondary not yet executed.",
        ),
    ]

    e3b_estimands = [
        EstimandSpec(
            estimand="static_overprovisioned minus fixed_1x offered deadline attainment at per_task_dla stale=0",
            treatment="static_overprovisioned",
            control="fixed_1x",
            metric="offered deadline attainment",
            state_age_ms=0,
        ),
        EstimandSpec(
            estimand="reactive minus fixed_1x offered deadline attainment at per_task_dla stale=0",
            treatment="reactive",
            control="fixed_1x",
            metric="offered deadline attainment",
            state_age_ms=0,
        ),
        EstimandSpec(
            estimand="proactive minus fixed_1x offered deadline attainment at per_task_dla stale=0",
            treatment="proactive",
            control="fixed_1x",
            metric="offered deadline attainment",
            state_age_ms=0,
        ),
        EstimandSpec(
            estimand="static_overprovisioned minus fixed_1x rejection_share at per_task_dla stale=0",
            treatment="static_overprovisioned",
            control="fixed_1x",
            metric="rejection_share",
            state_age_ms=0,
        ),
        EstimandSpec(
            estimand="reactive minus fixed_1x rejection_share at per_task_dla stale=0",
            treatment="reactive",
            control="fixed_1x",
            metric="rejection_share",
            state_age_ms=0,
        ),
        EstimandSpec(
            estimand="proactive minus fixed_1x resource_unit_seconds at per_task_dla stale=0",
            treatment="proactive",
            control="fixed_1x",
            metric="resource_unit_seconds",
            state_age_ms=0,
        ),
    ]
    e3b_paired = [
        PairedDifferenceUnavailable(
            comparison_id=f"E3b_{e.estimand.replace(' ', '_')[:60]}",
            unavailable_reason=base_reason
            + f" E3b {e.treatment}-minus-{e.control} {e.metric} not yet executed.",
        )
        for e in e3b_estimands
    ]

    e3c_estimands = [
        EstimandSpec(
            estimand="p2c_dla minus per_task_dla offered deadline attainment under fixed_1x at each state_age",
            treatment="p2c_dla",
            control="per_task_dla",
            metric="offered deadline attainment",
            state_age_ms=None,
        ),
        EstimandSpec(
            estimand="proactive minus reactive offered deadline attainment under per_task_dla at each state_age",
            treatment="proactive",
            control="reactive",
            metric="offered deadline attainment",
            state_age_ms=None,
        ),
        EstimandSpec(
            estimand="p2c_dla minus per_task_dla rejection_share under fixed_1x at each state_age",
            treatment="p2c_dla",
            control="per_task_dla",
            metric="rejection_share",
            state_age_ms=None,
        ),
        EstimandSpec(
            estimand="proactive minus reactive resource_unit_seconds under per_task_dla at each state_age",
            treatment="proactive",
            control="reactive",
            metric="resource_unit_seconds",
            state_age_ms=None,
        ),
    ]
    e3c_paired = [
        PairedDifferenceUnavailable(
            comparison_id=f"E3c_{e.estimand.replace(' ', '_')[:60]}",
            unavailable_reason=base_reason
            + f" E3c {e.treatment}-minus-{e.control} {e.metric} stale sensitivity not yet executed.",
        )
        for e in e3c_estimands
    ]

    e3a_view = NoResultsComparisonView(
        stage="E3a",
        estimands=e3a_estimands,
        paired_differences=e3a_paired,
        unavailable_reason=base_reason + " E3a dormant under hold.",
    )
    e3b_view = NoResultsComparisonView(
        stage="E3b",
        estimands=e3b_estimands,
        paired_differences=e3b_paired,
        unavailable_reason=base_reason + " E3b trade-off family dormant.",
    )
    e3c_view = NoResultsComparisonView(
        stage="E3c",
        estimands=e3c_estimands,
        paired_differences=e3c_paired,
        unavailable_reason=base_reason
        + " E3c staleness sensitivity dormant; 32 stale variants not run.",
    )

    # Cross-check that we never use tasks as N and never claim universal superiority
    for view in (e3a_view, e3b_view, e3c_view):
        if view.tasks_are_not_replicates is not True:
            raise ValueError("tasks_are_not_replicates must be True")
        if view.manchester_wide_inference_forbidden is not True:
            raise ValueError("manchester_wide_inference must be forbidden")
        if view.universal_superiority_forbidden is not True:
            raise ValueError("universal_superiority must be forbidden")

    return E3ResearchComparisonView(e3a=e3a_view, e3b=e3b_view, e3c=e3c_view)


__all__ = [
    "E3ResearchComparisonView",
    "NoResultsComparisonView",
    "PairedDifferenceUnavailable",
    "EstimandSpec",
    "build_e3_comparison_view",
    "REPLICATION_UNIT",
    "FLEET_SEEDS",
    "N_FLEET_DRAWS",
    "DEGREES_OF_FREEDOM",
    "CRITICAL_T_95_DF3",
    "METHOD",
]
