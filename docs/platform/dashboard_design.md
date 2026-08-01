# Design — Platform dashboard section (platform P-3)

**Status: PROPOSED design, `owner_approved_candidate` ceiling. Three new Streamlit
pages, strictly ADDITIVE under the house UI rules (nothing existing hidden or moved;
a11y label uniqueness; AppTest coverage). This is the surface the 11–22 Aug
participants evaluate (P-D3 resolved yes).**

## 1. Page: Data Inventory

One honest table of everything the platform has ingested, sourced from what already
exists on disk — workspace receipts, quarantine manifests, registry rows, session
records — with per-dataset: source, acquisition mode (attended / scheduled / archive),
row-or-snapshot count, last-updated, receipt digest, and a freshness cell. Freshness is
the scheduled runner's de-facto monitor: a missed window shows as a gap, in the open,
rather than an alert nobody reads. The inventory also lists the **private diagnostic
archives** (the GPU-track preservation records and homecoming evidence) by their
committed records — sha, date, and status string verbatim, including `NON_ADMITTED`
and deviation labels — because an inventory that omits the non-admitted work would
understate what exists, and one that showed it unlabelled would overstate what it
proves. Read-only; no acquisition can be triggered from the page (the acquisition
boundary stays where it is).

## 2. Page: Forecasts

The [bus prediction layer](bus_prediction_design.md) rendered honestly: hourly
concurrency and progression-speed climatology with intervals, support counts printed on
every cell, `insufficient_support` cells shown as exactly that, fit digest + source
session count in the caption, and — once the held-out verdict exists — the verdict
(including a null) displayed with the same prominence as the curves. `FORECAST — NOT
EVIDENCE` banner throughout. The measured series (four density points, the hourly
speed–density line) plots beside the model so a viewer sees data and model together.

## 3. Page: What-If Composer

The [composer](whatif_composer_design.md) UI: scenario form → prediction card (typed
banner, intervals, regime label) or refusal card (the named gap + the tier-2 offer) →
draft-campaign action producing the design + unsigned predeclaration, with the
signing/execution steps described as instructions to a human, never buttons that do
them. A predictions-vs-measurements table at the bottom grows as verifications land —
the platform's honesty exhibit, empty at launch and visibly so.

## 4. Navigation and framing

One new "Platform" group in the existing seven-group navigation (additive), pages
ordered Inventory → Forecasts → What-If. Each page opens with a one-line scope banner
naming what is and is not claimed — the participant-facing articulation of the label
ceilings the project already enforces internally.

## 5. Testing and evaluation hooks

AppTest suites per page (render, empty-states, banner presence, label uniqueness);
a11y checks extend the existing 34-page suite. Empty states matter more than usual:
participants may see the platform before weeks of scheduled data exist, so
inventory-with-gaps, forecasts-with-thin-support, and an empty honesty table must each
read as designed honesty, not brokenness — first-run guidance follows the UX-02
additive pattern. The user-evaluation instrument gains 2–3 platform tasks (find a
dataset's freshness; read a forecast's support; compose a scenario and say what the
refusal means) — drafted for the owner to approve alongside the existing instrument.

## 6. Out of scope for v1

A decision layer (recommendations) — the platform reports evidence and predictions;
recommending is a distinct epistemic act deferred deliberately and recorded in the plan;
editing schedules from the UI; any write action against workspaces or registries.
