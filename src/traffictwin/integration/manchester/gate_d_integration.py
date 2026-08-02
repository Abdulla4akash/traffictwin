"""Read-only Manchester Gate-D integration over committed candidate records.

The module joins existing measurement, candidate-contract and readiness truth.
It does not read files, review map matches, choose scientific thresholds,
register contracts, execute SUMO, accept a baseline, or calculate a real
observed-versus-simulated comparison.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.comparison import ManchesterComparisonMetricContract
from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.owner_candidate_contracts import (
    comparison_contract_fingerprint,
    comparison_contract_is_registered,
    owner_candidate_comparison_contract,
)

GATE_D_METHOD_VERSION: Literal["manchester-gate-d-integration-1.0"] = (
    "manchester-gate-d-integration-1.0"
)
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SAFE_REF_PATTERN = r"^[a-z0-9][A-Za-z0-9_./-]{2,239}$"

SourceRole: TypeAlias = Literal[
    "decision_worksheet",
    "candidate_measurement",
    "accepted_source_derived_candidate",
    "restoration_receipt",
]
SensitivityPopulation: TypeAlias = Literal[
    "known_a_road_reference_sample",
    "real_dft_count_points_with_raw_counts",
]
DependencyState: TypeAlias = Literal[
    "candidate_available",
    "blocked_human_review",
    "blocked_scientific_decision",
    "blocked_missing_artifact",
    "blocked_failed_feasibility",
    "blocked_registration",
]
BlockerOwner: TypeAlias = Literal["none", "named_person", "supervisor", "owner", "lead"]

_EXPECTED_RADII = (10, 20, 30, 50, 100)
_EXPECTED_MAP_COUNTS = {
    "observations": 305,
    "owner_policy_accepted": 131,
    "awaiting_manual_review": 165,
    "no_suitable_candidate": 9,
    "unavailable_missing_evidence": 0,
    "strict_acceptances": 106,
    "override_acceptances": 25,
    "override_applied_edges": 51,
    "readmitted_edges": 51,
    "refused_edges": 1339,
}
_EXPECTED_PROFILE_COUNTS = {
    "offered_rows": 39072,
    "admitted_rows": 39072,
    "excluded_rows": 0,
    "sites": 305,
    "series": 3256,
    "expected_cells": 39072,
    "observed_cells": 39072,
    "missing_cells": 0,
    "measured_zero_cells": 166,
}


class GateDIntegrationError(RuntimeError):
    """Typed refusal at the fixed Gate-D integration boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class GateDModel(ManchesterSnapshotModel):
    """Strict, frozen and canonical Manchester Gate-D record."""


class GateDSourceBinding(GateDModel):
    source_id: Literal[
        "map_matching_worksheet",
        "map_match_v1_measurement",
        "map_match_v11_measurement",
        "dft_temporal_profile_measurement",
        "chain_restoration_receipt",
    ]
    repository_ref: str = Field(pattern=_SAFE_REF_PATTERN)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    role: SourceRole
    evidence_class: Literal[
        "measured_decision_support",
        "exploratory_candidate_software_evidence",
        "accepted_real_snapshot_derived_candidate",
    ]
    support_scope: str = Field(min_length=20, max_length=400)
    limitation: str = Field(min_length=20, max_length=500)
    llm_output: Literal[False] = False
    creates_evidence: Literal[False] = False


class SensitivityRow(GateDModel):
    radius_m: Literal[10, 20, 30, 50, 100]
    sites_with_candidate: int = Field(ge=0)
    population: int = Field(ge=1)
    mean_candidates: Decimal = Field(ge=0)
    median_candidates: int = Field(ge=0)
    p90_candidates: int = Field(ge=0)
    max_candidates: int = Field(ge=0)
    multi_road_class_percent: Decimal = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_row(self) -> SensitivityRow:
        if self.sites_with_candidate > self.population:
            raise ValueError("candidate sites cannot exceed the population")
        if not self.mean_candidates.is_finite() or not self.multi_road_class_percent.is_finite():
            raise ValueError("sensitivity values must be finite")
        if not self.median_candidates <= self.p90_candidates <= self.max_candidates:
            raise ValueError("candidate distribution summaries must be ordered")
        return self


