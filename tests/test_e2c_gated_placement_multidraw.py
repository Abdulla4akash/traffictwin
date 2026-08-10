from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_e2c_gated_placement_multidraw import (  # noqa: E402
    mechanism_record,
    paired_differences,
    primary_summary,
    verify_manifest_snapshot,
    write_raw_evidence_index,
)
from run_e2c_gated_placement_multidraw import (  # noqa: E402
    initialise_or_verify_campaign_root,
    verify_order_and_prior_gates,
    verify_review_gate,
    write_json_new,
)
from validate_e2c_gated_placement_multidraw import (  # noqa: E402
    cell_name,
    compare_cross_arm,
    format_command,
)

MANIFEST_PATH = ROOT / "docs/evaluation/e2c/e2c_gated_placement_multidraw_manifest_v1.json"


def frozen_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_freezes_only_the_eight_authorised_cells() -> None:
    manifest = frozen_manifest()
    observed = [(cell["fleet_seed"], cell["arm"]) for cell in manifest["full_cell_order"]]
    assert observed == [
        (1, "ingress_dla"),
        (1, "dla"),
        (2, "ingress_dla"),
        (2, "dla"),
        (3, "ingress_dla"),
        (3, "dla"),
        (4, "ingress_dla"),
        (4, "dla"),
    ]
    assert set(manifest["arms"]) == {"ingress_dla", "dla"}
    assert manifest["smoke_gate"]["total_runs"] == 16
    assert manifest["design"]["primary_replication_set"] == [1, 2, 3, 4]
    assert manifest["design"]["pilot_seed_excluded_from_primary_inference"] == 0
    assert manifest["repositories"]["vec_env"]["modification_allowed"] is False


def test_manifest_sidecar_matches_frozen_bytes() -> None:
    observed = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    assert MANIFEST_PATH.with_suffix(".sha256").read_text().split()[0] == observed


def test_command_template_changes_only_declared_cell_values(tmp_path: Path) -> None:
    manifest = frozen_manifest()
    cell = manifest["full_cell_order"][4]
    command = format_command(manifest, cell, tmp_path, max_steps=10)
    assert command[command.index("--max-steps") + 1] == "10"
    assert command[command.index("--fleet-seed") + 1] == "3"
    assert command[command.index("--rsu-lb") + 1] == "ingress_dla"
    assert command[command.index("--rsu-backhaul-ms") + 1] == "0.0"
    assert command[command.index("--k8s-scale") + 1] == "off"
    assert "off" not in [command[command.index("--rsu-lb") + 1]]


def test_primary_summary_uses_four_draws_and_df3_interval() -> None:
    result = primary_summary([-0.02, -0.01, -0.03, -0.04])
    assert result["n_fleet_draws"] == 4
    assert result["confidence_interval"]["degrees_of_freedom"] == 3
    assert result["seed0_included"] is False
    assert result["tasks_used_as_independent_replicates"] is False
    assert result["sign_counts"] == {"negative": 4, "zero": 0, "positive": 0}
    assert result["mean"] == pytest.approx(-0.025)
    assert result["sample_standard_deviation"] == pytest.approx(0.012909944487358056)
    assert result["standard_error"] == pytest.approx(0.006454972243679028)
    assert result["confidence_interval"]["critical_value"] == pytest.approx(3.182446305284263)
    assert result["confidence_interval"]["lower"] == pytest.approx(-0.045542602567608795)
    assert result["confidence_interval"]["upper"] == pytest.approx(-0.0044573974323912115)
    assert result["decision"] == (
        "evidence_of_directional_difference_within_bounded_four_draw_replication"
    )


def test_primary_summary_refuses_seed0_augmented_sample() -> None:
    with pytest.raises(ValueError, match="exactly four"):
        primary_summary([-0.02, -0.01, -0.03, -0.04, -0.02])


