"""Offline unit tests for the controlled TfGM traffic-signals acquisition workflow.

All transports are injected fakes (httpx.MockTransport); no test touches the
network. Synthetic ZIPs are labelled synthetic and are never the official
release; the audited official hashes are asserted as pinned constants only.
"""

from __future__ import annotations

import io
import json
import socket
import zipfile
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from pyproj import Transformer

from traffictwin.integration.manchester.archive import ArchiveMember
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
from traffictwin.integration.manchester.tfgm_acquisition import (
    TFGM_ACQUISITION_METHOD_VERSION,
    TFGM_ACQUISITION_SCHEMA_VERSION,
    TFGM_FRESHNESS_POLICY_VERSION,
    TFGM_LICENCE_ID,
    TFGM_ZIP_MEMBER_PATH,
    TFGM_ZIP_PATH,
    TfgmAcquisitionError,
    TfgmAcquisitionRequest,
    TfgmAcquisitionResult,
    TfgmReplayRequest,
    TfgmReplayResult,
    TfgmSelectedMemberEvidence,
    acquire_tfgm_signals_snapshot,
    build_zip_inventory_fingerprint,
    replay_tfgm_quarantine,
)
from traffictwin.integration.manchester.tfgm_signals import (
    TFGM_SIGNAL_HEADER,
    TFGM_SIGNALS_ATTRIBUTION,
)

POLICY = ManchesterSnapshotPolicy(
    max_member_count=4, max_member_bytes=8_000_000, max_total_bytes=16_000_000
)
_TO_WGS84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
PDF_ATTRIBUTION_2025 = (
    "Contains Transport for Greater Manchester data. Contains OS data © Crown "
    "copyright and database right 2025."
)


def make_clock() -> Callable[[], datetime]:
    counter = iter(range(10_000))

    def clock() -> datetime:
        return datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=next(counter))

    return clock


def signal_row(fras: str, *, krn: str = "Yes", easting: int = 383500) -> list[str]:
    northing = 398500
    longitude, latitude = _TO_WGS84.transform(easting, northing)
    return [
        fras,
        "Synthetic junction (synthetic fixture)",
        "Junction",
        "",
        "",
        str(easting),
        str(northing),
        "SCOOT",
        "Manchester",
        "",
        f"{longitude:.10f}",
        f"{latitude:.10f}",
        "1",
        "",
        krn,
    ]


def csv_bytes(rows: list[list[str]]) -> bytes:
    lines = [",".join(TFGM_SIGNAL_HEADER)] + [",".join(row) for row in rows]
    return ("﻿" + "\r\n".join(lines) + "\r\n").encode("utf-8")


def build_zip(
    members: dict[str, bytes] | None = None,
    *,
    extra_infos: list[tuple[zipfile.ZipInfo, bytes]] | None = None,
) -> bytes:
    if members is None:
        members = {
            "CSV-format/TrafficSignals.csv": csv_bytes(
                [
                    signal_row("SYN001"),
                    signal_row("SYN002", easting=383600),
                    signal_row("SYN003", easting=383700),
                ]
            ),
            "TFGM_OGL.txt": (TFGM_SIGNALS_ATTRIBUTION + "\nSynthetic test copy.").encode("utf-8"),
            "GeoJSON-format/TrafficSignals.geojson": b'{"synthetic": true}',
        }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
        for info, payload in extra_infos or []:
            archive.writestr(info, payload)
    return buffer.getvalue()


def make_transport(
    payload: bytes,
    calls: list[tuple[str, str, dict[str, str]]],
    status: int = 200,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.host, request.url.path, dict(request.url.params)))
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(
            200,
            headers={"content-type": "application/x-zip-compressed"},
            stream=httpx.ByteStream(payload),
        )

    return httpx.MockTransport(handler)


def make_request(**overrides: object) -> TfgmAcquisitionRequest:
    values: dict[str, object] = {"policy": POLICY, "synthetic": True}
    values.update(overrides)
    return TfgmAcquisitionRequest.model_validate(values)


