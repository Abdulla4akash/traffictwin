"""Unavailable-data components."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.results import MetricValue


def render_unavailable_panel(
    title: str, missing_evidence: list[str], reason_codes: list[str]
) -> None:
    """Render an unavailable evidence panel."""

    st.warning(title)
    st.write(
        {
            "missing_evidence": missing_evidence or ["not declared or not valid"],
            "reason_codes": reason_codes or ["REQUIRED_TABLE_UNAVAILABLE"],
        }
    )


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
