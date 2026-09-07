# Why common-target execution used RSUs 0–4

**Completed 7 September 2026. Post-hoc, read-only mechanism audit.**

The saved morning runs support the proposed explanation: **five task substeps,
empty queues at every batch boundary, positive admitted work and lowest-index
tie-breaking together confine common-target placement to RSUs 0–4.** This is
more specific evidence than the previously reported workload shares.

The audit inspected all four completed common-target runs (fleet seeds 0, 2,
3 and 4), covering **43,200 simulated seconds and 216,000 task substeps**.
It also checked the execution-RSU identities in the four existing per-task
controls. It launched **zero simulations**, changed no evaluator source and
verified the input files' hashes before and after analysis. The consolidation
at private-repository commit `f17298e` remains unchanged.

## Direct observations from the arrays

1. Every recorded common-target end-of-second RSU workload and task count was
   zero: **388,800 RSU/second entries** for each of those fields.
2. There were **179,427 substeps with an observable V2I target**. Each contained
   exactly one selected target, and in every case **task substep `k` selected
   RSU `k`**, using zero-based indices. There were zero exceptions.
3. Selected and admitted execution identities were confined to RSUs **0–4**
   in each common-target draw. The existing per-task control used **all nine**
   RSUs in each draw.
4. Common-target used all five RSUs in **15,803 seconds**; other seconds used
   fewer. “Five RSUs” describes the full-run union, not five executions or five
   busy RSUs in every second.
5. The common-target arrays contain **511,684 deadline-gate rejections** and
   **zero RSU-capacity rejections** across the four draws. The counts match
   the original summaries. None of these gate-rejected tasks is recorded as
   admitted.

The remaining **36,573 substeps** contain no recorded V2I attempt, so their
stored selected-target value is `-1`. The source still computes a target, but
the audit does not label that unobserved internal selection as a measurement.

## Reconstruction and checks

Substep queue workloads were not directly saved for common-target. The audit
reconstructed them using recorded task admissions and execution destinations,
the already archived task-type/service-work reference, and the existing frozen
workload replay. The reference and replay hashes match the replication
manifest; the replay does not recompute admissions or generate new traffic.
That reference had previously been qualified against the instrumented pilot.

The reconstruction reproduced all saved workload and task-count endpoints
**exactly**. It also showed that every observable target was the **lowest-index
minimum-workload RSU**, with zero mismatches. The number of tied minima was
9, 8, 7, 6 or 5 as the occupied prefix grew. Every substep's inferred target
equalled the number of preceding substeps that had added positive work.

| Fleet seed | Recorded gate-rejected tasks | Maximum reconstructed workload before the drain (ms) | Maximum reconstructed tasks at one RSU before the drain |
|---:|---:|---:|---:|
| 0 | 127,554 | 538.730 | 25 |
| 2 | 161,015 | 537.441 | 24 |
| 3 | 125,492 | 535.168 | 23 |
| 4 | 97,623 | 534.281 | 22 |

Every reconstructed workload cleared within the 1,000 ms service interval.
The next batch therefore began empty. This is a measured/reconstructed property
of these runs, not a theorem that every possible common-target workload must
clear within one second. In particular, the causal per-task workload bound
must not be silently assumed for the common-target three-pass reconciliation.

The original admission capacity was **6,220 tasks per RSU**. The reconstructed
maximum task counts are far below that ceiling; increasing the waiting room
would not address the observed gate-rejection mechanism.

## Deduction from the frozen code and observed state

