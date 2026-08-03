from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_bods_acquisition import (
    API_KEY,
    BOX,
    RAW_VEHICLE_REF,
    make_clock,
    make_transport,
    siri_xml,
)
from traffictwin.integration.manchester.bods_live import BodsLiveRefresh, refresh_bods_live_scene
from traffictwin.integration.manchester.bods_operational_trends import (
    BodsOperationalTrendError,
    build_bods_trend_window,
    build_bods_utc_day_rollup,
    failed_bods_operational_attempt,
    successful_bods_operational_attempt,
)
from traffictwin.release.compatibility import initialise_v07_workspace

ATTEMPTED = datetime(2026, 7, 22, 10, 0, 30, tzinfo=UTC)
TERMINAL = ATTEMPTED + timedelta(seconds=5)


def _refresh(tmp_path: Path) -> BodsLiveRefresh:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    calls: list[tuple[str, str, dict[str, str]]] = []
    with httpx.Client(transport=make_transport(siri_xml(), calls)) as client:
        return refresh_bods_live_scene(
            workspace,
            BOX,
            api_key=API_KEY,
            synthetic=True,
            http_client=client,
            utc_now=make_clock(),
        )


def test_success_aggregate_has_exact_counts_ages_and_no_identifiers(tmp_path: Path) -> None:
    refresh = _refresh(tmp_path)

    aggregate = successful_bods_operational_attempt(
        refresh,
        attempted_at_utc=ATTEMPTED,
        terminal_at_utc=TERMINAL,
        trigger="automatic",
    )

    assert aggregate.activities_seen == 2
    assert aggregate.records_accepted == 2
    assert aggregate.synthetic_records == 2
    assert aggregate.verified_bee_rows == 0
    assert aggregate.other_or_unknown_rows == 2
    assert aggregate.distinct_operator_count == 1
    assert aggregate.source_age.minimum_age_ms == 65_000
    assert aggregate.source_age.median_age_ms == 65_000
    assert aggregate.source_age.p95_age_ms == 65_000
    assert aggregate.source_age.negative_age_count == 0
    payload = aggregate.canonical_json()
    assert RAW_VEHICLE_REF not in payload
    assert "SYNOP" not in payload
    assert "vehicle_token" not in payload
    assert "latitude" not in payload
    assert aggregate.road_speed_available is False
    assert aggregate.complete_fleet_coverage_available is False


def test_clock_skew_and_repeated_source_time_cadence_are_explicit(tmp_path: Path) -> None:
    refresh = _refresh(tmp_path)
    skew_terminal = datetime(2026, 7, 22, 9, 59, 20, tzinfo=UTC)
    first = successful_bods_operational_attempt(
        refresh,
        attempted_at_utc=skew_terminal - timedelta(seconds=1),
        terminal_at_utc=skew_terminal,
        trigger="operator",
    )
    second = successful_bods_operational_attempt(
        refresh,
        attempted_at_utc=ATTEMPTED,
        terminal_at_utc=TERMINAL,
        trigger="automatic",
        previous_success=first,
    )

    assert first.source_age.negative_age_count == 2
    assert first.source_age.minimum_age_ms == -10_000
    assert second.previous_success_source_cadence_ms == 0


def test_failures_are_safe_zero_response_attempts() -> None:
    failed = failed_bods_operational_attempt(
        attempted_at_utc=ATTEMPTED,
        terminal_at_utc=TERMINAL,
        trigger="automatic",
        failure_code="secret provider detail",
        acquisition_contract_fingerprint="a" * 64,
    )

    assert failed.safe_failure_code == "UNCLASSIFIED_SAFE_FAILURE"
    assert failed.source_response_available is False
    assert failed.records_accepted == 0
    assert "secret provider detail" not in failed.canonical_json()


def test_window_and_day_rollup_keep_denominators_and_single_point_truth(tmp_path: Path) -> None:
    refresh = _refresh(tmp_path)
    success = successful_bods_operational_attempt(
        refresh,
        attempted_at_utc=ATTEMPTED,
        terminal_at_utc=TERMINAL,
        trigger="automatic",
    )
    failed = failed_bods_operational_attempt(
        attempted_at_utc=ATTEMPTED + timedelta(minutes=1),
        terminal_at_utc=TERMINAL + timedelta(minutes=1),
        trigger="automatic",
        failure_code="REQUEST_FAILED",
        acquisition_contract_fingerprint="a" * 64,
    )
    start = datetime(2026, 7, 22, tzinfo=UTC)
    end = start + timedelta(days=1)

    window = build_bods_trend_window(
        (failed, success),
        window_start_utc=start,
        window_end_utc=end,
        expected_automatic_attempts=1440,
    )
    day = build_bods_utc_day_rollup(
        (failed, success), date(2026, 7, 22), expected_automatic_attempts=1440
    )

    assert window.observed_attempts == 2
    assert window.succeeded == 1
    assert window.failed == 1
    assert window.missing_automatic_attempts == 1438
    assert window.trend_available is False
    assert window.failure_counts == (("REQUEST_FAILED", 1),)
    assert day.window == window
    assert len(day.attempt_fingerprints) == 2
    with pytest.raises(BodsOperationalTrendError, match="DUPLICATE_ATTEMPT"):
        build_bods_trend_window(
            (success, success),
            window_start_utc=start,
            window_end_utc=end,
            expected_automatic_attempts=1440,
        )


def test_response_and_membership_denominators_cannot_drift(tmp_path: Path) -> None:
    aggregate = successful_bods_operational_attempt(
        _refresh(tmp_path),
        attempted_at_utc=ATTEMPTED,
        terminal_at_utc=TERMINAL,
        trigger="automatic",
    )
    payload = aggregate.model_dump()
    payload["verified_bee_rows"] = 1

    with pytest.raises(ValidationError, match="membership counts"):
        type(aggregate).model_validate(payload)
