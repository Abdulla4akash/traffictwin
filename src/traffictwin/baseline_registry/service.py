"""Deterministic service for Baseline Registry — append-only ledger and promotion gates."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from traffictwin.baseline_registry.models import (
    BASELINE_SCHEMA_VERSION,
    BaselineApproval,
    BaselineCandidate,
    BaselineCompatibilityAudit,
    BaselineLedgerEntry,
    BaselineLedgerEventKind,
    BaselinePromotionOperation,
    BaselinePromotionReceipt,
    BaselinePromotionRequest,
    BaselineRecord,
    BaselineRegistry,
    BaselineScope,
    BaselineStatus,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_JSON_BYTES = 2_000_000
_LIMITATIONS = [
    "Promotion requires an explicit approval binding the exact candidate and scope; the newest candidate is never promoted automatically.",  # noqa: E501
    "Rollback is represented only by promoting a previous candidate through a new ledger event; historical records are never edited.",  # noqa: E501
    "Evidence and source standing are declared and checked at promotion; synthetic evidence is never relabelled as observed.",  # noqa: E501
    "Regression-gate policy is declared per baseline; this registry does not claim causality, optimality, or production readiness.",  # noqa: E501
    "Portable exports exclude local paths, retrieval clocks, and secrets; fingerprints use deterministic canonical JSON.",  # noqa: E501
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _now_or_fixed(clock: Callable[[], datetime] | None) -> datetime:
    if clock is None:
        return utc_now()
    return clock()


# ---------------------------------------------------------------------------
# Registry creation & validation helpers
# ---------------------------------------------------------------------------


def create_empty_registry(
    *,
    clock: Callable[[], datetime] | None = None,
) -> BaselineRegistry:
    """Return a new empty registry."""
    now = _now_or_fixed(clock)
    temp = BaselineRegistry(
        schema_version=BASELINE_SCHEMA_VERSION,
        created_at=now,
        ledger=[],
        candidates={},
        approvals={},
        active_baselines={},
        registry_fingerprint="0" * 64,
    )
    fp = temp.compute_fingerprint()
    return temp.model_copy(update={"registry_fingerprint": fp})


def _next_entry_index(registry: BaselineRegistry) -> int:
    return len(registry.ledger)


def _build_ledger_entry(
    *,
    entry_index: int,
    event_kind: BaselineLedgerEventKind,
    timestamp: datetime,
    scope_id: str,
    candidate_id: str | None,
    baseline_id: str | None,
    artifact_fingerprint: str | None,
    approval_fingerprint: str | None,
    superseded_fingerprint: str | None,
    registry_parent_fingerprint: str,
    actor: str | None,
    note: str | None,
) -> BaselineLedgerEntry:
    provisional = BaselineLedgerEntry(
        entry_index=entry_index,
        event_kind=event_kind,
        timestamp=timestamp,
        scope_id=scope_id,
        candidate_id=candidate_id,
        baseline_id=baseline_id,
        artifact_fingerprint=artifact_fingerprint,
        approval_fingerprint=approval_fingerprint,
        superseded_fingerprint=superseded_fingerprint,
        registry_parent_fingerprint=registry_parent_fingerprint,
        entry_fingerprint="0" * 64,
        actor=actor,
        note=note,
    )
    fp = provisional.compute_fingerprint()
    return provisional.model_copy(update={"entry_fingerprint": fp})


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------


def registry_limitations() -> list[str]:
    return list(_LIMITATIONS)


def validate_registry_json(
    payload: bytes | str, *, maximum_bytes: int = MAX_JSON_BYTES
) -> BaselineRegistry:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(data) > maximum_bytes:
        raise ValueError(f"registry JSON exceeds {maximum_bytes} bytes")
    return BaselineRegistry.model_validate_json(data)


def registry_to_json(registry: BaselineRegistry) -> str:
    return registry.to_json()


def registry_to_csv(registry: BaselineRegistry) -> str:
    """Deterministic CSV over ledger timeline."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "entry_index",
            "event_kind",
            "timestamp",
            "scope_id",
            "candidate_id",
            "baseline_id",
            "artifact_fingerprint",
            "approval_fingerprint",
            "superseded_fingerprint",
            "registry_parent_fingerprint",
            "entry_fingerprint",
            "actor",
            "note",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in sorted(registry.ledger, key=lambda e: e.entry_index):
        writer.writerow(
            {
                "entry_index": entry.entry_index,
                "event_kind": entry.event_kind.value,
                "timestamp": entry.timestamp.isoformat(),
                "scope_id": entry.scope_id,
                "candidate_id": entry.candidate_id or "",
                "baseline_id": entry.baseline_id or "",
                "artifact_fingerprint": entry.artifact_fingerprint or "",
                "approval_fingerprint": entry.approval_fingerprint or "",
                "superseded_fingerprint": entry.superseded_fingerprint or "",
                "registry_parent_fingerprint": entry.registry_parent_fingerprint,
                "entry_fingerprint": entry.entry_fingerprint,
                "actor": entry.actor or "",
                "note": entry.note or "",
            }
        )
    return output.getvalue()


