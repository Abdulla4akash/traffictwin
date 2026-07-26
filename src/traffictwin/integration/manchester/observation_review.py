"""Typed, sealed analyst decisions over the manual map-match review queue.

Policy v1.1 deliberately left 165 Manchester observations awaiting a person:
its own artifacts carry ``human_accepted: False`` as a type-level literal and
the CLI exposes no accept flag. This module is the missing decision half of
that workflow — a ledger in which a *named person* decides one row at a time,
with the reason recorded, the candidate group validated against the row's real
evidence, and every change of mind superseding rather than overwriting.

What the tooling refuses to make possible: an anonymous decision, a bulk
accept, a decision for a row the queue does not contain, a group the row does
not offer, an edited ledger passing itself off as sealed, or any label
stronger than ``analyst_reviewed_candidate``. Until a person uses it, every
queued row stays visibly pending — that pending state is the honest deliverable
of this slice, not a defect in it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from traffictwin.integration.manchester.observation_matching import ObservationMatchingModel
from traffictwin.integration.manchester.observation_matching_v11 import (
    MAP_MATCH_POLICY_V11_ID,
    ManualReviewQueue,
    ObservationMatchV11,
)

REVIEW_METHOD_VERSION: Literal["manchester-map-match-analyst-review-1.0"] = (
    "manchester-map-match-analyst-review-1.0"
)

_PLACEHOLDER_IDENTITIES = frozenset(
    {"tbd", "todo", "n/a", "na", "none", "unknown", "agent", "anonymous", "-", "_"}
)


class MatchReviewError(ValueError):
    """Raised when a decision or ledger cannot be admitted safely."""


class ReviewerIdentity(ObservationMatchingModel):
    """A named person; the tooling refuses anonymous or placeholder review."""

    reviewer_name: str = Field(min_length=1, max_length=200)
    reviewer_role: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_identity(self) -> ReviewerIdentity:
        for value in (self.reviewer_name, self.reviewer_role):
            if not value.strip() or value.strip().lower() in _PLACEHOLDER_IDENTITIES:
                raise ValueError(
                    "reviewer identity must name a real person and role, not a placeholder"
                )
        return self


class ReviewDecisionKind(StrEnum):
    """The three explicit actions a reviewer may take on one row."""

    ACCEPT_GROUP = "accept_group"
    REJECT_ALL_CANDIDATES = "reject_all_candidates"
    DEFER = "defer"


class MatchReviewDecision(ObservationMatchingModel):
    """One person's explicit decision for one queued observation."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["manchester-map-match-analyst-review-1.0"] = REVIEW_METHOD_VERSION
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    count_point_id: int = Field(ge=0)
    kind: ReviewDecisionKind
    accepted_group_key: str | None = Field(default=None, min_length=1, max_length=220)
    reason: str = Field(min_length=10, max_length=2_000)
    reviewer: ReviewerIdentity
    decided_at_utc: str = Field(min_length=1, max_length=64)
    #: Fingerprint of the earlier decision this one replaces, if any. The
    #: replaced decision stays in the ledger; nothing is ever overwritten.
    supersedes: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    research_status: Literal["analyst_reviewed_candidate"] = "analyst_reviewed_candidate"
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False
    bulk_operation: Literal[False] = False

    @model_validator(mode="after")
    def validate_decision(self) -> MatchReviewDecision:
        accepts = self.kind is ReviewDecisionKind.ACCEPT_GROUP
        if accepts != (self.accepted_group_key is not None):
            raise ValueError("exactly the accept_group decision names an accepted group key")
        return self


class MatchReviewStatus(ObservationMatchingModel):
    """Where the review stands; pending rows stay visible, never assumed done."""

    queued_total: int = Field(ge=0)
    decided_total: int = Field(ge=0)
    pending_total: int = Field(ge=0)
    accepted_total: int = Field(ge=0)
    rejected_total: int = Field(ge=0)
    deferred_total: int = Field(ge=0)
    no_candidate_preserved_total: int = Field(ge=0)
    pending_count_point_ids: tuple[int, ...] = ()

    @model_validator(mode="after")
    def validate_status(self) -> MatchReviewStatus:
        if self.decided_total + self.pending_total != self.queued_total:
            raise ValueError("decided and pending rows must account for the whole queue")
        if self.accepted_total + self.rejected_total + self.deferred_total != self.decided_total:
            raise ValueError("decision kinds must account for every live decision")
        if len(self.pending_count_point_ids) != self.pending_total:
            raise ValueError("pending rows must be listed, not merely counted")
        return self


