from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from gpu.real_bmask.evaluate_mask_grid import (
    CAPACITY_PER_SLOT,
    EVALUATION_EPISODES,
    EVALUATION_MODES,
    EVALUATOR_SEED,
)
from gpu.real_bmask.run_campaign import (
    EFFECTIVE_TIMESTEPS,
    EXPECTED_UPDATES,
    MODEL_SEEDS,
    PREDECLARATION_RELATIVE_PATH,
    campaign_jobs,
    verify_approval,
)


def test_bmask_matrix_is_paired_full_scale_and_two_mode() -> None:
    jobs = campaign_jobs()
    assert len(jobs) == 10
    assert MODEL_SEEDS == (300, 301, 302, 303, 304)
    assert EXPECTED_UPDATES == 781
    assert EFFECTIVE_TIMESTEPS == 4_998_400
    assert CAPACITY_PER_SLOT == (2.5, 1.5, 1.0, 0.75)
    assert EVALUATION_MODES == ("unmasked", "masked")
    assert EVALUATION_EPISODES == 32
    assert EVALUATOR_SEED == 43_434_343
    assert {(job.treatment, job.use_action_mask) for job in jobs} == {
        ("capacity_aware_unmasked", False),
        ("capacity_aware_masked", True),
    }
    assert all(job.baseline_alpha == 0.7 for job in jobs)
    assert all(job.observation_dimension == 19 for job in jobs)
    for seed in MODEL_SEEDS:
        assert sum(job.model_seed == seed for job in jobs) == 2


def test_bmask_approval_binds_design_harness_and_data_boundary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    predeclaration = repo / PREDECLARATION_RELATIVE_PATH
    harness = repo / "gpu/real_bmask/run_campaign.py"
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
                    "gpu/real_bmask/run_campaign.py": hashlib.sha256(
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
