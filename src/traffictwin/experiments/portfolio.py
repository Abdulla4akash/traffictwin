"""Transparent, deterministic portfolio-selector prototype."""

from __future__ import annotations

import csv
import statistics
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from io import StringIO

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.domain.enums import FleetTierMix, RsuCapacityMode, TaskClass, WorkloadOrdering
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.experiments.winner_map import WinnerMapReport


class PortfolioRule(BaseModel):
    """One ordered, fully inspectable selector rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    selected_algorithm: str = Field(min_length=1)
    minimum_load_intensity: float | None = Field(default=None, ge=0.0)
    maximum_load_intensity: float | None = Field(default=None, ge=0.0)
    minimum_t1_share: float | None = Field(default=None, ge=0.0, le=1.0)
    fleet_tier_mix: FleetTierMix | None = None
    rsu_capacity_mode: RsuCapacityMode | None = None
    workload_ordering: WorkloadOrdering | None = None
    rationale: str = Field(min_length=1)


class PortfolioRuleSet(BaseModel):
    """Versioned ordered rule set with an explicit fallback."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    selector_id: str = "synthetic-portfolio-v1"
    rules: list[PortfolioRule]
    fallback_algorithm: str
    synthetic_demonstration_only: bool = True
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Rules are engineering demonstrations, not learned or externally calibrated policies.",
            "A selection does not launch, train, or alter an offloading model.",
        ]
    )


class PortfolioDecision(BaseModel):
    """Auditable result of applying one rule set to one seed."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str
    selected_algorithm: str
    matched_rule_id: str | None
    load_intensity: float
    t1_share: float | None
    rationale: str
    synthetic_demonstration_only: bool


class PortfolioEvaluationRow(BaseModel):
    """Selector result joined to one winner-map row."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str
    selected_algorithm: str
    matched_rule_id: str | None
    winner_algorithms: list[str]
    selected_score: float | None
    regret: float | None
    winner_or_tie: bool | None
    status: str


class PortfolioEvaluationReport(BaseModel):
    """Descriptive evaluation of a transparent selector."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime
    selector_id: str
    metric_key: str
    evaluated_seed_count: int
    available_seed_count: int
    winner_or_tie_rate: float | None
    mean_selected_score: float | None
    selected_score_standard_deviation: float | None
    mean_regret: float | None
    regret_standard_deviation: float | None
    failure_seed_ids: list[str]
    rows: list[PortfolioEvaluationRow]
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return machine-readable JSON."""

        return self.model_dump_json(indent=2)


class ConstituentEvaluation(BaseModel):
    """One fixed constituent's descriptive held-out performance."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str
    available_seed_count: int = Field(ge=0)
    winner_or_tie_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_score: float | None = None
    score_standard_deviation: float | None = Field(default=None, ge=0.0)
    mean_regret: float | None = Field(default=None, ge=0.0)
    regret_standard_deviation: float | None = Field(default=None, ge=0.0)
    failure_seed_ids: list[str] = Field(default_factory=list)


class PairwiseDominance(BaseModel):
    """Held-out pairwise constituent comparison counts."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str
    comparator: str
    available_seed_count: int = Field(ge=0)
    wins: int = Field(ge=0)
    ties: int = Field(ge=0)
    losses: int = Field(ge=0)


class PortfolioStudyReport(BaseModel):
    """Development/held-out evaluation of a fixed transparent selector."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime
    selector_id: str
    metric_key: str
    objective: ObjectiveDirection
    development_seed_ids: list[str]
    held_out_seed_ids: list[str]
    development_evaluation: PortfolioEvaluationReport
    held_out_evaluation: PortfolioEvaluationReport
    held_out_constituents: list[ConstituentEvaluation]
    dominance_matrix: list[PairwiseDominance]
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return machine-readable JSON."""

        return self.model_dump_json(indent=2)


