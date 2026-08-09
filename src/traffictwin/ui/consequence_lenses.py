"""Curated Traffic and VEC consequence projection over existing comparison output.

This module is a typed presentation projection. It consumes existing
validated analyses and comparison results, selects and groups existing
metrics, retains exact values and reason codes, and avoids scientific
recomputation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.metrics.catalogue import METRIC_DEFINITIONS
from traffictwin.metrics.comparison import ComparisonReport, MetricComparison
from traffictwin.metrics.results import JsonScalar
from traffictwin.ui.services.models import BundleAnalysis, ServiceError
from traffictwin.ui.services.provenance import compare_runs_for_ui

TRAFFIC_LENS_KEYS: tuple[str, ...] = (
    "trip.records.count",
    "trip.completed.count",
    "trip.incomplete.count",
    "trip.completion.rate",
    "trip.duration.count",
    "trip.duration.mean_s",
    "trip.duration.p50_s",
    "trip.duration.p95_s",
    "trip.duration.min_s",
    "trip.duration.max_s",
    "traffic.observation.count",
    "traffic.count.total",
    "traffic.count.mean",
    "traffic.speed.mean_mps",
    "traffic.speed.p50_mps",
    "traffic.speed.p95_mps",
    "traffic.speed.min_mps",
    "traffic.sensor.count",
    "traffic.time_coverage",
)

VEC_LENS_KEYS: tuple[str, ...] = (
    "task.generated.count",
    "task.completed.count",
    "task.completion.rate",
    "task.incomplete.rate",
    "task.deadline_miss.completed_observed_rate",
    "task.completion.rate_by_class",
    "task.completion.rate_by_vehicle_tier",
    "task.drops.by_cause",
    "task.latency.count",
    "task.latency.mean_ms",
    "task.latency.p50_ms",
    "task.latency.p95_ms",
    "task.latency.p99_ms",
    "task.decision.counts",
    "task.decision_share.local",
    "task.decision_share.v2i",
    "task.decision_share.v2v",
    "task.decision_share.unknown",
    "task.offload.rate",
    "infra.observed_rsu.count",
    "infra.queue_length.mean",
    "infra.queue_length.max",
    "infra.utilisation.mean",
    "infra.utilisation.p95",
    "infra.saturation.episode_count",
    "infra.saturation.duration_s",
    "infra.rsu.summary",
    "infra.load_balance.jain_capacity_normalised",
    "fairness.rsu.capacity_normalised_load.by_group",
    "fairness.rsu.capacity_normalised_load.max_gap",
    "fairness.vehicle_tier.completion_rate.max_gap",
    "fairness.vehicle_tier.completion_rate.jain",
    "spatial.rsu.task.count_by_target",
    "spatial.rsu.task.completion_rate_by_target",
    "spatial.rsu.task.deadline_miss.completed_observed_rate_by_target",
    "spatial.vehicle.observation_count_by_grid_cell",
    "spatial.vehicle.distinct_count_by_grid_cell",
    "spatial.vehicle.speed.mean_mps_by_grid_cell",
    "task.energy.mean_per_observed_task_j",
    "task.energy.per_completed_j",
    "task.energy_delay_product.mean_j_ms",
)

ALL_LENS_KEYS: frozenset[str] = frozenset((*TRAFFIC_LENS_KEYS, *VEC_LENS_KEYS))

DENOMINATOR_BY_KEY: dict[str, str] = {
    "task.completion.rate": ("Completed valid tasks / generated valid tasks"),
    "task.incomplete.rate": ("Incomplete valid tasks / generated valid tasks"),
    "task.deadline_miss.completed_observed_rate": (
        "Deadline misses / completed tasks with observed latency and deadline"
    ),
    "trip.completion.rate": "Completed trips / total trip records",
    "task.offload.rate": "V2I plus V2V decisions / recognised decisions",
    "task.decision_share.local": "Local decisions / recognised decisions",
    "task.decision_share.v2i": "V2I decisions / recognised decisions",
    "task.decision_share.v2v": "V2V decisions / recognised decisions",
    "task.decision_share.unknown": "Unknown decisions / all decisions",
    "task.completion.rate_by_class": ("Completed tasks / generated tasks, grouped by task class"),
    "task.completion.rate_by_vehicle_tier": (
        "Completed tasks / generated tasks, grouped by operational vehicle tier"
    ),
    "spatial.rsu.task.completion_rate_by_target": (
        "Completed canonical V2I tasks / canonical V2I tasks, by exact target RSU"
    ),
    "spatial.rsu.task.deadline_miss.completed_observed_rate_by_target": (
        "Deadline misses / completed V2I tasks with observed latency, by exact target RSU"
    ),
}


class ConsequenceMetricRow(BaseModel):
    """One curated consequence row projecting an existing comparison."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    label: str
    domain: str
    baseline: JsonScalar
    variation: JsonScalar
    absolute_delta: float | None = None
    relative_delta: float | None = None
    unit: str | None = None
    status: str
    direction: str
    reason_codes: list[str] = Field(default_factory=list)
    compatibility_findings: list[str] = Field(default_factory=list)
    denominator_description: str | None = None
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)


