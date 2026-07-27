"""Experiment manager, research analysis, statistical study, and protocol services."""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import ValidationError

from traffictwin.demo.workspace import workspace_status
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.equivalence_testing import (
    EquivalenceStudy,
    EquivalenceStudyConfig,
    evaluate_equivalence_study,
)
from traffictwin.experiments.evidence import (
    ExperimentEvidenceOptions,
    ObjectiveDirection,
    TrainingValidationObservation,
    build_experiment_evidence_pack,
    training_validation_observation_from_collections,
)
from traffictwin.experiments.n_way_ranking import (
    NWayRankingConfig,
    NWayRankingStudy,
    evaluate_n_way_ranking,
)
from traffictwin.experiments.portfolio import (
    default_synthetic_portfolio_rules,
    evaluate_portfolio,
    evaluate_portfolio_study,
)
from traffictwin.experiments.power_analysis import (
    PowerAnalysis,
    PowerAnalysisConfig,
    evaluate_power_analysis,
)
from traffictwin.experiments.protocol import (
    build_experiment_protocol,
)
from traffictwin.experiments.regression_gate import (
    RegressionGateReport,
    RegressionGoldenContract,
    RegressionSubjectKind,
    evaluate_regression_gate,
    parse_regression_golden_contract_json,
)
from traffictwin.experiments.statistical_study import (
    PairedStudyConfig,
    StatisticalStudy,
    evaluate_paired_statistical_study,
)
from traffictwin.experiments.tracking import (
    ProtocolSlotStatus,
    ProtocolTracker,
    ProtocolTrackingError,
)
from traffictwin.experiments.winner_map import build_winner_map
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.rules.engine import evaluate_rules
from traffictwin.storage.registry import (
    Registry,
    RegistryNotFoundError,
)
from traffictwin.synthetic.experiments import (
    PORTFOLIO_DEVELOPMENT_PRESETS,
    PORTFOLIO_HELD_OUT_PRESETS,
    PORTFOLIO_STUDY_EXPERIMENT_ID,
)
from traffictwin.ui.services.models import (
    ExperimentManagerView,
    ResearchAnalysisCatalog,
    ResearchAnalysisView,
    ServiceError,
    StatisticalStudyCatalog,
)
from traffictwin.ui.services.reports import list_workspace_reports


def load_experiment_manager_view(
    registry_path: str | Path,
    workspace_path: str | Path | None = None,
) -> ExperimentManagerView:
    """Build a read-only local experiment manager catalogue."""

    path = Path(registry_path)
    experiments = _registry_payload_rows(path, "experiments", "experiment_id")
    runs = _registry_payload_rows(path, "runs", "run_id")
    seeds = _registry_payload_rows(path, "seeds", "seed_id")
    bundle_imports = _registry_bundle_rows(path)
    metrics_by_run = _registry_count_by_run(path, "metric_collections")
    evidence_by_run = _registry_count_by_run(path, "evidence_packs")
    policies = sorted({str(row.get("algorithm", "")) for row in runs if row.get("algorithm")})
    reports = list_workspace_reports(workspace_path) if workspace_path else []
    return ExperimentManagerView(
        registry_path=path,
        workspace=workspace_status(workspace_path) if workspace_path else None,
        experiments=experiments,
        runs=runs,
        seeds=seeds,
        policies=policies,
        bundle_imports=bundle_imports,
        comparisons=_workspace_comparisons(Path(workspace_path)) if workspace_path else [],
        reports=reports,
        metrics_by_run=metrics_by_run,
        evidence_by_run=evidence_by_run,
    )


