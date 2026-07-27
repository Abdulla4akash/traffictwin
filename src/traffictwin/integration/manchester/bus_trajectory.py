"""Trace construction for the predeclared real-bus-fleet experiment (B1 §3).

`docs/evaluation/bus_fleet_experiment_predeclaration_draft.md` §3 fixes, before
any trajectory has been derived, exactly how observed bus position fixes become
a one-second trace: path-following interpolation, a gap ceiling that drops
rather than invents, dwell handling, a matched-share floor, an implied-speed
screen, and VEC-06's one-second resolution. §5 adds the viability checks —
monotone per-vehicle timestamps and a published interpolated-versus-observed
share per vehicle.

This module is that construction layer, built ahead of signing so the B1
execution step is ready. **It runs on no real data.** Nothing here opens a
quarantine member, calls BODS, reads or writes a session artifact, or touches a
snapshot; the caller hands in already-extracted, already-matched fixes and the
matched road paths between them.

**The parameters are owner decision G2 and have no defaults here.** Gap ceiling,
dwell radius, matched-share floor, and implied-speed bound are required keyword
arguments. A default would be this module quietly making a decision the
predeclaration reserves for a person, so there is not one anywhere in the file —
not in a signature, not in a constant, not in a model field.

**Labels.** Every artifact carries ``derived_scenario`` ``True``, ``observed_fcd``
``False``, and ``buses_only`` ``True`` as type-level literals. Only the fleet
*motion* is observation-derived; the trace is never observed FCD, and buses are
never general traffic.

**What this module deliberately does not do.** §3's trace-window rule (the
longest contiguous span carrying at least N linked vehicles) is not implemented:
its threshold is a further ``FILL-AT-SIGNING`` value, and the window is chosen
over a derivation's output rather than inside it.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Literal

from pydantic import Field

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

BUS_TRAJECTORY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
BUS_TRAJECTORY_METHOD_VERSION: Literal["manchester-bus-trajectory-1.0"] = (
    "manchester-bus-trajectory-1.0"
)

#: Why a vehicle contributed no seconds to the derived trace.
VehicleExclusionReason = Literal[
    "fewer_than_two_fixes",
    "matched_share_below_floor",
    "no_retained_segment",
]

#: What the derivation did with one fix-to-fix segment.
SegmentOutcome = Literal[
    "interpolated",
    "dwell",
    "dropped_gap_ceiling",
    "dropped_unmatched_fix",
    "dropped_missing_path",
]


class BusTrajectoryError(ValueError):
    """Raised when observations or parameters cannot be derived as supplied."""


@dataclass(frozen=True)
class VehicleFix:
    """One observed position fix for one session-scoped vehicle.

    ``x_m``/``y_m`` are the fix's **map-matched** planar location in the
    network's own coordinate frame, so a matched path between two fixes starts
    and ends exactly on them. ``matched`` records whether the matcher accepted
    the fix at all; an unmatched fix has no usable location and the segments
    touching it are dropped rather than guessed.

    ``timestamp_s`` is a whole second because §3's resolution rule is
    one-second positions; a sub-second fix would need a rounding convention this
    module refuses to invent.
    """

    timestamp_s: int
    x_m: float
    y_m: float
    matched: bool

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp_s, int) or isinstance(self.timestamp_s, bool):
            raise BusTrajectoryError("fix timestamp must be a whole number of seconds")
        if not (isfinite(self.x_m) and isfinite(self.y_m)):
            raise BusTrajectoryError("fix coordinates must be finite")


@dataclass(frozen=True)
class MatchedPath:
    """The map-matched road path a vehicle travelled between two fixes.

    The points are an ordered planar polyline in the network's coordinate
    frame, running from the earlier fix's matched location to the later one's.
    The derivation progresses along this polyline, which is the whole point of
    §3's rule: a straight line between fixes runs through buildings, and this
    module has no straight-line fallback for a segment whose path is missing.
    """

    points: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise BusTrajectoryError("a matched path needs at least two points")
        for point in self.points:
            if len(point) != 2:
                raise BusTrajectoryError("a matched path point must be an (x, y) pair")
            if not (isfinite(point[0]) and isfinite(point[1])):
                raise BusTrajectoryError("matched path coordinates must be finite")

    @property
    def cumulative_lengths_m(self) -> tuple[float, ...]:
        """Return the distance along the path at each of its points."""

        cumulative = [0.0]
        for start, end in zip(self.points, self.points[1:], strict=False):
            cumulative.append(cumulative[-1] + hypot(end[0] - start[0], end[1] - start[1]))
        return tuple(cumulative)

    @property
    def length_m(self) -> float:
        """Return the total travelled length of the path."""

        return self.cumulative_lengths_m[-1]

    def position_at(self, distance_m: float) -> tuple[float, float]:
        """Return the planar position ``distance_m`` along the path."""

        return _position_along(self.points, self.cumulative_lengths_m, distance_m)


@dataclass(frozen=True)
class VehicleObservation:
    """One vehicle's ordered fixes plus the matched path spanning each gap.

    ``paths`` is positional: ``paths[i]`` is the road path from ``fixes[i]`` to
    ``fixes[i + 1]``, and ``None`` means the matcher produced none. There is one
    entry per fix-to-fix segment, so the two sequences cannot drift apart.

    ``vehicle_key`` is whatever session-scoped key the caller derived — this
    module never sees, stores, or emits a raw vehicle reference.
    """

    vehicle_key: str
    fixes: tuple[VehicleFix, ...]
    paths: tuple[MatchedPath | None, ...]

    def __post_init__(self) -> None:
        if not self.vehicle_key:
            raise BusTrajectoryError("vehicle key must not be empty")
        expected = max(len(self.fixes) - 1, 0)
        if len(self.paths) != expected:
            raise BusTrajectoryError(
                f"vehicle {self.vehicle_key} supplies {len(self.paths)} matched paths "
                f"for {len(self.fixes)} fixes; {expected} are required"
            )


@dataclass(frozen=True, slots=True)
class TracePoint:
    """One derived one-second position for one vehicle.

    ``observed`` separates the seconds that coincide with a real fix from the
    seconds this module constructed, which is exactly the
    interpolated-versus-observed share §5 requires be published.
    """

    time_s: int
    x_m: float
    y_m: float
    speed_mps: float
    observed: bool


@dataclass(frozen=True)
class VehicleTrack:
    """One vehicle's derived one-second positions, in time order."""

    vehicle_key: str
    points: tuple[TracePoint, ...]


