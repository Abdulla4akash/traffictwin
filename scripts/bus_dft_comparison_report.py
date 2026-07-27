"""Write the bus-progression versus DfT hourly-shape comparison for one workspace.

The B2 comparison step as a single command: take one attended session's hourly
bus-progression measurement out of an explicitly named workspace, take the
observed hourly road-demand shape out of the committed Option-A edgeData file,
align them on the local clock hour, and write the result as a JSON artifact and
a markdown report into a supplied output directory.

**It measures nothing.** The alignment, the support gate, and the rank
correlation are all produced by the accepted
:mod:`traffictwin.integration.manchester.bus_profile_comparison` functions over
an artifact the accepted
:mod:`traffictwin.integration.manchester.bods_session_identity` primitive
already wrote. Both are imported by full module path because the Manchester
package ``__init__`` is lead-claimed, and neither is modified.

**The UTC-to-local offset is required.** The session artifact records UTC hours;
the DfT profile records local clock-hour labels under the unresolved GA-DFT-1
blocker. A defaulted offset would misalign two independent real sources by an
hour without anybody noticing, so there is no default — the operator declares it.

**Aggregates only, and snapshot ids do not travel.** An artifact that does not
declare itself aggregate-only, or that claims to publish raw identifiers, is
refused before it is read. A snapshot id is a locator into the quarantine
directory, so the report publishes the snapshot *count* and leaves the ids in
the workspace artifact. Neither written file contains an absolute path.

**Two independent sources, described side by side.** Bus progression speed is
bus displacement over an update interval — never road-traffic speed. The DfT
side is road counts — never bus counts. The Spearman value is a rank
correlation between two observed shapes: no significance test is performed, no
threshold is applied, and nothing here says one shape explains the other.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from traffictwin.integration.manchester.bods_session_identity import (
    BodsSessionIdentityError,
    SessionProgressionMeasurement,
)
from traffictwin.integration.manchester.bus_profile_comparison import (
    BusDftShapeComparison,
    DftHourlyShape,
    compare_bus_progression_to_dft_shape,
    load_dft_hourly_shape,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel

REPORT_VERSION: Literal["bus-dft-comparison-report-1.0"] = "bus-dft-comparison-report-1.0"

MANCHESTER_SUBDIRECTORY = "manchester"
#: The declared sibling name for a progression measurement, matching the name
#: the post-session report script already reads.
PROGRESSION_ARTIFACT_NAME = "bus_session_progression_measurement.json"

#: The committed Option-A edgeData evidence, whose observation side is DfT road
#: counts. Used unless the operator names a different file.
DEFAULT_EDGEDATA_PATH = Path("docs/integration/evidence/manchester_edgedata_counts_option_a.xml")

JSON_OUTPUT_NAME = "bus_dft_comparison.json"
MARKDOWN_OUTPUT_NAME = "bus_dft_comparison.md"

_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024

STANDING_LIMITATIONS: tuple[str, ...] = (
    "Descriptive only. Two independently observed hourly shapes are set beside each "
    "other; neither is a control for the other and no mechanism is established.",
    "The Spearman value is a rank correlation over the surviving aligned hours. No "
    "significance test was performed and none is implied by its size or sign.",
    "Bus progression speed is bus displacement over an update interval. It is not "
    "road-traffic speed, and road-traffic speed is not available from this source.",
    "The DfT side is road counts from the surviving Option-A edgeData window. Road "
    "counts are not bus counts.",
    "The DfT hour is a local clock-hour label under the unresolved GA-DFT-1 blocker, "
    "and the offset applied to the session's UTC hours is a declared operator input "
    "rather than an inference.",
    "Owner-approved-candidate evidence: not supervisor-approved, not validated, not "
    "causal, and not generalisable beyond the observed session and window.",
)


class BusDftComparisonReportError(RuntimeError):
    """Raised when the comparison cannot be produced from the supplied inputs."""


class BusDftComparisonReport(ManchesterSnapshotModel):
    """The written artifact: the accepted comparison with locators left behind."""

    schema_version: Literal["1.0"] = "1.0"
    report_version: Literal["bus-dft-comparison-report-1.0"] = REPORT_VERSION
    dft_edgedata_name: str = Field(min_length=1, max_length=200)
    dft_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dft_total_entered: int = Field(ge=1)
    utc_to_local_offset_hours: int = Field(ge=-12, le=14)
    minimum_segments_per_hour: int = Field(ge=1)
    session_snapshot_count: int = Field(ge=2)
    aligned_hour_local_labels: tuple[int, ...]
    bus_speed_mps_median_by_hour: tuple[float, ...]
    bus_segment_support_by_hour: tuple[int, ...]
    dft_share_by_hour: tuple[float, ...]
    hours_excluded_for_support: tuple[int, ...]
    excluded_hour_segment_support: tuple[int, ...]
    spearman_rho: float | None = Field(default=None, ge=-1, le=1)
    spearman_pair_count: int = Field(ge=0)
    limitations: tuple[str, ...] = Field(min_length=1)
    session_snapshot_ids_published: Literal[False] = False
    absolute_paths_published: Literal[False] = False
    aggregates_only: Literal[True] = True
    descriptive_non_causal: Literal[True] = True
    significance_claimed: Literal[False] = False
    bus_speed_is_not_road_speed: Literal[True] = True
    road_counts_are_not_bus_counts: Literal[True] = True
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"

    @model_validator(mode="after")
    def validate_series(self) -> BusDftComparisonReport:
        aligned = {
            len(self.aligned_hour_local_labels),
            len(self.bus_speed_mps_median_by_hour),
            len(self.bus_segment_support_by_hour),
            len(self.dft_share_by_hour),
        }
        if aligned != {len(self.aligned_hour_local_labels)}:
            raise ValueError("aligned series must share the hour axis")
        if len(self.hours_excluded_for_support) != len(self.excluded_hour_segment_support):
            raise ValueError("every excluded hour must report the support it had")
        return self


def main(argv: list[str] | None = None) -> int:
    """Write the comparison artifact and report for one workspace."""

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "workspace",
        type=Path,
        help=(
            f"Workspace directory holding {MANCHESTER_SUBDIRECTORY}/"
            f"{PROGRESSION_ARTIFACT_NAME}. Required; there is no default."
        ),
    )
    parser.add_argument(
        "output_directory",
        type=Path,
        help="Directory to write the JSON artifact and markdown report into.",
    )
    parser.add_argument(
        "--utc-offset-hours",
        type=int,
        required=True,
        help=(
            "Hours to add to the session's UTC hours to reach DfT local clock labels. "
            "Required and never defaulted: a wrong offset misaligns two real sources."
        ),
    )
    parser.add_argument(
        "--dft-edgedata",
        type=Path,
        default=DEFAULT_EDGEDATA_PATH,
        help=f"Option-A edgeData file (default {DEFAULT_EDGEDATA_PATH}).",
    )
    parser.add_argument(
        "--minimum-segments-per-hour",
        type=int,
        default=None,
        help=(
            "Override the accepted support gate. Omit to use the accepted default, "
            "which is the value the comparison module already applies."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing output files instead of refusing.",
    )
    arguments = parser.parse_args(argv)
    try:
        report = build_comparison_report(
            arguments.workspace,
            dft_edgedata_path=arguments.dft_edgedata,
            utc_to_local_offset_hours=arguments.utc_offset_hours,
            minimum_segments_per_hour=arguments.minimum_segments_per_hour,
        )
        written = write_comparison_report(
            report,
            arguments.output_directory,
            overwrite=arguments.overwrite,
        )
    except BusDftComparisonReportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for path in written:
        print(f"written: {path}")
    return 0


def build_comparison_report(
    workspace: Path,
    *,
    dft_edgedata_path: Path,
    utc_to_local_offset_hours: int,
    minimum_segments_per_hour: int | None = None,
) -> BusDftComparisonReport:
    """Run the accepted comparison for one workspace and return the report artifact."""

    progression = _load_progression(Path(workspace))
    shape = _load_shape(Path(dft_edgedata_path))
    comparison = _compare(
        progression,
        shape,
        utc_to_local_offset_hours=utc_to_local_offset_hours,
        minimum_segments_per_hour=minimum_segments_per_hour,
    )
    support = _support_by_local_hour(
        progression, utc_to_local_offset_hours=utc_to_local_offset_hours
    )
    return BusDftComparisonReport(
        dft_edgedata_name=Path(dft_edgedata_path).name,
        dft_source_sha256=shape.source_sha256,
        dft_total_entered=shape.total_entered,
        utc_to_local_offset_hours=comparison.utc_to_local_offset_hours,
        minimum_segments_per_hour=comparison.minimum_segments_per_hour,
        session_snapshot_count=len(comparison.session_snapshot_ids),
        aligned_hour_local_labels=comparison.aligned_hour_local_labels,
        bus_speed_mps_median_by_hour=comparison.bus_speed_mps_median_by_hour,
        bus_segment_support_by_hour=comparison.bus_segment_support_by_hour,
        dft_share_by_hour=comparison.dft_share_by_hour,
        hours_excluded_for_support=comparison.hours_excluded_for_support,
        excluded_hour_segment_support=tuple(
            support.get(hour, 0) for hour in comparison.hours_excluded_for_support
        ),
        spearman_rho=comparison.spearman_rho,
        spearman_pair_count=comparison.spearman_pair_count,
        limitations=STANDING_LIMITATIONS,
    )


def write_comparison_report(
    report: BusDftComparisonReport,
    output_directory: Path,
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Write the JSON artifact and the markdown report; return what was written."""

    directory = Path(output_directory)
    json_path = directory / JSON_OUTPUT_NAME
    markdown_path = directory / MARKDOWN_OUTPUT_NAME
    if not overwrite:
        for path in (json_path, markdown_path):
            if path.exists():
                raise BusDftComparisonReportError(
                    f"{path} already exists; pass --overwrite to replace it"
                )
    try:
        directory.mkdir(parents=True, exist_ok=True)
        json_path.write_text(f"{report.model_dump_json(indent=2)}\n", encoding="utf-8")
        markdown_path.write_text(render_comparison_markdown(report), encoding="utf-8")
    except OSError as error:
        raise BusDftComparisonReportError(f"the report could not be written: {error}") from error
    return [json_path, markdown_path]


