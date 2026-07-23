"""Synthetic-only evidence and refusals for the MAN-09 map-matching candidate."""

from __future__ import annotations

import json
from decimal import Decimal

import pyproj
import pytest
from pydantic import ValidationError
from pyproj import Transformer

from traffictwin.integration.manchester.map_matching import (
    MANCHESTER_MAP_MATCHING_CAPABILITY_ID,
    MANCHESTER_MAP_MATCHING_METHOD_VERSION,
    ManchesterMapMatchingError,
    ManchesterMapMatchingPreflight,
    SyntheticEdgeMatchCandidate,
    SyntheticMapMatchingPolicy,
    SyntheticMapMatchReport,
    SyntheticMapMatchRequest,
    SyntheticMapMatchReviewDecision,
    SyntheticObservationMatchContext,
    SyntheticSumoEdgeGeometry,
    Wgs84Coordinate,
    build_synthetic_network_binding,
    current_map_matching_preflight,
    evaluate_synthetic_map_matches,
    record_synthetic_map_match_review,
)
from traffictwin.integration.manchester.spatial import (
    ManchesterSpatialPointEvidence,
    SpatialAdmissionReport,
    evaluate_spatial_batch,
)

NETWORK_HASH = "a" * 64
SCOPE_HASH = "b" * 64
RECORD_HASH = "c" * 64
BASE_EASTING = 383_626.0
BASE_NORTHING = 398_205.0
_TO_WGS84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def coordinate(easting: float, northing: float) -> Wgs84Coordinate:
    longitude, latitude = _TO_WGS84.transform(easting, northing)
    return Wgs84Coordinate(
        longitude=Decimal(str(longitude)),
        latitude=Decimal(str(latitude)),
    )


def spatial_report(*, second_point: bool = False) -> SpatialAdmissionReport:
    point = coordinate(BASE_EASTING, BASE_NORTHING)
    evidence = [
        ManchesterSpatialPointEvidence(
            source="synthetic",
            source_record_fingerprint=RECORD_HASH,
            point_id="synthetic:observation-1",
            coordinate_kind="wgs84",
            longitude_epsg4326=point.longitude,
            latitude_epsg4326=point.latitude,
            geographic_scope="synthetic",
            scope_basis="synthetic_contract",
            scope_evidence_fingerprint=SCOPE_HASH,
            geometry_meaning="synthetic_point",
            source_record_state="eligible",
            coordinate_uncertainty_m=Decimal("1"),
            uncertainty_basis="caller_declared",
            synthetic=True,
        )
    ]
    if second_point:
        other = coordinate(BASE_EASTING + 40, BASE_NORTHING)
        evidence.append(
            ManchesterSpatialPointEvidence(
                source="synthetic",
                source_record_fingerprint="d" * 64,
                point_id="synthetic:observation-2",
                coordinate_kind="wgs84",
                longitude_epsg4326=other.longitude,
                latitude_epsg4326=other.latitude,
                geographic_scope="synthetic",
                scope_basis="synthetic_contract",
                scope_evidence_fingerprint=SCOPE_HASH,
                geometry_meaning="synthetic_point",
                source_record_state="eligible",
                coordinate_uncertainty_m=Decimal("1"),
                uncertainty_basis="caller_declared",
                synthetic=True,
            )
        )
    return evaluate_spatial_batch(tuple(evidence))


def edges(*, near_road_class: str | None = "primary") -> tuple[SyntheticSumoEdgeGeometry, ...]:
    return (
        SyntheticSumoEdgeGeometry(
            network_sha256=NETWORK_HASH,
            edge_id="edge-near",
            road_class=near_road_class,
            shape=(
                coordinate(BASE_EASTING + 10, BASE_NORTHING - 100),
                coordinate(BASE_EASTING + 10, BASE_NORTHING + 100),
            ),
        ),
        SyntheticSumoEdgeGeometry(
            network_sha256=NETWORK_HASH,
            edge_id="edge-other",
            road_class="primary",
            shape=(
                coordinate(BASE_EASTING - 100, BASE_NORTHING + 50),
                coordinate(BASE_EASTING + 100, BASE_NORTHING + 50),
            ),
        ),
    )


def request(
    *,
    report: SpatialAdmissionReport | None = None,
    direction: Decimal | None = Decimal("0"),
    road_class: str | None = "primary",
    require_road_class: bool = True,
    edge_values: tuple[SyntheticSumoEdgeGeometry, ...] | None = None,
) -> SyntheticMapMatchRequest:
    admitted = report or spatial_report()
    contexts = tuple(
        SyntheticObservationMatchContext(
            point_id=result.point_id,
            spatial_result_fingerprint=result.fingerprint(),
            direction_degrees=direction,
            road_class=road_class,
        )
        for result in sorted(admitted.results, key=lambda item: item.point_id)
    )
    return SyntheticMapMatchRequest(
        policy=SyntheticMapMatchingPolicy(
            policy_id="synthetic-policy-v1",
            max_distance_m=Decimal("30"),
            max_direction_delta_degrees=Decimal("20"),
            require_road_class_match=require_road_class,
        ),
        network=build_synthetic_network_binding("synthetic-network-v1", NETWORK_HASH),
        spatial_report=admitted,
        observations=contexts,
        edges=edge_values or edges(),
    )


