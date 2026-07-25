"""Command-line interface for Phase 1 TrafficTwin workflows."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, cast

import typer
import yaml

from traffictwin.annotations import (
    AnalystAnnotationRequest,
    AnalystAnnotationTargetKind,
    AnalystArtifactReference,
    AnalystDecisionLabel,
    analyst_annotation_contract,
)
from traffictwin.case_studies import build_synthetic_case_study_pack
from traffictwin.config.capabilities import default_export_import_manifest, manifest_to_plain_dict
from traffictwin.config.seed_io import SeedIOError, load_seed, normalise_seed_file
from traffictwin.demo.launcher import launch_workspace
from traffictwin.demo.workspace import initialise_workspace, reset_workspace, workspace_status
from traffictwin.diagnostics.cross_rule import cross_rule_reasoning_contract
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.diagnostics.sensitivity import analyse_nearest_flip
from traffictwin.diagnostics.temporal import evaluate_temporal_bundle
from traffictwin.doctor import (
    DoctorOverallStatus,
    doctor_contract,
    doctor_contract_to_text,
    doctor_report_to_text,
    run_doctor,
)
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.measurement import measurement_impairment_contract
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.evaluation.participants import (
    analyse_participant_results,
    load_mock_participant_dataset,
    participant_analysis_to_csv,
)
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import TemporalEvidenceConfig
from traffictwin.experiments.equivalence_testing import (
    EquivalenceMarginBasis,
    EquivalenceStudyConfig,
    EquivalenceStudyStatus,
    equivalence_study_to_csv,
    equivalence_study_to_markdown,
    equivalence_testing_contract,
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
    NWayRankingStatus,
    evaluate_n_way_ranking,
    n_way_ranking_contract,
    n_way_ranking_to_csv,
    n_way_ranking_to_markdown,
)
from traffictwin.experiments.parameter_sweep import (
    ParameterSweepError,
    execute_parameter_sweep,
    load_parameter_sweep_request,
    parameter_sweep_contract,
)
from traffictwin.experiments.portfolio import (
    default_synthetic_portfolio_rules,
    evaluate_portfolio,
    evaluate_portfolio_study,
    portfolio_study_to_csv,
    portfolio_study_to_markdown,
)
from traffictwin.experiments.power_analysis import (
    PairedVarianceBasis,
    PowerAnalysisConfig,
    PowerAnalysisStatus,
    TargetEffectBasis,
    evaluate_power_analysis,
    power_analysis_method_contract,
    power_analysis_to_csv,
    power_analysis_to_markdown,
)
from traffictwin.experiments.protocol import (
    ExperimentProtocol,
    ProtocolMatchStatus,
    build_experiment_protocol,
    match_bundle_manifest,
    protocol_to_csv,
    protocol_to_yaml,
)
from traffictwin.experiments.regression_gate import (
    GoldenApprovalStatus,
    RegressionGateStatus,
    RegressionSubject,
    RegressionSubjectKind,
    RegressionToleranceSpec,
    SourceIdentityPolicy,
    build_regression_golden_contract,
    evaluate_regression_gate,
    parse_regression_golden_contract_json,
    parse_statistical_study_json,
    regression_gate_method_contract,
    regression_gate_to_csv,
    regression_gate_to_markdown,
)
from traffictwin.experiments.scenario_mutation import (
    ScenarioMutationError,
    execute_scenario_mutation,
    load_scenario_mutation_request,
    scenario_mutation_contract,
)
from traffictwin.experiments.statistical_study import (
    PairedStudyConfig,
    StatisticalStudyStatus,
    evaluate_paired_statistical_study,
    statistical_study_contract,
    statistical_study_pairs_to_csv,
    statistical_study_to_markdown,
)
from traffictwin.experiments.tracking import (
    InvalidProtocolSlotTransitionError,
    ProtocolSlotStatus,
    ProtocolTracker,
    ProtocolTrackingError,
)
from traffictwin.experiments.winner_map import build_winner_map
from traffictwin.ingestion.batch import (
    BatchBundleSummary,
    batch_summary_to_csv,
    batch_summary_to_text,
    import_bundle_batch,
    validate_bundle_batch,
)
from traffictwin.ingestion.bundle import (
    BundleValidationResult,
    import_bundle_streaming,
    inspect_bundle,
    inspect_bundle_cache,
    validate_bundle,
    validate_bundle_cached,
    validate_bundle_streaming,
)
from traffictwin.ingestion.bundle import (
    import_bundle as import_run_bundle,
)
from traffictwin.ingestion.cache import (
    CanonicalCacheConfigurationError,
    CanonicalCacheState,
    CanonicalCacheStatus,
    canonical_cache_contract,
)
from traffictwin.ingestion.manifest_inference import (
    CanonicalisationManifest,
    FileSelection,
    ManifestInferenceError,
    ManifestInferenceSelections,
    apply_canonicalisation_to_template,
    bundle_manifest_to_yaml,
    confirm_manifest_inference,
    infer_manifest,
    load_canonicalisation_manifest,
    load_inference_draft,
    manifest_inference_contract,
)
from traffictwin.ingestion.streaming import (
    DEFAULT_STREAM_CHUNK_ROWS,
    DEFAULT_STREAM_MAX_BUNDLE_BYTES,
    DEFAULT_STREAM_MAX_CHUNK_BYTES,
    DEFAULT_STREAM_MAX_TABLE_BYTES,
    StreamingBundleValidationResult,
    StreamingCanonicalisationConfig,
)
from traffictwin.integration.external import (
    DiscoveryReportStatus,
    ExternalSourceError,
    ValidationOutcome,
    discover_external_sources,
    external_source_catalogue,
    inspect_external_source,
)
from traffictwin.integration.manchester.demand_reconstruction import (
    DemandReconstructionError,
    EdgeHourCount,
    ordinals_by_edge_id,
    resolve_direction,
    site_is_in_survey_window,
    write_edgedata_counts,
)
from traffictwin.integration.manchester.dft_acquisition import (
    DftAcquisitionError,
    DftAcquisitionRequest,
    DftDataset,
    acquire_dft_snapshot,
    catalogue_accepted_dft_snapshots,
    open_accepted_dft_snapshot,
)
from traffictwin.integration.manchester.dft_temporal_profile import (
    MAX_PROFILE_ARTIFACT_BYTES,
    DftTemporalProfileError,
    DftTemporalProfilePolicy,
    ManchesterDftTemporalProfile,
    build_dft_temporal_profile,
    open_real_raw_count_evidence,
    profile_service_status,
    simulation_interval_for_hour,
    write_profile_record,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterSnapshotPolicy,
    sha256_hex,
)
from traffictwin.integration.manchester.network_acquisition import (
    OSM_MAX_EXTRACT_BYTES,
    OSM_REFERENCE_DATE,
    LocalOsmExtractImportRequest,
    OperatorAuthorisation,
    OsmAcquisitionError,
    OsmExtractAcquisitionRequest,
    OsmExtractIdentity,
    acquire_osm_extract_snapshot,
    import_local_osm_extract,
)
from traffictwin.integration.manchester.network_build import (
    ManchesterBaselineNetworkBinding,
    NetworkBuildError,
    NetworkBuildRequest,
    build_baseline_network,
    check_builder_input_format,
)
from traffictwin.integration.manchester.network_connectivity import (
    DEFAULT_CONTRAST_PROBES,
    DEFAULT_ROUTE_PROBES,
    ELIGIBILITIES,
    MAX_ROUTE_PROBES,
    Eligibility,
    NetworkConnectivityError,
    review_network_connectivity,
    stream_network_edges,
)
from traffictwin.integration.manchester.network_decode import (
    NetworkDecodeError,
    decode_pbf_to_osm_xml,
    pinned_source_expectation,
    verify_decoded_artifact,
)
from traffictwin.integration.manchester.network_geometry import (
    NetworkGeometryError,
    build_edge_index,
)
from traffictwin.integration.manchester.network_scope import baseline_scope_decision
from traffictwin.integration.manchester.network_service import (
    NETWORKS_DIRECTORY_NAME,
    baseline_network_status,
    inspect_network_candidate,
    list_network_candidates,
    write_connectivity_record,
)
from traffictwin.integration.manchester.observation_matching import (
    ObservationMatchingError,
    dft_road_reference,
)
from traffictwin.integration.manchester.observation_matching_v11 import (
    MAP_MATCH_POLICY_V11_ID,
    ManchesterMapMatchPolicyV11,
    ObservationMatchV11,
    build_manual_review_queue,
    match_observation_v11,
)
from traffictwin.integration.manchester.owner_candidate_contracts import (
    COMPARISON_CONTRACT_VERSION,
    comparison_contract_fingerprint,
    comparison_contract_is_registered,
)
from traffictwin.integration.manchester.sumo_run import (
    ManchesterSumoRunError,
    sumo_identity,
)
from traffictwin.integration.manchester.workflow_service import (
    manchester_workflow_status,
)
from traffictwin.integration.sumo import (
    compute_metrics_for_sumo,
    import_sumo_results,
    sumo_source_contract,
    validate_sumo_results,
)
from traffictwin.integration.sumo_execution import (
    SumoExecutionError,
    SumoExecutionPreset,
    SumoWorkflowRequest,
    SumoWorkflowStatus,
    execute_and_import_sumo,
    import_sumo_execution,
    preset_definition,
    sumo_runtime_status,
)
from traffictwin.integration.tos import (
    TosEvaluationRun,
    audit_tos_package,
    build_evaluation_matrix,
    build_generalisation_matrix,
    build_static_results_atlas,
    build_tos_evidence_pack,
    build_tos_integration_readiness,
    build_tos_metric_trace,
    build_tos_research_report,
    build_tos_rule_trace,
    compare_campaigns,
    import_evaluation_summaries,
    list_instrumented_runs,
    list_training_runs,
    load_replay_frame,
    load_rsu_replay_series,
    load_task_sample,
    load_training_run,
    metric_collection_from_evaluation,
    read_evaluation_runs,
    stage_public_tos_atlas,
    summarise_rsu_run,
    summarise_task_outcomes,
    summarise_trace,
    tos_source_contract,
    validate_tos_package,
    write_tos_results_pack,
    write_tos_supervisor_pack,
)
from traffictwin.integration.tos.readers import TosPackageError, instrumented_key_for_run
from traffictwin.integration.vec_interface import (
    VecInterfaceError,
    compare_vec_admissions,
    export_vec_admission,
    inspect_vec_artifact,
    inspect_vec_interface,
    load_preprocess_request,
    load_run_request,
    load_scientific_admission,
    vec_interface_contract,
)
from traffictwin.integration.vec_orchestration import (
    VecExecutionPreset,
    VecOrchestrationError,
    VecWorkflowRequest,
    VecWorkflowStatus,
    execute_and_import,
    import_vec_execution,
    preset_workload,
)
from traffictwin.integration.vec_preprocessing import (
    VecFcdPreflightReport,
    VecFcdPreprocessingError,
    preflight_vec_fcd,
    preprocess_vec_fcd,
)
from traffictwin.integration.vec_research import (
    VecEndToEndResearchError,
    create_vec_end_to_end_archive,
    vec_end_to_end_contract,
    verify_vec_end_to_end_archive,
)
from traffictwin.integration.vec_runner import (
    VecRunnerError,
    VecRunnerPreflightReport,
    preflight_vec_run,
    run_vec_evaluator,
)
from traffictwin.metrics.aggregation import aggregate_experiment
from traffictwin.metrics.comparison import compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.plugins import metric_plugin_api_contract
from traffictwin.metrics.results import MetricCollection, MetricStatus
from traffictwin.metrics.windowed import (
    PartialWindowPolicy,
    WindowedMetricConfig,
    WindowedMetricSeries,
    WindowLimitExceededError,
    compute_windowed_metrics_for_bundle,
)
from traffictwin.provenance.builder import build_window_metric_trace
from traffictwin.provenance.completeness import (
    ProvenanceCompletenessReport,
    provenance_completeness_contract,
    provenance_completeness_report_to_csv,
)
from traffictwin.provenance.contributions import (
    build_window_metric_contribution_report,
    contribution_report_to_csv,
)
from traffictwin.provenance.differences import (
    difference_contribution_report_to_csv,
    difference_provenance_contract,
)
from traffictwin.provenance.graph_export import (
    DEFAULT_GRAPH_EDGE_LIMIT,
    DEFAULT_GRAPH_NODE_LIMIT,
    MAX_GRAPH_EDGE_LIMIT,
    MAX_GRAPH_NODE_LIMIT,
    GraphRedactionMode,
    provenance_graph_export_contract,
)
from traffictwin.provenance.markdown import trace_to_markdown
from traffictwin.provenance.models import ProvenanceTrace
from traffictwin.provenance.query import (
    ProvenanceQueryError,
    build_provenance_context,
    export_provenance,
    get_comparison_provenance_completeness,
    get_difference_contributions,
    get_metric_contributions,
    get_metric_provenance,
    get_report_provenance_completeness,
    get_rule_provenance,
    get_run_provenance,
    get_source_provenance,
    node_type_counts,
)
from traffictwin.provenance.serialization import trace_to_json
from traffictwin.registry_search import (
    MAX_SEARCH_LIMIT,
    RegistrySearchError,
    SearchCategory,
    registry_search_contract,
    search_registry,
)
from traffictwin.release import (
    V06AttestationError,
    V06MigrationError,
    V07CompatibilityError,
    build_v06_producer_attestation,
    copy_v06_registry,
    current_release_metadata,
    initialise_v07_workspace,
    inspect_v07_workspace,
    load_v06_producer_attestation,
    migrate_v06_registry,
    preview_v06_migration,
    preview_v06_registry_copy,
    rollback_v06_migration,
    stage_synthetic_demo_site,
)
from traffictwin.rendering.findings import (
    diagnostic_narrative_to_markdown,
    render_diagnostic_findings,
)
from traffictwin.reporting.annotation_rendering import (
    ReportAnnotationError,
    attach_registry_annotations,
)
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.diffing import (
    ReportDiffError,
    compare_structured_reports,
    parse_research_report_json,
    report_diff_contract,
    report_diff_to_markdown,
)
from traffictwin.reporting.executive import (
    ExecutiveSummaryError,
    executive_summary_contract,
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
    ResearchExportProjection,
    latex_export_contract,
    project_comparison_report,
    project_diagnostic_report,
    project_metric_collection,
    project_statistical_study,
    write_projection_exports,
)
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.models import ReportBuildError, ResearchReport, ResearchReportType
from traffictwin.reporting.pdf import report_to_pdf_bytes
from traffictwin.research_object import (
    PermissionStatus,
    PublicationScope,
    RawEvidenceDisposition,
    ResearchObjectError,
    ResearchObjectRequest,
    create_research_object_archive,
    research_object_contract,
    verify_research_object,
)
from traffictwin.rules.config import R6Config, R7Config, R8Config, RuleSetConfig
from traffictwin.rules.declarative import (
    DeclarativeRuleError,
    declarative_rule_contract,
    evaluate_declarative_rule,
    load_declarative_rule,
)
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.evaluation import (
    build_extended_fixture_set,
    evaluate_fixture_set,
    load_fixture_set,
)
from traffictwin.storage.migrations import (
    CURRENT_REGISTRY_SCHEMA_VERSION,
    RegistryMigrationError,
    inspect_registry_migrations,
    migrate_registry,
    registry_migration_contract,
)
from traffictwin.storage.registry import (
    Registry,
    RegistryConflictError,
    RegistryError,
    RegistryNotFoundError,
)
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.config import load_synthetic_scenario_config
from traffictwin.synthetic.experiments import (
    PORTFOLIO_DEVELOPMENT_PRESETS,
    PORTFOLIO_HELD_OUT_PRESETS,
    PORTFOLIO_STUDY_EXPERIMENT_ID,
    generate_trivial_multi_algorithm_experiment,
)
from traffictwin.synthetic.scenarios import list_preset_names, preset_config
from traffictwin.synthetic.validation import verify_synthetic_path

app = typer.Typer(no_args_is_help=True, help="TrafficTwin research-software CLI.")
registry_app = typer.Typer(no_args_is_help=True, help="Metadata registry commands.")
bundle_app = typer.Typer(no_args_is_help=True, help="Run-bundle commands.")
metrics_app = typer.Typer(no_args_is_help=True, help="Deterministic metric commands.")
evidence_app = typer.Typer(no_args_is_help=True, help="Evidence-pack commands.")
experiment_app = typer.Typer(
    no_args_is_help=True,
    help="Experiment planning, protocol, and aggregation commands.",
)
diagnose_app = typer.Typer(no_args_is_help=True, help="Deterministic diagnostic commands.")
provenance_app = typer.Typer(no_args_is_help=True, help="Read-only provenance trace commands.")
synthetic_app = typer.Typer(no_args_is_help=True, help="Standalone synthetic fixture commands.")
demo_app = typer.Typer(no_args_is_help=True, help="Standalone demo workspace commands.")
report_app = typer.Typer(no_args_is_help=True, help="Deterministic research-report export.")
archive_app = typer.Typer(
    no_args_is_help=True,
    help="Permission-aware deterministic RO-Crate archival export.",
)
release_app = typer.Typer(no_args_is_help=True, help="Release and deployment-readiness commands.")
integration_app = typer.Typer(no_args_is_help=True, help="Evidence-gated external data tools.")
external_app = typer.Typer(
    no_args_is_help=True,
    help="General read-only external-source discovery and contract tools.",
)
tos_app = typer.Typer(no_args_is_help=True, help="Read-only TOS Data package tools.")
sumo_app = typer.Typer(no_args_is_help=True, help="Import-only Eclipse SUMO result tools.")
vec_app = typer.Typer(no_args_is_help=True, help="Capability-gated Randy/VEC workflows.")
manchester_app = typer.Typer(
    no_args_is_help=True,
    help="Bounded Manchester evidence and baseline-network tools.",
)
manchester_network_app = typer.Typer(
    no_args_is_help=True,
    help="Operator-invoked Greater Manchester baseline-network commands (MAN-09, planned).",
)
manchester_profile_app = typer.Typer(
    no_args_is_help=True,
    help="Read-only DfT temporal-profile candidate commands (MAN-09, planned).",
)
manchester_workflow_app = typer.Typer(
    no_args_is_help=True,
    help="Read-only status across the Manchester research workflow (MAN-09, planned).",
)
manchester_observation_app = typer.Typer(
    no_args_is_help=True,
    help="Operator-invoked DfT observation acquisition and inspection (MAN-02).",
)
manchester_match_app = typer.Typer(
    no_args_is_help=True,
    help="Read-only observation-to-network map-match views (MAN-09, planned).",
)
manchester_demand_app = typer.Typer(
    no_args_is_help=True,
    help="Count-constrained candidate demand views (MAN-09, planned).",
)
manchester_run_app = typer.Typer(
    no_args_is_help=True,
    help="Operator-invoked controlled SUMO execution (MAN-09, planned).",
)
MANCHESTER_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "docs" / "integration" / "evidence"

manchester_evidence_app = typer.Typer(
    no_args_is_help=True,
    help="Read-only lineage and permission-safe evidence export (MAN-09, planned).",
)
manifest_app = typer.Typer(
    no_args_is_help=True,
    help="Deterministic, confirmation-gated CSV manifest inference.",
)
participant_app = typer.Typer(
    no_args_is_help=True,
    help="Analyse explicitly labelled synthetic mock participant results.",
)
app.add_typer(registry_app, name="registry")
app.add_typer(bundle_app, name="bundle")
app.add_typer(metrics_app, name="metrics")
app.add_typer(evidence_app, name="evidence")
app.add_typer(experiment_app, name="experiment")
app.add_typer(diagnose_app, name="diagnose")
app.add_typer(provenance_app, name="provenance")
app.add_typer(synthetic_app, name="synthetic")
app.add_typer(demo_app, name="demo")
app.add_typer(report_app, name="report")
app.add_typer(archive_app, name="archive")
app.add_typer(release_app, name="release")
app.add_typer(integration_app, name="integration")
app.add_typer(participant_app, name="participant-evaluation")
app.add_typer(manifest_app, name="manifest")
integration_app.add_typer(tos_app, name="tos")
integration_app.add_typer(sumo_app, name="sumo")
integration_app.add_typer(external_app, name="external")
integration_app.add_typer(vec_app, name="vec")
integration_app.add_typer(manchester_app, name="manchester")
manchester_app.add_typer(manchester_network_app, name="network")
manchester_app.add_typer(manchester_profile_app, name="profile")
manchester_app.add_typer(manchester_workflow_app, name="workflow")
manchester_app.add_typer(manchester_observation_app, name="observation")
manchester_app.add_typer(manchester_match_app, name="match")
manchester_app.add_typer(manchester_demand_app, name="demand")
manchester_app.add_typer(manchester_run_app, name="run")
manchester_app.add_typer(manchester_evidence_app, name="evidence")


@vec_app.command("contract")
def vec_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the VEC-10 thin-interface and safety boundary."""

    contract = vec_interface_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"capability_id: {contract.capability_id}")
    typer.echo(f"execution_mode: {contract.execution_mode}")
    typer.echo("operations: " + ", ".join(contract.operations))
    typer.echo("prohibited: " + "; ".join(contract.prohibited_controls))
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@vec_app.command("snapshot")
def vec_snapshot_command(
    vec_repo: Annotated[Path, typer.Option("--vec-repo", exists=True, file_okay=False)],
    tos_data_repo: Annotated[Path, typer.Option("--tos-data-repo", exists=True, file_okay=False)],
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Inspect both pinned external repositories without modifying them."""

    try:
        snapshot = inspect_vec_interface(vec_repo, tos_data_repo)
        payload = snapshot.model_dump_json(indent=2) + "\n"
        if output is None:
            typer.echo(payload, nl=False)
        else:
            _vec_write_new(output, payload)
            typer.echo(f"snapshot: {output}")
    except (OSError, VecInterfaceError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("validate")
def vec_validate_command(
    kind: Annotated[str, typer.Option("--kind", help="preprocess or run")],
    request: Annotated[Path, typer.Option("--request", exists=True, dir_okay=False)],
    input_root: Annotated[Path, typer.Option("--input-root", exists=True, file_okay=False)],
    vec_repo: Annotated[Path, typer.Option("--vec-repo", exists=True, file_okay=False)],
    tos_data_repo: Annotated[
        Path | None, typer.Option("--tos-data-repo", exists=True, file_okay=False)
    ] = None,
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Run a request-specific VEC-06 or VEC-07 read-only preflight."""

    try:
        report: VecFcdPreflightReport | VecRunnerPreflightReport
        if kind == "preprocess":
            report = preflight_vec_fcd(input_root, vec_repo, load_preprocess_request(request))
        elif kind == "run":
            if tos_data_repo is None:
                raise VecInterfaceError("--tos-data-repo is required for --kind run")
            report = preflight_vec_run(
                input_root,
                vec_repo,
                tos_data_repo,
                load_run_request(request),
            )
        else:
            raise VecInterfaceError("--kind must be preprocess or run")
        payload = report.model_dump_json(indent=2) + "\n"
        if output is None:
            typer.echo(payload, nl=False)
        else:
            _vec_write_new(output, payload)
            typer.echo(f"preflight: {output}")
            typer.echo(f"status: {report.status.value}")
        if report.status.value != "accepted":
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except (OSError, VecInterfaceError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("preprocess")
def vec_preprocess_command(
    request: Annotated[Path, typer.Option("--request", exists=True, dir_okay=False)],
    input_root: Annotated[Path, typer.Option("--input-root", exists=True, file_okay=False)],
    vec_repo: Annotated[Path, typer.Option("--vec-repo", exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
) -> None:
    """Execute one accepted VEC-06 request in the foreground."""

    try:
        parsed = load_preprocess_request(request)
        typer.echo("state: validating")
        preflight = preflight_vec_fcd(input_root, vec_repo, parsed)
        typer.echo(f"preflight: {preflight.status.value}")
        if preflight.status.value != "accepted":
            raise typer.Exit(code=1)
        typer.echo("state: running_foreground")
        receipt = preprocess_vec_fcd(input_root, vec_repo, output, parsed)
        typer.echo(f"state: {receipt.status}")
        typer.echo(f"receipt: {output / 'preprocessing_receipt.json'}")
        typer.echo(f"fingerprint: {receipt.fingerprint()}")
    except typer.Exit:
        raise
    except (OSError, VecInterfaceError, VecFcdPreprocessingError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("run")
def vec_run_command(
    request: Annotated[Path, typer.Option("--request", exists=True, dir_okay=False)],
    input_root: Annotated[Path, typer.Option("--input-root", exists=True, file_okay=False)],
    vec_repo: Annotated[Path, typer.Option("--vec-repo", exists=True, file_okay=False)],
    tos_data_repo: Annotated[Path, typer.Option("--tos-data-repo", exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
) -> None:
    """Validate, monitor, and execute one VEC-07 request in this foreground process."""

    try:
        parsed = load_run_request(request)
        typer.echo("state: validating")
        preflight = preflight_vec_run(input_root, vec_repo, tos_data_repo, parsed)
        typer.echo(f"preflight: {preflight.status.value}")
        if preflight.status.value != "accepted":
            raise typer.Exit(code=1)
        typer.echo("state: running_foreground")
        receipt = run_vec_evaluator(
            input_root,
            vec_repo,
            tos_data_repo,
            output,
            parsed,
        )
        typer.echo(f"state: {receipt.status.value}")
        typer.echo(f"receipt: {output / 'execution_receipt.json'}")
        typer.echo(f"elapsed_seconds: {receipt.elapsed_seconds:.6f}")
        typer.echo(f"fingerprint: {receipt.fingerprint()}")
    except typer.Exit:
        raise
    except (OSError, VecInterfaceError, VecRunnerError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("execute-and-import")
def vec_execute_and_import_command(
    preset: Annotated[VecExecutionPreset, typer.Option("--preset")],
    input_root: Annotated[Path, typer.Option("--input-root", exists=True, file_okay=False)],
    vec_repo: Annotated[Path, typer.Option("--vec-repo", exists=True, file_okay=False)],
    tos_data_repo: Annotated[Path, typer.Option("--tos-data-repo", exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False)],
    confirm_full_run: Annotated[bool, typer.Option("--confirm-full-run")] = False,
) -> None:
    """Preflight, execute, validate, and import one closed preset in this foreground process."""

    try:
        workflow = VecWorkflowRequest(
            preset=preset,
            input_root=str(input_root),
            vec_repo=str(vec_repo),
            tos_data_repo=str(tos_data_repo),
            output_dir=str(output),
            registry_path=str(registry),
            confirm_full_run=confirm_full_run,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    workload = preset_workload(preset)
    typer.echo(f"preset: {preset.value}")
    typer.echo(f"evaluator_steps: {workload.evaluator_steps}")
    typer.echo(f"timeout_bound_seconds: {workload.timeout_seconds_bound}")
    typer.echo("state: validating")
    receipt = execute_and_import(workflow)
    for stage in receipt.stages:
        typer.echo(f"{stage.stage.value}: {stage.state.value} - {stage.detail}")
    typer.echo(f"workflow: {receipt.status.value}")
    if receipt.receipt_fingerprint is not None:
        typer.echo(f"receipt_fingerprint: {receipt.receipt_fingerprint}")
    if receipt.import_outcome is not None:
        outcome = receipt.import_outcome
        typer.echo(f"registry_run_id: {outcome.registry_run_id}")
        typer.echo(f"import_created: {outcome.created}")
        typer.echo(f"import_idempotent: {outcome.idempotent}")
        typer.echo(f"import_stable_fingerprint: {outcome.stable_fingerprint}")
    if receipt.status is not VecWorkflowStatus.COMPLETED_IMPORTED:
        for finding in receipt.findings:
            typer.echo(f"finding: {finding}", err=True)
        raise typer.Exit(code=1)


@vec_app.command("import-result")
def vec_import_result_command(
    result_dir: Annotated[Path, typer.Option("--result-dir", exists=True, file_okay=False)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False)],
    vec_repo: Annotated[
        Path | None,
        typer.Option("--vec-repo", exists=True, file_okay=False),
    ] = None,
    tos_data_repo: Annotated[
        Path | None,
        typer.Option("--tos-data-repo", exists=True, file_okay=False),
    ] = None,
) -> None:
    """Re-validate one published preset execution and import it idempotently."""

    try:
        record, outcome = import_vec_execution(
            result_dir,
            registry,
            vec_repo=vec_repo,
            tos_data_repo=tos_data_repo,
        )
    except (OSError, VecOrchestrationError, RegistryConflictError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"preset: {record.preset.value}")
    typer.echo(f"evidence_grade: {record.evidence_grade.value}")
    typer.echo(f"registry_run_id: {outcome.registry_run_id}")
    typer.echo(f"import_created: {outcome.created}")
    typer.echo(f"import_idempotent: {outcome.idempotent}")
    typer.echo(f"import_stable_fingerprint: {outcome.stable_fingerprint}")
    typer.echo(f"scientific_admission: {record.scientific_admission_status}")


@vec_app.command("monitor-current")
def vec_monitor_current_command() -> None:
    """Explain the deliberately process-local foreground monitoring boundary."""

    typer.echo("state: idle")
    typer.echo("monitor_scope: current_foreground_process_only")
    typer.echo("start a monitored operation with `integration vec preprocess` or `run`")
    typer.echo("persistent_async_queue: false")


@vec_app.command("inspect")
def vec_inspect_command(
    artifact: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
) -> None:
    """Inspect one strict portable VEC receipt or report."""

    try:
        typer.echo(inspect_vec_artifact(artifact).model_dump_json(indent=2))
    except VecInterfaceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("compare")
def vec_compare_command(
    baseline: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    variation: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Compare compatible scalar metrics from two accepted VEC-09 reports."""

    try:
        comparison = compare_vec_admissions(
            load_scientific_admission(baseline),
            load_scientific_admission(variation),
        )
        _vec_write_new(output, comparison.model_dump_json(indent=2) + "\n")
        typer.echo(f"comparison: {output}")
        typer.echo(f"comparable_metrics: {len(comparison.comparable_metrics)}")
        typer.echo(f"fingerprint: {comparison.fingerprint()}")
    except (OSError, VecInterfaceError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("export")
def vec_export_command(
    report: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path, typer.Option("--output", dir_okay=False)] = Path("vec-export.json"),
) -> None:
    """Export an accepted VEC-09 report without scientific recomputation."""

    try:
        if output_format not in {"json", "csv", "markdown"}:
            raise VecInterfaceError("--format must be json, csv, or markdown")
        payload = export_vec_admission(
            load_scientific_admission(report),
            output_format,  # type: ignore[arg-type]
        )
        _vec_write_new(output, payload)
        typer.echo(f"export: {output}")
        typer.echo(f"format: {output_format}")
    except (OSError, VecInterfaceError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("research-contract")
def vec_research_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the deterministic, permission-bounded VEC-12 archive contract."""

    contract = vec_end_to_end_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"capability: {contract.capability}")
    typer.echo(f"status: {contract.status}")
    typer.echo(f"artifact_version: {contract.artifact_version}")
    typer.echo(f"permitted_members: {len(contract.permitted_members)}")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@vec_app.command("research-create")
def vec_research_create_command(
    generated_root: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)] = Path(
        "vec_end_to_end_research_artifact.zip"
    ),
) -> None:
    """Create one new deterministic VEC-12 archive from accepted generated evidence."""

    try:
        receipt = create_vec_end_to_end_archive(generated_root, output)
        typer.echo(f"archive: {output}")
        typer.echo(f"artifact_id: {receipt.artifact_id}")
        typer.echo(f"archive_sha256: {receipt.archive_sha256}")
        typer.echo(f"member_count: {receipt.member_count}")
    except (OSError, VecEndToEndResearchError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@vec_app.command("research-verify")
def vec_research_verify_command(
    archive: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Verify one VEC-12 archive offline without extracting it."""

    result = verify_vec_end_to_end_archive(archive)
    if output_format == "json":
        typer.echo(result.model_dump_json(indent=2))
    else:
        _require_text_format(output_format)
        typer.echo(f"valid: {str(result.valid).lower()}")
        if result.valid:
            typer.echo(f"artifact_id: {result.artifact_id}")
            typer.echo(f"archive_sha256: {result.archive_sha256}")
            typer.echo(f"member_count: {result.member_count}")
        else:
            typer.echo("errors: " + "; ".join(result.errors))
    if not result.valid:
        raise typer.Exit(code=1)


def _vec_write_new(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise VecInterfaceError(f"refusing to overwrite VEC output: {path}") from exc


@app.command("validate-seed")
def validate_seed(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Validate a scenario seed YAML file."""

    try:
        seed = load_seed(path)
    except SeedIOError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"valid seed: {seed.seed_id}")


@app.command("normalise-seed")
def normalise_seed(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    destination: Annotated[Path, typer.Argument(dir_okay=False, writable=True)],
) -> None:
    """Validate and export a deterministic YAML representation."""

    try:
        document = normalise_seed_file(source, destination)
    except SeedIOError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"normalised seed: {document.seed.seed_id} -> {destination}")


@app.command("capabilities")
def capabilities() -> None:
    """Show the default export/import-only capability manifest."""

    manifest = default_export_import_manifest()
    typer.echo(yaml.safe_dump(manifest_to_plain_dict(manifest), sort_keys=False))


@archive_app.command("contract")
def archive_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the versioned OPS-04 archival method and safety contract."""

    contract = research_object_contract()
    if output_format == "json":
        payload = contract.model_dump(mode="json")
        payload["fingerprint"] = contract.fingerprint()
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    _require_text_format(output_format)
    typer.echo(f"capability: {contract.capability_id}")
    typer.echo(f"contract_version: {contract.contract_version}")
    typer.echo(f"contract_fingerprint: {contract.fingerprint()}")
    typer.echo(f"ro_crate: {contract.ro_crate_specification}")
    typer.echo(f"cff_version: {contract.cff_version}")
    typer.echo(f"source_boundary: {contract.source_boundary}")
    typer.echo("raw_evidence_modes: " + ", ".join(sorted(contract.raw_evidence_modes)))


@archive_app.command("create")
def archive_create_command(
    bundle: Annotated[Path, typer.Argument(exists=True, readable=True)],
    destination: Annotated[Path, typer.Argument(dir_okay=False)],
    publication_date: Annotated[
        str,
        typer.Option("--publication-date", help="Publication date in YYYY-MM-DD form."),
    ],
    title: Annotated[str | None, typer.Option("--title")] = None,
    description: Annotated[str | None, typer.Option("--description")] = None,
    publication_scope: Annotated[str, typer.Option("--publication-scope")] = "private",
    raw_evidence: Annotated[str, typer.Option("--raw-evidence")] = "reference",
    permission_status: Annotated[str, typer.Option("--permission-status")] = "unknown",
    permission_basis: Annotated[str | None, typer.Option("--permission-basis")] = None,
    licence_statement: Annotated[
        str,
        typer.Option("--licence-statement"),
    ] = (
        "TrafficTwin repository licence is not specified; this crate grants no additional "
        "reuse rights."
    ),
    raw_evidence_licence: Annotated[
        str | None,
        typer.Option("--raw-evidence-licence"),
    ] = None,
    persistent_identifier: Annotated[
        str | None,
        typer.Option("--persistent-identifier"),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Create a verified, deterministic attached RO-Crate ZIP from one accepted bundle."""

    if output_format not in {"text", "json"}:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    try:
        request = ResearchObjectRequest(
            publication_date=date.fromisoformat(publication_date),
            title=title,
            description=description,
            publication_scope=PublicationScope(publication_scope),
            raw_evidence=RawEvidenceDisposition(raw_evidence),
            permission_status=PermissionStatus(permission_status),
            permission_basis=permission_basis,
            licence_statement=licence_statement,
            raw_evidence_licence=raw_evidence_licence,
            persistent_identifier=persistent_identifier,
        )
        receipt = create_research_object_archive(
            bundle,
            destination,
            request,
            overwrite=overwrite,
        )
    except (OSError, ResearchObjectError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(receipt.model_dump_json(indent=2))
        return
    typer.echo(f"archive: {destination}")
    typer.echo(f"object_id: {receipt.object_id}")
    typer.echo(f"archive_sha256: {receipt.archive_sha256}")
    typer.echo(f"archive_size: {receipt.archive_size}")
    typer.echo(f"members: {receipt.member_count}")
    typer.echo(f"raw_evidence: {receipt.raw_evidence.value}")
    typer.echo("verified: true")


@archive_app.command("verify")
def archive_verify_command(
    archive: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Verify an OPS-04 archive offline without extraction or mutation."""

    if output_format not in {"text", "json"}:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    verification = verify_research_object(archive)
    if output_format == "json":
        typer.echo(verification.model_dump_json(indent=2))
    else:
        typer.echo(f"valid: {str(verification.valid).lower()}")
        typer.echo(f"archive_sha256: {verification.archive_sha256 or 'unavailable'}")
        typer.echo(f"object_id: {verification.object_id or 'unavailable'}")
        typer.echo(f"members: {verification.member_count}")
        typer.echo(f"checksums: {verification.checksum_count}")
        for error in verification.errors:
            typer.echo(f"error: {error}")
    if not verification.valid:
        raise typer.Exit(code=1)


@app.command("doctor")
def doctor_command(
    workspace: Annotated[Path | None, typer.Option("--workspace", file_okay=False)] = None,
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
    bundle: Annotated[Path | None, typer.Option("--bundle")] = None,
    cache_root: Annotated[Path | None, typer.Option("--cache-root", file_okay=False)] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
    show_contract: Annotated[bool, typer.Option("--contract")] = False,
) -> None:
    """Diagnose runtime and selected local targets without changing them."""

    if output_format not in {"text", "json"}:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    if show_contract:
        contract = doctor_contract()
        if output_format == "json":
            payload = contract.model_dump(mode="json")
            payload["fingerprint"] = contract.fingerprint()
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        else:
            typer.echo(doctor_contract_to_text(contract), nl=False)
        return
    report = run_doctor(
        workspace=workspace,
        registry=registry,
        bundle=bundle,
        cache_root=cache_root,
    )
    if output_format == "json":
        payload = report.model_dump(mode="json")
        payload["report_fingerprint"] = report.fingerprint()
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        typer.echo(doctor_report_to_text(report), nl=False)
    if report.overall_status is DoctorOverallStatus.BLOCKED:
        raise typer.Exit(code=1)


@registry_app.command("init")
def init_registry(
    path: Annotated[Path, typer.Argument(dir_okay=False, writable=True)],
) -> None:
    """Initialise a SQLite metadata registry."""

    registry = Registry(path)
    try:
        result = registry.initialize()
    except RegistryMigrationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"registry initialised: {path}")
    typer.echo(f"schema_version: {result.final_version}")
    typer.echo(
        "applied_migrations: "
        + (", ".join(str(item.version) for item in result.applied_migrations) or "none")
    )


@registry_app.command("inspect")
def inspect_registry(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Inspect a SQLite metadata registry."""

    try:
        summary = Registry(path).inspect()
    except RegistryMigrationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"registry: {summary.path}")
    typer.echo(f"schema_version: {summary.schema_version}")
    typer.echo(f"seeds: {summary.seed_count}")
    typer.echo(f"experiments: {summary.experiment_count}")
    typer.echo(f"runs: {summary.run_count}")
    typer.echo(f"bundle_imports: {summary.bundle_import_count}")
    typer.echo(f"metric_collections: {summary.metric_collection_count}")
    typer.echo(f"evidence_packs: {summary.evidence_pack_count}")
    typer.echo(f"experiment_evidence_packs: {summary.experiment_evidence_pack_count}")
    typer.echo(f"experiment_protocols: {summary.experiment_protocol_count}")
    typer.echo(f"protocol_slots: {summary.protocol_slot_count}")
    typer.echo(f"analyst_annotations: {summary.analyst_annotation_count}")


@registry_app.command("migration-contract")
def registry_migration_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the ordered transactional OPS-01 migration boundary."""

    contract = registry_migration_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"capability_id: {contract.capability_id}")
    typer.echo(f"contract_version: {contract.contract_version}")
    typer.echo(f"current_registry_schema_version: {contract.current_registry_schema_version}")
    for migration in contract.ordered_migrations:
        typer.echo(f"migration: {migration.version} {migration.name} checksum={migration.checksum}")
    typer.echo(f"transaction_policy: {contract.transaction_policy}")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@registry_app.command("migration-status")
def registry_migration_status_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect schema version and pending migrations without changing the registry."""

    if output_format not in {"text", "json"}:
        typer.echo("format must be text or json", err=True)
        raise typer.Exit(code=1)
    try:
        status = inspect_registry_migrations(path)
    except RegistryMigrationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(status.model_dump_json(indent=2))
        return
    typer.echo(f"registry: {path}")
    typer.echo(f"state: {status.state.value}")
    typer.echo(f"current_version: {status.current_version}")
    typer.echo(f"latest_version: {status.latest_version}")
    typer.echo(
        "applied_versions: "
        + (", ".join(str(version) for version in status.applied_versions) or "none")
    )
    typer.echo(
        "pending_versions: "
        + (", ".join(str(version) for version in status.pending_versions) or "none")
    )
    typer.echo(f"ledger_valid: {str(status.ledger_valid).lower()}")
    typer.echo(f"integrity_check: {status.integrity_check}")
    typer.echo(f"schema_fingerprint: {status.schema_fingerprint}")
    typer.echo(f"fingerprint: {status.fingerprint()}")


@registry_app.command("migrate")
def migrate_registry_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, writable=True)],
    target_version: Annotated[
        int,
        typer.Option("--target-version", min=1, max=CURRENT_REGISTRY_SCHEMA_VERSION),
    ] = CURRENT_REGISTRY_SCHEMA_VERSION,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Atomically migrate an existing supported registry to a target version."""

    if output_format not in {"text", "json"}:
        typer.echo("format must be text or json", err=True)
        raise typer.Exit(code=1)
    try:
        result = migrate_registry(path, target_version=target_version)
    except RegistryMigrationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(result.model_dump_json(indent=2))
        return
    typer.echo(f"registry: {path}")
    typer.echo(f"initial_version: {result.initial_version}")
    typer.echo(f"final_version: {result.final_version}")
    typer.echo(
        "applied_migrations: "
        + (", ".join(str(item.version) for item in result.applied_migrations) or "none")
    )
    typer.echo(f"already_at_target: {str(result.already_at_target).lower()}")
    typer.echo(f"legacy_schema_detected: {str(result.legacy_schema_detected).lower()}")
    typer.echo(f"integrity_check: {result.integrity_check}")
    typer.echo(f"schema_fingerprint: {result.schema_fingerprint}")
    typer.echo(f"fingerprint: {result.fingerprint()}")


@registry_app.command("search-contract")
def registry_search_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the deterministic read-only REP-05 search boundary."""

    contract = registry_search_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"capability_id: {contract.capability_id}")
    typer.echo(f"contract_version: {contract.contract_version}")
    typer.echo("categories: " + ", ".join(item.value for item in contract.categories))
    typer.echo(f"default_result_limit: {contract.default_result_limit}")
    typer.echo(f"maximum_result_limit: {contract.maximum_result_limit}")
    typer.echo(f"maximum_query_characters: {contract.maximum_query_characters}")
    typer.echo(f"maximum_query_tokens: {contract.maximum_query_tokens}")
    typer.echo(f"maximum_candidate_documents: {contract.maximum_candidate_documents}")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@registry_app.command("search")
def registry_search_command(
    query: Annotated[str, typer.Argument(help="Lexical AND query.")],
    registry: Annotated[
        Path,
        typer.Option("--registry", exists=True, dir_okay=False, readable=True),
    ],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", exists=True, file_okay=False, readable=True),
    ] = None,
    categories: Annotated[
        list[SearchCategory] | None,
        typer.Option("--category", help="Repeat to restrict result categories."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=MAX_SEARCH_LIMIT)] = 50,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Search local registry records and bounded report text without writing an index."""

    if output_format not in {"text", "json"}:
        typer.echo("format must be text or json", err=True)
        raise typer.Exit(code=1)
    try:
        result = search_registry(
            registry,
            query,
            workspace_path=workspace,
            categories=categories,
            limit=limit,
        )
    except (OSError, RegistrySearchError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(result.model_dump_json(indent=2))
        return
    typer.echo(f"query: {result.query}")
    typer.echo("terms: " + ", ".join(result.normalised_terms))
    typer.echo(f"candidates: {result.candidate_count}")
    typer.echo(f"matches: {result.matching_count}")
    typer.echo(f"returned: {result.returned_count}")
    typer.echo(f"omitted_matches: {result.omitted_match_count}")
    typer.echo(f"skipped_reports: {result.skipped_report_count}")
    typer.echo(f"redactions: {result.redaction_count}")
    typer.echo(f"fingerprint: {result.fingerprint()}")
    for hit in result.hits:
        typer.echo(
            f"{hit.rank}. [{hit.category.value}] {hit.title} "
            f"(score={hit.score}, reference={hit.reference})"
        )
        typer.echo(f"   {hit.snippet}")


@registry_app.command("annotation-contract")
def registry_annotation_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the append-only REP-02 analyst-annotation boundary."""

    contract = analyst_annotation_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"contract_version: {contract.contract_version}")
    typer.echo("target_kinds: " + ", ".join(item.value for item in contract.supported_target_kinds))
    typer.echo("decision_labels: " + ", ".join(item.value for item in contract.decision_labels))
    typer.echo(f"maximum_note_characters: {contract.maximum_note_characters}")
    typer.echo(f"maximum_page_records: {contract.maximum_page_records}")
    typer.echo(f"maximum_report_records: {contract.maximum_report_records}")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@registry_app.command("annotation-add")
def registry_annotation_add_command(
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False)],
    target_kind: Annotated[AnalystAnnotationTargetKind, typer.Option("--target-kind")],
    target_id: Annotated[str, typer.Option("--target-id")],
    author: Annotated[str, typer.Option("--author")],
    note: Annotated[str, typer.Option("--note")],
    decision_label: Annotated[
        AnalystDecisionLabel,
        typer.Option("--decision-label"),
    ] = AnalystDecisionLabel.OBSERVATION,
    target_fingerprint: Annotated[
        str | None,
        typer.Option("--target-fingerprint"),
    ] = None,
) -> None:
    """Append one analyst-authored note or decision to a typed artifact reference."""

    try:
        request = AnalystAnnotationRequest(
            target=AnalystArtifactReference(
                kind=target_kind,
                artifact_id=target_id,
                artifact_fingerprint=target_fingerprint,
            ),
            author_label=author,
            note=note,
            decision_label=decision_label,
        )
        annotation = Registry(registry).append_analyst_annotation(request)
    except (RegistryError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"annotation: {annotation.annotation_id}")
    typer.echo(f"sequence: {annotation.sequence}")
    typer.echo(f"target: {annotation.target.key}")
    typer.echo(f"decision_label: {annotation.decision_label.value}")
    typer.echo(f"created_at: {annotation.created_at.isoformat()}")


@registry_app.command("annotation-list")
def registry_annotation_list_command(
    registry: Annotated[
        Path,
        typer.Option("--registry", exists=True, dir_okay=False, readable=True),
    ],
    target_kind: Annotated[
        AnalystAnnotationTargetKind | None,
        typer.Option("--target-kind"),
    ] = None,
    target_id: Annotated[str | None, typer.Option("--target-id")] = None,
    target_fingerprint: Annotated[
        str | None,
        typer.Option("--target-fingerprint"),
    ] = None,
    after_sequence: Annotated[int, typer.Option("--after-sequence", min=0)] = 0,
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 100,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Read a bounded ordered page from the append-only annotation history."""

    try:
        if (target_kind is None) != (target_id is None):
            raise ValueError("--target-kind and --target-id must be provided together")
        if target_fingerprint is not None and target_kind is None:
            raise ValueError("--target-fingerprint requires a target kind and identifier")
        target = (
            AnalystArtifactReference(
                kind=target_kind,
                artifact_id=target_id,
                artifact_fingerprint=target_fingerprint,
            )
            if target_kind is not None and target_id is not None
            else None
        )
        page = Registry(registry).list_analyst_annotations(
            target=target,
            after_sequence=after_sequence,
            limit=limit,
        )
    except (RegistryError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(page.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"annotations: {len(page.annotations)}")
    typer.echo(f"has_more: {str(page.has_more).lower()}")
    typer.echo(f"history_fingerprint: {page.fingerprint()}")
    for annotation in page.annotations:
        typer.echo(
            f"{annotation.sequence}\t{annotation.annotation_id}\t"
            f"{annotation.target.key}\t{annotation.decision_label.value}\t"
            f"{annotation.author_label}\t{annotation.created_at.isoformat()}"
        )


@bundle_app.command("validate")
def validate_run_bundle(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Validate a directory or ZIP run bundle."""

    result = validate_bundle(path)
    report = result.report
    typer.echo(f"bundle: {report.bundle_id or 'unknown'}")
    typer.echo(f"run: {report.run_id or 'unknown'}")
    typer.echo(f"status: {report.status.value}")
    typer.echo(f"may_import: {report.may_import}")
    typer.echo(f"findings: {len(report.findings)}")
    if not report.may_import:
        raise typer.Exit(code=1)


@bundle_app.command("inspect")
def inspect_run_bundle(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Inspect a bundle without registry mutation."""

    result = inspect_bundle(path)
    report = result.report
    typer.echo(f"bundle: {report.bundle_id or 'unknown'}")
    typer.echo(f"run: {report.run_id or 'unknown'}")
    typer.echo(f"status: {report.status.value}")
    typer.echo(f"declared_files: {len(result.manifest.files) if result.manifest else 0}")
    typer.echo(f"available_evidence: {', '.join(report.available_evidence_categories) or 'none'}")
    typer.echo(
        f"unavailable_evidence: {', '.join(report.unavailable_evidence_categories) or 'none'}"
    )


@bundle_app.command("cache-contract")
def canonical_cache_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the content-addressed, fail-closed OPS-02 cache boundary."""

    contract = canonical_cache_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"capability_id: {contract.capability_id}")
    typer.echo(f"contract_version: {contract.contract_version}")
    typer.echo(f"adapter: {contract.adapter_id} {contract.adapter_version}")
    typer.echo(f"validator_version: {contract.validator_version}")
    typer.echo(f"cache_format: {contract.cache_format}")
    typer.echo("key_components: " + ", ".join(contract.key_components))
    typer.echo("canonical_tables: " + ", ".join(contract.canonical_tables))
    typer.echo(f"canonical_schema_fingerprint: {contract.canonical_schema_fingerprint}")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@bundle_app.command("cache-status")
def canonical_cache_status_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    cache_root: Annotated[Path, typer.Option("--cache-root", file_okay=False)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Re-fingerprint raw evidence and inspect its expected cache entry without writes."""

    try:
        status = inspect_bundle_cache(path, cache_root)
    except CanonicalCacheConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(status.model_dump_json(indent=2))
    else:
        _require_text_format(output_format)
        _emit_cache_status(status)
    if status.state in {
        CanonicalCacheState.STALE,
        CanonicalCacheState.INCOMPATIBLE,
        CanonicalCacheState.CORRUPT,
        CanonicalCacheState.UNAVAILABLE,
        CanonicalCacheState.WRITE_FAILED,
    }:
        raise typer.Exit(code=1)


@bundle_app.command("cache-validate")
def canonical_cache_validate_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    cache_root: Annotated[Path, typer.Option("--cache-root", file_okay=False)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Validate cold or reuse a fully verified canonical Parquet cache entry."""

    if output_format not in {"text", "json"}:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    try:
        result = validate_bundle_cached(path, cache_root)
    except CanonicalCacheConfigurationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    report = result.validation.report
    if output_format == "json":
        typer.echo(
            json.dumps(
                {
                    "validation": {
                        "bundle_id": report.bundle_id,
                        "run_id": report.run_id,
                        "fingerprint": result.validation.fingerprint,
                        "status": report.status.value,
                        "may_import": report.may_import,
                        "finding_count": len(report.findings),
                        "canonical_record_counts": report.canonical_record_counts,
                    },
                    "cache": result.cache.model_dump(mode="json"),
                },
                indent=2,
            )
        )
    else:
        _require_text_format(output_format)
        typer.echo(f"bundle: {report.bundle_id or 'unknown'}")
        typer.echo(f"run: {report.run_id or 'unknown'}")
        typer.echo(f"validation_status: {report.status.value}")
        typer.echo(f"may_import: {str(report.may_import).lower()}")
        _emit_cache_status(result.cache)
    if not report.may_import or result.cache.state not in {
        CanonicalCacheState.HIT,
        CanonicalCacheState.WRITTEN,
    }:
        raise typer.Exit(code=1)


@bundle_app.command("import")
def import_run_bundle_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False, writable=True)],
) -> None:
    """Validate and register an accepted bundle."""

    try:
        result = import_run_bundle(path, registry)
    except RegistryConflictError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"bundle: {result.bundle_id or 'unknown'}")
    typer.echo(f"run: {result.run_id or 'unknown'}")
    typer.echo(f"status: {result.status}")
    typer.echo(f"idempotent: {result.idempotent}")
    typer.echo(result.message)
    if result.status == "rejected":
        raise typer.Exit(code=1)


