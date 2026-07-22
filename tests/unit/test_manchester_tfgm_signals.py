"""Offline acceptance and refusal evidence for the MAN-04 TfGM parser."""

from __future__ import annotations

import csv
import io
import json
import socket
from base64 import b64decode
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.models import ManchesterValidationState, sha256_hex
from traffictwin.integration.manchester.tfgm_signals import (
    TFGM_SIGNAL_HEADER,
    TFGM_SIGNALS_ARCHIVE_SHA256,
    TFGM_SIGNALS_ATTRIBUTION,
    TfgmSignalAdapterError,
    TfgmSignalMemberRef,
    TfgmSignalParseReport,
    parse_tfgm_signal_csv,
)

FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "manchester" / "tfgm" / "signals-manchester-3.csv.b64"
)
FIXTURE_SHA256 = "becf158f1bbb1b15ab3eafd2e312ffd736a2f49497726c6802e1a4dacbdcf0f2"
SNAPSHOT_ID = "tfgm_signals-20260722T150000Z-abcdef012345"


def fixture() -> bytes:
    payload = b64decode(FIXTURE.read_text(encoding="ascii"))
    assert sha256_hex(payload) == FIXTURE_SHA256
    return payload


def member(
    payload: bytes,
    *,
    evidence_class: str = "redistributable_derived_sample",
    synthetic: bool = False,
) -> TfgmSignalMemberRef:
    return TfgmSignalMemberRef.model_validate(
        {
            "snapshot_id": SNAPSHOT_ID,
            "member_path": "derived/signals-manchester-3.csv",
            "member_sha256": sha256_hex(payload),
            "evidence_class": evidence_class,
            "source_archive_sha256": TFGM_SIGNALS_ARCHIVE_SHA256,
            "synthetic": synthetic,
        }
    )


def parse(payload: bytes | None = None) -> TfgmSignalParseReport:
    body = fixture() if payload is None else payload
    return parse_tfgm_signal_csv((member(body), body))


def csv_rows(payload: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline="")))


def encode_rows(rows: list[list[str]]) -> bytes:
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\r\n").writerows(rows)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def finding_codes(report: TfgmSignalParseReport) -> set[str]:
    return {finding.code for finding in report.findings}


def test_attributed_derived_fixture_parses_without_full_dataset_claim() -> None:
    report = parse()
    assert report.status is ManchesterValidationState.ACCEPTED
    assert report.complete_dataset is False
    assert report.publication_class == "redistributable_derived"
    assert report.attribution == TFGM_SIGNALS_ATTRIBUTION
    assert report.counts.rows_seen == 3
    assert report.counts.records_accepted == 3
    assert report.counts.authorities_present == 1

    first = report.records[0]
    assert first.fras_ref == "0001"
    assert first.authority == "Manchester"
    assert first.signal_type == "Junction"
    assert first.control_type == "UTC"
    assert first.easting_epsg27700 == 383626
    assert str(first.longitude_epsg4326) == "-2.24815652"
    assert first.key_route_network is False
    assert first.coordinate_crosscheck_passed is True


def test_static_reference_cannot_claim_live_signal_behaviour() -> None:
    record = parse().records[0]
    assert record.evidence_status == "static_reference"
    assert record.live_state_available is False
    assert record.phase_available is False
    assert record.timing_available is False
    assert record.queue_available is False
    assert record.traffic_count_available is False
    assert record.incident_available is False

    strengthened = json.loads(record.canonical_json())
    strengthened["live_state_available"] = True
    with pytest.raises(ValidationError):
        type(record).model_validate(strengthened)

    strengthened["live_state_available"] = False
    strengthened["current_phase"] = "green"
    with pytest.raises(ValidationError):
        type(record).model_validate(strengthened)