def acquire(
    workspace: Path,
    request: TfgmAcquisitionRequest,
    payload: bytes | None = None,
    calls: list[tuple[str, str, dict[str, str]]] | None = None,
    status: int = 200,
) -> TfgmAcquisitionResult:
    recorded = calls if calls is not None else []
    with httpx.Client(
        transport=make_transport(payload if payload is not None else build_zip(), recorded, status)
    ) as raw_client:
        return acquire_tfgm_signals_snapshot(
            workspace, request, http_client=raw_client, utc_now=make_clock()
        )


def workspace_dirs(workspace: Path, area: str) -> list[Path]:
    root = workspace / area
    if not root.is_dir():
        return []
    return [p for p in root.iterdir() if p.is_dir()]


def replay_request(expected_synthetic: bool | None = True) -> TfgmReplayRequest:
    return TfgmReplayRequest(expected_synthetic=expected_synthetic)


def test_exact_allowed_request_and_receipt_identity(tmp_path: Path) -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []
    result = acquire(tmp_path, make_request(), calls=calls)
    assert calls == [("odata.tfgm.com", TFGM_ZIP_PATH, {})]
    assert result.endpoint_path == TFGM_ZIP_PATH
    assert result.dataset_version == "nov-2025-jan-2026-release"
    assert result.publication_class == "private"
    assert result.attribution_text == TFGM_SIGNALS_ATTRIBUTION
    assert result.records_accepted == 3
    assert result.promoted is True


def test_arbitrary_url_path_query_and_limits_are_rejected() -> None:
    for injected in (
        {"host": "evil.invalid"},
        {"path": "/opendata/other.zip"},
        {"url": "https://evil.invalid/x.zip"},
        {"query": {"download": "1"}},
        {"max_members": 10_000_000},
        {"max_decompressed_bytes": 10**12},
        {"parser": "pickle"},
    ):
        with pytest.raises(ValidationError):
            make_request(**injected)
    field_names = set(TfgmAcquisitionRequest.model_fields)
    assert field_names.isdisjoint(
        {"host", "path", "url", "query", "endpoint", "publication_class", "archive_policy"}
    )


def test_download_byte_bound_publishes_nothing(tmp_path: Path) -> None:
    small_policy = ManchesterSnapshotPolicy(
        max_member_count=4, max_member_bytes=200, max_total_bytes=400
    )
    with pytest.raises(TfgmAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(policy=small_policy))
    assert excinfo.value.code == "TRANSPORT_FAILURE"
    assert excinfo.value.quarantine_snapshot_id is None
    assert not workspace_dirs(tmp_path, "quarantine")
    assert not workspace_dirs(tmp_path, "accepted")


def test_zip_is_quarantined_before_decompression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import traffictwin.integration.manchester.tfgm_acquisition as module
    from traffictwin.integration.manchester.archive import read_bounded_zip as original

    observed: dict[str, object] = {}

    def spying_read(payload: bytes, **kwargs: object) -> object:
        quarantine_dirs = workspace_dirs(tmp_path, "quarantine")
        assert len(quarantine_dirs) == 1
        observed["zip_present"] = (
            quarantine_dirs[0] / "raw" / "archive" / "traffic-signals.zip"
        ).is_file()
        observed["manifest_present"] = (quarantine_dirs[0] / "quarantine-manifest.json").is_file()
        return original(payload, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "read_bounded_zip", spying_read)
    acquire(tmp_path, make_request())
    assert observed == {"zip_present": True, "manifest_present": True}


def test_successful_promotion_preserves_attribution(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    accepted = workspace_dirs(tmp_path, "accepted")
    assert len(accepted) == 1
    receipt = verify_manchester_snapshot(accepted[0])
    assert receipt.fingerprint() == result.snapshot_receipt_fingerprint
    stored = ManchesterSnapshotManifest.model_validate_json(
        (accepted[0] / "snapshot-manifest.json").read_bytes()
    )
    assert stored.validation_state is ManchesterValidationState.ACCEPTED
    assert stored.attribution_text == TFGM_SIGNALS_ATTRIBUTION
    assert stored.licence_id == TFGM_LICENCE_ID
    assert stored.publication_class is ManchesterPublicationClass.PRIVATE
    assert stored.synthetic is True


def test_pdf_year_attribution_is_a_typed_refusal(tmp_path: Path) -> None:
    payload = build_zip(
        {
            "CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001")]),
            "TFGM_OGL.txt": PDF_ATTRIBUTION_2025.encode("utf-8"),
        }
    )
    with pytest.raises(TfgmAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(), payload)
    assert excinfo.value.code == "ATTRIBUTION_DRIFT"
    assert excinfo.value.quarantine_snapshot_id is not None
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


