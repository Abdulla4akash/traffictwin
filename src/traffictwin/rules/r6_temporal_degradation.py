"""R6 sustained temporal degradation and post-event recovery candidate rule."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from statistics import fmean

from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import (
    TemporalEvidence,
    TemporalEvidenceStatus,
    TemporalMetricPoint,
    TemporalPointEligibility,
)
from traffictwin.rules.base import DiagnosticRule
from traffictwin.rules.config import R6Config, RuleSetConfig
from traffictwin.rules.models import (
    ConfidenceCategory,
    Finding,
    FindingSupport,
    Recommendation,
    RuleResult,
    RuleStatus,
    result_from_findings,
)


class RecoveryAssessment(StrEnum):
    """Deterministic post-event recovery classification."""

    NOT_APPLICABLE_NO_EVENT = "not_applicable_no_event"
    NOT_ASSESSED_NO_DEGRADATION = "not_assessed_no_degradation"
    RECOVERED = "recovered"
    RECOVERED_AFTER_GAP = "recovered_after_gap"
    NOT_RECOVERED_WITHIN_HORIZON = "not_recovered_within_horizon"
    INDETERMINATE_MISSING_INTERVALS = "indeterminate_missing_intervals"
    HORIZON_INCOMPLETE = "horizon_incomplete"


class R6TemporalDegradationRule(DiagnosticRule):
    """Identify sustained adverse movement without treating temporal gaps as observations."""

    rule_id = "R6"
    rule_version = "1.0"
    title = "Temporal degradation and recovery candidate"

    def evaluate(
        self,
        evidence_pack: EvidencePack,
        config: RuleSetConfig,
        evaluated_at: datetime,
    ) -> RuleResult:
        """Evaluate R6 over the typed temporal section of one EvidencePack."""

        evidence = evidence_pack.temporal_evidence
        if evidence is None:
            return _insufficient(
                self,
                evidence_pack,
                evaluated_at,
                ["temporal_evidence"],
                "No fixed-window temporal evidence is attached to this EvidencePack.",
            )
        if evidence.status is not TemporalEvidenceStatus.AVAILABLE:
            reasons = [reason.value for reason in evidence.reason_codes]
            return _insufficient(
                self,
                evidence_pack,
                evaluated_at,
                reasons or ["available temporal evidence"],
                "The attached temporal evidence is unavailable or invalid.",
                evidence=evidence,
            )
        cfg = config.r6
        if evidence.higher_is_better is None or evidence.unit is None:
            return _insufficient(
                self,
                evidence_pack,
                evaluated_at,
                ["declared temporal metric direction and unit"],
                "The temporal metric has no compatible objective direction or unit.",
                evidence=evidence,
            )
        eligible = [point for point in evidence.points if _eligible(point)]
        if len(eligible) < cfg.minimum_evaluable_windows:
            return _insufficient(
                self,
                evidence_pack,
                evaluated_at,
                [
                    f"at least {cfg.minimum_evaluable_windows} eligible windows; "
                    f"observed {len(eligible)}"
                ],
                "Too few window observations satisfy the temporal evidence contract.",
                evidence=evidence,
            )

        baseline, observation, horizon_complete = _analysis_regions(evidence, cfg)
        if len(baseline) != cfg.baseline_window_count or not all(_eligible(p) for p in baseline):
            missing_ordinals = [point.ordinal for point in baseline if not _eligible(point)]
            if len(baseline) < cfg.baseline_window_count:
                missing_ordinals.extend(
                    range(
                        max((point.ordinal for point in baseline), default=-1) + 1,
                        cfg.baseline_window_count,
                    )
                )
            return _insufficient(
                self,
                evidence_pack,
                evaluated_at,
                [f"complete consecutive baseline windows: {_join(missing_ordinals)}"],
                "The exact declared baseline contains missing or inadmissible windows.",
                evidence=evidence,
            )
        if len(observation) < cfg.sustained_window_count:
            return _insufficient(
                self,
                evidence_pack,
                evaluated_at,
                [f"at least {cfg.sustained_window_count} post-baseline window positions"],
                "The observation region is shorter than the sustained-window requirement.",
                evidence=evidence,
            )

        baseline_mean = round(fmean(_value(point) for point in baseline), 12)
        adverse = {
            point.ordinal: _adverse_delta(point, baseline_mean, evidence.higher_is_better)
            for point in observation
            if _eligible(point)
        }
        episode = _first_sustained_episode(observation, adverse, cfg)
        ineligible_observation = [point for point in observation if not _eligible(point)]
        findings = _base_findings(evidence, cfg, baseline, baseline_mean, observation)

        if episode is None:
            findings.append(
                Finding(
                    finding_id="R6-F3",
                    statement="No sustained eligible adverse episode met the configured threshold.",
                    evidence_keys=[evidence.metric_key],
                    observed_values={
                        "maximum_observed_adverse_delta": max(adverse.values(), default=None),
                        "required_delta": cfg.minimum_deterioration_delta,
                        "required_consecutive_windows": cfg.sustained_window_count,
                    },
                    expected_condition=(
                        f"adverse delta >= {cfg.minimum_deterioration_delta} {evidence.unit} for "
                        f"{cfg.sustained_window_count} consecutive eligible windows"
                    ),
                    support=FindingSupport.CONTRADICTS,
                )
            )
            missing_or_truncated = bool(ineligible_observation) or (
                evidence.event is not None and not horizon_complete
            )
            if missing_or_truncated:
                return result_from_findings(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    title=self.title,
                    status=RuleStatus.INSUFFICIENT_EVIDENCE,
                    synthetic=evidence_pack.synthetic,
                    evaluated_at=evaluated_at,
                    findings=findings,
                    missing_evidence=_missing_observation_evidence(
                        ineligible_observation,
                        horizon_complete,
                        evidence.event is not None,
                    ),
                    confidence=ConfidenceCategory.UNAVAILABLE,
                    confidence_basis=[
                        "gaps or a truncated event horizon prevent a supported non-trigger"
                    ],
                    limitations=_limitations(),
                    metadata=_metadata(
                        evidence,
                        cfg,
                        baseline,
                        baseline_mean,
                        observation,
                        ineligible_observation,
                        None,
                        RecoveryAssessment.NOT_ASSESSED_NO_DEGRADATION,
                        None,
                        horizon_complete,
                    ),
                )
            return result_from_findings(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                title=self.title,
                status=RuleStatus.NOT_TRIGGERED,
                synthetic=evidence_pack.synthetic,
                evaluated_at=evaluated_at,
                findings=findings,
                confidence=ConfidenceCategory.UNAVAILABLE,
                confidence_basis=["complete evaluated windows did not meet the R6 trigger"],
                limitations=_limitations(),
                metadata=_metadata(
                    evidence,
                    cfg,
                    baseline,
                    baseline_mean,
                    observation,
                    ineligible_observation,
                    None,
                    RecoveryAssessment.NOT_ASSESSED_NO_DEGRADATION,
                    None,
                    horizon_complete,
                ),
            )

        peak_delta = max(adverse[point.ordinal] for point in episode)
        findings.append(
            Finding(
                finding_id="R6-F3",
                statement="A sustained eligible adverse episode met the configured threshold.",
                evidence_keys=[evidence.metric_key],
                observed_values={
                    "episode_start_ordinal": episode[0].ordinal,
                    "episode_end_ordinal": episode[-1].ordinal,
                    "episode_window_count": len(episode),
                    "peak_adverse_delta": peak_delta,
                },
                expected_condition=(
                    f"adverse delta >= {cfg.minimum_deterioration_delta} {evidence.unit} for "
                    f"{cfg.sustained_window_count} consecutive eligible windows"
                ),
                support=FindingSupport.SUPPORTS,
            )
        )
        recovery, recovery_point = _recovery_assessment(
            evidence,
            observation,
            episode,
            adverse,
            cfg,
            horizon_complete,
        )
        findings.append(_recovery_finding(evidence, cfg, recovery, recovery_point))
        confidence = (
            ConfidenceCategory.LOW
            if ineligible_observation or recovery is RecoveryAssessment.RECOVERED_AFTER_GAP
            else (
                ConfidenceCategory.HIGH
                if evidence.event is not None and horizon_complete
                else ConfidenceCategory.MODERATE
            )
        )
        return result_from_findings(
            rule_id=self.rule_id,
            rule_version=self.rule_version,
            title=self.title,
            status=RuleStatus.TRIGGERED,
            synthetic=evidence_pack.synthetic,
            evaluated_at=evaluated_at,
            hypothesis=(
                f"{evidence.metric_key} exhibits a sustained adverse within-run episode; "
                f"post-event recovery is classified as {recovery.value}."
            ),
            findings=findings,
            missing_evidence=_missing_observation_evidence(
                ineligible_observation,
                horizon_complete,
                evidence.event is not None,
            ),
            alternative_explanations=[
                "ordinary workload variation within the run",
                "window-boundary or cohort effects",
                "measurement gaps or changing observation support",
                "an unrecorded scenario or policy-state change",
                "a declared event may be temporally associated without causing the change",
            ],
            recommendations=[
                Recommendation(
                    action="inspect the reported windows and repeat the run under matched seeds",
                    rationale="window lineage and replication can test whether the pattern repeats",
                    expected_direction="episode stability and evidence gaps become measurable",
                    prerequisite=(
                        "compatible window contract, metric definition, and source evidence"
                    ),
                    verification_step=(
                        "trace each reported ordinal with window-metric provenance and rerun R6"
                    ),
                )
            ],
            confidence=confidence,
            confidence_basis=[
                "confidence reflects exact baseline, consecutive eligible windows, event-horizon "
                "completeness, and visible gaps; it is not a probability"
            ],
            limitations=_limitations(),
            metadata=_metadata(
                evidence,
                cfg,
                baseline,
                baseline_mean,
                observation,
                ineligible_observation,
                episode,
                recovery,
                recovery_point,
                horizon_complete,
            ),
        )


def _analysis_regions(
    evidence: TemporalEvidence,
    cfg: R6Config,
) -> tuple[list[TemporalMetricPoint], list[TemporalMetricPoint], bool]:
    points = evidence.points
    if evidence.event is None:
        return points[: cfg.baseline_window_count], points[cfg.baseline_window_count :], True
    event_index = next(
        index
        for index, point in enumerate(points)
        if point.ordinal == evidence.event.event_window_ordinal
    )
    baseline = points[max(0, event_index - cfg.baseline_window_count) : event_index]
    horizon_end = event_index + cfg.recovery_horizon_windows
    observation = points[event_index:horizon_end]
    return baseline, observation, len(observation) == cfg.recovery_horizon_windows


def _base_findings(
    evidence: TemporalEvidence,
    cfg: R6Config,
    baseline: list[TemporalMetricPoint],
    baseline_mean: float,
    observation: list[TemporalMetricPoint],
) -> list[Finding]:
    eligible_observation_count = sum(_eligible(point) for point in observation)
    return [
        Finding(
            finding_id="R6-F1",
            statement="The exact consecutive baseline windows provide the declared reference.",
            evidence_keys=[evidence.metric_key],
            observed_values={
                "baseline_mean": baseline_mean,
                "baseline_window_count": len(baseline),
                "baseline_ordinals": _join([point.ordinal for point in baseline]),
            },
            expected_condition=f"{cfg.baseline_window_count} consecutive eligible baseline windows",
            support=FindingSupport.SUPPORTS,
        ),
        Finding(
            finding_id="R6-F2",
            statement="Observation-window admission is reported independently from metric values.",
            evidence_keys=[evidence.metric_key],
            observed_values={
                "observation_window_count": len(observation),
                "eligible_observation_window_count": eligible_observation_count,
                "ineligible_observation_window_count": (
                    len(observation) - eligible_observation_count
                ),
                "minimum_window_coverage": evidence.config.minimum_window_coverage,
            },
            expected_condition="missing or low-coverage windows never support deterioration",
            support=FindingSupport.NEUTRAL,
        ),
    ]


def _first_sustained_episode(
    observation: list[TemporalMetricPoint],
    adverse: dict[int, float],
    cfg: R6Config,
) -> list[TemporalMetricPoint] | None:
    runs: list[list[TemporalMetricPoint]] = []
    current: list[TemporalMetricPoint] = []
    for point in observation:
        qualifies = (
            _eligible(point)
            and adverse[point.ordinal] >= cfg.minimum_deterioration_delta
            and (not current or point.ordinal == current[-1].ordinal + 1)
        )
        if qualifies:
            current.append(point)
            continue
        if current:
            runs.append(current)
        current = []
        if _eligible(point) and adverse[point.ordinal] >= cfg.minimum_deterioration_delta:
            current = [point]
    if current:
        runs.append(current)
    return next((run for run in runs if len(run) >= cfg.sustained_window_count), None)


def _recovery_assessment(
    evidence: TemporalEvidence,
    observation: list[TemporalMetricPoint],
    episode: list[TemporalMetricPoint],
    adverse: dict[int, float],
    cfg: R6Config,
    horizon_complete: bool,
) -> tuple[RecoveryAssessment, TemporalMetricPoint | None]:
    if evidence.event is None:
        return RecoveryAssessment.NOT_APPLICABLE_NO_EVENT, None
    following = [point for point in observation if point.ordinal > episode[-1].ordinal]
    gap_seen = False
    for point in following:
        if not _eligible(point):
            gap_seen = True
            continue
        if adverse[point.ordinal] <= cfg.recovery_tolerance:
            return (
                RecoveryAssessment.RECOVERED_AFTER_GAP
                if gap_seen
                else RecoveryAssessment.RECOVERED,
                point,
            )
    if any(not _eligible(point) for point in following):
        return RecoveryAssessment.INDETERMINATE_MISSING_INTERVALS, None
    if not horizon_complete:
        return RecoveryAssessment.HORIZON_INCOMPLETE, None
    return RecoveryAssessment.NOT_RECOVERED_WITHIN_HORIZON, None


def _recovery_finding(
    evidence: TemporalEvidence,
    cfg: R6Config,
    assessment: RecoveryAssessment,
    point: TemporalMetricPoint | None,
) -> Finding:
    return Finding(
        finding_id="R6-F4",
        statement="Post-event recovery is classified within the declared fixed-window horizon.",
        evidence_keys=[evidence.metric_key],
        observed_values={
            "recovery_assessment": assessment.value,
            "recovery_window_ordinal": point.ordinal if point is not None else None,
            "event_window_ordinal": (
                evidence.event.event_window_ordinal if evidence.event is not None else None
            ),
        },
        expected_condition=(
            f"adverse delta <= {cfg.recovery_tolerance} {evidence.unit} within "
            f"{cfg.recovery_horizon_windows} event-horizon windows"
        ),
        support=FindingSupport.NEUTRAL,
    )


def _metadata(
    evidence: TemporalEvidence,
    cfg: R6Config,
    baseline: list[TemporalMetricPoint],
    baseline_mean: float,
    observation: list[TemporalMetricPoint],
    missing: list[TemporalMetricPoint],
    episode: list[TemporalMetricPoint] | None,
    recovery: RecoveryAssessment,
    recovery_point: TemporalMetricPoint | None,
    horizon_complete: bool,
) -> dict[str, str | int | float | bool | None]:
    return {
        "temporal_evidence_fingerprint": evidence.fingerprint(),
        "window_series_fingerprint": evidence.series_fingerprint,
        "metric_key": evidence.metric_key,
        "metric_unit": evidence.unit,
        "higher_is_better": evidence.higher_is_better,
        "baseline_mean": baseline_mean,
        "baseline_ordinals": _join([point.ordinal for point in baseline]),
        "observation_ordinals": _join([point.ordinal for point in observation]),
        "missing_observation_ordinals": _join([point.ordinal for point in missing]),
        "episode_start_ordinal": episode[0].ordinal if episode else None,
        "episode_end_ordinal": episode[-1].ordinal if episode else None,
        "peak_adverse_delta": (
            max(
                _adverse_delta(point, baseline_mean, bool(evidence.higher_is_better))
                for point in episode
            )
            if episode
            else None
        ),
        "event_window_ordinal": (
            evidence.event.event_window_ordinal if evidence.event is not None else None
        ),
        "recovery_assessment": recovery.value,
        "recovery_window_ordinal": recovery_point.ordinal if recovery_point is not None else None,
        "event_horizon_complete": horizon_complete,
        "minimum_deterioration_delta": cfg.minimum_deterioration_delta,
        "sustained_window_count": cfg.sustained_window_count,
        "recovery_tolerance": cfg.recovery_tolerance,
        "recovery_horizon_windows": cfg.recovery_horizon_windows,
    }


def _insufficient(
    rule: R6TemporalDegradationRule,
    evidence_pack: EvidencePack,
    evaluated_at: datetime,
    missing: list[str],
    statement: str,
    *,
    evidence: TemporalEvidence | None = None,
) -> RuleResult:
    return result_from_findings(
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        title=rule.title,
        status=RuleStatus.INSUFFICIENT_EVIDENCE,
        synthetic=evidence_pack.synthetic,
        evaluated_at=evaluated_at,
        findings=[
            Finding(
                finding_id="R6-INSUFFICIENT",
                statement=statement,
                evidence_keys=(
                    [evidence.metric_key]
                    if evidence is not None
                    and evidence.metric_key in evidence_pack.metric_collection.by_key()
                    else []
                ),
                observed_values={
                    "temporal_status": evidence.status.value if evidence is not None else None,
                    "eligible_window_count": (
                        evidence.eligible_window_count if evidence is not None else 0
                    ),
                },
                expected_condition="complete compatible temporal evidence satisfying R6 minima",
                support=FindingSupport.NEUTRAL,
            )
        ],
        missing_evidence=missing,
        recommendations=[
            Recommendation(
                action="build compatible fixed-window temporal evidence before interpreting R6",
                rationale="R6 cannot substitute missing intervals or infer event context",
                expected_direction="R6 evidence readiness should increase",
                prerequisite=(
                    "window-applicable scalar metric with direction and sufficient coverage"
                ),
                verification_step=(
                    "attach temporal evidence to the EvidencePack and rerun diagnostics"
                ),
            )
        ],
        confidence=ConfidenceCategory.UNAVAILABLE,
        confidence_basis=["required temporal evidence for R6 is incomplete or incompatible"],
        limitations=_limitations(),
        metadata=(
            {
                "temporal_evidence_fingerprint": evidence.fingerprint(),
                "window_series_fingerprint": evidence.series_fingerprint,
                "metric_key": evidence.metric_key,
            }
            if evidence is not None
            else {}
        ),
    )


def _missing_observation_evidence(
    missing: list[TemporalMetricPoint],
    horizon_complete: bool,
    has_event: bool,
) -> list[str]:
    result = (
        [f"eligible temporal values for window ordinals: {_join([p.ordinal for p in missing])}"]
        if missing
        else []
    )
    if has_event and not horizon_complete:
        result.append("complete declared post-event recovery horizon")
    if not has_event:
        result.append("researcher-declared event context for recovery assessment")
    return result


def _limitations() -> list[str]:
    return [
        "R6 is a deterministic descriptive candidate, not causal incident attribution.",
        "Default thresholds are provisional synthetic-development values.",
        "Requested-range coverage is not proof of sensor completeness.",
        "Cohort-window and boundary effects can change adjacent window values.",
    ]


def _adverse_delta(point: TemporalMetricPoint, baseline: float, higher_is_better: bool) -> float:
    value = _value(point)
    return round(baseline - value if higher_is_better else value - baseline, 12)


def _eligible(point: TemporalMetricPoint) -> bool:
    return point.eligibility is TemporalPointEligibility.ELIGIBLE and point.value is not None


def _value(point: TemporalMetricPoint) -> float:
    if point.value is None:
        raise ValueError("eligible temporal point must have a numeric value")
    return point.value


def _join(values: list[int]) -> str:
    return ",".join(str(value) for value in values)
