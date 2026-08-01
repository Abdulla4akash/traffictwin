"""Capacity-aware benchmark tooling (post-v1 B-1, §6 gates 1-2 ONLY).

Implements ``docs/platform/capacity_aware_benchmark_design.md`` up to its
own execution boundary: the versioned protocol schema, actor-compatibility
checking, capacity-representation freezing, a synthetic end-to-end dry run,
and the UNSIGNED predeclaration draft. No experiment or compute campaign can
start from this module — there is no execution path, no cloud submission,
no credential use, and ``request_execution`` exists only to refuse with the
gates that are missing.

The research questions stay honest: whether a capacity-aware policy behaves
differently, and whether an alternative algorithm differs mechanically, are
open questions whose null or worse outcomes are complete results. An
algorithm name alone is not a baseline — unmatched contracts report
``INCOMPATIBLE`` and are never ranked. Existing B-CAP and Sparse-64
diagnostics may motivate protocol choices but can never be reused as
admitted benchmark evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.platform.whatif_composer import REGISTERED_SEED_COHORTS

METHOD_VERSION: Literal["benchmark-protocol-1.0"] = "benchmark-protocol-1.0"
DESIGN_REFERENCE: Literal["docs/platform/capacity_aware_benchmark_design.md"] = (
    "docs/platform/capacity_aware_benchmark_design.md"
)
CITATION_REFERENCE: Literal["docs/producer_citation_requirements.md"] = (
    "docs/producer_citation_requirements.md"
)

#: Endpoints that must be reported together — outcome coherence, not latency.
REQUIRED_ENDPOINT_SET = (
    "task.latency.mean_ms",
    "tos.task.deadline_success.rate",
    "task.completion_failure_composition",
    "action_offloading_behaviour",
)

#: Non-admitted artifacts that may motivate but never evidence.
_NON_ADMITTED_MARKERS = ("sparse64", "b-cap 17d/19d", "bcap smoke", "gpu-track")
_LEAKAGE_MARKERS = ("best on evaluation", "highest evaluation", "picked after results")


class BenchmarkProtocolError(RuntimeError):
    """Typed refusal; the tooling fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class ActorCompatibilityRecord(ProtocolModel):
    """One actor family's contract; comparability is checked, not assumed."""

    family: str
    implementation: str
    action_support: Literal["discrete", "continuous"]
    observation_dimensions: int = Field(ge=1)
    reward_contract: str
    checkpoint_selection_rule: str
    training_interaction_budget: int = Field(ge=1)

    @model_validator(mode="after")
    def refuse_selection_leakage(self) -> ActorCompatibilityRecord:
        lowered = self.checkpoint_selection_rule.lower()
        for marker in _LEAKAGE_MARKERS:
            if marker in lowered:
                raise ValueError(
                    "CHECKPOINT_SELECTION_LEAKAGE: the selection rule conditions on "
                    "evaluation performance; selection must be fixed pre-hoc"
                )
        return self


class CapacityRepresentation(ProtocolModel):
    """The frozen capacity feature — every §4 question answered up front."""

    kind: Literal["scalar_total", "per_rsu_vector", "local_observable"]
    units: str
    normalisation_source: Literal["training_design"]
    missing_value_behaviour: str
    represents: Literal["provisioned", "remaining", "both"]
    visibility_timing_rule: str
    added_dimensions: int = Field(ge=1)
    training_min_value: float
    training_max_value: float

    @model_validator(mode="after")
    def validate_training_scale(self) -> CapacityRepresentation:
        if self.training_max_value <= self.training_min_value:
            raise ValueError(
                "CAPACITY_REPRESENTATION_UNFROZEN: training maximum must exceed training minimum"
            )
        return self

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


class CapacityFeature(ProtocolModel):
    """Capacity values transformed only by the frozen training-design scale."""

    representation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    values: tuple[float, ...] = Field(min_length=1)
    visible_before_action: Literal[True] = True


class MatchedBudgetAccount(ProtocolModel):
    """Structural budget equality; resource figures remain non-authoritative estimates."""

    reference_interactions: int = Field(ge=1)
    candidate_interactions: int = Field(ge=1)
    wall_clock_ceiling_hours_estimate: float = Field(gt=0.0)
    gpu_ceiling_hours_estimate: float = Field(gt=0.0)
    estimate_only: Literal[True] = True
    authority: Literal[False] = False


