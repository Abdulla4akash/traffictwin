"""Trip metric calculators."""

from __future__ import annotations

from datetime import datetime

from traffictwin.canonical.records import TripRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.availability import available_metric, unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricValue, RunMetricContext, UnavailableReason
from traffictwin.metrics.statistics import arithmetic_mean, percentile_linear

TRIP_KEYS = [
    "trip.records.count",
    "trip.completed.count",
    "trip.incomplete.count",
    "trip.completion.rate",
    "trip.duration.count",
    "trip.duration.mean_s",
    "trip.duration.p50_s",
    "trip.duration.p95_s",
    "trip.duration.min_s",
    "trip.duration.max_s",
]


def trip_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    """Compute trip metrics."""

    if evidence.trips is not EvidenceStatus.AVAILABLE:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
                ["trips"],
            )
            for key in TRIP_KEYS
        ]

    trips = list(tables.trips)
    if not trips:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.NO_VALID_ROWS],
                ["trips"],
            )
            for key in TRIP_KEYS
        ]

    durations = [_duration(trip) for trip in trips]
    valid_durations = [duration for duration in durations if duration is not None]
    completed = sum(1 for trip in trips if _is_completed(trip))
    incomplete = len(trips) - completed
    return [
        available_metric("trip.records.count", len(trips), context, config, computed_at),
        available_metric("trip.completed.count", completed, context, config, computed_at),
        available_metric("trip.incomplete.count", incomplete, context, config, computed_at),
        available_metric(
            "trip.completion.rate", completed / len(trips), context, config, computed_at
        ),
        *_duration_metrics(valid_durations, context, config, computed_at),
    ]


def _duration_metrics(
    durations: list[float],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    if not durations:
        return [
            available_metric("trip.duration.count", 0, context, config, computed_at),
            *[
                unavailable_metric(
                    key,
                    context,
                    config,
                    computed_at,
                    [UnavailableReason.NO_COMPLETED_TRIPS],
                    ["trips.duration_s"],
                )
                for key in (
                    "trip.duration.mean_s",
                    "trip.duration.p50_s",
                    "trip.duration.p95_s",
                    "trip.duration.min_s",
                    "trip.duration.max_s",
                )
            ],
        ]
    return [
        available_metric("trip.duration.count", len(durations), context, config, computed_at),
        available_metric(
            "trip.duration.mean_s",
            arithmetic_mean(durations),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "trip.duration.p50_s",
            percentile_linear(durations, 0.50),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "trip.duration.p95_s",
            percentile_linear(durations, 0.95),
            context,
            config,
            computed_at,
        ),
        available_metric("trip.duration.min_s", min(durations), context, config, computed_at),
        available_metric("trip.duration.max_s", max(durations), context, config, computed_at),
    ]


def _is_completed(trip: TripRecord) -> bool:
    return trip.arrival_time_s is not None or _duration(trip) is not None


def _duration(trip: TripRecord) -> float | None:
    if trip.duration_s is not None:
        return trip.duration_s
    if trip.arrival_time_s is not None:
        return trip.arrival_time_s - trip.departure_time_s
    return None
