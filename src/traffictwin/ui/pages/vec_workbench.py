"""Thin capability-gated VEC-10 workbench."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.integration.vec_interface import (
    VecInterfaceError,
    compare_vec_admissions,
    export_vec_admission,
    inspect_vec_artifact,
    inspect_vec_interface,
    load_preprocess_request,
    load_run_request,
    load_scientific_admission,
)
from traffictwin.integration.vec_orchestration import (
    VecExecutionPreset,
    VecOrchestrationError,
    VecWorkflowRequest,
    VecWorkflowStatus,
    execute_and_import,
    list_imported_vec_executions,
    preset_workload,
)
from traffictwin.integration.vec_preprocessing import (
    VecFcdPreflightReport,
    VecFcdPreprocessingError,
    VecFcdPreprocessReceipt,
    preflight_vec_fcd,
    preprocess_vec_fcd,
)
from traffictwin.integration.vec_runner import (
    VecExecutionReceipt,
    VecRunnerError,
    VecRunnerPreflightReport,
    preflight_vec_run,
    run_vec_evaluator,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header


def render() -> None:
    """Render the VEC-10 interface without constructing scientific requests in the UI."""

    render_page_header(UiPage.VEC_WORKBENCH)
    st.info(
        "This page delegates typed JSON requests to the accepted VEC-06/VEC-07 services. "
        "Execution is foreground-only and request-specific. There is no command box, background "
        "queue, training, dependency installer, or source-repository write path."
    )
    paths = _source_paths()
    _snapshot_section(*paths)
    _one_click_section(*paths)
    _request_section(*paths)
    _artifact_section()
    _comparison_and_export_section()


def _source_paths() -> tuple[Path, Path]:
    columns = st.columns(2)
    vec_repo = Path(
        columns[0].text_input(
            "vec_env repository",
            value=str(st.session_state.get("vec_repo_path", "../external/vec_env")),
            key="vec_repo_path",
        )
    )
    tos_repo = Path(
        columns[1].text_input(
            "tos-data repository",
            value=str(st.session_state.get("vec_tos_repo_path", "../external/tos-data")),
            key="vec_tos_repo_path",
        )
    )
    return vec_repo, tos_repo


def _snapshot_section(vec_repo: Path, tos_repo: Path) -> None:
    st.subheader("1. Source snapshot and capability boundary")
    if st.button("Inspect pinned repositories", type="primary"):
        try:
            st.session_state["vec_interface_snapshot"] = inspect_vec_interface(vec_repo, tos_repo)
        except (OSError, VecInterfaceError) as exc:
            st.session_state["vec_interface_error"] = str(exc)
    error = st.session_state.pop("vec_interface_error", None)
    if error:
        st.error(str(error))
    snapshot = st.session_state.get("vec_interface_snapshot")
    if snapshot is None:
        st.caption("Inspect the repositories before attempting request-specific validation.")
        return
    st.dataframe(
        [
            {
                "repository": item.repository,
                "clean": item.clean,
                "audited commit available": item.audited_commit_available,
                "exact blob access": item.ready_for_exact_blob_access,
                "worktree head": item.worktree_head,
            }
            for item in snapshot.repositories
        ],
        hide_index=True,
        width="stretch",
    )
    st.dataframe(
        [
            {
                "operation": item.operation,
                "availability": item.availability.value,
                "reason": item.reason,
            }
            for item in snapshot.operations
        ],
        hide_index=True,
        width="stretch",
    )


def one_click_ready(
    input_root: str,
    output_dir: str,
    registry_path: str,
    preset: VecExecutionPreset,
    confirmed: bool,
) -> bool:
    """Return whether the one-click action may be enabled; full runs need confirmation."""

    complete = bool(input_root.strip()) and bool(output_dir.strip()) and bool(registry_path.strip())
    if preset is VecExecutionPreset.FULL_REPRODUCTION:
        return complete and confirmed
    return complete


def _one_click_section(vec_repo: Path, tos_repo: Path) -> None:
    st.subheader("2. One-click controlled execution")
    st.caption(
        "One explicit action runs the complete request-specific preflight, the allowlisted "
        "foreground evaluator, output revalidation, and one idempotent registry import. "
        "There is no background execution, live SUMO, training, or unrestricted launch."
    )
    preset_value = st.selectbox(
        "Closed execution preset",
        [item.value for item in VecExecutionPreset],
        key="vec_oneclick_preset",
    )
    preset = VecExecutionPreset(preset_value)
    workload = preset_workload(preset)
    st.write(
        {
            "evaluator steps (request property)": workload.evaluator_steps,
            "trace": workload.trace_file,
            "timeout bound (s)": workload.timeout_seconds_bound,
            "foreground only": workload.foreground_only,
        }
    )
    st.caption(workload.description)
    input_root = st.text_input(
        "Input root (tos-data working tree)",
        value=str(st.session_state.get("vec_oneclick_input_root", tos_repo)),
        key="vec_oneclick_input_root",
    )
    output_dir = st.text_input(
        "New output directory (must not exist)",
        key="vec_oneclick_output_dir",
    )
    registry_path = st.text_input(
        "Active registry path",
        value=str(st.session_state.get("active_registry_path", "")),
        key="vec_oneclick_registry_path",
    )
    confirmed = True
    if preset is VecExecutionPreset.FULL_REPRODUCTION:
        confirmed = st.checkbox(
            "I understand the full protocol-seed reproduction is a long foreground run "
            "and is distinct from the _s102 best-of-seeds evidence.",
            key="vec_oneclick_confirm_full",
        )
    ready = one_click_ready(input_root, output_dir, registry_path, preset, confirmed)
    if not ready:
        st.caption(
            "Provide the input root, a new output directory, the registry path, and any "
            "required confirmation."
        )
    if st.button(
        "Validate, Run and Import",
        type="primary",
        disabled=not ready,
        key="vec_oneclick_execute",
    ):
        try:
            workflow = VecWorkflowRequest(
                preset=preset,
                input_root=input_root,
                vec_repo=str(vec_repo),
                tos_data_repo=str(tos_repo),
                output_dir=output_dir,
                registry_path=registry_path,
                confirm_full_run=confirmed,
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        monitor = st.status("Current process: validating preflight", expanded=True)
        monitor.update(label="Current process: preflight, execution, validation, import")
        receipt = execute_and_import(workflow)
        st.session_state["vec_oneclick_receipt"] = receipt
        st.session_state["active_registry_path"] = registry_path
        if receipt.status is VecWorkflowStatus.COMPLETED_IMPORTED:
            monitor.update(label="Current process: completed and imported", state="complete")
        else:
            monitor.update(label=f"Current process: {receipt.status.value}", state="error")
    receipt = st.session_state.get("vec_oneclick_receipt")
    _imported_execution_records(registry_path)
    if receipt is None:
        return
    st.write(f"Workflow: **{receipt.status.value}**")
    st.dataframe(
        [
            {
                "stage": item.stage.value,
                "state": item.state.value,
                "detail": item.detail,
            }
            for item in receipt.stages
        ],
        hide_index=True,
        width="stretch",
    )
    if receipt.status is VecWorkflowStatus.COMPLETED_IMPORTED and receipt.import_outcome:
        outcome = receipt.import_outcome
        st.success(
            ("Idempotent re-import of " if outcome.idempotent else "Imported ")
            + f"registry run `{outcome.registry_run_id}` "
            + f"(stable fingerprint `{outcome.stable_fingerprint[:16]}`)."
        )
        st.write(
            {
                "receipt fingerprint": receipt.receipt_fingerprint,
                "output fingerprint": receipt.output_fingerprint,
                "import record fingerprint": receipt.import_record_stable_fingerprint,
                "external repositories unchanged": (
                    receipt.external_repositories_verified_unchanged
                ),
                "raw inputs unchanged": receipt.raw_inputs_verified_unchanged,
            }
        )
        st.dataframe(
            [
                {
                    "output": item.path,
                    "size (bytes)": item.size_bytes,
                    "sha256": item.sha256,
                }
                for item in receipt.outputs
            ],
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Imported evidence is structural execution evidence: scientific admission stays "
            "unavailable, deadline success is not physical completion, selected actions are "
            "not confirmed transfers, and no publication permission is granted. The persisted "
            "record is available in Imported VEC execution records above and the basic run row "
            "is listed in Experiment Manager."
        )
    else:
        for finding in receipt.findings:
            st.error(finding)
        st.caption(
            "Nothing was imported. Failed, rejected, timed-out, cancelled, or mutated "
            "executions never create registry records."
        )


def _imported_execution_records(registry_path: str) -> None:
    with st.expander("Imported VEC execution records"):
        if not registry_path.strip():
            st.caption("Enter an active registry path to inspect persisted VEC executions.")
            return
        try:
            records = list_imported_vec_executions(registry_path)
        except (OSError, VecOrchestrationError) as exc:
            st.error(str(exc))
            return
        if not records:
            st.caption("No one-click VEC execution records are stored in this registry.")
            return
        labels = [f"{item.registry_run_id} / {item.preset.value}" for item in records]
        selected_label = st.selectbox(
            "Imported execution",
            labels,
            key="vec_oneclick_imported_record",
        )
        selected = records[labels.index(selected_label)]
        st.write(
            {
                "run id": selected.registry_run_id,
                "preset": selected.preset.value,
                "evidence grade": selected.evidence_grade.value,
                "scientific admission": selected.scientific_admission_status,
                "publication": selected.publication_status,
                "request fingerprint": selected.request_fingerprint,
                "receipt fingerprint": selected.receipt_fingerprint,
                "output fingerprint": selected.output_fingerprint,
                "vec_env commit": selected.vec_env_commit,
                "tos-data commit": selected.tos_data_commit,
            }
        )
        st.dataframe(
            [
                {
                    "output": item.path,
                    "size (bytes)": item.size_bytes,
                    "sha256": item.sha256,
                }
                for item in selected.outputs
            ],
            hide_index=True,
            width="stretch",
        )
        for limitation in selected.limitations:
            st.warning(limitation)


def _request_section(vec_repo: Path, tos_repo: Path) -> None:
    st.subheader("3. Validate and execute one typed request")
    kind = st.radio("Request type", ("preprocess", "run"), horizontal=True)
    request_path = Path(st.text_input("Request JSON path", key="vec_request_path"))
    input_root = Path(st.text_input("Input root", key="vec_input_root"))
    output_path = Path(st.text_input("New output directory", key="vec_output_path"))
    if st.button("Validate typed request"):
        try:
            report: VecFcdPreflightReport | VecRunnerPreflightReport
            if kind == "preprocess":
                request = load_preprocess_request(request_path)
                report = preflight_vec_fcd(input_root, vec_repo, request)
            else:
                run_request = load_run_request(request_path)
                report = preflight_vec_run(input_root, vec_repo, tos_repo, run_request)
            st.session_state["vec_preflight_kind"] = kind
            st.session_state["vec_preflight"] = report
        except (OSError, VecInterfaceError) as exc:
            st.error(str(exc))
    report = st.session_state.get("vec_preflight")
    report_kind = st.session_state.get("vec_preflight_kind")
    accepted = isinstance(report, (VecFcdPreflightReport, VecRunnerPreflightReport)) and (
        report.status.value == "accepted"
    )
    if isinstance(report, (VecFcdPreflightReport, VecRunnerPreflightReport)):
        st.write(f"Preflight: **{report.status.value}**")
        st.dataframe(
            [
                {
                    "severity": item.severity.value,
                    "code": item.code,
                    "message": item.message,
                }
                for item in report.findings
            ],
            hide_index=True,
            width="stretch",
        )
    label = "Execute preprocessing" if kind == "preprocess" else "Run evaluator in foreground"
    disabled = not accepted or report_kind != kind
    if st.button(label, disabled=disabled, type="primary"):
        monitor = st.status("Current process: validating", expanded=True)
        try:
            receipt: VecFcdPreprocessReceipt | VecExecutionReceipt
            monitor.update(label="Current process: running foreground", state="running")
            if kind == "preprocess":
                receipt = preprocess_vec_fcd(
                    input_root,
                    vec_repo,
                    output_path,
                    load_preprocess_request(request_path),
                )
            else:
                receipt = run_vec_evaluator(
                    input_root,
                    vec_repo,
                    tos_repo,
                    output_path,
                    load_run_request(request_path),
                )
            monitor.update(label="Current process: completed", state="complete")
            st.success(f"Completed with receipt fingerprint {receipt.fingerprint()}")
        except (OSError, VecInterfaceError, VecFcdPreprocessingError, VecRunnerError) as exc:
            monitor.update(label="Current process: failed", state="error")
            st.error(str(exc))
    st.caption(
        "Monitoring covers only the foreground operation owned by this Streamlit process. "
        "Closing or restarting the app does not create or recover a job queue."
    )


def _artifact_section() -> None:
    st.subheader("4. Inspect a portable receipt or report")
    artifact = Path(st.text_input("Artifact JSON path", key="vec_artifact_path"))
    if st.button("Inspect VEC artifact"):
        try:
            st.session_state["vec_artifact_inspection"] = inspect_vec_artifact(artifact)
        except VecInterfaceError as exc:
            st.error(str(exc))
    inspection = st.session_state.get("vec_artifact_inspection")
    if inspection is not None:
        st.json(inspection.model_dump(mode="json"))


def _comparison_and_export_section() -> None:
    st.subheader("5. Compare or export accepted scientific admission")
    columns = st.columns(2)
    baseline = Path(columns[0].text_input("Baseline VEC-09 report", key="vec_baseline_report"))
    variation = Path(columns[1].text_input("Variation VEC-09 report", key="vec_variation_report"))
    if st.button("Compare compatible scalar metrics"):
        try:
            comparison = compare_vec_admissions(
                load_scientific_admission(baseline),
                load_scientific_admission(variation),
            )
            st.session_state["vec_admission_comparison"] = comparison
        except VecInterfaceError as exc:
            st.error(str(exc))
    comparison = st.session_state.get("vec_admission_comparison")
    if comparison is not None:
        st.warning(
            "Differences are descriptive variation-minus-baseline values, not causal effects."
        )
        st.dataframe(
            [item.model_dump(mode="json") for item in comparison.comparable_metrics],
            hide_index=True,
            width="stretch",
        )
    export_report = Path(st.text_input("VEC-09 report to export", key="vec_export_report"))
    export_format = st.selectbox("Export format", ("json", "csv", "markdown"))
    try:
        export_payload = (
            export_vec_admission(load_scientific_admission(export_report), export_format)
            if str(export_report) not in {"", "."} and export_report.is_file()
            else None
        )
    except VecInterfaceError as exc:
        st.error(str(exc))
        export_payload = None
    st.download_button(
        "Download VEC-09 export",
        data=export_payload or "",
        file_name=f"vec-scientific-admission.{_extension(export_format)}",
        mime=_mime(export_format),
        disabled=export_payload is None,
    )


def _extension(output_format: str) -> str:
    return {"json": "json", "csv": "csv", "markdown": "md"}[output_format]


def _mime(output_format: str) -> str:
    return {
        "json": "application/json",
        "csv": "text/csv",
        "markdown": "text/markdown",
    }[output_format]
