"""Deterministic fixed-window metric computation over canonical records."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.catalogue import window_metric_catalogue
from traffictwin.metrics.engine import compute_metrics, run_context_from_bundle, utc_now
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import MetricPluginRegistry
from traffictwin.metrics.results import (
    MetricCollection,
    MetricStatus,
    MetricValue,
    RunMetricContext,
)

WINDOWING_SCHEMA_VERSION: Literal["1.0"] = "1.0"
WINDOW_ANCHOR_POLICY_VERSION: Literal["1.0"] = "1.0"

WINDOW_ANCHORS: dict[str, str] = {
    "tasks": "arrival_time_s",
    "infrastructure": "timestamp_s",
    "vehicles": "timestamp_s",
    "traffic": "timestamp_s",
    "trips": "departure_time_s",
    "incidents": "timestamp_s",
}


class WindowingModel(BaseModel):
    """Strict base model for windowed metric artifacts."""

    model_config = ConfigDict(extra="forbid")


class PartialWindowPolicy(StrEnum):
    """Treatment of grid windows only partly covered by the requested interval."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


class WindowRangeSource(StrEnum):
    """How the evaluated temporal range was established."""

    EXPLICIT = "explicit"
    INFERRED_ALIGNED_ENVELOPE = "inferred_aligned_envelope"
    UNAVAILABLE = "unavailable"


