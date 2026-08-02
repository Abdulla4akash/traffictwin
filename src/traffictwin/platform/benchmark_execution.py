"""Bounded execution packaging for the unsigned Phase-169 benchmark protocol.

The module exports immutable planned jobs and runs only tiny deterministic
engineering-seed fixtures.  It has no actor loader, optimiser, subprocess,
network, scheduler or cloud-provider client.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.platform.benchmark_protocol import (
    ACTION_TRACKS,
    CAPACITY_REPRESENTATIONS,
    EVALUATION_ONLY_ALGORITHMS,
    REQUIRED_ENDPOINT_SET,
    REWARD_TRACKS,
    TRAINING_ALGORITHMS,
    ActionTrack,
    AlgorithmFamily,
    BenchmarkProtocol,
    CapacityRepresentation,
    CapacityRepresentationKind,
    FactorialCell,
    PredeclarationArtifact,
    RewardTrack,
    SignedPredeclaration,
    build_factorial_plan,
    build_owner_selected_protocol,
    construct_capacity_feature,
    request_execution,
)

METHOD_VERSION: Literal["benchmark-execution-package-1.0"] = "benchmark-execution-package-1.0"
PLUGIN_INTERFACE_VERSION: Literal["benchmark-actor-plugin-contract-1.0"] = (
    "benchmark-actor-plugin-contract-1.0"
)
SYNTHETIC_RUNTIME_VERSION: Literal["deterministic-synthetic-worker-1.0"] = (
    "deterministic-synthetic-worker-1.0"
)
SYNTHETIC_STEP_BUDGET: Literal[4] = 4
MAX_SYNTHETIC_ATTEMPTS: Literal[3] = 3

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PRIVATE_MARKERS = (
    "/users/",
    "/home/",
    "\\users\\",
    "password",
    "credential",
    "api_key",
    "token",
    "private permission",
)


class BenchmarkExecutionError(RuntimeError):
    """Typed fail-closed refusal from the execution package."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _has_private_content(value: object) -> bool:
    material = _canonical_bytes(value).decode("utf-8").lower()
    return any(marker in material for marker in _PRIVATE_MARKERS)


class AdapterSuiteManifest(ExecutionModel):
    method_version: Literal["benchmark-adapter-suite-1.0"] = "benchmark-adapter-suite-1.0"
    observation_contract: Literal["base-plus-frozen-capacity-feature"] = (
        "base-plus-frozen-capacity-feature"
    )
    action_contract: Literal["discrete-local-v2i-v2v"] = "discrete-local-v2i-v2v"
    reward_contract: Literal["four-declared-engineering-formulas"] = (
        "four-declared-engineering-formulas"
    )
    capacity_representations: tuple[CapacityRepresentationKind, ...] = CAPACITY_REPRESENTATIONS
    action_tracks: tuple[ActionTrack, ...] = ACTION_TRACKS
    reward_tracks: tuple[RewardTrack, ...] = REWARD_TRACKS
    scientific_validation: Literal[False] = False
    evidence: Literal[False] = False

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class ActorPluginManifest(ExecutionModel):
    method_version: Literal["benchmark-execution-package-1.0"] = METHOD_VERSION
    plugin_interface_version: Literal["benchmark-actor-plugin-contract-1.0"] = (
        PLUGIN_INTERFACE_VERSION
    )
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    family: AlgorithmFamily
    candidate_contract_digest: str = Field(pattern=_SHA256_PATTERN)
    role: Literal["train_and_evaluate", "evaluation_only_control"]
    paradigm: str
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    checkpoint_selection_rule: str
    binding_state: Literal["contract_only"] = "contract_only"
    real_implementation_bound: Literal[False] = False
    checkpoint_present: Literal[False] = False
    scientific_execution_allowed: Literal[False] = False
    arbitrary_import_allowed: Literal[False] = False
    evidence: Literal[False] = False

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class RuntimeManifest(ExecutionModel):
    method_version: Literal["benchmark-execution-package-1.0"] = METHOD_VERSION
    runtime_version: Literal["deterministic-synthetic-worker-1.0"] = SYNTHETIC_RUNTIME_VERSION
    execution_class: Literal["synthetic_dry_run"] = "synthetic_dry_run"
    in_process: Literal[True] = True
    network_allowed: Literal[False] = False
    subprocess_allowed: Literal[False] = False
    arbitrary_code_loading_allowed: Literal[False] = False
    training_allowed: Literal[False] = False
    maximum_steps_per_job: Literal[4] = SYNTHETIC_STEP_BUDGET
    evidence: Literal[False] = False

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class ManifestBundle(ExecutionModel):
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_suite: AdapterSuiteManifest
    runtime: RuntimeManifest
    actors: tuple[ActorPluginManifest, ...]

    @model_validator(mode="after")
    def validate_complete_bundle(self) -> ManifestBundle:
        expected = TRAINING_ALGORITHMS + EVALUATION_ONLY_ALGORITHMS
        if tuple(item.family for item in self.actors) != expected:
            raise ValueError("MANIFEST_FAMILY_MISMATCH")
        if len({item.family for item in self.actors}) != len(expected):
            raise ValueError("MANIFEST_FAMILY_DUPLICATE")
        if any(item.protocol_digest != self.protocol_digest for item in self.actors):
            raise ValueError("PROTOCOL_DIGEST_MISMATCH")
        adapter_digest = self.adapter_suite.digest()
        if any(item.adapter_suite_digest != adapter_digest for item in self.actors):
            raise ValueError("ADAPTER_DIGEST_MISMATCH")
        if _has_private_content(self.model_dump(mode="json")):
            raise ValueError("PRIVATE_CONTENT_DETECTED")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


def build_manifest_bundle(protocol: BenchmarkProtocol) -> ManifestBundle:
    """Build contract-only manifests for all seven declared algorithm families."""

    adapter_suite = AdapterSuiteManifest()
    actors = tuple(
        ActorPluginManifest(
            protocol_digest=protocol.digest(),
            family=contract.family,
            candidate_contract_digest=contract.candidate_contract_digest,
            role=contract.role,
            paradigm=contract.paradigm,
            adapter_suite_digest=adapter_suite.digest(),
            checkpoint_selection_rule=contract.checkpoint_selection_rule,
        )
        for contract in protocol.algorithms
    )
    return ManifestBundle(
        protocol_digest=protocol.digest(),
        adapter_suite=adapter_suite,
        runtime=RuntimeManifest(),
        actors=actors,
    )


class AdaptedObservation(ExecutionModel):
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    representation_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    values: tuple[float, ...]
    base_dimensions: int = Field(ge=1, le=1024)
    capacity_dimensions: int = Field(ge=0, le=1024)
    visible_before_action: bool
    synthetic_contract_check: Literal[True] = True
    evidence: Literal[False] = False


