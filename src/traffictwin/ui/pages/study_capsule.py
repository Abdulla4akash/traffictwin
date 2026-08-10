"""Study Capsule Builder page — deterministic analysis-level review capsule."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import streamlit as st

from traffictwin.study_capsule import (
    StudyCapsuleAdmissionLabel,
    StudyCapsuleEvidenceLabel,
    StudyCapsuleMemberInput,
    StudyCapsuleMemberKind,
    StudyCapsulePublicationPolicy,
    StudyCapsuleRequest,
    StudyCapsuleUnavailable,
    build_study_capsule,
    create_study_capsule_archive,
    default_synthetic_member,
    preview_membership,
    study_capsule_contract,
    verify_study_capsule_bytes,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.state import UiConfig

_DEFAULT_STUDY_ID = "study-demo-001"
_DEFAULT_CAPSULE_TITLE = "Demo Study Capsule"
_SYNTHETIC_FINGERPRINTS: dict[str, str] = {
    # Deterministic fingerprints for demo seeds (sha256 of kind:logical_id)
    # Generated via _sha256 for reproducibility; values hard-coded for UI stability.
}

# Predefined demo members to illustrate the workflow.
_DEMO_MEMBERS: list[tuple[StudyCapsuleMemberKind, str, StudyCapsuleEvidenceLabel]] = [
    (
        StudyCapsuleMemberKind.SCENARIO_SEED,
        "scenario-baseline",
        StudyCapsuleEvidenceLabel.AUTHORED_CONFIGURATION,
    ),
    (
        StudyCapsuleMemberKind.RUN_SUMMARY,
        "run-baseline",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.RUN_SUMMARY,
        "run-variation",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.COMPARISON_REPORT,
        "comparison-baseline-vs-variation",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.CONSEQUENCE_REPORT,
        "consequence-traffic",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.EVIDENCE_PACK,
        "evidence-pack-baseline",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.DIAGNOSTIC_RESULT,
        "diagnostics-r0-r3",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.PROVENANCE_GRAPH,
        "provenance-baseline",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
        "report-run-baseline",
        StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    ),
    (
        StudyCapsuleMemberKind.ANALYST_NOTE,
        "analyst-note-001",
        StudyCapsuleEvidenceLabel.AUTHORED_CONFIGURATION,
    ),
]


def _evidence_options() -> list[str]:
    return [e.value for e in StudyCapsuleEvidenceLabel]


def _policy_options() -> list[str]:
    return [p.value for p in StudyCapsulePublicationPolicy]


def _admission_options() -> list[str]:
    return [a.value for a in StudyCapsuleAdmissionLabel]


def _build_default_members(
    selected_kinds: set[StudyCapsuleMemberKind],
    policy_overrides: dict[str, str],
    evidence_overrides: dict[str, str],
) -> list[StudyCapsuleMemberInput]:
    """Build demo members via the public production helper.

    All fingerprint and content logic lives in the service layer; the page
    only collects widget values and delegates.
    """

    members: list[StudyCapsuleMemberInput] = []
    for kind, logical_id, default_ev in _DEMO_MEMBERS:
        if kind not in selected_kinds:
            continue
        key = f"{kind.value}:{logical_id}"
        # Safe default: raw evidence must not default to EMBED
        raw_like = {
            StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
            StudyCapsuleEvidenceLabel.HISTORICAL_OBSERVATION,
            StudyCapsuleEvidenceLabel.NEAR_LIVE_OPERATIONAL,
            StudyCapsuleEvidenceLabel.UNADMITTED_RESEARCH,
        }
        default_policy = (
            StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT.value
            if default_ev in raw_like
            else StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED.value
        )
        policy_val = policy_overrides.get(key, default_policy)
        ev_val = evidence_overrides.get(key, default_ev.value)
        policy = StudyCapsulePublicationPolicy(policy_val)
        ev = StudyCapsuleEvidenceLabel(ev_val)
        members.append(default_synthetic_member(kind, logical_id, evidence_label=ev, policy=policy))
    return members


def _raw_like(ev: StudyCapsuleEvidenceLabel) -> bool:
    return ev in {
        StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
        StudyCapsuleEvidenceLabel.HISTORICAL_OBSERVATION,
        StudyCapsuleEvidenceLabel.NEAR_LIVE_OPERATIONAL,
        StudyCapsuleEvidenceLabel.UNADMITTED_RESEARCH,
    }


def render(config: UiConfig) -> None:  # noqa: ARG001
    """Render the Study Capsule Builder page."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.STUDY_CAPSULE))
    st.caption(
        "Assemble selected derived artifacts into a deterministic, "
        "offline-verifiable review package. Raw imported evidence is referenced "
        "or excluded by default — never embedded without explicit permission."
    )
    st.info(
        "This capsule is an analysis-level review artifact. A verifiable "
        "capsule does not prove scientific validity; it proves that the listed "
        "artifacts were bound with the shown checksums and limitations."
    )

    contract = study_capsule_contract()
    with st.expander("Method contract", expanded=False):
        st.json(
            {
                "schema_version": contract.schema_version,
                "contract_version": contract.contract_version,
                "member_kinds": contract.member_kinds,
                "publication_policies": contract.publication_policies,
                "required_members": contract.required_members,
                "limits": contract.limits,
            }
        )

    # --- Study selection ---
    st.subheader("1. Choose study / experiment context")
    study_col, title_col = st.columns(2)
    with study_col:
        study_id = st.text_input(
            "Study ID (logical, 1-128 chars)",
            value=_DEFAULT_STUDY_ID,
            key="capsule_study_id",
        )
        study_version = st.text_input("Study version", value="1.0", key="capsule_study_version")
        study_title = st.text_input(
            "Study title (optional)",
            value="Manchester What-If: Demand Surge",
            key="capsule_study_title",
        )
        study_description = st.text_area(
            "Study description (optional)",
            value="",
            key="capsule_study_description",
            height=80,
        )
    with title_col:
        capsule_title = st.text_input(
            "Capsule title", value=_DEFAULT_CAPSULE_TITLE, key="capsule_capsule_title"
        )
        creation_date = st.date_input(
            "Creation date (deterministic)", value=date(2026, 8, 9), key="capsule_creation_date"
        )
        capsule_description = st.text_area(
            "Capsule description (optional)",
            value=(
                "Deterministic review package binding baseline/variation "
                "artifacts for supervisor review."
            ),
            key="capsule_description",
        )

    st.subheader("2. Choose eligible derived artifacts")
    st.caption(
        "Each member carries evidence and admission labels. Imported/raw "
        "evidence defaults to reference or exclusion."
    )
    # Kind selection
    kind_options = [k.value for k in StudyCapsuleMemberKind]
    default_kinds = [
        StudyCapsuleMemberKind.SCENARIO_SEED.value,
        StudyCapsuleMemberKind.RUN_SUMMARY.value,
        StudyCapsuleMemberKind.COMPARISON_REPORT.value,
        StudyCapsuleMemberKind.EVIDENCE_PACK.value,
        StudyCapsuleMemberKind.DETERMINISTIC_REPORT.value,
    ]
    selected_kind_strs = st.multiselect(
        "Artifact kinds to include (demo library)",
        options=kind_options,
        default=default_kinds,
        key="capsule_kind_select",
    )
    selected_kinds = {StudyCapsuleMemberKind(v) for v in selected_kind_strs}

    # Per-member policy and evidence overrides
    st.subheader("3. Member publication policy")
    st.caption(
        "EMBED_SAFE_DERIVED embeds bytes; REFERENCE_BY_FINGERPRINT stores "
        "fingerprint only; EXCLUDE records reason."
    )
    policy_overrides: dict[str, str] = {}
    evidence_overrides: dict[str, str] = {}
    # Build a table-like UI for each demo member that is selected
    table_rows: list[dict[str, str]] = []
    for kind, logical_id, default_ev in _DEMO_MEMBERS:
        if kind not in selected_kinds:
            continue
        key = f"{kind.value}:{logical_id}"
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            st.markdown(f"**{kind.value}** — `{logical_id}`")
        with col2:
            ev_choice = st.selectbox(
                f"Evidence {key}",
                options=_evidence_options(),
                index=_evidence_options().index(default_ev.value),
                key=f"ev_{key}",
                label_visibility="collapsed",
            )
            evidence_overrides[key] = ev_choice
        with col3:
            # Safe default: raw evidence must not default to EMBED
            raw_vals = {
                StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE.value,
                StudyCapsuleEvidenceLabel.HISTORICAL_OBSERVATION.value,
                StudyCapsuleEvidenceLabel.NEAR_LIVE_OPERATIONAL.value,
                StudyCapsuleEvidenceLabel.UNADMITTED_RESEARCH.value,
            }
            default_pol = (
                StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT.value
                if ev_choice in raw_vals
                else StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED.value
            )
            try:
                default_index = _policy_options().index(default_pol)
            except ValueError:
                default_index = 0
            pol_choice = st.selectbox(
                f"Policy {key}",
                options=_policy_options(),
                index=default_index,
                key=f"pol_{key}",
                label_visibility="collapsed",
            )
            policy_overrides[key] = pol_choice
        # Admission label is not exposed per-member for synthetic demo; defaults to not_applicable
        table_rows.append(
            {
                "kind": kind.value,
                "logical_id": logical_id,
                "evidence_label": evidence_overrides[key],
                "policy": policy_overrides[key],
            }
        )

    if table_rows:
        st.dataframe(table_rows, hide_index=True, width="stretch")

    st.warning(
        "Privacy: the portable manifest stores no absolute paths, secrets, or raw bytes "
        "for referenced/excluded members. Imported evidence is referenced by fingerprint only. "
        "Verifier proves internal integrity, not external authenticity."
    )

    # Limitations and unavailable (before preview so preview can use them)
    st.subheader("4. Limitations and unavailable evidence")
    limitations_text = st.text_area(
        "Limitations (one per line)",
        value="Synthetic single-run evidence only\nNo Manchester live traffic\n"
        "Not a proof of scientific validity",
        key="capsule_limitations",
    )
    limitations = [line.strip() for line in limitations_text.splitlines() if line.strip()]

    unavailable_col1, unavailable_col2 = st.columns(2)
    with unavailable_col1:
        unavailable_kind = st.selectbox(
            "Unavailable kind (optional)",
            options=[""] + kind_options,
            key="capsule_unavail_kind",
        )
    with unavailable_col2:
        unavailable_id = st.text_input("Unavailable logical ID", value="", key="capsule_unavail_id")
    unavailable_reason = st.text_input("Unavailable reason", value="", key="capsule_unavail_reason")

    unavailable_entries: list[StudyCapsuleUnavailable] = []
    if unavailable_kind and unavailable_id and unavailable_reason:
        try:
            unavailable_entries.append(
                StudyCapsuleUnavailable(
                    kind=StudyCapsuleMemberKind(unavailable_kind),
                    logical_id=unavailable_id,
                    reason=unavailable_reason,
                )
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Unavailable entry invalid: {exc}")

    # Preview what will be embedded / referenced / excluded / unavailable
    st.subheader("5. Preview: embedded / referenced / excluded / unavailable")
    preview_req = None
    try:
        preview_members = _build_default_members(
            selected_kinds, policy_overrides, evidence_overrides
        )
        preview_req = StudyCapsuleRequest(
            creation_date=creation_date if isinstance(creation_date, date) else date(2026, 8, 9),
            study_id=study_id,
            study_version=study_version,
            study_title=study_title or None,
            study_description=study_description or None,
            capsule_title=capsule_title,
            capsule_description=capsule_description or None,
            members=preview_members,
            limitations=limitations,
            unavailable=unavailable_entries,
        )
        preview = preview_membership(preview_req)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("**Embedded**")
            for item in preview["embedded"]:
                st.markdown(f"- `{item}`")
            if not preview["embedded"]:
                st.caption("none")
        with c2:
            st.markdown("**Referenced**")
            for item in preview["referenced"]:
                st.markdown(f"- `{item}`")
            if not preview["referenced"]:
                st.caption("none")
        with c3:
            st.markdown("**Excluded**")
            for item in preview["excluded"]:
                st.markdown(f"- `{item}`")
            if not preview["excluded"]:
                st.caption("none")
        with c4:
            st.markdown("**Unavailable**")
            for item in preview["unavailable"]:
                st.markdown(f"- `{item}`")
            if not preview["unavailable"]:
                st.caption("none")
        st.session_state["_capsule_preview_req"] = preview_req
    except Exception as exc:  # noqa: BLE001
        st.error(f"Preview validation failed: {exc}")

    # Build action
    st.subheader("6. Build capsule")
    if st.button("Build study capsule", type="primary", key="capsule_build"):
        try:
            members = _build_default_members(selected_kinds, policy_overrides, evidence_overrides)
            final_req = StudyCapsuleRequest(
                creation_date=creation_date
                if isinstance(creation_date, date)
                else date(2026, 8, 9),
                study_id=study_id,
                study_version=study_version,
                study_title=study_title or None,
                study_description=study_description or None,
                capsule_title=capsule_title,
                capsule_description=capsule_description or None,
                members=members,
                limitations=limitations,
                unavailable=unavailable_entries,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Request validation failed: {exc}")
            st.stop()
        # Build via production service
        try:
            built = build_study_capsule(final_req)
            # Verify preview matched manifest (UI build receipt)
            preview_before = preview_membership(final_req)
            manifest_embedded = sorted(
                [
                    f"{m.kind.value}:{m.logical_id}"
                    for m in built.manifest.members
                    if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED
                ]
            )
            if preview_before["embedded"] != manifest_embedded:
                st.error(
                    "UI preview does not match manifest embedded members — builder inconsistency"
                )
                st.stop()
            # Create archive atomically in temp location and capture bytes
            with tempfile.TemporaryDirectory() as td:
                tmp_path = Path(td) / "study-capsule.zip"
                receipt = create_study_capsule_archive(final_req, tmp_path)
                archive_bytes = tmp_path.read_bytes()
            st.session_state["_capsule_receipt"] = receipt.model_dump(mode="json")
            st.session_state["_capsule_archive_bytes"] = archive_bytes
            st.session_state["_capsule_manifest_json"] = built.manifest.model_dump_json(indent=2)
            st.session_state["_capsule_preview"] = preview_before
            st.success(f"Capsule built: {receipt.capsule_id}")
            st.json(receipt.model_dump(mode="json"))
            st.download_button(
                "Download deterministic archive",
                data=archive_bytes,
                file_name="study-capsule.zip",
                mime="application/zip",
                key="capsule_download",
            )
            with st.expander("Manifest (portable, canonical)", expanded=False):
                st.code(st.session_state["_capsule_manifest_json"], language="json")
            with st.expander("Member audit", expanded=False):
                audit_rows = [
                    {
                        "kind": m.kind.value,
                        "logical_id": m.logical_id,
                        "policy": m.policy.value,
                        "evidence": m.evidence_label.value,
                        "archive_path": m.archive_path or "—",
                        "sha256": (m.sha256[:12] + "…") if m.sha256 else "—",
                    }
                    for m in built.manifest.members
                ]
                st.dataframe(audit_rows, hide_index=True, width="stretch")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Build failed: {exc}")

    # Show previous receipt if exists
    if "_capsule_receipt" in st.session_state:
        st.subheader("Last build receipt")
        st.json(st.session_state["_capsule_receipt"])
        if "_capsule_archive_bytes" in st.session_state:
            st.download_button(
                "Download last archive again",
                data=st.session_state["_capsule_archive_bytes"],
                file_name="study-capsule.zip",
                mime="application/zip",
                key="capsule_download_again",
            )

    st.divider()
    st.subheader("7. Verify archive")
    st.caption(
        "Offline verification recomputes every embedded checksum and verifies the "
        "manifest fingerprint. It proves internal integrity, not external authenticity."
    )
    upload = st.file_uploader(
        "Upload capsule ZIP for verification", type=["zip"], key="capsule_verify_upload"
    )
    verify_path_str = st.text_input(
        "Or enter local archive path", value="", key="capsule_verify_path"
    )
    if st.button("Verify", key="capsule_verify_btn"):
        payload: bytes | None = None
        if upload is not None:
            payload = upload.getvalue()
        elif verify_path_str:
            try:
                payload = Path(verify_path_str).read_bytes()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Cannot read path: {exc}")
                st.stop()
        else:
            st.warning("Provide a ZIP upload or path to verify.")
            st.stop()
        assert payload is not None
        # Call production verifier (offline)
        verification = verify_study_capsule_bytes(payload)
        st.session_state["_capsule_verification"] = verification.model_dump(mode="json")
        if verification.valid:
            st.success(f"Verification PASSED — {verification.status.value}")
        else:
            st.error(f"Verification FAILED — {verification.status.value}")
        st.json(verification.model_dump(mode="json"))
        with st.expander("Member audit from archive", expanded=False):
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.markdown("**Embedded**")
                for item in verification.embedded_members:
                    st.markdown(f"- `{item}`")
                if not verification.embedded_members:
                    st.caption("none")
            with col_b:
                st.markdown("**Referenced**")
                for item in verification.referenced_members:
                    st.markdown(f"- `{item}`")
                if not verification.referenced_members:
                    st.caption("none")
            with col_c:
                st.markdown("**Excluded**")
                for item in verification.excluded_members:
                    st.markdown(f"- `{item}`")
                if not verification.excluded_members:
                    st.caption("none")
            with col_d:
                st.markdown("**Unavailable**")
                for item in verification.unavailable_members:
                    st.markdown(f"- `{item}`")
                if not verification.unavailable_members:
                    st.caption("none")
            if verification.errors:
                st.error("Errors:")
                for err in verification.errors:
                    st.markdown(f"- {err}")

    if "_capsule_verification" in st.session_state and upload is None and not verify_path_str:
        with st.expander("Last verification result", expanded=False):
            st.json(st.session_state["_capsule_verification"])
