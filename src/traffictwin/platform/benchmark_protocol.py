"""Owner-selected maximum-coverage capacity/multi-algorithm benchmark tooling.

This module freezes the complete proposed protocol, enumerates all 240
compatible training cells and 2,400 matched training jobs, renders the
unsigned digest-bound predeclaration, validates a later owner signature and
tests frozen analysis/admission rules on synthetic fixtures.  It contains no
training loop, scheduler client, credential use or cloud submission path.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from itertools import product
from math import comb
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.platform.whatif_composer import REGISTERED_SEED_COHORTS

METHOD_VERSION: Literal["benchmark-protocol-2.0"] = "benchmark-protocol-2.0"
DESIGN_REFERENCE: Literal["docs/platform/capacity_aware_benchmark_design.md"] = (
    "docs/platform/capacity_aware_benchmark_design.md"
)
CITATION_REFERENCE: Literal["docs/producer_citation_requirements.md"] = (
    "docs/producer_citation_requirements.md"
)

AlgorithmFamily = Literal[
    "mappo",
    "ippo",
    "qmix",
    "vdn",
    "independent_dqn",
    "deterministic_heuristic",
    "random",
]
TrainingAlgorithm = Literal["mappo", "ippo", "qmix", "vdn", "independent_dqn"]
CapacityRepresentationKind = Literal[
    "capacity_blind",
    "global_scalar",
    "per_rsu_vector",
    "local_observable",
    "provisioned_remaining",
    "local_utilisation_queue",
]
ActionTrack = Literal["local_v2i_v2v_unmasked", "local_v2i_v2v_feasibility_masked"]
RewardTrack = Literal[
    "balanced_qos_energy",
    "pure_qos",
    "outcome_coherent",
    "fairness_aware",
]
DomainId = Literal[
    "procedural_vec",
    "manchester_corridor",
    "sparse64_whole_fleet",
    "manchester_additional_periods",
    "sumo_networks",
    "dhaka_corridor",
]
AlgorithmRole = Literal["train_and_evaluate", "evaluation_only_control"]
AlgorithmParadigm = Literal[
    "centralised_actor_critic",
    "independent_actor_critic",
    "value_decomposition",
    "independent_value",
    "deterministic_rule",
    "random_policy",
]
VisibilityTiming = Literal["visible_before_action_same_tick", "not_visible"]

TRAINING_ALGORITHMS: tuple[TrainingAlgorithm, ...] = (
    "mappo",
    "ippo",
    "qmix",
    "vdn",
    "independent_dqn",
)
EVALUATION_ONLY_ALGORITHMS: tuple[AlgorithmFamily, ...] = (
    "deterministic_heuristic",
    "random",
)
CAPACITY_REPRESENTATIONS: tuple[CapacityRepresentationKind, ...] = (
    "capacity_blind",
    "global_scalar",
    "per_rsu_vector",
    "local_observable",
    "provisioned_remaining",
    "local_utilisation_queue",
)
ACTION_TRACKS: tuple[ActionTrack, ...] = (
    "local_v2i_v2v_unmasked",
    "local_v2i_v2v_feasibility_masked",
)
REWARD_TRACKS: tuple[RewardTrack, ...] = (
    "balanced_qos_energy",
    "pure_qos",
    "outcome_coherent",
    "fairness_aware",
)
DOMAIN_IDS: tuple[DomainId, ...] = (
    "procedural_vec",
    "manchester_corridor",
    "sparse64_whole_fleet",
    "manchester_additional_periods",
    "sumo_networks",
    "dhaka_corridor",
)
RESEARCH_QUESTIONS = (
    "capacity-awareness main effect under matched contracts",
    "algorithm-family main effect under matched contracts",
    "capacity-representation by algorithm-family interaction",
)
REQUIRED_ENDPOINT_SET = (
    "equal_weight_task_class_deadline_completion",
    "task.latency.mean_ms",
    "task.energy.mean_j",
    "task.completion_failure_composition",
    "action_offloading_behaviour",
    "persistent_minority_failure_concentration",
)
_NON_ADMITTED_MARKERS = ("b-cap 17d/19d", "bcap smoke", "147-repeat")
_LEAKAGE_MARKERS = ("best on evaluation", "highest evaluation", "picked after results")
_PRIVATE_MARKERS = ("/Users/", "/home/", "\\Users\\", "password", "credential", "token")


class BenchmarkProtocolError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


def _digest(value: object) -> str:
    material = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AlgorithmContract(ProtocolModel):
    family: AlgorithmFamily
    candidate_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: AlgorithmRole
    paradigm: AlgorithmParadigm
    action_support: Literal["discrete_local_v2i_v2v"]
    checkpoint_selection_rule: str
    training_interactions_per_seed: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_role_and_selection(self) -> AlgorithmContract:
        for marker in _LEAKAGE_MARKERS:
            if marker in self.checkpoint_selection_rule.lower():
                raise ValueError("CHECKPOINT_SELECTION_LEAKAGE")
        if self.role == "train_and_evaluate" and self.training_interactions_per_seed == 0:
            raise ValueError("training algorithms require a positive interaction budget")
        if self.role == "evaluation_only_control" and self.training_interactions_per_seed != 0:
            raise ValueError("heuristic/random controls must not claim training jobs")
        return self


class CapacityRepresentation(ProtocolModel):
    kind: CapacityRepresentationKind
    units: str
    normalisation_source: Literal["training_design"]
    missing_value_behaviour: Literal["refuse"]
    visibility_timing_rule: VisibilityTiming
    added_dimensions: int = Field(ge=0)
    training_min_value: float
    training_max_value: float

    @model_validator(mode="after")
    def validate_scale(self) -> CapacityRepresentation:
        if self.kind == "capacity_blind":
            if self.added_dimensions != 0 or self.visibility_timing_rule != "not_visible":
                raise ValueError("capacity-blind representation must add no visible dimension")
        elif self.added_dimensions == 0 or self.visibility_timing_rule == "not_visible":
            raise ValueError("capacity-aware representations must be visible before action")
        if self.training_max_value <= self.training_min_value:
            raise ValueError("CAPACITY_REPRESENTATION_UNFROZEN")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class CapacityFeature(ProtocolModel):
    representation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    values: tuple[float, ...]
    visible_before_action: bool


def construct_capacity_feature(
    representation: CapacityRepresentation,
    *,
    provisioned_values: tuple[float, ...] = (),
    remaining_values: tuple[float, ...] = (),
    utilisation_values: tuple[float, ...] = (),
    queue_values: tuple[float, ...] = (),
) -> CapacityFeature:
    """Build only from the frozen training-design scale, never held-out results."""

    channels: dict[CapacityRepresentationKind, tuple[float, ...]] = {
        "capacity_blind": (),
        "global_scalar": provisioned_values,
        "per_rsu_vector": provisioned_values,
        "local_observable": provisioned_values,
        "provisioned_remaining": provisioned_values + remaining_values,
        "local_utilisation_queue": utilisation_values + queue_values,
    }
    raw = channels[representation.kind]
    if len(raw) != representation.added_dimensions:
        raise BenchmarkProtocolError(
            "OBSERVATION_DIMENSION_MISMATCH",
            f"representation requires {representation.added_dimensions} values, got {len(raw)}",
        )
    low = representation.training_min_value
    high = representation.training_max_value
    if any(value < low or value > high for value in raw):
        raise BenchmarkProtocolError(
            "CAPACITY_REPRESENTATION_UNFROZEN",
            "capacity lies outside the frozen training-design scale",
        )
    return CapacityFeature(
        representation_digest=representation.digest(),
        values=tuple((value - low) / (high - low) for value in raw),
        visible_before_action=representation.kind != "capacity_blind",
    )


class DomainScope(ProtocolModel):
    domain_id: DomainId
    mobility_scope: str
    fleet_scope: str
    infrastructure_scope: str
    simulator_scope: str
    evidence_pool: Literal["separate"] = "separate"


class ContractSuite(ProtocolModel):
    observation_tracks: tuple[CapacityRepresentationKind, ...]
    action_tracks: tuple[ActionTrack, ...]
    reward_tracks: tuple[RewardTrack, ...]
    action_vocabulary: tuple[Literal["local", "v2i", "v2v"], ...]
    domain_pooling: Literal[False] = False

    @model_validator(mode="after")
    def validate_complete_suite(self) -> ContractSuite:
        if self.observation_tracks != CAPACITY_REPRESENTATIONS:
            raise ValueError("observation tracks must cover all selected representations")
        if self.action_tracks != ACTION_TRACKS or self.reward_tracks != REWARD_TRACKS:
            raise ValueError("action/reward tracks must match the owner-selected complete suite")
        if self.action_vocabulary != ("local", "v2i", "v2v"):
            raise ValueError("action vocabulary must remain local/V2I/V2V")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class SeedNamespaces(ProtocolModel):
    engineering: tuple[int, ...]
    training: tuple[int, ...]
    tuning: tuple[int, ...]
    evaluation: tuple[int, ...]

    @model_validator(mode="after")
    def validate_disjoint_fresh_counts(self) -> SeedNamespaces:
        expected = {"engineering": 3, "training": 10, "tuning": 5, "evaluation": 20}
        namespaces = {
            "engineering": set(self.engineering),
            "training": set(self.training),
            "tuning": set(self.tuning),
            "evaluation": set(self.evaluation),
        }
        for name, count in expected.items():
            if len(namespaces[name]) != count:
                raise ValueError(f"SEED_COUNT_MISMATCH: {name} requires {count} unique seeds")
        names = list(namespaces)
        for index, first in enumerate(names):
            for second in names[index + 1 :]:
                overlap = namespaces[first] & namespaces[second]
                if overlap:
                    raise ValueError(
                        f"SEED_NAMESPACE_CONTAMINATED: {first}/{second} share {sorted(overlap)}"
                    )
        spent = set().union(*(set(values) for values in REGISTERED_SEED_COHORTS.values()))
        for name, seeds in namespaces.items():
            collision = seeds & spent
            if collision:
                raise ValueError(f"SEED_NAMESPACE_CONTAMINATED: {name} reuses {sorted(collision)}")
        return self


class CheckpointPolicy(ProtocolModel):
    primary: Literal["terminal_checkpoint"]
    robustness_milestones_percent: tuple[Literal[25, 50, 75, 100], ...]
    heldout_selection_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_milestones(self) -> CheckpointPolicy:
        if self.robustness_milestones_percent != (25, 50, 75, 100):
            raise ValueError("checkpoint milestones must be exactly 25/50/75/100")
        return self


class PracticalThresholds(ProtocolModel):
    """Proposed study-scale thresholds, bound by the complete protocol digest."""

    deadline_completion_absolute: float = 0.01
    mean_latency_ms: float = 100.0
    mean_energy_j: float = 0.1
    failure_rate_absolute: float = 0.01
    action_share_absolute: float = 0.05
    persistent_minority_share_absolute: float = 0.02

    @model_validator(mode="after")
    def validate_frozen_thresholds(self) -> PracticalThresholds:
        if self.model_dump() != {
            "deadline_completion_absolute": 0.01,
            "mean_latency_ms": 100.0,
            "mean_energy_j": 0.1,
            "failure_rate_absolute": 0.01,
            "action_share_absolute": 0.05,
            "persistent_minority_share_absolute": 0.02,
        }:
            raise ValueError("practical thresholds must match the owner-selected protocol")
        return self


class StatisticalProtocol(ProtocolModel):
    paired_difference: Literal[True] = True
    paired_bootstrap_confidence: float = 0.95
    exact_sign_test: Literal[True] = True
    paired_permutation_test: Literal[True] = True
    confirmatory_multiplicity: Literal["holm_fwer_0.05"]
    exploratory_multiplicity: Literal["benjamini_hochberg_fdr_0.05"]
    practical_thresholds: PracticalThresholds
    minimum_successful_pairs: Literal[18] = 18
    planned_pairs: Literal[20] = 20
    ties_reported: Literal[True] = True
    nulls_are_valid_results: Literal[True] = True
    domains_analysed_separately: Literal[True] = True
    post_hoc_seed_expansion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_confidence(self) -> StatisticalProtocol:
        if self.paired_bootstrap_confidence != 0.95:
            raise ValueError("paired bootstrap confidence must remain 0.95")
        return self


class ComputePlan(ProtocolModel):
    primary_scheduler: Literal["gcp_batch"]
    failover_scheduler: Literal["aws_batch"]
    accelerator_calibration: tuple[Literal["l4", "a100", "h100"], ...]
    scientific_cross_accelerator_reproducibility: Literal[True] = True
    maximum_gpu_hours_estimate: float = 5000.0
    maximum_cost_gbp_estimate: float = 5000.0
    calibration_cost_gbp_estimate: float = 250.0
    pilot_cost_gbp_estimate: float = 750.0
    estimate_only: Literal[True] = True
    authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_frozen_estimates(self) -> ComputePlan:
        if (
            self.maximum_gpu_hours_estimate,
            self.maximum_cost_gbp_estimate,
            self.calibration_cost_gbp_estimate,
            self.pilot_cost_gbp_estimate,
        ) != (5000.0, 5000.0, 250.0, 750.0):
            raise ValueError("resource estimates must match the owner-selected ceilings")
        return self


class FactorialCell(ProtocolModel):
    cell_id: str
    algorithm: TrainingAlgorithm
    capacity_representation: CapacityRepresentationKind
    reward_track: RewardTrack
    action_track: ActionTrack
    contract_suite_digest: str
    domain_ids: tuple[DomainId, ...]
    training_seed_count: Literal[10] = 10
    matched_interactions_per_seed: int = Field(ge=1)


class EvaluationOnlyControl(ProtocolModel):
    algorithm: Literal["deterministic_heuristic", "random"]
    domain_ids: tuple[DomainId, ...]
    capacity_representations: tuple[CapacityRepresentationKind, ...]
    action_tracks: tuple[ActionTrack, ...]
    training_jobs: Literal[0] = 0


class FactorialPlan(ProtocolModel):
    cells: tuple[FactorialCell, ...]
    evaluation_only_controls: tuple[EvaluationOnlyControl, ...]
    compatible_training_cells: Literal[240] = 240
    training_jobs: Literal[2400] = 2400
    full_compatible_factorial: Literal[True] = True
    matched_budget: Literal[True] = True
    estimates_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_counts(self) -> FactorialPlan:
        if len(self.cells) != self.compatible_training_cells:
            raise ValueError("FACTORIAL_CELL_COUNT_MISMATCH")
        if sum(int(cell.training_seed_count) for cell in self.cells) != self.training_jobs:
            raise ValueError("TRAINING_JOB_COUNT_MISMATCH")
        if len({cell.cell_id for cell in self.cells}) != len(self.cells):
            raise ValueError("factorial cell ids must be unique")
        return self


class BenchmarkProtocol(ProtocolModel):
    schema_version: Literal["2.0"] = "2.0"
    method_version: Literal["benchmark-protocol-2.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/capacity_aware_benchmark_design.md"] = DESIGN_REFERENCE
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    evidence: Literal[False] = False
    creates_new_evidence: Literal[False] = False
    predeclaration_status: Literal["proposed_unsigned"] = "proposed_unsigned"
    research_questions: tuple[str, ...]
    algorithms: tuple[AlgorithmContract, ...]
    capacity_representations: tuple[CapacityRepresentation, ...]
    domains: tuple[DomainScope, ...]
    contracts: ContractSuite
    capacity_arms: tuple[float, ...]
    fleet_grid: tuple[str, ...]
    infrastructure_grid: tuple[str, ...]
    seeds: SeedNamespaces
    primary_endpoint: Literal["equal_weight_task_class_deadline_completion"]
    reported_endpoints: tuple[str, ...]
    checkpoint_policy: CheckpointPolicy
    statistics: StatisticalProtocol
    compute: ComputePlan
    training_interactions_per_seed: int = Field(ge=1)
    publishable_null: str = Field(min_length=20)
    deviation_policy: str = Field(min_length=20)
    motivating_context: tuple[str, ...]
    evidence_inputs: tuple[str, ...] = ()
    owner_decisions_open: tuple[()] = ()

    @model_validator(mode="after")
    def validate_owner_selected_protocol(self) -> BenchmarkProtocol:
        if self.research_questions != RESEARCH_QUESTIONS:
            raise ValueError("research questions do not match the owner-selected scope")
        families = tuple(item.family for item in self.algorithms)
        if families != TRAINING_ALGORITHMS + EVALUATION_ONLY_ALGORITHMS:
            raise ValueError("algorithm families do not match the owner-selected complete set")
        kinds = tuple(item.kind for item in self.capacity_representations)
        if kinds != CAPACITY_REPRESENTATIONS:
            raise ValueError("capacity representations do not match the complete set")
        if tuple(item.domain_id for item in self.domains) != DOMAIN_IDS:
            raise ValueError("domains do not match the owner-selected separate scopes")
        if any(item.evidence_pool != "separate" for item in self.domains):
            raise ValueError("INCOMPATIBLE_DOMAIN_POOLING")
        missing = [item for item in REQUIRED_ENDPOINT_SET if item not in self.reported_endpoints]
        if missing:
            raise ValueError(f"PRIMARY_ENDPOINT_MISSING: {missing}")
        if len(set(self.capacity_arms)) != len(self.capacity_arms) or len(self.capacity_arms) < 2:
            raise ValueError("capacity arms must be unique and contain a comparison")
        if _contains_private(self.model_dump(mode="json")):
            raise ValueError("PRIVATE_CONTENT_DETECTED")
        for entry in self.evidence_inputs:
            if any(marker in entry.lower() for marker in _NON_ADMITTED_MARKERS):
                raise ValueError("EXISTING_NON_ADMITTED_REUSE")
        if self.evidence_inputs:
            raise ValueError("EXISTING_RESULT_REUSE")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


def _contains_private(value: object) -> bool:
    material = json.dumps(value, sort_keys=True).lower()
    return any(marker.lower() in material for marker in _PRIVATE_MARKERS)


def _algorithm_contracts(interactions: int) -> tuple[AlgorithmContract, ...]:
    specs: tuple[tuple[AlgorithmFamily, AlgorithmRole, AlgorithmParadigm], ...] = (
        ("mappo", "train_and_evaluate", "centralised_actor_critic"),
        ("ippo", "train_and_evaluate", "independent_actor_critic"),
        ("qmix", "train_and_evaluate", "value_decomposition"),
        ("vdn", "train_and_evaluate", "value_decomposition"),
        ("independent_dqn", "train_and_evaluate", "independent_value"),
        ("deterministic_heuristic", "evaluation_only_control", "deterministic_rule"),
        ("random", "evaluation_only_control", "random_policy"),
    )
    return tuple(
        AlgorithmContract(
            family=family,
            candidate_contract_digest=hashlib.sha256(
                f"benchmark:{family}:candidate-contract:v1".encode()
            ).hexdigest(),
            role=role,
            paradigm=paradigm,
            action_support="discrete_local_v2i_v2v",
            checkpoint_selection_rule=(
                "terminal checkpoint primary; milestones 25/50/75/100 robustness only"
                if role == "train_and_evaluate"
                else "deterministic policy; no trained checkpoint"
            ),
            training_interactions_per_seed=interactions if role == "train_and_evaluate" else 0,
        )
        for family, role, paradigm in specs
    )


def _capacity_representations() -> tuple[CapacityRepresentation, ...]:
    dimensions: tuple[tuple[CapacityRepresentationKind, int, VisibilityTiming], ...] = (
        ("capacity_blind", 0, "not_visible"),
        ("global_scalar", 1, "visible_before_action_same_tick"),
        ("per_rsu_vector", 10, "visible_before_action_same_tick"),
        ("local_observable", 1, "visible_before_action_same_tick"),
        ("provisioned_remaining", 20, "visible_before_action_same_tick"),
        ("local_utilisation_queue", 2, "visible_before_action_same_tick"),
    )
    return tuple(
        CapacityRepresentation(
            kind=kind,
            units="normalised by frozen training-design envelope",
            normalisation_source="training_design",
            missing_value_behaviour="refuse",
            visibility_timing_rule=timing,
            added_dimensions=count,
            training_min_value=0.0,
            training_max_value=2.5,
        )
        for kind, count, timing in dimensions
    )


def _domains() -> tuple[DomainScope, ...]:
    values: tuple[tuple[DomainId, str], ...] = (
        ("procedural_vec", "procedural VEC mobility and load grid"),
        ("manchester_corridor", "pinned Manchester corridor periods"),
        ("sparse64_whole_fleet", "whole-fleet Sparse-64 compatible future design"),
        ("manchester_additional_periods", "additional safe Manchester periods"),
        ("sumo_networks", "pinned SUMO network fixtures"),
        ("dhaka_corridor", "Dhaka corridor synthetic/approved aggregate scope"),
    )
    return tuple(
        DomainScope(
            domain_id=domain_id,
            mobility_scope=description,
            fleet_scope="fleet-size and composition grid",
            infrastructure_scope="site-count, placement and capacity grid",
            simulator_scope="domain-pinned compatible simulator adapter",
        )
        for domain_id, description in values
    )


def build_owner_selected_protocol() -> BenchmarkProtocol:
    """Return the exact unsigned protocol selected by the owner on 2 August 2026."""

    interactions = 5_000_000
    contracts = ContractSuite(
        observation_tracks=CAPACITY_REPRESENTATIONS,
        action_tracks=ACTION_TRACKS,
        reward_tracks=REWARD_TRACKS,
        action_vocabulary=("local", "v2i", "v2v"),
    )
    return BenchmarkProtocol(
        research_questions=RESEARCH_QUESTIONS,
        algorithms=_algorithm_contracts(interactions),
        capacity_representations=_capacity_representations(),
        domains=_domains(),
        contracts=contracts,
        capacity_arms=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.5),
        fleet_grid=("small", "medium", "uk2030", "whole_fleet", "composition_shifted"),
        infrastructure_grid=("sparse", "corridor", "full", "placement_shifted"),
        seeds=SeedNamespaces(
            engineering=(2000, 2001, 2002),
            training=tuple(range(2100, 2110)),
            tuning=tuple(range(2200, 2205)),
            evaluation=tuple(range(2300, 2320)),
        ),
        primary_endpoint="equal_weight_task_class_deadline_completion",
        reported_endpoints=REQUIRED_ENDPOINT_SET,
        checkpoint_policy=CheckpointPolicy(
            primary="terminal_checkpoint",
            robustness_milestones_percent=(25, 50, 75, 100),
        ),
        statistics=StatisticalProtocol(
            confirmatory_multiplicity="holm_fwer_0.05",
            exploratory_multiplicity="benjamini_hochberg_fdr_0.05",
            practical_thresholds=PracticalThresholds(),
        ),
        compute=ComputePlan(
            primary_scheduler="gcp_batch",
            failover_scheduler="aws_batch",
            accelerator_calibration=("l4", "a100", "h100"),
        ),
        training_interactions_per_seed=interactions,
        publishable_null=(
            "no predeclared practically meaningful capacity, algorithm or interaction "
            "difference is a complete valid result"
        ),
        deviation_policy=(
            "retain every deviation, exclude only by predeclared rules and never expand seeds "
            "or select checkpoints from held-out outcomes"
        ),
        motivating_context=(
            "confirmed action invariance motivates capacity-aware training",
            "old B-CAP and Sparse-64 records motivate scope only and are never evidence inputs",
        ),
    )


def build_factorial_plan(protocol: BenchmarkProtocol) -> FactorialPlan:
    """Enumerate 5 algorithms × 6 representations × 4 rewards × 2 action tracks."""

    contract_digest = protocol.contracts.digest()
    cells: list[FactorialCell] = []
    for algorithm in TRAINING_ALGORITHMS:
        for representation in CAPACITY_REPRESENTATIONS:
            for reward in REWARD_TRACKS:
                for action in ACTION_TRACKS:
                    cell_id = f"{algorithm}__{representation}__{reward}__{action}"
                    cells.append(
                        FactorialCell(
                            cell_id=cell_id,
                            algorithm=algorithm,
                            capacity_representation=representation,
                            reward_track=reward,
                            action_track=action,
                            contract_suite_digest=contract_digest,
                            domain_ids=DOMAIN_IDS,
                            matched_interactions_per_seed=protocol.training_interactions_per_seed,
                        )
                    )
    controls = (
        EvaluationOnlyControl(
            algorithm="deterministic_heuristic",
            domain_ids=DOMAIN_IDS,
            capacity_representations=CAPACITY_REPRESENTATIONS,
            action_tracks=ACTION_TRACKS,
        ),
        EvaluationOnlyControl(
            algorithm="random",
            domain_ids=DOMAIN_IDS,
            capacity_representations=CAPACITY_REPRESENTATIONS,
            action_tracks=ACTION_TRACKS,
        ),
    )
    return FactorialPlan(cells=tuple(cells), evaluation_only_controls=controls)


class MatchedBudgetAccount(ProtocolModel):
    compatible_training_cells: int
    training_jobs: int
    training_interactions_per_job: int
    total_training_interactions: int
    gpu_ceiling_hours_estimate: float
    cost_ceiling_gbp_estimate: float
    estimate_only: Literal[True] = True
    authority: Literal[False] = False


def account_matched_budget(protocol: BenchmarkProtocol) -> MatchedBudgetAccount:
    plan = build_factorial_plan(protocol)
    return MatchedBudgetAccount(
        compatible_training_cells=plan.compatible_training_cells,
        training_jobs=plan.training_jobs,
        training_interactions_per_job=protocol.training_interactions_per_seed,
        total_training_interactions=(plan.training_jobs * protocol.training_interactions_per_seed),
        gpu_ceiling_hours_estimate=protocol.compute.maximum_gpu_hours_estimate,
        cost_ceiling_gbp_estimate=protocol.compute.maximum_cost_gbp_estimate,
    )


class ResourceEligibility(ProtocolModel):
    protocol_digest: str
    requested_gpu_hours_estimate: float = Field(ge=0)
    requested_cost_gbp_estimate: float = Field(ge=0)
    within_estimated_ceiling: Literal[True] = True
    allocation_created: Literal[False] = False
    authority: Literal[False] = False


def validate_resource_estimate(
    protocol: BenchmarkProtocol, *, gpu_hours: float, cost_gbp: float
) -> ResourceEligibility:
    """Check proposed bounds without allocating resources or granting authority."""

    if (
        gpu_hours > protocol.compute.maximum_gpu_hours_estimate
        or cost_gbp > protocol.compute.maximum_cost_gbp_estimate
    ):
        raise BenchmarkProtocolError(
            "RESOURCE_BUDGET_EXCEEDED",
            "requested estimate exceeds the frozen GPU-hour or cost ceiling",
        )
    return ResourceEligibility(
        protocol_digest=protocol.digest(),
        requested_gpu_hours_estimate=gpu_hours,
        requested_cost_gbp_estimate=cost_gbp,
    )


def check_compatibility(
    reference: AlgorithmContract, candidate: AlgorithmContract
) -> Literal["comparable", "INCOMPATIBLE"]:
    if (
        reference.action_support != candidate.action_support
        or reference.role != candidate.role
        or reference.training_interactions_per_seed != candidate.training_interactions_per_seed
    ):
        return "INCOMPATIBLE"
    return "comparable"


class PairedSyntheticResult(ProtocolModel):
    seed: int
    reference_value: float
    candidate_value: float


class BenchmarkAnalysis(ProtocolModel):
    protocol_digest: str
    evaluated_pairs: int
    mean_paired_difference: float
    paired_bootstrap_interval_95: tuple[float, float]
    exact_sign_test_p: float = Field(ge=0, le=1)
    exact_paired_permutation_p: float = Field(ge=0, le=1)
    holm_adjusted_p: tuple[float, ...]
    benjamini_hochberg_adjusted_p: tuple[float, ...]
    verdict: Literal["PUBLISHABLE_NULL", "SYNTHETIC_DIRECTION"]
    methods_exercised: tuple[str, ...]
    deviations: tuple[str, ...]
    evidence: Literal[False] = False
    confirmatory: Literal[False] = False
    synthetic_dry_run: Literal[True] = True


def _quantile(values: tuple[float, ...], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _paired_bootstrap_interval(differences: tuple[float, ...]) -> tuple[float, float]:
    count = len(differences)
    means = tuple(
        sum(differences[index] for index in sample) / count
        for sample in product(range(count), repeat=count)
    )
    return (_quantile(means, 0.025), _quantile(means, 0.975))


def _exact_sign_test(differences: tuple[float, ...]) -> float:
    positives = sum(value > 0 for value in differences)
    negatives = sum(value < 0 for value in differences)
    non_ties = positives + negatives
    if non_ties == 0:
        return 1.0
    smaller = min(positives, negatives)
    lower_tail = sum(comb(non_ties, index) for index in range(smaller + 1)) / (2**non_ties)
    return float(min(1.0, 2 * lower_tail))


def _exact_paired_permutation(differences: tuple[float, ...]) -> float:
    nonzero = tuple(value for value in differences if value != 0)
    if not nonzero:
        return 1.0
    observed = abs(sum(nonzero) / len(nonzero))
    statistics = tuple(
        abs(sum(value * sign for value, sign in zip(nonzero, signs, strict=True)) / len(nonzero))
        for signs in product((-1, 1), repeat=len(nonzero))
    )
    return sum(value >= observed for value in statistics) / len(statistics)


def _holm_adjust(values: tuple[float, ...]) -> tuple[float, ...]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    adjusted = [0.0] * len(values)
    running = 0.0
    for rank, (original_index, value) in enumerate(ordered):
        running = max(running, min(1.0, (len(values) - rank) * value))
        adjusted[original_index] = running
    return tuple(adjusted)


def _benjamini_hochberg_adjust(values: tuple[float, ...]) -> tuple[float, ...]:
    ordered = sorted(enumerate(values), key=lambda item: item[1], reverse=True)
    adjusted = [0.0] * len(values)
    running = 1.0
    total = len(values)
    for reverse_rank, (original_index, value) in enumerate(ordered):
        rank = total - reverse_rank
        running = min(running, min(1.0, value * total / rank))
        adjusted[original_index] = running
    return tuple(adjusted)


def synthetic_dry_run(protocol: BenchmarkProtocol) -> BenchmarkAnalysis:
    results = tuple(
        PairedSyntheticResult(
            seed=seed,
            reference_value=float(100 + seed % 7),
            candidate_value=float(100 + seed % 7),
        )
        for seed in protocol.seeds.engineering
    )
    return analyse_benchmark(
        protocol,
        results,
        deviations=("synthetic fixture deviation retained",),
        synthetic=True,
    )


def analyse_benchmark(
    protocol: BenchmarkProtocol,
    results: tuple[PairedSyntheticResult, ...],
    *,
    deviations: tuple[str, ...],
    synthetic: Literal[True],
) -> BenchmarkAnalysis:
    if synthetic is not True:
        raise BenchmarkProtocolError("COMPUTE_AUTHORITY_MISSING", "only synthetic self-tests run")
    seeds = [item.seed for item in results]
    if len(seeds) != len(set(seeds)) or set(seeds) != set(protocol.seeds.engineering):
        raise BenchmarkProtocolError(
            "SEED_NAMESPACE_CONTAMINATED",
            "synthetic analysis requires the exact engineering seed namespace",
        )
    differences = tuple(item.candidate_value - item.reference_value for item in results)
    mean_difference = sum(differences) / len(differences)
    sign_p = _exact_sign_test(differences)
    permutation_p = _exact_paired_permutation(differences)
    unadjusted = (sign_p, permutation_p)
    verdict: Literal["PUBLISHABLE_NULL", "SYNTHETIC_DIRECTION"] = (
        "PUBLISHABLE_NULL" if all(value == 0 for value in differences) else "SYNTHETIC_DIRECTION"
    )
    return BenchmarkAnalysis(
        protocol_digest=protocol.digest(),
        evaluated_pairs=len(results),
        mean_paired_difference=mean_difference,
        paired_bootstrap_interval_95=_paired_bootstrap_interval(differences),
        exact_sign_test_p=sign_p,
        exact_paired_permutation_p=permutation_p,
        holm_adjusted_p=_holm_adjust(unadjusted),
        benjamini_hochberg_adjusted_p=_benjamini_hochberg_adjust(unadjusted),
        verdict=verdict,
        methods_exercised=(
            "paired_difference",
            "paired_bootstrap_95",
            "exact_sign_test",
            "paired_permutation",
            "holm_fwer_0.05",
            "benjamini_hochberg_fdr_0.05",
        ),
        deviations=deviations,
    )


class PredeclarationArtifact(ProtocolModel):
    protocol_digest: str
    markdown: str
    markdown_sha256: str
    status: Literal["proposed_unsigned"] = "proposed_unsigned"
    signature_present: Literal[False] = False
    evidence: Literal[False] = False


def render_predeclaration_draft(protocol: BenchmarkProtocol) -> str:
    plan = build_factorial_plan(protocol)
    lines = [
        "# Capacity-aware and multi-algorithm benchmark — PROPOSED / UNSIGNED",
        "",
        "This predeclaration creates no evidence, signature, cloud authority or execution.",
        "",
        f"Protocol digest: `{protocol.digest()}`",
        f"Design reference: {protocol.design_reference}",
        f"Citation requirements: {CITATION_REFERENCE}",
        "",
        "## Research questions",
        "",
        *[f"- {item}" for item in protocol.research_questions],
        "",
        "## Frozen factorial",
        "",
        f"- compatible training cells: {plan.compatible_training_cells}",
        f"- training jobs: {plan.training_jobs}",
        f"- trained algorithms: {', '.join(TRAINING_ALGORITHMS)}",
        f"- evaluation-only controls: {', '.join(EVALUATION_ONLY_ALGORITHMS)}",
        f"- capacity representations: {', '.join(CAPACITY_REPRESENTATIONS)}",
        f"- action tracks: {', '.join(ACTION_TRACKS)}",
        f"- reward tracks: {', '.join(REWARD_TRACKS)}",
        f"- separately analysed domains: {', '.join(DOMAIN_IDS)}",
        "",
        "## Primary endpoint and statistics",
        "",
        f"Primary: {protocol.primary_endpoint}",
        *[f"- report: {item}" for item in protocol.reported_endpoints],
        "- paired difference and 95% paired bootstrap interval",
        "- exact sign test and paired permutation test",
        "- Holm FWER 0.05 confirmatory; BH FDR 0.05 exploratory",
        (
            "- practical thresholds (protocol-digest-bound): 0.01 deadline/failure absolute, "
            "100 ms latency, 0.1 J energy, 0.05 action share and 0.02 minority share"
        ),
        "- at least 18 of 20 fresh pairs; no post-hoc seed expansion",
        "",
        "## Seeds, checkpoints and compute estimates",
        "",
        f"- engineering: {protocol.seeds.engineering}",
        f"- training: {protocol.seeds.training}",
        f"- tuning: {protocol.seeds.tuning}",
        f"- fresh paired evaluation: {protocol.seeds.evaluation}",
        "- terminal checkpoint primary; 25/50/75/100% milestones robustness only",
        "- GCP Batch primary; AWS Batch failover",
        "- L4/A100/H100 calibration and cross-accelerator reproducibility",
        "- ceilings: 5,000 GPU-hours / GBP 5,000; calibration GBP 250; pilot GBP 750",
        "- all resource figures are estimates until the final owner signature binds them",
        "",
        "## Null, deviations and admission",
        "",
        protocol.publishable_null,
        protocol.deviation_policy,
        "Domains remain separate. Existing B-CAP and prior Sparse-64 returns are not inputs.",
        (
            "Rule-based admission eligibility requires exact scope/digest, >=18 pairs, frozen "
            "analysis, multiplicity completion and only predeclared deviations; eligibility is "
            "not itself admission."
        ),
        "",
        "## Sign-off (EMPTY)",
        "",
        "| field | value |",
        "|---|---|",
        "| owner identity | |",
        "| owner role | |",
        "| signed at UTC | |",
        "| final markdown SHA-256 | |",
        "| protocol SHA-256 | |",
        "| bounded compute/spend authority | |",
        "",
    ]
    return "\n".join(lines)


def freeze_predeclaration(protocol: BenchmarkProtocol) -> PredeclarationArtifact:
    markdown = render_predeclaration_draft(protocol)
    return PredeclarationArtifact(
        protocol_digest=protocol.digest(),
        markdown=markdown,
        markdown_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    )


class SignedPredeclaration(ProtocolModel):
    protocol_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_markdown_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signer_role: Literal["human_owner"]
    signature_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    signed_at_utc: datetime
    scope_and_budget_unchanged: Literal[True]
    policy_validated: Literal[True]

    @model_validator(mode="after")
    def validate_time(self) -> SignedPredeclaration:
        if self.signed_at_utc.tzinfo is None or self.signed_at_utc.utcoffset() is None:
            raise ValueError("signature time must be timezone-aware")
        return self


class ExecutionEligibility(ProtocolModel):
    protocol_digest: str
    predeclaration_digest: str
    eligible: Literal[True] = True
    automatic_within_signed_scope: Literal[True] = True
    external_scheduler_required: Literal[True] = True
    execution_started: Literal[False] = False
    evidence: Literal[False] = False


def request_execution(
    protocol: BenchmarkProtocol,
    *,
    artifact: PredeclarationArtifact | None = None,
    signature: SignedPredeclaration | None = None,
) -> ExecutionEligibility:
    """Validate automatic eligibility; never submit a job or contact a scheduler."""

    if protocol.owner_decisions_open:
        raise BenchmarkProtocolError("OWNER_DECISION_MISSING", "owner decisions remain open")
    frozen = artifact or freeze_predeclaration(protocol)
    if frozen.protocol_digest != protocol.digest():
        raise BenchmarkProtocolError("PREDECLARATION_DIGEST_MISMATCH", "protocol digest changed")
    if signature is None:
        raise BenchmarkProtocolError("PREDECLARATION_UNSIGNED", "human owner signature is absent")
    if (
        signature.protocol_digest != protocol.digest()
        or signature.final_markdown_sha256 != frozen.markdown_sha256
    ):
        raise BenchmarkProtocolError(
            "PREDECLARATION_DIGEST_MISMATCH",
            "signature does not bind the exact protocol and final markdown",
        )
    return ExecutionEligibility(
        protocol_digest=protocol.digest(),
        predeclaration_digest=frozen.markdown_sha256,
    )


class CampaignAnalysisReceipt(ProtocolModel):
    protocol_digest: str
    predeclaration_digest: str
    successful_pairs: int = Field(ge=0)
    frozen_analysis_complete: bool
    multiplicity_complete: bool
    domains_separate: bool
    seed_namespaces_unchanged: bool
    checkpoint_rule_followed: bool
    deviations: tuple[str, ...]
    deviations_predeclared_acceptable: bool


class AdmissionEligibility(ProtocolModel):
    eligible: bool
    reasons: tuple[str, ...]
    protocol_digest: str
    automatic_rule_evaluation: Literal[True] = True
    admission_created: Literal[False] = False
    evidence_created: Literal[False] = False


def assess_admission_eligibility(
    protocol: BenchmarkProtocol,
    artifact: PredeclarationArtifact,
    signature: SignedPredeclaration,
    receipt: CampaignAnalysisReceipt,
) -> AdmissionEligibility:
    reasons: list[str] = []
    try:
        request_execution(protocol, artifact=artifact, signature=signature)
    except BenchmarkProtocolError as error:
        reasons.append(error.code)
    if receipt.protocol_digest != protocol.digest():
        reasons.append("PROTOCOL_DIGEST_MISMATCH")
    if receipt.predeclaration_digest != artifact.markdown_sha256:
        reasons.append("PREDECLARATION_DIGEST_MISMATCH")
    if receipt.successful_pairs < protocol.statistics.minimum_successful_pairs:
        reasons.append("MINIMUM_SUCCESSFUL_PAIRS_NOT_MET")
    if not receipt.frozen_analysis_complete:
        reasons.append("FROZEN_ANALYSIS_INCOMPLETE")
    if not receipt.multiplicity_complete:
        reasons.append("MULTIPLICITY_INCOMPLETE")
    if not receipt.domains_separate:
        reasons.append("INCOMPATIBLE_DOMAIN_POOLING")
    if not receipt.seed_namespaces_unchanged:
        reasons.append("SEED_NAMESPACE_CHANGED")
    if not receipt.checkpoint_rule_followed:
        reasons.append("CHECKPOINT_SELECTION_DEVIATION")
    if not receipt.deviations_predeclared_acceptable:
        reasons.append("EXECUTION_DEVIATION_OUTSIDE_RULE")
    return AdmissionEligibility(
        eligible=not reasons,
        reasons=tuple(reasons),
        protocol_digest=protocol.digest(),
    )
