"""Append-only ledger and human-review service for the Evidence Admission Inbox.

Business logic lives outside Streamlit. Every decision is hash-chained and
append-only; in-place editing is never permitted. Export is fail-closed and
requires a verified non-genesis ledger whose current state is ADMITTED, whose
tail matches the case anchor, and whose cached case state agrees with the
ledger. Validation is not admission.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from traffictwin.data_contract.fingerprint import sanitise_for_csv
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


class DuplicateCaseError(EvidenceAdmissionError):
    """Duplicate case_id refused; existing review case cannot be replaced."""


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


def allowed_transitions_from(
    state: EvidenceReviewState,
) -> tuple[EvidenceReviewState, ...]:
    """Return authoritative allowed targets from one review state."""
    return tuple(tgt for (src, tgt) in sorted(_ALLOWED, key=lambda p: p[1].value) if src == state)


def _case_ledger_consistency_violations(
    case: EvidenceReviewCase,
    ledger: EvidenceReviewLedger,
) -> list[str]:
    violations: list[str] = []
    if case.case_id != ledger.case_id:
        violations.append(f"case/ledger case_id mismatch: {case.case_id!r} vs {ledger.case_id!r}")
    if case.fingerprint() != ledger.case_fingerprint:
        violations.append("case fingerprint does not match ledger case_fingerprint")
    chain_violations = ledger.verify()
    if chain_violations:
        violations.extend(chain_violations)
    if case.ledger_tail_fingerprint != ledger.tail_fingerprint:
        violations.append(
            f"case tail anchor mismatch: case {case.ledger_tail_fingerprint[:8]}… "
            f"vs ledger {ledger.tail_fingerprint[:8]}…"
        )
    # Derived ledger state must agree with cached case state
    expected_state = ledger.current_state
    if expected_state is None:
        if case.current_state != EvidenceReviewState.PENDING:
            violations.append(
                f"case state {case.current_state.value!r} disagrees with empty ledger "
                f"(expected {EvidenceReviewState.PENDING.value!r})"
            )
    else:
        if case.current_state != expected_state:
            violations.append(
                f"case state {case.current_state.value!r} disagrees with ledger state "
                f"{expected_state.value!r}"
            )
    return violations


def _assert_case_ledger_consistency(
    case: EvidenceReviewCase,
    ledger: EvidenceReviewLedger,
) -> None:
    violations = _case_ledger_consistency_violations(case, ledger)
    if violations:
        raise LedgerVerificationError("; ".join(violations))


def verify_case_with_ledger(
    case: EvidenceReviewCase,
    ledger: EvidenceReviewLedger,
) -> list[str]:
    """Public helper: verify case+ledger pair integrity (portable, no store)."""
    return _case_ledger_consistency_violations(case, ledger)


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
    The decision ledger is authoritative; the cached case snapshot must
    always agree with it.
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
        # Reject duplicate case_id before any mutation (append-only, immutable identity)
        norm_case_id = case_id.strip()
        if norm_case_id in self._cases:
            raise DuplicateCaseError(
                f"duplicate case_id {norm_case_id!r} refused; "  # noqa: E501
                "existing review case cannot be replaced"
            )
        binding_key = (
            candidate_artifact_fingerprint.strip().lower(),
            expected_preregistration_cell_id.strip(),
        )
        if binding_key in self._binding_index:
            raise DuplicateBindingError(
                f"duplicate cell/candidate binding refused: cell {expected_preregistration_cell_id!r} "  # noqa: E501
                f"already bound to case {self._binding_index[binding_key]!r}"
            )
        ts = created_at.astimezone(UTC) if created_at is not None else _utc_now()
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
        ledger = EvidenceReviewLedger(case_id=case.case_id, case_fingerprint=case_fp, decisions=())
        # Verify fresh pair is internally consistent (pending + genesis)
        _assert_case_ledger_consistency(case, ledger)
        self._cases[case.case_id] = _StoredCase(case=case, ledger=ledger)
        self._binding_index[binding_key] = case.case_id
        return case.model_copy(deep=True)

    def get_case(self, case_id: str) -> EvidenceReviewCase:
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        return stored.case.model_copy(deep=True)

    def get_ledger(self, case_id: str) -> EvidenceReviewLedger:
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        return stored.ledger.model_copy(deep=True)

    def list_cases(self) -> list[EvidenceReviewCase]:
        return [s.case.model_copy(deep=True) for s in self._cases.values()]

    def list_ledgers(self) -> list[EvidenceReviewLedger]:
        return [s.ledger.model_copy(deep=True) for s in self._cases.values()]

    def case_snapshots(
        self,
    ) -> list[tuple[EvidenceReviewCase, EvidenceReviewLedger]]:
        """Public snapshot of case+ledger pairs (defensive copies, no private store exposure)."""
        return [
            (s.case.model_copy(deep=True), s.ledger.model_copy(deep=True))
            for s in self._cases.values()
        ]

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
        # Verify existing stored state first — corrupted tail must not be extended
        _assert_case_ledger_consistency(stored.case, stored.ledger)

        ledger = stored.ledger
        stored_case = stored.case

        if any(d.decision_id == decision_id for d in ledger.decisions):
            raise DuplicateDecisionError(f"duplicate decision_id {decision_id!r} refused")

        expected_prev = ledger.tail_fingerprint
        provided_prev = (
            previous_decision_fingerprint.strip().lower()
            if previous_decision_fingerprint is not None
            else expected_prev
        )
        if provided_prev != expected_prev:
            raise StaleParentError(
                f"stale previous fingerprint refused: expected {expected_prev[:8]}… "
                f"got {provided_prev[:8]}…"
            )

        # Derive current state from ledger (authoritative), not cached case alone
        current = ledger.current_state
        if current is None:
            current = EvidenceReviewState.PENDING
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
        new_decisions = ledger.decisions + (entry,)
        new_ledger = EvidenceReviewLedger(
            case_id=ledger.case_id,
            case_fingerprint=ledger.case_fingerprint,
            decisions=new_decisions,
        )
        violations = new_ledger.verify()
        if violations:
            raise LedgerVerificationError("; ".join(violations))

        updated_case = stored_case.model_copy(
            update={
                "current_state": new_ledger.current_state,
                "updated_at": ts,
                "ledger_tail_fingerprint": new_ledger.tail_fingerprint,
            }
        )
        _assert_case_ledger_consistency(updated_case, new_ledger)
        self._cases[case_id] = _StoredCase(case=updated_case, ledger=new_ledger)
        return entry.model_copy(deep=True)

    def verify_ledger(self, case_id: str) -> list[str]:
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        return _case_ledger_consistency_violations(stored.case, stored.ledger)

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

        The decision ledger is the ONLY authority for admission.
        Requires a verified case/ledger pair whose ledger current_state is ADMITTED,
        plus binding and compatibility checks. Non-empty/non-genesis is implied by ADMITTED.
        """
        stored = self._cases.get(case_id)
        if stored is None:
            raise EvidenceAdmissionError(f"unknown case {case_id!r}")
        case = stored.case
        ledger = stored.ledger

        # Full case/ledger consistency (includes ledger.verify and tail anchor)
        violations = _case_ledger_consistency_violations(case, ledger)
        if violations:
            raise LedgerVerificationError("; ".join(violations))

        ledger_state = ledger.current_state
        if ledger_state != EvidenceReviewState.ADMITTED:
            if ledger_state is not None:
                raise ExportRefusedError(
                    f"export refused: ledger state is {ledger_state.value!r}, not 'admitted'"
                )
            else:
                raise ExportRefusedError(
                    "export refused: ledger has no admission decision; "
                    "current ledger state is unavailable"
                )

        # Fingerprint and binding checks (fail-closed)
        if artifact_fingerprint is not None:
            cand_fp = artifact_fingerprint.strip().lower()
        else:
            cand_fp = case.candidate_artifact_fingerprint
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

        if case.compatibility_standing != CompatibilityStanding.COMPATIBLE:
            raise ExportRefusedError(
                f"export refused: compatibility standing is {case.compatibility_standing.value!r}, "
                "not compatible"
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
        canonical = {
            "export_id": export_id,
            "case_id": case.case_id,
            "case_fingerprint": ledger.case_fingerprint,
            "ledger_tail_fingerprint": ledger.tail_fingerprint,
            "attachment": attachment.model_dump(mode="json"),
            "exported_at": "<normalised>",
        }
        fp = _fingerprint(canonical)
        export = EvidenceAdmissionExport(
            export_id=export_id,
            case_id=case.case_id,
            case_fingerprint=ledger.case_fingerprint,
            ledger_tail_fingerprint=ledger.tail_fingerprint,
            attachment=attachment,
            exported_at=ts,
            fingerprint=fp,
        )
        expected_fp = export.computed_fingerprint()
        if export.fingerprint != expected_fp:
            raise EvidenceAdmissionError(
                "export fingerprint mismatch: deterministic serialization failed"
            )
        return export

    # -- queue helpers -------------------------------------------------------

    def cases_by_state(self, state: EvidenceReviewState) -> list[EvidenceReviewCase]:
        # Derive state from ledger (authoritative) rather than trusting cached snapshot alone,
        # but stored pair is already guaranteed consistent, so both agree.
        result: list[EvidenceReviewCase] = []
        for stored in self._cases.values():
            ledger_state = stored.ledger.current_state
            derived = ledger_state if ledger_state is not None else EvidenceReviewState.PENDING
            if derived == state:
                result.append(stored.case.model_copy(deep=True))
        return result

    def pending_queue(self) -> list[EvidenceReviewCase]:
        return self.cases_by_state(EvidenceReviewState.PENDING)

    def needs_information_queue(self) -> list[EvidenceReviewCase]:
        return self.cases_by_state(EvidenceReviewState.NEEDS_INFORMATION)

    def admitted_history(self) -> list[EvidenceReviewCase]:
        return self.cases_by_state(EvidenceReviewState.ADMITTED)

    def rejected_or_withdrawn_history(self) -> list[EvidenceReviewCase]:
        return [
            s.case.model_copy(deep=True)
            for s in self._cases.values()
            if (
                s.ledger.current_state
                if s.ledger.current_state is not None
                else EvidenceReviewState.PENDING
            )
            in (EvidenceReviewState.REJECTED, EvidenceReviewState.WITHDRAWN)
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
    ledger = EvidenceReviewLedger(
        case_id=data["case_id"],
        case_fingerprint=data["case_fingerprint"],
        decisions=tuple(decisions),
    )
    # Verify integrity of the deserialized artifact
    chain_violations = ledger.verify()
    if chain_violations:
        raise LedgerVerificationError("; ".join(chain_violations))
    if data.get("decision_count") != len(ledger.decisions):
        raise LedgerVerificationError(
            f"decision_count mismatch: expected {data.get('decision_count')!r} "
            f"got {len(ledger.decisions)!r}"
        )
    if data.get("tail_fingerprint") != ledger.tail_fingerprint:
        raise LedgerVerificationError(
            f"tail_fingerprint mismatch: expected {data.get('tail_fingerprint')!r} "
            f"got {ledger.tail_fingerprint!r}"
        )
    return ledger


def case_to_json(case: EvidenceReviewCase) -> str:
    payload = case.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def case_from_json(text: str) -> EvidenceReviewCase:
    # Typed model validation only; a case JSON alone cannot verify its external ledger chain.
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
    for case, ledger in sorted(service.case_snapshots(), key=lambda pair: pair[0].case_id):
        violations = verify_case_with_ledger(case, ledger)
        if violations:
            raise LedgerVerificationError("; ".join(violations))
        ledger_state = ledger.current_state
        display_state = ledger_state if ledger_state is not None else EvidenceReviewState.PENDING
        writer.writerow(
            {
                "case_id": sanitise_for_csv(case.case_id),
                "candidate_artifact_fingerprint": sanitise_for_csv(
                    case.candidate_artifact_fingerprint
                ),
                "expected_preregistration_cell_id": sanitise_for_csv(
                    case.expected_preregistration_cell_id
                ),
                "observed_metric_key": sanitise_for_csv(case.observed_metric_key),
                "observed_metric_version": sanitise_for_csv(case.observed_metric_version),
                "observed_metric_unit": sanitise_for_csv(case.observed_metric_unit),
                "evidence_mode": sanitise_for_csv(case.evidence_mode.value),
                "source_contract_result_fingerprint": sanitise_for_csv(
                    case.source_contract_result_fingerprint
                ),
                "rights_privacy_standing": sanitise_for_csv(case.rights_privacy_standing.value),
                "validation_standing": sanitise_for_csv(case.validation_standing.value),
                "compatibility_standing": sanitise_for_csv(case.compatibility_standing.value),
                "current_state": sanitise_for_csv(display_state.value),
                "ledger_tail_fingerprint": sanitise_for_csv(ledger.tail_fingerprint),
                "finding_count": sanitise_for_csv(str(len(case.findings))),
                "decision_count": sanitise_for_csv(str(len(ledger.decisions))),
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
    violations = _case_ledger_consistency_violations(case, ledger)
    if violations:
        raise LedgerVerificationError("; ".join(violations))
    if decision not in ledger.decisions:
        raise LedgerVerificationError(
            f"decision {decision.decision_id!r} not committed to ledger {ledger.case_id!r}"
        )
    # Ensure decision fingerprint is exactly present (verify membership already implies, but check)
    found = next((d for d in ledger.decisions if d.decision_id == decision.decision_id), None)
    if found is None or found.fingerprint() != decision.fingerprint():
        raise LedgerVerificationError("decision fingerprint mismatch with ledger entry")
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
