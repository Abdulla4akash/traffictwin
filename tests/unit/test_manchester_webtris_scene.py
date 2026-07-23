"""Offline tests for the accepted WebTRIS-site-to-MAN-08 scene bridge."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_map_layers import request as synthetic_layer_request
from tests.unit.test_manchester_webtris_acquisition import (
    acquire,
    default_responses,
    make_request,
    site_payload,
)
from traffictwin.integration.manchester.models import ManchesterPublicationClass
from traffictwin.integration.manchester.webtris_acquisition import WebtrisAcquisitionResult
from traffictwin.integration.manchester.webtris_scene import (
    WebtrisSceneError,
    WebtrisSiteLayerSummary,
    build_webtris_site_layer,
    publish_webtris_site_scene,
)
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.manchester_operations import load_local_manchester_scene

EVALUATED_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _accepted(tmp_path: Path) -> tuple[Path, WebtrisAcquisitionResult]:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    return workspace, acquire(workspace, make_request("site"))


def _site_response(**changes: object) -> bytes:
    body = json.loads(site_payload())
    body["sites"][0].update(changes)
    return json.dumps(body).encode("utf-8")


def test_accepted_site_builds_historical_strategic_reference_layer(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)

    built = build_webtris_site_layer(
        workspace,
        acquisition,
        mode="historical_replay",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.site_id == "34"
    assert built.summary.layer_id == "webtris-site-34"
    assert built.summary.records_accepted == 1
    assert built.summary.spatial_admitted == 1
    assert built.summary.layer_status == "available"
    assert built.summary.daily_traffic_values_included is False
    assert built.summary.source_time_promoted_to_utc is False
    assert built.summary.live_road_traffic_available is False
    assert built.layer_request.source == "webtris"
    assert built.layer_request.mode == "historical_replay"
    assert built.layer_request.snapshot_fingerprint == acquisition.fingerprint()
    assert built.layer_request.freshness is not None
    assert built.layer_request.freshness.truth_state == "synthetic"
    assert built.parser_report.fingerprint() == acquisition.parser_report_fingerprint
    assert built.spatial_report.results[0].geographic_scope == "strategic_approaches"


@pytest.mark.parametrize("mode", ["historical_replay", "latest_available"])
def test_explicit_publication_populates_fixed_scene(
    tmp_path: Path,
    mode: str,
) -> None:
    workspace, acquisition = _accepted(tmp_path)

    result = publish_webtris_site_scene(
        workspace,
        (acquisition,),
        mode=mode,  # type: ignore[arg-type]
        evaluated_at_utc=EVALUATED_AT,
    )

    assert result.publication.scene.mode == mode
    assert result.publication.scene.visible_layer_ids == ("webtris-site-34",)
    assert result.publication.scene.source_fusion_performed is False
    loaded = load_local_manchester_scene(workspace, mode)
    assert loaded.scene == result.publication.scene


def test_additional_layer_stays_separate_without_scope_fusion(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    context = synthetic_layer_request(layer_id="synthetic-context", title="Synthetic context")

    result = publish_webtris_site_scene(
        workspace,
        (acquisition,),
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
        additional_layer_requests=(context,),
    )

    assert tuple(layer.request.layer_id for layer in result.publication.scene.layers) == (
        "synthetic-context",
        "webtris-site-34",
    )
    assert result.publication.scene.source_fusion_performed is False
    assert result.publication.scene.cross_scope_totals_available is False
    assert result.publication.scene.scopes_treated_as_equal is False


def test_build_performs_no_network_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, acquisition = _accepted(tmp_path)

    def refuse_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("accepted-site replay must not use the network")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    built = build_webtris_site_layer(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.spatial_admitted == 1


def test_unmarked_workspace_is_refused_before_snapshot_access(tmp_path: Path) -> None:
    _workspace, acquisition = _accepted(tmp_path)
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()

    with pytest.raises(WebtrisSceneError) as excinfo:
        build_webtris_site_layer(
            ordinary,
            acquisition,
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "WORKSPACE_INVALID"


def test_daily_product_is_never_relabelled_as_a_site_layer(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    daily = acquire(workspace, make_request("daily_report"))

    with pytest.raises(WebtrisSceneError) as excinfo:
        build_webtris_site_layer(
            workspace,
            daily,
            mode="historical_replay",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "PRODUCT_REFUSED"


def test_mutated_accepted_member_is_refused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    target = workspace / "accepted" / acquisition.snapshot_id / "raw/site/site.json"
    target.chmod(0o600)
    target.write_bytes(target.read_bytes() + b"drift")

    with pytest.raises(WebtrisSceneError) as excinfo:
        build_webtris_site_layer(
            workspace,
            acquisition,
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "ACCEPTED_SNAPSHOT_INVALID"


def test_mutated_parser_binding_is_refused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    drifted = acquisition.model_copy(update={"parser_report_fingerprint": "0" * 64})

    with pytest.raises(WebtrisSceneError) as excinfo:
        build_webtris_site_layer(
            workspace,
            drifted,
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "PARSER_REPORT_MISMATCH"


def test_response_site_identity_must_match_selected_endpoint(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    responses = default_responses()
    responses["site"] = _site_response(Id="35")
    acquisition = acquire(workspace, make_request("site"), responses=responses)

    with pytest.raises(WebtrisSceneError) as excinfo:
        build_webtris_site_layer(
            workspace,
            acquisition,
            mode="historical_replay",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "SITE_SCOPE_MISMATCH"


def test_inactive_selected_site_is_visible_as_unavailable_not_dropped(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    responses = default_responses()
    responses["site"] = _site_response(Status="Inactive")
    acquisition = acquire(workspace, make_request("site"), responses=responses)

    built = build_webtris_site_layer(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.spatial_admitted == 0
    assert built.summary.spatial_excluded == 1
    assert built.summary.layer_status == "unavailable"
    assert built.spatial_report.results[0].reason == "source_record_inactive"


def test_public_export_follows_snapshot_publication_class(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    acquisition = acquire(
        workspace,
        make_request(
            "site",
            publication_class=ManchesterPublicationClass.REDISTRIBUTABLE_RAW,
        ),
    )

    built = build_webtris_site_layer(
        workspace,
        acquisition,
        mode="historical_replay",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.publication_class is ManchesterPublicationClass.REDISTRIBUTABLE_RAW
    assert built.summary.public_export_available is True


def test_duplicate_selected_site_is_refused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)

    with pytest.raises(WebtrisSceneError) as excinfo:
        publish_webtris_site_scene(
            workspace,
            (acquisition, acquisition),
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "DUPLICATE_SITE"


def test_empty_site_inventory_is_refused(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path

    with pytest.raises(WebtrisSceneError) as excinfo:
        publish_webtris_site_scene(
            workspace,
            (),
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "NO_SITES"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("layer_id", "webtris-site-35"),
        ("records_accepted", 2),
        ("spatial_admitted", 0),
        ("layer_status", "unavailable"),
        ("public_export_available", True),
        ("daily_traffic_values_included", True),
        ("source_time_promoted_to_utc", True),
        ("live_road_traffic_available", True),
        ("cross_source_join_performed", True),
    ],
)
def test_summary_mutations_are_refused(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    workspace, acquisition = _accepted(tmp_path)
    summary = build_webtris_site_layer(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
    ).summary
    payload = json.loads(summary.model_dump_json())
    payload[field] = value

    with pytest.raises(ValidationError):
        WebtrisSiteLayerSummary.model_validate(payload)
