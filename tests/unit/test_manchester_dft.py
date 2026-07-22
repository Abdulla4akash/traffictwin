"""Unit tests for the MAN-02 DfT adapter library (synthetic fixtures only).

Every payload below is a synthetic, clearly labelled software fixture shaped
exactly like the Gate A audited DfT contract. No fixture is real DfT data and
nothing here contacts a network.
"""

from __future__ import annotations

import json
import socket
from base64 import b64decode
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.dft import (
    DftAadfParseReport,
    DftAdapterError,
    DftCountPointParseReport,
    DftManchesterScope,
    DftMemberRef,
    DftRawCountParseReport,
    DftRawCountRecord,
    parse_dft_aadf,
    parse_dft_count_points,
    parse_dft_raw_counts,
)
from traffictwin.integration.manchester.models import (
    ManchesterValidationState,
    sha256_hex,
)

SNAPSHOT_ID = "dft_manchester-20260722T100000Z-abcdef012345"
REAL_FIXTURE_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "manchester" / "dft"
SCOPE = DftManchesterScope()


def make_ref(path: str, payload: bytes, synthetic: bool = True) -> DftMemberRef:
    return DftMemberRef(
        snapshot_id=SNAPSHOT_ID,
        member_path=path,
        member_sha256=sha256_hex(payload),
        synthetic=synthetic,
    )


def envelope(
    rows: list[dict[str, object]],
    current_page: int = 1,
    last_page: int = 1,
    per_page: int | None = None,
    total: int | None = None,
    **extra: object,
) -> bytes:
    body: dict[str, object] = {
        "current_page": current_page,
        "per_page": per_page if per_page is not None else max(len(rows), 1),
        "total": total if total is not None else len(rows),
        "last_page": last_page,
        "from": 1 if rows else None,
        "to": len(rows) if rows else None,
        "path": "synthetic-fixture",
        "first_page_url": "synthetic-fixture",
        "last_page_url": "synthetic-fixture",
        "next_page_url": None,
        "prev_page_url": None,
        "links": [],
        "data": rows,
    }
    body.update(extra)
    return json.dumps(body).encode("utf-8")


def raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 1001,
        "count_point_id": 12345,
        "direction_of_travel": "N",
        "year": 2004,
        "count_date": "2004-05-21",
        "hour": 12,
        "region_id": 5,
        "local_authority_id": 85,
        "road_name": "Synthetic Way",
        "road_category": "PA",
        "road_type": "Major",
        "start_junction_road_name": "Synthetic Start",
        "end_junction_road_name": "Synthetic End",
        "easting": 383500,
        "northing": 398500,
        "latitude": 53.48,
        "longitude": -2.24,
        "link_length_km": 1.2,
        "link_length_miles": 0.75,
        "pedal_cycles": 5,
        "two_wheeled_motor_vehicles": 10,
        "cars_and_taxis": 100,
        "buses_and_coaches": 7,
        "lgvs": 20,
        "hgvs_2_rigid_axle": 4,
        "hgvs_3_rigid_axle": 3,
        "hgvs_4_or_more_rigid_axle": 2,
        "hgvs_3_or_4_articulated_axle": 1,
        "hgvs_5_articulated_axle": 1,
        "hgvs_6_articulated_axle": 1,
        "all_hgvs": 12,
        "all_motor_vehicles": 149,
    }
    row.update(overrides)
    return row


def count_point_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 501,
        "count_point_id": 12345,
        "aadf_year": 2025,
        "region_id": 5,
        "local_authority_id": 85,
        "road_name": "Synthetic Way",
        "road_category": "PA",
        "road_type": "Major",
        "start_junction_road_name": "Synthetic Start",
        "end_junction_road_name": "Synthetic End",
        "easting": 383500,
        "northing": 398500,
        "latitude": 53.48,
        "longitude": -2.24,
        "link_length_km": 1.2,
        "link_length_miles": 0.75,
    }
    row.update(overrides)
    return row


def aadf_row(**overrides: object) -> dict[str, object]:
    row = raw_row()
    for name in ("direction_of_travel", "count_date", "hour"):
        row.pop(name)
    row["estimation_method"] = "Estimated"
    row["estimation_method_detailed"] = "Synthetic estimation label"
    row.update(overrides)
    return row


