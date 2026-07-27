"""Unit coverage for the predeclared §3 bus-trace construction rules.

Every fixture here is a handful of synthetic in-memory fixes. Nothing in this
module opens a quarantine member, calls BODS, reads a session artifact, or
touches a real observation.

The parameter values used below — 120 s, 15 m, 0.8, 32 m/s — are **test values
only**. They are the predeclaration's *proposed* G2 defaults, they are owner
decisions until a person signs them, and the library under test holds no default
for any of them.
"""

from __future__ import annotations

import pytest

from traffictwin.integration.manchester.bus_trajectory import (
    BusTraceDerivation,
    BusTrajectoryError,
    MatchedPath,
    VehicleFix,
    VehicleObservation,
    derive_bus_trace,
    iter_fcd_timesteps,
)

TEST_GAP_CEILING_S = 120
TEST_DWELL_RADIUS_M = 15.0
TEST_MATCHED_SHARE_FLOOR = 0.8
TEST_SPEED_BOUND_MPS = 32.0


def _derive(
    observations: list[VehicleObservation],
    **overrides: object,
) -> BusTraceDerivation:
    arguments: dict[str, object] = {
        "trace_label": "synthetic-derivation",
        "gap_ceiling_s": TEST_GAP_CEILING_S,
        "dwell_radius_m": TEST_DWELL_RADIUS_M,
        "matched_share_floor": TEST_MATCHED_SHARE_FLOOR,
        "implied_speed_bound_mps": TEST_SPEED_BOUND_MPS,
    }
    arguments.update(overrides)
    return derive_bus_trace(
        observations,
        trace_label=str(arguments["trace_label"]),
        gap_ceiling_s=arguments["gap_ceiling_s"],  # type: ignore[arg-type]
        dwell_radius_m=arguments["dwell_radius_m"],  # type: ignore[arg-type]
        matched_share_floor=arguments["matched_share_floor"],  # type: ignore[arg-type]
        implied_speed_bound_mps=arguments["implied_speed_bound_mps"],  # type: ignore[arg-type]
    )


def _fix(timestamp_s: int, x_m: float, y_m: float, *, matched: bool = True) -> VehicleFix:
    return VehicleFix(timestamp_s=timestamp_s, x_m=x_m, y_m=y_m, matched=matched)


def _l_path(
    start: tuple[float, float], corner: tuple[float, float], end: tuple[float, float]
) -> MatchedPath:
    """An L-shaped road path: the whole reason interpolation is not a straight line."""

    return MatchedPath(points=(start, corner, end))


def _one_vehicle() -> VehicleObservation:
    """Ten seconds along an L: 60 m east, then 40 m north."""

    return VehicleObservation(
        vehicle_key="bus-a",
        fixes=(_fix(0, 0.0, 0.0), _fix(10, 60.0, 40.0)),
        paths=(_l_path((0.0, 0.0), (60.0, 0.0), (60.0, 40.0)),),
    )


def test_interpolation_follows_the_matched_path_and_never_a_straight_line() -> None:
    derivation = _derive([_one_vehicle()])

    (track,) = derivation.tracks
    assert [point.time_s for point in track.points] == list(range(11))
    # 100 m of path over 10 s: at t=5 the vehicle is 50 m along, still on the
    # eastward leg. A straight line from (0, 0) to (60, 40) would put it at
    # (30, 20) instead — through whatever stands between the two fixes.
    midpoint = track.points[5]
    assert (midpoint.x_m, midpoint.y_m) == pytest.approx((50.0, 0.0))
    assert midpoint.observed is False
    # At t=8 it has turned the corner: 80 m along is 20 m up the northward leg.
    assert (track.points[8].x_m, track.points[8].y_m) == pytest.approx((60.0, 20.0))
    assert all(point.speed_mps == pytest.approx(10.0) for point in track.points)


