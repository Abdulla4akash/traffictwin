"""Fail-closed MAN-09 preflight and deterministic synthetic map matching.

Real Manchester observation-to-SUMO matching remains unavailable because the
repository has neither a reviewed Manchester SUMO network/licence nor an
approved distance/direction/road-class policy.  This module makes those
blockers structural while providing a synthetic-only harness for testing
geometry, candidate reconciliation, ambiguity, and explicit analyst review.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Literal, TypeAlias

import pyproj
from pydantic import Field, model_validator
from pyproj import Transformer

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.spatial import (
    SpatialAdmissionReport,
    SpatialAdmissionResult,
)

MANCHESTER_MAP_MATCHING_SCHEMA_VERSION = "1.0"
MANCHESTER_MAP_MATCHING_METHOD_VERSION = "manchester-map-matching-candidate-1.0"
MANCHESTER_MAP_MATCHING_CAPABILITY_ID = "MAN-09"

_DISTANCE_CRS = "EPSG:27700"
_TARGET_CRS = "EPSG:4326"
_DISTANCE_QUANTUM = Decimal("0.001")
_ANGLE_QUANTUM = Decimal("0.001")
_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$"
_ROAD_CLASS_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/ -]{0,99}$"

MapMatchingBlocker: TypeAlias = Literal[
    "MANCHESTER_NETWORK_LICENCE_UNAPPROVED",
    "MANCHESTER_NETWORK_NOT_REVIEWED",
    "MAP_MATCH_POLICY_UNAPPROVED",
    "REAL_SOURCE_GATE_B_UNACCEPTED",
]
CandidateReason: TypeAlias = Literal[
    "DIRECTION_NOT_PROVIDED",
    "DIRECTION_OUTSIDE_THRESHOLD",
    "DIRECTION_WITHIN_THRESHOLD",
    "DISTANCE_OUTSIDE_THRESHOLD",
    "DISTANCE_WITHIN_THRESHOLD",
    "ROAD_CLASS_MATCH",
    "ROAD_CLASS_MISMATCH",
    "ROAD_CLASS_MISSING",
    "ROAD_CLASS_NOT_REQUIRED",
]
ReviewReason: TypeAlias = Literal[
    "AMBIGUOUS_CANDIDATES",
    "NO_SUITABLE_CANDIDATE",
    "SYNTHETIC_FIXTURE_SELECTION",
]

_REAL_BLOCKERS: tuple[MapMatchingBlocker, ...] = (
    "MANCHESTER_NETWORK_LICENCE_UNAPPROVED",
    "MANCHESTER_NETWORK_NOT_REVIEWED",
    "MAP_MATCH_POLICY_UNAPPROVED",
    "REAL_SOURCE_GATE_B_UNACCEPTED",
)


class ManchesterMapMatchingError(ValueError):
    """Typed refusal for unsupported or inconsistent map-matching input."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterMapMatchingModel(ManchesterSnapshotModel):
    """Strict frozen base for candidate MAN-09 artifacts."""


class ManchesterMapMatchingPreflight(ManchesterMapMatchingModel):
    """Current real-source availability without fabricated policy decisions."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-map-matching-candidate-1.0"] = (
        "manchester-map-matching-candidate-1.0"
    )
    capability_status: Literal["planned"] = "planned"
    status: Literal["unavailable"] = "unavailable"
    blockers: tuple[MapMatchingBlocker, ...]
    real_candidate_generation_available: Literal[False] = False
    confidence_classification_available: Literal[False] = False
    analyst_acceptance_available: Literal[False] = False
    sumo_baseline_available: Literal[False] = False
    synthetic_harness_available: Literal[True] = True
    observation_to_demand_conversion_available: Literal[False] = False
    visual_proximity_establishes_identity: Literal[False] = False

    @model_validator(mode="after")
    def validate_preflight(self) -> ManchesterMapMatchingPreflight:
        if self.blockers != _REAL_BLOCKERS:
            raise ValueError("real map matching must retain every current reviewed blocker")
        return self


class SyntheticMapMatchingPolicy(ManchesterMapMatchingModel):
    """Caller-declared thresholds usable only by labelled synthetic fixtures."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    policy_id: str = Field(pattern=_ID_PATTERN)
    max_distance_m: Decimal = Field(gt=0, le=5_000)
    max_direction_delta_degrees: Decimal = Field(ge=0, le=180)
    require_road_class_match: bool
    distance_precision_m: Literal["0.001"] = "0.001"
    angle_precision_degrees: Literal["0.001"] = "0.001"
    evidence_class: Literal["synthetic_test_only"] = "synthetic_test_only"
    approved_for_manchester: Literal[False] = False
    scientific_confidence_available: Literal[False] = False
    automatic_selection_available: Literal[False] = False


