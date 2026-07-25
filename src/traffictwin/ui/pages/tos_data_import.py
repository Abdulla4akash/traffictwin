"""Read-only TOS Data package import and replay page."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from traffictwin.integration.tos import TosRsuReplayPoint
from traffictwin.integration.tos.readers import instrumented_key_for_run
from traffictwin.metrics.results import MetricStatus
from traffictwin.provenance.serialization import trace_to_json
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.cards import fingerprint_summary
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    TosPackageView,
    analyse_tos_run_for_ui,
    compare_tos_runs_for_ui,
    import_tos_for_ui,
    inspect_tos_for_ui,
    load_tos_replay_for_ui,
    load_tos_rsu_series_for_ui,
    load_tos_task_sample_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import ColumnDisplay, table_column_config


def render(config: UiConfig) -> None:
    """Render the evidence-gated TOS package workflow."""

    render_page_header(UiPage.TOS_DATA)
    st.info(
        "This page reads an imported simulation-results package. It does not launch Randy's "
        "environment or provide live data. Confirmed source-specific RSU fields remain separate "
        "from TrafficTwin's canonical infrastructure metrics."
    )
    default_path = str(st.session_state.get("selected_tos_data_path") or config.tos_data_path or "")
    source_text = st.text_input(
        "TOS Data package directory",
        value=default_path,
        placeholder="Path to the checked-out TOS Data repository",
    )
    st.session_state["selected_tos_data_path"] = source_text
    source = Path(source_text) if source_text else None
    inspect_col, validate_col = st.columns(2)
    inspect_clicked = inspect_col.button("Inspect Package", type="primary")
    validate_clicked = validate_col.button("Deep Validate NPZ Contracts")
    if inspect_clicked or validate_clicked:
        if source is None or not source.is_dir():
            st.error("Select an existing TOS Data package directory.")
        else:
            with st.spinner("Inspecting the package without modifying source files..."):
                view = inspect_tos_for_ui(source, deep=validate_clicked)
            st.session_state["latest_tos_package_view"] = view

    view = st.session_state.get("latest_tos_package_view")
    if isinstance(view, ServiceError):
        st.error(view.message)
        if view.detail:
            with st.expander("Advanced: technical detail"):
                st.code(view.detail)
        return
    if not isinstance(view, TosPackageView):
        st.caption("Inspect a package to view its documented runs and source arrays.")
        return
    if source is None:
        return
    _render_package_summary(view)
    _render_import(view, source, config)
    _render_run_analysis(view)
    _render_comparison(view)
    _render_replay(view, source)


def _render_package_summary(view: TosPackageView) -> None:
    report = view.report
    badge_row([report.status.value.upper().replace("_", " "), "IMPORTED SIMULATION"])
    inventory = report.inventory
    columns = st.columns(5)
    columns[0].metric("Evaluation runs", inventory.evaluation_rows)
    columns[1].metric("Per-step files", inventory.perstep_files)
    columns[2].metric("Per-task showcases", inventory.pertask_files)
    columns[3].metric("Trace files", inventory.trace_files)
    columns[4].metric("Training curves", inventory.training_csv_files)
    st.caption(
        f"Engine: {', '.join(report.engine_versions) or 'unavailable'} | "
        f"Package commit: `{fingerprint_summary(report.package_commit)}` | "
        f"Fingerprint: `{fingerprint_summary(report.package_fingerprint)}`"
    )
    if report.package_commit or report.package_fingerprint:
        with st.expander("Advanced: package identity"):
            st.code(
                f"package_commit: {report.package_commit or 'unavailable'}\n"
                f"package_fingerprint: {report.package_fingerprint or 'unavailable'}",
                language=None,
            )
    st.subheader("Capability boundary")
    capabilities = report.capabilities.model_dump(mode="json")
    capability_table_rows = [
        {"capability": key, "status": "SUPPORTED" if value else "UNSUPPORTED"}
        for key, value in capabilities.items()
    ]
    st.dataframe(
        capability_table_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(capability_table_rows),
    )
    with st.expander(f"Validation findings ({len(report.findings)})", expanded=True):
        finding_rows = [
            {
                "severity": item.severity.value,
                "code": item.code,
                "message": item.message,
                "affected": ", ".join(item.affected_capabilities),
            }
            for item in report.findings
        ]
        st.dataframe(
            finding_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(finding_rows),
        )
    with st.expander("vec_env source contract"):
        contract = view.source_contract
        st.caption(
            f"Semantics evidence commit: {contract.evidence_commit} | "
            f"SUMO: {contract.source_versions['sumo']} | "
            f"Direct launch: {contract.execution.direct_launch.value.upper()}"
        )
        contract_rows = [
            {
                "field": item.field,
                "meaning": item.meaning,
                "unit": item.unit or "not applicable",
                "status": item.status.value,
                "limitations": "; ".join(item.limitations),
            }
            for item in contract.fields
        ]
        st.dataframe(
            contract_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(contract_rows),
        )
        st.warning("Direct launch remains disabled: " + "; ".join(contract.execution.blockers))


def _render_import(view: TosPackageView, source: Path, config: UiConfig) -> None:
    st.subheader("Registry import")
    registry = Path(
        st.text_input(
            "Registry path for TOS summaries",
            value=str(st.session_state.get("active_registry_path", config.registry_path)),
            key="tos_registry_path",
        )
    )
    st.session_state["active_registry_path"] = str(registry)
    st.caption(
        "Import registers 300 source-summary runs when the current package is complete. "
        "It does not create canonical task or infrastructure rows."
    )
    if st.button(
        "Import Evaluation Summaries",
        disabled=not view.report.may_import_summaries,
    ):
        with st.spinner("Registering source summaries idempotently..."):
            result = import_tos_for_ui(source, registry, view.report)
        if isinstance(result, ServiceError):
            st.error(result.message)
            if result.detail:
                with st.expander("Advanced: technical detail"):
                    st.code(result.detail)
        else:
            st.success(
                f"Runs created: {result.runs_created}; existing: {result.runs_existing}; "
                f"metric collections stored: {result.metric_collections_stored}."
            )


def _render_run_analysis(view: TosPackageView) -> None:
    st.subheader("Evaluation summary analysis")
    campaigns = sorted({run.campaign for run in view.evaluation_runs})
    cells = sorted({run.cell for run in view.evaluation_runs})
    filter_cols = st.columns(3)
    campaign = filter_cols[0].selectbox("Campaign", ["All", *campaigns])
    cell = filter_cols[1].selectbox("Scenario cell", ["All", *cells])
    fleet = filter_cols[2].selectbox("Evaluation fleet", ["All", "synthetic", "uk2030"])
    filtered = [
        run
        for run in view.evaluation_runs
        if (campaign == "All" or run.campaign == campaign)
        and (cell == "All" or run.cell == cell)
        and (fleet == "All" or run.eval_fleet == fleet)
    ]
    evaluation_rows = [
        {
            "run_id": run.run_id,
            "campaign": run.campaign,
            "cell": run.cell,
            "fleet": run.eval_fleet,
            "seed": run.fleet_seed,
            "deadline_success": run.completion,
            "mean_latency_ms_all_arrivals": run.avg_latency_ms_per_task,
            "local": run.p_local,
            "v2i": run.p_v2i,
            "v2v": run.p_v2v,
        }
        for run in filtered[:200]
    ]
    st.dataframe(
        evaluation_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(
            evaluation_rows,
            overrides={
                "run_id": ColumnDisplay(key="run_id", label="Run", hidden=False),
                "mean_latency_ms_all_arrivals": ColumnDisplay(
                    key="mean_latency_ms_all_arrivals",
                    label="Mean latency (ms, all arrivals)",
                ),
            },
        ),
    )
    if not filtered:
        st.warning("No evaluation rows match the selected filters.")
        return
    run_id = st.selectbox("Selected evaluation run", [run.run_id for run in filtered])
    analysis = analyse_tos_run_for_ui(view, run_id)
    if isinstance(analysis, ServiceError):
        st.error(analysis.message)
        return
    metrics = analysis.metric_collection.by_key()
    metric_cols = st.columns(4)
    for column, key, label in zip(
        metric_cols,
        (
            "tos.task.deadline_success.rate",
            "task.latency.mean_ms",
            "task.offload.rate",
            "infra.utilisation.mean",
        ),
        ("Deadline success", "Mean latency (ms)", "Offload share", "RSU utilisation"),
        strict=True,
    ):
        metric = metrics[key]
        with column:
            if metric.status is MetricStatus.AVAILABLE:
                st.metric(label, metric.value, border=True)
            else:
                with st.container(border=True):
                    st.caption(label)
                    st.markdown(badge_markdown("unavailable"))
    st.warning(
        "Completion is the source-defined fraction of arrivals meeting deadlines. Mean latency "
        "includes deadline-missing arrivals and can represent backlog in overloaded cells."
    )
    st.markdown(
        f"**Diagnostic readiness:** "
        f"{badge_markdown(analysis.diagnostic_report.overall_readiness.value)}"
    )
    st.table(
        [
            {"Rule": result.rule_id, "Status": badge_markdown(result.status.value)}
            for result in analysis.diagnostic_report.results
        ]
    )
    downloads = st.columns(3)
    downloads[0].download_button(
        "Download EvidencePack JSON",
        analysis.evidence_pack.to_json(),
        file_name=f"{analysis.run.run_id.replace(':', '-')}-evidence.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Download DiagnosticReport JSON",
        analysis.diagnostic_report.to_json(),
        file_name=f"{analysis.run.run_id.replace(':', '-')}-diagnostics.json",
        mime="application/json",
    )
    downloads[2].download_button(
        "Download Provenance JSON",
        trace_to_json(analysis.completion_trace),
        file_name=f"{analysis.run.run_id.replace(':', '-')}-provenance.json",
        mime="application/json",
    )


def _render_replay(view: TosPackageView, source: Path) -> None:
    st.subheader("Instrumented historical replay")
    badge_row(["HISTORICAL REPLAY", "IMPORTED SIMULATION"])
    if not view.instrumented_runs:
        st.info("No matched per-step and summary artifacts are available.")
        return
    run_key = st.selectbox("Instrumented run", view.instrumented_runs)
    evaluation = next(
        (row for row in view.evaluation_runs if instrumented_key_for_run(row) == run_key),
        None,
    )
    maximum = max((evaluation.duration_s - 1) if evaluation else 0, 0)
    index = int(
        st.number_input(
            "Time index",
            min_value=0,
            max_value=maximum,
            value=0,
            step=1,
        )
    )
    frame = load_tos_replay_for_ui(source, run_key, index, max_vehicles=100)
    if isinstance(frame, ServiceError):
        st.error(frame.message)
        return
    point_cols = st.columns(4)
    point_cols[0].metric("Source timestamp", frame.point.timestamp_s)
    point_cols[1].metric("Arrivals", frame.point.arrivals)
    point_cols[2].metric("Deadline met", frame.point.deadline_met)
    point_cols[3].metric("Active slots", frame.total_active_vehicle_slots)
    if frame.vehicles:
        figure = go.Figure(
            go.Scatter(
                x=[vehicle.position_x_source_units for vehicle in frame.vehicles],
                y=[vehicle.position_y_source_units for vehicle in frame.vehicles],
                mode="markers",
                text=[vehicle.slot_reference for vehicle in frame.vehicles],
                customdata=[vehicle.speed_source_units for vehicle in frame.vehicles],
                hovertemplate=(
                    "%{text}<br>x=%{x:.1f} m<br>y=%{y:.1f} m"
                    "<br>speed=%{customdata:.2f} m/s<extra></extra>"
                ),
            )
        )
        figure.update_layout(
            title="Vehicle slots at selected source timestamp",
            xaxis_title="Network position x (m)",
            yaxis_title="Network position y (m)",
            height=420,
        )
        st.plotly_chart(figure, width="stretch")
    with st.expander("RSU source state", expanded=True):
        st.info(
            "rsu_load is the active in-flight task count; rsu_busy_ms is remaining compute "
            "backlog. Pressure is active tasks / maximum concurrent tasks. It is not CPU "
            "utilisation or canonical queue length."
        )
        st.dataframe(
            [
                {
                    "RSU": state.rsu_reference,
                    "active tasks": state.rsu_load_source_value,
                    "remaining backlog (ms)": state.rsu_busy_ms_source_value,
                    "maximum concurrent tasks": state.rsu_max_concurrent_source_value,
                    "concurrency pressure": state.load_pressure_fraction,
                }
                for state in frame.rsus
            ],
            hide_index=True,
            width="stretch",
        )
    stride = max(1, (maximum + 1) // 600)
    if st.button("Load RSU Pressure History"):
        with st.spinner("Loading bounded source-specific RSU history..."):
            st.session_state["tos_rsu_series"] = load_tos_rsu_series_for_ui(
                source,
                run_key,
                stride=stride,
            )
            st.session_state["tos_rsu_series_run"] = run_key
    rsu_series = st.session_state.get("tos_rsu_series")
    if (
        isinstance(rsu_series, ServiceError)
        and st.session_state.get("tos_rsu_series_run") == run_key
    ):
        st.error(rsu_series.message)
    elif isinstance(rsu_series, list) and st.session_state.get("tos_rsu_series_run") == run_key:
        _render_rsu_history(rsu_series)
    for warning in frame.warnings:
        st.caption(warning)
    if run_key in view.pertask_runs:
        if st.button("Load 50 Per-Task Entries"):
            st.session_state["tos_task_sample"] = load_tos_task_sample_for_ui(
                source,
                run_key,
                limit=50,
            )
        sample = st.session_state.get("tos_task_sample")
        if isinstance(sample, ServiceError):
            st.error(sample.message)
        elif sample is not None and getattr(sample, "run_key", None) == run_key:
            sample_rows = [item.model_dump(mode="json") for item in sample.observations]
            st.dataframe(
                sample_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(sample_rows, hide_machine_ids=False),
            )


def _render_rsu_history(points: list[TosRsuReplayPoint]) -> None:
    """Render source-state history already interpreted by the integration service."""

    if not points:
        st.info("No RSU source history is available for this run.")
        return
    by_rsu: dict[str, list[TosRsuReplayPoint]] = {}
    for point in points:
        by_rsu.setdefault(point.rsu_reference, []).append(point)
    pressure = go.Figure()
    backlog = go.Figure()
    for reference, values in sorted(by_rsu.items()):
        pressure.add_trace(
            go.Scatter(
                x=[item.timestamp_s for item in values],
                y=[item.concurrency_pressure_fraction for item in values],
                mode="lines",
                name=reference,
            )
        )
        backlog.add_trace(
            go.Scatter(
                x=[item.timestamp_s for item in values],
                y=[item.remaining_compute_backlog_ms for item in values],
                mode="lines",
                name=reference,
            )
        )
    pressure.update_layout(
        title="RSU concurrency pressure (source-specific inspection)",
        xaxis_title="Simulation time (s)",
        yaxis_title="Active tasks / maximum concurrent tasks",
        height=360,
    )
    backlog.update_layout(
        title="RSU remaining compute backlog",
        xaxis_title="Simulation time (s)",
        yaxis_title="Remaining compute backlog (ms)",
        height=360,
    )
    st.plotly_chart(pressure, width="stretch")
    st.plotly_chart(backlog, width="stretch")
    st.caption(
        "These source-specific state signals are not Phase 3 infrastructure utilisation or "
        "queue-length metrics."
    )


def _render_comparison(view: TosPackageView) -> None:
    st.subheader("Source-summary comparison")
    st.caption(
        "Choose runs with the same cell, evaluation fleet, and fleet seed. Comparison uses the "
        "existing deterministic delta service and retains source-metric provenance."
    )
    options = [run.run_id for run in view.evaluation_runs]
    if len(options) < 2:
        st.info("At least two evaluation rows are required for comparison.")
        return
    pairable = {
        run.run_id
        for run in view.evaluation_runs
        if any(
            candidate.experiment_id == run.experiment_id
            and candidate.fleet_seed == run.fleet_seed
            and candidate.run_id != run.run_id
            for candidate in view.evaluation_runs
        )
    }
    default_index = next(
        (index for index, run_id in enumerate(options) if run_id in pairable),
        0,
    )
    columns = st.columns(2)
    baseline = columns[0].selectbox("Baseline source run", options, index=default_index)
    baseline_run = next(run for run in view.evaluation_runs if run.run_id == baseline)
    compatible = [
        run.run_id
        for run in view.evaluation_runs
        if run.experiment_id == baseline_run.experiment_id
        and run.fleet_seed == baseline_run.fleet_seed
        and run.run_id != baseline
    ]
    if not compatible:
        st.info("No compatible comparison run is available for this source row.")
        return
    variation = columns[1].selectbox("Variation source run", compatible)
    comparison = compare_tos_runs_for_ui(view, baseline, variation)
    if isinstance(comparison, ServiceError):
        st.error(comparison.message)
        return
    rows = [
        {
            "metric_key": item.metric_key,
            "baseline": item.baseline,
            "variation": item.variation,
            "absolute_delta": item.absolute_delta,
            "relative_delta": item.relative_delta,
            "direction": item.direction.value,
        }
        for item in comparison.comparable_metrics
    ]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(rows),
    )
    if comparison.warnings:
        st.warning("; ".join(comparison.warnings))