@pytest.mark.parametrize(
    ("label", "builder"),
    [
        (
            "traversal",
            lambda: build_zip(
                {"CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001")])},
                extra_infos=[(zipfile.ZipInfo("../evil.csv"), b"x")],
            ),
        ),
        (
            "absolute",
            lambda: build_zip(
                {"CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001")])},
                extra_infos=[(zipfile.ZipInfo("/abs.csv"), b"x")],
            ),
        ),
        (
            "duplicate",
            lambda: build_zip(
                {"TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8")},
                extra_infos=[
                    (zipfile.ZipInfo("CSV-format/TrafficSignals.csv"), b"a"),
                    (zipfile.ZipInfo("CSV-format/TrafficSignals.csv"), b"b"),
                ],
            ),
        ),
        (
            "nested-archive",
            lambda: build_zip(
                {
                    "CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001")]),
                    "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
                    "inner.zip": b"PK\x03\x04",
                }
            ),
        ),
        (
            "decompression-bomb",
            lambda: build_zip(
                {
                    "CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001")]),
                    "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
                    "big.bin": b"\x00" * 1_000_000,
                }
            ),
        ),
        (
            "symlink",
            lambda: build_zip(
                {
                    "CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001")]),
                    "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
                },
                extra_infos=[(_symlink_info("link.csv"), b"target")],
            ),
        ),
        (
            "missing-required-member",
            lambda: build_zip({"TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8")}),
        ),
    ],
)
@pytest.mark.filterwarnings("ignore:Duplicate name:UserWarning")
def test_unsafe_archives_are_refused_after_quarantine(
    tmp_path: Path, label: str, builder: Callable[[], bytes]
) -> None:
    with pytest.raises(TfgmAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(), builder())
    assert excinfo.value.code == "ARCHIVE_REJECTED", label
    assert excinfo.value.quarantine_snapshot_id is not None
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


def _symlink_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.external_attr = 0o120777 << 16
    return info


def test_executable_member_is_refused(tmp_path: Path) -> None:
    payload = build_zip(
        {
            "CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001")]),
            "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
            "tools/run.exe": b"MZ",
        }
    )
    with pytest.raises(TfgmAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(), payload)
    assert excinfo.value.code == "UNEXPECTED_MEMBER"
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


def test_malformed_csv_schema_drift_is_rejected(tmp_path: Path) -> None:
    bad_header = csv_bytes([signal_row("SYN001")]).replace(b"FRAS_ref", b"Fras")
    payload = build_zip(
        {
            "CSV-format/TrafficSignals.csv": bad_header,
            "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
        }
    )
    with pytest.raises(TfgmAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(), payload)
    assert excinfo.value.code == "PARSE_REJECTED"
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


def test_warning_admission_is_code_specific(tmp_path: Path) -> None:
    payload = build_zip(
        {
            "CSV-format/TrafficSignals.csv": csv_bytes(
                [signal_row("SYN001", krn=""), signal_row("SYN002", easting=383600)]
            ),
            "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
        }
    )
    for area in ("refuse", "wrong", "admit"):
        (tmp_path / area).mkdir()
    with pytest.raises(TfgmAcquisitionError) as refused:
        acquire(tmp_path / "refuse", make_request(), payload)
    assert refused.value.code == "WARNINGS_REFUSED"
    assert len(workspace_dirs(tmp_path / "refuse", "quarantine")) == 1
    assert not workspace_dirs(tmp_path / "refuse", "accepted")

    with pytest.raises(TfgmAcquisitionError) as wrong:
        acquire(
            tmp_path / "wrong",
            make_request(admitted_warning_codes=("COORDINATE_MISMATCH",)),
            payload,
        )
    assert wrong.value.code == "WARNINGS_REFUSED"

    result = acquire(
        tmp_path / "admit",
        make_request(admitted_warning_codes=("KRN_MISSING",)),
        payload,
    )
    assert result.parser_status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS


def test_failures_never_replace_accepted_and_repeat_is_refused(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    accepted = workspace_dirs(tmp_path, "accepted")[0]
    before = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    with pytest.raises(TfgmAcquisitionError) as transport_failure:
        acquire(tmp_path, make_request(), status=404)
    assert transport_failure.value.code == "TRANSPORT_FAILURE"
    with pytest.raises(ManchesterSnapshotError) as repeat:
        acquire(tmp_path, make_request())
    assert repeat.value.code == "DESTINATION_EXISTS"
    after = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    assert after == before
    assert result.snapshot_id == accepted.name


def test_offline_replay_is_deterministic_and_never_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = acquire(tmp_path, make_request())

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during replay")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    first = replay_tfgm_quarantine(tmp_path, result.snapshot_id, replay_request())
    second = replay_tfgm_quarantine(tmp_path, result.snapshot_id, replay_request())
    assert first.parser_report_fingerprint == result.parser_report_fingerprint
    assert first.fingerprint() == second.fingerprint()
    assert first.replayed_offline is True
    assert len(workspace_dirs(tmp_path, "accepted")) == 1


def test_replay_refuses_relabelling_and_mutation(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    with pytest.raises(TfgmAcquisitionError) as synthetic_mismatch:
        replay_tfgm_quarantine(
            tmp_path, result.snapshot_id, replay_request(expected_synthetic=False)
        )
    assert synthetic_mismatch.value.code == "SYNTHETIC_MISMATCH"

    quarantine = workspace_dirs(tmp_path, "quarantine")[0]
    member = quarantine / "raw" / "archive" / "traffic-signals.zip"
    member.chmod(0o644)
    member.write_bytes(b"PK\x03\x04tampered")
    with pytest.raises(ManchesterSnapshotError):
        replay_tfgm_quarantine(tmp_path, result.snapshot_id, replay_request())


def test_replay_refuses_foreign_source_and_publication_class(tmp_path: Path) -> None:
    payload = build_zip()
    member = ManchesterRawMember(
        relative_path=TFGM_ZIP_MEMBER_PATH,
        byte_size=len(payload),
        media_type="application/x-zip-compressed",
        sha256=sha256_hex(payload),
    )
    started = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)
    raw_fingerprint = build_raw_fingerprint([member])

    def manifest(
        source_id: str,
        publication: ManchesterPublicationClass,
        *,
        redacted_parameter_names: tuple[str, ...] = (),
    ) -> ManchesterQuarantineManifest:
        return ManchesterQuarantineManifest(
            snapshot_id=build_snapshot_id(source_id, started, raw_fingerprint),
            source=ManchesterSourceIdentity(
                source_id=source_id,
                source_name="Synthetic relabelling fixture",
                adapter_version=TFGM_ACQUISITION_METHOD_VERSION,
                source_schema_version=TFGM_ACQUISITION_SCHEMA_VERSION,
                freshness_policy_version=TFGM_FRESHNESS_POLICY_VERSION,
            ),
            request=ManchesterRequestIdentity(
                host="odata.tfgm.com",
                path=TFGM_ZIP_PATH,
                redacted_parameter_names=redacted_parameter_names,
            ),
            retrieval=ManchesterRetrievalWindow(started_at_utc=started, completed_at_utc=started),
            http=None,
            members=(member,),
            member_count=1,
            total_bytes=len(payload),
            raw_fingerprint=raw_fingerprint,
            publication_class=publication,
            licence_id=TFGM_LICENCE_ID,
            attribution_text=TFGM_SIGNALS_ATTRIBUTION,
            access_date=date(2026, 7, 22),
            synthetic=True,
        )

    foreign = manifest("some_other_source", ManchesterPublicationClass.PRIVATE)
    publish_manchester_quarantine(tmp_path, foreign, {TFGM_ZIP_MEMBER_PATH: payload}, POLICY)
    with pytest.raises(TfgmAcquisitionError) as product_mismatch:
        replay_tfgm_quarantine(tmp_path, foreign.snapshot_id, replay_request())
    assert product_mismatch.value.code == "PRODUCT_MISMATCH"

    relabelled = manifest("tfgm_traffic_signals", ManchesterPublicationClass.REDISTRIBUTABLE_RAW)
    publish_manchester_quarantine(tmp_path, relabelled, {TFGM_ZIP_MEMBER_PATH: payload}, POLICY)
    with pytest.raises(TfgmAcquisitionError) as contract_mismatch:
        replay_tfgm_quarantine(tmp_path, relabelled.snapshot_id, replay_request())
    assert contract_mismatch.value.code == "SOURCE_CONTRACT_MISMATCH"

    redacted_workspace = tmp_path / "redacted-request"
    redacted_workspace.mkdir()
    redacted = manifest(
        "tfgm_traffic_signals",
        ManchesterPublicationClass.PRIVATE,
        redacted_parameter_names=("token",),
    )
    publish_manchester_quarantine(
        redacted_workspace, redacted, {TFGM_ZIP_MEMBER_PATH: payload}, POLICY
    )
    with pytest.raises(TfgmAcquisitionError) as redacted_mismatch:
        replay_tfgm_quarantine(redacted_workspace, redacted.snapshot_id, replay_request())
    assert redacted_mismatch.value.code == "SOURCE_CONTRACT_MISMATCH"


def test_real_request_requires_the_audited_release(tmp_path: Path) -> None:
    with pytest.raises(TfgmAcquisitionError) as excinfo:
        acquire(tmp_path, make_request(synthetic=False))
    assert excinfo.value.code == "OFFICIAL_ARCHIVE_IDENTITY_MISMATCH"
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


def _mutated(result: TfgmAcquisitionResult, field_name: str, value: object) -> str:
    payload = json.loads(result.canonical_json())
    payload[field_name] = value
    return json.dumps(payload)


def test_receipts_fail_closed_on_mutation(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    replayed = replay_tfgm_quarantine(tmp_path, result.snapshot_id, replay_request())
    other_snapshot_id_suffix = "tfgm_traffic_signals-20260722T100000Z-" + "0" * 12
    mutations: list[tuple[str, object]] = [
        ("parser_status", "rejected"),
        ("synthetic", False),
        ("zip_sha256", "0" * 64),
        ("records_accepted", result.rows_seen + 1),
        ("attribution_text", PDF_ATTRIBUTION_2025),
        ("endpoint_path", "/opendata/downloads/Other/Other.zip"),
        ("dataset_version", "feb-2026-release"),
        ("source_id", "webtris_site"),
        ("publication_class", "redistributable_raw"),
        ("snapshot_id", other_snapshot_id_suffix),
        ("snapshot_id", "dft_raw_counts-20260722T100000Z-" + result.raw_fingerprint[:12]),
        ("csv_sha256", "1" * 64),
        ("quarantine_receipt_fingerprint", "2" * 64),
        ("snapshot_receipt_fingerprint", "3" * 64),
        ("rows_seen", result.rows_seen + 4),
        ("records_accepted", result.records_accepted + 4),
        ("rows_malformed", 1),
        ("parser_warning_codes", ["KRN_MISSING"]),
        ("zip_inventory_fingerprint", "4" * 64),
    ]
    for field_name, value in mutations:
        with pytest.raises(ValidationError):
            TfgmAcquisitionResult.model_validate_json(_mutated(result, field_name, value))

    inconsistent_pair = json.loads(result.canonical_json())
    inconsistent_pair["rows_seen"] = 9
    inconsistent_pair["records_accepted"] = 5
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(inconsistent_pair))

    zip_member_mutation = json.loads(result.canonical_json())
    for entry in zip_member_mutation["zip_members"]:
        if entry["path"] == "CSV-format/TrafficSignals.csv":
            entry["decompressed_bytes"] = entry["decompressed_bytes"] + 1
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(zip_member_mutation))

    csv_evidence_mutation = json.loads(result.canonical_json())
    csv_evidence_mutation["csv_member"]["sha256"] = "5" * 64
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(csv_evidence_mutation))

    attribution_evidence_mutation = json.loads(result.canonical_json())
    attribution_evidence_mutation["attribution_member"]["sha256"] = "8" * 64
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(attribution_evidence_mutation))

    compression_ratio_mutation = json.loads(result.canonical_json())
    compression_ratio_mutation["zip_members"][0]["compression_ratio"] += 1.0
    mutated_members = tuple(
        ArchiveMember.model_validate(entry) for entry in compression_ratio_mutation["zip_members"]
    )
    selected_members = (
        TfgmSelectedMemberEvidence.model_validate(compression_ratio_mutation["csv_member"]),
        TfgmSelectedMemberEvidence.model_validate(compression_ratio_mutation["attribution_member"]),
    )
    compression_ratio_mutation["zip_inventory_fingerprint"] = build_zip_inventory_fingerprint(
        mutated_members, selected_members
    )
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(compression_ratio_mutation))

    embedded_receipt_mutation = json.loads(result.canonical_json())
    embedded_receipt_mutation["quarantine_receipt"]["snapshot_id"] = other_snapshot_id_suffix
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(embedded_receipt_mutation))

    replay_payload = json.loads(replayed.canonical_json())
    replay_payload["synthetic"] = False
    with pytest.raises(ValidationError):
        TfgmReplayResult.model_validate_json(json.dumps(replay_payload))
    replay_receipt_payload = json.loads(replayed.canonical_json())
    replay_receipt_payload["quarantine_receipt_fingerprint"] = "6" * 64
    with pytest.raises(ValidationError):
        TfgmReplayResult.model_validate_json(json.dumps(replay_receipt_payload))