def test_observed_seconds_carry_their_own_fix_and_are_counted_separately() -> None:
    derivation = _derive([_one_vehicle()])

    (track,) = derivation.tracks
    observed = [point for point in track.points if point.observed]
    assert [point.time_s for point in observed] == [0, 10]
    assert (observed[0].x_m, observed[0].y_m) == (0.0, 0.0)
    assert (observed[1].x_m, observed[1].y_m) == (60.0, 40.0)

    (record,) = derivation.report.vehicles
    assert record.derived_second_count == 11
    assert record.observed_second_count == 2
    assert record.interpolated_second_count == 9
    assert record.interpolated_share == pytest.approx(9 / 11)
    assert derivation.report.interpolated_share == pytest.approx(9 / 11)


def test_gap_ceiling_drops_the_segment_and_counts_it_rather_than_inventing_it() -> None:
    observation = VehicleObservation(
        vehicle_key="bus-gap",
        fixes=(_fix(0, 0.0, 0.0), _fix(10, 60.0, 40.0), _fix(400, 160.0, 40.0)),
        paths=(
            _l_path((0.0, 0.0), (60.0, 0.0), (60.0, 40.0)),
            MatchedPath(points=((60.0, 40.0), (160.0, 40.0))),
        ),
    )

    derivation = _derive([observation])

    (track,) = derivation.tracks
    assert [point.time_s for point in track.points] == list(range(11))
    (record,) = derivation.report.vehicles
    assert record.dropped_gap_segment_count == 1
    assert record.dropped_gap_seconds == 390
    assert record.interpolated_segment_count == 1
    assert derivation.report.dropped_gap_seconds == 390


def test_the_gap_ceiling_is_applied_before_dwell_so_stale_fixes_are_not_dwell() -> None:
    """A vehicle repeating an identical fix hours later is stale, not parked.

    The probe recorded one vehicle resuming after 3.2 hours. Testing dwell first
    would read the identical repeated fix as a stationary bus and fabricate
    hours of occupancy; the ceiling drops it, exactly as §5 states.
    """

    stale = VehicleObservation(
        vehicle_key="bus-stale",
        fixes=(_fix(0, 100.0, 100.0), _fix(11_520, 100.0, 100.0)),
        paths=(None,),
    )

    derivation = _derive([stale])

    assert derivation.tracks == ()
    (record,) = derivation.report.vehicles
    assert record.dropped_gap_segment_count == 1
    assert record.dwell_segment_count == 0
    assert record.included is False
    assert record.exclusion_reason == "no_retained_segment"


def test_dwell_holds_the_matched_location_at_zero_speed() -> None:
    observation = VehicleObservation(
        vehicle_key="bus-dwell",
        fixes=(_fix(0, 200.0, 300.0), _fix(30, 205.0, 300.0)),
        paths=(None,),
    )

    derivation = _derive([observation])

    (track,) = derivation.tracks
    assert len(track.points) == 31
    held = track.points[15]
    assert (held.x_m, held.y_m) == (200.0, 300.0)
    assert held.speed_mps == 0.0
    assert held.observed is False
    (record,) = derivation.report.vehicles
    assert record.dwell_segment_count == 1
    assert record.interpolated_segment_count == 0


def test_a_dwell_segment_that_carried_a_path_is_counted_not_hidden() -> None:
    """§3 defines dwell by displacement, so a short loop reads as a dwell.

    The library follows the predeclaration rather than second-guessing it, and
    publishes how often that happened so the case is visible.
    """

    looping = VehicleObservation(
        vehicle_key="bus-loop",
        fixes=(_fix(0, 0.0, 0.0), _fix(60, 10.0, 0.0)),
        paths=(_l_path((0.0, 0.0), (0.0, 400.0), (10.0, 0.0)),),
    )

    derivation = _derive([looping])

    (record,) = derivation.report.vehicles
    assert record.dwell_segment_count == 1
    assert record.dwell_segments_with_supplied_path_count == 1
    assert derivation.report.dwell_segments_with_supplied_path_count == 1


