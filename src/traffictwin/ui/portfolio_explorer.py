"""Typed UI projection over the transparent portfolio selector.

This module is a deterministic presentation layer over
``traffictwin.experiments.portfolio``. It does not re-derive selection
logic and does not claim optimality.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.domain.enums import FleetTierMix, RsuCapacityMode, TaskClass, WorkloadOrdering
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.portfolio import (
    PortfolioRuleSet,
    PortfolioStudyReport,
    default_synthetic_portfolio_rules,
    evaluate_portfolio_study,
    select_portfolio_policy,
)
from traffictwin.metrics.results import JsonScalar
from traffictwin.synthetic.experiments import generate_synthetic_portfolio_study
from traffictwin.synthetic.generator import generate_run_data
from traffictwin.synthetic.scenarios import preset_config

_FIXTURE_TIME = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)


def _fixed_clock() -> datetime:
    return _FIXTURE_TIME


class ChallengeExecutionStatus(StrEnum):
    """Truthful execution status for a challenge seed."""

    EXECUTABLE = "EXECUTABLE"
    REPRESENTABLE_ONLY = "REPRESENTABLE_ONLY"
    NOT_YET_EXECUTABLE = "NOT_YET_EXECUTABLE"


# Authoritative selector-consumed field contract.
# Mirrors ``_matches`` in ``traffictwin.experiments.portfolio``:
# load_intensity = demand.multiplier * workload.birth_rate_multiplier
# minimum/maximum_load_intensity, minimum_t1_share (workload.class_mix[T1]),
# fleet_tier_mix, rsu_capacity_mode, workload_ordering.
SELECTOR_CONSUMED_FIELDS: frozenset[str] = frozenset(
    {
        "demand.multiplier",
        "workload.birth_rate_multiplier",
        "workload.class_mix",
        "workload.class_mix[T1]",
        "fleet.tier_mix",
        "infrastructure.rsu_capacity_mode",
        "workload.ordering",
    }
)

# Fields that are valid ScenarioSeed configuration but are NOT consumed by the
# current selector. Kept explicit to avoid implying they affect selection.
SELECTOR_INERT_EXAMPLES: frozenset[str] = frozenset(
    {
        "traffic.event_type",
        "traffic.location",
        "traffic.event_demand_multiplier",
        "traffic.duration_min",
        "traffic.lanes_closed",
        "infrastructure.rsu_count",
        "fleet.count",
        "evaluation.random_seed",
    }
)


def is_selector_input(param: str) -> bool:
    """Return whether an override affects the current selector decision."""
    # Exact match or prefix for class_mix dict
    if param in SELECTOR_CONSUMED_FIELDS:
        return True
    return param.startswith("workload.class_mix")


class ChallengeSeedDefinition(BaseModel):
    """Deterministic challenge seed library entry."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    challenge_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    why_challenging: str = Field(min_length=1)
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    target_evidence_surfaces: list[str] = Field(default_factory=list)
    evidence_standing: str = Field(default="synthetic demonstration only")
    status: ChallengeExecutionStatus = Field(default=ChallengeExecutionStatus.REPRESENTABLE_ONLY)
    not_yet_executable_reason: str | None = None
    limitations: list[str] = Field(default_factory=list)
    scenario_seed_preview: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _migrate_aliases(cls, data: Any) -> Any:  # noqa: ANN401
        if (
            isinstance(data, dict)
            and "expected_evidence_surfaces" in data
            and "target_evidence_surfaces" not in data
        ):  # noqa: E501, SIM102
            data["target_evidence_surfaces"] = data.pop("expected_evidence_surfaces")
        # Alias: executable_now bool -> status
        if isinstance(data, dict) and "executable_now" in data and "status" not in data:  # noqa: SIM102
            val = data.pop("executable_now")
            if val is True:
                data["status"] = ChallengeExecutionStatus.EXECUTABLE
            elif val is False:
                data["status"] = ChallengeExecutionStatus.NOT_YET_EXECUTABLE
        return data

    @property
    def expected_evidence_surfaces(self) -> list[str]:  # pragma: no cover - compat alias
        return self.target_evidence_surfaces

    @property
    def executable_now(self) -> bool:  # pragma: no cover - compat alias
        return self.status == ChallengeExecutionStatus.EXECUTABLE