@dataclass(frozen=True)
class FcdVehicleRow:
    """One vehicle's row inside one VEC-06 timestep."""

    vehicle_key: str
    x_m: float
    y_m: float
    speed_mps: float


@dataclass(frozen=True)
class FcdTimestep:
    """One VEC-06 timestep: an exact second and the vehicles present in it."""

    time_s: int
    vehicles: tuple[FcdVehicleRow, ...]


class VehicleTraceAccounting(ManchesterSnapshotModel):
    """Per-vehicle accounting for one derivation.

    Every segment a vehicle contributed is accounted for exactly once across the
    retained and dropped counters, so a reader can reconstruct what happened to
    the vehicle's observations without re-running the derivation.
    """

    schema_version: Literal["1.0"] = BUS_TRAJECTORY_SCHEMA_VERSION
    vehicle_key: str

    fix_count: int = Field(ge=0)
    matched_fix_count: int = Field(ge=0)
    matched_share: float | None = Field(default=None, ge=0, le=1)

    included: bool
    exclusion_reason: VehicleExclusionReason | None = None

    segment_count: int = Field(ge=0)
    interpolated_segment_count: int = Field(ge=0)
    dwell_segment_count: int = Field(ge=0)
    dwell_segments_with_supplied_path_count: int = Field(ge=0)
    dropped_gap_segment_count: int = Field(ge=0)
    dropped_gap_seconds: int = Field(ge=0)
    dropped_unmatched_fix_segment_count: int = Field(ge=0)
    dropped_missing_path_segment_count: int = Field(ge=0)

    speed_flagged_segment_count: int = Field(ge=0)
    max_implied_speed_mps: float | None = Field(default=None, ge=0)

    derived_second_count: int = Field(ge=0)
    observed_second_count: int = Field(ge=0)
    interpolated_second_count: int = Field(ge=0)
    interpolated_share: float | None = Field(default=None, ge=0, le=1)

    window_start_s: int | None = None
    window_end_s: int | None = None


