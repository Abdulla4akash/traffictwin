"""Unit coverage for loading aggregate-only bus session measurements."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traffictwin.integration.manchester.bods_session_identity import (
    SessionCadenceMeasurement,
    SessionProgressionMeasurement,
)
from traffictwin.ui.bus_sessions_services import (
    CADENCE_ARTIFACT_NAME,
    PROGRESSION_ARTIFACT_NAME,
    BusSessionsError,
    UnavailableArtifact,
    cadence_rows,
    load_bus_session_context,
    progression_rows,
)


def _cadence() -> SessionCadenceMeasurement:
    return SessionCadenceMeasurement(
        snapshot_ids=("snap-a", "snap-b", "snap-c"),
        snapshot_count=3,
        vehicles_seen_total=2,
        vehicles_linked_across_snapshots=2,
        observation_count=6,
        repeated_identical_fix_count=1,
        update_delta_seconds_median=60.0,
        update_delta_seconds_p90=60.0,
        update_delta_seconds_max=60.0,
        displacement_m_median=140.0,
        displacement_m_p90=180.0,
        displacement_m_max=200.0,
        implied_speed_mps_max=3.4,
    )


def _progression() -> SessionProgressionMeasurement:
    return SessionProgressionMeasurement(
        snapshot_ids=("snap-a", "snap-b"),
        hour_utc=(9, 8),
        segment_count_by_hour=(40, 12),
        speed_mps_median_by_hour=(6.5, 4.25),
        speed_mps_p90_by_hour=(9.0, 7.5),
        vehicles_contributing_by_hour=(11, 4),
    )


def _workspace(tmp_path: Path, *, cadence: bool = True, progression: bool = True) -> Path:
    directory = tmp_path / "manchester"
    directory.mkdir(parents=True, exist_ok=True)
    if cadence:
        (directory / CADENCE_ARTIFACT_NAME).write_text(
            _cadence().model_dump_json(), encoding="utf-8"
        )
    if progression:
        (directory / PROGRESSION_ARTIFACT_NAME).write_text(
            _progression().model_dump_json(), encoding="utf-8"
        )
    return tmp_path


def test_an_unset_workspace_is_an_explicit_error() -> None:
    outcome = load_bus_session_context(None)

    assert isinstance(outcome, BusSessionsError)
    assert "No workspace is configured" in outcome.message


def test_a_blank_workspace_path_is_an_explicit_error() -> None:
    outcome = load_bus_session_context("   ")

    assert isinstance(outcome, BusSessionsError)
    assert "No workspace is configured" in outcome.message


def test_a_workspace_without_a_manchester_directory_is_an_explicit_error(
    tmp_path: Path,
) -> None:
    outcome = load_bus_session_context(tmp_path)

    assert isinstance(outcome, BusSessionsError)
    assert "no Manchester directory" in outcome.message
    assert outcome.detail is not None


def test_an_empty_manchester_directory_reports_both_artifacts_unavailable(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path, cadence=False, progression=False)

    context = load_bus_session_context(workspace)

    assert not isinstance(context, BusSessionsError)
    assert context.has_any_measurement is False
    assert isinstance(context.cadence, UnavailableArtifact)
    assert isinstance(context.progression, UnavailableArtifact)
    assert context.cadence.status == "unavailable"
    assert "No attended cadence session" in context.cadence.reason


def test_a_missing_progression_artifact_states_that_nothing_writes_one(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path, progression=False)

    context = load_bus_session_context(workspace)

    assert not isinstance(context, BusSessionsError)
    assert not isinstance(context.cadence, UnavailableArtifact)
    assert isinstance(context.progression, UnavailableArtifact)
    # The honest reason: the primitive exists, no runner publishes it.
    assert "No attended-session runner writes a progression measurement yet" in (
        context.progression.reason
    )
    assert context.has_any_measurement is True


def test_both_artifacts_load_when_present(tmp_path: Path) -> None:
    context = load_bus_session_context(_workspace(tmp_path))

    assert not isinstance(context, BusSessionsError)
    assert isinstance(context.cadence, SessionCadenceMeasurement)
    assert isinstance(context.progression, SessionProgressionMeasurement)
    assert context.cadence.snapshot_count == 3
    assert context.workspace_directory.name == "manchester"


def test_an_unreadable_artifact_is_unavailable_with_its_reason(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / "manchester" / CADENCE_ARTIFACT_NAME).write_text("{not json", encoding="utf-8")

    context = load_bus_session_context(workspace)

    assert not isinstance(context, BusSessionsError)
    assert isinstance(context.cadence, UnavailableArtifact)
    assert "could not be read as a valid measurement" in context.cadence.reason


def test_an_artifact_not_declaring_itself_aggregate_only_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    payload = json.loads(_cadence().model_dump_json())
    payload["aggregates_only"] = False
    (workspace / "manchester" / CADENCE_ARTIFACT_NAME).write_text(
        json.dumps(payload), encoding="utf-8"
    )

    context = load_bus_session_context(workspace)

    assert not isinstance(context, BusSessionsError)
    # `aggregates_only` is a Literal[True], so the model itself refuses the
    # tampered artifact before the loader's own belt-and-braces check is
    # reached. Either way it never loads.
    assert isinstance(context.cadence, UnavailableArtifact)
    assert "aggregates_only" in context.cadence.reason


def test_raw_identifiers_published_is_also_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    payload = json.loads(_cadence().model_dump_json())
    payload["raw_identifiers_published"] = True
    (workspace / "manchester" / CADENCE_ARTIFACT_NAME).write_text(
        json.dumps(payload), encoding="utf-8"
    )

    context = load_bus_session_context(workspace)

    assert not isinstance(context, BusSessionsError)
    assert isinstance(context.cadence, UnavailableArtifact)
    assert "raw_identifiers_published" in context.cadence.reason


def test_an_oversized_artifact_is_not_opened(tmp_path: Path) -> None:
    from traffictwin.ui import bus_sessions_services

    workspace = _workspace(tmp_path)
    original = bus_sessions_services._MAX_ARTIFACT_BYTES
    try:
        bus_sessions_services._MAX_ARTIFACT_BYTES = 1
        context = load_bus_session_context(workspace)
    finally:
        bus_sessions_services._MAX_ARTIFACT_BYTES = original

    assert not isinstance(context, BusSessionsError)
    assert isinstance(context.cadence, UnavailableArtifact)
    assert "bounded read size" in context.cadence.reason


def test_cadence_rows_label_every_aggregate(tmp_path: Path) -> None:
    rows = cadence_rows(_cadence())

    labels = [row.label for row in rows]
    assert "Snapshots in session" in labels
    assert "Update interval, median (s)" in labels
    assert "Implied bus speed, max (m/s)" in labels
    values = {row.label: row.value for row in rows}
    assert values["Snapshots in session"] == "3"
    assert values["Update interval, median (s)"] == "60.000"


def test_an_absent_aggregate_renders_unavailable_not_zero() -> None:
    measurement = _cadence().model_copy(update={"implied_speed_mps_max": None})

    values = {row.label: row.value for row in cadence_rows(measurement)}

    assert values["Implied bus speed, max (m/s)"] == "unavailable"


def test_no_row_can_surface_a_token_or_raw_reference() -> None:
    rendered = " ".join(f"{row.label} {row.value}" for row in cadence_rows(_cadence()))

    for forbidden in ("token", "salt", "VehicleRef", "vehicle_ref", "snap-a"):
        assert forbidden not in rendered


def test_progression_rows_are_ordered_by_hour_and_carry_their_support() -> None:
    rows = progression_rows(_progression())

    assert [row.hour_utc for row in rows] == [8, 9]
    first = rows[0]
    assert first.segment_count == 12
    assert first.vehicles_contributing == 4
    assert first.speed_mps_median == pytest.approx(4.25)
    assert first.speed_mps_p90 == pytest.approx(7.5)
