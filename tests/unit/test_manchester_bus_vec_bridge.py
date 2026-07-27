"""B1 bridge: slot assignment, gap handling, reconciliation, and the admission refusal.

Every fixture is a synthetic derivation built in memory. Nothing here reads a
quarantine member, a session artifact, a snapshot, or a trace file, and no part
of VEC-06 is executed — the bridge is construction only, and its tests must not
be able to imply otherwise.
"""

from __future__ import annotations

import numpy as np
import pytest

from traffictwin.integration.manchester.bus_trajectory import (
    BusTraceDerivation,
    BusTraceReport,
    TracePoint,
    VehicleTrack,
)
from traffictwin.integration.manchester.bus_vec_bridge import (
    BRIDGED_TRACE_KEYS,
    OCCUPANCY_HEADER,
    STANDING_BRIDGE_LIMITATIONS,
    UNBRIDGED_TRACE_KEYS,
    VEC06_TRACE_KEYS,
    BusVecBridgeError,
    BusVecBridgeResult,
    BusVecRequestDraft,
    build_vec06_inputs,
    reconcile_spans_with_mask,
)
from traffictwin.integration.vec_preprocessing.models import (
    MAX_VEHICLES_PER_TIMESTEP,
    VecFcdPreprocessRequest,
    VecGreedyUrbanPlacement,
)

SHA_A = "a" * 64
SHA_B = "b" * 64

INPUT_ID = "bus-b1-window"
SCENARIO_DAY = "2026-07-20"
WINDOW_LABEL = "morning-peak"
SUMO_SEED = 7


def _points(start_s: int, count: int, *, x0: float = 0.0) -> tuple[TracePoint, ...]:
    return tuple(
        TracePoint(
            time_s=start_s + offset,
            x_m=x0 + float(offset),
            y_m=x0 * 2.0 + float(offset) * 0.5,
            speed_mps=1.0 + float(offset) * 0.25,
            observed=offset == 0,
        )
        for offset in range(count)
    )


def _track(key: str, *runs: tuple[int, int]) -> VehicleTrack:
    """Build one track from (start_second, length) runs; gaps between them are dropped."""

    points: list[TracePoint] = []
    for index, (start_s, count) in enumerate(runs):
        points.extend(_points(start_s, count, x0=float(index * 100)))
    return VehicleTrack(vehicle_key=key, points=tuple(points))


def _report(trace_label: str = "b1-synthetic") -> BusTraceReport:
    return BusTraceReport(
        trace_label=trace_label,
        gap_ceiling_s=30,
        dwell_radius_m=10.0,
        matched_share_floor=0.8,
        implied_speed_bound_mps=30.0,
        vehicle_count=0,
        included_vehicle_count=0,
        excluded_vehicle_count=0,
        excluded_below_matched_share_count=0,
        segment_count=0,
        interpolated_segment_count=0,
        dwell_segment_count=0,
        dwell_segments_with_supplied_path_count=0,
        dropped_gap_segment_count=0,
        dropped_gap_seconds=0,
        dropped_unmatched_fix_segment_count=0,
        dropped_missing_path_segment_count=0,
        speed_flagged_segment_count=0,
        derived_second_count=0,
        observed_second_count=0,
        interpolated_second_count=0,
    )


def _derivation(*tracks: VehicleTrack, trace_label: str = "b1-synthetic") -> BusTraceDerivation:
    return BusTraceDerivation(report=_report(trace_label), tracks=tuple(tracks))


def _build(
    *tracks: VehicleTrack, placement: VecGreedyUrbanPlacement | None = None
) -> BusVecBridgeResult:
    return build_vec06_inputs(
        _derivation(*tracks),
        input_id=INPUT_ID,
        scenario_day=SCENARIO_DAY,
        window_label=WINDOW_LABEL,
        sumo_seed=SUMO_SEED,
        placement=placement,
    )


# --------------------------------------------------------------------------- #
# Shape: the arrays VEC-06 expects
# --------------------------------------------------------------------------- #


