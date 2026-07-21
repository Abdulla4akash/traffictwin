"""Strict VEC-08 numerical-reproduction contracts."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VEC_REPRODUCTION_SCHEMA_VERSION = "1.0"
VEC_REPRODUCTION_METHOD_VERSION = "vec-instrumented-reproduction-1.0"
VEC_REPRODUCTION_CAPABILITY_ID = "VEC-08"
PINNED_TOS_DATA_COMMIT = "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"
PINNED_CASE_ID = "ukfleettrain-mappo_we_uk2030_fs0"
PINNED_EXPECTED_FILES = {
    "evals/eval_results_master.csv": (
        "71643348c724afb0bdc4d279813dba0bfd61dda78529d6417f73791f8d9ce7a6"
    ),
    "instrumented/json/ukft_mappo_uk2030_we_fs0.json": (
        "8b2a91881fb2040abb04c441b335e445074b94cf04d854456bad7e31828d5546"
    ),
    "instrumented/perstep/ukft_mappo_uk2030_we_fs0_perstep.npz": (
        "c23c683e0589da0e78f193ceabed418636dc4e93be4f9ee7b4cefaa1aa602775"
    ),
}


class VecReproductionModel(BaseModel):
    """Strict finite base for VEC-08 records."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class VecReproductionGrade(StrEnum):
    """Closed scientific grade for one reproduction attempt."""

    EXACT = "exact"
    NUMERICALLY_EQUIVALENT = "numerically_equivalent"
    DIVERGENT = "divergent"
    REJECTED = "rejected"


class VecComparisonStatus(StrEnum):
    """Outcome of one expected-versus-observed comparison."""

    EXACT = "exact"
    WITHIN_TOLERANCE = "within_tolerance"
    MISMATCH = "mismatch"
    EXCLUDED = "excluded"
    UNAVAILABLE = "unavailable"