def load_research_analysis_view(
    registry_path: str | Path,
    experiment_id: str,
    *,
    metric_key: str = "task.completion.rate",
    objective: ObjectiveDirection = ObjectiveDirection.MAXIMISE,
    training_validation: list[TrainingValidationObservation] | None = None,
) -> ResearchAnalysisView | ServiceError:
    """Build the experiment-level research analysis without UI calculations."""

    path = Path(registry_path)
    try:
        registry = Registry(path)
        collections = [
            collection
            for payload in registry.list_metric_collection_json()
            if (collection := MetricCollection.model_validate_json(payload)).results
            and collection.results[0].experiment_id == experiment_id
        ]
        if not collections:
            return ServiceError(
                "No stored metric collections match this experiment.",
                experiment_id,
            )
        registered_seeds = registry.list_seeds()
        aliases = {seed.seed_id: seed.parent_seed_id or seed.seed_id for seed in registered_seeds}
        seeds_by_family: dict[str, ScenarioSeed] = {}
        for seed in registered_seeds:
            family = aliases[seed.seed_id]
            if seed.seed_id == family:
                seeds_by_family[family] = seed
            else:
                seeds_by_family.setdefault(family, seed)
        evidence = build_experiment_evidence_pack(
            collections,
            ExperimentEvidenceOptions(
                experiment_id=experiment_id,
                primary_metric_key=metric_key,
                objective=objective,
            ),
            training_validation=training_validation,
        )
        diagnostics = evaluate_rules(evidence)
        winner_map = build_winner_map(
            collections,
            metric_key=metric_key,
            objective=objective,
            seed_aliases=aliases,
        )
        portfolio = evaluate_portfolio(
            winner_map,
            seeds_by_family,
            default_synthetic_portfolio_rules(),
        )
        portfolio_study = None
        if experiment_id == PORTFOLIO_STUDY_EXPERIMENT_ID:
            portfolio_study = evaluate_portfolio_study(
                winner_map,
                seeds_by_family,
                default_synthetic_portfolio_rules(),
                development_seed_ids=[f"seed-{name}" for name in PORTFOLIO_DEVELOPMENT_PRESETS],
                held_out_seed_ids=[f"seed-{name}" for name in PORTFOLIO_HELD_OUT_PRESETS],
            )
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Research analysis could not be prepared.", str(exc))
    return ResearchAnalysisView(
        experiment_id=experiment_id,
        source_collection_count=len(collections),
        evidence_pack=evidence,
        diagnostic_report=diagnostics,
        winner_map=winner_map,
        portfolio=portfolio,
        portfolio_study=portfolio_study,
    )


def load_research_analysis_catalog(
    registry_path: str | Path,
    experiment_id: str,
) -> ResearchAnalysisCatalog | ServiceError:
    """List finite scalar metrics and runs available for one experiment."""

    try:
        collections = _metric_collections_for_experiment(registry_path, experiment_id)
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Research analysis inputs could not be loaded.", str(exc))
    if not collections:
        return ServiceError("No stored metric collections match this experiment.", experiment_id)
    metric_keys = sorted(
        {
            metric.metric_key
            for collection in collections
            for metric in collection.results
            if metric.status is MetricStatus.AVAILABLE
            and isinstance(metric.value, int | float)
            and not isinstance(metric.value, bool)
        }
    )
    if not metric_keys:
        return ServiceError("No available finite scalar metrics match this experiment.")
    return ResearchAnalysisCatalog(
        experiment_id=experiment_id,
        metric_keys=metric_keys,
        run_ids=sorted(collection.run_id for collection in collections),
    )


def statistical_study_experiments_for_ui(
    registry_path: str | Path,
) -> list[str] | ServiceError:
    """List registered experiments that also have stored metric collections."""

    try:
        registry = Registry(registry_path)
        with_metrics = {
            collection.results[0].experiment_id
            for payload in registry.list_metric_collection_json()
            if (collection := MetricCollection.model_validate_json(payload)).results
            and collection.results[0].experiment_id is not None
        }
        return [
            experiment.experiment_id
            for experiment in registry.list_experiments()
            if experiment.experiment_id in with_metrics
        ]
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Statistical-study experiments could not be loaded.", str(exc))