def candidates_to_csv(registry: BaselineRegistry) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "candidate_id",
            "scope_id",
            "artifact_fingerprint",
            "artifact_type",
            "schema_version",
            "evidence_standing",
            "source_standing",
            "allowed_evidence_standings",
            "regression_gate_policy",
            "created_at",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for cand in sorted(registry.candidates.values(), key=lambda c: c.candidate_id):
        writer.writerow(
            {
                "candidate_id": cand.candidate_id,
                "scope_id": cand.scope.scope_id,
                "artifact_fingerprint": cand.artifact_fingerprint,
                "artifact_type": cand.artifact_type.value,
                "schema_version": cand.schema_version,
                "evidence_standing": cand.evidence_standing.value,
                "source_standing": cand.source_standing.value,
                "allowed_evidence_standings": ",".join(
                    s.value for s in cand.scope.allowed_evidence_standings
                ),
                "regression_gate_policy": cand.regression_gate_policy,
                "created_at": cand.created_at.isoformat(),
            }
        )
    return output.getvalue()


def active_baselines_to_csv(registry: BaselineRegistry) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "baseline_id",
            "scope_id",
            "candidate_id",
            "artifact_fingerprint",
            "artifact_type",
            "evidence_standing",
            "source_standing",
            "allowed_evidence_standings",
            "approval_fingerprint",
            "effective_date",
            "superseded_baseline_fingerprint",
            "regression_gate_policy",
            "record_fingerprint",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for rec in sorted(registry.active_baselines.values(), key=lambda r: r.scope.scope_id):
        writer.writerow(
            {
                "baseline_id": rec.baseline_id,
                "scope_id": rec.scope.scope_id,
                "candidate_id": rec.candidate_id,
                "artifact_fingerprint": rec.artifact_fingerprint,
                "artifact_type": rec.artifact_type.value,
                "evidence_standing": rec.evidence_standing.value,
                "source_standing": rec.source_standing.value,
                "allowed_evidence_standings": ",".join(
                    s.value for s in rec.scope.allowed_evidence_standings
                ),
                "approval_fingerprint": rec.approval_fingerprint,
                "effective_date": rec.effective_date.isoformat(),
                "superseded_baseline_fingerprint": rec.superseded_baseline_fingerprint or "",
                "regression_gate_policy": rec.regression_gate_policy,
                "record_fingerprint": rec.record_fingerprint,
            }
        )
    return output.getvalue()


# ---------------------------------------------------------------------------
# Candidate registration
# ---------------------------------------------------------------------------


def build_candidate(
    *,
    candidate_id: str,
    scope: BaselineScope,
    artifact_fingerprint: str,
    artifact_type: str | object,
    schema_version: str,
    metric_contracts: list[str],
    cohort_definition: str,
    evidence_standing: str | object,
    source_standing: str | object,
    regression_gate_policy: str,
    limitations: str,
    clock: Callable[[], datetime] | None = None,
) -> BaselineCandidate:
    from traffictwin.baseline_registry.models import (
        BaselineArtifactType,
        BaselineEvidenceStanding,
        BaselineSourceStanding,
    )

    if isinstance(artifact_type, str):
        try:
            at = BaselineArtifactType(artifact_type)
        except ValueError as exc:
            raise ValueError(f"unsupported artifact_type: {artifact_type}") from exc
    else:
        at = artifact_type  # type: ignore[assignment]
    if isinstance(evidence_standing, str):
        try:
            ev = BaselineEvidenceStanding(evidence_standing)
        except ValueError as exc:
            raise ValueError(f"unsupported evidence_standing: {evidence_standing}") from exc
    else:
        ev = evidence_standing  # type: ignore[assignment]
    if isinstance(source_standing, str):
        try:
            ss = BaselineSourceStanding(source_standing)
        except ValueError as exc:
            raise ValueError(f"unsupported source_standing: {source_standing}") from exc
    else:
        ss = source_standing  # type: ignore[assignment]

    now = _now_or_fixed(clock)
    cand = BaselineCandidate(
        candidate_id=candidate_id,
        scope=scope,
        artifact_fingerprint=artifact_fingerprint,
        artifact_type=at,
        schema_version=schema_version,
        metric_contracts=metric_contracts,
        cohort_definition=cohort_definition,
        evidence_standing=ev,
        source_standing=ss,
        regression_gate_policy=regression_gate_policy,
        limitations=limitations,
        created_at=now,
    )
    return cand


def _scope_semantic_fingerprint(scope: BaselineScope) -> str:
    return scope.fingerprint()


