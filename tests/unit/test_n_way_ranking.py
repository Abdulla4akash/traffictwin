from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

import pytest
from pydantic import ValidationError

from tests.statistical_helpers import fixed_study_clock, study_collection
from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.experiments.n_way_ranking import (
    NWayComponentStatus,
    NWayExclusionCode,
    NWayRankingConfig,
    NWayRankingStatus,
    evaluate_n_way_ranking,
    n_way_ranking_to_csv,
    n_way_ranking_to_markdown,
)
from traffictwin.metrics.results import MetricCollection, MetricStatus


def _config(**updates: object) -> NWayRankingConfig:
    payload: dict[str, object] = {
        "experiment_id": "exp-nway",
        "seed_ids": ["seed-family"],
        "algorithms": ["policy-a", "policy-b", "policy-c"],
        "metric_key": "task.completion.rate",
        "expected_random_seeds": [1, 2, 3, 4],
        "bootstrap_repetitions": 1_000,
        "resampling_seed": 91,
    }
    payload.update(updates)
    return NWayRankingConfig.model_validate(payload)


def _collection(
    algorithm: str,
    random_seed: int,
    value: float,
    *,
    metric_key: str = "task.completion.rate",
    metric_status: MetricStatus = MetricStatus.AVAILABLE,
    unit: str = "fraction",
    metadata: Mapping[str, object] | None = None,
) -> MetricCollection:
    collection = study_collection(
        "baseline",
        random_seed,
        value,
        run_id=f"run-{algorithm}-{random_seed}",
        experiment_id="exp-nway",
        algorithm=algorithm,
        metric_key=metric_key,
        metric_status=metric_status,
        unit=unit,
        metadata=metadata,
    )
    return collection.model_copy(
        update={
            "results": [
                metric.model_copy(update={"seed_id": "seed-family"})
                for metric in collection.results
            ]
        }
    )


def _complete_rows(seed_count: int = 4) -> list[MetricCollection]:
    values = {"policy-a": 0.90, "policy-b": 0.75, "policy-c": 0.60}
    return [
        _collection(algorithm, seed, value + seed * 0.01)
        for seed in range(1, seed_count + 1)
        for algorithm, value in values.items()
    ]


def test_n_way_ranking_extends_winner_map_with_joint_uncertainty() -> None:
    study = evaluate_n_way_ranking(
        _complete_rows(),
        _config(),
        clock=fixed_study_clock,
    )

    assert study.status is NWayRankingStatus.AVAILABLE
    assert study.entries[0].status is NWayRankingStatus.AVAILABLE
    assert study.entries[0].winner_algorithms == ["policy-a"]
    assert [row.rank for row in study.entries[0].policy_ranks] == [1, 2, 3]
    assert {row.observation_count for row in study.entries[0].policy_ranks} == {4}
    assert all(row.mean_interval_lower is not None for row in study.entries[0].policy_ranks)
    assert all(
        sum(row.rank_frequencies.values()) == pytest.approx(1.0)
        for row in study.entries[0].policy_ranks
    )
    assert study.entries[0].policy_ranks[0].top_rank_frequency == 1.0
    assert study.winner_map.entries[0].policy_scores[0].mean == (
        study.entries[0].policy_ranks[0].mean
    )
    assert "policy_rank" in n_way_ranking_to_csv(study)
    assert "numerical tie, not equivalence" in n_way_ranking_to_markdown(study)


def test_n_way_ranking_respects_minimise_and_explicit_numeric_ties() -> None:
    rows = [
        _collection(algorithm, seed, value)
        for seed in (1, 2, 3)
        for algorithm, value in {
            "policy-a": 10.0,
            "policy-b": 10.0005,
            "policy-c": 12.0,
        }.items()
    ]
    study = evaluate_n_way_ranking(
        rows,
        _config(
            objective=ObjectiveDirection.MINIMISE,
            expected_random_seeds=[1, 2, 3],
            tie_tolerance=0.001,
        ),
        clock=fixed_study_clock,
    )

    entry = study.entries[0]
    assert entry.winner_algorithms == ["policy-a", "policy-b"]
    assert [(row.algorithm, row.rank) for row in entry.policy_ranks] == [
        ("policy-a", 1),
        ("policy-b", 1),
        ("policy-c", 3),
    ]
    assert entry.policy_ranks[-1].regret == pytest.approx(2.0)


