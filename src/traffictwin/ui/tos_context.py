"""Shared session context for read-only TOS package pages."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.services import ServiceError, TosPackageView, inspect_tos_for_ui
from traffictwin.ui.state import UiConfig


def active_tos_package(config: UiConfig) -> TosPackageView | None:
    """Return or reconstruct the selected package view without mutating source files."""

    current = st.session_state.get("latest_tos_package_view")
    selected = st.session_state.get("selected_tos_data_path") or config.tos_data_path
    if isinstance(current, TosPackageView) and (
        selected is None or current.source_path == Path(selected).resolve()
    ):
        return current
    if selected and Path(selected).is_dir():
        with st.spinner("Inspecting the selected TOS package..."):
            current = inspect_tos_for_ui(selected, deep=False)
        st.session_state["latest_tos_package_view"] = current
    if isinstance(current, ServiceError):
        st.error(current.message)
        if current.detail:
            with st.expander("Advanced: technical detail"):
                st.code(current.detail)
        return None
    if isinstance(current, TosPackageView):
        return current
    st.info("Inspect a TOS Data package on the TOS Data Import page first.")
    return None
