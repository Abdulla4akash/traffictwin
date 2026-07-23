"""MAN-10 candidate: deterministic observed-versus-simulated comparison.

The module is a pure evidence transformation. One versioned contract binds one
observed source, geographic scope, time basis, interval duration, aggregation,
weighting, missingness, denominator, coverage, unit, precision, and interpretation
policy. Exact typed inputs are embedded in every result and every persisted result is
fully re-derived from those inputs during validation.

Production goodness-of-fit remains unavailable until the exact contract fingerprint
is added to the reviewed registry. Synthetic-development contracts exist only to
exercise deterministic software behavior; they make no Manchester realism claim.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal, TypeAlias, TypeVar

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)

MANCHESTER_COMPARISON_SCHEMA_VERSION = "1.0"
MANCHESTER_COMPARISON_METHOD_VERSION = "manchester-comparison-1.0"
MANCHESTER_COMPARISON_CAPABILITY_ID = "MAN-10"

# A production entry requires a reviewed, predeclared study design. Keeping this
# registry empty makes real MAE/RMSE unavailable while MAN-10 remains planned.
APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS: frozenset[str] = frozenset()

DIFFERENCE_DIRECTION = "simulated_minus_observed"
RESULT_QUANTUM = Decimal("0.001")
_DECIMAL_PRECISION = 28
_MAX_ABSOLUTE_VALUE = Decimal("1000000000")

_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$"
_LABEL_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"

ComparisonMeasure: TypeAlias = Literal["vehicle_count", "average_speed_mps"]
ComparisonUnit: TypeAlias = Literal["vehicles_per_interval", "m/s"]
GoodnessOfFitMetric: TypeAlias = Literal["mae", "rmse"]
ComparisonSide: TypeAlias = Literal["observed", "simulated"]
ObservedSource: TypeAlias = Literal["dft_raw_count", "webtris_daily", "synthetic_utc_road"]
ContractAdmission: TypeAlias = Literal[
    "synthetic_development_inputs",
    "approved_production_contract",
    "not_admitted_production_unapproved",
]
ExclusionReason: TypeAlias = Literal[
    "unmatched_no_simulated_counterpart",
    "unmatched_no_observed_counterpart",
    "duplicate_identical_row",
    "conflicting_duplicate_rows",
    "source_mismatch",
    "measure_mismatch",
    "unit_mismatch",
    "scope_mismatch",
    "time_basis_mismatch",
    "interval_duration_mismatch",
    "lineage_fingerprint_mismatch",
]

_MEASURE_UNITS: dict[ComparisonMeasure, ComparisonUnit] = {
    "vehicle_count": "vehicles_per_interval",
    "average_speed_mps": "m/s",
}

_InputT = TypeVar("_InputT", bound="_ComparisonInputBase")


class ManchesterComparisonError(ValueError):
    """Typed caller-side misuse of the comparison boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterComparisonModel(ManchesterSnapshotModel):
    """Strict frozen base for deterministic MAN-10 artifacts."""


