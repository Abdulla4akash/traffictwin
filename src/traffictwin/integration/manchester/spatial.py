"""MAN-07 candidate: deterministic geographic point admission.

The service validates source CRS evidence, source-specific scope evidence, and
dual-coordinate agreement before a point can enter a geographic map layer. It
does not perform map matching, proximity joins, boundary inference, or network
access. Unknown source frames remain available only to non-geographic views.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal
from functools import lru_cache
from typing import Literal, TypeAlias

import pyproj
from pydantic import Field, model_validator
from pyproj import Transformer

from traffictwin.integration.manchester.bods import LiveTransitVehicleObservation
from traffictwin.integration.manchester.dft import (
    DftAadfRecord,
    DftCountPointRecord,
    DftRawCountRecord,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.randy import RandyManchesterBridgeReport
from traffictwin.integration.manchester.tfgm_signals import (
    COORDINATE_TOLERANCE_METRES,
    TfgmSignalLocation,
)
from traffictwin.integration.manchester.webtris import WebtrisSiteRecord

MANCHESTER_SPATIAL_SCHEMA_VERSION = "1.0"
MANCHESTER_SPATIAL_METHOD_VERSION = "manchester-spatial-admission-1.0"
MANCHESTER_SPATIAL_CAPABILITY_ID = "MAN-07"
TARGET_CRS = "EPSG:4326"
OSGB_CRS = "EPSG:27700"

SpatialSource: TypeAlias = Literal[
    "dft",
    "webtris",
    "tfgm_signals",
    "bods_siri_vm",
    "randy_tos",
    "sumo_vec",
    "analysis_rsu",
    "synthetic",
]
CoordinateEvidenceKind: TypeAlias = Literal[
    "wgs84",
    "bng_and_wgs84",
    "bng_only",
    "incomplete",
    "unknown",
]
GeographicScope: TypeAlias = Literal[
    "manchester_local_authority",
    "strategic_approaches",
    "greater_manchester",
    "request_bounding_box",
    "declared_network",
    "synthetic",
    "unavailable",
]
ScopeBasis: TypeAlias = Literal[
    "audited_dft_authority_e08000003",
    "selected_webtris_strategic_site",
    "tfgm_greater_manchester_authority",
    "bods_request_bounds",
    "declared_network_projection",
    "synthetic_contract",
    "none",
]
GeometryMeaning: TypeAlias = Literal[
    "road_count_point",
    "strategic_road_detector",
    "traffic_signal_site",
    "transit_vehicle_position",
    "simulation_position",
    "analysis_site",
    "synthetic_point",
    "unavailable",
]
SpatialAdmissionReason: TypeAlias = Literal[
    "direct_wgs84_admitted",
    "dual_coordinates_admitted",
    "source_record_inactive",
    "source_coordinates_missing",
    "unknown_source_crs",
    "dual_coordinate_evidence_required",
    "dual_coordinate_mismatch",
    "scope_evidence_missing",
    "scope_basis_mismatch",
    "source_semantics_mismatch",
    "no_evidenced_coordinate_projection",
]

_POINT_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$"


class ManchesterSpatialError(ValueError):
    """Raised when a caller supplies duplicate or contradictory input lineage."""


class ManchesterSpatialModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-07 spatial artifacts."""


