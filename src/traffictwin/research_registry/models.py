"""Future-generic frozen strict ResearchStudyRecord family for B1.

This module provides a deterministic, bounded, fail-closed family that
captures study/version/title/question/hypothesis/status, explicit
relationship references (predecessor/successor/supersedes) where
supplied, provenance identities (code/manifest/evaluator/actor/
checkpoint/trace) where applicable, replication unit, seeds/draws,
arms, estimand, primary/secondary metrics, per-draw values, declared
summary and interval, evidence standing, admission status, limitations,
non-claims and product links.

Design goals
- Pydantic ``frozen=True`` + ``extra="forbid"`` everywhere.
- Canonical sorted JSON (``sort_keys=True``) and SHA-256 fingerprints.
- Bounded fields, deterministic ordering (sorted unique lists), explicit
  missingness via ``None``.
- Fail closed on extra fields, non-finite floats, duplicate identities,
  evidence/admission without exact 40-hex code SHA and 64-hex manifest
  hash, private absolute paths, likely secrets, and coherent
  draws/metrics/interval/evidence/admission.
- Valid to represent a future/unavailable study without evidence.

Relationship graph computation belongs to Lane 08; this lane only stores
explicitly supplied references. Authentic package admission is an
ingestion/service concern (Lane 08 trusted adapter), not inferable from
study letters in this generic model.

Do not hardcode E2 or E3; this family is generic.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Regular expressions and bounded constants
# ---------------------------------------------------------------------------

HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

STUDY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,63}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}$")
IDENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,63}$")
REPLICATION_UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")
ARM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")
METRIC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")

# Private absolute path detectors
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/tmp/|/var/folders/|[A-Za-z]:[\\/])")  # noqa: S108
_ABS_POSIX_RE = re.compile(r"^/[^ \n]*")
_WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")

# Secret keyword detector (case-insensitive)
_SECRET_RE = re.compile(
    r"(password|secret|api[_-]?key|token|credential|private[_-]?key|bearer)",
    re.IGNORECASE,
)

MAX_TITLE_LEN = 300
MAX_QUESTION_LEN = 2000
MAX_HYPOTHESIS_LEN = 2000
MAX_ESTIMAND_LEN = 2000
MAX_LIMITATION_LEN = 1000
MAX_NONCLAIM_LEN = 1000
MAX_PRODUCT_LINK_LEN = 500
MAX_RELATIONSHIPS = 32
MAX_SEEDS = 128
MAX_ARMS = 32
MAX_METRICS = 32
MAX_PER_DRAW = 4096
MAX_LIMITATIONS = 32
MAX_NONCLAIMS = 32
MAX_PRODUCT_LINKS = 32


def _is_finite(v: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _contains_private_path(s: str) -> bool:
    if _PRIVATE_PATH_RE.search(s):
        return True
    if _WINDOWS_ABS_RE.match(s):
        return True
    return bool(_ABS_POSIX_RE.match(s) and _PRIVATE_PATH_RE.search(s))


def _contains_secret(s: str) -> bool:
    return bool(_SECRET_RE.search(s))


def _check_no_private_or_secret(s: str, field_name: str = "field") -> str:
    if _contains_private_path(s):
        raise ValueError(f"{field_name} must not contain private absolute path: {s!r}")
    if _contains_secret(s):
        raise ValueError(f"{field_name} must not contain likely secret: {s!r}")
    return s


def _ensure_sorted_unique_str(values: list[str], field_name: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicate identities")
    return sorted(values)


def _ensure_sorted_unique_int(values: list[int], field_name: str) -> list[int]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicate identities")
    return sorted(values)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StudyStatus(StrEnum):
    """Generic study lifecycle status."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class EvidenceStanding(StrEnum):
    """Evidence standing – explicit unavailable vs available."""

    RESEARCH_EVIDENCE_FACT = "RESEARCH-EVIDENCE FACT"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DERIVED = "derived"
    PROVISIONAL = "provisional"