def parse_raw(
    rows: list[dict[str, object]],
    per_page: int | None = None,
    total: int | None = None,
) -> DftRawCountParseReport:
    payload = envelope(rows, per_page=per_page, total=total)
    return parse_dft_raw_counts([(make_ref("pages/page-1.json", payload), payload)], SCOPE)


def finding_codes(
    report: DftRawCountParseReport | DftCountPointParseReport | DftAadfParseReport,
) -> set[str]:
    return {finding.code for finding in report.findings}


def test_parses_valid_raw_count_page() -> None:
    report = parse_raw([raw_row()])
    assert report.status is ManchesterValidationState.ACCEPTED
    assert report.counts.records_accepted == 1
    record = report.records[0]
    assert record.count_point_id == 12345
    assert record.direction_of_travel == "N"
    assert record.count_date == date(2004, 5, 21)
    assert record.hour == 12
    assert record.time_basis == "local_clock_hour"
    assert record.evidence_status == "historical"
    assert record.evidence_kind == "survey_hour_raw_count"
    assert record.measured_speed_available is False
    assert record.ons_code == "E08000003"
    assert record.location.latitude == Decimal("53.48")
    assert record.location.easting == Decimal("383500")
    assert record.counts.all_motor_vehicles == 149
    assert record.counts.pedal_cycles == 5
    assert record.source.snapshot_id == SNAPSHOT_ID
    assert record.source.member_path == "pages/page-1.json"


@pytest.mark.parametrize(
    ("filename", "expected_sha256", "parser"),
    [
        (
            "raw-count-43177.json.b64",
            "06869d2d3ff2606a719bd043bcf8f3e30ad7fca17df1084c12598912c4a56c22",
            parse_dft_raw_counts,
        ),
        (
            "count-point-6046.json.b64",
            "525250e7df43cbd8738e841fccf1d3b1a2787c229f87c6dd7d00ca019c122635",
            parse_dft_count_points,
        ),
        (
            "aadf-9219.json.b64",
            "d46e8c8fa29dbf72b3cd974a5dc6349fb8750e32e6758aad91b8b588cb4571a5",
            parse_dft_aadf,
        ),
    ],
)
def test_minimal_official_manchester_fixtures(
    filename: str,
    expected_sha256: str,
    parser: object,
) -> None:
    payload = b64decode((REAL_FIXTURE_DIRECTORY / filename).read_text(encoding="ascii"))
    assert sha256_hex(payload) == expected_sha256
    ref = DftMemberRef(
        snapshot_id="dft_manchester-20260722T120000Z-123456789abc",
        member_path=f"official/{filename.removesuffix('.b64')}",
        member_sha256=expected_sha256,
        synthetic=False,
    )
    report = parser([(ref, payload)], SCOPE)  # type: ignore[operator]
    assert report.status is ManchesterValidationState.ACCEPTED
    assert report.synthetic is False
    assert len(report.records) == 1
    record = report.records[0]
    assert record.local_authority_id == 85
    assert record.ons_code == "E08000003"
    assert record.location.latitude == Decimal("53.39597741")
    assert record.location.link_length_km == Decimal("1.0")


def test_deterministic_fingerprint_and_page_order_independence() -> None:
    row_a = raw_row()
    row_b = raw_row(id=1002, count_point_id=22222, hour=13)
    page_1 = envelope([row_a], current_page=1, last_page=2, per_page=1, total=2)
    page_2 = envelope([row_b], current_page=2, last_page=2, per_page=1, total=2)
    members_forward = [
        (make_ref("pages/page-1.json", page_1), page_1),
        (make_ref("pages/page-2.json", page_2), page_2),
    ]
    members_reversed = list(reversed(members_forward))
    forward = parse_dft_raw_counts(members_forward, SCOPE)
    reversed_ = parse_dft_raw_counts(members_reversed, SCOPE)
    assert forward.fingerprint() == reversed_.fingerprint()
    assert forward.canonical_json() == reversed_.canonical_json()
    assert [r.count_point_id for r in forward.records] == [12345, 22222]


def test_manchester_scope_is_enforced() -> None:
    report = parse_raw([raw_row(), raw_row(id=1002, local_authority_id=999)])
    assert report.status is ManchesterValidationState.REJECTED
    assert "OUT_OF_SCOPE_RECORD" in finding_codes(report)
    assert report.counts.rows_excluded_out_of_scope == 1


