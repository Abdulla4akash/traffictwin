# E2c gated-placement matched multi-draw decision record — 10 August 2026

## Decision and bounded authority

Run one matched replication of `ingress_dla` versus `dla` over four new provisional fleet draws,
fleet seeds 1, 2, 3 and 4. Each of the eight ordered cells receives two serial ten-step smokes and,
only after its cell gates pass, one 3,600-step full run. No other arm, seed, backend or scientific
intervention is authorised. The exact contract is frozen in
[`e2c_gated_placement_multidraw_manifest_v1.json`](e2c_gated_placement_multidraw_manifest_v1.json).

E1, E2 and E2b remain closed. Their manifests, reports, machine records and raw outputs are
immutable prerequisites and may only be verified and reused by hash. E2c does not reopen or
reinterpret any closed cell.

## Why this replication is required

The E2b seed-0 mechanism pilot generated the directional hypothesis. With the same deadline-aware
admission gate, the observed offered-task attainment was `0.715773211` for strongest-link
execution (`ingress_dla`) and `0.694939919` for JSQ execution placement (`dla`). The seed-0
`dla - ingress_dla` difference was `-0.020833292`. That is one pilot draw, not a population result.

E2c uses four new fleet draws as the replication units. Seed 0 is excluded from the primary
four-draw inferential calculation because it generated the hypothesis. It is retained only in a
separately labelled combined descriptive pilot-plus-replication summary after the primary result.
Individual task slots are accounting records and are never treated as independent replicates.

This is the cleanest available placement comparison because both arms use the same live
per-substep deadline-aware eligibility and fixed-point gate. It therefore avoids the inherited
`off` step-entry eligibility caveat identified in E2b. The controlled difference is infrastructure
execution placement:

- `ingress_dla`: strongest-link ingress is also the execution RSU; no forwarding;
- `dla`: JSQ selects the execution RSU and the same deadline-aware gate is applied there.

`dla` means JSQ placement plus deadline-aware admission. It is never described as only
deadline-aware placement.

## Read-only implementation feasibility audit

Source inspection at vec_env commit `0e5ed2f79b50011fe0475a5c2069978f9fdd778d` confirms that no
evaluator or instrumentation change is required:

- the evaluator CLI already accepts both `ingress_dla` and `dla`;
- strongest-link radio ingress is `best_rsu_idx` from `compute_per_vehicle_links`;
- `ingress_dla` sets its selected execution target to that `best_rsu_idx`;
- `dla` selects the existing per-substep JSQ target from current `rsu_busy_ms`;
- both modes pass `use_dla=True` into the same `seq_offsets` gate and fixed three-iteration
  reconciliation;
- outcome code 3 records deadline-gate rejection separately from cap rejection (code 4) and V2I
  unavailability (code 7);
- queue scatters include only admitted V2I tasks, so rejected work is not enqueued;
- selected targets are retained for rejected tasks while actual execution remains `-1`;
- native arrays already record ingress, selected target, actual execution, admission, forwarding
  and forwarding latency for every `[T,KMAX,N]` slot; and
- the actor is evaluated before placement/admission and neither mode introduces another PRNG split.

The existing TrafficTwin validators already enforce task accounting, both work ledgers, task-path
reconciliation, zero forwarding for `ingress_dla`, and admitted-only execution. E2c therefore adds
only TrafficTwin campaign orchestration, paired validation and deterministic analysis. vec_env and
tos-data remain read-only.

## Fixed design choices

The 2.5x waiting-room ceiling remains fixed at 6,220 tasks per RSU. It is the original E0 reference
point and was not selected after inspecting new E2c outcomes. Compute service remains fixed at 1x,
scaling is off, queue semantics remain sequential with three reconciliation iterations, vehicle
queues remain conserved, and cap admission remains explicit reject.

Backhaul remains zero to replicate the ideal-fibre mechanism in the seed-0 pilot. Forwarding paths
and counts remain measured, but nonzero forwarding cost is the separate unauthorised E3 question.
The evaluator seed remains 0 and is disclosed; the new replication unit is the fleet seed.

The actor remains the frozen 17-dimensional Paper-2A MAPPO actor. It selects Local, V2I or V2V,
does not observe current RSU load, and does not choose an execution RSU. Cross-arm vehicle actions,
task identities and fleet assignment must match exactly within each seed. Float32 logits retain the
already accepted absolute `1e-5` diagnostic bound; that diagnostic can never excuse an action
difference and cannot be widened after observing a result.

## Backend, compute and storage decision

Only `macos_arm64_cpu_jax_0_4_30` is selected: macOS arm64, Python 3.11.15, JAX/JAXLIB 0.4.30,
CPU backend `TFRT_CPU_0`, x64 disabled and concurrency one. The A100 gate is closed as rejected
because it failed same-backend byte repeatability, exact action identity and the frozen continuous-
array tolerance contract. No other backend is permitted.

Completed seed-0 full cells measured 8,901.2 seconds for `ingress_dla` and 7,787.5 seconds for
`dla`. Four new pairs therefore project to 66,754.8 evaluator seconds (18.543 hours), below the
30-hour maximum. Their full outputs plus the matching smoke footprint project to 1,677,780,708
bytes (1.563 GiB). Predeclaration observed 245.108 GiB free, 156.86 times the single projected
output and 78.43 times the required twice-projected-output gate. Runtime and storage are rechecked
before every cell.

## Predeclared analysis

For each new seed, the primary difference is:

`offered_deadline_attainment_dla - offered_deadline_attainment_ingress_dla`.

The four new differences are reported raw, followed by sign counts, mean, sample standard
deviation, standard error, median, minimum, maximum and a two-sided 95% Student-t interval with
three degrees of freedom. An interval excluding zero is reported only as evidence of a directional
difference within this bounded four-draw replication. An interval containing zero yields
`inconclusive_at_this_replication_size`.

Afterward, seed 0 and seeds 1–4 are summarised separately as a **combined descriptive
pilot-plus-replication summary**. That five-draw description is not a held-out confirmatory test and
does not replace the primary four-draw result.

Secondary outcomes use matched raw per-seed differences before aggregate descriptions: admitted
attainment, deadline-met tasks, admitted tasks, V2I admissions, gate and cap rejection, offered,
admitted and deadline-met latency, energy per offered task, forwarding count/share, execution-share
range and maximum execution share. Mechanism summaries use only recorded task paths and outcomes;
they do not invent decision-time backlog fields or infer unrecorded queue state.

## Claims, limitations and stop boundary

The study remains one Manchester incident hour, one provisional `uk2030` fleet family, one actor,
one cap, one fixed service level, one evaluator seed and four new fleet draws. It tests a controlled
simulator intervention, not physical deployment, Kubernetes execution, confirmed task-result return
or Manchester-wide real-world performance.

No equivalence, non-inferiority, formal tie, universal JSQ harm, population-wide controller
superiority or task-level significance claim is allowed. A mixed or interval-crossing result remains
inconclusive at this replication size. Mechanism wording is limited to observed path redistribution
being **associated with** paired deadline directions.

Any identity, review, repeatability, task/action stream, accounting, conservation, path,
configuration, numerical, storage, compute or no-overwrite failure stops all later cells and is
retained. Exact independent Claude `APPROVE` is required before the first scientific cell. The next
action after the eight cells and declared evidence package is researcher review; no experiment
follows automatically.
