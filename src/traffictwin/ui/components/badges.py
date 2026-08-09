"""Badge components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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

BadgeColor = Literal["red", "orange", "yellow", "blue", "green", "violet", "gray", "primary"]


@dataclass(frozen=True)
class BadgeStyle:
    """Colour and icon for one badge label.

    Colour never carries the only meaning: the verbatim label text and a
    Material icon always accompany it.
    """

    color: BadgeColor
    icon: str | None = None


_NEUTRAL_STYLE = BadgeStyle(color="gray")

# Semantic styles keyed by normalised label (lowercase, underscores for
# spaces). Evidence states stay visually distinct from one another and from
# validation/capability statuses; unknown labels fall back to a neutral grey
# badge without implying judgement.
_BADGE_STYLES: dict[str, BadgeStyle] = {
    # Evidence truth states (design v0.7 §6).
    "historical": BadgeStyle(color="violet", icon=":material/history:"),
    "historical_replay": BadgeStyle(color="violet", icon=":material/history:"),
    "near_live": BadgeStyle(color="blue", icon=":material/schedule:"),
    "live_vehicle": BadgeStyle(color="green", icon=":material/directions_bus:"),
    "stale": BadgeStyle(color="orange", icon=":material/history_toggle_off:"),
    "unavailable": BadgeStyle(color="red", icon=":material/block:"),
    "synthetic": BadgeStyle(color="gray", icon=":material/science:"),
    # Validation statuses.
    "accepted": BadgeStyle(color="green", icon=":material/check_circle:"),
    "accepted_with_warnings": BadgeStyle(color="yellow", icon=":material/warning:"),
    "rejected": BadgeStyle(color="red", icon=":material/cancel:"),
    "invalid": BadgeStyle(color="red", icon=":material/error:"),
    # Capability and availability statuses.
    "supported": BadgeStyle(color="green", icon=":material/check_circle:"),
    "unsupported": BadgeStyle(color="red", icon=":material/block:"),
    "unknown": BadgeStyle(color="gray", icon=":material/help:"),
    "available": BadgeStyle(color="green", icon=":material/check_circle:"),
    "partial": BadgeStyle(color="yellow", icon=":material/pending:"),
    "imported": BadgeStyle(color="blue", icon=":material/download_done:"),
}

# Display text for evidence states; verbatim apart from underscore-to-space
# uppercasing so no wording stronger than the state itself is introduced.
_EVIDENCE_STATE_DISPLAY: dict[str, str] = {
    "historical": "HISTORICAL",
    "near_live": "NEAR LIVE",
    "live_vehicle": "LIVE VEHICLE",
    "stale": "STALE",
    "unavailable": "UNAVAILABLE",
    "synthetic": "SYNTHETIC",
}


def _normalise(label: str) -> str:
    return label.strip().lower().replace(" ", "_")


def _sanitise(label: str) -> str:
    """Keep badge labels safe inside a markdown badge directive."""

    return label.replace("[", "(").replace("]", ")")


def badge_style(label: str) -> BadgeStyle:
    """Return the semantic style for a label, neutral grey when unknown."""

    return _BADGE_STYLES.get(_normalise(label), _NEUTRAL_STYLE)


def badge_markdown(label: str) -> str:
    """Return inline badge markdown with semantic colour and icon."""

    style = badge_style(label)
    text = _sanitise(label)
    if style.icon is not None:
        text = f"{style.icon} {text}"
    return f":{style.color}-badge[{text}]"


def badge(label: str) -> None:
    """Render a compact text badge."""

    style = badge_style(label)
    st.badge(_sanitise(label), icon=style.icon, color=style.color)


def badge_row(labels: list[str]) -> None:
    """Render a row of badges."""

    st.markdown(" ".join(badge_markdown(label) for label in labels))


def status_badge(label: str) -> None:
    """Render a normalised status badge."""

    normalised = STATUS_STYLE.get(label.lower(), label.upper())
    badge(normalised)


def labelled_badge(label: str, value: str) -> None:
    """Render a label/value badge without implying judgement."""

    st.markdown(f"**{label}:** :gray-badge[{_sanitise(value)}]")


def evidence_state_badge(state: str) -> None:
    """Render one evidence truth state as a distinct badge.

    Unknown states stay visible verbatim on a neutral grey badge; they are
    never collapsed into another state or hidden.
    """

    display = _EVIDENCE_STATE_DISPLAY.get(_normalise(state), state.upper().replace("_", " "))
    style = badge_style(state)
    st.badge(_sanitise(display), icon=style.icon, color=style.color)


def provenance_badge(synthetic_flag: object) -> str:
    """Three-state provenance badge: synthetic / imported / unknown.

    Preserves exact semantics:
    * None -> UNKNOWN
    * True -> SYNTHETIC
    * False -> IMPORTED
    Unknown is never collapsed into false.
    """

    if synthetic_flag is None:
        return ":gray-badge[UNKNOWN]"
    return badge_markdown("synthetic") if bool(synthetic_flag) else ":gray-badge[IMPORTED]"
