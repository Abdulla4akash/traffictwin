"""Offline deterministic tests for the static Manchester context service."""

from __future__ import annotations

import pytest

from traffictwin.integration.manchester.boundary_reference import ManchesterBoundaryError
from traffictwin.ui.manchester_context import load_manchester_context


def test_load_manchester_context_is_deterministic_and_offline() -> None:
    first = load_manchester_context()
    second = load_manchester_context()

    assert first.greater_manchester.reference.scope == "greater_manchester_combined_authority"
    assert first.manchester.reference.scope == "manchester_local_authority"
    assert first.greater_manchester.reference.official_code == "E47000001"
    assert first.manchester.reference.official_code == "E08000003"
    assert first.attribution == second.attribution
    assert "Contains OS data" in first.attribution[0]
    assert "Office for National Statistics" in first.attribution[1]
    # Deterministic deck
    assert len(first.deck.layers) == 2
    assert len(second.deck.layers) == 2
    assert first.deck.layers[0].id == "ons-boundary-greater_manchester_combined_authority"
    assert first.deck.layers[1].id == "ons-boundary-manchester_local_authority"
    # Offline: no basemap
    assert first.deck.map_provider is None
    assert first.deck.map_style is None
    # ViewState fitted to Greater Manchester (span ~0.82 => zoom 7.5)
    view = first.deck.initial_view_state
    assert view is not None
    assert -3.0 < view.longitude < -1.5
    assert 53.0 < view.latitude < 54.0
    assert 7.0 <= view.zoom <= 9.0


def test_manchester_context_provenance_is_exact() -> None:
    context = load_manchester_context()

    assert context.greater_manchester.reference.reference_date == "December 2025"
    assert context.manchester.reference.reference_date == "December 2025"
    assert context.greater_manchester.reference.licence_id == "OGL-3.0"
    assert context.manchester.reference.licence_id == "OGL-3.0"
    assert context.greater_manchester.reference.source_owner == "Office for National Statistics"
    assert context.greater_manchester.display_only is True
    assert context.manchester.display_only is True
    # GeoJSON payload is context-only
    payload = context.greater_manchester.geojson()
    assert "display context only" in str(payload["properties"]["accessible_label"])  # type: ignore[index]
    assert payload["properties"]["official_code"] == "E47000001"  # type: ignore[index]


def test_manchester_context_requires_no_credentials_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("MAPBOX_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    monkeypatch.delenv("BODS_API_KEY", raising=False)

    context = load_manchester_context()

    assert context.deck is not None
    assert context.greater_manchester.reference.map_context_available is True
    assert context.greater_manchester.reference.remote_basemap_available is False


def test_malformed_boundary_is_handled_by_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate a missing asset by patching load_boundary_features to raise
    import traffictwin.ui.manchester_context as ctx_module

    def _raise() -> None:
        raise ManchesterBoundaryError("BOUNDARY_ASSET_UNAVAILABLE", "missing")

    monkeypatch.setattr(ctx_module, "load_boundary_features", _raise)

    with pytest.raises(ManchesterBoundaryError) as excinfo:
        load_manchester_context()

    assert excinfo.value.code == "BOUNDARY_ASSET_UNAVAILABLE"
