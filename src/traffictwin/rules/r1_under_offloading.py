"""R1 under-offloading candidate rule."""

from __future__ import annotations

from datetime import datetime

from traffictwin.evidence.pack import EvidencePack
from traffictwin.rules.base import (
    DiagnosticRule,
    MetricLookup,
    confidence_from_support,
    validation_issue_count,
)
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


class R1UnderOffloadingRule(DiagnosticRule):
    """Identify candidate under-use of external compute capacity."""

    rule_id = "R1"
    title = "Under-offloading candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R1."""

        cfg = config.r1
        lookup = MetricLookup(evidence_pack)
        task_count = lookup.numeric("task.generated.count")
        t1_completion = lookup.mapping_number("task.completion.rate_by_class", "T1")
        offload_rate = lookup.numeric("task.offload.rate")
        utilisation = lookup.numeric("infra.utilisation.mean")
        tier_metric = lookup.metric("task.completion.rate_by_vehicle_tier")

        missing = _missing_required(task_count, t1_completion, offload_rate, utilisation)
        if task_count is not None and task_count < cfg.minimum_task_count:
            missing.append(
                f"minimum task sample {cfg.minimum_task_count} not met (observed {int(task_count)})"
            )
        if missing:
            return _insufficient(self, evidence_pack, evaluated_at, missing)

        assert task_count is not None
        assert t1_completion is not None
        assert offload_rate is not None
        assert utilisation is not None

        t1_miss_rate = 1.0 - t1_completion
        findings = [
            Finding(
                finding_id="R1-F1",
                statement="T1 task miss rate is compared with the configured R1 threshold.",
                evidence_keys=["task.completion.rate_by_class"],
                observed_values={"t1_miss_rate": t1_miss_rate},
                expected_condition=f"T1 miss rate >= {cfg.t1_miss_rate_min}",
                support=_support(t1_miss_rate >= cfg.t1_miss_rate_min),
            ),
            Finding(
                finding_id="R1-F2",
                statement=(
                    "Mean RSU utilisation is compared with the configured available-capacity "
                    "threshold."
                ),
                evidence_keys=["infra.utilisation.mean"],
                observed_values={"mean_rsu_utilisation": utilisation},
                expected_condition=f"mean RSU utilisation <= {cfg.rsu_utilisation_max}",
                support=_support(utilisation <= cfg.rsu_utilisation_max),
            ),
            Finding(
                finding_id="R1-F3",
                statement=(
                    "Recognised offload rate is compared with the configured low-offload threshold."
                ),
                evidence_keys=["task.offload.rate"],
                observed_values={"offload_rate": offload_rate},
                expected_condition=f"offload rate <= {cfg.offload_rate_max}",
                support=_support(offload_rate <= cfg.offload_rate_max),
            ),
            Finding(
                finding_id="R1-F4",
                statement="Task sample size meets the configured minimum.",
                evidence_keys=["task.generated.count"],
                observed_values={"task_count": task_count},
                expected_condition=f"task count >= {cfg.minimum_task_count}",
                support=FindingSupport.SUPPORTS,
            ),
        ]

        missing_context: list[str] = []
        limitations: list[str] = []
        if tier_metric is None or not lookup.has_available("task.completion.rate_by_vehicle_tier"):
            missing_context.append("low-tier vehicle breakdown")
            limitations.append(
                "Phase 3 evidence does not provide a T1-by-low-tier cross-tab; "
                "R1 confidence is capped without that direct evidence."
            )
            if tier_metric is not None:
                findings.append(
                    Finding(
                        finding_id="R1-F5",
                        statement=(
                            "Low-tier vehicle breakdown is unavailable in the metric collection."
                        ),
                        evidence_keys=["task.completion.rate_by_vehicle_tier"],
                        observed_values={"status": tier_metric.status.value},
                        expected_condition="low-tier completion evidence available",
                        support=FindingSupport.NEUTRAL,
                    )
                )
        missing_context.append("decision-time action availability")

        support_count = sum(1 for finding in findings if finding.support is FindingSupport.SUPPORTS)
        contradiction_count = sum(
            1 for finding in findings if finding.support is FindingSupport.CONTRADICTS
        )
        high_t1_miss = t1_miss_rate >= cfg.t1_miss_rate_min
        usable_capacity = utilisation <= cfg.rsu_utilisation_max
        low_offload = offload_rate <= cfg.offload_rate_max

        if high_t1_miss and usable_capacity and low_offload:
            status = RuleStatus.TRIGGERED
            hypothesis = (
                "The policy may be leaving usable external compute capacity idle for "
                "safety-critical tasks."
            )
            confidence = confidence_from_support(
                required_complete=True,
                supporting_conditions=support_count,
                contradiction_count=contradiction_count,
                validation_issues=validation_issue_count(evidence_pack),
                missing_context=len(missing_context),
            )
        elif high_t1_miss and low_offload and not usable_capacity:
            status = RuleStatus.CONFLICTING_EVIDENCE
            hypothesis = (
                "Some evidence is consistent with under-offloading, but other evidence does not "
                "support the pattern."
            )
            confidence = ConfidenceCategory.LOW
        elif high_t1_miss and usable_capacity and not low_offload:
            status = RuleStatus.CONFLICTING_EVIDENCE
            hypothesis = (
                "Safety-critical task outcomes and available capacity are concerning, but offload "
                "use is not low under the configured threshold."
            )
            confidence = ConfidenceCategory.LOW
        else:
            status = RuleStatus.NOT_TRIGGERED
            hypothesis = None
            confidence = ConfidenceCategory.UNAVAILABLE

        return result_from_findings(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            title=self.title,
            status=status,
            synthetic=evidence_pack.synthetic,
            evaluated_at=evaluated_at,
            hypothesis=hypothesis,
            findings=findings,
            missing_evidence=missing_context,
            alternative_explanations=[
                "poor link quality",
                "V2I or V2V unavailable at decision time",
                "reward-function priorities",
                "stale or incompatible checkpoint",
                "distribution shift",
                "missing decision-time state",
                "task placement constraints",
                "data-location constraints",
            ],
            recommendations=_recommendations(),
            confidence=confidence,
            confidence_basis=[
                "confidence uses T1 miss rate, offload rate, infrastructure utilisation, "
                "sample size, validation quality, and missing direct low-tier evidence"
            ],
            limitations=limitations,
        )