def test_survey_and_aadf_families_cannot_cross() -> None:
    aadf_into_raw = parse_raw([aadf_row()])
    assert aadf_into_raw.status is ManchesterValidationState.REJECTED
    assert "UNEXPECTED_FIELD" in finding_codes(aadf_into_raw)

    raw_payload = envelope([raw_row()])
    raw_into_aadf = parse_dft_aadf(
        [(make_ref("pages/page-1.json", raw_payload), raw_payload)], SCOPE
    )
    assert raw_into_aadf.status is ManchesterValidationState.REJECTED
    assert "UNEXPECTED_FIELD" in finding_codes(raw_into_aadf)

    aadf_payload = envelope([aadf_row()])
    aadf_report = parse_dft_aadf(
        [(make_ref("pages/page-1.json", aadf_payload), aadf_payload)], SCOPE
    )
    assert aadf_report.status is ManchesterValidationState.ACCEPTED
    record = aadf_report.records[0]
    assert record.statistical_not_survey is True
    assert record.evidence_kind == "annual_average_daily_flow"
    assert record.time_basis == "date_only"


def test_speed_is_structurally_unavailable() -> None:
    speed_fields = {name for name in DftRawCountRecord.model_fields if "speed" in name}
    assert speed_fields == {"measured_speed_available"}

    record = parse_raw([raw_row()]).records[0]
    flipped = json.loads(record.canonical_json())
    flipped["measured_speed_available"] = True
    with pytest.raises(ValidationError):
        DftRawCountRecord.model_validate_json(json.dumps(flipped))

    report = parse_raw([raw_row(speed_mph=42)])
    assert report.status is ManchesterValidationState.REJECTED
    assert "UNEXPECTED_FIELD" in finding_codes(report)


def test_vehicle_class_totals_reconcile_exactly() -> None:
    bad_hgv = parse_raw([raw_row(all_hgvs=13)])
    assert bad_hgv.status is ManchesterValidationState.REJECTED
    assert "INCONSISTENT_HGV_TOTAL" in finding_codes(bad_hgv)

    bad_motor = parse_raw([raw_row(all_motor_vehicles=150)])
    assert bad_motor.status is ManchesterValidationState.REJECTED
    assert "INCONSISTENT_MOTOR_TOTAL" in finding_codes(bad_motor)


def test_null_and_missing_field_behaviour() -> None:
    incomplete = parse_raw([raw_row(cars_and_taxis=None, all_motor_vehicles=None)])
    assert incomplete.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert "COUNTS_INCOMPLETE" in finding_codes(incomplete)
    assert incomplete.counts.records_with_incomplete_counts == 1
    assert incomplete.records[0].counts.cars_and_taxis is None

    null_required = parse_raw([raw_row(hour=None)])
    assert null_required.status is ManchesterValidationState.REJECTED
    assert "NULL_REQUIRED_FIELD" in finding_codes(null_required)

    row = raw_row()
    del row["count_date"]
    missing_key = parse_raw([row])
    assert missing_key.status is ManchesterValidationState.REJECTED
    assert "MISSING_FIELD" in finding_codes(missing_key)


@pytest.mark.parametrize(
    "value", ["2004-13-45", "21/05/2004", "2004-05-21T00:00:00", "", 20040521, None]
)
def test_malformed_dates_are_refused(value: object) -> None:
    report = parse_raw([raw_row(count_date=value)])
    assert report.status is ManchesterValidationState.REJECTED
    assert finding_codes(report) & {"MALFORMED_DATE", "NULL_REQUIRED_FIELD"}


@pytest.mark.parametrize("value", [24, -1, "12", 3.5])
def test_malformed_hours_are_refused(value: object) -> None:
    report = parse_raw([raw_row(hour=value)])
    assert report.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_HOUR" in finding_codes(report)


def test_year_and_count_date_must_agree() -> None:
    report = parse_raw([raw_row(year=2005)])
    assert report.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_ROW" in finding_codes(report)


def test_identical_duplicates_collapse_and_conflicts_reject() -> None:
    identical = parse_raw(
        [raw_row(), raw_row(id=1002)],
        per_page=2,
        total=2,
    )
    assert identical.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert "DUPLICATE_ROW" in finding_codes(identical)
    assert identical.counts.duplicate_rows_collapsed == 1
    assert identical.counts.records_accepted == 1

    conflicting = parse_raw(
        [raw_row(), raw_row(id=1002, cars_and_taxis=90, all_motor_vehicles=139)],
        per_page=2,
        total=2,
    )
    assert conflicting.status is ManchesterValidationState.REJECTED
    assert "CONFLICTING_DUPLICATE" in finding_codes(conflicting)
    assert conflicting.counts.records_accepted == 0
    assert conflicting.counts.rows_excluded_conflicting == 2


