# BETA-D-02 §2 demand diagnosis — results, 28 July 2026

**Status: `owner_approved_candidate`, exploratory, descriptive, non-causal. Measurements
only. No variant is selected, no viability threshold is applied, and no verdict is reached
here — those are owner decisions against
[the predeclaration](demand_rebuild_predeclaration.md), which is unsigned.**

§2 of the predeclaration requires four measurements *before* any variant runs, published
regardless of what they show, and states that if they contradict the recorded hypothesis
"the variant order below is re-proposed to the owner rather than silently continued."

**They contradict it. The re-proposal is §6 below, presented and not taken.**

Inputs: the study subnetwork restored earlier today
([record](../integration/evidence/manchester_chain_restoration_20260728.json)), the
committed Option-A edgeData counts, and the alpha.7 envelope reproduced at its recorded
seed. Run script `scripts/run_demand_diagnosis.py`; receipt and full report beside the
private artifacts in gitignored `data/demand-diagnosis-20260728/`.

## 1. The reproduction is faithful

| Stage | This run | Recorded 25 July | Note |
|---|---|---|---|
| Trips (`randomTrips`, seed 42, fringe-factor 5, min-distance 300, `--validate`) | 43,200 | 43,200 | exact |
| Pool (`duarouter`, seed 42) | 43,200 routes, 88,163,681 B | 43,200 routes, 88,163,497 B | +184 B = generation banner |
| Demand (`routeSampler`, seed 42) | 749,267 vehicles | 746,440 | +2,827 (+0.38%), explained in §5 |
| Cells matched exactly | 1,658 / 1,800 (92.11%) | 1,629 / 1,788 (91.1%) | |
| Count achievement | 91.72% | 91.32% | |
| Overflow | 0 | 0 | |
| Edges with any underflow | 16 | 18 | |
| Two dominant shortfall edges | `1544431771`, `1544380919` | the same two | 61.4% of unmet here, ~59% then |

Durations: trips 774.2 s, pool 594.5 s, demand 200.0 s, diagnosis passes 2.2 s and 31.5 s.
All 285,794 real edges carry a usable length and a positive free-flow speed, so no edge was
dropped for undefined residence time.

## 2. The fringe half of the hypothesis is refuted

The recorded gridlock hypothesis attributed the alpha.7 failure partly to *fringe bias* —
too many routes entering at the clip boundary. Measured:

| | Pool | Sampled demand |
|---|---|---|
| Routes whose first edge is known | 43,200 | 749,267 |
| …entering on a subnetwork-boundary edge | **28** | **2,810** |
| Fringe share | **0.0006 (0.06%)** | **0.0038 (0.38%)** |

For context, and to show the result is not an artifact of a narrow definition:

- **entry-fringe** (this measurement: an edge whose from-junction receives no real edge, so
  a route starting there entered at the clip boundary) — **5,371 of 285,794 edges, 1.88%**;
- **exit-fringe** (to-junction has no outflow) — 6,661 edges;
- **either**, the broader `sumolib`-style `is_fringe` that `--fringe-factor` acts on —
  **11,526 edges, 4.03%**.

So 0.06% of pool routes start on an entry-fringe edge, against a **1.88% unweighted base
rate and a declared 5× fringe weighting**. The measured share is not merely small; it is
far below what no weighting at all would produce. Whatever `--fringe-factor 5` did to this
pool, boundary entry is not a meaningful population in it.

**Consequence:** V1 — "remove fringe weighting; uniform edge sampling" — is the predeclared
*first* variant, and it changes a control whose effect is not visible in the artifact.

## 3. The long-route half is supported

| Measurement | n | mean | p05 | p50 | p95 | max |
|---|---|---|---|---|---|---|
| Pool route length (km) | 43,200 | 8.58 | 2.20 | **7.85** | 17.46 | 27.86 |
| Pool route edge count | 43,200 | 177.99 | 58 | **165** | 339 | 562 |
| Pool free-flow residence (s) | 43,200 | 565.37 | 174.19 | 535.52 | 1068.03 | 1537.60 |
| Demand route length (km) | 749,267 | 9.12 | 2.81 | **8.17** | 18.27 | 27.86 |
| Demand route edge count | 749,267 | 149.55 | 54 | **134** | 296 | 514 |
| Demand free-flow residence (s) | 749,267 | 534.48 | 210.18 | **502.56** | 986.73 | 1537.60 |

These are long cross-network paths for a single local authority. The demand median of
**134 edges reproduces exactly** the median measured on the truncated survivor during the
27-July continuity audit — an independent corroboration that the survivor's route
statistics did describe a comparable construction.

One arithmetic implication, stated as arithmetic and not as a claim about the simulator:
749,267 vehicles × 534.48 s mean free-flow residence ≈ 400.5 M vehicle-seconds across the
43,200 s window, i.e. **≈ 9,270 concurrent vehicles on average even if nothing ever slows
down**.

