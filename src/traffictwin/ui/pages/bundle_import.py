"""Bundle import and validation page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.validation import render_validation_report
from traffictwin.ui.services import (
    ServiceError,
    safe_import_bundle_for_ui,
    store_evidence_for_ui,
    store_metrics_for_ui,
    validate_bundle_for_ui,
)
from traffictwin.ui.state import UiConfig


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
        st.json(
            {
                "bundle_id": manifest.bundle.bundle_id,
                "run_id": manifest.run.run_id,
                "experiment_id": manifest.run.experiment_id,
                "seed_id": manifest.run.seed_id,
                "environment": manifest.environment.model_dump(mode="json"),
                "declared_files": sorted(manifest.files),
            }
        )
        st.subheader("Declared Files")
        st.dataframe(
            [
                {
                    "kind": kind,
                    "path": declaration.path,
                    "schema_version": declaration.schema_version,
                    "required": declaration.required,
                    "required_columns": ", ".join(declaration.required_columns),
                }
                for kind, declaration in sorted(manifest.files.items())
            ],
            hide_index=True,
            width="stretch",
        )

    render_validation_report(report)
    st.subheader("Evidence Availability")
    st.json(analysis.validation.evidence.model_dump(mode="json"))

    if (
        analysis.analysis_ready
        and analysis.metrics is not None
        and analysis.evidence_pack is not None
    ):
        if st.button("Import Accepted Bundle"):
            result = safe_import_bundle_for_ui(bundle_path, registry_path)
            if isinstance(result, ServiceError):
                st.error(result.message)
                with st.expander("Technical detail"):
                    st.write(result.detail)
            else:
                store_metrics_for_ui(registry_path, analysis.metrics)
                store_evidence_for_ui(registry_path, analysis.evidence_pack)
                st.success(f"{result.message}; run={result.run_id}; idempotent={result.idempotent}")
    else:
        st.error("Rejected bundles cannot be imported or used in analysis pages.")
