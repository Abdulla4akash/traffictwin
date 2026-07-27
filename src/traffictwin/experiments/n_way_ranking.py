"""Strict common-seed N-way ranking built on the descriptive winner map."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.experiments.statistical_study import metric_collection_fingerprint
from traffictwin.experiments.winner_map import PolicyScore, WinnerMapReport, build_winner_map
from traffictwin.metrics.results import JsonScalar, MetricCollection, MetricStatus, MetricValue
from traffictwin.metrics.statistics import percentile_linear, stable_float

N_WAY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
N_WAY_METHOD_VERSION: Literal["1.0"] = "1.0"
N_WAY_BOOTSTRAP_METHOD: Literal["joint_paired_seed_percentile_bootstrap_v1"] = (
    "joint_paired_seed_percentile_bootstrap_v1"
)
MINIMUM_N_WAY_SUPPORT: Literal[3] = 3
MINIMUM_BOOTSTRAP_REPETITIONS = 1_000
MAXIMUM_BOOTSTRAP_REPETITIONS = 100_000


class NWayRankingStatus(StrEnum):
    """Availability of a complete study or one scenario-family ranking."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    INCOMPATIBLE = "incompatible"


class NWayComponentStatus(StrEnum):
    """Availability of one N-way statistical component."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class NWayExclusionCode(StrEnum):
    """Stable reasons an endpoint or seed cannot enter an N-way ranking."""

    DUPLICATE_RUN_ID = "DUPLICATE_RUN_ID"
    EMPTY_COLLECTION = "EMPTY_COLLECTION"
    METRIC_MISSING = "METRIC_MISSING"
    METRIC_UNAVAILABLE = "METRIC_UNAVAILABLE"
    METRIC_NOT_FINITE_SCALAR = "METRIC_NOT_FINITE_SCALAR"
    METRIC_CONTEXT_MISMATCH = "METRIC_CONTEXT_MISMATCH"
    SOURCE_FINGERPRINT_MISSING = "SOURCE_FINGERPRINT_MISSING"
    ENVIRONMENT_PROVENANCE_UNRESOLVED = "ENVIRONMENT_PROVENANCE_UNRESOLVED"
    SEMANTIC_CONTRACT_UNRESOLVED = "SEMANTIC_CONTRACT_UNRESOLVED"
    DUPLICATE_POLICY_SEED = "DUPLICATE_POLICY_SEED"
    INCOMPLETE_COMMON_SEED = "INCOMPLETE_COMMON_SEED"
    COMMON_SEED_INCOMPATIBLE = "COMMON_SEED_INCOMPATIBLE"
    FAMILY_SIGNATURE_INCOMPATIBLE = "FAMILY_SIGNATURE_INCOMPATIBLE"


class NWayRankingConfig(BaseModel):
    """Predeclared common-seed N-way policy-ranking plan."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = N_WAY_SCHEMA_VERSION
    experiment_id: str = Field(min_length=1)
    seed_ids: list[str] = Field(min_length=1)
    algorithms: list[str] = Field(min_length=2)
    checkpoint: str | None = None
    #: Reviewed per-algorithm extension: when comparing policies whose
    #: checkpoints necessarily differ (distinct trained actors), declare each
    #: algorithm's exact checkpoint here instead of the single ``checkpoint``.
    #: Mutually exclusive with ``checkpoint``; keys must equal ``algorithms``.
    checkpoint_by_algorithm: dict[str, str] | None = None
    metric_key: str = Field(min_length=1)
    objective: ObjectiveDirection = ObjectiveDirection.MAXIMISE
    pairing_key: Literal["random_seed"] = "random_seed"
    estimand: Literal["per_policy_mean_over_complete_common_random_seeds"] = (
        "per_policy_mean_over_complete_common_random_seeds"
    )
    tie_policy: Literal["absolute_mean_difference_within_predeclared_tolerance"] = (
        "absolute_mean_difference_within_predeclared_tolerance"
    )
    tie_tolerance: float = Field(default=1e-12, ge=0.0)
    confidence_level: float = Field(default=0.95, ge=0.80, le=0.99)
    bootstrap_repetitions: int = Field(
        default=10_000,
        ge=MINIMUM_BOOTSTRAP_REPETITIONS,
        le=MAXIMUM_BOOTSTRAP_REPETITIONS,
    )
    resampling_seed: int = Field(default=20_260_720, ge=0, le=2**63 - 2)
    expected_random_seeds: list[int] = Field(default_factory=list)
    minimum_complete_seeds: Literal[3] = MINIMUM_N_WAY_SUPPORT
    multiple_comparison_policy: Literal[
        "not_applicable_joint_descriptive_ranking_no_hypothesis_tests"
    ] = "not_applicable_joint_descriptive_ranking_no_hypothesis_tests"

    @field_validator("seed_ids", "algorithms")
    @classmethod
    def validate_unique_labels(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("identifiers must not be blank")
        if len(values) != len(set(values)):
            raise ValueError("identifiers must not contain duplicates")
        return sorted(values)

    @field_validator("expected_random_seeds")
    @classmethod
    def validate_expected_random_seeds(cls, values: list[int]) -> list[int]:
        if any(value < 0 for value in values):
            raise ValueError("expected_random_seeds values must be non-negative")
        if len(values) != len(set(values)):
            raise ValueError("expected_random_seeds must not contain duplicates")
        return sorted(values)

    @model_validator(mode="after")
    def validate_finite_tolerance(self) -> NWayRankingConfig:
        if not math.isfinite(self.tie_tolerance):
            raise ValueError("tie_tolerance must be finite")
        if self.checkpoint_by_algorithm is not None:
            if self.checkpoint is not None:
                raise ValueError("checkpoint and checkpoint_by_algorithm are mutually exclusive")
            if set(self.checkpoint_by_algorithm) != set(self.algorithms):
                raise ValueError("checkpoint_by_algorithm keys must equal the declared algorithms")
            for value in self.checkpoint_by_algorithm.values():
                if not value or len(value) > 300:
                    raise ValueError("each per-algorithm checkpoint must be 1-300 characters")
        return self

    def expected_checkpoint(self, algorithm: str) -> str | None:
        """Return the declared checkpoint for one algorithm."""

        if self.checkpoint_by_algorithm is not None:
            return self.checkpoint_by_algorithm.get(algorithm)
        return self.checkpoint

    def fingerprint(self) -> str:
        """Return the stable identity of the complete analysis plan."""

        return _fingerprint(self.model_dump(mode="json"))


class NWayExclusion(BaseModel):
    """One retained reason an input or pairing key did not enter a ranking."""

    model_config = ConfigDict(extra="forbid")

    code: NWayExclusionCode
    detail: str
    seed_id: str | None = None
    algorithm: str | None = None
    random_seed: int | None = None
    run_id: str | None = None


class NWayObservation(BaseModel):
    """One complete compatible random-seed row across every selected policy."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str
    random_seed: int
    values_by_algorithm: dict[str, float]
    run_ids_by_algorithm: dict[str, str]
    input_fingerprints_by_algorithm: dict[str, str]
    collection_fingerprints_by_algorithm: dict[str, str]


class NWayFamilyAudit(BaseModel):
    """Missingness, duplicates, compatibility, and support for one seed family."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str
    expected_random_seeds: list[int]
    complete_random_seeds: list[int]
    missing_expected_random_seeds: list[int]
    incomplete_random_seeds: list[int]
    incompatible_random_seeds: list[int]
    missing_random_seeds_by_algorithm: dict[str, list[int]]
    duplicate_random_seeds_by_algorithm: dict[str, list[int]]
    selected_collection_count: int
    complete_seed_count: int
    exclusion_count: int
    exclusions: list[NWayExclusion] = Field(default_factory=list)


class NWayBootstrapSummary(BaseModel):
    """Joint paired-seed bootstrap settings and availability."""

    model_config = ConfigDict(extra="forbid")

    status: NWayComponentStatus
    method: Literal["joint_paired_seed_percentile_bootstrap_v1"] = N_WAY_BOOTSTRAP_METHOD
    confidence_level: float
    repetitions: int
    seed: int
    reason: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class NWayPolicyRank(BaseModel):
    """One policy's winner-map score plus joint-bootstrap uncertainty."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str
    observation_count: int = Field(ge=1)
    mean: float
    standard_deviation: float = Field(ge=0.0)
    minimum: float
    maximum: float
    rank: int = Field(ge=1)
    regret: float = Field(ge=0.0)
    winner: bool
    mean_interval_lower: float | None = None
    mean_interval_upper: float | None = None
    top_rank_frequency: float | None = Field(default=None, ge=0.0, le=1.0)
    rank_interval_lower: int | None = Field(default=None, ge=1)
    rank_interval_upper: int | None = Field(default=None, ge=1)
    rank_frequencies: dict[str, float] = Field(default_factory=dict)
    uncertainty_reason: str | None = None


class NWayRankingEntry(BaseModel):
    """N-way ranking and complete audit for one scenario-seed family."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str
    status: NWayRankingStatus
    status_reason: str | None = None
    metric_key: str
    unit: str | None = None
    objective: ObjectiveDirection
    winner_algorithms: list[str]
    policy_ranks: list[NWayPolicyRank]
    observations: list[NWayObservation]
    audit: NWayFamilyAudit
    bootstrap: NWayBootstrapSummary
    compatibility_signature_fingerprint: str | None = None
    synthetic: bool | None = None


class NWayRankingStudy(BaseModel):
    """Versioned STA-02 study extending the descriptive winner map."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = N_WAY_SCHEMA_VERSION
    method_version: Literal["1.0"] = N_WAY_METHOD_VERSION
    study_id: str
    generated_at: datetime
    status: NWayRankingStatus
    config: NWayRankingConfig
    config_fingerprint: str
    winner_map: WinnerMapReport
    entries: list[NWayRankingEntry]
    input_collection_fingerprints: dict[str, str]
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return formatted strict JSON."""

        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)

    def canonical_json(self) -> str:
        """Return canonical JSON with generation timestamps normalised."""

        payload = self.model_dump(mode="json")
        payload["generated_at"] = "<normalised>"
        payload["winner_map"]["generated_at"] = "<normalised>"
        return _canonical(payload)

    def fingerprint(self) -> str:
        """Return the deterministic study fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class NWayRankingContract(BaseModel):
    """Published STA-02 evidence and method boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = N_WAY_SCHEMA_VERSION
    method_version: Literal["1.0"] = N_WAY_METHOD_VERSION
    evidence_boundary: str
    comparison_scope: str
    pairing_key: str
    estimand: str
    ranking_extension: str
    tie_policy: str
    bootstrap_method: str
    minimum_complete_seeds: int
    repetition_bounds: dict[str, int]
    multiple_comparison_policy: str
    compatibility_requirements: list[str]
    assumptions: list[str]
    unavailable_behavior: str
    unsupported: list[str]
    limitations: list[str]

    def fingerprint(self) -> str:
        """Return the deterministic method-contract fingerprint."""

        return _fingerprint(self.model_dump(mode="json"))


