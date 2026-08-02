"""Offline golden and adversarial tests for National Highways operational feeds."""

from __future__ import annotations

import gzip
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.models import ManchesterValidationState
from traffictwin.integration.manchester.national_highways import (
    NationalHighwaysError,
    default_manchester_operational_envelope,
    parse_national_highways_payload,
)
from traffictwin.integration.manchester.national_highways_acquisition import (
    NATIONAL_HIGHWAYS_FORMAT_HEADER,
    NATIONAL_HIGHWAYS_MEDIA_HEADER,
    NATIONAL_HIGHWAYS_SECRET_HEADER,
    NationalHighwaysAcquisitionError,
    NationalHighwaysAcquisitionRequest,
    acquire_national_highways_snapshot,
    replay_national_highways_snapshot,
)
from traffictwin.integration.manchester.national_highways_live import (
    NATIONAL_HIGHWAYS_LATEST_OVERLAY,
    NATIONAL_HIGHWAYS_LIVE_OVERLAY,
    NationalHighwaysLiveError,
    coordinated_national_highways_refresh,
    load_national_highways_control_state,
    project_national_highways_scene_for_display,
)
from traffictwin.integration.manchester.snapshots import ACCEPTED_DIRECTORY_NAME
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.manchester_operations import load_local_manchester_scene

SYNTHETIC_KEY = "SYNTHETIC-NATIONAL-HIGHWAYS-KEY"
PUBLICATION_TIME = "2026-07-24T10:00:00Z"


def _clock() -> Callable[[], datetime]:
    counter = iter(range(10_000))

    def clock() -> datetime:
        return datetime(2026, 7, 24, 10, 0, tzinfo=UTC) + timedelta(milliseconds=next(counter))

    return clock


def _location(latitude: str = "53.4808", longitude: str = "-2.2426") -> dict[str, object]:
    return {
        "locLinearLocation": {
            "gmlLineString": {
                "locGmlLineString": {
                    "posList": f"{latitude} {longitude} {latitude} {longitude}",
                    "srsDimension": 2,
                    "srsName": "ESPG::4326",
                }
            },
            "supplementaryPositionalDescription": {
                "locationDescription": "M60 clockwise within synthetic junction"
            },
        },
        "locSingleRoadLinearLocation": {
            "linearWithinLinearElement": [
                {
                    "directionOnLinearSection": "clockwise",
                    "linearElement": {"locLinearElementByCode": {"roadName": "M60"}},
                }
            ]
        },
    }


def _situation_payload(product: str, *, outside: bool = False) -> bytes:
    location = _location("52.0", "-1.0") if outside else _location()
    common: dict[str, object] = {
        "idG": f"synthetic-{product}-record",
        "versionG": "1",
        "locationReference": location,
        "situationRecordVersionTime": "2026-07-24T09:59:00Z",
        "validity": {
            "validityStatus": "active",
            "validityTimeSpecification": {
                "overallStartTime": "2026-07-24T09:00:00Z",
                "overallEndTime": "2026-07-24T11:00:00Z",
            },
        },
        "cause": {"causeType": "unplannedEvent"},
    }
    if product == "closures":
        key = "sitRoadOrCarriagewayOrLaneManagement"
        common["roadOrCarriagewayOrLaneManagementType"] = {"value": "laneClosures"}
    else:
        key = "sitSpeedManagement"
        common["temporarySpeedLimit"] = 64.3738
        common["cause"] = {
            "causeType": "unplannedEvent",
            "detailedCauseType": {"speedManagementType": "temporarySpeedLimit"},
        }
    document = {
        "D2Payload": {
            "feedType": "SituationPublication",
            "modelBaseVersion": "3",
            "publicationTime": PUBLICATION_TIME,
            "situation": [
                {
                    "idG": f"synthetic-{product}-situation",
                    "situationRecord": [{key: common}],
                }
            ],
        }
    }
    return json.dumps(document, separators=(",", ":")).encode()


