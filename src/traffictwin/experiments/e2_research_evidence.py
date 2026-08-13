# ruff: noqa: E501, ANN401, SIM102
"""Strict Pydantic production model for frozen E2 package.

Covers exact source/study identities, strategy IDs, observations, fleet draws,
paired differences, declared summaries/CIs, evidence standing, provenance,
missingness reasons, partial task lifecycle, limitations and explicit non-claims.

Validation enforces:
- replication unit fleet_draw, evaluator seed 0, complete draw sets
- finite values, identity/hash shapes, unique IDs, CI ordering
- missing-value/reason coherence
- absence of private absolute paths/secrets
- deterministic path-free fingerprint
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants — frozen identities
# ---------------------------------------------------------------------------

EXPECTED_BASE_SHA: str = "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6"
EXPECTED_ACTOR_SHA256: str = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
EXPECTED_TRACE_SHA256: str = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"

EXPECTED_RESEARCH_HEADS: dict[str, str] = {
    "e2b": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
    "e2c": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
    "e2d": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
}

EXPECTED_MANIFESTS: frozenset[str] = frozenset(
    {
        "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
        "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
        "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
    }
)

# Strategy IDs — canonical short forms used in observations + matrix long forms.
ALLOWED_STRATEGY_IDS: frozenset[str] = frozenset(
    {
        "off",
        "jsq",
        "ingress_dla",
        "dla",
        "per_task_dla",
        "strongest_link_off",
        "jsq_without_gate",
        "common_target_dla",
    }
)

# Expected short IDs that must be present.
REQUIRED_STRATEGY_IDS: frozenset[str] = frozenset(
    {"off", "jsq", "ingress_dla", "dla", "per_task_dla"}
)

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

# Private-path / secret detectors (case-insensitive scan).
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/tmp/|/var/folders/|C:\\\\|D:\\\\)")
_SECRET_RE = re.compile(
    r"(password|secret|api[_-]?key|token|credential|workstation|private[_-]?key)",
    re.IGNORECASE,
)

# CI / observed attainment bounds
ATTAINMENT_MIN = 0.0
ATTAINMENT_MAX = 1.0
PAIRED_DIFF_MIN = -1.0
PAIRED_DIFF_MAX = 1.0

# Strict explicit tolerances for deterministic reconciliation of declared
# summaries against paired-difference per-draw values. Keep explicit so
# failure is loud on drift, and keep narrow to avoid hiding rounding.
MEAN_RECONCILIATION_TOL: float = 1e-12
SD_RECONCILIATION_TOL: float = 1e-12
SE_RECONCILIATION_TOL: float = 1e-12

# Comparison IDs where source declares no sd/se — must remain None/UNAVAILABLE.
SECONDARY_UNAVAILABLE_SD_SE_IDS: frozenset[str] = frozenset({"e2d_per_task_minus_dla"})


def _is_finite(v: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _scan_for_private_paths(obj: Any, path: str = "$") -> list[str]:
    """Recursively scan string values for private absolute paths/secrets."""
    violations: list[str] = []
    if isinstance(obj, str):
        if _PRIVATE_PATH_RE.search(obj):
            violations.append(f"{path}: absolute private path detected: {obj!r}")
        if _SECRET_RE.search(obj):
            violations.append(f"{path}: secret/credential keyword detected: {obj!r}")
        # Also reject any absolute-like path starting with / that looks private.
        # We only reject known private prefixes above to avoid false positives on
        # relative provenance paths like "docs/evaluation/...".
        # Double-check: any string starting with "/" and containing more than one "/" ?
        if obj.startswith("/") and "/" in obj[1:]:
            # Only flag if it looks like absolute workstation path
            if _PRIVATE_PATH_RE.search(obj):
                violations.append(f"{path}: absolute path rejected")
        # Also reject strings that look like absolute filesystem paths with drive letter.
        if re.match(r"^[A-Za-z]:\\\\", obj):
            violations.append(f"{path}: windows absolute path rejected: {obj!r}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            violations.extend(_scan_for_private_paths(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            violations.extend(_scan_for_private_paths(v, f"{path}[{i}]"))
    return violations


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvidenceStanding(StrEnum):
    RESEARCH_EVIDENCE_FACT = "RESEARCH-EVIDENCE FACT"
    SOURCE_DERIVED_FACT = "SOURCE-DERIVED FACT"
    IMPLEMENTATION_VERIFIED_FACT = "IMPLEMENTATION-VERIFIED FACT"
    INFERENCE = "INFERENCE"
    PROVISIONAL_WORDING = "PROVISIONAL WORDING"
    EXTERNAL_DECISION_REQUIRED = "EXTERNAL DECISION REQUIRED"


class ProvenanceStanding(StrEnum):
    RESEARCH_EVIDENCE_FACT = "RESEARCH-EVIDENCE FACT"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ActorIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha256: str = Field(description="SHA-256 of frozen actor checkpoint")
    training_seed: int = Field(ge=0)
    observes_current_rsu_load: bool = Field()
    selects_execution_rsu: bool = Field()

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not HEX64_RE.match(v):
            raise ValueError(f"actor sha256 must be 64 hex chars, got {v!r}")
        if v != EXPECTED_ACTOR_SHA256:
            raise ValueError(f"actor sha256 must be frozen {EXPECTED_ACTOR_SHA256}, got {v!r}")
        return v

    @field_validator("observes_current_rsu_load", "selects_execution_rsu")
    @classmethod
    def validate_false(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError("frozen actor must not observe RSU load nor select execution RSU")
        return v


class TraceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha256: str = Field(description="SHA-256 of frozen trace")

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not HEX64_RE.match(v):
            raise ValueError(f"trace sha256 must be 64 hex chars, got {v!r}")
        if v != EXPECTED_TRACE_SHA256:
            raise ValueError(f"trace sha256 must be frozen {EXPECTED_TRACE_SHA256}, got {v!r}")
        return v


class ResearchHeads(BaseModel):
    model_config = ConfigDict(extra="forbid")

    e2b: str = Field(description="E2b code commit 40 hex")
    e2c: str = Field(description="E2c code commit 40 hex")
    e2d: str = Field(description="E2d code commit 40 hex")

    @field_validator("e2b", "e2c", "e2d")
    @classmethod
    def validate_commit(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"commit must be 40 hex chars, got {v!r}")
        return v

    @model_validator(mode="after")
    def validate_expected(self) -> ResearchHeads:
        for key in ("e2b", "e2c", "e2d"):
            expected = EXPECTED_RESEARCH_HEADS[key]
            actual = getattr(self, key)
            if actual != expected:
                raise ValueError(f"research head {key} must be {expected}, got {actual!r}")
        return self


class SourceIdentities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_sha: str = Field(description="Frozen campaign base 40 hex")
    actor: ActorIdentity
    trace: TraceIdentity
    research_heads: ResearchHeads
    manifest_sha256_by_study: dict[str, str] = Field(description="Map study->manifest 64 hex")

    @field_validator("base_sha")
    @classmethod
    def validate_base(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"base_sha must be 40 hex chars, got {v!r}")
        if v != EXPECTED_BASE_SHA:
            raise ValueError(f"base_sha must be frozen {EXPECTED_BASE_SHA}, got {v!r}")
        return v

    @field_validator("manifest_sha256_by_study")
    @classmethod
    def validate_manifests(cls, v: dict[str, str]) -> dict[str, str]:
        for study, sha in v.items():
            if study not in {"e2b", "e2c", "e2d"}:
                raise ValueError(f"unexpected study key {study!r} in manifest map")
            if not HEX64_RE.match(sha):
                raise ValueError(f"manifest {study} must be 64 hex, got {sha!r}")
            if sha not in EXPECTED_MANIFESTS:
                raise ValueError(f"manifest {study} sha {sha!r} not in allowed frozen set")
        # Ensure all three studies present
        missing = {"e2b", "e2c", "e2d"} - set(v.keys())
        if missing:
            raise ValueError(f"missing manifest entries for {missing}")
        return v


class StrategyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(min_length=1, max_length=64)
    human_label: str = Field(min_length=1)
    placement: str = Field(min_length=1)
    admission_gate: str = Field(min_length=1)

    @field_validator("strategy_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if v not in ALLOWED_STRATEGY_IDS:
            raise ValueError(f"strategy_id {v!r} not in allowed {sorted(ALLOWED_STRATEGY_IDS)}")
        return v


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figure_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    arm: str = Field(min_length=1)
    value: float = Field(description="Attainment or paired difference, must be finite")
    manifest_sha256: str = Field(min_length=64, max_length=64)
    code_commit: str = Field(min_length=40, max_length=40)
    fleet_seed: int = Field(ge=0)
    evaluator_seed: int = Field()
    replication_unit: Literal["fleet_draw"] = Field()
    standing: str = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        if not _is_finite(v):
            raise ValueError(f"value must be finite, got {v!r}")
        return float(v)

    @field_validator("manifest_sha256")
    @classmethod
    def validate_manifest(cls, v: str) -> str:
        if not HEX64_RE.match(v):
            raise ValueError(f"manifest_sha256 must be 64 hex, got {v!r}")
        if v not in EXPECTED_MANIFESTS:
            raise ValueError(f"manifest_sha256 {v!r} not in frozen allowlist")
        return v

    @field_validator("code_commit")
    @classmethod
    def validate_commit(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"code_commit must be 40 hex, got {v!r}")
        # Must be one of the frozen heads or base
        allowed = set(EXPECTED_RESEARCH_HEADS.values()) | {EXPECTED_BASE_SHA}
        if v not in allowed:
            raise ValueError(f"code_commit {v!r} not in frozen allowed set")
        return v

    @field_validator("evaluator_seed")
    @classmethod
    def validate_evaluator_seed(cls, v: int) -> int:
        if v != 0:
            raise ValueError(f"evaluator_seed must be 0 (frozen), got {v}")
        return v


class FleetDrawSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study: str = Field(description="e2b|e2c|e2d")
    fleet_seeds: list[int] = Field(min_length=1)
    replication_unit: Literal["fleet_draw"] = Field()
    evaluator_seed: int = Field()

    @field_validator("study")
    @classmethod
    def validate_study(cls, v: str) -> str:
        if v not in {"e2b", "e2c", "e2d"}:
            raise ValueError(f"study must be e2b/e2c/e2d, got {v!r}")
        return v

    @field_validator("evaluator_seed")
    @classmethod
    def validate_seed(cls, v: int) -> int:
        if v != 0:
            raise ValueError(f"evaluator_seed must be 0, got {v}")
        return v

    @field_validator("fleet_seeds")
    @classmethod
    def validate_seeds(cls, v: list[int]) -> list[int]:
        if len(v) != len(set(v)):
            raise ValueError(f"fleet_seeds must be unique, got {v}")
        for s in v:
            if not isinstance(s, int) or s < 0:
                raise ValueError(f"fleet_seed must be non-negative int, got {s!r}")
        return v

    @model_validator(mode="after")
    def validate_complete_sets(self) -> FleetDrawSet:
        if self.study == "e2b":
            if self.fleet_seeds != [0]:
                raise ValueError(f"e2b fleet_seeds must be [0], got {self.fleet_seeds}")
        elif self.study in {"e2c", "e2d"}:
            if sorted(self.fleet_seeds) != [1, 2, 3, 4]:
                raise ValueError(
                    f"{self.study} fleet_seeds must be [1,2,3,4], got {self.fleet_seeds}"
                )
        return self


class PairedDifferenceSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: str = Field(min_length=1)
    fleet_seeds: list[int] = Field(min_length=1)
    per_seed_values: list[float] = Field(min_length=1)
    replication_unit: Literal["fleet_draw"] = Field()

    @field_validator("per_seed_values")
    @classmethod
    def validate_finite(cls, v: list[float]) -> list[float]:
        for x in v:
            if not _is_finite(x):
                raise ValueError(f"per_seed_values must be finite, got {x!r}")
        return [float(x) for x in v]

    @model_validator(mode="after")
    def validate_sets(self) -> PairedDifferenceSet:
        if len(self.fleet_seeds) != len(self.per_seed_values):
            raise ValueError(f"fleet_seeds {self.fleet_seeds} and per_seed_values length mismatch")
        if len(self.fleet_seeds) != len(set(self.fleet_seeds)):
            raise ValueError("fleet_seeds must be unique")
        if sorted(self.fleet_seeds) != [1, 2, 3, 4]:
            raise ValueError(
                f"paired difference fleet_seeds must be [1,2,3,4], got {self.fleet_seeds}"
            )
        return self


class DeclaredSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison_id: str = Field(min_length=1)
    mean: float = Field()
    lower: float = Field()
    upper: float = Field()
    # Optional provenance stats
    sample_sd: float | None = Field(default=None)
    standard_error: float | None = Field(default=None)
    degrees_of_freedom: int | None = Field(default=None)
    method: str = Field(min_length=1)
    includes_zero: bool = Field()
    decision: str = Field(min_length=1)

    @field_validator("mean", "lower", "upper", "sample_sd", "standard_error")
    @classmethod
    def validate_finite_opt(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not _is_finite(v):
            raise ValueError(f"value must be finite, got {v!r}")
        return float(v)

    @model_validator(mode="after")
    def validate_ci_ordering(self) -> DeclaredSummary:
        if not (self.lower < self.upper):
            raise ValueError(
                f"CI ordering violated: lower {self.lower} must be < upper {self.upper}"
            )
        # Determine if CI includes zero
        ci_includes_zero = self.lower <= 0 <= self.upper
        if ci_includes_zero != self.includes_zero:
            raise ValueError(
                f"includes_zero {self.includes_zero} inconsistent with CI [{self.lower}, {self.upper}]"
            )
        # Mean must lie within CI (inclusive)
        if not (self.lower <= self.mean <= self.upper):
            # Allow tiny epsilon due to rounding? Be strict: must be within.
            raise ValueError(f"mean {self.mean} must lie within CI [{self.lower}, {self.upper}]")
        return self


class ProvenanceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: str = Field(min_length=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    code_commit: str = Field(min_length=40, max_length=40)
    standing: str = Field(min_length=1)

    @field_validator("manifest_sha256")
    @classmethod
    def validate_manifest(cls, v: str) -> str:
        if not HEX64_RE.match(v):
            raise ValueError(f"manifest_sha256 must be 64 hex, got {v!r}")
        if v not in EXPECTED_MANIFESTS:
            raise ValueError(f"manifest_sha256 {v!r} not in frozen allowlist")
        return v

    @field_validator("code_commit")
    @classmethod
    def validate_commit(cls, v: str) -> str:
        if not HEX40_RE.match(v):
            raise ValueError(f"code_commit must be 40 hex, got {v!r}")
        allowed = set(EXPECTED_RESEARCH_HEADS.values()) | {EXPECTED_BASE_SHA}
        if v not in allowed:
            raise ValueError(f"code_commit {v!r} not in frozen allowed set")
        return v


class MissingnessReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("missingness reason must be non-empty")
        if _PRIVATE_PATH_RE.search(v) or _SECRET_RE.search(v):
            raise ValueError(f"reason must not contain private path/secret: {v!r}")
        return v


class PartialTaskLifecycle(BaseModel):
    """Partial lifecycle for E2d seed 1 — unavailable fields are None with reasons.

    Conservation: offered == admitted + rejected_total, forwarded <= admitted,
    deadline_success <= admitted, deadline_success <= offered.
    """

    model_config = ConfigDict(extra="forbid")

    offered: int = Field(ge=0)
    admitted: int = Field(ge=0)
    rejected_total: int = Field(ge=0)
    forwarded: int = Field(ge=0)
    deadline_success: int = Field(ge=0)
    # Unavailable / optional fields — None means unavailable.
    gate_rejected: int | None = Field(default=None, ge=0)
    capacity_rejected: int | None = Field(default=None, ge=0)
    started: int | None = Field(default=None, ge=0)
    compute_completed: int | None = Field(default=None, ge=0)
    returned: int | None = Field(default=None, ge=0)
    dropped: int | None = Field(default=None, ge=0)
    unavailable_reasons: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_coherence(self) -> PartialTaskLifecycle:
        # Conservation
        if self.offered != self.admitted + self.rejected_total:
            raise ValueError(
                f"lifecycle conservation violated: offered {self.offered} != admitted {self.admitted} + rejected_total {self.rejected_total}"
            )
        if self.forwarded > self.admitted:
            raise ValueError(f"forwarded {self.forwarded} must be <= admitted {self.admitted}")
        if self.deadline_success > self.admitted:
            raise ValueError(
                f"deadline_success {self.deadline_success} must be <= admitted {self.admitted}"
            )
        if self.deadline_success > self.offered:
            raise ValueError(
                f"deadline_success {self.deadline_success} must be <= offered {self.offered}"
            )

        # Missingness coherence: unavailable field (None) must have reason, available must not.
        for field in (
            "gate_rejected",
            "capacity_rejected",
            "started",
            "compute_completed",
            "returned",
            "dropped",
        ):
            val = getattr(self, field)
            has_reason = field in self.unavailable_reasons
            if val is None and not has_reason:
                raise ValueError(
                    f"field {field} is None (unavailable) but missing reason in unavailable_reasons"
                )
            if val is not None and has_reason:
                raise ValueError(f"field {field} has value {val} but also has unavailable reason")
            if has_reason:
                reason = self.unavailable_reasons[field]
                if not reason or not reason.strip():
                    raise ValueError(f"reason for {field} must be non-empty")
                if _PRIVATE_PATH_RE.search(reason) or _SECRET_RE.search(reason):
                    raise ValueError(f"reason for {field} must not contain private path/secret")
        # Extra keys in unavailable_reasons must correspond to known optional fields.
        allowed_unavailable = {
            "gate_rejected",
            "capacity_rejected",
            "started",
            "compute_completed",
            "returned",
            "dropped",
        }
        for k in self.unavailable_reasons:
            if k not in allowed_unavailable:
                raise ValueError(f"unexpected key {k!r} in unavailable_reasons")
        # Dedicated frozen E2 package: all six source-declared unavailable fields must
        # remain UNAVAILABLE as independently instrumented quantities — never zero/number.
        for _field in (
            "gate_rejected",
            "capacity_rejected",
            "started",
            "compute_completed",
            "returned",
            "dropped",
        ):
            if getattr(self, _field) is not None:
                raise ValueError(
                    f"field {_field} is UNAVAILABLE as an independently instrumented quantity and must be None (fail-closed; zero/any number is not allowed)"
                )
            # Ensure the UNAVAILABLE reason is present and does not claim started == admitted.
            _reason = self.unavailable_reasons.get(_field, "")
            if "==" in _reason and "admitted" in _reason:
                raise ValueError(
                    f"reason for {_field} must not claim equality with admitted; use 'UNAVAILABLE as an independently instrumented quantity'"
                )
        # Explicitly forbid started == admitted equality claim even in case of future relaxation.
        started_reason = self.unavailable_reasons.get("started", "")
        if "started == admitted" in started_reason or "== admitted" in started_reason:
            raise ValueError(
                "started reason must be 'UNAVAILABLE as an independently instrumented quantity' and must not claim 'started == admitted' as a measured fact"
            )
        return self


# ---------------------------------------------------------------------------
# Top-level package
# ---------------------------------------------------------------------------


class E2ResearchEvidencePackage(BaseModel):
    """Frozen E2 research evidence package — strict, path-free fingerprinted."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["v08_e2_research_evidence_v1"] = Field()
    campaign: Literal["v08-requirements-closure"] = Field()
    source_identities: SourceIdentities
    replication_unit: Literal["fleet_draw"] = Field()
    evaluator_seed: Literal[0] = Field()
    strategies: list[StrategyRecord] = Field(min_length=1)
    observations: list[Observation] = Field(min_length=1)
    fleet_draw_sets: list[FleetDrawSet] = Field(min_length=1)
    paired_differences: list[PairedDifferenceSet] = Field(min_length=1)
    declared_summaries: list[DeclaredSummary] = Field(min_length=1)
    provenance: list[ProvenanceEntry] = Field(min_length=1)
    missingness: list[MissingnessReason] = Field(default_factory=list)
    task_lifecycle: PartialTaskLifecycle
    limitations: list[str] = Field(min_length=1)
    non_claims: list[str] = Field(min_length=1)

    @field_validator("limitations", "non_claims")
    @classmethod
    def validate_nonempty_strings(cls, v: list[str]) -> list[str]:
        for s in v:
            if not s or not s.strip():
                raise ValueError("limitation/non_claim must be non-empty string")
            if _PRIVATE_PATH_RE.search(s) or _SECRET_RE.search(s):
                raise ValueError(
                    f"limitation/non_claim must not contain private path/secret: {s!r}"
                )
        return v

    @model_validator(mode="after")
    def validate_cross_fields(self) -> E2ResearchEvidencePackage:
        # Unique IDs
        figure_ids = [o.figure_id for o in self.observations]
        if len(figure_ids) != len(set(figure_ids)):
            raise ValueError(f"figure_id must be unique, duplicates in {figure_ids}")
        strategy_ids = [s.strategy_id for s in self.strategies]
        if len(strategy_ids) != len(set(strategy_ids)):
            raise ValueError(f"strategy_id must be unique, got {strategy_ids}")
        # Require all REQUIRED_STRATEGY_IDS present (allow long-form aliases)
        # Check that each required short id appears either directly or via alias mapping
        # Map long aliases to short: strongest_link_off->off, jsq_without_gate->jsq, common_target_dla->dla
        alias_map = {
            "strongest_link_off": "off",
            "jsq_without_gate": "jsq",
            "common_target_dla": "dla",
        }
        present_shorts = set()
        for sid in strategy_ids:
            present_shorts.add(alias_map.get(sid, sid))
        missing = REQUIRED_STRATEGY_IDS - present_shorts
        if missing:
            raise ValueError(f"missing required strategy_ids {missing}, present {strategy_ids}")

        # Replication unit already literal but also ensure fleet_draw_sets match
        for fds in self.fleet_draw_sets:
            if fds.replication_unit != self.replication_unit:
                raise ValueError("fleet_draw_set replication_unit mismatch top-level")
            if fds.evaluator_seed != self.evaluator_seed:
                raise ValueError("fleet_draw_set evaluator_seed mismatch top-level")

        # Paired differences replication unit must match top
        for pd in self.paired_differences:
            if pd.replication_unit != self.replication_unit:
                raise ValueError(f"paired difference {pd.comparison_id} replication_unit mismatch")

        # Finite checks for declared summaries already done, but also ensure
        # provenance manifests align with source identities
        source_manifests = set(self.source_identities.manifest_sha256_by_study.values())
        for prov in self.provenance:
            if (
                prov.manifest_sha256 not in source_manifests
                and prov.manifest_sha256 not in EXPECTED_MANIFESTS
            ):
                raise ValueError(
                    f"provenance manifest {prov.manifest_sha256!r} not in source identities"
                )

        # Fail-closed binding: every declared summary must map to a
        # paired_differences comparison_id and reconcile deterministically.
        # - declared mean must equal arithmetic mean of per_seed_values
        #   within MEAN_RECONCILIATION_TOL
        # - for source-declared sd/se comparisons, reconcile sample_sd and
        #   standard_error within strict tolerances
        # - for secondary (source-absent) ids, sd/se must remain None/UNAVAILABLE
        # Do not recompute CI with a different statistical method — only
        # strict mean/sd/se binding.
        pd_ids = {pd.comparison_id for pd in self.paired_differences}
        ds_ids = {ds.comparison_id for ds in self.declared_summaries}
        if len(pd_ids) != len(self.paired_differences):
            raise ValueError("paired_differences comparison_id must be unique")
        if len(ds_ids) != len(self.declared_summaries):
            raise ValueError("declared_summaries comparison_id must be unique")
        # Every paired_difference must have a declared summary and vice versa
        # (fail-closed linkage). Exact equality ensures no orphan summary or
        # missing comparison.
        if pd_ids != ds_ids:
            raise ValueError(
                f"declared_summaries and paired_differences comparison_ids must match exactly: "
                f"paired {sorted(pd_ids)} vs declared {sorted(ds_ids)}"
            )
        pd_by_id: dict[str, PairedDifferenceSet] = {
            pd.comparison_id: pd for pd in self.paired_differences
        }
        for ds in self.declared_summaries:
            pd_opt = pd_by_id.get(ds.comparison_id)
            if pd_opt is None:
                raise ValueError(
                    f"declared summary {ds.comparison_id!r} has no matching paired_differences entry"
                )
            matched_pd: PairedDifferenceSet = pd_opt
            # Deterministic mean reconciliation within strict explicit tolerance
            expected_mean = sum(matched_pd.per_seed_values) / len(matched_pd.per_seed_values)
            if abs(ds.mean - expected_mean) > MEAN_RECONCILIATION_TOL:
                raise ValueError(
                    f"declared summary {ds.comparison_id!r} mean {ds.mean} drifts from "
                    f"paired per_seed_values mean {expected_mean} by "
                    f"{abs(ds.mean - expected_mean)} > {MEAN_RECONCILIATION_TOL}"
                )
            if ds.comparison_id in SECONDARY_UNAVAILABLE_SD_SE_IDS:
                if ds.sample_sd is not None or ds.standard_error is not None:
                    raise ValueError(
                        f"declared summary {ds.comparison_id!r} sample_sd/standard_error must be "
                        f"None/UNAVAILABLE — source declares no such fields and fabricated values "
                        f"contradict per-draw values/CI; got sample_sd={ds.sample_sd!r}, "
                        f"standard_error={ds.standard_error!r}"
                    )
            else:
                # Primary source-declared sd/se — must be present and consistent
                if ds.sample_sd is None or ds.standard_error is None:
                    raise ValueError(
                        f"declared summary {ds.comparison_id!r} missing source-declared "
                        f"sample_sd/standard_error"
                    )
                n = len(matched_pd.per_seed_values)
                # sample standard deviation with Bessel's correction (ddof=1)
                mean = expected_mean
                var = (
                    sum((x - mean) ** 2 for x in matched_pd.per_seed_values) / (n - 1)
                    if n > 1
                    else 0.0
                )
                expected_sd = math.sqrt(var)
                expected_se = expected_sd / math.sqrt(n) if n > 0 else 0.0
                if abs(ds.sample_sd - expected_sd) > SD_RECONCILIATION_TOL:
                    raise ValueError(
                        f"declared summary {ds.comparison_id!r} sample_sd {ds.sample_sd} drifts from "
                        f"expected {expected_sd} by {abs(ds.sample_sd - expected_sd)} > {SD_RECONCILIATION_TOL}"
                    )
                if abs(ds.standard_error - expected_se) > SE_RECONCILIATION_TOL:
                    raise ValueError(
                        f"declared summary {ds.comparison_id!r} standard_error {ds.standard_error} drifts from "
                        f"expected {expected_se} by {abs(ds.standard_error - expected_se)} > {SE_RECONCILIATION_TOL}"
                    )

        # Fail-closed on started equality claim: owner contract forbids claiming
        # started == admitted as a measured fact. The faithful bounded reason is
        # UNAVAILABLE as an independently instrumented quantity.
        for m in self.missingness:
            if m.field == "started" and "==" in m.reason and "admitted" in m.reason:
                raise ValueError(
                    "missingness reason for started must not claim 'started == admitted'; use 'UNAVAILABLE as an independently instrumented quantity'"
                )
            if m.field == "started" and "treated as admitted" in m.reason:
                raise ValueError(
                    "missingness reason for started must not claim treated as admitted; use 'UNAVAILABLE as an independently instrumented quantity'"
                )

        # Absence of private absolute paths/secrets across entire payload
        violations = _scan_for_private_paths(self.model_dump(mode="json"))
        if violations:
            raise ValueError(f"private path/secret detected: {violations[:3]}")

        return self

    # -----------------------------------------------------------------------
    # Fingerprint — deterministic, path-free, no timestamps
    # -----------------------------------------------------------------------

    def _fingerprint_payload(self) -> dict[str, Any]:
        """Build canonical payload for fingerprint — excludes absolute paths."""
        raw = self.model_dump(mode="json")

        # Exclude any keys that are paths or that could contain absolute paths
        # We deep-strip any string value that looks like absolute private path.
        # Also exclude provenance artifact strings that might be relative docs paths?
        # But docs/evaluation/... relative paths are allowed and not private.
        # We only strip absolute private paths — they should already be rejected.
        # For path-free guarantee, we ensure fingerprint does NOT include any
        # field named artifact_path or similar if present — but our model
        # currently has no artifact_path at top level; observations do not
        # contain artifact_path either (we removed it). If we ever add it,
        # we strip it.
        def _strip(o: Any) -> Any:
            if isinstance(o, dict):
                out: dict[str, Any] = {}
                for k, v in o.items():
                    if k in {
                        "artifact_path",
                        "raw_root",
                        "raw_path",
                        "actor_path",
                        "trace_path",
                        "file_path",
                    }:
                        continue
                    # Recursively strip
                    stripped = _strip(v)
                    out[k] = stripped
                return out
            if isinstance(o, list):
                return [_strip(x) for x in o]
            if isinstance(o, str):
                # If string is an absolute private path, replace with placeholder (should not happen)
                if _PRIVATE_PATH_RE.search(o):
                    return "<redacted-path>"
                return o
            return o

        payload = _strip(raw)
        # Also sort and ensure deterministic types: convert all floats via repr?
        # json.dumps with sort_keys handles ordering.
        return payload  # type: ignore[no-any-return]

    def fingerprint(self) -> str:
        """Deterministic path-free fingerprint — sha256 of canonical JSON."""
        payload = self._fingerprint_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_MAX_JSON_BYTES = 500_000  # guard against oversized payloads


