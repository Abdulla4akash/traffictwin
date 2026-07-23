"""Offline adversarial tests for the controlled BODS SIRI-VM acquisition workflow.

All transports are injected fakes (httpx.MockTransport); no test touches the
network. Every XML payload is a clearly labelled synthetic fixture; the API
key is a synthetic sentinel whose absence from all persisted artifacts is
asserted explicitly.
"""

from __future__ import annotations

import json
import logging
import socket
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event, Thread

import httpx
import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.bods_acquisition import (
    BODS_ACQUISITION_METHOD_VERSION,
    BODS_ACQUISITION_SCHEMA_VERSION,
    BODS_ATTRIBUTION_TEXT,
    BODS_DATAFEED_PATH,
    BODS_FEED_MEMBER_PATH,
    BODS_FRESHNESS_POLICY_VERSION,
    BODS_LICENCE_ID,
    BODS_SOURCE_HOST,
    BodsAcquisitionError,
    BodsAcquisitionRequest,
    BodsAcquisitionResult,
    BodsReplayRequest,
    BodsReplayResult,
    acquire_bods_snapshot,
    replay_bods_quarantine,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
    ManchesterRawMember,
    ManchesterRequestIdentity,
    ManchesterRetrievalWindow,
    ManchesterSnapshotManifest,
    ManchesterSnapshotPolicy,
    ManchesterSourceIdentity,
    ManchesterValidationState,
    build_raw_fingerprint,
    build_snapshot_id,
    sha256_hex,
)
from traffictwin.integration.manchester.snapshots import (
    ManchesterSnapshotError,
    publish_manchester_quarantine,
    verify_manchester_snapshot,
)

POLICY = ManchesterSnapshotPolicy(
    max_member_count=4, max_member_bytes=8_000_000, max_total_bytes=16_000_000
)
API_KEY = "SYNTHETIC-KEY-b6f1d2c3e4a5"
RAW_VEHICLE_REF = "SYNVEH0001"
SIRI_NS = "http://www.siri.org.uk/siri"
BOX = BodsBoundingBox(
    min_longitude=Decimal("-2.4"),
    min_latitude=Decimal("53.3"),
    max_longitude=Decimal("-2.1"),
    max_latitude=Decimal("53.6"),
)
BOX_VALUE = "-2.4,53.3,-2.1,53.6"


def make_clock() -> Callable[[], datetime]:
    counter = iter(range(10_000))

    def clock() -> datetime:
        return datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=next(counter))

    return clock


def vehicle_activity(
    vehicle_ref: str = RAW_VEHICLE_REF,
    longitude: str = "-2.24",
    latitude: str = "53.48",
    line_ref: str = "SYN1",
    drop_vehicle_ref: bool = False,
) -> str:
    vehicle = "" if drop_vehicle_ref else f"<VehicleRef>{vehicle_ref}</VehicleRef>"
    return (
        "<VehicleActivity>"
        "<RecordedAtTime>2026-07-22T09:59:30Z</RecordedAtTime>"
        "<ValidUntilTime>2026-07-22T10:05:00Z</ValidUntilTime>"
        "<MonitoredVehicleJourney>"
        "<OperatorRef>SYNOP</OperatorRef>"
        f"<LineRef>{line_ref}</LineRef>"
        "<PublishedLineName>Synthetic line one</PublishedLineName>"
        "<DirectionRef>outbound</DirectionRef>"
        "<OriginRef>900001</OriginRef>"
        "<OriginName>Synthetic Origin</OriginName>"
        "<DestinationRef>900002</DestinationRef>"
        "<VehicleLocation>"
        f"<Longitude>{longitude}</Longitude>"
        f"<Latitude>{latitude}</Latitude>"
        "</VehicleLocation>"
        "<Bearing>90</Bearing>"
        "<BlockRef>B1</BlockRef>"
        "<VehicleJourneyRef>VJ1</VehicleJourneyRef>"
        f"{vehicle}"
        "</MonitoredVehicleJourney>"
        "</VehicleActivity>"
    )


