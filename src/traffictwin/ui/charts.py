"""Chart data preparation and Plotly figure builders."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import cast

import plotly.graph_objects as go

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.diagnostics.threshold_sweep import ThresholdSensitivityReport
from traffictwin.metrics.results import MetricCollection, MetricStatus


def traffic_series(tables: CanonicalTables) -> list[dict[str, object]]:
    """Return traffic observation chart rows."""

    return [
        {
            "timestamp_s": record.timestamp_s,
            "sensor_id": record.sensor_id,
            "count": record.count,
            "average_speed_mps": record.average_speed_mps,
        }
        for record in sorted(tables.traffic, key=lambda item: (item.sensor_id, item.timestamp_s))
    ]


def infrastructure_series(
    tables: CanonicalTables, rsu_id: str | None = None
) -> list[dict[str, object]]:
    """Return infrastructure chart rows."""

    records = tables.infrastructure
    if rsu_id:
        records = [record for record in records if record.rsu_id == rsu_id]
    return [
        {
            "timestamp_s": record.timestamp_s,
            "rsu_id": record.rsu_id,
            "queue_length": record.queue_length,
            "utilisation_fraction": record.utilisation_fraction,
            "active_tasks": record.active_tasks,
            "arrivals": record.arrivals,
            "drops": record.drops,
        }
        for record in sorted(records, key=lambda item: (item.rsu_id, item.timestamp_s))
    ]


def task_event_series(
    tables: CanonicalTables,
    *,
    vehicle_id: str | None = None,
    task_class: str | None = None,
) -> list[dict[str, object]]:
    """Return filtered task arrival/completion events over time."""

    grouped: dict[float, Counter[str]] = defaultdict(Counter)
    for task in tables.tasks:
        if vehicle_id is not None and task.vehicle_id != vehicle_id:
            continue
        if task_class is not None and task.task_class.value != task_class:
            continue
        grouped[task.arrival_time_s]["arrivals"] += 1
        if task.completion_time_s is not None:
            grouped[task.completion_time_s]["completions"] += 1
    return [
        {
            "timestamp_s": timestamp,
            "arrivals": counts["arrivals"],
            "completions": counts["completions"],
        }
        for timestamp, counts in sorted(grouped.items())
    ]


def trip_duration_rows(tables: CanonicalTables) -> list[dict[str, object]]:
    """Return trip duration rows using accepted canonical trip records."""

    rows: list[dict[str, object]] = []
    for trip in tables.trips:
        duration = trip.duration_s
        if duration is None and trip.arrival_time_s is not None:
            duration = trip.arrival_time_s - trip.departure_time_s
        if duration is not None:
            rows.append(
                {
                    "trip_id": trip.trip_id,
                    "vehicle_id": trip.vehicle_id,
                    "duration_s": duration,
                    "route_id": trip.route_id,
                }
            )
    return rows


def metric_status_counts(collection: MetricCollection | None) -> dict[str, int]:
    """Return metric counts by status."""

    if collection is None:
        return {}
    counts = Counter(metric.status.value for metric in collection.results)
    return dict(sorted(counts.items()))


def metric_value_by_key(collection: MetricCollection | None, key: str) -> object | None:
    """Return an available metric value by key."""

    if collection is None:
        return None
    metric = collection.by_key().get(key)
    if metric is None or metric.status is not MetricStatus.AVAILABLE:
        return None
    return cast(object, metric.value)


def corridor_snapshot_rows(
    tables: CanonicalTables,
    timestamp_s: float,
    *,
    vehicle_id: str | None = None,
) -> list[dict[str, object]]:
    """Return coordinate-bearing vehicle history up to one replay timestamp."""

    rows: list[dict[str, object]] = [
        {
            "timestamp_s": record.timestamp_s,
            "vehicle_id": record.vehicle_id,
            "x": record.x,
            "y": record.y,
            "speed_mps": record.speed_mps,
            "lane": record.lane,
            "tier": record.tier,
        }
        for record in tables.vehicles
        if record.timestamp_s <= timestamp_s
        and record.x is not None
        and record.y is not None
        and (vehicle_id is None or record.vehicle_id == vehicle_id)
    ]
    return sorted(
        rows,
        key=lambda row: (str(row["vehicle_id"]), cast(float, row["timestamp_s"])),
    )


def corridor_figure(
    tables: CanonicalTables,
    timestamp_s: float,
    *,
    vehicle_id: str | None = None,
    incident_type: str | None = None,
) -> go.Figure | None:
    """Build a non-geographic coordinate-plane replay for synthetic/source vehicle positions."""

    rows = corridor_snapshot_rows(tables, timestamp_s, vehicle_id=vehicle_id)
    if not rows:
        return None
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["vehicle_id"])].append(row)
    figure = go.Figure()
    for identifier, history in sorted(grouped.items()):
        figure.add_trace(
            go.Scatter(
                x=[row["x"] for row in history],
                y=[row["y"] for row in history],
                mode="lines",
                line={"width": 1.5},
                name=f"{identifier} path",
                legendgroup=identifier,
                showlegend=False,
                hoverinfo="skip",
            )
        )
        current = history[-1]
        figure.add_trace(
            go.Scatter(
                x=[current["x"]],
                y=[current["y"]],
                mode="markers+text",
                marker={"size": 11},
                text=[identifier],
                textposition="top center",
                name=identifier,
                legendgroup=identifier,
                showlegend=False,
                customdata=[
                    [current["timestamp_s"], current["speed_mps"], current["lane"], current["tier"]]
                ],
                hovertemplate=(
                    "%{text}<br>x=%{x}<br>y=%{y}<br>time=%{customdata[0]} s"
                    "<br>speed=%{customdata[1]} m/s<br>lane=%{customdata[2]}"
                    "<br>tier=%{customdata[3]}<extra></extra>"
                ),
            )
        )
    active_incidents = [
        incident
        for incident in tables.incidents
        if incident.timestamp_s <= timestamp_s
        and (incident_type is None or incident.incident_type == incident_type)
        and (
            incident.duration_s is None or timestamp_s <= incident.timestamp_s + incident.duration_s
        )
    ]
    if active_incidents:
        labels = ", ".join(
            f"{incident.incident_type} ({incident.location or 'location unavailable'})"
            for incident in active_incidents
        )
        figure.add_annotation(
            x=0.01,
            y=0.99,
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="top",
            text=f"Active incident metadata: {labels}",
            showarrow=False,
            bgcolor="rgba(255,247,230,0.9)",
        )
    figure.update_layout(
        title=f"Vehicle coordinate replay at {timestamp_s:.1f} s",
        xaxis_title="Source x coordinate (non-geographic)",
        yaxis_title="Source y coordinate (non-geographic)",
    )
    figure.update_yaxes(scaleanchor="x", scaleratio=1)
    return figure


def line_figure(
    rows: list[dict[str, object]],
    *,
    x_key: str,
    y_keys: list[str],
    title: str,
    y_title: str,
) -> go.Figure:
    """Build a simple time-series figure."""

    figure = go.Figure()
    x_values = [row[x_key] for row in rows]
    for y_key in y_keys:
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=[row[y_key] for row in rows],
                mode="lines+markers",
                name=y_key.replace("_", " "),
                hovertemplate=f"%{{x}} s<br>{y_key}: %{{y}}<extra></extra>",
            )
        )
    figure.update_layout(title=title, xaxis_title="Simulation time (s)", yaxis_title=y_title)
    return figure


def bar_figure(
    labels: list[str],
    values: list[float | int],
    *,
    title: str,
    y_title: str,
) -> go.Figure:
    """Build a neutral bar chart."""

    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=values,
                hovertemplate="%{x}: %{y}<extra></extra>",
            )
        ]
    )
    figure.update_layout(title=title, xaxis_title="", yaxis_title=y_title)
    return figure


def threshold_sweep_figure(report: ThresholdSensitivityReport) -> go.Figure:
    """Render every DIA-06 point and sampled transition interval without value judgement."""

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[point.threshold for point in report.points],
            y=[point.status.value for point in report.points],
            mode="lines+markers",
            line={"color": "#546e7a", "width": 2},
            marker={"color": "#546e7a", "size": 9},
            customdata=[
                [point.ordinal, point.triggered, point.is_source_threshold]
                for point in report.points
            ],
            hovertemplate=(
                "threshold=%{x}<br>status=%{y}<br>ordinal=%{customdata[0]}"
                "<br>triggered=%{customdata[1]}<br>source threshold=%{customdata[2]}"
                "<extra></extra>"
            ),
            name="ordinary rule status",
        )
    )
    if report.source_threshold is not None:
        figure.add_vline(
            x=report.source_threshold,
            line_dash="dash",
            line_color="#37474f",
            annotation_text="source threshold",
            annotation_position="top",
        )
    for boundary in report.flip_boundaries:
        figure.add_vrect(
            x0=boundary.lower_threshold,
            x1=boundary.upper_threshold,
            fillcolor="#b0bec5",
            opacity=0.22,
            line_width=0,
            annotation_text="sampled flip interval",
            annotation_position="bottom left",
        )
    figure.update_layout(
        title=f"{report.rule_id} status across the complete evaluated threshold grid",
        xaxis_title=f"{report.parameter_path} ({report.threshold_unit})",
        yaxis_title="Ordinary rule status",
        showlegend=False,
    )
    return figure
