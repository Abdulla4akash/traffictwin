"""Badge components."""

from __future__ import annotations

import streamlit as st


def badge(label: str) -> None:
    """Render a compact text badge."""

    st.markdown(f"**`{label}`**")


def badge_row(labels: list[str]) -> None:
    """Render a row of badges."""

    st.markdown(" ".join(f"**`{label}`**" for label in labels))