def register_candidate(
    registry: BaselineRegistry,
    candidate: BaselineCandidate,
    *,
    actor: str | None = None,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> BaselineRegistry:
    """Append a candidate_registered event. Fail-closed on duplicates / policy drift."""
    if candidate.candidate_id in registry.candidates:
        raise ValueError(f"candidate_id {candidate.candidate_id!r} already registered")
    if len(registry.candidates) >= 500:
        raise ValueError("candidate limit reached")

    # Scope policy stability: if same scope_id already exists, require semantic fingerprint match
    existing_scopes: list[BaselineScope] = []
    for c in registry.candidates.values():
        if c.scope.scope_id == candidate.scope.scope_id:
            existing_scopes.append(c.scope)
    for rec in registry.active_baselines.values():
        if rec.scope.scope_id == candidate.scope.scope_id:
            existing_scopes.append(rec.scope)
    if existing_scopes:
        expected_fp = _scope_semantic_fingerprint(existing_scopes[0])
        cand_fp = _scope_semantic_fingerprint(candidate.scope)
        if cand_fp != expected_fp:
            raise ValueError(
                f"scope_id {candidate.scope.scope_id!r} already exists with different policy; "
                f"use a new/versioned scope_id for policy change"
            )
        # Also ensure all existing scopes with same id have same fingerprint
        for s in existing_scopes[1:]:
            if _scope_semantic_fingerprint(s) != expected_fp:
                raise ValueError("inconsistent scope policy already in registry")

    now = _now_or_fixed(clock)
    parent_fp = registry.registry_fingerprint
    entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry),
        event_kind=BaselineLedgerEventKind.CANDIDATE_REGISTERED,
        timestamp=now,
        scope_id=candidate.scope.scope_id,
        candidate_id=candidate.candidate_id,
        baseline_id=None,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=None,
        superseded_fingerprint=None,
        registry_parent_fingerprint=parent_fp,
        actor=actor,
        note=note,
    )

    new_candidates = dict(registry.candidates)
    new_candidates[candidate.candidate_id] = candidate
    new_ledger = list(registry.ledger)
    new_ledger.append(entry)

    new_registry = registry.model_copy(update={"candidates": new_candidates, "ledger": new_ledger})
    new_fp = new_registry.compute_fingerprint()
    return new_registry.model_copy(update={"registry_fingerprint": new_fp})


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


def approve_candidate(
    registry: BaselineRegistry,
    *,
    candidate_id: str,
    approver: str,
    approval_note: str,
    actor: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[BaselineRegistry, BaselineApproval]:
    """Create an explicit approval for the exact candidate."""
    if candidate_id not in registry.candidates:
        raise ValueError(f"candidate {candidate_id!r} does not exist")
    candidate = registry.candidates[candidate_id]

    now = _now_or_fixed(clock)
    provisional = BaselineApproval(
        approval_id=f"approval-{candidate_id}",
        candidate_id=candidate_id,
        scope_id=candidate.scope.scope_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approver=approver,
        approval_note=approval_note,
        approved_at=now,
        approval_fingerprint="0" * 64,
    )
    fp = provisional.compute_fingerprint()
    approval = provisional.model_copy(update={"approval_fingerprint": fp})

    new_approvals = dict(registry.approvals)
    new_approvals[candidate_id] = approval

    parent_fp = registry.registry_fingerprint
    entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry),
        event_kind=BaselineLedgerEventKind.APPROVED,
        timestamp=now,
        scope_id=candidate.scope.scope_id,
        candidate_id=candidate_id,
        baseline_id=None,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=fp,
        superseded_fingerprint=None,
        registry_parent_fingerprint=parent_fp,
        actor=actor or approver,
        note=approval_note,
    )

    new_ledger = list(registry.ledger)
    new_ledger.append(entry)

    new_registry = registry.model_copy(update={"approvals": new_approvals, "ledger": new_ledger})
    new_fp = new_registry.compute_fingerprint()
    new_registry = new_registry.model_copy(update={"registry_fingerprint": new_fp})
    return new_registry, approval


# ---------------------------------------------------------------------------
# Helpers for restore history
# ---------------------------------------------------------------------------


def _previous_baseline_history_for_candidate(
    registry: BaselineRegistry, candidate_id: str, scope_id: str
) -> tuple[bool, str | None]:
    """Return (was_previously_active, superseded_reason).

    Checks ledger for a prior PROMOTED or RESTORED_AS_NEW_PROMOTION for this candidate/scope
    that was later superseded (i.e., a SUPERSEDED event for that baseline exists).
    """
    # Find promotion events for candidate
    promotion_events = [
        e
        for e in registry.ledger
        if e.candidate_id == candidate_id
        and e.scope_id == scope_id
        and e.event_kind
        in (BaselineLedgerEventKind.PROMOTED, BaselineLedgerEventKind.RESTORED_AS_NEW_PROMOTION)
        and e.baseline_id is not None
    ]
    if not promotion_events:
        return False, "candidate was never previously promoted in this scope"

    # For each promotion, check if its baseline was later superseded
    for prom in promotion_events:
        baseline_id = prom.baseline_id
        # Look for SUPERSEDED event that points at this baseline (old baseline being superseded)
        superseded_events = [
            e
            for e in registry.ledger
            if e.event_kind == BaselineLedgerEventKind.SUPERSEDED
            and e.baseline_id == baseline_id
            and e.scope_id == scope_id
        ]
        if superseded_events:
            return True, None
        # Also check if baseline is not currently active but was superseded
        # If candidate is not currently active, and there is a superseded event after promotion
        # Simpler: if candidate not active and promotion exists, and superseded event
        # But to be precise, we require explicit superseded event for that baseline.
        # If not superseded, then candidate is still active or was never superseded.
        # If promotion exists but no superseded, then it might still be active.
        # For now, only superseded history counts.
    return False, "candidate has no superseded prior baseline in this scope"


