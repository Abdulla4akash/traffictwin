"""Explicitly labelled source-summary metrics for TOS evaluation rows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.integration.tos.models import (
    TOS_SOURCE_METRIC_VERSION,
    TosEvaluationRun,
    TosValidationReport,
)
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.definitions import AggregationScope, MetricDefinition, MetricDomain
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    JsonValue,
    MetricCollection,
    MetricStatus,
    MetricValue,
    UnavailableReason,
)

TOS_METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "tos.task.deadline_success.rate": MetricDefinition(
        key="tos.task.deadline_success.rate",
        human_name="TOS deadline-success rate",
        description="Source-reported fraction of task arrivals meeting their deadline.",
        domain=MetricDomain.TASK,
        unit="ratio",
        aggregation_scope=AggregationScope.RUN,
        required_fields={"tos_evaluation_summary": ["completion"]},
        implementation_version=TOS_SOURCE_METRIC_VERSION,
        higher_is_better=True,
        limitations=[
            "This source metric is not TrafficTwin task.completion.rate.",
            "It does not establish eventual physical task completion.",
        ],
    ),
    "tos.task.deadline_success.rate_by_class": MetricDefinition(
        key="tos.task.deadline_success.rate_by_class",
        human_name="TOS deadline-success rate by task class",
        description="Source-reported deadline-success fraction grouped by T1, T2, and T3.",
        domain=MetricDomain.TASK,
        unit="ratio",
        aggregation_scope=AggregationScope.TASK_CLASS,
        required_fields={
            "tos_evaluation_summary": ["t1_completion", "t2_completion", "t3_completion"]
        },
        implementation_version=TOS_SOURCE_METRIC_VERSION,
        higher_is_better=True,
        limitations=[
            "This source metric is not TrafficTwin task.completion.rate_by_class.",
            "It does not establish eventual physical task completion.",
        ],
    ),
}


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def metric_collection_from_evaluation(
    run: TosEvaluationRun,
    package_fingerprint: str,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> MetricCollection:
    """Translate documented source summaries into labelled metric results.

    Values remain source-provided summaries. This function does not claim to
    recompute them from canonical TrafficTwin records.
    """

    computed_at = clock()
    source_values: dict[str, JsonValue] = {
        "tos.task.deadline_success.rate": run.completion,
        "tos.task.deadline_success.rate_by_class": {
            "T1": run.t1_completion,
            "T2": run.t2_completion,
            "T3": run.t3_completion,
        },
    }
    compatible_values: dict[str, JsonValue] = {
        "task.latency.mean_ms": run.avg_latency_ms_per_task,
        "task.decision_share.local": run.p_local,
        "task.decision_share.v2i": run.p_v2i,
        "task.decision_share.v2v": run.p_v2v,
        "task.decision_share.unknown": 0.0,
        "task.offload.rate": run.p_v2i + run.p_v2v,
    }
    results: list[MetricValue] = []
    for key, definition in TOS_METRIC_DEFINITIONS.items():
        results.append(
            _available_metric(
                run,
                definition,
                source_values[key],
                computed_at,
            )
        )
    for key, definition in metric_catalogue().items():
        if key in compatible_values:
            results.append(_available_metric(run, definition, compatible_values[key], computed_at))
            continue
        reason = _unavailable_reason(key)
        metadata = _source_metadata(run)
        if key == "task.energy.per_completed_j":
            metadata["source_energy_j_per_arrival"] = run.avg_energy_j_per_task
        results.append(
            MetricValue(
                metric_key=key,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=definition.unit,
                scope=definition.aggregation_scope.value,
                required_evidence=[
                    f"{table}.{field}"
                    for table, fields in definition.required_fields.items()
                    for field in fields
                ]
                or list(definition.required_tables),
                missing_evidence=_missing_evidence(key),
                reason_codes=[reason],
                warnings=[_unavailable_warning(key)],
                implementation_version=TOS_SOURCE_METRIC_VERSION,
                run_id=run.run_id,
                experiment_id=run.experiment_id,
                seed_id=run.seed_id,
                algorithm=run.campaign,
                checkpoint=run.actor,
                random_seed=run.fleet_seed,
                synthetic=False,
                computed_at=computed_at,
                metadata=metadata,
            )
        )
    results.sort(key=lambda item: item.metric_key)
    return MetricCollection(
        run_id=run.run_id,
        metric_version=TOS_SOURCE_METRIC_VERSION,
        results=results,
        unavailable_count=sum(item.status is MetricStatus.UNAVAILABLE for item in results),
        partial_count=0,
        generated_at=computed_at,
        input_fingerprint=_run_fingerprint(run, package_fingerprint),
    )


def tos_metric_catalogue() -> dict[str, MetricDefinition]:
    """Return source-specific definitions keyed by stable metric identifier."""

    return dict(TOS_METRIC_DEFINITIONS)


def _available_metric(
    run: TosEvaluationRun,
    definition: MetricDefinition,
    value: JsonValue,
    computed_at: datetime,
) -> MetricValue:
    return MetricValue(
        metric_key=definition.key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=definition.unit,
        scope=definition.aggregation_scope.value,
        required_evidence=["tos.evaluation_summary"],
        warnings=[
            "Source-provided evaluation summary; not recomputed from canonical rows.",
            _semantics_warning(definition.key),
        ],
        implementation_version=TOS_SOURCE_METRIC_VERSION,
        run_id=run.run_id,
        experiment_id=run.experiment_id,
        seed_id=run.seed_id,
        algorithm=run.campaign,
        checkpoint=run.actor,
        random_seed=run.fleet_seed,
        synthetic=False,
        computed_at=computed_at,
        metadata=_source_metadata(run),
    )


def build_tos_evidence_pack(
    run: TosEvaluationRun,
    validation_report: TosValidationReport,
    metric_collection: MetricCollection | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> EvidencePack:
    """Build an honest partial EvidencePack from one source-summary row."""

    if validation_report.package_fingerprint is None:
        raise ValueError("TOS package fingerprint is required for an EvidencePack")
    collection = metric_collection or metric_collection_from_evaluation(
        run,
        validation_report.package_fingerprint,
        clock=clock,
    )
    generated_at = clock()
    fingerprint = validation_report.package_fingerprint
    pack_id = f"evidence-{run.run_id.replace(':', '-')}-{fingerprint[:12]}"
    severity_counts = {
        severity: sum(item.severity.value == severity for item in validation_report.findings)
        for severity in ("info", "warning", "error")
    }
    return EvidencePack(
        pack_id=pack_id,
        generated_at=generated_at,
        synthetic=False,
        run_context={
            "run_id": run.run_id,
            "experiment_id": run.experiment_id,
            "seed_id": run.seed_id,
            "algorithm": run.campaign,
            "checkpoint": run.actor,
            "random_seed": run.fleet_seed,
            "environment": "randy-tos-evaluation",
            "environment_version": run.engine_version,
            "environment_commit": None,
        },
        source_bundle_fingerprint=fingerprint,
        validation_summary={
            "status": validation_report.status.value,
            "may_import": validation_report.may_import_summaries,
            "finding_count": len(validation_report.findings),
            "counts_by_severity": severity_counts,
            "validator_version": validation_report.adapter_version,
        },
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.PARTIAL,
            infrastructure=EvidenceStatus.UNAVAILABLE,
            vehicles=EvidenceStatus.UNAVAILABLE,
            traffic=EvidenceStatus.UNAVAILABLE,
            trips=EvidenceStatus.UNAVAILABLE,
            incidents=EvidenceStatus.UNAVAILABLE,
            diagnosis=EvidenceStatus.PARTIAL,
        ),
        metric_engine_config=MetricEngineConfig(metric_version=TOS_SOURCE_METRIC_VERSION),
        metric_collection=collection,
        excluded_record_counts={},
        warnings=[
            "TOS source summaries are partial evidence and are not canonical row-level metrics.",
            "RSU arrays remain unmapped; R1 and R2 infrastructure evidence is unavailable.",
            "No trip evidence is present in the TOS Data package.",
        ],
        provenance={
            "bundle_id": f"tos-data-{fingerprint[:12]}",
            "bundle_source": "external TOS Data package",
            "manifest_version": None,
            "metric_version": collection.metric_version,
        },
    )


def _source_metadata(run: TosEvaluationRun) -> dict[str, str | int | float | bool | None]:
    return {
        "source_kind": "tos_evaluation_summary",
        "source_file": run.source_file,
        "source_row": run.source_row,
        "source_outcome_semantics": "deadline_met_per_arrival",
        "engine_version": run.engine_version,
        "duration_s": run.duration_s,
        "max_vehicle_slots": run.max_vehicle_slots,
        "evaluation_fleet": run.eval_fleet,
        "source_metric": True,
    }


def _semantics_warning(metric_key: str) -> str:
    if metric_key.startswith("tos.task.deadline_success"):
        return "Source completion means the fraction of task arrivals meeting their deadline."
    if metric_key == "task.latency.mean_ms":
        return "Source mean latency includes deadline-missing arrivals carrying queue backlog."
    return "Action values use the package-documented local, V2I, and V2V encoding."


def _unavailable_reason(metric_key: str) -> UnavailableReason:
    if metric_key == "task.completion.rate_by_vehicle_tier":
        return UnavailableReason.VEHICLE_TIER_UNAVAILABLE
    if metric_key.startswith("infra.load_balance"):
        return UnavailableReason.CAPACITY_UNAVAILABLE
    if metric_key.startswith("trip.duration"):
        return UnavailableReason.NO_COMPLETED_TRIPS
    if metric_key.startswith("task.latency"):
        return UnavailableReason.NO_LATENCY_VALUES
    if metric_key.startswith("comparison."):
        return UnavailableReason.METRIC_NOT_APPLICABLE
    if metric_key.startswith(("infra.", "traffic.", "trip.")):
        return UnavailableReason.REQUIRED_TABLE_UNAVAILABLE
    return UnavailableReason.REQUIRED_FIELD_UNAVAILABLE


def _missing_evidence(metric_key: str) -> list[str]:
    if metric_key.startswith("infra."):
        return ["interpretable per-RSU queue/utilisation/capacity evidence"]
    if metric_key.startswith("traffic."):
        return ["canonical traffic observations with confirmed source units"]
    if metric_key.startswith("trip."):
        return ["trip or journey-time records"]
    if metric_key == "task.completion.rate_by_vehicle_tier":
        return ["per-vehicle tier mapping"]
    if metric_key == "task.energy.per_completed_j":
        return ["per-completed-task energy denominator"]
    if metric_key == "task.incomplete.rate":
        return ["physical completion status distinct from deadline success"]
    if metric_key == "task.deadline_miss.completed_observed_rate":
        return ["completed-task denominator compatible with the TrafficTwin definition"]
    return ["canonical row-level evidence required by this metric definition"]


def _unavailable_warning(metric_key: str) -> str:
    if metric_key.startswith("infra."):
        return "RSU source arrays are preserved but not assigned unconfirmed semantics."
    if metric_key == "task.incomplete.rate":
        return "Deadline misses are not silently presented as eventual physical incompletion."
    if metric_key == "task.energy.per_completed_j":
        return "The source reports joules per arrival, not TrafficTwin joules per completed task."
    return "The evaluation master does not contain the required compatible evidence."


def _run_fingerprint(run: TosEvaluationRun, package_fingerprint: str) -> str:
    payload = run.model_dump(mode="json", by_alias=True)
    basis = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(f"{package_fingerprint}|{basis}".encode()).hexdigest()