class MatchReviewLedger(ObservationMatchingModel):
    """Append-only, seal-protected record of analyst decisions for one queue."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["manchester-map-match-analyst-review-1.0"] = REVIEW_METHOD_VERSION
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    queue_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: tuple[MatchReviewDecision, ...] = ()
    #: Two-pass seal over the complete payload with this field empty. A ledger
    #: without it, or whose bytes changed after sealing, refuses to load.
    seal: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_ledger(self) -> MatchReviewLedger:
        seen: dict[str, MatchReviewDecision] = {}
        live_by_row: dict[int, str] = {}
        for decision in self.decisions:
            fingerprint = decision.fingerprint()
            if decision.supersedes is not None:
                target = seen.get(decision.supersedes)
                if target is None:
                    raise ValueError(
                        "a superseding decision must reference an earlier ledger entry"
                    )
                if target.count_point_id != decision.count_point_id:
                    raise ValueError("a decision may only supersede the same observation")
                if live_by_row.get(decision.count_point_id) != decision.supersedes:
                    raise ValueError("only the live decision for a row may be superseded")
            elif decision.count_point_id in live_by_row:
                raise ValueError("a second decision for a row must explicitly supersede the first")
            seen[fingerprint] = decision
            live_by_row[decision.count_point_id] = fingerprint
        return self

    def live_decisions(self) -> dict[int, MatchReviewDecision]:
        """Return the effective decision per observation after supersessions."""

        live: dict[int, MatchReviewDecision] = {}
        for decision in self.decisions:
            live[decision.count_point_id] = decision
        return live

    def sealed_payload_fingerprint(self) -> str:
        """Fingerprint the ledger exactly as the seal covers it."""

        return self.model_copy(update={"seal": None}).fingerprint()


def start_review_ledger(queue: ManualReviewQueue, policy_fingerprint: str) -> MatchReviewLedger:
    """Open an empty, unsealed ledger bound to one exact queue and policy."""

    return MatchReviewLedger(
        queue_fingerprint=queue.fingerprint(),
        policy_fingerprint=policy_fingerprint,
    )


def record_review_decision(
    ledger: MatchReviewLedger,
    queue: ManualReviewQueue,
    decision: MatchReviewDecision,
    *,
    row: ObservationMatchV11 | None = None,
) -> MatchReviewLedger:
    """Append exactly one decision, failing closed on every identity mismatch.

    Accepting a group requires the full match row so the accepted key is
    checked against the row's actual groups — a queue summary alone cannot
    prove a group exists, so it is not allowed to.
    """

    if ledger.seal is not None:
        raise MatchReviewError("LEDGER_SEALED: append to the unsealed working ledger, then reseal")
    if ledger.queue_fingerprint != queue.fingerprint():
        raise MatchReviewError("QUEUE_MISMATCH: this ledger belongs to a different review queue")
    entry = next(
        (item for item in queue.entries if item.count_point_id == decision.count_point_id),
        None,
    )
    if entry is None:
        raise MatchReviewError(
            f"UNKNOWN_COUNT_POINT: {decision.count_point_id} is not in the review queue"
        )
    live = ledger.live_decisions().get(decision.count_point_id)
    if live is not None and decision.supersedes != live.fingerprint():
        raise MatchReviewError(
            "DUPLICATE_DECISION: the row already has a live decision; supersede it "
            "explicitly by fingerprint"
        )
    if live is None and decision.supersedes is not None:
        raise MatchReviewError("SUPERSEDE_TARGET_MISSING: nothing to supersede for this row")
    if decision.kind is ReviewDecisionKind.ACCEPT_GROUP:
        if row is None:
            raise MatchReviewError(
                "ROW_EVIDENCE_REQUIRED: accepting a group requires the full match row"
            )
        if row.count_point_id != decision.count_point_id:
            raise MatchReviewError("ROW_MISMATCH: the supplied row is a different observation")
        if row.policy_fingerprint != ledger.policy_fingerprint:
            raise MatchReviewError(
                "POLICY_MISMATCH: the supplied row was produced under a different policy"
            )
        group_keys = {group.group_key for group in row.groups}
        if decision.accepted_group_key not in group_keys:
            raise MatchReviewError(
                "UNKNOWN_GROUP: the accepted group key is not among the row's road groups"
            )
    return ledger.model_copy(update={"decisions": (*ledger.decisions, decision)})


def seal_review_ledger(ledger: MatchReviewLedger) -> MatchReviewLedger:
    """Seal the ledger for export; the seal covers every byte but itself."""

    return ledger.model_copy(update={"seal": ledger.sealed_payload_fingerprint()})


def load_review_ledger(payload: str) -> MatchReviewLedger:
    """Load one exported ledger, refusing unsealed or tampered content."""

    ledger = MatchReviewLedger.model_validate_json(payload)
    if ledger.seal is None:
        raise MatchReviewError("SEAL_MISSING: an exported ledger must be sealed")
    if ledger.seal != ledger.sealed_payload_fingerprint():
        raise MatchReviewError("SEAL_MISMATCH: the ledger changed after it was sealed")
    return ledger


def review_status(ledger: MatchReviewLedger, queue: ManualReviewQueue) -> MatchReviewStatus:
    """Report progress with pending rows listed, never silently assumed decided."""

    if ledger.queue_fingerprint != queue.fingerprint():
        raise MatchReviewError("QUEUE_MISMATCH: this ledger belongs to a different review queue")
    live = ledger.live_decisions()
    pending = tuple(
        sorted(entry.count_point_id for entry in queue.entries if entry.count_point_id not in live)
    )
    kinds = [decision.kind for decision in live.values()]
    return MatchReviewStatus(
        queued_total=queue.queued_total,
        decided_total=len(live),
        pending_total=len(pending),
        accepted_total=kinds.count(ReviewDecisionKind.ACCEPT_GROUP),
        rejected_total=kinds.count(ReviewDecisionKind.REJECT_ALL_CANDIDATES),
        deferred_total=kinds.count(ReviewDecisionKind.DEFER),
        no_candidate_preserved_total=sum(
            1 for entry in queue.entries if entry.disposition == "no_suitable_candidate"
        ),
        pending_count_point_ids=pending,
    )