class SensitivityTable(GateDModel):
    population_id: SensitivityPopulation
    population: int = Field(ge=1)
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    rows: tuple[SensitivityRow, ...]
    interpretation: Literal["measured_threshold_decision_support_not_threshold_selection"] = (
        "measured_threshold_decision_support_not_threshold_selection"
    )
    threshold_selected_by_table: Literal[False] = False
    scientific_validation: Literal[False] = False

    @model_validator(mode="after")
    def validate_table(self) -> SensitivityTable:
        if tuple(row.radius_m for row in self.rows) != _EXPECTED_RADII:
            raise ValueError("sensitivity radii must be the fixed measured sequence")
        if any(row.population != self.population for row in self.rows):
            raise ValueError("every sensitivity row must retain the population denominator")
        return self


class MappingPolicySummary(GateDModel):
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"]
    policy_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    outer_search_radius_m: Literal[50] = 50
    native_eligibility_m: Literal[30] = 30
    fallback_eligibility_m: Literal[50] = 50
    strict_clear_native_m: Literal[10] = 10
    strict_clear_fallback_m: Literal[20] = 20
    direction_tolerance_degrees: Literal[45] = 45
    exact_reference_override_m: Literal[5] = 5
    observations: int = Field(ge=0)
    owner_policy_accepted: int = Field(ge=0)
    awaiting_manual_review: int = Field(ge=0)
    no_suitable_candidate: int = Field(ge=0)
    unavailable_missing_evidence: int = Field(ge=0)
    strict_acceptances: int = Field(ge=0)
    override_acceptances: int = Field(ge=0)
    override_applied_edges: int = Field(ge=0)
    readmitted_edges: int = Field(ge=0)
    refused_edges: int = Field(ge=0)
    automatic_acceptance: Literal[False] = False
    analyst_accepted: Literal[False] = False
    human_accepted: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False

    @model_validator(mode="after")
    def validate_reconciliation(self) -> MappingPolicySummary:
        values = {key: getattr(self, key) for key in _EXPECTED_MAP_COUNTS}
        if values != _EXPECTED_MAP_COUNTS:
            raise ValueError("map-policy summary must match the committed 305-site measurement")
        if (
            self.owner_policy_accepted
            + self.awaiting_manual_review
            + self.no_suitable_candidate
            + self.unavailable_missing_evidence
            != self.observations
        ):
            raise ValueError("map-policy dispositions must account for every observation")
        if self.strict_acceptances + self.override_acceptances != self.owner_policy_accepted:
            raise ValueError("acceptance paths must reconcile to owner-policy acceptances")
        if self.override_applied_edges > self.readmitted_edges:
            raise ValueError("applied override edges are a subset of readmitted edges")
        return self


class AnalystReviewReadiness(GateDModel):
    ledger_contract: Literal["manchester-map-match-analyst-review-1.0"] = (
        "manchester-map-match-analyst-review-1.0"
    )
    queue_total: int = Field(ge=0)
    decided_total: int = Field(ge=0)
    pending_total: int = Field(ge=0)
    awaiting_manual_review: int = Field(ge=0)
    no_candidate_preserved_total: int = Field(ge=0)
    review_state: Literal["pending_named_person_review"] = "pending_named_person_review"
    decision_records_embedded: Literal[False] = False
    analyst_reviewed: Literal[False] = False
    human_accepted: Literal[False] = False
    supervisor_approved: Literal[False] = False
    bulk_operation: Literal[False] = False

    @model_validator(mode="after")
    def validate_queue(self) -> AnalystReviewReadiness:
        if (self.queue_total, self.decided_total, self.pending_total) != (174, 0, 174):
            raise ValueError("review readiness must retain the empty 174-row ledger")
        if self.awaiting_manual_review != 165 or self.no_candidate_preserved_total != 9:
            raise ValueError("review queue must retain 165 ambiguous and nine no-candidate rows")
        if self.decided_total + self.pending_total != self.queue_total:
            raise ValueError("review decisions and pending rows must reconcile")
        return self


class TemporalPartitionSummary(GateDModel):
    partition: Literal["development", "held_out"]
    sites: int = Field(ge=0)
    series: int = Field(ge=0)
    expected_cells: int = Field(ge=0)
    observed_cells: int = Field(ge=0)
    missing_cells: int = Field(ge=0)
    excluded_cells: int = Field(ge=0)
    measured_zero_cells: int = Field(ge=0)
    coverage: Decimal = Field(ge=0, le=1)
    meets_minimum_coverage: bool

    @model_validator(mode="after")
    def validate_partition(self) -> TemporalPartitionSummary:
        if self.observed_cells + self.missing_cells + self.excluded_cells != self.expected_cells:
            raise ValueError("temporal partition cells must reconcile")
        return self


