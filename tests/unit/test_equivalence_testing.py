from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from tests.statistical_helpers import (
    FIXED_STUDY_TIME,
    fixed_study_clock,
    study_collection,
    study_collections,
)
from traffictwin.experiments.equivalence_testing import (
    EquivalenceComponentStatus,
    EquivalenceConclusion,
    EquivalenceMarginBasis,
    EquivalenceStudyConfig,
    EquivalenceStudyStatus,
    _student_t_cdf,
    _student_t_quantile,
    equivalence_study_to_csv,
    equivalence_study_to_markdown,
    equivalence_testing_contract,
    evaluate_equivalence_study,
)
from traffictwin.experiments.statistical_study import PairExclusionCode
from traffictwin.metrics.results import MetricCollection, MetricStatus


def _config(**updates: object) -> EquivalenceStudyConfig:
    payload: dict[str, object] = {
        "experiment_id": "exp-paired",
        "baseline_seed_id": "seed-baseline",
        "variation_seed_id": "seed-variation",
        "algorithm": "policy-a",
        "metric_key": "task.completion.rate",
        "equivalence_margin": 0.2,
        "margin_basis": EquivalenceMarginBasis.PROVISIONAL_DESIGN,
        "margin_justification": "Synthetic method-test margin only",
        "expected_random_seeds": [1, 2, 3, 4, 5],
    }
    payload.update(updates)
    return EquivalenceStudyConfig.model_validate(payload)


def test_contract_and_student_t_reference_values_are_pinned() -> None:
    contract = equivalence_testing_contract()

    assert contract.method == "paired_mean_tost_v1"
    assert contract.minimum_pairs == 3
    assert contract.alpha_bounds == {"minimum": 0.005, "maximum": 0.10}
    assert len(contract.fingerprint()) == 64
    assert _student_t_cdf(2.91998558035372, 2) == pytest.approx(0.95, abs=1e-14)
    assert _student_t_quantile(0.95, 2) == pytest.approx(2.91998558035372, abs=1e-13)
    assert _student_t_quantile(0.05, 2) == pytest.approx(-2.91998558035372, abs=1e-13)


def test_known_equivalent_sample_requires_both_one_sided_rejections() -> None:
    study = evaluate_equivalence_study(
        study_collections([-0.05, 0.0, 0.05, 0.02, -0.02]),
        _config(),
        clock=fixed_study_clock,
    )

    assert study.status is EquivalenceStudyStatus.AVAILABLE
    assert study.tost.status is EquivalenceComponentStatus.AVAILABLE
    assert study.tost.conclusion is EquivalenceConclusion.DEMONSTRATED
    assert study.tost.lower_test is not None
    assert study.tost.upper_test is not None
    assert study.tost.lower_test.rejected is True
    assert study.tost.upper_test.rejected is True
    assert study.tost.interval.confidence_level == 0.9
    assert study.tost.interval.strictly_inside_margin is True
    assert study.tost.interval.lower == pytest.approx(-0.03630404259731535)
    assert study.tost.interval.upper == pytest.approx(0.03630404259731535)
    assert study.source_paired_study_fingerprint
    assert study.pairing_audit.eligible_random_seeds == [1, 2, 3, 4, 5]


def test_non_significant_difference_is_not_relabelled_as_equivalence() -> None:
    study = evaluate_equivalence_study(
        study_collections([-0.3, 0.3, -0.3, 0.3, 0.0]),
        _config(),
        clock=fixed_study_clock,
    )

    assert study.tost.mean_paired_difference == 0.0
    assert study.tost.conclusion is EquivalenceConclusion.NOT_DEMONSTRATED
    assert study.tost.lower_test is not None
    assert study.tost.upper_test is not None
    assert study.tost.lower_test.p_value == pytest.approx(0.10514769155917358)
    assert study.tost.upper_test.p_value == pytest.approx(0.10514769155917363)
    assert study.tost.interval.strictly_inside_margin is False
    assert any("does not establish" in warning for warning in study.warnings)


def test_margin_boundary_and_clearly_outside_sample_do_not_demonstrate_equivalence() -> None:
    boundary = evaluate_equivalence_study(
        study_collections([0.15, 0.2, 0.25, 0.2, 0.2]),
        _config(),
        clock=fixed_study_clock,
    )
    outside = evaluate_equivalence_study(
        study_collections([0.25, 0.3, 0.35, 0.3, 0.3]),
        _config(),
        clock=fixed_study_clock,
    )

    assert boundary.tost.conclusion is EquivalenceConclusion.NOT_DEMONSTRATED
    assert boundary.tost.upper_test is not None
    assert boundary.tost.upper_test.p_value == pytest.approx(0.5)
    assert outside.tost.conclusion is EquivalenceConclusion.NOT_DEMONSTRATED
    assert outside.tost.upper_test is not None
    assert outside.tost.upper_test.rejected is False


