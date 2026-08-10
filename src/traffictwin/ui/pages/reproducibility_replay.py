"""Reproducibility Replay page — allowlisted deterministic replay runner."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from traffictwin.reproducibility_replay.service import (
    build_receipt,
    build_replay_plan,
    build_replay_plan_from_capsule_bytes,
    execute_replay,
    plan_entries_to_csv,
    plan_to_json,
    receipt_to_csv,
    replay_contract,
    verify_capsule_integrity,
)


def _fingerprint_preview(fp: str | None) -> str:
    if fp is None:
        return "—"
    return fp[:12] + "…"


def render(config: object) -> None:  # noqa: ANN001,ARG001
    st.title("Reproducibility Replay")

    st.warning(
        "Evidence and authority boundary: this runner replays only allowlisted deterministic "
        "analyses (event-aligned report, resource-strategy report, preregistration gate, "
        "comparison report) from a verified study capsule or fingerprinted derived artifacts. "
        "Raw imported, historical, near-live, or unadmitted evidence is refused and never "
        "executed. A verifiable capsule or a matched replay proves internal integrity and "
        "byte-identical canonical output, not scientific validity, external authenticity, or causal effect."  # noqa: E501
    )

    st.caption(
        "No arbitrary Python or shell is executed. Only typed allowlisted requests are reconstructed "  # noqa: E501
        "via the registry. Unsigned authenticity is not claimed."
    )

    contract = replay_contract()
    with st.expander("Allowlisted contract", expanded=False):
        st.json(
            {
                "allowlisted_kinds": contract.allowlisted_kinds,
                "supported_versions": contract.supported_versions,
                "evidence_boundary": contract.evidence_boundary,
                "limitations": contract.limitations,
                "warnings": contract.warnings,
                "allowlist_fingerprint": contract.allowlist_fingerprint,
            }
        )

    # --- Capsule / artifact selection ---
    st.subheader("Capsule or artifact selection")
    st.caption(
        "Provide a verified study capsule ZIP or a standalone fingerprinted artifact JSON. No automatic run on page load."  # noqa: E501
    )

    uploaded = st.file_uploader(
        "Upload capsule ZIP",
        type=["zip"],
        key="replay_capsule_uploader",
    )
    path_str = st.text_input(
        "Or capsule path",
        value="",
        placeholder="path/to/study-capsule.zip",
        key="replay_capsule_path_input",
        help="Local path to a capsule ZIP for offline verification.",
    )
    standalone_uploader = st.file_uploader(
        "Or upload standalone artifact JSON (fingerprinted derived artifact)",
        type=["json"],
        key="replay_artifact_uploader",
    )
    standalone_text = st.text_area(
        "Or paste artifact JSON",
        value="",
        placeholder='{"schema_version":"1.0","report_id":"..."}',
        key="replay_artifact_text",
        height=120,
    )

    capsule_bytes: bytes | None = None
    _capsule_label: str | None = None
    if uploaded is not None:
        try:
            capsule_bytes = uploaded.getvalue()
            _capsule_label = uploaded.name  # noqa: F841
        except Exception as exc:
            st.error(f"Could not read uploaded capsule: {exc}")
            return
    elif path_str.strip():
        p = Path(path_str.strip())
        if not p.exists():
            st.error(f"Capsule path does not exist: {p}")
            return
        try:
            capsule_bytes = p.read_bytes()
            _capsule_label = str(p)  # noqa: F841
        except Exception as exc:
            st.error(f"Could not read capsule path: {exc}")
            return

    # Verification standing — before any results
    st.subheader("Verification standing")

    if capsule_bytes is not None:
        integrity = verify_capsule_integrity(capsule_bytes)
        cols = st.columns(3)
        cols[0].metric("Integrity", "valid" if integrity.valid else "invalid")
        cols[1].metric("Status", integrity.status)
        cols[2].metric(
            "Archive SHA-256", _fingerprint_preview(integrity.archive_sha256), border=True
        )
        st.caption(f"Full SHA-256: `{integrity.archive_sha256 or '—'}`")
        if integrity.capsule_id:
            st.markdown(f"**Capsule ID:** `{integrity.capsule_id}`")
        if integrity.manifest_fingerprint:
            st.markdown(f"**Manifest fingerprint:** `{integrity.manifest_fingerprint}`")
        if integrity.errors:
            st.error("Verification errors:")
            for err in integrity.errors:
                st.markdown(f"- {err}")
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.markdown("**Embedded**")
            for item in integrity.embedded_members:
                st.markdown(f"- `{item}`")
            if not integrity.embedded_members:
                st.caption("none")
        with col_b:
            st.markdown("**Referenced**")
            for item in integrity.referenced_members:
                st.markdown(f"- `{item}`")
            if not integrity.referenced_members:
                st.caption("none")
        with col_c:
            st.markdown("**Excluded**")
            for item in integrity.excluded_members:
                st.markdown(f"- `{item}`")
            if not integrity.excluded_members:
                st.caption("none")
        with col_d:
            st.markdown("**Unavailable**")
            for item in integrity.unavailable_members:
                st.markdown(f"- `{item}`")
            if not integrity.unavailable_members:
                st.caption("none")

        if not integrity.valid:
            st.warning(
                "Capsule integrity is not valid. Replay planning will refuse tampered or malformed inputs."  # noqa: E501
            )
            # Still show plan button but plan will contain refusal
    elif standalone_uploader is not None or standalone_text.strip():
        st.info(
            "Standalone artifact mode — capsule verification is not applicable. Allowlisted artifacts will be planned for replay."  # noqa: E501
        )
        st.caption(
            "Standalone artifacts must be fingerprinted derived artifacts, not raw evidence."
        )
    else:
        st.info(
            "No capsule or artifact selected. Upload a study capsule ZIP or provide a fingerprinted derived artifact. "  # noqa: E501
            "The page has a useful empty state when no verified capsule exists. No replay runs automatically."  # noqa: E501
        )
        st.caption(
            "Example: build a capsule via Study Capsule Builder, then replay its embedded deterministic reports here."  # noqa: E501
        )
        return

    # --- Plan ---
    st.subheader("Replay plan")
    st.caption("Plan declares which analyses are replayable. Raw evidence is never executed.")

    # We need to construct plan deterministically; keep in session state no auto-run
    plan = None
    if capsule_bytes is not None:
        plan = build_replay_plan_from_capsule_bytes(capsule_bytes)
    else:
        # Standalone mode
        raw_payload: bytes | None = None
        if standalone_uploader is not None:
            try:
                raw_payload = standalone_uploader.getvalue()
            except Exception as exc:
                st.error(f"Could not read artifact upload: {exc}")
                return
        elif standalone_text.strip():
            raw_payload = standalone_text.strip().encode("utf-8")
        if raw_payload:
            try:
                payload = json.loads(raw_payload)
                if not isinstance(payload, dict):
                    st.error("Artifact JSON must be an object.")
                    return
                # logical id heuristic
                lid = str(
                    payload.get("logical_id")
                    or payload.get("report_id")
                    or payload.get("study_id")
                    or "standalone-artifact"
                )
                evidence_label = (
                    str(payload.get("evidence_label"))
                    if isinstance(payload.get("evidence_label"), str)
                    else None
                )
                plan = build_replay_plan(standalone_artifacts=[(lid, payload, evidence_label)])
            except Exception as exc:
                st.error(f"Artifact JSON is invalid: {exc}")
                return

    if plan is None:
        st.error("No plan could be built.")
        return

    st.caption(f"Verification status: `{plan.verification_status}` · Entries: {len(plan.entries)}")
    if plan.warnings:
        for w in plan.warnings:
            st.warning(w)
    if plan.limitations:
        with st.expander("Limitations", expanded=False):
            for lim in plan.limitations:
                st.markdown(f"- {lim}")

    # Replayable / unavailable split
    replayable = [e for e in plan.entries if e.replayable]
    unavailable = [e for e in plan.entries if not e.replayable]

    st.markdown("**Replayable analyses (allowlisted)**")
    if replayable:
        rows = [
            {
                "artifact_kind": e.artifact_kind.value,
                "logical_id": e.logical_id,
                "status": e.status.value,
                "expected_fingerprint": _fingerprint_preview(e.expected_output_fingerprint),
                "reason": e.reason,
            }
            for e in replayable
        ]
        st.dataframe(rows, hide_index=True, width="stretch")
        with st.expander("Plan JSON", expanded=False):
            st.code(plan_to_json(plan), language="json")
        st.download_button(
            "Download plan JSON",
            data=plan_to_json(plan).encode("utf-8"),
            file_name="replay-plan.json",
            mime="application/json",
            key="replay_plan_download",
        )
        st.download_button(
            "Download plan CSV",
            data=plan_entries_to_csv(plan).encode("utf-8"),
            file_name="replay-plan.csv",
            mime="text/csv",
            key="replay_plan_csv",
        )
    else:
        st.caption("No replayable analyses in this capsule or artifact set.")

    st.markdown("**Unavailable or refused**")
    if unavailable:
        rows_u = [
            {
                "artifact_kind": e.artifact_kind.value,
                "logical_id": e.logical_id,
                "status": e.status.value,
                "reason": e.reason,
            }
            for e in unavailable
        ]
        st.dataframe(rows_u, hide_index=True, width="stretch")
    else:
        st.caption("All entries are replayable or no entries produced.")

    # --- Explicit selection ---
    st.subheader("Select replayable entries to run")
    st.caption("Only explicitly selected replayable entries will be executed. No automatic run.")

    if not replayable:
        st.info(
            "No replayable entries to execute. Provide a capsule with allowlisted derived artifacts or a fingerprinted report."  # noqa: E501
        )
        return

    options = [f"{e.artifact_kind.value}:{e.logical_id}" for e in replayable]
    selected_specs = st.multiselect(
        "Choose entries to replay",
        options,
        default=[],
        key="replay_selected_specs",
        help="Explicit selection is required; unselected replayable entries are not executed.",
    )

    # Preserve selection across reruns for display
    if "replay_receipt" in st.session_state and not selected_specs:
        # Show last receipt even without current selection
        with st.expander("Last receipt", expanded=False):
            st.json(st.session_state["replay_receipt"])

    run_clicked = st.button("Run selected replays", type="primary", key="replay_run_button")

    if run_clicked:
        if not selected_specs:
            st.warning("Select at least one replayable entry before running.")
            st.stop()
        # Parse selected into kind, logical_id
        from traffictwin.reproducibility_replay.models import ReplayArtifactKind

        selected: list[tuple[ReplayArtifactKind, str]] = []
        for spec in selected_specs:
            kind_str, logical_id = spec.split(":", 1)
            try:
                kind = ReplayArtifactKind(kind_str)
            except ValueError:
                st.error(f"Invalid kind in selection: {spec!r}")
                continue
            selected.append((kind, logical_id))

        executions, refusals = execute_replay(plan, selected=selected)
        receipt = build_receipt(plan, executions, refusals)
        st.session_state["replay_receipt"] = receipt.model_dump(mode="json")
        st.session_state["replay_receipt_canonical"] = receipt.canonical_json()
        st.session_state["replay_receipt_csv"] = receipt_to_csv(receipt)
        st.session_state["replay_plan_fp"] = plan.fingerprint()
        st.session_state["replay_receipt_fp"] = receipt.receipt_fingerprint
        st.success(
            f"Replay completed: {receipt.executed_count} executed · {receipt.matched_count} matched · {receipt.mismatched_count} mismatched · {receipt.failed_count} failed"  # noqa: E501
        )
        st.json(receipt.model_dump(mode="json"))
    elif "replay_receipt" in st.session_state:
        # Show receipt without re-running
        st.subheader("Receipt")
        st.json(st.session_state["replay_receipt"])
    else:
        st.info("Choose at least one replayable entry and press Run selected replays.")

    # --- Comparison details ---
    if "replay_receipt" in st.session_state:
        receipt_data = st.session_state["replay_receipt"]
        executions_data = receipt_data.get("executions", [])
        if executions_data:
            st.subheader("Expected versus actual fingerprint")
            rows_c = [
                {
                    "artifact_kind": e.get("artifact_kind"),
                    "logical_id": e.get("logical_id"),
                    "expected": _fingerprint_preview(e.get("expected_output_fingerprint")),
                    "actual": _fingerprint_preview(e.get("actual_output_fingerprint")),
                    "status": e.get("status"),
                    "reason": e.get("reason"),
                }
                for e in executions_data
            ]
            st.dataframe(rows_c, hide_index=True, width="stretch")
            # Detailed mismatch expander
            mismatches = receipt_data.get("mismatches", [])
            if mismatches:
                st.error("Mismatches")
                for m in mismatches:
                    st.markdown(
                        f"- `{m.get('artifact_kind')}:{m.get('logical_id')}` expected `{m.get('expected_fingerprint', '')[:12]}…` actual `{m.get('actual_fingerprint', '')[:12]}…` — {m.get('detail')}"  # noqa: E501
                    )
            else:
                st.success(
                    "No mismatches — all executed fingerprints matched expected fingerprints."
                )
        # Full fingerprint detail
        with st.expander("Fingerprint detail (full hex64)", expanded=False):
            for e in executions_data:
                st.markdown(
                    f"- `{e.get('artifact_kind')}:{e.get('logical_id')}` expected `{e.get('expected_output_fingerprint')}` actual `{e.get('actual_output_fingerprint') or '—'}` status `{e.get('status')}`"  # noqa: E501
                )

        # Receipt downloads
        st.subheader("Receipt download")
        st.caption(
            f"Plan fingerprint: `{st.session_state.get('replay_plan_fp', '—')}` · Receipt fingerprint: `{st.session_state.get('replay_receipt_fp', '—')}`"  # noqa: E501
        )
        st.download_button(
            "Download receipt JSON",
            data=json.dumps(receipt_data, indent=2, sort_keys=True).encode("utf-8"),
            file_name="replay-receipt.json",
            mime="application/json",
            key="replay_receipt_json",
        )
        st.download_button(
            "Download receipt CSV",
            data=st.session_state.get("replay_receipt_csv", "").encode("utf-8"),
            file_name="replay-receipt.csv",
            mime="text/csv",
            key="replay_receipt_csv",
        )
        with st.expander("Canonical receipt payload (deterministic)", expanded=False):
            st.code(st.session_state.get("replay_receipt_canonical", "{}"), language="json")