def default_synthetic_portfolio_rules() -> PortfolioRuleSet:
    """Return a transparent rule set for standalone workflow verification."""

    return PortfolioRuleSet(
        rules=[
            PortfolioRule(
                rule_id="P1-weak-fleet",
                selected_algorithm="synthetic-selective",
                fleet_tier_mix=FleetTierMix.WEAK,
                rationale="A weak fleet is routed to the synthetic selective profile.",
            ),
            PortfolioRule(
                rule_id="P2-t1-pressure",
                selected_algorithm="synthetic-selective",
                minimum_t1_share=0.50,
                rationale="A T1-heavy synthetic workload uses the selective profile.",
            ),
            PortfolioRule(
                rule_id="P3-low-pressure",
                selected_algorithm="synthetic-always-local",
                maximum_load_intensity=0.80,
                rationale="A low-pressure synthetic seed uses the always-local profile.",
            ),
            PortfolioRule(
                rule_id="P4-reduced-capacity",
                selected_algorithm="synthetic-balanced",
                rsu_capacity_mode=RsuCapacityMode.REDUCED,
                rationale="Reduced synthetic infrastructure capacity uses the balanced profile.",
            ),
            PortfolioRule(
                rule_id="P5-high-pressure",
                selected_algorithm="synthetic-balanced",
                minimum_load_intensity=1.50,
                rationale="A high-pressure synthetic seed uses the balanced profile.",
            ),
        ],
        fallback_algorithm="synthetic-balanced",
    )


def select_portfolio_policy(
    seed: ScenarioSeed,
    ruleset: PortfolioRuleSet,
) -> PortfolioDecision:
    """Select a policy label using ordered deterministic rules."""

    load_intensity = seed.demand.multiplier * seed.workload.birth_rate_multiplier
    t1_share = seed.workload.class_mix.get(TaskClass.T1)
    for rule in ruleset.rules:
        if _matches(rule, seed, load_intensity, t1_share):
            return PortfolioDecision(
                seed_id=seed.seed_id,
                selected_algorithm=rule.selected_algorithm,
                matched_rule_id=rule.rule_id,
                load_intensity=load_intensity,
                t1_share=t1_share,
                rationale=rule.rationale,
                synthetic_demonstration_only=ruleset.synthetic_demonstration_only,
            )
    return PortfolioDecision(
        seed_id=seed.seed_id,
        selected_algorithm=ruleset.fallback_algorithm,
        matched_rule_id=None,
        load_intensity=load_intensity,
        t1_share=t1_share,
        rationale="No rule matched; the explicit fallback was selected.",
        synthetic_demonstration_only=ruleset.synthetic_demonstration_only,
    )


def evaluate_portfolio(
    winner_map: WinnerMapReport,
    seeds: Mapping[str, ScenarioSeed],
    ruleset: PortfolioRuleSet,
    *,
    clock: Callable[[], datetime] | None = None,
) -> PortfolioEvaluationReport:
    """Join selector decisions to observed winner-map scores."""

    rows: list[PortfolioEvaluationRow] = []
    regrets: list[float] = []
    selected_scores: list[float] = []
    wins = 0
    available = 0
    warnings = list(ruleset.limitations)
    for entry in winner_map.entries:
        seed = seeds.get(entry.seed_id)
        if seed is None:
            rows.append(
                PortfolioEvaluationRow(
                    seed_id=entry.seed_id,
                    selected_algorithm=ruleset.fallback_algorithm,
                    matched_rule_id=None,
                    winner_algorithms=entry.winner_algorithms,
                    selected_score=None,
                    regret=None,
                    winner_or_tie=None,
                    status="seed_metadata_unavailable",
                )
            )
            continue
        decision = select_portfolio_policy(seed, ruleset)
        score = next(
            (
                candidate
                for candidate in entry.policy_scores
                if candidate.algorithm == decision.selected_algorithm
            ),
            None,
        )
        if score is None:
            rows.append(
                PortfolioEvaluationRow(
                    seed_id=entry.seed_id,
                    selected_algorithm=decision.selected_algorithm,
                    matched_rule_id=decision.matched_rule_id,
                    winner_algorithms=entry.winner_algorithms,
                    selected_score=None,
                    regret=None,
                    winner_or_tie=None,
                    status="selected_policy_unobserved",
                )
            )
            continue
        available += 1
        regrets.append(score.regret)
        selected_scores.append(score.mean)
        wins += int(score.winner)
        rows.append(
            PortfolioEvaluationRow(
                seed_id=entry.seed_id,
                selected_algorithm=decision.selected_algorithm,
                matched_rule_id=decision.matched_rule_id,
                winner_algorithms=entry.winner_algorithms,
                selected_score=score.mean,
                regret=score.regret,
                winner_or_tie=score.winner,
                status="available",
            )
        )
    if winner_map.synthetic_only:
        warnings.append(
            "This evaluates synthetic policy profiles only and is not a "
            "portfolio-performance claim."
        )
    generated_at = clock() if clock is not None else datetime.now(UTC)
    return PortfolioEvaluationReport(
        generated_at=generated_at,
        selector_id=ruleset.selector_id,
        metric_key=winner_map.metric_key,
        evaluated_seed_count=len(rows),
        available_seed_count=available,
        winner_or_tie_rate=wins / available if available else None,
        mean_selected_score=(
            sum(selected_scores) / len(selected_scores) if selected_scores else None
        ),
        selected_score_standard_deviation=_population_deviation(selected_scores),
        mean_regret=sum(regrets) / len(regrets) if regrets else None,
        regret_standard_deviation=_population_deviation(regrets),
        failure_seed_ids=sorted(
            row.seed_id for row in rows if row.status != "available" or row.winner_or_tie is False
        ),
        rows=rows,
        warnings=warnings,
    )


