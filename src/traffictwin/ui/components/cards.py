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


def section_header(title: str, description: str | None = None) -> None:
    """Render a consistent section heading."""

    st.subheader(title)
    if description:
        st.caption(description)


def report_card(
    *,
    title: str,
    report_type: str,
    path: str,
    modified: str,
    format_label: str,
) -> None:
    """Render a report summary card."""

    st.markdown(f"**{title}**")
    st.caption(f"{report_type} / {format_label} / {modified}")
    st.code(path, language=None)


def metadata_card(title: str, rows: dict[str, object]) -> None:
    """Render compact metadata as a two-column table."""

    st.markdown(f"**{title}**")
    st.dataframe(
        [{"field": key, "value": value} for key, value in rows.items()],
        hide_index=True,
        width="stretch",
    )