def test_primary_difference_is_dla_minus_ingress_dla() -> None:
    records = {
        1: {
            "ingress_dla": {"offered_task_deadline_attainment": 0.72},
            "dla": {"offered_task_deadline_attainment": 0.69},
        },
        2: {
            "ingress_dla": {"offered_task_deadline_attainment": 0.68},
            "dla": {"offered_task_deadline_attainment": 0.70},
        },
    }
    assert paired_differences(records, ("offered_task_deadline_attainment",)) == pytest.approx(
        {"1": -0.03, "2": 0.02}
    )


def test_review_gate_requires_exact_approve_and_identity(tmp_path: Path) -> None:
    review = tmp_path / "review.json"
    identities = {"traffictwin_commit": "tt", "vec_env_commit": "vec"}
    payload = {
        "verdict": "APPROVE_WITH_MINOR_FIXES",
        "traffictwin_commit": "tt",
        "vec_env_commit": "vec",
        "manifest_sha256": "manifest",
    }
    review.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Claude APPROVE mismatch"):
        verify_review_gate(review, identities, "manifest")
    payload["verdict"] = "APPROVE"
    review.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_review_gate(review, identities, "manifest")["verdict"] == "APPROVE"
    payload["traffictwin_commit"] = "drift"
    review.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Claude APPROVE mismatch"):
        verify_review_gate(review, identities, "manifest")


