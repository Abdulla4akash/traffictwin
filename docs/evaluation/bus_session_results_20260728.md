# BODS Bus Sessions — Post-Hoc Measurement Results (28 July 2026)

**Status: descriptive `owner_approved_candidate`, aggregates only, non-causal. No bus
experiment has run. B1 remains unsigned and cannot execute until a person completes
G1–G5. Buses remain buses; none of these counts is general road traffic.**

## Processing contract

The already-captured quarantines were processed offline with no acquisition, API key,
network request, or attendance step. Each explicit snapshot range received a fresh
in-process salt under `manchester-bods-session-identity-1.1`; the salt died with the
process. The accepted report command then read only the written cadence/progression
aggregates. Artifact hashes and exact quarantine provenance are in the committed
[evidence record](../integration/evidence/bods_bus_sessions_20260728.json); private
aggregate views are under `session-records/{night-20260726,dawn-20260728,peak-20260728}`
inside the v0.7 workspace.

The peak range contains 52 verified quarantines: 51 promoted MAN-05 snapshots plus the
final fail-closed quarantine. Its bytes were **not** promoted into a scene. The separate
session-identity layer could reduce it to non-identifying aggregates after its own hash
and structure checks; this does not reverse or weaken the MAN-05 refusal.

## Three-density result

"Active" means one operator-scoped session pseudonym with at least two distinct recorded
times in the declared session. It is a session-support count, not a simultaneous road
traffic count.

| Session | Local captured window (BST) | Snapshots | Vehicles seen | Active | Median / p90 update | Repeated identical fixes | Median displacement |
|---|---|---:|---:|---:|---:|---:|---:|
| Night | 00:40–00:56 | 15 | 872 | **41** | 68 / 75 s | 11,672 / 12,960 (90.1%) | 417.9 m |
| Shallow dawn | 06:12–07:09 | 52 | 1,676 | **1,162** | 67 / 76 s | 39,502 / 82,189 (48.1%) | 300.9 m |
| Morning peak | 08:02–08:58 | 52 | 1,677 | **1,433** | 66 / 75 s | 20,997 / 82,722 (25.4%) | 231.4 m |

The cadence is strikingly stable across density (median 66–68 s, p90 75–76 s), while
usable linked-fleet support changes radically: dawn is 28.3× night, peak is 35.0× night,
and peak is 23.3% above dawn. Dawn already supplies 81.1% of peak's active support. The
night probe was valid for cadence but not representative of daytime fleet density.

## Real identity defect found by the longer sessions

The v1.0 layer tokenised bare `VehicleRef`. The long sessions proved that field is not
feed-global: 7 dawn and 9 peak values occur under more than one `OperatorRef`. Merging
those vehicles manufactured maxima of 18.7 km/s and 17.4 km/s. Policy v1.1 now tokens
`OperatorRef || NUL || VehicleRef`, retaining the same per-session salt/privacy boundary;
the corrected maxima are 38.0 m/s (dawn) and 64.7 m/s (peak). Historical v1.0 aggregate
JSON remains readable, and the night result is numerically unchanged under v1.1.

The corrected maxima still expose a small GPS/feed-outlier problem rather than licensing
a larger B1 speed ceiling. The existing proposed 32 m/s ceiling is exceeded, so signing
must choose and predeclare the response. **Recommended for the owner to consider:** keep
32 m/s as the plausibility ceiling, drop and count violating segments, and publish the
retained share; do not raise the ceiling post hoc merely to admit the 64.7 m/s jump. This
is a recommendation, not a taken G2 decision.

## The two rush-hour parser refusals

Offline replay of both preserved refusals gives the same exact result:

- MAN-05 code `CONFLICTING_ACTIVITY`;
- one conflicting raw-ref/time group containing two activities;
- the two activities belong to different operators;
- scoping the group by operator leaves zero conflicts.

The first occurred after one promoted snapshot in the abandoned 07:57 BST attempt; the
second ended the 08:02–08:58 BST retry after 51 promotions. This is a recurring
rush-hour identity-scope gap in lead-owned MAN-05, not malformed XML and not an
acquisition failure. The parser remains untouched; its correction is a lead/Codex
coordination slice. Both quarantines and byte identities remain preserved in the evidence
record.

## B1 FILL-FROM-PROBE proposals (not decisions)

| Draft field | Proposed fill from the peak session | Status |
|---|---|---|
| Observation session | 28 Jul 2026, 08:02–08:58 BST; 52 verified quarantines (51 MAN-05 promoted + final refusal) | measured provenance; G1 still signed by a person |
| Session identity | `manchester-bods-session-identity-1.1` | measured correction; aggregate-only |
| Update interval | median **66 s**, p90 **75 s** | measured |
| Linked-fleet support | **1,433 active** of 1,677 seen; busiest captured hour 07 UTC has 1,432 contributors | measured; threshold remains G1/G2 choice |
| Gap evidence | longest observed gap **64,873 s** from stale-resume records | informs the proposed 120 s ceiling; does not choose it |
| Displacement | median **231.4 m** per distinct update | measured |
| Implied-speed evidence | maximum **64.7 m/s**, so the proposed 32 m/s plausibility gate does not pass every segment | requires explicit owner outlier rule at signing |
| Dwell radius / matched-share floor | unavailable until map matching | remains `FILL-AT-SIGNING` |
| Trace viability | not yet assessed | no trajectory, VEC-06 admission, or campaign exists |

