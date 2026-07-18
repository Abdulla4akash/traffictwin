"""Bounded inspection of TOS per-arrival showcase arrays."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from traffictwin.domain.enums import TaskClass
from traffictwin.integration.tos.models import (
    TosTaskObservation,
    TosTaskSample,
    task_class_from_code,
    task_deadline_ms,
)
from traffictwin.integration.tos.readers import (
    TosPackageError,
    package_relative,
    pertask_path,
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
    if source.stat().st_size > max_source_bytes:
        raise TosPackageError(
            f"per-task source exceeds inspection limit: {source.stat().st_size} bytes"
        )
    np = _numpy()
    try:
        with np.load(source, allow_pickle=False) as archive:
            missing = sorted(set(_TASK_KEYS) - set(archive.files))
            if missing:
                raise TosPackageError("per-task arrays are missing: " + ", ".join(missing))
            arrays = {key: archive[key] for key in _TASK_KEYS}
    except (OSError, ValueError) as exc:
        raise TosPackageError(f"cannot load per-task showcase: {exc}") from exc
    shapes = {tuple(array.shape) for array in arrays.values()}
    if len(shapes) != 1:
        raise TosPackageError("per-task arrays do not share one shape")
    active = arrays["task_active"]
    total = int(active.sum())
    observations: list[TosTaskObservation] = []
    consistency = True
    relative = package_relative(root, source)
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
                    task_class=task_class,
                    deadline_met=met,
                    latency_ms=latency,
                    deadline_ms=deadline,
                    source_file=relative,
                    source_index=source_index,
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
            (
                "The bounded sample is for inspection; headline values come from the evaluation "
                "master."
            ),
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
