"""Deterministic paired common-seed power planning for STA-05."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from statistics import NormalDist
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.metrics.results import JsonScalar
from traffictwin.metrics.statistics import stable_float

POWER_ANALYSIS_SCHEMA_VERSION: Literal["1.0"] = "1.0"
POWER_ANALYSIS_METHOD_VERSION: Literal["1.0"] = "1.0"
PAIRED_NORMAL_APPROXIMATION_METHOD: Literal["two_sided_paired_mean_normal_approximation_v1"] = (
    "two_sided_paired_mean_normal_approximation_v1"
)
MINIMUM_ALPHA = 0.001
MAXIMUM_ALPHA = 0.20
MINIMUM_TARGET_POWER = 0.50
MAXIMUM_TARGET_POWER = 0.999
MINIMUM_COMMON_SEED_REPLICATES: Literal[3] = 3
MAXIMUM_ALLOWED_REPLICATES = 1_000_000
DEFAULT_MAXIMUM_REPLICATES = 100_000
SMALL_SAMPLE_THRESHOLD = 30


class PowerAnalysisStatus(StrEnum):
    """Availability of the complete planning calculation."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class PowerAnalysisReasonCode(StrEnum):
    """Stable reason the requested sample-size calculation is unavailable."""

    NONE = "NONE"
    ZERO_TARGET_EFFECT = "ZERO_TARGET_EFFECT"
    NON_POSITIVE_VARIANCE = "NON_POSITIVE_VARIANCE"
    MAXIMUM_REPLICATES_EXCEEDED = "MAXIMUM_REPLICATES_EXCEEDED"


class TargetEffectBasis(StrEnum):
    """Predeclared source of the target effect used for planning."""

    PRACTICAL_THRESHOLD = "practical_threshold"
    LITERATURE = "literature"
    PILOT_STUDY = "pilot_study"
    SYNTHETIC = "synthetic"
    PROVISIONAL_DESIGN = "provisional_design"


class PairedVarianceBasis(StrEnum):
    """Predeclared source of the paired-difference variance."""

    LITERATURE = "literature"
    PILOT_STUDY = "pilot_study"
    SYNTHETIC = "synthetic"
    PROVISIONAL_DESIGN = "provisional_design"


class PowerEstimateLabel(StrEnum):
    """Mandatory qualifiers attached to a planning estimate."""

    PLANNING_AID = "planning_aid_not_a_guarantee"
    SMALL_PILOT_SAMPLE = "small_pilot_sample"
    SMALL_PLANNED_SAMPLE = "small_planned_sample"
    SYNTHETIC_INPUT = "synthetic_input"
    PROVISIONAL_INPUT = "provisional_input"