The measured peak window is shorter than the originally proposed 90 minutes because the
strict parser halted it. It has ample linked support for attempting trajectory derivation,
but that is not itself a viability verdict. G1–G5, the outlier response, map-matching
coverage, VEC-06 admission, and the B1 campaign remain future, separately gated steps.

## What these measurements mean (interpretation, confidence-labelled)

Added 28 July 2026 as an owner-directed reading of the measurements above. Every claim
here is descriptive and inherits the record's ceilings; the labels below say explicitly
which statements are measured, which are inference, and which are open.

### 1. The observed fleet may populate the capacity study's unresolved density band

**Measured elsewhere:** the completed capacity sweep found the control inert in all four
normal traces (139, 163, 175, 215 maximum concurrent slots) and outcome-active only in
the 2,488-slot collapse hour, leaving the binding threshold bracketed in `(215, 2488]`
([sweep results](capacity_sweep_completion_results_20260728.md)).

**Measured here and in the accepted probe:** the evening probe recorded **304
concurrently live vehicles in a single snapshot**
([options assessment](bus_data_experiment_options.md) §1); this peak session recorded
**1,433 active session-support vehicles** across ~56 minutes.

**Inference, not yet measured:** peak *concurrency* has not been computed — 1,433 is a
window-total, not a simultaneous count, and the two quantities are not interchangeable.
But the evening probe's 304 already exceeds every normal trace's maximum concurrency, and
a weekday peak is not plausibly sparser than a Wednesday evening. A derived bus-fleet
trace therefore looks likely to sit **above the inert regimes and below the collapse
hour** — inside the exact band no audited trace occupies.

**Cheap next step that would settle it:** count distinct linked vehicles reporting within
each single snapshot of the peak range and take the maximum. That is offline, aggregate,
and needs no acquisition. Until it is run, this subsection is a hypothesis about where B1
would land, not a property of the data.

If it holds, B1 stops being only a distribution-shift study and becomes a candidate route
to locating the saturation boundary with observed vehicles rather than synthetic ones.

### 2. Cadence stability closes B1's largest methodological unknown

Median update interval is **66–68 s and p90 75–76 s from an empty night to full rush
hour** — measured. The practical reading: the update cadence is a property of the feed,
not of traffic load, so the interpolation policy the B1 draft predeclares behaves the
same regardless of when a session is collected. One major "does this assumption survive
peak conditions?" risk is answered, and the answer is yes.

### 3. Displacement falling with density is a real-world consistency signal

Median displacement per update falls **417.9 m → 300.9 m → 231.4 m** across night, dawn,
and peak — measured. At the measured cadences that is roughly **22 km/h at night against
12.6 km/h at peak**: buses progress more slowly when the road is busier, which is the
direction any congestion account predicts. This is evidence that the pipeline measures
something real about Manchester rather than an artifact, and it is the natural quantity
for the declared B2 comparison. It remains bus progression, never road speed.

### 4. The identity defect was a silent-corruption risk, not a nuisance

Had v1.0's bare-`VehicleRef` tokenisation survived into trajectory derivation, merged
vehicles would have produced kilometre-per-second "buses" inside a trace that still
looked plausible in aggregate — the failure mode that is hardest to catch downstream.
It surfaced only because sessions ran long enough for cross-operator collisions to
appear; the 15-snapshot night probe could not have exposed it. Recorded as an
integration finding: **provider identifiers are not necessarily globally unique, and
identity scope must be verified on data dense enough to collide.**

### 5. The parser refusals constrain collection, and share the defect's root cause

Both refusals reduce to the same cross-operator identity-scope gap, in the accepted
MAN-05 parser rather than the session layer. Two consequences, both measured: the
boundary behaved correctly (refusing rather than silently merging), and **a full
90-minute peak session is not currently collectable** — the run halts near 51 promoted
snapshots. B1's declared session length must either accept ~56-minute windows or wait on
a lead-owned parser correction. This is a scheduling fact, not a scientific result.

### 6. What the session cannot support

No hypothesis was tested; no trace, admission, or campaign exists. The density comparison
describes captured bus-session support, never road traffic volume. Session pseudonyms are
incomparable across sessions by construction. The 64.7 m/s maximum shows outliers survive
the identity correction, so any viability gate needs an explicit predeclared outlier rule
before it can pass or fail honestly.

## Boundaries

- Aggregate-only measurements; no session token, salt, or raw vehicle reference is
  committed.
- Session pseudonyms are not comparable between night, dawn, and peak.
- Progression speed is bus displacement over update intervals, never road speed.
- Density ratios describe captured bus-session support, never traffic volume.
- No B1 hypothesis was tested and no owner signature or supervisor approval is implied.
