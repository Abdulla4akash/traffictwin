"""Study Accrual & Deviation Monitor — thin UI over deterministic service."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import streamlit as st

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
from traffictwin.study_accrual.models import AccrualReport
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
            description="Stop when all planned cells have compatible admitted evidence or after interim looks.",  # noqa: E501
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
    # Freeze to obtain deterministic matrix and fingerprint
    frozen = freeze_plan(plan, clock=lambda: datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC))
    return frozen


def _demo_attachments(plan: StudyPlan) -> list[EvidenceAttachment]:
    """Return deterministic admitted attachments for demo: all cells complete."""
    atts: list[EvidenceAttachment] = []
    base_time = datetime(2026, 1, 11, 10, 0, 0, tzinfo=UTC)
    for idx, cell in enumerate(sorted(plan.planned_run_cells, key=lambda c: c.cell_id)):  # noqa: B007
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


def hashlib_sha(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_plan_from_upload(content: str) -> StudyPlan | None:
    import json

    import yaml

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
    _ = config  # config reserved for future registry integration
    st.title("Study Accrual Monitor")
    st.caption(
        "Deterministic monitor showing how collected and reviewed evidence compares with the "
        "frozen preregistered plan over time. This is monitoring and deviation accounting; "
        "it does not change the plan or make interim decisions."
    )
    _render_evidence_notice()

    # --- Plan source ---
    st.subheader("1 · Plan source")
    st.caption(
        "Provide a frozen StudyPlan JSON/YAML or use the synthetic demo. "
        "Only a frozen plan has a deterministic accrual identity."
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

    # --- Evidence inputs ---
    st.subheader("2 · Evidence attachments")
    st.caption(
        "Evidence attachments are read from the frozen plan's evidence_attachments. "
        "Optional: mark specific cells as rejected/withdrawn via generic review JSON, "
        "and declare interim looks used. No evidence is auto-admitted."
    )

    # If plan has no evidence, offer demo attachments
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
        # Attach demo evidence deterministically without mutating original concept (service builds report without mutation)  # noqa: E501
        demo_atts = _demo_attachments(plan)
        try:
            effective_plan = attach_evidence(
                plan, demo_atts, clock=lambda: datetime(2026, 1, 11, 10, 0, 0, tzinfo=UTC)
            )
        except Exception:
            effective_plan = plan

    # Generic review JSON (optional)
    st.caption(
        "Optional generic review/admission export (JSON) with rejected/withdrawn cells and interim looks."  # noqa: E501
    )
    generic_payload: dict[str, object] | None = None
    generic_file = st.file_uploader(
        "Upload generic review JSON (optional)",
        type=["json"],
        key="study_accrual_generic_review",
    )
    generic_paste = st.text_area(
        "Or paste generic review JSON",
        value="",
        key="study_accrual_generic_paste",
        height=80,
    )
    generic_json_str: str | None = None
    if generic_file is not None:
        try:
            generic_json_str = generic_file.getvalue().decode("utf-8")
        except Exception as exc:
            st.error(f"Failed to read generic JSON: {exc}")
    elif generic_paste.strip():
        generic_json_str = generic_paste.strip()
    if generic_json_str:
        try:
            payload = json.loads(generic_json_str)
            if isinstance(payload, dict):
                generic_payload = payload  # noqa: S110
                st.success("Generic review JSON parsed.")
            else:
                st.error("Generic JSON must be an object (fail-closed).")
                generic_payload = None
        except Exception as exc:
            st.error(f"Invalid generic JSON: {exc}")
            generic_payload = None

    # Interim looks override (if not in generic)
    interim_looks_override = st.number_input(
        "Interim looks used (explicit, optional)",
        min_value=0,
        max_value=20,
        value=0,
        step=1,
        key="study_accrual_interim_looks",
    )

    # Rejected/withdrawn manual lists
    rejected_input = st.text_input(
        "Rejected cell_ids (comma-separated, optional)",
        value="",
        key="study_accrual_rejected",
        placeholder="cell-0001, cell-0002",
    )
    withdrawn_input = st.text_input(
        "Withdrawn cell_ids (comma-separated, optional)",
        value="",
        key="study_accrual_withdrawn",
        placeholder="cell-0003",
    )
    rejected_ids = {s.strip() for s in rejected_input.split(",") if s.strip()}
    withdrawn_ids = {s.strip() for s in withdrawn_input.split(",") if s.strip()}

    # Resolve interim looks: explicit input takes precedence if >0, else generic
    interim_for_service: int | None = None
    if interim_looks_override > 0:
        interim_for_service = int(interim_looks_override)
    elif generic_payload and isinstance(generic_payload.get("interim_looks_used"), int):
        interim_for_service = int(generic_payload.get("interim_looks_used", 0))  # type: ignore[call-overload]
    elif generic_payload and isinstance(generic_payload.get("interim_looks"), int):
        interim_for_service = int(generic_payload.get("interim_looks", 0))  # type: ignore[call-overload]

    # Build report via deterministic service — no UI-side recomputation
    try:
        report: AccrualReport = build_accrual_report(
            effective_plan,
            rejected_cell_ids=rejected_ids,
            withdrawn_cell_ids=withdrawn_ids,
            interim_looks_used=interim_for_service,
            generic_review_payload=generic_payload,
        )
    except Exception as exc:
        st.error(f"Accrual report failed (fail-closed): {exc}")
        return

    # --- Overall accrual banner ---
    st.subheader("3 · Overall accrual")
    snap = report.snapshot
    if report.is_unavailable:
        st.warning(f"Accrual unavailable: {report.unavailable_reason}")
    else:
        # Banner with progress bar
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
        cols2[3].metric("Post-evidence amendments", snap.post_evidence_amendment_count)
        st.caption(
            f"Plan fingerprint: `{snap.plan_fingerprint[:12] + '…' if snap.plan_fingerprint else 'Unavailable'}`"  # noqa: E501
        )
        st.caption(
            f"Report fingerprint: `{report.fingerprint[:12] + '…' if report.fingerprint else 'Unavailable'}`"  # noqa: E501
        )

    # --- Progress counters (detailed) ---
    st.subheader("4 · Progress counters")
    # Show counts reconcile note
    st.caption(
        "Counts reconcile: expected = planned_missing + attached_unadmitted + attached_admitted + complete + incompatible + rejected + withdrawn; remaining = expected - complete; attached = expected - planned_missing."  # noqa: E501
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
        {"measure": "planned_missing", "count": snap.planned_missing_count},
        {"measure": "attached_unadmitted", "count": snap.attached_unadmitted_count},
        {"measure": "attached_admitted", "count": snap.attached_admitted_count},
    ]
    st.dataframe(counter_data, width="stretch", key="study_accrual_counters")

    # --- Planned versus current matrix ---
    st.subheader("5 · Planned-versus-current matrix")
    if not report.cells:
        st.info(
            "No planned cells to display. Freeze a plan with a run matrix to enable monitoring."
        )
    else:
        # Build display rows — thin rendering of typed service output, no recomputation
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
            "Each row shows expected identity, attachment state, admission state, compatibility, first observed time, latest decision, and deviation reason (if any)."  # noqa: E501
        )

    # --- Deviation timeline ---
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

    # --- Stopping progress ---
    st.subheader("7 · Stopping progress")
    sp = report.stopping_progress
    scol1, scol2, scol3 = st.columns(3)
    scol1.metric("Expected", sp.expected_count)
    scol2.metric("Attached", sp.attached_count)
    scol3.metric("Admitted", sp.admitted_count)
    scol1b, scol2b, scol3b = st.columns(3)
    scol1b.metric("Interim looks allowed", sp.interim_looks_allowed)
    scol2b.metric("Interim looks used", sp.interim_looks_used)
    scol3b.metric("Max replicates", sp.max_replicates if sp.max_replicates is not None else "—")
    st.caption(
        f"Status: {sp.status} — remaining {sp.remaining} — overrun: {sp.is_overrun} (by {sp.overrun_by})"  # noqa: E501
    )

    # --- Amendment history ---
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
                f"{snap.post_evidence_amendment_count} post-evidence amendments require review; plan was amended after evidence collection."  # noqa: E501
            )

    # --- Blockers ---
    st.subheader("9 · Blockers")
    if not report.blockers:
        st.success(
            "No blockers — accrual does not block a gate on its own (gate evaluation remains separate)."  # noqa: E501
        )
    else:
        for blk in report.blockers:
            st.warning(blk)
    if report.warnings:
        with st.expander("Advanced: warnings"):
            for w in report.warnings:
                st.caption(f"[{w.severity}] {w.code}: {w.message}")

    # --- Deterministic exports ---
    st.subheader("10 · Deterministic exports")
    st.caption(
        "Portable exports exclude local paths and wall-clock; fingerprints are stable SHA-256 over sorted canonical JSON."  # noqa: E501
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
            "- No optimal policy is claimed without a declared decision contract.\n"
            "- No shell is invoked from user-supplied input; bounded inputs are enforced.\n"
        )
    st.caption(
        "No automatic plan amendment — amendments are explicit, versioned, and preserve parent fingerprint immutably."  # noqa: E501
    )
