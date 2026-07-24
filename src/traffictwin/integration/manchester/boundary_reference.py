"""Pinned official boundary context for the offline Manchester evidence map.

The two packaged GeoJSON files are display-only derivatives of public-authoritative
ONS December 2025 generalised boundaries. They provide geographic context without a
remote tile provider. They are not a road network, a sensor-coverage claim, or an
admission boundary for scientific filtering.
"""

from __future__ import annotations

import json
import math
from importlib import resources
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel, sha256_hex

MANCHESTER_BOUNDARY_SCHEMA_VERSION = "1.0"
MANCHESTER_BOUNDARY_METHOD_VERSION = "ons-boundary-display-reference-1.0"
MANCHESTER_BOUNDARY_CAPABILITY_ID = "MAN-08"
MANCHESTER_BOUNDARY_MAX_BYTES = 32 * 1024

ONS_LICENCE_URI = "https://www.ons.gov.uk/methodology/geography/licences"
OGL_V3_URI = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
ONS_ATTRIBUTION = (
    "Source: Office for National Statistics licensed under the Open Government Licence v.3.0"
)
OS_ATTRIBUTION = "Contains OS data © Crown copyright and database right 2025"

BoundaryScope: TypeAlias = Literal[
    "manchester_local_authority",
    "greater_manchester_combined_authority",
]
BoundaryPosition: TypeAlias = tuple[float, float]
BoundaryRing: TypeAlias = tuple[BoundaryPosition, ...]
BoundaryPolygon: TypeAlias = tuple[BoundaryRing, ...]


class ManchesterBoundaryError(RuntimeError):
    """Raised when a packaged official boundary reference fails closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterBoundaryReference(ManchesterSnapshotModel):
    """Frozen provenance and interpretation contract for one boundary asset."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["ons-boundary-display-reference-1.0"] = (
        "ons-boundary-display-reference-1.0"
    )
    scope: BoundaryScope
    official_code: str = Field(pattern=r"^E[0-9]{8}$")
    official_name: str
    reference_date: Literal["December 2025"] = "December 2025"
    source_owner: Literal["Office for National Statistics"] = "Office for National Statistics"
    source_item_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    source_feature_service_uri: str
    source_product: str
    source_generalisation: Literal["BGC Generalised (20m), coastline clipped"] = (
        "BGC Generalised (20m), coastline clipped"
    )
    display_query_max_allowable_offset_degrees: float = 0.001
    display_query_geometry_precision_decimals: Literal[4] = 4
    asset_name: Literal[
        "manchester_local_authority.geojson",
        "greater_manchester_combined_authority.geojson",
    ]
    asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    licence_id: Literal["OGL-3.0"] = "OGL-3.0"
    licence_uri: Literal["https://www.ons.gov.uk/methodology/geography/licences"] = (
        "https://www.ons.gov.uk/methodology/geography/licences"
    )
    attribution_lines: tuple[str, str] = (OS_ATTRIBUTION, ONS_ATTRIBUTION)
    coordinate_reference_system: Literal["EPSG:4326"] = "EPSG:4326"
    map_context_available: Literal[True] = True
    public_display_available: Literal[True] = True
    remote_basemap_available: Literal[False] = False
    road_network_available: Literal[False] = False
    sensor_coverage_available: Literal[False] = False
    scientific_clipping_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_frozen_identity(self) -> ManchesterBoundaryReference:
        expected = _REFERENCE_VALUES[self.scope]
        observed = (
            self.official_code,
            self.official_name,
            self.source_item_id,
            self.source_feature_service_uri,
            self.source_product,
            self.asset_name,
            self.asset_sha256,
        )
        if observed != expected:
            raise ValueError("boundary identity must match the reviewed ONS reference")
        if self.display_query_max_allowable_offset_degrees != 0.001:
            raise ValueError("boundary display generalisation must match the reviewed query")
        if self.attribution_lines != (OS_ATTRIBUTION, ONS_ATTRIBUTION):
            raise ValueError("boundary attribution must retain the reviewed ONS and OS wording")
        return self


class ManchesterBoundaryFeature(ManchesterSnapshotModel):
    """Validated display geometry decoded from one exact packaged asset."""

    reference: ManchesterBoundaryReference
    geometry_type: Literal["Polygon"] = "Polygon"
    coordinates: BoundaryPolygon
    source_asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    display_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_geometry(self) -> ManchesterBoundaryFeature:
        if self.source_asset_sha256 != self.reference.asset_sha256:
            raise ValueError("boundary feature must bind the exact reviewed asset")
        if not self.coordinates:
            raise ValueError("boundary polygon must contain at least one ring")
        for ring in self.coordinates:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("boundary rings must be closed with at least four positions")
            for longitude, latitude in ring:
                if not math.isfinite(longitude) or not math.isfinite(latitude):
                    raise ValueError("boundary coordinates must be finite")
                if not (-3.5 <= longitude <= -1.0 and 52.5 <= latitude <= 54.5):
                    raise ValueError("boundary coordinates must remain in the reviewed region")
        return self

    def geojson(self) -> dict[str, object]:
        """Return a renderer-ready feature with explicit accessible context."""

        return {
            "type": "Feature",
            "properties": {
                "accessible_label": (
                    f"Official {self.reference.official_name} boundary; display context only"
                ),
                "source": "Office for National Statistics",
                "scope": self.reference.scope,
                "uncertainty_m": "display-only generalised boundary",
                "official_code": self.reference.official_code,
            },
            "geometry": {
                "type": self.geometry_type,
                "coordinates": self.coordinates,
            },
        }


