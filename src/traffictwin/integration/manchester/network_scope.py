"""Greater Manchester baseline scope, derived extract envelope, and DfT coverage.

Design Gate-D step 1 requires one bound Manchester SUMO network.  ADR-059
records the repository owner's 25 July 2026 decisions: Greater Manchester is
the single primary baseline scope and Manchester local authority is a
selectable sub-area filter rather than a second baseline network.

Three honesty boundaries are structural here rather than documentary:

1.  The packaged ONS boundary assets are BGC-generalised display geometry.
    ``boundary_reference.py`` already declares ``scientific_clipping_available``
    false, and this module does not override it.  The extract envelope is
    labelled as *derived from display geometry* and carries an explicit
    uncertainty and margin.
2.  Coordinates are never silently clipped or reinterpreted.  Every scope test
    reports the frame it used, and a point outside the baseline is reported as
    outside rather than snapped inward.
3.  DfT calibration evidence covers Manchester local authority only.  Greater
    Manchester locations without observations are ``uncovered``; they are never
    filled with zero, because a missing survey point is not measured silence.

This module performs no acquisition, no network build, and no calibration.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal, TypeAlias

import pyproj
from pydantic import Field, model_validator
from pyproj import Transformer

from traffictwin.integration.manchester.boundary_reference import (
    ManchesterBoundaryFeature,
    load_boundary_feature,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel

MANCHESTER_NETWORK_SCOPE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MANCHESTER_NETWORK_SCOPE_METHOD_VERSION: Literal["manchester-baseline-network-scope-1.0"] = (
    "manchester-baseline-network-scope-1.0"
)
MANCHESTER_NETWORK_SCOPE_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

BASELINE_SCOPE: Literal["greater_manchester_combined_authority"] = (
    "greater_manchester_combined_authority"
)
SUB_AREA_SCOPE: Literal["manchester_local_authority"] = "manchester_local_authority"

GEOGRAPHIC_CRS: Literal["EPSG:4326"] = "EPSG:4326"
DISTANCE_CRS: Literal["EPSG:27700"] = "EPSG:27700"

#: Margin added to the derived envelope, in decimal degrees.  The packaged
#: geometry is generalised to 20 m and rounded to 4 decimal places; ~0.01
#: degrees is roughly 1.1 km of latitude and comfortably exceeds both.  It
#: exists so the extract cannot clip a road that the generalised outline
#: understates, and it is declared rather than hidden.
ENVELOPE_MARGIN_DEGREES = Decimal("0.01")

#: Declared boundary uncertainty of the *envelope*, in metres.  This describes
#: the ONS generalisation, not the positional accuracy of OSM geometry, which
#: TrafficTwin does not assert.
ENVELOPE_UNCERTAINTY_M = 20

_COORDINATE_QUANTUM = Decimal("0.000001")

RequiredArea: TypeAlias = Literal[
    "manchester_city_centre",
    "university_of_manchester",
]

CoverageState: TypeAlias = Literal["covered", "uncovered"]

#: Required inclusion probes for the baseline network.  The repository owner
#: required that the baseline contain Manchester City Centre and the University
#: of Manchester area, so these are asserted rather than assumed.  Coordinates
#: are public landmark positions used only as containment probes; they are not
#: observation sites and carry no traffic meaning.
REQUIRED_AREA_PROBES: tuple[tuple[RequiredArea, str, Decimal, Decimal], ...] = (
    (
        "manchester_city_centre",
        "Manchester city centre (St Peter's Square)",
        Decimal("-2.2446"),
        Decimal("53.4779"),
    ),
    (
        "university_of_manchester",
        "University of Manchester (Oxford Road campus)",
        Decimal("-2.2339"),
        Decimal("53.4668"),
    ),
)


class ManchesterNetworkScopeError(ValueError):
    """Typed refusal for an unsupported or inconsistent scope request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NetworkScopeModel(ManchesterSnapshotModel):
    """Strict frozen base for baseline-scope artifacts."""


