"""MAN-09 candidate: deterministic calibration-candidate evaluation.

The module is a pure evidence transformation over caller-supplied, already
completed candidate evidence. One versioned contract binds one observed source,
geographic scope kind, scope, time basis, interval duration, measure, unit,
objective, weighting, missingness, duplicate, denominator, coverage, parameter
bound/grid, precision, tie-break, and interpretation policy. Exact typed inputs
are embedded in every report and every persisted report is fully re-derived
from those inputs during validation.

Hard boundaries:

- no network, filesystem discovery, wall clock, database, UI, LLM, SUMO launch,
  or subprocess use — candidates arrive as completed typed evidence;
- raw observations, map matches, networks, and SUMO results are never edited;
- no demand synthesis: raw counts are never converted into vehicle-generation
  rates, and no DfT AADF value is representable here at all, so AADF can never
  become hourly demand;
- WebTRIS evidence is structurally strategic-road-site scoped;
- a missing observation is never zero, conflicts are never arbitrated, and
  count and speed evidence can never share one objective;
- production objectives and ranking stay unavailable until a lead-reviewed
  contract fingerprint enters the frozen-empty registry below; and
- a ranked candidate is only a candidate selected for analyst review — nothing
  here accepts a baseline, and ``MAN-09`` remains ``planned``.

Self-consistency is tamper evidence, not cryptographic authenticity: an actor
who rebuilds an internally consistent artifact has created new evidence and
still needs the upstream acceptance and publication gates.
"""

from __future__ import annotations

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

MANCHESTER_CALIBRATION_SCHEMA_VERSION = "1.0"
MANCHESTER_CALIBRATION_METHOD_VERSION = "manchester-calibration-1.0"
MANCHESTER_CALIBRATION_CAPABILITY_ID = "MAN-09"

# A production entry requires a reviewed, predeclared calibration study design.
# Keeping this registry empty keeps real objective values and ranking
# unavailable while MAN-09 remains planned.
APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS: frozenset[str] = frozenset()

RESIDUAL_DIRECTION = "simulated_minus_observed"
RESULT_QUANTUM = Decimal("0.001")
_DECIMAL_PRECISION = 28
_MAX_ABSOLUTE_VALUE = Decimal("1000000000")

_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$"
_LABEL_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
_UNIT_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_/%.^*-]{0,31}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"

CalibrationMeasure: TypeAlias = Literal["vehicle_count", "average_speed_mps"]
CalibrationUnit: TypeAlias = Literal["vehicles_per_interval", "m/s"]
CalibrationObjective: TypeAlias = Literal["mean_absolute_error", "root_mean_square_error"]
CalibrationSide: TypeAlias = Literal["observed", "simulated"]
ObservedSource: TypeAlias = Literal["dft_raw_count", "webtris_daily", "synthetic_utc_road"]
ScopeKind: TypeAlias = Literal["strategic_road_site", "urban_zone", "synthetic_zone"]
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

_MEASURE_UNITS: dict[CalibrationMeasure, CalibrationUnit] = {
    "vehicle_count": "vehicles_per_interval",
    "average_speed_mps": "m/s",
}

# Structural source semantics: WebTRIS evidence stays strategic-road-site
# scoped, DfT raw counts stay urban-zone scoped, synthetic fixtures stay in
# clearly labelled synthetic zones.
_SOURCE_SCOPE_KINDS: dict[ObservedSource, ScopeKind] = {
    "dft_raw_count": "urban_zone",
    "webtris_daily": "strategic_road_site",
    "synthetic_utc_road": "synthetic_zone",
}

_InputT = TypeVar("_InputT", bound="_CalibrationInputBase")
_PairKey: TypeAlias = tuple[str, int, int, str, str]


