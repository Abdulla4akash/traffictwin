"""Synthetic tests for the source-specific DfT historical survey view."""

from __future__ import annotations

import json
import socket
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

import traffictwin.integration.manchester.dft_survey_view as survey_view
from tests.unit.test_manchester_dft_acquisition import (
    acquire,
    count_point_row,
    envelope_bytes,
    make_request,
)
from traffictwin.integration.manchester.dft import (
    DftManchesterScope,
    DftMemberRef,
    DftRawCountParseReport,
    parse_dft_raw_counts,
)
from traffictwin.integration.manchester.dft_acquisition import DftAcquisitionResult
from traffictwin.integration.manchester.dft_survey_view import (
    DftSurveyView,
    DftSurveyViewError,
    DftSurveyViewQuery,
    build_dft_survey_view,
    build_dft_survey_view_from_accepted,
    build_dft_survey_view_from_snapshot,
    dft_survey_filter_options,
    dft_survey_filter_options_from_accepted,
    dft_survey_filter_options_from_snapshot,
    validate_dft_survey_view,
)
from traffictwin.integration.manchester.models import (
    ManchesterValidationState,
    sha256_hex,
)
from traffictwin.release.compatibility import initialise_v07_workspace

SNAPSHOT_ID = "dft_survey_view-20260723T120000Z-abcdef012345"


def _raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 1001,
        "count_point_id": 100,
        "direction_of_travel": "N",
        "year": 2025,
        "count_date": "2025-05-21",
        "hour": 8,
        "region_id": 5,
        "local_authority_id": 85,
        "road_name": "Synthetic Survey Road",
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
        "pedal_cycles": None,
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


def _report(*, rejected: bool = False) -> DftRawCountParseReport:
    rows = [
        _raw_row(),
        _raw_row(id=1002, hour=9, cars_and_taxis=None, all_motor_vehicles=145),
        _raw_row(
            id=1003,
            direction_of_travel="S",
            cars_and_taxis=80,
            all_motor_vehicles=129,
        ),
        _raw_row(
            id=1004,
            count_point_id=200,
            count_date="2025-06-03",
            cars_and_taxis=50,
            all_motor_vehicles=99,
        ),
    ]
    if rejected:
        rows.append(_raw_row(id=1005, count_point_id=300, local_authority_id=999))
    payload = json.dumps(
        {
            "current_page": 1,
            "per_page": len(rows),
            "total": len(rows),
            "last_page": 1,
            "from": 1,
            "to": len(rows),
            "path": "synthetic-fixture",
            "first_page_url": "synthetic-fixture",
            "last_page_url": "synthetic-fixture",
            "next_page_url": None,
            "prev_page_url": None,
            "links": [],
            "data": rows,
        }
    ).encode()
    source = DftMemberRef(
        snapshot_id=SNAPSHOT_ID,
        member_path="pages/page-1.json",
        member_sha256=sha256_hex(payload),
        synthetic=True,
    )
    return parse_dft_raw_counts(((source, payload),), DftManchesterScope())


def _query(
    report: DftRawCountParseReport | None = None,
    **overrides: object,
) -> DftSurveyViewQuery:
    source = _report() if report is None else report
    values: dict[str, object] = {
        "source_report_fingerprint": source.fingerprint(),
        "count_point_ids": (100,),
        "directions": ("N",),
        "count_dates": (date(2025, 5, 21),),
        "hours": (8, 9),
        "vehicle_class": "cars_and_taxis",
    }
    values.update(overrides)
    return DftSurveyViewQuery.model_validate(values)


def test_filter_options_preserve_evidenced_values_and_missingness() -> None:
    report = _report()
    assert report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    options = dft_survey_filter_options(report)

    assert options.source_report_fingerprint == report.fingerprint()
    assert options.source_record_count == 4
    assert options.count_point_ids == (100, 200)
    assert options.directions == ("N", "S")
    assert options.count_dates == (date(2025, 5, 21), date(2025, 6, 3))
    assert options.hours == (8, 9)
    assert "cars_and_taxis" in options.vehicle_classes_with_any_value
    assert "cars_and_taxis" not in options.vehicle_classes_complete
    assert "pedal_cycles" not in options.vehicle_classes_with_any_value
    assert options.utc_timestamps_available is False
    assert options.measured_speed_available is False


def test_accepted_snapshot_drives_filters_and_view_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    rows = [_raw_row(), _raw_row(id=1002, hour=9, cars_and_taxis=None)]
    acquisition = acquire(
        workspace,
        {1: envelope_bytes(rows, 1, 1, 2, 2)},
        make_request(page_size=2, accept_with_warnings=True),
    )
    assert isinstance(acquisition, DftAcquisitionResult)

    def refuse_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("accepted survey replay must not use the network")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    options = dft_survey_filter_options_from_accepted(workspace, acquisition)
    query = DftSurveyViewQuery(
        source_report_fingerprint=options.source_report_fingerprint,
        count_point_ids=(100,),
        directions=("N",),
        count_dates=(date(2025, 5, 21),),
        hours=(8, 9),
        vehicle_class="cars_and_taxis",
    )
    view = build_dft_survey_view_from_accepted(
        workspace,
        acquisition,
        query,
    )
    snapshot_options = dft_survey_filter_options_from_snapshot(
        workspace,
        acquisition.snapshot_id,
    )
    snapshot_view = build_dft_survey_view_from_snapshot(
        workspace,
        acquisition.snapshot_id,
        query,
    )

    assert options.source_record_count == 2
    assert snapshot_options == options
    assert snapshot_view == view
    assert view.counts.selected_records == 2
    assert view.counts.values_present == 1
    assert view.counts.values_missing == 1
    assert view.missing_filled_with_zero is False


