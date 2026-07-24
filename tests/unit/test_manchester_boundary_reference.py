"""Offline integrity tests for the official Manchester boundary references."""

from __future__ import annotations

import json
from importlib import resources as importlib_resources
from pathlib import Path

import pytest
from pydantic import ValidationError

import traffictwin.integration.manchester.boundary_reference as boundary


def test_reviewed_references_pin_current_official_scopes_and_limits() -> None:
    manchester = boundary.boundary_reference("manchester_local_authority")
    greater = boundary.boundary_reference("greater_manchester_combined_authority")

    assert (manchester.official_code, manchester.official_name) == ("E08000003", "Manchester")
    assert (greater.official_code, greater.official_name) == ("E47000001", "Greater Manchester")
    assert manchester.reference_date == greater.reference_date == "December 2025"
    assert manchester.licence_id == greater.licence_id == "OGL-3.0"
    assert manchester.attribution_lines == (boundary.OS_ATTRIBUTION, boundary.ONS_ATTRIBUTION)
    for reference in (manchester, greater):
        assert reference.map_context_available is True
        assert reference.public_display_available is True
        assert reference.remote_basemap_available is False
        assert reference.road_network_available is False
        assert reference.sensor_coverage_available is False
        assert reference.scientific_clipping_available is False


def test_packaged_boundaries_are_hash_verified_closed_polygons() -> None:
    features = boundary.load_boundary_features()

    assert tuple(item.reference.scope for item in features) == (
        "greater_manchester_combined_authority",
        "manchester_local_authority",
    )
    assert all(item.coordinates[0][0] == item.coordinates[0][-1] for item in features)
    assert len(features[0].coordinates[0]) == 404
    assert len(features[1].coordinates[0]) == 159
    assert all(item.source_asset_sha256 == item.reference.asset_sha256 for item in features)


def test_renderer_payload_is_explicitly_context_only() -> None:
    feature = boundary.load_boundary_feature("manchester_local_authority")
    payload = feature.geojson()

    assert payload["type"] == "Feature"
    properties = payload["properties"]
    assert isinstance(properties, dict)
    assert properties["official_code"] == "E08000003"
    assert properties["scope"] == "manchester_local_authority"
    assert "display context only" in str(properties["accessible_label"])
    assert "road" not in json.dumps(payload).lower()


def test_reference_identity_and_capability_claims_cannot_be_mutated() -> None:
    reference = boundary.boundary_reference("manchester_local_authority")
    payload = reference.model_dump(mode="json")

    for key, value in (
        ("official_code", "E00000000"),
        ("road_network_available", True),
        ("scientific_clipping_available", True),
        ("remote_basemap_available", True),
        ("asset_sha256", "0" * 64),
    ):
        changed = dict(payload)
        changed[key] = value
        with pytest.raises(ValidationError):
            boundary.ManchesterBoundaryReference.model_validate(changed)


def test_tampered_packaged_asset_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "package"
    data = package / "boundary_data"
    data.mkdir(parents=True)
    (data / "manchester_local_authority.geojson").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(importlib_resources, "files", lambda _package: package)

    with pytest.raises(boundary.ManchesterBoundaryError) as excinfo:
        boundary.load_boundary_feature("manchester_local_authority")

    assert excinfo.value.code == "BOUNDARY_ASSET_IDENTITY_MISMATCH"


def test_boundary_attribution_is_exact_and_stable() -> None:
    assert boundary.boundary_attributions() == (
        boundary.OS_ATTRIBUTION,
        boundary.ONS_ATTRIBUTION,
    )
