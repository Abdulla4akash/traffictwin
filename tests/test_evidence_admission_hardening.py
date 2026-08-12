"""Hardening regressions for B1/B2/M1/M2 and Q-cleanup.

Implements zero-decision attack, genesis, tail-anchor, CSV injection,
ledger import, receipt, binding, immutability, and helper contracts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.evidence_admission.models import (
    CompatibilityStanding,
    EvidenceMode,
    EvidenceReviewDecision,
    EvidenceReviewLedger,
    EvidenceReviewState,
    RightsPrivacyStanding,
    ValidationStanding,
    _fingerprint,
)
from traffictwin.evidence_admission.service import (
    EvidenceAdmissionInboxService,
    ExportRefusedError,
    LedgerVerificationError,
    allowed_transitions_from,
    ledger_from_json,
    ledger_to_json,
    review_summary_to_csv,
    verify_case_with_ledger,
)
from traffictwin.preregistration.models import ArtifactAdmission


def _hex(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _svc_case(
    case_id: str = "case-h",
    cell_id: str = "cell-h",
    compatibility: CompatibilityStanding = CompatibilityStanding.COMPATIBLE,
) -> tuple[EvidenceAdmissionInboxService, str]:
    svc = EvidenceAdmissionInboxService()
    svc.create_case(
        case_id=case_id,
        candidate_artifact_fingerprint=_hex(f"art-{case_id}"),
        expected_preregistration_cell_id=cell_id,
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex(f"con-{case_id}"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=compatibility,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    return svc, case_id


# B1 — zero-decision attack: corrupted cached state must not export
def test_zero_decision_attack_corrupted_case_is_refused() -> None:
    svc, case_id = _svc_case("case-zero", "cell-zero")
    ledger = svc.get_ledger(case_id)
    assert ledger.decisions == ()
    assert ledger.current_state is None
    assert ledger.tail_fingerprint == "0" * 64
    # Simulate corruption: craft a corrupted case snapshot with ADMITTED but empty ledger
    # Because models are frozen, we must use model_copy to craft adversarial copy
    # and then inject via test-local internal pair (white-box corruption for test)
    case = svc.get_case(case_id)
    corrupted = case.model_copy(update={"current_state": EvidenceReviewState.ADMITTED})
    # Directly inject corrupted pair into a test-local service to simulate stolen state
    # We use the service's private store for adversarial setup (allowed in test)
    svc._cases[case_id] = type(svc._cases[case_id])(case=corrupted, ledger=ledger)
    with pytest.raises(
        (ExportRefusedError, LedgerVerificationError),
        match="(?i)(admitted|admission|mismatch|genesis|unavailable|no admitted)",
    ):
        svc.export_admitted_attachment(case_id)


def test_genesis_tail_can_never_export() -> None:
    # After Q1 dead-guard removal, genesis is implied by empty ADMITTED check.
    # Real protection is case/ledger consistency: forged ADMITTED with empty ledger must be refused.
    svc, case_id = _svc_case("case-genesis", "cell-genesis")
    ledger = svc.get_ledger(case_id)
    assert ledger.tail_fingerprint == "0" * 64
    assert ledger.current_state is None
    case = svc.get_case(case_id)
    corrupted = case.model_copy(update={"current_state": EvidenceReviewState.ADMITTED})
    svc._cases[case_id] = type(svc._cases[case_id])(case=corrupted, ledger=ledger)
    violations = svc.verify_ledger(case_id)
    assert any("disagrees with empty ledger" in v for v in violations)
    with pytest.raises((ExportRefusedError, LedgerVerificationError)):
        svc.export_admitted_attachment(case_id)


def test_case_ledger_state_mismatch_is_detected() -> None:
    svc, case_id = _svc_case("case-mismatch", "cell-mismatch")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    case = svc.get_case(case_id)
    ledger = svc.get_ledger(case_id)
    # Corrupt cached state to pending while ledger is admitted
    corrupted = case.model_copy(update={"current_state": EvidenceReviewState.PENDING})
    svc._cases[case_id] = type(svc._cases[case_id])(case=corrupted, ledger=ledger)
    violations = svc.verify_ledger(case_id)
    assert any("disagrees with ledger state" in v for v in violations)
    with pytest.raises((LedgerVerificationError, ExportRefusedError)):
        svc.export_admitted_attachment(case_id)
    # Also appending a new decision must first detect corruption
    with pytest.raises(LedgerVerificationError):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-2",
            decision=EvidenceReviewState.WITHDRAWN,
            reason="withdraw",
            reviewer_label="r2",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        )


def test_tail_anchor_mismatch_refused() -> None:
    svc, case_id = _svc_case("case-tail", "cell-tail")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    ledger = svc.get_ledger(case_id)
    case = svc.get_case(case_id)
    assert ledger.tail_fingerprint != "0" * 64
    # Tamper last decision reason while preserving previous fingerprint (tail tamper)
    tampered_dec = ledger.decisions[-1].model_copy(update={"reason": "tampered reason"})
    # Ledger internal predecessor chain may still verify structurally if we keep previous, but tail changes  # noqa: E501
    tampered_ledger = EvidenceReviewLedger(
        case_id=ledger.case_id,
        case_fingerprint=ledger.case_fingerprint,
        decisions=ledger.decisions[:-1] + (tampered_dec,),
    )
    # Internal verify may pass (since previous chain still matches), but anchor must fail
    # Inject tampered ledger with original case tail (mismatch)
    svc._cases[case_id] = type(svc._cases[case_id])(case=case, ledger=tampered_ledger)
    violations = svc.verify_ledger(case_id)
    assert any("tail anchor mismatch" in v for v in violations)
    with pytest.raises((LedgerVerificationError, ExportRefusedError)):
        svc.export_admitted_attachment(case_id)


def test_non_tail_tamper_detected_via_chain() -> None:
    svc, case_id = _svc_case("case-nontail", "cell-nontail")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    ledger = svc.get_ledger(case_id)
    # Tamper first decision (non-tail) — successor's previous should now be stale
    tampered_first = ledger.decisions[0].model_copy(update={"reason": "evil tamper"})
    tampered_ledger = EvidenceReviewLedger(
        case_id=ledger.case_id,
        case_fingerprint=ledger.case_fingerprint,
        decisions=(tampered_first, ledger.decisions[1]),
    )
    # Internal verify must detect stale successor previous
    chain_violations = tampered_ledger.verify()
    assert any("stale previous fingerprint" in v for v in chain_violations)


def test_export_binding_proof() -> None:
    svc, case_id = _svc_case("case-bind", "cell-bind")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    case = svc.get_case(case_id)
    ledger = svc.get_ledger(case_id)
    export = svc.export_admitted_attachment(case_id)
    assert export.attachment.artifact_fingerprint == case.candidate_artifact_fingerprint
    assert export.attachment.cell_id == case.expected_preregistration_cell_id
    assert export.attachment.observed_metric_key == case.observed_metric_key
    assert export.attachment.observed_metric_version == case.observed_metric_version
    assert export.attachment.observed_unit == case.observed_metric_unit
    assert export.attachment.is_admitted is True
    assert export.attachment.admission_label == ArtifactAdmission.ADMITTED
    assert export.ledger_tail_fingerprint == case.ledger_tail_fingerprint == ledger.tail_fingerprint
    assert export.ledger_tail_fingerprint != "0" * 64


def test_case_and_decision_immutability() -> None:
    svc, case_id = _svc_case("case-imm", "cell-imm")
    case = svc.get_case(case_id)
    with pytest.raises(ValidationError):
        case.current_state = EvidenceReviewState.ADMITTED  # type: ignore[misc]
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    ledger = svc.get_ledger(case_id)
    dec = ledger.decisions[0]
    with pytest.raises(ValidationError):
        dec.reason = "mutated"  # type: ignore[misc]


def test_ledger_tuple_immutability_and_defensive_copy() -> None:
    svc, case_id = _svc_case("case-def", "cell-def")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    ledger = svc.get_ledger(case_id)
    assert isinstance(ledger.decisions, tuple)
    # Defensive copy: mutating returned list must not affect service
    cases = svc.list_cases()
    cases.append(cases[0])  # external mutation
    assert len(svc.list_cases()) == 1
    # Mutating returned case copy must not affect stored
    case_copy = svc.get_case(case_id)
    # Frozen so cannot assign, but we can test that a copy is independent
    assert case_copy.model_copy(deep=True).case_id == case_id
    # Direct private access is not used by CSV anymore, but we prove public API
    snapshots = svc.case_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0][0].case_id == case_id


def test_csv_formula_injection_is_sanitized() -> None:
    svc = EvidenceAdmissionInboxService()
    # Use values that are valid identifiers but formula-like; observed_metric_key allows dots etc but we can test via direct CSV sanitise  # noqa: E501
    # The validators for metric_key require non-space characters but allow "=" prefix? _validate_identifier for cell_id requires alphanumeric start, so formula injection via metric_key is allowed because it only checks non-space.  # noqa: E501
    # Let's create cases with dangerous metric values that pass validation (only non-space check)
    svc.create_case(
        case_id="case-formula",
        candidate_artifact_fingerprint=_hex("art-formula"),
        expected_preregistration_cell_id="cell-formula",
        observed_metric_key="=cmd|'/c calc'!A1",
        observed_metric_version="+SUM(1,1)",
        observed_metric_unit="@evil",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-formula"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    csv_text = review_summary_to_csv(svc)
    # Formula-like cells must be prefixed with single quote per sanitise_for_csv
    assert "'=cmd|'/c calc'!A1" in csv_text
    assert "'+SUM(1,1)" in csv_text or "'+SUM" in csv_text
    assert "'@evil" in csv_text
    # Safe normal strings remain unchanged (no extra prefix)
    svc2, _ = _svc_case("case-safe", "cell-safe")
    csv2 = review_summary_to_csv(svc2)
    assert "task.completion.rate" in csv2
    assert "'task.completion.rate" not in csv2


def test_ledger_import_verifies_tamper() -> None:
    svc, case_id = _svc_case("case-import", "cell-import")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    ledger = svc.get_ledger(case_id)
    clean_json = ledger_to_json(ledger)
    # A. clean round-trip succeeds
    assert ledger_from_json(clean_json).tail_fingerprint == ledger.tail_fingerprint

    # B. tamper non-tail decision reason without updating tail — should be refused (chain stale)
    tampered = json.loads(clean_json)
    tampered["decisions"][0]["reason"] = "tampered"
    with pytest.raises(LedgerVerificationError):
        ledger_from_json(json.dumps(tampered))

    # C. tamper tail decision without updating serialized tail — should be refused
    tampered2 = json.loads(clean_json)
    tampered2["decisions"][1]["reason"] = "tampered tail"
    with pytest.raises(LedgerVerificationError):
        ledger_from_json(json.dumps(tampered2))

    # D. tamper decision_count
    tampered3 = json.loads(clean_json)
    tampered3["decision_count"] = 99
    with pytest.raises(LedgerVerificationError):
        ledger_from_json(json.dumps(tampered3))

    # E. tamper tail_fingerprint
    tampered4 = json.loads(clean_json)
    tampered4["tail_fingerprint"] = "f" * 64
    with pytest.raises(LedgerVerificationError):
        ledger_from_json(json.dumps(tampered4))


def test_receipt_rejects_uncommitted_decision_and_tail_mismatch() -> None:
    from traffictwin.evidence_admission.service import build_receipt

    svc, case_id = _svc_case("case-receipt", "cell-receipt")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    case = svc.get_case(case_id)
    ledger = svc.get_ledger(case_id)
    # Valid receipt succeeds
    receipt = build_receipt(case=case, ledger=ledger, decision=ledger.decisions[0])
    assert receipt.decision_id == "dec-1"

    # Unrelated decision B not in ledger
    unrelated = EvidenceReviewDecision(
        decision_id="dec-unrelated",
        case_id=case_id,
        case_fingerprint=ledger.case_fingerprint,
        previous_decision_fingerprint=ledger.tail_fingerprint,
        decision=EvidenceReviewState.WITHDRAWN,
        reason="unrelated",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        requested_information_fields=[],
    )
    with pytest.raises(LedgerVerificationError):
        build_receipt(case=case, ledger=ledger, decision=unrelated)

    # Tail mismatch — case anchor does not match ledger tail
    corrupted_case = case.model_copy(update={"ledger_tail_fingerprint": "f" * 64})
    with pytest.raises(LedgerVerificationError):
        build_receipt(case=corrupted_case, ledger=ledger, decision=ledger.decisions[0])
        # Actually tampered_ledger same as original, but case tail mismatched already; second check is same  # noqa: E501


def test_allow_nan_false_rejects_nan_payload() -> None:
    with pytest.raises(ValueError):
        _fingerprint({"value": float("nan")})


def test_public_snapshot_api_no_private_access() -> None:
    svc, _ = _svc_case("case-public", "cell-public")
    # Ensure service exposes case_snapshots and does not require private _cases for CSV
    snapshots = svc.case_snapshots()
    assert len(snapshots) == 1
    # CSV uses only public API (we verified via implementation); just ensure it works without private access  # noqa: E501
    csv_text = review_summary_to_csv(svc)
    assert "case-public" in csv_text


def test_allowed_transitions_from_authoritative() -> None:
    assert set(allowed_transitions_from(EvidenceReviewState.PENDING)) == {
        EvidenceReviewState.NEEDS_INFORMATION,
        EvidenceReviewState.ADMITTED,
        EvidenceReviewState.REJECTED,
    }
    assert set(allowed_transitions_from(EvidenceReviewState.NEEDS_INFORMATION)) == {
        EvidenceReviewState.PENDING,
        EvidenceReviewState.ADMITTED,
        EvidenceReviewState.REJECTED,
    }
    assert set(allowed_transitions_from(EvidenceReviewState.ADMITTED)) == {
        EvidenceReviewState.WITHDRAWN
    }
    assert set(allowed_transitions_from(EvidenceReviewState.REJECTED)) == {
        EvidenceReviewState.PENDING
    }
    assert set(allowed_transitions_from(EvidenceReviewState.WITHDRAWN)) == set()


def test_queue_helpers_derive_from_ledger() -> None:
    svc, case_id = _svc_case("case-queue", "cell-queue")
    # Initially pending via ledger None -> pending
    assert len(svc.pending_queue()) == 1
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    assert len(svc.pending_queue()) == 0
    assert len(svc.needs_information_queue()) == 1


def test_verify_case_with_ledger_documents_case_only_limitation() -> None:
    svc, case_id = _svc_case("case-verify", "cell-verify")
    case = svc.get_case(case_id)
    ledger = svc.get_ledger(case_id)
    # Case alone cannot verify history; helper returns violations if mismatch
    assert verify_case_with_ledger(case, ledger) == []
    # Corrupted case should show violation
    corrupted = case.model_copy(update={"current_state": EvidenceReviewState.ADMITTED})
    assert verify_case_with_ledger(corrupted, ledger) != []


def test_export_refusal_message_is_human_readable() -> None:
    """Regression: export refusal renders real ledger state and no code fragments."""
    # Rejected ledger → message must contain rejected + admitted, no fragments
    svc, case_id = _svc_case("case-refusal-rej", "cell-refusal-rej")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.REJECTED,
        reason="rights restricted",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    with pytest.raises(ExportRefusedError) as exc_rejected:
        svc.export_admitted_attachment(case_id)
    msg_rej = str(exc_rejected.value)
    assert "rejected" in msg_rej
    assert "admitted" in msg_rej
    assert "if present" not in msg_rej
    assert "else None" not in msg_rej
    assert "export refused" in msg_rej.lower()

    # Pending empty ledger → unavailable, no fragments
    svc2, case_id2 = _svc_case("case-refusal-pending", "cell-refusal-pending")
    with pytest.raises(ExportRefusedError) as exc_pending:
        svc2.export_admitted_attachment(case_id2)
    msg_pend = str(exc_pending.value)
    assert "export refused" in msg_pend.lower()
    assert "unavailable" in msg_pend.lower() or "no admission" in msg_pend.lower()
    assert "if present" not in msg_pend
    assert "else None" not in msg_pend


def test_duplicate_case_id_refuses_and_is_transactional() -> None:
    """B1: duplicate case_id must be refused before any mutation; original ledger preserved."""
    from traffictwin.evidence_admission.service import DuplicateBindingError, DuplicateCaseError

    svc, case_id = _svc_case("case-dup", "cellA")
    artifact_a = _hex("art-case-dup")
    # Admit original
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit original",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    assert svc.export_admitted_attachment(case_id).attachment.is_admitted is True
    original_case = svc.get_case(case_id)
    original_ledger = svc.get_ledger(case_id)
    original_tail = original_ledger.tail_fingerprint
    original_cell = original_case.expected_preregistration_cell_id
    assert original_cell == "cellA"
    assert original_ledger.current_state == EvidenceReviewState.ADMITTED

    # Attempt duplicate case_id with different cellB (same artifact)
    with pytest.raises(DuplicateCaseError, match="duplicate case_id"):
        svc.create_case(
            case_id=case_id,
            candidate_artifact_fingerprint=artifact_a,
            expected_preregistration_cell_id="cellB",
            observed_metric_key="task.completion.rate",
            observed_metric_version="1.0",
            observed_metric_unit="ratio",
            evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
            source_contract_result_fingerprint=_hex("con-case-dup"),
            rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
            validation_standing=ValidationStanding.VALIDATED,
            compatibility_standing=CompatibilityStanding.COMPATIBLE,
            created_at=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        )

    # Transactional: original unchanged
    assert svc.get_case(case_id).expected_preregistration_cell_id == "cellA"
    assert svc.get_ledger(case_id).tail_fingerprint == original_tail
    assert svc.get_ledger(case_id).current_state == EvidenceReviewState.ADMITTED
    assert svc.export_admitted_attachment(case_id).attachment.cell_id == "cellA"

    # Binding index consistency: old binding still occupied, new binding free
    with pytest.raises(DuplicateBindingError, match="duplicate cell/candidate binding"):
        svc.create_case(
            case_id="other-case",
            candidate_artifact_fingerprint=artifact_a,
            expected_preregistration_cell_id="cellA",
            observed_metric_key="task.completion.rate",
            observed_metric_version="1.0",
            observed_metric_unit="ratio",
            evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
            source_contract_result_fingerprint=_hex("con-other"),
            rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
            validation_standing=ValidationStanding.VALIDATED,
            compatibility_standing=CompatibilityStanding.COMPATIBLE,
            created_at=datetime(2026, 8, 10, 12, 3, tzinfo=UTC),
        )
    # New binding with different case_id should succeed (was not inserted by failed attempt)
    new_case = svc.create_case(
        case_id="new-case",
        candidate_artifact_fingerprint=artifact_a,
        expected_preregistration_cell_id="cellB",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-new"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 4, tzinfo=UTC),
    )
    assert new_case.case_id == "new-case"
    assert new_case.expected_preregistration_cell_id == "cellB"
    # Also duplicate case_id with same binding must still be refused
    with pytest.raises(DuplicateCaseError):
        svc.create_case(
            case_id=case_id,
            candidate_artifact_fingerprint=artifact_a,
            expected_preregistration_cell_id="cellA",
            observed_metric_key="task.completion.rate",
            observed_metric_version="1.0",
            observed_metric_unit="ratio",
            evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
            source_contract_result_fingerprint=_hex("con-dup2"),
            rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
            validation_standing=ValidationStanding.VALIDATED,
            compatibility_standing=CompatibilityStanding.COMPATIBLE,
        )


def test_review_summary_csv_fails_closed_on_inconsistent_pair_and_uses_ledger_state() -> None:
    """B2 CSV: valid admitted row uses ledger state; inconsistent pair refuses entire CSV."""
    svc, case_id = _svc_case("case-csv-ok", "cell-csv-ok")
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    csv_text = review_summary_to_csv(svc)
    assert "case-csv-ok" in csv_text
    assert "admitted" in csv_text
    # Parse typed CSV column rather than raw substring
    import csv
    import io

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert any(
        r["case_id"] == "case-csv-ok"
        and r["current_state"] == "admitted"
        and r["decision_count"] == "1"
        for r in rows
    )

    # Construct inconsistent cached state: case says admitted but ledger empty
    svc2, case_id2 = _svc_case("case-csv-bad", "cell-csv-bad")
    assert svc2.get_ledger(case_id2).current_state is None
    case2 = svc2.get_case(case_id2)
    corrupted = case2.model_copy(update={"current_state": EvidenceReviewState.ADMITTED})
    svc2._cases[case_id2] = type(svc2._cases[case_id2])(
        case=corrupted, ledger=svc2.get_ledger(case_id2)
    )
    with pytest.raises(LedgerVerificationError):
        review_summary_to_csv(svc2)

    # Also ledger-derived state: pending empty should write pending, not cached
    svc3, case_id3 = _svc_case("case-csv-pending", "cell-csv-pending")
    csv3 = review_summary_to_csv(svc3)
    assert "pending" in csv3


def test_cli_duplicate_case_id_is_refused_and_original_remains() -> None:
    """B1 CLI: create-demo duplicate case_id refused, original export still succeeds."""
    from typer.testing import CliRunner

    from traffictwin.evidence_admission.cli import app
    from traffictwin.evidence_admission.service import reset_global_service

    runner = CliRunner()
    reset_global_service()

    # create-demo c1 cellA
    result = runner.invoke(app, ["create-demo", "c1", "cellA"])
    assert result.exit_code == 0, result.output + (result.stderr or "")

    # decide admitted
    result = runner.invoke(
        app, ["decide", "c1", "admitted", "--reason", "admit", "--reviewer", "r1"]
    )
    assert result.exit_code == 0, result.output + (result.stderr or "")

    # export succeeds
    result = runner.invoke(app, ["export", "c1"])
    assert result.exit_code == 0, result.output + (result.stderr or "")
    assert "admitted" in result.output.lower()

    # duplicate create-demo c1 cellB should be refused
    result = runner.invoke(app, ["create-demo", "c1", "cellB"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "duplicate case_id" in combined.lower()
    assert (
        "cannot be replaced" in combined.lower()
        or "already exists" in combined.lower()
        or "duplicate" in combined.lower()
    )

    # original export still succeeds
    result = runner.invoke(app, ["export", "c1"])
    assert result.exit_code == 0
    assert "cellA" in result.output

    # ledger decision_count retained
    result = runner.invoke(app, ["ledger", "c1"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["decision_count"] == 1
    assert payload["case_id"] == "c1"

    reset_global_service()


def test_cli_receipt_unknown_decision_reports_deterministic_error() -> None:
    """Q5: CLI receipt unknown decision id must have real error, not blank."""
    from typer.testing import CliRunner

    from traffictwin.evidence_admission.cli import app
    from traffictwin.evidence_admission.service import reset_global_service

    runner = CliRunner()
    reset_global_service()
    runner.invoke(app, ["create-demo", "c1", "cellA"])
    runner.invoke(app, ["decide", "c1", "admitted", "--reason", "admit", "--reviewer", "r1"])
    result = runner.invoke(app, ["receipt", "c1", "does-not-exist"])
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "does-not-exist" in combined
    assert "not found" in combined.lower()
    assert "c1" in combined
    assert result.stdout.count("\n") < 10  # no traceback dump
    reset_global_service()