class BusTraceReport(ManchesterSnapshotModel):
    """The publishable record of one derivation.

    It carries the declared parameters, the fleet-level totals, and the
    per-vehicle accounting — not the positions themselves, which live in the
    returned tracks so a full-fleet derivation is not held twice.
    """

    schema_version: Literal["1.0"] = BUS_TRAJECTORY_SCHEMA_VERSION
    method_version: Literal["manchester-bus-trajectory-1.0"] = BUS_TRAJECTORY_METHOD_VERSION
    trace_label: str

    # Composition labels, fixed by §2 before construction.
    derived_scenario: Literal[True] = True
    observed_fcd: Literal[False] = False
    buses_only: Literal[True] = True
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"

    # The declared G2/§5 parameters, recorded with the trace they produced.
    gap_ceiling_s: int = Field(gt=0)
    dwell_radius_m: float = Field(ge=0)
    matched_share_floor: float = Field(ge=0, le=1)
    implied_speed_bound_mps: float = Field(gt=0)

    vehicle_count: int = Field(ge=0)
    included_vehicle_count: int = Field(ge=0)
    excluded_vehicle_count: int = Field(ge=0)
    excluded_below_matched_share_count: int = Field(ge=0)

    segment_count: int = Field(ge=0)
    interpolated_segment_count: int = Field(ge=0)
    dwell_segment_count: int = Field(ge=0)
    dwell_segments_with_supplied_path_count: int = Field(ge=0)
    dropped_gap_segment_count: int = Field(ge=0)
    dropped_gap_seconds: int = Field(ge=0)
    dropped_unmatched_fix_segment_count: int = Field(ge=0)
    dropped_missing_path_segment_count: int = Field(ge=0)

    speed_flagged_segment_count: int = Field(ge=0)
    max_implied_speed_mps: float | None = Field(default=None, ge=0)

    derived_second_count: int = Field(ge=0)
    observed_second_count: int = Field(ge=0)
    interpolated_second_count: int = Field(ge=0)
    interpolated_share: float | None = Field(default=None, ge=0, le=1)

    window_start_s: int | None = None
    window_end_s: int | None = None

    vehicles: tuple[VehicleTraceAccounting, ...] = ()


@dataclass(frozen=True)
class BusTraceDerivation:
    """A derivation's publishable report beside the tracks it describes."""

    report: BusTraceReport
    tracks: tuple[VehicleTrack, ...]


@dataclass(frozen=True)
class _SegmentResult:
    """What one fix-to-fix segment produced, before resampling."""

    outcome: SegmentOutcome
    start_s: int
    end_s: int
    implied_speed_mps: float | None
    speed_flagged: bool
    path: MatchedPath | None
    dwell_path_supplied: bool


