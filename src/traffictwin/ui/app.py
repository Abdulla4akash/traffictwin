"""Streamlit app entry point."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.guided_runtime import consume_guided_legacy_navigation
from traffictwin.ui.navigation import render_sidebar_context, select_page
from traffictwin.ui.navigation_v07 import (
    v07_navigation_pages,
    v07_navigation_requested,
)
from traffictwin.ui.page_runtime import render_registered_page
from traffictwin.ui.state import ensure_session_state, load_ui_config
from traffictwin.ui.theme import apply_research_theme


def main() -> None:
    """Run the Streamlit application."""

    config = load_ui_config()
    st.set_page_config(page_title=config.page_title, layout="wide")
    apply_research_theme()
    ensure_session_state(st.session_state, config)
    if config.workspace_path is not None:
        default_bundle = config.default_fixture_path / "baseline"
        current_bundle = str(st.session_state.get("selected_bundle_path", ""))
        if default_bundle.exists() and (
            not current_bundle or current_bundle.startswith("tests/fixtures")
        ):
            st.session_state["selected_bundle_path"] = str(default_bundle)
            st.session_state["selected_baseline_run"] = str(default_bundle)
            variation = config.default_fixture_path / "stressed_demand"
            if variation.exists():
                st.session_state["selected_variation_run"] = str(variation)
    # Branding is deliberately not a page-level heading: every registered page
    # supplies the one h1 that describes its own content.
    st.sidebar.markdown("**TrafficTwin**")
    st.sidebar.caption("Import-first research UI")
    if v07_navigation_requested():
        st.session_state["_v07_navigation_active"] = True
        navigation = st.navigation(v07_navigation_pages(), position="sidebar", expanded=False)
        navigation.run()
        return
    st.session_state["_v07_navigation_active"] = False
    consume_guided_legacy_navigation()
    page = select_page()
    st.session_state["_active_ui_page"] = page
    render_sidebar_context(page)
    render_registered_page(page, config)


if __name__ == "__main__":
    main()
