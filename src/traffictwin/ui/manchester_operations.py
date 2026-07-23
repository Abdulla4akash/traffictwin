"""Thin local-data helpers for the candidate Manchester Operations page.

The UI boundary deliberately accepts only a validated ``ManchesterMapScene``
stored at a fixed path below the configured workspace. It performs no network
access, coordinate projection, source joins, or scientific calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

import pydeck as pdk
from pydantic import ValidationError

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.map_layers import (
    ManchesterMapLayerManifest,
    ManchesterMapScene,
    MapMode,
)
from traffictwin.integration.manchester.models import sha256_hex
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

MANCHESTER_SCENE_DIRECTORY = Path("manchester/scenes")
MANCHESTER_SCENE_MAX_BYTES = 8 * 1024 * 1024

SceneLoadStatus = Literal["available", "unavailable", "rejected"]
LiveAcquisitionStatus = Literal[
    "ready",
    "workspace_unconfigured",
    "workspace_invalid",
    "api_key_missing",
]
SceneLoadReason = Literal[
    "ready",
    "workspace_unconfigured",
    "scene_missing",
    "scene_path_escaped",
    "scene_symlink_refused",
    "scene_empty",
    "scene_too_large",
    "scene_read_failed",
    "scene_invalid",
    "scene_mode_mismatch",
]

_SCENE_FILENAMES: dict[MapMode, str] = {
    "historical_replay": "historical_replay.json",
    "latest_available": "latest_available.json",
    "live_vehicles": "live_vehicles.json",
}
_SYMBOL_GLYPHS = {
    "circle": "●",
    "square": "■",
    "diamond": "◆",
    "triangle": "▲",
    "cross": "✚",
}


@dataclass(frozen=True, slots=True)
class LocalManchesterScene:
    """Display-safe result of loading one fixed local scene artifact."""

    status: SceneLoadStatus
    reason: SceneLoadReason
    message: str
    scene: ManchesterMapScene | None = None
    artifact_sha256: str | None = None
    byte_size: int | None = None


@dataclass(frozen=True, slots=True)
class LiveAcquisitionReadiness:
    """Secret-free readiness state for the explicit BODS fetch form."""

    status: LiveAcquisitionStatus
    message: str
    ready: bool


def assess_live_acquisition_readiness(
    workspace_path: str | Path | None,
    *,
    api_key_available: bool,
) -> LiveAcquisitionReadiness:
    """Check local prerequisites without reading or retaining a credential."""

    if workspace_path is None:
        return LiveAcquisitionReadiness(
            status="workspace_unconfigured",
            message="Configure an isolated TrafficTwin v0.7 workspace first.",
            ready=False,
        )
    try:
        inspect_v07_workspace(workspace_path)
    except V07WorkspaceError:
        return LiveAcquisitionReadiness(
            status="workspace_invalid",
            message="The configured workspace is not a valid isolated v0.7 workspace.",
            ready=False,
        )
    if not api_key_available:
        return LiveAcquisitionReadiness(
            status="api_key_missing",
            message="Set BODS_API_KEY in the app environment, then restart Streamlit.",
            ready=False,
        )
    return LiveAcquisitionReadiness(
        status="ready",
        message="Ready for one controlled BODS bus-position fetch.",
        ready=True,
    )


def parse_bods_bounding_box(value: str) -> BodsBoundingBox:
    """Parse an explicit four-value request scope without inventing Manchester bounds."""

    parts = tuple(part.strip() for part in value.split(","))
    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError(
            "Enter four comma-separated values: min longitude, min latitude, "
            "max longitude, max latitude."
        )
    try:
        values = tuple(Decimal(part) for part in parts)
        return BodsBoundingBox(
            min_longitude=values[0],
            min_latitude=values[1],
            max_longitude=values[2],
            max_latitude=values[3],
        )
    except (InvalidOperation, ValidationError) as exc:
        raise ValueError(
            "The bounding box must contain valid ordered geographic coordinates."
        ) from exc


def scene_relative_path(mode: MapMode) -> Path:
    """Return the fixed workspace-relative scene path for one mode."""

    return MANCHESTER_SCENE_DIRECTORY / _SCENE_FILENAMES[mode]


def load_local_manchester_scene(
    workspace_path: str | Path | None,
    mode: MapMode,
) -> LocalManchesterScene:
    """Load and validate one bounded scene without exposing private paths."""

    if workspace_path is None:
        return _unavailable(
            "workspace_unconfigured",
            "Configure a TrafficTwin workspace to inspect local Manchester evidence.",
        )

    workspace = Path(workspace_path)
    candidate = workspace / scene_relative_path(mode)
    try:
        resolved_workspace = workspace.resolve()
        resolved_candidate = candidate.resolve(strict=True)
    except FileNotFoundError:
        return _unavailable(
            "scene_missing",
            "No accepted local scene is available for this evidence mode.",
        )
    except OSError:
        return _rejected("scene_read_failed", "The local scene could not be inspected safely.")

    if not resolved_candidate.is_relative_to(resolved_workspace):
        return _rejected("scene_path_escaped", "The local scene resolved outside the workspace.")
    if candidate.is_symlink():
        return _rejected(
            "scene_symlink_refused",
            "Symlinked Manchester scene artifacts are not accepted.",
        )
    if not resolved_candidate.is_file():
        return _unavailable(
            "scene_missing",
            "No accepted local scene is available for this evidence mode.",
        )

    try:
        size = resolved_candidate.stat().st_size
    except OSError:
        return _rejected("scene_read_failed", "The local scene could not be inspected safely.")
    if size == 0:
        return _rejected("scene_empty", "The local scene artifact is empty.")
    if size > MANCHESTER_SCENE_MAX_BYTES:
        return _rejected(
            "scene_too_large",
            "The local scene exceeds the bounded Manchester UI artifact size.",
        )

    try:
        payload = resolved_candidate.read_bytes()
    except OSError:
        return _rejected("scene_read_failed", "The local scene could not be read safely.")
    if len(payload) != size:
        return _rejected(
            "scene_read_failed",
            "The local scene changed while it was being read; refresh after publication completes.",
        )
    try:
        scene = ManchesterMapScene.model_validate_json(payload)
    except (ValidationError, ValueError):
        return _rejected(
            "scene_invalid",
            "The local scene failed the MAN-08 integrity contract.",
        )
    if scene.mode != mode:
        return _rejected(
            "scene_mode_mismatch",
            "The local scene does not match the selected evidence mode.",
        )
    return LocalManchesterScene(
        status="available",
        reason="ready",
        message="Validated local Manchester scene loaded.",
        scene=scene,
        artifact_sha256=sha256_hex(payload),
        byte_size=len(payload),
    )


def visible_layer_ids(scene: ManchesterMapScene) -> tuple[str, ...]:
    """Return renderable visible layer IDs in the scene's stable order."""

    return tuple(
        layer.request.layer_id
        for layer in scene.layers
        if layer.visible and layer.local_rendering_available
    )


