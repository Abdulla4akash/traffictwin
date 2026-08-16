"""Streamlit runtime for the Guided Demo mode tour.

The tour advances presentation stages only. The tick fragment below never
performs a provider request, never records guided-workflow progress, and
never mutates evidence: it moves a slideshow. The ~4-second cadence is
presentation time and is never a simulation or provider timestep.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from traffictwin.ui.guided_tour import (
    TOUR_TICK_SECONDS,
    GuidedDemoMode,
    GuidedTourState,
    advance_tour,
    next_stage,
    pause_tour,
    play_tour,
    previous_stage,
    restart_tour,
    stages_for_mode,
    start_tour,
)

GUIDED_TOUR_KEY = "guided_demo_tour"
GUIDED_TOUR_LIVE_MARKER_KEY = "_guided_demo_live_marker"


def load_tour_state(
    state: MutableMapping[str, Any] | None = None,
) -> GuidedTourState | None:
    """Return the active tour state, discarding anything malformed."""

    store: MutableMapping[str, Any] = st.session_state if state is None else state
    value = store.get(GUIDED_TOUR_KEY)
    if value is None:
        return None
    if isinstance(value, GuidedTourState):
        return value
    store.pop(GUIDED_TOUR_KEY, None)
    return None


def begin_tour(mode: GuidedDemoMode) -> None:
    """Enter one demo mode at its first stage, playing."""

    st.session_state[GUIDED_TOUR_KEY] = start_tour(mode)
    st.session_state.pop(GUIDED_TOUR_LIVE_MARKER_KEY, None)


def exit_tour() -> None:
    """Leave the demo tour and return to the launcher."""

    st.session_state.pop(GUIDED_TOUR_KEY, None)
    st.session_state.pop(GUIDED_TOUR_LIVE_MARKER_KEY, None)


def on_tour_previous() -> None:
    state = load_tour_state()
    if state is not None:
        st.session_state[GUIDED_TOUR_KEY] = previous_stage(state)


def on_tour_next() -> None:
    state = load_tour_state()
    if state is not None:
        st.session_state[GUIDED_TOUR_KEY] = next_stage(state)


def on_tour_toggle_play() -> None:
    state = load_tour_state()
    if state is None:
        return
    st.session_state[GUIDED_TOUR_KEY] = pause_tour(state) if state.playing else play_tour(state)


def on_tour_restart() -> None:
    state = load_tour_state()
    if state is not None:
        st.session_state[GUIDED_TOUR_KEY] = restart_tour(state)


@st.fragment(run_every=TOUR_TICK_SECONDS)  # type: ignore[untyped-decorator]
def render_stage_ticker() -> None:
    """Advance the presentation clock by one declared tick per rerender.

    The fragment escalates to a full-page rerun only when the visible stage
    actually changes, so a paused or finished tour causes no rerun loop.
    """

    state = load_tour_state()
    if state is None or not state.playing:
        return
    if len(stages_for_mode(state.mode)) <= 1:
        return
    advanced = advance_tour(state)
    st.session_state[GUIDED_TOUR_KEY] = advanced
    if advanced.stage_index != state.stage_index or advanced.playing != state.playing:
        st.rerun()
