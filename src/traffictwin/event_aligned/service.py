"""Deterministic event-aligned analysis service reusing the fixed-window metric engine."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.event_aligned.models import (
    CoverageState,
    EventAlignedMetricPoint,
    EventAlignedPhase,
    EventAlignedPhaseSummary,
    EventAlignedReport,
    EventAlignedRun,
    EventAlignedWindowSpec,
    EventAnchor,
    ExcludedRun,
    PairwiseDelta,
)
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.catalogue import METRIC_DEFINITIONS, window_metric_catalogue
from traffictwin.metrics.definitions import MetricDefinition
from traffictwin.metrics.engine import compute_metrics, run_context_from_bundle, utc_now
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricStatus

SCHEMA_VERSION: str = "1.0"
CANONICAL_TIME_BASIS = "utc_bundle_created_at_offset_v1"


def _require_aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None:
        msg = f"{label} must be timezone-aware; naive timestamps are rejected"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _bundle_created_at_utc(result: BundleValidationResult) -> datetime:
    if result.manifest is None:
        msg = "bundle manifest is missing; time basis unavailable"
        raise ValueError(msg)
    created = result.manifest.bundle.created_at
    if created is None:
        msg = "bundle.created_at is missing; time basis unavailable"
        raise ValueError(msg)
    if created.tzinfo is None:
        msg = "bundle.created_at must be timezone-aware; naive time basis rejected"
        raise ValueError(msg)
    return created.astimezone(UTC)


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _source_time_range_seconds(tables: CanonicalTables) -> tuple[float, float] | None:
    times = [
        *(record.arrival_time_s for record in tables.tasks),
        *(record.timestamp_s for record in tables.infrastructure),
        *(record.timestamp_s for record in tables.vehicles),
        *(record.timestamp_s for record in tables.traffic),
        *(record.departure_time_s for record in tables.trips),
        *(record.timestamp_s for record in tables.incidents),
    ]
    if not times:
        return None
    return (min(times), max(times))


def _filter_tables_for_absolute_window(
    tables: CanonicalTables,
    bundle_created_at: datetime,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> CanonicalTables:
    """Filter canonical records whose absolute time falls in [start, end)."""

    start = _decimal((window_start_utc - bundle_created_at).total_seconds())
    end = _decimal((window_end_utc - bundle_created_at).total_seconds())

    def admitted(value: float) -> bool:
        ts = _decimal(value)
        return start <= ts < end

    return CanonicalTables(
        tasks=[r for r in tables.tasks if admitted(r.arrival_time_s)],
        infrastructure=[r for r in tables.infrastructure if admitted(r.timestamp_s)],
        vehicles=[r for r in tables.vehicles if admitted(r.timestamp_s)],
        traffic=[r for r in tables.traffic if admitted(r.timestamp_s)],
        trips=[r for r in tables.trips if admitted(r.departure_time_s)],
        incidents=[r for r in tables.incidents if admitted(r.timestamp_s)],
    )


def _metric_definition_for_key(metric_key: str) -> MetricDefinition:
    definition = METRIC_DEFINITIONS.get(metric_key)
    if definition is None:
        msg = f"unsupported metric_key: {metric_key!r}"
        raise ValueError(msg)
    return definition


def _build_bins_for_spec(
    spec: EventAlignedWindowSpec, anchor_utc: datetime
) -> list[dict[str, object]]:
    """Return deterministic bins across pre/event/post phases."""

    _require_aware(anchor_utc, "anchor_time_utc")
    # Preflight: check total bins before materialisation (reuse windowed.py pattern)
    total = spec.total_bins()
    if not math.isfinite(total) or total <= 0:
        msg = "total_bins must be finite positive"
        raise ValueError(msg)
    if total > spec.max_bins:
        msg = f"window request resolves to {total} bins; configured maximum is {spec.max_bins}"
        raise ValueError(msg)
    anchor = anchor_utc.astimezone(UTC)
    bins: list[dict[str, object]] = []
    bin_index = 0

    def add_phase(
        phase: EventAlignedPhase,
        phase_relative_start: float,
        phase_relative_end: float,
    ) -> None:
        nonlocal bin_index
        duration = phase_relative_end - phase_relative_start
        width_dec = _decimal(spec.bin_width_s)
        start_dec = _decimal(phase_relative_start)
        end_dec = _decimal(phase_relative_end)
        total_phase = math.ceil(duration / spec.bin_width_s)
        for i in range(total_phase):
            rel_start_dec = start_dec + Decimal(i) * width_dec
            rel_end_dec = rel_start_dec + width_dec
            if rel_end_dec > end_dec:
                rel_end_dec = end_dec
            rel_start = float(rel_start_dec)
            rel_end = float(rel_end_dec)
            coverage = float((rel_end_dec - rel_start_dec) / width_dec) if width_dec != 0 else 0.0
            abs_start = anchor + timedelta(seconds=rel_start)
            abs_end = anchor + timedelta(seconds=rel_end)
            bins.append(
                {
                    "phase": phase,
                    "bin_index": bin_index,
                    "relative_start_s": rel_start,
                    "relative_end_s": rel_end,
                    "absolute_start_utc": abs_start,
                    "absolute_end_utc": abs_end,
                    "coverage_fraction": coverage,
                    "is_partial": coverage < 1.0 - 1e-9,
                }
            )
            bin_index += 1

    add_phase(EventAlignedPhase.PRE, -spec.pre_duration_s, 0.0)
    add_phase(EventAlignedPhase.EVENT, 0.0, spec.event_duration_s)
    add_phase(
        EventAlignedPhase.POST, spec.event_duration_s, spec.event_duration_s + spec.post_duration_s
    )
    return bins


def build_event_aligned_report(
    runs_with_anchors: list[tuple[BundleValidationResult, EventAnchor]],
    spec: EventAlignedWindowSpec,
    *,
    report_id: str | None = None,
    clock: Callable[[], datetime] = utc_now,
    metric_engine_config: MetricEngineConfig | None = None,
) -> EventAlignedReport:
    """Build a deterministic event-aligned report reusing the fixed-window metric engine."""

    if not (2 <= len(runs_with_anchors) <= 8):
        msg = "event-aligned analysis requires between 2 and 8 runs"
        raise ValueError(msg)

    for _, anchor in runs_with_anchors:
        _require_aware(anchor.anchor_time_utc, "anchor_time_utc")
        if not anchor.kind.is_authored:
            msg = "anchor kind must be authored, not observed"
            raise ValueError(msg)
        if "observed" in anchor.source_label.lower():
            msg = "authored anchors must not be labelled observed"
            raise ValueError(msg)

    definition = _metric_definition_for_key(spec.metric_key)
    # Engine-contract compatibility: validate spec against authoritative definition once
    if spec.metric_version != definition.implementation_version:
        msg = (
            f"spec metric_version {spec.metric_version!r} does not match authoritative "
            f"implementation_version {definition.implementation_version!r} for metric {spec.metric_key!r}"  # noqa: E501
        )
        raise ValueError(msg)
    if spec.metric_unit != definition.unit:
        msg = (
            f"spec metric_unit {spec.metric_unit!r} does not match authoritative unit {definition.unit!r} "  # noqa: E501
            f"for metric {spec.metric_key!r}"
        )
        raise ValueError(msg)
    # Window-eligibility guard using public catalogue
    window_keys = set(window_metric_catalogue())
    if spec.metric_key not in window_keys or not definition.time_window_applicable:
        msg = f"metric {spec.metric_key!r} is not window-applicable"
        raise ValueError(msg)

    # Preflight total bins before any materialisation
    total_bins = spec.total_bins()
    if total_bins > spec.max_bins:
        msg = f"window request resolves to {total_bins} bins; configured maximum is {spec.max_bins}"
        raise ValueError(msg)
    # Overall report expansion bound
    if total_bins * len(runs_with_anchors) > 100_000:
        msg = f"report would contain {total_bins * len(runs_with_anchors)} bins; exceeds overall limit 100000"  # noqa: E501
        raise ValueError(msg)

    engine_config = metric_engine_config or MetricEngineConfig(metric_version=spec.metric_version)

    warnings: list[str] = [
        "Windows use [start, end). Coverage is requested-bin overlap, not inferred sensor completeness.",  # noqa: E501
        "No interpolation is performed; missing bins remain unavailable and are never zero-filled.",
        "Differences are descriptive during the declared event window, not causal effects.",
        "Manual timestamps and authored incidents are labelled authored anchors, not observed incidents.",  # noqa: E501
        "Canonical time basis is utc_bundle_created_at_offset_v1; timestamps are seconds offset from bundle created_at.",  # noqa: E501
        "All runs are re-evaluated under the single current engine contract; spec validated against authoritative metric definition. Denominator is the metric's documented required evidence per definition.",  # noqa: E501
    ]
    limitations = [
        "Event-aligned analysis reuses the existing fixed-window metric engine; it does not implement a second metric calculation.",  # noqa: E501
        "Task, infrastructure, traffic, trip and incident records are assigned to windows by arrival/departure/timestamp as defined in the existing window anchor policy.",  # noqa: E501
        "Pairwise deltas are descriptive differences during the declared event window; they do not claim recovery, clearance, or causal impact. PARTIAL numeric values are included in summaries while retaining PARTIAL status; see summary warnings.",  # noqa: E501
        "Smoothing or interpolation is not applied; empty bins remain visible with unavailable status.",  # noqa: E501
    ]

    accepted_runs: list[EventAlignedRun] = []
    excluded_runs: list[ExcludedRun] = []
    metric_points: list[EventAlignedMetricPoint] = []
    phase_summaries: list[EventAlignedPhaseSummary] = []

    valid_entries: list[tuple[BundleValidationResult, EventAnchor]] = []

    for result, anchor in runs_with_anchors:
        run_id = result.manifest.run.run_id if result.manifest else anchor.run_id or "unknown"
        bundle_id = result.manifest.bundle.bundle_id if result.manifest else anchor.bundle_id
        if result.manifest is None:
            excluded_runs.append(
                ExcludedRun(
                    run_id=run_id,
                    bundle_id=bundle_id,
                    bundle_fingerprint=result.fingerprint,
                    reason_code="INVALID_MANIFEST",
                    reason_detail="bundle manifest is missing",
                    anchor=anchor,
                )
            )
            continue
        # Time basis must be timezone-aware
        try:
            bundle_created_at = _bundle_created_at_utc(result)
        except ValueError as exc:
            excluded_runs.append(
                ExcludedRun(
                    run_id=run_id,
                    bundle_id=bundle_id,
                    bundle_fingerprint=result.fingerprint,
                    reason_code="INVALID_TIME_BASIS",
                    reason_detail=str(exc),
                    anchor=anchor,
                )
            )
            continue
        time_range = _source_time_range_seconds(result.canonical)
        if time_range is None:
            excluded_runs.append(
                ExcludedRun(
                    run_id=run_id,
                    bundle_id=bundle_id,
                    bundle_fingerprint=result.fingerprint,
                    reason_code="INSUFFICIENT_TEMPORAL_RANGE",
                    reason_detail="no canonical timestamps available to evaluate aligned windows",
                    anchor=anchor,
                )
            )
            continue
        valid_entries.append((result, anchor))

    per_run_available_values: dict[str, dict[EventAlignedPhase, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    per_run_bin_counts: dict[str, dict[EventAlignedPhase, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"bin_count": 0, "available": 0, "empty": 0, "partial": 0})
    )

    for result, anchor in valid_entries:
        run_id = result.manifest.run.run_id if result.manifest else anchor.run_id or "unknown"
        bundle_id = result.manifest.bundle.bundle_id if result.manifest else anchor.bundle_id
        bundle_fingerprint = result.fingerprint
        experiment_id = result.manifest.run.experiment_id if result.manifest else None
        seed_id = result.manifest.run.seed_id if result.manifest else None
        algorithm = result.manifest.run.algorithm if result.manifest else None
        bundle_created_at = _bundle_created_at_utc(result)
        time_range = _source_time_range_seconds(result.canonical)
        bins = _build_bins_for_spec(spec, anchor.anchor_time_utc)
        accepted_runs.append(
            EventAlignedRun(
                run_id=run_id,
                bundle_id=bundle_id,
                bundle_fingerprint=bundle_fingerprint,
                experiment_id=experiment_id,
                seed_id=seed_id,
                algorithm=algorithm,
                anchor=anchor,
                time_coverage_s=time_range,
                warnings=[],
                source_record_counts=result.canonical.record_counts(),
            )
        )
        # Hoist per-run immutable state before bin loop
        run_context = run_context_from_bundle(result)
        evidence = result.evidence
        for b in bins:
            phase: EventAlignedPhase = b["phase"]  # type: ignore
            rel_start: float = b["relative_start_s"]  # type: ignore
            rel_end: float = b["relative_end_s"]  # type: ignore
            abs_start: datetime = b["absolute_start_utc"]  # type: ignore
            abs_end: datetime = b["absolute_end_utc"]  # type: ignore
            coverage_fraction: float = b["coverage_fraction"]  # type: ignore
            is_partial: bool = b["is_partial"]  # type: ignore
            filtered = _filter_tables_for_absolute_window(
                result.canonical, bundle_created_at, abs_start, abs_end
            )
            counts = filtered.record_counts()
            total_records = sum(counts.values())
            if total_records == 0:
                coverage_state = CoverageState.EMPTY
            elif is_partial:
                coverage_state = CoverageState.PARTIAL
            else:
                coverage_state = CoverageState.COMPLETE
            collection = compute_metrics(
                filtered,
                run_context,
                evidence,
                engine_config,
                clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
            )
            by_key = collection.by_key()
            metric_value = by_key.get(spec.metric_key)
            if metric_value is None:
                status = "unavailable"
                value = None
                reason_codes = ["METRIC_NOT_FOUND"]
                warnings_bin: list[str] = []
            else:
                if metric_value.status == MetricStatus.AVAILABLE:
                    status = "available"
                elif metric_value.status == MetricStatus.PARTIAL:
                    status = "partial"
                elif metric_value.status == MetricStatus.INVALID:
                    status = "invalid"
                else:
                    status = "unavailable"
                # Preserve numeric for AVAILABLE and PARTIAL
                if status in ("available", "partial") and isinstance(
                    metric_value.value, (int, float)
                ):
                    # Ensure finite
                    v = float(metric_value.value)
                    import math

                    value = v if math.isfinite(v) else None
                else:
                    value = None
                reason_codes = [rc.value for rc in metric_value.reason_codes]
                warnings_bin = list(metric_value.warnings)
            point = EventAlignedMetricPoint(
                run_id=run_id,
                phase=phase,
                bin_index=int(b["bin_index"]),  # type: ignore
                relative_start_s=float(rel_start),
                relative_end_s=float(rel_end),
                absolute_window_start_utc=abs_start,
                absolute_window_end_utc=abs_end,
                coverage_state=coverage_state,
                coverage_fraction=float(coverage_fraction),
                source_record_counts=counts,
                metric_key=spec.metric_key,
                metric_version=spec.metric_version,
                metric_unit=spec.metric_unit,
                status=status,
                value=float(value) if isinstance(value, (int, float)) else None,
                reason_codes=reason_codes,
                warnings=warnings_bin,
            )
            metric_points.append(point)
            per_run_bin_counts[run_id][phase]["bin_count"] += 1
            # Numeric summaries include both AVAILABLE and PARTIAL with numeric value
            if status in ("available", "partial") and value is not None:
                per_run_available_values[run_id][phase].append(float(value))
                if status == "available":
                    per_run_bin_counts[run_id][phase]["available"] += 1
                else:
                    per_run_bin_counts[run_id][phase]["partial"] += 1
            elif status == "available":
                per_run_bin_counts[run_id][phase]["available"] += 1
            elif status == "partial":
                per_run_bin_counts[run_id][phase]["partial"] += 1
            if coverage_state == CoverageState.EMPTY:
                per_run_bin_counts[run_id][phase]["empty"] += 1
            if coverage_state == CoverageState.PARTIAL:
                per_run_bin_counts[run_id][phase]["partial"] += 1

    for run_id, phase_map in list(per_run_available_values.items()):
        for phase in EventAlignedPhase:
            bin_counts = per_run_bin_counts[run_id][phase]
            values = phase_map.get(phase, [])
            if bin_counts["bin_count"] == 0:
                relevant = [p for p in metric_points if p.run_id == run_id and p.phase == phase]
                if relevant:
                    bin_counts["bin_count"] = len(relevant)
                    bin_counts["empty"] = sum(
                        1 for p in relevant if p.coverage_state == CoverageState.EMPTY
                    )
                    bin_counts["partial"] = sum(
                        1 for p in relevant if p.coverage_state == CoverageState.PARTIAL
                    )
                    bin_counts["available"] = sum(1 for p in relevant if p.status == "available")
                else:
                    continue
            if values:
                mean_val = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                median_val = (
                    sorted_vals[n // 2]
                    if n % 2 == 1
                    else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0
                )
                summary_warnings: list[str] = []
                if any(
                    p.status == "partial" and p.value is not None
                    for p in metric_points
                    if p.run_id == run_id and p.phase == phase
                ):
                    summary_warnings.append(
                        "Partial numeric values included in mean/min/max/median."
                    )  # noqa: E501
            else:
                mean_val = None
                min_val = None
                max_val = None
                median_val = None
                summary_warnings = [
                    f"No available numeric values for {phase.value} (partial values also absent)."
                ]
            phase_summaries.append(
                EventAlignedPhaseSummary(
                    run_id=run_id,
                    phase=phase,
                    metric_key=spec.metric_key,
                    metric_version=spec.metric_version,
                    metric_unit=spec.metric_unit,
                    bin_count=bin_counts["bin_count"],
                    available_count=bin_counts["available"],
                    empty_count=bin_counts["empty"],
                    partial_count=bin_counts["partial"],
                    mean_value=mean_val,
                    min_value=min_val,
                    max_value=max_val,
                    median_value=median_val,
                    warnings=summary_warnings,
                )
            )
    accepted_ids = {r.run_id for r in accepted_runs}
    for run_id in accepted_ids:
        for phase in EventAlignedPhase:
            if any(s.run_id == run_id and s.phase == phase for s in phase_summaries):
                continue
            relevant = [p for p in metric_points if p.run_id == run_id and p.phase == phase]
            if not relevant:
                continue
            bin_count = len(relevant)
            available = sum(1 for p in relevant if p.status == "available")
            empty = sum(1 for p in relevant if p.coverage_state == CoverageState.EMPTY)
            partial = sum(1 for p in relevant if p.coverage_state == CoverageState.PARTIAL)
            phase_summaries.append(
                EventAlignedPhaseSummary(
                    run_id=run_id,
                    phase=phase,
                    metric_key=spec.metric_key,
                    metric_version=spec.metric_version,
                    metric_unit=spec.metric_unit,
                    bin_count=bin_count,
                    available_count=available,
                    empty_count=empty,
                    partial_count=partial,
                    mean_value=None,
                    min_value=None,
                    max_value=None,
                    median_value=None,
                    warnings=[f"No available numeric values for {phase.value}"],
                )
            )

    pairwise_deltas: list[PairwiseDelta] = []
    accepted_sorted = sorted(accepted_runs, key=lambda r: r.run_id)
    summary_map: dict[tuple[str, EventAlignedPhase], EventAlignedPhaseSummary] = {
        (s.run_id, s.phase): s for s in phase_summaries
    }
    for i, baseline in enumerate(accepted_sorted):
        for variation in accepted_sorted[i + 1 :]:
            for phase in EventAlignedPhase:
                base_summary = summary_map.get((baseline.run_id, phase))
                var_summary = summary_map.get((variation.run_id, phase))
                if base_summary is None or var_summary is None:
                    continue
                if base_summary.mean_value is None or var_summary.mean_value is None:
                    continue
                absolute = var_summary.mean_value - base_summary.mean_value
                if base_summary.mean_value != 0:
                    relative = absolute / base_summary.mean_value
                else:
                    relative = None
                description = (
                    f"Difference during the declared {phase.value} window: "
                    f"{variation.run_id} mean {var_summary.mean_value:.4f} "
                    f"compared with {baseline.run_id} mean {base_summary.mean_value:.4f} "
                    f"(absolute difference {absolute:.4f})"
                )
                pairwise_deltas.append(
                    PairwiseDelta(
                        baseline_run_id=baseline.run_id,
                        variation_run_id=variation.run_id,
                        metric_key=spec.metric_key,
                        metric_version=spec.metric_version,
                        metric_unit=spec.metric_unit,
                        phase=phase,
                        baseline_mean=base_summary.mean_value,
                        variation_mean=var_summary.mean_value,
                        absolute_difference=absolute,
                        relative_difference=relative,
                        description=description,
                        warnings=[],
                    )
                )

    accepted_runs_sorted = sorted(accepted_runs, key=lambda r: r.run_id)
    excluded_runs_sorted = sorted(excluded_runs, key=lambda r: r.run_id)
    metric_points_sorted = sorted(metric_points, key=lambda p: (p.run_id, p.bin_index))
    phase_summaries_sorted = sorted(phase_summaries, key=lambda s: (s.run_id, s.phase.value))
    pairwise_deltas_sorted = sorted(
        pairwise_deltas, key=lambda d: (d.baseline_run_id, d.variation_run_id, d.phase.value)
    )
    warnings_sorted = sorted(set(warnings))
    limitations_sorted = sorted(set(limitations))
    tmp_report_id = report_id or f"event-aligned-{spec.metric_key}-{len(accepted_runs)}runs"
    placeholder = "0" * 64
    created_at = clock()
    _require_aware(created_at, "clock generated_at")
    report_without_fp = EventAlignedReport(
        schema_version="1.0",
        report_id=tmp_report_id,
        canonical_time_basis=CANONICAL_TIME_BASIS,
        spec=spec,
        accepted_runs=accepted_runs_sorted,
        excluded_runs=excluded_runs_sorted,
        metric_points=metric_points_sorted,
        phase_summaries=phase_summaries_sorted,
        pairwise_deltas=pairwise_deltas_sorted,
        warnings=warnings_sorted,
        limitations=limitations_sorted,
        created_at_utc=created_at,
        fingerprint=placeholder,
    )
    fingerprint = report_without_fp.computed_fingerprint()
    final_report = report_without_fp.model_copy(update={"fingerprint": fingerprint})
    return final_report


def preview_exact_windows(
    spec: EventAlignedWindowSpec, anchor: EventAnchor
) -> dict[str, tuple[datetime, datetime]]:
    """Preview exact half-open windows for one anchor."""

    return spec.preview_windows(anchor.anchor_time_utc)
