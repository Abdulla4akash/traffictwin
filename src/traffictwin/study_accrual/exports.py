"""Deterministic JSON and CSV exports for accrual monitor."""

from __future__ import annotations

import csv
import io
import json

from traffictwin.data_contract.fingerprint import sanitise_for_csv
from traffictwin.study_accrual.models import AccrualReport


def export_report_json(report: AccrualReport) -> str:
    """Return deterministic JSON export (portable, semantic timestamps preserved).

    Runtime generation clock is excluded from fingerprint; declared evidence/amendment
    timestamps are semantic and ARE included.
    """
    data = report.model_dump(mode="json", by_alias=True)
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)


def export_report_json_canonical(report: AccrualReport) -> str:
    """Return canonical compact JSON for fingerprint verification."""
    data = report.canonical_payload()
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _sanitise(value: str) -> str:
    return sanitise_for_csv(value)


def export_cells_csv(report: AccrualReport) -> str:
    """Return tabular CSV for planned-versus-current matrix with formula protection.

    One row per cell. Missing values are empty, not zero-filled.
    Textual cells are sanitized via repository helper.
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
                "cell_id": _sanitise(cell.cell_id),
                "arm_id": _sanitise(cell.arm_id or ""),
                "seed_id": _sanitise(cell.seed_id or ""),
                "policy_label": _sanitise(cell.policy_label or ""),
                "replication_id": "" if cell.replication_id is None else str(cell.replication_id),
                "metric_key": _sanitise(cell.metric_key or ""),
                "metric_version": _sanitise(cell.metric_version or ""),
                "replication_unit": _sanitise(cell.replication_unit or ""),
                "attachment_state": _sanitise(cell.attachment_state),
                "admission_state": _sanitise(cell.admission_state),
                "compatibility": _sanitise(cell.compatibility),
                "first_observed_time": _sanitise(cell.first_observed_time or ""),
                "latest_decision": _sanitise(cell.latest_decision or ""),
                "status": _sanitise(cell.status.value),
                "deviation_reason": _sanitise(cell.deviation_reason or ""),
            }
        )
    return output.getvalue()


def export_deviations_csv(report: AccrualReport) -> str:
    """Return CSV for deviations with formula protection."""
    output = io.StringIO()
    fieldnames = ["code", "cell_id", "message"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for dev in sorted(report.deviations, key=lambda d: (d.code.value, d.cell_id or "")):
        writer.writerow(
            {
                "code": _sanitise(dev.code.value),
                "cell_id": _sanitise(dev.cell_id or ""),
                "message": _sanitise(dev.message),
            }
        )
    return output.getvalue()
