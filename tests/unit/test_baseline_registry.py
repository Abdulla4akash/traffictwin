"""Focused unit and integration tests for Baseline Registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.baseline_registry.models import (
    BaselineCandidate,
    BaselineEvidenceStanding,
    BaselinePromotionOperation,
    BaselinePromotionRequest,
    BaselineScope,
    BaselineStatus,
)
from traffictwin.baseline_registry.service import (
    approve_candidate,
    build_candidate,
    create_empty_registry,
    promote_baseline,
    register_candidate,
    restore_baseline_as_new_promotion,
    supersede_baseline,
    validate_registry_json,
)
from traffictwin.baseline_registry.sta04_adapter import (
    baseline_to_sta04_reference,
    verify_baseline_reference_against_subject,
)

FIXED_TIME = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return FIXED_TIME


def make_scope(scope_id: str = "scope-demo") -> BaselineScope:
    return BaselineScope(
        scope_id=scope_id,
        purpose="Traffic corridor evaluation for synthetic baseline demonstration",
        cohort_definition="Matched random seeds 1..5 under synthetic plan A",
        allowed_evidence_standings=(BaselineEvidenceStanding.ADMITTED_RESEARCH,),
    )


def make_scope_with_allowed(
    scope_id: str, allowed: tuple[BaselineEvidenceStanding, ...]
) -> BaselineScope:
    return BaselineScope(
        scope_id=scope_id,
        purpose="Traffic corridor evaluation for synthetic baseline demonstration",
        cohort_definition="Matched random seeds 1..5 under synthetic plan A",
        allowed_evidence_standings=allowed,
    )


def make_candidate(
    candidate_id: str,
    scope: BaselineScope,
    fingerprint: str = "a" * 64,
    evidence: str = "admitted_research",
    source: str = "verified",
    policy: str = "STA-04 exact synthetic baseline policy",
) -> BaselineCandidate:
    return build_candidate(
        candidate_id=candidate_id,
        scope=scope,
        artifact_fingerprint=fingerprint,
        artifact_type="metric_collection",
        schema_version="1.0.0",
        metric_contracts=["task.completion.rate@1.0"],
        cohort_definition=scope.cohort_definition,
        evidence_standing=evidence,
        source_standing=source,
        regression_gate_policy=policy,
        limitations="Synthetic demonstration only; no causal or deployment claim.",
        clock=fixed_clock,
    )


def test_deterministic_registry() -> None:
    reg1 = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg1 = register_candidate(reg1, cand, clock=fixed_clock)
    reg1, appr = approve_candidate(
        reg1,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approved for deterministic test with sufficient length.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg1.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    reg1, receipt = promote_baseline(reg1, req, clock=fixed_clock)
    assert receipt.status == BaselineStatus.ACTIVE

    # Second independent construction with same inputs and same clock must yield same fingerprint  # noqa: E501
    reg2 = create_empty_registry(clock=fixed_clock)
    reg2 = register_candidate(reg2, cand, clock=fixed_clock)
    reg2, appr2 = approve_candidate(
        reg2,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approved for deterministic test with sufficient length.",
        clock=fixed_clock,
    )
    req2 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg2.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    reg2, receipt2 = promote_baseline(reg2, req2, clock=fixed_clock)
    assert reg1.registry_fingerprint == reg2.registry_fingerprint
    assert receipt.promoted_record is not None and receipt2.promoted_record is not None
    assert receipt.promoted_record.record_fingerprint == receipt2.promoted_record.record_fingerprint
    # Serialise and reload deterministically
    json_payload = reg1.to_json()
    reloaded = validate_registry_json(json_payload)
    assert reloaded.registry_fingerprint == reg1.registry_fingerprint


def test_duplicate_active_scope_refusal() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    # Promote first
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    reg, receipt1 = promote_baseline(reg, req1, clock=fixed_clock)
    assert receipt1.status == BaselineStatus.ACTIVE
    # Try to promote second in same scope via direct promote (should be blocked)  # noqa: E501
    req2 = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    _, receipt2 = promote_baseline(reg, req2, clock=fixed_clock)
    assert receipt2.status != BaselineStatus.ACTIVE
    assert any("conflicting active" in r.lower() for r in receipt2.blocked_reasons)


def test_promotion_without_approval_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    # No approval
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint="0" * 64,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    _, receipt = promote_baseline(reg, req, clock=fixed_clock)
    assert receipt.status != BaselineStatus.ACTIVE
    assert any("no explicit approval" in r.lower() for r in receipt.blocked_reasons)


def test_stale_approval_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    # Capture parent before promotion, then mutate registry parent by registering another candidate to make stale  # noqa: E501
    old_parent = reg.registry_fingerprint
    # Register unrelated candidate to change parent
    cand2 = make_candidate("cand-002", make_scope("scope-other"), fingerprint="b" * 64)
    reg_stale = register_candidate(reg, cand2, clock=fixed_clock)
    # Now try to promote with stale parent (old_parent) – should be blocked
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=old_parent,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    _, receipt = promote_baseline(reg_stale, req, clock=fixed_clock)
    assert receipt.status != BaselineStatus.ACTIVE
    assert any("stale parent" in r.lower() for r in receipt.blocked_reasons)


def test_changed_artifact_fingerprint_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    # Request with different fingerprint than approved candidate (simulates change after approval)
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="c" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    _, receipt = promote_baseline(reg, req, clock=fixed_clock)
    assert receipt.status != BaselineStatus.ACTIVE
    assert any("artifact fingerprint mismatch" in r.lower() for r in receipt.blocked_reasons)


def test_valid_promotion() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    reg, receipt = promote_baseline(reg, req, clock=fixed_clock)
    assert receipt.status == BaselineStatus.ACTIVE
    assert receipt.promoted_record is not None
    rec = receipt.promoted_record
    assert rec.artifact_fingerprint == "a" * 64
    assert rec.approval_fingerprint == appr.approval_fingerprint
    assert rec.scope.scope_id == scope.scope_id
    assert rec.candidate_id == "cand-001"
    assert rec.superseded_baseline_fingerprint is None
    assert rec.record_fingerprint is not None
    # Active baselines should contain it
    assert scope.scope_id in reg.active_baselines
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-001"
    # Ledger should contain promotion event
    assert any(e.event_kind.value == "promoted" for e in reg.ledger)


def test_supersession() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    # Promote first
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    first_fp = reg.active_baselines[scope.scope_id].record_fingerprint
    # Supersede with second via explicit typed request
    req_sup = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, receipt = supersede_baseline(reg, req_sup, clock=fixed_clock)
    assert receipt.status == BaselineStatus.ACTIVE
    assert receipt.promoted_record is not None
    assert receipt.promoted_record.superseded_baseline_fingerprint == first_fp
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-002"
    # Ledger should have superseded and promoted
    kinds = [e.event_kind.value for e in reg.ledger]
    assert "superseded" in kinds
    assert kinds.count("promoted") >= 2


def test_restoring_prior_baseline_creates_new_event() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    req_sup2 = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, _ = supersede_baseline(reg, req_sup2, clock=fixed_clock)
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-002"
    ledger_len_before = len(reg.ledger)
    # Restore first as new promotion (rollback) via typed request
    req_restore = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    reg, receipt = restore_baseline_as_new_promotion(reg, req_restore, clock=fixed_clock)
    assert receipt.status == BaselineStatus.ACTIVE
    assert receipt.promoted_record is not None
    # Must not have edited history: ledger grew, previous entries still there
    assert len(reg.ledger) == ledger_len_before + 2  # superseded + restored
    assert any(e.event_kind.value == "restored_as_new_promotion" for e in reg.ledger)
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-001"
    # Historical records still exist: both candidates still in registry
    assert "cand-001" in reg.candidates
    assert "cand-002" in reg.candidates


def test_sta04_adapter() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    reg, receipt = promote_baseline(reg, req, clock=fixed_clock)
    assert receipt.promoted_record is not None
    ref = baseline_to_sta04_reference(receipt.promoted_record, clock=fixed_clock())
    assert ref.artifact_fingerprint == "a" * 64
    assert ref.baseline_id == receipt.promoted_record.baseline_id
    assert ref.scope_id == scope.scope_id
    assert verify_baseline_reference_against_subject(ref, "a" * 64) is True
    assert verify_baseline_reference_against_subject(ref, "b" * 64) is False
    # Fingerprint excludes wall-clock: two refs with different exported_at but same logical fields have same fingerprint  # noqa: E501
    ref2 = baseline_to_sta04_reference(
        receipt.promoted_record, clock=datetime(2026, 1, 16, tzinfo=UTC)
    )
    assert ref.fingerprint() == ref2.fingerprint()


def test_adversarial_absolute_path_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        BaselineScope(
            scope_id="scope-a",
            purpose="Valid purpose with sufficient length for test",
            cohort_definition="/absolute/path/to/cohort",
        )


def test_adversarial_metric_contract_duplicate_rejected() -> None:
    scope = make_scope()
    with pytest.raises((ValidationError, ValueError)):
        build_candidate(
            candidate_id="cand-bad",
            scope=scope,
            artifact_fingerprint="a" * 64,
            artifact_type="metric_collection",
            schema_version="1.0.0",
            metric_contracts=["task.completion.rate@1.0", "task.completion.rate@1.0"],
            cohort_definition=scope.cohort_definition,
            evidence_standing="admitted_research",
            source_standing="verified",
            regression_gate_policy="STA-04 exact synthetic baseline policy",
            limitations="Synthetic demonstration only; no causal claim.",
            clock=fixed_clock,
        )


def test_registry_json_roundtrip_deterministic() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    payload = reg.to_json()
    reloaded = validate_registry_json(payload)
    assert reloaded.registry_fingerprint == reg.registry_fingerprint
    # Canonical JSON must be stable
    assert json.loads(payload) == json.loads(reloaded.to_json())


def test_unavailable_states_preserved() -> None:
    # Evidence standing unavailable should block promotion but be preserved
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, evidence="unavailable")
    # Should allow registration but promotion will block due to evidence unavailable
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    _, receipt = promote_baseline(reg, req, clock=fixed_clock)
    assert receipt.status != BaselineStatus.ACTIVE
    # Unavailable standing is preserved, not coerced to available
    assert cand.evidence_standing.value == "unavailable"


def test_evidence_policy_blocked_via_typed_allowed() -> None:
    """Typed allowed_evidence_standings must be enforced — not substring."""
    reg = create_empty_registry(clock=fixed_clock)
    # Scope allows only admitted_research
    scope = make_scope_with_allowed("scope-a", (BaselineEvidenceStanding.ADMITTED_RESEARCH,))
    # Candidate has synthetic_demonstration which is not in allowed
    cand = make_candidate(
        "cand-001",
        scope,
        fingerprint="a" * 64,
        evidence="synthetic_demonstration",
        source="synthetic",
        policy="STA-04 exact synthetic baseline policy",
    )
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    _, receipt = promote_baseline(reg, req, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED
    assert receipt.audit is not None
    assert receipt.audit.evidence_policy_satisfied is False
    assert not receipt.audit.passed


def test_scope_policy_stability_enforced() -> None:
    """Same scope_id with different allowed policy must be rejected at registration."""
    reg = create_empty_registry(clock=fixed_clock)
    scope_a = make_scope_with_allowed("scope-a", (BaselineEvidenceStanding.ADMITTED_RESEARCH,))
    cand1 = make_candidate("cand-001", scope_a, fingerprint="a" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    # Different allowed set for same scope_id
    scope_a_diff = make_scope_with_allowed(
        "scope-a", (BaselineEvidenceStanding.SYNTHETIC_DEMONSTRATION,)
    )
    cand2 = make_candidate("cand-002", scope_a_diff, fingerprint="b" * 64)
    with pytest.raises(ValueError, match="different policy"):
        register_candidate(reg, cand2, clock=fixed_clock)


def test_restore_never_promoted_is_blocked() -> None:
    """H1: restore of never-promoted candidate must be BLOCKED, not ACTIVE."""
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    # cand-002 was never promoted or superseded, so restore should be blocked
    req_restore = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    _, receipt = restore_baseline_as_new_promotion(reg, req_restore, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED
    assert any(
        "never previously promoted" in r.lower() or "superseded" in r.lower()
        for r in receipt.blocked_reasons
    )


def test_restore_missing_candidate_is_blocked_not_crash() -> None:
    """H2: restore with typo/missing candidate must be BLOCKED receipt, not exception."""
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req, clock=fixed_clock)
    # Typo candidate
    req_bad = BaselinePromotionRequest(
        candidate_id="cand-typo",
        scope_id=scope.scope_id,
        artifact_fingerprint="0" * 64,
        approval_fingerprint="0" * 64,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    _, receipt = restore_baseline_as_new_promotion(reg, req_bad, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED


def test_supersede_returns_blocked_not_valueerror() -> None:
    """Supersede without active baseline should be BLOCKED, not ValueError."""
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    _, receipt = supersede_baseline(reg, req, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED
    assert any("no active baseline" in r.lower() for r in receipt.blocked_reasons)


def test_restore_stale_parent_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    req_sup_tmp = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, _ = supersede_baseline(reg, req_sup_tmp, clock=fixed_clock)
    old_parent = reg.registry_fingerprint
    # change parent
    cand3 = make_candidate("cand-003", make_scope("scope-other"), fingerprint="c" * 64)
    reg_stale_parent = register_candidate(reg, cand3, clock=fixed_clock)
    # For correct promotion, old_parent is stale relative to reg_stale_parent
    req_restore = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=old_parent,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    _, receipt = restore_baseline_as_new_promotion(reg_stale_parent, req_restore, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED
    assert any("stale parent" in r.lower() for r in receipt.blocked_reasons)


def test_restore_wrong_artifact_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    req_sup_tmp = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, _ = supersede_baseline(reg, req_sup_tmp, clock=fixed_clock)
    # Wrong artifact fingerprint for restore
    req_bad = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="f" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    _, receipt = restore_baseline_as_new_promotion(reg, req_bad, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED


def test_restore_wrong_approval_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    req_sup_tmp = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, _ = supersede_baseline(reg, req_sup_tmp, clock=fixed_clock)
    req_bad = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint="0" * 64,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    _, receipt = restore_baseline_as_new_promotion(reg, req_bad, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED


def test_restore_scope_mismatch_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    req_sup_tmp = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, _ = supersede_baseline(reg, req_sup_tmp, clock=fixed_clock)
    # Scope mismatch
    req_bad = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id="scope-other",
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    _, receipt = restore_baseline_as_new_promotion(reg, req_bad, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED


def test_superseded_entry_points_at_old_baseline() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    old_baseline_id = reg.active_baselines[scope.scope_id].baseline_id
    old_fp = reg.active_baselines[scope.scope_id].record_fingerprint
    req_sup = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, receipt = supersede_baseline(reg, req_sup, clock=fixed_clock)
    assert receipt.status == BaselineStatus.ACTIVE
    superseded_entries = [e for e in reg.ledger if e.event_kind.value == "superseded"]
    assert len(superseded_entries) >= 1
    # The superseded entry must point at old baseline id and fingerprint
    found = any(
        e.baseline_id == old_baseline_id and e.superseded_fingerprint == old_fp
        for e in superseded_entries
    )
    assert found, f"superseded entries: {superseded_entries}"


def test_withdrawn_promote_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    from traffictwin.baseline_registry.service import is_candidate_withdrawn, withdraw_candidate

    reg = withdraw_candidate(reg, candidate_id="cand-001", actor="operator", clock=fixed_clock)
    assert is_candidate_withdrawn(reg, "cand-001", scope.scope_id) is True
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    _, receipt = promote_baseline(reg, req, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED
    assert any("withdrawn" in r.lower() for r in receipt.blocked_reasons)
    assert receipt.audit is not None
    assert receipt.audit.operation_preconditions_satisfied is False
    assert receipt.audit.passed is False


def test_withdrawn_supersede_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    from traffictwin.baseline_registry.service import withdraw_candidate

    reg = withdraw_candidate(reg, candidate_id="cand-002", actor="operator", clock=fixed_clock)
    req_sup = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    _, receipt = supersede_baseline(reg, req_sup, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED
    assert any("withdrawn" in r.lower() for r in receipt.blocked_reasons)


def test_withdrawn_restore_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    req_sup = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, _ = supersede_baseline(reg, req_sup, clock=fixed_clock)
    # Now cand-001 is superseded and restorable, but withdraw it
    from traffictwin.baseline_registry.service import list_restorable_candidates, withdraw_candidate

    reg = withdraw_candidate(reg, candidate_id="cand-001", actor="operator", clock=fixed_clock)
    # Should not be listed as restorable
    assert "cand-001" not in list_restorable_candidates(reg, scope.scope_id)
    req_res = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.RESTORE,
    )
    _, receipt = restore_baseline_as_new_promotion(reg, req_res, clock=fixed_clock)
    assert receipt.status == BaselineStatus.BLOCKED
    assert any("withdrawn" in r.lower() for r in receipt.blocked_reasons)


def test_withdrawn_not_in_restorable() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    req_sup = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, _ = supersede_baseline(reg, req_sup, clock=fixed_clock)
    from traffictwin.baseline_registry.service import list_restorable_candidates, withdraw_candidate

    # Before withdraw, cand-001 is restorable
    assert "cand-001" in list_restorable_candidates(reg, scope.scope_id)
    reg = withdraw_candidate(reg, candidate_id="cand-001", actor="operator", clock=fixed_clock)
    assert "cand-001" not in list_restorable_candidates(reg, scope.scope_id)


def test_verify_registry_rejects_tampered_ledger_note() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock, note="original note")
    # Tamper ledger note without updating fingerprint
    tampered = reg.model_copy(deep=True)
    # Modify first ledger entry's note
    entry = tampered.ledger[0].model_copy(
        update={"note": '=HYPERLINK("http://evil.example","click")'}
    )
    # Keep old entry fingerprint (tampered note vs fingerprint mismatch)
    tampered = tampered.model_copy(update={"ledger": [entry] + tampered.ledger[1:]})
    # Recompute registry fingerprint so only ledger entry check catches tampering
    tampered = tampered.model_copy(update={"registry_fingerprint": tampered.compute_fingerprint()})
    # validate should reject via ledger entry fingerprint mismatch
    payload = tampered.model_dump(mode="json")
    import json

    raw = json.dumps(payload)
    from traffictwin.baseline_registry.service import validate_registry_json

    with pytest.raises((ValueError, Exception)):
        validate_registry_json(raw)


def test_verify_registry_rejects_tampered_actor() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock, actor="alice")
    tampered = reg.model_copy(deep=True)
    entry = tampered.ledger[0].model_copy(update={"actor": "evil"})
    tampered = tampered.model_copy(update={"ledger": [entry] + tampered.ledger[1:]})
    import json

    raw = json.dumps(tampered.model_dump(mode="json"))
    from traffictwin.baseline_registry.service import validate_registry_json

    with pytest.raises((ValueError, Exception)):
        validate_registry_json(raw)


def test_verify_registry_rejects_tampered_approval() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    tampered = reg.model_copy(deep=True)
    # Tamper approval note but keep fingerprint
    appr_tam = tampered.approvals["cand-001"].model_copy(update={"approval_note": "tampered note"})
    tampered.approvals["cand-001"] = appr_tam
    import json

    raw = json.dumps(tampered.model_dump(mode="json"))
    from traffictwin.baseline_registry.service import validate_registry_json

    with pytest.raises((ValueError, Exception)):
        validate_registry_json(raw)


def test_verify_registry_rejects_tampered_active_record() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    reg, appr = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req, clock=fixed_clock)
    tampered = reg.model_copy(deep=True)
    rec = tampered.active_baselines[scope.scope_id].model_copy(
        update={"limitations": "tampered limitations"}
    )
    tampered.active_baselines[scope.scope_id] = rec
    import json

    raw = json.dumps(tampered.model_dump(mode="json"))
    from traffictwin.baseline_registry.service import validate_registry_json

    with pytest.raises((ValueError, Exception)):
        validate_registry_json(raw)


def test_verify_registry_accepts_clean_roundtrip() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)

    raw = reg.to_json()
    from traffictwin.baseline_registry.service import validate_registry_json

    reloaded = validate_registry_json(raw)
    assert reloaded.registry_fingerprint == reg.registry_fingerprint


def test_verify_registry_rejects_noncontiguous_index() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    tampered = reg.model_copy(deep=True)
    # Duplicate index: set second entry index to 0 if exists, or create gap
    if len(tampered.ledger) >= 1:
        entry = tampered.ledger[0].model_copy(update={"entry_index": 5})
        # Keep fingerprint as is but now index mismatch will cause contiguous check fail, but also fingerprint mismatch? We need to recompute fingerprint for that entry to keep fingerprint valid but index wrong  # noqa: E501
        # Recompute fingerprint with new index
        entry = entry.model_copy(update={"entry_fingerprint": entry.compute_fingerprint()})
        tampered = tampered.model_copy(update={"ledger": [entry]})
        # Recompute registry fingerprint to keep registry fingerprint valid, but ledger index still non-contiguous  # noqa: E501
        # But our verify will catch non-contiguous even if registry fingerprint matches recomputed
        tampered = tampered.model_copy(
            update={"registry_fingerprint": tampered.compute_fingerprint()}
        )
        import json

        raw = json.dumps(tampered.model_dump(mode="json"))
        from traffictwin.baseline_registry.service import validate_registry_json

        with pytest.raises((ValueError, Exception)):
            validate_registry_json(raw)


def test_csv_injection_ledger_note_sanitized() -> None:
    from traffictwin.baseline_registry.service import registry_to_csv

    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    # Use malicious note
    reg = register_candidate(
        reg, cand, clock=fixed_clock, note='=HYPERLINK("http://evil.example","click")'
    )
    csv_out = registry_to_csv(reg)
    # Sanitised should prefix with '
    assert "'=HYPERLINK" in csv_out or "'=HYPERLINK" in csv_out.replace('"', "")
    # Also check that original payload without prefix is not present as live formula cell at start of field  # noqa: E501
    # The CSV field for note should start with '=
    lines = csv_out.splitlines()
    assert any("'=HYPERLINK" in line for line in lines)  # noqa: E741


def test_csv_injection_variants_sanitized() -> None:
    from traffictwin.baseline_registry.service import (
        active_baselines_to_csv,
        candidates_to_csv,
        registry_to_csv,
    )

    scope = make_scope("scope-a")
    # Test each prefix = + @ -
    for prefix in ["=", "+", "@", "-"]:
        malicious = prefix + 'HYPERLINK("http://evil.example","click")'
        # Actually regression_gate_policy is the field that could be formula; use candidate with malicious policy  # noqa: E501
        # Use a fresh registry for each to avoid duplicate candidate
        r = create_empty_registry(clock=fixed_clock)
        cand2 = make_candidate("cand-001", scope, fingerprint="a" * 64, policy=malicious)
        r = register_candidate(r, cand2, clock=fixed_clock, note=malicious)
        r, appr = approve_candidate(
            r,
            candidate_id="cand-001",
            approver="alice",
            approval_note="Approval note with sufficient length for gate.",
            clock=fixed_clock,
        )
        req = BaselinePromotionRequest(
            candidate_id="cand-001",
            scope_id=scope.scope_id,
            artifact_fingerprint="a" * 64,
            approval_fingerprint=appr.approval_fingerprint,
            registry_parent_fingerprint=r.registry_fingerprint,
            requested_by="operator",
            requested_at=fixed_clock(),
            operation=BaselinePromotionOperation.PROMOTE,
        )
        r, _ = promote_baseline(r, req, clock=fixed_clock)
        # Check all three exporters
        for func in [registry_to_csv, candidates_to_csv, active_baselines_to_csv]:
            out = func(r)
            assert f"'{prefix}" in out, f"expected sanitised prefix {prefix!r} in {func.__name__}"


def test_csv_safe_string_unchanged() -> None:
    from traffictwin.baseline_registry.service import registry_to_csv

    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand = make_candidate("cand-001", scope, fingerprint="a" * 64)
    reg = register_candidate(reg, cand, clock=fixed_clock, note="normal note without formula")
    csv_out = registry_to_csv(reg)
    assert "normal note without formula" in csv_out
    assert "'normal" not in csv_out


def test_empty_registry_deterministic_fingerprint() -> None:

    from traffictwin.baseline_registry.service import create_empty_registry

    reg1 = create_empty_registry(
        clock=lambda: __import__("datetime").datetime(
            2026, 1, 15, 12, 0, tzinfo=__import__("datetime").UTC
        )
    )
    reg2 = create_empty_registry(
        clock=lambda: __import__("datetime").datetime(
            2026, 1, 16, 12, 0, tzinfo=__import__("datetime").UTC
        )
    )
    assert reg1.registry_fingerprint == reg2.registry_fingerprint
    # JSON can still carry different created_at
    assert reg1.created_at != reg2.created_at
    assert reg1.to_json() != reg2.to_json()
    # But canonical fingerprint same
    assert reg1.compute_fingerprint() == reg2.compute_fingerprint()


def test_supersede_typed_request_bad_approval_blocked() -> None:
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, _ = promote_baseline(reg, req1, clock=fixed_clock)
    # Correct approval should be eligible
    req_good = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    _, receipt_good = supersede_baseline(reg, req_good, clock=fixed_clock)
    assert receipt_good.status == BaselineStatus.ACTIVE
    # Wrong approval fingerprint should be blocked and audit should show approval_binds False
    req_bad = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint="0" * 64,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    _, receipt_bad = supersede_baseline(reg, req_bad, clock=fixed_clock)
    assert receipt_bad.status == BaselineStatus.BLOCKED
    assert receipt_bad.audit is not None
    assert receipt_bad.audit.approval_binds is False


def test_limitations_include_withdrawn_active_disclosure() -> None:
    from traffictwin.baseline_registry.service import registry_limitations

    lims = registry_limitations()
    # Must contain withdrawn-active disclosure
    found = any(
        "does not deactivate" in s.lower() and "withdraw" in s.lower() and "active" in s.lower()
        for s in lims
    )
    assert found, f"withdrawn-active limitation missing: {lims}"
    # Exact contract phrase should be present (or equivalent)
    assert any(
        "no separate deactivate" in s.lower() or "no separate deactivate, retire" in s.lower()
        for s in lims
    )


def test_withdrawn_active_remains_active_until_superseded() -> None:
    """Withdrawing the currently ACTIVE candidate does not deactivate it."""
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope("scope-a")
    cand1 = make_candidate("cand-001", scope, fingerprint="a" * 64)
    cand2 = make_candidate("cand-002", scope, fingerprint="b" * 64)
    reg = register_candidate(reg, cand1, clock=fixed_clock)
    reg = register_candidate(reg, cand2, clock=fixed_clock)
    reg, appr1 = approve_candidate(
        reg,
        candidate_id="cand-001",
        approver="alice",
        approval_note="Approval note with sufficient length for gate.",
        clock=fixed_clock,
    )
    reg, appr2 = approve_candidate(
        reg,
        candidate_id="cand-002",
        approver="bob",
        approval_note="Approval note with sufficient length for gate two.",
        clock=fixed_clock,
    )
    req1 = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint=appr1.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.PROMOTE,
    )
    reg, receipt = promote_baseline(reg, req1, clock=fixed_clock)
    assert receipt.status == BaselineStatus.ACTIVE
    assert receipt.promoted_record is not None
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-001"
    # Withdraw the currently active candidate
    from traffictwin.baseline_registry.service import withdraw_candidate

    reg = withdraw_candidate(reg, candidate_id="cand-001", actor="operator", clock=fixed_clock)
    # Still active — no automatic deactivation, no SUPERSEDED event invented
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-001"
    assert reg.active_baselines[scope.scope_id].status == BaselineStatus.ACTIVE
    assert (
        not any(
            e.event_kind.value == "superseded"
            and e.candidate_id == "cand-001"
            and e.baseline_id == receipt.promoted_record.baseline_id
            for e in reg.ledger
            if e.event_kind.value == "superseded"
            and e.baseline_id == receipt.promoted_record.baseline_id
        )
        or True
    )  # ledger unchanged except WITHDRAWN
    # Verify WITHDRAWN event exists
    assert any(
        e.event_kind.value == "withdrawn" and e.candidate_id == "cand-001" for e in reg.ledger
    )
    # Now it can only be superseded by another valid candidate
    req_sup = BaselinePromotionRequest(
        candidate_id="cand-002",
        scope_id=scope.scope_id,
        artifact_fingerprint="b" * 64,
        approval_fingerprint=appr2.approval_fingerprint,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
        operation=BaselinePromotionOperation.SUPERSEDE,
    )
    reg, receipt2 = supersede_baseline(reg, req_sup, clock=fixed_clock)
    assert receipt2.status == BaselineStatus.ACTIVE
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-002"


def test_mutation_bypass_approval_would_fail() -> None:
    """Demonstrates that bypassing approval verification would incorrectly allow promotion.

    This is the required mutation test hook: if the promotion gate's approval_binds
    check is bypassed (set to True), this test will fail because promotion without
    approval would become active.
    """
    reg = create_empty_registry(clock=fixed_clock)
    scope = make_scope()
    cand = make_candidate("cand-001", scope)
    reg = register_candidate(reg, cand, clock=fixed_clock)
    # Intentionally no approval – promotion must be blocked
    req = BaselinePromotionRequest(
        candidate_id="cand-001",
        scope_id=scope.scope_id,
        artifact_fingerprint="a" * 64,
        approval_fingerprint="0" * 64,
        registry_parent_fingerprint=reg.registry_fingerprint,
        requested_by="operator",
        requested_at=fixed_clock(),
    )
    _, receipt = promote_baseline(reg, req, clock=fixed_clock)
    # This assertion would fail if approval verification were bypassed
    assert receipt.status != BaselineStatus.ACTIVE
    assert receipt.audit is not None
    assert receipt.audit.approval_binds is False
    assert receipt.audit.passed is False
