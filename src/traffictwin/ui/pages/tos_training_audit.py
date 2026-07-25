"""TOS training-history, reproducibility-audit, and export page."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    TosPackageView,
    tos_audit_for_ui,
    tos_readiness_for_ui,
    tos_report_exports_for_ui,
    tos_supervisor_pack_for_ui,
    tos_training_run_for_ui,
    tos_training_runs_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tos_context import active_tos_package


def render(config: UiConfig) -> None:
    """Render source training curves, audit checks, and deliberate exports."""

    render_page_header(UiPage.TOS_TRAINING)
    badge_row(["IMPORTED SIMULATION", "SOURCE TRAINING RECORDS", "READ ONLY"])
    st.info(
        "Training curves describe the source training distribution. They are not Manchester "
        "evaluation results, and wall-clock values must not be pooled across machines."
    )
    package = active_tos_package(config)
    if package is None:
        return
    _render_training(package)
    _render_audit(package)
    _render_readiness(package)
    _render_exports(package)


def _render_training(package: TosPackageView) -> None:
    st.subheader("Training history explorer")
    summaries = tos_training_runs_for_ui(package)
    if isinstance(summaries, ServiceError):
        st.error(summaries.message)
        return
    if not summaries:
        st.info("No training-history CSV files are available.")
        return
    filters = st.columns(2)
    policy = filters[0].selectbox(
        "Policy family", ["All", *sorted({item.policy_label for item in summaries})]
    )
    filtered = [item for item in summaries if policy == "All" or item.policy_label == policy]
    training_id = filters[1].selectbox("Training run", [item.training_id for item in filtered])
    run = tos_training_run_for_ui(package, training_id)
    if isinstance(run, ServiceError):
        st.error(run.message)
        return
    columns = st.columns(4)
    columns[0].metric("Source points", run.summary.point_count)
    columns[1].metric("Measured points", run.summary.measured_point_count)
    columns[2].metric("Warm-up unavailable", run.summary.warmup_unavailable_count)
    columns[3].metric("Final environment step", f"{run.summary.final_env_step:,}")
    completion = go.Figure()
    for field, label in (
        ("mean_completion", "Overall"),
        ("type_1_completion", "T1"),
        ("type_2_completion", "T2"),
        ("type_3_completion", "T3"),
    ):
        selected = [point for point in run.points if getattr(point, field) is not None]
        completion.add_trace(
            go.Scatter(
                x=[point.env_step for point in selected],
                y=[getattr(point, field) for point in selected],
                mode="lines",
                name=label,
            )
        )
    completion.update_layout(
        xaxis_title="Environment step",
        yaxis_title="Training-distribution deadline success (fraction)",
        height=380,
    )
    st.plotly_chart(completion, width="stretch")
    actions = go.Figure()
    for field, label in (("p_local", "Local"), ("p_v2i", "V2I"), ("p_v2v", "V2V")):
        selected = [point for point in run.points if getattr(point, field) is not None]
        actions.add_trace(
            go.Scatter(
                x=[point.env_step for point in selected],
                y=[getattr(point, field) for point in selected],
                mode="lines",
                name=label,
            )
        )
    actions.update_layout(
        xaxis_title="Environment step",
        yaxis_title="Decision share (fraction)",
        height=340,
    )
    st.plotly_chart(actions, width="stretch")
    if run.greedy_evaluation is not None:
        with st.expander("Final greedy evaluation on the training distribution"):
            st.json(run.greedy_evaluation.model_dump(mode="json"))
    for warning in run.summary.warnings:
        st.caption(warning)


def _render_audit(package: TosPackageView) -> None:
    st.subheader("Reproducibility auditor")
    audit = tos_audit_for_ui(package)
    if isinstance(audit, ServiceError):
        st.error(audit.message)
        return
    columns = st.columns(5)
    columns[0].metric("Evaluation rows", audit.evaluation_run_count)
    columns[1].metric("Training histories", audit.training_history_count)
    columns[2].metric("Instrumented runs", audit.instrumented_run_count)
    columns[3].metric("Per-task runs", audit.per_task_run_count)
    columns[4].metric("Processed traces", audit.trace_count)
    st.dataframe(
        [
            {
                "status": check.status.value,
                "code": check.code,
                "message": check.message,
                "affected capabilities": ", ".join(check.affected_capabilities),
            }
            for check in audit.checks
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(f"Package fingerprint: {audit.package_fingerprint}")
    st.caption(f"Source semantics commit: {audit.semantics_source_commit}")
    for warning in audit.warnings:
        st.caption(warning)


def _render_readiness(package: TosPackageView) -> None:
    st.subheader("External integration gates")
    readiness = tos_readiness_for_ui(package)
    if isinstance(readiness, ServiceError):
        st.error(readiness.message)
        return
    st.dataframe(
        [
            {
                "status": gate.status.value,
                "gate": gate.gate_id,
                "title": gate.title,
                "required for": ", ".join(gate.required_for),
                "next action": gate.next_action,
            }
            for gate in readiness.gates
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Unknown permissions are never treated as granted. Blocked capabilities remain disabled "
        "rather than being simulated."
    )


def _render_exports(package: TosPackageView) -> None:
    st.subheader("Supervisor, viva & dissertation pack")
    campaigns = sorted({run.campaign for run in package.evaluation_runs})
    variations = [campaign for campaign in campaigns if campaign != "baseline"]
    variation = st.selectbox("Comparison campaign for report", variations)
    st.warning(
        "Exports contain aggregate imported simulation results. Confirm permission before public "
        "deployment or sharing Randy-provided outputs outside the research team."
    )
    if st.button("Prepare private research exports", type="primary"):
        with st.spinner("Building deterministic exports from the inspected package..."):
            st.session_state["tos_report_exports"] = tos_report_exports_for_ui(
                package, variation_campaign=variation
            )
            st.session_state["tos_supervisor_pack"] = tos_supervisor_pack_for_ui(
                package, variation_campaign=variation
            )
            st.session_state["tos_report_variation"] = variation
    exports = st.session_state.get("tos_report_exports")
    if isinstance(exports, ServiceError):
        st.error(exports.message)
    elif isinstance(exports, tuple) and st.session_state.get("tos_report_variation") == variation:
        markdown, html, atlas = exports
        supervisor_pack = st.session_state.get("tos_supervisor_pack")
        columns = st.columns(4)
        columns[0].download_button(
            "Download research report (Markdown)",
            markdown,
            file_name="tos-research-report.md",
            mime="text/markdown",
        )
        columns[1].download_button(
            "Download research report (HTML)",
            html,
            file_name="tos-research-report.html",
            mime="text/html",
        )
        columns[2].download_button(
            "Download static results atlas",
            atlas,
            file_name="tos-results-atlas.html",
            mime="text/html",
        )
        if isinstance(supervisor_pack, bytes):
            columns[3].download_button(
                "Download private supervisor pack",
                supervisor_pack,
                file_name="traffictwin-tos-supervisor-pack.zip",
                mime="application/zip",
            )
        elif isinstance(supervisor_pack, ServiceError):
            columns[3].error(supervisor_pack.message)
        st.caption(
            "The supervisor ZIP includes checksums, a manifest, evaluation plan, viva notes, "
            "readiness gates, reports, and the aggregate atlas. Keep it private until publication "
            "permission is recorded."
        )