def derive_bus_trace(
    observations: Iterable[VehicleObservation],
    *,
    trace_label: str,
    gap_ceiling_s: int,
    dwell_radius_m: float,
    matched_share_floor: float,
    implied_speed_bound_mps: float,
) -> BusTraceDerivation:
    """Derive the one-second trace from observed fixes under the §3 rules.

    The four parameters are owner decision G2 and are required: this module
    holds no default for any of them.

    Segments are classified in a fixed order, and the order is load-bearing:

    1. **Gap ceiling first.** A segment whose fixes are more than
       ``gap_ceiling_s`` apart is dropped and counted. The probe measured stale
       vehicles repeating identical fixes hours apart — one resumed after 3.2
       hours — so testing dwell first would turn staleness into hours of
       fabricated stationary occupancy.
    2. **Unmatched fixes.** A segment touching a fix the matcher rejected has no
       usable location and is dropped and counted.
    3. **Dwell.** Fixes no further apart than ``dwell_radius_m`` are §3 dwell:
       the vehicle is stationary at the entry fix's matched location. The rule
       is a displacement rule, exactly as predeclared, so a vehicle that loops
       back within the radius is recorded as dwelling; the count of dwell
       segments that nonetheless carried a matched path is published so that
       case is visible rather than hidden.
    4. **Path following.** Anything else needs the caller's matched path and
       progresses along it at constant rate. A segment with no path is dropped
       and counted; there is no straight-line fallback.

    The implied-speed screen **flags and never drops** — a segment over
    ``implied_speed_bound_mps`` is kept, counted, and reported with its measured
    value, so a person sees what the screen caught instead of a silently thinned
    trace.
    """

    _validate_parameters(
        gap_ceiling_s=gap_ceiling_s,
        dwell_radius_m=dwell_radius_m,
        matched_share_floor=matched_share_floor,
        implied_speed_bound_mps=implied_speed_bound_mps,
    )
    if not trace_label:
        raise BusTrajectoryError("trace label must not be empty")

    accounting: list[VehicleTraceAccounting] = []
    tracks: list[VehicleTrack] = []
    seen_keys: set[str] = set()

    for observation in observations:
        if observation.vehicle_key in seen_keys:
            raise BusTrajectoryError(f"vehicle {observation.vehicle_key} is supplied twice")
        seen_keys.add(observation.vehicle_key)
        _require_monotone(observation)
        record, track = _derive_vehicle(
            observation,
            gap_ceiling_s=gap_ceiling_s,
            dwell_radius_m=dwell_radius_m,
            matched_share_floor=matched_share_floor,
            implied_speed_bound_mps=implied_speed_bound_mps,
        )
        accounting.append(record)
        if track is not None:
            tracks.append(track)

    return BusTraceDerivation(
        report=_build_report(
            trace_label=trace_label,
            gap_ceiling_s=gap_ceiling_s,
            dwell_radius_m=dwell_radius_m,
            matched_share_floor=matched_share_floor,
            implied_speed_bound_mps=implied_speed_bound_mps,
            accounting=tuple(accounting),
        ),
        tracks=tuple(tracks),
    )


def iter_fcd_timesteps(derivation: BusTraceDerivation) -> Iterator[FcdTimestep]:
    """Yield the derivation as VEC-06's one-second timestep sequence.

    VEC-06 requires finite, strictly increasing, **exact one-second** timesteps,
    so every second between the first and last derived second is emitted — a
    second in which the gap ceiling left no vehicle is an empty timestep, never
    a missing one and never a filled-in position.
    """

    report = derivation.report
    if report.window_start_s is None or report.window_end_s is None:
        return
    by_second: dict[int, list[FcdVehicleRow]] = {}
    for track in derivation.tracks:
        for point in track.points:
            by_second.setdefault(point.time_s, []).append(
                FcdVehicleRow(
                    vehicle_key=track.vehicle_key,
                    x_m=point.x_m,
                    y_m=point.y_m,
                    speed_mps=point.speed_mps,
                )
            )
    for second in range(report.window_start_s, report.window_end_s + 1):
        rows = sorted(by_second.get(second, ()), key=lambda row: row.vehicle_key)
        yield FcdTimestep(time_s=second, vehicles=tuple(rows))


def _validate_parameters(
    *,
    gap_ceiling_s: int,
    dwell_radius_m: float,
    matched_share_floor: float,
    implied_speed_bound_mps: float,
) -> None:
    if not isinstance(gap_ceiling_s, int) or isinstance(gap_ceiling_s, bool):
        raise BusTrajectoryError("gap ceiling must be a whole number of seconds")
    if gap_ceiling_s <= 0:
        raise BusTrajectoryError("gap ceiling must be positive")
    if not isfinite(dwell_radius_m) or dwell_radius_m < 0:
        raise BusTrajectoryError("dwell radius must be finite and non-negative")
    if not isfinite(matched_share_floor) or not 0.0 <= matched_share_floor <= 1.0:
        raise BusTrajectoryError("matched-share floor must lie between 0 and 1")
    if not isfinite(implied_speed_bound_mps) or implied_speed_bound_mps <= 0:
        raise BusTrajectoryError("implied-speed bound must be finite and positive")


def _require_monotone(observation: VehicleObservation) -> None:
    """Refuse non-monotone fixes — a §5 viability check, not a repair."""

    for earlier, later in zip(observation.fixes, observation.fixes[1:], strict=False):
        if later.timestamp_s <= earlier.timestamp_s:
            raise BusTrajectoryError(
                f"vehicle {observation.vehicle_key} has non-increasing fix timestamps at "
                f"{earlier.timestamp_s} -> {later.timestamp_s}"
            )


