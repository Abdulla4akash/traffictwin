"""UI-facing service layer over the tested TrafficTwin library."""

from __future__ import annotations

import math
import sqlite3
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import ValidationError

from traffictwin.annotations import (
    AnalystAnnotation,
    AnalystAnnotationHistory,
    AnalystAnnotationRequest,
    AnalystAnnotationTargetKind,
    AnalystArtifactReference,
    AnalystDecisionLabel,
)
from traffictwin.config.capabilities import CapabilityManifest, default_export_import_manifest
from traffictwin.config.seed_io import SeedIOError, dump_seed, load_seed
from traffictwin.demo.workspace import WorkspaceStatus, workspace_status
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.diagnostics.temporal import (
    TemporalDiagnosticAnalysis,
    evaluate_temporal_series,
)
from traffictwin.diagnostics.threshold_sweep import (
    ThresholdSensitivityReport,
    ThresholdSweepRequest,
    config_for_evaluated_point,
    evaluate_threshold_sweep,
)
from traffictwin.domain.enums import (
    Decision,
    FleetTierMix,
    RsuCapacityMode,
    TaskClass,
    WorkloadOrdering,
)
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.measurement import (
    MeasurementImpairmentContract,
    MeasurementTableKind,
    SyntheticMeasurementImpairmentConfig,
    measurement_impairment_contract,
)
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import TemporalEvidenceConfig
from traffictwin.experiments.equivalence_testing import (
    EquivalenceStudy,
    EquivalenceStudyConfig,
    evaluate_equivalence_study,
)
from traffictwin.experiments.evidence import (
    ExperimentEvidenceOptions,
    ObjectiveDirection,
    TrainingValidationObservation,
    build_experiment_evidence_pack,
    training_validation_observation_from_collections,
)
from traffictwin.experiments.n_way_ranking import (
    NWayRankingConfig,
    NWayRankingStudy,
    evaluate_n_way_ranking,
)
from traffictwin.experiments.parameter_sweep import (
    ParameterSweepMode,
    ParameterSweepRequest,
    ParameterSweepResult,
    SweepAxis,
    SweepParameter,
    execute_parameter_sweep,
    expand_parameter_sweep,
    parameter_sweep_contract,
    parameter_sweep_response_to_csv,
)
from traffictwin.experiments.planning import ExperimentPlanSummary, summarise_experiment_plan
from traffictwin.experiments.portfolio import (
    PortfolioEvaluationReport,
    PortfolioStudyReport,
    default_synthetic_portfolio_rules,
    evaluate_portfolio,
    evaluate_portfolio_study,
)
from traffictwin.experiments.power_analysis import (
    PowerAnalysis,
    PowerAnalysisConfig,
    evaluate_power_analysis,
)
from traffictwin.experiments.protocol import (
    ExperimentProtocol,
    ProtocolBundleMatch,
    build_experiment_protocol,
    match_bundle_manifest,
    protocol_to_csv,
    protocol_to_yaml,
)
from traffictwin.experiments.regression_gate import (
    RegressionGateReport,
    RegressionGoldenContract,
    RegressionSubjectKind,
    evaluate_regression_gate,
    parse_regression_golden_contract_json,
    parse_statistical_study_json,
)
from traffictwin.experiments.scenario_mutation import (
    MutationOperator,
    MutationSpec,
    MutationTableKind,
    RowDropoutMutation,
    RsuRemovalMutation,
    ScenarioMutationRequest,
    ScenarioMutationResult,
    TimestampJitterMutation,
    execute_scenario_mutation,
    plan_scenario_mutation,
    scenario_mutation_contract,
)
from traffictwin.experiments.statistical_study import (
    PairedStudyConfig,
    StatisticalStudy,
    evaluate_paired_statistical_study,
)
from traffictwin.experiments.tracking import (
    ProtocolSlotStatus,
    ProtocolTracker,
    ProtocolTrackingError,
)
from traffictwin.experiments.winner_map import WinnerMapReport, build_winner_map
from traffictwin.ingestion.batch import (
    BatchBundleSummary,
    import_bundle_batch,
    validate_bundle_batch,
)
from traffictwin.ingestion.bundle import (
    BundleValidationResult,
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
from traffictwin.integration.tos import (
    TosCampaignComparisonReport,
    TosEvaluationMatrix,
    TosEvaluationRun,
    TosGeneralisationMatrix,
    TosImportSummary,
    TosIntegrationReadinessReport,
    TosReplayFrame,
    TosReplayPoint,
    TosReproducibilityAudit,
    TosRsuReplayPoint,
    TosRsuRunSummary,
    TosSourceContract,
    TosTaskOutcomeSummary,
    TosTaskSample,
    TosTraceSummary,
    TosTrainingRun,
    TosTrainingRunSummary,
    TosValidationReport,
    audit_tos_package,
    build_evaluation_matrix,
    build_generalisation_matrix,
    build_static_results_atlas,
    build_tos_evidence_pack,
    build_tos_integration_readiness,
    build_tos_metric_trace,
    build_tos_research_report,
    build_tos_supervisor_pack_zip,
    compare_campaigns,
    import_evaluation_summaries,
    list_instrumented_runs,
    list_training_runs,
    load_replay_frame,
    load_replay_series,
    load_rsu_replay_series,
    load_task_sample,
    load_training_run,
    metric_collection_from_evaluation,
    read_evaluation_runs,
    summarise_rsu_run,
    summarise_task_outcomes,
    summarise_trace,
    tos_analysis_catalogue,
    tos_source_contract,
    validate_tos_package,
)
from traffictwin.integration.tos.analysis_models import TosAnalysisMeasureDefinition
from traffictwin.integration.tos.readers import (
    TosPackageError,
    instrumented_key_for_run,
    list_pertask_runs,
)
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import MetricPluginApiContract, metric_plugin_api_contract
from traffictwin.metrics.results import JsonScalar, MetricCollection, MetricStatus
from traffictwin.metrics.windowed import (
    PartialWindowPolicy,
    WindowedMetricConfig,
    WindowedMetricSeries,
    WindowLimitExceededError,
    compute_windowed_metrics_for_bundle,
)
from traffictwin.provenance.completeness import ProvenanceCompletenessReport
from traffictwin.provenance.contributions import MetricContributionReport
from traffictwin.provenance.differences import DifferenceContributionReport
from traffictwin.provenance.graph_export import GraphRedactionMode, ProvenanceGraphView
from traffictwin.provenance.models import ProvenanceTrace, SourceRowPreview
from traffictwin.provenance.query import (
    ProvenanceContext,
    ProvenanceQueryError,
    get_comparison_provenance_completeness,
    get_difference_contributions,
    get_metric_contributions,
    get_metric_provenance,
    get_provenance_graph_view,
    get_report_provenance_completeness,
    get_rule_provenance,
    get_run_provenance,
    get_source_provenance,
)
from traffictwin.registry_search import (
    RegistrySearchError,
    RegistrySearchResult,
    SearchCategory,
    search_registry,
)
from traffictwin.release.metadata import current_release_metadata
from traffictwin.reporting.annotation_rendering import attach_registry_annotations
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.diffing import (
    ReportDiffError,
    StructuredReportDiff,
    compare_structured_reports,
    parse_research_report_json,
    report_diff_to_markdown,
)
from traffictwin.reporting.executive import (
    ExecutiveSummary,
    ExecutiveSummaryError,
    executive_summary_to_html,
    executive_summary_to_markdown,
    project_executive_summary,
)
from traffictwin.reporting.executive_pdf import (
    ExecutiveSummaryLayoutError,
    executive_summary_to_pdf_bytes,
)
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.latex import (
    ResearchExportReceipt,
    project_comparison_report,
    project_diagnostic_report,
    project_metric_collection,
    project_statistical_study,
    write_projection_exports,
)
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.models import ResearchReportType
from traffictwin.reporting.pdf import report_to_pdf_bytes
from traffictwin.rules.config import R6Config, R7Config, R8Config, RuleSetConfig
from traffictwin.rules.declarative import DeclarativeRuleContract, declarative_rule_contract
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleResult
from traffictwin.storage.registry import (
    BundleImportResult,
    DuplicateIdentifierError,
    Registry,
    RegistryConflictError,
    RegistryNotFoundError,
    RegistrySummary,
)
from traffictwin.synthetic.bundles import (
    synthetic_bundle_id,
    synthetic_run_id,
    write_synthetic_bundle,
)
from traffictwin.synthetic.config import (
    SYNTHETIC_GENERATOR_VERSION,
    SyntheticPolicyProfile,
    SyntheticScenarioConfig,
    synthetic_scenario_config_to_yaml,
)
from traffictwin.synthetic.experiments import (
    PORTFOLIO_DEVELOPMENT_PRESETS,
    PORTFOLIO_HELD_OUT_PRESETS,
    PORTFOLIO_STUDY_EXPERIMENT_ID,
)
from traffictwin.synthetic.scenarios import (
    incident_variant_config,
    list_preset_names,
    preset_config,
)


@dataclass(frozen=True)
class ProjectStatus:
    """Project status shown on the Home page."""

    registry_path: Path
    registry_exists: bool
    registry_summary: RegistrySummary | None
    latest_runs: list[Run]
    capability_manifest: CapabilityManifest
    current_phase: str = "Standalone product polish prototype"
    canonical_design_version: str = "TrafficTwin v0.5"


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
class ReplayBundleChoice:
    """Validated bundle metadata used by the historical replay source selector."""

    path: Path
    vehicle_count: int
    incident_count: int
    incident_types: tuple[str, ...]


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
class StructuredReportDiffView:
    """REP-03 result plus its exact JSON and presentation-only Markdown exports."""

    report: StructuredReportDiff
    json_payload: str
    markdown_payload: str


@dataclass(frozen=True)
class ExecutiveSummaryView:
    """REP-04 projection plus complete downloadable output representations."""

    summary: ExecutiveSummary
    json_payload: str
    markdown_payload: str
    html_payload: str
    pdf_payload: bytes


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
class ExperimentPlannerCatalog:
    """Typed registry objects available to the experiment planner."""

    registry_path: Path
    seeds: list[ScenarioSeed]
    experiments: list[Experiment]
    algorithms: list[str]


@dataclass(frozen=True)
class ResearchAnalysisView:
    """Experiment-level evidence, diagnostics, winner map, and portfolio results."""

    experiment_id: str
    source_collection_count: int
    evidence_pack: EvidencePack
    diagnostic_report: DiagnosticReport
    winner_map: WinnerMapReport
    portfolio: PortfolioEvaluationReport
    portfolio_study: PortfolioStudyReport | None


@dataclass(frozen=True)
class ResearchAnalysisCatalog:
    """Scalar metrics and stored run IDs available for explicit research analysis."""

    experiment_id: str
    metric_keys: list[str]
    run_ids: list[str]


@dataclass(frozen=True)
class StatisticalStudyCatalog:
    """Registered plan and stored scalar inputs available to STA-01 through STA-04."""

    experiment_id: str
    baseline_seed_id: str
    variation_seed_ids: list[str]
    algorithms: list[str]
    checkpoints: list[str | None]
    metric_keys: list[str]
    expected_random_seeds: list[int]
    collection_count: int


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
class ParameterSweepUiCatalog:
    """Closed fields and modes rendered by the thin sweep page."""

    preset_names: list[str]
    modes: list[ParameterSweepMode]
    parameter_paths: list[SweepParameter]
    metric_keys: list[str]
    max_axes: int
    max_points: int


@dataclass(frozen=True)
class ScenarioMutationUiCatalog:
    """Closed EXP-02 operators and limits rendered by the thin mutation page."""

    operators: list[MutationOperator]
    table_kinds: list[MutationTableKind]
    max_changed_rows: int
    max_absolute_jitter_s: float


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


@dataclass(frozen=True)
class TosPackageView:
    """Read-only TOS package view model."""

    source_path: Path
    report: TosValidationReport
    evaluation_runs: list[TosEvaluationRun]
    instrumented_runs: list[str]
    pertask_runs: list[str]
    source_contract: TosSourceContract


@dataclass(frozen=True)
class TosResultsView:
    """Evaluation matrix and package-evidenced generalisation labels."""

    matrix: TosEvaluationMatrix
    generalisation: TosGeneralisationMatrix
    measures: tuple[TosAnalysisMeasureDefinition, ...]
    campaigns: list[str]
    fleets: list[str]


@dataclass(frozen=True)
class TosRunAnalysis:
    """Source-summary analysis for one TOS evaluation row."""

    run: TosEvaluationRun
    metric_collection: MetricCollection
    evidence_pack: EvidencePack
    diagnostic_report: DiagnosticReport
    completion_trace: ProvenanceTrace


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


def inspect_tos_for_ui(
    path: str | Path,
    *,
    deep: bool = False,
) -> TosPackageView | ServiceError:
    """Inspect a TOS package through the integration boundary."""

    try:
        report = validate_tos_package(path, deep=deep)
        rows = read_evaluation_runs(path) if report.may_import_summaries else []
        return TosPackageView(
            source_path=Path(path).resolve(),
            report=report,
            evaluation_runs=rows,
            instrumented_runs=list_instrumented_runs(path),
            pertask_runs=list_pertask_runs(path),
            source_contract=tos_source_contract(),
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS Data package could not be inspected.", str(exc))


def tos_results_for_ui(
    package_view: TosPackageView,
    *,
    measure_key: str = "tos.task.deadline_success.rate",
    evaluation_fleet: str = "uk2030",
) -> TosResultsView | ServiceError:
    """Prepare source matrix and domain labels without UI-side calculations."""

    try:
        return TosResultsView(
            matrix=build_evaluation_matrix(
                package_view.evaluation_runs,
                package_view.source_path,
                measure_key=measure_key,
                evaluation_fleet=evaluation_fleet,
            ),
            generalisation=build_generalisation_matrix(
                package_view.evaluation_runs, package_view.source_path
            ),
            measures=tos_analysis_catalogue(),
            campaigns=sorted(
                {
                    run.campaign
                    for run in package_view.evaluation_runs
                    if run.eval_fleet == evaluation_fleet
                }
            ),
            fleets=sorted({run.eval_fleet for run in package_view.evaluation_runs}),
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS results matrix could not be prepared.", str(exc))


def compare_tos_campaigns_for_ui(
    package_view: TosPackageView,
    baseline_campaign: str,
    variation_campaign: str,
    *,
    measure_key: str,
    evaluation_fleet: str,
) -> TosCampaignComparisonReport | ServiceError:
    """Build a paired campaign report over common source fleet seeds."""

    try:
        return compare_campaigns(
            package_view.evaluation_runs,
            package_view.source_path,
            baseline_campaign,
            variation_campaign,
            evaluation_fleet=evaluation_fleet,
            measure_keys=[measure_key],
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS paired campaign comparison could not be prepared.", str(exc))


def tos_training_runs_for_ui(
    package_view: TosPackageView,
) -> list[TosTrainingRunSummary] | ServiceError:
    """Index source training histories."""

    try:
        return list_training_runs(package_view.source_path)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS training histories could not be indexed.", str(exc))


def tos_training_run_for_ui(
    package_view: TosPackageView,
    training_id: str,
) -> TosTrainingRun | ServiceError:
    """Load one bounded source training history."""

    try:
        return load_training_run(package_view.source_path, training_id)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS training history could not be loaded.", str(exc))


def tos_trace_summary_for_ui(
    package_view: TosPackageView,
    trace_name: str,
) -> TosTraceSummary | ServiceError:
    """Load a bounded processed-FCD profile."""

    try:
        return summarise_trace(package_view.source_path, trace_name)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("Processed FCD trace could not be summarised.", str(exc))


def tos_rsu_summary_for_ui(
    package_view: TosPackageView,
    run_key: str,
) -> TosRsuRunSummary | ServiceError:
    """Summarise source RSU state for an instrumented run."""

    try:
        return summarise_rsu_run(package_view.source_path, run_key)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS RSU source state could not be summarised.", str(exc))


def tos_task_summary_for_ui(
    package_view: TosPackageView,
    run_key: str,
) -> TosTaskOutcomeSummary | ServiceError:
    """Aggregate one complete per-task showcase array."""

    try:
        return summarise_task_outcomes(package_view.source_path, run_key)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS per-task outcomes could not be summarised.", str(exc))


def tos_audit_for_ui(
    package_view: TosPackageView,
) -> TosReproducibilityAudit | ServiceError:
    """Build the read-only reproducibility audit."""

    try:
        return audit_tos_package(package_view.source_path)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS reproducibility audit could not be prepared.", str(exc))


def tos_readiness_for_ui(
    package_view: TosPackageView,
) -> TosIntegrationReadinessReport | ServiceError:
    """Build machine-readable integration and permission gates."""

    try:
        return build_tos_integration_readiness(package_view.source_path)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS integration readiness could not be prepared.", str(exc))


def tos_supervisor_pack_for_ui(
    package_view: TosPackageView,
    *,
    variation_campaign: str,
) -> bytes | ServiceError:
    """Build a private checksummed supervisor pack for deliberate download."""

    try:
        return build_tos_supervisor_pack_zip(
            package_view.source_path,
            variation_campaign=variation_campaign,
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS supervisor pack could not be prepared.", str(exc))


def tos_report_exports_for_ui(
    package_view: TosPackageView,
    *,
    variation_campaign: str,
) -> tuple[str, str, str] | ServiceError:
    """Return Markdown report, HTML report, and aggregate-only static atlas."""

    try:
        report = build_tos_research_report(
            package_view.source_path, variation_campaign=variation_campaign
        )
        return (
            report_to_markdown(report),
            report_to_html(report),
            build_static_results_atlas(package_view.source_path),
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS report exports could not be prepared.", str(exc))


def import_tos_for_ui(
    path: str | Path,
    registry_path: str | Path,
    report: TosValidationReport,
) -> TosImportSummary | ServiceError:
    """Import accepted TOS summaries through the idempotent registry service."""

    try:
        return import_evaluation_summaries(path, registry_path, validation_report=report)
    except (OSError, ValueError, TosPackageError, RegistryConflictError) as exc:
        return ServiceError("TOS evaluation summaries could not be imported.", str(exc))


def analyse_tos_run_for_ui(
    package_view: TosPackageView,
    run_identifier: str,
) -> TosRunAnalysis | ServiceError:
    """Build metrics, partial evidence, diagnostics, and provenance for one source row."""

    try:
        run = _find_tos_run(package_view.evaluation_runs, run_identifier)
        fingerprint = package_view.report.package_fingerprint
        if fingerprint is None:
            return ServiceError("TOS package fingerprint is unavailable.")
        collection = metric_collection_from_evaluation(run, fingerprint)
        pack = build_tos_evidence_pack(run, package_view.report, collection)
        diagnosis = evaluate_rules(pack)
        trace = build_tos_metric_trace(
            run,
            collection,
            package_view.report,
            "tos.task.deadline_success.rate",
        )
        return TosRunAnalysis(
            run=run,
            metric_collection=collection,
            evidence_pack=pack,
            diagnostic_report=diagnosis,
            completion_trace=trace,
        )
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS run analysis could not be prepared.", str(exc))


def compare_tos_runs_for_ui(
    package_view: TosPackageView,
    baseline_identifier: str,
    variation_identifier: str,
) -> ComparisonReport | ServiceError:
    """Compare two compatible source-summary runs through Phase 3 comparison logic."""

    try:
        baseline = _find_tos_run(package_view.evaluation_runs, baseline_identifier)
        variation = _find_tos_run(package_view.evaluation_runs, variation_identifier)
        fingerprint = package_view.report.package_fingerprint
        if fingerprint is None:
            return ServiceError("TOS package fingerprint is unavailable.")
        baseline_metrics = metric_collection_from_evaluation(baseline, fingerprint)
        variation_metrics = metric_collection_from_evaluation(variation, fingerprint)
        return compare_metric_collections(baseline_metrics, variation_metrics)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS source-summary comparison could not be prepared.", str(exc))


def load_tos_replay_for_ui(
    path: str | Path,
    run_key: str,
    index: int,
    *,
    max_vehicles: int = 100,
) -> TosReplayFrame | ServiceError:
    """Load one bounded TOS historical replay frame."""

    try:
        return load_replay_frame(path, run_key, index, max_vehicles=max_vehicles)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS replay frame could not be loaded.", str(exc))


def load_tos_replay_series_for_ui(
    path: str | Path,
    run_key: str,
) -> list[TosReplayPoint] | ServiceError:
    """Load the small logical replay series used by deterministic UI controls."""

    try:
        return list(load_replay_series(path, run_key))
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS logical replay series could not be loaded.", str(exc))


def load_tos_task_sample_for_ui(
    path: str | Path,
    run_key: str,
    *,
    limit: int = 50,
) -> TosTaskSample | ServiceError:
    """Load a bounded, read-only TOS per-task sample."""

    try:
        return load_task_sample(path, run_key, limit=limit)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS per-task sample could not be loaded.", str(exc))


def load_tos_rsu_series_for_ui(
    path: str | Path,
    run_key: str,
    *,
    stride: int = 1,
) -> list[TosRsuReplayPoint] | ServiceError:
    """Load interpreted, source-specific RSU history for visual inspection."""

    try:
        return load_rsu_replay_series(path, run_key, stride=stride)
    except (OSError, ValueError, TosPackageError) as exc:
        return ServiceError("TOS RSU replay history could not be loaded.", str(exc))


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
                "incident_schedule": (
                    [
                        {
                            "timestamp_s": _as_float(data.get("incident_timestamp_s", 0.0)),
                            "incident_type": str(data.get("incident_type") or "synthetic_incident"),
                            "location": str(data.get("incident_location") or "") or None,
                            "severity": str(data.get("incident_severity") or "") or None,
                            "duration_s": _as_float(data.get("incident_duration_s", 60.0)),
                            "lanes_closed": (
                                _as_int(data["incident_lanes_closed"])
                                if data.get("incident_lanes_closed") is not None
                                else None
                            ),
                            "demand_multiplier": _as_float(
                                data.get("incident_demand_multiplier", 1.0)
                            ),
                            "vehicles_involved": _split_csv(
                                str(data.get("incident_vehicles_involved", ""))
                            ),
                        }
                    ]
                    if bool(data.get("incident_enabled", False))
                    else []
                ),
                "synthetic_faults": _split_csv(str(data.get("synthetic_faults", ""))),
                "include_infrastructure": bool(data.get("include_infrastructure", True)),
                "include_vehicles": bool(data.get("include_vehicles", True)),
                "include_traffic": bool(data.get("include_traffic", True)),
                "include_trips": bool(data.get("include_trips", True)),
                "include_incidents": bool(data.get("include_incidents", True)),
                "measurement_imperfections": _measurement_config_from_form(data),
            }
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return ServiceError("Synthetic scenario configuration is invalid.", str(exc))
    return config


def _measurement_config_from_form(
    data: dict[str, object],
) -> SyntheticMeasurementImpairmentConfig | None:
    if not bool(data.get("measurement_imperfections_enabled", False)):
        return None
    dropout_values = {
        MeasurementTableKind.INFRA_STATE: _as_float(
            data.get("infrastructure_dropout_fraction", 0.0)
        ),
        MeasurementTableKind.VEHICLE_STATE: _as_float(data.get("vehicle_dropout_fraction", 0.0)),
        MeasurementTableKind.TRAFFIC_OBS: _as_float(data.get("traffic_dropout_fraction", 0.0)),
    }
    return SyntheticMeasurementImpairmentConfig(
        random_seed=_as_int(data.get("measurement_random_seed", 17)),
        vehicle_position_max_error_m=_as_float(data.get("vehicle_position_max_error_m", 0.0)),
        vehicle_speed_max_error_mps=_as_float(data.get("vehicle_speed_max_error_mps", 0.0)),
        traffic_speed_max_error_mps=_as_float(data.get("traffic_speed_max_error_mps", 0.0)),
        traffic_count_max_error=_as_int(data.get("traffic_count_max_error", 0)),
        infrastructure_utilisation_max_error=_as_float(
            data.get("infrastructure_utilisation_max_error", 0.0)
        ),
        infrastructure_queue_max_error=_as_int(data.get("infrastructure_queue_max_error", 0)),
        row_dropout_fraction_by_table={
            table: fraction for table, fraction in dropout_values.items() if fraction > 0.0
        },
    )


def scenario_config_to_yaml(config: SyntheticScenarioConfig) -> str:
    """Return deterministic YAML for a synthetic generator configuration."""

    return synthetic_scenario_config_to_yaml(config)


def incident_variant_for_ui(
    config: SyntheticScenarioConfig,
) -> SyntheticScenarioConfig | ServiceError:
    """Create an explicit synthetic what-if variation from the authored incident."""

    try:
        return incident_variant_config(config)
    except ValueError as exc:
        return ServiceError("Incident what-if variant could not be created.", str(exc))


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
        {"field": "incident_count", "value": len(config.incident_schedule)},
        {"field": "synthetic_faults", "value": ", ".join(config.synthetic_faults) or "none"},
        {
            "field": "measurement_imperfections",
            "value": (
                config.measurement_imperfections.fingerprint()
                if config.measurement_imperfections is not None
                else "disabled"
            ),
        },
    ]
    return ScenarioPreview(
        config=config,
        expected_bundle_id=synthetic_bundle_id(config),
        expected_run_id=synthetic_run_id(config),
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


def measurement_impairment_contract_for_ui() -> MeasurementImpairmentContract:
    """Return the typed EXP-03 contract for thin UI rendering."""

    return measurement_impairment_contract()


def parameter_sweep_catalog_for_ui() -> ParameterSweepUiCatalog:
    """Return the public EXP-01 inputs without defining UI-only capabilities."""

    contract = parameter_sweep_contract()
    return ParameterSweepUiCatalog(
        preset_names=list_preset_names(),
        modes=contract.supported_modes,
        parameter_paths=contract.synthetic_parameter_paths,
        metric_keys=sorted(metric_catalogue()),
        max_axes=contract.max_axes,
        max_points=contract.max_points,
    )


def prepare_parameter_sweep_for_ui(
    *,
    sweep_id: str,
    title: str,
    description: str,
    mode: str,
    preset_name: str,
    axes: list[tuple[str, str]],
    metric_keys: list[str],
) -> ParameterSweepRequest | ServiceError:
    """Parse bounded form values and validate every grid point in the library layer."""

    try:
        parsed_axes = [
            SweepAxis(
                parameter_path=SweepParameter(path),
                values=_parse_sweep_values(values),
            )
            for path, values in axes
            if path and values.strip()
        ]
        request = ParameterSweepRequest(
            sweep_id=sweep_id.strip(),
            title=title.strip(),
            description=description.strip(),
            mode=ParameterSweepMode(mode),
            base_synthetic_config=preset_config(preset_name),
            axes=parsed_axes,
            metric_keys=(
                metric_keys if mode == ParameterSweepMode.LOCAL_SYNTHETIC_BUNDLES.value else []
            ),
        )
        expand_parameter_sweep(request)
    except (TypeError, ValueError) as exc:
        return ServiceError("The parameter sweep is invalid.", str(exc))
    return request


def execute_parameter_sweep_for_ui(
    request: ParameterSweepRequest,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ParameterSweepResult | ServiceError:
    """Materialise one already validated request through the EXP-01 service."""

    try:
        return execute_parameter_sweep(request, output_dir, overwrite=overwrite)
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        return ServiceError("The parameter sweep could not be materialised.", str(exc))


def parameter_sweep_result_json_for_ui(result: ParameterSweepResult) -> str:
    """Return the typed sweep result as JSON."""

    return result.model_dump_json(indent=2, by_alias=True) + "\n"


def parameter_sweep_response_csv_for_ui(result: ParameterSweepResult) -> str:
    """Return the library-produced response surface as CSV."""

    return parameter_sweep_response_to_csv(result)


def scenario_mutation_catalog_for_ui() -> ScenarioMutationUiCatalog:
    """Return the public EXP-02 inputs without defining UI-only mutation semantics."""

    contract = scenario_mutation_contract()
    return ScenarioMutationUiCatalog(
        operators=contract.supported_operators,
        table_kinds=contract.supported_tables,
        max_changed_rows=contract.max_changed_rows,
        max_absolute_jitter_s=contract.max_absolute_jitter_s,
    )


def prepare_scenario_mutation_for_ui(
    *,
    parent_bundle: str | Path,
    mutation_id: str,
    title: str,
    description: str,
    operator: str,
    table_kind: str,
    drop_fraction: float,
    max_absolute_jitter_s: float,
    rsu_id: str,
    random_seed: int,
) -> ScenarioMutationRequest | ServiceError:
    """Build and fully plan one closed EXP-02 request through the library layer."""

    try:
        selected_operator = MutationOperator(operator)
        mutation: MutationSpec
        if selected_operator is MutationOperator.ROW_DROPOUT:
            mutation = RowDropoutMutation(
                table_kind=MutationTableKind(table_kind),
                drop_fraction=drop_fraction,
                random_seed=random_seed,
            )
        elif selected_operator is MutationOperator.TIMESTAMP_JITTER:
            mutation = TimestampJitterMutation(
                table_kind=MutationTableKind(table_kind),
                max_absolute_jitter_s=max_absolute_jitter_s,
                random_seed=random_seed,
            )
        else:
            mutation = RsuRemovalMutation(rsu_id=rsu_id.strip())
        request = ScenarioMutationRequest(
            mutation_id=mutation_id.strip(),
            title=title.strip(),
            description=description.strip(),
            mutation=mutation,
        )
        plan_scenario_mutation(parent_bundle, request)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return ServiceError("The scenario mutation is invalid.", str(exc))
    return request


def execute_scenario_mutation_for_ui(
    parent_bundle: str | Path,
    request: ScenarioMutationRequest,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> ScenarioMutationResult | ServiceError:
    """Materialise one planned EXP-02 request through the typed library service."""

    try:
        return execute_scenario_mutation(
            parent_bundle,
            request,
            output_dir,
            overwrite=overwrite,
        )
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        return ServiceError("The scenario mutation could not be materialised.", str(exc))


def scenario_mutation_result_json_for_ui(result: ScenarioMutationResult) -> str:
    """Return the typed mutation manifest as JSON."""

    return result.model_dump_json(indent=2) + "\n"


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


def load_research_analysis_view(
    registry_path: str | Path,
    experiment_id: str,
    *,
    metric_key: str = "task.completion.rate",
    objective: ObjectiveDirection = ObjectiveDirection.MAXIMISE,
    training_validation: list[TrainingValidationObservation] | None = None,
) -> ResearchAnalysisView | ServiceError:
    """Build the experiment-level research analysis without UI calculations."""

    path = Path(registry_path)
    try:
        registry = Registry(path)
        collections = [
            collection
            for payload in registry.list_metric_collection_json()
            if (collection := MetricCollection.model_validate_json(payload)).results
            and collection.results[0].experiment_id == experiment_id
        ]
        if not collections:
            return ServiceError(
                "No stored metric collections match this experiment.",
                experiment_id,
            )
        registered_seeds = registry.list_seeds()
        aliases = {seed.seed_id: seed.parent_seed_id or seed.seed_id for seed in registered_seeds}
        seeds_by_family: dict[str, ScenarioSeed] = {}
        for seed in registered_seeds:
            family = aliases[seed.seed_id]
            if seed.seed_id == family:
                seeds_by_family[family] = seed
            else:
                seeds_by_family.setdefault(family, seed)
        evidence = build_experiment_evidence_pack(
            collections,
            ExperimentEvidenceOptions(
                experiment_id=experiment_id,
                primary_metric_key=metric_key,
                objective=objective,
            ),
            training_validation=training_validation,
        )
        diagnostics = evaluate_rules(evidence)
        winner_map = build_winner_map(
            collections,
            metric_key=metric_key,
            objective=objective,
            seed_aliases=aliases,
        )
        portfolio = evaluate_portfolio(
            winner_map,
            seeds_by_family,
            default_synthetic_portfolio_rules(),
        )
        portfolio_study = None
        if experiment_id == PORTFOLIO_STUDY_EXPERIMENT_ID:
            portfolio_study = evaluate_portfolio_study(
                winner_map,
                seeds_by_family,
                default_synthetic_portfolio_rules(),
                development_seed_ids=[f"seed-{name}" for name in PORTFOLIO_DEVELOPMENT_PRESETS],
                held_out_seed_ids=[f"seed-{name}" for name in PORTFOLIO_HELD_OUT_PRESETS],
            )
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Research analysis could not be prepared.", str(exc))
    return ResearchAnalysisView(
        experiment_id=experiment_id,
        source_collection_count=len(collections),
        evidence_pack=evidence,
        diagnostic_report=diagnostics,
        winner_map=winner_map,
        portfolio=portfolio,
        portfolio_study=portfolio_study,
    )


def load_research_analysis_catalog(
    registry_path: str | Path,
    experiment_id: str,
) -> ResearchAnalysisCatalog | ServiceError:
    """List finite scalar metrics and runs available for one experiment."""

    try:
        collections = _metric_collections_for_experiment(registry_path, experiment_id)
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Research analysis inputs could not be loaded.", str(exc))
    if not collections:
        return ServiceError("No stored metric collections match this experiment.", experiment_id)
    metric_keys = sorted(
        {
            metric.metric_key
            for collection in collections
            for metric in collection.results
            if metric.status is MetricStatus.AVAILABLE
            and isinstance(metric.value, int | float)
            and not isinstance(metric.value, bool)
        }
    )
    if not metric_keys:
        return ServiceError("No available finite scalar metrics match this experiment.")
    return ResearchAnalysisCatalog(
        experiment_id=experiment_id,
        metric_keys=metric_keys,
        run_ids=sorted(collection.run_id for collection in collections),
    )


def statistical_study_experiments_for_ui(
    registry_path: str | Path,
) -> list[str] | ServiceError:
    """List registered experiments that also have stored metric collections."""

    try:
        registry = Registry(registry_path)
        with_metrics = {
            collection.results[0].experiment_id
            for payload in registry.list_metric_collection_json()
            if (collection := MetricCollection.model_validate_json(payload)).results
            and collection.results[0].experiment_id is not None
        }
        return [
            experiment.experiment_id
            for experiment in registry.list_experiments()
            if experiment.experiment_id in with_metrics
        ]
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Statistical-study experiments could not be loaded.", str(exc))


def load_statistical_study_catalog(
    registry_path: str | Path,
    experiment_id: str,
) -> StatisticalStudyCatalog | ServiceError:
    """Load one registered common-seed plan and its stored scalar metric catalogue."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(experiment_id)
        collections = _metric_collections_for_experiment(registry_path, experiment_id)
        if not collections:
            return ServiceError("No stored metric collections match this experiment.")
        metric_keys = sorted(
            {
                metric.metric_key
                for collection in collections
                for metric in collection.results
                if metric.status is MetricStatus.AVAILABLE
                and isinstance(metric.value, int | float)
                and not isinstance(metric.value, bool)
                and math.isfinite(float(metric.value))
            }
        )
        if not metric_keys:
            return ServiceError("No finite scalar metrics are available for this experiment.")
        checkpoints = sorted(
            {collection.results[0].checkpoint for collection in collections},
            key=lambda value: (value is not None, value or ""),
        )
        return StatisticalStudyCatalog(
            experiment_id=experiment_id,
            baseline_seed_id=experiment.baseline_seed_id,
            variation_seed_ids=list(experiment.variation_seed_ids),
            algorithms=list(experiment.algorithms),
            checkpoints=checkpoints,
            metric_keys=metric_keys,
            expected_random_seeds=sorted(experiment.common_random_seed_set),
            collection_count=len(collections),
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Statistical-study inputs could not be loaded.", str(exc))


def evaluate_statistical_study_for_ui(
    registry_path: str | Path,
    config: PairedStudyConfig,
) -> StatisticalStudy | ServiceError:
    """Delegate one complete predeclared STA-01 plan to the library service."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(config.experiment_id)
        if config.baseline_seed_id != experiment.baseline_seed_id:
            raise ValueError("baseline seed does not match the registered experiment plan")
        if config.variation_seed_id not in experiment.variation_seed_ids:
            raise ValueError("variation seed is not declared by the registered experiment plan")
        if config.algorithm not in experiment.algorithms:
            raise ValueError("algorithm is not declared by the registered experiment plan")
        if config.expected_random_seeds != sorted(experiment.common_random_seed_set):
            raise ValueError("common random-seed set does not match the registered experiment plan")
        return evaluate_paired_statistical_study(
            _metric_collections_for_experiment(registry_path, config.experiment_id),
            config,
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Statistical study could not be evaluated.", str(exc))


def evaluate_n_way_ranking_for_ui(
    registry_path: str | Path,
    config: NWayRankingConfig,
) -> NWayRankingStudy | ServiceError:
    """Delegate one complete registered STA-02 plan to the library service."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(config.experiment_id)
        planned_seeds = {experiment.baseline_seed_id, *experiment.variation_seed_ids}
        if not set(config.seed_ids).issubset(planned_seeds):
            raise ValueError("scenario families are not declared by the registered experiment")
        if not set(config.algorithms).issubset(experiment.algorithms):
            raise ValueError("policies are not declared by the registered experiment")
        if config.expected_random_seeds != sorted(experiment.common_random_seed_set):
            raise ValueError("common random-seed set does not match the registered experiment plan")
        aliases = {
            seed.seed_id: seed.parent_seed_id or seed.seed_id for seed in registry.list_seeds()
        }
        return evaluate_n_way_ranking(
            _metric_collections_for_experiment(registry_path, config.experiment_id),
            config,
            seed_aliases=aliases,
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("N-way ranking could not be evaluated.", str(exc))


def evaluate_equivalence_study_for_ui(
    registry_path: str | Path,
    config: EquivalenceStudyConfig,
) -> EquivalenceStudy | ServiceError:
    """Delegate one complete registered STA-03 plan to the library service."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(config.experiment_id)
        if config.baseline_seed_id != experiment.baseline_seed_id:
            raise ValueError("baseline seed does not match the registered experiment plan")
        if config.variation_seed_id not in experiment.variation_seed_ids:
            raise ValueError("variation seed is not declared by the registered experiment plan")
        if config.algorithm not in experiment.algorithms:
            raise ValueError("algorithm is not declared by the registered experiment plan")
        if config.expected_random_seeds != sorted(experiment.common_random_seed_set):
            raise ValueError("common random-seed set does not match the registered experiment plan")
        return evaluate_equivalence_study(
            _metric_collections_for_experiment(registry_path, config.experiment_id),
            config,
        )
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Equivalence study could not be evaluated.", str(exc))


def evaluate_power_analysis_for_ui(
    config: PowerAnalysisConfig,
) -> PowerAnalysis | ServiceError:
    """Delegate one complete STA-05 prospective plan to the library service."""

    try:
        return evaluate_power_analysis(config)
    except (ValueError, ValidationError) as exc:
        return ServiceError("Power analysis could not be evaluated.", str(exc))


def regression_metric_runs_for_ui(
    registry_path: str | Path,
) -> list[str] | ServiceError:
    """List stored non-empty MetricCollections available as STA-04 subjects."""

    try:
        return sorted(
            collection.run_id
            for payload in Registry(registry_path).list_metric_collection_json()
            if (collection := MetricCollection.model_validate_json(payload)).results
        )
    except (OSError, sqlite3.Error, ValueError, ValidationError) as exc:
        return ServiceError("Regression-gate metric subjects could not be loaded.", str(exc))


def parse_regression_golden_for_ui(
    payload: bytes,
) -> RegressionGoldenContract | ServiceError:
    """Parse one bounded strict golden contract uploaded by the user."""

    try:
        return parse_regression_golden_contract_json(payload)
    except (ValueError, ValidationError) as exc:
        return ServiceError("Regression golden contract is invalid.", str(exc))


def evaluate_metric_regression_gate_for_ui(
    registry_path: str | Path,
    run_id: str,
    contract: RegressionGoldenContract,
) -> RegressionGateReport | ServiceError:
    """Evaluate one stored MetricCollection against an uploaded golden contract."""

    if contract.subject_kind is not RegressionSubjectKind.METRIC_COLLECTION:
        return ServiceError("The golden contract does not target a metric collection.")
    try:
        collection = MetricCollection.model_validate_json(
            Registry(registry_path).get_metric_collection_json(run_id)
        )
        return evaluate_regression_gate(collection, contract)
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        ValidationError,
        RegistryNotFoundError,
    ) as exc:
        return ServiceError("Metric regression gate could not be evaluated.", str(exc))


def evaluate_statistical_regression_gate_for_ui(
    study: StatisticalStudy,
    contract: RegressionGoldenContract,
) -> RegressionGateReport | ServiceError:
    """Evaluate an existing typed STA-01 session result against a golden contract."""

    if contract.subject_kind is not RegressionSubjectKind.PAIRED_STATISTICAL_STUDY:
        return ServiceError("The golden contract does not target a paired statistical study.")
    try:
        return evaluate_regression_gate(study, contract)
    except (ValueError, ValidationError) as exc:
        return ServiceError("Statistical-study regression gate could not be evaluated.", str(exc))


def build_training_validation_pairs_for_ui(
    registry_path: str | Path,
    training_run_ids: list[str],
    validation_run_ids: list[str],
    metric_key: str,
) -> list[TrainingValidationObservation] | ServiceError:
    """Build ordered, explicit, compatibility-checked pairs for R5."""

    if len(training_run_ids) != len(validation_run_ids):
        return ServiceError(
            "Training and validation selections must contain the same number of runs."
        )
    if len(set(training_run_ids)) != len(training_run_ids) or len(set(validation_run_ids)) != len(
        validation_run_ids
    ):
        return ServiceError("Training and validation run selections must not contain duplicates.")
    registry = Registry(registry_path)
    pairs: list[TrainingValidationObservation] = []
    try:
        for training_id, validation_id in zip(training_run_ids, validation_run_ids, strict=True):
            training = MetricCollection.model_validate_json(
                registry.get_metric_collection_json(training_id)
            )
            validation = MetricCollection.model_validate_json(
                registry.get_metric_collection_json(validation_id)
            )
            pairs.append(
                training_validation_observation_from_collections(
                    training,
                    validation,
                    metric_key,
                )
            )
    except (OSError, sqlite3.Error, ValueError, ValidationError, RegistryNotFoundError) as exc:
        return ServiceError("Training-validation pairs are incompatible.", str(exc))
    return pairs


def _metric_collections_for_experiment(
    registry_path: str | Path,
    experiment_id: str,
) -> list[MetricCollection]:
    registry = Registry(registry_path)
    return [
        collection
        for payload in registry.list_metric_collection_json()
        if (collection := MetricCollection.model_validate_json(payload)).results
        and collection.results[0].experiment_id == experiment_id
    ]


def protocol_tracking_rows_for_ui(
    registry_path: str | Path,
) -> list[dict[str, object]] | ServiceError:
    """Return manual protocol slot state for the Experiment Manager."""

    tracker = ProtocolTracker(registry_path)
    rows: list[dict[str, object]] = []
    try:
        for protocol_id in tracker.list_protocol_ids():
            rows.extend(slot.model_dump(mode="json") for slot in tracker.list_slots(protocol_id))
    except (OSError, sqlite3.Error, ProtocolTrackingError) as exc:
        return ServiceError("Protocol tracking state could not be loaded.", str(exc))
    return rows


def initialise_protocol_tracking_for_ui(
    registry_path: str | Path,
    experiment_id: str,
) -> dict[str, object] | ServiceError:
    """Create manual tracking rows from a registered experiment protocol."""

    try:
        registry = Registry(registry_path)
        experiment = registry.get_experiment(experiment_id)
        seeds = {seed.seed_id: seed for seed in registry.list_seeds()}
        protocol = build_experiment_protocol(experiment, seeds)
        created = ProtocolTracker(registry_path).register_protocol(protocol)
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        RegistryNotFoundError,
        ProtocolTrackingError,
    ) as exc:
        return ServiceError("Protocol tracking could not be initialised.", str(exc))
    return {
        "protocol_id": protocol.protocol_id,
        "slot_count": len(protocol.slots),
        "created": created,
    }


def update_protocol_slot_for_ui(
    registry_path: str | Path,
    protocol_id: str,
    slot_id: str,
    status: str,
    *,
    run_id: str = "",
    bundle_id: str = "",
    note: str = "",
) -> dict[str, object] | ServiceError:
    """Apply a manual protocol-slot transition through the typed tracker."""

    try:
        record = ProtocolTracker(registry_path).update_slot(
            protocol_id,
            slot_id,
            ProtocolSlotStatus(status),
            observed_run_id=run_id or None,
            observed_bundle_id=bundle_id or None,
            note=note or None,
        )
    except (OSError, sqlite3.Error, ValueError, ProtocolTrackingError) as exc:
        return ServiceError("Protocol slot could not be updated.", str(exc))
    return record.model_dump(mode="json")


def load_experiment_planner_catalog(
    registry_path: str | Path,
) -> ExperimentPlannerCatalog | ServiceError:
    """Load typed seeds, experiments, and known policy labels for planning."""

    path = Path(registry_path)
    try:
        registry = Registry(path)
        registry.initialize()
        seeds = registry.list_seeds()
        experiments = registry.list_experiments()
        runs = registry.list_runs()
    except (OSError, sqlite3.Error, ValueError) as exc:
        return ServiceError("The experiment-planning catalogue could not be loaded.", str(exc))
    algorithms = sorted(
        {
            *(seed.policy.algorithm for seed in seeds),
            *(run.algorithm for run in runs),
        }
    )
    return ExperimentPlannerCatalog(
        registry_path=path,
        seeds=seeds,
        experiments=experiments,
        algorithms=algorithms,
    )


def prepare_experiment_plan_for_ui(
    *,
    experiment_id: str,
    research_question: str,
    hypothesis: str,
    baseline_seed_id: str,
    variation_seed_ids: list[str],
    algorithms: list[str],
    additional_algorithm_labels: str,
    common_random_seeds: str,
    registered_seeds: list[ScenarioSeed],
    clock: Callable[[], datetime] | None = None,
) -> ExperimentPlanSummary | ServiceError:
    """Build and validate an experiment plan from UI form values."""

    try:
        random_seeds = _parse_nonnegative_int_csv(common_random_seeds)
        combined_algorithms = [
            *(algorithm.strip() for algorithm in algorithms if algorithm.strip()),
            *_split_csv(additional_algorithm_labels),
        ]
        now = clock() if clock is not None else datetime.now(UTC)
        experiment = Experiment(
            experiment_id=experiment_id.strip(),
            research_question=research_question.strip(),
            hypothesis=hypothesis.strip() or None,
            baseline_seed_id=baseline_seed_id,
            variation_seed_ids=variation_seed_ids,
            algorithms=combined_algorithms,
            common_random_seed_set=random_seeds,
            planned_replicates=len(random_seeds),
            created_at=now,
            updated_at=now,
        )
        return summarise_experiment_plan(
            experiment,
            {seed.seed_id: seed for seed in registered_seeds},
        )
    except (ValidationError, ValueError) as exc:
        return ServiceError("The experiment plan is invalid.", str(exc))


def register_experiment_plan_for_ui(
    summary: ExperimentPlanSummary,
    registry_path: str | Path,
) -> Experiment | ServiceError:
    """Register a validated plan without creating or launching runs."""

    try:
        registry = Registry(registry_path)
        registry.initialize()
        summarise_experiment_plan(
            summary.experiment,
            {seed.seed_id: seed for seed in registry.list_seeds()},
        )
        registry.add_experiment(summary.experiment)
    except (DuplicateIdentifierError, OSError, sqlite3.Error, ValueError) as exc:
        return ServiceError("The experiment plan could not be registered.", str(exc))
    return summary.experiment


def experiment_plan_yaml_for_ui(summary: ExperimentPlanSummary) -> str:
    """Serialise a validated experiment plan to deterministic YAML."""

    return yaml.safe_dump(
        summary.experiment.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=False,
    )


def build_experiment_protocol_for_ui(
    experiment: Experiment,
    registered_seeds: list[ScenarioSeed],
) -> ExperimentProtocol | ServiceError:
    """Build a read-only execution protocol from typed planner inputs."""

    try:
        return build_experiment_protocol(
            experiment,
            {seed.seed_id: seed for seed in registered_seeds},
        )
    except ValueError as exc:
        return ServiceError("The experiment protocol could not be built.", str(exc))


def load_registered_experiment_protocol_for_ui(
    experiment_id: str,
    registry_path: str | Path,
) -> ExperimentProtocol | ServiceError:
    """Load a registered experiment and build its deterministic protocol."""

    try:
        registry = Registry(registry_path)
        registry.initialize()
        experiment = registry.get_experiment(experiment_id)
        seeds = registry.list_seeds()
    except (OSError, sqlite3.Error, RegistryNotFoundError, ValueError) as exc:
        return ServiceError("The registered experiment protocol could not be loaded.", str(exc))
    return build_experiment_protocol_for_ui(experiment, seeds)


def experiment_protocol_yaml_for_ui(protocol: ExperimentProtocol) -> str:
    """Return the versioned protocol as deterministic YAML."""

    return protocol_to_yaml(protocol)


def experiment_protocol_csv_for_ui(protocol: ExperimentProtocol) -> str:
    """Return the protocol slots as a deterministic CSV run sheet."""

    return protocol_to_csv(protocol)


def match_bundle_to_protocol_for_ui(
    protocol: ExperimentProtocol,
    bundle_path: str | Path,
) -> ProtocolBundleMatch | ServiceError:
    """Validate and match one completed bundle without importing it."""

    result = validate_bundle(bundle_path)
    if result.manifest is None or not result.report.may_import:
        codes = ", ".join(finding.code.value for finding in result.report.findings)
        return ServiceError(
            "The bundle was rejected and cannot be matched to the protocol.",
            codes or "No valid manifest was available.",
        )
    return match_bundle_manifest(protocol, result.manifest)


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
        if suffix not in {".md", ".html", ".json", ".pdf", ".svg", ".tex"}:
            continue
        stat = path.stat()
        entries.append(
            ReportEntry(
                path=path,
                name=path.name,
                report_type=_infer_report_type(path.name),
                format_label={
                    ".html": "HTML",
                    ".json": "JSON",
                    ".pdf": "PDF",
                    ".svg": "SVG",
                    ".tex": "LaTeX",
                }.get(suffix, "Markdown"),
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
    annotation_registry_path: str | Path | None = None,
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
        if annotation_registry_path is not None:
            registry_path = Path(annotation_registry_path)
            if not registry_path.is_file():
                return ServiceError(
                    "Annotation registry is unavailable.",
                    str(registry_path),
                )
            report = attach_registry_annotations(report, Registry(registry_path))
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix.lower() == ".json":
            output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        elif output.suffix.lower() == ".pdf":
            output.write_bytes(report_to_pdf_bytes(report))
        else:
            payload = (
                report_to_html(report)
                if output.suffix.lower() == ".html"
                else report_to_markdown(report)
            )
            output.write_text(payload, encoding="utf-8")
    except Exception as exc:
        return ServiceError("Report could not be generated.", str(exc))
    return output


def compare_structured_reports_for_ui(
    baseline_path: str | Path,
    variation_path: str | Path,
) -> StructuredReportDiffView | ServiceError:
    """Compare two saved report JSON payloads through the REP-03 library boundary."""

    try:
        baseline = parse_research_report_json(Path(baseline_path).read_bytes())
        variation = parse_research_report_json(Path(variation_path).read_bytes())
        report = compare_structured_reports(baseline, variation)
        return StructuredReportDiffView(
            report=report,
            json_payload=report.model_dump_json(indent=2) + "\n",
            markdown_payload=report_diff_to_markdown(report),
        )
    except (OSError, ReportDiffError) as exc:
        return ServiceError("Structured reports could not be compared.", str(exc))


def build_executive_summary_for_ui(
    source_report_path: str | Path,
) -> ExecutiveSummaryView | ServiceError:
    """Build all REP-04 outputs from one saved typed report through the library boundary."""

    source = Path(source_report_path)
    try:
        report = parse_research_report_json(source.read_bytes())
        summary = project_executive_summary(
            report,
            source_report_reference=source.name,
        )
        return ExecutiveSummaryView(
            summary=summary,
            json_payload=summary.model_dump_json(indent=2) + "\n",
            markdown_payload=executive_summary_to_markdown(summary),
            html_payload=executive_summary_to_html(summary),
            pdf_payload=executive_summary_to_pdf_bytes(summary),
        )
    except (
        OSError,
        ReportDiffError,
        ExecutiveSummaryError,
        ExecutiveSummaryLayoutError,
    ) as exc:
        return ServiceError("Executive summary could not be generated.", str(exc))


def append_analyst_annotation_for_ui(
    registry_path: str | Path,
    *,
    target_kind: AnalystAnnotationTargetKind | str,
    target_id: str,
    author_label: str,
    note: str,
    decision_label: AnalystDecisionLabel | str = AnalystDecisionLabel.OBSERVATION,
    target_fingerprint: str | None = None,
) -> AnalystAnnotation | ServiceError:
    """Append one REP-02 annotation through the typed registry boundary."""

    try:
        request = AnalystAnnotationRequest(
            target=AnalystArtifactReference(
                kind=AnalystAnnotationTargetKind(target_kind),
                artifact_id=target_id,
                artifact_fingerprint=target_fingerprint or None,
            ),
            author_label=author_label,
            note=note,
            decision_label=AnalystDecisionLabel(decision_label),
        )
        return Registry(registry_path).append_analyst_annotation(request)
    except Exception as exc:
        return ServiceError("Analyst annotation could not be appended.", str(exc))


def list_analyst_annotations_for_ui(
    registry_path: str | Path,
    *,
    target_kind: AnalystAnnotationTargetKind | str,
    target_id: str,
    target_fingerprint: str | None = None,
    limit: int = 100,
) -> AnalystAnnotationHistory | ServiceError:
    """Read one target-scoped REP-02 history page for the Reports UI."""

    try:
        target = AnalystArtifactReference(
            kind=AnalystAnnotationTargetKind(target_kind),
            artifact_id=target_id,
            artifact_fingerprint=target_fingerprint or None,
        )
        return Registry(registry_path).list_analyst_annotations(target=target, limit=limit)
    except Exception as exc:
        return ServiceError("Analyst annotation history could not be loaded.", str(exc))


def generate_research_export_for_ui(
    export_kind: Literal["metrics", "comparison", "statistical_study", "rules"],
    primary_path: str | Path,
    table_output_path: str | Path,
    *,
    secondary_path: str | Path | None = None,
    figure_output_path: str | Path | None = None,
    overwrite: bool = False,
) -> ResearchExportReceipt | ServiceError:
    """Build REP-01 outputs through the deterministic reporting library."""

    try:
        if export_kind == "statistical_study":
            study = parse_statistical_study_json(Path(primary_path).read_bytes())
            projection = project_statistical_study(study)
        else:
            primary = validate_bundle_for_ui(primary_path)
            if primary.metrics is None or primary.diagnostic_report is None:
                return ServiceError(
                    "Research export requires an accepted bundle.",
                    primary.validation.report.status.value,
                )
            if export_kind == "metrics":
                projection = project_metric_collection(primary.metrics)
            elif export_kind == "rules":
                projection = project_diagnostic_report(primary.diagnostic_report)
            elif export_kind == "comparison":
                if secondary_path is None:
                    return ServiceError("Comparison export requires a second bundle path.")
                secondary = validate_bundle_for_ui(secondary_path)
                if secondary.metrics is None:
                    return ServiceError(
                        "Comparison export requires two accepted bundles.",
                        secondary.validation.report.status.value,
                    )
                projection = project_comparison_report(
                    compare_metric_collections(primary.metrics, secondary.metrics)
                )
            else:
                return ServiceError("Unsupported research export kind.", export_kind)
        return write_projection_exports(
            projection,
            table_output_path,
            figure_path=figure_output_path,
            overwrite=overwrite,
        )
    except (FileExistsError, OSError, ValidationError, ValueError) as exc:
        return ServiceError("Research export could not be generated.", str(exc))


def search_for_ui(
    query: str,
    registry_path: str | Path,
    workspace_path: str | Path | None = None,
    *,
    categories: list[SearchCategory | str] | None = None,
    limit: int = 50,
) -> RegistrySearchResult | ServiceError:
    """Run bounded REP-05 search through the tested read-only library boundary."""

    try:
        return search_registry(
            registry_path,
            query,
            workspace_path=workspace_path,
            categories=categories,
            limit=limit,
        )
    except (OSError, RegistrySearchError) as exc:
        return ServiceError("Registry search could not be completed.", str(exc))


def about_info_for_ui() -> AboutInfo:
    """Return project metadata for the About page."""

    metadata = current_release_metadata()
    return AboutInfo(
        package_version=metadata.version,
        generator_version=SYNTHETIC_GENERATOR_VERSION,
        metric_version=MetricEngineConfig().metric_version,
        diagnostic_version="ruleset-1.3",
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


def compute_run_metrics_for_ui(
    result: BundleValidationResult,
    config: MetricEngineConfig | None = None,
) -> MetricCollection:
    """Compute metrics through the Phase 3 engine."""

    return compute_metrics_for_bundle(result, config or MetricEngineConfig())


def metric_plugin_api_for_ui() -> MetricPluginApiContract:
    """Return the read-only trusted-extension boundary for UI explanation."""

    return metric_plugin_api_contract()


def declarative_rule_contract_for_ui() -> DeclarativeRuleContract:
    """Return the read-only closed declarative-rule grammar boundary for UI explanation."""

    return declarative_rule_contract()


def compute_windowed_metrics_for_ui(
    result: BundleValidationResult,
    *,
    width_s: float,
    alignment_origin_s: float = 0.0,
    analysis_start_s: float | None = None,
    analysis_end_s: float | None = None,
    partial_window_policy: str = "include",
) -> WindowedMetricSeries | ServiceError:
    """Validate UI inputs and call the deterministic fixed-window metric service."""

    try:
        config = WindowedMetricConfig(
            width_s=width_s,
            alignment_origin_s=alignment_origin_s,
            analysis_start_s=analysis_start_s,
            analysis_end_s=analysis_end_s,
            partial_window_policy=PartialWindowPolicy(partial_window_policy),
        )
        return compute_windowed_metrics_for_bundle(result, config)
    except (ValueError, WindowLimitExceededError) as exc:
        return ServiceError("Windowed metrics could not be computed.", str(exc))


def evaluate_temporal_diagnostics_for_ui(
    result: BundleValidationResult,
    series: WindowedMetricSeries,
    *,
    metric_key: str,
    minimum_window_coverage: float = 1.0,
    event_time_s: float | None = None,
    event_label: str | None = None,
    baseline_window_count: int = 2,
    minimum_evaluable_windows: int = 4,
    minimum_deterioration_delta: float = 0.10,
    sustained_window_count: int = 2,
    recovery_tolerance: float = 0.05,
    recovery_horizon_windows: int = 4,
) -> TemporalDiagnosticAnalysis | ServiceError:
    """Validate R6 controls and delegate all temporal calculations to library services."""

    try:
        temporal_config = TemporalEvidenceConfig(
            metric_key=metric_key,
            minimum_window_coverage=minimum_window_coverage,
            event_time_s=event_time_s,
            event_label=event_label,
        )
        rule_config = RuleSetConfig(
            r6=R6Config(
                baseline_window_count=baseline_window_count,
                minimum_evaluable_windows=minimum_evaluable_windows,
                minimum_deterioration_delta=minimum_deterioration_delta,
                sustained_window_count=sustained_window_count,
                recovery_tolerance=recovery_tolerance,
                recovery_horizon_windows=recovery_horizon_windows,
            )
        )
        return evaluate_temporal_series(
            result,
            series,
            temporal_config,
            rule_config=rule_config,
        )
    except ValueError as exc:
        return ServiceError("Temporal diagnosis could not be evaluated.", str(exc))


def evaluate_fairness_diagnostic_for_ui(
    pack: EvidencePack,
    *,
    dimension: str = "vehicle_tier_completion",
    minimum_outcome_gap: float = 0.20,
    minimum_group_support: int = 2,
) -> RuleResult | ServiceError:
    """Validate R7 controls and delegate all rule evaluation to the library engine."""

    try:
        r7 = R7Config.model_validate(
            {
                "dimension": dimension,
                "minimum_outcome_gap": minimum_outcome_gap,
                "minimum_group_support": minimum_group_support,
            }
        )
        config = RuleSetConfig.model_validate(
            {
                "r0": {"enabled": False},
                "r1": {"enabled": False},
                "r2": {"enabled": False},
                "r3": {"enabled": False},
                "r4": {"enabled": False},
                "r5": {"enabled": False},
                "r6": {"enabled": False},
                "r7": r7.model_dump(mode="json"),
                "r8": {"enabled": False},
            }
        )
        return evaluate_rules(pack, config).results[0]
    except ValueError as exc:
        return ServiceError("Operational fairness diagnosis could not be evaluated.", str(exc))


def evaluate_energy_diagnostic_for_ui(
    pack: EvidencePack,
    *,
    minimum_energy_per_completed_task_j: float = 1.50,
    minimum_completed_tasks: int = 10,
) -> RuleResult | ServiceError:
    """Validate R8 controls and delegate all rule evaluation to the library engine."""

    try:
        r8 = R8Config(
            minimum_energy_per_completed_task_j=minimum_energy_per_completed_task_j,
            minimum_completed_tasks=minimum_completed_tasks,
        )
        config = RuleSetConfig.model_validate(
            {
                "r0": {"enabled": False},
                "r1": {"enabled": False},
                "r2": {"enabled": False},
                "r3": {"enabled": False},
                "r4": {"enabled": False},
                "r5": {"enabled": False},
                "r6": {"enabled": False},
                "r7": {"enabled": False},
                "r8": r8.model_dump(mode="json"),
            }
        )
        return evaluate_rules(pack, config).results[0]
    except ValueError as exc:
        return ServiceError("Completed-task energy diagnosis could not be evaluated.", str(exc))


def evaluate_threshold_sweep_for_ui(
    pack: EvidencePack,
    *,
    rule_id: str,
    minimum_threshold: float,
    maximum_threshold: float,
    point_count: int,
    rule_config: RuleSetConfig | None = None,
) -> ThresholdSensitivityReport | ServiceError:
    """Validate DIA-06 controls and delegate the complete grid to the library service."""

    try:
        request = ThresholdSweepRequest(
            rule_id=rule_id,
            minimum_threshold=minimum_threshold,
            maximum_threshold=maximum_threshold,
            point_count=point_count,
        )
        return evaluate_threshold_sweep(pack, request, rule_config)
    except (RuntimeError, ValueError) as exc:
        return ServiceError("Threshold sensitivity could not be evaluated.", str(exc))


def parse_rule_config_json_for_ui(payload: str | bytes) -> RuleSetConfig | ServiceError:
    """Validate one explicitly supplied complete RuleSetConfig JSON payload."""

    try:
        return RuleSetConfig.model_validate_json(payload)
    except (UnicodeDecodeError, ValidationError, ValueError) as exc:
        return ServiceError("Rule configuration could not be imported.", str(exc))


def rule_config_json_for_ui(config: RuleSetConfig) -> str:
    """Return an explicit complete config export without persisting it."""

    return config.model_dump_json(indent=2)


def sweep_point_config_json_for_ui(
    report: ThresholdSensitivityReport,
    source_config: RuleSetConfig,
    threshold: float,
) -> str | ServiceError:
    """Return one complete validated config for an exact retained DIA-06 point."""

    try:
        config = config_for_evaluated_point(report, source_config, threshold)
        return rule_config_json_for_ui(config)
    except ValueError as exc:
        return ServiceError("Evaluated-point configuration could not be exported.", str(exc))


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


def metric_contributions_for_ui(
    analysis: BundleAnalysis,
    metric_key: str,
) -> MetricContributionReport:
    """Build the complete canonical-row contribution ledger for one metric."""

    return get_metric_contributions(provenance_context_for_ui(analysis), metric_key)


def rule_provenance_for_ui(analysis: BundleAnalysis, rule_id: str) -> ProvenanceTrace:
    """Build a diagnostic-rule provenance trace for the selected analysis."""

    return get_rule_provenance(provenance_context_for_ui(analysis), rule_id)


def run_provenance_for_ui(analysis: BundleAnalysis) -> ProvenanceTrace:
    """Build a run-level provenance trace for the selected analysis."""

    return get_run_provenance(provenance_context_for_ui(analysis))


def provenance_graph_for_ui(
    trace: ProvenanceTrace,
    *,
    node_limit: int,
    edge_limit: int,
    redaction_mode: GraphRedactionMode | str = GraphRedactionMode.SAFE,
) -> ProvenanceGraphView | ServiceError:
    """Build the typed bounded graph projection used by the explorer and downloads."""

    try:
        return get_provenance_graph_view(
            trace,
            node_limit=node_limit,
            edge_limit=edge_limit,
            redaction_mode=redaction_mode,
        )
    except ProvenanceQueryError as exc:
        return ServiceError("The bounded provenance graph is unavailable.", str(exc))


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


def difference_contributions_for_ui(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
    metric_key: str,
) -> DifferenceContributionReport | ServiceError:
    """Build typed PRO-01 lineage without placing arithmetic in the UI."""

    try:
        return get_difference_contributions(
            provenance_context_for_ui(baseline),
            provenance_context_for_ui(variation),
            metric_key,
        )
    except ProvenanceQueryError as exc:
        return ServiceError("Difference provenance is unavailable.", str(exc))


def report_provenance_completeness_for_ui(
    analysis: BundleAnalysis,
    report_type: ResearchReportType | str,
) -> ProvenanceCompletenessReport | ServiceError:
    """Build the typed PRO-03 denominator and classifications for one report template."""

    try:
        return get_report_provenance_completeness(
            provenance_context_for_ui(analysis),
            report_type,
        )
    except ProvenanceQueryError as exc:
        return ServiceError("Report provenance completeness is unavailable.", str(exc))


def comparison_provenance_completeness_for_ui(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
) -> ProvenanceCompletenessReport | ServiceError:
    """Build the typed PRO-03 denominator for one comparison report."""

    try:
        return get_comparison_provenance_completeness(
            provenance_context_for_ui(baseline),
            provenance_context_for_ui(variation),
        )
    except ProvenanceQueryError as exc:
        return ServiceError("Comparison provenance completeness is unavailable.", str(exc))


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


def _find_tos_run(
    rows: list[TosEvaluationRun],
    identifier: str,
) -> TosEvaluationRun:
    for row in rows:
        if identifier in {row.run_id, row.source_key, instrumented_key_for_run(row)}:
            return row
    raise TosPackageError(f"TOS evaluation run not found: {identifier}")


def _optional_int(value: object) -> int | None:
    if value in {"", None}:
        return None
    return _as_int(value)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_nonnegative_int_csv(value: str) -> list[int]:
    tokens = _split_csv(value)
    if not tokens:
        raise ValueError("at least one common random seed is required")
    try:
        parsed = [int(token) for token in tokens]
    except ValueError as exc:
        raise ValueError("common random seeds must be comma-separated integers") from exc
    if any(seed < 0 for seed in parsed):
        raise ValueError("common random seeds must be non-negative")
    if len(set(parsed)) != len(parsed):
        raise ValueError("common random seeds must not contain duplicates")
    return parsed


def _parse_sweep_values(value: str) -> list[JsonScalar]:
    tokens = _split_csv(value)
    if not tokens:
        raise ValueError("every enabled sweep axis requires at least one value")
    parsed: list[JsonScalar] = []
    for token in tokens:
        try:
            item = yaml.safe_load(token)
        except yaml.YAMLError as exc:
            raise ValueError("sweep values must be comma-separated scalar YAML values") from exc
        if not isinstance(item, str | int | float | bool):
            raise ValueError("sweep values must be non-null scalar YAML values")
        parsed.append(item)
    return parsed


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


def _git_commit_hash() -> str | None:
    git_marker = Path(".git")
    git_dir = _resolve_git_directory(git_marker)
    if git_dir is None:
        return None
    head = _read_git_text(git_dir / "HEAD")
    if head is None:
        return None
    if head.startswith("ref: "):
        ref_name = head.removeprefix("ref: ").strip()
        common_dir = _resolve_git_common_directory(git_dir)
        for root in dict.fromkeys((git_dir, common_dir)):
            value = _read_git_text(root / ref_name)
            if value:
                return value[:12]
        packed_refs = _read_git_text(common_dir / "packed-refs")
        if packed_refs is not None:
            suffix = f" {ref_name}"
            for line in packed_refs.splitlines():
                if not line.startswith(("#", "^")) and line.endswith(suffix):
                    return line.split(" ", maxsplit=1)[0][:12]
        return None
    return head[:12] if head else None


def _resolve_git_directory(marker: Path) -> Path | None:
    """Resolve a normal ``.git`` directory or a linked-worktree marker."""

    if marker.is_dir():
        return marker
    content = _read_git_text(marker)
    if content is None or not content.startswith("gitdir: "):
        return None
    candidate = Path(content.removeprefix("gitdir: ").strip())
    if not candidate.is_absolute():
        candidate = marker.parent / candidate
    return candidate.resolve() if candidate.is_dir() else None


def _resolve_git_common_directory(git_dir: Path) -> Path:
    """Return the shared Git directory for a linked worktree when present."""

    content = _read_git_text(git_dir / "commondir")
    if content is None:
        return git_dir
    candidate = Path(content)
    if not candidate.is_absolute():
        candidate = git_dir / candidate
    resolved = candidate.resolve()
    return resolved if resolved.is_dir() else git_dir


def _read_git_text(path: Path) -> str | None:
    """Read small Git metadata defensively for optional About-page display."""

    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