class WindowSeriesStatus(StrEnum):
    """Overall status of a windowed metric computation."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class WindowDisposition(StrEnum):
    """Whether one intersecting grid window was evaluated."""

    INCLUDED = "included"
    EXCLUDED_PARTIAL = "excluded_partial"


class WindowedMetricConfig(WindowingModel):
    """Versioned fixed-window configuration with explicit edge semantics."""

    schema_version: Literal["1.0"] = WINDOWING_SCHEMA_VERSION
    width_s: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    alignment_origin_s: float = Field(default=0.0, allow_inf_nan=False)
    analysis_start_s: float | None = Field(default=None, allow_inf_nan=False)
    analysis_end_s: float | None = Field(default=None, allow_inf_nan=False)
    partial_window_policy: PartialWindowPolicy = PartialWindowPolicy.INCLUDE
    empty_window_policy: Literal["emit_unavailable"] = "emit_unavailable"
    max_windows: int = Field(default=10_000, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_explicit_range(self) -> WindowedMetricConfig:
        supplied = (self.analysis_start_s is not None, self.analysis_end_s is not None)
        if supplied[0] != supplied[1]:
            raise ValueError("analysis_start_s and analysis_end_s must be supplied together")
        if (
            self.analysis_start_s is not None
            and self.analysis_end_s is not None
            and self.analysis_end_s <= self.analysis_start_s
        ):
            raise ValueError("analysis_end_s must be greater than analysis_start_s")
        return self


class MetricWindow(WindowingModel):
    """One aligned half-open grid window and its requested-range overlap."""

    schema_version: Literal["1.0"] = WINDOWING_SCHEMA_VERSION
    ordinal: int = Field(ge=0)
    grid_index: int
    start_s: float
    end_s: float
    effective_start_s: float
    effective_end_s: float
    width_s: float = Field(gt=0)
    alignment_origin_s: float
    boundary: Literal["[start,end)"] = "[start,end)"
    requested_interval_coverage_fraction: float = Field(ge=0, le=1)
    is_partial: bool


class WindowMetricSlice(WindowingModel):
    """Source counts and optional metrics for one intersecting grid window."""

    schema_version: Literal["1.0"] = WINDOWING_SCHEMA_VERSION
    window: MetricWindow
    disposition: WindowDisposition
    source_record_counts: dict[str, int]
    metrics: MetricCollection | None = None

    @property
    def is_empty(self) -> bool:
        """Return whether no canonical source record falls in the effective interval."""

        return sum(self.source_record_counts.values()) == 0


class WindowedMetricSeries(WindowingModel):
    """Complete deterministic fixed-window artifact for one run."""

    schema_version: Literal["1.0"] = WINDOWING_SCHEMA_VERSION
    anchor_policy_version: Literal["1.0"] = WINDOW_ANCHOR_POLICY_VERSION
    run_id: str
    metric_version: str
    status: WindowSeriesStatus
    config: WindowedMetricConfig
    range_source: WindowRangeSource
    analysis_start_s: float | None
    analysis_end_s: float | None
    source_time_min_s: float | None
    source_time_max_s: float | None
    boundary: Literal["[start,end)"] = "[start,end)"
    coverage_semantics: Literal["requested_interval_overlap_divided_by_grid_width"] = (
        "requested_interval_overlap_divided_by_grid_width"
    )
    empty_window_semantics: Literal["visible_with_metric_unavailability"] = (
        "visible_with_metric_unavailability"
    )
    anchor_fields: dict[str, str]
    applicable_metric_keys: list[str]
    slices: list[WindowMetricSlice]
    included_window_count: int = Field(ge=0)
    excluded_partial_window_count: int = Field(ge=0)
    included_empty_window_count: int = Field(ge=0)
    input_fingerprint: str | None = None
    warnings: list[str]

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)

    def slice_at(self, ordinal: int) -> WindowMetricSlice:
        """Return one slice by stable zero-based ordinal."""

        for item in self.slices:
            if item.window.ordinal == ordinal:
                return item
        raise ValueError(f"window ordinal is not present: {ordinal}")


class WindowLimitExceededError(ValueError):
    """Raised before computation when an explicit request exceeds its window bound."""


def compute_windowed_metrics(
    canonical_tables: CanonicalTables,
    run_context: RunMetricContext,
    evidence_availability: EvidenceAvailability,
    window_config: WindowedMetricConfig,
    metric_config: MetricEngineConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> WindowedMetricSeries:
    """Compute every declared window-applicable metric over fixed aligned intervals."""

    active_metric_config = metric_config or MetricEngineConfig()
    window_plugin_registry = (
        plugin_registry.window_applicable() if plugin_registry is not None else None
    )
    computed_at = clock()
    source_times = _source_times(canonical_tables)
    source_min = min(source_times) if source_times else None
    source_max = max(source_times) if source_times else None
    resolved = _resolve_analysis_range(window_config, source_min, source_max)
    applicable_keys = list(window_metric_catalogue(plugin_registry))
    warnings = [
        "Window coverage is requested-interval overlap, not inferred sampling or sensor "
        "completeness.",
        "Non-additive metrics and boundary-clipped episodes are not expected to recombine into "
        "the whole-run value.",
    ]
    if resolved is None:
        return WindowedMetricSeries(
            run_id=run_context.run_id,
            metric_version=active_metric_config.metric_version,
            status=(
                WindowSeriesStatus.INVALID
                if not run_context.validation_may_import
                else WindowSeriesStatus.UNAVAILABLE
            ),
            config=window_config,
            range_source=WindowRangeSource.UNAVAILABLE,
            analysis_start_s=None,
            analysis_end_s=None,
            source_time_min_s=source_min,
            source_time_max_s=source_max,
            anchor_fields=dict(WINDOW_ANCHORS),
            applicable_metric_keys=applicable_keys,
            slices=[],
            included_window_count=0,
            excluded_partial_window_count=0,
            included_empty_window_count=0,
            input_fingerprint=run_context.source_bundle_fingerprint,
            warnings=[*warnings, "No canonical timestamp was available to infer a window range."],
        )

    analysis_start, analysis_end, range_source = resolved
    windows = _metric_windows(window_config, analysis_start, analysis_end)
    slices: list[WindowMetricSlice] = []
    for window in windows:
        filtered = canonical_tables_for_window(canonical_tables, window)
        counts = filtered.record_counts()
        if window.is_partial and window_config.partial_window_policy is PartialWindowPolicy.EXCLUDE:
            slices.append(
                WindowMetricSlice(
                    window=window,
                    disposition=WindowDisposition.EXCLUDED_PARTIAL,
                    source_record_counts=counts,
                )
            )
            continue
        collection = compute_metrics(
            filtered,
            run_context,
            evidence_availability,
            active_metric_config,
            plugin_registry=window_plugin_registry,
            clock=lambda: computed_at,
        )
        collection = _window_collection(collection, window, applicable_keys)
        slices.append(
            WindowMetricSlice(
                window=window,
                disposition=WindowDisposition.INCLUDED,
                source_record_counts=counts,
                metrics=collection,
            )
        )

    included = [item for item in slices if item.disposition is WindowDisposition.INCLUDED]
    return WindowedMetricSeries(
        run_id=run_context.run_id,
        metric_version=active_metric_config.metric_version,
        status=(
            WindowSeriesStatus.AVAILABLE
            if run_context.validation_may_import
            else WindowSeriesStatus.INVALID
        ),
        config=window_config,
        range_source=range_source,
        analysis_start_s=float(analysis_start),
        analysis_end_s=float(analysis_end),
        source_time_min_s=source_min,
        source_time_max_s=source_max,
        anchor_fields=dict(WINDOW_ANCHORS),
        applicable_metric_keys=applicable_keys,
        slices=slices,
        included_window_count=len(included),
        excluded_partial_window_count=len(slices) - len(included),
        included_empty_window_count=sum(item.is_empty for item in included),
        input_fingerprint=run_context.source_bundle_fingerprint,
        warnings=warnings,
    )


def compute_windowed_metrics_for_bundle(
    result: BundleValidationResult,
    window_config: WindowedMetricConfig,
    metric_config: MetricEngineConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> WindowedMetricSeries:
    """Compute fixed-window metrics from an ordinary validated bundle artifact."""

    return compute_windowed_metrics(
        result.canonical,
        run_context_from_bundle(result),
        result.evidence,
        window_config,
        metric_config,
        plugin_registry=plugin_registry,
        clock=clock,
    )


def canonical_tables_for_window(
    tables: CanonicalTables,
    window: MetricWindow,
) -> CanonicalTables:
    """Return canonical records assigned to one effective half-open interval."""

    start = _decimal(window.effective_start_s)
    end = _decimal(window.effective_end_s)

    def admitted(value: float) -> bool:
        timestamp = _decimal(value)
        return start <= timestamp < end

    return CanonicalTables(
        tasks=[record for record in tables.tasks if admitted(record.arrival_time_s)],
        infrastructure=[record for record in tables.infrastructure if admitted(record.timestamp_s)],
        vehicles=[record for record in tables.vehicles if admitted(record.timestamp_s)],
        traffic=[record for record in tables.traffic if admitted(record.timestamp_s)],
        trips=[record for record in tables.trips if admitted(record.departure_time_s)],
        incidents=[record for record in tables.incidents if admitted(record.timestamp_s)],
    )


def bundle_result_for_window(
    result: BundleValidationResult,
    window: MetricWindow,
) -> BundleValidationResult:
    """Return a read-only bundle view containing only one window's canonical rows."""

    return replace(result, canonical=canonical_tables_for_window(result.canonical, window))