def _derive_vehicle(
    observation: VehicleObservation,
    *,
    gap_ceiling_s: int,
    dwell_radius_m: float,
    matched_share_floor: float,
    implied_speed_bound_mps: float,
) -> tuple[VehicleTraceAccounting, VehicleTrack | None]:
    fix_count = len(observation.fixes)
    matched_fix_count = sum(1 for fix in observation.fixes if fix.matched)
    matched_share = matched_fix_count / fix_count if fix_count else None

    if fix_count < 2:
        return (
            _empty_accounting(
                observation.vehicle_key,
                fix_count=fix_count,
                matched_fix_count=matched_fix_count,
                matched_share=matched_share,
                reason="fewer_than_two_fixes",
            ),
            None,
        )
    if matched_share is None or matched_share < matched_share_floor:
        return (
            _empty_accounting(
                observation.vehicle_key,
                fix_count=fix_count,
                matched_fix_count=matched_fix_count,
                matched_share=matched_share,
                reason="matched_share_below_floor",
            ),
            None,
        )

    segments = [
        _classify_segment(
            observation,
            index,
            gap_ceiling_s=gap_ceiling_s,
            dwell_radius_m=dwell_radius_m,
            implied_speed_bound_mps=implied_speed_bound_mps,
        )
        for index in range(fix_count - 1)
    ]
    points = _resample(observation, segments)

    observed_seconds = sum(1 for point in points if point.observed)
    derived_seconds = len(points)
    implied = [
        segment.implied_speed_mps
        for segment in segments
        if segment.implied_speed_mps is not None and _is_retained(segment)
    ]
    record = VehicleTraceAccounting(
        vehicle_key=observation.vehicle_key,
        fix_count=fix_count,
        matched_fix_count=matched_fix_count,
        matched_share=matched_share,
        included=derived_seconds > 0,
        exclusion_reason=None if derived_seconds > 0 else "no_retained_segment",
        segment_count=len(segments),
        interpolated_segment_count=_count(segments, "interpolated"),
        dwell_segment_count=_count(segments, "dwell"),
        dwell_segments_with_supplied_path_count=sum(
            1 for segment in segments if segment.dwell_path_supplied
        ),
        dropped_gap_segment_count=_count(segments, "dropped_gap_ceiling"),
        dropped_gap_seconds=sum(
            segment.end_s - segment.start_s
            for segment in segments
            if segment.outcome == "dropped_gap_ceiling"
        ),
        dropped_unmatched_fix_segment_count=_count(segments, "dropped_unmatched_fix"),
        dropped_missing_path_segment_count=_count(segments, "dropped_missing_path"),
        speed_flagged_segment_count=sum(1 for segment in segments if segment.speed_flagged),
        max_implied_speed_mps=max(implied) if implied else None,
        derived_second_count=derived_seconds,
        observed_second_count=observed_seconds,
        interpolated_second_count=derived_seconds - observed_seconds,
        interpolated_share=(
            (derived_seconds - observed_seconds) / derived_seconds if derived_seconds else None
        ),
        window_start_s=points[0].time_s if points else None,
        window_end_s=points[-1].time_s if points else None,
    )
    track = VehicleTrack(vehicle_key=observation.vehicle_key, points=points) if points else None
    return record, track


def _classify_segment(
    observation: VehicleObservation,
    index: int,
    *,
    gap_ceiling_s: int,
    dwell_radius_m: float,
    implied_speed_bound_mps: float,
) -> _SegmentResult:
    start = observation.fixes[index]
    end = observation.fixes[index + 1]
    path = observation.paths[index]
    elapsed_s = end.timestamp_s - start.timestamp_s

    if elapsed_s > gap_ceiling_s:
        return _dropped(start.timestamp_s, end.timestamp_s, "dropped_gap_ceiling")
    if not (start.matched and end.matched):
        return _dropped(start.timestamp_s, end.timestamp_s, "dropped_unmatched_fix")

    displacement_m = hypot(end.x_m - start.x_m, end.y_m - start.y_m)
    if displacement_m <= dwell_radius_m:
        implied = displacement_m / elapsed_s
        return _SegmentResult(
            outcome="dwell",
            start_s=start.timestamp_s,
            end_s=end.timestamp_s,
            implied_speed_mps=implied,
            speed_flagged=implied > implied_speed_bound_mps,
            path=None,
            dwell_path_supplied=path is not None,
        )
    if path is None:
        return _dropped(start.timestamp_s, end.timestamp_s, "dropped_missing_path")

    _require_path_connects(observation.vehicle_key, index, path, start, end)
    implied = path.length_m / elapsed_s
    return _SegmentResult(
        outcome="interpolated",
        start_s=start.timestamp_s,
        end_s=end.timestamp_s,
        implied_speed_mps=implied,
        speed_flagged=implied > implied_speed_bound_mps,
        path=path,
        dwell_path_supplied=False,
    )


