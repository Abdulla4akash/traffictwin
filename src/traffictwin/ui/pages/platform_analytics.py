"""Analytics Quality: immutable operational reports, never scientific confidence."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.platform_console_services import (
    PlatformConsoleError,
    load_analytics_console,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    st.title("Analytics Quality")
    badge_row(["READ-ONLY", "OPERATIONAL QUALITY", "NOT SCIENTIFIC CONFIDENCE"])
    st.caption(
        "Immutable aggregate-quality reports from the single allowlisted local feed. "
        "Freshness, completeness and exclusions are operational readiness checks: a pass does "
        "not admit evidence, readiness is not forecast validity, and this page neither runs the "
        "monitor nor activates the 15-minute scheduler."
    )
    try:
        console = load_analytics_console(config.workspace_path)
    except PlatformConsoleError as error:
        st.warning(f"Analytics quality unavailable: {error}")
        return
    if console.latest is None:
        st.info(
            f"Analytics quality unavailable: {console.unavailable_reason}. This is an explicit "
            "unavailable state; absent reports and observations are never displayed as zero."
        )
        return

    latest = console.latest
    metric_columns = st.columns(4)
    metric_columns[0].metric("Accepted sources", len(latest.accepted))
    metric_columns[1].metric("Warnings", len(latest.warned))
    metric_columns[2].metric("Refusals", len(latest.refused))
    metric_columns[3].metric("Not observed", len(latest.not_observed))
    st.caption(
        f"Latest report `{latest.digest()}`; policy "
        f"`{latest.operational_policy_digest or 'unavailable'}`; generated "
        f"{latest.generated_at_utc.isoformat() if latest.generated_at_utc else 'unavailable'}. "
        f"Evidence created: `{str(latest.evidence).lower()}`. {latest.standing_note}"
    )

    st.subheader("Immutable report feed")
    st.dataframe(
        [
            {
                "report digest": row.report_digest,
                "generated (UTC)": (
                    row.generated_at_utc.isoformat() if row.generated_at_utc else "unavailable"
                ),
                "accepted": row.accepted_count,
                "warnings": row.warning_count,
                "refusals": row.refusal_count,
                "not observed": row.not_observed_count,
                "policy digest": row.policy_digest or "unavailable",
                "evidence": row.evidence,
            }
            for row in console.feed
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Latest quality observations")
    observations = (*latest.refused, *latest.warned, *latest.informational)
    if observations:
        st.dataframe(
            [
                {
                    "severity": item.severity,
                    "rule": item.rule,
                    "scope": item.scope,
                    "measured": item.measured,
                    "support": item.support if item.support is not None else "unavailable",
                    "source digest": item.source_sha256,
                }
                for item in observations
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No quality observation was recorded in the latest report; this is not a pass.")
    if latest.not_observed:
        st.warning("Not observed: " + " | ".join(latest.not_observed))
    else:
        st.caption("The latest report has no explicit not-observed entries.")
    st.caption(
        f"Notification surface: {', '.join(latest.notification_surface) or 'unavailable'}. "
        f"Retention: {latest.retention_policy or 'unavailable'}. This page sends nothing and "
        "offers no delete or acknowledgement control."
    )
