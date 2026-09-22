"""Differential construct checks: no traffic campaign is executed here."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from numpy.typing import ArrayLike, NDArray

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTAL = ROOT / "docs/evaluation/e3a_csf3_2026-09-11/experimental"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p2c = load_module("e3a_p2c_test", EXPERIMENTAL / "p2c.py")
reference = load_module("e3a_p2c_reference", EXPERIMENTAL / "vendor/preserved_e3_p2c_placement.py")


def combined(limbs: tuple[Any, Any]) -> int:
    return int(limbs[0]) | (int(limbs[1]) << 32)


@pytest.mark.parametrize(
    "fields,expected,pair",
    [
        ((0, 0, 0, 0, 0), 0x7D19C361A3548205, (1, 9)),
        ((0, 1, 3599, 4, 12439), 0x295C562A48F4F730, (2, 7)),
        ((0, 2, 1234, 2, 5678), 0x350F2378AD774558, (2, 8)),
    ],
)
def test_normative_hash_vectors(
    fields: tuple[int, ...], expected: int, pair: tuple[int, int]
) -> None:
    limbs = tuple(p2c.u64(value) for value in fields)
    actual = jax.jit(p2c.mix_keys)(limbs)
    assert combined(actual) == expected
    indices = jax.jit(p2c.pair_indices)(limbs, jnp.int32(10))
    assert tuple(sorted(map(int, indices))) == pair
    assert not jax.config.jax_enable_x64


def test_uint64_overflow_and_full_key_range_differential() -> None:
    rng = np.random.default_rng(7701)
    values = [0, 1, 0xFFFFFFFF, 0x100000000, (1 << 63), (1 << 64) - 1]
    values += [int(value) for value in rng.integers(0, (1 << 64) - 1, 100, dtype=np.uint64)]
    run_split = jax.jit(p2c.splitmix64)
    run_fold = jax.jit(p2c.mix_keys)
    run_pair = jax.jit(p2c.pair_indices)
    for index, value in enumerate(values):
        assert combined(run_split(p2c.u64(value))) == reference._splitmix64(value)
        fields = (value, values[-index - 1], value ^ 0xFFFFFFFF, index, value)
        limbs = tuple(p2c.u64(field) for field in fields)
        assert combined(run_fold(limbs)) == reference._mix_keys(*fields)
        for count in (2, 3, 10, 19, 65535):
            pair = tuple(sorted(map(int, run_pair(limbs, jnp.int32(count)))))
            assert pair == reference._deterministic_pair(range(count), *fields)


def run_case(
    *,
    busy: ArrayLike,
    loads: ArrayLike,
    deadline: ArrayLike,
    work: ArrayLike,
    attempts: ArrayLike | None = None,
    radio: ArrayLike | None = None,
    cap: int = 3,
    seed: int = 0,
    fleet: int = 1,
    tick: int = 5,
    slot: int = 0,
    iterations: int = 3,
) -> Any:  # noqa: ANN401 -- dynamically loaded JAX result pytree
    work = np.asarray(work, dtype=np.float32)
    width = len(work)
    args: dict[str, Any] = {
        "attempts": jnp.asarray(np.ones(width, bool) if attempts is None else attempts),
        "ingress_radio_viable": jnp.asarray(np.ones(width, bool) if radio is None else radio),
        "deadlines_ms": jnp.asarray(np.broadcast_to(deadline, (width,)), dtype=jnp.float32),
        "service_work_ms_by_rsu": jnp.asarray(np.broadcast_to(work[:, None], (width, len(busy)))),
        "base_busy_ms": jnp.asarray(busy, dtype=jnp.float32),
        "base_load": jnp.asarray(loads, dtype=jnp.int32),
        "capacity": cap,
        "reconciliation_iterations": iterations,
        "evaluator_seed": seed,
        "fleet_seed": fleet,
        "outer_tick": jnp.int32(tick),
        "task_slot": jnp.int32(slot),
    }
    result = jax.jit(
        p2c.p2c_sequential,
        static_argnames=("capacity", "reconciliation_iterations", "evaluator_seed", "fleet_seed"),
    )(**args)
    return jax.tree.map(np.asarray, result)


def reference_pass(
    *,
    busy: ArrayLike,
    loads: ArrayLike,
    deadline: ArrayLike,
    work: ArrayLike,
    attempts: ArrayLike,
    radio: ArrayLike,
    cap: int,
    seed: int = 0,
    fleet: int = 1,
    tick: int = 5,
    slot: int = 0,
) -> tuple[list[tuple[Any, ...]], NDArray[Any], NDArray[Any]]:
    busy = np.asarray(busy, dtype=np.float32).copy()
    loads = np.asarray(loads, dtype=np.int32).copy()
    output = []
    width = len(work)
    for vehicle, (attempt, viable, task_deadline, task_work) in enumerate(
        zip(attempts, radio, deadline, work, strict=True)
    ):
        ordinal = slot * width + vehicle
        target, pair, count, gate, cap_rej = -1, (-1, -1), 0, False, False
        if attempt and viable:
            feasible = np.flatnonzero((busy < task_deadline) & (loads < cap)).tolist()
            count = len(feasible)
            if count:
                receipt = reference.p2c_select(
                    feasible_candidates=feasible,
                    declared_workloads={i: float(value) for i, value in enumerate(busy)},
                    reservation_overlay={},
                    state_age_ms=0,
                    evaluator_seed=seed,
                    fleet_seed=fleet,
                    outer_tick=tick,
                    task_slot=slot,
                    sequential_task_ordinal=ordinal,
                    task_work_ms=float(task_work),
                )
                assert receipt.rejection_reason is None
                target = receipt.chosen_rsu
                pair = receipt.sampled_pair or (-1, -1)
                busy[target] += np.float32(task_work)
                loads[target] += 1
            else:
                gate = not np.any(busy < task_deadline)
                cap_rej = not gate
        output.append((target, pair, count, gate, cap_rej, ordinal))
    return output, busy, loads


@pytest.mark.parametrize(
    "busy,loads,deadline,expected_gate,expected_cap",
    [
        ([10, 10], [0, 0], 10, [True], [False]),  # strict equality rejects
        ([0, 10], [3, 0], 10, [False], [True]),  # deadline-feasible full
        ([0, 0], [3, 3], 10, [False], [True]),
    ],
)
def test_no_feasible_no_selection_no_reservation(
    busy: list[int],
    loads: list[int],
    deadline: int,
    expected_gate: list[bool],
    expected_cap: list[bool],
) -> None:
    result = run_case(busy=busy, loads=loads, deadline=deadline, work=[7])
    np.testing.assert_array_equal(result.selected_rsu, [-1])
    np.testing.assert_array_equal(result.sampled_pair, [[-1, -1]])
    np.testing.assert_array_equal(result.gate_rejected, expected_gate)
    np.testing.assert_array_equal(result.cap_rejected, expected_cap)
    np.testing.assert_array_equal(result.effective_busy_ms, busy)
    np.testing.assert_array_equal(result.effective_load, loads)
    np.testing.assert_array_equal(result.ranking_workload_inspections, [0])


def test_sole_candidate_reservation_closes_gate_then_rejection() -> None:
    result = run_case(busy=[0, 30], loads=[0, 0], deadline=10, work=[12, 12])
    np.testing.assert_array_equal(result.selected_rsu, [0, -1])
    np.testing.assert_array_equal(result.sampled_pair, [[-1, -1], [-1, -1]])
    np.testing.assert_array_equal(result.feasible_count, [1, 0])
    np.testing.assert_array_equal(result.effective_busy_ms, [12, 30])
    np.testing.assert_array_equal(result.effective_load, [1, 0])
    np.testing.assert_array_equal(result.gate_rejected, [False, True])


def test_pair_tie_uses_lower_rsu_and_never_global_min_outside_pair() -> None:
    # Normative pair for this key is (1, 9); global min 0 is outside the pair.
    result = run_case(busy=[0] + [5] * 9, loads=[0] * 10, deadline=10, work=[1], fleet=0, tick=0)
    np.testing.assert_array_equal(result.sampled_pair, [[1, 9]])
    np.testing.assert_array_equal(result.selected_rsu, [1])
    np.testing.assert_array_equal(result.feasibility_workload_checks, [10])
    np.testing.assert_array_equal(result.ranking_workload_inspections, [2])
    np.testing.assert_array_equal(result.unique_workload_values_observed, [10])


def test_radio_unavailable_precedes_gate_and_does_not_reserve() -> None:
    result = run_case(
        busy=[10, 10],
        loads=[3, 3],
        deadline=10,
        work=[4, 5],
        attempts=[True, False],
        radio=[False, True],
    )
    np.testing.assert_array_equal(result.selected_rsu, [-1, -1])
    assert not result.coarse_candidate.any()
    assert not result.gate_rejected.any()
    assert not result.cap_rejected.any()
    assert not result.feasibility_workload_checks.any()
    np.testing.assert_array_equal(result.effective_busy_ms, [10, 10])


def test_dense_ordinal_survives_padding_actor_and_rejection_paths() -> None:
    width = 7
    result = run_case(
        busy=[0] * 10,
        loads=[0] * 10,
        deadline=[20, 20, 0, 20, 20, 20, 20],
        work=[1] * width,
        attempts=[False, True, True, False, True, True, True],
        radio=[True, False, True, True, True, True, True],
        slot=4,
    )
    np.testing.assert_array_equal(result.sequential_task_ordinal, np.arange(28, 35))
    for vehicle in (4, 5, 6):
        expected = reference._deterministic_pair(range(10), 0, 1, 5, 4, 28 + vehicle)
        assert tuple(result.sampled_pair[vehicle]) == expected
    np.testing.assert_array_equal(result.selected_rsu[:4], [-1] * 4)


def test_randomized_actual_decisions_match_preserved_selector_and_n0_contract() -> None:
    rng = np.random.default_rng(3129)
    for _ in range(12):
        width, count = 24, 10
        args: dict[str, Any] = {
            "busy": rng.integers(0, 30, count).tolist(),
            "loads": rng.integers(0, 4, count).tolist(),
            "deadline": rng.integers(5, 35, width).astype(np.float32),
            "work": rng.uniform(0.1, 8, width).astype(np.float32),
            "attempts": rng.random(width) > 0.2,
            "radio": rng.random(width) > 0.2,
            "cap": 4,
            "slot": int(rng.integers(0, 5)),
            "tick": int(rng.integers(0, 3600)),
        }
        actual = run_case(**args)
        expected, busy, loads = reference_pass(**args)
        for index, (target, pair, count, gate, cap_rej, ordinal) in enumerate(expected):
            assert actual.selected_rsu[index] == target
            assert tuple(actual.sampled_pair[index]) == pair
            assert actual.feasible_count[index] == count
            assert actual.gate_rejected[index] == gate
            assert actual.cap_rejected[index] == cap_rej
            assert actual.sequential_task_ordinal[index] == ordinal
        np.testing.assert_array_equal(actual.effective_busy_ms, busy)
        np.testing.assert_array_equal(actual.effective_load, loads)
        once = run_case(**args, iterations=1)
        for first, repeated in zip(once, actual, strict=True):
            np.testing.assert_array_equal(first, repeated)
