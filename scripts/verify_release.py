"""Release smoke checks for the standalone TrafficTwin package."""

from __future__ import annotations

import tempfile
from pathlib import Path

from traffictwin.demo.workspace import initialise_workspace, workspace_status
from traffictwin.release.deployment import stage_synthetic_demo_site
from traffictwin.reporting.builder import build_run_report


def main() -> None:
    """Run lightweight release checks that avoid external services."""

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "demo"
        initialise_workspace(workspace)
        status = workspace_status(workspace)
        if not status.valid_workspace or status.imported_run_count == 0:
            raise SystemExit("demo workspace verification failed")
        build_run_report(workspace / "bundles" / "baseline")
        site = stage_synthetic_demo_site(workspace, Path(tmp) / "public")
        if not site.synthetic or site.live_data or site.external_integration:
            raise SystemExit("synthetic static-site safety verification failed")
    print("release smoke checks passed")


if __name__ == "__main__":
    main()
