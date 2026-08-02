"""Mechanism Observatory: coherence-checked cards in owner-fixed order."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st

from traffictwin.platform.observatory import EvidenceRole, render_headline
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.platform_console_services import (
    PlatformConsoleError,
    SourceLink,
    load_observatory_console,
)
from traffictwin.ui.state import UiConfig


def _render_links(links: tuple[SourceLink, ...]) -> None:
    for link in links:
        st.markdown(f"- [{link.label}]({link.url}) — SHA-256 `{link.sha256}`")


def render(config: UiConfig) -> None:
    del config
    st.title("Mechanism Observatory")
    badge_row(["READ-ONLY", "EVIDENCE ROLE EXPLICIT", "NO CAUSAL DIAGNOSIS"])
    st.caption(
        "Digest-pinned study, mechanism and policy-contract cards. The view does not recalculate "
        "endpoints, recommend a policy, pool evidence roles or upgrade standing. Every displayed "
        "deviation, support bound and limitation remains first-class."
    )
    role_value = st.selectbox(
        "Observatory evidence role filter",
        ("All evidence roles", "protocol_confirmed", "post_hoc", "exploratory", "descriptive"),
    )
    include_appendix = st.checkbox(
        "Include the separate NON_ADMITTED appendix",
        value=False,
        help="The appendix remains descriptive and is never pooled with admitted studies.",
    )
    try:
        console = load_observatory_console(
            Path.cwd(),
            evidence_role=(
                None if role_value == "All evidence roles" else cast(EvidenceRole, str(role_value))
            ),
            include_non_admitted_appendix=include_appendix,
        )
    except PlatformConsoleError as error:
        st.warning(f"Mechanism Observatory unavailable: {error}")
        return
    bundle = console.bundle
    st.caption(
        f"Bundle digest `{bundle.bundle_digest}`; policy ceiling `{bundle.research_status}`; "
        f"creates evidence: `{str(bundle.evidence).lower()}`."
    )

    st.subheader("1. Standing, scope and deviation")
    if console.studies:
        st.dataframe(
            [
                {
                    "study": study.study_id,
                    "standing": study.admission_status,
                    "qualifier": study.admission_qualifier,
                    "role": study.evidence_role,
                    "trace": study.trace_family,
                    "actor": study.actor_family,
                    "seeds": ", ".join(str(seed) for seed in study.seed_set),
                    "deviations": " | ".join(study.execution_deviations) or "none recorded",
                }
                for study in console.studies
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No study card matches this role; unavailable is not unsupported or zero.")

    st.subheader("2. Primary endpoint")
    st.markdown(render_headline(bundle))
    headline_columns = st.columns(3)
    headline_columns[0].metric(
        "Mean paired latency delta", f"{bundle.headline.mean_latency_delta_ms:,.1f} ms"
    )
    headline_columns[1].metric("Held-out seed support", "5 paired seeds")
    headline_columns[2].metric("Exact sign-test floor", "p=0.0625")

    st.subheader("3. Uncertainty")
    st.warning(
        f"Bootstrap interval [{bundle.headline.bootstrap_low_ms:,.1f}, "
        f"{bundle.headline.bootstrap_high_ms:,.1f}] ms. "
        f"{bundle.headline.sign_test_wording}."
    )

    st.subheader("4. Companion metrics")
    st.caption(bundle.headline.deadline_attainment_fact)
    st.caption(bundle.headline.locus_fact)
    st.caption(bundle.action_invariance.statement)
    st.dataframe(
        [
            {
                "check": check.check_id,
                "state": check.state,
                "required": ", ".join(check.required_metrics),
                "present": ", ".join(check.present_metrics),
                "limitation": check.limitation,
            }
            for check in bundle.coherence_checks
        ],
        hide_index=True,
        width="stretch",
    )
    st.dataframe(
        [
            {
                "actor": contract.actor_family,
                "checkpoint": contract.checkpoint,
                "observation": contract.observation_summary,
                "capacity observed": contract.rsu_capacity_in_observation,
                "action space": contract.action_space,
                "measured envelope": contract.measured_capacity_envelope,
            }
            for contract in bundle.policy_contracts
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("5. Mechanisms")
    if not console.mechanism_cards:
        st.info("No mechanism card matches this role; no fallback mechanism is invented.")
    for card in console.mechanism_cards:
        with st.expander(f"{card.title} — {card.evidence_role}"):
            st.markdown(card.statistic)
            st.caption(f"Support: {card.support}")
            for limitation in card.limitations:
                st.warning(limitation)

    st.subheader("6. Limitations")
    st.caption(
        "Protocol-confirmed, post-hoc, exploratory and descriptive records remain separate. "
        "The admitted Sparse-64 clean rerun retains its execution deviation and remains "
        "incompatible with corridor VEC; the earlier return is NON_ADMITTED even when shown."
    )

    st.subheader("7. Citations")
    _render_links(console.source_links)
    st.markdown(
        "Producer citation contract: "
        "[docs/producer_citation_requirements.md]"
        "(https://github.com/Abdulla4akash/traffictwin/blob/main/"
        "docs/producer_citation_requirements.md)"
    )
