"""Append-only ledger and human-review service for the Evidence Admission Inbox.

Business logic lives outside Streamlit. Every decision is hash-chained and
append-only; in-place editing is never permitted. Export is fail-closed and
requires the latest state to be admitted, matching fingerprints, compatible
metric identity, an unchanged cell binding, no newer withdrawal, and a verified
ledger. Validation is not admission.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from traffictwin.evidence_admission.models import (
    CompatibilityStanding,
    EvidenceAdmissionExport,
    EvidenceCandidateBinding,
    EvidenceMode,
    EvidenceReviewCase,
    EvidenceReviewDecision,
    EvidenceReviewFinding,
    EvidenceReviewLedger,
    EvidenceReviewReceipt,
    EvidenceReviewState,
    RightsPrivacyStanding,
    ValidationStanding,
    _fingerprint,
)
from traffictwin.preregistration.models import ArtifactAdmission, EvidenceAttachment

# ---------------------------------------------------------------------------
# Errors (explicit unavailable/refused states, fail-closed)
# ---------------------------------------------------------------------------


class EvidenceAdmissionError(ValueError):
    """Base refused/unavailable error for the inbox service."""


class DuplicateBindingError(EvidenceAdmissionError):
    """Duplicate cell/candidate binding refused."""


class DuplicateDecisionError(EvidenceAdmissionError):
    """Duplicate decision ID refused."""


class StaleParentError(EvidenceAdmissionError):
    """Stale previous fingerprint refused."""


class TransitionRefusedError(EvidenceAdmissionError):
    """Invalid state transition refused."""


class LedgerVerificationError(EvidenceAdmissionError):
    """Ledger does not verify."""


class ExportRefusedError(EvidenceAdmissionError):
    """Export fails closed because admission preconditions are not met."""


# ---------------------------------------------------------------------------
# Allowed transitions (fail-closed)
# ---------------------------------------------------------------------------

_ALLOWED: set[tuple[EvidenceReviewState, EvidenceReviewState]] = {
    (EvidenceReviewState.PENDING, EvidenceReviewState.NEEDS_INFORMATION),
    (EvidenceReviewState.PENDING, EvidenceReviewState.ADMITTED),
    (EvidenceReviewState.PENDING, EvidenceReviewState.REJECTED),
    (EvidenceReviewState.NEEDS_INFORMATION, EvidenceReviewState.PENDING),
    (EvidenceReviewState.NEEDS_INFORMATION, EvidenceReviewState.ADMITTED),
    (EvidenceReviewState.NEEDS_INFORMATION, EvidenceReviewState.REJECTED),
    (EvidenceReviewState.ADMITTED, EvidenceReviewState.WITHDRAWN),
    (EvidenceReviewState.REJECTED, EvidenceReviewState.PENDING),
}

_GENESIS = "0" * 64


def _utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# In-memory inbox store
# ---------------------------------------------------------------------------


@dataclass
class _StoredCase:
    case: EvidenceReviewCase
    ledger: EvidenceReviewLedger


class EvidenceAdmissionInboxService:
    """In-memory human-review queue with hash-chained ledgers.

    This service holds cases and their append-only ledgers. It never
    automatically admits evidence, never zero-fills missing evidence,
    and never exposes local paths in exported fingerprints.
    """

    def __init__(self) -> None:
        self._cases: dict[str, _StoredCase] = {}
        self._binding_index: dict[tuple[str, str], str] = {}

    # -- cases ---------------------------------------------------------------

    def create_case(
        self,
        *,
        case_id: str,
        candidate_artifact_fingerprint: str,
        expected_preregistration_cell_id: str,
        observed_metric_key: str,
        observed_metric_version: str,
        observed_metric_unit: str,
        evidence_mode: EvidenceMode,
        source_contract_result_fingerprint: str,
        rights_privacy_standing: RightsPrivacyStanding,
        validation_standing: ValidationStanding,
        compatibility_standing: CompatibilityStanding,
        findings: list[EvidenceReviewFinding] | None = None,
        created_at: datetime | None = None,
    ) -> EvidenceReviewCase:
        """Create a new pending case, refusing duplicate cell/candidate bindings."""
        binding_key = (
            candidate_artifact_fingerprint.strip().lower(),
            expected_preregistration_cell_id.strip(),
        )
        if binding_key in self._binding_index:
            raise DuplicateBindingError(
                f"duplicate cell/candidate binding refused: cell {expected_preregistration_cell_id!r} "  # noqa: E501
                f"already bound to case {self._binding_index[binding_key]!r}"
            )
        ts = (
            (created_at.astimezone(UTC) if created_at is not None else _utc_now())
            if True
            else _utc_now()
        )
        # Normalize hex lower
        cand_fp = candidate_artifact_fingerprint.strip().lower()
        src_fp = source_contract_result_fingerprint.strip().lower()
        case = EvidenceReviewCase(
            case_id=case_id,
            candidate_artifact_fingerprint=cand_fp,
            expected_preregistration_cell_id=expected_preregistration_cell_id,
            observed_metric_key=observed_metric_key,
            observed_metric_version=observed_metric_version,
            observed_metric_unit=observed_metric_unit,
            evidence_mode=evidence_mode,
            source_contract_result_fingerprint=src_fp,
            rights_privacy_standing=rights_privacy_standing,
            validation_standing=validation_standing,
            compatibility_standing=compatibility_standing,
            findings=list(findings or []),
            current_state=EvidenceReviewState.PENDING,
            created_at=ts,
            updated_at=ts,
            candidate_binding=EvidenceCandidateBinding(
                candidate_artifact_fingerprint=cand_fp,
                expected_preregistration_cell_id=expected_preregistration_cell_id,
                observed_metric_key=observed_metric_key,
                observed_metric_version=observed_metric_version,
                observed_metric_unit=observed_metric_unit,
                evidence_mode=evidence_mode,
                source_contract_result_fingerprint=src_fp,
            ),
            ledger_tail_fingerprint=_GENESIS,
        )
        case_fp = case.fingerprint()
        ledger = EvidenceReviewLedger(case_id=case.case_id, case_fingerprint=case_fp, decisions=[])
        self._cases[case.case_id] = _StoredCase(case=case, ledger=ledger)
        self._binding_index[binding_key] = case.case_id
        return case

    def get_case(self, case_id: str) -> EvidenceReviewCase:
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        return stored.case

    def get_ledger(self, case_id: str) -> EvidenceReviewLedger:
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        return stored.ledger

    def list_cases(self) -> list[EvidenceReviewCase]:
        return [s.case for s in self._cases.values()]

    def list_ledgers(self) -> list[EvidenceReviewLedger]:
        return [s.ledger for s in self._cases.values()]

    # -- decisions -----------------------------------------------------------

    def append_decision(
        self,
        *,
        case_id: str,
        decision_id: str,
        decision: EvidenceReviewState,
        reason: str,
        reviewer_label: str,
        decision_timestamp: datetime | None = None,
        requested_information_fields: list[str] | None = None,
        previous_decision_fingerprint: str | None = None,
    ) -> EvidenceReviewDecision:
        """Append one immutable decision, refusing duplicates, stale parents, and bad transitions."""  # noqa: E501
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        ledger = stored.ledger
        case = stored.case

        # Duplicate decision ID refusal (across this ledger)
        if any(d.decision_id == decision_id for d in ledger.decisions):
            raise DuplicateDecisionError(f"duplicate decision_id {decision_id!r} refused")
        # Also guard global duplicate across all ledgers? keep per-ledger as spec.

        expected_prev = ledger.tail_fingerprint
        provided_prev = (
            previous_decision_fingerprint.strip().lower()
            if previous_decision_fingerprint is not None
            else expected_prev
        )
        if provided_prev != expected_prev:
            raise StaleParentError(
                f"stale previous fingerprint refused: expected {expected_prev[:8]}… "  # noqa: E501
                f"got {provided_prev[:8]}…"  # noqa: E501
            )

        # Invalid transition refusal (fail-closed)
        current = case.current_state
        if (current, decision) not in _ALLOWED:
            raise TransitionRefusedError(
                f"transition {current.value!r} -> {decision.value!r} is not allowed"
            )

        ts = decision_timestamp.astimezone(UTC) if decision_timestamp is not None else _utc_now()

        entry = EvidenceReviewDecision(
            decision_id=decision_id,
            case_id=case_id,
            case_fingerprint=ledger.case_fingerprint,
            previous_decision_fingerprint=expected_prev,
            decision=decision,
            reason=reason,
            reviewer_label=reviewer_label,
            decision_timestamp=ts,
            requested_information_fields=list(requested_information_fields or []),
        )
        # Verify entry fingerprint chain link before mutating
        # (The entry's previous must equal the previous tail exactly.)
        new_decisions = list(ledger.decisions) + [entry]
        new_ledger = EvidenceReviewLedger(
            case_id=ledger.case_id,
            case_fingerprint=ledger.case_fingerprint,
            decisions=new_decisions,
        )
        violations = new_ledger.verify()
        if violations:
            raise LedgerVerificationError("; ".join(violations))

        # Update stored case and ledger atomically
        updated_case = case.model_copy(
            update={
                "current_state": decision,
                "updated_at": ts,
                "ledger_tail_fingerprint": new_ledger.tail_fingerprint,
            }
        )
        self._cases[case_id] = _StoredCase(case=updated_case, ledger=new_ledger)
        return entry

    def verify_ledger(self, case_id: str) -> list[str]:
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        return stored.ledger.verify()

    # -- export --------------------------------------------------------------

    def export_admitted_attachment(
        self,
        case_id: str,
        *,
        clock: datetime | None = None,
        artifact_fingerprint: str | None = None,
        cell_id: str | None = None,
        metric_key: str | None = None,
        metric_version: str | None = None,
        metric_unit: str | None = None,
    ) -> EvidenceAdmissionExport:
        """Export an admitted EvidenceAttachment, fail-closed.

        Guards:
        - latest case state is admitted
        - artifact fingerprint matches reviewed candidate
        - cell binding is unchanged
        - metric/version/unit remain compatible
        - no newer withdrawal exists (implied by latest==admitted)
        - ledger verifies
        """
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        case = stored.case
        ledger = stored.ledger

        # Ledger must verify
        violations = ledger.verify()
        if violations:
            raise LedgerVerificationError("; ".join(violations))

        # Latest state must be admitted (fail-closed for pending/rejected/withdrawn)
        if case.current_state != EvidenceReviewState.ADMITTED:
            raise ExportRefusedError(
                f"export refused: latest state is {case.current_state.value!r}, not admitted"
            )

        # No newer withdrawal (redundant with above, but explicit)
        if (
            any(d.decision == EvidenceReviewState.WITHDRAWN for d in ledger.decisions)
            and case.current_state != EvidenceReviewState.ADMITTED
        ):
            raise ExportRefusedError("export refused: a withdrawal exists after admission")

        # Fingerprint and binding checks (fail-closed)
        cand_fp = (
            artifact_fingerprint.strip().lower()
            if artifact_fingerprint is not None
            else case.candidate_artifact_fingerprint
        )
        cell = cell_id.strip() if cell_id is not None else case.expected_preregistration_cell_id
        m_key = metric_key.strip() if metric_key is not None else case.observed_metric_key
        m_ver = (
            metric_version.strip() if metric_version is not None else case.observed_metric_version
        )
        m_unit = metric_unit.strip() if metric_unit is not None else case.observed_metric_unit

        if cand_fp != case.candidate_artifact_fingerprint:
            raise ExportRefusedError(
                "export refused: artifact fingerprint does not match reviewed candidate"
            )
        if cell != case.expected_preregistration_cell_id:
            raise ExportRefusedError("export refused: preregistration cell binding has changed")
        if m_key != case.observed_metric_key:
            raise ExportRefusedError("export refused: observed metric key mismatch blocks export")
        if m_ver != case.observed_metric_version:
            raise ExportRefusedError(
                "export refused: observed metric version mismatch blocks export"
            )
        if m_unit != case.observed_metric_unit:
            raise ExportRefusedError("export refused: observed unit mismatch blocks export")

        # Compatibility standing must be compatible (explicit refusal if not)
        if case.compatibility_standing != CompatibilityStanding.COMPATIBLE:
            raise ExportRefusedError(
                f"export refused: compatibility standing is {case.compatibility_standing.value!r}, "  # noqa: E501
                "not compatible"  # noqa: E501
            )

        ts = clock.astimezone(UTC) if clock is not None else _utc_now()

        attachment = EvidenceAttachment(
            artifact_fingerprint=case.candidate_artifact_fingerprint,
            cell_id=case.expected_preregistration_cell_id,
            observed_metric_key=case.observed_metric_key,
            observed_metric_version=case.observed_metric_version,
            observed_unit=case.observed_metric_unit,
            is_admitted=True,
            admission_label=ArtifactAdmission.ADMITTED,
            attached_at=ts,
        )
        export_id = f"export-{case.case_id}"
        # Compute export fingerprint deterministically (portable, no paths)
        canonical = {
            "export_id": export_id,
            "case_id": case.case_id,
            "case_fingerprint": ledger.case_fingerprint,
            "ledger_tail_fingerprint": ledger.tail_fingerprint,
            "attachment": attachment.model_dump(mode="json"),
            "exported_at": "<normalised>",
        }
        fp = _fingerprint(canonical)
        # Validate via model
        export = EvidenceAdmissionExport(
            export_id=export_id,
            case_id=case.case_id,
            case_fingerprint=ledger.case_fingerprint,
            ledger_tail_fingerprint=ledger.tail_fingerprint,
            attachment=attachment,
            exported_at=ts,
            fingerprint=fp,
        )
        # Double-check computed fingerprint matches stored one (deterministic)
        expected_fp = export.computed_fingerprint()
        if export.fingerprint != expected_fp:
            raise EvidenceAdmissionError(
                "export fingerprint mismatch: deterministic serialization failed"
            )
        return export

    # -- queue helpers -------------------------------------------------------

    def cases_by_state(self, state: EvidenceReviewState) -> list[EvidenceReviewCase]:
        return [s.case for s in self._cases.values() if s.case.current_state == state]

    def pending_queue(self) -> list[EvidenceReviewCase]:
        return self.cases_by_state(EvidenceReviewState.PENDING)

    def needs_information_queue(self) -> list[EvidenceReviewCase]:
        return self.cases_by_state(EvidenceReviewState.NEEDS_INFORMATION)

    def admitted_history(self) -> list[EvidenceReviewCase]:
        return self.cases_by_state(EvidenceReviewState.ADMITTED)

    def rejected_or_withdrawn_history(self) -> list[EvidenceReviewCase]:
        return [
            s.case
            for s in self._cases.values()
            if s.case.current_state in (EvidenceReviewState.REJECTED, EvidenceReviewState.WITHDRAWN)
        ]


# ---------------------------------------------------------------------------
# Deterministic exports (ledger JSON, case JSON, CSV, attachment JSON, receipt JSON)
# ---------------------------------------------------------------------------


def ledger_to_json(ledger: EvidenceReviewLedger) -> str:
    payload = {
        "case_id": ledger.case_id,
        "case_fingerprint": ledger.case_fingerprint,
        "tail_fingerprint": ledger.tail_fingerprint,
        "decision_count": len(ledger.decisions),
        "decisions": [d.model_dump(mode="json") for d in ledger.decisions],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def ledger_from_json(text: str) -> EvidenceReviewLedger:
    data = json.loads(text)
    decisions = [EvidenceReviewDecision.model_validate(item) for item in data.get("decisions", [])]
    return EvidenceReviewLedger(
        case_id=data["case_id"], case_fingerprint=data["case_fingerprint"], decisions=decisions
    )


def case_to_json(case: EvidenceReviewCase) -> str:
    payload = case.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def case_from_json(text: str) -> EvidenceReviewCase:
    return EvidenceReviewCase.model_validate_json(text)


def review_summary_to_csv(service: EvidenceAdmissionInboxService) -> str:
    columns = [
        "case_id",
        "candidate_artifact_fingerprint",
        "expected_preregistration_cell_id",
        "observed_metric_key",
        "observed_metric_version",
        "observed_metric_unit",
        "evidence_mode",
        "source_contract_result_fingerprint",
        "rights_privacy_standing",
        "validation_standing",
        "compatibility_standing",
        "current_state",
        "ledger_tail_fingerprint",
        "finding_count",
        "decision_count",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for stored in sorted(service._cases.values(), key=lambda s: s.case.case_id):
        case = stored.case
        ledger = stored.ledger
        writer.writerow(
            {
                "case_id": case.case_id,
                "candidate_artifact_fingerprint": case.candidate_artifact_fingerprint,
                "expected_preregistration_cell_id": case.expected_preregistration_cell_id,
                "observed_metric_key": case.observed_metric_key,
                "observed_metric_version": case.observed_metric_version,
                "observed_metric_unit": case.observed_metric_unit,
                "evidence_mode": case.evidence_mode.value,
                "source_contract_result_fingerprint": case.source_contract_result_fingerprint,
                "rights_privacy_standing": case.rights_privacy_standing.value,
                "validation_standing": case.validation_standing.value,
                "compatibility_standing": case.compatibility_standing.value,
                "current_state": case.current_state.value,
                "ledger_tail_fingerprint": ledger.tail_fingerprint,
                "finding_count": len(case.findings),
                "decision_count": len(ledger.decisions),
            }
        )
    return output.getvalue()


def admitted_attachment_to_json(export: EvidenceAdmissionExport) -> str:
    payload = export.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def receipt_to_json(receipt: EvidenceReviewReceipt) -> str:
    payload = receipt.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_receipt(
    *,
    case: EvidenceReviewCase,
    ledger: EvidenceReviewLedger,
    decision: EvidenceReviewDecision,
) -> EvidenceReviewReceipt:
    """Build a portable receipt for one decision without credential data."""
    tail = ledger.tail_fingerprint
    receipt_id = f"receipt-{decision.decision_id}"
    canonical = {
        "receipt_id": receipt_id,
        "case_id": case.case_id,
        "decision_id": decision.decision_id,
        "case_fingerprint": case.fingerprint(),
        "decision_fingerprint": decision.fingerprint(),
        "ledger_tail_fingerprint": tail,
        "decision": decision.decision.value,
        "reason": decision.reason,
        "reviewer_label": decision.reviewer_label,
        "decision_timestamp": "<normalised>",
        "previous_decision_fingerprint": decision.previous_decision_fingerprint,
        "requested_information_fields": decision.requested_information_fields,
        "fingerprint": "<placeholder>",
    }
    # Compute fingerprint over normalised payload
    tmp = dict(canonical)
    tmp.pop("fingerprint", None)
    fp = _fingerprint(tmp)
    receipt = EvidenceReviewReceipt(
        receipt_id=receipt_id,
        case_id=case.case_id,
        decision_id=decision.decision_id,
        case_fingerprint=case.fingerprint(),
        decision_fingerprint=decision.fingerprint(),
        ledger_tail_fingerprint=tail,
        decision=decision.decision,
        reason=decision.reason,
        reviewer_label=decision.reviewer_label,
        decision_timestamp=decision.decision_timestamp,
        previous_decision_fingerprint=decision.previous_decision_fingerprint,
        requested_information_fields=decision.requested_information_fields,
        fingerprint=fp,
    )
    # Deterministic check
    expected = receipt.computed_fingerprint()
    if receipt.fingerprint != expected:
        raise EvidenceAdmissionError("receipt fingerprint mismatch")
    return receipt


# ---------------------------------------------------------------------------
# Store-level helpers used by CLI/UI (in-memory singleton for session)
# ---------------------------------------------------------------------------

_global_service: EvidenceAdmissionInboxService | None = None


def get_global_service() -> EvidenceAdmissionInboxService:
    global _global_service
    if _global_service is None:
        _global_service = EvidenceAdmissionInboxService()
    return _global_service


def reset_global_service() -> None:
    global _global_service
    _global_service = EvidenceAdmissionInboxService()