def construct_capacity_feature(
    representation: CapacityRepresentation,
    *,
    provisioned_values: tuple[float, ...],
    remaining_values: tuple[float, ...] | None = None,
) -> CapacityFeature:
    """Build the capacity feature without consulting evaluation-arm statistics."""

    if not provisioned_values:
        raise BenchmarkProtocolError(
            "CAPACITY_REPRESENTATION_UNFROZEN", "at least one provisioned value is required"
        )
    if representation.represents in {"remaining", "both"} and remaining_values is None:
        raise BenchmarkProtocolError(
            "CAPACITY_REPRESENTATION_UNFROZEN",
            "the frozen representation requires remaining-capacity values",
        )
    if remaining_values is not None and len(remaining_values) != len(provisioned_values):
        raise BenchmarkProtocolError(
            "OBSERVATION_DIMENSION_MISMATCH",
            "provisioned and remaining capacity vectors must have the same length",
        )
    raw_values = {
        "provisioned": provisioned_values,
        "remaining": remaining_values or (),
        "both": provisioned_values + (remaining_values or ()),
    }[representation.represents]
    if len(raw_values) != representation.added_dimensions:
        raise BenchmarkProtocolError(
            "OBSERVATION_DIMENSION_MISMATCH",
            f"frozen feature expects {representation.added_dimensions} values, got "
            f"{len(raw_values)}",
        )
    low = representation.training_min_value
    high = representation.training_max_value
    if any(value < low or value > high for value in raw_values):
        raise BenchmarkProtocolError(
            "CAPACITY_REPRESENTATION_UNFROZEN",
            "capacity lies outside the frozen training-design scale; evaluation values "
            "are never used to rescale it",
        )
    return CapacityFeature(
        representation_digest=representation.digest(),
        values=tuple((value - low) / (high - low) for value in raw_values),
    )


def account_matched_budget(protocol: BenchmarkProtocol) -> MatchedBudgetAccount:
    """Expose equality and bounded estimates without granting compute authority."""

    return MatchedBudgetAccount(
        reference_interactions=protocol.reference_actor.training_interaction_budget,
        candidate_interactions=protocol.candidate_actor.training_interaction_budget,
        wall_clock_ceiling_hours_estimate=protocol.wall_clock_ceiling_hours,
        gpu_ceiling_hours_estimate=protocol.gpu_ceiling_hours,
    )