class SyntheticSumoNetworkBinding(ManchesterMapMatchingModel):
    """Synthetic network identity; never a reviewed Manchester network claim."""

    network_id: str = Field(pattern=_ID_PATTERN)
    network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    geometry_crs: Literal["EPSG:4326"] = "EPSG:4326"
    distance_crs: Literal["EPSG:27700"] = "EPSG:27700"
    pyproj_version: str = Field(min_length=1, max_length=40)
    proj_version: str = Field(min_length=1, max_length=40)
    licence_id: Literal["synthetic-test-data"] = "synthetic-test-data"
    publication_class: Literal["redistributable_derived"] = "redistributable_derived"
    evidence_class: Literal["synthetic_test_only"] = "synthetic_test_only"
    synthetic: Literal[True] = True
    reviewed_manchester_network: Literal[False] = False
    accepted_for_real_matching: Literal[False] = False

    @model_validator(mode="after")
    def validate_runtime(self) -> SyntheticSumoNetworkBinding:
        if self.pyproj_version != pyproj.__version__:
            raise ValueError("network binding must record the active pyproj version")
        if self.proj_version != pyproj.proj_version_str:
            raise ValueError("network binding must record the active PROJ version")
        return self


class Wgs84Coordinate(ManchesterMapMatchingModel):
    """One exact synthetic edge-shape coordinate."""

    longitude: Decimal = Field(ge=-180, le=180)
    latitude: Decimal = Field(ge=-90, le=90)


class SyntheticSumoEdgeGeometry(ManchesterMapMatchingModel):
    """One bounded directed synthetic SUMO-edge shape."""

    network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    edge_id: str = Field(pattern=_ID_PATTERN)
    road_class: str | None = Field(default=None, pattern=_ROAD_CLASS_PATTERN)
    shape: tuple[Wgs84Coordinate, ...] = Field(min_length=2, max_length=64)
    directed: Literal[True] = True
    geometry_crs: Literal["EPSG:4326"] = "EPSG:4326"
    synthetic: Literal[True] = True

    @model_validator(mode="after")
    def validate_shape(self) -> SyntheticSumoEdgeGeometry:
        if any(left == right for left, right in zip(self.shape, self.shape[1:], strict=False)):
            raise ValueError("edge shape cannot contain consecutive duplicate coordinates")
        return self


class SyntheticObservationMatchContext(ManchesterMapMatchingModel):
    """Optional evidenced matching features for one admitted synthetic point."""

    point_id: str = Field(pattern=_ID_PATTERN)
    spatial_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    direction_degrees: Decimal | None = Field(default=None, ge=0, lt=360)
    road_class: str | None = Field(default=None, pattern=_ROAD_CLASS_PATTERN)
    synthetic: Literal[True] = True


