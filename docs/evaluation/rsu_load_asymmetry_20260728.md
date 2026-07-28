# Per-RSU Load Asymmetry — Study Case 1 Measurement (28 July 2026)

**Status: exploratory `owner_approved_candidate`, descriptive, non-causal. Analysis only —
computed from the admitted pilot cells' published per-step `rsu_load` arrays, pooled over
seeds {0,1,2}, 3,600 steps, 10 RSUs.**

Answers the producer's original Study Case 1 question — *which RSU is overwhelmed, and how
overwhelmed* — on the collapse-hour trace.

## Measured

| Arm | Mean load/step | Busiest RSU | Quietest | Gini | Zero-load RSUs |
|---|---:|---:|---:|---:|---:|
| cap-2.5 | 25,071.1 | 6,060.9 (24.2%) | 0.0 (0.0%) | 0.486 | 3 of 10 |
| cap-0.75 | 7,742.9 | 1,795.6 (23.2%) | 0.0 (0.0%) | 0.467 | 3 of 10 |

Per-RSU share, cap-2.5: 24.2% · 15.2% · 18.7% · 18.1% · **0.0%** · 1.7% · 14.4% ·
**0.0%** · **0.0%** · 7.8%

## Three findings

1. **Thirty percent of the infrastructure is unused.** RSUs 5, 8 and 9 carry *exactly zero*
   load at every capacity level; RSU 6 carries 1.7–4.3%. Four of ten units are effectively
   idle while the busiest carries ~24%.
2. **The squeeze does not redistribute load.** Gini moves only 0.486 → 0.467 and every
   RSU's share is near-identical across a 3.3× capacity change. Consistent with the
   observation-gap mechanism: the policy's targeting never changes, so relative placement
   pressure cannot change either.
3. **Total load falls 3.2×** (25,071 → 7,743 mean load/step), tracking the latency-tail
   collapse rather than any change in distribution.

## Operator reading (descriptive, not a recommendation)

On this trace, capacity is not the binding infrastructure problem — *placement* is. Adding
capacity to idle units would change nothing, and the squeeze cannot rebalance what the
policy never targets. Whether relocating the idle units would help is a placement question
this measurement does not answer; VEC-06 generated the placement and it is labelled as
such.

## Limitations

One actor, one reviewed trace, three seeds; RSU indices are the evaluator's generated
static placement, never verified Manchester roadside infrastructure; load is the
evaluator's concurrent-task count, never a physical utilisation measurement.
