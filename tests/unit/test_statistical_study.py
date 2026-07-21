from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from tests.statistical_helpers import (
    FIXED_STUDY_TIME,
    fixed_study_clock,
    paired_study_config,
    study_collection,
    study_collections,
)
from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.experiments.statistical_study import (
    PairExclusionCode,
    PairInterpretation,
    RandomisationMode,
    StatisticalComponentStatus,
    StatisticalStudyStatus,
    evaluate_paired_statistical_study,
    statistical_study_contract,
    statistical_study_pairs_to_csv,
    statistical_study_to_markdown,
)
from traffictwin.metrics.results import MetricCollection, MetricStatus


def test_contract_publishes_bounded_paired_methods() -> None:
    contract = statistical_study_contract()

    assert contract.method_version == "1.0"
    assert contract.minimum_pairs == 3
    assert contract.exact_sign_flip_max_pairs == 16
    assert contract.repetition_bounds == {"minimum": 1_000, "maximum": 100_000}
    assert "Cliff's delta" in " ".join(contract.secondary_effects)
    assert len(contract.fingerprint()) == 64


def test_known_effect_uses_paired_estimate_exact_test_and_effect_sizes() -> None:
    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )

    assert study.status is StatisticalStudyStatus.AVAILABLE
    assert study.synthetic is True
    assert study.estimate.mean_paired_difference == 2.0
    assert study.estimate.sample_sd_paired_difference == 1.0
    assert study.estimate.standard_error == pytest.approx(1 / 3**0.5)
    assert study.bootstrap_interval.lower is not None
    assert study.bootstrap_interval.upper is not None
    assert study.randomisation_test.mode is RandomisationMode.EXACT
    assert study.randomisation_test.evaluated_assignments == 8
    assert study.randomisation_test.p_value == 0.25
    assert study.effect_sizes.cohen_dz == 2.0
    assert study.effect_sizes.matched_pairs_rank_biserial == 1.0
    assert study.effect_sizes.variation_favourable_count == 3
    assert study.effect_sizes.cliffs_delta == "not_calculated_for_paired_primary_design"
    assert len(study.fingerprint()) == 64


def test_known_null_and_minimise_objective_are_descriptive_not_reversed() -> None:
    null = evaluate_paired_statistical_study(
        study_collections([-1.0, 0.0, 1.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    minimise = evaluate_paired_statistical_study(
        study_collections([-3.0, -2.0, -1.0]),
        paired_study_config(objective=ObjectiveDirection.MINIMISE),
        clock=fixed_study_clock,
    )

    assert null.estimate.mean_paired_difference == 0.0
    assert null.randomisation_test.p_value == 1.0
    assert null.effect_sizes.cohen_dz == 0.0
    assert null.effect_sizes.matched_pairs_rank_biserial == 0.0
    assert minimise.estimate.mean_paired_difference == -2.0
    assert minimise.estimate.interpretation is PairInterpretation.FAVOURS_VARIATION
    assert all(
        row.interpretation is PairInterpretation.FAVOURS_VARIATION for row in minimise.observations
    )


def test_thin_support_retains_pairs_but_withholds_inference() -> None:
    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0]),
        paired_study_config(expected_random_seeds=[1, 2, 3]),
        clock=fixed_study_clock,
    )

    assert study.status is StatisticalStudyStatus.INSUFFICIENT
    assert study.pairing_audit.eligible_random_seeds == [1, 2]
    assert study.pairing_audit.missing_expected_random_seeds == [3]
    assert study.estimate.status is StatisticalComponentStatus.UNAVAILABLE
    assert study.bootstrap_interval.lower is None
    assert study.randomisation_test.mode is RandomisationMode.NOT_RUN


