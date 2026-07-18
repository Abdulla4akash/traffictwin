"""Provenance Explorer page."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.provenance.markdown import trace_to_markdown
from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.provenance.query import dependent_rules_for_metric
from traffictwin.provenance.serialization import trace_to_json
from traffictwin.ui.components.source_preview import render_source_row_preview
from traffictwin.ui.components.trace_tree import (
    render_trace_completeness,
    render_trace_lineage,
    render_trace_nodes,
    render_trace_summary,
)
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import (
    BundleAnalysis,
    metric_provenance_for_ui,
    rule_provenance_for_ui,
    run_provenance_for_ui,
    source_preview_for_ui,
)

PROVENANCE_NOTICE = (
    "Provenance shows how TrafficTwin derived a result from available records and configured "
    "rules. It does not establish real-world causality."
)


def render() -> None:
    """Render the Provenance Explorer."""

    st.title("Provenance Explorer")
    st.info(PROVENANCE_NOTICE)
    analysis = load_selected_analysis()
    if analysis is None:
        return
    render_source_caption(analysis)

    root_type = st.radio(
        "Trace root",
        ["Metric", "Diagnostic rule", "Source file row", "Run metadata"],
        horizontal=True,
    )
    if root_type == "Metric":
        _render_metric_trace(analysis)
    elif root_type == "Diagnostic rule":
        _render_rule_trace(analysis)
    elif root_type == "Source file row":
        _render_source_preview(analysis)
    else:
        _render_trace(run_provenance_for_ui(analysis), root_label="run")


def _render_metric_trace(analysis: BundleAnalysis) -> None:
    metrics = analysis.metrics
    if metrics is None:
        st.info("Metric provenance is unavailable because metrics were not computed.")
        return
    metric_keys = [metric.metric_key for metric in metrics.results]
    default_index = (
        metric_keys.index("task.completion.rate") if "task.completion.rate" in metric_keys else 0
    )
    metric_key = st.selectbox("Metric key", metric_keys, index=default_index)
    if not isinstance(metric_key, str):
        return
    definition = metric_catalogue().get(metric_key)
    metric = metrics.by_key().get(metric_key)
    with st.expander("Metric dependency view", expanded=True):
        st.write(
            {
                "key": metric_key,
                "definition": definition.model_dump(mode="json") if definition else "Unavailable",
                "current_status": metric.status.value if metric else "unavailable",
                "current_value": metric.value if metric else None,
                "dependent_rules": dependent_rules_for_metric(metric_key),
            }
        )
    _render_trace(metric_provenance_for_ui(analysis, metric_key), root_label=metric_key)


def _render_rule_trace(analysis: BundleAnalysis) -> None:
    report = analysis.diagnostic_report
    if report is None:
        st.info("Diagnostic provenance is unavailable because no DiagnosticReport is loaded.")
        return
    rule_ids = [result.rule_id for result in report.results]
    rule_id = st.selectbox("Rule result", rule_ids)
    if not isinstance(rule_id, str):
        return
    result = next(item for item in report.results if item.rule_id == rule_id)
    with st.expander("Rule dependency view", expanded=True):
        st.write(
            {
                "rule_id": result.rule_id,
                "status": result.status.value,
                "evidence_keys": result.evidence_keys,
                "missing_evidence": result.missing_evidence,
                "confidence": result.confidence.value,
                "thresholds": getattr(report.rule_config, rule_id.lower()).model_dump(mode="json"),
                "hypothesis": result.hypothesis,
                "alternatives": result.alternative_explanations,
                "recommendations": [
                    recommendation.model_dump(mode="json")
                    for recommendation in result.recommendations
                ],
            }
        )
    _render_trace(rule_provenance_for_ui(analysis, rule_id), root_label=rule_id)


def _render_source_preview(analysis: BundleAnalysis) -> None:
    validation = analysis.validation
    manifest = validation.manifest
    if manifest is None or not manifest.files:
        st.info("No declared source files are available for source-row inspection.")
        return
    files = [declaration.path for declaration in manifest.files.values()]
    source_file = st.selectbox("Source file", files)
    source_row = st.number_input("CSV line number", min_value=2, value=2, step=1)
    context_rows = st.slider("Context rows", min_value=0, max_value=5, value=2)
    if not isinstance(source_file, str):
        return
    preview = source_preview_for_ui(
        analysis,
        source_file,
        int(source_row),
        context_rows=int(context_rows),
    )
    render_source_row_preview(preview)
    st.download_button(
        "Download SourceRowPreview JSON",
        data=preview.model_dump_json(indent=2),
        file_name=f"source-row-{preview.file.replace('/', '_')}-{preview.row_number}.json",
        mime="application/json",
    )


def _render_trace(trace: ProvenanceTrace, *, root_label: str) -> None:
    render_trace_summary(trace)
    tab_summary, tab_lineage, tab_nodes, tab_export = st.tabs(
        ["Completeness", "Lineage", "Nodes", "Export"]
    )
    with tab_summary:
        render_trace_completeness(trace)
    with tab_lineage:
        render_trace_lineage(trace)
    with tab_nodes:
        render_trace_nodes(trace)
    with tab_export:
        json_payload = trace_to_json(trace)
        markdown_payload = trace_to_markdown(trace)
        safe_label = root_label.replace("/", "_").replace(":", "_")
        st.download_button(
            "Download trace JSON",
            data=json_payload,
            file_name=f"provenance-{safe_label}.json",
            mime="application/json",
        )
        st.download_button(
            "Download trace Markdown",
            data=markdown_payload,
            file_name=f"provenance-{safe_label}.md",
            mime="text/markdown",
        )
