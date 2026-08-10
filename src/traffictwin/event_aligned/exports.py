"""Deterministic JSON and CSV exports for event-aligned analysis."""

from __future__ import annotations

import csv
import io
import json

from traffictwin.event_aligned.models import EventAlignedReport


def export_report_json(report: EventAlignedReport) -> str:
    """Return deterministic JSON export (portable, wall-clock independent)."""

    data = report.to_portable_dict()
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )  # noqa: E501


def export_report_json_pretty(report: EventAlignedReport) -> str:
    """Return pretty JSON for human inspection (still deterministic)."""

    data = report.to_portable_dict()
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)


def export_points_csv(report: EventAlignedReport) -> str:
    """Return tabular CSV for relative-time metric points.

    One row per bin. Missing values are empty, not zero-filled.
    """

    output = io.StringIO()
    fieldnames = [
        "run_id",
        "phase",
        "bin_index",
        "relative_start_s",
        "relative_end_s",
        "absolute_window_start_utc",
        "absolute_window_end_utc",
        "coverage_state",
        "coverage_fraction",
        "metric_key",
        "metric_version",
        "metric_unit",
        "status",
        "value",
        "reason_codes",
        "source_record_counts",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for point in sorted(report.metric_points, key=lambda p: (p.run_id, p.bin_index)):
        writer.writerow(
            {
                "run_id": point.run_id,
                "phase": point.phase.value,
                "bin_index": point.bin_index,
                "relative_start_s": point.relative_start_s,
                "relative_end_s": point.relative_end_s,
                "absolute_window_start_utc": point.absolute_window_start_utc.isoformat().replace(
                    "+00:00", "Z"
                ),
                "absolute_window_end_utc": point.absolute_window_end_utc.isoformat().replace(
                    "+00:00", "Z"
                ),
                "coverage_state": point.coverage_state.value,
                "coverage_fraction": point.coverage_fraction,
                "metric_key": point.metric_key,
                "metric_version": point.metric_version,
                "metric_unit": point.metric_unit,
                "status": point.status,
                "value": "" if point.value is None else point.value,
                "reason_codes": ";".join(point.reason_codes),
                "source_record_counts": json.dumps(
                    point.source_record_counts, sort_keys=True, separators=(",", ":")
                ),
            }
        )
    return output.getvalue()


def export_phase_summaries_csv(report: EventAlignedReport) -> str:
    """Return CSV for before/during/after summaries."""

    output = io.StringIO()
    fieldnames = [
        "run_id",
        "phase",
        "metric_key",
        "metric_version",
        "metric_unit",
        "bin_count",
        "available_count",
        "empty_count",
        "partial_count",
        "mean_value",
        "min_value",
        "max_value",
        "median_value",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for summary in sorted(report.phase_summaries, key=lambda s: (s.run_id, s.phase.value)):
        writer.writerow(
            {
                "run_id": summary.run_id,
                "phase": summary.phase.value,
                "metric_key": summary.metric_key,
                "metric_version": summary.metric_version,
                "metric_unit": summary.metric_unit,
                "bin_count": summary.bin_count,
                "available_count": summary.available_count,
                "empty_count": summary.empty_count,
                "partial_count": summary.partial_count,
                "mean_value": "" if summary.mean_value is None else summary.mean_value,
                "min_value": "" if summary.min_value is None else summary.min_value,
                "max_value": "" if summary.max_value is None else summary.max_value,
                "median_value": "" if summary.median_value is None else summary.median_value,
            }
        )
    return output.getvalue()