def _vms_payload() -> bytes:
    document = {
        "D2Payload": {
            "feedType": "vmsPublication",
            "modelBaseVersionG": "3",
            "publicationTime": PUBLICATION_TIME,
            "vmsControllerStatus": [
                {
                    "vmsControllerReference": {"idG": "synthetic-controller"},
                    "vmsStatus": [
                        {
                            "vmsIndex": 1,
                            "vmsStatus": {
                                "workingStatus": "working ",
                                "vmsMessage": [
                                    {
                                        "messageIndex": 1,
                                        "vmsMessage": {
                                            "messageInformationType": ["instructionOrMessage"],
                                            "messageSetBy": "System",
                                            "reasonForSetting": "Synthetic test reason",
                                            "timeLastSet": "2026-07-24T09:58:00Z",
                                        },
                                    }
                                ],
                                "vmsStatusExtensionG": {
                                    "description": "3x18 Characters",
                                    "externalIdentifier": "synthetic-vms",
                                    "vmsType": "monochromeGraphic",
                                    "vmsLocation": {
                                        "locPointLocation": {
                                            "pointByCoordinates": {
                                                "pointCoordinates": {
                                                    "latitude": 53.490269,
                                                    "longitude": -2.378301,
                                                }
                                            },
                                            "supplementaryPositionalDescription": {
                                                "locationDescription": "M60 within synthetic J12",
                                                "roadInformation": [{"roadName": "M60"}],
                                                "supplementaryPositionalDescriptionExtensionG": {
                                                    "direction": "anticlockwise"
                                                },
                                            },
                                        }
                                    },
                                },
                            },
                        }
                    ],
                }
            ],
        }
    }
    return json.dumps(document, separators=(",", ":")).encode()


def _payload_for_path(path: str) -> bytes:
    if path == "/roads/v2.0/closures":
        return _situation_payload("closures")
    if path == "/sma/v1.0/speedManagedAreas":
        return _situation_payload("speed_limits")
    if path == "/dvms/v1.0/vms":
        return _vms_payload()
    raise AssertionError(path)


def _transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(_payload_for_path(request.url.path)),
        )

    return httpx.MockTransport(handler)


def _gzip_transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            headers={
                "content-encoding": "gzip",
                "content-type": "application/json",
            },
            stream=httpx.ByteStream(gzip.compress(_payload_for_path(request.url.path))),
        )

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("product", ["closures", "speed_limits", "vms"])
def test_exact_observed_schemas_project_source_separated_records(product: str) -> None:
    payload = _vms_payload() if product == "vms" else _situation_payload(product)
    report = parse_national_highways_payload(
        payload,
        product=product,  # type: ignore[arg-type]
        envelope=default_manchester_operational_envelope(),
        synthetic=True,
    )

    assert report.counts.source_items_seen == 1
    assert report.counts.records_accepted == 1
    assert report.counts.outside_envelope == 0
    record = report.records[0]
    assert record.product == product
    assert record.strategic_road_network_only is True
    assert record.measured_speed_available is False
    assert record.traffic_volume_available is False
    if product == "speed_limits":
        assert record.temporary_speed_limit_kph is not None
    if product == "vms":
        assert record.literal_display_text_available is False
        assert record.vms_reason_for_setting == "Synthetic test reason"


def test_outside_geometry_is_reconciled_and_not_rendered() -> None:
    report = parse_national_highways_payload(
        _situation_payload("closures", outside=True),
        product="closures",
        envelope=default_manchester_operational_envelope(),
        synthetic=True,
    )
    assert report.records == ()
    assert report.counts.outside_envelope == 1
    assert report.counts.source_items_seen == 1


def test_duplicate_json_keys_and_wrong_feed_fail_closed() -> None:
    with pytest.raises(NationalHighwaysError) as duplicate:
        parse_national_highways_payload(
            b'{"D2Payload":{"feedType":"SituationPublication","feedType":"other"}}',
            product="closures",
            envelope=default_manchester_operational_envelope(),
            synthetic=True,
        )
    assert duplicate.value.code == "JSON_INVALID"

    document = json.loads(_situation_payload("closures"))
    document["D2Payload"]["feedType"] = "vmsPublication"
    with pytest.raises(NationalHighwaysError) as wrong:
        parse_national_highways_payload(
            json.dumps(document).encode(),
            product="closures",
            envelope=default_manchester_operational_envelope(),
            synthetic=True,
        )
    assert wrong.value.code == "FEED_TYPE_MISMATCH"


