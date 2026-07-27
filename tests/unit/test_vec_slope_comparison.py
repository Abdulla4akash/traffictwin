"""Tests for the descriptive cross-actor capacity-slope comparison."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from traffictwin.experiments.statistical_study import (
    PairedStudyConfig,
    evaluate_paired_statistical_study,
)
from traffictwin.integration.vec_campaign.analysis import (
    VecArmDescriptives,
    VecCampaignAnalysis,
    VecCampaignComparison,
)
from traffictwin.integration.vec_campaign.service import VecCampaignError
from traffictwin.integration.vec_campaign.slope_comparison import (
    compare_actor_capacity_slopes,
)
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue

NOW = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


def _analysis(actor: str, means_by_cap: dict[str, float]) -> VecCampaignAnalysis:
    """Build a minimal analysis artifact carrying only what slopes consume."""

    def _metric(run_id: str, seed: int, arm: str, value: float) -> MetricValue:
        return MetricValue(
            metric_key="tos.task.deadline_success.rate",
            status=MetricStatus.AVAILABLE,
            value=value,
            unit="ratio",
            scope="run",
            implementation_version="test-1.0",
            run_id=run_id,
            experiment_id="slope-unit",
            seed_id=arm,
            algorithm=actor,
            checkpoint=f"checkpoints/{actor}.npz",
            random_seed=seed,
            synthetic=True,
            environment="randy-vec",
            environment_version="v2",
            environment_commit="0" * 40,
            computed_at=NOW,
        )

    collections = [
        MetricCollection(
            run_id=f"{actor}-{arm}-{seed}",
            metric_version="test-1.0",
            results=[_metric(f"{actor}-{arm}-{seed}", seed, arm, value + seed * 1e-4)],
            unavailable_count=0,
            partial_count=0,
            generated_at=NOW,
            input_fingerprint="f" * 64,
        )
        for arm, value in means_by_cap.items()
        for seed in (0, 1, 2)
    ]
    config = PairedStudyConfig(
        experiment_id="slope-unit",
        baseline_seed_id=next(iter(means_by_cap)),
        variation_seed_id=list(means_by_cap)[1],
        algorithm=actor,
        checkpoint=f"checkpoints/{actor}.npz",
        metric_key="tos.task.deadline_success.rate",
        bootstrap_repetitions=1_000,
        randomisation_repetitions=1_000,
        expected_random_seeds=[0, 1, 2],
    )
    study = evaluate_paired_statistical_study(collections, config)
    comparison = VecCampaignComparison(
        variation_label=list(means_by_cap)[1],
        study_status=study.status.value,
        admitted_pair_count=study.pairing_audit.eligible_pair_count,
        study=study,
    )
    descriptives = [
        VecArmDescriptives(
            arm_label=arm,
            metric_key="tos.task.deadline_success.rate",
            seed_values={str(seed): value + seed * 1e-4 for seed in (0, 1, 2)},
            mean=value + 1e-4,
            minimum=value,
            maximum=value + 2e-4,
        )
        for arm, value in means_by_cap.items()
    ]
    return VecCampaignAnalysis(
        experiment_id="slope-unit",
        design_fingerprint="a" * 64,
        campaign_status="completed",
        primary_metric_key="tos.task.deadline_success.rate",
        baseline_label=next(iter(means_by_cap)),
        admitted_collection_count=len(collections),
        comparisons=[comparison],
        primary_descriptives=descriptives,
        generated_at_utc=NOW.isoformat(),
        limitations=["synthetic slope-comparison fixture"],
    )


def test_crossover_detected_when_winners_reverse_with_complete_support() -> None:
    first = _analysis("actor_a", {"cap-2.5": 0.80, "cap-1.0": 0.60})
    second = _analysis("actor_b", {"cap-2.5": 0.75, "cap-1.0": 0.70})

    comparison = compare_actor_capacity_slopes(
        first,
        second,
        first_actor_id="actor_a",
        second_actor_id="actor_b",
        expected_seed_count=3,
    )

    assert comparison.shared_capacity_levels == (1.0, 2.5)
    assert comparison.winner_by_level == ("actor_b", "actor_a")
    assert comparison.crossover_rule_applicable is True
    assert comparison.crossover_detected is True
    assert comparison.confirmatory is False
    assert comparison.significance_claimed is False


def test_no_crossover_when_one_actor_dominates() -> None:
    first = _analysis("actor_a", {"cap-2.5": 0.80, "cap-1.0": 0.78})
    second = _analysis("actor_b", {"cap-2.5": 0.70, "cap-1.0": 0.69})

    comparison = compare_actor_capacity_slopes(
        first,
        second,
        first_actor_id="actor_a",
        second_actor_id="actor_b",
        expected_seed_count=3,
    )

    assert comparison.crossover_detected is False
    assert set(comparison.winner_by_level) == {"actor_a"}


def test_incomplete_support_makes_the_rule_inapplicable() -> None:
    first = _analysis("actor_a", {"cap-2.5": 0.80, "cap-1.0": 0.60})
    second = _analysis("actor_b", {"cap-2.5": 0.75, "cap-1.0": 0.70})

    comparison = compare_actor_capacity_slopes(
        first,
        second,
        first_actor_id="actor_a",
        second_actor_id="actor_b",
        expected_seed_count=5,
    )

    assert comparison.crossover_rule_applicable is False
    assert comparison.crossover_detected is False


def test_mismatched_levels_and_identical_actors_refuse() -> None:
    first = _analysis("actor_a", {"cap-2.5": 0.80, "cap-1.0": 0.60})
    second = _analysis("actor_b", {"cap-2.5": 0.75, "cap-1.5": 0.70})

    with pytest.raises(VecCampaignError, match="SLOPE_LEVELS_MISMATCH"):
        compare_actor_capacity_slopes(
            first,
            second,
            first_actor_id="actor_a",
            second_actor_id="actor_b",
            expected_seed_count=3,
        )
    with pytest.raises(VecCampaignError, match="SLOPE_ACTORS_IDENTICAL"):
        compare_actor_capacity_slopes(
            first,
            first,
            first_actor_id="actor_a",
            second_actor_id="actor_a",
            expected_seed_count=3,
        )


def test_rendered_report_is_deterministic_and_descriptive() -> None:
    from traffictwin.integration.vec_campaign.slope_comparison import (
        render_slope_comparison_markdown,
    )

    first = _analysis("actor_a", {"cap-2.5": 0.80, "cap-1.0": 0.60})
    second = _analysis("actor_b", {"cap-2.5": 0.75, "cap-1.0": 0.70})
    comparison = compare_actor_capacity_slopes(
        first,
        second,
        first_actor_id="actor_a",
        second_actor_id="actor_b",
        expected_seed_count=3,
    )

    report = render_slope_comparison_markdown(comparison)

    assert "Descriptive and non-causal" in report
    assert "crossover detected: **True**" in report
    assert "actor_a" in report and "actor_b" in report
    assert render_slope_comparison_markdown(comparison) == report
