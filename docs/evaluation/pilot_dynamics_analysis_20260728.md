# Capacity-pilot dynamics: the mechanism in closed form — 28 July 2026

**Status: `owner_approved_candidate`, analysis-only, exploratory, descriptive, non-causal.
No run executed; every number comes from arrays inside already-admitted pilot cells. The
pilot is exploratory by its own predeclaration and nothing here is promoted to
confirmatory.**

Three measurements the capacity programme never took, over all 12 admitted cells
(4 capacities × 3 seeds). Together they replace the descriptive account of the confirmed
finding with a quantitative one.

## 1. The tail-latency ceiling is linear in capacity

Missed tasks do not fail by a little. They pile up against a ceiling — and **that ceiling is
proportional to per-vehicle capacity**, to within half a percent, across every arm, seed and
task class:

| Capacity | p95 latency of missed tasks | Ceiling ÷ capacity |
|---|---|---|
| 2.5 | ~99,200 – 100,200 ms | ~39,700 – 40,100 |
| 1.5 | ~59,500 – 60,200 ms | ~39,700 – 40,100 |
| 1.0 | ~39,650 – 40,200 ms | ~39,650 – 40,200 |
| 0.75 | ~29,700 – 30,200 ms | ~39,600 – 40,300 |

**Across all 36 (cell × class) pairs: mean 39,959 ms, standard deviation 166 ms, relative
spread 0.41%.**

So the ceiling is `≈ 40 s × capacity`: 100 s at cap-2.5, 60 s at cap-1.5, 40 s at cap-1.0,
30 s at cap-0.75.

### Why this explains the confirmed result exactly

The confirmed finding was a −8,310.9 ms mean paired latency reduction with **flat deadline
attainment**, which read as a paradox. It is not:

1. The ceiling is **linear in capacity** — more per-vehicle capacity lets more work queue,
   so the worst-case wait is longer. Squeezing does not make anything faster; it caps how
   much backlog can accumulate.
2. The latency-tail analysis established that **97.9–99.4% of latency mass sits above 1 s**,
   i.e. essentially all of it is at the ceiling.
3. Mass at a ceiling that is linear in capacity ⇒ **mean latency is linear in capacity**.
   Predicted arm ratio 2.5 / 0.75 = 3.33; measured confirmatory arm means 12,027.5 → 3,716.6
   ms = 3.24. The 3% shortfall is exactly the small non-ceiling population.
4. Every deadline is **far below the ceiling at every capacity** — 100 ms and 500 ms against
   a minimum ceiling of 30,000 ms, a factor of 60 to 300. A task at the ceiling misses its
   deadline at cap-2.5 and still misses it at cap-0.75.

**The squeeze compresses the failed population without ever moving a task across the
deadline.** That is the whole mechanism, and it is now a functional form rather than a
narrative.

## 2. The policy is bimodal, not probabilistic

The recorded aggregate offload rate of ~0.40 reads as "each vehicle offloads about 40% of
the time". It is nothing of the sort. Counting only steps where a slot actually carries
tasks (`veh_k > 0` — absent steps are not "chose local"):

| Seed | Never offloads | Always offloads | Ever mixes | Mixed share |
|---|---|---|---|---|
| 0 | 1,413 | 988 | 87 | 3.5% |
| 1 | 1,393 | 992 | 103 | 4.1% |
| 2 | 1,384 | 1,018 | 86 | 3.5% |

**These counts are identical across all four capacities within each seed.** Offload-rate
Gini is 0.587–0.596.

So the policy is not making a per-situation decision that happens to average 40%. It
partitions vehicles into two nearly disjoint populations — one that always offloads and one
that never does — and **only ~3.5% of slots ever switch behaviour at all**. Capacity changes
neither the partition nor its membership.

This deepens the observability-gap mechanism. The earlier finding was that the policy cannot
*see* capacity. This shows that on this trace it barely makes a *decision* in the
situational sense at all: behaviour is close to a fixed per-vehicle assignment.

## 3. Deadline failure is concentrated, and not because of workload