class ManchesterComparisonMetricContract(ManchesterComparisonModel):
    """Every methodological decision for one non-fusing comparison."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-10"] = "MAN-10"
    method_version: Literal["manchester-comparison-1.0"] = "manchester-comparison-1.0"
    contract_version: str = Field(pattern=_LABEL_PATTERN)
    evidence_class: Literal["synthetic_development", "production"]
    observed_source: ObservedSource
    scope_label: str = Field(pattern=_LABEL_PATTERN)
    scope_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    time_basis_label: str = Field(pattern=_LABEL_PATTERN)
    time_basis_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    interval_duration_s: int = Field(ge=1, le=86_400)
    measure: ComparisonMeasure
    unit: ComparisonUnit
    pairing_key_fields: tuple[
        Literal["site_edge_id"],
        Literal["interval_start_s"],
        Literal["interval_end_s"],
        Literal["direction"],
        Literal["vehicle_class"],
    ] = ("site_edge_id", "interval_start_s", "interval_end_s", "direction", "vehicle_class")
    source_fusion: Literal["none"] = "none"
    interval_aggregation: Literal["exact_interval_no_resampling"] = "exact_interval_no_resampling"
    weighting_policy: Literal["equal_interval"] = "equal_interval"
    missing_policy: Literal["exclude_unpaired_never_zero"] = "exclude_unpaired_never_zero"
    duplicate_policy: Literal["collapse_identical_exclude_conflicts"] = (
        "collapse_identical_exclude_conflicts"
    )
    denominator_policy: Literal["all_input_rows_per_side"] = "all_input_rows_per_side"
    minimum_observed_coverage: Decimal = Field(ge=0, le=1)
    minimum_simulated_coverage: Decimal = Field(ge=0, le=1)
    difference_direction: Literal["simulated_minus_observed"] = "simulated_minus_observed"
    unit_conversion: Literal["none"] = "none"
    rounding_mode: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    result_quantum: Literal["0.001"] = "0.001"
    metric_denominator: Literal["paired_intervals"] = "paired_intervals"
    goodness_of_fit_metrics: tuple[GoodnessOfFitMetric, ...] = Field(
        default=("mae", "rmse"), min_length=1
    )
    interpretation_policy: Literal["descriptive_non_causal"] = "descriptive_non_causal"

    @model_validator(mode="after")
    def validate_contract(self) -> ManchesterComparisonMetricContract:
        if self.unit != _MEASURE_UNITS[self.measure]:
            raise ValueError("the contract unit must be the fixed unit of its measure")
        if self.observed_source == "dft_raw_count" and self.measure != "vehicle_count":
            raise ValueError("DfT raw-count contracts can compare vehicle counts only")
        if self.evidence_class == "synthetic_development" and self.observed_source != (
            "synthetic_utc_road"
        ):
            raise ValueError("synthetic development contracts require the synthetic source")
        if self.evidence_class == "production" and self.observed_source == "synthetic_utc_road":
            raise ValueError("production contracts cannot select the synthetic source")
        for coverage in (
            self.minimum_observed_coverage,
            self.minimum_simulated_coverage,
        ):
            if not coverage.is_finite() or _quantize(coverage) != coverage:
                raise ValueError("coverage thresholds must be finite multiples of 0.001")
        metrics = list(self.goodness_of_fit_metrics)
        if metrics != sorted(set(metrics)):
            raise ValueError("goodness-of-fit metrics must be sorted and unique")
        return self


class ComparisonIntervalContent(ManchesterComparisonModel):
    """Scientific content shared by one observed or simulated interval."""

    site_edge_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    interval_start_s: int = Field(ge=0, le=31_536_000)
    interval_end_s: int = Field(ge=1, le=31_536_000)
    direction: str = Field(pattern=_IDENTIFIER_PATTERN)
    vehicle_class: str = Field(pattern=_IDENTIFIER_PATTERN)
    measure: ComparisonMeasure
    unit: ComparisonUnit
    value: Decimal = Field(ge=0)
    scope_label: str = Field(pattern=_LABEL_PATTERN)
    scope_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    time_basis_label: str = Field(pattern=_LABEL_PATTERN)
    time_basis_fingerprint: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_content(self) -> ComparisonIntervalContent:
        if self.interval_end_s <= self.interval_start_s:
            raise ValueError("interval end must be after its start")
        if self.unit != _MEASURE_UNITS[self.measure]:
            raise ValueError("interval unit must be the fixed unit of its measure")
        if not self.value.is_finite() or self.value > _MAX_ABSOLUTE_VALUE:
            raise ValueError("comparison values must be finite and bounded")
        return self

    def pair_key(self) -> tuple[str, int, int, str, str]:
        return (
            self.site_edge_id,
            self.interval_start_s,
            self.interval_end_s,
            self.direction,
            self.vehicle_class,
        )

    def duration_s(self) -> int:
        return self.interval_end_s - self.interval_start_s

    def semantic_key(self) -> tuple[object, ...]:
        """Numeric equality deliberately treats Decimal('10') and Decimal('10.0') equally."""

        return (
            *self.pair_key(),
            self.measure,
            self.unit,
            self.value,
            self.scope_label,
            self.scope_fingerprint,
            self.time_basis_label,
            self.time_basis_fingerprint,
        )


class _ComparisonInputBase(ManchesterComparisonModel):
    """One content-bound comparison input plus its upstream provenance reference."""

    interval: ComparisonIntervalContent
    interval_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    input_binding_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    synthetic: bool

    @model_validator(mode="after")
    def validate_input_binding(self) -> _ComparisonInputBase:
        if self.interval_fingerprint != self.interval.fingerprint():
            raise ValueError("interval fingerprint must bind the embedded interval")
        if self.input_binding_fingerprint != _input_binding_fingerprint(self):
            raise ValueError("input binding fingerprint must bind content and provenance")
        return self

    def pair_key(self) -> tuple[str, int, int, str, str]:
        return self.interval.pair_key()

    def semantic_key(self) -> tuple[object, ...]:
        return (*self.interval.semantic_key(), self.synthetic)


class ObservedComparisonInterval(_ComparisonInputBase):
    """One observed interval bound to snapshot, projection, and mapping evidence."""

    source: ObservedSource
    source_snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    projection_report_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    mapping_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    measurement_state: Literal["observed"] = "observed"
    missing_filled_with_zero: Literal[False] = False

    @model_validator(mode="after")
    def validate_source_semantics(self) -> ObservedComparisonInterval:
        if self.source == "dft_raw_count" and self.interval.measure != "vehicle_count":
            raise ValueError("DfT raw-count evidence cannot represent speed")
        if self.synthetic != (self.source == "synthetic_utc_road"):
            raise ValueError("observed source and synthetic evidence state must agree")
        return self


class SimulatedComparisonInterval(_ComparisonInputBase):
    """One simulated interval bound to network, calibration, and SUMO-run evidence."""

    network_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    calibration_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    sumo_run_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    evidence_kind: Literal["sumo_simulated_interval"] = "sumo_simulated_interval"


class ComparisonLineage(ManchesterComparisonModel):
    """Exact upstream artifacts one comparison may consume."""

    observed_snapshot_ids: tuple[str, ...] = Field(min_length=1)
    projection_report_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    mapping_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    calibration_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    network_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    sumo_run_fingerprint: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_lineage(self) -> ComparisonLineage:
        identifiers = list(self.observed_snapshot_ids)
        if identifiers != sorted(set(identifiers)):
            raise ValueError("observed snapshot ids must be sorted and unique")
        if any(re.fullmatch(_SNAPSHOT_ID_PATTERN, value) is None for value in identifiers):
            raise ValueError("observed snapshot ids must have the snapshot shape")
        return self


class AdmittedComparisonPair(ManchesterComparisonModel):
    """One exactly paired interval with recomputable differences and input bindings."""

    site_edge_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    interval_start_s: int = Field(ge=0)
    interval_end_s: int = Field(ge=1)
    direction: str = Field(pattern=_IDENTIFIER_PATTERN)
    vehicle_class: str = Field(pattern=_IDENTIFIER_PATTERN)
    measure: ComparisonMeasure
    unit: ComparisonUnit
    scope_label: str = Field(pattern=_LABEL_PATTERN)
    scope_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    time_basis_label: str = Field(pattern=_LABEL_PATTERN)
    time_basis_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    observed_value: Decimal = Field(ge=0)
    simulated_value: Decimal = Field(ge=0)
    difference_direction: Literal["simulated_minus_observed"] = "simulated_minus_observed"
    signed_difference: Decimal
    absolute_difference: Decimal = Field(ge=0)
    observed_input_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    simulated_input_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    observed_source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    simulated_source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_pair(self) -> AdmittedComparisonPair:
        if self.interval_end_s <= self.interval_start_s:
            raise ValueError("interval end must be after its start")
        for value in (self.observed_value, self.simulated_value, self.signed_difference):
            if not value.is_finite():
                raise ValueError("paired values and differences must be finite")
        expected = _subtract_quantized(self.simulated_value, self.observed_value)
        if self.signed_difference != expected:
            raise ValueError("signed_difference must be simulated minus observed")
        if self.absolute_difference != expected.copy_abs():
            raise ValueError("absolute_difference must be the signed-difference magnitude")
        return self


class ExcludedComparisonInterval(ManchesterComparisonModel):
    """One exact input retained outside the paired set with a derived reason."""

    side: ComparisonSide
    site_edge_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    interval_start_s: int = Field(ge=0)
    interval_end_s: int = Field(ge=1)
    direction: str = Field(pattern=_IDENTIFIER_PATTERN)
    vehicle_class: str = Field(pattern=_IDENTIFIER_PATTERN)
    reason: ExclusionReason
    input_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    filled_with_zero: Literal[False] = False


class ComparisonMetricResult(ManchesterComparisonModel):
    """One goodness-of-fit outcome with typed unavailability."""

    metric: GoodnessOfFitMetric
    status: Literal["available", "unavailable"]
    reason: Literal[
        "ok",
        "contract_not_admitted",
        "no_paired_intervals",
        "coverage_below_contract_minimum",
    ]
    unit: ComparisonUnit
    value: Decimal | None = None
    sample_size: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_metric(self) -> ComparisonMetricResult:
        if self.status == "available":
            if self.value is None or self.reason != "ok" or self.sample_size < 1:
                raise ValueError("available metrics need a value, ok reason, and samples")
            if not self.value.is_finite() or self.value < 0:
                raise ValueError("available metric values must be finite and non-negative")
        elif self.value is not None or self.reason == "ok":
            raise ValueError("unavailable metrics cannot carry values or an ok reason")
        return self


class ObservedSimulationComparison(ManchesterComparisonModel):
    """Self-validating comparison containing the exact canonical input inventories."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-10"] = "MAN-10"
    method_version: Literal["manchester-comparison-1.0"] = "manchester-comparison-1.0"
    contract: ManchesterComparisonMetricContract
    contract_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    contract_admitted: bool
    contract_admission: ContractAdmission
    lineage: ComparisonLineage
    lineage_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    observed_inputs: tuple[ObservedComparisonInterval, ...]
    simulated_inputs: tuple[SimulatedComparisonInterval, ...]
    observed_input_rows: int = Field(ge=0)
    simulated_input_rows: int = Field(ge=0)
    observed_input_set_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    simulated_input_set_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    pairs: tuple[AdmittedComparisonPair, ...]
    exclusions: tuple[ExcludedComparisonInterval, ...]
    paired_intervals: int = Field(ge=0)
    excluded_observed: int = Field(ge=0)
    excluded_simulated: int = Field(ge=0)
    paired_observed_coverage: Decimal = Field(ge=0, le=1)
    paired_simulated_coverage: Decimal = Field(ge=0, le=1)
    coverage_requirement_met: bool
    metrics: tuple[ComparisonMetricResult, ...]
    synthetic: bool
    non_causal_descriptive_only: Literal[True] = True
    interpretation_statement: Literal[
        "Paired differences are descriptive software evidence; they do not establish "
        "model quality, realism, or the origin of any difference."
    ] = (
        "Paired differences are descriptive software evidence; they do not establish "
        "model quality, realism, or the origin of any difference."
    )

    @model_validator(mode="after")
    def validate_comparison(self) -> ObservedSimulationComparison:
        derived = _derive_comparison(
            self.contract,
            self.lineage,
            self.observed_inputs,
            self.simulated_inputs,
        )
        expected: dict[str, object] = {
            "contract_fingerprint": self.contract.fingerprint(),
            "contract_admitted": derived.contract_admitted,
            "contract_admission": derived.contract_admission,
            "lineage_fingerprint": self.lineage.fingerprint(),
            "observed_inputs": derived.observed_inputs,
            "simulated_inputs": derived.simulated_inputs,
            "observed_input_rows": len(derived.observed_inputs),
            "simulated_input_rows": len(derived.simulated_inputs),
            "observed_input_set_fingerprint": derived.observed_input_set_fingerprint,
            "simulated_input_set_fingerprint": derived.simulated_input_set_fingerprint,
            "pairs": derived.pairs,
            "exclusions": derived.exclusions,
            "paired_intervals": len(derived.pairs),
            "excluded_observed": derived.excluded_observed,
            "excluded_simulated": derived.excluded_simulated,
            "paired_observed_coverage": derived.paired_observed_coverage,
            "paired_simulated_coverage": derived.paired_simulated_coverage,
            "coverage_requirement_met": derived.coverage_requirement_met,
            "metrics": derived.metrics,
            "synthetic": derived.synthetic,
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must be re-derived from the embedded inputs")
        return self


@dataclass(frozen=True, slots=True)
class _DerivedComparison:
    observed_inputs: tuple[ObservedComparisonInterval, ...]
    simulated_inputs: tuple[SimulatedComparisonInterval, ...]
    contract_admitted: bool
    contract_admission: ContractAdmission
    observed_input_set_fingerprint: str
    simulated_input_set_fingerprint: str
    pairs: tuple[AdmittedComparisonPair, ...]
    exclusions: tuple[ExcludedComparisonInterval, ...]
    excluded_observed: int
    excluded_simulated: int
    paired_observed_coverage: Decimal
    paired_simulated_coverage: Decimal
    coverage_requirement_met: bool
    metrics: tuple[ComparisonMetricResult, ...]
    synthetic: bool


def build_observed_comparison_interval(
    *,
    interval: ComparisonIntervalContent,
    source_row_fingerprint: str,
    synthetic: bool,
    source: ObservedSource,
    source_snapshot_id: str,
    projection_report_fingerprint: str,
    mapping_fingerprint: str,
) -> ObservedComparisonInterval:
    """Build a content/provenance-bound observed comparison input."""

    payload: dict[str, object] = {
        "interval": interval,
        "interval_fingerprint": interval.fingerprint(),
        "source_row_fingerprint": source_row_fingerprint,
        "synthetic": synthetic,
        "source": source,
        "source_snapshot_id": source_snapshot_id,
        "projection_report_fingerprint": projection_report_fingerprint,
        "mapping_fingerprint": mapping_fingerprint,
        "measurement_state": "observed",
        "missing_filled_with_zero": False,
    }
    payload["input_binding_fingerprint"] = _input_binding_from_payload(payload)
    return ObservedComparisonInterval.model_validate(payload)


def build_simulated_comparison_interval(
    *,
    interval: ComparisonIntervalContent,
    source_row_fingerprint: str,
    synthetic: bool,
    network_fingerprint: str,
    calibration_fingerprint: str,
    sumo_run_fingerprint: str,
) -> SimulatedComparisonInterval:
    """Build a content/provenance-bound simulated comparison input."""

    payload: dict[str, object] = {
        "interval": interval,
        "interval_fingerprint": interval.fingerprint(),
        "source_row_fingerprint": source_row_fingerprint,
        "synthetic": synthetic,
        "network_fingerprint": network_fingerprint,
        "calibration_fingerprint": calibration_fingerprint,
        "sumo_run_fingerprint": sumo_run_fingerprint,
        "evidence_kind": "sumo_simulated_interval",
    }
    payload["input_binding_fingerprint"] = _input_binding_from_payload(payload)
    return SimulatedComparisonInterval.model_validate(payload)


def compare_observed_and_simulated(
    contract: ManchesterComparisonMetricContract,
    lineage: ComparisonLineage,
    observed: Sequence[ObservedComparisonInterval],
    simulated: Sequence[SimulatedComparisonInterval],
) -> ObservedSimulationComparison:
    """Derive one exact, non-fusing comparison and embed its canonical inputs."""

    derived = _derive_comparison(contract, lineage, observed, simulated)
    return ObservedSimulationComparison(
        contract=contract,
        contract_fingerprint=contract.fingerprint(),
        contract_admitted=derived.contract_admitted,
        contract_admission=derived.contract_admission,
        lineage=lineage,
        lineage_fingerprint=lineage.fingerprint(),
        observed_inputs=derived.observed_inputs,
        simulated_inputs=derived.simulated_inputs,
        observed_input_rows=len(derived.observed_inputs),
        simulated_input_rows=len(derived.simulated_inputs),
        observed_input_set_fingerprint=derived.observed_input_set_fingerprint,
        simulated_input_set_fingerprint=derived.simulated_input_set_fingerprint,
        pairs=derived.pairs,
        exclusions=derived.exclusions,
        paired_intervals=len(derived.pairs),
        excluded_observed=derived.excluded_observed,
        excluded_simulated=derived.excluded_simulated,
        paired_observed_coverage=derived.paired_observed_coverage,
        paired_simulated_coverage=derived.paired_simulated_coverage,
        coverage_requirement_met=derived.coverage_requirement_met,
        metrics=derived.metrics,
        synthetic=derived.synthetic,
    )


def _derive_comparison(
    contract: ManchesterComparisonMetricContract,
    lineage: ComparisonLineage,
    observed: Sequence[ObservedComparisonInterval],
    simulated: Sequence[SimulatedComparisonInterval],
) -> _DerivedComparison:
    observed_inputs = tuple(sorted(observed, key=_input_sort_key))
    simulated_inputs = tuple(sorted(simulated, key=_input_sort_key))
    if not observed_inputs and not simulated_inputs:
        raise ManchesterComparisonError("NO_INPUT", "at least one input row is required")
    synthetic_flags = {row.synthetic for row in observed_inputs} | {
        row.synthetic for row in simulated_inputs
    }
    if len(synthetic_flags) != 1:
        raise ManchesterComparisonError(
            "MIXED_EVIDENCE", "synthetic and real rows can never enter one comparison"
        )
    synthetic = next(iter(synthetic_flags))
    if contract.evidence_class == "synthetic_development" and not synthetic:
        raise ManchesterComparisonError(
            "CONTRACT_EVIDENCE_CLASS_MISMATCH",
            "a synthetic development contract cannot admit real evidence",
        )
    if contract.evidence_class == "production" and synthetic:
        raise ManchesterComparisonError(
            "CONTRACT_EVIDENCE_CLASS_MISMATCH",
            "a production contract cannot be exercised with synthetic evidence",
        )

    admission = _contract_admission(contract)
    admitted = admission != "not_admitted_production_unapproved"
    exclusions: list[ExcludedComparisonInterval] = []
    observed_valid: dict[tuple[str, int, int, str, str], list[ObservedComparisonInterval]] = {}
    simulated_valid: dict[tuple[str, int, int, str, str], list[SimulatedComparisonInterval]] = {}

    for observed_input in observed_inputs:
        reason = _row_screen_reason_observed(observed_input, contract, lineage)
        if reason is None:
            observed_valid.setdefault(observed_input.pair_key(), []).append(observed_input)
        else:
            exclusions.append(_exclusion("observed", observed_input, reason))
    for simulated_input in simulated_inputs:
        reason = _row_screen_reason_simulated(simulated_input, contract, lineage)
        if reason is None:
            simulated_valid.setdefault(simulated_input.pair_key(), []).append(simulated_input)
        else:
            exclusions.append(_exclusion("simulated", simulated_input, reason))

    observed_unique = _deduplicate("observed", observed_valid, exclusions)
    simulated_unique = _deduplicate("simulated", simulated_valid, exclusions)
    pairs: list[AdmittedComparisonPair] = []
    for key in sorted(set(observed_unique) | set(simulated_unique)):
        observed_row = observed_unique.get(key)
        simulated_row = simulated_unique.get(key)
        if observed_row is not None and simulated_row is not None:
            content = observed_row.interval
            signed = _subtract_quantized(simulated_row.interval.value, content.value)
            pairs.append(
                AdmittedComparisonPair(
                    site_edge_id=content.site_edge_id,
                    interval_start_s=content.interval_start_s,
                    interval_end_s=content.interval_end_s,
                    direction=content.direction,
                    vehicle_class=content.vehicle_class,
                    measure=contract.measure,
                    unit=contract.unit,
                    scope_label=contract.scope_label,
                    scope_fingerprint=contract.scope_fingerprint,
                    time_basis_label=contract.time_basis_label,
                    time_basis_fingerprint=contract.time_basis_fingerprint,
                    observed_value=content.value,
                    simulated_value=simulated_row.interval.value,
                    signed_difference=signed,
                    absolute_difference=signed.copy_abs(),
                    observed_input_fingerprint=observed_row.fingerprint(),
                    simulated_input_fingerprint=simulated_row.fingerprint(),
                    observed_source_row_fingerprint=observed_row.source_row_fingerprint,
                    simulated_source_row_fingerprint=simulated_row.source_row_fingerprint,
                )
            )
        elif observed_row is not None:
            exclusions.append(
                _exclusion("observed", observed_row, "unmatched_no_simulated_counterpart")
            )
        elif simulated_row is not None:
            exclusions.append(
                _exclusion("simulated", simulated_row, "unmatched_no_observed_counterpart")
            )

    pairs.sort(key=_pair_sort_key)
    exclusions.sort(key=_exclusion_sort_key)
    observed_exclusions = sum(item.side == "observed" for item in exclusions)
    simulated_exclusions = sum(item.side == "simulated" for item in exclusions)
    observed_coverage = _ratio_quantized(len(pairs), len(observed_inputs))
    simulated_coverage = _ratio_quantized(len(pairs), len(simulated_inputs))
    coverage_met = bool(pairs) and (
        _ratio_meets_threshold(len(pairs), len(observed_inputs), contract.minimum_observed_coverage)
        and _ratio_meets_threshold(
            len(pairs), len(simulated_inputs), contract.minimum_simulated_coverage
        )
    )
    pair_tuple = tuple(pairs)
    metrics = tuple(
        _expected_metric(name, pair_tuple, admitted, coverage_met, contract.unit)
        for name in contract.goodness_of_fit_metrics
    )
    return _DerivedComparison(
        observed_inputs=observed_inputs,
        simulated_inputs=simulated_inputs,
        contract_admitted=admitted,
        contract_admission=admission,
        observed_input_set_fingerprint=_fingerprint_inputs(observed_inputs),
        simulated_input_set_fingerprint=_fingerprint_inputs(simulated_inputs),
        pairs=pair_tuple,
        exclusions=tuple(exclusions),
        excluded_observed=observed_exclusions,
        excluded_simulated=simulated_exclusions,
        paired_observed_coverage=observed_coverage,
        paired_simulated_coverage=simulated_coverage,
        coverage_requirement_met=coverage_met,
        metrics=metrics,
        synthetic=synthetic,
    )


def _contract_admission(contract: ManchesterComparisonMetricContract) -> ContractAdmission:
    if contract.evidence_class == "synthetic_development":
        return "synthetic_development_inputs"
    if contract.fingerprint() in APPROVED_PRODUCTION_CONTRACT_FINGERPRINTS:
        return "approved_production_contract"
    return "not_admitted_production_unapproved"


def _row_screen_reason_observed(
    row: ObservedComparisonInterval,
    contract: ManchesterComparisonMetricContract,
    lineage: ComparisonLineage,
) -> ExclusionReason | None:
    content = row.interval
    if row.source != contract.observed_source:
        return "source_mismatch"
    reason = _content_screen_reason(content, contract)
    if reason is not None:
        return reason
    if (
        row.projection_report_fingerprint != lineage.projection_report_fingerprint
        or row.mapping_fingerprint != lineage.mapping_fingerprint
        or row.source_snapshot_id not in lineage.observed_snapshot_ids
    ):
        return "lineage_fingerprint_mismatch"
    return None


def _row_screen_reason_simulated(
    row: SimulatedComparisonInterval,
    contract: ManchesterComparisonMetricContract,
    lineage: ComparisonLineage,
) -> ExclusionReason | None:
    reason = _content_screen_reason(row.interval, contract)
    if reason is not None:
        return reason
    if (
        row.network_fingerprint != lineage.network_fingerprint
        or row.calibration_fingerprint != lineage.calibration_fingerprint
        or row.sumo_run_fingerprint != lineage.sumo_run_fingerprint
    ):
        return "lineage_fingerprint_mismatch"
    return None


def _content_screen_reason(
    content: ComparisonIntervalContent,
    contract: ManchesterComparisonMetricContract,
) -> ExclusionReason | None:
    if content.measure != contract.measure:
        return "measure_mismatch"
    if content.unit != contract.unit:
        return "unit_mismatch"
    if (
        content.scope_label != contract.scope_label
        or content.scope_fingerprint != contract.scope_fingerprint
    ):
        return "scope_mismatch"
    if (
        content.time_basis_label != contract.time_basis_label
        or content.time_basis_fingerprint != contract.time_basis_fingerprint
    ):
        return "time_basis_mismatch"
    if content.duration_s() != contract.interval_duration_s:
        return "interval_duration_mismatch"
    return None


def _deduplicate(
    side: ComparisonSide,
    grouped: dict[tuple[str, int, int, str, str], list[_InputT]],
    exclusions: list[ExcludedComparisonInterval],
) -> dict[tuple[str, int, int, str, str], _InputT]:
    unique: dict[tuple[str, int, int, str, str], _InputT] = {}
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=_input_sort_key)
        semantic_values = {row.semantic_key() for row in rows}
        if len(semantic_values) == 1:
            unique[key] = rows[0]
            for extra in rows[1:]:
                exclusions.append(_exclusion(side, extra, "duplicate_identical_row"))
        else:
            for row in rows:
                exclusions.append(_exclusion(side, row, "conflicting_duplicate_rows"))
    return unique


