"""Thin app-page wrapper for Study Workspace (with fallback for isolated commits)."""

from __future__ import annotations

try:
    from traffictwin.ui.labels import UiPage
    from traffictwin.ui.page_runtime import run_page_script

    target = getattr(UiPage, "STUDY_WORKSPACE", None)
    if target is None:
        raise AttributeError("STUDY_WORKSPACE not yet registered")
    run_page_script(target)
except Exception:
    # Fallback when the enum has not yet been registered (pre-integration isolated commit)
    import streamlit as st

    from traffictwin.ui.pages.study_workspace import render
    from traffictwin.ui.state import UiConfig

    # Minimal render fallback — full render will work once navigation is registered
    try:
        render(UiConfig())
    except Exception as exc:  # pragma: no cover - surface error thinly
        st.error(f"Workspace render failed: {exc}")
