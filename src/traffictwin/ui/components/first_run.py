"""First-run guidance for pages whose workspace holds no records yet.

The guidance is additive beside the page's honest empty state, never a
replacement for it: unavailable and empty conditions stay visible exactly as
before, and the component only offers concrete next actions when there is
genuinely nothing to show.
"""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button

GUIDANCE_HEADING = "Getting started"


def first_run_guidance(
    *,
    actions: Sequence[tuple[str, UiPage]],
    message: str,
    key_prefix: str,
) -> None:
    """Offer concrete next steps beside an honest empty state."""

    with st.container(border=True):
        st.markdown(f"**{GUIDANCE_HEADING}**")
        st.caption(message)
        columns = st.columns(max(len(actions), 1))
        for column, (label, page) in zip(columns, actions, strict=False):
            navigation_button(
                column.button,
                label,
                page,
                key=f"{key_prefix}_{page.name.lower()}",
                width="stretch",
            )
