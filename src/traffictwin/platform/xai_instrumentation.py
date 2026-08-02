"""Fenced decision-audit and attribution-shaped synthetic instrumentation.

This module contains pure contracts and deterministic fixtures.  It does not
load an actor or checkpoint, invoke an XAI library, execute a simulator, or
create scientific evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

METHOD_VERSION: Literal["xai-instrumentation-1.0"] = "xai-instrumentation-1.0"
ActionName = Literal["local", "v2i", "v2v"]
SourceRole = Literal[
    "project_context", "method_reference", "synthetic_fixture", "unavailable_requirement"
]
AttributionMethod = Literal[
    "shap_shaped_synthetic_fixture", "integrated_gradients_shaped_synthetic_fixture"
]
MissingAttributionRequirement = Literal[
    "producer_snapshot_hook", "authorised_model_access", "validated_application_method"
]

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_PRIVATE_MARKERS = (
    "/users/",
    "/home/",
    "\\users\\",
    "password",
    "credential",
    "api_key",
    "private permission",
    "participant_id",
    "vehicle_id",
    "task_id",
    "trip_id",
)
_UNSUPPORTED_CLAIM_PHRASES: dict[str, str] = {
    "caused the action": "CAUSAL_SUPPORT_MISSING",
    "causal effect": "CAUSAL_SUPPORT_MISSING",
    "proves that": "PROOF_SUPPORT_MISSING",
    "proof that": "PROOF_SUPPORT_MISSING",
    "faithfully explains": "FAITHFULNESS_SUPPORT_MISSING",
    "faithful explanation": "FAITHFULNESS_SUPPORT_MISSING",
    "validated explanation": "VALIDATION_SUPPORT_MISSING",
    "globally optimal": "OPTIMALITY_SUPPORT_MISSING",
    "the optimal action": "OPTIMALITY_SUPPORT_MISSING",
    "the best action": "OPTIMALITY_SUPPORT_MISSING",
    "the safest action": "SAFETY_SUPPORT_MISSING",
    "solves the problem": "SOLUTION_SUPPORT_MISSING",
    "guarantees the outcome": "GUARANTEE_SUPPORT_MISSING",
}


class XaiInstrumentationError(RuntimeError):
    """Typed fail-closed XAI instrumentation refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class XaiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        allow_inf_nan=False,
        revalidate_instances="always",
    )


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


class ExplanationClaimSupport(XaiModel):
    causal: Literal[False] = False
    proof: Literal[False] = False
    faithfulness_validated: Literal[False] = False
    application_validated: Literal[False] = False
    optimality_supported: Literal[False] = False
    safety_supported: Literal[False] = False
    solution_supported: Literal[False] = False
    guarantee_supported: Literal[False] = False


def validate_explanation_language(
    text: str, support: ExplanationClaimSupport | None = None
) -> None:
    """Reject common positive overclaims unless their exact support flag exists."""

    normalised = " ".join(text.lower().split())
    permitted = support or ExplanationClaimSupport()
    gates = {
        "CAUSAL_SUPPORT_MISSING": permitted.causal,
        "PROOF_SUPPORT_MISSING": permitted.proof,
        "FAITHFULNESS_SUPPORT_MISSING": permitted.faithfulness_validated,
        "VALIDATION_SUPPORT_MISSING": permitted.application_validated,
        "OPTIMALITY_SUPPORT_MISSING": permitted.optimality_supported,
        "SAFETY_SUPPORT_MISSING": permitted.safety_supported,
        "SOLUTION_SUPPORT_MISSING": permitted.solution_supported,
        "GUARANTEE_SUPPORT_MISSING": permitted.guarantee_supported,
    }
    for phrase, code in _UNSUPPORTED_CLAIM_PHRASES.items():
        if phrase in normalised and not gates[code]:
            raise XaiInstrumentationError(code, "claim exceeds the declared support contract")


OBSERVATION_CONTRACT_DIGEST = _digest(
    {
        "features": ("declared_load", "queue_fraction", "deadline_pressure"),
        "timing": "visible_before_action_same_tick",
        "scope": "synthetic_aggregate_only",
    }
)
ACTION_VOCABULARY_DIGEST = _digest(("local", "v2i", "v2v"))
SYNTHETIC_ACTOR_CONTRACT_DIGEST = _digest(
    {"actor": "synthetic_policy_fixture", "observation": OBSERVATION_CONTRACT_DIGEST}
)
SYNTHETIC_CHECKPOINT_DIGEST = _digest(
    {"checkpoint": "synthetic_contract_marker", "contains_model_parameters": False}
)


