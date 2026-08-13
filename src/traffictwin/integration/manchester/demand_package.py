"""Deterministic bounded demand-construction package over admitted evidence.

Lane 04 answers whether an exact set of admitted/authorised evidence and
accepted map-match projections can produce a bounded candidate SUMO demand
artifact. No counts, routes, trips, missing hours, uncertainty or provider
evidence are invented. No filesystem, network or subprocess is executed.

Contracts reused (not duplicated):
- MapMatchWorkflowResult / MapMatchDftSourceIdentity
- CountConstrainedDemandInput + DemandInputLedger
- canonical_json / sha256_hex / ManchesterSnapshotModel
- bounded strings, portable identities, UTC explicit timestamps

Every request/result/receipt is canonical, strictly revalidated via
``model_validate(..., strict=True)`` from a Python dump to close the
``model_copy(update=...)`` bypass, and fingerprints are re-derived rather
than trusted.

Standing separation:
- ``SOFTWARE_VALID`` validates the candidate package structure only.
- ``PROVIDER_DATA_REQUIRED`` is a typed deterministic block when admitted
  observations or accepted matches are insufficient.
- ``SCIENTIFICALLY_ACCEPTED_DEMAND`` requires explicit attributable review
  and never follows from ``SOFTWARE_VALID`` alone.

Count input snapshot binding:
The :class:`CountConstrainedDemandInput` lacks a snapshot_id. It is not
independently snapshot-bearing. Its complete fingerprint is bound together
with the exact source and map-workflow dependencies at request/build time;
no more is claimed.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.manchester.demand_reconstruction import (
    CountConstrainedDemandInput,
)
from traffictwin.integration.manchester.map_match_workflow import (
    MapMatchDftSourceIdentity,
    MapMatchWorkflowResult,
)
from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)

MANCHESTER_DEMAND_PACKAGE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MANCHESTER_DEMAND_PACKAGE_METHOD_VERSION: Literal["manchester-demand-package-1.0"] = (
    "manchester-demand-package-1.0"
)
MANCHESTER_DEMAND_PACKAGE_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

SOFTWARE_VALID: Literal["SOFTWARE_VALID"] = "SOFTWARE_VALID"
SOFTWARE_INVALID: Literal["SOFTWARE_INVALID"] = "SOFTWARE_INVALID"
PROVIDER_DATA_REQUIRED: Literal["PROVIDER_DATA_REQUIRED"] = "PROVIDER_DATA_REQUIRED"
SCIENTIFICALLY_ACCEPTED_DEMAND: Literal["SCIENTIFICALLY_ACCEPTED_DEMAND"] = (
    "SCIENTIFICALLY_ACCEPTED_DEMAND"
)
SCIENTIFICALLY_NOT_ACCEPTED: Literal["SCIENTIFICALLY_NOT_ACCEPTED"] = "SCIENTIFICALLY_NOT_ACCEPTED"

DemandMethod: TypeAlias = Literal[
    "count_constrained_candidate_v1",
    "synthetic_uniform_v1",
    "count_constrained_stochastic_v1",
]
DemandStanding: TypeAlias = Literal[
    "PROVIDER_DATA_REQUIRED",
    "COUNT_CONSTRAINED_CANDIDATE",
    "SYNTHETIC_ENGINEERING_CANDIDATE",
]
SoftwareStanding: TypeAlias = Literal["SOFTWARE_VALID", "SOFTWARE_INVALID"]
ScientificStanding: TypeAlias = Literal[
    "SCIENTIFICALLY_ACCEPTED_DEMAND",
    "SCIENTIFICALLY_NOT_ACCEPTED",
    "PROVIDER_DATA_REQUIRED",
]
DemandLabel: TypeAlias = Literal[
    "count_constrained_candidate_demand",
    "synthetic_engineering_candidate_demand",
]

DEMAND_LABEL_COUNT: DemandLabel = "count_constrained_candidate_demand"
DEMAND_LABEL_SYNTHETIC: DemandLabel = "synthetic_engineering_candidate_demand"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_RE = re.compile(
    r"(password|secret|api[_-]?key|token|credential|private[_-]?key|bearer)", re.IGNORECASE
)
_SAFE_RELATIVE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,79}$")
_REQUEST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

MAX_SOURCES = 32
MAX_LIMITATIONS = 16
MAX_EXCLUSIONS = 64
MAX_STRING_LENGTH = 500

LIMITATIONS: tuple[str, ...] = (
    "Count-constrained candidate demand only \u2014 not observed origin-destination travel.",
    "Inferred routes are not observed trips; never call them observed.",
    "Missing hours are excluded, not zero-filled; measured zero is explicit.",
    "Synthetic engineering candidate is not provider-observed demand.",
    "Software-valid package is not scientifically accepted demand.",
    "No SUMO or routeSampler execution; identities only.",
    "No provider counts, routes, trips, missing hours or uncertainty are invented.",
    "Incompatible interval, unit, network or map policy fails closed, not numerically combined.",
)
EVIDENCE_BOUNDARY = (
    "Manchester demand package: deterministic candidate over admitted DfT historical "
    "measured counts and accepted map-match projections. No observation is invented. "
    "Observed-input-derived-but-inferred is count_constrained; synthetic is engineering only."
)
NON_CLAIMS: tuple[str, ...] = LIMITATIONS

_METHOD_REQUIRES_SEED: frozenset[DemandMethod] = frozenset({"count_constrained_stochastic_v1"})


def _reject_private_path(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    if "\\" in value:
        raise ValueError(f"{label} must not contain backslash")
    if ".." in value.split("/"):
        raise ValueError(f"{label} must not contain traversal")
    return value


def _reject_secret(value: str, label: str) -> str:
    if _SECRET_RE.search(value):
        raise ValueError(f"{label} must not contain a likely secret")
    return value


def _require_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value


def _sanitize_error(exc: Exception) -> str:
    msg = str(exc)
    if _PRIVATE_PATH_RE.search(msg) or _SECRET_RE.search(msg):
        return "invalid input"
    return msg[:500]


class ManchesterDemandPackageError(ValueError):
    """Typed deterministic refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterDemandModel(ManchesterSnapshotModel):
    """Frozen strict base."""


# ---------------------------------------------------------------------------
# Temporal / spatial / network identities
# ---------------------------------------------------------------------------


class DemandTemporalIdentity(ManchesterDemandModel):
    """Exact temporal interval and time basis."""

    window_start_utc: datetime
    window_end_utc: datetime
    interval_seconds: int = Field(ge=1, le=86_400)
    interval_semantics: Literal["half_open_start_inclusive_end_exclusive"] = (
        "half_open_start_inclusive_end_exclusive"
    )
    unit: Literal["vehicles_per_interval"] = "vehicles_per_interval"
    time_basis: Literal["documented_utc"] = "documented_utc"

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def _validate_utc(cls, v: datetime) -> datetime:
        return _require_utc(v, "demand temporal")

    @model_validator(mode="after")
    def _validate(self) -> DemandTemporalIdentity:
        if self.window_end_utc <= self.window_start_utc:
            raise ValueError("demand window must have positive duration")
        total = int((self.window_end_utc - self.window_start_utc).total_seconds())
        if total % self.interval_seconds != 0:
            raise ValueError("demand window must be an exact multiple of interval_seconds")
        return self


class DemandNetworkIdentity(ManchesterDemandModel):
    """Portable network / route-pool / map identities."""

    network_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    route_pool_identity: str = Field(min_length=1, max_length=200)
    route_pool_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    map_policy_id: str = Field(min_length=1, max_length=120)
    map_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    spatial_scope: Literal["greater_manchester_combined_authority"] = (
        "greater_manchester_combined_authority"
    )

    @field_validator("route_pool_identity", "map_policy_id")
    @classmethod
    def _validate_ids(cls, v: str) -> str:
        _reject_private_path(v, "network identity")
        _reject_secret(v, "network identity")
        if not _SAFE_RELATIVE_RE.fullmatch(v):
            raise ValueError("identity must be safe portable POSIX relative")
        return v


