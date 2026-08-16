"""TrafficTwin Analyst: bounded, evidence-grounded analysis surface.

Deterministic first, always: the page builds the Analyst Evidence Packet
from existing services, classifies it deterministically, and renders that
result completely without any LLM. The optional DeepSeek prose rendering
is a per-request, consent-gated enhancement that can never change the
classification, add a number, or promote evidence standing.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

from traffictwin.analyst import (
    SIGNAL_DISPLAY_NAMES,
    AnalystClassification,
    AnalystEvidencePacket,
    AnalystProseError,
    AnalystRefusalError,
    analyst_prose_status,
    build_analyst_packet,
    build_prose_request,
    classify_packet,
    render_analyst_prose,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import fingerprint_summary, section_header
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.consequence_cache import session_validate_bundle
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.state import UiConfig

_QUESTIONS: tuple[str, ...] = (
    "Why did this scenario behave this way?",
    "What is the main bottleneck?",
    "Does this look model-side or infrastructure-side?",
    "Which evidence supports that interpretation?",
    "What should I investigate next?",
    "What can TrafficTwin not conclude from this evidence?",
)

_CAUSAL_MARKERS = re.compile(
    r"\b(cause[sd]?|causal|because|prove[sd]?|proof|guarantee[sd]?)\b", re.IGNORECASE
)


def render(config: UiConfig) -> None:
    """Render the Analyst page."""

    del config
    st.title("TrafficTwin Analyst")
    badge_row(["DETERMINISTIC FIRST", "DECISION SUPPORT", "NO EXECUTION"])
    st.caption(
        "The Analyst restates existing deterministic evidence and rule "
        "outcomes, then assigns a bounded model-vs-infrastructure signal. "
        "It never computes science, never executes anything, and an "
        "optional AI rendering only rewrites the deterministic result as "
        "prose."
    )

    baseline_default = str(st.session_state.get("selected_baseline_run") or "")
    variation_default = str(st.session_state.get("selected_variation_run") or "")
    baseline_text = st.text_input(
        "Baseline bundle path",
        value=baseline_default,
        key="analyst_baseline_path",
        help="A validated run bundle. With a variation below, the Analyst "
        "analyses the comparison; alone, it analyses the single run.",
    )
    variation_text = st.text_input(
        "Variation bundle path (optional)",
        value=variation_default,
        key="analyst_variation_path",
    )

    question = st.radio("Question", _QUESTIONS, key="analyst_question")
    free_text = st.text_input(
        "Ask in your own words (optional)",
        key="analyst_free_text",
        help="Free text never reaches any AI model; it only selects one of "
        "the bounded questions above.",
    )
    if free_text.strip() and _CAUSAL_MARKERS.search(free_text):
        st.warning(
            "UNSUPPORTED_CAUSAL_REQUEST: the selected evidence supports "
            "descriptive comparison only. Causal wording is refused unless "
            "an existing deterministic policy grants that exact scope."
        )
        return

    if not baseline_text.strip():
        render_unavailable_panel(
            "Analyst has no selected evidence",
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
                key="analyst_open_whatif_empty",
                width="stretch",
            )
        with columns[1]:
            navigation_button(
                st.button,
                "Open Comparison",
                UiPage.COMPARE,
                key="analyst_open_compare_empty",
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
    except AnalystRefusalError as error:
        render_unavailable_panel(
            "Analyst refuses to interpret this selection",
            [error.refusal_message],
            [error.code.value],
        )
        return
    except OSError:
        render_unavailable_panel(
            "Analyst could not read the selected bundle",
            ["The selected path could not be read as a run bundle."],
            ["NO_SELECTED_RUN"],
        )
        return

    classification = classify_packet(packet)
    _render_evidence_badges(packet)
    _render_finding(packet, classification, question)
    _render_supporting_evidence(classification)
    _render_key_numbers(packet)
    _render_traceability(packet, classification)
    _render_prose_section(packet, classification)
    _render_navigation()


def _render_evidence_badges(packet: AnalystEvidencePacket) -> None:
    labels: list[str] = [packet.identity.baseline_standing]
    if (
        packet.identity.variation_standing is not None
        and packet.identity.variation_standing != packet.identity.baseline_standing
    ):
        labels.append(packet.identity.variation_standing)
    labels.append("COMPARISON" if packet.identity.subject_kind == "comparison" else "SINGLE RUN")
    badge_row(labels)


def _answer_focus(question: str, classification: AnalystClassification) -> str:
    if question == _QUESTIONS[4]:
        return "Answer focus: the suggested next investigation below."
    if question == _QUESTIONS[5]:
        return "Answer focus: the limitations and unavailable evidence below."
    if question == _QUESTIONS[3]:
        return "Answer focus: the supporting facts and traceability below."
    return (
        "Answer focus: the deterministic signal below "
        f"({SIGNAL_DISPLAY_NAMES[classification.signal]})."
    )


def _render_finding(
    packet: AnalystEvidencePacket,
    classification: AnalystClassification,
    question: str,
) -> None:
    with st.container(border=True):
        st.markdown(f"### {SIGNAL_DISPLAY_NAMES[classification.signal]}")
        st.caption(_answer_focus(question, classification))
        st.write(classification.statement)
        st.caption(
            f"Confidence: {classification.confidence} (categorical) · "
            f"{classification.confidence_basis} · rule basis: "
            f"{', '.join(classification.rule_basis) or 'none'}"
        )
        if classification.next_investigation:
            st.info(f"Suggested next investigation: {classification.next_investigation}")
        if packet.diagnostics.conflict_observations:
            for observation in packet.diagnostics.conflict_observations:
                st.warning(observation)


def _render_supporting_evidence(classification: AnalystClassification) -> None:
    section_header("What supports this")
    if classification.supported_facts:
        for fact in classification.supported_facts:
            st.markdown(f"- ✓ {fact}")
    else:
        st.caption("No triggered rule contributes a supporting finding.")
    section_header("What does not support this")
    if classification.not_supported:
        for item in classification.not_supported:
            st.markdown(f"- {item}")
    else:
        st.caption("No contradicting or missing evidence was recorded.")


def _format_fact_value(value: object, unit: str | None) -> str:
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


def _render_key_numbers(packet: AnalystEvidencePacket) -> None:
    facts = [
        fact
        for fact in (*packet.vec_facts, *packet.infrastructure_facts)
        if fact.status == "available"
    ][:3]
    if not facts:
        st.caption(
            "No headline metric is available for this selection; unavailable "
            "values stay unavailable."
        )
        return
    section_header("Key numbers", "Restated from existing services; nothing recomputed.")
    with st.container(horizontal=True):
        for fact in facts:
            is_comparison = packet.identity.subject_kind == "comparison"
            value = fact.variation if is_comparison else fact.baseline
            delta = None
            if is_comparison and fact.relative_delta is not None:
                delta = f"{fact.relative_delta * 100:+.1f}% vs baseline"
            st.metric(
                label=fact.label,
                value=_format_fact_value(value, fact.unit),
                delta=delta,
                delta_color="off",
                border=True,
            )


def _render_traceability(
    packet: AnalystEvidencePacket, classification: AnalystClassification
) -> None:
    with st.expander("Why is the Analyst saying this?", expanded=False):
        st.caption(
            "Deterministic supporting record: rule outcomes, evidence keys, "
            "and artifact digests. There is no hidden reasoning."
        )
        st.dataframe(
            [
                {
                    "Rule": rule.rule_id,
                    "Title": rule.title,
                    "Status": rule.status,
                    "Confidence": rule.confidence,
                    "Evidence keys": ", ".join(rule.evidence_keys),
                }
                for rule in packet.diagnostics.subject_rules
            ],
            hide_index=True,
            width="stretch",
        )
        provenance = packet.provenance
        digest_rows = (
            ("Baseline bundle", provenance.baseline_bundle_fingerprint),
            ("Variation bundle", provenance.variation_bundle_fingerprint),
            ("Diagnostics", provenance.subject_diagnostic_fingerprint),
            ("Consequence lens", provenance.consequence_lens_fingerprint),
            ("Packet", classification.packet_fingerprint),
        )
        st.markdown(
            "\n".join(f"- {label}: `{fingerprint_summary(value)}`" for label, value in digest_rows)
            + f"\n- Classifier: `{classification.classifier_version}`"
        )
        st.download_button(
            "Download Analyst packet (JSON)",
            data=packet.canonical_json(),
            file_name="analyst_evidence_packet.json",
            mime="application/json",
            key="analyst_packet_download",
        )
        for limitation in packet.limitations:
            st.caption(f"Limitation: {limitation}")


def _render_prose_section(
    packet: AnalystEvidencePacket, classification: AnalystClassification
) -> None:
    section_header(
        "AI explanation",
        "DeepSeek · prose rendering only · no metrics generated · the "
        "deterministic result above stays authoritative.",
    )
    status = analyst_prose_status()
    if not status["configured"]:
        st.info(
            "LLM_NOT_CONFIGURED: DeepSeek is not configured in this process. "
            "The deterministic analysis above is complete without it."
        )
        return
    st.success("DeepSeek is configured locally; no request is sent until you consent below.")
    consent = st.checkbox(
        "I consent to sending this bounded analysis packet to DeepSeek for this request",
        key="analyst_llm_consent",
    )
    if not st.button("Explain with AI", key="analyst_llm_explain"):
        return
    if not consent:
        st.warning("Explicit DeepSeek consent is required; no external request was sent.")
        return
    try:
        prose = render_analyst_prose(build_prose_request(packet, classification))
    except AnalystProseError as error:
        st.warning(
            f"The AI rendering refused: {error}. The deterministic result "
            "above remains complete and authoritative."
        )
        return
    st.write(prose.explanation)
    if prose.next_investigation:
        st.caption(f"AI phrasing of the next investigation: {prose.next_investigation}")
    st.caption(
        f"Rendered by `{prose.model}`; prompt/input/response digests recorded "
        "without retaining the prose transcript or key. LLM output is never "
        "evidence."
    )


def _render_navigation() -> None:
    section_header("Inspect the underlying evidence")
    columns = st.columns(5)
    with columns[0]:
        navigation_button(
            st.button,
            "Open Consequence Lenses",
            UiPage.CONSEQUENCE_LENSES,
            key="analyst_open_lenses",
            width="stretch",
        )
    with columns[1]:
        navigation_button(
            st.button,
            "Open Comparison",
            UiPage.COMPARE,
            key="analyst_open_compare",
            width="stretch",
        )
    with columns[2]:
        navigation_button(
            st.button,
            "Open Provenance Explorer",
            UiPage.PROVENANCE,
            key="analyst_open_provenance",
            width="stretch",
        )
    with columns[3]:
        navigation_button(
            st.button,
            "Open Infrastructure & Congestion",
            UiPage.INFRASTRUCTURE,
            key="analyst_open_infrastructure",
            width="stretch",
        )
    with columns[4]:
        navigation_button(
            st.button,
            "Open What-If Studio",
            UiPage.WHATIF_STUDIO,
            key="analyst_open_whatif",
            width="stretch",
        )
    st.caption(
        "Preparing or running a what-if remains a human act on the existing "
        "What-If surfaces; the Analyst never executes or authorises anything."
    )
