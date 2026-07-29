# What the offloading decision is actually a function of

**Status: exploratory, analysis-only, `owner_approved_candidate` ceiling. Descriptive and
non-causal. Not supervisor-approved, not confirmatory, no significance claimed. No run executed;
every number below comes from arrays in already-admitted cells.**

Producer code and data use is covered by the recorded permission with citation — see
[citation requirements](../producer_citation_requirements.md).

## 1. The question the earlier analysis left open

The [pilot dynamics analysis](pilot_dynamics_analysis_20260728.md) established that the offload
decision is **bimodal**: each vehicle slot either never offloads or always does, only ~3.5% ever
mix, and the split is identical at every capacity. It did not ask **what decides which side a
vehicle falls on** — and that turns out to be the whole story.

## 2. The finding

**The trained policy's offload decision is a function of vehicle compute tier, and of nothing
else that was measured.**

Across five admitted cells spanning two campaigns, four seeds and capacities from 2.5 down to
0.1:

| Cell | corr(offload, failure) | never-offload | its failure | always-offload | its failure | tier-0 share of always-offload |
|---|---|---|---|---|---|---|
| `cap-2.5-fs0` | +0.868 | 1,413 | 0.028 | 988 | 0.479 | **100.0%** |
| `cap-0.75-fs2` | +0.891 | 1,384 | 0.028 | 1,018 | 0.528 | **100.0%** |
| `cap-2.5-fs60` | +0.882 | 1,410 | 0.028 | 995 | 0.490 | **100.0%** |
| `cap-0.1-fs60` | +0.881 | 1,410 | 0.028 | 995 | 0.489 | **100.0%** |
| `cap-0.1-fs61` | +0.887 | 1,416 | 0.028 | 1,006 | 0.498 | **100.0%** |

The always-offload group is **exactly** the tier-0 population in every cell, and the
never-offload group contains **no tier-0 vehicle in any cell** — it is tier 1 (≈60%) and tier 2
(≈40%). The producer's capability scalars are `TIER_CAP_SCALAR = [0.0751, 0.4847, 1.0]`, so
tier 0 is roughly **13× weaker** than tier 2.

The worst-failing decile of slots is **100% always-offload in every cell**; the best decile is
~99.6% never-offload.

### 2b. The rule, fully specified

Characterising the ~3.5% "mixed" slots completes it. At `cap-2.5-fs60` the mixed group is
**50 tier-1 and 33 tier-2 slots — no tier-0 vehicle at all**. So:

| Tier | Capability | Offload rate |
|---|---|---|
| 0 | 0.0751 | **exactly 1.0** — group minimum is 1.0000, i.e. unconditional |
| 1, 2 | 0.4847, 1.0 | **exactly 0.0** for 1,410 of 1,493 slots; 83 exceptions spanning 0.0004–0.7459 (median 0.066) |

The weak vehicles receive no decision at all. Whatever situational behaviour the policy retains
exists only among the strong vehicles, in 5.6% of them, and never changes the outcome for the
population that actually fails.

The partition is also identical **element-wise** across a 25× capacity change — same vehicles in
the same groups, and every per-slot offload rate equal to the last bit. This is a
re-confirmation at vehicle granularity rather than an independent result: it follows from the
previously published keyed action comparison, which found 0 mismatches in 8,956,800 per-vehicle
actions. It is recorded here because it locates *why* that comparison found what it did.

## 3. Two confounds, eliminated rather than assumed

A raw failure gap between two groups can be manufactured by either of these, so both were
measured.

**Workload — not the explanation.** Tasks per slot are 5,263 (never) against 5,243 (always) at
`cap-2.5-fs0`, consistent with the pilot's task-count Gini of 0.028. The groups carry the same
load.

**Task mix — not the explanation.** Class shares are identical (20/30/50) in both groups, and
failure diverges *within* every class:

| Class | Deadline | never-offload | always-offload |
|---|---|---|---|
| T1 | 100 ms | 5.2% | **64.4%** |
| T2 | 500 ms | **0.0%** | 34.0% |
| T3 | 100 ms | 3.5% | 49.5% |

Tier-1/2 vehicles miss a 500 ms deadline **literally never** on this trace.

## 4. What this reframes

**The headline attainment figure is a fleet-composition artifact.** "≈79% deadline attainment"
is not a property of the algorithm. It is ~40% of the fleet failing about half the time and
~60% succeeding ~97% of the time, averaged. Change the tier mix and the number moves; the
algorithm need not change at all. Any report quoting a single attainment number for this system
is quoting the fleet, not the policy.