def test_missing_policy_endpoint_uses_one_complete_cohort_for_every_policy() -> None:
    rows = [
        row
        for row in _complete_rows()
        if not (row.results[0].algorithm == "policy-c" and row.results[0].random_seed == 4)
    ]
    study = evaluate_n_way_ranking(rows, _config(), clock=fixed_study_clock)

    entry = study.entries[0]
    assert entry.status is NWayRankingStatus.AVAILABLE
    assert entry.audit.complete_random_seeds == [1, 2, 3]
    assert entry.audit.incomplete_random_seeds == [4]
    assert entry.audit.missing_random_seeds_by_algorithm["policy-c"] == [4]
    assert {row.observation_count for row in entry.policy_ranks} == {3}
    assert any(
        item.code is NWayExclusionCode.INCOMPLETE_COMMON_SEED for item in entry.audit.exclusions
    )


def test_thin_complete_cohort_keeps_description_but_not_uncertainty() -> None:
    study = evaluate_n_way_ranking(
        _complete_rows(2),
        _config(expected_random_seeds=[1, 2]),
        clock=fixed_study_clock,
    )

    entry = study.entries[0]
    assert study.status is NWayRankingStatus.INSUFFICIENT
    assert entry.status is NWayRankingStatus.INSUFFICIENT
    assert entry.policy_ranks
    assert entry.bootstrap.status is NWayComponentStatus.UNAVAILABLE
    assert all(row.mean_interval_lower is None for row in entry.policy_ranks)
    assert all(row.uncertainty_reason for row in entry.policy_ranks)


def test_incompatible_seed_is_excluded_not_ranked() -> None:
    rows = _complete_rows()
    changed = rows[-1].model_copy(
        update={
            "results": [
                metric.model_copy(update={"environment_version": "2.0"})
                for metric in rows[-1].results
            ]
        }
    )
    study = evaluate_n_way_ranking(
        [*rows[:-1], changed],
        _config(),
        clock=fixed_study_clock,
    )

    entry = study.entries[0]
    assert entry.status is NWayRankingStatus.AVAILABLE
    assert entry.audit.complete_random_seeds == [1, 2, 3]
    assert entry.audit.incompatible_random_seeds == [4]
    assert {row.observation_count for row in entry.policy_ranks} == {3}
    assert any(
        item.code is NWayExclusionCode.COMMON_SEED_INCOMPATIBLE for item in entry.audit.exclusions
    )


def test_multiple_complete_signatures_make_family_incompatible_without_subgroup_choice() -> None:
    rows = _complete_rows()
    changed = [
        row.model_copy(
            update={
                "results": [
                    metric.model_copy(update={"environment_version": "2.0"})
                    for metric in row.results
                ]
            }
        )
        if row.results[0].random_seed == 4
        else row
        for row in rows
    ]
    study = evaluate_n_way_ranking(changed, _config(), clock=fixed_study_clock)

    entry = study.entries[0]
    assert study.status is NWayRankingStatus.INCOMPATIBLE
    assert entry.status is NWayRankingStatus.INCOMPATIBLE
    assert entry.policy_ranks == []
    assert len(entry.observations) == 4
    assert entry.audit.complete_random_seeds == [1, 2, 3, 4]
    assert any(
        item.code is NWayExclusionCode.FAMILY_SIGNATURE_INCOMPATIBLE
        for item in entry.audit.exclusions
    )


def test_unavailable_and_duplicate_endpoints_remain_visible_missingness() -> None:
    rows = _complete_rows()
    unavailable = _collection(
        "policy-c",
        4,
        0.0,
        metric_status=MetricStatus.UNAVAILABLE,
    )
    duplicate = _collection("policy-b", 3, 0.79)
    # Build a second endpoint with a distinct run ID but the same policy/seed pairing key.
    duplicate = duplicate.model_copy(update={"run_id": "run-policy-b-3-extra"})
    duplicate = duplicate.model_copy(
        update={
            "results": [
                metric.model_copy(update={"run_id": duplicate.run_id})
                for metric in duplicate.results
            ],
            "input_fingerprint": "fingerprint-run-policy-b-3-extra",
        }
    )
    filtered = [
        row
        for row in rows
        if not (row.results[0].algorithm == "policy-c" and row.results[0].random_seed == 4)
    ]
    study = evaluate_n_way_ranking(
        [*filtered, unavailable, duplicate],
        _config(),
        clock=fixed_study_clock,
    )

    codes = {item.code for item in study.entries[0].audit.exclusions}
    assert NWayExclusionCode.METRIC_UNAVAILABLE in codes
    assert NWayExclusionCode.DUPLICATE_POLICY_SEED in codes
    assert study.entries[0].audit.complete_random_seeds == [1, 2]


