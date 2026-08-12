"""Study Accrual & Deviation Monitor — thin UI over deterministic service."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import streamlit as st
import yaml

from traffictwin.metrics.catalogue import METRIC_VERSION
from traffictwin.preregistration.models import (
    AnalysisMethod,
    ArtifactAdmission,
    CohortRule,
    DecisionRule,
    EstimandDefinition,
    EvidenceAttachment,
    EvidenceMode,
    ExclusionRule,
    MissingnessPolicy,
    MultiplicityPolicy,
    OutcomeDefinition,
    ReplicationUnit,
    StoppingRule,
    StudyPlan,
    StudyPlanStatus,
    StudyQuestion,
)
from traffictwin.preregistration.service import attach_evidence, freeze_plan
from traffictwin.study_accrual.exports import (
    export_cells_csv,
    export_deviations_csv,
    export_report_json,
)
from traffictwin.study_accrual.models import (
    AccrualReport,
    AccrualReviewDecision,
    AccrualReviewHandoff,
    AccrualReviewState,
)
from traffictwin.study_accrual.service import build_accrual_report
from traffictwin.ui.state import UiConfig


def _default_demo_plan() -> StudyPlan:
    metric = "task.completion.rate"
    plan = StudyPlan(
        plan_id="accrual-demo-001",
        study_question=StudyQuestion(
            text="Does the variation change task completion rate under predeclared replication?",
            hypothesis="Variation improves completion rate versus baseline.",
            background="Frozen to monitor accrual without interim decisions.",
        ),
        evidence_mode=EvidenceMode.SYNTHETIC_EVIDENCE,
        primary_outcomes=[
            OutcomeDefinition(
                outcome_id="primary-001",
                metric_key=metric,
                metric_version=METRIC_VERSION,
                unit="ratio",
                denominator="generated_tasks",
                description="Primary completion rate in ratio unit.",
                higher_is_better=True,
            )
        ],
        secondary_outcomes=[],
        estimand=EstimandDefinition(
            estimand_id="estimand-001",
            description="Mean paired difference variation minus baseline over common replicates.",
            population="common_random_seed replicates",
            effect_measure="mean_difference",
        ),
        replication_unit=ReplicationUnit.RANDOM_SEED,
        replication_ids=[1, 2, 3],
        planned_arms=["baseline", "variation"],
        seeds=["seed-baseline", "seed-variation"],
        policies=["policy-a", "policy-b"],
        metrics=[metric],
        cohort_rules=[
            CohortRule(
                rule_id="cohort-001",
                description="Include all valid generated tasks with latency observed.",
            )
        ],
        exclusion_rules=[
            ExclusionRule(
                rule_id="exclude-001", description="Exclude runs with invalid source data."
            )
        ],
        missingness_policy=MissingnessPolicy.COMPLETE_CASE,
        analysis_method=AnalysisMethod.PAIRED_MEAN_DIFFERENCE,
        multiplicity_policy=MultiplicityPolicy.NONE_SINGLE_TEST,
        stopping_rule=StoppingRule(
            description="Stop when all planned replicates have compatible admitted evidence.",
            max_replicates=6,
            interim_looks=2,
        ),
        decision_rule=DecisionRule(
            rule_type="two_sided_test",
            alpha=0.05,
            interpretation="Two-sided test at alpha 0.05 for primary outcome.",
            comparison="two_sided",
        ),
        limitations="Demonstration limitations with sufficient length for governance validation.",
        planned_run_cells=[],
    )
    frozen = freeze_plan(plan, clock=lambda: datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC))
    return frozen


def hashlib_sha(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _demo_attachments(plan: StudyPlan) -> list[EvidenceAttachment]:
    """Return deterministic admitted attachments for demo: all cells complete."""
    atts: list[EvidenceAttachment] = []
    base_time = datetime(2026, 1, 11, 10, 0, 0, tzinfo=UTC)
    for cell in sorted(plan.planned_run_cells, key=lambda c: c.cell_id):
        att = EvidenceAttachment(
            artifact_fingerprint=hashlib_sha(f"demo-{cell.cell_id}"),
            cell_id=cell.cell_id,
            artifact_type="metric_collection",
            observed_metric_key=cell.metric_key,
            observed_metric_version=cell.metric_version,
            observed_unit="ratio",
            is_admitted=True,
            admission_label=ArtifactAdmission.ADMITTED,
            incompatibility_reason=None,
            attached_at=base_time,
        )
        atts.append(att)
    return atts


def _load_plan_from_upload(content: str) -> StudyPlan | None:
    try:
        data = json.loads(content)
        return StudyPlan.model_validate(data)
    except Exception:  # noqa: S110
        pass
    try:
        data_yaml = yaml.safe_load(content)
        if isinstance(data_yaml, dict):
            return StudyPlan.model_validate(data_yaml)
    except Exception:  # noqa: S110
        pass
    return None


def _parse_review_handoff_json(content: str) -> AccrualReviewHandoff | None:
    try:
        data = json.loads(content)
        return AccrualReviewHandoff.model_validate(data)
    except Exception as exc:
        st.error(f"Review handoff JSON invalid (fail-closed): {exc}")
        return None


def _render_evidence_notice() -> None:
    st.info(
        "Evidence & authority boundary: This monitor compares collected and reviewed evidence "
        "against the frozen preregistered plan. It does not reinterpret synthetic evidence as "
        "observed, does not auto-admit evidence, does not call freezing approval, and never "
        "makes an interim scientific decision. Manchester evidence is shown only when genuine "
        "admitted Manchester evidence is supplied; no Manchester claim is made by default."
    )


def render(config: UiConfig | None = None) -> None:  # noqa: ARG001
    """Render the Study Accrual Monitor page."""
    _ = config
    st.title("Study Accrual Monitor")
    st.caption(
        "Deterministic monitor showing how collected and reviewed evidence compares with the "
        "frozen preregistered plan over time. This is monitoring and deviation accounting; "
        "it does not change the plan or make interim decisions."
    )
    _render_evidence_notice()

    st.subheader("1 · Plan source")
    st.caption(
        "Provide a frozen StudyPlan JSON/YAML or use the synthetic demo. "
        "Only a frozen plan has a deterministic accrual identity; fingerprint is verified."
    )

    demo_plan = _default_demo_plan()
    uploaded = st.file_uploader(
        "Upload frozen StudyPlan (JSON or YAML)",
        type=["json", "yaml", "yml"],
        key="study_accrual_plan_upload",
    )
    pasted = st.text_area(
        "Or paste StudyPlan JSON/YAML",
        value="",
        key="study_accrual_plan_paste",
        height=120,
    )

    plan: StudyPlan | None = None
    if uploaded is not None:
        try:
            content = uploaded.getvalue().decode("utf-8")
            plan = _load_plan_from_upload(content)
            if plan is None:
                st.error("Upload could not be parsed as a StudyPlan (fail-closed).")
            else:
                st.success(f"Loaded plan {plan.plan_id} v{plan.version} status {plan.status.value}")
        except Exception as exc:
            st.error(f"Failed to read uploaded plan: {exc}")
    elif pasted.strip():
        plan = _load_plan_from_upload(pasted.strip())
        if plan is None:
            st.error("Paste could not be parsed as a StudyPlan (fail-closed).")
        else:
            st.success(
                f"Loaded pasted plan {plan.plan_id} v{plan.version} status {plan.status.value}"
            )

    if plan is None:
        st.caption("Using synthetic demo frozen plan (no Manchester claim).")
        plan = demo_plan

    st.subheader("2 · Evidence attachments")
    st.caption(
        "Evidence attachments are read from the frozen plan's evidence_attachments. "
        "Optional typed review handoff marks cells as rejected/withdrawn; review decisions drive latest_decision and create accrual blockers."  # noqa: E501
    )

    use_demo_evidence = st.checkbox(
        "Use synthetic demo admitted evidence (for illustration only)",
        value=(len(plan.evidence_attachments) == 0 and plan.status == StudyPlanStatus.FROZEN),
        key="study_accrual_use_demo_evidence",
    )

    effective_plan = plan
    if (
        use_demo_evidence
        and plan.status == StudyPlanStatus.FROZEN
        and not plan.evidence_attachments
    ):
        demo_atts = _demo_attachments(plan)
        try:
            effective_plan = attach_evidence(
                plan, demo_atts, clock=lambda: datetime(2026, 1, 11, 10, 0, 0, tzinfo=UTC)
            )
        except Exception:
            effective_plan = plan

    st.caption("Typed review handoff (JSON) — strict schema 1.0, no alias soup.")
    st.caption(
        'Example: {"schema_version":"1.0","decisions":[{"cell_id":"cell-0001","state":"REJECTED","reason":"manual review rejects"}],"interim_looks_used":1}'  # noqa: E501
    )
    generic_file = st.file_uploader(
        "Upload typed review handoff JSON (optional)",
        type=["json"],
        key="study_accrual_generic_review",
    )
    generic_paste = st.text_area(
        "Or paste review handoff JSON",
        value="",
        key="study_accrual_generic_paste",
        height=80,
    )
    handoff: AccrualReviewHandoff | None = None
    handoff_parse_error = False
    if generic_file is not None:
        try:
            content = generic_file.getvalue().decode("utf-8")
            handoff = _parse_review_handoff_json(content)
            if handoff is not None:
                st.success("Review handoff JSON parsed and validated.")
            else:
                handoff_parse_error = True
        except Exception as exc:
            st.error(f"Failed to read handoff JSON: {exc}")
            handoff_parse_error = True
    elif generic_paste.strip():
        handoff = _parse_review_handoff_json(generic_paste.strip())
        if handoff is not None:
            st.success("Review handoff JSON parsed and validated.")
        else:
            handoff_parse_error = True

    if handoff_parse_error and handoff is None:
        st.warning("Review handoff invalid — accrual will be refused if applied.")

    interim_input = st.number_input(
        "Interim looks used (explicit, optional — converted to typed handoff)",
        min_value=0,
        max_value=20,
        value=0,
        step=1,
        key="study_accrual_interim_looks",
    )
    rejected_input = st.text_input(
        "Rejected cell_ids (comma-separated, optional — converted to typed handoff)",
        value="",
        key="study_accrual_rejected",
        placeholder="cell-0001, cell-0002",
    )
    withdrawn_input = st.text_input(
        "Withdrawn cell_ids (comma-separated, optional — converted to typed handoff)",
        value="",
        key="study_accrual_withdrawn",
        placeholder="cell-0003",
    )

    # Convert manual controls into SAME typed handoff before service invocation (one service path)
    manual_decisions: list[AccrualReviewDecision] = []
    manual_rejected = {s.strip() for s in rejected_input.split(",") if s.strip()}
    manual_withdrawn = {s.strip() for s in withdrawn_input.split(",") if s.strip()}
    # Validate manual contradictions before building handoff
    overlap = manual_rejected & manual_withdrawn
    if overlap:
        st.error(
            f"Manual handoff contradiction: cells both rejected and withdrawn: {sorted(overlap)} (fail-closed)"  # noqa: E501
        )
        manual_handoff_error = True
    else:
        manual_handoff_error = False
        for cid in sorted(manual_rejected):
            try:
                manual_decisions.append(
                    AccrualReviewDecision(
                        cell_id=cid, state=AccrualReviewState.REJECTED, reason="manual rejected"
                    )
                )
            except Exception as exc:
                st.error(f"Invalid rejected cell {cid!r}: {exc}")
                manual_handoff_error = True
        for cid in sorted(manual_withdrawn):
            try:
                manual_decisions.append(
                    AccrualReviewDecision(
                        cell_id=cid, state=AccrualReviewState.WITHDRAWN, reason="manual withdrawn"
                    )
                )
            except Exception as exc:
                st.error(f"Invalid withdrawn cell {cid!r}: {exc}")
                manual_handoff_error = True

    # Merge manual + handoff JSON into one typed handoff (fail-closed on duplicates)
    combined_handoff: AccrualReviewHandoff | None = None
    if handoff is not None or manual_decisions or interim_input > 0:
        # If both handoff and manual exist, merge but check duplicates
        all_decisions: list[AccrualReviewDecision] = []
        if handoff is not None:
            all_decisions.extend(handoff.decisions)
        all_decisions.extend(manual_decisions)
        # Interim: prefer manual >0 else handoff
        interim_val: int | None = None
        if interim_input > 0:
            interim_val = int(interim_input)
        elif handoff and handoff.interim_looks_used is not None:
            interim_val = handoff.interim_looks_used
        # Validate duplicate cell across combined
        seen: dict[str, str] = {}
        duplicate_found = False
        for dec in all_decisions:
            if dec.cell_id in seen:
                st.error(
                    f"Duplicate review decision for cell {dec.cell_id!r} across handoff + manual (fail-closed)"  # noqa: E501
                )
                duplicate_found = True
            seen[dec.cell_id] = dec.state.value
        if duplicate_found or manual_handoff_error or handoff_parse_error:
            st.error("Review handoff invalid — accrual will be refused if submitted.")
            combined_handoff = None
            # Create a deliberately invalid handoff to trigger service refuse? Instead show error and not call service  # noqa: E501
            # We'll create a report with unavailable after service call fails closed; for now set to None and let service handle manual error via blocker?  # noqa: E501
            # To demonstrate fail-closed, we will attempt to build an invalid handoff and catch.
            try:
                combined_handoff = AccrualReviewHandoff(
                    schema_version="1.0",
                    decisions=all_decisions,
                    interim_looks_used=interim_val,
                )
            except Exception as exc:
                st.error(f"Combined handoff invalid: {exc}")
                combined_handoff = None
        else:
            try:
                combined_handoff = AccrualReviewHandoff(
                    schema_version="1.0",
                    decisions=sorted(all_decisions, key=lambda d: d.cell_id),
                    interim_looks_used=interim_val,
                )
            except Exception as exc:
                st.error(f"Invalid review handoff (fail-closed): {exc}")
                combined_handoff = None

    # Build report via deterministic service — no UI-side recomputation
    try:
        report: AccrualReport = build_accrual_report(
            effective_plan,
            review_handoff=combined_handoff,
        )
    except Exception as exc:
        st.error(f"Accrual report failed (fail-closed): {exc}")
        return

    st.subheader("3 · Overall accrual")
    snap = report.snapshot
    if report.is_unavailable:
        st.warning(f"Accrual unavailable: {report.unavailable_reason}")
        if report.warnings:
            for w in report.warnings:
                st.caption(f"[{w.severity}] {w.code}: {w.message}")
    else:
        pct = 0.0
        if snap.expected_count > 0:
            pct = snap.complete_count / snap.expected_count
        st.progress(
            min(1.0, max(0.0, pct)),
            text=f"Accrual {snap.complete_count}/{snap.expected_count} complete",
        )
        cols = st.columns(4)
        cols[0].metric("Expected", snap.expected_count)
        cols[1].metric("Attached", snap.attached_count)
        cols[2].metric("Admitted", snap.admitted_count)
        cols[3].metric("Remaining", snap.remaining_count)
        cols2 = st.columns(4)
        cols2[0].metric("Rejected", snap.rejected_count)
        cols2[1].metric("Incompatible", snap.incompatible_count)
        cols2[2].metric("Extra", snap.extra_count)
        cols2[3].metric("Duplicate", snap.duplicate_count)
        st.caption(f"Post-evidence amendments: {snap.post_evidence_amendment_count}")
        st.caption(
            f"Replicates planned/observed: {snap.planned_replicate_count}/{snap.observed_replicate_count} (max {report.stopping_progress.max_replicates or '—'})"  # noqa: E501
        )
        st.caption(
            f"Plan fingerprint: `{snap.plan_fingerprint[:12] + '…' if snap.plan_fingerprint else 'Unavailable'}`"  # noqa: E501
        )
        st.caption(
            f"Report fingerprint: `{report.fingerprint[:12] + '…' if report.fingerprint else 'Unavailable'}`"  # noqa: E501
        )

    st.subheader("4 · Progress counters")
    st.caption(
        "Counts reconcile: expected = planned_missing + attached_unadmitted + complete + incompatible + rejected + withdrawn + duplicate; remaining = expected - complete; attached = expected - planned_missing."  # noqa: E501
    )
    counter_data = [
        {"measure": "expected", "count": snap.expected_count},
        {"measure": "attached", "count": snap.attached_count},
        {"measure": "admitted", "count": snap.admitted_count},
        {"measure": "complete", "count": snap.complete_count},
        {"measure": "remaining", "count": snap.remaining_count},
        {"measure": "extra", "count": snap.extra_count},
        {"measure": "rejected", "count": snap.rejected_count},
        {"measure": "incompatible", "count": snap.incompatible_count},
        {"measure": "withdrawn", "count": snap.withdrawn_count},
        {"measure": "duplicate", "count": snap.duplicate_count},
        {"measure": "planned_missing", "count": snap.planned_missing_count},
        {"measure": "attached_unadmitted", "count": snap.attached_unadmitted_count},
        {"measure": "planned_replicates", "count": snap.planned_replicate_count},
        {"measure": "observed_replicates", "count": snap.observed_replicate_count},
    ]
    st.dataframe(counter_data, width="stretch", key="study_accrual_counters")

    st.subheader("5 · Planned-versus-current matrix")
    if not report.cells:
        st.info(
            "No planned cells to display. Freeze a plan with a run matrix to enable monitoring."
        )
    else:
        rows: list[dict[str, object]] = []
        for cell in sorted(report.cells, key=lambda c: c.cell_id):
            rows.append(
                {
                    "cell_id": cell.cell_id,
                    "status": cell.status.value,
                    "attachment": cell.attachment_state,
                    "admission": cell.admission_state,
                    "compatibility": cell.compatibility,
                    "first_observed": cell.first_observed_time or "",
                    "latest_decision": cell.latest_decision or "",
                    "deviation": cell.deviation_reason or "",
                }
            )
        st.dataframe(rows, width="stretch", key="study_accrual_matrix")
        st.caption(
            "Each row shows expected identity, attachment state, admission state, compatibility, first observed time, latest decision (review-driven), and deviation reason."  # noqa: E501
        )

    st.subheader("6 · Deviation timeline")
    if not report.timeline and not report.deviations:
        st.info("No deviations recorded — accrual is clean (or no evidence yet).")
    else:
        if report.deviations:
            st.markdown("**Deviations (typed, only when explicit record exists)**")
            dev_rows = [
                {"code": d.code.value, "cell_id": d.cell_id or "", "message": d.message}
                for d in report.deviations
            ]
            st.dataframe(dev_rows, width="stretch", key="study_accrual_deviations")
        if report.timeline:
            st.markdown("**Timeline (deterministic, sorted by timestamp)**")
            tl_rows = [
                {
                    "timestamp": t.timestamp or "",
                    "event": t.event_type,
                    "cell_id": t.cell_id or "",
                    "message": t.message,
                }
                for t in report.timeline
            ]
            st.dataframe(tl_rows, width="stretch", key="study_accrual_timeline")

    st.subheader("7 · Stopping progress")
    sp = report.stopping_progress
    scol1, scol2, scol3 = st.columns(3)
    scol1.metric("Planned replicates", sp.planned_replicate_count)
    scol2.metric("Observed replicates", sp.observed_replicate_count)
    scol3.metric("Max replicates", sp.max_replicates if sp.max_replicates is not None else "—")
    scol1b, scol2b, scol3b = st.columns(3)
    scol1b.metric("Interim allowed", sp.interim_looks_allowed)
    scol2b.metric("Interim used", sp.interim_looks_used)
    scol3b.metric("Overrun", f"{sp.is_overrun} (by {sp.overrun_by})")
    st.caption(
        f"Accrual: {sp.expected_count} cells, {sp.attached_count} attached, {sp.admitted_count} admitted — status {sp.status}"  # noqa: E501
    )
    st.caption(
        "Stopping progress compares distinct replication_id values, not cell counts. Extra evidence does not increase replicate count."  # noqa: E501
    )

    st.subheader("8 · Amendment history")
    if not report.amendment_history:
        st.info("No amendments in lineage.")
    else:
        hist_rows: list[dict[str, object]] = []
        for rev in sorted(report.amendment_history, key=lambda r: r.get("version", 0)):
            hist_rows.append(
                {
                    "version": rev.get("version"),
                    "amendment_reason": str(rev.get("amendment_reason", ""))[:80],
                    "is_post_evidence": rev.get("is_post_evidence"),
                    "amendment_label": rev.get("amendment_label"),
                }
            )
        st.dataframe(hist_rows, width="stretch", key="study_accrual_amendments")
        if snap.post_evidence_amendment_count > 0:
            st.warning(
                f"{snap.post_evidence_amendment_count} post-evidence amendments require review; study governance blocked while evidence accrual may be complete."  # noqa: E501
            )

    st.subheader("9 · Accrual blockers")
    if not report.blockers:
        st.success(
            "No accrual blockers — evidence accrual complete, but stored preregistration gate status is shown separately as recomputed context."  # noqa: E501
        )
    else:
        for blk in report.blockers:
            st.warning(blk)
    if report.warnings:
        with st.expander("Advanced: warnings and gate context"):
            for w in report.warnings:
                st.caption(f"[{w.severity}] {w.code}: {w.message}")
            st.caption(
                "Stored preregistration gate status is recomputed via the authoritative gate implementation and shown as context; it does not remove current accrual blockers."  # noqa: E501
            )

    st.subheader("10 · Deterministic exports")
    st.caption(
        "Portable exports preserve semantic evidence/amendment timestamps; only runtime generation clock is excluded. Fingerprints are stable SHA-256 over sorted canonical JSON (allow_nan=False)."  # noqa: E501
    )
    json_export = export_report_json(report)
    cells_csv = export_cells_csv(report)
    dev_csv = export_deviations_csv(report)
    c1, c2, c3 = st.columns(3)
    c1.download_button(
        "Download report JSON",
        data=json_export,
        file_name=f"{snap.plan_id}-accrual-v{snap.plan_version}.json",
        mime="application/json",
        width="stretch",
        key="study_accrual_dl_json",
    )
    c2.download_button(
        "Download matrix CSV",
        data=cells_csv,
        file_name=f"{snap.plan_id}-accrual-matrix.csv",
        mime="text/csv",
        width="stretch",
        key="study_accrual_dl_matrix",
    )
    c3.download_button(
        "Download deviations CSV",
        data=dev_csv,
        file_name=f"{snap.plan_id}-accrual-deviations.csv",
        mime="text/csv",
        width="stretch",
        key="study_accrual_dl_deviations",
    )
    st.caption(f"Report fingerprint: `{report.fingerprint}`")
    with st.expander("Advanced: governance boundaries"):
        st.markdown(
            "- Monitoring only — does not amend the plan or admit evidence automatically.\n"
            "- Unadmitted evidence stays unadmitted; is_admitted=True is required.\n"
            "- Synthetic evidence is never relabelled as observed; Manchester claim requires genuine admitted Manchester evidence.\n"  # noqa: E501
            "- No post-hoc metric or unit changes are inferred; deviations are explicit.\n"
            "- Post-evidence amendment is a governance blocker, not a per-cell evidence rewrite; compatible admitted cells remain COMPLETE.\n"  # noqa: E501
            "- No optimal policy is claimed without a declared decision contract.\n"
            "- No shell is invoked from user-supplied input; bounded inputs are enforced; review handoff is strict typed.\n"  # noqa: E501
            "- CSV exports are sanitized for spreadsheet formula injection via repository helper.\n"
        )
    st.caption(
        "No automatic plan amendment — amendments are explicit, versioned, and preserve parent fingerprint immutably."  # noqa: E501
    )
