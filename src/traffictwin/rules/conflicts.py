"""Report-level diagnostic conflict observations."""

from __future__ import annotations

from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.results import MetricStatus
from traffictwin.rules.models import RuleResult, RuleStatus


def analyse_conflicts(results: list[RuleResult], evidence_pack: EvidencePack) -> list[str]:
    """Return deterministic report-level conflict observations."""

    statuses = {result.rule_id: result.status for result in results}
    observations: list[str] = []
    if statuses.get("R1") is RuleStatus.TRIGGERED and statuses.get("R2") is RuleStatus.TRIGGERED:
        observations.append(
            "Evidence supports both policy under-use and infrastructure saturation candidates; "
            "the current report does not choose between them."
        )
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
