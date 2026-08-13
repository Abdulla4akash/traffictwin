"""Deterministic status projection over v1.1 matching and analyst review.

Wraps :mod:`observation_matching_v11` and :mod:`observation_review` without
reimplementing matching.  Terminal standings are truthful:

* ``AUTO_ACCEPTED`` – owner policy says ``owner_policy_accepted_candidate`` with
  ``clear_candidate`` confidence and a recorded ``acceptance_path``.
* ``HUMAN_ACCEPTED`` – sealed live ``accept_group`` decision by a named reviewer
  for the exact queue entry and one of the observation's road groups.
* ``REJECTED`` – policy ``no_suitable_candidate`` / ``unavailable_missing_evidence``
  or a sealed ``reject_all_candidates`` decision.
* ``UNRESOLVED`` – ``awaiting_manual_review`` without an accepting live decision
  (including ``defer``).

No claim of observational truth, scientific validation, or baseline acceptance is
ever made.  Distance alone never accepts.  The module fails closed on duplicate
ids, tampered or unsealed ledgers, stale/superseded/mismatched decisions, leaked
secrets or private paths, and silently accepted ambiguity.  Ordering is
deterministic and the workflow fingerprint is canonical.

Source binding: every workflow is anchored to an admitted DfT historical
measured-count snapshot (``roadtraffic.dft.gov.uk``), never to BODS general road
traffic or any inferred provider truth.  The snapshot identity is explicit,
frozen, and provenance-bound; raw caller rows without exact accepted snapshot
provenance are refused.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, TypeAlias

from pydantic import (
    AliasChoices,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.observation_matching_v11 import (
    MAP_MATCH_POLICY_V11_ID,
    ManualReviewQueue,
    ObservationMatchV11,
    RoadGroupV11,
    TerminalDispositionV11,
)
from traffictwin.integration.manchester.observation_review import (
    MatchReviewDecision,
    MatchReviewLedger,
    ReviewDecisionKind,
)

MAP_MATCH_WORKFLOW_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAP_MATCH_WORKFLOW_METHOD_VERSION: Literal["manchester-map-match-workflow-1.0"] = (
    "manchester-map-match-workflow-1.0"
)
MAP_MATCH_WORKFLOW_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

MapMatchStanding: TypeAlias = Literal["AUTO_ACCEPTED", "HUMAN_ACCEPTED", "REJECTED", "UNRESOLVED"]

_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_RE = re.compile(
    r"(password|secret|api[_-]?key|token|credential|private[_-]?key|bearer)", re.IGNORECASE
)
_SNAPSHOT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

MAX_OBSERVATIONS = 1024
MAX_DIAGNOSTICS = 64
MAX_DIAGNOSTIC_LEN = 2000
MAX_REASON_LEN = 3000
MAX_SHORT_REASON = 1000
MAX_MATCHED_EDGES = 64


def _reject_private_paths(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    return value


def _reject_secrets(value: str, label: str) -> str:
    if _SECRET_RE.search(value):
        raise ValueError(f"{label} must not contain a likely secret")
    return value


def _parse_utc_datetime(value: str) -> datetime:
    raw = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:  # noqa: BLE001
        # Sanitized coded error – never echo raw input which may contain paths/secrets.
        raise MapMatchWorkflowError("INVALID_TIMESTAMP", "invalid UTC datetime") from None
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise MapMatchWorkflowError(
            "INVALID_TIMESTAMP", "datetime must be timezone-aware UTC"
        ) from None
    return dt.astimezone(UTC)


class MapMatchWorkflowError(ValueError):
    """Fail-closed refusal with a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class MapMatchWorkflowModel(ManchesterSnapshotModel):
    """Frozen base."""


def _sanitize_workflow_error(exc: Exception) -> str:
    """Return a safe message without leaking paths or secrets."""
    msg = str(exc)
    # Strip any potential private path or secret patterns from the message.
    # Use generic fallback if sensitive markers remain.
    if _PRIVATE_PATH_RE.search(msg) or _SECRET_RE.search(msg):
        return "invalid input"
    # Truncate and avoid leaking large dumps.
    return msg[:500]


