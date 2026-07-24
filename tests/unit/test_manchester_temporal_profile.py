"""Tests for the deterministic MAN-09 temporal-profile foundation."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, getcontext, localcontext

import pytest

from traffictwin.integration.manchester.temporal_profile import (
    APPROVED_PRODUCTION_PROFILE_POLICY_FINGERPRINTS,
    DeclaredExcludedDate,
    ManchesterTemporalProfileError,
    ManchesterTemporalProfileReport,
    TemporalProfileObservation,
    TemporalProfilePolicy,
    build_temporal_profile,
    day_type_for,
    season_for,
)

_SNAPSHOT = "a" * 64
_PARSER = "b" * 64


def _policy(**overrides: object) -> TemporalProfilePolicy:
    payload: dict[str, object] = {
        "policy_label": "synthetic-dev-profile",
        "source": "synthetic_utc_road",
        "measure": "vehicle_count",
        "unit": "vehicles_per_interval",
        "time_basis": "utc",
        "season_rule": "none",
        "window_start_date": dt.date(2026, 3, 2),
        "window_end_date": dt.date(2026, 3, 15),
        "expected_slot_labels": ("07:00", "08:00"),
        "minimum_cell_observations": 1,
    }
    payload.update(overrides)
    return TemporalProfilePolicy.model_validate(payload)


def _observation(
    *,
    record_id: str = "row-1",
    date: dt.date = dt.date(2026, 3, 2),
    slot: str = "07:00",
    value: Decimal | None = Decimal("10"),
) -> TemporalProfileObservation:
    return TemporalProfileObservation(
        source="synthetic_utc_road",
        source_record_id=record_id,
        source_date=date,
        slot_label=slot,
        measure="vehicle_count",
        unit="vehicles_per_interval",
        value=value,
        snapshot_fingerprint=_SNAPSHOT,
        parser_report_fingerprint=_PARSER,
    )


def test_day_type_and_season_rules_are_exact() -> None:
    assert day_type_for(dt.date(2026, 3, 2)) == "weekday"  # Monday
    assert day_type_for(dt.date(2026, 3, 7)) == "saturday"
    assert day_type_for(dt.date(2026, 3, 8)) == "sunday"
    assert season_for(dt.date(2026, 1, 15), "meteorological_month_v1") == "winter"
    assert season_for(dt.date(2026, 12, 1), "meteorological_month_v1") == "winter"
    assert season_for(dt.date(2026, 7, 24), "meteorological_month_v1") == "summer"
    assert season_for(dt.date(2026, 7, 24), "none") == "all_year"


def test_missing_cells_stay_visible_and_never_become_zero() -> None:
    report = build_temporal_profile(_policy(), [_observation()])

    # 14-day window covers weekday, saturday, and sunday; two slots each.
    assert len(report.cells) == 6
    states = report.cells_by_state()
    assert states["available"] == 1
    assert states["no_observations"] == 5
    empty = [cell for cell in report.cells if cell.state == "no_observations"]
    assert all(cell.mean_value is None for cell in empty)
    assert all(cell.observation_count == 0 for cell in empty)
    available = next(cell for cell in report.cells if cell.state == "available")
    assert available.mean_value == Decimal("10.000")
    assert available.contributing_dates == (dt.date(2026, 3, 2),)
    assert report.policy.missing_as_zero is False
    assert report.policy.interpolation == "unavailable"


def test_mean_min_max_are_deterministic_decimals() -> None:
    rows = [
        _observation(record_id="row-1", value=Decimal("10")),
        _observation(record_id="row-2", value=Decimal("11")),
        _observation(record_id="row-3", value=Decimal("14")),
    ]
    report = build_temporal_profile(_policy(), rows)

    cell = next(cell for cell in report.cells if cell.state == "available")
    assert cell.observation_count == 3
    assert cell.mean_value == Decimal("11.667")
    assert cell.minimum_value == Decimal("10")
    assert cell.maximum_value == Decimal("14")


def test_ambient_decimal_context_cannot_change_output() -> None:
    rows = [
        _observation(record_id="row-1", value=Decimal("10")),
        _observation(record_id="row-2", value=Decimal("11")),
        _observation(record_id="row-3", value=Decimal("14")),
    ]
    with localcontext() as context:
        context.prec = 2
        report = build_temporal_profile(_policy(), rows)
    assert getcontext().prec != 2
    cell = next(cell for cell in report.cells if cell.state == "available")
    assert cell.mean_value == Decimal("11.667")


def test_null_values_are_retained_as_typed_exclusions_not_zero() -> None:
    report = build_temporal_profile(
        _policy(), [_observation(value=None), _observation(record_id="row-2")]
    )

    assert report.admitted_observation_count == 1
    reasons = [item.reason for item in report.excluded_observations]
    assert reasons == ["null_value_retained"]
    assert report.excluded_observations[0].observation.value is None


def test_declared_excluded_dates_are_never_inferred_and_stay_typed() -> None:
    policy = _policy(
        declared_excluded_dates=(
            DeclaredExcludedDate(date=dt.date(2026, 3, 2), reason_label="declared-event-day"),
        )
    )
    report = build_temporal_profile(policy, [_observation()])

    assert report.admitted_observation_count == 0
    assert [item.reason for item in report.excluded_observations] == ["declared_excluded_date"]
    assert policy.holiday_inference == "unavailable"


def test_window_and_slot_membership_are_exact() -> None:
    report = build_temporal_profile(
        _policy(),
        [
            _observation(record_id="row-1", date=dt.date(2026, 3, 1)),
            _observation(record_id="row-2", slot="09:00"),
            _observation(record_id="row-3"),
        ],
    )

    reasons = sorted(item.reason for item in report.excluded_observations)
    assert reasons == ["outside_analysis_window", "unknown_slot_label"]
    assert report.admitted_observation_count == 1


def test_identical_duplicates_collapse_and_conflicts_exclude_both() -> None:
    identical = [_observation(), _observation()]
    conflicting = [
        _observation(record_id="row-2", value=Decimal("5")),
        _observation(record_id="row-2", value=Decimal("6")),
    ]
    report = build_temporal_profile(_policy(), identical + conflicting)

    assert report.collapsed_duplicate_count == 1
    assert report.admitted_observation_count == 1
    conflict_rows = [
        item for item in report.excluded_observations if item.reason == "conflicting_duplicate_rows"
    ]
    assert len(conflict_rows) == 2
    assert report.offered_observation_count == 4


def test_insufficient_cells_publish_counts_but_no_values() -> None:
    policy = _policy(minimum_cell_observations=2)
    report = build_temporal_profile(policy, [_observation()])

    cell = next(cell for cell in report.cells if cell.observation_count == 1)
    assert cell.state == "insufficient_observations"
    assert cell.mean_value is None
    assert cell.contributing_dates == (dt.date(2026, 3, 2),)


def test_seasonal_rule_partitions_cells_by_window_calendar() -> None:
    policy = _policy(
        season_rule="meteorological_month_v1",
        window_start_date=dt.date(2026, 2, 27),
        window_end_date=dt.date(2026, 3, 2),
    )
    report = build_temporal_profile(policy, [_observation()])

    keys = {(cell.season, cell.day_type) for cell in report.cells}
    assert keys == {
        ("winter", "weekday"),
        ("winter", "saturday"),
        ("spring", "sunday"),
        ("spring", "weekday"),
    }


def test_source_clock_semantics_are_structural() -> None:
    with pytest.raises(ValueError, match="structural source clock semantics"):
        _policy(source="dft_raw_count", time_basis="utc")
    dft_policy = _policy(source="dft_raw_count", time_basis="source_local_clock_undeclared")
    assert dft_policy.time_basis == "source_local_clock_undeclared"


def test_production_sources_stay_not_admitted_and_registry_is_empty() -> None:
    assert not APPROVED_PRODUCTION_PROFILE_POLICY_FINGERPRINTS
    policy = _policy(source="webtris_daily", time_basis="source_local_clock_undeclared")
    row = _observation().model_copy(update={"source": "webtris_daily"})
    report = build_temporal_profile(policy, [TemporalProfileObservation.model_validate(row)])

    assert report.admission == "not_admitted_production_unapproved"
    assert report.utc_projection_available is False
    assert report.calibration_use_available is False
    assert report.sumo_demand_available is False
    assert report.baseline_available is False


def test_synthetic_admission_and_structural_negatives() -> None:
    report = build_temporal_profile(_policy(), [_observation()])

    assert report.admission == "synthetic_development_inputs"
    assert report.capability_status == "planned"
    assert report.utc_projection_available is True
    assert report.calibration_use_available is False
    assert report.sumo_demand_available is False
    assert report.baseline_available is False


def test_source_and_measure_mismatches_are_typed_refusals() -> None:
    policy = _policy()
    webtris_row = TemporalProfileObservation.model_validate(
        _observation().model_copy(update={"source": "webtris_daily"})
    )
    with pytest.raises(ManchesterTemporalProfileError, match="SOURCE_MISMATCH"):
        build_temporal_profile(policy, [webtris_row])
    speed_policy = _policy(measure="average_speed_mps", unit="m/s")
    with pytest.raises(ManchesterTemporalProfileError, match="MEASURE_MISMATCH"):
        build_temporal_profile(speed_policy, [_observation()])


def test_reload_is_re_derived_and_tamper_evident() -> None:
    import json

    report = build_temporal_profile(_policy(), [_observation()])
    payload = report.model_dump(mode="json")

    reloaded = ManchesterTemporalProfileReport.model_validate_json(report.model_dump_json())
    assert reloaded.fingerprint() == report.fingerprint()

    tampered_cells = dict(payload)
    tampered_cells["cells"] = [
        {**cell, "mean_value": "999.000"} if cell["state"] == "available" else cell
        for cell in payload["cells"]
    ]
    with pytest.raises(ValueError, match="do not re-derive"):
        ManchesterTemporalProfileReport.model_validate_json(json.dumps(tampered_cells))

    tampered_admission = dict(payload)
    tampered_admission["admitted_observations"] = [
        {**row, "value": None} for row in payload["admitted_observations"]
    ]
    with pytest.raises(ValueError, match="fails policy admission|do not re-derive"):
        ManchesterTemporalProfileReport.model_validate_json(json.dumps(tampered_admission))


def test_policy_grid_and_window_bounds_fail_closed() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        _policy(window_end_date=dt.date(2026, 3, 1))
    with pytest.raises(ValueError, match="exceeds"):
        _policy(window_end_date=dt.date(2028, 1, 1))
    with pytest.raises(ValueError, match="sorted and unique"):
        _policy(expected_slot_labels=("08:00", "07:00"))
    with pytest.raises(ValueError, match="outside window"):
        _policy(
            declared_excluded_dates=(
                DeclaredExcludedDate(date=dt.date(2026, 4, 1), reason_label="declared-event"),
            )
        )
    with pytest.raises(ManchesterTemporalProfileError, match="OBSERVATIONS_OVERSIZED"):
        build_temporal_profile(
            _policy(),
            [_observation(record_id=f"row-{index}") for index in range(50_001)],
        )


def test_reload_refuses_fabricated_conflicting_exclusion() -> None:
    """A never-offered row marked conflicting is refused (single-row group)."""

    import json as _json

    report = build_temporal_profile(_policy(), [_observation()])
    payload = report.model_dump(mode="json")
    fake = _observation(record_id="synthetic:ghost", value=Decimal("7")).model_dump(mode="json")
    payload["excluded_observations"] = [
        {"reason": "conflicting_duplicate_rows", "observation": fake}
    ]
    payload["excluded_observation_count"] = 1
    payload["offered_observation_count"] = (
        payload["admitted_observation_count"] + 1 + payload["collapsed_duplicate_count"]
    )
    with pytest.raises(ValueError, match="at least two offered rows|do not re-derive"):
        ManchesterTemporalProfileReport.model_validate_json(_json.dumps(payload))


def test_reload_refuses_admitted_and_excluded_overlap() -> None:
    """The same observation cannot appear in both partitions."""

    import json as _json

    report = build_temporal_profile(_policy(), [_observation()])
    payload = report.model_dump(mode="json")
    admitted = payload["admitted_observations"][0]
    payload["excluded_observations"] = [
        {"reason": "null_value_retained", "observation": {**admitted, "value": None}}
    ]
    payload["excluded_observation_count"] = 1
    payload["offered_observation_count"] = (
        payload["admitted_observation_count"] + 1 + payload["collapsed_duplicate_count"]
    )
    with pytest.raises(ValueError, match="both admitted and excluded|do not re-derive"):
        ManchesterTemporalProfileReport.model_validate_json(_json.dumps(payload))


def test_reload_refuses_removed_duplicate_identical_reason() -> None:
    """The dead duplicate_identical_row reason is no longer a valid enum value."""

    import json as _json

    report = build_temporal_profile(_policy(), [_observation(value=None)])
    payload = report.model_dump(mode="json")
    payload["excluded_observations"][0]["reason"] = "duplicate_identical_row"
    with pytest.raises(ValueError):
        ManchesterTemporalProfileReport.model_validate_json(_json.dumps(payload))


def test_genuine_conflict_group_still_reloads() -> None:
    """A real two-form conflict group round-trips through validation."""

    import json as _json

    conflicting = [
        _observation(record_id="synthetic:c", value=Decimal("5")),
        _observation(record_id="synthetic:c", value=Decimal("6")),
    ]
    report = build_temporal_profile(_policy(), [*conflicting, _observation(record_id="ok")])
    assert any(item.reason == "conflicting_duplicate_rows" for item in report.excluded_observations)
    reloaded = ManchesterTemporalProfileReport.model_validate_json(
        _json.dumps(report.model_dump(mode="json"))
    )
    assert reloaded.fingerprint() == report.fingerprint()
