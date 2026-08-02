"""Decision Safety: evidence-backed metric advice with no execution authority."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.platform_console_services import (
    PlatformConsoleError,
    load_decision_console,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    del config
    st.title("Decision Safety")
    badge_row(["RULESET V2", "METRIC-SPECIFIC", "NO EXECUTION AUTHORITY"])
    st.caption(
        "A digest-bound Decision-Safety assessment over the compatible confirmed-capacity "
        "comparison. Ranking and advice are confined to paired mean latency inside this measured "
        "simulation study; they are not overall-service, safety, real-road or automatic-control "
        "decisions, and generating the assessment creates no evidence."
    )
    try:
        console = load_decision_console(Path.cwd())
    except PlatformConsoleError as error:
        st.warning(f"Decision Safety unavailable: {error}")
        return
    assessment = console.assessment
    st.warning(console.required_notice.text)
    st.caption(
        f"Ruleset digest `{assessment.ruleset_digest}`; policy source "
        f"`{assessment.policy_source_digest}`; policy ceiling `{assessment.policy_ceiling}`."
    )

    st.subheader("Eligibility, metric and support")
    st.dataframe(
        [
            {
                "option": option.option_id,
                "capacity": option.capacity,
                "metric": option.primary_metric_name,
                "value": option.primary_metric_value,
                "support": option.support_count,
                "uncertainty": option.interval_status,
                "standing": option.kind,
                "inside envelope": option.inside_measured_envelope,
                "matched/predeclared": option.matched_budget and option.comparison_predeclared,
                "deviations": " | ".join(option.execution_deviations) or "none recorded",
            }
            for option in console.options
        ],
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "The cap-2.5 value is the paired-difference reference (0 ms by definition), not a missing "
        "measurement converted to zero. Support and uncertainty come from the five-seed "
        "digest-pinned comparison."
    )

    st.subheader("Metric-specific ranking, winners and advice")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Assessment status", assessment.status)
    metric_columns[1].metric("Evidence backed", str(assessment.evidence_backed).lower())
    metric_columns[2].metric("Creates new evidence", str(assessment.creates_new_evidence).lower())
    metric_columns[3].metric("Execution authority", str(assessment.execution_authority).lower())
    st.markdown(f"**Ranking:** {', '.join(assessment.ranked_option_ids) or 'unavailable'}")
    st.markdown(
        f"**Metric winner(s):** {', '.join(assessment.metric_winner_option_ids) or 'unavailable'}"
    )
    if assessment.advisory_recommendation is None:
        st.info("No advisory is available under the bound policy.")
    else:
        st.success(assessment.advisory_recommendation)
    st.caption(
        "Owner-preselected default: "
        f"{assessment.owner_preselected_default_option_id or 'unavailable — none was asserted'}. "
        f"Cause scope: `{assessment.causal_scope}`. Recommendation flag: "
        f"`{str(assessment.recommendation).lower()}`."
    )

    st.subheader("Cautions and exclusions")
    st.dataframe(
        [
            {
                "code": notice.code,
                "text": notice.text,
                "evidence backed": notice.evidence_backed,
                "cause scope": notice.causal_scope,
                "execution authority": notice.execution_authority,
            }
            for notice in assessment.notices
        ],
        hide_index=True,
        width="stretch",
    )
    if assessment.exclusions:
        st.dataframe(
            [
                {"option": option_id, "reason": reason}
                for option_id, reason in sorted(assessment.exclusions.items())
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.caption("No option was excluded; this does not broaden the metric or study scope.")

    st.subheader("Reviewable instruction drafts")
    if assessment.execution_instruction_drafts:
        st.dataframe(
            [
                {
                    "option": draft.option_id,
                    "draft": draft.text,
                    "review required": draft.review_required,
                    "executable": draft.executable,
                    "execution authority": draft.execution_authority,
                    "creates new evidence": draft.creates_new_evidence,
                }
                for draft in assessment.execution_instruction_drafts
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No reviewable instruction draft is available.")
    st.caption(
        "Draft text cannot run, approve, schedule or admit anything. A separate execution surface "
        "would still need its own valid human authority."
    )

    st.subheader("Digest-bound source and citation")
    for link in console.source_links:
        st.markdown(f"- [{link.label}]({link.url}) — SHA-256 `{link.sha256}`")
    st.markdown(
        "Producer citation contract: "
        "[docs/producer_citation_requirements.md]"
        "(https://github.com/Abdulla4akash/traffictwin/blob/main/"
        "docs/producer_citation_requirements.md)"
    )
