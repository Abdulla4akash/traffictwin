"""Offline unit tests for the controlled WebTRIS acquisition workflow.

All transports are injected fakes (httpx.MockTransport); no test touches the
network. Synthetic payloads are labelled synthetic; the retained official
fixtures are used read-only for the replay-validation path.
"""

from __future__ import annotations

import base64
import json
import socket
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

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
from traffictwin.integration.manchester.webtris_acquisition import (
    WEBTRIS_ACQUISITION_METHOD_VERSION,
    WEBTRIS_ACQUISITION_SCHEMA_VERSION,
    WEBTRIS_ATTRIBUTION_TEXT,
    WEBTRIS_FRESHNESS_POLICY_VERSION,
    WEBTRIS_LICENCE_ID,
    WEBTRIS_LICENCE_URI,
    WebtrisAcquisitionError,
    WebtrisAcquisitionRequest,
    WebtrisAcquisitionResult,
    WebtrisProduct,
    WebtrisReplayRequest,
    WebtrisReplayResult,
    acquire_webtris_snapshot,
    replay_webtris_quarantine,
)

FIXTURE_DIR = Path("tests/fixtures/manchester/webtris")
FIXTURE_HASHES = {
    "site-34.json.b64": "f88cfc3442beb93a3e78b342891d8533566f50d6345a869152ee5aa1585488f7",
    "daily-site-34-20260301.json.b64": (
        "0a4d9f35f65c5f579102e23e4cc19525984701e610a56bb51196723941f550b5"
    ),
    "quality-site-34-20260301.json.b64": (
        "0c64204d9a32b3ae21aee61667103ee8d46e6fc5f2ba421fb0332ae1c0906654"
    ),
}
POLICY = ManchesterSnapshotPolicy(
    max_member_count=16, max_member_bytes=1_000_000, max_total_bytes=4_000_000
)
SITE_ID = "34"
SITE_NAME = "SYN M56 synthetic site"
REPORT_DATE = date(2026, 3, 1)
REQUEST_DATE = "01032026"


def make_clock() -> Callable[[], datetime]:
    counter = iter(range(10_000))

    def clock() -> datetime:
        return datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=next(counter))

    return clock


def site_payload() -> bytes:
    return json.dumps(
        {
            "row_count": 1,
            "sites": [
                {
                    "Id": SITE_ID,
                    "Name": "Synthetic MIDAS site fixture",
                    "Description": "SYN/0001A",
                    "Longitude": -2.3,
                    "Latitude": 53.35,
                    "Status": "Active",
                }
            ],
        }
    ).encode("utf-8")


def daily_row(interval: int, *, missing: bool = False) -> dict[str, str]:
    total_minutes = interval * 15 + 14
    ending = f"{total_minutes // 60:02d}:{total_minutes % 60:02d}:59"
    row = {
        "Site Name": SITE_NAME,
        "Report Date": "2026-03-01T00:00:00",
        "Time Period Ending": ending,
        "Time Interval": str(interval),
    }
    length_values = ["1", "0", "0", "0"]
    speed_values = ["1"] + ["0"] * 13
    length_names = ("0 - 520 cm", "521 - 660 cm", "661 - 1160 cm", "1160+ cm")
    speed_names = (
        "0 - 10 mph",
        "11 - 15 mph",
        "16 - 20 mph",
        "21 - 25 mph",
        "26 - 30 mph",
        "31 - 35 mph",
        "36 - 40 mph",
        "41 - 45 mph",
        "46 - 50 mph",
        "51 - 55 mph",
        "56 - 60 mph",
        "61 - 70 mph",
        "71 - 80 mph",
        "80+ mph",
    )
    for name, value in zip(length_names, length_values, strict=True):
        row[name] = "" if missing else value
    for name, value in zip(speed_names, speed_values, strict=True):
        row[name] = "" if missing else value
    row["Avg mph"] = "" if missing else "50.2"
    row["Total Volume"] = "" if missing else "1"
    return row


