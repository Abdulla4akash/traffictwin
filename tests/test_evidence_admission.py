"""Focused unit and integration tests for the Evidence Admission Inbox.

Covers deterministic ledger chain, duplicate decision refusal, stale parent
refusal, invalid transition refusal, fail-closed export guards, duplicate
cell/candidate binding, deterministic identity, and adversarial inputs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest

from traffictwin.evidence_admission.models import (
    CompatibilityStanding,
    EvidenceMode,
    EvidenceReviewFinding,
    EvidenceReviewState,
    FindingCategory,
    FindingSeverity,
    RightsPrivacyStanding,
    ValidationStanding,
)
from traffictwin.evidence_admission.service import (
    DuplicateBindingError,
    DuplicateDecisionError,
    EvidenceAdmissionInboxService,
    ExportRefusedError,
    StaleParentError,
    TransitionRefusedError,
    admitted_attachment_to_json,
    build_receipt,
    case_to_json,
    ledger_to_json,
    receipt_to_json,
    review_summary_to_csv,
)
from traffictwin.preregistration.models import ArtifactAdmission


def _hex(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _service_with_case(
    case_id: str = "case-1",
    cell_id: str = "cell-1",
    metric_key: str = "task.completion.rate",
    metric_version: str = "1.0",
    unit: str = "ratio",
    artifact_seed: str = "artifact-1",
    contract_seed: str = "contract-1",
    compatibility: CompatibilityStanding = CompatibilityStanding.COMPATIBLE,
    rights: RightsPrivacyStanding = RightsPrivacyStanding.ALLOWED,
    validation: ValidationStanding = ValidationStanding.VALIDATED,
) -> tuple[EvidenceAdmissionInboxService, str]:
    svc = EvidenceAdmissionInboxService()
    svc.create_case(
        case_id=case_id,
        candidate_artifact_fingerprint=_hex(artifact_seed),
        expected_preregistration_cell_id=cell_id,
        observed_metric_key=metric_key,
        observed_metric_version=metric_version,
        observed_metric_unit=unit,
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex(contract_seed),
        rights_privacy_standing=rights,
        validation_standing=validation,
        compatibility_standing=compatibility,
        findings=[
            EvidenceReviewFinding(
                code="finding_1",
                category=FindingCategory.VALIDATION,
                severity=FindingSeverity.INFO,
                description="Validation passed; pending human review.",
            )
        ],
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    return svc, case_id


# ---------------------------------------------------------------------------
# Deterministic ledger chain
# ---------------------------------------------------------------------------


def test_deterministic_ledger_chain_is_stable() -> None:
    svc, case_id = _service_with_case()
    ledger = svc.get_ledger(case_id)
    genesis = "0" * 64
    assert ledger.tail_fingerprint == genesis

    d1 = svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need missing denominator detail",
        reviewer_label="reviewer-a",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["denominator_detail"],
    )
    # First decision previous must be genesis
    assert d1.previous_decision_fingerprint == genesis
    # Fingerprint deterministic
    fp1 = d1.fingerprint()
    assert fp1 == d1.fingerprint()

    d2 = svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.ADMITTED,
        reason="information received, rights and validation clear",
        reviewer_label="reviewer-b",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    assert d2.previous_decision_fingerprint == fp1

    # Ledger tail is last decision's fingerprint
    assert svc.get_ledger(case_id).tail_fingerprint == d2.fingerprint()

    # Deterministic JSON: re-serialise gives same fingerprint chain
    json1 = ledger_to_json(svc.get_ledger(case_id))
    json2 = ledger_to_json(svc.get_ledger(case_id))
    assert json1 == json2

    # Re-create identical second service and verify identical fingerprints
    svc2, _ = _service_with_case()
    svc2.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need missing denominator detail",
        reviewer_label="reviewer-a",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["denominator_detail"],
    )
    svc2.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.ADMITTED,
        reason="information received, rights and validation clear",
        reviewer_label="reviewer-b",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    assert svc.get_ledger(case_id).tail_fingerprint == svc2.get_ledger(case_id).tail_fingerprint


def test_ledger_verify_detects_no_violations_on_clean_chain() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="rights allowed, validation passed, compatible",
        reviewer_label="reviewer-a",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    assert svc.get_ledger(case_id).verifies() is True
    assert svc.verify_ledger(case_id) == []


# ---------------------------------------------------------------------------
# Duplicate decision ID refusal
# ---------------------------------------------------------------------------


def test_duplicate_decision_id_is_refused() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    with pytest.raises(DuplicateDecisionError, match="duplicate decision_id"):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-1",
            decision=EvidenceReviewState.ADMITTED,
            reason="second",
            reviewer_label="r2",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        )


# ---------------------------------------------------------------------------
# Stale decision parent refusal
# ---------------------------------------------------------------------------


def test_stale_parent_fingerprint_is_refused() -> None:
    svc, case_id = _service_with_case()
    _d1 = svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    # Correct parent is d1's fingerprint; provide stale genesis instead
    with pytest.raises(StaleParentError, match="stale previous fingerprint"):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-2",
            decision=EvidenceReviewState.ADMITTED,
            reason="admit",
            reviewer_label="r2",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
            previous_decision_fingerprint="0" * 64,
        )
    # Also stale random fingerprint
    with pytest.raises(StaleParentError):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-2",
            decision=EvidenceReviewState.ADMITTED,
            reason="admit",
            reviewer_label="r2",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
            previous_decision_fingerprint="a" * 64,
        )


# ---------------------------------------------------------------------------
# Invalid transition refusal
# ---------------------------------------------------------------------------


def test_invalid_transition_is_refused() -> None:
    svc, case_id = _service_with_case()
    # pending -> withdrawn is not allowed
    with pytest.raises(TransitionRefusedError, match="not allowed"):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-bad",
            decision=EvidenceReviewState.WITHDRAWN,
            reason="withdraw directly from pending — not allowed",
            reviewer_label="r1",
            decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        )
    # valid pending -> admitted
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    # admitted -> rejected is not allowed
    with pytest.raises(TransitionRefusedError):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-2",
            decision=EvidenceReviewState.REJECTED,
            reason="reject from admitted",
            reviewer_label="r2",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        )
    # admitted -> needs_information is not allowed
    with pytest.raises(TransitionRefusedError):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-2",
            decision=EvidenceReviewState.NEEDS_INFORMATION,
            reason="needs info from admitted",
            reviewer_label="r2",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        )
    # withdrawn is terminal — no further transition
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.WITHDRAWN,
        reason="withdraw admission",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    with pytest.raises(TransitionRefusedError):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-3",
            decision=EvidenceReviewState.PENDING,
            reason="reopen withdrawn",
            reviewer_label="r3",
            decision_timestamp=datetime(2026, 8, 10, 12, 3, tzinfo=UTC),
        )


def test_rejected_can_only_reopen_to_pending() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.REJECTED,
        reason="not compatible",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    # rejected -> pending (reopen) is allowed
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.PENDING,
        reason="reopen after additional evidence",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    assert svc.get_case(case_id).current_state == EvidenceReviewState.PENDING
    # rejected -> admitted directly is refused (need to go via pending)
    svc2, case2 = _service_with_case(
        case_id="case-rej", artifact_seed="art-rej", contract_seed="con-rej"
    )
    svc2.append_decision(
        case_id=case2,
        decision_id="dec-1",
        decision=EvidenceReviewState.REJECTED,
        reason="reject",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    with pytest.raises(TransitionRefusedError):
        svc2.append_decision(
            case_id=case2,
            decision_id="dec-2",
            decision=EvidenceReviewState.ADMITTED,
            reason="admit directly from rejected",
            reviewer_label="r2",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        )


# ---------------------------------------------------------------------------
# Export guards — fail-closed
# ---------------------------------------------------------------------------


def test_pending_cannot_export() -> None:
    svc, case_id = _service_with_case()
    # Still pending, no decision — human-readable unavailable, not code fragment
    with pytest.raises(ExportRefusedError, match="unavailable"):
        svc.export_admitted_attachment(case_id)
    # Pending -> needs_information still not admitted
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    with pytest.raises(ExportRefusedError):
        svc.export_admitted_attachment(case_id)


def test_rejected_cannot_export() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.REJECTED,
        reason="rights restricted",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    with pytest.raises(ExportRefusedError, match="admitted"):
        svc.export_admitted_attachment(case_id)


def test_withdrawn_admission_cannot_export() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    # Export now succeeds
    exp = svc.export_admitted_attachment(case_id)
    assert exp.attachment.is_admitted is True
    assert exp.attachment.admission_label == ArtifactAdmission.ADMITTED

    # Withdraw the admission
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.WITHDRAWN,
        reason="withdraw after re-review",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    with pytest.raises(ExportRefusedError, match="admitted"):
        svc.export_admitted_attachment(case_id)


def test_admitted_compatible_case_exports() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="rights allowed, validation validated, compatible",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    export = svc.export_admitted_attachment(case_id)
    assert export.attachment.is_admitted is True
    assert export.attachment.admission_label == ArtifactAdmission.ADMITTED
    assert (
        export.attachment.artifact_fingerprint
        == svc.get_case(case_id).candidate_artifact_fingerprint
    )
    assert export.attachment.cell_id == svc.get_case(case_id).expected_preregistration_cell_id
    assert export.attachment.observed_metric_key == svc.get_case(case_id).observed_metric_key
    assert (
        export.attachment.observed_metric_version == svc.get_case(case_id).observed_metric_version
    )
    assert export.attachment.observed_unit == svc.get_case(case_id).observed_metric_unit
    # Export fingerprint deterministic
    assert export.fingerprint == export.computed_fingerprint()
    # Portable JSON contains no local path
    j = admitted_attachment_to_json(export)
    assert "/Users" not in j
    assert "/private/tmp" not in j


def test_metric_mismatch_blocks_export() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    with pytest.raises(ExportRefusedError, match="metric key mismatch"):
        svc.export_admitted_attachment(case_id, metric_key="other.metric")
    with pytest.raises(ExportRefusedError, match="metric version mismatch"):
        svc.export_admitted_attachment(case_id, metric_version="9.9")
    with pytest.raises(ExportRefusedError, match="observed unit mismatch"):
        svc.export_admitted_attachment(case_id, metric_unit="wrong-unit")
    with pytest.raises(ExportRefusedError, match="artifact fingerprint does not match"):
        svc.export_admitted_attachment(case_id, artifact_fingerprint="a" * 64)
    with pytest.raises(ExportRefusedError, match="cell binding has changed"):
        svc.export_admitted_attachment(case_id, cell_id="other-cell")


def test_needs_information_then_admitted_can_export() -> None:
    svc, case_id = _service_with_case()
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
        reason="info received",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    export = svc.export_admitted_attachment(case_id)
    assert export.attachment.is_admitted is True


# ---------------------------------------------------------------------------
# Duplicate cell/candidate binding refused
# ---------------------------------------------------------------------------


def test_duplicate_cell_candidate_binding_is_refused() -> None:
    svc, _ = _service_with_case(case_id="case-a", cell_id="cell-X", artifact_seed="artifact-same")
    with pytest.raises(DuplicateBindingError, match="duplicate cell/candidate binding"):
        svc.create_case(
            case_id="case-b",
            candidate_artifact_fingerprint=_hex("artifact-same"),
            expected_preregistration_cell_id="cell-X",
            observed_metric_key="task.completion.rate",
            observed_metric_version="1.0",
            observed_metric_unit="ratio",
            evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
            source_contract_result_fingerprint=_hex("contract-other"),
            rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
            validation_standing=ValidationStanding.VALIDATED,
            compatibility_standing=CompatibilityStanding.COMPATIBLE,
            created_at=datetime(2026, 8, 10, 12, 5, tzinfo=UTC),
        )
    # Different cell is allowed
    svc.create_case(
        case_id="case-c",
        candidate_artifact_fingerprint=_hex("artifact-same"),
        expected_preregistration_cell_id="cell-Y",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("contract-other2"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 6, tzinfo=UTC),
    )
    assert len(svc.list_cases()) == 2


# ---------------------------------------------------------------------------
# Deterministic identity proofs
# ---------------------------------------------------------------------------


def test_case_fingerprint_deterministic_across_identical_bindings() -> None:
    svc1, case_id = _service_with_case(
        case_id="case-det", artifact_seed="det-art", contract_seed="det-con"
    )
    case1 = svc1.get_case(case_id)
    fp1 = case1.fingerprint()
    # Build second service with same bindings — fingerprint must match
    svc2, _ = _service_with_case(
        case_id="case-det", artifact_seed="det-art", contract_seed="det-con"
    )
    case2 = svc2.get_case("case-det")
    assert case2.fingerprint() == fp1
    # Case JSON deterministic
    assert case_to_json(case1) == case_to_json(case2)


def test_ledger_json_is_deterministic() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit deterministic",
        reviewer_label="reviewer-x",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    ledger = svc.get_ledger(case_id)
    assert ledger_to_json(ledger) == ledger_to_json(ledger)


def test_no_local_path_in_exports() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="reviewer-local",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    case = svc.get_case(case_id)
    ledger = svc.get_ledger(case_id)
    export = svc.export_admitted_attachment(case_id)
    # Build receipt to check
    receipt = build_receipt(case=case, ledger=ledger, decision=ledger.decisions[0])
    for j in (
        case_to_json(case),
        ledger_to_json(ledger),
        admitted_attachment_to_json(export),
        receipt_to_json(receipt),
    ):
        assert "/Users/akashx" not in j
        assert "/private" not in j
        assert "credential" not in j.lower()


# ---------------------------------------------------------------------------
# Review summary CSV
# ---------------------------------------------------------------------------


def test_review_summary_csv_is_deterministic_and_tabular() -> None:
    svc, case1 = _service_with_case(case_id="case-1", cell_id="cell-1")
    svc2_cases = [
        ("case-2", "cell-2", EvidenceReviewState.REJECTED),
        ("case-3", "cell-3", EvidenceReviewState.NEEDS_INFORMATION),
    ]
    for cid, cell, state in svc2_cases:
        svc.create_case(
            case_id=cid,
            candidate_artifact_fingerprint=_hex(f"art-{cid}"),
            expected_preregistration_cell_id=cell,
            observed_metric_key="task.completion.rate",
            observed_metric_version="1.0",
            observed_metric_unit="ratio",
            evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
            source_contract_result_fingerprint=_hex(f"con-{cid}"),
            rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
            validation_standing=ValidationStanding.VALIDATED,
            compatibility_standing=CompatibilityStanding.COMPATIBLE,
            created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        )
        if state == EvidenceReviewState.REJECTED:
            svc.append_decision(
                case_id=cid,
                decision_id=f"dec-{cid}-1",
                decision=state,
                reason="reject",
                reviewer_label="r",
                decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
            )
        elif state == EvidenceReviewState.NEEDS_INFORMATION:
            svc.append_decision(
                case_id=cid,
                decision_id=f"dec-{cid}-1",
                decision=state,
                reason="need info",
                reviewer_label="r",
                decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
                requested_information_fields=["field_a"],
            )

    csv1 = review_summary_to_csv(svc)
    csv2 = review_summary_to_csv(svc)
    assert csv1 == csv2
    lines = csv1.strip().split("\n")
    assert lines[0].startswith("case_id,")
    # header + 3 rows
    assert len(lines) == 4


# ---------------------------------------------------------------------------
# Receipt without credential data
# ---------------------------------------------------------------------------


def test_receipt_has_no_credential_or_path_data() -> None:
    svc, case_id = _service_with_case()
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit for receipt",
        reviewer_label="pseudonymous-reviewer-07",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    case = svc.get_case(case_id)
    ledger = svc.get_ledger(case_id)
    receipt = build_receipt(case=case, ledger=ledger, decision=ledger.decisions[0])
    j = receipt_to_json(receipt)
    payload = json.loads(j)
    # Receipt must carry pseudonymous reviewer label, not a private path
    assert payload["reviewer_label"] == "pseudonymous-reviewer-07"
    assert "/Users" not in j
    assert "password" not in j.lower()
    assert payload["fingerprint"] == receipt.computed_fingerprint()


# ---------------------------------------------------------------------------
# Adversarial / negative tests
# ---------------------------------------------------------------------------


def test_adversarial_reviewer_label_with_path_is_stored_but_not_in_fingerprint_path_contamination() -> (  # noqa: E501
    None
):
    svc, case_id = _service_with_case()
    # Reviewer label is bounded and validated, but its value is not a path in exports beyond the label itself.  # noqa: E501
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="reviewer-allowed",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    # Attempt to create a case with an illegal reviewer-like string that would be a path — but the case creation  # noqa: E501
    # itself does not take reviewer; the decision does. An illegal reviewer label shape with slash would fail validation.  # noqa: E501
    with pytest.raises(ValueError):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-2",
            decision=EvidenceReviewState.WITHDRAWN,
            reason="withdraw",
            reviewer_label="/private/tmp/evil",
            decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        )


def test_bounded_requested_fields_rejected_when_too_many() -> None:
    svc, case_id = _service_with_case()
    with pytest.raises(ValueError):
        svc.append_decision(
            case_id=case_id,
            decision_id="dec-1",
            decision=EvidenceReviewState.NEEDS_INFORMATION,
            reason="need info with too many fields",
            reviewer_label="r1",
            decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
            requested_information_fields=[f"field_{i}" for i in range(20)],
        )


def test_incompatible_compatibility_standing_blocks_export() -> None:
    svc, case_id = _service_with_case(compatibility=CompatibilityStanding.INCOMPATIBLE)
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit even though incompatible — should still be blocked at export",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    with pytest.raises(ExportRefusedError, match="compatibility standing is"):
        svc.export_admitted_attachment(case_id)


# ---------------------------------------------------------------------------
# Export-guard test used for mutation: removing latest-state check must cause failure
# ---------------------------------------------------------------------------


def test_export_guard_remains_fail_closed_for_pending_and_withdrawn() -> None:
    """This test must fail if the latest-state admission requirement is removed."""
    svc, case_id = _service_with_case()
    # Pending must not export
    with pytest.raises(ExportRefusedError):
        svc.export_admitted_attachment(case_id)
    # Admit then withdraw -> withdrawn must not export
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    assert svc.export_admitted_attachment(case_id).attachment.is_admitted is True
    svc.append_decision(
        case_id=case_id,
        decision_id="dec-2",
        decision=EvidenceReviewState.WITHDRAWN,
        reason="withdraw",
        reviewer_label="r2",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    with pytest.raises(ExportRefusedError):
        svc.export_admitted_attachment(case_id)
