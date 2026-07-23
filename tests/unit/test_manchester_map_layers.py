"""Offline map-layer evidence for the candidate MAN-08 service."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    SourceFreshnessEvaluation,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.map_layers import (
    SYNTHETIC_ATTRIBUTION,
    ManchesterMapError,
    ManchesterMapLayerManifest,
    ManchesterMapScene,
    MapLayerRequest,
    build_map_layer,
    build_map_scene,
    map_layer_style,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterValidationState,
)
from traffictwin.integration.manchester.spatial import (
    ManchesterSpatialPointEvidence,
    evaluate_spatial_batch,
)

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
SNAPSHOT = "synthetic_map-20260723T090000Z-abcdef012345"


def spatial_item(
    *,
    source_record: str = "a" * 64,
    point_id: str = "synthetic:one",
    longitude: str = "-2.2426",
    latitude: str = "53.4808",
    state: str = "eligible",
) -> ManchesterSpatialPointEvidence:
    return ManchesterSpatialPointEvidence.model_validate(
        {
            "source": "synthetic",
            "source_record_fingerprint": source_record,
            "point_id": point_id,
            "coordinate_kind": "wgs84",
            "longitude_epsg4326": Decimal(longitude),
            "latitude_epsg4326": Decimal(latitude),
            "geographic_scope": "synthetic",
            "scope_basis": "synthetic_contract",
            "scope_evidence_fingerprint": "b" * 64,
            "geometry_meaning": "synthetic_point",
            "source_record_state": state,
            "coordinate_uncertainty_m": Decimal("3"),
            "uncertainty_basis": "caller_declared",
            "synthetic": True,
        }
    )


def synthetic_freshness(*, unavailable: bool = False) -> SourceFreshnessEvaluation:
    return evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="synthetic",
            evidence_validation=(
                ManchesterValidationState.REJECTED
                if unavailable
                else ManchesterValidationState.ACCEPTED
            ),
            snapshot_available=True,
            use_mode="historical",
            evaluated_at_utc=NOW,
            synthetic=True,
        )
    )


def request(**changes: object) -> MapLayerRequest:
    values: dict[str, object] = {
        "layer_id": "synthetic-points",
        "title": "Synthetic points",
        "mode": "latest_available",
        "source": "synthetic",
        "snapshot_id": SNAPSHOT,
        "snapshot_fingerprint": "c" * 64,
        "spatial_report": evaluate_spatial_batch((spatial_item(),)),
        "freshness": synthetic_freshness(),
        "publication_class": ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED,
        "licence_id": "synthetic-fixture",
        "attribution_lines": (SYNTHETIC_ATTRIBUTION,),
        "synthetic": True,
    }
    values.update(changes)
    return MapLayerRequest.model_validate(values)


def test_available_layer_contains_only_admitted_exact_points() -> None:
    layer = build_map_layer(request())

    assert layer.status == "available"
    assert layer.reason == "ready"
    assert layer.visible is True
    assert layer.local_rendering_available is True
    assert layer.public_export_available is True
    assert layer.basemap_provider is None
    assert layer.external_network_required is False
    assert len(layer.points) == 1
    assert layer.points[0].longitude == Decimal("-2.2426")
    assert layer.points[0].map_matched is False
    assert layer.bounds is not None
    assert layer.bounds.min_latitude == Decimal("53.4808")


def test_partial_spatial_report_renders_only_admitted_points() -> None:
    report = evaluate_spatial_batch(
        (
            spatial_item(),
            spatial_item(
                source_record="d" * 64,
                point_id="synthetic:two",
                state="inactive",
            ),
        )
    )
    layer = build_map_layer(request(spatial_report=report))

    assert layer.status == "partial"
    assert layer.reason == "spatial_admission_partial"
    assert layer.counts.spatial_inputs == 2
    assert layer.counts.points_rendered == 1
    assert layer.counts.points_excluded == 1


def test_missing_snapshot_spatial_failure_and_freshness_failure_disable_layer() -> None:
    missing = build_map_layer(request(snapshot_id=None, snapshot_fingerprint=None))
    assert missing.status == "unavailable"
    assert missing.reason == "snapshot_unavailable"
    assert missing.points
    assert missing.visible is False

    excluded_report = evaluate_spatial_batch((spatial_item(state="inactive"),))
    spatial = build_map_layer(request(spatial_report=excluded_report))
    assert spatial.reason == "spatial_admission_unavailable"
    assert spatial.points == ()

    freshness = build_map_layer(request(freshness=synthetic_freshness(unavailable=True)))
    assert freshness.reason == "freshness_unavailable"
    assert freshness.local_rendering_available is False


def test_private_snapshot_can_render_locally_but_never_export() -> None:
    layer = build_map_layer(request(publication_class=ManchesterPublicationClass.PRIVATE))
    assert layer.local_rendering_available is True
    assert layer.public_export_available is False


def test_requested_hidden_layer_is_available_but_not_visible() -> None:
    layer = build_map_layer(request(requested_visible=False))
    assert layer.status == "available"
    assert layer.local_rendering_available is True
    assert layer.visible is False


def test_stale_bods_layer_remains_visible_with_stale_badge() -> None:
    evidence = ManchesterSpatialPointEvidence(
        source="bods_siri_vm",
        source_record_fingerprint="e" * 64,
        point_id="bods:vehicle-token",
        coordinate_kind="wgs84",
        longitude_epsg4326=Decimal("-2.25"),
        latitude_epsg4326=Decimal("53.49"),
        geographic_scope="request_bounding_box",
        scope_basis="bods_request_bounds",
        scope_evidence_fingerprint="f" * 64,
        geometry_meaning="transit_vehicle_position",
        source_record_state="eligible",
        uncertainty_basis="source_not_stated",
        synthetic=False,
    )
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="bods_siri_vm",
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="live",
            evaluated_at_utc=NOW + timedelta(seconds=61),
            observed_at_utc=NOW,
            valid_until_utc=NOW + timedelta(seconds=90),
            synthetic=False,
        )
    )
    layer = build_map_layer(
        MapLayerRequest(
            layer_id="transit-vehicles",
            title="Transit vehicles",
            mode="live_vehicles",
            source="bods_siri_vm",
            snapshot_id="bods-20260723T100000Z-abcdef012345",
            snapshot_fingerprint="1" * 64,
            spatial_report=evaluate_spatial_batch((evidence,)),
            freshness=freshness,
            publication_class=ManchesterPublicationClass.PRIVATE,
            licence_id="private-bods",
            attribution_lines=("Private BODS SIRI-VM research snapshot.",),
            synthetic=False,
        )
    )
    assert layer.status == "partial"
    assert layer.reason == "stale_cached_evidence"
    assert layer.visible is True
    assert layer.stale_badge_visible is True
    assert layer.public_export_available is False


def test_ogl_sources_require_the_reviewed_licence_uri() -> None:
    data = request().model_dump(mode="python")
    data.update(
        {
            "source": "webtris",
            "synthetic": False,
            "licence_id": "OGL",
            "attribution_lines": ("Contains National Highways WebTRIS data.",),
        }
    )
    with pytest.raises(ValidationError, match="OGL v3 URI"):
        MapLayerRequest.model_validate(data)


def test_mixed_spatial_sources_and_wrong_freshness_are_refused() -> None:
    spatial = request().spatial_report.model_dump(mode="python")
    spatial["results"][0]["source"] = "webtris"
    spatial["results"][0]["policy"] = (
        request().spatial_report.results[0].policy.model_copy(update={"source": "webtris"})
    )
    with pytest.raises(ValidationError):
        MapLayerRequest.model_validate(
            {**request().model_dump(mode="python"), "spatial_report": spatial}
        )

    dft_freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="dft_count_points",
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="historical",
            evaluated_at_utc=NOW,
            synthetic=False,
        )
    )
    with pytest.raises(ValidationError, match="freshness source"):
        request(freshness=dft_freshness)

    with pytest.raises(ValidationError, match="explicit freshness"):
        request(freshness=None)


def test_frozen_styles_use_symbol_and_text_not_only_colour() -> None:
    assert map_layer_style("dft").symbol == "circle"
    assert map_layer_style("webtris").symbol == "square"
    assert map_layer_style("tfgm_signals").symbol == "diamond"
    assert map_layer_style("bods_siri_vm").symbol == "triangle"
    for source in (
        "dft",
        "webtris",
        "tfgm_signals",
        "bods_siri_vm",
        "randy_tos",
        "sumo_vec",
        "analysis_rsu",
        "synthetic",
    ):
        style = map_layer_style(source)
        assert style.legend_label
        assert style.accessible_description
        assert style.colour_is_sole_meaning is False


def test_scene_unions_visible_attribution_and_never_fuses_scopes() -> None:
    first = build_map_layer(request(layer_id="alpha"))
    second = build_map_layer(
        request(
            layer_id="beta",
            snapshot_id="synthetic_map-20260723T090001Z-bcdef0123456",
            snapshot_fingerprint="2" * 64,
            spatial_report=evaluate_spatial_batch(
                (
                    spatial_item(
                        source_record="3" * 64,
                        point_id="synthetic:three",
                        longitude="-2.20",
                        latitude="53.50",
                    ),
                )
            ),
        )
    )
    scene = build_map_scene("latest_available", (second, first))

    assert scene.status == "available"
    assert scene.visible_layer_ids == ("alpha", "beta")
    assert scene.attributions == (SYNTHETIC_ATTRIBUTION,)
    assert scene.scopes == ("synthetic",)
    assert scene.bounds is not None
    assert scene.bounds.min_longitude == Decimal("-2.2426")
    assert scene.bounds.max_latitude == Decimal("53.50")
    assert scene.basemap_provider is None
    assert scene.source_fusion_performed is False
    assert scene.cross_scope_totals_available is False


def test_hidden_layer_contributes_no_scene_attribution_or_bounds() -> None:
    hidden = build_map_layer(request(requested_visible=False))
    scene = build_map_scene("latest_available", (hidden,))
    assert scene.status == "available"
    assert scene.visible_layer_ids == ()
    assert scene.attributions == ()
    assert scene.bounds is None


def test_duplicate_layer_ids_and_cross_mode_scenes_are_refused() -> None:
    layer = build_map_layer(request())
    with pytest.raises(ManchesterMapError, match="duplicate"):
        build_map_scene("latest_available", (layer, layer))
    with pytest.raises(ManchesterMapError, match="mode"):
        build_map_scene("historical_replay", (layer,))


def test_manifest_and_scene_mutations_fail_closed() -> None:
    layer = build_map_layer(request())
    mutations = (
        ("visible", False),
        ("spatial_report_fingerprint", "0" * 64),
        ("freshness_fingerprint", "0" * 64),
        ("public_export_available", False),
        ("stale_badge_visible", True),
    )
    for field, value in mutations:
        payload = json.loads(layer.canonical_json())
        payload[field] = value
        with pytest.raises(ValidationError):
            ManchesterMapLayerManifest.model_validate_json(json.dumps(payload))

    scene = build_map_scene("latest_available", (layer,))
    payload = json.loads(scene.canonical_json())
    payload["attributions"] = []
    with pytest.raises(ValidationError):
        ManchesterMapScene.model_validate_json(json.dumps(payload))


def test_models_are_strict_frozen_and_deterministic() -> None:
    layer = build_map_layer(request())
    round_trip = ManchesterMapLayerManifest.model_validate_json(layer.canonical_json())
    assert round_trip == layer
    assert round_trip.fingerprint() == layer.fingerprint()
    with pytest.raises(ValidationError):
        MapLayerRequest.model_validate({**request().model_dump(mode="python"), "unexpected": True})
    with pytest.raises(ValidationError):
        layer.visible = False  # type: ignore[misc]