def siri_xml(activities: list[str] | None = None) -> bytes:
    body = "".join(
        activities
        if activities is not None
        else [vehicle_activity(), vehicle_activity("SYNVEH0002", line_ref="SYN2")]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Siri xmlns="{SIRI_NS}">'
        "<ServiceDelivery>"
        "<ResponseTimestamp>2026-07-22T10:00:00Z</ResponseTimestamp>"
        "<ProducerRef>SYNTHETIC</ProducerRef>"
        f"<VehicleMonitoringDelivery>{body}</VehicleMonitoringDelivery>"
        "</ServiceDelivery>"
        "</Siri>"
    ).encode()


def make_transport(
    payload: bytes,
    calls: list[tuple[str, str, dict[str, str]]],
    status: int = 200,
    content_type: str = "application/xml",
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.host, request.url.path, dict(request.url.params)))
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(
            200,
            headers={"content-type": content_type},
            stream=httpx.ByteStream(payload),
        )

    return httpx.MockTransport(handler)


def make_request(**overrides: object) -> BodsAcquisitionRequest:
    values: dict[str, object] = {
        "bounding_box": BOX,
        "policy": POLICY,
        "synthetic": True,
    }
    values.update(overrides)
    return BodsAcquisitionRequest.model_validate(values)


def acquire(
    workspace: Path,
    request: BodsAcquisitionRequest,
    payload: bytes | None = None,
    calls: list[tuple[str, str, dict[str, str]]] | None = None,
    status: int = 200,
    content_type: str = "application/xml",
    api_key: str = API_KEY,
) -> BodsAcquisitionResult:
    recorded = calls if calls is not None else []
    with httpx.Client(
        transport=make_transport(
            payload if payload is not None else siri_xml(), recorded, status, content_type
        )
    ) as raw_client:
        return acquire_bods_snapshot(
            workspace,
            request,
            api_key=api_key,
            http_client=raw_client,
            utc_now=make_clock(),
        )


def workspace_dirs(workspace: Path, area: str) -> list[Path]:
    root = workspace / area
    if not root.is_dir():
        return []
    return [p for p in root.iterdir() if p.is_dir()]


def replay_request(**overrides: object) -> BodsReplayRequest:
    values: dict[str, object] = {"bounding_box": BOX, "expected_synthetic": True}
    values.update(overrides)
    return BodsReplayRequest.model_validate(values)


def test_exact_allowlisted_request_and_key_transmission(tmp_path: Path) -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []
    result = acquire(tmp_path, make_request(operator_ref="SYNOP", line_ref="SYN1"), calls=calls)
    assert calls == [
        (
            BODS_SOURCE_HOST,
            BODS_DATAFEED_PATH,
            {
                "boundingBox": BOX_VALUE,
                "lineRef": "SYN1",
                "operatorRef": "SYNOP",
                "api_key": API_KEY,
            },
        )
    ]
    # The fake server ignores filters, so both synthetic activities return.
    assert result.records_accepted == 2
    assert result.parser_status is ManchesterValidationState.ACCEPTED


