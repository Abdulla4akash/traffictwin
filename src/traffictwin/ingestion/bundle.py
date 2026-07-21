"""High-level run-bundle validation and import orchestration."""

from __future__ import annotations

import zipfile
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
from traffictwin.ingestion.cache import (
    CanonicalCacheError,
    CanonicalCacheProbe,
    CanonicalCacheState,
    CanonicalCacheStatus,
    canonical_cache_key,
    probe_canonical_cache,
    unavailable_cache_status,
    validate_cache_location,
    write_canonical_cache,
    write_failed_cache_status,
)
from traffictwin.ingestion.canonicalise import canonicalise_bundle
from traffictwin.ingestion.hashes import bundle_fingerprint, sha256_file
from traffictwin.ingestion.loader import BundleLoadError, open_bundle
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.ingestion.streaming import (
    CanonicalChunk,
    CanonicalChunkConsumer,
    StreamingBundleValidationResult,
    StreamingCanonicalisationConfig,
    StreamingCanonicalisationSummary,
    canonicalise_bundle_streaming,
)
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
    "tasks.csv.gz",
    "infra_state.csv.gz",
    "vehicle_state.csv.gz",
    "traffic_obs.csv.gz",
    "trips.csv.gz",
    "incidents.csv.gz",
    "tasks.parquet",
    "infra_state.parquet",
    "vehicle_state.parquet",
    "traffic_obs.parquet",
    "trips.parquet",
    "incidents.parquet",
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


@dataclass(frozen=True)
class CachedBundleValidationResult:
    """Ordinary validation semantics plus one explicit OPS-02 cache receipt."""

    validation: BundleValidationResult
    cache: CanonicalCacheStatus


@dataclass(frozen=True)
class CollectedStreamingBundleResult:
    """Accepted streaming chunks collected for exact downstream-equivalence checks."""

    validation: BundleValidationResult
    streaming: StreamingCanonicalisationSummary


@dataclass(frozen=True)
class StreamingBundleImportResult:
    """Streaming validation plus ordinary registry registration outcome."""

    validation: StreamingBundleValidationResult
    registry: BundleImportResult


def validate_bundle(path: str | Path) -> BundleValidationResult:
    """Validate a directory or ZIP run bundle."""

    source = Path(path)
    report = ValidationReport()

    try:
        with open_bundle(source) as workspace:
            files = [file for file in workspace.root.rglob("*") if file.is_file()]
            fingerprint = bundle_fingerprint(files, workspace.root)
            manifest = _load_manifest(workspace.root, report)
            return _validate_open_workspace(
                source,
                workspace.root,
                fingerprint,
                manifest,
                report,
            )
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
    return _finalise_bundle_validation(
        source=source,
        fingerprint=None,
        manifest=None,
        seed=None,
        canonical=CanonicalTables(),
        evidence=EvidenceAvailability(),
        report=report,
    )


def validate_bundle_cached(
    path: str | Path,
    cache_root: str | Path,
) -> CachedBundleValidationResult:
    """Validate with exact raw re-fingerprinting and fail-closed canonical-cache reuse."""

    source = Path(path)
    resolved_cache = validate_cache_location(source, Path(cache_root))
    report = ValidationReport()
    probe: CanonicalCacheProbe | None = None

    try:
        with open_bundle(source) as workspace:
            files = [file for file in workspace.root.rglob("*") if file.is_file()]
            fingerprint = bundle_fingerprint(files, workspace.root)
            manifest = _load_manifest(workspace.root, report)
            if manifest is not None:
                key = canonical_cache_key(fingerprint, manifest)
                probe = probe_canonical_cache(resolved_cache, key, manifest=manifest)
                if probe.payload is not None:
                    metadata = probe.payload.metadata
                    return CachedBundleValidationResult(
                        validation=BundleValidationResult(
                            source=source,
                            fingerprint=fingerprint,
                            manifest=metadata.manifest,
                            seed=metadata.seed,
                            canonical=probe.payload.canonical,
                            evidence=metadata.evidence,
                            insufficient_evidence=metadata.insufficient_evidence,
                            report=metadata.report,
                        ),
                        cache=probe.status,
                    )
            result = _validate_open_workspace(
                source,
                workspace.root,
                fingerprint,
                manifest,
                report,
            )
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
        result = _finalise_bundle_validation(
            source=source,
            fingerprint=None,
            manifest=None,
            seed=None,
            canonical=CanonicalTables(),
            evidence=EvidenceAvailability(),
            report=report,
        )

    if (
        probe is None
        or result.manifest is None
        or result.seed is None
        or result.fingerprint is None
    ):
        return CachedBundleValidationResult(
            validation=result,
            cache=unavailable_cache_status(
                "a complete valid manifest, seed, and raw fingerprint are required"
            ),
        )
    if probe.status.state is not CanonicalCacheState.MISS:
        return CachedBundleValidationResult(validation=result, cache=probe.status)
    if not result.report.may_import:
        return CachedBundleValidationResult(
            validation=result,
            cache=unavailable_cache_status(
                "rejected validation results are not cached",
                canonical_cache_key(result.fingerprint, result.manifest),
            ),
        )
    key = canonical_cache_key(result.fingerprint, result.manifest)
    try:
        written = write_canonical_cache(
            resolved_cache,
            key,
            manifest=result.manifest,
            seed=result.seed,
            canonical=result.canonical,
            evidence=result.evidence,
            insufficient_evidence=result.insufficient_evidence,
            report=result.report,
        )
    except (CanonicalCacheError, OSError) as exc:
        return CachedBundleValidationResult(
            validation=result,
            cache=write_failed_cache_status(str(exc), resolved_cache, key),
        )
    return CachedBundleValidationResult(validation=result, cache=written.status)


