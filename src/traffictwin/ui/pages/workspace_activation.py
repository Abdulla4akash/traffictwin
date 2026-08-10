"""Workspace Activation page — preview-first, confirmation-gated local activation."""

from __future__ import annotations

import json

import streamlit as st

from traffictwin.ui.state import UiConfig
from traffictwin.workspace_activation.models import (
    RetentionPolicy,
    WorkspaceActivationConfirmation,
    WorkspaceActivationRequest,
)
from traffictwin.workspace_activation.service import (
    ActivationRefusedError,
    activate_workspace,
    build_activation_plan,
    deactivate_workspace,
    get_workspace_status,
    plan_to_csv,
    plan_to_json,
    preflight_to_csv,
    preflight_to_json,
    preflight_workspace,
    receipt_to_csv,
    receipt_to_json,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request_from_state() -> WorkspaceActivationRequest:
    dest = str(st.session_state.get("ws_dest", "")).strip() or "/tmp/traffictwin-workspace-demo"  # noqa: S108
    bods = bool(st.session_state.get("ws_bods", False))
    nh = bool(st.session_state.get("ws_nh", False))
    retention_days = int(st.session_state.get("ws_retention_days", 30))
    anonymize = bool(st.session_state.get("ws_anonymize", True))
    allow_export = bool(st.session_state.get("ws_allow_export", False))
    backup = str(st.session_state.get("ws_backup", "")).strip() or None
    start_workers = bool(st.session_state.get("ws_start_workers", False))
    workers_str = str(st.session_state.get("ws_workers", "")).strip()
    workers = [w.strip() for w in workers_str.split(",") if w.strip()] if workers_str else []
    return WorkspaceActivationRequest(
        destination_path=dest,
        bods_enabled=bods,
        national_highways_enabled=nh,
        retention_policy=RetentionPolicy(
            retention_days=retention_days, anonymize=anonymize, allow_export=allow_export
        ),
        backup_destination=backup,
        start_workers=start_workers,
        allowlisted_workers=workers,
    )


def _render_boundary() -> None:
    st.info(
        "Local preview-first, confirmation-gated workspace activation. "
        "This is NOT public deployment or production activation. "
        "Workspace activation does not make provider network requests; it records provider readiness/configuration only. "  # noqa: E501
        "BODS and National Highways checks show configuration and credential **presence only** (no values). "  # noqa: E501
        "All actions are typed, deterministic, and bounded; incompatible requests are refused (fail-closed)."  # noqa: E501
    )
    st.caption(
        "Evidence and authority boundary: synthetic demonstration only — no Manchester live data or production readiness is claimed."  # noqa: E501
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render(config: UiConfig | None = None) -> None:  # noqa: ARG001
    """Render workspace activation wizard."""
    st.title("Workspace Activation")
    _render_boundary()

    # Empty state guidance
    if not st.session_state.get("ws_dest"):
        st.caption(
            "Enter a destination path to begin. Use a local empty or new directory outside the repository, e.g. /tmp/traffictwin-workspace-demo."  # noqa: E501
        )

    # ------------------------------------------------------------------
    # Path selection
    # ------------------------------------------------------------------
    st.subheader("Destination")
    st.text_input(
        "Workspace destination path",
        value=st.session_state.get("ws_dest", "/tmp/traffictwin-workspace-demo"),  # noqa: S108
        key="ws_dest",
        help="Absolute path to a local workspace directory. Symlink escapes and unmanaged non-empty targets are refused.",  # noqa: E501
    )
    st.text_input(
        "Backup destination (optional)",
        value=st.session_state.get("ws_backup", ""),
        key="ws_backup",
        help="Optional backup path. If empty, a default backups/ inside the workspace is used.",
    )

    # ------------------------------------------------------------------
    # Retention / privacy review
    # ------------------------------------------------------------------
    st.subheader("Retention and privacy")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.number_input(
            "Retention days",
            min_value=1,
            max_value=3650,
            value=int(st.session_state.get("ws_retention_days", 30)),
            key="ws_retention_days",
        )
    with col_b:
        st.checkbox(
            "Anonymize", value=bool(st.session_state.get("ws_anonymize", True)), key="ws_anonymize"
        )
    with col_c:
        st.checkbox(
            "Allow export",
            value=bool(st.session_state.get("ws_allow_export", False)),
            key="ws_allow_export",
        )
    st.caption(
        "Retention policy is reviewed explicitly before planning; anonymization and export flags are never inferred."  # noqa: E501
    )

    # ------------------------------------------------------------------
    # Provider and worker options
    # ------------------------------------------------------------------
    st.subheader("Providers and workers")
    st.checkbox(
        "Enable BODS provider",
        value=bool(st.session_state.get("ws_bods", False)),
        key="ws_bods",
        help="If enabled, BODS credential/configuration presence is checked without revealing values or making network calls.",  # noqa: E501
    )
    st.checkbox(
        "Enable National Highways provider",
        value=bool(st.session_state.get("ws_nh", False)),
        key="ws_nh",
        help="If enabled, National Highways credential/configuration presence is checked without revealing values or making network calls.",  # noqa: E501
    )
    st.checkbox(
        "Start allowlisted workers after activation",
        value=bool(st.session_state.get("ws_start_workers", False)),
        key="ws_start_workers",
    )
    st.text_input(
        "Allowlisted workers (comma-separated)",
        value=st.session_state.get("ws_workers", ""),
        key="ws_workers",
        help="Only allowlisted workers may start: aggregate-compactor, evidence-indexer, provenance-builder.",  # noqa: E501
    )

    # ------------------------------------------------------------------
    # Dry-run preflight
    # ------------------------------------------------------------------
    st.subheader("Dry-run preflight")
    if st.button("Run preflight", key="ws_preflight_btn"):
        try:
            req = _request_from_state()
            pre = preflight_workspace(req)
            st.session_state["ws_preflight"] = pre
            st.session_state["ws_preflight_request_fp"] = req.fingerprint()
            st.success("Preflight completed without mutation.")
        except Exception as exc:
            st.error(f"Preflight failed: {exc}")

    pre = st.session_state.get("ws_preflight")
    if pre is not None:
        st.markdown("**Preflight result**")
        # Credential presence indicators (no values)
        st.markdown("**Credential presence (values never shown)**")
        for cred in pre.credential_presence:
            icon = "✅" if cred.present else "⚪"
            st.write(
                f"{icon} {cred.name} ({cred.env_var}): {'present' if cred.present else 'not present'} — source: {cred.source}"  # noqa: E501
            )

        # Findings
        if pre.findings:
            st.markdown("**Findings**")
            for f in pre.findings:
                if f.severity.value == "error":
                    st.error(f"{f.code} [{f.category}]: {f.message}")
                elif f.severity.value == "warning":
                    st.warning(f"{f.code} [{f.category}]: {f.message}")
                else:
                    st.info(f"{f.code} [{f.category}]: {f.message}")
        else:
            st.info("No findings.")

        # Provider readiness
        st.markdown("**Provider readiness (no network calls)**")
        for pr in pre.provider_readiness:
            badge = pr.status.value
            st.write(f"- {pr.provider.value}: enabled={pr.enabled} status={badge} — {pr.detail}")

        # Extra fields
        st.write(
            f"Path valid: {pre.path_valid} | Is managed: {pre.is_managed} | Is empty: {pre.is_empty}"  # noqa: E501
        )
        st.write(
            f"Disk available: {pre.disk_available_bytes} bytes | Required: {pre.disk_required_bytes} bytes | Version OK: {pre.version_ok} | Ready to plan: {pre.ready_to_plan}"  # noqa: E501
        )
        st.write(
            f"Retention: {pre.retention_policy.retention_days} days, anonymize={pre.retention_policy.anonymize}, allow_export={pre.retention_policy.allow_export}"  # noqa: E501
        )
        st.write(
            f"Aggregate store ready: {pre.aggregate_store_ready} | Backup ready: {pre.backup_ready}"
        )
        if pre.worker_readiness:
            st.markdown("**Worker readiness**")
            for wf in pre.worker_readiness:
                st.write(f"- {wf.code}: {wf.message}")

        # Exports
        st.download_button(
            "Download preflight JSON",
            data=preflight_to_json(pre),
            file_name="preflight.json",
            mime="application/json",
            key="ws_preflight_json",
        )
        st.download_button(
            "Download preflight CSV",
            data=preflight_to_csv(pre),
            file_name="preflight.csv",
            mime="text/csv",
            key="ws_preflight_csv",
        )
    else:
        st.caption(
            "No preflight yet. Run a dry-run preflight to see credential presence, path checks, and provider readiness before planning."  # noqa: E501
        )

    # ------------------------------------------------------------------
    # Activation plan
    # ------------------------------------------------------------------
    st.subheader("Activation plan")
    if st.button("Build activation plan", key="ws_plan_btn"):
        try:
            req = _request_from_state()
            pre = st.session_state.get("ws_preflight")
            # If preflight exists but is stale (fingerprint mismatch), build_plan will refuse; we surface that  # noqa: E501
            plan = build_activation_plan(req, pre)
            st.session_state["ws_plan"] = plan
            st.session_state["ws_plan_request_fp"] = req.fingerprint()
            st.success(f"Plan built. Confirmation digest: {plan.confirmation_digest}")
        except ActivationRefusedError as exc:
            st.error(f"Plan refused: {exc.code}: {exc.message}")
        except Exception as exc:
            st.error(f"Plan failed: {exc}")

    plan = st.session_state.get("ws_plan")
    if plan is not None:
        st.markdown("**Plan preview (deterministic)**")
        st.write(f"Plan version: {plan.plan_version}")
        st.write(f"Request fingerprint: `{plan.request_fingerprint}`")
        st.write(f"Destination: `{plan.destination_path}`")
        st.markdown("**Directories to create**")
        for d in plan.directories_to_create:
            st.code(d, language=None)
        st.markdown("**Files to create**")
        for f in plan.files_to_create:
            st.code(f, language=None)
        st.markdown("**Database initialization**")
        for db in plan.database_initialization:
            st.code(db, language=None)
        st.markdown("**Provider configurations**")
        for pc in plan.provider_configurations:
            st.write(
                f"- {pc.provider.value}: enabled={pc.enabled} status={pc.status.value} — {pc.detail}"  # noqa: E501
            )
        st.write(
            f"Retention: {plan.retention_settings.retention_days} days, anonymize={plan.retention_settings.anonymize}, allow_export={plan.retention_settings.allow_export}"  # noqa: E501
        )
        st.write(f"Worker start options: {plan.worker_start_options or 'none'}")
        st.markdown("**Backup and rollback**")
        st.info(f"Backup plan: {plan.backup_plan}")
        st.info(f"Rollback plan: {plan.rollback_plan}")
        st.markdown("**Actions**")
        for a in plan.actions:
            st.write(f"- {a.kind.value}: `{a.target}` — {a.detail}")
        st.code(f"Confirmation digest: {plan.confirmation_digest}", language=None)
        st.caption(
            "Mutation is allowed only when the caller supplies this exact preview digest. Changed request after preview: REFUSED."  # noqa: E501
        )
        st.download_button(
            "Download plan JSON",
            data=plan_to_json(plan),
            file_name="plan.json",
            mime="application/json",
            key="ws_plan_json",
        )
        st.download_button(
            "Download plan CSV",
            data=plan_to_csv(plan),
            file_name="plan.csv",
            mime="text/csv",
            key="ws_plan_csv",
        )
    else:
        st.caption(
            "No plan yet. Build a deterministic activation plan to review all filesystem, database, and configuration effects before confirming."  # noqa: E501
        )

    # ------------------------------------------------------------------
    # Confirmation and activation
    # ------------------------------------------------------------------
    st.subheader("Confirmation and activation")
    st.text_input(
        "Confirmation digest (paste exact plan digest to authorize mutation)",
        value=st.session_state.get("ws_confirmation", ""),
        key="ws_confirmation",
        help="Activation proceeds only when this digest exactly matches the preview plan digest.",
    )
    if st.button("Activate workspace", key="ws_activate_btn", type="primary"):
        try:
            req = _request_from_state()
            plan = st.session_state.get("ws_plan")
            if plan is None:
                st.error("No plan built. Build a plan first.")
            else:
                digest = str(st.session_state.get("ws_confirmation", "")).strip()
                if not digest:
                    st.error("Confirmation digest is required.")
                else:
                    conf = WorkspaceActivationConfirmation(
                        confirmation_digest=digest, request_fingerprint=req.fingerprint()
                    )
                    receipt = activate_workspace(req, plan, conf)
                    st.session_state["ws_receipt"] = receipt
                    if receipt.status == "already_active":
                        st.success(
                            f"Workspace already active (idempotent retry). Confirmation digest: {receipt.confirmation_digest}"  # noqa: E501
                        )
                    else:
                        st.success(f"Workspace activated. Marker: {receipt.marker_path}")
                    st.json(json.loads(receipt.canonical_json()))
        except ActivationRefusedError as exc:
            st.error(f"Activation refused: {exc.code}: {exc.message}")
        except Exception as exc:
            st.error(f"Activation failed: {exc}")

    receipt = st.session_state.get("ws_receipt")
    if receipt is not None:
        st.markdown("**Activation receipt**")
        st.json(json.loads(receipt.canonical_json()))
        st.download_button(
            "Download receipt JSON",
            data=receipt_to_json(receipt),
            file_name="receipt.json",
            mime="application/json",
            key="ws_receipt_json",
        )
        st.download_button(
            "Download receipt CSV",
            data=receipt_to_csv(receipt),
            file_name="receipt.csv",
            mime="text/csv",
            key="ws_receipt_csv",
        )

    # ------------------------------------------------------------------
    # Status and deactivation
    # ------------------------------------------------------------------
    st.subheader("Status and deactivation")
    if st.button("Refresh status", key="ws_status_btn"):
        try:
            req = _request_from_state()
            status = get_workspace_status(req.destination_path)
            st.session_state["ws_status"] = status
        except Exception as exc:
            st.error(f"Status failed: {exc}")

    status = st.session_state.get("ws_status")
    if status is not None:
        st.write(
            f"Exists: {status.exists} | Managed: {status.is_managed} | Active: {status.is_active} | Marker present: {status.marker_present}"  # noqa: E501
        )
        if status.receipt:
            st.json(json.loads(status.receipt.canonical_json()))
        for f in status.findings:
            st.write(f"- {f.code}: {f.message}")
        st.write("Providers:")
        for p in status.providers:
            st.write(f"- {p.provider.value}: {p.status.value}")

    st.markdown("**Deactivation (preserves data by default)**")
    st.caption(
        "Deactivation stops only managed local workers and preserves evidence and stores. Marker removal requires confirmation."  # noqa: E501
    )
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if st.button("Deactivate (keep marker)", key="ws_deactivate_keep"):
            try:
                req = _request_from_state()
                rec = deactivate_workspace(req.destination_path, remove_marker=False)
                st.session_state["ws_deactivate_receipt"] = rec
                st.success(
                    f"Deactivation completed. Workers stopped: {rec.workers_stopped}. Preserved: {rec.preserved_paths}"  # noqa: E501
                )
                st.json(json.loads(rec.canonical_json()))
            except Exception as exc:
                st.error(f"Deactivation failed: {exc}")
    with col_d2:
        if st.button(
            "Deactivate and remove marker (confirmation required)", key="ws_deactivate_remove"
        ):
            try:
                req = _request_from_state()
                digest = str(st.session_state.get("ws_confirmation", "")).strip()
                if not digest:
                    st.error("Confirmation digest is required to remove marker.")
                else:
                    status = get_workspace_status(req.destination_path)
                    fp = status.receipt.request_fingerprint if status.receipt else None
                    conf = WorkspaceActivationConfirmation(
                        confirmation_digest=digest, request_fingerprint=fp
                    )
                    rec = deactivate_workspace(
                        req.destination_path, confirmation=conf, remove_marker=True
                    )
                    st.session_state["ws_deactivate_receipt"] = rec
                    st.success(
                        f"Deactivation with marker removal completed. Marker removed: {rec.marker_removed}"  # noqa: E501
                    )
                    st.json(json.loads(rec.canonical_json()))
            except ActivationRefusedError as exc:
                st.error(f"Deactivation refused: {exc.code}: {exc.message}")
            except Exception as exc:
                st.error(f"Deactivation failed: {exc}")

    drec = st.session_state.get("ws_deactivate_receipt")
    if drec is not None:
        st.download_button(
            "Download deactivation JSON",
            data=drec.canonical_json(),
            file_name="deactivation.json",
            mime="application/json",
            key="ws_deactivate_json",
        )

    st.caption(
        "No secrets are displayed or stored. Credential presence is shown only as present/not present."  # noqa: E501
    )