def test_warning_admission_binds_the_persisted_request(tmp_path: Path) -> None:
    payload = build_zip(
        {
            "CSV-format/TrafficSignals.csv": csv_bytes([signal_row("SYN001", krn="")]),
            "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
        }
    )
    result = acquire(tmp_path, make_request(admitted_warning_codes=("KRN_MISSING",)), payload)
    assert result.parser_warning_codes == ("KRN_MISSING",)

    shrunk = json.loads(result.canonical_json())
    shrunk["request"]["admitted_warning_codes"] = []
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(shrunk))

    swapped = json.loads(result.canonical_json())
    swapped["request"]["admitted_warning_codes"] = ["COORDINATE_MISMATCH"]
    with pytest.raises(ValidationError):
        TfgmAcquisitionResult.model_validate_json(json.dumps(swapped))


def test_parser_fingerprint_is_verified_by_replay_not_by_the_receipt_alone(
    tmp_path: Path,
) -> None:
    result = acquire(tmp_path, make_request())
    forged = TfgmAcquisitionResult.model_validate_json(
        _mutated(result, "parser_report_fingerprint", "7" * 64)
    )
    assert forged.parser_report_fingerprint == "7" * 64
    replayed = replay_tfgm_quarantine(tmp_path, result.snapshot_id, replay_request())
    assert replayed.parser_report_fingerprint == result.parser_report_fingerprint
    assert replayed.parser_report_fingerprint != forged.parser_report_fingerprint


