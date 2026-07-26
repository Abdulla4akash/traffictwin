# Demand Rebuild — Route-Pool Variants Predeclaration (PROPOSED, UNSIGNED)

**Status: PROPOSED. Not approved, not executed.** No measurement, pool, or simulation described
here has been run. Beta Phase C (`BETA-D-02`) requires the variants and the selection rule to be
predeclared before outcomes are inspected; this document is that predeclaration, drafted while
the only known result is the alpha.7 failure.

- Proposed: 27 July 2026
- Consumes: the accepted study subnetwork (285,794 edges), the Option-A window's edgeData counts
  (1,788 cells, 149 edges, 2,024,123 observed vehicles), and the recorded alpha.7 route-pool
  envelope (43,200 routes, seed 42)
- Preserves: the alpha.7 candidate demand and its gridlock diagnostic, unchanged, under their
  original provenance identity
- Policy label ceiling: `owner_approved_candidate`

## 1. The measured failure this rebuild answers

The alpha.7 count-constrained demand achieved 91.32% of observed counts with zero overflow — and
then gridlocked the one-hour diagnostic: halting share rose from 49.8% to 88.8%, teleports from
113 to 21,669 (35.7% of inserted vehicles), insertion rate more than halved, and only 8.1% of
demand entered the network. A count-matching artifact that cannot physically flow is a refusal,
not a baseline.

**Recorded hypothesis, to be tested and not assumed:** the route pool is dominated by long
cross-network routes produced by the previous generation policy (fringe weighting and
minimum-distance choices), so routeSampler could only satisfy counts by scheduling traffic that
saturates the network between count points.

## 2. Diagnosis first: measurements before any variant runs

Reproduce the alpha.7 pool from its recorded seed and envelope (deterministic), then measure and
publish, for the pool and for the sampled demand:

- route-length distribution (km) and route edge-count distribution;
- expected network residence time at free flow;
- edge coverage: how many pool routes traverse each counted edge (count-point multiplicity);
- the share of pool routes entering from subnetwork-boundary edges (the fringe share).

These measurements are the hypothesis test. They are published regardless of what they show, and
if they *contradict* the recorded hypothesis, the variant order below is re-proposed to the owner
rather than silently continued.

## 3. Predeclared variants, in evaluation order

Every variant regenerates the pool under a **new provenance identity** with a deterministic seed,
leaves counts and window untouched (Option A stays decided), and changes exactly the stated
controls. Proposed order reflects the hypothesis; V0 is the measured control.

| Variant | Change from alpha.7 | Rationale |
|---|---|---|
| **V0** | none (existing measured result) | control; already known to gridlock |
| **V1** | remove fringe weighting; uniform edge sampling | tests the fringe half of the hypothesis in isolation |
| **V2** | V1 plus a bounded trip-length envelope: minimum 0.5 km, maximum `FILL-AT-SIGNING` km chosen from the §2 length distribution (proposed default: the distance at which 95% of counted-edge coverage is retained) | tests the long-route half; keeps short urban trips |
| **V3** | V2 plus pool enlargement (2× routes, same envelope, new seed recorded) | tests whether remaining underflow is pool-size, not policy — only reached if V2 is viable but fails count-achievement |

The selection rule is **first viable in order**, not best-looking: the first variant meeting
every viability criterion in §4 is selected; later variants run only if earlier ones fail, or as
the explicitly labelled V3 count-achievement remedy. If no variant is viable, the result is a
published refusal and the next step is a design conversation, not threshold relaxation.

## 4. Fail-closed viability contract (proposed thresholds, owner decides)

Evaluated on a bounded one-hour pilot simulation per candidate demand, through the existing
controlled SUMO boundary, before any full-window run:

| Criterion | Proposed threshold | Measured alpha.7 value |
|---|---|---|
| Demand entering the network | ≥ 85% | 8.1% |
| Teleports as share of inserted vehicles | ≤ 1% | 35.7% |
| Final halting share | ≤ 30% | 88.8% |
| Count achievement (routeSampler) | ≥ 85% of observed | 91.32% (the one axis alpha.7 passed) |
| Output size within the runner's bounded-output contract | required | passed |

All five must hold; a variant failing any one is recorded with its measurements and not retried
with altered controls. GEH remains a verbatim diagnostic and appears nowhere in this contract.

## 5. Boundaries carried forward unchanged

- Missing observations stay missing; no demand is invented for uncovered Greater Manchester.
- Reconstructed routes are never observed journeys; the Manchester local-authority scope never
  becomes a Greater Manchester claim.
- The 80/20 site split and the Option-A window stay frozen; the pandemic-year gap stays a gap.
- Every executable identity, argument vector, and seed is recorded; no arbitrary shell surface.
- A viable run is not calibrated, and nothing here performs calibration or comparison.

## 6. Execution cost note

Pool regeneration and each pilot simulation are hours-scale CPU work. Nothing in this document
executes while the capacity-pilot campaign occupies the machine; scheduling is an owner decision
after signing.

## 7. Owner decisions required before execution

| # | Decision | Proposed default |
|---|---|---|
| E1 | Variant order and V3's conditional role | as tabled in §3 |
| E2 | Trip-length maximum rule for V2 | 95% counted-edge-coverage retention distance |
| E3 | Viability thresholds | as tabled in §4 |
| E4 | Pilot simulation window | one hour, same as the alpha.7 diagnostic, for comparability |
| E5 | Scheduling relative to the capacity study | after the pilot campaign completes |

**Sign-off (a person completes this; an agent never does):**

- Approved by: ______________________
- Role: ______________________
- Date: ______________________
- Deviations from the proposed defaults: ______________________
