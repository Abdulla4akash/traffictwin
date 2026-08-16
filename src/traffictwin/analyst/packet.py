"""Build the Analyst Evidence Packet from existing deterministic services.

Everything in the packet is restated from services that already exist:
bundle validation, the metric collection, the consequence-lens projection,
and the deterministic diagnostic report. Nothing is recomputed, estimated,
or zero-filled; unavailable values stay unavailable with their reason codes.
"""

from __future__ import annotations

from typing import Literal

from traffictwin.analyst.models import (
    AnalystCrossRuleFact,
    AnalystDiagnostics,
    AnalystEvidencePacket,
    AnalystFindingFact,
    AnalystIdentity,
    AnalystMetricFact,
    AnalystProvenance,
    AnalystRecommendationFact,
    AnalystRefusalCode,
    AnalystRefusalError,
    AnalystRuleFact,
    JsonScalar,
)
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.metrics.results import MetricStatus
from traffictwin.ui.consequence_lenses import (
    DENOMINATOR_BY_KEY,
    ConsequenceLensReport,
    build_consequence_lens_report,
)
from traffictwin.ui.services import ServiceError
from traffictwin.ui.services.models import BundleAnalysis

ANALYST_TRAFFIC_KEYS: tuple[str, ...] = (
    "trip.duration.mean_s",
    "trip.duration.p95_s",
    "trip.completion.rate",
)
ANALYST_VEC_KEYS: tuple[str, ...] = (
    "task.completion.rate",
    "task.latency.mean_ms",
    "task.incomplete.rate",
    "task.offload.rate",
)
ANALYST_INFRASTRUCTURE_KEYS: tuple[str, ...] = (
    "infra.utilisation.mean",
    "infra.utilisation.p95",
    "infra.queue_length.max",
    "infra.saturation.duration_s",
    "infra.saturation.episode_count",
    "infra.load_balance.jain_capacity_normalised",
)

_FIXED_LIMITATIONS: tuple[str, ...] = (
    "Diagnostic hypotheses are deterministic, evidence-based candidates, not proven root causes.",
    "A comparison describes differences between the selected runs; it does "
    "not establish causality.",
    "Unavailable evidence stays unavailable; nothing is estimated, defaulted, or filled with zero.",
)


def _standing(analysis: BundleAnalysis) -> Literal["SYNTHETIC", "IMPORTED", "UNKNOWN"]:
    """The existing display rule: manifest environment name decides."""
    manifest = analysis.validation.manifest
    if manifest is None:
        return "UNKNOWN"
    return "SYNTHETIC" if manifest.environment.name == "synthetic" else "IMPORTED"


def _scalar(value: object) -> JsonScalar:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _lens_fact(report: ConsequenceLensReport, metric_key: str) -> AnalystMetricFact | None:
    for row in (*report.traffic_summary.rows, *report.vec_summary.rows):
        if row.metric_key == metric_key:
            return AnalystMetricFact(
                metric_key=row.metric_key,
                label=row.label,
                unit=row.unit,
                baseline=_scalar(row.baseline),
                variation=_scalar(row.variation),
                absolute_delta=row.absolute_delta,
                relative_delta=row.relative_delta,
                status=row.status,
                reason_codes=tuple(row.reason_codes),
                denominator=DENOMINATOR_BY_KEY.get(metric_key),
                source_service="consequence_lens",
            )
    return None


def _collection_fact(analysis: BundleAnalysis, metric_key: str) -> AnalystMetricFact | None:
    if analysis.metrics is None:
        return None
    metric = analysis.metrics.by_key().get(metric_key)
    if metric is None:
        return None
    return AnalystMetricFact(
        metric_key=metric_key,
        label=metric_key,
        unit=metric.unit,
        baseline=_scalar(metric.value),
        status=metric.status.value,
        reason_codes=tuple(code.value for code in metric.reason_codes),
        denominator=DENOMINATOR_BY_KEY.get(metric_key),
        source_service="metric_collection",
    )


