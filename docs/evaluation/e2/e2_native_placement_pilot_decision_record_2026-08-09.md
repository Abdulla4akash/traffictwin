# E2 native-placement pilot decision record — 9 August 2026

## Decision

Authorise only the predeclared one-seed, three-arm E2 pilot after the exact
instrumentation, hand-check, independent Claude review, and repeated-smoke
gates pass. The pilot must then stop for researcher review.

The frozen contract is
[`e2_native_placement_pilot_manifest_v1.json`](e2_native_placement_pilot_manifest_v1.json),
SHA-256
`53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8`.

## Why E1 is closed

E1 completed its authorised physical multi-draw campaign at TrafficTwin commit
`a1423e604078f70c95d4115287d3f0391348becf`. All 12 new full cells, all 24
repeated smokes, and all 15 analysed full records passed their declared task
and service-work gates. The five-draw 40x-minus-0.75x offered-attainment
confidence interval included zero. That is inconclusive evidence, not
equivalence, non-inferiority, or a tie. No E1 cap or semantic variant is needed
to answer the bounded E2 placement question, and its manifests and raw outputs
remain immutable.

## Fixed scientific choices

The waiting-room cap stays at 2.5x, resolved to 6,220 tasks per RSU, because it
is the original/default E0 reference point. Choosing another cap after seeing
E2 would introduce an outcome-dependent intervention. Service stays fixed at
1x so E2 changes infrastructure placement/admission rather than capacity.
Scaling is off.

Backhaul is fixed at zero milliseconds. This is an ideal-fibre mechanism
pilot: forwarding identities, counts, shares, and paths are still measured,
but nonzero forwarding cost is the separate, unauthorised E3 sensitivity
question.

The Paper-2A MAPPO vehicle actor is frozen because the causal intervention is
infrastructure-side execution placement. The 17-dimensional actor chooses only
Local, V2I, or V2V and does not observe current RSU load. Native
The pre-existing `veh_action` array is the exact binding for the frozen greedy
actor output/action stream and must remain byte-identical across arms. Native
`veh_actor_logits` are retained as a diagnostic. Placement-dependent admission
can change modelled EV energy, then state of charge, then a later observation
and logit even though the actor parameters are frozen. Logit hashes, byte
identity, and maximum absolute divergence are therefore reported against the
predeclared float32 absolute bound of `1e-5`; this never permits an action
difference.

Only three arms are admitted:

1. `off`: strongest-link radio ingress and execution at that ingress;
2. `jsq`: strongest-link radio ingress with deterministic execution at the
   current least-backlog RSU;
3. `dla`: the same JSQ placement plus deadline-aware admission.

The `off`-versus-`jsq` difference is the bounded placement contrast. The
`jsq`-versus-`dla` difference isolates added deadline-aware admission within
the same JSQ placement family. `off` versus `dla` is a joint
placement-plus-admission contrast. `dla` must never be described as only
deadline-aware placement.

P2C and DLA-P2C are excluded because they add a stochastic controller path and
are unnecessary for the first deterministic mechanism check. Static/reactive
scaling, prediction, learned scheduling, action masking, actor augmentation,
and retraining would answer different questions and are deferred.

## Native path audit and instrumentation gate

Source inspection at vec_env parent
`0f01f4d2082d3e8b735e74a873095ab8eeba37cc` established that radio ingress is
the strongest instantaneous V2I link; `off` executes there; `jsq` selects from
current `rsu_busy_ms`; `dla` uses that JSQ selection and adds an admission gate;
capacity and deadline admission apply at the selected execution RSU; and
backhaul latency enters the successful V2I path only when execution differs
from ingress. The pre-existing saved task file did not expose these identities.

Candidate vec_env commit `e11f4445a9cc939a79d4f419c6f48b43ce110664`
adds output-only task ingress, selected target, actual execution, admission,
forwarding, and charged forwarding-latency arrays, plus frozen actor logits and
the already-computed total-energy numerator. It adds no PRNG split and does not
alter physics or existing definitions. The resolved module actually imported
by the evaluator is separately hash-bound to the candidate `vec_jax.py`.

The final ten-step matched no-effect checks against the untouched parent passed
for `off`, `jsq`, and `dla`: all existing scientific JSON values matched after
excluding `wall_s` and declared additive fields; all existing per-step and
per-task arrays matched in shape, dtype, and bytes; and the only new arrays were
the declared path fields and actor logits. Raw evidence is retained under
`/Users/akashx/AntigravityTest/e2_outputs/e2-native-placement-pilot-v1/instrumentation_no_effect_candidate_e11f444`.
An earlier gate-output serialization failure is retained separately under
`instrumentation_no_effect_candidate_df1e20b`; it produced no scientific
comparison verdict and its directory was not reused.

The production-evaluator two-RSU probe also passed. With RSU 0 saturated and
RSU 1 idle, `off` retained ingress/selection/execution at RSU 0, rejected work
at the cap, and emitted no forwarding. `jsq` admitted redirected work at RSU 1
and reconciled its forwarding and service-work counts. In the DLA case, 124
gate-rejected tasks retained a selected target but had actual execution `-1`,
were not admitted or forwarded, charged zero forwarding latency, and enqueued
no work. A separate output-only positive check charged exactly 2.5 ms only to
an admitted forwarded task; that probe is not an E2 science arm and does not
change the locked zero-backhaul design. All 34 checks passed. Raw evidence is
retained under
`/Users/akashx/AntigravityTest/e2_outputs/e2-native-placement-pilot-v1/two_rsu_probe_candidate_e11f444`.

## Statistical interpretation

This is one evaluator seed and one fleet draw. The analysis will report raw
arm values and raw differences only. Individual tasks are accounting records,
not independent statistical replicates. No fleet-seed confidence interval,
population generalisation, controller-superiority statement, equivalence
claim, non-inferiority claim, or real-world optimality claim is permitted.

A controller can reduce per-RSU imbalance while worsening deadline attainment.
Both are direct observations and neither may substitute for the other.

## Unsupported claims and validity threats

The pilot does not establish Kubernetes deployment, a learned dispatcher,
physical task return, deployment-scale backhaul performance, ordinary-traffic
robustness, bus behaviour, population generality, or multi-seed stability.
“Completion” is evaluator deadline success, not confirmed physical result
delivery.

Principal threats are the single fleet draw; fixed evaluator seed; provisional
UK-2030 fleet assumptions; a frozen actor trained in a different topology and
without current RSU load; ideal zero-cost forwarding; one incident scenario;
one cap; and deterministic JSQ's per-substep common argmin convention. These
are limitations to report, not permissions to add unpredeclared arms.

## Stop/go rule

The full pilot may start only after both draft PRs exist and independent Claude
returns exact `APPROVE` for both complete diffs, the exact commits, and this
manifest hash. `APPROVE_WITH_MINOR_FIXES` is not a full-run go verdict. Each arm
must then pass two serial ten-step repeats, exact within-arm scientific and
array repeatability, exact cross-arm task/fleet/action identity, and the
separately bounded actor-logit diagnostic.

Any identity drift, no-effect difference, path inconsistency, rejected
execution/forwarding, accounting or work-conservation failure, silent loss,
nonfinite/unexplained negative value, repeat difference, output collision,
raw artifact entering Git, or unpredeclared command stops the pilot. Failed and
negative evidence is retained.

The next decision after the three declared full arms is researcher review. No
additional E2 seed or E3, scaling, P2C, learning, retraining, prediction, or
ordinary-traffic run is automatic.
