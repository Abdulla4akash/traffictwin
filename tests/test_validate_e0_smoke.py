from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scripts.validate_e0_smoke import build_report


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_run(path: Path, *, offered: float = 2.0, veh_offered: float = 10.0) -> None:
    path.mkdir()
    summary = {
        "trace": "trace.npz",
        "actor": "actor.npz",
        "model": "C",
        "T": 1,
        "maxN": 2,
        "rsu_max_concurrent": 5,
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
        "n_offered": offered,
        "n_admitted": 1.0,
        "total_tasks": offered,
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
        "wall_s": 1.0,
    }
    (path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
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
        task_type=np.array([[[1, 2]]], dtype=np.int8),
        task_lat_ms=np.array([[[50.0, 1000.0]]], dtype=np.float32),
        task_outcome=np.array([[[1, 5]]], dtype=np.int8),
        task_met=np.array([[[True, False]]]),
        task_active=np.array([[[True, True]]]),
    )


def _write_manifest(path: Path, actor: Path, trace: Path) -> None:
    manifest: dict[str, Any] = {
        "manifest_id": "test",
        "scope": {"max_steps": 1},
        "inputs": {
            "actor": {"path": "actor.npz", "sha256": _sha256(actor)},
            "trace": {
                "path": "trace.npz",
                "sha256": _sha256(trace),
                "padded_fleet_width": 2,
                "has_enter_channel": False,
            },
        },
        "configuration": {
            "fleet_seed": 0,
            "fleet": {"preset": "uk2030"},
            "arrival_lambda": 1.5,
            "cap": {"resolved_value": 5},
            "compute": {
                "rsu_service_multiplier": 1.0,
                "scaling": "off",
                "mean_multiplier_expected": 1.0,
            },
            "placement": {"mode": "off", "backhaul_ms": 0.0},
            "rsu_admission": "reject",
            "substep_queue": "sequential",
            "vehicle_queue": "conserved",
        },
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _fixture(tmp_path: Path, **run_overrides: float) -> tuple[Path, Path, Path, Path, Path]:
    actor = tmp_path / "actor.npz"
    trace = tmp_path / "trace.npz"
    actor.write_bytes(b"actor")
    trace.write_bytes(b"trace")
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, actor, trace)
    run_1 = tmp_path / "run_1"
    run_2 = tmp_path / "run_2"
    _write_run(run_1, **run_overrides)
    _write_run(run_2, **run_overrides)
    return manifest, run_1, run_2, actor, trace


def test_valid_outputs_pass_and_repeat_is_identical(tmp_path: Path) -> None:
    manifest, run_1, run_2, actor, trace = _fixture(tmp_path)
    report = build_report(manifest, run_1, run_2, actor, trace)
    assert report["passed"] is True
    assert report["repeat"]["scientific_summary_identical"] is True
    assert report["repeat"]["instrumentation_arrays_identical"] is True


def test_silent_task_loss_fails(tmp_path: Path) -> None:
    manifest, run_1, run_2, actor, trace = _fixture(tmp_path, offered=3.0)
    report = build_report(manifest, run_1, run_2, actor, trace)
    assert report["passed"] is False
    failed = {check["name"] for check in report["runs"][0]["checks"] if not check["passed"]}
    assert "active_records_equal_offered" in failed
    assert "offered_equals_admitted_plus_terminal_rejections" in failed


def test_vehicle_work_nonconservation_fails(tmp_path: Path) -> None:
    manifest, run_1, run_2, actor, trace = _fixture(tmp_path, veh_offered=11.0)
    report = build_report(manifest, run_1, run_2, actor, trace)
    assert report["passed"] is False
    failed = {check["name"] for check in report["runs"][0]["checks"] if not check["passed"]}
    assert "vehicle_work_ms_conserved" in failed