class SyntheticMapMatchRequest(ManchesterMapMatchingModel):
    """Complete bounded synthetic candidate request."""

    policy: SyntheticMapMatchingPolicy
    network: SyntheticSumoNetworkBinding
    spatial_report: SpatialAdmissionReport
    observations: tuple[SyntheticObservationMatchContext, ...] = Field(min_length=1, max_length=128)
    edges: tuple[SyntheticSumoEdgeGeometry, ...] = Field(min_length=1, max_length=128)
    synthetic: Literal[True] = True
    real_source_execution_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_request(self) -> SyntheticMapMatchRequest:
        if self.spatial_report.status != "available":
            raise ValueError("synthetic map matching requires a fully admitted spatial report")
        results = self.spatial_report.results
        if any(result.source != "synthetic" or result.status != "admitted" for result in results):
            raise ValueError("synthetic map matching accepts only admitted synthetic points")
        observation_ids = tuple(item.point_id for item in self.observations)
        if observation_ids != tuple(sorted(observation_ids)) or len(set(observation_ids)) != len(
            observation_ids
        ):
            raise ValueError("observation contexts must have sorted unique point IDs")
        result_by_id = {result.point_id: result for result in results}
        if set(observation_ids) != set(result_by_id):
            raise ValueError("observation contexts must exactly cover admitted spatial points")
        for observation in self.observations:
            if (
                observation.spatial_result_fingerprint
                != result_by_id[observation.point_id].fingerprint()
            ):
                raise ValueError("observation context must bind its spatial result")
        edge_ids = tuple(edge.edge_id for edge in self.edges)
        if edge_ids != tuple(sorted(edge_ids)) or len(set(edge_ids)) != len(edge_ids):
            raise ValueError("edge geometries must have sorted unique edge IDs")
        if any(edge.network_sha256 != self.network.network_sha256 for edge in self.edges):
            raise ValueError("every edge must bind the request network")
        return self


class SyntheticEdgeMatchCandidate(ManchesterMapMatchingModel):
    """One computed point/edge feature row; never an automatic identity."""

    point_id: str = Field(pattern=_ID_PATTERN)
    spatial_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    edge_id: str = Field(pattern=_ID_PATTERN)
    edge_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    nearest_segment_index: int = Field(ge=0)
    distance_m: Decimal = Field(ge=0)
    edge_bearing_degrees: Decimal = Field(ge=0, lt=360)
    direction_delta_degrees: Decimal | None = Field(default=None, ge=0, le=180)
    road_class_match: bool | None
    passes_distance: bool
    passes_direction: bool
    passes_road_class: bool
    eligible_under_synthetic_policy: bool
    reasons: tuple[CandidateReason, CandidateReason, CandidateReason]
    confidence: Literal["synthetic_rule_only"] = "synthetic_rule_only"
    manual_review_required: Literal[True] = True
    automatically_selected: Literal[False] = False
    identity_join_established: Literal[False] = False
    approved_for_manchester: Literal[False] = False

    @model_validator(mode="after")
    def validate_candidate(self) -> SyntheticEdgeMatchCandidate:
        expected = self.passes_distance and self.passes_direction and self.passes_road_class
        if self.eligible_under_synthetic_policy != expected:
            raise ValueError("synthetic eligibility must reconcile feature gates")
        return self


class SyntheticMapMatchCounts(ManchesterMapMatchingModel):
    """Complete point-by-edge reconciliation."""

    observations_seen: int = Field(ge=0)
    edges_seen: int = Field(ge=0)
    candidate_pairs_evaluated: int = Field(ge=0)
    eligible_pairs: int = Field(ge=0)
    observations_without_eligible_candidate: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_pair_count(self) -> SyntheticMapMatchCounts:
        if self.candidate_pairs_evaluated != self.observations_seen * self.edges_seen:
            raise ValueError("candidate pair count must be the complete Cartesian product")
        return self