class VecReproductionRequest(VecReproductionModel):
    """Pinned request for the single approved VEC-08 reference case."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-08"] = "VEC-08"
    case_id: Literal["ukfleettrain-mappo_we_uk2030_fs0"] = "ukfleettrain-mappo_we_uk2030_fs0"
    expected_commit: Literal["f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"] = (
        "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"
    )
    observed_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tolerance_policy: Literal["vec-reproduction-tolerance-1.0"] = "vec-reproduction-tolerance-1.0"

    def fingerprint(self) -> str:
        """Fingerprint the complete fixed-case verification request."""

        return _sha256(_canonical_json(self.model_dump(mode="json")).encode())


class VecNumericTolerance(VecReproductionModel):
    """Predeclared inclusive numeric tolerance."""

    absolute: float = Field(ge=0)
    relative: float = Field(ge=0)
    max_ulp: int | None = Field(default=None, ge=0)
    rationale: str = Field(min_length=1, max_length=1_000)


class VecReproductionCheck(VecReproductionModel):
    """One deterministic field or array comparison result."""

    artifact: str
    field: str
    status: VecComparisonStatus
    comparison: Literal["exact", "numeric", "semantic", "excluded", "unavailable"]
    expected: str | int | float | bool | list[int] | None = None
    observed: str | int | float | bool | list[int] | None = None
    element_count: int = Field(default=1, ge=0)
    mismatch_count: int = Field(default=0, ge=0)
    max_absolute_error: float | None = Field(default=None, ge=0)
    max_relative_error: float | None = Field(default=None, ge=0)
    max_ulp_error: int | None = Field(default=None, ge=0)
    tolerance: VecNumericTolerance | None = None
    note: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def validate_result(self) -> VecReproductionCheck:
        if self.status is VecComparisonStatus.WITHIN_TOLERANCE and self.tolerance is None:
            raise ValueError("within-tolerance checks require a declared tolerance")
        if self.comparison == "numeric" and self.tolerance is None:
            raise ValueError("numeric comparisons require a declared tolerance")
        if self.status is VecComparisonStatus.EXACT and self.mismatch_count:
            raise ValueError("exact comparisons cannot contain mismatches")
        return self


class VecReproductionSource(VecReproductionModel):
    """Identity of one immutable expected or observed artifact."""

    role: Literal["expected", "observed"]
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")


class VecReproductionSummary(VecReproductionModel):
    """Counts of each comparison outcome."""

    exact: int = Field(ge=0)
    within_tolerance: int = Field(ge=0)
    mismatch: int = Field(ge=0)
    excluded: int = Field(ge=0)
    unavailable: int = Field(ge=0)


class VecRepeatRunEvidence(VecReproductionModel):
    """Exact same-host repeat evidence, excluding only machine wall time."""

    calibration_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acceptance_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    same_execution_controls: bool
    scientific_json_exact: bool
    perstep_arrays_exact: bool
    pertask_arrays_exact: bool
    wall_time_excluded: Literal[True] = True

    @model_validator(mode="after")
    def validate_repeat(self) -> VecRepeatRunEvidence:
        if not (
            self.same_execution_controls
            and self.scientific_json_exact
            and self.perstep_arrays_exact
            and self.pertask_arrays_exact
        ):
            raise ValueError("accepted repeat evidence requires exact scientific outputs")
        if self.calibration_receipt_sha256 == self.acceptance_receipt_sha256:
            raise ValueError("repeat evidence requires two distinct execution receipts")
        return self


class VecReproductionReport(VecReproductionModel):
    """Portable expected-versus-observed VEC-08 evidence."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-08"] = "VEC-08"
    method_version: Literal["vec-instrumented-reproduction-1.0"] = (
        "vec-instrumented-reproduction-1.0"
    )
    grade: VecReproductionGrade
    request: VecReproductionRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    engine_version: Literal["v2_post_nrsus_fix"] = "v2_post_nrsus_fix"
    source_mode: Literal["exact_pinned_git_blobs"] = "exact_pinned_git_blobs"
    campaign: Literal["ukfleettrain_mappo"] = "ukfleettrain_mappo"
    scenario_cell: Literal["we"] = "we"
    evaluation_fleet: Literal["uk2030"] = "uk2030"
    evaluator_seed: Literal[0] = 0
    fleet_seed: Literal[0] = 0
    selected_seed_label: Literal["protocol_seed_not_best_of_seeds"] = (
        "protocol_seed_not_best_of_seeds"
    )
    expected_sources: list[VecReproductionSource]
    observed_sources: list[VecReproductionSource]
    runner_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime: dict[str, str | int]
    tolerance_calibration: str = Field(min_length=1, max_length=2_000)
    repeat_run: VecRepeatRunEvidence | None
    checks: list[VecReproductionCheck]
    summary: VecReproductionSummary
    external_repositories_modified: Literal[False] = False
    raw_inputs_modified: Literal[False] = False
    direct_launch_supported: Literal[False] = False
    interpretation_limits: list[str]

    @model_validator(mode="after")
    def validate_report(self) -> VecReproductionReport:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        counts = {
            status: sum(check.status is status for check in self.checks)
            for status in VecComparisonStatus
        }
        expected = VecReproductionSummary(
            exact=counts[VecComparisonStatus.EXACT],
            within_tolerance=counts[VecComparisonStatus.WITHIN_TOLERANCE],
            mismatch=counts[VecComparisonStatus.MISMATCH],
            excluded=counts[VecComparisonStatus.EXCLUDED],
            unavailable=counts[VecComparisonStatus.UNAVAILABLE],
        )
        if self.summary != expected:
            raise ValueError("comparison summary does not match checks")
        if self.grade in {
            VecReproductionGrade.EXACT,
            VecReproductionGrade.NUMERICALLY_EQUIVALENT,
        }:
            if self.summary.mismatch:
                raise ValueError("accepted grades cannot contain mismatches")
            if self.repeat_run is None:
                raise ValueError("accepted grades require an exact independent repeat run")
        if self.grade is VecReproductionGrade.EXACT and self.summary.within_tolerance:
            raise ValueError("exact grade cannot contain tolerance-dependent checks")
        if self.grade is VecReproductionGrade.DIVERGENT and not self.summary.mismatch:
            raise ValueError("divergent grade requires a mismatch")
        return self

    def fingerprint(self) -> str:
        """Fingerprint the complete reproduction evidence."""

        return _sha256(_canonical_json(self.model_dump(mode="json")).encode())


