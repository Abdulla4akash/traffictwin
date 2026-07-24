"""Small Streamlit theme helpers for the research UI."""

from __future__ import annotations


def apply_research_theme() -> None:
    """Retain the public theme hook while native configuration owns styling.

    Colour, typography, radius, widget borders, and light/dark variants all
    come from ``.streamlit/config.toml``. Keeping this function as a no-op
    preserves the app's public call site without injecting brittle HTML/CSS.
    """
