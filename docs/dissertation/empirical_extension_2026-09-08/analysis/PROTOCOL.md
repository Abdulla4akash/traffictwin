# Retrospective extension protocol — 8 September 2026

Recorded before new aggregation, comparator outcomes or timing measurements.
Base: ee6a4b151d92329f9c26e3f344d87b70b84fc31e. EXECUTE_NEW_CONFIRMATION=false.

| Question | Evidence/action | Completion boundary |
|---|---|---|
| Does reversal recur with joint randomness? | Source/key/feedback inspection; seal eight joint blocks × four arms; dry-run runner | No full evaluation; recurrence remains unestablished |
| Does workload awareness beat spreading? | New causal round-robin; same admission kernel and explicit persistent pointer; bounded tests | Implementation qualification only; no fleet outcome for round-robin |
| What host cost accompanies scheduling? | Actual JAX helpers, 2 dimensions × 2 fixtures × 4 policies; 100 synchronised timed calls after 5 warm-ups | Timing variability, not fleet replication or end-to-end runtime |
| Which types contribute to the September gain? | Authenticate exactly eight existing primary-morning per-task files; aggregate three types, reconcile saved totals | Descriptive type-level outcomes; no new joins or subgroup tests |

## Benchmark declaration

Dimensions (N,R,K)=(215,9,5),(2488,10,5). Four policies: ingress_dla,
common-target dla, causal per_task_dla, causal round-robin. Fixtures, not
observed full substep inputs: types cycle T1,T2,T3; service uses each type's
nominal RSU work with deterministic wobble inside [0.9,1.1]; deadlines remain
100,500,100 ms. Sparse: one in ten V2I attempts, initially empty queues.
Busy: four in five attempts, initial workload 40..120 ms and count 1..R;
capacity 6220, identical radio masks/ingress/work across arms. Five substeps,
no intermediate drain; one final 1000 ms drain, source count-carry formula.
Actual service arrays are supplied before timing to all policies: excludes
actor, radio, RNG/service generation, transfer, outcome scoring and I/O.

Compile each configuration once explicitly; report lowering/compilation
separately. Five untimed synchronised warm-ups, then exactly 100 calls;
inputs device-resident, all output leaves synchronised. Report median, IQR,
p95 and min/max, with raw durations. No repetitions added for precision or
favourable ordering. Fixed configuration order; frequency/thermal drift is
uncontrolled. Record runtime/device/thread environment and compiler memory
analysis where available; memory estimates are not process peak RSS.
Float32, original JAX runtime; no library upgrades. Correctness comparisons
use exact booleans/integers, and atol=1e-3 ms, rtol=1e-6 for finite workloads;
timing is not an equivalence test against exact arithmetic. No thresholds
will be relaxed after a disagreement.

## Attribution and scope

These are current owner-requested, AI-assisted retrospective extensions.
Sandra's August advice supports explicit mechanisms, a worked example and
supporting metrics; it did not predeclare this comparator, benchmark or
joint-seed study. Historical raw-data recovery is excluded. Existing proof,
719-input investigation, 19-run audit and 23 joins are reused, not rerun.
