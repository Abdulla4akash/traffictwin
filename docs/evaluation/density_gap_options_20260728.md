# Closing the (215, 2488] density gap — options, 28 July 2026

**Status: decision memo. Options are presented and costed; none is taken. The recommended
option (C) needs no decision and is queued; options A and B are owner/lead territory.**

## The gap

The capacity programme is closed except for one hole. Capacity is exactly inert at 139, 163,
175 and 215 concurrent slots, and binds at 2,488. **Saturation onset is bracketed in
(215, 2488] and nothing we hold sits inside it.** The real observed bus fleet — peak
concurrency ~1,216–1,250, measured twice — falls in that band, which is what makes the gap
worth closing rather than merely noting.

## Why the obvious approach is blocked

Subsampling the `inc` trace to intermediate densities would answer it directly. It cannot be
done within current boundaries:

**The runner has no fleet-size control.** `VecRunRequest` exposes `fleet`, `fleet_seed`,
`rsu_capacity_per_vehicle` and `max_steps` — nothing that limits concurrent vehicles.
`trace_slots` is an *observed output*, not a request knob. So density can only be changed by
changing the trace.

That leaves two routes, both above this agent's authority:

### Option A — admit a derived trace *(owner/lead decision, ADR-class)*

Construct reduced-slot `inc` variants and admit them through the allowlist.

**Why this is not a reasonable choice to take unilaterally:** every prior allowlist extension
(ADR-062, ADR-065, ADR-066) admitted an **audited producer artifact** whose hashes reconcile
against the Gate-A table. A derived trace has no Gate-A hash — it is ours. Admitting one
changes what the allowlist *means*, from "audited traces only" to "audited traces plus
constructions we vouch for".

**The project's own precedent points the other way.** The B-BUS derived traces were
deliberately kept **outside** VEC-06 admission — the Sparse-64 arm is recorded as
"exploratory outside accepted VEC-06; it cannot inherit the corridor arm's contract status".
Admitting a derived `inc` would contradict that stance.

Cost if approved: trace construction and validation, a new ADR, ~24 h compute for a 4-density
× 2-arm × 3-seed sweep.

### Option B — add a slot-subset control to the runner *(lead decision)*

Extend `VecRunRequest` with a vehicle-subset control.

Changes an accepted VEC-07 interface and its fingerprints, and introduces a control whose
semantics ("which vehicles?") need their own predeclaration. Lead-owned surface.

## Option C — map the onset curve from the low end, using only admitted traces *(recommended; no decision needed)*

The gap can be attacked from below without any derived trace.

**The observation.** Binding onset is not a fixed capacity — it moves with density. On `ev`
(175 slots) outcomes are inert at cap-0.5 and cap-0.25 and bind only at cap-0.1. On `inc`
(2,488 slots) latency responds across the whole range from cap-2.5 down. So onset capacity
falls as density falls, and the two known points differ by ~25× in onset capacity against
~14× in density — the same order.

**The hypothesis, stated before running:** *onset capacity scales with concurrent density*,
approximately `c_onset ∝ N`. If it holds, the four low-density traces should show onset at
capacities ordered by their slot counts (139 < 163 < 175 < 215), and the fitted relation
**extrapolates a prediction for the unresolved band** which `inc` already constrains.

**Why it is cheap.** The low-density traces are minutes per run, not the collapse hour's
~59 min: `we` measured at 225.7 s and `ev` at 265.9 s per run. A deep-squeeze sweep of
4 traces × 4 arms × 3 seeds ≈ 48 cells lands in roughly **4 hours**, not 24.

**What it cannot do.** It locates the onset *curve* from below and extrapolates into the gap;
it does not directly observe a 1,000-slot regime. An extrapolation is weaker evidence than a
measurement, and would be labelled as such. If the fitted relation predicts `inc`'s behaviour
correctly that is meaningful support; if it does not, the scaling hypothesis is refuted,
which is also worth having.

## Recommendation

Run **C** now — it is free of decisions, cheap, and turns an unresolved bracket into a
testable scaling law with a prediction that `inc` independently checks.

Treat **A** as the follow-up *only if* C's extrapolation proves interesting enough to justify
an ADR that loosens what the allowlist guarantees. That ordering keeps the evidence boundary
intact until there is a measured reason to revisit it.

**B** is recorded for completeness and is not recommended: it changes an accepted interface
to answer one question, when C answers most of it for free.

## Boundaries

- No derived trace has been constructed, admitted, or proposed for admission here.
- No accepted interface has been modified.
- The five admitted traces and their allowlist are untouched.