class SpatialAdmissionPolicy(ManchesterSpatialModel):
    """Frozen source-specific CRS, scope, and transformation policy."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    method_version: Literal["manchester-spatial-admission-1.0"] = "manchester-spatial-admission-1.0"
    source: SpatialSource
    source_crs: tuple[Literal["EPSG:27700", "EPSG:4326"], ...]
    accepted_coordinate_kinds: tuple[CoordinateEvidenceKind, ...]
    required_scope: GeographicScope
    required_scope_basis: ScopeBasis
    required_geometry_meaning: GeometryMeaning
    target_crs: Literal["EPSG:4326"] = "EPSG:4326"
    dual_coordinate_tolerance_m: Decimal | None = Field(default=None, gt=0)
    transformer_method: Literal[
        "identity_wgs84",
        "epsg27700_to_epsg4326_validation",
        "unavailable",
    ]
    pyproj_version: str = Field(min_length=1, max_length=40)
    proj_version: str = Field(min_length=1, max_length=40)
    always_xy: Literal[True] = True
    boundary_inferred_from_coordinates: Literal[False] = False
    visual_proximity_establishes_identity: Literal[False] = False

    @model_validator(mode="after")
    def validate_policy(self) -> SpatialAdmissionPolicy:
        expected_by_source: dict[
            SpatialSource,
            tuple[
                tuple[Literal["EPSG:27700", "EPSG:4326"], ...],
                tuple[CoordinateEvidenceKind, ...],
                GeographicScope,
                ScopeBasis,
                GeometryMeaning,
                Literal[
                    "identity_wgs84",
                    "epsg27700_to_epsg4326_validation",
                    "unavailable",
                ],
                Decimal | None,
            ],
        ] = {
            "dft": (
                ("EPSG:27700", "EPSG:4326"),
                ("bng_and_wgs84",),
                "manchester_local_authority",
                "audited_dft_authority_e08000003",
                "road_count_point",
                "epsg27700_to_epsg4326_validation",
                Decimal(str(COORDINATE_TOLERANCE_METRES)),
            ),
            "tfgm_signals": (
                ("EPSG:27700", "EPSG:4326"),
                ("bng_and_wgs84",),
                "greater_manchester",
                "tfgm_greater_manchester_authority",
                "traffic_signal_site",
                "epsg27700_to_epsg4326_validation",
                Decimal(str(COORDINATE_TOLERANCE_METRES)),
            ),
            "webtris": (
                ("EPSG:4326",),
                ("wgs84",),
                "strategic_approaches",
                "selected_webtris_strategic_site",
                "strategic_road_detector",
                "identity_wgs84",
                None,
            ),
            "bods_siri_vm": (
                ("EPSG:4326",),
                ("wgs84",),
                "request_bounding_box",
                "bods_request_bounds",
                "transit_vehicle_position",
                "identity_wgs84",
                None,
            ),
            "synthetic": (
                ("EPSG:4326",),
                ("wgs84",),
                "synthetic",
                "synthetic_contract",
                "synthetic_point",
                "identity_wgs84",
                None,
            ),
            "randy_tos": ((), (), "unavailable", "none", "unavailable", "unavailable", None),
            "sumo_vec": (
                (),
                (),
                "unavailable",
                "none",
                "simulation_position",
                "unavailable",
                None,
            ),
            "analysis_rsu": (
                (),
                (),
                "unavailable",
                "none",
                "analysis_site",
                "unavailable",
                None,
            ),
        }
        observed = (
            self.source_crs,
            self.accepted_coordinate_kinds,
            self.required_scope,
            self.required_scope_basis,
            self.required_geometry_meaning,
            self.transformer_method,
            self.dual_coordinate_tolerance_m,
        )
        if observed != expected_by_source[self.source]:
            raise ValueError("source policy must match the frozen MAN-07 policy matrix")
        if not self.accepted_coordinate_kinds:
            if (
                self.source_crs
                or self.transformer_method != "unavailable"
                or self.dual_coordinate_tolerance_m is not None
            ):
                raise ValueError("sources without admitted coordinates need unavailable transform")
        elif "bng_and_wgs84" in self.accepted_coordinate_kinds:
            if (
                self.source_crs != ("EPSG:27700", "EPSG:4326")
                or self.accepted_coordinate_kinds != ("bng_and_wgs84",)
                or self.transformer_method != "epsg27700_to_epsg4326_validation"
                or self.dual_coordinate_tolerance_m is None
            ):
                raise ValueError(
                    "dual-coordinate sources require the versioned validation transform"
                )
        elif (
            self.source_crs != ("EPSG:4326",)
            or self.accepted_coordinate_kinds != ("wgs84",)
            or self.transformer_method != "identity_wgs84"
            or self.dual_coordinate_tolerance_m is not None
        ):
            raise ValueError("direct sources require the exact WGS84 identity policy")
        return self


class ManchesterSpatialPointEvidence(ManchesterSpatialModel):
    """One source point with original coordinates and explicit scope evidence."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    source: SpatialSource
    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    point_id: str = Field(pattern=_POINT_ID_PATTERN)
    coordinate_kind: CoordinateEvidenceKind
    easting_epsg27700: Decimal | None = Field(default=None, ge=0, le=1_000_000)
    northing_epsg27700: Decimal | None = Field(default=None, ge=0, le=2_000_000)
    longitude_epsg4326: Decimal | None = Field(default=None, ge=-180, le=180)
    latitude_epsg4326: Decimal | None = Field(default=None, ge=-90, le=90)
    geographic_scope: GeographicScope
    scope_basis: ScopeBasis
    scope_evidence_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    geometry_meaning: GeometryMeaning
    source_record_state: Literal["eligible", "inactive", "unavailable"]
    coordinate_uncertainty_m: Decimal | None = Field(default=None, ge=0)
    uncertainty_basis: Literal["source_not_stated", "caller_declared"]
    synthetic: bool
    source_values_preserved: Literal[True] = True
    identity_join_claimed: Literal[False] = False

    @model_validator(mode="after")
    def validate_evidence(self) -> ManchesterSpatialPointEvidence:
        bng_values = (self.easting_epsg27700, self.northing_epsg27700)
        wgs_values = (self.longitude_epsg4326, self.latitude_epsg4326)
        bng_complete = all(value is not None for value in bng_values)
        wgs_complete = all(value is not None for value in wgs_values)
        any_bng = any(value is not None for value in bng_values)
        any_wgs = any(value is not None for value in wgs_values)
        expected_kind: CoordinateEvidenceKind
        if bng_complete and wgs_complete:
            expected_kind = "bng_and_wgs84"
        elif bng_complete and not any_wgs:
            expected_kind = "bng_only"
        elif wgs_complete and not any_bng:
            expected_kind = "wgs84"
        elif any_bng or any_wgs:
            expected_kind = "incomplete"
        else:
            expected_kind = "unknown"
        if self.coordinate_kind != expected_kind:
            raise ValueError("coordinate kind must exactly match supplied source values")
        no_scope = self.scope_basis == "none"
        if no_scope != (self.scope_evidence_fingerprint is None):
            raise ValueError("scope evidence fingerprint and scope basis must coexist")
        if no_scope != (self.geographic_scope == "unavailable"):
            raise ValueError("unavailable scope must use the none basis")
        declared_uncertainty = self.coordinate_uncertainty_m is not None
        if declared_uncertainty != (self.uncertainty_basis == "caller_declared"):
            raise ValueError("coordinate uncertainty and its basis must coexist")
        if self.source == "synthetic" and not self.synthetic:
            raise ValueError("synthetic spatial source must remain labelled synthetic")
        return self


