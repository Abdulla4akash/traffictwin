"""Deterministic common-seed paired statistical studies for STA-01."""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.metrics.results import JsonScalar, MetricCollection, MetricStatus, MetricValue
from traffictwin.metrics.statistics import (
    arithmetic_mean,
    percentile_linear,
    sample_standard_deviation,
)

STUDY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
METHOD_VERSION: Literal["1.0"] = "1.0"
BOOTSTRAP_METHOD: Literal["paired_percentile_bootstrap_mean_v1"] = (
    "paired_percentile_bootstrap_mean_v1"
)
RANDOMISATION_METHOD: Literal["two_sided_paired_sign_flip_mean_v1"] = (
    "two_sided_paired_sign_flip_mean_v1"
)
EXACT_SIGN_FLIP_MAX_PAIRS = 16
MINIMUM_PAIRED_SUPPORT: Literal[3] = 3
MINIMUM_RESAMPLING_REPETITIONS = 1_000
MAXIMUM_RESAMPLING_REPETITIONS = 100_000


class StatisticalStudyStatus(StrEnum):
    """Availability of the complete predeclared study."""

    AVAILABLE = "available"
    INSUFFICIENT = "insufficient"
    INCOMPATIBLE = "incompatible"


class StatisticalComponentStatus(StrEnum):
    """Availability of one inferential study component."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class RandomisationMode(StrEnum):
    """How the paired sign-flip reference distribution was evaluated."""

    EXACT = "exact_enumeration"
    MONTE_CARLO = "seeded_monte_carlo"
    NOT_RUN = "not_run"


class PairRole(StrEnum):
    """Role of an input or pair exclusion."""

    BASELINE = "baseline"
    VARIATION = "variation"
    PAIR = "pair"
    STUDY = "study"


class PairExclusionCode(StrEnum):
    """Stable reasons an input cannot enter the paired estimand."""

    EMPTY_COLLECTION = "EMPTY_COLLECTION"
    DUPLICATE_RUN_ID = "DUPLICATE_RUN_ID"
    RANDOM_SEED_NOT_PREDECLARED = "RANDOM_SEED_NOT_PREDECLARED"
    METRIC_MISSING = "METRIC_MISSING"
    METRIC_UNAVAILABLE = "METRIC_UNAVAILABLE"
    METRIC_NOT_FINITE_SCALAR = "METRIC_NOT_FINITE_SCALAR"
    METRIC_CONTEXT_MISMATCH = "METRIC_CONTEXT_MISMATCH"
    SOURCE_FINGERPRINT_MISSING = "SOURCE_FINGERPRINT_MISSING"
    ENVIRONMENT_PROVENANCE_UNRESOLVED = "ENVIRONMENT_PROVENANCE_UNRESOLVED"
    SEMANTIC_CONTRACT_UNRESOLVED = "SEMANTIC_CONTRACT_UNRESOLVED"
    DUPLICATE_PAIRING_KEY = "DUPLICATE_PAIRING_KEY"
    PAIR_INCOMPATIBLE = "PAIR_INCOMPATIBLE"
    STUDY_SIGNATURE_INCOMPATIBLE = "STUDY_SIGNATURE_INCOMPATIBLE"


class PairInterpretation(StrEnum):
    """Objective-aware descriptive direction for a variation-baseline difference."""

    FAVOURS_VARIATION = "favours_variation"
    FAVOURS_BASELINE = "favours_baseline"
    TIE = "tie"


class PairedStudyConfig(BaseModel):
    """Strict predeclared analysis plan for one common-seed comparison."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = STUDY_SCHEMA_VERSION
    experiment_id: str = Field(min_length=1)
    baseline_seed_id: str = Field(min_length=1)
    variation_seed_id: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)
    checkpoint: str | None = None
    metric_key: str = Field(min_length=1)
    objective: ObjectiveDirection = ObjectiveDirection.MAXIMISE
    pairing_key: Literal["random_seed"] = "random_seed"
    estimand: Literal["mean_paired_difference_variation_minus_baseline"] = (
        "mean_paired_difference_variation_minus_baseline"
    )
    alternative: Literal["two_sided"] = "two_sided"
    confidence_level: float = Field(default=0.95, ge=0.80, le=0.99)
    bootstrap_repetitions: int = Field(
        default=10_000,
        ge=MINIMUM_RESAMPLING_REPETITIONS,
        le=MAXIMUM_RESAMPLING_REPETITIONS,
    )
    randomisation_repetitions: int = Field(
        default=10_000,
        ge=MINIMUM_RESAMPLING_REPETITIONS,
        le=MAXIMUM_RESAMPLING_REPETITIONS,
    )
    resampling_seed: int = Field(default=20_260_720, ge=0, le=2**63 - 2)
    expected_random_seeds: list[int] = Field(default_factory=list)
    minimum_pairs: Literal[3] = MINIMUM_PAIRED_SUPPORT
    multiple_comparison_policy: Literal["not_applicable_single_predeclared_comparison"] = (
        "not_applicable_single_predeclared_comparison"
    )

    @field_validator("expected_random_seeds")
    @classmethod
    def validate_expected_random_seeds(cls, values: list[int]) -> list[int]:
        if any(value < 0 for value in values):
            raise ValueError("expected_random_seeds values must be non-negative")
        if len(values) != len(set(values)):
            raise ValueError("expected_random_seeds must not contain duplicates")
        return sorted(values)

    @model_validator(mode="after")
    def validate_conditions(self) -> PairedStudyConfig:
        if self.baseline_seed_id == self.variation_seed_id:
            raise ValueError("baseline_seed_id and variation_seed_id must differ")
        return self

    def fingerprint(self) -> str:
        """Return the stable identity of the complete analysis plan."""

        return _fingerprint(self.model_dump(mode="json"))


