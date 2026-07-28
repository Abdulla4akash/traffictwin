# Evening-peak bus session — results, 28 July 2026

**Status: `owner_approved_candidate`, exploratory, descriptive, non-causal. Aggregate-only
session identity (`manchester-bods-session-identity-1.1`); no vehicle is linkable across
sessions, no raw identifier is published from an accepted snapshot, and the session salt
died with the process. Transit vehicles only — never general road traffic.**

Owner-triggered and owner-attended, opened at 17:13 BST because the evening peak was
running. It is the fourth density point and the **longest clean rush-hour window captured
to date**.

## What ran

| | |
|---|---|
| Window | 16:16:43Z – 17:49:40Z (17:16 – 18:49 BST) |
| Requested / accepted / refused | 85 / **83** / 2 |
| Runner | `scripts/bus_attended_session.py` (refusal-resilient; see below) |
| Interval | 65 s, one at a time, ≥60 s enforced by the accepted boundary |

An earlier launch of the pre-existing runner at 16:13Z died after 2 snapshots on the third
attempt's `PARSE_REJECTED`; that attempt's two accepted snapshots are separate evidence and
are not part of this session's measurement.

## Four density points, and one metric trap

**"Active" is not concurrency.** `vehicles_linked_across_snapshots` counts vehicles seen in
at least two snapshots across the whole session, so it grows with session length; the
per-snapshot vehicle count is the concurrency measure. Both are reported, and the
support figure is additionally **re-measured over a length-matched 52-snapshot prefix** so
it can be compared with the 52-snapshot morning session without the length artifact.

| Session | Snapshots | Seen | Active (support) | Cadence med / p90 | Displacement median |
|---|---|---|---|---|---|
| Night probe (27 Jul) | 15 | 872 | 41 | 68 / 75 s | 418 m |
| Shallow dawn | 52 | 1,676 | 1,162 | 67 / 76 s | 300.9 m |
| Morning peak | 52 | 1,677 | 1,433 | 66 / 75 s | 231.4 m |
| **Evening peak (full)** | **83** | **1,741** | **1,522** | **66 / 75 s** | **241.9 m** |
| **Evening peak (first 52, length-matched)** | 52 | 1,708 | **1,481** | 66 / 75 s | 230.2 m |

**Evening peak carries slightly more support than morning peak on a matched window —
1,481 against 1,433, +3.3%.** The full-session 1,522 is *not* the number to compare with
1,433; the matched 1,481 is.

### Concurrency, measured per snapshot

| | Max | Median |
|---|---|---|
| Morning peak (measured 28 Jul) | 1,216 | 1,192 |
| **Evening peak** | **1,250** | **1,215** |

Evening exceeds morning by 2.8% on the maximum and 1.9% on the median — essentially equal,
marginally higher in the evening. Both sit inside the capacity sweep's unresolved
(215, 2488] concurrency band, so the observed Manchester bus fleet remains the only real
fleet measured in the region where capacity was found to bind.

### The evening curve

The session captured a crest and a clean monotonic taper, which a single-point sample
cannot show:

| Local time | 17:16 | 17:41 | 18:02 | 18:13 | 18:24 | 18:36 | 18:47 |
|---|---|---|---|---|---|---|---|
| Concurrent vehicles | 1,240 | **1,250** | 1,228 | 1,177 | 1,135 | 1,060 | 999 |

The crest is at **17:41 BST**, and by the session's end the fleet is down 20.2% from it.

## Cadence and motion

- Update cadence **median 66 s, p90 75 s** — identical to the morning peak and consistent
  across all four sessions (66–68 s median), so the feed's cadence does not degrade with
  fleet size.
- Displacement median 241.9 m, p90 561.7 m.
- 133,922 observations; 35,786 repeated identical fixes.
- `update_delta_seconds_max` 86,659 s (≈24.07 h) with a paired 18,602 m displacement — a
  stale-resume artifact of the same kind seen in every prior session, not motion.
- **`implied_speed_mps_max` 66.79 m/s again exceeds the proposed 32 m/s B1 ceiling**
  (morning was 64.7 m/s). This reinforces, on a second peak window, the standing
  recommendation: keep 32 m/s and drop-and-count violating segments, publishing the retained
  share. It remains a recommendation, not a taken G2 decision.

## Two refusals, absorbed rather than fatal

Both are fail-closed `PARSE_REJECTED` refusals from lead-owned MAN-05, at attempts 20
(16:37:45Z) and 65 (17:27:33Z). Neither snapshot was promoted, measured, or admitted; both
sets of bytes stay in quarantine, and both are named in the session's refusal ledger.

**This is the point of the new runner.** The pre-existing runner catches only
`BodsLiveControlError`, so a `BodsAcquisitionError` ends the process — which is exactly how
today lost the morning peak after 51 promotions and the first evening attempt after 2. The
resilient runner records the refusal and continues the attended window, changing nothing
about the parser, the promotion rule, or the evidence boundary. Without it this session
would have ended at 19 snapshots and there would be no evening density point at all.

Replayed offline, both refusals are the same defect as the morning's — see
[the five-refusal diagnosis](../integration/evidence/man05_refusal_diagnosis_20260728.json).
Across all five of today's refusals: exactly one conflicting group, exactly two activities,
always different operators, and **zero** conflicts under
`(OperatorRef, VehicleRef, RecordedAtTime)`. BNGN appears in all five, ANWE in four, and
three of the four distinct colliding refs sit in the 3000 series where ANWE and BNGN
numbering overlaps.

## Boundaries

- Attended and owner-triggered; no unattended acquisition occurred.
- Aggregate-only measurement; session-scoped identity; salt not persisted; no cross-session
  linkage.
- Buses are never general traffic, and bus progression speed is never road speed.
- This session is new evidence and does **not** alter the frozen B-BUS dawn/peak traces or
  either Colab pack.
- No B1 experiment ran; G1–G5 remain unsigned owner decisions.