def _is_restorable_candidate(registry: BaselineRegistry, candidate_id: str, scope_id: str) -> bool:
    ok, _ = _previous_baseline_history_for_candidate(registry, candidate_id, scope_id)
    return ok


def list_restorable_candidates(registry: BaselineRegistry, scope_id: str) -> list[str]:
    """Return candidate_ids that are restorable in the given scope."""
    restorable: list[str] = []
    for cand_id, cand in registry.candidates.items():
        if cand.scope.scope_id != scope_id:
            continue
        if _is_restorable_candidate(registry, cand_id, scope_id):
            # Also candidate not already active
            active = registry.active_baselines.get(scope_id)
            if active is not None and active.candidate_id == cand_id:
                continue
            restorable.append(cand_id)
    return sorted(restorable)


# ---------------------------------------------------------------------------
# Authoritative promotion gate
# ---------------------------------------------------------------------------


def _audit_promotion_gate(
    registry: BaselineRegistry,
    request: BaselinePromotionRequest,
    candidate: BaselineCandidate | None,
    approval: BaselineApproval | None,
) -> BaselineCompatibilityAudit:
    findings: list[str] = []

    # Determine candidate existence first
    if candidate is None:
        # All other checks false when missing
        audit = BaselineCompatibilityAudit(
            candidate_id=request.candidate_id,
            scope_id=request.scope_id,
            artifact_fingerprint_verified=False,
            scope_compatible=False,
            evidence_policy_satisfied=False,
            source_standing_satisfied=False,
            approval_binds=False,
            no_stale_parent=(request.registry_parent_fingerprint == registry.registry_fingerprint),
            operation_preconditions_satisfied=False,
            findings=[f"candidate {request.candidate_id!r} does not exist"],
            passed=False,
            audit_fingerprint="0" * 64,
        )
        return audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})

    # 1. artifact fingerprint verified
    artifact_verified = candidate.artifact_fingerprint == request.artifact_fingerprint
    if not artifact_verified:
        findings.append(
            f"artifact fingerprint mismatch: candidate {candidate.artifact_fingerprint[:12]}…"
        )

    # 2. scope compatible: request scope == candidate scope, cohort definitions match, scope policy stable  # noqa: E501
    scope_compatible = (
        request.scope_id == candidate.scope.scope_id
        and candidate.cohort_definition == candidate.scope.cohort_definition
    )
    if not scope_compatible:
        if request.scope_id != candidate.scope.scope_id:
            findings.append(
                f"request scope {request.scope_id!r} does not match candidate scope {candidate.scope.scope_id!r}"  # noqa: E501
            )
        else:
            findings.append("candidate cohort does not match scope cohort")

    # 3. evidence policy satisfied: candidate.evidence_standing in allowed, not UNAVAILABLE
    evidence_satisfied = (
        candidate.evidence_standing in candidate.scope.allowed_evidence_standings
        and candidate.evidence_standing.value != "unavailable"
    )
    if not evidence_satisfied:
        if candidate.evidence_standing.value == "unavailable":
            findings.append("evidence standing is unavailable")
        else:
            allowed = ", ".join(s.value for s in candidate.scope.allowed_evidence_standings)
            findings.append(
                f"evidence standing {candidate.evidence_standing.value!r} not in allowed {allowed!r}"  # noqa: E501
            )

    # 4. source standing satisfied: not UNAVAILABLE
    source_satisfied = candidate.source_standing.value != "unavailable"
    if not source_satisfied:
        findings.append("source standing is unavailable")

    # 5. approval binds
    approval_binds = False
    if approval is None:
        findings.append("no explicit approval exists for candidate")
    else:
        binds_candidate = approval.candidate_id == request.candidate_id
        binds_scope = approval.scope_id == request.scope_id == candidate.scope.scope_id
        binds_fingerprint = (
            approval.artifact_fingerprint
            == request.artifact_fingerprint
            == candidate.artifact_fingerprint
        )
        binds_approval_fp = approval.approval_fingerprint == request.approval_fingerprint
        approval_binds = binds_candidate and binds_scope and binds_fingerprint and binds_approval_fp
        if not binds_candidate:
            findings.append("approval candidate_id does not match request")
        if not binds_scope:
            findings.append("approval scope does not match request/candidate scope")
        if not binds_fingerprint:
            findings.append("approval artifact fingerprint does not match request/candidate")
        if not binds_approval_fp:
            findings.append("approval fingerprint mismatch")

    # 6. no stale parent
    no_stale_parent = request.registry_parent_fingerprint == registry.registry_fingerprint
    if not no_stale_parent:
        findings.append(
            f"stale parent registry: request {request.registry_parent_fingerprint[:12]}… != current {registry.registry_fingerprint[:12]}…"  # noqa: E501
        )

    # 7. operation preconditions
    op = request.operation
    active = registry.active_baselines.get(request.scope_id)
    operation_ok = False
    if op == BaselinePromotionOperation.PROMOTE:
        # No active baseline may exist
        if active is None:
            operation_ok = True
        else:
            findings.append(
                f"conflicting active baseline already exists in scope {request.scope_id!r}"
            )
    elif op == BaselinePromotionOperation.SUPERSEDE:
        if active is None:
            findings.append(f"no active baseline in scope {request.scope_id!r} to supersede")
        elif active.candidate_id == request.candidate_id:
            findings.append("supersede candidate is already active")
        else:
            operation_ok = True
    elif op == BaselinePromotionOperation.RESTORE:
        # Must have been previously active and superseded, not currently active, and approval etc already checked  # noqa: E501
        if active is None:
            findings.append("no active baseline in scope for restore to supersede")
        else:
            if active.candidate_id == request.candidate_id:
                findings.append("restore candidate is already active")
            else:
                was_active, reason = _previous_baseline_history_for_candidate(
                    registry, request.candidate_id, request.scope_id
                )
                if not was_active:
                    findings.append(
                        f"restore requires a previously active superseded candidate: {reason}"
                    )
                else:
                    operation_ok = True
    else:
        findings.append(f"unknown operation {op!r}")

    passed = bool(
        artifact_verified
        and scope_compatible
        and evidence_satisfied
        and source_satisfied
        and approval_binds
        and no_stale_parent
        and operation_ok
    )

    if passed:
        findings.append("all promotion gate checks passed")

    audit = BaselineCompatibilityAudit(
        candidate_id=request.candidate_id,
        scope_id=request.scope_id,
        artifact_fingerprint_verified=artifact_verified,
        scope_compatible=scope_compatible,
        evidence_policy_satisfied=evidence_satisfied,
        source_standing_satisfied=source_satisfied,
        approval_binds=approval_binds,
        no_stale_parent=no_stale_parent,
        operation_preconditions_satisfied=operation_ok,
        findings=findings,
        passed=passed,
        audit_fingerprint="0" * 64,
    )
    return audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})


