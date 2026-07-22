"""Offline acceptance and negative evidence for the MAN-03 WebTRIS parser."""

from __future__ import annotations

import json
import socket
from base64 import b64decode
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.models import ManchesterValidationState, sha256_hex
from traffictwin.integration.manchester.webtris import (
    MPH_TO_MPS,
    SPEED_BIN_FIELDS,
    WebtrisAdapterError,
    WebtrisDailyObservation,
    WebtrisDailyParseReport,
    WebtrisDailyScope,
    WebtrisMemberRef,
    WebtrisSiteParseReport,
    parse_webtris_daily_quality,
    parse_webtris_daily_report,
    parse_webtris_site,
)

FIXTURE_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "manchester" / "webtris"
SNAPSHOT_ID = "webtris-20260722T130000Z-abcdef012345"
SCOPE = WebtrisDailyScope(
    site_id="34",
    site_name="M56/8150A",
    report_date=date(2026, 3, 1),
)
FIXTURE_HASHES = {
    "site-34.json.b64": "f88cfc3442beb93a3e78b342891d8533566f50d6345a869152ee5aa1585488f7",
    "daily-site-34-20260301.json.b64": (
        "0a4d9f35f65c5f579102e23e4cc19525984701e610a56bb51196723941f550b5"
    ),
    "quality-site-34-20260301.json.b64": (
        "0c64204d9a32b3ae21aee61667103ee8d46e6fc5f2ba421fb0332ae1c0906654"
    ),
}


def fixture(name: str) -> bytes:
    payload = b64decode((FIXTURE_DIRECTORY / name).read_text(encoding="ascii"))
    assert sha256_hex(payload) == FIXTURE_HASHES[name]
    return payload


def ref(
    payload: bytes,
    role: str,
    *,
    path: str = "official/page-1.json",
    page: int = 1,
    synthetic: bool = False,
    snapshot_id: str = SNAPSHOT_ID,
) -> WebtrisMemberRef:
    return WebtrisMemberRef.model_validate(
        {
            "snapshot_id": snapshot_id,
            "member_path": path,
            "member_sha256": sha256_hex(payload),
            "member_role": role,
            "page_number": page,
            "synthetic": synthetic,
        }
    )


def daily_report(payload: bytes | None = None) -> WebtrisDailyParseReport:
    body = fixture("daily-site-34-20260301.json.b64") if payload is None else payload
    return parse_webtris_daily_report(((ref(body, "daily_report"), body),), SCOPE)


def finding_codes(report: object) -> set[str]:
    return {finding.code for finding in report.findings}  # type: ignore[attr-defined]


def mutate_daily(mutator: Callable[[dict[str, object]], None]) -> bytes:
    decoded = json.loads(fixture("daily-site-34-20260301.json.b64"))
    mutator(decoded)
    return json.dumps(decoded, separators=(",", ":")).encode()


def daily_rows(decoded: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], decoded["Rows"])


def test_exact_official_site_fixture_and_scope() -> None:
    payload = fixture("site-34.json.b64")
    report = parse_webtris_site((ref(payload, "site"), payload))
    assert report.status is ManchesterValidationState.ACCEPTED
    assert report.synthetic is False
    assert len(report.records) == 1
    site = report.records[0]
    assert site.site_id == "34"
    assert site.description == "M56/8150A"
    assert site.source_status == "Active"
    assert site.latitude == Decimal("53.3578532696194")
    assert site.longitude == Decimal("-2.30747451952892")
    assert site.road_domain == "national_highways_strategic_road"


def test_exact_official_daily_fixture_preserves_missing_and_source_time() -> None:
    report = daily_report()
    assert report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert report.counts.records_accepted == 96
    assert report.counts.intervals_missing > 0
    assert finding_codes(report) == {
        "LENGTH_TOTAL_MISMATCH",
        "MISSING_INTERVAL_MEASUREMENTS",
    }

    first = report.records[0]
    assert first.measurement_state == "missing"
    assert first.total_volume is None
    assert first.length_counts.cm_0_520 is None
    assert first.time_basis == "source_string_undeclared"
    assert "utc" not in {name.lower() for name in type(first).model_fields}

    observed = next(record for record in report.records if record.average_speed_mph is not None)
    assert observed.average_speed_mph is not None
    assert observed.average_speed_mps == observed.average_speed_mph * MPH_TO_MPS
    assert observed.evidence_status == "historical"
    assert observed.road_domain == "national_highways_strategic_road"
    assert any(record.time_period_ending_raw == "02:23:00" for record in report.records)
    source_mismatch = report.records[82]
    assert source_mismatch.length_total_reconciled is False
    assert source_mismatch.total_volume == 414


