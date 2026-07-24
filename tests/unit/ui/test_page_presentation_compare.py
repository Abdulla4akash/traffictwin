"""Presentation tests for the comparison page provenance badge."""

from __future__ import annotations

from traffictwin.ui.pages.compare import _provenance_badge


def test_provenance_badge_is_three_state() -> None:
    # A definite synthetic flag renders the synthetic badge.
    assert "synthetic" in _provenance_badge(True)
    # A definite non-synthetic flag renders IMPORTED.
    assert _provenance_badge(False) == ":gray-badge[IMPORTED]"
    # An absent/unknown flag is NOT collapsed to a definite IMPORTED state.
    assert _provenance_badge(None) == ":gray-badge[UNKNOWN]"
    assert "IMPORTED" not in _provenance_badge(None)