def inspect_bundle_cache(
    path: str | Path,
    cache_root: str | Path,
) -> CanonicalCacheStatus:
    """Inspect one expected cache entry without canonicalising or writing anything."""

    source = Path(path)
    resolved_cache = validate_cache_location(source, Path(cache_root))
    report = ValidationReport()
    try:
        with open_bundle(source) as workspace:
            files = [file for file in workspace.root.rglob("*") if file.is_file()]
            fingerprint = bundle_fingerprint(files, workspace.root)
            manifest = _load_manifest(workspace.root, report)
            if manifest is None:
                return unavailable_cache_status("raw manifest is missing or invalid")
            key = canonical_cache_key(fingerprint, manifest)
            return probe_canonical_cache(resolved_cache, key, manifest=manifest).status
    except BundleLoadError as exc:
        return unavailable_cache_status(str(exc))


def _validate_open_workspace(
    source: Path,
    root: Path,
    fingerprint: str,
    manifest: BundleManifest | None,
    report: ValidationReport,
) -> BundleValidationResult:
    canonical = CanonicalTables()
    seed: ScenarioSeed | None = None
    evidence = EvidenceAvailability()
    if manifest is not None:
        report.bundle_id = manifest.bundle.bundle_id
        report.run_id = manifest.run.run_id
        _validate_environment(manifest, report)
        _validate_declared_files(root, manifest, report)
        _validate_undeclared_files(root, manifest, report)
        seed = _validate_seed(root, manifest, report)
        canonical = canonicalise_bundle(root, manifest, report)
        report.canonical_record_counts = canonical.record_counts()
        evidence = _build_evidence_availability(manifest, canonical, report)
        _add_evidence_findings(evidence, report)
    return _finalise_bundle_validation(
        source=source,
        fingerprint=fingerprint,
        manifest=manifest,
        seed=seed,
        canonical=canonical,
        evidence=evidence,
        report=report,
    )


def _finalise_bundle_validation(
    *,
    source: Path,
    fingerprint: str | None,
    manifest: BundleManifest | None,
    seed: ScenarioSeed | None,
    canonical: CanonicalTables,
    evidence: EvidenceAvailability,
    report: ValidationReport,
) -> BundleValidationResult:
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


def validate_bundle_streaming(
    path: str | Path,
    *,
    config: StreamingCanonicalisationConfig | None = None,
    consumer: CanonicalChunkConsumer | None = None,
) -> StreamingBundleValidationResult:
    """Validate and emit canonical chunks without retaining all canonical rows."""

    active_config = config or StreamingCanonicalisationConfig()
    source = Path(path)
    report = ValidationReport()
    manifest: BundleManifest | None = None
    seed: ScenarioSeed | None = None
    evidence = EvidenceAvailability()
    fingerprint: str | None = None
    streaming = _empty_streaming_summary(active_config)

    try:
        with open_bundle(
            source,
            max_uncompressed_bytes=active_config.max_bundle_uncompressed_bytes,
        ) as workspace:
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
                streaming = canonicalise_bundle_streaming(
                    workspace.root,
                    manifest,
                    report,
                    config=active_config,
                    consumer=consumer,
                )
                report.canonical_record_counts = streaming.canonical_record_counts
                evidence = _build_evidence_availability_from_counts(
                    manifest,
                    streaming.canonical_record_counts,
                    report,
                )
                _add_evidence_findings(evidence, report)
    except (BundleLoadError, OSError, zipfile.BadZipFile) as exc:
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
    return StreamingBundleValidationResult(
        source=source,
        fingerprint=fingerprint,
        manifest=manifest,
        seed=seed,
        streaming=streaming,
        evidence=evidence,
        insufficient_evidence=insufficient,
        report=report,
    )


