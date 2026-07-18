"""Safe source-row inspection for provenance traces."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from traffictwin.canonical.records import CanonicalRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.ingestion.loader import BundleLoadError, open_bundle
from traffictwin.ingestion.manifest import BundleManifest, FileDeclaration
from traffictwin.metrics.results import JsonValue
from traffictwin.provenance.models import ProvenanceStatus, SourceRow, SourceRowPreview
from traffictwin.validation.findings import ValidationFinding
from traffictwin.validation.report import ValidationReport


def get_source_row(
    bundle_reference: str | Path,
    source_file: str,
    source_row: int,
    *,
    context_rows: int = 2,
    canonical_tables: CanonicalTables | None = None,
    validation_report: ValidationReport | None = None,
    manifest: BundleManifest | None = None,
) -> SourceRowPreview:
    """Return a bounded, read-only preview of a CSV source row."""

    if context_rows < 0:
        msg = "context_rows must be non-negative"
        raise ValueError(msg)
    if not _is_safe_relative_path(source_file):
        return _unavailable_preview(
            source_file,
            source_row,
            "source path must be bundle-relative and must not contain '..'",
        )
    try:
        with open_bundle(bundle_reference) as workspace:
            root = workspace.root.resolve()
            path = (root / source_file).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                return _unavailable_preview(source_file, source_row, "source path escapes bundle")
            if not path.exists() or not path.is_file():
                return _unavailable_preview(source_file, source_row, "source file is unavailable")
            return _read_csv_preview(
                path,
                source_file,
                source_row,
                context_rows=context_rows,
                canonical_tables=canonical_tables,
                validation_report=validation_report,
                declaration=_declaration_for_file(manifest, source_file),
            )
    except BundleLoadError as exc:
        return _unavailable_preview(source_file, source_row, str(exc))
    except OSError as exc:
        return _unavailable_preview(source_file, source_row, f"source row could not be read: {exc}")


def source_preview_for_record(
    bundle_reference: str | Path,
    record: CanonicalRecord,
    *,
    context_rows: int = 2,
    canonical_tables: CanonicalTables | None = None,
    validation_report: ValidationReport | None = None,
    manifest: BundleManifest | None = None,
) -> SourceRowPreview:
    """Return a source preview for a canonical record."""

    return get_source_row(
        bundle_reference,
        record.source_file,
        record.source_row,
        context_rows=context_rows,
        canonical_tables=canonical_tables,
        validation_report=validation_report,
        manifest=manifest,
    )


def _read_csv_preview(
    path: Path,
    source_file: str,
    source_row: int,
    *,
    context_rows: int,
    canonical_tables: CanonicalTables | None,
    validation_report: ValidationReport | None,
    declaration: FileDeclaration | None,
) -> SourceRowPreview:
    start = max(2, source_row - context_rows)
    end = source_row + context_rows
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration:
            return _unavailable_preview(source_file, source_row, "source CSV is empty")
        surrounding: list[SourceRow] = []
        raw_values: dict[str, str | None] = {}
        for line_number, values in enumerate(reader, start=2):
            if line_number > end:
                break
            if line_number < start:
                continue
            row = _row_dict(headers, values)
            surrounding.append(SourceRow(row_number=line_number, values=row))
            if line_number == source_row:
                raw_values = row
        if not raw_values:
            return SourceRowPreview(
                file=source_file,
                row_number=source_row,
                status=ProvenanceStatus.UNAVAILABLE,
                headers=headers,
                surrounding_rows=surrounding,
                inclusion_status="not_found",
                warnings=["requested source row was not found"],
            )
    canonical_type, canonical_values = _canonical_record_values(
        canonical_tables,
        source_file,
        source_row,
    )
    return SourceRowPreview(
        file=source_file,
        row_number=source_row,
        status=ProvenanceStatus.AVAILABLE,
        headers=headers,
        raw_values=raw_values,
        surrounding_rows=surrounding,
        canonical_record_type=canonical_type,
        canonical_values=canonical_values,
        conversions=_declaration_summary(declaration),
        validation_findings=_finding_summaries(validation_report, source_file, source_row),
        inclusion_status="included" if canonical_type is not None else "not_canonicalised",
    )


def _row_dict(headers: list[str], values: list[str]) -> dict[str, str | None]:
    return {
        header: values[index] if index < len(values) else None
        for index, header in enumerate(headers)
    }


def _canonical_record_values(
    canonical_tables: CanonicalTables | None,
    source_file: str,
    source_row: int,
) -> tuple[str | None, dict[str, JsonValue]]:
    if canonical_tables is None:
        return None, {}
    table_records: list[tuple[str, Iterable[CanonicalRecord]]] = [
        ("TaskRecord", canonical_tables.tasks),
        ("InfrastructureRecord", canonical_tables.infrastructure),
        ("VehicleStateRecord", canonical_tables.vehicles),
        ("TrafficObservationRecord", canonical_tables.traffic),
        ("TripRecord", canonical_tables.trips),
        ("IncidentRecord", canonical_tables.incidents),
    ]
    for record_type, records in table_records:
        for record in records:
            if record.source_file == source_file and record.source_row == source_row:
                return record_type, record.model_dump(mode="json")
    return None, {}


def _finding_summaries(
    validation_report: ValidationReport | None,
    source_file: str,
    source_row: int,
) -> list[dict[str, JsonValue]]:
    if validation_report is None:
        return []
    findings: list[dict[str, JsonValue]] = []
    for finding in validation_report.findings:
        if finding.file == source_file and finding.row == source_row:
            findings.append(_finding_summary(finding))
    return findings


def _finding_summary(finding: ValidationFinding) -> dict[str, JsonValue]:
    return {
        "code": finding.code.value,
        "severity": finding.severity.value,
        "message": finding.message,
        "file": finding.file,
        "row": finding.row,
        "field": finding.field,
        "value": finding.value,
        "may_continue": finding.may_continue,
        "affected_capabilities": list(finding.affected_capabilities),
    }


def _declaration_for_file(
    manifest: BundleManifest | None,
    source_file: str,
) -> FileDeclaration | None:
    if manifest is None:
        return None
    for declaration in manifest.files.values():
        if declaration.path == source_file:
            return declaration
    return None


def _declaration_summary(declaration: FileDeclaration | None) -> dict[str, JsonValue]:
    if declaration is None:
        return {}
    return {
        "schema_version": declaration.schema_version,
        "column_map": dict(sorted(declaration.column_map.items())),
        "units": dict(sorted(declaration.units.items())),
        "required_columns": list(declaration.required_columns),
    }


def _is_safe_relative_path(source_file: str) -> bool:
    path = Path(source_file)
    return not path.is_absolute() and ".." not in path.parts


def _unavailable_preview(source_file: str, source_row: int, warning: str) -> SourceRowPreview:
    return SourceRowPreview(
        file=source_file,
        row_number=source_row,
        status=ProvenanceStatus.UNAVAILABLE,
        inclusion_status="unavailable",
        warnings=[warning],
    )