class PortfolioCandidateView(BaseModel):
    """View over one constituent evaluation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    algorithm: str
    rank: int | None = None
    winner_or_tie_rate: float | None = None
    mean_score: float | None = None
    mean_regret: float | None = None
    available_seed_count: int
    seeds_not_won: list[str] = Field(default_factory=list)
    evidence_standing: str = "synthetic demonstration only"
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_failure_alias(cls, data: Any) -> Any:  # noqa: ANN401
        if isinstance(data, dict) and "failure_seed_ids" in data and "seeds_not_won" not in data:  # noqa: SIM102
            data["seeds_not_won"] = data.pop("failure_seed_ids")
        return data

    @property
    def failure_seed_ids(self) -> list[str]:  # pragma: no cover - compat alias
        return self.seeds_not_won


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
    seed_dict: dict[str, Any] = dict(base)
    seed_dict["seed_id"] = challenge.challenge_id
    seed_dict["name"] = challenge.title
    seed_dict["description"] = challenge.purpose + " " + challenge.why_challenging
    for key, value in challenge.parameter_overrides.items():
        _apply_dot_override(seed_dict, key, value)
    seed_dict["provenance"] = {
        "created_by": "TrafficTwin challenge library",
        "source": "TrafficTwin synthetic demonstration",
    }
    return ScenarioSeed.model_validate(seed_dict)


def _apply_dot_override(target: dict[str, Any], dotted: str, value: object) -> None:
    parts = dotted.split(".")
    cur: dict[str, Any] = target
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
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
        why_challenging=(
            "Tests selector under uniform high pressure; P5 high-pressure rule expected."
        ),
        parameter_overrides={
            "demand.multiplier": 2.2,
            "workload.birth_rate_multiplier": 1.6,
            "traffic.event_type": "stadium_event",
            "traffic.location": "old-trafford-corridor",
            "traffic.event_demand_multiplier": 2.0,
            "traffic.duration_min": 15.0,
        },
        target_evidence_surfaces=[
            "traffic.count.total",
            "task.generated.count",
            "infra.queue_length.mean",
        ],
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
        limitations=[
            (
                "Infrastructure capacity is rsu_capacity_mode (STANDARD), not compute cores "
                "or waiting-room seats."
            ),
            "Synthetic event demand is not a calibrated Manchester surge.",
            "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
            "provide a generic ScenarioSeed-to-run execution path for this challenge.",
        ],
        scenario_seed_preview={},
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-02-lane-closure-corridor",
        title="Lane closure / road-clearing corridor",
        purpose="Synthetic incident with closed lanes and corridor demand response.",
        why_challenging=(
            "Represents a lane-closure scenario record; current portfolio selector does not "
            "simulate lane closure effects. Maps to S6 corridor fixture for synthetic workflow."
        ),
        parameter_overrides={
            "traffic.event_type": "road_closure",
            "traffic.location": "m60-corridor-j9",
            "traffic.lanes_closed": 2,
            "traffic.duration_min": 30.0,
            "traffic.event_demand_multiplier": 1.3,
            "demand.multiplier": 1.1,
            "infrastructure.rsu_capacity_mode": RsuCapacityMode.STANDARD.value,
        },
        target_evidence_surfaces=[
            "trip.duration.mean_s",
            "traffic.speed.mean_mps",
            "infra.utilisation.mean",
        ],
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
        limitations=[
            "Lane closure is a synthetic incident type; not SUMO-closed or live Manchester. "
            "Current portfolio selector does not simulate lane closure effects; lanes do not actually close in this UI study.",  # noqa: E501
            "rsu_capacity_mode remains STANDARD infrastructure mode, not compute.",
            "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
            "provide a generic ScenarioSeed-to-run execution path for this challenge.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-03-t1-heavy-weak-fleet",
        title="T1-heavy workload + weak fleet",
        purpose="Workload dominated by T1 tasks with a weak vehicle tier mix.",
        why_challenging=(
            "T1-heavy weak-fleet case; weak-fleet P1 takes precedence, so the T1-pressure "
            "condition is present but shadowed. Tests ordered rule precedence, not P2 execution."
        ),
        parameter_overrides={
            "workload.class_mix": {
                TaskClass.T1.value: 0.6,
                TaskClass.T2.value: 0.2,
                TaskClass.T3.value: 0.2,
            },
            "fleet.tier_mix": FleetTierMix.WEAK.value,
            "workload.birth_rate_multiplier": 1.5,
            "demand.multiplier": 1.0,
        },
        target_evidence_surfaces=[
            "task.completion.rate",
            "task.latency.mean_ms",
            "fairness.vehicle_tier.completion_rate.max_gap",
        ],
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
        limitations=[
            "Fleet tier mix WEAK is synthetic; not a live Manchester fleet measurement.",
            "No waiting-room capacity is implied by tier mix.",
            "Matched rule is P1-weak-fleet, not P2-t1-pressure, because P1 shadows P2 when both conditions hold.",  # noqa: E501
            "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
            "provide a generic ScenarioSeed-to-run execution path for this challenge.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-04-rsu-waiting-room-squeeze",
        title="Reduced-capacity stress",
        purpose="Reduced infrastructure capacity with short queuing room.",
        why_challenging="Tests P4 reduced-capacity rule; distinguishes admission vs compute.",
        parameter_overrides={
            "infrastructure.rsu_capacity_mode": RsuCapacityMode.REDUCED.value,
            "infrastructure.rsu_count": 3,
            "demand.multiplier": 1.2,
            "workload.birth_rate_multiplier": 1.4,
        },
        target_evidence_surfaces=[
            "infra.queue_length.max",
            "infra.saturation.episode_count",
            "task.offload.rate",
        ],
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
        limitations=[
            (
                "Current product exposes only rsu_capacity_mode (STANDARD/REDUCED) and "
                "rsu_count; it does not expose separate waiting-room seats, service/"
                "compute cores, worker count, or in-flight cap. Do not label rsu_capacity "
                "as compute. Does NOT model separate waiting-room and compute resources."
            ),
            "Queue length and saturation are synthetic observations, not live RSU telemetry.",
            "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
            "provide a generic ScenarioSeed-to-run execution path for this challenge.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-05-load-aware-forwarding",
        title="High-load forwarding context",
        purpose="High task arrival with mixed ordering to create conditions relevant to forwarding evaluation.",  # noqa: E501
        why_challenging=(
            "Creates high-load conditions relevant to forwarding evaluation; it does not "
            "implement a load-aware forwarding strategy. Tests placement under mixed load."
        ),
        parameter_overrides={
            "workload.birth_rate_multiplier": 1.8,
            "workload.ordering": WorkloadOrdering.MIXED.value,
            "demand.multiplier": 1.3,
            "fleet.tier_mix": FleetTierMix.MIXED.value,
        },
        target_evidence_surfaces=[
            "infra.load_balance.jain_capacity_normalised",
            "task.decision_share.v2i",
            "task.completion.rate",
        ],
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
        limitations=[
            "High-load forwarding context is evaluated via synthetic task routing only; no load-aware forwarding mechanism is implemented.",  # noqa: E501
            "No placement is deployed to Kubernetes or live RSUs.",
            "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
            "provide a generic ScenarioSeed-to-run execution path for this challenge.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-06-stale-state-scheduling",
        title="Ordered-arrival fallback case",
        purpose="Ordered workload with moderate pressure to expose fallback selection.",  # noqa: E501
        why_challenging="Tests scheduling under ordered task stream; stale-state scheduling is not represented.",  # noqa: E501
        parameter_overrides={
            "workload.ordering": WorkloadOrdering.EASY_FIRST.value,
            "workload.birth_rate_multiplier": 1.2,
            "demand.multiplier": 1.0,
            "evaluation.random_seed": 42,
        },
        target_evidence_surfaces=[
            "task.latency.p95_ms",
            "task.deadline_miss.completed_observed_rate",
            "traffic.count.mean",
        ],
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
        limitations=[
            "Stale-state scheduling remains a research gap / not represented by this ScenarioSeed; ordered arrival is the only modeled ordering.",  # noqa: E501
            "Random seed 42 is deterministic synthetic repeatability only.",
            "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
            "provide a generic ScenarioSeed-to-run execution path for this challenge.",
        ],
    ),
    ChallengeSeedDefinition(
        challenge_id="CH-07-scaling-strategy",
        title="Scaling stress",
        purpose="Larger fleet and RSU count to test scaling behaviour under larger context.",  # noqa: E501
        why_challenging=(
            "Large-fleet / RSU-count stress context; does not dynamically scale or autoscale. "
            "Tests V2I decisions with more RSUs."
        ),
        parameter_overrides={
            "fleet.count": 80,
            "infrastructure.rsu_count": 6,
            "demand.multiplier": 1.0,
            "workload.birth_rate_multiplier": 2.0,
        },
        target_evidence_surfaces=[
            "infra.observed_rsu.count",
            "spatial.rsu.task.completion_rate_by_target",
            "task.energy.mean_per_observed_task_j",
        ],
        status=ChallengeExecutionStatus.REPRESENTABLE_ONLY,
        limitations=[
            (
                "Fleet count 80 and RSU count 6 are synthetic scaling values; not a live "
                "Manchester deployment. Large-fleet / RSU-count stress context only; no dynamic scaling or autoscaling."  # noqa: E501
            ),
            "rsu_count is infrastructure count, distinct from waiting-room or compute capacity.",
            "Representable as a validated ScenarioSeed. TrafficTwin does not currently "
            "provide a generic ScenarioSeed-to-run execution path for this challenge.",
        ],
    ),
]


def get_challenge_seed_library() -> list[ChallengeSeedDefinition]:
    """Return deterministic ordered challenge library."""

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
def _cached_demo_portfolio_study() -> PortfolioStudyReport:
    """Internal cached construction; do not mutate the returned instance."""

    with tempfile.TemporaryDirectory() as tmp:
        fixture = generate_synthetic_portfolio_study(Path(tmp) / "study", overwrite=True)
        from traffictwin.experiments.winner_map import build_winner_map
        from traffictwin.ingestion.bundle import validate_bundle
        from traffictwin.metrics.engine import compute_metrics_for_bundle

        collections = []
        aliases: dict[str, str] = {}
        for path in fixture.bundle_paths:
            validation = validate_bundle(path)
            assert validation.seed is not None
            aliases[validation.seed.seed_id] = (
                validation.seed.parent_seed_id or validation.seed.seed_id
            )
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


def get_demo_portfolio_study() -> PortfolioStudyReport:
    """Return deterministic demo portfolio study (deep copy, cache-isolated)."""

    return _cached_demo_portfolio_study().model_copy(deep=True)


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
        challenge = get_challenge_seed_library()[0]
        seed = _scenario_seed_from_challenge(challenge)
        selection = describe_portfolio_selection(seed)

    try:
        study = get_demo_portfolio_study()
        candidates = [
            PortfolioCandidateView(
                algorithm=c.algorithm,
                winner_or_tie_rate=c.winner_or_tie_rate,
                mean_score=c.mean_score,
                mean_regret=c.mean_regret,
                available_seed_count=c.available_seed_count,
                seeds_not_won=list(c.failure_seed_ids),
            )
            for c in study.held_out_constituents
        ]
        # Ranking by mean_regret ascending (lower regret is better).
        # Portfolio metric objective is MAXIMISE for task.completion.rate, but
        # regret is minimise (distance from best). Do not claim optimality.
        candidates_sorted = sorted(
            candidates,
            key=lambda c: c.mean_regret if c.mean_regret is not None else float("inf"),
        )
        for idx, cand in enumerate(candidates_sorted, start=1):
            cand.rank = idx
        warnings = list(study.warnings)
    except Exception as exc:  # pragma: no cover - defensive
        study = None
        candidates_sorted = []
        warnings = [f"Portfolio study unavailable: {exc}"]

    if challenge is not None:
        warnings = [*warnings, *challenge.limitations]

    # Fingerprint binds substantive projected evidence; excludes live clock, paths, secrets.
    # Bind canonical representations of challenge, selection, candidates, study,
    # dominance, evaluations, and warnings.
    if study is not None:
        # Use model_dump without generated_at timestamps to avoid clock binding.
        study_payload = study.model_dump(mode="json", exclude={"generated_at"})
        # Also exclude nested generated_at in evaluations
        for key in ("development_evaluation", "held_out_evaluation"):
            if key in study_payload and isinstance(study_payload[key], dict):
                study_payload[key].pop("generated_at", None)
    else:
        study_payload = None

    fingerprint_payload = {
        "challenge_id": challenge.challenge_id if challenge else None,
        "challenge_parameter_overrides": challenge.parameter_overrides if challenge else None,
        "challenge_status": challenge.status.value if challenge else None,
        "challenge_evidence_standing": challenge.evidence_standing if challenge else None,
        "challenge_target_surfaces": challenge.target_evidence_surfaces if challenge else None,
        "selection": selection.model_dump(mode="json") if selection else None,
        "selector_input_features": selection.scenario_features if selection else None,
        "selected_algorithm": selection.selected_algorithm if selection else None,
        "matched_rule_id": selection.matched_rule_id if selection else None,
        "rationale": selection.rationale if selection else None,
        "candidates": [c.model_dump(mode="json") for c in candidates_sorted],
        "candidate_ranking": [c.algorithm for c in candidates_sorted],
        "candidate_mean_scores": {c.algorithm: c.mean_score for c in candidates_sorted},
        "candidate_mean_regret": {c.algorithm: c.mean_regret for c in candidates_sorted},
        "winner_tie_rates": {c.algorithm: c.winner_or_tie_rate for c in candidates_sorted},
        "available_seed_counts": {c.algorithm: c.available_seed_count for c in candidates_sorted},
        "seeds_not_won": {c.algorithm: sorted(c.seeds_not_won) for c in candidates_sorted},
        "development_evaluation": study_payload["development_evaluation"]
        if study_payload
        else None,  # noqa: E501
        "held_out_evaluation": study_payload["held_out_evaluation"] if study_payload else None,  # noqa: E501
        "dominance_matrix": study_payload["dominance_matrix"] if study_payload else None,  # noqa: E501
        "held_out_seed_ids": study_payload["held_out_seed_ids"] if study_payload else None,  # noqa: E501
        "development_seed_ids": study_payload["development_seed_ids"] if study_payload else None,  # noqa: E501
        "selector_id": study_payload["selector_id"] if study_payload else None,  # noqa: E501
        "metric_key": study_payload["metric_key"] if study_payload else None,  # noqa: E501
        "objective": str(study_payload["objective"])
        if study_payload and "objective" in study_payload
        else None,  # noqa: E501
        "warnings": sorted(warnings),
        "study_warnings": sorted(study.warnings) if study else None,  # noqa: E501
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, default=str).encode()
    ).hexdigest()

    return PortfolioExplorerView(
        selected_challenge=challenge,
        selection=selection,
        candidate_views=candidates_sorted,
        study_report=study.model_copy(deep=True) if study is not None else None,
        warnings=warnings,
        fingerprint=fingerprint,
    )
