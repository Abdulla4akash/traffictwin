"""Static Manchester geographic context for Home fallback.

This module provides an offline, deterministic boundary outline for the
Manchester study area when no accepted Manchester scene is available. It
reuses the already-reviewed ONS December 2025 generalised boundaries and
adds no provider, network, or scientific capability.

The geometry is display-only: no traffic, no telemetry, no calibrated
network, no live data.
"""

from __future__ import annotations

from dataclasses import dataclass

import pydeck as pdk

from traffictwin.integration.manchester.boundary_reference import (
    ManchesterBoundaryFeature,
    boundary_attributions,
    load_boundary_features,
)

# The two packaged GeoJSON files are ~10 KB total and are re-validated on
# load. Caching is intentionally not used here: the files are tiny, the load
# is deterministic and cheap, and Streamlit caching would add cross-test
# session complexity for no meaningful performance gain.


@dataclass(frozen=True)
class ManchesterContext:
    """Validated static geographic context for the study area."""

    greater_manchester: ManchesterBoundaryFeature
    manchester: ManchesterBoundaryFeature
    deck: pdk.Deck
    attribution: tuple[str, str]


def load_manchester_context() -> ManchesterContext:
    """Load the static boundary context or raise ``ManchesterBoundaryError``."""

    greater_manchester, manchester = load_boundary_features()
    deck = _build_context_deck((greater_manchester, manchester))
    return ManchesterContext(
        greater_manchester=greater_manchester,
        manchester=manchester,
        deck=deck,
        attribution=boundary_attributions(),
    )


def _build_context_deck(
    features: tuple[ManchesterBoundaryFeature, ...],
) -> pdk.Deck:
    """Build an offline, no-basemap deck fitted to the boundary extents."""

    # Reuse the single authoritative boundary layer construction.
    from traffictwin.ui.manchester_operations import build_boundary_layers

    layers = build_boundary_layers(features)
    longitude, latitude, zoom = _context_view_state(features)
    return pdk.Deck(
        layers=layers,
        map_provider=None,
        map_style=None,
        initial_view_state=pdk.ViewState(
            longitude=longitude,
            latitude=latitude,
            zoom=zoom,
            min_zoom=5,
            max_zoom=17,
            pitch=0,
            bearing=0,
        ),
        tooltip={
            "text": "{accessible_label}\nSource: {source}\nScope: {scope}\n"
            "Coordinate uncertainty: {uncertainty_m}"
        },
        description=(
            "Static Manchester geographic context. Pinned ONS December 2025 "
            "boundaries provide an offline study-area reference. No basemap, "
            "live traffic, observed scene, or calibrated network is displayed."
        ),
    )


def _context_view_state(
    features: tuple[ManchesterBoundaryFeature, ...],
) -> tuple[float, float, float]:
    """Centre and zoom the view so the Greater Manchester boundary fits."""

    longitudes: list[float] = []
    latitudes: list[float] = []
    for feature in features:
        for ring in feature.coordinates:
            for longitude, latitude in ring:
                longitudes.append(float(longitude))
                latitudes.append(float(latitude))
    if not longitudes or not latitudes:
        return -2.2426, 53.4808, 8.5
    min_lon, max_lon = min(longitudes), max(longitudes)
    min_lat, max_lat = min(latitudes), max(latitudes)
    centre_lon = (min_lon + max_lon) / 2
    centre_lat = (min_lat + max_lat) / 2
    span = max(max_lon - min_lon, max_lat - min_lat)
    if span <= 0.02:
        zoom = 13.0
    elif span <= 0.1:
        zoom = 11.0
    elif span <= 0.5:
        zoom = 9.0
    elif span <= 1.0:
        zoom = 7.5
    else:
        zoom = 7.0
    return centre_lon, centre_lat, zoom