def test_insufficient_and_zero_variance_cohorts_are_explicitly_unavailable() -> None:
    insufficient = evaluate_equivalence_study(
        study_collections([0.01, -0.01]),
        _config(expected_random_seeds=[1, 2, 3]),
        clock=fixed_study_clock,
    )
    degenerate = evaluate_equivalence_study(
        study_collections([0.1, 0.1, 0.1, 0.1, 0.1]),
        _config(),
        clock=fixed_study_clock,
    )

    assert insufficient.status is EquivalenceStudyStatus.INSUFFICIENT
    assert insufficient.tost.conclusion is EquivalenceConclusion.UNAVAILABLE
    assert insufficient.pairing_audit.missing_expected_random_seeds == [3]
    assert degenerate.status is EquivalenceStudyStatus.DEGENERATE
    assert degenerate.tost.status is EquivalenceComponentStatus.UNAVAILABLE
    assert degenerate.tost.lower_test is None
    assert "zero or invalid variance" in str(degenerate.tost.reason)


def test_sta01_missing_duplicate_and_semantic_exclusions_are_reused() -> None:
    rows = study_collections([0.01, 0.02, 0.03, 0.04, 0.05])
    rows[0] = rows[0].model_copy(update={"input_fingerprint": None})
    rows.append(
        study_collection(
            "variation",
            2,
            None,
            run_id="run-variation-2-unavailable",
            metric_status=MetricStatus.UNAVAILABLE,
        )
    )

    study = evaluate_equivalence_study(rows, _config(), clock=fixed_study_clock)
    codes = {exclusion.code for exclusion in study.pairing_audit.exclusions}

    assert study.status is EquivalenceStudyStatus.AVAILABLE
    assert PairExclusionCode.SOURCE_FINGERPRINT_MISSING in codes
    assert PairExclusionCode.METRIC_UNAVAILABLE in codes


def test_cross_pair_signature_incompatibility_is_not_subgrouped() -> None:
    rows = study_collections([-0.05, 0.0, 0.05, 0.02, -0.02])
    rows[-2] = study_collection(
        "baseline",
        5,
        10.0,
        environment_version="2.0",
    )
    rows[-1] = study_collection(
        "variation",
        5,
        9.98,
        environment_version="2.0",
    )

    study = evaluate_equivalence_study(rows, _config(), clock=fixed_study_clock)

    assert study.status is EquivalenceStudyStatus.INCOMPATIBLE
    assert any(
        exclusion.code is PairExclusionCode.STUDY_SIGNATURE_INCOMPATIBLE
        for exclusion in study.pairing_audit.exclusions
    )
    assert study.tost.conclusion is EquivalenceConclusion.UNAVAILABLE


def test_order_timestamps_and_evaluation_do_not_mutate_or_change_fingerprint() -> None:
    rows = study_collections([-0.05, 0.0, 0.05, 0.02, -0.02])
    snapshot = deepcopy(rows)
    shifted: list[MetricCollection] = [
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
        for collection in rows
    ]
    first = evaluate_equivalence_study(rows, _config(), clock=fixed_study_clock)
    second = evaluate_equivalence_study(
        list(reversed(shifted)),
        _config(expected_random_seeds=[5, 4, 3, 2, 1]),
        clock=lambda: FIXED_STUDY_TIME + timedelta(hours=2),
    )

    assert rows == snapshot
    assert first.fingerprint() == second.fingerprint()
    assert first.tost == second.tost
    assert (
        "ordinary non-significance is not equivalence"
        in equivalence_study_to_markdown(first).lower()
    )
    assert equivalence_study_to_csv(first).count("eligible_pair") == 5


@pytest.mark.parametrize(
    "update",
    [
        {"baseline_seed_id": "seed-variation"},
        {"equivalence_margin": 0.0},
        {"equivalence_margin": float("inf")},
        {"alpha": 0.004},
        {"alpha": 0.101},
        {"expected_random_seeds": [1, 1, 2]},
        {"minimum_pairs": 2},
        {"method": "ordinary_non_significance"},
        {"margin_justification": "too short"},
        {
            "margin_basis": EquivalenceMarginBasis.LITERATURE,
            "margin_reference": None,
        },
    ],
)
def test_config_rejects_unjustified_or_out_of_contract_choices(
    update: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _config(**update)


def test_literature_margin_requires_and_retains_reference() -> None:
    config = _config(
        margin_basis=EquivalenceMarginBasis.LITERATURE,
        margin_justification="Published practical threshold for this metric",
        margin_reference="Example et al. (2026), section 4",
    )

    assert config.margin_reference == "Example et al. (2026), section 4"
    assert config.expected_random_seeds == [1, 2, 3, 4, 5]
