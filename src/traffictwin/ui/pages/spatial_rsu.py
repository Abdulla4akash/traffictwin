"""Evidence-gated per-RSU outcome and source-frame spatial summary page."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.results import MetricValue
from traffictwin.ui.components.unavailable import render_metric_unavailable
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption


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
    st.subheader("Task Outcomes By Execution-Target RSU")
    rsu_rows = _rsu_rows(metrics)
    if rsu_rows:
        columns = st.columns(2)
        columns[0].metric("Target RSU groups", len(rsu_rows))
        columns[1].metric(
            "Target coverage",
            _percentage(target_count.metadata.get("coverage_fraction") if target_count else None),
        )
        st.dataframe(rsu_rows, hide_index=True, width="stretch")
        if target_count is not None:
            st.caption(_target_contract_caption(target_count))
    else:
        render_metric_unavailable(
            target_count,
            "a task-to-RSU contract plus complete exact V2I target_id-to-rsu_id joins",
        )

    grid_count = metrics.get("spatial.vehicle.observation_count_by_grid_cell")
    st.subheader("Vehicle Source-Frame Grid")
    grid_rows = _grid_rows(metrics)
    if grid_rows:
        columns = st.columns(2)
        columns[0].metric("Observed grid cells", len(grid_rows))
        columns[1].metric(
            "Coordinate coverage",
            _percentage(grid_count.metadata.get("coverage_fraction") if grid_count else None),
        )
        st.dataframe(grid_rows, hide_index=True, width="stretch")
        if grid_count is not None:
            st.caption(_grid_contract_caption(grid_count))
    else:
        render_metric_unavailable(
            grid_count,
            "a coordinate-frame/grid contract and complete finite vehicle x/y observations",
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
