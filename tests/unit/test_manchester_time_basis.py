"""Deterministic UTC, refusal, and DST evidence for MAN-07 time primitives."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.time_basis import (
    DateOnlyTime,
    LocalClockHourTime,
    ManchesterTimeBasis,
    ManchesterTimeError,
    ManchesterTimeProjection,
    SimulationClockTime,
    UndeclaredSourceStringTime,
    UtcInstantTime,
    project_source_time,
    resolve_london_local,
    to_london_display,
)


def basis(
    start: datetime = datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    end: datetime = datetime(2026, 7, 22, 13, 0, tzinfo=UTC),
) -> ManchesterTimeBasis:
    return ManchesterTimeBasis(
        analysis_anchor_utc=start,
        window_start_utc=start,
        window_end_utc=end,
    )


def test_utc_instant_projects_to_exact_relative_seconds() -> None:
    window = basis()
    source = UtcInstantTime(observed_at_utc=datetime(2026, 7, 22, 12, 15, 30, 125000, tzinfo=UTC))
    projection = project_source_time(source, window)
    assert projection.status == "admitted"
    assert projection.reason == "utc_instant_in_window"
    assert projection.timestamp_s == Decimal("930.125")
    assert projection.observed_at_utc == source.observed_at_utc
    assert projection.time_basis_fingerprint == window.fingerprint()
    assert projection.fabricated_instant is False


def test_analysis_window_is_half_open() -> None:
    window = basis()
    at_start = project_source_time(
        UtcInstantTime(observed_at_utc=window.window_start_utc),
        window,
    )
    before_end = project_source_time(
        UtcInstantTime(observed_at_utc=window.window_end_utc - timedelta(microseconds=1)),
        window,
    )
    at_end = project_source_time(
        UtcInstantTime(observed_at_utc=window.window_end_utc),
        window,
    )
    assert at_start.timestamp_s == 0
    assert before_end.status == "admitted"
    assert at_end.status == "excluded"
    assert at_end.reason == "outside_half_open_window"
    assert at_end.timestamp_s is None


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (
            LocalClockHourTime(source_date=date(2026, 7, 22), hour_label=7),
            "undocumented_source_timezone_ga_dft_1",
        ),
        (
            UndeclaredSourceStringTime(
                source_date_raw="2026-03-01T00:00:00",
                source_time_raw="02:23:00",
            ),
            "undocumented_source_timezone_ga_wt_1",
        ),
        (DateOnlyTime(source_date=date(2026, 7, 22)), "date_only_has_no_instant"),
        (
            SimulationClockTime(timestamp_s=Decimal("30"), clock_domain="randy_tos"),
            "simulation_clock_is_not_wall_clock",
        ),
    ],
)
def test_non_utc_source_bases_are_preserved_but_never_promoted(
    source: object,
    reason: str,
) -> None:
    projection = project_source_time(source, basis())  # type: ignore[arg-type]
    assert projection.status == "excluded"
    assert projection.reason == reason
    assert projection.timestamp_s is None
    assert projection.observed_at_utc is None
    assert projection.source_value_preserved is True
    assert projection.fabricated_instant is False


def test_date_only_value_spanning_dst_never_becomes_midnight() -> None:
    spring = DateOnlyTime(source_date=date(2026, 3, 29))
    autumn = DateOnlyTime(source_date=date(2026, 10, 25))
    assert project_source_time(spring, basis()).reason == "date_only_has_no_instant"
    assert project_source_time(autumn, basis()).reason == "date_only_has_no_instant"


def test_time_basis_requires_explicit_utc_start_anchor_and_positive_window() -> None:
    start = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="analysis anchor must equal"):
        ManchesterTimeBasis(
            analysis_anchor_utc=start + timedelta(seconds=1),
            window_start_utc=start,
            window_end_utc=start + timedelta(hours=1),
        )
    with pytest.raises(ValidationError, match="positive duration"):
        ManchesterTimeBasis(
            analysis_anchor_utc=start,
            window_start_utc=start,
            window_end_utc=start,
        )
    with pytest.raises(ValidationError, match="explicitly UTC"):
        basis(start=start.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="explicitly UTC"):
        UtcInstantTime(observed_at_utc=start.astimezone(timezone(timedelta(hours=1))))


def test_spring_forward_missing_london_hour_is_nonexistent() -> None:
    missing = resolve_london_local(datetime(2026, 3, 29, 1, 30))
    assert missing.status == "nonexistent"
    assert missing.candidates == ()
    assert missing.selected_utc is None
    assert missing.fabricated_instant is False


def test_autumn_repeated_london_hour_is_ambiguous_until_fold_supplied() -> None:
    local = datetime(2026, 10, 25, 1, 30)
    ambiguous = resolve_london_local(local)
    assert ambiguous.status == "ambiguous"
    assert [candidate.fold for candidate in ambiguous.candidates] == [0, 1]
    assert [candidate.utc_instant for candidate in ambiguous.candidates] == [
        datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
        datetime(2026, 10, 25, 1, 30, tzinfo=UTC),
    ]
    assert ambiguous.selected_utc is None

    first = resolve_london_local(local, fold=0)
    second = resolve_london_local(local, fold=1)
    assert first.selected_utc == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert second.selected_utc == datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
    assert first.selected_utc != second.selected_utc


def test_unique_london_wall_time_resolves_without_fold_guessing() -> None:
    result = resolve_london_local(datetime(2026, 7, 22, 12, 30))
    assert result.status == "unique"
    assert len(result.candidates) == 1
    assert result.selected_fold == 0
    assert result.selected_utc == datetime(2026, 7, 22, 11, 30, tzinfo=UTC)


def test_london_display_retains_repeated_hour_fold_and_utc_source() -> None:
    first = to_london_display(datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
    second = to_london_display(datetime(2026, 10, 25, 1, 30, tzinfo=UTC))
    assert first.local_datetime.replace(tzinfo=None) == datetime(2026, 10, 25, 1, 30)
    assert second.local_datetime.replace(tzinfo=None) == datetime(2026, 10, 25, 1, 30)
    assert first.fold == 0
    assert first.utc_offset_seconds == 3600
    assert second.fold == 1
    assert second.utc_offset_seconds == 0
    assert first.observed_at_utc != second.observed_at_utc
    assert first.storage_rewritten is False


def test_half_open_projection_uses_elapsed_utc_across_spring_transition() -> None:
    window = basis(
        datetime(2026, 3, 29, 0, 30, tzinfo=UTC),
        datetime(2026, 3, 29, 2, 30, tzinfo=UTC),
    )
    projected = project_source_time(
        UtcInstantTime(observed_at_utc=datetime(2026, 3, 29, 1, 30, tzinfo=UTC)),
        window,
    )
    display = to_london_display(projected.observed_at_utc)  # type: ignore[arg-type]
    assert projected.timestamp_s == 3600
    assert display.local_datetime.replace(tzinfo=None) == datetime(2026, 3, 29, 2, 30)
    assert display.utc_offset_seconds == 3600


def test_half_open_projection_uses_elapsed_utc_across_autumn_transition() -> None:
    window = basis(
        datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
        datetime(2026, 10, 25, 2, 30, tzinfo=UTC),
    )
    projected = project_source_time(
        UtcInstantTime(observed_at_utc=datetime(2026, 10, 25, 1, 30, tzinfo=UTC)),
        window,
    )
    assert projected.timestamp_s == 3600
    display = to_london_display(projected.observed_at_utc)  # type: ignore[arg-type]
    assert display.local_datetime.replace(tzinfo=None) == datetime(2026, 10, 25, 1, 30)
    assert display.fold == 1


def test_aware_local_input_and_strengthened_projection_are_refused() -> None:
    with pytest.raises(ManchesterTimeError, match="must be naive"):
        resolve_london_local(datetime(2026, 7, 22, 12, 0, tzinfo=UTC))

    projection = project_source_time(
        DateOnlyTime(source_date=date(2026, 7, 22)),
        basis(),
    )
    strengthened = projection.model_dump(mode="python")
    strengthened["fabricated_instant"] = True
    with pytest.raises(ValidationError):
        ManchesterTimeProjection.model_validate(strengthened)
