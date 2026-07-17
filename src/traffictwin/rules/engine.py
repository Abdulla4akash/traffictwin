"""Deterministic diagnostic rule engine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from traffictwin.diagnostics.report import (
    DiagnosticReport,
    OverallReadiness,
    diagnostic_report_id,
    readiness_from_results,
)
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import JsonScalar
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.conflicts import analyse_conflicts
from traffictwin.rules.models import (
    ConfidenceCategory,
    Finding,
    FindingSupport,
    RuleResult,
    RuleStatus,
    result_from_findings,
)
from traffictwin.rules.registry import enabled_rules


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def evaluate_rules(
    evidence_pack: EvidencePack,
    rule_config: RuleSetConfig | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> DiagnosticReport:
    """Evaluate deterministic diagnostic rules against one EvidencePack."""

    config = rule_config or RuleSetConfig()
    generated_at = clock()
    metric_keys = set(evidence_pack.metric_collection.by_key())
    results: list[RuleResult] = []
    warnings: list[str] = []
    for rule in enabled_rules(config.enabled_rule_ids()):
        try:
            result = rule.evaluate(evidence_pack, config, generated_at)
        except Exception as exc:  # pragma: no cover - exercised through a synthetic test rule
            result = _invalid_result(
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                title=rule.title,
                synthetic=evidence_pack.synthetic,
                evaluated_at=generated_at,
                message=str(exc),
            )
            warnings.append(f"{rule.rule_id} raised {exc.__class__.__name__}: {exc}")
        result = _validate_evidence_keys(result, metric_keys, warnings)
        results.append(result)

    results = sorted(results, key=lambda item: item.rule_id)
    triggered = [result.rule_id for result in results if result.status is RuleStatus.TRIGGERED]
    insufficient = [
        result.rule_id for result in results if result.status is RuleStatus.INSUFFICIENT_EVIDENCE
    ]
    conflicting = [
        result.rule_id for result in results if result.status is RuleStatus.CONFLICTING_EVIDENCE
    ]
    blocked = sorted(
        {
            rule_id
            for result in results
            if result.rule_id == "R0"
            for rule_id in _blocked_rules_from_r0(result)
        }
        | set(insufficient)
    )
    report_id = diagnostic_report_id(
        evidence_pack_id=evidence_pack.pack_id,
        ruleset_version=config.ruleset_version,
        generated_at=generated_at,
    )
    readiness = readiness_from_results(results)
    if evidence_pack.validation_summary.get("may_import") is False:
        readiness = OverallReadiness.INVALID
    return DiagnosticReport(
        report_id=report_id,
        evidence_pack_id=evidence_pack.pack_id,
        run_context=dict(evidence_pack.run_context),
        generated_at=generated_at,
        ruleset_version=config.ruleset_version,
        rule_config=config,
        results=results,
        triggered_rule_ids=triggered,
        insufficient_rule_ids=insufficient,
        conflicting_rule_ids=conflicting,
        blocked_rules=blocked,
        evidence_summary={
            "validation": evidence_pack.validation_summary,
            "availability": evidence_pack.evidence_availability.model_dump(mode="json"),
        },
        overall_readiness=readiness,
        synthetic=evidence_pack.synthetic,
        provenance={
            "source_evidence_fingerprint": evidence_pack.fingerprint(),
            "source_bundle_fingerprint": evidence_pack.source_bundle_fingerprint,
            "metric_version": evidence_pack.metric_collection.metric_version,
        },
        warnings=sorted(set(warnings)),
        conflict_observations=analyse_conflicts(results, evidence_pack),
    )


def _validate_evidence_keys(
    result: RuleResult,
    metric_keys: set[str],
    warnings: list[str],
) -> RuleResult:
    cited = set(result.evidence_keys)
    for finding in result.findings:
        cited.update(finding.evidence_keys)
    missing = sorted(key for key in cited if key not in metric_keys)
    if not missing:
        return result
    warnings.append(
        f"{result.rule_id} cited metric keys that are not present in the EvidencePack: "
        f"{', '.join(missing)}"
    )
    findings = [
        *result.findings,
        Finding(
            finding_id=f"{result.rule_id}-TECH-MISSING-EVIDENCE-KEY",
            statement="The rule cited evidence keys that are absent from the EvidencePack.",
            evidence_keys=[],
            observed_values={"missing_evidence_keys": ", ".join(missing)},
            expected_condition=(
                "all cited evidence keys exist in the EvidencePack metric collection"
            ),
            support=FindingSupport.NEUTRAL,
        ),
    ]
    return result_from_findings(
        rule_id=result.rule_id,
        rule_version=result.rule_version,
        title=result.title,
        status=RuleStatus.INVALID,
        synthetic=result.synthetic,
        evaluated_at=result.evaluated_at,
        hypothesis=result.hypothesis,
        findings=findings,
        missing_evidence=[*result.missing_evidence, *missing],
        alternative_explanations=result.alternative_explanations,
        recommendations=result.recommendations,
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=[*result.confidence_basis, "rule cited absent evidence keys"],
        limitations=result.limitations,
        metadata=result.metadata,
    )


def _invalid_result(
    *,
    rule_id: str,
    rule_version: str,
    title: str,
    synthetic: bool,
    evaluated_at: datetime,
    message: str,
) -> RuleResult:
    return result_from_findings(
        rule_id=rule_id,
        rule_version=rule_version,
        title=title,
        status=RuleStatus.INVALID,
        synthetic=synthetic,
        evaluated_at=evaluated_at,
        hypothesis=None,
        findings=[
            Finding(
                finding_id=f"{rule_id}-EXCEPTION",
                statement="Rule evaluation failed and was isolated from other rules.",
                evidence_keys=[],
                observed_values={"error": message},
                expected_condition="rule executes without runtime failure",
                support=FindingSupport.NEUTRAL,
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["runtime failure during rule evaluation"],
    )


def _blocked_rules_from_r0(result: RuleResult) -> list[str]:
    value: JsonScalar = result.metadata.get("blocked_rules")
    if not isinstance(value, str) or not value:
        return []
    return [item for item in value.split(",") if item]