def test_header_and_utf8_bom_are_required() -> None:
    body = fixture()
    without_bom = body.removeprefix(b"\xef\xbb\xbf")
    missing_bom = parse(without_bom)
    assert missing_bom.status is ManchesterValidationState.REJECTED
    assert "MISSING_UTF8_BOM" in finding_codes(missing_bom)

    rows = csv_rows(body)
    rows[0][0] = "FRAS_ID"
    wrong_header = parse(encode_rows(rows))
    assert wrong_header.status is ManchesterValidationState.REJECTED
    assert "HEADER_MISMATCH" in finding_codes(wrong_header)


def test_coordinate_corruption_is_rejected() -> None:
    rows = csv_rows(fixture())
    longitude_index = rows[0].index("Longitude")
    rows[1][longitude_index] = "-3.00000000"
    report = parse(encode_rows(rows))
    assert report.status is ManchesterValidationState.REJECTED
    assert "COORDINATE_MISMATCH" in finding_codes(report)
    assert report.counts.rows_malformed == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Type", "Traffic Camera"),
        ("Type_Of_Control", "Unknown"),
        ("Authority", "Liverpool"),
        ("NIS_node", "1.5"),
        ("KRN", "Maybe"),
    ],
)
def test_out_of_contract_values_are_rejected(field: str, value: str) -> None:
    rows = csv_rows(fixture())
    rows[1][rows[0].index(field)] = value
    report = parse(encode_rows(rows))
    assert report.status is ManchesterValidationState.REJECTED
    assert "MALFORMED_ROW" in finding_codes(report)


def test_empty_krn_is_missing_not_false() -> None:
    rows = csv_rows(fixture())
    rows[1][rows[0].index("KRN")] = ""
    report = parse(encode_rows(rows))
    assert report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert report.records[0].key_route_network is None
    assert report.counts.rows_with_unknown_krn == 1
    assert finding_codes(report) == {"KRN_MISSING"}


def test_duplicate_fras_reference_rejects_the_report() -> None:
    rows = csv_rows(fixture())
    rows[2][rows[0].index("FRAS_ref")] = rows[1][rows[0].index("FRAS_ref")]
    report = parse(encode_rows(rows))
    assert report.status is ManchesterValidationState.REJECTED
    assert "DUPLICATE_FRAS_REF" in finding_codes(report)
    assert report.records == ()


def test_full_official_claim_requires_exact_csv_identity() -> None:
    body = fixture()
    full_claim = member(body, evidence_class="full_official_csv")
    with pytest.raises(TfgmSignalAdapterError) as excinfo:
        parse_tfgm_signal_csv((full_claim, body))
    assert excinfo.value.code == "OFFICIAL_CSV_IDENTITY_MISMATCH"

    with pytest.raises(ValidationError):
        TfgmSignalMemberRef.model_validate(
            {
                **member(body).model_dump(),
                "evidence_class": "full_official_csv",
                "synthetic": True,
            }
        )


def test_hash_mutation_is_refused_before_csv_parsing() -> None:
    body = fixture()
    broken = member(body).model_copy(update={"member_sha256": sha256_hex(b"changed")})
    with pytest.raises(TfgmSignalAdapterError) as excinfo:
        parse_tfgm_signal_csv((broken, body))
    assert excinfo.value.code == "MEMBER_HASH_MISMATCH"


def test_row_order_has_deterministic_canonical_output() -> None:
    rows = csv_rows(fixture())
    reversed_body = encode_rows([rows[0], *reversed(rows[1:])])
    reversed_report = parse(reversed_body)
    original = parse()
    assert [record.fras_ref for record in reversed_report.records] == ["0001", "0010", "0100"]
    assert [record.fras_ref for record in original.records] == ["0001", "0010", "0100"]


def test_parser_performs_no_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert parse().status is ManchesterValidationState.ACCEPTED


def test_header_contract_contains_exactly_fifteen_fields() -> None:
    assert len(TFGM_SIGNAL_HEADER) == 15
    assert TFGM_SIGNAL_HEADER[0] == "FRAS_ref"
    assert TFGM_SIGNAL_HEADER[-1] == "KRN"
