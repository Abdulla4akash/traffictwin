"""Deterministic validation and summaries for native E2 V2I path outputs.

This module is deliberately NumPy-only and runs after evaluator physics.  It
does not participate in task generation, action selection, placement,
admission, queueing, latency, energy, reward, or service-work accounting.

The task identity is ``(time, substep, padded vehicle slot)`` and every path
array has shape ``[T, KMAX, N]``.  RSU indices use ``-1`` as the inactive /
not-applicable sentinel.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np


PATH_DTYPES = {
    "task_ingress_rsu": np.dtype(np.int16),
    "task_selected_execution_rsu": np.dtype(np.int16),
    "task_execution_rsu": np.dtype(np.int16),
    "task_forwarded": np.dtype(np.bool_),
    "task_forwarding_latency_ms": np.dtype(np.float32),
    "task_v2i_admitted": np.dtype(np.bool_),
}


def validate_v2i_path_arrays(
    arrays: Mapping[str, np.ndarray],
    *,
    n_rsus: int,
    rsu_lb: str,
) -> list[str]:
    """Return path-schema/consistency errors; an empty list means pass."""
    errors: list[str] = []
    missing = [name for name in PATH_DTYPES if name not in arrays]
    if missing:
        return [f"missing path arrays: {missing}"]

    ingress = np.asarray(arrays["task_ingress_rsu"])
    shape = ingress.shape
    shape_compatible = True
    if len(shape) != 3:
        errors.append(f"task_ingress_rsu shape {shape} is not [T,KMAX,N]")
        shape_compatible = False

    for name, expected_dtype in PATH_DTYPES.items():
        value = np.asarray(arrays[name])
        if value.shape != shape:
            errors.append(f"{name} shape {value.shape} != {shape}")
            shape_compatible = False
        if value.dtype != expected_dtype:
            errors.append(f"{name} dtype {value.dtype} != {expected_dtype}")

    if not shape_compatible:
        return errors

    selected = np.asarray(arrays["task_selected_execution_rsu"])
    execution = np.asarray(arrays["task_execution_rsu"])
    forwarded = np.asarray(arrays["task_forwarded"])
    forwarding_ms = np.asarray(arrays["task_forwarding_latency_ms"])
    admitted = np.asarray(arrays["task_v2i_admitted"])
    attempt = ingress >= 0

    for name, value in (
        ("task_ingress_rsu", ingress),
        ("task_selected_execution_rsu", selected),
        ("task_execution_rsu", execution),
    ):
        if np.any((value < -1) | (value >= n_rsus)):
            errors.append(f"{name} contains an RSU index outside [-1,{n_rsus})")

    if rsu_lb == "p2c_dla":
        if not np.array_equal(selected >= 0, admitted):
            errors.append("P2C target presence does not equal admission; N0 must select no target")
        if not np.array_equal(selected, execution):
            errors.append("P2C selected target does not equal actual execution")
    elif not np.array_equal(selected >= 0, attempt):
        errors.append("selected-target presence does not equal V2I-attempt presence")
    if np.any(admitted & ~attempt):
        errors.append("task_v2i_admitted is true outside V2I attempts")
    if not np.array_equal(execution >= 0, admitted):
        errors.append("actual-execution presence does not equal V2I admission")
    expected_forwarded = admitted & (execution != ingress)
    if not np.array_equal(forwarded, expected_forwarded):
        errors.append("task_forwarded does not equal admitted AND execution!=ingress")
    if not np.isfinite(forwarding_ms).all():
        errors.append("task_forwarding_latency_ms contains NaN or infinity")
    if np.any(forwarding_ms < 0):
        errors.append("task_forwarding_latency_ms contains negative values")
    if np.any(forwarding_ms[~forwarded] != 0.0):
        errors.append("non-forwarded tasks have nonzero forwarding latency")
    if rsu_lb in ("off", "ingress_dla") and np.any(
        selected[attempt] != ingress[attempt]
    ):
        errors.append(
            f"{rsu_lb} mode selected an execution target different from ingress"
        )

    if "task_active" in arrays:
        task_active = np.asarray(arrays["task_active"])
        if task_active.shape != shape or task_active.dtype != np.bool_:
            errors.append("task_active shape/dtype is incompatible with path arrays")
        elif np.any(attempt & ~task_active):
            errors.append("V2I attempt appears in an inactive task slot")

    if "task_outcome" in arrays:
        outcome = np.asarray(arrays["task_outcome"])
        if outcome.shape != shape:
            errors.append("task_outcome shape is incompatible with path arrays")
        else:
            rejected_or_unavailable_v2i = np.isin(outcome, (3, 4, 7))
            expected_v2i_admitted = attempt & np.isin(outcome, (1, 2))
            if not np.array_equal(admitted, expected_v2i_admitted):
                errors.append(
                    "task_v2i_admitted does not equal V2I attempt with admitted outcome 1 or 2"
                )
            if np.any(execution[rejected_or_unavailable_v2i] != -1):
                errors.append("rejected/unavailable V2I task has an actual execution RSU")
            if np.any(forwarded[rejected_or_unavailable_v2i]):
                errors.append("rejected/unavailable V2I task is marked forwarded")
            if np.any(admitted[rejected_or_unavailable_v2i]):
                errors.append("rejected/unavailable V2I task is marked admitted")

    return errors


def summarise_v2i_paths(
    arrays: Mapping[str, np.ndarray],
    *,
    n_rsus: int,
    rsu_lb: str,
) -> dict:
    """Validate and deterministically aggregate native task-level V2I paths.

    ``execution_share_range`` is the declared imbalance diagnostic:
    ``max(per-RSU execution share) - min(per-RSU execution share)``.  It is
    zero for no admitted V2I tasks and otherwise lies in ``[0, 1]``.
    """
    errors = validate_v2i_path_arrays(arrays, n_rsus=n_rsus, rsu_lb=rsu_lb)
    if errors:
        raise ValueError("; ".join(errors))

    ingress = np.asarray(arrays["task_ingress_rsu"])
    selected = np.asarray(arrays["task_selected_execution_rsu"])
    execution = np.asarray(arrays["task_execution_rsu"])
    forwarded = np.asarray(arrays["task_forwarded"])
    forwarding_ms = np.asarray(arrays["task_forwarding_latency_ms"])
    admitted = np.asarray(arrays["task_v2i_admitted"])
    attempt = ingress >= 0

    ingress_count = np.bincount(ingress[attempt], minlength=n_rsus).astype(np.int64)
    selected_mask = selected >= 0 if rsu_lb == "p2c_dla" else attempt
    selected_count = np.bincount(selected[selected_mask], minlength=n_rsus).astype(np.int64)
    execution_count = np.bincount(execution[admitted], minlength=n_rsus).astype(np.int64)
    admitted_count = int(admitted.sum())
    forwarded_count = int(forwarded.sum())

    pair_matrix = np.zeros((n_rsus, n_rsus), dtype=np.int64)
    np.add.at(pair_matrix, (ingress[admitted], execution[admitted]), 1)

    if admitted_count:
        execution_share = execution_count.astype(np.float64) / admitted_count
        forwarding_share = forwarded_count / admitted_count
        mean_forwarding_per_admitted = float(forwarding_ms[admitted].sum(dtype=np.float64) / admitted_count)
    else:
        execution_share = np.zeros(n_rsus, dtype=np.float64)
        forwarding_share = 0.0
        mean_forwarding_per_admitted = 0.0
    if forwarded_count:
        mean_forwarding_per_forwarded = float(
            forwarding_ms[forwarded].sum(dtype=np.float64) / forwarded_count
        )
    else:
        mean_forwarding_per_forwarded = 0.0

    summary = {
        "schema_version": "e2_native_v2i_path_v1",
        "v2i_attempts": int(attempt.sum()),
        "v2i_admitted_tasks": admitted_count,
        "ingress_count_per_rsu": ingress_count.tolist(),
        "selected_target_count_per_rsu": selected_count.tolist(),
        "actual_execution_count_per_rsu": execution_count.tolist(),
        "forwarded_admitted_task_count": forwarded_count,
        "forwarded_share_of_admitted_v2i": float(forwarding_share),
        "total_forwarding_latency_ms": float(forwarding_ms.sum(dtype=np.float64)),
        "mean_forwarding_latency_ms_per_admitted_v2i": mean_forwarding_per_admitted,
        "mean_forwarding_latency_ms_per_forwarded_v2i": mean_forwarding_per_forwarded,
        "ingress_to_execution_pair_matrix": pair_matrix.tolist(),
        "execution_share_per_rsu": execution_share.tolist(),
        "maximum_execution_share": float(execution_share.max()),
        "imbalance_diagnostic": {
            "name": "execution_share_range",
            "definition": "max(per-RSU execution share) - min(per-RSU execution share)",
            "value": float(execution_share.max() - execution_share.min()),
        },
    }

    if sum(summary["actual_execution_count_per_rsu"]) != admitted_count:
        raise ValueError("per-RSU execution totals do not reconcile with admitted V2I")
    if int(pair_matrix.sum()) != admitted_count:
        raise ValueError("ingress-to-execution matrix does not reconcile with admitted V2I")
    if summary["forwarded_admitted_task_count"] != int(
        (pair_matrix.sum() - np.trace(pair_matrix))
    ):
        raise ValueError("forwarding count does not reconcile with path-pair matrix")
    return summary
