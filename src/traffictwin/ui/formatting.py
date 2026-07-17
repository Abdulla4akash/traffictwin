"""Formatting helpers for Streamlit views."""

from __future__ import annotations

from traffictwin.config.capabilities import CapabilitySupport
from traffictwin.metrics.results import MetricStatus, MetricValue
from traffictwin.validation.report import ImportStatus


def capability_label(value: CapabilitySupport) -> str:
    """Return the visible capability label."""

    labels = {
        CapabilitySupport.TRUE: "Supported",
        CapabilitySupport.FALSE: "Unsupported",
        CapabilitySupport.UNKNOWN: "Unknown",
    }
    return labels[value]


def validation_label(status: ImportStatus | str) -> str:
    """Return visible validation status text."""

    value = status.value if isinstance(status, ImportStatus) else status
    return value.replace("_", " ").upper()


def metric_status_label(status: MetricStatus | str) -> str:
    """Return visible metric status text."""

    value = status.value if isinstance(status, MetricStatus) else status
    return value.upper()


def format_number(value: object, *, digits: int = 3) -> str:
    """Format a scalar number without hiding zero."""

    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def format_ratio(value: object) -> str:
    """Format a ratio as a percentage."""

    if value is None:
        return "Unavailable"
    if not isinstance(value, int | float) or isinstance(value, bool):
        return str(value)
    return f"{value * 100:.1f}%"


def format_metric_value(metric: MetricValue | None) -> str:
    """Format a metric value while preserving unavailable states."""

    if metric is None:
        return "Unavailable"
    if metric.status is not MetricStatus.AVAILABLE:
        return "Unavailable"
    if metric.unit == "ratio":
        return format_ratio(metric.value)
    return format_number(metric.value)


def format_metric_detail(metric: MetricValue | None) -> str:
    """Return a compact detail string with units or reason codes."""

    if metric is None:
        return "Metric not present"
    if metric.status is MetricStatus.AVAILABLE:
        return metric.unit
    reasons = ", ".join(reason.value for reason in metric.reason_codes)
    return reasons or metric.status.value
