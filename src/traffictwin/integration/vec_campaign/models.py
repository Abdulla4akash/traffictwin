"""Strict contracts for bounded, predeclared VEC campaign execution.

A campaign is the deterministic execution of one *already predeclared* run
matrix: fixed factors, named arms, a fixed seed set, and one primary endpoint,
all decided before any result is visible. The contracts here exist to make the
predeclaration binding at execution time — a campaign cannot be constructed
without a recorded human approval that binds the exact predeclaration bytes,
and it cannot consume reserved held-out seeds without separate authorisation.

Code cannot verify that a person truly approved a design. It can refuse to run
without an explicit approval record, refuse to run if the approved document
changed afterwards, and keep both facts in the receipt. That is the boundary
this module implements; it never infers, defaults, or manufactures approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.integration.vec_fresh_admission.models import VecPairingSeedSource
from traffictwin.integration.vec_runner.models import (
    PINNED_REVIEWED_TRACES,
    VecFleet,
    VecRunRequest,
)

VEC_CAMPAIGN_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_CAMPAIGN_METHOD_VERSION: Literal["vec-bounded-campaign-1.0"] = "vec-bounded-campaign-1.0"

#: Hard ceiling on one campaign's cells. Larger designs must be partitioned
#: deliberately rather than expanded by accident.
MAX_CAMPAIGN_CELLS = 200

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,60}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,199}$")


class VecCampaignModel(BaseModel):
    """Strict finite base model for campaign artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    def canonical_json(self) -> str:
        """Return deterministic canonical JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical JSON form."""

        return _sha256(self.canonical_json().encode())


class VecCampaignPhase(StrEnum):
    """Which declared seed cohort a campaign consumes."""

    PILOT = "pilot"
    HELD_OUT = "held_out"


class VecCampaignCellState(StrEnum):
    """Terminal state of one campaign cell."""

    ADMITTED = "admitted"
    REUSED = "reused"
    EXECUTION_FAILED = "execution_failed"
    ADMISSION_REFUSED = "admission_refused"
    SKIPPED_BUDGET = "skipped_budget"
    SKIPPED_HALTED = "skipped_halted"


class VecCampaignStatus(StrEnum):
    """Terminal state of one campaign invocation."""

    COMPLETED = "completed"
    HALTED_ON_FAILURE = "halted_on_failure"
    HALTED_ON_BUDGET = "halted_on_budget"
    REFUSED = "refused"