def daily_payload(
    rows: list[dict[str, str]],
    *,
    row_count: int = 96,
    request_date: str = REQUEST_DATE,
    **extra: object,
) -> bytes:
    body: dict[str, object] = {
        "Header": {
            "row_count": row_count,
            "start_date": request_date,
            "end_date": request_date,
            "links": [],
        },
        "Rows": rows,
    }
    body.update(extra)
    return json.dumps(body).encode("utf-8")


def full_day_rows(missing_intervals: set[int] | None = None) -> list[dict[str, str]]:
    missing = missing_intervals or set()
    return [daily_row(index, missing=index in missing) for index in range(96)]


def quality_payload() -> bytes:
    return json.dumps(
        {"row_count": 1, "Qualities": [{"Date": "2026-03-01T00:00:00", "Quality": 89}]}
    ).encode("utf-8")


def paged(rows: list[dict[str, str]], page_size: int) -> dict[int, bytes]:
    return {
        page: daily_payload(rows[(page - 1) * page_size : page * page_size])
        for page in range(1, -(-len(rows) // page_size) + 1)
    }


def make_transport(
    responses: dict[str, dict[int, bytes] | bytes],
    calls: list[tuple[str, str, dict[str, str]]],
    fail_page: int | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append((request.url.host, request.url.path, params))
        path = request.url.path
        if path.startswith("/api/v1.0/sites/"):
            payload = responses["site"]
        elif path == "/api/v1.0/quality/daily":
            payload = responses["quality"]
        else:
            pages = responses["daily"]
            assert isinstance(pages, dict)
            page = int(params.get("page", "1"))
            if fail_page is not None and page == fail_page:
                return httpx.Response(404)
            payload = pages[page]
        assert isinstance(payload, bytes)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(payload),
        )

    return httpx.MockTransport(handler)


def make_request(
    product: WebtrisProduct = "daily_report", **overrides: object
) -> WebtrisAcquisitionRequest:
    values: dict[str, object] = {
        "product": product,
        "site_id": SITE_ID,
        "max_pages": 10,
        "policy": POLICY,
        "publication_class": ManchesterPublicationClass.PRIVATE,
        "synthetic": True,
    }
    if product != "site":
        values["site_name"] = SITE_NAME
        values["report_date"] = REPORT_DATE
    if product == "daily_report":
        values["page_size"] = 96
    values.update(overrides)
    return WebtrisAcquisitionRequest.model_validate(values)


def default_responses() -> dict[str, dict[int, bytes] | bytes]:
    return {
        "site": site_payload(),
        "daily": {1: daily_payload(full_day_rows())},
        "quality": quality_payload(),
    }


def acquire(
    workspace: Path,
    request: WebtrisAcquisitionRequest,
    responses: dict[str, dict[int, bytes] | bytes] | None = None,
    calls: list[tuple[str, str, dict[str, str]]] | None = None,
    fail_page: int | None = None,
) -> WebtrisAcquisitionResult:
    recorded = calls if calls is not None else []
    with httpx.Client(
        transport=make_transport(responses or default_responses(), recorded, fail_page)
    ) as raw_client:
        return acquire_webtris_snapshot(
            workspace, request, http_client=raw_client, utc_now=make_clock()
        )


def workspace_dirs(workspace: Path, area: str) -> list[Path]:
    root = workspace / area
    if not root.is_dir():
        return []
    return [p for p in root.iterdir() if p.is_dir()]


@pytest.mark.parametrize(
    ("product", "path", "params"),
    [
        ("site", "/api/v1.0/sites/34", {}),
        (
            "daily_report",
            "/api/v1.0/reports/daily",
            {
                "sites": "34",
                "start_date": REQUEST_DATE,
                "end_date": REQUEST_DATE,
                "page": "1",
                "page_size": "96",
            },
        ),
        (
            "daily_quality",
            "/api/v1.0/quality/daily",
            {"siteId": "34", "start_date": REQUEST_DATE, "end_date": REQUEST_DATE},
        ),
    ],
)
def test_exact_allowlisted_request_per_product(
    tmp_path: Path, product: WebtrisProduct, path: str, params: dict[str, str]
) -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []
    result = acquire(tmp_path, make_request(product), calls=calls)
    assert calls == [("webtris.nationalhighways.co.uk", path, params)]
    assert result.endpoint_path == path
    assert result.parser_status is not ManchesterValidationState.REJECTED


def test_host_path_query_and_date_injection_is_refused() -> None:
    for injected in (
        {"host": "evil.invalid"},
        {"path": "/api/v1.0/other"},
        {"url": "https://evil.invalid/api/v1.0/reports/daily"},
        {"query": {"sites": "34"}},
        {"report_date": "01032026"},
        {"site_id": "34; DROP"},
    ):
        with pytest.raises(ValidationError):
            make_request(**injected)
    field_names = set(WebtrisAcquisitionRequest.model_fields)
    assert field_names.isdisjoint({"host", "path", "url", "query", "endpoint"})
    assert "accept_with_warnings" not in field_names
    with pytest.raises(ValidationError):
        make_request("site", report_date=REPORT_DATE, site_name=None)
    with pytest.raises(ValidationError):
        make_request("daily_quality", page_size=1)


def test_deterministic_pagination_and_stable_receipts(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": paged(full_day_rows(), 48),
        "quality": quality_payload(),
    }
    calls: list[tuple[str, str, dict[str, str]]] = []
    request = make_request(page_size=48)
    first = acquire(tmp_path / "a", request, responses, calls)
    assert [call[2]["page"] for call in calls] == ["1", "2"]
    second = acquire(tmp_path / "b", request, responses)
    assert first.fingerprint() == second.fingerprint()
    assert [m.relative_path for m in first.members] == [
        "pages/page-0001.json",
        "pages/page-0002.json",
    ]


def test_all_pages_are_quarantined_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import traffictwin.integration.manchester.webtris_acquisition as module
    from traffictwin.integration.manchester.webtris import parse_webtris_daily_report as original

    observed: dict[str, object] = {}

    def spying_parse(members: object, scope: object) -> object:
        quarantine_dirs = workspace_dirs(tmp_path, "quarantine")
        assert len(quarantine_dirs) == 1
        raw_pages = quarantine_dirs[0] / "raw" / "pages"
        observed["pages"] = sorted(p.name for p in raw_pages.iterdir())
        observed["manifest"] = (quarantine_dirs[0] / "quarantine-manifest.json").is_file()
        return original(members, scope)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "parse_webtris_daily_report", spying_parse)
    responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": paged(full_day_rows(), 48),
        "quality": quality_payload(),
    }
    acquire(tmp_path, make_request(page_size=48), responses)
    assert observed["pages"] == ["page-0001.json", "page-0002.json"]
    assert observed["manifest"] is True


