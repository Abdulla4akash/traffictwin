from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_e1_seed_three_cap import build_seed_comparison

CAPS = {"0p75": 1866, "2p5": 6220, "40x": 99520}


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _metrics(cap: int, admitted: int, offered_deadline: float, latency: float) -> dict[str, object]:
    offered = 1000
    rejected = offered - admitted
    return {
        "rsu_max_concurrent": cap,
        "offered_tasks": offered,
        "admitted_tasks": admitted,
        "rejected_or_unavailable_tasks": rejected,
        "rejection_fraction_offered": rejected / offered,
        "rejection_counts": {
            "v2i_gate_rejected": 0,
            "v2i_cap_rejected": rejected,
            "local_mqd_rejected": 0,
            "v2v_mqd_rejected": 0,
            "v2i_unavailable": 0,
            "v2v_unavailable": 0,
        },
        "deadline_met_tasks": 600,
        "deadline_attainment_offered": offered_deadline,
        "deadline_attainment_admitted": 600 / admitted,
        "penalty_inclusive_latency_ms_per_offered_task": latency,
        "latency_ms_per_admitted_task": latency * 0.75,
        "latency_ms_per_deadline_met_task": 40.0,
        "admitted_latency_tail_ms": {"p50": 50.0, "p95": latency, "p99": latency * 2},
        "deadline_met_latency_tail_ms": {"p50": 30.0, "p95": 100.0, "p99": 200.0},
        "work_ms": {
            "v2i_offered": 1000.0,
            "v2i_admitted": float(admitted),
            "v2i_rejected_or_unavailable": float(rejected),
            "veh_offered": 500.0,
            "veh_admitted": 400.0,
            "veh_rejected": 100.0,
        },
        "wall_s": 10.0,
    }


def _validation() -> dict[str, object]:
    return {
        "passed": True,
        "run": {
            "checks": [{"name": "accounting", "passed": True}],
            "array_sha256": {"per_task": {"task_active": "active", "task_type": "type"}},
        },
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    manifest = tmp_path / "manifest.json"
    seed_root = tmp_path / "fleet_seed_1"
    seed0 = tmp_path / "seed0.json"
    _write(
        manifest,
        {
            "backend_decision": {
                "selected_backend": "macos_arm64_cpu_jax_0_4_30",
                "campaign_execution_allowed": True,
            },
            "cap_grid": [
                {"label": label, "resolved_tasks_per_rsu": cap} for label, cap in CAPS.items()
            ],
            "output": {"logical_locator": "local-output:test-campaign"},
        },
    )
    inputs = {
        "0p75": _metrics(1866, 800, 0.61, 100.0),
        "2p5": _metrics(6220, 850, 0.60, 200.0),
        "40x": _metrics(99520, 900, 0.60, 400.0),
    }
    for label, metrics in inputs.items():
        _write(seed_root / f"cap_{label}" / "cell_metrics.json", metrics)
        _write(seed_root / f"cap_{label}" / "full_validation.json", _validation())
    _write(
        seed0,
        {
            "passed": True,
            "physical_points": {
                label: {
                    "n_admitted": point["admitted_tasks"],
                    "n_rejected": point["rejected_or_unavailable_tasks"],
                    "v2i_cap_rejected": point["rejection_counts"]["v2i_cap_rejected"],
                    "completion_offered": point["deadline_attainment_offered"],
                    "completion_admitted": point["deadline_attainment_admitted"],
                    "penalty_inclusive_latency_ms_per_offered_task": point[
                        "penalty_inclusive_latency_ms_per_offered_task"
                    ],
                    "latency_ms_per_admitted_task": point["latency_ms_per_admitted_task"],
                }
                for label, point in inputs.items()
            },
        },
    )
    return manifest, seed_root, seed0


def test_valid_seed_comparison_computes_deltas_and_pattern(tmp_path: Path) -> None:
    manifest, seed_root, seed0 = _fixture(tmp_path)
    validation, comparison = build_seed_comparison(manifest, seed_root, seed0)

    assert validation["passed"] is True
    assert comparison["higher_cap_minus_lower_cap"]["40x_minus_0p75"]["admitted_tasks"] == 100.0
    assert (
        comparison["seed1_descriptive_trends"]["offered_deadline_attainment_profile"]
        == "decrease_then_plateau"
    )
    assert (
        comparison["qualitative_pattern_comparison"]["all_predeclared_qualitative_fields_match"]
        is True
    )
    assert comparison["interpretation_limits"]["five_draw_inference_calculated"] is False


def test_task_stream_mismatch_fails_validation(tmp_path: Path) -> None:
    manifest, seed_root, seed0 = _fixture(tmp_path)
    path = seed_root / "cap_40x" / "full_validation.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["run"]["array_sha256"]["per_task"]["task_active"] = "different"
    _write(path, record)

    validation, comparison = build_seed_comparison(manifest, seed_root, seed0)

    assert validation["passed"] is False
    assert comparison["validation_passed"] is False
    failed = {item["name"] for item in validation["checks"] if not item["passed"]}
    assert "task_active_identical_across_caps" in failed
