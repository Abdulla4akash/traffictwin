"""Tiny synthetic integration and exact frozen-comparator parity checks."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / "docs/evaluation/e3a_csf3_2026-09-11/experimental/evaluator_v3.py"
OLD = ROOT / "docs/dissertation/joint_confirmation_2026-09-08/experimental/evaluator_v2.py"


@pytest.fixture(scope="module")
def outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], dict[str, Any]]:
    temporary = tmp_path_factory.mktemp("e3a_construct")
    # A flat deployment must not depend on the source repository's parents.
    standalone = temporary / "standalone_experimental"
    shutil.copytree(NEW.parent, standalone, ignore=shutil.ignore_patterns("__pycache__"))
    new_evaluator = standalone / "evaluator_v3.py"
    width, ticks = 8, 3
    mask: NDArray[np.bool_] = np.ones((ticks, width), dtype=bool)
    mask[0, 0] = False
    np.savez(
        temporary / "trace.npz",
        pos_x=np.zeros((ticks, width), np.float32),
        pos_y=np.zeros((ticks, width), np.float32),
        mask=mask,
        times=np.arange(ticks, dtype=np.float32),
        rsu_xy=np.array([[10, 10], [20, 20], [30, 30], [40, 40]], dtype=np.float32),
    )
    actor: dict[str, NDArray[np.float32]] = {}
    for layer, (left, right) in enumerate(((17, 4), (4, 4), (4, 3))):
        actor[f"Dense_{layer}.kernel"] = np.zeros((left, right), dtype=np.float32)
        actor[f"Dense_{layer}.bias"] = np.zeros(right, dtype=np.float32)
    actor["Dense_2.bias"][1] = 10.0  # deterministic synthetic V2I actor
    np.savez(temporary / "actor.npz", **actor)
    results = {}
    for version, evaluator, arm in (
        ("old", OLD, "ingress_dla"),
        ("old", OLD, "per_task_dla"),
        ("new", new_evaluator, "ingress_dla"),
        ("new", new_evaluator, "per_task_dla"),
        ("new", new_evaluator, "p2c_dla"),
    ):
        prefix = temporary / f"{version}_{arm}"
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("VEC_JAX_")
        }
        command = [
            sys.executable,
            str(evaluator),
            "--trace",
            str(temporary / "trace.npz"),
            "--actor",
            str(temporary / "actor.npz"),
            "--fleet",
            "uk2030",
            "--seed",
            "0",
            "--fleet-seed",
            "1",
            "--rsu-lb",
            arm,
            "--substep-queue",
            "sequential",
            "--rsu-cap-mode",
            "reject",
            "--veh-queue",
            "conserved",
            "--rsu-cap-abs",
            "2",
            "--per-step-out",
            f"{prefix}.steps.npz",
            "--per-task-out",
            f"{prefix}.tasks.npz",
            "--out-json",
            f"{prefix}.json",
        ]
        completed = subprocess.run(  # noqa: S603 -- fixed evaluator and synthetic temporary inputs
            command, env=environment, capture_output=True, text=True, timeout=60
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        results[version, arm] = {
            "steps": dict(np.load(f"{prefix}.steps.npz")),
            "tasks": dict(np.load(f"{prefix}.tasks.npz")),
            "summary": json.loads(Path(f"{prefix}.json").read_text()),
        }
    return results


@pytest.mark.parametrize("arm", ["ingress_dla", "per_task_dla"])
def test_old_comparators_preserve_every_numeric_artifact(
    outputs: dict[tuple[str, str], dict[str, Any]], arm: str
) -> None:
    old, new = outputs["old", arm], outputs["new", arm]
    for category in ("steps", "tasks"):
        assert old[category].keys() == new[category].keys()
        for name in old[category]:
            np.testing.assert_array_equal(new[category][name], old[category][name], err_msg=name)
    for name in old["summary"]:
        if name not in ("wall_s", "extension_schema"):
            assert new["summary"][name] == old["summary"][name], name
    assert new["summary"]["enter_reset"] is False


def test_p2c_emitted_paths_keys_exogenous_and_conservation(
    outputs: dict[tuple[str, str], dict[str, Any]],
) -> None:
    actual = outputs["new", "p2c_dla"]
    tasks, steps = actual["tasks"], actual["steps"]
    reference = outputs["new", "per_task_dla"]
    for name in (
        "exogenous_keys",
        "slot_tier",
        "slot_is_ev",
        "slot_soc_initial",
        "veh_k",
        "observation_task_type",
        "observation_task_size",
    ):
        np.testing.assert_array_equal(steps[name], reference["steps"][name], err_msg=name)
    for name in ("task_type", "task_sizes_mb", "task_active"):
        np.testing.assert_array_equal(tasks[name], reference["tasks"][name], err_msg=name)
    selected = tasks["task_selected_execution_rsu"]
    admitted = tasks["task_v2i_admitted"]
    np.testing.assert_array_equal(selected >= 0, admitted)
    np.testing.assert_array_equal(selected, tasks["task_execution_rsu"])
    assert tasks["task_active"].sum() > 0
    assert admitted.sum() > 0
    assert np.isin(tasks["task_outcome"], (3, 4, 7)).sum() > 0
    dense: NDArray[np.int32] = np.arange(40, dtype=np.int32).reshape(5, 8)
    np.testing.assert_array_equal(
        tasks["task_p2c_sequential_ordinal"], np.broadcast_to(dense, (3, 5, 8))
    )
    count = tasks["task_p2c_feasible_count"]
    np.testing.assert_array_equal(
        tasks["task_p2c_ranking_workload_inspections"], np.minimum(count, 2)
    )
    assert (tasks["task_p2c_sampled_pair"][count < 2] == -1).all()
    # Reconstruct the actual emitted causal queues, independently of the kernel.
    for tick in range(3):
        busy = steps["rsu_start_busy_ms"][tick].copy()
        load = steps["rsu_start_load"][tick].copy()
        for slot in range(5):
            for vehicle in range(8):
                target = selected[tick, slot, vehicle]
                attempt = tasks["task_ingress_rsu"][tick, slot, vehicle] >= 0
                radio = steps["veh_v2i_quality"][tick, vehicle] > 0.0
                if attempt and radio:
                    deadline = (100.0, 500.0, 100.0)[tasks["task_type"][tick, slot, vehicle]]
                    feasible = np.flatnonzero((busy < deadline) & (load < 2))
                    assert count[tick, slot, vehicle] == len(feasible)
                    assert tasks["task_p2c_feasibility_workload_checks"][tick, slot, vehicle] == 4
                    if not len(feasible):
                        expected_code = 3 if not np.any(busy < deadline) else 4
                        assert tasks["task_outcome"][tick, slot, vehicle] == expected_code
                        assert target == -1
                    elif len(feasible) == 1:
                        assert target == feasible[0]
                    else:
                        pair = tasks["task_p2c_sampled_pair"][tick, slot, vehicle]
                        assert pair[0] < pair[1]
                        assert all(member in feasible for member in pair)
                        assert target == min(pair, key=lambda member: (busy[member], member))
                else:
                    assert count[tick, slot, vehicle] == 0
                    assert tasks["task_p2c_feasibility_workload_checks"][tick, slot, vehicle] == 0
                if target >= 0:
                    assert tasks["task_p2c_placement_busy_ms"][tick, slot, vehicle] == busy[target]
                    busy[target] += tasks["task_rsu_service_ms"][tick, slot, vehicle]
                    load[target] += 1
        np.testing.assert_array_equal(busy, steps["rsu_pre_drain_busy_ms"][tick])
        np.testing.assert_array_equal(load, steps["rsu_pre_drain_load"][tick])
