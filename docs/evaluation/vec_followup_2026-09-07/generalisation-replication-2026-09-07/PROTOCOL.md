# Three-arm working-day replication: analysis declared before new outcomes

Primary data: four previously uninspected fleet draws, seeds **0, 2, 3, 4**.
Each draw runs ingress DLA (`ingress_dla`), inherited common-target least-busy
DLA (`dla`), and sequential per-task least-busy DLA (`per_task_dla`). These
are twelve full 10,800-step runs. No stopping or replacement depends on the
sign, size, or apparent significance of their outcomes.

The already inspected seed-1 pilot is excluded from the primary analysis.
Its two completed runs are preserved. A separate supplementary table will
combine seeds 0–4 for ingress and per-task only, explicitly labelling seed 1
as the exploratory pilot. No seed-1 common-target result is imputed or run.

## Fixed design

Use the canonical Manchester working-day morning trace for 15 October 2024,
08:00–11:00, with 215 padded vehicle slots and nine RSUs. Keep the frozen
onehot17 MAPPO seed100 actor, evaluator seed 0, UK2030 fleet preset,
canonical slot assignment and per-visit vehicle-queue reset, absolute 6,220
tasks/RSU capacity, service 1×, arrival rate 1.5, forwarding 0 ms, and scaling
off. Keep sequential/reject/conserved accounting and three reconciliation
iterations. The fresh per-task arm uses the existing zero-delay observation
instrumentation; no scheduler receives stale state. All arms use frozen
evaluator commit `908bd10f86542de94fc38af90dd56c2ccc08cf9b` and its recorded
Mac CPU runtime. No evaluator physics, admission algorithm or random stream
is changed for this campaign.

The workload-backlog admission predicate is inherited by all arms. The
common-target implementation retains its three-pass vectorised reconciliation;
the per-task implementation retains its causal sequential pass. Their
implementation semantics are precisely what this comparison examines.

## Primary outcome and estimands

The outcome for each run is deadline-met tasks divided by **all offered
tasks**, including rejected and unavailable tasks. The replication unit is
the fleet draw. Never pool individual tasks as independent replications.

For each seed, compute these signed differences in percentage points:

1. Per-task minus ingress.
2. Common-target minus ingress.
3. Per-task minus common-target.

Report all four differences for each contrast, their equally weighted mean,
sample standard deviation, minimum and maximum. Report a two-sided paired
Student-t 95% interval, `mean ± t(0.975, 3) × SD / sqrt(4)`, and additionally
a Bonferroni simultaneous interval using `t(1 - 0.05/(2×3), 3)` for the family
of three contrasts. These small-sample parametric intervals depend on the
distribution of draw-level differences. Four draws do not support a strong
distributional diagnostic, and no task-level significance test is used.

The historical reversal pattern is `common-target < ingress < per-task`.
Report whether it holds for each seed and for the three arm means. Distinguish
this descriptive ordering from uncertainty-supported evidence: for the latter,
the simultaneous interval for common-target minus ingress must lie entirely
below zero and that for per-task minus ingress entirely above zero. Report
any other ordering, mixed signs or inconclusive intervals without changing
the question after looking at the results.

## Secondary reporting

Report each arm and draw's offered/admitted/deadline-met task counts, rejection
categories, per-task-type attainment, energy per offered task, forwarding
counts, execution counts per RSU, admitted service work per RSU, post-batch
workload distribution and service utilisation. Label these as diagnostics,
without searching for a favourable secondary significance test.

The supplementary five-draw, two-arm summary reports the per-seed differences,
mean and range descriptively. It is not five unseen confirmation draws and
does not contribute to the primary three-arm intervals or ranking conclusion.

## Validation and execution

Before full runs, perform a 300-step probe for every seed/arm combination.
Check all probes before starting full cells. Within each seed require matched
fleet, task stream, actions and radio ingress; actor logits use absolute
tolerance 0.00001. Require exact task counts/outcome taxonomy, finite values,
valid paths, fixed absolute capacity and unchanged source/input identities.

For every arm, reconstruct admitted RSU service work from the frozen task-key
stream, task types, admissions and execution destinations. Check per-second
RSU workload and task-count carry against the saved records, admitted-work
totals against the summary ledger, and initial + admitted = served + final
remaining workload. Qualify this reconstruction against the pilot's saved
pre-drain instrumentation before using it on new draws. Queue endpoint
tolerance is 0.1 ms; accumulated work uses rtol 0.0001 and atol 1 ms, matching
the pilot. Report the actual discrepancies. Common-target selections must
share a destination within each task substep and select a least-workload RSU.

Preserve every attempt and stop on invalid inputs, drift, failed validation,
evaluator error, insufficient storage or a three-hour cell timeout. No
automatic full-cell retries. Full runs are serial, grouped by seed; each seed
runs per-task, ingress, then common-target so both comparators can be checked
against the same per-task reference. Every full task prefix must agree with
its own probe. Record the complete twelve-cell plan before starting probes.

This tests fleet variability within a second Manchester scenario. The morning
and incident scenarios differ in density, date/window, RSU layout/count and
trace entry/slot conventions. Their effect-size difference does not isolate
a single cause or establish independent geographical generalisation.