def test_successful_promotion_and_boundary_labels(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    accepted = workspace_dirs(tmp_path, "accepted")
    assert len(accepted) == 1
    receipt = verify_manchester_snapshot(accepted[0])
    assert receipt.fingerprint() == result.snapshot_receipt_fingerprint
    stored = ManchesterSnapshotManifest.model_validate_json(
        (accepted[0] / "snapshot-manifest.json").read_bytes()
    )
    assert stored.validation_state is ManchesterValidationState.ACCEPTED
    assert stored.licence_id == WEBTRIS_LICENCE_ID
    assert stored.attribution_text == WEBTRIS_ATTRIBUTION_TEXT
    assert WEBTRIS_LICENCE_URI in stored.attribution_text
    assert stored.synthetic is True
    result_fields = set(WebtrisAcquisitionResult.model_fields)
    assert result_fields.isdisjoint({"observed_at_utc", "freshness", "live", "near_live"})
    assert result.records_accepted == 96


def test_result_models_bind_product_request_inventory_and_evidence_class(
    tmp_path: Path,
) -> None:
    result = acquire(tmp_path, make_request())

    mutations: tuple[tuple[str, object], ...] = (
        ("product", "site"),
        ("source_id", "webtris_site"),
        ("synthetic", False),
        ("pages", 2),
        ("raw_fingerprint", "0" * 64),
    )
    for field, value in mutations:
        payload = result.model_dump(mode="python")
        payload[field] = value
        with pytest.raises(ValidationError):
            WebtrisAcquisitionResult.model_validate(payload)


def test_warning_admission_is_code_specific(tmp_path: Path) -> None:
    responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": {1: daily_payload(full_day_rows(missing_intervals={7}))},
        "quality": quality_payload(),
    }
    for area in ("refuse", "wrong-code", "admit"):
        (tmp_path / area).mkdir()

    with pytest.raises(WebtrisAcquisitionError) as refused:
        acquire(tmp_path / "refuse", make_request(), responses)
    assert refused.value.code == "WARNINGS_REFUSED"
    assert refused.value.quarantine_snapshot_id is not None
    assert len(workspace_dirs(tmp_path / "refuse", "quarantine")) == 1
    assert not workspace_dirs(tmp_path / "refuse", "accepted")

    with pytest.raises(WebtrisAcquisitionError) as wrong_code:
        acquire(
            tmp_path / "wrong-code",
            make_request(admitted_warning_codes=("LENGTH_TOTAL_MISMATCH",)),
            responses,
        )
    assert wrong_code.value.code == "WARNINGS_REFUSED"

    result = acquire(
        tmp_path / "admit",
        make_request(admitted_warning_codes=("MISSING_INTERVAL_MEASUREMENTS",)),
        responses,
    )
    assert result.parser_status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert result.intervals_missing == 1
    stored = ManchesterSnapshotManifest.model_validate_json(
        (workspace_dirs(tmp_path / "admit", "accepted")[0] / "snapshot-manifest.json").read_bytes()
    )
    assert any(f.code == "MISSING_INTERVAL_MEASUREMENTS" for f in stored.findings)


