"""Deterministic metric computation and rule-readiness admission for VEC-09."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import numpy as np

from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.integration.vec_identity import VecIdentitySnapshot
from traffictwin.integration.vec_science.models import (
    VecMetricAdmissionDecision,
    VecMetricAdmissionStatus,
    VecRuleReadiness,
    VecRuleReadinessStatus,
    VecScientificAdmissionReport,
    vec_scientific_admission_contract,
)
from traffictwin.integration.vec_task_join import VecTaskJoinReport, build_task_join_report
from traffictwin.integration.vec_trip_join import VecTripJoinReport
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    MetricCollection,
    MetricStatus,
    MetricValue,
    UnavailableReason,
)

METRIC_VERSION = "vec-scientific-admission-1.0"


class VecScientificAdmissionError(ValueError):
    """Raised when consumed evidence is not accepted or does not reconcile."""


def _metric(
    key: str,
    value: int | float | dict[str, float],
    unit: str,
    scope: str,
    report: VecTaskJoinReport,
    computed_at: datetime,
    *,
    metadata: dict[str, Any] | None = None,
) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        scope=scope,
        required_evidence=["VEC-03 identity", "VEC-04 reconciled task evidence"],
        warnings=[
            "Audited VEC source evidence; deadline success is not physical completion.",
            "No threshold was calibrated or evaluated by VEC-09.",
        ],
        implementation_version=METRIC_VERSION,
        run_id=report.run_label,
        experiment_id=None,
        seed_id=report.run_label,
        algorithm="audited-vec-source",
        checkpoint=None,
        random_seed=0,
        synthetic=False,
        environment="randy-vec",
        environment_version="v2_post_nrsus_fix",
        environment_commit=report.source_commit,
        computed_at=computed_at,
        metadata=metadata or {},
    )


def _unavailable(
    key: str,
    unit: str,
    blocker: str,
    report: VecTaskJoinReport,
    computed_at: datetime,
) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.UNAVAILABLE,
        unit=unit,
        scope="run",
        missing_evidence=[blocker],
        reason_codes=[UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
        warnings=["VEC-09 refuses to infer or relabel the missing evidence."],
        implementation_version=METRIC_VERSION,
        run_id=report.run_label,
        experiment_id=None,
        seed_id=report.run_label,
        algorithm="audited-vec-source",
        random_seed=0,
        synthetic=False,
        environment="randy-vec",
        environment_version="v2_post_nrsus_fix",
        environment_commit=report.source_commit,
        computed_at=computed_at,
    )


def build_vec_scientific_admission(
    trace_arrays: Mapping[str, Any],
    perstep_arrays: Mapping[str, Any],
    pertask_arrays: Mapping[str, Any],
    identity: VecIdentitySnapshot,
    task_report: VecTaskJoinReport,
    *,
    reproduction_report_fingerprint: str,
    reproduction_grade: str,
    computed_at: datetime,
    trip_report: VecTripJoinReport | None = None,
) -> VecScientificAdmissionReport:
    """Compute admitted metrics and publish rule readiness without evaluating thresholds."""

    if reproduction_grade != "numerically_equivalent":
        raise VecScientificAdmissionError("VEC-08 numerical equivalence is required")
    if len(reproduction_report_fingerprint) != 64:
        raise VecScientificAdmissionError("a VEC-08 report fingerprint is required")
    rebuilt = build_task_join_report(
        trace_arrays,
        perstep_arrays,
        pertask_arrays,
        identity,
        run_label=task_report.run_label,
    )
    if rebuilt.fingerprint() != task_report.fingerprint():
        raise VecScientificAdmissionError("VEC-04 evidence does not match its accepted report")
    if trip_report is not None:
        if trip_report.scenario != task_report.scenario:
            raise VecScientificAdmissionError("trip and task evidence scenarios do not match")
        if trip_report.identity_snapshot_fingerprint != task_report.identity_snapshot_fingerprint:
            raise VecScientificAdmissionError(
                "trip and task evidence identity snapshots do not match"
            )
        if trip_report.source_commit != task_report.source_commit:
            raise VecScientificAdmissionError("trip and task evidence source commits do not match")

    active = np.asarray(pertask_arrays["task_active"], dtype=bool)
    met = np.asarray(pertask_arrays["task_met"], dtype=bool)
    task_type = np.asarray(pertask_arrays["task_type"])
    latency = np.asarray(pertask_arrays["task_lat_ms"])
    action = np.broadcast_to(np.asarray(perstep_arrays["veh_action"])[:, None, :], active.shape)
    tier = np.broadcast_to(np.asarray(perstep_arrays["slot_tier"])[None, None, :], active.shape)
    best_rsu = np.broadcast_to(np.asarray(perstep_arrays["veh_best_rsu"])[:, None, :], active.shape)
    best_v2v = np.broadcast_to(np.asarray(perstep_arrays["veh_best_v2v"])[:, None, :], active.shape)
    total = int(active.sum())
    if total <= 0:
        raise VecScientificAdmissionError("at least one reconciled task is required")
    deadline_met = int((active & met).sum())
    action_counts = {code: int((active & (action == code)).sum()) for code in (0, 1, 2)}
    class_rates: dict[str, float] = {}
    class_support: dict[str, int] = {}
    for code, label in enumerate(("T1", "T2", "T3")):
        cohort = active & (task_type == code)
        count = int(cohort.sum())
        if count:
            class_rates[label] = float((cohort & met).sum()) / count
            class_support[label] = count
    tier_rates: dict[str, float] = {}
    tier_support: dict[str, int] = {}
    for code in (0, 1, 2):
        cohort = active & (tier == code)
        count = int(cohort.sum())
        if count:
            tier_rates[str(code)] = float((cohort & met).sum()) / count
            tier_support[str(code)] = count
    offload = active & ((action == 1) | (action == 2))
    offload_count = int(offload.sum())
    no_target = active & (((action == 1) & (best_rsu < 0)) | ((action == 2) & (best_v2v < 0)))
    no_target_count = int(no_target.sum())

    results = [
        _metric("task.generated.count", total, "count", "run", task_report, computed_at),
        _metric(
            "task.latency.mean_ms",
            float(latency[active].mean(dtype=np.float64)),
            "ms",
            "run",
            task_report,
            computed_at,
        ),
        *[
            _metric(
                f"task.decision_share.{label}",
                action_counts[code] / total,
                "ratio",
                "run",
                task_report,
                computed_at,
            )
            for code, label in ((0, "local"), (1, "v2i"), (2, "v2v"))
        ],
        _metric("task.decision_share.unknown", 0.0, "ratio", "run", task_report, computed_at),
        _metric(
            "task.offload.rate",
            (action_counts[1] + action_counts[2]) / total,
            "ratio",
            "run",
            task_report,
            computed_at,
        ),
        _metric(
            "tos.task.deadline_success.rate",
            deadline_met / total,
            "ratio",
            "run",
            task_report,
            computed_at,
            metadata={"outcome_semantics": "deadline_met_per_arrival"},
        ),
        _metric(
            "tos.task.deadline_success.rate_by_class",
            class_rates,
            "ratio",
            "task_class",
            task_report,
            computed_at,
            metadata={
                "task_type_codes": "0=T1,1=T2,2=T3",
                "group_support_counts": class_support,
                "unsupported_groups_omitted": True,
            },
        ),
        _metric(
            "tos.task.deadline_success.rate_by_slot_tier",
            tier_rates,
            "ratio",
            "slot_tier",
            task_report,
            computed_at,
            metadata={
                "group_support_counts": tier_support,
                "attribute_interpretation": "operational_slot_assignment_not_protected_attribute",
            },
        ),
        _metric(
            "tos.operational.slot_tier.deadline_success.max_gap",
            max(tier_rates.values()) - min(tier_rates.values()),
            "ratio",
            "run",
            task_report,
            computed_at,
            metadata={"group_support_counts": tier_support, "group_count": 3},
        ),
        _metric(
            "tos.task.no_eligible_target.rate_among_offload",
            no_target_count / offload_count if offload_count else 0.0,
            "ratio",
            "run",
            task_report,
            computed_at,
            metadata={
                "no_eligible_target_count": no_target_count,
                "offload_task_count": offload_count,
                "failure_inferred": False,
            },
        ),
    ]
    if trip_report is not None:
        summary = trip_report.duration_summary
        for key, value, unit in (
            ("trip.duration.count", summary.eligible_count, "count"),
            ("trip.duration.mean_s", summary.mean_s, "s"),
            ("trip.duration.p50_s", summary.p50_s, "s"),
            ("trip.duration.p95_s", summary.p95_s, "s"),
            ("trip.duration.min_s", summary.min_s, "s"),
            ("trip.duration.max_s", summary.max_s, "s"),
        ):
            results.append(
                _metric(
                    key,
                    value,
                    unit,
                    "run",
                    task_report,
                    computed_at,
                    metadata={"cohort": summary.cohort_semantics},
                )
            )
    unavailable = {
        "task.completed.count": ("count", "physical completion evidence is absent"),
        "task.completion.rate": ("ratio", "physical completion evidence is absent"),
        "task.energy.per_completed_j": ("J/task", "per-task energy evidence is absent"),
        "infra.utilisation.mean": ("ratio", "canonical CPU utilisation evidence is absent"),
        "infra.queue.mean_tasks": ("tasks", "canonical queue-length evidence is absent"),
        "fairness.vehicle_tier.completion_rate.max_gap": (
            "ratio",
            "slot-tier deadline success is not stable-vehicle physical completion",
        ),
        "spatial.rsu.task.completion_rate_by_target": (
            "ratio",
            "eligible targets are not confirmed execution targets",
        ),
        "trip.completion.rate": (
            "ratio",
            "the exact matched duration cohort excludes censored occupancy vehicles",
        ),
    }
    for key, (unit, blocker) in unavailable.items():
        results.append(_unavailable(key, unit, blocker, task_report, computed_at))
    results.sort(key=lambda item: item.metric_key)
    collection = MetricCollection(
        run_id=task_report.run_label,
        metric_version=METRIC_VERSION,
        results=results,
        unavailable_count=sum(item.status is MetricStatus.UNAVAILABLE for item in results),
        partial_count=0,
        generated_at=computed_at,
        input_fingerprint=task_report.fingerprint(),
    )
    evidence_pack = EvidencePack(
        pack_id=f"vec-science-{task_report.fingerprint()[:12]}",
        generated_at=computed_at,
        synthetic=False,
        run_context={
            "run_id": task_report.run_label,
            "environment": "randy-vec",
            "environment_version": "v2_post_nrsus_fix",
        },
        source_bundle_fingerprint=task_report.fingerprint(),
        validation_summary={"status": "accepted", "may_import": False, "finding_count": 0},
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.AVAILABLE,
            vehicles=EvidenceStatus.AVAILABLE,
            trips=EvidenceStatus.AVAILABLE if trip_report else EvidenceStatus.UNAVAILABLE,
            infrastructure=EvidenceStatus.PARTIAL,
            traffic=EvidenceStatus.PARTIAL,
            diagnosis=EvidenceStatus.PARTIAL,
        ),
        metric_engine_config=MetricEngineConfig(metric_version=METRIC_VERSION),
        metric_collection=collection,
        excluded_record_counts=(
            {
                "trip_right_censored": trip_report.right_censored_count,
                "trip_missing_before_boundary": trip_report.missing_before_boundary_count,
            }
            if trip_report
            else {}
        ),
        warnings=[
            "VEC evidence remains source-specific; no canonical task completion is claimed.",
            "Diagnostic thresholds were not evaluated or calibrated by this admission step.",
        ],
        provenance={
            "task_join_report_fingerprint": task_report.fingerprint(),
            "reproduction_report_fingerprint": reproduction_report_fingerprint,
        },
    )
    decisions = _metric_decisions(results)
    readiness = _rule_readiness(collection)
    return VecScientificAdmissionReport(
        run_label=task_report.run_label,
        scenario=task_report.scenario,
        task_join_report_fingerprint=task_report.fingerprint(),
        trip_join_report_fingerprint=trip_report.fingerprint() if trip_report else None,
        reproduction_report_fingerprint=reproduction_report_fingerprint,
        metric_decisions=decisions,
        rule_readiness=readiness,
        evidence_pack=evidence_pack,
    )


def _metric_decisions(results: list[MetricValue]) -> tuple[VecMetricAdmissionDecision, ...]:
    contract = vec_scientific_admission_contract()
    existing = set(contract.admitted_existing_metrics)
    source_specific = set(contract.admitted_source_specific_metrics)
    decisions = []
    for result in results:
        if result.status is MetricStatus.UNAVAILABLE:
            status = VecMetricAdmissionStatus.UNAVAILABLE
            blocker = result.missing_evidence[0]
        elif result.metric_key in existing:
            status = VecMetricAdmissionStatus.ADMITTED_EXISTING
            blocker = None
        elif result.metric_key in source_specific:
            status = VecMetricAdmissionStatus.ADMITTED_SOURCE_SPECIFIC
            blocker = None
        else:
            raise VecScientificAdmissionError(f"metric {result.metric_key} is not in the contract")
        decisions.append(
            VecMetricAdmissionDecision(
                metric_key=result.metric_key,
                status=status,
                evidence=tuple(result.required_evidence or result.missing_evidence),
                semantics=result.warnings[0],
                blocker=blocker,
            )
        )
    return tuple(sorted(decisions, key=lambda item: item.metric_key))


def _rule_readiness(collection: MetricCollection) -> tuple[VecRuleReadiness, ...]:
    available = {
        item.metric_key for item in collection.results if item.status is MetricStatus.AVAILABLE
    }
    return (
        VecRuleReadiness(
            rule_id="R1",
            status=VecRuleReadinessStatus.BLOCKED,
            admitted_evidence=tuple(
                sorted(available & {"task.generated.count", "task.offload.rate"})
            ),
            missing_evidence=("physical T1 completion", "canonical infra.utilisation.mean"),
            rationale=(
                "Deadline success and no-target evidence cannot satisfy R1's "
                "completion/utilisation contract."
            ),
        ),
        VecRuleReadiness(
            rule_id="R2",
            status=VecRuleReadinessStatus.BLOCKED,
            admitted_evidence=(),
            missing_evidence=(
                "canonical utilisation",
                "canonical queue trend",
                "confirmed execution targets",
            ),
            rationale=(
                "RSU load/backlog and eligible targets do not satisfy the R2 "
                "infrastructure contract."
            ),
        ),
        VecRuleReadiness(
            rule_id="R6",
            status=VecRuleReadinessStatus.CONDITIONAL,
            admitted_evidence=("tos.task.deadline_success.rate", "task.latency.mean_ms"),
            missing_evidence=(
                "predeclared window design",
                "predeclared threshold",
                "development/held-out label",
            ),
            rationale=(
                "Temporal source evidence is constructible, but evaluation would require "
                "a separate predeclared design."
            ),
        ),
        VecRuleReadiness(
            rule_id="R7",
            status=VecRuleReadinessStatus.BLOCKED,
            admitted_evidence=("tos.operational.slot_tier.deadline_success.max_gap",),
            missing_evidence=(
                "stable vehicle-tier physical completion under the R7 fairness policy",
            ),
            rationale=(
                "Operational slot-tier deadline success must not be relabelled as R7 "
                "completion fairness."
            ),
        ),
    )
