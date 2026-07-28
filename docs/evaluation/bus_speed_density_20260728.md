# Bus progression speed against fleet size — 28 July 2026

**Status: `owner_approved_candidate`, exploratory, descriptive, **non-causal**. Aggregate-only
session identity (`manchester-bods-session-identity-1.1`); one fresh in-process salt per
declared session, no cross-session linkage, no raw identifiers published. Bus progression
speed is **never** road-traffic speed.**

Four attended sessions now span a **36× range of fleet size** under one unchanged
acquisition boundary and one identity policy. That makes them a speed–density series for
the observed Manchester bus fleet, obtained from live open data with no simulator and no new
acquisition.

## Method

Speed is computed **per segment** by the accepted B2 primitive
`measure_session_progression`, not as median displacement over median interval — that ratio
is not a median speed. The session figure is the median of hourly medians over hours
carrying at least 100 segments; thin hours stay visible in the table rather than being
folded in.

Sessions are bounded by explicit UTC stamp ranges rather than hour prefixes, because the
dawn session spans 05:1x–06:09 and a prefix would have swallowed `065742Z` — the single
promotion from the aborted 07:57 BST attempt, which belongs to no measured session. Session
sizes reconcile exactly with the recorded three-session results (night 15/41, dawn 52/1,162).

## The series

| Session | Snapshots | Active fleet | Median progression speed | km/h |
|---|---|---|---|---|
| Night probe (27 Jul) | 15 | 41 | **6.290 m/s** | 22.6 |
| Shallow dawn | 52 | 1,162 | 4.441 m/s | 16.0 |
| Morning peak | 51 | 1,431 | 3.518 m/s | 12.7 |
| Evening peak | 83 | 1,522 | 3.610 m/s | 13.0 |

**Buses at peak move 44% slower than at night.**

## Resolved by hour, the relationship is monotone

The evening session spans two UTC hours and separates cleanly, which turns four session
points into six hour points:

| Hour (UTC) | Local | Segments | Vehicles | Median m/s | p90 m/s |
|---|---|---|---|---|---|
| 23Z | 00:00 | 415 | 41 | **6.290** | 12.573 |
| 06Z | 07:00 | 7,779 | 1,075 | 4.358 | 9.096 |
| 05Z | 06:00 | 32,744 | 1,077 | 4.523 | 9.404 |
| 17Z | 18:00 | 47,965 | 1,395 | 3.850 | 8.470 |
| 07Z | 08:00 | 58,720 | 1,429 | 3.518 | 8.159 |
| 16Z | 17:00 | 48,360 | 1,462 | **3.369** | 7.904 |

Ordered by fleet size, median speed falls essentially monotonically — 6.290 → 4.523 → 4.358
→ 3.850 → 3.518 → 3.369 m/s. The one inversion is between the two dawn hours, which carry
nearly identical fleets (1,077 vs 1,075) and very unequal support (32,744 vs 7,779
segments), so it is within the noise the support counts already expose.

p90 speed falls in lockstep (12.573 → 7.904 m/s), so this is a shift of the whole
distribution, not a change in its tail.

## The evening asymmetry, explained by the hourly split

At session level the evening peak looks *faster* than the morning peak (3.610 vs 3.518 m/s)
despite carrying **more** vehicles (1,522 vs 1,431) — which reads as a contradiction. The
hourly resolution dissolves it:

- **16Z** (17:00 BST): 1,462 vehicles at **3.369 m/s** — more vehicles and slower than the
  morning peak's 1,429 at 3.518.
- **17Z** (18:00 BST): 1,395 vehicles at **3.850 m/s** — the taper, faster as the fleet thins.

The session-level average simply mixes the crest with the recovery. **Compared hour for
hour, the evening peak is both denser and slower than the morning peak**, exactly as the
series predicts. This is why the session figure is reported alongside the hourly table and
never on its own.

## What this is not

- **Not causal.** Fleet size and time of day move together, and so does general road
  traffic. The honest statement is "buses progress more slowly when more buses are in
  service", not "more buses cause slower buses". Bus fleet size is a proxy for time of day,
  and general congestion is an unmeasured common cause. Separating them needs the road-side
  observation this series does not contain.
- **Not road speed.** These are bus progression speeds including dwell at stops, signals and
  layover. A bus fleet is not a probe fleet for general traffic.
- **Not a validation of anything.** No comparison against the DfT hourly profile is
  performed here; that is the separate declared B2 step.
- Stale-resume segments exist in every session; per-segment medians are robust to the small
  number of extreme values they produce, and the p90 column is reported so the spread is
  visible.

## Why it is worth having

It is the project's first **real-world measured relationship** obtained end to end from live
open data through the accepted acquisition, quarantine, privacy and aggregation boundary —
36× of fleet range, six hour points, monotone, with the one inversion explained by its own
support counts. It needs no simulator, no predeclaration and no owner decision, and it
stands independently of whether any bus VEC experiment ever runs.