def test_page_and_byte_bounds_are_enforced(tmp_path: Path) -> None:
    for area in ("pages", "bytes"):
        (tmp_path / area).mkdir()
    responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": paged(full_day_rows(), 1),
        "quality": quality_payload(),
    }
    with pytest.raises(WebtrisAcquisitionError) as pages_exceeded:
        acquire(tmp_path / "pages", make_request(page_size=1, max_pages=3), responses)
    assert pages_exceeded.value.code == "PAGE_LIMIT_EXCEEDED"

    tight = ManchesterSnapshotPolicy(
        max_member_count=16, max_member_bytes=30_000, max_total_bytes=30_000
    )
    two_pages: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": paged(full_day_rows(), 48),
        "quality": quality_payload(),
    }
    with pytest.raises(WebtrisAcquisitionError) as bytes_exceeded:
        acquire(tmp_path / "bytes", make_request(page_size=48, policy=tight), two_pages)
    assert bytes_exceeded.value.code == "TOTAL_BYTES_EXCEEDED"
    for area in ("pages", "bytes"):
        assert not workspace_dirs(tmp_path / area, "quarantine")
        assert not workspace_dirs(tmp_path / area, "accepted")


def test_transport_failure_is_typed_and_preserves_accepted(tmp_path: Path) -> None:
    responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": paged(full_day_rows(), 48),
        "quality": quality_payload(),
    }
    request = make_request(page_size=48)
    acquire(tmp_path, request, responses)
    accepted = workspace_dirs(tmp_path, "accepted")[0]
    before = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    with pytest.raises(WebtrisAcquisitionError) as excinfo:
        acquire(tmp_path, request, responses, fail_page=2)
    assert excinfo.value.code == "TRANSPORT_FAILURE"
    assert "never zero traffic" in str(excinfo.value)
    after = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    assert after == before


