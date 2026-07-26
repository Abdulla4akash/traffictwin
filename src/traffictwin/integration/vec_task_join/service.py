"""Fail-closed VEC tier/EV/task/action/target reconciliation (VEC-04)."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Iterator, Mapping
from typing import Any

import numpy as np

from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.integration.tos.contract_v2 import (
    validate_perstep_arrays,
    validate_pertask_arrays,
)
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    resolve_vehicle_identity,
    trace_fingerprint,
)
from traffictwin.integration.vec_task_join.models import (
    VecJoinedTaskObservation,
    VecSelectedTargetKind,
    VecTargetAvailability,
    VecTaskJoinReport,
)

_TASK_CLASSES = (TaskClass.T1, TaskClass.T2, TaskClass.T3)
_ACTIONS = (Decision.LOCAL, Decision.V2I, Decision.V2V)
_ABS_LATENCY_TOLERANCE_MS = 0.00390625
_REL_LATENCY_TOLERANCE = 3e-7


class VecTaskJoinError(ValueError):
    """Raised when matched VEC evidence cannot support a complete semantic join."""


def _arrays_fingerprint(arrays: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(arrays):
        value = np.ascontiguousarray(np.asarray(arrays[key]))
        digest.update(key.encode())
        digest.update(b"\0")
        digest.update(value.dtype.str.encode())
        digest.update(b"\0")
        digest.update(str(value.shape).encode())
        digest.update(b"\0")
        digest.update(value.tobytes())
    return digest.hexdigest()


def _validated_arrays(
    trace_arrays: Mapping[str, Any],
    perstep_arrays: Mapping[str, Any],
    pertask_arrays: Mapping[str, Any],
    identity: VecIdentitySnapshot,
) -> tuple[dict[str, np.ndarray[Any, Any]], dict[str, np.ndarray[Any, Any]]]:
    if trace_fingerprint(trace_arrays) != identity.report.trace_fingerprint:
        raise VecTaskJoinError("trace does not match the accepted identity snapshot")
    perstep_report = validate_perstep_arrays(perstep_arrays, trace_arrays)
    if perstep_report.status != "accepted":
        codes = ", ".join(finding.code for finding in perstep_report.findings)
        raise VecTaskJoinError(f"per-step artifact is invalid: {codes}")
    pertask_report = validate_pertask_arrays(pertask_arrays, trace_arrays)
    if pertask_report.status != "accepted":
        codes = ", ".join(finding.code for finding in pertask_report.findings)
        raise VecTaskJoinError(f"per-task artifact is invalid: {codes}")
    perstep = {key: np.asarray(value) for key, value in perstep_arrays.items()}
    pertask = {key: np.asarray(value) for key, value in pertask_arrays.items()}
    return perstep, pertask


def build_task_join_report(
    trace_arrays: Mapping[str, Any],
    perstep_arrays: Mapping[str, Any],
    pertask_arrays: Mapping[str, Any],
    identity: VecIdentitySnapshot,
    *,
    run_label: str,
) -> VecTaskJoinReport:
    """Reconcile every task, action and eligibility state before allowing row access."""

    perstep, pertask = _validated_arrays(trace_arrays, perstep_arrays, pertask_arrays, identity)
    mask = np.asarray(trace_arrays["mask"], dtype=bool)
    task_active: np.ndarray[Any, Any] = pertask["task_active"].astype(bool, copy=False)
    task_met: np.ndarray[Any, Any] = pertask["task_met"].astype(bool, copy=False)
    veh_k = perstep["veh_k"]
    veh_done = perstep["veh_done"]

    if not np.array_equal(perstep["active"], mask.sum(axis=1, dtype=np.int32)):
        raise VecTaskJoinError("per-step active counts do not match the trace mask per second")
    if np.any(task_active & ~mask[:, None, :]):
        raise VecTaskJoinError("an active task exists outside an occupied identity cell")
    if not np.array_equal(task_active.sum(axis=1), veh_k):
        raise VecTaskJoinError("per-task active counts do not match veh_k for every vehicle-second")
    if not np.array_equal((task_met & task_active).sum(axis=1), veh_done):
        raise VecTaskJoinError("per-task deadline successes do not match veh_done")
    if not np.array_equal(task_active.sum(axis=(1, 2)), perstep["arrivals"]):
        raise VecTaskJoinError("per-task arrivals do not match the per-step stream")
    if not np.array_equal((task_met & task_active).sum(axis=(1, 2)), perstep["done"]):
        raise VecTaskJoinError("per-task deadline successes do not match the per-step stream")
    task_latency = np.where(task_active, pertask["task_lat_ms"], np.float32(0.0))
    # The verification sum runs in float64: a float32 reduction's own rounding at
    # wide-trace magnitudes (thousands of active tasks per step) exceeds the
    # tolerance and would reject evidence whose float64 sum reconciles exactly.
    latency_by_step = task_latency.astype(np.float64).sum(axis=(1, 2))
    for index, (observed, expected) in enumerate(
        zip(latency_by_step, perstep["lat_sum"], strict=True)
    ):
        if not math.isclose(
            float(observed),
            float(expected),
            rel_tol=_REL_LATENCY_TOLERANCE,
            abs_tol=_ABS_LATENCY_TOLERANCE_MS,
        ):
            raise VecTaskJoinError(f"per-task latency does not reconcile at time index {index}")

    task_types = pertask["task_type"][task_active]
    actions_grid = np.broadcast_to(perstep["veh_action"][:, None, :], task_active.shape)
    task_actions = actions_grid[task_active]
    best_rsu_grid = np.broadcast_to(perstep["veh_best_rsu"][:, None, :], task_active.shape)
    best_v2v_grid = np.broadcast_to(perstep["veh_best_v2v"][:, None, :], task_active.shape)
    task_rsu = best_rsu_grid[task_active]
    task_v2v = best_v2v_grid[task_active]
    class_counts = Counter(_TASK_CLASSES[int(code)] for code in task_types)
    action_counts = Counter(_ACTIONS[int(code)] for code in task_actions)
    availability_counts: Counter[VecTargetAvailability] = Counter()
    for action_code, rsu, peer in zip(task_actions, task_rsu, task_v2v, strict=True):
        if int(action_code) == 0:
            availability_counts[VecTargetAvailability.NOT_APPLICABLE_LOCAL] += 1
        elif (int(action_code) == 1 and int(rsu) >= 0) or (
            int(action_code) == 2 and int(peer) >= 0
        ):
            availability_counts[VecTargetAvailability.ELIGIBLE_TARGET] += 1
        else:
            availability_counts[VecTargetAvailability.NO_ELIGIBLE_TARGET] += 1

    return VecTaskJoinReport(
        scenario=identity.report.scenario,
        run_label=run_label,
        identity_snapshot_fingerprint=identity.fingerprint(),
        trace_fingerprint=trace_fingerprint(trace_arrays),
        perstep_fingerprint=_arrays_fingerprint(perstep_arrays),
        pertask_fingerprint=_arrays_fingerprint(pertask_arrays),
        active_vehicle_seconds=int(mask.sum()),
        total_tasks=int(task_active.sum()),
        deadline_met_tasks=int((task_met & task_active).sum()),
        task_class_counts={task_class: class_counts[task_class] for task_class in _TASK_CLASSES},
        action_counts={action: action_counts[action] for action in _ACTIONS},
        target_availability_counts={
            state: availability_counts[state] for state in VecTargetAvailability
        },
    )


def iter_joined_tasks(
    trace_arrays: Mapping[str, Any],
    perstep_arrays: Mapping[str, Any],
    pertask_arrays: Mapping[str, Any],
    identity: VecIdentitySnapshot,
    report: VecTaskJoinReport,
) -> Iterator[VecJoinedTaskObservation]:
    """Yield task rows only after all artifact fingerprints and counts reconcile."""

    if report.identity_snapshot_fingerprint != identity.fingerprint():
        raise VecTaskJoinError("identity snapshot does not match the task-join report")
    if report.trace_fingerprint != trace_fingerprint(trace_arrays):
        raise VecTaskJoinError("trace does not match the task-join report")
    if report.perstep_fingerprint != _arrays_fingerprint(perstep_arrays):
        raise VecTaskJoinError("per-step artifact does not match the task-join report")
    if report.pertask_fingerprint != _arrays_fingerprint(pertask_arrays):
        raise VecTaskJoinError("per-task artifact does not match the task-join report")

    times = np.asarray(trace_arrays["times"])
    perstep = {key: np.asarray(value) for key, value in perstep_arrays.items()}
    pertask = {key: np.asarray(value) for key, value in pertask_arrays.items()}
    active_coordinates = np.argwhere(pertask["task_active"])
    for time_index_raw, task_index_raw, slot_raw in active_coordinates:
        time_index = int(time_index_raw)
        task_index = int(task_index_raw)
        slot = int(slot_raw)
        vehicle_id = resolve_vehicle_identity(identity, time_index=time_index, slot=slot)
        if vehicle_id is None:
            raise VecTaskJoinError("accepted task cell has no vehicle identity")
        action = _ACTIONS[int(perstep["veh_action"][time_index, slot])]
        rsu_raw = int(perstep["veh_best_rsu"][time_index, slot])
        peer_raw = int(perstep["veh_best_v2v"][time_index, slot])
        eligible_rsu = rsu_raw if rsu_raw >= 0 else None
        eligible_peer = peer_raw if peer_raw >= 0 else None
        if action is Decision.LOCAL:
            availability = VecTargetAvailability.NOT_APPLICABLE_LOCAL
            kind = VecSelectedTargetKind.NONE
            selected = None
        elif action is Decision.V2I and eligible_rsu is not None:
            availability = VecTargetAvailability.ELIGIBLE_TARGET
            kind = VecSelectedTargetKind.RSU_INDEX
            selected = eligible_rsu
        elif action is Decision.V2V and eligible_peer is not None:
            availability = VecTargetAvailability.ELIGIBLE_TARGET
            kind = VecSelectedTargetKind.VEHICLE_SLOT_INDEX
            selected = eligible_peer
        else:
            availability = VecTargetAvailability.NO_ELIGIBLE_TARGET
            kind = VecSelectedTargetKind.NONE
            selected = None
        yield VecJoinedTaskObservation(
            scenario=report.scenario,
            run_label=report.run_label,
            time_index=time_index,
            trace_time_s=float(times[time_index]),
            slot=slot,
            sumo_vehicle_id=vehicle_id,
            task_index=task_index,
            task_class=_TASK_CLASSES[int(pertask["task_type"][time_index, task_index, slot])],
            latency_ms=float(pertask["task_lat_ms"][time_index, task_index, slot]),
            deadline_met=bool(pertask["task_met"][time_index, task_index, slot]),
            slot_tier=int(perstep["slot_tier"][slot]),
            slot_is_ev=bool(perstep["slot_is_ev"][slot]),
            action=action,
            eligible_best_rsu=eligible_rsu,
            eligible_best_v2v=eligible_peer,
            target_availability=availability,
            selected_target_kind=kind,
            selected_target_index=selected,
        )
