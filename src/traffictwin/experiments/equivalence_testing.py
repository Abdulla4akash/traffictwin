"""Predeclared paired TOST equivalence studies for STA-03."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.experiments.statistical_study import (
    CommonSeedPairingAudit,
    PairedStudyConfig,
    PairedStudyObservation,
    StatisticalStudyStatus,
    evaluate_paired_statistical_study,
)
from traffictwin.metrics.results import JsonScalar, MetricCollection
from traffictwin.metrics.statistics import arithmetic_mean, sample_standard_deviation

EQUIVALENCE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
EQUIVALENCE_METHOD_VERSION: Literal["1.0"] = "1.0"
PAIRED_TOST_METHOD: Literal["paired_mean_tost_v1"] = "paired_mean_tost_v1"
MINIMUM_EQUIVALENCE_PAIRS: Literal[3] = 3
MINIMUM_ALPHA = 0.005
MAXIMUM_ALPHA = 0.10


class EquivalenceStudyStatus(StrEnum):
    """Availability of the complete equivalence study."""

    AVAILABLE = "available"
    INSUFFICIENT = "insufficient"
    INCOMPATIBLE = "incompatible"
    DEGENERATE = "degenerate"


class EquivalenceComponentStatus(StrEnum):
    """Availability of the paired TOST component."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class EquivalenceConclusion(StrEnum):
    """Bounded interpretation of the paired TOST decision."""

    DEMONSTRATED = "equivalence_demonstrated"
    NOT_DEMONSTRATED = "equivalence_not_demonstrated"
    UNAVAILABLE = "unavailable"


class EquivalenceMarginBasis(StrEnum):
    """Predeclared source of practical meaning for the absolute margin."""

    PRACTICAL_THRESHOLD = "practical_threshold"
    LITERATURE = "literature"
    PROVISIONAL_DESIGN = "provisional_design"