def test_pairing_audit_retains_unmatched_unplanned_and_unavailable_inputs() -> None:
    collections = study_collections([1.0, 2.0, 3.0])
    collections.pop()  # variation seed 3 becomes unmatched
    collections.extend(
        [
            study_collection("baseline", 4, 10.0),
            study_collection("variation", 4, 11.0),
            study_collection(
                "variation",
                2,
                None,
                run_id="run-variation-2-unavailable",
                metric_status=MetricStatus.UNAVAILABLE,
            ),
        ]
    )
    study = evaluate_paired_statistical_study(
        collections,
        paired_study_config(expected_random_seeds=[1, 2, 3]),
        clock=fixed_study_clock,
    )

    codes = {item.code for item in study.pairing_audit.exclusions}
    assert study.status is StatisticalStudyStatus.INSUFFICIENT
    assert study.pairing_audit.unmatched_baseline_random_seeds == [3]
    assert PairExclusionCode.RANDOM_SEED_NOT_PREDECLARED in codes
    assert PairExclusionCode.METRIC_UNAVAILABLE in codes
    assert PairExclusionCode.DUPLICATE_PAIRING_KEY not in codes


def test_duplicate_keys_and_mixed_signatures_are_never_selected_by_order() -> None:
    duplicates = [
        *study_collections([1.0, 2.0, 3.0]),
        study_collection("baseline", 1, 9.5, run_id="run-baseline-1-copy"),
    ]
    duplicate_study = evaluate_paired_statistical_study(
        duplicates,
        paired_study_config(),
        clock=fixed_study_clock,
    )
    mixed = study_collections([1.0, 2.0, 3.0])
    mixed[-1] = study_collection(
        "variation",
        3,
        13.0,
        environment_version="2.0",
    )
    mixed_study = evaluate_paired_statistical_study(
        mixed,
        paired_study_config(),
        clock=fixed_study_clock,
    )

    assert duplicate_study.pairing_audit.duplicate_baseline_random_seeds == [1]
    assert duplicate_study.status is StatisticalStudyStatus.INSUFFICIENT
    assert mixed_study.status is StatisticalStudyStatus.INSUFFICIENT
    assert any(
        item.code is PairExclusionCode.PAIR_INCOMPATIBLE
        for item in mixed_study.pairing_audit.exclusions
    )


def test_semantic_contract_and_cross_pair_signature_must_match() -> None:
    metadata = {
        "energy_contract_fingerprint": "contract-a",
    }
    rows: list[MetricCollection] = []
    for seed in [1, 2, 3]:
        rows.extend(
            [
                study_collection(
                    "baseline",
                    seed,
                    1.0,
                    metric_key="task.energy.per_completed_j",
                    unit="J/task",
                    metadata=metadata,
                ),
                study_collection(
                    "variation",
                    seed,
                    1.1,
                    metric_key="task.energy.per_completed_j",
                    unit="J/task",
                    metadata=metadata,
                ),
            ]
        )
    rows[-1] = study_collection(
        "variation",
        3,
        1.1,
        metric_key="task.energy.per_completed_j",
        unit="J/task",
        implementation_version="2.0",
        metadata=metadata,
    )
    config = paired_study_config(metric_key="task.energy.per_completed_j")
    study = evaluate_paired_statistical_study(rows, config, clock=fixed_study_clock)

    assert study.status is StatisticalStudyStatus.INSUFFICIENT
    assert any(
        "implementation version differs" in item.detail for item in study.pairing_audit.exclusions
    )


def test_cross_pair_signature_mismatch_blocks_subgroup_selection() -> None:
    rows = study_collections([1.0, 2.0, 3.0])
    rows[-2] = study_collection(
        "baseline",
        3,
        10.0,
        environment_version="2.0",
    )
    rows[-1] = study_collection(
        "variation",
        3,
        13.0,
        environment_version="2.0",
    )

    study = evaluate_paired_statistical_study(
        rows,
        paired_study_config(),
        clock=fixed_study_clock,
    )

    assert study.status is StatisticalStudyStatus.INCOMPATIBLE
    assert study.pairing_audit.eligible_random_seeds == [1, 2, 3]
    assert any(
        item.code is PairExclusionCode.STUDY_SIGNATURE_INCOMPATIBLE
        for item in study.pairing_audit.exclusions
    )