def test_arrays_match_the_accepted_trace_contract() -> None:
    result = _build(_track("token-a", (0, 4)), _track("token-b", (0, 4)))
    arrays = result.arrays

    assert arrays.t_count == 4
    assert arrays.max_n == 2
    assert arrays.pos_x.shape == (4, 2)
    assert arrays.pos_y.shape == (4, 2)
    assert arrays.speed.shape == (4, 2)
    assert arrays.mask.shape == (4, 2)
    assert arrays.times.shape == (4,)
    assert str(arrays.pos_x.dtype) == "float32"
    assert str(arrays.pos_y.dtype) == "float32"
    assert str(arrays.speed.dtype) == "float32"
    assert str(arrays.mask.dtype) == "bool"
    assert str(arrays.times.dtype) == "float32"
    assert np.all(np.diff(arrays.times) == 1.0)


def test_npz_mapping_emits_the_motion_keys_and_omits_placement() -> None:
    result = _build(_track("token-a", (0, 3)))
    mapping = result.arrays.as_npz_mapping()

    assert set(mapping) == set(BRIDGED_TRACE_KEYS)
    assert set(BRIDGED_TRACE_KEYS) | set(UNBRIDGED_TRACE_KEYS) == set(VEC06_TRACE_KEYS)
    assert not set(mapping) & set(UNBRIDGED_TRACE_KEYS)
    assert float(mapping["dt"]) == 1.0
    assert int(mapping["T"]) == 3
    assert int(mapping["maxN"]) == 1


def test_mask_sum_equals_the_derived_second_count() -> None:
    result = _build(_track("token-a", (0, 5)), _track("token-b", (2, 3)))

    assert int(result.arrays.mask.sum()) == 8
    assert result.request_draft.vehicle_observation_count == 8


def test_positions_land_in_the_slot_the_span_names() -> None:
    result = _build(_track("token-a", (0, 2)), _track("token-b", (0, 2)))
    arrays = result.arrays

    for span in result.spans:
        for row in range(span.t_enter, span.t_exit + 1):
            assert arrays.mask[row, span.slot]
    inactive = ~arrays.mask
    assert np.all(arrays.pos_x[inactive] == 0.0)
    assert np.all(arrays.speed[inactive] == 0.0)


# --------------------------------------------------------------------------- #
# Time base
# --------------------------------------------------------------------------- #


def test_times_are_row_offsets_and_the_absolute_start_is_recorded() -> None:
    result = _build(_track("token-a", (600, 3)))

    assert result.arrays.window_start_s == 600
    assert list(result.arrays.times) == [0.0, 1.0, 2.0]
    assert result.request_draft.window_start_s == 600


def test_epoch_scale_timestamps_survive_without_losing_a_second() -> None:
    """float32 cannot hold 1.7e9 to the second; the offset base is why this works."""

    base = 1_784_000_000
    # The hazard, made explicit: at this magnitude float32 cannot tell two
    # consecutive seconds apart, so writing absolute times would fuse them.
    assert np.float32(base) == np.float32(base + 1)
    result = _build(_track("token-a", (base, 4)))
    arrays = result.arrays

    assert arrays.window_start_s == base
    assert list(arrays.times) == [0.0, 1.0, 2.0, 3.0]
    assert result.spans[0].t_enter == 0
    assert result.spans[0].t_exit == 3


def test_spans_are_row_indices_not_absolute_seconds() -> None:
    result = _build(_track("token-a", (1_000, 2)), _track("token-b", (1_002, 2)))

    spans = {span.sumo_vehicle_id: span for span in result.spans}
    assert (spans["token-a"].t_enter, spans["token-a"].t_exit) == (0, 1)
    assert (spans["token-b"].t_enter, spans["token-b"].t_exit) == (2, 3)


# --------------------------------------------------------------------------- #
# Slot assignment: first free slot, in run order
# --------------------------------------------------------------------------- #


def test_concurrent_vehicles_take_distinct_slots() -> None:
    result = _build(
        _track("token-b", (0, 4)),
        _track("token-a", (0, 4)),
        _track("token-c", (0, 4)),
    )

    slots = {span.sumo_vehicle_id: span.slot for span in result.spans}
    assert sorted(slots.values()) == [0, 1, 2]
    assert result.arrays.max_n == 3
    # Ordering is by (t_enter, vehicle_key), not by the caller's track order.
    assert slots["token-a"] == 0
    assert slots["token-b"] == 1
    assert slots["token-c"] == 2


def test_a_freed_slot_is_reused_by_a_later_vehicle() -> None:
    result = _build(_track("token-a", (0, 3)), _track("token-b", (3, 3)))

    slots = {span.sumo_vehicle_id: span.slot for span in result.spans}
    assert slots == {"token-a": 0, "token-b": 0}
    assert result.arrays.max_n == 1
    assert result.arrays.t_count == 6