def test_exact_official_quality_is_availability_not_accuracy() -> None:
    payload = fixture("quality-site-34-20260301.json.b64")
    report = parse_webtris_daily_quality((ref(payload, "daily_quality"), payload), SCOPE)
    assert report.status is ManchesterValidationState.ACCEPTED
    quality = report.records[0]
    assert quality.availability_percent == 89
    assert quality.interpretation == "data_availability_percentage"
    assert quality.sensor_accuracy_claim_available is False
    assert quality.traffic_validity_claim_available is False


def test_exact_daily_schema_is_frozen() -> None:
    def add_field(decoded: dict[str, object]) -> None:
        daily_rows(decoded)[0]["Average Speed"] = "60"

    report = daily_report(mutate_daily(add_field))
    assert report.status is ManchesterValidationState.REJECTED
    assert "DAILY_SCHEMA_DRIFT" in finding_codes(report)


def test_all_four_length_bins_reconcile_to_total_volume() -> None:
    def break_total(decoded: dict[str, object]) -> None:
        row = next(row for row in daily_rows(decoded) if row["Total Volume"] != "")
        total = row["Total Volume"]
        assert isinstance(total, str)
        row["Total Volume"] = str(int(total) + 1)

    report = daily_report(mutate_daily(break_total))
    assert report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert "LENGTH_TOTAL_MISMATCH" in finding_codes(report)
    assert report.counts.records_accepted == 96


def test_complete_speed_bins_reconcile_to_total_volume() -> None:
    def populate_speed_bins(decoded: dict[str, object]) -> None:
        row = next(row for row in daily_rows(decoded) if row["Total Volume"] != "")
        for name in SPEED_BIN_FIELDS:
            row[name] = "0"
        row[SPEED_BIN_FIELDS[-1]] = row["Total Volume"]

    accepted = daily_report(mutate_daily(populate_speed_bins))
    assert accepted.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS

    def break_speed_bins(decoded: dict[str, object]) -> None:
        populate_speed_bins(decoded)
        row = next(row for row in daily_rows(decoded) if row["Total Volume"] != "")
        row[SPEED_BIN_FIELDS[0]] = "1"

    rejected = daily_report(mutate_daily(break_speed_bins))
    assert rejected.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert "SPEED_TOTAL_MISMATCH" in finding_codes(rejected)


def test_incomplete_or_duplicate_interval_set_rejects() -> None:
    def remove_interval(decoded: dict[str, object]) -> None:
        daily_rows(decoded).pop()

    incomplete = daily_report(mutate_daily(remove_interval))
    assert incomplete.status is ManchesterValidationState.REJECTED
    assert "INCOMPLETE_INTERVAL_SET" in finding_codes(incomplete)

    def duplicate_interval(decoded: dict[str, object]) -> None:
        daily_rows(decoded)[1]["Time Interval"] = "0"

    duplicate = daily_report(mutate_daily(duplicate_interval))
    assert duplicate.status is ManchesterValidationState.REJECTED
    assert "DUPLICATE_INTERVAL" in finding_codes(duplicate)


def test_page_input_order_is_deterministic() -> None:
    decoded = json.loads(fixture("daily-site-34-20260301.json.b64"))
    header = decoded["Header"]
    rows = decoded["Rows"]
    page_1 = json.dumps({"Header": header, "Rows": rows[:48]}, separators=(",", ":")).encode()
    page_2 = json.dumps({"Header": header, "Rows": rows[48:]}, separators=(",", ":")).encode()
    member_1 = (ref(page_1, "daily_report", path="pages/1.json", page=1), page_1)
    member_2 = (ref(page_2, "daily_report", path="pages/2.json", page=2), page_2)
    forward = parse_webtris_daily_report((member_1, member_2), SCOPE)
    reverse = parse_webtris_daily_report((member_2, member_1), SCOPE)
    assert forward.canonical_json() == reverse.canonical_json()
    assert forward.fingerprint() == reverse.fingerprint()


