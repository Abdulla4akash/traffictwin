"""One-command standalone Streamlit launcher."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from traffictwin.demo.workspace import initialise_workspace, workspace_status


@dataclass(frozen=True)
class LaunchPlan:
    """Preview of the Streamlit launch command."""

    command: list[str]
    workspace: Path
    registry: Path
    environment: dict[str, str]


def launch_workspace(path: str | Path, *, dry_run: bool = False) -> LaunchPlan:
    """Initialise if needed and launch Streamlit against the demo workspace."""

    workspace = Path(path)
    if not workspace.exists() or not (workspace / "workspace.yaml").exists():
        initialise_workspace(workspace)
    status = workspace_status(workspace)
    if not status.valid_workspace:
        msg = f"workspace is not valid: {workspace}"
        raise ValueError(msg)
    app_path = Path(__file__).resolve().parents[1] / "ui" / "app.py"
    env = os.environ.copy()
    env["TRAFFICTWIN_WORKSPACE_PATH"] = str(workspace)
    env["TRAFFICTWIN_REGISTRY_PATH"] = str(workspace / "registry.sqlite")
    env["TRAFFICTWIN_FIXTURE_PATH"] = str(workspace / "bundles")
    command = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    plan = LaunchPlan(
        command=command,
        workspace=workspace,
        registry=workspace / "registry.sqlite",
        environment={
            "TRAFFICTWIN_WORKSPACE_PATH": str(workspace),
            "TRAFFICTWIN_REGISTRY_PATH": str(workspace / "registry.sqlite"),
            "TRAFFICTWIN_FIXTURE_PATH": str(workspace / "bundles"),
        },
    )
    if not dry_run:
        subprocess.run(command, env=env, check=False)  # noqa: S603 - fixed argv, no shell.
    return plan
