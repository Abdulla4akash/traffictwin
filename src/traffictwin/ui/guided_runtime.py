"""Cross-page Streamlit controller for the action-aware guided workflow."""

from __future__ import annotations

from collections.abc import MutableMapping

import streamlit as st

from traffictwin.ui.guided import (
    DemoTrack,
    GuidedCompletionMode,
    GuidedDemoProgress,
    start_guided_progress,
    steps_for_track,
)
from traffictwin.ui.labels import UiPage

GUIDED_PROGRESS_KEY = "guided_demo_progress"
GUIDED_NOTICE_KEY = "_guided_demo_notice"
GUIDED_LEGACY_PENDING_PAGE_KEY = "_guided_demo_pending_legacy_page"


def load_guided_progress(
    state: MutableMapping[str, object] | None = None,
) -> GuidedDemoProgress | None:
    """Load valid guided progress, clearing an invalid persisted value safely."""

    session = state if state is not None else st.session_state
    raw = session.get(GUIDED_PROGRESS_KEY)
    if isinstance(raw, GuidedDemoProgress):
        progress = raw
    elif isinstance(raw, dict):
        try:
            progress = GuidedDemoProgress.model_validate(raw)
        except ValueError:
            session.pop(GUIDED_PROGRESS_KEY, None)
            return None
    else:
        if raw is not None:
            session.pop(GUIDED_PROGRESS_KEY, None)
        return None
    _mirror_legacy_stage_keys(session, progress)
    return progress


def start_guided_workflow(track: DemoTrack) -> GuidedDemoProgress:
    """Replace prior progress with a clean active workflow."""

    progress = start_guided_progress(track)
    _save_progress(progress)
    st.session_state.pop(GUIDED_NOTICE_KEY, None)
    return progress


def clear_guided_workflow() -> None:
    """Clear progress while retaining the selected track widget value."""

    st.session_state.pop(GUIDED_PROGRESS_KEY, None)
    st.session_state.pop(GUIDED_NOTICE_KEY, None)
    st.session_state["guided_demo_step"] = 0


def begin_guided_workflow(track: DemoTrack) -> None:
    """Start a track and immediately open its first real task page."""

    progress = start_guided_workflow(track)
    _navigate(progress.current_step.target_page)


def resume_guided_workflow(progress: GuidedDemoProgress) -> None:
    """Resume retained progress and immediately open its current task page."""

    resumed = progress.resume()
    _save_progress(resumed)
    _navigate(resumed.current_step.target_page)


def complete_guided_action(page: UiPage, action: str) -> bool:
    """Advance automatically after one exact successful page action.

    Pages call this only after their existing deterministic service has succeeded. It is a no-op
    outside an active matching guided stage.
    """

    progress = load_guided_progress()
    if progress is None or not progress.active:
        return False
    step = progress.current_step
    if (
        step.target_page is not page
        or step.completion_mode is not GuidedCompletionMode.ACTION
        or step.completion_action != action
    ):
        return False
    updated = progress.complete_current()
    _save_progress(updated)
    st.session_state[GUIDED_NOTICE_KEY] = f'Completed guided stage "{step.title}" automatically.'
    _navigate(_destination_for(updated))
    return True


def consume_guided_legacy_navigation() -> None:
    """Apply one guide-requested legacy route before the sidebar radio is created."""

    pending = st.session_state.pop(GUIDED_LEGACY_PENDING_PAGE_KEY, None)
    if pending is None:
        return
    try:
        page = UiPage(str(pending))
    except ValueError as exc:
        raise ValueError(f"unknown pending guided page: {pending!r}") from exc
    st.session_state["active_page"] = page.value


