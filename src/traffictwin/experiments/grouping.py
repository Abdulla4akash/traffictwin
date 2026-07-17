"""Small grouping helpers for experiment metric collections."""

from __future__ import annotations

from collections import defaultdict

from traffictwin.metrics.results import MetricCollection


def group_by_seed(collections: list[MetricCollection]) -> dict[str, list[MetricCollection]]:
    """Group metric collections by seed ID."""

    grouped: dict[str, list[MetricCollection]] = defaultdict(list)
    for collection in collections:
        if collection.results:
            grouped[collection.results[0].seed_id].append(collection)
    return dict(sorted(grouped.items()))
