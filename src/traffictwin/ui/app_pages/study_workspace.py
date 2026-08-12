"""App page wrapper for Study Workspace."""

from __future__ import annotations

from traffictwin.ui.pages.study_workspace import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