# ---------------------------------------------------------------------------
# Promotion helpers
# ---------------------------------------------------------------------------


def _promotion_failure_receipt(
    request: BaselinePromotionRequest,
    audit: BaselineCompatibilityAudit,
    clock: Callable[[], datetime] | None,
) -> BaselinePromotionReceipt:
    now = _now_or_fixed(clock)
    receipt = BaselinePromotionReceipt(
        request=request,
        status=BaselineStatus.BLOCKED,
        promoted_record=None,
        blocked_reasons=list(audit.findings),
        audit=audit,
        receipt_fingerprint="0" * 64,
        created_at=now,
    )
    return receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})


def _build_promotion_record(
    candidate: BaselineCandidate,
    approval: BaselineApproval,
    superseded_fp: str | None,
    now: datetime,
) -> BaselineRecord:
    # Determine baseline_id: for promote/supersede, use baseline-{candidate_id}; for restore, use suffix to avoid clash  # noqa: E501
    baseline_id = f"baseline-{candidate.candidate_id}"
    # For restore, caller will adjust if needed to avoid id clash – but we keep deterministic
    # If baseline_id already exists historically, we append suffix via ledger length? Caller handles.  # noqa: E501
    provisional = BaselineRecord(
        baseline_id=baseline_id,
        scope=candidate.scope,
        artifact_fingerprint=candidate.artifact_fingerprint,
        artifact_type=candidate.artifact_type,
        schema_version=candidate.schema_version,
        metric_contracts=list(candidate.metric_contracts),
        cohort_definition=candidate.cohort_definition,
        evidence_standing=candidate.evidence_standing,
        source_standing=candidate.source_standing,
        approval_fingerprint=approval.approval_fingerprint,
        effective_date=now.date(),
        superseded_baseline_fingerprint=superseded_fp,
        regression_gate_policy=candidate.regression_gate_policy,
        limitations=candidate.limitations,
        candidate_id=candidate.candidate_id,
        status=BaselineStatus.ACTIVE,
        created_at=now,
        record_fingerprint="0" * 64,
    )
    fp = provisional.compute_fingerprint()
    return provisional.model_copy(update={"record_fingerprint": fp})


# ---------------------------------------------------------------------------
# Promotion (core)
# ---------------------------------------------------------------------------


