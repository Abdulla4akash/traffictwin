"""Deterministic experiment-plan validation and preview."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from traffictwin.domain.experiment import Experiment
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.metrics.comparison import diff_seed_parameters
from traffictwin.metrics.results import JsonScalar


@dataclass(frozen=True)
class ExperimentPlanCell:
    """One planned condition, policy, and random-seed combination."""

    role: str
    seed_id: str
    algorithm: str
    random_seed: int

    def as_row(self) -> dict[str, str | int]:
        """Return a table-safe representation."""

        return {
            "role": self.role,
            "seed_id": self.seed_id,
            "algorithm": self.algorithm,
            "random_seed": self.random_seed,
        }


@dataclass(frozen=True)
class ExperimentPlanSummary:
    """Validated, bounded preview of an experiment plan."""

    experiment: Experiment
    condition_count: int
    algorithm_count: int
    replicate_count: int
    planned_run_count: int
    preview_cells: tuple[ExperimentPlanCell, ...]
    preview_truncated: bool
    seed_differences: dict[str, tuple[dict[str, JsonScalar], ...]]
    warnings: tuple[str, ...]


def summarise_experiment_plan(
    experiment: Experiment,
    registered_seeds: Mapping[str, ScenarioSeed],
    *,
    preview_limit: int = 200,
) -> ExperimentPlanSummary:
    """Validate seed references and build a deterministic plan preview."""

    if preview_limit < 1:
        raise ValueError("preview_limit must be at least 1")

    condition_ids = (experiment.baseline_seed_id, *experiment.variation_seed_ids)
    missing = sorted(seed_id for seed_id in condition_ids if seed_id not in registered_seeds)
    errors: list[str] = []
    if missing:
        errors.append(f"unregistered scenario seeds: {', '.join(missing)}")
    if experiment.baseline_seed_id in experiment.variation_seed_ids:
        errors.append("baseline seed must not also be a variation")
    if not experiment.algorithms:
        errors.append("at least one policy or algorithm label is required")
    elif any(not algorithm.strip() for algorithm in experiment.algorithms):
        errors.append("policy or algorithm labels must not be blank")
    if not experiment.common_random_seed_set:
        errors.append("at least one common random seed is required")
    if experiment.planned_replicates != len(experiment.common_random_seed_set):
        errors.append("planned_replicates must match the number of common random seeds")
    if errors:
        raise ValueError("; ".join(errors))

    algorithms = tuple(experiment.algorithms)
    random_seeds = tuple(experiment.common_random_seed_set)
    planned_run_count = len(condition_ids) * len(algorithms) * len(random_seeds)
    cells: list[ExperimentPlanCell] = []
    for condition_index, seed_id in enumerate(condition_ids):
        role = "baseline" if condition_index == 0 else "variation"
        for algorithm in algorithms:
            for random_seed in random_seeds:
                if len(cells) < preview_limit:
                    cells.append(
                        ExperimentPlanCell(
                            role=role,
                            seed_id=seed_id,
                            algorithm=algorithm,
                            random_seed=random_seed,
                        )
                    )

    warnings: list[str] = []
    if len(condition_ids) == 1 and len(algorithms) == 1:
        warnings.append(
            "The plan contains one condition and one policy, so it does not define a comparison."
        )
    if planned_run_count > preview_limit:
        warnings.append(
            f"The design preview is limited to {preview_limit} of {planned_run_count} run slots."
        )

    baseline_seed = registered_seeds[experiment.baseline_seed_id]
    differences = {
        variation_id: tuple(diff_seed_parameters(baseline_seed, registered_seeds[variation_id]))
        for variation_id in experiment.variation_seed_ids
    }
    return ExperimentPlanSummary(
        experiment=experiment,
        condition_count=len(condition_ids),
        algorithm_count=len(algorithms),
        replicate_count=len(random_seeds),
        planned_run_count=planned_run_count,
        preview_cells=tuple(cells),
        preview_truncated=planned_run_count > preview_limit,
        seed_differences=differences,
        warnings=tuple(warnings),
    )