def test_api_key_never_persists_anywhere(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        result = acquire(tmp_path, make_request())
    assert API_KEY not in result.canonical_json()
    assert API_KEY not in caplog.text
    assert result.request_identity.redacted_parameter_names == ("api_key",)
    assert all(name != "api_key" for name, _v in result.request_identity.parameters)

    quarantine = workspace_dirs(tmp_path, "quarantine")[0]
    accepted = workspace_dirs(tmp_path, "accepted")[0]
    for artifact in (
        quarantine / "quarantine-manifest.json",
        quarantine / "quarantine-receipt.json",
        accepted / "snapshot-manifest.json",
        accepted / "snapshot-receipt.json",
    ):
        assert API_KEY.encode() not in artifact.read_bytes()

    replayed = replay_bods_quarantine(tmp_path, result.snapshot_id, replay_request())
    assert API_KEY not in replayed.canonical_json()


def test_api_key_never_appears_in_errors(tmp_path: Path) -> None:
    with pytest.raises(BodsAcquisitionError) as invalid:
        acquire(tmp_path, make_request(), api_key=f"{API_KEY} ")
    assert invalid.value.code == "API_KEY_INVALID"
    assert API_KEY not in str(invalid.value)

    with pytest.raises(BodsAcquisitionError) as failed:
        acquire(tmp_path, make_request(), status=404)
    assert failed.value.code == "TRANSPORT_FAILURE"
    assert API_KEY not in str(failed.value)
    assert not workspace_dirs(tmp_path, "quarantine")


def test_real_evidence_refuses_injected_transport_and_clock(tmp_path: Path) -> None:
    request = make_request(synthetic=False)
    calls: list[tuple[str, str, dict[str, str]]] = []
    with (
        httpx.Client(transport=make_transport(siri_xml(), calls)) as raw_client,
        pytest.raises(BodsAcquisitionError) as transport,
    ):
        acquire_bods_snapshot(
            tmp_path / "transport",
            request,
            api_key=API_KEY,
            http_client=raw_client,
        )
    assert transport.value.code == "UNTRUSTED_REAL_SOURCE_BOUNDARY"
    assert calls == []

    with pytest.raises(BodsAcquisitionError) as clock:
        acquire_bods_snapshot(
            tmp_path / "clock",
            request,
            api_key=API_KEY,
            utc_now=make_clock(),
        )
    assert clock.value.code == "UNTRUSTED_REAL_SOURCE_BOUNDARY"
    assert not workspace_dirs(tmp_path / "transport", "quarantine")
    assert not workspace_dirs(tmp_path / "clock", "quarantine")


def test_authenticated_log_suppression_is_serial_and_restores_levels() -> None:
    import traffictwin.integration.manchester.bods_acquisition as module

    loggers = [logging.getLogger("httpx"), logging.getLogger("httpcore")]
    original_levels = [logger.level for logger in loggers]
    first_entered = Event()
    second_attempted = Event()
    second_entered = Event()
    release_first = Event()
    release_second = Event()

    def first_worker() -> None:
        with module._suppressed_url_logging():
            first_entered.set()
            release_first.wait(2)

    def second_worker() -> None:
        second_attempted.set()
        with module._suppressed_url_logging():
            second_entered.set()
            release_second.wait(2)

    first = Thread(target=first_worker)
    second = Thread(target=second_worker)
    try:
        for logger in loggers:
            logger.setLevel(logging.NOTSET)
        first.start()
        assert first_entered.wait(2)
        second.start()
        assert second_attempted.wait(2)
        assert not second_entered.wait(0.05)
        assert all(logger.level >= logging.WARNING for logger in loggers)

        release_first.set()
        assert second_entered.wait(2)
        assert all(logger.level >= logging.WARNING for logger in loggers)
        release_second.set()
        first.join(2)
        second.join(2)
        assert not first.is_alive() and not second.is_alive()
        assert all(logger.level == logging.NOTSET for logger in loggers)
    finally:
        release_first.set()
        release_second.set()
        first.join(2)
        second.join(2)
        for logger, level in zip(loggers, original_levels, strict=True):
            logger.setLevel(level)


def test_unsafe_request_fields_are_rejected() -> None:
    for injected in (
        {"host": "evil.invalid"},
        {"path": "/api/v2/other/"},
        {"url": "https://evil.invalid/api/v1/datafeed/"},
        {"query": {"vehicleRef": "SYNVEH0001"}},
        {"api_key": API_KEY},
        {"timeout": 1},
        {"max_response_bytes": 10**12},
        {"operator_ref": "BN DB"},
        {"line_ref": "a" * 65},
    ):
        with pytest.raises(ValidationError):
            make_request(**injected)
    field_names = set(BodsAcquisitionRequest.model_fields)
    assert field_names.isdisjoint(
        {"api_key", "host", "path", "url", "query", "endpoint", "publication_class"}
    )


def test_response_byte_and_content_type_bounds(tmp_path: Path) -> None:
    small_policy = ManchesterSnapshotPolicy(
        max_member_count=4, max_member_bytes=64, max_total_bytes=128
    )
    with pytest.raises(BodsAcquisitionError) as too_big:
        acquire(tmp_path / "b", make_request(policy=small_policy))
    assert too_big.value.code == "TRANSPORT_FAILURE"

    with pytest.raises(BodsAcquisitionError) as wrong_type:
        acquire(tmp_path / "c", make_request(), content_type="application/json")
    assert wrong_type.value.code == "TRANSPORT_FAILURE"
    for area in ("b", "c"):
        assert not workspace_dirs(tmp_path / area, "quarantine")
        assert not workspace_dirs(tmp_path / area, "accepted")


def test_feed_is_quarantined_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import traffictwin.integration.manchester.bods_acquisition as module
    from traffictwin.integration.manchester.bods import parse_bods_siri_vm as original

    observed: dict[str, object] = {}

    def spying_parse(member: object, scope: object) -> object:
        quarantine_dirs = workspace_dirs(tmp_path, "quarantine")
        assert len(quarantine_dirs) == 1
        observed["feed_present"] = (quarantine_dirs[0] / "raw" / "feed" / "siri-vm.xml").is_file()
        observed["manifest_present"] = (quarantine_dirs[0] / "quarantine-manifest.json").is_file()
        return original(member, scope)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "parse_bods_siri_vm", spying_parse)
    acquire(tmp_path, make_request())
    assert observed == {"feed_present": True, "manifest_present": True}


