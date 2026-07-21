"""Infrastructure metric calculators."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from traffictwin.canonical.records import InfrastructureRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.availability import available_metric, unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import JsonObject, MetricValue, RunMetricContext, UnavailableReason
from traffictwin.metrics.statistics import arithmetic_mean, percentile_linear

INFRASTRUCTURE_KEYS = [
    "infra.rsu.summary",
    "infra.observed_rsu.count",
    "infra.queue_length.mean",
    "infra.queue_length.max",
    "infra.utilisation.mean",
    "infra.utilisation.p95",
    "infra.saturation.episode_count",
    "infra.saturation.duration_s",
]


def infrastructure_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    """Compute infrastructure metrics."""

    if evidence.infrastructure is not EvidenceStatus.AVAILABLE:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
                ["infrastructure"],
            )
            for key in INFRASTRUCTURE_KEYS
        ]

    records = list(tables.infrastructure)
    if not records:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.NO_VALID_ROWS],
                ["infrastructure"],
            )
            for key in INFRASTRUCTURE_KEYS
        ]

    queue_values = [record.queue_length for record in records if record.queue_length is not None]
    utilisation_values = [
        record.utilisation_fraction for record in records if record.utilisation_fraction is not None
    ]
    results = [
        available_metric("infra.rsu.summary", _rsu_summary(records), context, config, computed_at),
        available_metric(
            "infra.observed_rsu.count",
            len({record.rsu_id for record in records}),
            context,
            config,
            computed_at,
        ),
        *_queue_metrics(queue_values, context, config, computed_at),
        *_utilisation_metrics(utilisation_values, context, config, computed_at),
        *_saturation_metrics(records, context, config, computed_at),
    ]
    return results


def _rsu_summary(records: list[InfrastructureRecord]) -> JsonObject:
    grouped: dict[str, list[InfrastructureRecord]] = defaultdict(list)
    for record in records:
        grouped[record.rsu_id].append(record)

    summary: JsonObject = {}
    for rsu_id in sorted(grouped):
        rsu_records = grouped[rsu_id]
        queues = [record.queue_length for record in rsu_records if record.queue_length is not None]
        utilisations = [
            record.utilisation_fraction
            for record in rsu_records
            if record.utilisation_fraction is not None
        ]
        arrivals = [record.arrivals for record in rsu_records if record.arrivals is not None]
        drops = [record.drops for record in rsu_records if record.drops is not None]
        active = [record.active_tasks for record in rsu_records if record.active_tasks is not None]
        summary[rsu_id] = {
            "observation_count": len(rsu_records),
            "queue_length_mean": arithmetic_mean(queues) if queues else None,
            "queue_length_max": max(queues) if queues else None,
            "utilisation_mean": arithmetic_mean(utilisations) if utilisations else None,
            "utilisation_p95": percentile_linear(utilisations, 0.95) if utilisations else None,
            "arrivals_total": sum(arrivals) if arrivals else None,
            "drops_total": sum(drops) if drops else None,
            "active_tasks_mean": arithmetic_mean(active) if active else None,
        }
    return summary


def _queue_metrics(
    queue_values: list[float],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    if not queue_values:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
                ["infrastructure.queue_length"],
            )
            for key in ("infra.queue_length.mean", "infra.queue_length.max")
        ]
    return [
        available_metric(
            "infra.queue_length.mean",
            arithmetic_mean(queue_values),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "infra.queue_length.max",
            max(queue_values),
            context,
            config,
            computed_at,
        ),
    ]


def _utilisation_metrics(
    utilisation_values: list[float],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    if not utilisation_values:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
                ["infrastructure.utilisation_fraction"],
            )
            for key in ("infra.utilisation.mean", "infra.utilisation.p95")
        ]
    return [
        available_metric(
            "infra.utilisation.mean",
            arithmetic_mean(utilisation_values),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "infra.utilisation.p95",
            percentile_linear(utilisation_values, 0.95),
            context,
            config,
            computed_at,
        ),
    ]


def _saturation_metrics(
    records: list[InfrastructureRecord],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    usable = [record for record in records if record.utilisation_fraction is not None]
    if not usable:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
                ["infrastructure.utilisation_fraction"],
            )
            for key in ("infra.saturation.episode_count", "infra.saturation.duration_s")
        ]

    episode_count = 0
    duration_s = 0.0
    grouped: dict[str, list[InfrastructureRecord]] = defaultdict(list)
    for record in usable:
        grouped[record.rsu_id].append(record)

    for rsu_records in grouped.values():
        ordered = sorted(rsu_records, key=lambda item: item.timestamp_s)
        in_episode = False
        for index, record in enumerate(ordered):
            saturated = record.utilisation_fraction is not None and (
                record.utilisation_fraction >= config.saturation_threshold
            )
            if saturated and not in_episode:
                episode_count += 1
                in_episode = True
            if not saturated:
                in_episode = False
                continue
            if index + 1 >= len(ordered):
                continue
            next_timestamp = ordered[index + 1].timestamp_s
            gap = next_timestamp - record.timestamp_s
            if gap < 0:
                continue
            if config.saturation_max_gap_s is not None and gap > config.saturation_max_gap_s:
                in_episode = False
                continue
            duration_s += gap

    metadata: JsonObject = {
        "saturation_threshold": config.saturation_threshold,
        "saturation_max_gap_s": config.saturation_max_gap_s,
    }
    return [
        available_metric(
            "infra.saturation.episode_count",
            episode_count,
            context,
            config,
            computed_at,
            metadata=metadata,
        ),
        available_metric(
            "infra.saturation.duration_s",
            duration_s,
            context,
            config,
            computed_at,
            metadata=metadata,
        ),
    ]
