"""MAN-08 candidate: deterministic offline Manchester map-layer payloads.

The service projects no coordinates and performs no joins. It converts only
MAN-07-admitted points into renderer-neutral payloads, binds freshness and
snapshot provenance, and keeps attribution/publication limits executable.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.freshness import (
    FreshnessTruthState,
    SourceFreshnessEvaluation,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotModel,
)
from traffictwin.integration.manchester.spatial import (
    GeographicScope,
    GeometryMeaning,
    SpatialAdmissionReport,
    SpatialCoordinateBounds,
    SpatialSource,
)

MANCHESTER_MAP_SCHEMA_VERSION = "1.0"
MANCHESTER_MAP_METHOD_VERSION = "manchester-map-layer-1.0"
MANCHESTER_MAP_CAPABILITY_ID = "MAN-08"
OGL_V3_URI = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
NATIONAL_HIGHWAYS_TERMS_URI = "https://developer.data.nationalhighways.co.uk/terms"
NATIONAL_HIGHWAYS_ATTRIBUTION = "Powered by National Highways’ Transport Data Feeds"
SYNTHETIC_ATTRIBUTION = "Synthetic TrafficTwin fixture; not observed Manchester data."

MapMode: TypeAlias = Literal["historical_replay", "latest_available", "live_vehicles"]
MapLayerStatus: TypeAlias = Literal["available", "partial", "unavailable"]
MapLayerReason: TypeAlias = Literal[
    "ready",
    "spatial_admission_partial",
    "spatial_admission_unavailable",
    "snapshot_unavailable",
    "freshness_unavailable",
    "stale_cached_evidence",
]
MapSymbol: TypeAlias = Literal["circle", "square", "diamond", "triangle", "cross"]

_LAYER_ID_PATTERN = r"^[a-z][a-z0-9_-]{1,63}$"
_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"


class ManchesterMapError(ValueError):
    """Raised for duplicate or cross-mode scene input."""


class ManchesterMapModel(ManchesterSnapshotModel):
    """Strict frozen base for candidate MAN-08 artifacts."""


class MapLayerStyle(ManchesterMapModel):
    """Accessible source-specific point style; colour is never the sole cue."""

    source: SpatialSource
    symbol: MapSymbol
    legend_label: str = Field(min_length=1, max_length=100)
    accessible_description: str = Field(min_length=1, max_length=240)
    fill_rgba: tuple[int, int, int, Literal[210]]
    radius_pixels: int = Field(ge=3, le=20)
    colour_is_sole_meaning: Literal[False] = False

    @model_validator(mode="after")
    def validate_style(self) -> MapLayerStyle:
        expected = _style_values(self.source)
        observed = (
            self.symbol,
            self.legend_label,
            self.accessible_description,
            self.fill_rgba,
            self.radius_pixels,
        )
        if observed != expected:
            raise ValueError("style must match the frozen source-specific map policy")
        return self


class MapLayerRequest(ManchesterMapModel):
    """Complete local evidence required to assemble one point layer."""

    layer_id: str = Field(pattern=_LAYER_ID_PATTERN)
    title: str = Field(min_length=1, max_length=120)
    mode: MapMode
    source: SpatialSource
    snapshot_id: str | None = Field(default=None, pattern=_SNAPSHOT_ID_PATTERN)
    snapshot_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    spatial_report: SpatialAdmissionReport
    freshness: SourceFreshnessEvaluation | None = None
    publication_class: ManchesterPublicationClass
    licence_id: str = Field(min_length=1, max_length=80)
    licence_uri: str | None = Field(default=None, max_length=500)
    attribution_lines: tuple[str, ...] = Field(min_length=1, max_length=4)
    synthetic: bool
    requested_visible: bool = True
    point_labels: tuple[tuple[str, str], ...] = ()

    @model_validator(mode="after")
    def validate_request(self) -> MapLayerRequest:
        if (self.snapshot_id is None) != (self.snapshot_fingerprint is None):
            raise ValueError("snapshot id and fingerprint must coexist")
        if tuple(sorted(set(self.attribution_lines))) != self.attribution_lines:
            raise ValueError("attribution lines must be sorted and unique")
        if any(not line.strip() or len(line) > 500 for line in self.attribution_lines):
            raise ValueError("attribution lines must be bounded non-empty text")
        if self.source == "synthetic":
            if not self.synthetic or self.attribution_lines != (SYNTHETIC_ATTRIBUTION,):
                raise ValueError("synthetic layers need the exact synthetic label")
        elif self.synthetic is False and self.licence_id.startswith("synthetic"):
            raise ValueError("observed-source layers cannot claim a synthetic licence")
        if self.source in {"dft", "webtris", "tfgm_signals"} and (self.licence_uri != OGL_V3_URI):
            raise ValueError("OGL source layers must retain the reviewed OGL v3 URI")
        if self.source.startswith("national_highways_") and (
            self.licence_uri != NATIONAL_HIGHWAYS_TERMS_URI
            or NATIONAL_HIGHWAYS_ATTRIBUTION not in self.attribution_lines
            or self.publication_class is not ManchesterPublicationClass.PRIVATE
        ):
            raise ValueError(
                "National Highways layers require the reviewed terms, attribution, "
                "and private class"
            )
        _validate_freshness_source(self.source, self.freshness)
        for result in self.spatial_report.results:
            if result.source != self.source:
                raise ValueError("a map layer cannot mix spatial source families")
        label_keys = tuple(key for key, _label in self.point_labels)
        if label_keys != tuple(sorted(set(label_keys))):
            raise ValueError("point labels must have sorted unique source fingerprints")
        if any(len(label) > 500 or not label.strip() for _key, label in self.point_labels):
            raise ValueError("point labels must be bounded non-empty text")
        admitted_keys = tuple(
            sorted(
                result.source_record_fingerprint
                for result in self.spatial_report.results
                if result.status == "admitted"
            )
        )
        if self.point_labels and label_keys != admitted_keys:
            raise ValueError("point labels must cover every admitted source record exactly")
        return self


class ManchesterMapPoint(ManchesterMapModel):
    """One admitted WGS84 point with no inferred identity or continuity."""

    point_id: str = Field(min_length=1, max_length=200)
    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    spatial_result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    longitude: Decimal = Field(ge=-180, le=180)
    latitude: Decimal = Field(ge=-90, le=90)
    geographic_scope: GeographicScope
    geometry_meaning: GeometryMeaning
    coordinate_uncertainty_m: Decimal | None = Field(default=None, ge=0)
    accessible_label: str = Field(min_length=1, max_length=320)
    source_position_preserved: Literal[True] = True
    map_matched: Literal[False] = False
    identity_joined: Literal[False] = False
    continuity_inferred: Literal[False] = False


class MapLayerCounts(ManchesterMapModel):
    """Complete spatial-to-map point reconciliation."""

    spatial_inputs: int = Field(ge=0)
    points_rendered: int = Field(ge=0)
    points_excluded: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> MapLayerCounts:
        if self.spatial_inputs != self.points_rendered + self.points_excluded:
            raise ValueError("map-layer counts must reconcile")
        return self


class ManchesterMapLayerManifest(ManchesterMapModel):
    """One complete renderer-neutral map layer and its display contract."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-map-layer-1.0"] = "manchester-map-layer-1.0"
    request: MapLayerRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: MapLayerStatus
    reason: MapLayerReason
    style: MapLayerStyle
    spatial_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    freshness_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    freshness_truth_state: FreshnessTruthState | None = None
    points: tuple[ManchesterMapPoint, ...]
    bounds: SpatialCoordinateBounds | None
    counts: MapLayerCounts
    visible: bool
    local_rendering_available: bool
    public_export_available: bool
    basemap_provider: None = None
    external_network_required: Literal[False] = False
    stale_badge_visible: bool
    attribution_visible: Literal[True] = True
    source_scope_visible: Literal[True] = True
    cross_source_join_performed: Literal[False] = False
    visual_proximity_join_performed: Literal[False] = False
    aggregation_implies_occupancy: Literal[False] = False

    @model_validator(mode="after")
    def validate_manifest(self) -> ManchesterMapLayerManifest:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint must match the embedded request")
        if self.spatial_report_fingerprint != self.request.spatial_report.fingerprint():
            raise ValueError("spatial report fingerprint must match the request")
        expected_freshness = (
            None if self.request.freshness is None else self.request.freshness.fingerprint()
        )
        if self.freshness_fingerprint != expected_freshness:
            raise ValueError("freshness fingerprint must match the request")
        expected_truth = (
            None if self.request.freshness is None else self.request.freshness.truth_state
        )
        if self.freshness_truth_state != expected_truth:
            raise ValueError("freshness truth state must match the embedded evaluation")
        if self.style != map_layer_style(self.request.source):
            raise ValueError("style must match the frozen source style")
        point_fingerprints = tuple(point.spatial_result_fingerprint for point in self.points)
        expected_results = tuple(
            result.fingerprint()
            for result in self.request.spatial_report.results
            if result.status == "admitted"
        )
        if point_fingerprints != expected_results:
            raise ValueError("rendered points must exactly follow admitted spatial results")
        expected_counts = MapLayerCounts(
            spatial_inputs=self.request.spatial_report.counts.inputs_seen,
            points_rendered=len(self.points),
            points_excluded=self.request.spatial_report.counts.excluded,
        )
        if self.counts != expected_counts:
            raise ValueError("map counts must match spatial admission")
        expected_bounds = _point_bounds(self.points)
        if self.bounds != expected_bounds:
            raise ValueError("map bounds must exactly enclose rendered points")
        renderable = self.status != "unavailable"
        if self.local_rendering_available != renderable:
            raise ValueError("local rendering availability must match status")
        if self.visible != (renderable and self.request.requested_visible):
            raise ValueError("visibility must match availability and the request")
        expected_export = renderable and self.request.publication_class in {
            ManchesterPublicationClass.REDISTRIBUTABLE_RAW,
            ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED,
        }
        if self.public_export_available != expected_export:
            raise ValueError("public export must follow the snapshot publication class")
        stale = self.request.freshness is not None and self.request.freshness.truth_state == "stale"
        if self.stale_badge_visible != stale:
            raise ValueError("stale badge must match the freshness decision")
        expected_status, expected_reason = _layer_state(self.request)
        if (self.status, self.reason) != (expected_status, expected_reason):
            raise ValueError("map status must match deterministic prerequisites")
        return self


