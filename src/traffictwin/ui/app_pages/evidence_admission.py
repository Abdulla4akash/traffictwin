"""Streamlit entry point for the Evidence Admission Inbox additive page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.pages.evidence_admission import render
from traffictwin.ui.state import load_ui_config

st.session_state["_active_ui_route"] = "evidence-admission"
st.sidebar.caption(
    "Human review between validation and admission; validation is not admission, "
    "and no attachment is created automatically."  # noqa: E501
)
render(load_ui_config())