class VecReproductionContract(VecReproductionModel):
    """Published fixed-case VEC-08 method contract."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["VEC-08"] = "VEC-08"
    method_version: Literal["vec-instrumented-reproduction-1.0"] = (
        "vec-instrumented-reproduction-1.0"
    )
    case_id: str
    expected_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    expected_files: dict[str, str]
    exact_fields: list[str]
    numeric_tolerances: dict[str, VecNumericTolerance]
    excluded_fields: dict[str, str]
    unavailable_comparisons: dict[str, str]
    acceptance_rule: str
    interpretation_limits: list[str]

    def fingerprint(self) -> str:
        """Fingerprint the public reproduction method."""

        return _sha256(_canonical_json(self.model_dump(mode="json")).encode())


SCALAR_TOLERANCE = VecNumericTolerance(
    absolute=1e-7,
    relative=3e-7,
    rationale=(
        "Frozen after the first controlled Apple-arm64 CPU calibration: the only scalar drift was "
        "a 6.04e-8 energy reduction difference; the bound covers float32 reduction order without "
        "covering any task, action, deadline, latency, or fleet-count change."
    ),
)
LATENCY_STREAM_TOLERANCE = VecNumericTolerance(
    absolute=0.00390625,
    relative=3e-7,
    max_ulp=3,
    rationale=(
        "Frozen after the first controlled Apple-arm64 CPU calibration: 9,536 of 32,400 float32 "
        "per-step latency sums differed by at most 0.00390625 ms and three ULPs while every "
        "discrete/state stream and the final latency aggregate matched exactly."
    ),
)


def vec_reproduction_contract() -> VecReproductionContract:
    """Return the immutable public VEC-08 verification method."""

    return VecReproductionContract(
        case_id=PINNED_CASE_ID,
        expected_commit=PINNED_TOS_DATA_COMMIT,
        expected_files=dict(PINNED_EXPECTED_FILES),
        exact_fields=[
            "expected/master row equals expected instrumented JSON",
            "run schema and all scientific fields except avg_energy_j_per_task",
            "per-step schema, dtype, shape, and every array except lat_sum",
            "VEC-07 request identity, output hashes, source/input immutability, and engine labels",
        ],
        numeric_tolerances={
            "run.avg_energy_j_per_task": SCALAR_TOLERANCE,
            "per-step.lat_sum": LATENCY_STREAM_TOLERANCE,
        },
        excluded_fields={
            "run.wall_s": "machine-dependent performance metadata, never a scientific endpoint",
            "run.actor basename": (
                "the isolated runner stages the exact actor blob as actor.npz; semantic identity "
                "is verified from the receipt and hash"
            ),
        },
        unavailable_comparisons={
            "per-task expected artifact": (
                "the source package has no per-task file for this approved weekend case; the "
                "observed file is schema-validated by VEC-07 but not compared numerically"
            )
        },
        acceptance_rule=(
            "numerically_equivalent requires zero mismatches, exact schemas/counts/discrete and "
            "state arrays, and every admitted float difference inside its predeclared inclusive "
            "absolute-or-relative and optional ULP bounds"
        ),
        interpretation_limits=[
            "one protocol-seed weekend case does not establish cross-platform or scenario-wide "
            "equivalence",
            "wall-clock performance is excluded and no speed claim is admitted",
            "per-task expected values are unavailable for this case",
            "VEC-08 reproduction does not itself expose a product direct-launch control",
        ],
    )


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
