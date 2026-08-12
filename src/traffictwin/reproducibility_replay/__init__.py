"""Reproducibility Replay package — deterministic allowlisted replay runner."""

from traffictwin.reproducibility_replay.models import (
    ReplayAdapterDescriptor,
    ReplayArtifactKind,
    ReplayComparison,
    ReplayExecution,
    ReplayMismatch,
    ReplayPlan,
    ReplayPlanEntry,
    ReplayReceipt,
    ReplayRefusal,
    ReplayRequest,
    ReplayStatus,
)
from traffictwin.reproducibility_replay.service import (
    build_replay_plan,
    build_replay_plan_from_capsule_bytes,
    compare_replay_output,
    execute_replay,
    replay_contract,
    verify_capsule_integrity,
)

__all__ = [
    "ReplayAdapterDescriptor",
    "ReplayArtifactKind",
    "ReplayComparison",
    "ReplayExecution",
    "ReplayMismatch",
    "ReplayPlan",
    "ReplayPlanEntry",
    "ReplayReceipt",
    "ReplayRefusal",
    "ReplayRequest",
    "ReplayStatus",
    "build_replay_plan",
    "build_replay_plan_from_capsule_bytes",
    "compare_replay_output",
    "execute_replay",
    "replay_contract",
    "verify_capsule_integrity",
]
