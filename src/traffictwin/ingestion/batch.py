"""Deterministic, failure-isolated validation and import of bundle path sets."""

from __future__ import annotations

import csv
import glob
import os
import sqlite3
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.ingestion.bundle import (
    BundleValidationResult,
    import_validated_bundle,
    validate_bundle,
)
from traffictwin.storage.registry import RegistryConflictError, RegistryError
from traffictwin.validation.report import ImportStatus

BATCH_SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAX_BATCH_INPUTS = 64
MAX_BATCH_BUNDLES = 256


class BatchOperation(StrEnum):
    """Supported batch operations."""

    VALIDATE = "validate"
    IMPORT = "import"


class BatchOverallStatus(StrEnum):
    """Consolidated batch outcome."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class BatchImportState(StrEnum):
    """Registry outcome for one candidate."""

    NOT_REQUESTED = "not_requested"
    CREATED = "created"
    IDEMPOTENT = "idempotent"
    REJECTED = "rejected"
    CONFLICT = "conflict"
    FAILED = "failed"


class BatchIssueCode(StrEnum):
    """Stable codes for input-set failures outside an individual bundle."""

    INPUT_REQUIRED = "BATCH_INPUT_REQUIRED"
    INPUT_LIMIT_EXCEEDED = "BATCH_INPUT_LIMIT_EXCEEDED"
    GLOB_UNMATCHED = "BATCH_GLOB_UNMATCHED"
    BUNDLE_LIMIT_EXCEEDED = "BATCH_BUNDLE_LIMIT_EXCEEDED"


class BatchModel(BaseModel):
    """Strict base model for batch artifacts."""

    model_config = ConfigDict(extra="forbid")


class BatchInputIssue(BatchModel):
    """One problem resolving the explicit input set."""

    code: BatchIssueCode
    reference: str | None = None
    message: str


class BatchBundleResult(BatchModel):
    """Validation and optional registry outcome for one resolved bundle candidate."""

    source: str
    matched_by: list[str] = Field(default_factory=list)
    bundle_id: str | None = None
    run_id: str | None = None
    fingerprint: str | None = None
    validation_status: ImportStatus
    may_import: bool
    finding_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    import_state: BatchImportState = BatchImportState.NOT_REQUESTED
    message: str


class BatchBundleSummary(BatchModel):
    """Consolidated deterministic summary for an explicit batch request."""

    schema_version: Literal["1.0"] = BATCH_SCHEMA_VERSION
    operation: BatchOperation
    overall_status: BatchOverallStatus
    input_references: list[str]
    input_issues: list[BatchInputIssue] = Field(default_factory=list)
    matched_bundle_count: int = Field(ge=0)
    processed_bundle_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    idempotent_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: list[BatchBundleResult] = Field(default_factory=list)
    max_inputs: int = MAX_BATCH_INPUTS
    max_bundles: int = MAX_BATCH_BUNDLES

    @property
    def successful(self) -> bool:
        """Return whether every explicit input completed without rejection or conflict."""

        return self.overall_status is BatchOverallStatus.COMPLETE

    def to_json(self) -> str:
        """Return stable formatted JSON."""

        return self.model_dump_json(indent=2)


@dataclass(frozen=True)
class _ResolvedCandidate:
    path: Path
    matched_by: tuple[str, ...]


@dataclass(frozen=True)
class _Resolution:
    input_references: tuple[str, ...]
    candidates: tuple[_ResolvedCandidate, ...]
    issues: tuple[BatchInputIssue, ...]


def validate_bundle_batch(inputs: Sequence[str | Path]) -> BatchBundleSummary:
    """Validate an explicit set of bundle paths/globs without registry mutation."""

    resolution = _resolve_inputs(inputs)
    results = [
        _validate_candidate(candidate, operation=BatchOperation.VALIDATE, registry_path=None)
        for candidate in resolution.candidates
    ]
    return _build_summary(BatchOperation.VALIDATE, resolution, results)


def import_bundle_batch(
    inputs: Sequence[str | Path],
    registry_path: str | Path,
) -> BatchBundleSummary:
    """Validate and independently register each resolved bundle candidate."""

    resolution = _resolve_inputs(inputs)
    results = [
        _validate_candidate(
            candidate,
            operation=BatchOperation.IMPORT,
            registry_path=registry_path,
        )
        for candidate in resolution.candidates
    ]
    return _build_summary(BatchOperation.IMPORT, resolution, results)


def batch_summary_to_text(summary: BatchBundleSummary) -> str:
    """Render a compact human-readable consolidated summary."""

    lines = [
        f"operation: {summary.operation.value}",
        f"status: {summary.overall_status.value}",
        f"matched_bundles: {summary.matched_bundle_count}",
        f"processed_bundles: {summary.processed_bundle_count}",
        f"accepted: {summary.accepted_count}",
        f"rejected: {summary.rejected_count}",
    ]
    if summary.operation is BatchOperation.IMPORT:
        lines.extend(
            [
                f"created: {summary.created_count}",
                f"idempotent: {summary.idempotent_count}",
                f"conflicts: {summary.conflict_count}",
                f"failed: {summary.failed_count}",
            ]
        )
    for issue in summary.input_issues:
        reference = f" [{issue.reference}]" if issue.reference else ""
        lines.append(f"input_issue: {issue.code.value}{reference}: {issue.message}")
    for result in summary.results:
        lines.append(
            "bundle: "
            f"{result.source} validation={result.validation_status.value} "
            f"import={result.import_state.value} findings={result.finding_count}"
        )
    return "\n".join(lines) + "\n"


def batch_summary_to_csv(summary: BatchBundleSummary) -> str:
    """Render deterministic per-bundle outcomes as CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "source",
            "matched_by",
            "bundle_id",
            "run_id",
            "fingerprint",
            "validation_status",
            "may_import",
            "finding_count",
            "warning_count",
            "error_count",
            "import_state",
            "message",
        ]
    )
    for result in summary.results:
        writer.writerow(
            [
                result.source,
                "|".join(result.matched_by),
                result.bundle_id or "",
                result.run_id or "",
                result.fingerprint or "",
                result.validation_status.value,
                str(result.may_import).lower(),
                result.finding_count,
                result.warning_count,
                result.error_count,
                result.import_state.value,
                result.message,
            ]
        )
    return output.getvalue()


