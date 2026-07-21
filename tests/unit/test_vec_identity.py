"""Synthetic tests for occupancy-bounded vehicle identity (VEC-03)."""

from __future__ import annotations

import numpy as np
import pytest

from tests.tos_v2_helpers import (
    V2_SCENARIO,
    build_v2_occupancy_rows,
    build_v2_trace,
)
from traffictwin.integration.vec_identity import (
    VecIdentityError,
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
    iter_vehicle_mobility,
    resolve_vehicle_identity,
    vec_identity_contract,
)


def _snapshot() -> VecIdentitySnapshot:
    header, rows = build_v2_occupancy_rows()
    return build_vehicle_identity_snapshot(build_v2_trace(), header, rows, scenario=V2_SCENARIO)


def test_contract_and_complete_identity_coverage_are_deterministic() -> None:
    first = _snapshot()
    second = _snapshot()

    assert first.report.status == "accepted"
    assert first.report.active_trace_cells == 12
    assert first.report.identity_cells == 12
    assert first.report.missing_identity_cells == 0
    assert first.report.inactive_identity_cells == 0
    assert first.report.interval_semantics == "inclusive"
    assert first.fingerprint() == second.fingerprint()
    assert vec_identity_contract().fingerprint() == vec_identity_contract().fingerprint()


def test_identity_is_bounded_and_slot_reuse_changes_vehicle() -> None:
    snapshot = _snapshot()

    assert resolve_vehicle_identity(snapshot, time_index=2, slot=0) == "veh_synthetic_a"
    assert resolve_vehicle_identity(snapshot, time_index=3, slot=0) == "veh_synthetic_c"
    assert resolve_vehicle_identity(snapshot, time_index=5, slot=2) is None
    with pytest.raises(VecIdentityError, match="outside the trace"):
        resolve_vehicle_identity(snapshot, time_index=6, slot=0)


def test_requested_mobility_rows_use_exact_identity_and_units() -> None:
    rows = list(
        iter_vehicle_mobility(
            build_v2_trace(),
            _snapshot(),
            cells=[(2, 0), (3, 0), (5, 1)],
        )
    )

    assert [row.sumo_vehicle_id for row in rows] == [
        "veh_synthetic_a",
        "veh_synthetic_c",
        "veh_synthetic_b",
    ]
    assert [row.trace_time_s for row in rows] == [102.0, 103.0, 105.0]
    assert all(row.identity_semantics == "occupancy_bounded_inclusive" for row in rows)


def test_full_mobility_stream_has_one_row_per_identity_cell() -> None:
    rows = list(iter_vehicle_mobility(build_v2_trace(), _snapshot()))

    assert len(rows) == 12
    assert {row.sumo_vehicle_id for row in rows} == {
        "veh_synthetic_a",
        "veh_synthetic_b",
        "veh_synthetic_c",
    }


def test_inactive_or_uncovered_mobility_cell_is_refused() -> None:
    with pytest.raises(VecIdentityError, match="not inside an active occupancy span"):
        list(iter_vehicle_mobility(build_v2_trace(), _snapshot(), cells=[(0, 2)]))


def test_trace_binding_rejects_even_a_valid_but_different_trace() -> None:
    changed = build_v2_trace()
    changed["pos_x"] = np.asarray(changed["pos_x"]).copy()
    changed["pos_x"][0, 0] += np.float32(1.0)

    with pytest.raises(VecIdentityError, match="fingerprint"):
        list(iter_vehicle_mobility(changed, _snapshot(), cells=[(0, 0)]))


@pytest.mark.parametrize(
    "rows",
    [
        [
            ["veh_synthetic_a", "0", "0", "1"],
            ["veh_synthetic_b", "1", "0", "5"],
            ["veh_synthetic_c", "0", "3", "5"],
        ],
        [
            ["veh_synthetic_a", "0", "0", "3"],
            ["veh_synthetic_b", "1", "0", "5"],
            ["veh_synthetic_c", "0", "3", "5"],
        ],
    ],
)
def test_gap_and_overlap_cannot_create_a_partial_snapshot(rows: list[list[str]]) -> None:
    header, _ = build_v2_occupancy_rows()
    with pytest.raises(VecIdentityError):
        build_vehicle_identity_snapshot(build_v2_trace(), header, rows, scenario=V2_SCENARIO)


def test_same_count_but_wrong_cells_are_rejected() -> None:
    header, rows = build_v2_occupancy_rows()
    rows[0][1] = "2"

    with pytest.raises(VecIdentityError, match="identity coverage rejected"):
        build_vehicle_identity_snapshot(build_v2_trace(), header, rows, scenario=V2_SCENARIO)


def test_invalid_upstream_trace_fails_closed() -> None:
    trace = build_v2_trace()
    del trace["mask"]
    header, rows = build_v2_occupancy_rows()
    with pytest.raises(VecIdentityError, match="upstream trace is invalid"):
        build_vehicle_identity_snapshot(trace, header, rows, scenario=V2_SCENARIO)