def test_successful_promotion_and_bus_only_semantics(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    accepted = workspace_dirs(tmp_path, "accepted")
    assert len(accepted) == 1
    receipt = verify_manchester_snapshot(accepted[0])
    assert receipt.fingerprint() == result.snapshot_receipt_fingerprint
    stored = ManchesterSnapshotManifest.model_validate_json(
        (accepted[0] / "snapshot-manifest.json").read_bytes()
    )
    assert stored.publication_class is ManchesterPublicationClass.PRIVATE
    assert stored.licence_id == BODS_LICENCE_ID
    assert stored.attribution_text == BODS_ATTRIBUTION_TEXT
    assert result.records_accepted == 2
    assert result.synthetic_records == 2
    assert result.retention_policy == "unapproved"
    assert result.public_export_available is False
    assert result.bee_network_membership_available is False
    assert result.transit_vehicle_only is True
    assert result.road_traffic_volume_available is False
    result_fields = set(BodsAcquisitionResult.model_fields)
    assert result_fields.isdisjoint(
        {"road_count", "traffic_volume", "congestion", "fleet_complete"}
    )


def test_no_bee_network_operator_codes_are_hard_coded() -> None:
    import traffictwin.integration.manchester.bods_acquisition as module

    source_text = Path(str(module.__file__)).read_text(encoding="utf-8")
    for code in ("BNDB", "BNFM", "BNGN", "BNML", "BNSM", "BNVB"):
        assert code not in source_text


def test_warning_admission_is_code_specific(tmp_path: Path) -> None:
    outside = siri_xml([vehicle_activity(), vehicle_activity("SYNVEH0003", longitude="-3.5")])
    for area in ("refuse", "wrong", "admit"):
        (tmp_path / area).mkdir()
    with pytest.raises(BodsAcquisitionError) as refused:
        acquire(tmp_path / "refuse", make_request(), outside)
    assert refused.value.code == "WARNINGS_REFUSED"
    assert refused.value.quarantine_snapshot_id is not None
    assert len(workspace_dirs(tmp_path / "refuse", "quarantine")) == 1
    assert not workspace_dirs(tmp_path / "refuse", "accepted")

    with pytest.raises(BodsAcquisitionError) as wrong:
        acquire(
            tmp_path / "wrong",
            make_request(admitted_warning_codes=("DUPLICATE_ACTIVITY",)),
            outside,
        )
    assert wrong.value.code == "WARNINGS_REFUSED"

    result = acquire(
        tmp_path / "admit",
        make_request(admitted_warning_codes=("OUTSIDE_BOUNDING_BOX",)),
        outside,
    )
    assert result.parser_status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert result.outside_bounds == 1
    assert result.parser_warning_codes == ("OUTSIDE_BOUNDING_BOX",)


@pytest.mark.parametrize(
    ("label", "payload"),
    [
        ("not-xml", b"\x00synthetic-not-xml"),
        (
            "dtd-entity",
            b'<?xml version="1.0"?><!DOCTYPE Siri [<!ENTITY x "y">]>'
            b'<Siri xmlns="http://www.siri.org.uk/siri">&x;</Siri>',
        ),
        (
            "wrong-root",
            b'<?xml version="1.0"?><NotSiri xmlns="http://www.siri.org.uk/siri"></NotSiri>',
        ),
    ],
)
def test_malformed_and_unsafe_xml_fails_closed(tmp_path: Path, label: str, payload: bytes) -> None:
    with pytest.raises(BodsAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(), payload)
    assert excinfo.value.code == "PARSE_REJECTED", label
    assert excinfo.value.quarantine_snapshot_id is not None
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


def test_schema_drift_activity_fails_closed(tmp_path: Path) -> None:
    payload = siri_xml([vehicle_activity(drop_vehicle_ref=True)])
    with pytest.raises(BodsAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(), payload)
    assert excinfo.value.code == "PARSE_REJECTED"
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


def test_failures_never_replace_accepted_and_repeat_is_refused(tmp_path: Path) -> None:
    acquire(tmp_path, make_request())
    accepted = workspace_dirs(tmp_path, "accepted")[0]
    before = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    with pytest.raises(BodsAcquisitionError):
        acquire(tmp_path, make_request(), status=404)
    with pytest.raises(ManchesterSnapshotError) as repeat:
        acquire(tmp_path, make_request())
    assert repeat.value.code == "DESTINATION_EXISTS"
    after = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    assert after == before


def test_offline_replay_is_deterministic_and_never_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = acquire(tmp_path, make_request())

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during replay")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    first = replay_bods_quarantine(tmp_path, result.snapshot_id, replay_request())
    second = replay_bods_quarantine(tmp_path, result.snapshot_id, replay_request())
    assert first.fingerprint() == second.fingerprint()
    assert first.replayed_offline is True
    assert first.synthetic_records == first.records_accepted
    assert first.live_vehicle == 0 and first.stale == 0
    assert len(workspace_dirs(tmp_path, "accepted")) == 1


def test_replay_rejects_relabelling(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())

    other_box = BodsBoundingBox(
        min_longitude=Decimal("-3.0"),
        min_latitude=Decimal("53.0"),
        max_longitude=Decimal("-2.0"),
        max_latitude=Decimal("54.0"),
    )
    with pytest.raises(BodsAcquisitionError) as scope_mismatch:
        replay_bods_quarantine(tmp_path, result.snapshot_id, replay_request(bounding_box=other_box))
    assert scope_mismatch.value.code == "SCOPE_MISMATCH"

    with pytest.raises(BodsAcquisitionError) as filter_mismatch:
        replay_bods_quarantine(tmp_path, result.snapshot_id, replay_request(operator_ref="SYNOP"))
    assert filter_mismatch.value.code == "SCOPE_MISMATCH"

    with pytest.raises(BodsAcquisitionError) as synthetic_mismatch:
        replay_bods_quarantine(
            tmp_path, result.snapshot_id, replay_request(expected_synthetic=False)
        )
    assert synthetic_mismatch.value.code == "SYNTHETIC_MISMATCH"


def _crafted_manifest(
    payload: bytes,
    *,
    source_id: str = "bods_siri_vm",
    publication: ManchesterPublicationClass = ManchesterPublicationClass.PRIVATE,
    redacted: tuple[str, ...] = ("api_key",),
    freshness_policy_version: str = BODS_FRESHNESS_POLICY_VERSION,
) -> tuple[ManchesterQuarantineManifest, dict[str, bytes]]:
    member = ManchesterRawMember(
        relative_path=BODS_FEED_MEMBER_PATH,
        byte_size=len(payload),
        media_type="application/xml",
        sha256=sha256_hex(payload),
    )
    started = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)
    raw_fingerprint = build_raw_fingerprint([member])
    manifest = ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id(source_id, started, raw_fingerprint),
        source=ManchesterSourceIdentity(
            source_id=source_id,
            source_name="Synthetic relabelling fixture",
            adapter_version=BODS_ACQUISITION_METHOD_VERSION,
            source_schema_version=BODS_ACQUISITION_SCHEMA_VERSION,
            freshness_policy_version=freshness_policy_version,
        ),
        request=ManchesterRequestIdentity(
            host=BODS_SOURCE_HOST,
            path=BODS_DATAFEED_PATH,
            parameters=(("boundingBox", BOX_VALUE),),
            redacted_parameter_names=redacted,
        ),
        retrieval=ManchesterRetrievalWindow(started_at_utc=started, completed_at_utc=started),
        http=None,
        members=(member,),
        member_count=1,
        total_bytes=len(payload),
        raw_fingerprint=raw_fingerprint,
        publication_class=publication,
        licence_id=BODS_LICENCE_ID,
        attribution_text=BODS_ATTRIBUTION_TEXT,
        access_date=date(2026, 7, 22),
        synthetic=True,
    )
    return manifest, {BODS_FEED_MEMBER_PATH: payload}


