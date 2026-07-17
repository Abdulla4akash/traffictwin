"""Manifest-driven generic CSV adapter."""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import ValidationError

from traffictwin.canonical.records import (
    IncidentRecord,
    InfrastructureRecord,
    TaskRecord,
    TrafficObservationRecord,
    TripRecord,
    VehicleStateRecord,
)
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.ingestion.manifest import BundleManifest, FileDeclaration
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.findings import Severity, ValidationFinding
from traffictwin.validation.report import ValidationReport

SUPPORTED_FIELDS: dict[str, set[str]] = {
    "tasks": {
        "task_id",
        "vehicle_id",
        "task_class",
        "arrival_time",
        "deadline_ms",
        "decision",
        "completed",
        "completion_time",
        "latency_ms",
        "target_id",
        "workload_cycles",
        "data_size_bytes",
        "energy_j",
        "drop_reason",
    },
    "infra_state": {
        "timestamp",
        "rsu_id",
        "queue_length",
        "utilisation",
        "arrivals",
        "active_tasks",
        "drops",
        "capacity",
    },
    "vehicle_state": {"timestamp", "vehicle_id", "x", "y", "speed", "lane", "tier"},
    "traffic_obs": {"timestamp", "sensor_id", "count", "average_speed", "location"},
    "trips": {
        "trip_id",
        "vehicle_id",
        "departure_time",
        "arrival_time",
        "duration",
        "route_id",
    },
    "incidents": {"incident_id", "timestamp", "incident_type", "location", "severity"},
}

UNIT_DIMENSIONS: dict[str, str] = {
    "arrival_time": "time_s",
    "completion_time": "time_s",
    "timestamp": "time_s",
    "departure_time": "time_s",
    "duration": "time_s",
    "deadline_ms": "duration_ms",
    "latency_ms": "duration_ms",
    "speed": "speed_mps",
    "average_speed": "speed_mps",
    "data_size_bytes": "bytes",
    "energy_j": "joules",
    "workload_cycles": "cycles",
    "utilisation": "fraction",
}

FIELD_CAPABILITIES: dict[str, list[str]] = {
    "tasks": ["task_metrics", "offload_decision_analysis"],
    "infra_state": ["infrastructure_utilisation_metrics", "infrastructure_bottleneck_diagnosis"],
    "vehicle_state": ["vehicle_state_analysis"],
    "traffic_obs": ["traffic_observation_metrics"],
    "trips": ["journey_time_metrics"],
    "incidents": ["incident_context"],
}


