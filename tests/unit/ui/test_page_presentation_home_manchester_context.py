"""AppTest coverage for the static Manchester geographic context on Home."""

from __future__ import annotations

import tempfile
from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.integration.manchester.boundary_reference import ManchesterBoundaryError
from traffictwin.ui.state import default_session_state

HOME_APP = "src/traffictwin/ui/app_pages/home.py"


@pytest.fixture(autouse=True)
def _isolate_traffictwin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_TOS_DATA_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_FIXTURE_PATH", raising=False)


def _home_app() -> AppTest:
    app = AppTest.from_file(HOME_APP)
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _scene_payload() -> str:
    # Minimal valid scene with one synthetic point, matching test_manchester_operations helper
    from datetime import UTC, datetime
    from decimal import Decimal

    from traffictwin.integration.manchester.freshness import (
        FreshnessEvaluationRequest,
        evaluate_source_freshness,
    )
    from traffictwin.integration.manchester.map_layers import (
        SYNTHETIC_ATTRIBUTION,
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
            evaluated_at_utc=datetime(2026, 7, 23, 10, 0, tzinfo=UTC),
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
    scene = build_map_scene("latest_available", (layer,))
    return scene.canonical_json()


def test_home_shows_static_context_when_no_accepted_scene() -> None:
    app = _home_app().run(timeout=30)

    assert not app.exception
    # Static context should be visible when no scene
    markdown_text = " ".join(str(m.value) for m in app.markdown)
    caption_text = " ".join(str(c.value) for c in app.caption)
    assert "Manchester study-area context" in markdown_text
    assert (
        "Static geographic context — no live or observed traffic scene is loaded." in caption_text
    )
    # Provenance must be visible and exact
    assert "E47000001" in caption_text
    assert "E08000003" in caption_text
    assert "December 2025" in caption_text
    assert "Office for National Statistics" in caption_text
    assert "Open Government Licence v.3.0" in caption_text
    # Wording must not claim live traffic — pin the negative contract precisely
    assert "Live Manchester map" not in markdown_text
    assert "Live Manchester map" not in caption_text
    # Unavailable explanation must remain visible
    assert "No demo workspace is configured — create one to begin." in markdown_text
    # Map chart must be emitted — verify via AppTest deck element
    decks = app.get("deck_gl_json_chart")
    assert len(decks) >= 1
    # Deeper deck checks are covered by test_manchester_context service tests


def test_home_accepted_scene_takes_precedence_over_static_context() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "with-scene"
        initialise_workspace(workspace)
        # Add a valid Manchester scene so Home sees an accepted scene
        scene_path = workspace / "manchester" / "scenes" / "latest_available.json"
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(_scene_payload(), encoding="utf-8")

        app = _home_app()
        app.session_state["_active_demo_workspace_path"] = str(workspace)
        app.session_state["active_registry_path"] = str(workspace / "registry.sqlite")
        app.run(timeout=30)

        assert not app.exception
        markdown_text = " ".join(str(m.value) for m in app.markdown)
        caption_text = " ".join(str(c.value) for c in app.caption)
        # Accepted scene rendering should be present
        assert (
            "Latest accepted local scene" in caption_text or "Accepted local scene" in caption_text
        )
        # Static fallback must be absent when accepted scene is available
        assert "Manchester study-area context — static geographic reference" not in markdown_text
        # The accepted-scene deck should be present
        decks = app.get("deck_gl_json_chart")
        assert len(decks) >= 1


def test_home_static_context_with_synthetic_demo_workspace() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "synthetic-demo"
        initialise_workspace(workspace)

        app = _home_app()
        app.session_state["_active_demo_workspace_path"] = str(workspace)
        app.session_state["active_registry_path"] = str(workspace / "registry.sqlite")
        app.run(timeout=30)

        assert not app.exception
        markdown_text = " ".join(str(m.value) for m in app.markdown)
        caption_text = " ".join(str(c.value) for c in app.caption)
        # Static context must still be shown
        assert "Manchester study-area context" in markdown_text
        assert (
            "Static geographic context — no live or observed traffic scene is loaded."
            in caption_text
        )
        # Synthetic distinction must be explicit — pin the exact sentence
        assert (
            "Synthetic demo workspace is active, but the boundary above remains "
            "geographic context only — it does not represent Manchester observed traffic "
            "or a calibrated simulation." in caption_text
        )
        # Visible local layers must remain 0
        assert any(m.label == "Visible local layers" and str(m.value) == "0" for m in app.metric)
        decks = app.get("deck_gl_json_chart")
        assert len(decks) >= 1


def test_home_does_not_crash_when_boundary_asset_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Patch the loader to simulate missing/invalid asset
    import traffictwin.ui.pages.home as home_module

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise ManchesterBoundaryError("BOUNDARY_ASSET_UNAVAILABLE", "missing")

    monkeypatch.setattr(home_module, "load_manchester_context", _raise)

    app = _home_app().run(timeout=30)

    assert not app.exception
    caption_text = " ".join(str(c.value) for c in app.caption)
    # Fallback must be truthful and not crash
    assert "Static geographic context unavailable" in caption_text
    assert "no live or observed traffic scene" in caption_text.lower()
    # Home should still show the unavailable explanation
    markdown_text = " ".join(str(m.value) for m in app.markdown)
    assert "No demo workspace is configured" in markdown_text or "No accepted" in markdown_text
    # No static deck should be rendered in failure mode (still may have no deck or empty)
    # But page must not crash — verified by no exception