class ManchesterCalibrationError(ValueError):
    """Typed caller-side misuse of the calibration boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterCalibrationModel(ManchesterSnapshotModel):
    """Strict frozen base for deterministic MAN-09 artifacts."""


class CalibrationParameterBound(ManchesterCalibrationModel):
    """One bounded calibration parameter with its exact permitted grid."""

    name: str = Field(pattern=_LABEL_PATTERN)
    unit: str = Field(pattern=_UNIT_PATTERN)
    lower_bound: Decimal
    upper_bound: Decimal
    permitted_values: tuple[Decimal, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_bound(self) -> CalibrationParameterBound:
        values = (self.lower_bound, self.upper_bound, *self.permitted_values)
        for value in values:
            if not value.is_finite() or value.copy_abs() > _MAX_ABSOLUTE_VALUE:
                raise ValueError("parameter bounds and grid values must be finite and bounded")
        if self.lower_bound > self.upper_bound:
            raise ValueError("the lower bound cannot exceed the upper bound")
        grid = list(self.permitted_values)
        if any(later <= earlier for earlier, later in zip(grid, grid[1:], strict=False)):
            raise ValueError("the permitted grid must be strictly increasing")
        if any(value < self.lower_bound or value > self.upper_bound for value in grid):
            raise ValueError("every permitted grid value must lie inside the bounds")
        return self


class ManchesterCalibrationContract(ManchesterCalibrationModel):
    """Every methodological decision for one non-fusing candidate evaluation."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-calibration-1.0"] = "manchester-calibration-1.0"
    contract_version: str = Field(pattern=_LABEL_PATTERN)
    evidence_class: Literal["synthetic_development", "production"]
    observed_source: ObservedSource
    scope_kind: ScopeKind
    scope_label: str = Field(pattern=_LABEL_PATTERN)
    scope_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    time_basis_label: str = Field(pattern=_LABEL_PATTERN)
    time_basis_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    source_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    projection_report_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    mapping_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    network_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    interval_duration_s: int = Field(ge=1, le=86_400)
    measure: CalibrationMeasure
    unit: CalibrationUnit
    pairing_key_fields: tuple[
        Literal["site_edge_id"],
        Literal["interval_start_s"],
        Literal["interval_end_s"],
        Literal["direction"],
        Literal["vehicle_class"],
    ] = ("site_edge_id", "interval_start_s", "interval_end_s", "direction", "vehicle_class")
    objective: CalibrationObjective
    residual_direction: Literal["simulated_minus_observed"] = "simulated_minus_observed"
    weighting_policy: Literal["equal_interval"] = "equal_interval"
    missing_policy: Literal["exclude_unpaired_never_zero"] = "exclude_unpaired_never_zero"
    duplicate_policy: Literal["collapse_identical_exclude_conflicts"] = (
        "collapse_identical_exclude_conflicts"
    )
    denominator_policy: Literal["all_input_rows_per_side"] = "all_input_rows_per_side"
    minimum_observed_coverage: Decimal = Field(ge=0, le=1)
    minimum_simulated_coverage: Decimal = Field(ge=0, le=1)
    parameters: tuple[CalibrationParameterBound, ...] = Field(min_length=1, max_length=16)
    demand_synthesis: Literal["none_supplied_candidate_evidence_only"] = (
        "none_supplied_candidate_evidence_only"
    )
    source_fusion: Literal["none"] = "none"
    unit_conversion: Literal["none"] = "none"
    interval_aggregation: Literal["exact_interval_no_resampling"] = "exact_interval_no_resampling"
    rounding_mode: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    result_quantum: Literal["0.001"] = "0.001"
    tie_break_policy: Literal["objective_value_then_candidate_binding_fingerprint"] = (
        "objective_value_then_candidate_binding_fingerprint"
    )
    interpretation_policy: Literal["descriptive_candidate_review_only"] = (
        "descriptive_candidate_review_only"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ManchesterCalibrationContract:
        if self.unit != _MEASURE_UNITS[self.measure]:
            raise ValueError("the contract unit must be the fixed unit of its measure")
        if self.observed_source == "dft_raw_count" and self.measure != "vehicle_count":
            raise ValueError("DfT raw-count contracts can calibrate vehicle counts only")
        if self.scope_kind != _SOURCE_SCOPE_KINDS[self.observed_source]:
            raise ValueError("the scope kind must be the fixed scope kind of its source")
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
        names = [bound.name for bound in self.parameters]
        if names != sorted(set(names)):
            raise ValueError("parameter bounds must be sorted by unique name")
        return self


class CalibrationIntervalContent(ManchesterCalibrationModel):
    """Scientific content shared by one observed or simulated interval."""

    site_edge_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    interval_start_s: int = Field(ge=0, le=31_536_000)
    interval_end_s: int = Field(ge=1, le=31_536_000)
    direction: str = Field(pattern=_IDENTIFIER_PATTERN)
    vehicle_class: str = Field(pattern=_IDENTIFIER_PATTERN)
    measure: CalibrationMeasure
    unit: CalibrationUnit
    value: Decimal = Field(ge=0)
    scope_kind: ScopeKind
    scope_label: str = Field(pattern=_LABEL_PATTERN)
    scope_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    time_basis_label: str = Field(pattern=_LABEL_PATTERN)
    time_basis_fingerprint: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_content(self) -> CalibrationIntervalContent:
        if self.interval_end_s <= self.interval_start_s:
            raise ValueError("interval end must be after its start")
        if self.unit != _MEASURE_UNITS[self.measure]:
            raise ValueError("interval unit must be the fixed unit of its measure")
        if not self.value.is_finite() or self.value > _MAX_ABSOLUTE_VALUE:
            raise ValueError("calibration values must be finite and bounded")
        return self

    def pair_key(self) -> _PairKey:
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
            self.scope_kind,
            self.scope_label,
            self.scope_fingerprint,
            self.time_basis_label,
            self.time_basis_fingerprint,
        )


