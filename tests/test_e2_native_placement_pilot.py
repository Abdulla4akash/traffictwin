from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_e2_native_placement_pilot import contrast  # noqa: E402
from validate_e2_native_placement_pilot import validate_phase, validate_run  # noqa: E402


def manifest() -> dict:
    return {
        "design": {
            "padded_fleet_width": 2,
            "resolved_cap_tasks_per_rsu": 5,
            "fleet": "uk2030",
            "fleet_seed": 0,
            "arrival_lambda": 1.5,
            "rsu_service_multiplier": 1.0,
            "backhaul_ms": 0.0,
            "rsus": 2,
        },
        "cross_arm_actor_stream_contract": {
            "logit_diagnostic": {
                "absolute_tolerance": 1e-5,
                "interpretation": "diagnostic only",
            }
        },
    }


def write_valid_run(root: Path, *, rsu_lb: str = "jsq") -> Path:
    root.mkdir()
    task_active = np.array([[[True, True], [True, False]]])
    task_outcome = np.array([[[1, 1], [4, 0]]], dtype=np.int8)
    task_met = np.array([[[True, True], [False, False]]])
    task_type = np.zeros((1, 2, 2), dtype=np.int8)
    task_lat = np.array([[[10.0, 20.0], [1000.0, 0.0]]], dtype=np.float32)
    ingress = np.array([[[0, -1], [0, -1]]], dtype=np.int16)
    selected = np.array([[[0, -1], [1, -1]]], dtype=np.int16)
    execution = np.array([[[0, -1], [-1, -1]]], dtype=np.int16)
    forwarded = np.zeros((1, 2, 2), dtype=np.bool_)
    forwarding_ms = np.zeros((1, 2, 2), dtype=np.float32)
    admitted = np.array([[[True, False], [False, False]]])
    np.savez_compressed(
        root / "per_task.npz",
        task_active=task_active,
        task_outcome=task_outcome,
        task_met=task_met,
        task_type=task_type,
        task_lat_ms=task_lat,
        task_ingress_rsu=ingress,
        task_selected_execution_rsu=selected,
        task_execution_rsu=execution,
        task_forwarded=forwarded,
        task_forwarding_latency_ms=forwarding_ms,
        task_v2i_admitted=admitted,
    )
    np.savez_compressed(
        root / "per_step.npz",
        arrivals=np.array([3], dtype=np.int32),
        done=np.array([2], dtype=np.int32),
        lat_sum=np.array([1030.0], dtype=np.float32),
        active=np.array([2], dtype=np.int32),
        n_local=np.array([1], dtype=np.int32),
        n_v2i=np.array([2], dtype=np.int32),
        n_v2v=np.array([0], dtype=np.int32),
        veh_action=np.array([[1, 0]], dtype=np.int8),
        veh_actor_logits=np.zeros((1, 2, 3), dtype=np.float32),
        veh_k=np.array([[2, 1]], dtype=np.int8),
        veh_done=np.array([[1, 1]], dtype=np.int16),
        veh_queue_ms=np.zeros((1, 2), dtype=np.float32),
        veh_best_rsu=np.zeros((1, 2), dtype=np.int16),
        veh_best_v2v=np.zeros((1, 2), dtype=np.int16),
        rsu_busy_ms=np.zeros((1, 2), dtype=np.float32),
        rsu_load=np.zeros((1, 2), dtype=np.int32),
        times=np.array([0.0]),
        slot_tier=np.array([0, 1], dtype=np.int8),
        slot_is_ev=np.array([False, True]),
    )
    summary = {
        "T": 1,
        "maxN": 2,
        "rsu_max_concurrent": 5,
        "fleet": "uk2030",
        "fleet_seed": 0,
        "obs_variant": "onehot17",
        "lambda_arrival": 1.5,
        "rsu_service_mult": 1.0,
        "rsu_lb": rsu_lb,
        "rsu_backhaul_ms": 0.0,
        "k8s_scale": "off",
        "k8s_first_scaleup_s": -1.0,
        "rsu_cap_mode": "reject",
        "substep_queue": "sequential",
        "veh_queue_mode": "conserved",
        "n_offered": 3.0,
        "n_admitted": 2.0,
        "completion": 2 / 3,
        "completion_admitted": 1.0,
        "avg_latency_ms_per_task": 1030 / 3,
        "avg_latency_admitted_ms": 15.0,
        "avg_latency_met_ms": 15.0,
        "v2i_gate_rejected": 0.0,
        "v2i_cap_rejected": 1.0,
        "local_mqd_rejected": 0.0,
        "v2v_mqd_rejected": 0.0,
        "v2i_unavailable": 0.0,
        "v2v_unavailable": 0.0,
        "t1_completion": 2 / 3,
        "t2_completion": 0.0,
        "t3_completion": 0.0,
        "p_local": 1 / 3,
        "p_v2i": 2 / 3,
        "p_v2v": 0.0,
        "avg_energy_j_per_task": 0.1,
        "total_energy_j": 0.3,
        "work_ms": {
            "v2i_offered": 100.0,
            "v2i_admitted": 50.0,
            "v2i_rejected_or_unavailable": 50.0,
            "veh_offered": 10.0,
            "veh_admitted": 10.0,
            "veh_rejected": 0.0,
        },
        "v2i_path_metrics": {
            "v2i_attempts": 2,
            "v2i_admitted_tasks": 1,
            "ingress_count_per_rsu": [2, 0],
            "selected_target_count_per_rsu": [1, 1],
            "actual_execution_count_per_rsu": [1, 0],
            "forwarded_admitted_task_count": 0,
            "forwarded_share_of_admitted_v2i": 0.0,
            "total_forwarding_latency_ms": 0.0,
            "mean_forwarding_latency_ms_per_admitted_v2i": 0.0,
            "mean_forwarding_latency_ms_per_forwarded_v2i": 0.0,
            "ingress_to_execution_pair_matrix": [[1, 0], [0, 0]],
            "execution_share_per_rsu": [1.0, 0.0],
            "maximum_execution_share": 1.0,
            "imbalance_diagnostic": {"value": 1.0},
        },
    }
    (root / "summary.json").write_text(json.dumps(summary))
    (root / "command.json").write_text(json.dumps({"argv": []}))
    (root / "checksums.sha256").write_text("placeholder\n")
    return root