## 4. The binding constraint is coverage, and it is neither of the hypothesised halves

Counted-edge multiplicity — how many pool routes traverse each counted edge — is extreme:

| | n | p05 | p50 | p95 | max | zero-coverage |
|---|---|---|---|---|---|---|
| Pool | 150 | 20.8 | 394.5 | 2,268.4 | 3,107 | **4** |
| Demand | 150 | 1,789.3 | 8,318.5 | 37,821.2 | 68,279 | 4 |

**Four counted edges are traversed by no pool route at all, and every vehicle observed on
them is unmet:**

| Edge | Pool routes | Observed | Unmet | |
|---|---|---|---|---|
| `1544129757` | 0 | 7,289 | 7,289 | 100% |
| `1544096242` | 0 | 6,317 | 6,317 | 100% |
| `1544067340` | 0 | 5,484 | 5,484 | 100% |
| `1544105506` | 0 | 1 | 1 | 100% |

And the two edges that dominate the entire shortfall are **not** under-supplied — they are
very nearly unreachable:

| Edge | Pool routes | Observed | Unmet | |
|---|---|---|---|---|
| `1544431771` | **2** | 54,857 | 53,272 | 97.1% |
| `1544380919` | **2** | 52,234 | 49,872 | 95.5% |

Against a median of **395** pool routes per counted edge.

**Six of 150 counted edges carry pool coverage of 2 routes or fewer, and together they
account for 122,235 of the 167,931 unmet vehicles — 72.8% of the entire shortfall.** The
remaining underflow is spread across ten edges that are covered by hundreds or thousands of
routes and simply run short (for example `998731423`: 1,352 routes, 37.8% unmet).

This is a structural reachability property of the pool, not a weighting or sizing property.

## 5. Why this run produced 2,827 more vehicles, and an artifact that does not reconcile

The committed Option-A edgeData artifact holds **150 counted edges × 12 intervals = 1,800
cells totalling 2,027,275 vehicles**. The alpha.7 record states **149 edges / 1,788 cells /
2,024,123 vehicles**. The 11 measured-zero cells match exactly in both, so these are close
relatives.

But the surplus does not decompose: 1,800 − 1,788 = 12 cells is exactly one extra edge, and
**no single edge in the committed file totals the missing 3,152 vehicles**, so no
149-edge subset of the committed artifact reproduces the recorded total. The committed
artifact is therefore *not byte-exactly the input the alpha.7 demand consumed*.

This closes the open +3,152 reconciliation note raised by the B2 comparison on 27 July, and
it reframes it: the discrepancy is on the observation side, it is quantified, and it is not
resolvable from committed evidence alone. The +2,827 extra demand vehicles here are
consistent in sign and magnitude with the +3,152 observation-side surplus.

**Everything in §§2–4 is measured on the committed artifact and is unaffected**, because
those measurements concern the pool's structure, not the count totals — and the recorded run
independently found the same two dominant shortfall edges.

## 6. Re-proposal, presented and not taken (owner decision, E-series)

§2 requires that a contradicted hypothesis re-opens the variant order. All three predeclared
variants target mechanisms the measurements say are not binding:

| Variant | Predeclared change | What the measurement says |
|---|---|---|
| **V1** | remove fringe weighting | fringe entry is 0.06% of pool routes — below the unweighted base rate |
| **V2** | bounded trip-length envelope | shortening routes plausibly makes distant counted edges *less* reachable, not more |
| **V3** | 2× pool, same envelope | doubling coverage of 0 routes is 0; doubling 2 routes against 54,857 observed vehicles is not a remedy |

The measurements point instead at **targeted reachability**: generating trips that
deliberately traverse the counted edges (for example `randomTrips --edge-permission`-style
weighting toward counted edges, or seeding trips from the counted edges themselves) rather
than sampling the network uniformly and hoping coverage falls where the observations are.

**That is a new variant, not one of V1–V3, so it is not mine to run.** The predeclaration's
own rule is that a contradicted hypothesis returns to the owner. Three options, none taken:

1. **Amend the predeclaration** with a coverage-targeted variant before any variant runs,
   re-freeze, and proceed under the amended order.
2. **Run V1–V3 as written**, recording in advance that §2 predicts they will not clear the
   §4 contract — a defensible, publishable negative result about the predeclared remedies.
3. **Publish §2 alone** as the diagnosis result and treat the demand rebuild as blocked on a
   design conversation, which is the outcome §4 already reserves for "no variant is viable".

## Boundaries carried forward

- Reconstructed routes are never observed journeys; this is Manchester local-authority
  evidence and never a Greater Manchester claim.
- Missing observations stay missing; no demand is invented for uncovered area.
- No calibration or comparison is performed, and nothing here is supervisor-approved.
- GEH appears nowhere in this record; the routeSampler mismatch is reported verbatim as a
  diagnostic.
