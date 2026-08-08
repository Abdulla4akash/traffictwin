from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scripts.validate_e0_smoke import sha256_file
from scripts.validate_e1_new_cap_pair import (
    build_dual_smoke_report,
    build_new_full_pair_report,
)


def _write_legacy_run(path: Path) -> None:
    path.mkdir(parents=True)
    summary = {
        "trace": "trace.npz",
        "actor": "actor.npz",
        "model": "C",
        "T": 1,
        "maxN": 2,
        "rsu_max_concurrent": 2,
        "fleet": "uk2030",
        "fleet_seed": 0,
        "obs_variant": "onehot17",
        "lambda_arrival": 1.5,
        "rsu_service_mult": 1.0,
        "rsu_lb": "off",
        "rsu_backhaul_ms": 0.0,
        "k8s_scale": "off",
        "k8s_mean_mult": 1.0,
        "k8s_scale_events": 0,
        "rsu_cap_mode": "clamp",
        "substep_queue": "snapshot",
        "veh_queue_mode": "legacy",
        "enter_reset": False,
        "total_tasks": 2.0,
        "n_offered": 2.0,
        "n_admitted": None,
        "completion_admitted": None,
        "avg_latency_admitted_ms": None,
        "avg_latency_met_ms": None,
        "work_ms": None,
        "v2i_gate_rejected": 0.0,
        "v2i_cap_rejected": 0.0,
        "local_mqd_rejected": 0.0,
        "v2v_mqd_rejected": 0.0,
        "v2i_unavailable": 0.0,
        "v2v_unavailable": 0.0,
        "completion": 0.5,
        "avg_latency_ms_per_task": 525.0,
        "t1_completion": 1.0,
        "t2_completion": 0.0,
        "t3_completion": 0.0,
        "p_local": 1.0,
        "p_v2i": 0.0,
        "p_v2v": 0.0,
        "wall_s": 1.0,
    }
    (path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (path / "stdout_stderr.log").write_text("legacy fixture\n", encoding="utf-8")
    np.savez_compressed(
        path / "per_step.npz",
        arrivals=np.array([2], dtype=np.int32),
        done=np.array([1], dtype=np.int32),
        lat_sum=np.array([1050.0], dtype=np.float32),
        n_local=np.array([2], dtype=np.int32),
        n_v2i=np.array([0], dtype=np.int32),
        n_v2v=np.array([0], dtype=np.int32),
        rsu_busy_ms=np.array([[0.0]], dtype=np.float32),
        rsu_load=np.array([[0]], dtype=np.int32),
    )
    np.savez_compressed(
        path / "per_task.npz",
        task_type=np.array([[[0, 1]]], dtype=np.int8),
        task_lat_ms=np.array([[[50.0, 1000.0]]], dtype=np.float32),
        task_met=np.array([[[True, False]]]),
        task_active=np.array([[[True, True]]]),
    )


def _write_physical_run(
    path: Path,
    *,
    veh_offered: float = 10.0,
    task_types: tuple[int, int] = (0, 1),
) -> None:
    path.mkdir(parents=True)
    summary = {
        "trace": "trace.npz",
        "actor": "actor.npz",
        "model": "C",
        "T": 1,
        "maxN": 2,
        "rsu_max_concurrent": 2,
        "fleet": "uk2030",
        "fleet_seed": 0,
        "obs_variant": "onehot17",
        "lambda_arrival": 1.5,
        "rsu_service_mult": 1.0,
        "rsu_lb": "off",
        "rsu_backhaul_ms": 0.0,
        "k8s_scale": "off",
        "k8s_mean_mult": 1.0,
        "k8s_scale_events": 0,
        "rsu_cap_mode": "reject",
        "substep_queue": "sequential",
        "veh_queue_mode": "conserved",
        "enter_reset": False,
        "total_tasks": 2.0,
        "n_offered": 2.0,
        "n_admitted": 1.0,
        "v2i_gate_rejected": 0.0,
        "v2i_cap_rejected": 0.0,
        "local_mqd_rejected": 1.0,
        "v2v_mqd_rejected": 0.0,
        "v2i_unavailable": 0.0,
        "v2v_unavailable": 0.0,
        "work_ms": {
            "v2i_offered": 0.0,
            "v2i_admitted": 0.0,
            "v2i_rejected_or_unavailable": 0.0,
            "veh_offered": veh_offered,
            "veh_admitted": 8.0,
            "veh_rejected": 2.0,
        },
        "completion": 0.5,
        "completion_admitted": 1.0,
        "avg_latency_ms_per_task": 525.0,
        "avg_latency_admitted_ms": 50.0,
        "avg_latency_met_ms": 50.0,
        "t1_completion": 1.0,
        "t2_completion": 0.0,
        "t3_completion": 0.0,
        "p_local": 1.0,
        "p_v2i": 0.0,
        "p_v2v": 0.0,
        "wall_s": 1.0,
    }
    (path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (path / "stdout_stderr.log").write_text("physical fixture\n", encoding="utf-8")
    np.savez_compressed(
        path / "per_step.npz",
        arrivals=np.array([2], dtype=np.int32),
        done=np.array([1], dtype=np.int32),
        n_local=np.array([2], dtype=np.int32),
        n_v2i=np.array([0], dtype=np.int32),
        n_v2v=np.array([0], dtype=np.int32),
        rsu_busy_ms=np.array([[0.0]], dtype=np.float32),
        rsu_load=np.array([[0]], dtype=np.int32),
    )
    np.savez_compressed(
        path / "per_task.npz",
        task_type=np.array([[task_types]], dtype=np.int8),
        task_lat_ms=np.array([[[50.0, 1000.0]]], dtype=np.float32),
        task_outcome=np.array([[[1, 5]]], dtype=np.int8),
        task_met=np.array([[[True, False]]]),
        task_active=np.array([[[True, True]]]),
    )


def _write_manifest(path: Path, actor: Path, trace: Path) -> None:
    manifest: dict[str, Any] = {
        "manifest_id": "test-e1-new-cap",
        "scope": {"smoke_steps": 1, "full_steps": 1},
        "inputs": {
            "actor": {"path": "actor.npz", "sha256": sha256_file(actor)},
            "trace": {
                "path": "trace.npz",
                "sha256": sha256_file(trace),
                "padded_fleet_width": 2,
                "has_enter_channel": False,
            },
        },
        "controlled_configuration": {
            "fleet_seed": 0,
            "fleet": {"preset": "uk2030"},
            "arrival_lambda": 1.5,
            "cap": {"resolved_value": 2},
            "compute": {
                "rsu_service_multiplier": 1.0,
                "scaling": "off",
                "mean_multiplier_expected": 1.0,
            },
            "placement": {"mode": "off", "backhaul_ms": 0.0},
        },
        "arms": {
            "legacy": {
                "rsu_cap_mode": "clamp",
                "substep_queue": "snapshot",
                "vehicle_queue_effective": "legacy",
            },
            "physical": {
                "rsu_cap_mode": "reject",
                "substep_queue": "sequential",
                "vehicle_queue_effective": "conserved",
            },
        },
        "validation_decisions": {
            "smoke_pass": "test_smoke_pass",
            "full_pass": "test_full_pass",
            "stop": "test_stop",
        },
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _fixture(
    tmp_path: Path,
    *,
    physical_veh_offered: float = 10.0,
    physical_task_types: tuple[int, int] = (0, 1),
) -> tuple[Path, list[Path], list[Path], Path, Path]:
    actor = tmp_path / "actor.npz"
    trace = tmp_path / "trace.npz"
    actor.write_bytes(b"actor")
    trace.write_bytes(b"trace")
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, actor, trace)
    legacy_runs = [tmp_path / "legacy_1", tmp_path / "legacy_2"]
    physical_runs = [tmp_path / "physical_1", tmp_path / "physical_2"]
    for run in legacy_runs:
        _write_legacy_run(run)
    for run in physical_runs:
        _write_physical_run(
            run,
            veh_offered=physical_veh_offered,
            task_types=physical_task_types,
        )
    return manifest, legacy_runs, physical_runs, actor, trace


def test_valid_dual_smoke_repeat_passes(tmp_path: Path) -> None:
    manifest, legacy, physical, actor, trace = _fixture(tmp_path)
    report = build_dual_smoke_report(
        manifest,
        legacy[0],
        legacy[1],
        physical[0],
        physical[1],
        actor,
        trace,
    )
    assert report["passed"] is True
    assert all(report["legacy_repeat"].values())
    assert all(report["physical_repeat"].values())
    assert all(report["paired_input_equality"].values())


def test_physical_work_nonconservation_stops_smoke(tmp_path: Path) -> None:
    manifest, legacy, physical, actor, trace = _fixture(
        tmp_path,
        physical_veh_offered=11.0,
    )
    report = build_dual_smoke_report(
        manifest,
        legacy[0],
        legacy[1],
        physical[0],
        physical[1],
        actor,
        trace,
    )
    assert report["passed"] is False
    failed = {
        check["name"] for check in report["physical_runs"][0]["checks"] if not check["passed"]
    }
    assert "vehicle_work_ms_conserved" in failed


def test_valid_new_full_pair_preserves_null_legacy_metrics(tmp_path: Path) -> None:
    manifest, legacy, physical, actor, trace = _fixture(tmp_path)
    report = build_new_full_pair_report(
        manifest,
        legacy[0],
        physical[0],
        actor,
        trace,
    )
    assert report["passed"] is True
    assert report["paired_metrics_physical_minus_legacy"]["completion_admitted"] is None
    assert report["paired_metrics_physical_minus_legacy"]["rejection_fraction"] is None
    assert report["physical_run"]["observed"]["work_unit"] == "milliseconds of service work"


def test_cross_arm_task_type_mismatch_stops_pair(tmp_path: Path) -> None:
    manifest, legacy, physical, actor, trace = _fixture(
        tmp_path,
        physical_task_types=(0, 2),
    )
    report = build_new_full_pair_report(
        manifest,
        legacy[0],
        physical[0],
        actor,
        trace,
    )
    assert report["physical_run"]["passed"] is True
    assert report["paired_input_equality"]["task_type"] is False
    assert report["passed"] is False