class PairingExclusion(BaseModel):
    """One retained reason an input or pairing key did not enter the study."""

    model_config = ConfigDict(extra="forbid")

    role: PairRole
    code: PairExclusionCode
    detail: str
    run_id: str | None = None
    random_seed: int | None = None


class PairedStudyObservation(BaseModel):
    """One compatible common-seed observation retained by the estimand."""

    model_config = ConfigDict(extra="forbid")

    random_seed: int
    baseline_run_id: str
    variation_run_id: str
    baseline_value: float
    variation_value: float
    paired_difference: float
    interpretation: PairInterpretation
    baseline_input_fingerprint: str
    variation_input_fingerprint: str
    baseline_collection_fingerprint: str
    variation_collection_fingerprint: str


class CommonSeedPairingAudit(BaseModel):
    """Complete pairing and exclusion inventory for one study."""

    model_config = ConfigDict(extra="forbid")

    pairing_key: Literal["random_seed"] = "random_seed"
    expected_random_seeds: list[int]
    eligible_random_seeds: list[int]
    missing_expected_random_seeds: list[int]
    unmatched_baseline_random_seeds: list[int]
    unmatched_variation_random_seeds: list[int]
    duplicate_baseline_random_seeds: list[int]
    duplicate_variation_random_seeds: list[int]
    input_collection_count: int
    selected_collection_count: int
    eligible_pair_count: int
    exclusion_count: int
    exclusions: list[PairingExclusion] = Field(default_factory=list)


class PairedEstimate(BaseModel):
    """Primary original-unit paired estimand and descriptive sample values."""

    model_config = ConfigDict(extra="forbid")

    status: StatisticalComponentStatus
    n: int
    unit: str | None = None
    mean_paired_difference: float | None = None
    sample_sd_paired_difference: float | None = None
    standard_error: float | None = None
    minimum_paired_difference: float | None = None
    maximum_paired_difference: float | None = None
    interpretation: PairInterpretation | None = None
    reason: str | None = None


