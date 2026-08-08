from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.compare_e1_cap_sweep import build_sweep_comparison


def _run(cap: int, *, active_hash: str = "active") -> dict[str, Any]:
    return {
        "passed": True,
        "output_sha256": {"summary.json": f"summary-{cap}", "stdout_stderr.log": "log"},
        "array_sha256": {"per_task": {"task_active": active_hash, "task_type": "type"}},
        "scientific_summary": {
            "T": 1,
            "maxN": 2,
            "actor": "actor.npz",
            "trace": "trace.npz",
            "fleet": "uk2030",
            "fleet_seed": 0,
            "lambda_arrival": 1.5,
            "rsu_service_mult": 1.0,
            "rsu_lb": "off",
            "rsu_backhaul_ms": 0.0,
            "k8s_scale": "off",
            "substep_queue": "sequential",
            "veh_queue_mode": "conserved",
            "rsu_cap_mode": "reject",
            "rsu_max_concurrent": cap,
            "n_offered": 100.0,
            "n_admitted": 80.0 + cap,
            "completion": 0.6,
            "completion_admitted": 0.7 - cap / 100.0,
            "avg_latency_ms_per_task": 1000.0 * cap,
            "avg_latency_admitted_ms": 100.0 * cap,
            "local_mqd_rejected": 1.0,
            "v2v_mqd_rejected": 2.0,
            "v2i_cap_rejected": 10.0 - cap,
            "v2i_unavailable": 0.0,
            "v2v_unavailable": 0.0,
        },
    }


def _legacy(cap: int, *, active_hash: str = "active") -> dict[str, Any]:
    return {
        "passed": True,
        "array_sha256": {"per_task": {"task_active": active_hash, "task_type": "type"}},
        "scientific_summary": {
            "rsu_max_concurrent": cap,
            "n_offered": 100.0,
            "completion": 0.65,
            "avg_latency_ms_per_task": 500.0 * cap,
        },
    }


def _identity() -> dict[str, Any]:
    return {
        "passed": True,
        "sha256": {"actor": "actor-hash", "trace": "trace-hash"},
    }


def _direct(cap: int, *, active_hash: str = "active") -> dict[str, Any]:
    return {
        "passed": True,
        "input_identity": _identity(),
        "paired_input_equality": {
            "offered_count": True,
            "task_active": True,
            "task_type": True,
        },
        "legacy_run": _legacy(cap, active_hash=active_hash),
        "physical_run": _run(cap, active_hash=active_hash),
    }


def _write_fixture(
    tmp_path: Path,
    *,
    high_active: str = "active",
    caps: tuple[int, int, int] = (1, 2, 3),
) -> tuple[Path, Path, Path, Path]:
    low_cap, middle_cap, high_cap = caps
    reuse_run = _run(middle_cap)
    reuse_report = {"passed": True, "runs": [reuse_run]}
    reuse_path = tmp_path / "reuse.json"
    reuse_path.write_text(json.dumps(reuse_report), encoding="utf-8")
    reuse_sha = hashlib.sha256(reuse_path.read_bytes()).hexdigest()
    middle = {
        "passed": True,
        "input_identity": _identity(),
        "paired_input_equality": {
            "offered_count": True,
            "task_active": True,
            "task_type": True,
        },
        "legacy_run": _legacy(middle_cap),
        "physical_e0_reuse": {
            "validation_sha256": reuse_sha,
            "output_sha256": {"summary.json": f"summary-{middle_cap}"},
        },
    }
    low_path = tmp_path / "low.json"
    middle_path = tmp_path / "middle.json"
    high_path = tmp_path / "high.json"
    low_path.write_text(json.dumps(_direct(low_cap)), encoding="utf-8")
    middle_path.write_text(json.dumps(middle), encoding="utf-8")
    high_path.write_text(json.dumps(_direct(high_cap, active_hash=high_active)), encoding="utf-8")
    return low_path, middle_path, reuse_path, high_path


def test_valid_three_cap_sweep_computes_deltas(tmp_path: Path) -> None:
    low, middle, reuse, high = _write_fixture(tmp_path)
    report = build_sweep_comparison(low, middle, reuse, high)
    assert report["passed"] is True
    assert list(report["physical_points"]) == ["0p75", "2p5", "40x"]
    assert report["physical_higher_cap_minus_lower_cap"]["2p5_to_40x"]["n_admitted"] == 1.0
    assert (
        report["descriptive_trend_checks"]["physical_cap_rejections_nonincreasing_with_cap"] is True
    )


def test_task_stream_mismatch_stops_sweep(tmp_path: Path) -> None:
    low, middle, reuse, high = _write_fixture(tmp_path, high_active="different")
    report = build_sweep_comparison(low, middle, reuse, high)
    assert report["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "physical_task_active_equal" in failed
    assert "legacy_task_active_equal" in failed


def test_nonincreasing_caps_stop_sweep(tmp_path: Path) -> None:
    low, middle, reuse, high = _write_fixture(tmp_path, caps=(1, 3, 2))
    report = build_sweep_comparison(low, middle, reuse, high)
    assert report["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "caps_strictly_increasing" in failed


def test_reuse_hash_mismatch_stops_sweep(tmp_path: Path) -> None:
    low, middle, reuse, high = _write_fixture(tmp_path)
    reuse.write_text(json.dumps({"passed": False, "runs": []}), encoding="utf-8")
    report = build_sweep_comparison(low, middle, reuse, high)
    assert report["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "2p5_reuse_validation_hash_matches" in failed