class _CalibrationInputBase(ManchesterCalibrationModel):
    """One content-bound calibration input plus its upstream provenance reference."""

    interval: CalibrationIntervalContent
    interval_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    input_binding_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    synthetic: bool

    @model_validator(mode="after")
    def validate_input_binding(self) -> _CalibrationInputBase:
        if self.interval_fingerprint != self.interval.fingerprint():
            raise ValueError("interval fingerprint must bind the embedded interval")
        if self.input_binding_fingerprint != _input_binding_fingerprint(self):
            raise ValueError("input binding fingerprint must bind content and provenance")
        return self

    def pair_key(self) -> _PairKey:
        return self.interval.pair_key()

    def semantic_key(self) -> tuple[object, ...]:
        return (*self.interval.semantic_key(), self.synthetic)


class ObservedCalibrationInterval(_CalibrationInputBase):
    """One observed interval bound to snapshot, projection, and mapping evidence."""

    source: ObservedSource
    source_snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    source_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    projection_report_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    mapping_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    measurement_state: Literal["observed"] = "observed"
    missing_filled_with_zero: Literal[False] = False

    @model_validator(mode="after")
    def validate_source_semantics(self) -> ObservedCalibrationInterval:
        if self.source == "dft_raw_count" and self.interval.measure != "vehicle_count":
            raise ValueError("DfT raw-count evidence cannot represent speed")
        if self.interval.scope_kind != _SOURCE_SCOPE_KINDS[self.source]:
            raise ValueError("observed scope kind must be the fixed scope kind of its source")
        if self.synthetic != (self.source == "synthetic_utc_road"):
            raise ValueError("observed source and synthetic evidence state must agree")
        return self


class SimulatedCalibrationInterval(_CalibrationInputBase):
    """One simulated interval bound to network and SUMO-run evidence."""

    network_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    sumo_run_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    evidence_kind: Literal["sumo_simulated_interval"] = "sumo_simulated_interval"


class CalibrationParameterValue(ManchesterCalibrationModel):
    """One exact candidate parameter assignment."""

    name: str = Field(pattern=_LABEL_PATTERN)
    value: Decimal

    @model_validator(mode="after")
    def validate_value(self) -> CalibrationParameterValue:
        if not self.value.is_finite() or self.value.copy_abs() > _MAX_ABSOLUTE_VALUE:
            raise ValueError("parameter values must be finite and bounded")
        return self


class CalibrationCandidateInput(ManchesterCalibrationModel):
    """One caller-supplied, already-completed candidate and its simulated evidence."""

    candidate_label: str = Field(pattern=_LABEL_PATTERN)
    parameter_values: tuple[CalibrationParameterValue, ...] = Field(min_length=1, max_length=16)
    sumo_run_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    simulated_inputs: tuple[SimulatedCalibrationInterval, ...] = Field(max_length=100_000)

    @model_validator(mode="after")
    def validate_candidate(self) -> CalibrationCandidateInput:
        names = [item.name for item in self.parameter_values]
        if names != sorted(set(names)):
            raise ValueError("candidate parameter values must be sorted by unique name")
        return self


class CalibrationEvidencePair(ManchesterCalibrationModel):
    """One exactly paired interval with recomputable residuals and input bindings."""

    site_edge_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    interval_start_s: int = Field(ge=0)
    interval_end_s: int = Field(ge=1)
    direction: str = Field(pattern=_IDENTIFIER_PATTERN)
    vehicle_class: str = Field(pattern=_IDENTIFIER_PATTERN)
    measure: CalibrationMeasure
    unit: CalibrationUnit
    scope_kind: ScopeKind
    scope_label: str = Field(pattern=_LABEL_PATTERN)
    scope_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    time_basis_label: str = Field(pattern=_LABEL_PATTERN)
    time_basis_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    observed_value: Decimal = Field(ge=0)
    simulated_value: Decimal = Field(ge=0)
    residual_direction: Literal["simulated_minus_observed"] = "simulated_minus_observed"
    signed_residual: Decimal
    absolute_residual: Decimal = Field(ge=0)
    observed_input_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    simulated_input_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    observed_source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    simulated_source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_pair(self) -> CalibrationEvidencePair:
        if self.interval_end_s <= self.interval_start_s:
            raise ValueError("interval end must be after its start")
        for value in (self.observed_value, self.simulated_value, self.signed_residual):
            if not value.is_finite():
                raise ValueError("paired values and residuals must be finite")
        expected = _subtract_quantized(self.simulated_value, self.observed_value)
        if self.signed_residual != expected:
            raise ValueError("signed_residual must be simulated minus observed")
        if self.absolute_residual != expected.copy_abs():
            raise ValueError("absolute_residual must be the signed-residual magnitude")
        return self


