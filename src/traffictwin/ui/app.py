"""Streamlit app entry point."""

from __future__ import annotations

import os

import streamlit as st

from traffictwin.integration.manchester.bods_auto_refresh import (
    BodsAutoRefreshError,
    BodsAutoRefreshStatus,
    configured_bods_auto_refresh_seconds,
    configured_bods_bounding_box,
    ensure_bods_auto_refresh,
)
from traffictwin.integration.manchester.bods_live_control import BodsLiveControlError
from traffictwin.integration.manchester.national_highways_auto_refresh import (
    NationalHighwaysAutoRefreshError,
    NationalHighwaysAutoRefreshStatus,
    configured_national_highways_auto_refresh_seconds,
    ensure_national_highways_auto_refresh,
)
from traffictwin.integration.manchester.national_highways_live import NationalHighwaysLiveError
from traffictwin.ui.guided_runtime import consume_guided_legacy_navigation
from traffictwin.ui.navigation import render_sidebar_context, select_page
from traffictwin.ui.navigation_v07 import (
    v07_navigation_pages,
    v07_navigation_requested,
)
from traffictwin.ui.page_runtime import render_registered_page
from traffictwin.ui.state import UiConfig, ensure_session_state, load_ui_config
from traffictwin.ui.theme import apply_research_theme


def main() -> None:
    """Run the Streamlit application."""

    config = load_ui_config()
    st.set_page_config(page_title=config.page_title, layout="wide")
    apply_research_theme()
    ensure_session_state(st.session_state, config)
    _ensure_configured_national_highways_auto_refresh(config)
    _ensure_configured_bods_auto_refresh(config)
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


def _ensure_configured_national_highways_auto_refresh(
    config: UiConfig,
) -> NationalHighwaysAutoRefreshStatus | None:
    """Start the idempotent process worker only with a real workspace and transient key."""

    subscription_key = os.getenv("NATIONAL_HIGHWAYS_API_KEY")
    if config.workspace_path is None or not subscription_key:
        st.session_state.pop("_national_highways_auto_refresh_error", None)
        return None
    try:
        interval_seconds = configured_national_highways_auto_refresh_seconds()
        if interval_seconds is None:
            st.session_state.pop("_national_highways_auto_refresh_error", None)
            return None
        status = ensure_national_highways_auto_refresh(
            config.workspace_path,
            subscription_key=subscription_key,
            interval_seconds=interval_seconds,
        )
    except (
        NationalHighwaysAutoRefreshError,
        NationalHighwaysLiveError,
        OSError,
        ValueError,
    ) as exc:
        st.session_state["_national_highways_auto_refresh_error"] = getattr(
            exc, "code", "AUTO_REFRESH_START_FAILED"
        )
        return None
    st.session_state.pop("_national_highways_auto_refresh_error", None)
    return status


def _ensure_configured_bods_auto_refresh(config: UiConfig) -> BodsAutoRefreshStatus | None:
    """Start private BODS polling only with an explicit workspace, key, and request box."""

    api_key = os.getenv("BODS_API_KEY")
    if config.workspace_path is None or not api_key:
        st.session_state.pop("_bods_auto_refresh_error", None)
        return None
    try:
        interval_seconds = configured_bods_auto_refresh_seconds()
        if interval_seconds is None:
            st.session_state.pop("_bods_auto_refresh_error", None)
            return None
        bounding_box = configured_bods_bounding_box()
        if bounding_box is None:
            st.session_state["_bods_auto_refresh_error"] = "BODS_AUTO_REFRESH_SCOPE_MISSING"
            return None
        status = ensure_bods_auto_refresh(
            config.workspace_path,
            bounding_box,
            api_key=api_key,
            interval_seconds=interval_seconds,
        )
    except (BodsAutoRefreshError, BodsLiveControlError, OSError, ValueError) as exc:
        st.session_state["_bods_auto_refresh_error"] = getattr(
            exc, "code", "BODS_AUTO_REFRESH_START_FAILED"
        )
        return None
    st.session_state.pop("_bods_auto_refresh_error", None)
    return status


if __name__ == "__main__":
    main()