class PowerAnalysisConfig(BaseModel):
    """Strict predeclared inputs for one paired common-seed planning calculation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = POWER_ANALYSIS_SCHEMA_VERSION
    method: Literal["two_sided_paired_mean_normal_approximation_v1"] = (
        PAIRED_NORMAL_APPROXIMATION_METHOD
    )
    metric_key: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    pairing_key: Literal["random_seed"] = "random_seed"
    estimand: Literal["mean_paired_difference_variation_minus_baseline"] = (
        "mean_paired_difference_variation_minus_baseline"
    )
    alternative: Literal["two_sided"] = "two_sided"
    target_effect: float
    paired_difference_variance: float = Field(ge=0.0)
    alpha: float = Field(default=0.05, ge=MINIMUM_ALPHA, le=MAXIMUM_ALPHA)
    target_power: float = Field(
        default=0.80,
        ge=MINIMUM_TARGET_POWER,
        le=MAXIMUM_TARGET_POWER,
    )
    target_effect_basis: TargetEffectBasis
    target_effect_justification: str = Field(min_length=12)
    target_effect_reference: str | None = None
    variance_basis: PairedVarianceBasis
    variance_justification: str = Field(min_length=12)
    variance_reference: str | None = None
    pilot_sample_size: int | None = Field(default=None, ge=2)
    synthetic: bool = False
    minimum_replicates: Literal[3] = MINIMUM_COMMON_SEED_REPLICATES
    maximum_replicates: int = Field(
        default=DEFAULT_MAXIMUM_REPLICATES,
        ge=MINIMUM_COMMON_SEED_REPLICATES,
        le=MAXIMUM_ALLOWED_REPLICATES,
    )
    multiple_comparison_policy: Literal["not_applicable_single_predeclared_comparison"] = (
        "not_applicable_single_predeclared_comparison"
    )

    @field_validator("metric_key", "unit")
    @classmethod
    def normalise_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must contain non-space characters")
        return stripped

    @field_validator("target_effect_justification", "variance_justification")
    @classmethod
    def validate_justification(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 12:
            raise ValueError("justification must contain at least 12 non-space characters")
        return stripped

    @field_validator("target_effect_reference", "variance_reference")
    @classmethod
    def normalise_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_plan(self) -> PowerAnalysisConfig:
        numeric_values = {
            "target_effect": self.target_effect,
            "paired_difference_variance": self.paired_difference_variance,
            "alpha": self.alpha,
            "target_power": self.target_power,
        }
        for name, value in numeric_values.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if (
            self.target_effect_basis is TargetEffectBasis.LITERATURE
            and not self.target_effect_reference
        ):
            raise ValueError("target_effect_reference is required for a literature effect basis")
        if self.variance_basis is PairedVarianceBasis.LITERATURE and not self.variance_reference:
            raise ValueError("variance_reference is required for a literature variance basis")
        uses_pilot = (
            self.target_effect_basis is TargetEffectBasis.PILOT_STUDY
            or self.variance_basis is PairedVarianceBasis.PILOT_STUDY
        )
        if uses_pilot and self.pilot_sample_size is None:
            raise ValueError("pilot_sample_size is required when either input uses a pilot study")
        uses_synthetic = (
            self.target_effect_basis is TargetEffectBasis.SYNTHETIC
            or self.variance_basis is PairedVarianceBasis.SYNTHETIC
        )
        if uses_synthetic and not self.synthetic:
            raise ValueError("synthetic must be true when either input basis is synthetic")
        return self

    def fingerprint(self) -> str:
        """Return the stable identity of the complete predeclared plan."""

        return _fingerprint(self.model_dump(mode="json"))


class PairedPowerCalculation(BaseModel):
    """Complete numerical output or typed unavailable state."""

    model_config = ConfigDict(extra="forbid")

    status: PowerAnalysisStatus
    reason_code: PowerAnalysisReasonCode
    reason: str | None = None
    method: Literal["two_sided_paired_mean_normal_approximation_v1"] = (
        PAIRED_NORMAL_APPROXIMATION_METHOD
    )
    target_effect: float
    target_effect_magnitude: float
    paired_difference_variance: float
    paired_difference_standard_deviation: float | None = None
    standardised_effect_magnitude: float | None = None
    alpha: float
    target_power: float
    two_sided_critical_value: float
    required_common_seed_replicates: int | None = None
    required_total_policy_runs: int | None = None
    achieved_power: float | None = None
    preceding_replicate_count: int | None = None
    preceding_power: float | None = None


class PowerAnalysis(BaseModel):
    """Versioned deterministic STA-05 planning artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = POWER_ANALYSIS_SCHEMA_VERSION
    method_version: Literal["1.0"] = POWER_ANALYSIS_METHOD_VERSION
    analysis_id: str
    generated_at: datetime
    status: PowerAnalysisStatus
    config: PowerAnalysisConfig
    config_fingerprint: str
    calculation: PairedPowerCalculation
    labels: list[PowerEstimateLabel]
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return formatted strict JSON."""

        return self.model_dump_json(indent=2)

    def fingerprint(self) -> str:
        """Return a timestamp-normalised artifact fingerprint."""

        payload = self.model_dump(mode="json")
        payload["generated_at"] = "<normalised>"
        return _fingerprint(payload)


class PowerAnalysisMethodContract(BaseModel):
    """Machine-readable scientific boundary of STA-05 version 1.0."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = POWER_ANALYSIS_SCHEMA_VERSION
    method_version: Literal["1.0"] = POWER_ANALYSIS_METHOD_VERSION
    method: Literal["two_sided_paired_mean_normal_approximation_v1"] = (
        PAIRED_NORMAL_APPROXIMATION_METHOD
    )
    pairing_key: Literal["random_seed"] = "random_seed"
    estimand: Literal["mean_paired_difference_variation_minus_baseline"] = (
        "mean_paired_difference_variation_minus_baseline"
    )
    alternative: Literal["two_sided"] = "two_sided"
    required_inputs: list[str]
    alpha_bounds: dict[str, float]
    target_power_bounds: dict[str, float]
    replicate_bounds: dict[str, int]
    decision_rule: str
    labels: list[str]
    assumptions: list[str]
    unavailable_behavior: str
    unsupported: list[str]
    limitations: list[str]

    def fingerprint(self) -> str:
        """Return the stable method-contract identity."""

        return _fingerprint(self.model_dump(mode="json"))


