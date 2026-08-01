from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from gpu.real_breward.evaluate_fixed_grid import CAPACITY_PER_SLOT, EVALUATION_EPISODES
from gpu.real_breward.run_campaign import (
    EFFECTIVE_TIMESTEPS,
    EXPECTED_UPDATES,
    MODEL_SEEDS,
    PREDECLARATION_RELATIVE_PATH,
    campaign_jobs,
    verify_approval,
)


def test_breward_matrix_is_matched_and_full_scale() -> None:
    jobs = campaign_jobs()
    assert len(jobs) == 10
    assert MODEL_SEEDS == (200, 201, 202, 203, 204)
    assert EXPECTED_UPDATES == 781
    assert EFFECTIVE_TIMESTEPS == 4_998_400
    assert CAPACITY_PER_SLOT == (2.5, 1.5, 1.0, 0.75)
    assert EVALUATION_EPISODES == 32
    assert {(job.treatment, job.baseline_alpha) for job in jobs} == {
        ("capacity_aware_alpha_0_7", 0.7),
        ("capacity_aware_alpha_1_0", 1.0),
    }
    assert all(job.observation_dimension == 19 for job in jobs)
    for seed in MODEL_SEEDS:
        assert sum(job.model_seed == seed for job in jobs) == 2


def test_breward_approval_binds_design_and_harness(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    predeclaration = repo / PREDECLARATION_RELATIVE_PATH
    harness = repo / "gpu/real_breward/run_campaign.py"
    predeclaration.parent.mkdir(parents=True)
    harness.parent.mkdir(parents=True)
    predeclaration.write_text("frozen design\n", encoding="utf-8")
    harness.write_text("frozen harness\n", encoding="utf-8")
    receipt = repo / "approval.json"
    receipt.write_text(
        json.dumps(
            {
                "approved": True,
                "held_out_authorised": False,
                "predeclaration_path": PREDECLARATION_RELATIVE_PATH,
                "predeclaration_sha256": hashlib.sha256(predeclaration.read_bytes()).hexdigest(),
                "harness_sha256": {
                    "gpu/real_breward/run_campaign.py": hashlib.sha256(
                        harness.read_bytes()
                    ).hexdigest()
                },
            }
        ),
        encoding="utf-8",
    )
    assert verify_approval(repo, receipt)["approved"] is True
    harness.write_text("changed harness\n", encoding="utf-8")
    with pytest.raises(ValueError, match="approved harness bytes changed"):
        verify_approval(repo, receipt)
