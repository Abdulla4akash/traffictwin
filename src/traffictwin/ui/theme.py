"""Small Streamlit theme helpers for the research UI."""

from __future__ import annotations

import streamlit as st


def apply_research_theme() -> None:
    """Apply small, theme-aware presentation helpers.

    Colour, typography, radius, and light/dark variants come from the native
    Streamlit theme in ``.streamlit/config.toml``. This helper only keeps
    layout-neutral utility styles that read correctly in both modes; it must
    never hard-code light-only or dark-only colours.
    """

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] [role="radiogroup"] label {
            margin-bottom: 0.15rem;
        }
        .tt-notice {
            border-left: 4px solid rgba(100, 116, 139, 0.9);
            padding: 0.65rem 0.8rem;
            background: rgba(148, 163, 184, 0.12);
            border-radius: 6px;
        }
        .tt-lineage {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.92rem;
            line-height: 1.55;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
