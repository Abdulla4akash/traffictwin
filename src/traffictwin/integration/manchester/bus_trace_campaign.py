"""Approved dawn-to-peak B-BUS trajectory helpers.

This is the campaign-specific layer for
``docs/evaluation/bbus_dawn_peak_protocol_20260728.md``.  It makes two
differences from the earlier construction-only B1 components explicit:

* a position candidate is selected deterministically inside the already
  declared MAN-09 distance bounds; and
* a matched path above the owner's 32 m/s ceiling is dropped and counted
  before the historical :mod:`bus_trajectory` constructor sees it.

The module performs no acquisition, opens no quarantine, writes no file and
runs no router.  Callers supply session-tokenised observations and routed edge
paths.  A result stays ``owner_approved_candidate``: the rebuilt network is
reviewed but is not accepted for real matching, and this experiment does not
silently promote it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Literal, cast

from pydantic import Field, model_validator

from traffictwin.integration.manchester.bus_trajectory import (
    BusTraceDerivation,
    BusTraceReport,
    MatchedPath,
    VehicleFix,
    VehicleObservation,
    derive_bus_trace,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.network_geometry import EdgeSpatialIndex

BBUS_CAMPAIGN_TRACE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
BBUS_CAMPAIGN_TRACE_METHOD_VERSION: Literal["bbus-dawn-peak-trace-1.0"] = "bbus-dawn-peak-trace-1.0"

GAP_CEILING_S = 120
DWELL_RADIUS_M = 15.0
MATCHED_SHARE_FLOOR = 0.8
IMPLIED_SPEED_CEILING_MPS = 32.0
OUTER_SEARCH_RADIUS_M = 50.0
NATIVE_ELIGIBILITY_M = 30.0
FALLBACK_ELIGIBILITY_M = 50.0


class BBusCampaignTraceError(ValueError):
    """Raised when the approved candidate trace cannot be built as supplied."""


@dataclass(frozen=True, slots=True)
class ProjectedCandidate:
    """One deterministic position-to-edge candidate in a metric CRS."""

    edge_id: str
    edge_ordinal: int
    geometry_source: Literal["explicit_edge_shape", "junction_endpoints"]
    snapped_x_m: float
    snapped_y_m: float
    distance_m: float
    along_edge_m: float


@dataclass(frozen=True, slots=True)
class CampaignFix:
    """One deduplicated fix beside its optional selected edge candidate."""

    timestamp_s: int
    projected_x_m: float
    projected_y_m: float
    candidate: ProjectedCandidate | None

    def as_vehicle_fix(self) -> VehicleFix:
        """Return the historical constructor's fix without inventing a match."""

        candidate = self.candidate
        return VehicleFix(
            timestamp_s=self.timestamp_s,
            x_m=self.projected_x_m if candidate is None else candidate.snapped_x_m,
            y_m=self.projected_y_m if candidate is None else candidate.snapped_y_m,
            matched=candidate is not None,
        )


class CampaignVehicleSpeedAccounting(ManchesterSnapshotModel):
    """Speed-ceiling drops for one session token."""

    vehicle_key: str = Field(min_length=1)
    dropped_speed_segment_count: int = Field(ge=0)
    max_dropped_implied_speed_mps: float | None = Field(default=None, gt=0)


