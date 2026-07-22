"""Offline acceptance and refusal evidence for the MAN-05 BODS parser."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.bods import (
    BodsAdapterError,
    BodsBoundingBox,
    BodsMemberRef,
    BodsParseReport,
    BodsParseScope,
    LiveTransitVehicleObservation,
    bods_freshness_state,
    parse_bods_siri_vm,
)
from traffictwin.integration.manchester.models import ManchesterValidationState, sha256_hex

FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "manchester" / "bods" / "siri-vm-synthetic.xml"
)
FIXTURE_SHA256 = "e59331ed0abf13d6ba0b09da2ede55ad041eb7d92e799deb98d5706938c2d9b8"
SNAPSHOT_ID = "bods-20260722T120020Z-abcdef012345"
EVALUATED_AT = datetime(2026, 7, 22, 12, 0, 30, tzinfo=UTC)


def fixture() -> bytes:
    payload = FIXTURE.read_bytes()
    assert sha256_hex(payload) == FIXTURE_SHA256
    return payload


def member(payload: bytes, *, synthetic: bool = True) -> BodsMemberRef:
    return BodsMemberRef(
        snapshot_id=SNAPSHOT_ID,
        member_path="private/raw/siri-vm.xml",
        member_sha256=sha256_hex(payload),
        synthetic=synthetic,
    )


def scope(
    *,
    mode: str = "live",
    evaluated_at: datetime = EVALUATED_AT,
    min_longitude: str = "-3.0",
    max_longitude: str = "-1.5",
) -> BodsParseScope:
    return BodsParseScope.model_validate(
        {
            "evaluated_at_utc": evaluated_at,
            "mode": mode,
            "bounding_box": BodsBoundingBox(
                min_longitude=Decimal(min_longitude),
                min_latitude=Decimal("53.0"),
                max_longitude=Decimal(max_longitude),
                max_latitude=Decimal("54.0"),
            ),
        }
    )


def parse(payload: bytes | None = None, *, synthetic: bool = True) -> BodsParseReport:
    body = fixture() if payload is None else payload
    return parse_bods_siri_vm((member(body, synthetic=synthetic), body), scope())


def finding_codes(report: BodsParseReport) -> set[str]:
    return {finding.code for finding in report.findings}


def replace_once(payload: bytes, old: str, new: str) -> bytes:
    source = old.encode()
    assert payload.count(source) >= 1
    return payload.replace(source, new.encode(), 1)


def first_activity(payload: bytes) -> bytes:
    start_marker = b"      <VehicleActivity>"
    end_marker = b"      </VehicleActivity>"
    start = payload.index(start_marker)
    end = payload.index(end_marker, start) + len(end_marker)
    return payload[start:end]


def test_schema_faithful_synthetic_fixture_is_privacy_safe() -> None:
    report = parse()
    assert report.status is ManchesterValidationState.ACCEPTED
    assert report.counts.activities_seen == 2
    assert report.counts.records_accepted == 2
    assert report.counts.synthetic == 2
    assert report.raw_vehicle_identifiers_in_output is False
    assert report.retention_policy_approved is False
    assert report.public_export_available is False

    first = next(record for record in report.records if record.operator_ref == "BNSM")
    assert first.freshness_state == "synthetic"
    assert first.velocity_mps == Decimal("8.5")
    assert first.occupancy == "seatsAvailable"
    assert len(first.vehicle_token) == 24
    assert first.identity_scope == "snapshot_only"
    second = next(record for record in report.records if record.operator_ref == "SYN1")
    assert second.velocity_mps is None
    assert second.occupancy is None
    assert second.destination_name is None

    rendered = report.canonical_json()
    assert "synthetic-vehicle-alpha" not in rendered
    assert "synthetic-vehicle-beta" not in rendered
    assert all("vehicle" not in finding.message.lower() for finding in report.findings)


def test_operator_and_display_name_cannot_activate_bee_membership() -> None:
    record = next(record for record in parse().records if record.operator_ref == "BNSM")
    assert record.operator_ref == "BNSM"
    assert record.published_line_name == "Bee Network 50"
    assert record.bee_network_membership == "unverified"
    assert record.bee_network_membership_available is False

    strengthened = json.loads(record.canonical_json())
    strengthened["bee_network_membership"] = "bee_network_franchised"
    with pytest.raises(ValidationError):
        LiveTransitVehicleObservation.model_validate(strengthened)


def test_transit_observation_cannot_claim_general_traffic_or_passengers() -> None:
    record = parse().records[0]
    assert record.transit_vehicle_only is True
    assert record.road_traffic_volume_available is False
    assert record.private_vehicle_flow_available is False
    assert record.passenger_inference_available is False

    strengthened = record.model_dump(mode="python")
    strengthened["road_traffic_volume_available"] = True
    with pytest.raises(ValidationError):
        LiveTransitVehicleObservation.model_validate(strengthened)


def test_freshness_policy_is_source_time_based_and_deterministic() -> None:
    recorded = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    valid_until = recorded + timedelta(seconds=90)

    assert bods_freshness_state(
        recorded_at_utc=recorded,
        valid_until_utc=valid_until,
        evaluated_at_utc=recorded + timedelta(seconds=60),
        mode="live",
        synthetic=False,
    ) == "live_vehicle"
    assert bods_freshness_state(
        recorded_at_utc=recorded,
        valid_until_utc=valid_until,
        evaluated_at_utc=recorded + timedelta(seconds=61),
        mode="live",
        synthetic=False,
    ) == "stale"
    assert bods_freshness_state(
        recorded_at_utc=recorded,
        valid_until_utc=recorded + timedelta(seconds=30),
        evaluated_at_utc=recorded + timedelta(seconds=31),
        mode="live",
        synthetic=False,
    ) == "stale"
    assert bods_freshness_state(
        recorded_at_utc=recorded,
        valid_until_utc=valid_until,
        evaluated_at_utc=recorded - timedelta(seconds=1),
        mode="live",
        synthetic=False,
    ) == "stale"
    assert bods_freshness_state(
        recorded_at_utc=recorded,
        valid_until_utc=valid_until,
        evaluated_at_utc=recorded + timedelta(seconds=10),
        mode="offline_replay",
        synthetic=False,
    ) == "historical"
    assert bods_freshness_state(
        recorded_at_utc=recorded,
        valid_until_utc=valid_until,
        evaluated_at_utc=recorded + timedelta(seconds=10),
        mode="live",
        synthetic=True,
    ) == "synthetic"


def test_freshness_refuses_non_utc_and_invalid_windows() -> None:
    recorded = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    with pytest.raises(BodsAdapterError, match="NON_UTC_FRESHNESS_INPUT"):
        bods_freshness_state(
            recorded_at_utc=recorded.replace(tzinfo=None),
            valid_until_utc=recorded + timedelta(seconds=30),
            evaluated_at_utc=recorded,
            mode="live",
            synthetic=False,
        )
    with pytest.raises(ValidationError, match="evaluated_at_utc must be explicitly UTC"):
        scope(evaluated_at=recorded.astimezone(timezone(timedelta(hours=1))))
    with pytest.raises(BodsAdapterError, match="INVALID_VALIDITY_WINDOW"):
        bods_freshness_state(
            recorded_at_utc=recorded,
            valid_until_utc=recorded - timedelta(seconds=1),
            evaluated_at_utc=recorded,
            mode="live",
            synthetic=False,
        )


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("2026-07-22T12:00:00Z", "2026-07-22T13:00:00+01:00"),
        ("<VehicleRef>synthetic-vehicle-alpha</VehicleRef>", ""),
        ("<Occupancy>seatsAvailable</Occupancy>", "<Occupancy>unknown</Occupancy>"),
        ("<Velocity>8.5</Velocity>", "<Velocity>-1</Velocity>"),
        ("<Bearing>90</Bearing>", "<Bearing>361</Bearing>"),
    ],
)
def test_malformed_activities_are_rejected_without_imputation(old: str, new: str) -> None:
    report = parse(replace_once(fixture(), old, new))
    assert report.status is ManchesterValidationState.REJECTED
    assert report.counts.malformed == 1
    assert "MALFORMED_ACTIVITY" in finding_codes(report)


def test_invalid_valid_until_before_recorded_is_rejected() -> None:
    body = replace_once(
        fixture(),
        "<ValidUntilTime>2026-07-22T12:01:30Z</ValidUntilTime>",
        "<ValidUntilTime>2026-07-22T11:59:59Z</ValidUntilTime>",
    )
    report = parse(body)
    assert report.status is ManchesterValidationState.REJECTED
    assert report.counts.malformed == 1


def test_geographic_exclusion_is_visible_and_accounted() -> None:
    body = replace_once(fixture(), "<Longitude>-2.2400</Longitude>", "<Longitude>-4.0</Longitude>")
    report = parse(body)
    assert report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert report.counts.activities_seen == 2
    assert report.counts.outside_bounds == 1
    assert report.counts.records_accepted == 1
    assert finding_codes(report) == {"OUTSIDE_BOUNDING_BOX"}


def test_exact_duplicate_is_collapsed_with_complete_accounting() -> None:
    body = fixture()
    activity = first_activity(body)
    duplicated = body.replace(activity, activity + b"\n" + activity, 1)
    report = parse(duplicated)
    assert report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert report.counts.activities_seen == 3
    assert report.counts.records_accepted == 2
    assert report.counts.duplicate_collapsed == 1
    assert finding_codes(report) == {"DUPLICATE_ACTIVITY"}


def test_conflicting_duplicate_is_withheld_and_rejects_report() -> None:
    body = fixture()
    activity = first_activity(body)
    conflicting = activity.replace(
        b"<Longitude>-2.2400</Longitude>",
        b"<Longitude>-2.2300</Longitude>",
    )
    payload = body.replace(activity, activity + b"\n" + conflicting, 1)
    report = parse(payload)
    assert report.status is ManchesterValidationState.REJECTED
    assert report.counts.activities_seen == 3
    assert report.counts.records_accepted == 1
    assert report.counts.conflicting_duplicates == 2
    assert finding_codes(report) == {"CONFLICTING_ACTIVITY"}


def test_snapshot_scoped_tokens_are_stable_but_change_between_snapshots() -> None:
    body = fixture()
    first = parse().records[0]
    other_ref = member(body).model_copy(
        update={"snapshot_id": "bods-20260722T120030Z-123456abcdef"}
    )
    second = parse_bods_siri_vm((other_ref, body), scope()).records[0]
    assert first.vehicle_token != second.vehicle_token
    assert first.vehicle_token == parse().records[0].vehicle_token


def test_member_hash_is_verified_before_xml_parsing() -> None:
    body = fixture()
    broken = member(body).model_copy(update={"member_sha256": sha256_hex(b"changed")})
    with pytest.raises(BodsAdapterError, match="MEMBER_HASH_MISMATCH"):
        parse_bods_siri_vm((broken, body), scope())


@pytest.mark.parametrize(
    "payload",
    [
        b'<?xml version="1.0"?><!DOCTYPE Siri [<!ENTITY x "expanded">]>'
        b'<Siri xmlns="http://www.siri.org.uk/siri">&x;</Siri>',
        b'<Siri xmlns="https://example.invalid/not-siri"/>',
        b"not XML",
    ],
)
def test_unsafe_malformed_or_wrong_namespace_xml_is_rejected(payload: bytes) -> None:
    report = parse(payload)
    assert report.status is ManchesterValidationState.REJECTED
    assert finding_codes(report) == {"MALFORMED_OR_UNSAFE_XML"}
    assert payload.decode(errors="ignore") not in report.canonical_json()


def test_parser_performs_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert parse().status is ManchesterValidationState.ACCEPTED


def test_model_contract_cannot_enable_retention_or_public_export() -> None:
    rendered = json.loads(parse().canonical_json())
    rendered["retention_policy_approved"] = True
    with pytest.raises(ValidationError):
        BodsParseReport.model_validate(rendered)

    rendered = json.loads(parse().canonical_json())
    rendered["public_export_available"] = True
    with pytest.raises(ValidationError):
        BodsParseReport.model_validate(rendered)
