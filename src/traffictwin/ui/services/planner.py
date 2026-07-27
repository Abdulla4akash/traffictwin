"""Experiment planner and protocol construction services."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from traffictwin.domain.experiment import Experiment
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.planning import ExperimentPlanSummary, summarise_experiment_plan
from traffictwin.experiments.protocol import (
    ExperimentProtocol,
    ProtocolBundleMatch,
    build_experiment_protocol,
    match_bundle_manifest,
    protocol_to_csv,
    protocol_to_yaml,
)
from traffictwin.ingestion.bundle import (
    validate_bundle,
)
from traffictwin.storage.registry import (
    DuplicateIdentifierError,
    Registry,
    RegistryNotFoundError,
)
from traffictwin.ui.services._common import _split_csv
from traffictwin.ui.services.models import ExperimentPlannerCatalog, ServiceError


def load_experiment_planner_catalog(
    registry_path: str | Path,
) -> ExperimentPlannerCatalog | ServiceError:
    """Load typed seeds, experiments, and known policy labels for planning."""

    path = Path(registry_path)
    try:
        registry = Registry(path)
        registry.initialize()
        seeds = registry.list_seeds()
        experiments = registry.list_experiments()
        runs = registry.list_runs()
    except (OSError, sqlite3.Error, ValueError) as exc:
        return ServiceError("The experiment-planning catalogue could not be loaded.", str(exc))
    algorithms = sorted(
        {
            *(seed.policy.algorithm for seed in seeds),
            *(run.algorithm for run in runs),
        }
    )
    return ExperimentPlannerCatalog(
        registry_path=path,
        seeds=seeds,
        experiments=experiments,
        algorithms=algorithms,
    )


def prepare_experiment_plan_for_ui(
    *,
    experiment_id: str,
    research_question: str,
    hypothesis: str,
    baseline_seed_id: str,
    variation_seed_ids: list[str],
    algorithms: list[str],
    additional_algorithm_labels: str,
    common_random_seeds: str,
    registered_seeds: list[ScenarioSeed],
    clock: Callable[[], datetime] | None = None,
) -> ExperimentPlanSummary | ServiceError:
    """Build and validate an experiment plan from UI form values."""

    try:
        random_seeds = _parse_nonnegative_int_csv(common_random_seeds)
        combined_algorithms = [
            *(algorithm.strip() for algorithm in algorithms if algorithm.strip()),
            *_split_csv(additional_algorithm_labels),
        ]
        now = clock() if clock is not None else datetime.now(UTC)
        experiment = Experiment(
            experiment_id=experiment_id.strip(),
            research_question=research_question.strip(),
            hypothesis=hypothesis.strip() or None,
            baseline_seed_id=baseline_seed_id,
            variation_seed_ids=variation_seed_ids,
            algorithms=combined_algorithms,
            common_random_seed_set=random_seeds,
            planned_replicates=len(random_seeds),
            created_at=now,
            updated_at=now,
        )
        return summarise_experiment_plan(
            experiment,
            {seed.seed_id: seed for seed in registered_seeds},
        )
    except (ValidationError, ValueError) as exc:
        return ServiceError("The experiment plan is invalid.", str(exc))


def register_experiment_plan_for_ui(
    summary: ExperimentPlanSummary,
    registry_path: str | Path,
) -> Experiment | ServiceError:
    """Register a validated plan without creating or launching runs."""

    try:
        registry = Registry(registry_path)
        registry.initialize()
        summarise_experiment_plan(
            summary.experiment,
            {seed.seed_id: seed for seed in registry.list_seeds()},
        )
        registry.add_experiment(summary.experiment)
    except (DuplicateIdentifierError, OSError, sqlite3.Error, ValueError) as exc:
        return ServiceError("The experiment plan could not be registered.", str(exc))
    return summary.experiment


def experiment_plan_yaml_for_ui(summary: ExperimentPlanSummary) -> str:
    """Serialise a validated experiment plan to deterministic YAML."""

    return yaml.safe_dump(
        summary.experiment.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=False,
    )


def build_experiment_protocol_for_ui(
    experiment: Experiment,
    registered_seeds: list[ScenarioSeed],
) -> ExperimentProtocol | ServiceError:
    """Build a read-only execution protocol from typed planner inputs."""

    try:
        return build_experiment_protocol(
            experiment,
            {seed.seed_id: seed for seed in registered_seeds},
        )
    except ValueError as exc:
        return ServiceError("The experiment protocol could not be built.", str(exc))


def load_registered_experiment_protocol_for_ui(
    experiment_id: str,
    registry_path: str | Path,
) -> ExperimentProtocol | ServiceError:
    """Load a registered experiment and build its deterministic protocol."""

    try:
        registry = Registry(registry_path)
        registry.initialize()
        experiment = registry.get_experiment(experiment_id)
        seeds = registry.list_seeds()
    except (OSError, sqlite3.Error, RegistryNotFoundError, ValueError) as exc:
        return ServiceError("The registered experiment protocol could not be loaded.", str(exc))
    return build_experiment_protocol_for_ui(experiment, seeds)


def experiment_protocol_yaml_for_ui(protocol: ExperimentProtocol) -> str:
    """Return the versioned protocol as deterministic YAML."""

    return protocol_to_yaml(protocol)


def experiment_protocol_csv_for_ui(protocol: ExperimentProtocol) -> str:
    """Return the protocol slots as a deterministic CSV run sheet."""

    return protocol_to_csv(protocol)


def match_bundle_to_protocol_for_ui(
    protocol: ExperimentProtocol,
    bundle_path: str | Path,
) -> ProtocolBundleMatch | ServiceError:
    """Validate and match one completed bundle without importing it."""

    result = validate_bundle(bundle_path)
    if result.manifest is None or not result.report.may_import:
        codes = ", ".join(finding.code.value for finding in result.report.findings)
        return ServiceError(
            "The bundle was rejected and cannot be matched to the protocol.",
            codes or "No valid manifest was available.",
        )
    return match_bundle_manifest(protocol, result.manifest)


def _parse_nonnegative_int_csv(value: str) -> list[int]:
    tokens = _split_csv(value)
    if not tokens:
        raise ValueError("at least one common random seed is required")
    try:
        parsed = [int(token) for token in tokens]
    except ValueError as exc:
        raise ValueError("common random seeds must be comma-separated integers") from exc
    if any(seed < 0 for seed in parsed):
        raise ValueError("common random seeds must be non-negative")
    if len(set(parsed)) != len(parsed):
        raise ValueError("common random seeds must not contain duplicates")
    return parsed