class ApprovedCampaignTraceReport(ManchesterSnapshotModel):
    """The approved drop-and-count rule wrapped around the base report."""

    schema_version: Literal["1.0"] = BBUS_CAMPAIGN_TRACE_SCHEMA_VERSION
    method_version: Literal["bbus-dawn-peak-trace-1.0"] = BBUS_CAMPAIGN_TRACE_METHOD_VERSION
    experiment_id: Literal["B-BUS-DAWN-PEAK-20260728"] = "B-BUS-DAWN-PEAK-20260728"
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    network_accepted_for_real_matching: Literal[False] = False
    derived_scenario: Literal[True] = True
    observed_fcd: Literal[False] = False
    buses_only: Literal[True] = True

    gap_ceiling_s: int = 120
    dwell_radius_m: float = 15.0
    matched_share_floor: float = 0.8
    implied_speed_ceiling_mps: float = 32.0
    speed_ceiling_response: Literal["drop_and_count"] = "drop_and_count"

    dropped_speed_segment_count: int = Field(ge=0)
    max_dropped_implied_speed_mps: float | None = Field(default=None, gt=0)
    effective_dropped_missing_path_segment_count: int = Field(ge=0)
    retained_max_implied_speed_mps: float | None = Field(default=None, ge=0)
    vehicles: tuple[CampaignVehicleSpeedAccounting, ...]
    base_trajectory_report: BusTraceReport

    @model_validator(mode="after")
    def validate_drop_accounting(self) -> ApprovedCampaignTraceReport:
        if (
            self.gap_ceiling_s,
            self.dwell_radius_m,
            self.matched_share_floor,
            self.implied_speed_ceiling_mps,
        ) != (
            GAP_CEILING_S,
            DWELL_RADIUS_M,
            MATCHED_SHARE_FLOOR,
            IMPLIED_SPEED_CEILING_MPS,
        ):
            raise ValueError("the approved trajectory controls are immutable")
        if self.dropped_speed_segment_count != sum(
            item.dropped_speed_segment_count for item in self.vehicles
        ):
            raise ValueError("per-vehicle speed drops do not reconcile")
        base = self.base_trajectory_report
        if base.speed_flagged_segment_count != 0:
            raise ValueError("a speed-ceiling violation reached the retaining constructor")
        expected_missing = (
            base.dropped_missing_path_segment_count - self.dropped_speed_segment_count
        )
        if self.effective_dropped_missing_path_segment_count != expected_missing:
            raise ValueError("effective missing-path count does not reconcile")
        if (
            self.retained_max_implied_speed_mps is not None
            and self.retained_max_implied_speed_mps > IMPLIED_SPEED_CEILING_MPS
        ):
            raise ValueError("a retained segment exceeds the approved speed ceiling")
        return self


@dataclass(frozen=True)
class ApprovedCampaignTraceDerivation:
    """The usable base tracks beside the campaign-specific audited report."""

    derivation: BusTraceDerivation
    report: ApprovedCampaignTraceReport


def select_position_candidate(
    *,
    index: EdgeSpatialIndex,
    x_m: float,
    y_m: float,
    bus_eligible_edge_ids: frozenset[str],
) -> tuple[ProjectedCandidate | None, bool]:
    """Select the nearest eligible edge and report an exact-distance tie.

    The search and eligibility values are the pre-result bindings in the
    approved protocol.  Geometry distance is primary and edge ID is the only
    tie breaker.  ``bool`` is true when another eligible edge has the same
    distance to within one nanometre; the decision stays visible in accounting.
    """

    if not (isfinite(x_m) and isfinite(y_m)):
        raise BBusCampaignTraceError("projected fix coordinates must be finite")
    choices: list[tuple[float, str, int, str, float, float, float]] = []
    for ordinal in index.edges_within(x_m, y_m, radius_m=OUTER_SEARCH_RADIUS_M):
        edge_id, _, _, source = index.edge_record(ordinal)
        if edge_id not in bus_eligible_edge_ids:
            continue
        geometry = index.geometry(ordinal)
        snapped_x, snapped_y, distance, along = project_onto_polyline(geometry, x_m, y_m)
        ceiling = (
            NATIVE_ELIGIBILITY_M if source == "explicit_edge_shape" else FALLBACK_ELIGIBILITY_M
        )
        if distance <= ceiling:
            choices.append((distance, edge_id, ordinal, source, snapped_x, snapped_y, along))
    if not choices:
        return None, False
    choices.sort(key=lambda item: (item[0], item[1]))
    selected = choices[0]
    tied = len(choices) > 1 and abs(choices[1][0] - selected[0]) <= 1e-9
    source = cast(Literal["explicit_edge_shape", "junction_endpoints"], selected[3])
    if source not in {"explicit_edge_shape", "junction_endpoints"}:
        raise BBusCampaignTraceError("candidate geometry source is outside the contract")
    return (
        ProjectedCandidate(
            edge_id=selected[1],
            edge_ordinal=selected[2],
            geometry_source=source,
            snapped_x_m=selected[4],
            snapped_y_m=selected[5],
            distance_m=selected[0],
            along_edge_m=selected[6],
        ),
        tied,
    )