class SourceSupport(XaiModel):
    support_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,63}$")
    role: SourceRole
    source_ref: str = Field(min_length=3, max_length=200)
    source_digest: str = Field(pattern=_SHA256_PATTERN)
    binding_kind: Literal["exact_repository_bytes", "citation_metadata_only", "contract_record"]
    support_scope: str = Field(min_length=10, max_length=400)
    limitation: str = Field(min_length=10, max_length=400)
    evidence: bool
    llm_output: Literal[False] = False

    @model_validator(mode="after")
    def validate_content(self) -> SourceSupport:
        if _has_private_content(self.model_dump(mode="json")):
            raise ValueError("PRIVATE_CONTENT_DETECTED")
        validate_explanation_language(f"{self.support_scope} {self.limitation}")
        if self.role in {"synthetic_fixture", "unavailable_requirement"} and self.evidence:
            raise ValueError("SYNTHETIC_OR_MISSING_INPUT_IS_NOT_EVIDENCE")
        return self


class SnapshotFeature(XaiModel):
    name: Literal["declared_load", "queue_fraction", "deadline_pressure"]
    value: float = Field(ge=0, le=1)
    units: Literal["normalised_fraction"] = "normalised_fraction"
    visible_before_action: Literal[True] = True


class DecisionTimeSnapshot(XaiModel):
    snapshot_id: str = Field(pattern=r"^synthetic-snapshot-[0-9]{3}$")
    source_artifact_digest: str = Field(pattern=_SHA256_PATTERN)
    source_record_digest: str = Field(pattern=_SHA256_PATTERN)
    actor_id: Literal["synthetic_policy_fixture"] = "synthetic_policy_fixture"
    actor_contract_digest: str = Field(pattern=_SHA256_PATTERN)
    checkpoint_digest: str = Field(pattern=_SHA256_PATTERN)
    observation_contract_digest: str = Field(pattern=_SHA256_PATTERN)
    action_vocabulary_digest: str = Field(pattern=_SHA256_PATTERN)
    simulation_step: int = Field(ge=0)
    features: tuple[SnapshotFeature, ...]
    recorded_action: ActionName
    source_support_ids: tuple[str, ...]
    producer_snapshot_hook: Literal["synthetic_fixture_only"] = "synthetic_fixture_only"
    synthetic_fixture: Literal[True] = True
    real_actor: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_snapshot_contract(self) -> DecisionTimeSnapshot:
        if tuple(feature.name for feature in self.features) != (
            "declared_load",
            "queue_fraction",
            "deadline_pressure",
        ):
            raise ValueError("OBSERVATION_CONTRACT_MISMATCH")
        if self.observation_contract_digest != OBSERVATION_CONTRACT_DIGEST:
            raise ValueError("OBSERVATION_CONTRACT_MISMATCH")
        if self.action_vocabulary_digest != ACTION_VOCABULARY_DIGEST:
            raise ValueError("ACTION_CONTRACT_MISMATCH")
        if self.actor_contract_digest != SYNTHETIC_ACTOR_CONTRACT_DIGEST:
            raise ValueError("ACTOR_CONTRACT_MISMATCH")
        if self.checkpoint_digest != SYNTHETIC_CHECKPOINT_DIGEST:
            raise ValueError("CHECKPOINT_DIGEST_MISMATCH")
        if len(set(self.source_support_ids)) != len(self.source_support_ids):
            raise ValueError("SOURCE_SUPPORT_DUPLICATE")
        if _has_private_content(self.model_dump(mode="json")):
            raise ValueError("PRIVATE_CONTENT_DETECTED")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))

    def feature_value(self, name: str) -> float:
        feature = next((item for item in self.features if item.name == name), None)
        if feature is None:
            raise XaiInstrumentationError("FEATURE_UNAVAILABLE", "snapshot feature is absent")
        return feature.value


class ReplayAdapterManifest(XaiModel):
    adapter_id: Literal["always_local", "lyapunov_queue_aware"]
    method_version: Literal["xai-replay-adapter-1.0"] = "xai-replay-adapter-1.0"
    observation_contract_digest: str = Field(pattern=_SHA256_PATTERN)
    action_vocabulary_digest: str = Field(pattern=_SHA256_PATTERN)
    decision_rule: str = Field(min_length=10, max_length=300)
    real_policy: Literal[False] = False
    claims_optimality: Literal[False] = False
    evidence: Literal[False] = False

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class CounterfactualReplayResult(XaiModel):
    replay_id: str = Field(pattern=_SHA256_PATTERN)
    snapshot_id: str
    snapshot_digest: str = Field(pattern=_SHA256_PATTERN)
    adapter_id: Literal["always_local", "lyapunov_queue_aware"]
    adapter_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    replay_action: ActionName
    input_digest: str = Field(pattern=_SHA256_PATTERN)
    output_digest: str = Field(pattern=_SHA256_PATTERN)
    mutates_snapshot: Literal[False] = False
    counterfactual_claim: Literal["engineering_baseline_replay_only"] = (
        "engineering_baseline_replay_only"
    )
    causal: Literal[False] = False
    optimality_supported: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_result_identity(self) -> CounterfactualReplayResult:
        if self.output_digest != _digest(
            {"input_digest": self.input_digest, "action": self.replay_action}
        ):
            raise ValueError("REPLAY_OUTPUT_DIGEST_MISMATCH")
        if self.replay_id != _digest(
            {
                "snapshot_id": self.snapshot_id,
                "adapter_id": self.adapter_id,
                "output": self.replay_action,
            }
        ):
            raise ValueError("REPLAY_ID_MISMATCH")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class CounterfactualReplayAdapter(Protocol):
    @property
    def manifest(self) -> ReplayAdapterManifest: ...

    def replay(self, snapshot: DecisionTimeSnapshot) -> CounterfactualReplayResult: ...