def test_malformed_json_drift_and_schema_drift(tmp_path: Path) -> None:
    for area in ("m", "d", "s"):
        (tmp_path / area).mkdir()
    with pytest.raises(WebtrisAcquisitionError) as malformed:
        acquire(
            tmp_path / "m",
            make_request(),
            {"site": site_payload(), "daily": {1: b"\x00not-json"}, "quality": quality_payload()},
        )
    assert malformed.value.code == "PAGINATION_PEEK_FAILED"

    rows = full_day_rows()
    drifting: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": {
            1: daily_payload(rows[:48]),
            2: daily_payload(rows[48:], row_count=97),
        },
        "quality": quality_payload(),
    }
    with pytest.raises(WebtrisAcquisitionError) as drift:
        acquire(tmp_path / "d", make_request(page_size=48), drifting)
    assert drift.value.code == "PAGINATION_DRIFT"
    for area in ("m", "d"):
        assert not workspace_dirs(tmp_path / area, "quarantine")

    schema_drift: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": {1: daily_payload(full_day_rows(), unexpected_key=1)},
        "quality": quality_payload(),
    }
    with pytest.raises(WebtrisAcquisitionError) as rejected:
        acquire(tmp_path / "s", make_request(), schema_drift)
    assert rejected.value.code == "PARSE_REJECTED"
    assert len(workspace_dirs(tmp_path / "s", "quarantine")) == 1
    assert not workspace_dirs(tmp_path / "s", "accepted")


def test_hash_mutation_and_repeat_publication(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    quarantine = workspace_dirs(tmp_path, "quarantine")[0]
    member = quarantine / "raw" / "pages" / "page-0001.json"
    member.chmod(0o644)
    member.write_bytes(b'{"tampered": true}')
    with pytest.raises(ManchesterSnapshotError):
        replay_webtris_quarantine(
            tmp_path,
            result.snapshot_id,
            WebtrisReplayRequest(
                product="daily_report",
                site_id=SITE_ID,
                site_name=SITE_NAME,
                report_date=REPORT_DATE,
                page_size=96,
            ),
        )
    member.chmod(0o644)
    member.write_bytes(b"")
    with pytest.raises(ManchesterSnapshotError) as repeat:
        acquire(tmp_path, make_request())
    assert repeat.value.code == "DESTINATION_EXISTS"


def test_replay_binding_refuses_relabelling(tmp_path: Path) -> None:
    result = acquire(tmp_path, make_request())
    snapshot_id: str = result.snapshot_id

    as_quality = WebtrisReplayRequest(
        product="daily_quality",
        site_id=SITE_ID,
        site_name=SITE_NAME,
        report_date=REPORT_DATE,
    )
    with pytest.raises(WebtrisAcquisitionError) as product_mismatch:
        replay_webtris_quarantine(tmp_path, snapshot_id, as_quality)
    assert product_mismatch.value.code == "PRODUCT_MISMATCH"

    wrong_date = WebtrisReplayRequest(
        product="daily_report",
        site_id=SITE_ID,
        site_name=SITE_NAME,
        report_date=date(2026, 3, 2),
        page_size=96,
    )
    with pytest.raises(WebtrisAcquisitionError) as date_mismatch:
        replay_webtris_quarantine(tmp_path, snapshot_id, wrong_date)
    assert date_mismatch.value.code == "SCOPE_MISMATCH"

    wrong_site = WebtrisReplayRequest(
        product="daily_report",
        site_id="35",
        site_name=SITE_NAME,
        report_date=REPORT_DATE,
        page_size=96,
    )
    with pytest.raises(WebtrisAcquisitionError) as site_mismatch:
        replay_webtris_quarantine(tmp_path, snapshot_id, wrong_site)
    assert site_mismatch.value.code == "SCOPE_MISMATCH"

    wrong_synthetic = WebtrisReplayRequest(
        product="daily_report",
        site_id=SITE_ID,
        site_name=SITE_NAME,
        report_date=REPORT_DATE,
        page_size=96,
        expected_synthetic=False,
    )
    with pytest.raises(WebtrisAcquisitionError) as synthetic_mismatch:
        replay_webtris_quarantine(tmp_path, snapshot_id, wrong_synthetic)
    assert synthetic_mismatch.value.code == "SYNTHETIC_MISMATCH"


def test_replay_refuses_broken_page_inventory(tmp_path: Path) -> None:
    started = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)
    rows = full_day_rows()
    payloads = {
        "pages/page-0001.json": daily_payload(rows[:48]),
        "pages/page-0003.json": daily_payload(rows[48:]),
    }
    members = tuple(
        ManchesterRawMember(
            relative_path=path,
            byte_size=len(payload),
            media_type="application/json",
            sha256=sha256_hex(payload),
        )
        for path, payload in sorted(payloads.items())
    )
    raw_fingerprint = build_raw_fingerprint(members)
    manifest = ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id("webtris_daily_report", started, raw_fingerprint),
        source=ManchesterSourceIdentity(
            source_id="webtris_daily_report",
            source_name="Synthetic broken-inventory fixture",
            adapter_version=WEBTRIS_ACQUISITION_METHOD_VERSION,
            source_schema_version=WEBTRIS_ACQUISITION_SCHEMA_VERSION,
            freshness_policy_version=WEBTRIS_FRESHNESS_POLICY_VERSION,
        ),
        request=ManchesterRequestIdentity(
            host="webtris.nationalhighways.co.uk",
            path="/api/v1.0/reports/daily",
            parameters=(
                ("end_date", REQUEST_DATE),
                ("page", "1"),
                ("page_size", "48"),
                ("sites", SITE_ID),
                ("start_date", REQUEST_DATE),
            ),
        ),
        retrieval=ManchesterRetrievalWindow(started_at_utc=started, completed_at_utc=started),
        http=None,
        members=members,
        member_count=len(members),
        total_bytes=sum(member.byte_size for member in members),
        raw_fingerprint=raw_fingerprint,
        publication_class=ManchesterPublicationClass.PRIVATE,
        licence_id=WEBTRIS_LICENCE_ID,
        attribution_text=WEBTRIS_ATTRIBUTION_TEXT,
        access_date=date(2026, 7, 22),
        synthetic=True,
    )
    publish_manchester_quarantine(tmp_path, manifest, payloads, POLICY)
    with pytest.raises(WebtrisAcquisitionError) as excinfo:
        replay_webtris_quarantine(
            tmp_path,
            manifest.snapshot_id,
            WebtrisReplayRequest(
                product="daily_report",
                site_id=SITE_ID,
                site_name=SITE_NAME,
                report_date=REPORT_DATE,
                page_size=48,
            ),
        )
    assert excinfo.value.code == "SOURCE_CONTRACT_MISMATCH"


