"""Small KPI card helpers."""

from __future__ import annotations

import streamlit as st

from traffictwin.metrics.results import MetricValue
from traffictwin.ui.formatting import format_metric_detail, format_metric_value


def metric_card(title: str, metric: MetricValue | None) -> None:
    """Render one metric card."""

    st.metric(label=title, value=format_metric_value(metric), help=format_metric_detail(metric))


def text_card(title: str, value: object, help_text: str | None = None) -> None:
    """Render a simple text metric."""

    st.metric(label=title, value=str(value), help=help_text)