def test_a_segment_without_a_matched_path_is_dropped_never_straight_lined() -> None:
    observation = VehicleObservation(
        vehicle_key="bus-unpathed",
        fixes=(_fix(0, 0.0, 0.0), _fix(20, 400.0, 0.0)),
        paths=(None,),
    )

    derivation = _derive([observation])

    assert derivation.tracks == ()
    (record,) = derivation.report.vehicles
    assert record.dropped_missing_path_segment_count == 1
    assert record.derived_second_count == 0


def test_a_path_that_does_not_join_its_two_fixes_is_refused() -> None:
    observation = VehicleObservation(
        vehicle_key="bus-disconnected",
        fixes=(_fix(0, 0.0, 0.0), _fix(20, 400.0, 0.0)),
        paths=(MatchedPath(points=((5.0, 5.0), (400.0, 0.0))),),
    )

    with pytest.raises(BusTrajectoryError, match="does not run from"):
        _derive([observation])


def test_a_segment_touching_an_unmatched_fix_is_dropped_and_counted() -> None:
    observation = VehicleObservation(
        vehicle_key="bus-unmatched-mid",
        fixes=(
            _fix(0, 0.0, 0.0),
            _fix(10, 60.0, 40.0, matched=False),
            _fix(20, 160.0, 40.0),
            _fix(30, 260.0, 40.0),
            _fix(40, 360.0, 40.0),
            _fix(50, 460.0, 40.0),
        ),
        paths=(
            _l_path((0.0, 0.0), (60.0, 0.0), (60.0, 40.0)),
            MatchedPath(points=((60.0, 40.0), (160.0, 40.0))),
            MatchedPath(points=((160.0, 40.0), (260.0, 40.0))),
            MatchedPath(points=((260.0, 40.0), (360.0, 40.0))),
            MatchedPath(points=((360.0, 40.0), (460.0, 40.0))),
        ),
    )

    derivation = _derive([observation])

    (record,) = derivation.report.vehicles
    assert record.matched_fix_count == 5
    assert record.matched_share == pytest.approx(5 / 6)
    assert record.dropped_unmatched_fix_segment_count == 2
    assert record.interpolated_segment_count == 3
    (track,) = derivation.tracks
    # The two segments around the unmatched fix leave no positions at all;
    # the surviving run starts again at the next matched fix.
    assert [point.time_s for point in track.points] == list(range(20, 51))


def test_a_vehicle_below_the_matched_share_floor_is_excluded_with_its_count() -> None:
    observation = VehicleObservation(
        vehicle_key="bus-poorly-matched",
        fixes=(
            _fix(0, 0.0, 0.0),
            _fix(10, 100.0, 0.0, matched=False),
            _fix(20, 200.0, 0.0, matched=False),
            _fix(30, 300.0, 0.0),
        ),
        paths=(
            MatchedPath(points=((0.0, 0.0), (100.0, 0.0))),
            MatchedPath(points=((100.0, 0.0), (200.0, 0.0))),
            MatchedPath(points=((200.0, 0.0), (300.0, 0.0))),
        ),
    )

    derivation = _derive([observation])

    assert derivation.tracks == ()
    (record,) = derivation.report.vehicles
    assert record.matched_share == pytest.approx(0.5)
    assert record.included is False
    assert record.exclusion_reason == "matched_share_below_floor"
    # No segment was classified for an excluded vehicle, so its counters are
    # zero because no work happened rather than because nothing was found.
    assert record.segment_count == 0
    assert derivation.report.excluded_below_matched_share_count == 1
    assert derivation.report.included_vehicle_count == 0