def test_unexpected_fields_are_rejected() -> None:
    report = parse_raw([raw_row(average_speed_mph=48.0)])
    assert report.status is ManchesterValidationState.REJECTED
    assert "UNEXPECTED_FIELD" in finding_codes(report)


def test_out_of_contract_envelope_is_rejected() -> None:
    payload = envelope([raw_row()], bogus_envelope_key=1)
    report = parse_dft_raw_counts([(make_ref("pages/page-1.json", payload), payload)], SCOPE)
    assert report.status is ManchesterValidationState.REJECTED
    assert "UNEXPECTED_ENVELOPE_FIELD" in finding_codes(report)

    not_json = b"\x00\x01synthetic-not-json"
    bad = parse_dft_raw_counts([(make_ref("pages/page-1.json", not_json), not_json)], SCOPE)
    assert bad.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_JSON" in finding_codes(bad)


def test_pagination_contract_is_enforced() -> None:
    page_2_only = envelope([raw_row()], current_page=2, last_page=2, per_page=1, total=2)
    report = parse_dft_raw_counts(
        [(make_ref("pages/page-2.json", page_2_only), page_2_only)], SCOPE
    )
    assert report.status is ManchesterValidationState.REJECTED
    assert "INCOMPLETE_PAGE_SET" in finding_codes(report)

    total_mismatch = envelope([raw_row()], total=5, per_page=5)
    mismatch = parse_dft_raw_counts(
        [(make_ref("pages/page-1.json", total_mismatch), total_mismatch)], SCOPE
    )
    assert mismatch.status is ManchesterValidationState.REJECTED
    assert "ROW_TOTAL_MISMATCH" in finding_codes(mismatch)

    page_1 = envelope([raw_row()], current_page=1, last_page=2, per_page=1, total=2)
    page_2 = envelope([raw_row(id=1002, hour=13)], current_page=2, last_page=2, per_page=1, total=3)
    inconsistent = parse_dft_raw_counts(
        [
            (make_ref("pages/page-1.json", page_1), page_1),
            (make_ref("pages/page-2.json", page_2), page_2),
        ],
        SCOPE,
    )
    assert inconsistent.status is ManchesterValidationState.REJECTED
    assert "INCONSISTENT_PAGE_SET" in finding_codes(inconsistent)


def test_lineage_is_preserved_and_hash_mismatch_refused() -> None:
    payload = envelope([raw_row()])
    ref = make_ref("pages/page-1.json", payload)
    report = parse_dft_raw_counts([(ref, payload)], SCOPE)
    assert report.sources == (ref,)
    assert report.records[0].source == ref

    tampered = DftMemberRef(
        snapshot_id=SNAPSHOT_ID,
        member_path="pages/page-1.json",
        member_sha256=sha256_hex(b"other"),
        synthetic=True,
    )
    with pytest.raises(DftAdapterError) as excinfo:
        parse_dft_raw_counts([(tampered, payload)], SCOPE)
    assert excinfo.value.code == "MEMBER_HASH_MISMATCH"


def test_caller_misuse_raises_typed_errors() -> None:
    with pytest.raises(DftAdapterError) as no_members:
        parse_dft_raw_counts([], SCOPE)
    assert no_members.value.code == "NO_MEMBERS"

    payload = envelope([raw_row()])
    ref = make_ref("pages/page-1.json", payload)
    with pytest.raises(DftAdapterError) as duplicate:
        parse_dft_raw_counts([(ref, payload), (ref, payload)], SCOPE)
    assert duplicate.value.code == "DUPLICATE_MEMBER"


def test_no_network_access_during_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during pure parsing")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    report = parse_raw([raw_row()])
    assert report.status is ManchesterValidationState.ACCEPTED


def test_synthetic_labels_flow_from_sources() -> None:
    payload = envelope([raw_row()])
    synthetic_report = parse_dft_raw_counts(
        [(make_ref("pages/page-1.json", payload), payload)], SCOPE
    )
    assert synthetic_report.synthetic is True

    real_shaped_ref = make_ref("pages/page-1.json", payload, synthetic=False)
    non_synthetic = parse_dft_raw_counts([(real_shaped_ref, payload)], SCOPE)
    assert non_synthetic.synthetic is False

    stripped = json.loads(synthetic_report.canonical_json())
    stripped["synthetic"] = False
    with pytest.raises(ValidationError):
        DftRawCountParseReport.model_validate_json(json.dumps(stripped))