@bundle_app.command("batch-validate")
def validate_run_bundle_batch_command(
    inputs: Annotated[
        list[str],
        typer.Argument(help="One or more explicit bundle paths or quoted glob patterns."),
    ],
    output_format: Annotated[str, typer.Option("--format")] = "text",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Validate a deterministic bundle path/glob set without registry mutation."""

    summary = validate_bundle_batch(inputs)
    _emit_batch_summary(summary, output_format, output)
    if not summary.successful:
        raise typer.Exit(code=1)


@bundle_app.command("batch-import")
def import_run_bundle_batch_command(
    inputs: Annotated[
        list[str],
        typer.Argument(help="One or more explicit bundle paths or quoted glob patterns."),
    ],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False, writable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Validate and independently import a deterministic bundle path/glob set."""

    summary = import_bundle_batch(inputs, registry)
    _emit_batch_summary(summary, output_format, output)
    if not summary.successful:
        raise typer.Exit(code=1)


@bundle_app.command("stream-validate")
def validate_run_bundle_streaming_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    chunk_rows: Annotated[int, typer.Option("--chunk-rows")] = DEFAULT_STREAM_CHUNK_ROWS,
    max_chunk_bytes: Annotated[
        int, typer.Option("--max-chunk-bytes")
    ] = DEFAULT_STREAM_MAX_CHUNK_BYTES,
    max_table_bytes: Annotated[
        int, typer.Option("--max-table-bytes")
    ] = DEFAULT_STREAM_MAX_TABLE_BYTES,
    max_bundle_bytes: Annotated[
        int, typer.Option("--max-bundle-bytes")
    ] = DEFAULT_STREAM_MAX_BUNDLE_BYTES,
    output_format: Annotated[str, typer.Option("--format")] = "text",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Validate through bounded canonical chunks without retaining all records."""

    config = _streaming_config(
        chunk_rows,
        max_chunk_bytes,
        max_table_bytes,
        max_bundle_bytes,
    )
    result = validate_bundle_streaming(path, config=config)
    _emit_streaming_validation(result, output_format, output)
    if not result.report.may_import:
        raise typer.Exit(code=1)


@bundle_app.command("stream-import")
def import_run_bundle_streaming_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False, writable=True)],
    chunk_rows: Annotated[int, typer.Option("--chunk-rows")] = DEFAULT_STREAM_CHUNK_ROWS,
    max_chunk_bytes: Annotated[
        int, typer.Option("--max-chunk-bytes")
    ] = DEFAULT_STREAM_MAX_CHUNK_BYTES,
    max_table_bytes: Annotated[
        int, typer.Option("--max-table-bytes")
    ] = DEFAULT_STREAM_MAX_TABLE_BYTES,
    max_bundle_bytes: Annotated[
        int, typer.Option("--max-bundle-bytes")
    ] = DEFAULT_STREAM_MAX_BUNDLE_BYTES,
    output_format: Annotated[str, typer.Option("--format")] = "text",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Stream-validate and register metadata through ordinary import semantics."""

    config = _streaming_config(
        chunk_rows,
        max_chunk_bytes,
        max_table_bytes,
        max_bundle_bytes,
    )
    try:
        result = import_bundle_streaming(path, registry, config=config)
    except RegistryConflictError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = json.dumps(
            {
                "validation": result.validation.model_dump(mode="json"),
                "registry": {
                    "bundle_id": result.registry.bundle_id,
                    "run_id": result.registry.run_id,
                    "created": result.registry.created,
                    "idempotent": result.registry.idempotent,
                    "status": result.registry.status,
                    "message": result.registry.message,
                },
            },
            indent=2,
        )
    elif output_format == "text":
        payload = _streaming_validation_to_text(result.validation) + (
            f"registry_created: {result.registry.created}\n"
            f"registry_idempotent: {result.registry.idempotent}\n"
            f"registry_message: {result.registry.message}\n"
        )
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="streaming import summary written")
    if not result.validation.report.may_import:
        raise typer.Exit(code=1)


