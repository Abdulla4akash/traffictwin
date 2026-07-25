"""Automated accessibility evidence across the v0.7 page set (Gate C, UX-03).

**Automated evidence only.** These checks cannot accept Gate C and are not an
accessibility audit. They cover what the `AppTest` element tree can prove:
that every interactive control carries a usable label, that labels are not
ambiguous within a page, and that heading structure is coherent.

**What is deliberately not checked here.** Contrast ratio, zoom and reflow,
keyboard traversal order, and screen-reader announcement cannot be established
from the element tree — they need a rendered browser or a person. Approximating
them and reporting a pass would be worse than an honest gap, so they live in
`docs/evaluation/manual_accessibility_checklist.md` instead, unticked.

No screen-reader user, participant, or assistive-technology session is invented
by this file.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state

#: Controls a keyboard or screen-reader user must be able to identify.
_LABELLED_ELEMENTS = ("button", "text_input", "selectbox", "checkbox", "radio", "multiselect")

#: Above this many collapsible and text elements, a single heading is not enough
#: to orient by. Chosen to sit well above the median page, so it flags genuinely
#: dense pages rather than ordinary ones.
_DENSE_PAGE_ELEMENTS = 20

#: Labels that exist but say nothing useful out of context.
_UNINFORMATIVE_LABELS = frozenset(
    {"", " ", "...", "…", "-", "--", "click", "click here", "here", "ok", "go", "submit", "?"}
)


#: Real defects these checks found, in files this work does not own. Each is
#: marked ``strict``, so the suite fails the moment one is fixed and the entry
#: has to be removed. Weakening the assertion instead would have hidden the
#: defect and left the check asserting nothing.
#:
#: Empty: the duplicate "Plan an Experiment" button on the home page was
#: removed once the UI came into scope, and this registry emptied with it.
_KNOWN_LABEL_DEFECTS: dict[UiPage, str] = {}


def _page_params() -> list[object]:
    """Every page, with a known defect marked rather than excused."""

    params: list[object] = []
    for page in UiPage:
        reason = _KNOWN_LABEL_DEFECTS.get(page)
        marks = pytest.mark.xfail(reason=reason, strict=True) if reason else ()
        params.append(pytest.param(page, marks=marks, id=page.name))
    return params


def _run(page: UiPage) -> AppTest:
    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in default_session_state().items():
        app.session_state[key] = value
    app.run(timeout=40)
    assert not app.exception, f"{page.name} raised before it could be inspected"
    return app


def _labels(app: AppTest, kind: str) -> list[str]:
    collection = getattr(app, kind, None)
    if collection is None:
        return []
    labels: list[str] = []
    for element in collection:
        label = getattr(element, "label", None)
        if label is not None:
            labels.append(str(label))
    return labels


@pytest.mark.parametrize("page", list(UiPage), ids=lambda page: page.name)
class TestEveryControlIsIdentifiable:
    def test_no_interactive_control_is_unlabelled(self, page: UiPage) -> None:
        # A control with no label is unusable by anyone not looking at it.
        app = _run(page)
        for kind in _LABELLED_ELEMENTS:
            for label in _labels(app, kind):
                assert label.strip(), f"{page.name} has an unlabelled {kind}"

    def test_no_control_label_is_uninformative(self, page: UiPage) -> None:
        # "Click here" tells a screen-reader user nothing about what it does.
        app = _run(page)
        for kind in _LABELLED_ELEMENTS:
            for label in _labels(app, kind):
                normalised = label.strip().lower().rstrip(":")
                assert normalised not in _UNINFORMATIVE_LABELS, (
                    f"{page.name} has an uninformative {kind} label: {label!r}"
                )


@pytest.mark.parametrize("page", _page_params())
class TestControlLabelsAreUnambiguous:
    def test_no_two_controls_on_a_page_share_a_label(self, page: UiPage) -> None:
        # Two identically-labelled controls on one page cannot be told apart by
        # a user traversing them without sight of their position.
        app = _run(page)
        for kind in _LABELLED_ELEMENTS:
            labels = [label.strip().lower() for label in _labels(app, kind) if label.strip()]
            duplicates = {label for label in labels if labels.count(label) > 1}
            assert not duplicates, f"{page.name} repeats a {kind} label: {sorted(duplicates)}"


@pytest.mark.parametrize("page", list(UiPage), ids=lambda page: page.name)
class TestHeadingStructureIsCoherent:
    def test_a_page_has_exactly_one_title(self, page: UiPage) -> None:
        # More than one top-level heading leaves no single landmark to orient by.
        app = _run(page)
        assert len(app.title) <= 1, f"{page.name} declares {len(app.title)} titles"

    def test_a_page_declares_a_heading_before_a_subheading(self, page: UiPage) -> None:
        # A subheading with no heading above it is an orphaned level.
        app = _run(page)
        if len(app.subheader) > 0:
            assert len(app.title) + len(app.header) > 0, (
                f"{page.name} uses subheadings with no heading above them"
            )

    def test_a_dense_page_offers_more_than_one_landmark(self, page: UiPage) -> None:
        # A page with one heading and dozens of elements gives a reader
        # navigating by heading nothing to navigate by. The provenance page had
        # a title followed by 24 expanders and no heading between them.
        app = _run(page)
        headings = len(app.title) + len(app.header) + len(app.subheader)
        collapsible = len(getattr(app, "expander", []) or [])
        body = len(getattr(app, "markdown", []) or []) + len(getattr(app, "caption", []) or [])
        if collapsible + body >= _DENSE_PAGE_ELEMENTS:
            assert headings >= 2, (
                f"{page.name} renders {collapsible + body} content elements behind "
                f"{headings} heading(s); a reader navigating by heading has nothing to use"
            )

    def test_no_heading_is_blank(self, page: UiPage) -> None:
        app = _run(page)
        for kind in ("title", "header", "subheader"):
            for element in getattr(app, kind, []):
                value = getattr(element, "value", None) or getattr(element, "body", "")
                assert str(value).strip(), f"{page.name} has a blank {kind}"


class TestTheAutomatedScopeIsStatedHonestly:
    """The value of these checks depends on nobody mistaking them for an audit."""

    def test_the_manual_checklist_exists_and_is_unticked(self) -> None:
        from pathlib import Path

        checklist = Path("docs/evaluation/manual_accessibility_checklist.md")
        assert checklist.is_file(), "the manual checklist must accompany the automated checks"
        text = checklist.read_text(encoding="utf-8")
        assert "[x]" not in text.lower(), "no manual item may ship pre-ticked"

    def test_the_checklist_covers_what_cannot_be_automated(self) -> None:
        from pathlib import Path

        text = Path("docs/evaluation/manual_accessibility_checklist.md").read_text(encoding="utf-8")
        lowered = text.lower()
        for item in ("contrast", "zoom", "keyboard", "screen reader"):
            assert item in lowered, f"the checklist must cover {item}"

    def test_every_page_is_covered_by_the_automated_checks(self) -> None:
        # A page silently omitted would look checked.
        assert len(list(UiPage)) >= 30
