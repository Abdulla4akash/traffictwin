"""Strict contracts for owner-approved-candidate fresh-run scientific admission.

Policy ``vec-fresh-run-scientific-admission-1.0`` turns one completed VEC-07
execution's deterministic outputs into registry metrics that the STA-01
paired-study tooling can consume. It is an owner-approved candidate research
policy: it is not VEC-08 reproduction grading, not the accepted VEC-09
source-run admission, not analyst review, and not supervisor approval. The
VEC-10 structural import record keeps its literal
``scientific_admission_status: "unavailable"``; this policy produces a
separate, honestly labelled artifact bound to the execution receipt.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.integration.vec_runner.models import (
    PINNED_REVIEWED_TRACES,
    VecRunRequest,
)

VEC_FRESH_ADMISSION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_FRESH_ADMISSION_METHOD_VERSION: Literal["vec-fresh-run-scientific-admission-1.0"] = (
    "vec-fresh-run-scientific-admission-1.0"
)
VEC_FRESH_ADMISSION_RESEARCH_STATUS: Literal["owner_approved_candidate"] = (
    "owner_approved_candidate"
)

STANDING_FRESH_ADMISSION_LIMITATIONS = (
    "Fresh-run admission is an owner-approved candidate research policy; it is not "
    "supervisor approval, analyst review, or publication validation.",
    "The execution was not VEC-08 reproduction-graded; numerical equivalence with the "
    "audited source engine is not claimed for this run.",
    "Deadline success is never physical task completion; action selection is never a "
    "confirmed transfer; aggregate energy is never per-task energy.",
    "Trip evidence is trace-level SUMO output and is deliberately excluded from "
    "fresh-run admission; trip metrics remain unavailable.",
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,199}$")


class VecFreshAdmissionModel(BaseModel):
    """Strict finite base model for fresh-admission artifacts."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    def canonical_json(self) -> str:
        """Return deterministic canonical JSON."""

        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical JSON form."""

        return _sha256(self.canonical_json().encode())


class VecPairingSeedSource(StrEnum):
    """Which request seed field supplies the STA-01 pairing ``random_seed``."""

    FLEET_SEED = "fleet_seed"
    EVALUATOR_SEED = "evaluator_seed"


class VecFreshRunStudyContext(VecFreshAdmissionModel):
    """Caller-declared study context stamped onto every admitted metric.

    The pairing seed is never typed in: the admission derives it from the
    execution receipt's request according to ``pairing_seed_source`` so the
    stamped ``random_seed`` always matches an executed control.
    """

    experiment_id: str
    seed_id: str
    pairing_seed_source: VecPairingSeedSource
    synthetic_fixture: bool = False

    @field_validator("experiment_id", "seed_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not _IDENTIFIER_RE.fullmatch(value):
            raise ValueError(
                "identifiers must start alphanumeric and use letters, numbers, "
                "dots, underscores, colons, or hyphens (max 200 characters)"
            )
        return value


class VecFreshRunAdmissionRecord(VecFreshAdmissionModel):
    """Immutable evidence for one fresh-run scientific admission.

    Semantic guards are literal so the record cannot be represented as more
    than it is: no reproduction grade, no analyst review, no supervisor
    approval, no physical-completion or transfer claims, and no trip evidence.
    """

    schema_version: Literal["1.0"] = VEC_FRESH_ADMISSION_SCHEMA_VERSION
    policy_id: Literal["vec-fresh-run-scientific-admission-1.0"] = (
        VEC_FRESH_ADMISSION_METHOD_VERSION
    )
    research_status: Literal["owner_approved_candidate"] = VEC_FRESH_ADMISSION_RESEARCH_STATUS
    request: VecRunRequest
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_file_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at_utc: str
    finished_at_utc: str
    reviewed_trace: bool
    trace_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    occupancy_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    tos_data_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    identity_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_join_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    metric_collection_run_id: str = Field(min_length=1, max_length=200)
    metric_collection_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    metric_version: Literal["vec-fresh-run-scientific-admission-1.0"] = (
        VEC_FRESH_ADMISSION_METHOD_VERSION
    )
    available_metric_count: int = Field(ge=1)
    unavailable_metric_count: int = Field(ge=1)
    study: VecFreshRunStudyContext
    pairing_random_seed: int = Field(ge=0)
    admitted_at_utc: str
    registry_run_id: str = Field(min_length=1, max_length=200)
    registry_bundle_id: str = Field(min_length=1, max_length=200)
    reproduction_graded: Literal[False] = False
    analyst_reviewed: Literal[False] = False
    supervisor_approved: Literal[False] = False
    deadline_success_is_physical_completion: Literal[False] = False
    action_selection_is_confirmed_transfer: Literal[False] = False
    aggregate_energy_is_per_task_energy: Literal[False] = False
    trip_evidence_included: Literal[False] = False
    limitations: list[str] = Field(min_length=1, max_length=16)

    @field_validator("limitations")
    @classmethod
    def validate_statements(cls, value: list[str]) -> list[str]:
        for item in value:
            if not 1 <= len(item) <= 1_000:
                raise ValueError("limitations must be 1-1000 characters")
        return value

    @model_validator(mode="after")
    def validate_semantics(self) -> VecFreshRunAdmissionRecord:
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        if self.trace_sha256 != self.request.trace_sha256:
            raise ValueError("trace hash must match the executed request")
        if self.reviewed_trace != (self.trace_sha256 in PINNED_REVIEWED_TRACES):
            raise ValueError("reviewed_trace must reflect the pinned reviewed-trace set")
        if not self.reviewed_trace and not self.study.synthetic_fixture:
            raise ValueError(
                "an unreviewed trace is admissible only as a clearly labelled synthetic fixture"
            )
        if not self.study.synthetic_fixture:
            if self.tos_data_commit != TOS_DATA_AUDITED_COMMIT:
                raise ValueError(
                    "real admission requires identity evidence from the audited tos-data commit"
                )
            if self.occupancy_sha256 is None or self.receipt_file_sha256 is None:
                raise ValueError("real admission requires the occupancy hash and receipt file hash")
        expected_seed = {
            VecPairingSeedSource.FLEET_SEED: self.request.fleet_seed,
            VecPairingSeedSource.EVALUATOR_SEED: self.request.evaluator_seed,
        }[self.study.pairing_seed_source]
        if self.pairing_random_seed != expected_seed:
            raise ValueError("pairing_random_seed must equal the declared request seed field")
        expected_run_id = f"vec:fresh:{self.receipt_fingerprint[:16]}"
        expected_bundle_id = f"vec-fresh:{self.receipt_fingerprint}"
        if self.registry_run_id != expected_run_id:
            raise ValueError("registry_run_id must derive from the receipt fingerprint")
        if self.registry_bundle_id != expected_bundle_id:
            raise ValueError("registry_bundle_id must derive from the receipt fingerprint")
        if self.metric_collection_run_id != self.registry_run_id:
            raise ValueError("metric collection must bind to the registry run id")
        missing = [
            statement
            for statement in STANDING_FRESH_ADMISSION_LIMITATIONS
            if statement not in self.limitations
        ]
        if missing:
            raise ValueError(
                "limitations must retain the standing fresh-admission statements; "
                f"missing: {len(missing)}"
            )
        return self

    def stable_fingerprint(self) -> str:
        """Fingerprint the admission identity excluding the admission wall-clock time."""

        payload = self.model_dump(mode="json")
        del payload["admitted_at_utc"]
        return _sha256(_canonical_json(payload).encode())


class VecFreshAdmissionOutcome(VecFreshAdmissionModel):
    """Registry outcome for one fresh-run admission attempt."""

    run_created: bool
    run_idempotent: bool
    metrics_created: bool
    registry_run_id: str = Field(min_length=1, max_length=200)
    registry_bundle_id: str = Field(min_length=1, max_length=200)
    stable_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_reference: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_flags(self) -> VecFreshAdmissionOutcome:
        if self.run_created and self.run_idempotent:
            raise ValueError("a run import is either newly created or idempotent, not both")
        return self


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