def test_real_map_matching_preflight_is_explicitly_unavailable() -> None:
    preflight = current_map_matching_preflight()

    assert preflight.capability_id == MANCHESTER_MAP_MATCHING_CAPABILITY_ID
    assert preflight.method_version == MANCHESTER_MAP_MATCHING_METHOD_VERSION
    assert preflight.capability_status == "planned"
    assert preflight.status == "unavailable"
    assert preflight.blockers == (
        "MANCHESTER_NETWORK_LICENCE_UNAPPROVED",
        "MANCHESTER_NETWORK_NOT_REVIEWED",
        "MAP_MATCH_POLICY_UNAPPROVED",
        "REAL_SOURCE_GATE_B_UNACCEPTED",
    )
    assert preflight.real_candidate_generation_available is False
    assert preflight.sumo_baseline_available is False
    assert preflight.observation_to_demand_conversion_available is False


def test_preflight_blockers_cannot_be_weakened() -> None:
    payload = current_map_matching_preflight().model_dump(mode="python")
    payload["blockers"] = payload["blockers"][:-1]
    with pytest.raises(ValidationError, match="every current reviewed blocker"):
        ManchesterMapMatchingPreflight.model_validate(payload)


def test_synthetic_candidates_have_golden_distance_direction_and_complete_counts() -> None:
    report = evaluate_synthetic_map_matches(request())

    assert report.status == "synthetic_candidates_require_review"
    assert report.counts.observations_seen == 1
    assert report.counts.edges_seen == 2
    assert report.counts.candidate_pairs_evaluated == 2
    assert report.counts.eligible_pairs == 1
    assert report.counts.observations_without_eligible_candidate == 0
    near = report.candidates[0]
    assert near.edge_id == "edge-near"
    assert abs(near.distance_m - Decimal("10")) <= Decimal("0.002")
    assert abs(near.edge_bearing_degrees - Decimal("0")) <= Decimal("0.002")
    assert near.direction_delta_degrees is not None
    assert near.direction_delta_degrees <= Decimal("0.002")
    assert near.road_class_match is True
    assert near.eligible_under_synthetic_policy is True
    assert near.reasons == (
        "DISTANCE_WITHIN_THRESHOLD",
        "DIRECTION_WITHIN_THRESHOLD",
        "ROAD_CLASS_MATCH",
    )


def test_candidate_output_never_selects_or_claims_confidence_or_identity() -> None:
    report = evaluate_synthetic_map_matches(request())

    assert report.manual_review_required is True
    assert report.automatic_selection_performed is False
    assert report.real_manchester_matching_available is False
    assert report.confidence_classification_available is False
    assert report.sumo_baseline_available is False
    for candidate in report.candidates:
        assert candidate.confidence == "synthetic_rule_only"
        assert candidate.manual_review_required is True
        assert candidate.automatically_selected is False
        assert candidate.identity_join_established is False
        assert candidate.approved_for_manchester is False


def test_distance_direction_and_road_class_gates_are_all_explicit() -> None:
    mismatched = request(direction=Decimal("180"), edge_values=edges(near_road_class="secondary"))
    report = evaluate_synthetic_map_matches(mismatched)
    near = next(item for item in report.candidates if item.edge_id == "edge-near")

    assert near.passes_distance is True
    assert near.passes_direction is False
    assert near.passes_road_class is False
    assert near.eligible_under_synthetic_policy is False
    assert near.reasons == (
        "DISTANCE_WITHIN_THRESHOLD",
        "DIRECTION_OUTSIDE_THRESHOLD",
        "ROAD_CLASS_MISMATCH",
    )
    assert report.counts.eligible_pairs == 0
    assert report.counts.observations_without_eligible_candidate == 1


def test_missing_direction_and_disabled_road_class_are_visible_not_inferred() -> None:
    report = evaluate_synthetic_map_matches(
        request(direction=None, road_class=None, require_road_class=False)
    )
    near = report.candidates[0]

    assert near.direction_delta_degrees is None
    assert near.road_class_match is None
    assert near.reasons == (
        "DISTANCE_WITHIN_THRESHOLD",
        "DIRECTION_NOT_PROVIDED",
        "ROAD_CLASS_NOT_REQUIRED",
    )


def test_request_requires_sorted_unique_complete_lineage() -> None:
    valid = request()
    values = valid.model_dump(mode="python")
    values["edges"] = tuple(reversed(values["edges"]))
    with pytest.raises(ValidationError, match="sorted unique edge IDs"):
        SyntheticMapMatchRequest.model_validate(values)

    values = valid.model_dump(mode="python")
    values["observations"] = ()
    with pytest.raises(ValidationError):
        SyntheticMapMatchRequest.model_validate(values)

    values = valid.model_dump(mode="python")
    values["edges"][0]["network_sha256"] = "f" * 64
    with pytest.raises(ValidationError, match="bind the request network"):
        SyntheticMapMatchRequest.model_validate(values)


