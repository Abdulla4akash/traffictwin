"""Small Streamlit theme helpers for the research UI."""

from __future__ import annotations

import streamlit as st


def apply_research_theme() -> None:
    """Apply lightweight, local CSS for visual consistency."""

    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {
            border: 1px solid rgba(49, 51, 63, 0.16);
            border-radius: 8px;
            padding: 0.75rem 0.85rem;
            background: rgba(250, 250, 252, 0.72);
        }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            margin-bottom: 0.15rem;
        }
        .tt-notice {
            border-left: 4px solid #607d8b;
            padding: 0.65rem 0.8rem;
            background: #f6f8fa;
            border-radius: 4px;
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
