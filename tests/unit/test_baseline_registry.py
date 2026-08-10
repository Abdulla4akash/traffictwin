"""Focused unit and integration tests for Baseline Registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.baseline_registry.models import (
    BaselineCandidate,
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
    # Supersede with second
    reg, receipt = supersede_baseline(
        reg,
        scope_id=scope.scope_id,
        superseding_candidate_id="cand-002",
        actor="operator",
        clock=fixed_clock,
    )
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
    reg, _ = supersede_baseline(
        reg,
        scope_id=scope.scope_id,
        superseding_candidate_id="cand-002",
        actor="operator",
        clock=fixed_clock,
    )
    assert reg.active_baselines[scope.scope_id].candidate_id == "cand-002"
    ledger_len_before = len(reg.ledger)
    # Restore first as new promotion (rollback)
    reg, receipt = restore_baseline_as_new_promotion(
        reg,
        scope_id=scope.scope_id,
        restore_candidate_id="cand-001",
        actor="operator",
        clock=fixed_clock,
    )
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
