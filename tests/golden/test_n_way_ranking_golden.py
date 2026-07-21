from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import fixed_study_clock, study_collection

from traffictwin.experiments.n_way_ranking import NWayRankingConfig, evaluate_n_way_ranking

EXPECTED = Path("tests/golden/expected/n_way_ranking_known_order.json")


def test_known_n_way_order_and_uncertainty_match_golden_projection() -> None:
    collections = []
    for seed in (1, 2, 3, 4):
        for algorithm, value in {
            "policy-a": 0.90,
            "policy-b": 0.75,
            "policy-c": 0.60,
        }.items():
            collection = study_collection(
                "baseline",
                seed,
                value + seed * 0.01,
                run_id=f"run-{algorithm}-{seed}",
                experiment_id="exp-nway",
                algorithm=algorithm,
            )
            collections.append(
                collection.model_copy(
                    update={
                        "results": [
                            metric.model_copy(update={"seed_id": "seed-family"})
                            for metric in collection.results
                        ]
                    }
                )
            )
    study = evaluate_n_way_ranking(
        collections,
        NWayRankingConfig(
            experiment_id="exp-nway",
            seed_ids=["seed-family"],
            algorithms=["policy-a", "policy-b", "policy-c"],
            metric_key="task.completion.rate",
            expected_random_seeds=[1, 2, 3, 4],
            bootstrap_repetitions=1_000,
            resampling_seed=91,
        ),
        clock=fixed_study_clock,
    )
    entry = study.entries[0]
    actual = {
        "study_id": study.study_id,
        "status": study.status.value,
        "config_fingerprint": study.config_fingerprint,
        "winner_map_entry": study.winner_map.entries[0].model_dump(mode="json"),
        "family_status": entry.status.value,
        "winner_algorithms": entry.winner_algorithms,
        "policy_ranks": [row.model_dump(mode="json") for row in entry.policy_ranks],
        "complete_random_seeds": entry.audit.complete_random_seeds,
        "missing_expected_random_seeds": entry.audit.missing_expected_random_seeds,
        "exclusion_count": entry.audit.exclusion_count,
        "bootstrap": entry.bootstrap.model_dump(mode="json"),
        "compatibility_signature_fingerprint": entry.compatibility_signature_fingerprint,
        "provenance": study.provenance,
        "warnings": study.warnings,
        "fingerprint": study.fingerprint(),
    }

    assert actual == json.loads(EXPECTED.read_text(encoding="utf-8"))
