# Real Bus-Fleet Offloading Experiment (B1) — DRAFT (NOT SIGNABLE YET)

**Status: structural draft; cannot be signed, approved, or executed in this form.** The
`FILL-FROM-PROBE` measurements are now proposed below from the 28-July peak session;
`FILL-AT-SIGNING` values and the response to measured speed outliers remain owner choices.
This is the predeclaration skeleton for option B1 of
[the bus experiment options](bus_data_experiment_options.md), fixed in structure before any
trajectory has been derived.

- Drafted: 27 July 2026, during the first attended cadence-probe session
- Consumes: one owner-attended observation session (F2 window), the session-scoped identity
  policy `manchester-bods-session-identity-1.1` (F0, operator-scope correction measured and
  implemented), the accepted Greater
  Manchester network, VEC-06 preprocessing, and the campaign instrument (ADR-061/063)
- Policy label ceiling: `owner_approved_candidate`

## 1. Question and hypothesis

**Question.** How do the two audited offloading policies behave when the vehicle population is
a real observed Manchester bus fleet — schedule-structured, with 1,433 active identities in
the measured peak session — rather than the dense synthetic car fleets they were trained
against?

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
| Observation session | `FILL-AT-SIGNING`; proposed measured source: 28 July 2026, 08:02–08:58 BST, 52 verified quarantines (51 MAN-05 promoted + final fail-closed refusal) |
| Measured per-vehicle update interval | **median 66 s / p90 75 s** (peak); stable across night/dawn/peak at median 66–68 s and p90 75–76 s |
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
speeds within `FILL-AT-SIGNING` m/s, monotone per-vehicle timestamps, occupancy
reconciliation, and a published interpolated-versus-observed share per vehicle. The earlier
proposed 32 m/s ceiling now has a measured conflict: the corrected peak aggregate contains a
64.7 m/s maximum. A person must choose the response before derivation. The recorded
recommendation is to retain 32 m/s, drop and count violating segments, and publish retained
coverage rather than raise the ceiling post hoc; it is not an agent-taken G2 decision. A trace
failing the signed rule is a published refusal, not a tuning exercise.

**Session facts informing the gates:** night = 41 active; dawn = 1,162; peak = 1,433.
Peak cadence is median 66 s / p90 75 s, median displacement 231.4 m, and 20,997 of 82,722
observations are repeated identical fixes. The longest peak stale-resume gap is 64,873 s,
confirming that a finite gap ceiling is necessary. Full measurement and the two recurring
MAN-05 `CONFLICTING_ACTIVITY` refusals are recorded in
[the session result](bus_session_results_20260728.md).

## 6. Owner decisions at signing

| # | Decision | Proposed default |
|---|---|---|
| G1 | Session window | measured peak range 08:02–08:58 BST (52 quarantines) |
| G2 | Gap ceiling / dwell radius / matched-share floor / speed-outlier response | 120 s / 15 m / 80%; speed rule unresolved (recommend retain 32 m/s and drop+count violations) |
| G3 | Capacity levels | pilot baseline + confirmatory knee level |
| G4 | Fleet seeds | `{30–34}`, disjoint from pilot, held-out, and crossover sets |
| G5 | Scheduling | after the capacity confirmatory campaign; sessions may run earlier (attended, I/O-only) |

**Sign-off (a person completes this; an agent never does):**

- Candidate cadence attachment for the person to confirm: peak fingerprint
  `1e5ec631d989e10fc086d634ff5f5aae4cec7831d0a59faf1e9d12afff244417`
- Cadence measurement attached (fingerprint): ______________________
- Decisions G1–G5: ______________________
- Approved by / role / date: ______________________
