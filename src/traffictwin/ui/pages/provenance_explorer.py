"""Provenance Explorer page."""

from __future__ import annotations

import re

import streamlit as st

from traffictwin.metrics.catalogue import metric_definition_for_result
from traffictwin.provenance.completeness import provenance_completeness_report_to_csv
from traffictwin.provenance.contributions import contribution_report_to_csv
from traffictwin.provenance.graph_export import (
    MAX_GRAPH_EDGE_LIMIT,
    MAX_GRAPH_NODE_LIMIT,
    GraphRedactionMode,
    provenance_graph_to_dot,
    provenance_graph_to_graphml,
)
from traffictwin.provenance.markdown import trace_to_markdown
from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.provenance.query import dependent_rules_for_metric
from traffictwin.provenance.serialization import trace_to_json
from traffictwin.reporting.models import ResearchReportType
from traffictwin.ui.components.badges import badge_markdown
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
    ServiceError,
    metric_contributions_for_ui,
    metric_provenance_for_ui,
    provenance_graph_for_ui,
    report_provenance_completeness_for_ui,
    rule_provenance_for_ui,
    run_provenance_for_ui,
    source_preview_for_ui,
)
from traffictwin.ui.tables import table_column_config

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
    _render_report_completeness(analysis)

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


def _render_report_completeness(analysis: BundleAnalysis) -> None:
    with st.expander("Report claim provenance completeness (PRO-03)", expanded=True):
        st.caption(
            "Every typed result claim stays in the denominator. The score gives no partial "
            "credit to aggregate-only or unavailable claims and does not measure truth or "
            "causality."
        )
        report_type = st.selectbox(
            "Completeness report template",
            [ResearchReportType.RUN.value, ResearchReportType.DIAGNOSTICS.value],
            format_func=lambda value: str(value).title(),
        )
        completeness = report_provenance_completeness_for_ui(analysis, str(report_type))
        if isinstance(completeness, ServiceError):
            st.error(completeness.message)
            if completeness.detail:
                st.caption(completeness.detail)
            return
        score = f"{completeness.score * 100:.1f}%" if completeness.score is not None else "N/A"
        columns = st.columns(5)
        columns[0].metric("Source-row score", score)
        columns[1].metric("Denominator", completeness.denominator_count)
        columns[2].metric("Source-row complete", completeness.source_row_complete_count)
        columns[3].metric("Aggregate only", completeness.aggregate_only_count)
        columns[4].metric("Unavailable", completeness.unavailable_count)
        claim_rows = [
            {
                "claim": claim.artifact_key,
                "kind": claim.claim_kind.value,
                "status": claim.artifact_status,
                "classification": claim.classification.value,
                "depth": claim.trace_depth.value,
                "candidate_rows": claim.candidate_source_row_count,
                "reasons": "; ".join(claim.reason_codes),
            }
            for claim in completeness.claims
        ]
        st.dataframe(
            claim_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(claim_rows),
        )
        st.caption(completeness.denominator_definition)
        with st.expander("Advanced/Evidence: denominator exclusions and trace-depth rules"):
            st.json(
                {
                    "exclusions": [
                        item.model_dump(mode="json") for item in completeness.exclusions
                    ],
                    "trace_depth_rules": completeness.trace_depth_rules,
                    "score_numerator": completeness.score_numerator_definition,
                }
            )
        downloads = st.columns(2)
        downloads[0].download_button(
            "Download completeness JSON",
            data=completeness.to_json(),
            file_name=f"{completeness.report_id}-provenance-completeness.json",
            mime="application/json",
        )
        downloads[1].download_button(
            "Download completeness CSV",
            data=provenance_completeness_report_to_csv(completeness),
            file_name=f"{completeness.report_id}-provenance-completeness.csv",
            mime="text/csv",
        )


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
    metric = metrics.by_key().get(metric_key)
    definition = metric_definition_for_result(metric) if metric is not None else None
    dependent_rules = dependent_rules_for_metric(metric_key)
    with st.container(border=True):
        st.markdown(
            f"**Metric:** `{metric_key}` · "
            f"**Status:** {badge_markdown(metric.status.value if metric else 'unavailable')}"
        )
        st.markdown(
            f"**Current value:** {metric.value if metric else 'Unavailable'} · "
            f"**Dependent rules:** {', '.join(dependent_rules) if dependent_rules else 'none'}"
        )
        st.caption(
            "Dependency links are how this metric feeds configured rules; they do not establish "
            "real-world causality."
        )
    with st.expander("Advanced/Evidence: metric definition and dependents (raw)"):
        st.json(
            {
                "key": metric_key,
                "definition": definition.model_dump(mode="json") if definition else "Unavailable",
                "current_status": metric.status.value if metric else "unavailable",
                "current_value": metric.value if metric else None,
                "dependent_rules": dependent_rules,
            }
        )
    with st.expander("Complete canonical-row contribution ledger"):
        contributions = metric_contributions_for_ui(analysis, metric_key)
        ledger_cols = st.columns(4)
        ledger_cols[0].metric("Candidate rows", contributions.candidate_row_count, border=True)
        ledger_cols[1].metric("Included rows", contributions.included_row_count, border=True)
        ledger_cols[2].metric("Excluded rows", contributions.excluded_row_count, border=True)
        with ledger_cols[3], st.container(border=True):
            st.caption("Complete row ledger")
            st.markdown(badge_markdown("yes" if contributions.complete_row_ledger else "no"))
        ledger_rows = [
            {
                "table": row.canonical_table,
                "record_id": row.record_id,
                "source": f"{row.source_file}:{row.source_row}",
                "included": row.included,
                "reason": row.inclusion_reason,
            }
            for row in contributions.rows
        ]
        st.dataframe(
            ledger_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(ledger_rows),
        )
        cols = st.columns(2)
        cols[0].download_button(
            "Download contribution JSON",
            data=contributions.to_json(),
            file_name=f"{metric_key.replace('.', '_')}-contributions.json",
            mime="application/json",
        )
        cols[1].download_button(
            "Download contribution CSV",
            data=contribution_report_to_csv(contributions),
            file_name=f"{metric_key.replace('.', '_')}-contributions.csv",
            mime="text/csv",
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
    with st.container(border=True):
        st.markdown(
            f"**Rule:** `{result.rule_id}` · "
            f"**Status:** {badge_markdown(result.status.value)} · "
            f"**Confidence:** {badge_markdown(result.confidence.value)}"
        )
        if result.hypothesis:
            st.markdown(f"**Candidate hypothesis:** {result.hypothesis}")
        st.markdown(
            f"**Evidence keys:** {', '.join(result.evidence_keys) or 'none'}\n\n"
            f"**Missing evidence:** "
            + ("; ".join(result.missing_evidence) if result.missing_evidence else "none")
        )
        if result.alternative_explanations:
            st.markdown(
                "**Alternative explanations:** " + "; ".join(result.alternative_explanations)
            )
        st.caption("A hypothesis is a candidate explanation, not a confirmed cause.")
    with st.expander("Advanced/Evidence: rule thresholds and recommendations (raw)"):
        st.json(
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
    source_row = st.number_input("Source record number", min_value=2, value=2, step=1)
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
    tab_summary, tab_graph, tab_lineage, tab_nodes, tab_export = st.tabs(
        ["Completeness", "Graph", "Lineage", "Nodes", "Export"]
    )
    with tab_summary:
        render_trace_completeness(trace)
    with tab_graph:
        st.caption(
            "The view is a bounded projection of the existing trace. Layout is visual only; "
            "the exported node and edge data remain deterministic."
        )
        controls = st.columns(3)
        node_limit = controls[0].slider(
            "Maximum graph nodes",
            min_value=1,
            max_value=min(250, MAX_GRAPH_NODE_LIMIT),
            value=min(max(1, len(trace.nodes)), 120),
        )
        edge_limit = controls[1].slider(
            "Maximum graph edges",
            min_value=0,
            max_value=min(1_000, MAX_GRAPH_EDGE_LIMIT),
            value=min(len(trace.edges), 240),
        )
        redaction = controls[2].selectbox(
            "Graph disclosure profile",
            [mode.value for mode in GraphRedactionMode],
            format_func=lambda value: str(value).replace("_", " ").title(),
        )
        graph_view = provenance_graph_for_ui(
            trace,
            node_limit=int(node_limit),
            edge_limit=int(edge_limit),
            redaction_mode=str(redaction),
        )
        if isinstance(graph_view, ServiceError):
            st.error(graph_view.message)
            if graph_view.detail:
                st.caption(graph_view.detail)
        else:
            summary_cols = st.columns(4)
            summary_cols[0].metric("Shown nodes", f"{len(graph_view.nodes)}/{len(trace.nodes)}")
            summary_cols[1].metric("Shown edges", f"{len(graph_view.edges)}/{len(trace.edges)}")
            summary_cols[2].metric("Redactions", graph_view.redaction_count)
            with summary_cols[3], st.container(border=True):
                st.caption("Truncated")
                st.markdown(badge_markdown("yes" if graph_view.truncated else "no"))
            if graph_view.truncated:
                st.warning(
                    f"Bounded view omitted {graph_view.omitted_node_count} nodes and "
                    f"{graph_view.omitted_edge_count} edges. Increase the limits to inspect more."
                )
            st.graphviz_chart(provenance_graph_to_dot(graph_view), width="stretch")
            selected_node_id = st.selectbox(
                "Inspect graph node",
                [node.node_id for node in graph_view.nodes],
                format_func=lambda node_id: next(
                    f"{node.label} — {node.node_type.value}"
                    for node in graph_view.nodes
                    if node.node_id == node_id
                ),
            )
            selected_node = next(
                node for node in graph_view.nodes if node.node_id == selected_node_id
            )
            st.markdown(
                f"**Node:** {selected_node.label} · "
                f"**Type:** {badge_markdown(selected_node.node_type.value)}"
            )
            with st.expander("Advanced/Evidence: selected node (raw)"):
                st.json(selected_node.model_dump(mode="json"))
    with tab_lineage:
        render_trace_lineage(trace)
    with tab_nodes:
        render_trace_nodes(trace)
    with tab_export:
        json_payload = trace_to_json(trace)
        markdown_payload = trace_to_markdown(trace)
        safe_label = _safe_download_stem(root_label)
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
        if not isinstance(graph_view, ServiceError):
            st.download_button(
                "Download bounded graph DOT",
                data=provenance_graph_to_dot(graph_view),
                file_name=f"provenance-{safe_label}.dot",
                mime="text/vnd.graphviz",
            )
            st.download_button(
                "Download bounded graph GraphML",
                data=provenance_graph_to_graphml(graph_view),
                file_name=f"provenance-{safe_label}.graphml",
                mime="application/graphml+xml",
            )


def _safe_download_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return safe[:100] or "trace"
