"""Bundle validation, import, streaming, manifest inference, SUMO, and replay services."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from traffictwin.ingestion.batch import (
    BatchBundleSummary,
    import_bundle_batch,
    validate_bundle_batch,
)
from traffictwin.ingestion.bundle import (
    StreamingBundleImportResult,
    import_bundle,
    import_bundle_streaming,
    validate_bundle,
    validate_bundle_streaming,
)
from traffictwin.ingestion.manifest_inference import (
    CanonicalisationManifest,
    ManifestInferenceDraft,
    ManifestInferenceError,
    ManifestInferenceSelections,
    apply_canonicalisation_to_template,
    bundle_manifest_to_yaml,
    confirm_manifest_inference,
    infer_manifest,
)
from traffictwin.ingestion.streaming import (
    StreamingBundleValidationResult,
    StreamingCanonicalisationConfig,
)
from traffictwin.integration.sumo import (
    SumoAnalysis,
    SumoImportResult,
    compute_metrics_for_sumo,
    import_sumo_results,
    validate_sumo_results,
)
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.storage.registry import (
    BundleImportResult,
    RegistryConflictError,
)
from traffictwin.ui.services.metrics import (
    build_diagnostic_report_for_ui,
    build_evidence_pack_for_ui,
    compute_run_metrics_for_ui,
)
from traffictwin.ui.services.models import BundleAnalysis, ReplayBundleChoice, ServiceError


def validate_bundle_for_ui(
    path: str | Path,
    config: MetricEngineConfig | None = None,
) -> BundleAnalysis:
    """Validate a bundle and compute Phase 3 artifacts when safe."""

    source = Path(path)
    result = validate_bundle(source)
    if result.manifest is None or not result.report.may_import:
        return BundleAnalysis(source, result, None, None, None)
    metrics = compute_run_metrics_for_ui(result, config)
    evidence = build_evidence_pack_for_ui(result, metrics, config)
    diagnostic_report = build_diagnostic_report_for_ui(evidence)
    return BundleAnalysis(source, result, metrics, evidence, diagnostic_report)


def validate_bundle_batch_for_ui(inputs: list[str | Path]) -> BatchBundleSummary:
    """Validate an explicit batch through the shared deterministic service."""

    return validate_bundle_batch(inputs)


def import_bundle_batch_for_ui(
    inputs: list[str | Path],
    registry_path: str | Path,
) -> BatchBundleSummary:
    """Import accepted batch candidates with per-bundle transaction isolation."""

    return import_bundle_batch(inputs, registry_path)


def validate_bundle_streaming_for_ui(
    path: str | Path,
    *,
    chunk_rows: int,
) -> StreamingBundleValidationResult | ServiceError:
    """Validate a large bundle through the shared bounded streaming service."""

    try:
        return validate_bundle_streaming(
            path,
            config=StreamingCanonicalisationConfig(chunk_rows=chunk_rows),
        )
    except (OSError, ValueError) as exc:
        return ServiceError("Streaming bundle validation could not be completed.", str(exc))


def import_bundle_streaming_for_ui(
    path: str | Path,
    registry_path: str | Path,
    *,
    chunk_rows: int,
) -> StreamingBundleImportResult | ServiceError:
    """Validate by chunks and register metadata with ordinary conflict semantics."""

    try:
        return import_bundle_streaming(
            path,
            registry_path,
            config=StreamingCanonicalisationConfig(chunk_rows=chunk_rows),
        )
    except (OSError, ValueError, RegistryConflictError) as exc:
        return ServiceError("Streaming bundle import could not be completed.", str(exc))


def infer_manifest_for_ui(path: str | Path) -> ManifestInferenceDraft | ServiceError:
    """Return deterministic, non-executable CSV mapping suggestions."""

    try:
        return infer_manifest(path)
    except (OSError, ValueError) as exc:
        return ServiceError("CSV manifest inference could not be completed.", str(exc))


def confirm_manifest_inference_for_ui(
    draft: ManifestInferenceDraft,
    source: str | Path,
    *,
    confirmed_by: str,
    selections: ManifestInferenceSelections,
) -> CanonicalisationManifest | ServiceError:
    """Confirm the explicit mappings selected in the Streamlit wizard."""

    try:
        return confirm_manifest_inference(
            draft,
            source,
            confirmed_by=confirmed_by,
            accept_suggestions=True,
            selections=selections,
        )
    except (ManifestInferenceError, OSError, ValueError) as exc:
        return ServiceError("Mapping selections could not be confirmed.", str(exc))


def manifest_file_fragment_for_ui(canonicalisation: CanonicalisationManifest) -> str:
    """Render confirmed file declarations as a YAML fragment."""

    payload = {
        "files": {
            kind: declaration.model_dump(mode="json", exclude_none=True)
            for kind, declaration in canonicalisation.file_declarations().items()
        }
    }
    return yaml.safe_dump(payload, sort_keys=False)


def apply_manifest_inference_for_ui(
    canonicalisation: CanonicalisationManifest,
    template_path: str | Path,
) -> str | ServiceError:
    """Apply confirmed mappings to a complete metadata template for download."""

    try:
        raw = yaml.safe_load(Path(template_path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ManifestInferenceError("bundle manifest template must contain a mapping")
        manifest = apply_canonicalisation_to_template(canonicalisation, raw)
        return bundle_manifest_to_yaml(manifest)
    except (ManifestInferenceError, OSError, yaml.YAMLError, ValidationError) as exc:
        return ServiceError("Confirmed mappings could not be applied to the template.", str(exc))


def validate_sumo_for_ui(
    path: str | Path,
    config: MetricEngineConfig | None = None,
) -> SumoAnalysis | ServiceError:
    """Validate SUMO outputs and compute only supported canonical metrics."""

    try:
        validation = validate_sumo_results(path)
        if validation.manifest is None or not validation.report.may_import:
            return SumoAnalysis(validation=validation)
        return SumoAnalysis(
            validation=validation,
            metrics=compute_metrics_for_sumo(validation, config),
        )
    except (OSError, ValueError) as exc:
        return ServiceError("SUMO result package could not be analysed.", str(exc))


def import_sumo_for_ui(
    path: str | Path,
    registry_path: str | Path,
    analysis: SumoAnalysis,
    config: MetricEngineConfig | None = None,
) -> SumoImportResult | ServiceError:
    """Import already validated SUMO results through the registry service."""

    try:
        return import_sumo_results(
            path,
            registry_path,
            validation_result=analysis.validation,
            metric_config=config,
        )
    except (OSError, ValueError, RegistryConflictError) as exc:
        return ServiceError("SUMO result package could not be imported.", str(exc))


def list_replay_bundles_for_ui(
    root: str | Path,
    *,
    current_path: str | Path | None = None,
) -> list[ReplayBundleChoice]:
    """Return valid top-level bundles available to the historical replay page."""

    root_path = Path(root)
    candidates = {
        manifest.parent for manifest in root_path.glob("*/manifest.yaml") if manifest.is_file()
    }
    if (root_path / "manifest.yaml").is_file():
        candidates.add(root_path)
    if current_path is not None:
        current = Path(current_path)
        if (current / "manifest.yaml").is_file():
            candidates.add(current)

    choices: list[ReplayBundleChoice] = []
    for path in sorted(candidates, key=lambda item: str(item)):
        result = validate_bundle(path)
        if result.manifest is None or not result.report.may_import:
            continue
        choices.append(
            ReplayBundleChoice(
                path=path,
                vehicle_count=len({vehicle.vehicle_id for vehicle in result.canonical.vehicles}),
                incident_count=len(result.canonical.incidents),
                incident_types=tuple(
                    sorted({incident.incident_type for incident in result.canonical.incidents})
                ),
            )
        )
    return choices


def import_bundle_for_ui(path: str | Path, registry_path: str | Path) -> BundleImportResult:
    """Import a bundle into the registry using Phase 2 import behavior."""

    return import_bundle(path, registry_path)


def safe_import_bundle_for_ui(
    path: str | Path,
    registry_path: str | Path,
) -> BundleImportResult | ServiceError:
    """Import a bundle and return user-facing conflicts."""

    try:
        return import_bundle_for_ui(path, registry_path)
    except RegistryConflictError as exc:
        return ServiceError("Bundle import conflict.", str(exc))