def _replay_result(
    snapshot: DecisionTimeSnapshot, manifest: ReplayAdapterManifest, action: ActionName
) -> CounterfactualReplayResult:
    input_digest = _digest(
        {
            "snapshot_digest": snapshot.digest(),
            "adapter_manifest_digest": manifest.digest(),
        }
    )
    output_digest = _digest({"input_digest": input_digest, "action": action})
    replay_id = _digest(
        {"snapshot_id": snapshot.snapshot_id, "adapter_id": manifest.adapter_id, "output": action}
    )
    return CounterfactualReplayResult(
        replay_id=replay_id,
        snapshot_id=snapshot.snapshot_id,
        snapshot_digest=snapshot.digest(),
        adapter_id=manifest.adapter_id,
        adapter_manifest_digest=manifest.digest(),
        replay_action=action,
        input_digest=input_digest,
        output_digest=output_digest,
    )


class AlwaysLocalReplay:
    def __init__(self) -> None:
        self._manifest = ReplayAdapterManifest(
            adapter_id="always_local",
            observation_contract_digest=OBSERVATION_CONTRACT_DIGEST,
            action_vocabulary_digest=ACTION_VOCABULARY_DIGEST,
            decision_rule="Return local for every compatible synthetic snapshot.",
        )

    @property
    def manifest(self) -> ReplayAdapterManifest:
        return self._manifest

    def replay(self, snapshot: DecisionTimeSnapshot) -> CounterfactualReplayResult:
        return _replay_result(snapshot, self.manifest, "local")


class LyapunovQueueAwareReplay:
    def __init__(self) -> None:
        self._manifest = ReplayAdapterManifest(
            adapter_id="lyapunov_queue_aware",
            observation_contract_digest=OBSERVATION_CONTRACT_DIGEST,
            action_vocabulary_digest=ACTION_VOCABULARY_DIGEST,
            decision_rule=(
                "Synthetic fixed rule: high queue/load uses V2V, medium load uses V2I, otherwise "
                "local; deadline pressure above 0.85 uses local."
            ),
        )

    @property
    def manifest(self) -> ReplayAdapterManifest:
        return self._manifest

    def replay(self, snapshot: DecisionTimeSnapshot) -> CounterfactualReplayResult:
        load = snapshot.feature_value("declared_load")
        queue = snapshot.feature_value("queue_fraction")
        deadline = snapshot.feature_value("deadline_pressure")
        if deadline > 0.85:
            action: ActionName = "local"
        elif queue >= 0.7 or load >= 0.75:
            action = "v2v"
        elif load >= 0.4:
            action = "v2i"
        else:
            action = "local"
        return _replay_result(snapshot, self.manifest, action)


def replay_counterfactuals(
    snapshots: tuple[DecisionTimeSnapshot, ...],
    adapters: tuple[CounterfactualReplayAdapter, ...],
) -> tuple[CounterfactualReplayResult, ...]:
    if not snapshots or not adapters:
        raise XaiInstrumentationError("REPLAY_INPUT_EMPTY", "snapshots and adapters are required")
    before = tuple(snapshot.digest() for snapshot in snapshots)
    results = tuple(adapter.replay(snapshot) for snapshot in snapshots for adapter in adapters)
    after = tuple(snapshot.digest() for snapshot in snapshots)
    if before != after:
        raise XaiInstrumentationError("SNAPSHOT_MUTATED", "replay changed its input snapshot")
    return results


class PolicyDisagreementRow(XaiModel):
    row_id: str = Field(pattern=_SHA256_PATTERN)
    snapshot_id: str
    snapshot_digest: str = Field(pattern=_SHA256_PATTERN)
    recorded_actor_id: Literal["synthetic_policy_fixture"] = "synthetic_policy_fixture"
    recorded_checkpoint_digest: str = Field(pattern=_SHA256_PATTERN)
    recorded_action: ActionName
    replay_adapter_id: Literal["always_local", "lyapunov_queue_aware"]
    replay_manifest_digest: str = Field(pattern=_SHA256_PATTERN)
    replay_action: ActionName
    disagreement: bool
    interpretation: Literal["descriptive_action_difference_only"] = (
        "descriptive_action_difference_only"
    )
    correct_action_identified: Literal[False] = False
    causal: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_row_identity(self) -> PolicyDisagreementRow:
        payload = self.model_dump(mode="json")
        del payload["row_id"]
        if self.row_id != _digest(payload):
            raise ValueError("DISAGREEMENT_DIGEST_MISMATCH")
        if self.disagreement != (self.recorded_action != self.replay_action):
            raise ValueError("DISAGREEMENT_VALUE_MISMATCH")
        return self


