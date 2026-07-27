"""Thin UI services for the analyst map-match review workflow (BETA-D-01).

The page-independent layer between a future Match Review page and the sealed
review ledger: load the queue and match rows from workspace artifacts, open or
continue a working ledger file, record exactly one decision at a time through
the library's fail-closed API, and seal for export. Nothing here computes a
match, relabels a candidate, or performs a bulk action — the underlying
library refuses all three, and this layer adds only file handling and
user-facing error text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from traffictwin.integration.manchester.observation_matching_v11 import (
    ManualReviewQueue,
    ObservationMatchV11,
    build_manual_review_queue,
)
from traffictwin.integration.manchester.observation_review import (
    MatchReviewDecision,
    MatchReviewError,
    MatchReviewLedger,
    MatchReviewStatus,
    ReviewDecisionKind,
    ReviewerIdentity,
    record_review_decision,
    review_status,
    seal_review_ledger,
    start_review_ledger,
)

_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class ReviewServiceError:
    """User-facing review-service error with optional technical detail."""

    message: str
    detail: str | None = None


@dataclass(frozen=True)
class LoadedReviewContext:
    """Everything the review page needs for one queue."""

    queue: ManualReviewQueue
    rows_by_count_point: dict[int, ObservationMatchV11]
    ledger: MatchReviewLedger
    status: MatchReviewStatus
    ledger_path: Path


def load_review_context(
    match_results_path: str | Path,
    ledger_path: str | Path,
    policy_fingerprint: str | None = None,
) -> LoadedReviewContext | ReviewServiceError:
    """Load match rows, derive the queue, and open or continue the ledger.

    The queue is always rebuilt from the match rows so it cannot drift from
    them; an existing working ledger must belong to exactly that queue and
    policy or loading refuses. When ``policy_fingerprint`` is omitted it is
    derived from the rows, which must all share one policy.
    """

    rows = _load_match_rows(Path(match_results_path))
    if isinstance(rows, ReviewServiceError):
        return rows
    fingerprints = {row.policy_fingerprint for row in rows.values()}
    if policy_fingerprint is None:
        if len(fingerprints) != 1:
            return ReviewServiceError(
                "The match rows mix more than one policy fingerprint; review them "
                "as separate artifacts."
            )
        policy_fingerprint = next(iter(fingerprints))
    elif fingerprints != {policy_fingerprint}:
        return ReviewServiceError(
            "The match rows were produced under a different policy than requested."
        )
    queue = build_manual_review_queue(list(rows.values()))
    ledger_file = Path(ledger_path)
    if ledger_file.exists():
        try:
            ledger = MatchReviewLedger.model_validate_json(ledger_file.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            return ReviewServiceError(
                "The working ledger could not be read.", detail=str(exc)[:500]
            )
        if ledger.seal is not None:
            return ReviewServiceError(
                "This ledger is sealed for export. Continue on an unsealed working "
                "copy, or choose a new ledger path."
            )
        if ledger.queue_fingerprint != queue.fingerprint():
            return ReviewServiceError(
                "The working ledger belongs to a different review queue; it will "
                "not be mixed with this one."
            )
        if ledger.policy_fingerprint != policy_fingerprint:
            return ReviewServiceError(
                "The working ledger was opened under a different matching policy."
            )
    else:
        ledger = start_review_ledger(queue, policy_fingerprint)
    try:
        status = review_status(ledger, queue)
    except MatchReviewError as exc:
        return ReviewServiceError("The ledger does not fit this queue.", detail=str(exc))
    return LoadedReviewContext(
        queue=queue,
        rows_by_count_point=rows,
        ledger=ledger,
        status=status,
        ledger_path=ledger_file,
    )


def record_decision_for_ui(
    context: LoadedReviewContext,
    *,
    count_point_id: int,
    kind: ReviewDecisionKind,
    reviewer_name: str,
    reviewer_role: str,
    reason: str,
    decided_at_utc: str,
    accepted_group_key: str | None = None,
    supersedes: str | None = None,
) -> LoadedReviewContext | ReviewServiceError:
    """Record exactly one decision and persist the updated working ledger."""

    try:
        decision = MatchReviewDecision(
            count_point_id=count_point_id,
            kind=kind,
            accepted_group_key=accepted_group_key,
            reason=reason,
            reviewer=ReviewerIdentity(reviewer_name=reviewer_name, reviewer_role=reviewer_role),
            decided_at_utc=decided_at_utc,
            supersedes=supersedes,
        )
    except ValidationError as exc:
        return ReviewServiceError(
            "The decision is incomplete: it needs a real reviewer name and role and "
            "a written reason of at least ten characters.",
            detail=str(exc)[:500],
        )
    row = context.rows_by_count_point.get(count_point_id)
    try:
        updated = record_review_decision(context.ledger, context.queue, decision, row=row)
    except MatchReviewError as exc:
        return ReviewServiceError("The decision was refused.", detail=str(exc))
    try:
        context.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        context.ledger_path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        return ReviewServiceError(
            "The decision was valid but the working ledger could not be written.",
            detail=str(exc)[:500],
        )
    return LoadedReviewContext(
        queue=context.queue,
        rows_by_count_point=context.rows_by_count_point,
        ledger=updated,
        status=review_status(updated, context.queue),
        ledger_path=context.ledger_path,
    )


def seal_ledger_for_export(
    context: LoadedReviewContext, export_path: str | Path
) -> Path | ReviewServiceError:
    """Write the sealed export beside the untouched working ledger."""

    sealed = seal_review_ledger(context.ledger)
    target = Path(export_path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(sealed.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        return ReviewServiceError("The sealed export could not be written.", detail=str(exc)[:500])
    return target


def _load_match_rows(
    path: Path,
) -> dict[int, ObservationMatchV11] | ReviewServiceError:
    if not path.is_file():
        return ReviewServiceError(
            "No match-results artifact exists at the configured path.",
            detail=str(path),
        )
    if path.stat().st_size > _MAX_ARTIFACT_BYTES:
        return ReviewServiceError("The match-results artifact exceeds the bounded size.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ReviewServiceError(
            "The match-results artifact is not readable JSON.", detail=str(exc)[:500]
        )
    if not isinstance(payload, list):
        return ReviewServiceError(
            "The match-results artifact must be a JSON list of v1.1 match rows."
        )
    rows: dict[int, ObservationMatchV11] = {}
    for index, item in enumerate(payload):
        try:
            # The strict frozen base refuses python-dict tuples, so each row
            # validates through JSON mode exactly as it was persisted.
            row = ObservationMatchV11.model_validate_json(json.dumps(item))
        except ValidationError as exc:
            return ReviewServiceError(
                f"Match row {index} is not a valid v1.1 result.", detail=str(exc)[:500]
            )
        if row.count_point_id in rows:
            return ReviewServiceError(
                f"Match row {index} duplicates count point {row.count_point_id}."
            )
        rows[row.count_point_id] = row
    if not rows:
        return ReviewServiceError("The match-results artifact contains no rows.")
    return rows