class TemporalProfileSummary(GateDModel):
    policy_id: Literal["manchester-dft-temporal-profile-owner-candidate-1.0"]
    policy_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    source_snapshot_id: Literal["dft_raw_counts-20260725T063354Z-61965dc5c182"]
    source_raw_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    evidence_class: Literal["accepted_real_snapshot_derived_candidate"] = (
        "accepted_real_snapshot_derived_candidate"
    )
    time_basis: Literal["local_clock_hour"] = "local_clock_hour"
    utc_instant_available: Literal[False] = False
    simulation_origin_local_hour: Literal[7] = 7
    interval_seconds: Literal[3600] = 3600
    missing_as_zero: Literal[False] = False
    offered_rows: int = Field(ge=0)
    admitted_rows: int = Field(ge=0)
    excluded_rows: int = Field(ge=0)
    sites: int = Field(ge=0)
    series: int = Field(ge=0)
    expected_cells: int = Field(ge=0)
    observed_cells: int = Field(ge=0)
    missing_cells: int = Field(ge=0)
    measured_zero_cells: int = Field(ge=0)
    coverage: Decimal = Field(ge=0, le=1)
    partitions: tuple[TemporalPartitionSummary, ...]
    dft_time_semantics_blocker: Literal["GA-DFT-1"] = "GA-DFT-1"
    webtris_time_semantics_blocker: Literal["GA-WT-1"] = "GA-WT-1"
    calibration_use_available: Literal[False] = False
    baseline_available: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False

    @model_validator(mode="after")
    def validate_profile(self) -> TemporalProfileSummary:
        values = {key: getattr(self, key) for key in _EXPECTED_PROFILE_COUNTS}
        if values != _EXPECTED_PROFILE_COUNTS:
            raise ValueError("temporal summary must match the committed profile measurement")
        if self.coverage != Decimal("1.000000"):
            raise ValueError("committed profile coverage must remain exactly 1.000000")
        if tuple(item.partition for item in self.partitions) != ("development", "held_out"):
            raise ValueError("temporal partitions must retain development then held-out order")
        if sum(item.sites for item in self.partitions) != self.sites:
            raise ValueError("temporal partition sites must reconcile")
        if sum(item.series for item in self.partitions) != self.series:
            raise ValueError("temporal partition series must reconcile")
        if sum(item.expected_cells for item in self.partitions) != self.expected_cells:
            raise ValueError("temporal partition expected cells must reconcile")
        if sum(item.observed_cells for item in self.partitions) != self.observed_cells:
            raise ValueError("temporal partition observed cells must reconcile")
        if sum(item.measured_zero_cells for item in self.partitions) != self.measured_zero_cells:
            raise ValueError("temporal partition measured zeros must reconcile")
        return self


class GateDDependency(GateDModel):
    dependency_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    title: str = Field(min_length=5, max_length=120)
    state: DependencyState
    blocker_owner: BlockerOwner
    summary: str = Field(min_length=20, max_length=500)
    satisfied_for_downstream: bool
    source_fingerprint: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    missing_as_zero: Literal[False] = False

    @model_validator(mode="after")
    def validate_dependency(self) -> GateDDependency:
        available = self.state == "candidate_available"
        if self.satisfied_for_downstream and not available:
            raise ValueError("a blocked dependency cannot be satisfied downstream")
        if available and self.blocker_owner != "none":
            raise ValueError("an available candidate dependency has no blocker owner")
        if not available and self.blocker_owner == "none":
            raise ValueError("a blocked dependency must name who can lift it")
        return self


