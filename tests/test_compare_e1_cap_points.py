from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.compare_e1_cap_points import build_comparison


def _run(cap: int, active_hash: str = "active") -> dict[str, Any]:
    return {
        "passed": True,
        "output_sha256": {
            "summary.json": "summary",
            "stdout_stderr.log": "log",
        },
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
            "n_admitted": 90.0 + cap,
            "completion": 0.6 + cap / 100.0,
            "completion_admitted": 0.7 + cap / 100.0,
            "avg_latency_ms_per_task": 1000.0 - cap,
            "avg_latency_admitted_ms": 100.0 - cap,
            "local_mqd_rejected": 1.0,
            "v2v_mqd_rejected": 2.0,
            "v2i_cap_rejected": 7.0 - cap,
            "v2i_unavailable": 0.0,
            "v2v_unavailable": 0.0,
        },
    }


def _legacy(active_hash: str = "active") -> dict[str, Any]:
    return {
        "passed": True,
        "array_sha256": {"per_task": {"task_active": active_hash, "task_type": "type"}},
        "scientific_summary": {
            "completion": 0.5,
            "avg_latency_ms_per_task": 500.0,
        },
    }


def _write_fixture(tmp_path: Path, *, low_active: str = "active") -> tuple[Path, Path, Path]:
    reuse_run = _run(5)
    reuse = {"passed": True, "runs": [reuse_run]}
    reuse_path = tmp_path / "reuse.json"
    reuse_path.write_text(json.dumps(reuse), encoding="utf-8")
    reuse_sha = hashlib.sha256(reuse_path.read_bytes()).hexdigest()
    identity = {
        "passed": True,
        "sha256": {"actor": "actor-hash", "trace": "trace-hash"},
    }
    high = {
        "passed": True,
        "input_identity": identity,
        "legacy_run": _legacy(),
        "physical_e0_reuse": {
            "validation_sha256": reuse_sha,
            "output_sha256": {"summary.json": "summary"},
        },
    }
    low = {
        "passed": True,
        "input_identity": identity,
        "legacy_run": _legacy(active_hash=low_active),
        "physical_run": _run(2, active_hash=low_active),
    }
    low_path = tmp_path / "low.json"
    high_path = tmp_path / "high.json"
    low_path.write_text(json.dumps(low), encoding="utf-8")
    high_path.write_text(json.dumps(high), encoding="utf-8")
    return low_path, high_path, reuse_path


def test_valid_comparison_computes_low_minus_high(tmp_path: Path) -> None:
    low, high, reuse = _write_fixture(tmp_path)
    report = build_comparison(low, high, reuse)
    assert report["passed"] is True
    assert report["physical_points"]["low_cap"]["rsu_max_concurrent"] == 2
    assert report["physical_points"]["high_cap"]["rsu_max_concurrent"] == 5
    assert report["physical_low_minus_high"]["n_admitted"] == -3.0
    assert report["interpretation_limits"]["multi_seed_inference_supported"] is False


def test_task_stream_mismatch_stops_comparison(tmp_path: Path) -> None:
    low, high, reuse = _write_fixture(tmp_path, low_active="different")
    report = build_comparison(low, high, reuse)
    assert report["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "physical_task_active_equal" in failed
    assert "legacy_task_active_equal" in failed


def test_reuse_validation_hash_mismatch_stops_comparison(tmp_path: Path) -> None:
    low, high, reuse = _write_fixture(tmp_path)
    reuse.write_text(json.dumps({"passed": False, "runs": []}), encoding="utf-8")
    report = build_comparison(low, high, reuse)
    assert report["passed"] is False
    failed = {check["name"] for check in report["checks"] if not check["passed"]}
    assert "reuse_validation_hash_matches" in failed