class GenericCsvAdapter:
    """CSV adapter driven entirely by manifest declarations."""

    def canonicalise(
        self,
        root: Path,
        manifest: BundleManifest,
        report: ValidationReport,
    ) -> CanonicalTables:
        """Read declared CSV files and return canonical records."""

        tables = CanonicalTables()
        for kind, declaration in manifest.files.items():
            path = root / declaration.path
            if not path.exists():
                continue
            report.files_inspected.append(declaration.path)
            rows = self._read_rows(kind, path, declaration, report)
            if rows is None:
                continue
            if kind == "tasks":
                tables.tasks.extend(self._tasks(rows, declaration, report))
            elif kind == "infra_state":
                tables.infrastructure.extend(self._infrastructure(rows, declaration, report))
            elif kind == "vehicle_state":
                tables.vehicles.extend(self._vehicles(rows, declaration, report))
            elif kind == "traffic_obs":
                tables.traffic.extend(self._traffic(rows, declaration, report))
            elif kind == "trips":
                tables.trips.extend(self._trips(rows, declaration, report))
            elif kind == "incidents":
                tables.incidents.extend(self._incidents(rows, declaration, report))
        self._validate_duplicate_task_ids(tables.tasks, report)
        return tables

    def _read_rows(
        self,
        kind: str,
        path: Path,
        declaration: FileDeclaration,
        report: ValidationReport,
    ) -> list[dict[str, str]] | None:
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
                if not self._validate_columns(
                    kind, declaration.path, declaration, fieldnames, report
                ):
                    return None
                return [dict(row) for row in reader]
        except OSError as exc:
            report.add(
                self._finding(
                    ValidationCode.FILE_UNREADABLE,
                    Severity.FATAL,
                    f"could not read CSV file: {exc}",
                    file=path.name,
                    may_continue=False,
                )
            )
            return None

    def _validate_columns(
        self,
        kind: str,
        filename: str,
        declaration: FileDeclaration,
        fieldnames: Sequence[str],
        report: ValidationReport,
    ) -> bool:
        ok = True
        required_source_columns = [
            declaration.source_column_for(column) for column in declaration.required_columns
        ]
        for column in required_source_columns:
            if column not in fieldnames:
                report.add(
                    self._finding(
                        ValidationCode.REQUIRED_COLUMN_MISSING,
                        Severity.ERROR,
                        f"required column is missing: {column}",
                        file=filename,
                        field=column,
                        may_continue=False,
                    )
                )
                ok = False
        supported = SUPPORTED_FIELDS[kind]
        known_source_columns = {declaration.source_column_for(field) for field in supported}
        for column in fieldnames:
            if column not in known_source_columns:
                report.add(
                    self._finding(
                        ValidationCode.UNKNOWN_COLUMN,
                        Severity.WARNING,
                        f"undeclared column will be ignored: {column}",
                        file=filename,
                        field=column,
                        may_continue=True,
                    )
                )
        return ok

    def _tasks(
        self,
        rows: list[dict[str, str]],
        declaration: FileDeclaration,
        report: ValidationReport,
    ) -> list[TaskRecord]:
        records: list[TaskRecord] = []
        for index, row in enumerate(rows, start=2):
            file = declaration.path
            task_id = self._text(row, declaration, "task_id")
            vehicle_id = self._text(row, declaration, "vehicle_id")
            if not task_id:
                report.add(
                    self._finding(
                        ValidationCode.TASK_ID_MISSING,
                        Severity.ERROR,
                        "task_id is required",
                        file=file,
                        row=index,
                        field="task_id",
                        may_continue=False,
                    )
                )
                continue
            if not vehicle_id:
                report.add(
                    self._finding(
                        ValidationCode.VEHICLE_ID_MISSING,
                        Severity.ERROR,
                        "vehicle_id is required",
                        file=file,
                        row=index,
                        field="vehicle_id",
                        may_continue=False,
                    )
                )
                continue
            task_class = self._task_class(row, declaration, file, index, report)
            decision = self._decision(row, declaration, file, index, report)
            arrival = self._number(
                row, declaration, "arrival_time", file, index, report, required=True
            )
            deadline = self._number(
                row, declaration, "deadline_ms", file, index, report, required=True
            )
            completed = self._bool(
                row, declaration, "completed", file, index, report, required=True
            )
            if arrival is None or deadline is None or completed is None:
                continue
            completion = self._number(row, declaration, "completion_time", file, index, report)
            latency = self._number(row, declaration, "latency_ms", file, index, report)
            if deadline < 0:
                report.add(
                    self._finding(
                        ValidationCode.TASK_DEADLINE_NEGATIVE,
                        Severity.ERROR,
                        "deadline_ms must be non-negative",
                        file=file,
                        row=index,
                        field="deadline_ms",
                        value=deadline,
                        may_continue=False,
                    )
                )
            if latency is not None and latency < 0:
                report.add(
                    self._finding(
                        ValidationCode.TASK_LATENCY_NEGATIVE,
                        Severity.ERROR,
                        "latency_ms must be non-negative",
                        file=file,
                        row=index,
                        field="latency_ms",
                        value=latency,
                        may_continue=False,
                    )
                )
            if completion is not None and completion < arrival:
                report.add(
                    self._finding(
                        ValidationCode.TASK_COMPLETION_BEFORE_ARRIVAL,
                        Severity.ERROR,
                        "completion_time must not be before arrival_time",
                        file=file,
                        row=index,
                        field="completion_time",
                        value=completion,
                        may_continue=False,
                    )
                )
            try:
                records.append(
                    TaskRecord(
                        task_id=task_id,
                        vehicle_id=vehicle_id,
                        task_class=task_class,
                        arrival_time_s=arrival,
                        deadline_ms=deadline,
                        decision=decision,
                        completed=completed,
                        completion_time_s=completion,
                        latency_ms=latency,
                        target_id=self._text(row, declaration, "target_id"),
                        workload_cycles=self._number(
                            row, declaration, "workload_cycles", file, index, report
                        ),
                        data_size_bytes=self._number(
                            row, declaration, "data_size_bytes", file, index, report
                        ),
                        energy_j=self._number(row, declaration, "energy_j", file, index, report),
                        drop_reason=self._text(row, declaration, "drop_reason"),
                        source_file=file,
                        source_row=index,
                    )
                )
            except ValidationError:
                continue
        return records

    def _infrastructure(
        self,
        rows: list[dict[str, str]],
        declaration: FileDeclaration,
        report: ValidationReport,
    ) -> list[InfrastructureRecord]:
        records: list[InfrastructureRecord] = []
        for index, row in enumerate(rows, start=2):
            file = declaration.path
            timestamp = self._number(
                row, declaration, "timestamp", file, index, report, required=True
            )
            rsu_id = self._text(row, declaration, "rsu_id")
            if timestamp is None:
                report.add(
                    self._finding(
                        ValidationCode.TIMESTAMP_INVALID,
                        Severity.ERROR,
                        "timestamp is required and must be numeric",
                        file=file,
                        row=index,
                        field="timestamp",
                        may_continue=False,
                    )
                )
                continue
            if not rsu_id:
                report.add(
                    self._finding(
                        ValidationCode.RSU_ID_MISSING,
                        Severity.ERROR,
                        "rsu_id is required",
                        file=file,
                        row=index,
                        field="rsu_id",
                        may_continue=False,
                    )
                )
                continue
            queue_length = self._number(row, declaration, "queue_length", file, index, report)
            utilisation = self._number(row, declaration, "utilisation", file, index, report)
            if queue_length is not None and queue_length < 0:
                report.add(
                    self._finding(
                        ValidationCode.QUEUE_LENGTH_NEGATIVE,
                        Severity.ERROR,
                        "queue_length must be non-negative",
                        file=file,
                        row=index,
                        field="queue_length",
                        value=queue_length,
                        may_continue=False,
                    )
                )
            if utilisation is not None and not 0 <= utilisation <= 1:
                report.add(
                    self._finding(
                        ValidationCode.UTILISATION_OUT_OF_RANGE,
                        Severity.ERROR,
                        "utilisation must be between 0 and 1",
                        file=file,
                        row=index,
                        field="utilisation",
                        value=utilisation,
                        may_continue=True,
                        capabilities=FIELD_CAPABILITIES["infra_state"],
                    )
                )
                utilisation = None
            records.append(
                InfrastructureRecord(
                    timestamp_s=timestamp,
                    rsu_id=rsu_id,
                    queue_length=queue_length,
                    utilisation_fraction=utilisation,
                    arrivals=self._integer(row, declaration, "arrivals", file, index, report),
                    active_tasks=self._integer(
                        row, declaration, "active_tasks", file, index, report
                    ),
                    drops=self._integer(row, declaration, "drops", file, index, report),
                    capacity=self._number(row, declaration, "capacity", file, index, report),
                    source_file=file,
                    source_row=index,
                )
            )
        return records

    def _vehicles(
        self,
        rows: list[dict[str, str]],
        declaration: FileDeclaration,
        report: ValidationReport,
    ) -> list[VehicleStateRecord]:
        records: list[VehicleStateRecord] = []
        for index, row in enumerate(rows, start=2):
            file = declaration.path
            timestamp = self._number(
                row, declaration, "timestamp", file, index, report, required=True
            )
            vehicle_id = self._text(row, declaration, "vehicle_id")
            if timestamp is None or not vehicle_id:
                report.add(
                    self._finding(
                        ValidationCode.VEHICLE_ID_MISSING,
                        Severity.ERROR,
                        "vehicle timestamp and vehicle_id are required",
                        file=file,
                        row=index,
                        may_continue=False,
                    )
                )
                continue
            speed = self._number(row, declaration, "speed", file, index, report)
            if speed is not None and speed < 0:
                report.add(
                    self._finding(
                        ValidationCode.SPEED_NEGATIVE,
                        Severity.ERROR,
                        "speed must be non-negative",
                        file=file,
                        row=index,
                        field="speed",
                        value=speed,
                        may_continue=True,
                    )
                )
                speed = None
            records.append(
                VehicleStateRecord(
                    timestamp_s=timestamp,
                    vehicle_id=vehicle_id,
                    x=self._number(row, declaration, "x", file, index, report),
                    y=self._number(row, declaration, "y", file, index, report),
                    speed_mps=speed,
                    lane=self._text(row, declaration, "lane"),
                    tier=self._text(row, declaration, "tier"),
                    source_file=file,
                    source_row=index,
                )
            )
        return records

    def _traffic(
        self,
        rows: list[dict[str, str]],
        declaration: FileDeclaration,
        report: ValidationReport,
    ) -> list[TrafficObservationRecord]:
        records: list[TrafficObservationRecord] = []
        for index, row in enumerate(rows, start=2):
            file = declaration.path
            timestamp = self._number(
                row, declaration, "timestamp", file, index, report, required=True
            )
            sensor_id = self._text(row, declaration, "sensor_id")
            if timestamp is None or not sensor_id:
                continue
            count = self._integer(row, declaration, "count", file, index, report)
            speed = self._number(row, declaration, "average_speed", file, index, report)
            if count is not None and count < 0:
                report.add(
                    self._finding(
                        ValidationCode.COUNT_NEGATIVE,
                        Severity.ERROR,
                        "count must be non-negative",
                        file=file,
                        row=index,
                        field="count",
                        value=count,
                        may_continue=True,
                    )
                )
                count = None
            if speed is not None and speed < 0:
                report.add(
                    self._finding(
                        ValidationCode.SPEED_NEGATIVE,
                        Severity.ERROR,
                        "average_speed must be non-negative",
                        file=file,
                        row=index,
                        field="average_speed",
                        value=speed,
                        may_continue=True,
                    )
                )
                speed = None
            records.append(
                TrafficObservationRecord(
                    timestamp_s=timestamp,
                    sensor_id=sensor_id,
                    count=count,
                    average_speed_mps=speed,
                    location=self._text(row, declaration, "location"),
                    source_file=file,
                    source_row=index,
                )
            )
        return records

    def _trips(
        self,
        rows: list[dict[str, str]],
        declaration: FileDeclaration,
        report: ValidationReport,
    ) -> list[TripRecord]:
        records: list[TripRecord] = []
        for index, row in enumerate(rows, start=2):
            file = declaration.path
            trip_id = self._text(row, declaration, "trip_id")
            departure = self._number(
                row, declaration, "departure_time", file, index, report, required=True
            )
            if not trip_id or departure is None:
                continue
            arrival = self._number(row, declaration, "arrival_time", file, index, report)
            duration = self._number(row, declaration, "duration", file, index, report)
            if arrival is not None and arrival < departure:
                report.add(
                    self._finding(
                        ValidationCode.TRIP_ARRIVAL_BEFORE_DEPARTURE,
                        Severity.ERROR,
                        "arrival_time must not be before departure_time",
                        file=file,
                        row=index,
                        field="arrival_time",
                        value=arrival,
                        may_continue=False,
                    )
                )
            if duration is not None and duration < 0:
                report.add(
                    self._finding(
                        ValidationCode.TRIP_DURATION_NEGATIVE,
                        Severity.ERROR,
                        "duration must be non-negative",
                        file=file,
                        row=index,
                        field="duration",
                        value=duration,
                        may_continue=False,
                    )
                )
            if (
                arrival is not None
                and duration is not None
                and abs((arrival - departure) - duration) > 1e-6
            ):
                report.add(
                    self._finding(
                        ValidationCode.TRIP_DURATION_INCONSISTENT,
                        Severity.WARNING,
                        "duration does not match arrival_time - departure_time",
                        file=file,
                        row=index,
                        field="duration",
                        value=duration,
                        may_continue=True,
                    )
                )
            records.append(
                TripRecord(
                    trip_id=trip_id,
                    vehicle_id=self._text(row, declaration, "vehicle_id"),
                    departure_time_s=departure,
                    arrival_time_s=arrival,
                    duration_s=duration,
                    route_id=self._text(row, declaration, "route_id"),
                    source_file=file,
                    source_row=index,
                )
            )
        return records

    def _incidents(
        self,
        rows: list[dict[str, str]],
        declaration: FileDeclaration,
        report: ValidationReport,
    ) -> list[IncidentRecord]:
        records: list[IncidentRecord] = []
        for index, row in enumerate(rows, start=2):
            file = declaration.path
            incident_id = self._text(row, declaration, "incident_id")
            timestamp = self._number(
                row, declaration, "timestamp", file, index, report, required=True
            )
            incident_type = self._text(row, declaration, "incident_type")
            if not incident_id or timestamp is None or not incident_type:
                continue
            records.append(
                IncidentRecord(
                    incident_id=incident_id,
                    timestamp_s=timestamp,
                    incident_type=incident_type,
                    location=self._text(row, declaration, "location"),
                    severity=self._text(row, declaration, "severity"),
                    source_file=file,
                    source_row=index,
                )
            )
        return records

    def _validate_duplicate_task_ids(
        self,
        records: list[TaskRecord],
        report: ValidationReport,
    ) -> None:
        seen: set[str] = set()
        for record in records:
            if record.task_id in seen:
                report.add(
                    self._finding(
                        ValidationCode.TASK_ID_DUPLICATE,
                        Severity.ERROR,
                        "task_id must be unique within a run",
                        file=record.source_file,
                        row=record.source_row,
                        field="task_id",
                        value=record.task_id,
                        may_continue=False,
                    )
                )
            seen.add(record.task_id)

    def _text(self, row: dict[str, str], declaration: FileDeclaration, field: str) -> str | None:
        value = row.get(declaration.source_column_for(field))
        if value is None or value == "":
            return None
        return value

    def _number(
        self,
        row: dict[str, str],
        declaration: FileDeclaration,
        field: str,
        file: str,
        source_row: int,
        report: ValidationReport,
        *,
        required: bool = False,
    ) -> float | None:
        raw = self._text(row, declaration, field)
        if raw is None:
            if required:
                report.add(
                    self._finding(
                        ValidationCode.TYPE_PARSE_FAILED,
                        Severity.ERROR,
                        f"{field} is required and must be numeric",
                        file=file,
                        row=source_row,
                        field=field,
                        may_continue=False,
                    )
                )
            return None
        try:
            value = float(raw)
        except ValueError:
            report.add(
                self._finding(
                    ValidationCode.TYPE_PARSE_FAILED,
                    Severity.ERROR,
                    f"{field} must be numeric",
                    file=file,
                    row=source_row,
                    field=field,
                    value=raw,
                    may_continue=not required,
                )
            )
            return None
        return self._convert_unit(value, declaration, field, file, source_row, report)

    def _integer(
        self,
        row: dict[str, str],
        declaration: FileDeclaration,
        field: str,
        file: str,
        source_row: int,
        report: ValidationReport,
    ) -> int | None:
        value = self._number(row, declaration, field, file, source_row, report)
        if value is None:
            return None
        return int(value)

    def _bool(
        self,
        row: dict[str, str],
        declaration: FileDeclaration,
        field: str,
        file: str,
        source_row: int,
        report: ValidationReport,
        *,
        required: bool = False,
    ) -> bool | None:
        raw = self._text(row, declaration, field)
        if raw is None:
            if required:
                report.add(
                    self._finding(
                        ValidationCode.TYPE_PARSE_FAILED,
                        Severity.ERROR,
                        f"{field} is required and must be boolean",
                        file=file,
                        row=source_row,
                        field=field,
                        may_continue=False,
                    )
                )
            return None
        normalised = raw.strip().lower()
        if normalised in {"true", "1", "yes"}:
            return True
        if normalised in {"false", "0", "no"}:
            return False
        report.add(
            self._finding(
                ValidationCode.TYPE_PARSE_FAILED,
                Severity.ERROR,
                f"{field} must be boolean",
                file=file,
                row=source_row,
                field=field,
                value=raw,
                may_continue=not required,
            )
        )
        return None

    def _task_class(
        self,
        row: dict[str, str],
        declaration: FileDeclaration,
        file: str,
        source_row: int,
        report: ValidationReport,
    ) -> TaskClass:
        raw = self._text(row, declaration, "task_class")
        if raw in {TaskClass.T1.value, TaskClass.T2.value, TaskClass.T3.value}:
            return TaskClass(raw)
        report.add(
            self._finding(
                ValidationCode.TASK_CLASS_UNKNOWN,
                Severity.WARNING,
                "task_class is not one of T1, T2, T3",
                file=file,
                row=source_row,
                field="task_class",
                value=raw,
                may_continue=True,
            )
        )
        return TaskClass.UNKNOWN

    def _decision(
        self,
        row: dict[str, str],
        declaration: FileDeclaration,
        file: str,
        source_row: int,
        report: ValidationReport,
    ) -> Decision:
        raw = self._text(row, declaration, "decision")
        if raw in {Decision.LOCAL.value, Decision.V2I.value, Decision.V2V.value}:
            return Decision(raw)
        report.add(
            self._finding(
                ValidationCode.TASK_DECISION_UNKNOWN,
                Severity.WARNING,
                "decision is not one of local, v2i, v2v",
                file=file,
                row=source_row,
                field="decision",
                value=raw,
                may_continue=True,
            )
        )
        return Decision.UNKNOWN

    def _convert_unit(
        self,
        value: float,
        declaration: FileDeclaration,
        field: str,
        file: str,
        source_row: int,
        report: ValidationReport,
    ) -> float | None:
        dimension = UNIT_DIMENSIONS.get(field)
        if dimension is None:
            return value
        unit = declaration.units.get(field)
        if unit is None:
            report.add(
                self._finding(
                    ValidationCode.UNKNOWN_UNIT,
                    Severity.ERROR,
                    f"unit is required for field: {field}",
                    file=file,
                    row=source_row,
                    field=field,
                    may_continue=False,
                )
            )
            return None
        converter = _CONVERTERS.get(dimension, {}).get(unit)
        if converter is None:
            report.add(
                self._finding(
                    ValidationCode.UNIT_CONVERSION_UNSUPPORTED,
                    Severity.ERROR,
                    f"unsupported unit for {field}: {unit}",
                    file=file,
                    row=source_row,
                    field=field,
                    value=unit,
                    may_continue=False,
                )
            )
            return None
        return converter(value)

    @staticmethod
    def _finding(
        code: ValidationCode,
        severity: Severity,
        message: str,
        *,
        file: str | None = None,
        row: int | None = None,
        field: str | None = None,
        value: object | None = None,
        may_continue: bool,
        capabilities: list[str] | None = None,
    ) -> ValidationFinding:
        return ValidationFinding(
            code=code,
            severity=severity,
            message=message,
            file=file,
            row=row,
            field=field,
            value=value,
            may_continue=may_continue,
            affected_capabilities=capabilities or [],
        )


def _identity(value: float) -> float:
    return value


_CONVERTERS: dict[str, dict[str, Callable[[float], float]]] = {
    "time_s": {
        "s": _identity,
        "ms": lambda value: value / 1000.0,
        "min": lambda value: value * 60.0,
    },
    "duration_ms": {"ms": _identity, "s": lambda value: value * 1000.0},
    "speed_mps": {"m/s": _identity, "mps": _identity, "km/h": lambda value: value / 3.6},
    "bytes": {"bytes": _identity, "B": _identity, "KB": lambda value: value * 1000.0},
    "joules": {"J": _identity},
    "cycles": {"cycles": _identity},
    "fraction": {"fraction": _identity},
}
