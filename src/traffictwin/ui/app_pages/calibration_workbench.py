"""App page wrapper for Calibration Workbench."""

from __future__ import annotations

from traffictwin.ui.pages.calibration_workbench import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