def promote_baseline(
    registry: BaselineRegistry,
    request: BaselinePromotionRequest,
    *,
    clock: Callable[[], datetime] | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Try to promote a candidate. Fail-closed with BLOCKED receipt."""
    if request.operation != BaselinePromotionOperation.PROMOTE:
        # Operation mismatch is a blocked precondition
        candidate = registry.candidates.get(request.candidate_id)
        approval = registry.approvals.get(request.candidate_id)
        audit = _audit_promotion_gate(registry, request, candidate, approval)
        # Overwrite findings to indicate operation mismatch if not already
        if "unknown operation" not in " ".join(audit.findings):
            # Already handled by gate (scope mismatch etc), but ensure blocked
            pass
        return registry, _promotion_failure_receipt(request, audit, clock)

    candidate = registry.candidates.get(request.candidate_id)
    approval = registry.approvals.get(request.candidate_id)
    audit = _audit_promotion_gate(registry, request, candidate, approval)
    if not audit.passed:
        return registry, _promotion_failure_receipt(request, audit, clock)

    assert candidate is not None
    assert approval is not None
    now = _now_or_fixed(clock)
    # Superseded is None for promote (no active)
    record = _build_promotion_record(candidate, approval, None, now)

    parent_fp = registry.registry_fingerprint
    entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry),
        event_kind=BaselineLedgerEventKind.PROMOTED,
        timestamp=now,
        scope_id=candidate.scope.scope_id,
        candidate_id=candidate.candidate_id,
        baseline_id=record.baseline_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=record.approval_fingerprint,
        superseded_fingerprint=None,
        registry_parent_fingerprint=parent_fp,
        actor=request.requested_by,
        note="promoted",
    )

    new_active = dict(registry.active_baselines)
    new_active[candidate.scope.scope_id] = record
    new_ledger = list(registry.ledger)
    new_ledger.append(entry)

    new_registry = registry.model_copy(
        update={"active_baselines": new_active, "ledger": new_ledger}
    )
    new_fp = new_registry.compute_fingerprint()
    new_registry = new_registry.model_copy(update={"registry_fingerprint": new_fp})

    receipt = BaselinePromotionReceipt(
        request=request,
        status=BaselineStatus.ACTIVE,
        promoted_record=record,
        blocked_reasons=[],
        audit=audit,
        receipt_fingerprint="0" * 64,
        created_at=now,
    )
    receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
    return new_registry, receipt


# ---------------------------------------------------------------------------
# Supersession (core) – accepts typed request
# ---------------------------------------------------------------------------


def supersede_baseline(
    registry: BaselineRegistry,
    request: BaselinePromotionRequest | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    scope_id: str | None = None,
    superseding_candidate_id: str | None = None,
    actor: str | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Supersede the active baseline in a scope with a new candidate via request.

    Supports both new request-based and legacy compat signatures.
    """
    # Legacy compat dispatch
    if request is None and scope_id is not None and superseding_candidate_id is not None:
        return supersede_baseline_compat(
            registry,
            scope_id=scope_id,
            superseding_candidate_id=superseding_candidate_id,
            actor=actor or "operator",
            clock=clock,
        )
    if request is None:
        raise TypeError(
            "supersede_baseline requires either request or scope_id/superseding_candidate_id"
        )
    assert isinstance(request, BaselinePromotionRequest)
    if request.operation != BaselinePromotionOperation.SUPERSEDE:
        candidate = registry.candidates.get(request.candidate_id)
        approval = registry.approvals.get(request.candidate_id)
        audit = _audit_promotion_gate(registry, request, candidate, approval)
        return registry, _promotion_failure_receipt(request, audit, clock)

    candidate = registry.candidates.get(request.candidate_id)
    approval = registry.approvals.get(request.candidate_id)
    audit = _audit_promotion_gate(registry, request, candidate, approval)
    if not audit.passed:
        return registry, _promotion_failure_receipt(request, audit, clock)

    assert candidate is not None
    assert approval is not None
    now = _now_or_fixed(clock)
    active_record = registry.active_baselines.get(request.scope_id)
    assert active_record is not None  # gate ensures

    superseded_fp = active_record.record_fingerprint
    record = _build_promotion_record(candidate, approval, superseded_fp, now)
    # Ensure baseline_id uniqueness if already exists historically
    # If baseline_id collides with existing ledger baseline_id, suffix with ledger length
    existing_ids = {e.baseline_id for e in registry.ledger if e.baseline_id}
    if record.baseline_id in existing_ids:
        record = record.model_copy(
            update={"baseline_id": f"{record.baseline_id}-{len(registry.ledger)}"}
        )
        record = record.model_copy(update={"record_fingerprint": record.compute_fingerprint()})

    parent_fp = registry.registry_fingerprint
    # SUPERSEDED entry describes OLD active record
    superseded_entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry),
        event_kind=BaselineLedgerEventKind.SUPERSEDED,
        timestamp=now,
        scope_id=request.scope_id,
        candidate_id=active_record.candidate_id,
        baseline_id=active_record.baseline_id,
        artifact_fingerprint=active_record.artifact_fingerprint,
        approval_fingerprint=active_record.approval_fingerprint,
        superseded_fingerprint=superseded_fp,
        registry_parent_fingerprint=parent_fp,
        actor=request.requested_by,
        note=f"superseded {active_record.baseline_id}",
    )
    interim_registry = registry.model_copy(
        update={"ledger": list(registry.ledger) + [superseded_entry]}
    )
    interim_fp = interim_registry.compute_fingerprint()

    promoted_entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry) + 1,
        event_kind=BaselineLedgerEventKind.PROMOTED,
        timestamp=now,
        scope_id=request.scope_id,
        candidate_id=candidate.candidate_id,
        baseline_id=record.baseline_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=record.approval_fingerprint,
        superseded_fingerprint=superseded_fp,
        registry_parent_fingerprint=interim_fp,
        actor=request.requested_by,
        note=f"superseding promotion {record.baseline_id}",
    )

    new_active = dict(registry.active_baselines)
    new_active[request.scope_id] = record
    new_ledger = list(registry.ledger) + [superseded_entry, promoted_entry]

    new_registry = registry.model_copy(
        update={"active_baselines": new_active, "ledger": new_ledger}
    )
    new_fp = new_registry.compute_fingerprint()
    new_registry = new_registry.model_copy(update={"registry_fingerprint": new_fp})

    receipt = BaselinePromotionReceipt(
        request=request,
        status=BaselineStatus.ACTIVE,
        promoted_record=record,
        blocked_reasons=[],
        audit=audit,
        receipt_fingerprint="0" * 64,
        created_at=now,
    )
    receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
    return new_registry, receipt