def build_disagreement_rows(
    snapshots: tuple[DecisionTimeSnapshot, ...],
    replays: tuple[CounterfactualReplayResult, ...],
) -> tuple[PolicyDisagreementRow, ...]:
    snapshot_by_id = {item.snapshot_id: item for item in snapshots}
    if len(snapshot_by_id) != len(snapshots):
        raise XaiInstrumentationError("SNAPSHOT_DUPLICATE", "snapshot ids must be unique")
    rows: list[PolicyDisagreementRow] = []
    for replay in replays:
        snapshot = snapshot_by_id.get(replay.snapshot_id)
        if snapshot is None or replay.snapshot_digest != snapshot.digest():
            raise XaiInstrumentationError("REPLAY_BINDING_MISMATCH", "replay snapshot changed")
        payload = {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_digest": snapshot.digest(),
            "recorded_actor_id": snapshot.actor_id,
            "recorded_checkpoint_digest": snapshot.checkpoint_digest,
            "recorded_action": snapshot.recorded_action,
            "replay_adapter_id": replay.adapter_id,
            "replay_manifest_digest": replay.adapter_manifest_digest,
            "replay_action": replay.replay_action,
            "disagreement": snapshot.recorded_action != replay.replay_action,
            "interpretation": "descriptive_action_difference_only",
            "correct_action_identified": False,
            "causal": False,
            "evidence": False,
        }
        rows.append(PolicyDisagreementRow.model_validate({"row_id": _digest(payload), **payload}))
    return tuple(rows)


class DisagreementBrowserResult(XaiModel):
    rows: tuple[PolicyDisagreementRow, ...]
    total_rows: int = Field(ge=0)
    disagreement_rows: int = Field(ge=0)
    filters_applied: tuple[str, ...]
    changes_standing: Literal[False] = False
    evidence: Literal[False] = False


def browse_disagreements(
    rows: tuple[PolicyDisagreementRow, ...],
    *,
    disagreement_only: bool = False,
    recorded_action: ActionName | Literal["all"] = "all",
) -> DisagreementBrowserResult:
    selected = rows
    filters: list[str] = []
    if disagreement_only:
        selected = tuple(item for item in selected if item.disagreement)
        filters.append("disagreement_only")
    if recorded_action != "all":
        selected = tuple(item for item in selected if item.recorded_action == recorded_action)
        filters.append(f"recorded_action={recorded_action}")
    return DisagreementBrowserResult(
        rows=selected,
        total_rows=len(selected),
        disagreement_rows=sum(item.disagreement for item in selected),
        filters_applied=tuple(filters),
    )


class PolicyDecision(XaiModel):
    policy_id: Literal["synthetic_policy_fixture", "always_local", "lyapunov_queue_aware"]
    snapshot_id: str
    snapshot_digest: str = Field(pattern=_SHA256_PATTERN)
    declared_load: float = Field(ge=0, le=1)
    action: ActionName
    decision_digest: str = Field(pattern=_SHA256_PATTERN)


class FingerprintBin(XaiModel):
    label: Literal["low", "medium", "high"]
    lower_inclusive: float = Field(ge=0, le=1)
    upper_exclusive: float = Field(gt=0, le=1.01)
    support: int = Field(ge=0)
    local_share: float | None = Field(default=None, ge=0, le=1)
    v2i_share: float | None = Field(default=None, ge=0, le=1)
    v2v_share: float | None = Field(default=None, ge=0, le=1)
    availability: Literal["available", "unavailable_no_support"]

    @model_validator(mode="after")
    def validate_reconciliation(self) -> FingerprintBin:
        shares = (self.local_share, self.v2i_share, self.v2v_share)
        if self.support == 0:
            if self.availability != "unavailable_no_support" or any(
                item is not None for item in shares
            ):
                raise ValueError("EMPTY_BIN_MUST_BE_UNAVAILABLE")
        elif (
            self.availability != "available"
            or any(item is None for item in shares)
            or not math.isclose(sum(item for item in shares if item is not None), 1.0)
        ):
            raise ValueError("FINGERPRINT_SHARE_MISMATCH")
        return self


class BehaviouralFingerprint(XaiModel):
    policy_id: Literal["synthetic_policy_fixture", "always_local", "lyapunov_queue_aware"]
    decision_set_digest: str = Field(pattern=_SHA256_PATTERN)
    bins: tuple[FingerprintBin, ...]
    total_support: int = Field(ge=0)
    interpretation: Literal["descriptive_action_share_by_declared_load"] = (
        "descriptive_action_share_by_declared_load"
    )
    generalisation_supported: Literal[False] = False
    causal: Literal[False] = False
    evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_bins(self) -> BehaviouralFingerprint:
        if tuple(item.label for item in self.bins) != ("low", "medium", "high"):
            raise ValueError("FINGERPRINT_BIN_MISMATCH")
        if sum(item.support for item in self.bins) != self.total_support:
            raise ValueError("FINGERPRINT_SUPPORT_MISMATCH")
        return self


