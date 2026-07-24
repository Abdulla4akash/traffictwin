"""Thin UI service for the synthetic MAN-09 map-match review demonstration.

The page renders only what the tested library computes. This module builds one
deterministic, clearly labelled synthetic demonstration request (it is not
Manchester evidence), exposes the complete candidate product, and turns
explicit per-observation analyst selections into the typed review record.
Real-source matching, confidence classification, analyst acceptance, and any
SUMO baseline remain structurally unavailable behind their recorded blockers.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

from pyproj import Transformer

from traffictwin.integration.manchester.map_matching import (
    ManchesterMapMatchingPreflight,
    SyntheticEdgeMatchCandidate,
    SyntheticMapMatchingPolicy,
    SyntheticMapMatchReport,
    SyntheticMapMatchRequest,
    SyntheticMapMatchReview,
    SyntheticMapMatchReviewDecision,
    SyntheticObservationMatchContext,
    SyntheticSumoEdgeGeometry,
    Wgs84Coordinate,
    build_synthetic_network_binding,
    current_map_matching_preflight,
    evaluate_synthetic_map_matches,
    record_synthetic_map_match_review,
)
from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.integration.manchester.spatial import (
    ManchesterSpatialPointEvidence,
    evaluate_spatial_batch,
)
from traffictwin.integration.manchester.temporal_profile import (
    DeclaredExcludedDate,
    ManchesterTemporalProfileReport,
    TemporalProfileObservation,
    TemporalProfilePolicy,
    build_temporal_profile,
)

REJECT_ALL_SENTINEL = "__reject_all_candidates__"

_DEMO_NETWORK_ID = "synthetic-map-match-demo-network-v1"
_DEMO_NETWORK_SHA256 = sha256_hex(b"traffictwin-synthetic-map-match-demo-network-v1")
_DEMO_SCOPE_SHA256 = sha256_hex(b"traffictwin-synthetic-map-match-demo-scope-v1")
_BASE_EASTING = 383_626.0
_BASE_NORTHING = 398_205.0
_TO_WGS84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def _coordinate(easting: float, northing: float) -> Wgs84Coordinate:
    longitude, latitude = _TO_WGS84.transform(easting, northing)
    return Wgs84Coordinate(longitude=Decimal(str(longitude)), latitude=Decimal(str(latitude)))


def _point_evidence(
    point_id: str, easting: float, northing: float
) -> ManchesterSpatialPointEvidence:
    point = _coordinate(easting, northing)
    return ManchesterSpatialPointEvidence(
        source="synthetic",
        source_record_fingerprint=sha256_hex(point_id.encode("utf-8")),
        point_id=point_id,
        coordinate_kind="wgs84",
        longitude_epsg4326=point.longitude,
        latitude_epsg4326=point.latitude,
        geographic_scope="synthetic",
        scope_basis="synthetic_contract",
        scope_evidence_fingerprint=_DEMO_SCOPE_SHA256,
        geometry_meaning="synthetic_point",
        source_record_state="eligible",
        coordinate_uncertainty_m=Decimal("1"),
        uncertainty_basis="caller_declared",
        synthetic=True,
    )


def _edge(edge_id: str, easting: float, northing: float) -> SyntheticSumoEdgeGeometry:
    """Build one directed south-to-north synthetic edge (bearing about 0 degrees)."""

    return SyntheticSumoEdgeGeometry(
        network_sha256=_DEMO_NETWORK_SHA256,
        edge_id=edge_id,
        road_class="synthetic-road",
        shape=(
            _coordinate(easting, northing - 100),
            _coordinate(easting, northing + 100),
        ),
    )


def map_match_preflight_for_ui() -> ManchesterMapMatchingPreflight:
    """Return the exact fail-closed real-source availability record."""

    return current_map_matching_preflight()


def synthetic_map_match_demo_report() -> SyntheticMapMatchReport:
    """Build the deterministic synthetic demonstration candidate product.

    The fixture demonstrates the three review situations without inventing
    evidence: one observation with exactly one eligible candidate, one with
    two ambiguous eligible candidates, and one with no eligible candidate.
    """

    observations = (
        # One eligible candidate: only edge-a runs within the distance gate.
        _point_evidence("synthetic:obs-clear", _BASE_EASTING + 8, _BASE_NORTHING),
        # Two eligible candidates: edges b1/b2 run 10 m either side.
        _point_evidence("synthetic:obs-ambiguous", _BASE_EASTING + 400, _BASE_NORTHING),
        # No eligible candidate: every edge is far outside the gate.
        _point_evidence("synthetic:obs-distant", _BASE_EASTING + 5_000, _BASE_NORTHING),
    )
    spatial_report = evaluate_spatial_batch(observations)
    contexts = tuple(
        SyntheticObservationMatchContext(
            point_id=result.point_id,
            spatial_result_fingerprint=result.fingerprint(),
            direction_degrees=Decimal("0"),
            road_class="synthetic-road",
        )
        for result in sorted(spatial_report.results, key=lambda item: item.point_id)
    )
    edges = (
        _edge("edge-a", _BASE_EASTING, _BASE_NORTHING),
        _edge("edge-b1", _BASE_EASTING + 390, _BASE_NORTHING),
        _edge("edge-b2", _BASE_EASTING + 410, _BASE_NORTHING),
    )
    request = SyntheticMapMatchRequest(
        policy=SyntheticMapMatchingPolicy(
            policy_id="synthetic-demo-policy-v1",
            max_distance_m=Decimal("30"),
            max_direction_delta_degrees=Decimal("45"),
            require_road_class_match=True,
        ),
        network=build_synthetic_network_binding(_DEMO_NETWORK_ID, _DEMO_NETWORK_SHA256),
        spatial_report=spatial_report,
        observations=contexts,
        edges=edges,
    )
    return evaluate_synthetic_map_matches(request)


def eligible_candidates_by_point(
    report: SyntheticMapMatchReport,
) -> dict[str, list[SyntheticEdgeMatchCandidate]]:
    """Group the policy-eligible candidates by observation, keeping empties."""

    grouped: dict[str, list[SyntheticEdgeMatchCandidate]] = {
        observation.point_id: [] for observation in report.request.observations
    }
    for candidate in report.candidates:
        if candidate.eligible_under_synthetic_policy:
            grouped[candidate.point_id].append(candidate)
    return grouped


def review_from_selections(
    report: SyntheticMapMatchReport,
    selections: Mapping[str, str],
) -> SyntheticMapMatchReview:
    """Turn explicit per-observation selections into the typed review record.

    ``selections`` maps every observation to a selected candidate fingerprint
    or :data:`REJECT_ALL_SENTINEL`. The rejection reason is derived from the
    report itself: ``NO_SUITABLE_CANDIDATE`` when no eligible candidate exists
    and ``AMBIGUOUS_CANDIDATES`` when eligible candidates were declined.
    """

    eligible = eligible_candidates_by_point(report)
    decisions = []
    for observation in report.request.observations:
        selected = selections.get(observation.point_id, REJECT_ALL_SENTINEL)
        if selected == REJECT_ALL_SENTINEL:
            reason: Literal["AMBIGUOUS_CANDIDATES", "NO_SUITABLE_CANDIDATE"] = (
                "NO_SUITABLE_CANDIDATE"
                if not eligible[observation.point_id]
                else "AMBIGUOUS_CANDIDATES"
            )
            decisions.append(
                SyntheticMapMatchReviewDecision(
                    point_id=observation.point_id,
                    outcome="all_candidates_rejected",
                    candidate_fingerprint=None,
                    reason=reason,
                )
            )
        else:
            decisions.append(
                SyntheticMapMatchReviewDecision(
                    point_id=observation.point_id,
                    outcome="candidate_selected",
                    candidate_fingerprint=selected,
                    reason="SYNTHETIC_FIXTURE_SELECTION",
                )
            )
    return record_synthetic_map_match_review(report, decisions)


def candidate_display_rows(report: SyntheticMapMatchReport) -> list[dict[str, object]]:
    """Project the complete candidate product into human-readable table rows."""

    return [
        {
            "observation": candidate.point_id,
            "edge": candidate.edge_id,
            "distance_m": str(candidate.distance_m),
            "direction_delta_deg": (
                str(candidate.direction_delta_degrees)
                if candidate.direction_delta_degrees is not None
                else None
            ),
            "road_class_match": candidate.road_class_match,
            "eligible": candidate.eligible_under_synthetic_policy,
            "reasons": ", ".join(candidate.reasons),
        }
        for candidate in report.candidates
    ]


def synthetic_temporal_profile_demo() -> ManchesterTemporalProfileReport:
    """Build the deterministic synthetic temporal-profile demonstration.

    The labelled synthetic fixture demonstrates available, insufficient,
    missing, null-value, and declared-excluded-date cells without inventing
    evidence; missing cells stay visible and never become zero.
    """

    policy = TemporalProfilePolicy(
        policy_label="synthetic-demo-profile",
        source="synthetic_utc_road",
        measure="vehicle_count",
        unit="vehicles_per_interval",
        time_basis="utc",
        season_rule="none",
        window_start_date=dt.date(2026, 3, 2),
        window_end_date=dt.date(2026, 3, 8),
        expected_slot_labels=("07:00", "08:00"),
        declared_excluded_dates=(
            DeclaredExcludedDate(date=dt.date(2026, 3, 6), reason_label="declared-event-day"),
        ),
        minimum_cell_observations=2,
    )
    fingerprint = sha256_hex(b"traffictwin-synthetic-temporal-profile-demo-v1")
    observations = [
        TemporalProfileObservation(
            source="synthetic_utc_road",
            source_record_id=record_id,
            source_date=source_date,
            slot_label=slot,
            measure="vehicle_count",
            unit="vehicles_per_interval",
            value=value,
            snapshot_fingerprint=fingerprint,
            parser_report_fingerprint=fingerprint,
        )
        for record_id, source_date, slot, value in (
            # Weekday 07:00 becomes available: two observed survey days.
            ("synthetic:row-1", dt.date(2026, 3, 2), "07:00", Decimal("120")),
            ("synthetic:row-2", dt.date(2026, 3, 3), "07:00", Decimal("132")),
            # Weekday 08:00 stays insufficient: one observation under the
            # two-observation minimum.
            ("synthetic:row-3", dt.date(2026, 3, 2), "08:00", Decimal("141")),
            # A null value stays a typed exclusion, never zero.
            ("synthetic:row-4", dt.date(2026, 3, 4), "07:00", None),
            # A declared excluded date is refused with its reason label.
            ("synthetic:row-5", dt.date(2026, 3, 6), "07:00", Decimal("95")),
        )
    ]
    return build_temporal_profile(policy, observations)


def profile_cell_display_rows(report: ManchesterTemporalProfileReport) -> list[dict[str, object]]:
    """Project the complete cell grid into human-readable table rows."""

    return [
        {
            "day_type": cell.day_type,
            "slot": cell.slot_label,
            "state": cell.state,
            "observations": cell.observation_count,
            "mean": str(cell.mean_value) if cell.mean_value is not None else None,
            "dates": ", ".join(item.isoformat() for item in cell.contributing_dates),
        }
        for cell in report.cells
    ]