def _exclusion(
    side: ComparisonSide,
    row: _ComparisonInputBase,
    reason: ExclusionReason,
) -> ExcludedComparisonInterval:
    content = row.interval
    return ExcludedComparisonInterval(
        side=side,
        site_edge_id=content.site_edge_id,
        interval_start_s=content.interval_start_s,
        interval_end_s=content.interval_end_s,
        direction=content.direction,
        vehicle_class=content.vehicle_class,
        reason=reason,
        input_fingerprint=row.fingerprint(),
        source_row_fingerprint=row.source_row_fingerprint,
    )


def _expected_metric(
    metric: GoodnessOfFitMetric,
    pairs: Sequence[AdmittedComparisonPair],
    admitted: bool,
    coverage_met: bool,
    unit: ComparisonUnit,
) -> ComparisonMetricResult:
    if not admitted:
        return ComparisonMetricResult(
            metric=metric,
            status="unavailable",
            reason="contract_not_admitted",
            unit=unit,
            sample_size=len(pairs),
        )
    if not pairs:
        return ComparisonMetricResult(
            metric=metric,
            status="unavailable",
            reason="no_paired_intervals",
            unit=unit,
            sample_size=0,
        )
    if not coverage_met:
        return ComparisonMetricResult(
            metric=metric,
            status="unavailable",
            reason="coverage_below_contract_minimum",
            unit=unit,
            sample_size=len(pairs),
        )
    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        count = Decimal(len(pairs))
        exact_differences = [pair.simulated_value - pair.observed_value for pair in pairs]
        if metric == "mae":
            value = (sum((abs(value) for value in exact_differences), Decimal(0)) / count).quantize(
                RESULT_QUANTUM
            )
        else:
            squares = sum((value * value for value in exact_differences), Decimal(0))
            value = (squares / count).sqrt().quantize(RESULT_QUANTUM)
    return ComparisonMetricResult(
        metric=metric,
        status="available",
        reason="ok",
        unit=unit,
        value=value,
        sample_size=len(pairs),
    )