_REFERENCE_VALUES: dict[
    BoundaryScope,
    tuple[str, str, str, str, str, str, str],
] = {
    "manchester_local_authority": (
        "E08000003",
        "Manchester",
        "54b2a8f849f743aea669488cab415c8f",
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Local_Authority_Districts_DEC_2025_Boundaries_UK_BGC/FeatureServer",
        "Local Authority Districts (December 2025) Boundaries UK BGC",
        "manchester_local_authority.geojson",
        "31b78ea21882ec80a82b0cc584a57e0b1d1a4f1c8269e1bfc54826fb9981a51c",
    ),
    "greater_manchester_combined_authority": (
        "E47000001",
        "Greater Manchester",
        "8b6547b5908a4c90a2d63baf9543c5fb",
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Combined_Authorities_December_2025_Boundaries_EN_BGC/FeatureServer",
        "Combined Authorities (December 2025) Boundaries EN BGC",
        "greater_manchester_combined_authority.geojson",
        "1bf8a1293de43f1573ec87685e0772ec8b9bd4cb14ec0ae0b0c21cd80d9a313a",
    ),
}


def boundary_reference(scope: BoundaryScope) -> ManchesterBoundaryReference:
    """Return the frozen reviewed reference for one supported official scope."""

    code, name, item_id, service_uri, product, asset_name, digest = _REFERENCE_VALUES[scope]
    return ManchesterBoundaryReference(
        scope=scope,
        official_code=code,
        official_name=name,
        source_item_id=item_id,
        source_feature_service_uri=service_uri,
        source_product=product,
        asset_name=asset_name,  # type: ignore[arg-type]
        asset_sha256=digest,
    )


def load_boundary_feature(scope: BoundaryScope) -> ManchesterBoundaryFeature:
    """Load and re-verify one exact packaged official boundary derivative."""

    reference = boundary_reference(scope)
    asset = resources.files("traffictwin.integration.manchester").joinpath(
        "boundary_data", reference.asset_name
    )
    try:
        payload = asset.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_UNAVAILABLE",
            f"the reviewed {reference.official_name} boundary asset is unavailable",
        ) from exc
    if not payload or len(payload) > MANCHESTER_BOUNDARY_MAX_BYTES:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_SIZE_REFUSED",
            "the packaged boundary asset is empty or exceeds its reviewed size boundary",
        )
    observed_digest = sha256_hex(payload)
    if observed_digest != reference.asset_sha256:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_IDENTITY_MISMATCH",
            "the packaged boundary asset no longer matches the reviewed ONS derivative",
        )
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID",
            "the reviewed boundary asset is not valid UTF-8 GeoJSON",
        ) from exc
    coordinates = _validated_geojson_coordinates(document, reference)
    return ManchesterBoundaryFeature(
        reference=reference,
        coordinates=coordinates,
        source_asset_sha256=observed_digest,
    )


def load_boundary_features() -> tuple[ManchesterBoundaryFeature, ManchesterBoundaryFeature]:
    """Load both official context boundaries in stable outside-to-inside order."""

    return (
        load_boundary_feature("greater_manchester_combined_authority"),
        load_boundary_feature("manchester_local_authority"),
    )


def boundary_attributions() -> tuple[str, str]:
    """Return the exact attribution required whenever the boundaries render."""

    return OS_ATTRIBUTION, ONS_ATTRIBUTION


def _validated_geojson_coordinates(
    document: object,
    reference: ManchesterBoundaryReference,
) -> BoundaryPolygon:
    if not isinstance(document, dict) or set(document) != {"crs", "features", "type"}:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID",
            "the boundary GeoJSON must be an exact FeatureCollection",
        )
    if document.get("type") != "FeatureCollection":
        raise ManchesterBoundaryError("BOUNDARY_ASSET_INVALID", "unexpected GeoJSON root type")
    if document.get("crs") != {
        "type": "name",
        "properties": {"name": "EPSG:4326"},
    }:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID", "the boundary asset must declare exact EPSG:4326"
        )
    features = document.get("features")
    if not isinstance(features, list) or len(features) != 1:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID", "the boundary asset must contain exactly one feature"
        )
    feature = features[0]
    if not isinstance(feature, dict) or set(feature) != {"geometry", "properties", "type"}:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID", "the boundary feature has an unexpected shape"
        )
    expected_properties = (
        {"LAD25CD": reference.official_code, "LAD25NM": reference.official_name}
        if reference.scope == "manchester_local_authority"
        else {"CAUTH25CD": reference.official_code, "CAUTH25NM": reference.official_name}
    )
    if feature.get("type") != "Feature" or feature.get("properties") != expected_properties:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID", "the boundary feature identity does not match its reference"
        )
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Polygon":
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID", "the boundary geometry must be one Polygon"
        )
    try:
        return tuple(
            tuple((float(position[0]), float(position[1])) for position in ring)
            for ring in geometry["coordinates"]
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ManchesterBoundaryError(
            "BOUNDARY_ASSET_INVALID", "the boundary coordinate arrays are malformed"
        ) from exc