def adapt_observation(
    protocol: BenchmarkProtocol,
    representation: CapacityRepresentation,
    *,
    base_values: tuple[float, ...],
    provisioned_values: tuple[float, ...] = (),
    remaining_values: tuple[float, ...] = (),
    utilisation_values: tuple[float, ...] = (),
    queue_values: tuple[float, ...] = (),
) -> AdaptedObservation:
    """Adapt one finite synthetic observation through the frozen capacity contract."""

    if not base_values or len(base_values) > 1024 or not all(map(math.isfinite, base_values)):
        raise BenchmarkExecutionError(
            "OBSERVATION_INVALID", "base observation must contain bounded finite values"
        )
    protocol_representation = next(
        (item for item in protocol.capacity_representations if item.kind == representation.kind),
        None,
    )
    if (
        protocol_representation is None
        or protocol_representation.digest() != representation.digest()
    ):
        raise BenchmarkExecutionError(
            "OBSERVATION_CONTRACT_MISMATCH", "representation is not the frozen protocol contract"
        )
    capacity = construct_capacity_feature(
        representation,
        provisioned_values=provisioned_values,
        remaining_values=remaining_values,
        utilisation_values=utilisation_values,
        queue_values=queue_values,
    )
    return AdaptedObservation(
        protocol_digest=protocol.digest(),
        representation_digest=representation.digest(),
        adapter_suite_digest=AdapterSuiteManifest().digest(),
        values=base_values + capacity.values,
        base_dimensions=len(base_values),
        capacity_dimensions=len(capacity.values),
        visible_before_action=capacity.visible_before_action,
    )


class AdaptedAction(ExecutionModel):
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    action_track: ActionTrack
    action_index: Literal[0, 1, 2]
    action: Literal["local", "v2i", "v2v"]
    feasibility_checked: bool
    synthetic_contract_check: Literal[True] = True
    evidence: Literal[False] = False


def adapt_action(
    action_track: ActionTrack,
    *,
    action_index: int,
    feasible_actions: tuple[bool, bool, bool],
) -> AdaptedAction:
    """Map the fixed discrete action vocabulary and enforce the declared mask track."""

    if action_track not in ACTION_TRACKS:
        raise BenchmarkExecutionError("ACTION_CONTRACT_MISMATCH", "unknown action track")
    if action_index not in (0, 1, 2):
        raise BenchmarkExecutionError("ACTION_OUT_OF_RANGE", "action index must be 0, 1 or 2")
    if action_track == "local_v2i_v2v_feasibility_masked" and not feasible_actions[action_index]:
        raise BenchmarkExecutionError("ACTION_INFEASIBLE", "masked action is not feasible")
    actions: tuple[Literal["local", "v2i", "v2v"], ...] = ("local", "v2i", "v2v")
    checked = action_track == "local_v2i_v2v_feasibility_masked"
    return AdaptedAction(
        adapter_suite_digest=AdapterSuiteManifest().digest(),
        action_track=action_track,
        action_index=action_index,  # type: ignore[arg-type]
        action=actions[action_index],
        feasibility_checked=checked,
    )


class RewardComponents(ExecutionModel):
    deadline_completion: float = Field(ge=0, le=1)
    latency_penalty: float = Field(ge=0, le=1)
    energy_penalty: float = Field(ge=0, le=1)
    failure_penalty: float = Field(ge=0, le=1)
    fairness_penalty: float = Field(ge=0, le=1)


class AdaptedReward(ExecutionModel):
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    reward_track: RewardTrack
    value: float
    engineering_formula: Literal[True] = True
    literature_validated: Literal[False] = False
    evidence: Literal[False] = False


def adapt_reward(reward_track: RewardTrack, components: RewardComponents) -> AdaptedReward:
    """Exercise all declared reward interfaces with fixed synthetic-only formulas."""

    formulas = {
        "balanced_qos_energy": (
            components.deadline_completion
            - 0.25 * components.latency_penalty
            - 0.25 * components.energy_penalty
        ),
        "pure_qos": components.deadline_completion - components.latency_penalty,
        "outcome_coherent": (
            components.deadline_completion
            - components.failure_penalty
            - 0.1 * components.latency_penalty
        ),
        "fairness_aware": (
            components.deadline_completion
            - components.failure_penalty
            - components.fairness_penalty
        ),
    }
    if reward_track not in formulas:
        raise BenchmarkExecutionError("REWARD_CONTRACT_MISMATCH", "unknown reward track")
    return AdaptedReward(
        adapter_suite_digest=AdapterSuiteManifest().digest(),
        reward_track=reward_track,
        value=formulas[reward_track],
    )


class PlannedTrainingJob(ExecutionModel):
    job_id: str = Field(pattern=_SHA256_PATTERN)
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    factorial_plan_digest: str = Field(pattern=_SHA256_PATTERN)
    cell_id: str
    algorithm: Literal["mappo", "ippo", "qmix", "vdn", "independent_dqn"]
    capacity_representation: CapacityRepresentationKind
    reward_track: RewardTrack
    action_track: ActionTrack
    training_seed: int
    matched_interactions: int = Field(ge=1)
    actor_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    runtime_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    checkpoint_rule: Literal["terminal_checkpoint_primary_25_50_75_100_robustness"] = (
        "terminal_checkpoint_primary_25_50_75_100_robustness"
    )
    scope_status: Literal["proposed_unsigned"] = "proposed_unsigned"
    dispatch_authorised: Literal[False] = False
    evidence: Literal[False] = False

    def identity_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        del payload["job_id"]
        return payload