@dataclass(frozen=True)
class _Candidate:
    family_id: str
    collection: MetricCollection
    metric: MetricValue
    collection_fingerprint: str


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def n_way_ranking_contract() -> NWayRankingContract:
    """Return the complete bounded STA-02 v1 method contract."""

    return NWayRankingContract(
        evidence_boundary=(
            "Completed MetricCollection artifacts, a registered full-factorial experiment plan, "
            "and an explicit NWayRankingConfig only; no raw rows are read or metrics recomputed."
        ),
        comparison_scope=(
            "Policies are ranked independently within each declared scenario-seed family; "
            "scenario and policy effects are not conflated."
        ),
        pairing_key="exact random_seed with one endpoint for every selected policy",
        estimand="per-policy mean over the identical complete common-random-seed cohort",
        ranking_extension=(
            "The admitted cohort is delegated to WinnerMapReport for objective-aware rank, "
            "ties, winners, and regret."
        ),
        tie_policy=(
            "Absolute difference between policy means no greater than the predeclared tolerance; "
            "a numerical tie is not equivalence."
        ),
        bootstrap_method=N_WAY_BOOTSTRAP_METHOD,
        minimum_complete_seeds=MINIMUM_N_WAY_SUPPORT,
        repetition_bounds={
            "minimum": MINIMUM_BOOTSTRAP_REPETITIONS,
            "maximum": MAXIMUM_BOOTSTRAP_REPETITIONS,
        },
        multiple_comparison_policy=("not_applicable_joint_descriptive_ranking_no_hypothesis_tests"),
        compatibility_requirements=[
            "experiment, declared scenario family, selected policy, checkpoint (single, or "
            "declared per algorithm for distinct trained actors), and common seed",
            "metric collection and implementation versions, finite scalar status, and unit",
            "synthetic label and exact environment identity/version-or-commit",
            "immutable source fingerprint for every admitted endpoint",
            "equal energy/fairness/plugin/spatial semantic fingerprints when applicable",
        ],
        assumptions=_bootstrap_assumptions(),
        unavailable_behavior=(
            "Incomplete common seeds are excluded from every policy denominator; incompatible "
            "contracts receive no rank; support below three receives no uncertainty."
        ),
        unsupported=[
            "equivalence claims or ties inferred from confidence-interval overlap",
            "post-hoc pairwise hypothesis tests or multiplicity adjustment",
            "ranking scenario-policy combinations in one undifferentiated table",
            "imputation, automatic subgroup selection, or unpaired resampling",
            "equivalence (STA-03), regression gates (STA-04), and power analysis (STA-05)",
        ],
        limitations=_limitations(),
    )