@bundle_app.command("report")
def report_run_bundle(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Write a machine-readable validation report."""

    if output_format != "json":
        typer.echo("only --format json is supported", err=True)
        raise typer.Exit(code=1)
    result = validate_bundle(path)
    typer.echo(result.report.to_json())


@metrics_app.command("compute")
def compute_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Compute deterministic metrics for a validated bundle."""

    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    typer.echo(f"run: {collection.run_id}")
    typer.echo(f"metric_version: {collection.metric_version}")
    typer.echo(f"metrics: {len(collection.results)}")
    typer.echo(f"unavailable: {collection.unavailable_count}")
    key_values = collection.by_key()
    for key in (
        "task.completion.rate",
        "task.energy.mean_per_observed_task_j",
        "task.energy.per_completed_j",
        "task.energy_delay_product.mean_j_ms",
        "fairness.vehicle_tier.completion_rate.max_gap",
        "fairness.vehicle_tier.completion_rate.jain",
        "fairness.rsu.capacity_normalised_load.max_gap",
        "infra.load_balance.jain_capacity_normalised",
        "spatial.rsu.task.count_by_target",
        "spatial.rsu.task.completion_rate_by_target",
        "spatial.rsu.task.deadline_miss.completed_observed_rate_by_target",
        "spatial.vehicle.observation_count_by_grid_cell",
        "spatial.vehicle.distinct_count_by_grid_cell",
        "spatial.vehicle.speed.mean_mps_by_grid_cell",
        "infra.utilisation.mean",
        "traffic.speed.mean_mps",
        "trip.duration.mean_s",
    ):
        metric = key_values.get(key)
        if metric is None:
            continue
        value = metric.value if metric.status is MetricStatus.AVAILABLE else "unavailable"
        typer.echo(f"{key}: {value}")
    if not result.report.may_import:
        raise typer.Exit(code=1)


@metrics_app.command("plugin-api")
def metric_plugin_api_command(
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Describe the trusted local custom-metric registration boundary."""

    contract = metric_plugin_api_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
    elif output_format == "text":
        typer.echo(f"schema_version: {contract.schema_version}")
        typer.echo(f"registration_mode: {contract.registration_mode}")
        typer.echo(f"determinism_verification_runs: {contract.determinism_verification_runs}")
        typer.echo(f"execution_failure_policy: {contract.execution_failure_policy}")
        typer.echo(f"supported_tables: {', '.join(contract.supported_tables)}")
        typer.echo("dynamic_file_import: false")
        typer.echo("uploaded_code_execution: false")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)


@metrics_app.command("report")
def report_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
) -> None:
    """Emit complete machine-readable metric JSON for a bundle."""

    if output_format != "json":
        typer.echo("only --format json is supported", err=True)
        raise typer.Exit(code=1)
    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    if registry is not None and result.manifest is not None:
        Registry(registry).store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    typer.echo(collection.model_dump_json(indent=2))
    if not result.report.may_import:
        raise typer.Exit(code=1)


@metrics_app.command("windows")
def compute_windowed_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    width_s: Annotated[float, typer.Option("--width-s", min=0.000001)],
    alignment_origin_s: Annotated[float, typer.Option("--origin-s")] = 0.0,
    analysis_start_s: Annotated[float | None, typer.Option("--start-s")] = None,
    analysis_end_s: Annotated[float | None, typer.Option("--end-s")] = None,
    partial_windows: Annotated[str, typer.Option("--partial-windows")] = "include",
    max_windows: Annotated[int, typer.Option("--max-windows", min=1)] = 10_000,
    output_format: Annotated[str, typer.Option("--format")] = "text",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Compute declared metrics over aligned half-open fixed windows."""

    config = _windowed_metric_config(
        width_s,
        alignment_origin_s,
        analysis_start_s,
        analysis_end_s,
        partial_windows,
        max_windows,
    )
    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    try:
        series = compute_windowed_metrics_for_bundle(result, config)
    except WindowLimitExceededError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = series.to_json()
    elif output_format == "text":
        payload = _windowed_metric_series_to_text(series)
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="windowed metric series written")
    if not result.report.may_import:
        raise typer.Exit(code=1)


@app.command("compare")
def compare_command(
    baseline: Annotated[str, typer.Argument()],
    variation: Annotated[str, typer.Argument()],
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Compare two bundles or two registered metric collections."""

    baseline_collection, baseline_seed = _collection_from_identifier(baseline, registry)
    variation_collection, variation_seed = _collection_from_identifier(variation, registry)
    report = compare_metric_collections(
        baseline_collection,
        variation_collection,
        baseline_seed=baseline_seed,
        variation_seed=variation_seed,
    )
    if output_format == "json":
        typer.echo(report.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"baseline: {baseline_collection.run_id}")
    typer.echo(f"variation: {variation_collection.run_id}")
    for metric in report.comparable_metrics:
        if metric.metric_key in {
            "task.completion.rate",
            "infra.queue_length.mean",
            "traffic.speed.mean_mps",
            "trip.duration.mean_s",
        }:
            typer.echo(
                f"{metric.metric_key}: delta={metric.absolute_delta} "
                f"relative={metric.relative_delta} direction={metric.direction.value}"
            )
    typer.echo(f"unavailable_comparisons: {len(report.unavailable_comparisons)}")


@evidence_app.command("build")
def build_evidence_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
) -> None:
    """Build a versioned evidence-pack JSON document."""

    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    pack = build_evidence_pack(result, collection)
    payload = pack.to_json()
    if output is not None:
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"evidence_pack: {output}")
    else:
        typer.echo(payload)
    if registry is not None:
        Registry(registry).store_evidence_pack(
            pack_id=pack.pack_id,
            run_id=collection.run_id,
            source_fingerprint=collection.input_fingerprint,
            payload_json=payload,
        )
    if not result.report.may_import:
        raise typer.Exit(code=1)


@experiment_app.command("summarise")
def summarise_experiment_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Summarise stored metric collections for one experiment."""

    collections = [
        collection
        for payload in Registry(registry).list_metric_collection_json()
        if (collection := MetricCollection.model_validate_json(payload)).results
        and collection.results[0].experiment_id == experiment_id
    ]
    report = aggregate_experiment(collections)
    if output_format == "json":
        typer.echo(report.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"experiment: {experiment_id}")
    typer.echo(f"conditions: {report.condition_count}")
    for condition in report.conditions:
        typer.echo(f"{condition.condition_id}: runs={condition.run_count}")


@experiment_app.command("study-contract")
def experiment_study_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Publish the bounded STA-01 paired statistical method contract."""

    contract = statistical_study_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"method_version: {contract.method_version}")
    typer.echo(f"pairing_key: {contract.pairing_key}")
    typer.echo(f"estimand: {contract.estimand}")
    typer.echo(f"bootstrap_method: {contract.bootstrap_method}")
    typer.echo(f"randomisation_method: {contract.randomisation_method}")
    typer.echo(f"minimum_pairs: {contract.minimum_pairs}")


@experiment_app.command("equivalence-contract")
def experiment_equivalence_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Publish the bounded STA-03 paired TOST method contract."""

    contract = equivalence_testing_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"method_version: {contract.method_version}")
    typer.echo(f"pairing_contract: {contract.pairing_contract}")
    typer.echo(f"estimand: {contract.estimand}")
    typer.echo(f"method: {contract.method}")
    typer.echo(f"minimum_pairs: {contract.minimum_pairs}")
    typer.echo(f"decision_rule: {contract.decision_rule}")


@experiment_app.command("regression-contract")
def experiment_regression_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Publish the bounded STA-04 regression-gate method contract."""

    contract = regression_gate_method_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"method_version: {contract.method_version}")
    typer.echo(f"tolerance_method: {contract.tolerance_method}")
    typer.echo(f"tolerance_formula: {contract.tolerance_formula}")
    typer.echo(f"subject_kinds: {', '.join(item.value for item in contract.subject_kinds)}")
    typer.echo(
        "ci_exit_codes: "
        + ", ".join(f"{status}={code}" for status, code in contract.ci_exit_codes.items())
    )


@experiment_app.command("power-contract")
def experiment_power_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Publish the bounded STA-05 paired power-planning method contract."""

    contract = power_analysis_method_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"method_version: {contract.method_version}")
    typer.echo(f"pairing_key: {contract.pairing_key}")
    typer.echo(f"estimand: {contract.estimand}")
    typer.echo(f"method: {contract.method}")
    typer.echo(f"alternative: {contract.alternative}")
    typer.echo(f"minimum_replicates: {contract.replicate_bounds['minimum']}")
    typer.echo(f"maximum_replicates: {contract.replicate_bounds['maximum']}")


