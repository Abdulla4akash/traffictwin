# E2b placement × admission factorial decision record — 10 August 2026

## Decision

Authorise exactly one new 3,600-step `ingress_dla` arm after the source audit,
existing-arm no-effect gate, production-path two-RSU probe, exact predeclaration,
independent Claude `APPROVE`, and two repeated ten-step smokes pass. Stop after the
four-cell descriptive analysis for researcher review.

The frozen contract is
[`e2b_placement_admission_factorial_manifest_v1.json`](e2b_placement_admission_factorial_manifest_v1.json).

## Closed prerequisites and missing cell

E1 remains closed at TrafficTwin commit
`a1423e604078f70c95d4115287d3f0391348becf`; its manifest SHA-256 remains
`0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`.
The original E2 pilot remains closed at final evidence commit
`c05736125a401b8176c53212b3915ec57b95fdc3`; its manifest SHA-256 remains
`53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8`.
Their repositories, manifests and external raw outputs are reuse-only.

E2 observed JSQ placement without a deadline gate and JSQ placement with the gate,
but did not observe strongest-link placement with the same gate. The new cell is
needed to distinguish placement, admission and their interaction. Only one arm is
needed because `off`, `jsq` and `dla` already use the identical task/fleet/action
stream and passed all E2 path, accounting and conservation gates. They are reused
only after their immutable root checksum ledger and declared document/run hashes
verify.

This is a mechanism-decomposition experiment. `ingress_dla` means strongest-link
execution plus deadline-aware admission. It is not load balancing. Existing `dla`
continues to mean JSQ placement plus deadline-aware admission.

## Production implementation audit

Source inspection at vec_env parent
`e11f4445a9cc939a79d4f419c6f48b43ce110664` established:

- `compute_per_vehicle_links` evaluates current V2I links and assigns
  `best_rsu_idx = argmax(link quality)`, which is the radio ingress;
- `off` retains `best_rsu_idx` as its execution target;
- `jsq` and `dla` choose a common `argmin(rsu_busy_ms)` target once per task
  substep; P2C variants use their separate existing keyed candidate path;
- `dla` enables the deadline gate by passing `use_dla=True` to `seq_offsets`;
- `seq_offsets` computes service times from the same already-split per-task keys
  later used by `process_agent`, adds fixed vehicle-order co-batch offsets, and
  reconciles deadline and cap admission for three fixed-point iterations;
- gate failures are `candidate AND NOT gate_ok`; remaining in-batch failures are
  cap rejections, so outcome codes 3 and 4 remain distinct;
- only `active AND V2I AND rsu_ok` tasks are scattered into `rsu_busy_ms` and
  `rsu_load`, so rejected work is excluded from enqueue;
- native instrumentation records strongest-link ingress, pre-admission selection,
  admitted execution, forwarding and forwarding latency directly inside the
  production evaluator; rejected tasks retain selection but execution is `-1`;
- forwarding latency is charged only when execution differs from ingress; and
- no part of placement or admission enters the frozen actor observation or action
  calculation.

The missing cell is therefore a static Python branch that sets the selected target
to the existing `best_rsu_idx` and enables the exact existing DLA gate. It adds no
PRNG split, sampled value, actor input, queue field, service path or output field.
The existing modes remain on their original branches.

## Fixed scientific choices

The waiting-room cap remains the default 2.5x reference, resolved to 6,220 tasks
per RSU. Choosing another cap after the E2 observations would confound the new
mechanism comparison. Service remains fixed at 1x, scaling remains off and
backhaul remains zero so E2b changes only the placement/admission cell.

The evaluator and fleet seeds remain zero, using the same Manchester incident
hour and provisional UK-2030 draw. The frozen 17-dimensional Paper-2A actor still
chooses Local, V2I or V2V and does not observe current RSU load. Exact vehicle
actions must remain identical. Float32 actor logits remain a diagnostic with the
already accepted absolute `1e-5` bound because admission-dependent energy can
change later state of charge; that bound can never excuse an action difference.

P2C, multi-seed replication, nonzero backhaul, E3, scaling, prediction, learning,
retraining and ordinary traffic are deferred because each changes a separate
factor or evidence population. No close numerical result may be called equivalent.

## Factorial estimands and interpretation

The four cells are `off` (strongest-link, gate off), `jsq` (JSQ, gate off),
`ingress_dla` (strongest-link, gate on) and `dla` (JSQ, gate on). Declared raw
contrasts are:

1. placement without the gate: `jsq - off`;
2. placement with the gate: `dla - ingress_dla`;
3. admission under strongest-link: `ingress_dla - off`;
4. admission under JSQ: `dla - jsq`; and
5. interaction: `dla - jsq - ingress_dla + off`.

The primary outcome is deadline-met tasks over all offered tasks. The same
descriptive formulas are applied to the declared secondary outcomes. Individual
tasks are accounting records, not independent statistical replicates. No confidence
interval, population generalisation, formal controller superiority, equivalence,
non-inferiority or real-world optimality claim is permitted.

## Validity limitations and stop rule

This is one evaluator seed, one fleet draw, one incident hour, one cap, fixed 1x
service and ideal zero-cost backhaul. The fleet is provisional; the frozen actor was
trained in another topology and lacks current RSU load; deadline success is not
confirmed physical result delivery. No ordinary-traffic control, deployment,
Kubernetes execution, scaling, P2C or learned controller is tested.

The full arm may run only after both stacked draft PRs exist and independent Claude
returns exact `APPROVE` for both complete diffs, exact commits and manifest hash.
Any existing-mode drift, RNG or action drift, non-ingress selection, forwarding,
rejected enqueue/execution, repeat difference, accounting/work failure, path mismatch,
nonfinite/unexplained negative value, identity/configuration drift, output collision,
raw/private Git addition, or need for an undeclared run stops E2b. Failed and negative
evidence remains retained. The next decision after the single full arm is researcher
review.
