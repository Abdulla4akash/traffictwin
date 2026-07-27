"""Read-only loading of aggregate-only bus session measurements for the UI.

The page-independent half of the Bus Sessions screen. It reads the measurement
artifacts the session-identity work writes into a workspace and turns them into
display rows. It computes no new measurement, performs no acquisition, and
touches no snapshot.

**Aggregates only, by construction.** The underlying artifacts carry
``aggregates_only: True`` and ``raw_identifiers_published: False`` as type-level
literals, and this layer refuses to load anything that does not. Session tokens
and raw vehicle references never existed outside the extraction function that
produced these files, so there is nothing here to leak — and a loader that
accepted an artifact without those literals would be the one way that could
change, which is why the check is explicit rather than assumed.

**Buses are buses.** Progression speed is bus displacement over an update
interval. It is never road-traffic speed, and the artifacts' own
``road_traffic_speed_available: False`` and ``road_traffic_volume_available:
False`` literals are surfaced rather than hidden.

An absent workspace or artifact is an explicit unavailable state carrying its
reason. Nothing is defaulted, estimated, or filled in.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import ValidationError

from traffictwin.integration.manchester.bods_session_identity import (
    SessionCadenceMeasurement,
    SessionProgressionMeasurement,
)

MeasurementT = TypeVar("MeasurementT", SessionCadenceMeasurement, SessionProgressionMeasurement)

#: Written by ``scripts/bus_cadence_probe_session.py`` into ``<workspace>/manchester/``.
CADENCE_ARTIFACT_NAME = "bus_cadence_probe_measurement.json"
#: The declared sibling name for a progression measurement. No runner writes one
#: today, so its absence is the normal state and is reported as such.
PROGRESSION_ARTIFACT_NAME = "bus_session_progression_measurement.json"
MANCHESTER_SUBDIRECTORY = "manchester"

_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024

NO_PROGRESSION_WRITER_REASON = (
    "No attended-session runner writes a progression measurement yet, so this "
    "artifact is normally absent. The measurement primitive exists; nothing "
    "publishes it into the workspace."
)


@dataclass(frozen=True)
class BusSessionsError:
    """User-facing bus-sessions error with optional technical detail."""

    message: str
    detail: str | None = None


@dataclass(frozen=True)
class UnavailableArtifact:
    """One measurement artifact that is not present, with the reason it is not."""

    artifact: str
    status: Literal["unavailable"]
    reason: str


@dataclass(frozen=True)
class CadenceRow:
    """One labelled aggregate from the cadence measurement."""

    label: str
    value: str


@dataclass(frozen=True)
class ProgressionRow:
    """One UTC hour of bus progression, with the support behind it."""

    hour_utc: int
    segment_count: int
    vehicles_contributing: int
    speed_mps_median: float
    speed_mps_p90: float


@dataclass(frozen=True)
class BusSessionContext:
    """Everything the Bus Sessions page renders for one workspace."""

    workspace_directory: Path
    cadence: SessionCadenceMeasurement | UnavailableArtifact
    progression: SessionProgressionMeasurement | UnavailableArtifact

    @property
    def has_any_measurement(self) -> bool:
        """Return whether at least one artifact was loaded."""

        return not (
            isinstance(self.cadence, UnavailableArtifact)
            and isinstance(self.progression, UnavailableArtifact)
        )


def load_bus_session_context(
    workspace_path: str | Path | None,
) -> BusSessionContext | BusSessionsError:
    """Load whichever aggregate measurements the workspace actually holds."""

    if workspace_path is None or not str(workspace_path).strip():
        return BusSessionsError(
            "No workspace is configured, so no bus session measurements can be found."
        )
    directory = Path(workspace_path) / MANCHESTER_SUBDIRECTORY
    if not directory.is_dir():
        return BusSessionsError(
            "This workspace has no Manchester directory, so no attended bus session "
            "has been recorded into it.",
            detail=str(directory),
        )
    return BusSessionContext(
        workspace_directory=directory,
        cadence=_load(
            directory / CADENCE_ARTIFACT_NAME,
            SessionCadenceMeasurement,
            "session cadence measurement",
            "No attended cadence session has been recorded into this workspace.",
        ),
        progression=_load(
            directory / PROGRESSION_ARTIFACT_NAME,
            SessionProgressionMeasurement,
            "session progression measurement",
            NO_PROGRESSION_WRITER_REASON,
        ),
    )


def _load(
    path: Path,
    model: type[MeasurementT],
    artifact: str,
    absent_reason: str,
) -> MeasurementT | UnavailableArtifact:
    if not path.is_file():
        return UnavailableArtifact(artifact=artifact, status="unavailable", reason=absent_reason)
    if path.stat().st_size > _MAX_ARTIFACT_BYTES:
        return UnavailableArtifact(
            artifact=artifact,
            status="unavailable",
            reason="The artifact exceeds the bounded read size and was not opened.",
        )
    try:
        # The strict frozen base refuses python-dict tuples, so the artifact
        # validates through JSON mode exactly as it was persisted.
        loaded = model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        return UnavailableArtifact(
            artifact=artifact,
            status="unavailable",
            reason=f"The artifact could not be read as a valid measurement: {str(exc)[:300]}",
        )
    if not (loaded.aggregates_only and not loaded.raw_identifiers_published):
        return UnavailableArtifact(
            artifact=artifact,
            status="unavailable",
            reason="The artifact does not declare itself aggregate-only, so it was refused.",
        )
    return loaded


def cadence_rows(measurement: SessionCadenceMeasurement) -> list[CadenceRow]:
    """Return the cadence aggregates as labelled display rows."""

    return [
        CadenceRow("Snapshots in session", str(measurement.snapshot_count)),
        CadenceRow("Vehicles seen", str(measurement.vehicles_seen_total)),
        CadenceRow(
            "Vehicles linked across snapshots",
            str(measurement.vehicles_linked_across_snapshots),
        ),
        CadenceRow("Linked observations", str(measurement.observation_count)),
        CadenceRow("Repeated identical fixes", str(measurement.repeated_identical_fix_count)),
        CadenceRow("Update interval, median (s)", _number(measurement.update_delta_seconds_median)),
        CadenceRow("Update interval, p90 (s)", _number(measurement.update_delta_seconds_p90)),
        CadenceRow("Update interval, max (s)", _number(measurement.update_delta_seconds_max)),
        CadenceRow("Displacement, median (m)", _number(measurement.displacement_m_median)),
        CadenceRow("Displacement, p90 (m)", _number(measurement.displacement_m_p90)),
        CadenceRow("Displacement, max (m)", _number(measurement.displacement_m_max)),
        CadenceRow("Implied bus speed, max (m/s)", _number(measurement.implied_speed_mps_max)),
    ]


def progression_rows(measurement: SessionProgressionMeasurement) -> list[ProgressionRow]:
    """Return the hourly bus progression rows, ordered by UTC hour."""

    rows = [
        ProgressionRow(
            hour_utc=hour,
            segment_count=segments,
            vehicles_contributing=vehicles,
            speed_mps_median=median,
            speed_mps_p90=p90,
        )
        for hour, segments, vehicles, median, p90 in zip(
            measurement.hour_utc,
            measurement.segment_count_by_hour,
            measurement.vehicles_contributing_by_hour,
            measurement.speed_mps_median_by_hour,
            measurement.speed_mps_p90_by_hour,
            strict=True,
        )
    ]
    return sorted(rows, key=lambda row: row.hour_utc)


def _number(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.3f}"
