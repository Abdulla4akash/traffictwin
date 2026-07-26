# Live Bus Data — Experiment Options Assessment (PROPOSED)

**Status: options assessment for an owner decision. Nothing here is signed, and no acquisition
or experiment runs from this document.** The owner directed on 27 July 2026 that the BODS
live-bus capability must be used for experiments; this document says what is honestly possible,
what each option costs, and which decisions only the owner can make.

- Grounded in measured evidence, not assumption:
  [the accepted Bee Network probe](../integration/evidence/manchester_bods_bee_network_probe_20260723.json)
  and the accepted MAN-05 acquisition boundary
  ([live scene](../integration/manchester_bods_live.md),
  [controlled refresh](../integration/manchester_bods_live_control.md))
- Policy label ceiling: `owner_approved_candidate`

## 1. Measured starting facts

From the accepted 23 July 2026 snapshot (22:39 UTC, evening service):

| Fact | Value |
|---|---|
| Records accepted in one Greater Manchester snapshot | 1,565 |
| Concurrently **live** vehicles | **304** (1,261 stale-labelled retained) |
| Distinct operators | 27; the five verified Bee operators contribute ~1,370 records |
| Acquisition cadence bound | **≥ 60 s between requests, one at a time, human-triggered** |
| Snapshot form | immutable, receipted, private; raw identifiers never published |

Two consequences frame every option. First, a real concurrent fleet of hundreds exists — the
same order as the audited weekend trace's 139 slots, so fleet-scale experiments are numerically
plausible. Second, an "observation session" under the accepted boundary is a **human-initiated
sequence of receipted snapshots at 60-second cadence** — there is no continuous stream, and any
finer-grained trajectory is a *derived, interpolated* artifact that must say so.

## 2. The boundaries every option inherits

- Buses are never general traffic; every design below is explicitly a **bus** study.
- Import-first: experiments consume immutable snapshots offline; nothing evaluates live.
- Retention/republication terms are unresolved (`BETA-B-01`), so raw snapshots stay in the
  private workspace and only bounded aggregates are publishable.
- Vehicle identifiers are pseudonymised in anything that leaves the workspace.
- No always-on daemon: sessions are bounded, attended, and receipted.
- Retrieval time is never observation time; each record's own `RecordedAtTime` governs.

## 3. The options, strongest first

### B1 — Offloading policies on a real observed bus fleet (recommended)

**Question.** How do the two audited offloading policies behave when the vehicle population is
a *real observed Manchester bus fleet* — sparse, schedule-structured, a few hundred concurrent
vehicles — rather than a dense synthetic car fleet? This evaluates the Year-1 report's central
distribution-shift concern on genuinely observed Manchester data, and it is the only option
that connects the bus capability directly to the dissertation's core VEC chain.

**Construction.** One owner-attended acquisition session (proposed: 60–90 minutes, snapshot
every 60 s → 60–90 receipted snapshots, ideally a weekday peak); map-match observed positions
to the accepted Greater Manchester network with the existing MAN-09 machinery; derive a
one-second trace by **declared interpolation along the matched road path** between successive
observations; admit through VEC-06 as a preprocessing receipt; run VEC-07 + fresh admission +
a campaign under a predeclared design (capacity squeeze and/or actor contrast on the bus
fleet).

**Honest labels required.** The trace is a *derived scenario from observed bus positions with
declared interpolation* — never "observed FCD". With ~60 s between observations and buses at
5–10 m/s, roughly 300–600 m of each vehicle's path between fixes is interpolated; the
interpolation policy (path-following, dwell handling, gap ceiling beyond which a vehicle is
dropped rather than invented) is an owner-approved candidate policy with its own
predeclaration. RSU placement is VEC-06's generated static placement, labelled as such.

**Cost and open items.** The largest option: an attended session, an interpolation-policy
predeclaration, map-matching at bus-GPS accuracy (a measured error budget, reusing the
existing candidate machinery), VEC-06 admission, then the campaign. Estimated several working
days plus the session. Decisive unknown to measure *first*: the per-vehicle `RecordedAtTime`
update distribution — if positions update well inside 60 s, consecutive snapshots may carry
denser observation times than the request cadence suggests, shrinking the interpolation gaps.

### B2 — Bus progression versus the DfT temporal profile (cross-source consistency)

**Question.** Do observed bus progression speeds by hour, on corridors with bound DfT count
sites, vary consistently with the accepted DfT hourly demand profile? A descriptive
cross-source plausibility study: two independent real sources, one city.

**Construction.** Two or three attended sessions across contrasting hours; per-corridor bus
speed aggregates from successive matched positions; comparison against the profile's hourly
shape, reported descriptively with denominators and no causal language. Cheaper than B1 (no
interpolation to one second, no VEC admission); needs multiple sessions for hour coverage.
Dissertation link: moderate — strongest if the journey-time research direction is chosen.

### B3 — The bus-structured corridor SUMO scene (existing stretch goal, unchanged)

The already-sanctioned Oxford Road-style corridor: historical bus structure (routes, stops,
dwell) in one SUMO scene, DfT counts still carrying road demand, evaluated through VEC-06.
Highest cost, entangled with MAN-09's demand-health work, and already rated a time-boxed
stretch goal by the completed-possibility rubric. This document does not change its status.

### B4 — Headway and punctuality descriptives (cheapest, weakest link)

Headway regularity and delay distributions for Bee services from session snapshots. Honest and
quick, but connects to no current research question; worth doing only as a by-product of B1/B2
sessions, not as its own experiment.

## 4. Recommended sequence

1. **Cadence probe first (one short attended session):** 10–15 snapshots at the 60 s bound,
   then measure the per-vehicle `RecordedAtTime` update distribution and position accuracy
   against the matched network. This is one evening's work, produces a published measurement
   either way, and decides B1's interpolation gap honestly before anything is designed around
   an assumption.
2. **If the cadence supports it, predeclare and run B1** — it is novel, core-connected, and
   reuses nearly everything already built (network, matching, VEC-06/07, fresh admission,
   campaigns, analysis).
3. **B2 sessions piggyback** on any B1 session at no extra acquisition cost.

## 5. Owner decisions required

| # | Decision | Proposed default |
|---|---|---|
| F1 | Run the cadence probe session? | yes — one attended 15-minute session at 60 s cadence |
| F2 | Session window for B1, if pursued | weekday 08:00–09:30 local (peak service density) |
| F3 | Which experiment(s) | B1 primary; B2 as by-product; B4 only as by-product; B3 unchanged |
| F4 | Where B1 sits against the existing programme | after the capacity pilot's confirmatory protocol is signed, before the corridor stretch |
| F5 | Interpolation gap ceiling for B1 | drop a vehicle's segment when successive fixes exceed 120 s apart, rather than inventing it |

**Sign-off (a person completes this; an agent never does):**

- Decisions taken: ______________________
- Approved by / role / date: ______________________
