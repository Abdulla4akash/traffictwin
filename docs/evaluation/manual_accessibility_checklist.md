# Manual accessibility checklist (Gate C, UX-03)

- Status: **unticked**; no item has been performed
- Scope: the v0.7 Streamlit page set
- Companion to the automated checks in `tests/ui/test_accessibility.py`

## What this checklist is for

The automated checks establish what the rendered element tree can prove: that every interactive
control carries a usable, informative, non-duplicated label, and that heading structure is coherent.
They run over every page on every test run.

They are **not an accessibility audit**, and they cannot accept Gate C. Four things matter and none
of them can be established from the element tree:

| Cannot be automated | Why |
|---|---|
| Contrast ratio | needs the rendered colours of a real browser, not the element tree |
| Zoom and reflow | needs a viewport at 200% and 400% |
| Keyboard traversal order | Streamlit does not expose DOM tab order to the test harness |
| Screen-reader announcement | needs assistive technology and a person using it |

Approximating any of these and reporting a pass would be worse than an honest gap, so they are
listed here for a person instead.

**No screen-reader user, participant, or assistive-technology session has been invented anywhere in
this repository.** This checklist ships unticked and unsigned, and must be completed by a person
before any Gate-C accessibility claim is made.

## Keyboard

- [ ] Every interactive control is reachable using only Tab and Shift+Tab.
- [ ] Tab order follows the visible reading order on each page.
- [ ] Focus is always visible; no control receives focus without a visible indicator.
- [ ] No keyboard trap: focus can always leave a control, an expander, and a dialog.
- [ ] Every action available by pointer is available by keyboard.
- [ ] Skipping to the main content does not require tabbing through the whole navigation.

## Contrast and colour

- [ ] Body text meets WCAG 2.2 AA contrast (4.5:1) in both light and dark themes.
- [ ] Large text and UI component boundaries meet 3:1 in both themes.
- [ ] No state is signalled by colour alone; an unavailable state carries text as well.
- [ ] Charts remain readable in greyscale, or carry a non-colour encoding.
- [ ] Focus indicators meet contrast against both the control and the background.

## Zoom and reflow

- [ ] At 200% browser zoom no content is lost and no horizontal scrolling is required.
- [ ] At 400% zoom the page reflows to a single column without overlapping content.
- [ ] Tables and wide evidence blocks scroll within their own container, not the page.
- [ ] Text spacing overrides (line height 1.5, paragraph spacing 2em) do not clip content.

## Screen reader

- [ ] Each page announces a single, meaningful top-level heading.
- [ ] Heading levels descend without skipping.
- [ ] Every control announces a label that identifies it out of context.
- [ ] Unavailable states announce *why* they are unavailable, not merely that they are.
- [ ] Status changes after an action are announced without needing to hunt for them.
- [ ] Data tables announce their column headers.

## Recording the outcome

Record the browser, assistive technology, versions and date beside each section. An item left
unticked is an item not done — it is never inferred from a passing automated check.

| Role | Name | Date | Signature |
|---|---|---|---|
| Performed by | | | |
| Reviewed by | | | |
