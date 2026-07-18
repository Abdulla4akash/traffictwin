"""Experiment Manager page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import load_experiment_manager_view
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render experiments, runs, seeds, comparisons, and export references."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.EXPERIMENT_MANAGER))
    view = load_experiment_manager_view(config.registry_path, config.workspace_path)

    cols = st.columns(5)
    cols[0].metric("Experiments", len(view.experiments))
    cols[1].metric("Runs", len(view.runs))
    cols[2].metric("Seeds", len(view.seeds))
    cols[3].metric("Reports", len(view.reports))
    cols[4].metric("Comparisons", len(view.comparisons))

    query = st.text_input("Filter manager tables", value="")
    status_filter = st.selectbox("Run status", ["all", "completed", "failed", "imported"])

    section_header("Experiments")
    experiments = _filter_rows(view.experiments, query)
    if experiments:
        st.dataframe(
            [
                {
                    "experiment_id": row.get("experiment_id"),
                    "status": row.get("status"),
                    "baseline_seed_id": row.get("baseline_seed_id"),
                    "planned_replicates": row.get("planned_replicates"),
                    "algorithms": _join_values(row.get("algorithms", [])),
                }
                for row in experiments
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No experiments match the current filter.")

    section_header("Runs")
    runs = _filter_rows(view.runs, query)
    if status_filter != "all":
        runs = [row for row in runs if str(row.get("status")) == status_filter]
    if runs:
        st.dataframe(
            [
                {
                    "run_id": row.get("run_id"),
                    "experiment_id": row.get("experiment_id"),
                    "seed_id": row.get("seed_id"),
                    "algorithm": row.get("algorithm"),
                    "random_seed": row.get("random_seed"),
                    "status": row.get("status"),
                    "metrics": view.metrics_by_run.get(str(row.get("run_id")), 0),
                    "evidence": view.evidence_by_run.get(str(row.get("run_id")), 0),
                }
                for row in runs
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No runs match the current filter.")

    section_header("Bundle Imports")
    if view.bundle_imports:
        st.dataframe(
            [
                {
                    "bundle_id": row.get("bundle_id"),
                    "run_id": row.get("run_id"),
                    "fingerprint": str(row.get("fingerprint", ""))[:16],
                    "source": row.get("source_reference"),
                    "imported_at": row.get("imported_at"),
                }
                for row in _filter_rows(view.bundle_imports, query)
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No bundle imports are registered.")

    section_header("Seeds And Policies")
    cols = st.columns(2)
    with cols[0]:
        st.dataframe(
            [
                {
                    "seed_id": row.get("id") or row.get("seed_id"),
                    "name": row.get("name"),
                    "base": row.get("base"),
                    "schema_version": row.get("schema_version"),
                }
                for row in _filter_rows(view.seeds, query)
            ],
            hide_index=True,
            width="stretch",
        )
    with cols[1]:
        st.write(view.policies or ["No policies registered."])

    section_header("Comparisons And Reports")
    cols = st.columns(2)
    with cols[0]:
        st.dataframe(view.comparisons, hide_index=True, width="stretch")
    with cols[1]:
        st.dataframe(
            [
                {
                    "name": report.name,
                    "type": report.report_type,
                    "format": report.format_label,
                    "scenario": report.scenario_hint,
                }
                for report in view.reports
            ],
            hide_index=True,
            width="stretch",
        )


def _filter_rows(rows: list[dict[str, object]], query: str) -> list[dict[str, object]]:
    needle = query.strip().lower()
    if not needle:
        return rows
    return [row for row in rows if needle in " ".join(str(value) for value in row.values()).lower()]


def _join_values(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
