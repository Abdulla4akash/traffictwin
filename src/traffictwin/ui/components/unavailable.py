"""Unavailable-data components."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.results import MetricValue
from traffictwin.ui.components.badges import badge_markdown

_DEFAULT_MISSING_EVIDENCE = "not declared or not valid"
_DEFAULT_REASON_CODE = "REQUIRED_TABLE_UNAVAILABLE"


def render_unavailable_panel(
    title: str, missing_evidence: list[str], reason_codes: list[str]
) -> None:
    """Render an unavailable evidence panel.

    The value stays visibly unavailable: it is never hidden, estimated,
    defaulted, or replaced with zero. The exact reason codes and the missing
    evidence stay on screen verbatim.
    """

    evidence = missing_evidence or [_DEFAULT_MISSING_EVIDENCE]
    codes = reason_codes or [_DEFAULT_REASON_CODE]
    with st.container(border=True):
        st.markdown(f"{badge_markdown('unavailable')} **{title}**")
        st.markdown(
            "The evidence required for this value is missing or was not "
            "accepted, so it is reported as unavailable rather than "
            "estimated, defaulted, or filled with zero."
        )
        st.markdown("**Missing evidence:**\n" + "\n".join(f"- {item}" for item in evidence))
        st.caption("Reason codes: " + ", ".join(f"`{code}`" for code in codes))


def render_metric_unavailable(metric: MetricValue | None, source_hint: str) -> None:
    """Render unavailable metric details."""

    if metric is None:
        render_unavailable_panel(
            "Metric unavailable",
            [source_hint],
            ["METRIC_NOT_APPLICABLE"],
        )
        return
    render_unavailable_panel(
        f"{metric.metric_key} is unavailable",
        metric.missing_evidence or [source_hint],
        [reason.value for reason in metric.reason_codes],
    )
