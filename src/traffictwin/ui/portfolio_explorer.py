"""Typed UI projection over the transparent portfolio selector.

This module is a deterministic presentation layer over
``traffictwin.experiments.portfolio``. It does not re-derive selection
logic and does not claim optimality.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.domain.enums import FleetTierMix, RsuCapacityMode, TaskClass, WorkloadOrdering
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.portfolio import (
    PortfolioDecision,
    PortfolioRuleSet,
    PortfolioStudyReport,
    default_synthetic_portfolio_rules,
    evaluate_portfolio_study,
    select_portfolio_policy,
)
from traffictwin.metrics.results import JsonScalar
from traffictwin.synthetic.config import SyntheticPolicyProfile
from traffictwin.synthetic.experiments import generate_synthetic_portfolio_study
from traffictwin.synthetic.generator import generate_run_data
from traffictwin.synthetic.scenarios import preset_config

_FIXTURE_TIME = __import__("datetime").datetime(2026, 7, 17, 12, 0, tzinfo=__import__("datetime").timezone.utc)


def _fixed_clock() -> __import__("datetime").datetime:
    return _FIXTURE_TIME


class ChallengeSeedDefinition(BaseModel):
    """Deterministic challenge seed library entry."""

    model_config = ConfigDict(extra="forbid")

    challenge_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    why_challenging: str = Field(min_length=1)
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    expected_evidence_surfaces: list[str] = Field(default_factory=list)
    evidence_standing: str = Field(default="synthetic demonstration only")
    executable_now: bool = True
    not_yet_executable_reason: str | None = None
    limitations: list[str] = Field(default_factory=list)
    scenario_seed_preview: dict[str, Any] = Field(default_factory=dict)


class PortfolioCandidateView(BaseModel):
    """View over one constituent evaluation."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str
    rank: int | None = None
    winner_or_tie_rate: float | None = None
    mean_score: float | None = None
    mean_regret: float | None = None
    available_seed_count: int
    failure_seed_ids: list[str] = Field(default_factory=list)
    evidence_standing: str = "synthetic demonstration only"
    limitations: list[str] = Field(default_factory=list)