def _missing_required(
    task_count: float | None,
    t1_completion: float | None,
    offload_rate: float | None,
    utilisation: float | None,
) -> list[str]:
    missing: list[str] = []
    if task_count is None:
        missing.append("task.generated.count")
    if t1_completion is None:
        missing.append("task.completion.rate_by_class.T1")
    if offload_rate is None:
        missing.append("task.offload.rate")
    if utilisation is None:
        missing.append("infra.utilisation.mean")
    return missing


def _insufficient(
    rule: R1UnderOffloadingRule,
    evidence_pack: EvidencePack,
    evaluated_at: datetime,
    missing: list[str],
) -> RuleResult:
    return result_from_findings(
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        title=rule.title,
        status=RuleStatus.INSUFFICIENT_EVIDENCE,
        synthetic=evidence_pack.synthetic,
        evaluated_at=evaluated_at,
        hypothesis=None,
        missing_evidence=missing,
        recommendations=[
            Recommendation(
                action=(
                    "provide task-class, offload, infrastructure-utilisation, and sufficient "
                    "sample evidence"
                ),
                rationale=(
                    "R1 needs these inputs before it can identify an under-offloading candidate."
                ),
                expected_direction="R1 readiness should increase",
                prerequisite="accepted EvidencePack with required metric keys",
                verification_step="rerun diagnostics and confirm R1 is no longer insufficient",
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["required evidence for R1 is incomplete"],
    )


def _support(condition: bool) -> FindingSupport:
    return FindingSupport.SUPPORTS if condition else FindingSupport.CONTRADICTS


def _recommendations() -> list[Recommendation]:
    return [
        Recommendation(
            action="inspect V2I and V2V action availability for the affected scenario",
            rationale=(
                "low offload use is only meaningful if external actions were available at "
                "decision time"
            ),
            expected_direction=(
                "clarifies whether low offload is policy behavior or action-space limitation"
            ),
            prerequisite="decision-time action availability evidence",
            verification_step="compare the rule result after adding action-availability evidence",
        ),
        Recommendation(
            action="compare with a better-trained or alternative checkpoint under the same seed",
            rationale=(
                "checkpoint evidence is needed before undertraining is considered more than an "
                "alternative explanation"
            ),
            expected_direction=(
                "T1 completion may increase if policy capacity was the limiting factor"
            ),
            prerequisite="compatible checkpoint comparison with common random seeds",
            verification_step=(
                "evaluate the same metrics and diagnostic rule on the comparison EvidencePack"
            ),
        ),
    ]
