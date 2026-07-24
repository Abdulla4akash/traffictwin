"""Shared page helpers."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.services import BundleAnalysis, validate_bundle_for_ui


def selected_bundle_path() -> Path:
    """Return the selected bundle path from session state."""

    return Path(
        str(st.session_state.get("selected_bundle_path", "tests/fixtures/bundles/baseline_valid"))
    )


def load_selected_analysis() -> BundleAnalysis | None:
    """Load the selected bundle and guard rejected bundles."""

    path = selected_bundle_path()
    if not path.exists():
        st.error(f"Bundle path does not exist: {path}")
        return None
    analysis = validate_bundle_for_ui(path)
    st.session_state["latest_validation_report"] = analysis.validation.report
    st.session_state["latest_metric_collection"] = analysis.metrics
    st.session_state["latest_evidence_pack"] = analysis.evidence_pack
    if not analysis.analysis_ready:
        st.error("This bundle is rejected and cannot be used in analysis pages.")
        with st.expander("Advanced: raw validation report JSON"):
            st.json(analysis.validation.report.model_dump(mode="json"))
        return None
    return analysis


def render_source_caption(analysis: BundleAnalysis) -> None:
    """Render a source/provenance caption.

    The primary caption shows a readable truncated fingerprint; the complete
    value stays accessible in the Advanced expander beneath it.
    """

    manifest = analysis.validation.manifest
    source = "SYNTHETIC" if manifest and manifest.environment.name == "synthetic" else "IMPORTED"
    fingerprint = analysis.validation.fingerprint
    st.caption(
        f"Data source: {source} | Bundle: {analysis.source_path} | "
        f"Fingerprint: `{fingerprint_summary(fingerprint)}`"
    )
    if fingerprint:
        with st.expander("Advanced: bundle identity"):
            st.code(
                f"bundle_path: {analysis.source_path}\nfingerprint: {fingerprint}",
                language=None,
            )
