"""Import-only Eclipse SUMO XML workbench."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.metrics.results import MetricStatus
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.validation import render_validation_report
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    import_sumo_for_ui,
    validate_sumo_for_ui,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render SUMO result validation, summary replay, metrics, and import controls."""

    render_page_header(UiPage.SUMO_IMPORT)
    st.warning(
        "Import-only: TrafficTwin reads completed tripinfo.xml and summary.xml outputs. "
        "It does not launch SUMO, and FCD remains unavailable without an explicit mapping."
    )
    fixture = Path.cwd() / "tests/fixtures/sumo/square_public"
    default_source = fixture if fixture.is_dir() else Path.cwd()
    source = Path(
        st.text_input(
            "SUMO result directory",
            value=str(st.session_state.get("sumo_source_path", default_source)),
        )
    )
    st.session_state["sumo_source_path"] = str(source)
    registry = Path(
        st.text_input(
            "Registry path",
            value=str(st.session_state.get("active_registry_path", config.registry_path)),
        )
    )
    st.session_state["active_registry_path"] = str(registry)
    if not source.is_dir():
        st.error(f"SUMO result directory does not exist: {source}")
        return

    analysis = validate_sumo_for_ui(source, config.metric_engine_config)
    if isinstance(analysis, ServiceError):
        st.error(analysis.message)
        if analysis.detail:
            st.code(analysis.detail)
        return
    result = analysis.validation
    badge_row(
        [
            result.report.status.value.upper().replace("_", " "),
            "SUMO XML",
            "IMPORT ONLY",
            "SYNTHETIC" if result.manifest and result.manifest.source.synthetic else "IMPORTED",
        ]
    )
    if result.manifest is not None:
        manifest = result.manifest
        st.subheader("Source contract")
        st.json(
            {
                "bundle_id": manifest.bundle.bundle_id,
                "run_id": manifest.run.run_id,
                "scenario": manifest.source.scenario_id,
                "scenario_url": manifest.source.scenario_url,
                "sumo_version": manifest.source.sumo_version,
                "licence": manifest.source.licence_spdx,
                "retrieval_date": manifest.source.retrieval_date.isoformat(),
                "redistribution_allowed": manifest.source.redistribution_allowed,
                "direct_launch": False,
                "fcd_mapping": "unavailable",
            }
        )
    st.subheader("Preserved raw evidence")
    st.dataframe(
        [item.model_dump(mode="json") for item in result.raw_files],
        hide_index=True,
        width="stretch",
    )
    counts = st.columns(4)
    counts[0].metric("Tripinfo records", len(result.trip_observations))
    counts[1].metric("Canonical trips", len(result.canonical.trips))
    completed_value: str | int | float = "Unavailable"
    if analysis.metrics is not None:
        completed_value = analysis.metrics.by_key()["trip.completed.count"].value
    counts[2].metric("Completed trips", completed_value)
    counts[3].metric("Summary steps", len(result.summary_steps))

    render_validation_report(result.report)
    if result.summary_steps:
        st.subheader("SUMO network summary")
        st.caption(
            "These are source-specific simulation snapshots. Running is occupancy, not an "
            "interval traffic count."
        )
        stride = max(1, len(result.summary_steps) // 1000)
        chart_rows = [
            {
                "time_s": step.time_s,
                "running": step.running,
                "halting": step.halting,
                "mean_speed_mps": step.mean_speed_mps,
            }
            for step in result.summary_steps[::stride]
        ]
        st.line_chart(chart_rows, x="time_s", y=["running", "halting"])
        st.line_chart(chart_rows, x="time_s", y="mean_speed_mps")

    if analysis.metrics is not None:
        st.subheader("Deterministic canonical trip metrics")
        keys = (
            "trip.records.count",
            "trip.completed.count",
            "trip.incomplete.count",
            "trip.completion.rate",
            "trip.duration.mean_s",
            "trip.duration.p95_s",
        )
        by_key = analysis.metrics.by_key()
        st.dataframe(
            [
                {
                    "metric": key,
                    "status": by_key[key].status.value,
                    "value": (
                        by_key[key].value if by_key[key].status is MetricStatus.AVAILABLE else None
                    ),
                    "unit": by_key[key].unit,
                }
                for key in keys
            ],
            hide_index=True,
            width="stretch",
        )
    if result.report.may_import and st.button("Import SUMO Results", type="primary"):
        imported = import_sumo_for_ui(
            source,
            registry,
            analysis,
            config.metric_engine_config,
        )
        if isinstance(imported, ServiceError):
            st.error(imported.message)
            if imported.detail:
                st.code(imported.detail)
        else:
            st.success(
                f"{imported.message}; run={imported.run_id}; "
                f"idempotent={imported.idempotent}; metrics_stored={imported.metrics_stored}"
            )
