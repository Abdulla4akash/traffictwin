"""Descriptive cross-actor capacity-slope comparison (crossover option ii).

The accepted paired and ranking tools cannot compare the two audited actors
directly — STA-01 carries a single algorithm and STA-02 a single checkpoint —
so this module implements the crossover draft's alternative method entirely
descriptively: each actor's per-capacity mean of the primary endpoint, an
ordinary least-squares slope over capacity per actor, per-level deltas, and
the draft's predeclared binary crossover rule. No interval, no test, no
significance language, and type-level literals keep it that way.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from traffictwin.integration.vec_campaign.analysis import VecCampaignAnalysis
from traffictwin.integration.vec_campaign.models import VecCampaignModel
from traffictwin.integration.vec_campaign.service import VecCampaignError


class ActorCapacityCurve(VecCampaignModel):
    """One actor's descriptive per-capacity means for the shared endpoint."""

    actor_id: str = Field(min_length=1, max_length=200)
    capacity_levels: tuple[float, ...] = Field(min_length=2)
    mean_by_level: tuple[float, ...] = Field(min_length=2)
    seed_support_by_level: tuple[int, ...] = Field(min_length=2)
    ols_slope_per_capacity_unit: float
    complete_support: bool

    @model_validator(mode="after")
    def validate_alignment(self) -> ActorCapacityCurve:
        lengths = {
            len(self.capacity_levels),
            len(self.mean_by_level),
            len(self.seed_support_by_level),
        }
        if lengths != {len(self.capacity_levels)}:
            raise ValueError("per-level series must align")
        if tuple(sorted(self.capacity_levels)) != self.capacity_levels:
            raise ValueError("capacity levels must be ascending")
        return self


