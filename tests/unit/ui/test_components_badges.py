"""Tests for the shared badge components."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from traffictwin.ui.components.badges import (
    _BADGE_STYLES,
    STATUS_STYLE,
    BadgeStyle,
    badge_markdown,
    badge_style,
)

REQUIRED_EVIDENCE_STATES = [
    "historical",
    "near_live",
    "live_vehicle",
    "stale",
    "unavailable",
    "synthetic",
]

REQUIRED_VALIDATION_STATES = ["accepted", "accepted_with_warnings", "rejected"]


def test_status_style_mapping_is_backward_compatible() -> None:
    assert STATUS_STYLE["unknown"] == "UNKNOWN"
    assert STATUS_STYLE["accepted_with_warnings"] == "ACCEPTED WITH WARNINGS"
    assert STATUS_STYLE["historical replay"] == "HISTORICAL REPLAY"
    assert len(STATUS_STYLE) == 13


def test_every_required_state_has_a_distinct_presentation() -> None:
    styles: dict[str, BadgeStyle] = {
        state: badge_style(state)
        for state in [*REQUIRED_EVIDENCE_STATES, *REQUIRED_VALIDATION_STATES]
    }
    # Colour is never the only distinction, so distinctness is asserted on
    # the (colour, icon) pair; the verbatim label text adds a third layer.
    presentations = {(style.color, style.icon) for style in styles.values()}
    assert len(presentations) == len(styles)
    for style in styles.values():
        assert style.icon is not None


def test_evidence_states_are_not_collapsed_into_one_live_colour() -> None:
    colours = {state: badge_style(state).color for state in REQUIRED_EVIDENCE_STATES}
    assert colours["near_live"] != colours["live_vehicle"]
    assert colours["stale"] not in (colours["near_live"], colours["live_vehicle"])
    assert colours["historical"] != colours["stale"]


def test_unknown_labels_fall_back_to_neutral_grey() -> None:
    style = badge_style("NO DIRECT LAUNCH")
    assert style.color == "gray"
    assert style.icon is None


def test_badge_markdown_contains_colour_label_and_icon() -> None:
    markdown = badge_markdown("accepted")
    assert markdown.startswith(":green-badge[")
    assert ":material/check_circle:" in markdown
    assert "accepted" in markdown


def test_badge_markdown_sanitises_bracket_characters() -> None:
    markdown = badge_markdown("A[B]C")
    assert "[A(B)C]" in markdown


def test_uppercase_display_labels_resolve_to_the_same_style() -> None:
    assert badge_style("ACCEPTED WITH WARNINGS") == badge_style("accepted_with_warnings")
    assert badge_style("HISTORICAL REPLAY") == badge_style("historical replay")


def _render_all_badges() -> None:
    from traffictwin.ui.components.badges import (
        badge,
        badge_row,
        evidence_state_badge,
        labelled_badge,
        status_badge,
    )

    for state in [
        "historical",
        "near_live",
        "live_vehicle",
        "stale",
        "unavailable",
        "synthetic",
        "accepted",
        "accepted_with_warnings",
        "rejected",
    ]:
        evidence_state_badge(state)
        badge(state)
    for status in [
        "supported",
        "unsupported",
        "unknown",
        "available",
        "partial",
        "invalid",
        "imported",
        "historical replay",
    ]:
        status_badge(status)
    badge_row(["SYNTHETIC", "IMPORTED", "HISTORICAL REPLAY", "NO DIRECT LAUNCH"])
    labelled_badge("Mode", "historical replay")


def test_all_mapped_badges_render_without_exception() -> None:
    """Rendering exercises Streamlit's Material icon validation server-side."""

    at = AppTest.from_function(_render_all_badges)
    at.run()
    assert not at.exception


def test_every_mapped_style_uses_a_known_colour() -> None:
    allowed = {"red", "orange", "yellow", "blue", "green", "violet", "gray", "primary"}
    for style in _BADGE_STYLES.values():
        assert style.color in allowed
