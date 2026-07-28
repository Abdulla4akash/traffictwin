# Latency-Tail Analysis — the Confirmed Finding's Mechanism, Measured (28 July 2026)

**Status: exploratory `owner_approved_candidate`, descriptive, non-causal. Analysis only —
no new execution; computed from the 12 admitted pilot cells' published per-task arrays
(39,228,702 active tasks per arm, pooled over seeds {0,1,2}).**

This settles the one interpretation the [detailed findings record](capacity_study_detailed_findings.md)
carried as "consistent reading, checkable but not yet checked": that mean latency collapses
under capacity squeeze because a tighter concurrency bound truncates a queue-blowup **tail**,
leaving the bulk untouched. It does — and the split is cleaner than the reading assumed.

## Measured distribution by arm

| Arm | p50 | p90 | p99 | max | mean | share > 1 s | latency mass in > 1 s tail |
|---|---:|---:|---:|---:|---:|---:|---:|
| cap-2.5 | 44.3 ms | 32,260 ms | 99,854 ms | 102,432 ms | 9,798.8 ms | 11.4816% | 99.35% |
| cap-1.5 | 44.3 ms | 31,117 ms | 59,975 ms | 61,966 ms | 6,029.6 ms | 11.4623% | 98.95% |
| cap-1.0 | 44.3 ms | 26,677 ms | 40,009 ms | 41,673 ms | 4,089.9 ms | 11.4485% | 98.45% |
| cap-0.75 | 44.3 ms | 21,947 ms | 30,034 ms | 31,468 ms | 3,083.6 ms | 11.4138% | 97.94% |

## The three facts that explain the whole finding

1. **The bulk is untouched.** p50 is **44.3 ms at every capacity level** (−0.10% across the
   full 3.3× squeeze). Roughly 88.5% of tasks are unaffected by the control.
2. **The tail's population barely moves, but its severity collapses.** The share of tasks
   exceeding 1 s falls only 11.4816% → 11.4138% (−0.07 pp), while **p99 falls 69.9%**
   (99,854 → 30,034 ms) and p90 falls 32.0%. Squeezing capacity does not change *how many*
   tasks queue pathologically — it changes *how long the worst ones wait*.
3. **The mean is almost entirely tail.** 97.9–99.4% of all latency mass sits above 1 s, so
   the 68.5% mean reduction is a tail statistic, not a broad improvement.

## Why deadlines stay flat while mean latency collapses

Deadlines are 100 ms (T1, T3) and 500 ms (T2). The ~88.5% bulk completes at ~44 ms and meets
them at every capacity. The ~11.5% in the >1 s tail misses them at every capacity — whether a
task waits 30 s or 100 s, it has missed a 100 ms deadline identically. **The squeeze moves
latency only within the already-failed population**, which is exactly why the confirmed
−8.3 s mean effect coexists with a flat deadline rate. The two results are not in tension;
they are the same phenomenon measured at two points of the distribution.

## Consequences

- The mechanism chain is now complete and measured end to end: the policy cannot see
  capacity (observation gap) → its decisions never change (keyed-action identity) → the
  control acts only on queueing → and queueing acts only on the tail (this record).
- **Mean latency is a misleading headline metric for this system**, since it is ~99% tail
  mass. Any future protocol should predeclare a percentile or a tail-share endpoint
  alongside it. This does not weaken the confirmed result, which was predeclared on the mean
  before any held-out data existed and is reported here with its composition made explicit.

## Limitations

One actor, one reviewed collapse-hour trace, three pilot seeds, four capacity levels;
pooled across seeds; exploratory forever; deadline success is never physical completion.