def _input_binding_from_payload(payload: dict[str, object]) -> str:
    interval = payload["interval"]
    if not isinstance(interval, ComparisonIntervalContent):
        raise TypeError("comparison input builders require validated interval content")
    canonical_payload = {
        key: (interval.model_dump(mode="json") if key == "interval" else value)
        for key, value in payload.items()
        if key != "input_binding_fingerprint"
    }
    return sha256_hex(canonical_json(canonical_payload).encode("utf-8"))


def _input_binding_fingerprint(row: _ComparisonInputBase) -> str:
    return sha256_hex(
        canonical_json(row.model_dump(mode="json", exclude={"input_binding_fingerprint"})).encode(
            "utf-8"
        )
    )


def _input_sort_key(row: _ComparisonInputBase) -> tuple[object, ...]:
    return (*row.pair_key(), row.fingerprint())


def _pair_sort_key(pair: AdmittedComparisonPair) -> tuple[object, ...]:
    return (
        pair.site_edge_id,
        pair.interval_start_s,
        pair.interval_end_s,
        pair.direction,
        pair.vehicle_class,
    )


def _exclusion_sort_key(exclusion: ExcludedComparisonInterval) -> tuple[object, ...]:
    return (
        exclusion.side,
        exclusion.site_edge_id,
        exclusion.interval_start_s,
        exclusion.interval_end_s,
        exclusion.direction,
        exclusion.vehicle_class,
        exclusion.reason,
        exclusion.input_fingerprint,
    )


def _subtract_quantized(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        return (left - right).quantize(RESULT_QUANTUM)


def _ratio_quantized(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0.000")
    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        return (Decimal(numerator) / Decimal(denominator)).quantize(RESULT_QUANTUM)


def _ratio_meets_threshold(numerator: int, denominator: int, threshold: Decimal) -> bool:
    if denominator == 0:
        return False
    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        return Decimal(numerator) / Decimal(denominator) >= threshold


def _quantize(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        return value.quantize(RESULT_QUANTUM)


def _fingerprint_inputs(inputs: Sequence[_ComparisonInputBase]) -> str:
    return sha256_hex(canonical_json([row.fingerprint() for row in inputs]).encode("utf-8"))
