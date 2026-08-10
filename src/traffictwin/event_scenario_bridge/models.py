"""Typed models for the deterministic Event-to-Scenario Bridge."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_METRICS = 16
_MAX_WINDOWS = 8
_MAX_LINKS = 64
_MAX_DESCRIPTION_LEN = 500


def _validate_identifier(value: str, field_name: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        msg = (
            f"{field_name} must start with an alphanumeric character and contain only "
            "letters, numbers, dots, underscores, colons, or hyphens"
        )
        raise ValueError(msg)
    return value


class StrictModel(BaseModel):
    """Strict base: rejects unknown fields and validates on assignment."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class BridgeStatus(StrEnum):
    """Discriminated bridge outcome."""

    OK = "ok"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"


class EvidenceStanding(StrEnum):
    """Evidence standing for the bridge — always authored / non-admitted."""

    AUTHORED_CONFIGURATION = "authored_configuration"
    SYNTHETIC_EVALUATION = "synthetic_evaluation"
    IMPORTED_EVIDENCE = "imported_evidence"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class DeclaredEventReference(StrictModel):
    """Declared event identity — authored, not observed."""

    event_id: str = Field(min_length=1, max_length=128)
    event_kind: str = Field(min_length=1, max_length=64, description="Authored event kind label")
    anchor_time_utc: datetime
    source_label: str = Field(min_length=1, max_length=200)
    provenance_detail: str | None = Field(default=None, max_length=_MAX_DESCRIPTION_LEN)
    artifact_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    bundle_id: str | None = None
    incident_id: str | None = None

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        return _validate_identifier(value, "event_id")

    @field_validator("anchor_time_utc")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "anchor_time_utc must be timezone-aware; naive timestamps are rejected"
            raise ValueError(msg)
        return value.astimezone(UTC)

    @field_validator("source_label")
    @classmethod
    def validate_source_label(cls, value: str) -> str:
        lowered = value.lower()
        if "observed" in lowered:
            msg = "authored event references must not be labelled observed"
            raise ValueError(msg)
        return value

    @field_validator("event_kind")
    @classmethod
    def validate_event_kind(cls, value: str) -> str:
        lowered = value.lower()
        if "observed" in lowered:
            msg = "authored event kind must not be labelled observed"
            raise ValueError(msg)
        stripped = value.strip()
        if not stripped:
            raise ValueError("event_kind must contain non-space characters")
        return stripped

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "anchor_time_utc": self.anchor_time_utc.isoformat().replace("+00:00", "Z"),
            "artifact_fingerprint": self.artifact_fingerprint,
            "bundle_id": self.bundle_id,
            "event_id": self.event_id,
            "event_kind": self.event_kind,
            "incident_id": self.incident_id,
            "provenance_detail": self.provenance_detail,
            "source_label": self.source_label,
        }


class EventImpactEnvelope(StrictModel):
    """Affected area and window specification — half-open semantics [start,end)."""

    affected_links: list[str] = Field(default_factory=list, max_length=_MAX_LINKS)
    affected_area_label: str | None = Field(default=None, max_length=200)
    pre_duration_s: float = Field(gt=0, le=1_000_000)
    event_duration_s: float = Field(gt=0, le=1_000_000)
    post_duration_s: float = Field(gt=0, le=1_000_000)
    bin_width_s: float = Field(gt=0, le=1_000_000)
    window_start_offset_s: float | None = Field(default=None)
    window_end_offset_s: float | None = Field(default=None)
    bin_boundary: Literal["[start,end)"] = "[start,end)"

    @field_validator("affected_links")
    @classmethod
    def validate_links(cls, value: list[str]) -> list[str]:
        for link in value:
            _validate_identifier(link, "affected_links item")
        if len(set(value)) != len(value):
            raise ValueError("affected_links must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_window_consistency(self) -> EventImpactEnvelope:
        if (
            self.window_start_offset_s is not None
            and self.window_end_offset_s is not None
            and self.window_end_offset_s <= self.window_start_offset_s
        ):
            msg = "window_end_offset_s must be greater than window_start_offset_s"
            raise ValueError(msg)
        # bin_width must divide windows sensibly — total bins bounded
        total = self.pre_duration_s + self.event_duration_s + self.post_duration_s
        import math

        bins = math.ceil(total / self.bin_width_s)
        if bins > 10_000:
            msg = f"total bins {bins} exceeds 10,000 — reduce durations or increase bin_width_s"
            raise ValueError(msg)
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "affected_area_label": self.affected_area_label,
            "affected_links": sorted(self.affected_links),
            "bin_boundary": self.bin_boundary,
            "bin_width_s": self.bin_width_s,
            "event_duration_s": self.event_duration_s,
            "post_duration_s": self.post_duration_s,
            "pre_duration_s": self.pre_duration_s,
            "window_end_offset_s": self.window_end_offset_s,
            "window_start_offset_s": self.window_start_offset_s,
        }

    def preview_windows(self, anchor_utc: datetime) -> dict[str, tuple[datetime, datetime]]:
        """Return half-open windows anchored to the event time."""
        from datetime import timedelta

        if anchor_utc.tzinfo is None:
            msg = "anchor_utc must be timezone-aware"
            raise ValueError(msg)
        anchor = anchor_utc.astimezone(UTC)
        pre_start = anchor - timedelta(seconds=self.pre_duration_s)
        pre_end = anchor
        event_start = anchor
        event_end = anchor + timedelta(seconds=self.event_duration_s)
        post_start = event_end
        post_end = post_start + timedelta(seconds=self.post_duration_s)
        return {
            "pre": (pre_start, pre_end),
            "event": (event_start, event_end),
            "post": (post_start, post_end),
        }


