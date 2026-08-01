"""Bus prediction layer (platform slice 4, design §7 test list).

Deterministic synthetic aggregates with known climatology; no live network,
no raw BODS data, no producer surface. The properties asserted are the
reviewed design's honesty story: aggregate-only input gates, whole-local-date
chronological splitting, unsupported-ratio and interval-support refusals,
baseline comparisons with the publishable null, forecast labelling, the
cadence-only dependency refusal, and the verdict self-test on fit dates only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traffictwin.platform.bus_prediction import (
    ALL_TARGETS,
    TARGET_CONCURRENCY_MAX,
    TARGET_CONCURRENCY_MEDIAN,
    TARGET_PROGRESSION_SPEED,
    BuildRules,
    BusPredictionError,
    LoadedAggregate,
    evaluate_held_out,
    fit_bus_forecast,
    forecast_climatology,
    forecast_nowcast,
    load_activity_aggregates,
    readiness_report,
    verdict_self_test,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED_AT = "2026-08-01T20:00:00+00:00"
RULES = BuildRules(min_snapshots_per_session=2, min_interval_support_dates=5)


def _aggregate_payload(
    session_date: str,
    label: str,
    live_by_hour: dict[int, list[int]],
    *,
    speeds_by_hour: dict[int, tuple[float, int]] | None = None,
    snapshot_prefix: str | None = None,
) -> dict[str, object]:
    prefix = snapshot_prefix or f"{session_date.replace('-', '')}-{label}"
    per_snapshot = []
    index = 0
    for hour, values in sorted(live_by_hour.items()):
        for value in values:
            per_snapshot.append(
                {
                    "snapshot_id": f"bods_siri_vm-{prefix}-{index:04d}",
                    "hour_utc": hour,
                    "hour_local": hour,
                    "live_vehicle": value,
                }
            )
            index += 1
    progression = [
        {
            "hour_utc": hour,
            "hour_local": hour,
            "segment_count": segments,
            "speed_mps_median": speed,
            "speed_mps_p90": speed * 1.5,
            "vehicles_contributing": max(1, segments // 2),
        }
        for hour, (speed, segments) in sorted((speeds_by_hour or {}).items())
    ]
    return {
        "record_type": "bods_session_activity_aggregate",
        "schema_version": "1.0",
        "design_reference": "docs/platform/bus_prediction_design.md",
        "session_kind": "scheduled",
        "label": label,
        "session_date_local": session_date,
        "utc_offset_seconds_applied": 0,
        "timezone_note": "synthetic fixture; local == UTC",
        "schedule_digest": None,
        "snapshot_count": len(per_snapshot),
        "concurrency_source": "parser_live_vehicle",
        "per_snapshot_live_vehicle": per_snapshot,
        "progression_available": bool(progression),
        "progression_unavailable_reason": None if progression else "none in fixture",
        "hourly_progression": progression,
        "aggregates_only": True,
        "raw_identifiers_published": False,
        "bus_progression_only": True,
        "road_traffic_speed_available": False,
        "session_salt_discarded": True,
    }


def _write(tmp_path: Path, name: str, payload: dict[str, object]) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _load_days(
    tmp_path: Path,
    days: list[tuple[str, dict[int, list[int]], dict[int, tuple[float, int]] | None]],
) -> tuple[LoadedAggregate, ...]:
    paths = [
        _write(
            tmp_path,
            f"aggregate_{index}.json",
            _aggregate_payload(day, "window", live, speeds_by_hour=speeds),
        )
        for index, (day, live, speeds) in enumerate(days)
    ]
    return load_activity_aggregates(paths)


#: Mon 2026-08-03 .. Fri 2026-08-07 — five weekdays with a known climatology.
WEEKDAYS = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]


def _five_weekdays(tmp_path: Path) -> tuple[LoadedAggregate, ...]:
    days: list[tuple[str, dict[int, list[int]], dict[int, tuple[float, int]] | None]] = [
        (
            day,
            {5: [100 + offset, 102 + offset], 6: [200 + offset, 202 + offset]},
            {5: (4.0, 10), 6: (5.0, 10)},
        )
        for offset, day in enumerate(WEEKDAYS)
    ]
    return _load_days(tmp_path, days)


# --- the module is producer-independent --------------------------------------


def test_the_module_imports_nothing_producer_derived() -> None:
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "bus_prediction.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "vec_campaign",
        "vec_runner",
        "outcome_predictor",
        "ukfleettrain",
        "vec_env",
        "tos-data",
    ):
        assert forbidden not in source


# --- input gates -------------------------------------------------------------


def test_private_content_is_refused_by_name(tmp_path: Path) -> None:
    payload = _aggregate_payload("2026-08-03", "window", {5: [10, 11]})
    payload["timezone_note"] = "written to /Users/someone/private"
    path = _write(tmp_path, "private.json", payload)
    with pytest.raises(BusPredictionError) as excinfo:
        load_activity_aggregates([path])
    assert excinfo.value.code == "PRIVATE_CONTENT_REFUSED"
    identifier = _aggregate_payload("2026-08-03", "window", {5: [10, 11]})
    identifier["timezone_note"] = "carries a VehicleRef somewhere"
    identifier_path = _write(tmp_path, "identifier.json", identifier)
    with pytest.raises(BusPredictionError) as second:
        load_activity_aggregates([identifier_path])
    assert second.value.code == "PRIVATE_CONTENT_REFUSED"


def test_non_aggregate_schemas_are_refused(tmp_path: Path) -> None:
    payload = _aggregate_payload("2026-08-03", "window", {5: [10, 11]})
    payload["record_type"] = "something_else"
    path = _write(tmp_path, "wrong.json", payload)
    with pytest.raises(BusPredictionError) as excinfo:
        load_activity_aggregates([path])
    assert excinfo.value.code == "AGGREGATE_INVALID"


def test_duplicate_sessions_and_overlapping_snapshots_are_refused(
    tmp_path: Path,
) -> None:
    first = _write(
        tmp_path,
        "first.json",
        _aggregate_payload("2026-08-03", "window", {5: [10, 11]}),
    )
    twin = _write(
        tmp_path,
        "twin.json",
        _aggregate_payload("2026-08-03", "window", {6: [20, 21]}),
    )
    with pytest.raises(BusPredictionError) as duplicate:
        load_activity_aggregates([first, twin])
    assert duplicate.value.code == "DUPLICATE_SESSION"
    overlapping = _write(
        tmp_path,
        "overlap.json",
        _aggregate_payload(
            "2026-08-04",
            "other",
            {5: [10, 11]},
            snapshot_prefix="20260803-window",
        ),
    )
    with pytest.raises(BusPredictionError) as overlap:
        load_activity_aggregates([first, overlapping])
    assert overlap.value.code == "DUPLICATE_SESSION"


def test_thin_sessions_are_excluded_with_a_reason_not_fatally(tmp_path: Path) -> None:
    rules = BuildRules(min_snapshots_per_session=4, min_interval_support_dates=5)
    loaded = _load_days(
        tmp_path,
        [
            ("2026-08-03", {5: [10, 11, 12, 13]}, None),
            ("2026-08-04", {5: [10]}, None),
        ],
    )
    report = readiness_report(loaded, rules)
    assert report["sources_total"] == 2
    assert report["sources_eligible"] == 1
    exclusions = report["exclusions"]
    assert isinstance(exclusions, list)
    assert "minimum" in exclusions[0]["reason"]


# --- dataset keys are the DECLARED local date and hours ----------------------


def test_declared_local_dates_key_the_dataset_never_utc(tmp_path: Path) -> None:
    # Two sessions share UTC hours but declare different local service dates
    # (the DST/midnight shape): they must land in different date keys.
    saturday = _aggregate_payload("2026-08-01", "night", {23: [50, 52]})
    sunday = _aggregate_payload(
        "2026-08-02", "night_after", {23: [70, 72]}, snapshot_prefix="susession"
    )
    loaded = load_activity_aggregates(
        [_write(tmp_path, "sat.json", saturday), _write(tmp_path, "sun.json", sunday)]
    )
    report = readiness_report(loaded, RULES)
    dates = report["eligible_dates_by_day_type"]
    assert isinstance(dates, dict)
    assert dates["weekend"] == ["2026-08-01", "2026-08-02"]


# --- climatology, intervals, support -----------------------------------------


def test_climatology_reproduces_the_known_mean_with_support(tmp_path: Path) -> None:
    fit = fit_bus_forecast(_five_weekdays(tmp_path), RULES, generated_at_utc=GENERATED_AT)
    record = forecast_climatology(fit, TARGET_CONCURRENCY_MEDIAN, "weekday", 5, rules=RULES)
    # Medians per date are 101..105 -> mean 103.
    assert record.value == pytest.approx(103.0)
    assert record.support_dates == 5
    assert not record.insufficient_support
    assert record.interval_low is not None
    assert record.interval_high is not None
    assert record.value is not None
    assert record.interval_low <= record.value <= record.interval_high
    assert record.forecast is True
    assert record.evidence is False
    assert record.causal is False
    assert record.fit_digest


def test_thin_cells_report_insufficient_support_not_an_interval(
    tmp_path: Path,
) -> None:
    loaded = _load_days(
        tmp_path,
        [
            ("2026-08-03", {5: [100, 102]}, None),
            ("2026-08-04", {5: [104, 106]}, None),
        ],
    )
    fit = fit_bus_forecast(
        loaded, RULES, generated_at_utc=GENERATED_AT, targets=(TARGET_CONCURRENCY_MEDIAN,)
    )
    record = forecast_climatology(fit, TARGET_CONCURRENCY_MEDIAN, "weekday", 5, rules=RULES)
    assert record.value is not None
    assert record.insufficient_support
    assert record.interval_low is None
    empty = forecast_climatology(fit, TARGET_CONCURRENCY_MEDIAN, "weekend", 5, rules=RULES)
    assert empty.value is None
    assert empty.insufficient_support


# --- the nowcast blend and its refusals --------------------------------------


def test_nowcast_blends_and_respects_the_alpha_bounds(tmp_path: Path) -> None:
    fit = fit_bus_forecast(_five_weekdays(tmp_path), RULES, generated_at_utc=GENERATED_AT)
    alpha = fit.alpha_by_target[TARGET_CONCURRENCY_MEDIAN]
    assert alpha is not None
    assert 0.0 <= alpha <= 1.0
    record = forecast_nowcast(fit, TARGET_CONCURRENCY_MEDIAN, "weekday", 5, 101.0, rules=RULES)
    assert record.kind == "nowcast"
    assert record.hour_local == 6
    assert record.value is not None
    assert record.forecast is True
    assert record.evidence is False


def test_nowcast_refuses_midnight_unsupported_ratio_and_missing_cells(
    tmp_path: Path,
) -> None:
    loaded = _load_days(
        tmp_path,
        [
            ("2026-08-03", {5: [0, 0], 6: [10, 12], 23: [5, 6]}, None),
            ("2026-08-04", {5: [0, 0], 6: [11, 13], 23: [6, 7]}, None),
        ],
    )
    fit = fit_bus_forecast(
        loaded, RULES, generated_at_utc=GENERATED_AT, targets=(TARGET_CONCURRENCY_MEDIAN,)
    )
    midnight = forecast_nowcast(fit, TARGET_CONCURRENCY_MEDIAN, "weekday", 23, 6.0, rules=RULES)
    assert midnight.insufficient_support
    assert "midnight" in str(midnight.insufficient_reason)
    zero_denominator = forecast_nowcast(
        fit, TARGET_CONCURRENCY_MEDIAN, "weekday", 5, 0.0, rules=RULES
    )
    assert zero_denominator.insufficient_support
    assert "ratio" in str(zero_denominator.insufficient_reason)
    missing = forecast_nowcast(fit, TARGET_CONCURRENCY_MEDIAN, "weekend", 5, 10.0, rules=RULES)
    assert missing.insufficient_support


# --- the cadence-only dependency refusal -------------------------------------


def test_speed_fitting_refuses_when_only_cadence_artifacts_exist(
    tmp_path: Path,
) -> None:
    loaded = _load_days(
        tmp_path,
        [("2026-08-03", {5: [100, 102]}, None), ("2026-08-04", {5: [104, 106]}, None)],
    )
    with pytest.raises(BusPredictionError) as excinfo:
        fit_bus_forecast(loaded, RULES, generated_at_utc=GENERATED_AT)
    assert excinfo.value.code == "PROGRESSION_AGGREGATES_MISSING"
    fit = fit_bus_forecast(
        loaded,
        RULES,
        generated_at_utc=GENERATED_AT,
        targets=(TARGET_CONCURRENCY_MEDIAN, TARGET_CONCURRENCY_MAX),
    )
    assert TARGET_PROGRESSION_SPEED not in fit.targets


# --- chronological whole-date splitting --------------------------------------


def test_split_violations_and_date_overlap_refuse(tmp_path: Path) -> None:
    fit = fit_bus_forecast(_five_weekdays(tmp_path), RULES, generated_at_utc=GENERATED_AT)
    overlap = _load_days(
        tmp_path / "overlap",
        [(WEEKDAYS[-1], {5: [100, 102], 6: [200, 202]}, {5: (4.0, 10), 6: (5.0, 10)})],
    )
    with pytest.raises(BusPredictionError) as overlapping:
        evaluate_held_out(fit, overlap, RULES)
    assert overlapping.value.code == "DATE_OVERLAP"
    earlier = _load_days(
        tmp_path / "earlier",
        [("2026-08-01", {5: [90, 92], 6: [180, 182]}, {5: (4.0, 10), 6: (5.0, 10)})],
    )
    with pytest.raises(BusPredictionError) as violated:
        evaluate_held_out(fit, earlier, RULES)
    assert violated.value.code == "SPLIT_VIOLATION"


# --- baselines and the publishable null --------------------------------------


def test_held_out_reports_baselines_and_the_null_is_a_complete_outcome(
    tmp_path: Path,
) -> None:
    fit = fit_bus_forecast(
        _five_weekdays(tmp_path),
        RULES,
        generated_at_utc=GENERATED_AT,
        targets=(TARGET_CONCURRENCY_MEDIAN,),
    )
    held_out = _load_days(
        tmp_path / "held",
        [("2026-08-10", {5: [120, 122], 6: [240, 242]}, None)],
    )
    evaluation = evaluate_held_out(fit, held_out, RULES)
    assert evaluation.evidence is False
    assert evaluation.confirmatory is False
    assert evaluation.held_out_dates == ("2026-08-10",)
    cell = evaluation.cells[0]
    assert cell.support_pairs == 1
    assert cell.mae_blend >= 0.0
    assert cell.mae_persistence >= 0.0
    assert cell.mae_climatology >= 0.0
    verdict = evaluation.verdict_by_target[TARGET_CONCURRENCY_MEDIAN]
    assert verdict in {"BLEND_BEATS_PERSISTENCE", "NULL_PERSISTENCE_NOT_BEATEN"}
    assert "publishable" in evaluation.verdict_rule


# --- the verdict self-test runs on fit dates only ----------------------------


def test_verdict_self_test_passes_on_fit_dates_and_reports_thin_data(
    tmp_path: Path,
) -> None:
    outcome = verdict_self_test(
        _five_weekdays(tmp_path),
        RULES,
        generated_at_utc=GENERATED_AT,
        targets=(TARGET_CONCURRENCY_MEDIAN,),
    )
    assert outcome.passed
    assert outcome.pseudo_held_out_date == WEEKDAYS[-1]
    assert outcome.verdict_by_target
    thin = verdict_self_test(
        _load_days(tmp_path / "thin", [("2026-08-03", {5: [10, 11]}, None)]),
        RULES,
        generated_at_utc=GENERATED_AT,
        targets=(TARGET_CONCURRENCY_MEDIAN,),
    )
    assert not thin.passed
    assert "two distinct" in thin.detail


# --- readiness honesty -------------------------------------------------------


def test_readiness_counts_dates_not_wall_clock_and_names_the_speed_gap(
    tmp_path: Path,
) -> None:
    loaded = _load_days(
        tmp_path,
        [("2026-08-03", {5: [100, 102]}, None), ("2026-08-08", {5: [50, 52]}, None)],
    )
    report = readiness_report(loaded, RULES)
    dates = report["eligible_dates_by_day_type"]
    assert isinstance(dates, dict)
    assert dates["weekday"] == ["2026-08-03"]
    assert dates["weekend"] == ["2026-08-08"]
    assert report["progression_target_available"] is False
    note = report["progression_note"]
    assert isinstance(note, str)
    assert "cadence-era" in note
    honesty = report["honesty_note"]
    assert isinstance(honesty, str)
    assert "never wall-clock" in honesty


def test_all_targets_constant_matches_the_design() -> None:
    assert ALL_TARGETS == (
        TARGET_CONCURRENCY_MEDIAN,
        TARGET_CONCURRENCY_MAX,
        TARGET_PROGRESSION_SPEED,
    )
