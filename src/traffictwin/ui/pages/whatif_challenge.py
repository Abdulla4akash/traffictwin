"""What-If Challenge: a study-design review surface over the recommendation.

The deterministic chain ends here in a reviewable specification: Analyst
finding → recommendation → controlled challenge with explicit variables,
held-fixed controls, observables, and unresolved user inputs. The page
prepares a typed prefill for What-If Studio when the user resolves the
required inputs and clicks Prepare — nothing is ever run from here, and
the Studio's own review and generation steps remain the human's acts.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.analyst import (
    AnalystProseError,
    AnalystRefusalError,
    ChallengeReadiness,
    ChallengeTrack,
    WhatIfChallengeSpec,
    build_analyst_packet,
    build_challenge_prefill,
    build_challenge_prose_request,
    challenge_prose_status,
    classify_packet,
    plan_challenge,
    render_challenge_prose,
    resolve_scenario_track,
    select_recommendation,
)
from traffictwin.analyst.recommendation import CATEGORY_DISPLAY_NAMES, RecommendationCategory
from traffictwin.ui.challenge_whatif_bridge import (
    PENDING_WHATIF_CHALLENGE_DRAFT_KEY,
    draft_to_handoff_dict,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import fingerprint_summary, section_header
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.consequence_cache import session_validate_bundle
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.state import UiConfig
from traffictwin.ui.whatif_controls import DEFAULT_WHATIF_WIDGET_VALUES


def render(config: UiConfig) -> None:
    """Render the What-If Challenge page."""

    del config
    st.title("What-If Challenge")
    badge_row(["CONTROLLED COMPARISON PLAN", "REVIEW ONLY", "NO EXECUTION"])
    st.caption(
        "TrafficTwin converts the selected deterministic recommendation "
        "into a controlled, reviewable What-If challenge: one variable "
        "under investigation, explicit held-fixed controls, existing "
        "observables, and typed unresolved inputs. Preparing a prefill "
        "never runs anything; What-If Studio keeps its own review and "
        "generation steps."
    )

    baseline_default = str(st.session_state.get("selected_baseline_run") or "")
    variation_default = str(st.session_state.get("selected_variation_run") or "")
    baseline_text = st.text_input(
        "Baseline bundle path",
        value=baseline_default,
        key="whatif_challenge_baseline_path",
    )
    variation_text = st.text_input(
        "Variation bundle path (optional)",
        value=variation_default,
        key="whatif_challenge_variation_path",
    )

    if not baseline_text.strip():
        render_unavailable_panel(
            "No evidence subject is selected",
            [
                "Select a validated run bundle, or generate a deterministic "
                "pair in What-If Studio first."
            ],
            ["NO_SELECTED_RUN"],
        )
        return

    try:
        baseline = session_validate_bundle(Path(baseline_text.strip()), st.session_state)
        variation = (
            session_validate_bundle(Path(variation_text.strip()), st.session_state)
            if variation_text.strip()
            else None
        )
        analyst_packet = build_analyst_packet(baseline, variation)
        classification = classify_packet(analyst_packet)
        recommendation = select_recommendation(analyst_packet, classification)
        spec = plan_challenge(recommendation, analyst_packet)
    except AnalystRefusalError as error:
        render_unavailable_panel(
            "No challenge is derivable from this selection",
            [error.refusal_message],
            [error.code.value],
        )
        return
    except OSError:
        render_unavailable_panel(
            "The selected bundle could not be read",
            ["The selected path could not be read as a run bundle."],
            ["NO_SELECTED_RUN"],
        )
        return

    _render_source_chain(spec)
    _render_challenge_card(spec)
    for track in spec.tracks:
        _render_track(spec, track)
    _render_prose_section(spec)
    _render_provenance(spec)
    _render_actions()


def _render_source_chain(spec: WhatIfChallengeSpec) -> None:
    badge_row([spec.evidence_standing, spec.readiness.value])
    with st.container(border=True):
        st.markdown(f"**Source finding: {spec.analyst_signal}**")
        recommendation_display = CATEGORY_DISPLAY_NAMES[
            RecommendationCategory(spec.recommendation_category)
        ]
        st.caption(
            f"Source recommendation: {recommendation_display} "
            f"({spec.recommendation_category}) · confidence: "
            f"{spec.confidence} (categorical)"
        )


def _render_challenge_card(spec: WhatIfChallengeSpec) -> None:
    with st.container(border=True):
        st.markdown(f"### {spec.headline}")
        st.write(spec.statement)
        st.caption(
            f"Challenge category: {spec.category.value} · readiness: "
            f"{spec.readiness.value} · planner {spec.planner_version}"
        )
        if spec.readiness is ChallengeReadiness.INSUFFICIENT_EVIDENCE:
            for item in spec.missing_evidence:
                st.markdown(f"- {item}")


def _track_state_key(track_id: str, input_id: str) -> str:
    return f"whatif_challenge_input_{track_id}_{input_id}"


def _render_track(spec: WhatIfChallengeSpec, track: ChallengeTrack) -> None:
    section_header(track.title, track.research_question)
    if track.readiness is ChallengeReadiness.NOT_REPRESENTABLE:
        render_unavailable_panel(
            "Supported recommendation, but not currently representable",
            list(track.unsupported_dimensions),
            ["NOT_REPRESENTABLE"],
        )
        return

    resolved: dict[str, str | int | float] = {}
    effective_track = track
    if track.track_id == "scenario-control":
        dimension = st.selectbox(
            track.required_user_inputs[0].prompt,
            options=track.required_user_inputs[0].allowed_choices,
            index=None,
            key=_track_state_key(track.track_id, "scenario_dimension"),
        )
        if dimension is None:
            st.caption(
                "NEEDS_USER_INPUT: choose the scenario dimension to see the "
                "resolved comparison plan."
            )
            return
        effective_track = resolve_scenario_track(spec, dimension)

    st.markdown(f"**Variable under investigation:** {effective_track.variable_under_investigation}")
    st.write(effective_track.comparison_structure)

    with st.expander(f"Held fixed — {effective_track.track_id}", expanded=False):
        for control in effective_track.held_fixed:
            st.markdown(f"- ✓ `{control.dimension}` ({control.group}) — {control.basis}")

    for user_input in effective_track.required_user_inputs:
        key = _track_state_key(effective_track.track_id, user_input.input_id)
        if user_input.kind == "choice":
            choice = st.selectbox(
                user_input.prompt,
                options=user_input.allowed_choices,
                index=None,
                key=key,
                help=user_input.provenance,
            )
            if choice is not None:
                resolved[user_input.input_id] = choice
        else:
            raw_default = DEFAULT_WHATIF_WIDGET_VALUES.get(
                f"whatif_{user_input.whatif_field}", user_input.minimum
            )
            default = float(raw_default) if raw_default is not None else 0.0
            if user_input.value_type == "int":
                resolved[user_input.input_id] = int(
                    st.number_input(
                        user_input.prompt,
                        min_value=int(user_input.minimum or 0),
                        max_value=(int(user_input.maximum) if user_input.maximum else None),
                        value=int(default),
                        key=key,
                        help=user_input.provenance,
                    )
                )
            else:
                resolved[user_input.input_id] = float(
                    st.number_input(
                        user_input.prompt,
                        min_value=float(user_input.minimum or 0.0),
                        max_value=(float(user_input.maximum) if user_input.maximum else None),
                        value=float(default),
                        key=key,
                        help=user_input.provenance,
                    )
                )

    if effective_track.expected_observables:
        st.caption(
            "Expected observables (existing deterministic metrics): "
            + ", ".join(f"`{key}`" for key in effective_track.expected_observables)
        )
    st.markdown(f"**What this could support:** {effective_track.could_support}")
    st.markdown(f"**What this cannot establish:** {effective_track.cannot_establish}")

    unresolved = [
        user_input.input_id
        for user_input in effective_track.required_user_inputs
        if user_input.input_id not in resolved
    ]
    if unresolved:
        st.caption(
            f"NEEDS_USER_INPUT: resolve {', '.join(unresolved)} before a prefill can be prepared."
        )
        return
    if st.button(
        "Prepare in What-If Studio",
        key=f"whatif_challenge_prepare_{effective_track.track_id}",
        type="primary",
    ):
        try:
            draft = build_challenge_prefill(spec, effective_track, resolved)
        except AnalystRefusalError as error:
            st.warning(f"The prefill was refused: {error}")
            return
        st.session_state[PENDING_WHATIF_CHALLENGE_DRAFT_KEY] = draft_to_handoff_dict(draft)
        st.session_state["whatif_challenge_prefill_applied_fingerprint"] = None
        st.session_state["whatif_challenge_prefill_applied"] = False
        st.session_state["_v07_pending_page"] = UiPage.WHATIF_STUDIO.value
        st.success(
            "Deterministic prefill prepared for review in What-If Studio. "
            "Nothing has been executed; generate the pair explicitly there."
        )
        st.rerun()


def _render_prose_section(spec: WhatIfChallengeSpec) -> None:
    section_header(
        "AI explanation",
        "DeepSeek · prose rendering only · the deterministic challenge above stays authoritative.",
    )
    status = challenge_prose_status()
    if not status["configured"]:
        st.info(
            "LLM_NOT_CONFIGURED: DeepSeek is not configured in this process. "
            "The deterministic challenge above is complete without it."
        )
        return
    st.success("DeepSeek is configured locally; no request is sent until you consent below.")
    consent = st.checkbox(
        "I consent to sending this bounded challenge packet to DeepSeek for this request",
        key="whatif_challenge_llm_consent",
    )
    if not st.button("Explain this challenge with AI", key="whatif_challenge_llm_explain"):
        return
    if not consent:
        st.warning("Explicit DeepSeek consent is required; no external request was sent.")
        return
    try:
        prose = render_challenge_prose(build_challenge_prose_request(spec))
    except AnalystProseError as error:
        st.warning(
            f"The AI rendering refused: {error}. The deterministic challenge "
            "above remains complete and authoritative."
        )
        return
    st.write(prose.challenge_explanation)
    st.caption(f"Controls: {prose.control_explanation}")
    st.caption(f"Interpretation boundary: {prose.interpretation_boundary}")
    st.caption(
        f"Rendered by `{prose.model}`; prompt/input/response digests recorded "
        "without retaining the prose transcript or key. LLM output is never "
        "evidence."
    )


def _render_provenance(spec: WhatIfChallengeSpec) -> None:
    with st.expander("Provenance and traceability", expanded=False):
        st.caption(
            "The auditable chain: evidence → Analyst packet → classification "
            "→ recommendation packet → challenge specification → prefill."
        )
        digest_rows = (
            ("Analyst packet", spec.source_analyst_fingerprint),
            ("Recommendation packet", spec.source_recommendation_fingerprint),
            ("Challenge specification", spec.fingerprint()),
        )
        st.markdown(
            "\n".join(f"- {label}: `{fingerprint_summary(value)}`" for label, value in digest_rows)
        )
        st.markdown("\n".join(f"- `{ref}`" for ref in spec.provenance_refs))
        st.download_button(
            "Download challenge specification (JSON)",
            data=spec.canonical_json(),
            file_name="whatif_challenge_spec.json",
            mime="application/json",
            key="whatif_challenge_spec_download",
        )
        for limitation in spec.limitations:
            st.caption(f"Limitation: {limitation}")


def _render_actions() -> None:
    section_header("Continue the chain")
    columns = st.columns(4)
    with columns[0]:
        if st.button("Open Analyst", key="whatif_challenge_open_analyst", width="stretch"):
            st.switch_page("app_pages/analyst.py")
    with columns[1]:
        if st.button(
            "Open Next Investigation",
            key="whatif_challenge_open_next",
            width="stretch",
        ):
            st.switch_page("app_pages/next_investigation.py")
    with columns[2]:
        navigation_button(
            st.button,
            "Open What-If Studio",
            UiPage.WHATIF_STUDIO,
            key="whatif_challenge_open_studio",
            width="stretch",
        )
    with columns[3]:
        navigation_button(
            st.button,
            "Open Consequence Lenses",
            UiPage.CONSEQUENCE_LENSES,
            key="whatif_challenge_open_lenses",
            width="stretch",
        )
    st.caption(
        "Generating or running a what-if pair remains a human act inside "
        "What-If Studio; this page only prepares a reviewable prefill."
    )