class CalibrationOrchestration(GateDModel):
    workflow_version: Literal["manchester-calibration-orchestration-1.0"] = (
        "manchester-calibration-orchestration-1.0"
    )
    interval_adapter: Literal["one_hour_cell_to_exact_3600_second_interval"] = (
        "one_hour_cell_to_exact_3600_second_interval"
    )
    output_unit: Literal["vehicles_per_interval"] = "vehicles_per_interval"
    resampling: Literal[False] = False
    timezone_conversion: Literal[False] = False
    source_fusion: Literal[False] = False
    interpolation: Literal[False] = False
    missing_filled_with_zero: Literal[False] = False
    dependencies: tuple[GateDDependency, ...]
    state: Literal["unavailable_missing_predeclaration_and_inputs"] = (
        "unavailable_missing_predeclaration_and_inputs"
    )
    calibration_contract_registered: Literal[False] = False
    calibration_executed: Literal[False] = False
    objective_available: Literal[False] = False
    candidate_selected: Literal[False] = False

    @model_validator(mode="after")
    def validate_dependencies(self) -> CalibrationOrchestration:
        expected_ids = (
            "temporal_profile",
            "human_mapping_review",
            "projection_and_mapping_binding",
            "calibration_method_contract",
            "viable_demand_and_candidate_runs",
            "calibration_contract_registration",
        )
        if tuple(item.dependency_id for item in self.dependencies) != expected_ids:
            raise ValueError("calibration dependencies must retain their frozen order")
        if all(item.satisfied_for_downstream for item in self.dependencies):
            raise ValueError("Phase 179 cannot present calibration as ready")
        return self


class ManchesterBaselineCandidateWorkflow(GateDModel):
    workflow_version: Literal["manchester-sumo-baseline-candidate-workflow-1.0"] = (
        "manchester-sumo-baseline-candidate-workflow-1.0"
    )
    required_order: tuple[
        Literal["reviewed_mapping"],
        Literal["compatible_temporal_profile"],
        Literal["admitted_calibration_report"],
        Literal["viable_controlled_sumo_receipt"],
        Literal["uncertainty_and_held_out_review"],
        Literal["explicit_human_accept_or_refuse"],
    ] = (
        "reviewed_mapping",
        "compatible_temporal_profile",
        "admitted_calibration_report",
        "viable_controlled_sumo_receipt",
        "uncertainty_and_held_out_review",
        "explicit_human_accept_or_refuse",
    )
    state: Literal["unavailable_missing_inputs"] = "unavailable_missing_inputs"
    missing_requirements: tuple[str, ...] = Field(min_length=1)
    candidate_fingerprint: None = None
    baseline_created: Literal[False] = False
    baseline_accepted: Literal[False] = False
    sumo_executed: Literal[False] = False
    automatic_acceptance: Literal[False] = False
    scientific_evidence: Literal[False] = False


class ComparisonMetricAvailability(GateDModel):
    metric: Literal["mae", "rmse"]
    status: Literal["unavailable"] = "unavailable"
    reason: Literal["candidate_contract_unregistered_and_inputs_missing"] = (
        "candidate_contract_unregistered_and_inputs_missing"
    )
    value: None = None


class ComparisonContractWorkflow(GateDModel):
    workflow_version: Literal["manchester-comparison-contract-workflow-1.0"] = (
        "manchester-comparison-contract-workflow-1.0"
    )
    contract: ManchesterComparisonMetricContract
    contract_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    registration_state: Literal["candidate_unregistered"] = "candidate_unregistered"
    contract_registered: Literal[False] = False
    compatible_real_inputs_available: Literal[False] = False
    comparison_executed: Literal[False] = False
    result_available: Literal[False] = False
    metrics: tuple[ComparisonMetricAvailability, ...]
    missing_requirements: tuple[str, ...] = Field(min_length=1)
    geh_in_contract: Literal[False] = False
    geh_threshold_available: Literal[False] = False
    non_causal_descriptive_only: Literal[True] = True
    model_validity_established: Literal[False] = False

    @model_validator(mode="after")
    def validate_contract_workflow(self) -> ComparisonContractWorkflow:
        expected = owner_candidate_comparison_contract()
        if self.contract != expected or self.contract_fingerprint != expected.fingerprint():
            raise ValueError("comparison workflow must reuse the exact owner-candidate contract")
        if comparison_contract_is_registered():
            raise ValueError("candidate-unregistered state disagrees with the production registry")
        if tuple(item.metric for item in self.metrics) != expected.goodness_of_fit_metrics:
            raise ValueError("metric unavailable rows must cover the exact contract metric set")
        return self


