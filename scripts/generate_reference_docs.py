"""Generate documentation-safe reference artifacts from TrafficTwin code."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from traffictwin.annotations import (
    AnalystAnnotation,
    AnalystAnnotationContract,
    AnalystAnnotationHistory,
    AnalystAnnotationRequest,
    AnalystArtifactReference,
    analyst_annotation_contract,
)
from traffictwin.canonical.records import (
    IncidentRecord,
    InfrastructureRecord,
    TaskRecord,
    TrafficObservationRecord,
    TripRecord,
    VehicleStateRecord,
)
from traffictwin.case_studies import CaseStudyPackManifest
from traffictwin.config.capabilities import CapabilityManifest
from traffictwin.diagnostics.cross_rule import (
    CrossRulePolicy,
    CrossRuleReasoningContract,
    CrossRuleReasoningReport,
    CrossRuleRelationship,
    cross_rule_reasoning_contract,
)
from traffictwin.diagnostics.sensitivity import (
    NearestFlipAnalysis,
    NearestFlipCandidate,
    NearestFlipConstraint,
    NearestFlipContract,
    nearest_flip_contract,
)
from traffictwin.diagnostics.temporal import (
    TemporalDiagnosisContract,
    TemporalDiagnosticAnalysis,
    temporal_diagnosis_contract,
)
from traffictwin.diagnostics.threshold_sweep import (
    ThresholdFlipBoundary,
    ThresholdSensitivityContract,
    ThresholdSensitivityReport,
    ThresholdSweepAxis,
    ThresholdSweepPoint,
    ThresholdSweepRequest,
    TriggerStabilitySummary,
    threshold_sensitivity_contract,
)
from traffictwin.doctor import (
    DoctorCapabilitySummary,
    DoctorCheck,
    DoctorContract,
    DoctorDependency,
    DoctorRegistryDiagnosis,
    DoctorReport,
    DoctorTargets,
    DoctorWorkspaceDiagnosis,
    doctor_contract,
)
from traffictwin.domain.energy import TaskEnergyContract
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.fairness import OperationalFairnessPolicy
from traffictwin.domain.measurement import (
    MeasurementDropoutAudit,
    MeasurementFieldAudit,
    MeasurementImpairmentContract,
    SyntheticMeasurementImpairmentAudit,
    SyntheticMeasurementImpairmentConfig,
    measurement_impairment_contract,
)
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed, SeedDocument
from traffictwin.domain.spatial import TaskRsuTargetContract, VehicleSpatialGridContract
from traffictwin.evaluation.participants import (
    MockParticipantDataset,
    ParticipantAnalysisReport,
)
from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import (
    TemporalEventContext,
    TemporalEvidence,
    TemporalEvidenceConfig,
    TemporalMetricPoint,
)
from traffictwin.experiments.equivalence_testing import (
    EquivalenceConfidenceInterval,
    EquivalenceStudy,
    EquivalenceStudyConfig,
    EquivalenceTestingContract,
    OneSidedEquivalenceTest,
    PairedTostResult,
    equivalence_testing_contract,
)
from traffictwin.experiments.evidence import (
    PairedMetricEndpoint,
    TrainingValidationObservation,
)
from traffictwin.experiments.n_way_ranking import (
    NWayBootstrapSummary,
    NWayFamilyAudit,
    NWayObservation,
    NWayPolicyRank,
    NWayRankingConfig,
    NWayRankingContract,
    NWayRankingEntry,
    NWayRankingStudy,
    n_way_ranking_contract,
)
from traffictwin.experiments.parameter_sweep import (
    ExternalRunRequest,
    ParameterAssignment,
    ParameterSweepContract,
    ParameterSweepExpansion,
    ParameterSweepPoint,
    ParameterSweepRequest,
    ParameterSweepResult,
    SweepAxis,
    SweepResponseRow,
    parameter_sweep_contract,
)
from traffictwin.experiments.portfolio import PortfolioStudyReport
from traffictwin.experiments.power_analysis import (
    PairedPowerCalculation,
    PowerAnalysis,
    PowerAnalysisConfig,
    PowerAnalysisMethodContract,
    power_analysis_method_contract,
)
from traffictwin.experiments.protocol import (
    ExperimentProtocol,
    ExperimentProtocolSlot,
    ProtocolBundleMatch,
)
from traffictwin.experiments.regression_gate import (
    MetricCollectionRegressionContext,
    RegressionAssertion,
    RegressionBlockingFinding,
    RegressionCheck,
    RegressionGateMethodContract,
    RegressionGateReport,
    RegressionGoldenContract,
    RegressionToleranceSpec,
    StatisticalStudyRegressionContext,
    regression_gate_method_contract,
)
from traffictwin.experiments.scenario_mutation import (
    MutationFieldChange,
    MutationFileChange,
    MutationRowChange,
    RowDropoutMutation,
    RsuRemovalMutation,
    ScenarioMutationContract,
    ScenarioMutationPlan,
    ScenarioMutationRequest,
    ScenarioMutationResult,
    TimestampJitterMutation,
    scenario_mutation_contract,
)
from traffictwin.experiments.statistical_study import (
    CommonSeedPairingAudit,
    PairedBootstrapInterval,
    PairedEffectSizes,
    PairedEstimate,
    PairedRandomisationTest,
    PairedStudyConfig,
    PairedStudyObservation,
    StatisticalStudy,
    StatisticalStudyContract,
    statistical_study_contract,
)
from traffictwin.experiments.winner_map import WinnerMapReport
from traffictwin.ingestion.batch import BatchBundleResult, BatchBundleSummary, BatchInputIssue
from traffictwin.ingestion.cache import (
    CanonicalCacheContract,
    CanonicalCacheEntry,
    CanonicalCacheFile,
    CanonicalCacheKey,
    CanonicalCacheMetadata,
    CanonicalCacheStatus,
    canonical_cache_contract,
)
from traffictwin.ingestion.manifest import BundleManifest, FileDeclaration
from traffictwin.ingestion.manifest_inference import (
    CanonicalisationManifest,
    ManifestInferenceContract,
    ManifestInferenceDraft,
    ManifestInferenceSelections,
    manifest_inference_contract,
)
from traffictwin.ingestion.streaming import (
    CanonicalChunk,
    StreamingBundleValidationResult,
    StreamingCanonicalisationConfig,
    StreamingCanonicalisationSummary,
)
from traffictwin.integration.external import (
    ExternalAdapterContract,
    ExternalBlocker,
    ExternalConversionProfile,
    ExternalDiscoveryReport,
    ExternalFieldSemantic,
    ExternalProvenanceObservation,
    ExternalProvenanceRequirement,
    ExternalSourceCatalogue,
    ExternalSourceDiscovery,
    ExternalSourceInspection,
    ExternalValidationSummary,
    SourceMarker,
    external_source_catalogue,
)
from traffictwin.integration.manchester import (
    AdmittedComparisonPair,
    ArchiveMember,
    ArchivePolicy,
    BodsAcquisitionRequest,
    BodsAcquisitionResult,
    BodsLiveRefreshSummary,
    BodsReplayRequest,
    BodsReplayResult,
    CalibrationCandidateEvaluation,
    CalibrationCandidateInput,
    CalibrationEvidencePair,
    CalibrationIntervalContent,
    CalibrationObjectiveResult,
    CalibrationParameterBound,
    CalibrationParameterValue,
    ComparisonIntervalContent,
    ComparisonLineage,
    ComparisonMetricResult,
    DftAadfParseReport,
    DftAadfRecord,
    DftAcceptedDatasetCounts,
    DftAcceptedSnapshotCatalogue,
    DftAcceptedSnapshotSummary,
    DftAcquisitionRequest,
    DftAcquisitionResult,
    DftCountPointLayerSummary,
    DftCountPointParseReport,
    DftCountPointRecord,
    DftFinding,
    DftManchesterScope,
    DftMemberRef,
    DftParseCounts,
    DftRawCountParseReport,
    DftRawCountRecord,
    DftReplayResult,
    DftRoadLocation,
    DftSourceRefreshSummary,
    DftSurveyFilterOptions,
    DftSurveyObservation,
    DftSurveyView,
    DftSurveyViewCounts,
    DftSurveyViewQuery,
    DftVehicleClassCounts,
    EndpointPolicy,
    ExcludedCalibrationInterval,
    ExcludedComparisonInterval,
    FreshnessEvaluationRequest,
    ManchesterCalibrationContract,
    ManchesterCalibrationReport,
    ManchesterComparisonMetricContract,
    ManchesterHttpMetadata,
    ManchesterHttpSnapshotParts,
    ManchesterLineageArtifactReference,
    ManchesterLineageEdge,
    ManchesterLineageStage,
    ManchesterMapLayerManifest,
    ManchesterMapPoint,
    ManchesterMapScene,
    ManchesterPriorSnapshotLink,
    ManchesterProjectedRoadRow,
    ManchesterProjectionCounts,
    ManchesterProjectionExclusion,
    ManchesterProjectionReport,
    ManchesterQuarantineManifest,
    ManchesterQuarantineReceipt,
    ManchesterRawMember,
    ManchesterRequestIdentity,
    ManchesterResearchLineage,
    ManchesterRetrievalWindow,
    ManchesterRoadObservation,
    ManchesterSceneFilePublication,
    ManchesterScenePublicationReceipt,
    ManchesterScenePublicationRequest,
    ManchesterSnapshotFinding,
    ManchesterSnapshotManifest,
    ManchesterSnapshotPolicy,
    ManchesterSnapshotReceipt,
    ManchesterSourceIdentity,
    ManchesterSpatialPointEvidence,
    MapLayerCounts,
    MapLayerRequest,
    MapLayerStyle,
    ObservedCalibrationInterval,
    ObservedComparisonInterval,
    ObservedSimulationComparison,
    SafeResponseMetadata,
    SimulatedCalibrationInterval,
    SimulatedComparisonInterval,
    SourceFreshnessEvaluation,
    SourceFreshnessPolicy,
    SpatialAdmissionCounts,
    SpatialAdmissionPolicy,
    SpatialAdmissionReport,
    SpatialAdmissionResult,
    SpatialCoordinateBounds,
    TfgmAcquisitionRequest,
    TfgmAcquisitionResult,
    TfgmReplayRequest,
    TfgmReplayResult,
    TfgmSelectedMemberEvidence,
    TfgmSignalLayerSummary,
    TfgmSourceRefreshSummary,
    TransportPolicy,
    WebtrisAcceptedProductCounts,
    WebtrisAcceptedSnapshotCatalogue,
    WebtrisAcceptedSnapshotSummary,
    WebtrisAcquisitionRequest,
    WebtrisAcquisitionResult,
    WebtrisChartSeries,
    WebtrisReplayRequest,
    WebtrisReplayResult,
    WebtrisSiteLayerSummary,
    WebtrisSourceRefreshSummary,
    WebtrisTimeseriesEvidence,
    WebtrisTimeseriesFilter,
    WebtrisTimeseriesResult,
    XmlPolicy,
    map_style_catalogue,
    spatial_policy_catalogue,
)
from traffictwin.integration.sumo.contract import SumoSourceContract, sumo_source_contract
from traffictwin.integration.sumo.models import (
    SumoImportResult,
    SumoResultManifest,
    SumoSummaryStep,
    SumoTripObservation,
    SumoValidationResult,
)
from traffictwin.integration.sumo_execution.models import (
    SumoExecutionImportRecord,
    SumoExecutionReceipt,
    SumoImportOutcome,
    SumoPreflightReport,
    SumoRunnerContract,
    SumoRunPreset,
    SumoRunRequest,
    SumoRuntimeStatus,
    SumoWorkflowReceipt,
    SumoWorkflowRequest,
)
from traffictwin.integration.sumo_execution.service import sumo_execution_contract
from traffictwin.integration.tos.analysis import tos_analysis_catalogue
from traffictwin.integration.tos.analysis_models import (
    TosCampaignComparisonReport,
    TosEvaluationMatrix,
    TosGeneralisationMatrix,
    TosReproducibilityAudit,
    TosRsuRunSummary,
    TosTaskOutcomeSummary,
    TosTraceSummary,
    TosTrainingRun,
)
from traffictwin.integration.tos.contract import TosSourceContract, tos_source_contract
from traffictwin.integration.tos.contract_v2 import (
    ArtifactValidationReport,
    AuditedSourceFile,
    ObservedArraySchema,
    OccupancyReconciliationReport,
    OccupancySpan,
    TosSourceContractV2,
    UnavailableField,
    V2Finding,
    VecTaskActionObservation,
    VecTripJoin,
    VecVehicleAttributeObservation,
    tos_source_contract_v2,
)
from traffictwin.integration.tos.metrics import tos_metric_catalogue
from traffictwin.integration.tos.models import (
    TosEvaluationRun,
    TosReplayFrame,
    TosTaskSample,
    TosValidationReport,
)
from traffictwin.integration.tos.publication import (
    ExcludedArtifact,
    IncludedArtifact,
    PublicationPermissionBasis,
    PublicationSourceLabels,
    RepositoryCitation,
    SanitisationDeclaration,
    TosPublicationManifest,
    default_excluded_inventory,
    permitted_artifact_kinds,
)
from traffictwin.integration.tos.readiness import TosIntegrationReadinessReport
from traffictwin.integration.tos.supervisor import TosSupervisorPackManifest
from traffictwin.integration.vec_identity.models import (
    VecIdentityContract,
    VecIdentityCoverageReport,
    VecIdentityFinding,
    VecIdentitySnapshot,
    VecVehicleMobilityObservation,
    vec_identity_contract,
)
from traffictwin.integration.vec_interface.models import (
    VecAdmissionComparison,
    VecArtifactInspection,
    VecInterfaceContract,
    VecInterfaceSnapshot,
    VecMetricDelta,
    VecOperationStatus,
    VecRepositorySnapshot,
    vec_interface_contract,
)
from traffictwin.integration.vec_orchestration.models import (
    VecExecutionImportRecord,
    VecImportOutcome,
    VecOrchestrationContract,
    VecPresetWorkload,
    VecWorkflowReceipt,
    VecWorkflowRequest,
    VecWorkflowStage,
)
from traffictwin.integration.vec_orchestration.service import vec_orchestration_contract
from traffictwin.integration.vec_preprocessing.models import (
    VecFcdMetadata,
    VecFcdPreflightReport,
    VecFcdPreprocessingContract,
    VecFcdPreprocessReceipt,
    VecFcdPreprocessRequest,
    VecFileEvidence,
    VecGreedyUrbanPlacement,
    VecNetworkMetadata,
    VecPreflightFinding,
    VecPreprocessCommand,
    VecSourceScriptEvidence,
    vec_fcd_preprocessing_contract,
)
from traffictwin.integration.vec_publication.models import (
    VecDissertationPackContract,
    VecDissertationPackManifest,
    VecSanitisedMatchedSample,
    vec_dissertation_pack_contract,
)
from traffictwin.integration.vec_reproduction.models import (
    VecNumericTolerance,
    VecRepeatRunEvidence,
    VecReproductionCheck,
    VecReproductionContract,
    VecReproductionReport,
    VecReproductionRequest,
    VecReproductionSource,
    VecReproductionSummary,
    vec_reproduction_contract,
)
from traffictwin.integration.vec_research.models import (
    VecEndToEndContract,
    VecEndToEndManifest,
    VecEndToEndReceipt,
    VecEndToEndVerification,
    vec_end_to_end_contract,
)
from traffictwin.integration.vec_runner.models import (
    VecExecutionReceipt,
    VecRepositoryEvidence,
    VecRunnerContract,
    VecRunnerFileEvidence,
    VecRunnerFinding,
    VecRunnerPreflightReport,
    VecRunRequest,
    VecRuntimeEvidence,
    vec_runner_contract,
)
from traffictwin.integration.vec_science.models import (
    VecMetricAdmissionDecision,
    VecRuleReadiness,
    VecScientificAdmissionContract,
    VecScientificAdmissionReport,
    vec_scientific_admission_contract,
)
from traffictwin.integration.vec_task_join.models import (
    VecJoinedTaskObservation,
    VecTaskJoinContract,
    VecTaskJoinReport,
    vec_task_join_contract,
)
from traffictwin.integration.vec_trip_join.models import (
    VecJourneyDurationSummary,
    VecMatchedTrip,
    VecTripExclusion,
    VecTripJoinContract,
    VecTripJoinDataset,
    VecTripJoinReport,
    vec_trip_join_contract,
)
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import (
    MetricPluginApiContract,
    MetricPluginRegistryReport,
    PluginMetricContract,
    PluginMetricResult,
    PluginOutputSchema,
    PluginTableRequirement,
    metric_plugin_api_contract,
)
from traffictwin.metrics.results import MetricCollection
from traffictwin.metrics.windowed import (
    MetricWindow,
    WindowedMetricConfig,
    WindowedMetricSeries,
    WindowMetricSlice,
)
from traffictwin.provenance.completeness import (
    ClaimCompletenessAssessment,
    ProvenanceCompletenessContract,
    ProvenanceCompletenessReport,
    provenance_completeness_contract,
)
from traffictwin.provenance.contributions import (
    MetricContributionReport,
    WindowMetricContributionReport,
)
from traffictwin.provenance.differences import (
    DifferenceContributionReport,
    DifferenceContributionRow,
    DifferenceProvenanceContract,
    difference_provenance_contract,
)
from traffictwin.provenance.graph_export import (
    GraphExportEdge,
    GraphExportNode,
    ProvenanceGraphExportContract,
    ProvenanceGraphView,
    provenance_graph_export_contract,
)
from traffictwin.provenance.models import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceTrace,
    SourceRowPreview,
)
from traffictwin.registry_search import (
    RegistrySearchContract,
    RegistrySearchHit,
    RegistrySearchResult,
    registry_search_contract,
)
from traffictwin.release.compatibility import (
    V06RegistryCopyPreview,
    V06RegistryCopyReceipt,
    V07WorkspaceContract,
    V07WorkspaceInspection,
    V07WorkspaceManifest,
    v07_workspace_contract,
)
from traffictwin.release.deployment import SyntheticStaticSiteManifest
from traffictwin.rendering.findings import DiagnosticNarrative
from traffictwin.reporting.diffing import (
    ReportClaimDiff,
    ReportDiffContract,
    ReportFieldChange,
    ReportSectionDiff,
    StructuredReportDiff,
    report_diff_contract,
)
from traffictwin.reporting.executive import (
    ExecutiveSummary,
    ExecutiveSummaryAvailability,
    ExecutiveSummaryContract,
    ExecutiveSummaryHighlight,
    ExecutiveSummaryProvenanceLink,
    executive_summary_contract,
)
from traffictwin.reporting.latex import (
    LatexExportContract,
    ResearchExportFile,
    ResearchExportProjection,
    ResearchExportReceipt,
    ResearchFigureEntry,
    latex_export_contract,
)
from traffictwin.reporting.models import (
    ReportClaimExclusion,
    ReportClaimReference,
    ReportClaimSnapshot,
    ResearchReport,
)
from traffictwin.research_object import (
    CitationAuthor,
    ResearchObjectArchiveReceipt,
    ResearchObjectContract,
    ResearchObjectExclusion,
    ResearchObjectInventoryEntry,
    ResearchObjectManifest,
    ResearchObjectRequest,
    ResearchObjectSoftware,
    ResearchObjectSource,
    ResearchObjectVerification,
    ResolvedInclusionPolicy,
    research_object_contract,
)
from traffictwin.rules.catalogue import rule_catalogue
from traffictwin.rules.config import R7Config, RuleSetConfig
from traffictwin.rules.declarative import (
    BooleanPredicateDefinition,
    DeclarativeRecommendation,
    DeclarativeRuleContract,
    DeclarativeRuleDefinition,
    DeclarativeRuleRegistryReport,
    MetadataRequirement,
    NumericPredicateDefinition,
    PredicateEvaluation,
    declarative_rule_contract,
)
from traffictwin.rules.evaluation import FaultInjectionEvaluationReport
from traffictwin.rules.r7_fairness import r7_rule_definition
from traffictwin.rules.r8_energy_anomaly import (
    R8EnergyDiagnosisContract,
    r8_energy_diagnosis_contract,
)
from traffictwin.storage.migrations import (
    RegistryMigrationContract,
    RegistryMigrationDescriptor,
    RegistryMigrationResult,
    RegistryMigrationStatus,
    registry_migration_contract,
)
from traffictwin.synthetic.config import SyntheticScenarioConfig
from traffictwin.ui.audit import AccessibilityAuditReport
from traffictwin.validation.codes import ValidationCode
from traffictwin.validation.report import ValidationReport

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "reference" / "generated"


MODEL_TYPES: dict[str, type[BaseModel]] = {
    "ScenarioSeed": ScenarioSeed,
    "SeedDocument": SeedDocument,
    "Experiment": Experiment,
    "Run": Run,
    "CapabilityManifest": CapabilityManifest,
    "DoctorCheck": DoctorCheck,
    "DoctorDependency": DoctorDependency,
    "DoctorCapabilitySummary": DoctorCapabilitySummary,
    "DoctorWorkspaceDiagnosis": DoctorWorkspaceDiagnosis,
    "DoctorRegistryDiagnosis": DoctorRegistryDiagnosis,
    "DoctorTargets": DoctorTargets,
    "DoctorReport": DoctorReport,
    "DoctorContract": DoctorContract,
    "CitationAuthor": CitationAuthor,
    "ResearchObjectRequest": ResearchObjectRequest,
    "ResolvedInclusionPolicy": ResolvedInclusionPolicy,
    "ResearchObjectInventoryEntry": ResearchObjectInventoryEntry,
    "ResearchObjectExclusion": ResearchObjectExclusion,
    "ResearchObjectSource": ResearchObjectSource,
    "ResearchObjectSoftware": ResearchObjectSoftware,
    "ResearchObjectManifest": ResearchObjectManifest,
    "ResearchObjectContract": ResearchObjectContract,
    "ResearchObjectArchiveReceipt": ResearchObjectArchiveReceipt,
    "ResearchObjectVerification": ResearchObjectVerification,
    "AnalystArtifactReference": AnalystArtifactReference,
    "AnalystAnnotationRequest": AnalystAnnotationRequest,
    "AnalystAnnotation": AnalystAnnotation,
    "AnalystAnnotationHistory": AnalystAnnotationHistory,
    "AnalystAnnotationContract": AnalystAnnotationContract,
    "ReportClaimSnapshot": ReportClaimSnapshot,
    "ReportFieldChange": ReportFieldChange,
    "ReportClaimDiff": ReportClaimDiff,
    "ReportSectionDiff": ReportSectionDiff,
    "StructuredReportDiff": StructuredReportDiff,
    "ReportDiffContract": ReportDiffContract,
    "ExecutiveSummaryAvailability": ExecutiveSummaryAvailability,
    "ExecutiveSummaryProvenanceLink": ExecutiveSummaryProvenanceLink,
    "ExecutiveSummaryHighlight": ExecutiveSummaryHighlight,
    "ExecutiveSummary": ExecutiveSummary,
    "ExecutiveSummaryContract": ExecutiveSummaryContract,
    "RegistrySearchHit": RegistrySearchHit,
    "RegistrySearchResult": RegistrySearchResult,
    "RegistrySearchContract": RegistrySearchContract,
    "RegistryMigrationDescriptor": RegistryMigrationDescriptor,
    "RegistryMigrationStatus": RegistryMigrationStatus,
    "RegistryMigrationResult": RegistryMigrationResult,
    "RegistryMigrationContract": RegistryMigrationContract,
    "V07WorkspaceContract": V07WorkspaceContract,
    "V07WorkspaceManifest": V07WorkspaceManifest,
    "V07WorkspaceInspection": V07WorkspaceInspection,
    "V06RegistryCopyPreview": V06RegistryCopyPreview,
    "V06RegistryCopyReceipt": V06RegistryCopyReceipt,
    "ManchesterSourceIdentity": ManchesterSourceIdentity,
    "ManchesterRequestIdentity": ManchesterRequestIdentity,
    "ManchesterRetrievalWindow": ManchesterRetrievalWindow,
    "ManchesterHttpMetadata": ManchesterHttpMetadata,
    "ManchesterRawMember": ManchesterRawMember,
    "ManchesterSnapshotFinding": ManchesterSnapshotFinding,
    "ManchesterPriorSnapshotLink": ManchesterPriorSnapshotLink,
    "ManchesterSnapshotPolicy": ManchesterSnapshotPolicy,
    "ManchesterSnapshotManifest": ManchesterSnapshotManifest,
    "ManchesterSnapshotReceipt": ManchesterSnapshotReceipt,
    "ManchesterQuarantineManifest": ManchesterQuarantineManifest,
    "ManchesterQuarantineReceipt": ManchesterQuarantineReceipt,
    "BodsAcquisitionRequest": BodsAcquisitionRequest,
    "BodsAcquisitionResult": BodsAcquisitionResult,
    "BodsReplayRequest": BodsReplayRequest,
    "BodsReplayResult": BodsReplayResult,
    "BodsLiveRefreshSummary": BodsLiveRefreshSummary,
    "CalibrationParameterBound": CalibrationParameterBound,
    "ManchesterCalibrationContract": ManchesterCalibrationContract,
    "CalibrationIntervalContent": CalibrationIntervalContent,
    "ObservedCalibrationInterval": ObservedCalibrationInterval,
    "SimulatedCalibrationInterval": SimulatedCalibrationInterval,
    "CalibrationParameterValue": CalibrationParameterValue,
    "CalibrationCandidateInput": CalibrationCandidateInput,
    "CalibrationEvidencePair": CalibrationEvidencePair,
    "ExcludedCalibrationInterval": ExcludedCalibrationInterval,
    "CalibrationObjectiveResult": CalibrationObjectiveResult,
    "CalibrationCandidateEvaluation": CalibrationCandidateEvaluation,
    "ManchesterCalibrationReport": ManchesterCalibrationReport,
    "ManchesterComparisonMetricContract": ManchesterComparisonMetricContract,
    "ComparisonIntervalContent": ComparisonIntervalContent,
    "ObservedComparisonInterval": ObservedComparisonInterval,
    "SimulatedComparisonInterval": SimulatedComparisonInterval,
    "ComparisonLineage": ComparisonLineage,
    "AdmittedComparisonPair": AdmittedComparisonPair,
    "ExcludedComparisonInterval": ExcludedComparisonInterval,
    "ComparisonMetricResult": ComparisonMetricResult,
    "ObservedSimulationComparison": ObservedSimulationComparison,
    "ManchesterLineageArtifactReference": ManchesterLineageArtifactReference,
    "ManchesterLineageStage": ManchesterLineageStage,
    "ManchesterLineageEdge": ManchesterLineageEdge,
    "ManchesterResearchLineage": ManchesterResearchLineage,
    "ManchesterHttpSnapshotParts": ManchesterHttpSnapshotParts,
    "DftMemberRef": DftMemberRef,
    "DftManchesterScope": DftManchesterScope,
    "DftVehicleClassCounts": DftVehicleClassCounts,
    "DftRoadLocation": DftRoadLocation,
    "DftSourceRefreshSummary": DftSourceRefreshSummary,
    "DftRawCountRecord": DftRawCountRecord,
    "DftCountPointRecord": DftCountPointRecord,
    "DftAadfRecord": DftAadfRecord,
    "DftFinding": DftFinding,
    "DftParseCounts": DftParseCounts,
    "DftRawCountParseReport": DftRawCountParseReport,
    "DftCountPointParseReport": DftCountPointParseReport,
    "DftCountPointLayerSummary": DftCountPointLayerSummary,
    "DftAadfParseReport": DftAadfParseReport,
    "DftSurveyFilterOptions": DftSurveyFilterOptions,
    "DftSurveyViewQuery": DftSurveyViewQuery,
    "DftSurveyObservation": DftSurveyObservation,
    "DftSurveyViewCounts": DftSurveyViewCounts,
    "DftSurveyView": DftSurveyView,
    "DftAcquisitionRequest": DftAcquisitionRequest,
    "DftAcquisitionResult": DftAcquisitionResult,
    "DftAcceptedDatasetCounts": DftAcceptedDatasetCounts,
    "DftAcceptedSnapshotSummary": DftAcceptedSnapshotSummary,
    "DftAcceptedSnapshotCatalogue": DftAcceptedSnapshotCatalogue,
    "DftReplayResult": DftReplayResult,
    "FreshnessEvaluationRequest": FreshnessEvaluationRequest,
    "SourceFreshnessPolicy": SourceFreshnessPolicy,
    "SourceFreshnessEvaluation": SourceFreshnessEvaluation,
    "ManchesterRoadObservation": ManchesterRoadObservation,
    "ManchesterProjectedRoadRow": ManchesterProjectedRoadRow,
    "ManchesterProjectionExclusion": ManchesterProjectionExclusion,
    "ManchesterProjectionCounts": ManchesterProjectionCounts,
    "ManchesterProjectionReport": ManchesterProjectionReport,
    "MapLayerStyle": MapLayerStyle,
    "MapLayerRequest": MapLayerRequest,
    "ManchesterMapPoint": ManchesterMapPoint,
    "MapLayerCounts": MapLayerCounts,
    "ManchesterMapLayerManifest": ManchesterMapLayerManifest,
    "ManchesterMapScene": ManchesterMapScene,
    "ManchesterScenePublicationRequest": ManchesterScenePublicationRequest,
    "ManchesterSceneFilePublication": ManchesterSceneFilePublication,
    "ManchesterScenePublicationReceipt": ManchesterScenePublicationReceipt,
    "ManchesterSpatialPointEvidence": ManchesterSpatialPointEvidence,
    "SpatialAdmissionPolicy": SpatialAdmissionPolicy,
    "SpatialCoordinateBounds": SpatialCoordinateBounds,
    "SpatialAdmissionResult": SpatialAdmissionResult,
    "SpatialAdmissionCounts": SpatialAdmissionCounts,
    "SpatialAdmissionReport": SpatialAdmissionReport,
    "TfgmSelectedMemberEvidence": TfgmSelectedMemberEvidence,
    "TfgmSignalLayerSummary": TfgmSignalLayerSummary,
    "TfgmSourceRefreshSummary": TfgmSourceRefreshSummary,
    "TfgmAcquisitionRequest": TfgmAcquisitionRequest,
    "TfgmAcquisitionResult": TfgmAcquisitionResult,
    "TfgmReplayRequest": TfgmReplayRequest,
    "TfgmReplayResult": TfgmReplayResult,
    "WebtrisAcquisitionRequest": WebtrisAcquisitionRequest,
    "WebtrisAcquisitionResult": WebtrisAcquisitionResult,
    "WebtrisAcceptedProductCounts": WebtrisAcceptedProductCounts,
    "WebtrisAcceptedSnapshotSummary": WebtrisAcceptedSnapshotSummary,
    "WebtrisAcceptedSnapshotCatalogue": WebtrisAcceptedSnapshotCatalogue,
    "WebtrisChartSeries": WebtrisChartSeries,
    "WebtrisReplayRequest": WebtrisReplayRequest,
    "WebtrisReplayResult": WebtrisReplayResult,
    "WebtrisSiteLayerSummary": WebtrisSiteLayerSummary,
    "WebtrisSourceRefreshSummary": WebtrisSourceRefreshSummary,
    "WebtrisTimeseriesEvidence": WebtrisTimeseriesEvidence,
    "WebtrisTimeseriesFilter": WebtrisTimeseriesFilter,
    "WebtrisTimeseriesResult": WebtrisTimeseriesResult,
    "EndpointPolicy": EndpointPolicy,
    "TransportPolicy": TransportPolicy,
    "SafeResponseMetadata": SafeResponseMetadata,
    "ArchivePolicy": ArchivePolicy,
    "ArchiveMember": ArchiveMember,
    "XmlPolicy": XmlPolicy,
    "TaskEnergyContract": TaskEnergyContract,
    "OperationalFairnessPolicy": OperationalFairnessPolicy,
    "SyntheticScenarioConfig": SyntheticScenarioConfig,
    "SyntheticMeasurementImpairmentConfig": SyntheticMeasurementImpairmentConfig,
    "MeasurementFieldAudit": MeasurementFieldAudit,
    "MeasurementDropoutAudit": MeasurementDropoutAudit,
    "SyntheticMeasurementImpairmentAudit": SyntheticMeasurementImpairmentAudit,
    "MeasurementImpairmentContract": MeasurementImpairmentContract,
    "TaskRsuTargetContract": TaskRsuTargetContract,
    "VehicleSpatialGridContract": VehicleSpatialGridContract,
    "BundleManifest": BundleManifest,
    "FileDeclaration": FileDeclaration,
    "ManifestInferenceDraft": ManifestInferenceDraft,
    "ManifestInferenceSelections": ManifestInferenceSelections,
    "CanonicalisationManifest": CanonicalisationManifest,
    "ManifestInferenceContract": ManifestInferenceContract,
    "BatchInputIssue": BatchInputIssue,
    "BatchBundleResult": BatchBundleResult,
    "BatchBundleSummary": BatchBundleSummary,
    "CanonicalCacheKey": CanonicalCacheKey,
    "CanonicalCacheFile": CanonicalCacheFile,
    "CanonicalCacheEntry": CanonicalCacheEntry,
    "CanonicalCacheMetadata": CanonicalCacheMetadata,
    "CanonicalCacheStatus": CanonicalCacheStatus,
    "CanonicalCacheContract": CanonicalCacheContract,
    "SourceMarker": SourceMarker,
    "ExternalFieldSemantic": ExternalFieldSemantic,
    "ExternalProvenanceRequirement": ExternalProvenanceRequirement,
    "ExternalProvenanceObservation": ExternalProvenanceObservation,
    "ExternalConversionProfile": ExternalConversionProfile,
    "ExternalBlocker": ExternalBlocker,
    "ExternalAdapterContract": ExternalAdapterContract,
    "ExternalSourceDiscovery": ExternalSourceDiscovery,
    "ExternalDiscoveryReport": ExternalDiscoveryReport,
    "ExternalValidationSummary": ExternalValidationSummary,
    "ExternalSourceInspection": ExternalSourceInspection,
    "ExternalSourceCatalogue": ExternalSourceCatalogue,
    "StreamingCanonicalisationConfig": StreamingCanonicalisationConfig,
    "CanonicalChunk": CanonicalChunk,
    "StreamingCanonicalisationSummary": StreamingCanonicalisationSummary,
    "StreamingBundleValidationResult": StreamingBundleValidationResult,
    "TaskRecord": TaskRecord,
    "InfrastructureRecord": InfrastructureRecord,
    "VehicleStateRecord": VehicleStateRecord,
    "TrafficObservationRecord": TrafficObservationRecord,
    "TripRecord": TripRecord,
    "IncidentRecord": IncidentRecord,
    "ValidationReport": ValidationReport,
    "SumoResultManifest": SumoResultManifest,
    "SumoTripObservation": SumoTripObservation,
    "SumoSummaryStep": SumoSummaryStep,
    "SumoValidationResult": SumoValidationResult,
    "SumoImportResult": SumoImportResult,
    "SumoSourceContract": SumoSourceContract,
    "VecGreedyUrbanPlacement": VecGreedyUrbanPlacement,
    "VecFcdPreprocessRequest": VecFcdPreprocessRequest,
    "VecFileEvidence": VecFileEvidence,
    "VecSourceScriptEvidence": VecSourceScriptEvidence,
    "VecNetworkMetadata": VecNetworkMetadata,
    "VecFcdMetadata": VecFcdMetadata,
    "VecPreflightFinding": VecPreflightFinding,
    "VecFcdPreflightReport": VecFcdPreflightReport,
    "VecPreprocessCommand": VecPreprocessCommand,
    "VecFcdPreprocessReceipt": VecFcdPreprocessReceipt,
    "VecFcdPreprocessingContract": VecFcdPreprocessingContract,
    "VecIdentityFinding": VecIdentityFinding,
    "VecIdentityCoverageReport": VecIdentityCoverageReport,
    "VecIdentitySnapshot": VecIdentitySnapshot,
    "VecVehicleMobilityObservation": VecVehicleMobilityObservation,
    "VecIdentityContract": VecIdentityContract,
    "VecRepositorySnapshot": VecRepositorySnapshot,
    "VecOperationStatus": VecOperationStatus,
    "VecInterfaceSnapshot": VecInterfaceSnapshot,
    "VecMetricDelta": VecMetricDelta,
    "VecAdmissionComparison": VecAdmissionComparison,
    "VecArtifactInspection": VecArtifactInspection,
    "VecInterfaceContract": VecInterfaceContract,
    "VecNumericTolerance": VecNumericTolerance,
    "VecReproductionRequest": VecReproductionRequest,
    "VecReproductionCheck": VecReproductionCheck,
    "VecReproductionSource": VecReproductionSource,
    "VecReproductionSummary": VecReproductionSummary,
    "VecRepeatRunEvidence": VecRepeatRunEvidence,
    "VecReproductionReport": VecReproductionReport,
    "VecReproductionContract": VecReproductionContract,
    "VecJoinedTaskObservation": VecJoinedTaskObservation,
    "VecTaskJoinReport": VecTaskJoinReport,
    "VecTaskJoinContract": VecTaskJoinContract,
    "VecMatchedTrip": VecMatchedTrip,
    "VecTripExclusion": VecTripExclusion,
    "VecJourneyDurationSummary": VecJourneyDurationSummary,
    "VecTripJoinReport": VecTripJoinReport,
    "VecTripJoinDataset": VecTripJoinDataset,
    "VecTripJoinContract": VecTripJoinContract,
    "VecRunRequest": VecRunRequest,
    "VecRunnerFinding": VecRunnerFinding,
    "VecRunnerFileEvidence": VecRunnerFileEvidence,
    "VecRepositoryEvidence": VecRepositoryEvidence,
    "VecRuntimeEvidence": VecRuntimeEvidence,
    "VecRunnerPreflightReport": VecRunnerPreflightReport,
    "VecExecutionReceipt": VecExecutionReceipt,
    "VecRunnerContract": VecRunnerContract,
    "VecPresetWorkload": VecPresetWorkload,
    "VecWorkflowRequest": VecWorkflowRequest,
    "VecWorkflowStage": VecWorkflowStage,
    "VecExecutionImportRecord": VecExecutionImportRecord,
    "VecImportOutcome": VecImportOutcome,
    "VecWorkflowReceipt": VecWorkflowReceipt,
    "VecOrchestrationContract": VecOrchestrationContract,
    "SumoRunPreset": SumoRunPreset,
    "SumoRuntimeStatus": SumoRuntimeStatus,
    "SumoRunRequest": SumoRunRequest,
    "SumoPreflightReport": SumoPreflightReport,
    "SumoExecutionReceipt": SumoExecutionReceipt,
    "SumoImportOutcome": SumoImportOutcome,
    "SumoExecutionImportRecord": SumoExecutionImportRecord,
    "SumoWorkflowRequest": SumoWorkflowRequest,
    "SumoWorkflowReceipt": SumoWorkflowReceipt,
    "SumoRunnerContract": SumoRunnerContract,
    "VecMetricAdmissionDecision": VecMetricAdmissionDecision,
    "VecRuleReadiness": VecRuleReadiness,
    "VecScientificAdmissionReport": VecScientificAdmissionReport,
    "VecScientificAdmissionContract": VecScientificAdmissionContract,
    "MetricEngineConfig": MetricEngineConfig,
    "PluginTableRequirement": PluginTableRequirement,
    "PluginOutputSchema": PluginOutputSchema,
    "PluginMetricContract": PluginMetricContract,
    "PluginMetricResult": PluginMetricResult,
    "MetricPluginRegistryReport": MetricPluginRegistryReport,
    "MetricPluginApiContract": MetricPluginApiContract,
    "MetricCollection": MetricCollection,
    "WindowedMetricConfig": WindowedMetricConfig,
    "MetricWindow": MetricWindow,
    "WindowMetricSlice": WindowMetricSlice,
    "WindowedMetricSeries": WindowedMetricSeries,
    "TemporalEvidenceConfig": TemporalEvidenceConfig,
    "TemporalMetricPoint": TemporalMetricPoint,
    "TemporalEventContext": TemporalEventContext,
    "TemporalEvidence": TemporalEvidence,
    "TemporalDiagnosisContract": TemporalDiagnosisContract,
    "TemporalDiagnosticAnalysis": TemporalDiagnosticAnalysis,
    "NearestFlipConstraint": NearestFlipConstraint,
    "NearestFlipCandidate": NearestFlipCandidate,
    "NearestFlipAnalysis": NearestFlipAnalysis,
    "NearestFlipContract": NearestFlipContract,
    "ThresholdSweepAxis": ThresholdSweepAxis,
    "ThresholdSweepRequest": ThresholdSweepRequest,
    "ThresholdSweepPoint": ThresholdSweepPoint,
    "ThresholdFlipBoundary": ThresholdFlipBoundary,
    "TriggerStabilitySummary": TriggerStabilitySummary,
    "ThresholdSensitivityReport": ThresholdSensitivityReport,
    "ThresholdSensitivityContract": ThresholdSensitivityContract,
    "CrossRulePolicy": CrossRulePolicy,
    "CrossRuleRelationship": CrossRuleRelationship,
    "CrossRuleReasoningReport": CrossRuleReasoningReport,
    "CrossRuleReasoningContract": CrossRuleReasoningContract,
    "EvidencePack": EvidencePack,
    "PairedMetricEndpoint": PairedMetricEndpoint,
    "TrainingValidationObservation": TrainingValidationObservation,
    "PairedStudyConfig": PairedStudyConfig,
    "PairedStudyObservation": PairedStudyObservation,
    "CommonSeedPairingAudit": CommonSeedPairingAudit,
    "PairedEstimate": PairedEstimate,
    "PairedBootstrapInterval": PairedBootstrapInterval,
    "PairedRandomisationTest": PairedRandomisationTest,
    "PairedEffectSizes": PairedEffectSizes,
    "StatisticalStudy": StatisticalStudy,
    "StatisticalStudyContract": StatisticalStudyContract,
    "EquivalenceStudyConfig": EquivalenceStudyConfig,
    "OneSidedEquivalenceTest": OneSidedEquivalenceTest,
    "EquivalenceConfidenceInterval": EquivalenceConfidenceInterval,
    "PairedTostResult": PairedTostResult,
    "EquivalenceStudy": EquivalenceStudy,
    "EquivalenceTestingContract": EquivalenceTestingContract,
    "RegressionToleranceSpec": RegressionToleranceSpec,
    "RegressionAssertion": RegressionAssertion,
    "MetricCollectionRegressionContext": MetricCollectionRegressionContext,
    "StatisticalStudyRegressionContext": StatisticalStudyRegressionContext,
    "RegressionGoldenContract": RegressionGoldenContract,
    "RegressionBlockingFinding": RegressionBlockingFinding,
    "RegressionCheck": RegressionCheck,
    "RegressionGateReport": RegressionGateReport,
    "RegressionGateMethodContract": RegressionGateMethodContract,
    "PowerAnalysisConfig": PowerAnalysisConfig,
    "PairedPowerCalculation": PairedPowerCalculation,
    "PowerAnalysis": PowerAnalysis,
    "PowerAnalysisMethodContract": PowerAnalysisMethodContract,
    "NWayRankingConfig": NWayRankingConfig,
    "NWayObservation": NWayObservation,
    "NWayFamilyAudit": NWayFamilyAudit,
    "NWayBootstrapSummary": NWayBootstrapSummary,
    "NWayPolicyRank": NWayPolicyRank,
    "NWayRankingEntry": NWayRankingEntry,
    "NWayRankingStudy": NWayRankingStudy,
    "NWayRankingContract": NWayRankingContract,
    "SweepAxis": SweepAxis,
    "ParameterAssignment": ParameterAssignment,
    "ExternalRunRequest": ExternalRunRequest,
    "ParameterSweepPoint": ParameterSweepPoint,
    "SweepResponseRow": SweepResponseRow,
    "ParameterSweepRequest": ParameterSweepRequest,
    "ParameterSweepExpansion": ParameterSweepExpansion,
    "ParameterSweepResult": ParameterSweepResult,
    "ParameterSweepContract": ParameterSweepContract,
    "RowDropoutMutation": RowDropoutMutation,
    "TimestampJitterMutation": TimestampJitterMutation,
    "RsuRemovalMutation": RsuRemovalMutation,
    "MutationFieldChange": MutationFieldChange,
    "MutationRowChange": MutationRowChange,
    "MutationFileChange": MutationFileChange,
    "ScenarioMutationRequest": ScenarioMutationRequest,
    "ScenarioMutationPlan": ScenarioMutationPlan,
    "ScenarioMutationResult": ScenarioMutationResult,
    "ScenarioMutationContract": ScenarioMutationContract,
    "WinnerMapReport": WinnerMapReport,
    "PortfolioStudyReport": PortfolioStudyReport,
    "FaultInjectionEvaluationReport": FaultInjectionEvaluationReport,
    "CaseStudyPackManifest": CaseStudyPackManifest,
    "ExperimentProtocol": ExperimentProtocol,
    "ExperimentProtocolSlot": ExperimentProtocolSlot,
    "ProtocolBundleMatch": ProtocolBundleMatch,
    "ProvenanceNode": ProvenanceNode,
    "ProvenanceEdge": ProvenanceEdge,
    "ProvenanceTrace": ProvenanceTrace,
    "SourceRowPreview": SourceRowPreview,
    "MetricContributionReport": MetricContributionReport,
    "WindowMetricContributionReport": WindowMetricContributionReport,
    "DifferenceContributionRow": DifferenceContributionRow,
    "DifferenceContributionReport": DifferenceContributionReport,
    "DifferenceProvenanceContract": DifferenceProvenanceContract,
    "GraphExportNode": GraphExportNode,
    "GraphExportEdge": GraphExportEdge,
    "ProvenanceGraphView": ProvenanceGraphView,
    "ProvenanceGraphExportContract": ProvenanceGraphExportContract,
    "ClaimCompletenessAssessment": ClaimCompletenessAssessment,
    "ProvenanceCompletenessReport": ProvenanceCompletenessReport,
    "ProvenanceCompletenessContract": ProvenanceCompletenessContract,
    "ReportClaimReference": ReportClaimReference,
    "ReportClaimExclusion": ReportClaimExclusion,
    "ResearchReport": ResearchReport,
    "ResearchFigureEntry": ResearchFigureEntry,
    "ResearchExportProjection": ResearchExportProjection,
    "ResearchExportFile": ResearchExportFile,
    "ResearchExportReceipt": ResearchExportReceipt,
    "LatexExportContract": LatexExportContract,
    "DiagnosticNarrative": DiagnosticNarrative,
    "MockParticipantDataset": MockParticipantDataset,
    "ParticipantAnalysisReport": ParticipantAnalysisReport,
    "AccessibilityAuditReport": AccessibilityAuditReport,
    "TosEvaluationRun": TosEvaluationRun,
    "TosReplayFrame": TosReplayFrame,
    "TosTaskSample": TosTaskSample,
    "TosValidationReport": TosValidationReport,
    "TosSourceContract": TosSourceContract,
    "AuditedSourceFile": AuditedSourceFile,
    "ObservedArraySchema": ObservedArraySchema,
    "UnavailableField": UnavailableField,
    "TosSourceContractV2": TosSourceContractV2,
    "OccupancySpan": OccupancySpan,
    "VecVehicleAttributeObservation": VecVehicleAttributeObservation,
    "VecTaskActionObservation": VecTaskActionObservation,
    "VecTripJoin": VecTripJoin,
    "V2Finding": V2Finding,
    "ArtifactValidationReport": ArtifactValidationReport,
    "OccupancyReconciliationReport": OccupancyReconciliationReport,
    "RepositoryCitation": RepositoryCitation,
    "PublicationPermissionBasis": PublicationPermissionBasis,
    "SanitisationDeclaration": SanitisationDeclaration,
    "PublicationSourceLabels": PublicationSourceLabels,
    "IncludedArtifact": IncludedArtifact,
    "ExcludedArtifact": ExcludedArtifact,
    "TosPublicationManifest": TosPublicationManifest,
    "VecSanitisedMatchedSample": VecSanitisedMatchedSample,
    "VecDissertationPackManifest": VecDissertationPackManifest,
    "VecDissertationPackContract": VecDissertationPackContract,
    "VecEndToEndManifest": VecEndToEndManifest,
    "VecEndToEndContract": VecEndToEndContract,
    "VecEndToEndReceipt": VecEndToEndReceipt,
    "VecEndToEndVerification": VecEndToEndVerification,
    "TosEvaluationMatrix": TosEvaluationMatrix,
    "TosCampaignComparisonReport": TosCampaignComparisonReport,
    "TosGeneralisationMatrix": TosGeneralisationMatrix,
    "TosTrainingRun": TosTrainingRun,
    "TosTraceSummary": TosTraceSummary,
    "TosRsuRunSummary": TosRsuRunSummary,
    "TosTaskOutcomeSummary": TosTaskOutcomeSummary,
    "TosReproducibilityAudit": TosReproducibilityAudit,
    "TosIntegrationReadinessReport": TosIntegrationReadinessReport,
    "TosSupervisorPackManifest": TosSupervisorPackManifest,
    "SyntheticStaticSiteManifest": SyntheticStaticSiteManifest,
    "RuleSetConfig": RuleSetConfig,
    "R8EnergyDiagnosisContract": R8EnergyDiagnosisContract,
    "MetadataRequirement": MetadataRequirement,
    "NumericPredicateDefinition": NumericPredicateDefinition,
    "BooleanPredicateDefinition": BooleanPredicateDefinition,
    "DeclarativeRecommendation": DeclarativeRecommendation,
    "DeclarativeRuleDefinition": DeclarativeRuleDefinition,
    "PredicateEvaluation": PredicateEvaluation,
    "DeclarativeRuleRegistryReport": DeclarativeRuleRegistryReport,
    "DeclarativeRuleContract": DeclarativeRuleContract,
}

CLI_COMMANDS = [
    [],
    ["validate-seed"],
    ["normalise-seed"],
    ["capabilities"],
    ["doctor"],
    ["archive"],
    ["archive", "contract"],
    ["archive", "create"],
    ["archive", "verify"],
    ["synthetic"],
    ["synthetic", "presets"],
    ["synthetic", "measurement-contract"],
    ["synthetic", "generate-config"],
    ["synthetic", "generate-preset"],
    ["synthetic", "experiment-generate-preset"],
    ["synthetic", "verify"],
    ["synthetic", "case-study-pack"],
    ["demo"],
    ["demo", "initialise"],
    ["demo", "reset"],
    ["demo", "status"],
    ["demo", "launch"],
    ["compare"],
    ["registry"],
    ["registry", "init"],
    ["registry", "inspect"],
    ["registry", "migration-contract"],
    ["registry", "migration-status"],
    ["registry", "migrate"],
    ["registry", "annotation-contract"],
    ["registry", "annotation-add"],
    ["registry", "annotation-list"],
    ["registry", "search-contract"],
    ["registry", "search"],
    ["bundle"],
    ["bundle", "validate"],
    ["bundle", "inspect"],
    ["bundle", "cache-contract"],
    ["bundle", "cache-status"],
    ["bundle", "cache-validate"],
    ["bundle", "import"],
    ["bundle", "batch-validate"],
    ["bundle", "batch-import"],
    ["bundle", "stream-validate"],
    ["bundle", "stream-import"],
    ["bundle", "report"],
    ["manifest"],
    ["manifest", "contract"],
    ["manifest", "infer"],
    ["manifest", "confirm"],
    ["manifest", "files"],
    ["manifest", "apply"],
    ["metrics"],
    ["metrics", "compute"],
    ["metrics", "plugin-api"],
    ["metrics", "report"],
    ["metrics", "windows"],
    ["evidence"],
    ["evidence", "build"],
    ["report"],
    ["report", "run"],
    ["report", "compare"],
    ["report", "diagnostics"],
    ["report", "full"],
    ["report", "diff-contract"],
    ["report", "diff"],
    ["report", "latex-contract"],
    ["report", "latex-metrics"],
    ["report", "latex-comparison"],
    ["report", "latex-study"],
    ["report", "latex-rules"],
    ["release"],
    ["release", "status"],
    ["release", "stage-demo-site"],
    ["experiment"],
    ["experiment", "summarise"],
    ["experiment", "study-contract"],
    ["experiment", "statistical-study"],
    ["experiment", "n-way-contract"],
    ["experiment", "n-way-ranking"],
    ["experiment", "equivalence-contract"],
    ["experiment", "equivalence-study"],
    ["experiment", "regression-contract"],
    ["experiment", "regression-golden"],
    ["experiment", "regression-gate"],
    ["experiment", "power-contract"],
    ["experiment", "power-analysis"],
    ["experiment", "parameter-sweep-contract"],
    ["experiment", "parameter-sweep"],
    ["experiment", "mutation-contract"],
    ["experiment", "mutate-scenario"],
    ["experiment", "protocol"],
    ["experiment", "match-bundle"],
    ["experiment", "evidence"],
    ["experiment", "winner-map"],
    ["experiment", "portfolio"],
    ["experiment", "portfolio-study"],
    ["experiment", "track-init"],
    ["experiment", "track-list"],
    ["experiment", "track-update"],
    ["diagnose"],
    ["diagnose", "bundle"],
    ["diagnose", "evidence"],
    ["diagnose", "temporal"],
    ["diagnose", "rule-contract"],
    ["diagnose", "cross-rule-contract"],
    ["diagnose", "cross-rule"],
    ["diagnose", "rule-validate"],
    ["diagnose", "rule-evaluate"],
    ["diagnose", "fairness"],
    ["diagnose", "energy"],
    ["diagnose", "nearest-flip"],
    ["diagnose", "report"],
    ["diagnose", "evaluate"],
    ["diagnose", "render"],
    ["provenance"],
    ["provenance", "metric"],
    ["provenance", "window-metric"],
    ["provenance", "contributors"],
    ["provenance", "difference-contract"],
    ["provenance", "difference-contributors"],
    ["provenance", "graph-contract"],
    ["provenance", "completeness-contract"],
    ["provenance", "completeness"],
    ["provenance", "comparison-completeness"],
    ["provenance", "window-contributors"],
    ["provenance", "rule"],
    ["provenance", "run"],
    ["provenance", "source"],
    ["provenance", "export"],
    ["participant-evaluation"],
    ["participant-evaluation", "analyse-mock"],
    ["integration"],
    ["integration", "external"],
    ["integration", "external", "contract"],
    ["integration", "external", "discover"],
    ["integration", "external", "inspect"],
    ["integration", "sumo"],
    ["integration", "sumo", "contract"],
    ["integration", "sumo", "validate"],
    ["integration", "sumo", "metrics"],
    ["integration", "sumo", "import"],
    ["integration", "vec"],
    ["integration", "vec", "contract"],
    ["integration", "vec", "snapshot"],
    ["integration", "vec", "validate"],
    ["integration", "vec", "preprocess"],
    ["integration", "vec", "run"],
    ["integration", "vec", "monitor-current"],
    ["integration", "vec", "inspect"],
    ["integration", "vec", "compare"],
    ["integration", "vec", "export"],
    ["integration", "vec", "research-contract"],
    ["integration", "vec", "research-create"],
    ["integration", "vec", "research-verify"],
    ["integration", "tos"],
    ["integration", "tos", "inspect"],
    ["integration", "tos", "contract"],
    ["integration", "tos", "validate"],
    ["integration", "tos", "runs"],
    ["integration", "tos", "import"],
    ["integration", "tos", "metrics"],
    ["integration", "tos", "replay"],
    ["integration", "tos", "rsu-series"],
    ["integration", "tos", "task-sample"],
    ["integration", "tos", "diagnose"],
    ["integration", "tos", "provenance"],
    ["integration", "tos", "matrix"],
    ["integration", "tos", "compare-campaigns"],
    ["integration", "tos", "generalisation"],
    ["integration", "tos", "training-runs"],
    ["integration", "tos", "training"],
    ["integration", "tos", "trace-summary"],
    ["integration", "tos", "rsu-summary"],
    ["integration", "tos", "task-summary"],
    ["integration", "tos", "audit"],
    ["integration", "tos", "report"],
    ["integration", "tos", "atlas"],
    ["integration", "tos", "results-pack"],
    ["integration", "tos", "readiness"],
    ["integration", "tos", "supervisor-pack"],
    ["integration", "tos", "stage-public-atlas"],
]


def main() -> None:
    """Write generated reference JSON files."""

    OUTPUT.mkdir(parents=True, exist_ok=True)
    _write_json("pydantic_schemas.json", _schemas())
    _write_json("metric_catalogue.json", _metric_catalogue())
    _write_json("validation_codes.json", _validation_codes())
    _write_json("rule_catalogue.json", _rule_catalogue())
    _write_json("cli_help.json", _cli_help())
    _write_json("sumo_source_contract.json", sumo_source_contract().model_dump(mode="json"))
    _write_json(
        "vec_fcd_preprocessing_contract.json",
        vec_fcd_preprocessing_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_identity_contract.json",
        vec_identity_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_runner_contract.json",
        vec_runner_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_reproduction_contract.json",
        vec_reproduction_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_task_join_contract.json",
        vec_task_join_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_trip_join_contract.json",
        vec_trip_join_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_scientific_admission_contract.json",
        vec_scientific_admission_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_dissertation_pack_contract.json",
        vec_dissertation_pack_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_interface_contract.json",
        vec_interface_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_orchestration_contract.json",
        vec_orchestration_contract().model_dump(mode="json"),
    )
    _write_json(
        "sumo_execution_contract.json",
        sumo_execution_contract().model_dump(mode="json"),
    )
    _write_json(
        "vec_end_to_end_contract.json",
        vec_end_to_end_contract().model_dump(mode="json"),
    )
    _write_json(
        "measurement_impairment_contract.json",
        measurement_impairment_contract().model_dump(mode="json"),
    )
    _write_json(
        "manifest_inference_contract.json",
        manifest_inference_contract().model_dump(mode="json"),
    )
    _write_json("tos_source_contract.json", tos_source_contract().model_dump(mode="json"))
    _write_json(
        "tos_source_contract_v2.json",
        tos_source_contract_v2().model_dump(mode="json"),
    )
    _write_json(
        "tos_publication_policy.json",
        {
            "policy_version": "tos-publication-policy-1.0",
            "status": "accepted",
            "required_engine_version": "v2_post_nrsus_fix",
            "permitted_artifact_kinds": [item.value for item in permitted_artifact_kinds()],
            "mandatory_excluded_inventory": [
                item.model_dump(mode="json") for item in default_excluded_inventory()
            ],
            "capability_implemented": True,
            "blocker": None,
            "accepted_pack": "vec_dissertation_pack/manifest.json",
        },
    )
    _write_json(
        "external_source_contract.json",
        external_source_catalogue().model_dump(mode="json"),
    )
    _write_json(
        "manchester_spatial_policy.json",
        {
            "_meta": _metadata(
                "traffictwin.integration.manchester.spatial.spatial_policy_catalogue"
            ),
            "policies": [policy.model_dump(mode="json") for policy in spatial_policy_catalogue()],
        },
    )
    _write_json(
        "manchester_map_style_policy.json",
        {
            "_meta": _metadata("traffictwin.integration.manchester.map_layers.map_style_catalogue"),
            "styles": [style.model_dump(mode="json") for style in map_style_catalogue()],
            "basemap_provider": None,
            "external_network_required": False,
        },
    )
    _write_json(
        "metric_plugin_api_contract.json",
        metric_plugin_api_contract().model_dump(mode="json"),
    )
    _write_json(
        "temporal_diagnosis_contract.json",
        temporal_diagnosis_contract().model_dump(mode="json"),
    )
    _write_json(
        "declarative_rule_contract.json",
        declarative_rule_contract().model_dump(mode="json"),
    )
    _write_json(
        "r8_energy_diagnosis_contract.json",
        r8_energy_diagnosis_contract().model_dump(mode="json"),
    )
    _write_json(
        "nearest_flip_contract.json",
        nearest_flip_contract().model_dump(mode="json"),
    )
    _write_json(
        "threshold_sensitivity_contract.json",
        threshold_sensitivity_contract().model_dump(mode="json"),
    )
    _write_json(
        "cross_rule_reasoning_contract.json",
        cross_rule_reasoning_contract().model_dump(mode="json"),
    )
    _write_json(
        "statistical_study_contract.json",
        statistical_study_contract().model_dump(mode="json"),
    )
    _write_json(
        "n_way_ranking_contract.json",
        n_way_ranking_contract().model_dump(mode="json"),
    )
    _write_json(
        "equivalence_testing_contract.json",
        equivalence_testing_contract().model_dump(mode="json"),
    )
    _write_json(
        "regression_gate_contract.json",
        regression_gate_method_contract().model_dump(mode="json"),
    )
    _write_json(
        "power_analysis_contract.json",
        power_analysis_method_contract().model_dump(mode="json"),
    )
    _write_json(
        "difference_provenance_contract.json",
        difference_provenance_contract().model_dump(mode="json"),
    )
    _write_json(
        "provenance_graph_export_contract.json",
        provenance_graph_export_contract().model_dump(mode="json"),
    )
    _write_json(
        "provenance_completeness_contract.json",
        provenance_completeness_contract().model_dump(mode="json"),
    )
    _write_json(
        "parameter_sweep_contract.json",
        parameter_sweep_contract().model_dump(mode="json"),
    )
    _write_json(
        "scenario_mutation_contract.json",
        scenario_mutation_contract().model_dump(mode="json"),
    )
    _write_json(
        "latex_export_contract.json",
        latex_export_contract().model_dump(mode="json"),
    )
    _write_json(
        "analyst_annotation_contract.json",
        analyst_annotation_contract().model_dump(mode="json"),
    )
    _write_json(
        "report_diff_contract.json",
        report_diff_contract().model_dump(mode="json"),
    )
    _write_json(
        "executive_summary_contract.json",
        executive_summary_contract().model_dump(mode="json"),
    )
    _write_json(
        "registry_search_contract.json",
        registry_search_contract().model_dump(mode="json"),
    )
    _write_json(
        "registry_migration_contract.json",
        registry_migration_contract().model_dump(mode="json"),
    )
    _write_json(
        "v07_workspace_contract.json",
        v07_workspace_contract().model_dump(mode="json"),
    )
    _write_json(
        "canonical_cache_contract.json",
        canonical_cache_contract().model_dump(mode="json"),
    )
    _write_json(
        "doctor_contract.json",
        doctor_contract().model_dump(mode="json"),
    )
    _write_json(
        "research_object_contract.json",
        research_object_contract().model_dump(mode="json"),
    )
    tier_rule = r7_rule_definition(R7Config(dimension="vehicle_tier_completion"))
    target_rule = r7_rule_definition(R7Config(dimension="target_rsu_completion"))
    _write_json(
        "r7_rule_definitions.json",
        {
            "_meta": _metadata("traffictwin.rules.r7_fairness.r7_rule_definition"),
            "definitions": [
                {
                    "dimension": "vehicle_tier_completion",
                    "fingerprint": tier_rule.fingerprint(),
                    "definition": tier_rule.model_dump(mode="json"),
                },
                {
                    "dimension": "target_rsu_completion",
                    "fingerprint": target_rule.fingerprint(),
                    "definition": target_rule.model_dump(mode="json"),
                },
            ],
        },
    )
    _write_json(
        "tos_analysis_catalogue.json",
        {
            "_meta": _metadata("traffictwin.integration.tos.analysis.tos_analysis_catalogue"),
            "measures": [item.model_dump(mode="json") for item in tos_analysis_catalogue()],
        },
    )


def _metadata(kind: str) -> dict[str, str]:
    return {
        "generated": "true",
        "source": kind,
        "note": "Generated by scripts/generate_reference_docs.py. Do not hand-edit.",
    }


def _schemas() -> dict[str, Any]:
    return {
        "_meta": _metadata("pydantic model_json_schema"),
        "schemas": {name: model.model_json_schema() for name, model in sorted(MODEL_TYPES.items())},
    }


def _metric_catalogue() -> dict[str, Any]:
    catalogue = {**metric_catalogue(), **tos_metric_catalogue()}
    return {
        "_meta": _metadata(
            "traffictwin.metrics.catalogue.metric_catalogue and "
            "traffictwin.integration.tos.metrics.tos_metric_catalogue"
        ),
        "metrics": {
            key: definition.model_dump(mode="json") for key, definition in sorted(catalogue.items())
        },
    }


def _validation_codes() -> dict[str, Any]:
    return {
        "_meta": _metadata("traffictwin.validation.codes.ValidationCode"),
        "codes": [code.value for code in ValidationCode],
    }


def _rule_catalogue() -> dict[str, Any]:
    return {
        "_meta": _metadata("traffictwin.rules.catalogue.rule_catalogue"),
        "rules": {
            key: definition.model_dump(mode="json") for key, definition in rule_catalogue().items()
        },
    }


def _cli_help() -> dict[str, Any]:
    executable = _traffictwin_executable()
    env = {
        **os.environ,
        "COLUMNS": "100",
        "NO_COLOR": "1",
        "TERM": "dumb",
        "TERMINAL_WIDTH": "100",
        "_TYPER_FORCE_DISABLE_TERMINAL": "1",
    }
    entries: list[dict[str, Any]] = []
    for command in CLI_COMMANDS:
        args = [executable, *command, "--help"]
        completed = subprocess.run(  # noqa: S603 - fixed local CLI help commands only.
            args,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        entries.append(
            {
                "command": " ".join(["traffictwin", *command]),
                "args": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
    return {
        "_meta": _metadata("traffictwin Typer --help output"),
        "commands": entries,
    }


def _traffictwin_executable() -> str:
    local_script = Path(sys.executable).parent / "traffictwin"
    if local_script.exists():
        return str(local_script)
    found = shutil.which("traffictwin")
    if found is not None:
        return found
    msg = "traffictwin console script not found; run `python -m pip install -e .` first"
    raise RuntimeError(msg)


def _write_json(name: str, payload: dict[str, Any]) -> None:
    path = OUTPUT / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    main()
