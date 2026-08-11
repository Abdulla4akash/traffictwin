"""Evidence Admission Inbox — human review queue between validation and admission.

A thin Streamlit surface over :mod:`traffictwin.evidence_admission.service`.
Validation is not admission: only an explicit human admitted decision may
create an admitted EvidenceAttachment for Preregistration Studio.

Evidence and authority boundary: this page records human review over
imported/validated artifacts; it does not establish external validity,
real-world robustness, or Manchester evidence, never automatically admits
evidence, and never zero-fills missing evidence.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import streamlit as st

from traffictwin.evidence_admission.models import (
    EvidenceReviewCase,
    EvidenceReviewLedger,
    EvidenceReviewState,
)
from traffictwin.evidence_admission.service import (
    EvidenceAdmissionError,
    EvidenceAdmissionInboxService,
    admitted_attachment_to_json,
    allowed_transitions_from,
    build_receipt,
    case_to_json,
    ledger_to_json,
    receipt_to_json,
    review_summary_to_csv,
    verify_case_with_ledger,
)
from traffictwin.ui.state import UiConfig

SESSION_SERVICE_KEY = "evidence_admission_service"


def _get_service() -> EvidenceAdmissionInboxService:
    if SESSION_SERVICE_KEY not in st.session_state:
        st.session_state[SESSION_SERVICE_KEY] = EvidenceAdmissionInboxService()
    svc = st.session_state[SESSION_SERVICE_KEY]
    # Defensive: ensure the stored object is the expected type (tests may inject)
    if not isinstance(svc, EvidenceAdmissionInboxService):
        svc = EvidenceAdmissionInboxService()
        st.session_state[SESSION_SERVICE_KEY] = svc
    return svc


def _boundary_caption() -> str:
    return (
        "Evidence and authority boundary: validation is not admission. "
        "This queue records human review over imported or validated artifacts "
        "and does not establish external validity, causality, Manchester evidence, "
        "or optimality. Only an explicit human admitted decision may create an "
        "admitted EvidenceAttachment; rejected, pending, needs_information, and "
        "withdrawn cases export nothing. Synthetic evidence remains labelled synthetic."
    )


def render(config: UiConfig) -> None:  # noqa: ARG001
    """Render the Evidence Admission Inbox queues, detail, and explicit decision form."""
    st.title("Evidence Admission Inbox")
    st.caption(_boundary_caption())
    st.caption(
        "Human review sits between imported/validated artifacts and Preregistration Studio "
        "evidence attachment. Every decision is append-only and hash-chained; a changed decision "
        "creates a new ledger entry — nothing is edited in place."
    )

    service = _get_service()

    # Queue membership and displayed state both ledger-derived via snapshots
    snapshots = service.case_snapshots()
    pending_snaps = [
        (c, ledger)
        for c, ledger in snapshots
        if (
            ledger.current_state
            if ledger.current_state is not None
            else EvidenceReviewState.PENDING
        )
        == EvidenceReviewState.PENDING
    ]
    needs_snaps = [
        (c, ledger)
        for c, ledger in snapshots
        if ledger.current_state == EvidenceReviewState.NEEDS_INFORMATION
    ]
    admitted_snaps = [
        (c, ledger)
        for c, ledger in snapshots
        if ledger.current_state == EvidenceReviewState.ADMITTED
    ]
    rejected_withdrawn_snaps = [
        (c, ledger)
        for c, ledger in snapshots
        if (
            ledger.current_state
            if ledger.current_state is not None
            else EvidenceReviewState.PENDING
        )
        in (EvidenceReviewState.REJECTED, EvidenceReviewState.WITHDRAWN)
    ]

    st.subheader("Pending queue")
    _render_queue(
        pending_snaps,
        empty_message="No cases are pending review.",
        key="pending",
    )

    st.subheader("Needs information queue")
    _render_queue(
        needs_snaps,
        empty_message="No cases are waiting for additional information.",
        key="needs_information",
    )

    st.subheader("Admitted history")
    _render_queue(
        admitted_snaps,
        empty_message=(
            "No cases have been admitted. Only an explicit admitted decision creates "
            "an admitted attachment."
        ),
        key="admitted",
    )

    st.subheader("Rejected and withdrawn history")
    _render_queue(
        rejected_withdrawn_snaps,
        empty_message="No cases have been rejected or withdrawn.",
        key="rejected_withdrawn",
    )

    st.subheader("Case detail")

    cases = service.list_cases()
    if not cases:
        st.info(
            "The inbox is empty in this workspace process. Create a demo case below to explore "
            "the queue, or in tests, enqueue cases via the service API before rendering. "
            "Nothing is auto-created and no synthetic evidence is relabelled as observed."
        )
        _render_create_demo(service)
        _render_summary_exports(service)
        return

    case_ids = sorted(c.case_id for c in cases)
    default_case = case_ids[0]
    selected_raw = st.session_state.get("evidence_admission_selected_case", default_case)
    selected_index = case_ids.index(selected_raw) if selected_raw in case_ids else 0
    selected_case_id: str = str(
        st.selectbox(
            "Select case for detail and decision",
            options=case_ids,
            index=selected_index,
            key="evidence_admission_selected_case",
        )
    )

    try:
        case = service.get_case(selected_case_id)
        ledger = service.get_ledger(selected_case_id)
    except EvidenceAdmissionError as exc:
        st.error(str(exc))
        return

    # Authoritative pair check — do not trust cached case state alone
    violations = verify_case_with_ledger(case, ledger)
    if violations:
        st.error(
            "Case/ledger integrity verification failed for case "
            f"{selected_case_id!r}: " + "; ".join(violations)
        )
        st.error(
            "The cached case state cannot be trusted until the pair is repaired/reloaded. "
            "No decision or admitted export is available."
        )
        st.caption(
            f"Forensic — Case fingerprint: {case.fingerprint()[:16]}…  "
            f"Ledger tail: {ledger.tail_fingerprint[:16]}… (pair invalid)"
        )
        st.subheader("Findings and source standing (forensic — pair invalid)")
        _render_standings(case)
        _render_findings(case)
        st.info("Decision and attachment controls are withheld due to integrity failure.")
        st.subheader("Append-only history (forensic)")
        _render_history(ledger)
        _render_create_demo(service)
        return

    # Valid pair — derive display state from ledger (authoritative)
    ledger_state = ledger.current_state
    display_state = ledger_state if ledger_state is not None else EvidenceReviewState.PENDING

    st.caption(
        f"Case fingerprint: {case.fingerprint()[:16]}…  "
        f"Ledger tail: {ledger.tail_fingerprint[:16]}…"
    )

    st.subheader("Findings and source standing")
    _render_standings(case)
    _render_findings(case)

    st.subheader("Source contract and validation standing")
    st.dataframe(
        [
            {
                "Field": "Candidate artifact fingerprint",
                "Value": case.candidate_artifact_fingerprint,
            },
            {
                "Field": "Expected preregistration cell",
                "Value": case.expected_preregistration_cell_id,
            },
            {
                "Field": "Observed metric",
                "Value": (
                    f"{case.observed_metric_key} @ {case.observed_metric_version} "
                    f"[{case.observed_metric_unit}]"
                ),
            },
            {"Field": "Evidence mode", "Value": case.evidence_mode.value},
            {
                "Field": "Source-contract result fingerprint",
                "Value": case.source_contract_result_fingerprint,
            },
            {"Field": "Rights / privacy standing", "Value": case.rights_privacy_standing.value},
            {"Field": "Validation standing", "Value": case.validation_standing.value},
            {"Field": "Compatibility standing", "Value": case.compatibility_standing.value},
            {"Field": "Current state", "Value": display_state.value},
        ],
        hide_index=True,
        width="stretch",
        key="evidence_admission_standing_table",
    )
    st.caption(
        "Privacy and evidence standing are shown before any decision controls. "
        "A case with restricted rights, failed validation, or incompatibility remains blocked."
    )
    st.caption("Case/ledger pair integrity verified — ledger state is authoritative.")

    st.subheader("Explicit decision")
    st.caption(
        "No automatic decision is made. Choose a transition, provide a reason, and identify the reviewer."  # noqa: E501
    )
    _render_decision_form(service, case, ledger, display_state)

    st.subheader("Append-only history")
    _render_history(ledger)

    st.subheader("Attachment preview and download")
    _render_attachment(service, case, ledger)

    st.subheader("Exports")
    _render_exports(service, case, ledger)
    _render_summary_exports(service)
    _render_create_demo(service)


def _render_queue(
    snapshots: Sequence[tuple[EvidenceReviewCase, EvidenceReviewLedger]],
    *,
    empty_message: str,
    key: str,
) -> None:
    if not snapshots:
        st.info(empty_message)
        return
    rows: list[dict[str, str]] = []
    for c, ledger in snapshots:
        ledger_state = ledger.current_state
        display_state = ledger_state if ledger_state is not None else EvidenceReviewState.PENDING
        rows.append(
            {
                "case_id": c.case_id,
                "cell_id": c.expected_preregistration_cell_id,
                "metric": f"{c.observed_metric_key}@{c.observed_metric_version}",
                "state": display_state.value,
                "rights": c.rights_privacy_standing.value,
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch", key=f"evidence_admission_queue_{key}")


def _render_standings(case: EvidenceReviewCase) -> None:
    st.caption(
        f"Rights standing: **{case.rights_privacy_standing.value}** · "
        f"Validation: **{case.validation_standing.value}** · "
        f"Compatibility: **{case.compatibility_standing.value}** · "
        f"Evidence mode: **{case.evidence_mode.value}**"
    )


def _render_findings(case: EvidenceReviewCase) -> None:
    findings = case.findings
    if not findings:
        st.caption("No additional findings recorded for this case.")
        return
    rows = [
        {
            "code": f.code,
            "category": f.category.value,
            "severity": f.severity.value,
            "description": f.description,
        }
        for f in findings
    ]
    st.dataframe(rows, hide_index=True, width="stretch", key="evidence_admission_findings")


def _render_decision_form(
    service: EvidenceAdmissionInboxService,
    case: EvidenceReviewCase,
    ledger: EvidenceReviewLedger,
    display_state: EvidenceReviewState,
) -> None:
    current = display_state.value
    st.caption(
        f"Current state is **{current}**. Only the allowed transitions from that state will be accepted."  # noqa: E501
    )

    allowed = [s.value for s in allowed_transitions_from(display_state)]
    if not allowed:
        st.info(f"No further decisions are allowed from the terminal state {current!r}.")
        return

    with st.form(key="evidence_admission_decision_form"):
        decision = st.selectbox(
            "Decision (target state)",
            options=allowed,
            key="evidence_admission_decision_choice",
        )
        reason = st.text_area(
            "Reason",
            value="",
            placeholder="Human rationale for this transition (required)",
            key="evidence_admission_reason",
        )
        reviewer_label = st.text_input(
            "Reviewer label or pseudonymous reviewer ID",
            value="reviewer-demo",
            key="evidence_admission_reviewer",
        )
        requested = st.text_input(
            "Requested information fields (comma-separated, only for needs_information)",
            value="",
            key="evidence_admission_requested",
        )
        submitted = st.form_submit_button("Record decision", type="primary")

    if not submitted:
        return

    reason_s = reason.strip()
    reviewer_s = reviewer_label.strip()
    if not reason_s:
        st.error("A reason is required for every decision.")
        return
    if not reviewer_s:
        st.error("A reviewer label is required for every decision.")
        return

    requested_fields: list[str] = []
    if requested.strip():
        requested_fields = [p.strip() for p in requested.split(",") if p.strip()]

    decision_id = f"dec-{case.case_id}-{len(ledger.decisions) + 1}"

    try:
        target_state = EvidenceReviewState(decision)
    except ValueError:
        st.error(f"Unknown decision {decision!r}.")
        return

    try:
        entry = service.append_decision(
            case_id=case.case_id,
            decision_id=decision_id,
            decision=target_state,
            reason=reason_s,
            reviewer_label=reviewer_s,
            decision_timestamp=datetime.now(UTC),
            requested_information_fields=requested_fields,
        )
    except EvidenceAdmissionError as exc:
        st.error(str(exc))
        return

    st.success(
        f"Recorded decision {entry.decision.value!r} as {entry.decision_id}. "
        f"The ledger tail is now {ledger.tail_fingerprint[:8]}… -> {entry.fingerprint()[:8]}…"
    )
    st.rerun()


def _render_history(ledger: EvidenceReviewLedger) -> None:
    decisions = ledger.decisions
    if not decisions:
        st.info(
            "No decisions have been recorded for this case. The case is pending its first review."
        )
        return
    rows = []
    for d in decisions:
        rows.append(
            {
                "decision_id": d.decision_id,
                "decision": d.decision.value,
                "reason": d.reason,
                "reviewer": d.reviewer_label,
                "timestamp": d.decision_timestamp.isoformat(),
                "previous": d.previous_decision_fingerprint[:8] + "…",
                "fingerprint": d.fingerprint()[:8] + "…",
                "requested": ", ".join(d.requested_information_fields)
                if d.requested_information_fields
                else "—",
            }
        )
    st.dataframe(rows, hide_index=True, width="stretch", key="evidence_admission_history")
    violations = ledger.verify()
    if violations:
        st.error("Ledger hash chain verification failed: " + "; ".join(violations))
    else:
        st.caption(
            "Decision hash chain verifies: every entry's previous fingerprint matches "
            "its predecessor and decision IDs are unique."
        )


def _render_attachment(
    service: EvidenceAdmissionInboxService,
    case: EvidenceReviewCase,
    ledger: EvidenceReviewLedger,
) -> None:
    try:
        export = service.export_admitted_attachment(case.case_id)
    except EvidenceAdmissionError as exc:
        st.info(
            str(exc) + " — pending, rejected, or withdrawn cases fail closed and export nothing."
        )
        st.caption(
            "The exported attachment would use is_admitted=True and admission_label=admitted, "
            "consistent with Preregistration Studio."
        )
        return
    st.success(
        f"Admitted attachment is available for case {export.case_id} "
        f"(ledger tail {export.ledger_tail_fingerprint[:8]}…)."
    )
    st.json(export.attachment.model_dump(mode="json"))
    attachment_json = json.dumps(
        export.attachment.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    st.download_button(
        "Download admitted attachment JSON",
        data=attachment_json.encode("utf-8"),
        file_name=f"admitted-attachment-{case.case_id}.json",
        mime="application/json",
        key="evidence_admission_download_attachment",
    )
    full_export_json = admitted_attachment_to_json(export)
    st.download_button(
        "Download full export JSON",
        data=full_export_json.encode("utf-8"),
        file_name=f"evidence-admission-export-{case.case_id}.json",
        mime="application/json",
        key="evidence_admission_download_export",
    )


def _render_exports(
    service: EvidenceAdmissionInboxService,
    case: EvidenceReviewCase,
    ledger: EvidenceReviewLedger,
) -> None:
    _ = service
    ledger_json = ledger_to_json(ledger)
    case_json = case_to_json(case)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download ledger JSON",
            data=ledger_json.encode("utf-8"),
            file_name=f"ledger-{case.case_id}.json",
            mime="application/json",
            key="evidence_admission_download_ledger",
        )
    with col2:
        st.download_button(
            "Download case JSON",
            data=case_json.encode("utf-8"),
            file_name=f"case-{case.case_id}.json",
            mime="application/json",
            key="evidence_admission_download_case",
        )
    if ledger.decisions:
        latest = ledger.decisions[-1]
        receipt = build_receipt(case=case, ledger=ledger, decision=latest)
        receipt_json = receipt_to_json(receipt)
        st.download_button(
            "Download receipt JSON for latest decision",
            data=receipt_json.encode("utf-8"),
            file_name=f"receipt-{latest.decision_id}.json",
            mime="application/json",
            key="evidence_admission_download_receipt",
        )
        st.caption(
            f"Receipt fingerprint: {receipt.fingerprint[:16]}…  "
            "No reviewer credential or private path is included."
        )


def _render_summary_exports(service: EvidenceAdmissionInboxService) -> None:
    try:
        csv_text = review_summary_to_csv(service)
    except EvidenceAdmissionError as exc:
        offending: list[str] = []
        for case, ledger in service.case_snapshots():
            if verify_case_with_ledger(case, ledger):
                offending.append(case.case_id)
        detail = f": {', '.join(sorted(offending))}" if offending else ""
        st.error(
            f"Review-summary CSV is unavailable because one or more case/ledger pairs "
            f"failed integrity verification{detail}: {exc}"
        )
        return
    st.download_button(
        "Download review summary CSV",
        data=csv_text.encode("utf-8"),
        file_name="evidence-admission-review-summary.csv",
        mime="text/csv",
        key="evidence_admission_download_csv",
    )
    st.caption(
        "Review summary CSV is deterministic and contains one row per case with state, "
        "standings, and fingerprints — no local paths."
    )


def _render_create_demo(service: EvidenceAdmissionInboxService) -> None:
    with st.expander("Advanced: create a demo case in this process (no persistence)"):
        st.caption(
            "Demo cases use deterministic fingerprints (not local paths) and are visible only "
            "in this process."
        )
        demo_case_id = st.text_input(
            "Demo case ID", value="demo-case-1", key="evidence_admission_demo_case_id"
        )
        demo_cell_id = st.text_input(
            "Demo cell ID", value="cell-demo-1", key="evidence_admission_demo_cell"
        )
        if st.button("Create demo pending case", key="evidence_admission_create_demo"):
            import hashlib

            from traffictwin.evidence_admission.models import (
                CompatibilityStanding,
                EvidenceMode,
                RightsPrivacyStanding,
                ValidationStanding,
            )

            artifact_fp = hashlib.sha256(f"demo-artifact:{demo_case_id}".encode()).hexdigest()
            contract_fp = hashlib.sha256(f"demo-contract:{demo_case_id}".encode()).hexdigest()
            try:
                service.create_case(
                    case_id=demo_case_id.strip(),
                    candidate_artifact_fingerprint=artifact_fp,
                    expected_preregistration_cell_id=demo_cell_id.strip(),
                    observed_metric_key="task.completion.rate",
                    observed_metric_version="1.0",
                    observed_metric_unit="ratio",
                    evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
                    source_contract_result_fingerprint=contract_fp,
                    rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
                    validation_standing=ValidationStanding.VALIDATED,
                    compatibility_standing=CompatibilityStanding.COMPATIBLE,
                    findings=[],
                    created_at=datetime.now(UTC),
                )
            except EvidenceAdmissionError as exc:
                st.error(str(exc))
                return
            st.success(f"Created demo case {demo_case_id}.")
            st.rerun()
