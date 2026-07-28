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

## Boundaries

- Aggregate-only measurements; no session token, salt, or raw vehicle reference is
  committed.
- Session pseudonyms are not comparable between night, dawn, and peak.
- Progression speed is bus displacement over update intervals, never road speed.
- Density ratios describe captured bus-session support, never traffic volume.
- No B1 hypothesis was tested and no owner signature or supervisor approval is implied.