def test_publication_time_drives_near_live_and_stale_truth() -> None:
    observed = datetime(2026, 7, 24, 10, 0, tzinfo=UTC)
    near_live = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="national_highways_closures",
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="live",
            evaluated_at_utc=observed + timedelta(minutes=5),
            observed_at_utc=observed,
            synthetic=False,
        )
    )
    stale = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="national_highways_closures",
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="live",
            evaluated_at_utc=observed + timedelta(minutes=11),
            observed_at_utc=observed,
            synthetic=False,
        )
    )
    outage = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="national_highways_closures",
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="live",
            evaluated_at_utc=observed + timedelta(minutes=1),
            observed_at_utc=observed,
            synthetic=False,
            service_state="forced_unavailable",
            service_notice_id="synthetic-outage-test",
            using_cached_snapshot=True,
        )
    )
    assert near_live.truth_state == "near_live"
    assert stale.truth_state == "stale"
    assert outage.truth_state == "stale"
    assert outage.reason == "cached_snapshot_during_service_outage"


def test_secret_header_is_transient_and_offline_replay_reproduces_parser(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    calls: list[httpx.Request] = []
    request = NationalHighwaysAcquisitionRequest(
        product="closures",
        envelope=default_manchester_operational_envelope(),
        event_type="unplanned",
        window_start_utc=datetime(2026, 7, 24, 4, 0, tzinfo=UTC),
        window_end_utc=datetime(2026, 7, 24, 10, 0, tzinfo=UTC),
        synthetic=True,
    )
    with (
        caplog.at_level(logging.DEBUG),
        httpx.Client(transport=_transport(calls)) as client,
    ):
        acquired = acquire_national_highways_snapshot(
            workspace,
            request,
            subscription_key=SYNTHETIC_KEY,
            http_client=client,
            utc_now=_clock(),
        )

    assert len(calls) == 1
    sent = calls[0]
    assert sent.headers[NATIONAL_HIGHWAYS_SECRET_HEADER] == SYNTHETIC_KEY
    assert sent.headers[NATIONAL_HIGHWAYS_FORMAT_HEADER] == "DATEXII"
    assert sent.headers[NATIONAL_HIGHWAYS_MEDIA_HEADER] == "application/json"
    assert acquired.result.subscription_key_persisted is False
    assert SYNTHETIC_KEY not in caplog.text
    replay = replay_national_highways_snapshot(
        workspace,
        acquired.result.snapshot_id,
        request,
    )
    assert replay.fingerprint() == acquired.report.fingerprint()
    accepted = workspace / ACCEPTED_DIRECTORY_NAME / acquired.result.snapshot_id
    assert accepted.is_dir()
    for path in workspace.rglob("*"):
        if path.is_file() and not path.is_symlink():
            assert SYNTHETIC_KEY.encode() not in path.read_bytes()
    assert SYNTHETIC_KEY not in acquired.result.canonical_json()


def test_gzip_wire_entity_is_preserved_then_bounded_decoded(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    calls: list[httpx.Request] = []
    request = NationalHighwaysAcquisitionRequest(
        product="closures",
        envelope=default_manchester_operational_envelope(),
        event_type="unplanned",
        window_start_utc=datetime(2026, 7, 24, 4, 0, tzinfo=UTC),
        window_end_utc=datetime(2026, 7, 24, 10, 0, tzinfo=UTC),
        synthetic=True,
    )
    with httpx.Client(transport=_gzip_transport(calls)) as client:
        acquired = acquire_national_highways_snapshot(
            workspace,
            request,
            subscription_key=SYNTHETIC_KEY,
            http_client=client,
            utc_now=_clock(),
        )

    assert len(calls) == 1
    assert acquired.result.raw_sha256 != acquired.result.parser_payload_sha256
    assert acquired.result.records_accepted == 1
    replay = replay_national_highways_snapshot(
        workspace,
        acquired.result.snapshot_id,
        request,
    )
    assert replay.fingerprint() == acquired.report.fingerprint()


def test_controlled_refresh_publishes_three_overlay_layers_and_history(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    calls: list[httpx.Request] = []
    with httpx.Client(transport=_transport(calls)) as client:
        summary = coordinated_national_highways_refresh(
            workspace,
            subscription_key=SYNTHETIC_KEY,
            utc_now=_clock(),
            http_client=client,
            synthetic=True,
        )

    assert len(calls) == 3
    assert tuple(item.product for item in summary.products) == (
        "closures",
        "speed_limits",
        "vms",
    )
    assert summary.total_records_accepted == 3
    assert summary.operator_triggered is True
    assert summary.automatic_polling_performed is False
    assert (workspace / NATIONAL_HIGHWAYS_LATEST_OVERLAY).is_file()
    assert (workspace / NATIONAL_HIGHWAYS_LIVE_OVERLAY).is_file()
    state = load_national_highways_control_state(workspace)
    assert state.successes_total == 1
    assert state.history_entry_count == 1
    latest = load_local_manchester_scene(workspace, "latest_available")
    live = load_local_manchester_scene(workspace, "live_vehicles")
    assert latest.scene is not None and len(latest.scene.layers) == 3
    assert live.scene is not None and len(live.scene.layers) == 3
    assert {layer.request.source for layer in latest.scene.layers} == {
        "national_highways_closures",
        "national_highways_speed_limits",
        "national_highways_vms",
    }
    assert all(layer.request.publication_class.value == "private" for layer in latest.scene.layers)
    for path in workspace.rglob("*"):
        if path.is_file() and not path.is_symlink():
            assert SYNTHETIC_KEY.encode() not in path.read_bytes()


def test_automatic_refresh_records_its_trigger_truthfully(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    with httpx.Client(transport=_transport([])) as client:
        summary = coordinated_national_highways_refresh(
            workspace,
            subscription_key=SYNTHETIC_KEY,
            utc_now=_clock(),
            http_client=client,
            synthetic=True,
            trigger="automatic",
        )

    assert summary.operator_triggered is False
    assert summary.automatic_polling_performed is True
    state = load_national_highways_control_state(workspace)
    assert state.automatic_polling_available is True
    assert state.history[-1].automatic_polling_performed is True


def test_failed_refresh_preserves_overlay_and_synthetic_truth_label(
    tmp_path: Path,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    with httpx.Client(transport=_transport([])) as client:
        coordinated_national_highways_refresh(
            workspace,
            subscription_key=SYNTHETIC_KEY,
            utc_now=_clock(),
            http_client=client,
            synthetic=True,
        )
    target = workspace / NATIONAL_HIGHWAYS_LATEST_OVERLAY
    accepted_scene = target.read_bytes()

    def reject(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, headers={"content-type": "application/json"})

    failed_at = datetime(2026, 7, 24, 10, 2, tzinfo=UTC)
    with (
        httpx.Client(transport=httpx.MockTransport(reject)) as client,
        pytest.raises(NationalHighwaysAcquisitionError),
    ):
        coordinated_national_highways_refresh(
            workspace,
            subscription_key=SYNTHETIC_KEY,
            utc_now=lambda: failed_at,
            http_client=client,
            synthetic=True,
        )

    assert target.read_bytes() == accepted_scene
    state = load_national_highways_control_state(workspace)
    assert state.last_attempt_status == "failed"
    assert state.successes_total == 1
    assert state.failures_total == 1
    loaded = load_local_manchester_scene(workspace, "latest_available")
    assert loaded.scene is not None
    projected = project_national_highways_scene_for_display(
        loaded.scene,
        evaluated_at_utc=failed_at,
        source_outage=True,
    )
    assert all(
        layer.request.freshness is not None and layer.request.freshness.truth_state == "synthetic"
        for layer in projected.layers
    )


def test_refresh_refuses_workspace_internal_symlink_escape(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "manchester" / "live").symlink_to(outside, target_is_directory=True)

    with pytest.raises(NationalHighwaysLiveError) as load_error:
        load_national_highways_control_state(workspace)
    with pytest.raises(NationalHighwaysLiveError) as raised:
        coordinated_national_highways_refresh(
            workspace,
            subscription_key=SYNTHETIC_KEY,
            utc_now=_clock(),
            synthetic=True,
        )

    assert load_error.value.code == "CONTROL_STATE_INVALID"
    assert raised.value.code == "LOCK_PATH_INVALID"
    assert tuple(outside.iterdir()) == ()
