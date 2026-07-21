"""Typed temporal evidence extracted from deterministic fixed-window metrics."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.metrics.catalogue import metric_definition_for_result
from traffictwin.metrics.results import MetricStatus, MetricValue
from traffictwin.metrics.windowed import (
    MetricWindow,
    WindowDisposition,
    WindowedMetricConfig,
    WindowedMetricSeries,
    WindowSeriesStatus,
)

TEMPORAL_EVIDENCE_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class TemporalEvidenceModel(BaseModel):
    """Strict immutable base for temporal diagnostic evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TemporalEvidenceStatus(StrEnum):
    """Readiness of one selected windowed metric for temporal diagnosis."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class TemporalEvidenceReason(StrEnum):
    """Stable reasons why temporal evidence cannot be evaluated."""

    SERIES_UNAVAILABLE = "TEMPORAL_SERIES_UNAVAILABLE"
    SERIES_INVALID = "TEMPORAL_SERIES_INVALID"
    METRIC_NOT_WINDOW_APPLICABLE = "TEMPORAL_METRIC_NOT_WINDOW_APPLICABLE"
    METRIC_ABSENT = "TEMPORAL_METRIC_ABSENT"
    METRIC_DIRECTION_UNDECLARED = "TEMPORAL_METRIC_DIRECTION_UNDECLARED"
    METRIC_CONTRACT_INCOMPATIBLE = "TEMPORAL_METRIC_CONTRACT_INCOMPATIBLE"
    NO_ELIGIBLE_WINDOWS = "TEMPORAL_NO_ELIGIBLE_WINDOWS"
    EVENT_OUTSIDE_ANALYSIS_RANGE = "TEMPORAL_EVENT_OUTSIDE_ANALYSIS_RANGE"
    RUN_MISMATCH = "TEMPORAL_RUN_MISMATCH"
    SOURCE_FINGERPRINT_MISMATCH = "TEMPORAL_SOURCE_FINGERPRINT_MISMATCH"


class TemporalPointEligibility(StrEnum):
    """Why one fixed-window observation is or is not admitted to R6."""

    ELIGIBLE = "eligible"
    EXCLUDED_PARTIAL = "excluded_partial"
    LOW_COVERAGE = "low_coverage"
    METRIC_ABSENT = "metric_absent"
    METRIC_UNAVAILABLE = "metric_unavailable"
    METRIC_PARTIAL = "metric_partial"
    METRIC_INVALID = "metric_invalid"
    NON_NUMERIC = "non_numeric"
    INCOMPATIBLE = "incompatible"


class TemporalEvidenceConfig(TemporalEvidenceModel):
    """Declared selection and admission policy for one temporal metric series."""

    schema_version: Literal["1.0"] = TEMPORAL_EVIDENCE_SCHEMA_VERSION
    metric_key: str = Field(default="task.deadline_miss.completed_observed_rate", min_length=1)
    minimum_window_coverage: float = Field(default=1.0, ge=0.0, le=1.0, allow_inf_nan=False)
    event_time_s: float | None = Field(default=None, allow_inf_nan=False)
    event_label: str | None = Field(default=None, min_length=1, max_length=160)
    event_source: Literal["researcher_declared"] = "researcher_declared"
    event_alignment_policy: Literal["containing_half_open_effective_window_v1"] = (
        "containing_half_open_effective_window_v1"
    )

    @model_validator(mode="after")
    def validate_event_label(self) -> TemporalEvidenceConfig:
        if self.event_label is not None and self.event_time_s is None:
            raise ValueError("event_label requires event_time_s")
        return self


class TemporalMetricPoint(TemporalEvidenceModel):
    """One visible fixed-window observation and its R6 admission state."""

    ordinal: int = Field(ge=0)
    grid_index: int
    start_s: float
    end_s: float
    effective_start_s: float
    effective_end_s: float
    requested_interval_coverage_fraction: float = Field(ge=0.0, le=1.0)
    disposition: WindowDisposition
    metric_status: MetricStatus | None = None
    value: float | None = Field(default=None, allow_inf_nan=False)
    unit: str | None = None
    implementation_version: str | None = None
    eligibility: TemporalPointEligibility
    reason_codes: list[str] = Field(default_factory=list)


class TemporalEventContext(TemporalEvidenceModel):
    """Researcher-declared event mapped to the existing fixed grid."""

    event_time_s: float = Field(allow_inf_nan=False)
    event_label: str
    source: Literal["researcher_declared"] = "researcher_declared"
    alignment_policy: Literal["containing_half_open_effective_window_v1"] = (
        "containing_half_open_effective_window_v1"
    )
    event_window_ordinal: int = Field(ge=0)


class TemporalEvidence(TemporalEvidenceModel):
    """Complete versioned window evidence consumed by R6 through EvidencePack."""

    schema_version: Literal["1.0"] = TEMPORAL_EVIDENCE_SCHEMA_VERSION
    status: TemporalEvidenceStatus
    reason_codes: list[TemporalEvidenceReason] = Field(default_factory=list)
    config: TemporalEvidenceConfig
    run_id: str
    metric_version: str
    metric_key: str
    unit: str | None = None
    implementation_version: str | None = None
    higher_is_better: bool | None = None
    boundary: Literal["[start,end)"] = "[start,end)"
    anchor_policy_version: str
    window_config: WindowedMetricConfig
    series_fingerprint: str
    input_fingerprint: str | None = None
    points: list[TemporalMetricPoint]
    total_window_count: int = Field(ge=0)
    eligible_window_count: int = Field(ge=0)
    ineligible_window_count: int = Field(ge=0)
    event: TemporalEventContext | None = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts_and_grid(self) -> TemporalEvidence:
        if self.total_window_count != len(self.points):
            raise ValueError("temporal total_window_count must match points")
        eligible = sum(
            point.eligibility is TemporalPointEligibility.ELIGIBLE for point in self.points
        )
        if self.eligible_window_count != eligible:
            raise ValueError("temporal eligible_window_count must match points")
        if self.ineligible_window_count != len(self.points) - eligible:
            raise ValueError("temporal ineligible_window_count must match points")
        ordinals = [point.ordinal for point in self.points]
        if ordinals != list(range(len(self.points))):
            raise ValueError("temporal point ordinals must be contiguous and ordered from zero")
        if self.event is not None and self.event.event_window_ordinal not in ordinals:
            raise ValueError("temporal event window must exist in points")
        return self

    def canonical_json(self) -> str:
        """Return stable canonical JSON."""

        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        """Return a deterministic identity for the complete temporal evidence."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def build_temporal_evidence(
    series: WindowedMetricSeries,
    config: TemporalEvidenceConfig,
) -> TemporalEvidence:
    """Extract one complete scalar metric timeline without hiding unusable windows."""

    series_fingerprint = windowed_metric_series_fingerprint(series)
    points, representative, contract_incompatible = _metric_points(series, config)
    reasons: list[TemporalEvidenceReason] = []
    status = TemporalEvidenceStatus.AVAILABLE
    if series.status is WindowSeriesStatus.INVALID:
        reasons.append(TemporalEvidenceReason.SERIES_INVALID)
        status = TemporalEvidenceStatus.INVALID
    elif series.status is not WindowSeriesStatus.AVAILABLE:
        reasons.append(TemporalEvidenceReason.SERIES_UNAVAILABLE)
        status = TemporalEvidenceStatus.UNAVAILABLE
    if config.metric_key not in series.applicable_metric_keys:
        reasons.append(TemporalEvidenceReason.METRIC_NOT_WINDOW_APPLICABLE)
        status = TemporalEvidenceStatus.UNAVAILABLE
    if representative is None:
        reasons.append(TemporalEvidenceReason.METRIC_ABSENT)
        status = TemporalEvidenceStatus.UNAVAILABLE

    definition = (
        metric_definition_for_result(representative) if representative is not None else None
    )
    higher_is_better = definition.higher_is_better if definition is not None else None
    if representative is not None and (definition is None or not definition.time_window_applicable):
        reasons.append(TemporalEvidenceReason.METRIC_NOT_WINDOW_APPLICABLE)
        status = TemporalEvidenceStatus.UNAVAILABLE
    if representative is not None and higher_is_better is None:
        reasons.append(TemporalEvidenceReason.METRIC_DIRECTION_UNDECLARED)
        status = TemporalEvidenceStatus.UNAVAILABLE
    if contract_incompatible:
        reasons.append(TemporalEvidenceReason.METRIC_CONTRACT_INCOMPATIBLE)
        status = TemporalEvidenceStatus.INVALID

    eligible_count = sum(point.eligibility is TemporalPointEligibility.ELIGIBLE for point in points)
    if not eligible_count:
        reasons.append(TemporalEvidenceReason.NO_ELIGIBLE_WINDOWS)
        if status is TemporalEvidenceStatus.AVAILABLE:
            status = TemporalEvidenceStatus.UNAVAILABLE

    event = _event_context(series, config)
    if config.event_time_s is not None and event is None:
        reasons.append(TemporalEvidenceReason.EVENT_OUTSIDE_ANALYSIS_RANGE)
        if status is TemporalEvidenceStatus.AVAILABLE:
            status = TemporalEvidenceStatus.UNAVAILABLE

    return TemporalEvidence(
        status=status,
        reason_codes=sorted(set(reasons), key=str),
        config=config,
        run_id=series.run_id,
        metric_version=series.metric_version,
        metric_key=config.metric_key,
        unit=representative.unit if representative is not None else None,
        implementation_version=(
            representative.implementation_version if representative is not None else None
        ),
        higher_is_better=higher_is_better,
        anchor_policy_version=series.anchor_policy_version,
        window_config=series.config,
        series_fingerprint=series_fingerprint,
        input_fingerprint=series.input_fingerprint,
        points=points,
        total_window_count=len(points),
        eligible_window_count=eligible_count,
        ineligible_window_count=len(points) - eligible_count,
        event=event,
        warnings=[
            "Ineligible windows remain visible and are never converted to zero or skipped when "
            "testing consecutive deterioration.",
            *series.warnings,
        ],
        limitations=[
            "Temporal evidence is descriptive fixed-window lineage, not causal attribution.",
            "Requested-range coverage is not proof of sensor completeness.",
            "Event context is researcher-declared and is not inferred from the metric series.",
        ],
    )