**Capacity invariance now has a complete explanation, and a simpler one than the observation
gap.** Earlier work located a structural blindness — no RSU-load term in the observation vector.
This is stronger: the decision is not responding to *situational* input at all. Who offloads is
fixed by hardware, so no capacity change can alter the decision set. The observation gap
explains why the policy *could not* adapt; this shows it *does not vary* on anything the run
changes.

**It converges with the producer's own Year-1 finding.** That report documented decisions
collapsing to ~94–95% local under a reward misaligned with cooperative offloading. This is the
same pathology in the Year-2 environment, measured at per-vehicle resolution: not a distribution
over actions, but a partition of the fleet by hardware class.

## 5. What this does **not** establish

**Whether offloading helps the vehicles that do it.** Tier-0 vehicles fail ~48% of the time
*while always offloading*. Whether they would fail more, less, or the same executing locally is
a counterfactual this measurement cannot reach — it requires a different actor on the same
trace. That is precisely the
[actor crossover campaign](actor_crossover_candidate_inc_20260728.md), whose 12 cells were
queued before this analysis existed.

If tier-0 vehicles do **better** under `baseline_model_c_17`, the trained policy is actively
harmful for 40% of the fleet, and the "worse" algorithm wins. If they do worse, offloading is
rescuing vehicles that would otherwise fail outright. Either is a publishable result and neither
is currently known.

**Causality between offloading and failure is not claimed.** The correlation of +0.87 is between
two variables that are both determined by tier. Tier is the common cause; this analysis
separates it from workload and task mix, and stops there.

## 6. The confirmed capacity effect, decomposed by population

If the partition is real, the capacity effect should live entirely in the offloading population.
It does — and the other population's numbers are not merely stable, they are **bit-identical**.

Same seed, capacity 2.5 against 0.1 (a 25× squeeze):

| Seed | Group | mean latency | p50 | p95 of missed | attainment |
|---|---|---|---|---|---|
| 60 | never-offload | 39.6 → **39.6 ms** | 25.3 → 25.3 | 265.1 → 265.1 | 0.9720 → 0.9720 |
| 60 | always-offload | 25,625.5 → 1,061.3 ms | 169.6 → 168.4 | 100,190.1 → 4,097.4 | 0.5103 → 0.5116 |
| 61 | never-offload | 39.6 → **39.6 ms** | 25.0 → 25.0 | 287.0 → 287.0 | 0.9715 → 0.9715 |
| 61 | always-offload | 27,438.3 → 1,074.1 ms | 194.9 → 181.8 | 99,948.5 → 4,079.0 | 0.4926 → 0.5028 |

**Δ mean latency: +0.0 ms (never-offload) against −24,564.2 ms (seed 60) and −26,364.1 ms
(seed 61).**

Three consequences.

**The confirmed fleet-mean effect describes no vehicle.** The headline −8,310.9 ms is an average
over a bimodal population: roughly 40% of the fleet experienced a reduction an order of
magnitude larger, and roughly 60% experienced *exactly none*. No vehicle experienced −8.3 s. A
mean over a bimodal population is a number about the mixture, not about any member of it.

**The ceiling law is an RSU-queue law.** Computed on the offloading population alone, p95 of
missed ÷ capacity gives 40,076 and 40,974 (seed 60) and 39,979 and 40,790 (seed 61) — the same
constant. Computed on the never-offload population it has no capacity relationship at all: 265.1
ms at both capacities on seed 60, 287.0 at both on seed 61. `L(c) ≈ K·c` was never a property of
the system; it is a property of the RSU queue, and it applies only to traffic that enters it.
The pooled measurement recovered it because ~92% of all missed tasks belong to the offloading
population.

**It resolves the seed-difference puzzle.** Fleet attainment moved 8.5× more at seed 61 than at
seed 60. Decomposed: tier-0 attainment moved +0.0013 (seed 60) and +0.0102 (seed 61), and the
fleet figure is that movement diluted by the tier-0 share (~0.41). 0.0102 × 0.41 ≈ 0.0042
against a measured fleet change of 0.00416. The seeds differ in how much the offloading
population gained, not in anything structural.

## 7. Limits

- One trace (`inc`, the modelled collapse hour), one producer environment, one actor.
- Five cells were analysed, not all twelve of each campaign; the pattern is identical in all
  five and no cell contradicts it, but the remaining cells are unexamined.
- `slot_tier` is read from the admitted arrays; the capability scalars are read from producer
  source. Neither is re-derived here.
- Exploratory: no predeclaration governs this measurement, and it is reported as a descriptive
  reading of existing artifacts rather than a tested hypothesis.

Reproduced by `scripts/analyse_offload_partition.py`; evidence at
`data/offload-partition-20260729/offload_partition.json` (§2–§5) and
`data/offload-partition-20260729/effect-decomposition/offload_partition.json` (§6).
