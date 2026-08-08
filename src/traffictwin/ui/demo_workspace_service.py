"""Thin in-UI demo-workspace service for the P0 clean-workspace journey.

The Streamlit pages remain thin: this module turns the single
``traffictwin.demo.workspace`` library into a typed, failure-explicit
UI boundary without duplicating generation logic, metrics, or registry
knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import streamlit as st

from traffictwin.demo.workspace import initialise_workspace, workspace_status
from traffictwin.ui.state import UiConfig

DEFAULT_DEMO_WORKSPACE_PATH = Path(".traffictwin-demo")

_ACTIVE_DEMO_WORKSPACE_KEY = "_active_demo_workspace_path"
_ACTIVE_REGISTRY_KEY = "active_registry_path"
_DEMO_WORKSPACE_FLASH_KEY = "_demo_workspace_flash"

DemoWorkspaceStatus = Literal["ready", "created", "already_exists", "failed"]
DemoWorkspaceReason = Literal[
    "ready",
    "created",
    "already_exists",
    "invalid_path",
    "unsafe_path",
    "non_empty_without_force",
    "unexpected_error",
]


@dataclass(frozen=True)
class DemoWorkspaceResult:
    """Typed result from creating or inspecting a demo workspace."""

    status: DemoWorkspaceStatus
    path: Path
    reason: DemoWorkspaceReason
    message: str
    workspace_valid: bool
    scenario_count: int
    imported_run_count: int
    comparison_count: int


def inspect_demo_workspace(path: str | Path | None) -> DemoWorkspaceResult:
    """Inspect an existing demo workspace without mutation."""

    workspace = _coerce_workspace_path(path)
    if workspace is None:
        return DemoWorkspaceResult(
            status="failed",
            path=DEFAULT_DEMO_WORKSPACE_PATH,
            reason="invalid_path",
            message="No workspace path is configured. Use the demo initialiser first.",
            workspace_valid=False,
            scenario_count=0,
            imported_run_count=0,
            comparison_count=0,
        )
    try:
        status = workspace_status(workspace)
    except (OSError, ValueError) as exc:
        return DemoWorkspaceResult(
            status="failed",
            path=workspace,
            reason="unsafe_path",
            message=str(exc),
            workspace_valid=False,
            scenario_count=0,
            imported_run_count=0,
            comparison_count=0,
        )
    if not status.valid_workspace:
        joined = (
            "; ".join(status.messages) if status.messages else "No valid workspace marker found."
        )
        return DemoWorkspaceResult(
            status="failed",
            path=workspace,
            reason="unexpected_error",
            message=joined,
            workspace_valid=False,
            scenario_count=status.scenario_count,
            imported_run_count=status.imported_run_count,
            comparison_count=status.comparison_count,
        )
    return DemoWorkspaceResult(
        status="ready",
        path=workspace,
        reason="ready",
        message=(
            f"Demo workspace ready at {workspace}: {status.scenario_count} scenarios, "
            f"{status.imported_run_count} runs, {status.comparison_count} comparisons."
        ),
        workspace_valid=True,
        scenario_count=status.scenario_count,
        imported_run_count=status.imported_run_count,
        comparison_count=status.comparison_count,
    )


def ensure_demo_workspace(
    path: str | Path | None = None,
    *,
    allow_existing: bool = True,
) -> DemoWorkspaceResult:
    """Create a deterministic demo workspace at ``path`` if absent.

    The call is bounded and synchronous; it reuses the existing
    ``initialise_workspace`` library and its safety checks.  It never
    guesses a private path and never mutates the caller on failure.
    """

    workspace = _coerce_workspace_path(path)
    if workspace is None:
        return DemoWorkspaceResult(
            status="failed",
            path=DEFAULT_DEMO_WORKSPACE_PATH,
            reason="invalid_path",
            message="Provide a valid filesystem path for the demo workspace.",
            workspace_valid=False,
            scenario_count=0,
            imported_run_count=0,
            comparison_count=0,
        )

    # If a valid workspace already lives there, report it as success
    # rather than failing — the UI should treat this as a harmless rerun.
    try:
        status = workspace_status(workspace)
    except (OSError, ValueError) as exc:
        return DemoWorkspaceResult(
            status="failed",
            path=workspace,
            reason="unsafe_path",
            message=str(exc),
            workspace_valid=False,
            scenario_count=0,
            imported_run_count=0,
            comparison_count=0,
        )
    if status.valid_workspace and allow_existing:
        return DemoWorkspaceResult(
            status="already_exists",
            path=workspace,
            reason="already_exists",
            message=(
                f"A demo workspace already exists at {workspace}. No new workspace was "
                f"created; the existing {status.scenario_count} scenarios and "
                f"{status.imported_run_count} runs remain available."
            ),
            workspace_valid=True,
            scenario_count=status.scenario_count,
            imported_run_count=status.imported_run_count,
            comparison_count=status.comparison_count,
        )

    try:
        result = initialise_workspace(workspace)
    except FileExistsError as exc:
        return DemoWorkspaceResult(
            status="failed",
            path=workspace,
            reason="non_empty_without_force",
            message=str(exc),
            workspace_valid=False,
            scenario_count=0,
            imported_run_count=0,
            comparison_count=0,
        )
    except ValueError as exc:
        return DemoWorkspaceResult(
            status="failed",
            path=workspace,
            reason="unsafe_path",
            message=str(exc),
            workspace_valid=False,
            scenario_count=0,
            imported_run_count=0,
            comparison_count=0,
        )
    except (OSError, RuntimeError) as exc:
        return DemoWorkspaceResult(
            status="failed",
            path=workspace,
            reason="unexpected_error",
            message=str(exc),
            workspace_valid=False,
            scenario_count=0,
            imported_run_count=0,
            comparison_count=0,
        )

    # Re-read status so the reported counts are authoritative, not
    # merely what the initialiser claims.
    final_status = workspace_status(workspace)
    return DemoWorkspaceResult(
        status="created",
        path=result.path,
        reason="created",
        message=(
            f"Demo workspace created at {workspace}: {final_status.scenario_count} scenarios, "
            f"{final_status.imported_run_count} runs, {final_status.comparison_count} comparisons. "
            "All data is synthetic — no Manchester or live source was used."
        ),
        workspace_valid=final_status.valid_workspace,
        scenario_count=final_status.scenario_count,
        imported_run_count=final_status.imported_run_count,
        comparison_count=final_status.comparison_count,
    )


def _coerce_workspace_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    raw = str(path).strip()
    if not raw:
        return None
    return Path(raw)


def _is_valid_workspace(path: Path) -> bool:
    """Return True only for a workspace that contains a valid marker."""

    try:
        return workspace_status(path).valid_workspace
    except (OSError, ValueError):
        return False


def _is_within_workspace(candidate: Path, workspace: Path) -> bool:
    """Return True only when ``candidate`` is contained in ``workspace``."""

    try:
        return candidate.resolve().is_relative_to(workspace.resolve())
    except (OSError, ValueError, RuntimeError):
        return False


def resolve_effective_demo_paths(config: UiConfig) -> tuple[Path | None, Path]:
    """Resolve the effective workspace and registry with clear precedence.

    Precedence is ``valid configured workspace > valid session workspace > no workspace``.
    A session registry is honoured only when it is contained in the effective
    workspace (via :meth:`Path.is_relative_to`); when no valid workspace exists
    the session registry is honoured so that an in-browser demo creation shows
    counts immediately without a process restart.
    """

    workspace: Path | None = config.workspace_path
    registry: Path = config.registry_path
    session_workspace = st.session_state.get(_ACTIVE_DEMO_WORKSPACE_KEY)
    session_registry = st.session_state.get(_ACTIVE_REGISTRY_KEY)

    if workspace is not None and not _is_valid_workspace(workspace):
        workspace = None

    if workspace is None and isinstance(session_workspace, str) and session_workspace.strip():
        candidate_ws = Path(session_workspace.strip())
        if _is_valid_workspace(candidate_ws):
            workspace = candidate_ws

    if isinstance(session_registry, str) and session_registry.strip():
        candidate = Path(session_registry.strip())
        if workspace is not None:
            if _is_within_workspace(candidate, workspace):
                registry = candidate
        else:
            registry = candidate
    return workspace, registry
