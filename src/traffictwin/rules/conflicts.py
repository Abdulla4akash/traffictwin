"""Report-level diagnostic conflict observations."""

from __future__ import annotations

from traffictwin.diagnostics.cross_rule import (
    CrossRuleReasoningReport,
    CrossRuleRelationType,
)
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricStatus
from traffictwin.rules.models import RuleResult, RuleStatus


def analyse_conflicts(
    results: list[RuleResult],
    evidence_pack: EvidencePack,
    cross_rule_analysis: CrossRuleReasoningReport,
) -> list[str]:
    """Return deterministic report-level conflict observations."""

    observations = [
        relationship.statement
        for relationship in cross_rule_analysis.relationships
        if relationship.relation_type is CrossRuleRelationType.CONFLICT
    ]
    metrics = evidence_pack.metric_collection.by_key()
    mean_util = metrics.get("infra.utilisation.mean")
    p95_util = metrics.get("infra.utilisation.p95")
    if (
        mean_util is not None
        and p95_util is not None
        and mean_util.status is MetricStatus.AVAILABLE
        and p95_util.status is MetricStatus.AVAILABLE
        and isinstance(mean_util.value, int | float)
        and isinstance(p95_util.value, int | float)
        and float(mean_util.value) < 0.60
        and float(p95_util.value) >= 0.90
    ):
        observations.append("Global average utilisation may hide a local hotspot.")
    if any(result.status is RuleStatus.CONFLICTING_EVIDENCE for result in results):
        observations.append(
            "The current evidence contains contradictions; follow-up experiments are needed "
            "before choosing one hypothesis."
        )
    return sorted(set(observations))