def project_onto_polyline(
    geometry: Sequence[float], x_m: float, y_m: float
) -> tuple[float, float, float, float]:
    """Return snapped point, perpendicular distance and distance along a line."""

    if len(geometry) < 4 or len(geometry) % 2:
        raise BBusCampaignTraceError("an edge geometry needs at least two coordinate pairs")
    best: tuple[float, float, float, float] | None = None
    travelled = 0.0
    for index in range(0, len(geometry) - 2, 2):
        ax, ay = float(geometry[index]), float(geometry[index + 1])
        bx, by = float(geometry[index + 2]), float(geometry[index + 3])
        dx, dy = bx - ax, by - ay
        length = hypot(dx, dy)
        fraction = (
            0.0
            if length == 0.0
            else max(0.0, min(1.0, ((x_m - ax) * dx + (y_m - ay) * dy) / (length**2)))
        )
        snapped_x, snapped_y = ax + fraction * dx, ay + fraction * dy
        distance = hypot(x_m - snapped_x, y_m - snapped_y)
        candidate = (snapped_x, snapped_y, distance, travelled + fraction * length)
        if best is None or (distance, candidate[3]) < (best[2], best[3]):
            best = candidate
        travelled += length
    if best is None:  # pragma: no cover - guarded by the coordinate count
        raise BBusCampaignTraceError("edge geometry has no usable segment")
    return best


def routed_path(
    *,
    route_edge_ids: Sequence[str],
    start: ProjectedCandidate,
    end: ProjectedCandidate,
    index: EdgeSpatialIndex,
    edge_ordinals: Mapping[str, int],
) -> MatchedPath | None:
    """Clip one routed edge sequence to its two snapped endpoint positions."""

    if not route_edge_ids:
        return None
    if route_edge_ids[0] != start.edge_id or route_edge_ids[-1] != end.edge_id:
        return None
    try:
        geometries = [index.geometry(edge_ordinals[edge_id]) for edge_id in route_edge_ids]
    except KeyError:
        return None

    if len(geometries) == 1:
        if end.along_edge_m <= start.along_edge_m:
            return None
        points = _polyline_slice(geometries[0], start.along_edge_m, end.along_edge_m, start, end)
    else:
        points = _after_position(geometries[0], start.along_edge_m, start)
        for geometry in geometries[1:-1]:
            points.extend(_pairs(geometry))
        points.extend(_before_position(geometries[-1], end.along_edge_m, end))
        points = _deduplicate_adjacent(points)
    if len(points) < 2 or points[0] != (start.snapped_x_m, start.snapped_y_m):
        return None
    if points[-1] != (end.snapped_x_m, end.snapped_y_m):
        return None
    if all(point == points[0] for point in points[1:]):
        return None
    return MatchedPath(points=tuple(points))


def build_vehicle_observation(
    *,
    vehicle_key: str,
    fixes: Sequence[CampaignFix],
    routes_by_segment: Mapping[int, MatchedPath | None],
) -> VehicleObservation:
    """Assemble one vehicle with positional route indices."""

    paths = tuple(routes_by_segment.get(index) for index in range(max(len(fixes) - 1, 0)))
    return VehicleObservation(
        vehicle_key=vehicle_key,
        fixes=tuple(fix.as_vehicle_fix() for fix in fixes),
        paths=paths,
    )


