# Predeclaration addendum — operationalising the onset-scaling hypothesis

**Status: PROPOSED, exploratory. `owner_approved_candidate` ceiling. Not supervisor-approved,
not confirmatory, no significance claimed. Fresh seeds {60, 61, 62}; the held-out cohort
{10–14} is spent and untouched.**

Written **before any cell of the `we-deep`, `wd-am-deep` or `wd-pm-deep` legs had run** — at
the time of writing all three output directories are empty and the chain is still queued
behind `inc-deep` and `inc-baseline`. The state is recorded in §6 so the claim is checkable
against git history rather than asserted.

## 1. Why an addendum exists

`density_gap_options_20260728.md` §"Option C" states the hypothesis the three onset legs
test:

> *onset capacity scales with concurrent density*, approximately `c_onset ∝ N`. If it holds,
> the four low-density traces should show onset at capacities ordered by their slot counts
> (139 < 163 < 175 < 215).

That is a direction, not a decidable prediction. It never says **what counts as onset**, and
without that the threshold could be chosen after the arms are visible — the exact failure the
ceiling-law predeclaration was written to avoid. This addendum fixes the measurement rule, the
per-trace predictions and the verdict rule in advance.

**It does not touch the memo.** `density_gap_options_20260728.md` is byte-frozen at
`00681a14…` because three launched campaign designs bind that digest; editing it would break
their approval check and their resume. This is a separate analysis-side document with no
campaign design bound to it.

## 2. The measurement rule — onset, defined

The rule is **transcribed, not invented**. The committed five-regime and deep-squeeze records
already judge capacity response by exact identity — *"every metric exactly identical across
all four standard capacity arms in every seed (paired diffs literally 0.000000)"*. That is the
criterion adopted here verbatim:

- An arm is **inert** on a trace when, for **every** metric in the campaign analysis and
  **every** seed, its value equals the baseline arm's (`cap-2.5`) value **exactly**.
- An arm **binds** when it is not inert — any nonzero difference, in any metric, at any seed.
- The **measured onset** `c_onset(T)` on the {0.5, 0.25, 0.1} grid is the **largest** arm
  capacity that binds. If no deep arm binds, onset is **censored below the grid floor**,
  recorded as `< 0.1` and never as a number.

There is no tolerance parameter, because there is nothing to tune: across five traces the
observed differences have been either exactly zero or clearly nonzero. If an arm ever binds at
a higher capacity than one that is inert below it, that non-monotonicity is flagged in the
output rather than smoothed over.

## 3. The prediction, propagated from the one measured onset

`ev` (175 slots) is the only trace whose onset has been bracketed: `cap-0.25` is exactly
identical to baseline, `cap-0.1` binds. So `c_onset(ev) ∈ (0.1, 0.25]`, and proportionality
`c_onset = κ·N` gives `κ ∈ (5.714·10⁻⁴, 1.4286·10⁻³]`.

The prediction is therefore a **band, not a point** — the bracket is propagated rather than
collapsed to a convenient midpoint:

| Trace | Slots `N` | Predicted `c_onset` band |
|---|---|---|
| `we` | 139 | (0.0794, 0.1986] |
| `wd_pm` | 163 | (0.0931, 0.2329] |
| `wd_am` | 215 | (0.1229, 0.3071] |
| `inc` | 2,488 | (1.4217, 3.5543] |

An arm binds iff its capacity is at or below `c_onset`. Applying that to the {0.5, 0.25, 0.1}
grid gives six **decidable** predictions and three cells the sweep *resolves* rather than
tests:

| Arm | `we` (139) | `wd_pm` (163) | `wd_am` (215) |
|---|---|---|---|
| cap-0.5 | **inert** | **inert** | **inert** |
| cap-0.25 | **inert** | **inert** | indeterminate |
| cap-0.1 | indeterminate | indeterminate | **binds** |

**Where the weight actually sits.** Five of the six sharp predictions are *inert* predictions,
and inertness is what four traces have shown at every capacity ever tried — they are close to
free. The single prediction that can genuinely fail is **`wd_am` binds at cap-0.1**. That is
the load-bearing claim of this addendum and it should be read as the test; the rest is
bookkeeping. It is stated plainly here so that a reader does not have to notice it
independently.

## 4. Verdict rule, fixed now

- **HELD** — all six sharp predictions are correct.
- **REFUTED** — any one of the six is wrong.

Two descriptive qualifiers are reported **alongside** the verdict, never in place of it, so
that a refutation says *how* it failed:

1. `ordering_preserved` — whether the measured onsets are weakly ordered by density,
   `c_onset(we) ≤ c_onset(wd_pm) ≤ c_onset(ev) ≤ c_onset(wd_am)`, with censored traces
   treated as tied below the floor. A refutation with the ordering intact means onset still
   moves with density but not at ev's constant; a refutation with the ordering broken means
   density is not the governing variable at all.
2. `all_censored_at_floor` — whether every deep arm on all three traces was inert, so onset
   lies below 0.1 everywhere and the grid could not locate it. This still refutes the
   prediction (it requires `wd_am` to bind at 0.1) but bounds `κ` from above instead of
   measuring it.

If any leg has not produced a campaign analysis, the verdict is **INCOMPLETE** and the missing
legs are named. Missing data is never read as a passed prediction.

## 5. What this cannot show

- Onset is located on a **three-point grid** whose steps are 2–2.5× apart, across four traces
  spanning only 1.5× in density (139→215). The grid may simply lack the resolution to order
  them, and a tie at the floor is a predeclared outcome, not a failure of the run.
- `inc` is a **consistency check, not a test**: the pilot shows `cap-1.5` differs from
  `cap-2.5`, so `c_onset(inc) ≥ 1.5`, which is inside the predicted (1.4217, 3.5543] band —
  but with no arm above 2.5 the band's upper half is unobserved.
- Extrapolation into the unresolved (215, 2488] density band remains extrapolation, and stays
  labelled as such however the verdict falls.
- Nothing here changes the evidence boundary: no derived trace, no new admission, no interface
  change. The five admitted traces and their allowlist are untouched.

## 6. State at the time of writing (checkable against git)

| Fact | Value |
|---|---|
| `data/vec-fresh/capacity-deep-we` | does not exist — 0 of 12 cells run |
| `data/vec-fresh/capacity-deep-wd-am` | does not exist — 0 of 12 cells run |
| `data/vec-fresh/capacity-deep-wd-pm` | does not exist — 0 of 12 cells run |
| Chain position | queued behind `inc-deep` (2/12) and `inc-baseline` (0/12) |
| Source memo digest | `00681a14efb5b7134fb81abae0f365c27148972723d6ae3140deecfd2254ef3a` (unmodified) |
| Verdict code | `scripts/verify_onset_scaling_prediction.py`, committed with this file |

The verdict code is committed in the same commit as this document and re-hashes it at run
time, so neither the rule nor the predictions can be adjusted once the arms are visible.

## Sign-off

| Field | Value |
|---|---|
| Proposed by | primary research/integration agent |
| Approved by | *(relayed delegation, recorded at execution; not an owner-typed signature)* |
| Supervisor approval | **none — not sought, not implied** |
