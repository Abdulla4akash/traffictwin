"""Hostile checks for immutable execution, independent accounting and reduction."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import numpy as np
import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "docs/evaluation/e3a_csf3_2026-09-11"
Json = dict[str, Any]


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validation = load_module("e3a_validation_test", PACKAGE / "validation.py")
with mock.patch.dict(sys.modules, {"validation": validation}):
    campaign = load_module("e3a_campaign_test", PACKAGE / "campaign.py")


def records() -> list[Json]:
    result = []
    for seed, difference in enumerate((1, 2, -1, 4), 1):
        for arm, fraction in zip(campaign.ARMS, (0.80, 0.85, 0.85 + difference / 100), strict=True):
            offered = 10000 * seed
            config = campaign.cell_config((seed - 1) * 3 + campaign.ARMS.index(arm), "a" * 64)
            result.append(
                {
                    "configuration": config,
                    "status": "passed",
                    "offered": offered,
                    "admitted": offered,
                    "successes": round(offered * fraction),
                    "terminal_failures": 0,
                    "forwarded": 0,
                    "cpu_model": "test CPU",
                    "shared_input_hashes": {"task/task_active": f"seed-{seed}"},
                }
            )
    return result


def test_reduce_uses_four_paired_draw_differences_and_own_denominators() -> None:
    result = campaign.reduce_records(records())
    primary = result["primary"]
    assert primary["mean_difference_pp"] == pytest.approx(1.5)
    assert primary["per_fleet_difference_pp"] == pytest.approx([1, 2, -1, 4])
    assert primary["sample_sd_pp"] == pytest.approx(np.std([1, 2, -1, 4], ddof=1))
    assert primary["standard_error_pp"] == pytest.approx(primary["sample_sd_pp"] / 2)
    margin = primary["standard_error_pp"] * 3.182446305
    assert primary["descriptive_t_interval_95_pp"] == pytest.approx([1.5 - margin, 1.5 + margin])
    assert result["secondary"]["mean_difference_pp"] == pytest.approx(6.5)
    assert result["qualification_records_included"] == 0


@pytest.mark.parametrize(
    "attack", ["missing", "duplicate", "qualification", "exogenous", "denominator", "cpu"]
)
def test_reduction_refuses_missing_or_incompatible_cells(attack: str) -> None:
    inputs = records()
    if attack == "missing":
        inputs.pop()
    elif attack == "duplicate":
        inputs[-1] = copy.deepcopy(inputs[0])
    elif attack == "qualification":
        inputs[0]["configuration"]["phase"] = "benchmark"
    elif attack == "exogenous":
        inputs[1]["shared_input_hashes"]["task/task_active"] = "changed"
    elif attack == "cpu":
        inputs[1]["cpu_model"] = "other CPU"
    else:
        inputs[0]["offered"] = 0
    with pytest.raises(ValueError):
        campaign.reduce_records(inputs)


def test_command_preserves_explicit_zero_delay_only_for_archived_per_task(tmp_path: Path) -> None:
    for index, arm in enumerate(campaign.ARMS):
        config = campaign.cell_config(index, "a" * 64)
        command = campaign.command_for(tmp_path, tmp_path / "out", config)
        assert command[command.index("--rsu-lb") + 1] == arm
        assert command[command.index("--max-steps") + 1] == "3600"
        assert command[command.index("--rsu-cap-abs") + 1] == "6220"
        if arm == "per_task_dla":
            assert command[command.index("--rsu-state-delay-ms") + 1] == "0"
        else:
            assert "--rsu-state-delay-ms" not in command


def test_first_smoke_failure_prevents_benchmarks_and_full_qualification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = []
    monkeypatch.setattr(campaign, "external_gates", lambda *_: "approved")

    def fail(*args: object) -> None:
        config = args[2]
        seen.append((config["phase"], config["steps"], config["arm"]))
        raise ValueError("deliberate accounting failure")

    monkeypatch.setattr(campaign, "attempt", fail)
    with pytest.raises(ValueError, match="deliberate"):
        campaign.qualify(tmp_path, {}, "a" * 64, {})
    assert seen == [("smoke", 10, "ingress_dla")]
    assert (tmp_path / "STOPPED.json").exists()
    assert (tmp_path / "qualification/FAILED.json").exists()
    assert not (tmp_path / "QUALIFIED.json").exists()
    with pytest.raises(ValueError, match="prior failure"):
        campaign.qualify(tmp_path, {}, "a" * 64, {})


def test_attempt_never_overwrites_an_existing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = campaign.cell_config(0, "a" * 64)
    destination = campaign.cell_directory(tmp_path, config)
    destination.mkdir(parents=True)
    (destination / "stdout.log").write_text("preserved original\n")
    monkeypatch.setattr(campaign, "verify_bundle", lambda *_: {})
    with pytest.raises(FileExistsError):
        campaign.attempt(tmp_path, {}, config, {}, 10)
    assert (destination / "stdout.log").read_text() == "preserved original\n"


def test_qualification_storage_and_memory_budget_are_fail_closed() -> None:
    benchmark = {
        "elapsed_seconds": 10,
        "raw_bytes": 100,
        "peak_child_rss_kib": 1024,
        "peak_validator_rss_kib": 1024,
    }
    benchmarks = [copy.deepcopy(benchmark) for _ in range(3)]
    required = 20 * campaign.GIB + 2 * 3 * 100 * 4
    with pytest.raises(ValueError, match="space"):
        campaign.qualification_budget(benchmarks, required - 1)
    assert campaign.qualification_budget(benchmarks, required)["memory_gib_per_cell"] == 32
    benchmarks[0]["peak_child_rss_kib"] = 28 * campaign.GIB // 1024
    with pytest.raises(ValueError, match="RSS"):
        campaign.qualification_budget(benchmarks, required)


def test_external_source_review_is_bound_to_the_exact_manifest_and_commit(tmp_path: Path) -> None:
    commit, seal = "b" * 40, "a" * 64
    gates = {
        "status": "passed",
        "manifest_sha256": seal,
        "source_commit": commit,
        "gates": {"unit_construct": "passed", "independent_review": "passed"},
        "review_verdict": f"VERDICT: APPROVE exact SHA {commit}",
    }
    (tmp_path / "EXTERNAL_GATES.json").write_text(json.dumps(gates))
    assert campaign.external_gates(tmp_path, {"source_commit": commit}, seal)
    with pytest.raises(ValueError, match="another bundle"):
        campaign.external_gates(tmp_path, {"source_commit": commit}, "c" * 64)
    gates["review_verdict"] = "process exit code 0"
    (tmp_path / "EXTERNAL_GATES.json").write_text(json.dumps(gates))
    with pytest.raises(ValueError, match="approval missing"):
        campaign.external_gates(tmp_path, {"source_commit": commit}, seal)


def scalar_pair(seed: int, fleet: int, tick: int, slot: int, ordinal: int, count: int) -> list[int]:
    """Pure Python reference, independent of both NumPy and the JAX limb kernel."""
    mask = (1 << 64) - 1

    def mix(value: int) -> int:
        value = (value + 0x9E3779B97F4A7C15) & mask
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
        return value ^ (value >> 31)

    value = 0x6A09E667F3BCC909
    for field in (seed, fleet, tick, slot, ordinal):
        value = mix(value ^ field)
    first, second = value % count, mix(value) % (count - 1)
    return sorted([first, second + (second >= first)])


def p2c_case() -> tuple[Json, Json, Json]:
    pair = scalar_pair(0, 1, 0, 0, 0, 4)
    selected = min(pair)
    step = {
        "rsu_start_busy_ms": np.zeros((1, 4), np.float32),
        "rsu_start_load": np.zeros((1, 4), np.int32),
        "veh_action": np.ones((1, 1), np.int8),
        "veh_v2i_quality": np.ones((1, 1), np.float32),
        "rsu_pre_drain_busy_ms": np.zeros((1, 4), np.float32),
        "rsu_pre_drain_load": np.zeros((1, 4), np.int32),
    }
    step["rsu_pre_drain_busy_ms"][0, selected] = 60
    step["rsu_pre_drain_load"][0, selected] = 1
    task = {
        "task_active": np.ones((1, 1, 1), bool),
        "task_type": np.zeros((1, 1, 1), np.int8),
        "task_outcome": np.ones((1, 1, 1), np.int8),
        "task_selected_execution_rsu": np.full((1, 1, 1), selected, np.int16),
        "task_v2i_admitted": np.ones((1, 1, 1), bool),
        "task_rsu_service_ms": np.full((1, 1, 1), 60, np.float32),
        "task_p2c_feasible_count": np.full((1, 1, 1), 4, np.int16),
        "task_p2c_sampled_pair": np.array([[[pair]]], np.int16),
        "task_p2c_feasibility_workload_checks": np.full((1, 1, 1), 4, np.int16),
        "task_p2c_ranking_workload_inspections": np.full((1, 1, 1), 2, np.int8),
        "task_p2c_unique_workload_values_observed": np.full((1, 1, 1), 4, np.int16),
        "task_p2c_sequential_ordinal": np.zeros((1, 1, 1), np.int32),
        "task_p2c_placement_busy_ms": np.zeros((1, 1, 1), np.float32),
    }
    return step, task, {"evaluator_seed": 0, "fleet_seed": 1}


def test_independent_p2c_counter_and_causal_work_validation() -> None:
    step, task, config = p2c_case()
    assert validation.validate_p2c(step, task, config)["status"] == "passed"
    task["task_p2c_feasible_count"][0, 0, 0] = 3
    with pytest.raises(ValueError, match="feasible count"):
        validation.validate_p2c(step, task, config)


def test_another_feasible_pair_with_valid_ranking_still_fails_exact_key_binding() -> None:
    step, task, config = p2c_case()
    original = task["task_p2c_sampled_pair"][0, 0, 0].tolist()
    alternative = next(pair for pair in ([0, 1], [0, 2], [0, 3], [1, 2]) if pair != original)
    task["task_p2c_sampled_pair"][0, 0, 0] = alternative
    task["task_selected_execution_rsu"][0, 0, 0] = min(alternative)
    step["rsu_pre_drain_busy_ms"][:] = 0
    step["rsu_pre_drain_load"][:] = 0
    step["rsu_pre_drain_busy_ms"][0, min(alternative)] = 60
    step["rsu_pre_drain_load"][0, min(alternative)] = 1
    with pytest.raises(ValueError, match="exact counter key"):
        validation.validate_p2c(step, task, config)


def empty_cell(tmp_path: Path) -> tuple[Json, Json, Json, Json]:
    t, n, r = 2, 3, 2
    step = {
        key: np.zeros((t,), np.float32)
        for key in ("arrivals", "done", "active", "n_local", "n_v2i", "n_v2v", "lat_sum")
    }
    step.update(
        {
            key: np.zeros((t, n), np.float32)
            for key in (
                "veh_queue_ms",
                "veh_start_busy_ms",
                "veh_pre_drain_busy_ms",
                "veh_v2i_quality",
                "veh_v2i_capacity_mbps",
                "veh_soc_before",
                "veh_soc_after",
                "veh_energy_j",
                "observation_task_size",
            )
        }
    )
    step.update(
        {
            key: np.zeros((t, n), np.int32)
            for key in (
                "veh_action",
                "veh_k",
                "veh_done",
                "veh_start_load",
                "veh_pre_drain_load",
                "veh_load",
                "veh_v2v_target",
                "observation_task_type",
                "veh_best_rsu",
                "veh_best_v2v",
            )
        }
    )
    step.update(
        {
            key: np.zeros((t, r), np.float32)
            for key in ("rsu_start_busy_ms", "rsu_pre_drain_busy_ms", "rsu_busy_ms")
        }
    )
    step.update(
        {
            key: np.zeros((t, r), np.int32)
            for key in ("rsu_start_load", "rsu_pre_drain_load", "rsu_load")
        }
    )
    step.update(
        {
            "veh_v2v_radio_viable": np.zeros((t, n), bool),
            "veh_actor_logits": np.zeros((t, n, 3), np.float32),
            "veh_observations": np.zeros((t, n, 17), np.float32),
            "exogenous_keys": np.zeros((t, 6, 2), np.uint32),
            "times": np.arange(t, dtype=np.float64),
            "slot_tier": np.zeros(n, np.int8),
            "slot_is_ev": np.zeros(n, bool),
            "slot_soc_initial": np.ones(n, np.float32),
            "slot_tx_power_w": np.ones(n, np.float32),
            "rr_pointer_before": np.full(t, -1, np.int32),
            "rr_pointer_after": np.full(t, -1, np.int32),
        }
    )
    step["veh_soc_before"][:] = step["veh_soc_after"][:] = 1
    step["active"][:] = n
    shape = (t, 5, n)
    task = {
        key: np.zeros(shape, bool)
        for key in (
            "task_active",
            "task_met",
            "task_v2i_admitted",
            "task_forwarded",
            "task_final_admitted",
        )
    }
    task.update(
        {
            key: np.zeros(shape, np.float32)
            for key in (
                "task_lat_ms",
                "task_sizes_mb",
                "task_rsu_service_ms",
                "task_local_service_ms",
                "task_v2v_service_ms",
                "task_forwarding_latency_ms",
            )
        }
    )
    task.update({key: np.zeros(shape, np.int8) for key in ("task_type", "task_outcome")})
    task.update(
        {
            key: np.full(shape, -1, np.int16)
            for key in ("task_ingress_rsu", "task_selected_execution_rsu", "task_execution_rsu")
        }
    )
    summary = {
        "T": t,
        "maxN": n,
        "n_rsus": r,
        "k_max": 5,
        "rsu_max_concurrent": 6220,
        "rsu_lb": "ingress_dla",
        "fleet_seed": 1,
        "evaluator_seed": 0,
        "enter_reset": False,
        "reset_soc_on_enter": False,
        "rsu_service_mult": 1.0,
        "rsu_backhaul_ms": 0.0,
        "k8s_scale": "off",
        "fleet": "uk2030",
        "lambda_arrival": 1.5,
        "rsu_cap_mode": "reject",
        "substep_queue": "sequential",
        "veh_queue_mode": "conserved",
        "substep_queue_iterations": 3,
        "obs_variant": "onehot17",
        "model": "C",
        "max_vehicle_queue_depth": 10,
        "n_offered": 0,
        "total_tasks": 0,
        "n_admitted": 0,
        "completion": 0,
        "completion_admitted": 0,
    }
    summary.update(
        dict.fromkeys(
            (
                "v2i_gate_rejected",
                "v2i_cap_rejected",
                "local_mqd_rejected",
                "v2v_mqd_rejected",
                "v2i_unavailable",
                "v2v_unavailable",
            ),
            0,
        )
    )
    for index in range(1, 4):
        summary[f"t{index}_share"] = summary[f"t{index}_completion"] = 0
    trace = tmp_path / "trace.npz"
    np.savez(trace, mask=np.ones((t, n), bool), times=step["times"])
    config = {
        "steps": t,
        "n_vehicles": n,
        "n_rsus": r,
        "arm": "ingress_dla",
        "fleet_seed": 1,
        "evaluator_seed": 0,
        "enter_reset": False,
        "seal_sha256": "a" * 64,
        "inputs": {"trace": str(trace)},
    }
    return step, task, summary, config


def store_cell(path: Path, step: Json, task: Json, summary: Json) -> None:
    np.savez(path / "per_step.npz", **step)
    np.savez(path / "per_task.npz", **task)
    (path / "summary.json").write_text(json.dumps(summary))


def test_generalized_validator_accepts_no_enter_trace_and_refuses_unbacked_summary(
    tmp_path: Path,
) -> None:
    step, task, summary, config = empty_cell(tmp_path)
    store_cell(tmp_path, step, task, summary)
    assert validation.validate_cell(tmp_path, config)["offered"] == 0
    summary["n_offered"] = 1
    store_cell(tmp_path, step, task, summary)
    with pytest.raises(ValueError, match="Integer count"):
        validation.validate_cell(tmp_path, config)


def test_no_enter_trace_uses_mask_only_queue_carry(tmp_path: Path) -> None:
    step, task, summary, config = empty_cell(tmp_path)
    # One admitted Local task carries 2 ms past the one-second drain; its slot
    # disappears next tick, so inherited mask-only semantics clear the queue.
    task["task_active"][0, 0, 0] = task["task_final_admitted"][0, 0, 0] = True
    task["task_outcome"][0, 0, 0] = 2
    task["task_lat_ms"][0, 0, 0] = task["task_local_service_ms"][0, 0, 0] = 1002
    step["veh_k"][0, 0] = 1
    step["arrivals"][0] = step["n_local"][0] = 1
    step["veh_pre_drain_busy_ms"][0, 0] = 1002
    step["veh_queue_ms"][0, 0] = 2
    step["veh_pre_drain_load"][0, 0] = step["veh_load"][0, 0] = 1
    mask = np.ones((2, 3), bool)
    mask[1, 0] = False
    step["active"][1] = 2
    np.savez(config["inputs"]["trace"], mask=mask, times=step["times"])
    summary.update(n_offered=1, total_tasks=1, n_admitted=1, t1_share=1)
    store_cell(tmp_path, step, task, summary)
    assert validation.validate_cell(tmp_path, config)["admitted"] == 1
    # Keep all local within-step conservation identities valid while falsely
    # retaining the departed vehicle's carry: only the trace-reset gate catches it.
    step["veh_start_busy_ms"][1, 0] = step["veh_pre_drain_busy_ms"][1, 0] = 2
    step["veh_start_load"][1, 0] = step["veh_pre_drain_load"][1, 0] = 1
    store_cell(tmp_path, step, task, summary)
    with pytest.raises(ValueError, match="queue reset/carry"):
        validation.validate_cell(tmp_path, config)


@pytest.mark.parametrize("arm", campaign.ARMS)
def test_real_evaluator_construct_records_pass_independent_validator(
    tmp_path: Path, arm: str
) -> None:
    evaluator = Path(
        os.environ.get("E3A_EVALUATOR_TEST_PATH", PACKAGE / "experimental/evaluator_v3.py")
    )
    if not evaluator.is_file():
        pytest.skip("Independent evaluator builder has not yet been composed into this worktree")
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    width, ticks, rsus = 8, 3, 4
    mask = np.ones((ticks, width), bool)
    mask[0, 0] = False
    np.savez(
        inputs / "trace_inc_fullrsu.npz",
        pos_x=np.zeros((ticks, width), np.float32),
        pos_y=np.zeros((ticks, width), np.float32),
        mask=mask,
        times=np.arange(ticks, dtype=np.float32),
        rsu_xy=np.array([[10, 10], [20, 20], [30, 30], [40, 40]], np.float32),
    )
    actor = {}
    for layer, (left, right) in enumerate(((17, 4), (4, 4), (4, 3))):
        actor[f"Dense_{layer}.kernel"] = np.zeros((left, right), np.float32)
        actor[f"Dense_{layer}.bias"] = np.zeros(right, np.float32)
    actor["Dense_2.bias"][1] = 10
    np.savez(inputs / "actor.npz", **actor)
    config = campaign.cell_config(campaign.ARMS.index(arm), "a" * 64, steps=ticks)
    config.update(
        n_vehicles=width, n_rsus=rsus, inputs={"trace": str(inputs / "trace_inc_fullrsu.npz")}
    )
    command = campaign.command_for(tmp_path, tmp_path, config)
    command[2] = str(evaluator)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("JAX_", "VEC_JAX_", "XLA_"))
    }
    environment.update(campaign.ENVIRONMENT)
    completed = subprocess.run(  # noqa: S603 - fixed synthetic construct, no shell
        command, env=environment, capture_output=True, text=True, timeout=60, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert validation.validate_cell(tmp_path, config)["offered"] > 0