class PlannedJobPack(ExecutionModel):
    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["benchmark-execution-package-1.0"] = METHOD_VERSION
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    factorial_plan_digest: str = Field(pattern=_SHA256_PATTERN)
    manifest_bundle_digest: str = Field(pattern=_SHA256_PATTERN)
    actor_manifest_digests: tuple[str, ...]
    runtime_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    jobs: tuple[PlannedTrainingJob, ...]
    compatible_training_cells: Literal[240] = 240
    planned_training_jobs: Literal[2400] = 2400
    training_seeds_per_cell: Literal[10] = 10
    training_seed_namespace: tuple[int, ...] = tuple(range(2100, 2110))
    matched_interactions_per_job: Literal[5000000] = 5_000_000
    matched_budget: Literal[True] = True
    scope_status: Literal["proposed_unsigned"] = "proposed_unsigned"
    dispatch_authorised: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_pack_shape(self) -> PlannedJobPack:
        if len(self.jobs) != self.planned_training_jobs:
            raise ValueError("TRAINING_JOB_COUNT_MISMATCH")
        if len({item.job_id for item in self.jobs}) != len(self.jobs):
            raise ValueError("DUPLICATE_JOB_ID")
        cell_ids = {item.cell_id for item in self.jobs}
        expected_cells = {
            f"{algorithm}__{representation}__{reward}__{action}"
            for algorithm in TRAINING_ALGORITHMS
            for representation in CAPACITY_REPRESENTATIONS
            for reward in REWARD_TRACKS
            for action in ACTION_TRACKS
        }
        if cell_ids != expected_cells:
            raise ValueError("FACTORIAL_CELL_COUNT_MISMATCH")
        if self.training_seed_namespace != tuple(range(2100, 2110)):
            raise ValueError("SEED_NAMESPACE_CONTAMINATED")
        if len(self.actor_manifest_digests) != len(TRAINING_ALGORITHMS) or any(
            not re.fullmatch(_SHA256_PATTERN, digest) for digest in self.actor_manifest_digests
        ):
            raise ValueError("ACTOR_MANIFEST_MISMATCH")
        actor_digests = dict(zip(TRAINING_ALGORITHMS, self.actor_manifest_digests, strict=True))
        counts = dict.fromkeys(cell_ids, 0)
        seeds_by_cell: dict[str, set[int]] = {cell_id: set() for cell_id in cell_ids}
        for job in self.jobs:
            counts[job.cell_id] += 1
            seeds_by_cell[job.cell_id].add(job.training_seed)
            if job.protocol_digest != self.protocol_digest:
                raise ValueError("PROTOCOL_DIGEST_MISMATCH")
            if job.factorial_plan_digest != self.factorial_plan_digest:
                raise ValueError("FACTORIAL_PLAN_DIGEST_MISMATCH")
            if _digest(job.identity_payload()) != job.job_id:
                raise ValueError("JOB_DIGEST_MISMATCH")
            expected_cell_id = (
                f"{job.algorithm}__{job.capacity_representation}__"
                f"{job.reward_track}__{job.action_track}"
            )
            if job.cell_id != expected_cell_id:
                raise ValueError("FACTORIAL_CELL_MISMATCH")
            if job.training_seed not in self.training_seed_namespace:
                raise ValueError("SEED_NAMESPACE_CONTAMINATED")
            if job.matched_interactions != self.matched_interactions_per_job:
                raise ValueError("MATCHED_BUDGET_MISMATCH")
            if job.actor_manifest_digest != actor_digests[job.algorithm]:
                raise ValueError("ACTOR_MANIFEST_MISMATCH")
            if (
                job.runtime_manifest_digest != self.runtime_manifest_digest
                or job.adapter_suite_digest != self.adapter_suite_digest
            ):
                raise ValueError("RUNTIME_ADAPTER_MISMATCH")
        if set(counts.values()) != {self.training_seeds_per_cell}:
            raise ValueError("MATCHED_SEED_COUNT_MISMATCH")
        expected_seeds = set(self.training_seed_namespace)
        if any(seeds != expected_seeds for seeds in seeds_by_cell.values()):
            raise ValueError("SEED_NAMESPACE_CONTAMINATED")
        if _has_private_content(self.model_dump(mode="json")):
            raise ValueError("PRIVATE_CONTENT_DETECTED")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


def _plan_digest(cells: tuple[FactorialCell, ...]) -> str:
    return _digest([item.model_dump(mode="json") for item in cells])


def build_planned_job_pack(
    protocol: BenchmarkProtocol, manifests: ManifestBundle | None = None
) -> PlannedJobPack:
    """Expand the exact frozen factorial to 2,400 unsigned, non-dispatching jobs."""

    bundle = manifests or build_manifest_bundle(protocol)
    if bundle.protocol_digest != protocol.digest():
        raise BenchmarkExecutionError("PROTOCOL_DIGEST_MISMATCH", "manifest bundle changed")
    plan = build_factorial_plan(protocol)
    factorial_digest = _plan_digest(plan.cells)
    actor_digests = {actor.family: actor.digest() for actor in bundle.actors}
    jobs: list[PlannedTrainingJob] = []
    for cell in plan.cells:
        for seed in protocol.seeds.training:
            payload: dict[str, object] = {
                "protocol_digest": protocol.digest(),
                "factorial_plan_digest": factorial_digest,
                "cell_id": cell.cell_id,
                "algorithm": cell.algorithm,
                "capacity_representation": cell.capacity_representation,
                "reward_track": cell.reward_track,
                "action_track": cell.action_track,
                "training_seed": seed,
                "matched_interactions": cell.matched_interactions_per_seed,
                "actor_manifest_digest": actor_digests[cell.algorithm],
                "runtime_manifest_digest": bundle.runtime.digest(),
                "adapter_suite_digest": bundle.adapter_suite.digest(),
                "checkpoint_rule": "terminal_checkpoint_primary_25_50_75_100_robustness",
                "scope_status": "proposed_unsigned",
                "dispatch_authorised": False,
                "evidence": False,
            }
            jobs.append(PlannedTrainingJob.model_validate({"job_id": _digest(payload), **payload}))
    return PlannedJobPack(
        protocol_digest=protocol.digest(),
        factorial_plan_digest=factorial_digest,
        manifest_bundle_digest=bundle.digest(),
        actor_manifest_digests=tuple(actor_digests[item] for item in TRAINING_ALGORITHMS),
        runtime_manifest_digest=bundle.runtime.digest(),
        adapter_suite_digest=bundle.adapter_suite.digest(),
        jobs=tuple(jobs),
    )


def render_planned_job_pack(pack: PlannedJobPack) -> bytes:
    """Render canonical NDJSON with a metadata record followed by ordered jobs."""

    header = {
        "record_type": "planned_job_pack",
        "schema_version": pack.schema_version,
        "method_version": pack.method_version,
        "protocol_digest": pack.protocol_digest,
        "factorial_plan_digest": pack.factorial_plan_digest,
        "manifest_bundle_digest": pack.manifest_bundle_digest,
        "actor_manifest_digests": pack.actor_manifest_digests,
        "runtime_manifest_digest": pack.runtime_manifest_digest,
        "adapter_suite_digest": pack.adapter_suite_digest,
        "compatible_training_cells": pack.compatible_training_cells,
        "planned_training_jobs": pack.planned_training_jobs,
        "training_seeds_per_cell": pack.training_seeds_per_cell,
        "training_seed_namespace": pack.training_seed_namespace,
        "matched_interactions_per_job": pack.matched_interactions_per_job,
        "matched_budget": pack.matched_budget,
        "scope_status": pack.scope_status,
        "dispatch_authorised": pack.dispatch_authorised,
        "evidence": pack.evidence,
        "pack_digest": pack.digest(),
    }
    lines = [_canonical_bytes(header)]
    lines.extend(_canonical_bytes(job.model_dump(mode="json")) for job in pack.jobs)
    return b"\n".join(lines) + b"\n"


