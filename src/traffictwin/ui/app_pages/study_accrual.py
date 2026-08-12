from traffictwin.ui.pages.study_accrual import render
from traffictwin.ui.state import UiConfig, load_ui_config

config: UiConfig = load_ui_config()
render(config)
