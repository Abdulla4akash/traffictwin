"""Cross-file reconciliation checks."""

from __future__ import annotations

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.findings import Severity, ValidationFinding
from traffictwin.validation.report import ValidationReport


def reconcile_tables(tables: CanonicalTables, report: ValidationReport) -> None:
    """Run lightweight cross-file reconciliation checks."""

    vehicle_ids = {record.vehicle_id for record in tables.vehicles}
    rsu_ids = {record.rsu_id for record in tables.infrastructure}

    if vehicle_ids:
        for task in tables.tasks:
            if task.vehicle_id not in vehicle_ids:
                report.add(
                    ValidationFinding(
                        code=ValidationCode.UNKNOWN_VEHICLE_REFERENCE,
                        severity=Severity.WARNING,
                        message="task vehicle_id is not present in vehicle_state records",
                        file=task.source_file,
                        row=task.source_row,
                        field="vehicle_id",
                        value=task.vehicle_id,
                        may_continue=True,
                        affected_capabilities=["vehicle_task_reconciliation"],
                    )
                )

    if rsu_ids:
        for task in tables.tasks:
            if task.decision is Decision.V2I and task.target_id and task.target_id not in rsu_ids:
                report.add(
                    ValidationFinding(
                        code=ValidationCode.UNKNOWN_RSU_REFERENCE,
                        severity=Severity.WARNING,
                        message="v2i task target_id is not present in infra_state records",
                        file=task.source_file,
                        row=task.source_row,
                        field="target_id",
                        value=task.target_id,
                        may_continue=True,
                        affected_capabilities=["infrastructure_task_reconciliation"],
                    )
                )
