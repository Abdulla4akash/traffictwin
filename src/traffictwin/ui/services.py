"""UI-facing service layer over the tested TrafficTwin library."""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import ValidationError

from traffictwin.config.capabilities import CapabilityManifest, default_export_import_manifest
from traffictwin.config.seed_io import SeedIOError, dump_seed, load_seed
from traffictwin.demo.workspace import WorkspaceStatus, workspace_status
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
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection
from traffictwin.provenance.models import ProvenanceTrace, SourceRowPreview
from traffictwin.provenance.query import (
    ProvenanceContext,
    get_metric_provenance,
    get_rule_provenance,
    get_run_provenance,
    get_source_provenance,
)
from traffictwin.release.metadata import current_release_metadata
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.rules.catalogue import rule_catalogue
from traffictwin.rules.engine import evaluate_rules
from traffictwin.storage.registry import (
    BundleImportResult,
    Registry,
    RegistryConflictError,
    RegistrySummary,
)
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import (
    SYNTHETIC_GENERATOR_VERSION,
    SyntheticPolicyProfile,
    SyntheticScenarioConfig,
)
from traffictwin.synthetic.scenarios import list_preset_names, preset_config


@dataclass(frozen=True)
class ProjectStatus:
    """Project status shown on the Home page."""

    registry_path: Path
    registry_exists: bool
    registry_summary: RegistrySummary | None
    latest_runs: list[Run]
    capability_manifest: CapabilityManifest
    current_phase: str = "Standalone product polish prototype"
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


@dataclass(frozen=True)
class ReportEntry:
    """Report file metadata for the report dashboard."""

    path: Path
    name: str
    report_type: str
    format_label: str
    modified_at: str
    size_bytes: int
    scenario_hint: str | None = None


@dataclass(frozen=True)
class ExperimentManagerView:
    """Read-only experiment manager view model."""

    registry_path: Path
    workspace: WorkspaceStatus | None
    experiments: list[dict[str, object]]
    runs: list[dict[str, object]]
    seeds: list[dict[str, object]]
    policies: list[str]
    bundle_imports: list[dict[str, object]]
    comparisons: list[dict[str, object]]
    reports: list[ReportEntry]
    metrics_by_run: dict[str, int]
    evidence_by_run: dict[str, int]


@dataclass(frozen=True)
class SearchHit:
    """Simple deterministic search result."""

    category: str
    title: str
    detail: str
    reference: str


@dataclass(frozen=True)
class ScenarioPreview:
    """Scenario-builder preview without generating files."""

    config: SyntheticScenarioConfig
    expected_bundle_id: str
    expected_run_id: str
    expected_files: list[str]
    summary_rows: list[dict[str, object]]


@dataclass(frozen=True)
class ScenarioGenerationResult:
    """Result of generating and validating one synthetic bundle."""

    bundle_path: Path
    analysis: BundleAnalysis


@dataclass(frozen=True)
class AboutInfo:
    """Version and build metadata for the About page."""

    package_version: str
    generator_version: str
    metric_version: str
    diagnostic_version: str
    provenance_version: str
    python_version: str
    licence: str
    commit_hash: str | None


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


def synthetic_preset_names_for_ui() -> list[str]:
    """Return synthetic presets available to the Scenario Builder."""

    return list_preset_names()


def synthetic_policy_options_for_ui() -> list[str]:
    """Return documented synthetic policy labels."""

    return [profile.value for profile in SyntheticPolicyProfile]


def preset_config_for_ui(name: str, *, random_seed: int = 7) -> SyntheticScenarioConfig:
    """Return a preset config for UI editing."""

    return preset_config(name, random_seed=random_seed)


