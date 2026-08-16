"""Next Investigation: the deterministic recommendation over the Analyst.

The Analyst interprets the evidence; this page answers "what is the most
defensible next investigation". The recommendation is selected by pure
deterministic logic before anything renders, every suggested action
quotes an existing conditional rule recommendation, and the optional
consent-gated AI section only rewrites the already-decided result. If the
Analyst refuses a subject, this page fails closed with the same typed
refusal.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.analyst import (
    AnalystProseError,
    AnalystRefusalError,
    RecommendationCategory,
    RecommendationEvidencePacket,
    build_analyst_packet,
    build_recommendation_prose_request,
    classify_packet,
    recommendation_prose_status,
    render_recommendation_prose,
    select_recommendation,
)
from traffictwin.analyst.models import SIGNAL_DISPLAY_NAMES, AnalystSignal
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import fingerprint_summary, section_header
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.consequence_cache import session_validate_bundle
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.state import UiConfig

_TRACK_HEADINGS = {
    "model": "Model-side track",
    "infrastructure": "Infrastructure-side track",
    "scenario": "Controlled-comparison track",
}


def render(config: UiConfig) -> None:
    """Render the Next Investigation page."""

    del config
    st.title("Next Investigation")
    badge_row(["DETERMINISTIC RECOMMENDATION", "DECISION SUPPORT", "NO EXECUTION"])
    st.caption(
        "TrafficTwin selects the most defensible next investigation from "
        "the Analyst's deterministic finding. Every suggested action quotes "
        "an existing conditional rule recommendation; an optional AI "
        "rendering only explains the already-decided result."
    )

    baseline_default = str(st.session_state.get("selected_baseline_run") or "")
    variation_default = str(st.session_state.get("selected_variation_run") or "")
    baseline_text = st.text_input(
        "Baseline bundle path",
        value=baseline_default,
        key="next_investigation_baseline_path",
        help="A validated run bundle. With a variation below, the "
        "recommendation covers the comparison; alone, the single run.",
    )
    variation_text = st.text_input(
        "Variation bundle path (optional)",
        value=variation_default,
        key="next_investigation_variation_path",
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
                key="next_investigation_open_whatif_empty",
                width="stretch",
            )
        with columns[1]:
            navigation_button(
                st.button,
                "Open Comparison",
                UiPage.COMPARE,
                key="next_investigation_open_compare_empty",
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
        analyst_packet = build_analyst_packet(baseline, variation)
        classification = classify_packet(analyst_packet)
        packet = select_recommendation(analyst_packet, classification)
    except AnalystRefusalError as error:
        render_unavailable_panel(
            "No recommendation is derivable from this selection",
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

    _render_analyst_finding(packet, classification.signal)
    _render_recommendation(packet)
    _render_evidence_sections(packet)
    _render_next_investigation(packet)
    _render_prose_section(packet)
    _render_provenance(packet)
    _render_actions(packet)


def _render_analyst_finding(packet: RecommendationEvidencePacket, signal: AnalystSignal) -> None:
    labels = [packet.evidence_standing]
    labels.append("COMPARISON" if packet.subject_kind == "comparison" else "SINGLE RUN")
    badge_row(labels)
    with st.container(border=True):
        st.markdown(f"**Analyst finding: {SIGNAL_DISPLAY_NAMES[signal]}**")
        st.caption(f"{packet.analyst_statement} · confidence: {packet.confidence} (categorical)")


def _render_recommendation(packet: RecommendationEvidencePacket) -> None:
    with st.container(border=True):
        st.markdown(f"### {packet.headline}")
        st.write(packet.rationale)
        st.caption(
            f"Category: {packet.category.value} · contributing rules: "
            f"{', '.join(packet.contributing_rule_ids) or 'none'} · "
            f"selector {packet.selector_version}"
        )
        if packet.alternative_category is not None and packet.alternative_reason:
            st.info(
                "Deterministically supported alternative — "
                f"{packet.alternative_category.value}: {packet.alternative_reason}"
            )


def _render_evidence_sections(packet: RecommendationEvidencePacket) -> None:
    section_header("Why this direction")
    if packet.supported_facts:
        for fact in packet.supported_facts:
            st.markdown(f"- ✓ {fact}")
    else:
        st.caption("No triggered rule contributes a supporting finding.")
    section_header("What is not established")
    for item in packet.not_established:
        st.markdown(f"- {item}")
    section_header("Important missing evidence")
    if packet.missing_evidence:
        for item in packet.missing_evidence:
            st.markdown(f"- {item}")
    else:
        st.caption("No missing evidence was recorded for this selection.")


def _render_next_investigation(packet: RecommendationEvidencePacket) -> None:
    section_header(
        "Suggested next investigation",
        "Existing deterministic rule recommendations, quoted verbatim. "
        "All are conditional; none is a command.",
    )
    if not packet.source_recommendations:
        if packet.category is RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED:
            st.caption("No intervention is recommended for this evidence.")
        else:
            st.caption(
                "No existing deterministic recommendation applies; resolve "
                "the missing evidence first."
            )
        return
    current_track = None
    for source in packet.source_recommendations:
        if source.track != current_track:
            current_track = source.track
            st.markdown(f"**{_TRACK_HEADINGS[source.track]}**")
        with st.container(border=True):
            st.markdown(f"**{source.rule_id}: {source.action}**")
            st.caption(
                f"{source.rationale} · expected direction: "
                f"{source.expected_direction} · prerequisite: "
                f"{source.prerequisite} · verify: {source.verification_step}"
            )


def _render_prose_section(packet: RecommendationEvidencePacket) -> None:
    section_header(
        "AI explanation",
        "DeepSeek · prose rendering only · the deterministic recommendation "
        "above stays authoritative.",
    )
    status = recommendation_prose_status()
    if not status["configured"]:
        st.info(
            "LLM_NOT_CONFIGURED: DeepSeek is not configured in this process. "
            "The deterministic recommendation above is complete without it."
        )
        return
    st.success("DeepSeek is configured locally; no request is sent until you consent below.")
    consent = st.checkbox(
        "I consent to sending this bounded recommendation packet to DeepSeek for this request",
        key="next_investigation_llm_consent",
    )
    if not st.button("Explain this recommendation with AI", key="next_investigation_llm_explain"):
        return
    if not consent:
        st.warning("Explicit DeepSeek consent is required; no external request was sent.")
        return
    try:
        prose = render_recommendation_prose(build_recommendation_prose_request(packet))
    except AnalystProseError as error:
        st.warning(
            f"The AI rendering refused: {error}. The deterministic "
            "recommendation above remains complete and authoritative."
        )
        return
    st.write(prose.recommendation_explanation)
    if prose.why_not_alternative:
        st.caption(f"Why not the alternative: {prose.why_not_alternative}")
    st.caption(f"Next investigation, in prose: {prose.next_investigation_explanation}")
    st.caption(
        f"Rendered by `{prose.model}`; prompt/input/response digests recorded "
        "without retaining the prose transcript or key. LLM output is never "
        "evidence."
    )


def _render_provenance(packet: RecommendationEvidencePacket) -> None:
    with st.expander("Provenance and traceability", expanded=False):
        st.caption(
            "The deterministic chain: diagnostic rule → rule status → "
            "Analyst classification → existing recommendation → category."
        )
        st.dataframe(
            [{"Rule": rule_id, "Status": status} for rule_id, status in packet.rule_statuses],
            hide_index=True,
            width="stretch",
        )
        st.markdown(
            "\n".join(f"- `{ref}`" for ref in packet.provenance_refs)
            + f"\n- Recommendation packet: `{fingerprint_summary(packet.fingerprint())}`"
        )
        st.download_button(
            "Download recommendation packet (JSON)",
            data=packet.canonical_json(),
            file_name="recommendation_evidence_packet.json",
            mime="application/json",
            key="next_investigation_packet_download",
        )
        st.caption(f"Prepare a What-If: {packet.whatif_prefill_deferred_reason}")
        for limitation in packet.limitations:
            st.caption(f"Limitation: {limitation}")


def _render_actions(packet: RecommendationEvidencePacket) -> None:
    section_header("Inspect the underlying evidence")
    columns = st.columns(4)
    with columns[0]:
        if st.button("Open Analyst", key="next_investigation_open_analyst", width="stretch"):
            st.switch_page("app_pages/analyst.py")
    with columns[1]:
        navigation_button(
            st.button,
            "Open Infrastructure & Congestion",
            UiPage.INFRASTRUCTURE,
            key="next_investigation_open_infrastructure",
            width="stretch",
        )
    with columns[2]:
        navigation_button(
            st.button,
            "Open Consequence Lenses",
            UiPage.CONSEQUENCE_LENSES,
            key="next_investigation_open_lenses",
            width="stretch",
        )
    with columns[3]:
        navigation_button(
            st.button,
            "Open What-If Studio",
            UiPage.WHATIF_STUDIO,
            key="next_investigation_open_whatif",
            width="stretch",
        )
    del packet
    st.caption(
        "Running a what-if remains a human act on the existing What-If "
        "surfaces; this page never executes or authorises anything."
    )
