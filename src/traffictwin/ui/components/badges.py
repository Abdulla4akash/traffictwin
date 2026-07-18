"""Badge components."""

from __future__ import annotations

import streamlit as st

STATUS_STYLE = {
    "supported": "SUPPORTED",
    "unsupported": "UNSUPPORTED",
    "unknown": "UNKNOWN",
    "accepted": "ACCEPTED",
    "accepted_with_warnings": "ACCEPTED WITH WARNINGS",
    "rejected": "REJECTED",
    "available": "AVAILABLE",
    "partial": "PARTIAL",
    "unavailable": "UNAVAILABLE",
    "invalid": "INVALID",
    "synthetic": "SYNTHETIC",
    "imported": "IMPORTED",
    "historical replay": "HISTORICAL REPLAY",
}


def badge(label: str) -> None:
    """Render a compact text badge."""

    st.markdown(f"**`{label}`**")


def badge_row(labels: list[str]) -> None:
    """Render a row of badges."""

    st.markdown(" ".join(f"**`{label}`**" for label in labels))


def status_badge(label: str) -> None:
    """Render a normalised status badge."""

    normalised = STATUS_STYLE.get(label.lower(), label.upper())
    badge(normalised)


def labelled_badge(label: str, value: str) -> None:
    """Render a label/value badge without implying judgement."""

    st.markdown(f"**{label}:** `{value}`")
