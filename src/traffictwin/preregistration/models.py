"""Typed domain models for the Preregistration Studio governance workflow."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.domain.scenario import _validate_identifier

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class StrictModel(BaseModel):
    """Base that rejects unknown fields and validates on assignment."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


# Reuse authoritative identifier validation; preregistration owns no separate regex.


def _validate_plan_identifier(value: str, field_name: str) -> str:
    # Delegate to authoritative helper to avoid duplication
    result = _validate_identifier(value, field_name)
    if result is None:
        raise ValueError(f"{field_name} must not be empty")
    return result


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StudyPlanStatus(StrEnum):
    DRAFT = "DRAFT"
    FROZEN = "FROZEN"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    DECIDED = "DECIDED"
    CLOSED = "CLOSED"


class EvidenceMode(StrEnum):
    AUTHORED_CONFIGURATION = "authored_configuration"
    SYNTHETIC_EVIDENCE = "synthetic_evidence"
    IMPORTED_EVIDENCE = "imported_evidence"
    HISTORICAL_OBSERVATION = "historical_observation"
    NEAR_LIVE_OPERATIONAL = "near_live_operational"
    ADMITTED_RESEARCH = "admitted_research"
    UNADMITTED_RESEARCH = "unadmitted_research"
    STATIC_GEOGRAPHIC = "static_geographic"
    UNAVAILABLE = "unavailable"


class ReplicationUnit(StrEnum):
    RANDOM_SEED = "random_seed"
    RUN_REPLICATE = "run_replicate"
    SCENARIO_SEED = "scenario_seed"
    VEHICLE = "vehicle"
    RSU = "rsu"
    TIME_WINDOW = "time_window"
    OTHER = "other"


class MissingnessPolicy(StrEnum):
    COMPLETE_CASE = "complete_case"
    EXCLUDE_MISSING = "exclude_missing"
    FLAG_MISSING = "flag_missing"
    NOT_APPLICABLE = "not_applicable"
    AVAILABLE_CASE = "available_case"
    NO_IMPUTATION = "no_imputation"


class AnalysisMethod(StrEnum):
    PAIRED_MEAN_DIFFERENCE = "paired_mean_difference"
    PAIRED_BOOTSTRAP = "paired_bootstrap"
    SIGN_FLIP = "sign_flip"
    TOST_EQUIVALENCE = "tost_equivalence"
    DESCRIPTIVE = "descriptive"
    REGRESSION = "regression"
    MIXED_EFFECTS = "mixed_effects"
    COX_REGRESSION = "cox_regression"
    RANK_BASED = "rank_based"


class MultiplicityPolicy(StrEnum):
    NONE_SINGLE_TEST = "none_single_test"
    BONFERRONI = "bonferroni"
    HOLM = "holm"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"
    HIERARCHICAL = "hierarchical"
    NOT_APPLICABLE = "not_applicable"


class DecisionGateStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"
    READY = "ready"


class AmendmentLabel(StrEnum):
    PRE_EVIDENCE = "pre_evidence"
    POST_EVIDENCE = "post_evidence"


class ArtifactAdmission(StrEnum):
    ADMITTED = "admitted"
    UNADMITTED = "unadmitted"
    SYNTHETIC = "synthetic"
    IMPORTED = "imported"
    HISTORICAL = "historical"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def is_explicitly_admitted(att: EvidenceAttachment) -> bool:
    """Authoritative admission check: only is_admitted==True counts."""
    return att.is_admitted is True


# ---------------------------------------------------------------------------
# Small models
# ---------------------------------------------------------------------------


