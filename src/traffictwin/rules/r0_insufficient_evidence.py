"""R0 insufficient or inconsistent evidence rule."""

from __future__ import annotations

from datetime import datetime

from traffictwin.evidence.availability import EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricStatus
from traffictwin.rules.base import DiagnosticRule, MetricLookup, validation_blocking_count
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.models import (
    ConfidenceCategory,
    Finding,
    FindingSupport,
    Recommendation,
    RuleResult,
    RuleStatus,
    result_from_findings,
)


class R0InsufficientEvidenceRule(DiagnosticRule):
    """Identify validation and evidence gaps that block or qualify diagnosis."""

    rule_id = "R0"
    title = "Insufficient or inconsistent evidence"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R0."""

        del config
        lookup = MetricLookup(evidence_pack)
        blocking_count = validation_blocking_count(evidence_pack)
        may_import = evidence_pack.validation_summary.get("may_import")
        evidence = evidence_pack.evidence_availability
        blocked_rules = _blocked_rules(evidence_pack)
        invalid_metric_keys = sorted(
            metric.metric_key
            for metric in evidence_pack.metric_collection.results
            if metric.status is MetricStatus.INVALID
        )
        findings: list[Finding] = []
        missing: list[str] = []

        if may_import is False or blocking_count > 0:
            findings.append(
                Finding(
                    finding_id="R0-F1",
                    statement=(
                        "Validation contains blocking errors or the bundle may not be imported."
                    ),
                    evidence_keys=_first_existing_keys(lookup, ["task.generated.count"]),
                    observed_values={
                        "may_import": may_import,
                        "blocking_validation_findings": blocking_count,
                    },
                    expected_condition="may_import is true and error/fatal findings are zero",
                    support=FindingSupport.SUPPORTS,
                )
            )
            missing.append("repair validation errors before diagnostic rules are interpreted")

        if invalid_metric_keys:
            findings.append(
                Finding(
                    finding_id="R0-F2",
                    statement="One or more metric results are invalid.",
                    evidence_keys=invalid_metric_keys[:8],
                    observed_values={"invalid_metric_count": len(invalid_metric_keys)},
                    expected_condition=(
                        "diagnostic inputs should be available or explicitly unavailable, "
                        "not invalid"
                    ),
                    support=FindingSupport.SUPPORTS,
                )
            )

        if evidence.diagnosis is not EvidenceStatus.AVAILABLE:
            findings.append(
                Finding(
                    finding_id="R0-F3",
                    statement="The evidence summary marks diagnosis as unavailable or invalid.",
                    evidence_keys=_first_existing_keys(
                        lookup,
                        ["task.generated.count", "infra.utilisation.mean"],
                    ),
                    observed_values={"diagnosis_evidence": evidence.diagnosis.value},
                    expected_condition="diagnosis evidence category should be available",
                    support=FindingSupport.SUPPORTS,
                )
            )
            missing.append("complete the evidence categories required by the requested rules")

        if blocked_rules:
            findings.append(
                Finding(
                    finding_id="R0-F4",
                    statement="Some diagnostic rules are blocked by missing required evidence.",
                    evidence_keys=_blocked_rule_evidence_keys(lookup, blocked_rules),
                    observed_values={"blocked_rules": ", ".join(blocked_rules)},
                    expected_condition="required evidence for each enabled rule is available",
                    support=FindingSupport.SUPPORTS,
                )
            )

        if not findings:
            return result_from_findings(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                title=self.title,
                status=RuleStatus.NOT_TRIGGERED,
                synthetic=evidence_pack.synthetic,
                evaluated_at=evaluated_at,
                hypothesis=None,
                findings=[
                    Finding(
                        finding_id="R0-F0",
                        statement=(
                            "No blocking validation or required-evidence issue was detected "
                            "for implemented rules."
                        ),
                        evidence_keys=_first_existing_keys(
                            lookup,
                            ["task.generated.count", "infra.utilisation.mean"],
                        ),
                        observed_values={"may_import": may_import},
                        expected_condition=(
                            "no blocking validation or implemented-rule evidence gaps"
                        ),
                        support=FindingSupport.NEUTRAL,
                    )
                ],
                confidence=ConfidenceCategory.UNAVAILABLE,
                confidence_basis=["R0 did not identify a data-readiness hypothesis."],
            )

        return result_from_findings(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            title=self.title,
            status=RuleStatus.TRIGGERED,
            synthetic=evidence_pack.synthetic,
            evaluated_at=evaluated_at,
            hypothesis=(
                "Evidence is insufficient or inconsistent for at least one diagnostic "
                "interpretation."
            ),
            findings=findings,
            missing_evidence=sorted(set(missing)),
            recommendations=[
                Recommendation(
                    action=(
                        "repair or provide the missing evidence before interpreting blocked "
                        "hypotheses"
                    ),
                    rationale=(
                        "R0 suppresses unsupported diagnostic advice when evidence is incomplete "
                        "or inconsistent."
                    ),
                    expected_direction="diagnostic readiness should increase",
                    prerequisite="updated validation report and evidence availability summary",
                    verification_step=(
                        "rebuild the EvidencePack and rerun deterministic diagnostics"
                    ),
                )
            ],
            confidence=ConfidenceCategory.HIGH if blocking_count else ConfidenceCategory.MODERATE,
            confidence_basis=[
                "confidence reflects validation status, metric validity, and required-evidence "
                "completeness"
            ],
            metadata={"blocked_rules": ",".join(blocked_rules)},
        )


def _blocked_rules(evidence_pack: EvidencePack) -> list[str]:
    evidence = evidence_pack.evidence_availability
    blocked: list[str] = []
    if evidence.tasks not in {EvidenceStatus.AVAILABLE, EvidenceStatus.PARTIAL}:
        blocked.extend(["R1", "R2", "R8"])
    if evidence.infrastructure not in {EvidenceStatus.AVAILABLE, EvidenceStatus.PARTIAL}:
        blocked.extend(["R1", "R2", "R4"])
    return sorted(set(blocked))


def _blocked_rule_evidence_keys(lookup: MetricLookup, blocked_rules: list[str]) -> list[str]:
    candidates: list[str] = []
    if "R1" in blocked_rules:
        candidates.extend(
            [
                "task.generated.count",
                "task.completion.rate_by_class",
                "task.offload.rate",
                "infra.utilisation.mean",
            ]
        )
    if "R2" in blocked_rules:
        candidates.extend(
            [
                "infra.saturation.duration_s",
                "infra.queue_length.max",
                "task.incomplete.rate",
            ]
        )
    if "R3" in blocked_rules:
        candidates.extend(["experiment.algorithm.count", "experiment.cross_algorithm_dispersion"])
    if "R4" in blocked_rules:
        candidates.extend(
            [
                "infra.load_balance.jain_capacity_normalised",
                "infra.utilisation.mean",
                "infra.observed_rsu.count",
            ]
        )
    if "R8" in blocked_rules:
        candidates.extend(["task.energy.per_completed_j", "task.completed.count"])
    return _first_existing_keys(lookup, candidates)


def _first_existing_keys(lookup: MetricLookup, candidates: list[str]) -> list[str]:
    existing = lookup.available_metric_keys()
    return [key for key in candidates if key in existing]
