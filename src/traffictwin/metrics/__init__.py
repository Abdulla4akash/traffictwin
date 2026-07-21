"""Deterministic metric computation for TrafficTwin."""

from traffictwin.metrics.engine import compute_metrics, compute_metrics_for_bundle
from traffictwin.metrics.plugins import (
    MetricPluginRegistry,
    PluginMetricContract,
    PluginMetricInput,
    PluginMetricResult,
)
from traffictwin.metrics.windowed import (
    MetricWindow,
    PartialWindowPolicy,
    WindowedMetricConfig,
    WindowedMetricSeries,
    compute_windowed_metrics,
    compute_windowed_metrics_for_bundle,
)

__all__ = [
    "MetricWindow",
    "MetricPluginRegistry",
    "PartialWindowPolicy",
    "PluginMetricContract",
    "PluginMetricInput",
    "PluginMetricResult",
    "WindowedMetricConfig",
    "WindowedMetricSeries",
    "compute_metrics",
    "compute_metrics_for_bundle",
    "compute_windowed_metrics",
    "compute_windowed_metrics_for_bundle",
]