class SyntheticMapMatchReport(ManchesterMapMatchingModel):
    """Deterministic synthetic-only candidates awaiting explicit review."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-map-matching-candidate-1.0"] = (
        "manchester-map-matching-candidate-1.0"
    )
    request: SyntheticMapMatchRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidates: tuple[SyntheticEdgeMatchCandidate, ...]
    counts: SyntheticMapMatchCounts
    status: Literal["synthetic_candidates_require_review"] = "synthetic_candidates_require_review"
    complete_reconciliation: Literal[True] = True
    manual_review_required: Literal[True] = True
    automatic_selection_performed: Literal[False] = False
    real_manchester_matching_available: Literal[False] = False
    confidence_classification_available: Literal[False] = False
    sumo_baseline_available: Literal[False] = False
    observation_to_demand_conversion_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> SyntheticMapMatchReport:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint must bind the embedded request")
        expected_candidates = _compute_candidates(self.request)
        if self.candidates != expected_candidates:
            raise ValueError("candidate rows must match deterministic geometry evaluation")
        expected_counts = _candidate_counts(self.request, expected_candidates)
        if self.counts != expected_counts:
            raise ValueError("candidate counts must reconcile the computed rows")
        return self


class SyntheticMapMatchReviewDecision(ManchesterMapMatchingModel):
    """One explicit analyst decision over synthetic candidate evidence."""

    point_id: str = Field(pattern=_ID_PATTERN)
    outcome: Literal["candidate_selected", "all_candidates_rejected"]
    candidate_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: ReviewReason
    reviewer_role: Literal["analyst"] = "analyst"
    synthetic: Literal[True] = True

    @model_validator(mode="after")
    def validate_decision(self) -> SyntheticMapMatchReviewDecision:
        selected = self.outcome == "candidate_selected"
        if selected != (self.candidate_fingerprint is not None):
            raise ValueError("selected decisions must carry exactly one candidate fingerprint")
        if selected != (self.reason == "SYNTHETIC_FIXTURE_SELECTION"):
            raise ValueError("review reason must match selection status")
        return self


class SyntheticMapMatchReview(ManchesterMapMatchingModel):
    """Complete synthetic review record that still cannot create a baseline."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: tuple[SyntheticMapMatchReviewDecision, ...]
    observations_reviewed: int = Field(ge=0)
    candidates_selected: int = Field(ge=0)
    observations_rejected: int = Field(ge=0)
    complete_manual_review: Literal[True] = True
    synthetic: Literal[True] = True
    accepted_real_map_match: Literal[False] = False
    sumo_baseline_available: Literal[False] = False
    calibration_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_counts(self) -> SyntheticMapMatchReview:
        selected = sum(item.outcome == "candidate_selected" for item in self.decisions)
        if self.observations_reviewed != len(self.decisions):
            raise ValueError("reviewed observation count must match decisions")
        if self.candidates_selected != selected:
            raise ValueError("selected candidate count must match decisions")
        if self.observations_rejected != len(self.decisions) - selected:
            raise ValueError("rejected observation count must match decisions")
        return self


def current_map_matching_preflight() -> ManchesterMapMatchingPreflight:
    """Return the exact current fail-closed real-source availability."""

    return ManchesterMapMatchingPreflight(blockers=_REAL_BLOCKERS)


def build_synthetic_network_binding(
    network_id: str, network_sha256: str
) -> SyntheticSumoNetworkBinding:
    """Build a runtime-bound identity for a clearly synthetic network fixture."""

    return SyntheticSumoNetworkBinding(
        network_id=network_id,
        network_sha256=network_sha256,
        pyproj_version=pyproj.__version__,
        proj_version=pyproj.proj_version_str,
    )


def evaluate_synthetic_map_matches(request: SyntheticMapMatchRequest) -> SyntheticMapMatchReport:
    """Compute all bounded synthetic point/edge feature pairs without selection."""

    candidates = _compute_candidates(request)
    return SyntheticMapMatchReport(
        request=request,
        request_fingerprint=request.fingerprint(),
        candidates=candidates,
        counts=_candidate_counts(request, candidates),
    )


