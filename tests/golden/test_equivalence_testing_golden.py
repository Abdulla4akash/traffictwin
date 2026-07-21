from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import fixed_study_clock, study_collections

from traffictwin.experiments.equivalence_testing import (
    EquivalenceMarginBasis,
    EquivalenceStudyConfig,
    evaluate_equivalence_study,
)

EXPECTED = Path("tests/golden/expected/equivalence_known_result.json")


def test_known_paired_equivalence_matches_golden_projection() -> None:
    study = evaluate_equivalence_study(
        study_collections([-0.05, 0.0, 0.05, 0.02, -0.02]),
        EquivalenceStudyConfig(
            experiment_id="exp-paired",
            baseline_seed_id="seed-baseline",
            variation_seed_id="seed-variation",
            algorithm="policy-a",
            metric_key="task.completion.rate",
            equivalence_margin=0.2,
            margin_basis=EquivalenceMarginBasis.PROVISIONAL_DESIGN,
            margin_justification="Synthetic golden method-test margin only",
            expected_random_seeds=[1, 2, 3, 4, 5],
        ),
        clock=fixed_study_clock,
    )
    actual = {
        "study_id": study.study_id,
        "status": study.status.value,
        "synthetic": study.synthetic,
        "config": study.config.model_dump(mode="json"),
        "config_fingerprint": study.config_fingerprint,
        "metric_unit": study.metric_unit,
        "eligible_random_seeds": study.pairing_audit.eligible_random_seeds,
        "paired_differences": [row.paired_difference for row in study.observations],
        "tost": study.tost.model_dump(mode="json"),
        "source_paired_study_fingerprint": study.source_paired_study_fingerprint,
        "compatibility_signature_fingerprint": study.compatibility_signature_fingerprint,
        "provenance": study.provenance,
        "warnings": study.warnings,
        "fingerprint": study.fingerprint(),
    }

    assert actual == json.loads(EXPECTED.read_text(encoding="utf-8"))
