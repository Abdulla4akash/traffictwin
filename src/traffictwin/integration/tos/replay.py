"""Logical historical replay over documented TOS per-step and trace arrays."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from traffictwin.integration.tos.models import (
    TosReplayFrame,
    TosReplayPoint,
    TosRsuSourceState,
    TosVehicleSlotState,
    action_label,
)
from traffictwin.integration.tos.readers import (
    TosPackageError,
    package_relative,
    perstep_path,
    read_summary_for_key,
    trace_path,
)

_SERIES_KEYS = (
    "times",
    "arrivals",
    "done",
    "lat_sum",
    "active",
    "n_local",
    "n_v2i",
    "n_v2v",
)


def load_replay_series(
    root: str | Path,
    run_key: str,
    *,
    stride: int = 1,
) -> list[TosReplayPoint]:
    """Load documented one-dimensional replay aggregates."""

    if stride < 1:
        raise ValueError("stride must be at least 1")
    np = _numpy()
    source = perstep_path(root, run_key)
    try:
        with np.load(source, allow_pickle=False) as archive:
            missing = sorted(set(_SERIES_KEYS) - set(archive.files))
            if missing:
                raise TosPackageError("per-step arrays are missing: " + ", ".join(missing))
            arrays = {key: archive[key] for key in _SERIES_KEYS}
    except (OSError, ValueError) as exc:
        if isinstance(exc, TosPackageError):
            raise
        raise TosPackageError(f"cannot load per-step replay: {exc}") from exc
    length = len(arrays["times"])
    if any(len(array) != length for array in arrays.values()):
        raise TosPackageError("per-step aggregate arrays do not share one timeline length")
    points = [_point_from_arrays(arrays, index) for index in range(0, length, stride)]
    return points


def load_replay_frame(
    root: str | Path,
    run_key: str,
    index: int,
    *,
    max_vehicles: int = 100,
) -> TosReplayFrame:
    """Load one bounded frame joined strictly by timestamp and padded slot index."""

    if index < 0:
        raise ValueError("replay index must be non-negative")
    if max_vehicles < 1 or max_vehicles > 1000:
        raise ValueError("max_vehicles must be between 1 and 1000")
    np = _numpy()
    stream_path = perstep_path(root, run_key)
    summary = read_summary_for_key(root, run_key)
    mobility_path = trace_path(root, summary.trace)
    try:
        with np.load(stream_path, allow_pickle=False) as stream:
            if index >= len(stream["times"]):
                raise TosPackageError(
                    f"replay index {index} is outside 0..{len(stream['times']) - 1}"
                )
            point_arrays = {key: stream[key] for key in _SERIES_KEYS}
            point = _point_from_arrays(point_arrays, index)
            actions = stream["veh_action"][index]
            arrivals = stream["veh_k"][index]
            completed = stream["veh_done"][index]
            queue_delay = stream["veh_queue_ms"][index]
            rsu_load = stream["rsu_load"][index]
            rsu_busy = stream["rsu_busy_ms"][index]
        with np.load(mobility_path, allow_pickle=False) as trace:
            if index >= len(trace["times"]):
                raise TosPackageError("trace timeline is shorter than the per-step timeline")
            trace_time = float(trace["times"][index])
            if not math.isclose(trace_time, point.timestamp_s, rel_tol=0, abs_tol=1e-5):
                raise TosPackageError("trace and per-step timestamps do not align")
            mask = trace["mask"][index]
            positions_x = trace["pos_x"][index]
            positions_y = trace["pos_y"][index]
            speeds = trace["speed"][index]
            rsu_xy = trace["rsu_xy"]
    except (OSError, ValueError, KeyError) as exc:
        if isinstance(exc, TosPackageError):
            raise
        raise TosPackageError(f"cannot load replay frame: {exc}") from exc

    active_indices = [int(value) for value in np.flatnonzero(mask)]
    selected = active_indices[:max_vehicles]
    vehicles = [
        TosVehicleSlotState(
            slot_reference=f"slot:{slot}@time-index:{index}",
            slot_index=slot,
            position_x_source_units=float(positions_x[slot]),
            position_y_source_units=float(positions_y[slot]),
            speed_source_units=float(speeds[slot]),
            action=action_label(int(actions[slot])) if int(arrivals[slot]) > 0 else None,
            arrivals=int(arrivals[slot]),
            deadline_met=int(completed[slot]),
            queue_delay_ms=float(queue_delay[slot]),
        )
        for slot in selected
    ]
    if len(rsu_load) != len(rsu_busy) or len(rsu_load) != len(rsu_xy):
        raise TosPackageError("per-RSU and trace coordinate arrays have incompatible lengths")
    rsus = [
        TosRsuSourceState(
            rsu_reference=f"rsu-index:{rsu_index}",
            rsu_index=rsu_index,
            position_x_source_units=float(rsu_xy[rsu_index][0]),
            position_y_source_units=float(rsu_xy[rsu_index][1]),
            rsu_load_source_value=int(rsu_load[rsu_index]),
            rsu_busy_ms_source_value=float(rsu_busy[rsu_index]),
            rsu_max_concurrent_source_value=summary.rsu_max_concurrent,
        )
        for rsu_index in range(len(rsu_load))
    ]
    return TosReplayFrame(
        run_key=run_key,
        source_file=package_relative(root, stream_path),
        trace_file=package_relative(root, mobility_path),
        point=point,
        vehicles=vehicles,
        rsus=rsus,
        total_active_vehicle_slots=len(active_indices),
        truncated=len(active_indices) > len(selected),
        warnings=[
            "Vehicle slot references are time-local and must not be treated as persistent IDs.",
            "Position and speed values retain source units pending author confirmation.",
            (
                "RSU values are raw source fields; no utilisation, queue, or capacity ratio is "
                "derived."
            ),
        ],
    )


def _point_from_arrays(arrays: dict[str, Any], index: int) -> TosReplayPoint:
    return TosReplayPoint(
        index=index,
        timestamp_s=float(arrays["times"][index]),
        arrivals=int(arrays["arrivals"][index]),
        deadline_met=int(arrays["done"][index]),
        latency_sum_ms=float(arrays["lat_sum"][index]),
        active_vehicle_slots=int(arrays["active"][index]),
        local_decisions=int(arrays["n_local"][index]),
        v2i_decisions=int(arrays["n_v2i"][index]),
        v2v_decisions=int(arrays["n_v2v"][index]),
    )


def _numpy() -> Any:  # noqa: ANN401 - optional NumPy module is loaded dynamically
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise TosPackageError(
            'TOS replay requires the optional dependency: pip install -e ".[tos]"'
        ) from exc
    return np
