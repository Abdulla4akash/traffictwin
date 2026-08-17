"""Recommendation Agent: bounded decision support over the Analyst chain.

Answers one narrow question: given the selected evidence, what should
the analyst investigate next — the model/policy, the infrastructure or
resource configuration, both, nothing, or is the evidence insufficient?
The decision is derived deterministically before anything renders; every
candidate investigation is retained with its eligibility or exclusion
reasons; retraining sits behind an explicit typed gate; the bounded
question box maps preset analyst questions onto deterministic queries;
and the optional consent-gated AI section only rewrites the
already-decided result. Nothing on this page executes, approves, or
creates evidence.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.analyst import (
    BOUNDED_QUESTIONS,
    AnalystProseError,
    AnalystRefusalError,
    ChallengeReadiness,
    RecommendationDecision,
    UnrecognisedQuestionError,
    WhatIfChallengeSpec,
    answer_free_text,
    answer_question,
    build_analyst_packet,
    build_decision_prose_request,
    classify_packet,
    decide_recommendation,
    decision_prose_status,
    plan_challenge,
    render_decision_prose,
    select_recommendation,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import fingerprint_summary, section_header
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.consequence_cache import session_validate_bundle
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render the Recommendation Agent page."""

    del config
    st.title("Recommendation Agent")
    badge_row(["DETERMINISTIC DECISION SUPPORT", "ADVISORY ONLY", "NO EXECUTION"])
    st.caption(
        "TrafficTwin decides the most defensible next investigation from "
        "the deterministic Analyst chain, keeps every candidate with its "
        "eligibility or exclusion reasons, and holds retraining behind a "
        "strict evidence gate. A human decides what happens next; nothing "
        "here executes anything."
    )

    baseline_default = str(st.session_state.get("selected_baseline_run") or "")
    variation_default = str(st.session_state.get("selected_variation_run") or "")
    baseline_text = st.text_input(
        "Baseline bundle path",
        value=baseline_default,
        key="recommendation_agent_baseline_path",
        help="A validated run bundle. With a variation below, the decision "
        "covers the comparison; alone, the single run.",
    )
    variation_text = st.text_input(
        "Variation bundle path (optional)",
        value=variation_default,
        key="recommendation_agent_variation_path",
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
        columns = st.columns(2)
        with columns[0]:
            navigation_button(
                st.button,
                "Open What-If Studio",
                UiPage.WHATIF_STUDIO,
                key="recommendation_agent_open_whatif_empty",
                width="stretch",
            )
        with columns[1]:
            navigation_button(
                st.button,
                "Open Comparison",
                UiPage.COMPARE,
                key="recommendation_agent_open_compare_empty",
                width="stretch",
            )
        return

    try:
        baseline = session_validate_bundle(Path(baseline_text.strip()), st.session_state)
        variation = (
            session_validate_bundle(Path(variation_text.strip()), st.session_state)
            if variation_text.strip()
            else None
        )
        packet = build_analyst_packet(baseline, variation)
        classification = classify_packet(packet)
        recommendation = select_recommendation(packet, classification)
        decision = decide_recommendation(packet, classification, recommendation)
        challenge = plan_challenge(recommendation, packet)
    except AnalystRefusalError as error:
        render_unavailable_panel(
            "No decision is derivable from this selection",
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

    _render_finding(decision)
    _render_next_investigation(decision)
    _render_retraining_gate(decision)
    _render_other_candidates(decision)
    _render_why_not_ledger(decision)
    _render_questions(decision)
    _render_whatif_handoff(challenge)
    _render_prose_section(decision)
    _render_provenance(decision)
    _render_actions()


def _render_finding(decision: RecommendationDecision) -> None:
    badge_row(
        [
            decision.evidence_standing,
            "COMPARISON" if decision.subject_kind == "comparison" else "SINGLE RUN",
            "EXECUTION AUTHORITY: NONE",
        ]
    )
    with st.container(border=True):
        st.markdown(f"**Current finding: {decision.direction_display}**")
        st.write(f"{decision.headline}.")
        st.caption(
            f"{decision.statement} · Analyst signal: {decision.analyst_signal} "
            f"· confidence: {decision.confidence} (categorical)"
        )


def _render_next_investigation(decision: RecommendationDecision) -> None:
    section_header("Next investigation")
    if decision.next_investigation_candidate_id is None:
        st.caption(
            "No candidate investigation is eligible on the selected "
            "evidence. That is a valid result: resolve the missing evidence "
            "below before deciding between model and infrastructure."
        )
        return
    top = next(item for item in decision.candidates if item.rank == 1)
    with st.container(border=True):
        st.markdown(f"### 1. {top.title}")
        st.markdown("**Why this is first**")
        for line in top.evidence_support:
            st.markdown(f"- ✓ {line}")
        if not top.evidence_support:
            st.caption("This candidate reflects the absence of a triggered problem.")
        st.caption(
            f"Candidate: {top.candidate_id.value} · status: {top.status.value} "
            "· executable: no · authority: none"
        )


def _render_retraining_gate(decision: RecommendationDecision) -> None:
    gate = decision.retraining_gate
    section_header(
        "Why not retrain yet?" if not gate.satisfied else "Retraining gate",
        "Retraining is a last-resort investigation behind a strict "
        "evidence gate; a poor outcome alone never satisfies it.",
    )
    with st.container(border=True):
        for item in gate.requirements:
            marker = "✓" if item.satisfied else "•"
            st.markdown(f"- {marker} **{item.requirement_id}** — {item.evidence}")
        st.caption(gate.note)


def _render_other_candidates(decision: RecommendationDecision) -> None:
    ranked = [item for item in decision.candidates if item.rank is not None and item.rank > 1]
    if not ranked:
        return
    section_header("Other supported investigations")
    for item in sorted(ranked, key=lambda entry: entry.rank or 0):
        st.markdown(f"**{item.rank}. {item.title}** — {item.status.value}")


def _render_why_not_ledger(decision: RecommendationDecision) -> None:
    excluded = [item for item in decision.candidates if item.rank is None]
    if not excluded:
        return
    with st.expander("Why not the other candidates?", expanded=False):
        st.caption(
            "Every roster candidate keeps its deterministic eligibility "
            "ledger; exclusion codes follow the Decision Safety style."
        )
        for item in excluded:
            st.markdown(
                f"**{item.title}** — {item.status.value} "
                f"({', '.join(code.value for code in item.exclusion_codes)})"
            )
            for reason in item.exclusion_reasons:
                st.markdown(f"- {reason}")
            for line in item.unavailable_evidence:
                st.caption(f"Unavailable: {line}")


def _render_questions(decision: RecommendationDecision) -> None:
    section_header(
        "Ask a bounded question",
        "Preset analyst questions map onto deterministic queries over the "
        "decision above. This is not a chatbot; free text never reaches an "
        "LLM from here.",
    )
    preset = st.selectbox(
        "Preset question",
        list(BOUNDED_QUESTIONS.values()),
        key="recommendation_agent_question_preset",
    )
    free_text = st.text_input(
        "Or ask in your own words (mapped deterministically)",
        key="recommendation_agent_question_text",
    )
    if not st.button("Answer from the decision", key="recommendation_agent_question_answer"):
        return
    try:
        if free_text.strip():
            answer = answer_free_text(decision, free_text)
        else:
            question_id = next(qid for qid, text in BOUNDED_QUESTIONS.items() if text == preset)
            answer = answer_question(decision, question_id)
    except UnrecognisedQuestionError as error:
        st.warning(str(error))
        return
    with st.container(border=True):
        st.markdown(f"**{answer.question}**")
        st.write(answer.answer)
        for line in answer.supporting_lines:
            st.markdown(f"- {line}")
        st.caption(f"{answer.boundary} · question id: {answer.question_id.value}")


def _render_whatif_handoff(challenge: WhatIfChallengeSpec) -> None:
    section_header(
        "Prepare a What-If",
        "A reviewable proposal only; What-If Studio remains the sole "
        "action boundary and nothing is executed from this page.",
    )
    if challenge.readiness is ChallengeReadiness.NOT_REPRESENTABLE:
        st.info(
            "This recommendation cannot currently be represented as a "
            "supported TrafficTwin what-if: no registered What-If dimension "
            "varies the recommended mechanism in isolation. No parameter "
            "mapping is fabricated."
        )
        return
    if challenge.readiness in (
        ChallengeReadiness.INSUFFICIENT_EVIDENCE,
        ChallengeReadiness.NO_ACTIONABLE_CHALLENGE,
    ):
        st.caption(challenge.statement)
        return
    with st.container(border=True):
        st.markdown(f"**{challenge.headline}**")
        st.write(challenge.statement)
        for track in challenge.tracks:
            st.caption(
                f"Track `{track.track_id}`: varies "
                f"{track.variable_under_investigation or 'a user-selected dimension'} "
                f"· readiness: {track.readiness.value}"
            )
        if st.button(
            "Open What-If Challenge to prepare this",
            key="recommendation_agent_open_challenge",
        ):
            st.switch_page("app_pages/whatif_challenge.py")
        st.caption(
            "The Challenge page collects the bounded inputs and hands a "
            "reviewable prefill to What-If Studio; generation stays an "
            "explicit human act there."
        )


def _render_prose_section(decision: RecommendationDecision) -> None:
    section_header(
        "AI explanation",
        "DeepSeek · prose rendering only · the deterministic decision above stays authoritative.",
    )
    status = decision_prose_status()
    if not status["configured"]:
        st.info(
            "LLM_NOT_CONFIGURED: DeepSeek is not configured in this process. "
            "The deterministic decision above is complete without it."
        )
        return
    st.success("DeepSeek is configured locally; no request is sent until you consent below.")
    consent = st.checkbox(
        "I consent to sending this bounded decision packet to DeepSeek for this request",
        key="recommendation_agent_llm_consent",
    )
    if not st.button("Explain this decision with AI", key="recommendation_agent_llm_explain"):
        return
    if not consent:
        st.warning("Explicit DeepSeek consent is required; no external request was sent.")
        return
    try:
        prose = render_decision_prose(build_decision_prose_request(decision), decision)
    except AnalystProseError as error:
        st.warning(
            f"The AI rendering refused: {error}. The deterministic decision "
            "above remains complete and authoritative."
        )
        return
    st.write(prose.decision_explanation)
    if prose.why_not_explanation:
        st.caption(f"Why the alternatives were excluded: {prose.why_not_explanation}")
    st.caption(f"Evidence gaps, in prose: {prose.evidence_gap_explanation}")
    st.caption(
        f"Rendered by `{prose.model}`; prompt/input/response digests recorded "
        "without retaining the prose transcript or key. LLM output is never "
        "evidence."
    )


def _render_provenance(decision: RecommendationDecision) -> None:
    with st.expander("Provenance and traceability", expanded=False):
        st.caption(
            "The deterministic chain: diagnostic rules → Analyst "
            "classification → Next Investigation category → candidate "
            "ledger and ranking. Identical inputs produce this identical "
            "decision."
        )
        st.markdown(
            "\n".join(f"- `{ref}`" for ref in decision.provenance_refs)
            + f"\n- Decision: `{fingerprint_summary(decision.fingerprint())}`"
        )
        st.download_button(
            "Download decision (JSON)",
            data=decision.canonical_json(),
            file_name="recommendation_decision.json",
            mime="application/json",
            key="recommendation_agent_decision_download",
        )
        for limitation in decision.limitations:
            st.caption(f"Limitation: {limitation}")


def _render_actions() -> None:
    section_header("Inspect the underlying evidence")
    columns = st.columns(4)
    with columns[0]:
        if st.button("Open Analyst", key="recommendation_agent_open_analyst", width="stretch"):
            st.switch_page("app_pages/analyst.py")
    with columns[1]:
        if st.button(
            "Open Next Investigation",
            key="recommendation_agent_open_next",
            width="stretch",
        ):
            st.switch_page("app_pages/next_investigation.py")
    with columns[2]:
        if st.button(
            "Open Decision Safety",
            key="recommendation_agent_open_decision_safety",
            width="stretch",
        ):
            st.switch_page("app_pages/platform_decision_safety.py")
    with columns[3]:
        navigation_button(
            st.button,
            "Open Provenance Explorer",
            UiPage.PROVENANCE,
            key="recommendation_agent_open_provenance",
            width="stretch",
        )
    st.caption(
        "Every recommendation on this page is advisory, reviewable and "
        "non-executable; acting on one remains a human decision on the "
        "existing TrafficTwin surfaces."
    )
