"""Thin UI and local-artifact tests for candidate MAN-08 operations."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path

import pytest
from tests.unit.test_manchester_dft_acquisition import (
    acquire as acquire_dft,
)
from tests.unit.test_manchester_dft_acquisition import (
    envelope_bytes as dft_envelope_bytes,
)
from tests.unit.test_manchester_dft_acquisition import (
    make_request as make_dft_request,
)
from tests.unit.test_manchester_dft_acquisition import (
    raw_row as dft_raw_row,
)
from tests.unit.test_manchester_webtris_acquisition import (
    acquire,
    default_responses,
    full_day_rows,
    make_request,
    paged,
)

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
PACK = Path("docs/reference/generated/vec_dissertation_pack").resolve()


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


def test_scene_filters_are_exact_display_only_and_reconcile_per_source() -> None:
    scene = _scene()
    options = operations.scene_filter_options(scene, ("synthetic-points",))
    assert options.geographic_scopes == ("synthetic",)
    assert options.freshness_states == ("synthetic",)

    visible = operations.filter_manchester_scene(
        scene,
        ("synthetic-points",),
        geographic_scopes=options.geographic_scopes,
        freshness_states=options.freshness_states,
    )
    assert visible.has_displayed_points is True
    assert visible.visible_scopes == ("synthetic",)
    assert visible.attributions == (SYNTHETIC_ATTRIBUTION,)
    assert visible.layers[0].hidden_by_filters == 0
    summary = operations.filtered_source_summary_rows(visible)
    assert summary == [
        {
            "Layer": "Synthetic points",
            "Source": "synthetic",
            "Evidence state": "available",
            "Freshness": "synthetic",
            "Accepted map points": 1,
            "Displayed map points": 1,
            "Hidden by filters": 0,
            "Source exclusions": 0,
            "Displayed scope": "synthetic",
            "Publication": "redistributable_derived",
            "Snapshot": "synthetic_map-20260723T100000Z-abcdef012345",
        }
    ]

    hidden_by_scope = operations.filter_manchester_scene(
        scene,
        ("synthetic-points",),
        geographic_scopes=(),
        freshness_states=("synthetic",),
    )
    assert hidden_by_scope.has_displayed_points is False
    assert hidden_by_scope.layers[0].hidden_by_scope == 1
    assert hidden_by_scope.layers[0].hidden_by_freshness == 0
    assert hidden_by_scope.attributions == ()
    assert hidden_by_scope.visible_scopes == ()
    assert operations.filtered_source_summary_rows(hidden_by_scope)[0]["Displayed map points"] == 0

    hidden_by_freshness = operations.filter_manchester_scene(
        scene,
        ("synthetic-points",),
        geographic_scopes=("synthetic",),
        freshness_states=(),
    )
    assert hidden_by_freshness.layers[0].hidden_by_scope == 0
    assert hidden_by_freshness.layers[0].hidden_by_freshness == 1


def test_scene_filters_refuse_unknown_and_duplicate_values() -> None:
    scene = _scene()
    with pytest.raises(ValueError, match="geographic scopes.*unavailable"):
        operations.filter_manchester_scene(
            scene,
            ("synthetic-points",),
            geographic_scopes=("greater_manchester",),
            freshness_states=("synthetic",),
        )
    with pytest.raises(ValueError, match="freshness states.*unavailable"):
        operations.filter_manchester_scene(
            scene,
            ("synthetic-points",),
            geographic_scopes=("synthetic",),
            freshness_states=("historical",),
        )
    with pytest.raises(ValueError, match="must be unique"):
        operations.filter_manchester_scene(
            scene,
            ("synthetic-points",),
            geographic_scopes=("synthetic", "synthetic"),
            freshness_states=("synthetic",),
        )


def test_filtered_scene_outputs_refuse_tampered_reconciliation() -> None:
    scene = _scene()
    filtered = operations.filter_manchester_scene(
        scene,
        ("synthetic-points",),
        geographic_scopes=("synthetic",),
        freshness_states=("synthetic",),
    )
    tampered = replace(
        filtered,
        layers=(replace(filtered.layers[0], hidden_by_scope=1),),
    )
    with pytest.raises(ValueError, match="exactly re-derived"):
        operations.build_filtered_manchester_deck(tampered)
    with pytest.raises(ValueError, match="exactly re-derived"):
        operations.filtered_source_summary_rows(tampered)


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
    assert (
        operations.assess_national_highways_acquisition_readiness(
            workspace,
            subscription_key_available=False,
        ).status
        == "api_key_missing"
    )
    assert operations.assess_national_highways_acquisition_readiness(
        workspace,
        subscription_key_available=True,
    ).ready

    box = operations.parse_bods_bounding_box("-2.4, 53.3, -2.1, 53.6")
    assert box.min_longitude == Decimal("-2.4")
    assert box.max_latitude == Decimal("53.6")
    for invalid in ("", "-2.4,53.3", "west,53.3,-2.1,53.6", "-2,54,-3,53"):
        with pytest.raises(ValueError):
            operations.parse_bods_bounding_box(invalid)


def test_local_webtris_catalogue_and_labels_are_bounded_and_display_safe(
    tmp_path: Path,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    empty = operations.load_local_webtris_catalogue(workspace)
    assert empty.status == "unavailable"
    assert empty.reason == "no_accepted_daily_reports"

    acquired = acquire(workspace, make_request("daily_report"), default_responses())
    loaded = operations.load_local_webtris_catalogue(workspace)
    assert loaded.status == "available"
    assert loaded.catalogue is not None
    options = operations.accepted_webtris_daily_options(loaded.catalogue)
    assert len(options) == 1
    assert options[0].snapshot_id == acquired.snapshot_id
    label = operations.webtris_snapshot_label(options[0])
    assert "site 34" in label
    assert "2026-03-01" in label
    assert acquired.snapshot_id[-12:] in label
    assert str(workspace) not in label


def test_local_webtris_timeseries_keeps_missing_measurements_as_chart_gaps(
    tmp_path: Path,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    responses = default_responses()
    responses["daily"] = paged(full_day_rows(missing_intervals={7}), 96)
    acquired = acquire(
        workspace,
        make_request(
            "daily_report",
            admitted_warning_codes=("MISSING_INTERVAL_MEASUREMENTS",),
        ),
        responses,
    )

    empty_filter = operations.load_local_webtris_timeseries(workspace, acquired.snapshot_id, ())
    assert empty_filter.reason == "measurement_filter_empty"
    loaded = operations.load_local_webtris_timeseries(
        workspace,
        acquired.snapshot_id,
        ("missing", "observed"),
    )
    assert loaded.status == "available"
    assert loaded.result is not None
    assert loaded.result.counts.rows_admitted == 96
    assert loaded.result.counts.rows_missing_measurement_admitted == 1
    chart_rows = operations.webtris_chart_rows(loaded.result)
    assert len(chart_rows) == 96
    assert chart_rows[7]["Measurement state"] == "missing"
    assert chart_rows[7]["Volume"] is None
    assert chart_rows[7]["Average speed (mph)"] is None
    assert chart_rows[8]["Volume"] == 1


def test_local_dft_catalogue_filters_and_discrete_survey_rows(
    tmp_path: Path,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    empty = operations.load_local_dft_catalogue(workspace)
    assert empty.status == "unavailable"
    assert empty.reason == "no_accepted_raw_counts"

    rows = [
        dft_raw_row(),
        dft_raw_row(
            id=1002,
            direction_of_travel="S",
            cars_and_taxis=80,
            all_motor_vehicles=129,
        ),
        dft_raw_row(id=1003, hour=13, cars_and_taxis=None),
    ]
    acquired = acquire_dft(
        workspace,
        {1: dft_envelope_bytes(rows, 1, 1, 3, 3)},
        make_dft_request(page_size=3, accept_with_warnings=True),
    )
    loaded = operations.load_local_dft_catalogue(workspace)
    assert loaded.status == "available"
    assert loaded.catalogue is not None
    snapshots = operations.accepted_dft_raw_count_options(loaded.catalogue)
    assert len(snapshots) == 1
    assert snapshots[0].snapshot_id == acquired.snapshot_id
    assert str(workspace) not in operations.dft_snapshot_label(snapshots[0])

    loaded_options = operations.load_local_dft_survey_options(workspace, acquired.snapshot_id)
    assert loaded_options.status == "available"
    assert loaded_options.options is not None
    assert loaded_options.options.count_point_ids == (12345,)
    assert loaded_options.options.directions == ("N", "S")
    assert loaded_options.options.hours == (12, 13)

    empty_filter = operations.load_local_dft_survey_view(
        workspace,
        acquired.snapshot_id,
        count_point_id=12345,
        directions=(),
        count_date=date(2004, 5, 21),
        hours=(12,),
        vehicle_class="cars_and_taxis",
    )
    assert empty_filter.reason == "filter_selection_empty"
    selected = operations.load_local_dft_survey_view(
        workspace,
        acquired.snapshot_id,
        count_point_id=12345,
        directions=("N", "S"),
        count_date=date(2004, 5, 21),
        hours=(12, 13),
        vehicle_class="cars_and_taxis",
    )
    assert selected.status == "available"
    assert selected.view is not None
    assert selected.view.counts.selected_records == 3
    assert selected.view.counts.values_present == 2
    assert selected.view.counts.values_missing == 1
    chart_rows = operations.dft_survey_chart_rows(selected.view)
    assert sum(row["Count"] is None for row in chart_rows) == 1
    table_rows = operations.dft_survey_table_rows(selected.view)
    assert sum(row["Value state"] == "missing" for row in table_rows) == 1
    assert selected.view.continuous_time_series_available is False


def test_optional_randy_case_study_is_integrity_gated_and_display_safe(
    tmp_path: Path,
) -> None:
    unconfigured = operations.load_local_randy_case_study(None)
    assert unconfigured.status == "unconfigured"
    assert unconfigured.report is None

    rejected = operations.load_local_randy_case_study(tmp_path / "missing")
    assert rejected.status == "rejected"
    assert rejected.report is None
    assert str(tmp_path) not in rejected.message

    loaded = operations.load_local_randy_case_study(PACK)
    assert loaded.status == "available"
    assert loaded.report is not None
    assert len(operations.randy_sample_rows(loaded.report)) == 3
    metric_rows = operations.randy_metric_rows(loaded.report)
    unavailable = next(row for row in metric_rows if row["Metric"] == "task.completion.rate")
    assert unavailable["Value"] == "unavailable"
    assert unavailable["Missing evidence"] == "physical completion evidence is absent"
    display_payload = json.dumps(
        {
            "samples": operations.randy_sample_rows(loaded.report),
            "metrics": metric_rows,
        },
        sort_keys=True,
    )
    assert str(PACK) not in display_payload
    assert "sumo_vehicle_id" not in display_payload


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
    assert any(item.label == "Accepted map points" and item.value == "1" for item in app.metric)
    assert any(item.label == "Displayed map points" and item.value == "1" for item in app.metric)
    assert any(item.label == "Geographic scope" for item in app.pills)
    assert any(item.label == "Freshness state" for item in app.pills)
    assert any("basemap: disabled" in item.value for item in app.caption)
    assert any(SYNTHETIC_ATTRIBUTION in item.value for item in app.caption)
    assert not any("No accepted local scene" in item.value for item in app.info)

    scope_filter = next(item for item in app.pills if item.label == "Geographic scope")
    scope_filter.set_value([])
    app.run(timeout=20)
    assert not app.exception
    assert any(
        "selected display filters contain no admitted map points" in item.value
        for item in app.warning
    )
    assert any(item.label == "Displayed map points" and item.value == "0" for item in app.metric)
    assert any("Attribution: none displayed" in item.value for item in app.caption)


def test_manchester_page_exposes_explicit_non_live_source_refresh_forms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]

    latest = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)
    assert not latest.exception
    latest_buttons = {button.label: button.disabled for button in latest.button}
    assert latest_buttons["Fetch site, report, and quality"] is False
    assert latest_buttons["Fetch signal locations"] is False
    assert any(item.label == "WebTRIS site ID" for item in latest.text_input)
    assert any(item.label == "Source report date" for item in latest.date_input)
    assert any(
        "Neither source is live city-road telemetry" in item.value for item in latest.caption
    )

    latest.segmented_control[0].set_value("historical_replay")
    latest.run(timeout=20)
    assert not latest.exception
    historical_buttons = {button.label: button.disabled for button in latest.button}
    assert historical_buttons["Fetch selected historical rows"] is False
    number_labels = {item.label for item in latest.number_input}
    assert {"Raw-count row ID", "Count-point row ID", "AADF row ID"}.issubset(number_labels)
    assert any("not live traffic" in item.value for item in latest.caption)


def test_historical_mode_renders_accepted_webtris_controls_and_charts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    acquire(workspace, make_request("daily_report"), default_responses())
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)
    app.segmented_control[0].set_value("historical_replay")
    app.run(timeout=20)

    assert not app.exception
    assert any(item.value == "WebTRIS historical intervals" for item in app.subheader)
    assert any(item.label == "Accepted WebTRIS site-day" for item in app.selectbox)
    assert any(item.label == "Measurement state" for item in app.pills)
    assert any(item.label == "Admitted intervals" and item.value == "96" for item in app.metric)
    assert any("source clock strings" in item.value for item in app.caption)


def test_historical_mode_renders_accepted_dft_survey_controls_and_discrete_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    rows = [dft_raw_row(), dft_raw_row(id=1002, hour=13)]
    acquire_dft(
        workspace,
        {1: dft_envelope_bytes(rows, 1, 1, 2, 2)},
        make_dft_request(page_size=2),
    )
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)
    app.segmented_control[0].set_value("historical_replay")
    app.run(timeout=20)

    assert not app.exception
    assert any(item.value == "DfT historical survey counts" for item in app.subheader)
    labels = {item.label for item in app.selectbox}
    assert {
        "Accepted DfT raw-count snapshot",
        "Count point",
        "Survey date",
        "Vehicle class",
    }.issubset(labels)
    assert any(item.label == "Direction" for item in app.pills)
    assert any(item.label == "Local-clock hour labels" for item in app.multiselect)
    assert any(item.label == "Selected survey rows" and item.value == "2" for item in app.metric)
    assert any("discrete source survey rows only" in item.value for item in app.caption)


def test_manchester_page_renders_optional_non_geographic_randy_case_study(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_scene(tmp_path, _scene(), "latest_available.json")
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path))
    monkeypatch.setenv("TRAFFICTWIN_RANDY_PACK_PATH", str(PACK))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)

    assert not app.exception
    assert any(item.value == "Randy/TOS case-study evidence" for item in app.subheader)
    assert any(item.label == "Sanitised samples" and item.value == "3" for item in app.metric)
    assert any(item.label == "Available aggregates" and item.value == "18" for item in app.metric)
    assert any("non-geographic" in item.value for item in app.caption)
    assert not any(str(PACK) in item.value for item in app.caption)


def test_live_fetch_form_is_explicit_and_prerequisite_gated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)
    app.segmented_control[0].set_value("live_vehicles")
    app.run(timeout=20)

    assert not app.exception
    fetch = next(button for button in app.button if button.label == "Fetch latest buses")
    assert fetch.disabled is True
    road_fetch = next(
        button for button in app.button if button.label == "Refresh all three operational feeds"
    )
    assert road_fetch.disabled is True
    assert any("Set BODS_API_KEY" in item.value for item in app.caption)
    assert any("Set NATIONAL_HIGHWAYS_API_KEY" in item.value for item in app.caption)
    assert any(item.label == "Request bounding box" for item in app.text_input)
    assert any("verified Bee Network operators" in item.value for item in app.caption)
    assert any("not general live road traffic" in item.value for item in app.caption)
    assert any("cleanup is never automatic" in item.value for item in app.caption)
    assert any("source polling: manual only" in item.value for item in app.caption)
    assert any(button.label == "Preview private snapshot cleanup" for button in app.button)

    monkeypatch.setenv("BODS_API_KEY", "test-only-not-submitted")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "test-only-not-submitted")
    ready = app_test.from_file("src/traffictwin/ui/app_pages/manchester.py").run(timeout=20)
    ready.segmented_control[0].set_value("live_vehicles")
    ready.run(timeout=20)
    fetch = next(button for button in ready.button if button.label == "Fetch latest buses")
    assert fetch.disabled is False
    road_fetch = next(
        button for button in ready.button if button.label == "Refresh all three operational feeds"
    )
    assert road_fetch.disabled is False
    assert not ready.exception
