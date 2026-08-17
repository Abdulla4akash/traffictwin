"""Challenge Designer: deterministic candidate what-if scenarios.

Three bounded modes — make the current scenario harder, test a bounded
hypothesis, or a deterministic surprise trio — each returning at most
three distinct, validated candidate scenarios over the registered
What-If contract. Selecting a candidate prepares the existing What-If
Studio prefill draft; nothing is ever executed from this page, and the
Studio keeps its own review and generation steps.
"""

from __future__ import annotations

import streamlit as st

from traffictwin.analyst import AnalystRefusalError
from traffictwin.analyst.challenge_candidates import (
    CandidateGenerationMode,
    ChallengeCandidateSet,
    ChallengeHypothesis,
    ChallengeScenarioProposal,
    candidate_to_whatif_draft,
    design_candidates,
)
from traffictwin.analyst.recommendation import RecommendationCategory
from traffictwin.ui.challenge_whatif_bridge import (
    PENDING_WHATIF_CHALLENGE_DRAFT_KEY,
    draft_to_handoff_dict,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import fingerprint_summary, section_header
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.labels import UiPage
from traffictwin.ui.state import UiConfig

_MODE_LABELS: dict[str, CandidateGenerationMode] = {
    "Make current scenario harder": CandidateGenerationMode.MAKE_HARDER,
    "Test a hypothesis": CandidateGenerationMode.TEST_HYPOTHESIS,
    "Surprise me": CandidateGenerationMode.SURPRISE_ME,
}


def render(config: UiConfig) -> None:
    """Render the Challenge Designer page."""

    del config
    st.title("Challenge Designer")
    badge_row(["CANDIDATE SCENARIOS", "REVIEW ONLY", "NO EXECUTION"])
    st.caption(
        "TrafficTwin designs up to three distinct candidate what-if "
        "scenarios over the registered What-If contract: bounded, "
        "single-mechanism pressure rather than maximal stress, with every "
        "change, held-constant control and limitation stated. Candidates "
        "are design proposals, never evidence; What-If Studio keeps its "
        "own review and generation steps."
    )

    mode_label = st.radio(
        "What do you want to challenge?",
        options=tuple(_MODE_LABELS),
        key="challenge_designer_mode",
        horizontal=True,
    )
    mode = _MODE_LABELS[mode_label]

    hypothesis: ChallengeHypothesis | None = None
    free_text: str | None = None
    if mode is CandidateGenerationMode.TEST_HYPOTHESIS:
        selected = st.selectbox(
            "Bounded hypothesis vocabulary",
            options=tuple(item.value for item in ChallengeHypothesis),
            index=None,
            key="challenge_designer_hypothesis",
            help=(
                "Mechanisms the contract cannot represent (placement, "
                "admission, queue capacity, fleet capability, ordering) are "
                "refused by name rather than approximated."
            ),
        )
        if selected is not None:
            hypothesis = ChallengeHypothesis(selected)
        free_text = st.text_input(
            "Or describe the hypothesis in your own words",
            key="challenge_designer_free_text",
            placeholder="Create a scenario where infrastructure placement matters.",
        )
        if not free_text:
            free_text = None

    bias = st.selectbox(
        "Bias toward a prior Next Investigation recommendation (optional)",
        options=tuple(item.value for item in RecommendationCategory),
        index=None,
        key="challenge_designer_recommendation_bias",
        help=(
            "Only reorders which candidate families come first; it never "
            "adds, removes or upgrades a candidate."
        ),
    )

    try:
        result = design_candidates(
            mode,
            hypothesis=hypothesis,
            free_text=free_text,
            recommendation_category=bias,
        )
    except AnalystRefusalError as error:
        render_unavailable_panel(
            "No candidates are derivable from this request",
            [error.refusal_message],
            [error.code.value],
        )
        return

    _render_outcome(result)


def _render_outcome(result: ChallengeCandidateSet) -> None:
    for note in result.designer_notes:
        st.caption(note)
    if result.outcome == "INSUFFICIENT_CONTEXT":
        render_unavailable_panel(
            "The request did not match the bounded hypothesis vocabulary",
            list(result.designer_notes) or ["Select a hypothesis from the list above."],
            ["INSUFFICIENT_CONTEXT"],
        )
        return
    if result.outcome == "HYPOTHESIS_NOT_REPRESENTABLE":
        render_unavailable_panel(
            "Supported question, but not currently representable",
            [item.reason for item in result.unrepresentable_reasons],
            ["NOT_REPRESENTABLE"],
        )
        return

    section_header(
        f"{len(result.candidates)} candidate scenarios",
        "Distinct mechanisms, bounded magnitudes, deterministic validation.",
    )
    for proposal in result.candidates:
        _render_candidate_card(proposal)
    st.caption(
        f"Design request fingerprint: `{fingerprint_summary(result.fingerprint())}` · "
        "identical inputs always produce identical candidates."
    )


def _render_candidate_card(proposal: ChallengeScenarioProposal) -> None:
    with st.container(border=True):
        st.markdown(f"### {proposal.title}")
        badge_row([proposal.family.value, proposal.validation_status.value])
        st.write(proposal.short_description)
        st.markdown(f"**Mechanism:** {proposal.intended_mechanism}")

        st.markdown("**Changes**")
        for change in proposal.changed_parameters:
            st.markdown(
                f"- `{change.whatif_field}`: {change.baseline_value} → "
                f"{change.proposed_value} ({change.direction})"
            )
        for idea in proposal.unsupported_ideas:
            st.markdown(f"- ✗ UNSUPPORTED IDEA (not transferred): {idea.idea}")

        st.caption(
            "Observe: " + ", ".join(f"`{key}`" for key in proposal.primary_observation_targets)
        )
        st.caption(f"Prediction unavailable — {proposal.prediction_reason}")

        with st.expander("Why this scenario?", expanded=False):
            st.markdown(f"**Why informative:** {proposal.why_informative}")
            st.markdown(f"**Why not maximal stress:** {proposal.not_maximal_basis}")
            st.markdown(f"**What it cannot establish:** {proposal.cannot_establish}")
            st.caption(proposal.triviality_basis)
            for reason in proposal.validation_reasons:
                st.caption(f"Validation note: {reason}")

        with st.expander("Review before handoff", expanded=False):
            st.caption(
                f"Baseline preset: `{proposal.baseline_preset}` · baseline "
                f"digest: `{fingerprint_summary(proposal.baseline_digest)}` · "
                f"evidence standing: {proposal.evidence_standing} · "
                "execution authority: NONE"
            )
            st.markdown("**Held constant**")
            for control in proposal.held_constant:
                st.markdown(f"- ✓ `{control.dimension}` ({control.group})")
            for limitation in proposal.limitations:
                st.caption(f"Limitation: {limitation}")

        if st.button(
            "Prepare in What-If Studio",
            key=f"challenge_designer_prepare_{proposal.proposal_id}",
            type="primary",
        ):
            try:
                draft = candidate_to_whatif_draft(proposal)
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