class SpatialCoordinateBounds(ManchesterSpatialModel):
    """Exact target-coordinate envelope for admitted points."""

    min_longitude: Decimal = Field(ge=-180, le=180)
    min_latitude: Decimal = Field(ge=-90, le=90)
    max_longitude: Decimal = Field(ge=-180, le=180)
    max_latitude: Decimal = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def validate_bounds(self) -> SpatialCoordinateBounds:
        if self.min_longitude > self.max_longitude or self.min_latitude > self.max_latitude:
            raise ValueError("coordinate bounds are reversed")
        return self


class SpatialAdmissionResult(ManchesterSpatialModel):
    """One deterministic map-admission or exclusion decision."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    method_version: Literal["manchester-spatial-admission-1.0"] = "manchester-spatial-admission-1.0"
    evidence_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    point_id: str = Field(pattern=_POINT_ID_PATTERN)
    source: SpatialSource
    policy: SpatialAdmissionPolicy
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["admitted", "excluded"]
    reason: SpatialAdmissionReason
    target_crs: Literal["EPSG:4326"] = "EPSG:4326"
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    target_bounds: SpatialCoordinateBounds | None = None
    coordinate_error_m: Decimal | None = Field(default=None, ge=0)
    transformation_used_for_validation: bool
    target_uses_declared_source_wgs84: bool
    geographic_scope: GeographicScope
    scope_basis: ScopeBasis
    geometry_meaning: GeometryMeaning
    coordinate_uncertainty_m: Decimal | None = Field(default=None, ge=0)
    map_rendering_available: bool
    source_values_preserved: Literal[True] = True
    boundary_inferred_from_coordinates: Literal[False] = False
    identity_join_established: Literal[False] = False
    visual_proximity_join_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> SpatialAdmissionResult:
        if self.policy.source != self.source:
            raise ValueError("result source must match the embedded source policy")
        if self.policy_fingerprint != self.policy.fingerprint():
            raise ValueError("policy fingerprint must match the embedded policy")
        admitted = self.status == "admitted"
        if admitted != self.map_rendering_available:
            raise ValueError("map availability must match admission status")
        has_target = self.longitude is not None and self.latitude is not None
        if admitted != has_target or admitted != (self.target_bounds is not None):
            raise ValueError("only admitted points may carry target coordinates and bounds")
        if admitted:
            if self.longitude is None or self.latitude is None:
                raise ValueError("admitted point is missing target coordinates")
            expected_bounds = SpatialCoordinateBounds(
                min_longitude=self.longitude,
                min_latitude=self.latitude,
                max_longitude=self.longitude,
                max_latitude=self.latitude,
            )
            if self.target_bounds != expected_bounds:
                raise ValueError("point bounds must exactly match the admitted coordinate")
            if (
                self.geographic_scope != self.policy.required_scope
                or self.scope_basis != self.policy.required_scope_basis
                or self.geometry_meaning != self.policy.required_geometry_meaning
            ):
                raise ValueError("admitted result must match the frozen source semantics")
        admitted_reasons = {"direct_wgs84_admitted", "dual_coordinates_admitted"}
        if admitted != (self.reason in admitted_reasons):
            raise ValueError("admission status must match the deterministic reason")
        if self.reason == "dual_coordinates_admitted":
            tolerance = self.policy.dual_coordinate_tolerance_m
            if (
                self.coordinate_error_m is None
                or tolerance is None
                or self.coordinate_error_m > tolerance
                or not self.transformation_used_for_validation
            ):
                raise ValueError("dual admission requires an in-tolerance transform check")
        if self.reason == "direct_wgs84_admitted" and (
            self.coordinate_error_m is not None or self.transformation_used_for_validation
        ):
            raise ValueError("direct WGS84 admission cannot claim a transform check")
        if self.reason == "dual_coordinate_mismatch":
            tolerance = self.policy.dual_coordinate_tolerance_m
            if (
                self.coordinate_error_m is None
                or tolerance is None
                or self.coordinate_error_m <= tolerance
                or not self.transformation_used_for_validation
            ):
                raise ValueError("dual-coordinate mismatch needs an out-of-tolerance check")
        if self.reason not in {"dual_coordinates_admitted", "dual_coordinate_mismatch"} and (
            self.coordinate_error_m is not None or self.transformation_used_for_validation
        ):
            raise ValueError("only dual-coordinate decisions may carry transform evidence")
        if self.target_uses_declared_source_wgs84 != admitted:
            raise ValueError("admitted target must retain the declared source WGS84 values")
        return self


class SpatialAdmissionCounts(ManchesterSpatialModel):
    """Complete batch accounting by decision family."""

    inputs_seen: int = Field(ge=0)
    admitted: int = Field(ge=0)
    excluded: int = Field(ge=0)
    coordinate_exclusions: int = Field(ge=0)
    scope_exclusions: int = Field(ge=0)
    source_state_exclusions: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> SpatialAdmissionCounts:
        if self.inputs_seen != self.admitted + self.excluded:
            raise ValueError("spatial counts must reconcile to inputs")
        if self.excluded != (
            self.coordinate_exclusions + self.scope_exclusions + self.source_state_exclusions
        ):
            raise ValueError("spatial exclusion families must reconcile")
        return self


class SpatialAdmissionReport(ManchesterSpatialModel):
    """Deterministic, order-independent, completely reconciled spatial report."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    method_version: Literal["manchester-spatial-admission-1.0"] = "manchester-spatial-admission-1.0"
    input_evidence_fingerprints: tuple[str, ...]
    status: Literal["available", "partial", "unavailable"]
    counts: SpatialAdmissionCounts
    results: tuple[SpatialAdmissionResult, ...]
    complete_reconciliation: Literal[True] = True
    cross_source_identity_join_performed: Literal[False] = False
    visual_proximity_join_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> SpatialAdmissionReport:
        if tuple(sorted(self.input_evidence_fingerprints)) != self.input_evidence_fingerprints:
            raise ValueError("input fingerprints must be sorted")
        if len(set(self.input_evidence_fingerprints)) != len(self.input_evidence_fingerprints):
            raise ValueError("input fingerprints must be unique")
        result_fingerprints = tuple(result.evidence_fingerprint for result in self.results)
        if result_fingerprints != self.input_evidence_fingerprints:
            raise ValueError("every sorted input must have exactly one ordered spatial result")
        admitted = sum(result.status == "admitted" for result in self.results)
        scope_reasons = {
            "scope_evidence_missing",
            "scope_basis_mismatch",
            "source_semantics_mismatch",
        }
        source_state_reasons = {
            "source_record_inactive",
            "no_evidenced_coordinate_projection",
        }
        scope_exclusions = sum(result.reason in scope_reasons for result in self.results)
        source_state_exclusions = sum(
            result.reason in source_state_reasons for result in self.results
        )
        excluded = len(self.results) - admitted
        if self.counts != SpatialAdmissionCounts(
            inputs_seen=len(self.results),
            admitted=admitted,
            excluded=excluded,
            coordinate_exclusions=excluded - scope_exclusions - source_state_exclusions,
            scope_exclusions=scope_exclusions,
            source_state_exclusions=source_state_exclusions,
        ):
            raise ValueError("report counts must match results")
        expected_status = (
            "unavailable"
            if not admitted
            else "available"
            if admitted == len(self.results)
            else "partial"
        )
        if self.status != expected_status:
            raise ValueError("report status must match admitted and excluded results")
        return self