def collect_bundle_streaming(
    path: str | Path,
    *,
    config: StreamingCanonicalisationConfig | None = None,
) -> CollectedStreamingBundleResult:
    """Collect streaming chunks for equivalence testing and ordinary downstream analysis."""

    canonical = CanonicalTables()

    def collect(chunk: CanonicalChunk) -> None:
        canonical.tasks.extend(chunk.canonical.tasks)
        canonical.infrastructure.extend(chunk.canonical.infrastructure)
        canonical.vehicles.extend(chunk.canonical.vehicles)
        canonical.traffic.extend(chunk.canonical.traffic)
        canonical.trips.extend(chunk.canonical.trips)
        canonical.incidents.extend(chunk.canonical.incidents)

    result = validate_bundle_streaming(path, config=config, consumer=collect)
    validation = BundleValidationResult(
        source=result.source,
        fingerprint=result.fingerprint,
        manifest=result.manifest,
        seed=result.seed,
        canonical=canonical,
        evidence=result.evidence,
        insufficient_evidence=result.insufficient_evidence,
        report=result.report,
    )
    return CollectedStreamingBundleResult(validation=validation, streaming=result.streaming)


def import_bundle_streaming(
    path: str | Path,
    registry_path: str | Path,
    *,
    config: StreamingCanonicalisationConfig | None = None,
) -> StreamingBundleImportResult:
    """Validate through bounded chunks, then apply ordinary registry import semantics."""

    validation = validate_bundle_streaming(path, config=config)
    registry = import_validated_bundle(
        BundleValidationResult(
            source=validation.source,
            fingerprint=validation.fingerprint,
            manifest=validation.manifest,
            seed=validation.seed,
            canonical=CanonicalTables(),
            evidence=validation.evidence,
            insufficient_evidence=validation.insufficient_evidence,
            report=validation.report,
        ),
        registry_path,
    )
    return StreamingBundleImportResult(validation=validation, registry=registry)


def import_bundle(path: str | Path, registry_path: str | Path) -> BundleImportResult:
    """Validate and register an accepted bundle."""

    return import_validated_bundle(validate_bundle(path), registry_path)


def import_validated_bundle(
    result: BundleValidationResult,
    registry_path: str | Path,
) -> BundleImportResult:
    """Register one already validated result without changing import semantics."""

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
        source_bundle=str(result.source),
        validation_status=ValidationStatus.VALID,
    )
    return Registry(registry_path).register_bundle_import(
        run=run,
        bundle_id=manifest.bundle.bundle_id,
        source_reference=str(result.source),
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
    return _build_evidence_availability_from_counts(manifest, canonical.record_counts(), report)


def _build_evidence_availability_from_counts(
    manifest: BundleManifest,
    canonical_counts: dict[str, int],
    report: ValidationReport,
) -> EvidenceAvailability:
    file_errors = {
        finding.file
        for finding in report.findings
        if finding.file and finding.severity in {Severity.ERROR, Severity.FATAL}
    }

    def status(kind: str, table_count: int) -> EvidenceStatus:
        declaration = manifest.files.get(kind)
        if declaration is None:
            return EvidenceStatus.UNAVAILABLE
        filename = declaration.path
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
        tasks=status("tasks", canonical_counts.get("tasks", 0)),
        infrastructure=status("infra_state", canonical_counts.get("infrastructure", 0)),
        vehicles=status("vehicle_state", canonical_counts.get("vehicles", 0)),
        traffic=status("traffic_obs", canonical_counts.get("traffic", 0)),
        trips=status("trips", canonical_counts.get("trips", 0)),
        incidents=status("incidents", canonical_counts.get("incidents", 0)),
    )
    diagnosis = (
        EvidenceStatus.AVAILABLE
        if evidence.tasks is EvidenceStatus.AVAILABLE
        and evidence.infrastructure is EvidenceStatus.AVAILABLE
        and not file_errors
        else EvidenceStatus.UNAVAILABLE
    )
    return evidence.model_copy(update={"diagnosis": diagnosis})


def _empty_streaming_summary(
    config: StreamingCanonicalisationConfig,
) -> StreamingCanonicalisationSummary:
    return StreamingCanonicalisationSummary(
        config=config,
        chunk_count=0,
        files_processed=[],
        source_row_counts=dict.fromkeys(manifest_source_kinds(), 0),
        canonical_record_counts=CanonicalTables().record_counts(),
        max_observed_chunk_source_rows=0,
        max_observed_chunk_canonical_records=0,
        max_observed_chunk_decoded_bytes=0,
    )


def manifest_source_kinds() -> tuple[str, ...]:
    """Return source table kinds in the canonical manifest contract."""

    return ("tasks", "infra_state", "vehicle_state", "traffic_obs", "trips", "incidents")


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