def _resolve_inputs(inputs: Sequence[str | Path]) -> _Resolution:
    references = tuple(str(item).strip() for item in inputs if str(item).strip())
    if not references:
        return _Resolution(
            input_references=(),
            candidates=(),
            issues=(
                BatchInputIssue(
                    code=BatchIssueCode.INPUT_REQUIRED,
                    message="at least one bundle path or glob is required",
                ),
            ),
        )
    if len(references) > MAX_BATCH_INPUTS:
        return _limit_resolution(
            references,
            BatchIssueCode.INPUT_LIMIT_EXCEEDED,
            f"batch accepts at most {MAX_BATCH_INPUTS} input references",
        )

    matched_by_path: dict[Path, set[str]] = {}
    issues: list[BatchInputIssue] = []
    for reference in references:
        expanded = os.path.expanduser(reference)
        if glob.has_magic(expanded):
            matches = []
            for match in glob.iglob(expanded, recursive=True):
                matches.append(match)
                if len(matches) > MAX_BATCH_BUNDLES:
                    return _limit_resolution(
                        references,
                        BatchIssueCode.BUNDLE_LIMIT_EXCEEDED,
                        f"one input resolved beyond the {MAX_BATCH_BUNDLES}-bundle limit",
                        reference=reference,
                    )
            if not matches:
                issues.append(
                    BatchInputIssue(
                        code=BatchIssueCode.GLOB_UNMATCHED,
                        reference=reference,
                        message="glob did not match any paths",
                    )
                )
                continue
        else:
            matches = [expanded]
        for match in matches:
            resolved = _normalise_candidate(Path(match))
            matched_by_path.setdefault(resolved, set()).add(reference)
            if len(matched_by_path) > MAX_BATCH_BUNDLES:
                return _limit_resolution(
                    references,
                    BatchIssueCode.BUNDLE_LIMIT_EXCEEDED,
                    f"batch resolves at most {MAX_BATCH_BUNDLES} unique bundle paths",
                )

    candidates = tuple(
        _ResolvedCandidate(path=path, matched_by=tuple(sorted(matched_by_path[path])))
        for path in sorted(matched_by_path, key=lambda item: item.as_posix())
    )
    return _Resolution(references, candidates, tuple(issues))