def source_spatial_policy(source: SpatialSource) -> SpatialAdmissionPolicy:
    """Return the exact v1 policy for a source family and current projection runtime."""

    if source == "dft":
        return SpatialAdmissionPolicy(
            source=source,
            source_crs=("EPSG:27700", "EPSG:4326"),
            accepted_coordinate_kinds=("bng_and_wgs84",),
            required_scope="manchester_local_authority",
            required_scope_basis="audited_dft_authority_e08000003",
            required_geometry_meaning="road_count_point",
            dual_coordinate_tolerance_m=Decimal(str(COORDINATE_TOLERANCE_METRES)),
            transformer_method="epsg27700_to_epsg4326_validation",
            pyproj_version=pyproj.__version__,
            proj_version=pyproj.proj_version_str,
        )
    if source == "tfgm_signals":
        return SpatialAdmissionPolicy(
            source=source,
            source_crs=("EPSG:27700", "EPSG:4326"),
            accepted_coordinate_kinds=("bng_and_wgs84",),
            required_scope="greater_manchester",
            required_scope_basis="tfgm_greater_manchester_authority",
            required_geometry_meaning="traffic_signal_site",
            dual_coordinate_tolerance_m=Decimal(str(COORDINATE_TOLERANCE_METRES)),
            transformer_method="epsg27700_to_epsg4326_validation",
            pyproj_version=pyproj.__version__,
            proj_version=pyproj.proj_version_str,
        )
    if source == "webtris":
        return SpatialAdmissionPolicy(
            source=source,
            source_crs=("EPSG:4326",),
            accepted_coordinate_kinds=("wgs84",),
            required_scope="strategic_approaches",
            required_scope_basis="selected_webtris_strategic_site",
            required_geometry_meaning="strategic_road_detector",
            transformer_method="identity_wgs84",
            pyproj_version=pyproj.__version__,
            proj_version=pyproj.proj_version_str,
        )
    if source == "bods_siri_vm":
        return SpatialAdmissionPolicy(
            source=source,
            source_crs=("EPSG:4326",),
            accepted_coordinate_kinds=("wgs84",),
            required_scope="request_bounding_box",
            required_scope_basis="bods_request_bounds",
            required_geometry_meaning="transit_vehicle_position",
            transformer_method="identity_wgs84",
            pyproj_version=pyproj.__version__,
            proj_version=pyproj.proj_version_str,
        )
    if source == "synthetic":
        return SpatialAdmissionPolicy(
            source=source,
            source_crs=("EPSG:4326",),
            accepted_coordinate_kinds=("wgs84",),
            required_scope="synthetic",
            required_scope_basis="synthetic_contract",
            required_geometry_meaning="synthetic_point",
            transformer_method="identity_wgs84",
            pyproj_version=pyproj.__version__,
            proj_version=pyproj.proj_version_str,
        )
    required_scope: GeographicScope = "unavailable"
    required_basis: ScopeBasis = "none"
    geometry_by_source: dict[SpatialSource, GeometryMeaning] = {
        "randy_tos": "unavailable",
        "sumo_vec": "simulation_position",
        "analysis_rsu": "analysis_site",
        "dft": "road_count_point",
        "webtris": "strategic_road_detector",
        "tfgm_signals": "traffic_signal_site",
        "bods_siri_vm": "transit_vehicle_position",
        "synthetic": "synthetic_point",
    }
    return SpatialAdmissionPolicy(
        source=source,
        source_crs=(),
        accepted_coordinate_kinds=(),
        required_scope=required_scope,
        required_scope_basis=required_basis,
        required_geometry_meaning=geometry_by_source[source],
        transformer_method="unavailable",
        pyproj_version=pyproj.__version__,
        proj_version=pyproj.proj_version_str,
    )