def _require_path_connects(
    vehicle_key: str,
    index: int,
    path: MatchedPath,
    start: VehicleFix,
    end: VehicleFix,
) -> None:
    """Refuse a path that does not join the two fixes it claims to span.

    Bridging the discrepancy would mean drawing a straight line from the fix to
    the path — the one construction §3 forbids — so a disconnected path is
    reported as the matcher defect it is.
    """

    if path.points[0] != (start.x_m, start.y_m) or path.points[-1] != (end.x_m, end.y_m):
        raise BusTrajectoryError(
            f"vehicle {vehicle_key} segment {index}: the matched path does not run from the "
            "earlier fix's matched location to the later fix's"
        )


def _dropped(start_s: int, end_s: int, outcome: SegmentOutcome) -> _SegmentResult:
    return _SegmentResult(
        outcome=outcome,
        start_s=start_s,
        end_s=end_s,
        implied_speed_mps=None,
        speed_flagged=False,
        path=None,
        dwell_path_supplied=False,
    )


def _resample(
    observation: VehicleObservation, segments: Sequence[_SegmentResult]
) -> tuple[TracePoint, ...]:
    """Emit one position per second across each run of retained segments.

    Retained segments that touch produce one continuous run; a dropped segment
    ends the run, so the vehicle simply has no positions across the gap. Within
    a run, a second that coincides with a fix carries that fix's own matched
    location and is marked observed.
    """

    points: list[TracePoint] = []
    run: list[_SegmentResult] = []
    for segment in segments:
        if _is_retained(segment):
            run.append(segment)
            continue
        points.extend(_emit_run(observation, run))
        run = []
    points.extend(_emit_run(observation, run))
    return tuple(points)


def _emit_run(
    observation: VehicleObservation, run: Sequence[_SegmentResult]
) -> Iterator[TracePoint]:
    if not run:
        return
    fix_at = {fix.timestamp_s: fix for fix in observation.fixes}
    for position, segment in enumerate(run):
        cumulative = segment.path.cumulative_lengths_m if segment.path is not None else None
        length_m = cumulative[-1] if cumulative is not None else 0.0
        elapsed_s = segment.end_s - segment.start_s
        speed_mps = 0.0 if segment.path is None else length_m / elapsed_s
        entry = fix_at[segment.start_s]
        last = position == len(run) - 1
        final_second = segment.end_s if last else segment.end_s - 1
        for second in range(segment.start_s, final_second + 1):
            fix = fix_at.get(second)
            if fix is not None:
                yield TracePoint(
                    time_s=second,
                    x_m=fix.x_m,
                    y_m=fix.y_m,
                    speed_mps=speed_mps,
                    observed=True,
                )
                continue
            if segment.path is None or cumulative is None:
                # §3 dwell: stationary at the entry fix's matched location.
                yield TracePoint(
                    time_s=second,
                    x_m=entry.x_m,
                    y_m=entry.y_m,
                    speed_mps=0.0,
                    observed=False,
                )
                continue
            fraction = (second - segment.start_s) / elapsed_s
            x_m, y_m = _position_along(segment.path.points, cumulative, fraction * length_m)
            yield TracePoint(time_s=second, x_m=x_m, y_m=y_m, speed_mps=speed_mps, observed=False)


def _position_along(
    points: Sequence[tuple[float, float]],
    cumulative: Sequence[float],
    distance_m: float,
) -> tuple[float, float]:
    total = cumulative[-1]
    if distance_m <= 0 or total <= 0:
        return points[0]
    if distance_m >= total:
        return points[-1]
    index = max(bisect_right(cumulative, distance_m) - 1, 0)
    span = cumulative[index + 1] - cumulative[index]
    if span <= 0:
        return points[index]
    fraction = (distance_m - cumulative[index]) / span
    start = points[index]
    end = points[index + 1]
    return (
        start[0] + (end[0] - start[0]) * fraction,
        start[1] + (end[1] - start[1]) * fraction,
    )


