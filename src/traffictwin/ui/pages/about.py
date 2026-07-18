"""About page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.cards import metadata_card, section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import about_info_for_ui


def render() -> None:
    """Render package, schema, and version metadata."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.ABOUT))
    st.info(
        "TrafficTwin is a standalone research prototype. Licence is not yet specified. "
        "No Randy, SUMO, or live Manchester integration is active."
    )
    info = about_info_for_ui()
    metadata_card(
        "Version Metadata",
        {
            "package_version": info.package_version,
            "synthetic_generator_version": info.generator_version,
            "metric_version": info.metric_version,
            "diagnostic_ruleset_version": info.diagnostic_version,
            "provenance_schema_version": info.provenance_version,
            "python_version": info.python_version,
            "commit_hash": info.commit_hash or "unavailable",
            "licence": info.licence,
        },
    )
    section_header("Schema Versions")
    st.dataframe(
        [
            {"contract": "ScenarioSeed", "schema_version": "1.0"},
            {"contract": "Run bundle manifest", "schema_version": "1.0"},
            {"contract": "EvidencePack", "schema_version": "1.0"},
            {"contract": "DiagnosticReport", "schema_version": "1.0"},
            {"contract": "ProvenanceTrace", "schema_version": "1.0"},
        ],
        hide_index=True,
        width="stretch",
    )