def spatial_policy_catalogue() -> tuple[SpatialAdmissionPolicy, ...]:
    """Return the complete source policy inventory in stable source order."""

    sources: tuple[SpatialSource, ...] = (
        "analysis_rsu",
        "bods_siri_vm",
        "dft",
        "randy_tos",
        "sumo_vec",
        "synthetic",
        "tfgm_signals",
        "webtris",
    )
    return tuple(source_spatial_policy(source) for source in sources)


def evaluate_spatial_admission(
    evidence: ManchesterSpatialPointEvidence,
) -> SpatialAdmissionResult:
    """Evaluate one source point without boundary inference or proximity joins."""

    policy = source_spatial_policy(evidence.source)

    def result(
        status: Literal["admitted", "excluded"],
        reason: SpatialAdmissionReason,
        *,
        longitude: Decimal | None = None,
        latitude: Decimal | None = None,
        error_m: Decimal | None = None,
        transformed: bool = False,
    ) -> SpatialAdmissionResult:
        admitted = status == "admitted"
        bounds = (
            SpatialCoordinateBounds(
                min_longitude=longitude,
                min_latitude=latitude,
                max_longitude=longitude,
                max_latitude=latitude,
            )
            if admitted and longitude is not None and latitude is not None
            else None
        )
        return SpatialAdmissionResult(
            evidence_fingerprint=evidence.fingerprint(),
            source_record_fingerprint=evidence.source_record_fingerprint,
            point_id=evidence.point_id,
            source=evidence.source,
            policy=policy,
            policy_fingerprint=policy.fingerprint(),
            status=status,
            reason=reason,
            longitude=longitude,
            latitude=latitude,
            target_bounds=bounds,
            coordinate_error_m=error_m,
            transformation_used_for_validation=transformed,
            target_uses_declared_source_wgs84=admitted,
            geographic_scope=evidence.geographic_scope,
            scope_basis=evidence.scope_basis,
            geometry_meaning=evidence.geometry_meaning,
            coordinate_uncertainty_m=evidence.coordinate_uncertainty_m,
            map_rendering_available=admitted,
        )

    if evidence.source_record_state == "inactive":
        return result("excluded", "source_record_inactive")
    if evidence.source_record_state == "unavailable":
        return result("excluded", "no_evidenced_coordinate_projection")
    if not policy.accepted_coordinate_kinds:
        return result("excluded", "no_evidenced_coordinate_projection")
    if evidence.coordinate_kind == "unknown":
        return result("excluded", "unknown_source_crs")
    if evidence.coordinate_kind == "incomplete":
        return result("excluded", "source_coordinates_missing")
    if evidence.coordinate_kind not in policy.accepted_coordinate_kinds:
        return result("excluded", "dual_coordinate_evidence_required")
    if evidence.scope_evidence_fingerprint is None:
        return result("excluded", "scope_evidence_missing")
    if (
        evidence.geographic_scope != policy.required_scope
        or evidence.scope_basis != policy.required_scope_basis
    ):
        return result("excluded", "scope_basis_mismatch")
    if evidence.geometry_meaning != policy.required_geometry_meaning:
        return result("excluded", "source_semantics_mismatch")
    longitude = evidence.longitude_epsg4326
    latitude = evidence.latitude_epsg4326
    if longitude is None or latitude is None:
        return result("excluded", "source_coordinates_missing")
    if evidence.coordinate_kind == "wgs84":
        return result(
            "admitted",
            "direct_wgs84_admitted",
            longitude=longitude,
            latitude=latitude,
        )
    easting = evidence.easting_epsg27700
    northing = evidence.northing_epsg27700
    if easting is None or northing is None:
        return result("excluded", "source_coordinates_missing")
    calculated_longitude, calculated_latitude = _osgb_to_wgs84().transform(
        float(easting), float(northing)
    )
    error = _coordinate_error_m(
        calculated_longitude,
        calculated_latitude,
        float(longitude),
        float(latitude),
    )
    error_decimal = Decimal(str(error))
    tolerance = policy.dual_coordinate_tolerance_m
    if tolerance is None or error_decimal > tolerance:
        return result(
            "excluded",
            "dual_coordinate_mismatch",
            error_m=error_decimal,
            transformed=True,
        )
    return result(
        "admitted",
        "dual_coordinates_admitted",
        longitude=longitude,
        latitude=latitude,
        error_m=error_decimal,
        transformed=True,
    )