class CheckpointIdentity(ExecutionModel):
    milestone: Literal["synthetic_terminal", "25", "50", "75", "100"]
    checkpoint_digest: str = Field(pattern=_SHA256_PATTERN)
    selected_from_outcomes: Literal[False] = False
    content_present: Literal[False] = False


class PlannedCheckpointInventory(ExecutionModel):
    job_id: str = Field(pattern=_SHA256_PATTERN)
    checkpoint_digests: tuple[str, ...]
    milestones: tuple[Literal["25", "50", "75", "100"], ...]
    terminal_checkpoint_digest: str = Field(pattern=_SHA256_PATTERN)
    contract_inventory_complete: Literal[True] = True
    selected_from_outcomes: Literal[False] = False
    implementation_verified: Literal[False] = False
    evidence: Literal[False] = False


def validate_planned_checkpoint_inventory(
    job: PlannedTrainingJob, checkpoints: tuple[CheckpointIdentity, ...]
) -> PlannedCheckpointInventory:
    """Validate checkpoint identities against the frozen rule without reading model bytes."""

    if tuple(item.milestone for item in checkpoints) != ("25", "50", "75", "100"):
        raise BenchmarkExecutionError(
            "CHECKPOINT_INVENTORY_MISMATCH", "milestones must be exactly 25/50/75/100"
        )
    if len({item.checkpoint_digest for item in checkpoints}) != 4:
        raise BenchmarkExecutionError(
            "CHECKPOINT_INVENTORY_MISMATCH", "checkpoint identities must be unique"
        )
    if any(item.selected_from_outcomes for item in checkpoints):
        raise BenchmarkExecutionError(
            "CHECKPOINT_SELECTION_LEAKAGE", "outcome-selected checkpoints are forbidden"
        )
    return PlannedCheckpointInventory(
        job_id=job.job_id,
        checkpoint_digests=tuple(item.checkpoint_digest for item in checkpoints),
        milestones=("25", "50", "75", "100"),
        terminal_checkpoint_digest=checkpoints[-1].checkpoint_digest,
    )


class PlannedJobReturn(ExecutionModel):
    job_id: str = Field(pattern=_SHA256_PATTERN)
    planned_job_pack_digest: str = Field(pattern=_SHA256_PATTERN)
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    signed_predeclaration_digest: str = Field(pattern=_SHA256_PATTERN)
    signature_digest: str = Field(pattern=_SHA256_PATTERN)
    actor_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    runtime_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    training_seed: int
    interactions_consumed: int = Field(ge=0)
    endpoint_names: tuple[str, ...]
    checkpoints: tuple[CheckpointIdentity, ...]
    deviations: tuple[str, ...]
    result_digest: str = Field(pattern=_SHA256_PATTERN)
    status: Literal["completed"] = "completed"
    receipt_is_evidence: Literal[False] = False
    admission_created: Literal[False] = False

    def result_identity_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        del payload["result_digest"]
        return payload


class PlannedReturnCompatibility(ExecutionModel):
    job_id: str = Field(pattern=_SHA256_PATTERN)
    result_digest: str = Field(pattern=_SHA256_PATTERN)
    compatible: Literal[True] = True
    receipt_is_evidence: Literal[False] = False
    analysis_started: Literal[False] = False
    admission_created: Literal[False] = False


def validate_planned_job_return(
    protocol: BenchmarkProtocol,
    pack: PlannedJobPack,
    job: PlannedTrainingJob,
    artifact: PredeclarationArtifact,
    signature: SignedPredeclaration,
    returned: PlannedJobReturn,
) -> PlannedReturnCompatibility:
    """Gate a future return against signed scope; never analyse or admit it."""

    request_execution(protocol, artifact=artifact, signature=signature)
    if job not in pack.jobs or pack.protocol_digest != protocol.digest():
        raise BenchmarkExecutionError("JOB_NOT_IN_PACK", "planned job is absent or changed")
    expected = {
        "job_id": job.job_id,
        "planned_job_pack_digest": pack.digest(),
        "protocol_digest": protocol.digest(),
        "signed_predeclaration_digest": artifact.markdown_sha256,
        "signature_digest": signature.signature_digest,
        "actor_manifest_digest": job.actor_manifest_digest,
        "runtime_manifest_digest": job.runtime_manifest_digest,
        "adapter_suite_digest": job.adapter_suite_digest,
        "training_seed": job.training_seed,
        "interactions_consumed": job.matched_interactions,
        "endpoint_names": REQUIRED_ENDPOINT_SET,
    }
    actual = returned.model_dump(mode="python", include=set(expected))
    if actual != expected:
        raise BenchmarkExecutionError(
            "RETURN_CONTRACT_MISMATCH", "return changed identity, budget, seed or endpoints"
        )
    validate_planned_checkpoint_inventory(job, returned.checkpoints)
    if returned.result_digest != _digest(returned.result_identity_payload()):
        raise BenchmarkExecutionError("RESULT_DIGEST_MISMATCH", "planned return changed")
    return PlannedReturnCompatibility(job_id=job.job_id, result_digest=returned.result_digest)


class LocalExportReceipt(ExecutionModel):
    artifact_kind: Literal["planned_job_pack", "resource_plan", "synthetic_receipts"]
    content_sha256: str = Field(pattern=_SHA256_PATTERN)
    bytes_written: int = Field(ge=1)
    record_count: int = Field(ge=1)
    atomic_write: Literal[True] = True
    overwrite: Literal[False] = False
    path_included: Literal[False] = False
    dispatch_created: Literal[False] = False
    evidence: Literal[False] = False