def load_e2_research_evidence_json(text: str) -> E2ResearchEvidencePackage:
    """Parse and strictly validate E2 research evidence JSON.

    Rejects:
    - oversized payloads
    - private absolute paths / secrets in raw text
    - malformed JSON
    - schema violations (via Pydantic)
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if len(text.encode("utf-8")) > _MAX_JSON_BYTES:
        raise ValueError(f"payload exceeds {_MAX_JSON_BYTES} bytes")
    # Early scan for private paths/secrets in raw text before parsing
    if _PRIVATE_PATH_RE.search(text):
        raise ValueError("payload contains private absolute path (e.g. /Users/, /home/)")
    if _SECRET_RE.search(text):
        # Allow the word "secret" only in non-claim context? Be strict: reject any secret keyword
        # Need to avoid false positive on legitimate limitation text containing "secret"?
        # Our model limitations do not contain secret keywords, so safe to reject.
        # But to avoid breaking valid payload that mentions "no secrets", we check for
        # assignment-like patterns: password=, secret=
        secret_assign_re = re.compile(r"(password|secret|api_key|token)\s*[:=]", re.IGNORECASE)
        if secret_assign_re.search(text):
            raise ValueError("payload contains secret/credential assignment")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top-level JSON must be object")
    # Additional scan on parsed structure for private paths
    violations = _scan_for_private_paths(data)
    if violations:
        raise ValueError(f"private path/secret in payload: {violations[0]}")
    return E2ResearchEvidencePackage.model_validate(data)


__all__ = [
    "E2ResearchEvidencePackage",
    "load_e2_research_evidence_json",
    "ActorIdentity",
    "TraceIdentity",
    "ResearchHeads",
    "SourceIdentities",
    "StrategyRecord",
    "Observation",
    "FleetDrawSet",
    "PairedDifferenceSet",
    "DeclaredSummary",
    "ProvenanceEntry",
    "MissingnessReason",
    "PartialTaskLifecycle",
]
