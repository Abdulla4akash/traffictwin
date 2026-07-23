"""Candidate MAN-08 Manchester Operations page."""

from __future__ import annotations

import os
from typing import cast

import streamlit as st

from traffictwin.integration.manchester.bods_acquisition import BodsAcquisitionError
from traffictwin.integration.manchester.bods_live import (
    BodsLiveRefreshSummary,
    BodsLiveWorkflowError,
    refresh_bods_live_scene,
)
from traffictwin.integration.manchester.map_layers import (
    ManchesterMapLayerManifest,
    ManchesterMapScene,
    MapMode,
)
from traffictwin.integration.manchester.snapshots import ManchesterSnapshotError
from traffictwin.ui.manchester_operations import (
    LocalManchesterScene,
    assess_live_acquisition_readiness,
    build_manchester_deck,
    layer_summary_rows,
    load_local_manchester_scene,
    parse_bods_bounding_box,
    visible_layer_ids,
)
from traffictwin.ui.state import UiConfig

_MODE_LABELS: dict[MapMode, str] = {
    "historical_replay": "Historical replay",
    "latest_available": "Latest available",
    "live_vehicles": "Live vehicles",
}
_STATUS_COLOURS = {
    "available": "green",
    "partial": "orange",
    "unavailable": "red",
}


