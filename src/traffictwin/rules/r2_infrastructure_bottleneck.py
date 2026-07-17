"""R2 infrastructure-bottleneck candidate rule."""

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


class R2InfrastructureBottleneckRule(DiagnosticRule):
    """Identify infrastructure pressure aligned with degraded task outcomes."""

    rule_id = "R2"
    title = "Infrastructure-bottleneck candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R2."""

        cfg = config.r2
        lookup = MetricLookup(evidence_pack)
        task_count = lookup.numeric("task.generated.count")
        completed_count = lookup.numeric("task.completed.count")
        incomplete_rate = lookup.numeric("task.incomplete.rate")
        deadline_rate = lookup.numeric("task.deadline_miss.completed_observed_rate")
        queue_max = lookup.numeric("infra.queue_length.max")
        utilisation_p95 = lookup.numeric("infra.utilisation.p95")
        saturation_duration = lookup.numeric("infra.saturation.duration_s")
        saturation_episodes = lookup.numeric("infra.saturation.episode_count")

        missing = _missing_required(
            task_count,
            incomplete_rate,
            queue_max,
            utilisation_p95,
            saturation_duration,
            saturation_episodes,
        )
        if missing:
            return _insufficient(self, evidence_pack, evaluated_at, missing)

        assert task_count is not None
        assert incomplete_rate is not None
        assert queue_max is not None
        assert utilisation_p95 is not None
        assert saturation_duration is not None
        assert saturation_episodes is not None

        missed_tasks = incomplete_rate * task_count
        if completed_count is not None and deadline_rate is not None:
            missed_tasks += completed_count * deadline_rate

        findings = [
            Finding(
                finding_id="R2-F1",
                statement="P95 utilisation is compared with the configured saturation threshold.",
                evidence_keys=["infra.utilisation.p95"],
                observed_values={"p95_utilisation": utilisation_p95},
                expected_condition=f"P95 utilisation >= {cfg.saturation_threshold}",
                support=_support(utilisation_p95 >= cfg.saturation_threshold),
            ),
            Finding(
                finding_id="R2-F2",
                statement="Saturation duration is compared with the configured minimum duration.",
                evidence_keys=["infra.saturation.duration_s"],
                observed_values={"saturation_duration_s": saturation_duration},
                expected_condition=(
                    f"saturation duration >= {cfg.minimum_saturation_duration_s} seconds"
                ),
                support=_support(saturation_duration >= cfg.minimum_saturation_duration_s),
            ),
            Finding(
                finding_id="R2-F3",
                statement=(
                    "Maximum queue length is compared with the configured high-queue threshold."
                ),
                evidence_keys=["infra.queue_length.max"],
                observed_values={"max_queue_length": queue_max},
                expected_condition=f"max queue length >= {cfg.queue_length_high_min}",
                support=_support(queue_max >= cfg.queue_length_high_min),
            ),
            Finding(
                finding_id="R2-F4",
                statement="Estimated missed tasks are compared with the configured minimum.",
                evidence_keys=[
                    "task.generated.count",
                    "task.completed.count",
                    "task.incomplete.rate",
                    "task.deadline_miss.completed_observed_rate",
                ],
                observed_values={"estimated_missed_tasks": missed_tasks},
                expected_condition=f"estimated missed tasks >= {cfg.minimum_missed_tasks}",
                support=_support(missed_tasks >= cfg.minimum_missed_tasks),
            ),
            Finding(
                finding_id="R2-F5",
                statement="At least one saturation episode is present.",
                evidence_keys=["infra.saturation.episode_count"],
                observed_values={"saturation_episodes": saturation_episodes},
                expected_condition="saturation episode count > 0",
                support=_support(saturation_episodes > 0),
            ),
        ]
        limitations = [
            "Phase 3 evidence contains aggregate saturation and queue metrics but not direct "
            "task-to-saturation temporal overlap.",
        ]
        missing_context = ["task misses overlapping saturation windows"]
        if cfg.queue_growth_required:
            missing_context.append("direct queue-growth time series")
            limitations.append(
                "Queue growth is represented by aggregate queue pressure until an EvidencePack "
                "contains explicit growth evidence."
            )

        support_count = sum(1 for finding in findings if finding.support is FindingSupport.SUPPORTS)
        contradiction_count = sum(
            1 for finding in findings if finding.support is FindingSupport.CONTRADICTS
        )
        saturated = utilisation_p95 >= cfg.saturation_threshold
        sustained = saturation_duration >= cfg.minimum_saturation_duration_s
        queue_high = queue_max >= cfg.queue_length_high_min
        task_misses = missed_tasks >= cfg.minimum_missed_tasks
        has_episode = saturation_episodes > 0

        if saturated and sustained and queue_high and task_misses and has_episode:
            status = RuleStatus.TRIGGERED
            hypothesis = (
                "Infrastructure capacity or placement may be constraining task completion during "
                "sustained load."
            )
            confidence = confidence_from_support(
                required_complete=True,
                supporting_conditions=support_count,
                contradiction_count=0 if contradiction_count <= 1 else contradiction_count,
                validation_issues=validation_issue_count(evidence_pack),
                missing_context=len(missing_context),
            )
        elif (saturated or sustained or queue_high or has_episode) and task_misses:
            status = RuleStatus.CONFLICTING_EVIDENCE
            hypothesis = (
                "Some infrastructure-pressure evidence is present, but the full bottleneck pattern "
                "is not consistently supported."
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
                "policy routing imbalance",
                "one RSU receiving disproportionate demand",
                "communication bottleneck",
                "action-space restrictions",
                "scenario configuration error",
                "unreliable utilisation instrumentation",
                "temporary demand burst rather than structural capacity limitation",
            ],
            recommendations=[
                Recommendation(
                    action="test increased RSU capacity in a controlled variation",
                    rationale=(
                        "capacity changes can test whether saturation pressure is limiting outcomes"
                    ),
                    expected_direction=(
                        "saturation duration and missed-task indicators may decrease"
                    ),
                    prerequisite="same seed, common random seed, unchanged policy",
                    verification_step=(
                        "compare EvidencePacks before and after the capacity variation"
                    ),
                ),
                Recommendation(
                    action="inspect communication and queue-delay components",
                    rationale=(
                        "queue pressure alone does not distinguish compute capacity from "
                        "communication delay"
                    ),
                    expected_direction="clarifies the bottleneck candidate",
                    prerequisite="queue-delay or communication-delay evidence",
                    verification_step="rerun diagnostics with the additional evidence",
                ),
            ],
            confidence=confidence,
            confidence_basis=[
                "confidence uses saturation duration, utilisation, queue pressure, missed-task "
                "evidence, validation quality, and missing temporal-overlap evidence"
            ],
            limitations=limitations,
        )