class ActorSlopeComparison(VecCampaignModel):
    """Descriptive comparison of two actors' capacity responses."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["vec-actor-slope-comparison-1.0"] = "vec-actor-slope-comparison-1.0"
    primary_metric_key: str = Field(min_length=1)
    curves: tuple[ActorCapacityCurve, ...] = Field(min_length=2, max_length=2)
    shared_capacity_levels: tuple[float, ...] = Field(min_length=2)
    delta_by_level_first_minus_second: tuple[float, ...] = Field(min_length=2)
    winner_by_level: tuple[str, ...] = Field(min_length=2)
    slope_difference_first_minus_second: float
    crossover_rule_applicable: bool
    crossover_detected: bool
    crossover_rule: Literal[
        "winner_reversed_between_highest_and_lowest_level_with_complete_support"
    ] = "winner_reversed_between_highest_and_lowest_level_with_complete_support"
    descriptive_non_causal: Literal[True] = True
    confirmatory: Literal[False] = False
    significance_claimed: Literal[False] = False
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"

    @model_validator(mode="after")
    def validate_series(self) -> ActorSlopeComparison:
        expected = len(self.shared_capacity_levels)
        if (
            len(self.delta_by_level_first_minus_second) != expected
            or len(self.winner_by_level) != expected
        ):
            raise ValueError("per-level series must align with the shared levels")
        if self.crossover_detected and not self.crossover_rule_applicable:
            raise ValueError("a crossover cannot be detected when the rule is inapplicable")
        return self


def compare_actor_capacity_slopes(
    first: VecCampaignAnalysis,
    second: VecCampaignAnalysis,
    *,
    first_actor_id: str,
    second_actor_id: str,
    expected_seed_count: int,
) -> ActorSlopeComparison:
    """Compare two per-actor campaign analyses descriptively.

    Both analyses must carry the same primary endpoint and the same capacity
    levels (parsed from the shared `cap-<value>` arm-label convention); each
    level's seed support is reported, and the predeclared binary crossover
    rule applies only when both endpoint levels have complete support in both
    curves.
    """

    if first_actor_id == second_actor_id:
        raise VecCampaignError("SLOPE_ACTORS_IDENTICAL: two distinct actors are required")
    if first.primary_metric_key != second.primary_metric_key:
        raise VecCampaignError(
            "SLOPE_METRIC_MISMATCH: both analyses must share the primary endpoint"
        )
    first_curve = _curve(first, first_actor_id, expected_seed_count)
    second_curve = _curve(second, second_actor_id, expected_seed_count)
    if first_curve.capacity_levels != second_curve.capacity_levels:
        raise VecCampaignError(
            "SLOPE_LEVELS_MISMATCH: both actors must be measured at identical levels"
        )

    deltas = tuple(
        a - b for a, b in zip(first_curve.mean_by_level, second_curve.mean_by_level, strict=True)
    )
    winners = tuple(
        first_actor_id if delta > 0 else second_actor_id if delta < 0 else "tie" for delta in deltas
    )
    applicable = (
        first_curve.complete_support
        and second_curve.complete_support
        and winners[0] != "tie"
        and winners[-1] != "tie"
    )
    detected = applicable and winners[0] != winners[-1]
    return ActorSlopeComparison(
        primary_metric_key=first.primary_metric_key,
        curves=(first_curve, second_curve),
        shared_capacity_levels=first_curve.capacity_levels,
        delta_by_level_first_minus_second=deltas,
        winner_by_level=winners,
        slope_difference_first_minus_second=(
            first_curve.ols_slope_per_capacity_unit - second_curve.ols_slope_per_capacity_unit
        ),
        crossover_rule_applicable=applicable,
        crossover_detected=detected,
    )


def _curve(
    analysis: VecCampaignAnalysis, actor_id: str, expected_seed_count: int
) -> ActorCapacityCurve:
    levels: list[tuple[float, float, int]] = []
    for row in analysis.primary_descriptives:
        capacity = _capacity_from_label(row.arm_label)
        levels.append((capacity, row.mean, len(row.seed_values)))
    if len(levels) < 2:
        raise VecCampaignError("SLOPE_TOO_FEW_LEVELS: at least two capacity levels are needed")
    levels.sort(key=lambda item: item[0])
    capacities = tuple(item[0] for item in levels)
    if len(set(capacities)) != len(capacities):
        raise VecCampaignError("SLOPE_DUPLICATE_LEVELS: capacity levels must be distinct")
    means = tuple(item[1] for item in levels)
    supports = tuple(item[2] for item in levels)
    return ActorCapacityCurve(
        actor_id=actor_id,
        capacity_levels=capacities,
        mean_by_level=means,
        seed_support_by_level=supports,
        ols_slope_per_capacity_unit=_ols_slope(capacities, means),
        complete_support=all(support >= expected_seed_count for support in supports),
    )


def _capacity_from_label(label: str) -> float:
    prefix = "cap-"
    if not label.startswith(prefix):
        raise VecCampaignError(
            f"SLOPE_LABEL_UNPARSEABLE: arm label {label!r} does not follow cap-<value>"
        )
    try:
        return float(label[len(prefix) :])
    except ValueError as exc:
        raise VecCampaignError(
            f"SLOPE_LABEL_UNPARSEABLE: arm label {label!r} does not follow cap-<value>"
        ) from exc


def _ols_slope(x_values: tuple[float, ...], y_values: tuple[float, ...]) -> float:
    count = len(x_values)
    mean_x = sum(x_values) / count
    mean_y = sum(y_values) / count
    denominator = sum((x - mean_x) ** 2 for x in x_values)
    if denominator == 0:
        raise VecCampaignError("SLOPE_DEGENERATE: capacity levels have no spread")
    return (
        sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values, strict=True))
        / denominator
    )


def render_slope_comparison_markdown(comparison: ActorSlopeComparison) -> str:
    """Render one deterministic descriptive cross-actor report."""

    first, second = comparison.curves
    lines = [
        "# Cross-actor capacity-slope comparison (descriptive)",
        "",
        "**Owner-approved candidate evidence. Descriptive and non-causal; no "
        "confirmatory or significance claim is made by this report.**",
        "",
        f"- Method: `{comparison.method_version}`",
        f"- Primary endpoint: `{comparison.primary_metric_key}`",
        f"- Crossover rule: `{comparison.crossover_rule}`",
        f"- Rule applicable: {comparison.crossover_rule_applicable} — "
        f"crossover detected: **{comparison.crossover_detected}**",
        "",
        "## Per-level means and winners",
        "",
        f"| Capacity | `{first.actor_id}` | `{second.actor_id}` | Δ (first − second) "
        "| Winner | Support |",
        "|---:|---:|---:|---:|---|---|",
    ]
    for index, level in enumerate(comparison.shared_capacity_levels):
        lines.append(
            f"| {level} | {first.mean_by_level[index]:.6f} "
            f"| {second.mean_by_level[index]:.6f} "
            f"| {comparison.delta_by_level_first_minus_second[index]:+.6f} "
            f"| {comparison.winner_by_level[index]} "
            f"| {first.seed_support_by_level[index]}/{second.seed_support_by_level[index]} |"
        )
    lines += [
        "",
        "## Slopes (ordinary least squares over capacity)",
        "",
        f"- `{first.actor_id}`: {first.ols_slope_per_capacity_unit:+.6f} per capacity unit"
        f" (complete support: {first.complete_support})",
        f"- `{second.actor_id}`: {second.ols_slope_per_capacity_unit:+.6f} per capacity unit"
        f" (complete support: {second.complete_support})",
        f"- Difference (first − second): {comparison.slope_difference_first_minus_second:+.6f}",
        "",
    ]
    return "\n".join(lines)