def power_analysis_method_contract() -> PowerAnalysisMethodContract:
    """Return the fixed STA-05 version 1.0 method contract."""

    return PowerAnalysisMethodContract(
        required_inputs=[
            "finite signed target effect in the metric's original unit",
            "finite non-negative variance of paired variation-minus-baseline differences",
            "two-sided alpha",
            "target power",
            "effect and variance bases with written justifications",
            "pilot sample size when either input is pilot-derived",
            "explicit synthetic label when either input is synthetic",
        ],
        alpha_bounds={"minimum": MINIMUM_ALPHA, "maximum": MAXIMUM_ALPHA},
        target_power_bounds={
            "minimum": MINIMUM_TARGET_POWER,
            "maximum": MAXIMUM_TARGET_POWER,
        },
        replicate_bounds={
            "minimum": MINIMUM_COMMON_SEED_REPLICATES,
            "maximum": MAXIMUM_ALLOWED_REPLICATES,
        },
        decision_rule=(
            "Return the smallest integer n within the declared bounds whose two-sided normal-"
            "approximation power is greater than or equal to target_power; verify n-1 remains "
            "below target when n exceeds the minimum."
        ),
        labels=[item.value for item in PowerEstimateLabel],
        assumptions=_method_assumptions(),
        unavailable_behavior=(
            "A zero target effect, non-positive paired-difference variance, or target not reached "
            "within the declared maximum yields a typed unavailable calculation; no value is "
            "imputed and unavailable is never represented as zero."
        ),
        unsupported=[
            "retrospective or observed post-hoc power claims",
            "power for STA-01 sign-flip randomisation inference",
            "paired TOST equivalence power",
            "N-way or multiple-comparison power",
            "attrition, incompatible-run, or missing-pair inflation",
            "automatic extraction of a target effect or variance from observed results",
            "simulation-based, sequential, adaptive, cluster, or unpaired designs",
        ],
        limitations=_method_limitations(),
    )


