"""Deterministic transformations for the two approved B-BUS successors.

This module consumes only the already-derived dense bus motion arrays. It does
not acquire, parse, match, route or interpolate BODS observations. Corridor
scope and sparse-site selection are deliberately separate methods because the
former requires full coverage while the latter explicitly permits uncovered
vehicle-seconds and is outside VEC-06.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from traffictwin.integration.manchester.bus_vec_bridge import (
    OccupancySpan,
    reconcile_spans_with_mask,
)

METHOD_VERSION = "bbus-dual-successor-1.0"

CORRIDOR_START_XY_M = (383_863.597181, 397_936.133916)
CORRIDOR_END_XY_M = (384_569.687684, 396_698.832727)
CORRIDOR_HALF_WIDTH_M = 750.0

PLACEMENT_CELL_M = 50.0
PLACEMENT_RADIUS_M = 500.0
SPARSE_SITE_COUNT = 64
MAX_OCCUPIED_CELLS = 2_000

REQUIRED_TRACE_KEYS = frozenset(
    {"pos_x", "pos_y", "speed", "mask", "times", "dt", "maxN", "T", "window", "sumo_seed"}
)


class BBusSuccessorError(ValueError):
    """Raised when a successor cannot be built without changing its protocol."""


@dataclass(frozen=True, slots=True)
class CorridorTraceResult:
    """One compact in-corridor trace plus exact source accounting."""

    arrays: dict[str, Any]
    spans: tuple[OccupancySpan, ...]
    source_vehicle_seconds: int
    retained_vehicle_seconds: int
    excluded_vehicle_seconds: int
    source_occupancy_spans: int
    retained_occupancy_spans: int
    retained_session_tokens: int
    peak_concurrent_vehicles: int
    occupied_cells: int


@dataclass(frozen=True, slots=True)
class SparsePlacementResult:
    """Dawn-selected sites and selection accounting."""

    rsu_xy: npt.NDArray[np.float32]
    occupied_cells: int
    total_vehicle_seconds: int
    safely_covered_cells: int
    safely_covered_vehicle_seconds: int
    iteration_gains: tuple[int, ...]
    remaining_uncovered_cells: int


@dataclass(frozen=True, slots=True)
class ExactCoverage:
    """Exact point-to-site coverage at the declared physical radius."""

    total_vehicle_seconds: int
    covered_vehicle_seconds: int
    uncovered_vehicle_seconds: int
    covered_share: float


@dataclass(frozen=True, slots=True)
class _FilteredRun:
    token: str
    source_slot: int
    t_enter: int
    t_exit: int


def corridor_membership(
    pos_x: npt.NDArray[np.floating[Any]],
    pos_y: npt.NDArray[np.floating[Any]],
) -> npt.NDArray[np.bool_]:
    """Return membership in the frozen 750 m projected landmark-line capsule."""

    if pos_x.shape != pos_y.shape:
        raise BBusSuccessorError("corridor coordinate arrays have different shapes")
    x = np.asarray(pos_x, dtype=np.float64)
    y = np.asarray(pos_y, dtype=np.float64)
    start: npt.NDArray[np.float64] = np.asarray(CORRIDOR_START_XY_M, dtype=np.float64)
    end: npt.NDArray[np.float64] = np.asarray(CORRIDOR_END_XY_M, dtype=np.float64)
    direction = end - start
    denominator = float(direction @ direction)
    if denominator <= 0:
        raise BBusSuccessorError("the frozen corridor endpoints are degenerate")
    projection = ((x - start[0]) * direction[0] + (y - start[1]) * direction[1]) / denominator
    projection = np.clip(projection, 0.0, 1.0)
    closest_x = start[0] + projection * direction[0]
    closest_y = start[1] + projection * direction[1]
    distance_squared = (x - closest_x) ** 2 + (y - closest_y) ** 2
    # One micrometre-squared tolerance keeps the mathematically closed boundary
    # closed after the projected double-precision dot products above.
    return np.asarray(distance_squared <= CORRIDOR_HALF_WIDTH_M**2 + 1e-6, dtype=bool)


def build_corridor_trace(
    trace: dict[str, Any], spans: tuple[OccupancySpan, ...]
) -> CorridorTraceResult:
    """Filter one parent trace to the frozen capsule and compact its slots."""

    pos_x, pos_y, speed, source_mask = _validate_trace(trace)
    reconcile_spans_with_mask(spans, source_mask)
    retained_source_mask = source_mask & corridor_membership(pos_x, pos_y)
    source_vehicle_seconds = int(np.count_nonzero(source_mask))
    retained_vehicle_seconds = int(np.count_nonzero(retained_source_mask))
    if retained_vehicle_seconds == 0:
        raise BBusSuccessorError("the frozen corridor retained no active vehicle-second")

    runs = _filtered_runs(spans, retained_source_mask)
    assignments = _assign_slots(runs)
    max_n = 1 + max(slot for _, slot in assignments)
    shape = (source_mask.shape[0], max_n)
    out_x = np.zeros(shape, dtype=np.float32)
    out_y = np.zeros(shape, dtype=np.float32)
    out_speed = np.zeros(shape, dtype=np.float32)
    out_mask = np.zeros(shape, dtype=bool)
    out_spans: list[OccupancySpan] = []
    for run, target_slot in assignments:
        window = slice(run.t_enter, run.t_exit + 1)
        out_x[window, target_slot] = pos_x[window, run.source_slot]
        out_y[window, target_slot] = pos_y[window, run.source_slot]
        out_speed[window, target_slot] = speed[window, run.source_slot]
        out_mask[window, target_slot] = True
        out_spans.append(
            OccupancySpan(
                sumo_vehicle_id=run.token,
                slot=target_slot,
                t_enter=run.t_enter,
                t_exit=run.t_exit,
            )
        )
    reconciled = tuple(out_spans)
    reconcile_spans_with_mask(reconciled, out_mask)
    if int(np.count_nonzero(out_mask)) != retained_vehicle_seconds:
        raise BBusSuccessorError("corridor compaction changed the retained vehicle-second count")

    arrays = {
        "pos_x": out_x,
        "pos_y": out_y,
        "speed": out_speed,
        "mask": out_mask,
        "times": np.asarray(trace["times"], dtype=np.float32).copy(),
        "dt": np.float32(np.asarray(trace["dt"]).item()),
        "maxN": np.int32(max_n),
        "T": np.int32(source_mask.shape[0]),
        "window": np.asarray(trace["window"]).copy(),
        "sumo_seed": np.int32(np.asarray(trace["sumo_seed"]).item()),
    }
    return CorridorTraceResult(
        arrays=arrays,
        spans=reconciled,
        source_vehicle_seconds=source_vehicle_seconds,
        retained_vehicle_seconds=retained_vehicle_seconds,
        excluded_vehicle_seconds=source_vehicle_seconds - retained_vehicle_seconds,
        source_occupancy_spans=len(spans),
        retained_occupancy_spans=len(reconciled),
        retained_session_tokens=len({span.sumo_vehicle_id for span in reconciled}),
        peak_concurrent_vehicles=max_n,
        occupied_cells=count_occupied_cells(arrays),
    )


def select_sparse64_sites(dawn_trace: dict[str, Any]) -> SparsePlacementResult:
    """Select exactly 64 weighted sites from dawn, with deterministic ties."""

    pos_x, pos_y, _, mask = _validate_trace(dawn_trace)
    points = np.stack((pos_x[mask], pos_y[mask]), axis=1)
    cells, weights = np.unique(
        np.floor(points / PLACEMENT_CELL_M).astype(np.int64),
        axis=0,
        return_counts=True,
    )
    if len(cells) < SPARSE_SITE_COUNT:
        raise BBusSuccessorError(
            f"dawn has only {len(cells)} candidate cells; exactly {SPARSE_SITE_COUNT} are required"
        )
    cell_weights = {
        (int(cell[0]), int(cell[1])): int(weight)
        for cell, weight in zip(cells, weights, strict=True)
    }
    selected, gains, safely_covered = _select_weighted_sites(
        cell_weights, site_count=SPARSE_SITE_COUNT
    )
    if len(selected) != SPARSE_SITE_COUNT or any(gain <= 0 for gain in gains):
        raise BBusSuccessorError("sparse placement did not produce 64 distinct positive-gain sites")
    rsu_xy = ((np.asarray(selected, dtype=np.float64) + np.float64(0.5)) * PLACEMENT_CELL_M).astype(
        np.float32
    )
    return SparsePlacementResult(
        rsu_xy=rsu_xy,
        occupied_cells=len(cell_weights),
        total_vehicle_seconds=int(weights.sum()),
        safely_covered_cells=len(safely_covered),
        safely_covered_vehicle_seconds=sum(cell_weights[cell] for cell in safely_covered),
        iteration_gains=tuple(gains),
        remaining_uncovered_cells=len(cell_weights) - len(safely_covered),
    )


def attach_sites(trace: dict[str, Any], rsu_xy: npt.NDArray[np.float32]) -> dict[str, Any]:
    """Return the unchanged trace fields plus a validated site array."""

    _validate_trace(trace)
    sites = np.asarray(rsu_xy, dtype=np.float32)
    if sites.shape != (SPARSE_SITE_COUNT, 2) or not np.isfinite(sites).all():
        raise BBusSuccessorError("the sparse site array must be finite with shape (64, 2)")
    attached = {key: np.asarray(value).copy() for key, value in trace.items() if key != "rsu_xy"}
    attached["rsu_xy"] = sites.copy()
    return attached


def exact_coverage(
    trace: dict[str, Any],
    rsu_xy: npt.NDArray[np.floating[Any]],
    *,
    chunk_size: int = 100_000,
) -> ExactCoverage:
    """Measure exact 500 m point coverage without allocating a K-by-64 matrix."""

    pos_x, pos_y, _, mask = _validate_trace(trace)
    sites = np.asarray(rsu_xy, dtype=np.float64)
    if sites.ndim != 2 or sites.shape[1:] != (2,) or len(sites) == 0:
        raise BBusSuccessorError("coverage requires at least one two-dimensional site")
    if chunk_size < 1:
        raise BBusSuccessorError("coverage chunk size must be positive")
    points = np.stack((pos_x[mask], pos_y[mask]), axis=1).astype(np.float64, copy=False)
    covered = 0
    radius_squared = PLACEMENT_RADIUS_M**2
    for start in range(0, len(points), chunk_size):
        chunk = points[start : start + chunk_size]
        distance_squared = ((chunk[:, None, :] - sites[None, :, :]) ** 2).sum(axis=2)
        covered += int(np.count_nonzero(np.min(distance_squared, axis=1) <= radius_squared))
    total = len(points)
    return ExactCoverage(
        total_vehicle_seconds=total,
        covered_vehicle_seconds=covered,
        uncovered_vehicle_seconds=total - covered,
        covered_share=covered / total,
    )


def count_occupied_cells(trace: dict[str, Any]) -> int:
    """Count distinct active 50 m cells."""

    pos_x, pos_y, _, mask = _validate_trace(trace)
    points = np.stack((pos_x[mask], pos_y[mask]), axis=1)
    return len(np.unique(np.floor(points / PLACEMENT_CELL_M).astype(np.int64), axis=0))


def _validate_trace(
    trace: dict[str, Any],
) -> tuple[
    npt.NDArray[np.float32],
    npt.NDArray[np.float32],
    npt.NDArray[np.float32],
    npt.NDArray[np.bool_],
]:
    missing = REQUIRED_TRACE_KEYS - trace.keys()
    if missing:
        raise BBusSuccessorError(f"trace is missing required keys: {sorted(missing)}")
    pos_x = np.asarray(trace["pos_x"], dtype=np.float32)
    pos_y = np.asarray(trace["pos_y"], dtype=np.float32)
    speed = np.asarray(trace["speed"], dtype=np.float32)
    mask = np.asarray(trace["mask"], dtype=bool)
    if pos_x.ndim != 2 or pos_x.shape != pos_y.shape or pos_x.shape != speed.shape:
        raise BBusSuccessorError("motion arrays must be equally shaped two-dimensional arrays")
    if mask.shape != pos_x.shape:
        raise BBusSuccessorError("the active mask does not match the motion arrays")
    if int(np.asarray(trace["T"]).item()) != pos_x.shape[0]:
        raise BBusSuccessorError("T does not match the trace row count")
    if int(np.asarray(trace["maxN"]).item()) != pos_x.shape[1]:
        raise BBusSuccessorError("maxN does not match the trace column count")
    if not mask.any():
        raise BBusSuccessorError("trace has no active vehicle-second")
    if not (
        np.isfinite(pos_x[mask]).all()
        and np.isfinite(pos_y[mask]).all()
        and np.isfinite(speed[mask]).all()
    ):
        raise BBusSuccessorError("active trace values must be finite")
    return pos_x, pos_y, speed, mask


def _filtered_runs(
    spans: tuple[OccupancySpan, ...], retained_mask: npt.NDArray[np.bool_]
) -> tuple[_FilteredRun, ...]:
    runs: list[_FilteredRun] = []
    for span in spans:
        active = retained_mask[span.t_enter : span.t_exit + 1, span.slot]
        indices: npt.NDArray[np.int64] = np.flatnonzero(active) + span.t_enter
        if len(indices) == 0:
            continue
        start = previous = int(indices[0])
        for value in indices[1:]:
            current = int(value)
            if current == previous + 1:
                previous = current
                continue
            runs.append(_FilteredRun(span.sumo_vehicle_id, span.slot, start, previous))
            start = previous = current
        runs.append(_FilteredRun(span.sumo_vehicle_id, span.slot, start, previous))
    return tuple(runs)


def _assign_slots(
    runs: tuple[_FilteredRun, ...],
) -> tuple[tuple[_FilteredRun, int], ...]:
    ordered = sorted(
        runs,
        key=lambda run: (run.t_enter, run.token, run.source_slot, run.t_exit),
    )
    occupied_until: list[int] = []
    assignments: list[tuple[_FilteredRun, int]] = []
    for run in ordered:
        slot = next(
            (index for index, until in enumerate(occupied_until) if until < run.t_enter),
            None,
        )
        if slot is None:
            slot = len(occupied_until)
            occupied_until.append(run.t_exit)
        else:
            occupied_until[slot] = run.t_exit
        assignments.append((run, slot))
    return tuple(assignments)


def _coverage_offsets() -> tuple[tuple[int, int], ...]:
    effective_radius = PLACEMENT_RADIUS_M - PLACEMENT_CELL_M * math.sqrt(2.0) / 2.0
    extent = math.ceil(effective_radius / PLACEMENT_CELL_M)
    offsets = [
        (dx, dy)
        for dx in range(-extent, extent + 1)
        for dy in range(-extent, extent + 1)
        if (dx * PLACEMENT_CELL_M) ** 2 + (dy * PLACEMENT_CELL_M) ** 2 <= effective_radius**2
    ]
    return tuple(sorted(offsets))


def _select_weighted_sites(
    cell_weights: dict[tuple[int, int], int], *, site_count: int
) -> tuple[list[tuple[int, int]], list[int], set[tuple[int, int]]]:
    if site_count < 1 or len(cell_weights) < site_count:
        raise BBusSuccessorError("site selection has fewer candidates than required sites")
    if any(weight <= 0 for weight in cell_weights.values()):
        raise BBusSuccessorError("occupied-cell weights must be positive")
    offsets = _coverage_offsets()
    gains = {
        candidate: sum(
            cell_weights.get((candidate[0] + dx, candidate[1] + dy), 0) for dx, dy in offsets
        )
        for candidate in cell_weights
    }
    available = set(cell_weights)
    covered: set[tuple[int, int]] = set()
    selected: list[tuple[int, int]] = []
    iteration_gains: list[int] = []
    for _ in range(site_count):
        best_gain = max(gains[candidate] for candidate in available)
        best = min(candidate for candidate in available if gains[candidate] == best_gain)
        if best_gain <= 0:
            raise BBusSuccessorError("site selection reached a zero-gain candidate")
        selected.append(best)
        iteration_gains.append(best_gain)
        available.remove(best)
        newly_covered = {
            (best[0] + dx, best[1] + dy)
            for dx, dy in offsets
            if (best[0] + dx, best[1] + dy) in cell_weights
        } - covered
        for cell in newly_covered:
            weight = cell_weights[cell]
            for dx, dy in offsets:
                candidate = (cell[0] + dx, cell[1] + dy)
                if candidate in gains:
                    gains[candidate] -= weight
        covered.update(newly_covered)
    return selected, iteration_gains, covered