class SeedNamespaces(ProtocolModel):
    """Disjoint, newly declared namespaces; contamination refuses."""

    training: tuple[int, ...]
    tuning: tuple[int, ...]
    dry_run: tuple[int, ...]
    evaluation: tuple[int, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_disjoint_and_clean(self) -> SeedNamespaces:
        namespaces = {
            "training": set(self.training),
            "tuning": set(self.tuning),
            "dry_run": set(self.dry_run),
            "evaluation": set(self.evaluation),
        }
        names = list(namespaces)
        for index, first in enumerate(names):
            for second in names[index + 1 :]:
                overlap = namespaces[first] & namespaces[second]
                if overlap:
                    raise ValueError(
                        f"SEED_NAMESPACE_CONTAMINATED: {first} and {second} share "
                        f"seeds {sorted(overlap)}"
                    )
        registered: set[int] = set()
        for cohort in REGISTERED_SEED_COHORTS.values():
            registered |= set(cohort)
        for name, seeds in namespaces.items():
            spent = seeds & registered
            if spent:
                raise ValueError(
                    f"SEED_NAMESPACE_CONTAMINATED: {name} names already-registered "
                    f"seeds {sorted(spent)}; inspected seeds cannot become unseen "
                    "benchmark seeds"
                )
        return self


class BenchmarkProtocol(ProtocolModel):
    """The versioned protocol; freezing it is gate 2, signing is gate 3."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["benchmark-protocol-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/capacity_aware_benchmark_design.md"] = DESIGN_REFERENCE
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    evidence: Literal[False] = False
    traces: tuple[str, ...] = Field(min_length=1)
    fleet_preset: str
    capacity_arms: tuple[str, ...] = Field(min_length=2)
    reference_actor: ActorCompatibilityRecord
    candidate_actor: ActorCompatibilityRecord
    capacity_representation: CapacityRepresentation
    single_intended_difference: str
    seeds: SeedNamespaces
    primary_endpoint: str
    reported_endpoints: tuple[str, ...]
    exact_test_note: str
    minimum_successful_pairs: int = Field(ge=1)
    publishable_null: str = Field(min_length=20)
    wall_clock_ceiling_hours: float = Field(gt=0.0)
    gpu_ceiling_hours: float = Field(gt=0.0)
    stop_rule: str = Field(min_length=10)
    motivating_context: tuple[str, ...] = ()
    evidence_inputs: tuple[str, ...] = ()
    owner_decisions_open: tuple[str, ...]

    @model_validator(mode="after")
    def validate_protocol(self) -> BenchmarkProtocol:
        missing = [
            endpoint
            for endpoint in REQUIRED_ENDPOINT_SET
            if endpoint not in self.reported_endpoints
        ]
        if missing:
            raise ValueError(
                f"PRIMARY_ENDPOINT_MISSING: outcome coherence requires reporting "
                f"{missing} together; latency alone is exactly the trap the confirmed "
                "study exposed"
            )
        if self.primary_endpoint == "task.latency.mean_ms":
            raise ValueError(
                "PRIMARY_ENDPOINT_MISSING: the primary endpoint must test outcome "
                "coherence rather than latency alone"
            )
        budget_reference = self.reference_actor.training_interaction_budget
        if self.candidate_actor.training_interaction_budget != budget_reference:
            raise ValueError(
                "TRAINING_BUDGET_UNMATCHED: the candidate's training budget must "
                "match the reference's"
            )
        expected = (
            self.reference_actor.observation_dimensions
            + self.capacity_representation.added_dimensions
        )
        if self.candidate_actor.observation_dimensions != expected:
            raise ValueError(
                "OBSERVATION_DIMENSION_MISMATCH: the capacity-aware actor must be "
                f"{expected}-dimensional (reference + frozen feature); existing "
                "checkpoints are never silently padded"
            )
        for entry in self.evidence_inputs:
            lowered = entry.lower()
            for marker in _NON_ADMITTED_MARKERS:
                if marker in lowered:
                    raise ValueError(
                        "EXISTING_NON_ADMITTED_REUSE: non-admitted diagnostics may "
                        "motivate protocol choices (motivating_context) but never "
                        "enter as benchmark evidence"
                    )
        if len(self.seeds.evaluation) == 5 and "p=0.0625" not in self.exact_test_note:
            raise ValueError(
                "the exact-test note must state the five-pair sign-test floor "
                "p=0.0625 before execution, not after results"
            )
        return self

    def digest(self) -> str:
        material = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


def check_compatibility(
    reference: ActorCompatibilityRecord, candidate: ActorCompatibilityRecord
) -> Literal["comparable", "INCOMPATIBLE"]:
    """An algorithm name is not a baseline; unmatched rows are never ranked."""

    if (
        candidate.action_support != reference.action_support
        or candidate.reward_contract != reference.reward_contract
        or candidate.training_interaction_budget != reference.training_interaction_budget
    ):
        return "INCOMPATIBLE"
    return "comparable"


# --- the synthetic dry run (gate 1) -----------------------------------------


class PairedSyntheticResult(ProtocolModel):
    seed: int
    reference_value: float
    candidate_value: float


class BenchmarkAnalysis(ProtocolModel):
    """The frozen analysis shape; a null is a complete, publishable outcome."""

    protocol_digest: str
    evaluated_pairs: int = Field(ge=0)
    mean_paired_difference: float | None
    verdict: Literal[
        "DIFFERENCE_IN_PREDECLARED_DIRECTION",
        "PUBLISHABLE_NULL",
        "NOT_EVALUABLE",
    ]
    deviations: tuple[str, ...]
    evidence: Literal[False] = False
    confirmatory: Literal[False] = False
    synthetic_dry_run: bool


def synthetic_dry_run(protocol: BenchmarkProtocol) -> BenchmarkAnalysis:
    """Prove the frozen analysis end to end on tiny non-scientific fixtures.

    The synthetic values are deterministic in the declared dry-run seeds and
    deliberately identical between arms, so the analysis must produce a
    publishable null while retaining an injected deviation — exactly what
    §9 requires the tooling to demonstrate before any compute exists.
    """

    if not protocol.seeds.dry_run:
        raise BenchmarkProtocolError(
            "OWNER_DECISION_MISSING", "no dry-run seed namespace was declared"
        )
    results = [
        PairedSyntheticResult(
            seed=seed,
            reference_value=float(100 + (seed % 7)),
            candidate_value=float(100 + (seed % 7)),
        )
        for seed in protocol.seeds.dry_run
    ]
    return analyse_benchmark(
        protocol,
        tuple(results),
        deviations=("synthetic dry run: one injected deviation retained by design",),
        synthetic=True,
    )


def analyse_benchmark(
    protocol: BenchmarkProtocol,
    results: tuple[PairedSyntheticResult, ...],
    *,
    deviations: tuple[str, ...],
    synthetic: Literal[True],
) -> BenchmarkAnalysis:
    """The frozen analysis: paired differences, verdict, deviations retained."""

    if synthetic is not True:
        raise BenchmarkProtocolError(
            "COMPUTE_AUTHORITY_MISSING",
            "this gate-1 analysis surface accepts synthetic fixtures only",
        )
    seeds = [item.seed for item in results]
    if len(seeds) != len(set(seeds)) or not set(seeds).issubset(protocol.seeds.dry_run):
        raise BenchmarkProtocolError(
            "SEED_NAMESPACE_CONTAMINATED",
            "synthetic results must use unique seeds from the declared dry-run namespace",
        )
    if len(results) < protocol.minimum_successful_pairs:
        return BenchmarkAnalysis(
            protocol_digest=protocol.digest(),
            evaluated_pairs=len(results),
            mean_paired_difference=None,
            verdict="NOT_EVALUABLE",
            deviations=deviations,
            synthetic_dry_run=synthetic,
        )
    differences = [item.candidate_value - item.reference_value for item in results]
    mean_difference = sum(differences) / len(differences)
    all_same_direction = all(d > 0 for d in differences) or all(d < 0 for d in differences)
    verdict: Literal["DIFFERENCE_IN_PREDECLARED_DIRECTION", "PUBLISHABLE_NULL"] = (
        "DIFFERENCE_IN_PREDECLARED_DIRECTION" if all_same_direction else "PUBLISHABLE_NULL"
    )
    return BenchmarkAnalysis(
        protocol_digest=protocol.digest(),
        evaluated_pairs=len(results),
        mean_paired_difference=mean_difference,
        verdict=verdict,
        deviations=deviations,
        synthetic_dry_run=synthetic,
    )


# --- gates 3-4 exist only to refuse here ------------------------------------


def request_execution(
    protocol: BenchmarkProtocol,
    *,
    predeclaration_signed: bool = False,
    compute_authorised: bool = False,
) -> None:
    """Execution is NOT this module's to grant; every path refuses."""

    if protocol.owner_decisions_open:
        raise BenchmarkProtocolError(
            "OWNER_DECISION_MISSING",
            f"open owner decisions remain: {list(protocol.owner_decisions_open)}",
        )
    if not predeclaration_signed:
        raise BenchmarkProtocolError(
            "PREDECLARATION_UNSIGNED",
            "no policy-valid signed predeclaration binds this protocol's digest",
        )
    if not compute_authorised:
        raise BenchmarkProtocolError(
            "COMPUTE_AUTHORITY_MISSING",
            "training/evaluation execution is separately authorised outside this "
            "tooling; there is no submission path here",
        )
    raise BenchmarkProtocolError(
        "COMPUTE_AUTHORITY_MISSING",
        "this tooling has no execution path by design (§6 gates 1-2); a separately "
        "authorised instrument runs the campaign",
    )


def render_predeclaration_draft(protocol: BenchmarkProtocol) -> str:
    """The UNSIGNED draft; the sign-off table is empty by construction."""

    lines = [
        "# Capacity-aware benchmark — Predeclaration (DRAFT — UNSIGNED)",
        "",
        "**No experiment or compute campaign may start from this document. Every owner "
        "decision below must be answered and the FINAL bytes signed first.**",
        "",
        f"Protocol digest (this draft): `{protocol.digest()}`",
        f"Design reference: {protocol.design_reference}",
        f"Citation set: {CITATION_REFERENCE}",
        "",
        "## Single intended difference",
        "",
        protocol.single_intended_difference,
        "",
        "## Endpoints (reported together — outcome coherence, never latency alone)",
        "",
        *[f"- {endpoint}" for endpoint in protocol.reported_endpoints],
        "",
        "## Exact-test resolution, stated before execution",
        "",
        protocol.exact_test_note,
        "",
        "## Publishable null",
        "",
        protocol.publishable_null,
        "",
        "## Open owner decisions",
        "",
        *[f"- {decision}" for decision in protocol.owner_decisions_open],
        "",
        "## Sign-off (EMPTY — a human must complete this)",
        "",
        "| field | value |",
        "|---|---|",
        "| approved_by | |",
        "| approved_role | |",
        "| approved_at_utc | |",
        "| predeclaration_sha256 (of the FINAL bytes) | |",
        "",
    ]
    return "\n".join(lines)