def selected_layers(
    scene: ManchesterMapScene,
    layer_ids: tuple[str, ...],
) -> tuple[ManchesterMapLayerManifest, ...]:
    """Return an exact visible subset, rejecting unknown or unavailable IDs."""

    if len(set(layer_ids)) != len(layer_ids):
        raise ValueError("selected Manchester layer IDs must be unique")
    available = {layer.request.layer_id: layer for layer in scene.layers if layer.visible}
    unknown = sorted(set(layer_ids) - set(available))
    if unknown:
        raise ValueError(f"selected Manchester layers are unavailable: {unknown}")
    return tuple(available[layer_id] for layer_id in layer_ids)


def build_manchester_deck(
    scene: ManchesterMapScene,
    layer_ids: tuple[str, ...],
) -> pdk.Deck:
    """Build a no-basemap PyDeck view from display-safe admitted points only."""

    layers = selected_layers(scene, layer_ids)
    deck_layers: list[pdk.Layer] = []
    for layer in layers:
        glyph = _SYMBOL_GLYPHS[layer.style.symbol]
        rows = [
            {
                "position": [float(point.longitude), float(point.latitude)],
                "symbol": glyph,
                "accessible_label": (
                    f"{layer.style.legend_label}; "
                    f"{point.geometry_meaning.replace('_', ' ')}; "
                    f"scope {point.geographic_scope.replace('_', ' ')}"
                ),
                "source": layer.request.source,
                "scope": point.geographic_scope,
                "uncertainty_m": (
                    None
                    if point.coordinate_uncertainty_m is None
                    else float(point.coordinate_uncertainty_m)
                ),
            }
            for point in layer.points
        ]
        deck_layers.append(
            pdk.Layer(
                "TextLayer",
                id=f"manchester-{layer.request.layer_id}",
                data=rows,
                get_position="position",
                get_text="symbol",
                get_color=list(layer.style.fill_rgba),
                get_size=layer.style.radius_pixels * 3,
                size_units="pixels",
                get_text_anchor="middle",
                get_alignment_baseline="center",
                pickable=True,
            )
        )

    longitude, latitude, zoom = _view_state(layers)
    return pdk.Deck(
        layers=deck_layers,
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
            "Coordinate uncertainty: {uncertainty_m} m"
        },
        description=(
            "Offline Manchester evidence map. Symbols identify source families; no basemap, "
            "source fusion, map matching, or continuity inference is used."
        ),
    )


def layer_summary_rows(scene: ManchesterMapScene) -> list[dict[str, object]]:
    """Return browser-safe layer reconciliation rows without point identifiers."""

    return [
        {
            "Layer": layer.request.title,
            "Source": layer.request.source,
            "Status": layer.status,
            "Reason": layer.reason,
            "Freshness": layer.freshness_truth_state or "not applicable",
            "Rendered points": layer.counts.points_rendered,
            "Excluded points": layer.counts.points_excluded,
            "Scope": ", ".join(sorted({point.geographic_scope for point in layer.points}))
            or "unavailable",
            "Publication": layer.request.publication_class.value,
            "Snapshot": layer.request.snapshot_id or "unavailable",
        }
        for layer in scene.layers
    ]


def _view_state(
    layers: tuple[ManchesterMapLayerManifest, ...],
) -> tuple[float, float, float]:
    bounds = tuple(layer.bounds for layer in layers if layer.bounds is not None)
    if not bounds:
        return -2.2426, 53.4808, 9.0
    minimum_longitude = min(float(item.min_longitude) for item in bounds)
    maximum_longitude = max(float(item.max_longitude) for item in bounds)
    minimum_latitude = min(float(item.min_latitude) for item in bounds)
    maximum_latitude = max(float(item.max_latitude) for item in bounds)
    span = max(maximum_longitude - minimum_longitude, maximum_latitude - minimum_latitude)
    zoom = 13.0 if span <= 0.02 else 11.0 if span <= 0.1 else 9.0 if span <= 0.5 else 7.0
    return (
        (minimum_longitude + maximum_longitude) / 2,
        (minimum_latitude + maximum_latitude) / 2,
        zoom,
    )


def _unavailable(reason: SceneLoadReason, message: str) -> LocalManchesterScene:
    return LocalManchesterScene(status="unavailable", reason=reason, message=message)


def _rejected(reason: SceneLoadReason, message: str) -> LocalManchesterScene:
    return LocalManchesterScene(status="rejected", reason=reason, message=message)