def test_a_slot_is_not_reused_while_still_occupied() -> None:
    result = _build(_track("token-a", (0, 3)), _track("token-b", (2, 3)))

    slots = {span.sumo_vehicle_id: span.slot for span in result.spans}
    assert slots == {"token-a": 0, "token-b": 1}


def test_slot_assignment_is_deterministic_across_input_orderings() -> None:
    tracks = (
        _track("token-a", (0, 3)),
        _track("token-b", (1, 3)),
        _track("token-c", (5, 2)),
    )
    first = _build(*tracks)
    second = _build(*reversed(tracks))

    assert first.spans == second.spans
    assert np.array_equal(first.arrays.mask, second.arrays.mask)


# --------------------------------------------------------------------------- #
# Gap-dropped vehicles
# --------------------------------------------------------------------------- #


def test_a_gap_dropped_vehicle_yields_one_span_per_run() -> None:
    result = _build(_track("token-a", (0, 2), (10, 2)))

    spans = sorted(result.spans, key=lambda span: span.t_enter)
    assert len(spans) == 2
    assert all(span.sumo_vehicle_id == "token-a" for span in spans)
    assert (spans[0].t_enter, spans[0].t_exit) == (0, 1)
    assert (spans[1].t_enter, spans[1].t_exit) == (10, 11)
    assert result.request_draft.unique_vehicle_count == 1
    assert result.request_draft.occupancy_span_count == 2


def test_the_dropped_gap_seconds_are_inactive_in_the_mask() -> None:
    result = _build(_track("token-a", (0, 2), (10, 2)))
    mask = result.arrays.mask

    assert not mask[2:10, 0].any()
    assert int(mask.sum()) == 4


def test_a_gap_lets_another_vehicle_borrow_the_slot() -> None:
    result = _build(_track("token-a", (0, 2), (10, 2)), _track("token-b", (4, 3)))

    slots = [(span.sumo_vehicle_id, span.slot, span.t_enter) for span in result.spans]
    assert sorted(slots) == [
        ("token-a", 0, 0),
        ("token-a", 0, 10),
        ("token-b", 0, 4),
    ]
    assert result.arrays.max_n == 1


def test_a_vehicle_with_no_derived_points_contributes_nothing() -> None:
    result = _build(_track("token-a", (0, 3)), VehicleTrack(vehicle_key="token-empty", points=()))

    assert {span.sumo_vehicle_id for span in result.spans} == {"token-a"}
    assert result.request_draft.unique_vehicle_count == 1


# --------------------------------------------------------------------------- #
# Mask/span reconciliation
# --------------------------------------------------------------------------- #


def test_spans_reconcile_with_the_mask_exactly() -> None:
    result = _build(
        _track("token-a", (0, 3), (8, 2)),
        _track("token-b", (1, 4)),
        _track("token-c", (6, 5)),
    )

    reconcile_spans_with_mask(result.spans, result.arrays.mask)


def test_reconciliation_rejects_an_active_cell_without_an_identity() -> None:
    result = _build(_track("token-a", (0, 3)), _track("token-b", (0, 3)))
    dropped = tuple(span for span in result.spans if span.sumo_vehicle_id != "token-b")

    with pytest.raises(BusVecBridgeError, match="active cells without an identity"):
        reconcile_spans_with_mask(dropped, result.arrays.mask)


def test_reconciliation_rejects_an_identity_on_an_inactive_cell() -> None:
    result = _build(_track("token-a", (0, 2), (10, 2)))
    stretched = (type(result.spans[0])(sumo_vehicle_id="token-a", slot=0, t_enter=0, t_exit=11),)

    with pytest.raises(BusVecBridgeError, match="identities on inactive cells"):
        reconcile_spans_with_mask(stretched, result.arrays.mask)


def test_reconciliation_rejects_two_spans_claiming_one_slot_second() -> None:
    result = _build(_track("token-a", (0, 3)))
    span = result.spans[0]

    with pytest.raises(BusVecBridgeError, match="more than one span"):
        reconcile_spans_with_mask((span, span), result.arrays.mask)


def test_occupancy_rows_use_the_accepted_header_order() -> None:
    result = _build(_track("token-a", (5, 3)))
    rows = result.occupancy_rows()

    assert OCCUPANCY_HEADER == ("sumo_vehicle_id", "slot", "t_enter", "t_exit")
    assert rows == (("token-a", "0", "0", "2"),)


