from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scripts.validate_e0_smoke import array_sha256, sha256_file
from scripts.validate_e1_semantics_pair import build_full_pair_report, build_smoke_report


def _write_legacy_run(path: Path, *, offered: float = 2.0, admitted: Any = None) -> None:  # noqa: ANN401
    path.mkdir(parents=True)
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
        "rsu_cap_mode": "clamp",
        "substep_queue": "snapshot",
        "veh_queue_mode": "legacy",
        "enter_reset": False,
        "total_tasks": offered,
        "n_offered": offered,
        "n_admitted": admitted,
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
    (path / "stdout_stderr.log").write_text("fixture\n", encoding="utf-8")
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


def _write_physical_evidence(
    root: Path,
    legacy_run: Path,
) -> tuple[Path, Path, dict[str, str]]:
    physical_run = root / "physical"
    physical_run.mkdir()
    physical_summary = {
        "n_offered": 2.0,
        "n_admitted": 2.0,
        "completion": 0.5,
        "completion_admitted": 0.5,
        "avg_latency_ms_per_task": 500.0,
    }
    (physical_run / "summary.json").write_text(json.dumps(physical_summary), encoding="utf-8")
    (physical_run / "per_step.npz").write_bytes(b"physical step")
    (physical_run / "per_task.npz").write_bytes(b"physical task")
    output_hashes = {
        name: sha256_file(physical_run / name)
        for name in ("summary.json", "per_step.npz", "per_task.npz")
    }
    with np.load(legacy_run / "per_task.npz", allow_pickle=False) as archive:
        per_task_hashes = {key: array_sha256(archive[key]) for key in archive.files}
    validation = {
        "passed": True,
        "decision": "full_corrected_reference_pass",
        "runs": [{"array_sha256": {"per_task": per_task_hashes}}],
    }
    validation_path = root / "physical_validation.json"
    validation_path.write_text(json.dumps(validation), encoding="utf-8")
    return physical_run, validation_path, output_hashes


def _write_manifest(
    path: Path,
    actor: Path,
    trace: Path,
    *,
    physical_validation: Path | None = None,
    physical_hashes: dict[str, str] | None = None,
) -> None:
    manifest: dict[str, Any] = {
        "manifest_id": "test-e1",
        "scope": {"legacy_smoke_steps": 1, "full_steps": 1},
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
            "cap": {"resolved_value": 5},
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
                "e0_validation_sha256": (
                    sha256_file(physical_validation) if physical_validation else "unused"
                )
            },
        },
        "execution": {"physical_reused_output_sha256": physical_hashes or {}},
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _smoke_fixture(
    tmp_path: Path, **legacy_overrides: float | None
) -> tuple[Path, Path, Path, Path, Path]:
    actor = tmp_path / "actor.npz"
    trace = tmp_path / "trace.npz"
    actor.write_bytes(b"actor")
    trace.write_bytes(b"trace")
    run_1 = tmp_path / "run_1"
    run_2 = tmp_path / "run_2"
    _write_legacy_run(run_1, **legacy_overrides)
    _write_legacy_run(run_2, **legacy_overrides)
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest, actor, trace)
    return manifest, run_1, run_2, actor, trace


def test_valid_legacy_smoke_repeat_passes(tmp_path: Path) -> None:
    manifest, run_1, run_2, actor, trace = _smoke_fixture(tmp_path)
    report = build_smoke_report(manifest, run_1, run_2, actor, trace)
    assert report["passed"] is True
    assert report["repeat"]["scientific_summary_identical"] is True
    assert report["repeat"]["instrumentation_arrays_identical"] is True


def test_legacy_silent_task_record_loss_fails(tmp_path: Path) -> None:
    manifest, run_1, run_2, actor, trace = _smoke_fixture(tmp_path, offered=3.0)
    report = build_smoke_report(manifest, run_1, run_2, actor, trace)
    assert report["passed"] is False
    failed = {check["name"] for check in report["runs"][0]["checks"] if not check["passed"]}
    assert "active_records_equal_offered" in failed


def test_legacy_admitted_value_is_rejected_as_unobservable(tmp_path: Path) -> None:
    manifest, run_1, run_2, actor, trace = _smoke_fixture(tmp_path, admitted=2.0)
    report = build_smoke_report(manifest, run_1, run_2, actor, trace)
    assert report["passed"] is False
    failed = {check["name"] for check in report["runs"][0]["checks"] if not check["passed"]}
    assert "legacy_unavailable_fields_remain_null" in failed


def test_valid_full_pair_passes_but_does_not_invent_legacy_metrics(tmp_path: Path) -> None:
    actor = tmp_path / "actor.npz"
    trace = tmp_path / "trace.npz"
    actor.write_bytes(b"actor")
    trace.write_bytes(b"trace")
    legacy_run = tmp_path / "legacy"
    _write_legacy_run(legacy_run)
    physical_run, validation_path, output_hashes = _write_physical_evidence(tmp_path, legacy_run)
    manifest = tmp_path / "manifest.json"
    _write_manifest(
        manifest,
        actor,
        trace,
        physical_validation=validation_path,
        physical_hashes=output_hashes,
    )

    report = build_full_pair_report(
        manifest,
        legacy_run,
        physical_run,
        validation_path,
        actor,
        trace,
    )
    assert report["passed"] is True
    assert report["paired_metrics_physical_minus_legacy"]["completion_admitted"] is None
    assert report["paired_metrics_physical_minus_legacy"]["rejection_fraction"] is None
    assert (
        report["interpretation_limits"]["legacy_conservation_verdict"]
        == "unavailable_and_nonconserving_by_source_contract"
    )