def export_local_artifact(
    output_root: Path,
    filename: str,
    content: bytes,
    *,
    artifact_kind: Literal["planned_job_pack", "resource_plan", "synthetic_receipts"],
    record_count: int,
) -> LocalExportReceipt:
    """Atomically create one explicit local artifact without returning its private path."""

    if not content or record_count < 1:
        raise BenchmarkExecutionError("EXPORT_EMPTY", "artifact content must not be empty")
    if not _SAFE_FILENAME.fullmatch(filename) or Path(filename).name != filename:
        raise BenchmarkExecutionError("EXPORT_PATH_UNSAFE", "filename must be one simple name")
    if output_root.is_symlink() or not output_root.is_dir():
        raise BenchmarkExecutionError("EXPORT_ROOT_UNSAFE", "output root must be a real directory")
    root_stat = output_root.stat()
    if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise BenchmarkExecutionError(
            "EXPORT_PERMISSIONS_UNSAFE", "output root must not be group/other writable"
        )
    target = output_root / filename
    descriptor: int | None = None
    staged: Path | None = None
    try:
        descriptor, staged_name = tempfile.mkstemp(
            prefix=f".{filename}.", suffix=".tmp", dir=output_root
        )
        staged = Path(staged_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(staged, target, follow_symlinks=False)
    except FileExistsError as error:
        raise BenchmarkExecutionError("EXPORT_EXISTS", "destination already exists") from error
    except OSError as error:
        raise BenchmarkExecutionError("EXPORT_FAILED", "atomic local export failed") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if staged is not None:
            staged.unlink(missing_ok=True)
    return LocalExportReceipt(
        artifact_kind=artifact_kind,
        content_sha256=hashlib.sha256(content).hexdigest(),
        bytes_written=len(content),
        record_count=record_count,
    )


def export_planned_job_pack(
    pack: PlannedJobPack, output_root: Path, filename: str
) -> LocalExportReceipt:
    return export_local_artifact(
        output_root,
        filename,
        render_planned_job_pack(pack),
        artifact_kind="planned_job_pack",
        record_count=len(pack.jobs),
    )


class SyntheticDryRunJob(ExecutionModel):
    job_id: str = Field(pattern=_SHA256_PATTERN)
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    manifest_bundle_digest: str = Field(pattern=_SHA256_PATTERN)
    actor_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    runtime_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    algorithm: AlgorithmFamily
    engineering_seed: int
    capacity_representation: CapacityRepresentationKind
    action_track: ActionTrack
    reward_track: RewardTrack
    step_budget: Literal[4] = SYNTHETIC_STEP_BUDGET
    execution_class: Literal["synthetic_dry_run"] = "synthetic_dry_run"
    scientific_campaign: Literal[False] = False
    evidence: Literal[False] = False

    def identity_payload(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        del payload["job_id"]
        return payload


class SyntheticDryRunPack(ExecutionModel):
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    manifest_bundle_digest: str = Field(pattern=_SHA256_PATTERN)
    jobs: tuple[SyntheticDryRunJob, ...]
    job_count: Literal[21] = 21
    execution_class: Literal["synthetic_dry_run"] = "synthetic_dry_run"
    scientific_campaign: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_dry_pack(self) -> SyntheticDryRunPack:
        if len(self.jobs) != self.job_count or len({item.job_id for item in self.jobs}) != len(
            self.jobs
        ):
            raise ValueError("SYNTHETIC_JOB_COUNT_MISMATCH")
        if any(_digest(item.identity_payload()) != item.job_id for item in self.jobs):
            raise ValueError("JOB_DIGEST_MISMATCH")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


def build_synthetic_dry_run_pack(
    protocol: BenchmarkProtocol, manifests: ManifestBundle | None = None
) -> SyntheticDryRunPack:
    """Build 7 families × 3 engineering seeds of tiny contract-only jobs."""

    bundle = manifests or build_manifest_bundle(protocol)
    actor_digests = {actor.family: actor.digest() for actor in bundle.actors}
    algorithms = TRAINING_ALGORITHMS + EVALUATION_ONLY_ALGORITHMS
    jobs: list[SyntheticDryRunJob] = []
    for algorithm_index, algorithm in enumerate(algorithms):
        for seed_index, seed in enumerate(protocol.seeds.engineering):
            payload: dict[str, object] = {
                "protocol_digest": protocol.digest(),
                "manifest_bundle_digest": bundle.digest(),
                "actor_manifest_digest": actor_digests[algorithm],
                "runtime_manifest_digest": bundle.runtime.digest(),
                "adapter_suite_digest": bundle.adapter_suite.digest(),
                "algorithm": algorithm,
                "engineering_seed": seed,
                "capacity_representation": CAPACITY_REPRESENTATIONS[
                    algorithm_index % len(CAPACITY_REPRESENTATIONS)
                ],
                "action_track": ACTION_TRACKS[(algorithm_index + seed_index) % len(ACTION_TRACKS)],
                "reward_track": REWARD_TRACKS[(algorithm_index + seed_index) % len(REWARD_TRACKS)],
                "step_budget": SYNTHETIC_STEP_BUDGET,
                "execution_class": "synthetic_dry_run",
                "scientific_campaign": False,
                "evidence": False,
            }
            jobs.append(SyntheticDryRunJob.model_validate({"job_id": _digest(payload), **payload}))
    return SyntheticDryRunPack(
        protocol_digest=protocol.digest(),
        manifest_bundle_digest=bundle.digest(),
        jobs=tuple(jobs),
    )


class SyntheticMetrics(ExecutionModel):
    equal_weight_task_class_deadline_completion: float = Field(ge=0, le=1)
    mean_latency_ms: float = Field(ge=0)
    mean_energy_j: float = Field(ge=0)
    completion_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    local_action_share: float = Field(ge=0, le=1)
    v2i_action_share: float = Field(ge=0, le=1)
    v2v_action_share: float = Field(ge=0, le=1)
    persistent_minority_failure_share: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_action_shares(self) -> SyntheticMetrics:
        if not math.isclose(
            self.local_action_share + self.v2i_action_share + self.v2v_action_share,
            1.0,
            abs_tol=1e-12,
        ):
            raise ValueError("ACTION_SHARE_MISMATCH")
        return self


class BenchmarkJobReceipt(ExecutionModel):
    job_id: str = Field(pattern=_SHA256_PATTERN)
    dry_run_pack_digest: str = Field(pattern=_SHA256_PATTERN)
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    manifest_bundle_digest: str = Field(pattern=_SHA256_PATTERN)
    actor_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    runtime_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_suite_digest: str = Field(pattern=_SHA256_PATTERN)
    algorithm: AlgorithmFamily
    engineering_seed: int
    step_budget: Literal[4] = SYNTHETIC_STEP_BUDGET
    attempt: int = Field(ge=1, le=MAX_SYNTHETIC_ATTEMPTS)
    status: Literal["completed", "failed", "refused"]
    adapter_trace_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    result_digest: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    metrics: SyntheticMetrics | None = None
    checkpoints: tuple[CheckpointIdentity, ...]
    deviations: tuple[str, ...]
    execution_class: Literal["synthetic_dry_run"] = "synthetic_dry_run"
    scientific_campaign: Literal[False] = False
    evidence: Literal[False] = False
    admission_created: Literal[False] = False

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> BenchmarkJobReceipt:
        if self.status == "completed":
            if (
                self.metrics is None
                or self.adapter_trace_digest is None
                or self.result_digest is None
            ):
                raise ValueError("COMPLETED_RESULT_MISSING")
            if tuple(item.milestone for item in self.checkpoints) != ("synthetic_terminal",):
                raise ValueError("SYNTHETIC_CHECKPOINT_MISMATCH")
        elif (
            self.metrics is not None
            or self.adapter_trace_digest is not None
            or self.result_digest is not None
            or self.checkpoints
        ):
            raise ValueError("FAILED_RESULT_MUST_BE_EMPTY")
        if _has_private_content(self.model_dump(mode="json")):
            raise ValueError("PRIVATE_CONTENT_DETECTED")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


def _capacity_kwargs(representation: CapacityRepresentation) -> dict[str, tuple[float, ...]]:
    count = representation.added_dimensions
    if representation.kind == "capacity_blind":
        return {}
    if representation.kind in {"global_scalar", "per_rsu_vector", "local_observable"}:
        return {"provisioned_values": (1.25,) * count}
    if representation.kind == "provisioned_remaining":
        half = count // 2
        return {
            "provisioned_values": (1.25,) * half,
            "remaining_values": (0.75,) * half,
        }
    return {"utilisation_values": (0.5,), "queue_values": (1.0,)}


def run_synthetic_job(
    protocol: BenchmarkProtocol,
    manifests: ManifestBundle,
    pack: SyntheticDryRunPack,
    job: SyntheticDryRunJob,
    *,
    attempt: int = 1,
) -> BenchmarkJobReceipt:
    """Run a deterministic four-step adapter exercise; never train or load an actor."""

    validate_synthetic_dispatch(protocol, manifests, pack, job, attempt=attempt)
    representation = next(
        item
        for item in protocol.capacity_representations
        if item.kind == job.capacity_representation
    )
    observation = adapt_observation(
        protocol,
        representation,
        base_values=(float(job.engineering_seed % 7), 1.0),
        **_capacity_kwargs(representation),
    )
    selector = int(job.job_id[:8], 16)
    action = adapt_action(
        job.action_track,
        action_index=selector % 3,
        feasible_actions=(True, True, True),
    )
    completion = 0.5 + (job.engineering_seed - protocol.seeds.engineering[0]) * 0.05
    reward = adapt_reward(
        job.reward_track,
        RewardComponents(
            deadline_completion=completion,
            latency_penalty=0.2,
            energy_penalty=0.1,
            failure_penalty=1.0 - completion,
            fairness_penalty=0.1,
        ),
    )
    shares = [0.0, 0.0, 0.0]
    shares[action.action_index] = 1.0
    metrics = SyntheticMetrics(
        equal_weight_task_class_deadline_completion=completion,
        mean_latency_ms=100.0 + float(selector % 10),
        mean_energy_j=1.0 + abs(reward.value) / 10.0,
        completion_count=2,
        failure_count=2,
        local_action_share=shares[0],
        v2i_action_share=shares[1],
        v2v_action_share=shares[2],
        persistent_minority_failure_share=0.25,
    )
    adapter_trace_digest = _digest(
        {
            "observation_digest": _digest(observation.model_dump(mode="json")),
            "action_digest": _digest(action.model_dump(mode="json")),
            "reward_digest": _digest(reward.model_dump(mode="json")),
        }
    )
    result_payload = {
        "job_id": job.job_id,
        "attempt": attempt,
        "adapter_trace_digest": adapter_trace_digest,
        "metrics": metrics.model_dump(mode="json"),
    }
    result_digest = _digest(result_payload)
    checkpoint = CheckpointIdentity(
        milestone="synthetic_terminal",
        checkpoint_digest=_digest(
            {"job_id": job.job_id, "attempt": attempt, "result_digest": result_digest}
        ),
    )
    return BenchmarkJobReceipt(
        job_id=job.job_id,
        dry_run_pack_digest=pack.digest(),
        protocol_digest=protocol.digest(),
        manifest_bundle_digest=manifests.digest(),
        actor_manifest_digest=job.actor_manifest_digest,
        runtime_manifest_digest=job.runtime_manifest_digest,
        adapter_suite_digest=job.adapter_suite_digest,
        algorithm=job.algorithm,
        engineering_seed=job.engineering_seed,
        attempt=attempt,
        status="completed",
        adapter_trace_digest=adapter_trace_digest,
        result_digest=result_digest,
        metrics=metrics,
        checkpoints=(checkpoint,),
        deviations=("deterministic synthetic fixture; no actor or training",),
    )


def run_synthetic_pack(
    protocol: BenchmarkProtocol,
    manifests: ManifestBundle,
    pack: SyntheticDryRunPack,
) -> tuple[BenchmarkJobReceipt, ...]:
    """Run the complete 21-job engineering fixture without scientific execution."""

    return tuple(run_synthetic_job(protocol, manifests, pack, job) for job in pack.jobs)


def render_synthetic_receipts(receipts: tuple[BenchmarkJobReceipt, ...]) -> bytes:
    if not receipts:
        raise BenchmarkExecutionError("EXPORT_EMPTY", "synthetic receipt set must not be empty")
    return (
        b"\n".join(
            _canonical_bytes(receipt.model_dump(mode="json"))
            for receipt in sorted(receipts, key=lambda item: (item.job_id, item.attempt))
        )
        + b"\n"
    )


def validate_synthetic_dispatch(
    protocol: BenchmarkProtocol,
    manifests: ManifestBundle,
    pack: SyntheticDryRunPack,
    job: SyntheticDryRunJob,
    *,
    attempt: int,
) -> None:
    """Recheck scope, identities, seed and budget immediately before local work."""

    if not 1 <= attempt <= MAX_SYNTHETIC_ATTEMPTS:
        raise BenchmarkExecutionError("ATTEMPT_BUDGET_EXCEEDED", "attempt is outside 1..3")
    if protocol.digest() != pack.protocol_digest or protocol.digest() != job.protocol_digest:
        raise BenchmarkExecutionError("PROTOCOL_DIGEST_MISMATCH", "protocol changed")
    if manifests.digest() != pack.manifest_bundle_digest:
        raise BenchmarkExecutionError("MANIFEST_DIGEST_MISMATCH", "manifest bundle changed")
    expected_job = next((item for item in pack.jobs if item.job_id == job.job_id), None)
    if expected_job != job or _digest(job.identity_payload()) != job.job_id:
        raise BenchmarkExecutionError("JOB_DIGEST_MISMATCH", "job is absent or changed")
    actor = next((item for item in manifests.actors if item.family == job.algorithm), None)
    if actor is None or actor.digest() != job.actor_manifest_digest:
        raise BenchmarkExecutionError("ACTOR_MANIFEST_MISMATCH", "actor contract changed")
    if (
        job.runtime_manifest_digest != manifests.runtime.digest()
        or job.adapter_suite_digest != manifests.adapter_suite.digest()
    ):
        raise BenchmarkExecutionError("RUNTIME_ADAPTER_MISMATCH", "runtime or adapter changed")
    if job.engineering_seed not in protocol.seeds.engineering:
        raise BenchmarkExecutionError("SEED_NAMESPACE_CONTAMINATED", "not an engineering seed")
    forbidden = set(protocol.seeds.training + protocol.seeds.tuning + protocol.seeds.evaluation)
    if job.engineering_seed in forbidden:
        raise BenchmarkExecutionError("SEED_NAMESPACE_CONTAMINATED", "seed namespaces overlap")
    if job.step_budget != SYNTHETIC_STEP_BUDGET:
        raise BenchmarkExecutionError("MATCHED_BUDGET_MISMATCH", "synthetic budget changed")


class ReceiptLedger:
    """Process-local idempotency and resume ledger for path-free receipts."""

    def __init__(self) -> None:
        self._receipts: dict[tuple[str, int], BenchmarkJobReceipt] = {}

    @property
    def receipts(self) -> tuple[BenchmarkJobReceipt, ...]:
        return tuple(
            self._receipts[key]
            for key in sorted(self._receipts, key=lambda item: (item[0], item[1]))
        )

    def latest(self, job_id: str) -> BenchmarkJobReceipt | None:
        candidates = [item for item in self._receipts.values() if item.job_id == job_id]
        return max(candidates, key=lambda item: item.attempt, default=None)


class ReceiptIngestion(ExecutionModel):
    job_id: str = Field(pattern=_SHA256_PATTERN)
    attempt: int
    status: Literal["completed", "failed", "refused"]
    receipt_digest: str = Field(pattern=_SHA256_PATTERN)
    idempotent_retry: bool
    evidence: Literal[False] = False


def ingest_receipt(
    protocol: BenchmarkProtocol,
    manifests: ManifestBundle,
    pack: SyntheticDryRunPack,
    receipt: BenchmarkJobReceipt,
    ledger: ReceiptLedger,
) -> ReceiptIngestion:
    """Validate a returned receipt and record an idempotent process-local identity."""

    job = next((item for item in pack.jobs if item.job_id == receipt.job_id), None)
    if job is None:
        raise BenchmarkExecutionError("JOB_NOT_IN_PACK", "receipt job is not declared")
    validate_synthetic_dispatch(protocol, manifests, pack, job, attempt=receipt.attempt)
    expected = {
        "dry_run_pack_digest": pack.digest(),
        "protocol_digest": protocol.digest(),
        "manifest_bundle_digest": manifests.digest(),
        "actor_manifest_digest": job.actor_manifest_digest,
        "runtime_manifest_digest": job.runtime_manifest_digest,
        "adapter_suite_digest": job.adapter_suite_digest,
        "algorithm": job.algorithm,
        "engineering_seed": job.engineering_seed,
        "step_budget": job.step_budget,
    }
    actual = receipt.model_dump(mode="python", include=set(expected))
    if actual != expected:
        raise BenchmarkExecutionError("RETURN_CONTRACT_MISMATCH", "receipt binding changed")
    if receipt.status == "completed":
        assert receipt.metrics is not None
        assert receipt.adapter_trace_digest is not None
        assert receipt.result_digest is not None
        expected_result = _digest(
            {
                "job_id": receipt.job_id,
                "attempt": receipt.attempt,
                "adapter_trace_digest": receipt.adapter_trace_digest,
                "metrics": receipt.metrics.model_dump(mode="json"),
            }
        )
        expected_checkpoint = _digest(
            {
                "job_id": receipt.job_id,
                "attempt": receipt.attempt,
                "result_digest": receipt.result_digest,
            }
        )
        if receipt.result_digest != expected_result:
            raise BenchmarkExecutionError("RESULT_DIGEST_MISMATCH", "returned metrics changed")
        if (
            len(receipt.checkpoints) != 1
            or receipt.checkpoints[0].checkpoint_digest != expected_checkpoint
        ):
            raise BenchmarkExecutionError(
                "CHECKPOINT_DIGEST_MISMATCH", "terminal checkpoint identity changed"
            )
    key = (receipt.job_id, receipt.attempt)
    existing = ledger._receipts.get(key)
    if existing is not None:
        if existing.digest() != receipt.digest():
            raise BenchmarkExecutionError("RECEIPT_MUTATED", "attempt receipt changed")
        return ReceiptIngestion(
            job_id=receipt.job_id,
            attempt=receipt.attempt,
            status=receipt.status,
            receipt_digest=receipt.digest(),
            idempotent_retry=True,
        )
    previous = ledger.latest(receipt.job_id)
    if receipt.attempt == 1:
        if previous is not None:
            raise BenchmarkExecutionError("ATTEMPT_SEQUENCE_INVALID", "attempt one already exists")
    elif (
        previous is None
        or receipt.attempt != previous.attempt + 1
        or previous.status == "completed"
    ):
        raise BenchmarkExecutionError(
            "ATTEMPT_SEQUENCE_INVALID", "retry must follow a failed/refused prior attempt"
        )
    ledger._receipts[key] = receipt
    return ReceiptIngestion(
        job_id=receipt.job_id,
        attempt=receipt.attempt,
        status=receipt.status,
        receipt_digest=receipt.digest(),
        idempotent_retry=False,
    )


class ResumePlan(ExecutionModel):
    dry_run_pack_digest: str = Field(pattern=_SHA256_PATTERN)
    completed_job_ids: tuple[str, ...]
    pending_job_ids: tuple[str, ...]
    retryable_job_ids: tuple[str, ...]
    exhausted_job_ids: tuple[str, ...]
    dispatch_started: Literal[False] = False
    evidence: Literal[False] = False


def build_resume_plan(pack: SyntheticDryRunPack, ledger: ReceiptLedger) -> ResumePlan:
    completed: list[str] = []
    pending: list[str] = []
    retryable: list[str] = []
    exhausted: list[str] = []
    for job in pack.jobs:
        latest = ledger.latest(job.job_id)
        if latest is None:
            pending.append(job.job_id)
        elif latest.status == "completed":
            completed.append(job.job_id)
        elif latest.attempt < MAX_SYNTHETIC_ATTEMPTS:
            retryable.append(job.job_id)
        else:
            exhausted.append(job.job_id)
    return ResumePlan(
        dry_run_pack_digest=pack.digest(),
        completed_job_ids=tuple(sorted(completed)),
        pending_job_ids=tuple(sorted(pending)),
        retryable_job_ids=tuple(sorted(retryable)),
        exhausted_job_ids=tuple(sorted(exhausted)),
    )


class CheckpointInventory(ExecutionModel):
    dry_run_pack_digest: str = Field(pattern=_SHA256_PATTERN)
    completed_jobs: int = Field(ge=0)
    synthetic_terminal_checkpoints: int = Field(ge=0)
    checkpoint_digests: tuple[str, ...]
    terminal_primary: Literal[True] = True
    scientific_checkpoint_inventory_complete: Literal[False] = False
    evidence: Literal[False] = False


def inventory_checkpoints(pack: SyntheticDryRunPack, ledger: ReceiptLedger) -> CheckpointInventory:
    completed = [item for item in ledger.receipts if item.status == "completed"]
    latest_completed = {
        item.job_id: item for item in completed if ledger.latest(item.job_id) == item
    }
    if any(
        tuple(checkpoint.milestone for checkpoint in item.checkpoints) != ("synthetic_terminal",)
        for item in latest_completed.values()
    ):
        raise BenchmarkExecutionError(
            "CHECKPOINT_INVENTORY_MISMATCH", "synthetic receipts require one terminal identity"
        )
    digests = tuple(
        sorted(item.checkpoints[0].checkpoint_digest for item in latest_completed.values())
    )
    return CheckpointInventory(
        dry_run_pack_digest=pack.digest(),
        completed_jobs=len(latest_completed),
        synthetic_terminal_checkpoints=len(digests),
        checkpoint_digests=digests,
    )


class ProviderNeutralResourcePlan(ExecutionModel):
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    planned_job_pack_digest: str = Field(pattern=_SHA256_PATTERN)
    planned_training_jobs: Literal[2400] = 2400
    total_training_interactions: Literal[12000000000] = 12_000_000_000
    provider_labels: tuple[Literal["gcp_batch", "aws_batch"], ...] = (
        "gcp_batch",
        "aws_batch",
    )
    accelerator_labels: tuple[Literal["l4", "a100", "h100"], ...] = ("l4", "a100", "h100")
    maximum_gpu_hours_estimate: float = 5000.0
    maximum_cost_gbp_estimate: float = 5000.0
    calibration_cost_gbp_estimate: float = 250.0
    pilot_cost_gbp_estimate: float = 750.0
    estimate_only: Literal[True] = True
    authority: Literal[False] = False
    allocation_created: Literal[False] = False
    submission_created: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_frozen_estimates(self) -> ProviderNeutralResourcePlan:
        if (
            self.maximum_gpu_hours_estimate,
            self.maximum_cost_gbp_estimate,
            self.calibration_cost_gbp_estimate,
            self.pilot_cost_gbp_estimate,
        ) != (5000.0, 5000.0, 250.0, 750.0):
            raise ValueError("RESOURCE_BUDGET_MISMATCH")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


def build_resource_plan(
    protocol: BenchmarkProtocol, pack: PlannedJobPack
) -> ProviderNeutralResourcePlan:
    if pack.protocol_digest != protocol.digest():
        raise BenchmarkExecutionError("PROTOCOL_DIGEST_MISMATCH", "job pack changed")
    if (
        protocol.compute.maximum_gpu_hours_estimate != 5000.0
        or protocol.compute.maximum_cost_gbp_estimate != 5000.0
    ):
        raise BenchmarkExecutionError("RESOURCE_BUDGET_MISMATCH", "frozen estimates changed")
    return ProviderNeutralResourcePlan(
        protocol_digest=protocol.digest(), planned_job_pack_digest=pack.digest()
    )


def render_resource_plan(plan: ProviderNeutralResourcePlan) -> bytes:
    return _canonical_bytes(plan.model_dump(mode="json")) + b"\n"


class SyntheticAnalysisInputFreeze(ExecutionModel):
    protocol_digest: str = Field(pattern=_SHA256_PATTERN)
    dry_run_pack_digest: str = Field(pattern=_SHA256_PATTERN)
    manifest_bundle_digest: str = Field(pattern=_SHA256_PATTERN)
    receipt_digests: tuple[str, ...]
    result_digests: tuple[str, ...]
    checkpoint_digests: tuple[str, ...]
    deviations: tuple[str, ...]
    analysis_input_digest: str = Field(pattern=_SHA256_PATTERN)
    complete_jobs: Literal[21] = 21
    synthetic_dry_run: Literal[True] = True
    confirmatory: Literal[False] = False
    evidence: Literal[False] = False
    admission_created: Literal[False] = False


def freeze_synthetic_analysis_inputs(
    protocol: BenchmarkProtocol,
    manifests: ManifestBundle,
    pack: SyntheticDryRunPack,
    ledger: ReceiptLedger,
) -> SyntheticAnalysisInputFreeze:
    """Freeze only a complete compatible synthetic receipt set; create no analysis/evidence."""

    resume = build_resume_plan(pack, ledger)
    if resume.pending_job_ids or resume.retryable_job_ids or resume.exhausted_job_ids:
        raise BenchmarkExecutionError(
            "ANALYSIS_INPUT_INCOMPLETE", "dry-run receipts are incomplete"
        )
    all_receipts = ledger.receipts
    receipts = tuple(
        sorted(
            (latest for job in pack.jobs if (latest := ledger.latest(job.job_id)) is not None),
            key=lambda item: item.job_id,
        )
    )
    if len(receipts) != len(pack.jobs) or any(item.status != "completed" for item in receipts):
        raise BenchmarkExecutionError("ANALYSIS_INPUT_INCOMPATIBLE", "receipt set is not complete")
    for receipt in receipts:
        job = next(item for item in pack.jobs if item.job_id == receipt.job_id)
        validate_synthetic_dispatch(protocol, manifests, pack, job, attempt=receipt.attempt)
        expected = ledger.latest(receipt.job_id)
        if expected != receipt or receipt.result_digest is None:
            raise BenchmarkExecutionError("ANALYSIS_INPUT_INCOMPATIBLE", "receipt lineage changed")
    checkpoint_inventory = inventory_checkpoints(pack, ledger)
    receipt_digests = tuple(item.digest() for item in all_receipts)
    result_digests = tuple(
        item.result_digest for item in receipts if item.result_digest is not None
    )
    deviations = tuple(
        sorted({deviation for item in all_receipts for deviation in item.deviations})
    )
    material = {
        "protocol_digest": protocol.digest(),
        "dry_run_pack_digest": pack.digest(),
        "manifest_bundle_digest": manifests.digest(),
        "receipt_digests": receipt_digests,
        "result_digests": result_digests,
        "checkpoint_digests": checkpoint_inventory.checkpoint_digests,
        "deviations": deviations,
        "synthetic_dry_run": True,
        "confirmatory": False,
        "evidence": False,
    }
    return SyntheticAnalysisInputFreeze(
        protocol_digest=protocol.digest(),
        dry_run_pack_digest=pack.digest(),
        manifest_bundle_digest=manifests.digest(),
        receipt_digests=receipt_digests,
        result_digests=result_digests,
        checkpoint_digests=checkpoint_inventory.checkpoint_digests,
        deviations=deviations,
        analysis_input_digest=_digest(material),
    )


def build_default_execution_package() -> tuple[
    BenchmarkProtocol, ManifestBundle, PlannedJobPack, SyntheticDryRunPack
]:
    """Convenience constructor for deterministic export/inspection tools."""

    protocol = build_owner_selected_protocol()
    manifests = build_manifest_bundle(protocol)
    return (
        protocol,
        manifests,
        build_planned_job_pack(protocol, manifests),
        build_synthetic_dry_run_pack(protocol, manifests),
    )