class GeographicPoint(NetworkScopeModel):
    """One exact WGS84 position with no implied traffic meaning."""

    longitude: Decimal = Field(ge=-180, le=180)
    latitude: Decimal = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def validate_quantum(self) -> GeographicPoint:
        for value in (self.longitude, self.latitude):
            if value != value.quantize(_COORDINATE_QUANTUM):
                raise ValueError("coordinates are bounded to six decimal places")
        return self


class ExtractEnvelope(NetworkScopeModel):
    """Axis-aligned envelope derived from generalised display geometry.

    This is deliberately not called a boundary.  It is the bounded region an
    OSM extract may cover, derived from display-only geometry plus a declared
    margin, and it is never presented as an administrative boundary or as a
    scientific clipping boundary.
    """

    schema_version: Literal["1.0"] = "1.0"
    derivation: Literal["derived_from_display_geometry"] = "derived_from_display_geometry"
    min_longitude: Decimal = Field(ge=-180, le=180)
    min_latitude: Decimal = Field(ge=-90, le=90)
    max_longitude: Decimal = Field(ge=-180, le=180)
    max_latitude: Decimal = Field(ge=-90, le=90)
    margin_degrees: Decimal = Field(gt=0, le=1)
    boundary_uncertainty_m: int = Field(ge=1, le=1_000)
    coordinate_reference_system: Literal["EPSG:4326"] = "EPSG:4326"
    administrative_boundary: Literal[False] = False
    scientific_clipping_boundary: Literal[False] = False

    @model_validator(mode="after")
    def validate_envelope(self) -> ExtractEnvelope:
        if self.min_longitude >= self.max_longitude:
            raise ValueError("envelope longitude range must be increasing")
        if self.min_latitude >= self.max_latitude:
            raise ValueError("envelope latitude range must be increasing")
        return self

    def contains(self, point: GeographicPoint) -> bool:
        """Report envelope containment without altering the point."""

        return (
            self.min_longitude <= point.longitude <= self.max_longitude
            and self.min_latitude <= point.latitude <= self.max_latitude
        )


class SubAreaBounds(NetworkScopeModel):
    """The Manchester local-authority filter's own axis-aligned WGS84 bounds.

    The local authority is a *filter* over the baseline network, never a second
    network, so a built network has to contain the whole filter area before a
    request filtered to the local authority can be answered without silently
    returning a truncated area.  These bounds exist so that containment can be
    measured rather than assumed.

    Like :class:`ExtractEnvelope` this comes from generalised display geometry
    and carries no margin, so it is not an administrative boundary either.
    """

    schema_version: Literal["1.0"] = "1.0"
    scope: Literal["manchester_local_authority"] = SUB_AREA_SCOPE
    official_code: Literal["E08000003"] = "E08000003"
    derivation: Literal["derived_from_display_geometry"] = "derived_from_display_geometry"
    min_longitude: Decimal = Field(ge=-180, le=180)
    min_latitude: Decimal = Field(ge=-90, le=90)
    max_longitude: Decimal = Field(ge=-180, le=180)
    max_latitude: Decimal = Field(ge=-90, le=90)
    coordinate_reference_system: Literal["EPSG:4326"] = GEOGRAPHIC_CRS
    administrative_boundary: Literal[False] = False
    margin_degrees: Literal[0] = 0

    @model_validator(mode="after")
    def validate_bounds(self) -> SubAreaBounds:
        if self.min_longitude >= self.max_longitude:
            raise ValueError("sub-area longitude range must be increasing")
        if self.min_latitude >= self.max_latitude:
            raise ValueError("sub-area latitude range must be increasing")
        return self


class RequiredAreaProbe(NetworkScopeModel):
    """One required-inclusion probe and the frame that evaluated it."""

    area: RequiredArea
    description: str = Field(min_length=1, max_length=120)
    point: GeographicPoint
    inside_baseline_boundary: bool
    inside_baseline_envelope: bool
    inside_sub_area_boundary: bool
    evaluation_frame: Literal["EPSG:4326"] = "EPSG:4326"
    traffic_observation_claim: Literal[False] = False


