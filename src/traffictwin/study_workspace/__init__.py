"""Study Workspace & Research Lifecycle Cockpit package.

Thin, deterministic workspace that references existing TrafficTwin
artifacts without copying or silently mutating them.
"""

from __future__ import annotations

from traffictwin.study_workspace.models import (
    StudyWorkspaceManifest,
    WorkspaceAction,
    WorkspaceArtifactKind,
    WorkspaceArtifactRef,
    WorkspaceArtifactStanding,
    WorkspaceAvailabilityState,
    WorkspaceBlocker,
    WorkspaceBlockerSeverity,
    WorkspaceCompatibilityStanding,
    WorkspaceLifecycleStage,
    WorkspaceValidationReport,
)
from traffictwin.study_workspace.service import (
    derive_lifecycle_stage,
    fingerprint_manifest,
    next_actions,
    validate_workspace,
)

__all__ = [
    "StudyWorkspaceManifest",
    "WorkspaceAction",
    "WorkspaceArtifactKind",
    "WorkspaceArtifactRef",
    "WorkspaceArtifactStanding",
    "WorkspaceAvailabilityState",
    "WorkspaceBlocker",
    "WorkspaceBlockerSeverity",
    "WorkspaceCompatibilityStanding",
    "WorkspaceLifecycleStage",
    "WorkspaceValidationReport",
    "derive_lifecycle_stage",
    "fingerprint_manifest",
    "next_actions",
    "validate_workspace",
]