def evaluate_portfolio_study(
    winner_map: WinnerMapReport,
    seeds: Mapping[str, ScenarioSeed],
    ruleset: PortfolioRuleSet,
    *,
    development_seed_ids: list[str],
    held_out_seed_ids: list[str],
    clock: Callable[[], datetime] | None = None,
) -> PortfolioStudyReport:
    """Evaluate a fixed selector and every observed constituent on held-out seeds."""

    development = sorted(set(development_seed_ids))
    held_out = sorted(set(held_out_seed_ids))
    if not development or not held_out:
        raise ValueError("portfolio study requires non-empty development and held-out seed sets")
    overlap = sorted(set(development) & set(held_out))
    if overlap:
        raise ValueError("development and held-out seeds overlap: " + ", ".join(overlap))
    available_ids = {entry.seed_id for entry in winner_map.entries}
    missing = sorted((set(development) | set(held_out)) - available_ids)
    if missing:
        raise ValueError("winner map is missing study seeds: " + ", ".join(missing))
    generated_at = clock() if clock is not None else datetime.now(UTC)
    development_map = winner_map.model_copy(
        update={
            "entries": [entry for entry in winner_map.entries if entry.seed_id in development],
            "generated_at": generated_at,
        }
    )
    held_out_map = winner_map.model_copy(
        update={
            "entries": [entry for entry in winner_map.entries if entry.seed_id in held_out],
            "generated_at": generated_at,
        }
    )
    development_evaluation = evaluate_portfolio(
        development_map,
        seeds,
        ruleset,
        clock=lambda: generated_at,
    )
    held_out_evaluation = evaluate_portfolio(
        held_out_map,
        seeds,
        ruleset,
        clock=lambda: generated_at,
    )
    algorithms = sorted(
        {score.algorithm for entry in held_out_map.entries for score in entry.policy_scores}
    )
    constituents: list[ConstituentEvaluation] = []
    for algorithm in algorithms:
        scores = [
            score
            for entry in held_out_map.entries
            for score in entry.policy_scores
            if score.algorithm == algorithm
        ]
        score_values = [score.mean for score in scores]
        regret_values = [score.regret for score in scores]
        constituents.append(
            ConstituentEvaluation(
                algorithm=algorithm,
                available_seed_count=len(scores),
                winner_or_tie_rate=(
                    sum(int(score.winner) for score in scores) / len(scores) if scores else None
                ),
                mean_score=(sum(score_values) / len(score_values) if score_values else None),
                score_standard_deviation=_population_deviation(score_values),
                mean_regret=(sum(regret_values) / len(regret_values) if regret_values else None),
                regret_standard_deviation=_population_deviation(regret_values),
                failure_seed_ids=sorted(
                    entry.seed_id
                    for entry in held_out_map.entries
                    for score in entry.policy_scores
                    if score.algorithm == algorithm and not score.winner
                ),
            )
        )
    return PortfolioStudyReport(
        generated_at=generated_at,
        selector_id=ruleset.selector_id,
        metric_key=winner_map.metric_key,
        objective=winner_map.objective,
        development_seed_ids=development,
        held_out_seed_ids=held_out,
        development_evaluation=development_evaluation,
        held_out_evaluation=held_out_evaluation,
        held_out_constituents=constituents,
        dominance_matrix=_dominance_matrix(held_out_map),
        warnings=[
            *ruleset.limitations,
            "The selector rules were fixed before the held-out synthetic seed evaluation.",
            "This split verifies research workflow only and is not an external performance claim.",
        ],
    )


