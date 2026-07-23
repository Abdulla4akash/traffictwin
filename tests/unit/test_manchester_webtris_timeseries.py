"""Offline adversarial tests for the MAN-08 WebTRIS historical timeseries service.

All acquisitions use injected fakes (httpx.MockTransport); no test touches the
network. Synthetic payloads are labelled synthetic. The retained official
OGL-recorded fixtures are used read-only as schema evidence for the
quarantine-replay path, never as a traffic sample or dissertation result.
"""

from __future__ import annotations

import base64
import json
import socket
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_webtris_acquisition import (
    FIXTURE_DIR,
    FIXTURE_HASHES,
    POLICY,
    REPORT_DATE,
    REQUEST_DATE,
    SITE_ID,
    SITE_NAME,
    acquire,
    daily_payload,
    full_day_rows,
    make_request,
    paged,
    site_payload,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
    ManchesterRawMember,
    ManchesterRequestIdentity,
    ManchesterRetrievalWindow,
    ManchesterSourceIdentity,
    build_raw_fingerprint,
    build_snapshot_id,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.snapshots import publish_manchester_quarantine
from traffictwin.integration.manchester.webtris import MPH_TO_MPS
from traffictwin.integration.manchester.webtris_acquisition import (
    WEBTRIS_ACQUISITION_METHOD_VERSION,
    WEBTRIS_ACQUISITION_SCHEMA_VERSION,
    WEBTRIS_ATTRIBUTION_TEXT,
    WEBTRIS_FRESHNESS_POLICY_VERSION,
    WEBTRIS_LICENCE_ID,
    WebtrisAcquisitionResult,
    WebtrisReplayRequest,
    WebtrisReplayResult,
    replay_webtris_quarantine,
)
from traffictwin.integration.manchester.webtris_timeseries import (
    MAX_TIMESERIES_EVIDENCE_ENTRIES,
    WebtrisChartSeries,
    WebtrisIntervalRow,
    WebtrisTimeseriesError,
    WebtrisTimeseriesEvidence,
    WebtrisTimeseriesFilter,
    WebtrisTimeseriesInput,
    WebtrisTimeseriesResult,
    build_webtris_chart_series,
    build_webtris_timeseries,
    build_webtris_timeseries_from_accepted_snapshots,
    verify_webtris_timeseries,
    verify_webtris_timeseries_from_accepted_snapshots,
)
from traffictwin.release.compatibility import initialise_v07_workspace

OFFICIAL_SITE_NAME = "M56/8150A"


def _workspace(tmp_path: Path) -> Path:
    return initialise_v07_workspace(tmp_path / "workspace-v0.7").path


def _site_rows(volume: str, missing: set[int] | None = None) -> list[dict[str, str]]:
    rows = full_day_rows(missing_intervals=missing)
    for row in rows:
        if row["Total Volume"] == "":
            continue
        row["Total Volume"] = volume
        row["0 - 520 cm"] = volume
        row["0 - 10 mph"] = volume
    return rows


def _quality_payload(percent: int) -> bytes:
    return json.dumps(
        {"row_count": 1, "Qualities": [{"Date": "2026-03-01T00:00:00", "Quality": percent}]}
    ).encode("utf-8")


def _responses(
    volume: str = "1", percent: int = 89, missing: set[int] | None = None
) -> dict[str, dict[int, bytes] | bytes]:
    return {
        "site": site_payload(),
        "daily": {1: daily_payload(_site_rows(volume, missing))},
        "quality": _quality_payload(percent),
    }


def _acquired_evidence(
    workspace: Path,
    *,
    site_id: str = SITE_ID,
    volume: str = "1",
    percent: int = 89,
    missing: set[int] | None = None,
    with_quality: bool = True,
) -> WebtrisTimeseriesEvidence:
    responses = _responses(volume, percent, missing)
    codes = ("MISSING_INTERVAL_MEASUREMENTS",) if missing else ()
    daily = acquire(
        workspace,
        make_request("daily_report", site_id=site_id, admitted_warning_codes=codes),
        responses,
    )
    quality = (
        acquire(workspace, make_request("daily_quality", site_id=site_id), responses)
        if with_quality
        else None
    )
    return WebtrisTimeseriesEvidence(daily_acquisition=daily, quality_acquisition=quality)


def _daily_replay_request(daily: WebtrisAcquisitionResult) -> WebtrisReplayRequest:
    return WebtrisReplayRequest(
        product="daily_report",
        site_id=daily.request.site_id,
        site_name=daily.request.site_name,
        report_date=daily.request.report_date,
        page_size=daily.request.page_size,
    )


def _replayed_evidence(
    workspace: Path, evidence: WebtrisTimeseriesEvidence
) -> WebtrisTimeseriesEvidence:
    daily = evidence.daily_acquisition
    assert daily is not None
    daily_replay = replay_webtris_quarantine(
        workspace, daily.snapshot_id, _daily_replay_request(daily)
    )
    quality_replay: WebtrisReplayResult | None = None
    if evidence.quality_acquisition is not None:
        quality = evidence.quality_acquisition
        quality_replay = replay_webtris_quarantine(
            workspace,
            quality.snapshot_id,
            WebtrisReplayRequest(
                product="daily_quality",
                site_id=quality.request.site_id,
                site_name=quality.request.site_name,
                report_date=quality.request.report_date,
            ),
        )
    return WebtrisTimeseriesEvidence(daily_replay=daily_replay, quality_replay=quality_replay)


def _filter(**overrides: object) -> WebtrisTimeseriesFilter:
    values: dict[str, object] = {
        "site_ids": (SITE_ID,),
        "start_date": REPORT_DATE,
        "end_date": REPORT_DATE,
        "measurement_states": ("missing", "observed"),
    }
    values.update(overrides)
    return WebtrisTimeseriesFilter.model_validate(values)


def _publish_official_quarantine(
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


def _official_fixture_evidence(workspace: Path) -> WebtrisTimeseriesEvidence:
    payloads: dict[str, bytes] = {}
    for name, digest in FIXTURE_HASHES.items():
        payload = base64.b64decode((FIXTURE_DIR / name).read_text())
        assert sha256_hex(payload) == digest
        payloads[name] = payload
    daily_snapshot = _publish_official_quarantine(
        workspace,
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
    quality_snapshot = _publish_official_quarantine(
        workspace,
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
    daily_replay = replay_webtris_quarantine(
        workspace,
        daily_snapshot,
        WebtrisReplayRequest(
            product="daily_report",
            site_id="34",
            site_name=OFFICIAL_SITE_NAME,
            report_date=REPORT_DATE,
            page_size=96,
            expected_synthetic=False,
        ),
    )
    quality_replay = replay_webtris_quarantine(
        workspace,
        quality_snapshot,
        WebtrisReplayRequest(
            product="daily_quality",
            site_id="34",
            site_name=OFFICIAL_SITE_NAME,
            report_date=REPORT_DATE,
            expected_synthetic=False,
        ),
    )
    return WebtrisTimeseriesEvidence(daily_replay=daily_replay, quality_replay=quality_replay)


def test_accepted_daily_and_quality_build_full_day_rows(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)

    result = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())

    assert result.result_state == "rows_available"
    assert result.counts.rows_seen == 96
    assert result.counts.rows_admitted == 96
    assert result.counts.rows_excluded == 0
    assert result.counts.evidence_supplied == 1
    assert result.counts.input_pages_total == 2
    assert result.licence_id == WEBTRIS_LICENCE_ID
    assert result.attribution_text == WEBTRIS_ATTRIBUTION_TEXT
    assert result.synthetic is True
    first = result.rows[0]
    assert first.site_id == SITE_ID
    assert first.site_name == SITE_NAME
    assert first.report_date_raw == "2026-03-01T00:00:00"
    assert first.time_period_ending_raw == "00:14:59"
    assert first.total_volume == 1
    assert first.average_speed_mph == Decimal("50.2")
    assert first.average_speed_mps == Decimal("50.2") * MPH_TO_MPS
    assert first.availability_percent == 89
    assert first.quality_snapshot_id is not None
    assert first.daily_snapshot_id == evidence.daily_snapshot_id()
    assert first.utc_projection_available is False
    assert first.time_basis == "source_string_undeclared"
    assert first.evidence_status == "historical"


def test_accepted_snapshot_id_build_matches_receipt_build_without_quality(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace, with_quality=False)
    daily = evidence.daily_acquisition
    assert daily is not None

    receipt_build = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())
    id_build = build_webtris_timeseries_from_accepted_snapshots(
        workspace,
        (daily.snapshot_id,),
        interval_filter=_filter(),
    )

    assert id_build == receipt_build
    assert id_build.inputs[0].availability_percent is None
    assert all(row.availability_percent is None for row in id_build.rows)
    assert (
        verify_webtris_timeseries_from_accepted_snapshots(
            workspace,
            (daily.snapshot_id,),
            id_build,
        )
        == id_build
    )


def test_accepted_snapshot_id_duplicates_are_explicit_and_order_invariant(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    first = _acquired_evidence(workspace, with_quality=False)
    second = _acquired_evidence(workspace, site_id="35", volume="2", with_quality=False)
    first_daily = first.daily_acquisition
    second_daily = second.daily_acquisition
    assert first_daily is not None and second_daily is not None
    interval_filter = _filter(site_ids=("34", "35"))

    forward = build_webtris_timeseries_from_accepted_snapshots(
        workspace,
        (first_daily.snapshot_id, second_daily.snapshot_id, first_daily.snapshot_id),
        interval_filter=interval_filter,
    )
    reverse = build_webtris_timeseries_from_accepted_snapshots(
        workspace,
        (first_daily.snapshot_id, first_daily.snapshot_id, second_daily.snapshot_id),
        interval_filter=interval_filter,
    )

    assert forward == reverse
    assert forward.counts.evidence_supplied == 3
    assert forward.counts.evidence_admitted == 2
    assert forward.counts.identical_duplicates_collapsed == 1
    assert forward.inputs[0].identical_duplicates_collapsed == 1


def test_accepted_snapshot_id_builder_refuses_wrong_product_and_conflicts(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    site = acquire(workspace, make_request("site"), _responses())
    with pytest.raises(WebtrisTimeseriesError) as wrong_product:
        build_webtris_timeseries_from_accepted_snapshots(
            workspace,
            (site.snapshot_id,),
            interval_filter=_filter(),
        )
    assert wrong_product.value.code == "PRODUCT_NOT_ADMITTED"

    first = _acquired_evidence(workspace, volume="1", with_quality=False)
    second = _acquired_evidence(workspace, volume="2", with_quality=False)
    first_daily = first.daily_acquisition
    second_daily = second.daily_acquisition
    assert first_daily is not None and second_daily is not None
    with pytest.raises(WebtrisTimeseriesError) as conflicting:
        build_webtris_timeseries_from_accepted_snapshots(
            workspace,
            (first_daily.snapshot_id, second_daily.snapshot_id),
            interval_filter=_filter(),
        )
    assert conflicting.value.code == "CONFLICTING_DUPLICATE_EVIDENCE"

    first_result = build_webtris_timeseries_from_accepted_snapshots(
        workspace,
        (first_daily.snapshot_id,),
        interval_filter=_filter(),
    )
    with pytest.raises(WebtrisTimeseriesError) as mismatch:
        verify_webtris_timeseries_from_accepted_snapshots(
            workspace,
            (second_daily.snapshot_id,),
            first_result,
        )
    assert mismatch.value.code == "RESULT_VERIFICATION_MISMATCH"


def test_build_is_deterministic_and_input_order_invariant(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first_site = _acquired_evidence(workspace)
    second_site = _acquired_evidence(workspace, site_id="35", volume="2", percent=77)
    interval_filter = _filter(site_ids=("34", "35"))

    forward = build_webtris_timeseries(
        workspace, (first_site, second_site), interval_filter=interval_filter
    )
    reversed_order = build_webtris_timeseries(
        workspace, (second_site, first_site), interval_filter=interval_filter
    )

    assert forward.fingerprint() == reversed_order.fingerprint()
    assert [item.site_id for item in forward.inputs] == ["34", "35"]
    assert forward.counts.rows_admitted == 192
    site_sequence = [row.site_id for row in forward.rows]
    assert site_sequence == sorted(site_sequence, key=lambda site: (len(site), site))
    reloaded = WebtrisTimeseriesResult.model_validate_json(forward.model_dump_json())
    assert reloaded.fingerprint() == forward.fingerprint()


def test_official_fixture_replay_builds_verbatim_rows(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _official_fixture_evidence(workspace)

    result = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())

    assert result.synthetic is False
    assert result.counts.rows_admitted == 96
    fixture_rows = json.loads(
        base64.b64decode((FIXTURE_DIR / "daily-site-34-20260301.json.b64").read_text())
    )["Rows"]
    for fixture_row in (fixture_rows[0], fixture_rows[82]):
        row = result.rows[int(fixture_row["Time Interval"])]
        assert row.site_name == OFFICIAL_SITE_NAME
        assert row.report_date_raw == fixture_row["Report Date"]
        assert row.time_period_ending_raw == fixture_row["Time Period Ending"]
        expected_volume = (
            None if fixture_row["Total Volume"] == "" else int(fixture_row["Total Volume"])
        )
        assert row.total_volume == expected_volume
        assert row.availability_percent == 89
    daily_replay = evidence.daily_replay
    assert daily_replay is not None
    assert result.counts.intervals_missing_measurement_seen == daily_replay.intervals_missing
    assert result.counts.rows_missing_measurement_admitted == daily_replay.intervals_missing
    assert result.inputs[0].daily_intervals_missing == daily_replay.intervals_missing
    series = build_webtris_chart_series(result)
    assert len(series) == 1
    assert series[0].site_name == OFFICIAL_SITE_NAME
    assert series[0].result_fingerprint == result.fingerprint()


def test_missing_intervals_stay_missing_and_are_never_zero(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace, missing={7})

    both = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())
    missing_row = both.rows[7]
    assert missing_row.measurement_state == "missing"
    assert missing_row.total_volume is None
    assert missing_row.average_speed_mph is None
    assert both.counts.intervals_missing_measurement_seen == 1
    assert both.counts.rows_missing_measurement_admitted == 1

    observed_only = build_webtris_timeseries(
        workspace, (evidence,), interval_filter=_filter(measurement_states=("observed",))
    )
    assert observed_only.counts.rows_admitted == 95
    assert observed_only.counts.rows_excluded == 1
    assert observed_only.exclusions[0].interval_index == 7
    assert observed_only.exclusions[0].reason == "measurement_state_filtered"
    assert observed_only.exclusions[0].excluded_value_replaced_with_zero is False
    assert all(row.measurement_state == "observed" for row in observed_only.rows)
    assert all(row.total_volume == 1 for row in observed_only.rows)
    assert {row.interval_index for row in observed_only.rows} == set(range(96)) - {7}


def test_whole_day_filters_partition_with_exact_reasons(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with_quality = _acquired_evidence(workspace)
    without_quality = _acquired_evidence(workspace, site_id="35", volume="2", with_quality=False)

    cases: tuple[tuple[WebtrisTimeseriesFilter, WebtrisTimeseriesEvidence, str], ...] = (
        (_filter(site_ids=("9999",)), with_quality, "site_not_selected"),
        (
            _filter(start_date=date(2026, 3, 2), end_date=date(2026, 3, 2)),
            with_quality,
            "outside_date_range",
        ),
        (_filter(min_availability_percent=90), with_quality, "availability_below_minimum"),
        (
            _filter(site_ids=("35",), min_availability_percent=90),
            without_quality,
            "availability_unreported",
        ),
    )
    for interval_filter, evidence, reason in cases:
        result = build_webtris_timeseries(workspace, (evidence,), interval_filter=interval_filter)
        assert result.result_state == "empty_after_filters"
        assert result.counts.rows_admitted == 0
        assert result.counts.rows_excluded == 96
        assert {item.reason for item in result.exclusions} == {reason}
        assert result.counts.exclusion_reasons[0].reason == reason
        assert result.counts.exclusion_reasons[0].rows == 96

    admitted = build_webtris_timeseries(
        workspace, (with_quality,), interval_filter=_filter(min_availability_percent=89)
    )
    assert admitted.counts.rows_admitted == 96
    assert all(row.total_volume == 1 for row in admitted.rows)


def test_identical_duplicates_collapse_with_reported_surplus(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    replayed = _replayed_evidence(workspace, evidence)

    result = build_webtris_timeseries(
        workspace, (replayed, evidence, evidence), interval_filter=_filter()
    )

    assert result.counts.evidence_supplied == 3
    assert result.counts.evidence_admitted == 1
    assert result.counts.identical_duplicates_collapsed == 2
    assert result.inputs[0].daily_storage_area == "accepted"
    assert result.inputs[0].identical_duplicates_collapsed == 2
    assert result.counts.rows_admitted == 96
    permuted = build_webtris_timeseries(
        workspace, (evidence, evidence, replayed), interval_filter=_filter()
    )
    assert permuted.fingerprint() == result.fingerprint()


def test_conflicting_duplicate_evidence_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first = _acquired_evidence(workspace)
    second = _acquired_evidence(workspace, volume="2", percent=77)

    with pytest.raises(WebtrisTimeseriesError) as excinfo:
        build_webtris_timeseries(workspace, (first, second), interval_filter=_filter())

    assert excinfo.value.code == "CONFLICTING_DUPLICATE_EVIDENCE"

    daily = first.daily_acquisition
    assert daily is not None
    without_quality = WebtrisTimeseriesEvidence(daily_acquisition=daily)
    with pytest.raises(WebtrisTimeseriesError) as quality_conflict:
        build_webtris_timeseries(workspace, (first, without_quality), interval_filter=_filter())

    assert quality_conflict.value.code == "CONFLICTING_DUPLICATE_EVIDENCE"


def test_replayed_quarantine_evidence_builds_rows(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _replayed_evidence(workspace, _acquired_evidence(workspace))

    result = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())

    assert result.counts.rows_admitted == 96
    assert result.inputs[0].daily_storage_area == "quarantine"
    assert result.inputs[0].quality_storage_area == "quarantine"
    assert result.rows[0].availability_percent == 89


def test_tampered_accepted_snapshot_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    daily = evidence.daily_acquisition
    assert daily is not None
    target = workspace / "accepted" / daily.snapshot_id / "raw" / "pages" / "page-0001.json"
    stored = target.read_bytes()
    flipped = stored.replace(b'"Avg mph": "50.2"', b'"Avg mph": "51.2"', 1)
    assert flipped != stored and len(flipped) == len(stored)
    target.chmod(0o600)
    target.write_bytes(flipped)

    with pytest.raises(WebtrisTimeseriesError) as excinfo:
        build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())

    assert excinfo.value.code == "ACCEPTED_SNAPSHOT_INVALID"


def test_tampered_quarantine_member_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _replayed_evidence(workspace, _acquired_evidence(workspace))
    daily_replay = evidence.daily_replay
    assert daily_replay is not None
    target = (
        workspace / "quarantine" / daily_replay.snapshot_id / "raw" / "pages" / "page-0001.json"
    )
    stored = target.read_bytes()
    flipped = stored.replace(b'"Total Volume": "1"', b'"Total Volume": "2"', 1)
    assert flipped != stored and len(flipped) == len(stored)
    target.chmod(0o600)
    target.write_bytes(flipped)

    with pytest.raises(WebtrisTimeseriesError) as excinfo:
        build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())

    assert excinfo.value.code == "QUARANTINE_REPLAY_INVALID"


def test_receipt_identity_mismatches_are_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    daily = evidence.daily_acquisition
    assert daily is not None

    drifted_parser = daily.model_copy(update={"parser_report_fingerprint": "0" * 64})
    with pytest.raises(WebtrisTimeseriesError) as parser_mismatch:
        build_webtris_timeseries(
            workspace,
            (WebtrisTimeseriesEvidence(daily_acquisition=drifted_parser),),
            interval_filter=_filter(),
        )
    assert parser_mismatch.value.code == "PARSER_REPORT_MISMATCH"

    drifted_receipt = daily.model_copy(update={"snapshot_receipt_fingerprint": "0" * 64})
    with pytest.raises(WebtrisTimeseriesError) as receipt_mismatch:
        build_webtris_timeseries(
            workspace,
            (WebtrisTimeseriesEvidence(daily_acquisition=drifted_receipt),),
            interval_filter=_filter(),
        )
    assert receipt_mismatch.value.code == "ACCEPTED_SNAPSHOT_MISMATCH"

    replayed = _replayed_evidence(workspace, evidence)
    daily_replay = replayed.daily_replay
    assert daily_replay is not None
    drifted_replay = daily_replay.model_copy(update={"parser_report_fingerprint": "0" * 64})
    with pytest.raises(WebtrisTimeseriesError) as replay_mismatch:
        build_webtris_timeseries(
            workspace,
            (WebtrisTimeseriesEvidence(daily_replay=drifted_replay),),
            interval_filter=_filter(),
        )
    assert replay_mismatch.value.code == "QUARANTINE_REPLAY_MISMATCH"


def test_accepted_bytes_cannot_be_relabelled_to_another_site_or_date(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    daily = evidence.daily_acquisition
    assert daily is not None

    for update in ({"site_id": "35"}, {"report_date": date(2026, 3, 2)}):
        forged = daily.model_copy(update={"request": daily.request.model_copy(update=update)})
        with pytest.raises(WebtrisTimeseriesError) as excinfo:
            build_webtris_timeseries(
                workspace,
                (WebtrisTimeseriesEvidence(daily_acquisition=forged),),
                interval_filter=_filter(site_ids=("34", "35")),
            )
        assert excinfo.value.code == "ACCEPTED_SNAPSHOT_MISMATCH"

    daily_replay = _replayed_evidence(workspace, evidence).daily_replay
    assert daily_replay is not None
    for update in ({"site_id": "35"}, {"report_date": date(2026, 3, 2)}):
        forged_replay = daily_replay.model_copy(
            update={"request": daily_replay.request.model_copy(update=update)}
        )
        with pytest.raises(WebtrisTimeseriesError) as replay_excinfo:
            build_webtris_timeseries(
                workspace,
                (WebtrisTimeseriesEvidence(daily_replay=forged_replay),),
                interval_filter=_filter(site_ids=("34", "35")),
            )
        assert replay_excinfo.value.code == "QUARANTINE_REPLAY_INVALID"


def test_evidence_shape_and_scope_mismatches_are_unrepresentable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    daily = evidence.daily_acquisition
    quality = evidence.quality_acquisition
    assert daily is not None and quality is not None
    site_reference = acquire(workspace, make_request("site"), _responses())

    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(daily_acquisition=site_reference)
    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(quality_acquisition=quality)
    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(
            daily_acquisition=daily,
            daily_replay=replay_webtris_quarantine(
                workspace, daily.snapshot_id, _daily_replay_request(daily)
            ),
        )
    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(daily_acquisition=quality)
    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(daily_acquisition=daily, quality_acquisition=daily)
    quality_replay = replay_webtris_quarantine(
        workspace,
        quality.snapshot_id,
        WebtrisReplayRequest(
            product="daily_quality",
            site_id=quality.request.site_id,
            site_name=quality.request.site_name,
            report_date=quality.request.report_date,
        ),
    )
    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(
            daily_acquisition=daily,
            quality_acquisition=quality,
            quality_replay=quality_replay,
        )
    real_class_snapshot = _publish_official_quarantine(
        workspace,
        "webtris_daily_quality",
        "quality/daily-quality.json",
        "/api/v1.0/quality/daily",
        (
            ("end_date", REQUEST_DATE),
            ("siteId", SITE_ID),
            ("start_date", REQUEST_DATE),
        ),
        _quality_payload(89),
    )
    real_class_replay = replay_webtris_quarantine(
        workspace,
        real_class_snapshot,
        WebtrisReplayRequest(
            product="daily_quality",
            site_id=SITE_ID,
            site_name=SITE_NAME,
            report_date=REPORT_DATE,
        ),
    )
    assert real_class_replay.synthetic is False
    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(daily_acquisition=daily, quality_replay=real_class_replay)

    (tmp_path / "other").mkdir()
    other_workspace = initialise_v07_workspace(tmp_path / "other" / "workspace-v0.7").path
    other_responses = _responses()
    other_responses["quality"] = json.dumps(
        {"row_count": 1, "Qualities": [{"Date": "2026-03-02T00:00:00", "Quality": 89}]}
    ).encode("utf-8")
    other_day = acquire(
        other_workspace,
        make_request("daily_quality", report_date=date(2026, 3, 2)),
        other_responses,
    )
    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(daily_acquisition=daily, quality_acquisition=other_day)


def test_mixed_evidence_classes_are_refused_across_entries(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    synthetic_entry = _acquired_evidence(workspace, site_id="35", volume="2")
    official_entry = _official_fixture_evidence(workspace)

    with pytest.raises(WebtrisTimeseriesError) as excinfo:
        build_webtris_timeseries(
            workspace,
            (synthetic_entry, official_entry),
            interval_filter=_filter(site_ids=("34", "35")),
        )

    assert excinfo.value.code == "MIXED_EVIDENCE_CLASS"


def test_schema_drifted_quarantine_cannot_back_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    drifted = dict(json.loads(daily_payload(full_day_rows())))
    drifted["unexpected_key"] = 1
    payload = json.dumps(drifted).encode("utf-8")
    snapshot_id = _publish_official_quarantine(
        workspace,
        "webtris_daily_report",
        "pages/page-0001.json",
        "/api/v1.0/reports/daily",
        (
            ("end_date", REQUEST_DATE),
            ("page", "1"),
            ("page_size", "96"),
            ("sites", SITE_ID),
            ("start_date", REQUEST_DATE),
        ),
        payload,
    )
    replay = replay_webtris_quarantine(
        workspace,
        snapshot_id,
        WebtrisReplayRequest(
            product="daily_report",
            site_id=SITE_ID,
            site_name=SITE_NAME,
            report_date=REPORT_DATE,
            page_size=96,
        ),
    )
    assert replay.parser_status.value == "rejected"

    with pytest.raises(ValidationError):
        WebtrisTimeseriesEvidence(daily_replay=replay)


def test_bounds_and_workspace_are_enforced(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)

    with pytest.raises(WebtrisTimeseriesError) as no_evidence:
        build_webtris_timeseries(workspace, (), interval_filter=_filter())
    assert no_evidence.value.code == "NO_EVIDENCE"

    too_many = (evidence,) * (MAX_TIMESERIES_EVIDENCE_ENTRIES + 1)
    with pytest.raises(WebtrisTimeseriesError) as bound:
        build_webtris_timeseries(workspace, too_many, interval_filter=_filter())
    assert bound.value.code == "EVIDENCE_BOUND_EXCEEDED"

    daily = evidence.daily_acquisition
    assert daily is not None
    forged_pages = replay_webtris_quarantine(
        workspace, daily.snapshot_id, _daily_replay_request(daily)
    ).model_copy(update={"pages": 4000})
    with pytest.raises(WebtrisTimeseriesError) as pages:
        build_webtris_timeseries(
            workspace,
            (WebtrisTimeseriesEvidence(daily_replay=forged_pages),),
            interval_filter=_filter(),
        )
    assert pages.value.code == "INPUT_PAGE_BOUND_EXCEEDED"

    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    with pytest.raises(WebtrisTimeseriesError) as unmarked:
        build_webtris_timeseries(ordinary, (evidence,), interval_filter=_filter())
    assert unmarked.value.code == "WORKSPACE_INVALID"

    with pytest.raises(ValidationError):
        _filter(site_ids=tuple(str(number) for number in range(100, 133)))
    with pytest.raises(ValidationError):
        _filter(end_date=date(2027, 4, 1))
    assert _filter(end_date=date(2027, 3, 1)).end_date == date(2027, 3, 1)
    with pytest.raises(ValidationError):
        _filter(end_date=date(2027, 3, 2))
    with pytest.raises(ValidationError):
        _filter(site_ids=("35", "34"))
    with pytest.raises(ValidationError):
        _filter(site_ids=("007",))
    with pytest.raises(ValidationError):
        _filter(site_ids=("34", "5"))
    with pytest.raises(ValidationError):
        _filter(measurement_states=("observed", "observed"))

    bypassed_filter = WebtrisTimeseriesFilter.model_construct(
        site_ids=("34", "34"),
        start_date=REPORT_DATE,
        end_date=REPORT_DATE,
        measurement_states=("missing", "observed"),
    )
    with pytest.raises(WebtrisTimeseriesError) as invalid_filter:
        build_webtris_timeseries(workspace, (evidence,), interval_filter=bypassed_filter)
    assert invalid_filter.value.code == "FILTER_INVALID"


def test_build_performs_no_network_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    replayed = _replayed_evidence(workspace, evidence)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("timeseries build must not use the network")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    result = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())
    replay_result = build_webtris_timeseries(workspace, (replayed,), interval_filter=_filter())

    assert result.counts.rows_admitted == 96
    assert replay_result.counts.rows_admitted == 96


def test_timezone_live_and_unit_strengthening_is_unrepresentable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = build_webtris_timeseries(
        workspace, (_acquired_evidence(workspace),), interval_filter=_filter()
    )

    row_payload = json.loads(result.rows[0].model_dump_json())
    for field, value in (
        ("time_basis", "documented_utc"),
        ("utc_projection_available", True),
        ("nominal_interval_seconds", 3600),
        ("volume_unit", "vehicles_per_hour"),
        ("speed_source_unit", "km_h"),
        ("speed_derived_unit", "mph"),
        ("missing_filled_with_zero", True),
        ("evidence_status", "near_live"),
        ("sensor_accuracy_claim_available", True),
    ):
        mutated = dict(row_payload)
        mutated[field] = value
        with pytest.raises(ValidationError):
            WebtrisIntervalRow.model_validate_json(json.dumps(mutated))

    result_payload = json.loads(result.model_dump_json())
    for field, value in (
        ("utc_timestamps_available", True),
        ("retrieval_time_used_as_observation_time", True),
        ("live_road_traffic_available", True),
        ("quality_is_accuracy_score", True),
        ("cross_source_fusion_performed", True),
        ("cross_site_aggregation_performed", True),
        ("resampling_or_interpolation_performed", True),
        ("map_association_performed", True),
        ("city_road_coverage_claimed", True),
        ("causal_interpretation_available", True),
        ("carriageway_direction_decoded", True),
        ("public_export_available", True),
        ("evidence_status", "near_live"),
        ("time_basis", "documented_utc"),
    ):
        mutated = dict(result_payload)
        mutated[field] = value
        with pytest.raises(ValidationError):
            WebtrisTimeseriesResult.model_validate_json(json.dumps(mutated))

    filter_fields = set(WebtrisTimeseriesFilter.model_fields)
    assert filter_fields.isdisjoint(
        {"direction", "carriageway", "vehicle_class", "utc_start", "utc_end"}
    )
    result_fields = set(WebtrisTimeseriesResult.model_fields)
    assert result_fields.isdisjoint(
        {"observed_at_utc", "retrieved_at_utc", "evaluated_at_utc", "freshness"}
    )


def test_persisted_result_mutations_fail_validation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace, missing={7})
    result = build_webtris_timeseries(
        workspace, (evidence,), interval_filter=_filter(measurement_states=("observed",))
    )
    payload = json.loads(result.model_dump_json())

    def mutated(**changes: object) -> str:
        clone = json.loads(json.dumps(payload))
        for path, value in changes.items():
            keys = path.split("__")
            target = clone
            for key in keys[:-1]:
                index_or_name: object = int(key) if key.isdigit() else key
                target = target[index_or_name]
            last: object = int(keys[-1]) if keys[-1].isdigit() else keys[-1]
            if value == "__delete__":
                del target[last]
            else:
                target[last] = value
        return json.dumps(clone)

    mutations: tuple[str, ...] = (
        mutated(counts__rows_admitted=96),
        mutated(rows__0__total_volume=2),
        mutated(rows__0__average_speed_mph="60.2"),
        mutated(rows__0="__delete__"),
        mutated(rows_fingerprint="0" * 64),
        mutated(inputs_fingerprint="0" * 64),
        mutated(filter_fingerprint="0" * 64),
        mutated(interval_filter__end_date="2026-03-02"),
        mutated(interval_filter__measurement_states=["missing", "observed"]),
        mutated(inputs__0__daily_snapshot_id="webtris_daily_report-20990101T000000Z-aaaaaaaaaaaa"),
        mutated(inputs__0__availability_percent=99),
        mutated(inputs__0__daily_intervals_missing=0),
        mutated(synthetic=False),
        mutated(exclusions__0__reason="site_not_selected"),
        mutated(counts__identical_duplicates_collapsed=1),
        mutated(result_state="empty_after_filters"),
        mutated(licence_id="CC-BY-4.0"),
        mutated(attribution_text="tampered attribution"),
    )
    for mutated_payload in mutations:
        with pytest.raises(ValidationError):
            WebtrisTimeseriesResult.model_validate_json(mutated_payload)

    assert WebtrisTimeseriesResult.model_validate_json(json.dumps(payload)) == result


def test_chart_series_expose_source_labels_without_aggregation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first_site = _acquired_evidence(workspace, missing={3})
    second_site = _acquired_evidence(workspace, site_id="35", volume="2", percent=77)
    result = build_webtris_timeseries(
        workspace,
        (first_site, second_site),
        interval_filter=_filter(site_ids=("34", "35")),
    )

    series = build_webtris_chart_series(result)

    assert [item.site_id for item in series] == ["34", "35"]
    assert all(item.result_fingerprint == result.fingerprint() for item in series)
    first = series[0]
    assert len(first.points) == 96
    assert first.points[3].measurement_state == "missing"
    assert first.points[3].total_volume is None
    assert first.points[4].total_volume == 1
    assert first.time_axis_basis == "source_string_undeclared"
    assert first.utc_timestamps_available is False
    assert first.volume_unit == "vehicles_per_reported_interval"
    assert first.speed_source_unit == "mph"
    assert first.missing_filled_with_zero is False
    assert series[1].points[0].total_volume == 2
    first_speed_mph = first.points[0].average_speed_mph
    assert first_speed_mph is not None
    assert first.points[0].average_speed_mps == first_speed_mph * MPH_TO_MPS

    series_payload = json.loads(first.model_dump_json())
    for field, value in (
        ("time_axis_basis", "documented_utc"),
        ("utc_timestamps_available", True),
        ("missing_filled_with_zero", True),
        ("volume_unit", "vehicles_per_hour"),
        ("speed_source_unit", "km_h"),
        ("evidence_status", "near_live"),
    ):
        strengthened = dict(series_payload)
        strengthened[field] = value
        with pytest.raises(ValidationError):
            WebtrisChartSeries.model_validate_json(json.dumps(strengthened))
    zero_filled = json.loads(json.dumps(series_payload))
    assert zero_filled["points"][3]["measurement_state"] == "missing"
    zero_filled["points"][3]["total_volume"] = 0
    with pytest.raises(ValidationError):
        WebtrisChartSeries.model_validate_json(json.dumps(zero_filled))

    empty = build_webtris_timeseries(
        workspace, (first_site,), interval_filter=_filter(site_ids=("9999",))
    )
    assert empty.result_state == "empty_after_filters"
    assert build_webtris_chart_series(empty) == ()


def _recomputed(payload: dict[str, object]) -> str:
    """Re-derive rows/inputs/filter fingerprints the way any offline actor could."""

    clone = json.loads(json.dumps(payload))
    clone["rows_fingerprint"] = sha256_hex(
        canonical_json(
            [
                WebtrisIntervalRow.model_validate_json(json.dumps(row)).fingerprint()
                for row in clone["rows"]
            ]
        ).encode("utf-8")
    )
    clone["inputs_fingerprint"] = sha256_hex(
        canonical_json(
            [
                WebtrisTimeseriesInput.model_validate_json(json.dumps(item)).fingerprint()
                for item in clone["inputs"]
            ]
        ).encode("utf-8")
    )
    clone["filter_fingerprint"] = WebtrisTimeseriesFilter.model_validate_json(
        json.dumps(clone["interval_filter"])
    ).fingerprint()
    return json.dumps(clone)


def test_semantic_bindings_survive_recomputed_fingerprints(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = build_webtris_timeseries(
        workspace, (_acquired_evidence(workspace, missing={7}),), interval_filter=_filter()
    )
    payload = json.loads(result.model_dump_json())
    revalidated = WebtrisTimeseriesResult.model_validate_json(_recomputed(payload))
    assert revalidated.fingerprint() == result.fingerprint()

    synthetic_relabel = json.loads(json.dumps(payload))
    synthetic_relabel["rows"][0]["synthetic"] = False
    with pytest.raises(ValidationError):
        WebtrisTimeseriesResult.model_validate_json(_recomputed(synthetic_relabel))

    alien_page = json.loads(json.dumps(payload))
    alien_page["rows"][0]["daily_page_number"] = 2
    alien_page["rows"][0]["daily_member_path"] = "pages/page-0002.json"
    with pytest.raises(ValidationError):
        WebtrisTimeseriesResult.model_validate_json(_recomputed(alien_page))

    alien_member = json.loads(json.dumps(payload))
    alien_member["rows"][0]["daily_member_path"] = "site/site.json"
    with pytest.raises(ValidationError):
        WebtrisTimeseriesResult.model_validate_json(_recomputed(alien_member))

    status_relabel = json.loads(json.dumps(payload))
    status_relabel["inputs"][0]["daily_parser_status"] = "accepted"
    with pytest.raises(ValidationError):
        WebtrisTimeseriesResult.model_validate_json(_recomputed(status_relabel))

    dropped_row = json.loads(json.dumps(payload))
    del dropped_row["rows"][95]
    with pytest.raises(ValidationError):
        WebtrisTimeseriesResult.model_validate_json(_recomputed(dropped_row))


def test_persisted_result_must_reproduce_from_immutable_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    result = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())

    assert verify_webtris_timeseries(workspace, (evidence,), result) == result

    payload = json.loads(result.model_dump_json())
    payload["rows"][0]["total_volume"] = 2
    internally_consistent = WebtrisTimeseriesResult.model_validate_json(_recomputed(payload))
    assert internally_consistent != result

    with pytest.raises(WebtrisTimeseriesError) as mismatch:
        verify_webtris_timeseries(workspace, (evidence,), internally_consistent)
    assert mismatch.value.code == "RESULT_VERIFICATION_MISMATCH"


def test_source_clock_labels_remain_strict_verbatim_clock_strings(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    result = build_webtris_timeseries(
        workspace, (_acquired_evidence(workspace),), interval_filter=_filter()
    )
    payload = json.loads(result.rows[0].model_dump_json())
    payload["time_period_ending_raw"] = "99:99:99"

    with pytest.raises(ValidationError):
        WebtrisIntervalRow.model_validate_json(json.dumps(payload))


def test_quality_evidence_verification_failures(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    replayed = _replayed_evidence(workspace, evidence)
    quality = evidence.quality_acquisition
    daily = evidence.daily_acquisition
    assert quality is not None and daily is not None

    drifted_parser = quality.model_copy(update={"parser_report_fingerprint": "0" * 64})
    with pytest.raises(WebtrisTimeseriesError) as parser_mismatch:
        build_webtris_timeseries(
            workspace,
            (
                WebtrisTimeseriesEvidence(
                    daily_acquisition=daily, quality_acquisition=drifted_parser
                ),
            ),
            interval_filter=_filter(),
        )
    assert parser_mismatch.value.code == "PARSER_REPORT_MISMATCH"

    drifted_receipt = quality.model_copy(update={"snapshot_receipt_fingerprint": "0" * 64})
    with pytest.raises(WebtrisTimeseriesError) as receipt_mismatch:
        build_webtris_timeseries(
            workspace,
            (
                WebtrisTimeseriesEvidence(
                    daily_acquisition=daily, quality_acquisition=drifted_receipt
                ),
            ),
            interval_filter=_filter(),
        )
    assert receipt_mismatch.value.code == "ACCEPTED_SNAPSHOT_MISMATCH"

    quality_replay = replayed.quality_replay
    assert quality_replay is not None
    quarantined = (
        workspace
        / "quarantine"
        / quality_replay.snapshot_id
        / "raw"
        / "quality"
        / "daily-quality.json"
    )
    stored = quarantined.read_bytes()
    flipped = stored.replace(b'"Quality": 89', b'"Quality": 98', 1)
    assert flipped != stored and len(flipped) == len(stored)
    quarantined.chmod(0o600)
    quarantined.write_bytes(flipped)
    with pytest.raises(WebtrisTimeseriesError) as replay_tamper:
        build_webtris_timeseries(workspace, (replayed,), interval_filter=_filter())
    assert replay_tamper.value.code == "QUARANTINE_REPLAY_INVALID"

    accepted = (
        workspace / "accepted" / quality.snapshot_id / "raw" / "quality" / "daily-quality.json"
    )
    accepted_bytes = accepted.read_bytes()
    accepted_flipped = accepted_bytes.replace(b'"Quality": 89', b'"Quality": 98', 1)
    assert accepted_flipped != accepted_bytes and len(accepted_flipped) == len(accepted_bytes)
    accepted.chmod(0o600)
    accepted.write_bytes(accepted_flipped)
    with pytest.raises(WebtrisTimeseriesError) as accepted_tamper:
        build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())
    assert accepted_tamper.value.code == "ACCEPTED_SNAPSHOT_INVALID"


def test_validator_bypassed_evidence_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    evidence = _acquired_evidence(workspace)
    daily = evidence.daily_acquisition
    assert daily is not None
    (tmp_path / "other").mkdir()
    other_workspace = initialise_v07_workspace(tmp_path / "other" / "workspace-v0.7").path
    other_responses = _responses()
    other_responses["quality"] = json.dumps(
        {"row_count": 1, "Qualities": [{"Date": "2026-03-02T00:00:00", "Quality": 89}]}
    ).encode("utf-8")
    other_day = acquire(
        other_workspace,
        make_request("daily_quality", report_date=date(2026, 3, 2)),
        other_responses,
    )
    bypassed = WebtrisTimeseriesEvidence.model_construct(
        daily_acquisition=daily,
        daily_replay=None,
        quality_acquisition=other_day,
        quality_replay=None,
    )

    with pytest.raises(WebtrisTimeseriesError) as excinfo:
        build_webtris_timeseries(workspace, (bypassed,), interval_filter=_filter())

    assert excinfo.value.code == "EVIDENCE_INVALID"


def test_multi_page_daily_evidence_preserves_page_lineage(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": paged(full_day_rows(), 48),
        "quality": _quality_payload(89),
    }
    daily = acquire(workspace, make_request("daily_report", page_size=48), responses)
    quality = acquire(workspace, make_request("daily_quality"), responses)
    evidence = WebtrisTimeseriesEvidence(daily_acquisition=daily, quality_acquisition=quality)

    result = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())

    assert result.inputs[0].daily_pages == 2
    assert result.counts.input_pages_total == 3
    assert result.counts.rows_admitted == 96
    assert result.rows[0].daily_page_number == 1
    assert result.rows[0].daily_member_path == "pages/page-0001.json"
    assert result.rows[50].daily_page_number == 2
    assert result.rows[50].daily_member_path == "pages/page-0002.json"
    rebuild = build_webtris_timeseries(workspace, (evidence,), interval_filter=_filter())
    assert rebuild.fingerprint() == result.fingerprint()


def test_canonical_site_order_is_numeric_not_lexicographic(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    site34 = _acquired_evidence(workspace)
    site5 = _acquired_evidence(workspace, site_id="5", volume="3", percent=66)

    result = build_webtris_timeseries(
        workspace, (site34, site5), interval_filter=_filter(site_ids=("5", "34"))
    )

    assert [item.site_id for item in result.inputs] == ["5", "34"]
    assert result.rows[0].site_id == "5"
    assert [item.site_id for item in build_webtris_chart_series(result)] == ["5", "34"]


def test_mixed_admitted_and_whole_day_excluded_inputs_reconcile(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    site34 = _acquired_evidence(workspace, missing={7})
    site35 = _acquired_evidence(workspace, site_id="35", volume="2", percent=77)

    result = build_webtris_timeseries(
        workspace,
        (site34, site35),
        interval_filter=_filter(site_ids=("34",), measurement_states=("observed",)),
    )

    assert result.result_state == "rows_available"
    assert result.counts.rows_admitted == 95
    assert result.counts.rows_excluded == 97
    reasons = {(item.reason, item.rows) for item in result.counts.exclusion_reasons}
    assert reasons == {("measurement_state_filtered", 1), ("site_not_selected", 96)}
    reloaded = WebtrisTimeseriesResult.model_validate_json(result.model_dump_json())
    assert reloaded == result


def test_chart_series_split_per_verified_site_name(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    first_day = _acquired_evidence(workspace)
    renamed_rows = _site_rows("1")
    for row in renamed_rows:
        row["Site Name"] = "SYN M56 renamed site"
        row["Report Date"] = "2026-03-02T00:00:00"
    renamed_responses: dict[str, dict[int, bytes] | bytes] = {
        "site": site_payload(),
        "daily": {1: daily_payload(renamed_rows, request_date="02032026")},
        "quality": _quality_payload(89),
    }
    renamed_daily = acquire(
        workspace,
        make_request(
            "daily_report",
            site_name="SYN M56 renamed site",
            report_date=date(2026, 3, 2),
        ),
        renamed_responses,
    )
    second_day = WebtrisTimeseriesEvidence(daily_acquisition=renamed_daily)

    result = build_webtris_timeseries(
        workspace,
        (first_day, second_day),
        interval_filter=_filter(end_date=date(2026, 3, 2)),
    )
    series = build_webtris_chart_series(result)

    assert [(item.site_id, item.site_name) for item in series] == [
        ("34", "SYN M56 renamed site"),
        ("34", SITE_NAME),
    ]
    assert all(len(item.points) == 96 for item in series)


def test_quality_stays_availability_never_accuracy(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with_quality = _acquired_evidence(workspace)
    result = build_webtris_timeseries(workspace, (with_quality,), interval_filter=_filter())

    input_item = result.inputs[0]
    assert input_item.availability_interpretation == "data_availability_percentage"
    assert input_item.sensor_accuracy_claim_available is False
    assert input_item.traffic_validity_claim_available is False
    input_payload = json.loads(input_item.model_dump_json())
    input_payload["sensor_accuracy_claim_available"] = True
    with pytest.raises(ValidationError):
        type(input_item).model_validate_json(json.dumps(input_payload))

    (tmp_path / "bare").mkdir()
    bare_workspace = initialise_v07_workspace(tmp_path / "bare" / "workspace-v0.7").path
    without_quality = _acquired_evidence(bare_workspace, with_quality=False)
    bare = build_webtris_timeseries(bare_workspace, (without_quality,), interval_filter=_filter())
    assert bare.rows[0].availability_percent is None
    assert bare.rows[0].quality_snapshot_id is None
    assert bare.rows[0].total_volume == result.rows[0].total_volume