class DftCalibrationCoverage(NetworkScopeModel):
    """Where DfT calibration evidence can and cannot apply in the baseline.

    DfT road-traffic count points are published for Manchester local authority.
    Inside the Greater Manchester baseline that is partial coverage.  A location
    outside the local-authority filter is ``uncovered`` and stays unavailable:
    it is never rendered as zero traffic, because no survey point is not the
    same measurement as no vehicles.
    """

    schema_version: Literal["1.0"] = "1.0"
    baseline_scope: Literal["greater_manchester_combined_authority"] = BASELINE_SCOPE
    observation_scope: Literal["manchester_local_authority"] = SUB_AREA_SCOPE
    observation_scope_code: Literal["E08000003"] = "E08000003"
    coverage_kind: Literal["partial"] = "partial"
    uncovered_state: Literal["unavailable"] = "unavailable"
    uncovered_is_zero: Literal[False] = False
    missing_filled_with_zero: Literal[False] = False
    calibration_performed: Literal[False] = False
    model_validity_claimed: Literal[False] = False

    def classify(self, *, inside_observation_scope: bool) -> CoverageState:
        """Classify one location's DfT calibration coverage."""

        return "covered" if inside_observation_scope else "uncovered"


class BaselineScopeDecision(NetworkScopeModel):
    """The ADR-059 scope decision as a checkable artifact."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-baseline-network-scope-1.0"] = (
        MANCHESTER_NETWORK_SCOPE_METHOD_VERSION
    )
    decision_record: Literal["ADR-059"] = "ADR-059"
    baseline_scope: Literal["greater_manchester_combined_authority"] = BASELINE_SCOPE
    baseline_official_code: Literal["E47000001"] = "E47000001"
    sub_area_scope: Literal["manchester_local_authority"] = SUB_AREA_SCOPE
    sub_area_official_code: Literal["E08000003"] = "E08000003"
    sub_area_is_filter: Literal[True] = True
    sub_area_is_second_network: Literal[False] = False
    boundary_asset_role: Literal["identity_and_derived_envelope_only"] = (
        "identity_and_derived_envelope_only"
    )
    envelope: ExtractEnvelope
    required_areas: tuple[RequiredAreaProbe, ...] = Field(min_length=2)
    dft_coverage: DftCalibrationCoverage
    geographic_crs: Literal["EPSG:4326"] = GEOGRAPHIC_CRS
    distance_crs: Literal["EPSG:27700"] = DISTANCE_CRS
    pyproj_version: str = Field(min_length=1, max_length=40)
    proj_version: str = Field(min_length=1, max_length=40)
    capability_status: Literal["planned"] = "planned"

    @model_validator(mode="after")
    def validate_decision(self) -> BaselineScopeDecision:
        if self.pyproj_version != pyproj.__version__:
            raise ValueError("scope decision must record the active pyproj version")
        if self.proj_version != pyproj.proj_version_str:
            raise ValueError("scope decision must record the active PROJ version")
        observed = tuple(probe.area for probe in self.required_areas)
        expected = tuple(area for area, _label, _lon, _lat in REQUIRED_AREA_PROBES)
        if observed != expected:
            raise ValueError("required-area probes must match the reviewed inclusion set exactly")
        missing = tuple(
            probe.area for probe in self.required_areas if not probe.inside_baseline_boundary
        )
        if missing:
            raise ValueError(
                "the baseline scope must contain every required area; "
                f"missing: {', '.join(sorted(missing))}"
            )
        return self


def _ring(feature: ManchesterBoundaryFeature) -> tuple[tuple[float, float], ...]:
    return feature.coordinates[0]


def _point_in_ring(point: GeographicPoint, ring: tuple[tuple[float, float], ...]) -> bool:
    """Deterministic ray-casting containment test in EPSG:4326.

    The test reports containment only.  It never moves, clips, snaps, or
    reprojects the tested point.
    """

    x = float(point.longitude)
    y = float(point.latitude)
    inside = False
    count = len(ring)
    previous = count - 1
    for current in range(count):
        x_current, y_current = ring[current]
        x_previous, y_previous = ring[previous]
        if (y_current > y) != (y_previous > y):
            crossing = (x_previous - x_current) * (y - y_current) / (
                y_previous - y_current
            ) + x_current
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def _quantise(value: float) -> Decimal:
    return Decimal(str(value)).quantize(_COORDINATE_QUANTUM)


@lru_cache(maxsize=1)
def distance_transformer() -> Transformer:
    """Return the shared WGS84-to-British-National-Grid transformer."""

    return Transformer.from_crs(GEOGRAPHIC_CRS, DISTANCE_CRS, always_xy=True)


def derive_extract_envelope(
    *,
    margin_degrees: Decimal = ENVELOPE_MARGIN_DEGREES,
) -> ExtractEnvelope:
    """Derive the bounded OSM extract envelope from the baseline display geometry."""

    if margin_degrees <= 0 or margin_degrees > 1:
        raise ManchesterNetworkScopeError(
            "ENVELOPE_MARGIN_REFUSED", "envelope margin must be a bounded positive degree value"
        )
    ring = _ring(load_boundary_feature(BASELINE_SCOPE))
    longitudes = [position[0] for position in ring]
    latitudes = [position[1] for position in ring]
    return ExtractEnvelope(
        min_longitude=_quantise(min(longitudes)) - margin_degrees,
        min_latitude=_quantise(min(latitudes)) - margin_degrees,
        max_longitude=_quantise(max(longitudes)) + margin_degrees,
        max_latitude=_quantise(max(latitudes)) + margin_degrees,
        margin_degrees=margin_degrees,
        boundary_uncertainty_m=ENVELOPE_UNCERTAINTY_M,
    )


def evaluate_required_areas(envelope: ExtractEnvelope) -> tuple[RequiredAreaProbe, ...]:
    """Evaluate every required-inclusion probe against boundary and envelope."""

    baseline_ring = _ring(load_boundary_feature(BASELINE_SCOPE))
    sub_area_ring = _ring(load_boundary_feature(SUB_AREA_SCOPE))
    probes: list[RequiredAreaProbe] = []
    for area, description, longitude, latitude in REQUIRED_AREA_PROBES:
        point = GeographicPoint(longitude=longitude, latitude=latitude)
        probes.append(
            RequiredAreaProbe(
                area=area,
                description=description,
                point=point,
                inside_baseline_boundary=_point_in_ring(point, baseline_ring),
                inside_baseline_envelope=envelope.contains(point),
                inside_sub_area_boundary=_point_in_ring(point, sub_area_ring),
            )
        )
    return tuple(probes)


def sub_area_bounds() -> SubAreaBounds:
    """Measure the local-authority filter's own bounds from its display geometry."""

    ring = _ring(load_boundary_feature(SUB_AREA_SCOPE))
    longitudes = [position[0] for position in ring]
    latitudes = [position[1] for position in ring]
    return SubAreaBounds(
        min_longitude=_quantise(min(longitudes)),
        min_latitude=_quantise(min(latitudes)),
        max_longitude=_quantise(max(longitudes)),
        max_latitude=_quantise(max(latitudes)),
    )


