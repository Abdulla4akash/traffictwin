"""Offline unit tests for the controlled DfT acquisition workflow.

All transports are injected fakes (httpx.MockTransport); no test touches the
network. Synthetic payloads are labelled synthetic; the three retained official
fixtures are used read-only for the replay-validation path.
"""

from __future__ import annotations

import base64
import json
import socket
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.dft import DftManchesterScope
from traffictwin.integration.manchester.dft_acquisition import (
    DFT_ATTRIBUTION_TEXT,
    DFT_LICENCE_ID,
    DftAcceptedSnapshotCatalogue,
    DftAcquisitionError,
    DftAcquisitionRequest,
    DftAcquisitionResult,
    DftDataset,
    acquire_dft_snapshot,
    catalogue_accepted_dft_snapshots,
    load_accepted_dft_report,
    open_accepted_dft_snapshot,
    replay_dft_quarantine,
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
from traffictwin.release.compatibility import initialise_v07_workspace

FIXTURE_DIR = Path("tests/fixtures/manchester/dft")
FIXTURE_HASHES = {
    "raw-count-43177.json.b64": "06869d2d3ff2606a719bd043bcf8f3e30ad7fca17df1084c12598912c4a56c22",
    "count-point-6046.json.b64": "525250e7df43cbd8738e841fccf1d3b1a2787c229f87c6dd7d00ca019c122635",
    "aadf-9219.json.b64": "d46e8c8fa29dbf72b3cd974a5dc6349fb8750e32e6758aad91b8b588cb4571a5",
}
POLICY = ManchesterSnapshotPolicy(
    max_member_count=16, max_member_bytes=1_000_000, max_total_bytes=4_000_000
)


def make_clock() -> Callable[[], datetime]:
    counter = iter(range(10_000))

    def clock() -> datetime:
        return datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=next(counter))

    return clock


def raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 1001,
        "count_point_id": 12345,
        "direction_of_travel": "N",
        "year": 2004,
        "count_date": "2004-05-21",
        "hour": 12,
        "region_id": 3,
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
        "region_id": 3,
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


def envelope_bytes(
    rows: list[dict[str, object]],
    current_page: int,
    last_page: int,
    per_page: int,
    total: int,
    **extra: object,
) -> bytes:
    body: dict[str, object] = {
        "current_page": current_page,
        "per_page": per_page,
        "total": total,
        "last_page": last_page,
        "from": 1 if rows else None,
        "to": len(rows) if rows else None,
        "path": "synthetic-fixture",
        "first_page_url": "synthetic-fixture",
        "last_page_url": "synthetic-fixture",
        "next_page_url": "synthetic-fixture" if current_page < last_page else None,
        "prev_page_url": None,
        "links": [],
        "data": rows,
    }
    body.update(extra)
    return json.dumps(body).encode("utf-8")


def two_page_raw_dataset() -> dict[int, bytes]:
    return {
        1: envelope_bytes([raw_row()], 1, 2, 1, 2),
        2: envelope_bytes([raw_row(id=1002, hour=13)], 2, 2, 1, 2),
    }


def make_transport(
    pages: dict[int, bytes],
    calls: list[tuple[str, str, dict[str, str]]],
    fail_page: int | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        calls.append((request.url.host, request.url.path, params))
        page = int(params.get("page[number]", "1"))
        if fail_page is not None and page == fail_page:
            return httpx.Response(404)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            stream=httpx.ByteStream(pages[page]),
        )

    return httpx.MockTransport(handler)


def make_request(dataset: DftDataset = "raw_counts", **overrides: object) -> DftAcquisitionRequest:
    values: dict[str, object] = {
        "dataset": dataset,
        "page_size": 1,
        "max_pages": 10,
        "max_rows": 1_000,
        "policy": POLICY,
        "publication_class": ManchesterPublicationClass.PRIVATE,
        "accept_with_warnings": False,
        "synthetic": True,
    }
    values.update(overrides)
    return DftAcquisitionRequest.model_validate(values)


def acquire(
    tmp_path: Path,
    pages: dict[int, bytes],
    request: DftAcquisitionRequest,
    calls: list[tuple[str, str, dict[str, str]]] | None = None,
    fail_page: int | None = None,
) -> DftAcquisitionResult:
    recorded = calls if calls is not None else []
    with httpx.Client(transport=make_transport(pages, recorded, fail_page)) as raw_client:
        return acquire_dft_snapshot(tmp_path, request, http_client=raw_client, utc_now=make_clock())