def evaluate_n_way_ranking(
    collections: Sequence[MetricCollection],
    config: NWayRankingConfig,
    *,
    seed_aliases: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> NWayRankingStudy:
    """Evaluate a strict N-way policy ranking over complete common-seed rows."""

    source_collections = list(collections)
    input_snapshot = [collection.model_dump(mode="json") for collection in source_collections]
    aliases = dict(seed_aliases or {})
    counts = _counts(collection.run_id for collection in source_collections)
    duplicate_run_ids = {run_id for run_id, count in counts.items() if count > 1}
    input_fingerprints = _input_fingerprints(source_collections, counts)
    selected: dict[tuple[str, str, int], list[_Candidate]] = defaultdict(list)
    exclusions_by_family: dict[str, list[NWayExclusion]] = {
        seed_id: [] for seed_id in config.seed_ids
    }
    selected_count: dict[str, int] = defaultdict(int)
    expected_set = set(config.expected_random_seeds)

    for collection in sorted(source_collections, key=lambda item: item.run_id):
        if not collection.results:
            continue
        context = collection.results[0]
        family_id = aliases.get(context.seed_id, context.seed_id)
        if (
            context.experiment_id != config.experiment_id
            or family_id not in config.seed_ids
            or context.algorithm not in config.algorithms
            or context.checkpoint != config.expected_checkpoint(context.algorithm)
            or (expected_set and context.random_seed not in expected_set)
        ):
            continue
        selected_count[family_id] += 1
        if collection.run_id in duplicate_run_ids:
            exclusions_by_family[family_id].append(
                NWayExclusion(
                    code=NWayExclusionCode.DUPLICATE_RUN_ID,
                    detail="Every occurrence of this duplicate run ID was excluded.",
                    seed_id=family_id,
                    algorithm=context.algorithm,
                    random_seed=context.random_seed,
                    run_id=collection.run_id,
                )
            )
            continue
        candidate = _candidate_from_collection(
            collection,
            family_id,
            config,
            input_fingerprints[collection.run_id],
            exclusions_by_family[family_id],
        )
        if candidate is not None:
            selected[(family_id, context.algorithm, context.random_seed)].append(candidate)

    entries: list[NWayRankingEntry] = []
    admitted_collections: list[MetricCollection] = []
    global_warnings: list[str] = []
    for family_id in config.seed_ids:
        entry, family_admitted = _evaluate_family(
            family_id,
            selected,
            exclusions_by_family[family_id],
            selected_count[family_id],
            config,
        )
        entries.append(entry)
        admitted_collections.extend(family_admitted)

    winner_map = build_winner_map(
        admitted_collections,
        metric_key=config.metric_key,
        objective=config.objective,
        tie_tolerance=config.tie_tolerance,
        seed_aliases=aliases,
        clock=clock,
    )
    winner_entries = {entry.seed_id: entry for entry in winner_map.entries}
    reconciled: list[NWayRankingEntry] = []
    for entry in entries:
        descriptive = winner_entries.get(entry.seed_id)
        if descriptive is None or entry.status is NWayRankingStatus.INCOMPATIBLE:
            reconciled.append(entry)
            continue
        ranks = _attach_uncertainty(entry, descriptive.policy_scores, config)
        reconciled.append(
            entry.model_copy(
                update={
                    "winner_algorithms": descriptive.winner_algorithms,
                    "policy_ranks": ranks,
                    "unit": descriptive.unit,
                }
            )
        )
    entries = reconciled

    available_count = sum(entry.status is NWayRankingStatus.AVAILABLE for entry in entries)
    if available_count == len(entries):
        status = NWayRankingStatus.AVAILABLE
    elif available_count:
        status = NWayRankingStatus.PARTIAL
    elif any(entry.status is NWayRankingStatus.INCOMPATIBLE for entry in entries):
        status = NWayRankingStatus.INCOMPATIBLE
    else:
        status = NWayRankingStatus.INSUFFICIENT

    if not config.expected_random_seeds:
        global_warnings.append(
            "No expected random-seed set was supplied; observed selected seeds defined the audit."
        )
    excluded_count = sum(entry.audit.exclusion_count for entry in entries)
    if excluded_count:
        global_warnings.append(
            f"{excluded_count} endpoint/seed exclusions are retained in the family audits."
        )
    if winner_map.synthetic_only:
        global_warnings.append(
            "The rankings use labelled synthetic policy profiles and are not external validation."
        )
    config_fingerprint = config.fingerprint()
    source_sequence_fingerprint = _fingerprint(input_fingerprints)
    contract = n_way_ranking_contract()
    study = NWayRankingStudy(
        study_id=(
            "nway-"
            + _fingerprint(
                {
                    "config_fingerprint": config_fingerprint,
                    "source_sequence_fingerprint": source_sequence_fingerprint,
                }
            )[:16]
        ),
        generated_at=winner_map.generated_at,
        status=status,
        config=config,
        config_fingerprint=config_fingerprint,
        winner_map=winner_map,
        entries=entries,
        input_collection_fingerprints=input_fingerprints,
        provenance={
            "method_contract_fingerprint": contract.fingerprint(),
            "source_collection_sequence_fingerprint": source_sequence_fingerprint,
            "input_collection_count": len(source_collections),
            "admitted_complete_collection_count": len(admitted_collections),
            "available_family_count": available_count,
        },
        warnings=[*global_warnings, *winner_map.warnings],
        assumptions=contract.assumptions,
        limitations=contract.limitations,
    )
    if [collection.model_dump(mode="json") for collection in source_collections] != input_snapshot:
        raise RuntimeError("N-way ranking evaluation mutated an input MetricCollection")
    return study


def n_way_ranking_to_markdown(study: NWayRankingStudy) -> str:
    """Render a typed N-way study as deterministic Markdown."""

    config = study.config
    lines = [
        "# TrafficTwin N-Way Policy Ranking",
        "",
        f"- Study: `{_cell(study.study_id)}`",
        f"- Status: `{study.status.value}`",
        f"- Experiment: `{_cell(config.experiment_id)}`",
        f"- Metric/objective: `{_cell(config.metric_key)}` / `{config.objective.value}`",
        f"- Policies: {', '.join(f'`{_cell(item)}`' for item in config.algorithms)}",
        f"- Scenario families: {', '.join(f'`{_cell(item)}`' for item in config.seed_ids)}",
        f"- Pairing/estimand: `{config.pairing_key}` / `{config.estimand}`",
        f"- Tie tolerance: `{config.tie_tolerance:.12g}` (numerical tie, not equivalence)",
        f"- Bootstrap: `{N_WAY_BOOTSTRAP_METHOD}`, repetitions={config.bootstrap_repetitions}, "
        f"seed={config.resampling_seed}, confidence={config.confidence_level}",
        f"- Config fingerprint: `{study.config_fingerprint}`",
        "",
    ]
    for entry in study.entries:
        lines.extend(
            [
                f"## Scenario Family `{_cell(entry.seed_id)}`",
                "",
                f"- Status: `{entry.status.value}`",
                f"- Complete common seeds: {entry.audit.complete_seed_count}",
                f"- Expected seeds: {_number_list(entry.audit.expected_random_seeds)}",
                f"- Missing expected seeds: "
                f"{_number_list(entry.audit.missing_expected_random_seeds)}",
                f"- Incomplete seeds: {_number_list(entry.audit.incomplete_random_seeds)}",
                f"- Incompatible seeds: {_number_list(entry.audit.incompatible_random_seeds)}",
                f"- Exclusions: {entry.audit.exclusion_count}",
                "",
            ]
        )
        if entry.policy_ranks:
            lines.extend(
                [
                    "| Rank | Policy | n | Mean | Mean interval | Top-rank frequency | Regret |",
                    "|---:|---|---:|---:|---|---:|---:|",
                    *[
                        f"| {row.rank} | {_cell(row.algorithm)} | {row.observation_count} | "
                        f"{_number(row.mean)} | "
                        f"[{_number(row.mean_interval_lower)}, "
                        f"{_number(row.mean_interval_upper)}] | "
                        f"{_number(row.top_rank_frequency)} | {_number(row.regret)} |"
                        for row in entry.policy_ranks
                    ],
                ]
            )
        else:
            lines.append(f"No rank: {_cell(entry.status_reason or entry.status.value)}")
        lines.extend(["", "### Complete Observations", ""])
        if entry.observations:
            lines.extend(
                [
                    "| Random seed | Policy values |",
                    "|---:|---|",
                    *[
                        f"| {row.random_seed} | "
                        + "; ".join(
                            f"{_cell(policy)}={_number(value)}"
                            for policy, value in sorted(row.values_by_algorithm.items())
                        )
                        + " |"
                        for row in entry.observations
                    ],
                ]
            )
        else:
            lines.append("None.")
        lines.extend(["", "### Exclusions", ""])
        lines.extend(
            [
                f"- `{item.code.value}` (policy={_cell(item.algorithm or 'none')}, "
                f"seed={item.random_seed if item.random_seed is not None else 'none'}, "
                f"run={_cell(item.run_id or 'none')}): {_cell(item.detail)}"
                for item in entry.audit.exclusions
            ]
            or ["None."]
        )
        lines.append("")
    lines.extend(["## Assumptions And Limitations", ""])
    lines.extend(f"- {_cell(item)}" for item in [*study.assumptions, *study.limitations])
    lines.extend(["", f"Study fingerprint: `{study.fingerprint()}`", ""])
    return "\n".join(lines)


def n_way_ranking_to_csv(study: NWayRankingStudy) -> str:
    """Export ranks, complete observations, and exclusions in one audit-safe CSV."""

    columns = [
        "record_type",
        "study_id",
        "study_status",
        "seed_id",
        "family_status",
        "metric_key",
        "unit",
        "algorithm",
        "random_seed",
        "run_id",
        "value",
        "observation_count",
        "mean",
        "rank",
        "winner",
        "regret",
        "mean_interval_lower",
        "mean_interval_upper",
        "top_rank_frequency",
        "rank_interval_lower",
        "rank_interval_upper",
        "exclusion_code",
        "exclusion_detail",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for entry in study.entries:
        common = {
            "study_id": study.study_id,
            "study_status": study.status.value,
            "seed_id": entry.seed_id,
            "family_status": entry.status.value,
            "metric_key": entry.metric_key,
            "unit": entry.unit or "",
        }
        for row in entry.policy_ranks:
            writer.writerow(
                {
                    **common,
                    "record_type": "policy_rank",
                    "algorithm": row.algorithm,
                    "observation_count": row.observation_count,
                    "mean": row.mean,
                    "rank": row.rank,
                    "winner": str(row.winner).lower(),
                    "regret": row.regret,
                    "mean_interval_lower": _csv_value(row.mean_interval_lower),
                    "mean_interval_upper": _csv_value(row.mean_interval_upper),
                    "top_rank_frequency": _csv_value(row.top_rank_frequency),
                    "rank_interval_lower": _csv_value(row.rank_interval_lower),
                    "rank_interval_upper": _csv_value(row.rank_interval_upper),
                }
            )
        for observation in entry.observations:
            for algorithm in sorted(observation.values_by_algorithm):
                writer.writerow(
                    {
                        **common,
                        "record_type": "complete_observation",
                        "algorithm": algorithm,
                        "random_seed": observation.random_seed,
                        "run_id": observation.run_ids_by_algorithm[algorithm],
                        "value": observation.values_by_algorithm[algorithm],
                    }
                )
        for exclusion in entry.audit.exclusions:
            writer.writerow(
                {
                    **common,
                    "record_type": "exclusion",
                    "algorithm": exclusion.algorithm or "",
                    "random_seed": _csv_value(exclusion.random_seed),
                    "run_id": exclusion.run_id or "",
                    "exclusion_code": exclusion.code.value,
                    "exclusion_detail": exclusion.detail,
                }
            )
    return output.getvalue()


def _evaluate_family(
    family_id: str,
    selected: Mapping[tuple[str, str, int], list[_Candidate]],
    initial_exclusions: list[NWayExclusion],
    selected_collection_count: int,
    config: NWayRankingConfig,
) -> tuple[NWayRankingEntry, list[MetricCollection]]:
    exclusions = list(initial_exclusions)
    expected = set(config.expected_random_seeds)
    observed = {
        random_seed for selected_family, _, random_seed in selected if selected_family == family_id
    }
    audit_seed_set = expected or observed
    duplicates_by_algorithm: dict[str, list[int]] = {}
    unique: dict[tuple[str, int], _Candidate] = {}
    for algorithm in config.algorithms:
        duplicates: list[int] = []
        for random_seed in sorted(observed):
            rows = selected.get((family_id, algorithm, random_seed), [])
            if len(rows) > 1:
                duplicates.append(random_seed)
                exclusions.append(
                    NWayExclusion(
                        code=NWayExclusionCode.DUPLICATE_POLICY_SEED,
                        detail=(
                            "More than one eligible endpoint exists for this policy/random-seed "
                            "key; TrafficTwin did not choose by input order."
                        ),
                        seed_id=family_id,
                        algorithm=algorithm,
                        random_seed=random_seed,
                    )
                )
            elif len(rows) == 1:
                unique[(algorithm, random_seed)] = rows[0]
        duplicates_by_algorithm[algorithm] = duplicates

    missing_by_algorithm = {
        algorithm: sorted(
            random_seed for random_seed in audit_seed_set if (algorithm, random_seed) not in unique
        )
        for algorithm in config.algorithms
    }
    incomplete = sorted(
        random_seed
        for random_seed in audit_seed_set
        if any((algorithm, random_seed) not in unique for algorithm in config.algorithms)
    )
    for random_seed in incomplete:
        exclusions.append(
            NWayExclusion(
                code=NWayExclusionCode.INCOMPLETE_COMMON_SEED,
                detail=(
                    "At least one selected policy endpoint is absent, unavailable, invalid, or "
                    "duplicate; this seed entered no policy denominator."
                ),
                seed_id=family_id,
                random_seed=random_seed,
            )
        )

    compatible_candidates: dict[int, list[_Candidate]] = {}
    incompatible: list[int] = []
    signatures: list[dict[str, object]] = []
    for random_seed in sorted(audit_seed_set - set(incomplete)):
        rows = [unique[(algorithm, random_seed)] for algorithm in config.algorithms]
        row_signatures = [_compatibility_signature(row, config.metric_key) for row in rows]
        if len({_canonical(signature) for signature in row_signatures}) != 1:
            incompatible.append(random_seed)
            exclusions.append(
                NWayExclusion(
                    code=NWayExclusionCode.COMMON_SEED_INCOMPATIBLE,
                    detail=(
                        "Selected policy endpoints differ in metric, unit, synthetic, "
                        "environment, or semantic compatibility signature."
                    ),
                    seed_id=family_id,
                    random_seed=random_seed,
                )
            )
            continue
        compatible_candidates[random_seed] = rows
        signatures.append(row_signatures[0])

    signature_payloads = {_canonical(signature) for signature in signatures}
    signature_fingerprint: str | None = None
    family_incompatible = len(signature_payloads) > 1
    if family_incompatible:
        exclusions.append(
            NWayExclusion(
                code=NWayExclusionCode.FAMILY_SIGNATURE_INCOMPATIBLE,
                detail=(
                    "Complete random-seed rows do not share one metric/environment/semantic "
                    "signature; no subgroup was selected or ranked."
                ),
                seed_id=family_id,
            )
        )
    elif signature_payloads:
        signature_fingerprint = hashlib.sha256(
            next(iter(signature_payloads)).encode("utf-8")
        ).hexdigest()

    observations: list[NWayObservation] = []
    admitted: list[MetricCollection] = []
    for random_seed, rows in sorted(compatible_candidates.items()):
        observations.append(
            NWayObservation(
                seed_id=family_id,
                random_seed=random_seed,
                values_by_algorithm={row.metric.algorithm: float(row.metric.value) for row in rows},
                run_ids_by_algorithm={row.metric.algorithm: row.collection.run_id for row in rows},
                input_fingerprints_by_algorithm={
                    row.metric.algorithm: str(row.collection.input_fingerprint) for row in rows
                },
                collection_fingerprints_by_algorithm={
                    row.metric.algorithm: row.collection_fingerprint for row in rows
                },
            )
        )
        if not family_incompatible:
            admitted.extend(row.collection for row in rows)

    missing_expected = sorted(expected - {row.random_seed for row in observations})
    audit = NWayFamilyAudit(
        seed_id=family_id,
        expected_random_seeds=sorted(expected),
        complete_random_seeds=[row.random_seed for row in observations],
        missing_expected_random_seeds=missing_expected,
        incomplete_random_seeds=incomplete,
        incompatible_random_seeds=incompatible,
        missing_random_seeds_by_algorithm=missing_by_algorithm,
        duplicate_random_seeds_by_algorithm=duplicates_by_algorithm,
        selected_collection_count=selected_collection_count,
        complete_seed_count=len(observations),
        exclusion_count=len(exclusions),
        exclusions=sorted(exclusions, key=_exclusion_sort_key),
    )
    if family_incompatible:
        status = NWayRankingStatus.INCOMPATIBLE
        reason = "Complete rows have incompatible study signatures; this family was not ranked."
    elif len(observations) < config.minimum_complete_seeds:
        status = NWayRankingStatus.INSUFFICIENT
        reason = (
            f"At least {config.minimum_complete_seeds} complete compatible common seeds are "
            f"required; {len(observations)} were admitted."
        )
    else:
        status = NWayRankingStatus.AVAILABLE
        reason = None
    signature = signatures[0] if signatures and not family_incompatible else None
    family_seed = _family_resampling_seed(config.resampling_seed, family_id)
    return (
        NWayRankingEntry(
            seed_id=family_id,
            status=status,
            status_reason=reason,
            metric_key=config.metric_key,
            objective=config.objective,
            winner_algorithms=[],
            policy_ranks=[],
            observations=observations,
            audit=audit,
            bootstrap=NWayBootstrapSummary(
                status=(
                    NWayComponentStatus.AVAILABLE
                    if status is NWayRankingStatus.AVAILABLE
                    else NWayComponentStatus.UNAVAILABLE
                ),
                confidence_level=config.confidence_level,
                repetitions=config.bootstrap_repetitions,
                seed=family_seed,
                reason=reason,
                assumptions=_bootstrap_assumptions(),
            ),
            compatibility_signature_fingerprint=signature_fingerprint,
            synthetic=bool(signature["synthetic"]) if signature is not None else None,
        ),
        admitted,
    )


def _attach_uncertainty(
    entry: NWayRankingEntry,
    descriptive_scores: Sequence[PolicyScore],
    config: NWayRankingConfig,
) -> list[NWayPolicyRank]:
    score_by_algorithm = {score.algorithm: score for score in descriptive_scores}
    uncertainty: dict[str, tuple[float, float, float, int, int, dict[str, float]]] = {}
    if entry.status is NWayRankingStatus.AVAILABLE:
        uncertainty = _joint_bootstrap(entry.observations, config, entry.bootstrap.seed)
    ranks: list[NWayPolicyRank] = []
    reason = entry.status_reason if entry.status is not NWayRankingStatus.AVAILABLE else None
    for algorithm in config.algorithms:
        score = score_by_algorithm.get(algorithm)
        if score is None:
            continue
        interval = uncertainty.get(algorithm)
        ranks.append(
            NWayPolicyRank(
                algorithm=algorithm,
                observation_count=score.observation_count,
                mean=score.mean,
                standard_deviation=score.standard_deviation,
                minimum=score.minimum,
                maximum=score.maximum,
                rank=score.rank,
                regret=score.regret,
                winner=score.winner,
                mean_interval_lower=interval[0] if interval else None,
                mean_interval_upper=interval[1] if interval else None,
                top_rank_frequency=interval[2] if interval else None,
                rank_interval_lower=interval[3] if interval else None,
                rank_interval_upper=interval[4] if interval else None,
                rank_frequencies=interval[5] if interval else {},
                uncertainty_reason=reason,
            )
        )
    return sorted(ranks, key=lambda row: (row.rank, row.algorithm))


def _joint_bootstrap(
    observations: Sequence[NWayObservation],
    config: NWayRankingConfig,
    seed: int,
) -> dict[str, tuple[float, float, float, int, int, dict[str, float]]]:
    rng = random.Random(seed)  # noqa: S311 - recorded deterministic scientific resampling
    n = len(observations)
    means: dict[str, list[float]] = {algorithm: [] for algorithm in config.algorithms}
    ranks: dict[str, list[int]] = {algorithm: [] for algorithm in config.algorithms}
    for _ in range(config.bootstrap_repetitions):
        sample = [observations[rng.randrange(n)] for _ in range(n)]
        replicate_means = {
            algorithm: sum(row.values_by_algorithm[algorithm] for row in sample) / n
            for algorithm in config.algorithms
        }
        replicate_ranks = _rank_values(replicate_means, config.objective, config.tie_tolerance)
        for algorithm in config.algorithms:
            means[algorithm].append(replicate_means[algorithm])
            ranks[algorithm].append(replicate_ranks[algorithm])
    alpha = 1.0 - config.confidence_level
    output: dict[str, tuple[float, float, float, int, int, dict[str, float]]] = {}
    for algorithm in config.algorithms:
        lower = percentile_linear(means[algorithm], alpha / 2.0)
        upper = percentile_linear(means[algorithm], 1.0 - alpha / 2.0)
        rank_lower = percentile_linear(ranks[algorithm], alpha / 2.0)
        rank_upper = percentile_linear(ranks[algorithm], 1.0 - alpha / 2.0)
        assert lower is not None and upper is not None
        assert rank_lower is not None and rank_upper is not None
        rank_counts = _counts(str(rank) for rank in ranks[algorithm])
        output[algorithm] = (
            stable_float(lower),
            stable_float(upper),
            ranks[algorithm].count(1) / config.bootstrap_repetitions,
            max(1, math.floor(rank_lower)),
            min(len(config.algorithms), math.ceil(rank_upper)),
            {
                rank: count / config.bootstrap_repetitions
                for rank, count in sorted(rank_counts.items(), key=lambda item: int(item[0]))
            },
        )
    return output


def _candidate_from_collection(
    collection: MetricCollection,
    family_id: str,
    config: NWayRankingConfig,
    collection_fingerprint: str,
    exclusions: list[NWayExclusion],
) -> _Candidate | None:
    context = collection.results[0]
    metric = collection.by_key().get(config.metric_key)
    if metric is None:
        _exclude_candidate(
            exclusions,
            NWayExclusionCode.METRIC_MISSING,
            collection,
            family_id,
            context,
            f"Metric {config.metric_key!r} is absent from the collection.",
        )
        return None
    if metric.status is not MetricStatus.AVAILABLE:
        _exclude_candidate(
            exclusions,
            NWayExclusionCode.METRIC_UNAVAILABLE,
            collection,
            family_id,
            context,
            f"Metric status is {metric.status.value}; unavailable/partial evidence is not zero.",
        )
        return None
    if not _is_finite_scalar(metric.value):
        _exclude_candidate(
            exclusions,
            NWayExclusionCode.METRIC_NOT_FINITE_SCALAR,
            collection,
            family_id,
            context,
            "The selected metric value is not one finite numeric scalar.",
        )
        return None
    expected_context = (
        collection.run_id,
        config.experiment_id,
        context.seed_id,
        context.algorithm,
        config.expected_checkpoint(context.algorithm),
        context.random_seed,
    )
    actual_context = (
        metric.run_id,
        metric.experiment_id,
        metric.seed_id,
        metric.algorithm,
        metric.checkpoint,
        metric.random_seed,
    )
    if actual_context != expected_context:
        _exclude_candidate(
            exclusions,
            NWayExclusionCode.METRIC_CONTEXT_MISMATCH,
            collection,
            family_id,
            context,
            "The selected metric context does not match its collection and analysis plan.",
        )
        return None
    if not collection.input_fingerprint:
        _exclude_candidate(
            exclusions,
            NWayExclusionCode.SOURCE_FINGERPRINT_MISSING,
            collection,
            family_id,
            context,
            "The collection has no immutable source input fingerprint.",
        )
        return None
    if not metric.environment or not (metric.environment_version or metric.environment_commit):
        _exclude_candidate(
            exclusions,
            NWayExclusionCode.ENVIRONMENT_PROVENANCE_UNRESOLVED,
            collection,
            family_id,
            context,
            "Environment identity requires a name and version or commit.",
        )
        return None
    missing_contracts = _missing_semantic_contracts(metric, config.metric_key)
    if missing_contracts:
        _exclude_candidate(
            exclusions,
            NWayExclusionCode.SEMANTIC_CONTRACT_UNRESOLVED,
            collection,
            family_id,
            context,
            "Missing required semantic fingerprints: " + ", ".join(missing_contracts),
        )
        return None
    return _Candidate(family_id, collection, metric, collection_fingerprint)


def _exclude_candidate(
    exclusions: list[NWayExclusion],
    code: NWayExclusionCode,
    collection: MetricCollection,
    family_id: str,
    context: MetricValue,
    detail: str,
) -> None:
    exclusions.append(
        NWayExclusion(
            code=code,
            detail=detail,
            seed_id=family_id,
            algorithm=context.algorithm,
            random_seed=context.random_seed,
            run_id=collection.run_id,
        )
    )
    return None


def _compatibility_signature(candidate: _Candidate, metric_key: str) -> dict[str, object]:
    metric = candidate.metric
    return {
        "metric_key": metric_key,
        "metric_collection_version": candidate.collection.metric_version,
        "metric_implementation_version": metric.implementation_version,
        "unit": metric.unit,
        "synthetic": metric.synthetic,
        "environment": metric.environment,
        "environment_version": metric.environment_version,
        "environment_commit": metric.environment_commit,
        "semantic_contract": {
            key: str(metric.metadata[key])
            for key in _semantic_contract_keys(metric_key)
            if isinstance(metric.metadata.get(key), str)
        },
    }


def _semantic_contract_keys(metric_key: str) -> list[str]:
    if metric_key.startswith(("task.energy.", "task.energy_delay_product.")):
        return ["energy_contract_fingerprint"]
    if metric_key.startswith("plugin."):
        return ["plugin_contract_fingerprint"]
    if metric_key.startswith("fairness.") or metric_key in {
        "task.completion.rate_by_vehicle_tier",
        "infra.load_balance.jain_capacity_normalised",
    }:
        return ["fairness_policy_fingerprint", "group_set_fingerprint"]
    if "target_rsu" in metric_key:
        return ["task_rsu_target_contract_fingerprint", "group_set_fingerprint"]
    if "vehicle_grid" in metric_key:
        return ["vehicle_spatial_grid_contract_fingerprint", "group_set_fingerprint"]
    return []


def _missing_semantic_contracts(metric: MetricValue, metric_key: str) -> list[str]:
    return [
        key
        for key in _semantic_contract_keys(metric_key)
        if not isinstance(metric.metadata.get(key), str) or not metric.metadata.get(key)
    ]


def _rank_values(
    values: Mapping[str, float],
    objective: ObjectiveDirection,
    tie_tolerance: float,
) -> dict[str, int]:
    ordered = sorted(
        values,
        key=lambda algorithm: (
            -values[algorithm] if objective is ObjectiveDirection.MAXIMISE else values[algorithm],
            algorithm,
        ),
    )
    result: dict[str, int] = {}
    last_value: float | None = None
    last_rank = 0
    for position, algorithm in enumerate(ordered, start=1):
        value = values[algorithm]
        if last_value is None or abs(value - last_value) > tie_tolerance:
            last_rank = position
            last_value = value
        result[algorithm] = last_rank
    return result


def _family_resampling_seed(seed: int, family_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{family_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def _input_fingerprints(
    collections: Sequence[MetricCollection], counts: Mapping[str, int]
) -> dict[str, str]:
    output: dict[str, str] = {}
    occurrences: dict[str, int] = defaultdict(int)
    fingerprint_rows = sorted(
        (collection.run_id, metric_collection_fingerprint(collection)) for collection in collections
    )
    for run_id, fingerprint in fingerprint_rows:
        occurrences[run_id] += 1
        key = f"{run_id}#{occurrences[run_id]}" if counts[run_id] > 1 else run_id
        output[key] = fingerprint
    return output


def _bootstrap_assumptions() -> list[str]:
    return [
        "Every admitted random-seed row contains one compatible endpoint for every policy.",
        "Complete common-seed rows are resampled jointly with replacement.",
        "The admitted seeds represent the empirical paired sample for the predeclared plan.",
        "Mean and rank intervals are descriptive bootstrap uncertainty, not external guarantees.",
        "No hypothesis test is performed and no multiplicity-adjusted claim is inferred.",
    ]


def _limitations() -> list[str]:
    return [
        "A numerical tie within tolerance is not statistical or practical equivalence.",
        "Overlapping or non-overlapping intervals are not an automatic decision rule.",
        "Top-rank frequency is resampling stability, not a universal probability of superiority.",
        "Rankings do not establish causality, practical importance, or external validity.",
        "Synthetic studies provide software and method evidence, not real-world validation.",
    ]


def _exclusion_sort_key(item: NWayExclusion) -> tuple[int, str, str, str]:
    return (
        item.random_seed if item.random_seed is not None else -1,
        item.algorithm or "",
        item.code.value,
        item.run_id or "",
    )


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return counts


def _is_finite_scalar(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.12g}"


def _number_list(values: Sequence[int]) -> str:
    return ", ".join(str(value) for value in values) if values else "none"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _csv_value(value: object | None) -> object:
    return "" if value is None else value


def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
