"""UI-facing service layer over the tested TrafficTwin library."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from traffictwin.config.capabilities import CapabilityManifest, default_export_import_manifest
from traffictwin.config.seed_io import SeedIOError, dump_seed, load_seed
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.domain.enums import (
    Decision,
    FleetTierMix,
    RsuCapacityMode,
    TaskClass,
    WorkloadOrdering,
)
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import BundleValidationResult, import_bundle, validate_bundle
from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection
from traffictwin.rules.engine import evaluate_rules
from traffictwin.storage.registry import (
    BundleImportResult,
    Registry,
    RegistryConflictError,
    RegistrySummary,
)


@dataclass(frozen=True)
class ProjectStatus:
    """Project status shown on the Home page."""

    registry_path: Path
    registry_exists: bool
    registry_summary: RegistrySummary | None
    latest_runs: list[Run]
    capability_manifest: CapabilityManifest
    current_phase: str = "Phase 5 diagnostic prototype"
    canonical_design_version: str = "TrafficTwin v0.4"


@dataclass(frozen=True)
class BundleAnalysis:
    """Validated bundle plus derived UI artifacts."""

    source_path: Path
    validation: BundleValidationResult
    metrics: MetricCollection | None
    evidence_pack: EvidencePack | None
    diagnostic_report: DiagnosticReport | None

    @property
    def analysis_ready(self) -> bool:
        return self.validation.manifest is not None and self.validation.report.may_import


@dataclass(frozen=True)
class ServiceError:
    """User-facing service error with optional technical detail."""

    message: str
    detail: str | None = None


def load_project_status(registry_path: str | Path) -> ProjectStatus:
    """Load project and registry status for the Home page."""

    path = Path(registry_path)
    summary = Registry(path).inspect() if path.exists() else None
    return ProjectStatus(
        registry_path=path,
        registry_exists=path.exists(),
        registry_summary=summary,
        latest_runs=list_registered_runs(path)[:5] if path.exists() else [],
        capability_manifest=default_export_import_manifest(),
    )


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


def import_bundle_for_ui(path: str | Path, registry_path: str | Path) -> BundleImportResult:
    """Import a bundle into the registry using Phase 2 import behavior."""

    return import_bundle(path, registry_path)


def compute_run_metrics_for_ui(
    result: BundleValidationResult,
    config: MetricEngineConfig | None = None,
) -> MetricCollection:
    """Compute metrics through the Phase 3 engine."""

    return compute_metrics_for_bundle(result, config or MetricEngineConfig())


def build_evidence_pack_for_ui(
    result: BundleValidationResult,
    metrics: MetricCollection,
    config: MetricEngineConfig | None = None,
) -> EvidencePack:
    """Build an evidence pack through the Phase 3 evidence builder."""

    return build_evidence_pack(result, metrics, config or MetricEngineConfig())


def build_diagnostic_report_for_ui(pack: EvidencePack) -> DiagnosticReport:
    """Build deterministic diagnostics through the Phase 5 rules engine."""

    return evaluate_rules(pack)


def compare_runs_for_ui(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
) -> ComparisonReport | ServiceError:
    """Compare two analysis-ready bundles."""

    if baseline.metrics is None or variation.metrics is None:
        return ServiceError("Both baseline and variation must be accepted before comparison.")
    return compare_metric_collections(
        baseline.metrics,
        variation.metrics,
        baseline_seed=baseline.validation.seed,
        variation_seed=variation.validation.seed,
    )


def list_registered_runs(registry_path: str | Path) -> list[Run]:
    """List registered runs from the SQLite registry."""

    path = Path(registry_path)
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT payload FROM runs ORDER BY updated_at DESC, created_at DESC, run_id"
        ).fetchall()
    return [Run.model_validate_json(cast(str, row["payload"])) for row in rows]


def load_registered_metric_collection(
    registry_path: str | Path,
    run_id: str,
) -> MetricCollection | None:
    """Load a stored metric collection from the registry."""

    path = Path(registry_path)
    if not path.exists():
        return None
    try:
        payload = Registry(path).get_metric_collection_json(run_id)
    except Exception:
        return None
    return MetricCollection.model_validate_json(payload)


def store_metrics_for_ui(registry_path: str | Path, metrics: MetricCollection) -> bool:
    """Store metric collection JSON in the registry."""

    return Registry(registry_path).store_metric_collection(
        run_id=metrics.run_id,
        metric_version=metrics.metric_version,
        source_fingerprint=metrics.input_fingerprint,
        payload_json=metrics.model_dump_json(),
    )


def store_evidence_for_ui(registry_path: str | Path, pack: EvidencePack) -> bool:
    """Store evidence pack JSON in the registry."""

    return Registry(registry_path).store_evidence_pack(
        pack_id=pack.pack_id,
        run_id=str(pack.run_context.get("run_id", "unknown")),
        source_fingerprint=pack.source_bundle_fingerprint,
        payload_json=pack.to_json(),
    )


def export_seed_for_ui(seed: ScenarioSeed) -> str:
    """Serialise a seed through the Phase 1 seed I/O layer."""

    return dump_seed(seed)


def load_seed_for_ui(path: str | Path) -> ScenarioSeed | ServiceError:
    """Load a seed for the Scenario Studio."""

    try:
        return load_seed(path)
    except SeedIOError as exc:
        return ServiceError("Seed could not be loaded.", str(exc))


def build_seed_from_form(data: dict[str, object]) -> ScenarioSeed | ServiceError:
    """Validate a scenario seed draft from form data."""

    try:
        seed = ScenarioSeed.model_validate(
            {
                "id": str(data["seed_id"]),
                "name": str(data["name"]),
                "description": str(data["description"]),
                "base": str(data["parent_seed_id"]) or None,
                "preset_id": str(data["preset_id"]) or None,
                "demand": {"multiplier": _as_float(data["demand_multiplier"])},
                "workload": {
                    "birth_rate_multiplier": _as_float(data["birth_rate_multiplier"]),
                    "class_mix": {
                        TaskClass.T1.value: _as_float(data["class_mix_t1"]),
                        TaskClass.T2.value: _as_float(data["class_mix_t2"]),
                        TaskClass.T3.value: _as_float(data["class_mix_t3"]),
                    },
                    "ordering": WorkloadOrdering(str(data["workload_ordering"])).value,
                },
                "fleet": {
                    "count": _optional_int(data["fleet_count"]),
                    "tier_mix": FleetTierMix(str(data["fleet_tier_mix"])).value,
                },
                "infrastructure": {
                    "rsu_count": _optional_int(data["rsu_count"]),
                    "rsu_capacity_mode": RsuCapacityMode(str(data["rsu_capacity_mode"])).value,
                    "failed_rsus": _split_csv(str(data["failed_rsus"])),
                },
                "allowed_decisions": [
                    Decision(value).value for value in _as_str_list(data["allowed_decisions"])
                ],
                "policy": {
                    "algorithm": str(data["algorithm"]),
                    "checkpoint": str(data["checkpoint"]) or None,
                },
                "evaluation": {"random_seed": _as_int(data["random_seed"])},
                "compare_against": str(data["compare_against"]) or None,
                "provenance": {
                    "created_by": str(data["created_by"]),
                    "source": str(data["source"]),
                },
            }
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return ServiceError("Seed draft is invalid.", str(exc))
    return seed


def default_seed_form_data() -> dict[str, object]:
    """Return default Scenario Studio form values."""

    return {
        "seed_id": "s1-ui-demo",
        "name": "Synthetic UI demo seed",
        "description": "Synthetic seed drafted in TrafficTwin Scenario Studio.",
        "parent_seed_id": "s1-gridlock-baseline",
        "preset_id": "S1",
        "demand_multiplier": 1.0,
        "birth_rate_multiplier": 1.0,
        "class_mix_t1": 0.30,
        "class_mix_t2": 0.30,
        "class_mix_t3": 0.40,
        "workload_ordering": WorkloadOrdering.MIXED.value,
        "fleet_count": "",
        "fleet_tier_mix": FleetTierMix.MIXED.value,
        "rsu_count": 2,
        "rsu_capacity_mode": RsuCapacityMode.STANDARD.value,
        "failed_rsus": "",
        "allowed_decisions": [Decision.LOCAL.value, Decision.V2I.value, Decision.V2V.value],
        "algorithm": "MAPPO",
        "checkpoint": "",
        "random_seed": 7,
        "compare_against": "",
        "created_by": "Abdulla Al Mamun Akash",
        "source": "TrafficTwin Scenario Studio",
    }


def register_seed_for_ui(seed: ScenarioSeed, registry_path: str | Path) -> ServiceError | None:
    """Register a seed in the metadata registry."""

    try:
        Registry(registry_path).add_seed(seed)
    except Exception as exc:
        return ServiceError("Seed could not be registered.", str(exc))
    return None


def safe_import_bundle_for_ui(
    path: str | Path,
    registry_path: str | Path,
) -> BundleImportResult | ServiceError:
    """Import a bundle and return user-facing conflicts."""

    try:
        return import_bundle_for_ui(path, registry_path)
    except RegistryConflictError as exc:
        return ServiceError("Bundle import conflict.", str(exc))


def _optional_int(value: object) -> int | None:
    if value in {"", None}:
        return None
    return _as_int(value)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _as_float(value: object) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return float(str(value))


def _as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return int(str(value))


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
