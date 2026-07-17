"""Chart data preparation and Plotly figure builders."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import cast

import plotly.graph_objects as go

from traffictwin.canonical.tables import CanonicalTables
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


def task_event_series(tables: CanonicalTables) -> list[dict[str, object]]:
    """Return task arrival/completion events over time."""

    grouped: dict[float, Counter[str]] = defaultdict(Counter)
    for task in tables.tasks:
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