def test_a_vehicle_with_one_fix_yields_nothing_and_says_why() -> None:
    observation = VehicleObservation(vehicle_key="bus-single", fixes=(_fix(0, 0.0, 0.0),), paths=())

    derivation = _derive([observation])

    (record,) = derivation.report.vehicles
    assert record.exclusion_reason == "fewer_than_two_fixes"
    assert record.matched_share == pytest.approx(1.0)


def test_the_speed_screen_flags_and_never_drops() -> None:
    """§5 screens implied speeds; the segment stays in the trace, flagged."""

    speeding = VehicleObservation(
        vehicle_key="bus-fast",
        fixes=(_fix(0, 0.0, 0.0), _fix(10, 500.0, 0.0)),
        paths=(MatchedPath(points=((0.0, 0.0), (500.0, 0.0))),),
    )

    derivation = _derive([speeding])

    (record,) = derivation.report.vehicles
    assert record.speed_flagged_segment_count == 1
    assert record.max_implied_speed_mps == pytest.approx(50.0)
    assert record.derived_second_count == 11
    assert record.interpolated_segment_count == 1
    assert derivation.report.speed_flagged_segment_count == 1
    assert derivation.report.max_implied_speed_mps == pytest.approx(50.0)


def test_a_legitimate_high_speed_below_the_bound_is_not_flagged() -> None:
    """The night probe measured 28.4 m/s, which the bound must not reject."""

    coach = VehicleObservation(
        vehicle_key="bus-coach",
        fixes=(_fix(0, 0.0, 0.0), _fix(10, 284.0, 0.0)),
        paths=(MatchedPath(points=((0.0, 0.0), (284.0, 0.0))),),
    )

    derivation = _derive([coach])

    (record,) = derivation.report.vehicles
    assert record.speed_flagged_segment_count == 0
    assert record.max_implied_speed_mps == pytest.approx(28.4)


def test_labels_are_type_level_and_cannot_be_set_to_a_forbidden_value() -> None:
    report = _derive([_one_vehicle()]).report

    assert report.derived_scenario is True
    assert report.observed_fcd is False
    assert report.buses_only is True
    assert report.research_status == "owner_approved_candidate"
    payload = report.model_dump(mode="json")
    assert payload["observed_fcd"] is False
    assert payload["buses_only"] is True


def test_the_declared_parameters_are_recorded_with_the_trace_they_produced() -> None:
    report = _derive([_one_vehicle()]).report

    assert report.gap_ceiling_s == TEST_GAP_CEILING_S
    assert report.dwell_radius_m == pytest.approx(TEST_DWELL_RADIUS_M)
    assert report.matched_share_floor == pytest.approx(TEST_MATCHED_SHARE_FLOOR)
    assert report.implied_speed_bound_mps == pytest.approx(TEST_SPEED_BOUND_MPS)
    assert report.fingerprint() == _derive([_one_vehicle()]).report.fingerprint()


def test_the_library_holds_no_default_for_any_owner_decision() -> None:
    """G2 is a person's decision; omitting a parameter must fail, not default."""

    with pytest.raises(TypeError):
        derive_bus_trace([_one_vehicle()], trace_label="no-parameters")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"gap_ceiling_s": 0}, "gap ceiling must be positive"),
        ({"gap_ceiling_s": 120.0}, "whole number of seconds"),
        ({"dwell_radius_m": -1.0}, "dwell radius"),
        ({"matched_share_floor": 1.5}, "matched-share floor"),
        ({"implied_speed_bound_mps": 0.0}, "implied-speed bound"),
    ],
)
def test_impossible_parameters_are_refused(override: dict[str, object], message: str) -> None:
    with pytest.raises(BusTrajectoryError, match=message):
        _derive([_one_vehicle()], **override)


def test_non_monotone_timestamps_are_refused_as_the_viability_check_requires() -> None:
    observation = VehicleObservation(
        vehicle_key="bus-backwards",
        fixes=(_fix(30, 0.0, 0.0), _fix(10, 100.0, 0.0)),
        paths=(MatchedPath(points=((0.0, 0.0), (100.0, 0.0))),),
    )

    with pytest.raises(BusTrajectoryError, match="non-increasing"):
        _derive([observation])


