from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import numpy.typing as npt

from traffictwin.integration.manchester.bbus_successors import (
    CORRIDOR_END_XY_M,
    CORRIDOR_HALF_WIDTH_M,
    CORRIDOR_START_XY_M,
    SPARSE_SITE_COUNT,
    _select_weighted_sites,
    attach_sites,
    build_corridor_trace,
    corridor_membership,
    exact_coverage,
)
from traffictwin.integration.manchester.bus_vec_bridge import (
    OccupancySpan,
    reconcile_spans_with_mask,
)


def _trace(pos_x: np.ndarray, pos_y: np.ndarray, mask: np.ndarray) -> dict[str, object]:
    shape = mask.shape
    return {
        "pos_x": pos_x.astype(np.float32),
        "pos_y": pos_y.astype(np.float32),
        "speed": np.ones(shape, dtype=np.float32),
        "mask": mask,
        "times": np.arange(shape[0], dtype=np.float32),
        "dt": np.float32(1.0),
        "maxN": np.int32(shape[1]),
        "T": np.int32(shape[0]),
        "window": np.asarray("test-window"),
        "sumo_seed": np.int32(42),
    }


def test_protocol_bytes_are_frozen() -> None:
    expected = {
        "docs/evaluation/bbus_corridor_dawn_peak_protocol_20260728.md": (
            "cd2e93f926d19a1c8b55d3962a674353be70b8d4fff0f69d80417e666238cde7"
        ),
        "docs/evaluation/bbus_sparse64_dawn_peak_protocol_20260728.md": (
            "f366f3ba886287150eefcf64268e38df4e2a488372ed738dbbc712573c221efa"
        ),
    }
    for path, digest in expected.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest


def test_corridor_membership_includes_capsule_boundary_and_endpoint_discs() -> None:
    start = np.asarray(CORRIDOR_START_XY_M)
    end = np.asarray(CORRIDOR_END_XY_M)
    direction = end - start
    normal = np.asarray((-direction[1], direction[0])) / np.linalg.norm(direction)
    midpoint = (start + end) / 2
    points = np.stack(
        (
            start,
            end,
            midpoint + normal * CORRIDOR_HALF_WIDTH_M,
            midpoint + normal * (CORRIDOR_HALF_WIDTH_M + 1.0),
        )
    )
    membership = corridor_membership(points[:, 0], points[:, 1])
    assert membership.tolist() == [True, True, True, False]


def test_corridor_filter_splits_runs_compacts_slots_and_reconciles() -> None:
    inside: npt.NDArray[np.float32] = np.asarray(CORRIDOR_START_XY_M, dtype=np.float32)
    outside = inside + np.asarray((2_000.0, 2_000.0), dtype=np.float32)
    pos_x: npt.NDArray[np.float32] = np.zeros((5, 2), dtype=np.float32)
    pos_y: npt.NDArray[np.float32] = np.zeros((5, 2), dtype=np.float32)
    mask: npt.NDArray[np.bool_] = np.zeros((5, 2), dtype=bool)
    for t, point in enumerate((inside, inside, outside, inside, inside)):
        pos_x[t, 0], pos_y[t, 0] = point
        mask[t, 0] = True
    pos_x[2:4, 1] = inside[0]
    pos_y[2:4, 1] = inside[1]
    mask[2:4, 1] = True
    spans = (
        OccupancySpan("token-a", 0, 0, 4),
        OccupancySpan("token-b", 1, 2, 3),
    )

    result = build_corridor_trace(_trace(pos_x, pos_y, mask), spans)

    assert result.source_vehicle_seconds == 7
    assert result.retained_vehicle_seconds == 6
    assert result.excluded_vehicle_seconds == 1
    assert result.retained_occupancy_spans == 3
    assert result.peak_concurrent_vehicles == 2
    reconcile_spans_with_mask(result.spans, result.arrays["mask"])


def test_weighted_sparse_selection_uses_weight_then_lexicographic_tie() -> None:
    weights = {(0, 0): 10, (100, 0): 5, (200, 0): 5}
    selected, gains, covered = _select_weighted_sites(weights, site_count=2)
    assert selected == [(0, 0), (100, 0)]
    assert gains == [10, 5]
    assert covered == {(0, 0), (100, 0)}


def test_site_attachment_preserves_motion_and_exact_coverage_is_counted() -> None:
    x = np.arange(SPARSE_SITE_COUNT, dtype=np.float32)[None, :] * 1_000.0
    y = np.zeros_like(x)
    mask = np.ones_like(x, dtype=bool)
    trace = _trace(x, y, mask)
    sites = np.stack((x[0], y[0]), axis=1).astype(np.float32)

    attached = attach_sites(trace, sites)
    coverage = exact_coverage(trace, sites, chunk_size=7)

    assert np.array_equal(attached["pos_x"], trace["pos_x"])
    assert np.array_equal(attached["rsu_xy"], sites)
    assert coverage.total_vehicle_seconds == SPARSE_SITE_COUNT
    assert coverage.covered_vehicle_seconds == SPARSE_SITE_COUNT
    assert coverage.covered_share == 1.0