def test_replay_rejects_foreign_source_publication_and_redaction_drift(
    tmp_path: Path,
) -> None:
    payload = siri_xml()

    foreign, members = _crafted_manifest(payload, source_id="some_other_feed")
    publish_manchester_quarantine(tmp_path, foreign, members, POLICY)
    with pytest.raises(BodsAcquisitionError) as product:
        replay_bods_quarantine(tmp_path, foreign.snapshot_id, replay_request())
    assert product.value.code == "PRODUCT_MISMATCH"

    relabelled, members = _crafted_manifest(
        payload + b" ", publication=ManchesterPublicationClass.REDISTRIBUTABLE_RAW
    )
    publish_manchester_quarantine(tmp_path, relabelled, members, POLICY)
    with pytest.raises(BodsAcquisitionError) as contract:
        replay_bods_quarantine(tmp_path, relabelled.snapshot_id, replay_request())
    assert contract.value.code == "SOURCE_CONTRACT_MISMATCH"

    missing_redaction, members = _crafted_manifest(payload + b"  ", redacted=())
    publish_manchester_quarantine(tmp_path, missing_redaction, members, POLICY)
    with pytest.raises(BodsAcquisitionError) as redaction:
        replay_bods_quarantine(tmp_path, missing_redaction.snapshot_id, replay_request())
    assert redaction.value.code == "REDACTION_CONTRACT_MISMATCH"

    extra_redaction, members = _crafted_manifest(payload + b"   ", redacted=("api_key", "token"))
    publish_manchester_quarantine(tmp_path, extra_redaction, members, POLICY)
    with pytest.raises(BodsAcquisitionError) as extra:
        replay_bods_quarantine(tmp_path, extra_redaction.snapshot_id, replay_request())
    assert extra.value.code == "REDACTION_CONTRACT_MISMATCH"

    freshness_drift, members = _crafted_manifest(
        payload + b"    ", freshness_policy_version="fabricated-freshness-v9"
    )
    publish_manchester_quarantine(tmp_path, freshness_drift, members, POLICY)
    with pytest.raises(BodsAcquisitionError) as freshness:
        replay_bods_quarantine(tmp_path, freshness_drift.snapshot_id, replay_request())
    assert freshness.value.code == "SOURCE_CONTRACT_MISMATCH"