def test_campaign_root_and_json_writes_refuse_overwrite(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest = {"outputs": {"raw_root": str(tmp_path / "raw")}}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    initialise_or_verify_campaign_root(manifest_path, manifest, 1)
    with pytest.raises(RuntimeError, match="undeclared pre-launch entries"):
        initialise_or_verify_campaign_root(manifest_path, manifest, 1)
    destination = tmp_path / "evidence.json"
    write_json_new(destination, {"status": "first"})
    with pytest.raises(FileExistsError):
        write_json_new(destination, {"status": "replacement"})


def test_analysis_refuses_manifest_snapshot_drift_and_root_index_overwrite(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest = {"outputs": {"raw_root": str(tmp_path)}}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    snapshot = tmp_path / "manifest_snapshot.json"
    snapshot.write_bytes(manifest_path.read_bytes())
    (tmp_path / "manifest_snapshot.sha256").write_text(
        f"{hashlib.sha256(snapshot.read_bytes()).hexdigest()}  manifest_snapshot.json\n",
        encoding="utf-8",
    )
    verify_manifest_snapshot(manifest_path, manifest, tmp_path)
    snapshot.write_text('{"drift": true}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="snapshot differs"):
        verify_manifest_snapshot(manifest_path, manifest, tmp_path)
    snapshot.write_bytes(manifest_path.read_bytes())
    write_raw_evidence_index(tmp_path)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_raw_evidence_index(tmp_path)


def write_cross_arm_run(root: Path, *, action: int = 1, logit_delta: float = 0.0) -> dict:
    root.mkdir(parents=True)
    np.savez_compressed(
        root / "per_step.npz",
        slot_tier=np.array([1], dtype=np.int8),
        slot_is_ev=np.array([True], dtype=np.bool_),
        veh_action=np.array([[action]], dtype=np.int8),
        n_local=np.array([0], dtype=np.int32),
        n_v2i=np.array([1], dtype=np.int32),
        n_v2v=np.array([0], dtype=np.int32),
        veh_actor_logits=np.array([[[0.0, 1.0 + logit_delta, 0.0]]], dtype=np.float32),
    )
    np.savez_compressed(
        root / "per_task.npz",
        task_active=np.ones((1, 1, 1), dtype=np.bool_),
        task_type=np.zeros((1, 1, 1), dtype=np.int8),
    )
    return {"run_dir": str(root), "summary": {"n_offered": 1.0}}


def test_cross_arm_identity_accepts_frozen_logit_contract(tmp_path: Path) -> None:
    ingress = write_cross_arm_run(tmp_path / "ingress")
    dla = write_cross_arm_run(tmp_path / "dla", logit_delta=1e-6)
    result = compare_cross_arm(ingress, dla, frozen_manifest())
    assert result["pass"] is True
    assert result["exact_fields"]["vehicle_action"] is True
    assert result["actor_logit_diagnostic"]["maximum_absolute_difference"] <= 1e-5


def test_cross_arm_identity_fails_on_one_actor_action(tmp_path: Path) -> None:
    ingress = write_cross_arm_run(tmp_path / "ingress")
    dla = write_cross_arm_run(tmp_path / "dla", action=0)
    result = compare_cross_arm(ingress, dla, frozen_manifest())
    assert result["pass"] is False
    assert result["exact_fields"]["vehicle_action"] is False


def test_cross_arm_identity_fails_if_logit_tolerance_is_breached(
    tmp_path: Path,
) -> None:
    ingress = write_cross_arm_run(tmp_path / "ingress")
    dla = write_cross_arm_run(tmp_path / "dla", logit_delta=2e-5)
    result = compare_cross_arm(ingress, dla, frozen_manifest())
    assert result["pass"] is False
    assert result["actor_logit_diagnostic"]["pass"] is False


def test_order_gate_refuses_silently_missing_prior_cell(tmp_path: Path) -> None:
    manifest = frozen_manifest()
    manifest["outputs"]["raw_root"] = str(tmp_path)
    second = manifest["full_cell_order"][1]
    with pytest.raises(RuntimeError, match="prior cell status missing"):
        verify_order_and_prior_gates(manifest, second)


def test_order_gate_requires_prior_pair_before_next_seed(tmp_path: Path) -> None:
    manifest = frozen_manifest()
    manifest["outputs"]["raw_root"] = str(tmp_path)
    for cell in manifest["full_cell_order"][:2]:
        root = tmp_path / "cells" / cell_name(cell)
        root.mkdir(parents=True)
        (root / "cell_status.json").write_text('{"status":"passed"}')
    third = manifest["full_cell_order"][2]
    with pytest.raises(RuntimeError, match="pair did not pass"):
        verify_order_and_prior_gates(manifest, third)


def test_mechanism_record_uses_only_recorded_paths(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    task = {
        "task_ingress_rsu": np.array([[[0, 1], [0, -1]]], dtype=np.int16),
        "task_selected_execution_rsu": np.array([[[1, 1], [0, -1]]], dtype=np.int16),
        "task_execution_rsu": np.array([[[1, 1], [-1, -1]]], dtype=np.int16),
        "task_v2i_admitted": np.array([[[True, True], [False, False]]]),
        "task_forwarded": np.array([[[True, False], [False, False]]]),
        "task_met": np.array([[[True, False], [False, False]]]),
        "task_outcome": np.array([[[1, 2], [3, 0]]], dtype=np.int8),
        "task_lat_ms": np.array([[[10.0, 30.0], [100.0, 0.0]]], dtype=np.float32),
    }
    np.savez_compressed(root / "per_task.npz", **task)
    path = {
        "selected_target_count_per_rsu": [1, 2],
        "actual_execution_count_per_rsu": [0, 2],
        "forwarded_admitted_task_count": 1,
        "forwarded_share_of_admitted_v2i": 0.5,
        "imbalance_diagnostic": {"value": 1.0},
        "maximum_execution_share": 1.0,
        "ingress_to_execution_pair_matrix": [[0, 1], [0, 1]],
    }
    (root / "summary.json").write_text(json.dumps({"v2i_path_metrics": path}), encoding="utf-8")
    result = mechanism_record(root, 2)
    assert result["gate_rejected_v2i_count_by_selected_rsu"] == [1, 0]
    assert result["deadline_met_admitted_v2i_count_by_execution_rsu"] == [0, 1]
    assert result["mean_admitted_v2i_latency_ms_by_execution_rsu"] == [None, 20.0]
    assert result["recorded_backlog_inferred"] is False
