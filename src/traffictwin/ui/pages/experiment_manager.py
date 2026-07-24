"""Experiment Manager page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.cards import fingerprint_summary, section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button, render_page_header
from traffictwin.ui.services import (
    ServiceError,
    initialise_protocol_tracking_for_ui,
    load_experiment_manager_view,
    protocol_tracking_rows_for_ui,
    update_protocol_slot_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def render(config: UiConfig) -> None:
    """Render experiments, runs, seeds, comparisons, and export references."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.EXPERIMENT_MANAGER))
    view = load_experiment_manager_view(config.registry_path, config.workspace_path)

    navigation_button(
        st.button,
        "Create Experiment Plan",
        UiPage.EXPERIMENT_PLANNER,
        kind="primary",
    )
    st.caption("Planning records metadata only; it does not create runs or launch a simulator.")

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
        experiment_rows = [
            {
                "experiment_id": row.get("experiment_id"),
                "status": row.get("status"),
                "baseline_seed_id": row.get("baseline_seed_id"),
                "planned_replicates": row.get("planned_replicates"),
                "algorithms": _join_values(row.get("algorithms", [])),
            }
            for row in experiments
        ]
        st.dataframe(
            experiment_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                experiment_rows,
                overrides={
                    "experiment_id": ColumnDisplay(
                        key="experiment_id", label="Experiment", hidden=False
                    )
                },
            ),
        )
    else:
        st.info("No experiments match the current filter.")

    section_header("Manual Protocol Tracking")
    experiment_ids = [str(row.get("experiment_id")) for row in view.experiments]
    if experiment_ids:
        selected_experiment = st.selectbox(
            "Experiment protocol",
            experiment_ids,
            key="tracking_experiment_id",
        )
        if st.button("Initialise Manual Slot Tracking"):
            result = initialise_protocol_tracking_for_ui(
                config.registry_path,
                selected_experiment,
            )
            if isinstance(result, ServiceError):
                st.error(result.message)
                st.caption(result.detail or "")
            else:
                st.success(
                    f"Tracking ready for {result['slot_count']} slots ({result['protocol_id']})."
                )
    tracking = protocol_tracking_rows_for_ui(config.registry_path)
    if isinstance(tracking, ServiceError):
        st.warning(tracking.message)
    elif tracking:
        st.dataframe(tracking, hide_index=True, width="stretch")
        slot_labels = [f"{row['protocol_id']} / {row['slot_id']}" for row in tracking]
        selected_slot = st.selectbox("Tracked slot", slot_labels)
        selected_index = slot_labels.index(selected_slot)
        selected_row = tracking[selected_index]
        cols = st.columns(2)
        next_status = cols[0].selectbox(
            "New status",
            ["received", "validated", "matched", "rejected", "complete"],
        )
        observed_run_id = cols[1].text_input("Observed run ID", value="")
        observed_bundle_id = st.text_input("Observed bundle ID", value="")
        tracking_note = st.text_input("Tracking note", value="")
        if st.button("Update Tracked Slot"):
            result = update_protocol_slot_for_ui(
                config.registry_path,
                str(selected_row["protocol_id"]),
                str(selected_row["slot_id"]),
                next_status,
                run_id=observed_run_id,
                bundle_id=observed_bundle_id,
                note=tracking_note,
            )
            if isinstance(result, ServiceError):
                st.error(result.message)
                st.caption(result.detail or "")
            else:
                st.success(f"{result['slot_id']} is now {result['status']}.")
    else:
        st.info("No protocol slots are tracked yet. Initialise one from a registered experiment.")

    section_header("Runs")
    runs = _filter_rows(view.runs, query)
    if status_filter != "all":
        runs = [row for row in runs if str(row.get("status")) == status_filter]
    if runs:
        run_rows = [
            {
                "run_id": row.get("run_id"),
                "algorithm": row.get("algorithm"),
                "status": row.get("status"),
                "metrics": view.metrics_by_run.get(str(row.get("run_id")), 0),
                "evidence": view.evidence_by_run.get(str(row.get("run_id")), 0),
                "experiment_id": row.get("experiment_id"),
                "seed_id": row.get("seed_id"),
                "random_seed": row.get("random_seed"),
            }
            for row in runs
        ]
        st.dataframe(
            run_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                run_rows,
                overrides={"run_id": ColumnDisplay(key="run_id", label="Run", hidden=False)},
            ),
        )
        with st.expander("Advanced: full run identifiers"):
            st.dataframe(
                run_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(run_rows, hide_machine_ids=False),
            )
    else:
        st.info("No runs match the current filter.")

    section_header("Bundle Imports")
    if view.bundle_imports:
        filtered_imports = _filter_rows(view.bundle_imports, query)
        import_rows = [
            {
                "bundle_id": row.get("bundle_id"),
                "run_id": row.get("run_id"),
                "fingerprint": fingerprint_summary(str(row.get("fingerprint", "")) or None),
                "source": row.get("source_reference"),
                "imported_at": row.get("imported_at"),
            }
            for row in filtered_imports
        ]
        st.dataframe(
            import_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                import_rows,
                overrides={
                    "bundle_id": ColumnDisplay(key="bundle_id", label="Bundle", hidden=False)
                },
            ),
        )
        with st.expander("Advanced: full bundle import identifiers"):
            full_import_rows = [
                {
                    "bundle_id": row.get("bundle_id"),
                    "run_id": row.get("run_id"),
                    "fingerprint": row.get("fingerprint"),
                    "source": row.get("source_reference"),
                    "imported_at": row.get("imported_at"),
                }
                for row in filtered_imports
            ]
            st.dataframe(
                full_import_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(full_import_rows, hide_machine_ids=False),
            )
    else:
        st.info("No bundle imports are registered.")

    section_header("Seeds And Policies")
    cols = st.columns(2)
    with cols[0]:
        seed_rows = [
            {
                "seed_id": row.get("id") or row.get("seed_id"),
                "name": row.get("name"),
                "base": row.get("base"),
                "schema_version": row.get("schema_version"),
            }
            for row in _filter_rows(view.seeds, query)
        ]
        st.dataframe(
            seed_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                seed_rows,
                overrides={"seed_id": ColumnDisplay(key="seed_id", label="Seed", hidden=False)},
            ),
        )
    with cols[1]:
        if view.policies:
            st.markdown("\n".join(f"- `{policy}`" for policy in view.policies))
        else:
            st.info("No policies registered.")

    section_header("Comparisons And Reports")
    cols = st.columns(2)
    with cols[0]:
        st.dataframe(
            view.comparisons,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(view.comparisons, hide_machine_ids=False),
        )
    with cols[1]:
        report_rows = [
            {
                "name": report.name,
                "type": report.report_type,
                "format": report.format_label,
                "scenario": report.scenario_hint,
            }
            for report in view.reports
        ]
        st.dataframe(
            report_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(report_rows),
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
