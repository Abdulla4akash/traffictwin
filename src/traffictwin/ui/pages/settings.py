"""Lightweight local Settings page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render local, session-scoped settings."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.SETTINGS))
    settings = dict(st.session_state.get("ui_settings", {}))

    section_header("Workspace")
    st.text_input("Active registry", value=str(config.registry_path), disabled=True)
    st.text_input(
        "Default workspace",
        value=str(config.workspace_path or ""),
        disabled=True,
        help="Set with TRAFFICTWIN_WORKSPACE_PATH before launching Streamlit.",
    )

    section_header("Preferences")
    theme = st.selectbox(
        "Theme",
        ["Research", "Compact"],
        index=0 if settings.get("theme", "Research") == "Research" else 1,
    )
    replay_speed = st.selectbox(
        "Default replay speed",
        [0.25, 0.5, 1.0, 2.0, 5.0],
        index=_speed_index(float(settings.get("default_replay_speed", 1.0))),
    )
    report_format = st.selectbox(
        "Default report format",
        ["markdown", "html"],
        index=0 if settings.get("default_report_format", "markdown") == "markdown" else 1,
    )
    export_dir = st.text_input(
        "Preferred export directory",
        value=str(settings.get("preferred_export_directory", "exports")),
    )
    demo_auto = st.checkbox(
        "Prefer standalone demo defaults",
        value=bool(settings.get("demo_auto_initialise", True)),
    )

    if st.button("Save Settings"):
        st.session_state["ui_settings"] = {
            "theme": theme,
            "default_replay_speed": replay_speed,
            "default_report_format": report_format,
            "preferred_export_directory": export_dir,
            "demo_auto_initialise": demo_auto,
        }
        st.success("Settings saved for this Streamlit session.")


def _speed_index(speed: float) -> int:
    speeds = [0.25, 0.5, 1.0, 2.0, 5.0]
    return speeds.index(speed) if speed in speeds else speeds.index(1.0)