def test_webtris_boundaries_are_preserved(tmp_path: Path) -> None:
    responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": {1: daily_payload(full_day_rows(missing_intervals={3}))},
        "quality": quality_payload(),
    }
    result = acquire(
        tmp_path,
        make_request(admitted_warning_codes=("MISSING_INTERVAL_MEASUREMENTS",)),
        responses,
    )
    replayed = replay_webtris_quarantine(
        tmp_path,
        result.snapshot_id,
        WebtrisReplayRequest(
            product="daily_report",
            site_id=SITE_ID,
            site_name=SITE_NAME,
            report_date=REPORT_DATE,
            page_size=96,
        ),
    )
    assert replayed.intervals_missing == 1

    (tmp_path / "q").mkdir()
    quality_result = acquire(tmp_path / "q", make_request("daily_quality"))
    assert quality_result.records_accepted == 1


def test_replay_is_offline_and_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = acquire(tmp_path, make_request())

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during replay")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    replay_request = WebtrisReplayRequest(
        product="daily_report",
        site_id=SITE_ID,
        site_name=SITE_NAME,
        report_date=REPORT_DATE,
        page_size=96,
        expected_synthetic=True,
    )
    first = replay_webtris_quarantine(tmp_path, result.snapshot_id, replay_request)
    second = replay_webtris_quarantine(tmp_path, result.snapshot_id, replay_request)
    assert first.parser_report_fingerprint == result.parser_report_fingerprint
    assert first.fingerprint() == second.fingerprint()
    assert first.replayed_offline is True
    assert len(workspace_dirs(tmp_path, "accepted")) == 1

    for field, value in (
        ("product", "site"),
        ("source_id", "webtris_site"),
        ("endpoint_path", "/api/v1.0/sites/34"),
        ("synthetic", False),
    ):
        payload = first.model_dump(mode="python")
        payload[field] = value
        with pytest.raises(ValidationError):
            WebtrisReplayResult.model_validate(payload)