def invalidate_temporal_evidence(
    evidence: TemporalEvidence,
    reason: TemporalEvidenceReason,
) -> TemporalEvidence:
    """Return an invalid copy carrying an additional compatibility reason."""

    reasons = sorted({*evidence.reason_codes, reason}, key=str)
    return evidence.model_copy(
        update={"status": TemporalEvidenceStatus.INVALID, "reason_codes": reasons},
        deep=True,
    )


def windowed_metric_series_fingerprint(series: WindowedMetricSeries) -> str:
    """Fingerprint a window series while normalising computation timestamps."""

    payload = series.model_dump(mode="json")
    for item in payload["slices"]:
        collection = item.get("metrics")
        if collection is None:
            continue
        collection["generated_at"] = "<normalised>"
        for metric in collection["results"]:
            metric["computed_at"] = "<normalised>"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _metric_points(
    series: WindowedMetricSeries,
    config: TemporalEvidenceConfig,
) -> tuple[list[TemporalMetricPoint], MetricValue | None, bool]:
    points: list[TemporalMetricPoint] = []
    representative: MetricValue | None = None
    contract_incompatible = False
    expected_contract: tuple[str, str] | None = None
    for item in series.slices:
        metric = item.metrics.by_key().get(config.metric_key) if item.metrics is not None else None
        if metric is not None and representative is None:
            representative = metric
            expected_contract = (metric.unit, metric.implementation_version)
        eligibility = _point_eligibility(item.disposition, item.window, metric, config)
        if metric is not None and expected_contract is not None:
            current_contract = (metric.unit, metric.implementation_version)
            if metric.run_id != series.run_id or current_contract != expected_contract:
                eligibility = TemporalPointEligibility.INCOMPATIBLE
                contract_incompatible = True
        numeric = _finite_number(metric.value) if metric is not None else None
        points.append(
            TemporalMetricPoint(
                ordinal=item.window.ordinal,
                grid_index=item.window.grid_index,
                start_s=item.window.start_s,
                end_s=item.window.end_s,
                effective_start_s=item.window.effective_start_s,
                effective_end_s=item.window.effective_end_s,
                requested_interval_coverage_fraction=(
                    item.window.requested_interval_coverage_fraction
                ),
                disposition=item.disposition,
                metric_status=metric.status if metric is not None else None,
                value=(numeric if eligibility is TemporalPointEligibility.ELIGIBLE else None),
                unit=metric.unit if metric is not None else None,
                implementation_version=(
                    metric.implementation_version if metric is not None else None
                ),
                eligibility=eligibility,
                reason_codes=(
                    [reason.value for reason in metric.reason_codes] if metric is not None else []
                ),
            )
        )
    return points, representative, contract_incompatible


