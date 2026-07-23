"""Thin UI and local-artifact tests for candidate MAN-08 operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path

import pytest

import traffictwin.ui.manchester_operations as operations
from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.map_layers import (
    SYNTHETIC_ATTRIBUTION,
    ManchesterMapScene,
    MapLayerRequest,
    build_map_layer,
    build_map_scene,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterValidationState,
)
from traffictwin.integration.manchester.spatial import (
    ManchesterSpatialPointEvidence,
    evaluate_spatial_batch,
)
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.navigation_v07 import MANCHESTER_PAGE_SPEC, validate_v07_page_specs

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


def _scene() -> ManchesterMapScene:
    point = ManchesterSpatialPointEvidence(
        source="synthetic",
        source_record_fingerprint="a" * 64,
        point_id="synthetic:central-manchester",
        coordinate_kind="wgs84",
        longitude_epsg4326=Decimal("-2.2426"),
        latitude_epsg4326=Decimal("53.4808"),
        geographic_scope="synthetic",
        scope_basis="synthetic_contract",
        scope_evidence_fingerprint="b" * 64,
        geometry_meaning="synthetic_point",
        source_record_state="eligible",
        coordinate_uncertainty_m=Decimal("3"),
        uncertainty_basis="caller_declared",
        synthetic=True,
    )
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="synthetic",
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="historical",
            evaluated_at_utc=NOW,
            synthetic=True,
        )
    )
    layer = build_map_layer(
        MapLayerRequest(
            layer_id="synthetic-points",
            title="Synthetic points",
            mode="latest_available",
            source="synthetic",
            snapshot_id="synthetic_map-20260723T100000Z-abcdef012345",
            snapshot_fingerprint="c" * 64,
            spatial_report=evaluate_spatial_batch((point,)),
            freshness=freshness,
            publication_class=ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED,
            licence_id="synthetic-fixture",
            attribution_lines=(SYNTHETIC_ATTRIBUTION,),
            synthetic=True,
        )
    )
    return build_map_scene("latest_available", (layer,))


def _write_scene(workspace: Path, scene: ManchesterMapScene, filename: str) -> Path:
    path = workspace / "manchester" / "scenes" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scene.canonical_json(), encoding="utf-8")
    return path


def test_scene_loader_is_fixed_bounded_and_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert operations.load_local_manchester_scene(None, "latest_available").reason == (
        "workspace_unconfigured"
    )
    assert operations.load_local_manchester_scene(tmp_path, "latest_available").reason == (
        "scene_missing"
    )

    path = _write_scene(tmp_path, _scene(), "latest_available.json")
    path.write_text("{}", encoding="utf-8")
    rejected = operations.load_local_manchester_scene(tmp_path, "latest_available")
    assert rejected.status == "rejected"
    assert rejected.reason == "scene_invalid"
    assert str(tmp_path) not in rejected.message

    monkeypatch.setattr(operations, "MANCHESTER_SCENE_MAX_BYTES", 4)
    path.write_text("12345", encoding="utf-8")
    assert operations.load_local_manchester_scene(tmp_path, "latest_available").reason == (
        "scene_too_large"
    )


def test_scene_loader_refuses_symlinks_and_cross_mode_artifacts(tmp_path: Path) -> None:
    target = tmp_path / "manchester" / "scenes" / "inside.json"
    target.parent.mkdir(parents=True)
    target.write_text(_scene().canonical_json(), encoding="utf-8")
    target.with_name("latest_available.json").symlink_to(target)
    assert operations.load_local_manchester_scene(tmp_path, "latest_available").reason == (
        "scene_symlink_refused"
    )

    target.with_name("latest_available.json").unlink()
    _write_scene(tmp_path, _scene(), "historical_replay.json")
    assert operations.load_local_manchester_scene(tmp_path, "historical_replay").reason == (
        "scene_mode_mismatch"
    )


def test_valid_scene_builds_no_basemap_symbol_layer_without_sensitive_point_table(
    tmp_path: Path,
) -> None:
    scene = _scene()
    _write_scene(tmp_path, scene, "latest_available.json")

    loaded = operations.load_local_manchester_scene(tmp_path, "latest_available")
    assert loaded.status == "available"
    assert loaded.scene == scene
    assert loaded.artifact_sha256 is not None
    assert loaded.byte_size is not None
    assert operations.visible_layer_ids(scene) == ("synthetic-points",)

    deck = operations.build_manchester_deck(scene, ("synthetic-points",))
    deck_json = json.loads(deck.to_json())
    assert "mapProvider" not in deck_json
    assert "mapStyle" not in deck_json
    assert deck_json["layers"][0]["@@type"] == "TextLayer"
    assert deck_json["layers"][0]["data"][0]["symbol"] == "✚"
    assert "point_id" not in deck_json["layers"][0]["data"][0]
    assert "synthetic:central-manchester" not in deck.to_json()
    assert operations.layer_summary_rows(scene)[0]["Rendered points"] == 1


def test_layer_selection_refuses_unknown_and_duplicate_ids() -> None:
    scene = _scene()
    with pytest.raises(ValueError, match="unavailable"):
        operations.selected_layers(scene, ("unknown",))
    with pytest.raises(ValueError, match="unique"):
        operations.selected_layers(scene, ("synthetic-points", "synthetic-points"))


def test_live_acquisition_readiness_and_explicit_bounds(tmp_path: Path) -> None:
    assert (
        operations.assess_live_acquisition_readiness(None, api_key_available=True).status
        == "workspace_unconfigured"
    )
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    assert (
        operations.assess_live_acquisition_readiness(ordinary, api_key_available=True).status
        == "workspace_invalid"
    )
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    assert (
        operations.assess_live_acquisition_readiness(workspace, api_key_available=False).status
        == "api_key_missing"
    )
    assert (
        operations.assess_live_acquisition_readiness(workspace, api_key_available=True).ready
        is True
    )

    box = operations.parse_bods_bounding_box("-2.4, 53.3, -2.1, 53.6")
    assert box.min_longitude == Decimal("-2.4")
    assert box.max_latitude == Decimal("53.6")
    for invalid in ("", "-2.4,53.3", "west,53.3,-2.1,53.6", "-2,54,-3,53"):
        with pytest.raises(ValueError):
            operations.parse_bods_bounding_box(invalid)


def test_additive_route_does_not_change_normative_page_inventory() -> None:
    validate_v07_page_specs()
    assert MANCHESTER_PAGE_SPEC.title == "Manchester Operations"
    assert MANCHESTER_PAGE_SPEC.group == "Overview"
    assert MANCHESTER_PAGE_SPEC.url_path == "manchester"


def test_manchester_page_renders_unavailable_state_without_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)

    assert not app.exception
    assert app.session_state["_active_ui_route"] == "manchester"
    assert any(item.value == "Manchester Operations" for item in app.title)
    assert any("Configure a TrafficTwin workspace" in item.value for item in app.info)
    actions = {
        button.label: button.disabled
        for button in app.button
        if button.label in {"Compare with SUMO", "Prepare SUMO baseline"}
    }
    assert actions == {"Compare with SUMO": True, "Prepare SUMO baseline": True}


def test_manchester_page_renders_valid_local_scene(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_scene(tmp_path, _scene(), "latest_available.json")
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)

    assert not app.exception
    assert any(item.label == "Evidence state" and item.value == "available" for item in app.metric)
    assert any(item.label == "Rendered records" and item.value == "1" for item in app.metric)
    assert any("basemap: disabled" in item.value for item in app.caption)
    assert any(SYNTHETIC_ATTRIBUTION in item.value for item in app.caption)
    assert not any("No accepted local scene" in item.value for item in app.info)


def test_live_fetch_form_is_explicit_and_prerequisite_gated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)
    app.segmented_control[0].set_value("live_vehicles")
    app.run(timeout=20)

    assert not app.exception
    fetch = next(button for button in app.button if button.label == "Fetch latest buses")
    assert fetch.disabled is True
    assert any("Set BODS_API_KEY" in item.value for item in app.caption)
    assert any(item.label == "Request bounding box" for item in app.text_input)

    monkeypatch.setenv("BODS_API_KEY", "test-only-not-submitted")
    ready = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)
    ready.segmented_control[0].set_value("live_vehicles")
    ready.run(timeout=20)
    fetch = next(button for button in ready.button if button.label == "Fetch latest buses")
    assert fetch.disabled is False
    assert not ready.exception