def test_missing_source_and_semantic_contracts_remain_explicit_exclusions() -> None:
    rows = study_collections([1.0, 2.0, 3.0])
    rows[0] = rows[0].model_copy(update={"input_fingerprint": None})
    energy = [
        study_collection(
            role,
            seed,
            1.0,
            metric_key="task.energy.per_completed_j",
            unit="J/task",
        )
        for seed in [1, 2, 3]
        for role in ["baseline", "variation"]
    ]

    source_study = evaluate_paired_statistical_study(
        rows,
        paired_study_config(),
        clock=fixed_study_clock,
    )
    semantic_study = evaluate_paired_statistical_study(
        energy,
        paired_study_config(metric_key="task.energy.per_completed_j"),
        clock=fixed_study_clock,
    )

    assert PairExclusionCode.SOURCE_FINGERPRINT_MISSING in {
        item.code for item in source_study.pairing_audit.exclusions
    }
    assert PairExclusionCode.SEMANTIC_CONTRACT_UNRESOLVED in {
        item.code for item in semantic_study.pairing_audit.exclusions
    }


def test_large_study_uses_seeded_monte_carlo_and_is_reproducible() -> None:
    differences = [float((seed % 5) - 1) for seed in range(1, 18)]
    config = paired_study_config(expected_random_seeds=list(range(1, 18)))
    first = evaluate_paired_statistical_study(
        study_collections(differences),
        config,
        clock=fixed_study_clock,
    )
    second = evaluate_paired_statistical_study(
        list(reversed(study_collections(differences))),
        config,
        clock=lambda: FIXED_STUDY_TIME + timedelta(days=1),
    )

    assert first.randomisation_test.mode is RandomisationMode.MONTE_CARLO
    assert first.randomisation_test.evaluated_assignments == 1_000
    assert first.randomisation_test.p_value == second.randomisation_test.p_value
    assert first.bootstrap_interval.lower == second.bootstrap_interval.lower
    assert first.bootstrap_interval.upper == second.bootstrap_interval.upper
    assert first.fingerprint() == second.fingerprint()


def test_input_timestamps_and_order_do_not_change_fingerprint_or_mutate_inputs() -> None:
    collections = study_collections([1.0, 2.0, 3.0])
    snapshot = deepcopy(collections)
    shifted = [
        collection.model_copy(
            update={
                "generated_at": FIXED_STUDY_TIME + timedelta(hours=1),
                "results": [
                    collection.results[0].model_copy(
                        update={"computed_at": FIXED_STUDY_TIME + timedelta(hours=1)}
                    )
                ],
            }
        )
        for collection in collections
    ]
    first = evaluate_paired_statistical_study(
        collections,
        paired_study_config(),
        clock=fixed_study_clock,
    )
    second = evaluate_paired_statistical_study(
        list(reversed(shifted)),
        paired_study_config(),
        clock=lambda: FIXED_STUDY_TIME + timedelta(hours=2),
    )

    assert collections == snapshot
    assert first.fingerprint() == second.fingerprint()
    assert "TrafficTwin Paired Statistical Study" in statistical_study_to_markdown(first)
    csv_text = statistical_study_pairs_to_csv(first)
    assert csv_text.count("eligible_pair") == 3


@pytest.mark.parametrize(
    "update",
    [
        {"baseline_seed_id": "seed-variation"},
        {"bootstrap_repetitions": 999},
        {"randomisation_repetitions": 100_001},
        {"confidence_level": 0.79},
        {"expected_random_seeds": [1, 1, 2]},
        {"minimum_pairs": 2},
        {"alternative": "greater"},
    ],
)
def test_config_rejects_post_hoc_or_out_of_contract_choices(update: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        paired_study_config(**update)


def test_common_seed_set_order_is_canonical_in_plan_identity() -> None:
    first = paired_study_config(expected_random_seeds=[3, 1, 2])
    second = paired_study_config(expected_random_seeds=[1, 2, 3])

    assert first.expected_random_seeds == [1, 2, 3]
    assert first.fingerprint() == second.fingerprint()