def test_semantic_contract_mismatch_is_excluded() -> None:
    rows = [
        _collection(
            algorithm,
            seed,
            2.0 + offset,
            metric_key="task.energy.per_completed_task.mean",
            unit="J/task",
            metadata={"energy_contract_fingerprint": fingerprint},
        )
        for seed in (1, 2, 3, 4)
        for algorithm, offset, fingerprint in (
            ("policy-a", 0.0, "contract-a"),
            ("policy-b", 0.1, "contract-a"),
            ("policy-c", 0.2, "contract-b" if seed == 4 else "contract-a"),
        )
    ]
    study = evaluate_n_way_ranking(
        rows,
        _config(metric_key="task.energy.per_completed_task.mean"),
        clock=fixed_study_clock,
    )

    assert study.entries[0].audit.incompatible_random_seeds == [4]
    assert {row.observation_count for row in study.entries[0].policy_ranks} == {3}


def test_results_are_order_stable_deterministic_and_do_not_mutate_inputs() -> None:
    rows = _complete_rows()
    snapshot = deepcopy(rows)
    config = _config()

    first = evaluate_n_way_ranking(rows, config, clock=fixed_study_clock)
    second = evaluate_n_way_ranking(list(reversed(rows)), config, clock=fixed_study_clock)

    assert first.canonical_json() == second.canonical_json()
    assert first.fingerprint() == second.fingerprint()
    assert first.entries[0].bootstrap.seed != config.resampling_seed
    assert rows == snapshot


def test_config_rejects_ambiguous_or_unbounded_plans() -> None:
    with pytest.raises(ValidationError, match="at least 2"):
        _config(algorithms=["policy-a"])
    with pytest.raises(ValidationError, match="duplicates"):
        _config(algorithms=["policy-a", "policy-a"])
    with pytest.raises(ValidationError, match="finite"):
        _config(tie_tolerance=float("inf"))
    with pytest.raises(ValidationError, match="greater than or equal to 1000"):
        _config(bootstrap_repetitions=999)


class TestPerAlgorithmCheckpoints:
    """Reviewed extension: distinct trained actors carry distinct checkpoints."""

    def test_two_actors_with_distinct_checkpoints_rank_together(self) -> None:
        from datetime import UTC, datetime

        from traffictwin.metrics.results import (
            MetricCollection,
            MetricStatus,
            MetricValue,
        )

        now = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)
        collections = []
        for algorithm, checkpoint, base in (
            ("actor_a", "checkpoints/a.npz", 0.8),
            ("actor_b", "checkpoints/b.npz", 0.7),
        ):
            for seed in (0, 1, 2):
                metric = MetricValue(
                    metric_key="tos.task.deadline_success.rate",
                    status=MetricStatus.AVAILABLE,
                    value=base + seed * 1e-3,
                    unit="ratio",
                    scope="run",
                    implementation_version="test-1.0",
                    run_id=f"{algorithm}-{seed}",
                    experiment_id="per-ckpt-unit",
                    seed_id="scenario-x",
                    algorithm=algorithm,
                    checkpoint=checkpoint,
                    random_seed=seed,
                    synthetic=True,
                    environment="randy-vec",
                    environment_version="v2",
                    environment_commit="0" * 40,
                    computed_at=now,
                )
                collections.append(
                    MetricCollection(
                        run_id=f"{algorithm}-{seed}",
                        metric_version="test-1.0",
                        results=[metric],
                        unavailable_count=0,
                        partial_count=0,
                        generated_at=now,
                        input_fingerprint="f" * 64,
                    )
                )
        config = NWayRankingConfig(
            experiment_id="per-ckpt-unit",
            seed_ids=["scenario-x"],
            algorithms=["actor_a", "actor_b"],
            checkpoint_by_algorithm={
                "actor_a": "checkpoints/a.npz",
                "actor_b": "checkpoints/b.npz",
            },
            metric_key="tos.task.deadline_success.rate",
            bootstrap_repetitions=1_000,
            expected_random_seeds=[0, 1, 2],
        )
        study = evaluate_n_way_ranking(collections, config)
        entry = study.winner_map.entries[0]
        assert entry.winner_algorithms == ["actor_a"]

    def test_mutual_exclusion_and_key_coverage_refuse(self) -> None:
        import pytest as _pytest

        with _pytest.raises(ValueError, match="mutually exclusive"):
            NWayRankingConfig(
                experiment_id="x",
                seed_ids=["s"],
                algorithms=["a", "b"],
                checkpoint="one.npz",
                checkpoint_by_algorithm={"a": "a.npz", "b": "b.npz"},
                metric_key="m",
            )
        with _pytest.raises(ValueError, match="keys must equal"):
            NWayRankingConfig(
                experiment_id="x",
                seed_ids=["s"],
                algorithms=["a", "b"],
                checkpoint_by_algorithm={"a": "a.npz"},
                metric_key="m",
            )