def evaluate_spatial_batch(
    evidence_items: Sequence[ManchesterSpatialPointEvidence],
) -> SpatialAdmissionReport:
    """Evaluate a deterministic input set and reconcile every decision."""

    ordered = tuple(sorted(evidence_items, key=lambda item: item.fingerprint()))
    fingerprints = tuple(item.fingerprint() for item in ordered)
    if len(set(fingerprints)) != len(fingerprints):
        raise ManchesterSpatialError("duplicate spatial evidence is not admissible")
    source_records = tuple(item.source_record_fingerprint for item in ordered)
    if len(set(source_records)) != len(source_records):
        raise ManchesterSpatialError("one source record cannot be spatially evaluated twice")
    results = tuple(evaluate_spatial_admission(item) for item in ordered)
    admitted = sum(item.status == "admitted" for item in results)
    scope_reasons = {
        "scope_evidence_missing",
        "scope_basis_mismatch",
        "source_semantics_mismatch",
    }
    source_state_reasons = {
        "source_record_inactive",
        "no_evidenced_coordinate_projection",
    }
    scope_exclusions = sum(item.reason in scope_reasons for item in results)
    source_state_exclusions = sum(item.reason in source_state_reasons for item in results)
    excluded = len(results) - admitted
    counts = SpatialAdmissionCounts(
        inputs_seen=len(results),
        admitted=admitted,
        excluded=excluded,
        coordinate_exclusions=excluded - scope_exclusions - source_state_exclusions,
        scope_exclusions=scope_exclusions,
        source_state_exclusions=source_state_exclusions,
    )
    status: Literal["available", "partial", "unavailable"] = (
        "unavailable" if not admitted else "available" if admitted == len(results) else "partial"
    )
    return SpatialAdmissionReport(
        input_evidence_fingerprints=fingerprints,
        status=status,
        counts=counts,
        results=results,
    )