def test_valid_run_passes_task_path_and_work_gates(tmp_path: Path) -> None:
    run = write_valid_run(tmp_path / "run")
    result = validate_run(
        run,
        arm={"id": "jsq", "rsu_lb": "jsq"},
        manifest=manifest(),
        expected_steps=1,
    )
    assert result["status"] == "passed", [
        check for check in result["checks"] if not check["pass"]
    ]


def test_rejected_execution_defect_fails(tmp_path: Path) -> None:
    run = write_valid_run(tmp_path / "run")
    with np.load(run / "per_task.npz") as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays["task_execution_rsu"][0, 1, 0] = 1
    np.savez_compressed(run / "per_task.npz", **arrays)
    result = validate_run(
        run,
        arm={"id": "jsq", "rsu_lb": "jsq"},
        manifest=manifest(),
        expected_steps=1,
    )
    assert result["status"] == "failed"
    assert not next(
        check["pass"] for check in result["checks"]
        if check["name"] == "rejected_v2i_has_no_execution"
    )


def test_v2i_admission_outcome_identity_defect_fails(tmp_path: Path) -> None:
    run = write_valid_run(tmp_path / "run")
    with np.load(run / "per_task.npz") as archive:
        arrays = {key: archive[key] for key in archive.files}
    arrays["task_v2i_admitted"][0, 1, 0] = True
    arrays["task_execution_rsu"][0, 1, 0] = 1
    arrays["task_forwarded"][0, 1, 0] = True
    np.savez_compressed(run / "per_task.npz", **arrays)
    result = validate_run(
        run, arm={"id": "jsq", "rsu_lb": "jsq"},
        manifest=manifest(), expected_steps=1,
    )
    assert result["status"] == "failed"
    assert not next(
        check["pass"] for check in result["checks"]
        if check["name"] == "v2i_admission_outcome_identity"
    )


