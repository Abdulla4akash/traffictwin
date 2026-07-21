"""Typed claim inventories shared by report rendering and provenance scoring."""

from __future__ import annotations

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.metrics.comparison import ComparisonReport, ComparisonStatus
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.reporting.models import (
    ReportClaimAvailability,
    ReportClaimExclusion,
    ReportClaimKind,
    ReportClaimReference,
    ReportClaimSnapshot,
    ResearchReportType,
)
from traffictwin.rules.models import RuleStatus

REPORT_CLAIM_DENOMINATOR = (
    "Every typed metric result, diagnostic rule result, or metric comparison explicitly included "
    "by the selected report template. Unavailable typed results remain in the denominator."
)

RUN_REPORT_METRIC_KEYS = (
    "task.generated.count",
    "task.completed.count",
    "task.completion.rate",
    "task.incomplete.rate",
    "task.latency.p95_ms",
    "task.latency.p99_ms",
    "task.energy.mean_per_observed_task_j",
    "task.energy.per_completed_j",
    "task.energy_delay_product.mean_j_ms",
    "fairness.vehicle_tier.completion_rate.max_gap",
    "fairness.vehicle_tier.completion_rate.jain",
    "fairness.rsu.capacity_normalised_load.max_gap",
    "infra.load_balance.jain_capacity_normalised",
    "spatial.rsu.task.count_by_target",
    "spatial.rsu.task.completion_rate_by_target",
    "spatial.rsu.task.deadline_miss.completed_observed_rate_by_target",
    "spatial.vehicle.observation_count_by_grid_cell",
    "spatial.vehicle.distinct_count_by_grid_cell",
    "spatial.vehicle.speed.mean_mps_by_grid_cell",
    "task.offload.rate",
    "infra.utilisation.p95",
    "infra.queue_length.max",
    "trip.duration.p95_s",
    "traffic.speed.mean_mps",
)

COMPARISON_REPORT_METRIC_KEYS = frozenset(
    {
        "task.completion.rate",
        "task.incomplete.rate",
        "task.latency.p99_ms",
        "task.energy.mean_per_observed_task_j",
        "task.energy.per_completed_j",
        "task.energy_delay_product.mean_j_ms",
        "fairness.vehicle_tier.completion_rate.max_gap",
        "fairness.vehicle_tier.completion_rate.jain",
        "fairness.rsu.capacity_normalised_load.max_gap",
        "infra.load_balance.jain_capacity_normalised",
        "infra.queue_length.max",
        "infra.utilisation.p95",
        "trip.duration.p95_s",
        "traffic.speed.mean_mps",
    }
)


def analysis_claim_references(
    report_id: str,
    metrics: MetricCollection,
    diagnostics: DiagnosticReport,
    *,
    metric_section: str,
) -> list[ReportClaimReference]:
    """Return the exact metric/rule claims included by run-like report templates."""

    metric_keys = metrics.by_key()
    claims = [
        ReportClaimReference(
            claim_id=f"{report_id}:metric:{metric_key}",
            claim_kind=ReportClaimKind.METRIC_RESULT,
            artifact_key=metric_key,
            section=metric_section,
            label=metric_key,
        )
        for metric_key in RUN_REPORT_METRIC_KEYS
        if metric_key in metric_keys
    ]
    claims.extend(
        ReportClaimReference(
            claim_id=f"{report_id}:rule:{result.rule_id}",
            claim_kind=ReportClaimKind.RULE_RESULT,
            artifact_key=result.rule_id,
            section="Diagnostic Hypotheses",
            label=f"{result.rule_id} — {result.title}",
        )
        for result in diagnostics.results
    )
    return claims


def analysis_claim_snapshots(
    report_id: str,
    metrics: MetricCollection,
    diagnostics: DiagnosticReport,
    *,
    metric_section: str,
) -> list[ReportClaimSnapshot]:
    """Project run metrics and rules into prose-free REP-03 claim snapshots."""

    metric_keys = metrics.by_key()
    snapshots = [
        ReportClaimSnapshot(
            claim_id=f"{report_id}:metric:{metric_key}",
            claim_kind=ReportClaimKind.METRIC_RESULT,
            artifact_key=metric_key,
            section=metric_section,
            availability=(
                ReportClaimAvailability.AVAILABLE
                if metric_keys[metric_key].status is MetricStatus.AVAILABLE
                else ReportClaimAvailability.UNAVAILABLE
            ),
            status=metric_keys[metric_key].status.value,
            value=metric_keys[metric_key].value,
            unit=metric_keys[metric_key].unit,
            reason_codes=[item.value for item in metric_keys[metric_key].reason_codes],
            details={
                "implementation_version": metric_keys[metric_key].implementation_version,
                "scope": metric_keys[metric_key].scope,
                "dimensions": metric_keys[metric_key].dimensions,
            },
        )
        for metric_key in RUN_REPORT_METRIC_KEYS
        if metric_key in metric_keys
    ]
    snapshots.extend(
        ReportClaimSnapshot(
            claim_id=f"{report_id}:rule:{result.rule_id}",
            claim_kind=ReportClaimKind.RULE_RESULT,
            artifact_key=result.rule_id,
            section="Diagnostic Hypotheses",
            availability=(
                ReportClaimAvailability.AVAILABLE
                if result.status in {RuleStatus.TRIGGERED, RuleStatus.NOT_TRIGGERED}
                else ReportClaimAvailability.UNAVAILABLE
            ),
            status=result.status.value,
            value={
                "confidence": result.confidence.value,
                "evidence_keys": sorted(result.evidence_keys),
                "findings": [
                    {
                        "finding_id": finding.finding_id,
                        "support": finding.support.value,
                        "evidence_keys": sorted(finding.evidence_keys),
                        "observed_values": finding.observed_values,
                    }
                    for finding in sorted(result.findings, key=lambda item: item.finding_id)
                ],
                "missing_evidence": sorted(result.missing_evidence),
                "metadata": result.metadata,
            },
            reason_codes=sorted(result.missing_evidence),
            details={"rule_version": result.rule_version},
        )
        for result in diagnostics.results
    )
    return snapshots


