"""Allowlisted adapter registry for reproducibility replay."""

from __future__ import annotations

import hashlib
import json

from traffictwin.reproducibility_replay.models import ReplayAdapterDescriptor, ReplayArtifactKind

# Single source of supported kinds — explicit allowlist, no dynamic import.
ADAPTER_REGISTRY: dict[ReplayArtifactKind, ReplayAdapterDescriptor] = {
    ReplayArtifactKind.EVENT_ALIGNED_REPORT: ReplayAdapterDescriptor(
        artifact_kind=ReplayArtifactKind.EVENT_ALIGNED_REPORT,
        supported_schema_versions=["1.0"],
        required_input_fingerprints=[
            "spec_fingerprint",
            "anchor_fingerprint",
        ],
        typed_request_model="EventAlignedWindowSpec+EventAnchor[]",
        service_callable="traffictwin.event_aligned.service:build_event_aligned_report",
        expected_output_type="traffictwin.event_aligned.models:EventAlignedReport",
        description="Reconstruct an event-aligned windowed report from typed window spec and authored anchors.",  # noqa: E501
    ),
    ReplayArtifactKind.RESOURCE_STRATEGY_REPORT: ReplayAdapterDescriptor(
        artifact_kind=ReplayArtifactKind.RESOURCE_STRATEGY_REPORT,
        supported_schema_versions=["1.0"],
        required_input_fingerprints=["study_fingerprint", "source_fingerprint"],
        typed_request_model="ResourceStrategyStudy",
        service_callable="traffictwin.experiments.resource_strategy:build_resource_strategy_report",
        expected_output_type="traffictwin.experiments.resource_strategy:ResourceStrategyReport",
        description="Reconstruct a resource-strategy descriptive report from an admitted study.",
    ),
    ReplayArtifactKind.PREREGISTRATION_GATE: ReplayAdapterDescriptor(
        artifact_kind=ReplayArtifactKind.PREREGISTRATION_GATE,
        supported_schema_versions=["1.0"],
        required_input_fingerprints=["plan_fingerprint"],
        typed_request_model="StudyPlan+EvidenceAttachment[]",
        service_callable="traffictwin.preregistration.service:evaluate_gate",
        expected_output_type="traffictwin.preregistration.models:DecisionGateReport",
        description="Re-evaluate the preregistration decision gate from a frozen plan and admitted evidence.",  # noqa: E501
    ),
    ReplayArtifactKind.COMPARISON_REPORT: ReplayAdapterDescriptor(
        artifact_kind=ReplayArtifactKind.COMPARISON_REPORT,
        supported_schema_versions=["1.0"],
        required_input_fingerprints=[
            "baseline_fingerprint",
            "variation_fingerprint",
        ],
        typed_request_model="MetricCollection+ComparisonRequest",
        service_callable="traffictwin.metrics.comparison:compare_metric_collections",
        expected_output_type="traffictwin.metrics.comparison:ComparisonReport",
        description="Re-run a baseline-versus-variation metric comparison from two MetricCollections.",  # noqa: E501
    ),
}

# Mapping from StudyCapsuleMemberKind to ReplayArtifactKind where portable capsule paths carry allowlisted artifacts.  # noqa: E501
# Capsule artifacts are filtered to EMBED_SAFE_DERIVED only; reference/excluded are not executable.
CAPSULE_MEMBER_TO_REPLAY_KIND: dict[str, ReplayArtifactKind] = {
    # Derived deterministic reports and comparison artifacts are replayable when embedded.
    "deterministic_report": ReplayArtifactKind.EVENT_ALIGNED_REPORT,
    "comparison_report": ReplayArtifactKind.COMPARISON_REPORT,
    "consequence_report": ReplayArtifactKind.RESOURCE_STRATEGY_REPORT,
    # We map run_summary + provenance etc as potential comparison/statistical inputs,
    # but only the allowlisted four kinds below are explicitly supported for replay.
    # For capsules that embed a ResourceStrategyStudy indirectly via deterministic_report,
    # the adapter uses the embedded bytes as study payload.
}

# Additional explicit capsule-kind allowlist for plan building:
# Only these capsule member kinds are considered for replay derivation.
ALLOWLISTED_CAPSULE_KINDS: frozenset[str] = frozenset(
    {
        "deterministic_report",
        "comparison_report",
        "consequence_report",
        "evidence_pack",
        "scenario_seed",
        "run_summary",
        "provenance_graph",
        "diagnostic_result",
        "validation_result",
    }
)

# Allowlisted replay kinds for explicit version checks (registry membership is authoritative).
ALLOWLISTED_REPLAY_KINDS: frozenset[ReplayArtifactKind] = frozenset(ADAPTER_REGISTRY.keys())


def get_adapter(kind: ReplayArtifactKind) -> ReplayAdapterDescriptor | None:
    return ADAPTER_REGISTRY.get(kind)


def is_allowlisted_kind(kind: str | ReplayArtifactKind) -> bool:
    if isinstance(kind, ReplayArtifactKind):
        return kind in ALLOWLISTED_REPLAY_KINDS
    try:
        parsed = ReplayArtifactKind(kind)
    except ValueError:
        return False
    return parsed in ALLOWLISTED_REPLAY_KINDS


def capsule_kind_to_replay_kind(capsule_member_kind: str) -> ReplayArtifactKind | None:
    return CAPSULE_MEMBER_TO_REPLAY_KIND.get(capsule_member_kind)


def registry_fingerprint() -> str:
    payload = {
        k.value: v.model_dump(mode="json")
        for k, v in sorted(ADAPTER_REGISTRY.items(), key=lambda kv: kv[0].value)
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
