"""Tabular view-model helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import streamlit as st

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

# Machine-identifier columns hidden from primary tables by default. Hiding is
# presentation only: the values remain in the row data and stay reachable
# through Advanced/Evidence views. Sensitive columns must still be removed
# before render (design v0.7 §13.3); hiding a column is not a security
# control.
MACHINE_ID_COLUMNS: frozenset[str] = frozenset(
    {
        "bundle_fingerprint",
        "experiment_id",
        "fingerprint",
        "metric_version",
        "node_id",
        "random_seed",
        "run_id",
        "schema_version",
        "seed_id",
        "snapshot_id",
        "source_fingerprint",
        "trace_id",
    }
)

# Human labels for the machine column keys produced by the row helpers in
# this module and by component tables. Unknown keys fall back to sentence
# casing.
COLUMN_LABELS: dict[str, str] = {
    "absolute_delta": "Absolute delta",
    "affected_capabilities": "Affected capabilities",
    "baseline": "Baseline",
    "capability": "Capability",
    "category": "Category",
    "code": "Finding code",
    "confidence": "Confidence",
    "count": "Count",
    "description": "Description",
    "direction": "Direction",
    "field": "Field",
    "file": "File",
    "label": "Label",
    "may_continue": "May continue",
    "message": "Message",
    "metric_key": "Metric",
    "node_type": "Node type",
    "reason": "Reasons",
    "reason_codes": "Reason codes",
    "relation": "Relation",
    "relative_delta": "Relative delta",
    "row": "Row",
    "severity": "Severity",
    "source": "Source",
    "status": "Status",
    "target": "Target",
    "unit": "Unit",
    "value": "Value",
    "variation": "Variation",
}


@dataclass(frozen=True)
class ColumnDisplay:
    """Presentation metadata for one table column.

    This describes how a value is labelled and formatted; it never changes
    the underlying value.
    """

    key: str
    label: str
    hidden: bool = False
    unit: str | None = None
    number_format: str | None = None
    help_text: str | None = None


def display_label(key: str) -> str:
    """Return the human label for a column key."""

    if key in COLUMN_LABELS:
        return COLUMN_LABELS[key]
    return key.replace("_", " ").strip().capitalize()


def column_display(
    key: str,
    *,
    unit: str | None = None,
    number_format: str | None = None,
    help_text: str | None = None,
    hide_machine_ids: bool = True,
) -> ColumnDisplay:
    """Return default presentation metadata for one column key."""

    hidden = hide_machine_ids and (key in MACHINE_ID_COLUMNS or key.endswith("_id"))
    label = display_label(key)
    if unit is not None:
        label = f"{label} ({unit})"
    return ColumnDisplay(
        key=key,
        label=label,
        hidden=hidden,
        unit=unit,
        number_format=number_format,
        help_text=help_text,
    )


def table_column_config(
    rows: Sequence[Mapping[str, object]],
    *,
    units: Mapping[str, str] | None = None,
    number_formats: Mapping[str, str] | None = None,
    hide_machine_ids: bool = True,
    overrides: Mapping[str, ColumnDisplay] | None = None,
) -> dict[str, object]:
    """Return ``st.dataframe`` ``column_config`` metadata for row dicts.

    ``units`` appends a unit to the column label; ``number_formats`` applies a
    display format such as ``"%.3f"`` or ``"percent"``. Hidden machine-ID
    columns map to ``None``. Values in ``rows`` are never modified.
    """

    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    config: dict[str, object] = {}
    for key in keys:
        if overrides is not None and key in overrides:
            spec = overrides[key]
        else:
            spec = column_display(
                key,
                unit=None if units is None else units.get(key),
                number_format=None if number_formats is None else number_formats.get(key),
                hide_machine_ids=hide_machine_ids,
            )
        if spec.hidden:
            config[key] = None
        elif spec.number_format is not None:
            config[key] = st.column_config.NumberColumn(
                spec.label, format=spec.number_format, help=spec.help_text
            )
        else:
            config[key] = st.column_config.TextColumn(spec.label, help=spec.help_text)
    return config


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


def _format_consequence_value(value: object) -> str:
    """Lossless rendering for consequence values — preserves numeric fidelity."""

    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN
            return "NaN"
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
        return repr(value)
    return str(value)


def consequence_lens_table_rows(report: object, domain: str) -> list[dict[str, object]]:
    """Shared view-model helper for consequence lenses.

    Typed as ``object`` to avoid circular import; expects a
    ``ConsequenceLensReport`` with ``traffic_summary``/``vec_summary``.
    Preserves lossless numeric formatting and all lens-specific fields.
    """

    # Local import to avoid circular dependency
    from traffictwin.ui.consequence_lenses import ConsequenceLensReport as _Report  # noqa: PLC0415

    if not isinstance(report, _Report):
        raise TypeError("report must be a ConsequenceLensReport")
    summary = report.traffic_summary if domain == "traffic" else report.vec_summary
    rows: list[dict[str, object]] = []
    for row in summary.rows:
        rows.append(
            {
                "metric_key": row.metric_key,
                "label": row.label,
                "status": row.status,
                "baseline": _format_consequence_value(row.baseline),
                "variation": _format_consequence_value(row.variation),
                "absolute_delta": _format_consequence_value(row.absolute_delta),
                "relative_delta": _format_consequence_value(row.relative_delta),
                "unit": row.unit or "",
                "direction": row.direction,
                "reason_codes": ", ".join(row.reason_codes),
                "denominator": row.denominator_description or "",
            }
        )
    return rows