def test_rejected_quarantine_replay_raises_typed_error(tmp_path: Path) -> None:
    bad_header = csv_bytes([signal_row("SYN001")]).replace(b"FRAS_ref", b"Fras")
    payload = build_zip(
        {
            "CSV-format/TrafficSignals.csv": bad_header,
            "TFGM_OGL.txt": TFGM_SIGNALS_ATTRIBUTION.encode("utf-8"),
        }
    )
    with pytest.raises(TfgmAcquisitionError) as acquisition_error:
        acquire(tmp_path, make_request(), payload)
    assert acquisition_error.value.code == "PARSE_REJECTED"
    snapshot_id = acquisition_error.value.quarantine_snapshot_id
    assert snapshot_id is not None

    with pytest.raises(TfgmAcquisitionError) as replay_error:
        replay_tfgm_quarantine(tmp_path, snapshot_id, replay_request())
    assert replay_error.value.code == "PARSE_REJECTED"
    assert replay_error.value.quarantine_snapshot_id == snapshot_id


def test_infrastructure_only_semantics_are_structural(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    result_fields = set(TfgmAcquisitionResult.model_fields)
    assert result_fields.isdisjoint(
        {"observed_at_utc", "freshness", "live", "near_live", "signal_phase", "queue"}
    )
    replayed = replay_tfgm_quarantine(tmp_path, result.snapshot_id, replay_request())
    assert replayed.parser_status is ManchesterValidationState.ACCEPTED

    from traffictwin.integration.manchester.tfgm_signals import TfgmSignalLocation

    location_fields = TfgmSignalLocation.model_fields
    for name in (
        "live_state_available",
        "phase_available",
        "timing_available",
        "queue_available",
        "traffic_count_available",
        "incident_available",
    ):
        assert location_fields[name].default is False
    assert location_fields["evidence_status"].default == "static_reference"
