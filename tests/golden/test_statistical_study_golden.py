from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import fixed_study_clock, paired_study_config, study_collections

from traffictwin.experiments.statistical_study import evaluate_paired_statistical_study

EXPECTED = Path("tests/golden/expected/statistical_study_known_effect.json")


def test_known_paired_effect_matches_golden_projection() -> None:
    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    actual = {
        "study_id": study.study_id,
        "status": study.status.value,
        "synthetic": study.synthetic,
        "config_fingerprint": study.config_fingerprint,
        "metric_unit": study.metric_unit,
        "eligible_random_seeds": study.pairing_audit.eligible_random_seeds,
        "paired_differences": [row.paired_difference for row in study.observations],
        "estimate": study.estimate.model_dump(mode="json"),
        "bootstrap_interval": {
            "method": study.bootstrap_interval.method,
            "lower": study.bootstrap_interval.lower,
            "upper": study.bootstrap_interval.upper,
            "repetitions": study.bootstrap_interval.repetitions,
            "seed": study.bootstrap_interval.seed,
        },
        "randomisation_test": {
            "mode": study.randomisation_test.mode,
            "observed_statistic": study.randomisation_test.observed_statistic,
            "p_value": study.randomisation_test.p_value,
            "evaluated_assignments": study.randomisation_test.evaluated_assignments,
        },
        "effect_sizes": {
            "mean_paired_difference": study.effect_sizes.mean_paired_difference,
            "cohen_dz": study.effect_sizes.cohen_dz,
            "matched_pairs_rank_biserial": (study.effect_sizes.matched_pairs_rank_biserial),
            "variation_favourable_count": (study.effect_sizes.variation_favourable_count),
            "baseline_favourable_count": study.effect_sizes.baseline_favourable_count,
            "tie_count": study.effect_sizes.tie_count,
            "cliffs_delta": study.effect_sizes.cliffs_delta,
        },
        "compatibility_signature_fingerprint": study.compatibility_signature_fingerprint,
        "provenance": study.provenance,
        "fingerprint": study.fingerprint(),
    }

    assert actual == json.loads(EXPECTED.read_text(encoding="utf-8"))
