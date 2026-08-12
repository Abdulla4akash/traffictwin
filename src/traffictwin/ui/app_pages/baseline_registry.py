"""Direct Streamlit page script for the candidate v0.7 router."""

from traffictwin.ui.pages.baseline_registry import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
