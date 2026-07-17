"""R3 scenario-triviality candidate rule."""

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

ALGORITHM_COUNT_KEY = "experiment.algorithm.count"
CROSS_ALGORITHM_DISPERSION_KEY = "experiment.cross_algorithm_dispersion"
ALWAYS_LOCAL_GAP_KEY = "experiment.always_local_gap_from_best"
PRESSURE_INDICATOR_KEY = "experiment.pressure.indicator"


class R3ScenarioTrivialityRule(DiagnosticRule):
    """Identify scenarios that may not distinguish policies."""

    rule_id = "R3"
    title = "Scenario-triviality candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R3."""

        cfg = config.r3
        lookup = MetricLookup(evidence_pack)
        algorithm_count = lookup.numeric(ALGORITHM_COUNT_KEY)
        dispersion = lookup.numeric(CROSS_ALGORITHM_DISPERSION_KEY)
        local_gap = lookup.numeric(ALWAYS_LOCAL_GAP_KEY)
        pressure = lookup.numeric(PRESSURE_INDICATOR_KEY)

        missing = []
        if algorithm_count is None:
            missing.append(ALGORITHM_COUNT_KEY)
        if dispersion is None:
            missing.append(CROSS_ALGORITHM_DISPERSION_KEY)
        if algorithm_count is not None and algorithm_count < cfg.minimum_algorithms:
            missing.append(
                f"minimum compatible algorithms {cfg.minimum_algorithms} not met "
                f"(observed {int(algorithm_count)})"
            )
        if missing:
            return _insufficient(self, evidence_pack, evaluated_at, missing)

        assert algorithm_count is not None
        assert dispersion is not None

        findings = [
            Finding(
                finding_id="R3-F1",
                statement="Compatible algorithm count is compared with the configured minimum.",
                evidence_keys=[ALGORITHM_COUNT_KEY],
                observed_values={"algorithm_count": algorithm_count},
                expected_condition=f"algorithm count >= {cfg.minimum_algorithms}",
                support=FindingSupport.SUPPORTS,
            ),
            Finding(
                finding_id="R3-F2",
                statement="Cross-algorithm dispersion is compared with the configured maximum.",
                evidence_keys=[CROSS_ALGORITHM_DISPERSION_KEY],
                observed_values={"cross_algorithm_dispersion": dispersion},
                expected_condition=(
                    f"cross-algorithm dispersion <= {cfg.maximum_cross_algorithm_dispersion}"
                ),
                support=_support(dispersion <= cfg.maximum_cross_algorithm_dispersion),
            ),
        ]
        missing_context: list[str] = []
        if local_gap is None:
            missing_context.append(ALWAYS_LOCAL_GAP_KEY)
        else:
            findings.append(
                Finding(
                    finding_id="R3-F3",
                    statement=(
                        "Always-local gap from the best policy is compared with the configured "
                        "maximum."
                    ),
                    evidence_keys=[ALWAYS_LOCAL_GAP_KEY],
                    observed_values={"always_local_gap_from_best": local_gap},
                    expected_condition=(
                        f"always-local gap from best <= {cfg.maximum_local_gap_from_best}"
                    ),
                    support=_support(local_gap <= cfg.maximum_local_gap_from_best),
                )
            )
        if cfg.maximum_pressure_indicator is not None:
            if pressure is None:
                missing_context.append(PRESSURE_INDICATOR_KEY)
            else:
                findings.append(
                    Finding(
                        finding_id="R3-F4",
                        statement=(
                            "Scenario pressure indicator is compared with the configured maximum."
                        ),
                        evidence_keys=[PRESSURE_INDICATOR_KEY],
                        observed_values={"pressure_indicator": pressure},
                        expected_condition=(
                            f"pressure indicator <= {cfg.maximum_pressure_indicator}"
                        ),
                        support=_support(pressure <= cfg.maximum_pressure_indicator),
                    )
                )

        support_count = sum(1 for finding in findings if finding.support is FindingSupport.SUPPORTS)
        contradiction_count = sum(
            1 for finding in findings if finding.support is FindingSupport.CONTRADICTS
        )
        if support_count >= 2 and contradiction_count == 0:
            status = RuleStatus.TRIGGERED
            hypothesis = (
                "The current scenario may be too weak to reveal meaningful differences between "
                "offloading strategies."
            )
            confidence = confidence_from_support(
                required_complete=True,
                supporting_conditions=support_count,
                contradiction_count=contradiction_count,
                validation_issues=0,
                missing_context=len(missing_context),
            )
        elif support_count > 0 and contradiction_count > 0:
            status = RuleStatus.CONFLICTING_EVIDENCE
            hypothesis = (
                "Some evidence is consistent with scenario triviality, but other evidence suggests "
                "the scenario may still be discriminative."
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
                "all algorithms are genuinely similarly capable",
                "metric selection is insensitive",
                "sample size is too small",
                "training budgets are insufficient",
                "scenario parameters were not applied correctly",
                "aggregation masks rare hard cases",
            ],
            recommendations=[
                Recommendation(
                    action="increase scenario pressure in a controlled seed variation",
                    rationale=(
                        "harder demand, tier, or T1-burst settings may expose policy differences"
                    ),
                    expected_direction=(
                        "cross-algorithm dispersion may increase if the original seed was weak"
                    ),
                    prerequisite="new seed preserves provenance and common random seeds",
                    verification_step="recompute metrics and R3 on the new experiment evidence",
                ),
                Recommendation(
                    action=(
                        "increase compatible replicates before drawing scenario-sensitivity "
                        "conclusions"
                    ),
                    rationale=(
                        "small sample sizes can hide rare failures or inflate apparent similarity"
                    ),
                    expected_direction="scenario-discrimination evidence becomes more stable",
                    prerequisite="additional compatible runs",
                    verification_step="rerun experiment aggregation and diagnostics",
                ),
            ],
            confidence=confidence,
            confidence_basis=[
                "confidence uses compatible algorithm count, cross-algorithm dispersion, optional "
                "always-local gap, optional pressure evidence, and missing context"
            ],
            limitations=[
                "R3 consumes experiment-level EvidencePack metrics and returns insufficient "
                "evidence "
                "for ordinary single-run packs."
            ],
        )


def _insufficient(
    rule: R3ScenarioTrivialityRule,
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
                action="provide compatible multi-algorithm experiment evidence",
                rationale=(
                    "R3 requires cross-algorithm dispersion before scenario triviality can be "
                    "assessed."
                ),
                expected_direction="R3 readiness should increase",
                prerequisite="multiple compatible algorithms or policies under the same scenario",
                verification_step=(
                    "build an EvidencePack containing experiment-level dispersion metrics"
                ),
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["required experiment-level evidence for R3 is incomplete"],
    )


def _support(condition: bool) -> FindingSupport:
    return FindingSupport.SUPPORTS if condition else FindingSupport.CONTRADICTS
