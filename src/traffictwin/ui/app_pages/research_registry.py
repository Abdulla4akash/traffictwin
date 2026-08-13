"""Direct Streamlit page script for Research Registry (read-only, typed Lane 07/08)."""

from traffictwin.ui.pages.research_registry import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