def dft_spatial_evidence(
    record: DftRawCountRecord | DftCountPointRecord | DftAadfRecord,
) -> ManchesterSpatialPointEvidence:
    """Preserve one Manchester-authority DfT count-point coordinate declaration."""

    return ManchesterSpatialPointEvidence(
        source="dft",
        source_record_fingerprint=record.fingerprint(),
        point_id=f"dft:{record.count_point_id}",
        coordinate_kind=_coordinate_kind(
            record.location.easting,
            record.location.northing,
            record.location.longitude,
            record.location.latitude,
        ),
        easting_epsg27700=record.location.easting,
        northing_epsg27700=record.location.northing,
        longitude_epsg4326=record.location.longitude,
        latitude_epsg4326=record.location.latitude,
        geographic_scope="manchester_local_authority",
        scope_basis="audited_dft_authority_e08000003",
        scope_evidence_fingerprint=record.fingerprint(),
        geometry_meaning="road_count_point",
        source_record_state="eligible",
        uncertainty_basis="source_not_stated",
        synthetic=record.source.synthetic,
    )


def webtris_spatial_evidence(
    record: WebtrisSiteRecord,
    *,
    selection_fingerprint: str,
) -> ManchesterSpatialPointEvidence:
    """Bind one WebTRIS site to an explicit selected strategic-site scope artifact."""

    return ManchesterSpatialPointEvidence(
        source="webtris",
        source_record_fingerprint=record.fingerprint(),
        point_id=f"webtris:{record.site_id}",
        coordinate_kind="wgs84",
        longitude_epsg4326=record.longitude,
        latitude_epsg4326=record.latitude,
        geographic_scope="strategic_approaches",
        scope_basis="selected_webtris_strategic_site",
        scope_evidence_fingerprint=selection_fingerprint,
        geometry_meaning="strategic_road_detector",
        source_record_state="eligible" if record.source_status == "Active" else "inactive",
        uncertainty_basis="source_not_stated",
        synthetic=record.source.synthetic,
    )