def test_accepted_survey_view_refuses_non_raw_count_dataset(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    acquisition = acquire(
        workspace,
        {1: envelope_bytes([count_point_row()], 1, 1, 1, 1)},
        make_request("count_points"),
    )
    assert isinstance(acquisition, DftAcquisitionResult)

    with pytest.raises(DftSurveyViewError) as error:
        dft_survey_filter_options_from_accepted(workspace, acquisition)
    assert error.value.code == "DATASET_REFUSED"


def test_builds_exact_non_aggregated_local_clock_view() -> None:
    report = _report()
    view = build_dft_survey_view(report, _query(report))

    assert view.counts.source_records == 4
    assert view.counts.selected_records == 2
    assert view.counts.records_outside_selection == 2
    assert view.counts.values_present == 1
    assert view.counts.values_missing == 1
    assert [row.hour for row in view.rows] == [8, 9]
    assert [row.count for row in view.rows] == [100, None]
    assert [row.source_total_motor_vehicles for row in view.rows] == [149, 145]
    assert view.rows[1].selected_value_missing is True
    assert view.rows[1].missing_filled_with_zero is False
    assert all(row.observed_at_utc is None for row in view.rows)
    assert all(row.source_timezone is None for row in view.rows)
    assert all(row.interval_seconds is None for row in view.rows)
    assert all(row.measured_speed_mps is None for row in view.rows)
    assert view.continuous_time_series_available is False
    assert view.canonical_projection_available is False
    assert view.aggregation_performed is False
    assert validate_dft_survey_view(report, view) == view


def test_empty_cross_filter_combination_is_honest_not_zero_filled() -> None:
    report = _report()
    query = _query(report, directions=("S",), hours=(9,))
    view = build_dft_survey_view(report, query)

    assert view.rows == ()
    assert view.counts.selected_records == 0
    assert view.counts.records_outside_selection == 4
    assert view.counts.values_present == 0
    assert view.counts.values_missing == 0


def test_query_refuses_unsorted_duplicate_and_unknown_values() -> None:
    report = _report()
    with pytest.raises(ValidationError, match="sorted and unique"):
        _query(report, hours=(9, 8))
    with pytest.raises(ValidationError, match="sorted and unique"):
        _query(report, count_point_ids=(100, 100))

    with pytest.raises(DftSurveyViewError) as error:
        build_dft_survey_view(report, _query(report, count_point_ids=(999,)))
    assert error.value.code == "FILTER_VALUE_UNAVAILABLE"


def test_query_refuses_report_mismatch_and_unavailable_class() -> None:
    report = _report()
    with pytest.raises(DftSurveyViewError) as mismatch:
        build_dft_survey_view(
            report,
            _query(report, source_report_fingerprint="f" * 64),
        )
    assert mismatch.value.code == "SOURCE_REPORT_MISMATCH"

    with pytest.raises(DftSurveyViewError) as unavailable:
        build_dft_survey_view(report, _query(report, vehicle_class="pedal_cycles"))
    assert unavailable.value.code == "VEHICLE_CLASS_UNAVAILABLE"


def test_rejected_parser_report_cannot_be_filtered() -> None:
    report = _report(rejected=True)
    assert report.status is ManchesterValidationState.REJECTED
    with pytest.raises(DftSurveyViewError) as error:
        dft_survey_filter_options(report)
    assert error.value.code == "SOURCE_REPORT_REJECTED"


def test_internal_and_source_bound_tampering_fail_closed() -> None:
    report = _report()
    view = build_dft_survey_view(report, _query(report))
    payload = json.loads(view.model_dump_json())
    payload["rows"][0]["count"] = 999
    with pytest.raises(ValidationError, match="row fingerprints"):
        DftSurveyView.model_validate_json(json.dumps(payload))

    source_mismatch = view.model_copy(update={"source_status": ManchesterValidationState.ACCEPTED})
    with pytest.raises(DftSurveyViewError) as error:
        validate_dft_survey_view(report, source_mismatch)
    assert error.value.code == "VIEW_SOURCE_MISMATCH"

    invalid_counts = json.loads(view.model_dump_json())
    invalid_counts["source_parse_counts"]["records_accepted"] += 1
    with pytest.raises(ValidationError, match="source parse counts"):
        DftSurveyView.model_validate_json(json.dumps(invalid_counts))


def test_all_motor_vehicle_selection_retains_exact_source_total() -> None:
    report = _report()
    view = build_dft_survey_view(
        report,
        _query(report, hours=(8,), vehicle_class="all_motor_vehicles"),
    )
    assert len(view.rows) == 1
    assert view.rows[0].count == 149
    assert view.rows[0].source_total_motor_vehicles == 149


def test_fixed_output_bound_refuses_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report()
    monkeypatch.setattr(survey_view, "DFT_SURVEY_VIEW_MAX_ROWS", 1)
    with pytest.raises(DftSurveyViewError) as error:
        build_dft_survey_view(report, _query(report))
    assert error.value.code == "VIEW_TOO_LARGE"
