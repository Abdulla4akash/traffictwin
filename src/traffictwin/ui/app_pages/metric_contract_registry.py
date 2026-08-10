"""Direct Streamlit page script for the Metric Contract Registry."""

from traffictwin.ui.pages.metric_contract_registry import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
