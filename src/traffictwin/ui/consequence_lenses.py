"""Curated Traffic and VEC consequence projection over existing comparison output.

This module is a typed presentation projection. It consumes existing
validated analyses and comparison results, selects and groups existing
metrics, retains exact values and reason codes, and avoids scientific
recomputation.

Report identity contract
------------------------
A ConsequenceLensReport fingerprint identifies the canonical logical
consequence projection. It binds:

* baseline_identity and variation_identity (logical run/seed/experiment/metric_version/synthetic)
* compatibility (tri-state same_* / synthetic_match, warnings)
* changed_seed_parameters
* traffic and VEC rows (status, direction, values, reason_codes, provenance, etc.)
* evidence_standing (logical synthetic/run/seed only, no absolute paths)
* warnings

It explicitly excludes:

* local absolute filesystem paths (/tmp, /Users, /private, etc.)
* optional local BundleAnalysis enrichment (bundle paths / bundle validation fingerprints)
* runtime wall-clock values (generated_at)

Two independent builds of the same logical comparison produce identical
fingerprint and identical canonical export bytes (deterministic).

The downloadable artifact is the canonical portable payload plus the
fingerprint, byte-identical for the same logical projection on any
machine.
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
    """Deterministic projection over an existing comparison report.

    The fingerprint identifies the canonical portable payload (logical
    comparison evidence). It does not depend on absolute local paths,
    optional local enrichment, or runtime wall-clock values.
    """

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

    def to_portable_dict(self) -> dict[str, Any]:
        """Return canonical portable payload excluding fingerprint self-reference.

        This is the exact payload that is hashed to produce ``fingerprint``
        and that is exported as the downloadable artifact (plus fingerprint).
        It contains no absolute paths and no runtime timestamps.
        The shape mirrors the report (traffic_summary/vec_summary) for
        backward compatibility with existing exports, but with deterministic
        ordering and without local paths.
        """

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
                "compatibility_findings": sorted(row.compatibility_findings),
                "provenance": dict(sorted(row.provenance.items())),
                "limitations": sorted(row.limitations),
                "denominator_description": row.denominator_description,
            }

        def _summary_payload(summary: ConsequenceDomainSummary) -> dict[str, Any]:
            return {
                "domain": summary.domain,
                "available_count": summary.available_count,
                "partial_count": summary.partial_count,
                "unavailable_count": summary.unavailable_count,
                "warnings": sorted(summary.warnings),
                "rows": [_row_payload(r) for r in summary.rows],
            }

        return {
            "projection_version": "1.0",
            "baseline_identity": dict(sorted(self.baseline_identity.items())),
            "variation_identity": dict(sorted(self.variation_identity.items())),
            "compatibility": dict(sorted(self.compatibility.items())),
            "changed_seed_parameters": sorted(
                self.changed_seed_parameters,
                key=lambda item: str(item.get("path")),
            ),
            "warnings": sorted(self.warnings),
            "evidence_standing": dict(sorted(self.evidence_standing.items())),
            "traffic_summary": _summary_payload(self.traffic_summary),
            "vec_summary": _summary_payload(self.vec_summary),
        }

    def to_canonical_bytes(self) -> bytes:
        """Return deterministic canonical JSON bytes for fingerprinting/export."""

        payload = self.to_portable_dict()
        # Use sorted keys, compact separators, no default=str leakage for unknown
        # types – we explicitly fail on non-serializable values.
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return encoded.encode("utf-8")

    def to_json(self) -> str:
        """Return deterministic portable JSON export (canonical payload + fingerprint)."""

        payload = self.to_portable_dict()
        # Export payload is canonical payload plus fingerprint, byte-deterministic.
        payload["fingerprint"] = self.fingerprint
        return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)


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


def _tri_state_equal(a: Any, b: Any) -> bool | None:  # noqa: ANN401
    """Return True if both known equal, False if both known different, None if unknown."""

    if a is None or b is None:
        return None
    # Treat empty string as unknown for identity fields where empty means missing
    if isinstance(a, str) and not a.strip():
        return None
    if isinstance(b, str) and not b.strip():
        return None
    return bool(a == b)


def _fingerprint_for_canonical(portable_dict: dict[str, Any]) -> str:
    """Compute SHA-256 over canonical portable payload (excluding fingerprint)."""

    encoded = json.dumps(portable_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
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

    # Ignore optional local BundleAnalysis enrichment for canonical identity
    return build_consequence_lens_report_from_comparison(comparison)


def build_consequence_lens_report_from_comparison(
    comparison: ComparisonReport,
    *,
    baseline: BundleAnalysis | None = None,  # noqa: ARG001 - kept for backward compat, intentionally ignored for identity
    variation: BundleAnalysis | None = None,  # noqa: ARG001
) -> ConsequenceLensReport:
    """Project an already computed comparison report into traffic and VEC lenses.

    Optional ``baseline``/``variation`` kwargs are accepted for backward
    compatibility but are intentionally **not** part of canonical report
    identity (no absolute paths, no local fingerprints). They remain local
    UI context only.
    """

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

    # Tri-state compatibility: None means unknown (one or both missing)
    same_experiment = _tri_state_equal(
        baseline_ctx.get("experiment_id"), variation_ctx.get("experiment_id")
    )
    same_seed = _tri_state_equal(baseline_ctx.get("random_seed"), variation_ctx.get("random_seed"))
    same_version = _tri_state_equal(
        baseline_ctx.get("metric_version"), variation_ctx.get("metric_version")
    )
    synthetic_match = _tri_state_equal(
        baseline_ctx.get("synthetic"), variation_ctx.get("synthetic")
    )

    warnings = list(comparison.warnings)
    if same_version is False and "metric collection versions differ" not in warnings:
        warnings.append("metric collection versions differ")
    # Unknown version does not promote
    has_authoritative_incompatibility = bool(warnings)
    # is_compatible requires all required dimensions explicitly True and no warnings
    is_compatible = bool(
        same_experiment is True
        and same_version is True
        and same_seed is True
        and synthetic_match is True
        and not has_authoritative_incompatibility
    )
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

    # Evidence standing: logical only, no absolute paths, no local fingerprints
    evidence_standing: dict[str, JsonScalar] = {
        "baseline_synthetic": baseline_ctx.get("synthetic"),
        "variation_synthetic": variation_ctx.get("synthetic"),
        "baseline_run_id": baseline_ctx.get("run_id"),
        "variation_run_id": variation_ctx.get("run_id"),
        "baseline_seed_id": baseline_ctx.get("seed_id"),
        "variation_seed_id": variation_ctx.get("seed_id"),
    }

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

    # Build provisional report without fingerprint to compute canonical fingerprint
    provisional = ConsequenceLensReport(
        baseline_identity=baseline_ctx,
        variation_identity=variation_ctx,
        compatibility=compatibility,
        changed_seed_parameters=list(comparison.changed_seed_parameters),
        traffic_summary=traffic_summary,
        vec_summary=vec_summary,
        evidence_standing=evidence_standing,
        warnings=list(warnings),
        fingerprint="",
    )
    fingerprint = _fingerprint_for_canonical(provisional.to_portable_dict())

    return ConsequenceLensReport(
        baseline_identity=baseline_ctx,
        variation_identity=variation_ctx,
        compatibility=compatibility,
        changed_seed_parameters=list(comparison.changed_seed_parameters),
        traffic_summary=traffic_summary,
        vec_summary=vec_summary,
        evidence_standing=evidence_standing,
        warnings=list(warnings),
        fingerprint=fingerprint,
    )
