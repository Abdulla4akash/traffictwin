"""Baseline Registry page — explicit, versioned workflow for declaring the current baseline."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from traffictwin.baseline_registry.models import (
    BaselineArtifactType,
    BaselineEvidenceStanding,
    BaselinePromotionOperation,
    BaselineRegistry,
    BaselineScope,
    BaselineSourceStanding,
)
from traffictwin.baseline_registry.service import (
    active_baselines_to_csv,
    approve_candidate,
    build_candidate,
    candidates_to_csv,
    create_empty_registry,
    is_candidate_withdrawn,
    list_restorable_candidates,
    promote_baseline,
    register_candidate,
    registry_limitations,
    registry_to_csv,
    registry_to_json,
    restore_baseline_as_new_promotion,
    supersede_baseline,
    withdraw_candidate,
)
from traffictwin.baseline_registry.sta04_adapter import baseline_to_sta04_reference
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.tables import table_column_config

SESSION_KEY = "baseline_registry_state"


def _get_registry() -> BaselineRegistry:
    if SESSION_KEY not in st.session_state:
        # Use fixed clock for deterministic demo registry? Use real clock.
        st.session_state[SESSION_KEY] = create_empty_registry()
        # Seed with two demo candidates for empty-state usefulness demonstration
        try:
            reg = st.session_state[SESSION_KEY]
            scope = BaselineScope(
                scope_id="scope-demo-traffic",
                purpose="Traffic corridor mean journey-time comparison for controlled evaluation",
                cohort_definition="Matched random seeds 1..5 under synthetic signal plan A",
                allowed_evidence_standings=(BaselineEvidenceStanding.ADMITTED_RESEARCH,),
            )
            cand_a = build_candidate(
                candidate_id="candidate-demo-a",
                scope=scope,
                artifact_fingerprint="a" * 64,
                artifact_type="metric_collection",
                schema_version="1.0",
                metric_contracts=["task.completion.rate@1.0"],
                cohort_definition=scope.cohort_definition,
                evidence_standing="synthetic_demonstration",
                source_standing="synthetic",
                regression_gate_policy="STA-04 exact synthetic baseline policy",
                limitations=(
                    "Synthetic demonstration only; not Manchester observation; no causal claim."
                ),
            )
            reg = register_candidate(reg, cand_a, actor="demo")
            reg, _ = approve_candidate(
                reg,
                candidate_id="candidate-demo-a",
                approver="demo-reviewer",
                approval_note="Demo approval for synthetic baseline demonstration.",
            )
            st.session_state[SESSION_KEY] = reg
        except Exception:  # noqa: S110
            pass
    value = st.session_state[SESSION_KEY]
    assert isinstance(value, BaselineRegistry)
    return value


def _set_registry(registry: BaselineRegistry) -> None:
    st.session_state[SESSION_KEY] = registry


def render(config: object) -> None:  # noqa: ARG001
    """Render the Baseline Registry."""
    del config
    render_page_header(UiPage.BASELINE_REGISTRY) if hasattr(
        UiPage, "BASELINE_REGISTRY"
    ) else st.title("Baseline Registry")
    # Evidence/authority boundary – must appear before results (page quality gate)
    st.warning(
        "This page declares which exact artifact is the current baseline for a specific purpose. "
        "The newest, fastest, or lowest-error candidate is never promoted automatically. "
        "Promotion requires an explicit review record."
    )
    st.caption(
        "Evidence and authority boundary: synthetic demonstration evidence remains synthetic and "
        "is never relabelled as observed. Unadmitted evidence stays unadmitted; zero is never "
        "substituted for missing evidence; no causality or optimality claim is made without a "
        "declared decision contract."
    )
    st.caption(
        "Portable exports exclude local paths, retrieval clocks, and secrets. Fingerprints use "
        "deterministic canonical JSON with stable SHA-256."
    )

    registry = _get_registry()

    # Flash notice for withdrawal of active baseline (survives rerun)
    flash = st.session_state.pop("baseline_withdraw_flash", None)
    if flash:
        # Use warning to make operator immediately see the actual result
        st.warning(flash)

    # ------------------------------------------------------------------
    # Limitations
    # ------------------------------------------------------------------
    with st.expander("Limitations and interpretation boundary"):
        for lim in registry_limitations():
            st.markdown(f"- {lim}")
        st.caption(
            "Manchester evidence requires genuine admitted Manchester evidence; not claimed here."
        )

    # ------------------------------------------------------------------
    # Empty state
    # ------------------------------------------------------------------
    if not registry.candidates and not registry.active_baselines:
        st.info(
            "No baseline candidates registered. Use the Register candidate form below to propose "
            "a candidate. The registry is empty — this is the useful empty state."
        )

    # ------------------------------------------------------------------
    # Current active baselines
    # ------------------------------------------------------------------
    st.subheader("Current active baselines")
    if registry.active_baselines:
        rows = []
        for scope_id, rec in sorted(registry.active_baselines.items()):
            withdrawn_flag = is_candidate_withdrawn(registry, rec.candidate_id, scope_id)
            rows.append(
                {
                    "scope_id": scope_id,
                    "baseline_id": rec.baseline_id,
                    "candidate_id": rec.candidate_id,
                    "artifact_fingerprint": rec.artifact_fingerprint,
                    "fp_short": fingerprint_summary(rec.artifact_fingerprint),
                    "artifact_type": rec.artifact_type.value,
                    "evidence_standing": rec.evidence_standing.value,
                    "source_standing": rec.source_standing.value,
                    "approval_fingerprint": fingerprint_summary(rec.approval_fingerprint),
                    "effective_date": rec.effective_date.isoformat(),
                    "superseded": fingerprint_summary(rec.superseded_baseline_fingerprint)
                    if rec.superseded_baseline_fingerprint
                    else "—",
                    "record_fingerprint": fingerprint_summary(rec.record_fingerprint),
                    "candidate_withdrawn": withdrawn_flag,
                    "status": rec.status.value,
                }
            )
        st.dataframe(
            rows, hide_index=True, width="stretch", column_config=table_column_config(rows)
        )
        with st.expander("Advanced: exact fingerprints"):
            for rec in sorted(registry.active_baselines.values(), key=lambda r: r.scope.scope_id):
                st.code(
                    f"{rec.scope.scope_id} record_fingerprint={rec.record_fingerprint}\nartifact={rec.artifact_fingerprint}\napproval={rec.approval_fingerprint}",  # noqa: E501
                    language=None,
                )
                # STA-04 adapter preview
                ref = baseline_to_sta04_reference(rec)
                st.caption(
                    f"STA-04 reference fingerprint: {ref.fingerprint()} "  # noqa: E501
                    f"novel policy={ref.regression_gate_policy}"
                )
    else:
        st.caption(  # noqa: E501
            "No active baseline. A scope has an active baseline only after an approved "
            "candidate is promoted through the explicit promotion gate."
        )
        st.markdown(":gray-badge[UNAVAILABLE] No active baseline in any scope")

    # ------------------------------------------------------------------
    # Candidates
    # ------------------------------------------------------------------
    st.subheader("Candidates")
    if registry.candidates:
        cand_rows = []
        for cand_id, cand in sorted(registry.candidates.items()):
            is_active = any(
                rec.candidate_id == cand_id for rec in registry.active_baselines.values()
            )
            is_approved = cand_id in registry.approvals
            withdrawn = is_candidate_withdrawn(registry, cand_id, cand.scope.scope_id)
            cand_rows.append(
                {
                    "candidate_id": cand_id,
                    "scope_id": cand.scope.scope_id,
                    "artifact_fp": fingerprint_summary(cand.artifact_fingerprint),
                    "full_fp": cand.artifact_fingerprint,
                    "artifact_type": cand.artifact_type.value,
                    "evidence_standing": cand.evidence_standing.value,
                    "source_standing": cand.source_standing.value,
                    "schema": cand.schema_version,
                    "approved": "yes" if is_approved else "no",
                    "active": "yes" if is_active else "no",
                    "withdrawn": withdrawn,
                }
            )
        st.dataframe(
            cand_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(cand_rows),
        )
        with st.expander("Advanced: candidate fingerprints"):
            for c in sorted(registry.candidates.values(), key=lambda x: x.candidate_id):
                st.code(
                    f"{c.candidate_id} full artifact fingerprint: {c.artifact_fingerprint}",
                    language=None,
                )
    else:
        st.caption("No candidates. Register one below.")

    # ------------------------------------------------------------------
    # Compatibility audit preview (last promotion)
    # ------------------------------------------------------------------
    st.subheader("Compatibility audit")
    # Show last audit if any promotion receipt in session?
    last_audit = st.session_state.get("baseline_last_audit")
    if last_audit is not None:
        st.json(
            last_audit.model_dump(mode="json") if hasattr(last_audit, "model_dump") else last_audit
        )
        st.caption(
            f"Audit fingerprint: {getattr(last_audit, 'audit_fingerprint', '')}"  # noqa: E501
        )
        st.caption(f"Passed: {last_audit.passed if hasattr(last_audit, 'passed') else ''}")
    else:
        st.caption(
            "No compatibility audit yet. Promote or supersede a candidate to generate an audit."
        )
        st.markdown(":gray-badge[UNAVAILABLE] No audit available")

    # ------------------------------------------------------------------
    # Approval history
    # ------------------------------------------------------------------
    st.subheader("Approval history")
    if registry.approvals:
        appr_rows = []
        for cid, appr in sorted(registry.approvals.items()):
            appr_rows.append(
                {
                    "candidate_id": cid,
                    "approval_id": appr.approval_id,
                    "scope_id": appr.scope_id,
                    "approver": appr.approver,
                    "approval_fp": fingerprint_summary(appr.approval_fingerprint),
                    "artifact_fp": fingerprint_summary(appr.artifact_fingerprint),
                    "approved_at": appr.approved_at.isoformat(),
                }
            )
        st.dataframe(
            appr_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(appr_rows),
        )
        with st.expander("Advanced: approval fingerprints"):
            for a in sorted(registry.approvals.values(), key=lambda x: x.candidate_id):
                st.code(
                    f"{a.candidate_id} approval_fingerprint={a.approval_fingerprint}"  # noqa: E501
                    f"\nartifact={a.artifact_fingerprint}",
                    language=None,
                )
    else:
        st.caption(
            "No approvals. Approve a candidate before promotion; "  # noqa: E501
            "promotion without approval is BLOCKED."
        )

    # ------------------------------------------------------------------
    # Promote / supersede flow
    # ------------------------------------------------------------------
    st.subheader("Promote / supersede flow")
    st.caption(  # noqa: E501
        "Promotion gate requires: candidate exists, exact artifact fingerprint verified, "
        "compatibility passes, evidence policy satisfied, "  # noqa: E501
        "explicit approval binds exact candidate+scope+ "  # noqa: E501
        "fingerprint, no stale parent, no conflicting active baseline in same "  # noqa: E501
        "scope. All checks are fail-closed."  # noqa: E501
    )

    col1, col2 = st.columns(2)
    with col1:
        with st.form("baseline_register_form"):
            st.markdown("**Register candidate**")
            reg_cand_id = st.text_input(
                "Candidate ID", value="candidate-002", key="baseline_reg_cand_id"
            )
            reg_scope_id = st.text_input(
                "Candidate scope ID", value="scope-demo-traffic", key="baseline_reg_scope"
            )
            reg_purpose = st.text_input(
                "Purpose",
                value="Traffic corridor mean journey-time baseline for evaluation",
                key="baseline_reg_purpose",
            )
            reg_cohort = st.text_input(
                "Cohort definition",
                value="Matched random seeds 1..5 under synthetic signal plan A",
                key="baseline_reg_cohort",
            )
            reg_fp = st.text_input(
                "Artifact fingerprint (64 hex)", value="b" * 64, key="baseline_reg_fp"
            )

            reg_type_actual = st.selectbox(
                "Artifact type",
                options=[t.value for t in BaselineArtifactType],
                key="baseline_reg_type",
            )
            reg_schema = st.text_input("Schema version", value="1.0.0", key="baseline_reg_schema")
            reg_evidence = st.selectbox(
                "Evidence standing",
                options=[e.value for e in BaselineEvidenceStanding],
                key="baseline_reg_evidence",
            )
            reg_source = st.selectbox(
                "Source standing",
                options=[s.value for s in BaselineSourceStanding],
                key="baseline_reg_source",
            )
            reg_allowed = st.multiselect(
                "Allowed evidence standings (typed policy)",
                options=[e.value for e in BaselineEvidenceStanding if e.value != "unavailable"],
                default=["admitted_research"],
                key="baseline_reg_allowed",
            )
            reg_policy = st.text_input(
                "Regression gate policy",
                value="STA-04 exact synthetic baseline policy",
                key="baseline_reg_policy",
            )
            reg_limit = st.text_input(
                "Limitations",
                value="Synthetic demonstration only; no causal claim.",
                key="baseline_reg_limit",
            )
            reg_metric = st.text_input(
                "Metric contracts (comma-separated)",
                value="task.completion.rate@1.0",
                key="baseline_reg_metric",
            )
            submitted_reg = st.form_submit_button("Register candidate")
        if submitted_reg:
            try:
                allowed_tuple = (
                    tuple(BaselineEvidenceStanding(v) for v in reg_allowed)
                    if reg_allowed
                    else (BaselineEvidenceStanding.ADMITTED_RESEARCH,)
                )
                # Canonicalize sorted
                allowed_tuple = tuple(sorted(set(allowed_tuple), key=lambda x: x.value))
                scope = BaselineScope(
                    scope_id=reg_scope_id,
                    purpose=reg_purpose,
                    cohort_definition=reg_cohort,
                    allowed_evidence_standings=allowed_tuple,
                )
                contracts = [c.strip() for c in reg_metric.split(",") if c.strip()]
                cand = build_candidate(
                    candidate_id=reg_cand_id,
                    scope=scope,
                    artifact_fingerprint=reg_fp,
                    artifact_type=reg_type_actual,
                    schema_version=reg_schema,
                    metric_contracts=contracts,
                    cohort_definition=reg_cohort,
                    evidence_standing=reg_evidence,
                    source_standing=reg_source,
                    regression_gate_policy=reg_policy,
                    limitations=reg_limit,
                )
                new_reg = register_candidate(registry, cand, actor="ui")
                _set_registry(new_reg)
                st.success(f"Registered candidate {reg_cand_id}")
                st.rerun()
            except Exception as exc:
                st.error(f"Register failed (fail-closed): {exc}")

    with col2:
        with st.form("baseline_approve_form"):
            st.markdown("**Approve candidate**")
            appr_cand_id = st.text_input(
                "Candidate ID to approve", value="candidate-002", key="baseline_appr_cand"
            )
            appr_approver = st.text_input(
                "Approver", value="reviewer-alice", key="baseline_appr_approver"
            )
            appr_note = st.text_input(
                "Approval note",
                value="Reviewed and approved for promotion after gate review.",
                key="baseline_appr_note",
            )
            submitted_appr = st.form_submit_button("Approve")
        if submitted_appr:
            try:
                new_reg, approval = approve_candidate(
                    registry,
                    candidate_id=appr_cand_id,
                    approver=appr_approver,
                    approval_note=appr_note,
                )
                _set_registry(new_reg)
                st.success(
                    f"Approved {appr_cand_id} approval_fp={approval.approval_fingerprint[:12]}…"
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Approve failed: {exc}")

    # Promote form
    with st.form("baseline_promote_form"):
        st.markdown("**Promote candidate to active baseline**")
        prom_cand_id = st.text_input(
            "Candidate ID to promote", value="candidate-demo-a", key="baseline_prom_cand"
        )
        prom_actor = st.text_input("Requested by", value="operator", key="baseline_prom_actor")
        submitted_prom = st.form_submit_button("Promote")
    if submitted_prom:
        from traffictwin.baseline_registry.models import BaselinePromotionRequest

        if prom_cand_id not in registry.candidates:
            st.error(f"Candidate {prom_cand_id!r} does not exist — BLOCKED")
        else:
            cand = registry.candidates[prom_cand_id]
            approval = registry.approvals.get(prom_cand_id)  # type: ignore[assignment]
            if approval is None:
                st.error(
                    "No approval exists for candidate — BLOCKED "  # noqa: E501
                    "(promotion requires explicit approval)"
                )
                # Still create audit for display
                # Create blocked receipt manually for UI
                req = BaselinePromotionRequest(
                    candidate_id=prom_cand_id,
                    scope_id=cand.scope.scope_id,
                    artifact_fingerprint=cand.artifact_fingerprint,
                    approval_fingerprint="0" * 64,
                    registry_parent_fingerprint=registry.registry_fingerprint,
                    requested_by=prom_actor,
                    requested_at=datetime.now(UTC),
                    operation=BaselinePromotionOperation.PROMOTE,
                )
                _, receipt = promote_baseline(registry, req)
                st.session_state["baseline_last_audit"] = receipt.audit
                st.error(f"Promotion BLOCKED: {'; '.join(receipt.blocked_reasons)}")
            else:
                req = BaselinePromotionRequest(
                    candidate_id=prom_cand_id,
                    scope_id=cand.scope.scope_id,
                    artifact_fingerprint=cand.artifact_fingerprint,
                    approval_fingerprint=approval.approval_fingerprint,
                    registry_parent_fingerprint=registry.registry_fingerprint,
                    requested_by=prom_actor,
                    requested_at=datetime.now(UTC),
                    operation=BaselinePromotionOperation.PROMOTE,
                )
                new_reg, receipt = promote_baseline(registry, req)
                st.session_state["baseline_last_audit"] = receipt.audit
                if receipt.status.value == "active":
                    _set_registry(new_reg)
                    assert receipt.promoted_record is not None
                    st.success(f"Promoted {prom_cand_id} -> {receipt.promoted_record.baseline_id}")
                    st.rerun()
                else:
                    st.error(f"Promotion BLOCKED: {'; '.join(receipt.blocked_reasons)}")

    # Supersede form
    with st.form("baseline_supersede_form"):
        st.markdown("**Supersede active baseline**")
        sup_scope = st.text_input(
            "Supersede scope ID", value="scope-demo-traffic", key="baseline_sup_scope"
        )
        sup_cand = st.text_input(
            "Superseding candidate ID", value="candidate-002", key="baseline_sup_cand"
        )
        sup_actor = st.text_input("Supersede actor", value="operator", key="baseline_sup_actor")
        submitted_sup = st.form_submit_button("Supersede")
    if submitted_sup:
        if sup_cand not in registry.candidates:
            st.error(f"Candidate {sup_cand!r} does not exist — BLOCKED")
            # Fail-closed audit via explicit request with zero fingerprints
            from traffictwin.baseline_registry.models import BaselinePromotionRequest

            req = BaselinePromotionRequest(
                candidate_id=sup_cand,
                scope_id=sup_scope,
                artifact_fingerprint="0" * 64,
                approval_fingerprint="0" * 64,
                registry_parent_fingerprint=registry.registry_fingerprint,
                requested_by=sup_actor,
                requested_at=datetime.now(UTC),
                operation=BaselinePromotionOperation.SUPERSEDE,
            )
            _, receipt = supersede_baseline(registry, req)
            st.session_state["baseline_last_audit"] = receipt.audit
            st.error(f"Supersede BLOCKED: {'; '.join(receipt.blocked_reasons)}")
        else:
            cand = registry.candidates[sup_cand]
            approval = registry.approvals.get(sup_cand)  # type: ignore[assignment]
            if approval is None:
                st.error("No approval exists for candidate — BLOCKED")
                from traffictwin.baseline_registry.models import BaselinePromotionRequest

                req = BaselinePromotionRequest(
                    candidate_id=sup_cand,
                    scope_id=sup_scope,
                    artifact_fingerprint=cand.artifact_fingerprint,
                    approval_fingerprint="0" * 64,
                    registry_parent_fingerprint=registry.registry_fingerprint,
                    requested_by=sup_actor,
                    requested_at=datetime.now(UTC),
                    operation=BaselinePromotionOperation.SUPERSEDE,
                )
                _, receipt = supersede_baseline(registry, req)
                st.session_state["baseline_last_audit"] = receipt.audit
                st.error(f"Supersede BLOCKED: {'; '.join(receipt.blocked_reasons)}")
            else:
                from traffictwin.baseline_registry.models import BaselinePromotionRequest

                req = BaselinePromotionRequest(
                    candidate_id=sup_cand,
                    scope_id=sup_scope,
                    artifact_fingerprint=cand.artifact_fingerprint,
                    approval_fingerprint=approval.approval_fingerprint,
                    registry_parent_fingerprint=registry.registry_fingerprint,
                    requested_by=sup_actor,
                    requested_at=datetime.now(UTC),
                    operation=BaselinePromotionOperation.SUPERSEDE,
                )
                new_reg, receipt = supersede_baseline(registry, req)
                st.session_state["baseline_last_audit"] = receipt.audit
                if receipt.status.value == "active":
                    assert receipt.promoted_record is not None
                    _set_registry(new_reg)
                    st.success(
                        f"Superseded {sup_scope} with {sup_cand} -> {receipt.promoted_record.baseline_id}"  # noqa: E501
                    )
                    st.rerun()
                else:
                    st.error(f"Supersede BLOCKED: {'; '.join(receipt.blocked_reasons)}")

    # Restore form — uses typed restorable selector to avoid typo/missing
    with st.form("baseline_restore_form"):
        st.markdown("**Restore prior baseline as new promotion (rollback via new event)**")
        res_scope = st.text_input(
            "Restore scope ID", value="scope-demo-traffic", key="baseline_res_scope"
        )
        restorable_opts = list_restorable_candidates(registry, res_scope) if res_scope else []
        if restorable_opts:
            res_cand = st.selectbox(
                "Restore candidate ID (only previously superseded)",
                options=restorable_opts,
                key="baseline_res_cand_select",
            )
        else:
            st.caption(  # noqa: E501
                "No restorable candidates in this scope (must have been previously active and superseded)."  # noqa: E501
            )
            res_cand = st.text_input(
                "Restore candidate ID (fallback)", value="", key="baseline_res_cand_fallback"
            )
        res_actor = st.text_input("Restore actor", value="operator", key="baseline_res_actor")
        submitted_res = st.form_submit_button("Restore as new promotion")
    if submitted_res:
        if not res_cand:
            st.error("Restore candidate required — BLOCKED")
        else:
            from traffictwin.baseline_registry.models import BaselinePromotionRequest

            cand_obj = registry.candidates.get(res_cand)
            appr_obj = registry.approvals.get(res_cand)
            if cand_obj is None:
                req = BaselinePromotionRequest(
                    candidate_id=res_cand,
                    scope_id=res_scope,
                    artifact_fingerprint="0" * 64,
                    approval_fingerprint="0" * 64,
                    registry_parent_fingerprint=registry.registry_fingerprint,
                    requested_by=res_actor,
                    requested_at=datetime.now(UTC),
                    operation=BaselinePromotionOperation.RESTORE,
                )
                _, receipt = restore_baseline_as_new_promotion(registry, req)
                st.session_state["baseline_last_audit"] = receipt.audit
                st.error(f"Restore BLOCKED: {'; '.join(receipt.blocked_reasons)}")
            elif appr_obj is None:
                st.error("No approval exists for candidate — BLOCKED")
                req = BaselinePromotionRequest(
                    candidate_id=res_cand,
                    scope_id=res_scope,
                    artifact_fingerprint=cand_obj.artifact_fingerprint,
                    approval_fingerprint="0" * 64,
                    registry_parent_fingerprint=registry.registry_fingerprint,
                    requested_by=res_actor,
                    requested_at=datetime.now(UTC),
                    operation=BaselinePromotionOperation.RESTORE,
                )
                _, receipt = restore_baseline_as_new_promotion(registry, req)
                st.session_state["baseline_last_audit"] = receipt.audit
                st.error(f"Restore BLOCKED: {'; '.join(receipt.blocked_reasons)}")
            else:
                req = BaselinePromotionRequest(
                    candidate_id=res_cand,
                    scope_id=res_scope,
                    artifact_fingerprint=cand_obj.artifact_fingerprint,
                    approval_fingerprint=appr_obj.approval_fingerprint,
                    registry_parent_fingerprint=registry.registry_fingerprint,
                    requested_by=res_actor,
                    requested_at=datetime.now(UTC),
                    operation=BaselinePromotionOperation.RESTORE,
                )
                new_reg, receipt = restore_baseline_as_new_promotion(registry, req)
                st.session_state["baseline_last_audit"] = receipt.audit
                if receipt.status.value == "active":
                    assert receipt.promoted_record is not None
                    _set_registry(new_reg)
                    st.success(  # noqa: E501
                        f"Restored {res_cand} in {res_scope} -> {receipt.promoted_record.baseline_id}"  # noqa: E501
                    )
                    st.rerun()
                else:
                    st.error(f"Restore BLOCKED: {'; '.join(receipt.blocked_reasons)}")

    # ------------------------------------------------------------------
    # Registry timeline
    # ------------------------------------------------------------------
    st.subheader("Registry timeline")
    if registry.ledger:
        tl_rows = []
        for entry in sorted(registry.ledger, key=lambda e: e.entry_index):
            tl_rows.append(
                {
                    "index": entry.entry_index,
                    "event": entry.event_kind.value,
                    "scope": entry.scope_id,
                    "candidate": entry.candidate_id or "—",
                    "baseline": entry.baseline_id or "—",
                    "artifact": fingerprint_summary(entry.artifact_fingerprint)
                    if entry.artifact_fingerprint
                    else "—",
                    "actor": entry.actor or "—",
                    "timestamp": entry.timestamp.isoformat(),
                }
            )
        st.dataframe(
            tl_rows, hide_index=True, width="stretch", column_config=table_column_config(tl_rows)
        )
    else:
        st.caption("No ledger entries. Timeline is empty.")
        st.markdown(":gray-badge[UNAVAILABLE] Empty timeline")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    st.subheader("Export")
    st.caption(  # noqa: E501
        "JSON export is the exact portable registry used by the page; "  # noqa: E501
        "CSV is tabular ledger for audit."  # noqa: E501
    )
    _reg_json = registry_to_json(registry)
    st.download_button(
        "Download Registry JSON",
        data=_reg_json,
        file_name="baseline_registry.json",
        mime="application/json",
        key="baseline_download_json",
    )
    _reg_csv = registry_to_csv(registry)
    st.download_button(
        "Download Ledger CSV",
        data=_reg_csv,
        file_name="baseline_registry_ledger.csv",
        mime="text/csv",
        key="baseline_download_csv",
    )
    _cand_csv = candidates_to_csv(registry)
    st.download_button(
        "Download Candidates CSV",
        data=_cand_csv,
        file_name="baseline_candidates.csv",
        mime="text/csv",
        key="baseline_download_candidates_csv",
    )
    _active_csv = active_baselines_to_csv(registry)
    st.download_button(
        "Download Active Baselines CSV",
        data=_active_csv,
        file_name="baseline_active.csv",
        mime="text/csv",
        key="baseline_download_active_csv",
    )

    # Fingerprint display
    st.subheader("Registry identity")
    st.caption(f"Registry fingerprint: `{fingerprint_summary(registry.registry_fingerprint)}`")
    st.code(f"Full registry fingerprint: {registry.registry_fingerprint}", language=None)
    with st.expander("Advanced: canonical JSON (truncated)"):
        canon = registry.canonical_json()
        st.code(canon[:3000] + ("… truncated" if len(canon) > 3000 else ""), language="json")

    # Withdraw candidate expander
    with st.expander("Withdraw candidate (append-only)"):
        w_cand = st.text_input("Candidate ID to withdraw", value="", key="baseline_withdraw_cand")
        w_actor = st.text_input("Withdraw actor", value="operator", key="baseline_withdraw_actor")
        if st.button("Withdraw", key="baseline_withdraw_button"):
            if not w_cand:
                st.error("Candidate ID required")
            else:
                try:
                    # Determine if candidate is currently active before withdrawal
                    was_active = False
                    was_scope: str | None = None
                    for s_id, rec in registry.active_baselines.items():
                        if rec.candidate_id == w_cand:
                            was_active = True
                            was_scope = s_id
                            break
                    # Also check candidate exists to get scope if not active
                    if not was_active and w_cand in registry.candidates:
                        was_scope = registry.candidates[w_cand].scope.scope_id
                    new_reg = withdraw_candidate(registry, candidate_id=w_cand, actor=w_actor)
                    _set_registry(new_reg)
                    if was_active and was_scope is not None:
                        # Active withdrawn remains active — warn operator, survives rerun
                        msg = (
                            f"Candidate {w_cand} was withdrawn, but it remains the active baseline for scope {was_scope}. "  # noqa: E501
                            "Withdrawal does not deactivate an active baseline; it remains active "  # noqa: E501
                            "until another valid candidate supersedes it."  # noqa: E501
                        )
                        st.session_state["baseline_withdraw_flash"] = msg
                        # Also store for immediate test inspection (before rerun)
                        st.warning(msg)
                    else:
                        st.session_state["baseline_withdraw_flash"] = (
                            f"Candidate {w_cand} was withdrawn."
                        )
                        st.success(f"Candidate {w_cand} was withdrawn.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Withdraw failed: {exc}")
