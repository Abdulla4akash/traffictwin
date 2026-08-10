# Current authoritative research direction

**Status date:** 2026-08-09
**Scope:** supervisor-aligned Randy/VEC dissertation experiments
**Current phase:** E1 closed; bounded one-seed E2 native-placement pilot complete and ready for review
**Execution authority:** stopped after the predeclared E2 exit; do not start another E2 seed, E3 or another experiment

This is the repository's **highest-authority operational record for what research task happens
next**. Agents must read it before dated audits, checklists, experiment reports or implementation
plans. Those records remain authoritative for their evidence and historical decisions, but their
old “next” instructions are snapshots and do not override this file.

## Authority and conflict rule

Use this order when records appear to disagree:

1. A new direct instruction from the researcher or supervisor supersedes this file. Update this
   file in the same reviewed change before treating the new direction as repository state.
2. This file governs the current operational sequence, active gate and prohibited next actions.
3. [Sandra's supervisor-direction record](../../SUPERVISOR_RESEARCH_DIRECTION.md) governs the
   scientific problem, intervention separation and required measures.
4. Predeclared manifests govern an authorised experiment's exact configuration and stop rules.
5. Machine-generated validation records and checksummed raw outputs govern observed results.
6. Dated audits, replies, checklists and narrative reports provide design history and supporting
   interpretation; they do not govern the current next action unless this file says so.

The broad [TrafficTwin v0.7 design](../traffictwin-design-v0_7.md) governs product capabilities and
Manchester evidence gates. It is not the active experiment scheduler for this VEC research thread.

## Current verified state

The evidence base through E1 evidence commit
`a1423e604078f70c95d4115287d3f0391348becf` and E2 reviewed execution commit
`b2ce160c64a3ce6e9fef9f23cdb52c9ee1940dbb`, together with the final records in this change,
establishes:

- E0 corrected accounting and conservation: complete for the bounded repeated smoke and one full
  seed-0/fleet-0 strongest-link reference;
- E1 seed-0/fleet-0 pilot: complete at provisional 0.75x, 2.5x and 40x waiting-room ceilings under
  legacy and physical semantic packages;
- physical task and service-work conservation: passed at all three full cap points;
- legacy conservation: unavailable and non-conserving by source contract;
- seed-0 decision gate: closed by the
  [multi-draw decision record](e1/e1_multidraw_decision_record_2026-08-08.md);
- G4 backend feasibility: failed before task generation under the exact pinned JAX 0.4.30 CUDA-12
  environment; [the retained result](e1/e1_colab_g4_backend_smoke_report_2026-08-08.md) contains no
  scientific task output or speedup;
- G4 JAX/CUDA-13 compatibility: failed independently at the mandatory first primitive with an
  observed PJRT FFI/ABI-size mismatch; no evaluator repeat ran and the
  [compatibility report](e1/e1_g4_jax13_compatibility_smoke_report_2026-08-08.md) contains no task,
  conservation or speed result;
- campaign backend: selected as the established macOS arm64 CPU runtime with Python 3.11.15 and
  JAX/JAXLIB 0.4.30; the three exact macOS seed-0 physical artifacts remain reused by hash;
- campaign matrix: 12 new physical cells, fleet seeds 1-4 by 0.75x, 2.5x and 40x, with concurrency
  one and a mandatory two-repeat ten-step gate before every corresponding full cell;
- seed-1 task-stream identity: offered count, `task_active` and `task_type` matched across 0.75x,
  2.5x and 40x; each full cell passed all 32 task/work/numerical checks;
- seed-1 descriptive pattern: higher caps admitted more tasks and rejected fewer, while offered
  deadline attainment decreased slightly then plateaued and latency rose sharply;
- seed-0 qualitative comparison: the same seven-field admission/rejection/deadline/latency pattern
  was observed; this is descriptive two-draw evidence, not five-draw inference;
- multi-draw E1 execution: all 24 new ten-step smokes and all 12 new full cells passed, with zero
  failed or stopped scientific cells; the three seed-0 full records were reused by exact hash;
- within-seed identity: offered count, `task_active` and `task_type` matched across caps for all
  five fleet draws; all 15 analysed full cells passed task and V2I/vehicle-work conservation;
- primary five-draw result: raw paired `40x - 0.75x` offered-deadline differences were
  `[-0.000171609043, -0.000122129965, 0, -0.000253436884, 0]`; mean
  `-0.000109435178`, sample SD `0.000110357776`, SE `0.000049353498`, and two-sided 95% Student-t
  CI `[-0.000246462456, 0.000027592099]`;
- primary decision: the interval includes zero, so the comparison is inconclusive at this
  replication size; this is not formal equivalence, non-inferiority or a tie;
- secondary pattern: 40x admitted more and rejected fewer tasks than 0.75x in every fleet draw,
  while admitted-task attainment fell and admitted/penalty-inclusive latency rose sharply; every
  `40x - 2.5x` offered-attainment difference was numerically zero, without supporting an
  equivalence claim;
- E1 final evidence remains fixed at commit
  `a1423e604078f70c95d4115287d3f0391348becf`; its frozen manifest remains SHA-256
  `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`, and E1 is closed;
- E2 reviewed execution identities: TrafficTwin pre-run commit
  `b2ce160c64a3ce6e9fef9f23cdb52c9ee1940dbb`, vec_env instrumentation commit
  `e11f4445a9cc939a79d4f419c6f48b43ce110664`, and tos-data commit
  `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`;
- E2 instrumentation no-effect gate: passed for matched `off`, `jsq` and `dla` checks against
  vec_env source commit `0f01f4d2082d3e8b735e74a873095ab8eeba37cc`; every pre-existing
  scientific summary and array agreed exactly after excluding wall-clock and additive fields;
- E2 two-RSU production-path probe: passed all 34 checks, including off cap rejection without
  forwarding, JSQ forwarding from saturated ingress RSU 0 to idle RSU 1 with conservation, and
  DLA selected-target retention with rejected execution `-1` and no false forwarding;
- E2 independent Claude verdict: `APPROVE` for the exact reviewed commits and manifest after the
  requested changes were addressed and re-reviewed;
- E2 repeated-smoke gate: both ten-step repeats passed for each of `off`, `jsq` and `dla`; repeated
  scientific summaries and existing arrays were exact, and cross-arm offered tasks, task identities,
  fleet assignment and vehicle actions matched;
- E2 full one-seed pilot: all three 3,600-step arms passed path, task-accounting, numerical and
  V2I/vehicle service-work conservation gates; all root raw-evidence checksums verify;
- E2 common offered tasks: 13,076,234 in every arm, with identical `task_active`, `task_type`, fleet
  assignment and vehicle-action arrays;
- E2 strongest-link/off observation: offered-task attainment `0.683619229`, admitted-task attainment
  `0.766522526`, 11,661,973 admitted tasks, 1,818,131 admitted V2I tasks and zero forwarded tasks;
- E2 JSQ observation: offered-task attainment `0.675681775`, admitted-task attainment `0.727737086`,
  12,140,886 admitted tasks, 2,297,044 admitted V2I tasks, 2,067,204 forwarded admitted V2I tasks
  (share `0.899940968`), and execution-share range `0.000457980`;
- E2 placement contrast, JSQ minus off: offered-task attainment `-0.007937454`, admitted-task
  attainment `-0.038785440`, admitted tasks `+478,913`, offered-task mean latency
  `-1,338.918 ms`, admitted-task mean latency `+4,839.858 ms`, and execution-share range
  `-0.098202128`; the more balanced execution distribution did not improve deadlines in this draw;
- E2 DLA observation: `dla` means JSQ placement plus deadline-aware admission; offered-task
  attainment `0.694939919`, admitted-task attainment `0.897716302`, 10,122,571 admitted tasks,
  278,729 admitted V2I tasks, 232,729 forwarded admitted V2I tasks (share `0.834965145`), and
  execution-share range `0.240014494`;
- E2 admission contrast, DLA minus JSQ: offered-task attainment `+0.019258144`, admitted-task
  attainment `+0.169979215`, admitted tasks `-2,018,315`, and offered-task mean latency
  `-15,400.420 ms`; this is the added admission intervention, not a placement-only comparison;
- E2 joint DLA-minus-off observation: offered-task attainment `+0.011320691` with 1,539,402 fewer
  admitted tasks; it combines placement and admission and cannot isolate either mechanism;
- E2 statistical status: one evaluator seed and one fleet draw, descriptive only; tasks are not
  independent replicates and no controller-superiority or population-generalisation claim is supported;
- Randy's reported `0.6943`: not reproduced;
- native physical completion/result-return evidence: unavailable.

The cumulative evidence and interpretation are in the
[E0-to-E1 seed-0 research record](e1/e1_seed0_three_cap_research_record_2026-08-08.md).

## The next thing to do

**Stop and review the completed bounded E2 native-placement pilot. Do not start another E2 seed,
E3, scaling, learning or another experiment.**

The pilot is governed by
[e2_native_placement_pilot_manifest_v1.json](e2/e2_native_placement_pilot_manifest_v1.json),
SHA-256 `53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8`.
It fixes one Manchester incident draw, cap 2.5x/6,220 tasks per RSU, fixed 1x service, zero
backhaul, physical queue semantics, the frozen 17-dimensional actor, and only `off`, `jsq` and
`dla`.

The [pilot report](e2/e2_native_placement_pilot_report_2026-08-09.md) separates direct
observations, declared contrasts and limitations. The governing
[validation](e2/e2_native_placement_pilot_validation_v1.json) passed every smoke, full-arm,
cross-arm, path, accounting and conservation gate. The
[comparison](e2/e2_native_placement_pilot_comparison_v1.json) contains the exact raw one-draw
contrasts, while the [path summary](e2/e2_native_placement_path_forwarding_summary_v1.json)
contains ingress, selected-target, execution, forwarding and per-RSU evidence. The
[evidence index](e2/e2_native_placement_evidence_index_v1.json) records the exact raw-output
locators and checksum ledgers outside Git.

### Exit condition

The one-seed E2 gate is closed. The three full arms completed serially within their individual
10,800-second limits, and all final evidence records are complete. The exact exit action is
researcher review and stop.

## What follows after this gate

Nothing follows automatically. A new direct researcher instruction is required before choosing
among E2 multi-seed expansion, an E3 nonzero-backhaul sensitivity, or any later scaling or learning
work. Researcher review must first decide whether the observed JSQ deadline harm despite much lower
execution imbalance, and the DLA admission/attainment trade-off, justify another bounded experiment.

## Explicitly not next

Do not start:

- another E2 seed or arm without a new direct researcher instruction;
- P2C or DLA-P2C;
- E3 or any nonzero-backhaul run;
- static/reactive/proactive scaling;
- MAPPO or other actor retraining;
- a learned infrastructure dispatcher;
- action masking or an RSU-load-augmented actor;
- proactive prediction or oracle forecasting;
- bus modelling as a replacement for the VEC thread;
- any G4, other-GPU, TPU or cross-backend E1 campaign cell;
- any additional E1 cell or semantic/cap variant.

## Active blockers and requests

- The pinned JAX 0.4.30 CUDA-12 and stable JAX 0.11.0 CUDA-13 G4 attempts are separate retained
  pre-task failures. No G4 scientific compatibility or performance measurement is available.
- The E1 campaign has no unresolved execution cell. Its five-draw primary result is inconclusive
  at this replication size and must not be relabelled as equivalence or non-inferiority.
- CSF3 remains unavailable from this machine because its hostname is not resolvable.
- Randy's original sweep package and exact definitions remain unavailable if historical
  reproduction is later desired; his reported `0.6943` is not reproduced.
- E2 native path instrumentation is available and validated, but authority for reuse or expansion
  is absent until researcher review.
- GitHub Actions billing/spending state may prevent hosted checks from starting; local pre-run and
  campaign validation remain mandatory regardless.

Unknown historical inputs do not block fresh, clearly named experiments after their own manifest
and compute gate pass. They do block claims that Randy's historical sweep was reproduced.

## Maintenance rule

After every accepted research gate or new direct research instruction:

1. replace the current-state and next-action sections here in the same reviewed commit;
2. cite the exact manifest, validation, report, branch and commit supporting the transition;
3. move completed actions to verified state rather than leaving stale “do now” language active;
4. add a clear pointer here from any new audit, plan or handoff that contains sequencing language;
5. preserve negative, null and failed results and all remaining blockers;
6. never rewrite dated manifests or validation outputs to make them look current.

## Historical design sources

- [Full 7 August research audit](TrafficTwin_research_audit_2026-08-07.md)—ranked experiment
  matrix and seven-day design; historical sequencing snapshot.
- [Audit reply](TrafficTwin_research_audit_reply_2026-08-07.md)—short historical executive reply.
- [Immediate request checklist](TrafficTwin_immediate_request_checklist_2026-08-07.txt)—historical
  E0-start checklist; completed items are not current instructions.
- [Current supervisor scientific direction](../../SUPERVISOR_RESEARCH_DIRECTION.md)—scientific
  problem and comparison principles.
