"""Direct Streamlit page script for workspace activation."""

from traffictwin.ui.pages.workspace_activation import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
