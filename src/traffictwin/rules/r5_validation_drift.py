"""R5 training-to-validation drift candidate rule."""

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

PAIR_COUNT_KEY = "experiment.training_validation.pair_count"
MAX_GAP_KEY = "experiment.training_validation.max_absolute_gap"
MEAN_GAP_KEY = "experiment.training_validation.mean_absolute_gap"
SIGNED_GAP_KEY = "experiment.training_validation.mean_signed_gap"


class R5ValidationDriftRule(DiagnosticRule):
    """Identify a descriptive gap between explicitly paired training and validation results."""

    rule_id = "R5"
    title = "Training-to-validation drift candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R5."""

        cfg = config.r5
        lookup = MetricLookup(evidence_pack)
        pair_count = lookup.numeric(PAIR_COUNT_KEY)
        max_gap = lookup.numeric(MAX_GAP_KEY)
        mean_gap = lookup.numeric(MEAN_GAP_KEY)
        signed_gap = lookup.numeric(SIGNED_GAP_KEY)
        missing = [
            key
            for key, value in ((PAIR_COUNT_KEY, pair_count), (MAX_GAP_KEY, max_gap))
            if value is None
        ]
        if missing:
            return _insufficient(self, evidence_pack, evaluated_at, missing)
        assert pair_count is not None and max_gap is not None
        enough_pairs = pair_count >= cfg.minimum_pair_count
        large_gap = max_gap >= cfg.maximum_absolute_gap
        findings = [
            Finding(
                finding_id="R5-F1",
                statement="Explicit training-validation pair count is checked.",
                evidence_keys=[PAIR_COUNT_KEY],
                observed_values={"pair_count": pair_count},
                expected_condition=f"pair count >= {cfg.minimum_pair_count}",
                support=_support(enough_pairs),
            ),
            Finding(
                finding_id="R5-F2",
                statement="Maximum absolute paired gap is compared with the drift threshold.",
                evidence_keys=[MAX_GAP_KEY],
                observed_values={"maximum_absolute_gap": max_gap},
                expected_condition=f"maximum absolute gap >= {cfg.maximum_absolute_gap}",
                support=_support(large_gap),
            ),
        ]
        if mean_gap is not None:
            findings.append(
                Finding(
                    finding_id="R5-F3",
                    statement="Mean absolute paired gap is reported as supporting context.",
                    evidence_keys=[MEAN_GAP_KEY, SIGNED_GAP_KEY],
                    observed_values={"mean_absolute_gap": mean_gap, "mean_signed_gap": signed_gap},
                    expected_condition="descriptive context only",
                    support=FindingSupport.NEUTRAL,
                )
            )
        if enough_pairs and large_gap:
            status = RuleStatus.TRIGGERED
            hypothesis = (
                "The evaluated policy may not transfer consistently from the declared training "
                "setting to the paired validation setting."
            )
            confidence = confidence_from_support(
                required_complete=True,
                supporting_conditions=2,
                contradiction_count=0,
                validation_issues=0,
                missing_context=1,
            )
        elif large_gap and not enough_pairs:
            status = RuleStatus.CONFLICTING_EVIDENCE
            hypothesis = "A large observed gap is present, but too few explicit pairs support it."
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
            missing_evidence=["matched environment and checkpoint provenance"],
            alternative_explanations=[
                "different scenario difficulty",
                "checkpoint mismatch",
                "metric-definition mismatch",
                "sampling variability",
                "training and validation seeds are not comparable",
            ],
            recommendations=[
                Recommendation(
                    action="repeat matched training-validation comparisons with common seeds",
                    rationale="additional explicit pairs can test whether the gap is stable",
                    expected_direction="gap variability and failure cases become measurable",
                    prerequisite="matched policy, checkpoint, metric definition, and seed metadata",
                    verification_step="rebuild experiment evidence and rerun R5",
                )
            ],
            confidence=confidence,
            confidence_basis=[
                "confidence uses explicit pair count and deterministic absolute-gap thresholds"
            ],
            limitations=[
                "R5 is a drift candidate, not evidence of overfitting or a causal mechanism.",
                "Default thresholds are provisional synthetic-development values.",
            ],
        )


def _insufficient(
    rule: R5ValidationDriftRule,
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
                action="provide explicit paired training and validation metric observations",
                rationale="R5 does not infer training-validation relationships from labels",
                expected_direction="R5 readiness should increase",
                prerequisite="matched metric definitions, policies, checkpoints, and seeds",
                verification_step="build experiment evidence with declared pairs",
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["required experiment-level evidence for R5 is incomplete"],
    )


def _support(condition: bool) -> FindingSupport:
    return FindingSupport.SUPPORTS if condition else FindingSupport.CONTRADICTS