class ExcludedCalibrationInterval(ManchesterCalibrationModel):
    """One exact input retained outside the paired set with a derived reason."""

    side: CalibrationSide
    site_edge_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    interval_start_s: int = Field(ge=0)
    interval_end_s: int = Field(ge=1)
    direction: str = Field(pattern=_IDENTIFIER_PATTERN)
    vehicle_class: str = Field(pattern=_IDENTIFIER_PATTERN)
    reason: ExclusionReason
    input_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    source_row_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    filled_with_zero: Literal[False] = False


class CalibrationObjectiveResult(ManchesterCalibrationModel):
    """One objective outcome with typed unavailability."""

    objective: CalibrationObjective
    status: Literal["available", "unavailable"]
    reason: Literal[
        "ok",
        "contract_not_admitted",
        "no_paired_intervals",
        "coverage_below_contract_minimum",
    ]
    unit: CalibrationUnit
    value: Decimal | None = None
    sample_size: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_objective(self) -> CalibrationObjectiveResult:
        if self.status == "available":
            if self.value is None or self.reason != "ok" or self.sample_size < 1:
                raise ValueError("available objectives need a value, ok reason, and samples")
            if not self.value.is_finite() or self.value < 0:
                raise ValueError("available objective values must be finite and non-negative")
        elif self.value is not None or self.reason == "ok":
            raise ValueError("unavailable objectives cannot carry values or an ok reason")
        return self


class CalibrationCandidateEvaluation(ManchesterCalibrationModel):
    """One fully derived candidate evaluation embedding its exact simulated inputs."""

    candidate_label: str = Field(pattern=_LABEL_PATTERN)
    parameter_values: tuple[CalibrationParameterValue, ...] = Field(min_length=1, max_length=16)
    sumo_run_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    simulated_inputs: tuple[SimulatedCalibrationInterval, ...]
    simulated_input_rows: int = Field(ge=0)
    simulated_input_set_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    candidate_binding_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    pairs: tuple[CalibrationEvidencePair, ...]
    exclusions: tuple[ExcludedCalibrationInterval, ...]
    paired_intervals: int = Field(ge=0)
    excluded_observed: int = Field(ge=0)
    excluded_simulated: int = Field(ge=0)
    paired_observed_coverage: Decimal = Field(ge=0, le=1)
    paired_simulated_coverage: Decimal = Field(ge=0, le=1)
    coverage_requirement_met: bool
    objective_result: CalibrationObjectiveResult

    @model_validator(mode="after")
    def validate_evaluation(self) -> CalibrationCandidateEvaluation:
        names = [item.name for item in self.parameter_values]
        if names != sorted(set(names)):
            raise ValueError("evaluation parameter values must be sorted by unique name")
        return self