def build_policy_decisions(
    snapshots: tuple[DecisionTimeSnapshot, ...],
    replays: tuple[CounterfactualReplayResult, ...],
) -> tuple[PolicyDecision, ...]:
    decisions: list[PolicyDecision] = []
    snapshot_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    for snapshot in snapshots:
        payload = {
            "policy_id": snapshot.actor_id,
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_digest": snapshot.digest(),
            "declared_load": snapshot.feature_value("declared_load"),
            "action": snapshot.recorded_action,
        }
        decisions.append(
            PolicyDecision.model_validate({"decision_digest": _digest(payload), **payload})
        )
    for replay in replays:
        snapshot = snapshot_by_id[replay.snapshot_id]
        payload = {
            "policy_id": replay.adapter_id,
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_digest": snapshot.digest(),
            "declared_load": snapshot.feature_value("declared_load"),
            "action": replay.replay_action,
        }
        decisions.append(
            PolicyDecision.model_validate({"decision_digest": _digest(payload), **payload})
        )
    return tuple(decisions)


def _fingerprint_bin(
    label: Literal["low", "medium", "high"],
    lower: float,
    upper: float,
    decisions: tuple[PolicyDecision, ...],
) -> FingerprintBin:
    selected = tuple(item for item in decisions if lower <= item.declared_load < upper)
    if not selected:
        return FingerprintBin(
            label=label,
            lower_inclusive=lower,
            upper_exclusive=upper,
            support=0,
            availability="unavailable_no_support",
        )
    counts = {
        action: sum(item.action == action for item in selected)
        for action in ("local", "v2i", "v2v")
    }
    support = len(selected)
    return FingerprintBin(
        label=label,
        lower_inclusive=lower,
        upper_exclusive=upper,
        support=support,
        local_share=counts["local"] / support,
        v2i_share=counts["v2i"] / support,
        v2v_share=counts["v2v"] / support,
        availability="available",
    )


def build_behavioural_fingerprints(
    decisions: tuple[PolicyDecision, ...],
) -> tuple[BehaviouralFingerprint, ...]:
    grouped: dict[str, list[PolicyDecision]] = defaultdict(list)
    for decision in decisions:
        grouped[decision.policy_id].append(decision)
    fingerprints: list[BehaviouralFingerprint] = []
    for policy_id in ("synthetic_policy_fixture", "always_local", "lyapunov_queue_aware"):
        policy_decisions = tuple(sorted(grouped[policy_id], key=lambda item: item.snapshot_id))
        if not policy_decisions:
            raise XaiInstrumentationError("FINGERPRINT_INPUT_MISSING", "policy has no decisions")
        bins = (
            _fingerprint_bin("low", 0.0, 0.34, policy_decisions),
            _fingerprint_bin("medium", 0.34, 0.67, policy_decisions),
            _fingerprint_bin("high", 0.67, 1.01, policy_decisions),
        )
        fingerprints.append(
            BehaviouralFingerprint.model_validate(
                {
                    "policy_id": policy_id,
                    "decision_set_digest": _digest(
                        [item.model_dump(mode="json") for item in policy_decisions]
                    ),
                    "bins": bins,
                    "total_support": len(policy_decisions),
                }
            )
        )
    return tuple(fingerprints)


class AttributionContribution(XaiModel):
    feature_name: Literal["declared_load", "queue_fraction", "deadline_pressure"]
    feature_value: float = Field(ge=0, le=1)
    contribution: float


class AttributionQualityMetadata(XaiModel):
    fidelity_metric: Literal["synthetic_reconstruction_absolute_error"] = (
        "synthetic_reconstruction_absolute_error"
    )
    fidelity_value: float = Field(ge=0)
    stability_metric: Literal["synthetic_repeat_max_absolute_delta"] = (
        "synthetic_repeat_max_absolute_delta"
    )
    stability_value: float = Field(ge=0)
    repeats: int = Field(ge=2)
    perturbation_scope: Literal["identical_synthetic_fixture_replay"] = (
        "identical_synthetic_fixture_replay"
    )
    application_validation: Literal["unavailable"] = "unavailable"
    integrity_check_only: Literal[True] = True
    faithfulness_validated: Literal[False] = False


