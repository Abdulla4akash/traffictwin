"""Safe UI services for one-row-at-a-time analyst map-match review."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from traffictwin.integration.manchester.observation_matching_v11 import (
    ManualReviewEntry,
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
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

_MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
_MAX_LEDGER_BYTES = 16 * 1024 * 1024

DecisionState = Literal["pending", "accepted", "rejected", "deferred"]
CandidateBucket = Literal["none", "one", "multiple"]
ReviewSort = Literal["count_point", "candidate_count", "disposition"]


@dataclass(frozen=True, slots=True)
class ReviewArtifactRegistration:
    """One exact private artifact whose identity is committed in project evidence."""

    artifact_id: str
    label: str
    relative_path: Path
    artifact_sha256: str
    rows_total: int
    queued_total: int
    policy_fingerprint: str


REGISTERED_REVIEW_ARTIFACTS: tuple[ReviewArtifactRegistration, ...] = (
    ReviewArtifactRegistration(
        artifact_id="manchester-v11-20260728",
        label="Manchester policy v1.1 reproduction · 305 rows · 174 queued",
        relative_path=Path("manchester/match_results_v11_20260728.json"),
        artifact_sha256="12f1e67246cae4591f33786f745626965e7171b19f12def5ebffec56e3d8ab09",
        rows_total=305,
        queued_total=174,
        policy_fingerprint="f0bc213b02fab2f15b411982b8ad585ec0dda5df05b298d0954b34c0cbe1226c",
    ),
)


@dataclass(frozen=True, slots=True)
class ReviewServiceError:
    """Display-safe review-service error with optional bounded technical detail."""

    message: str
    detail: str | None = None
    code: str = "REVIEW_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class RegisteredReviewArtifact:
    """Verified option for the page; its private path is never rendered."""

    registration: ReviewArtifactRegistration
    artifact_path: Path
    queue_fingerprint: str

    @property
    def display_label(self) -> str:
        return self.registration.label


@dataclass(frozen=True)
class LoadedReviewContext:
    """Everything the review page needs for one exact queue and working ledger."""

    queue: ManualReviewQueue
    rows_by_count_point: dict[int, ObservationMatchV11]
    ledger: MatchReviewLedger
    status: MatchReviewStatus
    ledger_path: Path
    loaded_ledger_sha256: str | None


@dataclass(frozen=True, slots=True)
class ReviewRowView:
    """One presentation-only queue row plus its effective decision state."""

    entry: ManualReviewEntry
    row: ObservationMatchV11
    decision_state: DecisionState
    live_decision: MatchReviewDecision | None
    revision_count: int

    @property
    def candidate_bucket(self) -> CandidateBucket:
        count = len(self.row.groups)
        return "none" if count == 0 else "one" if count == 1 else "multiple"


def discover_registered_review_artifacts(
    workspace_path: str | Path | None,
) -> tuple[RegisteredReviewArtifact, ...] | ReviewServiceError:
    """Find only exact built-in registrations inside one verified v0.7 workspace."""

    if workspace_path is None:
        return ReviewServiceError(
            "Configure a verified durable v0.7 workspace to review registered match evidence.",
            code="WORKSPACE_UNCONFIGURED",
        )
    try:
        inspect_v07_workspace(workspace_path)
        workspace = Path(workspace_path).resolve(strict=True)
    except (V07WorkspaceError, OSError) as exc:
        return ReviewServiceError(
            "The configured review workspace failed its v0.7 integrity contract.",
            detail=_safe_detail(exc),
            code="WORKSPACE_INVALID",
        )
    options: list[RegisteredReviewArtifact] = []
    for registration in REGISTERED_REVIEW_ARTIFACTS:
        target = workspace / registration.relative_path
        if not target.exists():
            continue
        if target.is_symlink() or not target.is_file():
            return ReviewServiceError(
                "A registered match artifact has an unsafe local file type.",
                code="ARTIFACT_UNSAFE",
            )
        try:
            resolved = target.resolve(strict=True)
            if not resolved.is_relative_to(workspace):
                raise OSError("registered artifact escaped workspace")
            payload = _bounded_file_bytes(target, _MAX_ARTIFACT_BYTES)
        except OSError as exc:
            return ReviewServiceError(
                "A registered match artifact could not be verified safely.",
                detail=_safe_detail(exc),
                code="ARTIFACT_READ_FAILED",
            )
        if hashlib.sha256(payload).hexdigest() != registration.artifact_sha256:
            return ReviewServiceError(
                "A registered match artifact no longer matches its committed identity.",
                code="ARTIFACT_DIGEST_MISMATCH",
            )
        rows = _load_match_rows_payload(payload)
        if isinstance(rows, ReviewServiceError):
            return rows
        queue = build_manual_review_queue(tuple(rows.values()))
        policies = {row.policy_fingerprint for row in rows.values()}
        if (
            len(rows) != registration.rows_total
            or queue.queued_total != registration.queued_total
            or policies != {registration.policy_fingerprint}
        ):
            return ReviewServiceError(
                "A registered match artifact failed its row, queue or policy reconciliation.",
                code="ARTIFACT_RECONCILIATION_FAILED",
            )
        options.append(
            RegisteredReviewArtifact(
                registration=registration,
                artifact_path=target,
                queue_fingerprint=queue.fingerprint(),
            )
        )
    return tuple(options)


def review_ledger_path(
    workspace_path: str | Path,
    artifact: RegisteredReviewArtifact,
) -> Path:
    """Return the fixed private working-ledger path for one queue/policy binding."""

    workspace = Path(workspace_path)
    filename = (
        f"{artifact.registration.artifact_id}-"
        f"{artifact.queue_fingerprint[:16]}-"
        f"{artifact.registration.policy_fingerprint[:16]}.working.json"
    )
    return workspace / "manchester" / "review" / filename


def review_export_path(context: LoadedReviewContext) -> Path:
    """Return a content-addressed sealed-export path without overwriting an earlier seal."""

    identity = context.ledger.sealed_payload_fingerprint()[:16]
    return context.ledger_path.with_name(
        context.ledger_path.name.removesuffix(".working.json") + f"-{identity}.sealed.json"
    )


def load_review_context(
    match_results_path: str | Path,
    ledger_path: str | Path,
    policy_fingerprint: str | None = None,
) -> LoadedReviewContext | ReviewServiceError:
    """Load exact rows, derive the queue, and reopen its verified working ledger."""

    rows = _load_match_rows(Path(match_results_path))
    if isinstance(rows, ReviewServiceError):
        return rows
    fingerprints = {row.policy_fingerprint for row in rows.values()}
    if policy_fingerprint is None:
        if len(fingerprints) != 1:
            return ReviewServiceError(
                "The match rows mix more than one policy fingerprint; review them as separate "
                "artifacts.",
                code="POLICY_MIXED",
            )
        policy_fingerprint = next(iter(fingerprints))
    elif fingerprints != {policy_fingerprint}:
        return ReviewServiceError(
            "The match rows were produced under a different policy than requested.",
            code="POLICY_MISMATCH",
        )
    queue = build_manual_review_queue(tuple(rows.values()))
    ledger_file = Path(ledger_path)
    loaded_sha256: str | None = None
    if ledger_file.exists():
        if ledger_file.is_symlink() or not ledger_file.is_file():
            return ReviewServiceError(
                "The working ledger has an unsafe local file type.", code="LEDGER_UNSAFE"
            )
        try:
            payload = _bounded_file_bytes(ledger_file, _MAX_LEDGER_BYTES)
            ledger = MatchReviewLedger.model_validate_json(payload)
        except (OSError, ValidationError) as exc:
            return ReviewServiceError(
                "The working ledger could not be verified.",
                detail=_safe_detail(exc),
                code="LEDGER_INVALID",
            )
        loaded_sha256 = hashlib.sha256(payload).hexdigest()
        if ledger.seal is not None:
            return ReviewServiceError(
                "This ledger is sealed for export. Continue on its unsealed working copy.",
                code="LEDGER_SEALED",
            )
        if ledger.queue_fingerprint != queue.fingerprint():
            return ReviewServiceError(
                "The working ledger belongs to a different review queue.",
                code="QUEUE_MISMATCH",
            )
        if ledger.policy_fingerprint != policy_fingerprint:
            return ReviewServiceError(
                "The working ledger was opened under a different matching policy.",
                code="POLICY_MISMATCH",
            )
    else:
        ledger = start_review_ledger(queue, policy_fingerprint)
    try:
        status = review_status(ledger, queue)
    except MatchReviewError as exc:
        return ReviewServiceError(
            "The ledger does not fit this queue.",
            detail=_safe_detail(exc),
            code="LEDGER_QUEUE_MISMATCH",
        )
    return LoadedReviewContext(
        queue=queue,
        rows_by_count_point=rows,
        ledger=ledger,
        status=status,
        ledger_path=ledger_file,
        loaded_ledger_sha256=loaded_sha256,
    )


def filtered_review_rows(
    context: LoadedReviewContext,
    *,
    query: str = "",
    dispositions: tuple[str, ...] = (),
    decision_states: tuple[DecisionState, ...] = (),
    candidate_buckets: tuple[CandidateBucket, ...] = (),
    sort_by: ReviewSort = "count_point",
) -> tuple[ReviewRowView, ...]:
    """Filter/sort presentation only; queue and ledger order never change."""

    entries = {item.count_point_id: item for item in context.queue.entries}
    live = context.ledger.live_decisions()
    revision_counts: dict[int, int] = {}
    for decision in context.ledger.decisions:
        revision_counts[decision.count_point_id] = (
            revision_counts.get(decision.count_point_id, 0) + 1
        )
    views = tuple(
        ReviewRowView(
            entry=entries[count_point_id],
            row=row,
            decision_state=_decision_state(live.get(count_point_id)),
            live_decision=live.get(count_point_id),
            revision_count=max(0, revision_counts.get(count_point_id, 0) - 1),
        )
        for count_point_id, row in context.rows_by_count_point.items()
        if count_point_id in entries
    )
    needle = query.strip().casefold()
    filtered = tuple(
        view
        for view in views
        if (not dispositions or view.entry.disposition in dispositions)
        and (not decision_states or view.decision_state in decision_states)
        and (not candidate_buckets or view.candidate_bucket in candidate_buckets)
        and (not needle or needle in _search_text(view))
    )
    key = {
        "count_point": lambda view: (view.entry.count_point_id,),
        "candidate_count": lambda view: (len(view.row.groups), view.entry.count_point_id),
        "disposition": lambda view: (view.entry.disposition, view.entry.count_point_id),
    }[sort_by]
    return tuple(sorted(filtered, key=key))


def changed_decision_count(context: LoadedReviewContext) -> int:
    """Count explicit superseding revisions without counting current decisions twice."""

    return len(context.ledger.decisions) - len(context.ledger.live_decisions())


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
    """Validate and atomically persist exactly one explicit human decision."""

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
            "The decision needs a real reviewer name and role and a written reason of at least "
            "ten characters.",
            detail=_safe_detail(exc),
            code="DECISION_INCOMPLETE",
        )
    row = context.rows_by_count_point.get(count_point_id)
    try:
        updated = record_review_decision(context.ledger, context.queue, decision, row=row)
    except MatchReviewError as exc:
        return ReviewServiceError(
            "The decision was refused.", detail=_safe_detail(exc), code="DECISION_REFUSED"
        )
    payload = updated.model_dump_json(indent=2).encode("utf-8")
    persisted = _persist_working_ledger(context, payload)
    if isinstance(persisted, ReviewServiceError):
        return persisted
    try:
        reloaded = MatchReviewLedger.model_validate_json(persisted)
        if reloaded != updated:
            raise ValueError("persisted ledger differs")
    except (ValidationError, ValueError) as exc:
        return ReviewServiceError(
            "The persisted decision failed readback verification.",
            detail=_safe_detail(exc),
            code="LEDGER_READBACK_FAILED",
        )
    return LoadedReviewContext(
        queue=context.queue,
        rows_by_count_point=context.rows_by_count_point,
        ledger=reloaded,
        status=review_status(reloaded, context.queue),
        ledger_path=context.ledger_path,
        loaded_ledger_sha256=hashlib.sha256(persisted).hexdigest(),
    )


def seal_ledger_for_export(
    context: LoadedReviewContext,
    export_path: str | Path | None = None,
) -> Path | ReviewServiceError:
    """Atomically publish a content-addressed seal while leaving the working copy untouched."""

    target = review_export_path(context) if export_path is None else Path(export_path)
    sealed = seal_review_ledger(context.ledger)
    payload = sealed.model_dump_json(indent=2).encode("utf-8")
    lock = _acquire_ledger_lock(context.ledger_path)
    if isinstance(lock, ReviewServiceError):
        return lock
    try:
        changed = _concurrent_change(context)
        if changed is not None:
            return changed
        result = _publish_new_exact(target, payload)
        if isinstance(result, ReviewServiceError):
            return result
        try:
            reloaded = MatchReviewLedger.model_validate_json(result)
        except ValidationError as exc:
            return ReviewServiceError(
                "The sealed export failed readback verification.",
                detail=_safe_detail(exc),
                code="SEAL_READBACK_FAILED",
            )
        if reloaded != sealed:
            return ReviewServiceError(
                "The sealed export failed readback verification.", code="SEAL_READBACK_FAILED"
            )
        return target
    finally:
        _release_lock(lock)


def _load_match_rows(path: Path) -> dict[int, ObservationMatchV11] | ReviewServiceError:
    if path.is_symlink() or not path.is_file():
        return ReviewServiceError(
            "No safe match-results artifact exists for this registration.",
            code="ARTIFACT_MISSING",
        )
    try:
        payload = _bounded_file_bytes(path, _MAX_ARTIFACT_BYTES)
    except OSError as exc:
        return ReviewServiceError(
            "The match-results artifact could not be read safely.",
            detail=_safe_detail(exc),
            code="ARTIFACT_READ_FAILED",
        )
    return _load_match_rows_payload(payload)


def _load_match_rows_payload(
    payload_bytes: bytes,
) -> dict[int, ObservationMatchV11] | ReviewServiceError:
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeDecodeError, ValueError) as exc:
        return ReviewServiceError(
            "The match-results artifact is not readable JSON.",
            detail=_safe_detail(exc),
            code="ARTIFACT_JSON_INVALID",
        )
    if not isinstance(payload, list):
        return ReviewServiceError(
            "The match-results artifact must be a JSON list of v1.1 rows.",
            code="ARTIFACT_SHAPE_INVALID",
        )
    rows: dict[int, ObservationMatchV11] = {}
    for index, item in enumerate(payload):
        try:
            row = ObservationMatchV11.model_validate_json(json.dumps(item))
        except ValidationError as exc:
            return ReviewServiceError(
                f"Match row {index} is not a valid v1.1 result.",
                detail=_safe_detail(exc),
                code="ARTIFACT_ROW_INVALID",
            )
        if row.count_point_id in rows:
            return ReviewServiceError(
                f"Match row {index} duplicates count point {row.count_point_id}.",
                code="ARTIFACT_ROW_DUPLICATE",
            )
        rows[row.count_point_id] = row
    if not rows:
        return ReviewServiceError(
            "The match-results artifact contains no rows.", code="ARTIFACT_EMPTY"
        )
    return rows


def _persist_working_ledger(
    context: LoadedReviewContext, payload: bytes
) -> bytes | ReviewServiceError:
    lock = _acquire_ledger_lock(context.ledger_path)
    if isinstance(lock, ReviewServiceError):
        return lock
    try:
        changed = _concurrent_change(context)
        if changed is not None:
            return changed
        published = _atomic_replace(context.ledger_path, payload)
        if isinstance(published, ReviewServiceError):
            return published
        try:
            return _bounded_file_bytes(context.ledger_path, _MAX_LEDGER_BYTES)
        except OSError as exc:
            return ReviewServiceError(
                "The working ledger could not be read back safely.",
                detail=_safe_detail(exc),
                code="LEDGER_READBACK_FAILED",
            )
    finally:
        _release_lock(lock)


def _concurrent_change(context: LoadedReviewContext) -> ReviewServiceError | None:
    target = context.ledger_path
    if not target.exists():
        current = None
    else:
        try:
            current = hashlib.sha256(_bounded_file_bytes(target, _MAX_LEDGER_BYTES)).hexdigest()
        except OSError as exc:
            return ReviewServiceError(
                "The working ledger changed or became unsafe; reload before deciding.",
                detail=_safe_detail(exc),
                code="LEDGER_CHANGED",
            )
    if current != context.loaded_ledger_sha256:
        return ReviewServiceError(
            "Another editor changed the working ledger; reload before deciding.",
            code="LEDGER_CHANGED",
        )
    return None


def _acquire_ledger_lock(path: Path) -> int | ReviewServiceError:
    try:
        parent = path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if parent.is_symlink() or not parent.is_dir():
            raise OSError("unsafe ledger directory")
        parent.chmod(0o700)
        lock_path = parent / f".{path.name}.lock"
        if lock_path.is_symlink() or (lock_path.exists() and not lock_path.is_file()):
            raise OSError("unsafe ledger lock")
        flags = os.O_WRONLY | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor
    except BlockingIOError:
        return ReviewServiceError(
            "Another editor is currently saving this ledger; try again after reloading.",
            code="LEDGER_BUSY",
        )
    except OSError as exc:
        return ReviewServiceError(
            "The private review ledger lock could not be acquired.",
            detail=_safe_detail(exc),
            code="LEDGER_LOCK_FAILED",
        )


def _release_lock(descriptor: int | ReviewServiceError) -> None:
    if isinstance(descriptor, ReviewServiceError):
        return
    fcntl.flock(descriptor, fcntl.LOCK_UN)
    os.close(descriptor)


def _atomic_replace(target: Path, payload: bytes) -> None | ReviewServiceError:
    if len(payload) > _MAX_LEDGER_BYTES:
        return ReviewServiceError(
            "The working ledger exceeds its bounded size.", code="LEDGER_TOO_LARGE"
        )
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
        _fsync_directory(target.parent)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        return ReviewServiceError(
            "The decision was valid but the working ledger could not be published atomically.",
            detail=_safe_detail(exc),
            code="LEDGER_WRITE_FAILED",
        )
    return None


def _publish_new_exact(target: Path, payload: bytes) -> bytes | ReviewServiceError:
    try:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise OSError("unsafe export target")
        if target.exists():
            existing = _bounded_file_bytes(target, _MAX_LEDGER_BYTES)
            if existing == payload:
                return existing
            return ReviewServiceError(
                "A different sealed export already uses this identity.",
                code="SEAL_TARGET_CONFLICT",
            )
        descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        temporary = Path(name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target, follow_symlinks=False)
        finally:
            temporary.unlink(missing_ok=True)
        target.chmod(0o600)
        _fsync_directory(target.parent)
        return _bounded_file_bytes(target, _MAX_LEDGER_BYTES)
    except OSError as exc:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)
        return ReviewServiceError(
            "The sealed export could not be published atomically.",
            detail=_safe_detail(exc),
            code="SEAL_WRITE_FAILED",
        )


def _bounded_file_bytes(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise OSError("unsafe file type")
    size = path.stat().st_size
    if size <= 0 or size > maximum:
        raise OSError("file size outside bound")
    payload = path.read_bytes()
    if len(payload) != size:
        raise OSError("file changed during read")
    return payload


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _decision_state(decision: MatchReviewDecision | None) -> DecisionState:
    if decision is None:
        return "pending"
    states: dict[ReviewDecisionKind, DecisionState] = {
        ReviewDecisionKind.ACCEPT_GROUP: "accepted",
        ReviewDecisionKind.REJECT_ALL_CANDIDATES: "rejected",
        ReviewDecisionKind.DEFER: "deferred",
    }
    return states[decision.kind]


def _search_text(view: ReviewRowView) -> str:
    values = (
        str(view.entry.count_point_id),
        view.entry.dft_normalised_ref or "",
        view.row.dft_road_name or "",
        view.entry.disposition,
        view.decision_state,
        *view.entry.review_reasons,
        *view.entry.missing_evidence,
    )
    return " ".join(values).casefold()


def _safe_detail(exc: BaseException) -> str:
    """Bound technical detail while never including a private filesystem path."""

    return type(exc).__name__[:80]
