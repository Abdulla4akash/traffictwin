"""Idempotent registry import for TOS evaluation-summary runs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.domain.enums import (
    ExecutionMode,
    ExperimentStatus,
    RunStatus,
    ValidationStatus,
)
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.run import Run
from traffictwin.evidence.pack import EvidencePack
from traffictwin.integration.tos.metrics import (
    build_tos_evidence_pack,
    metric_collection_from_evaluation,
)
from traffictwin.integration.tos.models import (
    TosEvaluationRun,
    TosImportSummary,
    TosValidationReport,
)
from traffictwin.integration.tos.readers import read_evaluation_runs
from traffictwin.integration.tos.validation import validate_tos_package
from traffictwin.metrics.results import MetricCollection
from traffictwin.storage.registry import (
    Registry,
    RegistryConflictError,
    RegistryNotFoundError,
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def import_evaluation_summaries(
    root: str | Path,
    registry_path: str | Path,
    *,
    validation_report: TosValidationReport | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> TosImportSummary:
    """Import documented evaluation rows and partial evidence idempotently."""

    report = validation_report or validate_tos_package(root)
    if not report.may_import_summaries or report.package_fingerprint is None:
        raise RegistryConflictError("TOS package validation rejected summary import")
    rows = read_evaluation_runs(root)
    registry = Registry(registry_path)
    registry.initialize()
    grouped: dict[str, list[TosEvaluationRun]] = defaultdict(list)
    for row in rows:
        grouped[row.experiment_id].append(row)

    experiments_created = 0
    experiments_existing = 0
    for experiment_id in sorted(grouped):
        experiment = _experiment_from_rows(grouped[experiment_id], clock())
        if _ensure_experiment(registry, experiment):
            experiments_created += 1
        else:
            experiments_existing += 1

    runs_created = 0
    runs_existing = 0
    metrics_stored = 0
    packs_stored = 0
    run_ids: list[str] = []
    for row in sorted(rows, key=lambda item: item.run_id):
        run = _run_from_evaluation(row, report.package_fingerprint, clock())
        created = _ensure_run(registry, run)
        if created:
            runs_created += 1
        else:
            runs_existing += 1
        collection = metric_collection_from_evaluation(
            row,
            report.package_fingerprint,
            clock=clock,
        )
        pack = build_tos_evidence_pack(row, report, collection, clock=clock)
        if created or not _same_metric_collection(registry, collection):
            registry.store_metric_collection(
                run_id=collection.run_id,
                metric_version=collection.metric_version,
                source_fingerprint=collection.input_fingerprint,
                payload_json=collection.model_dump_json(),
            )
            metrics_stored += 1
        if created or not _same_evidence_pack(registry, pack):
            registry.store_evidence_pack(
                pack_id=pack.pack_id,
                run_id=run.run_id,
                source_fingerprint=pack.source_bundle_fingerprint,
                payload_json=pack.model_dump_json(),
            )
            packs_stored += 1
        run_ids.append(run.run_id)

    return TosImportSummary(
        package_fingerprint=report.package_fingerprint,
        registry_reference=Path(registry_path).name,
        experiments_created=experiments_created,
        experiments_existing=experiments_existing,
        runs_created=runs_created,
        runs_existing=runs_existing,
        metric_collections_stored=metrics_stored,
        evidence_packs_stored=packs_stored,
        run_ids=run_ids,
        warnings=[
            "Imported values are source-provided evaluation summaries.",
            "No canonical task rows or interpreted RSU infrastructure records were registered.",
        ],
    )


def _experiment_from_rows(rows: list[TosEvaluationRun], now: datetime) -> Experiment:
    first = rows[0]
    seed_sets = [
        {row.fleet_seed for row in rows if row.campaign == campaign}
        for campaign in sorted({row.campaign for row in rows})
    ]
    common_seeds = sorted(set.intersection(*seed_sets)) if seed_sets else []
    return Experiment(
        experiment_id=first.experiment_id,
        research_question=(
            f"How do documented source campaigns compare for cell {first.cell} and "
            f"evaluation fleet {first.eval_fleet}?"
        ),
        hypothesis=None,
        baseline_seed_id=first.seed_id,
        variation_seed_ids=[],
        algorithms=sorted({row.campaign for row in rows}),
        common_random_seed_set=common_seeds,
        planned_replicates=max(len({row.fleet_seed for row in rows}), 1),
        status=ExperimentStatus.COMPLETED,
        created_at=now,
        updated_at=now,
    )


def _run_from_evaluation(
    row: TosEvaluationRun,
    package_fingerprint: str,
    now: datetime,
) -> Run:
    return Run(
        run_id=row.run_id,
        experiment_id=row.experiment_id,
        seed_id=row.seed_id,
        algorithm=row.campaign,
        checkpoint=row.actor,
        random_seed=row.fleet_seed,
        environment_version=row.engine_version,
        environment_commit=None,
        execution_mode=ExecutionMode.IMPORTED,
        status=RunStatus.COMPLETED,
        source_bundle=f"tos-data:{package_fingerprint[:16]}",
        validation_status=ValidationStatus.VALID,
        created_at=now,
        updated_at=now,
    )


def _ensure_experiment(registry: Registry, expected: Experiment) -> bool:
    try:
        existing = registry.get_experiment(expected.experiment_id)
    except RegistryNotFoundError:
        registry.add_experiment(expected)
        return True
    fields = (
        "baseline_seed_id",
        "variation_seed_ids",
        "algorithms",
        "common_random_seed_set",
        "planned_replicates",
        "status",
    )
    if any(getattr(existing, field) != getattr(expected, field) for field in fields):
        raise RegistryConflictError(
            f"experiment identifier conflicts with existing metadata: {expected.experiment_id}"
        )
    return False


def _ensure_run(registry: Registry, expected: Run) -> bool:
    try:
        existing = registry.get_run(expected.run_id)
    except RegistryNotFoundError:
        registry.add_run(expected)
        return True
    fields = (
        "experiment_id",
        "seed_id",
        "algorithm",
        "checkpoint",
        "random_seed",
        "environment_version",
        "execution_mode",
        "source_bundle",
        "validation_status",
    )
    if any(getattr(existing, field) != getattr(expected, field) for field in fields):
        raise RegistryConflictError(
            f"run identifier conflicts with existing metadata: {expected.run_id}"
        )
    return False


def _same_metric_collection(registry: Registry, expected: MetricCollection) -> bool:
    try:
        existing = MetricCollection.model_validate_json(
            registry.get_metric_collection_json(expected.run_id)
        )
    except RegistryNotFoundError:
        return False
    return _normalised_metric(existing) == _normalised_metric(expected)


def _same_evidence_pack(registry: Registry, expected: EvidencePack) -> bool:
    try:
        existing = EvidencePack.model_validate_json(
            registry.get_evidence_pack_json(expected.pack_id)
        )
    except RegistryNotFoundError:
        return False
    return existing.fingerprint() == expected.fingerprint()


def _normalised_metric(collection: MetricCollection) -> dict[str, object]:
    payload = collection.model_dump(mode="json")
    payload["generated_at"] = "<normalised>"
    for result in payload["results"]:
        result["computed_at"] = "<normalised>"
    return payload