class AttributionArtifact(XaiModel):
    artifact_id: str = Field(pattern=_SHA256_PATTERN)
    method: AttributionMethod
    method_version: Literal["synthetic-shape-1.0"] = "synthetic-shape-1.0"
    source_artifact_digest: str = Field(pattern=_SHA256_PATTERN)
    snapshot_id: str
    snapshot_digest: str = Field(pattern=_SHA256_PATTERN)
    actor_id: Literal["synthetic_policy_fixture"] = "synthetic_policy_fixture"
    actor_contract_digest: str = Field(pattern=_SHA256_PATTERN)
    checkpoint_digest: str = Field(pattern=_SHA256_PATTERN)
    baseline_value: float
    output_value: float
    contributions: tuple[AttributionContribution, ...]
    quality: AttributionQualityMetadata
    availability: Literal["synthetic_shape_only"] = "synthetic_shape_only"
    real_actor: Literal[False] = False
    causal: Literal[False] = False
    faithfulness_validated: Literal[False] = False
    optimality_supported: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_fixture_integrity(self) -> AttributionArtifact:
        if tuple(item.feature_name for item in self.contributions) != (
            "declared_load",
            "queue_fraction",
            "deadline_pressure",
        ):
            raise ValueError("ATTRIBUTION_FEATURE_ORDER_MISMATCH")
        reconstructed = self.baseline_value + sum(item.contribution for item in self.contributions)
        error = abs(reconstructed - self.output_value)
        if not math.isclose(error, self.quality.fidelity_value, abs_tol=1e-12):
            raise ValueError("ATTRIBUTION_RECONSTRUCTION_MISMATCH")
        payload = self.model_dump(mode="json")
        del payload["artifact_id"]
        if _digest(payload) != self.artifact_id:
            raise ValueError("ATTRIBUTION_DIGEST_MISMATCH")
        return self


class AttributionCapability(XaiModel):
    method: Literal["shap", "integrated_gradients"]
    status: Literal["unavailable"] = "unavailable"
    missing_requirements: tuple[MissingAttributionRequirement, ...]
    zero_substituted: Literal[False] = False
    evidence: Literal[False] = False


def _attribution_fixture(
    snapshot: DecisionTimeSnapshot,
    method: AttributionMethod,
    contributions: tuple[float, float, float],
) -> AttributionArtifact:
    rows = tuple(
        AttributionContribution(
            feature_name=feature.name, feature_value=feature.value, contribution=value
        )
        for feature, value in zip(snapshot.features, contributions, strict=True)
    )
    baseline = 0.3
    output = baseline + sum(contributions)
    payload: dict[str, object] = {
        "method": method,
        "method_version": "synthetic-shape-1.0",
        "source_artifact_digest": snapshot.source_artifact_digest,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_digest": snapshot.digest(),
        "actor_id": snapshot.actor_id,
        "actor_contract_digest": snapshot.actor_contract_digest,
        "checkpoint_digest": snapshot.checkpoint_digest,
        "baseline_value": baseline,
        "output_value": output,
        "contributions": tuple(row.model_dump(mode="json") for row in rows),
        "quality": AttributionQualityMetadata(
            fidelity_value=0.0,
            stability_value=0.0,
            repeats=3,
        ).model_dump(mode="json"),
        "availability": "synthetic_shape_only",
        "real_actor": False,
        "causal": False,
        "faithfulness_validated": False,
        "optimality_supported": False,
        "scientific_evidence": False,
    }
    return AttributionArtifact.model_validate({"artifact_id": _digest(payload), **payload})


