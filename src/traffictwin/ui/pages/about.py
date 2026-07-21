"""About page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.cards import metadata_card, section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    about_info_for_ui,
    declarative_rule_contract_for_ui,
    metric_plugin_api_for_ui,
)


def render() -> None:
    """Render package, schema, and version metadata."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.ABOUT))
    st.info(
        "TrafficTwin is a standalone research prototype. Licence is not yet specified. "
        "Audited Randy/VEC import and conditional foreground evaluation are available through "
        "the dedicated workbench; general SUMO launch and live Manchester data are unavailable."
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
            {"contract": "Declarative rule grammar", "schema_version": "1.0"},
            {"contract": "ProvenanceTrace", "schema_version": "1.0"},
        ],
        hide_index=True,
        width="stretch",
    )
    section_header("Trusted Metric Extensions")
    plugin_api = metric_plugin_api_for_ui()
    st.write(
        {
            "schema_version": plugin_api.schema_version,
            "registration_mode": plugin_api.registration_mode,
            "repeatability_runs": plugin_api.determinism_verification_runs,
            "failure_policy": plugin_api.execution_failure_policy,
            "uploaded_code_execution": plugin_api.uploaded_code_execution,
            "sandboxed_execution": plugin_api.sandboxed_execution,
        }
    )
    st.warning(
        "Custom metrics are explicit trusted local Python registrations. The UI does not upload, "
        "import, or execute user-supplied code, and repeatability checking is not a sandbox."
    )
    section_header("Trusted Declarative Rules")
    rule_contract = declarative_rule_contract_for_ui()
    st.write(
        {
            "schema_version": rule_contract.schema_version,
            "grammar_version": rule_contract.grammar_version,
            "trust_boundary": rule_contract.trust_boundary,
            "evidence_boundary": rule_contract.evidence_boundary,
            "maximum_yaml_bytes": rule_contract.maximum_yaml_bytes,
            "maximum_predicates": rule_contract.maximum_predicates,
            "reference_rule": rule_contract.reference_rule_id,
        }
    )
    st.warning(
        "Declarative rules use a closed threshold/boolean grammar over EvidencePack metrics. "
        "There is no YAML upload/evaluation control in the UI, arbitrary code is unsupported, "
        "and trusted local configuration is not a sandbox or scientific-validity guarantee."
    )