class PairedBootstrapInterval(BaseModel):
    """Deterministic paired percentile-bootstrap interval."""

    model_config = ConfigDict(extra="forbid")

    status: StatisticalComponentStatus
    method: Literal["paired_percentile_bootstrap_mean_v1"] = BOOTSTRAP_METHOD
    confidence_level: float
    repetitions: int
    seed: int
    lower: float | None = None
    upper: float | None = None
    reason: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class PairedRandomisationTest(BaseModel):
    """Two-sided paired sign-flip randomisation test result."""

    model_config = ConfigDict(extra="forbid")

    status: StatisticalComponentStatus
    method: Literal["two_sided_paired_sign_flip_mean_v1"] = RANDOMISATION_METHOD
    alternative: Literal["two_sided"] = "two_sided"
    mode: RandomisationMode
    observed_statistic: float | None = None
    p_value: float | None = None
    evaluated_assignments: int = 0
    requested_monte_carlo_repetitions: int
    seed: int
    reason: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class PairedEffectSizes(BaseModel):
    """Paired effect-size inventory with explicit unavailable states."""

    model_config = ConfigDict(extra="forbid")

    status: StatisticalComponentStatus
    mean_paired_difference: float | None = None
    cohen_dz: float | None = None
    cohen_dz_reason: str | None = None
    matched_pairs_rank_biserial: float | None = None
    rank_biserial_reason: str | None = None
    variation_favourable_count: int = 0
    baseline_favourable_count: int = 0
    tie_count: int = 0
    primary_effect: Literal["mean_paired_difference"] = "mean_paired_difference"
    cliffs_delta: Literal["not_calculated_for_paired_primary_design"] = (
        "not_calculated_for_paired_primary_design"
    )
    reason: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class StatisticalStudy(BaseModel):
    """Versioned STA-01 artifact over compatible common-seed metric replicates."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = STUDY_SCHEMA_VERSION
    method_version: Literal["1.0"] = METHOD_VERSION
    study_id: str
    generated_at: datetime
    status: StatisticalStudyStatus
    synthetic: bool | None
    config: PairedStudyConfig
    config_fingerprint: str
    metric_unit: str | None = None
    observations: list[PairedStudyObservation]
    pairing_audit: CommonSeedPairingAudit
    estimate: PairedEstimate
    bootstrap_interval: PairedBootstrapInterval
    randomisation_test: PairedRandomisationTest
    effect_sizes: PairedEffectSizes
    input_collection_fingerprints: dict[str, str]
    compatibility_signature_fingerprint: str | None = None
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return formatted strict JSON."""

        return json.dumps(
            self.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )

    def canonical_json(self) -> str:
        """Return canonical JSON with only the generation timestamp normalised."""

        payload = self.model_dump(mode="json")
        payload["generated_at"] = "<normalised>"
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Return the deterministic study fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class StatisticalStudyContract(BaseModel):
    """Published STA-01 method and evidence boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = STUDY_SCHEMA_VERSION
    method_version: Literal["1.0"] = METHOD_VERSION
    evidence_boundary: str
    pairing_key: str
    estimand: str
    bootstrap_method: str
    randomisation_method: str
    exact_sign_flip_max_pairs: int
    minimum_pairs: int
    repetition_bounds: dict[str, int]
    primary_effect: str
    secondary_effects: list[str]
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
    role: PairRole
    collection: MetricCollection
    metric: MetricValue
    collection_fingerprint: str

    @property
    def random_seed(self) -> int:
        return self.metric.random_seed


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def statistical_study_contract() -> StatisticalStudyContract:
    """Return the complete bounded STA-01 v1 method contract."""

    return StatisticalStudyContract(
        evidence_boundary=(
            "Completed MetricCollection artifacts and an explicit PairedStudyConfig only; the "
            "service does not read raw rows, recompute metrics, or mutate registry records."
        ),
        pairing_key="exact random_seed within one experiment/algorithm/checkpoint",
        estimand="mean of paired variation-minus-baseline scalar metric differences",
        bootstrap_method=BOOTSTRAP_METHOD,
        randomisation_method=RANDOMISATION_METHOD,
        exact_sign_flip_max_pairs=EXACT_SIGN_FLIP_MAX_PAIRS,
        minimum_pairs=MINIMUM_PAIRED_SUPPORT,
        repetition_bounds={
            "minimum": MINIMUM_RESAMPLING_REPETITIONS,
            "maximum": MAXIMUM_RESAMPLING_REPETITIONS,
        },
        primary_effect="original-unit mean paired difference",
        secondary_effects=[
            "Cohen's dz when paired-difference sample SD is non-zero",
            "matched-pairs rank-biserial correlation over non-zero absolute ranks",
            "Cliff's delta is not automatically calculated for this paired design",
        ],
        compatibility_requirements=[
            "experiment, algorithm, checkpoint, and common random-seed plan",
            "metric collection version, metric implementation version, scalar status, and unit",
            "synthetic label and exact environment identity/version-or-commit",
            "source input fingerprint for every retained endpoint",
            "equal energy/fairness/plugin/spatial semantic-contract fingerprints when applicable",
        ],
        assumptions=[
            "Pairs are the predeclared common-seed experimental units.",
            "The bootstrap treats admitted pairs as the empirical paired sample.",
            "The sign-flip null requires exchangeable signs of paired differences under zero "
            "effect.",
            "A single predeclared comparison is evaluated; no multiplicity adjustment applies.",
        ],
        unavailable_behavior=(
            "Thin, missing, unavailable, duplicate, unmatched, or incompatible evidence remains "
            "explicit and is never replaced by zero or silently selected."
        ),
        unsupported=[
            "N-way comparison or ranking (STA-02)",
            "equivalence testing (STA-03)",
            "regression gates (STA-04)",
            "power analysis (STA-05)",
            "unpaired primary inference or automatic Cliff's delta",
        ],
        limitations=[
            "A confidence interval and p-value do not establish practical importance or cause.",
            "Non-significance is not evidence of equivalence.",
            "Synthetic studies provide software/method evidence, not external validation.",
            "Method validity still depends on the declared experimental design and assumptions.",
        ],
    )


def evaluate_paired_statistical_study(
    collections: Sequence[MetricCollection],
    config: PairedStudyConfig,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> StatisticalStudy:
    """Evaluate the predeclared deterministic STA-01 study."""

    source_collections = list(collections)
    input_snapshot = [collection.model_dump(mode="json") for collection in source_collections]
    exclusions: list[PairingExclusion] = []
    duplicate_run_ids = sorted(
        run_id
        for run_id, count in _counts(collection.run_id for collection in source_collections).items()
        if count > 1
    )
    for run_id in duplicate_run_ids:
        exclusions.append(
            PairingExclusion(
                role=PairRole.STUDY,
                code=PairExclusionCode.DUPLICATE_RUN_ID,
                run_id=run_id,
                detail="The input sequence contains more than one collection for this run ID.",
            )
        )

    fingerprint_rows = sorted(
        (collection.run_id, metric_collection_fingerprint(collection))
        for collection in source_collections
    )
    input_collection_fingerprints: dict[str, str] = {}
    fingerprint_occurrences: dict[str, int] = defaultdict(int)
    run_id_counts = _counts(collection.run_id for collection in source_collections)
    for run_id, fingerprint in fingerprint_rows:
        fingerprint_occurrences[run_id] += 1
        key = f"{run_id}#{fingerprint_occurrences[run_id]}" if run_id_counts[run_id] > 1 else run_id
        input_collection_fingerprints[key] = fingerprint
    unique_collection_fingerprints = {
        run_id: fingerprint
        for run_id, fingerprint in fingerprint_rows
        if run_id_counts[run_id] == 1
    }
    candidates: dict[PairRole, list[_Candidate]] = {
        PairRole.BASELINE: [],
        PairRole.VARIATION: [],
    }
    selected_count = 0
    expected_set = set(config.expected_random_seeds)
    for collection in sorted(source_collections, key=lambda item: item.run_id):
        if collection.run_id in duplicate_run_ids:
            continue
        if not collection.results:
            exclusions.append(
                PairingExclusion(
                    role=PairRole.STUDY,
                    code=PairExclusionCode.EMPTY_COLLECTION,
                    run_id=collection.run_id,
                    detail="The metric collection has no run context or metric results.",
                )
            )
            continue
        context = collection.results[0]
        role = _selected_role(context, config)
        if role is None:
            continue
        selected_count += 1
        if expected_set and context.random_seed not in expected_set:
            exclusions.append(
                PairingExclusion(
                    role=role,
                    code=PairExclusionCode.RANDOM_SEED_NOT_PREDECLARED,
                    run_id=collection.run_id,
                    random_seed=context.random_seed,
                    detail="The run's random seed is outside the predeclared common-seed set.",
                )
            )
            continue
        candidate = _candidate_from_collection(
            collection,
            role,
            config,
            unique_collection_fingerprints[collection.run_id],
            exclusions,
        )
        if candidate is not None:
            candidates[role].append(candidate)

    by_role_seed = {role: _group_candidates(rows) for role, rows in candidates.items()}
    duplicate_by_role = {
        role: sorted(seed for seed, rows in groups.items() if len(rows) > 1)
        for role, groups in by_role_seed.items()
    }
    for role, duplicate_seeds in duplicate_by_role.items():
        for seed in duplicate_seeds:
            exclusions.append(
                PairingExclusion(
                    role=role,
                    code=PairExclusionCode.DUPLICATE_PAIRING_KEY,
                    random_seed=seed,
                    detail=(
                        f"More than one eligible {role.value} run uses random seed {seed}; "
                        "TrafficTwin will not choose one by input order."
                    ),
                )
            )

    baseline_unique = {
        seed: rows[0] for seed, rows in by_role_seed[PairRole.BASELINE].items() if len(rows) == 1
    }
    variation_unique = {
        seed: rows[0] for seed, rows in by_role_seed[PairRole.VARIATION].items() if len(rows) == 1
    }
    common = sorted(set(baseline_unique) & set(variation_unique))
    observations: list[PairedStudyObservation] = []
    signatures: list[dict[str, object]] = []
    for seed in common:
        baseline = baseline_unique[seed]
        variation = variation_unique[seed]
        pair_findings = _pair_compatibility_findings(baseline, variation, config.metric_key)
        if pair_findings:
            exclusions.append(
                PairingExclusion(
                    role=PairRole.PAIR,
                    code=PairExclusionCode.PAIR_INCOMPATIBLE,
                    random_seed=seed,
                    detail="; ".join(pair_findings),
                )
            )
            continue
        difference = float(variation.metric.value) - float(baseline.metric.value)
        observations.append(
            PairedStudyObservation(
                random_seed=seed,
                baseline_run_id=baseline.collection.run_id,
                variation_run_id=variation.collection.run_id,
                baseline_value=float(baseline.metric.value),
                variation_value=float(variation.metric.value),
                paired_difference=difference,
                interpretation=_interpret(difference, config.objective),
                baseline_input_fingerprint=str(baseline.collection.input_fingerprint),
                variation_input_fingerprint=str(variation.collection.input_fingerprint),
                baseline_collection_fingerprint=baseline.collection_fingerprint,
                variation_collection_fingerprint=variation.collection_fingerprint,
            )
        )
        signatures.append(_compatibility_signature(baseline, config.metric_key))

    signature_payloads = {_canonical(signature) for signature in signatures}
    signature_fingerprint: str | None = None
    incompatible_signature = len(signature_payloads) > 1
    if incompatible_signature:
        exclusions.append(
            PairingExclusion(
                role=PairRole.STUDY,
                code=PairExclusionCode.STUDY_SIGNATURE_INCOMPATIBLE,
                detail=(
                    "Eligible pairs do not share one metric/environment/semantic compatibility "
                    "signature; no subgroup was selected."
                ),
            )
        )
    elif signature_payloads:
        signature_fingerprint = hashlib.sha256(
            next(iter(signature_payloads)).encode("utf-8")
        ).hexdigest()

    observations.sort(key=lambda item: item.random_seed)
    eligible_seeds = [item.random_seed for item in observations]
    missing_expected = sorted(expected_set - set(eligible_seeds))
    unmatched_baseline = sorted(set(baseline_unique) - set(variation_unique))
    unmatched_variation = sorted(set(variation_unique) - set(baseline_unique))
    audit = CommonSeedPairingAudit(
        expected_random_seeds=sorted(expected_set),
        eligible_random_seeds=eligible_seeds,
        missing_expected_random_seeds=missing_expected,
        unmatched_baseline_random_seeds=unmatched_baseline,
        unmatched_variation_random_seeds=unmatched_variation,
        duplicate_baseline_random_seeds=duplicate_by_role[PairRole.BASELINE],
        duplicate_variation_random_seeds=duplicate_by_role[PairRole.VARIATION],
        input_collection_count=len(source_collections),
        selected_collection_count=selected_count,
        eligible_pair_count=len(observations),
        exclusion_count=len(exclusions),
        exclusions=sorted(
            exclusions,
            key=lambda item: (
                item.random_seed if item.random_seed is not None else -1,
                item.role.value,
                item.code.value,
                item.run_id or "",
            ),
        ),
    )

    if duplicate_run_ids or incompatible_signature:
        status = StatisticalStudyStatus.INCOMPATIBLE
        unavailable_reason = (
            "The selected inputs do not define one unambiguous compatibility cohort."
        )
    elif len(observations) < config.minimum_pairs:
        status = StatisticalStudyStatus.INSUFFICIENT
        unavailable_reason = (
            f"At least {config.minimum_pairs} compatible common-seed pairs are required; "
            f"{len(observations)} were admitted."
        )
    else:
        status = StatisticalStudyStatus.AVAILABLE
        unavailable_reason = None

    differences = [item.paired_difference for item in observations]
    unit = signatures[0]["unit"] if signatures and not incompatible_signature else None
    metric_unit = str(unit) if isinstance(unit, str) else None
    if status is StatisticalStudyStatus.AVAILABLE:
        estimate = _estimate(differences, metric_unit, config.objective)
        bootstrap = _bootstrap_interval(differences, config)
        randomisation = _randomisation_test(differences, config)
        effects = _effect_sizes(differences, config.objective)
    else:
        estimate = PairedEstimate(
            status=StatisticalComponentStatus.UNAVAILABLE,
            n=len(differences),
            unit=metric_unit,
            reason=unavailable_reason,
        )
        bootstrap = PairedBootstrapInterval(
            status=StatisticalComponentStatus.UNAVAILABLE,
            confidence_level=config.confidence_level,
            repetitions=config.bootstrap_repetitions,
            seed=config.resampling_seed,
            reason=unavailable_reason,
            assumptions=_bootstrap_assumptions(),
        )
        randomisation = PairedRandomisationTest(
            status=StatisticalComponentStatus.UNAVAILABLE,
            mode=RandomisationMode.NOT_RUN,
            requested_monte_carlo_repetitions=config.randomisation_repetitions,
            seed=config.resampling_seed + 1,
            reason=unavailable_reason,
            assumptions=_randomisation_assumptions(),
        )
        effects = PairedEffectSizes(
            status=StatisticalComponentStatus.UNAVAILABLE,
            reason=unavailable_reason,
            assumptions=_effect_assumptions(),
        )

    config_fingerprint = config.fingerprint()
    source_sequence_fingerprint = _fingerprint(input_collection_fingerprints)
    study_id = (
        "study-"
        + _fingerprint(
            {
                "config_fingerprint": config_fingerprint,
                "source_sequence_fingerprint": source_sequence_fingerprint,
            }
        )[:16]
    )
    contract = statistical_study_contract()
    warnings: list[str] = []
    if not config.expected_random_seeds:
        warnings.append(
            "No expected random-seed set was supplied; pairing used all otherwise eligible "
            "observed common seeds."
        )
    if missing_expected:
        warnings.append(
            "Predeclared random seeds without an eligible pair: "
            + ", ".join(str(seed) for seed in missing_expected)
        )
    if exclusions:
        warnings.append(
            f"{len(exclusions)} input/pair exclusions are retained in the pairing audit."
        )
    study = StatisticalStudy(
        study_id=study_id,
        generated_at=clock(),
        status=status,
        synthetic=(
            bool(signatures[0]["synthetic"]) if signatures and not incompatible_signature else None
        ),
        config=config,
        config_fingerprint=config_fingerprint,
        metric_unit=metric_unit,
        observations=observations,
        pairing_audit=audit,
        estimate=estimate,
        bootstrap_interval=bootstrap,
        randomisation_test=randomisation,
        effect_sizes=effects,
        input_collection_fingerprints=input_collection_fingerprints,
        compatibility_signature_fingerprint=signature_fingerprint,
        provenance={
            "method_contract_fingerprint": contract.fingerprint(),
            "source_collection_sequence_fingerprint": source_sequence_fingerprint,
            "input_collection_count": len(source_collections),
            "eligible_pair_count": len(observations),
            "synthetic": (
                bool(signatures[0]["synthetic"])
                if signatures and not incompatible_signature
                else None
            ),
        },
        warnings=warnings,
        assumptions=contract.assumptions,
        limitations=contract.limitations,
    )
    if [collection.model_dump(mode="json") for collection in source_collections] != input_snapshot:
        raise RuntimeError("statistical study evaluation mutated an input MetricCollection")
    return study


def metric_collection_fingerprint(collection: MetricCollection) -> str:
    """Fingerprint a complete MetricCollection while normalising its timestamps."""

    payload = collection.model_dump(mode="json")
    payload["generated_at"] = "<normalised>"
    for result in payload["results"]:
        result["computed_at"] = "<normalised>"
    return _fingerprint(payload)


def statistical_study_to_markdown(study: StatisticalStudy) -> str:
    """Render only the typed study artifact as a deterministic Markdown report."""

    config = study.config
    audit = study.pairing_audit
    source_mode = (
        "synthetic"
        if study.synthetic is True
        else "imported"
        if study.synthetic is False
        else "unavailable"
    )
    lines = [
        "# TrafficTwin Paired Statistical Study",
        "",
        f"- Study: `{_cell(study.study_id)}`",
        f"- Status: `{study.status.value}`",
        f"- Experiment: `{_cell(config.experiment_id)}`",
        f"- Metric: `{_cell(config.metric_key)}` ({_cell(study.metric_unit or 'unavailable')})",
        f"- Comparison: `{_cell(config.variation_seed_id)}` minus "
        f"`{_cell(config.baseline_seed_id)}`",
        f"- Algorithm/checkpoint: `{_cell(config.algorithm)}` / "
        f"`{_cell(config.checkpoint or 'none')}`",
        f"- Source mode: `{source_mode}`",
        "",
        "## Predeclared Analysis Plan",
        "",
        f"- Estimand: `{config.estimand}`",
        f"- Pairing key: `{config.pairing_key}`",
        f"- Objective: `{config.objective.value}`",
        f"- Alternative: `{config.alternative}`",
        f"- Confidence level: `{config.confidence_level}`",
        f"- Bootstrap: `{BOOTSTRAP_METHOD}`, repetitions={config.bootstrap_repetitions}, "
        f"seed={config.resampling_seed}",
        f"- Randomisation: `{RANDOMISATION_METHOD}`, exact through "
        f"n={EXACT_SIGN_FLIP_MAX_PAIRS}, Monte Carlo repetitions="
        f"{config.randomisation_repetitions}, seed={config.resampling_seed + 1}",
        f"- Config fingerprint: `{study.config_fingerprint}`",
        "",
        "## Pairing Audit",
        "",
        f"- Input collections: {audit.input_collection_count}",
        f"- Selected collections: {audit.selected_collection_count}",
        f"- Eligible pairs: {audit.eligible_pair_count}",
        f"- Exclusions: {audit.exclusion_count}",
        f"- Expected seeds: {_number_list(audit.expected_random_seeds)}",
        f"- Eligible seeds: {_number_list(audit.eligible_random_seeds)}",
        f"- Missing expected seeds: {_number_list(audit.missing_expected_random_seeds)}",
        f"- Unmatched baseline seeds: {_number_list(audit.unmatched_baseline_random_seeds)}",
        f"- Unmatched variation seeds: {_number_list(audit.unmatched_variation_random_seeds)}",
        "",
        "## Eligible Paired Observations",
        "",
    ]
    if study.observations:
        lines.extend(
            [
                "| Random seed | Baseline | Variation | Difference | Interpretation |",
                "|---:|---:|---:|---:|---|",
                *[
                    f"| {row.random_seed} | {_number(row.baseline_value)} | "
                    f"{_number(row.variation_value)} | {_number(row.paired_difference)} | "
                    f"{row.interpretation.value} |"
                    for row in study.observations
                ],
            ]
        )
    else:
        lines.append("No compatible paired observations were admitted.")
    lines.extend(["", "## Statistical Results", ""])
    if study.status is StatisticalStudyStatus.AVAILABLE:
        lines.extend(
            [
                f"- Mean paired difference: {_number(study.estimate.mean_paired_difference)} "
                f"{_cell(study.metric_unit or '')}",
                f"- Sample SD / SE: {_number(study.estimate.sample_sd_paired_difference)} / "
                f"{_number(study.estimate.standard_error)}",
                f"- {study.bootstrap_interval.confidence_level:.1%} paired-bootstrap interval: "
                f"[{_number(study.bootstrap_interval.lower)}, "
                f"{_number(study.bootstrap_interval.upper)}]",
                f"- Two-sided sign-flip p-value: "
                f"{_number(study.randomisation_test.p_value)} "
                f"({study.randomisation_test.mode.value}, "
                f"{study.randomisation_test.evaluated_assignments} assignments)",
                f"- Cohen's dz: {_number(study.effect_sizes.cohen_dz)}",
                f"- Matched-pairs rank-biserial: "
                f"{_number(study.effect_sizes.matched_pairs_rank_biserial)}",
                "- Cliff's delta: not calculated for the paired primary design",
            ]
        )
    else:
        lines.append(f"Unavailable: {_cell(study.estimate.reason or study.status.value)}")
    lines.extend(["", "## Exclusions", ""])
    if audit.exclusions:
        lines.extend(
            f"- `{item.code.value}` ({item.role.value}, seed="
            f"{item.random_seed if item.random_seed is not None else 'none'}, "
            f"run={_cell(item.run_id or 'none')}): {_cell(item.detail)}"
            for item in audit.exclusions
        )
    else:
        lines.append("None.")
    lines.extend(["", "## Assumptions And Limitations", ""])
    lines.extend(f"- {_cell(item)}" for item in [*study.assumptions, *study.limitations])
    lines.extend(
        [
            "",
            f"Study fingerprint: `{study.fingerprint()}`",
            "",
        ]
    )
    return "\n".join(lines)


def statistical_study_pairs_to_csv(study: StatisticalStudy) -> str:
    """Export eligible pairs and exclusions without dropping audit state."""

    columns = [
        "record_type",
        "study_id",
        "study_status",
        "metric_key",
        "unit",
        "random_seed",
        "role",
        "run_id",
        "baseline_run_id",
        "variation_run_id",
        "baseline_value",
        "variation_value",
        "paired_difference",
        "interpretation",
        "exclusion_code",
        "exclusion_detail",
        "baseline_input_fingerprint",
        "variation_input_fingerprint",
        "baseline_collection_fingerprint",
        "variation_collection_fingerprint",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    common = {
        "study_id": study.study_id,
        "study_status": study.status.value,
        "metric_key": study.config.metric_key,
        "unit": study.metric_unit or "",
    }
    for row in study.observations:
        writer.writerow(
            {
                **common,
                "record_type": "eligible_pair",
                "random_seed": row.random_seed,
                "baseline_run_id": row.baseline_run_id,
                "variation_run_id": row.variation_run_id,
                "baseline_value": row.baseline_value,
                "variation_value": row.variation_value,
                "paired_difference": row.paired_difference,
                "interpretation": row.interpretation.value,
                "baseline_input_fingerprint": row.baseline_input_fingerprint,
                "variation_input_fingerprint": row.variation_input_fingerprint,
                "baseline_collection_fingerprint": row.baseline_collection_fingerprint,
                "variation_collection_fingerprint": row.variation_collection_fingerprint,
            }
        )
    for exclusion in study.pairing_audit.exclusions:
        writer.writerow(
            {
                **common,
                "record_type": "exclusion",
                "random_seed": exclusion.random_seed if exclusion.random_seed is not None else "",
                "role": exclusion.role.value,
                "run_id": exclusion.run_id or "",
                "baseline_run_id": (
                    exclusion.run_id if exclusion.role is PairRole.BASELINE else ""
                ),
                "variation_run_id": (
                    exclusion.run_id if exclusion.role is PairRole.VARIATION else ""
                ),
                "exclusion_code": exclusion.code.value,
                "exclusion_detail": exclusion.detail,
            }
        )
    return output.getvalue()


def _selected_role(metric: MetricValue, config: PairedStudyConfig) -> PairRole | None:
    if (
        metric.experiment_id != config.experiment_id
        or metric.algorithm != config.algorithm
        or metric.checkpoint != config.checkpoint
    ):
        return None
    if metric.seed_id == config.baseline_seed_id:
        return PairRole.BASELINE
    if metric.seed_id == config.variation_seed_id:
        return PairRole.VARIATION
    return None


def _candidate_from_collection(
    collection: MetricCollection,
    role: PairRole,
    config: PairedStudyConfig,
    collection_fingerprint: str,
    exclusions: list[PairingExclusion],
) -> _Candidate | None:
    context = collection.results[0]
    metric = collection.by_key().get(config.metric_key)
    if metric is None:
        _exclude(
            exclusions,
            role,
            PairExclusionCode.METRIC_MISSING,
            collection,
            context.random_seed,
            f"Metric {config.metric_key!r} is absent from the collection.",
        )
        return None
    if metric.status is not MetricStatus.AVAILABLE:
        _exclude(
            exclusions,
            role,
            PairExclusionCode.METRIC_UNAVAILABLE,
            collection,
            context.random_seed,
            f"Metric status is {metric.status.value}; unavailable/partial values are not zero.",
        )
        return None
    if not _is_finite_scalar(metric.value):
        _exclude(
            exclusions,
            role,
            PairExclusionCode.METRIC_NOT_FINITE_SCALAR,
            collection,
            context.random_seed,
            "The selected metric value is not one finite numeric scalar.",
        )
        return None
    expected_context = (
        collection.run_id,
        config.experiment_id,
        config.algorithm,
        config.checkpoint,
        context.seed_id,
        context.random_seed,
    )
    actual_context = (
        metric.run_id,
        metric.experiment_id,
        metric.algorithm,
        metric.checkpoint,
        metric.seed_id,
        metric.random_seed,
    )
    if actual_context != expected_context:
        _exclude(
            exclusions,
            role,
            PairExclusionCode.METRIC_CONTEXT_MISMATCH,
            collection,
            context.random_seed,
            "The selected metric context does not match its collection and analysis plan.",
        )
        return None
    if not collection.input_fingerprint:
        _exclude(
            exclusions,
            role,
            PairExclusionCode.SOURCE_FINGERPRINT_MISSING,
            collection,
            context.random_seed,
            "The collection has no immutable source input fingerprint.",
        )
        return None
    if not metric.environment or not (metric.environment_version or metric.environment_commit):
        _exclude(
            exclusions,
            role,
            PairExclusionCode.ENVIRONMENT_PROVENANCE_UNRESOLVED,
            collection,
            context.random_seed,
            "Environment identity requires a name and version or commit.",
        )
        return None
    missing_contracts = _missing_semantic_contracts(metric, config.metric_key)
    if missing_contracts:
        _exclude(
            exclusions,
            role,
            PairExclusionCode.SEMANTIC_CONTRACT_UNRESOLVED,
            collection,
            context.random_seed,
            "Missing required semantic fingerprints: " + ", ".join(missing_contracts),
        )
        return None
    return _Candidate(role, collection, metric, collection_fingerprint)


def _pair_compatibility_findings(
    baseline: _Candidate,
    variation: _Candidate,
    metric_key: str,
) -> list[str]:
    fields = {
        "metric collection version": (
            baseline.collection.metric_version,
            variation.collection.metric_version,
        ),
        "metric implementation version": (
            baseline.metric.implementation_version,
            variation.metric.implementation_version,
        ),
        "metric unit": (baseline.metric.unit, variation.metric.unit),
        "synthetic label": (baseline.metric.synthetic, variation.metric.synthetic),
        "environment name": (baseline.metric.environment, variation.metric.environment),
        "environment version": (
            baseline.metric.environment_version,
            variation.metric.environment_version,
        ),
        "environment commit": (
            baseline.metric.environment_commit,
            variation.metric.environment_commit,
        ),
    }
    findings = [name + " differs" for name, values in fields.items() if values[0] != values[1]]
    baseline_contract = _semantic_contract(baseline.metric, metric_key)
    variation_contract = _semantic_contract(variation.metric, metric_key)
    if baseline_contract != variation_contract:
        findings.append("metric semantic-contract fingerprints differ")
    return findings


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
        "semantic_contract": _semantic_contract(metric, metric_key),
    }


def _semantic_contract(metric: MetricValue, metric_key: str) -> dict[str, str]:
    keys = _semantic_contract_keys(metric_key)
    return {
        key: str(metric.metadata[key]) for key in keys if isinstance(metric.metadata.get(key), str)
    }


def _missing_semantic_contracts(metric: MetricValue, metric_key: str) -> list[str]:
    return [
        key
        for key in _semantic_contract_keys(metric_key)
        if not isinstance(metric.metadata.get(key), str) or not metric.metadata.get(key)
    ]


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


def _estimate(
    differences: list[float],
    unit: str | None,
    objective: ObjectiveDirection,
) -> PairedEstimate:
    mean = arithmetic_mean(differences)
    sample_sd = sample_standard_deviation(differences)
    assert mean is not None and sample_sd is not None
    return PairedEstimate(
        status=StatisticalComponentStatus.AVAILABLE,
        n=len(differences),
        unit=unit,
        mean_paired_difference=mean,
        sample_sd_paired_difference=sample_sd,
        standard_error=sample_sd / math.sqrt(len(differences)),
        minimum_paired_difference=min(differences),
        maximum_paired_difference=max(differences),
        interpretation=_interpret(mean, objective),
    )


def _bootstrap_interval(
    differences: list[float],
    config: PairedStudyConfig,
) -> PairedBootstrapInterval:
    rng = random.Random(config.resampling_seed)  # noqa: S311 - scientific resampling
    n = len(differences)
    bootstrap_means = [
        sum(differences[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(config.bootstrap_repetitions)
    ]
    alpha = 1.0 - config.confidence_level
    lower = percentile_linear(bootstrap_means, alpha / 2.0)
    upper = percentile_linear(bootstrap_means, 1.0 - alpha / 2.0)
    assert lower is not None and upper is not None
    return PairedBootstrapInterval(
        status=StatisticalComponentStatus.AVAILABLE,
        confidence_level=config.confidence_level,
        repetitions=config.bootstrap_repetitions,
        seed=config.resampling_seed,
        lower=lower,
        upper=upper,
        assumptions=_bootstrap_assumptions(),
    )


def _randomisation_test(
    differences: list[float],
    config: PairedStudyConfig,
) -> PairedRandomisationTest:
    observed = abs(sum(differences) / len(differences))
    tolerance = max(1e-15, observed * 1e-12)
    if len(differences) <= EXACT_SIGN_FLIP_MAX_PAIRS:
        statistics = (
            abs(
                sum(sign * value for sign, value in zip(signs, differences, strict=True))
                / len(differences)
            )
            for signs in itertools.product((-1.0, 1.0), repeat=len(differences))
        )
        evaluated = 0
        extreme = 0
        for statistic in statistics:
            evaluated += 1
            if statistic >= observed - tolerance:
                extreme += 1
        p_value = extreme / evaluated
        mode = RandomisationMode.EXACT
    else:
        rng = random.Random(  # noqa: S311 - scientific randomisation
            config.resampling_seed + 1
        )
        evaluated = config.randomisation_repetitions
        extreme = 0
        for _ in range(evaluated):
            statistic = abs(
                sum((1.0 if rng.getrandbits(1) else -1.0) * value for value in differences)
                / len(differences)
            )
            if statistic >= observed - tolerance:
                extreme += 1
        p_value = (extreme + 1) / (evaluated + 1)
        mode = RandomisationMode.MONTE_CARLO
    return PairedRandomisationTest(
        status=StatisticalComponentStatus.AVAILABLE,
        mode=mode,
        observed_statistic=observed,
        p_value=p_value,
        evaluated_assignments=evaluated,
        requested_monte_carlo_repetitions=config.randomisation_repetitions,
        seed=config.resampling_seed + 1,
        assumptions=_randomisation_assumptions(),
    )


def _effect_sizes(
    differences: list[float],
    objective: ObjectiveDirection,
) -> PairedEffectSizes:
    mean = arithmetic_mean(differences)
    sample_sd = sample_standard_deviation(differences)
    assert mean is not None and sample_sd is not None
    cohen_dz = mean / sample_sd if sample_sd > 0 else None
    rank_biserial = _matched_pairs_rank_biserial(differences)
    interpretations = [_interpret(value, objective) for value in differences]
    return PairedEffectSizes(
        status=StatisticalComponentStatus.AVAILABLE,
        mean_paired_difference=mean,
        cohen_dz=cohen_dz,
        cohen_dz_reason=(
            None
            if cohen_dz is not None
            else "Paired-difference sample SD is zero, so Cohen's dz is undefined."
        ),
        matched_pairs_rank_biserial=rank_biserial,
        rank_biserial_reason=(
            None
            if rank_biserial is not None
            else (
                "Every paired difference is zero, so the non-zero absolute-rank denominator "
                "is empty."
            )
        ),
        variation_favourable_count=sum(
            item is PairInterpretation.FAVOURS_VARIATION for item in interpretations
        ),
        baseline_favourable_count=sum(
            item is PairInterpretation.FAVOURS_BASELINE for item in interpretations
        ),
        tie_count=sum(item is PairInterpretation.TIE for item in interpretations),
        assumptions=_effect_assumptions(),
    )


def _matched_pairs_rank_biserial(differences: list[float]) -> float | None:
    non_zero = [(abs(value), value) for value in differences if value != 0]
    if not non_zero:
        return None
    ordered = sorted(enumerate(non_zero), key=lambda item: item[1][0])
    ranks: dict[int, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1][0] == ordered[index][1][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        for position in range(index, end):
            ranks[ordered[position][0]] = average_rank
        index = end
    positive = sum(ranks[index] for index, (_, value) in enumerate(non_zero) if value > 0)
    negative = sum(ranks[index] for index, (_, value) in enumerate(non_zero) if value < 0)
    return (positive - negative) / (positive + negative)


def _interpret(difference: float, objective: ObjectiveDirection) -> PairInterpretation:
    if difference == 0:
        return PairInterpretation.TIE
    favourable = difference > 0 if objective is ObjectiveDirection.MAXIMISE else difference < 0
    return (
        PairInterpretation.FAVOURS_VARIATION if favourable else PairInterpretation.FAVOURS_BASELINE
    )


def _bootstrap_assumptions() -> list[str]:
    return [
        "Complete paired differences are resampled together with replacement.",
        "The admitted pairs represent the empirical common-seed sample for this plan.",
        "Percentile endpoints are descriptive bootstrap uncertainty, not an external guarantee.",
    ]


def _randomisation_assumptions() -> list[str]:
    return [
        "Under the sharp zero-effect null, paired-difference signs are exchangeable.",
        "The test is two-sided and uses the absolute mean paired difference.",
        "Monte Carlo mode uses the recorded local seed and plus-one p-value correction.",
    ]


def _effect_assumptions() -> list[str]:
    return [
        "The original-unit mean paired difference is the primary effect estimate.",
        "Cohen's dz standardises by the sample SD of paired differences.",
        "Matched-pairs rank-biserial uses non-zero absolute ranks and retains ties separately.",
        "No unpaired Cliff's delta is inferred for the primary paired design.",
    ]


def _group_candidates(rows: list[_Candidate]) -> dict[int, list[_Candidate]]:
    grouped: dict[int, list[_Candidate]] = defaultdict(list)
    for row in rows:
        grouped[row.random_seed].append(row)
    return grouped


def _exclude(
    exclusions: list[PairingExclusion],
    role: PairRole,
    code: PairExclusionCode,
    collection: MetricCollection,
    random_seed: int,
    detail: str,
) -> None:
    exclusions.append(
        PairingExclusion(
            role=role,
            code=code,
            run_id=collection.run_id,
            random_seed=random_seed,
            detail=detail,
        )
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
    if value is None:
        return "unavailable"
    return f"{value:.12g}"


def _number_list(values: list[int]) -> str:
    return ", ".join(str(value) for value in values) if values else "none"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
