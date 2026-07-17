"""Traffic observation metric calculators."""

from __future__ import annotations

from datetime import datetime

from traffictwin.canonical.records import TrafficObservationRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.availability import available_metric, unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricValue, RunMetricContext, UnavailableReason
from traffictwin.metrics.statistics import arithmetic_mean, percentile_linear

TRAFFIC_KEYS = [
    "traffic.observation.count",
    "traffic.count.total",
    "traffic.count.mean",
    "traffic.speed.mean_mps",
    "traffic.speed.p50_mps",
    "traffic.speed.p95_mps",
    "traffic.speed.min_mps",
    "traffic.time_coverage",
    "traffic.sensor.count",
]


def traffic_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    """Compute traffic metrics."""

    if evidence.traffic is not EvidenceStatus.AVAILABLE:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
                ["traffic"],
            )
            for key in TRAFFIC_KEYS
        ]

    records = list(tables.traffic)
    if not records:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.NO_VALID_ROWS],
                ["traffic"],
            )
            for key in TRAFFIC_KEYS
        ]

    counts = [record.count for record in records if record.count is not None]
    speeds = [
        record.average_speed_mps for record in records if record.average_speed_mps is not None
    ]
    return [
        available_metric("traffic.observation.count", len(records), context, config, computed_at),
        *_count_metrics(counts, context, config, computed_at),
        *_speed_metrics(speeds, context, config, computed_at),
        available_metric(
            "traffic.time_coverage",
            _time_coverage(records),
            context,
            config,
            computed_at,
            metadata={
                "duration_policy": (
                    "last_timestamp_minus_first_timestamp; no fixed interval inferred"
                )
            },
        ),
        available_metric(
            "traffic.sensor.count",
            len({record.sensor_id for record in records}),
            context,
            config,
            computed_at,
        ),
    ]


def _count_metrics(
    counts: list[int],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    if not counts:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
                ["traffic.count"],
            )
            for key in ("traffic.count.total", "traffic.count.mean")
        ]
    return [
        available_metric("traffic.count.total", sum(counts), context, config, computed_at),
        available_metric(
            "traffic.count.mean",
            arithmetic_mean(counts),
            context,
            config,
            computed_at,
        ),
    ]


def _speed_metrics(
    speeds: list[float],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    if not speeds:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
                ["traffic.average_speed_mps"],
            )
            for key in (
                "traffic.speed.mean_mps",
                "traffic.speed.p50_mps",
                "traffic.speed.p95_mps",
                "traffic.speed.min_mps",
            )
        ]
    return [
        available_metric(
            "traffic.speed.mean_mps",
            arithmetic_mean(speeds),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "traffic.speed.p50_mps",
            percentile_linear(speeds, 0.50),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "traffic.speed.p95_mps",
            percentile_linear(speeds, 0.95),
            context,
            config,
            computed_at,
        ),
        available_metric("traffic.speed.min_mps", min(speeds), context, config, computed_at),
    ]


def _time_coverage(records: list[TrafficObservationRecord]) -> dict[str, float]:
    timestamps = sorted(record.timestamp_s for record in records)
    first = timestamps[0]
    last = timestamps[-1]
    return {
        "first_timestamp_s": first,
        "last_timestamp_s": last,
        "duration_s": last - first,
    }
