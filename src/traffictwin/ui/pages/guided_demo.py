"""Guided Demo launcher: three scripted demo modes plus the manual workflow.

The landing page offers three demo modes — Synthetic, Live Bus, Historical —
each a scripted presentation over evidence that already exists. Every mode
keeps its evidence class visible and fails closed: an unavailable mode stays
unavailable and never substitutes another evidence class. The ~4-second
autoplay cadence is presentation time only, never simulation time and never
a provider timestep. The manual research workflow and the E2/E3 research
entries stay available below the launcher.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st
from streamlit.errors import StreamlitAPIException

from traffictwin.demo.workspace import workspace_status
from traffictwin.integration.manchester.bods_acquisition import (
    BODS_ATTRIBUTION_TEXT,
    BODS_LICENCE_ID,
)
from traffictwin.integration.manchester.bods_live_control import (
    BodsLiveControlError,
    load_bods_live_control_state,
    project_bods_live_scene_for_display,
)
from traffictwin.ui.components.badges import badge_row, status_badge
from traffictwin.ui.components.cards import (
    fingerprint_summary,
    metadata_card,
    render_fingerprint,
    section_header,
)
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.consequence_cache import session_validate_bundle
from traffictwin.ui.consequence_lenses import (
    ConsequenceLensReport,
    ConsequenceMetricRow,
    build_consequence_lens_report,
)
from traffictwin.ui.demo_workspace_service import (
    ensure_demo_workspace,
    resolve_effective_demo_paths,
)
from traffictwin.ui.guided import DemoTrack, GuidedDemoProgress, steps_for_track
from traffictwin.ui.guided_demo_modes import (
    HistoricalDemoAssessment,
    LiveBusDemoAssessment,
    SyntheticDemoAssessment,
    assess_historical_demo,
    assess_live_bus_demo,
    assess_synthetic_demo,
)
from traffictwin.ui.guided_runtime import (
    GUIDED_LEGACY_PENDING_PAGE_KEY,
    begin_guided_workflow,
    load_guided_progress,
    resume_guided_workflow,
)
from traffictwin.ui.guided_tour import (
    GuidedDemoMode,
    GuidedTourState,
    stages_for_mode,
)
from traffictwin.ui.guided_tour_runtime import (
    GUIDED_TOUR_LIVE_MARKER_KEY,
    begin_tour,
    exit_tour,
    load_tour_state,
    on_tour_next,
    on_tour_previous,
    on_tour_restart,
    on_tour_toggle_play,
    render_stage_ticker,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.manchester_context import load_manchester_context
from traffictwin.ui.manchester_operations import (
    build_manchester_deck,
    visible_layer_ids,
    webtris_chart_rows,
)
from traffictwin.ui.navigation import activate_page, render_page_header
from traffictwin.ui.services import ServiceError
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tos_context import active_tos_package

# Stable session-state intent for built-in E2 mode — shared with Home.
E2_RESOURCE_STRATEGY_INTENT_KEY = "resource_strategy_intent"
E2_RESOURCE_STRATEGY_INTENT_VALUE = "e2"

# Stable session-state intent for built-in E3 mode — shared with Home.
E3_RESOURCE_STRATEGY_INTENT_KEY = "resource_strategy_intent"
E3_RESOURCE_STRATEGY_INTENT_VALUE = "e3"

_PRESENTATION_BOUNDARY = (
    "Autoplay is presentation time only — never simulation time and never a provider timestep."
)


def _open_resource_strategy_explorer(intent_value: str) -> None:
    """Record the built-in-mode intent, then route on the following rerun.

    Both routers consume their pending-page key before any widget
    instantiates, so this stays legal outside a widget callback.
    """

    st.session_state[E2_RESOURCE_STRATEGY_INTENT_KEY] = intent_value
    if st.session_state.get("_v07_navigation_active") is True:
        activate_page(UiPage.RESOURCE_STRATEGY_EXPLORER)
        st.rerun()
    try:
        st.session_state["active_page"] = UiPage.RESOURCE_STRATEGY_EXPLORER.value
    except StreamlitAPIException:
        # The legacy router's sidebar radio owns this key once instantiated;
        # queue the route for the router to consume before the next render.
        st.session_state[GUIDED_LEGACY_PENDING_PAGE_KEY] = UiPage.RESOURCE_STRATEGY_EXPLORER.value
    st.rerun()


def render(config: UiConfig) -> None:
    """Render the Guided Demo launcher or the active demo mode."""

    render_page_header(UiPage.GUIDED_DEMO)
    state = load_tour_state()
    if state is not None:
        _render_tour(config, state)
        return
    _render_landing(config)


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------


def _render_landing(config: UiConfig) -> None:
    st.caption("Choose how you want to explore TrafficTwin.")

    with st.container(border=True):
        st.markdown("**▶ Synthetic Demo**")
        badge_row(["SYNTHETIC"])
        st.caption(
            "Deterministic, reproducible scenario demonstration. Works "
            "offline and always produces the same evidence."
        )
        if st.button(
            "Start Synthetic Demo",
            key="guided_demo_mode_synthetic",
            type="primary",
            width="stretch",
            icon=":material/play_arrow:",
        ):
            begin_tour(GuidedDemoMode.SYNTHETIC)
            st.rerun()

    with st.container(border=True):
        st.markdown("**🔴 Live Bus Demo**")
        badge_row(["LIVE BODS"])
        st.caption(
            "Current BODS bus-position evidence from the verified Manchester "
            "workspace. Requires a configured BODS source."
        )
        if st.button(
            "Start Live Bus Demo",
            key="guided_demo_mode_live_bods",
            type="primary",
            width="stretch",
            icon=":material/directions_bus:",
        ):
            begin_tour(GuidedDemoMode.LIVE_BODS)
            st.rerun()

    with st.container(border=True):
        st.markdown("**🕘 Historical Demo**")
        badge_row(["HISTORICAL"])
        st.caption("Replay accepted historical Manchester evidence and inspect its provenance.")
        if st.button(
            "Start Historical Demo",
            key="guided_demo_mode_historical",
            type="primary",
            width="stretch",
            icon=":material/history:",
        ):
            begin_tour(GuidedDemoMode.HISTORICAL)
            st.rerun()

    st.divider()
    section_header(
        "Explore manually",
        "Open the research entry points or follow the stage-by-stage workflow.",
    )

    with st.expander("Research inspection entries", expanded=False):
        _render_research_entries()

    with st.expander("Stage-by-stage research workflow", expanded=False):
        _render_manual_workflow(config)


def _render_research_entries() -> None:
    st.info(
        "TrafficTwin analyses experiment artifacts. The simulation environment produces records; "
        "TrafficTwin validates, measures, compares, diagnoses, and traces them; the researcher "
        "interprets the evidence and its limits."
    )

    with st.container(border=True):
        st.markdown("**Real E2 research — Resource Strategy Explorer**")
        st.caption(
            "Inspect the bounded admitted E2b/E2c/E2d study with matched-cohort descriptive "
            "comparison. Preselects the built-in E2 mode in Resource Strategy Explorer via a "
            "stable session-state intent. This is admitted VEC research, not Manchester "
            "observation, not a live forecast, and not Kubernetes deployment."
        )
        if st.button(
            "Inspect real E2 research",
            key="guided_demo_inspect_e2_research",
            width="stretch",
            type="primary",
        ):
            _open_resource_strategy_explorer(E2_RESOURCE_STRATEGY_INTENT_VALUE)
        st.caption(
            "Opens Resource Strategy Explorer with the built-in E2 mode preselected. "
            "Synthetic demonstration remains available separately in the explorer."
        )

    with st.container(border=True):
        st.markdown("**E3 Dynamic Resource V2 — dormant staged design (no results)**")
        st.caption(
            "Inspect the bounded E3a/E3b/E3c dormant staged design (14 arms, 56 configs, "
            "fleet_draw N=4, evaluator_seed 0) with truthful empty state. Preselects the built-in "
            "E3 mode in Resource Strategy Explorer via a stable session-state "  # noqa: E501
            "intent. This is dormant "
            "staged design, not Manchester observation, not a live forecast, and not deployment. "
            "No E3 research results exist today."
        )
        if st.button(
            "Inspect E3 Dynamic Resource V2",
            key="guided_demo_inspect_e3_research",
            width="stretch",
            type="primary",
        ):
            _open_resource_strategy_explorer(E3_RESOURCE_STRATEGY_INTENT_VALUE)
        st.caption(
            "Opens Resource Strategy Explorer with the built-in E3 mode preselected. "
            "Dormant design only; every numeric surface renders NOT_EXECUTED / "
            "NO_E3_RESEARCH_RESULTS_AVAILABLE explicitly."
        )


def _render_manual_workflow(config: UiConfig) -> None:
    selected = st.radio(
        "Evidence track",
        [track.value for track in DemoTrack],
        horizontal=True,
        key="guided_demo_track",
    )
    track = DemoTrack(selected)
    _render_track_status(config, track)

    steps = steps_for_track(track)
    progress = load_guided_progress()
    matching_progress = progress if progress is not None and progress.track is track else None
    if matching_progress is not None and matching_progress.finished:
        _render_completion(matching_progress)
    current_index = matching_progress.step_index if matching_progress is not None else 0
    step = steps[current_index]
    st.progress((current_index + 1) / len(steps))
    section_header(
        f"Stage {current_index + 1} of {len(steps)}: {step.title}",
        f"Research pipeline stage: {step.key}",
    )

    input_col, operation_col, output_col = st.columns(3)
    with input_col:
        st.markdown("**Evidence input**")
        st.write(step.input_label)
    with operation_col:
        st.markdown("**Deterministic operation**")
        st.write(step.operation_label)
    with output_col:
        st.markdown("**Evidence output**")
        st.write(step.output_label)
    st.warning(step.boundary)
    st.markdown("**Your task**")
    st.write(step.instruction)

    if matching_progress is not None and matching_progress.active:
        controls = st.columns(3)
        if controls[0].button(
            "Resume current task",
            type="primary",
            width="stretch",
            key="guided_resume_workflow",
        ):
            resume_guided_workflow(matching_progress)
        if controls[1].button(
            "Restart this track",
            width="stretch",
            key="guided_restart_workflow",
        ):
            begin_guided_workflow(track)
        if controls[2].button(
            "Exit guided mode",
            width="stretch",
            key="guided_exit_workflow",
        ):
            st.session_state["guided_demo_progress"] = matching_progress.exit().model_dump(
                mode="json"
            )
            st.rerun()
    elif matching_progress is not None and not matching_progress.finished:
        controls = st.columns(2)
        if controls[0].button(
            "Resume guided workflow",
            type="primary",
            width="stretch",
            key="guided_resume_paused_workflow",
        ):
            resume_guided_workflow(matching_progress)
        if controls[1].button(
            "Restart this track",
            width="stretch",
            key="guided_restart_paused_workflow",
        ):
            begin_guided_workflow(track)
    else:
        label = "Start again" if matching_progress is not None else "Start guided workflow"
        if st.button(
            label,
            type="primary",
            width="stretch",
            key="guided_start_workflow",
        ):
            begin_guided_workflow(track)

    st.markdown(f"**Full {len(steps)}-stage journey**")
    completed = (
        set(matching_progress.completed_step_keys) if matching_progress is not None else set()
    )
    skipped = set(matching_progress.skipped_step_keys) if matching_progress is not None else set()
    for index, candidate in enumerate(steps, start=1):
        outcome = (
            "completed"
            if candidate.key in completed
            else "skipped"
            if candidate.key in skipped
            else "upcoming"
        )
        st.markdown(f"**{index}. {candidate.title}** — {candidate.target_page.value} · {outcome}")
        st.caption(candidate.instruction)


def _render_completion(progress: GuidedDemoProgress) -> None:
    """Render an honest completion summary without claiming skipped stages complete."""

    steps = steps_for_track(progress.track)
    completed = len(progress.completed_step_keys)
    skipped = len(progress.skipped_step_keys)
    st.success(
        f"Guided workflow finished: {completed} completed and {skipped} explicitly skipped "
        f"out of {len(steps)} stages."
    )
    if skipped:
        st.warning("Skipped stages remain skipped; the guide does not count them as evidence.")


def _render_track_status(config: UiConfig, track: DemoTrack) -> None:
    section_header("Active evidence context")
    if track is DemoTrack.STANDALONE:
        badge_row(["SYNTHETIC", "OFFLINE", "DETERMINISTIC"])
        workspace, _ = resolve_effective_demo_paths(config)
        if workspace is None:
            st.warning("No standalone workspace is configured for this app process.")
            return
        status = workspace_status(workspace)
        workspace_label = "Ready" if status.valid_workspace else "Unavailable"
        st.markdown(
            f"**Workspace:** {workspace_label} | **Scenarios:** {status.scenario_count} | "
            f"**Imported runs:** {status.imported_run_count} | "
            f"**Comparisons:** {status.comparison_count}"
        )
        if status.messages:
            st.caption("; ".join(status.messages))
        return

    badge_row(["IMPORTED SIMULATION", "HISTORICAL", "READ-ONLY"])
    package = active_tos_package(config)
    if package is None:
        return
    inventory = package.report.inventory
    status_badge(package.report.status.value)
    st.markdown(
        f"**Evaluation rows:** {inventory.evaluation_rows} | "
        f"**Per-step arrays:** {inventory.perstep_files} | "
        f"**Per-task arrays:** {inventory.pertask_files} | "
        f"**Mobility traces:** {inventory.trace_files}"
    )
    st.markdown(
        f"**Training histories:** {inventory.training_csv_files} | "
        f"**Training summaries:** {inventory.training_summary_files} | "
        f"**Instrumented runs:** {len(package.instrumented_runs)}"
    )
    if package.report.package_fingerprint:
        st.caption(f"Package fingerprint: {package.report.package_fingerprint}")


# ---------------------------------------------------------------------------
# Tour shell
# ---------------------------------------------------------------------------


def _render_tour(config: UiConfig, state: GuidedTourState) -> None:
    if state.mode is GuidedDemoMode.SYNTHETIC:
        _render_synthetic_tour(config, state)
    elif state.mode is GuidedDemoMode.LIVE_BODS:
        _render_live_tour(config, state)
    else:
        _render_historical_tour(config, state)


def _render_tour_progress(state: GuidedTourState) -> None:
    stages = stages_for_mode(state.mode)
    st.progress((state.stage_index + 1) / len(stages))
    st.caption(
        f"Stage {state.stage_index + 1} / {len(stages)} · autoplay "
        f"≈ {state.speed_seconds:.0f} s per stage · {_PRESENTATION_BOUNDARY}"
    )


def _render_tour_controls(state: GuidedTourState) -> None:
    toggle_label = "Pause" if state.playing else "Play"
    if len(stages_for_mode(state.mode)) > 1:
        columns = st.columns(5)
        columns[0].button(
            "Previous", key="guided_tour_previous", width="stretch", on_click=on_tour_previous
        )
        columns[1].button(
            toggle_label, key="guided_tour_toggle", width="stretch", on_click=on_tour_toggle_play
        )
        columns[2].button("Next", key="guided_tour_next", width="stretch", on_click=on_tour_next)
        columns[3].button(
            "Restart", key="guided_tour_restart", width="stretch", on_click=on_tour_restart
        )
        columns[4].button("Exit demo", key="guided_tour_exit", width="stretch", on_click=exit_tour)
        return
    columns = st.columns(3)
    columns[0].button(
        toggle_label, key="guided_tour_toggle", width="stretch", on_click=on_tour_toggle_play
    )
    columns[1].button(
        "Restart", key="guided_tour_restart", width="stretch", on_click=on_tour_restart
    )
    columns[2].button("Exit demo", key="guided_tour_exit", width="stretch", on_click=exit_tour)


def _render_exit_only_control() -> None:
    st.button("Exit demo", key="guided_tour_exit", on_click=exit_tour)


def _open_source_health_button(key: str) -> None:
    if st.button("Open Source Health", key=key):
        st.switch_page("app_pages/source_health.py")


def _open_manchester_button(key: str) -> None:
    if st.button("Open Manchester Operations", key=key):
        st.switch_page("app_pages/manchester.py")


# ---------------------------------------------------------------------------
# Synthetic tour
# ---------------------------------------------------------------------------


def _render_synthetic_tour(config: UiConfig, state: GuidedTourState) -> None:
    badge_row(["SYNTHETIC", "DETERMINISTIC", "OFFLINE"])
    section_header(
        "Synthetic Demo",
        "A scripted walkthrough of one deterministic synthetic baseline and "
        "its stressed variation. Deterministic synthetic evidence — not "
        "Manchester observation.",
    )
    workspace, registry = resolve_effective_demo_paths(config)
    assessment = assess_synthetic_demo(workspace=workspace, registry=registry)
    if assessment.status != "ready":
        _render_synthetic_unavailable(assessment)
        return
    if assessment.baseline_bundle is None or assessment.variation_bundle is None:
        _render_synthetic_unavailable(assessment)
        return
    baseline = session_validate_bundle(assessment.baseline_bundle, st.session_state)
    variation = session_validate_bundle(assessment.variation_bundle, st.session_state)
    report = build_consequence_lens_report(baseline, variation)
    if isinstance(report, ServiceError):
        render_unavailable_panel(
            "Synthetic Demo unavailable",
            [report.message],
            ["CONSEQUENCE_PROJECTION_UNAVAILABLE"],
        )
        _render_exit_only_control()
        return

    stage = stages_for_mode(state.mode)[state.stage_index]
    _render_tour_progress(state)
    st.markdown(f"### {stage.title}")
    _render_synthetic_stage(stage.key, report)
    _render_tour_controls(state)
    render_stage_ticker()


def _render_synthetic_unavailable(assessment: SyntheticDemoAssessment) -> None:
    render_unavailable_panel(
        "Synthetic Demo unavailable",
        [assessment.message],
        [assessment.reason.upper()],
    )
    if st.button(
        "Create the demo workspace",
        key="guided_demo_create_workspace",
        type="primary",
    ):
        result = ensure_demo_workspace(None)
        if result.status in {"ready", "created", "already_exists"}:
            st.session_state["active_registry_path"] = str(result.path / "registry.sqlite")
            st.session_state["_active_demo_workspace_path"] = str(result.path)
            st.rerun()
        else:
            st.error(result.message)
    _render_exit_only_control()


def _lens_row(report: ConsequenceLensReport, metric_key: str) -> ConsequenceMetricRow | None:
    for row in (*report.traffic_summary.rows, *report.vec_summary.rows):
        if row.metric_key == metric_key:
            return row
    return None


def _format_scalar(value: object, unit: str | None) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int | float):
        if unit == "ratio":
            return f"{float(value) * 100:.1f}%"
        rendered = f"{value:,}" if isinstance(value, int) else f"{value:,.1f}"
        return f"{rendered} {unit}" if unit and unit != "count" else rendered
    return str(value)


def _baseline_metric(report: ConsequenceLensReport, metric_key: str) -> None:
    row = _lens_row(report, metric_key)
    if row is None or row.status != "available":
        st.metric(label=metric_key, value="unavailable", border=True)
        return
    st.metric(label=row.label, value=_format_scalar(row.baseline, row.unit), border=True)


def _consequence_metric(report: ConsequenceLensReport, metric_key: str) -> None:
    row = _lens_row(report, metric_key)
    if row is None or row.status != "available":
        st.metric(label=metric_key, value="unavailable", border=True)
        return
    delta = None
    if row.relative_delta is not None:
        delta = f"{row.relative_delta * 100:+.1f}% vs baseline"
    st.metric(
        label=row.label,
        value=_format_scalar(row.variation, row.unit),
        delta=delta,
        delta_color="off",
        border=True,
    )


def _tri_state_label(value: bool | None) -> str:
    if value is None:
        return "Undetermined"
    return "Yes" if value else "No"


def _render_synthetic_stage(stage_key: str, report: ConsequenceLensReport) -> None:
    identity = report.baseline_identity
    variation_identity = report.variation_identity
    if stage_key == "baseline":
        st.markdown(
            "TrafficTwin generates the `baseline` preset with a fixed random "
            "seed. The same inputs always produce the same evidence, so this "
            "demo is reproducible on any machine."
        )
        with st.container(horizontal=True):
            _baseline_metric(report, "trip.records.count")
            _baseline_metric(report, "trip.completion.rate")
            _baseline_metric(report, "trip.duration.mean_s")
        st.caption(
            f"Baseline run: `{identity.get('run_id')}` · random seed "
            f"{identity.get('random_seed')} · experiment `{identity.get('experiment_id')}`"
        )
    elif stage_key == "variation":
        st.markdown(
            "The `stressed_demand` preset varies the same scenario under "
            "declared parameter changes — the incident and demand pressure "
            "are part of the deterministic configuration, not a live event."
        )
        changed = report.changed_seed_parameters
        if changed:
            st.dataframe(changed, hide_index=True, width="stretch")
        else:
            st.caption("No changed seed parameters were recorded for this pair.")
        st.caption(
            f"Variation run: `{variation_identity.get('run_id')}` · random seed "
            f"{variation_identity.get('random_seed')} · experiment "
            f"`{variation_identity.get('experiment_id')}`"
        )
    elif stage_key == "compatibility":
        compatibility = report.compatibility
        st.markdown(
            "A comparison is valid only when both runs satisfy the comparison "
            "contract. TrafficTwin checks this; it is never assumed."
        )
        st.markdown(
            f"- Same experiment: **{_tri_state_label(compatibility.same_experiment)}** "
            f"(`{identity.get('experiment_id')}`)\n"
            f"- Same random seed: **{_tri_state_label(compatibility.same_random_seed)}** "
            f"({identity.get('random_seed')})\n"
            f"- Same metric version: **{_tri_state_label(compatibility.same_metric_version)}** "
            f"({compatibility.baseline_metric_version})\n"
            f"- Both synthetic: **{_tri_state_label(compatibility.synthetic_match)}**"
        )
        if compatibility.is_compatible:
            st.success("The pair forms a valid comparison under the comparison contract.")
        else:
            st.error(
                "The pair failed the comparison contract, so consequence values "
                "stay unavailable rather than estimated."
            )
    elif stage_key == "traffic":
        st.markdown("Selected traffic consequences of the stressed variation:")
        with st.container(horizontal=True):
            _consequence_metric(report, "trip.duration.mean_s")
            _consequence_metric(report, "trip.duration.p95_s")
            _consequence_metric(report, "trip.completion.rate")
        st.caption(
            "Values come from the existing consequence-lens projection over "
            "stored metrics; nothing is recomputed for this demo."
        )
    elif stage_key == "vec":
        st.markdown("Selected VEC (vehicular edge computing) consequences:")
        with st.container(horizontal=True):
            _consequence_metric(report, "task.completion.rate")
            _consequence_metric(report, "task.latency.mean_ms")
            _consequence_metric(report, "task.incomplete.rate")
        st.caption(
            "Task and latency metrics describe the synthetic VEC workload "
            "attached to the scenario, under the same comparison contract."
        )
    elif stage_key == "provenance":
        st.markdown(
            "Every number above traces to validated bundles with recorded "
            "identity. The comparison itself carries a deterministic "
            "fingerprint."
        )
        metadata_card(
            "Comparison identity",
            {
                "Baseline run": str(identity.get("run_id")),
                "Variation run": str(variation_identity.get("run_id")),
                "Metric version": str(identity.get("metric_version")),
                "Baseline input fingerprint": fingerprint_summary(
                    str(identity.get("input_fingerprint"))
                ),
                "Variation input fingerprint": fingerprint_summary(
                    str(variation_identity.get("input_fingerprint"))
                ),
            },
        )
        render_fingerprint("Comparison fingerprint", report.fingerprint)
    else:
        _render_synthetic_takeaway(report)


def _render_synthetic_takeaway(report: ConsequenceLensReport) -> None:
    duration = _lens_row(report, "trip.duration.mean_s")
    completion = _lens_row(report, "task.completion.rate")
    parts: list[str] = []
    if (
        duration is not None
        and duration.status == "available"
        and duration.relative_delta is not None
    ):
        parts.append(f"mean trip duration changed {duration.relative_delta * 100:+.0f}%")
    if (
        completion is not None
        and completion.status == "available"
        and completion.relative_delta is not None
    ):
        parts.append(f"task completion rate changed {completion.relative_delta * 100:+.0f}%")
    if parts:
        st.markdown(
            f"**Takeaway.** Under the stressed variation, {' and '.join(parts)} "
            "relative to the deterministic baseline."
        )
    else:
        st.markdown(
            "**Takeaway.** The headline consequence values are unavailable for "
            "this pair, and they stay unavailable rather than estimated."
        )
    st.success(
        "TrafficTwin turned one declared parameter change into a validated, "
        "reproducible consequence comparison — with the evidence class and "
        "the comparison contract visible at every step."
    )
    st.caption(
        "Deterministic synthetic evidence. Not Manchester observation, not a "
        "live forecast. A comparison describes differences; it does not prove "
        "causality."
    )


# ---------------------------------------------------------------------------
# Live Bus tour
# ---------------------------------------------------------------------------


def _render_live_tour(config: UiConfig, state: GuidedTourState) -> None:
    badge_row(["LIVE BODS", "BUS POSITIONS ONLY"])
    section_header(
        "Live Bus Demo",
        "The latest accepted BODS bus-position evidence for the verified "
        "Manchester workspace. BODS bus positions are not complete Manchester "
        "road traffic.",
    )
    workspace = None if config.workspace_path is None else str(config.workspace_path)
    assessment = assess_live_bus_demo(workspace, environment=os.environ)
    if assessment.status != "ready" or assessment.summary is None or assessment.scene is None:
        _render_live_unavailable(assessment)
        return

    summary = assessment.summary
    with st.container(horizontal=True):
        st.metric("Accepted bus positions", summary.records_accepted, border=True)
        st.metric("Within live window at acceptance", summary.live_vehicle, border=True)
        st.metric("Stale at acceptance", summary.stale, border=True)
    st.caption(
        f"Latest accepted source snapshot evaluated at "
        f"{summary.evaluated_at_utc.isoformat()} · source: BODS · licence "
        f"{BODS_LICENCE_ID}"
    )
    try:
        projected = project_bods_live_scene_for_display(
            assessment.scene, evaluated_at_utc=datetime.now(UTC)
        )
    except BodsLiveControlError:
        render_unavailable_panel(
            "Live Bus Demo unavailable",
            ["The accepted scene failed display-time freshness projection."],
            ["SCENE_PROJECTION_FAILED"],
        )
        _render_exit_only_control()
        return
    st.pydeck_chart(
        build_manchester_deck(projected, visible_layer_ids(projected)),
        width="stretch",
        height=460,
    )
    st.caption(BODS_ATTRIBUTION_TEXT)
    if assessment.auto_refresh_interval_seconds is None:
        st.caption(
            "Automatic BODS refresh is off in this app process. New evidence "
            "arrives only through controlled refreshes at least 60 s apart."
        )
    else:
        st.caption(
            f"A configured worker refreshes BODS evidence about every "
            f"{assessment.auto_refresh_interval_seconds} s. The demo shows "
            "accepted snapshots only and never interpolates movement."
        )
    _live_presentation_ticker(str(config.workspace_path))
    _render_tour_controls(state)
    _open_manchester_button("guided_demo_live_open_manchester")
    st.caption("Explore this evidence in Manchester Operations for filters and history.")


def _render_live_unavailable(assessment: LiveBusDemoAssessment) -> None:
    render_unavailable_panel(
        "Live Bus Demo unavailable",
        [assessment.message],
        [assessment.reason.upper()],
    )
    st.caption(
        "The demo never falls back to synthetic data: without accepted BODS "
        "evidence there is nothing truthful to show."
    )
    with st.container(horizontal=True):
        _open_source_health_button("guided_demo_live_open_source_health")
        _open_manchester_button("guided_demo_live_open_manchester_setup")
    _render_exit_only_control()


@st.fragment(run_every="4s")  # type: ignore[untyped-decorator]
def _live_presentation_ticker(workspace: str) -> None:
    """Re-check the accepted snapshot on the presentation cadence.

    The 4-second cadence is presentation time. The scene changes only when a
    genuinely newer accepted BODS snapshot exists; a presentation refresh is
    never a new provider observation.
    """

    state = load_tour_state()
    if state is None or state.mode is not GuidedDemoMode.LIVE_BODS:
        return
    if not state.playing:
        st.caption("Presentation updates paused. Press Play to resume the 4-second check.")
        return
    try:
        control_state = load_bods_live_control_state(Path(workspace))
    except BodsLiveControlError:
        st.caption("Presentation check could not read the local BODS control state.")
        return
    summary = control_state.latest_success
    marker = None if summary is None else (summary.snapshot_id, summary.scene_file_sha256)
    previous = st.session_state.get(GUIDED_TOUR_LIVE_MARKER_KEY, "__unset__")
    st.session_state[GUIDED_TOUR_LIVE_MARKER_KEY] = marker
    if previous != "__unset__" and previous != marker:
        st.rerun()
    checked = datetime.now(UTC).strftime("%H:%M:%S")
    st.caption(
        f"Presentation check {checked} UTC · the scene updates only when a "
        "newer accepted BODS snapshot exists · a presentation refresh is not "
        "a new provider observation."
    )


# ---------------------------------------------------------------------------
# Historical tour
# ---------------------------------------------------------------------------


def _render_historical_tour(config: UiConfig, state: GuidedTourState) -> None:
    badge_row(["HISTORICAL", "NOT LIVE", "NOT SYNTHETIC"])
    section_header(
        "Historical Demo",
        "A scripted replay of accepted historical source evidence with its "
        "provenance. Historical observations are not live and not synthetic.",
    )
    workspace = None if config.workspace_path is None else str(config.workspace_path)
    assessment = assess_historical_demo(workspace)
    if assessment.status != "ready" or assessment.snapshot is None or assessment.timeseries is None:
        _render_historical_unavailable(assessment)
        return

    stage = stages_for_mode(state.mode)[state.stage_index]
    _render_tour_progress(state)
    st.markdown(f"### {stage.title}")
    _render_historical_stage(stage.key, assessment)
    _render_tour_controls(state)
    render_stage_ticker()


def _render_historical_unavailable(assessment: HistoricalDemoAssessment) -> None:
    render_unavailable_panel(
        "Historical Demo unavailable",
        [assessment.message],
        [assessment.reason.upper()],
    )
    st.caption(
        "The demo never substitutes synthetic data for missing historical "
        "evidence. Acquire and accept a WebTRIS daily report first."
    )
    _open_manchester_button("guided_demo_historical_open_manchester")
    _render_exit_only_control()


def _render_historical_stage(stage_key: str, assessment: HistoricalDemoAssessment) -> None:
    snapshot = assessment.snapshot
    result = assessment.timeseries
    if snapshot is None or result is None:  # pragma: no cover - guarded by caller
        return
    site_name = snapshot.site_name or "site name unavailable"
    report_date = snapshot.report_date.isoformat() if snapshot.report_date else "date unavailable"
    if stage_key == "source":
        st.markdown(
            "This replay uses one accepted WebTRIS daily report stored as "
            "immutable local evidence — historical observations, not a live "
            "feed and not synthetic output."
        )
        metadata_card(
            "Accepted historical source",
            {
                "Source": "National Highways WebTRIS",
                "Evidence type": "Daily traffic report (historical observation)",
                "Site": f"{site_name} (site {snapshot.site_id})",
                "Source date": report_date,
                "Licence": snapshot.licence_id,
                "Snapshot": snapshot.snapshot_id[-12:],
            },
        )
    elif stage_key == "context":
        st.markdown(
            f"The measurement site — {site_name}, site {snapshot.site_id} — "
            "reports fixed-location roadside counts inside the Greater "
            "Manchester study area."
        )
        try:
            context = load_manchester_context()
        except Exception:  # noqa: BLE001 - boundary asset is optional display context
            st.caption(
                "Static geographic context unavailable — the offline boundary "
                "asset could not be loaded. No observed scene is implied."
            )
            return
        st.pydeck_chart(context.deck, width="stretch", height=380)
        st.caption(
            f"{context.attribution[0]} · {context.attribution[1]} · static "
            "boundary context for orientation only — not evidence."
        )
    elif stage_key == "observations":
        with st.container(horizontal=True):
            st.metric("Admitted intervals", result.counts.rows_admitted, border=True)
            st.metric(
                "Missing intervals",
                result.counts.rows_missing_measurement_admitted,
                border=True,
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
            st.caption("No observed volume values exist in this accepted daily report.")
        st.caption("Missing intervals stay gaps; they are never filled with zero.")
    elif stage_key == "temporal":
        rows = webtris_chart_rows(result)
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
            st.caption("No observed speed values exist in this accepted daily report.")
        st.caption(
            "Interval times are the provider's source strings; no UTC "
            "timestamps are invented for them."
        )
    elif stage_key == "lineage":
        st.markdown(
            "The replay is rebuilt from the immutable accepted snapshot and "
            "revalidated locally — every step is fingerprinted."
        )
        metadata_card(
            "Provenance",
            {
                "Raw fingerprint": fingerprint_summary(snapshot.raw_fingerprint),
                "Manifest fingerprint": fingerprint_summary(snapshot.manifest_fingerprint),
                "Parser replay": snapshot.parser_replay_state,
                "Retrieval completed": snapshot.retrieval_completed_at_utc.isoformat(),
                "Opened offline": str(snapshot.opened_offline),
                "Result fingerprint": fingerprint_summary(result.fingerprint()),
            },
        )
        st.caption(f"Licence: {result.licence_id} · {result.attribution_text}")
    else:
        observed = result.counts.rows_admitted - result.counts.rows_missing_measurement_admitted
        st.markdown(
            f"**Interpretation.** On {report_date}, site {snapshot.site_id} "
            f"({site_name}) recorded {observed} observed intervals, with "
            f"{result.counts.rows_missing_measurement_admitted} intervals "
            "missing and reported as missing."
        )
        st.success(
            "Accepted historical evidence replayed with its provenance intact "
            "— nothing fabricated, nothing interpolated, nothing promoted to "
            "a live or causal claim."
        )
        st.caption("HISTORICAL EVIDENCE · not live · not synthetic · descriptive replay only.")