@experiment_app.command("n-way-contract")
def experiment_n_way_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Publish the bounded STA-02 N-way ranking method contract."""

    contract = n_way_ranking_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"method_version: {contract.method_version}")
    typer.echo(f"comparison_scope: {contract.comparison_scope}")
    typer.echo(f"pairing_key: {contract.pairing_key}")
    typer.echo(f"estimand: {contract.estimand}")
    typer.echo(f"bootstrap_method: {contract.bootstrap_method}")
    typer.echo(f"minimum_complete_seeds: {contract.minimum_complete_seeds}")


@experiment_app.command("statistical-study")
def experiment_statistical_study_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    baseline_seed_id: Annotated[str, typer.Option("--baseline-seed")],
    variation_seed_id: Annotated[str, typer.Option("--variation-seed")],
    algorithm: Annotated[str, typer.Option("--algorithm")],
    checkpoint: Annotated[str | None, typer.Option("--checkpoint")] = None,
    metric_key: Annotated[str, typer.Option("--metric")] = "task.completion.rate",
    objective: Annotated[ObjectiveDirection, typer.Option("--objective")] = (
        ObjectiveDirection.MAXIMISE
    ),
    confidence_level: Annotated[float, typer.Option("--confidence-level")] = 0.95,
    bootstrap_repetitions: Annotated[int, typer.Option("--bootstrap-repetitions")] = 10_000,
    randomisation_repetitions: Annotated[int, typer.Option("--randomisation-repetitions")] = 10_000,
    resampling_seed: Annotated[int, typer.Option("--resampling-seed")] = 20_260_720,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate one predeclared common-seed paired statistical study."""

    try:
        registered = Registry(registry).get_experiment(experiment_id)
        _validate_statistical_study_selection(
            registered,
            baseline_seed_id,
            variation_seed_id,
            algorithm,
        )
        config = PairedStudyConfig(
            experiment_id=experiment_id,
            baseline_seed_id=baseline_seed_id,
            variation_seed_id=variation_seed_id,
            algorithm=algorithm,
            checkpoint=checkpoint,
            metric_key=metric_key,
            objective=objective,
            confidence_level=confidence_level,
            bootstrap_repetitions=bootstrap_repetitions,
            randomisation_repetitions=randomisation_repetitions,
            resampling_seed=resampling_seed,
            expected_random_seeds=registered.common_random_seed_set,
        )
        study = evaluate_paired_statistical_study(
            _experiment_collections(registry, experiment_id),
            config,
        )
    except (RegistryNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = study.to_json()
    elif output_format == "markdown":
        payload = statistical_study_to_markdown(study)
    elif output_format == "csv":
        payload = statistical_study_pairs_to_csv(study)
    else:
        typer.echo("only --format json, markdown, or csv is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label=f"statistical study: {study.study_id}")
    if study.status is not StatisticalStudyStatus.AVAILABLE:
        raise typer.Exit(code=1)


@experiment_app.command("n-way-ranking")
def experiment_n_way_ranking_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    algorithms: Annotated[list[str] | None, typer.Option("--algorithm")] = None,
    checkpoint: Annotated[str | None, typer.Option("--checkpoint")] = None,
    metric_key: Annotated[str, typer.Option("--metric")] = "task.completion.rate",
    objective: Annotated[ObjectiveDirection, typer.Option("--objective")] = (
        ObjectiveDirection.MAXIMISE
    ),
    confidence_level: Annotated[float, typer.Option("--confidence-level")] = 0.95,
    bootstrap_repetitions: Annotated[int, typer.Option("--bootstrap-repetitions")] = 10_000,
    resampling_seed: Annotated[int, typer.Option("--resampling-seed")] = 20_260_720,
    tie_tolerance: Annotated[float, typer.Option("--tie-tolerance")] = 1e-12,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Rank compatible policies within each scenario family over common seeds."""

    try:
        registry_store = Registry(registry)
        registered = registry_store.get_experiment(experiment_id)
        selected_algorithms = algorithms or registered.algorithms
        unplanned = sorted(set(selected_algorithms) - set(registered.algorithms))
        if unplanned:
            raise ValueError("unregistered policies: " + ", ".join(unplanned))
        seed_ids = [registered.baseline_seed_id, *registered.variation_seed_ids]
        config = NWayRankingConfig(
            experiment_id=experiment_id,
            seed_ids=seed_ids,
            algorithms=selected_algorithms,
            checkpoint=checkpoint,
            metric_key=metric_key,
            objective=objective,
            confidence_level=confidence_level,
            bootstrap_repetitions=bootstrap_repetitions,
            resampling_seed=resampling_seed,
            tie_tolerance=tie_tolerance,
            expected_random_seeds=registered.common_random_seed_set,
        )
        aliases = {
            seed.seed_id: seed.parent_seed_id or seed.seed_id
            for seed in registry_store.list_seeds()
        }
        study = evaluate_n_way_ranking(
            _experiment_collections(registry, experiment_id),
            config,
            seed_aliases=aliases,
        )
    except (RegistryNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = study.to_json()
    elif output_format == "markdown":
        payload = n_way_ranking_to_markdown(study)
    elif output_format == "csv":
        payload = n_way_ranking_to_csv(study)
    else:
        typer.echo("only --format json, markdown, or csv is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label=f"N-way ranking: {study.study_id}")
    if study.status not in {NWayRankingStatus.AVAILABLE, NWayRankingStatus.PARTIAL}:
        raise typer.Exit(code=1)


@experiment_app.command("equivalence-study")
def experiment_equivalence_study_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    baseline_seed_id: Annotated[str, typer.Option("--baseline-seed")],
    variation_seed_id: Annotated[str, typer.Option("--variation-seed")],
    algorithm: Annotated[str, typer.Option("--algorithm")],
    equivalence_margin: Annotated[float, typer.Option("--equivalence-margin")],
    margin_basis: Annotated[EquivalenceMarginBasis, typer.Option("--margin-basis")],
    margin_justification: Annotated[str, typer.Option("--margin-justification")],
    checkpoint: Annotated[str | None, typer.Option("--checkpoint")] = None,
    metric_key: Annotated[str, typer.Option("--metric")] = "task.completion.rate",
    objective: Annotated[ObjectiveDirection, typer.Option("--objective")] = (
        ObjectiveDirection.MAXIMISE
    ),
    margin_reference: Annotated[str | None, typer.Option("--margin-reference")] = None,
    alpha: Annotated[float, typer.Option("--alpha")] = 0.05,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate one predeclared common-seed paired TOST equivalence study."""

    try:
        registered = Registry(registry).get_experiment(experiment_id)
        _validate_statistical_study_selection(
            registered,
            baseline_seed_id,
            variation_seed_id,
            algorithm,
        )
        config = EquivalenceStudyConfig(
            experiment_id=experiment_id,
            baseline_seed_id=baseline_seed_id,
            variation_seed_id=variation_seed_id,
            algorithm=algorithm,
            checkpoint=checkpoint,
            metric_key=metric_key,
            objective=objective,
            equivalence_margin=equivalence_margin,
            margin_basis=margin_basis,
            margin_justification=margin_justification,
            margin_reference=margin_reference,
            alpha=alpha,
            expected_random_seeds=registered.common_random_seed_set,
        )
        study = evaluate_equivalence_study(
            _experiment_collections(registry, experiment_id),
            config,
        )
    except (RegistryNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = study.to_json()
    elif output_format == "markdown":
        payload = equivalence_study_to_markdown(study)
    elif output_format == "csv":
        payload = equivalence_study_to_csv(study)
    else:
        typer.echo("only --format json, markdown, or csv is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label=f"equivalence study: {study.study_id}")
    if study.status is not EquivalenceStudyStatus.AVAILABLE:
        raise typer.Exit(code=1)


@experiment_app.command("power-analysis")
def experiment_power_analysis_command(
    metric_key: Annotated[str, typer.Option("--metric")],
    unit: Annotated[str, typer.Option("--unit")],
    target_effect: Annotated[float, typer.Option("--target-effect")],
    paired_difference_variance: Annotated[float, typer.Option("--paired-difference-variance")],
    target_effect_basis: Annotated[TargetEffectBasis, typer.Option("--effect-basis")],
    target_effect_justification: Annotated[str, typer.Option("--effect-justification")],
    variance_basis: Annotated[PairedVarianceBasis, typer.Option("--variance-basis")],
    variance_justification: Annotated[str, typer.Option("--variance-justification")],
    target_effect_reference: Annotated[str | None, typer.Option("--effect-reference")] = None,
    variance_reference: Annotated[str | None, typer.Option("--variance-reference")] = None,
    pilot_sample_size: Annotated[int | None, typer.Option("--pilot-sample-size")] = None,
    synthetic: Annotated[bool, typer.Option("--synthetic")] = False,
    alpha: Annotated[float, typer.Option("--alpha")] = 0.05,
    target_power: Annotated[float, typer.Option("--target-power")] = 0.80,
    maximum_replicates: Annotated[int, typer.Option("--maximum-replicates")] = 100_000,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Estimate required common-seed pairs under a declared planning model."""

    try:
        config = PowerAnalysisConfig(
            metric_key=metric_key,
            unit=unit,
            target_effect=target_effect,
            paired_difference_variance=paired_difference_variance,
            alpha=alpha,
            target_power=target_power,
            target_effect_basis=target_effect_basis,
            target_effect_justification=target_effect_justification,
            target_effect_reference=target_effect_reference,
            variance_basis=variance_basis,
            variance_justification=variance_justification,
            variance_reference=variance_reference,
            pilot_sample_size=pilot_sample_size,
            synthetic=synthetic,
            maximum_replicates=maximum_replicates,
        )
        analysis = evaluate_power_analysis(config)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    if output_format == "json":
        payload = analysis.to_json()
    elif output_format == "markdown":
        payload = power_analysis_to_markdown(analysis)
    elif output_format == "csv":
        payload = power_analysis_to_csv(analysis)
    else:
        typer.echo("only --format json, markdown, or csv is supported", err=True)
        raise typer.Exit(code=2)
    _emit_or_write_json(payload, output, label=f"power analysis: {analysis.analysis_id}")
    if analysis.status is PowerAnalysisStatus.UNAVAILABLE:
        raise typer.Exit(code=2)


@experiment_app.command("regression-golden")
def experiment_regression_golden_command(
    subject: Annotated[str, typer.Argument()],
    contract_id: Annotated[str, typer.Option("--contract-id")],
    contract_version: Annotated[str, typer.Option("--contract-version")],
    tolerances: Annotated[
        list[str] | None,
        typer.Option(
            "--tolerance",
            help="Repeat SELECTOR=ABSOLUTE,RELATIVE for every asserted scalar.",
        ),
    ] = None,
    subject_kind: Annotated[RegressionSubjectKind, typer.Option("--subject-kind")] = (
        RegressionSubjectKind.METRIC_COLLECTION
    ),
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
    description: Annotated[str, typer.Option("--description")] = (
        "TrafficTwin versioned regression golden contract"
    ),
    source_identity_policy: Annotated[
        SourceIdentityPolicy, typer.Option("--source-identity-policy")
    ] = SourceIdentityPolicy.EXACT,
    approval_status: Annotated[GoldenApprovalStatus, typer.Option("--approval-status")] = (
        GoldenApprovalStatus.CANDIDATE
    ),
    approved_by: Annotated[str | None, typer.Option("--approved-by")] = None,
    approval_note: Annotated[str | None, typer.Option("--approval-note")] = None,
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Generate a reviewable golden contract from one completed typed artifact."""

    try:
        loaded = _load_regression_subject(subject, subject_kind, registry)
        specs = [_parse_regression_tolerance(value) for value in tolerances or []]
        contract = build_regression_golden_contract(
            loaded,
            contract_id=contract_id,
            contract_version=contract_version,
            description=description,
            tolerances=specs,
            source_identity_policy=source_identity_policy,
            approval_status=approval_status,
            approved_by=approved_by,
            approval_note=approval_note,
        )
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_or_write_json(
        contract.to_json(),
        output,
        label=f"regression golden: {contract.contract_id} {contract.contract_version}",
    )


@experiment_app.command("regression-gate")
def experiment_regression_gate_command(
    subject: Annotated[str, typer.Argument()],
    golden: Annotated[Path, typer.Option("--golden", exists=True, dir_okay=False, readable=True)],
    registry: Annotated[Path | None, typer.Option("--registry", dir_okay=False)] = None,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate one CI-ready pass/fail/unavailable regression gate."""

    try:
        contract = parse_regression_golden_contract_json(golden.read_bytes())
        loaded = _load_regression_subject(subject, contract.subject_kind, registry)
        report = evaluate_regression_gate(loaded, contract)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    if output_format == "json":
        payload = report.to_json()
    elif output_format == "markdown":
        payload = regression_gate_to_markdown(report)
    elif output_format == "csv":
        payload = regression_gate_to_csv(report)
    else:
        typer.echo("only --format json, markdown, or csv is supported", err=True)
        raise typer.Exit(code=2)
    _emit_or_write_json(payload, output, label=f"regression gate: {report.gate_id}")
    if report.status is RegressionGateStatus.FAILED:
        raise typer.Exit(code=1)
    if report.status is RegressionGateStatus.UNAVAILABLE:
        raise typer.Exit(code=2)


@experiment_app.command("protocol")
def export_experiment_protocol_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    output_format: Annotated[str, typer.Option("--format")] = "yaml",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Export a registered experiment as a deterministic YAML or CSV protocol."""

    try:
        protocol = _registered_experiment_protocol(registry, experiment_id)
    except (RegistryNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "yaml":
        payload = protocol_to_yaml(protocol)
    elif output_format == "csv":
        payload = protocol_to_csv(protocol)
    else:
        typer.echo("only --format yaml or --format csv is supported", err=True)
        raise typer.Exit(code=1)
    if output is None:
        typer.echo(payload, nl=False)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    typer.echo(f"protocol: {protocol.protocol_id}")
    typer.echo(f"run_slots: {len(protocol.slots)}")


@experiment_app.command("parameter-sweep-contract")
def parameter_sweep_contract_command(
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Print the bounded EXP-01 method and safety contract."""

    payload = parameter_sweep_contract().model_dump_json(indent=2) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"contract: {output}")
    else:
        typer.echo(payload, nl=False)


@experiment_app.command("parameter-sweep")
def parameter_sweep_command(
    request_path: Annotated[
        Path,
        typer.Option("--request", exists=True, readable=True, dir_okay=False),
    ],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Expand a bounded sweep and materialise only its declared safe mode."""

    try:
        request = load_parameter_sweep_request(request_path)
        result = execute_parameter_sweep(request, output, overwrite=overwrite)
    except (FileExistsError, OSError, ParameterSweepError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"sweep: {result.sweep_id}")
    typer.echo(f"mode: {result.mode.value}")
    typer.echo(f"status: {result.status}")
    typer.echo(f"points: {result.point_count}")
    typer.echo(f"response_rows: {result.response_row_count}")
    typer.echo(f"synthetic_evaluation: {str(result.synthetic_evaluation).lower()}")
    typer.echo(f"direct_launch_supported: {str(result.direct_launch_supported).lower()}")
    typer.echo(f"result: {output / 'sweep_result.json'}")
    typer.echo(f"response_surface: {output / 'response_surface.csv'}")
    typer.echo(f"output: {output}")


@experiment_app.command("mutation-contract")
def scenario_mutation_contract_command(
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Print the bounded EXP-02 method and safety contract."""

    payload = scenario_mutation_contract().model_dump_json(indent=2) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"contract: {output}")
    else:
        typer.echo(payload, nl=False)


@experiment_app.command("mutate-scenario")
def scenario_mutation_command(
    bundle: Annotated[Path, typer.Option("--bundle", exists=True, readable=True)],
    request_path: Annotated[
        Path,
        typer.Option("--request", exists=True, readable=True, dir_okay=False),
    ],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Create one validated copied mutation of a synthetic/evaluation bundle."""

    try:
        request = load_scenario_mutation_request(request_path)
        result = execute_scenario_mutation(bundle, request, output, overwrite=overwrite)
    except (FileExistsError, OSError, ScenarioMutationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"mutation: {result.mutation_id}")
    typer.echo(f"operator: {result.mutation.operator.value}")
    typer.echo(f"status: {result.status}")
    typer.echo(f"changed_rows: {result.changed_row_count}")
    typer.echo(f"validation_status: {result.validation_status}")
    typer.echo(f"synthetic_evaluation: {str(result.synthetic_evaluation).lower()}")
    typer.echo(f"raw_source_mutated: {str(result.raw_source_mutated).lower()}")
    typer.echo(f"direct_launch_supported: {str(result.direct_launch_supported).lower()}")
    typer.echo(f"bundle: {output / 'bundle'}")
    typer.echo(f"manifest: {output / 'mutation_manifest.json'}")
    typer.echo(f"output: {output}")


@experiment_app.command("match-bundle")
def match_experiment_bundle_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Validate and match a completed bundle to a registered protocol slot."""

    try:
        protocol = _registered_experiment_protocol(registry, experiment_id)
    except (RegistryNotFoundError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    validation = validate_bundle(path)
    if validation.manifest is None or not validation.report.may_import:
        typer.echo("bundle rejected; protocol matching was not performed", err=True)
        for validation_finding in validation.report.findings:
            typer.echo(f"{validation_finding.code.value}: {validation_finding.message}", err=True)
        raise typer.Exit(code=1)
    match = match_bundle_manifest(protocol, validation.manifest)
    if output_format == "json":
        typer.echo(match.to_json())
    elif output_format == "text":
        typer.echo(f"protocol: {match.protocol_id}")
        typer.echo(f"bundle: {match.bundle_id}")
        typer.echo(f"run: {match.run_id}")
        typer.echo(f"status: {match.status.value}")
        typer.echo(f"slot: {match.matched_slot_id or 'none'}")
        for match_finding in match.findings:
            typer.echo(f"finding: {match_finding}")
        for mismatch in match.mismatches:
            typer.echo(
                f"mismatch: {mismatch.field} expected={mismatch.expected!r} "
                f"observed={mismatch.observed!r}"
            )
    else:
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    if match.status not in {ProtocolMatchStatus.EXACT, ProtocolMatchStatus.COMPATIBLE}:
        raise typer.Exit(code=1)


def _registered_experiment_protocol(
    registry_path: Path,
    experiment_id: str,
) -> ExperimentProtocol:
    registry = Registry(registry_path)
    experiment = registry.get_experiment(experiment_id)
    seeds = {seed.seed_id: seed for seed in registry.list_seeds()}
    return build_experiment_protocol(experiment, seeds)


@experiment_app.command("evidence")
def experiment_evidence_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    metric_key: Annotated[str, typer.Option("--metric")] = "task.completion.rate",
    objective: Annotated[ObjectiveDirection, typer.Option("--objective")] = (
        ObjectiveDirection.MAXIMISE
    ),
    training_run: Annotated[list[str] | None, typer.Option("--training-run")] = None,
    validation_run: Annotated[list[str] | None, typer.Option("--validation-run")] = None,
    store: Annotated[bool, typer.Option("--store/--no-store")] = False,
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Build a reusable experiment-level EvidencePack from stored metrics."""

    collections = _experiment_collections(registry, experiment_id)
    if not collections:
        typer.echo(f"no stored metric collections for experiment: {experiment_id}", err=True)
        raise typer.Exit(code=1)
    training_ids = training_run or []
    validation_ids = validation_run or []
    pairs: list[TrainingValidationObservation] = []
    if len(training_ids) != len(validation_ids):
        typer.echo(
            "repeat --training-run and --validation-run the same number of times",
            err=True,
        )
        raise typer.Exit(code=1)
    if len(set(training_ids)) != len(training_ids) or len(set(validation_ids)) != len(
        validation_ids
    ):
        typer.echo("training and validation run IDs must not be duplicated", err=True)
        raise typer.Exit(code=1)
    for training_run_id, validation_run_id in zip(training_ids, validation_ids, strict=True):
        try:
            training = MetricCollection.model_validate_json(
                Registry(registry).get_metric_collection_json(training_run_id)
            )
            validation = MetricCollection.model_validate_json(
                Registry(registry).get_metric_collection_json(validation_run_id)
            )
            pairs.append(
                training_validation_observation_from_collections(
                    training,
                    validation,
                    metric_key,
                )
            )
        except (RegistryNotFoundError, ValueError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    try:
        pack = build_experiment_evidence_pack(
            collections,
            ExperimentEvidenceOptions(
                experiment_id=experiment_id,
                primary_metric_key=metric_key,
                objective=objective,
            ),
            training_validation=pairs,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if store:
        Registry(registry).store_experiment_evidence_pack(
            pack_id=pack.pack_id,
            experiment_id=experiment_id,
            source_fingerprint=pack.source_bundle_fingerprint,
            payload_json=pack.to_json(),
        )
    _emit_or_write_json(pack.to_json(), output, label=f"evidence: {pack.pack_id}")


@experiment_app.command("winner-map")
def experiment_winner_map_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    metric_key: Annotated[str, typer.Option("--metric")] = "task.completion.rate",
    objective: Annotated[ObjectiveDirection, typer.Option("--objective")] = (
        ObjectiveDirection.MAXIMISE
    ),
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Build a descriptive per-seed policy winner map."""

    collections = _experiment_collections(registry, experiment_id)
    registry_store = Registry(registry)
    aliases = {
        seed.seed_id: seed.parent_seed_id or seed.seed_id for seed in registry_store.list_seeds()
    }
    report = build_winner_map(
        collections,
        metric_key=metric_key,
        objective=objective,
        seed_aliases=aliases,
    )
    _emit_or_write_json(report.to_json(), output, label="winner map written")


@experiment_app.command("portfolio")
def experiment_portfolio_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    metric_key: Annotated[str, typer.Option("--metric")] = "task.completion.rate",
    objective: Annotated[ObjectiveDirection, typer.Option("--objective")] = (
        ObjectiveDirection.MAXIMISE
    ),
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate the transparent synthetic portfolio prototype against a winner map."""

    registry_store = Registry(registry)
    collections = _experiment_collections(registry, experiment_id)
    registered_seeds = registry_store.list_seeds()
    aliases = {seed.seed_id: seed.parent_seed_id or seed.seed_id for seed in registered_seeds}
    seeds_by_family: dict[str, ScenarioSeed] = {}
    for seed in registered_seeds:
        family = aliases[seed.seed_id]
        if seed.seed_id == family:
            seeds_by_family[family] = seed
        else:
            seeds_by_family.setdefault(family, seed)
    winner_map = build_winner_map(
        collections,
        metric_key=metric_key,
        objective=objective,
        seed_aliases=aliases,
    )
    report = evaluate_portfolio(
        winner_map,
        seeds_by_family,
        default_synthetic_portfolio_rules(),
    )
    _emit_or_write_json(report.to_json(), output, label="portfolio evaluation written")


@experiment_app.command("portfolio-study")
def experiment_portfolio_study_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
    metric_key: Annotated[str, typer.Option("--metric")] = "task.completion.rate",
    objective: Annotated[ObjectiveDirection, typer.Option("--objective")] = (
        ObjectiveDirection.MAXIMISE
    ),
    development_seed: Annotated[list[str] | None, typer.Option("--development-seed")] = None,
    held_out_seed: Annotated[list[str] | None, typer.Option("--held-out-seed")] = None,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate a fixed transparent selector on an explicit held-out seed set."""

    registry_store = Registry(registry)
    collections = _experiment_collections(registry, experiment_id)
    registered_seeds = registry_store.list_seeds()
    aliases = {seed.seed_id: seed.parent_seed_id or seed.seed_id for seed in registered_seeds}
    seeds_by_family: dict[str, ScenarioSeed] = {}
    for seed in registered_seeds:
        family = aliases[seed.seed_id]
        if seed.seed_id == family:
            seeds_by_family[family] = seed
        else:
            seeds_by_family.setdefault(family, seed)
    development = development_seed or []
    held_out = held_out_seed or []
    if experiment_id == PORTFOLIO_STUDY_EXPERIMENT_ID and not development and not held_out:
        development = [f"seed-{name}" for name in PORTFOLIO_DEVELOPMENT_PRESETS]
        held_out = [f"seed-{name}" for name in PORTFOLIO_HELD_OUT_PRESETS]
    try:
        report = evaluate_portfolio_study(
            build_winner_map(
                collections,
                metric_key=metric_key,
                objective=objective,
                seed_aliases=aliases,
            ),
            seeds_by_family,
            default_synthetic_portfolio_rules(),
            development_seed_ids=development,
            held_out_seed_ids=held_out,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = report.to_json()
    elif output_format == "csv":
        payload = portfolio_study_to_csv(report)
    elif output_format == "markdown":
        payload = portfolio_study_to_markdown(report)
    else:
        typer.echo("only --format json, csv, or markdown is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="portfolio study written")


@experiment_app.command("track-init")
def experiment_track_init_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    experiment_id: Annotated[str, typer.Option("--experiment-id")],
) -> None:
    """Initialise manual tracking for every slot in a registered protocol."""

    try:
        protocol = _registered_experiment_protocol(registry, experiment_id)
        created = ProtocolTracker(registry).register_protocol(protocol)
    except (RegistryNotFoundError, ValueError, ProtocolTrackingError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"protocol: {protocol.protocol_id}")
    typer.echo(f"slots: {len(protocol.slots)}")
    typer.echo(f"created: {created}")


@experiment_app.command("track-list")
def experiment_track_list_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    protocol_id: Annotated[str, typer.Option("--protocol-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """List manually tracked protocol slots."""

    tracker = ProtocolTracker(registry)
    try:
        summary = tracker.summary(protocol_id)
        slots = tracker.list_slots(protocol_id)
    except ProtocolTrackingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(
            json.dumps(
                {
                    "summary": summary.model_dump(mode="json"),
                    "slots": [slot.model_dump(mode="json") for slot in slots],
                },
                indent=2,
            )
        )
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"protocol: {protocol_id}")
    typer.echo(f"counts: {summary.counts_by_status}")
    for slot in slots:
        typer.echo(f"{slot.slot_id}: {slot.status.value}")


@experiment_app.command("track-update")
def experiment_track_update_command(
    registry: Annotated[
        Path, typer.Option("--registry", exists=True, dir_okay=False, readable=True)
    ],
    protocol_id: Annotated[str, typer.Option("--protocol-id")],
    slot_id: Annotated[str, typer.Option("--slot-id")],
    status: Annotated[ProtocolSlotStatus, typer.Option("--status")],
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    bundle_id: Annotated[str | None, typer.Option("--bundle-id")] = None,
    note: Annotated[str | None, typer.Option("--note")] = None,
) -> None:
    """Apply one explicit manual slot-status transition."""

    try:
        record = ProtocolTracker(registry).update_slot(
            protocol_id,
            slot_id,
            status,
            observed_run_id=run_id,
            observed_bundle_id=bundle_id,
            note=note,
        )
    except (ProtocolTrackingError, InvalidProtocolSlotTransitionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"slot: {record.slot_id}")
    typer.echo(f"status: {record.status.value}")


@diagnose_app.command("bundle")
def diagnose_bundle_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Evaluate deterministic diagnostics for a bundle."""

    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    pack = build_evidence_pack(result, collection)
    report = evaluate_rules(pack)
    typer.echo(f"run: {collection.run_id}")
    typer.echo(f"report: {report.report_id}")
    typer.echo(f"readiness: {report.overall_readiness.value}")
    typer.echo(f"triggered: {', '.join(report.triggered_rule_ids) or 'none'}")
    typer.echo(f"insufficient: {', '.join(report.insufficient_rule_ids) or 'none'}")
    if not result.report.may_import:
        typer.echo("bundle rejected; ordinary hypotheses are suppressed", err=True)
        raise typer.Exit(code=1)


@diagnose_app.command("evidence")
def diagnose_evidence_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Evaluate deterministic diagnostics for a saved EvidencePack JSON file."""

    pack = EvidencePack.model_validate_json(path.read_text(encoding="utf-8"))
    report = evaluate_rules(pack)
    typer.echo(f"evidence_pack: {pack.pack_id}")
    typer.echo(f"report: {report.report_id}")
    typer.echo(f"readiness: {report.overall_readiness.value}")
    typer.echo(f"triggered: {', '.join(report.triggered_rule_ids) or 'none'}")


@diagnose_app.command("rule-contract")
def diagnose_rule_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the closed trusted-local declarative-rule grammar boundary."""

    contract = declarative_rule_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"grammar_version: {contract.grammar_version}")
    typer.echo(f"trust_boundary: {contract.trust_boundary}")
    typer.echo(f"evidence_boundary: {contract.evidence_boundary}")
    typer.echo(f"maximum_yaml_bytes: {contract.maximum_yaml_bytes}")
    typer.echo(f"maximum_predicates: {contract.maximum_predicates}")
    typer.echo(f"reference_rule: {contract.reference_rule_id}")
    typer.echo("arbitrary_code: unsupported")


@diagnose_app.command("cross-rule-contract")
def diagnose_cross_rule_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the closed deterministic DIA-07 relationship policy."""

    contract = cross_rule_reasoning_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"policy_version: {contract.policy_version}")
    typer.echo(f"policies: {len(contract.policies)}")
    typer.echo(f"precedence_tiers: {contract.precedence_tiers}")
    typer.echo(f"retention: {contract.retention_guarantee}")
    typer.echo(f"confidence: {contract.confidence_semantics}")


@diagnose_app.command("cross-rule")
def diagnose_cross_rule_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate rules and emit the additive typed DIA-07 relationship report."""

    report = _diagnostic_report_from_path(path)
    analysis = report.cross_rule_analysis
    if analysis is None:  # pragma: no cover - current engine always produces the artifact
        typer.echo("cross-rule analysis is unavailable for this report", err=True)
        raise typer.Exit(code=1)
    if output_format == "json":
        payload = analysis.to_json()
    elif output_format == "text":
        relationship_lines = [
            f"{item.relation_type.value}: {item.source_rule_id} -> {item.target_rule_id} "
            f"({item.presentation_effect})"
            for item in analysis.relationships
        ]
        payload = "\n".join(
            [
                f"analysis_id: {analysis.analysis_id}",
                f"status: {analysis.status.value}",
                f"policy_version: {analysis.policy_version}",
                f"counts: {analysis.counts_by_type}",
                f"retained_rules: {', '.join(analysis.retained_rule_ids) or 'none'}",
                f"suppressed_rules: {', '.join(analysis.suppressed_rule_ids) or 'none'}",
                *relationship_lines,
            ]
        )
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="cross-rule reasoning report written")


@diagnose_app.command("rule-validate")
def diagnose_rule_validate_command(
    rule_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Validate and fingerprint one trusted local declarative YAML rule."""

    try:
        definition = load_declarative_rule(rule_path)
    except DeclarativeRuleError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(
            json.dumps(
                {
                    "definition": definition.model_dump(mode="json"),
                    "definition_fingerprint": definition.fingerprint(),
                    "valid": True,
                },
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return
    _require_text_format(output_format)
    typer.echo(f"rule_id: {definition.rule_id}")
    typer.echo(f"rule_version: {definition.rule_version}")
    typer.echo(f"grammar_version: {definition.grammar_version}")
    typer.echo(f"predicates: {len(definition.predicates)}")
    typer.echo(f"fingerprint: {definition.fingerprint()}")
    typer.echo("valid: true")


@diagnose_app.command("rule-evaluate")
def diagnose_rule_evaluate_command(
    rule_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    evidence_or_bundle: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Compile one trusted local YAML rule and evaluate an EvidencePack or bundle."""

    try:
        definition = load_declarative_rule(rule_path)
        pack = _evidence_pack_from_path(evidence_or_bundle)
        result = evaluate_declarative_rule(definition, pack)
    except (DeclarativeRuleError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = result.model_dump_json(indent=2)
    elif output_format == "text":
        payload = _rule_result_to_text(result)
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="declarative rule result written")


@diagnose_app.command("fairness")
def diagnose_fairness_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    dimension: Annotated[str, typer.Option("--dimension")] = "vehicle_tier_completion",
    minimum_outcome_gap: Annotated[
        float,
        typer.Option("--minimum-outcome-gap", min=0.0, max=1.0),
    ] = 0.20,
    minimum_group_support: Annotated[
        int,
        typer.Option("--minimum-group-support", min=1),
    ] = 2,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate only R7 over one explicit operational outcome-disparity dimension."""

    try:
        r7 = R7Config.model_validate(
            {
                "dimension": dimension,
                "minimum_outcome_gap": minimum_outcome_gap,
                "minimum_group_support": minimum_group_support,
            }
        )
        pack = _evidence_pack_from_path(path)
        report = evaluate_rules(pack, _r7_only_config(r7))
    except (OSError, ValueError) as exc:
        typer.echo(f"fairness diagnosis could not be evaluated: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    result = report.results[0]
    if output_format == "json":
        payload = result.model_dump_json(indent=2)
    elif output_format == "text":
        payload = _rule_result_to_text(result)
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="R7 fairness diagnosis written")


@diagnose_app.command("energy")
def diagnose_energy_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    minimum_energy_per_completed_task_j: Annotated[
        float,
        typer.Option("--minimum-energy-per-completed-task-j", min=0.0),
    ] = 1.50,
    minimum_completed_tasks: Annotated[
        int,
        typer.Option("--minimum-completed-tasks", min=1),
    ] = 10,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Evaluate only R8 over exact completed-task energy evidence."""

    try:
        r8 = R8Config(
            minimum_energy_per_completed_task_j=minimum_energy_per_completed_task_j,
            minimum_completed_tasks=minimum_completed_tasks,
        )
        pack = _evidence_pack_from_path(path)
        report = evaluate_rules(pack, _r8_only_config(r8))
    except (OSError, ValueError) as exc:
        typer.echo(f"energy diagnosis could not be evaluated: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    result = report.results[0]
    if output_format == "json":
        payload = result.model_dump_json(indent=2)
    elif output_format == "text":
        payload = _rule_result_to_text(result)
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="R8 energy diagnosis written")


@diagnose_app.command("nearest-flip")
def diagnose_nearest_flip_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    rule_id: Annotated[str, typer.Argument()],
    rule_config_path: Annotated[
        Path | None,
        typer.Option("--rule-config", dir_okay=False, readable=True),
    ] = None,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Find one exact verified R5/R7/R8 single-boundary configuration flip."""

    try:
        pack = _evidence_pack_from_path(path)
        config = (
            RuleSetConfig()
            if rule_config_path is None
            else RuleSetConfig.model_validate_json(rule_config_path.read_text(encoding="utf-8"))
        )
        analysis = analyse_nearest_flip(pack, rule_id, config)
    except (OSError, ValueError) as exc:
        typer.echo(f"nearest-flip analysis could not be evaluated: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = analysis.to_json()
    elif output_format == "text":
        payload = _nearest_flip_to_text(analysis)
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="nearest-flip analysis written")


@diagnose_app.command("temporal")
def diagnose_temporal_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    width_s: Annotated[float, typer.Option("--width-s", min=0.000001)],
    metric_key: Annotated[str, typer.Option("--metric-key")] = (
        "task.deadline_miss.completed_observed_rate"
    ),
    alignment_origin_s: Annotated[float, typer.Option("--origin-s")] = 0.0,
    analysis_start_s: Annotated[float | None, typer.Option("--start-s")] = None,
    analysis_end_s: Annotated[float | None, typer.Option("--end-s")] = None,
    partial_windows: Annotated[str, typer.Option("--partial-windows")] = "include",
    minimum_window_coverage: Annotated[
        float,
        typer.Option("--minimum-window-coverage", min=0.0, max=1.0),
    ] = 1.0,
    event_time_s: Annotated[float | None, typer.Option("--event-time-s")] = None,
    event_label: Annotated[str | None, typer.Option("--event-label")] = None,
    baseline_windows: Annotated[int, typer.Option("--baseline-windows", min=1)] = 2,
    minimum_evaluable_windows: Annotated[
        int,
        typer.Option("--minimum-evaluable-windows", min=2),
    ] = 4,
    deterioration_delta: Annotated[
        float,
        typer.Option("--deterioration-delta", min=0.000000001),
    ] = 0.10,
    sustained_windows: Annotated[int, typer.Option("--sustained-windows", min=1)] = 2,
    recovery_tolerance: Annotated[
        float,
        typer.Option("--recovery-tolerance", min=0.0),
    ] = 0.05,
    recovery_horizon_windows: Annotated[
        int,
        typer.Option("--recovery-horizon-windows", min=1),
    ] = 4,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Build temporal EvidencePack evidence and evaluate deterministic R6."""

    window_config = _windowed_metric_config(
        width_s,
        alignment_origin_s,
        analysis_start_s,
        analysis_end_s,
        partial_windows,
        10_000,
    )
    try:
        temporal_config = TemporalEvidenceConfig(
            metric_key=metric_key,
            minimum_window_coverage=minimum_window_coverage,
            event_time_s=event_time_s,
            event_label=event_label,
        )
        rules = RuleSetConfig(
            r6=R6Config(
                baseline_window_count=baseline_windows,
                minimum_evaluable_windows=minimum_evaluable_windows,
                minimum_deterioration_delta=deterioration_delta,
                sustained_window_count=sustained_windows,
                recovery_tolerance=recovery_tolerance,
                recovery_horizon_windows=recovery_horizon_windows,
            )
        )
    except ValueError as exc:
        typer.echo(f"invalid temporal diagnostic configuration: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    try:
        analysis = evaluate_temporal_bundle(
            result,
            window_config,
            temporal_config,
            rule_config=rules,
        )
    except WindowLimitExceededError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = analysis.to_json()
    elif output_format == "text":
        event_ordinal = (
            analysis.temporal_evidence.event.event_window_ordinal
            if analysis.temporal_evidence.event is not None
            else "none"
        )
        payload = (
            f"run: {analysis.temporal_evidence.run_id}\n"
            f"temporal_status: {analysis.temporal_evidence.status.value}\n"
            f"metric_key: {analysis.temporal_evidence.metric_key}\n"
            f"eligible_windows: {analysis.temporal_evidence.eligible_window_count}\n"
            f"ineligible_windows: {analysis.temporal_evidence.ineligible_window_count}\n"
            f"event_window_ordinal: {event_ordinal}\n"
            f"r6_status: {analysis.r6_result.status.value}\n"
            f"recovery: {analysis.r6_result.metadata.get('recovery_assessment', 'unavailable')}\n"
        )
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="temporal diagnostic analysis written")


@diagnose_app.command("report")
def diagnose_report_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Emit a complete machine-readable DiagnosticReport for a bundle or EvidencePack JSON."""

    if output_format != "json":
        typer.echo("only --format json is supported", err=True)
        raise typer.Exit(code=1)
    report = _diagnostic_report_from_path(path)
    typer.echo(report.to_json())


@diagnose_app.command("evaluate")
def diagnose_evaluate_command(
    fixture_set: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    extended: Annotated[bool, typer.Option("--extended/--declared")] = False,
) -> None:
    """Evaluate declared or expanded severity/seed synthetic diagnostic fixtures."""

    fixtures = load_fixture_set(fixture_set)
    if extended:
        fixtures = build_extended_fixture_set(fixtures)
    report = evaluate_fixture_set(fixtures)
    typer.echo(report.to_json())


@diagnose_app.command("render")
def diagnose_render_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "markdown",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Render only already-computed deterministic diagnostic findings into prose."""

    narrative = render_diagnostic_findings(_diagnostic_report_from_path(path))
    if output_format == "markdown":
        payload = diagnostic_narrative_to_markdown(narrative)
    elif output_format == "json":
        payload = narrative.to_json()
    else:
        typer.echo("only --format markdown or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="diagnostic narrative written")


@provenance_app.command("metric")
def provenance_metric_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    metric_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Trace one metric result back to definitions, canonical records, and source rows."""

    try:
        context = build_provenance_context(path)
        trace = get_metric_provenance(context, metric_key)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_provenance_trace(trace, output_format)


@provenance_app.command("window-metric")
def provenance_window_metric_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    metric_key: Annotated[str, typer.Argument()],
    width_s: Annotated[float, typer.Option("--width-s", min=0.000001)],
    window_ordinal: Annotated[int, typer.Option("--window-ordinal", min=0)] = 0,
    alignment_origin_s: Annotated[float, typer.Option("--origin-s")] = 0.0,
    analysis_start_s: Annotated[float | None, typer.Option("--start-s")] = None,
    analysis_end_s: Annotated[float | None, typer.Option("--end-s")] = None,
    partial_windows: Annotated[str, typer.Option("--partial-windows")] = "include",
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Trace one fixed-window metric to its accepted in-window source rows."""

    config = _windowed_metric_config(
        width_s,
        alignment_origin_s,
        analysis_start_s,
        analysis_end_s,
        partial_windows,
        10_000,
    )
    bundle = validate_bundle(path)
    _ensure_metric_context_available(bundle)
    try:
        series = compute_windowed_metrics_for_bundle(bundle, config)
        trace = build_window_metric_trace(metric_key, bundle, series, window_ordinal)
    except (ValueError, WindowLimitExceededError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_provenance_trace(trace, output_format)


@provenance_app.command("contributors")
def provenance_contributors_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    metric_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Export every canonical candidate row and its metric-inclusion state."""

    try:
        report = get_metric_contributions(build_provenance_context(path), metric_key)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = report.to_json()
    elif output_format == "csv":
        payload = contribution_report_to_csv(report)
    else:
        typer.echo("only --format json or csv is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="contribution ledger written")


@provenance_app.command("difference-contract")
def provenance_difference_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Publish the bounded PRO-01 difference-lineage contract."""

    contract = difference_provenance_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
    elif output_format == "text":
        typer.echo(f"schema_version: {contract.schema_version}")
        typer.echo(f"capability_id: {contract.capability_id}")
        typer.echo(f"comparison_basis: {contract.comparison_basis}")
        typer.echo(f"arithmetic_metrics: {len(contract.arithmetic_metric_methods)}")
        typer.echo("complete_candidate_row_ledgers: true")
        typer.echo("unavailable_is_not_zero: true")
        typer.echo(f"non_causality_statement: {contract.non_causality_statement}")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)


@provenance_app.command("graph-contract")
def provenance_graph_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Publish the deterministic bounded PRO-02 graph export contract."""

    contract = provenance_graph_export_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
    elif output_format == "text":
        typer.echo(f"schema_version: {contract.schema_version}")
        typer.echo(f"capability_id: {contract.capability_id}")
        typer.echo(f"formats: {', '.join(contract.formats)}")
        typer.echo(f"default_node_limit: {contract.default_node_limit}")
        typer.echo(f"default_edge_limit: {contract.default_edge_limit}")
        typer.echo(f"maximum_node_limit: {contract.maximum_node_limit}")
        typer.echo(f"maximum_edge_limit: {contract.maximum_edge_limit}")
        typer.echo(f"default_redaction_mode: {contract.default_redaction_mode.value}")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)


@provenance_app.command("completeness-contract")
def provenance_completeness_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Publish the explicit PRO-03 report-claim denominator and score contract."""

    contract = provenance_completeness_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
    elif output_format == "text":
        typer.echo(f"schema_version: {contract.schema_version}")
        typer.echo(f"capability_id: {contract.capability_id}")
        typer.echo(
            "supported_report_types: "
            + ", ".join(item.value for item in contract.supported_report_types)
        )
        typer.echo(f"denominator: {contract.denominator_definition}")
        typer.echo(f"numerator: {contract.score_numerator_definition}")
        typer.echo(f"zero_denominator: {contract.zero_denominator_policy}")
        typer.echo("unavailable_is_not_zero: true")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)


@provenance_app.command("completeness")
def provenance_completeness_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    report_type: Annotated[str, typer.Option("--report-type")] = ResearchReportType.RUN.value,
    comparison_baseline: Annotated[
        Path | None,
        typer.Option("--comparison-baseline", exists=True, readable=True),
    ] = None,
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Inventory and score the typed claims in one run-like report."""

    try:
        report = get_report_provenance_completeness(
            build_provenance_context(path),
            report_type,
            comparison_baseline=(
                build_provenance_context(comparison_baseline)
                if comparison_baseline is not None
                else None
            ),
        )
        payload = _provenance_completeness_payload(report, output_format)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_or_write_json(payload, output, label="provenance completeness written")


@provenance_app.command("comparison-completeness")
def provenance_comparison_completeness_command(
    baseline_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    variation_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Inventory and score every typed claim in one comparison report."""

    try:
        report = get_comparison_provenance_completeness(
            build_provenance_context(baseline_path),
            build_provenance_context(variation_path),
        )
        payload = _provenance_completeness_payload(report, output_format)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_or_write_json(payload, output, label="comparison provenance completeness written")


@provenance_app.command("difference-contributors")
def provenance_difference_contributors_command(
    baseline_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    variation_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    metric_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Export compatible variation-minus-baseline contributor lineage."""

    try:
        report = get_difference_contributions(
            build_provenance_context(baseline_path),
            build_provenance_context(variation_path),
            metric_key,
        )
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = report.to_json()
    elif output_format == "csv":
        payload = difference_contribution_report_to_csv(report)
    else:
        typer.echo("only --format json or csv is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="difference contribution ledger written")


@provenance_app.command("window-contributors")
def provenance_window_contributors_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    metric_key: Annotated[str, typer.Argument()],
    width_s: Annotated[float, typer.Option("--width-s", min=0.000001)],
    window_ordinal: Annotated[int, typer.Option("--window-ordinal", min=0)] = 0,
    alignment_origin_s: Annotated[float, typer.Option("--origin-s")] = 0.0,
    analysis_start_s: Annotated[float | None, typer.Option("--start-s")] = None,
    analysis_end_s: Annotated[float | None, typer.Option("--end-s")] = None,
    partial_windows: Annotated[str, typer.Option("--partial-windows")] = "include",
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Export every accepted candidate row for one fixed-window metric."""

    if output_format != "json":
        typer.echo("only --format json is supported", err=True)
        raise typer.Exit(code=1)
    config = _windowed_metric_config(
        width_s,
        alignment_origin_s,
        analysis_start_s,
        analysis_end_s,
        partial_windows,
        10_000,
    )
    bundle = validate_bundle(path)
    _ensure_metric_context_available(bundle)
    try:
        series = compute_windowed_metrics_for_bundle(bundle, config)
        report = build_window_metric_contribution_report(
            bundle,
            series,
            window_ordinal,
            metric_key,
        )
    except (ValueError, WindowLimitExceededError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_or_write_json(report.to_json(), output, label="window contribution ledger written")


@provenance_app.command("rule")
def provenance_rule_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    rule_id: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Trace one diagnostic rule result back to cited metric evidence."""

    try:
        context = build_provenance_context(path)
        trace = get_rule_provenance(context, rule_id)
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _emit_provenance_trace(trace, output_format)


@provenance_app.command("run")
def provenance_run_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Trace the run, manifest, validation, metric, and diagnostic context."""

    context = build_provenance_context(path)
    trace = get_run_provenance(context)
    _emit_provenance_trace(trace, output_format)


@provenance_app.command("source")
def provenance_source_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    source_file: Annotated[str, typer.Argument()],
    row: Annotated[int, typer.Argument(min=1)],
    context_rows: Annotated[int, typer.Option("--context-rows", min=0)] = 2,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect one read-only declared tabular source row inside a bundle."""

    context = build_provenance_context(path)
    preview = get_source_provenance(context, source_file, row, context_rows=context_rows)
    if output_format == "json":
        typer.echo(preview.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or --format json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"source: {preview.file}:{preview.row_number}")
    typer.echo(f"status: {preview.status.value}")
    typer.echo(f"inclusion_status: {preview.inclusion_status}")
    if preview.canonical_record_type is not None:
        typer.echo(f"canonical_record_type: {preview.canonical_record_type}")
    if preview.validation_findings:
        typer.echo(f"validation_findings: {len(preview.validation_findings)}")
    for warning in preview.warnings:
        typer.echo(f"warning: {warning}")


@provenance_app.command("export")
def provenance_export_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    root_type: Annotated[str, typer.Option("--root-type")],
    root_id: Annotated[str, typer.Option("--root-id")] = "",
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
    max_nodes: Annotated[
        int,
        typer.Option("--max-nodes", min=1, max=MAX_GRAPH_NODE_LIMIT),
    ] = DEFAULT_GRAPH_NODE_LIMIT,
    max_edges: Annotated[
        int,
        typer.Option("--max-edges", min=0, max=MAX_GRAPH_EDGE_LIMIT),
    ] = DEFAULT_GRAPH_EDGE_LIMIT,
    redaction: Annotated[str, typer.Option("--redaction")] = GraphRedactionMode.SAFE.value,
) -> None:
    """Export a provenance trace as JSON, Markdown, bounded DOT, or bounded GraphML."""

    try:
        context = build_provenance_context(path)
        if root_type == "metric":
            trace = get_metric_provenance(context, root_id)
        elif root_type == "rule":
            trace = get_rule_provenance(context, root_id)
        elif root_type == "run":
            trace = get_run_provenance(context)
        else:
            msg = "root-type must be one of: metric, rule, run"
            raise ProvenanceQueryError(msg)
        payload = export_provenance(
            trace,
            output_format,
            node_limit=max_nodes,
            edge_limit=max_edges,
            redaction_mode=redaction,
        )
    except ProvenanceQueryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output is not None:
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"provenance_trace: {output}")
    else:
        typer.echo(payload)


@synthetic_app.command("presets")
def synthetic_presets_command() -> None:
    """List standalone synthetic scenario presets."""

    for name in list_preset_names():
        typer.echo(name)


@synthetic_app.command("measurement-contract")
def synthetic_measurement_contract_command(
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Publish the closed EXP-03 measurement-noise and dropout contract."""

    payload = measurement_impairment_contract().model_dump_json(indent=2) + "\n"
    if output is None:
        typer.echo(payload, nl=False)
    else:
        output.write_text(payload, encoding="utf-8")
        typer.echo(f"measurement_contract: {output}")


@synthetic_app.command("generate-config")
def synthetic_generate_config_command(
    config: Annotated[Path, typer.Option("--config", exists=True, readable=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Generate one synthetic bundle from a complete strict YAML configuration."""

    try:
        scenario = load_synthetic_scenario_config(config)
        destination = write_synthetic_bundle(scenario, output, overwrite=overwrite)
        result = validate_bundle(destination)
    except (OSError, ValueError, FileExistsError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"bundle: {destination}")
    typer.echo(f"status: {result.report.status.value}")
    typer.echo("synthetic: true")
    manifest = result.manifest
    audit = manifest.synthetic_measurement_impairment if manifest is not None else None
    typer.echo(f"measurement_imperfections: {str(audit is not None).lower()}")
    if audit is not None:
        typer.echo(f"measurement_audit: {audit.audit_fingerprint}")
        typer.echo(
            f"measurement_rows_dropped: {sum(item.rows_dropped for item in audit.dropout_audits)}"
        )
    if not result.report.may_import:
        raise typer.Exit(code=1)


@synthetic_app.command("generate-preset")
def synthetic_generate_preset_command(
    name: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    random_seed: Annotated[int, typer.Option("--seed", min=0)] = 7,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Generate one deterministic synthetic run bundle."""

    try:
        config = preset_config(name, random_seed=random_seed)
        destination = write_synthetic_bundle(config, output, overwrite=overwrite)
    except (ValueError, FileExistsError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    result = validate_bundle(destination)
    typer.echo(f"bundle: {destination}")
    typer.echo(f"status: {result.report.status.value}")
    synthetic = result.manifest.environment.name == "synthetic" if result.manifest else False
    typer.echo(f"synthetic: {synthetic}")
    if not result.report.may_import:
        raise typer.Exit(code=1)


@synthetic_app.command("experiment-generate-preset")
def synthetic_experiment_generate_preset_command(
    name: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    seeds: Annotated[str, typer.Option("--seeds")] = "1,2,3",
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Generate a deterministic multi-seed synthetic experiment."""

    if name != "trivial_multi_algorithm":
        typer.echo("only trivial_multi_algorithm is supported for multi-seed generation", err=True)
        raise typer.Exit(code=1)
    try:
        seed_values = _parse_seed_list(seeds)
        paths = generate_trivial_multi_algorithm_experiment(
            output,
            random_seeds=seed_values,
            overwrite=overwrite,
        )
    except (ValueError, FileExistsError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"experiment: {name}")
    typer.echo(f"bundles: {len(paths)}")
    for path in paths:
        typer.echo(path)


@synthetic_app.command("verify")
def synthetic_verify_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Verify synthetic bundle labels and validation status."""

    result = verify_synthetic_path(path)
    typer.echo(f"path: {result.path}")
    typer.echo(f"checked: {result.checked_bundle_count}")
    typer.echo(f"accepted: {result.accepted_bundle_count}")
    typer.echo(f"rejected: {result.rejected_bundle_count}")
    for message in result.messages:
        typer.echo(message)
    if not result.ok:
        raise typer.Exit(code=1)


@synthetic_app.command("case-study-pack")
def synthetic_case_study_pack_command(
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Build baseline, incident, and infrastructure synthetic case-study artifacts."""

    try:
        manifest = build_synthetic_case_study_pack(output, overwrite=overwrite)
    except (FileExistsError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"case_study_pack: {manifest.pack_id}")
    typer.echo(f"scenarios: {len(manifest.scenario_ids)}")
    typer.echo(f"artifacts: {len(manifest.artifacts)}")
    typer.echo(f"manifest: {output / 'manifest.json'}")


@demo_app.command("initialise")
def demo_initialise_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Create a reproducible standalone demo workspace."""

    try:
        result = initialise_workspace(path, force=force)
    except (FileExistsError, ValueError, PermissionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("TrafficTwin standalone demo workspace initialised.")
    typer.echo("Synthetic data only; no Randy, SUMO, or live Manchester data is used.")
    typer.echo(f"workspace: {result.path}")
    typer.echo(f"registry: {result.registry_path}")
    typer.echo(f"bundles: {result.bundle_count}")
    typer.echo(f"imported_runs: {result.imported_run_count}")
    typer.echo(f"manifest: {result.manifest_path}")


@demo_app.command("reset")
def demo_reset_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
    yes: Annotated[bool, typer.Option("--yes")] = False,
) -> None:
    """Reset a marked standalone demo workspace."""

    try:
        result = reset_workspace(path, yes=yes)
    except (FileNotFoundError, ValueError, PermissionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"workspace reset: {result.path}")
    typer.echo(f"imported_runs: {result.imported_run_count}")


@demo_app.command("status")
def demo_status_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
) -> None:
    """Inspect a standalone demo workspace."""

    status = workspace_status(path)
    typer.echo(f"workspace: {status.path}")
    typer.echo(f"exists: {status.exists}")
    typer.echo(f"valid_workspace: {status.valid_workspace}")
    typer.echo(f"registry: {status.registry_path}")
    typer.echo(f"scenarios: {status.scenario_count}")
    typer.echo(f"imported_runs: {status.imported_run_count}")
    typer.echo(f"reports: {status.report_count}")
    typer.echo(f"comparisons: {status.comparison_count}")
    typer.echo(f"diagnostics: {status.diagnostics_status}")
    typer.echo("synthetic: true")
    for message in status.messages:
        typer.echo(f"warning: {message}")
    if not status.valid_workspace:
        raise typer.Exit(code=1)


@participant_app.command("analyse-mock")
def participant_evaluation_analyse_mock_command(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "json",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Analyse only a dataset carrying the required synthetic_mock label."""

    try:
        report = analyse_participant_results(load_mock_participant_dataset(path))
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        payload = report.to_json()
    elif output_format == "csv":
        payload = participant_analysis_to_csv(report)
    else:
        typer.echo("only --format json or csv is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="mock participant analysis written")


@demo_app.command("launch")
def demo_launch_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    port: Annotated[int | None, typer.Option("--port", min=1024, max=65535)] = None,
) -> None:
    """Initialise if needed and launch the Streamlit demo UI.

    Use --port for side-by-side operation next to another TrafficTwin process
    serving a different workspace on a different port.
    """

    try:
        plan = launch_workspace(path, dry_run=dry_run, port=port)
    except (FileExistsError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("TrafficTwin standalone demo uses synthetic fixture data only.")
    typer.echo(f"workspace: {plan.workspace}")
    typer.echo(f"registry: {plan.registry}")
    typer.echo("command: " + " ".join(plan.command))
    if dry_run:
        typer.echo("dry_run: true")


@report_app.command("run")
def report_run_command(
    path_or_run: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    registry: Annotated[
        Path | None,
        typer.Option("--registry", exists=True, dir_okay=False, readable=True),
    ] = None,
) -> None:
    """Export a deterministic single-run report."""

    _write_report(build_run_report, path_or_run, output, registry=registry)


@report_app.command("compare")
def report_compare_command(
    baseline: Annotated[Path, typer.Argument(exists=True, readable=True)],
    variation: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    registry: Annotated[
        Path | None,
        typer.Option("--registry", exists=True, dir_okay=False, readable=True),
    ] = None,
) -> None:
    """Export a deterministic baseline-versus-variation report."""

    try:
        report = build_comparison_report(baseline, variation)
    except ReportBuildError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _write_report_payload(_report_with_registry_annotations(report, registry), output)


@report_app.command("diagnostics")
def report_diagnostics_command(
    path_or_run: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    registry: Annotated[
        Path | None,
        typer.Option("--registry", exists=True, dir_okay=False, readable=True),
    ] = None,
) -> None:
    """Export a deterministic diagnostic report summary."""

    _write_report(build_diagnostics_report, path_or_run, output, registry=registry)


@report_app.command("full")
def report_full_command(
    path_or_run: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    comparison_baseline: Annotated[
        Path | None,
        typer.Option("--comparison-baseline", exists=True, readable=True),
    ] = None,
    registry: Annotated[
        Path | None,
        typer.Option("--registry", exists=True, dir_okay=False, readable=True),
    ] = None,
) -> None:
    """Export a deterministic full report as Markdown or standalone HTML."""

    try:
        report = build_full_report(path_or_run, comparison_baseline=comparison_baseline)
    except ReportBuildError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _write_report_payload(_report_with_registry_annotations(report, registry), output)


@report_app.command("diff-contract")
def report_diff_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the deterministic REP-03 structured report comparison boundary."""

    contract = report_diff_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"contract_version: {contract.contract_version}")
    typer.echo("report_types: " + ", ".join(item.value for item in contract.supported_report_types))
    typer.echo("classifications: " + ", ".join(item.value for item in contract.classifications))
    typer.echo("compares_rendered_prose: false")
    typer.echo("compares_analyst_annotations: false")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@report_app.command("executive-contract")
def report_executive_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the deterministic REP-04 one-page summary boundary."""

    contract = executive_summary_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"contract_version: {contract.contract_version}")
    typer.echo(f"renderer_version: {contract.renderer_version}")
    typer.echo("report_types: " + ", ".join(item.value for item in contract.supported_report_types))
    typer.echo("formats: " + ", ".join(item.value for item in contract.supported_formats))
    typer.echo(f"maximum_highlights: {contract.maximum_highlights}")
    typer.echo("source_warning_policy: retain_all_or_refuse")
    typer.echo("pdf_overflow_policy: fail_closed")
    typer.echo("scientific_recomputation: false")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@report_app.command("executive")
def report_executive_command(
    source_report: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Render a bounded supervisor summary from an existing structured report JSON."""

    try:
        report = parse_research_report_json(source_report.read_bytes())
        summary = project_executive_summary(
            report,
            source_report_reference=source_report.name,
        )
        suffix = output.suffix.lower()
        if suffix not in {".json", ".md", ".markdown", ".html", ".pdf"}:
            typer.echo(
                "executive summary output must use .json, .md, .markdown, .html, or .pdf",
                err=True,
            )
            raise typer.Exit(code=1)
        output.parent.mkdir(parents=True, exist_ok=True)
        if suffix == ".json":
            output.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
        elif suffix in {".md", ".markdown"}:
            output.write_text(executive_summary_to_markdown(summary), encoding="utf-8")
        elif suffix == ".html":
            output.write_text(executive_summary_to_html(summary), encoding="utf-8")
        else:
            output.write_bytes(executive_summary_to_pdf_bytes(summary))
    except typer.Exit:
        raise
    except (
        OSError,
        ReportDiffError,
        ExecutiveSummaryError,
        ExecutiveSummaryLayoutError,
    ) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"executive_summary: {output}")
    typer.echo(f"source_mode: {summary.source_mode.value}")
    typer.echo(f"claims: {summary.availability.total_claims}")
    typer.echo(f"warnings_retained: {len(summary.warnings)}")
    typer.echo(f"fingerprint: {summary.fingerprint()}")


@report_app.command("diff")
def report_diff_command(
    baseline: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    variation: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Compare two saved structured report JSON payloads without diffing prose."""

    try:
        baseline_report = parse_research_report_json(baseline.read_bytes())
        variation_report = parse_research_report_json(variation.read_bytes())
        report = compare_structured_reports(baseline_report, variation_report)
    except (OSError, ReportDiffError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    suffix = output.suffix.lower()
    if suffix not in {".json", ".md", ".markdown"}:
        typer.echo("structured report diff output must use .json, .md, or .markdown", err=True)
        raise typer.Exit(code=1)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        report.model_dump_json(indent=2) if suffix == ".json" else report_diff_to_markdown(report)
    )
    output.write_text(payload + ("\n" if suffix == ".json" else ""), encoding="utf-8")
    typer.echo(f"report_diff: {output}")
    typer.echo(f"status: {report.status.value}")
    typer.echo(f"fingerprint: {report.fingerprint()}")


@report_app.command("latex-contract")
def report_latex_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the deterministic REP-01 table and figure boundary."""

    contract = latex_export_contract()
    if output_format == "json":
        typer.echo(contract.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"schema_version: {contract.schema_version}")
    typer.echo(f"latex_renderer: {contract.latex_renderer_version}")
    typer.echo(f"figure_renderer: {contract.figure_renderer_version}")
    typer.echo("artifacts: " + ", ".join(item.value for item in contract.supported_artifacts))
    typer.echo("figures: " + ", ".join(item.value for item in contract.figure_formats))
    typer.echo(f"maximum_table_rows: {contract.maximum_table_rows}")
    typer.echo(f"maximum_figure_entries: {contract.maximum_figure_entries}")
    typer.echo(f"fingerprint: {contract.fingerprint()}")


@report_app.command("latex-metrics")
def report_latex_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    figure: Annotated[Path | None, typer.Option("--figure", dir_okay=False)] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Export metric results as an escaped LaTeX table and optional static figure."""

    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    projection = project_metric_collection(compute_metrics_for_bundle(result))
    _write_research_projection(projection, output, figure, overwrite=overwrite)


@report_app.command("latex-comparison")
def report_latex_comparison_command(
    baseline: Annotated[Path, typer.Argument(exists=True, readable=True)],
    variation: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    figure: Annotated[Path | None, typer.Option("--figure", dir_okay=False)] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Export an existing pairwise metric comparison as LaTeX and an optional figure."""

    baseline_result = validate_bundle(baseline)
    variation_result = validate_bundle(variation)
    _ensure_metric_context_available(baseline_result)
    _ensure_metric_context_available(variation_result)
    comparison = compare_metric_collections(
        compute_metrics_for_bundle(baseline_result),
        compute_metrics_for_bundle(variation_result),
    )
    projection = project_comparison_report(comparison)
    _write_research_projection(projection, output, figure, overwrite=overwrite)


@report_app.command("latex-study")
def report_latex_study_command(
    study_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    figure: Annotated[Path | None, typer.Option("--figure", dir_okay=False)] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Export a strict saved STA-01 study as LaTeX and an optional static figure."""

    try:
        study = parse_statistical_study_json(study_path.read_bytes())
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    projection = project_statistical_study(study)
    _write_research_projection(projection, output, figure, overwrite=overwrite)


@report_app.command("latex-rules")
def report_latex_rules_command(
    path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    figure: Annotated[Path | None, typer.Option("--figure", dir_okay=False)] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Export deterministic bundle diagnostics as LaTeX and an optional status figure."""

    projection = project_diagnostic_report(_diagnostic_report_from_path(path))
    _write_research_projection(projection, output, figure, overwrite=overwrite)


@release_app.command("status")
def release_status_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show release, licence, and supported deployment modes."""

    metadata = current_release_metadata()
    payload = {
        **metadata.model_dump(mode="json"),
        "deployment_modes": {
            "synthetic_static_site": "supported",
            "standalone_streamlit_container": "supported",
            "public_tos_atlas": "permission_gated",
            "direct_environment_launch": "unsupported",
            "live_data": "unsupported",
        },
    }
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
        return
    _require_text_format(output_format)
    typer.echo(f"version: {metadata.version}")
    typer.echo(f"release: {metadata.release_label}")
    typer.echo(f"licence: {metadata.licence_status}")
    typer.echo(f"status: {metadata.production_status}")
    for mode, state in payload["deployment_modes"].items():
        typer.echo(f"{mode}: {state}")


@release_app.command("stage-demo-site")
def release_stage_demo_site_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    overwrite: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Stage a Netlify-compatible synthetic-only static demonstration."""

    try:
        manifest = stage_synthetic_demo_site(workspace, output, overwrite=overwrite)
    except (FileExistsError, OSError, PermissionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"site: {output}")
    typer.echo(f"scenarios: {len(manifest.scenarios)}")
    typer.echo("synthetic: true")
    typer.echo("live_data: false")
    typer.echo(f"licence: {manifest.licence_status}")


@release_app.command("v07-workspace-init")
def release_v07_workspace_init_command(
    path: Annotated[Path, typer.Argument(file_okay=False)],
) -> None:
    """Create a new, separately marked v0.7 workspace (REL-01 foundation).

    The target must not exist; no v0.6 workspace or registry is read or
    changed. REL-01 remains planned.
    """

    try:
        result = initialise_v07_workspace(path)
    except (V07CompatibilityError, FileExistsError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    manifest = result.inspection.manifest
    typer.echo(f"workspace: {result.path}")
    typer.echo(f"workspace_kind: {manifest.workspace_kind}")
    typer.echo(f"workspace_namespace: {manifest.workspace_namespace}")
    typer.echo(f"cache_namespace: {manifest.cache_namespace}")
    typer.echo(f"active_registry: {result.active_registry_path}")
    typer.echo(f"manifest_fingerprint: {result.inspection.manifest_sha256}")
    typer.echo("capability_status: planned")


@release_app.command("v07-workspace-inspect")
def release_v07_workspace_inspect_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Read-only structural diagnosis of one v0.7 workspace marker and registry."""

    try:
        inspection = inspect_v07_workspace(path)
    except V07CompatibilityError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(json.dumps(inspection.model_dump(mode="json"), indent=2, sort_keys=True))
        return
    _require_text_format(output_format)
    manifest = inspection.manifest
    typer.echo(f"workspace: {path}")
    typer.echo(f"valid: {str(inspection.valid).lower()}")
    typer.echo(f"workspace_kind: {manifest.workspace_kind}")
    typer.echo(f"workspace_namespace: {manifest.workspace_namespace}")
    typer.echo(f"design_version: {manifest.design_version}")
    typer.echo(f"implementation_status: {manifest.implementation_status}")
    typer.echo(f"created_at: {manifest.created_at.isoformat()}")
    typer.echo(f"producer_package_version: {manifest.producer_package_version}")
    typer.echo(f"registry_schema_version: {inspection.active_registry_status.current_version}")
    typer.echo(f"manifest_sha256: {inspection.manifest_sha256}")
    typer.echo(f"active_registry_sha256: {inspection.active_registry_sha256}")
    typer.echo("capability_status: planned")


@release_app.command("v06-copy-preview")
def release_v06_copy_preview_command(
    source_registry: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Read-only preview of a byte-exact, non-active v0.6 registry copy.

    The source registry and the active v0.7 registry are not modified. The
    source must be closed and checkpointed; WAL/journal sidecars are refused.
    """

    try:
        preview = preview_v06_registry_copy(source_registry, workspace)
    except V07CompatibilityError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(json.dumps(preview.model_dump(mode="json"), indent=2, sort_keys=True))
        return
    _require_text_format(output_format)
    typer.echo(f"operation: {preview.operation}")
    typer.echo(f"source_registry_sha256: {preview.source_registry_sha256}")
    typer.echo(f"source_registry_schema_version: {preview.source_registry_schema_version}")
    typer.echo("source_product_version: unknown")
    typer.echo(f"target_directory: {preview.target_relative_directory}")
    typer.echo(f"required_free_bytes: {preview.required_free_bytes}")
    typer.echo(f"available_free_bytes: {preview.available_free_bytes}")
    typer.echo(f"has_required_space: {str(preview.has_required_space).lower()}")
    typer.echo(f"backup_required: {str(preview.backup_required).lower()}")
    typer.echo(f"automatic_activation: {str(preview.automatic_activation).lower()}")
    for blocker in preview.blockers:
        typer.echo(f"blocker: {blocker}")
    for action in preview.actions:
        typer.echo(f"action: {action}")
    typer.echo("capability_status: planned")


@release_app.command("v06-copy")
def release_v06_copy_command(
    source_registry: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
) -> None:
    """Publish a byte-exact v0.6 registry copy under compatibility/v0.6.

    The copy is new-only and never becomes the active v0.7 registry; the
    source registry bytes are verified unchanged before and after.
    """

    try:
        result = copy_v06_registry(source_registry, workspace)
    except (V07CompatibilityError, FileExistsError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    receipt = result.receipt
    typer.echo(f"copy_id: {receipt.copy_id}")
    typer.echo(f"copied_registry: {result.registry_path}")
    typer.echo(f"receipt: {result.receipt_path}")
    typer.echo(f"byte_exact: {str(receipt.byte_exact).lower()}")
    typer.echo(f"source_unchanged: {str(receipt.source_unchanged_during_copy).lower()}")
    typer.echo(f"automatic_activation: {str(receipt.automatic_activation).lower()}")
    typer.echo(f"scientific_admission: {receipt.scientific_admission}")
    typer.echo("capability_status: planned")


@release_app.command("v06-attest")
def release_v06_attest_command(
    registry: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    operator: Annotated[str, typer.Option("--operator", help="Attesting operator name.")],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Record the operator clean-checkout attestation for one registry.

    Running this command is the ADR-058 operator statement that the immutable
    v0.6.0 tag was run from a clean checkout against this exact registry.
    TrafficTwin cannot verify that human step and the attestation approves no
    migration by itself.
    """

    try:
        attestation = build_v06_producer_attestation(
            registry, operator_name=operator, attested_at=datetime.now(UTC)
        )
        payload = (attestation.canonical_json() + "\n").encode("utf-8")
        with output.open("xb") as handle:
            handle.write(payload)
    except (V06AttestationError, FileExistsError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"attestation: {output}")
    typer.echo(f"attested_tag: {attestation.attested_tag}")
    typer.echo(f"registry_sha256: {attestation.registry_sha256}")
    typer.echo(f"attestation_fingerprint: {attestation.fingerprint()}")
    typer.echo(f"migration_approved: {str(attestation.migration_approved).lower()}")
    typer.echo("capability_status: planned")


@release_app.command("v06-migrate-preview")
def release_v06_migrate_preview_command(
    source_registry: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    attestation_path: Annotated[
        Path, typer.Option("--attestation", exists=True, dir_okay=False, readable=True)
    ],
) -> None:
    """Read-only plan for one attested same-schema activation."""

    try:
        attestation = load_v06_producer_attestation(attestation_path)
        preview = preview_v06_migration(source_registry, workspace, attestation)
    except (V06AttestationError, V06MigrationError, V07CompatibilityError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"operation: {preview.operation}")
    typer.echo(f"migration_id: {preview.migration_id}")
    typer.echo(f"source_product_version: {preview.source_product_version} (operator attested)")
    typer.echo(f"source_registry_sha256: {preview.source_registry_sha256}")
    typer.echo(f"backup_directory: {preview.backup_relative_directory}")
    typer.echo(f"required_free_bytes: {preview.required_free_bytes}")
    typer.echo(f"has_required_space: {str(preview.has_required_space).lower()}")
    typer.echo(f"rollback_supported: {str(preview.rollback_supported).lower()}")
    for action in preview.actions:
        typer.echo(f"action: {action}")
    for blocker in preview.blockers:
        typer.echo(f"blocker: {blocker}")
    typer.echo("capability_status: planned")


@release_app.command("v06-migrate")
def release_v06_migrate_command(
    source_registry: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    attestation_path: Annotated[
        Path, typer.Option("--attestation", exists=True, dir_okay=False, readable=True)
    ],
) -> None:
    """Back up the active v0.7 registry, then activate the attested source.

    The previous active registry is preserved byte-exactly for rollback and
    the source registry is never modified.
    """

    try:
        attestation = load_v06_producer_attestation(attestation_path)
        result = migrate_v06_registry(source_registry, workspace, attestation)
    except (
        V06AttestationError,
        V06MigrationError,
        V07CompatibilityError,
        FileExistsError,
        OSError,
    ) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    receipt = result.receipt
    typer.echo(f"migration_id: {receipt.migration_id}")
    typer.echo(f"backup_registry: {result.backup_registry_path}")
    typer.echo(f"receipt: {result.receipt_path}")
    typer.echo(f"activated_registry_sha256: {receipt.active_registry_sha256_after}")
    typer.echo(f"source_unchanged: {str(receipt.source_unchanged_during_migration).lower()}")
    typer.echo(f"rollback_available: {str(receipt.rollback_available).lower()}")
    typer.echo(f"scientific_admission: {receipt.scientific_admission}")
    typer.echo("capability_status: planned")


@release_app.command("v06-rollback")
def release_v06_rollback_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    receipt_path: Annotated[
        Path, typer.Option("--receipt", exists=True, dir_okay=False, readable=True)
    ],
) -> None:
    """Restore the backed-up registry while the migration receipt matches."""

    try:
        result = rollback_v06_migration(workspace, receipt_path)
    except (V06MigrationError, V07CompatibilityError, FileExistsError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"migration_id: {result.receipt.migration_id}")
    typer.echo(f"restored_registry_sha256: {result.receipt.restored_registry_sha256}")
    typer.echo(f"rollback_receipt: {result.receipt_path}")
    typer.echo(f"backup_preserved: {str(result.receipt.backup_preserved).lower()}")
    typer.echo("capability_status: planned")


@external_app.command("contract")
def external_contract_command(
    adapter: Annotated[str | None, typer.Option("--adapter")] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show OPS-05 interface policy and the versioned reference-adapter contracts."""

    catalogue = external_source_catalogue()
    selected = None
    if adapter is not None:
        selected = next(
            (item for item in catalogue.adapters if item.adapter_id == adapter),
            None,
        )
        if selected is None:
            supported = ", ".join(item.adapter_id for item in catalogue.adapters)
            typer.echo(
                f"unknown external-source adapter {adapter!r}; supported: {supported}", err=True
            )
            raise typer.Exit(code=1)
    if output_format == "json":
        payload = (
            selected.model_dump_json(indent=2) if selected else catalogue.model_dump_json(indent=2)
        )
        typer.echo(payload)
        return
    _require_text_format(output_format)
    if selected is not None:
        typer.echo(f"adapter: {selected.adapter_id}")
        typer.echo(f"adapter_version: {selected.adapter_version}")
        typer.echo(f"source_family: {selected.source_family}")
        typer.echo(f"conversion_level: {selected.conversion.level.value}")
        typer.echo(f"contract_fingerprint: {selected.fingerprint()}")
        typer.echo("required_markers:")
        for marker in selected.discovery_markers:
            if marker.required:
                typer.echo(f"  - {marker.relative_path} ({marker.kind.value})")
        typer.echo("blockers:")
        for blocker in selected.blockers:
            typer.echo(f"  - {blocker.code}: {blocker.reason}")
        return
    typer.echo(f"capability: {catalogue.capability_id}")
    typer.echo(f"contract_version: {catalogue.contract_version}")
    typer.echo(f"adapters: {len(catalogue.adapters)}")
    for item in catalogue.adapters:
        typer.echo(f"  {item.adapter_id}: {item.source_family} [{item.conversion.level.value}]")
    typer.echo(f"catalogue_fingerprint: {catalogue.fingerprint()}")


@external_app.command("discover")
def external_discover_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Shallow-discover registered external sources without parsing or mutation."""

    report = discover_external_sources(path)
    if output_format == "json":
        typer.echo(report.model_dump_json(indent=2))
    elif output_format == "text":
        typer.echo(f"source_label: {report.source_label}")
        typer.echo(f"status: {report.status.value}")
        typer.echo("candidate_adapters: " + (", ".join(report.candidate_adapter_ids) or "none"))
        for result in report.results:
            typer.echo(f"{result.adapter_id}: {result.status.value} - {result.detail}")
        typer.echo(f"fingerprint: {report.fingerprint()}")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    if report.status is not DiscoveryReportStatus.ONE_MATCH:
        raise typer.Exit(code=1)


@external_app.command("inspect")
def external_inspect_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    adapter: Annotated[str | None, typer.Option("--adapter")] = None,
    deep: Annotated[bool, typer.Option("--deep/--shallow")] = False,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Validate one selected source through the portable read-only OPS-05 interface."""

    try:
        inspection = inspect_external_source(path, adapter_id=adapter, deep=deep)
    except (ExternalSourceError, OSError, TosPackageError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(inspection.model_dump_json(indent=2))
    elif output_format == "text":
        typer.echo(f"source_label: {inspection.source_label}")
        typer.echo(f"adapter: {inspection.adapter_id}")
        typer.echo(f"validation: {inspection.validation.outcome.value}")
        typer.echo(
            f"accepted_for_declared_import: {inspection.validation.accepted_for_declared_import}"
        )
        typer.echo(
            f"source_fingerprint: {inspection.validation.source_fingerprint or 'unavailable'}"
        )
        typer.echo(f"conversion_level: {inspection.conversion.level.value}")
        typer.echo("provenance:")
        for item in inspection.observed_provenance:
            typer.echo(f"  {item.key}: {item.status.value}")
        typer.echo("blockers:")
        for blocker in inspection.blockers:
            typer.echo(f"  - {blocker.code}")
        typer.echo(f"inspection_fingerprint: {inspection.fingerprint()}")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    if inspection.validation.outcome in {
        ValidationOutcome.REJECTED,
        ValidationOutcome.UNAVAILABLE,
    }:
        raise typer.Exit(code=1)


@sumo_app.command("contract")
def sumo_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the explicit SUMO XML mapping and unsupported capabilities."""

    contract = sumo_source_contract()
    if output_format == "json":
        typer.echo(contract.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"adapter_version: {contract.adapter_version}")
    typer.echo(f"supported_sumo_versions: {', '.join(contract.supported_sumo_versions)}")
    typer.echo(f"direct_launch: {contract.capabilities.supports.direct_launch.value}")
    typer.echo("mappings:")
    for mapping in contract.mappings:
        typer.echo(
            f"  {mapping.source} -> {mapping.destination or 'source-only'} [{mapping.status}]"
        )
    typer.echo("unsupported:")
    for item in contract.unsupported:
        typer.echo(f"  - {item}")


@manifest_app.command("infer")
def manifest_infer_command(
    source: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
) -> None:
    """Create a non-executable mapping draft from bounded CSV evidence."""

    draft = infer_manifest(source)
    if output_format == "json":
        payload = draft.to_json()
    elif output_format == "yaml":
        payload = draft.to_yaml()
    elif output_format == "text":
        if output is not None:
            typer.echo("--output requires --format json or yaml", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"source_label: {draft.source_label}")
        typer.echo(f"source_fingerprint: {draft.source_fingerprint or 'unavailable'}")
        typer.echo(f"draft_fingerprint: {draft.draft_fingerprint or 'unavailable'}")
        typer.echo("analysis_ready: false")
        typer.echo("confirmation_required: true")
        for file in draft.files:
            typer.echo(
                f"{file.path}: {file.status.value}; "
                f"suggested_kind={file.suggested_kind or 'unresolved'}"
            )
        for finding in draft.findings:
            typer.echo(f"{finding.severity.value}: {finding.code.value}: {finding.message}")
        return
    else:
        typer.echo("only --format text, json, or yaml is supported", err=True)
        raise typer.Exit(code=1)
    if output is None:
        typer.echo(payload)
    else:
        _write_manifest_inference_output(output, payload, overwrite=False)
        typer.echo(f"draft: {output}")


@manifest_app.command("contract")
def manifest_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the deterministic inference catalogue, bounds, and unsupported behavior."""

    contract = manifest_inference_contract()
    if output_format == "json":
        typer.echo(contract.to_json())
    elif output_format == "yaml":
        typer.echo(contract.to_yaml())
    elif output_format == "text":
        typer.echo(f"inference_version: {contract.inference_version}")
        typer.echo(f"max_files: {contract.limits.max_files}")
        typer.echo(f"max_columns_per_file: {contract.limits.max_columns_per_file}")
        typer.echo(f"max_sample_rows_per_file: {contract.limits.max_sample_rows_per_file}")
        typer.echo("methods:")
        for method in contract.methods:
            typer.echo(f"  {method.method.value}: {method.precedence} - {method.meaning}")
        typer.echo(f"score_semantics: {contract.score_semantics}")
        typer.echo("confirmation_required: true")
    else:
        typer.echo("only --format text, json, or yaml is supported", err=True)
        raise typer.Exit(code=1)


@manifest_app.command("confirm")
def manifest_confirm_command(
    draft_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    source: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    confirmed_by: Annotated[str, typer.Option("--confirmed-by")],
    accept_suggestions: Annotated[bool, typer.Option("--accept-suggestions")] = False,
    kinds: Annotated[list[str] | None, typer.Option("--kind")] = None,
    mappings: Annotated[list[str] | None, typer.Option("--map")] = None,
    unmap: Annotated[list[str] | None, typer.Option("--unmap")] = None,
    units: Annotated[list[str] | None, typer.Option("--unit")] = None,
    exclude: Annotated[list[str] | None, typer.Option("--exclude")] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Explicitly accept/edit a draft and emit a confirmed mapping artifact."""

    try:
        draft = load_inference_draft(draft_path)
        selections = _manifest_inference_selections(
            kinds or [], mappings or [], unmap or [], units or [], exclude or []
        )
        confirmed = confirm_manifest_inference(
            draft,
            source,
            confirmed_by=confirmed_by,
            accept_suggestions=accept_suggestions,
            selections=selections,
        )
        _ensure_not_confirmed_source_csv(output, source, confirmed)
        _write_manifest_inference_output(output, confirmed.to_yaml(), overwrite=overwrite)
    except (ManifestInferenceError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"canonicalisation: {output}")
    typer.echo(f"confirmation_state: {confirmed.confirmation_state.value}")
    typer.echo(f"confirmation_fingerprint: {confirmed.confirmation_fingerprint}")
    typer.echo("analysis_ready: true")


@manifest_app.command("files")
def manifest_files_command(
    canonicalisation_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, readable=True)
    ],
    output_format: Annotated[str, typer.Option("--format")] = "yaml",
) -> None:
    """Render confirmed file declarations for inspection or manual manifest editing."""

    try:
        canonicalisation = load_canonicalisation_manifest(canonicalisation_path)
    except ManifestInferenceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    payload = {
        "files": {
            kind: declaration.model_dump(mode="json", exclude_none=True)
            for kind, declaration in canonicalisation.file_declarations().items()
        }
    }
    if output_format == "yaml":
        typer.echo(yaml.safe_dump(payload, sort_keys=False))
    elif output_format == "json":
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo("only --format json or yaml is supported", err=True)
        raise typer.Exit(code=1)


@manifest_app.command("apply")
def manifest_apply_command(
    canonicalisation_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, readable=True)
    ],
    template_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Apply confirmed mappings to a complete bundle-manifest metadata template."""

    try:
        canonicalisation = load_canonicalisation_manifest(canonicalisation_path)
        raw = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ManifestInferenceError("bundle manifest template must contain a mapping")
        manifest = apply_canonicalisation_to_template(canonicalisation, raw)
        _write_manifest_inference_output(
            output,
            bundle_manifest_to_yaml(manifest),
            overwrite=overwrite,
        )
    except (ManifestInferenceError, OSError, yaml.YAMLError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"manifest: {output}")
    typer.echo(f"bundle: {manifest.bundle.bundle_id}")
    typer.echo(f"confirmed_by: {canonicalisation.confirmed_by}")


@sumo_app.command("validate")
def sumo_validate_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Validate and canonicalise immutable tripinfo and summary XML outputs."""

    result = validate_sumo_results(path)
    if output_format == "json":
        typer.echo(result.to_json())
    elif output_format == "text":
        typer.echo(f"bundle: {result.report.bundle_id or 'unknown'}")
        typer.echo(f"run: {result.report.run_id or 'unknown'}")
        typer.echo(f"status: {result.report.status.value}")
        typer.echo(f"may_import: {result.report.may_import}")
        typer.echo(f"fingerprint: {result.fingerprint or 'unavailable'}")
        typer.echo(f"tripinfo_records: {len(result.trip_observations)}")
        typer.echo(f"canonical_trips: {len(result.canonical.trips)}")
        typer.echo(f"summary_steps: {len(result.summary_steps)}")
        for finding in result.report.findings:
            typer.echo(f"{finding.severity.value}: {finding.code.value}: {finding.message}")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    if not result.report.may_import:
        raise typer.Exit(code=1)


@sumo_app.command("metrics")
def sumo_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Compute deterministic canonical trip metrics from accepted SUMO outputs."""

    result = validate_sumo_results(path)
    if result.manifest is None or not result.report.may_import:
        typer.echo("SUMO result package rejected; metrics were not computed", err=True)
        raise typer.Exit(code=1)
    collection = compute_metrics_for_sumo(result)
    if output_format == "json":
        typer.echo(collection.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"run: {collection.run_id}")
    typer.echo(f"metric_version: {collection.metric_version}")
    for key in (
        "trip.records.count",
        "trip.completed.count",
        "trip.incomplete.count",
        "trip.completion.rate",
        "trip.duration.mean_s",
        "trip.duration.p95_s",
    ):
        metric = collection.by_key()[key]
        typer.echo(f"{key}: {metric.value if metric.value is not None else metric.status.value}")


@sumo_app.command("import")
def sumo_import_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False, writable=True)],
) -> None:
    """Register accepted SUMO results and their deterministic canonical metrics."""

    try:
        result = import_sumo_results(path, registry)
    except RegistryConflictError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"bundle: {result.bundle_id or 'unknown'}")
    typer.echo(f"run: {result.run_id or 'unknown'}")
    typer.echo(f"status: {result.status}")
    typer.echo(f"created: {result.created}")
    typer.echo(f"idempotent: {result.idempotent}")
    typer.echo(f"metrics_stored: {result.metrics_stored}")
    typer.echo(result.message)
    if result.status == "rejected":
        raise typer.Exit(code=1)


@sumo_app.command("execute-and-import")
def sumo_execute_and_import_command(
    preset: Annotated[SumoExecutionPreset, typer.Option("--preset")],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False)],
    timeout_seconds: Annotated[int, typer.Option("--timeout-seconds", min=1, max=600)] = 120,
) -> None:
    """Preflight, execute, validate, and import one closed SUMO preset in the foreground."""

    try:
        workflow = SumoWorkflowRequest(
            preset=preset,
            output_dir=str(output),
            registry_path=str(registry),
            timeout_seconds=timeout_seconds,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    definition = preset_definition(preset)
    runtime = sumo_runtime_status()
    typer.echo(f"preset: {preset.value}")
    typer.echo(f"simulated_window_s: {definition.begin_s}..{definition.end_s}")
    typer.echo(f"vehicles: {definition.vehicle_count}")
    typer.echo(f"sumo_available: {runtime.available}")
    typer.echo(f"sumo_supported: {runtime.supported}")
    typer.echo(f"sumo_version: {runtime.version or 'unavailable'}")
    typer.echo(f"runtime: {runtime.reason}")
    typer.echo("state: validating")
    receipt = execute_and_import_sumo(workflow)
    for stage in receipt.stages:
        typer.echo(f"{stage.stage.value}: {stage.state.value} - {stage.detail}")
    typer.echo(f"workflow: {receipt.status.value}")
    if receipt.receipt_fingerprint is not None:
        typer.echo(f"receipt_fingerprint: {receipt.receipt_fingerprint}")
    if receipt.import_outcome is not None:
        outcome = receipt.import_outcome
        typer.echo(f"registry_run_id: {outcome.run_id}")
        typer.echo(f"import_created: {outcome.created}")
        typer.echo(f"import_idempotent: {outcome.idempotent}")
        typer.echo(f"metrics_stored: {outcome.metrics_stored}")
    if receipt.import_record_stable_fingerprint is not None:
        typer.echo(f"import_stable_fingerprint: {receipt.import_record_stable_fingerprint}")
    if receipt.status is not SumoWorkflowStatus.COMPLETED_IMPORTED:
        for finding in receipt.findings:
            typer.echo(f"finding: {finding}", err=True)
        raise typer.Exit(code=1)


@sumo_app.command("import-result")
def sumo_import_result_command(
    result_dir: Annotated[Path, typer.Option("--result-dir", exists=True, file_okay=False)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False)],
) -> None:
    """Re-validate one published controlled SUMO result and import it idempotently."""

    try:
        record, outcome, validation = import_sumo_execution(result_dir, registry)
    except (OSError, SumoExecutionError, RegistryConflictError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"preset: {record.preset.value}")
    typer.echo(f"adapter_validation: {validation.report.status.value}")
    typer.echo(f"registry_run_id: {outcome.run_id}")
    typer.echo(f"import_created: {outcome.created}")
    typer.echo(f"import_idempotent: {outcome.idempotent}")
    typer.echo(f"import_stable_fingerprint: {record.stable_fingerprint()}")
    typer.echo(f"synthetic: {record.synthetic}")


@tos_app.command("inspect")
def tos_inspect_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    deep: Annotated[bool, typer.Option("--deep/--shallow")] = False,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect TOS artifacts without registry mutation."""

    report = validate_tos_package(path, deep=deep)
    if output_format == "json":
        typer.echo(report.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    inventory = report.inventory
    typer.echo(f"status: {report.status.value}")
    typer.echo(f"may_import_summaries: {report.may_import_summaries}")
    typer.echo(f"package_fingerprint: {report.package_fingerprint or 'unavailable'}")
    typer.echo(f"package_commit: {report.package_commit or 'unavailable'}")
    typer.echo(f"evaluation_rows: {inventory.evaluation_rows}")
    typer.echo(f"perstep_files: {inventory.perstep_files}")
    typer.echo(f"pertask_files: {inventory.pertask_files}")
    typer.echo(f"trace_files: {inventory.trace_files}")
    for finding in report.findings:
        typer.echo(f"{finding.severity.value}: {finding.code}: {finding.message}")


@tos_app.command("contract")
def tos_contract_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the evidence-backed vec_env field, control, and execution contract."""

    contract = tos_source_contract()
    if output_format == "json":
        typer.echo(contract.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"adapter_version: {contract.adapter_version}")
    typer.echo(f"semantics_evidence_commit: {contract.evidence_commit}")
    typer.echo(f"direct_launch: {contract.execution.direct_launch.value}")
    typer.echo(f"execution_status: {contract.execution.status.value}")
    typer.echo("confirmed_fields:")
    for field in contract.fields:
        typer.echo(f"  {field.field}: {field.meaning} [{field.unit or 'no unit'}]")
    typer.echo("launch_blockers:")
    for blocker in contract.execution.blockers:
        typer.echo(f"  - {blocker}")


@tos_app.command("validate")
def tos_validate_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Deep-validate the documented TOS package contracts."""

    report = validate_tos_package(path, deep=True)
    if output_format == "json":
        typer.echo(report.to_json())
    elif output_format == "text":
        typer.echo(f"status: {report.status.value}")
        typer.echo(f"may_import_summaries: {report.may_import_summaries}")
        typer.echo(f"findings: {len(report.findings)}")
        for finding in report.findings:
            typer.echo(f"{finding.severity.value}: {finding.code}: {finding.message}")
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    if not report.may_import_summaries:
        raise typer.Exit(code=1)


@tos_app.command("runs")
def tos_runs_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 25,
) -> None:
    """List documented evaluation runs and instrumented run availability."""

    rows = read_evaluation_runs(path)
    instrumented = set(list_instrumented_runs(path))
    typer.echo(f"evaluation_runs: {len(rows)}")
    typer.echo(f"instrumented_runs: {len(instrumented)}")
    for row in rows[:limit]:
        instrumented_key = instrumented_key_for_run(row)
        instrumented_available = instrumented_key in instrumented
        instrumented_reference = (
            f" instrumented_key={instrumented_key}" if instrumented_available else ""
        )
        typer.echo(
            f"{row.run_id} completion={row.completion:.6f} "
            f"instrumented={instrumented_available}{instrumented_reference}"
        )


@tos_app.command("import")
def tos_import_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    registry: Annotated[Path, typer.Option("--registry", dir_okay=False, writable=True)],
) -> None:
    """Import validated source summaries into the TrafficTwin registry."""

    try:
        report = validate_tos_package(path, deep=True)
        result = import_evaluation_summaries(
            path,
            registry,
            validation_report=report,
        )
    except (TosPackageError, RegistryConflictError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"registry: {result.registry_reference}")
    typer.echo(f"experiments_created: {result.experiments_created}")
    typer.echo(f"experiments_existing: {result.experiments_existing}")
    typer.echo(f"runs_created: {result.runs_created}")
    typer.echo(f"runs_existing: {result.runs_existing}")
    typer.echo(f"metric_collections_stored: {result.metric_collections_stored}")
    typer.echo(f"evidence_packs_stored: {result.evidence_packs_stored}")


@tos_app.command("metrics")
def tos_metrics_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_id: Annotated[str, typer.Argument(help="TrafficTwin run ID or source artifact key")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect explicitly source-provided metrics for one evaluation run."""

    report = validate_tos_package(path, deep=False)
    row = _tos_row(path, run_id)
    if report.package_fingerprint is None:
        typer.echo("package fingerprint unavailable", err=True)
        raise typer.Exit(code=1)
    collection = metric_collection_from_evaluation(row, report.package_fingerprint)
    if output_format == "json":
        typer.echo(collection.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run: {row.run_id}")
    typer.echo(f"metric_version: {collection.metric_version}")
    for key in (
        "tos.task.deadline_success.rate",
        "tos.task.deadline_success.rate_by_class",
        "task.latency.mean_ms",
        "task.offload.rate",
    ):
        metric = collection.by_key()[key]
        typer.echo(f"{key}: {metric.value}")
    typer.echo(f"unavailable_metrics: {collection.unavailable_count}")


@tos_app.command("replay")
def tos_replay_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    index: Annotated[int, typer.Option("--index", min=0)] = 0,
    max_vehicles: Annotated[int, typer.Option("--max-vehicles", min=1, max=1000)] = 25,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect one deterministic historical replay frame."""

    try:
        frame = load_replay_frame(path, run_key, index, max_vehicles=max_vehicles)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(frame.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run_key: {frame.run_key}")
    typer.echo(f"time: {frame.point.timestamp_s}")
    typer.echo(f"arrivals: {frame.point.arrivals}")
    typer.echo(f"deadline_met: {frame.point.deadline_met}")
    typer.echo(f"active_vehicle_slots: {frame.total_active_vehicle_slots}")
    typer.echo(f"displayed_vehicle_slots: {len(frame.vehicles)}")
    typer.echo(f"rsu_source_rows: {len(frame.rsus)}")


@tos_app.command("rsu-series")
def tos_rsu_series_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    stride: Annotated[int, typer.Option("--stride", min=1)] = 1,
    limit: Annotated[int, typer.Option("--limit", min=1, max=10000)] = 250,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect bounded RSU active-task pressure and compute backlog history."""

    try:
        points = load_rsu_replay_series(path, run_key, stride=stride)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    selected = points[:limit]
    if output_format == "json":
        typer.echo(
            json.dumps(
                [point.model_dump(mode="json") for point in selected],
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run_key: {run_key}")
    typer.echo(f"total_points: {len(points)}")
    typer.echo(f"displayed_points: {len(selected)}")
    typer.echo("pressure_semantics: in_flight_tasks / maximum_concurrent_tasks")
    typer.echo("warning: concurrency pressure is not CPU utilisation")
    for point in selected:
        typer.echo(
            f"t={point.timestamp_s:g} {point.rsu_reference} "
            f"active={point.active_task_count} backlog_ms="
            f"{point.remaining_compute_backlog_ms:g} "
            f"pressure={point.concurrency_pressure_fraction:.6f}"
        )


@tos_app.command("task-sample")
def tos_task_sample_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    limit: Annotated[int, typer.Option("--limit", min=1, max=10000)] = 25,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect a bounded per-arrival showcase sample."""

    try:
        sample = load_task_sample(path, run_key, limit=limit)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(sample.model_dump_json(indent=2))
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run_key: {sample.run_key}")
    typer.echo(f"active_entries: {sample.total_active_entries}")
    typer.echo(f"sampled_entries: {len(sample.observations)}")
    typer.echo(f"deadline_consistency_verified: {sample.deadline_consistency_verified}")
    for observation in sample.observations:
        typer.echo(
            f"{observation.source_index} {observation.task_class.value} "
            f"deadline_met={observation.deadline_met} latency_ms={observation.latency_ms:.3f}"
        )


@tos_app.command("diagnose")
def tos_diagnose_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_id: Annotated[str, typer.Argument(help="TrafficTwin run ID or source artifact key")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Evaluate existing rules over an explicitly partial TOS EvidencePack."""

    report = validate_tos_package(path, deep=False)
    row = _tos_row(path, run_id)
    if report.package_fingerprint is None:
        typer.echo("package fingerprint unavailable", err=True)
        raise typer.Exit(code=1)
    collection = metric_collection_from_evaluation(row, report.package_fingerprint)
    pack = build_tos_evidence_pack(row, report, collection)
    diagnosis = evaluate_rules(pack)
    if output_format == "json":
        typer.echo(diagnosis.to_json())
        return
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"run: {row.run_id}")
    typer.echo(f"readiness: {diagnosis.overall_readiness.value}")
    for result in diagnosis.results:
        typer.echo(f"{result.rule_id}: {result.status.value}")


@tos_app.command("provenance")
def tos_provenance_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_id: Annotated[str, typer.Argument(help="TrafficTwin run ID or source artifact key")],
    root_type: Annotated[str, typer.Option("--root-type")] = "metric",
    root_id: Annotated[str, typer.Option("--root-id")] = "tos.task.deadline_success.rate",
    output_format: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Export aggregate-level metric or rule provenance for a TOS run."""

    report = validate_tos_package(path, deep=False)
    row = _tos_row(path, run_id)
    if report.package_fingerprint is None:
        typer.echo("package fingerprint unavailable", err=True)
        raise typer.Exit(code=1)
    collection = metric_collection_from_evaluation(row, report.package_fingerprint)
    if root_type == "metric":
        trace = build_tos_metric_trace(row, collection, report, root_id)
    elif root_type == "rule":
        pack = build_tos_evidence_pack(row, report, collection)
        diagnosis = evaluate_rules(pack)
        trace = build_tos_rule_trace(row, pack, diagnosis, report, root_id)
    else:
        typer.echo("--root-type must be metric or rule", err=True)
        raise typer.Exit(code=1)
    _emit_provenance_trace(trace, output_format)


@tos_app.command("matrix")
def tos_matrix_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    measure: Annotated[str, typer.Option("--measure")] = "tos.task.deadline_success.rate",
    fleet: Annotated[str, typer.Option("--fleet")] = "uk2030",
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Build the deterministic source evaluation matrix."""

    try:
        matrix = build_evaluation_matrix(
            read_evaluation_runs(path), path, measure_key=measure, evaluation_fleet=fleet
        )
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(matrix.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"measure: {matrix.measure.key}")
    typer.echo(f"evaluation_fleet: {matrix.evaluation_fleet}")
    typer.echo(f"campaigns: {len(matrix.campaigns)}")
    typer.echo(f"cells: {len(matrix.cells)}")
    for entry in matrix.entries:
        typer.echo(
            f"{entry.campaign} {entry.cell} n={entry.statistics.n} "
            f"mean={_optional_number(entry.statistics.mean)} "
            f"sample_sd={_optional_number(entry.statistics.sample_sd)}"
        )


@tos_app.command("compare-campaigns")
def tos_compare_campaigns_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    baseline: Annotated[str, typer.Argument()],
    variation: Annotated[str, typer.Argument()],
    measure: Annotated[str, typer.Option("--measure")] = "tos.task.deadline_success.rate",
    fleet: Annotated[str, typer.Option("--fleet")] = "uk2030",
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Compare two campaigns using common fleet seeds within each source cell."""

    try:
        report = compare_campaigns(
            read_evaluation_runs(path),
            path,
            baseline,
            variation,
            evaluation_fleet=fleet,
            measure_keys=[measure],
        )
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(report.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"comparison: {baseline} -> {variation}")
    typer.echo("delta_definition: variation - baseline")
    for item in report.comparisons:
        typer.echo(
            f"{item.cell} paired_n={item.paired_difference_statistics.n} "
            f"mean_delta={_optional_number(item.paired_difference_statistics.mean)}"
        )


@tos_app.command("generalisation")
def tos_generalisation_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show evidenced in-domain, held-out, and unknown source relationships."""

    matrix = build_generalisation_matrix(read_evaluation_runs(path), path)
    if output_format == "json":
        typer.echo(matrix.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    for entry in matrix.entries:
        typer.echo(f"{entry.campaign} {entry.cell}: {entry.evaluation_domain.value}")


@tos_app.command("training-runs")
def tos_training_runs_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    limit: Annotated[int, typer.Option("--limit", min=1, max=1000)] = 100,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """List source training histories and matched greedy summaries."""

    runs = list_training_runs(path)[:limit]
    if output_format == "json":
        typer.echo(
            json.dumps(
                [run.model_dump(mode="json") for run in runs],
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return
    _require_text_format(output_format)
    typer.echo(f"training_runs: {len(runs)}")
    for run in runs:
        typer.echo(
            f"{run.training_id} points={run.point_count} "
            f"final_completion={_optional_number(run.final_mean_completion)}"
        )


@tos_app.command("training")
def tos_training_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    training_id: Annotated[str, typer.Argument()],
    max_points: Annotated[int, typer.Option("--max-points", min=2, max=10000)] = 800,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Inspect one bounded source training curve."""

    try:
        run = load_training_run(path, training_id, max_points=max_points)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(run.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"training_id: {run.summary.training_id}")
    typer.echo(f"source_points: {run.summary.point_count}")
    typer.echo(f"displayed_points: {len(run.points)}")
    typer.echo(f"warmup_unavailable: {run.summary.warmup_unavailable_count}")
    typer.echo(f"greedy_summary: {run.greedy_evaluation is not None}")


@tos_app.command("trace-summary")
def tos_trace_summary_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    trace_name: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Summarise a processed FCD mobility trace."""

    try:
        summary = summarise_trace(path, trace_name)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(summary.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"trace: {summary.trace_file}")
    typer.echo(f"timeline_points: {summary.timeline_point_count}")
    typer.echo(f"active_slot_observations: {summary.observation_count}")
    typer.echo(f"mean_speed_mps: {_optional_number(summary.speed_mps.mean)}")
    typer.echo("warning: processed SUMO FCD simulation; no trip outputs")


@tos_app.command("rsu-summary")
def tos_rsu_summary_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Summarise source RSU concurrency pressure and compute backlog."""

    try:
        summary = summarise_rsu_run(path, run_key)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(summary.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"run_key: {summary.run_key}")
    typer.echo(f"rsus: {len(summary.rsus)}")
    typer.echo(f"maximum_concurrent_tasks: {summary.maximum_concurrent_tasks}")
    for rsu in summary.rsus:
        typer.echo(
            f"{rsu.rsu_reference} mean_pressure="
            f"{_optional_number(rsu.concurrency_pressure_fraction.mean)} "
            f"max_pressure={_optional_number(rsu.concurrency_pressure_fraction.maximum)}"
        )


@tos_app.command("task-summary")
def tos_task_summary_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    run_key: Annotated[str, typer.Argument()],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Aggregate one complete per-task showcase array."""

    try:
        summary = summarise_task_outcomes(path, run_key)
    except (TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(summary.model_dump_json(indent=2))
        return
    _require_text_format(output_format)
    typer.echo(f"run_key: {summary.run_key}")
    typer.echo(f"tasks: {summary.task_count}")
    typer.echo(f"deadline_success_rate: {_optional_number(summary.deadline_success_rate)}")
    typer.echo(f"latency_p50_ms: {_optional_number(summary.latency_ms.p50)}")
    typer.echo(f"deadline_consistency_verified: {summary.deadline_consistency_verified}")


@tos_app.command("audit")
def tos_audit_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Audit package reproducibility and artifact coverage."""

    audit = audit_tos_package(path)
    if output_format == "json":
        typer.echo(audit.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"package_fingerprint: {audit.package_fingerprint}")
    typer.echo(f"evaluation_runs: {audit.evaluation_run_count}")
    typer.echo(f"training_histories: {audit.training_history_count}")
    for check in audit.checks:
        typer.echo(f"{check.status.value}: {check.code}: {check.message}")


@tos_app.command("readiness")
def tos_readiness_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
    fixture_permission_confirmed: Annotated[
        bool, typer.Option("--confirm-fixture-permission")
    ] = False,
    publication_permission_confirmed: Annotated[
        bool, typer.Option("--confirm-publication-permission")
    ] = False,
) -> None:
    """Report evidence and permission gates for deeper TOS integration."""

    readiness = build_tos_integration_readiness(
        path,
        fixture_permission=True if fixture_permission_confirmed else None,
        publication_permission=True if publication_permission_confirmed else None,
    )
    if output_format == "json":
        typer.echo(readiness.to_json())
        return
    _require_text_format(output_format)
    typer.echo(f"overall_status: {readiness.overall_status.value}")
    typer.echo(f"package_fingerprint: {readiness.package_fingerprint}")
    for capability, status in sorted(readiness.capabilities.items()):
        typer.echo(f"{capability}: {status.value}")
    for gate in readiness.gates:
        typer.echo(f"{gate.status.value}: {gate.gate_id}: {gate.title}")


@tos_app.command("report")
def tos_report_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    variation: Annotated[str, typer.Option("--variation")] = "ukfleettrain_mappo",
) -> None:
    """Write a deterministic imported-simulation research report."""

    report = build_tos_research_report(path, variation_campaign=variation)
    _write_report_payload(report, output)


@tos_app.command("atlas")
def tos_atlas_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
) -> None:
    """Write a self-contained aggregate-only static results atlas."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_static_results_atlas(path), encoding="utf-8")
    typer.echo(f"atlas: {output}")
    typer.echo("publication_permission_required: true")


@tos_app.command("results-pack")
def tos_results_pack_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    variation: Annotated[str, typer.Option("--variation")] = "ukfleettrain_mappo",
) -> None:
    """Write report, matrix, comparison, audit, and static atlas artifacts."""

    try:
        pack = write_tos_results_pack(path, output, variation_campaign=variation)
    except (FileExistsError, TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"results_pack: {pack.directory}")
    typer.echo(f"report: {pack.markdown_report.name}")
    typer.echo(f"atlas: {pack.atlas_html.name}")
    typer.echo("publication_permission_required: true")


@tos_app.command("supervisor-pack")
def tos_supervisor_pack_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    variation: Annotated[str, typer.Option("--variation")] = "ukfleettrain_mappo",
) -> None:
    """Write a checksummed private supervisor and viva evidence pack."""

    try:
        pack = write_tos_supervisor_pack(path, output, variation_campaign=variation)
    except (FileExistsError, OSError, PermissionError, TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"supervisor_pack: {pack.directory}")
    typer.echo(f"manifest: {pack.manifest.name}")
    typer.echo(f"checksums: {pack.checksums.name}")
    typer.echo("classification: private_research_material")
    typer.echo("publication_permission_required: true")


@tos_app.command("stage-public-atlas")
def tos_stage_public_atlas_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", file_okay=False)],
    publication_permission_confirmed: Annotated[
        bool, typer.Option("--confirm-publication-permission")
    ] = False,
) -> None:
    """Stage the aggregate TOS atlas after explicit publication permission."""

    try:
        index = stage_public_tos_atlas(
            path,
            output,
            publication_permission_confirmed=publication_permission_confirmed,
        )
    except (FileExistsError, OSError, PermissionError, TosPackageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"public_atlas: {index}")
    typer.echo("publication_permission_attested: true")


def _require_text_format(output_format: str) -> None:
    if output_format != "text":
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)


def _emit_cache_status(status: CanonicalCacheStatus) -> None:
    typer.echo(f"cache_state: {status.state.value}")
    typer.echo(f"cache_key: {status.cache_key or 'unavailable'}")
    typer.echo(f"cache_entry: {status.cache_entry or 'unavailable'}")
    typer.echo(f"verified_files: {status.verified_files}")
    typer.echo(
        "canonical_record_counts: "
        + (json.dumps(status.record_counts, sort_keys=True) if status.record_counts else "none")
    )
    typer.echo(f"cache_detail: {status.detail}")


def _manifest_inference_selections(
    kinds: list[str],
    mappings: list[str],
    unmapped: list[str],
    units: list[str],
    excluded: list[str],
) -> ManifestInferenceSelections:
    files: dict[str, FileSelection] = {path: FileSelection(include=False) for path in excluded}
    try:
        for item in kinds:
            path, kind = _split_simple_assignment(item, "--kind")
            selection = files.setdefault(path, FileSelection())
            selection.kind = kind
        for item in mappings:
            path, canonical_field, source_column = _split_field_assignment(item, "--map")
            selection = files.setdefault(path, FileSelection())
            selection.column_map[canonical_field] = source_column
        for item in unmapped:
            path, canonical_field = _split_qualified_field(item, "--unmap")
            selection = files.setdefault(path, FileSelection())
            selection.unmapped_fields.append(canonical_field)
        for item in units:
            path, canonical_field, unit = _split_field_assignment(item, "--unit")
            selection = files.setdefault(path, FileSelection())
            selection.units[canonical_field] = unit
    except ValueError as exc:
        raise ManifestInferenceError(str(exc)) from exc
    return ManifestInferenceSelections(files=files)


def _split_simple_assignment(value: str, option: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"{option} expects KEY=VALUE")
    key, selected = value.split("=", maxsplit=1)
    if not key or not selected:
        raise ValueError(f"{option} expects non-empty KEY=VALUE")
    return key, selected


def _split_field_assignment(value: str, option: str) -> tuple[str, str, str]:
    key, selected = _split_simple_assignment(value, option)
    path, field = _split_qualified_field(key, option)
    return path, field, selected


def _split_qualified_field(value: str, option: str) -> tuple[str, str]:
    key = value
    if ":" not in key:
        raise ValueError(f"{option} expects FILE:FIELD")
    path, field = key.rsplit(":", maxsplit=1)
    if not path or not field:
        raise ValueError(f"{option} expects FILE:FIELD")
    return path, field


def _write_manifest_inference_output(output: Path, payload: str, *, overwrite: bool) -> None:
    if output.exists() and not overwrite:
        raise ManifestInferenceError(f"output already exists: {output}; use --overwrite")
    output.write_text(payload, encoding="utf-8")


def _ensure_not_confirmed_source_csv(
    output: Path,
    source: Path,
    canonicalisation: CanonicalisationManifest,
) -> None:
    output_resolved = output.resolve()
    source_files = {(source / mapping.path).resolve() for mapping in canonicalisation.mappings}
    if output_resolved in source_files:
        raise ManifestInferenceError("output cannot overwrite a confirmed immutable source CSV")


def _optional_number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6f}"


def _collection_from_identifier(
    identifier: str,
    registry_path: Path | None,
) -> tuple[MetricCollection, ScenarioSeed | None]:
    path = Path(identifier)
    if path.exists():
        result = validate_bundle(path)
        _ensure_metric_context_available(result)
        return compute_metrics_for_bundle(result), result.seed
    if registry_path is None:
        typer.echo(f"path not found and --registry not provided: {identifier}", err=True)
        raise typer.Exit(code=1)
    try:
        payload = Registry(registry_path).get_metric_collection_json(identifier)
    except RegistryNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    return MetricCollection.model_validate_json(payload), None


def _experiment_collections(registry_path: Path, experiment_id: str) -> list[MetricCollection]:
    """Load stored metric collections explicitly belonging to an experiment."""

    return [
        collection
        for payload in Registry(registry_path).list_metric_collection_json()
        if (collection := MetricCollection.model_validate_json(payload)).results
        and collection.results[0].experiment_id == experiment_id
    ]


def _validate_statistical_study_selection(
    experiment: Experiment,
    baseline_seed_id: str,
    variation_seed_id: str,
    algorithm: str,
) -> None:
    """Require the CLI analysis selection to match the registered plan."""

    findings: list[str] = []
    if baseline_seed_id != experiment.baseline_seed_id:
        findings.append(
            f"baseline seed must match registered baseline {experiment.baseline_seed_id!r}"
        )
    if variation_seed_id not in experiment.variation_seed_ids:
        findings.append("variation seed is not declared by the registered experiment")
    if algorithm not in experiment.algorithms:
        findings.append("algorithm is not declared by the registered experiment")
    if not experiment.common_random_seed_set:
        findings.append("registered experiment has no common random-seed set")
    if findings:
        raise ValueError("; ".join(findings))


def _load_regression_subject(
    identifier: str,
    subject_kind: RegressionSubjectKind,
    registry_path: Path | None,
) -> RegressionSubject:
    """Load only the typed artifact family declared by the golden contract."""

    if subject_kind is RegressionSubjectKind.METRIC_COLLECTION:
        return _collection_from_identifier(identifier, registry_path)[0]
    path = Path(identifier)
    if not path.is_file():
        raise ValueError("a paired statistical-study regression subject must be a JSON file")
    return parse_statistical_study_json(path.read_bytes())


def _parse_regression_tolerance(value: str) -> RegressionToleranceSpec:
    """Parse one explicit SELECTOR=ABSOLUTE,RELATIVE CLI declaration."""

    selector, separator, raw_tolerances = value.partition("=")
    if not separator or not selector.strip():
        raise ValueError("--tolerance expects SELECTOR=ABSOLUTE,RELATIVE")
    fields = [field.strip() for field in raw_tolerances.split(",")]
    if len(fields) != 2 or any(not field for field in fields):
        raise ValueError("--tolerance expects SELECTOR=ABSOLUTE,RELATIVE")
    try:
        absolute, relative = (float(field) for field in fields)
    except ValueError as exc:
        raise ValueError("regression tolerances must be finite numbers") from exc
    return RegressionToleranceSpec(
        selector=selector,
        absolute_tolerance=absolute,
        relative_tolerance=relative,
    )


def _emit_or_write_json(payload: str, output: Path | None, *, label: str) -> None:
    """Emit JSON or write it to an explicitly requested file."""

    if output is None:
        typer.echo(payload)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    typer.echo(label)
    typer.echo(f"output: {output}")


def _provenance_completeness_payload(
    report: ProvenanceCompletenessReport,
    output_format: str,
) -> str:
    if output_format == "json":
        return report.to_json()
    if output_format == "csv":
        return provenance_completeness_report_to_csv(report)
    if output_format == "text":
        score = f"{report.score:.6f}" if report.score is not None else "unavailable"
        return (
            f"report_id: {report.report_id}\n"
            f"report_type: {report.report_type.value}\n"
            f"status: {report.overall_status.value}\n"
            f"score: {score}\n"
            f"denominator: {report.denominator_count}\n"
            f"source_row_complete: {report.source_row_complete_count}\n"
            f"aggregate_only: {report.aggregate_only_count}\n"
            f"unavailable: {report.unavailable_count}\n"
        )
    raise ProvenanceQueryError("output format must be one of: json, csv, text")


def _emit_batch_summary(
    summary: BatchBundleSummary,
    output_format: str,
    output: Path | None,
) -> None:
    """Render a batch summary in one of the documented deterministic formats."""

    if output_format == "text":
        payload = batch_summary_to_text(summary)
    elif output_format == "json":
        payload = summary.to_json()
    elif output_format == "csv":
        payload = batch_summary_to_csv(summary)
    else:
        typer.echo("only --format text, json, or csv is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="batch summary written")


def _streaming_config(
    chunk_rows: int,
    max_chunk_bytes: int,
    max_table_bytes: int,
    max_bundle_bytes: int,
) -> StreamingCanonicalisationConfig:
    try:
        return StreamingCanonicalisationConfig(
            chunk_rows=chunk_rows,
            max_chunk_bytes=max_chunk_bytes,
            max_table_uncompressed_bytes=max_table_bytes,
            max_bundle_uncompressed_bytes=max_bundle_bytes,
        )
    except ValueError as exc:
        typer.echo(f"invalid streaming configuration: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _emit_streaming_validation(
    result: StreamingBundleValidationResult,
    output_format: str,
    output: Path | None,
) -> None:
    if output_format == "json":
        payload = result.to_json()
    elif output_format == "text":
        payload = _streaming_validation_to_text(result)
    else:
        typer.echo("only --format text or json is supported", err=True)
        raise typer.Exit(code=1)
    _emit_or_write_json(payload, output, label="streaming validation summary written")


def _streaming_validation_to_text(result: StreamingBundleValidationResult) -> str:
    summary = result.streaming
    counts = ", ".join(f"{name}={count}" for name, count in summary.canonical_record_counts.items())
    return (
        f"bundle: {result.report.bundle_id or 'unknown'}\n"
        f"run: {result.report.run_id or 'unknown'}\n"
        f"status: {result.report.status.value}\n"
        f"may_import: {result.report.may_import}\n"
        f"chunks: {summary.chunk_count}\n"
        f"chunk_rows_limit: {summary.config.chunk_rows}\n"
        f"max_observed_chunk_rows: {summary.max_observed_chunk_source_rows}\n"
        f"max_observed_chunk_bytes: {summary.max_observed_chunk_decoded_bytes}\n"
        f"canonical_records: {counts}\n"
    )


def _windowed_metric_config(
    width_s: float,
    alignment_origin_s: float,
    analysis_start_s: float | None,
    analysis_end_s: float | None,
    partial_windows: str,
    max_windows: int,
) -> WindowedMetricConfig:
    try:
        return WindowedMetricConfig(
            width_s=width_s,
            alignment_origin_s=alignment_origin_s,
            analysis_start_s=analysis_start_s,
            analysis_end_s=analysis_end_s,
            partial_window_policy=PartialWindowPolicy(partial_windows),
            max_windows=max_windows,
        )
    except ValueError as exc:
        typer.echo(f"invalid window configuration: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _windowed_metric_series_to_text(series: WindowedMetricSeries) -> str:
    return (
        f"run: {series.run_id}\n"
        f"status: {series.status.value}\n"
        f"boundary: {series.boundary}\n"
        f"width_s: {series.config.width_s}\n"
        f"alignment_origin_s: {series.config.alignment_origin_s}\n"
        f"range_source: {series.range_source.value}\n"
        f"analysis_range_s: {series.analysis_start_s} to {series.analysis_end_s}\n"
        f"included_windows: {series.included_window_count}\n"
        f"excluded_partial_windows: {series.excluded_partial_window_count}\n"
        f"included_empty_windows: {series.included_empty_window_count}\n"
        f"applicable_metrics: {len(series.applicable_metric_keys)}\n"
    )


def _tos_row(path: Path, identifier: str) -> TosEvaluationRun:
    rows = read_evaluation_runs(path)
    for row in rows:
        if identifier in {row.run_id, row.source_key, instrumented_key_for_run(row)}:
            return row
    typer.echo(f"TOS evaluation run not found: {identifier}", err=True)
    raise typer.Exit(code=1)


def _ensure_metric_context_available(result: BundleValidationResult) -> None:
    if result.manifest is None:
        report = result.report
        typer.echo(
            f"bundle rejected: {report.status.value}; manifest is unavailable for metric context",
            err=True,
        )
        raise typer.Exit(code=1)


def _diagnostic_report_from_path(path: Path) -> DiagnosticReport:
    return evaluate_rules(_evidence_pack_from_path(path))


def _evidence_pack_from_path(path: Path) -> EvidencePack:
    """Build or load the exact EvidencePack boundary consumed by diagnostic rules."""

    if path.is_file() and path.suffix.lower() == ".json":
        return EvidencePack.model_validate_json(path.read_text(encoding="utf-8"))
    result = validate_bundle(path)
    _ensure_metric_context_available(result)
    collection = compute_metrics_for_bundle(result)
    return build_evidence_pack(result, collection)


def _r7_only_config(r7: R7Config) -> RuleSetConfig:
    return RuleSetConfig.model_validate(
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


def _r8_only_config(r8: R8Config) -> RuleSetConfig:
    return RuleSetConfig.model_validate(
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


def _rule_result_to_text(result: object) -> str:
    """Return a compact stable text projection for any typed RuleResult."""

    from traffictwin.rules.models import RuleResult

    if not isinstance(result, RuleResult):  # pragma: no cover - internal type guard
        raise TypeError("expected RuleResult")
    lines = [
        f"rule_id: {result.rule_id}",
        f"rule_version: {result.rule_version}",
        f"status: {result.status.value}",
        f"confidence: {result.confidence.value}",
        f"evidence_keys: {', '.join(result.evidence_keys) or 'none'}",
    ]
    if result.hypothesis:
        lines.append(f"hypothesis: {result.hypothesis}")
    lines.extend(f"missing_evidence: {item}" for item in result.missing_evidence)
    fingerprint = result.metadata.get("declarative_definition_fingerprint")
    if fingerprint is not None:
        lines.append(f"definition_fingerprint: {fingerprint}")
    return "\n".join(lines) + "\n"


def _nearest_flip_to_text(analysis: object) -> str:
    """Return a compact stable text projection for a typed nearest-flip artifact."""

    from traffictwin.diagnostics.sensitivity import NearestFlipAnalysis

    if not isinstance(analysis, NearestFlipAnalysis):  # pragma: no cover - internal type guard
        raise TypeError("expected NearestFlipAnalysis")
    lines = [
        f"analysis_id: {analysis.analysis_id}",
        f"rule_id: {analysis.rule_id}",
        f"status: {analysis.status.value}",
        f"reason_code: {analysis.reason_code.value}",
        f"source_status: {analysis.source_status.value if analysis.source_status else 'none'}",
        "candidate_status: "
        f"{analysis.candidate_status.value if analysis.candidate_status else 'none'}",
        f"tie_count: {analysis.tie_count}",
    ]
    for constraint in analysis.constraints:
        lines.append(
            "constraint: "
            f"{constraint.parameter_path} observed={constraint.observed_value} "
            f"required={constraint.required_minimum} satisfied={str(constraint.satisfied).lower()}"
        )
    for candidate in analysis.candidates:
        lines.append(
            "candidate: "
            f"{candidate.parameter_path} {candidate.current_value} -> {candidate.flip_value} "
            f"delta={candidate.absolute_delta} {candidate.unit}"
        )
    lines.extend(
        [
            f"fingerprint: {analysis.fingerprint()}",
            f"reason: {analysis.reason}",
        ]
    )
    return "\n".join(lines) + "\n"


def _emit_provenance_trace(trace: ProvenanceTrace, output_format: str) -> None:
    if output_format == "json":
        typer.echo(trace_to_json(trace))
        return
    if output_format == "markdown":
        typer.echo(trace_to_markdown(trace))
        return
    if output_format in {"dot", "graphml"}:
        typer.echo(export_provenance(trace, output_format))
        return
    if output_format != "text":
        typer.echo(
            "only --format text, json, markdown, dot, or graphml is supported",
            err=True,
        )
        raise typer.Exit(code=1)
    counts = node_type_counts(trace)
    typer.echo(f"trace: {trace.trace_id}")
    typer.echo(f"root: {trace.root_node_id}")
    typer.echo(f"completeness: {trace.completeness.overall.value}")
    typer.echo(f"synthetic: {trace.synthetic}")
    typer.echo(f"nodes: {len(trace.nodes)}")
    typer.echo(f"edges: {len(trace.edges)}")
    typer.echo("node_types:")
    for key in sorted(counts):
        typer.echo(f"  {key}: {counts[key]}")
    for warning in trace.warnings:
        typer.echo(f"warning: {warning}")


def _parse_seed_list(value: str) -> list[int]:
    seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not seeds:
        msg = "at least one seed is required"
        raise ValueError(msg)
    if any(seed < 0 for seed in seeds):
        msg = "seeds must be non-negative integers"
        raise ValueError(msg)
    return seeds


def _write_report(
    builder: Callable[[str | Path], ResearchReport],
    path: Path,
    output: Path,
    *,
    registry: Path | None = None,
) -> None:
    try:
        report = builder(path)
    except ReportBuildError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    _write_report_payload(_report_with_registry_annotations(report, registry), output)


def _report_with_registry_annotations(
    report: ResearchReport,
    registry: Path | None,
) -> ResearchReport:
    if registry is None:
        return report
    try:
        return attach_registry_annotations(report, Registry(registry))
    except (RegistryError, ReportAnnotationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _write_report_payload(report: ResearchReport, output: Path) -> None:
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
    typer.echo(f"report: {output}")


def _write_research_projection(
    projection: ResearchExportProjection,
    output: Path,
    figure: Path | None,
    *,
    overwrite: bool,
) -> None:
    try:
        receipt = write_projection_exports(
            projection,
            output,
            figure_path=figure,
            overwrite=overwrite,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"table: {output}")
    if figure is not None:
        typer.echo(f"figure: {figure}")
    typer.echo(f"projection: {receipt.projection_fingerprint}")
    typer.echo(f"source_mode: {_projection_source_mode(projection)}")
    for published_file in receipt.files:
        typer.echo(
            "file: "
            f"{published_file.name} "
            f"format={published_file.format} "
            f"sha256={published_file.checksum_sha256} "
            f"bytes={published_file.size_bytes}"
        )


def _projection_source_mode(projection: ResearchExportProjection) -> str:
    if projection.synthetic is True:
        return "synthetic"
    if projection.synthetic is False:
        return "imported_or_non_synthetic"
    return "unresolved"


# --- MAN-09 Gate-D step 1: Greater Manchester baseline network -----------------
#
# These commands are the only place network acquisition and netconvert execution
# happen. Streamlit pages read accepted results through
# `integration.manchester.network_service` and never fetch or build.


def _networks_root(workspace: Path) -> Path:
    root = workspace / "manchester" / NETWORKS_DIRECTORY_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


@manchester_network_app.command("scope")
def manchester_network_scope_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the approved ADR-059 baseline scope and required-area inclusion.

    Greater Manchester is the baseline; Manchester local authority is a filter.
    MAN-09 remains planned.
    """

    decision = baseline_scope_decision()
    if output_format == "json":
        _echo_json(decision.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"decision_record: {decision.decision_record}")
    typer.echo(f"baseline_scope: {decision.baseline_scope} ({decision.baseline_official_code})")
    typer.echo(f"sub_area_filter: {decision.sub_area_scope} ({decision.sub_area_official_code})")
    typer.echo(f"sub_area_is_second_network: {str(decision.sub_area_is_second_network).lower()}")
    envelope = decision.envelope
    typer.echo(
        "extract_envelope: "
        f"lon {envelope.min_longitude}..{envelope.max_longitude} "
        f"lat {envelope.min_latitude}..{envelope.max_latitude}"
    )
    typer.echo(f"envelope_derivation: {envelope.derivation}")
    typer.echo(f"envelope_margin_degrees: {envelope.margin_degrees}")
    typer.echo(f"envelope_boundary_uncertainty_m: {envelope.boundary_uncertainty_m}")
    typer.echo(f"geographic_crs: {decision.geographic_crs}")
    typer.echo(f"distance_crs: {decision.distance_crs}")
    for probe in decision.required_areas:
        typer.echo(
            f"required_area: {probe.area} "
            f"inside_baseline={str(probe.inside_baseline_boundary).lower()} "
            f"inside_manchester_filter={str(probe.inside_sub_area_boundary).lower()}"
        )
    coverage = decision.dft_coverage
    typer.echo(f"dft_coverage: {coverage.coverage_kind} ({coverage.observation_scope} only)")
    typer.echo(f"dft_uncovered_state: {coverage.uncovered_state}")
    typer.echo(f"dft_uncovered_is_zero: {str(coverage.uncovered_is_zero).lower()}")
    typer.echo(f"capability_status: {decision.capability_status}")


@manchester_network_app.command("acquire")
def manchester_network_acquire_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Explicit operator authorisation for network access.")
    ] = False,
    reason: Annotated[str, typer.Option("--reason")] = "operator-invoked baseline acquisition",
    from_file: Annotated[
        Path | None,
        typer.Option("--from-file", help="Import a local extract instead of fetching."),
    ] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Acquire the pinned OSM extract into the workspace, or import a local one.

    Network access happens only with an explicit --confirm. The endpoint, path,
    media types, and byte bounds are frozen; no URL is accepted. MAN-09 remains
    planned and no network is built by this command.
    """

    if not confirm:
        typer.echo(
            "refused: acquisition needs explicit operator authorisation; pass --confirm",
            err=True,
        )
        raise typer.Exit(code=2)
    root = _networks_root(workspace)
    policy = ManchesterSnapshotPolicy(
        max_member_count=8,
        max_member_bytes=OSM_MAX_EXTRACT_BYTES,
        max_total_bytes=OSM_MAX_EXTRACT_BYTES + 1_000_000,
    )
    authorisation = OperatorAuthorisation(
        confirmed_by_operator=True, invoked_via="cli", reason=reason
    )
    try:
        if from_file is not None:
            result = import_local_osm_extract(
                root,
                from_file,
                LocalOsmExtractImportRequest(
                    authorisation=authorisation, policy=policy, synthetic=False
                ),
            )
        else:
            result = acquire_osm_extract_snapshot(
                root,
                OsmExtractAcquisitionRequest(
                    authorisation=authorisation, policy=policy, synthetic=False
                ),
            )
    except (OsmAcquisitionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(result.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    identity = result.identity
    typer.echo(f"acquisition_mode: {result.acquisition_mode}")
    typer.echo(f"snapshot_id: {result.snapshot_id}")
    typer.echo(f"extract_sha256: {identity.extract_sha256}")
    typer.echo(f"extract_md5: {identity.extract_md5}")
    typer.echo(f"extract_bytes: {identity.extract_bytes}")
    typer.echo(f"reference_date: {identity.reference_date.isoformat()}")
    typer.echo(f"extract_data_cutoff_date: {identity.extract_data_cutoff_date.isoformat()}")
    typer.echo(f"provider_checksum_verified: {str(identity.provider_checksum_verified).lower()}")
    typer.echo(f"licence_id: {identity.licence_id}")
    typer.echo(f"attribution: {identity.attribution_text}")
    typer.echo(f"publication_class: {identity.publication_class}")
    typer.echo(f"network_build_performed: {str(result.network_build_performed).lower()}")
    typer.echo(f"capability_status: {result.capability_status}")


@manchester_network_app.command("build")
def manchester_network_build_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    extract: Annotated[Path, typer.Option("--extract", exists=True, dir_okay=False)],
    network_id: Annotated[str, typer.Option("--network-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Build one baseline-network candidate with the frozen netconvert recipe.

    The builder takes no arguments, flags, or tool paths from the caller and
    never uses a shell. A build is geometry only: it is not calibration, not
    validation against observations, not live traffic, and not VEC execution.
    """

    root = _networks_root(workspace)
    try:
        # Check the input format before deriving identity, so a PBF extract
        # reports the actionable decode blocker instead of a byte-count error.
        check_builder_input_format(extract)
        identity_path = extract.parent / f"{extract.name}.identity.json"
        extract_identity = (
            OsmExtractIdentity.model_validate_json(identity_path.read_text(encoding="utf-8"))
            if identity_path.is_file()
            else _identity_from_file(extract)
        )
        binding = build_baseline_network(
            root,
            extract,
            NetworkBuildRequest(
                network_id=network_id,
                extract=extract_identity,
                synthetic=False,
            ),
        )
    except (NetworkBuildError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(binding.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    _echo_binding(binding)


def _identity_from_file(extract: Path) -> OsmExtractIdentity:
    payload = extract.read_bytes()
    return OsmExtractIdentity(
        extract_sha256=sha256_hex(payload),
        extract_md5=hashlib.md5(payload, usedforsecurity=False).hexdigest(),
        extract_bytes=len(payload),
        reference_date=OSM_REFERENCE_DATE,
        provider_checksum_verified=False,
        provider_checksum_source="absent",
        synthetic=False,
    )


def _echo_binding(binding: ManchesterBaselineNetworkBinding) -> None:
    typer.echo(f"network_id: {binding.network_id}")
    typer.echo(f"network_identity_sha256: {binding.network_identity_sha256}")
    typer.echo(f"network_sha256: {binding.network_sha256}")
    typer.echo(f"network_bytes: {binding.network_bytes}")
    typer.echo(f"byte_reproducible: {str(binding.byte_reproducible).lower()}")
    typer.echo(f"semantic_reproducibility: {binding.semantic_reproducibility}")
    typer.echo(f"netconvert_version: {binding.command.reported_version}")
    typer.echo(f"exit_code: {binding.command.exit_code}")
    typer.echo(f"validation_status: {binding.validation.status}")
    structure = binding.validation.structure
    typer.echo(
        "structure: "
        f"edges={structure.edge_count} junctions={structure.junction_count} "
        f"connections={structure.connection_count} lanes={structure.lane_count} "
        f"traffic_lights={structure.traffic_light_count}"
    )
    typer.echo(f"proj_parameter: {binding.validation.location.proj_parameter}")
    typer.echo(f"orig_boundary: {binding.validation.location.orig_boundary}")
    for area in binding.validation.required_areas:
        typer.echo(f"required_area: {area.area} inside={str(area.inside_network_boundary).lower()}")
    for warning in binding.command.warning_lines:
        typer.echo(f"warning: {warning}")
    typer.echo(f"licence_id: {binding.licence_id}")
    typer.echo(f"attribution: {binding.attribution_text}")
    typer.echo(f"baseline_scope: {binding.baseline_scope}")
    typer.echo(f"sub_area_filter_scope: {binding.sub_area_filter_scope}")
    typer.echo(f"calibration_performed: {str(binding.calibration_performed).lower()}")
    typer.echo(f"accepted_for_real_matching: {str(binding.accepted_for_real_matching).lower()}")
    typer.echo(f"gate: {binding.gate_d_step}")
    typer.echo(f"capability_status: {binding.capability_status}")


@manchester_network_app.command("list")
def manchester_network_list_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """List accepted baseline-network candidates in one workspace."""

    candidates = list_network_candidates(_networks_root(workspace))
    if output_format == "json":
        _echo_json([candidate.model_dump(mode="json") for candidate in candidates])
        return
    _require_text_format(output_format)
    if not candidates:
        typer.echo("no accepted baseline-network candidate exists in this workspace")
        typer.echo("capability_status: planned")
        return
    for candidate in candidates:
        typer.echo(
            f"{candidate.network_id} "
            f"identity={candidate.network_identity_sha256[:16]} "
            f"status={candidate.validation_status} "
            f"edges={candidate.edge_count} junctions={candidate.junction_count} "
            f"areas_covered={str(candidate.required_areas_covered).lower()}"
        )
    typer.echo("capability_status: planned")


@manchester_network_app.command("verify")
def manchester_network_verify_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    network_id: Annotated[str, typer.Option("--network-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Re-verify one candidate's recorded raw and semantic digests."""

    try:
        binding = inspect_network_candidate(_networks_root(workspace) / network_id)
    except (NetworkBuildError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(binding.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"network_id: {binding.network_id}")
    typer.echo("verified: true")
    typer.echo(f"network_sha256: {binding.network_sha256}")
    typer.echo(f"network_identity_sha256: {binding.network_identity_sha256}")
    typer.echo(f"capability_status: {binding.capability_status}")


def _eligibility(value: str) -> Eligibility:
    """Narrow a validated CLI string to the typed subgraph selector."""

    for candidate in ELIGIBILITIES:
        if candidate == value:
            return candidate
    raise typer.BadParameter(f"--probe-subgraph must be one of {', '.join(ELIGIBILITIES)}")


@manchester_network_app.command("connectivity")
def manchester_network_connectivity_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    network_id: Annotated[str, typer.Option("--network-id")],
    probes: Annotated[int, typer.Option("--probes", min=1, max=MAX_ROUTE_PROBES)] = (
        DEFAULT_ROUTE_PROBES
    ),
    contrast_probes: Annotated[
        int, typer.Option("--contrast-probes", min=0, max=MAX_ROUTE_PROBES)
    ] = DEFAULT_CONTRAST_PROBES,
    probe_subgraph: Annotated[str, typer.Option("--probe-subgraph")] = "passenger_car",
    save: Annotated[bool, typer.Option("--save/--no-save")] = True,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Review one accepted network's motor-eligible connectivity and routability.

    Bounded probes establish reachability for the pairs they run. They are not
    evidence of universal routability, and no number of them would be.
    """

    # Every argument is validated before the network is touched: a review
    # streams the whole file and walks the graph, and a run that is going to be
    # rejected for its output format must not do that work or leave a record.
    eligibility = _eligibility(probe_subgraph)
    if output_format != "json":
        _require_text_format(output_format)
    directory = _networks_root(workspace) / network_id
    try:
        report = review_network_connectivity(
            directory,
            probe_count=probes,
            contrast_probe_count=contrast_probes,
            probe_eligibility=eligibility,
        )
        if save:
            write_connectivity_record(directory, report)
    except (NetworkBuildError, NetworkConnectivityError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(report.model_dump(mode="json"))
        return
    access = report.access
    typer.echo(f"network_id: {report.network_id}")
    typer.echo(f"network_identity_sha256: {report.network_identity_sha256}")
    typer.echo(
        f"edge_elements: {access.total_edge_elements} "
        f"internal_excluded: {access.internal_edges_excluded} "
        f"real: {access.real_edges} dangling_excluded: {access.dangling_edges_excluded}"
    )
    typer.echo(
        f"passenger_car_edges: {access.passenger_car_edges} "
        f"motor_no_car_edges: {access.motor_vehicle_no_car_edges} "
        f"no_motor_edges: {access.no_motor_vehicle_edges} "
        f"unreadable_edges: {access.permissions_unreadable_edges}"
    )
    for summary in report.components:
        typer.echo(
            f"{summary.kind}/{summary.eligibility}: "
            f"edges={summary.eligible_edges} components={summary.component_count} "
            f"largest_edge_share={summary.largest_component_edge_share} "
            f"largest_length_share={summary.largest_component_length_share} "
            f"between_components={summary.edges_between_components} "
            f"fragments={summary.isolated.fragment_components} "
            f"fragment_edges={summary.isolated.fragment_edges} "
            f"untouched_junctions={summary.junctions_untouched}"
        )
    outcomes: dict[str, int] = {}
    for probe in report.probes:
        key = f"{probe.selection}/{probe.outcome}"
        outcomes[key] = outcomes.get(key, 0) + 1
    for key in sorted(outcomes):
        typer.echo(f"probe {key}: {outcomes[key]}")
    for note in report.exclusion_notes:
        typer.echo(f"exclusion: {note}")
    typer.echo(f"proves_universal_routability: {str(report.proves_universal_routability).lower()}")
    typer.echo(f"capability_status: {report.capability_status}")


@manchester_network_app.command("status")
def manchester_network_status_command(
    workspace: Annotated[Path | None, typer.Argument(file_okay=False)] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Report honest baseline-network status, including what stays unavailable."""

    root = _networks_root(workspace) if workspace is not None and workspace.is_dir() else None
    status = baseline_network_status(root)
    if output_format == "json":
        _echo_json(status.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"capability_id: {status.capability_id}")
    typer.echo(f"capability_status: {status.capability_status}")
    typer.echo(f"practical_state: {status.practical_state}")
    typer.echo(f"gate: {status.gate}")
    typer.echo(f"toolchain_available: {str(status.toolchain.available).lower()}")
    if status.toolchain.reported_version is not None:
        typer.echo(f"netconvert_version: {status.toolchain.reported_version}")
    if status.toolchain.blocker is not None:
        typer.echo(f"toolchain_blocker: {status.toolchain.blocker}")
    typer.echo(f"decoder_available: {str(status.decoder.available).lower()}")
    if status.decoder.reported_version is not None:
        typer.echo(f"osmium_version: {status.decoder.reported_version}")
    if status.decoder.blocker is not None:
        typer.echo(f"decoder_blocker: {status.decoder.blocker}")
    typer.echo(f"candidate_count: {status.candidate_count}")
    typer.echo(f"calibration_available: {str(status.calibration_available).lower()}")
    typer.echo(f"comparison_available: {str(status.comparison_available).lower()}")
    typer.echo(f"live_traffic_available: {str(status.live_traffic_available).lower()}")
    for blocker in status.map_matching_preflight.blockers:
        typer.echo(f"map_matching_blocker: {blocker}")
    for reason in status.unavailable_reasons:
        typer.echo(f"unavailable: {reason}")


@manchester_network_app.command("decode")
def manchester_network_decode_command(
    extract: Annotated[Path, typer.Option("--extract", exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", dir_okay=False)],
    verify_pinned: Annotated[
        bool,
        typer.Option(
            "--verify-pinned",
            help="Refuse anything but the exact ADR-059 pinned extract identity.",
        ),
    ] = False,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Decode a PBF extract to OSM XML with the frozen osmium recipe.

    netconvert 1.27.1 reads OSM XML only, so a PBF extract needs this step
    first. The decode is a format conversion and never a content selection: it
    applies no tag filter, bounding-box clip, simplification, or road-class
    choice. The decoded artifact is a private workspace intermediate and is
    never committed.
    """

    try:
        receipt = decode_pbf_to_osm_xml(
            extract,
            output,
            expectation=pinned_source_expectation() if verify_pinned else None,
        )
    except (NetworkDecodeError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(receipt.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"osmium_version: {receipt.tool.reported_version}")
    if receipt.tool.libosmium_version is not None:
        typer.echo(f"libosmium_version: {receipt.tool.libosmium_version}")
    typer.echo(f"source_sha256: {receipt.source_sha256}")
    typer.echo(f"source_bytes: {receipt.source_bytes}")
    typer.echo(f"decoded_sha256: {receipt.decoded_sha256}")
    typer.echo(f"decoded_bytes: {receipt.decoded_bytes}")
    header = receipt.source_header
    if header.replication_timestamp is not None:
        typer.echo(f"osm_data_cutoff_instant: {header.replication_timestamp}")
    if header.replication_sequence_number is not None:
        typer.echo(f"osm_replication_sequence: {header.replication_sequence_number}")
    if header.header_min_longitude is not None:
        typer.echo(
            "source_header_bbox: "
            f"lon {header.header_min_longitude}..{header.header_max_longitude} "
            f"lat {header.header_min_latitude}..{header.header_max_latitude}"
        )
    typer.echo(f"source_identity_verified: {str(receipt.source_identity_verified).lower()}")
    if receipt.data_cutoff_date is not None:
        typer.echo(f"data_cutoff_date: {receipt.data_cutoff_date.isoformat()}")
    if receipt.retrieval_date is not None:
        typer.echo(f"retrieval_date: {receipt.retrieval_date.isoformat()}")
    if receipt.provider_last_modified is not None:
        typer.echo(f"provider_last_modified: {receipt.provider_last_modified}")
    typer.echo(f"conversion_only: {str(receipt.conversion_only).lower()}")
    typer.echo(f"content_filtered: {str(receipt.content_filtered).lower()}")
    typer.echo(f"bounding_box_clipped: {str(receipt.bounding_box_clipped).lower()}")
    typer.echo(f"publication_class: {receipt.publication_class}")
    typer.echo(f"committed_to_git: {str(receipt.committed_to_git).lower()}")
    typer.echo(f"capability_status: {receipt.capability_status}")


@manchester_network_app.command("verify-decode")
def manchester_network_verify_decode_command(
    decoded: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Revalidate a promoted decoded OSM artifact and its receipt, fully offline.

    Calls neither the provider nor the decoder. A mutated artifact or a mutated
    receipt fails with a non-zero exit.
    """

    try:
        receipt = verify_decoded_artifact(decoded)
    except (NetworkDecodeError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(receipt.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo("verified: true")
    typer.echo(f"decoded_sha256: {receipt.decoded_sha256}")
    typer.echo(f"decoded_bytes: {receipt.decoded_bytes}")
    typer.echo(f"source_sha256: {receipt.source_sha256}")
    typer.echo(f"source_identity_verified: {str(receipt.source_identity_verified).lower()}")
    typer.echo("network_access_performed: false")
    typer.echo("decoder_invoked: false")
    typer.echo(f"capability_status: {receipt.capability_status}")


# --- Manchester DfT temporal-profile commands (MAN-09, planned) ---------------
# Read-only over accepted local snapshots. Nothing here fetches, and the service
# a UI reads is a pure summariser, so an ordinary rerun cannot reach a provider.


@manchester_profile_app.command("policy")
def manchester_profile_policy_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Print the declared temporal-profile policy without reading any evidence."""

    policy = DftTemporalProfilePolicy()
    if output_format == "json":
        _echo_json(policy.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"policy_id: {policy.policy_id}")
    typer.echo(f"policy_fingerprint: {policy.fingerprint()}")
    typer.echo(f"measure: {policy.measure} ({policy.unit})")
    typer.echo(f"time_basis: {policy.time_basis}")
    typer.echo(f"utc_projection_available: {str(policy.utc_projection_available).lower()}")
    typer.echo(
        f"simulation_origin: {policy.simulation_origin_local_hour}:00 local = second 0, "
        f"{policy.interval_seconds}s {policy.interval_convention}"
    )
    typer.echo(f"profile_hours: {', '.join(str(hour) for hour in policy.profile_hours)}")
    typer.echo(f"series_key: {policy.series_key}")
    typer.echo(f"missing_as_zero: {str(policy.missing_as_zero).lower()}")
    typer.echo(f"aadf_admitted: {str(policy.aadf_admitted).lower()}")
    typer.echo(
        f"webtris_admitted: {str(policy.webtris_admitted).lower()} "
        f"(blocker {policy.webtris_blocker})"
    )
    typer.echo(f"dft_hour_timezone_blocker: {policy.dft_hour_timezone_blocker}")
    typer.echo(
        f"split: {policy.split_rule} over {policy.split_unit}, "
        f"held_out_basis_points={policy.held_out_basis_points}"
    )
    typer.echo(f"minimum_partition_coverage: {policy.minimum_partition_coverage}")
    typer.echo(f"research_status: {policy.research_status}")
    typer.echo("capability_status: planned")


@manchester_profile_app.command("build")
def manchester_profile_build_command(
    workspace: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    snapshot_id: Annotated[str, typer.Option("--snapshot-id")],
    output: Annotated[Path | None, typer.Option("--output", dir_okay=False)] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite/--no-overwrite")] = False,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Build the temporal-profile candidate from one accepted raw-counts snapshot.

    The snapshot is re-verified through the MAN-01 contract before a byte is
    parsed, and a synthetic snapshot is refused. Nothing is fetched and the raw
    tree is never modified.
    """

    if output_format != "json":
        _require_text_format(output_format)
    if output is not None and output.exists() and not output.is_symlink() and not overwrite:
        # A profile is evidence. Replacing one silently would destroy a record
        # somebody may already have cited.
        typer.echo(
            f"{output} already exists; pass --overwrite to replace it",
            err=True,
        )
        raise typer.Exit(code=1)
    try:
        records, source = open_real_raw_count_evidence(workspace, snapshot_id)
        profile = build_dft_temporal_profile(records, source)
        if output is not None:
            write_profile_record(output, profile)
    except (DftAcquisitionError, DftTemporalProfileError, OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(profile.model_dump(mode="json"))
        return
    _echo_profile_text(profile)


@manchester_profile_app.command("inspect")
def manchester_profile_inspect_command(
    profile_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Reopen a stored profile and report its status without rebuilding it."""

    if output_format != "json":
        _require_text_format(output_format)
    # Bounded before reading: a stored profile is a few megabytes, and an
    # unbounded read of an arbitrary path is how a large or hostile file
    # becomes a memory problem.
    if profile_path.is_symlink():
        typer.echo("the profile path is a symlink, which is refused", err=True)
        raise typer.Exit(code=1)
    if not profile_path.is_file():
        typer.echo("the profile path is not a regular file", err=True)
        raise typer.Exit(code=1)
    if profile_path.stat().st_size > MAX_PROFILE_ARTIFACT_BYTES:
        typer.echo(
            f"the profile exceeds the {MAX_PROFILE_ARTIFACT_BYTES}-byte bound and was not read",
            err=True,
        )
        raise typer.Exit(code=1)
    try:
        profile = ManchesterDftTemporalProfile.model_validate_json(
            profile_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    status = profile_service_status(profile)
    if output_format == "json":
        _echo_json(status.model_dump(mode="json"))
        return
    typer.echo(f"profile_available: {str(status.profile_available).lower()}")
    typer.echo(f"evidence_class: {status.evidence_class}")
    typer.echo(f"admission: {status.admission}")
    typer.echo(f"sites_total: {status.sites_total}")
    typer.echo(f"series_total: {status.series_total}")
    typer.echo(f"coverage: {status.coverage}")
    typer.echo(f"performs_network_access: {str(status.performs_network_access).lower()}")
    for reason in status.unavailable_reasons:
        typer.echo(f"unavailable: {reason}")
    typer.echo(f"capability_status: {status.capability_status}")


def _echo_profile_text(profile: ManchesterDftTemporalProfile) -> None:
    """Render one profile as text, leading with its denominators."""

    typer.echo(f"policy_id: {profile.policy.policy_id}")
    typer.echo(f"policy_fingerprint: {profile.policy_fingerprint}")
    typer.echo(f"source_snapshot_id: {profile.source.snapshot_id}")
    typer.echo(f"source_raw_fingerprint: {profile.source.raw_fingerprint}")
    typer.echo(f"source_parser_report_fingerprint: {profile.source.parser_report_fingerprint}")
    typer.echo(f"evidence_class: {profile.evidence_class}")
    typer.echo(f"source_synthetic: {str(profile.source.synthetic).lower()}")
    typer.echo(f"input_lineage_fingerprint: {profile.fingerprint_of_inputs()}")
    typer.echo(f"admission: {profile.admission}")
    typer.echo(
        f"rows: offered={profile.offered_rows} admitted={profile.admitted_rows} "
        f"excluded={profile.excluded_rows}"
    )
    typer.echo(f"sites: {profile.sites_total} series: {profile.series_total}")
    typer.echo(
        f"cells: expected={profile.expected_cells} observed={profile.observed_cells} "
        f"missing={profile.missing_cells} measured_zero={profile.measured_zero_cells}"
    )
    typer.echo(f"coverage: {profile.coverage}")
    for summary in profile.partitions:
        typer.echo(
            f"partition {summary.partition}: sites={summary.sites} series={summary.series} "
            f"expected={summary.expected_cells} observed={summary.observed_cells} "
            f"missing={summary.missing_cells} excluded={summary.excluded_cells} "
            f"measured_zero={summary.measured_zero_cells} coverage={summary.coverage} "
            f"meets_minimum={str(summary.meets_minimum_coverage).lower()}"
        )
    reasons: dict[str, int] = {}
    for item in profile.exclusions:
        reasons[item.reason] = reasons.get(item.reason, 0) + 1
    for reason in sorted(reasons):
        typer.echo(f"exclusion {reason}: {reasons[reason]}")
    if not reasons:
        typer.echo("exclusion: none")
    typer.echo(f"utc_instant_available: {str(profile.utc_instant_available).lower()}")
    typer.echo(f"calibration_use_available: {str(profile.calibration_use_available).lower()}")
    typer.echo(f"aadf_fused: {str(profile.aadf_fused).lower()}")
    typer.echo(f"webtris_included: {str(profile.webtris_included).lower()}")
    typer.echo(f"capability_status: {profile.capability_status}")


@manchester_workflow_app.command("status")
def manchester_workflow_status_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
    show: Annotated[str, typer.Option("--show", help="all, available, or blocked")] = "all",
) -> None:
    """Show where the Manchester research workflow stands and what blocks it.

    Read-only and offline: nothing is fetched, executed, or computed. Every
    blocked stage states its blocker, so an unavailable stage is visible rather
    than silently absent. MAN-09 remains planned.
    """

    status = manchester_workflow_status()
    if output_format == "json":
        _echo_json(status.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    if show not in {"all", "available", "blocked"}:
        typer.secho(
            "--show must be one of: all, available, blocked",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)

    typer.echo(f"research_status: {status.research_status}")
    typer.echo(f"acceptance_basis: {status.acceptance_basis}")
    typer.echo(f"analyst_reviewed: {str(status.analyst_reviewed).lower()}")
    typer.echo(f"supervisor_approved: {str(status.supervisor_approved).lower()}")
    typer.echo(f"capability_status: {status.capability_status}")
    typer.echo(f"gate_d: {status.gate_d_state}")
    typer.echo(f"gate_e: {status.gate_e_state}")
    typer.echo(
        f"stages: {len(status.stages)} "
        f"(available {len(status.available_stages)}, blocked {len(status.blocked_stages)})"
    )

    if show == "available":
        selected = status.available_stages
    elif show == "blocked":
        selected = status.blocked_stages
    else:
        selected = status.stages
    for stage in selected:
        typer.echo(f"phase {stage.phase}: {stage.key} [{stage.state}]")
        if stage.summary:
            typer.echo(f"    produced: {stage.summary}")
        if stage.blocker:
            typer.echo(f"    blocked_by: {stage.blocker}")
            if stage.blocker_owner != "none":
                typer.echo(f"    lifted_by: {stage.blocker_owner}")

    for decision in status.open_owner_decisions:
        typer.echo(f"open_owner_decision: {decision}")


@manchester_workflow_app.command("decisions")
def manchester_workflow_decisions_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """List the decisions only the repository owner can make.

    These gate the remaining research chain. No agent may answer them, and none
    is answered by a default.
    """

    status = manchester_workflow_status()
    if output_format == "json":
        _echo_json({"open_owner_decisions": list(status.open_owner_decisions)})
        return
    _require_text_format(output_format)
    typer.echo(f"open_owner_decisions: {len(status.open_owner_decisions)}")
    for index, decision in enumerate(status.open_owner_decisions, start=1):
        typer.echo(f"{index}. {decision}")


@manchester_observation_app.command("snapshots")
def manchester_observation_snapshots_command(
    workspace: Annotated[Path, typer.Option("--workspace", help="v0.7 workspace root")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """List accepted DfT snapshots in a workspace.

    Read-only and offline: the catalogue is read from promoted artifacts and no
    request is made. MAN-02 evidence is historical and is never live traffic.
    """

    try:
        catalogue = catalogue_accepted_dft_snapshots(workspace)
    except DftAcquisitionError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(catalogue.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"network_access_performed: {str(catalogue.network_access_performed).lower()}")
    typer.echo(f"snapshots: {len(catalogue.snapshots)}")
    for snapshot in catalogue.snapshots:
        typer.echo(
            f"snapshot: {snapshot.snapshot_id} dataset={snapshot.dataset} pages={snapshot.pages}"
        )
        typer.echo(f"    raw_fingerprint: {snapshot.raw_fingerprint}")
        typer.echo(f"    endpoint_path: {snapshot.endpoint_path}")
    if not catalogue.snapshots:
        typer.echo("no accepted snapshot is present; acquisition is operator-invoked")


@manchester_match_app.command("policy")
def manchester_match_policy_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the owner-approved candidate map-matching policy.

    The policy is owner-approved candidate research, not supervisor-approved,
    and version 1.1 disables automatic final acceptance. MAN-09 remains planned.
    """

    policy = ManchesterMapMatchPolicyV11()
    if output_format == "json":
        _echo_json(policy.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"policy_id: {policy.policy_id}")
    typer.echo(f"research_status: {policy.research_status}")
    typer.echo(f"supervisor_approved: {str(policy.supervisor_approved).lower()}")
    typer.echo(f"scientifically_validated: {str(policy.scientifically_validated).lower()}")
    base = policy.base
    typer.echo(f"supersedes_policy_id: {policy.supersedes_policy_id}")
    typer.echo(f"automatic_acceptance_enabled: {str(base.automatic_acceptance_enabled).lower()}")
    typer.echo(
        f"owner_policy_acceptance_enabled: {str(policy.owner_policy_acceptance_enabled).lower()}"
    )
    typer.echo(f"outer_search_radius_m: {base.outer_search_radius_m}")
    typer.echo(f"native_eligibility_m: {base.native_eligibility_m}")
    typer.echo(f"fallback_eligibility_m: {base.fallback_eligibility_m}")
    typer.echo(f"direction_tolerance_degrees: {base.direction_tolerance_degrees}")
    typer.echo(f"override_relaxes_only: {policy.override_relaxes_only}")
    typer.echo(f"override_max_distance_m: {policy.override_max_distance_m}")
    typer.echo(f"override_uses_fuzzy_names: {str(policy.override_uses_fuzzy_names).lower()}")
    typer.echo(
        "acceptance_note: rows this policy accepts are owner_policy_accepted_candidate; "
        "no analyst, human, or supervisor has reviewed any row"
    )


def _manchester_match_results(
    workspace: Path,
    network: Path,
    raw_snapshot_id: str,
    count_point_snapshot_id: str,
) -> list[ObservationMatchV11]:
    """Reproduce the v1.1 match run from accepted snapshots.

    Deliberately recomputed rather than read from a cached artifact: a stale
    cache would let the CLI report a match set that no longer follows from the
    accepted evidence.
    """

    records, _binding = open_real_raw_count_evidence(workspace, raw_snapshot_id)
    load = open_accepted_dft_snapshot(workspace, count_point_snapshot_id)
    report = load.report
    points = getattr(report, "records", ())
    sites_with_counts = {record.count_point_id for record in records}
    index = build_edge_index(network)
    access = {edge.edge_id: edge.access for edge in stream_network_edges(network)}
    policy = ManchesterMapMatchPolicyV11()
    results: list[ObservationMatchV11] = []
    for point in points:
        if point.count_point_id not in sites_with_counts:
            continue
        location = point.location
        if location.easting is None or location.northing is None:
            continue
        results.append(
            match_observation_v11(
                count_point_id=point.count_point_id,
                easting=float(location.easting),
                northing=float(location.northing),
                dft_road_type=location.road_type,
                dft_road_name=location.road_name,
                dft_road_ref=dft_road_reference(location.road_name),
                index=index,
                policy=policy,
                motor_access=access,
            )
        )
    return results


@manchester_match_app.command("candidates")
def manchester_match_candidates_command(
    workspace: Annotated[Path, typer.Option("--workspace")],
    network: Annotated[Path, typer.Option("--network", help="reviewed study or baseline network")],
    raw_snapshot_id: Annotated[str, typer.Option("--raw-snapshot-id")],
    count_point_snapshot_id: Annotated[str, typer.Option("--count-point-snapshot-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Generate map-match candidates for every real count point.

    Recomputed from accepted snapshots, so the result always follows from the
    evidence. Rows the policy accepts are `owner_policy_accepted_candidate`; no
    person has reviewed any of them. MAN-09 remains planned.
    """

    try:
        results = _manchester_match_results(
            workspace, network, raw_snapshot_id, count_point_snapshot_id
        )
    except (DftAcquisitionError, ObservationMatchingError, NetworkGeometryError) as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    dispositions = Counter(result.disposition for result in results)
    payload = {
        "policy_id": MAP_MATCH_POLICY_V11_ID,
        "observations": len(results),
        "dispositions": dict(sorted(dispositions.items())),
        "acceptance_basis": "owner_policy_accepted_candidate",
        "analyst_reviewed": False,
        "supervisor_approved": False,
    }
    if output_format == "json":
        _echo_json(payload)
        return
    _require_text_format(output_format)
    typer.echo(f"policy_id: {MAP_MATCH_POLICY_V11_ID}")
    typer.echo(f"observations: {len(results)}")
    for disposition, count in sorted(dispositions.items()):
        typer.echo(f"disposition: {disposition} = {count}")
    typer.echo("acceptance_basis: owner_policy_accepted_candidate")
    typer.echo("analyst_reviewed: false")
    typer.echo("note: an accepted row was accepted by the owner's written policy, not by a person")


@manchester_match_app.command("review")
def manchester_match_review_command(
    workspace: Annotated[Path, typer.Option("--workspace")],
    network: Annotated[Path, typer.Option("--network")],
    raw_snapshot_id: Annotated[str, typer.Option("--raw-snapshot-id")],
    count_point_snapshot_id: Annotated[str, typer.Option("--count-point-snapshot-id")],
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 20,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the manual-review queue.

    Read-only by design. There is deliberately no accept, reject, or bulk
    option: policy 1.1 requires a person for every unaccepted row, and a command
    that could clear the queue would let an agent stand in for one.
    """

    try:
        results = _manchester_match_results(
            workspace, network, raw_snapshot_id, count_point_snapshot_id
        )
    except (DftAcquisitionError, ObservationMatchingError, NetworkGeometryError) as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    queue = build_manual_review_queue(results)
    if output_format == "json":
        _echo_json(queue.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"observations_total: {queue.observations_total}")
    typer.echo(f"accepted_total: {queue.accepted_total}")
    typer.echo(f"queued_total: {queue.queued_total}")
    typer.echo(f"queue_preserved: {str(queue.queue_preserved).lower()}")
    for entry in queue.entries[:limit]:
        typer.echo(
            f"queued: count_point={entry.count_point_id} "
            f"road_type={entry.dft_road_type} confidence={entry.confidence} "
            f"groups={entry.eligible_group_count}"
        )
        for reason in entry.review_reasons:
            typer.echo(f"    reason: {reason}")
    if queue.queued_total > limit:
        typer.echo(f"shown {limit} of {queue.queued_total}; raise --limit to see more")
    typer.echo("note: this command cannot accept or reject a row; every queued row needs a person")


@manchester_observation_app.command("acquire")
def manchester_observation_acquire_command(
    workspace: Annotated[Path, typer.Option("--workspace")],
    dataset: Annotated[str, typer.Option("--dataset", help="count_points or raw_counts")],
    confirm: Annotated[
        bool, typer.Option("--confirm", help="required: this performs a real request")
    ] = False,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Acquire one audited DfT dataset for Manchester local authority 85.

    Operator-invoked and never a side effect: without --confirm nothing is
    requested. Manchester scope is bound as a literal, so no caller can widen it,
    and the result is historical evidence that is never live traffic.
    """

    if dataset not in {"count_points", "raw_counts"}:
        typer.secho("--dataset must be count_points or raw_counts", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)
    if not confirm:
        typer.secho(
            "refusing to acquire without --confirm: this performs a real request to "
            "roadtraffic.dft.gov.uk and promotes a snapshot",
            err=True,
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=2)

    request = DftAcquisitionRequest(
        dataset=cast("DftDataset", dataset),
        page_size=500,
        max_pages=4 if dataset == "count_points" else 100,
        max_rows=2_000 if dataset == "count_points" else 60_000,
        policy=ManchesterSnapshotPolicy(
            max_member_count=120, max_member_bytes=20_000_000, max_total_bytes=400_000_000
        ),
        publication_class=ManchesterPublicationClass.PRIVATE,
        accept_with_warnings=False,
        synthetic=False,
    )
    try:
        result = acquire_dft_snapshot(workspace, request)
    except DftAcquisitionError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        _echo_json(result.model_dump(mode="json"))
        return
    _require_text_format(output_format)
    typer.echo(f"snapshot_id: {result.snapshot_id}")
    typer.echo(f"dataset: {result.dataset}")
    typer.echo(f"endpoint: {result.endpoint_host}{result.endpoint_path}")
    typer.echo(f"pages: {result.pages}")
    typer.echo(f"rows_seen: {result.rows_seen}")
    typer.echo(f"records_accepted: {result.records_accepted}")
    typer.echo(f"parser_status: {result.parser_status}")
    typer.echo(f"synthetic: {str(result.synthetic).lower()}")
    typer.echo(f"raw_fingerprint: {result.raw_fingerprint}")
    typer.echo("note: DfT evidence is historical and is never live traffic")


@manchester_match_app.command("ambiguity")
def manchester_match_ambiguity_command(
    workspace: Annotated[Path, typer.Option("--workspace")],
    network: Annotated[Path, typer.Option("--network")],
    raw_snapshot_id: Annotated[str, typer.Option("--raw-snapshot-id")],
    count_point_snapshot_id: Annotated[str, typer.Option("--count-point-snapshot-id")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Measure how ambiguous matching is at each sensitivity radius.

    Distance barely discriminates on this data; ambiguity does. The radii are
    the approved sensitivity set and are not acceptance thresholds.
    """

    try:
        records, _binding = open_real_raw_count_evidence(workspace, raw_snapshot_id)
        load = open_accepted_dft_snapshot(workspace, count_point_snapshot_id)
        index = build_edge_index(network)
    except (DftAcquisitionError, NetworkGeometryError) as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    sites_with_counts = {record.count_point_id for record in records}
    points = [
        point
        for point in getattr(load.report, "records", ())
        if point.count_point_id in sites_with_counts
        and point.location.easting is not None
        and point.location.northing is not None
    ]
    rows: list[dict[str, object]] = []
    for radius in (10.0, 20.0, 30.0, 50.0, 100.0):
        counts: list[int] = []
        with_any = 0
        for point in points:
            hits = index.edges_within(
                float(point.location.easting),
                float(point.location.northing),
                radius_m=radius,
            )
            counts.append(len(hits))
            if hits:
                with_any += 1
        counts.sort()
        rows.append(
            {
                "radius_m": radius,
                "sites": len(points),
                "sites_with_a_candidate": with_any,
                "mean_candidates": round(sum(counts) / max(len(counts), 1), 2),
                "median_candidates": counts[len(counts) // 2] if counts else 0,
                "max_candidates": max(counts) if counts else 0,
            }
        )
    if output_format == "json":
        _echo_json({"sensitivity": rows, "thresholds_applied": False})
        return
    _require_text_format(output_format)
    typer.echo(f"sites: {len(points)}")
    for row in rows:
        typer.echo(
            f"radius_m={row['radius_m']} "
            f"sites_with_a_candidate={row['sites_with_a_candidate']} "
            f"mean={row['mean_candidates']} median={row['median_candidates']} "
            f"max={row['max_candidates']}"
        )
    typer.echo("note: these radii are a sensitivity set, not acceptance thresholds")


@manchester_run_app.command("preflight")
def manchester_run_preflight_command(
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Report whether a controlled SUMO run can proceed, without running one.

    Checks the toolchain only. Whether the current candidate demand should be
    simulated at all is a separate, measured question; see the workflow status.
    """

    payload: dict[str, object] = {"sumo_available": False, "reported_version": None}
    try:
        tool = sumo_identity()
        payload = {"sumo_available": True, "reported_version": tool.reported_version}
    except ManchesterSumoRunError as exc:
        payload["blocker"] = exc.code
    if output_format == "json":
        _echo_json(payload)
        return
    _require_text_format(output_format)
    typer.echo(f"sumo_available: {str(payload['sumo_available']).lower()}")
    if payload.get("reported_version"):
        typer.echo(f"reported_version: {payload['reported_version']}")
    if payload.get("blocker"):
        typer.echo(f"blocker: {payload['blocker']}")
    typer.echo("step_length_s: 1")
    typer.echo("fcd_period_s: 1")
    typer.echo(
        "note: the current candidate demand gridlocks in simulation; see "
        "`integration manchester workflow status --show blocked`"
    )


@manchester_demand_app.command("build")
def manchester_demand_build_command(
    workspace: Annotated[Path, typer.Option("--workspace")],
    network: Annotated[Path, typer.Option("--network")],
    raw_snapshot_id: Annotated[str, typer.Option("--raw-snapshot-id")],
    count_point_snapshot_id: Annotated[str, typer.Option("--count-point-snapshot-id")],
    counts_output: Annotated[
        Path | None, typer.Option("--counts-output", help="write the edgeData counts file here")
    ] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Bind raw-count directions to network edges and summarise the demand input.

    Applies the owner's Option A survey window and the approved 45 degree
    direction tolerance. Produces the count target only: route sampling is a
    separate, expensive step, and the current candidate demand is known to
    gridlock in simulation.
    """

    try:
        records, _binding = open_real_raw_count_evidence(workspace, raw_snapshot_id)
        results = _manchester_match_results(
            workspace, network, raw_snapshot_id, count_point_snapshot_id
        )
        index = build_edge_index(network)
    except (DftAcquisitionError, ObservationMatchingError, NetworkGeometryError) as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    accepted = {
        result.count_point_id: result
        for result in results
        if result.disposition == "owner_policy_accepted_candidate"
    }
    latest: dict[int, str] = {}
    for record in records:
        stamp = str(record.count_date)
        if record.count_point_id not in latest or stamp > latest[record.count_point_id]:
            latest[record.count_point_id] = stamp
    in_window = {
        site for site in accepted if site_is_in_survey_window(latest.get(site, "1900-01-01"))
    }

    member_ids = {
        edge.edge_id
        for site in in_window
        for group in accepted[site].groups
        for edge in group.members
    }
    ordinals = ordinals_by_edge_id(index, member_ids)

    directions: dict[int, set[str]] = defaultdict(set)
    for record in records:
        if (
            record.count_point_id in in_window
            and str(record.count_date) == latest[record.count_point_id]
        ):
            directions[record.count_point_id].add(record.direction_of_travel)

    bindings: dict[tuple[int, str], str] = {}
    outcomes: Counter[str] = Counter()
    for site in sorted(in_window):
        result = accepted[site]
        members = [edge.edge_id for group in result.groups for edge in group.members]
        distances = {
            edge.edge_id: edge.distance_m for group in result.groups for edge in group.members
        }
        for direction in sorted(directions[site]):
            resolution = resolve_direction(
                count_point_id=site,
                direction_of_travel=direction,
                member_edge_ids=members,
                index=index,
                ordinals_by_edge=ordinals,
                tolerance_degrees=Decimal("45"),
                distance_by_edge=distances,
            )
            outcomes[resolution.binding] += 1
            if resolution.edge_id:
                bindings[(site, direction)] = resolution.edge_id

    cells: list[EdgeHourCount] = []
    for record in records:
        key = (record.count_point_id, record.direction_of_travel)
        if key not in bindings or str(record.count_date) != latest[record.count_point_id]:
            continue
        vehicles = record.counts.all_motor_vehicles
        if vehicles is None:
            continue
        start, end = simulation_interval_for_hour(record.hour)
        cells.append(
            EdgeHourCount(
                edge_id=bindings[key],
                count_point_id=record.count_point_id,
                direction_of_travel=record.direction_of_travel,
                hour=record.hour,
                interval_start_s=start,
                interval_end_s=end,
                all_motor_vehicles=vehicles,
                measured_zero=vehicles == 0,
            )
        )

    written: dict[str, int] = {}
    if counts_output is not None:
        try:
            written = write_edgedata_counts(counts_output, cells)
        except DemandReconstructionError as exc:
            typer.secho(str(exc), err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc

    payload = {
        "accepted_sites": len(accepted),
        "sites_in_survey_window": len(in_window),
        "site_directions": sum(len(value) for value in directions.values()),
        "direction_outcomes": dict(sorted(outcomes.items())),
        "bound_site_directions": len(bindings),
        "distinct_bound_edges": len(set(bindings.values())),
        "edge_hour_cells": len(cells),
        "total_observed_vehicles": sum(cell.all_motor_vehicles for cell in cells),
        "measured_zero_cells": sum(1 for cell in cells if cell.measured_zero),
        "intervals_written": written,
        "acceptance_basis": "owner_policy_accepted_candidate",
        "demand_label": "count_constrained_candidate_demand",
        "observed_origin_destination_travel": False,
    }
    if output_format == "json":
        _echo_json(payload)
        return
    _require_text_format(output_format)
    typer.echo(f"accepted_sites: {payload['accepted_sites']}")
    typer.echo(f"sites_in_survey_window: {payload['sites_in_survey_window']}")
    for binding, count in sorted(outcomes.items()):
        typer.echo(f"direction_outcome: {binding} = {count}")
    typer.echo(f"bound_site_directions: {payload['bound_site_directions']}")
    typer.echo(f"distinct_bound_edges: {payload['distinct_bound_edges']}")
    typer.echo(f"edge_hour_cells: {payload['edge_hour_cells']}")
    typer.echo(f"total_observed_vehicles: {payload['total_observed_vehicles']}")
    typer.echo(f"measured_zero_cells: {payload['measured_zero_cells']}")
    if counts_output is not None:
        typer.echo(f"counts_written_intervals: {len(written)}")
    typer.echo("demand_label: count_constrained_candidate_demand")
    typer.echo("note: a count target, not observed origin-destination travel")


@manchester_evidence_app.command("lineage")
def manchester_evidence_lineage_command(
    workspace: Annotated[Path, typer.Option("--workspace")],
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Show the chain of fingerprints binding the workflow's artifacts.

    Read-only and offline. A stage with no artifact is reported as absent rather
    than omitted, so a broken chain is visible instead of merely short.
    """

    try:
        catalogue = catalogue_accepted_dft_snapshots(workspace)
    except DftAcquisitionError as exc:
        typer.secho(str(exc), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    snapshots: list[dict[str, object]] = [
        {
            "stage": "observation_snapshot",
            "dataset": snapshot.dataset,
            "id": snapshot.snapshot_id,
            "raw_fingerprint": snapshot.raw_fingerprint,
        }
        for snapshot in catalogue.snapshots
    ]
    policy = ManchesterMapMatchPolicyV11()
    links: list[dict[str, object]] = [*snapshots]
    links.append(
        {
            "stage": "map_match_policy",
            "id": policy.policy_id,
            "raw_fingerprint": policy.fingerprint(),
        }
    )
    links.append(
        {
            "stage": "comparison_contract",
            "id": COMPARISON_CONTRACT_VERSION,
            "raw_fingerprint": comparison_contract_fingerprint(),
            "registered": comparison_contract_is_registered(),
        }
    )
    if output_format == "json":
        _echo_json({"links": links, "network_access_performed": False})
        return
    _require_text_format(output_format)
    typer.echo(f"links: {len(links)}")
    for link in links:
        typer.echo(f"stage: {link['stage']} id={link['id']}")
        typer.echo(f"    fingerprint: {link['raw_fingerprint']}")
        if "registered" in link:
            typer.echo(f"    registered: {str(link['registered']).lower()}")
    if not snapshots:
        typer.echo("absent: no accepted observation snapshot; the chain starts unbound")
    typer.echo("network_access_performed: false")


@manchester_evidence_app.command("export")
def manchester_evidence_export_command(
    destination: Annotated[Path, typer.Option("--destination")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    output_format: Annotated[str, typer.Option("--format")] = "text",
) -> None:
    """Export a permission-safe evidence bundle.

    Only bounded aggregate records are exported. Raw extracts, decoded XML,
    built networks, route pools and demand files stay private, and the export
    refuses if any record still carries a private absolute path.
    """

    records = sorted(MANCHESTER_EVIDENCE_DIR.glob("manchester_*.json"))
    if not records:
        typer.secho(
            "no aggregate evidence record was found to export",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    leaked: list[str] = []
    for record in records:
        text = record.read_text(encoding="utf-8")
        if "/Users/" in text or "/home/" in text or "/private/" in text:
            leaked.append(record.name)
    if leaked:
        typer.secho(
            "refusing to export: these records still carry a private absolute path: "
            + ", ".join(leaked),
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    destination.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    for record in records:
        (destination / record.name).write_text(record.read_text(encoding="utf-8"), encoding="utf-8")
        exported.append(record.name)

    payload = {
        "exported": exported,
        "count": len(exported),
        "workspace_inspected": workspace is not None,
        "raw_artifacts_included": False,
        "private_paths_present": False,
    }
    if output_format == "json":
        _echo_json(payload)
        return
    _require_text_format(output_format)
    typer.echo(f"exported: {len(exported)} aggregate evidence records")
    for name in exported:
        typer.echo(f"    {name}")
    typer.echo("raw_artifacts_included: false")
    typer.echo("private_paths_present: false")
