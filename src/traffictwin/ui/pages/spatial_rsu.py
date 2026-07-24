"""Evidence-gated per-RSU outcome and source-frame spatial summary page."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.results import MetricValue
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.services import BundleAnalysis
from traffictwin.ui.tables import table_column_config


def render() -> None:
    """Render contracted task-target and vehicle-grid evidence."""

    st.title("Spatial & RSU Evidence")
    analysis = load_selected_analysis()
    if analysis is None or analysis.metrics is None:
        return
    render_source_caption(analysis)
    metrics = analysis.metrics.by_key()
    st.info(
        "Per-RSU task outcomes use exact observed V2I execution targets. Spatial cells use only "
        "the declared source coordinate frame. TrafficTwin does not assign a nearest RSU, "
        "interpolate task positions, or claim geographic/causal meaning."
    )

    target_count = metrics.get("spatial.rsu.task.count_by_target")
    grid_count = metrics.get("spatial.vehicle.observation_count_by_grid_cell")
    _render_frame_and_provenance(analysis, grid_count)

    st.subheader("Task Outcomes By Execution-Target RSU")
    rsu_rows = _rsu_rows(metrics)
    if rsu_rows:
        columns = st.columns(2)
        columns[0].metric("Target RSU groups", len(rsu_rows))
        columns[1].metric(
            "Target coverage",
            _percentage(target_count.metadata.get("coverage_fraction") if target_count else None),
        )
        st.dataframe(
            rsu_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                rsu_rows,
                number_formats={
                    "completion_rate": "%.3f",
                    "completed_observed_deadline_miss_rate": "%.3f",
                    "mean_capacity_normalised_load": "%.3f",
                },
            ),
        )
        if target_count is not None:
            st.caption(_target_contract_caption(target_count))
    else:
        render_metric_unavailable(
            target_count,
            "a task-to-RSU contract plus complete exact V2I target_id-to-rsu_id joins",
        )
    _render_target_reconciliation(target_count)

    st.subheader("Vehicle Source-Frame Grid")
    grid_rows = _grid_rows(metrics)
    if grid_rows:
        columns = st.columns(2)
        columns[0].metric("Observed grid cells", len(grid_rows))
        columns[1].metric(
            "Coordinate coverage",
            _percentage(grid_count.metadata.get("coverage_fraction") if grid_count else None),
        )
        st.dataframe(
            grid_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(grid_rows, number_formats={"mean_speed_mps": "%.3f"}),
        )
        _render_grid_chart(grid_rows)
        if grid_count is not None:
            st.caption(_grid_contract_caption(grid_count))
    else:
        render_metric_unavailable(
            grid_count,
            "a coordinate-frame/grid contract and complete finite vehicle x/y observations",
        )
    _render_grid_reconciliation(grid_count)


def _render_frame_and_provenance(analysis: BundleAnalysis, grid_count: MetricValue | None) -> None:
    """Distinguish source/synthetic coordinates from geographic Manchester coordinates."""

    manifest = analysis.validation.manifest
    synthetic = manifest is not None and manifest.environment.name == "synthetic"
    provenance = "synthetic" if synthetic else "imported"
    frame = None
    if grid_count is not None:
        frame_value = grid_count.metadata.get("coordinate_frame_id")
        frame = str(frame_value) if frame_value is not None else None
    with st.container(border=True):
        st.markdown(
            f"**Coordinate provenance:** {badge_markdown(provenance)} · "
            f"**Coordinate frame:** `{frame or 'unavailable'}`"
        )
        st.caption(
            "Coordinates are in the declared source frame, not geographic Manchester coordinates. "
            "No live position and no official RSU location are implied; unprojectable or unmatched "
            "records are reported below rather than placed on a map."
        )


def _render_target_reconciliation(target_count: MetricValue | None) -> None:
    """Show matched and unmatched task-to-RSU records explicitly."""

    section_header("Execution-Target Reconciliation")
    metadata = target_count.metadata if target_count is not None else {}
    columns = st.columns(3)
    columns[0].metric(
        "Matched target tasks (count)", _int_display(metadata.get("eligible_count")), border=True
    )
    columns[1].metric(
        "Missing-target tasks (count)",
        _int_display(metadata.get("missing_target_count")),
        border=True,
    )
    columns[2].metric(
        "Unknown-target tasks (count)",
        _int_display(metadata.get("unknown_target_count")),
        border=True,
    )
    st.caption(
        "RSU assignment uses exact observed V2I targets only. Tasks with a missing or unknown "
        "target are reported as their own counts, never assigned to a nearest or assumed RSU."
    )


def _render_grid_reconciliation(grid_count: MetricValue | None) -> None:
    """Show positioned and unprojectable observations, plus the source-frame extent."""

    section_header("Coordinate Reconciliation")
    metadata = grid_count.metadata if grid_count is not None else {}
    eligible = metadata.get("eligible_count")
    population = metadata.get("population_count")
    unprojectable: object = "Unavailable"
    if isinstance(eligible, int) and isinstance(population, int):
        unprojectable = max(population - eligible, 0)
    columns = st.columns(3)
    columns[0].metric("Positioned observations (count)", _int_display(eligible), border=True)
    columns[1].metric("Total observations (count)", _int_display(population), border=True)
    columns[2].metric(
        "Unprojectable observations (count)", _int_display(unprojectable), border=True
    )
    extent = _extent_caption(metadata)
    if extent:
        st.caption(extent)
    st.caption(
        "Observations without finite source coordinates are reported as unprojectable and are "
        "never projected onto a geographic map or assigned an assumed position."
    )


def _render_grid_chart(grid_rows: list[dict[str, object]]) -> None:
    """Chart vehicle observations per source-frame grid cell, clearly non-geographic."""

    chart_rows = [
        {
            "grid_cell": str(row["grid_cell"]),
            "Observations": _int_value(row.get("vehicle_observations")),
        }
        for row in grid_rows
        if isinstance(row.get("vehicle_observations"), int)
    ]
    if not chart_rows:
        return
    st.bar_chart(
        chart_rows,
        x="grid_cell",
        y="Observations",
        x_label="Source-frame cell",
        y_label="Observations",
    )
    st.caption(
        "Descriptive observation counts per source-frame cell; this is not a geographic map and "
        "implies no real-world position."
    )


def _rsu_rows(metrics: dict[str, MetricValue]) -> list[dict[str, object]]:
    counts = _metric_dict(metrics.get("spatial.rsu.task.count_by_target"))
    completion = _metric_dict(metrics.get("spatial.rsu.task.completion_rate_by_target"))
    misses = _metric_dict(
        metrics.get("spatial.rsu.task.deadline_miss.completed_observed_rate_by_target")
    )
    loads = _metric_dict(metrics.get("fairness.rsu.capacity_normalised_load.by_group"))
    groups = sorted(set(counts) | set(completion) | set(misses) | set(loads))
    return [
        {
            "rsu_id": group,
            "targeted_v2i_tasks": counts.get(group),
            "completion_rate": completion.get(group),
            "completed_observed_deadline_miss_rate": misses.get(group),
            "mean_capacity_normalised_load": loads.get(group),
        }
        for group in groups
    ]


def _grid_rows(metrics: dict[str, MetricValue]) -> list[dict[str, object]]:
    observations = _metric_dict(metrics.get("spatial.vehicle.observation_count_by_grid_cell"))
    vehicles = _metric_dict(metrics.get("spatial.vehicle.distinct_count_by_grid_cell"))
    speeds = _metric_dict(metrics.get("spatial.vehicle.speed.mean_mps_by_grid_cell"))
    cells = sorted(set(observations) | set(vehicles) | set(speeds))
    return [
        {
            "grid_cell": cell,
            "vehicle_observations": observations.get(cell),
            "distinct_vehicles": vehicles.get(cell),
            "mean_speed_mps": speeds.get(cell),
        }
        for cell in cells
    ]


def _metric_dict(metric: MetricValue | None) -> dict[str, object]:
    if metric is None or not isinstance(metric.value, dict):
        return {}
    return metric.value


def _percentage(value: object) -> str:
    if isinstance(value, int | float):
        return f"{100 * value:.1f}%"
    return "Unavailable"


def _int_display(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return "Unavailable"


def _int_value(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _extent_caption(metadata: dict[str, object]) -> str | None:
    keys = ("minimum_x_m", "maximum_x_m", "minimum_y_m", "maximum_y_m")
    if not all(isinstance(metadata.get(key), int | float) for key in keys):
        return None
    return (
        f"Source-frame extent: x in [{metadata['minimum_x_m']}, {metadata['maximum_x_m']}] m, "
        f"y in [{metadata['minimum_y_m']}, {metadata['maximum_y_m']}] m (non-geographic)."
    )


def _target_contract_caption(metric: MetricValue) -> str:
    metadata = metric.metadata
    return (
        f"Task-to-RSU contract {metadata.get('task_rsu_target_contract_version')}; "
        f"fingerprint {metadata.get('task_rsu_target_contract_fingerprint')}; "
        f"join {metadata.get('target_join_method')}."
    )


def _grid_contract_caption(metric: MetricValue) -> str:
    metadata = metric.metadata
    return (
        f"Coordinate frame {metadata.get('coordinate_frame_id')}; "
        f"grid {metadata.get('cell_width_m')} m × {metadata.get('cell_height_m')} m; "
        f"contract fingerprint {metadata.get('vehicle_spatial_grid_contract_fingerprint')}."
    )
