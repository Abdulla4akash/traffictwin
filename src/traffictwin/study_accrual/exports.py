"""Deterministic JSON and CSV exports for accrual monitor."""

from __future__ import annotations

import csv
import io
import json

from traffictwin.study_accrual.models import AccrualReport


def export_report_json(report: AccrualReport) -> str:
    """Return deterministic JSON export (portable, wall-clock independent)."""
    data = report.model_dump(mode="json", by_alias=True)
    # Use sorted keys and stable separators for fingerprint parity
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)


def export_report_json_canonical(report: AccrualReport) -> str:
    """Return canonical compact JSON for fingerprint verification."""
    data = report.canonical_payload()
    # Include fingerprint separately for verification but canonical payload excludes it
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def export_cells_csv(report: AccrualReport) -> str:
    """Return tabular CSV for planned-versus-current matrix.

    One row per cell. Missing values are empty, not zero-filled.
    """
    output = io.StringIO()
    fieldnames = [
        "cell_id",
        "arm_id",
        "seed_id",
        "policy_label",
        "replication_id",
        "metric_key",
        "metric_version",
        "replication_unit",
        "attachment_state",
        "admission_state",
        "compatibility",
        "first_observed_time",
        "latest_decision",
        "status",
        "deviation_reason",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for cell in sorted(report.cells, key=lambda c: c.cell_id):
        writer.writerow(
            {
                "cell_id": cell.cell_id,
                "arm_id": cell.arm_id or "",
                "seed_id": cell.seed_id or "",
                "policy_label": cell.policy_label or "",
                "replication_id": "" if cell.replication_id is None else str(cell.replication_id),
                "metric_key": cell.metric_key or "",
                "metric_version": cell.metric_version or "",
                "replication_unit": cell.replication_unit or "",
                "attachment_state": cell.attachment_state,
                "admission_state": cell.admission_state,
                "compatibility": cell.compatibility,
                "first_observed_time": cell.first_observed_time or "",
                "latest_decision": cell.latest_decision or "",
                "status": cell.status.value,
                "deviation_reason": cell.deviation_reason or "",
            }
        )
    return output.getvalue()


def export_deviations_csv(report: AccrualReport) -> str:
    """Return CSV for deviations."""
    output = io.StringIO()
    fieldnames = ["code", "cell_id", "message"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for dev in sorted(report.deviations, key=lambda d: (d.code.value, d.cell_id or "")):
        writer.writerow(
            {
                "code": dev.code.value,
                "cell_id": dev.cell_id or "",
                "message": dev.message,
            }
        )
    return output.getvalue()
