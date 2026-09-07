# Optional two-prefix tie-break test

**Status: proposed only; not implemented, not executed.**

This prospective design records the small test suggested by the completed
[mechanism audit](evidence/REPORT.md). It is separate from the completed
replication and read-only audit. No full simulation is proposed, no result is
claimed, and the document itself is not an execution command or approval.

## Question and predictions

Does the lowest-index tie-break explain the fixed RSU identities, while the
five common-target decisions still constrain within-second placement?

Primary prediction: rotating the tie priority across seconds should produce
execution on all nine RSUs over the prefix, while each second still assigns
new work to at most five distinct RSUs. The frozen reference should retain
the low-index prefix. These predictions require empty batch starts and at
least one positive admitted V2I workload in each second.

Secondary, conditional prediction: under homogeneous RSU service, fixed
admission rules and zero forwarding charge, the per-task admissions and deadline
outcomes should remain unchanged despite different execution identities.
Forwarded-task identities/counts may change. This is not yet observed evidence
that better aggregate balance leaves deadline performance unchanged.

## Exactly two short conditions

Use only the **first 30 seconds of the canonical morning trace**, fleet seed
**0**, evaluator/task seed **0**:

| Condition | Execution-target rule |
|---|---|
| Reference | Frozen `dla`: one minimum-workload target per task substep, lowest RSU index on ties. |
| Candidate | Same common-target rule; among tied minima, prefer cyclic order beginning at elapsed step index modulo nine. |

For elapsed step `t` from 0 through 29, define the priority order as
`[(t + j) modulo 9 for j in 0..8]`. Select the first minimum-workload RSU in
that order. The order is shared by all five task substeps in that second.
This changes tie-breaking only, not the workload objective or dispatch cadence.

Retain the exact actor, canonical trace and entry markers, nine-RSU layout,
215 padded slots, 6,220-task absolute capacity, service 1×, zero forwarding
charge, scaling off, arrival rate 1.5, five task slots, three-pass common-target
admission reconciliation and queue-reset convention from the
[replication manifest](../vec_followup_2026-09-07/generalisation-replication-2026-09-07/manifest.json).
**Do not change `K_MAX`**, task sampling, candidate order or random-key splits.

## Implementation and validation boundary

Before execution, prepare an isolated candidate based on evaluator commit
`908bd10f86542de94fc38af90dd56c2ccc08cf9b`, record its exact patch and SHA,
and fix the two commands, output locations and runtime identities. The
candidate code and run manifest do not yet exist. Existing study outputs must
not be overwritten, and a mismatch must not trigger a longer run or tuning.

The reference prefix must reproduce the corresponding saved full-run prefix
for existing task and step fields. Compare the two prefixes for exact task
types/activity, fleet, actor actions and ingress. Keep the existing declared
actor-logit tolerance of 0.00001; do not select a new tolerance after seeing
outcomes. Verify task/work conservation in both conditions.

Record substep-start workloads and the selected target, validate that each
target is a minimum and that each tie uses the intended order, and verify
empty starts and positive admissions before assessing the primary prediction.
Report per-second execution sets and their whole-prefix union, admitted and
gate-rejected task counts, task-level deadline outcomes, forwarding counts
and workload shares. The short trace is a deterministic mechanism test, not
an independent fleet replication; no task-level significance test is planned.

## What would challenge the explanation?

If correctly rotated ties and empty starts are verified but execution remains
confined to RSUs 0–4 despite positive admissions in every second, the indexing
explanation is incomplete or another restriction remains. More than five
distinct new execution destinations in any second would contradict the retained
five-common-target contract and require implementation investigation.

If identities rotate but deadline/admission outcomes differ, retain the result
and investigate the failed conditional invariance prediction. Do not interpret
it automatically as a failure of the narrower identity explanation. If the
empty-start or positive-admission conditions fail, report that the intended
test conditions were not established rather than claiming falsification.

The test may be left unrun while the completed evidence is written up.
