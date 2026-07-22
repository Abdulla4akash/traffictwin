"""Projection and complete-reconciliation evidence for the MAN-07 candidate."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.dft import (
    DftMemberRef,
    DftRawCountRecord,
    DftRoadLocation,
    DftVehicleClassCounts,
)
from traffictwin.integration.manchester.projection import (
    ManchesterProjectionError,
    ManchesterProjectionReport,
    ManchesterRoadObservation,
    dft_raw_count_observation,
    project_road_observations,
    webtris_daily_observation,
)
from traffictwin.integration.manchester.time_basis import (
    ManchesterTimeBasis,
    UtcInstantTime,
)
from traffictwin.integration.manchester.webtris import (
    MPH_TO_MPS,
    WebtrisDailyObservation,
    WebtrisLengthCounts,
    WebtrisMemberRef,
    WebtrisSpeedCounts,
)

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
DFT_SNAPSHOT = "dft_manchester-20260722T100000Z-abcdef012345"
WEBTRIS_SNAPSHOT = "webtris-20260722T100000Z-abcdef012345"
SYNTHETIC_SNAPSHOT = "synthetic_road-20260722T120000Z-abcdef012345"


def time_basis() -> ManchesterTimeBasis:
    return ManchesterTimeBasis(
        analysis_anchor_utc=NOW,
        window_start_utc=NOW,
        window_end_utc=NOW + timedelta(hours=1),
    )


def dft_record(*, synthetic: bool = False) -> DftRawCountRecord:
    return DftRawCountRecord(
        source=DftMemberRef(
            snapshot_id=DFT_SNAPSHOT,
            member_path="raw-counts/page-1.json",
            member_sha256="a" * 64,
            synthetic=synthetic,
        ),
        row_index=0,
        source_row_id=1001,
        count_point_id=12345,
        direction_of_travel="N",
        year=2004,
        count_date=date(2004, 5, 21),
        hour=12,
        region_id=5,
        local_authority_id=85,
        ons_code="E08000003",
        location=DftRoadLocation(
            road_name="Synthetic Way",
            road_category="PA",
            road_type="Major",
            latitude=Decimal("53.48"),
            longitude=Decimal("-2.24"),
        ),
        counts=DftVehicleClassCounts(
            pedal_cycles=5,
            two_wheeled_motor_vehicles=10,
            cars_and_taxis=100,
            buses_and_coaches=7,
            lgvs=20,
            hgvs_2_rigid_axle=4,
            hgvs_3_rigid_axle=3,
            hgvs_4_or_more_rigid_axle=2,
            hgvs_3_or_4_articulated_axle=1,
            hgvs_5_articulated_axle=1,
            hgvs_6_articulated_axle=1,
            all_hgvs=12,
            all_motor_vehicles=149,
        ),
    )


def webtris_record(
    *,
    missing: bool = False,
    synthetic: bool = False,
) -> WebtrisDailyObservation:
    source = WebtrisMemberRef(
        snapshot_id=WEBTRIS_SNAPSHOT,
        member_path="daily/page-1.json",
        member_sha256="b" * 64,
        member_role="daily_report",
        synthetic=synthetic,
    )
    if missing:
        return WebtrisDailyObservation(
            source=source,
            row_index=0,
            site_id="34",
            site_name="M56/8150A",
            report_date_raw="2026-03-01 00:00:00",
            report_date=date(2026, 3, 1),
            time_period_ending_raw="00:15:00",
            interval_index=0,
            measurement_state="missing",
            length_counts=WebtrisLengthCounts(),
            speed_counts=WebtrisSpeedCounts(),
            length_total_reconciled=None,
            speed_total_reconciled=None,
        )
    return WebtrisDailyObservation(
        source=source,
        row_index=0,
        site_id="34",
        site_name="M56/8150A",
        report_date_raw="2026-03-01 00:00:00",
        report_date=date(2026, 3, 1),
        time_period_ending_raw="00:15:00",
        interval_index=0,
        measurement_state="observed",
        length_counts=WebtrisLengthCounts(
            cm_0_520=10,
            cm_521_660=0,
            cm_661_1160=0,
            cm_1160_plus=0,
        ),
        speed_counts=WebtrisSpeedCounts(
            mph_0_10=10,
            mph_11_15=0,
            mph_16_20=0,
            mph_21_25=0,
            mph_26_30=0,
            mph_31_35=0,
            mph_36_40=0,
            mph_41_45=0,
            mph_46_50=0,
            mph_51_55=0,
            mph_56_60=0,
            mph_61_70=0,
            mph_71_80=0,
            mph_80_plus=0,
        ),
        average_speed_mph=Decimal("10"),
        average_speed_mps=Decimal("10") * MPH_TO_MPS,
        total_volume=10,
        length_total_reconciled=True,
        speed_total_reconciled=True,
    )


def synthetic_observation(
    *,
    source_fingerprint: str = "c" * 64,
    observed_at: datetime = NOW + timedelta(seconds=30),
    row: int = 1,
) -> ManchesterRoadObservation:
    return ManchesterRoadObservation(
        source="synthetic_utc_road",
        source_snapshot_id=SYNTHETIC_SNAPSHOT,
        source_member_path="synthetic/road.json",
        source_member_sha256="d" * 64,
        source_record_fingerprint=source_fingerprint,
        source_row=row,
        source_row_identity=f"synthetic:{row}",
        source_time=UtcInstantTime(observed_at_utc=observed_at),
        sensor_id=f"synthetic-sensor-{row}",
        geographic_scope="synthetic",
        count=12,
        average_speed_mps=Decimal("5"),
        original_average_speed=Decimal("5"),
        original_speed_unit="m/s",
        nominal_interval_seconds=60,
        location_label="Synthetic location",
        measurement_state="observed",
        quality_state="synthetic",
        synthetic=True,
    )


def test_dft_conversion_preserves_count_and_refuses_utc_projection() -> None:
    source = dft_record()
    observation = dft_raw_count_observation(source)
    report = project_road_observations((observation,), time_basis())

    assert observation.source_record_fingerprint == source.fingerprint()
    assert observation.count == 149
    assert observation.average_speed_mps is None
    assert observation.original_speed_unit == "unavailable"
    assert observation.source_time.kind == "local_clock_hour"
    assert report.status == "unavailable"
    assert report.counts.time_basis_exclusions == 1
    assert report.exclusions[0].reason == "undocumented_source_timezone_ga_dft_1"
    assert report.rows == ()


def test_webtris_conversion_preserves_exact_mph_and_refuses_utc_projection() -> None:
    source = webtris_record()
    observation = webtris_daily_observation(source)
    report = project_road_observations((observation,), time_basis())

    assert observation.source_record_fingerprint == source.fingerprint()
    assert observation.count == 10
    assert observation.original_average_speed == Decimal("10")
    assert observation.average_speed_mps == Decimal("4.47040")
    assert observation.nominal_interval_seconds == 900
    assert report.exclusions[0].reason == "undocumented_source_timezone_ga_wt_1"


def test_missing_measurement_has_an_explicit_primary_exclusion() -> None:
    observation = webtris_daily_observation(webtris_record(missing=True))
    report = project_road_observations((observation,), time_basis())
    exclusion = report.exclusions[0]

    assert exclusion.reason == "source_measurement_missing"
    assert exclusion.measurement_available is False
    assert exclusion.time_projection.reason == "undocumented_source_timezone_ga_wt_1"
    assert report.counts.missing_measurements == 1
    assert report.counts.time_basis_exclusions == 0


def test_documented_synthetic_utc_observation_projects_to_existing_schema() -> None:
    observation = synthetic_observation()
    report = project_road_observations((observation,), time_basis())
    row = report.rows[0]
    canonical = row.to_canonical_record()

    assert report.status == "available"
    assert report.counts.rows_admitted == 1
    assert row.timestamp_s == 30.0
    assert canonical.timestamp_s == 30.0
    assert canonical.sensor_id == "synthetic-sensor-1"
    assert canonical.count == 12
    assert canonical.average_speed_mps == 5.0
    assert report.canonical_schema_extended is False
    assert report.retrieval_clock_used is False


def test_mixed_admission_is_partial_and_completely_reconciled() -> None:
    admitted = synthetic_observation()
    excluded = dft_raw_count_observation(dft_record())
    report = project_road_observations((excluded, admitted), time_basis())

    assert report.status == "partial"
    assert report.counts.inputs_seen == 2
    assert report.counts.rows_admitted == 1
    assert report.counts.rows_excluded == 1
    assert len(report.input_observation_fingerprints) == 2
    assert len(report.source_record_fingerprints) == 2
    accounted = {
        report.rows[0].input_observation_fingerprint,
        report.exclusions[0].input_observation_fingerprint,
    }
    assert accounted == set(report.input_observation_fingerprints)


def test_half_open_window_excludes_end_boundary_without_fabrication() -> None:
    observation = synthetic_observation(observed_at=NOW + timedelta(hours=1))
    report = project_road_observations((observation,), time_basis())

    assert report.status == "unavailable"
    assert report.exclusions[0].reason == "outside_half_open_window"
    assert report.exclusions[0].fabricated_timestamp is False
    assert report.exclusions[0].time_projection.timestamp_s is None


def test_projection_is_independent_of_input_order() -> None:
    first = synthetic_observation(source_fingerprint="1" * 64, row=1)
    second = synthetic_observation(
        source_fingerprint="2" * 64,
        observed_at=NOW + timedelta(seconds=40),
        row=2,
    )

    forward = project_road_observations((first, second), time_basis())
    reverse = project_road_observations((second, first), time_basis())

    assert forward.fingerprint() == reverse.fingerprint()
    assert forward.input_set_fingerprint == reverse.input_set_fingerprint


def test_duplicate_inputs_and_source_records_are_refused() -> None:
    first = synthetic_observation()
    with pytest.raises(ManchesterProjectionError, match="duplicate source observations"):
        project_road_observations((first, first), time_basis())

    second = synthetic_observation(
        source_fingerprint=first.source_record_fingerprint,
        observed_at=NOW + timedelta(seconds=40),
        row=2,
    )
    with pytest.raises(ManchesterProjectionError, match="one source record"):
        project_road_observations((first, second), time_basis())


def test_empty_request_is_explicitly_unavailable_and_reconciled() -> None:
    report = project_road_observations((), time_basis())

    assert report.status == "unavailable"
    assert report.counts.inputs_seen == 0
    assert report.complete_reconciliation is True
    assert report.rows == ()
    assert report.exclusions == ()


def test_source_specific_models_reject_strengthened_semantics() -> None:
    dft = dft_raw_count_observation(dft_record())
    payload = dft.model_dump(mode="python")
    payload["average_speed_mps"] = Decimal("13")
    payload["original_average_speed"] = Decimal("13")
    payload["original_speed_unit"] = "m/s"
    with pytest.raises(ValidationError, match="unevidenced speed"):
        ManchesterRoadObservation.model_validate(payload)

    webtris = webtris_daily_observation(webtris_record())
    payload = webtris.model_dump(mode="python")
    payload["average_speed_mps"] = Decimal("99")
    with pytest.raises(ValidationError, match="exact mph conversion"):
        ManchesterRoadObservation.model_validate(payload)

    payload = webtris.model_dump(mode="python")
    payload["retrieval_time_used"] = True
    with pytest.raises(ValidationError):
        ManchesterRoadObservation.model_validate(payload)


def test_report_schema_rejects_broken_reconciliation_and_stronger_status() -> None:
    report = project_road_observations((synthetic_observation(),), time_basis())

    payload = report.model_dump(mode="python")
    payload["status"] = "partial"
    with pytest.raises(ValidationError, match="status must match"):
        ManchesterProjectionReport.model_validate(payload)

    payload = report.model_dump(mode="python")
    payload["input_set_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError, match="input-set fingerprint"):
        ManchesterProjectionReport.model_validate(payload)

    payload = report.model_dump(mode="python")
    payload["rows"] = ()
    with pytest.raises(ValidationError, match="account for every input"):
        ManchesterProjectionReport.model_validate(payload)

    payload = report.model_dump(mode="python")
    payload["rows"][0]["timestamp_s"] = 999.0
    with pytest.raises(ValidationError, match="timestamp must match"):
        ManchesterProjectionReport.model_validate(payload)
