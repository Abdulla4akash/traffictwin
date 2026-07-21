"""R4 load-imbalance candidate rule."""

from __future__ import annotations

from datetime import datetime

from traffictwin.evidence.pack import EvidencePack
from traffictwin.rules.base import DiagnosticRule, MetricLookup, confidence_from_support
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

JAIN_KEY = "infra.load_balance.jain_capacity_normalised"
MEAN_UTILISATION_KEY = "infra.utilisation.mean"
RSU_COUNT_KEY = "infra.observed_rsu.count"


class R4LoadImbalanceRule(DiagnosticRule):
    """Identify uneven capacity-normalised RSU load at moderate total use."""

    rule_id = "R4"
    title = "Load-imbalance candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R4."""

        cfg = config.r4
        lookup = MetricLookup(evidence_pack)
        jain = lookup.numeric(JAIN_KEY)
        mean_utilisation = lookup.numeric(MEAN_UTILISATION_KEY)
        rsu_count = lookup.numeric(RSU_COUNT_KEY)
        missing = [
            key
            for key, value in (
                (JAIN_KEY, jain),
                (MEAN_UTILISATION_KEY, mean_utilisation),
                (RSU_COUNT_KEY, rsu_count),
            )
            if value is None
        ]
        if missing:
            return _insufficient(self, evidence_pack, evaluated_at, missing)
        assert jain is not None and mean_utilisation is not None and rsu_count is not None
        enough_rsus = rsu_count >= cfg.minimum_rsu_count
        imbalanced = jain <= cfg.maximum_jain_index
        moderate_total = mean_utilisation <= cfg.maximum_mean_utilisation
        findings = [
            Finding(
                finding_id="R4-F1",
                statement="Observed RSU count is compared with the configured minimum.",
                evidence_keys=[RSU_COUNT_KEY],
                observed_values={"observed_rsu_count": rsu_count},
                expected_condition=f"RSU count >= {cfg.minimum_rsu_count}",
                support=_support(enough_rsus),
            ),
            Finding(
                finding_id="R4-F2",
                statement=(
                    "Capacity-normalised Jain index is compared with the imbalance threshold."
                ),
                evidence_keys=[JAIN_KEY],
                observed_values={"jain_capacity_normalised": jain},
                expected_condition=f"Jain index <= {cfg.maximum_jain_index}",
                support=_support(imbalanced),
            ),
            Finding(
                finding_id="R4-F3",
                statement="Mean utilisation is checked for remaining aggregate capacity.",
                evidence_keys=[MEAN_UTILISATION_KEY],
                observed_values={"mean_utilisation": mean_utilisation},
                expected_condition=f"mean utilisation <= {cfg.maximum_mean_utilisation}",
                support=_support(moderate_total),
            ),
        ]
        support_count = sum(f.support is FindingSupport.SUPPORTS for f in findings)
        if enough_rsus and imbalanced and moderate_total:
            status = RuleStatus.TRIGGERED
            hypothesis = (
                "RSU placement or routing may be distributing work unevenly despite remaining "
                "aggregate capacity."
            )
            confidence = confidence_from_support(
                required_complete=True,
                supporting_conditions=support_count,
                contradiction_count=0,
                validation_issues=0,
                missing_context=1,
            )
        elif imbalanced and enough_rsus:
            status = RuleStatus.CONFLICTING_EVIDENCE
            hypothesis = (
                "Load is uneven, but aggregate utilisation does not clearly separate imbalance "
                "from overall capacity pressure."
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
            missing_evidence=["task-to-RSU routing and location context"],
            alternative_explanations=[
                "uneven spatial demand",
                "different RSU capacities",
                "temporary hotspot rather than persistent imbalance",
                "missing routing constraints",
            ],
            recommendations=[
                Recommendation(
                    action="compare a controlled routing or RSU-placement variation",
                    rationale="a controlled change can test whether the uneven load is avoidable",
                    expected_direction="Jain index may increase without increasing missed tasks",
                    prerequisite="same scenario, policy, and common random seeds",
                    verification_step="recompute R4 and outcome metrics for both conditions",
                )
            ],
            confidence=confidence,
            confidence_basis=[
                "confidence uses capacity-normalised balance, mean utilisation, and RSU count"
            ],
            limitations=[
                "Default thresholds are provisional synthetic-development values.",
                "R4 identifies a candidate imbalance and does not prove placement or routing "
                "cause.",
            ],
        )


def _insufficient(
    rule: R4LoadImbalanceRule,
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
        missing_evidence=missing,
        recommendations=[
            Recommendation(
                action="provide capacity, active-task, utilisation, and RSU-count evidence",
                rationale="R4 requires a capacity-normalised multi-RSU comparison",
                expected_direction="R4 readiness should increase",
                prerequisite="compatible infrastructure records",
                verification_step="recompute infrastructure metrics and rerun diagnostics",
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["required evidence for R4 is incomplete"],
    )


def _support(condition: bool) -> FindingSupport:
    return FindingSupport.SUPPORTS if condition else FindingSupport.CONTRADICTS