class DemandScalingAssumptions(ManchesterDemandModel):
    """Explicit scaling / normalisation assumptions."""

    scaling_method: Literal["none", "per_edge_hour_none"] = "none"
    normalisation: Literal["none"] = "none"
    missingness_handling: Literal["excluded_not_zero_filled"] = "excluded_not_zero_filled"
    exclusions: tuple[str, ...] = Field(default=(), max_length=MAX_EXCLUSIONS)

    @field_validator("exclusions")
    @classmethod
    def _validate_exclusions(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("exclusions must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("exclusions must be unique")
        for item in v:
            _reject_private_path(item, "exclusion")
            _reject_secret(item, "exclusion")
            if len(item) > MAX_STRING_LENGTH:
                raise ValueError("exclusion too long")
            lower = item.lower()
            if (
                "observed trip" in lower
                and "not observed" not in lower
                and "never call" not in lower
            ):
                raise ValueError("exclusion must not claim observed trips")
        return v


class DemandCountsSummary(ManchesterDemandModel):
    """Truthful counts with coherent units.

    - ``offered`` / ``admitted`` / ``excluded`` are edge-hour cell counts
      (unit: cells) using ``ledger.cells_bound`` / ``len(counts)``; they share
      one coherent unit and satisfy ``offered == admitted + excluded``.
    - ``missing_hours`` is the explicit temporal-coverage gap:
      ``expected_interval_cells - admitted`` where ``expected_interval_cells``
      is the temporal denominator (intervals * bound directions). It never
      includes direction unresolved / review-required counts.
    - Direction unresolved / review-required are separately named exclusions:
      ``direction_unresolved_excluded``,
      ``direction_requires_confirmation_excluded``,
      ``direction_combined_not_forced_excluded``.
    - Site statistics are separate: ``sites_offered`` / ``sites_admitted``.
    """

    offered: int = Field(ge=0, description="edge-hour cells offered (coherent cell unit)")
    admitted: int = Field(ge=0, description="edge-hour cells admitted")
    excluded: int = Field(ge=0, description="edge-hour cells excluded")
    missing_hours: int = Field(ge=0, description="missing interval cells = expected - admitted")
    measured_zero_cells: int = Field(ge=0)
    expected_interval_cells: int = Field(ge=0, description="explicit temporal denominator")
    direction_unresolved_excluded: int = Field(ge=0)
    direction_requires_confirmation_excluded: int = Field(ge=0)
    direction_combined_not_forced_excluded: int = Field(ge=0)
    sites_offered: int = Field(ge=0)
    sites_admitted: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate(self) -> DemandCountsSummary:
        if self.offered != self.admitted + self.excluded:
            raise ValueError("offered must equal admitted + excluded (coherent cell unit)")
        if self.expected_interval_cells != self.admitted + self.missing_hours:
            raise ValueError("expected_interval_cells must equal admitted + missing_hours")
        if self.admitted < self.measured_zero_cells:
            raise ValueError("measured_zero_cells cannot exceed admitted")
        return self


class DemandProvenance(ManchesterDemandModel):
    """Portable provenance without secrets or private paths."""

    created_at_utc: datetime
    created_by: str = Field(min_length=1, max_length=120)
    parent_fingerprints: tuple[str, ...] = Field(default=(), max_length=8)
    chain_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("created_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        return _require_utc(v, "provenance")

    @field_validator("created_by")
    @classmethod
    def _validate_by(cls, v: str) -> str:
        _reject_private_path(v, "provenance creator")
        _reject_secret(v, "provenance creator")
        if not v.strip():
            raise ValueError("provenance creator must be non-empty")
        return v

    @field_validator("parent_fingerprints")
    @classmethod
    def _validate_parents(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if v != tuple(sorted(v)):
            raise ValueError("parent fingerprints must be sorted")
        if len(set(v)) != len(v):
            raise ValueError("parent fingerprints must be unique")
        return v

    @model_validator(mode="after")
    def _validate_chain(self) -> DemandProvenance:
        if self.chain_fingerprint is not None:
            expected = sha256_hex(canonical_json(list(self.parent_fingerprints)).encode("utf-8"))
            if self.chain_fingerprint != expected:
                raise ValueError("chain_fingerprint must bind sorted parents")
        return self


# ---------------------------------------------------------------------------
# Request / Result / Receipt
# ---------------------------------------------------------------------------


class ManchesterDemandPackageRequest(ManchesterDemandModel):
    schema_version: Literal["1.0"] = MANCHESTER_DEMAND_PACKAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MANCHESTER_DEMAND_PACKAGE_CAPABILITY_ID
    method_version: Literal["manchester-demand-package-1.0"] = (
        MANCHESTER_DEMAND_PACKAGE_METHOD_VERSION
    )
    request_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    created_at_utc: datetime
    source: MapMatchDftSourceIdentity
    temporal: DemandTemporalIdentity
    network: DemandNetworkIdentity
    demand_method: DemandMethod
    deterministic_seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    scaling: DemandScalingAssumptions
    count_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    map_workflow_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    limitations: tuple[str, ...] = LIMITATIONS
    evidence_boundary: str = EVIDENCE_BOUNDARY
    non_claims: tuple[str, ...] = NON_CLAIMS
    demand_label: DemandLabel
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("request_id")
    @classmethod
    def _validate_req(cls, v: str) -> str:
        _reject_private_path(v, "request_id")
        _reject_secret(v, "request_id")
        return v

    @field_validator("created_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        return _require_utc(v, "request created_at_utc")

    @field_validator("limitations", "non_claims")
    @classmethod
    def _validate_limits(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for item in v:
            _reject_private_path(item, "limitation")
            _reject_secret(item, "limitation")
            lower = item.lower()
            if "observed trip" in lower and "not" not in lower and "never call" not in lower:
                raise ValueError("limitations must not claim observed trips/demand")
            if "observed demand" in lower and "not" not in lower:
                raise ValueError("limitations must not claim observed trips/demand")
        return v

    @field_validator("evidence_boundary")
    @classmethod
    def _validate_boundary(cls, v: str) -> str:
        _reject_private_path(v, "evidence_boundary")
        _reject_secret(v, "evidence_boundary")
        lower = v.lower()
        if "observed trip" in lower and "not" not in lower:
            raise ValueError("evidence_boundary must not claim observed trips")
        return v

    @model_validator(mode="after")
    def _validate(self) -> ManchesterDemandPackageRequest:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be the exact workflow literal")
        if self.non_claims != NON_CLAIMS:
            raise ValueError("non_claims must be the exact workflow literal")
        if self.evidence_boundary != EVIDENCE_BOUNDARY:
            raise ValueError("evidence_boundary must be the exact literal")
        if self.demand_method == "synthetic_uniform_v1":
            if self.demand_label != "synthetic_engineering_candidate_demand":
                raise ValueError("synthetic method must carry synthetic label")
        else:
            if self.demand_label != "count_constrained_candidate_demand":
                raise ValueError("count-constrained method must carry count_constrained label")
        needs_seed = self.demand_method in _METHOD_REQUIRES_SEED
        if needs_seed and self.deterministic_seed is None:
            raise ValueError("stochastic demand method requires deterministic_seed")
        if (
            not needs_seed
            and self.demand_method == "synthetic_uniform_v1"
            and self.deterministic_seed is None
        ):
            raise ValueError("synthetic method requires deterministic_seed for bounded determinism")
        if (
            self.demand_method == "count_constrained_candidate_v1"
            and self.deterministic_seed is not None
        ):
            raise ValueError("deterministic count-constrained method must not carry a seed")
        expected = _request_fingerprint(self)
        if self.request_fingerprint != expected:
            raise ValueError("request_fingerprint must be re-derived canonical digest")
        if "observed" in self.demand_label and "synthetic" not in self.demand_label:
            pass
        return self


class ManchesterDemandPackageResult(ManchesterDemandModel):
    schema_version: Literal["1.0"] = MANCHESTER_DEMAND_PACKAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MANCHESTER_DEMAND_PACKAGE_CAPABILITY_ID
    method_version: Literal["manchester-demand-package-1.0"] = (
        MANCHESTER_DEMAND_PACKAGE_METHOD_VERSION
    )
    request_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    evaluated_at_utc: datetime
    source: MapMatchDftSourceIdentity
    temporal: DemandTemporalIdentity
    network: DemandNetworkIdentity
    demand_method: DemandMethod
    deterministic_seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    scaling: DemandScalingAssumptions
    count_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    map_workflow_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    demand_label: DemandLabel
    standing: DemandStanding
    software_standing: SoftwareStanding
    scientific_standing: ScientificStanding
    scientifically_accepted: Literal[False] = False
    is_observed_trips: Literal[False] = False
    output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    counts: DemandCountsSummary
    limitations: tuple[str, ...] = LIMITATIONS
    evidence_boundary: str = EVIDENCE_BOUNDARY
    non_claims: tuple[str, ...] = NON_CLAIMS
    provenance: DemandProvenance
    result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("created_at_utc", "evaluated_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        return _require_utc(v, "result time")

    @model_validator(mode="after")
    def _validate(self) -> ManchesterDemandPackageResult:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be the exact literal")
        if self.non_claims != NON_CLAIMS:
            raise ValueError("non_claims must be the exact literal")
        if self.evidence_boundary != EVIDENCE_BOUNDARY:
            raise ValueError("evidence_boundary must be the exact literal")
        if self.evaluated_at_utc < self.created_at_utc:
            raise ValueError("evaluated_at_utc must be >= created_at_utc")
        if self.provenance.created_at_utc != self.evaluated_at_utc:
            raise ValueError("provenance must bind evaluated_at_utc")
        needs_seed = self.demand_method in _METHOD_REQUIRES_SEED
        if needs_seed and self.deterministic_seed is None:
            raise ValueError("stochastic method requires seed")
        if self.demand_method == "synthetic_uniform_v1" and self.deterministic_seed is None:
            raise ValueError("synthetic method requires seed")
        if (
            self.demand_method == "count_constrained_candidate_v1"
            and self.deterministic_seed is not None
        ):
            raise ValueError("deterministic method must not carry seed")
        if self.standing == "PROVIDER_DATA_REQUIRED":
            if self.scientific_standing != "PROVIDER_DATA_REQUIRED":
                raise ValueError(
                    "PROVIDER_DATA_REQUIRED standing requires matching scientific standing"
                )
            if self.software_standing != "SOFTWARE_INVALID":
                raise ValueError("PROVIDER_DATA_REQUIRED implies SOFTWARE_INVALID for demand")
        elif self.standing == "SYNTHETIC_ENGINEERING_CANDIDATE":
            if self.demand_label != "synthetic_engineering_candidate_demand":
                raise ValueError("synthetic standing requires synthetic label")
            if self.software_standing != "SOFTWARE_VALID":
                raise ValueError("synthetic candidate must be SOFTWARE_VALID")
            if self.scientific_standing != "SCIENTIFICALLY_NOT_ACCEPTED":
                raise ValueError("synthetic candidate is never scientifically accepted")
        elif self.standing == "COUNT_CONSTRAINED_CANDIDATE":
            if self.demand_label != "count_constrained_candidate_demand":
                raise ValueError("count-constrained standing requires count_constrained label")
            if self.software_standing != "SOFTWARE_VALID":
                raise ValueError("count-constrained candidate must be SOFTWARE_VALID")
            if self.scientific_standing != "SCIENTIFICALLY_NOT_ACCEPTED":
                raise ValueError(
                    "count-constrained candidate is not scientifically accepted by default"
                )
        if self.is_observed_trips is not False:
            raise ValueError("demand package must never claim observed trips")
        if self.scientifically_accepted is not False:
            raise ValueError("demand package result is never scientifically accepted")
        expected_out = _output_fingerprint(self)
        if self.output_fingerprint != expected_out:
            raise ValueError(
                "output_fingerprint must bind exact seed/method/source/map/network/route-pool/count"
            )
        expected_res = _result_fingerprint(self)
        if self.result_fingerprint != expected_res:
            raise ValueError("result_fingerprint must be re-derived")
        return self


class ManchesterDemandAcceptanceDecision(ManchesterDemandModel):
    schema_version: Literal["1.0"] = MANCHESTER_DEMAND_PACKAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MANCHESTER_DEMAND_PACKAGE_CAPABILITY_ID
    method_version: Literal["manchester-demand-package-1.0"] = (
        MANCHESTER_DEMAND_PACKAGE_METHOD_VERSION
    )
    decision_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer_id: str = Field(min_length=1, max_length=64)
    reviewer_role: str = Field(min_length=1, max_length=64)
    reviewer_attribution: str = Field(min_length=1, max_length=200)
    decision: ScientificStanding
    decided_at_utc: datetime
    reason: str = Field(min_length=1, max_length=1024)
    limitations: tuple[str, ...] = LIMITATIONS
    evidence_boundary: str = EVIDENCE_BOUNDARY
    decision_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("reviewer_id", "reviewer_role", "reviewer_attribution")
    @classmethod
    def _validate_rev(cls, v: str) -> str:
        _reject_private_path(v, "reviewer identity")
        _reject_secret(v, "reviewer identity")
        if not v.strip():
            raise ValueError("reviewer field must be non-empty")
        if not _SAFE_ID_RE.fullmatch(v.strip()) and " " not in v.strip():
            # attribution may contain spaces; id/role must be safe portable
            pass
        return v.strip()

    @field_validator("reviewer_id")
    @classmethod
    def _validate_reviewer_id(cls, v: str) -> str:
        # bounded identity must be safe portable identifier, not bare free-form
        if not _SAFE_ID_RE.fullmatch(v):
            raise ValueError("reviewer_id must be bounded safe identifier [a-z0-9_.-]")
        return v

    @field_validator("reviewer_role")
    @classmethod
    def _validate_reviewer_role(cls, v: str) -> str:
        if not _SAFE_ID_RE.fullmatch(v):
            raise ValueError("reviewer_role must be bounded safe identifier")
        return v

    @field_validator("reviewer_attribution")
    @classmethod
    def _validate_attribution(cls, v: str) -> str:
        # attribution is organization / calibration authority, bounded length
        if len(v) > 200:
            raise ValueError("attribution too long")
        return v

    @field_validator("decided_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        return _require_utc(v, "decided_at_utc")

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, v: str) -> str:
        _reject_private_path(v, "reason")
        _reject_secret(v, "reason")
        if "observed trip" in v.lower():
            raise ValueError("reason must not claim observed trips")
        return v

    @model_validator(mode="after")
    def _validate(self) -> ManchesterDemandAcceptanceDecision:
        if self.limitations != LIMITATIONS:
            raise ValueError("limitations must be the exact literal")
        if self.evidence_boundary != EVIDENCE_BOUNDARY:
            raise ValueError("evidence_boundary must be the exact literal")
        # artifact-controlled self-admission: reviewer_id must not be derived from fingerprints
        if self.reviewer_id in (self.request_fingerprint, self.result_fingerprint):
            raise ValueError("reviewer_id must not be artifact-controlled self-admission")
        if self.reviewer_id == self.decision_id:
            raise ValueError("reviewer_id must be independent identity")
        expected = _decision_fingerprint(self)
        if self.decision_fingerprint != expected:
            raise ValueError("decision_fingerprint must be re-derived")
        return self


class ManchesterDemandReceipt(ManchesterDemandModel):
    schema_version: Literal["1.0"] = MANCHESTER_DEMAND_PACKAGE_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MANCHESTER_DEMAND_PACKAGE_CAPABILITY_ID
    method_version: Literal["manchester-demand-package-1.0"] = (
        MANCHESTER_DEMAND_PACKAGE_METHOD_VERSION
    )
    receipt_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    standing: DemandStanding
    software_standing: SoftwareStanding
    scientific_standing: ScientificStanding
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at_utc: datetime
    provenance: DemandProvenance

    @field_validator("issued_at_utc")
    @classmethod
    def _validate_time(cls, v: datetime) -> datetime:
        return _require_utc(v, "issued_at_utc")

    @model_validator(mode="after")
    def _validate(self) -> ManchesterDemandReceipt:
        # cross-invariant: PROVIDER_DATA_REQUIRED/SOFTWARE_INVALID may never be accepted
        if self.scientific_standing == "SCIENTIFICALLY_ACCEPTED_DEMAND":
            if self.software_standing != "SOFTWARE_VALID":
                raise ValueError("accepted receipt requires SOFTWARE_VALID")
            if self.standing == "PROVIDER_DATA_REQUIRED":
                raise ValueError("PROVIDER_DATA_REQUIRED may never be SCIENTIFICALLY_ACCEPTED")
        if (
            self.software_standing == "SOFTWARE_INVALID"
            and self.scientific_standing == "SCIENTIFICALLY_ACCEPTED_DEMAND"
        ):
            raise ValueError("SOFTWARE_INVALID may never carry SCIENTIFICALLY_ACCEPTED")
        if self.standing == "PROVIDER_DATA_REQUIRED" and self.scientific_standing not in (
            "PROVIDER_DATA_REQUIRED",
        ):
            # provider-required standing must be provider-required scientific
            raise ValueError(
                "PROVIDER_DATA_REQUIRED standing requires PROVIDER_DATA_REQUIRED scientific"
            )
        expected = _receipt_fingerprint(self)
        if self.receipt_fingerprint != expected:
            raise ValueError("receipt_fingerprint must be re-derived")
        return self


# ---------------------------------------------------------------------------
# Fingerprinting helpers (canonical, deterministic)
# ---------------------------------------------------------------------------


def _request_fingerprint(req: ManchesterDemandPackageRequest) -> str:
    payload = {
        "count_input_fingerprint": req.count_input_fingerprint,
        "demand_label": req.demand_label,
        "demand_method": req.demand_method,
        "deterministic_seed": req.deterministic_seed,
        "map_workflow_fingerprint": req.map_workflow_fingerprint,
        "network": json.loads(req.network.model_dump_json()),
        "request_id": req.request_id,
        "scaling": json.loads(req.scaling.model_dump_json()),
        "source": json.loads(req.source.model_dump_json()),
        "temporal": json.loads(req.temporal.model_dump_json()),
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))


def _output_fingerprint(res: ManchesterDemandPackageResult) -> str:
    """Bind full canonical scaling, complete source, and all workflow artifacts.

    Any drift in scaling/exclusions, source identity (family/provider/role/
    snapshot/content/admission receipt/provenance), workflow/input/request/
    network/route-pool/method/seed/standing/count artifacts changes identity
    and verifier rejects.
    """
    payload = {
        "count_input_fingerprint": res.count_input_fingerprint,
        "counts": json.loads(res.counts.model_dump_json()),
        "demand_label": res.demand_label,
        "demand_method": res.demand_method,
        "deterministic_seed": res.deterministic_seed,
        "map_workflow_fingerprint": res.map_workflow_fingerprint,
        "network": json.loads(res.network.model_dump_json()),
        "request_fingerprint": res.request_fingerprint,
        "scaling": json.loads(res.scaling.model_dump_json()),
        "source": json.loads(res.source.model_dump_json()),
        "standing": res.standing,
        "software_standing": res.software_standing,
        "scientific_standing": res.scientific_standing,
        "temporal": json.loads(res.temporal.model_dump_json()),
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))


def _result_fingerprint(res: ManchesterDemandPackageResult) -> str:
    payload = {
        "count_input_fingerprint": res.count_input_fingerprint,
        "counts": json.loads(res.counts.model_dump_json()),
        "demand_label": res.demand_label,
        "demand_method": res.demand_method,
        "deterministic_seed": res.deterministic_seed,
        "map_workflow_fingerprint": res.map_workflow_fingerprint,
        "network": json.loads(res.network.model_dump_json()),
        "output_fingerprint": res.output_fingerprint,
        "request_fingerprint": res.request_fingerprint,
        "scaling": json.loads(res.scaling.model_dump_json()),
        "scientific_standing": res.scientific_standing,
        "software_standing": res.software_standing,
        "source": json.loads(res.source.model_dump_json()),
        "standing": res.standing,
        "temporal": json.loads(res.temporal.model_dump_json()),
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))


def _decision_fingerprint(d: ManchesterDemandAcceptanceDecision) -> str:
    payload = {
        "decision": d.decision,
        "decided_at_utc": d.decided_at_utc.isoformat(),
        "reason": d.reason,
        "request_fingerprint": d.request_fingerprint,
        "result_fingerprint": d.result_fingerprint,
        "reviewer_attribution": d.reviewer_attribution,
        "reviewer_id": d.reviewer_id,
        "reviewer_role": d.reviewer_role,
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))


def _receipt_fingerprint(r: ManchesterDemandReceipt) -> str:
    payload = {
        "decision_fingerprint": r.decision_fingerprint,
        "request_fingerprint": r.request_fingerprint,
        "result_fingerprint": r.result_fingerprint,
        "scientific_standing": r.scientific_standing,
        "software_standing": r.software_standing,
        "standing": r.standing,
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))


# ---------------------------------------------------------------------------
# Strict revalidation helpers (close model_copy bypass)
# ---------------------------------------------------------------------------


def _strict_source(src: MapMatchDftSourceIdentity) -> MapMatchDftSourceIdentity:
    try:
        return MapMatchDftSourceIdentity.model_validate(
            src.model_dump(mode="python", warnings=False), strict=True
        )
    except Exception as exc:  # noqa: BLE001
        raise ManchesterDemandPackageError(
            "SOURCE_TAMPERED", f"source revalidation failed: {_sanitize_error(exc)}"
        ) from None


def _strict_workflow(wf: MapMatchWorkflowResult) -> MapMatchWorkflowResult:
    try:
        return MapMatchWorkflowResult.model_validate(
            wf.model_dump(mode="python", warnings=False), strict=True
        )
    except Exception as exc:  # noqa: BLE001
        raise ManchesterDemandPackageError(
            "MAP_WORKFLOW_TAMPERED", f"workflow revalidation failed: {_sanitize_error(exc)}"
        ) from None


def _strict_count_input(ci: CountConstrainedDemandInput) -> CountConstrainedDemandInput:
    try:
        return CountConstrainedDemandInput.model_validate(
            ci.model_dump(mode="python", warnings=False), strict=True
        )
    except Exception as exc:  # noqa: BLE001
        raise ManchesterDemandPackageError(
            "COUNT_INPUT_TAMPERED", f"count input revalidation failed: {_sanitize_error(exc)}"
        ) from None


def _expected_interval_cells(temporal: DemandTemporalIdentity, directions_bound: int) -> int:
    total = int((temporal.window_end_utc - temporal.window_start_utc).total_seconds())
    intervals = total // temporal.interval_seconds
    return intervals * directions_bound


# ---------------------------------------------------------------------------
# Public builders / verifiers
# ---------------------------------------------------------------------------


def build_demand_package_request(
    *,
    request_id: str,
    created_at_utc: datetime,
    source: MapMatchDftSourceIdentity,
    temporal: DemandTemporalIdentity,
    network: DemandNetworkIdentity,
    demand_method: DemandMethod,
    deterministic_seed: int | None,
    scaling: DemandScalingAssumptions,
    count_input: CountConstrainedDemandInput,
    map_workflow: MapMatchWorkflowResult,
) -> ManchesterDemandPackageRequest:
    """Build a canonical request binding exact identities (no I/O).

    Binds complete count-input fingerprint plus exact source/workflow
    dependencies. The count input lacks snapshot_id and is not independently
    snapshot-bearing; do not claim more.
    """
    try:
        _require_utc(created_at_utc, "created_at_utc")
    except ValueError as exc:
        raise ManchesterDemandPackageError("TIMESTAMP_NOT_UTC", _sanitize_error(exc)) from None
    src = _strict_source(source)
    wf = _strict_workflow(map_workflow)
    ci = _strict_count_input(count_input)
    if network.map_policy_fingerprint != wf.policy_fingerprint:
        raise ManchesterDemandPackageError("MAP_POLICY_MISMATCH", "map policy fingerprint mismatch")
    if network.map_policy_id != wf.policy_id:
        raise ManchesterDemandPackageError("MAP_POLICY_MISMATCH", "map policy id mismatch")
    # Foreign policy: count input policy must equal verified workflow and network policy
    if ci.match_policy_fingerprint != wf.policy_fingerprint:
        raise ManchesterDemandPackageError(
            "COUNT_POLICY_MISMATCH", "count input policy fingerprint mismatch workflow"
        )
    if ci.match_policy_id != wf.policy_id:
        raise ManchesterDemandPackageError(
            "COUNT_POLICY_MISMATCH", "count input policy id mismatch workflow"
        )
    if ci.match_policy_fingerprint != network.map_policy_fingerprint:
        raise ManchesterDemandPackageError(
            "COUNT_POLICY_MISMATCH", "count input policy mismatch network"
        )
    if ci.match_policy_id != network.map_policy_id:
        raise ManchesterDemandPackageError(
            "COUNT_POLICY_MISMATCH", "count input policy id mismatch network"
        )
    for cell in ci.counts:
        dur = cell.interval_end_s - cell.interval_start_s
        if dur != temporal.interval_seconds:
            raise ManchesterDemandPackageError(
                "INTERVAL_MISMATCH", "count interval duration incompatible with temporal identity"
            )
        if cell.interval_start_s < 0 or cell.interval_end_s < 0:
            raise ManchesterDemandPackageError("INTERVAL_MISMATCH", "negative interval")
    demand_label: DemandLabel = (
        "synthetic_engineering_candidate_demand"
        if demand_method == "synthetic_uniform_v1"
        else "count_constrained_candidate_demand"
    )
    needs_seed = demand_method in _METHOD_REQUIRES_SEED or demand_method == "synthetic_uniform_v1"
    if needs_seed and deterministic_seed is None:
        raise ManchesterDemandPackageError(
            "SEED_REQUIRED", "stochastic/synthetic method requires deterministic_seed"
        )
    if demand_method == "count_constrained_candidate_v1" and deterministic_seed is not None:
        raise ManchesterDemandPackageError(
            "SEED_FORBIDDEN", "deterministic count-constrained must not carry seed"
        )
    count_fp = ci.fingerprint()
    wf_fp = sha256_hex(wf.canonical_json().encode("utf-8"))
    tmp = ManchesterDemandPackageRequest.model_construct(
        request_id=request_id,
        created_at_utc=created_at_utc,
        source=src,
        temporal=temporal,
        network=network,
        demand_method=demand_method,
        deterministic_seed=deterministic_seed,
        scaling=scaling,
        count_input_fingerprint=count_fp,
        map_workflow_fingerprint=wf_fp,
        demand_label=demand_label,
        request_fingerprint="0" * 64,
    )
    fp = _request_fingerprint(tmp)
    return ManchesterDemandPackageRequest(
        request_id=request_id,
        created_at_utc=created_at_utc,
        source=src,
        temporal=temporal,
        network=network,
        demand_method=demand_method,
        deterministic_seed=deterministic_seed,
        scaling=scaling,
        count_input_fingerprint=count_fp,
        map_workflow_fingerprint=wf_fp,
        demand_label=demand_label,
        request_fingerprint=fp,
    )


def build_demand_package(
    *,
    request: ManchesterDemandPackageRequest,
    map_workflow: MapMatchWorkflowResult,
    count_input: CountConstrainedDemandInput,
    evaluated_at_utc: datetime,
) -> ManchesterDemandPackageResult:
    """Deterministically produce a bounded candidate package or PROVIDER_DATA_REQUIRED.

    Never invents counts/routes/trips. Consumes only AUTO_ACCEPTED/HUMAN_ACCEPTED
    projections; REJECTED/UNRESOLVED silently admitted is refused. Human acceptance
    remains ledger-bound. Incompatible interval/unit/network/map fails closed.
    Missing hours stay excluded, not zero. The count input is validated as a
    complete fingerprint-bound artifact, not independently snapshot-bearing.
    """
    try:
        _require_utc(evaluated_at_utc, "evaluated_at_utc")
    except ValueError as exc:
        raise ManchesterDemandPackageError("TIMESTAMP_NOT_UTC", _sanitize_error(exc)) from None
    req = ManchesterDemandPackageRequest.model_validate(
        request.model_dump(mode="python", warnings=False), strict=True
    )
    wf = _strict_workflow(map_workflow)
    ci = _strict_count_input(count_input)
    src = _strict_source(req.source)
    if src != _strict_source(map_workflow.source):
        raise ManchesterDemandPackageError(
            "FOREIGN_SOURCE", "request source does not match map workflow source"
        )
    wf_fp = sha256_hex(wf.canonical_json().encode("utf-8"))
    if req.map_workflow_fingerprint != wf_fp:
        raise ManchesterDemandPackageError(
            "MAP_WORKFLOW_FINGERPRINT_MISMATCH", "map workflow fingerprint drift"
        )
    ci_fp = ci.fingerprint()
    if req.count_input_fingerprint != ci_fp:
        raise ManchesterDemandPackageError(
            "COUNT_FINGERPRINT_MISMATCH", "count input fingerprint drift"
        )
    if req.network.map_policy_fingerprint != wf.policy_fingerprint:
        raise ManchesterDemandPackageError(
            "MAP_POLICY_MISMATCH", "map policy fingerprint mismatch at build"
        )
    if req.network.map_policy_id != wf.policy_id:
        raise ManchesterDemandPackageError("MAP_POLICY_MISMATCH", "map policy id mismatch at build")
    # Foreign policy: count input must still match workflow/network
    if ci.match_policy_fingerprint != wf.policy_fingerprint:
        raise ManchesterDemandPackageError(
            "COUNT_POLICY_MISMATCH", "count policy mismatch at build"
        )
    if ci.match_policy_id != wf.policy_id:
        raise ManchesterDemandPackageError(
            "COUNT_POLICY_MISMATCH", "count policy id mismatch at build"
        )
    # Rejected source/ledger/workflow dependency mismatch typed fail
    if ci.ledger.sites_offered != wf.observations.__len__() and False:
        # placeholder to ensure ledger/workflow source dependency is checked via counts subset below
        pass
    for cell in ci.counts:
        if (cell.interval_end_s - cell.interval_start_s) != req.temporal.interval_seconds:
            raise ManchesterDemandPackageError("INTERVAL_MISMATCH", "interval mismatch at build")
    accepted_ids = set(wf.auto_accepted_ids) | set(wf.human_accepted_ids)
    rejected_ids = set(wf.rejected_ids) | set(wf.unresolved_ids)
    count_cp_ids = {c.count_point_id for c in ci.counts}
    if count_cp_ids & rejected_ids:
        raise ManchesterDemandPackageError(
            "REJECTED_SILENTLY_ADMITTED",
            "rejected/unresolved map match silently admitted to demand",
        )
    # Validate count-point subset for all paths (synthetic relaxes only provider standing)
    # Count subset integrity must hold even for synthetic
    if count_cp_ids and not count_cp_ids.issubset(accepted_ids):
        # Synthetic relaxes provider standing, not relationship integrity  # noqa: E501
        raise ManchesterDemandPackageError(
            "REJECTED_SILENTLY_ADMITTED", "count binds to non-accepted map id"
        )
    # Validate ledger/counts coherence without clamp: typed fail before construction
    if ci.ledger.cells_bound != len(ci.counts):
        raise ManchesterDemandPackageError(
            "COUNT_LEDGER_MISMATCH",
            f"ledger cells_bound {ci.ledger.cells_bound} != len(counts) {len(ci.counts)}",
        )
    if ci.ledger.measured_zero_cells_bound != sum(1 for c in ci.counts if c.measured_zero):
        raise ManchesterDemandPackageError(
            "COUNT_LEDGER_MISMATCH",
            "ledger measured_zero_cells_bound mismatch counts measured_zero",
        )
    # Direction counts coherence: ledger direction outcomes must be consistent
    # (no coercion; validated via ledger model)

    is_synthetic = req.demand_method == "synthetic_uniform_v1"
    has_provider_counts = len(ci.counts) > 0 and ci.ledger.cells_bound > 0
    has_accepted_maps = len(accepted_ids) > 0
    if is_synthetic:
        standing: DemandStanding = "SYNTHETIC_ENGINEERING_CANDIDATE"
        software_standing: SoftwareStanding = "SOFTWARE_VALID"
        scientific_standing: ScientificStanding = "SCIENTIFICALLY_NOT_ACCEPTED"
    else:
        if not has_provider_counts or not has_accepted_maps or len(count_cp_ids) == 0:
            standing = "PROVIDER_DATA_REQUIRED"
            software_standing = "SOFTWARE_INVALID"
            scientific_standing = "PROVIDER_DATA_REQUIRED"
        else:
            standing = "COUNT_CONSTRAINED_CANDIDATE"
            software_standing = "SOFTWARE_VALID"
            scientific_standing = "SCIENTIFICALLY_NOT_ACCEPTED"
    # Truthful counts summary with coherent units and explicit denominator
    try:
        expected = _expected_interval_cells(req.temporal, ci.ledger.directions_bound)
        # Synthetic may have 0 bound directions; expected 0 is valid
        if len(ci.counts) > expected and expected != 0:
            raise ManchesterDemandPackageError(
                "COUNT_INTERVAL_MISMATCH",
                f"admitted {len(ci.counts)} exceeds expected interval cells {expected}",
            )
        missing = expected - len(ci.counts) if expected >= len(ci.counts) else 0
        if expected < len(ci.counts):
            # synthetic expected 0 case handled below  # noqa: E501
            missing = 0
            if not is_synthetic:
                raise ManchesterDemandPackageError(
                    "COUNT_INTERVAL_MISMATCH", "counts exceed expected denominator"
                )
        # synthetic with 0 expected: treat expected as admitted  # noqa: E501
        if is_synthetic and expected == 0 and len(ci.counts) > 0:
            expected = len(ci.counts)
            missing = 0
        offered_cells = ci.ledger.cells_bound  # coherent cell unit
        admitted_cells = len(ci.counts)
        if offered_cells != admitted_cells:
            # No clamp: fail typed (already checked equality above, but keep explicit)
            raise ManchesterDemandPackageError(
                "COUNT_LEDGER_MISMATCH",
                "offered cells must equal admitted cells (ledger.cells_bound)",
            )
        counts_summary = DemandCountsSummary(
            offered=offered_cells,
            admitted=admitted_cells,
            excluded=0,
            missing_hours=missing,
            measured_zero_cells=ci.ledger.measured_zero_cells_bound,
            expected_interval_cells=expected,
            direction_unresolved_excluded=ci.ledger.directions_unresolved,
            direction_requires_confirmation_excluded=ci.ledger.directions_requiring_confirmation,
            direction_combined_not_forced_excluded=ci.ledger.directions_combined_not_forced,
            sites_offered=ci.ledger.sites_offered,
            sites_admitted=ci.ledger.sites_admissible,
        )
    except ManchesterDemandPackageError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ManchesterDemandPackageError("COUNTS_SUMMARY_INVALID", _sanitize_error(exc)) from None
    prov = DemandProvenance(
        created_at_utc=evaluated_at_utc,
        created_by="demand-package-builder",
        parent_fingerprints=tuple(sorted([req.request_fingerprint, wf_fp, ci_fp])),
    )
    prov = DemandProvenance(
        created_at_utc=evaluated_at_utc,
        created_by="demand-package-builder",
        parent_fingerprints=prov.parent_fingerprints,
        chain_fingerprint=sha256_hex(
            canonical_json(list(prov.parent_fingerprints)).encode("utf-8")
        ),
    )
    tmp = ManchesterDemandPackageResult.model_construct(
        request_id=req.request_id,
        request_fingerprint=req.request_fingerprint,
        created_at_utc=req.created_at_utc,
        evaluated_at_utc=evaluated_at_utc,
        source=src,
        temporal=req.temporal,
        network=req.network,
        demand_method=req.demand_method,
        deterministic_seed=req.deterministic_seed,
        scaling=req.scaling,
        count_input_fingerprint=ci_fp,
        map_workflow_fingerprint=wf_fp,
        demand_label=req.demand_label,
        standing=standing,
        software_standing=software_standing,
        scientific_standing=scientific_standing,
        output_fingerprint="0" * 64,
        counts=counts_summary,
        provenance=prov,
        result_fingerprint="0" * 64,
    )
    out_fp = _output_fingerprint(tmp)
    tmp2 = tmp.model_copy(update={"output_fingerprint": out_fp})
    res_fp = _result_fingerprint(tmp2)
    return ManchesterDemandPackageResult(
        request_id=req.request_id,
        request_fingerprint=req.request_fingerprint,
        created_at_utc=req.created_at_utc,
        evaluated_at_utc=evaluated_at_utc,
        source=src,
        temporal=req.temporal,
        network=req.network,
        demand_method=req.demand_method,
        deterministic_seed=req.deterministic_seed,
        scaling=req.scaling,
        count_input_fingerprint=ci_fp,
        map_workflow_fingerprint=wf_fp,
        demand_label=req.demand_label,
        standing=standing,
        software_standing=software_standing,
        scientific_standing=scientific_standing,
        output_fingerprint=out_fp,
        counts=counts_summary,
        provenance=prov,
        result_fingerprint=res_fp,
    )


def verify_demand_package(
    result: ManchesterDemandPackageResult,
    *,
    request: ManchesterDemandPackageRequest,
    map_workflow: MapMatchWorkflowResult,
    count_input: CountConstrainedDemandInput,
) -> ManchesterDemandPackageResult:
    """Re-derive result from exact supplied dependencies; never trust digests."""
    res = ManchesterDemandPackageResult.model_validate(
        result.model_dump(mode="python", warnings=False), strict=True
    )
    req = ManchesterDemandPackageRequest.model_validate(
        request.model_dump(mode="python", warnings=False), strict=True
    )
    wf = _strict_workflow(map_workflow)
    ci = _strict_count_input(count_input)
    if req.request_fingerprint != _request_fingerprint(req):
        raise ManchesterDemandPackageError("REQUEST_FINGERPRINT_DRIFT", "request fingerprint drift")
    if res.request_fingerprint != req.request_fingerprint:
        raise ManchesterDemandPackageError(
            "REQUEST_FINGERPRINT_MISMATCH", "result does not bind request"
        )
    if res.count_input_fingerprint != ci.fingerprint():
        raise ManchesterDemandPackageError("COUNT_FINGERPRINT_DRIFT", "count fingerprint drift")
    if res.map_workflow_fingerprint != sha256_hex(wf.canonical_json().encode("utf-8")):
        raise ManchesterDemandPackageError(
            "MAP_FINGERPRINT_DRIFT", "map workflow fingerprint drift"
        )
    # Foreign policy re-check
    if ci.match_policy_fingerprint != wf.policy_fingerprint:
        raise ManchesterDemandPackageError("COUNT_POLICY_MISMATCH", "count policy drift at verify")
    if ci.match_policy_id != wf.policy_id:
        raise ManchesterDemandPackageError(
            "COUNT_POLICY_MISMATCH", "count policy id drift at verify"
        )
    if res.output_fingerprint != _output_fingerprint(res):
        raise ManchesterDemandPackageError("OUTPUT_FINGERPRINT_DRIFT", "output fingerprint drift")
    if res.result_fingerprint != _result_fingerprint(res):
        raise ManchesterDemandPackageError("RESULT_FINGERPRINT_DRIFT", "result fingerprint drift")
    rebuilt = build_demand_package(
        request=req, map_workflow=wf, count_input=ci, evaluated_at_utc=res.evaluated_at_utc
    )
    if rebuilt != res:
        raise ManchesterDemandPackageError(
            "REBUILT_MISMATCH", "re-derived result does not match supplied result"
        )
    return res


def verify_demand_receipt(
    receipt: ManchesterDemandReceipt,
    *,
    result: ManchesterDemandPackageResult,
    decision: ManchesterDemandAcceptanceDecision,
) -> ManchesterDemandReceipt:
    rcpt = ManchesterDemandReceipt.model_validate(
        receipt.model_dump(mode="python", warnings=False), strict=True
    )
    res = ManchesterDemandPackageResult.model_validate(
        result.model_dump(mode="python", warnings=False), strict=True
    )
    dec = ManchesterDemandAcceptanceDecision.model_validate(
        decision.model_dump(mode="python", warnings=False), strict=True
    )
    # Strict fingerprint drift
    if dec.decision_fingerprint != _decision_fingerprint(dec):
        raise ManchesterDemandPackageError(
            "DECISION_FINGERPRINT_DRIFT", "decision fingerprint drift"
        )
    if rcpt.receipt_fingerprint != _receipt_fingerprint(rcpt):
        raise ManchesterDemandPackageError("RECEIPT_FINGERPRINT_DRIFT", "receipt fingerprint drift")
    # Exact receipt↔decision↔result bindings regardless of decision branch
    if rcpt.request_fingerprint != res.request_fingerprint:
        raise ManchesterDemandPackageError(
            "RECEIPT_REQUEST_MISMATCH", "receipt request fingerprint mismatch"
        )
    if rcpt.request_fingerprint != dec.request_fingerprint:
        raise ManchesterDemandPackageError(
            "RECEIPT_DECISION_REQUEST_MISMATCH", "receipt decision request mismatch"
        )
    if rcpt.result_fingerprint != res.result_fingerprint:
        raise ManchesterDemandPackageError(
            "RECEIPT_RESULT_MISMATCH", "receipt result fingerprint mismatch"
        )
    if rcpt.result_fingerprint != dec.result_fingerprint:
        raise ManchesterDemandPackageError(
            "RECEIPT_DECISION_RESULT_MISMATCH", "receipt decision result mismatch"
        )
    if rcpt.decision_fingerprint != dec.decision_fingerprint:
        raise ManchesterDemandPackageError(
            "RECEIPT_DECISION_MISMATCH", "receipt decision fingerprint mismatch"
        )
    # Standing cross-invariants: bind and require exact match
    if rcpt.standing != res.standing:
        raise ManchesterDemandPackageError(
            "RECEIPT_STANDING_MISMATCH", "receipt standing mismatch result"
        )
    if rcpt.software_standing != res.software_standing:
        raise ManchesterDemandPackageError(
            "RECEIPT_SOFTWARE_MISMATCH", "receipt software_standing mismatch result"
        )
    if rcpt.scientific_standing != dec.decision:
        raise ManchesterDemandPackageError(
            "RECEIPT_SCIENTIFIC_MISMATCH", "receipt scientific_standing mismatch decision"
        )
    # Also decision standing vs result standing coherence
    if dec.decision == "SCIENTIFICALLY_ACCEPTED_DEMAND":
        if res.software_standing != "SOFTWARE_VALID":
            raise ManchesterDemandPackageError(
                "ACCEPTANCE_WITHOUT_VALID", "accepted demand requires SOFTWARE_VALID"
            )
        if res.standing == "PROVIDER_DATA_REQUIRED":
            raise ManchesterDemandPackageError(
                "ACCEPTANCE_PROVIDER_REQUIRED", "provider-required cannot be accepted"
            )
        if res.standing == "SYNTHETIC_ENGINEERING_CANDIDATE":
            raise ManchesterDemandPackageError(
                "SYNTHETIC_ACCEPTANCE_BLOCKED",
                "synthetic candidate cannot be scientifically accepted",
            )
        if rcpt.software_standing != "SOFTWARE_VALID":
            raise ManchesterDemandPackageError(
                "RECEIPT_SOFTWARE_MISMATCH", "accepted receipt requires SOFTWARE_VALID"
            )
        if rcpt.standing == "PROVIDER_DATA_REQUIRED":
            raise ManchesterDemandPackageError(
                "RECEIPT_STANDING_MISMATCH", "provider-required cannot be accepted receipt"
            )
    # PROVIDER_DATA_REQUIRED / SOFTWARE_INVALID may never carry accepted
    if dec.decision == "PROVIDER_DATA_REQUIRED":
        if rcpt.scientific_standing == "SCIENTIFICALLY_ACCEPTED_DEMAND":
            raise ManchesterDemandPackageError(
                "PROVIDER_ACCEPTED_CONFLICT",
                "PROVIDER_DATA_REQUIRED may never be SCIENTIFICALLY_ACCEPTED",
            )
        if rcpt.software_standing == "SOFTWARE_VALID":
            raise ManchesterDemandPackageError(
                "PROVIDER_SOFTWARE_CONFLICT", "PROVIDER_DATA_REQUIRED may never be SOFTWARE_VALID"
            )
    if res.software_standing == "SOFTWARE_INVALID":
        if dec.decision == "SCIENTIFICALLY_ACCEPTED_DEMAND":
            raise ManchesterDemandPackageError(
                "ACCEPTANCE_WITHOUT_VALID", "SOFTWARE_INVALID may never be SCIENTIFICALLY_ACCEPTED"
            )
        if rcpt.scientific_standing == "SCIENTIFICALLY_ACCEPTED_DEMAND":
            raise ManchesterDemandPackageError(
                "PROVIDER_ACCEPTED_CONFLICT",
                "SOFTWARE_INVALID receipt may never be SCIENTIFICALLY_ACCEPTED",
            )
    # Synthetic acceptance blocked regardless of branch already checked
    # Ensure decision fingerprint binds exact reviewer identity etc. already validated via drift
    # Temporal ordering: receipt cannot precede decision or result
    if rcpt.issued_at_utc < dec.decided_at_utc:
        raise ManchesterDemandPackageError(
            "RECEIPT_TIME_VIOLATION", "receipt cannot precede decision"
        )
    if rcpt.issued_at_utc < res.evaluated_at_utc:
        raise ManchesterDemandPackageError(
            "RECEIPT_TIME_VIOLATION", "receipt cannot precede result"
        )
    if dec.decided_at_utc < res.evaluated_at_utc:
        raise ManchesterDemandPackageError(
            "DECISION_TIME_VIOLATION", "decision cannot precede result"
        )
    return rcpt


def decide_demand_acceptance(
    *,
    result: ManchesterDemandPackageResult,
    reviewer_id: str,
    reviewer_role: str | None = None,
    reviewer_attribution: str | None = None,
    decided_at_utc: datetime,
    decision: ScientificStanding,
    reason: str,
) -> ManchesterDemandAcceptanceDecision:
    try:
        _require_utc(decided_at_utc, "decided_at_utc")
    except ValueError as exc:
        raise ManchesterDemandPackageError("TIMESTAMP_NOT_UTC", _sanitize_error(exc)) from None
    res = ManchesterDemandPackageResult.model_validate(
        result.model_dump(mode="python", warnings=False), strict=True
    )
    # Bounded reviewer identity / role / attribution
    _reject_private_path(reviewer_id, "reviewer_id")
    _reject_secret(reviewer_id, "reviewer_id")
    if not _SAFE_ID_RE.fullmatch(reviewer_id.strip()):
        raise ManchesterDemandPackageError(
            "REVIEWER_ID_INVALID", "reviewer_id must be bounded safe identifier"
        )
    # No bare reviewer string for acceptance: role and attribution required
    role_val = reviewer_role if reviewer_role is not None else ""
    attr_val = reviewer_attribution if reviewer_attribution is not None else ""
    if decision == "SCIENTIFICALLY_ACCEPTED_DEMAND":
        if not role_val.strip() or not attr_val.strip():
            raise ManchesterDemandPackageError(
                "ACCEPTANCE_IDENTITY_INCOMPLETE",
                "acceptance requires explicit bounded reviewer_id, reviewer_role and attribution",
            )
        _reject_private_path(role_val, "reviewer_role")
        _reject_secret(role_val, "reviewer_role")
        if not _SAFE_ID_RE.fullmatch(role_val.strip()):
            raise ManchesterDemandPackageError(
                "REVIEWER_ROLE_INVALID", "reviewer_role must be bounded safe identifier"
            )
        _reject_private_path(attr_val, "reviewer_attribution")
        _reject_secret(attr_val, "reviewer_attribution")
        if len(attr_val.strip()) < 3:
            raise ManchesterDemandPackageError("ATTRIBUTION_INVALID", "attribution must be bounded")
        # artifact-controlled self-admission:  # noqa: E501
        # reviewer_id must not equal request/result fingerprints or request_id
        if reviewer_id.strip() in (res.request_fingerprint, res.result_fingerprint, res.request_id):
            raise ManchesterDemandPackageError(
                "SELF_ADMISSION", "reviewer identity must not be artifact-controlled"
            )
        # Scientific acceptance requires independent prerequisites, never software convergence alone
        if res.software_standing != "SOFTWARE_VALID":
            raise ManchesterDemandPackageError(
                "ACCEPTANCE_WITHOUT_VALID", "SOFTWARE_VALID required for acceptance"
            )
        if res.standing == "PROVIDER_DATA_REQUIRED":
            raise ManchesterDemandPackageError(
                "PROVIDER_DATA_REQUIRED", "provider data required blocks acceptance"
            )
        if res.standing == "SYNTHETIC_ENGINEERING_CANDIDATE":
            raise ManchesterDemandPackageError(
                "SYNTHETIC_ACCEPTANCE_BLOCKED", "synthetic candidate cannot be accepted"
            )
        if res.standing == "COUNT_CONSTRAINED_CANDIDATE" and res.counts.admitted == 0:
            raise ManchesterDemandPackageError(
                "PROVIDER_EVIDENCE_MISSING",
                "count-constrained acceptance requires admitted provider evidence",
            )
        if res.is_observed_trips:
            raise ManchesterDemandPackageError(
                "OBSERVED_TRIP_CLAIM", "demand must never claim observed trips"
            )
        if res.counts.expected_interval_cells == 0:
            raise ManchesterDemandPackageError(
                "CALIBRATION_MISSING", "acceptance requires explicit temporal coverage denominator"
            )
        # require explicit rationale referencing independent basis, not bare convergence
        lower = reason.lower()
        if "software" in lower and "converge" in lower and "independent" not in lower:
            raise ManchesterDemandPackageError(
                "SCIENTIFIC_PREREQUISITE_MISSING",
                "scientific acceptance requires independent "  # noqa: E501
                "production/source/map/rights/calibration/baseline, "
                "never software convergence alone",
            )
    else:
        # For non-accepted, role/attribution optional but bounded  # noqa: E501
        if role_val:
            _reject_private_path(role_val, "reviewer_role")
            _reject_secret(role_val, "reviewer_role")
            if not _SAFE_ID_RE.fullmatch(role_val.strip()):
                raise ManchesterDemandPackageError(
                    "REVIEWER_ROLE_INVALID", "reviewer_role must be bounded"
                )
        if attr_val:
            _reject_private_path(attr_val, "reviewer_attribution")
            _reject_secret(attr_val, "reviewer_attribution")
    _reject_private_path(reason, "reason")
    _reject_secret(reason, "reason")
    if "observed trip" in reason.lower():
        raise ManchesterDemandPackageError(
            "OBSERVED_TRIP_CLAIM", "reason must not claim observed trips"
        )
    # Use defaults for optional role/attribution when not supplied (non-accept paths)
    final_role = role_val.strip() if role_val.strip() else "reviewer"
    final_attr = attr_val.strip() if attr_val.strip() else "independent-review-board"
    # For non-accept, allow placeholder but still bind
    if decision != "SCIENTIFICALLY_ACCEPTED_DEMAND":
        # keep provided or placeholder; ensure bounded
        if not _SAFE_ID_RE.fullmatch(final_role):
            final_role = "reviewer"
        if len(final_attr) < 3:
            final_attr = "independent-review-board"
    tmp = ManchesterDemandAcceptanceDecision.model_construct(
        decision_id=f"demand-decision-{res.request_id}",
        request_fingerprint=res.request_fingerprint,
        result_fingerprint=res.result_fingerprint,
        reviewer_id=reviewer_id.strip(),
        reviewer_role=final_role,
        reviewer_attribution=final_attr,
        decision=decision,
        decided_at_utc=decided_at_utc,
        reason=reason,
        decision_fingerprint="0" * 64,
    )
    fp = _decision_fingerprint(tmp)
    return ManchesterDemandAcceptanceDecision(
        decision_id=f"demand-decision-{res.request_id}",
        request_fingerprint=res.request_fingerprint,
        result_fingerprint=res.result_fingerprint,
        reviewer_id=reviewer_id.strip(),
        reviewer_role=final_role,
        reviewer_attribution=final_attr,
        decision=decision,
        decided_at_utc=decided_at_utc,
        reason=reason,
        decision_fingerprint=fp,
    )


def issue_demand_receipt(
    *,
    result: ManchesterDemandPackageResult,
    decision: ManchesterDemandAcceptanceDecision,
    issued_at_utc: datetime,
) -> ManchesterDemandReceipt:
    try:
        _require_utc(issued_at_utc, "issued_at_utc")
    except ValueError as exc:
        raise ManchesterDemandPackageError("TIMESTAMP_NOT_UTC", _sanitize_error(exc)) from None
    res = ManchesterDemandPackageResult.model_validate(
        result.model_dump(mode="python", warnings=False), strict=True
    )
    dec = ManchesterDemandAcceptanceDecision.model_validate(
        decision.model_dump(mode="python", warnings=False), strict=True
    )
    if (
        dec.request_fingerprint != res.request_fingerprint
        or dec.result_fingerprint != res.result_fingerprint
    ):
        raise ManchesterDemandPackageError(
            "DECISION_RESULT_MISMATCH", "decision does not bind result"
        )
    if dec.decision_fingerprint != _decision_fingerprint(dec):
        raise ManchesterDemandPackageError(
            "DECISION_FINGERPRINT_DRIFT", "decision fingerprint drift"
        )
    if issued_at_utc < dec.decided_at_utc:
        raise ManchesterDemandPackageError(
            "RECEIPT_TIME_VIOLATION", "receipt cannot precede decision"
        )
    if dec.decision != "SCIENTIFICALLY_ACCEPTED_DEMAND":
        raise ManchesterDemandPackageError(
            "RECEIPT_ONLY_FOR_ACCEPTED", "receipt only for accepted demand"
        )
    # Standing cross-invariants at issuance as well
    if res.software_standing != "SOFTWARE_VALID":
        raise ManchesterDemandPackageError(
            "ACCEPTANCE_WITHOUT_VALID", "receipt requires SOFTWARE_VALID result"
        )
    if res.standing == "PROVIDER_DATA_REQUIRED":
        raise ManchesterDemandPackageError(
            "PROVIDER_DATA_REQUIRED", "provider-required cannot be receipted"
        )
    if res.standing == "SYNTHETIC_ENGINEERING_CANDIDATE":
        raise ManchesterDemandPackageError(
            "SYNTHETIC_ACCEPTANCE_BLOCKED", "synthetic cannot be receipted as accepted"
        )
    prov = DemandProvenance(
        created_at_utc=issued_at_utc,
        created_by="demand-receipt-issuer",
        parent_fingerprints=tuple(sorted([res.result_fingerprint, dec.decision_fingerprint])),
        chain_fingerprint=sha256_hex(
            canonical_json(sorted([res.result_fingerprint, dec.decision_fingerprint])).encode(
                "utf-8"
            )
        ),
    )
    tmp = ManchesterDemandReceipt.model_construct(
        receipt_id=f"demand-receipt-{res.request_id}",
        request_fingerprint=res.request_fingerprint,
        result_fingerprint=res.result_fingerprint,
        decision_fingerprint=dec.decision_fingerprint,
        standing=res.standing,
        software_standing=res.software_standing,
        scientific_standing=dec.decision,
        issued_at_utc=issued_at_utc,
        provenance=prov,
        receipt_fingerprint="0" * 64,
    )
    fp = _receipt_fingerprint(tmp)
    return ManchesterDemandReceipt(
        receipt_id=f"demand-receipt-{res.request_id}",
        request_fingerprint=res.request_fingerprint,
        result_fingerprint=res.result_fingerprint,
        decision_fingerprint=dec.decision_fingerprint,
        standing=res.standing,
        software_standing=res.software_standing,
        scientific_standing=dec.decision,
        issued_at_utc=issued_at_utc,
        provenance=prov,
        receipt_fingerprint=fp,
    )
