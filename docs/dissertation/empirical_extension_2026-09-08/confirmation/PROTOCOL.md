# Sealed prospective protocol: joint-randomness morning comparison

8 September 2026. **EXECUTE_NEW_CONFIRMATION=false. NOT EXECUTED.**
This is a retrospective project extension, declared before any new full-study
outcome. It is not Sandra's original design or a preregistration of the old
studies. No policy training, full evaluator prefix or campaign runs in this task.

## Questions and estimands

Eight joint blocks, each a previously unused fleet seed and evaluator seed;
four arms per block: ingress_dla, common-target dla, per_task_dla and
causal_round_robin v1. Exactly 32 planned full morning evaluations. Primary
family: per_task−ingress, common_target−ingress, per_task−round_robin, measured
in percentage points of **all offered tasks**. Reversal requires positive
per_task−ingress and negative common_target−ingress; report estimates and
intervals even if signs fail. Other contrasts descriptive. No task/type-level
significance tests. No pooling with prior pilots or original four-draw sample.

The estimand is a scheduler intervention under **frozen weights with endogenous
actions**, not forced fixed-action replay. This definition is resolved before
launch: admission can change V2I transmit energy, then EV SoC, observations,
logits and eventually actions. The old September action equality is an observed
control result, not a source guarantee for fresh randomness. Do not discard a
block because its observations, logits or actions differ across arms.

## Cyclic policy and fairness

One pointer initialised to 0; persistent through ascending padded candidates,
all five substeps and successive one-second batches. On active V2I with
positive ingress quality, propose current pointer and advance modulo R before
admission. No advance for padding, other modes or unavailable radio. Advance
also on substep-entry saturation, gate rejection and in-batch capacity failure.
No retries, full-node skipping or new random draws. The source's coarse
availability check follows radio quality and target selection, so no adjustment
to this proposed definition was necessary.

RR uses the same actual candidate work, strict backlog gate, two-stage count
capacity, final-admission scoring, service scatter and drain as causal least
workload. Repeated causal passes start with the same pointer and queues;
commit the final pointer once. Fixed 1x service, zero forwarding, scaling off;
RR v1 rejects incompatible state-delay/scaling/queue configurations. Existing
modes without the explicit extension-audit switch delegate to unchanged source.
The new copy instruments all four study arms identically. Route/kernel tests
are complete; full end-to-end qualification is **not executed**.

## Fixed inputs and random streams

Canonical trace SHA256 896aa5ad646d0d6c643de49eaa84373c9442b2d58483ac0e39aab76619c29628;
actor SHA256 93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208.
Morning T=10800, N=215, R=9, K=5; uk2030 fleet, arrival parameter 1.5,
absolute per-RSU count limit 6220; entry queue reset on, SoC reset off;
conserved vehicle queues; three admission replacements; unchanged float32 JAX
0.4.30 CPU runtime. Explicit runtime, raw trace/actor and output roots are
required. No historical raw inputs.

Seed rule: inspect surviving repository evaluation manifests, record their
hashes and observed seed fields, select the first eight absent nonnegative
fleet integers >=100 and evaluator integers >=200, zip in ascending order.
No crossed grid. The recorded absence is scoped to this manifest inventory,
not every experiment ever conducted. The seal records the resulting pairs.
Execution order rotates the four arms by block index, independent of outcomes.

The evaluator root key first splits into retained key and fleet key; explicit
fleet seed replaces only the latter. Fleet splitting samples tier, EV status,
initial SoC; transmit power derives from EV status. At each second the retained
key splits into next key, kt, ka, kl, ko, kp, kslots. These control observation
task type/size; service keys; operational fading; observation fading; arrival
counts; operational task types/sizes, respectively. ka splits by substep then
candidate, then into five process-agent keys, including RSU compute wobble.
Changing evaluator seed therefore changes much more than task assignment.
Target selection adds no random split in any planned arm.

Within blocks require equality of recorded fleet arrays, exogenous key arrays,
observation task descriptors, offered masks/counts, operational types/sizes and
pre-admission RSU service demands. The fixed source/key binding additionally
specifies the common fading primitives even where endogenous state changes a
selected link. Separately record observation/logit/action equality and maximum
absolute differences or changed action counts. Never force these to match.
Shared seeds alone are insufficient. No individual-decision causal claim
follows from a task transition after queues diverge.

## Inference and budget sensitivity

For each of three primary contrasts, compute eight paired block effects,
their mean and sample SD; use a two-sided Student-t interval with df=7 and
critical value t(1−0.05/(2×3),7). These are Bonferroni simultaneous 95% family
intervals, under independent joint blocks and approximately normal block
effects. Small n cannot validate normality or tail behaviour. Report every
block and both signs. No alternative test selected after inspecting results.
The precision file gives half-width = critical×SD/sqrt(8), across stipulated
SD values, and noncentral-t power across stipulated effect/SD ratios. These
are assumptions, not achieved power. Old fixed-evaluator-seed variance does
not estimate new joint-randomness variance. Eight blocks may leave wide
intervals; the compute budget does not establish adequacy.

## Execution, failure and preservation

Default dry-run only; the delivered seal refuses execution because the switch
is false. Future authorisation must explicitly set it true and reseal the same
matrix, without inspecting any new outcome. No more than 32 attempts are
allowed, serially, including failed attempts; there is no automatic retry.
A failed source/input/control/accounting check stops the whole study and
retains its logs and outputs. No seed substitution or effect-based stopping.
Resume accepts only completed cells with matching seal/command/output hashes;
an existing incomplete attempt stops and requires a documented protocol
amendment, never silently reruns. Full code changes invalidate the seal.

Budget: maximum 3 hours per cell, 96 serial wall-hours overall, one CPU process;
no paid service or cluster. Require 50 GiB free before first execution and
20 GiB before each cell; conservative allowance for new observation and task
logs, not a measured compression forecast. Timeout attempts count towards 32.
No outcomes are available in this package. The 32 cells themselves are checked
as they finish; the first valid four-arm block must pass all identities before
subsequent blocks. A failed check means incomplete confirmation, not removal
of an inconvenient result. Store raw files, logs, manifests and receipts in a
new root; hashes detect alteration but are not backups. Off-machine storage
still requires an author-selected/approved destination; nothing is uploaded.

Validation tolerances, declared before execution: task masks/categories/counts,
stream identities, source/input hashes and summary integer numerators are
exact; score numerator reconstruction absolute tolerance 1e-6 tasks for JSON
rounding; per-RSU/per-second admitted work versus backlog increment absolute
0.01 ms (float64 audit sum versus float32 scatter); drain tolerance 0.001 ms
plus relative 1e-6. A discrepancy is retained and stops execution; these
thresholds are not adjusted after a failure. Latency success uses the stored
inclusive task deadline; rejected latency is the exact 10×deadline penalty.

Pre-execution review amendment: the seal binds imported frozen causal and
state-delay helpers as well as the versioned copy. Final analysis requires all
eight passed block-control receipts, current seal, bound cell receipts and
unchanged output hashes, and rechecks shared exogenous identities. Individual
cell receipts alone cannot authorise primary inference. The earlier dry-run
seal is retained as PRE_REVIEW_SEAL.json; no full outcome preceded this change.