class VecCampaignApproval(VecCampaignModel):
    """Recorded human approval of one predeclaration document.

    Every field is required. The digest binds the approval to exact document
    bytes so a design cannot drift after it was approved, and
    ``held_out_authorised`` must be set deliberately before reserved
    confirmatory seeds may be consumed.
    """

    predeclaration_path: str = Field(min_length=1, max_length=1_000)
    predeclaration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_by: str = Field(min_length=1, max_length=200)
    approved_role: str = Field(min_length=1, max_length=200)
    approved_at_utc: str = Field(min_length=1, max_length=64)
    held_out_authorised: bool = False

    @field_validator("approved_by", "approved_role")
    @classmethod
    def validate_person(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("approval identity must not be blank")
        placeholders = {"tbd", "todo", "n/a", "na", "none", "unknown", "agent", "-", "_"}
        if text.lower() in placeholders:
            raise ValueError(
                "approval identity must name a real approver and role, not a placeholder"
            )
        return text


class VecCampaignArm(VecCampaignModel):
    """One named arm of the declared design."""

    label: str
    rsu_capacity_per_vehicle: float = Field(gt=0.0, le=1_000.0)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if not _LABEL_RE.fullmatch(value):
            raise ValueError("arm labels must be 1-61 ASCII letters, numbers, '.', '_' or '-'")
        return value


class VecCampaignBudget(VecCampaignModel):
    """Declared execution bounds; exceeding one halts rather than continuing."""

    max_cells: int = Field(ge=1, le=MAX_CAMPAIGN_CELLS)
    max_total_output_bytes: int = Field(ge=1)
    halt_on_failure: bool = True


class VecCampaignDesign(VecCampaignModel):
    """One predeclared, approved run matrix.

    Arms vary exactly one evaluator control (per-vehicle RSU task capacity).
    Everything else is fixed so a paired difference isolates that control.
    """

    schema_version: Literal["1.0"] = VEC_CAMPAIGN_SCHEMA_VERSION
    method_version: Literal["vec-bounded-campaign-1.0"] = VEC_CAMPAIGN_METHOD_VERSION
    experiment_id: str
    research_question: str = Field(min_length=1, max_length=2_000)
    run_id_prefix: str
    phase: VecCampaignPhase
    approval: VecCampaignApproval
    trace_file: str = Field(min_length=1, max_length=256)
    trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor_id: Literal["baseline_model_c_17", "ukfleettrain_mappo_model_c_17"]
    fleet: VecFleet
    evaluator_seed: int = Field(ge=0, le=2_147_483_647)
    max_steps: int = Field(ge=1, le=100_000)
    timeout_seconds: int = Field(ge=1, le=7_200)
    baseline_arm: VecCampaignArm
    variation_arms: list[VecCampaignArm] = Field(min_length=1, max_length=16)
    pairing_seed_source: VecPairingSeedSource
    fleet_seeds: list[int] = Field(min_length=3, max_length=64)
    primary_metric_key: str = Field(min_length=1, max_length=200)
    budget: VecCampaignBudget

    @field_validator("experiment_id")
    @classmethod
    def validate_experiment_id(cls, value: str) -> str:
        if not _IDENTIFIER_RE.fullmatch(value):
            raise ValueError("experiment_id must be a valid registry identifier")
        return value

    @field_validator("run_id_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        if not _LABEL_RE.fullmatch(value):
            raise ValueError("run_id_prefix must be 1-61 ASCII letters, numbers, '.', '_' or '-'")
        return value

    @field_validator("fleet_seeds")
    @classmethod
    def validate_seeds(cls, value: list[int]) -> list[int]:
        if any(seed < 0 or seed > 2_147_483_647 for seed in value):
            raise ValueError("fleet seeds must be non-negative evaluator-admissible integers")
        if len(set(value)) != len(value):
            raise ValueError("fleet_seeds must not contain duplicates")
        return sorted(value)

    @model_validator(mode="after")
    def validate_design(self) -> VecCampaignDesign:
        if self.trace_sha256 not in PINNED_REVIEWED_TRACES:
            raise ValueError(
                "campaigns run only reviewed traces; extend the reviewed allowlist first"
            )
        if PINNED_REVIEWED_TRACES[self.trace_sha256] != self.trace_file:
            raise ValueError("trace_file does not match the reviewed path for that hash")
        labels = [self.baseline_arm.label, *(arm.label for arm in self.variation_arms)]
        if len(set(labels)) != len(labels):
            raise ValueError("arm labels must be unique")
        capacities = [
            self.baseline_arm.rsu_capacity_per_vehicle,
            *(arm.rsu_capacity_per_vehicle for arm in self.variation_arms),
        ]
        if len(set(capacities)) != len(capacities):
            raise ValueError("arm capacities must be distinct so arms are not duplicate cells")
        if self.phase is VecCampaignPhase.HELD_OUT and not self.approval.held_out_authorised:
            raise ValueError(
                "consuming reserved held-out seeds requires explicit held_out_authorised approval"
            )
        cells = len(labels) * len(self.fleet_seeds)
        if cells > self.budget.max_cells:
            raise ValueError(
                f"the declared design needs {cells} cells but the budget allows "
                f"{self.budget.max_cells}"
            )
        for label in labels:
            for seed in self.fleet_seeds:
                composed = f"{self.run_id_prefix}-{label}-fs{seed}"
                if not _RUN_ID_RE.fullmatch(composed):
                    raise ValueError(f"composed run id is not runner-admissible: {composed}")
        return self

    def cell_run_id(self, arm_label: str, fleet_seed: int) -> str:
        """Return the deterministic runner run id for one cell."""

        return f"{self.run_id_prefix}-{arm_label}-fs{fleet_seed}"

    def cell_request(self, arm: VecCampaignArm, fleet_seed: int) -> VecRunRequest:
        """Return the exact bounded VEC-07 request for one cell."""

        return VecRunRequest(
            run_id=self.cell_run_id(arm.label, fleet_seed),
            trace_file=self.trace_file,
            trace_sha256=self.trace_sha256,
            actor_id=self.actor_id,
            evaluator_seed=self.evaluator_seed,
            fleet=self.fleet,
            fleet_seed=fleet_seed,
            rsu_capacity_per_vehicle=arm.rsu_capacity_per_vehicle,
            max_steps=self.max_steps,
            timeout_seconds=self.timeout_seconds,
        )

    def arms(self) -> list[VecCampaignArm]:
        """Return the baseline arm followed by declared variation arms."""

        return [self.baseline_arm, *self.variation_arms]


class VecCampaignCell(VecCampaignModel):
    """Deterministic outcome of one declared cell."""

    arm_label: str
    fleet_seed: int = Field(ge=0)
    run_id: str = Field(min_length=1, max_length=200)
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: VecCampaignCellState
    output_directory_name: str = Field(min_length=1, max_length=200)
    elapsed_seconds: float | None = Field(default=None, ge=0)
    output_bytes: int | None = Field(default=None, ge=0)
    receipt_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    registry_run_id: str | None = Field(default=None, min_length=1, max_length=200)
    admission_stable_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    detail: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_state(self) -> VecCampaignCell:
        admitted = self.state in {VecCampaignCellState.ADMITTED, VecCampaignCellState.REUSED}
        if admitted:
            if self.receipt_fingerprint is None or self.registry_run_id is None:
                raise ValueError("an admitted cell requires receipt and registry evidence")
            if self.admission_stable_fingerprint is None:
                raise ValueError("an admitted cell requires its admission fingerprint")
        elif self.registry_run_id is not None or self.admission_stable_fingerprint is not None:
            raise ValueError("only an admitted cell may carry registry admission evidence")
        return self


class VecCampaignReceipt(VecCampaignModel):
    """Complete typed evidence for one campaign invocation."""

    schema_version: Literal["1.0"] = VEC_CAMPAIGN_SCHEMA_VERSION
    method_version: Literal["vec-bounded-campaign-1.0"] = VEC_CAMPAIGN_METHOD_VERSION
    status: VecCampaignStatus
    design_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    experiment_id: str
    phase: VecCampaignPhase
    approval: VecCampaignApproval
    predeclaration_verified_unchanged: bool
    experiment_registered: bool
    cells: list[VecCampaignCell]
    planned_cell_count: int = Field(ge=1)
    admitted_cell_count: int = Field(ge=0)
    reused_cell_count: int = Field(ge=0)
    failed_cell_count: int = Field(ge=0)
    skipped_cell_count: int = Field(ge=0)
    total_output_bytes: int = Field(ge=0)
    total_elapsed_seconds: float = Field(ge=0)
    started_at_utc: str
    finished_at_utc: str
    background_execution: Literal[False] = False
    concurrent_execution: Literal[False] = False
    scientific_conclusion_recorded: Literal[False] = False
    findings: list[str] = Field(default_factory=list, max_length=64)
    limitations: list[str] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_counts(self) -> VecCampaignReceipt:
        if len(self.cells) != self.planned_cell_count:
            raise ValueError("every planned cell must have a recorded outcome")
        states = [cell.state for cell in self.cells]
        if states.count(VecCampaignCellState.ADMITTED) != self.admitted_cell_count:
            raise ValueError("admitted cell count does not match the recorded cells")
        if states.count(VecCampaignCellState.REUSED) != self.reused_cell_count:
            raise ValueError("reused cell count does not match the recorded cells")
        failed = states.count(VecCampaignCellState.EXECUTION_FAILED) + states.count(
            VecCampaignCellState.ADMISSION_REFUSED
        )
        if failed != self.failed_cell_count:
            raise ValueError("failed cell count does not match the recorded cells")
        skipped = states.count(VecCampaignCellState.SKIPPED_BUDGET) + states.count(
            VecCampaignCellState.SKIPPED_HALTED
        )
        if skipped != self.skipped_cell_count:
            raise ValueError("skipped cell count does not match the recorded cells")
        if self.status is VecCampaignStatus.COMPLETED and self.failed_cell_count:
            raise ValueError("a completed campaign cannot contain failed cells")
        if self.status is VecCampaignStatus.REFUSED and any(
            state in {VecCampaignCellState.ADMITTED, VecCampaignCellState.REUSED}
            for state in states
        ):
            raise ValueError("a refused campaign cannot have admitted any cell")
        return self


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