def derive_approved_campaign_trace(
    observations: Iterable[VehicleObservation], *, trace_label: str
) -> ApprovedCampaignTraceDerivation:
    """Apply the approved 32 m/s drop rule, then derive one-second tracks."""

    prepared: list[VehicleObservation] = []
    accounting: list[CampaignVehicleSpeedAccounting] = []
    all_dropped_speeds: list[float] = []
    for observation in observations:
        revised_paths = list(observation.paths)
        dropped: list[float] = []
        for index, path in enumerate(observation.paths):
            if path is None:
                continue
            start, end = observation.fixes[index], observation.fixes[index + 1]
            elapsed_s = end.timestamp_s - start.timestamp_s
            if elapsed_s <= 0:
                raise BBusCampaignTraceError(
                    f"vehicle {observation.vehicle_key} has non-positive segment time"
                )
            # Gap and dwell precede the speed rule in the approved order.
            if elapsed_s > GAP_CEILING_S:
                continue
            if hypot(end.x_m - start.x_m, end.y_m - start.y_m) <= DWELL_RADIUS_M:
                continue
            implied_speed = path.length_m / elapsed_s
            if implied_speed > IMPLIED_SPEED_CEILING_MPS:
                revised_paths[index] = None
                dropped.append(implied_speed)
        prepared.append(
            VehicleObservation(
                vehicle_key=observation.vehicle_key,
                fixes=observation.fixes,
                paths=tuple(revised_paths),
            )
        )
        all_dropped_speeds.extend(dropped)
        accounting.append(
            CampaignVehicleSpeedAccounting(
                vehicle_key=observation.vehicle_key,
                dropped_speed_segment_count=len(dropped),
                max_dropped_implied_speed_mps=max(dropped) if dropped else None,
            )
        )

    base = derive_bus_trace(
        prepared,
        trace_label=trace_label,
        gap_ceiling_s=GAP_CEILING_S,
        dwell_radius_m=DWELL_RADIUS_M,
        matched_share_floor=MATCHED_SHARE_FLOOR,
        implied_speed_bound_mps=IMPLIED_SPEED_CEILING_MPS,
    )
    dropped_count = len(all_dropped_speeds)
    effective_missing = base.report.dropped_missing_path_segment_count - dropped_count
    if effective_missing < 0:
        raise BBusCampaignTraceError("speed drops exceed the base missing-path count")
    report = ApprovedCampaignTraceReport(
        dropped_speed_segment_count=dropped_count,
        max_dropped_implied_speed_mps=(max(all_dropped_speeds) if all_dropped_speeds else None),
        effective_dropped_missing_path_segment_count=effective_missing,
        retained_max_implied_speed_mps=base.report.max_implied_speed_mps,
        vehicles=tuple(accounting),
        base_trajectory_report=base.report,
    )
    return ApprovedCampaignTraceDerivation(derivation=base, report=report)


def _pairs(geometry: Sequence[float]) -> list[tuple[float, float]]:
    return [
        (float(geometry[index]), float(geometry[index + 1])) for index in range(0, len(geometry), 2)
    ]


def _cumulative(points: Sequence[tuple[float, float]]) -> list[float]:
    values = [0.0]
    for start, end in zip(points, points[1:], strict=False):
        values.append(values[-1] + hypot(end[0] - start[0], end[1] - start[1]))
    return values


def _after_position(
    geometry: Sequence[float], along_m: float, candidate: ProjectedCandidate
) -> list[tuple[float, float]]:
    points = _pairs(geometry)
    cumulative = _cumulative(points)
    return _deduplicate_adjacent(
        [(candidate.snapped_x_m, candidate.snapped_y_m)]
        + [point for point, distance in zip(points, cumulative, strict=True) if distance > along_m]
    )


def _before_position(
    geometry: Sequence[float], along_m: float, candidate: ProjectedCandidate
) -> list[tuple[float, float]]:
    points = _pairs(geometry)
    cumulative = _cumulative(points)
    return _deduplicate_adjacent(
        [point for point, distance in zip(points, cumulative, strict=True) if distance < along_m]
        + [(candidate.snapped_x_m, candidate.snapped_y_m)]
    )


def _polyline_slice(
    geometry: Sequence[float],
    start_along_m: float,
    end_along_m: float,
    start: ProjectedCandidate,
    end: ProjectedCandidate,
) -> list[tuple[float, float]]:
    points = _pairs(geometry)
    cumulative = _cumulative(points)
    return _deduplicate_adjacent(
        [(start.snapped_x_m, start.snapped_y_m)]
        + [
            point
            for point, distance in zip(points, cumulative, strict=True)
            if start_along_m < distance < end_along_m
        ]
        + [(end.snapped_x_m, end.snapped_y_m)]
    )


def _deduplicate_adjacent(
    points: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for point in points:
        if not result or point != result[-1]:
            result.append(point)
    return result
