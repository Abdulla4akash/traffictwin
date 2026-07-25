"""Adversarial evidence for the real DfT temporal-profile candidate.

Every rule that could quietly invent data is attacked here: missing versus an
explicitly measured zero, the half-open interval boundaries, the local-hour to
simulation-second mapping, separation across site/direction/date, the
site-coherent deterministic split, the coverage refusal, AADF separation,
WebTRIS exclusion, and the no-fetch service boundary.

Fixtures are synthetic records built through the real ``dft.py`` models, so a
record that the parser could not produce cannot be tested against either.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.manchester.dft import (
    DftManchesterScope,
    DftMemberRef,
    DftRawCountRecord,
    DftRoadLocation,
    DftVehicleClassCounts,
    DirectionCode,
    RoadType,
)
from traffictwin.integration.manchester.dft_temporal_profile import (
    PROFILE_HOURS,
    SIMULATION_ORIGIN_LOCAL_HOUR,
    DftTemporalProfileError,
    DftTemporalProfilePolicy,
    ManchesterDftTemporalProfile,
    ProfileHourCell,
    ProfileSourceBinding,
    build_dft_temporal_profile,
    partition_for_site,
    profile_service_status,
    refuse_unadmitted_source,
    simulation_interval_for_hour,
    summarise_hours_present,
    write_profile_record,
)
from traffictwin.integration.manchester.models import ManchesterValidationState

runner = CliRunner()

POLICY = DftTemporalProfilePolicy()
SCOPE = DftManchesterScope()

#: The fixture snapshot these algorithm tests use. It is labelled synthetic
#: throughout, because that is what it is: forging a real lineage around
#: synthetic rows is exactly the thing the module now refuses.
FIXTURE_SNAPSHOT_ID = "dft_raw_counts-20260101T000000Z-000000000000"

SOURCE = DftMemberRef(
    snapshot_id=FIXTURE_SNAPSHOT_ID,
    member_path="pages/page-0001.json",
    member_sha256="0" * 64,
    synthetic=True,
)


def _binding(records_accepted: int) -> ProfileSourceBinding:
    """A labelled-synthetic binding whose accepted count matches the rows given."""

    return ProfileSourceBinding(
        snapshot_id=FIXTURE_SNAPSHOT_ID,
        raw_fingerprint="6" * 64,
        manifest_fingerprint="7" * 64,
        snapshot_receipt_fingerprint="8" * 64,
        parser_report_fingerprint="9" * 64,
        records_accepted=records_accepted,
        parser_status=ManchesterValidationState.ACCEPTED,
        synthetic=True,
        evidence_class="labelled_synthetic_fixture",
    )


def _build(
    records: list[DftRawCountRecord],
) -> ManchesterDftTemporalProfile:
    """Build over synthetic rows with a matching, honestly labelled binding."""

    return build_dft_temporal_profile(records, _binding(len(records)))


def _location(road_type: RoadType = "Major") -> DftRoadLocation:
    return DftRoadLocation(road_name="A56", road_category="PA", road_type=road_type)


def _row(
    *,
    site: int = 7950,
    direction: DirectionCode = "N",
    date: dt.date | None = None,
    hour: int = 7,
    all_motor_vehicles: int | None = 100,
    row_index: int = 0,
) -> DftRawCountRecord:
    survey_date = date if date is not None else dt.date(2025, 6, 11)
    return DftRawCountRecord(
        source=SOURCE,
        row_index=row_index,
        source_row_id=row_index,
        count_point_id=site,
        direction_of_travel=direction,
        year=survey_date.year,
        count_date=survey_date,
        hour=hour,
        region_id=1,
        local_authority_id=SCOPE.local_authority_id,
        ons_code=SCOPE.ons_code,
        location=_location(),
        counts=DftVehicleClassCounts(all_motor_vehicles=all_motor_vehicles),
    )


def _complete_series(
    *, site: int, direction: DirectionCode = "N", date: dt.date | None = None
) -> list[DftRawCountRecord]:
    """One site-direction-date with every declared hour observed."""

    return [
        _row(site=site, direction=direction, date=date, hour=hour, row_index=index)
        for index, hour in enumerate(PROFILE_HOURS)
    ]


class TestTheClockStaysLocal:
    def test_the_policy_never_offers_a_utc_instant(self) -> None:
        assert POLICY.time_basis == "local_clock_hour"
        assert POLICY.utc_projection_available is False
        assert POLICY.dft_hour_timezone_blocker == "GA-DFT-1"

    def test_seven_local_is_simulation_second_zero(self) -> None:
        assert simulation_interval_for_hour(SIMULATION_ORIGIN_LOCAL_HOUR) == (0, 3600)

    def test_every_declared_hour_maps_to_an_exact_half_open_interval(self) -> None:
        for offset, hour in enumerate(PROFILE_HOURS):
            start, end = simulation_interval_for_hour(hour)
            assert start == offset * 3600
            assert end == start + 3600

    def test_intervals_abut_without_gap_or_overlap(self) -> None:
        # Half-open means one hour's end is exactly the next hour's start.
        bounds = [simulation_interval_for_hour(hour) for hour in PROFILE_HOURS]
        for earlier, later in zip(bounds, bounds[1:], strict=False):
            assert earlier[1] == later[0]

    def test_the_window_covers_exactly_twelve_hours(self) -> None:
        assert len(PROFILE_HOURS) == 12
        assert simulation_interval_for_hour(PROFILE_HOURS[-1])[1] == 12 * 3600

    def test_an_hour_outside_the_window_is_refused_not_extrapolated(self) -> None:
        for hour in (0, 6, 19, 23):
            with pytest.raises(DftTemporalProfileError) as refused:
                simulation_interval_for_hour(hour)
            assert refused.value.code == "HOUR_OUTSIDE_DECLARED_WINDOW"

    def test_a_cell_may_not_misstate_its_own_interval(self) -> None:
        with pytest.raises(ValidationError, match="must follow from the local clock hour"):
            ProfileHourCell(
                local_clock_hour=8,
                simulation_second_start=0,
                simulation_second_end_exclusive=3600,
                state="observed",
                all_motor_vehicles=5,
            )

    def test_the_profile_declares_the_origin_as_a_convention(self) -> None:
        assert POLICY.simulation_origin_local_hour == 7
        assert POLICY.interval_convention == "half_open_start_inclusive_end_exclusive"


class TestMissingIsNotZero:
    def test_an_absent_hour_is_missing_and_carries_no_value(self) -> None:
        rows = [_row(hour=hour, row_index=index) for index, hour in enumerate((7, 8, 9))]
        profile = _build(rows)
        cells = {cell.local_clock_hour: cell for cell in profile.series[0].cells}
        assert cells[12].state == "missing_no_row"
        assert cells[12].all_motor_vehicles is None
        assert cells[12].measured_zero is False

    def test_an_explicit_zero_is_kept_as_a_measurement(self) -> None:
        # A road observed to carry nothing is a measurement; deleting it would
        # bias every mean computed downstream.
        rows = _complete_series(site=7950)
        rows[3] = _row(hour=PROFILE_HOURS[3], all_motor_vehicles=0, row_index=3)
        profile = _build(rows)
        cell = profile.series[0].cells[3]
        assert cell.state == "observed"
        assert cell.all_motor_vehicles == 0
        assert cell.measured_zero is True
        assert profile.measured_zero_cells == 1

    def test_a_null_value_is_an_exclusion_not_a_zero(self) -> None:
        rows = _complete_series(site=7950)
        rows[2] = _row(hour=PROFILE_HOURS[2], all_motor_vehicles=None, row_index=2)
        profile = _build(rows)
        cell = profile.series[0].cells[2]
        assert cell.state == "excluded_null_value"
        assert cell.all_motor_vehicles is None
        assert cell.measured_zero is False
        assert [item.reason for item in profile.exclusions] == ["null_all_motor_vehicles"]

    def test_a_missing_cell_may_not_be_given_a_value(self) -> None:
        with pytest.raises(ValidationError, match="missing is never zero"):
            ProfileHourCell(
                local_clock_hour=7,
                simulation_second_start=0,
                simulation_second_end_exclusive=3600,
                state="missing_no_row",
                all_motor_vehicles=0,
            )

    def test_an_unobserved_cell_may_not_claim_a_measured_zero(self) -> None:
        with pytest.raises(ValidationError, match="never measured as zero"):
            ProfileHourCell(
                local_clock_hour=7,
                simulation_second_start=0,
                simulation_second_end_exclusive=3600,
                state="missing_no_row",
                measured_zero=True,
            )

    def test_an_observed_cell_may_not_lie_about_being_zero(self) -> None:
        with pytest.raises(ValidationError, match="measured_zero must follow"):
            ProfileHourCell(
                local_clock_hour=7,
                simulation_second_start=0,
                simulation_second_end_exclusive=3600,
                state="observed",
                all_motor_vehicles=42,
                measured_zero=True,
            )

    def test_conflicting_duplicates_exclude_both_rather_than_choosing(self) -> None:
        rows = _complete_series(site=7950)
        rows.append(_row(hour=PROFILE_HOURS[0], all_motor_vehicles=999, row_index=99))
        profile = _build(rows)
        assert profile.series[0].cells[0].state == "excluded_conflicting_duplicate"
        assert profile.series[0].cells[0].all_motor_vehicles is None
        # Both conflicting rows are preserved in the ledger and countable;
        # neither is silently preferred over the other.
        assert [item.reason for item in profile.exclusions] == [
            "conflicting_duplicate_rows",
            "conflicting_duplicate_rows",
        ]
        assert profile.excluded_rows == 2
        assert profile.admitted_rows == len(rows) - 2

    def test_identical_duplicate_rows_collapse_without_excluding(self) -> None:
        rows = _complete_series(site=7950)
        rows.append(_row(hour=PROFILE_HOURS[0], all_motor_vehicles=100, row_index=99))
        profile = _build(rows)
        assert profile.series[0].cells[0].state == "observed"
        assert profile.exclusions == ()


class TestNothingIsFused:
    def test_two_directions_at_one_site_stay_separate_series(self) -> None:
        rows = _complete_series(site=7950, direction="N") + _complete_series(
            site=7950, direction="S"
        )
        profile = _build(rows)
        assert profile.series_total == 2
        assert {item.direction_of_travel for item in profile.series} == {"N", "S"}

    def test_two_dates_at_one_site_stay_separate_series(self) -> None:
        rows = _complete_series(site=7950, date=dt.date(2025, 6, 11)) + _complete_series(
            site=7950, date=dt.date(2024, 6, 12)
        )
        profile = _build(rows)
        assert profile.series_total == 2
        assert {item.count_date for item in profile.series} == {
            dt.date(2025, 6, 11),
            dt.date(2024, 6, 12),
        }

    def test_two_sites_stay_separate_series(self) -> None:
        rows = _complete_series(site=7950) + _complete_series(site=16536)
        profile = _build(rows)
        assert profile.series_total == 2
        assert profile.sites_total == 2

    def test_seasons_are_recorded_but_never_aggregated(self) -> None:
        rows = _complete_series(site=7950, date=dt.date(2025, 1, 15)) + _complete_series(
            site=7950, date=dt.date(2025, 7, 15)
        )
        profile = _build(rows)
        assert {item.season for item in profile.series} == {"winter", "summer"}
        assert profile.series_total == 2

    def test_the_policy_declares_every_non_fusion_rule(self) -> None:
        assert POLICY.fuses_across_sites is False
        assert POLICY.fuses_across_dates is False
        assert POLICY.fuses_across_seasons is False
        assert POLICY.fuses_across_directions is False
        assert POLICY.direction_preserved is True

    def test_a_forged_fusion_claim_is_refused(self) -> None:
        for field in ("fuses_across_sites", "fuses_across_directions", "missing_as_zero"):
            payload: dict[str, Any] = json.loads(POLICY.canonical_json())
            payload[field] = True
            with pytest.raises(ValidationError):
                DftTemporalProfilePolicy.model_validate_json(json.dumps(payload))


class TestTheSplitIsSiteCoherentAndDeterministic:
    def test_the_same_site_always_lands_in_the_same_partition(self) -> None:
        assert partition_for_site(7950) == partition_for_site(7950)

    def test_every_hour_direction_and_date_of_a_site_shares_its_partition(self) -> None:
        # Splitting by row would let one road appear on both sides, and a
        # held-out score would then be measuring memorisation.
        rows = (
            _complete_series(site=7950, direction="N")
            + _complete_series(site=7950, direction="S")
            + _complete_series(site=7950, date=dt.date(2024, 5, 1))
        )
        profile = _build(rows)
        partitions = {item.partition for item in profile.series if item.count_point_id == 7950}
        assert len(partitions) == 1

    def test_the_partition_is_reproducible_from_the_identity_alone(self) -> None:
        # No wall clock, no ordering, no run state enters the decision.
        first = [partition_for_site(site) for site in range(1000, 1100)]
        second = [partition_for_site(site) for site in reversed(range(1000, 1100))]
        assert first == list(reversed(second))

    def test_a_different_salt_produces_a_different_assignment(self) -> None:
        default = [partition_for_site(site) for site in range(1000, 1200)]
        other = [partition_for_site(site, salt="other-salt") for site in range(1000, 1200)]
        assert default != other

    def test_the_split_is_broadly_eighty_twenty_over_many_sites(self) -> None:
        sites = range(1, 5001)
        held = sum(1 for site in sites if partition_for_site(site) == "held_out")
        # The rule is a hash bucket, so the realised share is near 20% but never
        # promised to be exactly it; the published denominators are the truth.
        assert 0.17 < held / 5000 < 0.23

    def test_the_policy_names_the_split_unit_and_rule(self) -> None:
        assert POLICY.split_unit == "count_point_site"
        assert POLICY.split_rule == "sha256_site_identity_v1"
        assert POLICY.held_out_basis_points == 2000


class TestCoverageIsPublishedAndEnforced:
    def _both_sides(self) -> list[DftRawCountRecord]:
        development = next(
            site for site in range(1, 500) if partition_for_site(site) == "development"
        )
        held_out = next(site for site in range(1, 500) if partition_for_site(site) == "held_out")
        return _complete_series(site=development) + _complete_series(site=held_out)

    def test_complete_evidence_on_both_sides_is_admitted(self) -> None:
        profile = _build(self._both_sides())
        assert profile.admission == "admitted_candidate"
        assert profile.coverage == Decimal("1.000000")

    def test_denominators_are_published_per_partition(self) -> None:
        profile = _build(self._both_sides())
        for partition in ("development", "held_out"):
            summary = profile.partition_summary(partition)
            assert summary.expected_cells == 12
            assert summary.observed_cells == 12
            assert summary.coverage == Decimal("1.000000")
            assert summary.meets_minimum_coverage is True

    def test_a_partition_below_the_minimum_refuses_admission(self) -> None:
        rows = self._both_sides()
        # Strip one side down to 8 of 12 hours: 0.667, below 0.800.
        held_out = next(site for site in range(1, 500) if partition_for_site(site) == "held_out")
        rows = [
            row for row in rows if row.count_point_id != held_out or row.hour in PROFILE_HOURS[:8]
        ]
        profile = _build(rows)
        assert profile.partition_summary("held_out").coverage == Decimal("0.666667")
        assert profile.partition_summary("held_out").meets_minimum_coverage is False
        assert profile.admission == "not_admitted_insufficient_coverage"

    def test_an_empty_partition_refuses_admission(self) -> None:
        development = next(
            site for site in range(1, 500) if partition_for_site(site) == "development"
        )
        profile = _build(_complete_series(site=development))
        assert profile.partition_summary("held_out").series == 0
        assert profile.admission == "not_admitted_empty_partition"

    def test_coverage_above_the_minimum_is_admitted(self) -> None:
        # 10 of 12 hours is 0.833333, comfortably above the 0.800 minimum. The
        # exact-boundary case is covered separately by the 48/60 test.
        assert POLICY.minimum_partition_coverage == Decimal("0.800")
        rows = self._both_sides()
        held_out = next(site for site in range(1, 500) if partition_for_site(site) == "held_out")
        rows = [
            row for row in rows if row.count_point_id != held_out or row.hour in PROFILE_HOURS[:10]
        ]
        profile = _build(rows)
        assert profile.partition_summary("held_out").coverage == Decimal("0.833333")
        assert profile.admission == "admitted_candidate"

    def test_a_forged_admission_is_refused(self) -> None:
        profile = _build(self._both_sides())
        payload: dict[str, Any] = json.loads(profile.canonical_json())
        payload["admission"] = "not_admitted_insufficient_coverage"
        with pytest.raises(ValidationError, match="admission must follow"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_a_forged_coverage_is_refused(self) -> None:
        profile = _build(self._both_sides())
        payload: dict[str, Any] = json.loads(profile.canonical_json())
        payload["coverage"] = "1.000000"
        payload["observed_cells"] = payload["observed_cells"] - 1
        with pytest.raises(ValidationError):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_every_offered_row_is_accounted_for(self) -> None:
        rows = self._both_sides()
        rows.append(_row(site=7950, hour=3, row_index=500))
        profile = _build(rows)
        assert profile.offered_rows == len(rows)
        assert profile.admitted_rows + profile.excluded_rows == profile.offered_rows
        assert [item.reason for item in profile.exclusions] == ["hour_outside_declared_window"]


class TestOtherSourcesAreSeparated:
    def test_aadf_is_refused_as_a_profile_input(self) -> None:
        with pytest.raises(DftTemporalProfileError) as refused:
            refuse_unadmitted_source("dft_aadf")
        assert refused.value.code == "AADF_IS_NOT_A_SURVEY_HOUR"

    def test_webtris_is_excluded_with_its_open_blocker(self) -> None:
        with pytest.raises(DftTemporalProfileError) as refused:
            refuse_unadmitted_source("webtris")
        assert refused.value.code == "WEBTRIS_CLOCK_BASIS_UNRESOLVED"
        assert "GA-WT-1" in str(refused.value)

    def test_raw_counts_are_the_admitted_source(self) -> None:
        refuse_unadmitted_source("dft_raw_count")

    def test_an_unknown_source_is_refused(self) -> None:
        with pytest.raises(DftTemporalProfileError) as refused:
            refuse_unadmitted_source("bods")
        assert refused.value.code == "SOURCE_NOT_ADMITTED"

    def test_a_non_survey_evidence_kind_is_refused_by_the_builder(self) -> None:
        # Duck-typed AADF: the builder checks the evidence kind rather than
        # trusting the caller to pass the right family.
        class _NotASurveyHour:
            evidence_kind = "annual_average_daily_flow"
            time_basis = "date_only"
            count_point_id = 1
            ons_code = SCOPE.ons_code

        with pytest.raises(DftTemporalProfileError) as refused:
            build_dft_temporal_profile([_NotASurveyHour()], _binding(1))  # type: ignore[list-item]
        assert refused.value.code == "EVIDENCE_KIND_NOT_ADMITTED"

    def test_an_out_of_scope_authority_is_refused(self) -> None:
        class _Elsewhere:
            evidence_kind = "survey_hour_raw_count"
            time_basis = "local_clock_hour"
            count_point_id = 1
            ons_code = "E08000099"

        with pytest.raises(DftTemporalProfileError) as refused:
            build_dft_temporal_profile([_Elsewhere()], _binding(1))  # type: ignore[list-item]
        assert refused.value.code == "OUT_OF_SCOPE_LOCAL_AUTHORITY"

    def test_the_policy_declares_both_exclusions(self) -> None:
        assert POLICY.aadf_admitted is False
        assert POLICY.webtris_admitted is False
        assert POLICY.webtris_blocker == "GA-WT-1"

    def test_the_profile_never_claims_a_fusion(self) -> None:
        profile = _build(_complete_series(site=7950))
        assert profile.aadf_fused is False
        assert profile.webtris_included is False


class TestTheArtifactRefusesToOverclaim:
    def _profile(self) -> ManchesterDftTemporalProfile:
        return _build(_complete_series(site=7950))

    def test_the_capability_stays_planned(self) -> None:
        assert self._profile().capability_status == "planned"

    def test_no_utc_instant_is_offered(self) -> None:
        assert self._profile().utc_instant_available is False

    def test_calibration_and_demand_stay_unavailable(self) -> None:
        profile = self._profile()
        assert profile.calibration_use_available is False
        assert profile.sumo_demand_available is False
        assert profile.baseline_available is False

    def test_it_never_claims_supervisor_approval_or_validation(self) -> None:
        profile = self._profile()
        assert profile.supervisor_approved is False
        assert profile.scientifically_validated is False
        assert profile.exploratory_candidate_software_evidence is True

    def test_forged_overclaims_are_refused(self) -> None:
        for field in (
            "utc_instant_available",
            "calibration_use_available",
            "sumo_demand_available",
            "supervisor_approved",
            "scientifically_validated",
            "aadf_fused",
        ):
            payload: dict[str, Any] = json.loads(self._profile().canonical_json())
            payload[field] = True
            with pytest.raises(ValidationError):
                ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_a_forged_policy_fingerprint_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._profile().canonical_json())
        payload["policy_fingerprint"] = "0" * 64
        with pytest.raises(ValidationError, match="policy fingerprint does not match"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_the_profile_is_reproducible(self) -> None:
        rows = _complete_series(site=7950)
        assert _build(rows).canonical_json() == _build(rows).canonical_json()

    def test_row_order_does_not_change_the_profile(self) -> None:
        rows = _complete_series(site=7950) + _complete_series(site=16536)
        assert _build(rows).canonical_json() == _build(list(reversed(rows))).canonical_json()


class TestTheServiceNeverFetches:
    def test_the_status_is_structurally_offline(self) -> None:
        status = profile_service_status(_build(_complete_series(site=7950)))
        assert status.performs_network_access is False
        assert status.performs_acquisition is False

    def test_an_absent_profile_is_reported_not_invented(self) -> None:
        status = profile_service_status(None)
        assert status.profile_available is False
        assert status.admission is None
        assert status.coverage is None
        assert any(
            "No temporal profile has been built" in item for item in status.unavailable_reasons
        )

    def test_the_status_keeps_every_boundary_visible(self) -> None:
        status = profile_service_status(None)
        joined = " ".join(status.unavailable_reasons)
        assert "GA-DFT-1" in joined
        assert "GA-WT-1" in joined
        assert "AADF" in joined
        assert "simulation second zero" in joined

    def test_the_status_keeps_the_capability_planned(self) -> None:
        assert profile_service_status(None).capability_status == "planned"

    def test_a_forged_network_access_claim_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(profile_service_status(None).canonical_json())
        payload["performs_network_access"] = True
        with pytest.raises(ValidationError):
            type(profile_service_status(None)).model_validate_json(json.dumps(payload))


class TestWindowMeasurement:
    def test_hours_present_are_counted_not_assumed(self) -> None:
        rows = _complete_series(site=7950)
        counts = summarise_hours_present(rows)
        assert list(counts) == list(PROFILE_HOURS)
        assert set(counts.values()) == {1}


class TestRowAccountingLosesNothing:
    """Every offered row lands in exactly one bucket, and none disappears."""

    def test_a_null_beside_a_value_is_excluded_not_admitted(self) -> None:
        # The cell is observed, but that null row was still an input row that
        # contributed nothing; counting it as admitted would overstate the
        # evidence behind the profile.
        rows = _complete_series(site=7950)
        rows.append(_row(hour=PROFILE_HOURS[0], all_motor_vehicles=None, row_index=99))
        profile = _build(rows)
        assert profile.series[0].cells[0].state == "observed"
        assert profile.offered_rows == 13
        assert profile.admitted_rows == 12
        assert profile.excluded_rows == 1
        assert [item.reason for item in profile.exclusions] == ["null_all_motor_vehicles"]

    def test_the_ledger_length_is_the_excluded_row_count(self) -> None:
        rows = _complete_series(site=7950)
        rows.append(_row(hour=PROFILE_HOURS[0], all_motor_vehicles=None, row_index=90))
        rows.append(_row(hour=PROFILE_HOURS[1], all_motor_vehicles=None, row_index=91))
        rows.append(_row(hour=PROFILE_HOURS[1], all_motor_vehicles=None, row_index=92))
        rows.append(_row(site=7950, hour=3, row_index=93))
        profile = _build(rows)
        assert len(profile.exclusions) == profile.excluded_rows

    def test_a_wholly_null_cell_excludes_every_one_of_its_rows(self) -> None:
        rows = _complete_series(site=7950)
        rows[4] = _row(hour=PROFILE_HOURS[4], all_motor_vehicles=None, row_index=4)
        rows.append(_row(hour=PROFILE_HOURS[4], all_motor_vehicles=None, row_index=94))
        profile = _build(rows)
        assert profile.series[0].cells[4].state == "excluded_null_value"
        assert profile.excluded_rows == 2
        assert profile.admitted_rows == 11


class TestScopeNeedsBothIdentifiers:
    def test_a_wrong_ons_code_is_refused(self) -> None:
        class _WrongOns:
            evidence_kind = "survey_hour_raw_count"
            time_basis = "local_clock_hour"
            count_point_id = 1
            ons_code = "E08000099"
            local_authority_id = 85

        with pytest.raises(DftTemporalProfileError) as refused:
            build_dft_temporal_profile([_WrongOns()], _binding(1))  # type: ignore[list-item]
        assert refused.value.code == "OUT_OF_SCOPE_LOCAL_AUTHORITY"

    def test_a_wrong_local_authority_id_is_refused_even_with_the_right_ons_code(self) -> None:
        # The two identifiers are independent statements of one boundary; a row
        # agreeing with only one of them has a scope in doubt.
        class _WrongId:
            evidence_kind = "survey_hour_raw_count"
            time_basis = "local_clock_hour"
            count_point_id = 1
            ons_code = "E08000003"
            local_authority_id = 99

        with pytest.raises(DftTemporalProfileError) as refused:
            build_dft_temporal_profile([_WrongId()], _binding(1))  # type: ignore[list-item]
        assert refused.value.code == "OUT_OF_SCOPE_LOCAL_AUTHORITY"
        assert "local authority" in str(refused.value)

    def test_the_scope_binds_both_literals(self) -> None:
        assert POLICY.scope.ons_code == "E08000003"
        assert POLICY.scope.local_authority_id == 85


class TestCoverageGatingIsExact:
    def test_the_gate_uses_the_exact_ratio_not_the_displayed_value(self) -> None:
        # The loop below builds 801 complete series and 199 nine-hour ones:
        # 801*12 + 199*9 = 11,403 observed of 12,000, i.e. 0.950250. The point
        # is that the gate is evaluated on that exact integer ratio rather than
        # on the six-place figure the artifact publishes.
        development = next(
            site for site in range(1, 500) if partition_for_site(site) == "development"
        )
        held_out = next(site for site in range(1, 500) if partition_for_site(site) == "held_out")
        rows = _complete_series(site=development)
        # Held-out: 1000 series of 12 hours, drop 2401 cells to land just under.
        for index in range(1000):
            date = dt.date(2025, 1, 1) + dt.timedelta(days=index)
            hours = PROFILE_HOURS if index >= 801 else PROFILE_HOURS[:9]
            rows.extend(
                _row(site=held_out, date=date, hour=hour, row_index=1000 + index * 12 + offset)
                for offset, hour in enumerate(hours)
            )
        profile = _build(rows)
        summary = profile.partition_summary("held_out")
        exact_ok = summary.observed_cells * 1000 >= summary.expected_cells * 800
        assert summary.meets_minimum_coverage is exact_ok

    def test_a_partition_exactly_on_the_threshold_is_admitted(self) -> None:
        """Land on 48/60 = exactly 0.800 and require admission.

        Five held-out series: four complete, and a fifth brought into
        existence by a single explicit null row so its other eleven cells are
        missing. 48 observed of 60 expected is the threshold itself, which is
        the only case an inclusive gate and an exclusive one disagree about.
        """

        development = next(
            site for site in range(1, 500) if partition_for_site(site) == "development"
        )
        held_out = next(site for site in range(1, 500) if partition_for_site(site) == "held_out")
        rows = _complete_series(site=development)
        for index in range(4):
            date = dt.date(2025, 3, 1) + dt.timedelta(days=index)
            rows.extend(
                _row(site=held_out, date=date, hour=hour, row_index=2000 + index * 12 + offset)
                for offset, hour in enumerate(PROFILE_HOURS)
            )
        # The fifth series exists solely because of this null row.
        rows.append(
            _row(
                site=held_out,
                date=dt.date(2025, 3, 5),
                hour=PROFILE_HOURS[0],
                all_motor_vehicles=None,
                row_index=2999,
            )
        )
        profile = _build(rows)
        summary = profile.partition_summary("held_out")
        assert summary.series == 5
        assert summary.expected_cells == 60
        assert summary.observed_cells == 48
        assert summary.missing_cells == 11
        assert summary.excluded_cells == 1
        assert summary.coverage == Decimal("0.800000")
        assert summary.meets_minimum_coverage is True
        assert profile.admission == "admitted_candidate"

    def test_one_cell_below_the_threshold_refuses_admission(self) -> None:
        # 47/60 = 0.783333, just under: the neighbouring case must refuse.
        development = next(
            site for site in range(1, 500) if partition_for_site(site) == "development"
        )
        held_out = next(site for site in range(1, 500) if partition_for_site(site) == "held_out")
        rows = _complete_series(site=development)
        for index in range(4):
            date = dt.date(2025, 3, 1) + dt.timedelta(days=index)
            hours = PROFILE_HOURS if index < 3 else PROFILE_HOURS[:11]
            rows.extend(
                _row(site=held_out, date=date, hour=hour, row_index=2000 + index * 12 + offset)
                for offset, hour in enumerate(hours)
            )
        rows.append(
            _row(
                site=held_out,
                date=dt.date(2025, 3, 5),
                hour=PROFILE_HOURS[0],
                all_motor_vehicles=None,
                row_index=2999,
            )
        )
        profile = _build(rows)
        summary = profile.partition_summary("held_out")
        assert summary.observed_cells == 47
        assert summary.expected_cells == 60
        assert summary.meets_minimum_coverage is False
        assert profile.admission == "not_admitted_insufficient_coverage"


class TestSyntheticEvidenceCanNeverPassAsReal:
    """The one claim this module must never allow to be manufactured."""

    def test_a_synthetic_fixture_is_labelled_as_such_end_to_end(self) -> None:
        profile = _build(_complete_series(site=7950))
        assert profile.evidence_class == "labelled_synthetic_fixture"
        assert profile.source.evidence_class == "labelled_synthetic_fixture"
        assert profile.source.synthetic is True

    def test_a_binding_may_not_call_synthetic_rows_an_accepted_snapshot(self) -> None:
        with pytest.raises(ValidationError, match="evidence_class must follow"):
            ProfileSourceBinding(
                snapshot_id=FIXTURE_SNAPSHOT_ID,
                raw_fingerprint="6" * 64,
                manifest_fingerprint="7" * 64,
                snapshot_receipt_fingerprint="8" * 64,
                parser_report_fingerprint="9" * 64,
                records_accepted=12,
                parser_status=ManchesterValidationState.ACCEPTED,
                synthetic=True,
                evidence_class="accepted_real_snapshot",
            )

    def test_a_binding_may_not_call_real_rows_a_synthetic_fixture(self) -> None:
        with pytest.raises(ValidationError, match="evidence_class must follow"):
            ProfileSourceBinding(
                snapshot_id=FIXTURE_SNAPSHOT_ID,
                raw_fingerprint="6" * 64,
                manifest_fingerprint="7" * 64,
                snapshot_receipt_fingerprint="8" * 64,
                parser_report_fingerprint="9" * 64,
                records_accepted=12,
                parser_status=ManchesterValidationState.ACCEPTED,
                synthetic=False,
                evidence_class="labelled_synthetic_fixture",
            )

    def test_synthetic_rows_under_a_real_binding_are_refused(self) -> None:
        # The exact forgery: real-looking lineage pinned onto synthetic rows.
        real_looking = ProfileSourceBinding(
            snapshot_id=FIXTURE_SNAPSHOT_ID,
            raw_fingerprint="6" * 64,
            manifest_fingerprint="7" * 64,
            snapshot_receipt_fingerprint="8" * 64,
            parser_report_fingerprint="9" * 64,
            records_accepted=12,
            parser_status=ManchesterValidationState.ACCEPTED,
            synthetic=False,
            evidence_class="accepted_real_snapshot",
        )
        with pytest.raises(DftTemporalProfileError) as refused:
            build_dft_temporal_profile(_complete_series(site=7950), real_looking)
        assert refused.value.code == "ROW_EVIDENCE_CLASS_MISMATCH"

    def test_rows_from_another_snapshot_are_refused(self) -> None:
        elsewhere = ProfileSourceBinding(
            snapshot_id="dft_raw_counts-20990101T000000Z-ffffffffffff",
            raw_fingerprint="6" * 64,
            manifest_fingerprint="7" * 64,
            snapshot_receipt_fingerprint="8" * 64,
            parser_report_fingerprint="9" * 64,
            records_accepted=12,
            parser_status=ManchesterValidationState.ACCEPTED,
            synthetic=True,
            evidence_class="labelled_synthetic_fixture",
        )
        with pytest.raises(DftTemporalProfileError) as refused:
            build_dft_temporal_profile(_complete_series(site=7950), elsewhere)
        assert refused.value.code == "ROW_SNAPSHOT_MISMATCH"

    def test_a_binding_that_did_not_read_every_row_is_refused(self) -> None:
        # records_accepted must equal the rows offered, so a profile cannot
        # rest on a snapshot it only partly read.
        with pytest.raises(ValidationError, match="must equal the rows offered"):
            build_dft_temporal_profile(_complete_series(site=7950), _binding(39072))

    def test_the_profile_evidence_class_follows_its_source(self) -> None:
        profile = _build(_complete_series(site=7950))
        payload: dict[str, Any] = json.loads(profile.canonical_json())
        payload["evidence_class"] = "accepted_real_snapshot"
        with pytest.raises(ValidationError, match="evidence class must follow"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))


class TestTheSourceBindingMakesRealACheckableClaim:
    def test_the_profile_names_the_snapshot_it_rests_on(self) -> None:
        profile = _build(_complete_series(site=7950))
        assert profile.source.snapshot_id == FIXTURE_SNAPSHOT_ID
        assert profile.source.raw_fingerprint == "6" * 64
        assert profile.source.parser_report_fingerprint == "9" * 64

    def test_a_binding_may_not_claim_another_dataset(self) -> None:
        payload: dict[str, Any] = json.loads(_binding(12).canonical_json())
        payload["dataset"] = "aadf"
        with pytest.raises(ValidationError):
            ProfileSourceBinding.model_validate_json(json.dumps(payload))

    def test_a_rejected_parse_can_never_back_a_profile(self) -> None:
        # The rows behind a rejected report are not evidence of anything.
        with pytest.raises(ValidationError, match="rejected parse"):
            ProfileSourceBinding(
                snapshot_id=FIXTURE_SNAPSHOT_ID,
                raw_fingerprint="6" * 64,
                manifest_fingerprint="7" * 64,
                snapshot_receipt_fingerprint="8" * 64,
                parser_report_fingerprint="9" * 64,
                records_accepted=12,
                parser_status=ManchesterValidationState.REJECTED,
                synthetic=True,
                evidence_class="labelled_synthetic_fixture",
            )

    def test_an_accepted_with_warnings_parse_is_allowed(self) -> None:
        binding = ProfileSourceBinding(
            snapshot_id=FIXTURE_SNAPSHOT_ID,
            raw_fingerprint="6" * 64,
            manifest_fingerprint="7" * 64,
            snapshot_receipt_fingerprint="8" * 64,
            parser_report_fingerprint="9" * 64,
            records_accepted=12,
            parser_status=ManchesterValidationState.ACCEPTED_WITH_WARNINGS,
            synthetic=True,
            evidence_class="labelled_synthetic_fixture",
        )
        assert binding.parser_status == ManchesterValidationState.ACCEPTED_WITH_WARNINGS

    def test_the_input_fingerprint_binds_lineage_not_just_counts(self) -> None:
        # Two profiles with identical row totals but different source snapshots
        # must not fingerprint alike, or the digest would certify nothing.
        rows = _complete_series(site=7950)
        first = _build(rows)
        payload: dict[str, Any] = json.loads(_binding(len(rows)).canonical_json())
        payload["raw_fingerprint"] = "a" * 64
        second = build_dft_temporal_profile(
            rows, ProfileSourceBinding.model_validate_json(json.dumps(payload))
        )
        assert first.offered_rows == second.offered_rows
        assert first.fingerprint_of_inputs() != second.fingerprint_of_inputs()

    def test_the_input_fingerprint_binds_content(self) -> None:
        # Same lineage, different observations: the digest must move.
        rows = _complete_series(site=7950)
        changed = list(rows)
        changed[5] = _row(hour=PROFILE_HOURS[5], all_motor_vehicles=555, row_index=5)
        assert _build(rows).fingerprint_of_inputs() != _build(changed).fingerprint_of_inputs()

    def test_the_same_evidence_fingerprints_identically(self) -> None:
        rows = _complete_series(site=7950)
        assert _build(rows).fingerprint_of_inputs() == _build(rows).fingerprint_of_inputs()


class TestTheProfileCliRefusesCleanly:
    """Real CliRunner behaviour for the bounded profile command family."""

    def test_the_policy_command_needs_no_evidence(self) -> None:
        result = runner.invoke(app, ["integration", "manchester", "profile", "policy"])
        assert result.exit_code == 0
        assert "capability_status: planned" in result.stdout
        assert "utc_projection_available: false" in result.stdout
        assert "GA-WT-1" in result.stdout

    def test_an_invalid_format_is_refused(self) -> None:
        result = runner.invoke(
            app, ["integration", "manchester", "profile", "policy", "--format", "yaml"]
        )
        assert result.exit_code == 1

    def test_a_missing_workspace_fails_cleanly(self, tmp_path: Path) -> None:
        # open_real_raw_count_evidence raises a typed acquisition error, which
        # the command must catch rather than let escape as a traceback.
        result = runner.invoke(
            app,
            [
                "integration",
                "manchester",
                "profile",
                "build",
                str(tmp_path),
                "--snapshot-id",
                "dft_raw_counts-20260101T000000Z-000000000000",
            ],
        )
        assert result.exit_code == 1
        assert "Traceback" not in result.output

    def test_an_existing_output_is_not_silently_overwritten(self, tmp_path: Path) -> None:
        # A profile is evidence; replacing one silently would destroy a record
        # somebody may already have cited.
        target = tmp_path / "profile.json"
        target.write_text("existing evidence", encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "integration",
                "manchester",
                "profile",
                "build",
                str(tmp_path),
                "--snapshot-id",
                "whatever",
                "--output",
                str(target),
            ],
        )
        assert result.exit_code == 1
        assert target.read_text(encoding="utf-8") == "existing evidence"

    def test_inspect_refuses_a_symlink(self, tmp_path: Path) -> None:
        real = tmp_path / "real.json"
        real.write_text("{}", encoding="utf-8")
        link = tmp_path / "link.json"
        link.symlink_to(real)
        result = runner.invoke(app, ["integration", "manchester", "profile", "inspect", str(link)])
        assert result.exit_code == 1

    def test_inspect_refuses_an_oversized_artifact(self, tmp_path: Path) -> None:
        target = tmp_path / "huge.json"
        target.write_bytes(b"{" + b" " * 32)
        with mock.patch(
            "traffictwin.cli.MAX_PROFILE_ARTIFACT_BYTES",
            4,
        ):
            result = runner.invoke(
                app, ["integration", "manchester", "profile", "inspect", str(target)]
            )
        assert result.exit_code == 1

    def test_inspect_refuses_a_malformed_artifact(self, tmp_path: Path) -> None:
        target = tmp_path / "bad.json"
        target.write_text("{not json", encoding="utf-8")
        result = runner.invoke(
            app, ["integration", "manchester", "profile", "inspect", str(target)]
        )
        assert result.exit_code == 1
        assert "Traceback" not in result.output

    def test_inspect_reports_a_valid_profile_with_its_evidence_class(self, tmp_path: Path) -> None:
        profile = _build(_complete_series(site=7950))
        target = tmp_path / "profile.json"
        target.write_text(profile.canonical_json(), encoding="utf-8")
        result = runner.invoke(
            app, ["integration", "manchester", "profile", "inspect", str(target)]
        )
        assert result.exit_code == 0, result.output
        assert "evidence_class: labelled_synthetic_fixture" in result.stdout
        assert "performs_network_access: false" in result.stdout
        assert "capability_status: planned" in result.stdout


class TestAStoredArtifactCannotBeEditedIntoAgreement:
    """Published summaries are re-derived from the series, never trusted."""

    def _profile(self) -> ManchesterDftTemporalProfile:
        development = next(
            site for site in range(1, 500) if partition_for_site(site) == "development"
        )
        held_out = next(site for site in range(1, 500) if partition_for_site(site) == "held_out")
        rows = _complete_series(site=development) + _complete_series(site=held_out)
        return _build(rows)

    def test_a_flipped_threshold_flag_is_refused(self) -> None:
        # The most valuable single bit to forge: it turns a refusal into an
        # admission without touching a number.
        payload: dict[str, Any] = json.loads(self._profile().canonical_json())
        for summary in payload["partitions"]:
            summary["meets_minimum_coverage"] = False
        with pytest.raises(ValidationError):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_a_coherently_forged_partition_summary_is_refused(self) -> None:
        # Denominators and coverage moved together so every arithmetic check
        # inside the summary still passes; only re-derivation catches it.
        payload: dict[str, Any] = json.loads(self._profile().canonical_json())
        summary = payload["partitions"][0]
        summary["expected_cells"] = 24
        summary["observed_cells"] = 24
        summary["missing_cells"] = 0
        summary["excluded_cells"] = 0
        summary["coverage"] = "1.000000"
        with pytest.raises(ValidationError, match="does not match the one its own series produce"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_a_forged_series_partition_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._profile().canonical_json())
        for series in payload["series"]:
            series["partition"] = "development"
        with pytest.raises(ValidationError, match="partition must follow from its site identity"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_a_forged_series_season_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._profile().canonical_json())
        payload["series"][0]["season"] = "winter"
        with pytest.raises(ValidationError, match="season must follow from its survey date"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_a_forged_series_day_type_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._profile().canonical_json())
        payload["series"][0]["day_type"] = "sunday"
        with pytest.raises(ValidationError, match="day type must follow from its survey date"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_a_forged_site_total_is_refused(self) -> None:
        payload: dict[str, Any] = json.loads(self._profile().canonical_json())
        payload["sites_total"] = 99
        with pytest.raises(ValidationError, match="distinct sites present in the series"):
            ManchesterDftTemporalProfile.model_validate_json(json.dumps(payload))

    def test_an_honest_artifact_round_trips(self) -> None:
        profile = self._profile()
        reloaded = ManchesterDftTemporalProfile.model_validate_json(profile.canonical_json())
        assert reloaded.canonical_json() == profile.canonical_json()


class TestTheProfileOutputBoundary:
    """Writing a profile mirrors the connectivity record's guarantees."""

    def _profile(self) -> ManchesterDftTemporalProfile:
        return _build(_complete_series(site=7950))

    def test_a_valid_profile_writes_and_reads_back(self, tmp_path: Path) -> None:
        target = tmp_path / "profile.json"
        write_profile_record(target, self._profile())
        reloaded = ManchesterDftTemporalProfile.model_validate_json(
            target.read_text(encoding="utf-8")
        )
        assert reloaded.canonical_json() == self._profile().canonical_json()

    def test_writing_leaves_no_temporary_behind(self, tmp_path: Path) -> None:
        store = tmp_path / "store"
        store.mkdir()
        write_profile_record(store / "profile.json", self._profile())
        write_profile_record(store / "profile.json", self._profile())
        assert [item.name for item in store.iterdir()] == ["profile.json"]

    def test_a_symlink_output_is_refused(self, tmp_path: Path) -> None:
        real = tmp_path / "elsewhere.json"
        real.write_text("existing evidence", encoding="utf-8")
        link = tmp_path / "profile.json"
        link.symlink_to(real)
        with pytest.raises(DftTemporalProfileError) as refused:
            write_profile_record(link, self._profile())
        assert refused.value.code == "PROFILE_OUTPUT_SYMLINK"
        assert real.read_text(encoding="utf-8") == "existing evidence"

    def test_an_oversized_profile_is_refused_before_writing(self, tmp_path: Path) -> None:
        # A build that wrote past the bound would leave an artifact its own
        # `profile inspect` could never read back.
        store = tmp_path / "store"
        store.mkdir()
        with (
            mock.patch(
                "traffictwin.integration.manchester.dft_temporal_profile."
                "MAX_PROFILE_ARTIFACT_BYTES",
                32,
            ),
            pytest.raises(DftTemporalProfileError) as refused,
        ):
            write_profile_record(store / "profile.json", self._profile())
        assert refused.value.code == "PROFILE_ARTIFACT_OVERSIZED"
        assert list(store.iterdir()) == []

    def test_the_cli_refuses_to_overwrite_a_symlink_even_when_asked(self, tmp_path: Path) -> None:
        real = tmp_path / "elsewhere.json"
        real.write_text("existing evidence", encoding="utf-8")
        link = tmp_path / "profile.json"
        link.symlink_to(real)
        result = runner.invoke(
            app,
            [
                "integration",
                "manchester",
                "profile",
                "build",
                str(tmp_path),
                "--snapshot-id",
                FIXTURE_SNAPSHOT_ID,
                "--output",
                str(link),
                "--overwrite",
            ],
        )
        assert result.exit_code == 1
        assert real.read_text(encoding="utf-8") == "existing evidence"

    def test_overwrite_replaces_an_existing_record(self, tmp_path: Path) -> None:
        target = tmp_path / "profile.json"
        target.write_text("stale", encoding="utf-8")
        write_profile_record(target, self._profile())
        assert target.read_text(encoding="utf-8") != "stale"