@st.cache_data(ttl="30s", max_entries=12, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_scene(workspace_path: str | None, mode: MapMode) -> LocalManchesterScene:
    """Read one bounded local artifact; filtering remains outside the cache."""

    return load_local_manchester_scene(workspace_path, mode)


def render(config: UiConfig) -> None:
    """Render local evidence and the explicit controlled BODS acquisition action."""

    st.title("Manchester Operations")
    st.caption(
        "Explore admitted local evidence by source and scope. Only the explicit live-bus form "
        "can call BODS; ordinary reruns remain local, and buses, surveys, signals, and road "
        "observations are never treated as one traffic total."
    )

    initial_mode: MapMode = "latest_available"
    selected = st.segmented_control(
        "Evidence mode",
        options=tuple(_MODE_LABELS),
        default=initial_mode,
        required=True,
        format_func=lambda value: _MODE_LABELS[cast(MapMode, value)],
        key="manchester_ops_mode",
        width="stretch",
    )
    mode = cast(MapMode, selected or initial_mode)
    workspace = None if config.workspace_path is None else str(config.workspace_path)

    if mode == "live_vehicles":
        _render_live_acquisition(workspace)

    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button(
            "Refresh local evidence",
            icon=":material/refresh:",
            key="manchester_ops_refresh",
        ):
            _load_scene.clear()
            st.rerun()

    loaded = _load_scene(workspace, mode)
    if loaded.scene is None:
        if loaded.status == "rejected":
            st.error(loaded.message, icon=":material/error:")
        else:
            st.info(loaded.message, icon=":material/database:")
        st.caption(f"Evidence state: unavailable · reason: {loaded.reason}")
        _render_disabled_actions("No validated local Manchester scene is available.")
        return

    scene = loaded.scene
    _render_scene_header(scene, loaded)
    available_ids = visible_layer_ids(scene)
    title_by_id = {layer.request.layer_id: layer.request.title for layer in scene.layers}
    chosen = st.pills(
        "Visible evidence layers",
        options=available_ids,
        default=list(available_ids),
        selection_mode="multi",
        format_func=lambda layer_id: title_by_id[str(layer_id)],
        key=f"manchester_ops_layers_{mode}",
        width="stretch",
    )
    chosen_ids = tuple(cast(list[str], chosen or []))

    if chosen_ids:
        st.pydeck_chart(
            build_manchester_deck(scene, chosen_ids),
            width="stretch",
            height=540,
            key=f"manchester_ops_map_{mode}",
        )
    else:
        st.warning(
            "Select at least one available layer to render the offline evidence map.",
            icon=":material/layers_clear:",
        )

    _render_attribution(scene, chosen_ids)
    st.subheader("Source evidence")
    st.caption(
        "Counts below reconcile spatial records inside each source layer; they are not traffic "
        "volumes and are never summed across sources."
    )
    for layer in scene.layers:
        _render_source_card(layer)

    _render_disabled_actions(
        "No accepted MAN-09 observation-to-SUMO mapping or MAN-10 comparison contract exists."
    )

    with st.expander("Evidence details", icon=":material/fact_check:"):
        st.caption(f"Scene fingerprint: {scene.fingerprint()}")
        st.caption(f"Artifact SHA-256: {loaded.artifact_sha256}")
        st.caption(f"Bounded artifact size: {loaded.byte_size} bytes")
        st.dataframe(layer_summary_rows(scene), hide_index=True)
        st.info(
            "Traffic charts remain unavailable because this scene contains spatial layer "
            "manifests, not compatible interval observations. No missing value is filled with "
            "zero.",
            icon=":material/info:",
        )


def _render_live_acquisition(workspace: str | None) -> None:
    """Render one explicit authenticated action; never fetch during an ordinary rerun."""

    api_key = os.getenv("BODS_API_KEY")
    readiness = assess_live_acquisition_readiness(
        workspace,
        api_key_available=bool(api_key),
    )
    with st.form("manchester_bods_live_fetch", border=True, enter_to_submit=False):
        st.markdown("**Fetch latest bus positions**")
        st.caption(
            "One click performs one bounded BODS request, preserves the private response, and "
            "atomically replaces only the local live-vehicle scene. It is not general live road "
            "traffic and does not verify Bee Network membership."
        )
        bounding_box_value = st.text_input(
            "Request bounding box",
            value=os.getenv("TRAFFICTWIN_BODS_BOUNDING_BOX", ""),
            placeholder="min longitude, min latitude, max longitude, max latitude",
            help=(
                "The source request must carry an explicit geographic scope. TrafficTwin does "
                "not invent a Manchester or Greater Manchester boundary."
            ),
            key="manchester_bods_bounding_box",
        )
        st.caption(readiness.message)
        submitted = st.form_submit_button(
            "Fetch latest buses",
            type="primary",
            icon=":material/directions_bus:",
            disabled=not readiness.ready,
            help=None if readiness.ready else readiness.message,
            width="stretch",
        )

    if submitted:
        try:
            bounding_box = parse_bods_bounding_box(bounding_box_value)
        except ValueError as exc:
            st.error(str(exc), icon=":material/location_off:")
        else:
            try:
                with st.spinner("Fetching and validating the latest BODS bus positions..."):
                    refreshed = refresh_bods_live_scene(
                        cast(str, workspace),
                        bounding_box,
                        api_key=cast(str, api_key),
                    )
            except (BodsAcquisitionError, BodsLiveWorkflowError, ManchesterSnapshotError) as exc:
                code = getattr(exc, "code", "LIVE_REFRESH_FAILED")
                st.error(
                    f"The live-bus refresh failed safely ({code}). Existing local evidence was "
                    "not replaced.",
                    icon=":material/error:",
                )
            except (FileExistsError, OSError, ValueError):
                st.error(
                    "The live-bus refresh failed safely. Existing local evidence was not replaced.",
                    icon=":material/error:",
                )
            else:
                st.session_state["manchester_bods_last_refresh"] = (
                    refreshed.summary.canonical_json()
                )
                _load_scene.clear()
                st.success(
                    f"Accepted {refreshed.summary.records_accepted} transit positions: "
                    f"{refreshed.summary.live_vehicle} live and "
                    f"{refreshed.summary.stale} stale.",
                    icon=":material/check_circle:",
                )

    previous = st.session_state.get("manchester_bods_last_refresh")
    if isinstance(previous, str):
        try:
            summary = BodsLiveRefreshSummary.model_validate_json(previous)
        except ValueError:
            del st.session_state["manchester_bods_last_refresh"]
        else:
            with st.container(horizontal=True):
                st.metric("Live buses", summary.live_vehicle, border=True)
                st.metric("Stale bus records", summary.stale, border=True)
                st.metric("Accepted positions", summary.records_accepted, border=True)
            st.caption(
                f"Last controlled fetch: {summary.evaluated_at_utc.isoformat()} · snapshot: "
                f"{summary.snapshot_id} · road-traffic live state: unavailable"
            )


def _render_scene_header(scene: ManchesterMapScene, loaded: LocalManchesterScene) -> None:
    with st.container(horizontal=True):
        st.metric("Evidence state", scene.status.replace("_", " "), border=True)
        st.metric("Available layers", len(visible_layer_ids(scene)), border=True)
        st.metric("Geographic scopes", len(scene.scopes), border=True)
        st.metric("Source", "Validated local artifact", border=True)
    st.caption(
        f"Mode: {_MODE_LABELS[scene.mode]} · local artifact: {loaded.byte_size} bytes · "
        "basemap: disabled · network access: not required"
    )
    if scene.status == "partial":
        st.warning(
            "Some requested evidence is excluded, stale, or unavailable. Source cards retain the "
            "exact reasons.",
            icon=":material/warning:",
        )


def _render_source_card(layer: ManchesterMapLayerManifest) -> None:
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{layer.request.title}**")
            st.badge(
                layer.status.replace("_", " "),
                color=_STATUS_COLOURS[layer.status],
            )
            if layer.stale_badge_visible:
                st.badge("stale cached evidence", color="orange")
        st.caption(
            f"{layer.style.accessible_description}. Source: {layer.request.source}; "
            f"reason: {layer.reason.replace('_', ' ')}."
        )
        with st.container(horizontal=True):
            st.metric("Rendered records", layer.counts.points_rendered, border=True)
            st.metric("Excluded records", layer.counts.points_excluded, border=True)
            st.metric(
                "Freshness",
                (layer.freshness_truth_state or "not applicable").replace("_", " "),
                border=True,
            )
        st.caption(
            f"Snapshot: {layer.request.snapshot_id or 'unavailable'} · "
            f"publication: {layer.request.publication_class.value} · "
            f"licence: {layer.request.licence_id}"
        )


def _render_attribution(scene: ManchesterMapScene, chosen_ids: tuple[str, ...]) -> None:
    selected = [layer for layer in scene.layers if layer.request.layer_id in set(chosen_ids)]
    attributions = sorted({line for layer in selected for line in layer.request.attribution_lines})
    scopes = sorted({point.geographic_scope for layer in selected for point in layer.points})
    st.caption("Attribution: " + (" · ".join(attributions) if attributions else "none selected"))
    st.caption("Visible geographic scopes: " + (", ".join(scopes) if scopes else "none"))


def _render_disabled_actions(reason: str) -> None:
    st.subheader("Research actions")
    with st.container(horizontal=True):
        st.button(
            "Compare with SUMO",
            icon=":material/compare_arrows:",
            disabled=True,
            help=reason,
            key="manchester_ops_compare",
        )
        st.button(
            "Prepare SUMO baseline",
            icon=":material/edit_road:",
            disabled=True,
            help=reason,
            key="manchester_ops_baseline",
        )
