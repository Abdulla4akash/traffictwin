"""Wrapper for Study Capsule page; navigation registration is additive."""

try:
    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.page_runtime import run_page_script

    run_page_script(UiPage.STUDY_CAPSULE)
except Exception:
    # Fallback for early development / isolated testing before navigation registration
    from traffictwin.ui.pages.study_capsule import render as _render
    from traffictwin.ui.state import load_ui_config

    _render(load_ui_config())