class ConsequenceDomainSummary(BaseModel):
    """Summary for one consequence domain."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    rows: list[ConsequenceMetricRow] = Field(default_factory=list)
    available_count: int = 0
    partial_count: int = 0
    unavailable_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class ConsequenceLensReport(BaseModel):
    """Deterministic projection over an existing comparison report."""

    model_config = ConfigDict(extra="forbid")

    baseline_identity: dict[str, JsonScalar] = Field(default_factory=dict)
    variation_identity: dict[str, JsonScalar] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    changed_seed_parameters: list[dict[str, JsonScalar]] = Field(default_factory=list)
    traffic_summary: ConsequenceDomainSummary = Field(
        default_factory=lambda: ConsequenceDomainSummary(domain="traffic")
    )
    vec_summary: ConsequenceDomainSummary = Field(
        default_factory=lambda: ConsequenceDomainSummary(domain="vec")
    )
    evidence_standing: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str = ""
    generated_at: str = ""

    def to_json(self) -> str:
        """Return deterministic JSON export."""

        return self.model_dump_json(indent=2)


def _label_for_key(metric_key: str) -> str:
    definition = METRIC_DEFINITIONS.get(metric_key)
    if definition is not None:
        return definition.human_name
    return metric_key


def _domain_for_key(metric_key: str) -> str:
    if metric_key in TRAFFIC_LENS_KEYS:
        return "traffic"
    if metric_key in VEC_LENS_KEYS:
        return "vec"
    if metric_key.startswith(("traffic.", "trip.")):
        return "traffic"
    return "vec"


def _limitations_for_key(metric_key: str) -> list[str]:
    definition = METRIC_DEFINITIONS.get(metric_key)
    if definition is not None:
        return list(definition.limitations)
    return []


def _metric_row_from_comparison(comparison: MetricComparison) -> ConsequenceMetricRow:
    domain = _domain_for_key(comparison.metric_key)
    return ConsequenceMetricRow(
        metric_key=comparison.metric_key,
        label=_label_for_key(comparison.metric_key),
        domain=domain,
        baseline=comparison.baseline,
        variation=comparison.variation,
        absolute_delta=comparison.absolute_delta,
        relative_delta=comparison.relative_delta,
        unit=comparison.unit,
        status=comparison.status.value,
        direction=comparison.direction.value,
        reason_codes=[reason.value for reason in comparison.reason_codes],
        compatibility_findings=list(comparison.compatibility_findings),
        denominator_description=DENOMINATOR_BY_KEY.get(comparison.metric_key),
        limitations=_limitations_for_key(comparison.metric_key),
        provenance=dict(comparison.provenance),
    )


def _unavailable_row_for_missing_key(metric_key: str, findings: list[str]) -> ConsequenceMetricRow:
    domain = _domain_for_key(metric_key)
    definition = METRIC_DEFINITIONS.get(metric_key)
    unit = definition.unit if definition is not None else None
    return ConsequenceMetricRow(
        metric_key=metric_key,
        label=_label_for_key(metric_key),
        domain=domain,
        baseline=None,
        variation=None,
        absolute_delta=None,
        relative_delta=None,
        unit=unit,
        status="unavailable",
        direction="unavailable",
        reason_codes=["METRIC_NOT_APPLICABLE"],
        compatibility_findings=list(findings),
        denominator_description=DENOMINATOR_BY_KEY.get(metric_key),
        limitations=_limitations_for_key(metric_key),
        provenance={},
    )


def _fingerprint_for_report(
    report: ComparisonReport,
    traffic: ConsequenceDomainSummary,
    vec: ConsequenceDomainSummary,
) -> str:
    # Canonical stable binding of the complete projected payload.
    # Order is deterministic (allowlist order) and values are bound, not just keys.
    def _row_payload(row: ConsequenceMetricRow) -> dict[str, Any]:
        return {
            "metric_key": row.metric_key,
            "domain": row.domain,
            "status": row.status,
            "direction": row.direction,
            "baseline": row.baseline,
            "variation": row.variation,
            "absolute_delta": row.absolute_delta,
            "relative_delta": row.relative_delta,
            "unit": row.unit,
            "reason_codes": sorted(row.reason_codes),
        }

    payload: dict[str, Any] = {
        "projection_version": "1.0",
        "baseline_identity": report.baseline_context,
        "variation_identity": report.variation_context,
        "compatibility": {
            "same_experiment": report.baseline_context.get("experiment_id")
            == report.variation_context.get("experiment_id"),
            "same_random_seed": report.baseline_context.get("random_seed")
            == report.variation_context.get("random_seed"),
            "same_metric_version": report.baseline_context.get("metric_version")
            == report.variation_context.get("metric_version"),
        },
        "changed_seed_parameters": sorted(
            report.changed_seed_parameters,
            key=lambda item: str(item.get("path")),
        ),
        "warnings": sorted(report.warnings),
        "comparison_version": report.comparison_version,
        "traffic_rows": [_row_payload(row) for row in traffic.rows],
        "vec_rows": [_row_payload(row) for row in vec.rows],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_consequence_lens_report(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
) -> ConsequenceLensReport | ServiceError:
    """Build a deterministic curated projection over an existing comparison."""

    if baseline.metrics is None or variation.metrics is None:
        return ServiceError("Both baseline and variation must be accepted before comparison.")
    if not baseline.analysis_ready:
        return ServiceError(
            "Baseline bundle is rejected and cannot be used for consequence lenses."
        )
    if not variation.analysis_ready:
        return ServiceError(
            "Variation bundle is rejected and cannot be used for consequence lenses."
        )

    comparison = compare_runs_for_ui(baseline, variation)
    if isinstance(comparison, ServiceError):
        return comparison

    return build_consequence_lens_report_from_comparison(
        comparison,
        baseline=baseline,
        variation=variation,
    )


def build_consequence_lens_report_from_comparison(
    comparison: ComparisonReport,
    *,
    baseline: BundleAnalysis | None = None,
    variation: BundleAnalysis | None = None,
) -> ConsequenceLensReport:
    """Project an already computed comparison report into traffic and VEC lenses."""

    by_key: dict[str, MetricComparison] = {
        item.metric_key: item
        for item in [*comparison.comparable_metrics, *comparison.unavailable_comparisons]
    }

    traffic_rows: list[ConsequenceMetricRow] = []
    vec_rows: list[ConsequenceMetricRow] = []

    for key in TRAFFIC_LENS_KEYS:
        comp = by_key.get(key)
        if comp is not None:
            row = _metric_row_from_comparison(comp)
        else:
            row = _unavailable_row_for_missing_key(key, ["metric is missing from one collection"])
        traffic_rows.append(row)

    for key in VEC_LENS_KEYS:
        comp = by_key.get(key)
        if comp is not None:
            row = _metric_row_from_comparison(comp)
        else:
            row = _unavailable_row_for_missing_key(key, ["metric is missing from one collection"])
        vec_rows.append(row)

    traffic_available = sum(1 for row in traffic_rows if row.status == "available")
    traffic_partial = sum(1 for row in traffic_rows if row.status == "partial")
    traffic_unavailable = sum(1 for row in traffic_rows if row.status == "unavailable")
    vec_available = sum(1 for row in vec_rows if row.status == "available")
    vec_partial = sum(1 for row in vec_rows if row.status == "partial")
    vec_unavailable = sum(1 for row in vec_rows if row.status == "unavailable")

    baseline_ctx = dict(comparison.baseline_context)
    variation_ctx = dict(comparison.variation_context)

    # Compatibility preserves the authoritative comparison contract.
    same_experiment = baseline_ctx.get("experiment_id") == variation_ctx.get("experiment_id")
    same_seed = baseline_ctx.get("random_seed") == variation_ctx.get("random_seed")
    same_version = baseline_ctx.get("metric_version") == variation_ctx.get("metric_version")
    synthetic_match = baseline_ctx.get("synthetic") == variation_ctx.get("synthetic")
    is_compatible = bool(same_experiment and same_version and same_seed)
    # Warnings are the authoritative compatibility findings.
    warnings = list(comparison.warnings)
    if not same_version and "metric collection versions differ" not in warnings:
        warnings.append("metric collection versions differ")
    compatibility: dict[str, Any] = {
        "same_experiment": same_experiment,
        "same_random_seed": same_seed,
        "same_metric_version": same_version,
        "synthetic_match": synthetic_match,
        "is_compatible": is_compatible,
        "warnings": warnings,
        "baseline_metric_version": baseline_ctx.get("metric_version"),
        "variation_metric_version": variation_ctx.get("metric_version"),
    }

    evidence_standing: dict[str, JsonScalar] = {
        "baseline_synthetic": baseline_ctx.get("synthetic"),
        "variation_synthetic": variation_ctx.get("synthetic"),
        "baseline_run_id": baseline_ctx.get("run_id"),
        "variation_run_id": variation_ctx.get("run_id"),
        "baseline_seed_id": baseline_ctx.get("seed_id"),
        "variation_seed_id": variation_ctx.get("seed_id"),
    }
    if baseline is not None:
        evidence_standing["baseline_bundle_path"] = str(baseline.source_path)
        evidence_standing["baseline_fingerprint"] = baseline.validation.fingerprint
    if variation is not None:
        evidence_standing["variation_bundle_path"] = str(variation.source_path)
        evidence_standing["variation_fingerprint"] = variation.validation.fingerprint

    traffic_summary = ConsequenceDomainSummary(
        domain="traffic",
        rows=traffic_rows,
        available_count=traffic_available,
        partial_count=traffic_partial,
        unavailable_count=traffic_unavailable,
        warnings=list(warnings),
    )
    vec_summary = ConsequenceDomainSummary(
        domain="vec",
        rows=vec_rows,
        available_count=vec_available,
        partial_count=vec_partial,
        unavailable_count=vec_unavailable,
        warnings=list(warnings),
    )

    fingerprint = _fingerprint_for_report(comparison, traffic_summary, vec_summary)

    return ConsequenceLensReport(
        baseline_identity=baseline_ctx,
        variation_identity=variation_ctx,
        compatibility=compatibility,
        changed_seed_parameters=list(comparison.changed_seed_parameters),
        traffic_summary=traffic_summary,
        vec_summary=vec_summary,
        evidence_standing=evidence_standing,
        warnings=list(comparison.warnings),
        fingerprint=fingerprint,
        generated_at=comparison.generated_at.isoformat(),
    )