class ManchesterMapScene(ManchesterMapModel):
    """Offline scene composed without source fusion or cross-scope totals."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-map-layer-1.0"] = "manchester-map-layer-1.0"
    mode: MapMode
    layers: tuple[ManchesterMapLayerManifest, ...]
    visible_layer_ids: tuple[str, ...]
    attributions: tuple[str, ...]
    scopes: tuple[GeographicScope, ...]
    bounds: SpatialCoordinateBounds | None
    status: MapLayerStatus
    basemap_provider: None = None
    external_network_required: Literal[False] = False
    source_fusion_performed: Literal[False] = False
    cross_scope_totals_available: Literal[False] = False
    scopes_treated_as_equal: Literal[False] = False

    @model_validator(mode="after")
    def validate_scene(self) -> ManchesterMapScene:
        ids = tuple(layer.request.layer_id for layer in self.layers)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise ValueError("scene layers must have sorted unique IDs")
        if any(layer.request.mode != self.mode for layer in self.layers):
            raise ValueError("scene layers must share the requested mode")
        visible = tuple(layer.request.layer_id for layer in self.layers if layer.visible)
        if self.visible_layer_ids != visible:
            raise ValueError("visible layer inventory must match layer manifests")
        expected_attributions = tuple(
            sorted(
                {
                    line
                    for layer in self.layers
                    if layer.visible
                    for line in layer.request.attribution_lines
                }
            )
        )
        if self.attributions != expected_attributions:
            raise ValueError("scene attribution must equal the visible-layer union")
        expected_scopes = tuple(
            sorted(
                {
                    point.geographic_scope
                    for layer in self.layers
                    if layer.visible
                    for point in layer.points
                }
            )
        )
        if self.scopes != expected_scopes:
            raise ValueError("scene scopes must preserve the visible evidence scopes")
        expected_bounds = _layer_bounds(tuple(layer for layer in self.layers if layer.visible))
        if self.bounds != expected_bounds:
            raise ValueError("scene bounds must enclose visible layers")
        available = sum(layer.status == "available" for layer in self.layers)
        renderable = sum(layer.status != "unavailable" for layer in self.layers)
        expected_status: MapLayerStatus = (
            "unavailable"
            if not renderable
            else "available"
            if available == len(self.layers)
            else "partial"
        )
        if self.status != expected_status:
            raise ValueError("scene status must reconcile layer availability")
        return self


def map_layer_style(source: SpatialSource) -> MapLayerStyle:
    """Return the exact symbol/legend policy for one source family."""

    symbol, label, description, rgba, radius = _style_values(source)
    return MapLayerStyle(
        source=source,
        symbol=symbol,
        legend_label=label,
        accessible_description=description,
        fill_rgba=rgba,
        radius_pixels=radius,
    )


def map_style_catalogue() -> tuple[MapLayerStyle, ...]:
    """Return every source style in stable source order."""

    sources: tuple[SpatialSource, ...] = (
        "analysis_rsu",
        "bods_siri_vm",
        "dft",
        "national_highways_closures",
        "national_highways_speed_limits",
        "national_highways_vms",
        "randy_tos",
        "sumo_vec",
        "synthetic",
        "tfgm_signals",
        "webtris",
    )
    return tuple(map_layer_style(source) for source in sources)


def build_map_layer(request: MapLayerRequest) -> ManchesterMapLayerManifest:
    """Build one layer only from MAN-07-admitted points."""

    labels = dict(request.point_labels)
    points = tuple(
        ManchesterMapPoint(
            point_id=result.point_id,
            source_record_fingerprint=result.source_record_fingerprint,
            spatial_result_fingerprint=result.fingerprint(),
            longitude=result.longitude,
            latitude=result.latitude,
            geographic_scope=result.geographic_scope,
            geometry_meaning=result.geometry_meaning,
            coordinate_uncertainty_m=result.coordinate_uncertainty_m,
            accessible_label=labels.get(
                result.source_record_fingerprint,
                (
                    f"{result.geometry_meaning.replace('_', ' ')}; "
                    f"scope {result.geographic_scope.replace('_', ' ')}"
                ),
            ),
        )
        for result in request.spatial_report.results
        if result.status == "admitted"
        and result.longitude is not None
        and result.latitude is not None
    )
    status, reason = _layer_state(request)
    renderable = status != "unavailable"
    freshness_fingerprint = None if request.freshness is None else request.freshness.fingerprint()
    truth_state = None if request.freshness is None else request.freshness.truth_state
    return ManchesterMapLayerManifest(
        request=request,
        request_fingerprint=request.fingerprint(),
        status=status,
        reason=reason,
        style=map_layer_style(request.source),
        spatial_report_fingerprint=request.spatial_report.fingerprint(),
        freshness_fingerprint=freshness_fingerprint,
        freshness_truth_state=truth_state,
        points=points,
        bounds=_point_bounds(points),
        counts=MapLayerCounts(
            spatial_inputs=request.spatial_report.counts.inputs_seen,
            points_rendered=len(points),
            points_excluded=request.spatial_report.counts.excluded,
        ),
        visible=renderable and request.requested_visible,
        local_rendering_available=renderable,
        public_export_available=renderable
        and request.publication_class
        in {
            ManchesterPublicationClass.REDISTRIBUTABLE_RAW,
            ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED,
        },
        stale_badge_visible=truth_state == "stale",
    )


def build_map_scene(
    mode: MapMode,
    layers: Sequence[ManchesterMapLayerManifest],
) -> ManchesterMapScene:
    """Compose stable local layers without joining or aggregating their evidence."""

    ordered = tuple(sorted(layers, key=lambda layer: layer.request.layer_id))
    if len({layer.request.layer_id for layer in ordered}) != len(ordered):
        raise ManchesterMapError("duplicate map layer IDs are not admissible")
    if any(layer.request.mode != mode for layer in ordered):
        raise ManchesterMapError("map scene mode does not match every layer")
    visible = tuple(layer for layer in ordered if layer.visible)
    renderable = sum(layer.status != "unavailable" for layer in ordered)
    available = sum(layer.status == "available" for layer in ordered)
    status: MapLayerStatus = (
        "unavailable" if not renderable else "available" if available == len(ordered) else "partial"
    )
    return ManchesterMapScene(
        mode=mode,
        layers=ordered,
        visible_layer_ids=tuple(layer.request.layer_id for layer in visible),
        attributions=tuple(
            sorted({line for layer in visible for line in layer.request.attribution_lines})
        ),
        scopes=tuple(
            sorted({point.geographic_scope for layer in visible for point in layer.points})
        ),
        bounds=_layer_bounds(visible),
        status=status,
    )


def _layer_state(request: MapLayerRequest) -> tuple[MapLayerStatus, MapLayerReason]:
    if request.snapshot_id is None:
        return "unavailable", "snapshot_unavailable"
    if not request.spatial_report.counts.admitted:
        return "unavailable", "spatial_admission_unavailable"
    if request.freshness is not None and request.freshness.evaluation_status == "unavailable":
        return "unavailable", "freshness_unavailable"
    if request.freshness is not None and request.freshness.truth_state == "stale":
        return "partial", "stale_cached_evidence"
    if request.spatial_report.status == "partial":
        return "partial", "spatial_admission_partial"
    return "available", "ready"


def _point_bounds(points: Sequence[ManchesterMapPoint]) -> SpatialCoordinateBounds | None:
    if not points:
        return None
    return SpatialCoordinateBounds(
        min_longitude=min(point.longitude for point in points),
        min_latitude=min(point.latitude for point in points),
        max_longitude=max(point.longitude for point in points),
        max_latitude=max(point.latitude for point in points),
    )


def _layer_bounds(
    layers: Sequence[ManchesterMapLayerManifest],
) -> SpatialCoordinateBounds | None:
    bounds = tuple(layer.bounds for layer in layers if layer.bounds is not None)
    if not bounds:
        return None
    return SpatialCoordinateBounds(
        min_longitude=min(item.min_longitude for item in bounds),
        min_latitude=min(item.min_latitude for item in bounds),
        max_longitude=max(item.max_longitude for item in bounds),
        max_latitude=max(item.max_latitude for item in bounds),
    )


def _validate_freshness_source(
    source: SpatialSource,
    freshness: SourceFreshnessEvaluation | None,
) -> None:
    accepted: dict[SpatialSource, frozenset[str]] = {
        "dft": frozenset({"dft_raw_counts", "dft_count_points", "dft_aadf"}),
        "webtris": frozenset({"webtris_daily"}),
        "tfgm_signals": frozenset({"tfgm_signals"}),
        "bods_siri_vm": frozenset({"bods_siri_vm"}),
        "national_highways_closures": frozenset({"national_highways_closures"}),
        "national_highways_speed_limits": frozenset({"national_highways_speed_limits"}),
        "national_highways_vms": frozenset({"national_highways_vms"}),
        "randy_tos": frozenset({"randy_tos"}),
        "synthetic": frozenset({"synthetic"}),
        "sumo_vec": frozenset(),
        "analysis_rsu": frozenset(),
    }
    if accepted[source] and freshness is None:
        raise ValueError("this spatial source requires an explicit freshness evaluation")
    if freshness is not None and freshness.source not in accepted[source]:
        raise ValueError("freshness source does not match the spatial layer source")


def _style_values(
    source: SpatialSource,
) -> tuple[MapSymbol, str, str, tuple[int, int, int, Literal[210]], int]:
    values: dict[
        SpatialSource,
        tuple[MapSymbol, str, str, tuple[int, int, int, Literal[210]], int],
    ] = {
        "dft": (
            "circle",
            "DfT count point",
            "Circular historical road count point",
            (24, 96, 168, 210),
            7,
        ),
        "webtris": (
            "square",
            "WebTRIS detector",
            "Square strategic-road detector",
            (224, 112, 32, 210),
            7,
        ),
        "tfgm_signals": (
            "diamond",
            "TfGM signal",
            "Diamond static signal infrastructure site",
            (128, 72, 176, 210),
            7,
        ),
        "bods_siri_vm": (
            "triangle",
            "Transit vehicle",
            "Triangular transit-vehicle position",
            (24, 136, 96, 210),
            8,
        ),
        "national_highways_closures": (
            "cross",
            "Road/lane closure",
            "Cross-marked National Highways closure or incident position",
            (190, 48, 48, 210),
            9,
        ),
        "national_highways_speed_limits": (
            "diamond",
            "Temporary speed restriction",
            "Diamond National Highways imposed temporary speed restriction",
            (218, 132, 24, 210),
            9,
        ),
        "national_highways_vms": (
            "square",
            "Variable message sign",
            "Square National Highways digital variable-message sign status",
            (36, 112, 196, 210),
            9,
        ),
        "randy_tos": (
            "cross",
            "Randy evidence",
            "Cross-marked non-geographic Randy evidence",
            (96, 96, 96, 210),
            6,
        ),
        "sumo_vec": (
            "cross",
            "SUMO/VEC",
            "Cross-marked source-coordinate simulation evidence",
            (96, 96, 96, 210),
            6,
        ),
        "analysis_rsu": (
            "cross",
            "Analysis RSU",
            "Cross-marked generated analysis site",
            (96, 96, 96, 210),
            6,
        ),
        "synthetic": (
            "cross",
            "Synthetic point",
            "Cross-marked synthetic WGS84 fixture",
            (80, 80, 80, 210),
            6,
        ),
    }
    return values[source]
