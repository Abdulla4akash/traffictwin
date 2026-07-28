from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from gpu.real_bdomain.evaluate_domain_matrix import (
    CAPACITY_PER_SLOT,
    EVALUATION_EPISODES,
    EVALUATOR_SEED,
    TASK_DOMAINS,
    TASK_PROBABILITIES,
)
from gpu.real_bdomain.run_campaign import (
    EFFECTIVE_TIMESTEPS,
    EXPECTED_UPDATES,
    MODEL_SEEDS,
    PREDECLARATION_RELATIVE_PATH,
    campaign_jobs,
    verify_approval,
)


def test_bdomain_matrix_is_three_by_five_full_scale() -> None:
    jobs = campaign_jobs()
    assert len(jobs) == 15
    assert MODEL_SEEDS == (400, 401, 402, 403, 404)
    assert EXPECTED_UPDATES == 781
    assert EFFECTIVE_TIMESTEPS == 4_998_400
    assert TASK_DOMAINS == ("default", "safety_dominant", "pilot_inspired")
    assert TASK_PROBABILITIES == {
        "default": (0.20, 0.30, 0.50),
        "safety_dominant": (0.50, 0.25, 0.25),
        "pilot_inspired": (0.10, 0.20, 0.70),
    }
    assert CAPACITY_PER_SLOT == (2.5, 0.75)
    assert EVALUATION_EPISODES == 32
    assert EVALUATOR_SEED == 44_444_444
    assert all(job.baseline_alpha == 0.7 for job in jobs)
    assert all(job.use_action_mask is False for job in jobs)
    assert all(job.observation_dimension == 19 for job in jobs)
    for seed in MODEL_SEEDS:
        assert sum(job.model_seed == seed for job in jobs) == 3
    for domain in TASK_DOMAINS:
        assert sum(job.training_domain == domain for job in jobs) == 5


def test_bdomain_approval_binds_design_harness_and_data_boundary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    predeclaration = repo / PREDECLARATION_RELATIVE_PATH
    harness = repo / "gpu/real_bdomain/run_campaign.py"
    predeclaration.parent.mkdir(parents=True)
    harness.parent.mkdir(parents=True)
    predeclaration.write_text("frozen design\n")
    harness.write_text("frozen harness\n")
    receipt = repo / "approval.json"
    receipt.write_text(
        json.dumps(
            {
                "approved": True,
                "held_out_authorised": False,
                "producer_data_authorised_for_colab": False,
                "predeclaration_path": PREDECLARATION_RELATIVE_PATH,
                "predeclaration_sha256": hashlib.sha256(predeclaration.read_bytes()).hexdigest(),
                "harness_sha256": {
                    "gpu/real_bdomain/run_campaign.py": hashlib.sha256(
                        harness.read_bytes()
                    ).hexdigest()
                },
            }
        )
    )
    assert verify_approval(repo, receipt)["approved"] is True
    harness.write_text("changed harness\n")
    with pytest.raises(ValueError, match="approved harness bytes changed"):
        verify_approval(repo, receipt)