class StudyQuestion(StrictModel):
    text: str = Field(min_length=12)
    hypothesis: str | None = None
    background: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 12:
            raise ValueError("study question must contain at least 12 characters")
        return s

    @field_validator("hypothesis", "background")
    @classmethod
    def validate_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class OutcomeDefinition(StrictModel):
    outcome_id: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    denominator: str | None = None
    description: str = Field(min_length=8)
    higher_is_better: bool | None = None

    @field_validator("outcome_id")
    @classmethod
    def validate_outcome_id(cls, v: str) -> str:
        return _validate_plan_identifier(v, "outcome_id")

    @field_validator("metric_key", "metric_version", "unit")
    @classmethod
    def validate_required_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    @field_validator("denominator")
    @classmethod
    def validate_denominator(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("denominator must contain non-space characters when provided")
        return s

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 8:
            raise ValueError("description must contain at least 8 characters")
        return s


class EstimandDefinition(StrictModel):
    estimand_id: str = Field(min_length=1)
    description: str = Field(min_length=12)
    population: str = Field(min_length=4)
    effect_measure: str = Field(min_length=2)

    @field_validator("estimand_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_plan_identifier(v, "estimand_id")

    @field_validator("description", "population", "effect_measure")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s


class CohortRule(StrictModel):
    rule_id: str = Field(min_length=1)
    description: str = Field(min_length=8)

    @field_validator("rule_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_plan_identifier(v, "rule_id")

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 8:
            raise ValueError("description must contain at least 8 characters")
        return s


class ExclusionRule(StrictModel):
    rule_id: str = Field(min_length=1)
    description: str = Field(min_length=8)

    @field_validator("rule_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_plan_identifier(v, "rule_id")

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 8:
            raise ValueError("description must contain at least 8 characters")
        return s


class StoppingRule(StrictModel):
    description: str = Field(min_length=12)
    max_replicates: int | None = Field(default=None, ge=1)
    interim_looks: int = Field(default=0, ge=0)
    criteria: str | None = None

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 12:
            raise ValueError("stopping rule description must contain at least 12 characters")
        return s

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class DecisionRule(StrictModel):
    rule_type: str = Field(min_length=4)
    alpha: float | None = None
    threshold: float | None = None
    interpretation: str = Field(min_length=12)
    comparison: Literal["two_sided", "one_sided_greater", "one_sided_less", "equivalence"] = (
        "two_sided"  # noqa: E501
    )

    @field_validator("rule_type", "interpretation")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    @field_validator("alpha")
    @classmethod
    def validate_alpha(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not (0 < v < 1):
            raise ValueError("alpha must be between 0 and 1 exclusive")
        if not (v == v and v not in (float("inf"), float("-inf"))):
            raise ValueError("alpha must be finite")
        return v

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("threshold must be finite")
        return v


class PlannedRunCell(StrictModel):
    cell_id: str = Field(min_length=1)
    arm_id: str = Field(min_length=1)
    seed_id: str | None = None
    policy_label: str = Field(min_length=1)
    replication_id: int = Field(ge=0)
    metric_key: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    replication_unit: ReplicationUnit = ReplicationUnit.RANDOM_SEED

    @field_validator("cell_id", "arm_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_plan_identifier(v, "cell_id/arm_id")

    @field_validator("seed_id")
    @classmethod
    def validate_seed(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_plan_identifier(v, "seed_id")

    @field_validator("policy_label", "metric_key", "metric_version")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s


class StudyPlanRevision(StrictModel):
    version: int = Field(ge=1)
    parent_fingerprint: str | None = None
    parent_version: int | None = Field(default=None, ge=1)
    amendment_reason: str = Field(min_length=12)
    diff: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    is_post_evidence: bool = False
    amendment_label: AmendmentLabel = AmendmentLabel.PRE_EVIDENCE

    @field_validator("amendment_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 12:
            raise ValueError("amendment_reason must contain at least 12 characters")
        return s


class EvidenceAttachment(StrictModel):
    artifact_fingerprint: str = Field(min_length=16)
    cell_id: str = Field(min_length=1)
    artifact_type: str = Field(default="metric_collection")
    observed_metric_key: str = Field(min_length=1)
    observed_metric_version: str = Field(min_length=1)
    observed_unit: str = Field(min_length=1)
    is_admitted: bool = False
    admission_label: ArtifactAdmission = ArtifactAdmission.UNADMITTED
    incompatibility_reason: str | None = None
    attached_at: datetime | None = None

    @field_validator("artifact_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 16:
            raise ValueError("artifact_fingerprint must contain at least 16 characters")
        if not re.fullmatch(r"[0-9a-fA-F]+", s):
            raise ValueError("artifact_fingerprint must be hex")
        return s.lower()

    @field_validator("cell_id", "observed_metric_key", "observed_metric_version", "observed_unit")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    @field_validator("incompatibility_reason")
    @classmethod
    def validate_reason(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s or None


class DecisionGateReport(StrictModel):
    status: DecisionGateStatus
    reasons: list[str] = Field(default_factory=list)
    missing_cells: list[str] = Field(default_factory=list)
    extra_cells: list[str] = Field(default_factory=list)
    incompatible_cells: list[str] = Field(default_factory=list)
    incompatibility_reasons: dict[str, str] = Field(default_factory=dict)
    is_ready: bool = False
    is_blocked: bool = False
    is_unavailable: bool = False

    @model_validator(mode="after")
    def validate_flags(self) -> DecisionGateReport:
        if self.status == DecisionGateStatus.READY:
            if not (
                self.is_ready is True and self.is_blocked is False and self.is_unavailable is False
            ):  # noqa: E501
                raise ValueError(
                    "READY status requires is_ready=True and is_blocked/is_unavailable=False"
                )  # noqa: E501
            if self.missing_cells or self.extra_cells or self.incompatible_cells:
                raise ValueError("READY status cannot have missing/extra/incompatible cells")
        elif self.status in (DecisionGateStatus.BLOCKED, DecisionGateStatus.UNAVAILABLE):
            if self.is_ready is True:
                raise ValueError(f"{self.status.value} status cannot have is_ready=True")
            if self.status == DecisionGateStatus.BLOCKED and self.is_blocked is not True:
                raise ValueError("BLOCKED status requires is_blocked=True")
            if self.status == DecisionGateStatus.UNAVAILABLE and self.is_unavailable is not True:
                raise ValueError("UNAVAILABLE status requires is_unavailable=True")
        return self


# ---------------------------------------------------------------------------
# StudyPlan
# ---------------------------------------------------------------------------

STUDY_PLAN_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class StudyPlan(StrictModel):
    schema_version: Literal["1.0"] = STUDY_PLAN_SCHEMA_VERSION
    plan_id: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    status: StudyPlanStatus = StudyPlanStatus.DRAFT
    study_question: StudyQuestion
    evidence_mode: EvidenceMode
    primary_outcomes: list[OutcomeDefinition] = Field(default_factory=list)
    secondary_outcomes: list[OutcomeDefinition] = Field(default_factory=list)
    estimand: EstimandDefinition | None = None
    replication_unit: ReplicationUnit
    replication_ids: list[int] = Field(default_factory=list)
    replication_generation_rule: str | None = None
    planned_arms: list[str] = Field(default_factory=list)
    seeds: list[str] = Field(default_factory=list)
    policies: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    cohort_rules: list[CohortRule] = Field(default_factory=list)
    exclusion_rules: list[ExclusionRule] = Field(default_factory=list)
    missingness_policy: MissingnessPolicy
    analysis_method: AnalysisMethod
    multiplicity_policy: MultiplicityPolicy
    stopping_rule: StoppingRule
    decision_rule: DecisionRule
    limitations: str = Field(min_length=12)
    planned_run_cells: list[PlannedRunCell] = Field(default_factory=list)
    power_plan_fingerprint: str | None = None
    power_plan_reference: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    frozen_at: datetime | None = None
    evidence_attached_at: datetime | None = None
    parent_fingerprint: str | None = None
    parent_version: int | None = None
    revision_history: list[StudyPlanRevision] = Field(default_factory=list)
    evidence_attachments: list[EvidenceAttachment] = Field(default_factory=list)
    gate_report: DecisionGateReport | None = None
    fingerprint: str | None = None
    evidence_state_fingerprint: str | None = None

    @field_validator("plan_id")
    @classmethod
    def validate_plan_id(cls, v: str) -> str:
        return _validate_plan_identifier(v, "plan_id")

    @field_validator("planned_arms")
    @classmethod
    def validate_arms(cls, v: list[str]) -> list[str]:
        for arm in v:
            _validate_plan_identifier(arm, "planned_arms item")
            if not arm.strip():
                raise ValueError("arm must contain non-space characters")
        if len(set(v)) != len(v):
            raise ValueError("planned_arms must not contain duplicates")
        return v

    @field_validator("replication_ids")
    @classmethod
    def validate_replication_ids(cls, v: list[int]) -> list[int]:
        if any(x < 0 for x in v):
            raise ValueError("replication_ids must be non-negative")
        if len(set(v)) != len(v):
            raise ValueError("replication_ids must not contain duplicates")
        return sorted(v)

    @field_validator(
        "replication_generation_rule", "power_plan_reference", "power_plan_fingerprint"
    )  # noqa: E501
    @classmethod
    def validate_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters when provided")
        return s

    @field_validator("seeds", "policies", "metrics")
    @classmethod
    def validate_string_lists(cls, v: list[str]) -> list[str]:
        for item in v:
            if not item.strip():
                raise ValueError("list items must contain non-space characters")
        if len(set(v)) != len(v):
            raise ValueError("seeds/policies/metrics must not contain duplicates")
        return v

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 12:
            raise ValueError("limitations must contain at least 12 characters")
        return s

    @model_validator(mode="after")
    def validate_secondary_unique(self) -> StudyPlan:
        primary_ids = {o.outcome_id for o in self.primary_outcomes}
        secondary_ids = {o.outcome_id for o in self.secondary_outcomes}
        if primary_ids & secondary_ids:
            raise ValueError("primary and secondary outcome_ids must not overlap")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Return deterministic payload for fingerprinting, excluding wall-clock and volatile fields."""  # noqa: E501
        data = self.model_dump(mode="json", by_alias=True)
        for key in ("created_at", "frozen_at", "evidence_attached_at"):
            if key in data:
                data[key] = "<normalised>"
        if "revision_history" in data:
            for rev in data["revision_history"]:
                rev["created_at"] = "<normalised>"
        # Fingerprints are identities; frozen fingerprint must not bind post-freeze evidence or status  # noqa: E501
        data.pop("status", None)
        data.pop("fingerprint", None)
        data.pop("evidence_state_fingerprint", None)
        data.pop("gate_report", None)
        data.pop("evidence_attachments", None)
        data.pop("evidence_attached_at", None)
        return data

    def compute_fingerprint(self) -> str:
        payload = self.canonical_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def compute_evidence_state_fingerprint(self) -> str:
        """Deterministic identity for the evidence-attached state, separate from frozen plan."""
        payload = {
            "fingerprint": self.fingerprint,
            "evidence_attachments": [
                a.model_dump(mode="json")
                for a in sorted(self.evidence_attachments, key=lambda x: x.cell_id)
            ],  # noqa: E501
        }
        # Normalise attached_at
        for item in payload["evidence_attachments"]:  # type: ignore[union-attr]
            if item.get("attached_at") is not None:  # type: ignore[union-attr]
                item["attached_at"] = "<normalised>"  # type: ignore[index]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def fingerprint_or_compute(self) -> str:
        if self.fingerprint is not None:
            return self.fingerprint
        return self.compute_fingerprint()


def field_level_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return deterministic field-level diff between two canonical payloads."""
    diff: dict[str, dict[str, Any]] = {}
    all_keys = sorted(set(old.keys()) | set(new.keys()))
    for key in all_keys:
        old_val = old.get(key)
        new_val = new.get(key)
        old_canonical = (
            json.dumps(old_val, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            if old_val is not None
            else None
        )  # noqa: E501
        new_canonical = (
            json.dumps(new_val, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            if new_val is not None
            else None
        )  # noqa: E501
        if old_canonical != new_canonical:
            diff[key] = {"old": old_val, "new": new_val}
    return diff


def has_evidence_in_lineage(plan: StudyPlan) -> bool:
    """Monotonic taint: True if any ancestor or current plan has ever seen evidence."""
    if plan.evidence_attached_at is not None:
        return True
    if plan.status in (
        StudyPlanStatus.EVIDENCE_ATTACHED,
        StudyPlanStatus.DECIDED,
        StudyPlanStatus.CLOSED,
    ):  # noqa: E501
        return True
    if plan.evidence_attachments:
        return True
    for rev in plan.revision_history:
        if rev.is_post_evidence or rev.amendment_label == AmendmentLabel.POST_EVIDENCE:
            return True
    return False