def in_sub_area(point: GeographicPoint) -> bool:
    """Report whether one point falls inside the Manchester local-authority filter."""

    return _point_in_ring(point, _ring(load_boundary_feature(SUB_AREA_SCOPE)))


def in_baseline(point: GeographicPoint) -> bool:
    """Report whether one point falls inside the Greater Manchester baseline."""

    return _point_in_ring(point, _ring(load_boundary_feature(BASELINE_SCOPE)))


def classify_dft_coverage(point: GeographicPoint) -> CoverageState:
    """Classify one baseline location's DfT calibration coverage.

    A location outside the Manchester local-authority filter is ``uncovered``.
    Callers must render that as unavailable and must never substitute zero.
    """

    return DftCalibrationCoverage().classify(inside_observation_scope=in_sub_area(point))


def baseline_scope_decision(
    *,
    margin_degrees: Decimal = ENVELOPE_MARGIN_DEGREES,
) -> BaselineScopeDecision:
    """Build the complete checkable ADR-059 scope decision."""

    envelope = derive_extract_envelope(margin_degrees=margin_degrees)
    return BaselineScopeDecision(
        envelope=envelope,
        required_areas=evaluate_required_areas(envelope),
        dft_coverage=DftCalibrationCoverage(),
        pyproj_version=pyproj.__version__,
        proj_version=pyproj.proj_version_str,
    )
