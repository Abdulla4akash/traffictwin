# Three authorised dissertation follow-ups — 15 September 2026

## Authority and scope

The owner explicitly instructed: "okay run them all", referring to Claude's
suggestions 7 (native `dla_p2c`), 8 (half-speed servers), and 9 (second actor).
This protocol is recorded before their full outcomes. These are retrospective
extensions on the eight previously studied joint blocks, with new outcomes;
they are outside the original sealed confirmation family. They are not new
independent sampling of traces, actors or eight additional seed pairs. Historical
evidence and the original protocol remain immutable. No new training or remote
compute is needed. This study is distinct from the separate incident E3a study
with a different causal `p2c_dla` implementation.

## Fixed design

Use the original morning trace (10,800 seconds, padded N=215, R=9, K=5),
fleet/evaluator seed pairs (100,200) through (107,207), arrival parameter 1.5,
UK2030 fleet, count capacity 6,220, zero forwarding charge, no scaling,
sequential queue accounting with three reconciliation iterations, conserved
vehicle queues, queue entry reset and no SoC entry reset. CPU float32 runtime:
Python 3.11.15, JAX/JAXlib 0.4.30, NumPy 1.26.4. Preserve the instrumented
September 8 evaluator and its scheduling code byte-for-byte.

| Follow-up | Changed condition | New full cells | Primary contrasts |
|---|---|---:|---|
| 7 two-choice | Original actor, service 1, native `dla_p2c` | 8 | per-task − two-choice; two-choice − ingress; two-choice − round-robin |
| 8 half-speed | Original actor, service-rate multiplier 0.5, original four arms | 32 | per-task − ingress; common-target − ingress; per-task − round-robin; change in per-task-minus-round-robin gap from service 1 to 0.5 |
| 9 second actor | UK-fleet-trained actor, service 1, original four arms | 32 | per-task − ingress; common-target − ingress; per-task − round-robin |

Original four arms: `ingress_dla`, `dla`, `per_task_dla`, `causal_round_robin`.
Within each four-arm block rotate their order by block index, as previously.
Execute study 7, then 8, then 9, serially. Exactly 72 planned new full cells.
All historical comparator cells must pass original receipt/output/source
identity checks and a fresh raw accounting validation before reuse.

The primary outcome is 100 × deadline successes / ALL offered tasks. Rejects
remain in the denominator. The estimand is total scheduler intervention under
frozen actor weights; observations, logits and actions may change endogenously.
Do not enforce action equality or discard a block because actions differ.

## Actor and intervention identity

Original actor SHA-256:
`93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`.
Second actor SHA-256:
`b3eca1685245c59d1a3e86bd11ede887300bda1b00ba211a1913e467ad3f5183`.
Both have 17→64→64→3 float32 architecture and seed100 naming. The second
checkpoint is selected because its documented UK-fleet training distribution
differs, before inspecting these outcomes. It is not an independent training-
seed replication and does not establish generalisation to arbitrary actors.

Half-speed changes RSU service rate only: the existing environment multiplies
RSU CPU frequency by 0.5, doubling service work measured in milliseconds.
The one-second drain and count capacity stay fixed. Check the doubled actual
service arrays against matched historical cells; do not infer activation from
the flag alone. Changing actor must preserve matched exogenous inputs and
service work, while allowing its decision-dependent state to change.

Native `dla_p2c` samples two candidates with replacement per vehicle/substep,
chooses the lower initial substep workload (first candidate on ties), then uses
the original sequential admission reconciliation. Its extra randomness is
derived with fold-in tag 97 without advancing the exogenous stream. It differs
from causal per-task placement in both sampling and reservation visibility.
This compares full implementations, not a pure all-servers-versus-two ablation.

## Analysis fixed before outcomes

Each contrast uses eight equal-weight within-block differences, sample SD,
and two-sided Student-t intervals with 7 degrees of freedom. Report individual
95% intervals and within-study Bonferroni simultaneous 95% intervals (families
3, 4 and 3). Also report a single conservative Bonferroni family of all ten
new contrasts, using t(1−0.05/20,7), to make selection across studies visible.
The half-speed gap-change contrast is computed within block:
[(per-task−round-robin) at 0.5] − [(per-task−round-robin) at 1].
Do not substitute separate significance tests for this interaction contrast.
All other summaries, including actor gap changes and task/type breakdowns,
are descriptive. No task-level significance tests, cross-study pooling,
outcome-driven sample additions, seed substitutions, equivalence claims from
non-significance, or post-outcome choice of test. Report every result and its
uncertainty, including negative or inconclusive results. These intervals are
conditional on the selected trace/actors and the paired-effect sampling model;
eight previously examined blocks do not establish external validation.

## Qualification, validation and stopping

Before full execution, use the previously inspected pilot pair (fleet1,
evaluator0): four original normal-speed instrumented cells, native two-choice
instrumented and unchanged-reference cells, four half-speed cells, four second-
actor cells (14 attempts, 300 steps each), then one 150-step two-choice restart
for prefix determinism. Maximum 16 short attempts. Qualification is separate
from inference. Record all attempts, including failures, before launch.
Normal original arms must reproduce the preserved pilot scientific arrays;
two-choice must match unchanged evaluator shared fields. Verify within-block
exogenous equality, cross-condition input matching, service activation, actor
identity, outcome accounting, queue/service conservation, and cyclic pointer
progression. Replay native two-choice proposals from recorded keys/work.
Exercise refusal of altered counts, controls, hashes, missing receipts and
changed inputs using copies/mocks, not altered historical evidence.

Retain existing exact discrete/count checks, 1e-6-task reconstructed summary
tolerance, per-queue service conservation absolute 0.01 ms, drain absolute
0.001 ms plus relative 1e-6. Success uses inclusive latency <= deadline;
rejected tasks have ten-times-deadline penalty. No tolerance relaxation after
outcomes. A real source/input/control/accounting/timeout/storage failure stops
execution. Preserve partial outputs and diagnose it; no silent overwrite,
automatic retry, seed replacement or outcome-based exclusion. A repair needs
a documented amendment and newly bound code before affected work resumes.
Unexpected results and legitimate action differences do not trigger stopping.

Use an exclusive process lock, fresh output directories, 50 GiB initially and
20 GiB before each cell, a three-hour per-cell ceiling, and source/input hashes
checked at launch. Resume only complete cells with identical sealed config and
verified hashes. Independent source review is required before full execution.
Each cell saves commands, allowed numerical environment settings, timestamps,
stdout/stderr, task/step arrays, summary, and validation receipt. Each completed
block binds its cell receipts and matching controls. Analysis requires all
planned cells and receipts. Preserve a portable compact results packet and
plain-language research conclusions in the dissertation folder after completion.