class AdmissionStatus(StrEnum):
    """Admission status – explicit admitted vs not."""

    ADMITTED = "admitted"
    NOT_ADMITTED = "not_admitted"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class PerDrawValue(StrictFrozenModel):
    """One per-draw observation."""

    draw: int = Field(ge=0, le=1_000_000, description="Replication draw identifier")
    value: float = Field(description="Observed value, must be finite")
    arm: str | None = Field(default=None, min_length=1, max_length=64, pattern=ARM_RE.pattern)
    metric: str | None = Field(default=None, min_length=1, max_length=64, pattern=METRIC_RE.pattern)

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not _is_finite(v):
            raise ValueError(f"value must be finite, got {v!r}")
        return float(v)

    @field_validator("arm", "metric")
    @classmethod
    def _arm_metric_no_secret(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _check_no_private_or_secret(v, "per-draw arm/metric")
        return v


class DeclaredSummary(StrictFrozenModel):
    """Declared summary with optional interval."""

    estimate: float = Field(description="Point estimate, must be finite")
    ci_lower: float | None = Field(
        default=None, description="Interval lower, must be finite if present"
    )
    ci_upper: float | None = Field(
        default=None, description="Interval upper, must be finite if present"
    )
    method: str | None = Field(
        default=None, min_length=1, max_length=200, description="Method label"
    )

    @field_validator("estimate", "ci_lower", "ci_upper")
    @classmethod
    def _finite_opt(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not _is_finite(v):
            raise ValueError(f"value must be finite, got {v!r}")
        return float(v)

    @field_validator("method")
    @classmethod
    def _method_clean(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _check_no_private_or_secret(v, "declared_summary.method")
        return v

    @model_validator(mode="after")
    def _interval_order(self) -> DeclaredSummary:
        if self.ci_lower is not None and self.ci_upper is not None:
            if not (self.ci_lower < self.ci_upper):
                raise ValueError(
                    f"interval ordering violated: lower {self.ci_lower} must be < "
                    f"upper {self.ci_upper}"
                )
            if not (self.ci_lower <= self.estimate <= self.ci_upper):
                raise ValueError(
                    f"estimate {self.estimate} must lie within interval "
                    f"[{self.ci_lower}, {self.ci_upper}]"
                )
        elif (self.ci_lower is None) != (self.ci_upper is None):
            raise ValueError("both ci_lower and ci_upper must be present together or both absent")
        return self


# ---------------------------------------------------------------------------
# Main family
# ---------------------------------------------------------------------------


class ResearchStudyRecord(StrictFrozenModel):
    """Future-generic frozen strict study record for B1."""

    # Core identity
    study: str = Field(
        min_length=1, max_length=64, pattern=STUDY_ID_RE.pattern, description="Study identifier"
    )
    version: str = Field(
        min_length=1, max_length=64, pattern=VERSION_RE.pattern, description="Study version"
    )
    title: str = Field(min_length=1, max_length=MAX_TITLE_LEN, description="Study title")
    question: str = Field(
        min_length=1, max_length=MAX_QUESTION_LEN, description="Research question"
    )
    hypothesis: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_HYPOTHESIS_LEN,
        description="Hypothesis if any",
    )
    status: StudyStatus = Field(description="Lifecycle status")

    # Relationships where explicitly supplied
    predecessor: list[str] | None = Field(
        default=None, max_length=MAX_RELATIONSHIPS, description="Predecessor study ids"
    )
    successor: list[str] | None = Field(
        default=None, max_length=MAX_RELATIONSHIPS, description="Successor study ids"
    )
    supersedes: list[str] | None = Field(
        default=None, max_length=MAX_RELATIONSHIPS, description="Superseded study ids"
    )

    # Provenance identities where applicable
    code_sha: str | None = Field(
        default=None, min_length=40, max_length=40, description="40-hex code SHA"
    )
    manifest_hash: str | None = Field(
        default=None, min_length=64, max_length=64, description="64-hex manifest hash"
    )
    evaluator_id: str | None = Field(
        default=None, min_length=1, max_length=128, description="Evaluator identity"
    )
    actor_id: str | None = Field(
        default=None, min_length=64, max_length=64, description="64-hex actor hash"
    )
    checkpoint_id: str | None = Field(
        default=None, min_length=64, max_length=64, description="64-hex checkpoint hash"
    )
    trace_id: str | None = Field(
        default=None, min_length=64, max_length=64, description="64-hex trace hash"
    )

    # Replication / experimental design
    replication_unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=REPLICATION_UNIT_RE.pattern,
    )
    seeds: list[int] | None = Field(
        default=None, max_length=MAX_SEEDS, description="Replication seeds"
    )
    draws: list[int] | None = Field(
        default=None, max_length=MAX_SEEDS, description="Replication draws"
    )
    arms: list[str] | None = Field(
        default=None, max_length=MAX_ARMS, description="Experimental arms"
    )
    estimand: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_ESTIMAND_LEN,
        description="Estimand description",
    )
    primary_metrics: list[str] | None = Field(
        default=None, max_length=MAX_METRICS, description="Primary metrics"
    )
    secondary_metrics: list[str] | None = Field(
        default=None, max_length=MAX_METRICS, description="Secondary metrics"
    )
    per_draw_values: list[PerDrawValue] | None = Field(
        default=None, max_length=MAX_PER_DRAW, description="Per-draw values"
    )
    declared_summary: DeclaredSummary | None = Field(
        default=None, description="Declared summary and interval"
    )

    # Standing and admission
    evidence_standing: EvidenceStanding = Field(description="Evidence standing")
    admission_status: AdmissionStatus = Field(description="Admission status")

    # Limitations, non-claims, product links
    limitations: list[str] | None = Field(
        default=None, max_length=MAX_LIMITATIONS, description="Limitations"
    )
    non_claims: list[str] | None = Field(
        default=None, max_length=MAX_NONCLAIMS, description="Non-claims"
    )
    product_links: list[str] | None = Field(
        default=None,
        max_length=MAX_PRODUCT_LINKS,
        description="Product links, no absolute private paths",
    )

    # -----------------------------------------------------------------------
    # Field validators
    # -----------------------------------------------------------------------

    @field_validator("study")
    @classmethod
    def _study_ok(cls, v: str) -> str:
        if not STUDY_ID_RE.match(v):
            raise ValueError(f"study must match {STUDY_ID_RE.pattern}, got {v!r}")
        _check_no_private_or_secret(v, "study")
        return v

    @field_validator("version")
    @classmethod
    def _version_ok(cls, v: str) -> str:
        if not VERSION_RE.match(v):
            raise ValueError(f"version must match {VERSION_RE.pattern}, got {v!r}")
        _check_no_private_or_secret(v, "version")
        return v

    @field_validator("title", "question", "hypothesis", "estimand")
    @classmethod
    def _text_no_private_secret(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _check_no_private_or_secret(v, "text field")
        return v

    @field_validator("predecessor", "successor", "supersedes")
    @classmethod
    def _relationship_items(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) == 0:
            return v
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("relationship identifier must be non-empty string")
            if not IDENT_RE.match(item):
                raise ValueError(f"relationship id {item!r} must match {IDENT_RE.pattern}")
            _check_no_private_or_secret(item, "relationship id")
        if len(v) != len(set(v)):
            raise ValueError("relationship list must not contain duplicate identities")
        return sorted(v)

    @field_validator("code_sha")
    @classmethod
    def _code_sha_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not HEX40_RE.match(v):
            raise ValueError(f"code_sha must be 40-hex, got {v!r}")
        return v.lower()

    @field_validator("manifest_hash")
    @classmethod
    def _manifest_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not HEX64_RE.match(v):
            raise ValueError(f"manifest_hash must be 64-hex, got {v!r}")
        return v.lower()

    @field_validator("actor_id", "checkpoint_id", "trace_id")
    @classmethod
    def _hash64_ok(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not HEX64_RE.match(v):
            raise ValueError(f"identity must be 64-hex, got {v!r}")
        return v.lower()

    @field_validator("evaluator_id", "replication_unit")
    @classmethod
    def _bounded_no_secret(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _check_no_private_or_secret(v, "identity field")
        return v

    @field_validator("seeds", "draws")
    @classmethod
    def _seeds_ok(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return None
        if len(v) != len(set(v)):
            raise ValueError("seeds/draws must not contain duplicate identities")
        for x in v:
            if not isinstance(x, int) or isinstance(x, bool):
                raise ValueError(f"seed/draw must be int, got {x!r}")
            if x < 0 or x > 1_000_000:
                raise ValueError(f"seed/draw {x!r} out of bounded range 0..1000000")
        return sorted(v)

    @field_validator("arms")
    @classmethod
    def _arms_ok(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) == 0:
            raise ValueError("arms must be non-empty if supplied")
        for a in v:
            if not isinstance(a, str) or not a.strip():
                raise ValueError("arm must be non-empty string")
            if not ARM_RE.match(a):
                raise ValueError(f"arm {a!r} must match {ARM_RE.pattern}")
            _check_no_private_or_secret(a, "arm")
        if len(v) != len(set(v)):
            raise ValueError("arms must not contain duplicate identities")
        return sorted(v)

    @field_validator("primary_metrics", "secondary_metrics")
    @classmethod
    def _metrics_ok(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) == 0:
            raise ValueError("metrics must be non-empty if supplied")
        for m in v:
            if not isinstance(m, str) or not m.strip():
                raise ValueError("metric must be non-empty string")
            if not METRIC_RE.match(m):
                raise ValueError(f"metric {m!r} must match {METRIC_RE.pattern}")
            _check_no_private_or_secret(m, "metric")
        if len(v) != len(set(v)):
            raise ValueError("metrics must not contain duplicate identities")
        return sorted(v)

    @field_validator("limitations", "non_claims")
    @classmethod
    def _limitations_ok(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) == 0:
            raise ValueError("limitations/non_claims must be non-empty if supplied")
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("limitation/non_claim must be non-empty")
            if len(item) > MAX_LIMITATION_LEN:
                raise ValueError("limitation/non_claim exceeds max length")
            _check_no_private_or_secret(item, "limitation/non_claim")
        if len(v) != len(set(v)):
            raise ValueError("limitations/non_claims must not contain duplicate identities")
        return sorted(v)

    @field_validator("product_links")
    @classmethod
    def _product_links_ok(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) == 0:
            raise ValueError("product_links must be non-empty if supplied")
        for link in v:
            if not isinstance(link, str) or not link.strip():
                raise ValueError("product_link must be non-empty")
            if len(link) > MAX_PRODUCT_LINK_LEN:
                raise ValueError("product_link exceeds max length")
            _check_no_private_or_secret(link, "product_link")
            if _contains_private_path(link):
                raise ValueError(f"product_link must not contain private absolute path: {link!r}")
            if (
                _WINDOWS_ABS_RE.match(link)
                or link.startswith(  # noqa: S108
                    "/Users/"
                )
                or link.startswith("/home/")  # noqa: S108
                or link.startswith("/tmp/")  # noqa: S108
                or link.startswith(  # noqa: S108
                    "/var/folders/"
                )
            ):
                raise ValueError(f"product_link must not be private absolute path: {link!r}")
        if len(v) != len(set(v)):
            raise ValueError("product_links must not contain duplicate identities")
        return sorted(v)

    @field_validator("per_draw_values")
    @classmethod
    def _per_draw_values_ok(cls, v: list[PerDrawValue] | None) -> list[PerDrawValue] | None:
        if v is None:
            return None
        if len(v) == 0:
            raise ValueError("per_draw_values must be non-empty if supplied")
        seen: set[tuple[int, str | None, str | None]] = set()
        for item in v:
            key = (item.draw, item.arm, item.metric)
            if key in seen:
                raise ValueError(f"per_draw_values contains duplicate identity {key!r}")
            seen.add(key)
            if not _is_finite(item.value):
                raise ValueError(f"per_draw value must be finite, got {item.value!r}")
        return sorted(v, key=lambda x: (x.draw, x.arm or "", x.metric or "", x.value))

    # -----------------------------------------------------------------------
    # Cross-field fail-closed validators
    # -----------------------------------------------------------------------

    @model_validator(mode="after")
    def _fail_closed(self) -> ResearchStudyRecord:
        # Self-reference in relationships
        for rel_name in ("predecessor", "successor", "supersedes"):
            rel: list[str] | None = getattr(self, rel_name)
            if rel is not None and self.study in rel:
                raise ValueError(f"{rel_name} must not contain self study id {self.study!r}")

        # Evidence / admission coherence: admitted/available need exact hashes
        is_unavailable_evidence = self.evidence_standing == EvidenceStanding.UNAVAILABLE
        evidence_requires_hash = not is_unavailable_evidence
        admission_requires_hash = self.admission_status == AdmissionStatus.ADMITTED

        if evidence_requires_hash or admission_requires_hash:
            if self.code_sha is None or self.manifest_hash is None:
                raise ValueError(
                    "evidence/admission requires exact 40-hex code_sha and 64-hex manifest_hash"
                )
            if not HEX40_RE.match(self.code_sha):
                raise ValueError(f"code_sha must be 40-hex, got {self.code_sha!r}")
            if not HEX64_RE.match(self.manifest_hash):
                raise ValueError(f"manifest_hash must be 64-hex, got {self.manifest_hash!r}")

        # Admission coherence: admitted implies evidence is not unavailable
        if admission_requires_hash and is_unavailable_evidence:
            raise ValueError("admitted record cannot have unavailable evidence standing")

        # Duplicate across primary/secondary metrics
        if self.primary_metrics is not None and self.secondary_metrics is not None:
            overlap = set(self.primary_metrics) & set(self.secondary_metrics)
            if overlap:
                raise ValueError(
                    f"primary and secondary metrics must not overlap duplicate {overlap!r}"
                )

        # Per-draw draws/metrics coherence with declared collections
        if self.per_draw_values is not None:
            if self.draws is not None:
                draw_set = set(self.draws)
                for pd in self.per_draw_values:
                    if pd.draw not in draw_set:
                        raise ValueError(
                            f"per_draw draw {pd.draw!r} not in declared draws {self.draws!r}"
                        )
            if self.arms is not None:
                arm_set = set(self.arms)
                for pd in self.per_draw_values:
                    if pd.arm is not None and pd.arm not in arm_set:
                        raise ValueError(
                            f"per_draw arm {pd.arm!r} not in declared arms {self.arms!r}"
                        )
            known_metrics: set[str] = set()
            if self.primary_metrics is not None:
                known_metrics.update(self.primary_metrics)
            if self.secondary_metrics is not None:
                known_metrics.update(self.secondary_metrics)
            if known_metrics:
                for pd in self.per_draw_values:
                    if pd.metric is not None and pd.metric not in known_metrics:
                        raise ValueError(
                            f"per_draw metric {pd.metric!r} not in declared metrics "
                            f"{sorted(known_metrics)!r}"
                        )

        # Deep scan for private paths / secrets across all string content
        dump = self.model_dump(mode="json")

        def _walk(obj: object, path: str = "$") -> None:
            if isinstance(obj, str):
                if _contains_private_path(obj):
                    raise ValueError(f"{path} contains private absolute path: {obj!r}")
                if _contains_secret(obj):
                    raise ValueError(f"{path} contains likely secret: {obj!r}")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    _walk(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _walk(v, f"{path}[{i}]")

        _walk(dump, "$")

        return self

    # -----------------------------------------------------------------------
    # Canonical helpers
    # -----------------------------------------------------------------------

    def canonical_json(self) -> str:
        """Canonical sorted JSON representation."""
        payload = self.model_dump(mode="json")
        return _canonical_json(payload)

    def fingerprint(self) -> str:
        """SHA-256 fingerprint of canonical JSON (hex)."""
        return _sha256_hex(self.canonical_json().encode("utf-8"))

    @classmethod
    def from_canonical_json(cls, data: str) -> ResearchStudyRecord:
        """Parse and validate canonical JSON string."""
        if not isinstance(data, str) or not data.strip():
            raise ValueError("canonical JSON must be non-empty string")
        if _PRIVATE_PATH_RE.search(data):
            raise ValueError("canonical JSON contains private absolute path")
        if _SECRET_RE.search(data):
            raise ValueError("canonical JSON contains likely secret")
        try:
            obj = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        return cls.model_validate(obj)


__all__ = [
    "ResearchStudyRecord",
    "PerDrawValue",
    "DeclaredSummary",
    "StudyStatus",
    "EvidenceStanding",
    "AdmissionStatus",
]
