"""Bus Sessions page: aggregate-only evidence from attended live-bus sessions.

A thin surface over :mod:`traffictwin.ui.bus_sessions_services`. It renders the
cadence and hourly-progression aggregates a recorded session left in the
workspace, and nothing else: no acquisition is triggered here, no snapshot is
opened, and no per-vehicle row exists to display.

Three statements the page keeps visible rather than implied. These are bus
vehicles only, never general road traffic. Progression speed is bus displacement
over an update interval, never road speed. And an absent workspace or artifact is
shown as an explicit unavailable state with its reason, never as zero.
"""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.bus_sessions_services import (
    BusSessionContext,
    BusSessionsError,
    UnavailableArtifact,
    cadence_rows,
    load_bus_session_context,
    progression_rows,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render the aggregate-only bus session measurements for this workspace."""

    st.title("Bus Sessions")
    badge_row(["ATTENDED SESSION", "BUS VEHICLES ONLY", "AGGREGATES ONLY"])
    st.caption(
        "Measurements recorded from attended live-bus observation sessions. "
        "Aggregates only — no vehicle reference, session token, or per-vehicle "
        "row exists in these artifacts. Bus progression speed is never "
        "road-traffic speed, and buses are never general traffic."
    )

    context = load_bus_session_context(config.workspace_path)
    if isinstance(context, BusSessionsError):
        st.info(context.message)
        if context.detail:
            with st.expander("Advanced: technical detail"):
                st.code(context.detail, language=None)
        return

    st.caption(f"Reading measurement artifacts from `{context.workspace_directory}`.")
    if not context.has_any_measurement:
        st.info(
            "No bus session measurement has been recorded into this workspace yet. "
            "An attended session writes one; nothing is generated here."
        )
    _render_cadence(context)
    _render_progression(context)


def _render_cadence(context: BusSessionContext) -> None:
    st.subheader("Session cadence")
    measurement = context.cadence
    if isinstance(measurement, UnavailableArtifact):
        _render_unavailable(measurement)
        return
    st.caption(
        f"{measurement.snapshot_count} snapshots, policy `{measurement.policy_id}`, "
        f"status `{measurement.research_status}`. Cross-session linkage is "
        "impossible by construction: the salt is never persisted."
    )
    st.dataframe(
        [{"Measurement": row.label, "Value": row.value} for row in cadence_rows(measurement)],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Road-traffic volume is not available from this source; these are transit vehicles only."
    )


def _render_progression(context: BusSessionContext) -> None:
    st.subheader("Hourly bus progression")
    measurement = context.progression
    if isinstance(measurement, UnavailableArtifact):
        _render_unavailable(measurement)
        return
    rows = progression_rows(measurement)
    st.caption(
        "Median and p90 bus progression speed per UTC hour, each shown with the "
        "segment and vehicle support behind it. An hour with thin support is "
        "reported with that support, never smoothed away."
    )
    st.dataframe(
        [
            {
                "hour (UTC)": row.hour_utc,
                "median speed (m/s)": round(row.speed_mps_median, 3),
                "p90 speed (m/s)": round(row.speed_mps_p90, 3),
                "segments": row.segment_count,
                "vehicles": row.vehicles_contributing,
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Bus progression speed is not road speed, and no DfT comparison is performed on this page."
    )


def _render_unavailable(artifact: UnavailableArtifact) -> None:
    st.warning(f"**{artifact.artifact}** — {artifact.status}. {artifact.reason}")