class MapMatchDftSourceIdentity(MapMatchWorkflowModel):
    """Admitted DfT historical measured-count source provenance.

    This is the only accepted observation source for this workflow:
    Department for Transport Road Traffic Statistics
    (``roadtraffic.dft.gov.uk``) historical measured counts.  It is
    distinguished from BODS general road traffic and never implies
    provider truth.  All fingerprints are exact SHA-256 hex digests,
    the snapshot ID binds the content fingerprint, and portable
    provenance never carries private paths or secrets.  The admission
    receipt fingerprint is the exact 64-hex fingerprint of the accepted
    snapshot receipt and is required beyond ``is_accepted``.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        allow_inf_nan=False,
        revalidate_instances="always",
        populate_by_name=True,
    )

    source_family: Literal["dft"] = "dft"
    provider: Literal["roadtraffic.dft.gov.uk"] = "roadtraffic.dft.gov.uk"
    observation_role: Literal["historical_measured_count"] = "historical_measured_count"
    snapshot_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: str = Field(min_length=10, max_length=1000)
    admission_receipt_fingerprint: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        validation_alias=AliasChoices(
            "admission_receipt_fingerprint",
            "snapshot_receipt_fingerprint",
            "snapshot_receipt",
            "receipt_fingerprint",
            "admission_receipt",
        ),
    )
    is_accepted: Literal[True] = True
    is_source_blocked: Literal[False] = False

    @property
    def snapshot_receipt_fingerprint(self) -> str:
        """Alias for backward compatibility with snapshot_receipt naming."""
        return self.admission_receipt_fingerprint

    @property
    def receipt_fingerprint(self) -> str:
        """Alias for generic receipt fingerprint access."""
        return self.admission_receipt_fingerprint

    @field_validator(
        "snapshot_id", "content_fingerprint", "provenance", "admission_receipt_fingerprint"
    )
    @classmethod
    def _screen_source_text(cls, v: str) -> str:
        _reject_private_paths(v, "source")
        _reject_secrets(v, "source")
        return v

    @field_validator("provenance")
    @classmethod
    def _validate_provenance(cls, v: str) -> str:
        if "roadtraffic.dft.gov.uk" not in v:
            raise ValueError(
                "provenance must reference the admitted DfT host roadtraffic.dft.gov.uk"
            )
        lower = v.lower()
        if "bods" in lower:
            raise ValueError("provenance must not reference BODS")
        if "general_road_traffic" in lower or "general road traffic" in lower:
            raise ValueError("provenance must not inflate to BODS general road traffic")
        return v

    @model_validator(mode="after")
    def _validate_source_identity(self) -> MapMatchDftSourceIdentity:
        # Contradictory family/provider/role is already enforced by Literal,
        # but double-check for defence in depth against forged literals via
        # model_copy or direct construction bypass attempts.
        if self.source_family != "dft":
            raise ValueError("source_family must be dft for this workflow")
        if self.provider != "roadtraffic.dft.gov.uk":
            raise ValueError("provider must be roadtraffic.dft.gov.uk for DfT historical counts")
        if self.observation_role != "historical_measured_count":
            raise ValueError(
                "observation_role must be historical_measured_count, not BODS general traffic"
            )
        if self.is_source_blocked is not False:
            raise ValueError("source-blocked identities are rejected")
        if self.is_accepted is not True:
            raise ValueError("unaccepted source identities are rejected")
        # Snapshot ID must bind the content fingerprint prefix exactly as
        # build_snapshot_id does: tail 12 hex chars of the fingerprint.
        suffix = self.snapshot_id.rsplit("-", 1)[-1]
        expected_suffix = self.content_fingerprint[:12]
        if suffix != expected_suffix:
            raise ValueError("snapshot_id must end with the content fingerprint prefix")
        if not self.snapshot_id.startswith("dft_"):
            raise ValueError("snapshot_id must start with the admitted DfT source prefix dft_")
        # Fingerprint is already pattern-checked, but ensure lowercase hex.
        if self.content_fingerprint != self.content_fingerprint.lower():
            raise ValueError("content_fingerprint must be lowercase hex")
        if self.admission_receipt_fingerprint != self.admission_receipt_fingerprint.lower():
            raise ValueError("admission_receipt_fingerprint must be lowercase hex")
        if not _SHA256_RE.fullmatch(self.admission_receipt_fingerprint):
            raise ValueError("admission_receipt_fingerprint must be 64 lowercase hex")
        return self


# Backwards-compatible alias for callers that imported a generic name.
MapMatchObservationSourceIdentity = MapMatchDftSourceIdentity


class MapMatchObservationProjection(MapMatchWorkflowModel):
    """Per-observation deterministic projection."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        allow_inf_nan=False,
        revalidate_instances="always",
        populate_by_name=True,
    )

    schema_version: Literal["1.0"] = MAP_MATCH_WORKFLOW_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MAP_MATCH_WORKFLOW_CAPABILITY_ID
    method_version: Literal["manchester-map-match-workflow-1.0"] = MAP_MATCH_WORKFLOW_METHOD_VERSION
    observation: ObservationMatchV11
    queue_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    ledger_seal: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    standing: MapMatchStanding
    standing_reason: str = Field(min_length=10, max_length=MAX_REASON_LEN)
    diagnostics: tuple[str, ...] = Field(min_length=1, max_length=MAX_DIAGNOSTICS)
    ambiguity_reason: str | None = Field(default=None, max_length=MAX_SHORT_REASON)
    unmatched_reason: str | None = Field(default=None, max_length=MAX_SHORT_REASON)
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=200)
    reviewer_role: str | None = Field(default=None, min_length=1, max_length=200)
    decision_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    decided_at_utc: datetime | None = None
    decision_kind: ReviewDecisionKind | None = None
    accepted_group_key: str | None = Field(default=None, max_length=220)
    matched_edge_ids: tuple[str, ...] = Field(default=())
    nearest_distance_m: Decimal | None = Field(default=None, ge=0)
    original_disposition: TerminalDispositionV11
    scientifically_validated: Literal[False] = False
    observational_truth_claimed: Literal[False] = False
    baseline_acceptance_claimed: Literal[False] = False
    automatic_selection_performed: Literal[False] = False

    @field_validator("standing_reason", "ambiguity_reason", "unmatched_reason")
    @classmethod
    def _screen_reason(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _reject_private_paths(v, "reason")
        _reject_secrets(v, "reason")
        return v

    @field_validator("diagnostics")
    @classmethod
    def _screen_diagnostics(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for item in v:
            if len(item) > MAX_DIAGNOSTIC_LEN:
                raise ValueError("diagnostic item too long")
            _reject_private_paths(item, "diagnostic")
            _reject_secrets(item, "diagnostic")
        return v

    @field_validator("reviewer_name", "reviewer_role")
    @classmethod
    def _screen_reviewer(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _reject_private_paths(v, "reviewer")
        _reject_secrets(v, "reviewer")
        return v

    @field_validator("accepted_group_key")
    @classmethod
    def _screen_accepted_group(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _reject_private_paths(v, "accepted_group_key")
        _reject_secrets(v, "accepted_group_key")
        return v

    @field_validator("matched_edge_ids")
    @classmethod
    def _screen_matched_edges(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(v) > MAX_MATCHED_EDGES:
            raise ValueError("matched_edge_ids exceed bound")
        for eid in v:
            if not eid or len(eid) > 200:
                raise ValueError("matched edge_id length out of bounds")
            _reject_private_paths(eid, "matched_edge_ids")
            _reject_secrets(eid, "matched_edge_ids")
        if len(set(v)) != len(v):
            raise ValueError("matched_edge_ids must be unique")
        if tuple(sorted(v)) != v:
            raise ValueError("matched_edge_ids must be sorted deterministic")
        return v

    @field_validator("decided_at_utc")
    @classmethod
    def _validate_decided_at(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None or v.utcoffset() != timedelta(0):
            raise ValueError("decided_at_utc must be timezone-aware UTC")
        return v

    @model_validator(mode="after")
    def _validate_projection(self) -> MapMatchObservationProjection:
        obs = self.observation
        # Preserve original observation standing for auditability.
        if self.original_disposition != obs.disposition:
            raise ValueError("original_disposition must equal observation disposition")
        expected_nearest: Decimal | None = None
        if obs.groups:
            expected_nearest = min(g.nearest_distance_m for g in obs.groups)
        if self.nearest_distance_m != expected_nearest:
            raise ValueError("nearest_distance_m must equal minimal group distance")
        # Coherent diagnostics/ambiguity/unmatched derivation – no arbitrary rhetoric.
        expected_diagnostics = _diagnostics_for(obs)
        if self.diagnostics != expected_diagnostics:
            raise ValueError("diagnostics must equal derived diagnostics for observation")
        expected_ambiguity = _ambiguity_reason(obs)
        if self.ambiguity_reason != expected_ambiguity:
            raise ValueError("ambiguity_reason must equal derived ambiguity for observation")
        expected_unmatched = _unmatched_reason(obs)
        if self.unmatched_reason != expected_unmatched:
            raise ValueError("unmatched_reason must equal derived unmatched reason for observation")
        # Cross-field matched edge derivation and exact standing contracts.
        if self.standing == "AUTO_ACCEPTED":
            if obs.disposition != "owner_policy_accepted_candidate":
                raise ValueError("AUTO_ACCEPTED requires owner_policy_accepted_candidate")
            if obs.confidence != "clear_candidate":
                raise ValueError("AUTO_ACCEPTED requires clear_candidate")
            if obs.acceptance_path is None:
                raise ValueError("AUTO_ACCEPTED requires acceptance_path")
            # every human/ledger decision field must be absent
            if (
                self.decision_fingerprint is not None
                or self.reviewer_name is not None
                or self.reviewer_role is not None
                or self.decided_at_utc is not None
                or self.decision_kind is not None
                or self.ledger_seal is not None
            ):
                raise ValueError("AUTO_ACCEPTED must not carry any human/ledger decision field")
            if not obs.groups:
                raise ValueError("AUTO_ACCEPTED cannot have zero groups")
            if obs.review_reasons:
                raise ValueError("AUTO_ACCEPTED cannot carry review_reasons")
            # Deterministic derivation from policy record – never distance-ranked.
            try:
                derived = _auto_accepted_group(obs)
            except MapMatchWorkflowError as exc:
                raise ValueError(str(exc)) from exc
            if self.accepted_group_key != derived.group_key:
                raise ValueError(
                    "AUTO_ACCEPTED accepted_group_key must equal the derived "
                    "policy-accepted group key"
                )
            expected_ids = tuple(sorted({m.edge_id for m in derived.members}))
            if self.matched_edge_ids != expected_ids:
                raise ValueError(
                    "AUTO_ACCEPTED matched_edge_ids must equal derived group member edge IDs "
                    "sorted unique"
                )
            if self.ambiguity_reason is not None:
                raise ValueError("AUTO_ACCEPTED must have no ambiguity_reason")
            if self.unmatched_reason is not None:
                raise ValueError("AUTO_ACCEPTED must have no unmatched_reason")
            expected_reason = (
                "owner policy unambiguously accepted under clear thresholds; "
                "distance alone not sufficient"
            )
            if self.standing_reason != expected_reason:
                raise ValueError("AUTO_ACCEPTED standing_reason must be the canonical auto reason")
        elif self.standing == "HUMAN_ACCEPTED":
            if (
                self.decision_fingerprint is None
                or self.reviewer_name is None
                or self.reviewer_role is None
                or self.decided_at_utc is None
                or self.ledger_seal is None
            ):
                raise ValueError("HUMAN_ACCEPTED requires sealed named decision")
            if self.decision_kind != ReviewDecisionKind.ACCEPT_GROUP:
                raise ValueError("HUMAN_ACCEPTED requires accept_group")
            if self.accepted_group_key is None:
                raise ValueError("HUMAN_ACCEPTED requires accepted_group_key")
            if self.accepted_group_key not in {g.group_key for g in obs.groups}:
                raise ValueError("accepted_group_key must be among observation groups")
            if obs.disposition != "awaiting_manual_review":
                raise ValueError("HUMAN_ACCEPTED requires awaiting_manual_review observation")
            # Derive expected edge IDs from the accepted group.
            target = next(g for g in obs.groups if g.group_key == self.accepted_group_key)
            expected_human = tuple(sorted({m.edge_id for m in target.members}))
            if self.matched_edge_ids != expected_human:
                raise ValueError(
                    "HUMAN_ACCEPTED matched_edge_ids must equal accepted group member edge IDs "
                    "sorted unique"
                )
            # exact standing_reason contract
            expected_reason_h = (
                f"sealed named review accepted group {self.accepted_group_key} by "
                f"{self.reviewer_name}"
            )
            if self.standing_reason != expected_reason_h:
                raise ValueError(
                    "HUMAN_ACCEPTED standing_reason must name the accepted group and reviewer"
                )
            if self.unmatched_reason is not None:
                raise ValueError("HUMAN_ACCEPTED must have no unmatched_reason")
            # ambiguity coherent already checked via global equality
        elif self.standing == "REJECTED":
            if self.decision_kind == ReviewDecisionKind.ACCEPT_GROUP:
                raise ValueError("REJECTED cannot carry accept_group")
            if self.decision_kind == ReviewDecisionKind.DEFER:
                raise ValueError("REJECTED cannot carry defer")
            has_human = (
                self.decision_fingerprint is not None
                or self.reviewer_name is not None
                or self.reviewer_role is not None
                or self.decided_at_utc is not None
                or self.decision_kind is not None
                or self.ledger_seal is not None
            )
            if has_human:
                if self.decision_kind != ReviewDecisionKind.REJECT_ALL_CANDIDATES:
                    raise ValueError("REJECTED with human decision must be REJECT_ALL_CANDIDATES")
                if (
                    self.decision_fingerprint is None
                    or self.reviewer_name is None
                    or self.reviewer_role is None
                    or self.decided_at_utc is None
                    or self.ledger_seal is None
                ):
                    raise ValueError(
                        "human REJECTED requires sealed named reviewer with role/time/fingerprint"
                    )
                if obs.disposition not in (
                    "awaiting_manual_review",
                    "no_suitable_candidate",
                    "unavailable_missing_evidence",
                ):
                    raise ValueError(
                        "human REJECTED requires a queued disposition: awaiting_manual_review, "
                        "no_suitable_candidate or unavailable_missing_evidence"
                    )
                if self.original_disposition != obs.disposition:
                    raise ValueError("human REJECTED original_disposition must match observation")
                if self.accepted_group_key is not None:
                    raise ValueError("REJECTED must not carry accepted_group_key")
                if self.matched_edge_ids:
                    raise ValueError("REJECTED must not carry matched_edge_ids")
                expected_rej = (
                    f"sealed named review rejected all candidates by {self.reviewer_name}"
                )
                if self.standing_reason != expected_rej:
                    raise ValueError("human REJECTED standing_reason must name the reviewer")
            else:
                # policy-only rejection
                if obs.disposition not in ("no_suitable_candidate", "unavailable_missing_evidence"):
                    raise ValueError(
                        "REJECTED without human decision requires no_suitable_candidate or "
                        "unavailable_missing_evidence"
                    )
                # all human fields already absent via has_human check
                if self.accepted_group_key is not None:
                    raise ValueError("REJECTED must not carry accepted_group_key")
                if self.matched_edge_ids:
                    raise ValueError("REJECTED must not carry matched_edge_ids")
                if self.standing_reason != self.unmatched_reason:
                    raise ValueError("policy REJECTED standing_reason must equal unmatched_reason")
        elif self.standing == "UNRESOLVED":
            if self.decision_kind == ReviewDecisionKind.ACCEPT_GROUP:
                raise ValueError("UNRESOLVED cannot be accept_group")
            if self.decision_kind == ReviewDecisionKind.REJECT_ALL_CANDIDATES:
                raise ValueError("UNRESOLVED cannot be reject_all_candidates")
            if self.accepted_group_key is not None:
                raise ValueError("UNRESOLVED must not carry accepted_group_key")
            if self.matched_edge_ids:
                raise ValueError("UNRESOLVED must not carry matched_edge_ids")
            has_human_unres = (
                self.decision_fingerprint is not None
                or self.reviewer_name is not None
                or self.reviewer_role is not None
                or self.decided_at_utc is not None
                or self.decision_kind is not None
                or self.ledger_seal is not None
            )
            if has_human_unres:
                if self.decision_kind != ReviewDecisionKind.DEFER:
                    raise ValueError("UNRESOLVED with decision must be exactly DEFER")
                if (
                    self.decision_fingerprint is None
                    or self.reviewer_name is None
                    or self.reviewer_role is None
                    or self.decided_at_utc is None
                    or self.ledger_seal is None
                ):
                    raise ValueError(
                        "UNRESOLVED DEFER requires sealed named reviewer with role/time/fingerprint"
                    )
                if obs.disposition not in (
                    "awaiting_manual_review",
                    "no_suitable_candidate",
                    "unavailable_missing_evidence",
                ):
                    raise ValueError(
                        "UNRESOLVED DEFER requires a queued disposition: awaiting_manual_review, "
                        "no_suitable_candidate or unavailable_missing_evidence"
                    )
                expected_defer = (
                    f"sealed review deferred by {self.reviewer_name}; remains unresolved"
                )
                if self.standing_reason != expected_defer:
                    raise ValueError("UNRESOLVED DEFER standing_reason must name the reviewer")
            else:
                if obs.disposition != "awaiting_manual_review":
                    raise ValueError("UNRESOLVED without decision requires awaiting_manual_review")
                expected_unres = "awaiting manual review; no sealed decision; reproducible queue"
                if self.standing_reason != expected_unres:
                    raise ValueError(
                        "UNRESOLVED standing_reason must be the canonical unresolved reason"
                    )
                if self.decision_kind is not None:
                    raise ValueError("UNRESOLVED without decision must not carry decision_kind")
                if self.ledger_seal is not None:
                    raise ValueError("UNRESOLVED without decision must not carry ledger_seal")
        else:
            raise ValueError("unknown standing")
        return self


class MapMatchWorkflowResult(MapMatchWorkflowModel):
    """Coherent deterministic projection over all observations."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        allow_inf_nan=False,
        revalidate_instances="always",
        populate_by_name=True,
    )

    schema_version: Literal["1.0"] = MAP_MATCH_WORKFLOW_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MAP_MATCH_WORKFLOW_CAPABILITY_ID
    method_version: Literal["manchester-map-match-workflow-1.0"] = MAP_MATCH_WORKFLOW_METHOD_VERSION
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    queue_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    ledger_seal: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    ledger_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source: MapMatchDftSourceIdentity
    observations: tuple[MapMatchObservationProjection, ...] = Field(
        min_length=1, max_length=MAX_OBSERVATIONS
    )
    pending_queue: tuple[int, ...] = Field(default=())
    auto_accepted_ids: tuple[int, ...] = Field(default=())
    human_accepted_ids: tuple[int, ...] = Field(default=())
    rejected_ids: tuple[int, ...] = Field(default=())
    unresolved_ids: tuple[int, ...] = Field(default=())
    scientifically_validated: Literal[False] = False
    observational_truth_claimed: Literal[False] = False
    baseline_acceptance_claimed: Literal[False] = False

    @field_validator(
        "pending_queue", "auto_accepted_ids", "human_accepted_ids", "rejected_ids", "unresolved_ids"
    )
    @classmethod
    def _sorted_unique(cls, v: tuple[int, ...]) -> tuple[int, ...]:
        if len(v) > MAX_OBSERVATIONS:
            raise ValueError("queue ids exceed bound")
        if len(set(v)) != len(v):
            raise ValueError("queue ids must be unique")
        if tuple(sorted(v)) != v:
            raise ValueError("queue ids must be sorted deterministic")
        return v

    @model_validator(mode="after")
    def _validate_workflow(self) -> MapMatchWorkflowResult:
        ids = [o.observation.count_point_id for o in self.observations]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate observation count_point_id")
        if tuple(sorted(ids)) != tuple(ids):
            raise ValueError("observations must be sorted by count_point_id")

        # standing sets must match projections
        def _ids_for(standing: MapMatchStanding) -> tuple[int, ...]:
            return tuple(
                sorted(
                    o.observation.count_point_id
                    for o in self.observations
                    if o.standing == standing
                )
            )

        if self.pending_queue != _ids_for("UNRESOLVED"):
            raise ValueError("pending_queue must be exactly UNRESOLVED ids sorted")
        if self.auto_accepted_ids != _ids_for("AUTO_ACCEPTED"):
            raise ValueError("auto_accepted_ids mismatch")
        if self.human_accepted_ids != _ids_for("HUMAN_ACCEPTED"):
            raise ValueError("human_accepted_ids mismatch")
        if self.rejected_ids != _ids_for("REJECTED"):
            raise ValueError("rejected_ids mismatch")
        if self.unresolved_ids != _ids_for("UNRESOLVED"):
            raise ValueError("unresolved_ids mismatch")
        for obs in self.observations:
            if obs.observation.policy_fingerprint != self.policy_fingerprint:
                raise ValueError("policy_fingerprint mismatch with observation")
            if obs.queue_fingerprint != self.queue_fingerprint:
                raise ValueError("queue_fingerprint mismatch")
        if (self.ledger_seal is None) != (self.ledger_fingerprint is None):
            raise ValueError(
                "ledger_seal and ledger_fingerprint must both be present or both absent"
            )
        # Strict ledger binding: any projection carrying a decision must be bound to a present
        # result ledger seal+fingerprint, and every decided projection seal must equal it.
        # Conversely, no-ledger results must contain no human decision fields.
        for proj in self.observations:
            has_human_fields = (
                proj.decision_fingerprint is not None
                or proj.decision_kind is not None
                or proj.reviewer_name is not None
                or proj.reviewer_role is not None
                or proj.decided_at_utc is not None
                or proj.ledger_seal is not None
            )
            if has_human_fields:
                # all decided projections must carry the full sealed tuple
                if proj.ledger_seal is None or proj.decision_fingerprint is None:
                    raise ValueError(
                        "decided projection must carry ledger_seal and decision_fingerprint"
                    )
                if proj.decision_kind is None or proj.reviewer_name is None:
                    raise ValueError("decided projection must carry decision_kind and reviewer")
                if self.ledger_seal is None or self.ledger_fingerprint is None:
                    raise ValueError(
                        "workflow with human decision projections requires ledger seal+fingerprint"
                    )
                if proj.ledger_seal != self.ledger_seal:
                    raise ValueError("ledger_seal mismatch for decided observation")
        if self.ledger_seal is None:
            # no-ledger workflow must have zero human decision fields
            for proj in self.observations:
                if (
                    proj.ledger_seal is not None
                    or proj.decision_fingerprint is not None
                    or proj.decision_kind is not None
                    or proj.reviewer_name is not None
                    or proj.reviewer_role is not None
                    or proj.decided_at_utc is not None
                ):
                    raise ValueError("no-ledger result must not contain human decision fields")
        return self


def _diagnostics_for(obs: ObservationMatchV11) -> tuple[str, ...]:
    parts: list[str] = []
    parts.extend(obs.reasons)
    parts.extend(obs.review_reasons)
    for r in obs.rejections:
        parts.append(f"rejected {r.edge_id}: {r.reason} distance_m={r.distance_m}")
    for o in obs.overrides_refused:
        parts.append(f"override refused {o.edge_id}: {o.refusal}")
    if obs.missing_evidence:
        parts.append("missing evidence: " + ",".join(obs.missing_evidence))
    if obs.family_mismatch:
        parts.append(f"family_mismatch: {obs.family_mismatch}")
    if not parts:
        parts.append(f"disposition {obs.disposition} confidence {obs.confidence}")
    # Per-item length truncation deterministically.
    truncated = [p[:MAX_DIAGNOSTIC_LEN] for p in parts]
    if len(truncated) <= MAX_DIAGNOSTICS:
        return tuple(truncated)
    # Explicitly mark omitted count; keep deterministic order.
    omitted = len(truncated) - (MAX_DIAGNOSTICS - 1)
    keep = truncated[: MAX_DIAGNOSTICS - 1]
    marker = f"... {omitted} diagnostics omitted"
    marker = marker[:MAX_DIAGNOSTIC_LEN]
    return tuple(keep + [marker])


def _ambiguity_reason(obs: ObservationMatchV11) -> str | None:
    if len(obs.groups) > 1 and obs.disposition == "awaiting_manual_review":
        nearest = min(g.nearest_distance_m for g in obs.groups)
        return f"{len(obs.groups)} eligible road groups compete; nearest {nearest} m"
    return None


def _unmatched_reason(obs: ObservationMatchV11) -> str | None:
    if obs.disposition == "no_suitable_candidate":
        return "no candidate survived the approved filters, including the override"
    if obs.disposition == "unavailable_missing_evidence":
        if obs.missing_evidence:
            return "unavailable through missing evidence: " + ",".join(obs.missing_evidence)
        return "unavailable_missing_evidence"
    return None


def _nearest_distance(obs: ObservationMatchV11) -> Decimal | None:
    if not obs.groups:
        return None
    return min(g.nearest_distance_m for g in obs.groups)


def _auto_accepted_group(obs: ObservationMatchV11) -> RoadGroupV11:
    """Derive the policy-accepted group deterministically, never by distance.

    * strict ``strict_v1_0_clear`` → the unique non-``admitted_by_override`` group
      consistent with the base-policy acceptance.
    * override ``exact_reference_family_override`` → the unique
      ``admitted_by_override`` group whose members exactly equal
      ``overrides_applied`` identities and that is the sole
      ``exact_reference_match`` group.

    Fails closed (``MapMatchWorkflowError``) if the derivation is not
    unique/coherent.  Never guesses by nearest distance.
    """

    if obs.acceptance_path == "strict_v1_0_clear":
        non_override = [g for g in obs.groups if not g.admitted_by_override]
        if len(non_override) != 1:
            raise MapMatchWorkflowError(
                "AMBIGUOUS_AUTO_ACCEPTED",
                f"observation {obs.count_point_id} strict acceptance requires exactly "
                f"one non-override group, found {len(non_override)}",
            )
        selected = non_override[0]
        if obs.overrides_applied:
            raise MapMatchWorkflowError(
                "INCOHERENT_AUTO_ACCEPTED",
                f"observation {obs.count_point_id} strict path must not carry overrides_applied",
            )
        return selected
    if obs.acceptance_path == "exact_reference_family_override":
        if not obs.overrides_applied:
            raise MapMatchWorkflowError(
                "INCOHERENT_AUTO_ACCEPTED",
                f"observation {obs.count_point_id} override acceptance requires overrides_applied",
            )
        override_edge_ids = {o.edge_id for o in obs.overrides_applied}
        candidates = [
            g
            for g in obs.groups
            if g.admitted_by_override and {m.edge_id for m in g.members} == override_edge_ids
        ]
        if len(candidates) != 1:
            # Fallback to subset check only to give a deterministic failure message;
            # still requires uniqueness.
            candidates = [
                g
                for g in obs.groups
                if g.admitted_by_override
                and override_edge_ids.issubset({m.edge_id for m in g.members})
            ]
            if len(candidates) != 1:
                raise MapMatchWorkflowError(
                    "AMBIGUOUS_AUTO_ACCEPTED",
                    f"observation {obs.count_point_id} override acceptance requires exactly "
                    f"one admitted_by_override group matching overrides_applied, "
                    f"found {len(candidates)}",
                )
        selected = candidates[0]
        exact_groups = [g for g in obs.groups if g.exact_reference_match]
        if len(exact_groups) != 1 or exact_groups[0].group_key != selected.group_key:
            raise MapMatchWorkflowError(
                "INCOHERENT_AUTO_ACCEPTED",
                f"observation {obs.count_point_id} override acceptance requires exactly one "
                f"exact_reference group equal to the admitted group",
            )
        if not selected.admitted_by_override or not selected.exact_reference_match:
            raise MapMatchWorkflowError(
                "INCOHERENT_AUTO_ACCEPTED",
                f"observation {obs.count_point_id} override group must be admitted_by_override "
                f"and exact_reference_match",
            )
        return selected
    raise MapMatchWorkflowError(
        "INCOHERENT_AUTO_ACCEPTED",
        f"observation {obs.count_point_id} has unexpected acceptance_path {obs.acceptance_path!r}",
    )


def _matched_edge_ids_for_auto(obs: ObservationMatchV11) -> tuple[str, ...]:
    grp = _auto_accepted_group(obs)
    return tuple(sorted({m.edge_id for m in grp.members}))


def _matched_edge_ids_for_human(obs: ObservationMatchV11, accepted_key: str) -> tuple[str, ...]:
    grp = next((g for g in obs.groups if g.group_key == accepted_key), None)
    if grp is None:
        raise MapMatchWorkflowError(
            "GROUP_MISMATCH",
            f"observation {obs.count_point_id} references unknown group {accepted_key}",
        )
    return tuple(sorted({m.edge_id for m in grp.members}))


def build_map_match_workflow(
    *,
    observations: Sequence[ObservationMatchV11],
    queue: ManualReviewQueue,
    policy: object,
    source: MapMatchDftSourceIdentity,
    ledger: MatchReviewLedger | None = None,
) -> MapMatchWorkflowResult:
    """Build deterministic projection. Fails closed on every mismatch or ambiguity."""

    from traffictwin.integration.manchester.observation_matching_v11 import (
        ManchesterMapMatchPolicyV11,
    )

    if not isinstance(source, MapMatchDftSourceIdentity):
        raise MapMatchWorkflowError(
            "SOURCE_IDENTITY_INVALID", "source must be an admitted MapMatchDftSourceIdentity"
        )
    # Canonically revalidate source from its dump to defeat model_copy bypass.
    try:
        source = MapMatchDftSourceIdentity.model_validate(source.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError(
            "SOURCE_IDENTITY_INVALID", _sanitize_workflow_error(exc)
        ) from None
    # Source identity validation already ran via Pydantic, but enforce blocked/unaccepted
    # explicitly for fail-closed error codes distinct from Pydantic ValidationError.
    if source.is_source_blocked:
        raise MapMatchWorkflowError("SOURCE_BLOCKED", "source is blocked")
    if not source.is_accepted:
        raise MapMatchWorkflowError("SOURCE_NOT_ACCEPTED", "source is not accepted")

    if not isinstance(policy, ManchesterMapMatchPolicyV11):
        raise MapMatchWorkflowError(
            "POLICY_INCOMPATIBLE", "policy must be ManchesterMapMatchPolicyV11"
        )
    # Canonically revalidate policy, observations, queue, and ledger before trusting.
    try:
        policy = ManchesterMapMatchPolicyV11.model_validate(policy.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError("POLICY_INVALID", _sanitize_workflow_error(exc)) from None

    # Revalidate observations canonically; do not continue using forged instances.
    _revalidated_obs: list[ObservationMatchV11] = []
    for _obs in observations:
        if not isinstance(_obs, ObservationMatchV11):
            raise MapMatchWorkflowError("OBSERVATION_INVALID", "observation invalid")
        try:
            _ro = ObservationMatchV11.model_validate(_obs.model_dump())
        except Exception as exc:  # noqa: BLE001
            raise MapMatchWorkflowError(
                "OBSERVATION_INVALID", _sanitize_workflow_error(exc)
            ) from None
        _revalidated_obs.append(_ro)
    observations = tuple(_revalidated_obs)

    if not isinstance(queue, ManualReviewQueue):
        raise MapMatchWorkflowError("QUEUE_INVALID", "queue invalid")
    try:
        queue = ManualReviewQueue.model_validate(queue.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError("QUEUE_INVALID", _sanitize_workflow_error(exc)) from None

    if ledger is not None:
        if not isinstance(ledger, MatchReviewLedger):
            raise MapMatchWorkflowError("LEDGER_INVALID", "ledger invalid")
        try:
            ledger = MatchReviewLedger.model_validate(ledger.model_dump())
        except Exception as exc:  # noqa: BLE001
            raise MapMatchWorkflowError("LEDGER_INVALID", _sanitize_workflow_error(exc)) from None

    if not observations:
        raise MapMatchWorkflowError("EMPTY_OBSERVATIONS", "at least one observation required")
    if len(observations) > MAX_OBSERVATIONS:
        raise MapMatchWorkflowError("BOUNDS_EXCEEDED", "too many observations")

    ids = [o.count_point_id for o in observations]
    if len(set(ids)) != len(ids):
        raise MapMatchWorkflowError("DUPLICATE_OBSERVATION", "duplicate count_point_id")

    # Per-observation duplicate-edge rejection, deterministically scoped.
    for obs in observations:
        edge_ids_in_obs = [m.edge_id for g in obs.groups for m in g.members]
        if len(set(edge_ids_in_obs)) != len(edge_ids_in_obs):
            raise MapMatchWorkflowError(
                "DUPLICATE_EDGE", f"observation {obs.count_point_id} contains duplicate edge_id"
            )

    sorted_obs = tuple(sorted(observations, key=lambda o: o.count_point_id))
    policy_fp = policy.fingerprint()
    for obs in sorted_obs:
        if obs.policy_fingerprint != policy_fp:
            raise MapMatchWorkflowError(
                "POLICY_MISMATCH",
                f"observation {obs.count_point_id} policy_fingerprint mismatch",
            )

    queue_fp = queue.fingerprint()
    if queue.policy_id != MAP_MATCH_POLICY_V11_ID:
        raise MapMatchWorkflowError("QUEUE_POLICY_MISMATCH", "queue policy_id mismatch")
    # Validate queue denominators and duplicate point IDs against exact observation set.
    if queue.observations_total != len(observations):
        raise MapMatchWorkflowError(
            "QUEUE_DENOMINATOR_MISMATCH",
            "queue observations_total contradicts observation set",
        )
    _expected_accepted = sum(
        1 for o in observations if o.disposition == "owner_policy_accepted_candidate"
    )
    if queue.accepted_total != _expected_accepted:
        raise MapMatchWorkflowError(
            "QUEUE_DENOMINATOR_MISMATCH",
            "queue accepted_total contradicts observation set",
        )
    if queue.queued_total != len(queue.entries):
        raise MapMatchWorkflowError(
            "QUEUE_DENOMINATOR_MISMATCH",
            "queue queued_total contradicts entries length",
        )
    if queue.queued_total != (len(observations) - _expected_accepted):
        raise MapMatchWorkflowError(
            "QUEUE_DENOMINATOR_MISMATCH",
            "queue queued_total contradicts observation dispositions",
        )
    if len({e.count_point_id for e in queue.entries}) != len(queue.entries):
        raise MapMatchWorkflowError(
            "DUPLICATE_QUEUE_ENTRY", "queue contains duplicate count_point_id"
        )
    # queue must bind all non-accepted observations exactly
    queue_ids = {e.count_point_id for e in queue.entries}
    queue_by_id = {e.count_point_id: e for e in queue.entries}
    for obs in sorted_obs:
        if obs.disposition == "owner_policy_accepted_candidate":
            if obs.count_point_id in queue_ids:
                raise MapMatchWorkflowError(
                    "QUEUE_MISMATCH",
                    f"auto-accepted observation {obs.count_point_id} must not be in queue",
                )
        else:
            if obs.count_point_id not in queue_ids:
                raise MapMatchWorkflowError(
                    "QUEUE_MISMATCH",
                    f"observation {obs.count_point_id} disposition {obs.disposition} not in queue",
                )
            # exact queue entry identity binding: disposition, eligible_group_count, ref
            entry = queue_by_id[obs.count_point_id]
            if entry.disposition != obs.disposition:
                raise MapMatchWorkflowError(
                    "QUEUE_ENTRY_MISMATCH", f"disposition mismatch for {obs.count_point_id}"
                )
            if entry.eligible_group_count != len(obs.groups):
                raise MapMatchWorkflowError(
                    "QUEUE_ENTRY_MISMATCH",
                    f"eligible_group_count mismatch for {obs.count_point_id}",
                )
            if entry.dft_road_type != obs.dft_road_type:
                raise MapMatchWorkflowError(
                    "QUEUE_ENTRY_MISMATCH", f"dft_road_type mismatch for {obs.count_point_id}"
                )
            # nearest distance binding when groups present
            if obs.groups:
                expected_nearest = min(g.nearest_distance_m for g in obs.groups)
                if entry.nearest_distance_m != expected_nearest:
                    raise MapMatchWorkflowError(
                        "QUEUE_ENTRY_MISMATCH",
                        f"nearest_distance_m mismatch for {obs.count_point_id}",
                    )
            elif entry.nearest_distance_m is not None:
                raise MapMatchWorkflowError(
                    "QUEUE_ENTRY_MISMATCH",
                    f"queue entry should have no nearest distance for {obs.count_point_id}",
                )
    # queue must not contain extra ids not in observations
    obs_ids_set = set(ids)
    if queue_ids - obs_ids_set:
        raise MapMatchWorkflowError("QUEUE_MISMATCH", "queue contains unknown observation ids")

    ledger_seal: str | None = None
    ledger_fp: str | None = None
    live_decisions: dict[int, MatchReviewDecision] = {}
    if ledger is not None:
        if ledger.seal is None:
            raise MapMatchWorkflowError("LEDGER_NOT_SEALED", "ledger must be sealed")
        if ledger.seal != ledger.sealed_payload_fingerprint():
            raise MapMatchWorkflowError("LEDGER_TAMPERED", "ledger seal does not match payload")
        if ledger.queue_fingerprint != queue_fp:
            raise MapMatchWorkflowError("QUEUE_MISMATCH", "ledger queue_fingerprint mismatch")
        if ledger.policy_fingerprint != policy_fp:
            raise MapMatchWorkflowError("POLICY_MISMATCH", "ledger policy_fingerprint mismatch")
        ledger_seal = ledger.seal
        ledger_fp = ledger.sealed_payload_fingerprint()
        live_decisions = ledger.live_decisions()
        fps = [d.fingerprint() for d in ledger.decisions]
        if len(set(fps)) != len(fps):
            raise MapMatchWorkflowError("DUPLICATE_DECISION", "ledger contains duplicate decisions")
        for cid in live_decisions:
            if cid not in obs_ids_set:
                raise MapMatchWorkflowError(
                    "DECISION_OBSERVATION_MISMATCH",
                    f"ledger decision for unknown observation {cid}",
                )

    projections: list[MapMatchObservationProjection] = []
    for obs in sorted_obs:
        live = live_decisions.get(obs.count_point_id)
        diagnostics = _diagnostics_for(obs)
        amb = _ambiguity_reason(obs)
        unmatched = _unmatched_reason(obs)
        nearest = _nearest_distance(obs)

        if live is not None:
            kind = live.kind
            decided_at = _parse_utc_datetime(live.decided_at_utc)
            decision_fp = live.fingerprint()
            if kind == ReviewDecisionKind.ACCEPT_GROUP:
                group_keys = {g.group_key for g in obs.groups}
                accepted = live.accepted_group_key
                if accepted is None or accepted not in group_keys:
                    raise MapMatchWorkflowError(
                        "GROUP_MISMATCH",
                        f"decision for {obs.count_point_id} references unknown group {accepted}",
                    )
                standing: MapMatchStanding = "HUMAN_ACCEPTED"
                standing_reason = (
                    f"sealed named review accepted group {accepted} by "
                    f"{live.reviewer.reviewer_name}"
                )
                reviewer_name = live.reviewer.reviewer_name
                reviewer_role = live.reviewer.reviewer_role
                accepted_key = accepted
                matched_ids = _matched_edge_ids_for_human(obs, accepted)
            elif kind == ReviewDecisionKind.REJECT_ALL_CANDIDATES:
                standing = "REJECTED"
                standing_reason = (
                    f"sealed named review rejected all candidates by {live.reviewer.reviewer_name}"
                )
                reviewer_name = live.reviewer.reviewer_name
                reviewer_role = live.reviewer.reviewer_role
                decision_fp = live.fingerprint()
                accepted_key = None
                matched_ids = ()
            elif kind == ReviewDecisionKind.DEFER:
                standing = "UNRESOLVED"
                standing_reason = (
                    f"sealed review deferred by {live.reviewer.reviewer_name}; remains unresolved"
                )
                reviewer_name = live.reviewer.reviewer_name
                reviewer_role = live.reviewer.reviewer_role
                accepted_key = None
                matched_ids = ()
            else:
                raise MapMatchWorkflowError(
                    "INVALID_DECISION_KIND", f"unknown decision kind {kind}"
                )
            _reject_private_paths(standing_reason, "standing_reason")
            _reject_secrets(standing_reason, "standing_reason")
            try:
                proj = MapMatchObservationProjection(
                    observation=obs,
                    queue_fingerprint=queue_fp,
                    ledger_seal=ledger_seal,
                    standing=standing,
                    standing_reason=standing_reason,
                    diagnostics=diagnostics,
                    ambiguity_reason=amb,
                    unmatched_reason=unmatched,
                    reviewer_name=reviewer_name,
                    reviewer_role=reviewer_role,
                    decision_fingerprint=decision_fp,
                    decided_at_utc=decided_at,
                    decision_kind=kind,
                    accepted_group_key=accepted_key,
                    matched_edge_ids=matched_ids,
                    nearest_distance_m=nearest,
                    original_disposition=obs.disposition,
                )
            except MapMatchWorkflowError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise MapMatchWorkflowError(
                    "PROJECTION_INVALID", _sanitize_workflow_error(exc)
                ) from None
            projections.append(proj)
        else:
            if obs.disposition == "owner_policy_accepted_candidate":
                if obs.confidence != "clear_candidate":
                    raise MapMatchWorkflowError(
                        "AMBIGUOUS_CANDIDATE_SILENTLY_ACCEPTED",
                        f"observation {obs.count_point_id} accepted without clear_candidate",
                    )
                if obs.acceptance_path is None:
                    raise MapMatchWorkflowError(
                        "AMBIGUOUS_CANDIDATE_SILENTLY_ACCEPTED",
                        f"observation {obs.count_point_id} accepted without acceptance_path",
                    )
                if not obs.groups:
                    raise MapMatchWorkflowError(
                        "AMBIGUOUS_CANDIDATE_SILENTLY_ACCEPTED",
                        f"observation {obs.count_point_id} accepted with no groups",
                    )
                if obs.review_reasons:
                    raise MapMatchWorkflowError(
                        "AMBIGUOUS_CANDIDATE_SILENTLY_ACCEPTED",
                        f"observation {obs.count_point_id} has review_reasons but is accepted",
                    )
                # AUTO must bind the deterministically derived policy-accepted group.
                derived_group = _auto_accepted_group(obs)
                matched_ids = _matched_edge_ids_for_auto(obs)
                accepted_key = derived_group.group_key
                standing = "AUTO_ACCEPTED"
                standing_reason = (
                    "owner policy unambiguously accepted under clear thresholds; "
                    "distance alone not sufficient"
                )
                reviewer_name = None
                reviewer_role = None
                decision_fp = None
                decided_at = None
                kind = None
            elif obs.disposition in ("no_suitable_candidate", "unavailable_missing_evidence"):
                standing = "REJECTED"
                standing_reason = unmatched or f"policy {obs.disposition}; no suitable candidate"
                reviewer_name = None
                reviewer_role = None
                decision_fp = None
                decided_at = None
                accepted_key = None
                matched_ids = ()
                kind = None
            elif obs.disposition == "awaiting_manual_review":
                standing = "UNRESOLVED"
                standing_reason = "awaiting manual review; no sealed decision; reproducible queue"
                reviewer_name = None
                reviewer_role = None
                decision_fp = None
                decided_at = None
                accepted_key = None
                matched_ids = ()
                kind = None
            else:
                raise MapMatchWorkflowError(
                    "UNKNOWN_DISPOSITION", f"unknown disposition {obs.disposition}"
                )
            _reject_private_paths(standing_reason, "standing_reason")
            _reject_secrets(standing_reason, "standing_reason")
            try:
                proj = MapMatchObservationProjection(
                    observation=obs,
                    queue_fingerprint=queue_fp,
                    ledger_seal=None,
                    standing=standing,
                    standing_reason=standing_reason,
                    diagnostics=diagnostics,
                    ambiguity_reason=amb,
                    unmatched_reason=unmatched,
                    reviewer_name=reviewer_name,
                    reviewer_role=reviewer_role,
                    decision_fingerprint=decision_fp,
                    decided_at_utc=decided_at,
                    decision_kind=kind,
                    accepted_group_key=accepted_key,
                    matched_edge_ids=matched_ids,
                    nearest_distance_m=nearest,
                    original_disposition=obs.disposition,
                )
            except MapMatchWorkflowError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise MapMatchWorkflowError(
                    "PROJECTION_INVALID", _sanitize_workflow_error(exc)
                ) from None
            projections.append(proj)

    projections_sorted = tuple(sorted(projections, key=lambda p: p.observation.count_point_id))

    def _ids(standing: MapMatchStanding) -> tuple[int, ...]:
        return tuple(
            sorted(
                o.observation.count_point_id for o in projections_sorted if o.standing == standing
            )
        )

    try:
        result = MapMatchWorkflowResult(
            policy_fingerprint=policy_fp,
            queue_fingerprint=queue_fp,
            ledger_seal=ledger_seal,
            ledger_fingerprint=ledger_fp,
            source=source,
            observations=projections_sorted,
            pending_queue=_ids("UNRESOLVED"),
            auto_accepted_ids=_ids("AUTO_ACCEPTED"),
            human_accepted_ids=_ids("HUMAN_ACCEPTED"),
            rejected_ids=_ids("REJECTED"),
            unresolved_ids=_ids("UNRESOLVED"),
        )
    except MapMatchWorkflowError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError(
            "WORKFLOW_RESULT_INVALID", _sanitize_workflow_error(exc)
        ) from None
    return result


def verify_workflow_fingerprint(
    workflow: MapMatchWorkflowResult,
    policy: object,
    queue: object,
    ledger: object | None,
    *,
    source: MapMatchDftSourceIdentity,
) -> str:
    """Verify a workflow canonically and return its fingerprint.

    Requires exact ``policy``, ``queue``, ``ledger`` and ``source`` dependencies,
    canonically revalidates all, deterministically rebuilds the workflow via
    :func:`build_map_match_workflow`, and refuses any fabricated human decision,
    ledger identity or source.  No digest fallback is provided – a verify call
    must prove freshness, not just canonical validity.
    """

    # Canonical revalidation – defeats model_copy bypass.
    try:
        workflow = MapMatchWorkflowResult.model_validate(workflow.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError("WORKFLOW_INVALID", _sanitize_workflow_error(exc)) from None

    from traffictwin.integration.manchester.observation_matching_v11 import (
        ManchesterMapMatchPolicyV11,
    )

    # Require exact dependencies – no optional digest path.
    if policy is None or queue is None or source is None:
        raise MapMatchWorkflowError(
            "VERIFICATION_REQUIRES_DEPENDENCIES",
            "verification requires exact policy, queue, ledger and source",
        )
    # ledger may be None for unsealed workflows but must be explicitly passed.
    # Revalidate supplied dependencies canonically.
    if not isinstance(policy, ManchesterMapMatchPolicyV11):
        raise MapMatchWorkflowError(
            "POLICY_INCOMPATIBLE", "policy must be ManchesterMapMatchPolicyV11"
        )
    try:
        policy = ManchesterMapMatchPolicyV11.model_validate(policy.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError("POLICY_INVALID", _sanitize_workflow_error(exc)) from None

    if not isinstance(queue, ManualReviewQueue):
        raise MapMatchWorkflowError("QUEUE_INVALID", "queue invalid")
    try:
        queue = ManualReviewQueue.model_validate(queue.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError("QUEUE_INVALID", _sanitize_workflow_error(exc)) from None

    if ledger is not None:
        if not isinstance(ledger, MatchReviewLedger):
            raise MapMatchWorkflowError("LEDGER_INVALID", "ledger invalid")
        try:
            ledger = MatchReviewLedger.model_validate(ledger.model_dump())
        except Exception as exc:  # noqa: BLE001
            raise MapMatchWorkflowError("LEDGER_INVALID", _sanitize_workflow_error(exc)) from None
        if ledger.seal is None:
            raise MapMatchWorkflowError(
                "LEDGER_NOT_SEALED", "ledger must be sealed for verification"
            )
    else:
        # Explicit None ledger requires workflow be unsealed; checked below.
        pass

    if not isinstance(source, MapMatchDftSourceIdentity):
        raise MapMatchWorkflowError("SOURCE_IDENTITY_INVALID", "source invalid")
    try:
        source = MapMatchDftSourceIdentity.model_validate(source.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError(
            "SOURCE_IDENTITY_INVALID", _sanitize_workflow_error(exc)
        ) from None
    if source.fingerprint() != workflow.source.fingerprint():
        raise MapMatchWorkflowError(
            "SOURCE_MISMATCH", "supplied source does not match workflow source"
        )
    effective_source = source

    # Ledger presence must match workflow.
    if (workflow.ledger_seal is None) != (ledger is None):
        if workflow.ledger_seal is not None and ledger is None:
            raise MapMatchWorkflowError(
                "LEDGER_MISSING", "workflow is sealed but no ledger was supplied for verification"
            )
        if workflow.ledger_seal is None and ledger is not None:
            raise MapMatchWorkflowError(
                "LEDGER_UNEXPECTED", "workflow has no ledger but one was supplied"
            )
    if ledger is not None and workflow.ledger_seal is not None:
        if ledger.seal != workflow.ledger_seal:
            raise MapMatchWorkflowError(
                "LEDGER_SEAL_MISMATCH", "ledger seal does not match workflow"
            )
        if ledger.sealed_payload_fingerprint() != workflow.ledger_fingerprint:
            raise MapMatchWorkflowError(
                "LEDGER_FINGERPRINT_MISMATCH", "ledger fingerprint does not match workflow"
            )

    # Extract observations from the workflow's projections.
    observations = tuple(p.observation for p in workflow.observations)

    # Rebuild deterministically and compare exactly.
    try:
        rebuilt = build_map_match_workflow(
            observations=observations,
            queue=queue,
            policy=policy,
            source=effective_source,
            ledger=ledger,
        )
    except MapMatchWorkflowError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MapMatchWorkflowError("VERIFICATION_FAILED", _sanitize_workflow_error(exc)) from None

    if rebuilt.fingerprint() != workflow.fingerprint():
        raise MapMatchWorkflowError(
            "WORKFLOW_TAMPERED",
            "workflow fingerprint does not match rebuilt canonical workflow",
        )
    # Exact equality beyond fingerprint (deterministic ordering already covered).
    if rebuilt.model_dump(mode="json") != workflow.model_dump(mode="json"):
        raise MapMatchWorkflowError(
            "WORKFLOW_TAMPERED", "workflow content does not match rebuilt result"
        )
    return workflow.fingerprint()


def load_verified_ledger(payload: str) -> MatchReviewLedger:
    """Load and verify a sealed ledger, failing closed on tamper."""

    from traffictwin.integration.manchester.observation_review import load_review_ledger

    return load_review_ledger(payload)
