"""Direct route for the frozen dissertation study."""

import streamlit as st

from traffictwin.ui.pages.experimental_results import render

st.session_state["_active_ui_route"] = "experimental-results"
render()
