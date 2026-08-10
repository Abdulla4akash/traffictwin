"""App page wrapper for Calibration Workbench."""

from __future__ import annotations

try:
    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.page_runtime import run_page_script

    # Attempt normative registration; fallback to direct render if not yet integrated
    run_page_script(UiPage.CALIBRATION_WORKBENCH)  # type: ignore[attr-defined]
except Exception:
    from traffictwin.ui.pages.calibration_workbench import render

    render()
