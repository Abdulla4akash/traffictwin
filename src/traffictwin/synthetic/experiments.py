"""Multi-seed synthetic experiment generation for standalone demonstrations."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.pack import EvidencePack
from traffictwin.experiments.evidence import (
    ExperimentEvidenceOptions,
    build_experiment_evidence_pack,
)
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import SyntheticPolicyProfile
from traffictwin.synthetic.generator import generate_run_data
from traffictwin.synthetic.scenarios import preset_config

R3_EVIDENCE_KEYS = [
    "experiment.algorithm.count",
    "experiment.cross_algorithm_dispersion",
    "experiment.always_local_gap_from_best",
    "experiment.pressure.indicator",
]

PORTFOLIO_STUDY_EXPERIMENT_ID = "exp-synthetic-portfolio-study"
PORTFOLIO_DEVELOPMENT_PRESETS = [
    "trivial_multi_algorithm",
    "under_offloading",
    "infrastructure_bottleneck",
]
PORTFOLIO_HELD_OUT_PRESETS = [
    "s5_stadium_event_siting",
    "s6_road_clearing_corridor",
]


@dataclass(frozen=True)
class SyntheticPortfolioStudyFixture:
    """Generated multi-seed/multi-policy portfolio study inputs."""

    bundle_paths: list[Path]
    base_seeds: dict[str, ScenarioSeed]
    development_seed_ids: list[str]
    held_out_seed_ids: list[str]


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
                    "baseline_seed_id": "seed-trivial_multi_algorithm",
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


def generate_synthetic_portfolio_study(
    output_dir: str | Path,
    *,
    random_seeds: list[int] | None = None,
    overwrite: bool = False,
) -> SyntheticPortfolioStudyFixture:
    """Generate a fixed development/held-out portfolio workflow fixture."""

    destination = Path(output_dir)
    if destination.exists():
        if not overwrite:
            raise FileExistsError(f"portfolio study output already exists: {destination}")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    seeds = random_seeds or [1, 2, 3]
    policies = [
        SyntheticPolicyProfile.ALWAYS_LOCAL,
        SyntheticPolicyProfile.SELECTIVE,
        SyntheticPolicyProfile.BALANCED,
    ]
    base_seeds: dict[str, ScenarioSeed] = {}
    bundle_paths: list[Path] = []
    for preset_name in [*PORTFOLIO_DEVELOPMENT_PRESETS, *PORTFOLIO_HELD_OUT_PRESETS]:
        base_config = preset_config(preset_name)
        base_seed = generate_run_data(base_config).seed
        base_seeds[base_seed.seed_id] = base_seed
        for random_seed in seeds:
            for policy in policies:
                suffix = policy.value.removeprefix("synthetic-")
                config = preset_config(preset_name, random_seed=random_seed, policy=policy)
                config = config.model_copy(
                    update={
                        "scenario_id": (f"portfolio-{preset_name}-{suffix}-{random_seed}"),
                        "experiment_id": PORTFOLIO_STUDY_EXPERIMENT_ID,
                        "baseline_seed_id": base_seed.seed_id,
                    }
                )
                bundle_paths.append(
                    write_synthetic_bundle(
                        config,
                        destination / preset_name / f"{preset_name}-{suffix}-{random_seed}",
                        overwrite=True,
                    )
                )
    return SyntheticPortfolioStudyFixture(
        bundle_paths=bundle_paths,
        base_seeds=base_seeds,
        development_seed_ids=[
            generate_run_data(preset_config(name)).seed.seed_id
            for name in PORTFOLIO_DEVELOPMENT_PRESETS
        ],
        held_out_seed_ids=[
            generate_run_data(preset_config(name)).seed.seed_id
            for name in PORTFOLIO_HELD_OUT_PRESETS
        ],
    )


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
    pack = build_experiment_evidence_pack(
        collections,
        ExperimentEvidenceOptions(experiment_id="exp-standalone-trivial"),
        clock=lambda: now,
    )
    return pack.model_copy(
        update={
            "warnings": [
                *pack.warnings,
                "R3 evidence is derived from standalone synthetic low-pressure policy-profile "
                "bundles.",
            ]
        }
    )
