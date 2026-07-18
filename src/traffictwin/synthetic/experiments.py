"""Multi-seed synthetic experiment generation for standalone demonstrations."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.aggregation import aggregate_experiment
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import JsonScalar, MetricCollection, MetricStatus, MetricValue
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import SyntheticPolicyProfile
from traffictwin.synthetic.scenarios import preset_config

R3_EVIDENCE_KEYS = [
    "experiment.algorithm.count",
    "experiment.cross_algorithm_dispersion",
    "experiment.always_local_gap_from_best",
    "experiment.pressure.indicator",
]


def generate_trivial_multi_algorithm_experiment(
    output_dir: str | Path,
    *,
    random_seeds: list[int] | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Generate low-pressure bundles for multiple synthetic policy profiles."""

    destination = Path(output_dir)
    if destination.exists():
        if not overwrite:
            msg = f"experiment output already exists: {destination}"
            raise FileExistsError(msg)
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    seeds = random_seeds or [1, 2, 3]
    policies = [
        SyntheticPolicyProfile.ALWAYS_LOCAL,
        SyntheticPolicyProfile.SELECTIVE,
        SyntheticPolicyProfile.BALANCED,
    ]
    bundle_paths: list[Path] = []
    for seed in seeds:
        for policy in policies:
            config = preset_config("trivial_multi_algorithm", random_seed=seed, policy=policy)
            suffix = policy.value.replace("synthetic-", "").replace("_", "-")
            config = config.model_copy(
                update={
                    "scenario_id": f"trivial_multi_algorithm-{suffix}-{seed}",
                    "experiment_id": "exp-standalone-trivial",
                }
            )
            bundle_paths.append(
                write_synthetic_bundle(
                    config,
                    destination / f"{suffix}-{seed}",
                    overwrite=True,
                )
            )
    return bundle_paths


def build_r3_evidence_pack_from_bundles(
    bundle_paths: list[Path],
    *,
    clock: Callable[[], datetime] | None = None,
) -> EvidencePack:
    """Build an R3-compatible EvidencePack from Phase 3 metric aggregation."""

    now = clock() if clock is not None else datetime.now(UTC)
    config = MetricEngineConfig()
    collections = [
        compute_metrics_for_bundle(validate_bundle(path), config, clock=lambda: now)
        for path in sorted(bundle_paths, key=lambda item: str(item))
    ]
    aggregate = aggregate_experiment(
        collections,
        metric_keys=["task.completion.rate", "task.incomplete.rate", "infra.utilisation.mean"],
        clock=lambda: now,
    )
    by_algorithm: dict[str, list[float]] = {}
    pressure_values: list[float] = []
    for condition in aggregate.conditions:
        algorithm = condition.algorithm or "unknown"
        for metric in condition.metrics:
            if metric.metric_key == "task.completion.rate" and metric.mean is not None:
                by_algorithm.setdefault(algorithm, []).append(metric.mean)
            if (
                metric.metric_key in {"task.incomplete.rate", "infra.utilisation.mean"}
                and metric.mean is not None
            ):
                pressure_values.append(metric.mean)
    algorithm_means = {
        algorithm: sum(values) / len(values)
        for algorithm, values in sorted(by_algorithm.items())
        if values
    }
    best = max(algorithm_means.values()) if algorithm_means else 0.0
    worst = min(algorithm_means.values()) if algorithm_means else 0.0
    local = algorithm_means.get(SyntheticPolicyProfile.ALWAYS_LOCAL.value, best)
    context = _experiment_context(collections)
    metrics = [
        _experiment_metric(
            "experiment.algorithm.count",
            len(algorithm_means),
            "count",
            context,
            now,
            config,
        ),
        _experiment_metric(
            "experiment.cross_algorithm_dispersion",
            best - worst,
            "ratio",
            context,
            now,
            config,
        ),
        _experiment_metric(
            "experiment.always_local_gap_from_best",
            best - local,
            "ratio",
            context,
            now,
            config,
        ),
        _experiment_metric(
            "experiment.pressure.indicator",
            sum(pressure_values) / len(pressure_values) if pressure_values else 0.0,
            "ratio",
            context,
            now,
            config,
        ),
    ]
    collection = MetricCollection(
        run_id="experiment-exp-standalone-trivial",
        metric_version=config.metric_version,
        results=metrics,
        unavailable_count=0,
        partial_count=0,
        generated_at=now,
        input_fingerprint="synthetic-trivial-aggregation",
    )
    return EvidencePack(
        pack_id="evidence-exp-standalone-trivial-r3",
        generated_at=now,
        synthetic=True,
        run_context={
            "run_id": "experiment-exp-standalone-trivial",
            "experiment_id": "exp-standalone-trivial",
            "seed_id": "seed-trivial_multi_algorithm",
            "algorithm": "multiple synthetic policy profiles",
            "checkpoint": None,
            "random_seed": -1,
            "environment": "synthetic",
            "environment_version": "1.0",
            "environment_commit": None,
        },
        source_bundle_fingerprint="synthetic-trivial-aggregation",
        validation_summary={
            "status": "accepted",
            "may_import": True,
            "finding_count": 0,
            "counts_by_severity": {},
            "validator_version": "phase2.1",
        },
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.AVAILABLE,
            infrastructure=EvidenceStatus.AVAILABLE,
            vehicles=EvidenceStatus.AVAILABLE,
            traffic=EvidenceStatus.AVAILABLE,
            trips=EvidenceStatus.AVAILABLE,
            incidents=EvidenceStatus.UNAVAILABLE,
            diagnosis=EvidenceStatus.AVAILABLE,
        ),
        metric_engine_config=config,
        metric_collection=collection,
        excluded_record_counts={},
        warnings=[
            "R3 evidence is derived from standalone synthetic low-pressure policy-profile bundles."
        ],
        provenance={
            "bundle_source": "standalone synthetic experiment aggregation",
            "metric_version": config.metric_version,
            "aggregation_condition_count": aggregate.condition_count,
        },
    )


def _experiment_context(collections: list[MetricCollection]) -> dict[str, JsonScalar]:
    first = collections[0].results[0] if collections and collections[0].results else None
    return {
        "run_id": "experiment-exp-standalone-trivial",
        "experiment_id": "exp-standalone-trivial",
        "seed_id": "seed-trivial_multi_algorithm",
        "algorithm": "multiple synthetic policy profiles",
        "checkpoint": None,
        "random_seed": first.random_seed if first is not None else 0,
        "synthetic": True,
    }


def _experiment_metric(
    key: str,
    value: float | int,
    unit: str,
    context: dict[str, JsonScalar],
    computed_at: datetime,
    config: MetricEngineConfig,
) -> MetricValue:
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE,
        value=value,
        unit=unit,
        scope="experiment",
        dimensions={},
        required_evidence=["metric_collections", "experiment_aggregation"],
        missing_evidence=[],
        reason_codes=[],
        warnings=[],
        implementation_version=config.metric_version,
        run_id=str(context["run_id"]),
        experiment_id=str(context["experiment_id"]),
        seed_id=str(context["seed_id"]),
        algorithm=str(context["algorithm"]),
        checkpoint=None,
        random_seed=_context_random_seed(context),
        synthetic=True,
        computed_at=computed_at,
        metadata={"source": "Phase 3 aggregate_experiment"},
    )


def _context_random_seed(context: dict[str, JsonScalar]) -> int:
    value = context.get("random_seed")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0
