"""Deterministic service for Baseline Registry — append-only ledger and promotion gates."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime

from traffictwin.baseline_registry.models import (
    BASELINE_SCHEMA_VERSION,
    BaselineApproval,
    BaselineCandidate,
    BaselineCompatibilityAudit,
    BaselineLedgerEntry,
    BaselineLedgerEventKind,
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
    "Promotion requires an explicit approval binding the exact candidate "  # noqa: E501
    "and scope; the newest candidate is never promoted automatically.",
    "Rollback is represented only by promoting a previous candidate "  # noqa: E501
    "through a new ledger event; historical records are never edited.",
    "Evidence and source standing are declared and checked at "  # noqa: E501
    "promotion; synthetic evidence is never relabelled as observed.",
    "Regression-gate policy is declared per baseline; this registry "  # noqa: E501
    "does not claim causality, optimality, or production readiness.",
    "Portable exports exclude local paths, retrieval clocks, and "  # noqa: E501
    "secrets; fingerprints use deterministic canonical JSON.",
]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")


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
    # Compute fingerprint over payload without registry_fingerprint
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


def _recompute_registry_fingerprint(registry: BaselineRegistry) -> str:
    return registry.compute_fingerprint()


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


def _validate_no_path(value: str | None, field_name: str) -> None:
    if value is None:
        return
    # reuse helper from models – simple check for absolute path markers
    if "://" in value or (value.startswith("/") and "/" in value[1:]):
        # crude – but model validators already enforce; keep fail-closed
        raise ValueError(f"{field_name} must not contain absolute paths")


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

    # Coerce enums fail-closed
    try:
        at = (
            BaselineArtifactType(artifact_type) if isinstance(artifact_type, str) else artifact_type
        )
    except ValueError as exc:
        raise ValueError(f"unsupported artifact_type: {artifact_type}") from exc
    try:
        ev = (
            BaselineEvidenceStanding(evidence_standing)
            if isinstance(evidence_standing, str)
            else evidence_standing
        )
    except ValueError as exc:
        raise ValueError(f"unsupported evidence_standing: {evidence_standing}") from exc
    try:
        ss = (
            BaselineSourceStanding(source_standing)
            if isinstance(source_standing, str)
            else source_standing
        )
    except ValueError as exc:
        raise ValueError(f"unsupported source_standing: {source_standing}") from exc

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


def register_candidate(
    registry: BaselineRegistry,
    candidate: BaselineCandidate,
    *,
    actor: str | None = None,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> BaselineRegistry:
    """Append a candidate_registered event. Fail-closed on duplicates / bounds."""
    if candidate.candidate_id in registry.candidates:
        raise ValueError(f"candidate_id {candidate.candidate_id!r} already registered")

    # Enforce bounded candidates
    if len(registry.candidates) >= 500:
        raise ValueError("candidate limit reached")

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
    # Approval binds exact candidate fingerprint and scope
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

    # Check no stale parent? approvals are new, but we check registry fingerprint binds.
    # Store approval – overwrite if exists? For explicit review, allow re-approval but ledger keeps history.  # noqa: E501
    # We treat approvals dict as last approval per candidate, but ledger tracks all.
    new_approvals = dict(registry.approvals)
    # If already approved with different fingerprint, treat as new promotion? Keep latest.
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
# Compatibility audit
# ---------------------------------------------------------------------------


def _audit_promotion_gate(
    registry: BaselineRegistry,
    request: BaselinePromotionRequest,
    candidate: BaselineCandidate,
    approval: BaselineApproval | None,
) -> BaselineCompatibilityAudit:
    findings: list[str] = []

    # 1. candidate exists – already checked caller ensures
    # 2. exact artifact fingerprint verified
    artifact_verified = candidate.artifact_fingerprint == request.artifact_fingerprint
    if not artifact_verified:
        findings.append(
            f"artifact fingerprint mismatch: candidate {candidate.artifact_fingerprint[:12]}… != request {request.artifact_fingerprint[:12]}…"  # noqa: E501
        )

    # 3. compatibility audit passes – for baseline registry, compatibility means
    #    metric contracts, cohort, schema etc are internally consistent and
    #    candidate's standing satisfies policy? We'll define compatibility_passed as
    #    artifact_verified and no absolute path contamination (already validated) and
    #    metric contracts non-empty or allowed.
    compatibility_passed = artifact_verified and len(candidate.metric_contracts) <= 64
    if not compatibility_passed and artifact_verified:
        findings.append("compatibility check failed for candidate contracts")

    # 4. evidence standing satisfies declared baseline policy
    # Policy is a string; we interpret "requires admitted" etc. Fail-closed:
    # if policy contains "admitted" then evidence_standing must be admitted.
    # For now, allow any standing except UNAVAILABLE; but if policy says "admitted"
    # then require admitted.
    policy = candidate.regression_gate_policy.lower()
    evidence_satisfied = True
    if "admitted" in policy and candidate.evidence_standing.value != "admitted_research":
        evidence_satisfied = False
        findings.append(
            f"evidence standing {candidate.evidence_standing.value!r} does not satisfy policy requiring admitted"  # noqa: E501
        )
    if (
        candidate.evidence_standing.value == "unavailable"
        or candidate.source_standing.value == "unavailable"
    ):
        evidence_satisfied = False
        findings.append("evidence or source standing is unavailable")

    # 5 & 6. explicit approval exists and binds exact candidate and scope + fingerprint
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
        # Approval must bind exact candidate and scope
        approval_binds = binds_candidate and binds_scope and binds_fingerprint and binds_approval_fp
        if not binds_candidate:
            findings.append("approval candidate_id does not match request")
        if not binds_scope:
            findings.append("approval scope does not match request/candidate scope")
        if not binds_fingerprint:
            findings.append("approval artifact fingerprint does not match request/candidate")
        if not binds_approval_fp:
            findings.append("approval fingerprint mismatch")
        # Also check stale approval: approval must be for current candidate fingerprint, not older
        # If candidate fingerprint changed after approval, this already fails binds_fingerprint.

    # 7. no stale parent registry
    no_stale_parent = request.registry_parent_fingerprint == registry.registry_fingerprint
    if not no_stale_parent:
        findings.append(
            f"stale parent registry: request {request.registry_parent_fingerprint[:12]}… != current {registry.registry_fingerprint[:12]}…"  # noqa: E501
        )

    # 8. no conflicting active baseline in same scope – but promotion will supersede active if exists.  # noqa: E501
    # Conflict means there is active baseline in same scope and promotion is not superseding? We treat  # noqa: E501
    # as blocked if active exists and request does not supersede? Actually spec says "no conflicting active baseline in the same scope."  # noqa: E501
    # For initial promotion, conflict if active already exists in that scope (duplicate active scope refusal)  # noqa: E501
    # So we block if active exists for that scope – supersession should go through supersede path, not promote?  # noqa: E501
    # However supersede is logically a promotion that replaces active; we allow promotion to replace active but must record superseded fingerprint.  # noqa: E501
    # To satisfy duplicate active refusal test, we need to block a second promote without supersede.
    # We'll define no_conflicting_active = True if no active in scope, OR if active exists but promotion is intended to supersede (i.e., we will record superseded). But spec lists superseded as separate event, so promote should be blocked if active exists.  # noqa: E501
    # For simplicity: no_conflicting_active = (request.scope_id not in registry.active_baselines)
    # If active exists, gate fails. The supersede function will handle replacing active via its own gate but also checks same.  # noqa: E501
    # We'll allow promote to supersede if caller uses supersede path; for direct promote we block.
    # However to support supersession test, supersede function will allow replacement.
    # So for promote gate, conflicting active = False if active exists.
    no_conflicting_active = request.scope_id not in registry.active_baselines
    if not no_conflicting_active:
        findings.append(f"conflicting active baseline already exists in scope {request.scope_id!r}")

    passed = bool(
        artifact_verified
        and compatibility_passed
        and evidence_satisfied
        and approval_binds
        and no_stale_parent
        and no_conflicting_active
    )

    if passed:
        findings.append("all promotion gate checks passed")

    provisional = BaselineCompatibilityAudit(
        candidate_id=request.candidate_id,
        scope_id=request.scope_id,
        artifact_fingerprint_verified=artifact_verified,
        compatibility_passed=compatibility_passed,
        evidence_policy_satisfied=evidence_satisfied,
        approval_binds=approval_binds,
        no_stale_parent=no_stale_parent,
        no_conflicting_active=no_conflicting_active,
        findings=findings,
        passed=passed,
        audit_fingerprint="0" * 64,
    )
    fp = provisional.compute_fingerprint()
    return provisional.model_copy(update={"audit_fingerprint": fp})


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


def promote_baseline(
    registry: BaselineRegistry,
    request: BaselinePromotionRequest,
    *,
    clock: Callable[[], datetime] | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Try to promote a candidate. Fail-closed with blocked receipt on any gate failure."""
    now = _now_or_fixed(clock)

    # Verify candidate exists
    candidate = registry.candidates.get(request.candidate_id)
    if candidate is None:
        audit = BaselineCompatibilityAudit(
            candidate_id=request.candidate_id,
            scope_id=request.scope_id,
            artifact_fingerprint_verified=False,
            compatibility_passed=False,
            evidence_policy_satisfied=False,
            approval_binds=False,
            no_stale_parent=(request.registry_parent_fingerprint == registry.registry_fingerprint),
            no_conflicting_active=(request.scope_id not in registry.active_baselines),
            findings=[f"candidate {request.candidate_id!r} does not exist"],
            passed=False,
            audit_fingerprint="0" * 64,
        )
        audit = audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})
        receipt = BaselinePromotionReceipt(
            request=request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    # Fetch approval (exact)
    approval = registry.approvals.get(request.candidate_id)

    audit = _audit_promotion_gate(registry, request, candidate, approval)

    if not audit.passed:
        receipt = BaselinePromotionReceipt(
            request=request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    # Gate passed – create BaselineRecord
    # Superseded fingerprint is previous active's record fingerprint if any, else None (but gate ensures no active, so None)  # noqa: E501
    superseded_fp = None
    # Since promotion gate blocked if active exists, superseded is None for promote.
    # For supersede path, we handle separately.

    # Build record fingerprint via provisional
    provisional_record = BaselineRecord(
        baseline_id=f"baseline-{candidate.candidate_id}",
        scope=candidate.scope,
        artifact_fingerprint=candidate.artifact_fingerprint,
        artifact_type=candidate.artifact_type,
        schema_version=candidate.schema_version,
        metric_contracts=list(candidate.metric_contracts),
        cohort_definition=candidate.cohort_definition,
        evidence_standing=candidate.evidence_standing,
        source_standing=candidate.source_standing,
        approval_fingerprint=approval.approval_fingerprint
        if approval
        else request.approval_fingerprint,
        effective_date=now.date(),
        superseded_baseline_fingerprint=superseded_fp,
        regression_gate_policy=candidate.regression_gate_policy,
        limitations=candidate.limitations,
        candidate_id=candidate.candidate_id,
        status=BaselineStatus.ACTIVE,
        created_at=now,
        record_fingerprint="0" * 64,
    )
    record_fp = provisional_record.compute_fingerprint()
    record = provisional_record.model_copy(update={"record_fingerprint": record_fp})

    # Append promotion ledger entry
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
        superseded_fingerprint=superseded_fp,
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
    new_registry_fp = new_registry.compute_fingerprint()
    new_registry = new_registry.model_copy(update={"registry_fingerprint": new_registry_fp})

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
# Supersession
# ---------------------------------------------------------------------------


def supersede_baseline(
    registry: BaselineRegistry,
    *,
    scope_id: str,
    superseding_candidate_id: str,
    actor: str,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Supersede the active baseline in a scope with a new candidate.

    This is a promotion that replaces an existing active baseline. The old
    active's fingerprint is recorded as superseded_baseline_fingerprint and
    a SUPERSEDED ledger entry plus PROMOTED entry are appended (two events
    or one combined superseded+promoted? We model as one PROMOTED with
    superseded fingerprint plus a SUPERSEDED marker entry for audit).

    For append-only invariant, we never mutate the old record – we mark it
    superseded via a ledger event and insert the new active record.
    """
    now = _now_or_fixed(clock)

    if scope_id not in registry.active_baselines:
        # No active to supersede – treat as blocked
        dummy_request = BaselinePromotionRequest(
            candidate_id=superseding_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint="0" * 64,
            approval_fingerprint="0" * 64,
            registry_parent_fingerprint=registry.registry_fingerprint,
            requested_by=actor,
            requested_at=now,
        )
        audit = BaselineCompatibilityAudit(
            candidate_id=superseding_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint_verified=False,
            compatibility_passed=False,
            evidence_policy_satisfied=False,
            approval_binds=False,
            no_stale_parent=True,
            no_conflicting_active=False,
            findings=[f"no active baseline in scope {scope_id!r} to supersede"],
            passed=False,
            audit_fingerprint="0" * 64,
        )
        audit = audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})
        receipt = BaselinePromotionReceipt(
            request=dummy_request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    if superseding_candidate_id not in registry.candidates:
        dummy_request = BaselinePromotionRequest(
            candidate_id=superseding_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint="0" * 64,
            approval_fingerprint="0" * 64,
            registry_parent_fingerprint=registry.registry_fingerprint,
            requested_by=actor,
            requested_at=now,
        )
        audit = BaselineCompatibilityAudit(
            candidate_id=superseding_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint_verified=False,
            compatibility_passed=False,
            evidence_policy_satisfied=False,
            approval_binds=False,
            no_stale_parent=True,
            no_conflicting_active=False,
            findings=[f"superseding candidate {superseding_candidate_id!r} does not exist"],
            passed=False,
            audit_fingerprint="0" * 64,
        )
        audit = audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})
        receipt = BaselinePromotionReceipt(
            request=dummy_request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    candidate = registry.candidates[superseding_candidate_id]
    if candidate.scope.scope_id != scope_id:
        dummy_request = BaselinePromotionRequest(
            candidate_id=superseding_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint=candidate.artifact_fingerprint,
            approval_fingerprint=registry.approvals.get(
                superseding_candidate_id, candidate
            ).artifact_fingerprint
            if isinstance(registry.approvals.get(superseding_candidate_id), BaselineApproval)
            else "0" * 64,
            registry_parent_fingerprint=registry.registry_fingerprint,
            requested_by=actor,
            requested_at=now,
        )
        # Use actual approval fingerprint if available
        approval_fp = (
            registry.approvals[superseding_candidate_id].approval_fingerprint
            if superseding_candidate_id in registry.approvals
            else "0" * 64
        )
        dummy_request = dummy_request.model_copy(update={"approval_fingerprint": approval_fp})
        audit = BaselineCompatibilityAudit(
            candidate_id=superseding_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint_verified=False,
            compatibility_passed=False,
            evidence_policy_satisfied=False,
            approval_binds=False,
            no_stale_parent=True,
            no_conflicting_active=False,
            findings=[
                f"candidate scope {candidate.scope.scope_id!r} does not match supersede scope {scope_id!r}"  # noqa: E501
            ],
            passed=False,
            audit_fingerprint="0" * 64,
        )
        audit = audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})
        receipt = BaselinePromotionReceipt(
            request=dummy_request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    approval = registry.approvals.get(superseding_candidate_id)
    active_record = registry.active_baselines[scope_id]

    # Build request that would pass the promotion gate except for conflicting active – for supersede we need a relaxed check  # noqa: E501
    # So we perform a dedicated supersede audit where no_conflicting_active is allowed to be False but we treat it as ok if superseding.  # noqa: E501
    # We'll reuse _audit_promotion_gate but override its no_conflicting_active logic for supersede.

    request = BaselinePromotionRequest(
        candidate_id=superseding_candidate_id,
        scope_id=scope_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=approval.approval_fingerprint if approval else "0" * 64,
        registry_parent_fingerprint=registry.registry_fingerprint,
        requested_by=actor,
        requested_at=now,
    )

    # Run gate but allow active conflict – compute audit manually for supersede
    findings: list[str] = []
    artifact_verified = candidate.artifact_fingerprint == request.artifact_fingerprint
    if not artifact_verified:
        findings.append("artifact fingerprint mismatch for supersede")

    compatibility_passed = artifact_verified and len(candidate.metric_contracts) <= 64
    evidence_satisfied = True
    if (
        "admitted" in candidate.regression_gate_policy.lower()
        and candidate.evidence_standing.value != "admitted_research"
    ):
        evidence_satisfied = False
        findings.append(
            "evidence standing does not satisfy policy requiring admitted for supersede"
        )
    if (
        candidate.evidence_standing.value == "unavailable"
        or candidate.source_standing.value == "unavailable"
    ):
        evidence_satisfied = False
        findings.append("evidence or source standing is unavailable for supersede")

    approval_binds = False
    if approval is None:
        findings.append("no explicit approval for superseding candidate")
    else:
        approval_binds = (
            approval.candidate_id == request.candidate_id
            and approval.scope_id == request.scope_id
            and approval.artifact_fingerprint == request.artifact_fingerprint
            and approval.approval_fingerprint == request.approval_fingerprint
        )
        if not approval_binds:
            findings.append(
                "approval does not bind exact candidate/scope/fingerprint for supersede"
            )

    no_stale_parent = request.registry_parent_fingerprint == registry.registry_fingerprint
    if not no_stale_parent:
        findings.append("stale parent registry for supersede")

    # For supersede, we intentionally allow active exists; so no_conflicting_active is True if we are superseding (i.e., active exists)  # noqa: E501
    # To keep audit passed semantics, we treat no_conflicting_active as True for supersede case when active exists.  # noqa: E501
    # But we still record that we supersede.
    no_conflicting_active_supersede = True  # supersede explicitly allows replacing active

    passed = bool(
        artifact_verified
        and compatibility_passed
        and evidence_satisfied
        and approval_binds
        and no_stale_parent
        and no_conflicting_active_supersede
    )

    if not passed:
        findings.append("supersede gate blocked")

    audit = BaselineCompatibilityAudit(
        candidate_id=superseding_candidate_id,
        scope_id=scope_id,
        artifact_fingerprint_verified=artifact_verified,
        compatibility_passed=compatibility_passed,
        evidence_policy_satisfied=evidence_satisfied,
        approval_binds=approval_binds,
        no_stale_parent=no_stale_parent,
        no_conflicting_active=no_conflicting_active_supersede,
        findings=findings if not passed else findings + ["all supersede gate checks passed"],
        passed=passed,
        audit_fingerprint="0" * 64,
    )
    # Need to ensure findings + passed aligns – if passed, the last finding includes pass note, but audit validator expects findings consistent.  # noqa: E501
    # Already handled.
    audit = audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})

    if not passed:
        receipt = BaselinePromotionReceipt(
            request=request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    assert approval is not None  # for mypy: passed requires approval_binds
    # Create new active record with superseded fingerprint
    superseded_fp = active_record.record_fingerprint
    provisional_record = BaselineRecord(
        baseline_id=f"baseline-{candidate.candidate_id}",
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
    record_fp = provisional_record.compute_fingerprint()
    record = provisional_record.model_copy(update={"record_fingerprint": record_fp})

    # Ledger: first SUPERSEDED entry marking old baseline superseded, then PROMOTED entry for new one.  # noqa: E501
    # For append-only simplicity we add two entries atomically.
    parent_fp = registry.registry_fingerprint
    superseded_entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry),
        event_kind=BaselineLedgerEventKind.SUPERSEDED,
        timestamp=now,
        scope_id=scope_id,
        candidate_id=superseding_candidate_id,
        baseline_id=active_record.baseline_id,
        artifact_fingerprint=active_record.artifact_fingerprint,
        approval_fingerprint=active_record.approval_fingerprint,
        superseded_fingerprint=superseded_fp,
        registry_parent_fingerprint=parent_fp,
        actor=actor,
        note=note or f"superseded {active_record.baseline_id}",
    )
    # Compute intermediate registry fingerprint for second entry's parent? But spec says ledger is append-only; second entry's parent should be fingerprint after first entry.  # noqa: E501
    # We model registry with both entries appended sequentially – second entry's parent is fingerprint after first entry insertion.  # noqa: E501
    interim_registry = registry.model_copy(
        update={"ledger": list(registry.ledger) + [superseded_entry]}
    )
    interim_fp = interim_registry.compute_fingerprint()

    promoted_entry = _build_ledger_entry(
        entry_index=_next_entry_index(registry) + 1,
        event_kind=BaselineLedgerEventKind.PROMOTED,
        timestamp=now,
        scope_id=scope_id,
        candidate_id=superseding_candidate_id,
        baseline_id=record.baseline_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=record.approval_fingerprint,
        superseded_fingerprint=superseded_fp,
        registry_parent_fingerprint=interim_fp,
        actor=actor,
        note=note or f"superseding promotion {record.baseline_id}",
    )

    new_active = dict(registry.active_baselines)
    new_active[scope_id] = record
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
    """Mark a candidate as withdrawn via ledger event. Does not delete history."""
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
    # We keep candidate in dict but mark ledger; active baselines unchanged
    # Optionally remove from candidates dict? Spec says never edit historical records but withdrawal is new event.  # noqa: E501
    # We'll keep candidate but add withdrawn status via ledger; not removing from dict preserves history.  # noqa: E501
    new_ledger = list(registry.ledger) + [entry]
    new_registry = registry.model_copy(update={"ledger": new_ledger})
    new_fp = new_registry.compute_fingerprint()
    return new_registry.model_copy(update={"registry_fingerprint": new_fp})


# ---------------------------------------------------------------------------
# Restore as new promotion (rollback via new event)
# ---------------------------------------------------------------------------


def restore_baseline_as_new_promotion(
    registry: BaselineRegistry,
    *,
    scope_id: str,
    restore_candidate_id: str,
    actor: str,
    note: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[BaselineRegistry, BaselinePromotionReceipt]:
    """Promote a previously superseded candidate as a new promotion event.

    Rollback is never an edit; it is a fresh promotion with kind restored_as_new_promotion.
    """
    now = _now_or_fixed(clock)

    if restore_candidate_id not in registry.candidates:
        raise ValueError(f"candidate {restore_candidate_id!r} does not exist")
    candidate = registry.candidates[restore_candidate_id]
    if candidate.scope.scope_id != scope_id:
        raise ValueError(
            f"candidate scope {candidate.scope.scope_id!r} != restore scope {scope_id!r}"
        )

    approval = registry.approvals.get(restore_candidate_id)
    if approval is None:
        # Fail-closed: need approval
        dummy_request = BaselinePromotionRequest(
            candidate_id=restore_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint=candidate.artifact_fingerprint,
            approval_fingerprint="0" * 64,
            registry_parent_fingerprint=registry.registry_fingerprint,
            requested_by=actor,
            requested_at=now,
        )
        audit = BaselineCompatibilityAudit(
            candidate_id=restore_candidate_id,
            scope_id=scope_id,
            artifact_fingerprint_verified=True,
            compatibility_passed=True,
            evidence_policy_satisfied=True,
            approval_binds=False,
            no_stale_parent=True,
            no_conflicting_active=True,
            findings=["no approval for restore candidate"],
            passed=False,
            audit_fingerprint="0" * 64,
        )
        audit = audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})
        receipt = BaselinePromotionReceipt(
            request=dummy_request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    # Check that this candidate was previously promoted and then superseded? For restore we allow any prior candidate.  # noqa: E501
    # Require that there is an active baseline currently (otherwise simple promote would do). But restore should work even if active exists – it will supersede.  # noqa: E501
    # We'll reuse supersede logic but emit RESTORED_AS_NEW_PROMOTION event kind instead of PROMOTED.

    # Build request
    request = BaselinePromotionRequest(
        candidate_id=restore_candidate_id,
        scope_id=scope_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=approval.approval_fingerprint,
        registry_parent_fingerprint=registry.registry_fingerprint,
        requested_by=actor,
        requested_at=now,
    )

    # Audit similar to supersede but we check explicit restore conditions
    findings: list[str] = []
    artifact_verified = candidate.artifact_fingerprint == request.artifact_fingerprint
    approval_binds = (
        approval.candidate_id == request.candidate_id
        and approval.scope_id == request.scope_id
        and approval.artifact_fingerprint == request.artifact_fingerprint
        and approval.approval_fingerprint == request.approval_fingerprint
    )
    if not approval_binds:
        findings.append("approval does not bind restore candidate")

    no_stale_parent = request.registry_parent_fingerprint == registry.registry_fingerprint
    if not no_stale_parent:
        findings.append("stale parent for restore")

    evidence_satisfied = (
        candidate.evidence_standing.value != "unavailable"
        and candidate.source_standing.value != "unavailable"
    )
    if not evidence_satisfied:
        findings.append("evidence or source unavailable for restore")

    compatibility_passed = artifact_verified
    if not compatibility_passed:
        findings.append("compatibility failed for restore")

    passed = bool(
        artifact_verified
        and approval_binds
        and no_stale_parent
        and evidence_satisfied
        and compatibility_passed
    )

    audit = BaselineCompatibilityAudit(
        candidate_id=restore_candidate_id,
        scope_id=scope_id,
        artifact_fingerprint_verified=artifact_verified,
        compatibility_passed=compatibility_passed,
        evidence_policy_satisfied=evidence_satisfied,
        approval_binds=approval_binds,
        no_stale_parent=no_stale_parent,
        no_conflicting_active=True,  # restore allows replacing active, so treat as non-conflicting
        findings=findings if not passed else findings + ["restore gate passed"],
        passed=passed,
        audit_fingerprint="0" * 64,
    )
    audit = audit.model_copy(update={"audit_fingerprint": audit.compute_fingerprint()})

    if not passed:
        receipt = BaselinePromotionReceipt(
            request=request,
            status=BaselineStatus.UNAVAILABLE,
            promoted_record=None,
            blocked_reasons=list(audit.findings),
            audit=audit,
            receipt_fingerprint="0" * 64,
            created_at=now,
        )
        receipt = receipt.model_copy(update={"receipt_fingerprint": receipt.compute_fingerprint()})
        return registry, receipt

    # Determine superseded fingerprint if active exists
    active = registry.active_baselines.get(scope_id)
    superseded_fp = active.record_fingerprint if active else None

    provisional_record = BaselineRecord(
        baseline_id=f"baseline-{candidate.candidate_id}-restore-{len(registry.ledger)}",
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
    record_fp = provisional_record.compute_fingerprint()
    record = provisional_record.model_copy(update={"record_fingerprint": record_fp})

    # Ledger: if active exists, emit SUPERSEDED then RESTORED_AS_NEW_PROMOTION; else just RESTORED_AS_NEW_PROMOTION  # noqa: E501
    new_ledger = list(registry.ledger)
    parent_fp = registry.registry_fingerprint

    if active is not None:
        superseded_entry = _build_ledger_entry(
            entry_index=len(new_ledger),
            event_kind=BaselineLedgerEventKind.SUPERSEDED,
            timestamp=now,
            scope_id=scope_id,
            candidate_id=restore_candidate_id,
            baseline_id=active.baseline_id,
            artifact_fingerprint=active.artifact_fingerprint,
            approval_fingerprint=active.approval_fingerprint,
            superseded_fingerprint=superseded_fp,
            registry_parent_fingerprint=parent_fp,
            actor=actor,
            note=note or f"superseded for restore {record.baseline_id}",
        )
        new_ledger.append(superseded_entry)
        interim_registry = registry.model_copy(update={"ledger": new_ledger})
        interim_fp = interim_registry.compute_fingerprint()
        parent_fp = interim_fp

    restore_entry = _build_ledger_entry(
        entry_index=len(new_ledger),
        event_kind=BaselineLedgerEventKind.RESTORED_AS_NEW_PROMOTION,
        timestamp=now,
        scope_id=scope_id,
        candidate_id=restore_candidate_id,
        baseline_id=record.baseline_id,
        artifact_fingerprint=candidate.artifact_fingerprint,
        approval_fingerprint=approval.approval_fingerprint,
        superseded_fingerprint=superseded_fp,
        registry_parent_fingerprint=parent_fp,
        actor=actor,
        note=note or f"restored {restore_candidate_id}",
    )
    new_ledger.append(restore_entry)

    new_active = dict(registry.active_baselines)
    new_active[scope_id] = record

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
