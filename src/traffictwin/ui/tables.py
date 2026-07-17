"""Tabular view-model helpers."""

from __future__ import annotations

from traffictwin.config.capabilities import CapabilityManifest
from traffictwin.metrics.comparison import ComparisonReport
from traffictwin.metrics.results import MetricCollection, MetricValue
from traffictwin.ui.formatting import (
    capability_label,
    format_metric_value,
    metric_status_label,
    validation_label,
)
from traffictwin.validation.report import ValidationReport


def capability_rows(manifest: CapabilityManifest) -> list[dict[str, str]]:
    """Return capability rows for display."""

    return [
        {"capability": key, "status": capability_label(value)} for key, value in manifest.supports
    ]


def validation_finding_rows(report: ValidationReport) -> list[dict[str, object]]:
    """Return validation finding rows."""

    return [
        {
            "severity": finding.severity.value,
            "code": finding.code.value,
            "file": finding.file,
            "row": finding.row,
            "field": finding.field,
            "message": finding.message,
            "may_continue": finding.may_continue,
            "affected_capabilities": ", ".join(finding.affected_capabilities),
        }
        for finding in report.findings
    ]


def metric_rows(
    collection: MetricCollection | None, keys: list[str] | None = None
) -> list[dict[str, object]]:
    """Return metric rows with unavailable values preserved."""

    if collection is None:
        return []
    selected = set(keys) if keys is not None else None
    rows = []
    for metric in collection.results:
        if selected is not None and metric.metric_key not in selected:
            continue
        rows.append(_metric_row(metric))
    return rows


def comparison_rows(report: ComparisonReport) -> list[dict[str, object]]:
    """Return comparison rows."""

    rows: list[dict[str, object]] = []
    for comparison in [*report.comparable_metrics, *report.unavailable_comparisons]:
        rows.append(
            {
                "metric_key": comparison.metric_key,
                "status": comparison.status.value,
                "baseline": _display(comparison.baseline),
                "variation": _display(comparison.variation),
                "absolute_delta": _display(comparison.absolute_delta),
                "relative_delta": _display(comparison.relative_delta),
                "direction": comparison.direction.value,
                "reason_codes": ", ".join(reason.value for reason in comparison.reason_codes),
            }
        )
    return sorted(rows, key=lambda row: str(row["metric_key"]))


def validation_summary_rows(report: ValidationReport) -> list[dict[str, object]]:
    """Return validation summary rows."""

    return [
        {"field": "status", "value": validation_label(report.status)},
        {"field": "may_import", "value": str(report.may_import)},
        {"field": "errors", "value": str(report.counts_by_severity.get("error", 0))},
        {"field": "warnings", "value": str(report.counts_by_severity.get("warning", 0))},
        {"field": "fatal", "value": str(report.counts_by_severity.get("fatal", 0))},
    ]


def _metric_row(metric: MetricValue) -> dict[str, object]:
    return {
        "metric_key": metric.metric_key,
        "status": metric_status_label(metric.status),
        "value": format_metric_value(metric),
        "unit": metric.unit,
        "reason_codes": ", ".join(reason.value for reason in metric.reason_codes),
    }


def _display(value: object) -> str:
    if value is None:
        return "Unavailable"
    return str(value)