def test_real_or_partially_admitted_spatial_evidence_is_refused() -> None:
    admitted = spatial_report()
    foreign_result = admitted.results[0].model_copy(update={"source": "dft"})
    foreign_report = admitted.model_copy(update={"results": (foreign_result,)})
    with pytest.raises(ValidationError, match="only admitted synthetic points"):
        request(report=foreign_report)

    unavailable = admitted.model_copy(update={"status": "partial"})
    with pytest.raises(ValidationError):
        request(report=unavailable)


def test_network_runtime_and_synthetic_boundaries_cannot_be_strengthened() -> None:
    binding = build_synthetic_network_binding("synthetic-network-v1", NETWORK_HASH)
    for mutation in (
        {"pyproj_version": "0.0"},
        {"proj_version": "0.0"},
        {"synthetic": False},
        {"reviewed_manchester_network": True},
        {"accepted_for_real_matching": True},
        {"licence_id": "OGL-v3.0"},
    ):
        payload = binding.model_dump(mode="python")
        payload.update(mutation)
        with pytest.raises(ValidationError):
            type(binding).model_validate(payload)
    assert binding.pyproj_version == pyproj.__version__
    assert binding.proj_version == pyproj.proj_version_str


def test_report_is_deterministic_and_mutations_fail_closed() -> None:
    match_request = request()
    first = evaluate_synthetic_map_matches(match_request)
    second = evaluate_synthetic_map_matches(match_request)
    assert first == second
    assert first.fingerprint() == second.fingerprint()

    payload = json.loads(first.canonical_json())
    payload["candidates"][0]["distance_m"] = "999.000"
    with pytest.raises(ValidationError, match="deterministic geometry"):
        SyntheticMapMatchReport.model_validate_json(json.dumps(payload))

    candidate_payload = first.candidates[0].model_dump(mode="python")
    candidate_payload["identity_join_established"] = True
    with pytest.raises(ValidationError):
        SyntheticEdgeMatchCandidate.model_validate(candidate_payload)


def test_manual_review_is_complete_and_still_cannot_create_a_baseline() -> None:
    report = evaluate_synthetic_map_matches(request())
    selected = next(item for item in report.candidates if item.eligible_under_synthetic_policy)
    decision = SyntheticMapMatchReviewDecision(
        point_id=selected.point_id,
        outcome="candidate_selected",
        candidate_fingerprint=selected.fingerprint(),
        reason="SYNTHETIC_FIXTURE_SELECTION",
    )
    review = record_synthetic_map_match_review(report, (decision,))

    assert review.report_fingerprint == report.fingerprint()
    assert review.observations_reviewed == 1
    assert review.candidates_selected == 1
    assert review.complete_manual_review is True
    assert review.accepted_real_map_match is False
    assert review.sumo_baseline_available is False
    assert review.calibration_available is False


def test_review_refuses_incomplete_unknown_and_ineligible_selections() -> None:
    two_point_report = evaluate_synthetic_map_matches(
        request(report=spatial_report(second_point=True))
    )
    with pytest.raises(ManchesterMapMatchingError) as incomplete:
        record_synthetic_map_match_review(two_point_report, ())
    assert incomplete.value.code == "INCOMPLETE_REVIEW"

    one_point_report = evaluate_synthetic_map_matches(request())
    unknown = SyntheticMapMatchReviewDecision(
        point_id="synthetic:observation-1",
        outcome="candidate_selected",
        candidate_fingerprint="f" * 64,
        reason="SYNTHETIC_FIXTURE_SELECTION",
    )
    with pytest.raises(ManchesterMapMatchingError) as missing:
        record_synthetic_map_match_review(one_point_report, (unknown,))
    assert missing.value.code == "UNKNOWN_CANDIDATE"

    ineligible = next(
        item for item in one_point_report.candidates if not item.eligible_under_synthetic_policy
    )
    rejected_choice = SyntheticMapMatchReviewDecision(
        point_id=ineligible.point_id,
        outcome="candidate_selected",
        candidate_fingerprint=ineligible.fingerprint(),
        reason="SYNTHETIC_FIXTURE_SELECTION",
    )
    with pytest.raises(ManchesterMapMatchingError) as refused:
        record_synthetic_map_match_review(one_point_report, (rejected_choice,))
    assert refused.value.code == "INELIGIBLE_CANDIDATE"


def test_rejection_review_has_typed_reason_and_no_free_text() -> None:
    report = evaluate_synthetic_map_matches(
        request(direction=Decimal("180"), edge_values=edges(near_road_class="secondary"))
    )
    decision = SyntheticMapMatchReviewDecision(
        point_id="synthetic:observation-1",
        outcome="all_candidates_rejected",
        reason="NO_SUITABLE_CANDIDATE",
    )
    review = record_synthetic_map_match_review(report, (decision,))
    assert review.candidates_selected == 0
    assert review.observations_rejected == 1
    assert "reviewer_name" not in SyntheticMapMatchReviewDecision.model_fields
    assert "free_text" not in SyntheticMapMatchReviewDecision.model_fields