def render_comparison_markdown(report: BusDftComparisonReport) -> str:
    """Render the human-readable comparison report."""

    lines = [
        "# Bus progression versus DfT hourly shape",
        "",
        "Two independently observed hourly shapes for one city, set beside each other and",
        "described. Neither series is a control for the other, no threshold is applied, and",
        "no significance test was performed.",
        "",
        "## Provenance",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Report version | `{report.report_version}` |",
        f"| DfT edgeData file | `{report.dft_edgedata_name}` |",
        f"| DfT edgeData SHA-256 | `{report.dft_source_sha256}` |",
        f"| DfT total entries in window | {report.dft_total_entered:,} |",
        f"| Declared UTC-to-local offset | {report.utc_to_local_offset_hours:+d} h |",
        f"| Support gate | {report.minimum_segments_per_hour} segments per hour |",
        f"| Session snapshots contributing | {report.session_snapshot_count} |",
        f"| Research status | `{report.research_status}` |",
        "",
        "Snapshot ids are quarantine locators and are not published here; the count above is",
        "the aggregate. The workspace path was supplied on the command line and is not",
        "recorded in either written file.",
        "",
        "## Aligned hours",
        "",
    ]
    if report.aligned_hour_local_labels:
        lines.extend(
            [
                "| Local hour | Bus median progression speed (m/s) | Bus segment support | "
                "DfT share of window entries |",
                "|---|---|---|---|",
            ]
        )
        for hour, speed, segments, share in zip(
            report.aligned_hour_local_labels,
            report.bus_speed_mps_median_by_hour,
            report.bus_segment_support_by_hour,
            report.dft_share_by_hour,
            strict=True,
        ):
            lines.append(f"| {hour:02d} | {speed:.3f} | {segments} | {share:.4f} |")
    else:
        lines.append(
            "No hour cleared the support gate, so no hour is aligned. That is the finding, "
            "not a failure to report one."
        )
    lines.extend(["", "## Hours excluded for support", ""])
    if report.hours_excluded_for_support:
        lines.extend(
            [
                "| Local hour | Bus segments observed | Support gate |",
                "|---|---|---|",
            ]
        )
        for hour, segments in zip(
            report.hours_excluded_for_support,
            report.excluded_hour_segment_support,
            strict=True,
        ):
            lines.append(f"| {hour:02d} | {segments} | {report.minimum_segments_per_hour} |")
        lines.extend(
            [
                "",
                "These hours were observed but carried too few bus segments to summarise, so "
                "they are excluded from the alignment and reported with the support they had.",
            ]
        )
    else:
        lines.append("Every hour present in both sources cleared the support gate.")
    lines.extend(["", "## Rank correlation", ""])
    if report.spearman_rho is None:
        lines.append(
            "No Spearman value is reported: the alignment needs at least three surviving "
            f"hours and {len(report.aligned_hour_local_labels)} survived."
        )
    else:
        lines.append(
            f"Spearman rank correlation `{report.spearman_rho:+.4f}` over "
            f"{report.spearman_pair_count} aligned hours, between the bus median progression "
            "speed and the DfT share of window entries."
        )
        lines.append("")
        lines.append(
            "This is a rank correlation between two observed shapes and nothing more. It is "
            "not a significance statement, not an effect size, and not evidence that either "
            "series accounts for the other."
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.append("")
    return "\n".join(lines)


def _load_progression(workspace: Path) -> SessionProgressionMeasurement:
    """Load the workspace's progression artifact, refusing anything not aggregate-only."""

    directory = workspace / MANCHESTER_SUBDIRECTORY
    if not directory.is_dir():
        raise BusDftComparisonReportError(
            f"this workspace has no {MANCHESTER_SUBDIRECTORY}/ directory, so no attended "
            f"bus session has been recorded into it: {directory}"
        )
    path = directory / PROGRESSION_ARTIFACT_NAME
    if not path.is_file():
        raise BusDftComparisonReportError(
            f"no hourly progression measurement at {path}. The comparison needs one; no "
            "attended-session runner writes this artifact yet, so its absence is the "
            "normal state rather than a session failure."
        )
    if path.stat().st_size > _MAX_ARTIFACT_BYTES:
        raise BusDftComparisonReportError(
            f"{path} exceeds the bounded read size and was not opened"
        )
    try:
        # The strict frozen base refuses python-dict tuples, so the artifact
        # validates through JSON mode exactly as it was persisted.
        measurement = SessionProgressionMeasurement.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as error:
        raise BusDftComparisonReportError(
            f"{path} could not be read as a valid progression measurement: {str(error)[:300]}"
        ) from error
    if not (measurement.aggregates_only and not measurement.raw_identifiers_published):
        raise BusDftComparisonReportError(
            f"{path} does not declare itself aggregate-only, so it was refused"
        )
    return measurement


def _load_shape(edgedata_path: Path) -> DftHourlyShape:
    """Reduce the committed edgeData counts to their hourly shape."""

    try:
        return load_dft_hourly_shape(edgedata_path)
    except BodsSessionIdentityError as error:
        raise BusDftComparisonReportError(
            f"{edgedata_path} could not be reduced to an hourly shape: {error}"
        ) from error


def _compare(
    progression: SessionProgressionMeasurement,
    shape: DftHourlyShape,
    *,
    utc_to_local_offset_hours: int,
    minimum_segments_per_hour: int | None,
) -> BusDftShapeComparison:
    """Call the accepted comparison, letting its own default gate stand when unset."""

    try:
        if minimum_segments_per_hour is None:
            return compare_bus_progression_to_dft_shape(
                progression, shape, utc_to_local_offset_hours=utc_to_local_offset_hours
            )
        return compare_bus_progression_to_dft_shape(
            progression,
            shape,
            utc_to_local_offset_hours=utc_to_local_offset_hours,
            minimum_segments_per_hour=minimum_segments_per_hour,
        )
    except (BodsSessionIdentityError, ValidationError, ValueError) as error:
        raise BusDftComparisonReportError(
            f"the accepted comparison refused these inputs: {str(error)[:300]}"
        ) from error


def _support_by_local_hour(
    progression: SessionProgressionMeasurement, *, utc_to_local_offset_hours: int
) -> dict[int, int]:
    """Map each local clock hour to the bus segment count observed in it.

    The accepted comparison records *which* hours it excluded but not how much
    support they had. This re-presents the counts already in the progression
    artifact using the same local-hour mapping the comparison applies, so an
    excluded hour is reported with its evidence rather than only its label.
    """

    return {
        (hour_utc + utc_to_local_offset_hours) % 24: segments
        for hour_utc, segments in zip(
            progression.hour_utc, progression.segment_count_by_hour, strict=True
        )
    }


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