The frozen evaluator makes one `argmin(rb)` choice and broadcasts it to all
V2I candidates within a task substep. Only after that substep does it add the
admitted compute work to the chosen RSU. It scans five substeps before applying
the one-second drain. There is no alternative-RSU retry for a rejected task.
See the pinned [selector and admission path](https://github.com/Abdulla4akash/vec_env/blob/908bd10f86542de94fc38af90dd56c2ccc08cf9b/eval/eval_sumo_stage1_mc.py#L636-L687),
[work addition and path accounting](https://github.com/Abdulla4akash/vec_env/blob/908bd10f86542de94fc38af90dd56c2ccc08cf9b/eval/eval_sumo_stage1_mc.py#L784-L850),
and [five-slot scan and drain](https://github.com/Abdulla4akash/vec_env/blob/908bd10f86542de94fc38af90dd56c2ccc08cf9b/eval/eval_sumo_stage1_mc.py#L853-L876).

Given an empty initial vector, all nine RSUs tie at zero and the first choice
is RSU 0. Once that substep admits positive work, RSU 0 is no longer a minimum;
the next lowest-index zero is RSU 1. This repeats for subsequent nonempty
substeps. If a substep adds no work, the next minimum does not advance.
Consequently, five target decisions can fill at most the prefix 0–4. Clearing
the queues before the next batch restores the same all-zero tie and restarts
the prefix at RSU 0.

Two parts of the explanation have different roles:

- **One common target across each of five substeps** limits new placements
  to at most five distinct RSUs in a second.
- **Repeated empty starts and the lowest-index tie-break** make the chosen
  RSUs the same low-index prefix across seconds. Without those conditions,
  the full-run union need not remain five.

This explains the fixed RSU identities under the recorded conditions. It does
not prove that this mechanism alone accounts for the full deadline-performance
difference between common-target and per-task placement.

## Worked recorded second

The example is seed 0's first second containing a gate rejection, selected by
that deterministic rule rather than by the size of its effect: trace time
28,800 s (08:00:00), step 0.

| Task substep | Observed target | Newly admitted tasks | Admitted work at that target (ms) | Gate rejections |
|---:|---:|---:|---:|---:|
| 0 | 0 | 14 | 187.836 | 1 |
| 1 | 1 | 6 | 115.672 | 0 |
| 2 | 2 | 3 | 7.495 | 0 |
| 3 | 3 | 2 | 70.472 | 0 |
| 4 | No V2I attempt recorded | 0 | 0 | 0 |

At substep 0, the rejected candidate shared RSU 0 with the co-batch candidates,
while RSUs 1–8 remained empty. The inference for the unobserved last target
is RSU 4, but no task used it in this second. All four occupied queues drained
before the next batch. Full workload vectors and one example per draw are
retained in [worked_examples.json](worked_examples.json).

## Rejections despite idle alternatives

The audit checked the other RSUs' reconstructed workload and task count at
each rejecting substep. Since common-target sends all that substep's admitted
work to one RSU and no service drain occurs inside the substep, the other
RSUs' states remain unchanged throughout its candidate processing.

**All 511,684 gate-rejected tasks had at least five other RSUs with zero
workload and spare task-admission capacity.** The number of such alternatives
was between five and eight. RSUs 5–8 were entirely unused throughout all runs;
the additional idle alternatives depended on which substep rejected the task.
Gate rejections occurred only in substeps 0–3; none occurred in substep 4.

These are backlog-gate rejections while alternative queues are idle, not
evidence that the 6,220-task waiting rooms were full. An empty alternative
would satisfy the isolated backlog and count conditions for a positive-deadline
candidate if all other decisions were held fixed. This is **not** an estimate
that all those tasks would meet deadlines after redistribution: moving tasks
changes subsequent queues, admissions and latencies. No counterfactual rescue
count was calculated.

## Unavailable fields and interpretation limits

- Common-target substep-start/pre-drain workloads are reconstructed, not directly
  instrumented in its saved arrays. Matching zero endpoints alone cannot verify
  every intermediate workload; reconstruction also relies on the frozen service
  reference, recorded admissions and audited enqueue code.
- Candidate-level working offsets and the intermediate three-pass admission
  masks were not saved. This audit does not claim a fresh independent replay
  of the gate predicate for every candidate.
- Separate operational radio-quality/viability samples were not saved in these
  task archives. V2I-unavailable outcomes are distinct from the audited gate
  rejections; the audit does not reconstruct their channel realizations.
- Destinations are unobserved when a substep has no V2I attempts.
- Changed-tie-break, persistent-backlog and redistribution outcomes are absent.
  The audit is post-hoc mechanism evidence for the four existing morning draws,
  without new confidence intervals or a claim of universal scheduler behavior.

## One proposed falsification test — not run

Use **the first 30 seconds of fleet seed 0**, with a baseline prefix replay and
one candidate prefix on an isolated experimental checkout. Change only the
tie-break among equal minimum workloads: use cyclic RSU priority starting at
`step_index modulo 9`, while retaining one common target per substep. Preserve
the actor, task/random stream, five substeps, admission reconciliation, service,
capacity, layout and zero forwarding charge. Do not alter `K_MAX`, which would
also change the task-arrival contract.

If the explanation is correct, the selected low-workload prefix should rotate:
the used identities should reach all nine RSUs over the prefix, while each
second still places tasks on at most five RSUs. Require empty batch starts,
at least one admitted V2I task per second and the intended cyclic ties before
assessing that prediction. Persistent confinement to RSUs 0–4 under those
verified conditions would falsify the proposed indexing explanation or reveal
another selector restriction. With homogeneous RSU service and zero charged
forwarding, equal deadline/admission outcomes are an additional conditional
prediction; forwarding identities may change.

This is a short discriminating test of fixed identities versus within-second
dispatch concentration. It is **proposed only**: no prefix or full simulation
was launched for this audit.

## Evidence and reproduction

- [Audit result and exact input hashes](audit_results.json)
- [All 43,200 per-second target records](per_second_targets.csv.gz)
- [Twenty seed-by-substep summaries](per_substep_summary.csv)
- [Read-only analysis source](audit.py)
- [Checksum ledger](SHA256SUMS)

The script uses the original local replication directory and writes only this
new audit directory. Its reconstruction calls the archived workload replay,
not the evaluator or a campaign runner. Preserve the original inputs and use
a separate output copy for any subsequent audit rerun. The original study
arrays, commands, summaries, protocol, scripts and evaluator source were
unchanged at the end of the audit.
