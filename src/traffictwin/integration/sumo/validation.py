"""Validation orchestration for immutable SUMO result packages."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.ingestion.hashes import bundle_fingerprint, sha256_file
from traffictwin.integration.sumo.adapter import SumoResultsAdapter
from traffictwin.integration.sumo.models import (
    SUMO_RESULT_MANIFEST_VERSION,
    SUMO_VALIDATOR_VERSION,
    SUPPORTED_SUMO_VERSION_PREFIXES,
    SumoRawFileEvidence,
    SumoResultManifest,
    SumoValidationResult,
)
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.findings import Severity, ValidationFinding
from traffictwin.validation.report import ValidationReport


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def validate_sumo_results(
    path: str | Path,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> SumoValidationResult:
    """Validate and canonicalise a directory without changing its contents."""

    source = Path(path).resolve()
    report = ValidationReport(
        import_timestamp=clock(),
        validator_version=SUMO_VALIDATOR_VERSION,
    )
    if not source.is_dir():
        report.add(
            _finding(
                ValidationCode.SUMO_SOURCE_DIRECTORY_INVALID,
                Severity.FATAL,
                "SUMO result source must be a readable directory",
                may_continue=False,
            )
        )
        report.finalise()
        return SumoValidationResult(source=str(source), report=report)

    manifest = _load_manifest(source, report)
    canonical = CanonicalTables()
    trip_observations = []
    summary_steps = []
    raw_files: list[SumoRawFileEvidence] = []
    evidence = EvidenceAvailability()
    fingerprint: str | None = None
    if manifest is not None:
        report.bundle_id = manifest.bundle.bundle_id
        report.run_id = manifest.run.run_id
        version_supported = _validate_sumo_version(manifest, report)
        declared_files = _validate_declared_files(source, manifest, report)
        if declared_files:
            fingerprint = bundle_fingerprint([source / "sumo-source.yaml", *declared_files], source)
            raw_files = [
                SumoRawFileEvidence(
                    path=file.relative_to(source).as_posix(),
                    sha256=sha256_file(file),
                    size_bytes=file.stat().st_size,
                )
                for file in declared_files
            ]
        if (
            version_supported
            and len(declared_files) == 2
            and _files_match_checksums(source, manifest)
        ):
            output = SumoResultsAdapter().canonicalise(source, manifest, report)
            canonical = output.canonical
            trip_observations = output.trip_observations
            summary_steps = output.summary_steps
            evidence = EvidenceAvailability(
                trips=(
                    EvidenceStatus.AVAILABLE
                    if manifest.files.tripinfo.path in report.files_inspected
                    else EvidenceStatus.INVALID
                ),
                traffic=EvidenceStatus.UNAVAILABLE,
            )
        report.add(
            _finding(
                ValidationCode.SUMO_SOURCE_PROVENANCE_DECLARED,
                Severity.INFO,
                "scenario, SUMO version, licence, retrieval, redistribution, and checksums are "
                "declared in sumo-source.yaml",
                file="sumo-source.yaml",
                may_continue=True,
                affected_capabilities=["source_provenance"],
            )
        )
        report.add(
            _finding(
                ValidationCode.SUMO_FCD_MAPPING_REQUIRED,
                Severity.INFO,
                "FCD is unavailable until an explicit mapping contract is approved",
                may_continue=True,
                affected_capabilities=["sumo_fcd_import"],
            )
        )
        report.add(
            _finding(
                ValidationCode.SUMO_DIRECT_LAUNCH_UNSUPPORTED,
                Severity.INFO,
                "this adapter imports completed XML outputs and cannot launch SUMO",
                may_continue=True,
                affected_capabilities=["direct_launch", "asynchronous_launch"],
            )
        )

    report.canonical_record_counts = canonical.record_counts()
    report.available_evidence_categories = evidence.available_categories()
    report.unavailable_evidence_categories = evidence.unavailable_categories()
    report.finalise()
    return SumoValidationResult(
        source=str(source),
        fingerprint=fingerprint,
        manifest=manifest,
        raw_files=raw_files,
        canonical=canonical,
        trip_observations=trip_observations,
        summary_steps=summary_steps,
        evidence=evidence,
        report=report,
    )


def inspect_sumo_results(path: str | Path) -> SumoValidationResult:
    """Inspect SUMO results without registry mutation."""

    return validate_sumo_results(path)


def _load_manifest(root: Path, report: ValidationReport) -> SumoResultManifest | None:
    path = root / "sumo-source.yaml"
    if not path.is_file():
        report.add(
            _finding(
                ValidationCode.SUMO_MANIFEST_MISSING,
                Severity.FATAL,
                "sumo-source.yaml is required",
                file="sumo-source.yaml",
                may_continue=False,
            )
        )
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        report.add(
            _finding(
                ValidationCode.SUMO_MANIFEST_INVALID,
                Severity.FATAL,
                f"sumo-source.yaml could not be read or parsed: {exc}",
                file="sumo-source.yaml",
                may_continue=False,
            )
        )
        return None
    if not isinstance(loaded, dict):
        report.add(
            _finding(
                ValidationCode.SUMO_MANIFEST_INVALID,
                Severity.FATAL,
                "sumo-source.yaml must contain a mapping",
                file="sumo-source.yaml",
                may_continue=False,
            )
        )
        return None
    raw = cast(dict[str, Any], loaded)
    if raw.get("schema_version") != SUMO_RESULT_MANIFEST_VERSION:
        report.add(
            _finding(
                ValidationCode.SUMO_MANIFEST_SCHEMA_UNSUPPORTED,
                Severity.FATAL,
                f"only SUMO result manifest {SUMO_RESULT_MANIFEST_VERSION} is supported",
                file="sumo-source.yaml",
                field="schema_version",
                value=raw.get("schema_version"),
                may_continue=False,
            )
        )
        return None
    files = raw.get("files")
    if isinstance(files, dict) and "fcd" in files:
        report.add(
            _finding(
                ValidationCode.SUMO_FCD_MAPPING_REQUIRED,
                Severity.FATAL,
                "FCD cannot be declared until an explicit mapping contract is approved",
                file="sumo-source.yaml",
                field="files.fcd",
                may_continue=False,
                affected_capabilities=["sumo_fcd_import"],
            )
        )
        return None
    try:
        return SumoResultManifest.model_validate(raw)
    except ValidationError as exc:
        report.add(
            _finding(
                ValidationCode.SUMO_MANIFEST_INVALID,
                Severity.FATAL,
                f"sumo-source.yaml failed schema validation: {exc}",
                file="sumo-source.yaml",
                may_continue=False,
            )
        )
        return None


def _validate_sumo_version(
    manifest: SumoResultManifest,
    report: ValidationReport,
) -> bool:
    version = manifest.source.sumo_version
    if version.startswith(SUPPORTED_SUMO_VERSION_PREFIXES):
        return True
    report.add(
        _finding(
            ValidationCode.SUMO_VERSION_UNSUPPORTED,
            Severity.ERROR,
            "the v1 adapter is validated only for SUMO 1.27.x outputs",
            file="sumo-source.yaml",
            field="source.sumo_version",
            value=version,
            may_continue=False,
        )
    )
    return False


def _validate_declared_files(
    root: Path,
    manifest: SumoResultManifest,
    report: ValidationReport,
) -> list[Path]:
    paths: list[Path] = []
    for declaration in (manifest.files.tripinfo, manifest.files.summary):
        candidate = root / declaration.path
        if candidate.is_symlink():
            report.add(
                _finding(
                    ValidationCode.SUMO_FILE_PATH_UNSAFE,
                    Severity.ERROR,
                    "symbolic links are not accepted as immutable SUMO source files",
                    file=declaration.path,
                    may_continue=False,
                )
            )
            continue
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root.resolve())
        except (FileNotFoundError, OSError, ValueError):
            report.add(
                _finding(
                    ValidationCode.SUMO_FILE_DECLARED_MISSING,
                    Severity.ERROR,
                    f"declared SUMO result file is missing or unsafe: {declaration.path}",
                    file=declaration.path,
                    may_continue=False,
                )
            )
            continue
        if not resolved.is_file():
            report.add(
                _finding(
                    ValidationCode.SUMO_FILE_DECLARED_MISSING,
                    Severity.ERROR,
                    f"declared SUMO result is not a file: {declaration.path}",
                    file=declaration.path,
                    may_continue=False,
                )
            )
            continue
        paths.append(resolved)
        actual = sha256_file(resolved)
        if actual != declaration.checksum_sha256:
            report.add(
                _finding(
                    ValidationCode.SUMO_FILE_CHECKSUM_MISMATCH,
                    Severity.ERROR,
                    "declared SHA-256 checksum does not match raw XML",
                    file=declaration.path,
                    field="checksum_sha256",
                    value=actual,
                    may_continue=False,
                )
            )
    return paths


def _files_match_checksums(root: Path, manifest: SumoResultManifest) -> bool:
    return all(
        sha256_file(root / declaration.path) == declaration.checksum_sha256
        for declaration in (manifest.files.tripinfo, manifest.files.summary)
    )


def _finding(
    code: ValidationCode,
    severity: Severity,
    message: str,
    *,
    file: str | None = None,
    field: str | None = None,
    value: object = None,
    may_continue: bool,
    affected_capabilities: list[str] | None = None,
) -> ValidationFinding:
    return ValidationFinding(
        code=code,
        severity=severity,
        message=message,
        file=file,
        field=field,
        value=value,
        may_continue=may_continue,
        affected_capabilities=affected_capabilities or [],
    )