def supersede_baseline_compat(
    registry: BaselineRegistry,
    *,
    scope_id: str,
    superseding_candidate_id: str,
    actor: str,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Compat wrapper that builds a SUPERSEDE request from legacy args."""
    candidate = registry.candidates.get(superseding_candidate_id)
    approval = registry.approvals.get(superseding_candidate_id)
    now = _now_or_fixed(clock)
    if candidate is None:
        req = BaselinePromotionRequest(
            candidate_id=superseding_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint="0" * 64,
            approval_fingerprint="0" * 64,
            registry_parent_fingerprint=registry.registry_fingerprint,
            requested_by=actor,
            requested_at=now,
            operation=BaselinePromotionOperation.SUPERSEDE,
        )
        audit = _audit_promotion_gate(registry, req, None, None)
        return registry, _promotion_failure_receipt(req, audit, clock)
    art_fp = candidate.artifact_fingerprint
    appr_fp = approval.approval_fingerprint if approval else "0" * 64
    req = BaselinePromotionRequest(
        candidate_id=superseding_candidate_id,
        scope_id=scope_id,
        artifact_fingerprint=art_fp,
        approval_fingerprint=appr_fp,
        registry_parent_fingerprint=registry.registry_fingerprint,
        requested_by=actor,
        requested_at=now,
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    return supersede_baseline(registry, req, clock=clock)


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------


def withdraw_candidate(
    registry: BaselineRegistry,
    *,
    candidate_id: str,
    actor: str,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> BaselineRegistry:
    """Mark a candidate as withdrawn via ledger event."""
    if candidate_id not in registry.candidates:
        raise ValueError(f"candidate {candidate_id!r} does not exist")
    candidate = registry.candidates[candidate_id]
    now = _now_or_fixed(clock)
    parent_fp = registry.registry_fingerprint
    entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry),
        event_kind=BaselineLedgerEventKind.WITHDRAWN,
        timestamp=now,
        scope_id=candidate.scope.scope_id,
        candidate_id=candidate_id,
        baseline_id=None,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=None,
        superseded_fingerprint=None,
        registry_parent_fingerprint=parent_fp,
        actor=actor,
        note=note,
    )
    new_ledger = list(registry.ledger) + [entry]
    new_registry = registry.model_copy(update={"ledger": new_ledger})
    new_fp = new_registry.compute_fingerprint()
    return new_registry.model_copy(update={"registry_fingerprint": new_fp})


# ---------------------------------------------------------------------------
# Restore as new promotion (rollback via new event) – core uses same gate
# ---------------------------------------------------------------------------


def restore_baseline_as_new_promotion(
    registry: BaselineRegistry,
    request: BaselinePromotionRequest | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    scope_id: str | None = None,
    restore_candidate_id: str | None = None,
    actor: str | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Promote a previously superseded candidate as a new promotion event.

    Supports both new request-based and legacy compat signatures.
    """
    if request is None and scope_id is not None and restore_candidate_id is not None:
        return restore_baseline_as_new_promotion_compat(
            registry,
            scope_id=scope_id,
            restore_candidate_id=restore_candidate_id,
            actor=actor or "operator",
            clock=clock,
        )
    if request is None:
        raise TypeError("restore requires either request or scope_id/restore_candidate_id")
    assert isinstance(request, BaselinePromotionRequest)
    if request.operation != BaselinePromotionOperation.RESTORE:
        candidate = registry.candidates.get(request.candidate_id)
        approval = registry.approvals.get(request.candidate_id)
        audit = _audit_promotion_gate(registry, request, candidate, approval)
        return registry, _promotion_failure_receipt(request, audit, clock)

    candidate = registry.candidates.get(request.candidate_id)
    approval = registry.approvals.get(request.candidate_id)
    audit = _audit_promotion_gate(registry, request, candidate, approval)
    if not audit.passed:
        return registry, _promotion_failure_receipt(request, audit, clock)

    assert candidate is not None
    assert approval is not None
    now = _now_or_fixed(clock)
    active = registry.active_baselines.get(request.scope_id)
    # gate already ensured active exists and restore history ok; but double-check
    superseded_fp = active.record_fingerprint if active else None

    # Build new record with unique baseline_id to avoid clash
    provisional_id = f"baseline-{candidate.candidate_id}-restore-{len(registry.ledger)}"
    provisional = BaselineRecord(
        baseline_id=provisional_id,
        scope=candidate.scope,
        artifact_fingerprint=candidate.artifact_fingerprint,
        artifact_type=candidate.artifact_type,
        schema_version=candidate.schema_version,
        metric_contracts=list(candidate.metric_contracts),
        cohort_definition=candidate.cohort_definition,
        evidence_standing=candidate.evidence_standing,
        source_standing=candidate.source_standing,
        approval_fingerprint=approval.approval_fingerprint,
        effective_date=now.date(),
        superseded_baseline_fingerprint=superseded_fp,
        regression_gate_policy=candidate.regression_gate_policy,
        limitations=candidate.limitations,
        candidate_id=candidate.candidate_id,
        status=BaselineStatus.ACTIVE,
        created_at=now,
        record_fingerprint="0" * 64,
    )
    record_fp = provisional.compute_fingerprint()
    record = provisional.model_copy(update={"record_fingerprint": record_fp})

    new_ledger = list(registry.ledger)
    parent_fp = registry.registry_fingerprint

    if active is not None:
        superseded_entry = _build_ledger_entry(
            entry_index=len(new_ledger),
            event_kind=BaselineLedgerEventKind.SUPERSEDED,
            timestamp=now,
            scope_id=request.scope_id,
            candidate_id=active.candidate_id,
            baseline_id=active.baseline_id,
            artifact_fingerprint=active.artifact_fingerprint,
            approval_fingerprint=active.approval_fingerprint,
            superseded_fingerprint=superseded_fp,
            registry_parent_fingerprint=parent_fp,
            actor=request.requested_by,
            note=f"superseded for restore {record.baseline_id}",
        )
        new_ledger.append(superseded_entry)
        interim_registry = registry.model_copy(update={"ledger": new_ledger})
        parent_fp = interim_registry.compute_fingerprint()

    restore_entry = _build_ledger_entry(
        entry_index=len(new_ledger),
        event_kind=BaselineLedgerEventKind.RESTORED_AS_NEW_PROMOTION,
        timestamp=now,
        scope_id=request.scope_id,
        candidate_id=candidate.candidate_id,
        baseline_id=record.baseline_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=approval.approval_fingerprint,
        superseded_fingerprint=superseded_fp,
        registry_parent_fingerprint=parent_fp,
        actor=request.requested_by,
        note=f"restored {request.candidate_id}",
    )
    new_ledger.append(restore_entry)

    new_active = dict(registry.active_baselines)
    new_active[request.scope_id] = record

    new_registry = registry.model_copy(
        update={"active_baselines": new_active, "ledger": new_ledger}
    )
    new_fp = new_registry.compute_fingerprint()
    new_registry = new_registry.model_copy(update={"registry_fingerprint": new_fp})

    receipt = BaselinePromotionReceipt(
        request=request,
        status=BaselineStatus.ACTIVE,
        promoted_record=record,
        blocked_reasons=[],
        audit=audit,
        receipt_fingerprint="0" * 64,
        created_at=now,
    )
    receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
    return new_registry, receipt


def restore_baseline_as_new_promotion_compat(
    registry: BaselineRegistry,
    *,
    scope_id: str,
    restore_candidate_id: str,
    actor: str,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Compat wrapper for restore that builds request."""
    candidate = registry.candidates.get(restore_candidate_id)
    approval = registry.approvals.get(restore_candidate_id)
    now = _now_or_fixed(clock)
    if candidate is None:
        req = BaselinePromotionRequest(
            candidate_id=restore_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint="0" * 64,
            approval_fingerprint="0" * 64,
            registry_parent_fingerprint=registry.registry_fingerprint,
            requested_by=actor,
            requested_at=now,
            operation=BaselinePromotionOperation.RESTORE,
        )
        audit = _audit_promotion_gate(registry, req, None, None)
        return registry, _promotion_failure_receipt(req, audit, clock)
    # Scope mismatch will be caught by gate as scope_compatible false
    art_fp = candidate.artifact_fingerprint
    appr_fp = approval.approval_fingerprint if approval else "0" * 64
    req = BaselinePromotionRequest(
        candidate_id=restore_candidate_id,
        scope_id=scope_id,
        artifact_fingerprint=art_fp,
        approval_fingerprint=appr_fp,
        registry_parent_fingerprint=registry.registry_fingerprint,
        requested_by=actor,
        requested_at=now,
        operation=BaselinePromotionOperation.RESTORE,
    )
    return restore_baseline_as_new_promotion(registry, req, clock=clock)


# Backwards compat aliases for old API names
def _legacy_supersede_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN202,ANN002,ANN003
    return supersede_baseline_compat(*args, **kwargs)


# ---------------------------------------------------------------------------
# Show / Export helpers
# ---------------------------------------------------------------------------


def show_registry_summary(registry: BaselineRegistry) -> dict[str, object]:
    return {
        "schema_version": registry.schema_version,
        "registry_fingerprint": registry.registry_fingerprint,
        "candidate_count": len(registry.candidates),
        "active_count": len(registry.active_baselines),
        "ledger_count": len(registry.ledger),
        "limitations": registry_limitations(),
    }


def export_registry_json(registry: BaselineRegistry) -> str:
    return registry.to_json()


def export_registry_csv(registry: BaselineRegistry) -> str:
    return registry_to_csv(registry)