class MutationKind(StrEnum):
    """Closed mutation kinds supported by the bridge (subset of EXP-02 closed types)."""

    BOUNDED_DEMAND_CHANGE = "bounded_demand_change"
    LANE_CLOSURE = "lane_closure"
    ROAD_CLEARING = "road_clearing"
    RSU_REMOVAL = "rsu_removal"
    TIMESTAMP_EVENT_WINDOW_ADJUSTMENT = "timestamp_event_window_adjustment"


_SUPPORTED_MUTATION_KINDS = tuple(MutationKind)


class ScenarioMutationProposal(StrictModel):
    """One proposed mutation — restricted to existing closed mutation types."""

    mutation_kind: MutationKind
    target_description: str = Field(min_length=1, max_length=_MAX_DESCRIPTION_LEN)
    demand_multiplier: float | None = Field(default=None, gt=0, le=100)
    lanes_closed: int | None = Field(default=None, ge=0, le=16)
    rsu_id: str | None = None
    timestamp_jitter_s: float | None = Field(default=None, gt=0, le=3600)
    random_seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    table_kind: str | None = None

    @field_validator("rsu_id")
    @classmethod
    def validate_rsu_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, "rsu_id")

    @model_validator(mode="after")
    def validate_kind_constraints(self) -> ScenarioMutationProposal:
        kind = self.mutation_kind
        if kind == MutationKind.BOUNDED_DEMAND_CHANGE:
            if self.demand_multiplier is None:
                raise ValueError("bounded_demand_change requires demand_multiplier")
            if self.rsu_id is not None:
                raise ValueError("bounded_demand_change must not set rsu_id")
        elif kind == MutationKind.LANE_CLOSURE:
            if self.lanes_closed is None:
                raise ValueError("lane_closure requires lanes_closed")
            if self.rsu_id is not None:
                raise ValueError("lane_closure must not set rsu_id")
        elif kind == MutationKind.ROAD_CLEARING:
            if self.lanes_closed is not None and self.lanes_closed != 0:
                raise ValueError("road_clearing must have lanes_closed unset or 0")
            if self.rsu_id is not None:
                raise ValueError("road_clearing must not set rsu_id")
        elif kind == MutationKind.RSU_REMOVAL:
            if self.rsu_id is None:
                raise ValueError("rsu_removal requires rsu_id")
            if self.demand_multiplier is not None:
                raise ValueError("rsu_removal must not set demand_multiplier")
            if self.lanes_closed is not None:
                raise ValueError("rsu_removal must not set lanes_closed")
        elif kind == MutationKind.TIMESTAMP_EVENT_WINDOW_ADJUSTMENT:
            if self.timestamp_jitter_s is None:
                raise ValueError("timestamp_event_window_adjustment requires timestamp_jitter_s")
            if self.rsu_id is not None:
                raise ValueError("timestamp_event_window_adjustment must not set rsu_id")
        if self.demand_multiplier is not None and not (0.01 <= self.demand_multiplier <= 100.0):
            raise ValueError("demand_multiplier must be in [0.01, 100]")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "demand_multiplier": self.demand_multiplier,
            "lanes_closed": self.lanes_closed,
            "mutation_kind": self.mutation_kind.value,
            "random_seed": self.random_seed,
            "rsu_id": self.rsu_id,
            "table_kind": self.table_kind,
            "target_description": self.target_description,
            "timestamp_jitter_s": self.timestamp_jitter_s,
        }