def evaluate_power_analysis(
    config: PowerAnalysisConfig,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> PowerAnalysis:
    """Calculate the minimum common-seed pair count for one predeclared plan."""

    config_snapshot = config.model_dump(mode="json")
    generated_at = clock()
    normal = NormalDist()
    raw_critical_value = normal.inv_cdf(1.0 - config.alpha / 2.0)
    critical_value = stable_float(raw_critical_value)
    effect_magnitude = abs(config.target_effect)
    variance = config.paired_difference_variance
    standard_deviation = stable_float(math.sqrt(variance)) if variance > 0.0 else None

    if effect_magnitude == 0.0:
        calculation = _unavailable_calculation(
            config,
            critical_value,
            PowerAnalysisReasonCode.ZERO_TARGET_EFFECT,
            "A zero target effect has no finite positive-effect sample-size solution.",
            standard_deviation,
        )
    elif standard_deviation is None:
        calculation = _unavailable_calculation(
            config,
            critical_value,
            PowerAnalysisReasonCode.NON_POSITIVE_VARIANCE,
            "A finite positive paired-difference variance is required by this method.",
            None,
        )
    else:
        standardised_effect = stable_float(effect_magnitude / standard_deviation)
        maximum_power = _two_sided_normal_power(
            config.maximum_replicates,
            standardised_effect,
            raw_critical_value,
            normal,
        )
        if maximum_power < config.target_power:
            calculation = _unavailable_calculation(
                config,
                critical_value,
                PowerAnalysisReasonCode.MAXIMUM_REPLICATES_EXCEEDED,
                (
                    f"Target power {config.target_power:.6g} was not reached by the declared "
                    f"maximum of {config.maximum_replicates} common-seed replicates; maximum "
                    f"evaluated power was {maximum_power:.12g}."
                ),
                standard_deviation,
                standardised_effect=standardised_effect,
            )
        else:
            required = _minimum_required_replicates(
                config,
                standardised_effect,
                raw_critical_value,
            )
            achieved = _two_sided_normal_power(
                required,
                standardised_effect,
                raw_critical_value,
                normal,
            )
            preceding_count = required - 1 if required > config.minimum_replicates else None
            preceding_power = (
                _two_sided_normal_power(
                    preceding_count,
                    standardised_effect,
                    raw_critical_value,
                    normal,
                )
                if preceding_count is not None
                else None
            )
            calculation = PairedPowerCalculation(
                status=PowerAnalysisStatus.AVAILABLE,
                reason_code=PowerAnalysisReasonCode.NONE,
                target_effect=config.target_effect,
                target_effect_magnitude=effect_magnitude,
                paired_difference_variance=variance,
                paired_difference_standard_deviation=standard_deviation,
                standardised_effect_magnitude=standardised_effect,
                alpha=config.alpha,
                target_power=config.target_power,
                two_sided_critical_value=critical_value,
                required_common_seed_replicates=required,
                required_total_policy_runs=required * 2,
                achieved_power=achieved,
                preceding_replicate_count=preceding_count,
                preceding_power=preceding_power,
            )

    labels = _estimate_labels(config, calculation)
    contract = power_analysis_method_contract()
    config_fingerprint = config.fingerprint()
    analysis_id = "power-" + config_fingerprint[:16]
    analysis = PowerAnalysis(
        analysis_id=analysis_id,
        generated_at=generated_at,
        status=calculation.status,
        config=config,
        config_fingerprint=config_fingerprint,
        calculation=calculation,
        labels=labels,
        provenance={
            "method_contract_fingerprint": contract.fingerprint(),
            "planning_input_fingerprint": config_fingerprint,
            "target_effect_basis": config.target_effect_basis.value,
            "variance_basis": config.variance_basis.value,
            "pilot_sample_size": config.pilot_sample_size,
            "synthetic": config.synthetic,
            "minimum_replicates": config.minimum_replicates,
            "maximum_replicates": config.maximum_replicates,
        },
        warnings=_warnings(config, calculation, labels),
        assumptions=contract.assumptions,
        limitations=contract.limitations,
    )
    if config.model_dump(mode="json") != config_snapshot:
        raise RuntimeError("power analysis mutated its input configuration")
    return analysis


def power_analysis_to_markdown(analysis: PowerAnalysis) -> str:
    """Render one typed planning artifact as deterministic Markdown."""

    config = analysis.config
    result = analysis.calculation
    lines = [
        "# TrafficTwin Paired Common-Seed Power Analysis",
        "",
        f"- Analysis ID: `{analysis.analysis_id}`",
        f"- Status: `{analysis.status.value}`",
        f"- Labels: `{', '.join(item.value for item in analysis.labels)}`",
        f"- Metric: `{config.metric_key}`",
        f"- Unit: `{config.unit}`",
        f"- Method: `{config.method}`",
        "",
        "## Predeclared planning inputs",
        "",
        f"- Target effect: `{config.target_effect:.12g}` `{config.unit}`",
        f"- Target-effect basis: `{config.target_effect_basis.value}`",
        f"- Target-effect justification: {config.target_effect_justification}",
        f"- Target-effect reference: {config.target_effect_reference or 'not supplied'}",
        (
            f"- Paired-difference variance: `{config.paired_difference_variance:.12g}` "
            f"`{config.unit}^2`"
        ),
        f"- Variance basis: `{config.variance_basis.value}`",
        f"- Variance justification: {config.variance_justification}",
        f"- Variance reference: {config.variance_reference or 'not supplied'}",
        f"- Pilot sample size: `{config.pilot_sample_size or 'not applicable'}`",
        f"- Synthetic inputs: `{str(config.synthetic).lower()}`",
        f"- Two-sided alpha: `{config.alpha:.12g}`",
        f"- Target power: `{config.target_power:.12g}`",
        "",
        "## Planning result",
        "",
        f"- Reason code: `{result.reason_code.value}`",
        (
            "- Paired-difference standard deviation: "
            f"`{_optional_number(result.paired_difference_standard_deviation)}` `{config.unit}`"
        ),
        (
            "- Standardised effect magnitude: "
            f"`{_optional_number(result.standardised_effect_magnitude)}`"
        ),
        f"- Two-sided critical value: `{result.two_sided_critical_value:.12g}`",
        (
            "- Required common-seed replicates: "
            f"`{result.required_common_seed_replicates or 'unavailable'}`"
        ),
        f"- Required total policy runs: `{result.required_total_policy_runs or 'unavailable'}`",
        f"- Achieved approximate power: `{_optional_number(result.achieved_power)}`",
        (
            "- Preceding replicate count/power: "
            f"`{result.preceding_replicate_count or 'not applicable'}` / "
            f"`{_optional_number(result.preceding_power)}`"
        ),
    ]
    if result.reason:
        lines.append(f"- Availability reason: {result.reason}")
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {warning}" for warning in analysis.warnings)
    lines.extend(["", "## Assumptions"])
    lines.extend(f"- {assumption}" for assumption in analysis.assumptions)
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {limitation}" for limitation in analysis.limitations)
    return "\n".join(lines) + "\n"


def power_analysis_to_csv(analysis: PowerAnalysis) -> str:
    """Render the planning inputs and result as one deterministic CSV record."""

    output = io.StringIO(newline="")
    fieldnames = [
        "analysis_id",
        "status",
        "labels",
        "metric_key",
        "unit",
        "method",
        "target_effect",
        "target_effect_basis",
        "paired_difference_variance",
        "variance_basis",
        "pilot_sample_size",
        "synthetic",
        "alpha",
        "target_power",
        "required_common_seed_replicates",
        "required_total_policy_runs",
        "achieved_power",
        "preceding_replicate_count",
        "preceding_power",
        "reason_code",
        "reason",
        "config_fingerprint",
        "analysis_fingerprint",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    result = analysis.calculation
    writer.writerow(
        {
            "analysis_id": analysis.analysis_id,
            "status": analysis.status.value,
            "labels": "|".join(item.value for item in analysis.labels),
            "metric_key": analysis.config.metric_key,
            "unit": analysis.config.unit,
            "method": analysis.config.method,
            "target_effect": analysis.config.target_effect,
            "target_effect_basis": analysis.config.target_effect_basis.value,
            "paired_difference_variance": analysis.config.paired_difference_variance,
            "variance_basis": analysis.config.variance_basis.value,
            "pilot_sample_size": analysis.config.pilot_sample_size,
            "synthetic": str(analysis.config.synthetic).lower(),
            "alpha": analysis.config.alpha,
            "target_power": analysis.config.target_power,
            "required_common_seed_replicates": result.required_common_seed_replicates,
            "required_total_policy_runs": result.required_total_policy_runs,
            "achieved_power": result.achieved_power,
            "preceding_replicate_count": result.preceding_replicate_count,
            "preceding_power": result.preceding_power,
            "reason_code": result.reason_code.value,
            "reason": result.reason,
            "config_fingerprint": analysis.config_fingerprint,
            "analysis_fingerprint": analysis.fingerprint(),
        }
    )
    return output.getvalue()


def _minimum_required_replicates(
    config: PowerAnalysisConfig,
    standardised_effect: float,
    critical_value: float,
) -> int:
    normal = NormalDist()
    low: int = config.minimum_replicates
    high = config.maximum_replicates
    while low < high:
        midpoint = (low + high) // 2
        if (
            _two_sided_normal_power(midpoint, standardised_effect, critical_value, normal)
            >= config.target_power
        ):
            high = midpoint
        else:
            low = midpoint + 1
    return low


def _two_sided_normal_power(
    replicate_count: int,
    standardised_effect: float,
    critical_value: float,
    normal: NormalDist,
) -> float:
    noncentrality = math.sqrt(replicate_count) * standardised_effect
    left_tail = normal.cdf(-critical_value - noncentrality)
    right_tail = normal.cdf(noncentrality - critical_value)
    return stable_float(min(1.0, max(0.0, left_tail + right_tail)))


def _unavailable_calculation(
    config: PowerAnalysisConfig,
    critical_value: float,
    code: PowerAnalysisReasonCode,
    reason: str,
    standard_deviation: float | None,
    *,
    standardised_effect: float | None = None,
) -> PairedPowerCalculation:
    return PairedPowerCalculation(
        status=PowerAnalysisStatus.UNAVAILABLE,
        reason_code=code,
        reason=reason,
        target_effect=config.target_effect,
        target_effect_magnitude=abs(config.target_effect),
        paired_difference_variance=config.paired_difference_variance,
        paired_difference_standard_deviation=standard_deviation,
        standardised_effect_magnitude=standardised_effect,
        alpha=config.alpha,
        target_power=config.target_power,
        two_sided_critical_value=critical_value,
    )


def _estimate_labels(
    config: PowerAnalysisConfig,
    calculation: PairedPowerCalculation,
) -> list[PowerEstimateLabel]:
    labels = [PowerEstimateLabel.PLANNING_AID]
    if config.pilot_sample_size is not None and config.pilot_sample_size < SMALL_SAMPLE_THRESHOLD:
        labels.append(PowerEstimateLabel.SMALL_PILOT_SAMPLE)
    if (
        calculation.required_common_seed_replicates is not None
        and calculation.required_common_seed_replicates < SMALL_SAMPLE_THRESHOLD
    ):
        labels.append(PowerEstimateLabel.SMALL_PLANNED_SAMPLE)
    if config.synthetic:
        labels.append(PowerEstimateLabel.SYNTHETIC_INPUT)
    if (
        config.target_effect_basis is TargetEffectBasis.PROVISIONAL_DESIGN
        or config.variance_basis is PairedVarianceBasis.PROVISIONAL_DESIGN
    ):
        labels.append(PowerEstimateLabel.PROVISIONAL_INPUT)
    return labels


def _warnings(
    config: PowerAnalysisConfig,
    calculation: PairedPowerCalculation,
    labels: list[PowerEstimateLabel],
) -> list[str]:
    warnings = [
        "This is a prospective planning aid under declared assumptions, not a guarantee of "
        "achieved power, significance, effect size, or external validity."
    ]
    if PowerEstimateLabel.SMALL_PILOT_SAMPLE in labels:
        warnings.append(
            "The declared pilot sample has fewer than 30 pairs; its variance may be unstable and "
            "that uncertainty is not propagated into the sample-size estimate."
        )
    if PowerEstimateLabel.SMALL_PLANNED_SAMPLE in labels:
        warnings.append(
            "The planned sample has fewer than 30 pairs; the normal approximation may be poor "
            "when paired differences are skewed or heavy-tailed."
        )
    if PowerEstimateLabel.SYNTHETIC_INPUT in labels:
        warnings.append(
            "At least one planning input is synthetic; this estimate is method/software evidence "
            "and must not be presented as real-world calibration."
        )
    if PowerEstimateLabel.PROVISIONAL_INPUT in labels:
        warnings.append(
            "At least one planning input is provisional and requires study-specific defence "
            "before dissertation or deployment use."
        )
    if config.target_effect < 0.0:
        warnings.append(
            "The signed target effect is retained for provenance; two-sided power uses its "
            "absolute magnitude."
        )
    if calculation.status is PowerAnalysisStatus.UNAVAILABLE and calculation.reason:
        warnings.append(calculation.reason)
    return warnings


def _method_assumptions() -> list[str]:
    return [
        "Common random seeds define independent paired experimental units.",
        "The declared variance is the prospective variance of variation-minus-baseline paired "
        "differences in the stated unit squared.",
        "The paired-mean sampling distribution is approximated by a normal distribution and the "
        "planning variance is treated as fixed and known.",
        "The target effect, alpha, target power, and bases are declared before confirmatory "
        "results are inspected.",
        "Every planned common seed yields one compatible baseline and one compatible variation "
        "run; no attrition or exclusions are built into the estimate.",
        "The calculation concerns one two-sided predeclared comparison without multiplicity "
        "adjustment.",
    ]


def _method_limitations() -> list[str]:
    return [
        "The result is a planning estimate, not guaranteed achieved power and not evidence that "
        "a completed study was adequately powered.",
        "The normal approximation can be optimistic for small, skewed, heavy-tailed, or "
        "variance-uncertain paired samples.",
        "TrafficTwin does not derive a target effect or variance from observed results, validate "
        "their practical basis, or inflate for missing/incompatible pairs.",
        "This method does not calculate power for STA-01 sign-flip inference, STA-03 paired TOST, "
        "N-way ranking, multiple comparisons, sequential designs, or external simulator costs.",
        "Synthetic or provisional inputs provide software and design evidence only, not real-world "
        "or externally validated sample-size evidence.",
        "Power planning does not establish causality, practical importance, policy superiority, "
        "equivalence, or deployment suitability.",
    ]


def _optional_number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.12g}"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