def test_dates_and_clocks_remain_strict_source_strings() -> None:
    def bad_date(decoded: dict[str, object]) -> None:
        daily_rows(decoded)[0]["Report Date"] = "2026-03-01T01:00:00"

    assert "MALFORMED_DAILY_ROW" in finding_codes(daily_report(mutate_daily(bad_date)))

    def bad_clock(decoded: dict[str, object]) -> None:
        daily_rows(decoded)[0]["Time Period Ending"] = "24:00:00"

    assert "MALFORMED_DAILY_ROW" in finding_codes(daily_report(mutate_daily(bad_clock)))


def test_pagination_links_are_validated_but_never_persisted() -> None:
    def valid_link(decoded: dict[str, object]) -> None:
        header = cast(dict[str, object], decoded["Header"])
        header["links"] = [
            {
                "href": "http://webtris.nationalhighways.co.uk/api/v1.0/reports/Daily?page=2",
                "rel": "nextPage",
            }
        ]

    accepted = daily_report(mutate_daily(valid_link))
    assert accepted.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert "page=2" not in accepted.canonical_json()
    assert "http://" not in accepted.canonical_json()

    def bad_link(decoded: dict[str, object]) -> None:
        header = cast(dict[str, object], decoded["Header"])
        header["links"] = [{"href": "https://example.invalid", "rel": "execute"}]

    rejected = daily_report(mutate_daily(bad_link))
    assert rejected.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_HEADER" in finding_codes(rejected)


def test_broken_lineage_and_mixed_sources_raise_typed_errors() -> None:
    payload = fixture("daily-site-34-20260301.json.b64")
    broken = ref(payload, "daily_report").model_copy(
        update={"member_sha256": sha256_hex(b"changed")}
    )
    with pytest.raises(WebtrisAdapterError) as mismatch:
        parse_webtris_daily_report(((broken, payload),), SCOPE)
    assert mismatch.value.code == "MEMBER_HASH_MISMATCH"

    page_1 = ref(payload, "daily_report", path="pages/1.json")
    page_2 = ref(
        payload,
        "daily_report",
        path="pages/2.json",
        page=2,
        snapshot_id="webtris-20260722T140000Z-fedcba987654",
    )
    with pytest.raises(WebtrisAdapterError) as mixed:
        parse_webtris_daily_report(((page_1, payload), (page_2, payload)), SCOPE)
    assert mixed.value.code == "MIXED_SNAPSHOTS"


def test_non_standard_json_is_rejected() -> None:
    payload = b'{"row_count":1,"sites":[{"Longitude":NaN}]}'
    report = parse_webtris_site((ref(payload, "site", synthetic=True), payload))
    assert report.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_JSON" in finding_codes(report)


def test_parser_is_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert daily_report().counts.records_accepted == 96


def test_strict_models_reject_strengthened_claims() -> None:
    report = daily_report()
    payload = json.loads(report.canonical_json())
    payload["records"][0]["timestamp_utc"] = "2026-03-01T00:14:59Z"
    with pytest.raises(ValidationError):
        type(report).model_validate(payload)

    site_payload = fixture("site-34.json.b64")
    site_report = parse_webtris_site((ref(site_payload, "site"), site_payload))
    strengthened = json.loads(site_report.canonical_json())
    strengthened["city_road_coverage"] = True
    with pytest.raises(ValidationError):
        WebtrisSiteParseReport.model_validate(strengthened)


def test_observation_model_requires_exact_mph_conversion() -> None:
    record = next(
        record for record in daily_report().records if record.average_speed_mph is not None
    )
    payload = json.loads(record.canonical_json())
    payload["average_speed_mps"] = "999"
    with pytest.raises(ValidationError):
        WebtrisDailyObservation.model_validate(payload)
