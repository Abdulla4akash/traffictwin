"""Bundle import and validation page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ingestion.batch import BatchBundleSummary, BatchOperation
from traffictwin.ingestion.bundle import StreamingBundleImportResult
from traffictwin.ingestion.streaming import StreamingBundleValidationResult
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.validation import render_validation_report
from traffictwin.ui.services import (
    ServiceError,
    import_bundle_batch_for_ui,
    import_bundle_streaming_for_ui,
    safe_import_bundle_for_ui,
    store_evidence_for_ui,
    store_metrics_for_ui,
    validate_bundle_batch_for_ui,
    validate_bundle_for_ui,
    validate_bundle_streaming_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import table_column_config


def render(config: UiConfig) -> None:
    """Render bundle import page."""

    st.title("Bundle Import & Validation")
    st.caption("Validated bundles are imported as historical or synthetic run evidence.")
    bundle_path = Path(
        st.text_input(
            "Bundle directory or ZIP path",
            value=str(
                st.session_state.get(
                    "selected_bundle_path", config.default_fixture_path / "baseline_valid"
                )
            ),
        )
    )
    st.session_state["selected_bundle_path"] = str(bundle_path)
    registry_path = Path(
        st.text_input(
            "Registry path",
            value=str(st.session_state.get("active_registry_path", config.registry_path)),
        )
    )
    st.session_state["active_registry_path"] = str(registry_path)

    _render_batch_import(registry_path)

    use_streaming = st.toggle(
        "Use chunked canonicalisation for a large bundle",
        help=(
            "Uses bounded row/byte chunks and a disk-backed validation index. "
            "It does not retain all canonical rows or automatically compute metrics."
        ),
    )
    if use_streaming:
        _render_streaming_import(bundle_path, registry_path)
        return

    if st.button("Validate Bundle", type="primary"):
        st.session_state["selected_bundle_path"] = str(bundle_path)

    if not bundle_path.exists():
        st.error(f"Bundle path does not exist: {bundle_path}")
        return

    analysis = validate_bundle_for_ui(bundle_path, config.metric_engine_config)
    report = analysis.validation.report
    manifest = analysis.validation.manifest
    badge_row(
        [report.status.value.upper().replace("_", " "), "IMPORTED" if manifest else "REJECTED"]
    )

    if manifest is not None:
        st.subheader("Manifest Summary")
        with st.container(border=True):
            st.markdown(
                f"**Environment:** {manifest.environment.name} "
                f"{manifest.environment.version or ''} · "
                f"**Declared files:** {len(manifest.files)}"
            )
            st.caption(f"Run `{manifest.run.run_id}`")
        with st.expander("Advanced: manifest identifiers"):
            st.code(
                f"bundle_id: {manifest.bundle.bundle_id}\n"
                f"run_id: {manifest.run.run_id}\n"
                f"experiment_id: {manifest.run.experiment_id}\n"
                f"seed_id: {manifest.run.seed_id}",
                language=None,
            )
            st.json(manifest.environment.model_dump(mode="json"))
        st.subheader("Declared Files")
        declared_rows = [
            {
                "kind": kind,
                "path": declaration.path,
                "format": declaration.format.value,
                "compression": (
                    declaration.compression.value if declaration.compression else "none"
                ),
                "schema_version": declaration.schema_version,
                "required": declaration.required,
                "required_columns": ", ".join(declaration.required_columns),
            }
            for kind, declaration in sorted(manifest.files.items())
        ]
        st.dataframe(
            declared_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(declared_rows, hide_machine_ids=False),
        )

    render_validation_report(report)
    st.subheader("Evidence Availability")
    evidence_states = analysis.validation.evidence.model_dump(mode="json")
    st.table(
        [
            {"Evidence": category.replace("_", " ").capitalize(), "State": badge_markdown(state)}
            for category, state in evidence_states.items()
        ]
    )
    with st.expander("Advanced: raw evidence availability JSON"):
        st.json(evidence_states)

    if (
        analysis.analysis_ready
        and analysis.metrics is not None
        and analysis.evidence_pack is not None
    ):
        if st.button("Import Accepted Bundle"):
            result = safe_import_bundle_for_ui(bundle_path, registry_path)
            if isinstance(result, ServiceError):
                st.error(result.message)
                with st.expander("Advanced: technical detail"):
                    st.write(result.detail)
            else:
                store_metrics_for_ui(registry_path, analysis.metrics)
                store_evidence_for_ui(registry_path, analysis.evidence_pack)
                st.success(
                    f"{result.message} Registry run `{result.run_id}` "
                    f"({'idempotent re-import' if result.idempotent else 'newly created'})."
                )
    else:
        st.error("Rejected bundles cannot be imported or used in analysis pages.")


def _render_batch_import(registry_path: Path) -> None:
    """Render thin controls over the deterministic batch ingestion service."""

    with st.expander("Batch validate or import"):
        st.caption(
            "Enter one explicit bundle path or glob per line. Paths are expanded, "
            "deduplicated, and processed in deterministic order."
        )
        raw_inputs = st.text_area(
            "Bundle paths or glob patterns",
            value=str(st.session_state.get("bundle_batch_inputs", "")),
            placeholder="/data/runs/run-001\n/data/runs/run-*.zip",
            key="bundle_batch_inputs",
        )
        inputs = [line.strip() for line in raw_inputs.splitlines() if line.strip()]
        validate_column, import_column = st.columns(2)
        with validate_column:
            if st.button("Validate Batch", width="stretch"):
                st.session_state["bundle_batch_summary"] = validate_bundle_batch_for_ui(inputs)
        with import_column:
            if st.button("Import Accepted Batch", width="stretch"):
                st.session_state["bundle_batch_summary"] = import_bundle_batch_for_ui(
                    inputs,
                    registry_path,
                )

        summary = st.session_state.get("bundle_batch_summary")
        if isinstance(summary, BatchBundleSummary):
            _render_batch_summary(summary)


def _render_batch_summary(summary: BatchBundleSummary) -> None:
    """Render consolidated and per-candidate batch outcomes."""

    status = summary.overall_status.value.upper()
    if summary.successful:
        st.success(f"Batch {summary.operation.value} completed.")
    elif summary.processed_bundle_count:
        st.warning(f"Batch {summary.operation.value} finished with status {status}.")
    else:
        st.error(f"Batch {summary.operation.value} failed before processing a bundle.")

    columns = st.columns(4)
    columns[0].metric("Matched", summary.matched_bundle_count)
    columns[1].metric("Accepted", summary.accepted_count)
    columns[2].metric("Rejected", summary.rejected_count)
    columns[3].metric("Input issues", len(summary.input_issues))
    if summary.operation is BatchOperation.IMPORT:
        import_columns = st.columns(4)
        import_columns[0].metric("Created", summary.created_count)
        import_columns[1].metric("Idempotent", summary.idempotent_count)
        import_columns[2].metric("Conflicts", summary.conflict_count)
        import_columns[3].metric("Failed", summary.failed_count)

    if summary.input_issues:
        st.subheader("Input issues")
        issue_rows = [issue.model_dump(mode="json") for issue in summary.input_issues]
        st.dataframe(
            issue_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(issue_rows, hide_machine_ids=False),
        )
    if summary.results:
        st.subheader("Per-bundle outcomes")
        outcome_rows = [result.model_dump(mode="json") for result in summary.results]
        st.dataframe(
            outcome_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(outcome_rows, hide_machine_ids=False),
        )
    st.download_button(
        "Download batch summary (JSON)",
        data=summary.to_json(),
        file_name=f"bundle-batch-{summary.operation.value}.json",
        mime="application/json",
    )


def _render_streaming_import(bundle_path: Path, registry_path: Path) -> None:
    """Render controls over memory-bounded canonicalisation and metadata import."""

    st.subheader("Chunked canonicalisation")
    st.caption(
        "Chunks are provisional until complete validation succeeds. Global duplicate and "
        "reference checks use temporary disk-backed state."
    )
    chunk_rows = int(
        st.number_input(
            "Maximum rows per chunk",
            min_value=1,
            max_value=100_000,
            value=1_000,
            step=100,
        )
    )
    if not bundle_path.exists():
        st.error(f"Bundle path does not exist: {bundle_path}")
        return

    validate_column, import_column = st.columns(2)
    with validate_column:
        if st.button("Stream Validate", type="primary", width="stretch"):
            st.session_state["streaming_bundle_result"] = validate_bundle_streaming_for_ui(
                bundle_path,
                chunk_rows=chunk_rows,
            )
    with import_column:
        if st.button("Stream Validate & Import", width="stretch"):
            imported = import_bundle_streaming_for_ui(
                bundle_path,
                registry_path,
                chunk_rows=chunk_rows,
            )
            st.session_state["streaming_bundle_result"] = imported

    result = st.session_state.get("streaming_bundle_result")
    if isinstance(result, ServiceError):
        st.error(result.message)
        with st.expander("Advanced: technical detail"):
            st.write(result.detail)
        return
    registry_result = None
    if isinstance(result, StreamingBundleImportResult):
        registry_result = result.registry
        validation = result.validation
    elif isinstance(result, StreamingBundleValidationResult):
        validation = result
    else:
        return

    if registry_result is not None:
        if registry_result.created or registry_result.idempotent:
            st.success(
                f"{registry_result.message} "
                f"({'idempotent re-import' if registry_result.idempotent else 'newly created'})."
            )
        else:
            st.error(registry_result.message)
    summary = validation.streaming
    metrics = st.columns(4)
    metrics[0].metric("Chunks", summary.chunk_count)
    metrics[1].metric("Canonical records", sum(summary.canonical_record_counts.values()))
    metrics[2].metric("Largest chunk rows", summary.max_observed_chunk_source_rows)
    metrics[3].metric("Largest chunk bytes", summary.max_observed_chunk_decoded_bytes)
    with st.expander("Advanced: raw streaming summary JSON"):
        st.json(summary.model_dump(mode="json"))
    render_validation_report(validation.report)
    st.download_button(
        "Download streaming validation (JSON)",
        data=validation.to_json(),
        file_name="streaming-bundle-validation.json",
        mime="application/json",
    )
    st.info(
        "Streaming import registers validated bundle/run metadata only. Use collected mode only "
        "when the complete canonical result fits memory and downstream metrics are required."
    )
