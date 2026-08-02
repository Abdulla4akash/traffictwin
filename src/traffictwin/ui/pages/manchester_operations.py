"""Candidate MAN-08 Manchester Operations page."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Literal, cast

import streamlit as st

from traffictwin.integration.manchester.bods_acquisition import BodsAcquisitionError
from traffictwin.integration.manchester.bods_auto_refresh import bods_auto_refresh_status
from traffictwin.integration.manchester.bods_live import (
    BodsLiveRefreshSummary,
    BodsLiveWorkflowError,
)
from traffictwin.integration.manchester.bods_live_control import (
    BodsLiveControlError,
    bods_live_history_rows,
    coordinated_bods_live_refresh,
    load_bods_live_control_state,
    project_bods_live_scene_for_display,
)
from traffictwin.integration.manchester.bods_retention import (
    BodsRetentionError,
    BodsRetentionPlan,
    apply_bods_retention,
    preview_bods_retention,
)
from traffictwin.integration.manchester.boundary_reference import boundary_attributions
from traffictwin.integration.manchester.dft import DirectionCode
from traffictwin.integration.manchester.dft_acquisition import DftAcquisitionError
from traffictwin.integration.manchester.dft_scene import DftSceneError
from traffictwin.integration.manchester.dft_survey_view import DftVehicleClass
from traffictwin.integration.manchester.live_status_export import build_live_status_export
from traffictwin.integration.manchester.map_layers import (
    ManchesterMapScene,
    MapMode,
)
from traffictwin.integration.manchester.national_highways_acquisition import (
    NationalHighwaysAcquisitionError,
)
from traffictwin.integration.manchester.national_highways_auto_refresh import (
    national_highways_auto_refresh_status,
)
from traffictwin.integration.manchester.national_highways_live import (
    NationalHighwaysLiveError,
    NationalHighwaysRefreshSummary,
    coordinated_national_highways_refresh,
    load_national_highways_control_state,
    national_highways_history_rows,
    project_national_highways_scene_for_display,
)
from traffictwin.integration.manchester.snapshots import ManchesterSnapshotError
from traffictwin.integration.manchester.source_refresh import (
    DftSourceRefreshSummary,
    ManchesterSourceRefreshError,
    TfgmSourceRefreshSummary,
    WebtrisSourceRefreshSummary,
    refresh_dft_historical_rows,
    refresh_tfgm_signal_locations,
    refresh_webtris_site_day,
)
from traffictwin.integration.manchester.spatial import GeographicScope
from traffictwin.integration.manchester.tfgm_acquisition import TfgmAcquisitionError
from traffictwin.integration.manchester.tfgm_scene import TfgmSceneError
from traffictwin.integration.manchester.webtris_acquisition import WebtrisAcquisitionError
from traffictwin.integration.manchester.webtris_scene import WebtrisSceneError
from traffictwin.integration.manchester.webtris_timeseries import WebtrisMeasurementState
from traffictwin.ui.manchester_operations import (
    FilteredManchesterLayer,
    FilteredManchesterScene,
    LocalDftCatalogue,
    LocalDftSurveyOptions,
    LocalDftSurveyView,
    LocalManchesterScene,
    LocalRandyCaseStudy,
    LocalWebtrisCatalogue,
    LocalWebtrisTimeseries,
    SceneFreshnessState,
    accepted_dft_raw_count_options,
    accepted_webtris_daily_options,
    assess_live_acquisition_readiness,
    assess_national_highways_acquisition_readiness,
    build_filtered_manchester_deck,
    dft_snapshot_label,
    dft_survey_chart_rows,
    dft_survey_table_rows,
    filter_manchester_scene,
    filtered_source_summary_rows,
    layer_summary_rows,
    load_local_dft_catalogue,
    load_local_dft_survey_options,
    load_local_dft_survey_view,
    load_local_manchester_scene,
    load_local_randy_case_study,
    load_local_webtris_catalogue,
    load_local_webtris_timeseries,
    parse_bods_bounding_box,
    randy_metric_rows,
    randy_sample_rows,
    scene_filter_options,
    visible_layer_ids,
    webtris_chart_rows,
    webtris_snapshot_label,
)
from traffictwin.ui.map_match_review import (
    REJECT_ALL_SENTINEL,
    candidate_display_rows,
    eligible_candidates_by_point,
    map_match_preflight_for_ui,
    profile_cell_display_rows,
    review_from_selections,
    synthetic_map_match_demo_report,
    synthetic_temporal_profile_demo,
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
_AUDITED_WEBTRIS_SAMPLE_DATE = date(2026, 3, 1)


@st.cache_data(ttl="30s", max_entries=12, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_scene(workspace_path: str | None, mode: MapMode) -> LocalManchesterScene:
    """Read one bounded local artifact; filtering remains outside the cache."""

    return load_local_manchester_scene(workspace_path, mode)


@st.cache_data(ttl="5m", max_entries=4, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_randy_case_study(pack_path: str | None) -> LocalRandyCaseStudy:
    """Verify one optional local VEC-11 pack; never expose its path."""

    return load_local_randy_case_study(pack_path)


@st.cache_data(ttl="30s", max_entries=4, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_webtris_catalogue(workspace_path: str | None) -> LocalWebtrisCatalogue:
    """Verify the bounded local catalogue; ordinary reruns remain offline."""

    return load_local_webtris_catalogue(workspace_path)


@st.cache_data(ttl="30s", max_entries=12, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_webtris_timeseries(
    workspace_path: str | None,
    snapshot_id: str,
    measurement_states: tuple[WebtrisMeasurementState, ...],
) -> LocalWebtrisTimeseries:
    """Rebuild one accepted local site-day behind a bounded cache."""

    return load_local_webtris_timeseries(workspace_path, snapshot_id, measurement_states)


@st.cache_data(ttl="30s", max_entries=4, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_dft_catalogue(workspace_path: str | None) -> LocalDftCatalogue:
    """Verify the bounded local DfT catalogue; ordinary reruns remain offline."""

    return load_local_dft_catalogue(workspace_path)


@st.cache_data(ttl="30s", max_entries=12, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_dft_survey_options(
    workspace_path: str | None,
    snapshot_id: str,
) -> LocalDftSurveyOptions:
    """Cache the exact filter inventory for one accepted DfT snapshot."""

    return load_local_dft_survey_options(workspace_path, snapshot_id)


@st.cache_data(ttl="30s", max_entries=24, show_spinner=False)  # type: ignore[untyped-decorator]
def _load_dft_survey_view(
    workspace_path: str | None,
    snapshot_id: str,
    count_point_id: int,
    directions: tuple[DirectionCode, ...],
    count_date: date,
    hours: tuple[int, ...],
    vehicle_class: DftVehicleClass,
) -> LocalDftSurveyView:
    """Cache one small explicit DfT survey selection, never the full source body."""

    return load_local_dft_survey_view(
        workspace_path,
        snapshot_id,
        count_point_id=count_point_id,
        directions=directions,
        count_date=count_date,
        hours=hours,
        vehicle_class=vehicle_class,
    )


@st.fragment(run_every="30s")  # type: ignore[untyped-decorator]
def _watch_live_overlays(workspace: str | None) -> None:
    """Rerender local evidence when either process worker publishes a new overlay."""

    if workspace is None:
        return
    highways_worker = national_highways_auto_refresh_status(workspace)
    bods_worker = bods_auto_refresh_status(workspace)
    if highways_worker is None and bods_worker is None:
        return
    highways_marker: tuple[str | None, str, str | None] | None = None
    bods_marker: tuple[str | None, str, str | None] | None = None
    try:
        if highways_worker is not None:
            state = load_national_highways_control_state(workspace)
            highways_marker = (
                None
                if state.last_attempt_at_utc is None
                else state.last_attempt_at_utc.isoformat(),
                state.last_attempt_status,
                state.last_failure_code,
            )
        if bods_worker is not None:
            bods_state = load_bods_live_control_state(workspace)
            bods_marker = (
                None
                if bods_state.last_attempt_at_utc is None
                else bods_state.last_attempt_at_utc.isoformat(),
                bods_state.last_attempt_status,
                bods_state.last_failure_code,
            )
    except (BodsLiveControlError, NationalHighwaysLiveError, OSError, ValueError):
        return
    marker = (highways_marker, bods_marker)
    key = "_live_auto_refresh_marker"
    previous = st.session_state.get(key)
    st.session_state[key] = marker
    if previous is not None and previous != marker:
        _clear_manchester_caches()
        st.rerun()


def _render_live_status_download(workspace: str | None) -> None:
    """Offer a local aggregate manifest without exposing private source records."""

    with st.expander("Metadata-only live status", icon=":material/download:"):
        st.caption(
            "This local export contains source states, aggregate record counts, scope, and "
            "attribution only. It excludes coordinates, vehicle identifiers, API credentials, "
            "raw snapshots, and permission to host the metadata or a public live scene."
        )
        if workspace is None:
            st.caption("Unavailable: configure a v0.7 workspace first.")
            return
        try:
            manifest = build_live_status_export(
                generated_at_utc=datetime.now(UTC),
                bods=load_bods_live_control_state(workspace),
                national_highways=load_national_highways_control_state(workspace),
            )
        except (BodsLiveControlError, NationalHighwaysLiveError, ValueError):
            st.caption("Unavailable: one or more local control-state records failed validation.")
            return
        st.download_button(
            "Download live-status metadata",
            data=f"{manifest.canonical_json()}\n",
            file_name="manchester-live-status.json",
            mime="application/json",
            icon=":material/download:",
            width="stretch",
        )


def render(config: UiConfig) -> None:
    """Render local evidence and explicit controlled source acquisition actions."""

    st.title("Manchester Operations")
    st.caption(
        "Explore admitted local evidence by source and scope. A configured server refreshes the "
        "BODS bus layer every minute and the three National Highways operational layers every "
        "five minutes; page reruns remain local, and buses, surveys, signals, and road "
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
    _watch_live_overlays(workspace)

    if mode == "historical_replay":
        _render_dft_source_refresh(workspace)
    elif mode == "latest_available":
        _render_latest_source_refresh(workspace)
    else:
        _render_live_acquisition(workspace)

    _render_live_status_download(workspace)

    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button(
            "Refresh local evidence",
            icon=":material/refresh:",
            key="manchester_ops_refresh",
        ):
            _load_scene.clear()
            _load_dft_catalogue.clear()
            _load_dft_survey_options.clear()
            _load_dft_survey_view.clear()
            _load_webtris_catalogue.clear()
            _load_webtris_timeseries.clear()
            st.rerun()

    loaded = _load_scene(workspace, mode)
    if loaded.scene is None:
        if loaded.status == "rejected":
            st.error(loaded.message, icon=":material/error:")
        else:
            st.info(loaded.message, icon=":material/database:")
        st.caption(f"Evidence state: unavailable · reason: {loaded.reason}")
        if mode == "historical_replay":
            _render_dft_survey_history(workspace)
            _render_webtris_history(workspace)
        elif mode == "latest_available":
            _render_webtris_history(workspace)
        _render_randy_case_study()
        _render_disabled_actions("No validated local Manchester scene is available.")
        return

    scene = loaded.scene
    if mode in {"latest_available", "live_vehicles"}:
        try:
            national_highways_state = (
                None if workspace is None else load_national_highways_control_state(workspace)
            )
            source_outage = (
                national_highways_state is not None
                and national_highways_state.last_attempt_status == "failed"
            )
            scene = project_national_highways_scene_for_display(
                scene,
                evaluated_at_utc=datetime.now(UTC),
                source_outage=source_outage,
            )
        except (NationalHighwaysLiveError, ValueError):
            st.warning(
                "The National Highways overlay could not be re-evaluated safely. Other local "
                "source layers remain available.",
                icon=":material/warning:",
            )
        else:
            if any(
                layer.request.source.startswith("national_highways_")
                and layer.freshness_truth_state == "stale"
                for layer in scene.layers
            ):
                st.warning(
                    "The cached National Highways operational snapshot is stale or the latest "
                    "refresh failed. It remains visible for historical context and is not "
                    "relabeled as current.",
                    icon=":material/history:",
                )
    if mode == "live_vehicles":
        try:
            scene = project_bods_live_scene_for_display(
                scene,
                evaluated_at_utc=datetime.now(UTC),
            )
        except (BodsLiveControlError, ValueError):
            st.error(
                "The cached live scene could not be re-evaluated safely. Its stored evidence was "
                "not changed.",
                icon=":material/error:",
            )
            _render_disabled_actions("The live scene freshness projection was rejected.")
            return
        if any(layer.freshness_truth_state == "stale" for layer in scene.layers):
            st.warning(
                "This is a cached local bus scene. Its source-time freshness has expired, so all "
                "affected positions are displayed as stale until you run another controlled fetch.",
                icon=":material/history:",
            )
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
    chosen_ids = tuple(
        dict.fromkeys(
            layer_id for layer_id in cast(list[str], chosen or []) if layer_id in available_ids
        )
    )

    if chosen_ids:
        options = scene_filter_options(scene, chosen_ids)
        filter_key = _filter_widget_key(
            mode,
            chosen_ids,
            options.geographic_scopes,
            options.freshness_states,
        )
        st.caption(
            "Display filters only: they do not alter accepted evidence, combine source counts, "
            "or fill missing records."
        )
        with st.container(horizontal=True):
            selected_scopes = st.pills(
                "Geographic scope",
                options=options.geographic_scopes,
                default=list(options.geographic_scopes),
                selection_mode="multi",
                format_func=_human_label,
                key=f"manchester_ops_scope_{filter_key}",
                width="stretch",
            )
            selected_freshness = st.pills(
                "Freshness state",
                options=options.freshness_states,
                default=list(options.freshness_states),
                selection_mode="multi",
                format_func=_human_label,
                key=f"manchester_ops_freshness_{filter_key}",
                width="stretch",
            )
        filtered = filter_manchester_scene(
            scene,
            chosen_ids,
            geographic_scopes=tuple(cast(list[GeographicScope], selected_scopes or [])),
            freshness_states=tuple(cast(list[SceneFreshnessState], selected_freshness or [])),
        )
    else:
        filtered = filter_manchester_scene(
            scene,
            (),
            geographic_scopes=(),
            freshness_states=(),
        )

    if filtered.has_displayed_points:
        st.pydeck_chart(
            build_filtered_manchester_deck(filtered),
            width="stretch",
            height=540,
            key=f"manchester_ops_map_{mode}",
        )
    elif chosen_ids:
        st.warning(
            "The selected display filters contain no admitted map points. Change or clear the "
            "scope and freshness filters; the source evidence remains unchanged.",
            icon=":material/filter_alt_off:",
        )
    else:
        st.warning(
            "Select at least one available layer to render the offline evidence map.",
            icon=":material/layers_clear:",
        )

    _render_attribution(filtered)
    st.subheader("Source evidence")
    st.caption(
        "Counts below reconcile spatial records inside each source layer; they are not traffic "
        "volumes and are never summed across sources."
    )
    source_rows = filtered_source_summary_rows(filtered)
    if source_rows:
        st.dataframe(source_rows, hide_index=True, width="stretch")
    else:
        st.caption("Select an evidence layer to inspect its separate source reconciliation.")
    for layer in filtered.layers:
        _render_source_card(layer)

    if mode == "historical_replay":
        _render_dft_survey_history(workspace)
        _render_webtris_history(workspace)
    elif mode == "latest_available":
        _render_webtris_history(workspace)

    _render_randy_case_study()
    _render_disabled_actions(
        "No accepted MAN-09 observation-to-SUMO mapping or MAN-10 comparison contract exists."
    )

    with st.expander("Evidence details", icon=":material/fact_check:"):
        st.caption(f"Scene fingerprint: {scene.fingerprint()}")
        st.caption(f"Artifact SHA-256: {loaded.artifact_sha256}")
        st.caption(f"Bounded artifact size: {loaded.byte_size} bytes")
        st.dataframe(layer_summary_rows(scene), hide_index=True)
        st.info(
            "The map scene itself contains spatial layer manifests, not interval observations. "
            "Any separate WebTRIS charts above are rebuilt from their own accepted daily "
            "snapshots. No missing value is filled with zero.",
            icon=":material/info:",
        )


def _clear_manchester_caches() -> None:
    """Invalidate only bounded local Manchester reads after an explicit refresh."""

    _load_scene.clear()
    _load_dft_catalogue.clear()
    _load_dft_survey_options.clear()
    _load_dft_survey_view.clear()
    _load_webtris_catalogue.clear()
    _load_webtris_timeseries.clear()


def _render_latest_source_refresh(workspace: str | None) -> None:
    """Expose explicit WebTRIS and TfGM refreshes without claiming either is live."""

    st.subheader("Refresh latest available source evidence")
    st.caption(
        "WebTRIS supplies selected strategic-road site/day observations. TfGM supplies static "
        "traffic-signal locations. Neither source is live city-road telemetry; each action "
        "preserves exact source bytes and updates only its own local map layer."
    )
    webtris_col, tfgm_col = st.columns(2, gap="medium")
    with webtris_col:
        default_report_date = _default_webtris_report_date(workspace)
        with st.form("manchester_webtris_refresh", border=True, enter_to_submit=False):
            st.markdown("**WebTRIS strategic-road site/day**")
            site_id = st.text_input(
                "WebTRIS site ID",
                value="34",
                help=(
                    "Site 34 is the audited Manchester-area M56 example; enter another "
                    "numeric site ID explicitly."
                ),
                key="manchester_webtris_site_id",
            )
            selected_date = st.date_input(
                "Source report date",
                value=default_report_date,
                max_value=datetime.now(UTC).date(),
                help=(
                    "The source clock timezone is undocumented, so TrafficTwin retains this "
                    "as a source date. The initial default is the audited working day; choose "
                    "another day explicitly to test its availability."
                ),
                key="manchester_webtris_report_date",
            )
            webtris_submitted = st.form_submit_button(
                "Fetch site, report, and quality",
                type="primary",
                icon=":material/route:",
                disabled=workspace is None,
                help=(
                    None if workspace is not None else "Configure an isolated v0.7 workspace first."
                ),
                width="stretch",
            )
        if webtris_submitted:
            if not site_id.isdigit() or site_id.startswith("0"):
                st.error("Enter a positive numeric WebTRIS site ID.", icon=":material/error:")
            else:
                try:
                    with st.spinner("Fetching and validating the selected WebTRIS site/day..."):
                        refreshed = refresh_webtris_site_day(
                            cast(str, workspace),
                            site_id=site_id,
                            report_date=cast(date, selected_date),
                        )
                except (
                    WebtrisAcquisitionError,
                    WebtrisSceneError,
                    ManchesterSourceRefreshError,
                    ManchesterSnapshotError,
                    OSError,
                    ValueError,
                ) as exc:
                    _source_refresh_error("WebTRIS", exc)
                else:
                    st.session_state["manchester_webtris_last_refresh"] = refreshed.canonical_json()
                    _clear_manchester_caches()
                    st.success(
                        f"Accepted site {refreshed.site_id} and "
                        f"{refreshed.intervals_accepted} daily intervals.",
                        icon=":material/check_circle:",
                    )
        _render_webtris_refresh_summary()

    with tfgm_col:
        with st.form("manchester_tfgm_refresh", border=True, enter_to_submit=False):
            st.markdown("**TfGM traffic-signal locations**")
            st.caption(
                "Downloads the audited official archive and maps static signal references. "
                "It cannot show phase, timing, queues, incidents, or live signal state."
            )
            tfgm_submitted = st.form_submit_button(
                "Fetch signal locations",
                type="primary",
                icon=":material/traffic:",
                disabled=workspace is None,
                help=(
                    None if workspace is not None else "Configure an isolated v0.7 workspace first."
                ),
                width="stretch",
            )
        if tfgm_submitted:
            try:
                with st.spinner("Fetching and validating TfGM signal locations..."):
                    refreshed_tfgm = refresh_tfgm_signal_locations(cast(str, workspace))
            except (
                TfgmAcquisitionError,
                TfgmSceneError,
                ManchesterSourceRefreshError,
                ManchesterSnapshotError,
                OSError,
                ValueError,
            ) as exc:
                _source_refresh_error("TfGM", exc)
            else:
                st.session_state["manchester_tfgm_last_refresh"] = refreshed_tfgm.canonical_json()
                _clear_manchester_caches()
                st.success(
                    f"Accepted {refreshed_tfgm.records_accepted} static signal locations.",
                    icon=":material/check_circle:",
                )
        _render_tfgm_refresh_summary()
    _render_national_highways_acquisition(workspace, key_suffix="latest")


def _render_dft_source_refresh(workspace: str | None) -> None:
    """Expose selected historical DfT rows through one explicit bounded action."""

    with st.expander(
        "Import selected DfT historical evidence",
        icon=":material/history:",
    ):
        st.caption(
            "Fetch one exact Manchester raw-count row, one count-point reference row, and one "
            "AADF row. These are historical survey/statistical records—not live traffic—and "
            "no source hour is promoted to UTC."
        )
        with st.form("manchester_dft_refresh", border=True, enter_to_submit=False):
            raw_col, point_col, aadf_col = st.columns(3, gap="small")
            with raw_col:
                raw_count_id = st.number_input(
                    "Raw-count row ID",
                    min_value=1,
                    value=43177,
                    step=1,
                    key="manchester_dft_raw_count_id",
                )
            with point_col:
                count_point_id = st.number_input(
                    "Count-point row ID",
                    min_value=1,
                    value=6046,
                    step=1,
                    key="manchester_dft_count_point_id",
                )
            with aadf_col:
                aadf_id = st.number_input(
                    "AADF row ID",
                    min_value=1,
                    value=9219,
                    step=1,
                    key="manchester_dft_aadf_id",
                )
            submitted = st.form_submit_button(
                "Fetch selected historical rows",
                type="primary",
                icon=":material/download:",
                disabled=workspace is None,
                help=(
                    None if workspace is not None else "Configure an isolated v0.7 workspace first."
                ),
                width="stretch",
            )
        if submitted:
            try:
                with st.spinner("Fetching and validating the selected DfT rows..."):
                    refreshed = refresh_dft_historical_rows(
                        cast(str, workspace),
                        raw_count_row_id=int(raw_count_id),
                        count_point_row_id=int(count_point_id),
                        aadf_row_id=int(aadf_id),
                    )
            except (
                DftAcquisitionError,
                DftSceneError,
                ManchesterSourceRefreshError,
                ManchesterSnapshotError,
                OSError,
                ValueError,
            ) as exc:
                _source_refresh_error("DfT", exc)
            else:
                st.session_state["manchester_dft_last_refresh"] = refreshed.canonical_json()
                _clear_manchester_caches()
                st.success(
                    "Accepted the selected raw-count, count-point, and AADF evidence.",
                    icon=":material/check_circle:",
                )
        _render_dft_refresh_summary()


def _source_refresh_error(source: str, exc: Exception) -> None:
    code = getattr(exc, "code", "SOURCE_REFRESH_FAILED")
    st.error(
        f"The {source} refresh failed safely ({code}). Existing local map evidence was not "
        "replaced; any quarantined source bytes remain available for audit.",
        icon=":material/error:",
    )


def _render_webtris_refresh_summary() -> None:
    value = st.session_state.get("manchester_webtris_last_refresh")
    if not isinstance(value, str):
        return
    try:
        summary = WebtrisSourceRefreshSummary.model_validate_json(value)
    except ValueError:
        del st.session_state["manchester_webtris_last_refresh"]
        return
    st.caption(
        f"Last accepted: {summary.site_name} · {summary.report_date.isoformat()} · "
        f"{summary.intervals_missing} missing intervals · parser: "
        f"{summary.daily_parser_status.replace('_', ' ')} · live road state unavailable"
    )
    if summary.daily_warning_codes:
        st.caption("Source warnings retained: " + ", ".join(summary.daily_warning_codes))


def _default_webtris_report_date(workspace: str | None) -> date:
    """Prefer the newest already accepted source date without making a network request."""

    catalogue = _load_webtris_catalogue(workspace)
    if catalogue.catalogue is not None:
        options = accepted_webtris_daily_options(catalogue.catalogue)
        if options and options[0].report_date is not None:
            return options[0].report_date
    return min(datetime.now(UTC).date() - timedelta(days=1), _AUDITED_WEBTRIS_SAMPLE_DATE)


def _render_tfgm_refresh_summary() -> None:
    value = st.session_state.get("manchester_tfgm_last_refresh")
    if not isinstance(value, str):
        return
    try:
        summary = TfgmSourceRefreshSummary.model_validate_json(value)
    except ValueError:
        del st.session_state["manchester_tfgm_last_refresh"]
        return
    st.caption(
        f"Last accepted: {summary.spatial_admitted} mapped locations · "
        f"{summary.spatial_excluded} spatial exclusions · live state unavailable"
    )


def _render_dft_refresh_summary() -> None:
    value = st.session_state.get("manchester_dft_last_refresh")
    if not isinstance(value, str):
        return
    try:
        summary = DftSourceRefreshSummary.model_validate_json(value)
    except ValueError:
        del st.session_state["manchester_dft_last_refresh"]
        return
    st.caption(
        f"Last accepted: {summary.raw_count_records} survey row · "
        f"{summary.count_point_records} reference row · {summary.aadf_records} AADF row · "
        "live road state unavailable"
    )


def _render_dft_survey_history(workspace: str | None) -> None:
    """Render accepted DfT survey rows through the tested source-specific view."""

    st.subheader("DfT historical survey counts")
    st.caption(
        "Inspect one exact accepted raw-count snapshot. These are dated survey rows with an "
        "undocumented local-clock hour—not live traffic, a continuous time series, measured "
        "speed, AADF demand, or a SUMO input."
    )
    loaded_catalogue = _load_dft_catalogue(workspace)
    if loaded_catalogue.status == "rejected":
        st.error(loaded_catalogue.message, icon=":material/gpp_bad:")
        return
    if loaded_catalogue.catalogue is None:
        st.info(loaded_catalogue.message, icon=":material/database:")
        return
    snapshots = accepted_dft_raw_count_options(loaded_catalogue.catalogue)
    if not snapshots:
        st.info(loaded_catalogue.message, icon=":material/database:")
        return

    by_id = {item.snapshot_id: item for item in snapshots}
    selected_id = st.selectbox(
        "Accepted DfT raw-count snapshot",
        options=tuple(by_id),
        format_func=lambda snapshot_id: dft_snapshot_label(by_id[str(snapshot_id)]),
        key="manchester_ops_dft_snapshot",
        help=(
            "Only verified accepted raw-count snapshots are listed; AADF and reference-only "
            "data are excluded."
        ),
        width="stretch",
    )
    if selected_id is None:
        return
    snapshot_id = str(selected_id)
    loaded_options = _load_dft_survey_options(workspace, snapshot_id)
    if loaded_options.status == "rejected" or loaded_options.options is None:
        st.error(loaded_options.message, icon=":material/gpp_bad:")
        return
    options = loaded_options.options
    if (
        not options.count_point_ids
        or not options.count_dates
        or not options.directions
        or not options.hours
        or not options.vehicle_classes_with_any_value
    ):
        st.info(
            "The accepted DfT snapshot contains no complete filter inventory to inspect.",
            icon=":material/filter_alt_off:",
        )
        return

    widget_scope = snapshot_id[-12:]
    with st.container(horizontal=True):
        selected_point = st.selectbox(
            "Count point",
            options=options.count_point_ids,
            key=f"manchester_ops_dft_point_{widget_scope}",
            width="stretch",
        )
        selected_date = st.selectbox(
            "Survey date",
            options=options.count_dates,
            format_func=lambda value: value.isoformat(),
            key=f"manchester_ops_dft_date_{widget_scope}",
            width="stretch",
        )
        selected_class = st.selectbox(
            "Vehicle class",
            options=options.vehicle_classes_with_any_value,
            format_func=lambda value: _human_label(value),
            key=f"manchester_ops_dft_class_{widget_scope}",
            width="stretch",
        )
    selected_directions = st.pills(
        "Direction",
        options=options.directions,
        default=options.directions,
        selection_mode="multi",
        key=f"manchester_ops_dft_direction_{widget_scope}",
        help="Directions are exact source codes and are not inferred from road names.",
    )
    selected_hours = st.multiselect(
        "Local-clock hour labels",
        options=options.hours,
        default=options.hours,
        format_func=lambda value: f"{int(value):02d}:00",
        key=f"manchester_ops_dft_hours_{widget_scope}",
        help="The source timezone and exact interval duration are undocumented.",
        width="stretch",
    )
    directions = tuple(sorted(cast(list[DirectionCode], selected_directions or [])))
    hours = tuple(sorted(cast(list[int], selected_hours or [])))
    if (
        selected_point is None
        or selected_date is None
        or selected_class is None
        or not directions
        or not hours
    ):
        st.warning(
            "Select one count point, one survey date, one vehicle class, and at least one "
            "direction and hour.",
            icon=":material/filter_alt_off:",
        )
        return

    loaded = _load_dft_survey_view(
        workspace,
        snapshot_id,
        int(selected_point),
        directions,
        cast(date, selected_date),
        hours,
        cast(DftVehicleClass, selected_class),
    )
    if loaded.status == "rejected" or loaded.view is None:
        st.error(loaded.message, icon=":material/gpp_bad:")
        return
    view = loaded.view
    with st.container(horizontal=True):
        st.metric("Selected survey rows", view.counts.selected_records, border=True)
        st.metric("Values present", view.counts.values_present, border=True)
        st.metric("Values missing", view.counts.values_missing, border=True)
        st.metric("Source rows", view.counts.source_records, border=True)
    if not view.rows:
        st.warning(
            "No source row matches this exact filter intersection. TrafficTwin did not "
            "substitute another survey or emit a zero.",
            icon=":material/search_off:",
        )
    else:
        chart_rows = dft_survey_chart_rows(view)
        if any(row["Count"] is not None for row in chart_rows):
            st.bar_chart(
                chart_rows,
                x="Source survey hour",
                y="Count",
                color="Direction",
                x_label="Source date and local-clock hour (timezone undeclared)",
                y_label=_human_label(view.query.vehicle_class),
                stack=False,
                sort=False,
                width="stretch",
                height=300,
            )
        else:
            st.caption("Every selected source value is missing; no zero-valued bars are drawn.")
        st.dataframe(
            dft_survey_table_rows(view),
            hide_index=True,
            width="stretch",
        )
    selected_summary = by_id[snapshot_id]
    st.caption(
        f"Snapshot: {snapshot_id} · licence: {selected_summary.licence_id} · attribution: "
        f"{selected_summary.attribution_text} · query fingerprint: {view.query_fingerprint}"
    )
    st.caption(
        "Interpretation boundary: discrete source survey rows only; no aggregation, UTC "
        "projection, continuous-series claim, measured speed, AADF use, or canonical replay."
    )


def _render_webtris_history(workspace: str | None) -> None:
    """Render local MAN-03 daily evidence through the tested MAN-08 service."""

    st.subheader("WebTRIS historical intervals")
    st.caption(
        "Select one exact accepted site-day. Values are National Highways strategic-road "
        "observations with source clock strings; they are not live, UTC-normalised, city-wide, "
        "or aggregated across sites."
    )
    loaded_catalogue = _load_webtris_catalogue(workspace)
    if loaded_catalogue.status == "rejected":
        st.error(loaded_catalogue.message, icon=":material/gpp_bad:")
        return
    if loaded_catalogue.catalogue is None:
        st.info(loaded_catalogue.message, icon=":material/database:")
        return
    options = accepted_webtris_daily_options(loaded_catalogue.catalogue)
    if not options:
        st.info(loaded_catalogue.message, icon=":material/database:")
        return

    by_id = {item.snapshot_id: item for item in options}
    selected_id = st.selectbox(
        "Accepted WebTRIS site-day",
        options=tuple(by_id),
        format_func=lambda snapshot_id: webtris_snapshot_label(by_id[str(snapshot_id)]),
        key="manchester_ops_webtris_snapshot",
        help=(
            "Each option is one exact accepted snapshot; conflicting site-day versions are "
            "not merged."
        ),
        width="stretch",
    )
    selected_states = st.pills(
        "Measurement state",
        options=("observed", "missing"),
        default=("observed", "missing"),
        selection_mode="multi",
        format_func=_human_label,
        key="manchester_ops_webtris_measurement_states",
        help="Missing source intervals remain chart gaps and are never replaced with zero.",
    )
    states = tuple(sorted(cast(list[WebtrisMeasurementState], selected_states or [])))
    if selected_id is None or not states:
        st.warning(
            "Select an accepted site-day and at least one measurement state.",
            icon=":material/filter_alt_off:",
        )
        return

    loaded = _load_webtris_timeseries(workspace, str(selected_id), states)
    if loaded.status == "rejected" or loaded.result is None:
        st.error(loaded.message, icon=":material/gpp_bad:")
        return
    result = loaded.result
    input_item = result.inputs[0]
    with st.container(horizontal=True):
        st.metric("Admitted intervals", result.counts.rows_admitted, border=True)
        st.metric(
            "Admitted missing intervals",
            result.counts.rows_missing_measurement_admitted,
            border=True,
        )
        st.metric("Filtered intervals", result.counts.rows_excluded, border=True)
        st.metric("Source pages", result.counts.input_pages_total, border=True)
    st.caption(
        f"Site {input_item.site_id}: {input_item.site_name} · source date: "
        f"{input_item.report_date.isoformat()} · parser: "
        f"{input_item.daily_parser_status.value.replace('_', ' ')} · availability percentage: "
        "unreported on receipt-free replay"
    )

    rows = webtris_chart_rows(result)
    if any(row["Volume"] is not None for row in rows):
        st.line_chart(
            rows,
            x="Source interval",
            y="Volume",
            x_label="Source date and interval ending (timezone undeclared)",
            y_label="Vehicles per reported interval",
            width="stretch",
            height=280,
        )
    else:
        st.caption("No observed volume values pass the selected measurement-state filter.")
    if any(row["Average speed (mph)"] is not None for row in rows):
        st.line_chart(
            rows,
            x="Source interval",
            y="Average speed (mph)",
            x_label="Source date and interval ending (timezone undeclared)",
            y_label="Average speed (mph)",
            width="stretch",
            height=280,
        )
    else:
        st.caption("No observed speed values pass the selected measurement-state filter.")
    st.caption(
        f"Snapshot: {input_item.daily_snapshot_id} · licence: {result.licence_id} · "
        f"Attribution: {result.attribution_text} · result fingerprint: {result.fingerprint()}"
    )


def _render_live_acquisition(workspace: str | None) -> None:
    """Render automatic live status and explicit authenticated fallbacks."""

    _render_national_highways_acquisition(workspace, key_suffix="live")
    api_key = os.getenv("BODS_API_KEY")
    readiness = assess_live_acquisition_readiness(
        workspace,
        api_key_available=bool(api_key),
    )
    auto_status = None if workspace is None else bods_auto_refresh_status(workspace)
    auto_error = st.session_state.get("_bods_auto_refresh_error")
    if auto_status is not None and auto_status.running:
        st.success(
            f"Automatic BODS refresh active every {auto_status.interval_seconds} seconds while "
            "this server process is running. Provider-reported old positions remain stale; the "
            "manual action remains available as a fallback.",
            icon=":material/autorenew:",
        )
    elif isinstance(auto_error, str):
        st.warning(
            f"Automatic BODS refresh could not start safely ({auto_error}); use the manual "
            "fallback after correcting the server configuration.",
            icon=":material/warning:",
        )
    else:
        st.caption(
            "Automatic BODS refresh is inactive: start the app with a validated v0.7 workspace, "
            "BODS_API_KEY, and TRAFFICTWIN_BODS_BOUNDING_BOX, or use the manual fallback."
        )
    with st.form("manchester_bods_live_fetch", border=True, enter_to_submit=False):
        st.markdown("**Refresh bus positions now**")
        st.caption(
            "The fallback performs one bounded BODS request, preserves the private response, and "
            "atomically replaces only the local live-vehicle scene. Exact OperatorRef matching "
            "separates live-feed-verified Bee Network operators from other or unknown operators; "
            "the result is bus evidence, not general live road traffic."
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
                    controlled = coordinated_bods_live_refresh(
                        cast(str, workspace),
                        bounding_box,
                        api_key=cast(str, api_key),
                    )
                    refreshed = controlled.refresh
            except (
                BodsAcquisitionError,
                BodsLiveControlError,
                BodsLiveWorkflowError,
                ManchesterSnapshotError,
            ) as exc:
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
                    f"{refreshed.summary.stale} stale; "
                    f"{refreshed.summary.bee_network_franchised} matched the verified Bee "
                    "Network operator policy.",
                    icon=":material/check_circle:",
                )

    summary: BodsLiveRefreshSummary | None = None
    previous = st.session_state.get("manchester_bods_last_refresh")
    if isinstance(previous, str):
        try:
            summary = BodsLiveRefreshSummary.model_validate_json(previous)
        except ValueError:
            del st.session_state["manchester_bods_last_refresh"]
            summary = None
    if summary is None and workspace is not None:
        try:
            summary = load_bods_live_control_state(workspace).latest_success
        except (BodsLiveControlError, OSError, ValueError):
            summary = None
    if summary is not None:
        with st.container(horizontal=True):
            st.metric(
                "Bee Network positions",
                summary.bee_network_franchised,
                border=True,
            )
            st.metric(
                "Other or unknown operators",
                summary.non_franchised_or_unknown,
                border=True,
            )
            st.metric("Live at fetch", summary.live_vehicle, border=True)
            st.metric("Source-stale at fetch", summary.stale, border=True)
        st.caption(
            f"Last controlled fetch: {summary.evaluated_at_utc.isoformat()} · snapshot: "
            f"{summary.snapshot_id} · membership policy: "
            f"{summary.bee_network_policy_version} · one candidate operator remains pending · "
            "the map re-evaluates source timestamps after fetch · road-traffic live state: "
            "unavailable"
        )
    _render_bods_live_history(workspace)
    _render_bods_retention(workspace)


def _render_national_highways_acquisition(
    workspace: str | None,
    *,
    key_suffix: str,
) -> None:
    """Render automatic status plus the manual three-product fallback."""

    subscription_key = os.getenv("NATIONAL_HIGHWAYS_API_KEY")
    readiness = assess_national_highways_acquisition_readiness(
        workspace,
        subscription_key_available=bool(subscription_key),
    )
    with st.expander(
        "National Highways operational feeds",
        expanded=key_suffix == "live",
        icon=":material/road:",
    ):
        st.caption(
            "The server refreshes three bounded products together: closures/incidents, imposed "
            "temporary speed restrictions, and digital VMS status. Coverage is the Strategic "
            "Road Network inside a broad Manchester study envelope—not all city roads, measured "
            "traffic speed, traffic volume, or congestion."
        )
        auto_status = (
            None if workspace is None else national_highways_auto_refresh_status(workspace)
        )
        auto_error = st.session_state.get("_national_highways_auto_refresh_error")
        if auto_status is not None and auto_status.running:
            st.success(
                f"Automatic refresh active every {auto_status.interval_seconds / 60:g} minutes "
                "while this server process is running. The manual action remains available as "
                "a fallback.",
                icon=":material/autorenew:",
            )
        elif isinstance(auto_error, str):
            st.warning(
                f"Automatic refresh could not start safely ({auto_error}); use the manual "
                "fallback after correcting the server configuration.",
                icon=":material/warning:",
            )
        else:
            st.caption(
                "Automatic refresh is inactive: start the app with a validated v0.7 workspace "
                "and NATIONAL_HIGHWAYS_API_KEY, or use the manual fallback."
            )
        with st.form(
            f"manchester_national_highways_refresh_{key_suffix}",
            border=True,
            enter_to_submit=False,
        ):
            event_type = st.segmented_control(
                "Operational event type",
                options=("unplanned", "planned"),
                default="unplanned",
                format_func=lambda value: str(value).replace("_", " ").title(),
                key=f"manchester_national_highways_event_type_{key_suffix}",
                width="stretch",
            )
            st.caption(
                "Study envelope: 53.30–53.70 latitude, −2.60–−1.90 longitude · "
                "default automatic unplanned refresh every 5 minutes · "
                "provider limit 10 calls/minute · "
                "TrafficTwin uses 3 calls per refresh"
            )
            st.caption(readiness.message)
            submitted = st.form_submit_button(
                "Refresh all three operational feeds",
                type="primary",
                icon=":material/sync:",
                disabled=not readiness.ready,
                help=None if readiness.ready else readiness.message,
                width="stretch",
            )
        if submitted:
            try:
                with st.spinner("Fetching, quarantining, and validating all three feeds..."):
                    summary = coordinated_national_highways_refresh(
                        cast(str, workspace),
                        subscription_key=cast(str, subscription_key),
                        event_type=cast(Literal["planned", "unplanned"], event_type),
                    )
            except (
                NationalHighwaysAcquisitionError,
                NationalHighwaysLiveError,
                ManchesterSnapshotError,
                OSError,
                ValueError,
            ) as exc:
                code = getattr(exc, "code", "NATIONAL_HIGHWAYS_REFRESH_FAILED")
                st.error(
                    f"The operational refresh failed safely ({code}). Existing accepted scenes "
                    "remain available and will be labelled stale.",
                    icon=":material/error:",
                )
            else:
                st.session_state["manchester_national_highways_last_refresh"] = (
                    summary.canonical_json()
                )
                _clear_manchester_caches()
                st.success(
                    f"Accepted {summary.total_records_accepted} in-envelope operational records "
                    "across three source-separated layers.",
                    icon=":material/check_circle:",
                )
        _render_national_highways_summary(workspace)


def _render_national_highways_summary(workspace: str | None) -> None:
    value = st.session_state.get("manchester_national_highways_last_refresh")
    summary: NationalHighwaysRefreshSummary | None = None
    if isinstance(value, str):
        try:
            summary = NationalHighwaysRefreshSummary.model_validate_json(value)
        except ValueError:
            del st.session_state["manchester_national_highways_last_refresh"]
    if summary is not None:
        counts = {item.product: item.records_accepted for item in summary.products}
        with st.container(horizontal=True):
            st.metric("Closures / incidents", counts["closures"], border=True)
            st.metric("Temporary restrictions", counts["speed_limits"], border=True)
            st.metric("Digital VMS", counts["vms"], border=True)
        st.caption(
            f"Last controlled refresh: {summary.evaluated_at_utc.isoformat()} · three requests · "
            f"trigger: {'operator' if summary.operator_triggered else 'automatic server'} · "
            "raw responses preserved privately · API key not persisted"
        )
    if workspace is None:
        return
    try:
        state = load_national_highways_control_state(workspace)
    except (NationalHighwaysLiveError, OSError, ValueError):
        st.caption("Operational refresh history is unavailable; no source request was made.")
        return
    if state.last_attempt_status == "failed":
        st.warning(
            f"Latest refresh failed ({state.last_failure_code}). Any prior accepted overlay is "
            "unchanged and classified stale.",
            icon=":material/cloud_off:",
        )
    if not state.history:
        st.caption("Operational refresh history: no completed refresh recorded yet.")
        return
    rows = national_highways_history_rows(state)
    if len(rows) > 1:
        st.line_chart(
            rows,
            x="Retrieved at",
            y=["Closures/incidents", "Temporary speed restrictions", "VMS signs"],
            x_label="Controlled refresh time (UTC)",
            y_label="In-envelope operational records",
            width="stretch",
            height=260,
        )
    st.caption(
        f"Aggregate history: {state.history_entry_count} refreshes · 24-hour / 240-entry bound · "
        "automatic server refresh: "
        f"{'available' if state.automatic_polling_available else 'not yet recorded'} · "
        "no cross-source traffic total"
    )


def _render_bods_live_history(workspace: str | None) -> None:
    """Render bounded aggregate history from local control state; never fetch."""

    if workspace is None:
        return
    try:
        state = load_bods_live_control_state(workspace)
    except (BodsLiveControlError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "LIVE_HISTORY_INVALID")
        st.warning(
            f"Local live-refresh history is unavailable ({code}). No source request was made.",
            icon=":material/history_off:",
        )
        return
    if not state.history:
        st.caption(
            "Live refresh history: no controlled fetch recorded yet · automatic polling starts "
            "only with a configured key and explicit request box"
        )
        return
    with st.expander("Live bus aggregate history", expanded=False):
        with st.container(horizontal=True):
            st.metric("Recorded fetches", state.history_entry_count, border=True)
            st.metric("Successful fetches", state.successes_total, border=True)
            st.metric("Failed fetches", state.failures_total, border=True)
            st.metric("Minimum interval", "60 s", border=True)
        rows = bods_live_history_rows(state)
        if len(rows) > 1:
            st.line_chart(
                rows,
                x="Observed at",
                y=[
                    "Bee Network buses",
                    "Other or unknown buses",
                    "Live buses",
                    "Stale bus records",
                ],
                x_label="Controlled fetch evaluation time (UTC)",
                y_label="Transit positions",
                width="stretch",
                height=280,
            )
        else:
            st.caption("Run another controlled fetch after 60 seconds to begin a history chart.")
        st.caption(
            "Aggregate counts only · 24-hour / 240-entry bound · automatic polling recorded: "
            f"{'yes' if state.automatic_source_polling_performed else 'no'} · no raw vehicle "
            "identifiers · public export unavailable"
        )


def _render_bods_retention(workspace: str | None) -> None:
    """Render preview-first private-data retention; never delete automatically."""

    with st.expander("Private BODS snapshot retention", expanded=False):
        st.caption(
            "BODS raw snapshots may contain vehicle identifiers. The precautionary default keeps "
            "at most 24 hours / 240 snapshot families, but cleanup is never automatic and is not "
            "a claim of approved legal retention. The active live scene and newest snapshot are "
            "always protected."
        )
        if workspace is None:
            st.info("Configure a valid isolated v0.7 workspace to inspect private snapshots.")
            return
        if st.button(
            "Preview private snapshot cleanup",
            icon=":material/visibility:",
            key="manchester_bods_retention_preview",
            width="stretch",
        ):
            try:
                plan = preview_bods_retention(workspace)
            except (BodsRetentionError, OSError, ValueError) as exc:
                code = getattr(exc, "code", "RETENTION_PREVIEW_FAILED")
                st.error(
                    f"Private snapshot inventory failed safely ({code}); nothing was deleted.",
                    icon=":material/error:",
                )
            else:
                st.session_state["manchester_bods_retention_plan"] = plan.canonical_json()

        stored = st.session_state.get("manchester_bods_retention_plan")
        if not isinstance(stored, str):
            return
        try:
            plan = BodsRetentionPlan.model_validate_json(stored)
        except ValueError:
            del st.session_state["manchester_bods_retention_plan"]
            st.warning("The stored retention preview was invalidated; create a new preview.")
            return

        with st.container(horizontal=True):
            st.metric("Private families", plan.snapshot_family_count, border=True)
            st.metric("Protected / retained", plan.retained_family_count, border=True)
            st.metric("Cleanup candidates", plan.deletion_candidate_count, border=True)
            st.metric(
                "Candidate bytes",
                f"{plan.deletion_candidate_bytes / (1024 * 1024):.2f} MiB",
                border=True,
            )
        st.caption(
            f"Previewed {plan.evaluated_at_utc.isoformat()} · automatic deletion: unavailable · "
            "secure erasure: not guaranteed · public export: unavailable"
        )
        if plan.deletion_candidate_count == 0:
            st.success("The verified private snapshot inventory is within the selected bounds.")
            return
        st.warning(
            "Applying this plan permanently removes each candidate's accepted and quarantine "
            "directories. Review the preview fingerprint and type the exact confirmation below."
        )
        st.code(plan.confirmation_text(), language=None)
        with st.form("manchester_bods_retention_apply", border=True, enter_to_submit=False):
            confirmation = st.text_input(
                "Exact cleanup confirmation",
                key="manchester_bods_retention_confirmation",
            )
            submitted = st.form_submit_button(
                "Delete previewed private snapshots",
                icon=":material/delete_forever:",
                width="stretch",
            )
        if not submitted:
            return
        try:
            receipt = apply_bods_retention(
                workspace,
                plan,
                confirmation=confirmation,
            )
        except (BodsRetentionError, OSError, ValueError) as exc:
            code = getattr(exc, "code", "RETENTION_APPLY_FAILED")
            st.error(
                f"Private snapshot cleanup failed safely ({code}). Create a new preview before "
                "trying again.",
                icon=":material/error:",
            )
        else:
            del st.session_state["manchester_bods_retention_plan"]
            st.success(
                f"Deleted {receipt.deleted_family_count} complete private snapshot families "
                f"({receipt.deleted_private_bytes / (1024 * 1024):.2f} MiB). Filesystem secure "
                "erasure is not guaranteed.",
                icon=":material/check_circle:",
            )


def _render_scene_header(scene: ManchesterMapScene, loaded: LocalManchesterScene) -> None:
    with st.container(horizontal=True):
        st.metric("Evidence state", scene.status.replace("_", " "), border=True)
        st.metric("Available layers", len(visible_layer_ids(scene)), border=True)
        st.metric("Geographic scopes", len(scene.scopes), border=True)
        st.metric("Source", "Validated local artifact", border=True)
    st.caption(
        f"Mode: {_MODE_LABELS[scene.mode]} · local artifact: {loaded.byte_size} bytes · "
        "official boundary context: Manchester + Greater Manchester · basemap: disabled · "
        "network access: not required"
    )
    st.caption(
        "Boundary lines are display context only. They are not a road network, a sensor-coverage "
        "claim, or a scientific clipping rule."
    )
    if scene.status == "partial":
        st.warning(
            "Some requested evidence is excluded, stale, or unavailable. Source cards retain the "
            "exact reasons.",
            icon=":material/warning:",
        )


def _render_source_card(filtered: FilteredManchesterLayer) -> None:
    layer = filtered.manifest
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
            st.metric("Accepted map points", layer.counts.points_rendered, border=True)
            st.metric("Displayed map points", len(filtered.points), border=True)
            st.metric("Hidden by filters", filtered.hidden_by_filters, border=True)
            st.metric("Source exclusions", layer.counts.points_excluded, border=True)
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


def _render_attribution(filtered: FilteredManchesterScene) -> None:
    boundary_lines = boundary_attributions()
    st.caption("Attribution: " + " · ".join((*boundary_lines, *filtered.attributions)))
    st.caption(
        "Displayed geographic scopes: "
        + (", ".join(filtered.visible_scopes) if filtered.visible_scopes else "none")
    )


def _filter_widget_key(
    mode: MapMode,
    layer_ids: tuple[str, ...],
    scopes: tuple[GeographicScope, ...],
    freshness_states: tuple[SceneFreshnessState, ...],
) -> str:
    """Keep widget state bound to its exact available-option contract."""

    payload = "\0".join(
        (mode, *layer_ids, "--scopes--", *scopes, "--freshness--", *freshness_states)
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:12]


def _human_label(value: object) -> str:
    return str(value).replace("_", " ").capitalize()


def _render_randy_case_study() -> None:
    """Render the permission-safe non-geographic MAN-06 case-study panel."""

    st.subheader("Randy/TOS case-study evidence")
    loaded = _load_randy_case_study(os.getenv("TRAFFICTWIN_RANDY_PACK_PATH"))
    if loaded.status == "unconfigured":
        st.caption(loaded.message)
        return
    if loaded.status == "rejected" or loaded.report is None:
        st.error(loaded.message, icon=":material/gpp_bad:")
        return

    report = loaded.report
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown("**Accepted VEC-11 sanitised pack**")
            st.badge("local case study", color="blue")
            st.badge("non-geographic", color="gray")
            st.badge("not live", color="gray")
        st.caption(
            f"Run: {report.selected_run_label} · selection: {report.selection_label} · "
            f"engine: {report.engine_version}. This non-geographic panel is separate from the "
            "map and live Manchester evidence."
        )
        with st.container(horizontal=True):
            st.metric("Sanitised samples", len(report.samples), border=True)
            st.metric("Available aggregates", report.available_metric_count, border=True)
            st.metric("Unavailable aggregates", report.unavailable_metric_count, border=True)
        st.dataframe(randy_sample_rows(report), hide_index=True, width="stretch")

        with st.expander("Aggregate evidence and unavailable states"):
            st.dataframe(randy_metric_rows(report), hide_index=True, width="stretch")
        with st.expander("Citations, fingerprints, and limitations"):
            for citation in report.citations:
                st.markdown(f"- [{citation.repository}]({citation.url}) — {citation.citation_text}")
            st.caption(f"VEC-11 manifest fingerprint: {report.source_pack_manifest_fingerprint}")
            st.caption(
                f"Scientific admission fingerprint: {report.scientific_admission_fingerprint}"
            )
            for limitation in report.limitations:
                st.markdown(f"- {limitation}")
            st.warning(
                "Pseudonymisation is not anonymity. Owner permission is not a formal licence, "
                "and public hosting is not authorised.",
                icon=":material/warning:",
            )


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
    _render_map_match_review_demo()
    _render_temporal_profile_demo()


def _render_temporal_profile_demo() -> None:
    """Render the synthetic MAN-09 temporal-profile workflow demonstration."""

    with st.expander(
        "Synthetic temporal profile (MAN-09 demonstration)", icon=":material/calendar_month:"
    ):
        st.warning(
            "Synthetic demonstration only: these survey rows are generated software "
            "fixtures, not Manchester evidence. Real DfT/WebTRIS profiles remain "
            "not admitted while the production policy registry is empty and their "
            "source timezone blockers are open.",
            icon=":material/science:",
        )
        report = synthetic_temporal_profile_demo()
        states = report.cells_by_state()
        st.caption(
            f"Cells: {states['available']} available · "
            f"{states['insufficient_observations']} insufficient · "
            f"{states['no_observations']} without observations (never filled with zero) · "
            f"exclusions: "
            + ", ".join(sorted({item.reason for item in report.excluded_observations}))
        )
        st.dataframe(profile_cell_display_rows(report), hide_index=True, width="stretch")
        st.caption(
            "Null values stay typed exclusions, declared excluded dates carry their reason "
            "label, and no cell becomes SUMO demand, a baseline, or calibration input."
        )


def _render_map_match_review_demo() -> None:
    """Render the synthetic MAN-09 analyst-review workflow demonstration."""

    with st.expander("Synthetic map-match review (MAN-09 demonstration)", icon=":material/route:"):
        preflight = map_match_preflight_for_ui()
        st.warning(
            "Synthetic demonstration only: these observations, edges, and matches are "
            "generated software fixtures, not Manchester evidence. Real Manchester map "
            "matching remains unavailable: " + ", ".join(preflight.blockers) + ".",
            icon=":material/science:",
        )
        report = synthetic_map_match_demo_report()
        st.caption(
            f"Candidate pairs evaluated: {report.counts.candidate_pairs_evaluated} "
            f"(complete Cartesian reconciliation) · eligible pairs: "
            f"{report.counts.eligible_pairs} · observations without an eligible "
            f"candidate: {report.counts.observations_without_eligible_candidate}"
        )
        st.dataframe(candidate_display_rows(report), hide_index=True, width="stretch")
        eligible = eligible_candidates_by_point(report)
        with st.form("manchester_ops_map_match_review"):
            st.caption(
                "Each observation needs one explicit decision. Nothing is selected "
                "automatically, and rejected candidates stay in the record."
            )
            selections: dict[str, str] = {}
            for observation in report.request.observations:
                options = {REJECT_ALL_SENTINEL: "Reject all candidates"}
                for candidate in eligible[observation.point_id]:
                    options[candidate.fingerprint()] = (
                        f"{candidate.edge_id} · {candidate.distance_m} m · "
                        f"Δ{candidate.direction_delta_degrees}°"
                    )
                selections[observation.point_id] = st.selectbox(
                    observation.point_id,
                    options=list(options),
                    format_func=lambda value, mapping=options: mapping[value],
                    key=f"manchester_ops_map_match_{observation.point_id}",
                )
            submitted = st.form_submit_button("Record synthetic review", icon=":material/rule:")
        if submitted:
            review = review_from_selections(report, selections)
            st.success(
                f"Synthetic review recorded: {review.candidates_selected} selected, "
                f"{review.observations_rejected} rejected across "
                f"{review.observations_reviewed} observations.",
                icon=":material/fact_check:",
            )
            st.caption(
                "This typed record is synthetic workflow evidence only. It accepts no "
                "real map match and creates no SUMO baseline or calibration input."
            )
            st.download_button(
                "Download synthetic review record (JSON)",
                data=review.model_dump_json(indent=2),
                file_name="synthetic-map-match-review.json",
                mime="application/json",
                icon=":material/download:",
            )
