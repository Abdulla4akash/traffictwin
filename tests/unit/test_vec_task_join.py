"""Synthetic golden and refusal tests for VEC-04 joins."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from tests.tos_v2_helpers import (
    V2_SCENARIO,
    build_v2_occupancy_rows,
    build_v2_perstep,
    build_v2_pertask,
    build_v2_trace,
)
from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
)
from traffictwin.integration.vec_task_join import (
    VecJoinedTaskObservation,
    VecTargetAvailability,
    VecTaskJoinError,
    VecTaskJoinReport,
    build_task_join_report,
    iter_joined_tasks,
    vec_task_join_contract,
)


def _identity() -> VecIdentitySnapshot:
    header, rows = build_v2_occupancy_rows()
    return build_vehicle_identity_snapshot(build_v2_trace(), header, rows, scenario=V2_SCENARIO)


def _report() -> VecTaskJoinReport:
    return build_task_join_report(
        build_v2_trace(),
        build_v2_perstep(),
        build_v2_pertask(),
        _identity(),
        run_label="synthetic_golden",
    )


def test_golden_join_reconciles_all_count_families() -> None:
    report = _report()

    assert report.total_tasks == 7
    assert report.deadline_met_tasks == 5
    assert sum(report.task_class_counts.values()) == 7
    assert report.action_counts == {
        Decision.LOCAL: 3,
        Decision.V2I: 3,
        Decision.V2V: 1,
    }
    assert report.target_availability_counts == {
        VecTargetAvailability.NOT_APPLICABLE_LOCAL: 3,
        VecTargetAvailability.ELIGIBLE_TARGET: 4,
        VecTargetAvailability.NO_ELIGIBLE_TARGET: 0,
    }
    assert report.no_target_is_failure is False
    assert report.action_is_transfer_confirmation is False
    assert vec_task_join_contract().fingerprint() == vec_task_join_contract().fingerprint()


def test_joined_rows_have_exact_vehicle_and_fixed_slot_attributes() -> None:
    rows = list(
        iter_joined_tasks(
            build_v2_trace(),
            build_v2_perstep(),
            build_v2_pertask(),
            _identity(),
            _report(),
        )
    )

    assert len(rows) == 7
    recycled = [row for row in rows if row.time_index == 3 and row.slot == 0]
    assert recycled[0].sumo_vehicle_id == "veh_synthetic_c"
    assert recycled[0].slot_tier == 0
    assert all(row.transfer_confirmed is False for row in rows)
    assert all(row.eventual_completion == "unavailable" for row in rows)


def test_no_eligible_target_is_visible_but_not_called_failure() -> None:
    perstep = build_v2_perstep()
    perstep["veh_best_rsu"] = np.asarray(perstep["veh_best_rsu"]).copy()
    perstep["veh_best_rsu"][0, 1] = -1
    report = build_task_join_report(
        build_v2_trace(), perstep, build_v2_pertask(), _identity(), run_label="no_target"
    )
    rows = list(
        iter_joined_tasks(build_v2_trace(), perstep, build_v2_pertask(), _identity(), report)
    )
    row = next(item for item in rows if item.time_index == 0 and item.slot == 1)

    assert row.action is Decision.V2I
    assert row.target_availability is VecTargetAvailability.NO_ELIGIBLE_TARGET
    assert row.selected_target_index is None
    assert row.failure_inferred is False


def test_task_count_deadline_and_latency_mismatches_fail_closed() -> None:
    for key, position, value, message in (
        ("task_active", (0, 1, 0), False, "active counts"),
        ("task_met", (0, 0, 0), False, "deadline successes"),
        ("task_lat_ms", (0, 0, 0), np.float32(71.0), "latency"),
    ):
        pertask = build_v2_pertask()
        pertask[key] = np.asarray(pertask[key]).copy()
        pertask[key][position] = value
        with pytest.raises(VecTaskJoinError, match=message):
            build_task_join_report(
                build_v2_trace(),
                build_v2_perstep(),
                pertask,
                _identity(),
                run_label="bad",
            )


def test_task_outside_occupancy_and_changed_artifact_are_refused() -> None:
    pertask = build_v2_pertask()
    pertask["task_active"] = np.asarray(pertask["task_active"]).copy()
    pertask["task_active"][0, 0, 2] = True
    with pytest.raises(VecTaskJoinError):
        build_task_join_report(
            build_v2_trace(), build_v2_perstep(), pertask, _identity(), run_label="bad"
        )

    perstep = build_v2_perstep()
    perstep["veh_queue_ms"] = np.asarray(perstep["veh_queue_ms"]).copy()
    report = _report()
    perstep["veh_queue_ms"][0, 0] = np.float32(1.0)
    with pytest.raises(VecTaskJoinError, match="does not match"):
        list(iter_joined_tasks(build_v2_trace(), perstep, build_v2_pertask(), _identity(), report))


def test_semantic_claims_cannot_be_strengthened() -> None:
    row = next(
        iter_joined_tasks(
            build_v2_trace(),
            build_v2_perstep(),
            build_v2_pertask(),
            _identity(),
            _report(),
        )
    )
    payload = row.model_dump(mode="json")
    payload["transfer_confirmed"] = True
    with pytest.raises(ValidationError, match="transfer_confirmed"):
        VecJoinedTaskObservation.model_validate(payload)


def _wide_fixture() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Return a consistent wide-trace fixture at real incident-run magnitudes.

    The first full-length inc execution (3,649 active tasks per step, per-step
    latency sums near 3.9e7 ms) was refused by the latency reconciliation when
    the verification sum ran in float32: the verifier's own rounding exceeded
    the tolerance at one step while the evidence itself reconciled exactly in
    float64. numpy's pairwise summation makes that float32 failure depend on
    the exact value ordering, so the deterministic revert-guard is the real
    published inc run behind the env-gated integration chain test; this
    fixture pins that wide-magnitude evidence stays admissible.
    """

    t_count, max_n, task_k = 2, 2_000, 5
    occupied = 1_825
    mask: np.ndarray[tuple[int, ...], np.dtype[np.bool_]] = np.zeros((t_count, max_n), dtype=bool)
    mask[:, :occupied] = True
    trace: dict[str, object] = {
        "T": np.int32(t_count),
        "dt": np.float32(1.0),
        "mask": mask,
        "maxN": np.int32(max_n),
        "pos_x": np.where(mask, 10.0, 0.0).astype(np.float32),
        "pos_y": np.where(mask, 20.0, 0.0).astype(np.float32),
        "rsu_xy": np.array([[0.0, 0.0], [100.0, 100.0]], dtype=np.float32),
        "speed": np.where(mask, 5.0, 0.0).astype(np.float32),
        "sumo_seed": np.int32(42),
        "times": np.arange(t_count, dtype=np.float32),
        "window": np.str_("wide_regression_window"),
    }
    rng = np.random.default_rng(20_260_726)
    task_active: np.ndarray[tuple[int, ...], np.dtype[np.bool_]] = np.zeros(
        (t_count, task_k, max_n), dtype=bool
    )
    task_active[:, :2, :occupied] = True
    latencies: np.ndarray[tuple[int, ...], np.dtype[np.float32]] = np.zeros(
        (t_count, task_k, max_n), dtype=np.float32
    )
    for step in range(t_count):
        base = rng.uniform(2.4, 21_000, size=2 * occupied)
        heavy = rng.uniform(50_000, 100_449, size=2 * occupied)
        chosen = np.where(rng.uniform(size=2 * occupied) < 0.05, heavy, base)
        latencies[step][task_active[step]] = chosen.astype(np.float32)
    veh_k: np.ndarray[tuple[int, ...], np.dtype[np.int8]] = np.zeros(
        (t_count, max_n), dtype=np.int8
    )
    veh_k[:, :occupied] = 2
    lat_sum = (
        np.where(task_active, latencies, np.float32(0.0))
        .astype(np.float64)
        .sum(axis=(1, 2))
        .astype(np.float32)
    )
    arrivals: np.ndarray[tuple[int, ...], np.dtype[np.int32]] = np.full(
        t_count, 2 * occupied, dtype=np.int32
    )
    perstep: dict[str, object] = {
        "active": mask.sum(axis=1).astype(np.int32),
        "arrivals": arrivals,
        "done": np.zeros(t_count, dtype=np.int32),
        "lat_sum": lat_sum,
        "n_local": arrivals.copy(),
        "n_v2i": np.zeros(t_count, dtype=np.int32),
        "n_v2v": np.zeros(t_count, dtype=np.int32),
        "rsu_busy_ms": np.zeros((t_count, 2), dtype=np.float32),
        "rsu_load": np.zeros((t_count, 2), dtype=np.int32),
        "slot_is_ev": np.zeros(max_n, dtype=bool),
        "slot_tier": np.zeros(max_n, dtype=np.int8),
        "times": trace["times"],
        "veh_action": np.zeros((t_count, max_n), dtype=np.int8),
        "veh_best_rsu": np.full((t_count, max_n), -1, dtype=np.int16),
        "veh_best_v2v": np.full((t_count, max_n), -1, dtype=np.int16),
        "veh_done": np.zeros((t_count, max_n), dtype=np.int16),
        "veh_k": veh_k,
        "veh_queue_ms": np.zeros((t_count, max_n), dtype=np.float32),
    }
    pertask: dict[str, object] = {
        "task_active": task_active,
        "task_lat_ms": latencies,
        "task_met": np.zeros((t_count, task_k, max_n), dtype=bool),
        "task_type": np.zeros((t_count, task_k, max_n), dtype=np.int8),
    }
    return trace, perstep, pertask


def test_wide_trace_latency_sums_reconcile_at_incident_magnitudes() -> None:
    trace, perstep, pertask = _wide_fixture()
    header = ("sumo_vehicle_id", "slot", "t_enter", "t_exit")
    rows = [[f"veh{slot}", str(slot), "0", "1"] for slot in range(1_825)]
    identity = build_vehicle_identity_snapshot(trace, header, rows, scenario="wide_synthetic")

    report = build_task_join_report(trace, perstep, pertask, identity, run_label="wide_regression")

    assert report.total_tasks == 7_300
    assert report.deadline_met_tasks == 0
    assert float(np.asarray(perstep["lat_sum"]).max()) > 3e7