class GateDLineageStage(GateDModel):
    position: int = Field(ge=1, le=7)
    stage: Literal[
        "observation_source",
        "mapping_candidate",
        "human_mapping_review",
        "temporal_profile",
        "calibration",
        "baseline_candidate",
        "observed_simulated_comparison",
    ]
    state: DependencyState
    artifact_fingerprint: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    waits_on: tuple[str, ...]
    summary: str = Field(min_length=20, max_length=400)
    accepted_capability: Literal[False] = False
    scientific_validation: Literal[False] = False

    @model_validator(mode="after")
    def validate_stage(self) -> GateDLineageStage:
        if self.state == "candidate_available" and self.artifact_fingerprint is None:
            raise ValueError("an available candidate stage must bind an artifact fingerprint")
        if self.state != "candidate_available" and not self.waits_on:
            raise ValueError("a blocked stage must name its upstream dependency")
        return self


class ManchesterGateDIntegrationPacket(GateDModel):
    method_version: Literal["manchester-gate-d-integration-1.0"] = GATE_D_METHOD_VERSION
    capability_ids: tuple[Literal["MAN-09"], Literal["MAN-10"], Literal["MAN-11"]] = (
        "MAN-09",
        "MAN-10",
        "MAN-11",
    )
    source_bindings: tuple[GateDSourceBinding, ...]
    sensitivity_tables: tuple[SensitivityTable, ...]
    mapping_policy: MappingPolicySummary
    analyst_review: AnalystReviewReadiness
    temporal_profile: TemporalProfileSummary
    calibration: CalibrationOrchestration
    baseline: ManchesterBaselineCandidateWorkflow
    comparison: ComparisonContractWorkflow
    lineage: tuple[GateDLineageStage, ...]
    gate_d_state: Literal["foundation_only"] = "foundation_only"
    capability_status: Literal["planned"] = "planned"
    maximum_policy_ceiling: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    performs_network_access: Literal[False] = False
    performs_private_artifact_access: Literal[False] = False
    performs_review: Literal[False] = False
    performs_execution: Literal[False] = False
    registers_contract: Literal[False] = False
    creates_baseline: Literal[False] = False
    creates_comparison_result: Literal[False] = False
    creates_scientific_evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_packet(self) -> ManchesterGateDIntegrationPacket:
        expected_sources = (
            "map_matching_worksheet",
            "map_match_v1_measurement",
            "map_match_v11_measurement",
            "dft_temporal_profile_measurement",
            "chain_restoration_receipt",
        )
        if tuple(item.source_id for item in self.source_bindings) != expected_sources:
            raise ValueError("Gate-D packet must retain the fixed source inventory")
        worksheet_digest = self.source_bindings[0].sha256
        if self.sensitivity_tables != build_sensitivity_tables(worksheet_digest):
            raise ValueError(
                "sensitivity tables must be re-derived from the fixed worksheet binding"
            )
        if self.analyst_review.awaiting_manual_review != self.mapping_policy.awaiting_manual_review:
            raise ValueError("review readiness must bind the map-policy review population")
        if (
            self.analyst_review.no_candidate_preserved_total
            != self.mapping_policy.no_suitable_candidate
        ):
            raise ValueError("review readiness must preserve every no-candidate row")
        if self.comparison.contract_fingerprint != comparison_contract_fingerprint():
            raise ValueError("comparison fingerprint must match the existing owner contract")
        expected_stages = (
            "observation_source",
            "mapping_candidate",
            "human_mapping_review",
            "temporal_profile",
            "calibration",
            "baseline_candidate",
            "observed_simulated_comparison",
        )
        if tuple(item.position for item in self.lineage) != tuple(range(1, 8)):
            raise ValueError("Gate-D lineage positions must be contiguous")
        if tuple(item.stage for item in self.lineage) != expected_stages:
            raise ValueError("Gate-D lineage stages must retain their frozen order")
        return self

    def digest(self) -> str:
        return sha256_hex(self.canonical_json().encode("utf-8"))