class PortfolioSelectionView(BaseModel):
    """Deterministic selection view for one scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario_seed_id: str
    scenario_features: dict[str, JsonScalar] = Field(default_factory=dict)
    selected_algorithm: str
    matched_rule_id: str | None
    rationale: str
    selector_id: str
    synthetic_demonstration_only: bool = True
    warnings: list[str] = Field(default_factory=list)


class PortfolioExplorerView(BaseModel):
    """Aggregated view for the Portfolio Explorer page."""

    model_config = ConfigDict(extra="forbid")

    selected_challenge: ChallengeSeedDefinition | None = None
    selection: PortfolioSelectionView | None = None
    candidate_views: list[PortfolioCandidateView] = Field(default_factory=list)
    study_report: PortfolioStudyReport | None = None
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str = ""


def _scenario_seed_from_challenge(challenge: ChallengeSeedDefinition) -> ScenarioSeed:
    base = generate_run_data(preset_config("baseline")).seed.model_dump(mode="json")
    # Apply deterministic overrides onto the seed dict, then validate.
    # Use simple dot-notation handling for known fields.
    seed_dict: dict[str, Any] = dict(base)
    # Ensure we have a fresh seed_id/name
    seed_dict["seed_id"] = challenge.challenge_id
    seed_dict["name"] = challenge.title
    seed_dict["description"] = challenge.purpose + " " + challenge.why_challenging
    # Apply overrides
    for key, value in challenge.parameter_overrides.items():
        _apply_dot_override(seed_dict, key, value)
    # Keep provenance synthetic
    seed_dict["provenance"] = {"created_by": "TrafficTwin challenge library", "source": "TrafficTwin synthetic demonstration"}
    return ScenarioSeed.model_validate(seed_dict)


def _apply_dot_override(target: dict[str, Any], dotted: str, value: JsonScalar) -> None:
    parts = dotted.split(".")
    cur: dict[str, Any] = target
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]  # type: ignore[assignment]
    cur[parts[-1]] = value


def _load_intensity(seed: ScenarioSeed) -> float:
    return float(seed.demand.multiplier * seed.workload.birth_rate_multiplier)


def _t1_share(seed: ScenarioSeed) -> float | None:
    val = seed.workload.class_mix.get(TaskClass.T1)
    return float(val) if val is not None else None


# Challenge library — 7 deterministic definitions reusing validated fields.
_CHALLENGE_SEEDS: list[ChallengeSeedDefinition] = [
    ChallengeSeedDefinition(
        challenge_id="CH-01-arena-surge",
        title="Arena / event demand surge",
        purpose="High synthetic demand surge around an event location.",
        why_challenging="Tests selector under uniform high pressure; P5 high-pressure rule expected.",
        parameter_overrides={
            "demand.multiplier": 2.2,
            "workload.birth_rate_multiplier": 1.6,
            "traffic.event_type": "stadium_event",
            "traffic.location": "old-trafford-corridor",
            "traffic.event_demand_multiplier": 2.0,
            "traffic.duration_min": 15.0,
        },
        expected_evidence_surfaces=["traffic.count.total", "task.generated.count", "infra.queue_length.mean"],
        limitations=[
            "Infrastructure capacity is rsu_capacity_mode (STANDARD), not compute cores or waiting-room seats.",
            "Synthetic event demand is not a calibrated Manchester surge.",
        ],
        scenario_seed_preview={},
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-02-lane-closure-corridor",
        title="Lane closure / road-clearing corridor",
        purpose="Synthetic incident with closed lanes and corridor demand response.",
        why_challenging="Tests narrowing and incident handling; maps to S6 corridor fixture.",
        parameter_overrides={
            "traffic.event_type": "road_closure",
            "traffic.location": "m60-corridor-j9",
            "traffic.lanes_closed": 2,
            "traffic.duration_min": 30.0,
            "traffic.event_demand_multiplier": 1.3,
            "demand.multiplier": 1.1,
            "infrastructure.rsu_capacity_mode": RsuCapacityMode.STANDARD.value,
        },
        expected_evidence_surfaces=["trip.duration.mean_s", "traffic.speed.mean_mps", "infra.utilisation.mean"],
        limitations=[
            "Lane closure is a synthetic incident type; not SUMO-closed or live Manchester.",
            "rsu_capacity_mode remains STANDARD infrastructure mode, not compute.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-03-t1-heavy-weak-fleet",
        title="T1-heavy workload + weak fleet",
        purpose="Workload dominated by T1 tasks with a weak vehicle tier mix.",
        why_challenging="Tests P2 T1-pressure rule and weak-fleet routing.",
        parameter_overrides={
            "workload.class_mix": {TaskClass.T1.value: 0.6, TaskClass.T2.value: 0.2, TaskClass.T3.value: 0.2},
            "fleet.tier_mix": FleetTierMix.WEAK.value,
            "workload.birth_rate_multiplier": 1.5,
            "demand.multiplier": 1.0,
        },
        expected_evidence_surfaces=["task.completion.rate", "task.latency.mean_ms", "fairness.vehicle_tier.completion_rate.max_gap"],
        limitations=[
            "Fleet tier mix WEAK is synthetic; not a live Manchester fleet measurement.",
            "No waiting-room capacity is implied by tier mix.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-04-rsu-waiting-room-squeeze",
        title="RSU waiting-room squeeze",
        purpose="Reduced infrastructure capacity with short queuing room.",
        why_challenging="Tests P4 reduced-capacity rule; distinguishes admission vs compute.",
        parameter_overrides={
            "infrastructure.rsu_capacity_mode": RsuCapacityMode.REDUCED.value,
            "infrastructure.rsu_count": 3,
            "demand.multiplier": 1.2,
            "workload.birth_rate_multiplier": 1.4,
        },
        expected_evidence_surfaces=["infra.queue_length.max", "infra.saturation.episode_count", "task.offload.rate"],
        limitations=[
            "Current product exposes only rsu_capacity_mode (STANDARD/REDUCED) and rsu_count; it does not expose separate waiting-room seats, service/compute cores, worker count, or in-flight cap. Do not label rsu_capacity as compute.",
            "Queue length and saturation are synthetic observations, not live RSU telemetry.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-05-load-aware-forwarding",
        title="Load-aware forwarding / placement challenge",
        purpose="High task arrival with mixed ordering to stress forwarding.",
        why_challenging="Tests placement under mixed load; dominance varies by seed.",
        parameter_overrides={
            "workload.birth_rate_multiplier": 1.8,
            "workload.ordering": WorkloadOrdering.MIXED.value,
            "demand.multiplier": 1.3,
            "fleet.tier_mix": FleetTierMix.MIXED.value,
        },
        expected_evidence_surfaces=["infra.load_balance.jain_capacity_normalised", "task.decision_share.v2i", "task.completion.rate"],
        limitations=[
            "Load-aware forwarding is evaluated via synthetic task routing only.",
            "No placement is deployed to Kubernetes or live RSUs.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-06-stale-state-scheduling",
        title="Stale-state scheduling challenge",
        purpose="Ordered workload with moderate pressure to expose staleness.",
        why_challenging="Tests scheduling under ordered task stream.",
        parameter_overrides={
            "workload.ordering": WorkloadOrdering.EASY_FIRST.value,
            "workload.birth_rate_multiplier": 1.2,
            "demand.multiplier": 1.0,
            "evaluation.random_seed": 42,
        },
        expected_evidence_surfaces=["task.latency.p95_ms", "task.deadline_miss.completed_observed_rate", "traffic.count.mean"],
        limitations=[
            "Stale state is a research prompt; no live scheduler is evaluated.",
            "Random seed 42 is deterministic synthetic repeatability only.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-07-scaling-strategy",
        title="Scaling strategy challenge",
        purpose="Larger fleet and RSU count to test scaling behaviour.",
        why_challenging="Tests scaling of V2I decisions with more RSUs.",
        parameter_overrides={
            "fleet.count": 80,
            "infrastructure.rsu_count": 6,
            "demand.multiplier": 1.0,
            "workload.birth_rate_multiplier": 2.0,
        },
        expected_evidence_surfaces=["infra.observed_rsu.count", "spatial.rsu.task.completion_rate_by_target", "task.energy.mean_per_observed_task_j"],
        limitations=[
            "Fleet count 80 and RSU count 6 are synthetic scaling values; not a live Manchester deployment.",
            "rsu_count is infrastructure count, distinct from waiting-room or compute capacity.",
        ],
    ),
]


def get_challenge_seed_library() -> list[ChallengeSeedDefinition]:
    """Return deterministic ordered challenge library."""

    # Return deep copies to preserve determinism and prevent mutation.
    return [seed.model_copy(deep=True) for seed in _CHALLENGE_SEEDS]


def get_challenge_seed(challenge_id: str) -> ChallengeSeedDefinition | None:
    for seed in _CHALLENGE_SEEDS:
        if seed.challenge_id == challenge_id:
            return seed.model_copy(deep=True)
    return None


def describe_portfolio_selection(
    seed: ScenarioSeed,
    ruleset: PortfolioRuleSet | None = None,
) -> PortfolioSelectionView:
    rules = ruleset or default_synthetic_portfolio_rules()
    decision = select_portfolio_policy(seed, rules)
    return PortfolioSelectionView(
        scenario_seed_id=seed.seed_id,
        scenario_features={
            "load_intensity": _load_intensity(seed),
            "t1_share": _t1_share(seed),
            "fleet_tier_mix": seed.fleet.tier_mix.value,
            "rsu_capacity_mode": seed.infrastructure.rsu_capacity_mode.value,
            "rsu_count": seed.infrastructure.rsu_count,
            "fleet_count": seed.fleet.count,
            "demand_multiplier": seed.demand.multiplier,
            "birth_rate_multiplier": seed.workload.birth_rate_multiplier,
        },
        selected_algorithm=decision.selected_algorithm,
        matched_rule_id=decision.matched_rule_id,
        rationale=decision.rationale,
        selector_id=rules.selector_id,
        synthetic_demonstration_only=decision.synthetic_demonstration_only,
        warnings=list(rules.limitations),
    )


@lru_cache(maxsize=1)
def get_demo_portfolio_study() -> PortfolioStudyReport:
    """Return deterministic demo portfolio study (5 seeds, 3 policies, 3 seeds each)."""

    with tempfile.TemporaryDirectory() as tmp:
        fixture = generate_synthetic_portfolio_study(Path(tmp) / "study", overwrite=True)
        from traffictwin.ingestion.bundle import validate_bundle
        from traffictwin.metrics.engine import compute_metrics_for_bundle
        from traffictwin.experiments.winner_map import build_winner_map

        collections = []
        aliases: dict[str, str] = {}
        for path in fixture.bundle_paths:
            validation = validate_bundle(path)
            assert validation.seed is not None
            aliases[validation.seed.seed_id] = validation.seed.parent_seed_id or validation.seed.seed_id
            collections.append(compute_metrics_for_bundle(validation, clock=_fixed_clock))
        winner_map = build_winner_map(collections, seed_aliases=aliases, clock=_fixed_clock)
        report = evaluate_portfolio_study(
            winner_map,
            fixture.base_seeds,
            default_synthetic_portfolio_rules(),
            development_seed_ids=fixture.development_seed_ids,
            held_out_seed_ids=fixture.held_out_seed_ids,
            clock=_fixed_clock,
        )
        return report


def build_portfolio_explorer_view(
    challenge_id: str | None = None,
) -> PortfolioExplorerView:
    """Build deterministic explorer view for a challenge or default demo study."""

    challenge: ChallengeSeedDefinition | None = None
    selection: PortfolioSelectionView | None = None
    if challenge_id is not None:
        challenge = get_challenge_seed(challenge_id)
        if challenge is not None:
            seed = _scenario_seed_from_challenge(challenge)
            selection = describe_portfolio_selection(seed)
    else:
        # Default: first challenge as preview
        challenge = get_challenge_seed_library()[0]
        seed = _scenario_seed_from_challenge(challenge)
        selection = describe_portfolio_selection(seed)

    try:
        study = get_demo_portfolio_study()
        # Candidate views from held-out constituents
        candidates = [
            PortfolioCandidateView(
                algorithm=c.algorithm,
                winner_or_tie_rate=c.winner_or_tie_rate,
                mean_score=c.mean_score,
                mean_regret=c.mean_regret,
                available_seed_count=c.available_seed_count,
                failure_seed_ids=list(c.failure_seed_ids),
            )
            for c in study.held_out_constituents
        ]
        # Rank by mean_regret ascending (lower is better for minimise)
        # Objective is minimise for portfolio study
        candidates_sorted = sorted(
            candidates,
            key=lambda c: (c.mean_regret if c.mean_regret is not None else float("inf")),
        )
        for idx, cand in enumerate(candidates_sorted, start=1):
            cand.rank = idx
        warnings = list(study.warnings)
    except Exception as exc:  # pragma: no cover - defensive
        study = None
        candidates_sorted = []
        warnings = [f"Portfolio study unavailable: {exc}"]

    # Add challenge limitations to warnings where relevant
    if challenge is not None:
        warnings = [*warnings, *challenge.limitations]

    fingerprint_payload = {
        "challenge_id": challenge.challenge_id if challenge else None,
        "selection": selection.model_dump(mode="json") if selection else None,
        "candidates": [c.model_dump(mode="json") for c in candidates_sorted],
        "study_selector": study.selector_id if study else None,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, default=str).encode()
    ).hexdigest()

    return PortfolioExplorerView(
        selected_challenge=challenge,
        selection=selection,
        candidate_views=candidates_sorted,
        study_report=study,
        warnings=warnings,
        fingerprint=fingerprint,
    )

