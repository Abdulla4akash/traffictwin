"""Bounded inspection of TOS per-arrival showcase arrays."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from traffictwin.domain.enums import TaskClass
from traffictwin.integration.tos.analysis import descriptive_statistics
from traffictwin.integration.tos.analysis_models import (
    TosTaskOutcomeBreakdown,
    TosTaskOutcomeSummary,
)
from traffictwin.integration.tos.models import (
    TosTaskObservation,
    TosTaskSample,
    action_label,
    task_class_from_code,
    task_deadline_ms,
)
from traffictwin.integration.tos.readers import (
    TosPackageError,
    package_relative,
    perstep_path,
    pertask_path,
    read_npz_headers,
)

_TASK_KEYS = ("task_type", "task_lat_ms", "task_met", "task_active")


def load_task_sample(
    root: str | Path,
    run_key: str,
    *,
    limit: int = 100,
    max_source_bytes: int = 100_000_000,
) -> TosTaskSample:
    """Load the first active task entries without treating them as canonical records."""

    if limit < 1 or limit > 10_000:
        raise ValueError("task sample limit must be between 1 and 10000")
    source = pertask_path(root, run_key)
    decision_source = perstep_path(root, run_key)
    if source.stat().st_size > max_source_bytes:
        raise TosPackageError(
            f"per-task source exceeds inspection limit: {source.stat().st_size} bytes"
        )
    np = _numpy()
    try:
        with (
            np.load(source, allow_pickle=False) as archive,
            np.load(decision_source, allow_pickle=False) as stream,
        ):
            missing = sorted(set(_TASK_KEYS) - set(archive.files))
            if missing:
                raise TosPackageError("per-task arrays are missing: " + ", ".join(missing))
            arrays = {key: archive[key] for key in _TASK_KEYS}
            stream_missing = sorted({"times", "veh_action"} - set(stream.files))
            if stream_missing:
                raise TosPackageError(
                    "per-step decision arrays are missing: " + ", ".join(stream_missing)
                )
            times = stream["times"]
            actions = stream["veh_action"]
    except (OSError, ValueError) as exc:
        raise TosPackageError(f"cannot load per-task showcase: {exc}") from exc
    shapes = {tuple(array.shape) for array in arrays.values()}
    if len(shapes) != 1:
        raise TosPackageError("per-task arrays do not share one shape")
    active = arrays["task_active"]
    if actions.ndim != 2 or active.shape[0] != len(times):
        raise TosPackageError("per-task and per-step arrays do not share one timeline")
    if active.shape[0] != actions.shape[0] or active.shape[2] != actions.shape[1]:
        raise TosPackageError("per-task vehicle slots do not align with per-step decisions")
    total = int(active.sum())
    observations: list[TosTaskObservation] = []
    consistency = True
    relative = package_relative(root, source)
    decision_relative = package_relative(root, decision_source)
    for time_index in range(active.shape[0]):
        if len(observations) >= limit:
            break
        coordinates = np.argwhere(active[time_index])
        for task_slot_value, vehicle_slot_value in coordinates:
            task_slot = int(task_slot_value)
            vehicle_slot = int(vehicle_slot_value)
            code = int(arrays["task_type"][time_index, task_slot, vehicle_slot])
            task_class = task_class_from_code(code)
            if task_class is TaskClass.UNKNOWN:
                raise TosPackageError(f"unknown task type code {code} in {relative}")
            latency = float(arrays["task_lat_ms"][time_index, task_slot, vehicle_slot])
            if not math.isfinite(latency) or latency < 0:
                raise TosPackageError("per-task latency must be finite and non-negative")
            met = bool(arrays["task_met"][time_index, task_slot, vehicle_slot])
            decision = action_label(int(actions[time_index, vehicle_slot]))
            if decision is None:
                raise TosPackageError(
                    f"unknown action code {int(actions[time_index, vehicle_slot])} "
                    f"at [{time_index},{vehicle_slot}]"
                )
            deadline = task_deadline_ms(task_class)
            consistency = consistency and met == (latency <= deadline)
            source_index = f"[{time_index},{task_slot},{vehicle_slot}]"
            observations.append(
                TosTaskObservation(
                    task_reference=f"npz://{relative}#task{source_index}",
                    run_key=run_key,
                    time_index=time_index,
                    task_slot=task_slot,
                    vehicle_slot=vehicle_slot,
                    arrival_time_s=float(times[time_index]),
                    task_class=task_class,
                    decision=decision,
                    deadline_met=met,
                    latency_ms=latency,
                    deadline_ms=deadline,
                    source_file=relative,
                    source_index=source_index,
                    decision_source_file=decision_relative,
                    decision_source_index=f"[{time_index},{vehicle_slot}]",
                )
            )
            if len(observations) >= limit:
                break
    return TosTaskSample(
        run_key=run_key,
        source_file=relative,
        observations=observations,
        total_active_entries=total,
        sample_limit=limit,
        truncated=total > len(observations),
        deadline_consistency_verified=consistency,
        warnings=[
            "task_met is displayed as deadline_met and is not mapped to eventual completion.",
            "Vehicle indices are padded source slots, not persistent physical identifiers.",
            "Decisions are joined by the exact time index and time-local vehicle slot.",
            (
                "The bounded sample is for inspection; headline values come from the evaluation "
                "master."
            ),
        ],
    )


def summarise_task_outcomes(
    root: str | Path,
    run_key: str,
    *,
    max_uncompressed_bytes: int = 400_000_000,
) -> TosTaskOutcomeSummary:
    """Aggregate all active showcase tasks while retaining source semantics."""

    source = pertask_path(root, run_key)
    decision_source = perstep_path(root, run_key)
    total_bytes = sum(
        header.uncompressed_bytes
        for header in read_npz_headers(source, max_uncompressed_bytes=max_uncompressed_bytes)
    )
    if total_bytes > max_uncompressed_bytes:
        raise TosPackageError(
            f"per-task arrays exceed summary limit: {total_bytes} > {max_uncompressed_bytes}"
        )
    np = _numpy()
    try:
        with (
            np.load(source, allow_pickle=False) as archive,
            np.load(decision_source, allow_pickle=False) as stream,
        ):
            missing = sorted(set(_TASK_KEYS) - set(archive.files))
            if missing:
                raise TosPackageError("per-task arrays are missing: " + ", ".join(missing))
            active = archive["task_active"].astype(bool, copy=False)
            coordinates = np.nonzero(active)
            task_codes = archive["task_type"][coordinates]
            latencies = archive["task_lat_ms"][coordinates]
            deadline_met = archive["task_met"][coordinates].astype(bool, copy=False)
            actions = stream["veh_action"][coordinates[0], coordinates[2]]
    except (OSError, ValueError, KeyError) as exc:
        if isinstance(exc, TosPackageError):
            raise
        raise TosPackageError(f"cannot summarise per-task showcase: {exc}") from exc
    if active.ndim != 3:
        raise TosPackageError("per-task arrays must use [time, task_slot, vehicle_slot] shape")
    if not bool(np.all(np.isin(task_codes, [0, 1, 2]))):
        raise TosPackageError("per-task source contains an unknown task-type code")
    if not bool(np.all(np.isin(actions, [0, 1, 2]))):
        raise TosPackageError("per-step source contains an unknown action code for an active task")
    if not bool(np.all(np.isfinite(latencies))) or bool(np.any(latencies < 0)):
        raise TosPackageError("active per-task latencies must be finite and non-negative")
    deadlines = np.where(task_codes == 1, 500.0, 100.0)
    consistency = bool(np.all(deadline_met == (latencies <= deadlines)))
    task_count = int(len(latencies))
    success_count = int(deadline_met.sum())

    def breakdown(group: str, mask: Any) -> TosTaskOutcomeBreakdown:  # noqa: ANN401
        group_latencies = latencies[mask]
        count = int(mask.sum())
        met_count = int(deadline_met[mask].sum())
        return TosTaskOutcomeBreakdown(
            group=group,
            task_count=count,
            deadline_success_count=met_count,
            deadline_success_rate=met_count / count if count else None,
            latency_ms=descriptive_statistics([float(value) for value in group_latencies.tolist()]),
        )

    by_class = [
        breakdown(label, task_codes == code) for code, label in ((0, "T1"), (1, "T2"), (2, "T3"))
    ]
    by_decision = [
        breakdown(label, actions == code) for code, label in ((0, "local"), (1, "v2i"), (2, "v2v"))
    ]
    return TosTaskOutcomeSummary(
        run_key=run_key,
        source_file=package_relative(root, source),
        decision_source_file=package_relative(root, decision_source),
        task_count=task_count,
        deadline_success_count=success_count,
        deadline_success_rate=success_count / task_count if task_count else None,
        latency_ms=descriptive_statistics([float(value) for value in latencies.tolist()]),
        by_task_class=by_class,
        by_decision=by_decision,
        deadline_consistency_verified=consistency,
        warnings=[
            "task_met is interpreted as modelled latency within the class deadline.",
            "These arrays represent six showcase runs and are not the full 300-run matrix.",
            "Vehicle indices are time-local padded slots, not persistent vehicle identities.",
        ],
    )


def _numpy() -> Any:  # noqa: ANN401 - optional NumPy module is loaded dynamically
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise TosPackageError(
            'TOS task inspection requires the optional dependency: pip install -e ".[tos]"'
        ) from exc
    return np