def build_synthetic_config_from_form(
    data: dict[str, object],
) -> SyntheticScenarioConfig | ServiceError:
    """Validate Scenario Builder form data with the generator config model."""

    try:
        config = SyntheticScenarioConfig.model_validate(
            {
                "scenario_id": str(data["scenario_id"]),
                "name": str(data["name"]),
                "description": str(data["description"]),
                "experiment_id": str(data.get("experiment_id") or "exp-standalone-demo"),
                "baseline_seed_id": str(data.get("baseline_seed_id") or "") or None,
                "random_seed": _as_int(data["random_seed"]),
                "duration_s": _as_float(data["duration_s"]),
                "sampling_interval_s": _as_float(data["sampling_interval_s"]),
                "vehicle_count": _as_int(data["vehicle_count"]),
                "vehicle_tier_mix": {
                    "low": _as_float(data["vehicle_low_share"]),
                    "medium": _as_float(data["vehicle_medium_share"]),
                    "high": _as_float(data["vehicle_high_share"]),
                },
                "task_arrival_rate": _as_float(data["task_arrival_rate"]),
                "task_class_mix": {
                    TaskClass.T1.value: _as_float(data["task_mix_t1"]),
                    TaskClass.T2.value: _as_float(data["task_mix_t2"]),
                    TaskClass.T3.value: _as_float(data["task_mix_t3"]),
                },
                "rsu_count": _as_int(data["rsu_count"]),
                "rsu_capacity": _as_float(data["rsu_capacity"]),
                "baseline_network_delay_ms": _as_float(data["baseline_network_delay_ms"]),
                "congestion_multiplier": _as_float(data["congestion_multiplier"]),
                "policy_behavior": str(data["policy_behavior"]),
                "trip_count": _as_int(data["trip_count"]),
                "synthetic_faults": _split_csv(str(data.get("synthetic_faults", ""))),
                "include_infrastructure": bool(data.get("include_infrastructure", True)),
                "include_vehicles": bool(data.get("include_vehicles", True)),
                "include_traffic": bool(data.get("include_traffic", True)),
                "include_trips": bool(data.get("include_trips", True)),
                "include_incidents": bool(data.get("include_incidents", True)),
            }
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return ServiceError("Synthetic scenario configuration is invalid.", str(exc))
    return config


def scenario_config_to_yaml(config: SyntheticScenarioConfig) -> str:
    """Return deterministic YAML for a synthetic generator configuration."""

    return yaml.safe_dump(
        config.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=False,
    )


def preview_synthetic_scenario(config: SyntheticScenarioConfig) -> ScenarioPreview:
    """Return a file and metadata preview without writing a bundle."""

    expected_files = ["manifest.yaml", "seed.yaml", "tasks.csv"]
    if config.include_infrastructure:
        expected_files.append("infra_state.csv")
    if config.include_vehicles:
        expected_files.append("vehicle_state.csv")
    if config.include_traffic:
        expected_files.append("traffic_obs.csv")
    if config.include_trips:
        expected_files.append("trips.csv")
    if config.include_incidents:
        expected_files.append("incidents.csv")
    summary: list[dict[str, object]] = [
        {"field": "scenario_id", "value": config.scenario_id},
        {"field": "random_seed", "value": config.random_seed},
        {"field": "policy_profile", "value": config.policy_behavior.value},
        {"field": "vehicle_count", "value": config.vehicle_count},
        {"field": "task_arrival_rate", "value": config.task_arrival_rate},
        {"field": "rsu_count", "value": config.rsu_count},
        {"field": "rsu_capacity", "value": config.rsu_capacity},
        {"field": "synthetic_faults", "value": ", ".join(config.synthetic_faults) or "none"},
    ]
    return ScenarioPreview(
        config=config,
        expected_bundle_id=f"bundle-{config.scenario_id}-{config.random_seed}",
        expected_run_id=f"run-{config.scenario_id}-{config.random_seed}",
        expected_files=expected_files,
        summary_rows=summary,
    )


def generate_synthetic_bundle_for_ui(
    config: SyntheticScenarioConfig,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ScenarioGenerationResult | ServiceError:
    """Generate a synthetic bundle and validate it through Phase 2 services."""

    try:
        bundle_path = write_synthetic_bundle(config, output_dir, overwrite=overwrite)
        analysis = validate_bundle_for_ui(bundle_path)
    except Exception as exc:
        return ServiceError("Synthetic bundle could not be generated.", str(exc))
    return ScenarioGenerationResult(bundle_path=bundle_path, analysis=analysis)


def load_experiment_manager_view(
    registry_path: str | Path,
    workspace_path: str | Path | None = None,
) -> ExperimentManagerView:
    """Build a read-only local experiment manager catalogue."""

    path = Path(registry_path)
    experiments = _registry_payload_rows(path, "experiments", "experiment_id")
    runs = _registry_payload_rows(path, "runs", "run_id")
    seeds = _registry_payload_rows(path, "seeds", "seed_id")
    bundle_imports = _registry_bundle_rows(path)
    metrics_by_run = _registry_count_by_run(path, "metric_collections")
    evidence_by_run = _registry_count_by_run(path, "evidence_packs")
    policies = sorted({str(row.get("algorithm", "")) for row in runs if row.get("algorithm")})
    reports = list_workspace_reports(workspace_path) if workspace_path else []
    return ExperimentManagerView(
        registry_path=path,
        workspace=workspace_status(workspace_path) if workspace_path else None,
        experiments=experiments,
        runs=runs,
        seeds=seeds,
        policies=policies,
        bundle_imports=bundle_imports,
        comparisons=_workspace_comparisons(Path(workspace_path)) if workspace_path else [],
        reports=reports,
        metrics_by_run=metrics_by_run,
        evidence_by_run=evidence_by_run,
    )


def list_workspace_reports(workspace_path: str | Path | None) -> list[ReportEntry]:
    """Return report files from a standalone workspace."""

    if workspace_path is None:
        return []
    report_dir = Path(workspace_path) / "reports"
    if not report_dir.exists():
        return []
    entries: list[ReportEntry] = []
    for path in sorted(report_dir.glob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".md", ".html"}:
            continue
        stat = path.stat()
        entries.append(
            ReportEntry(
                path=path,
                name=path.name,
                report_type=_infer_report_type(path.name),
                format_label="HTML" if suffix == ".html" else "Markdown",
                modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                size_bytes=stat.st_size,
                scenario_hint=_scenario_hint(path.name),
            )
        )
    return entries


def regenerate_report_for_ui(
    report_type: Literal["run", "compare", "diagnostics", "full"],
    primary_path: str | Path,
    output_path: str | Path,
    *,
    secondary_path: str | Path | None = None,
) -> Path | ServiceError:
    """Generate a deterministic report through the existing reporting layer."""

    output = Path(output_path)
    try:
        if report_type == "run":
            report = build_run_report(primary_path)
        elif report_type == "compare":
            if secondary_path is None:
                return ServiceError("Comparison report requires a variation bundle path.")
            report = build_comparison_report(primary_path, secondary_path)
        elif report_type == "diagnostics":
            report = build_diagnostics_report(primary_path)
        elif report_type == "full":
            report = build_full_report(primary_path, comparison_baseline=secondary_path)
        else:
            return ServiceError("Unsupported report type.", report_type)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            report_to_html(report)
            if output.suffix.lower() == ".html"
            else report_to_markdown(report)
        )
        output.write_text(payload, encoding="utf-8")
    except Exception as exc:
        return ServiceError("Report could not be generated.", str(exc))
    return output


def search_for_ui(
    query: str,
    registry_path: str | Path,
    workspace_path: str | Path | None = None,
) -> list[SearchHit]:
    """Search local metadata, reports, metrics, rules, and source files."""

    needle = query.strip().lower()
    if not needle:
        return []
    view = load_experiment_manager_view(registry_path, workspace_path)
    hits: list[SearchHit] = []
    for row in view.experiments:
        _append_hit(hits, needle, "experiment", str(row.get("experiment_id", "")), row)
    for row in view.runs:
        _append_hit(hits, needle, "run", str(row.get("run_id", "")), row)
    for row in view.seeds:
        _append_hit(hits, needle, "seed", str(row.get("seed_id", "")), row)
    for report in view.reports:
        _append_hit(
            hits,
            needle,
            "report",
            report.name,
            {
                "path": _safe_display_path(report.path),
                "type": report.report_type,
                "format": report.format_label,
            },
        )
    for key, definition in metric_catalogue().items():
        _append_hit(
            hits,
            needle,
            "metric",
            key,
            {"name": definition.human_name, "domain": definition.domain.value},
        )
    for key, rule_definition in rule_catalogue().items():
        _append_hit(
            hits,
            needle,
            "rule",
            key,
            {"title": rule_definition.title, "version": rule_definition.rule_version},
        )
    if workspace_path is not None:
        for path in sorted((Path(workspace_path) / "bundles").rglob("*.csv")):
            _append_hit(
                hits,
                needle,
                "source_file",
                path.name,
                {"path": _safe_display_path(path)},
            )
    return sorted(hits, key=lambda hit: (hit.category, hit.title, hit.reference))


def about_info_for_ui() -> AboutInfo:
    """Return project metadata for the About page."""

    metadata = current_release_metadata()
    return AboutInfo(
        package_version=metadata.version,
        generator_version=SYNTHETIC_GENERATOR_VERSION,
        metric_version=MetricEngineConfig().metric_version,
        diagnostic_version="ruleset-1.0",
        provenance_version="1.0",
        python_version=sys.version.split()[0],
        licence=metadata.licence_status,
        commit_hash=_git_commit_hash(),
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


def provenance_context_for_ui(analysis: BundleAnalysis) -> ProvenanceContext:
    """Build a read-only provenance context from already computed UI artifacts."""

    return ProvenanceContext(
        bundle_path=analysis.source_path,
        validation=analysis.validation,
        metrics=analysis.metrics,
        evidence_pack=analysis.evidence_pack,
        diagnostic_report=analysis.diagnostic_report,
    )


def metric_provenance_for_ui(analysis: BundleAnalysis, metric_key: str) -> ProvenanceTrace:
    """Build a metric provenance trace for the selected analysis."""

    return get_metric_provenance(provenance_context_for_ui(analysis), metric_key)


def rule_provenance_for_ui(analysis: BundleAnalysis, rule_id: str) -> ProvenanceTrace:
    """Build a diagnostic-rule provenance trace for the selected analysis."""

    return get_rule_provenance(provenance_context_for_ui(analysis), rule_id)


def run_provenance_for_ui(analysis: BundleAnalysis) -> ProvenanceTrace:
    """Build a run-level provenance trace for the selected analysis."""

    return get_run_provenance(provenance_context_for_ui(analysis))


def source_preview_for_ui(
    analysis: BundleAnalysis,
    source_file: str,
    source_row: int,
    *,
    context_rows: int = 2,
) -> SourceRowPreview:
    """Return a read-only source-row preview for the selected analysis."""

    return get_source_provenance(
        provenance_context_for_ui(analysis),
        source_file,
        source_row,
        context_rows=context_rows,
    )


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


def _registry_payload_rows(
    registry_path: Path,
    table: Literal["experiments", "runs", "seeds"],
    id_column: Literal["experiment_id", "run_id", "seed_id"],
) -> list[dict[str, object]]:
    if not registry_path.exists():
        return []
    queries = {
        ("experiments", "experiment_id"): (
            "SELECT experiment_id, payload FROM experiments ORDER BY experiment_id"
        ),
        ("runs", "run_id"): "SELECT run_id, payload FROM runs ORDER BY run_id",
        ("seeds", "seed_id"): "SELECT seed_id, payload FROM seeds ORDER BY seed_id",
    }
    with sqlite3.connect(registry_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(queries[(table, id_column)]).fetchall()
    payloads: list[dict[str, object]] = []
    for row in rows:
        payload = yaml.safe_load(cast(str, row["payload"]))
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _registry_bundle_rows(registry_path: Path) -> list[dict[str, object]]:
    if not registry_path.exists():
        return []
    with sqlite3.connect(registry_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT bundle_id, run_id, source_reference, fingerprint, imported_at
            FROM bundle_imports
            ORDER BY imported_at DESC, bundle_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _registry_count_by_run(
    registry_path: Path,
    table: Literal["metric_collections", "evidence_packs"],
) -> dict[str, int]:
    if not registry_path.exists():
        return {}
    queries = {
        "metric_collections": (
            "SELECT run_id, COUNT(*) AS count "
            "FROM metric_collections GROUP BY run_id ORDER BY run_id"
        ),
        "evidence_packs": (
            "SELECT run_id, COUNT(*) AS count FROM evidence_packs GROUP BY run_id ORDER BY run_id"
        ),
    }
    with sqlite3.connect(registry_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(queries[table]).fetchall()
    return {cast(str, row["run_id"]): cast(int, row["count"]) for row in rows}


def _workspace_comparisons(workspace_path: Path) -> list[dict[str, object]]:
    path = workspace_path / "exports" / "comparisons.yaml"
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    comparisons = raw.get("comparisons", []) if isinstance(raw, dict) else []
    return comparisons if isinstance(comparisons, list) else []


def _infer_report_type(name: str) -> str:
    lowered = name.lower()
    if "diagnostic" in lowered:
        return "diagnostics"
    if " vs " in lowered or "_vs_" in lowered:
        return "comparison"
    if "full" in lowered:
        return "full"
    return "run"


def _scenario_hint(name: str) -> str | None:
    stem = Path(name).stem
    for prefix in ("baseline", "stressed", "under_offloading", "infrastructure_bottleneck"):
        if stem.startswith(prefix):
            return prefix
    return None


def _append_hit(
    hits: list[SearchHit],
    needle: str,
    category: str,
    title: str,
    payload: dict[str, object],
) -> None:
    haystack = " ".join([title, *(str(value) for value in payload.values())]).lower()
    if needle not in haystack:
        return
    detail = "; ".join(f"{key}={value}" for key, value in sorted(payload.items()))
    hits.append(
        SearchHit(
            category=category,
            title=title,
            detail=detail,
            reference=f"{category}:{title}",
        )
    )


def _safe_display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name if path.is_file() else path.as_posix()


def _git_commit_hash() -> str | None:
    git_dir = Path(".git")
    if not git_dir.exists():
        return None
    head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = git_dir / head.removeprefix("ref: ").strip()
        return ref.read_text(encoding="utf-8").strip()[:12] if ref.exists() else None
    return head[:12]
