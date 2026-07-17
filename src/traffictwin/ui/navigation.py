"""Navigation helpers."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.labels import UiPage


def page_options() -> list[str]:
    """Return page labels in sidebar order."""

    return [page.value for page in UiPage]


def select_page() -> UiPage:
    """Render and return the selected page."""

    label = st.sidebar.radio("Navigation", page_options(), key="active_page")
    return UiPage(label)
