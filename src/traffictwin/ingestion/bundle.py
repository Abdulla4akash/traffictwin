"""High-level run-bundle validation and import orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.config.seed_io import SeedIOError, load_seed
from traffictwin.domain.enums import ExecutionMode, RunStatus, ValidationStatus
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.insufficient import (
    InsufficientEvidenceSummary,
    build_insufficient_evidence_summary,
)
from traffictwin.ingestion.canonicalise import canonicalise_bundle
from traffictwin.ingestion.hashes import bundle_fingerprint, sha256_file
from traffictwin.ingestion.loader import BundleLoadError, open_bundle
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.storage.registry import BundleImportResult, Registry
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.findings import Severity, ValidationFinding
from traffictwin.validation.report import ValidationReport

EXPECTED_SOURCE_FILES = {
    "manifest.yaml",
    "seed.yaml",
    "tasks.csv",
    "infra_state.csv",
    "vehicle_state.csv",
    "traffic_obs.csv",
    "trips.csv",
    "incidents.csv",
}


@dataclass(frozen=True)
class BundleValidationResult:
    """Result from validating and canonicalising a bundle."""

    source: Path
    fingerprint: str | None
    manifest: BundleManifest | None
    seed: ScenarioSeed | None
    canonical: CanonicalTables
    evidence: EvidenceAvailability
    insufficient_evidence: InsufficientEvidenceSummary
    report: ValidationReport


def validate_bundle(path: str | Path) -> BundleValidationResult:
    """Validate a directory or ZIP run bundle."""

    source = Path(path)
    report = ValidationReport()
    canonical = CanonicalTables()
    manifest: BundleManifest | None = None
    seed: ScenarioSeed | None = None
    evidence = EvidenceAvailability()
    fingerprint: str | None = None

    try:
        with open_bundle(source) as workspace:
            files = [file for file in workspace.root.rglob("*") if file.is_file()]
            fingerprint = bundle_fingerprint(files, workspace.root)
            manifest = _load_manifest(workspace.root, report)
            if manifest is not None:
                report.bundle_id = manifest.bundle.bundle_id
                report.run_id = manifest.run.run_id
                _validate_environment(manifest, report)
                _validate_declared_files(workspace.root, manifest, report)
                _validate_undeclared_files(workspace.root, manifest, report)
                seed = _validate_seed(workspace.root, manifest, report)
                canonical = canonicalise_bundle(workspace.root, manifest, report)
                report.canonical_record_counts = canonical.record_counts()
                evidence = _build_evidence_availability(manifest, canonical, report)
                _add_evidence_findings(evidence, report)
    except BundleLoadError as exc:
        report.add(
            ValidationFinding(
                code=ValidationCode.FILE_UNREADABLE,
                severity=Severity.FATAL,
                message=str(exc),
                may_continue=False,
                affected_capabilities=["bundle_loading"],
            )
        )

    report.available_evidence_categories = evidence.available_categories()
    report.unavailable_evidence_categories = evidence.unavailable_categories()
    report.finalise()
    insufficient = build_insufficient_evidence_summary(report, evidence)
    return BundleValidationResult(
        source=source,
        fingerprint=fingerprint,
        manifest=manifest,
        seed=seed,
        canonical=canonical,
        evidence=evidence,
        insufficient_evidence=insufficient,
        report=report,
    )


def inspect_bundle(path: str | Path) -> BundleValidationResult:
    """Inspect a bundle without mutating a registry."""

    return validate_bundle(path)


def import_bundle(path: str | Path, registry_path: str | Path) -> BundleImportResult:
    """Validate and register an accepted bundle."""

    result = validate_bundle(path)
    if result.manifest is None or result.fingerprint is None or not result.report.may_import:
        return BundleImportResult(
            bundle_id=result.report.bundle_id,
            run_id=result.report.run_id,
            created=False,
            idempotent=False,
            status=result.report.status.value,
            message="bundle rejected; registry was not mutated",
        )

    manifest = result.manifest
    run = Run(
        run_id=manifest.run.run_id,
        experiment_id=manifest.run.experiment_id,
        seed_id=manifest.run.seed_id,
        algorithm=manifest.run.algorithm,
        checkpoint=manifest.run.checkpoint,
        random_seed=manifest.run.random_seed,
        environment_version=manifest.environment.version,
        environment_commit=manifest.environment.commit,
        started_at=manifest.run.started_at,
        ended_at=manifest.run.completed_at,
        execution_mode=ExecutionMode.IMPORTED,
        status=RunStatus.IMPORTED,
        source_bundle=str(Path(path)),
        validation_status=ValidationStatus.VALID,
    )
    return Registry(registry_path).register_bundle_import(
        run=run,
        bundle_id=manifest.bundle.bundle_id,
        source_reference=str(Path(path)),
        fingerprint=result.fingerprint,
        manifest_json=manifest.model_dump_json(),
        validation_report_json=result.report.to_json(),
        import_status=result.report.status.value,
    )


def _load_manifest(root: Path, report: ValidationReport) -> BundleManifest | None:
    manifest_path = root / "manifest.yaml"
    if not manifest_path.exists():
        report.add(
            ValidationFinding(
                code=ValidationCode.BUNDLE_MANIFEST_MISSING,
                severity=Severity.FATAL,
                message="manifest.yaml is required",
                file="manifest.yaml",
                may_continue=False,
            )
        )
        return None
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        report.add(
            ValidationFinding(
                code=ValidationCode.BUNDLE_MANIFEST_INVALID,
                severity=Severity.FATAL,
                message=f"manifest.yaml could not be read or parsed: {exc}",
                file="manifest.yaml",
                may_continue=False,
            )
        )
        return None
    if not isinstance(raw, dict):
        report.add(
            ValidationFinding(
                code=ValidationCode.BUNDLE_MANIFEST_INVALID,
                severity=Severity.FATAL,
                message="manifest.yaml must contain a mapping",
                file="manifest.yaml",
                may_continue=False,
            )
        )
        return None
    data = cast(dict[str, Any], raw)
    if data.get("schema_version") != "1.0":
        report.add(
            ValidationFinding(
                code=ValidationCode.MANIFEST_SCHEMA_UNSUPPORTED,
                severity=Severity.FATAL,
                message="only manifest schema_version 1.0 is supported",
                file="manifest.yaml",
                field="schema_version",
                value=data.get("schema_version"),
                may_continue=False,
            )
        )
        return None
    try:
        return BundleManifest.model_validate(data)
    except ValidationError as exc:
        report.add(
            ValidationFinding(
                code=ValidationCode.BUNDLE_MANIFEST_INVALID,
                severity=Severity.FATAL,
                message=f"manifest.yaml failed schema validation: {exc}",
                file="manifest.yaml",
                may_continue=False,
            )
        )
        if "Field required" in str(exc):
            report.add(
                ValidationFinding(
                    code=ValidationCode.MANIFEST_REQUIRED_FIELD_MISSING,
                    severity=Severity.FATAL,
                    message="manifest.yaml is missing one or more required fields",
                    file="manifest.yaml",
                    may_continue=False,
                )
            )
        return None


def _validate_environment(manifest: BundleManifest, report: ValidationReport) -> None:
    if manifest.environment.version is None and manifest.environment.commit is None:
        report.add(
            ValidationFinding(
                code=ValidationCode.ENVIRONMENT_VERSION_MISSING,
                severity=Severity.ERROR,
                message="environment.version or environment.commit is required",
                file="manifest.yaml",
                field="environment",
                may_continue=False,
                affected_capabilities=["provenance"],
            )
        )


def _validate_declared_files(
    root: Path,
    manifest: BundleManifest,
    report: ValidationReport,
) -> None:
    for declaration in manifest.files.values():
        path = root / declaration.path
        if not path.exists():
            report.add(
                ValidationFinding(
                    code=ValidationCode.FILE_DECLARED_MISSING,
                    severity=Severity.ERROR,
                    message=f"declared file is missing: {declaration.path}",
                    file=declaration.path,
                    may_continue=False,
                )
            )
            continue
        if declaration.checksum_sha256 is not None:
            actual = sha256_file(path)
            if actual != declaration.checksum_sha256:
                report.add(
                    ValidationFinding(
                        code=ValidationCode.FILE_CHECKSUM_MISMATCH,
                        severity=Severity.ERROR,
                        message="declared SHA-256 checksum does not match file content",
                        file=declaration.path,
                        field="checksum_sha256",
                        value=actual,
                        may_continue=False,
                    )
                )


def _validate_undeclared_files(
    root: Path,
    manifest: BundleManifest,
    report: ValidationReport,
) -> None:
    declared = {declaration.path for declaration in manifest.files.values()}
    allowed = declared | {"manifest.yaml", "seed.yaml"}
    for path in sorted(file for file in root.rglob("*") if file.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative not in allowed and path.name in EXPECTED_SOURCE_FILES:
            report.add(
                ValidationFinding(
                    code=ValidationCode.FILE_UNDECLARED_PRESENT,
                    severity=Severity.WARNING,
                    message=f"source file is present but not declared in manifest: {relative}",
                    file=relative,
                    may_continue=True,
                )
            )


def _validate_seed(
    root: Path,
    manifest: BundleManifest,
    report: ValidationReport,
) -> ScenarioSeed | None:
    seed_path = root / "seed.yaml"
    if not seed_path.exists():
        report.add(
            ValidationFinding(
                code=ValidationCode.SEED_MISSING,
                severity=Severity.FATAL,
                message="seed.yaml is required for Phase 2 bundles",
                file="seed.yaml",
                may_continue=False,
                affected_capabilities=["seed_provenance"],
            )
        )
        return None
    try:
        seed = load_seed(seed_path)
    except SeedIOError as exc:
        report.add(
            ValidationFinding(
                code=ValidationCode.SEED_MISSING,
                severity=Severity.FATAL,
                message=f"seed.yaml could not be loaded: {exc}",
                file="seed.yaml",
                may_continue=False,
                affected_capabilities=["seed_provenance"],
            )
        )
        return None
    if seed.seed_id != manifest.run.seed_id:
        report.add(
            ValidationFinding(
                code=ValidationCode.SEED_ID_MISMATCH,
                severity=Severity.ERROR,
                message="manifest run.seed_id does not match seed.yaml",
                file="seed.yaml",
                field="id",
                value=seed.seed_id,
                may_continue=False,
                affected_capabilities=["seed_provenance"],
            )
        )
    return seed


def _build_evidence_availability(
    manifest: BundleManifest,
    canonical: CanonicalTables,
    report: ValidationReport,
) -> EvidenceAvailability:
    file_errors = {
        finding.file
        for finding in report.findings
        if finding.file and finding.severity in {Severity.ERROR, Severity.FATAL}
    }

    def status(kind: str, table_count: int, filename: str) -> EvidenceStatus:
        if kind not in manifest.files:
            return EvidenceStatus.UNAVAILABLE
        if filename in file_errors:
            return EvidenceStatus.INVALID
        if table_count == 0:
            return EvidenceStatus.UNAVAILABLE
        warnings = {
            finding.file
            for finding in report.findings
            if finding.file == filename and finding.severity is Severity.WARNING
        }
        if warnings:
            return EvidenceStatus.PARTIAL
        return EvidenceStatus.AVAILABLE

    evidence = EvidenceAvailability(
        tasks=status("tasks", len(canonical.tasks), "tasks.csv"),
        infrastructure=status("infra_state", len(canonical.infrastructure), "infra_state.csv"),
        vehicles=status("vehicle_state", len(canonical.vehicles), "vehicle_state.csv"),
        traffic=status("traffic_obs", len(canonical.traffic), "traffic_obs.csv"),
        trips=status("trips", len(canonical.trips), "trips.csv"),
        incidents=status("incidents", len(canonical.incidents), "incidents.csv"),
    )
    diagnosis = (
        EvidenceStatus.AVAILABLE
        if evidence.tasks is EvidenceStatus.AVAILABLE
        and evidence.infrastructure is EvidenceStatus.AVAILABLE
        and not file_errors
        else EvidenceStatus.UNAVAILABLE
    )
    return evidence.model_copy(update={"diagnosis": diagnosis})


def _add_evidence_findings(evidence: EvidenceAvailability, report: ValidationReport) -> None:
    mapping = {
        "tasks": (
            evidence.tasks,
            ValidationCode.EVIDENCE_TASKS_UNAVAILABLE,
            "task evidence is unavailable",
        ),
        "infrastructure": (
            evidence.infrastructure,
            ValidationCode.EVIDENCE_INFRA_UNAVAILABLE,
            "infrastructure evidence is unavailable",
        ),
        "traffic": (
            evidence.traffic,
            ValidationCode.EVIDENCE_TRAFFIC_UNAVAILABLE,
            "traffic evidence is unavailable",
        ),
        "trips": (
            evidence.trips,
            ValidationCode.EVIDENCE_TRIPS_UNAVAILABLE,
            "trip evidence is unavailable",
        ),
    }
    for category, (status, code, message) in mapping.items():
        if status is EvidenceStatus.UNAVAILABLE:
            report.add(
                ValidationFinding(
                    code=code,
                    severity=Severity.WARNING,
                    message=message,
                    may_continue=True,
                    affected_capabilities=[category],
                )
            )
    if evidence.diagnosis is not EvidenceStatus.AVAILABLE:
        report.add(
            ValidationFinding(
                code=ValidationCode.EVIDENCE_INSUFFICIENT_FOR_DIAGNOSIS,
                severity=Severity.WARNING,
                message="validation/evidence state is insufficient for diagnostic hypotheses",
                may_continue=True,
                affected_capabilities=["diagnostic_rules"],
            )
        )