def load_statistical_study_catalog(
    registry_path: str | Path,
    experiment_id: str,
) -> StatisticalStudyCatalog | ServiceError:
    """Load one registered common-seed plan and its stored scalar metric catalogue."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(experiment_id)
        collections = _metric_collections_for_experiment(registry_path, experiment_id)
        if not collections:
            return ServiceError("No stored metric collections match this experiment.")
        metric_keys = sorted(
            {
                metric.metric_key
                for collection in collections
                for metric in collection.results
                if metric.status is MetricStatus.AVAILABLE
                and isinstance(metric.value, int | float)
                and not isinstance(metric.value, bool)
                and math.isfinite(float(metric.value))
            }
        )
        if not metric_keys:
            return ServiceError("No finite scalar metrics are available for this experiment.")
        checkpoints = sorted(
            {collection.results[0].checkpoint for collection in collections},
            key=lambda value: (value is not None, value or ""),
        )
        return StatisticalStudyCatalog(
            experiment_id=experiment_id,
            baseline_seed_id=experiment.baseline_seed_id,
            variation_seed_ids=list(experiment.variation_seed_ids),
            algorithms=list(experiment.algorithms),
            checkpoints=checkpoints,
            metric_keys=metric_keys,
            expected_random_seeds=sorted(experiment.common_random_seed_set),
            collection_count=len(collections),
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Statistical-study inputs could not be loaded.", str(exc))


def evaluate_statistical_study_for_ui(
    registry_path: str | Path,
    config: PairedStudyConfig,
) -> StatisticalStudy | ServiceError:
    """Delegate one complete predeclared STA-01 plan to the library service."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(config.experiment_id)
        if config.baseline_seed_id != experiment.baseline_seed_id:
            raise ValueError("baseline seed does not match the registered experiment plan")
        if config.variation_seed_id not in experiment.variation_seed_ids:
            raise ValueError("variation seed is not declared by the registered experiment plan")
        if config.algorithm not in experiment.algorithms:
            raise ValueError("algorithm is not declared by the registered experiment plan")
        if config.expected_random_seeds != sorted(experiment.common_random_seed_set):
            raise ValueError("common random-seed set does not match the registered experiment plan")
        return evaluate_paired_statistical_study(
            _metric_collections_for_experiment(registry_path, config.experiment_id),
            config,
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Statistical study could not be evaluated.", str(exc))


def evaluate_n_way_ranking_for_ui(
    registry_path: str | Path,
    config: NWayRankingConfig,
) -> NWayRankingStudy | ServiceError:
    """Delegate one complete registered STA-02 plan to the library service."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(config.experiment_id)
        planned_seeds = {experiment.baseline_seed_id, *experiment.variation_seed_ids}
        if not set(config.seed_ids).issubset(planned_seeds):
            raise ValueError("scenario families are not declared by the registered experiment")
        if not set(config.algorithms).issubset(experiment.algorithms):
            raise ValueError("policies are not declared by the registered experiment")
        if config.expected_random_seeds != sorted(experiment.common_random_seed_set):
            raise ValueError("common random-seed set does not match the registered experiment plan")
        aliases = {
            seed.seed_id: seed.parent_seed_id or seed.seed_id for seed in registry.list_seeds()
        }
        return evaluate_n_way_ranking(
            _metric_collections_for_experiment(registry_path, config.experiment_id),
            config,
            seed_aliases=aliases,
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("N-way ranking could not be evaluated.", str(exc))


def evaluate_equivalence_study_for_ui(
    registry_path: str | Path,
    config: EquivalenceStudyConfig,
) -> EquivalenceStudy | ServiceError:
    """Delegate one complete registered STA-03 plan to the library service."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(config.experiment_id)
        if config.baseline_seed_id != experiment.baseline_seed_id:
            raise ValueError("baseline seed does not match the registered experiment plan")
        if config.variation_seed_id not in experiment.variation_seed_ids:
            raise ValueError("variation seed is not declared by the registered experiment plan")
        if config.algorithm not in experiment.algorithms:
            raise ValueError("algorithm is not declared by the registered experiment plan")
        if config.expected_random_seeds != sorted(experiment.common_random_seed_set):
            raise ValueError("common random-seed set does not match the registered experiment plan")
        return evaluate_equivalence_study(
            _metric_collections_for_experiment(registry_path, config.experiment_id),
            config,
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Equivalence study could not be evaluated.", str(exc))


def evaluate_power_analysis_for_ui(
    config: PowerAnalysisConfig,
) -> PowerAnalysis | ServiceError:
    """Delegate one complete STA-05 prospective plan to the library service."""

    try:
        return evaluate_power_analysis(config)
    except (ValueError, ValidationError) as exc:
        return ServiceError("Power analysis could not be evaluated.", str(exc))


def regression_metric_runs_for_ui(
    registry_path: str | Path,
) -> list[str] | ServiceError:
    """List stored non-empty MetricCollections available as STA-04 subjects."""

    try:
        return sorted(
            collection.run_id
            for payload in Registry(registry_path).list_metric_collection_json()
            if (collection := MetricCollection.model_validate_json(payload)).results
        )
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Regression-gate metric subjects could not be loaded.", str(exc))


def parse_regression_golden_for_ui(
    payload: bytes,
) -> RegressionGoldenContract | ServiceError:
    """Parse one bounded strict golden contract uploaded by the user."""

    try:
        return parse_regression_golden_contract_json(payload)
    except (ValueError, ValidationError) as exc:
        return ServiceError("Regression golden contract is invalid.", str(exc))


def evaluate_metric_regression_gate_for_ui(
    registry_path: str | Path,
    run_id: str,
    contract: RegressionGoldenContract,
) -> RegressionGateReport | ServiceError:
    """Evaluate one stored MetricCollection against an uploaded golden contract."""

    if contract.subject_kind is not RegressionSubjectKind.METRIC_COLLECTION:
        return ServiceError("The golden contract does not target a metric collection.")
    try:
        collection = MetricCollection.model_validate_json(
            Registry(registry_path).get_metric_collection_json(run_id)
        )
        return evaluate_regression_gate(collection, contract)
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Metric regression gate could not be evaluated.", str(exc))


def evaluate_statistical_regression_gate_for_ui(
    study: StatisticalStudy,
    contract: RegressionGoldenContract,
) -> RegressionGateReport | ServiceError:
    """Evaluate an existing typed STA-01 session result against a golden contract."""

    if contract.subject_kind is not RegressionSubjectKind.PAIRED_STATISTICAL_STUDY:
        return ServiceError("The golden contract does not target a paired statistical study.")
    try:
        return evaluate_regression_gate(study, contract)
    except (ValueError, ValidationError) as exc:
        return ServiceError("Statistical-study regression gate could not be evaluated.", str(exc))


def build_training_validation_pairs_for_ui(
    registry_path: str | Path,
    training_run_ids: list[str],
    validation_run_ids: list[str],
    metric_key: str,
) -> list[TrainingValidationObservation] | ServiceError:
    """Build ordered, explicit, compatibility-checked pairs for R5."""

    if len(training_run_ids) != len(validation_run_ids):
        return ServiceError(
            "Training and validation selections must contain the same number of runs."
        )
    if len(set(training_run_ids)) != len(training_run_ids) or len(set(validation_run_ids)) != len(
        validation_run_ids
    ):
        return ServiceError("Training and validation run selections must not contain duplicates.")
    registry = Registry(registry_path)
    pairs: list[TrainingValidationObservation] = []
    try:
        for training_id, validation_id in zip(training_run_ids, validation_run_ids, strict=True):
            training = MetricCollection.model_validate_json(
                registry.get_metric_collection_json(training_id)
            )
            validation = MetricCollection.model_validate_json(
                registry.get_metric_collection_json(validation_id)
            )
            pairs.append(
                training_validation_observation_from_collections(
                    training,
                    validation,
                    metric_key,
                )
            )
    except (OSError, sqlite3.Error, ValueError, ValidationError, RegistryNotFoundError) as exc:
        return ServiceError("Training-validation pairs are incompatible.", str(exc))
    return pairs


def _metric_collections_for_experiment(
    registry_path: str | Path,
    experiment_id: str,
) -> list[MetricCollection]:
    registry = Registry(registry_path)
    return [
        collection
        for payload in registry.list_metric_collection_json()
        if (collection := MetricCollection.model_validate_json(payload)).results
        and collection.results[0].experiment_id == experiment_id
    ]


def protocol_tracking_rows_for_ui(
    registry_path: str | Path,
) -> list[dict[str, object]] | ServiceError:
    """Return manual protocol slot state for the Experiment Manager."""

    tracker = ProtocolTracker(registry_path)
    rows: list[dict[str, object]] = []
    try:
        for protocol_id in tracker.list_protocol_ids():
            rows.extend(slot.model_dump(mode="json") for slot in tracker.list_slots(protocol_id))
    except (OSError, sqlite3.Error, ProtocolTrackingError) as exc:
        return ServiceError("Protocol tracking state could not be loaded.", str(exc))
    return rows


def initialise_protocol_tracking_for_ui(
    registry_path: str | Path,
    experiment_id: str,
) -> dict[str, object] | ServiceError:
    """Create manual tracking rows from a registered experiment protocol."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(experiment_id)
        seeds = {seed.seed_id: seed for seed in registry.list_seeds()}
        protocol = build_experiment_protocol(experiment, seeds)
        created = ProtocolTracker(registry_path).register_protocol(protocol)
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        RegistryNotFoundError,
        ProtocolTrackingError,
    ) as exc:
        return ServiceError("Protocol tracking could not be initialised.", str(exc))
    return {
        "protocol_id": protocol.protocol_id,
        "slot_count": len(protocol.slots),
        "created": created,
    }


def update_protocol_slot_for_ui(
    registry_path: str | Path,
    protocol_id: str,
    slot_id: str,
    status: str,
    *,
    run_id: str = "",
    bundle_id: str = "",
    note: str = "",
) -> dict[str, object] | ServiceError:
    """Apply a manual protocol-slot transition through the typed tracker."""

    try:
        record = ProtocolTracker(registry_path).update_slot(
            protocol_id,
            slot_id,
            ProtocolSlotStatus(status),
            observed_run_id=run_id or None,
            observed_bundle_id=bundle_id or None,
            note=note or None,
        )
    except (OSError, sqlite3.Error, ValueError, ProtocolTrackingError) as exc:
        return ServiceError("Protocol slot could not be updated.", str(exc))
    return record.model_dump(mode="json")


def _registry_payload_rows(
    registry_path: Path,
    table: Literal["experiments", "runs", "seeds"],
    id_column: Literal["experiment_id", "run_id", "seed_id"],
) -> list[dict[str, object]]:
    if not registry_path.exists():
        return []
    queries = {
        ("experiments", "experiment_id"): (
            "SELECT experiment_id, payload FROM experiments ORDER BY experiment_id"
        ),
        ("runs", "run_id"): "SELECT run_id, payload FROM runs ORDER BY run_id",
        ("seeds", "seed_id"): "SELECT seed_id, payload FROM seeds ORDER BY seed_id",
    }
    with sqlite3.connect(registry_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(queries[(table, id_column)]).fetchall()
    payloads: list[dict[str, object]] = []
    for row in rows:
        payload = yaml.safe_load(cast(str, row["payload"]))
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _registry_bundle_rows(registry_path: Path) -> list[dict[str, object]]:
    if not registry_path.exists():
        return []
    with sqlite3.connect(registry_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT bundle_id, run_id, source_reference, fingerprint, imported_at
            FROM bundle_imports
            ORDER BY imported_at DESC, bundle_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _registry_count_by_run(
    registry_path: Path,
    table: Literal["metric_collections", "evidence_packs"],
) -> dict[str, int]:
    if not registry_path.exists():
        return {}
    queries = {
        "metric_collections": (
            "SELECT run_id, COUNT(*) AS count "
            "FROM metric_collections GROUP BY run_id ORDER BY run_id"
        ),
        "evidence_packs": (
            "SELECT run_id, COUNT(*) AS count FROM evidence_packs GROUP BY run_id ORDER BY run_id"
        ),
    }
    with sqlite3.connect(registry_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(queries[table]).fetchall()
    return {cast(str, row["run_id"]): cast(int, row["count"]) for row in rows}


def _workspace_comparisons(workspace_path: Path) -> list[dict[str, object]]:
    path = workspace_path / "exports" / "comparisons.yaml"
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    comparisons = raw.get("comparisons", []) if isinstance(raw, dict) else []
    return comparisons if isinstance(comparisons, list) else []
