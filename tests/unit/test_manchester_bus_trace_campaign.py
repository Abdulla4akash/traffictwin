from __future__ import annotations

import pytest

from traffictwin.integration.manchester.bus_trace_campaign import (
    CampaignFix,
    ProjectedCandidate,
    build_vehicle_observation,
    derive_approved_campaign_trace,
    project_onto_polyline,
    routed_path,
    select_position_candidate,
)
from traffictwin.integration.manchester.bus_trajectory import (
    MatchedPath,
    VehicleFix,
    VehicleObservation,
)
from traffictwin.integration.manchester.network_geometry import EdgeSpatialIndex


def _record(edge_id: str, source: str = "explicit_edge_shape") -> tuple[object, ...]:
    return (
        edge_id,
        f"from-{edge_id}",
        f"to-{edge_id}",
        "highway.primary",
        "A1",
        source,
        (0.0, 0.0, 0.001, 0.0),
    )


def _candidate(
    edge_id: str,
    ordinal: int,
    x: float,
    *,
    along: float,
) -> ProjectedCandidate:
    return ProjectedCandidate(
        edge_id=edge_id,
        edge_ordinal=ordinal,
        geometry_source="explicit_edge_shape",
        snapped_x_m=x,
        snapped_y_m=0.0,
        distance_m=0.0,
        along_edge_m=along,
    )


def test_projection_records_snapped_point_distance_and_along_edge() -> None:
    snapped_x, snapped_y, distance, along = project_onto_polyline(
        (0.0, 0.0, 100.0, 0.0, 100.0, 100.0), 80.0, 30.0
    )

    assert (snapped_x, snapped_y) == (100.0, 30.0)
    assert distance == pytest.approx(20.0)
    assert along == pytest.approx(130.0)


def test_candidate_selection_is_bus_filtered_bounded_and_edge_id_tied() -> None:
    index = EdgeSpatialIndex(200.0)
    index.add(_record("edge-b"), (0.0, 0.0, 100.0, 0.0))  # type: ignore[arg-type]
    index.add(_record("edge-a"), (0.0, 0.0, 100.0, 0.0))  # type: ignore[arg-type]
    index.add(_record("not-for-bus"), (0.0, 0.0, 100.0, 0.0))  # type: ignore[arg-type]

    selected, tied = select_position_candidate(
        index=index,
        x_m=50.0,
        y_m=5.0,
        bus_eligible_edge_ids=frozenset({"edge-a", "edge-b"}),
    )

    assert selected is not None
    assert selected.edge_id == "edge-a"
    assert selected.distance_m == pytest.approx(5.0)
    assert tied is True

    absent, _ = select_position_candidate(
        index=index,
        x_m=50.0,
        y_m=31.0,
        bus_eligible_edge_ids=frozenset({"edge-a", "edge-b"}),
    )
    assert absent is None


def test_routed_path_clips_first_and_last_edges_to_snapped_positions() -> None:
    index = EdgeSpatialIndex(200.0)
    index.add(_record("edge-a"), (0.0, 0.0, 100.0, 0.0))  # type: ignore[arg-type]
    index.add(_record("edge-b"), (100.0, 0.0, 200.0, 0.0))  # type: ignore[arg-type]

    path = routed_path(
        route_edge_ids=("edge-a", "edge-b"),
        start=_candidate("edge-a", 0, 20.0, along=20.0),
        end=_candidate("edge-b", 1, 180.0, along=80.0),
        index=index,
        edge_ordinals={"edge-a": 0, "edge-b": 1},
    )

    assert path is not None
    assert path.points == ((20.0, 0.0), (100.0, 0.0), (180.0, 0.0))
    assert path.length_m == pytest.approx(160.0)


def test_reverse_progress_on_one_directed_edge_is_not_invented() -> None:
    index = EdgeSpatialIndex(200.0)
    index.add(_record("edge-a"), (0.0, 0.0, 100.0, 0.0))  # type: ignore[arg-type]

    assert (
        routed_path(
            route_edge_ids=("edge-a",),
            start=_candidate("edge-a", 0, 80.0, along=80.0),
            end=_candidate("edge-a", 0, 20.0, along=20.0),
            index=index,
            edge_ordinals={"edge-a": 0},
        )
        is None
    )


def test_speed_violation_is_dropped_and_counted_not_flagged_and_retained() -> None:
    observation = VehicleObservation(
        vehicle_key="session-token",
        fixes=(
            VehicleFix(timestamp_s=0, x_m=0.0, y_m=0.0, matched=True),
            VehicleFix(timestamp_s=10, x_m=400.0, y_m=0.0, matched=True),
        ),
        paths=(MatchedPath(points=((0.0, 0.0), (400.0, 0.0))),),
    )

    result = derive_approved_campaign_trace((observation,), trace_label="dawn")

    assert result.report.dropped_speed_segment_count == 1
    assert result.report.max_dropped_implied_speed_mps == pytest.approx(40.0)
    assert result.report.effective_dropped_missing_path_segment_count == 0
    assert result.report.base_trajectory_report.speed_flagged_segment_count == 0
    assert result.report.base_trajectory_report.dropped_missing_path_segment_count == 1
    assert result.derivation.tracks == ()


def test_retained_path_stays_below_ceiling_and_preserves_labels() -> None:
    observation = VehicleObservation(
        vehicle_key="session-token",
        fixes=(
            VehicleFix(timestamp_s=0, x_m=0.0, y_m=0.0, matched=True),
            VehicleFix(timestamp_s=10, x_m=100.0, y_m=0.0, matched=True),
        ),
        paths=(MatchedPath(points=((0.0, 0.0), (100.0, 0.0))),),
    )

    result = derive_approved_campaign_trace((observation,), trace_label="peak")

    assert result.report.dropped_speed_segment_count == 0
    assert result.report.retained_max_implied_speed_mps == pytest.approx(10.0)
    assert result.report.network_accepted_for_real_matching is False
    assert result.report.derived_scenario is True
    assert result.report.observed_fcd is False
    assert result.report.buses_only is True
    assert len(result.derivation.tracks[0].points) == 11


def test_vehicle_assembly_preserves_positional_missing_routes() -> None:
    fixes = (
        CampaignFix(0, 0.0, 0.0, _candidate("a", 0, 0.0, along=0.0)),
        CampaignFix(10, 100.0, 0.0, _candidate("a", 0, 100.0, along=100.0)),
        CampaignFix(20, 200.0, 0.0, None),
    )
    path = MatchedPath(points=((0.0, 0.0), (100.0, 0.0)))

    observation = build_vehicle_observation(
        vehicle_key="token",
        fixes=fixes,
        routes_by_segment={0: path},
    )

    assert observation.paths == (path, None)
    assert observation.fixes[-1].matched is False