def build_sensitivity_tables(worksheet_digest: str) -> tuple[SensitivityTable, ...]:
    """Return the two measured tables, bound to the exact worksheet bytes."""

    if len(worksheet_digest) != 64 or any(
        char not in "0123456789abcdef" for char in worksheet_digest
    ):
        raise GateDIntegrationError("SOURCE_DIGEST_INVALID", "worksheet digest must be SHA-256")
    known_rows = (
        (10, 742, Decimal("6.0"), 6, 10, 23, Decimal("77.5")),
        (20, 742, Decimal("10.4"), 8, 20, 47, Decimal("89.2")),
        (30, 742, Decimal("15.8"), 12, 32, 85, Decimal("95.0")),
        (50, 742, Decimal("29.1"), 23, 58, 126, Decimal("98.0")),
        (100, 742, Decimal("76.0"), 61, 150, 414, Decimal("99.6")),
    )
    real_rows = (
        (10, 298, Decimal("4.5"), 3, 9, 24, Decimal("58.4")),
        (20, 304, Decimal("8.3"), 6, 18, 44, Decimal("70.8")),
        (30, 305, Decimal("13.3"), 10, 28, 61, Decimal("80.0")),
        (50, 305, Decimal("27.2"), 23, 57, 128, Decimal("90.5")),
        (100, 305, Decimal("87.4"), 71, 179, 460, Decimal("98.7")),
    )

    def rows(
        values: tuple[tuple[int, int, Decimal, int, int, int, Decimal], ...], population: int
    ) -> tuple[SensitivityRow, ...]:
        return tuple(
            SensitivityRow(
                radius_m=radius,  # type: ignore[arg-type]
                sites_with_candidate=sites,
                population=population,
                mean_candidates=mean,
                median_candidates=median,
                p90_candidates=p90,
                max_candidates=maximum,
                multi_road_class_percent=multi,
            )
            for radius, sites, mean, median, p90, maximum, multi in values
        )

    return (
        SensitivityTable(
            population_id="known_a_road_reference_sample",
            population=742,
            source_sha256=worksheet_digest,
            rows=rows(known_rows, 742),
        ),
        SensitivityTable(
            population_id="real_dft_count_points_with_raw_counts",
            population=305,
            source_sha256=worksheet_digest,
            rows=rows(real_rows, 305),
        ),
    )