class XaiAuditBundle(XaiModel):
    method_version: Literal["xai-instrumentation-1.0"] = METHOD_VERSION
    source_support: tuple[SourceSupport, ...]
    snapshots: tuple[DecisionTimeSnapshot, ...]
    replay_manifests: tuple[ReplayAdapterManifest, ...]
    replay_results: tuple[CounterfactualReplayResult, ...]
    disagreement_rows: tuple[PolicyDisagreementRow, ...]
    fingerprints: tuple[BehaviouralFingerprint, ...]
    attribution_artifacts: tuple[AttributionArtifact, ...]
    attribution_capabilities: tuple[AttributionCapability, ...]
    notices: tuple[str, ...]
    synthetic_fixture: Literal[True] = True
    real_attribution_available: Literal[False] = False
    causal: Literal[False] = False
    faithfulness_validated: Literal[False] = False
    scientific_evidence: Literal[False] = False
    execution_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_complete_bundle(self) -> XaiAuditBundle:
        if len(self.snapshots) != 12 or len(self.replay_results) != 24:
            raise ValueError("SYNTHETIC_FIXTURE_COUNT_MISMATCH")
        if len(self.disagreement_rows) != len(self.replay_results):
            raise ValueError("DISAGREEMENT_COUNT_MISMATCH")
        if tuple(item.adapter_id for item in self.replay_manifests) != (
            "always_local",
            "lyapunov_queue_aware",
        ):
            raise ValueError("REPLAY_MANIFEST_MISMATCH")
        if tuple(item.policy_id for item in self.fingerprints) != (
            "synthetic_policy_fixture",
            "always_local",
            "lyapunov_queue_aware",
        ):
            raise ValueError("FINGERPRINT_POLICY_MISMATCH")
        if tuple(item.method for item in self.attribution_artifacts) != (
            "shap_shaped_synthetic_fixture",
            "integrated_gradients_shaped_synthetic_fixture",
        ):
            raise ValueError("ATTRIBUTION_FIXTURE_MISMATCH")
        if tuple(item.method for item in self.attribution_capabilities) != (
            "shap",
            "integrated_gradients",
        ):
            raise ValueError("ATTRIBUTION_CAPABILITY_MISMATCH")
        if len({item.support_id for item in self.source_support}) != len(self.source_support):
            raise ValueError("SOURCE_SUPPORT_DUPLICATE")
        support_ids = {item.support_id for item in self.source_support}
        if any(
            not set(snapshot.source_support_ids).issubset(support_ids)
            for snapshot in self.snapshots
        ):
            raise ValueError("SOURCE_SUPPORT_MISMATCH")
        snapshot_by_id = {item.snapshot_id: item for item in self.snapshots}
        manifests = {item.adapter_id: item for item in self.replay_manifests}
        for replay in self.replay_results:
            snapshot = snapshot_by_id.get(replay.snapshot_id)
            manifest = manifests.get(replay.adapter_id)
            if snapshot is None or manifest is None:
                raise ValueError("REPLAY_BINDING_MISMATCH")
            expected_input = _digest(
                {
                    "snapshot_digest": snapshot.digest(),
                    "adapter_manifest_digest": manifest.digest(),
                }
            )
            if (
                replay.snapshot_digest != snapshot.digest()
                or replay.adapter_manifest_digest != manifest.digest()
                or replay.input_digest != expected_input
            ):
                raise ValueError("REPLAY_BINDING_MISMATCH")
        if self.disagreement_rows != build_disagreement_rows(self.snapshots, self.replay_results):
            raise ValueError("DISAGREEMENT_BINDING_MISMATCH")
        expected_fingerprints = build_behavioural_fingerprints(
            build_policy_decisions(self.snapshots, self.replay_results)
        )
        if self.fingerprints != expected_fingerprints:
            raise ValueError("FINGERPRINT_BINDING_MISMATCH")
        for artifact in self.attribution_artifacts:
            snapshot = snapshot_by_id.get(artifact.snapshot_id)
            if (
                snapshot is None
                or artifact.snapshot_digest != snapshot.digest()
                or artifact.source_artifact_digest != snapshot.source_artifact_digest
                or artifact.actor_contract_digest != snapshot.actor_contract_digest
                or artifact.checkpoint_digest != snapshot.checkpoint_digest
            ):
                raise ValueError("ATTRIBUTION_BINDING_MISMATCH")
        for notice in self.notices:
            validate_explanation_language(notice)
        if _has_private_content(self.model_dump(mode="json")):
            raise ValueError("PRIVATE_CONTENT_DETECTED")
        return self

    def digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


def _source_support(
    research_directions_digest: str,
    producer_citation_digest: str,
) -> tuple[SourceSupport, ...]:
    method_references = (
        (
            "shap-method-reference",
            "literature:Lundberg-Lee-2017-SHAP",
            "Defines a SHAP attribution family and motivates only the synthetic artifact shape.",
        ),
        (
            "ig-method-reference",
            "literature:Sundararajan-Taly-Yan-2017-Integrated-Gradients",
            "Defines Integrated Gradients and motivates only the synthetic artifact shape.",
        ),
    )
    records = [
        SourceSupport(
            support_id="meeting1-project-context",
            role="project_context",
            source_ref="docs/research_directions_v2.md",
            source_digest=research_directions_digest,
            binding_kind="exact_repository_bytes",
            support_scope=(
                "Motivates decision-level instrumentation and behaviour-versus-load views."
            ),
            limitation="Does not validate an attribution method or explain a real actor decision.",
            evidence=False,
        ),
        SourceSupport(
            support_id="producer-citation-contract",
            role="project_context",
            source_ref="docs/producer_citation_requirements.md",
            source_digest=producer_citation_digest,
            binding_kind="exact_repository_bytes",
            support_scope=(
                "Constrains future producer-derived actor and checkpoint citation records."
            ),
            limitation=(
                "Provides provenance requirements, not model access or explanation validity."
            ),
            evidence=False,
        ),
        SourceSupport(
            support_id="synthetic-decision-fixture",
            role="synthetic_fixture",
            source_ref="builtin:xai-synthetic-decision-fixture-v1",
            source_digest=_digest("xai-synthetic-decision-fixture-v1"),
            binding_kind="contract_record",
            support_scope=(
                "Exercises snapshot, replay, disagreement, fingerprint and attribution schemas."
            ),
            limitation="Synthetic software verification only; it is not a real actor observation.",
            evidence=False,
        ),
    ]
    records.extend(
        SourceSupport(
            support_id=support_id,
            role="method_reference",
            source_ref=source_ref,
            source_digest=_digest({"source_ref": source_ref, "binding": "citation_metadata_only"}),
            binding_kind="citation_metadata_only",
            support_scope=scope,
            limitation="Citation identity alone does not validate this application or fixture.",
            evidence=True,
        )
        for support_id, source_ref, scope in method_references
    )
    for support_id, requirement in (
        ("missing-producer-hook", "A compatible producer decision-time snapshot hook is absent."),
        ("missing-model-access", "Authorised real actor and checkpoint model access is absent."),
        (
            "missing-validation-method",
            "A predeclared literature-grounded application validation method is absent.",
        ),
    ):
        records.append(
            SourceSupport(
                support_id=support_id,
                role="unavailable_requirement",
                source_ref=f"requirement:{support_id}",
                source_digest=_digest(requirement),
                binding_kind="contract_record",
                support_scope=requirement,
                limitation="The missing requirement keeps real attribution unavailable.",
                evidence=False,
            )
        )
    return tuple(records)