def _publish_fixture_quarantine(
    workspace: Path,
    source_id: str,
    member_path: str,
    request_path: str,
    parameters: tuple[tuple[str, str], ...],
    payload: bytes,
) -> str:
    started = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)
    member = ManchesterRawMember(
        relative_path=member_path,
        byte_size=len(payload),
        media_type="application/json",
        sha256=sha256_hex(payload),
    )
    raw_fingerprint = build_raw_fingerprint([member])
    manifest = ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id(source_id, started, raw_fingerprint),
        source=ManchesterSourceIdentity(
            source_id=source_id,
            source_name="National Highways WebTRIS official minimal fixture",
            adapter_version=WEBTRIS_ACQUISITION_METHOD_VERSION,
            source_schema_version=WEBTRIS_ACQUISITION_SCHEMA_VERSION,
            freshness_policy_version=WEBTRIS_FRESHNESS_POLICY_VERSION,
        ),
        request=ManchesterRequestIdentity(
            host="webtris.nationalhighways.co.uk",
            path=request_path,
            parameters=parameters,
        ),
        retrieval=ManchesterRetrievalWindow(started_at_utc=started, completed_at_utc=started),
        http=None,
        members=(member,),
        member_count=1,
        total_bytes=len(payload),
        raw_fingerprint=raw_fingerprint,
        publication_class=ManchesterPublicationClass.PRIVATE,
        licence_id=WEBTRIS_LICENCE_ID,
        attribution_text=WEBTRIS_ATTRIBUTION_TEXT,
        access_date=date(2026, 7, 22),
        synthetic=False,
    )
    publish_manchester_quarantine(workspace, manifest, {member_path: payload}, POLICY)
    return manifest.snapshot_id


def test_official_fixtures_replay_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during fixture replay")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    payloads = {}
    for name, digest in FIXTURE_HASHES.items():
        payload = base64.b64decode((FIXTURE_DIR / name).read_text())
        assert sha256_hex(payload) == digest
        payloads[name] = payload

    site_snapshot = _publish_fixture_quarantine(
        tmp_path,
        "webtris_site",
        "site/site.json",
        "/api/v1.0/sites/34",
        (),
        payloads["site-34.json.b64"],
    )
    site_replay = replay_webtris_quarantine(
        tmp_path,
        site_snapshot,
        WebtrisReplayRequest(product="site", site_id="34", expected_synthetic=False),
    )
    assert site_replay.parser_status is ManchesterValidationState.ACCEPTED
    assert site_replay.records_accepted == 1

    daily_snapshot = _publish_fixture_quarantine(
        tmp_path,
        "webtris_daily_report",
        "pages/page-0001.json",
        "/api/v1.0/reports/daily",
        (
            ("end_date", REQUEST_DATE),
            ("page", "1"),
            ("page_size", "96"),
            ("sites", "34"),
            ("start_date", REQUEST_DATE),
        ),
        payloads["daily-site-34-20260301.json.b64"],
    )
    daily_replay = replay_webtris_quarantine(
        tmp_path,
        daily_snapshot,
        WebtrisReplayRequest(
            product="daily_report",
            site_id="34",
            site_name="M56/8150A",
            report_date=REPORT_DATE,
            page_size=96,
            expected_synthetic=False,
        ),
    )
    assert daily_replay.parser_status is not ManchesterValidationState.REJECTED
    assert daily_replay.records_accepted == 96
    assert daily_replay.synthetic is False

    quality_snapshot = _publish_fixture_quarantine(
        tmp_path,
        "webtris_daily_quality",
        "quality/daily-quality.json",
        "/api/v1.0/quality/daily",
        (
            ("end_date", REQUEST_DATE),
            ("siteId", "34"),
            ("start_date", REQUEST_DATE),
        ),
        payloads["quality-site-34-20260301.json.b64"],
    )
    quality_replay = replay_webtris_quarantine(
        tmp_path,
        quality_snapshot,
        WebtrisReplayRequest(
            product="daily_quality",
            site_id="34",
            site_name="M56/8150A",
            report_date=REPORT_DATE,
            expected_synthetic=False,
        ),
    )
    assert quality_replay.parser_status is ManchesterValidationState.ACCEPTED
    assert quality_replay.records_accepted == 1