def test_energy_denominator_defect_fails(tmp_path: Path) -> None:
    run = write_valid_run(tmp_path / "run")
    summary = json.loads((run / "summary.json").read_text())
    summary["total_energy_j"] = 3.0
    (run / "summary.json").write_text(json.dumps(summary))
    result = validate_run(
        run, arm={"id": "jsq", "rsu_lb": "jsq"},
        manifest=manifest(), expected_steps=1,
    )
    assert result["status"] == "failed"
    assert not next(
        check["pass"] for check in result["checks"]
        if check["name"] == "energy_per_offered_denominator"
    )


def test_missing_actor_logits_fails_without_exception(tmp_path: Path) -> None:
    run = write_valid_run(tmp_path / "run")
    with np.load(run / "per_step.npz") as archive:
        arrays = {key: archive[key] for key in archive.files if key != "veh_actor_logits"}
    np.savez_compressed(run / "per_step.npz", **arrays)
    result = validate_run(
        run, arm={"id": "jsq", "rsu_lb": "jsq"},
        manifest=manifest(), expected_steps=1,
    )
    assert result["status"] == "failed"
    assert not next(
        check["pass"] for check in result["checks"]
        if check["name"] == "actor_logits_schema"
    )


def test_phase_with_missing_runs_fails_closed_without_exception(tmp_path: Path) -> None:
    contract = manifest()
    contract.update({
        "outputs": {"raw_root": str(tmp_path)},
        "smoke_gate": {"steps": 10, "serial_repeats_per_arm": 2},
        "arms": [
            {"id": "off", "rsu_lb": "off"},
            {"id": "jsq", "rsu_lb": "jsq"},
            {"id": "dla", "rsu_lb": "dla"},
        ],
    })
    result = validate_phase(contract, "smoke")
    assert result["status"] == "failed"
    assert result["repeat_checks"] == []
    assert result["cross_arm_identity_checks"] == []


def test_contrast_is_raw_candidate_minus_reference() -> None:
    base = {
        "offered_task_deadline_attainment": 0.4,
        "admitted_task_deadline_attainment": 0.5,
        "admitted_tasks": 10,
        "latency_ms_per_offered_task": 100.0,
        "latency_ms_per_admitted_task": 80.0,
        "deadline_met_latency_mean_ms": 20.0,
        "energy_j_per_offered_task": 0.1,
        "rejection_and_unavailability": {"v2i_gate_rejected": 0, "v2i_cap_rejected": 2, "v2i_unavailable": 1},
        "task_class_completion": {"t1": 0.1, "t2": 0.2, "t3": 0.3},
        "v2i_path_metrics": {
            "v2i_admitted_tasks": 5,
            "forwarded_admitted_task_count": 0,
            "forwarded_share_of_admitted_v2i": 0.0,
            "maximum_execution_share": 0.8,
            "imbalance_diagnostic": {"value": 0.7},
            "actual_execution_count_per_rsu": [4, 1],
        },
    }
    candidate = json.loads(json.dumps(base))
    candidate["offered_task_deadline_attainment"] = 0.45
    candidate["v2i_path_metrics"]["actual_execution_count_per_rsu"] = [3, 2]
    result = contrast({"off": base, "jsq": candidate}, "jsq", "off", "placement")
    assert np.isclose(
        result["differences_candidate_minus_reference"]["offered_task_deadline_attainment"],
        0.05,
    )
    assert result["differences_candidate_minus_reference"]["actual_execution_count_per_rsu"] == [-1, 1]
    assert result["direct_primary_observation"] == "higher observed offered-task attainment"