def tfgm_signal_spatial_evidence(
    record: TfgmSignalLocation,
) -> ManchesterSpatialPointEvidence:
    """Preserve dual TfGM coordinates and the audited GM-authority scope."""

    return ManchesterSpatialPointEvidence(
        source="tfgm_signals",
        source_record_fingerprint=record.fingerprint(),
        point_id=f"tfgm-signal:{record.fras_ref}",
        coordinate_kind="bng_and_wgs84",
        easting_epsg27700=Decimal(record.easting_epsg27700),
        northing_epsg27700=Decimal(record.northing_epsg27700),
        longitude_epsg4326=record.longitude_epsg4326,
        latitude_epsg4326=record.latitude_epsg4326,
        geographic_scope="greater_manchester",
        scope_basis="tfgm_greater_manchester_authority",
        scope_evidence_fingerprint=record.fingerprint(),
        geometry_meaning="traffic_signal_site",
        source_record_state="eligible",
        uncertainty_basis="source_not_stated",
        synthetic=record.source.synthetic,
    )


def bods_spatial_evidence(
    record: LiveTransitVehicleObservation,
    *,
    request_bounds_fingerprint: str,
) -> ManchesterSpatialPointEvidence:
    """Bind one bus position to the exact accepted request-bounds artifact."""

    return ManchesterSpatialPointEvidence(
        source="bods_siri_vm",
        source_record_fingerprint=record.fingerprint(),
        point_id=f"bods:{record.source.snapshot_id}:{record.activity_index}",
        coordinate_kind="wgs84",
        longitude_epsg4326=record.longitude,
        latitude_epsg4326=record.latitude,
        geographic_scope="request_bounding_box",
        scope_basis="bods_request_bounds",
        scope_evidence_fingerprint=request_bounds_fingerprint,
        geometry_meaning="transit_vehicle_position",
        source_record_state="eligible",
        uncertainty_basis="source_not_stated",
        synthetic=record.source.synthetic,
    )


def randy_spatial_evidence(
    report: RandyManchesterBridgeReport,
) -> ManchesterSpatialPointEvidence:
    """Represent the audited bridge's missing geographic projection without invention."""

    return ManchesterSpatialPointEvidence(
        source="randy_tos",
        source_record_fingerprint=report.fingerprint(),
        point_id="randy:vec11-sanitised-pack",
        coordinate_kind="unknown",
        geographic_scope="unavailable",
        scope_basis="none",
        geometry_meaning="unavailable",
        source_record_state="unavailable",
        uncertainty_basis="source_not_stated",
        synthetic=False,
    )


def _coordinate_kind(
    easting: Decimal | None,
    northing: Decimal | None,
    longitude: Decimal | None,
    latitude: Decimal | None,
) -> CoordinateEvidenceKind:
    bng_complete = easting is not None and northing is not None
    wgs_complete = longitude is not None and latitude is not None
    any_bng = easting is not None or northing is not None
    any_wgs = longitude is not None or latitude is not None
    if bng_complete and wgs_complete:
        return "bng_and_wgs84"
    if bng_complete and not any_wgs:
        return "bng_only"
    if wgs_complete and not any_bng:
        return "wgs84"
    if any_bng or any_wgs:
        return "incomplete"
    return "unknown"


def _coordinate_error_m(
    calculated_longitude: float,
    calculated_latitude: float,
    declared_longitude: float,
    declared_latitude: float,
) -> float:
    east_west_metres = (
        (calculated_longitude - declared_longitude)
        * 111_320
        * math.cos(math.radians(calculated_latitude))
    )
    north_south_metres = (calculated_latitude - declared_latitude) * 110_540
    return math.hypot(east_west_metres, north_south_metres)


@lru_cache(maxsize=1)
def _osgb_to_wgs84() -> Transformer:
    return Transformer.from_crs(OSGB_CRS, TARGET_CRS, always_xy=True)