def _facts(
    keys: tuple[str, ...],
    *,
    lens: ConsequenceLensReport | None,
    subject: BundleAnalysis,
) -> tuple[AnalystMetricFact, ...]:
    facts: list[AnalystMetricFact] = []
    for key in keys:
        fact = _lens_fact(lens, key) if lens is not None else _collection_fact(subject, key)
        if fact is not None:
            facts.append(fact)
    return tuple(facts)


def _rule_facts(report: DiagnosticReport) -> tuple[AnalystRuleFact, ...]:
    facts: list[AnalystRuleFact] = []
    for result in report.results:
        facts.append(
            AnalystRuleFact(
                rule_id=result.rule_id,
                title=result.title,
                status=result.status.value,
                confidence=result.confidence.value,
                hypothesis=result.hypothesis,
                evidence_keys=tuple(result.evidence_keys),
                findings=tuple(
                    AnalystFindingFact(
                        finding_id=finding.finding_id,
                        statement=finding.statement,
                        evidence_keys=tuple(finding.evidence_keys),
                        observed_values={
                            key: _scalar(value) for key, value in finding.observed_values.items()
                        },
                        expected_condition=finding.expected_condition,
                        support=finding.support.value,
                    )
                    for finding in result.findings
                ),
                missing_evidence=tuple(result.missing_evidence),
                recommendations=tuple(
                    AnalystRecommendationFact(
                        action=item.action,
                        rationale=item.rationale,
                        expected_direction=item.expected_direction,
                        prerequisite=item.prerequisite,
                        verification_step=item.verification_step,
                    )
                    for item in result.recommendations
                ),
                limitations=tuple(result.limitations),
            )
        )
    return tuple(facts)


def _cross_rule_facts(report: DiagnosticReport) -> tuple[AnalystCrossRuleFact, ...]:
    analysis = report.cross_rule_analysis
    if analysis is None:
        return ()
    return tuple(
        AnalystCrossRuleFact(
            relation_type=str(getattr(rel.relation_type, "value", rel.relation_type)),
            source_rule_id=rel.source_rule_id,
            target_rule_id=rel.target_rule_id,
            statement=rel.statement,
        )
        for rel in analysis.relationships
    )


def _unavailable_keys(*fact_groups: tuple[AnalystMetricFact, ...]) -> tuple[str, ...]:
    return tuple(
        fact.metric_key
        for group in fact_groups
        for fact in group
        if fact.status != MetricStatus.AVAILABLE.value
    )


