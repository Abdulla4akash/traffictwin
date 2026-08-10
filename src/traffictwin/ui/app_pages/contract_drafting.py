"""Direct app_pages wrapper for Contract Drafting Assistant."""

from traffictwin.ui.pages.contract_drafting import render
from traffictwin.ui.state import load_ui_config

render(load_ui_config())