class EventScenarioBridgeRequest(StrictModel):
    """Complete authored bridge request — bounded and validated."""

    bridge_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    event_reference: DeclaredEventReference
    baseline_seed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_seed_id: str = Field(min_length=1, max_length=128)
    impact_envelope: EventImpactEnvelope
    mutation_proposals: list[ScenarioMutationProposal] = Field(
        min_length=1, max_length=8, description="At least one ordered mutation"
    )
    intended_metrics: list[str] = Field(min_length=1, max_length=_MAX_METRICS)
    intended_windows: list[str] = Field(default_factory=list, max_length=_MAX_WINDOWS)
    evidence_standing: EvidenceStanding = EvidenceStanding.AUTHORED_CONFIGURATION

    @field_validator("bridge_id")
    @classmethod
    def validate_bridge_id(cls, value: str) -> str:
        return _validate_identifier(value, "bridge_id")

    @field_validator("baseline_seed_id")
    @classmethod
    def validate_seed_id(cls, value: str) -> str:
        return _validate_identifier(value, "baseline_seed_id")

    @field_validator("intended_metrics")
    @classmethod
    def validate_metrics(cls, value: list[str]) -> list[str]:
        for item in value:
            stripped = item.strip()
            if not stripped:
                raise ValueError("intended_metrics items must contain non-space characters")
        if len(set(value)) != len(value):
            raise ValueError("intended_metrics must not contain duplicates")
        return value

    @field_validator("intended_windows")
    @classmethod
    def validate_windows(cls, value: list[str]) -> list[str]:
        for item in value:
            stripped = item.strip()
            if not stripped:
                raise ValueError("intended_windows items must contain non-space characters")
        if len(set(value)) != len(value):
            raise ValueError("intended_windows must not contain duplicates")
        return value

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "baseline_seed_fingerprint": self.baseline_seed_fingerprint,
            "baseline_seed_id": self.baseline_seed_id,
            "bridge_id": self.bridge_id,
            "description": self.description,
            "event_reference": self.event_reference.canonical_dict(),
            "evidence_standing": self.evidence_standing.value,
            "impact_envelope": self.impact_envelope.canonical_dict(),
            "intended_metrics": sorted(self.intended_metrics),
            "intended_windows": sorted(self.intended_windows),
            "mutation_proposals": [p.canonical_dict() for p in self.mutation_proposals],
            "title": self.title,
        }


# ---------------------------------------------------------------------------
# Handoffs — deterministic, unexecuted
# ---------------------------------------------------------------------------


class BridgeFinding(StrictModel):
    """One descriptive finding — never claims causality."""

    finding_id: str = Field(min_length=1)
    description: str = Field(min_length=8, max_length=1_000)
    severity: Literal["info", "warning", "limitation"] = "info"

    @field_validator("finding_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_identifier(value, "finding_id")

    @field_validator("description")
    @classmethod
    def validate_non_causal(cls, value: str) -> str:
        lowered = value.lower()
        # Forbid active causal claims like "caused", "proves", "proven" without negation.
        # Allow explanatory negations like "does not establish causal attribution"
        # which is a limitation disclosure, not a causal claim.
        forbidden_active = ["caused", "proves", "proven"]
        for term in forbidden_active:
            if term in lowered:
                msg = f"bridge findings must not claim causality: found {term!r}"
                raise ValueError(msg)
        # For "causal", forbid unless preceded by negation within the same sentence
        if "causal" in lowered:
            # Allow if the description contains a negation of causality
            negation_markers = [
                "not causal",
                "non-causal",
                "not claim causal",
                "no causal",
                "without causal",
                "does not establish causal",
            ]
            if not any(marker in lowered for marker in negation_markers):
                msg = "bridge findings must not claim causality: found 'causal'"
                raise ValueError(msg)
        stripped = value.strip()
        if len(stripped) < 8:
            raise ValueError("description must contain at least 8 characters")
        return stripped

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "finding_id": self.finding_id,
            "severity": self.severity,
        }