def test_a_vehicle_supplied_twice_is_refused() -> None:
    with pytest.raises(BusTrajectoryError, match="supplied twice"):
        _derive([_one_vehicle(), _one_vehicle()])


def test_path_and_fix_sequences_cannot_drift_apart() -> None:
    with pytest.raises(BusTrajectoryError, match="matched paths"):
        VehicleObservation(
            vehicle_key="bus-mismatched",
            fixes=(_fix(0, 0.0, 0.0), _fix(10, 100.0, 0.0)),
            paths=(),
        )


def test_a_degenerate_matched_path_is_refused() -> None:
    with pytest.raises(BusTrajectoryError, match="at least two points"):
        MatchedPath(points=((0.0, 0.0),))


def test_a_non_finite_fix_is_refused() -> None:
    with pytest.raises(BusTrajectoryError, match="finite"):
        VehicleFix(timestamp_s=0, x_m=float("nan"), y_m=0.0, matched=True)


def test_the_fcd_view_is_contiguous_one_second_timesteps() -> None:
    """VEC-06 requires exact one-second steps, so a dropped gap is an empty step."""

    gapped = VehicleObservation(
        vehicle_key="bus-a",
        fixes=(_fix(0, 0.0, 0.0), _fix(3, 30.0, 0.0), _fix(200, 60.0, 0.0), _fix(203, 90.0, 0.0)),
        paths=(
            MatchedPath(points=((0.0, 0.0), (30.0, 0.0))),
            MatchedPath(points=((30.0, 0.0), (60.0, 0.0))),
            MatchedPath(points=((60.0, 0.0), (90.0, 0.0))),
        ),
    )
    other = VehicleObservation(
        vehicle_key="bus-b",
        fixes=(_fix(1, 0.0, 500.0), _fix(3, 20.0, 500.0)),
        paths=(MatchedPath(points=((0.0, 500.0), (20.0, 500.0))),),
    )

    derivation = _derive([gapped, other])
    timesteps = list(iter_fcd_timesteps(derivation))

    assert [step.time_s for step in timesteps] == list(range(0, 204))
    # bus-b has not appeared yet at t=0, and rows are ordered by vehicle key.
    assert [row.vehicle_key for row in timesteps[0].vehicles] == ["bus-a"]
    assert [row.vehicle_key for row in timesteps[2].vehicles] == ["bus-a", "bus-b"]
    # The 197-second gap the ceiling dropped leaves genuinely empty timesteps.
    assert timesteps[100].vehicles == ()
    assert [row.vehicle_key for row in timesteps[201].vehicles] == ["bus-a"]


def test_an_empty_derivation_produces_no_timesteps_and_no_window() -> None:
    derivation = _derive([])

    assert list(iter_fcd_timesteps(derivation)) == []
    assert derivation.report.window_start_s is None
    assert derivation.report.window_end_s is None
    assert derivation.report.interpolated_share is None
    assert derivation.report.vehicle_count == 0


def test_the_fleet_window_spans_every_included_vehicle() -> None:
    first = VehicleObservation(
        vehicle_key="bus-early",
        fixes=(_fix(0, 0.0, 0.0), _fix(10, 100.0, 0.0)),
        paths=(MatchedPath(points=((0.0, 0.0), (100.0, 0.0))),),
    )
    second = VehicleObservation(
        vehicle_key="bus-late",
        fixes=(_fix(50, 0.0, 900.0), _fix(80, 100.0, 900.0)),
        paths=(MatchedPath(points=((0.0, 900.0), (100.0, 900.0))),),
    )

    report = _derive([first, second]).report

    assert report.window_start_s == 0
    assert report.window_end_s == 80
    assert report.included_vehicle_count == 2
    assert report.derived_second_count == 11 + 31