def workspace_dirs(tmp_path: Path, area: str) -> list[Path]:
    root = tmp_path / area
    if not root.is_dir():
        return []
    return [p for p in root.iterdir() if p.is_dir()]


@pytest.mark.parametrize(
    ("dataset", "path", "row"),
    [
        ("raw_counts", "/api/raw-counts", raw_row()),
        ("count_points", "/api/count-points", count_point_row()),
        ("aadf", "/api/average-annual-daily-flow", aadf_row()),
    ],
)
def test_exact_allowlisted_request_per_endpoint(
    tmp_path: Path, dataset: DftDataset, path: str, row: dict[str, object]
) -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []
    pages = {1: envelope_bytes([row], 1, 1, 1, 1)}
    result = acquire(tmp_path, pages, make_request(dataset), calls)
    assert calls == [
        (
            "roadtraffic.dft.gov.uk",
            path,
            {"filter[local_authority_id]": "85", "page[number]": "1", "page[size]": "1"},
        )
    ]
    assert result.endpoint_path == path
    assert result.records_accepted == 1


def test_manchester_identity_cannot_change() -> None:
    with pytest.raises(ValidationError):
        DftManchesterScope.model_validate({"local_authority_id": 86})
    with pytest.raises(ValidationError):
        DftManchesterScope.model_validate({"ons_code": "E08000001"})
    request = make_request()
    assert request.scope.local_authority_id == 85
    assert request.scope.ons_code == "E08000003"


def test_host_path_query_injection_is_refused() -> None:
    for injected in (
        {"host": "evil.invalid"},
        {"path": "/api/other"},
        {"url": "https://evil.invalid/api/raw-counts"},
        {"query": {"filter[region_id]": 3}},
    ):
        with pytest.raises(ValidationError):
            make_request(**injected)
    field_names = set(DftAcquisitionRequest.model_fields)
    assert field_names.isdisjoint({"host", "path", "url", "query", "endpoint"})
    with pytest.raises(ValidationError):
        make_request(dataset="count_points", year=2004)


def test_deterministic_pagination_and_stable_receipt(tmp_path: Path) -> None:
    calls: list[tuple[str, str, dict[str, str]]] = []
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = acquire(tmp_path / "a", two_page_raw_dataset(), make_request(), calls)
    assert [call[2]["page[number]"] for call in calls] == ["1", "2"]
    second = acquire(tmp_path / "b", two_page_raw_dataset(), make_request())
    assert first.fingerprint() == second.fingerprint()
    assert first.snapshot_id == second.snapshot_id
    assert [m.relative_path for m in first.members] == [
        "pages/page-0001.json",
        "pages/page-0002.json",
    ]


def test_result_contract_reconciles_dataset_members_and_request(tmp_path: Path) -> None:
    result = acquire(tmp_path, two_page_raw_dataset(), make_request())
    payload = result.model_dump(mode="python")
    payload["endpoint_path"] = "/api/average-annual-daily-flow"
    with pytest.raises(ValidationError, match="must match the selected DfT dataset"):
        DftAcquisitionResult.model_validate(payload)

    payload = result.model_dump(mode="python")
    payload["pages"] = 1
    with pytest.raises(ValidationError, match="page count must match"):
        DftAcquisitionResult.model_validate(payload)


def test_all_pages_are_quarantined_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import traffictwin.integration.manchester.dft_acquisition as module
    from traffictwin.integration.manchester.dft import parse_dft_raw_counts as original

    observed: dict[str, object] = {}

    def spying_parse(members: object, scope: DftManchesterScope) -> object:
        quarantine_dirs = workspace_dirs(tmp_path, "quarantine")
        assert len(quarantine_dirs) == 1
        raw_dir = quarantine_dirs[0] / "raw" / "pages"
        observed["quarantined_pages"] = sorted(p.name for p in raw_dir.iterdir())
        observed["manifest_present"] = (quarantine_dirs[0] / "quarantine-manifest.json").is_file()
        return original(members, scope)  # type: ignore[arg-type]

    monkeypatch.setattr(module, "parse_dft_raw_counts", spying_parse)
    acquire(tmp_path, two_page_raw_dataset(), make_request())
    assert observed["quarantined_pages"] == ["page-0001.json", "page-0002.json"]
    assert observed["manifest_present"] is True


