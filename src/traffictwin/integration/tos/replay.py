"""Logical historical replay over documented TOS per-step and trace arrays."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from traffictwin.integration.tos.analysis_models import (
    TosDescriptiveStatistics,
    TosRsuRunSummary,
    TosRsuSourceSummary,
    TosTraceProfilePoint,
    TosTraceSummary,
)
from traffictwin.integration.tos.models import (
    TosReplayFrame,
    TosReplayPoint,
    TosRsuReplayPoint,
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

_RSU_SERIES_KEYS = ("times", "rsu_load", "rsu_busy_ms")


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
            load_pressure_fraction=_load_pressure(
                int(rsu_load[rsu_index]), summary.rsu_max_concurrent
            ),
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
            "Trace positions use network metres and speeds use metres per second.",
            (
                "RSU concurrency pressure is active in-flight tasks divided by the recorded "
                "maximum concurrent tasks; it is not CPU utilisation."
            ),
        ],
    )


def load_rsu_replay_series(
    root: str | Path,
    run_key: str,
    *,
    stride: int = 1,
) -> list[TosRsuReplayPoint]:
    """Load interpreted RSU source values without promoting them to Phase 3 metrics."""

    if stride < 1:
        raise ValueError("stride must be at least 1")
    np = _numpy()
    source = perstep_path(root, run_key)
    summary = read_summary_for_key(root, run_key)
    try:
        with np.load(source, allow_pickle=False) as archive:
            missing = sorted(set(_RSU_SERIES_KEYS) - set(archive.files))
            if missing:
                raise TosPackageError("per-step RSU arrays are missing: " + ", ".join(missing))
            times = archive["times"]
            loads = archive["rsu_load"]
            busy = archive["rsu_busy_ms"]
    except (OSError, ValueError) as exc:
        if isinstance(exc, TosPackageError):
            raise
        raise TosPackageError(f"cannot load per-step RSU replay: {exc}") from exc
    if loads.ndim != 2 or busy.ndim != 2:
        raise TosPackageError("per-step RSU arrays must have [time, rsu] shape")
    if loads.shape != busy.shape or loads.shape[0] != len(times):
        raise TosPackageError("per-step RSU arrays do not share one timeline and RSU shape")
    relative = package_relative(root, source)
    points: list[TosRsuReplayPoint] = []
    for index in range(0, len(times), stride):
        for rsu_index in range(loads.shape[1]):
            active = int(loads[index, rsu_index])
            points.append(
                TosRsuReplayPoint(
                    index=index,
                    timestamp_s=float(times[index]),
                    rsu_reference=f"rsu-index:{rsu_index}",
                    rsu_index=rsu_index,
                    active_task_count=active,
                    remaining_compute_backlog_ms=float(busy[index, rsu_index]),
                    max_concurrent_tasks=summary.rsu_max_concurrent,
                    concurrency_pressure_fraction=_load_pressure(
                        active, summary.rsu_max_concurrent
                    ),
                    source_file=relative,
                )
            )
    return points


def summarise_trace(
    root: str | Path,
    trace_name: str,
    *,
    max_profile_points: int = 600,
) -> TosTraceSummary:
    """Summarise one processed FCD trace without claiming persistent vehicle identity."""

    if max_profile_points < 2 or max_profile_points > 5000:
        raise ValueError("max_profile_points must be between 2 and 5000")
    np = _numpy()
    source = trace_path(root, trace_name)
    try:
        with np.load(source, allow_pickle=False) as trace:
            required = {"times", "mask", "pos_x", "pos_y", "speed"}
            missing = sorted(required - set(trace.files))
            if missing:
                raise TosPackageError("trace arrays are missing: " + ", ".join(missing))
            times = trace["times"]
            mask = trace["mask"].astype(bool, copy=False)
            positions_x = trace["pos_x"]
            positions_y = trace["pos_y"]
            speeds = trace["speed"]
    except (OSError, ValueError) as exc:
        if isinstance(exc, TosPackageError):
            raise
        raise TosPackageError(f"cannot load processed FCD trace: {exc}") from exc
    if len(times) == 0:
        raise TosPackageError("processed FCD trace has no timeline points")
    if (
        mask.shape != positions_x.shape
        or mask.shape != positions_y.shape
        or mask.shape != speeds.shape
    ):
        raise TosPackageError("processed FCD arrays do not share one [time, slot] shape")
    if mask.shape[0] != len(times):
        raise TosPackageError("processed FCD arrays do not match the trace timeline")
    active_counts = mask.sum(axis=1)
    active_speeds = speeds[mask]
    active_x = positions_x[mask]
    active_y = positions_y[mask]
    indices = _sample_indices(len(times), max_profile_points)
    profile: list[TosTraceProfilePoint] = []
    for index in indices:
        point_speeds = speeds[index][mask[index]]
        profile.append(
            TosTraceProfilePoint(
                index=index,
                timestamp_s=float(times[index]),
                active_vehicle_slots=int(active_counts[index]),
                mean_speed_mps=(float(np.mean(point_speeds)) if len(point_speeds) else None),
                p50_speed_mps=(float(np.median(point_speeds)) if len(point_speeds) else None),
            )
        )
    return TosTraceSummary(
        trace_file=package_relative(root, source),
        observation_count=int(mask.sum()),
        timeline_point_count=len(times),
        first_timestamp_s=float(times[0]),
        last_timestamp_s=float(times[-1]),
        duration_s=max(0.0, float(times[-1]) - float(times[0])),
        active_vehicle_slots=_array_statistics(active_counts, np),
        speed_mps=_array_statistics(active_speeds, np),
        minimum_x_m=float(np.min(active_x)) if len(active_x) else None,
        maximum_x_m=float(np.max(active_x)) if len(active_x) else None,
        minimum_y_m=float(np.min(active_y)) if len(active_y) else None,
        maximum_y_m=float(np.max(active_y)) if len(active_y) else None,
        profile=profile,
        warnings=[
            "The trace is processed SUMO FCD simulation, not a live Manchester feed.",
            "Vehicle slots are recycled and are not persistent vehicle identifiers.",
            "This is a mobility-state profile, not a trip or journey-time output.",
        ],
    )


def summarise_rsu_run(root: str | Path, run_key: str) -> TosRsuRunSummary:
    """Summarise evidenced RSU source states without calling pressure utilisation."""

    np = _numpy()
    source = perstep_path(root, run_key)
    summary = read_summary_for_key(root, run_key)
    try:
        with np.load(source, allow_pickle=False) as archive:
            times = archive["times"]
            loads = archive["rsu_load"]
            backlog = archive["rsu_busy_ms"]
    except (OSError, ValueError, KeyError) as exc:
        raise TosPackageError(f"cannot load RSU source-state summary: {exc}") from exc
    if loads.ndim != 2 or loads.shape != backlog.shape or loads.shape[0] != len(times):
        raise TosPackageError("RSU source arrays do not share one [time, rsu] shape")
    pressure = loads / summary.rsu_max_concurrent
    if bool(np.any(pressure > 1)) or bool(np.any(pressure < 0)):
        raise TosPackageError("RSU concurrency pressure falls outside [0, 1]")
    rsus = [
        TosRsuSourceSummary(
            rsu_reference=f"rsu-index:{index}",
            observation_count=len(times),
            active_task_count=_array_statistics(loads[:, index], np),
            concurrency_pressure_fraction=_array_statistics(pressure[:, index], np),
            remaining_compute_backlog_ms=_array_statistics(backlog[:, index], np),
            peak_pressure_timestamp_s=float(times[int(np.argmax(pressure[:, index]))]),
            peak_backlog_timestamp_s=float(times[int(np.argmax(backlog[:, index]))]),
        )
        for index in range(loads.shape[1])
    ]
    return TosRsuRunSummary(
        run_key=run_key,
        source_file=package_relative(root, source),
        maximum_concurrent_tasks=summary.rsu_max_concurrent,
        rsus=rsus,
        warnings=[
            "Concurrency pressure is in-flight tasks divided by maximum concurrent tasks.",
            "Remaining compute backlog is a source-model quantity in milliseconds.",
            "Neither source field is promoted to canonical CPU utilisation.",
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


def _load_pressure(active_tasks: int, maximum: int) -> float:
    if maximum <= 0:
        raise TosPackageError("RSU maximum-concurrent value must be positive")
    pressure = active_tasks / maximum
    if pressure > 1:
        raise TosPackageError(
            "RSU in-flight task count exceeds the recorded maximum-concurrent value"
        )
    return pressure


def _array_statistics(values: Any, np: Any) -> TosDescriptiveStatistics:  # noqa: ANN401
    size = int(values.size)
    if size == 0:
        return TosDescriptiveStatistics(n=0)
    return TosDescriptiveStatistics(
        n=size,
        mean=float(np.mean(values)),
        sample_sd=float(np.std(values, ddof=1)) if size > 1 else None,
        minimum=float(np.min(values)),
        maximum=float(np.max(values)),
        p50=float(np.percentile(values, 50, method="linear")),
    )


def _sample_indices(length: int, limit: int) -> list[int]:
    if length <= limit:
        return list(range(length))
    return sorted({round(index * (length - 1) / (limit - 1)) for index in range(limit)})


def _numpy() -> Any:  # noqa: ANN401 - optional NumPy module is loaded dynamically
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise TosPackageError(
            'TOS replay requires the optional dependency: pip install -e ".[tos]"'
        ) from exc
    return np