def _normalise_candidate(path: Path) -> Path:
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _limit_resolution(
    references: tuple[str, ...],
    code: BatchIssueCode,
    message: str,
    *,
    reference: str | None = None,
) -> _Resolution:
    return _Resolution(
        input_references=references,
        candidates=(),
        issues=(BatchInputIssue(code=code, reference=reference, message=message),),
    )


def _validate_candidate(
    candidate: _ResolvedCandidate,
    *,
    operation: BatchOperation,
    registry_path: str | Path | None,
) -> BatchBundleResult:
    try:
        validation = _validate_one(candidate.path)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        return BatchBundleResult(
            source=candidate.path.as_posix(),
            matched_by=list(candidate.matched_by),
            validation_status=ImportStatus.REJECTED,
            may_import=False,
            finding_count=1,
            warning_count=0,
            error_count=1,
            import_state=(
                BatchImportState.REJECTED
                if operation is BatchOperation.IMPORT
                else BatchImportState.NOT_REQUESTED
            ),
            message=f"bundle validation failed before a report was produced: {exc}",
        )
    report = validation.report
    import_state = BatchImportState.NOT_REQUESTED
    message = f"bundle validation {report.status.value}"
    if operation is BatchOperation.IMPORT:
        if not report.may_import:
            import_state = BatchImportState.REJECTED
            message = "bundle rejected; registry was not mutated"
        else:
            if registry_path is None:
                raise ValueError("registry_path is required for batch import")
            try:
                imported = import_validated_bundle(validation, registry_path)
                import_state = (
                    BatchImportState.CREATED if imported.created else BatchImportState.IDEMPOTENT
                )
                message = imported.message
            except RegistryConflictError as exc:
                import_state = BatchImportState.CONFLICT
                message = str(exc)
            except (RegistryError, sqlite3.Error, OSError) as exc:
                import_state = BatchImportState.FAILED
                message = f"registry import failed: {exc}"
    counts = report.counts_by_severity
    return BatchBundleResult(
        source=candidate.path.as_posix(),
        matched_by=list(candidate.matched_by),
        bundle_id=report.bundle_id,
        run_id=report.run_id,
        fingerprint=validation.fingerprint,
        validation_status=report.status,
        may_import=report.may_import,
        finding_count=len(report.findings),
        warning_count=counts.get("warning", 0),
        error_count=counts.get("error", 0) + counts.get("fatal", 0),
        import_state=import_state,
        message=message,
    )


def _validate_one(path: Path) -> BundleValidationResult:
    """Keep the single validation call explicit for import and test instrumentation."""

    return validate_bundle(path)


def _build_summary(
    operation: BatchOperation,
    resolution: _Resolution,
    results: list[BatchBundleResult],
) -> BatchBundleSummary:
    accepted_count = sum(result.may_import for result in results)
    rejected_count = len(results) - accepted_count
    created_count = sum(result.import_state is BatchImportState.CREATED for result in results)
    idempotent_count = sum(result.import_state is BatchImportState.IDEMPOTENT for result in results)
    conflict_count = sum(result.import_state is BatchImportState.CONFLICT for result in results)
    failed_count = sum(result.import_state is BatchImportState.FAILED for result in results)
    success_count = (
        accepted_count if operation is BatchOperation.VALIDATE else created_count + idempotent_count
    )
    problem_count = len(resolution.issues) + rejected_count + conflict_count + failed_count
    if success_count == 0:
        overall_status = BatchOverallStatus.FAILED
    elif problem_count:
        overall_status = BatchOverallStatus.PARTIAL
    else:
        overall_status = BatchOverallStatus.COMPLETE
    return BatchBundleSummary(
        operation=operation,
        overall_status=overall_status,
        input_references=list(resolution.input_references),
        input_issues=list(resolution.issues),
        matched_bundle_count=len(resolution.candidates),
        processed_bundle_count=len(results),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        created_count=created_count,
        idempotent_count=idempotent_count,
        conflict_count=conflict_count,
        failed_count=failed_count,
        results=results,
        max_inputs=MAX_BATCH_INPUTS,
        max_bundles=MAX_BATCH_BUNDLES,
    )