def build_gate_d_packet(
    *,
    source_bindings: tuple[GateDSourceBinding, ...],
    mapping_policy: MappingPolicySummary,
    analyst_review: AnalystReviewReadiness,
    temporal_profile: TemporalProfileSummary,
) -> ManchesterGateDIntegrationPacket:
    """Join already-extracted fixed records without executing any Gate-D stage."""

    source_by_id = {item.source_id: item for item in source_bindings}
    if len(source_by_id) != 5:
        raise GateDIntegrationError("SOURCE_INVENTORY_MISMATCH", "five unique sources are required")
    calibration = CalibrationOrchestration(
        dependencies=(
            GateDDependency(
                dependency_id="temporal_profile",
                title="Real DfT temporal-profile candidate",
                state="candidate_available",
                blocker_owner="none",
                summary=(
                    "Exact local-clock-hour cells are available as candidate input semantics only."
                ),
                satisfied_for_downstream=True,
                source_fingerprint=temporal_profile.policy_fingerprint,
            ),
            GateDDependency(
                dependency_id="human_mapping_review",
                title="Human map-match review",
                state="blocked_human_review",
                blocker_owner="named_person",
                summary=(
                    "All 174 queued rows remain pending; software cannot create reviewer decisions."
                ),
                satisfied_for_downstream=False,
            ),
            GateDDependency(
                dependency_id="projection_and_mapping_binding",
                title="Final projection and reviewed mapping binding",
                state="blocked_missing_artifact",
                blocker_owner="lead",
                summary=(
                    "No final reviewed mapping/projection fingerprint pair is admitted downstream."
                ),
                satisfied_for_downstream=False,
            ),
            GateDDependency(
                dependency_id="calibration_method_contract",
                title="Calibration objective, grid and uncertainty design",
                state="blocked_scientific_decision",
                blocker_owner="supervisor",
                summary=(
                    "Objective, parameter bounds/grid, uncertainty and held-out rules are not "
                    "approved."
                ),
                satisfied_for_downstream=False,
            ),
            GateDDependency(
                dependency_id="viable_demand_and_candidate_runs",
                title="Viable demand and completed candidate runs",
                state="blocked_failed_feasibility",
                blocker_owner="owner",
                summary=(
                    "The preserved demand candidate gridlocks; no compatible candidate runs exist."
                ),
                satisfied_for_downstream=False,
            ),
            GateDDependency(
                dependency_id="calibration_contract_registration",
                title="Reviewed production calibration registration",
                state="blocked_registration",
                blocker_owner="lead",
                summary=(
                    "The production calibration registry remains empty pending a reviewed contract."
                ),
                satisfied_for_downstream=False,
            ),
        )
    )
    baseline = ManchesterBaselineCandidateWorkflow(
        missing_requirements=(
            "completed named-person mapping review and nine-site treatment",
            "admitted calibration contract and completed compatible candidate report",
            "viable controlled-SUMO receipt with deviations and exclusions",
            "uncertainty and held-out review",
            "explicit human accept-or-refuse record",
        )
    )
    contract = owner_candidate_comparison_contract()
    comparison = ComparisonContractWorkflow(
        contract=contract,
        contract_fingerprint=contract.fingerprint(),
        metrics=(
            ComparisonMetricAvailability(metric="mae"),
            ComparisonMetricAvailability(metric="rmse"),
        ),
        missing_requirements=(
            "registered reviewed production comparison contract",
            "compatible final projection and reviewed mapping fingerprints",
            "admitted calibration and accepted-or-refused baseline record",
            "controlled SUMO run and simulated interval inventory",
        ),
    )
    observation_digest = source_by_id["dft_temporal_profile_measurement"].sha256
    mapping_digest = source_by_id["map_match_v11_measurement"].sha256
    lineage = (
        GateDLineageStage(
            position=1,
            stage="observation_source",
            state="candidate_available",
            artifact_fingerprint=observation_digest,
            waits_on=(),
            summary=(
                "Accepted real DfT snapshot lineage is preserved in the temporal-profile record."
            ),
        ),
        GateDLineageStage(
            position=2,
            stage="mapping_candidate",
            state="candidate_available",
            artifact_fingerprint=mapping_digest,
            waits_on=(),
            summary="Owner-policy v1.1 candidate reconciliation is measured over all 305 sites.",
        ),
        GateDLineageStage(
            position=3,
            stage="human_mapping_review",
            state="blocked_human_review",
            waits_on=("named person decisions for 174 queued rows",),
            summary="The sealed ledger contract exists but contains zero decisions.",
        ),
        GateDLineageStage(
            position=4,
            stage="temporal_profile",
            state="candidate_available",
            artifact_fingerprint=temporal_profile.policy_fingerprint,
            waits_on=(),
            summary=(
                "The independently built real DfT profile candidate preserves local-clock "
                "semantics."
            ),
        ),
        GateDLineageStage(
            position=5,
            stage="calibration",
            state="blocked_scientific_decision",
            waits_on=("human_mapping_review", "calibration_method_contract", "candidate_runs"),
            summary="No admitted calibration contract, candidate report or objective exists.",
        ),
        GateDLineageStage(
            position=6,
            stage="baseline_candidate",
            state="blocked_missing_artifact",
            waits_on=("calibration", "viable_controlled_sumo_receipt", "human_decision"),
            summary="No ManchesterSumoBaseline candidate or acceptance/refusal record exists.",
        ),
        GateDLineageStage(
            position=7,
            stage="observed_simulated_comparison",
            state="blocked_registration",
            waits_on=("registered_contract", "baseline_candidate", "simulated_intervals"),
            summary="The owner-candidate contract is unregistered and no real comparison was run.",
        ),
    )
    return ManchesterGateDIntegrationPacket(
        source_bindings=source_bindings,
        sensitivity_tables=build_sensitivity_tables(source_bindings[0].sha256),
        mapping_policy=mapping_policy,
        analyst_review=analyst_review,
        temporal_profile=temporal_profile,
        calibration=calibration,
        baseline=baseline,
        comparison=comparison,
        lineage=lineage,
    )


def packet_text(packet: ManchesterGateDIntegrationPacket) -> str:
    """Return bounded human-readable fields for presentation privacy checks."""

    payload = {
        "sources": [
            [item.repository_ref, item.support_scope, item.limitation]
            for item in packet.source_bindings
        ],
        "calibration": [item.summary for item in packet.calibration.dependencies],
        "baseline": list(packet.baseline.missing_requirements),
        "comparison": list(packet.comparison.missing_requirements),
        "lineage": [item.summary for item in packet.lineage],
    }
    return canonical_json(payload)


__all__ = [
    "AnalystReviewReadiness",
    "CalibrationOrchestration",
    "ComparisonContractWorkflow",
    "GateDDependency",
    "GateDIntegrationError",
    "GateDLineageStage",
    "GateDSourceBinding",
    "ManchesterBaselineCandidateWorkflow",
    "ManchesterGateDIntegrationPacket",
    "MappingPolicySummary",
    "SensitivityRow",
    "SensitivityTable",
    "TemporalPartitionSummary",
    "TemporalProfileSummary",
    "build_gate_d_packet",
    "build_sensitivity_tables",
    "packet_text",
]
