"""Frozen view/catalog dataclasses shared by the UI service modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from traffictwin.config.capabilities import CapabilityManifest
from traffictwin.demo.workspace import WorkspaceStatus
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evidence.pack import EvidencePack
from traffictwin.experiments.parameter_sweep import (
    ParameterSweepMode,
    SweepParameter,
)
from traffictwin.experiments.portfolio import (
    PortfolioEvaluationReport,
    PortfolioStudyReport,
)
from traffictwin.experiments.scenario_mutation import (
    MutationOperator,
    MutationTableKind,
)
from traffictwin.experiments.winner_map import WinnerMapReport
from traffictwin.ingestion.bundle import (
    BundleValidationResult,
)
from traffictwin.integration.tos import (
    TosEvaluationMatrix,
    TosEvaluationRun,
    TosGeneralisationMatrix,
    TosSourceContract,
    TosValidationReport,
)
from traffictwin.integration.tos.analysis_models import TosAnalysisMeasureDefinition
from traffictwin.metrics.results import MetricCollection
from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.reporting.diffing import (
    StructuredReportDiff,
)
from traffictwin.reporting.executive import (
    ExecutiveSummary,
)
from traffictwin.storage.registry import (
    RegistrySummary,
)
from traffictwin.synthetic.config import (
    SyntheticScenarioConfig,
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
