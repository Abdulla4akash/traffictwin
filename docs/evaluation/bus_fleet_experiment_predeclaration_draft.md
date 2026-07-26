# Real Bus-Fleet Offloading Experiment (B1) — DRAFT (NOT SIGNABLE YET)

**Status: structural draft; cannot be signed, approved, or executed in this form.** Fields
marked `FILL-FROM-PROBE` require the attended cadence session's measured values, and fields
marked `FILL-AT-SIGNING` are owner choices. This is the predeclaration skeleton for option B1
of [the bus experiment options](bus_data_experiment_options.md), fixed in structure before any
trajectory has been derived.

- Drafted: 27 July 2026, during the first attended cadence-probe session
- Consumes: one owner-attended observation session (F2 window), the session-scoped identity
  policy `manchester-bods-session-identity-1.0` (F0, implemented), the accepted Greater
  Manchester network, VEC-06 preprocessing, and the campaign instrument (ADR-061/063)
- Policy label ceiling: `owner_approved_candidate`

## 1. Question and hypothesis

**Question.** How do the two audited offloading policies behave when the vehicle population is
a real observed Manchester bus fleet — sparse, schedule-structured, a few hundred concurrent
vehicles — rather than the dense synthetic car fleets they were trained against?

**Predeclared hypothesis (H1).** The training-distribution advantage inverts or shrinks: the
UK-2030-trained actor's margin over the baseline actor on synthetic fleets does not transfer to
the observed bus fleet (the Year-1 distribution-shift claim, evaluated on genuinely observed
Manchester vehicles).

**Publishable null (H0), fixed now.** If the margin transfers essentially unchanged, that is a
reportable robustness result of equal standing.

## 2. Honest labels, fixed before construction

- The trace is a **derived scenario from observed bus positions with declared interpolation**
  — never "observed FCD", never "real traffic". Buses are buses throughout.
- RSU placement is VEC-06's generated static analysis placement, labelled as such.
- Task workloads are the evaluator's synthetic generation model; only the *fleet motion* is
  observation-derived. Every artifact states this composition explicitly.
- Session identity is linkable within the one declared session only; the salt is destroyed at
  session end; no raw identifier survives into any artifact.

## 3. Trace construction rules

| Rule | Value |
|---|---|
| Observation session | `FILL-AT-SIGNING` (proposed F2 default: weekday 08:00–09:30 local, ~85 snapshots at 65 s) |
| Measured per-vehicle update interval | `FILL-FROM-PROBE` (median / p90 seconds) |
| Interpolation | along the map-matched road path between successive fixes, constant progression between fix times; never straight-line through buildings |
| Gap ceiling | drop a vehicle's segment when successive fixes exceed `FILL-AT-SIGNING` s (proposed F5 default 120 s); dropped coverage is reported, never invented |
| Dwell handling | fixes within `FILL-AT-SIGNING` m (proposed 15 m) treated as dwell at the matched stop location |
| Map-matching | existing candidate machinery against the accepted Greater Manchester network; per-vehicle matched-share and error budget published; vehicles below `FILL-AT-SIGNING` matched-share (proposed 80%) excluded with counts |
| Resolution | one-second positions as VEC-06 requires, derived per the above and labelled derived |
| Trace window | the longest contiguous span with ≥ `FILL-AT-SIGNING` linked vehicles (proposed 100) |

## 4. Design (structure fixed; cells at signing)

- Both actors over the identical derived trace and seeds — an actor contrast, so the method is
  **N-way ranking per capacity level** (STA-01 cannot express actor contrasts; recorded
  constraint), plus descriptive per-actor capacity curves.
- Capacity levels: `FILL-AT-SIGNING`, defaulting to the pilot's baseline (2.5) plus the
  confirmatory knee level, mirroring the crossover study's grid for comparability.
- Fleet seeds: fresh set disjoint from all existing cohorts, `FILL-AT-SIGNING` (proposed
  `{30, 31, 32, 33, 34}`); note the evaluator's fleet preset still assigns vehicle *types* —
  the observed component is motion, and the report says so.
- Execution through the approval-gated campaign instrument; admission through fresh-run
  admission; analysis through the exploratory harness. Nothing bypasses the existing gates.

## 5. Viability gate before any campaign

The derived trace must pass VEC-06's own validation and a predeclared sanity check: implied
speeds within `FILL-AT-SIGNING` m/s (proposed 25), monotone per-vehicle timestamps, occupancy
reconciliation, and a published interpolated-versus-observed share per vehicle. A trace
failing any check is a published refusal, not a tuning exercise.

## 6. Owner decisions at signing

| # | Decision | Proposed default |
|---|---|---|
| G1 | Session window | weekday 08:00–09:30 local |
| G2 | Gap ceiling / dwell radius / matched-share floor | 120 s / 15 m / 80% |
| G3 | Capacity levels | pilot baseline + confirmatory knee level |
| G4 | Fleet seeds | `{30–34}`, disjoint from pilot, held-out, and crossover sets |
| G5 | Scheduling | after the capacity confirmatory campaign; sessions may run earlier (attended, I/O-only) |

**Sign-off (a person completes this; an agent never does):**

- Cadence measurement attached (fingerprint): ______________________
- Decisions G1–G5: ______________________
- Approved by / role / date: ______________________