class ManchesterCalibrationReport(ManchesterCalibrationModel):
    """Self-validating candidate evaluation report embedding its canonical inputs."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-calibration-1.0"] = "manchester-calibration-1.0"
    contract: ManchesterCalibrationContract
    contract_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    contract_admitted: bool
    contract_admission: ContractAdmission
    observed_inputs: tuple[ObservedCalibrationInterval, ...]
    observed_input_rows: int = Field(ge=1)
    observed_input_set_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    candidate_evaluations: tuple[CalibrationCandidateEvaluation, ...] = Field(min_length=1)
    ranking: tuple[str, ...]
    selected_candidate_label: str | None
    selection_status: Literal[
        "candidate_selected_for_analyst_review",
        "no_candidate_available",
    ]
    automatic_acceptance: Literal[False] = False
    baseline_available: Literal[False] = False
    synthetic: bool
    non_causal_descriptive_only: Literal[True] = True
    interpretation_statement: Literal[
        "Candidate objective values are descriptive software evidence for analyst "
        "review; they do not establish realism, model quality, or the origin of any "
        "difference, and no candidate is accepted automatically."
    ] = (
        "Candidate objective values are descriptive software evidence for analyst "
        "review; they do not establish realism, model quality, or the origin of any "
        "difference, and no candidate is accepted automatically."
    )

    @model_validator(mode="after")
    def validate_report(self) -> ManchesterCalibrationReport:
        candidates = tuple(
            CalibrationCandidateInput(
                candidate_label=evaluation.candidate_label,
                parameter_values=evaluation.parameter_values,
                sumo_run_fingerprint=evaluation.sumo_run_fingerprint,
                simulated_inputs=evaluation.simulated_inputs,
            )
            for evaluation in self.candidate_evaluations
        )
        derived = _derive_report(self.contract, self.observed_inputs, candidates)
        expected: dict[str, object] = {
            "contract_fingerprint": self.contract.fingerprint(),
            "contract_admitted": derived.contract_admitted,
            "contract_admission": derived.contract_admission,
            "observed_inputs": derived.observed_inputs,
            "observed_input_rows": len(derived.observed_inputs),
            "observed_input_set_fingerprint": derived.observed_input_set_fingerprint,
            "candidate_evaluations": derived.candidate_evaluations,
            "ranking": derived.ranking,
            "selected_candidate_label": derived.selected_candidate_label,
            "selection_status": derived.selection_status,
            "synthetic": derived.synthetic,
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError(f"{field_name} must be re-derived from the embedded inputs")
        return self


@dataclass(frozen=True, slots=True)
class _DerivedReport:
    observed_inputs: tuple[ObservedCalibrationInterval, ...]
    contract_admitted: bool
    contract_admission: ContractAdmission
    observed_input_set_fingerprint: str
    candidate_evaluations: tuple[CalibrationCandidateEvaluation, ...]
    ranking: tuple[str, ...]
    selected_candidate_label: str | None
    selection_status: Literal[
        "candidate_selected_for_analyst_review",
        "no_candidate_available",
    ]
    synthetic: bool


def build_observed_calibration_interval(
    *,
    interval: CalibrationIntervalContent,
    source_row_fingerprint: str,
    synthetic: bool,
    source: ObservedSource,
    source_snapshot_id: str,
    source_fingerprint: str,
    projection_report_fingerprint: str,
    mapping_fingerprint: str,
) -> ObservedCalibrationInterval:
    """Build a content/provenance-bound observed calibration input."""

    payload: dict[str, object] = {
        "interval": interval,
        "interval_fingerprint": interval.fingerprint(),
        "source_row_fingerprint": source_row_fingerprint,
        "synthetic": synthetic,
        "source": source,
        "source_snapshot_id": source_snapshot_id,
        "source_fingerprint": source_fingerprint,
        "projection_report_fingerprint": projection_report_fingerprint,
        "mapping_fingerprint": mapping_fingerprint,
        "measurement_state": "observed",
        "missing_filled_with_zero": False,
    }
    payload["input_binding_fingerprint"] = _input_binding_from_payload(payload)
    return ObservedCalibrationInterval.model_validate(payload)


def build_simulated_calibration_interval(
    *,
    interval: CalibrationIntervalContent,
    source_row_fingerprint: str,
    synthetic: bool,
    network_fingerprint: str,
    sumo_run_fingerprint: str,
) -> SimulatedCalibrationInterval:
    """Build a content/provenance-bound simulated calibration input."""

    payload: dict[str, object] = {
        "interval": interval,
        "interval_fingerprint": interval.fingerprint(),
        "source_row_fingerprint": source_row_fingerprint,
        "synthetic": synthetic,
        "network_fingerprint": network_fingerprint,
        "sumo_run_fingerprint": sumo_run_fingerprint,
        "evidence_kind": "sumo_simulated_interval",
    }
    payload["input_binding_fingerprint"] = _input_binding_from_payload(payload)
    return SimulatedCalibrationInterval.model_validate(payload)


def evaluate_calibration_candidates(
    contract: ManchesterCalibrationContract,
    observed: Sequence[ObservedCalibrationInterval],
    candidates: Sequence[CalibrationCandidateInput],
) -> ManchesterCalibrationReport:
    """Evaluate supplied completed candidates and embed the exact canonical inputs."""

    derived = _derive_report(contract, observed, candidates)
    return ManchesterCalibrationReport(
        contract=contract,
        contract_fingerprint=contract.fingerprint(),
        contract_admitted=derived.contract_admitted,
        contract_admission=derived.contract_admission,
        observed_inputs=derived.observed_inputs,
        observed_input_rows=len(derived.observed_inputs),
        observed_input_set_fingerprint=derived.observed_input_set_fingerprint,
        candidate_evaluations=derived.candidate_evaluations,
        ranking=derived.ranking,
        selected_candidate_label=derived.selected_candidate_label,
        selection_status=derived.selection_status,
        synthetic=derived.synthetic,
    )


def _derive_report(
    contract: ManchesterCalibrationContract,
    observed: Sequence[ObservedCalibrationInterval],
    candidates: Sequence[CalibrationCandidateInput],
) -> _DerivedReport:
    observed_inputs = tuple(sorted(observed, key=_input_sort_key))
    if not observed_inputs or not candidates:
        raise ManchesterCalibrationError(
            "NO_INPUT", "at least one observed row and one candidate are required"
        )
    labels = [candidate.candidate_label for candidate in candidates]
    if len(set(labels)) != len(labels):
        raise ManchesterCalibrationError(
            "DUPLICATE_CANDIDATE_LABEL", "candidate labels must be unique"
        )
    ordered_candidates = tuple(sorted(candidates, key=lambda item: item.candidate_label))
    for candidate in ordered_candidates:
        _validate_candidate_parameters(contract, candidate)

    synthetic_flags = {row.synthetic for row in observed_inputs}
    for candidate in ordered_candidates:
        synthetic_flags |= {row.synthetic for row in candidate.simulated_inputs}
    if len(synthetic_flags) != 1:
        raise ManchesterCalibrationError(
            "MIXED_EVIDENCE", "synthetic and real rows can never enter one evaluation"
        )
    synthetic = next(iter(synthetic_flags))
    if contract.evidence_class == "synthetic_development" and not synthetic:
        raise ManchesterCalibrationError(
            "CONTRACT_EVIDENCE_CLASS_MISMATCH",
            "a synthetic development contract cannot admit real evidence",
        )
    if contract.evidence_class == "production" and synthetic:
        raise ManchesterCalibrationError(
            "CONTRACT_EVIDENCE_CLASS_MISMATCH",
            "a production contract cannot be exercised with synthetic evidence",
        )

    admission = _contract_admission(contract)
    admitted = admission != "not_admitted_production_unapproved"
    evaluations = tuple(
        _derive_candidate(contract, observed_inputs, candidate, admitted)
        for candidate in ordered_candidates
    )
    available = [
        evaluation
        for evaluation in evaluations
        if evaluation.objective_result.status == "available"
    ]
    ranked = sorted(
        available,
        key=lambda item: (
            item.objective_result.value if item.objective_result.value is not None else Decimal(0),
            item.candidate_binding_fingerprint,
        ),
    )
    ranking = tuple(item.candidate_label for item in ranked)
    selected = ranking[0] if ranking else None
    selection_status: Literal[
        "candidate_selected_for_analyst_review",
        "no_candidate_available",
    ] = (
        "candidate_selected_for_analyst_review"
        if selected is not None
        else ("no_candidate_available")
    )
    return _DerivedReport(
        observed_inputs=observed_inputs,
        contract_admitted=admitted,
        contract_admission=admission,
        observed_input_set_fingerprint=_fingerprint_inputs(observed_inputs),
        candidate_evaluations=evaluations,
        ranking=ranking,
        selected_candidate_label=selected,
        selection_status=selection_status,
        synthetic=synthetic,
    )


def _derive_candidate(
    contract: ManchesterCalibrationContract,
    observed_inputs: tuple[ObservedCalibrationInterval, ...],
    candidate: CalibrationCandidateInput,
    admitted: bool,
) -> CalibrationCandidateEvaluation:
    simulated_inputs = tuple(sorted(candidate.simulated_inputs, key=_input_sort_key))
    exclusions: list[ExcludedCalibrationInterval] = []
    observed_valid: dict[_PairKey, list[ObservedCalibrationInterval]] = {}
    simulated_valid: dict[_PairKey, list[SimulatedCalibrationInterval]] = {}

    for observed_input in observed_inputs:
        reason = _row_screen_reason_observed(observed_input, contract)
        if reason is None:
            observed_valid.setdefault(observed_input.pair_key(), []).append(observed_input)
        else:
            exclusions.append(_exclusion("observed", observed_input, reason))
    for simulated_input in simulated_inputs:
        reason = _row_screen_reason_simulated(simulated_input, contract, candidate)
        if reason is None:
            simulated_valid.setdefault(simulated_input.pair_key(), []).append(simulated_input)
        else:
            exclusions.append(_exclusion("simulated", simulated_input, reason))

    observed_unique = _deduplicate("observed", observed_valid, exclusions)
    simulated_unique = _deduplicate("simulated", simulated_valid, exclusions)
    pairs: list[CalibrationEvidencePair] = []
    for key in sorted(set(observed_unique) | set(simulated_unique)):
        observed_row = observed_unique.get(key)
        simulated_row = simulated_unique.get(key)
        if observed_row is not None and simulated_row is not None:
            content = observed_row.interval
            signed = _subtract_quantized(simulated_row.interval.value, content.value)
            pairs.append(
                CalibrationEvidencePair(
                    site_edge_id=content.site_edge_id,
                    interval_start_s=content.interval_start_s,
                    interval_end_s=content.interval_end_s,
                    direction=content.direction,
                    vehicle_class=content.vehicle_class,
                    measure=contract.measure,
                    unit=contract.unit,
                    scope_kind=contract.scope_kind,
                    scope_label=contract.scope_label,
                    scope_fingerprint=contract.scope_fingerprint,
                    time_basis_label=contract.time_basis_label,
                    time_basis_fingerprint=contract.time_basis_fingerprint,
                    observed_value=content.value,
                    simulated_value=simulated_row.interval.value,
                    signed_residual=signed,
                    absolute_residual=signed.copy_abs(),
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
    return CalibrationCandidateEvaluation(
        candidate_label=candidate.candidate_label,
        parameter_values=candidate.parameter_values,
        sumo_run_fingerprint=candidate.sumo_run_fingerprint,
        simulated_inputs=simulated_inputs,
        simulated_input_rows=len(simulated_inputs),
        simulated_input_set_fingerprint=_fingerprint_inputs(simulated_inputs),
        candidate_binding_fingerprint=_candidate_binding_fingerprint(candidate, simulated_inputs),
        pairs=pair_tuple,
        exclusions=tuple(exclusions),
        paired_intervals=len(pair_tuple),
        excluded_observed=observed_exclusions,
        excluded_simulated=simulated_exclusions,
        paired_observed_coverage=observed_coverage,
        paired_simulated_coverage=simulated_coverage,
        coverage_requirement_met=coverage_met,
        objective_result=_expected_objective(
            contract.objective, pair_tuple, admitted, coverage_met, contract.unit
        ),
    )


def _validate_candidate_parameters(
    contract: ManchesterCalibrationContract,
    candidate: CalibrationCandidateInput,
) -> None:
    bounds = {bound.name: bound for bound in contract.parameters}
    values = {item.name: item.value for item in candidate.parameter_values}
    if sorted(values) != sorted(bounds):
        raise ManchesterCalibrationError(
            "PARAMETER_CONTRACT_MISMATCH",
            f"candidate {candidate.candidate_label!r} must assign exactly the "
            "contract-declared parameters",
        )
    for name in sorted(values):
        bound = bounds[name]
        value = values[name]
        if value < bound.lower_bound or value > bound.upper_bound:
            raise ManchesterCalibrationError(
                "PARAMETER_OUT_OF_BOUNDS",
                f"candidate {candidate.candidate_label!r} parameter {name!r} is "
                "outside its contract bounds",
            )
        if all(value != permitted for permitted in bound.permitted_values):
            raise ManchesterCalibrationError(
                "PARAMETER_NOT_IN_PERMITTED_GRID",
                f"candidate {candidate.candidate_label!r} parameter {name!r} is "
                "not on the contract-permitted grid",
            )


def _contract_admission(contract: ManchesterCalibrationContract) -> ContractAdmission:
    if contract.evidence_class == "synthetic_development":
        return "synthetic_development_inputs"
    if contract.fingerprint() in APPROVED_PRODUCTION_CALIBRATION_CONTRACT_FINGERPRINTS:
        return "approved_production_contract"
    return "not_admitted_production_unapproved"


def _row_screen_reason_observed(
    row: ObservedCalibrationInterval,
    contract: ManchesterCalibrationContract,
) -> ExclusionReason | None:
    if row.source != contract.observed_source:
        return "source_mismatch"
    reason = _content_screen_reason(row.interval, contract)
    if reason is not None:
        return reason
    if (
        row.source_fingerprint != contract.source_fingerprint
        or row.projection_report_fingerprint != contract.projection_report_fingerprint
        or row.mapping_fingerprint != contract.mapping_fingerprint
    ):
        return "lineage_fingerprint_mismatch"
    return None


def _row_screen_reason_simulated(
    row: SimulatedCalibrationInterval,
    contract: ManchesterCalibrationContract,
    candidate: CalibrationCandidateInput,
) -> ExclusionReason | None:
    reason = _content_screen_reason(row.interval, contract)
    if reason is not None:
        return reason
    if (
        row.network_fingerprint != contract.network_fingerprint
        or row.sumo_run_fingerprint != candidate.sumo_run_fingerprint
    ):
        return "lineage_fingerprint_mismatch"
    return None


def _content_screen_reason(
    content: CalibrationIntervalContent,
    contract: ManchesterCalibrationContract,
) -> ExclusionReason | None:
    if content.measure != contract.measure:
        return "measure_mismatch"
    if content.unit != contract.unit:
        return "unit_mismatch"
    if (
        content.scope_kind != contract.scope_kind
        or content.scope_label != contract.scope_label
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
    side: CalibrationSide,
    grouped: dict[_PairKey, list[_InputT]],
    exclusions: list[ExcludedCalibrationInterval],
) -> dict[_PairKey, _InputT]:
    unique: dict[_PairKey, _InputT] = {}
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
    side: CalibrationSide,
    row: _CalibrationInputBase,
    reason: ExclusionReason,
) -> ExcludedCalibrationInterval:
    content = row.interval
    return ExcludedCalibrationInterval(
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


def _expected_objective(
    objective: CalibrationObjective,
    pairs: Sequence[CalibrationEvidencePair],
    admitted: bool,
    coverage_met: bool,
    unit: CalibrationUnit,
) -> CalibrationObjectiveResult:
    if not admitted:
        return CalibrationObjectiveResult(
            objective=objective,
            status="unavailable",
            reason="contract_not_admitted",
            unit=unit,
            sample_size=len(pairs),
        )
    if not pairs:
        return CalibrationObjectiveResult(
            objective=objective,
            status="unavailable",
            reason="no_paired_intervals",
            unit=unit,
            sample_size=0,
        )
    if not coverage_met:
        return CalibrationObjectiveResult(
            objective=objective,
            status="unavailable",
            reason="coverage_below_contract_minimum",
            unit=unit,
            sample_size=len(pairs),
        )
    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        count = Decimal(len(pairs))
        exact_residuals = [pair.simulated_value - pair.observed_value for pair in pairs]
        if objective == "mean_absolute_error":
            value = (
                sum((residual.copy_abs() for residual in exact_residuals), Decimal(0)) / count
            ).quantize(RESULT_QUANTUM)
        else:
            squares = sum((residual * residual for residual in exact_residuals), Decimal(0))
            value = (squares / count).sqrt().quantize(RESULT_QUANTUM)
    return CalibrationObjectiveResult(
        objective=objective,
        status="available",
        reason="ok",
        unit=unit,
        value=value,
        sample_size=len(pairs),
    )


def _candidate_binding_fingerprint(
    candidate: CalibrationCandidateInput,
    simulated_inputs: tuple[SimulatedCalibrationInterval, ...],
) -> str:
    payload = {
        "candidate_label": candidate.candidate_label,
        "parameter_values": [
            {"name": item.name, "value": str(item.value)} for item in candidate.parameter_values
        ],
        "sumo_run_fingerprint": candidate.sumo_run_fingerprint,
        "simulated_input_fingerprints": [row.fingerprint() for row in simulated_inputs],
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))


def _input_binding_from_payload(payload: dict[str, object]) -> str:
    interval = payload["interval"]
    if not isinstance(interval, CalibrationIntervalContent):
        raise TypeError("calibration input builders require validated interval content")
    canonical_payload = {
        key: (interval.model_dump(mode="json") if key == "interval" else value)
        for key, value in payload.items()
        if key != "input_binding_fingerprint"
    }
    return sha256_hex(canonical_json(canonical_payload).encode("utf-8"))


def _input_binding_fingerprint(row: _CalibrationInputBase) -> str:
    return sha256_hex(
        canonical_json(row.model_dump(mode="json", exclude={"input_binding_fingerprint"})).encode(
            "utf-8"
        )
    )


def _input_sort_key(row: _CalibrationInputBase) -> tuple[object, ...]:
    return (*row.pair_key(), row.fingerprint())


def _pair_sort_key(pair: CalibrationEvidencePair) -> tuple[object, ...]:
    return (
        pair.site_edge_id,
        pair.interval_start_s,
        pair.interval_end_s,
        pair.direction,
        pair.vehicle_class,
    )


def _exclusion_sort_key(exclusion: ExcludedCalibrationInterval) -> tuple[object, ...]:
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


def _fingerprint_inputs(inputs: Sequence[_CalibrationInputBase]) -> str:
    return sha256_hex(canonical_json([row.fingerprint() for row in inputs]).encode("utf-8"))