def record_synthetic_map_match_review(
    report: SyntheticMapMatchReport,
    decisions: Sequence[SyntheticMapMatchReviewDecision],
) -> SyntheticMapMatchReview:
    """Record one complete analyst review without creating a real baseline."""

    ordered = tuple(sorted(decisions, key=lambda item: item.point_id))
    point_ids = tuple(item.point_id for item in ordered)
    expected_ids = tuple(item.point_id for item in report.request.observations)
    if point_ids != expected_ids or len(set(point_ids)) != len(point_ids):
        raise ManchesterMapMatchingError(
            "INCOMPLETE_REVIEW",
            "review decisions must cover every observation exactly once",
        )
    candidates = {candidate.fingerprint(): candidate for candidate in report.candidates}
    for decision in ordered:
        if decision.candidate_fingerprint is None:
            continue
        candidate = candidates.get(decision.candidate_fingerprint)
        if candidate is None or candidate.point_id != decision.point_id:
            raise ManchesterMapMatchingError(
                "UNKNOWN_CANDIDATE",
                "selected candidate must belong to the reviewed observation and report",
            )
        if not candidate.eligible_under_synthetic_policy:
            raise ManchesterMapMatchingError(
                "INELIGIBLE_CANDIDATE",
                "synthetic review cannot select a candidate that failed its declared policy",
            )
    selected = sum(item.outcome == "candidate_selected" for item in ordered)
    return SyntheticMapMatchReview(
        report_fingerprint=report.fingerprint(),
        decisions=ordered,
        observations_reviewed=len(ordered),
        candidates_selected=selected,
        observations_rejected=len(ordered) - selected,
    )


def _compute_candidates(
    request: SyntheticMapMatchRequest,
) -> tuple[SyntheticEdgeMatchCandidate, ...]:
    result_by_id = {result.point_id: result for result in request.spatial_report.results}
    candidates: list[SyntheticEdgeMatchCandidate] = []
    for observation in request.observations:
        spatial_result = result_by_id[observation.point_id]
        point_xy = _project_spatial_result(spatial_result)
        for edge in request.edges:
            distance, segment_index, bearing = _nearest_edge_feature(point_xy, edge)
            distance_m = _decimal(distance, _DISTANCE_QUANTUM)
            bearing_degrees = _angle_decimal(bearing)
            direction_delta = (
                None
                if observation.direction_degrees is None
                else _angle_decimal(_direction_delta(float(observation.direction_degrees), bearing))
            )
            passes_distance = distance_m <= request.policy.max_distance_m
            passes_direction = (
                direction_delta is None
                or direction_delta <= request.policy.max_direction_delta_degrees
            )
            road_class_match = _road_class_match(observation, edge, request.policy)
            passes_road_class = road_class_match is not False
            distance_reason: CandidateReason = (
                "DISTANCE_WITHIN_THRESHOLD" if passes_distance else "DISTANCE_OUTSIDE_THRESHOLD"
            )
            reasons: tuple[CandidateReason, CandidateReason, CandidateReason] = (
                distance_reason,
                _direction_reason(direction_delta, passes_direction),
                _road_class_reason(
                    road_class_match,
                    request.policy.require_road_class_match,
                    observation.road_class,
                    edge.road_class,
                ),
            )
            candidates.append(
                SyntheticEdgeMatchCandidate(
                    point_id=observation.point_id,
                    spatial_result_fingerprint=spatial_result.fingerprint(),
                    edge_id=edge.edge_id,
                    edge_fingerprint=edge.fingerprint(),
                    nearest_segment_index=segment_index,
                    distance_m=distance_m,
                    edge_bearing_degrees=bearing_degrees,
                    direction_delta_degrees=direction_delta,
                    road_class_match=road_class_match,
                    passes_distance=passes_distance,
                    passes_direction=passes_direction,
                    passes_road_class=passes_road_class,
                    eligible_under_synthetic_policy=(
                        passes_distance and passes_direction and passes_road_class
                    ),
                    reasons=reasons,
                )
            )
    return tuple(
        sorted(candidates, key=lambda item: (item.point_id, item.distance_m, item.edge_id))
    )


