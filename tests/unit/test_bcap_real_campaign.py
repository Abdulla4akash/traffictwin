from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from gpu.real_bcap.run_campaign import (
    EFFECTIVE_TIMESTEPS,
    EXPECTED_UPDATES,
    MODEL_SEEDS,
    PREDECLARATION_RELATIVE_PATH,
    campaign_jobs,
    verify_approval,
)


def test_campaign_matrix_is_matched_and_full_scale() -> None:
    jobs = campaign_jobs()
    assert len(jobs) == 10
    assert MODEL_SEEDS == (100, 101, 102, 103, 104)
    assert EXPECTED_UPDATES == 781
    assert EFFECTIVE_TIMESTEPS == 4_998_400
    assert {(job.treatment, job.observation_dimension) for job in jobs} == {
        ("random_capacity_hidden17", 17),
        ("capacity_aware19", 19),
    }
    for seed in MODEL_SEEDS:
        assert sum(job.model_seed == seed for job in jobs) == 2


def test_approval_is_bound_to_exact_predeclaration_bytes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    predeclaration = repo / PREDECLARATION_RELATIVE_PATH
    predeclaration.parent.mkdir(parents=True)
    predeclaration.write_text("frozen design\n", encoding="utf-8")
    digest = hashlib.sha256(predeclaration.read_bytes()).hexdigest()
    receipt_path = repo / "approval.json"
    receipt_path.write_text(
        json.dumps(
            {
                "approved": True,
                "held_out_authorised": False,
                "predeclaration_path": PREDECLARATION_RELATIVE_PATH,
                "predeclaration_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    assert verify_approval(repo, receipt_path)["approved"] is True
    predeclaration.write_text("changed after approval\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after approval"):
        verify_approval(repo, receipt_path)