def _missing_required(
    task_count: float | None,
    incomplete_rate: float | None,
    queue_max: float | None,
    utilisation_p95: float | None,
    saturation_duration: float | None,
    saturation_episodes: float | None,
) -> list[str]:
    missing: list[str] = []
    if task_count is None:
        missing.append("task.generated.count")
    if incomplete_rate is None:
        missing.append("task.incomplete.rate")
    if queue_max is None:
        missing.append("infra.queue_length.max")
    if utilisation_p95 is None:
        missing.append("infra.utilisation.p95")
    if saturation_duration is None:
        missing.append("infra.saturation.duration_s")
    if saturation_episodes is None:
        missing.append("infra.saturation.episode_count")
    return missing


def _insufficient(
    rule: R2InfrastructureBottleneckRule,
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
                action="provide per-RSU utilisation, saturation, queue, and task-outcome evidence",
                rationale=(
                    "R2 needs infrastructure pressure and task outcome inputs before evaluation."
                ),
                expected_direction="R2 readiness should increase",
                prerequisite="accepted EvidencePack with infrastructure and task metrics",
                verification_step="rerun diagnostics and confirm R2 is no longer insufficient",
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["required evidence for R2 is incomplete"],
    )


def _support(condition: bool) -> FindingSupport:
    return FindingSupport.SUPPORTS if condition else FindingSupport.CONTRADICTS