def _candidate_counts(
    request: SyntheticMapMatchRequest,
    candidates: Sequence[SyntheticEdgeMatchCandidate],
) -> SyntheticMapMatchCounts:
    eligible_points = {
        candidate.point_id for candidate in candidates if candidate.eligible_under_synthetic_policy
    }
    return SyntheticMapMatchCounts(
        observations_seen=len(request.observations),
        edges_seen=len(request.edges),
        candidate_pairs_evaluated=len(candidates),
        eligible_pairs=sum(item.eligible_under_synthetic_policy for item in candidates),
        observations_without_eligible_candidate=len(request.observations) - len(eligible_points),
    )


def _project_spatial_result(result: SpatialAdmissionResult) -> tuple[float, float]:
    if result.longitude is None or result.latitude is None:
        raise ManchesterMapMatchingError(
            "SPATIAL_RESULT_UNAVAILABLE", "admitted synthetic point has no target coordinates"
        )
    return _distance_transformer().transform(float(result.longitude), float(result.latitude))


def _nearest_edge_feature(
    point_xy: tuple[float, float], edge: SyntheticSumoEdgeGeometry
) -> tuple[float, int, float]:
    projected = tuple(
        _distance_transformer().transform(float(point.longitude), float(point.latitude))
        for point in edge.shape
    )
    best: tuple[float, int, float] | None = None
    for index, (start, end) in enumerate(zip(projected, projected[1:], strict=False)):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length_squared = dx * dx + dy * dy
        if length_squared == 0:
            continue
        offset_x = point_xy[0] - start[0]
        offset_y = point_xy[1] - start[1]
        fraction = max(0.0, min(1.0, (offset_x * dx + offset_y * dy) / length_squared))
        nearest_x = start[0] + fraction * dx
        nearest_y = start[1] + fraction * dy
        distance = math.hypot(point_xy[0] - nearest_x, point_xy[1] - nearest_y)
        bearing = math.degrees(math.atan2(dx, dy)) % 360.0
        candidate = (distance, index, bearing)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        raise ManchesterMapMatchingError(
            "EDGE_GEOMETRY_DEGENERATE", "edge has no non-degenerate projected segment"
        )
    return best


def _road_class_match(
    observation: SyntheticObservationMatchContext,
    edge: SyntheticSumoEdgeGeometry,
    policy: SyntheticMapMatchingPolicy,
) -> bool | None:
    if not policy.require_road_class_match:
        return None
    if observation.road_class is None or edge.road_class is None:
        return False
    return observation.road_class == edge.road_class


def _direction_reason(direction_delta: Decimal | None, passes_direction: bool) -> CandidateReason:
    if direction_delta is None:
        return "DIRECTION_NOT_PROVIDED"
    if passes_direction:
        return "DIRECTION_WITHIN_THRESHOLD"
    return "DIRECTION_OUTSIDE_THRESHOLD"


def _road_class_reason(
    road_class_match: bool | None,
    required: bool,
    observation_class: str | None,
    edge_class: str | None,
) -> CandidateReason:
    if not required:
        return "ROAD_CLASS_NOT_REQUIRED"
    if observation_class is None or edge_class is None:
        return "ROAD_CLASS_MISSING"
    if road_class_match:
        return "ROAD_CLASS_MATCH"
    return "ROAD_CLASS_MISMATCH"


def _direction_delta(first: float, second: float) -> float:
    difference = abs(first - second) % 360.0
    return min(difference, 360.0 - difference)


def _decimal(value: float, quantum: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)


def _angle_decimal(value: float) -> Decimal:
    rounded = _decimal(value % 360.0, _ANGLE_QUANTUM)
    return Decimal("0.000") if rounded == Decimal("360.000") else rounded


@lru_cache(maxsize=1)
def _distance_transformer() -> Transformer:
    return Transformer.from_crs(_TARGET_CRS, _DISTANCE_CRS, always_xy=True)