class ScenarioSeedHandoff(StrictModel):
    """Handoff 1: scenario seed / mutation specification — unexecuted."""

    handoff_id: str
    handoff_kind: Literal["scenario_seed_mutation"] = "scenario_seed_mutation"
    baseline_seed_id: str
    baseline_seed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    bridge_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_seed_id: str
    mutation_proposals: list[ScenarioMutationProposal]
    execution_status: Literal["not_executed"] = "not_executed"
    evidence_created: Literal[False] = False
    admission_created: Literal[False] = False
    limitations: list[str]

    @field_validator("handoff_id", "derived_seed_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return _validate_identifier(value, "handoff identifier")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "admission_created": self.admission_created,
            "baseline_seed_fingerprint": self.baseline_seed_fingerprint,
            "baseline_seed_id": self.baseline_seed_id,
            "derived_seed_id": self.derived_seed_id,
            "event_fingerprint": self.event_fingerprint,
            "evidence_created": self.evidence_created,
            "execution_status": self.execution_status,
            "handoff_id": self.handoff_id,
            "handoff_kind": self.handoff_kind,
            "limitations": sorted(self.limitations),
            "mutation_proposals": [p.canonical_dict() for p in self.mutation_proposals],
        }


class EventAlignedHandoff(StrictModel):
    """Handoff 2: Event-Aligned analysis specification — unexecuted."""

    handoff_id: str
    handoff_kind: Literal["event_aligned_spec"] = "event_aligned_spec"
    event_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    bridge_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_seed_id: str
    baseline_seed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    anchor_time_utc: str = Field(description="ISO8601 UTC anchor time")
    impact_envelope: EventImpactEnvelope
    intended_metrics: list[str]
    bin_boundary: Literal["[start,end)"] = "[start,end)"
    execution_status: Literal["not_executed"] = "not_executed"
    evidence_created: Literal[False] = False
    admission_created: Literal[False] = False
    limitations: list[str]

    @field_validator("handoff_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_identifier(value, "handoff identifier")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "admission_created": self.admission_created,
            "anchor_time_utc": self.anchor_time_utc,
            "baseline_seed_fingerprint": self.baseline_seed_fingerprint,
            "baseline_seed_id": self.baseline_seed_id,
            "bin_boundary": self.bin_boundary,
            "event_fingerprint": self.event_fingerprint,
            "evidence_created": self.evidence_created,
            "execution_status": self.execution_status,
            "handoff_id": self.handoff_id,
            "handoff_kind": self.handoff_kind,
            "impact_envelope": self.impact_envelope.canonical_dict(),
            "intended_metrics": sorted(self.intended_metrics),
            "limitations": sorted(self.limitations),
        }


