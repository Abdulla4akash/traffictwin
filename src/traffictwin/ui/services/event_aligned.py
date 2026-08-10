"""UI service for event-aligned analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from traffictwin.event_aligned.exports import (
    export_phase_summaries_csv,
    export_points_csv,
    export_report_json,
)
from traffictwin.event_aligned.models import (
    EventAlignedReport,
    EventAlignedWindowSpec,
    EventAnchor,
    EventAnchorKind,
)
from traffictwin.event_aligned.service import build_event_aligned_report
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.catalogue import METRIC_DEFINITIONS, window_metric_catalogue
from traffictwin.ui.services.models import ServiceError


def _parse_anchor_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        msg = f"anchor timestamp must be ISO8601 with timezone: {exc}"
        raise ValueError(msg) from exc
    if dt.tzinfo is None:
        msg = "anchor timestamp must be timezone-aware; naive timestamps are rejected"
        raise ValueError(msg)
    return dt.astimezone(UTC)


def compute_event_aligned_for_ui(
    *,
    bundle_paths: list[str],
    metric_key: str,
    pre_duration_s: float,
    event_duration_s: float,
    post_duration_s: float,
    bin_width_s: float,
    anchor_kind: str,
    anchor_timestamps: list[str],
    anchor_labels: list[str] | None = None,
    report_id: str | None = None,
) -> EventAlignedReport | ServiceError:
    """Validate UI inputs and build the deterministic event-aligned report."""

    if not (2 <= len(bundle_paths) <= 8):
        return ServiceError(
            "Event-aligned analysis requires 2 to 8 bundles.", "Select 2-8 compatible runs"
        )
    if len(anchor_timestamps) != len(bundle_paths):
        return ServiceError("Anchor count must match bundle count.", "Provide one anchor per run")
    try:
        # Validate metric via public window catalogue (not private _WINDOW_ANCHORS_BY_KEY)
        window_keys = set(window_metric_catalogue())
        if metric_key not in window_keys:
            return ServiceError(
                f"Metric {metric_key!r} is not window-applicable.",
                "Choose a window-applicable metric",
            )
        definition = METRIC_DEFINITIONS.get(metric_key)
        if definition is None:
            return ServiceError(
                f"Unsupported metric: {metric_key}", "Choose a window-applicable metric"
            )
        spec = EventAlignedWindowSpec(
            pre_duration_s=float(pre_duration_s),
            event_duration_s=float(event_duration_s),
            post_duration_s=float(post_duration_s),
            bin_width_s=float(bin_width_s),
            metric_key=metric_key,
            metric_version=definition.implementation_version,
            metric_unit=definition.unit,
            metric_human_name=definition.human_name,
        )
        # Preflight total bins before building (reuse windowed.py pattern)
        total = spec.total_bins()
        if total > spec.max_bins:
            return ServiceError(
                f"Window request resolves to {total} bins; configured maximum is {spec.max_bins}.",
                "Reduce durations or increase bin width",
            )
        kind = EventAnchorKind(anchor_kind)
        runs_with_anchors: list[tuple[object, EventAnchor]] = []
        for idx, path_str in enumerate(bundle_paths):
            path = Path(path_str)
            if not path.exists():
                return ServiceError(f"Bundle path does not exist: {path}", str(path))
            result = validate_bundle(path)
            if result.manifest is None:
                return ServiceError(f"Bundle manifest missing for {path}", str(path))
            ts_str = anchor_timestamps[idx]
            anchor_dt = _parse_anchor_datetime(ts_str)
            label = (
                anchor_labels[idx]
                if anchor_labels and idx < len(anchor_labels)
                else kind.authored_label
            )
            if "observed" in label.lower():
                return ServiceError("Authored anchors must not be labelled observed.", label)
            anchor = EventAnchor(
                kind=kind,
                anchor_time_utc=anchor_dt,
                source_label=label,
                provenance_detail=f"UI selection for run {result.manifest.run.run_id}",
                run_id=result.manifest.run.run_id,
                bundle_id=result.manifest.bundle.bundle_id,
            )
            runs_with_anchors.append((result, anchor))
        report = build_event_aligned_report(
            runs_with_anchors,  # type: ignore[arg-type]
            spec,
            report_id=report_id,
        )
        return report
    except (ValueError, ValidationError) as exc:
        return ServiceError("Event-aligned analysis could not be built.", str(exc))


def event_aligned_json_for_ui(report: EventAlignedReport) -> str:
    return export_report_json(report)


def event_aligned_points_csv_for_ui(report: EventAlignedReport) -> str:
    return export_points_csv(report)


def event_aligned_summaries_csv_for_ui(report: EventAlignedReport) -> str:
    return export_phase_summaries_csv(report)