def comparison_claim_references(
    report_id: str,
    comparison: ComparisonReport,
) -> list[ReportClaimReference]:
    """Return every typed metric comparison represented by the comparison template."""

    comparisons = sorted(
        [*comparison.comparable_metrics, *comparison.unavailable_comparisons],
        key=lambda item: item.metric_key,
    )
    return [
        ReportClaimReference(
            claim_id=f"{report_id}:comparison:{item.metric_key}",
            claim_kind=ReportClaimKind.METRIC_COMPARISON,
            artifact_key=item.metric_key,
            section="Metric Deltas",
            label=f"{item.metric_key} variation-minus-baseline comparison",
        )
        for item in comparisons
        if item.metric_key in COMPARISON_REPORT_METRIC_KEYS
    ]


def comparison_claim_snapshots(
    report_id: str,
    comparison: ComparisonReport,
) -> list[ReportClaimSnapshot]:
    """Project typed metric comparisons without using formatted report prose."""

    comparisons = sorted(
        [*comparison.comparable_metrics, *comparison.unavailable_comparisons],
        key=lambda item: item.metric_key,
    )
    return [
        ReportClaimSnapshot(
            claim_id=f"{report_id}:comparison:{item.metric_key}",
            claim_kind=ReportClaimKind.METRIC_COMPARISON,
            artifact_key=item.metric_key,
            section="Metric Deltas",
            availability=(
                ReportClaimAvailability.AVAILABLE
                if item.status is ComparisonStatus.AVAILABLE
                else ReportClaimAvailability.UNAVAILABLE
            ),
            status=item.status.value,
            value={
                "baseline": item.baseline,
                "variation": item.variation,
                "absolute_delta": item.absolute_delta,
                "relative_delta": item.relative_delta,
                "direction": item.direction.value,
            },
            unit=item.unit,
            reason_codes=[reason.value for reason in item.reason_codes],
            details={"comparison_version": comparison.comparison_version},
        )
        for item in comparisons
        if item.metric_key in COMPARISON_REPORT_METRIC_KEYS
    ]


def full_report_claim_references(
    full_report_id: str,
    claims: list[ReportClaimReference],
) -> list[ReportClaimReference]:
    """Rebase embedded run/comparison claims onto one stable full-report denominator."""

    return [
        claim.model_copy(update={"claim_id": f"{full_report_id}:{index:04d}:{claim.artifact_key}"})
        for index, claim in enumerate(claims, start=1)
    ]


def full_report_claim_snapshots(
    full_report_id: str,
    snapshots: list[ReportClaimSnapshot],
) -> list[ReportClaimSnapshot]:
    """Rebase embedded typed snapshots with the same order as full-report references."""

    return [
        snapshot.model_copy(
            update={
                "claim_id": f"{full_report_id}:{index:04d}:{snapshot.artifact_key}",
            }
        )
        for index, snapshot in enumerate(snapshots, start=1)
    ]


def standard_claim_exclusions(report_type: ResearchReportType) -> list[ReportClaimExclusion]:
    """Publish non-denominator categories instead of silently ignoring rendered material."""

    exclusions = [
        ReportClaimExclusion(
            category="presentation_and_narrative",
            reason=(
                "Headings, formatting, explanatory prose, warnings, and limitations are not "
                "computed scientific result claims."
            ),
            examples=["report title", "disclaimer", "limitations"],
        ),
        ReportClaimExclusion(
            category="identity_and_reproduction_metadata",
            reason=(
                "Identifiers, timestamps, source labels, fingerprints, and reproduction commands "
                "are audited separately and do not enter the result-claim score."
            ),
            examples=["run ID", "bundle fingerprint", "CLI command"],
        ),
        ReportClaimExclusion(
            category="validation_and_evidence_inventory",
            reason=(
                "Validation status, finding-code lists, and evidence-category counts are pipeline "
                "metadata, not metric, diagnostic, or comparison result claims in PRO-03 v1.0."
            ),
            examples=["may import", "finding count", "available evidence categories"],
        ),
    ]
    if report_type in {ResearchReportType.COMPARISON, ResearchReportType.FULL}:
        exclusions.append(
            ReportClaimExclusion(
                category="comparison_context",
                reason=(
                    "Compatibility messages and changed seed parameters describe comparison "
                    "context; only typed metric comparisons enter this score."
                ),
                examples=["compatibility warning", "changed seed parameter"],
            )
        )
    return exclusions