def test_count_points_parse_and_deduplicate() -> None:
    payload = envelope([count_point_row()], per_page=1, total=1)
    report = parse_dft_count_points([(make_ref("pages/page-1.json", payload), payload)], SCOPE)
    assert report.status is ManchesterValidationState.ACCEPTED
    record = report.records[0]
    assert record.evidence_kind == "count_point_reference"
    assert record.aadf_year == 2025
    assert record.ons_code == "E08000003"

    conflicting_payload = envelope(
        [count_point_row(), count_point_row(id=502, road_name="Different Road")],
        per_page=2,
        total=2,
    )
    conflicting = parse_dft_count_points(
        [(make_ref("pages/page-1.json", conflicting_payload), conflicting_payload)], SCOPE
    )
    assert conflicting.status is ManchesterValidationState.REJECTED
    assert "CONFLICTING_DUPLICATE" in finding_codes(conflicting)


def test_aadf_id_is_required_and_typed() -> None:
    row_without_id = aadf_row()
    del row_without_id["id"]
    payload = envelope([row_without_id])
    report = parse_dft_aadf([(make_ref("pages/page-1.json", payload), payload)], SCOPE)
    assert report.status is ManchesterValidationState.REJECTED
    assert "MISSING_FIELD" in finding_codes(report)

    bad_payload = envelope([aadf_row(id="not-an-int")])
    bad = parse_dft_aadf([(make_ref("pages/page-1.json", bad_payload), bad_payload)], SCOPE)
    assert bad.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_ROW" in finding_codes(bad)


def test_documented_decimal_strings_are_accepted_exactly() -> None:
    report = parse_raw(
        [
            raw_row(
                latitude="53.39597741",
                longitude="-2.24809417",
                link_length_km="1.0",
                link_length_miles="0.6",
            )
        ]
    )
    assert report.status is ManchesterValidationState.ACCEPTED
    assert report.records[0].location.latitude == Decimal("53.39597741")
    assert report.records[0].location.link_length_km == Decimal("1.0")


def test_scope_is_fixed_to_official_manchester_binding() -> None:
    assert SCOPE.local_authority_id == 85
    assert SCOPE.ons_code == "E08000003"
    with pytest.raises(ValidationError):
        DftManchesterScope.model_validate({"local_authority_id": 71})


def test_mixed_snapshot_or_evidence_classes_are_refused() -> None:
    payload_1 = envelope([raw_row()])
    payload_2 = envelope([raw_row(id=1002, hour=13)])
    ref_1 = make_ref("pages/page-1.json", payload_1)
    ref_2 = DftMemberRef(
        snapshot_id="dft_manchester-20260722T110000Z-fedcba987654",
        member_path="pages/page-2.json",
        member_sha256=sha256_hex(payload_2),
        synthetic=True,
    )
    with pytest.raises(DftAdapterError) as mixed_snapshots:
        parse_dft_raw_counts([(ref_1, payload_1), (ref_2, payload_2)], SCOPE)
    assert mixed_snapshots.value.code == "MIXED_SNAPSHOTS"

    real_ref = ref_1.model_copy(update={"synthetic": False})
    with pytest.raises(DftAdapterError) as mixed_classes:
        parse_dft_raw_counts([(ref_1, payload_1), (real_ref, payload_1)], SCOPE)
    assert mixed_classes.value.code == "MIXED_EVIDENCE_CLASS"


def test_non_standard_json_constants_are_refused() -> None:
    payload = envelope([raw_row()]).replace(b'"latitude": 53.48', b'"latitude": NaN')
    report = parse_dft_raw_counts([(make_ref("pages/page-1.json", payload), payload)], SCOPE)
    assert report.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_JSON" in finding_codes(report)


def test_report_models_reject_unknown_fields() -> None:
    report = parse_raw([raw_row()])
    payload = json.loads(report.canonical_json())
    payload["bogus"] = 1
    with pytest.raises(ValidationError):
        DftRawCountParseReport.model_validate_json(json.dumps(payload))

    round_trip = DftRawCountParseReport.model_validate_json(report.canonical_json())
    assert round_trip.fingerprint() == report.fingerprint()