def test_session_tokens_are_the_vehicle_ids() -> None:
    result = _build(_track("bods-session-9f2c", (0, 2)))

    assert result.spans[0].sumo_vehicle_id == "bods-session-9f2c"


# --------------------------------------------------------------------------- #
# The request draft is never an admission
# --------------------------------------------------------------------------- #


def test_the_draft_carries_the_construction_only_literals() -> None:
    draft = _build(_track("token-a", (0, 3))).request_draft

    assert draft.vec06_admitted is False
    assert draft.derived_scenario is True
    assert draft.observed_fcd is False
    assert draft.buses_only is True
    assert draft.research_status == "owner_approved_candidate"
    assert draft.limitations == STANDING_BRIDGE_LIMITATIONS


def test_the_admission_literal_cannot_be_set_true() -> None:
    result = _build(_track("token-a", (0, 3)))

    assert result.vec06_admitted is False
    with pytest.raises(ValueError, match="vec06_admitted"):
        BusVecRequestDraft(
            vec06_admitted=True,  # type: ignore[arg-type]
            input_id="x",
            scenario_day="2026-07-20",
            window_label="w",
            sumo_seed=0,
            placement=VecGreedyUrbanPlacement(),
            trace_label="t",
            window_start_s=0,
            timestep_count=1,
            peak_concurrent_vehicles=1,
            vehicle_observation_count=1,
            unique_vehicle_count=1,
            occupancy_span_count=1,
            dense_trace_cells=1,
        )


def test_the_draft_records_the_declared_controls_and_derived_counts() -> None:
    draft = _build(_track("token-a", (0, 4)), _track("token-b", (0, 4))).request_draft

    assert draft.input_id == "bus-b1-window"
    assert draft.scenario_day == "2026-07-20"
    assert draft.window_label == "morning-peak"
    assert draft.sumo_seed == 7
    assert draft.trace_label == "b1-synthetic"
    assert draft.timestep_count == 4
    assert draft.peak_concurrent_vehicles == 2
    assert draft.dense_trace_cells == 8


def test_the_draft_composes_the_accepted_request_only_with_caller_digests() -> None:
    draft = _build(_track("token-a", (0, 3))).request_draft

    request = draft.to_preprocess_request(
        fcd_file="derived/bus_fcd.xml",
        fcd_sha256=SHA_A,
        network_file="derived/network.net.xml",
        network_sha256=SHA_B,
    )

    assert isinstance(request, VecFcdPreprocessRequest)
    assert request.capability_id == "VEC-06"
    assert request.input_id == draft.input_id
    assert request.sumo_seed == draft.sumo_seed
    assert request.fcd_sha256 == SHA_A
    assert request.network_sha256 == SHA_B


def test_placement_defaults_to_the_accepted_models_own_default() -> None:
    draft = _build(_track("token-a", (0, 3))).request_draft
    chosen = _build(
        _track("token-a", (0, 3)),
        placement=VecGreedyUrbanPlacement(radius_m=250.0, max_rsus=8),
    ).request_draft

    assert draft.placement == VecGreedyUrbanPlacement()
    assert chosen.placement.radius_m == 250.0
    assert chosen.placement.max_rsus == 8


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #


def test_an_empty_derivation_is_refused_rather_than_yielding_an_empty_trace() -> None:
    with pytest.raises(BusVecBridgeError, match="no derived seconds"):
        _build()
    with pytest.raises(BusVecBridgeError, match="no derived seconds"):
        _build(VehicleTrack(vehicle_key="token-empty", points=()))


def test_duplicate_seconds_for_one_vehicle_are_refused() -> None:
    repeat = TracePoint(time_s=1, x_m=9.0, y_m=9.0, speed_mps=1.0, observed=True)
    duplicated = VehicleTrack(vehicle_key="token-a", points=(*_points(0, 2), repeat))

    with pytest.raises(BusVecBridgeError, match="two derived points at the same second"):
        _build(duplicated)


def test_an_oversized_fleet_is_refused_before_any_array_is_allocated() -> None:
    crowd = [_track(f"token-{index:05d}", (0, 1)) for index in range(MAX_VEHICLES_PER_TIMESTEP + 1)]

    with pytest.raises(BusVecBridgeError, match="concurrent slots"):
        _build(*crowd)