def test_successful_promotion_publishes_accepted_snapshot(tmp_path: Path) -> None:
    result = acquire(tmp_path, two_page_raw_dataset(), make_request())
    accepted = workspace_dirs(tmp_path, "accepted")
    quarantined = workspace_dirs(tmp_path, "quarantine")
    assert len(accepted) == 1
    assert len(quarantined) == 1
    receipt = verify_manchester_snapshot(accepted[0])
    assert receipt.fingerprint() == result.snapshot_receipt_fingerprint
    stored = ManchesterSnapshotManifest.model_validate_json(
        (accepted[0] / "snapshot-manifest.json").read_bytes()
    )
    assert stored.validation_state is ManchesterValidationState.ACCEPTED
    assert stored.licence_id == DFT_LICENCE_ID
    assert stored.attribution_text == DFT_ATTRIBUTION_TEXT
    assert stored.synthetic is True


def test_accepted_report_replays_offline_from_exact_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    result = acquire(workspace, two_page_raw_dataset(), make_request())
    assert isinstance(result, DftAcquisitionResult)

    def refuse_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("accepted DfT replay must not use the network")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    report = load_accepted_dft_report(workspace, result)

    assert report.fingerprint() == result.parser_report_fingerprint
    assert report.counts.rows_seen == result.rows_seen
    assert report.counts.records_accepted == result.records_accepted
    assert report.status is result.parser_status


