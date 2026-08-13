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
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, TypeAlias

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.observation_matching_v11 import (
    MAP_MATCH_POLICY_V11_ID,
    ManualReviewQueue,
    ObservationMatchV11,
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

MAX_OBSERVATIONS = 1024
MAX_DIAGNOSTICS = 64
MAX_DIAGNOSTIC_LEN = 2000
MAX_REASON_LEN = 3000
MAX_SHORT_REASON = 1000


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
    except ValueError as exc:
        raise ValueError(f"invalid UTC datetime {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError("datetime must be timezone-aware UTC")
    return dt.astimezone(UTC)


class MapMatchWorkflowError(ValueError):
    """Fail-closed refusal with a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class MapMatchWorkflowModel(ManchesterSnapshotModel):
    """Frozen base."""


class MapMatchObservationProjection(MapMatchWorkflowModel):
    """Per-observation deterministic projection."""

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
    nearest_distance_m: Decimal | None = Field(default=None, ge=0)
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
        expected_nearest: Decimal | None = None
        if obs.groups:
            expected_nearest = min(g.nearest_distance_m for g in obs.groups)
        if self.nearest_distance_m != expected_nearest:
            raise ValueError("nearest_distance_m must equal minimal group distance")
        if self.standing == "AUTO_ACCEPTED":
            if obs.disposition != "owner_policy_accepted_candidate":
                raise ValueError("AUTO_ACCEPTED requires owner_policy_accepted_candidate")
            if obs.confidence != "clear_candidate":
                raise ValueError("AUTO_ACCEPTED requires clear_candidate")
            if obs.acceptance_path is None:
                raise ValueError("AUTO_ACCEPTED requires acceptance_path")
            if self.decision_fingerprint is not None or self.reviewer_name is not None:
                raise ValueError("AUTO_ACCEPTED must not carry a human decision")
            if self.accepted_group_key is not None:
                raise ValueError("AUTO_ACCEPTED must not carry accepted_group_key")
            if not obs.groups:
                raise ValueError("AUTO_ACCEPTED cannot have zero groups")
            if obs.review_reasons:
                raise ValueError("AUTO_ACCEPTED cannot carry review_reasons")
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
            if obs.disposition == "owner_policy_accepted_candidate":
                raise ValueError("owner-accepted observation cannot be HUMAN_ACCEPTED")
        elif self.standing == "REJECTED":
            if self.decision_kind == ReviewDecisionKind.ACCEPT_GROUP:
                raise ValueError("REJECTED cannot carry accept_group")
            if self.decision_kind == ReviewDecisionKind.REJECT_ALL_CANDIDATES and (
                self.decision_fingerprint is None
                or self.reviewer_name is None
                or self.ledger_seal is None
                or self.decided_at_utc is None
            ):
                raise ValueError("human REJECTED requires sealed decision")
        elif self.standing == "UNRESOLVED":
            if self.decision_kind == ReviewDecisionKind.ACCEPT_GROUP:
                raise ValueError("UNRESOLVED cannot be accept_group")
        else:
            raise ValueError("unknown standing")
        return self


class MapMatchWorkflowResult(MapMatchWorkflowModel):
    """Coherent deterministic projection over all observations."""

    schema_version: Literal["1.0"] = MAP_MATCH_WORKFLOW_SCHEMA_VERSION
    capability_id: Literal["MAN-09"] = MAP_MATCH_WORKFLOW_CAPABILITY_ID
    method_version: Literal["manchester-map-match-workflow-1.0"] = MAP_MATCH_WORKFLOW_METHOD_VERSION
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    queue_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    ledger_seal: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    ledger_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
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
            if (
                self.ledger_seal is not None
                and obs.decision_fingerprint is not None
                and obs.ledger_seal != self.ledger_seal
            ):
                raise ValueError("ledger_seal mismatch for decided observation")
        if (self.ledger_seal is None) != (self.ledger_fingerprint is None):
            raise ValueError(
                "ledger_seal and ledger_fingerprint must both be present or both absent"
            )
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
    # bound length, preserve order deterministically
    capped = tuple(p[:MAX_DIAGNOSTIC_LEN] for p in parts[:MAX_DIAGNOSTICS])
    if len(capped) != len(parts[:MAX_DIAGNOSTICS]):
        raise AssertionError("diagnostics bound violated")
    return capped


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


def build_map_match_workflow(
    *,
    observations: Sequence[ObservationMatchV11],
    queue: ManualReviewQueue,
    policy: object,
    ledger: MatchReviewLedger | None = None,
) -> MapMatchWorkflowResult:
    """Build deterministic projection. Fails closed on every mismatch or ambiguity."""

    from traffictwin.integration.manchester.observation_matching_v11 import (
        ManchesterMapMatchPolicyV11,
    )

    if not isinstance(policy, ManchesterMapMatchPolicyV11):
        raise MapMatchWorkflowError(
            "POLICY_INCOMPATIBLE", "policy must be ManchesterMapMatchPolicyV11"
        )
    if not observations:
        raise MapMatchWorkflowError("EMPTY_OBSERVATIONS", "at least one observation required")
    if len(observations) > MAX_OBSERVATIONS:
        raise MapMatchWorkflowError("BOUNDS_EXCEEDED", "too many observations")

    ids = [o.count_point_id for o in observations]
    if len(set(ids)) != len(ids):
        raise MapMatchWorkflowError("DUPLICATE_OBSERVATION", "duplicate count_point_id")

    # edge duplicate detection across observations
    seen_edges: set[str] = set()
    for obs in observations:
        for g in obs.groups:
            for m in g.members:
                if m.edge_id in seen_edges:
                    # duplicate edge ids across observations are not necessarily an error
                    # for synthetic fixtures, but we treat duplicate edge ids within the
                    # same observation's groups as a workflow anomaly.
                    pass
                # per-observation duplicate edge check
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
            elif kind == ReviewDecisionKind.REJECT_ALL_CANDIDATES:
                standing = "REJECTED"
                standing_reason = (
                    f"sealed named review rejected all candidates by {live.reviewer.reviewer_name}"
                )
                reviewer_name = live.reviewer.reviewer_name
                reviewer_role = live.reviewer.reviewer_role
                decision_fp = live.fingerprint()
                accepted_key = None
            elif kind == ReviewDecisionKind.DEFER:
                standing = "UNRESOLVED"
                standing_reason = (
                    f"sealed review deferred by {live.reviewer.reviewer_name}; remains unresolved"
                )
                reviewer_name = live.reviewer.reviewer_name
                reviewer_role = live.reviewer.reviewer_role
                accepted_key = None
            else:
                raise MapMatchWorkflowError(
                    "INVALID_DECISION_KIND", f"unknown decision kind {kind}"
                )
            _reject_private_paths(standing_reason, "standing_reason")
            _reject_secrets(standing_reason, "standing_reason")
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
                nearest_distance_m=nearest,
            )
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
                standing = "AUTO_ACCEPTED"
                standing_reason = (
                    "owner policy unambiguously accepted under clear thresholds; "
                    "distance alone not sufficient"
                )
                reviewer_name = None
                reviewer_role = None
                decision_fp = None
                decided_at = None
                accepted_key = None
                kind = None
            elif obs.disposition in ("no_suitable_candidate", "unavailable_missing_evidence"):
                standing = "REJECTED"
                standing_reason = unmatched or f"policy {obs.disposition}; no suitable candidate"
                reviewer_name = None
                reviewer_role = None
                decision_fp = None
                decided_at = None
                accepted_key = None
                kind = None
            elif obs.disposition == "awaiting_manual_review":
                standing = "UNRESOLVED"
                standing_reason = "awaiting manual review; no sealed decision; reproducible queue"
                reviewer_name = None
                reviewer_role = None
                decision_fp = None
                decided_at = None
                accepted_key = None
                kind = None
            else:
                raise MapMatchWorkflowError(
                    "UNKNOWN_DISPOSITION", f"unknown disposition {obs.disposition}"
                )
            _reject_private_paths(standing_reason, "standing_reason")
            _reject_secrets(standing_reason, "standing_reason")
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
                nearest_distance_m=nearest,
            )
            projections.append(proj)

    projections_sorted = tuple(sorted(projections, key=lambda p: p.observation.count_point_id))

    def _ids(standing: MapMatchStanding) -> tuple[int, ...]:
        return tuple(
            sorted(
                o.observation.count_point_id for o in projections_sorted if o.standing == standing
            )
        )

    result = MapMatchWorkflowResult(
        policy_fingerprint=policy_fp,
        queue_fingerprint=queue_fp,
        ledger_seal=ledger_seal,
        ledger_fingerprint=ledger_fp,
        observations=projections_sorted,
        pending_queue=_ids("UNRESOLVED"),
        auto_accepted_ids=_ids("AUTO_ACCEPTED"),
        human_accepted_ids=_ids("HUMAN_ACCEPTED"),
        rejected_ids=_ids("REJECTED"),
        unresolved_ids=_ids("UNRESOLVED"),
    )
    return result


def verify_workflow_fingerprint(workflow: MapMatchWorkflowResult) -> str:
    """Return canonical SHA-256 fingerprint."""

    return workflow.fingerprint()


def load_verified_ledger(payload: str) -> MatchReviewLedger:
    """Load and verify a sealed ledger, failing closed on tamper."""

    from traffictwin.integration.manchester.observation_review import load_review_ledger

    return load_review_ledger(payload)