def portfolio_study_to_csv(report: PortfolioStudyReport) -> str:
    """Render held-out selector and constituent results as deterministic CSV."""

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "record_type",
            "seed_or_algorithm",
            "selected_or_comparator",
            "score",
            "score_stddev",
            "regret",
            "regret_stddev",
            "winner_or_tie",
            "status_or_counts",
        ]
    )
    for row in report.held_out_evaluation.rows:
        writer.writerow(
            [
                "selector_seed",
                row.seed_id,
                row.selected_algorithm,
                row.selected_score,
                "",
                row.regret,
                "",
                row.winner_or_tie,
                row.status,
            ]
        )
    for item in report.held_out_constituents:
        writer.writerow(
            [
                "constituent",
                item.algorithm,
                "",
                item.mean_score,
                item.score_standard_deviation,
                item.mean_regret,
                item.regret_standard_deviation,
                item.winner_or_tie_rate,
                f"available={item.available_seed_count};failures={','.join(item.failure_seed_ids)}",
            ]
        )
    for dominance in report.dominance_matrix:
        writer.writerow(
            [
                "dominance",
                dominance.algorithm,
                dominance.comparator,
                "",
                "",
                "",
                "",
                "",
                (f"wins={dominance.wins};ties={dominance.ties};losses={dominance.losses}"),
            ]
        )
    return output.getvalue()


def portfolio_study_to_markdown(report: PortfolioStudyReport) -> str:
    """Render a concise deterministic held-out study report."""

    held = report.held_out_evaluation
    lines = [
        "# TrafficTwin Synthetic Portfolio Study",
        "",
        f"- Selector: `{report.selector_id}`",
        f"- Metric: `{report.metric_key}` ({report.objective.value})",
        f"- Development seed families: `{len(report.development_seed_ids)}`",
        f"- Held-out seed families: `{len(report.held_out_seed_ids)}`",
        f"- Held-out winner/tie rate: `{held.winner_or_tie_rate}`",
        f"- Held-out mean score: `{held.mean_selected_score}`",
        f"- Held-out score standard deviation: `{held.selected_score_standard_deviation}`",
        f"- Held-out mean regret: `{held.mean_regret}`",
        f"- Held-out regret standard deviation: `{held.regret_standard_deviation}`",
        f"- Failure seed families: `{', '.join(held.failure_seed_ids) or 'none'}`",
        "",
        "## Held-out constituents",
        "",
        "| Algorithm | Mean score | Score SD | Mean regret | Regret SD | Win/tie rate | Failures |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    lines.extend(
        "| "
        + " | ".join(
            [
                item.algorithm,
                str(item.mean_score),
                str(item.score_standard_deviation),
                str(item.mean_regret),
                str(item.regret_standard_deviation),
                str(item.winner_or_tie_rate),
                ", ".join(item.failure_seed_ids) or "none",
            ]
        )
        + " |"
        for item in report.held_out_constituents
    )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines).rstrip() + "\n"


def _population_deviation(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _dominance_matrix(winner_map: WinnerMapReport) -> list[PairwiseDominance]:
    algorithms = sorted(
        {score.algorithm for entry in winner_map.entries for score in entry.policy_scores}
    )
    rows: list[PairwiseDominance] = []
    for algorithm in algorithms:
        for comparator in algorithms:
            if algorithm == comparator:
                continue
            wins = ties = losses = available = 0
            for entry in winner_map.entries:
                by_algorithm = {score.algorithm: score for score in entry.policy_scores}
                left = by_algorithm.get(algorithm)
                right = by_algorithm.get(comparator)
                if left is None or right is None:
                    continue
                available += 1
                difference = left.mean - right.mean
                if winner_map.objective is ObjectiveDirection.MINIMISE:
                    difference = -difference
                if abs(difference) <= 1e-12:
                    ties += 1
                elif difference > 0:
                    wins += 1
                else:
                    losses += 1
            rows.append(
                PairwiseDominance(
                    algorithm=algorithm,
                    comparator=comparator,
                    available_seed_count=available,
                    wins=wins,
                    ties=ties,
                    losses=losses,
                )
            )
    return rows


def _matches(
    rule: PortfolioRule,
    seed: ScenarioSeed,
    load_intensity: float,
    t1_share: float | None,
) -> bool:
    checks = [
        rule.minimum_load_intensity is None or load_intensity >= rule.minimum_load_intensity,
        rule.maximum_load_intensity is None or load_intensity <= rule.maximum_load_intensity,
        rule.minimum_t1_share is None
        or (t1_share is not None and t1_share >= rule.minimum_t1_share),
        rule.fleet_tier_mix is None or seed.fleet.tier_mix is rule.fleet_tier_mix,
        rule.rsu_capacity_mode is None
        or seed.infrastructure.rsu_capacity_mode is rule.rsu_capacity_mode,
        rule.workload_ordering is None or seed.workload.ordering is rule.workload_ordering,
    ]
    return all(checks)