def _point_eligibility(
    disposition: WindowDisposition,
    window: MetricWindow,
    metric: MetricValue | None,
    config: TemporalEvidenceConfig,
) -> TemporalPointEligibility:
    if disposition is WindowDisposition.EXCLUDED_PARTIAL:
        return TemporalPointEligibility.EXCLUDED_PARTIAL
    if window.requested_interval_coverage_fraction < config.minimum_window_coverage:
        return TemporalPointEligibility.LOW_COVERAGE
    if metric is None:
        return TemporalPointEligibility.METRIC_ABSENT
    if metric.status is MetricStatus.UNAVAILABLE:
        return TemporalPointEligibility.METRIC_UNAVAILABLE
    if metric.status is MetricStatus.PARTIAL:
        return TemporalPointEligibility.METRIC_PARTIAL
    if metric.status is MetricStatus.INVALID:
        return TemporalPointEligibility.METRIC_INVALID
    if _finite_number(metric.value) is None:
        return TemporalPointEligibility.NON_NUMERIC
    return TemporalPointEligibility.ELIGIBLE


def _event_context(
    series: WindowedMetricSeries,
    config: TemporalEvidenceConfig,
) -> TemporalEventContext | None:
    if config.event_time_s is None:
        return None
    event_time = config.event_time_s
    for item in series.slices:
        if item.window.effective_start_s <= event_time < item.window.effective_end_s:
            return TemporalEventContext(
                event_time_s=event_time,
                event_label=config.event_label or "declared event",
                event_window_ordinal=item.window.ordinal,
            )
    return None


def _finite_number(value: object) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None