def _is_retained(segment: _SegmentResult) -> bool:
    return segment.outcome in {"interpolated", "dwell"}


def _count(segments: Sequence[_SegmentResult], outcome: SegmentOutcome) -> int:
    return sum(1 for segment in segments if segment.outcome == outcome)


def _empty_accounting(
    vehicle_key: str,
    *,
    fix_count: int,
    matched_fix_count: int,
    matched_share: float | None,
    reason: VehicleExclusionReason,
) -> VehicleTraceAccounting:
    """Return the accounting for a vehicle excluded before any segment ran.

    An excluded vehicle's segments are never classified, so its counters are
    zero because no work happened — not because nothing was found.
    """

    return VehicleTraceAccounting(
        vehicle_key=vehicle_key,
        fix_count=fix_count,
        matched_fix_count=matched_fix_count,
        matched_share=matched_share,
        included=False,
        exclusion_reason=reason,
        segment_count=0,
        interpolated_segment_count=0,
        dwell_segment_count=0,
        dwell_segments_with_supplied_path_count=0,
        dropped_gap_segment_count=0,
        dropped_gap_seconds=0,
        dropped_unmatched_fix_segment_count=0,
        dropped_missing_path_segment_count=0,
        speed_flagged_segment_count=0,
        max_implied_speed_mps=None,
        derived_second_count=0,
        observed_second_count=0,
        interpolated_second_count=0,
        interpolated_share=None,
        window_start_s=None,
        window_end_s=None,
    )


def _build_report(
    *,
    trace_label: str,
    gap_ceiling_s: int,
    dwell_radius_m: float,
    matched_share_floor: float,
    implied_speed_bound_mps: float,
    accounting: tuple[VehicleTraceAccounting, ...],
) -> BusTraceReport:
    derived = sum(record.derived_second_count for record in accounting)
    observed = sum(record.observed_second_count for record in accounting)
    starts = [record.window_start_s for record in accounting if record.window_start_s is not None]
    ends = [record.window_end_s for record in accounting if record.window_end_s is not None]
    speeds = [
        record.max_implied_speed_mps
        for record in accounting
        if record.max_implied_speed_mps is not None
    ]
    return BusTraceReport(
        trace_label=trace_label,
        gap_ceiling_s=gap_ceiling_s,
        dwell_radius_m=float(dwell_radius_m),
        matched_share_floor=float(matched_share_floor),
        implied_speed_bound_mps=float(implied_speed_bound_mps),
        vehicle_count=len(accounting),
        included_vehicle_count=sum(1 for record in accounting if record.included),
        excluded_vehicle_count=sum(1 for record in accounting if not record.included),
        excluded_below_matched_share_count=sum(
            1 for record in accounting if record.exclusion_reason == "matched_share_below_floor"
        ),
        segment_count=sum(record.segment_count for record in accounting),
        interpolated_segment_count=sum(record.interpolated_segment_count for record in accounting),
        dwell_segment_count=sum(record.dwell_segment_count for record in accounting),
        dwell_segments_with_supplied_path_count=sum(
            record.dwell_segments_with_supplied_path_count for record in accounting
        ),
        dropped_gap_segment_count=sum(record.dropped_gap_segment_count for record in accounting),
        dropped_gap_seconds=sum(record.dropped_gap_seconds for record in accounting),
        dropped_unmatched_fix_segment_count=sum(
            record.dropped_unmatched_fix_segment_count for record in accounting
        ),
        dropped_missing_path_segment_count=sum(
            record.dropped_missing_path_segment_count for record in accounting
        ),
        speed_flagged_segment_count=sum(
            record.speed_flagged_segment_count for record in accounting
        ),
        max_implied_speed_mps=max(speeds) if speeds else None,
        derived_second_count=derived,
        observed_second_count=observed,
        interpolated_second_count=derived - observed,
        interpolated_share=((derived - observed) / derived if derived else None),
        window_start_s=min(starts) if starts else None,
        window_end_s=max(ends) if ends else None,
        vehicles=accounting,
    )