def test_accepted_report_refuses_request_drift_and_unmarked_workspace(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    result = acquire(workspace, two_page_raw_dataset(), make_request())
    assert isinstance(result, DftAcquisitionResult)
    drifted_request = result.request.model_copy(update={"page_size": 2})
    drifted = result.model_copy(update={"request": drifted_request})

    with pytest.raises(DftAcquisitionError) as mismatch:
        load_accepted_dft_report(workspace, drifted)
    assert mismatch.value.code == "ACCEPTED_SNAPSHOT_MISMATCH"
    assert mismatch.value.accepted_snapshot_id == result.snapshot_id
    assert mismatch.value.quarantine_snapshot_id is None

    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    with pytest.raises(DftAcquisitionError) as unmarked:
        load_accepted_dft_report(ordinary, result)
    assert unmarked.value.code == "WORKSPACE_INVALID"


def test_empty_and_three_product_accepted_catalogues_are_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    empty = catalogue_accepted_dft_snapshots(workspace)
    assert empty.snapshots == ()
    assert empty.counts.total == 0

    cases: tuple[tuple[DftDataset, dict[str, object]], ...] = (
        ("raw_counts", raw_row()),
        ("count_points", count_point_row()),
        ("aadf", aadf_row()),
    )
    acquired: dict[DftDataset, DftAcquisitionResult] = {}
    for dataset, row in cases:
        result = acquire(
            workspace,
            {1: envelope_bytes([row], 1, 1, 1, 1)},
            make_request(dataset),
        )
        assert isinstance(result, DftAcquisitionResult)
        acquired[dataset] = result

    def refuse_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("accepted DfT catalogue must not use the network")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    catalogue = catalogue_accepted_dft_snapshots(workspace)

    assert tuple(item.dataset for item in catalogue.snapshots) == (
        "aadf",
        "count_points",
        "raw_counts",
    )
    assert catalogue.counts.raw_counts == 1
    assert catalogue.counts.count_points == 1
    assert catalogue.counts.aadf == 1
    assert catalogue.counts.total == 3
    opened = open_accepted_dft_snapshot(workspace, acquired["raw_counts"].snapshot_id)
    assert (
        opened.summary.parser_report_fingerprint == acquired["raw_counts"].parser_report_fingerprint
    )
    assert opened.summary.records_accepted == 1
    assert opened.summary.opened_offline is True
    assert opened.report.fingerprint() == opened.summary.parser_report_fingerprint


def test_accepted_catalogue_refuses_unsafe_id_limit_and_tampered_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import traffictwin.integration.manchester.dft_acquisition as module

    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    result = acquire(
        workspace,
        {1: envelope_bytes([raw_row()], 1, 1, 1, 1)},
        make_request(),
    )
    assert isinstance(result, DftAcquisitionResult)

    with pytest.raises(DftAcquisitionError) as unsafe:
        open_accepted_dft_snapshot(workspace, "../accepted/escape")
    assert unsafe.value.code == "SNAPSHOT_ID_INVALID"

    unrelated = workspace / "accepted" / "webtris_site-20260723T120000Z-abcdef012345"
    unrelated.mkdir()
    assert catalogue_accepted_dft_snapshots(workspace).counts.total == 1

    monkeypatch.setattr(module, "DFT_ACCEPTED_CATALOGUE_MAX_SNAPSHOTS", 0)
    with pytest.raises(DftAcquisitionError) as limited:
        catalogue_accepted_dft_snapshots(workspace)
    assert limited.value.code == "ACCEPTED_CATALOGUE_LIMIT"

    monkeypatch.setattr(module, "DFT_ACCEPTED_CATALOGUE_MAX_SNAPSHOTS", 512)
    catalogue = catalogue_accepted_dft_snapshots(workspace)
    payload = catalogue.model_dump(mode="python")
    payload["counts"]["raw_counts"] = 0
    with pytest.raises(ValidationError, match="catalogue counts must reconcile"):
        DftAcceptedSnapshotCatalogue.model_validate(payload)


def test_accepted_catalogue_refuses_dft_named_symlink(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    accepted = workspace / "accepted"
    accepted.mkdir()
    target = tmp_path / "outside"
    target.mkdir()
    unsafe = accepted / "dft_raw_counts-20260723T120000Z-abcdef012345"
    unsafe.symlink_to(target, target_is_directory=True)

    with pytest.raises(DftAcquisitionError) as error:
        catalogue_accepted_dft_snapshots(workspace)
    assert error.value.code == "ACCEPTED_SNAPSHOT_INVALID"
    assert error.value.accepted_snapshot_id == unsafe.name


def test_accepted_with_warnings_follows_explicit_policy(tmp_path: Path) -> None:
    pages = {1: envelope_bytes([raw_row(cars_and_taxis=None, all_motor_vehicles=None)], 1, 1, 1, 1)}
    (tmp_path / "refuse").mkdir()
    (tmp_path / "accept").mkdir()
    with pytest.raises(DftAcquisitionError) as refused:
        acquire(tmp_path / "refuse", pages, make_request())
    assert refused.value.code == "WARNINGS_REFUSED"
    assert refused.value.quarantine_snapshot_id is not None
    assert len(workspace_dirs(tmp_path / "refuse", "quarantine")) == 1
    assert not workspace_dirs(tmp_path / "refuse", "accepted")

    result = acquire(tmp_path / "accept", pages, make_request(accept_with_warnings=True))
    assert result.parser_status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    accepted = workspace_dirs(tmp_path / "accept", "accepted")
    stored = ManchesterSnapshotManifest.model_validate_json(
        (accepted[0] / "snapshot-manifest.json").read_bytes()
    )
    assert stored.validation_state is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    assert any(f.code == "COUNTS_INCOMPLETE" for f in stored.findings)


def test_incomplete_pages_publish_nothing(tmp_path: Path) -> None:
    with pytest.raises(DftAcquisitionError) as excinfo:
        acquire(tmp_path, two_page_raw_dataset(), make_request(), fail_page=2)
    assert excinfo.value.code == "TRANSPORT_FAILURE"
    assert excinfo.value.quarantine_snapshot_id is None
    assert not workspace_dirs(tmp_path, "quarantine")
    assert not workspace_dirs(tmp_path, "accepted")


def test_page_row_and_byte_bounds_are_enforced(tmp_path: Path) -> None:
    for area in ("p", "r", "b"):
        (tmp_path / area).mkdir()
    huge_last_page = {1: envelope_bytes([raw_row()], 1, 50, 1, 50)}
    with pytest.raises(DftAcquisitionError) as pages_exceeded:
        acquire(tmp_path / "p", huge_last_page, make_request(max_pages=3))
    assert pages_exceeded.value.code == "PAGE_LIMIT_EXCEEDED"

    too_many_rows = {1: envelope_bytes([raw_row()], 1, 1, 500, 11)}
    with pytest.raises(DftAcquisitionError) as rows_exceeded:
        acquire(
            tmp_path / "r",
            too_many_rows,
            make_request(page_size=500, max_rows=10),
        )
    assert rows_exceeded.value.code == "ROW_LIMIT_EXCEEDED"

    tight_policy = ManchesterSnapshotPolicy(
        max_member_count=16, max_member_bytes=1_500, max_total_bytes=1_500
    )
    with pytest.raises(DftAcquisitionError) as bytes_exceeded:
        acquire(
            tmp_path / "b",
            two_page_raw_dataset(),
            make_request(policy=tight_policy),
        )
    assert bytes_exceeded.value.code == "TOTAL_BYTES_EXCEEDED"
    for area in ("p", "r", "b"):
        assert not workspace_dirs(tmp_path / area, "quarantine")
        assert not workspace_dirs(tmp_path / area, "accepted")


def test_http_failure_never_replaces_accepted_snapshot(tmp_path: Path) -> None:
    acquire(tmp_path, two_page_raw_dataset(), make_request())
    accepted = workspace_dirs(tmp_path, "accepted")[0]
    before = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    with pytest.raises(DftAcquisitionError):
        acquire(tmp_path, two_page_raw_dataset(), make_request(), fail_page=1)
    after = {
        p.relative_to(accepted).as_posix(): p.read_bytes()
        for p in sorted(accepted.rglob("*"))
        if p.is_file()
    }
    assert after == before


def test_schema_drift_is_quarantined_but_never_promoted(tmp_path: Path) -> None:
    drifted = {1: envelope_bytes([raw_row()], 1, 1, 1, 1, unexpected_envelope_key=1)}
    with pytest.raises(DftAcquisitionError) as excinfo:
        acquire(tmp_path, drifted, make_request())
    assert excinfo.value.code == "PARSE_REJECTED"
    assert excinfo.value.quarantine_snapshot_id is not None
    assert len(workspace_dirs(tmp_path, "quarantine")) == 1
    assert not workspace_dirs(tmp_path, "accepted")


def test_malformed_json_and_pagination_drift_publish_nothing(tmp_path: Path) -> None:
    (tmp_path / "m").mkdir()
    (tmp_path / "d").mkdir()
    with pytest.raises(DftAcquisitionError) as malformed:
        acquire(tmp_path / "m", {1: b"\x00not-json"}, make_request())
    assert malformed.value.code == "PAGINATION_PEEK_FAILED"

    drifting = {
        1: envelope_bytes([raw_row()], 1, 2, 1, 2),
        2: envelope_bytes([raw_row(id=1002, hour=13)], 2, 4, 1, 4),
    }
    with pytest.raises(DftAcquisitionError) as drift:
        acquire(tmp_path / "d", drifting, make_request())
    assert drift.value.code == "PAGINATION_DRIFT"
    for area in ("m", "d"):
        assert not workspace_dirs(tmp_path / area, "quarantine")
        assert not workspace_dirs(tmp_path / area, "accepted")


def test_reported_page_size_and_pagination_math_must_reconcile(tmp_path: Path) -> None:
    (tmp_path / "size").mkdir()
    (tmp_path / "math").mkdir()
    wrong_size = {1: envelope_bytes([raw_row()], 1, 1, 2, 1)}
    with pytest.raises(DftAcquisitionError) as size_error:
        acquire(tmp_path / "size", wrong_size, make_request(page_size=1))
    assert size_error.value.code == "PAGINATION_DRIFT"

    wrong_math = {1: envelope_bytes([raw_row()], 1, 2, 1, 1)}
    with pytest.raises(DftAcquisitionError) as math_error:
        acquire(tmp_path / "math", wrong_math, make_request(page_size=1))
    assert math_error.value.code == "PAGINATION_PEEK_FAILED"
    assert not workspace_dirs(tmp_path / "size", "quarantine")
    assert not workspace_dirs(tmp_path / "math", "quarantine")


def test_hash_mutation_in_quarantine_is_detected(tmp_path: Path) -> None:
    result = acquire(tmp_path, two_page_raw_dataset(), make_request())
    quarantine = workspace_dirs(tmp_path, "quarantine")[0]
    member = quarantine / "raw" / "pages" / "page-0001.json"
    member.chmod(0o644)
    member.write_bytes(b'{"tampered": true}')
    with pytest.raises(ManchesterSnapshotError):
        replay_dft_quarantine(
            tmp_path,
            result.snapshot_id,
            "raw_counts",
        )


def test_synthetic_mismatch_is_refused(tmp_path: Path) -> None:
    result = acquire(tmp_path, two_page_raw_dataset(), make_request())
    with pytest.raises(DftAcquisitionError) as excinfo:
        replay_dft_quarantine(
            tmp_path,
            result.snapshot_id,
            "raw_counts",
            expected_synthetic=False,
        )
    assert excinfo.value.code == "SYNTHETIC_MISMATCH"


def test_replay_dataset_must_match_quarantine_provenance(tmp_path: Path) -> None:
    result = acquire(tmp_path, two_page_raw_dataset(), make_request())
    with pytest.raises(DftAcquisitionError) as excinfo:
        replay_dft_quarantine(
            tmp_path,
            result.snapshot_id,
            "aadf",
            expected_synthetic=True,
        )
    assert excinfo.value.code == "DATASET_MISMATCH"
    assert excinfo.value.quarantine_snapshot_id == result.snapshot_id


def test_repeated_acquisition_cannot_overwrite(tmp_path: Path) -> None:
    acquire(tmp_path, two_page_raw_dataset(), make_request())
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        acquire(tmp_path, two_page_raw_dataset(), make_request())
    assert excinfo.value.code == "DESTINATION_EXISTS"
    assert len(workspace_dirs(tmp_path, "accepted")) == 1


def test_replay_is_offline_and_matches_the_original_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = acquire(tmp_path, two_page_raw_dataset(), make_request())

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during replay")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    replayed = replay_dft_quarantine(
        tmp_path,
        result.snapshot_id,
        "raw_counts",
        expected_synthetic=True,
    )
    assert replayed.parser_report_fingerprint == result.parser_report_fingerprint
    assert replayed.parser_status is ManchesterValidationState.ACCEPTED
    assert replayed.records_accepted == 2
    assert len(workspace_dirs(tmp_path, "accepted")) == 1


def _fixture_bytes() -> Iterator[tuple[str, DftDataset, str, str, bytes]]:
    mapping: list[tuple[str, DftDataset, str, str]] = [
        ("raw-count-43177.json.b64", "raw_counts", "dft_raw_counts", "/api/raw-counts"),
        (
            "count-point-6046.json.b64",
            "count_points",
            "dft_count_points",
            "/api/count-points",
        ),
        (
            "aadf-9219.json.b64",
            "aadf",
            "dft_aadf",
            "/api/average-annual-daily-flow",
        ),
    ]
    for name, dataset, source_id, endpoint_path in mapping:
        payload = base64.b64decode((FIXTURE_DIR / name).read_text())
        assert sha256_hex(payload) == FIXTURE_HASHES[name]
        yield name, dataset, source_id, endpoint_path, payload


def test_official_fixtures_replay_through_validation_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted during fixture replay")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    started = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)
    for name, dataset, source_id, endpoint_path, payload in _fixture_bytes():
        member = ManchesterRawMember(
            relative_path="pages/page-0001.json",
            byte_size=len(payload),
            media_type="application/json",
            sha256=sha256_hex(payload),
        )
        raw_fingerprint = build_raw_fingerprint([member])
        manifest = ManchesterQuarantineManifest(
            snapshot_id=build_snapshot_id(source_id, started, raw_fingerprint),
            source=ManchesterSourceIdentity(
                source_id=source_id,
                source_name=f"DfT official minimal fixture {name}",
                adapter_version="manchester-dft-acquisition-1.0",
                source_schema_version="1.0",
                freshness_policy_version="dft-historical-1.0",
            ),
            request=ManchesterRequestIdentity(
                host="roadtraffic.dft.gov.uk",
                path=endpoint_path,
                parameters=(
                    ("filter[local_authority_id]", 85),
                    ("page[number]", 1),
                    ("page[size]", 1),
                ),
            ),
            retrieval=ManchesterRetrievalWindow(started_at_utc=started, completed_at_utc=started),
            http=None,
            members=(member,),
            member_count=1,
            total_bytes=len(payload),
            raw_fingerprint=raw_fingerprint,
            publication_class=ManchesterPublicationClass.REDISTRIBUTABLE_RAW,
            licence_id=DFT_LICENCE_ID,
            attribution_text=DFT_ATTRIBUTION_TEXT,
            access_date=date(2026, 7, 22),
            synthetic=False,
        )
        publish_manchester_quarantine(tmp_path, manifest, {"pages/page-0001.json": payload}, POLICY)
        replayed = replay_dft_quarantine(
            tmp_path, manifest.snapshot_id, dataset, expected_synthetic=False
        )
        assert replayed.parser_status is ManchesterValidationState.ACCEPTED
        assert replayed.records_accepted == 1
        assert replayed.synthetic is False