def _resolve_analysis_range(
    config: WindowedMetricConfig,
    source_min: float | None,
    source_max: float | None,
) -> tuple[Decimal, Decimal, WindowRangeSource] | None:
    if config.analysis_start_s is not None and config.analysis_end_s is not None:
        return (
            _decimal(config.analysis_start_s),
            _decimal(config.analysis_end_s),
            WindowRangeSource.EXPLICIT,
        )
    if source_min is None or source_max is None:
        return None
    width = _decimal(config.width_s)
    origin = _decimal(config.alignment_origin_s)
    minimum = _decimal(source_min)
    maximum = _decimal(source_max)
    first_index = _floor_index(minimum, origin, width)
    last_index = _floor_index(maximum, origin, width)
    return (
        origin + Decimal(first_index) * width,
        origin + Decimal(last_index + 1) * width,
        WindowRangeSource.INFERRED_ALIGNED_ENVELOPE,
    )


def _metric_windows(
    config: WindowedMetricConfig,
    analysis_start: Decimal,
    analysis_end: Decimal,
) -> list[MetricWindow]:
    width = _decimal(config.width_s)
    origin = _decimal(config.alignment_origin_s)
    first_index = _floor_index(analysis_start, origin, width)
    last_exclusive_index = int(
        ((analysis_end - origin) / width).to_integral_value(rounding=ROUND_CEILING)
    )
    count = last_exclusive_index - first_index
    if count > config.max_windows:
        raise WindowLimitExceededError(
            f"window request resolves to {count} windows; configured maximum is "
            f"{config.max_windows}"
        )
    windows: list[MetricWindow] = []
    for ordinal, grid_index in enumerate(range(first_index, last_exclusive_index)):
        start = origin + Decimal(grid_index) * width
        end = start + width
        effective_start = max(start, analysis_start)
        effective_end = min(end, analysis_end)
        coverage = (effective_end - effective_start) / width
        windows.append(
            MetricWindow(
                ordinal=ordinal,
                grid_index=grid_index,
                start_s=float(start),
                end_s=float(end),
                effective_start_s=float(effective_start),
                effective_end_s=float(effective_end),
                width_s=float(width),
                alignment_origin_s=float(origin),
                requested_interval_coverage_fraction=float(coverage),
                is_partial=coverage < Decimal(1),
            )
        )
    return windows


def _window_collection(
    collection: MetricCollection,
    window: MetricWindow,
    applicable_keys: list[str],
) -> MetricCollection:
    applicable = set(applicable_keys)
    results = [
        _window_metric(metric, window)
        for metric in collection.results
        if metric.metric_key in applicable
    ]
    return collection.model_copy(
        update={
            "results": results,
            "unavailable_count": sum(
                metric.status is MetricStatus.UNAVAILABLE for metric in results
            ),
            "partial_count": sum(metric.status is MetricStatus.PARTIAL for metric in results),
        }
    )


def _window_metric(metric: MetricValue, window: MetricWindow) -> MetricValue:
    return metric.model_copy(
        update={
            "scope": "time_window",
            "dimensions": {
                **metric.dimensions,
                "window_ordinal": window.ordinal,
                "window_start_s": window.start_s,
                "window_end_s": window.end_s,
                "window_effective_start_s": window.effective_start_s,
                "window_effective_end_s": window.effective_end_s,
            },
            "metadata": {
                **metric.metadata,
                "base_scope": metric.scope,
                "window_boundary": window.boundary,
                "window_requested_interval_coverage_fraction": (
                    window.requested_interval_coverage_fraction
                ),
                "window_is_partial": window.is_partial,
                "window_anchor_policy_version": WINDOW_ANCHOR_POLICY_VERSION,
            },
        }
    )


def _source_times(tables: CanonicalTables) -> list[float]:
    return [
        *(record.arrival_time_s for record in tables.tasks),
        *(record.timestamp_s for record in tables.infrastructure),
        *(record.timestamp_s for record in tables.vehicles),
        *(record.timestamp_s for record in tables.traffic),
        *(record.departure_time_s for record in tables.trips),
        *(record.timestamp_s for record in tables.incidents),
    ]


def _floor_index(timestamp: Decimal, origin: Decimal, width: Decimal) -> int:
    return int(((timestamp - origin) / width).to_integral_value(rounding=ROUND_FLOOR))


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))