| Measure | Range across the 12 cells |
|---|---|
| Deadline-failure-rate Gini across slots | 0.616 – 0.627 |
| Share of all failures borne by the worst decile of slots | 34.0% – 36.3% |
| Mean failure rate within that worst decile | ~0.75 |
| Median slot failure rate | ~0.035 |
| **Task-count Gini across slots** | **0.028** |

Tasks are distributed almost perfectly evenly across slots (Gini 0.028), so the concentration
is **not** a workload artifact. The same tenth of vehicles absorbs a third of all deadline
failures while the median vehicle fails about 3.5% of its tasks.

Capacity moves this only faintly and in the equalising direction (seed 0: 0.6274 → 0.6268
from cap-2.5 to cap-0.75), which is consistent with compressing the tail.

**This is a distributional result the aggregate cannot show**: "79% deadline attainment" is
not 79% for everyone. It is near-perfect service for most vehicles and near-total failure for
a persistent minority.

## 4. Three task classes fail in three different ways

Implied deadlines were read from the data — the largest latency among *met* tasks of each
class — rather than taken from configuration:

| Class | Implied deadline | Attainment | Median latency of misses | Character of failure |
|---|---|---|---|---|
| T1 | 100 ms | 0.711 | 372 – 376 ms | **near-misses**, ~3.7× over |
| T2 | 500 ms | 0.865 | 28,880 – 98,130 ms | **catastrophic**, at the ceiling |
| T3 | 100 ms | 0.782 | 1,026 – 1,131 ms | intermediate, ~10× over |

And the squeeze acts on exactly the classes sitting at the ceiling:

| Class | Median miss at cap-2.5 → cap-0.75 | Change |
|---|---|---|
| T1 | 376 → 372 ms | −1% |
| T3 | 1,131 → 1,026 ms | −9% |
| T2 | 98,130 → 28,880 ms | **−71%** |

T1's misses are near the deadline and barely move; T2's misses are at the ceiling and fall
with it. The aggregate deadline rate hides three qualitatively different failure modes.

## 5. Saturation is immediate, not gradual

Resolving the run into 60 buckets of 60 steps:

| Steps | Active slots | Mean latency cap-2.5 | cap-0.75 | Ratio |
|---|---|---|---|---|
| 0–60 | 2,447 | 2,949 ms | 2,257 ms | 1.31 |
| 360–420 | 2,417 | 13,440 ms | 4,202 ms | 3.20 |
| 1,440–1,500 | 2,451 | 13,006 ms | 3,884 ms | 3.35 |
| 2,880–2,940 | 2,414 | 13,223 ms | 3,928 ms | 3.37 |
| 3,240–3,300 | 2,424 | 12,129 ms | 3,301 ms | 3.67 |

Across all 60 buckets the ratio has median 3.320 — the capacity ratio. The first bucket
(1.31) is the queue filling; by ~360 steps, 10% into the run, the system is in steady state
and stays there. **The "collapse hour" is not a collapse at the VEC layer — it is saturated
from the start.** Total RSU load plateaus in the same window (~24,600 at cap-2.5 versus
~7,220 at cap-0.75, a ratio of 3.41).

Offload share is flat at 0.398–0.407 for the entire run at every capacity: **the policy never
adapts, at any point, to any load condition.**

## What this does not claim

- Analysis-only over exploratory pilot cells. The confirmed result stands on the signed
  held-out protocol, not on this.
- The ceiling law is measured on the `inc` collapse-hour trace with these actors. It is not
  established for other traces, and the four normal regimes never saturate, so no ceiling is
  observable there.
- "Capacity" is the predeclared per-vehicle RSU capacity control; no claim is made about
  physical infrastructure.
- Nothing here is causal in the interventional sense beyond the predeclared capacity arms
  themselves.

## Why it matters for the protocol lesson already recorded

The programme already recorded that mean latency is ~99% tail mass and that future protocols
should predeclare a percentile or tail-share endpoint. This sharpens that: on a saturated
trace the tail *is* a deterministic function of the control, so a mean-latency endpoint
measures the control's arithmetic rather than the policy's behaviour. **The endpoint that
would have distinguished a good policy from an inert one is deadline attainment stratified
by task class and by vehicle — neither of which the original protocol declared.**
