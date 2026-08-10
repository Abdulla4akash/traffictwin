"""Typed view-model helper for Consequence Lenses tables."""

from __future__ import annotations

from traffictwin.ui.consequence_lenses import ConsequenceLensReport
from traffictwin.ui.formatting import format_scalar


def consequence_lens_table_rows(
    report: ConsequenceLensReport, domain: str
) -> list[dict[str, object]]:
    """Return typed row dicts for a consequence domain.

    Feature-specific helper: imports the typed Consequence model statically
    and delegates scalar formatting to the single authoritative
    ``ui.formatting.format_scalar`` contract.
    """

    summary = report.traffic_summary if domain == "traffic" else report.vec_summary
    rows: list[dict[str, object]] = []
    for row in summary.rows:
        rows.append(
            {
                "metric_key": row.metric_key,
                "label": row.label,
                "status": row.status,
                "baseline": format_scalar(row.baseline),
                "variation": format_scalar(row.variation),
                "absolute_delta": format_scalar(row.absolute_delta),
                "relative_delta": format_scalar(row.relative_delta),
                "unit": row.unit or "",
                "direction": row.direction,
                "reason_codes": ", ".join(row.reason_codes),
                "denominator": row.denominator_description or "",
            }
        )
    return rows