def build_analyst_packet(
    baseline: BundleAnalysis,
    variation: BundleAnalysis | None = None,
) -> AnalystEvidencePacket:
    """Compose the packet, or raise a typed :class:`AnalystRefusalError`."""

    for side_name, analysis in (("baseline", baseline), ("variation", variation)):
        if analysis is not None and not analysis.analysis_ready:
            raise AnalystRefusalError(
                AnalystRefusalCode.EVIDENCE_STANDING_TOO_WEAK,
                f"The selected {side_name} bundle did not pass validation and "
                "metric computation, so the Analyst has no accepted evidence "
                "to restate.",
            )

    subject = variation if variation is not None else baseline
    subject_report = subject.diagnostic_report
    if subject_report is None:
        raise AnalystRefusalError(
            AnalystRefusalCode.INSUFFICIENT_EVIDENCE,
            "No deterministic diagnostic report is available for the selected evidence.",
        )

    lens: ConsequenceLensReport | None = None
    if variation is not None:
        lens_result = build_consequence_lens_report(baseline, variation)
        if isinstance(lens_result, ServiceError):
            raise AnalystRefusalError(
                AnalystRefusalCode.INSUFFICIENT_EVIDENCE,
                f"The consequence-lens projection is unavailable: {lens_result.message}",
            )
        lens = lens_result
        if not lens.compatibility.is_compatible:
            raise AnalystRefusalError(
                AnalystRefusalCode.INCOMPATIBLE_PAIR,
                "The selected pair fails the existing comparison contract, "
                "so the Analyst refuses to interpret it.",
            )

    baseline_identity = lens.baseline_identity if lens is not None else {}
    variation_identity = lens.variation_identity if lens is not None else {}
    manifest = baseline.validation.manifest
    identity = AnalystIdentity(
        subject_kind="comparison" if variation is not None else "single_run",
        baseline_run_id=(
            str(baseline_identity.get("run_id"))
            if lens is not None
            else (manifest.run.run_id if manifest is not None else None)
        ),
        variation_run_id=(str(variation_identity.get("run_id")) if lens is not None else None),
        experiment_id=(
            str(baseline_identity.get("experiment_id"))
            if lens is not None
            else (manifest.run.experiment_id if manifest is not None else None)
        ),
        metric_version=(
            str(baseline_identity.get("metric_version"))
            if lens is not None
            else (baseline.metrics.metric_version if baseline.metrics else None)
        ),
        baseline_standing=_standing(baseline),
        variation_standing=(_standing(variation) if variation is not None else None),
        same_experiment=lens.compatibility.same_experiment if lens else None,
        same_random_seed=lens.compatibility.same_random_seed if lens else None,
        same_metric_version=lens.compatibility.same_metric_version if lens else None,
        synthetic_match=lens.compatibility.synthetic_match if lens else None,
        comparison_compatible=lens.compatibility.is_compatible if lens else None,
    )

    traffic_facts = _facts(ANALYST_TRAFFIC_KEYS, lens=lens, subject=subject)
    vec_facts = _facts(ANALYST_VEC_KEYS, lens=lens, subject=subject)
    infrastructure_facts = _facts(ANALYST_INFRASTRUCTURE_KEYS, lens=lens, subject=subject)

    baseline_report = baseline.diagnostic_report if variation is not None else None
    diagnostics = AnalystDiagnostics(
        subject_side="variation" if variation is not None else "single_run",
        subject_readiness=subject_report.overall_readiness.value,
        subject_ruleset_version=subject_report.ruleset_version,
        subject_rules=_rule_facts(subject_report),
        baseline_readiness=(baseline_report.overall_readiness.value if baseline_report else None),
        baseline_triggered_rule_ids=(
            tuple(baseline_report.triggered_rule_ids) if baseline_report else ()
        ),
        cross_rule=_cross_rule_facts(subject_report),
        conflict_observations=tuple(subject_report.conflict_observations),
    )

    provenance = AnalystProvenance(
        baseline_bundle_fingerprint=baseline.validation.fingerprint,
        variation_bundle_fingerprint=(
            variation.validation.fingerprint if variation is not None else None
        ),
        baseline_metrics_input_fingerprint=(
            baseline.metrics.input_fingerprint if baseline.metrics else None
        ),
        variation_metrics_input_fingerprint=(
            variation.metrics.input_fingerprint
            if variation is not None and variation.metrics
            else None
        ),
        subject_diagnostic_fingerprint=subject_report.fingerprint(),
        baseline_diagnostic_fingerprint=(
            baseline_report.fingerprint() if baseline_report else None
        ),
        consequence_lens_fingerprint=lens.fingerprint if lens is not None else None,
    )

    limitations = list(_FIXED_LIMITATIONS)
    if identity.baseline_standing == "SYNTHETIC" and (
        identity.variation_standing in (None, "SYNTHETIC")
    ):
        limitations.append(
            "All selected evidence is synthetic; nothing here is Manchester "
            "observation, a live forecast, or admitted research."
        )

    changed_parameters: tuple[dict[str, JsonScalar], ...] = ()
    if lens is not None:
        changed_parameters = tuple(
            {key: _scalar(value) for key, value in entry.items()}
            for entry in lens.changed_seed_parameters
        )

    return AnalystEvidencePacket(
        identity=identity,
        traffic_facts=traffic_facts,
        vec_facts=vec_facts,
        infrastructure_facts=infrastructure_facts,
        changed_parameters=changed_parameters,
        diagnostics=diagnostics,
        provenance=provenance,
        unavailable_metric_keys=_unavailable_keys(traffic_facts, vec_facts, infrastructure_facts),
        limitations=tuple(limitations),
    )
