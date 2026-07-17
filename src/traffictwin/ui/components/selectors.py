"""Selector helpers."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st


def bundle_path_input(label: str, default: str, *, key: str) -> Path:
    """Render a bundle path input."""

    value = st.text_input(label, value=default, key=key)
    return Path(value)


def run_selector(label: str, options: list[str], *, key: str) -> str | None:
    """Render a run selector."""

    if not options:
        st.info("No registered runs available.")
        return None
    return cast(str, st.selectbox(label, options, key=key))
