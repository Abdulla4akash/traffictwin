# UI conventions

- Scope: `src/traffictwin/ui/`
- Status: enforced by tests in `tests/ui/test_accessibility.py`
- Last updated: 25 July 2026

These are the conventions the v0.7 UI actually follows, written down because three of them were
established by fixing drift that had already happened. Each is enforced by a test, so a convention
that stops being true fails the suite rather than quietly decaying again.

This document describes *presentation*. It does not relax anything in
[the v0.7 design](traffictwin-design-v0_7.md): no page computes a scientific metric, fetches
implicitly, launches a process, mutates raw evidence, or hides an unavailable state.

## Navigation

Seven task-oriented groups, each named for the question it answers, none larger than nine pages.
The grouping and every page's stable URL path are normative and live in the design document; the
navigation module and `tests/ui/test_navigation_v07.py` must agree with it.

A page's **URL path is permanent**. Regrouping is free; re-routing breaks bookmarks and deep links.

## Headings

**Sentence case**, not Title Case. It reads more easily and removes the per-word capitalisation
judgement, which had already produced headings like *Queue and Utilisation Over the Observed
Window* — capitalising "Over" and "the" is not correct Title Case under any style guide.

Acronyms, product names and requirement codes keep their case: `SUMO`, `DfT`, `WebTRIS`, `TOST`,
`LaTeX`, `RSU`, `Per-RSU`, `R7`, `R8`, `REP-02`.

**Page labels and page titles are not headings.** They are navigation identity and stay as they
are; changing one renames the page.

Prefer `section_header(title, description)` from `ui.components.cards` over a bare `st.subheader`.
It renders the same element plus an optional caption, so a section can say what it is for.

### Every page needs more than one landmark

A page carrying substantial content must offer at least two headings. The provenance page once
rendered a title followed by 24 expanders and nothing else: a sighted reader could scan expander
captions, but anyone navigating by heading had a single landmark for 84 elements.

## Progressive disclosure

Collapsed technical detail uses one prefix: **`Advanced:`**, defined once as
`labels.ADVANCED_DISCLOSURE_PREFIX`. It previously had three forms — `Advanced:`,
`Advanced/Evidence:` and a bare `Technical detail` — so the same control had to be learned more than
once, and the slash form read as two destinations rather than one kind of content.

Raw JSON, fingerprints, thresholds and long caveats belong behind it. Primary content is what a
reader needs to answer their question; the disclosure is what they need to check it.

**No two disclosures on one page may share a label.** Collapsed, an identical label is exactly the
point at which a reader has to choose between them.

## Controls

Every interactive control carries a label that identifies it out of context — "Click here" tells a
screen-reader user nothing. **No two controls on a page may share a label.** A sighted user tells
two buttons apart by position; a keyboard or screen-reader user cannot, which is how two buttons
both labelled *Plan an Experiment* survived on the home page.

## Unavailable states

An unavailable value is **never** hidden, estimated, defaulted, or replaced with zero.

`ui.components.unavailable.render_unavailable_panel` is the fullest expression of this: it shows an
`unavailable` badge, states plainly that the value is not estimated or filled with zero, and keeps
the missing evidence and reason codes on screen verbatim. Prefer it when unavailability is the
main thing a section has to report.

Five of the 39 pages currently use it; the rest express unavailability inline. That is not
automatically wrong — a state badge carrying the state with a caption explaining *why* is a correct
pattern, and several pages use it deliberately. What is wrong is a caption as the *only* signal,
because a caption is the least prominent element available and de-emphasising an unavailable state
is a way of hiding it.

When adding a section that can be unavailable, make the state visible in its own right, then
explain it.

## Why these are tested rather than documented alone

Every convention here was broken somewhere before it was written down, and in each case the break
was invisible: a duplicate button label reads fine to anyone looking at the screen, a third
disclosure prefix looks like a normal expander, and a heading in the wrong case looks like a
heading. Documentation alone would not have caught any of them.
