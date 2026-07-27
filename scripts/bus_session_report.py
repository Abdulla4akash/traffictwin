"""Turn one attended bus session's workspace artifacts into the B1 draft's numbers.

After an attended observation session, the measurement artifacts are already in
the workspace but the values the `B1` predeclaration needs are spread across
them. This is the one command that reads them and prints the report: session
scope, cadence percentiles, active-vehicle counts, the hourly progression
aggregates, an optional descriptive comparison against the committed DfT hourly
shape, and a **B1 FILL-FROM-PROBE candidate values** block that names which draft
row each measured value would fill.

**It measures nothing.** Every number is read from an artifact the accepted
:mod:`traffictwin.integration.manchester.bods_session_identity` measurement
functions already wrote, or computed by the accepted
:mod:`traffictwin.integration.manchester.bus_profile_comparison` comparison over
those artifacts. Both are imported by full module path because the Manchester
package ``__init__`` is lead-claimed, and neither is modified.

**No acquisition, no API key, no network, no snapshot.** The inputs are two JSON
files inside an explicitly named workspace and, optionally, one committed
edgeData file. Nothing is fetched, no BODS call is made, and no quarantine member
is opened.

**Aggregates only.** An artifact that does not declare itself aggregate-only, or
that claims to publish raw identifiers, is refused before it is used. No session
token, salt, raw vehicle reference, or snapshot id reaches the rendered report —
snapshot *count* is reported and the ids stay in the artifact, matching what the
accepted Bus Sessions surface already displays.

**Buses are buses.** Progression speed is bus displacement over an update
interval. It is never road-traffic speed, and road-traffic volume is not
available from this source at all.

**The B1 block proposes; it never decides.** Its values are candidates a person
confirms at signing. This script does not write into the predeclaration draft and
never turns a measured value into a chosen threshold — the gap ceiling, dwell
radius, matched-share floor, and speed bound remain owner decisions.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import ValidationError

from traffictwin.integration.manchester.bods_session_identity import (
    BodsSessionIdentityError,
    SessionCadenceMeasurement,
    SessionProgressionMeasurement,
)
from traffictwin.integration.manchester.bus_profile_comparison import (
    BusDftShapeComparison,
    compare_bus_progression_to_dft_shape,
    load_dft_hourly_shape,
)

MeasurementT = TypeVar("MeasurementT", SessionCadenceMeasurement, SessionProgressionMeasurement)

MANCHESTER_SUBDIRECTORY = "manchester"
#: Written by ``scripts/bus_cadence_probe_session.py``.
CADENCE_ARTIFACT_NAME = "bus_cadence_probe_measurement.json"
#: The declared sibling name for a progression measurement. No runner writes one
#: today, so its absence is the normal state rather than a session failure.
PROGRESSION_ARTIFACT_NAME = "bus_session_progression_measurement.json"

_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024

#: British Summer Time. The session artifacts record UTC hours; the DfT profile
#: records local clock-hour labels. Required rather than defaulted, because a
#: silently wrong offset would misalign two real sources by an hour.
DEFAULT_UTC_OFFSET_HOURS = 1

NO_PROGRESSION_WRITER_REASON = (
    "No attended-session runner writes a progression measurement yet, so this artifact is "
    "normally absent. The measurement primitive exists; nothing publishes it into a workspace."
)

UNAVAILABLE = "unavailable"


class BusSessionReportError(RuntimeError):
    """Raised when the workspace cannot be read as an attended bus session."""


@dataclass(frozen=True)
class UnavailableArtifact:
    """One measurement artifact that is not present, with the reason it is not."""

    artifact: str
    status: Literal["unavailable"]
    reason: str


def main(argv: list[str] | None = None) -> int:
    """Render the post-session report for one workspace."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "workspace",
        type=Path,
        help="Workspace directory holding manchester/. Required; there is no default.",
    )
    parser.add_argument(
        "--dft-edgedata",
        type=Path,
        default=None,
        help="Optional committed edgeData file for the descriptive hourly-shape comparison.",
    )
    parser.add_argument(
        "--utc-offset-hours",
        type=int,
        default=DEFAULT_UTC_OFFSET_HOURS,
        help=(
            "Hours to add to the session's UTC hours to reach DfT local clock labels "
            f"(default {DEFAULT_UTC_OFFSET_HOURS}, British Summer Time)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the report here instead of standard output.",
    )
    arguments = parser.parse_args(argv)
    try:
        report = render_session_report(
            arguments.workspace,
            dft_edgedata_path=arguments.dft_edgedata,
            utc_to_local_offset_hours=arguments.utc_offset_hours,
        )
    except BusSessionReportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if arguments.output is None:
        print(report, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(report, encoding="utf-8")
        print(f"written: {arguments.output}")
    return 0


def render_session_report(
    workspace: Path,
    *,
    dft_edgedata_path: Path | None = None,
    utc_to_local_offset_hours: int = DEFAULT_UTC_OFFSET_HOURS,
) -> str:
    """Render the complete markdown report for one attended session."""

    directory = Path(workspace) / MANCHESTER_SUBDIRECTORY
    if not directory.is_dir():
        raise BusSessionReportError(
            f"this workspace has no {MANCHESTER_SUBDIRECTORY}/ directory, so no attended "
            f"bus session has been recorded into it: {directory}"
        )
    cadence = _load(
        directory / CADENCE_ARTIFACT_NAME,
        SessionCadenceMeasurement,
        "session cadence measurement",
        "No attended cadence session has been recorded into this workspace.",
    )
    progression = _load(
        directory / PROGRESSION_ARTIFACT_NAME,
        SessionProgressionMeasurement,
        "session progression measurement",
        NO_PROGRESSION_WRITER_REASON,
    )
    if isinstance(cadence, UnavailableArtifact) and isinstance(progression, UnavailableArtifact):
        raise BusSessionReportError(
            f"neither measurement artifact is present in {directory}; "
            f"cadence: {cadence.reason} progression: {progression.reason}"
        )
    comparison = _comparison(
        progression,
        dft_edgedata_path,
        utc_to_local_offset_hours=utc_to_local_offset_hours,
    )
    sections = [
        _header(),
        _scope_section(cadence, progression),
        _cadence_section(cadence),
        _progression_section(progression),
        _comparison_section(comparison, dft_edgedata_path),
        _b1_section(cadence, progression),
        _boundaries_section(),
    ]
    return "\n".join(sections)


def _load(
    path: Path,
    model: type[MeasurementT],
    artifact: str,
    absent_reason: str,
) -> MeasurementT | UnavailableArtifact:
    """Load one artifact, refusing anything that is not declared aggregate-only."""

    if not path.is_file():
        return UnavailableArtifact(artifact=artifact, status=UNAVAILABLE, reason=absent_reason)
    if path.stat().st_size > _MAX_ARTIFACT_BYTES:
        return UnavailableArtifact(
            artifact=artifact,
            status=UNAVAILABLE,
            reason="The artifact exceeds the bounded read size and was not opened.",
        )
    try:
        # The strict frozen base refuses python-dict tuples, so the artifact
        # validates through JSON mode exactly as it was persisted.
        loaded = model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        return UnavailableArtifact(
            artifact=artifact,
            status=UNAVAILABLE,
            reason=f"The artifact could not be read as a valid measurement: {str(error)[:300]}",
        )
    if not (loaded.aggregates_only and not loaded.raw_identifiers_published):
        return UnavailableArtifact(
            artifact=artifact,
            status=UNAVAILABLE,
            reason="The artifact does not declare itself aggregate-only, so it was refused.",
        )
    return loaded


def _comparison(
    progression: SessionProgressionMeasurement | UnavailableArtifact,
    dft_edgedata_path: Path | None,
    *,
    utc_to_local_offset_hours: int,
) -> BusDftShapeComparison | UnavailableArtifact:
    """Run the accepted descriptive comparison, or say exactly why it did not run."""

    if dft_edgedata_path is None:
        return UnavailableArtifact(
            artifact="bus-versus-DfT hourly shape comparison",
            status=UNAVAILABLE,
            reason="No --dft-edgedata file was supplied, so no comparison was attempted.",
        )
    if isinstance(progression, UnavailableArtifact):
        return UnavailableArtifact(
            artifact="bus-versus-DfT hourly shape comparison",
            status=UNAVAILABLE,
            reason=(
                "The comparison needs an hourly progression measurement, which this "
                f"workspace does not hold. {progression.reason}"
            ),
        )
    try:
        shape = load_dft_hourly_shape(dft_edgedata_path)
    except BodsSessionIdentityError as error:
        return UnavailableArtifact(
            artifact="bus-versus-DfT hourly shape comparison",
            status=UNAVAILABLE,
            reason=f"The edgeData file could not be reduced to an hourly shape: {error}",
        )
    return compare_bus_progression_to_dft_shape(
        progression,
        shape,
        utc_to_local_offset_hours=utc_to_local_offset_hours,
    )


def _header() -> str:
    return "\n".join(
        [
            "# Attended bus session — post-session report",
            "",
            "Status: **owner_approved_candidate, descriptive, aggregates only.** Not supervisor",
            "approval, not validation, and not a causal claim.",
            "",
            "Every number below was measured by the accepted session-identity functions and is",
            "read here, not recomputed. Bus progression speed is never road-traffic speed, and",
            "road-traffic volume is not available from this source.",
            "",
        ]
    )


def _scope_section(
    cadence: SessionCadenceMeasurement | UnavailableArtifact,
    progression: SessionProgressionMeasurement | UnavailableArtifact,
) -> str:
    lines = ["## 1. Session scope", ""]
    if isinstance(cadence, UnavailableArtifact):
        lines += [f"Cadence measurement: **{UNAVAILABLE}** — {cadence.reason}", ""]
    else:
        lines += [
            "| Field | Value |",
            "|---|---|",
            f"| Policy | `{cadence.policy_id}` |",
            f"| Research status | `{cadence.research_status}` |",
            f"| Snapshots in session | {cadence.snapshot_count} |",
            "",
            "The artifact records which snapshots these were; the ids are deliberately not",
            "printed here, so the report carries no per-snapshot reference.",
            "",
        ]
    if isinstance(progression, UnavailableArtifact):
        lines += [f"Progression measurement: **{UNAVAILABLE}** — {progression.reason}", ""]
    else:
        hours = len(progression.hour_utc)
        lines += [f"Progression measurement: present, covering {hours} UTC hours.", ""]
    return "\n".join(lines)


def _cadence_section(cadence: SessionCadenceMeasurement | UnavailableArtifact) -> str:
    lines = ["## 2. Cadence percentiles and active-vehicle counts", ""]
    if isinstance(cadence, UnavailableArtifact):
        lines += [f"**{UNAVAILABLE}** — {cadence.reason}", ""]
        return "\n".join(lines)
    lines += [
        "### Active vehicles",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Vehicles seen | {cadence.vehicles_seen_total} |",
        f"| Vehicles actively updating (linked across snapshots) | "
        f"{cadence.vehicles_linked_across_snapshots} |",
        f"| Linked observations | {cadence.observation_count} |",
        f"| Repeated identical fixes | {cadence.repeated_identical_fix_count} |",
        "",
    ]
    lines += [
        _stale_sentence(cadence),
        "",
        "### Update interval and displacement",
        "",
        "| Measure | Median | p90 | Max |",
        "|---|---|---|---|",
        f"| Update interval (s) | {_number(cadence.update_delta_seconds_median)} | "
        f"{_number(cadence.update_delta_seconds_p90)} | "
        f"{_number(cadence.update_delta_seconds_max)} |",
        f"| Displacement (m) | {_number(cadence.displacement_m_median)} | "
        f"{_number(cadence.displacement_m_p90)} | {_number(cadence.displacement_m_max)} |",
        "",
        f"Maximum implied bus speed: **{_number(cadence.implied_speed_mps_max)} m/s**.",
        "",
    ]
    return "\n".join(lines)


def _stale_sentence(cadence: SessionCadenceMeasurement) -> str:
    """State the stale-vehicle share the way the B1 draft states it: as two counts."""

    if cadence.observation_count == 0:
        return "No linked observations were recorded, so no stale-fix share can be stated."
    share = cadence.repeated_identical_fix_count / cadence.observation_count
    return (
        f"{cadence.repeated_identical_fix_count} of {cadence.observation_count} linked "
        f"observations ({share:.1%}) were repeated identical fixes from stale vehicles, which "
        "the B1 gap ceiling drops by design."
    )


def _progression_section(progression: SessionProgressionMeasurement | UnavailableArtifact) -> str:
    lines = ["## 3. Hourly bus-progression aggregates", ""]
    if isinstance(progression, UnavailableArtifact):
        lines += [f"**{UNAVAILABLE}** — {progression.reason}", ""]
        return "\n".join(lines)
    lines += [
        "Bus progression only. These are transit vehicles moving between fixes, not road",
        "traffic, and no road-traffic speed or volume is derivable from them.",
        "",
        "| Hour (UTC) | Segments | Vehicles contributing | Median speed (m/s) | p90 speed (m/s) |",
        "|---|---|---|---|---|",
    ]
    rows = sorted(
        zip(
            progression.hour_utc,
            progression.segment_count_by_hour,
            progression.vehicles_contributing_by_hour,
            progression.speed_mps_median_by_hour,
            progression.speed_mps_p90_by_hour,
            strict=True,
        ),
        key=lambda row: row[0],
    )
    for hour, segments, vehicles, median, p90 in rows:
        lines.append(
            f"| {hour:02d} | {segments} | {vehicles} | {_number(median)} | {_number(p90)} |"
        )
    lines.append("")
    return "\n".join(lines)


def _comparison_section(
    comparison: BusDftShapeComparison | UnavailableArtifact,
    dft_edgedata_path: Path | None,
) -> str:
    lines = ["## 4. Bus shape beside the DfT hourly shape (descriptive)", ""]
    if isinstance(comparison, UnavailableArtifact):
        lines += [f"**{UNAVAILABLE}** — {comparison.reason}", ""]
        return "\n".join(lines)
    lines += [
        "Two independent observed sources placed side by side. This is descriptive and",
        "non-causal: bus progression speed is not road speed, and DfT road counts are not bus",
        "counts. Neither series explains the other.",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| DfT source SHA-256 | `{comparison.dft_source_sha256}` |",
        f"| UTC-to-local offset applied | {comparison.utc_to_local_offset_hours} h |",
        f"| Minimum segments per hour | {comparison.minimum_segments_per_hour} |",
        f"| Aligned hours | {_hours(comparison.aligned_hour_local_labels)} |",
        f"| Hours excluded for insufficient support | "
        f"{_hours(comparison.hours_excluded_for_support)} |",
        f"| Spearman rho | {_number(comparison.spearman_rho)} |",
        f"| Aligned pairs behind rho | {comparison.spearman_pair_count} |",
        "",
    ]
    if comparison.spearman_rho is None:
        lines += [
            "No correlation is reported: the accepted comparison needs at least three aligned",
            "hours with sufficient support, and this session did not supply them. That is a",
            "reported absence, not a value of zero.",
            "",
        ]
    return "\n".join(lines)


def _b1_section(
    cadence: SessionCadenceMeasurement | UnavailableArtifact,
    progression: SessionProgressionMeasurement | UnavailableArtifact,
) -> str:
    """Map measured values onto the B1 rows they would fill, as candidates only."""

    lines = [
        "## 5. B1 FILL-FROM-PROBE candidate values",
        "",
        "**Candidates for a person to confirm at signing — not decisions.** Each row names the",
        "`docs/evaluation/bus_fleet_experiment_predeclaration_draft.md` field it would fill and",
        "the measured value from this session. Nothing here is written into that draft, and a",
        "measurement is never converted into a chosen threshold: the gap ceiling, dwell radius,",
        "matched-share floor, and implied-speed bound stay `FILL-AT-SIGNING` owner decisions",
        "that this session only *informs*.",
        "",
        "| B1 field | Candidate value from this session | Status |",
        "|---|---|---|",
    ]
    if isinstance(cadence, UnavailableArtifact):
        lines.append(f"| §3 measured update interval | {UNAVAILABLE} | no cadence measurement |")
    else:
        lines += [
            f"| §3 measured per-vehicle update interval | median "
            f"{_number(cadence.update_delta_seconds_median)} s / p90 "
            f"{_number(cadence.update_delta_seconds_p90)} s | measured |",
            f"| §3 observation session — snapshots | {cadence.snapshot_count} | measured |",
            f"| §5 probe fact — vehicles seen | {cadence.vehicles_seen_total} | measured |",
            f"| §5 probe fact — actively updating | "
            f"{cadence.vehicles_linked_across_snapshots} | measured |",
            f"| §5 probe fact — repeated identical fixes | "
            f"{cadence.repeated_identical_fix_count} of {cadence.observation_count} "
            f"observations | measured |",
            f"| §5 probe fact — median displacement per update | "
            f"{_number(cadence.displacement_m_median)} m | measured |",
            f"| §5 implied-speed bound — highest observed | "
            f"{_number(cadence.implied_speed_mps_max)} m/s | **informs** the "
            f"`FILL-AT-SIGNING` bound; does not set it |",
            f"| §3 gap ceiling — longest observed gap between fixes | "
            f"{_number(cadence.update_delta_seconds_max)} s | **informs** the "
            f"`FILL-AT-SIGNING` ceiling; does not set it |",
        ]
    if isinstance(progression, UnavailableArtifact):
        lines.append(
            f"| §3 trace window — hourly support | {UNAVAILABLE} | no progression measurement |"
        )
    else:
        best = max(
            zip(
                progression.hour_utc,
                progression.vehicles_contributing_by_hour,
                strict=True,
            ),
            key=lambda row: row[1],
        )
        lines.append(
            f"| §3 trace window — busiest recorded hour | {best[0]:02d} UTC with {best[1]} "
            f"contributing vehicles | **informs** the `FILL-AT-SIGNING` linked-vehicle "
            f"threshold; does not set it |"
        )
    lines += [
        "",
        "Fields this session cannot fill, and why: per-vehicle matched-share and the",
        "interpolated-versus-observed share need map matching, which no session artifact",
        "carries; the trace window needs the linked-vehicle threshold chosen first. They stay",
        "unfilled rather than estimated.",
        "",
    ]
    return "\n".join(lines)


def _boundaries_section() -> str:
    return "\n".join(
        [
            "## 6. What this report is not",
            "",
            "- **Not road traffic.** Buses are buses. Progression speed is bus displacement over",
            "  an update interval; road-traffic speed and volume are not available here.",
            "- **Not a new measurement.** Every value is read from an artifact the accepted",
            "  measurement functions wrote, or computed by the accepted comparison over them.",
            "- **Not identifying.** The artifacts are aggregate-only by type, and no session",
            "  token, salt, raw vehicle reference, or snapshot id is printed.",
            "- **Not an acquisition.** No BODS call, no API key, no network access, and no",
            "  quarantine member is opened by this script.",
            "- **Not a signature.** The B1 draft stays unsigned, and its `FILL-AT-SIGNING`",
            "  values stay owner decisions.",
            "",
        ]
    )


def _number(value: float | None) -> str:
    return UNAVAILABLE if value is None else f"{value:.3f}"


def _hours(hours: tuple[int, ...]) -> str:
    return ", ".join(f"{hour:02d}" for hour in hours) if hours else "none"


if __name__ == "__main__":
    sys.exit(main())