def test_raw_vehicle_ref_never_appears_in_derived_output(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        result = acquire(tmp_path, make_request())
        replayed = replay_bods_quarantine(tmp_path, result.snapshot_id, replay_request())
    assert RAW_VEHICLE_REF not in result.canonical_json()
    assert RAW_VEHICLE_REF not in replayed.canonical_json()
    assert RAW_VEHICLE_REF not in caplog.text

    with pytest.raises(BodsAcquisitionError) as excinfo:
        replay_bods_quarantine(
            tmp_path, result.snapshot_id, replay_request(expected_synthetic=False)
        )
    assert RAW_VEHICLE_REF not in str(excinfo.value)


def _mutated(result: BodsAcquisitionResult, field_name: str, value: object) -> str:
    payload = json.loads(result.canonical_json())
    payload[field_name] = value
    return json.dumps(payload)


def test_receipt_field_mutations_fail_model_validation(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    mutations: list[tuple[str, object]] = [
        ("snapshot_id", "bods_siri_vm-20260722T100000Z-" + "0" * 12),
        ("snapshot_id", "dft_raw_counts-20260722T100000Z-" + result.raw_fingerprint[:12]),
        ("feed_sha256", "0" * 64),
        ("parser_status", "rejected"),
        ("synthetic", False),
        ("records_accepted", result.records_accepted + 1),
        ("activities_seen", result.activities_seen + 1),
        ("malformed", 1),
        ("conflicting_duplicates", 1),
        ("live_vehicle", result.records_accepted + 5),
        ("parser_warning_codes", ["OUTSIDE_BOUNDING_BOX"]),
        ("quarantine_receipt_fingerprint", "1" * 64),
        ("snapshot_receipt_fingerprint", "2" * 64),
        ("publication_class", "redistributable_raw"),
        ("retention_policy", "approved"),
        ("bee_network_membership_available", True),
        ("road_traffic_volume_available", True),
        ("evaluated_at_utc", "2035-01-01T00:00:00Z"),
    ]
    for field_name, value in mutations:
        with pytest.raises(ValidationError):
            BodsAcquisitionResult.model_validate_json(_mutated(result, field_name, value))

    identity_mutation = json.loads(result.canonical_json())
    identity_mutation["request_identity"]["redacted_parameter_names"] = ["token"]
    with pytest.raises(ValidationError):
        BodsAcquisitionResult.model_validate_json(json.dumps(identity_mutation))

    parameter_mutation = json.loads(result.canonical_json())
    parameter_mutation["request_identity"]["parameters"] = [["boundingBox", "-3.0,53.0,-2.0,54.0"]]
    with pytest.raises(ValidationError):
        BodsAcquisitionResult.model_validate_json(json.dumps(parameter_mutation))

    embedded_mutation = json.loads(result.canonical_json())
    embedded_mutation["quarantine_receipt"]["snapshot_id"] = (
        "bods_siri_vm-20260722T100000Z-" + "0" * 12
    )
    with pytest.raises(ValidationError):
        BodsAcquisitionResult.model_validate_json(json.dumps(embedded_mutation))

    manifest_mutation = json.loads(result.canonical_json())
    manifest_mutation["quarantine_manifest"]["retrieval"]["completed_at_utc"] = (
        "2035-01-01T00:00:00Z"
    )
    with pytest.raises(ValidationError):
        BodsAcquisitionResult.model_validate_json(json.dumps(manifest_mutation))

    replayed = replay_bods_quarantine(tmp_path, result.snapshot_id, replay_request())
    replay_mutation = json.loads(replayed.canonical_json())
    replay_mutation["live_vehicle"] = replayed.records_accepted
    replay_mutation["synthetic_records"] = 0
    with pytest.raises(ValidationError):
        BodsReplayResult.model_validate_json(json.dumps(replay_mutation))

    replay_time_mutation = json.loads(replayed.canonical_json())
    replay_time_mutation["evaluated_at_utc"] = "2035-01-01T00:00:00Z"
    with pytest.raises(ValidationError):
        BodsReplayResult.model_validate_json(json.dumps(replay_time_mutation))

    replay_scope_mutation = json.loads(replayed.canonical_json())
    replay_scope_mutation["request"]["bounding_box"] = {
        "min_longitude": "-3.0",
        "min_latitude": "53.0",
        "max_longitude": "-2.0",
        "max_latitude": "54.0",
    }
    with pytest.raises(ValidationError):
        BodsReplayResult.model_validate_json(json.dumps(replay_scope_mutation))


def test_admitted_warning_shrinkage_invalidates_the_receipt(tmp_path: Path) -> None:
    outside = siri_xml([vehicle_activity(), vehicle_activity("SYNVEH0003", longitude="-3.5")])
    result = acquire(
        tmp_path,
        make_request(admitted_warning_codes=("OUTSIDE_BOUNDING_BOX",)),
        outside,
    )
    shrunk = json.loads(result.canonical_json())
    shrunk["request"]["admitted_warning_codes"] = []
    with pytest.raises(ValidationError):
        BodsAcquisitionResult.model_validate_json(json.dumps(shrunk))