def _snapshots() -> tuple[DecisionTimeSnapshot, ...]:
    source_artifact_digest = _digest("xai-synthetic-decision-fixture-v1")
    actions: tuple[ActionName, ...] = (
        "local",
        "local",
        "v2i",
        "local",
        "v2i",
        "v2v",
        "v2i",
        "v2v",
        "local",
        "v2v",
        "v2v",
        "local",
    )
    snapshots: list[DecisionTimeSnapshot] = []
    for index, action in enumerate(actions):
        load = round(0.05 + index * 0.08, 2)
        queue = round(min(0.95, 0.1 + index * 0.07), 2)
        deadline = round(0.2 + (index % 4) * 0.2, 2)
        features = (
            SnapshotFeature(name="declared_load", value=load),
            SnapshotFeature(name="queue_fraction", value=queue),
            SnapshotFeature(name="deadline_pressure", value=deadline),
        )
        record_payload = {
            "index": index,
            "features": tuple(item.model_dump(mode="json") for item in features),
            "recorded_action": action,
        }
        snapshots.append(
            DecisionTimeSnapshot(
                snapshot_id=f"synthetic-snapshot-{index:03d}",
                source_artifact_digest=source_artifact_digest,
                source_record_digest=_digest(record_payload),
                actor_contract_digest=SYNTHETIC_ACTOR_CONTRACT_DIGEST,
                checkpoint_digest=SYNTHETIC_CHECKPOINT_DIGEST,
                observation_contract_digest=OBSERVATION_CONTRACT_DIGEST,
                action_vocabulary_digest=ACTION_VOCABULARY_DIGEST,
                simulation_step=index,
                features=features,
                recorded_action=action,
                source_support_ids=(
                    "meeting1-project-context",
                    "synthetic-decision-fixture",
                ),
            )
        )
    return tuple(snapshots)


def build_synthetic_xai_audit_bundle(
    *,
    research_directions_digest: str,
    producer_citation_digest: str,
) -> XaiAuditBundle:
    """Build the complete deterministic fixture with real attribution unavailable."""

    for digest in (research_directions_digest, producer_citation_digest):
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise XaiInstrumentationError("SOURCE_DIGEST_INVALID", "source digest must be SHA-256")
    source_support = _source_support(research_directions_digest, producer_citation_digest)
    snapshots = _snapshots()
    adapters: tuple[CounterfactualReplayAdapter, ...] = (
        AlwaysLocalReplay(),
        LyapunovQueueAwareReplay(),
    )
    replays = replay_counterfactuals(snapshots, adapters)
    disagreements = build_disagreement_rows(snapshots, replays)
    decisions = build_policy_decisions(snapshots, replays)
    fingerprints = build_behavioural_fingerprints(decisions)
    attribution_artifacts = (
        _attribution_fixture(snapshots[5], "shap_shaped_synthetic_fixture", (0.08, -0.03, 0.02)),
        _attribution_fixture(
            snapshots[5],
            "integrated_gradients_shaped_synthetic_fixture",
            (0.07, -0.01, 0.01),
        ),
    )
    missing: tuple[MissingAttributionRequirement, ...] = (
        "producer_snapshot_hook",
        "authorised_model_access",
        "validated_application_method",
    )
    capabilities = (
        AttributionCapability(method="shap", missing_requirements=missing),
        AttributionCapability(method="integrated_gradients", missing_requirements=missing),
    )
    return XaiAuditBundle(
        source_support=source_support,
        snapshots=snapshots,
        replay_manifests=tuple(adapter.manifest for adapter in adapters),
        replay_results=replays,
        disagreement_rows=disagreements,
        fingerprints=fingerprints,
        attribution_artifacts=attribution_artifacts,
        attribution_capabilities=capabilities,
        notices=(
            "Synthetic contract fixture only; no real actor or checkpoint was opened.",
            "Disagreements and action shares are descriptive and not causal.",
            "Attribution-shaped arithmetic checks do not establish faithfulness or validation.",
            "No row identifies a correct, safer, better or executable action.",
        ),
    )


def iter_bundle_text(bundle: XaiAuditBundle) -> Iterable[str]:
    """Expose bounded strings for presentation-layer privacy and language checks."""

    for support in bundle.source_support:
        yield support.source_ref
        yield support.support_scope
        yield support.limitation
    yield from bundle.notices