class PreregistrationDraftHandoff(StrictModel):
    """Handoff 3: preregistration draft — unexecuted, unadmitted."""

    handoff_id: str
    handoff_kind: Literal["preregistration_draft"] = "preregistration_draft"
    event_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    bridge_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_seed_id: str
    baseline_seed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    study_question: str = Field(min_length=12, max_length=1_000)
    planned_metrics: list[str]
    planned_windows: list[str]
    planned_mutations: list[ScenarioMutationProposal]
    evidence_standing: EvidenceStanding
    execution_status: Literal["not_executed"] = "not_executed"
    evidence_created: Literal[False] = False
    admission_created: Literal[False] = False
    limitations: list[str]

    @field_validator("handoff_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_identifier(value, "handoff identifier")

    @field_validator("study_question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 12:
            raise ValueError("study_question must contain at least 12 characters")
        lowered = stripped.lower()
        for term in ("caused", "causal", "proves", "proven"):
            if term in lowered:
                msg = f"study_question must not claim causality: found {term!r}"
                raise ValueError(msg)
        return stripped

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "admission_created": self.admission_created,
            "baseline_seed_fingerprint": self.baseline_seed_fingerprint,
            "baseline_seed_id": self.baseline_seed_id,
            "event_fingerprint": self.event_fingerprint,
            "evidence_created": self.evidence_created,
            "evidence_standing": self.evidence_standing.value,
            "execution_status": self.execution_status,
            "handoff_id": self.handoff_id,
            "handoff_kind": self.handoff_kind,
            "limitations": sorted(self.limitations),
            "planned_metrics": sorted(self.planned_metrics),
            "planned_mutations": [p.canonical_dict() for p in self.planned_mutations],
            "planned_windows": sorted(self.planned_windows),
            "study_question": self.study_question,
        }


class ExperimentPlanHandoff(StrictModel):
    """Handoff 4: experiment plan — unexecuted, no run allocation."""

    handoff_id: str
    handoff_kind: Literal["experiment_plan"] = "experiment_plan"
    event_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    bridge_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_seed_id: str
    baseline_seed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_seed_id: str
    planned_metrics: list[str]
    planned_cells: list[dict[str, Any]] = Field(default_factory=list)
    execution_status: Literal["not_executed"] = "not_executed"
    evidence_created: Literal[False] = False
    admission_created: Literal[False] = False
    limitations: list[str]

    @field_validator("handoff_id", "derived_seed_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        return _validate_identifier(value, "handoff identifier")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "admission_created": self.admission_created,
            "baseline_seed_fingerprint": self.baseline_seed_fingerprint,
            "baseline_seed_id": self.baseline_seed_id,
            "derived_seed_id": self.derived_seed_id,
            "event_fingerprint": self.event_fingerprint,
            "evidence_created": self.evidence_created,
            "execution_status": self.execution_status,
            "handoff_id": self.handoff_id,
            "handoff_kind": self.handoff_kind,
            "limitations": sorted(self.limitations),
            "planned_cells": sorted(
                self.planned_cells,
                key=lambda x: str(x.get("cell_id", "")),
            ),
            "planned_metrics": sorted(self.planned_metrics),
        }


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class EventScenarioBridgeManifest(StrictModel):
    """Portable deterministic bundle binding one event to four unexecuted handoffs."""

    schema_version: Literal["1.0"] = "1.0"
    manifest_id: str
    bridge_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_seed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_seed_id: str
    request: EventScenarioBridgeRequest
    scenario_seed_handoff: ScenarioSeedHandoff
    event_aligned_handoff: EventAlignedHandoff
    preregistration_draft_handoff: PreregistrationDraftHandoff
    experiment_plan_handoff: ExperimentPlanHandoff
    findings: list[BridgeFinding] = Field(default_factory=list)
    status: BridgeStatus = BridgeStatus.OK
    execution_status: Literal["not_executed"] = "not_executed"
    evidence_created: Literal[False] = False
    admission_created: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str]
    created_at_utc: datetime | None = None

    @field_validator("manifest_id")
    @classmethod
    def validate_manifest_id(cls, value: str) -> str:
        return _validate_identifier(value, "manifest_id")

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            msg = "created_at_utc must be timezone-aware when present"
            raise ValueError(msg)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_fingerprints_consistent(self) -> EventScenarioBridgeManifest:
        # Every handoff must bind same event and baseline fingerprints
        for handoff in (
            self.scenario_seed_handoff,
            self.event_aligned_handoff,
            self.preregistration_draft_handoff,
            self.experiment_plan_handoff,
        ):
            if handoff.event_fingerprint != self.event_fingerprint:
                msg = "all handoffs must bind the same event_fingerprint as manifest"
                raise ValueError(msg)
            if handoff.baseline_seed_fingerprint != self.baseline_seed_fingerprint:
                msg = "all handoffs must bind the same baseline_seed_fingerprint as manifest"
                raise ValueError(msg)
            if handoff.bridge_fingerprint != self.bridge_fingerprint:
                msg = "all handoffs must bind the same bridge_fingerprint as manifest"
                raise ValueError(msg)
        if self.request.baseline_seed_fingerprint != self.baseline_seed_fingerprint:
            msg = "request baseline_seed_fingerprint must match manifest"
            raise ValueError(msg)
        return self

    def canonical_dict(self) -> dict[str, Any]:
        """Return canonical dict excluding volatile fingerprints and clock."""

        return {
            "admission_created": self.admission_created,
            "baseline_seed_fingerprint": self.baseline_seed_fingerprint,
            "baseline_seed_id": self.baseline_seed_id,
            "event_aligned_handoff": self.event_aligned_handoff.canonical_dict(),
            "event_fingerprint": self.event_fingerprint,
            "evidence_created": self.evidence_created,
            "execution_status": self.execution_status,
            "experiment_plan_handoff": self.experiment_plan_handoff.canonical_dict(),
            "findings": sorted(
                [f.canonical_dict() for f in self.findings],
                key=lambda x: str(x.get("finding_id")),
            ),
            "limitations": sorted(self.limitations),
            "manifest_id": self.manifest_id,
            "preregistration_draft_handoff": self.preregistration_draft_handoff.canonical_dict(),
            "request": self.request.canonical_dict(),
            "scenario_seed_handoff": self.scenario_seed_handoff.canonical_dict(),
            "schema_version": self.schema_version,
            "status": self.status.value,
            "warnings": sorted(self.warnings),
        }

    def canonical_json(self) -> str:
        payload = self.canonical_dict()
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )

    def computed_fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def verify_fingerprint(self) -> bool:
        return self.bridge_fingerprint == self.computed_fingerprint()

    def to_portable_dict(self) -> dict[str, Any]:
        data = self.canonical_dict()
        data["bridge_fingerprint"] = self.bridge_fingerprint
        data["event_fingerprint"] = self.event_fingerprint
        if self.created_at_utc is not None:
            data["created_at_utc"] = self.created_at_utc.isoformat().replace("+00:00", "Z")
        return data