def render_guided_assistant(page: UiPage) -> None:
    """Render persistent guidance above the current real workflow page."""

    if page is UiPage.GUIDED_DEMO:
        return
    progress = load_guided_progress()
    if progress is None or not progress.active:
        return
    step = progress.current_step
    steps = steps_for_track(progress.track)
    notice = st.session_state.pop(GUIDED_NOTICE_KEY, None)
    with st.container(border=True):
        st.caption(
            f"Guided workflow · {progress.track.value} · "
            f"stage {progress.step_index + 1} of {len(steps)}"
        )
        st.progress((progress.step_index + 1) / len(steps))
        st.markdown(f"### {step.title}")
        if notice:
            st.success(str(notice))
        if page is not step.target_page:
            st.warning(
                f"The current guided task is on **{step.target_page.value}**. "
                "Your progress is paused while you view this page."
            )
            controls = st.columns(2)
            if controls[0].button(
                "Resume guided task",
                type="primary",
                width="stretch",
                key="guided_resume_current_task",
            ):
                _navigate(step.target_page)
            if controls[1].button(
                "Exit guided mode",
                width="stretch",
                key="guided_exit_off_task",
            ):
                _save_progress(progress.exit())
                st.rerun()
            return

        st.write(step.instruction)
        st.caption(f"Boundary: {step.boundary}")
        if step.completion_mode is GuidedCompletionMode.ACTION:
            st.info(
                "Complete the highlighted task on this page. The guide will record the "
                "successful result and open the next stage automatically."
            )
        else:
            st.info(
                "This is an inspection stage. Review the requested evidence, then use "
                "**Reviewed — continue**; the next real page opens automatically."
            )

        previous_col, complete_col, skip_col, exit_col = st.columns(4)
        if previous_col.button(
            "Previous",
            disabled=progress.step_index == 0,
            width="stretch",
            key="guided_previous_stage",
        ):
            previous = progress.previous()
            _save_progress(previous)
            _navigate(previous.current_step.target_page)

        if step.completion_mode is GuidedCompletionMode.REVIEW:
            if complete_col.button(
                "Reviewed — continue",
                type="primary",
                width="stretch",
                key="guided_complete_review_stage",
            ):
                _complete_or_skip(progress, skipped=False)
        else:
            complete_col.button(
                "Waiting for task",
                disabled=True,
                width="stretch",
                key="guided_waiting_for_action",
            )

        if skip_col.button(
            "Skip",
            width="stretch",
            key="guided_skip_stage",
            help="Records an explicit skip; it never marks the evidence task complete.",
        ):
            _complete_or_skip(progress, skipped=True)

        if exit_col.button(
            "Exit",
            width="stretch",
            key="guided_exit_stage",
        ):
            _save_progress(progress.exit())
            st.rerun()


def _complete_or_skip(progress: GuidedDemoProgress, *, skipped: bool) -> None:
    step = progress.current_step
    updated = progress.skip_current() if skipped else progress.complete_current()
    _save_progress(updated)
    outcome = "Skipped" if skipped else "Completed"
    st.session_state[GUIDED_NOTICE_KEY] = f'{outcome} guided stage "{step.title}".'
    _navigate(_destination_for(updated))


def _destination_for(progress: GuidedDemoProgress) -> UiPage:
    if progress.finished:
        return UiPage.GUIDED_DEMO
    return progress.current_step.target_page


def _save_progress(progress: GuidedDemoProgress) -> None:
    st.session_state[GUIDED_PROGRESS_KEY] = progress.model_dump(mode="json")
    _mirror_legacy_stage_keys(st.session_state, progress)


def _mirror_legacy_stage_keys(
    state: MutableMapping[str, object],
    progress: GuidedDemoProgress,
) -> None:
    state["guided_demo_step"] = progress.step_index


def _navigate(page: UiPage) -> None:
    if st.session_state.get("_v07_navigation_active") is True:
        from traffictwin.ui.navigation import V07_PENDING_PAGE_KEY

        st.session_state[V07_PENDING_PAGE_KEY] = page.value
        st.rerun()
        return
    st.session_state[GUIDED_LEGACY_PENDING_PAGE_KEY] = page.value
    st.rerun()