class EquivalenceStudyConfig(BaseModel):
    """Strict predeclared selection, margin, and method for paired equivalence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = EQUIVALENCE_SCHEMA_VERSION
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
    method: Literal["paired_mean_tost_v1"] = PAIRED_TOST_METHOD
    equivalence_margin: float = Field(gt=0.0)
    margin_basis: EquivalenceMarginBasis
    margin_justification: str = Field(min_length=12)
    margin_reference: str | None = None
    alpha: float = Field(default=0.05, ge=MINIMUM_ALPHA, le=MAXIMUM_ALPHA)
    expected_random_seeds: list[int] = Field(default_factory=list)
    minimum_pairs: Literal[3] = MINIMUM_EQUIVALENCE_PAIRS
    multiple_comparison_policy: Literal["not_applicable_single_predeclared_equivalence_test"] = (
        "not_applicable_single_predeclared_equivalence_test"
    )

    @field_validator("expected_random_seeds")
    @classmethod
    def validate_expected_random_seeds(cls, values: list[int]) -> list[int]:
        if any(value < 0 for value in values):
            raise ValueError("expected_random_seeds values must be non-negative")
        if len(values) != len(set(values)):
            raise ValueError("expected_random_seeds must not contain duplicates")
        return sorted(values)

    @field_validator("margin_justification")
    @classmethod
    def validate_margin_justification(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 12:
            raise ValueError("margin_justification must contain at least 12 non-space characters")
        return stripped

    @field_validator("margin_reference")
    @classmethod
    def normalise_margin_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_plan(self) -> EquivalenceStudyConfig:
        if self.baseline_seed_id == self.variation_seed_id:
            raise ValueError("baseline_seed_id and variation_seed_id must differ")
        if not math.isfinite(self.equivalence_margin):
            raise ValueError("equivalence_margin must be finite")
        if not math.isfinite(self.alpha):
            raise ValueError("alpha must be finite")
        if self.margin_basis is EquivalenceMarginBasis.LITERATURE and not self.margin_reference:
            raise ValueError("margin_reference is required when margin_basis is literature")
        return self

    def fingerprint(self) -> str:
        """Return the stable identity of the complete equivalence plan."""

        return _fingerprint(self.model_dump(mode="json"))

    def paired_config(self) -> PairedStudyConfig:
        """Build the fixed STA-01 pairing request used only to admit compatible pairs."""

        return PairedStudyConfig(
            experiment_id=self.experiment_id,
            baseline_seed_id=self.baseline_seed_id,
            variation_seed_id=self.variation_seed_id,
            algorithm=self.algorithm,
            checkpoint=self.checkpoint,
            metric_key=self.metric_key,
            objective=self.objective,
            expected_random_seeds=self.expected_random_seeds,
            confidence_level=0.95,
            bootstrap_repetitions=1_000,
            randomisation_repetitions=1_000,
            resampling_seed=0,
        )


class OneSidedEquivalenceTest(BaseModel):
    """One half of the intersection-union paired TOST decision."""

    model_config = ConfigDict(extra="forbid")

    side: Literal["lower", "upper"]
    null_hypothesis: str
    alternative_hypothesis: str
    t_statistic: float
    degrees_of_freedom: int = Field(ge=1)
    p_value: float = Field(ge=0.0, le=1.0)
    alpha: float
    rejected: bool


class EquivalenceConfidenceInterval(BaseModel):
    """The Student-t interval equivalent to the two one-sided test decision."""

    model_config = ConfigDict(extra="forbid")

    status: EquivalenceComponentStatus
    confidence_level: float
    critical_value: float | None = None
    lower: float | None = None
    upper: float | None = None
    strictly_inside_margin: bool | None = None
    reason: str | None = None


class PairedTostResult(BaseModel):
    """Complete paired-mean TOST estimate, hypotheses, and bounded conclusion."""

    model_config = ConfigDict(extra="forbid")

    status: EquivalenceComponentStatus
    method: Literal["paired_mean_tost_v1"] = PAIRED_TOST_METHOD
    n: int = Field(ge=0)
    degrees_of_freedom: int | None = Field(default=None, ge=1)
    unit: str | None = None
    mean_paired_difference: float | None = None
    sample_sd_paired_difference: float | None = None
    standard_error: float | None = None
    margin_lower: float
    margin_upper: float
    alpha: float
    lower_test: OneSidedEquivalenceTest | None = None
    upper_test: OneSidedEquivalenceTest | None = None
    interval: EquivalenceConfidenceInterval
    conclusion: EquivalenceConclusion
    reason: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class EquivalenceStudy(BaseModel):
    """Versioned STA-03 artifact over one compatible STA-01 pairing cohort."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = EQUIVALENCE_SCHEMA_VERSION
    method_version: Literal["1.0"] = EQUIVALENCE_METHOD_VERSION
    study_id: str
    generated_at: datetime
    status: EquivalenceStudyStatus
    synthetic: bool | None
    config: EquivalenceStudyConfig
    config_fingerprint: str
    metric_unit: str | None = None
    observations: list[PairedStudyObservation]
    pairing_audit: CommonSeedPairingAudit
    tost: PairedTostResult
    source_paired_study_id: str
    source_paired_study_fingerprint: str
    source_paired_config_fingerprint: str
    input_collection_fingerprints: dict[str, str]
    compatibility_signature_fingerprint: str | None = None
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return formatted strict JSON."""

        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)

    def canonical_json(self) -> str:
        """Return canonical JSON with only the generation timestamp normalised."""

        payload = self.model_dump(mode="json")
        payload["generated_at"] = "<normalised>"
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def fingerprint(self) -> str:
        """Return the deterministic equivalence-study fingerprint."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class EquivalenceTestingContract(BaseModel):
    """Published STA-03 method, margin, evidence, and interpretation boundary."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = EQUIVALENCE_SCHEMA_VERSION
    method_version: Literal["1.0"] = EQUIVALENCE_METHOD_VERSION
    evidence_boundary: str
    pairing_contract: str
    estimand: str
    method: str
    hypotheses: list[str]
    margin_contract: list[str]
    alpha_bounds: dict[str, float]
    minimum_pairs: int
    confidence_interval_rule: str
    decision_rule: str
    assumptions: list[str]
    unavailable_behavior: str
    unsupported: list[str]
    limitations: list[str]

    def fingerprint(self) -> str:
        """Return the deterministic method-contract fingerprint."""

        return _fingerprint(self.model_dump(mode="json"))


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def equivalence_testing_contract() -> EquivalenceTestingContract:
    """Return the complete bounded STA-03 v1 method contract."""

    return EquivalenceTestingContract(
        evidence_boundary=(
            "Completed MetricCollection artifacts admitted by the unchanged STA-01 common-seed "
            "pairing contract plus an explicit EquivalenceStudyConfig."
        ),
        pairing_contract=(
            "Exact random_seed pairs from one experiment, baseline/variation family, policy, "
            "checkpoint, metric, environment, unit, and semantic compatibility signature"
        ),
        estimand="mean paired difference in original units (variation minus baseline)",
        method=PAIRED_TOST_METHOD,
        hypotheses=[
            "lower: H0 mean <= -margin; H1 mean > -margin",
            "upper: H0 mean >= +margin; H1 mean < +margin",
        ],
        margin_contract=[
            "finite positive symmetric absolute margin in the metric's original unit",
            "declared before evaluation with practical_threshold, literature, or "
            "provisional_design basis",
            "written justification is mandatory; literature basis also requires a reference",
            "no repository-wide default margin and no post-hoc margin selection",
        ],
        alpha_bounds={"minimum": MINIMUM_ALPHA, "maximum": MAXIMUM_ALPHA},
        minimum_pairs=MINIMUM_EQUIVALENCE_PAIRS,
        confidence_interval_rule=(
            "the 100*(1-2*alpha)% paired Student-t interval must lie strictly inside "
            "(-margin, +margin)"
        ),
        decision_rule=(
            "equivalence is demonstrated only when both one-sided p-values are strictly below "
            "the predeclared alpha"
        ),
        assumptions=_tost_assumptions(),
        unavailable_behavior=(
            "Insufficient, incompatible, missing, duplicate, non-finite, provenance-incomplete, "
            "semantic-contract-incomplete, or zero-variance evidence yields an explicit typed "
            "unavailable result and is never imputed."
        ),
        unsupported=[
            "asymmetric or relative equivalence margins",
            "unpaired equivalence testing",
            "post-hoc margin selection",
            "multiple simultaneous equivalence claims",
            "non-inferiority or superiority conclusions",
            "regression gates (STA-04)",
            "power analysis (STA-05)",
        ],
        limitations=[
            "A failed TOST means equivalence was not demonstrated; it does not prove difference.",
            "An ordinary non-significant difference test is not evidence of equivalence.",
            "Student-t inference assumes approximately normal paired differences and independent "
            "random-seed experimental units.",
            "The caller, not TrafficTwin, supplies and defends the practical margin.",
            "Synthetic studies provide software/method evidence, not external validation.",
            "Equivalence does not establish causality, universal policy similarity, or deployment "
            "suitability.",
        ],
    )


def evaluate_equivalence_study(
    collections: Sequence[MetricCollection],
    config: EquivalenceStudyConfig,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> EquivalenceStudy:
    """Evaluate one predeclared paired TOST over the ordinary STA-01 pairing cohort."""

    source_collections = list(collections)
    input_snapshot = [collection.model_dump(mode="json") for collection in source_collections]
    generated_at = clock()
    paired = evaluate_paired_statistical_study(
        source_collections,
        config.paired_config(),
        clock=lambda: generated_at,
    )
    differences = [row.paired_difference for row in paired.observations]
    unavailable_reason: str | None = None
    if paired.status is StatisticalStudyStatus.INCOMPATIBLE:
        status = EquivalenceStudyStatus.INCOMPATIBLE
        unavailable_reason = "The inherited STA-01 pairing cohort is incompatible."
    elif paired.status is StatisticalStudyStatus.INSUFFICIENT:
        status = EquivalenceStudyStatus.INSUFFICIENT
        unavailable_reason = (
            f"At least {config.minimum_pairs} compatible common-seed pairs are required; "
            f"{len(differences)} were admitted."
        )
    else:
        sample_sd = sample_standard_deviation(differences)
        if sample_sd is None or sample_sd <= 0.0 or not math.isfinite(sample_sd):
            status = EquivalenceStudyStatus.DEGENERATE
            unavailable_reason = (
                "Paired TOST requires a finite positive paired-difference sample standard "
                "deviation; the admitted cohort has zero or invalid variance."
            )
        else:
            status = EquivalenceStudyStatus.AVAILABLE

    if status is EquivalenceStudyStatus.AVAILABLE:
        tost = _evaluate_tost(differences, paired.metric_unit, config)
    else:
        tost = _unavailable_tost(
            len(differences),
            paired.metric_unit,
            config,
            unavailable_reason or "Equivalence inference is unavailable.",
        )

    contract = equivalence_testing_contract()
    config_fingerprint = config.fingerprint()
    source_paired_fingerprint = paired.fingerprint()
    study_id = (
        "equivalence-"
        + _fingerprint(
            {
                "config_fingerprint": config_fingerprint,
                "source_paired_study_fingerprint": source_paired_fingerprint,
            }
        )[:16]
    )
    warnings = list(paired.warnings)
    warnings.append(
        "The equivalence margin is caller-declared in the metric's original unit; TrafficTwin "
        "does not validate its practical or literature basis."
    )
    if config.margin_basis is EquivalenceMarginBasis.PROVISIONAL_DESIGN:
        warnings.append(
            "The equivalence margin is explicitly provisional design evidence and must not be "
            "presented as literature- or stakeholder-validated."
        )
    if tost.conclusion is EquivalenceConclusion.NOT_DEMONSTRATED:
        warnings.append(
            "Equivalence was not demonstrated; this result does not establish that the conditions "
            "are meaningfully different."
        )
    study = EquivalenceStudy(
        study_id=study_id,
        generated_at=generated_at,
        status=status,
        synthetic=paired.synthetic,
        config=config,
        config_fingerprint=config_fingerprint,
        metric_unit=paired.metric_unit,
        observations=paired.observations,
        pairing_audit=paired.pairing_audit,
        tost=tost,
        source_paired_study_id=paired.study_id,
        source_paired_study_fingerprint=source_paired_fingerprint,
        source_paired_config_fingerprint=paired.config_fingerprint,
        input_collection_fingerprints=paired.input_collection_fingerprints,
        compatibility_signature_fingerprint=paired.compatibility_signature_fingerprint,
        provenance={
            "method_contract_fingerprint": contract.fingerprint(),
            "source_paired_method_contract_fingerprint": paired.provenance.get(
                "method_contract_fingerprint"
            ),
            "source_paired_study_fingerprint": source_paired_fingerprint,
            "source_collection_sequence_fingerprint": paired.provenance.get(
                "source_collection_sequence_fingerprint"
            ),
            "input_collection_count": len(source_collections),
            "eligible_pair_count": len(differences),
            "synthetic": paired.synthetic,
        },
        warnings=warnings,
        assumptions=contract.assumptions,
        limitations=contract.limitations,
    )
    if [collection.model_dump(mode="json") for collection in source_collections] != input_snapshot:
        raise RuntimeError("equivalence evaluation mutated an input MetricCollection")
    return study


def equivalence_study_to_markdown(study: EquivalenceStudy) -> str:
    """Render only the typed equivalence artifact as deterministic Markdown."""

    config = study.config
    tost = study.tost
    lines = [
        "# TrafficTwin Paired Equivalence Study",
        "",
        f"- Study ID: `{study.study_id}`",
        f"- Status: `{study.status.value}`",
        f"- Conclusion: `{tost.conclusion.value}`",
        f"- Experiment: `{config.experiment_id}`",
        f"- Comparison: `{config.variation_seed_id}` minus `{config.baseline_seed_id}`",
        f"- Policy: `{config.algorithm}`",
        f"- Metric: `{config.metric_key}`",
        f"- Unit: `{study.metric_unit or 'unavailable'}`",
        f"- Eligible common-seed pairs: `{len(study.observations)}`",
        f"- Method: `{tost.method}`",
        f"- One-sided alpha: `{config.alpha:.6g}`",
        "",
        "## Predeclared equivalence margin",
        "",
        f"- Region: `({-config.equivalence_margin:.12g}, {config.equivalence_margin:.12g})`",
        f"- Basis: `{config.margin_basis.value}`",
        f"- Justification: {config.margin_justification}",
        f"- Reference: {config.margin_reference or 'not supplied'}",
        "",
        "## TOST result",
        "",
        f"- Mean paired difference: `{_optional_number(tost.mean_paired_difference)}`",
        f"- Paired-difference SD: `{_optional_number(tost.sample_sd_paired_difference)}`",
        f"- Standard error: `{_optional_number(tost.standard_error)}`",
        (
            f"- {(1.0 - 2.0 * config.alpha) * 100:.1f}% interval: "
            f"`[{_optional_number(tost.interval.lower)}, "
            f"{_optional_number(tost.interval.upper)}]`"
        ),
    ]
    if tost.lower_test is not None and tost.upper_test is not None:
        both_rejected = str(tost.lower_test.rejected and tost.upper_test.rejected).lower()
        lines.extend(
            [
                f"- Lower one-sided p-value: `{tost.lower_test.p_value:.12g}`",
                f"- Upper one-sided p-value: `{tost.upper_test.p_value:.12g}`",
                f"- Both nulls rejected: `{both_rejected}`",
            ]
        )
    if tost.reason:
        lines.append(f"- Availability reason: {tost.reason}")
    expected_seeds = (
        ", ".join(map(str, study.pairing_audit.expected_random_seeds)) or "not declared"
    )
    eligible_seeds = ", ".join(map(str, study.pairing_audit.eligible_random_seeds)) or "none"
    lines.extend(
        [
            "",
            "> Equivalence is demonstrated only when both predeclared one-sided tests reject. "
            "Ordinary non-significance is not equivalence, and failed TOST does not prove a "
            "meaningful difference.",
            "",
            "## Pairing audit",
            "",
            f"- Expected seeds: `{expected_seeds}`",
            f"- Eligible seeds: `{eligible_seeds}`",
            f"- Exclusions: `{study.pairing_audit.exclusion_count}`",
        ]
    )
    for exclusion in study.pairing_audit.exclusions:
        lines.append(
            f"  - `{exclusion.code.value}` seed={exclusion.random_seed}: {exclusion.detail}"
        )
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in study.warnings)
    lines.extend(["", "## Assumptions", ""])
    lines.extend(f"- {assumption}" for assumption in study.assumptions)
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in study.limitations)
    return "\n".join(lines).rstrip() + "\n"


def equivalence_study_to_csv(study: EquivalenceStudy) -> str:
    """Export summary, tests, eligible pairs, and exclusions from one typed artifact."""

    output = io.StringIO(newline="")
    fieldnames = [
        "row_type",
        "study_id",
        "status",
        "conclusion",
        "random_seed",
        "baseline_run_id",
        "variation_run_id",
        "baseline_value",
        "variation_value",
        "paired_difference",
        "side",
        "t_statistic",
        "p_value",
        "rejected",
        "margin_lower",
        "margin_upper",
        "margin_basis",
        "margin_justification",
        "margin_reference",
        "alpha",
        "code",
        "detail",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    common = {
        "study_id": study.study_id,
        "status": study.status.value,
        "conclusion": study.tost.conclusion.value,
        "margin_lower": study.tost.margin_lower,
        "margin_upper": study.tost.margin_upper,
        "margin_basis": study.config.margin_basis.value,
        "margin_justification": study.config.margin_justification,
        "margin_reference": study.config.margin_reference or "",
        "alpha": study.config.alpha,
    }
    writer.writerow({"row_type": "summary", **common, "detail": study.tost.reason or ""})
    for test in [study.tost.lower_test, study.tost.upper_test]:
        if test is None:
            continue
        writer.writerow(
            {
                "row_type": "one_sided_test",
                **common,
                "side": test.side,
                "t_statistic": test.t_statistic,
                "p_value": test.p_value,
                "rejected": test.rejected,
                "detail": f"{test.null_hypothesis}; {test.alternative_hypothesis}",
            }
        )
    for row in study.observations:
        writer.writerow(
            {
                "row_type": "eligible_pair",
                **common,
                "random_seed": row.random_seed,
                "baseline_run_id": row.baseline_run_id,
                "variation_run_id": row.variation_run_id,
                "baseline_value": row.baseline_value,
                "variation_value": row.variation_value,
                "paired_difference": row.paired_difference,
            }
        )
    for exclusion in study.pairing_audit.exclusions:
        writer.writerow(
            {
                "row_type": "exclusion",
                **common,
                "random_seed": exclusion.random_seed,
                "code": exclusion.code.value,
                "detail": exclusion.detail,
            }
        )
    return output.getvalue()


def _evaluate_tost(
    differences: list[float],
    unit: str | None,
    config: EquivalenceStudyConfig,
) -> PairedTostResult:
    n = len(differences)
    degrees_of_freedom = n - 1
    mean = arithmetic_mean(differences)
    sample_sd = sample_standard_deviation(differences)
    if mean is None or sample_sd is None:
        raise RuntimeError("available paired TOST received insufficient numeric observations")
    standard_error = sample_sd / math.sqrt(n)
    margin = config.equivalence_margin
    lower_t = (mean + margin) / standard_error
    upper_t = (mean - margin) / standard_error
    lower_p = _clamp_probability(1.0 - _student_t_cdf(lower_t, degrees_of_freedom))
    upper_p = _clamp_probability(_student_t_cdf(upper_t, degrees_of_freedom))
    lower_rejected = lower_p < config.alpha
    upper_rejected = upper_p < config.alpha
    critical = _student_t_quantile(1.0 - config.alpha, degrees_of_freedom)
    interval_lower = mean - critical * standard_error
    interval_upper = mean + critical * standard_error
    interval_inside = interval_lower > -margin and interval_upper < margin
    demonstrated = lower_rejected and upper_rejected
    if demonstrated != interval_inside:
        raise RuntimeError(
            "paired TOST p-value and confidence-interval decisions did not reconcile"
        )
    return PairedTostResult(
        status=EquivalenceComponentStatus.AVAILABLE,
        n=n,
        degrees_of_freedom=degrees_of_freedom,
        unit=unit,
        mean_paired_difference=mean,
        sample_sd_paired_difference=sample_sd,
        standard_error=standard_error,
        margin_lower=-margin,
        margin_upper=margin,
        alpha=config.alpha,
        lower_test=OneSidedEquivalenceTest(
            side="lower",
            null_hypothesis=f"mean_paired_difference <= {-margin:.12g}",
            alternative_hypothesis=f"mean_paired_difference > {-margin:.12g}",
            t_statistic=lower_t,
            degrees_of_freedom=degrees_of_freedom,
            p_value=lower_p,
            alpha=config.alpha,
            rejected=lower_rejected,
        ),
        upper_test=OneSidedEquivalenceTest(
            side="upper",
            null_hypothesis=f"mean_paired_difference >= {margin:.12g}",
            alternative_hypothesis=f"mean_paired_difference < {margin:.12g}",
            t_statistic=upper_t,
            degrees_of_freedom=degrees_of_freedom,
            p_value=upper_p,
            alpha=config.alpha,
            rejected=upper_rejected,
        ),
        interval=EquivalenceConfidenceInterval(
            status=EquivalenceComponentStatus.AVAILABLE,
            confidence_level=1.0 - 2.0 * config.alpha,
            critical_value=critical,
            lower=interval_lower,
            upper=interval_upper,
            strictly_inside_margin=interval_inside,
        ),
        conclusion=(
            EquivalenceConclusion.DEMONSTRATED
            if demonstrated
            else EquivalenceConclusion.NOT_DEMONSTRATED
        ),
        assumptions=_tost_assumptions(),
    )


def _unavailable_tost(
    n: int,
    unit: str | None,
    config: EquivalenceStudyConfig,
    reason: str,
) -> PairedTostResult:
    return PairedTostResult(
        status=EquivalenceComponentStatus.UNAVAILABLE,
        n=n,
        unit=unit,
        margin_lower=-config.equivalence_margin,
        margin_upper=config.equivalence_margin,
        alpha=config.alpha,
        interval=EquivalenceConfidenceInterval(
            status=EquivalenceComponentStatus.UNAVAILABLE,
            confidence_level=1.0 - 2.0 * config.alpha,
            reason=reason,
        ),
        conclusion=EquivalenceConclusion.UNAVAILABLE,
        reason=reason,
        assumptions=_tost_assumptions(),
    )


def _tost_assumptions() -> list[str]:
    return [
        "The exact common random-seed pairs admitted by STA-01 are the experimental units.",
        "Paired differences are independent across random seeds and approximately normal.",
        "The symmetric absolute margin was chosen before inspecting this study result.",
        "The margin is expressed in the metric's unchanged original unit.",
        "Both one-sided null hypotheses must reject at the predeclared alpha.",
        "One predeclared equivalence claim is evaluated; no multiplicity adjustment applies.",
    ]


def _student_t_cdf(value: float, degrees_of_freedom: int) -> float:
    """Return the Student-t CDF using the regularised incomplete beta identity."""

    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be positive")
    if not math.isfinite(value):
        raise ValueError("Student-t value must be finite")
    if value == 0.0:
        return 0.5
    df = float(degrees_of_freedom)
    x = df / (df + value * value)
    beta = _regularised_incomplete_beta(x, df / 2.0, 0.5)
    return 1.0 - 0.5 * beta if value > 0.0 else 0.5 * beta


def _student_t_quantile(probability: float, degrees_of_freedom: int) -> float:
    """Invert the deterministic Student-t CDF by bounded monotonic bisection."""

    if not 0.0 < probability < 1.0:
        raise ValueError("probability must lie strictly between zero and one")
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be positive")
    if probability == 0.5:
        return 0.0
    if probability < 0.5:
        return -_student_t_quantile(1.0 - probability, degrees_of_freedom)
    lower = 0.0
    upper = 1.0
    while _student_t_cdf(upper, degrees_of_freedom) < probability:
        upper *= 2.0
        if upper > 2.0**52:
            raise RuntimeError("Student-t quantile search did not converge")
    for _ in range(160):
        midpoint = (lower + upper) / 2.0
        if _student_t_cdf(midpoint, degrees_of_freedom) < probability:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _regularised_incomplete_beta(x: float, a: float, b: float) -> float:
    """Evaluate I_x(a,b) with a stable continued-fraction expansion."""

    if not 0.0 <= x <= 1.0:
        raise ValueError("incomplete-beta x must lie in [0, 1]")
    if a <= 0.0 or b <= 0.0:
        raise ValueError("incomplete-beta shape parameters must be positive")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    maximum_iterations = 300
    epsilon = 3.0e-14
    minimum = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < minimum:
        d = minimum
    d = 1.0 / d
    result = d
    for iteration in range(1, maximum_iterations + 1):
        m = float(iteration)
        m2 = 2.0 * m
        coefficient = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + coefficient * d
        if abs(d) < minimum:
            d = minimum
        c = 1.0 + coefficient / c
        if abs(c) < minimum:
            c = minimum
        d = 1.0 / d
        result *= d * c
        coefficient = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + coefficient * d
        if abs(d) < minimum:
            d = minimum
        c = 1.0 + coefficient / c
        if abs(c) < minimum:
            c = minimum
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) <= epsilon:
            return result
    raise RuntimeError("incomplete-beta continued fraction did not converge")


def _clamp_probability(value: float) -> float:
    return min(1.0, max(0.0, value))


def _optional_number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.12g}"


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
