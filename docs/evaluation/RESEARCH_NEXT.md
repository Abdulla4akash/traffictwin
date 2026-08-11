# Current authoritative research direction

**Status date:** 2026-08-11
**Scope:** supervisor-aligned Randy/VEC dissertation experiments
**Current phase:** E1, E2, E2b and the bounded E2c matched gated-placement replication are closed;
the E2c post-run F1 reporting amendment awaits fresh independent exact-head review
**Execution authority:** none; E2c has completed all authorised cells and no further experiment is
authorised without a new direct researcher instruction

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
- direct E2b instruction: add only `ingress_dla`, meaning strongest-link execution plus the exact
  existing deadline-aware admission gate, to complete the missing placement × admission cell;
- E2b vec_env candidate: branch `agent/e2b-ingress-deadline-admission-v1` at
  `0e5ed2f79b50011fe0475a5c2069978f9fdd778d`; it adds no RNG split, actor input, queue field or
  output field and leaves existing mode branches intact;
- E2b existing-arm no-effect gate: passed for `off`, `jsq` and `dla`; scientific summaries and
  every existing/path/action/logit array agreed exactly against E2 parent `e11f4445...`;
- E2b production two-RSU probe: passed all 67 checks; `ingress_dla` admitted 17 tasks at ingress
  RSU 0, gate-rejected 143, cap-rejected zero, forwarded zero and conserved work, while the prior
  off/jsq/dla probe summaries and arrays remained exact by hash;
- E2b reviewed identities: TrafficTwin reviewed execution commit
  `f4e1897d6c17cf106880303a6be839407abe663e`, vec_env commit
  `0e5ed2f79b50011fe0475a5c2069978f9fdd778d`, tos-data commit
  `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`, and manifest SHA-256
  `9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91`;
- E2b independent review: the initial `REQUEST_CHANGES` record is retained; the contrast-timing
  caveat and actual imported-`vec_jax` binding were fixed, and Claude then returned exact
  `APPROVE` after independently passing 15 TrafficTwin tests, 13 vec_env tests and all hash checks;
- E2b repeated-smoke gate: both serial ten-step `ingress_dla` repeats passed, with exact scientific
  summaries excluding wall time, byte-identical existing/path arrays, exact completed-E2
  task/fleet/action identities, byte-identical logits, zero forwarding and both work ledgers conserved;
- E2b single full arm: the only new 3,600-step `ingress_dla` run passed every identity, numerical,
  task, path, accounting and V2I/vehicle-work conservation check; it offered the common 13,076,234
  tasks, admitted 10,424,749 tasks and attained `0.715773211` over offered and `0.897826701` over
  admitted tasks;
- E2b path observation: 2,652,389 V2I attempts, 580,907 admitted V2I tasks, 2,071,344 gate
  rejections, zero cap rejections, 138 unavailable attempts, zero forwarding and a diagonal-only
  ingress-to-execution matrix; execution-share range was `0.060050920`;
- E2b placement effects: JSQ minus off without the gate remains `-0.007937454`; DLA minus
  ingress-DLA with the same gate is `-0.020833292`, so JSQ placement had lower observed offered
  attainment even with the gate in this draw;
- E2b admission effects: ingress-DLA minus off under strongest-link is `+0.032153983`; DLA minus
  JSQ under JSQ remains `+0.019258144`; the placement-by-admission interaction is `-0.012895838`;
- E2b mechanism observation: the one-draw result is consistent with deadline-aware admission
  providing the observed attainment benefit while JSQ placement reduced it in both admission
  states; this is descriptive mechanism evidence, not population generalisation or controller
  superiority;
- E2b timing limitation: `off` uses a step-entry coarse saturation eligibility while non-`off`
  modes use a live per-substep check, so the strongest-link admission contrast and interaction are
  not perfectly gate-only; observed unavailable counts were nevertheless 138 in both `off` and
  `ingress_dla`;
- direct E2c instruction: replicate only the gate-held placement contrast, `dla - ingress_dla`,
  over new matched fleet seeds 1–4; seed 0 generated the hypothesis and is excluded from the
  primary four-draw Student-t interval;
- E2c feasibility audit: vec_env commit `0e5ed2f79b50011fe0475a5c2069978f9fdd778d`
  already implements both modes, the shared live per-substep deadline gate, native path arrays and
  required outcome taxonomy, so no vec_env or tos-data change is authorised or required;
- E2c selected backend: `macos_arm64_cpu_jax_0_4_30`, projected at 18.543 evaluator hours and
  1.563 GiB of new raw output, with a 30-hour limit and twice-projected-output free-space gate;
- E2c reviewed identities: TrafficTwin reviewed execution commit
  `676f132406877bbc6fb92b6c2a08b675571aa9fa`, vec_env commit
  `0e5ed2f79b50011fe0475a5c2069978f9fdd778d`, tos-data commit
  `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`, and manifest SHA-256
  `fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a`;
- E2c independent review: the initial `APPROVE_WITH_MINOR_FIXES` record is retained; the storage
  ratio, primary-statistic regression tests, manifest-snapshot binding and JSQ substep limitation
  were fixed, and Claude then returned exact `APPROVE` after 30 TrafficTwin tests, 13 vec_env tests
  and seven targeted mutation checks passed;
- E2c execution status: all 16 serial ten-step smokes, all eight ordered 3,600-step cells and all
  four fleet-seed pair validations passed; no cell failed or stopped, and task accounting, native
  path reconciliation, V2I work conservation and vehicle work conservation passed throughout;
- E2c primary raw `dla - ingress_dla` offered-attainment differences for new fleet seeds 1–4 were
  `[-0.022097034972, -0.020519134179, -0.021447383092, -0.020825491499]`; all four were negative;
- E2c primary summary: mean `-0.021222260935`, sample SD `0.000699457605`, SE
  `0.000349728802`, and two-sided 95% Student-t interval with three degrees of freedom
  `[-0.022335254070, -0.020109267800]`;
- E2c primary decision: the interval excludes zero, providing evidence of a directional difference
  within this bounded four-new-draw replication; this is not population-wide controller
  superiority, equivalence, physical deployment evidence or a task-level inference;
- E2c combined descriptive pilot-plus-replication summary: seed-0-to-4 differences were all
  negative, with descriptive mean `-0.021144467130`, median `-0.020833291910` and range
  `[-0.022097034972, -0.020519134179]`; seed 0 was excluded from the primary interval and this
  five-draw description is not a held-out confirmatory test;
- E2c mechanism observation: compared with ingress-DLA, DLA admitted 297,616–320,400 fewer V2I
  tasks per new draw, forwarded 234,143–241,809 admitted tasks (shares `0.848793202`–`0.857025898`),
  and increased execution-share range by `0.165271543`–`0.181311635`; those path changes are
  associated with the consistently negative paired deadline direction under the inherited
  one-common-JSQ-target-per-substep convention;
- E2c compute/storage: the eight accepted full cells used 56,084.6 evaluator seconds and the 16
  smokes used 344.7 seconds, for 56,429.3 seconds (15.6748 hours) total under the 30-hour cap; raw
  evidence before the root index used 1,680,469,503 bytes, and the final root checksum ledger and
  evidence index were written without overwrite;
- E2c post-run reporting amendment: independent final-evidence review found the science valid but
  required the supervisor-facing summary to carry the study's essential limitations. The
  [explicit amendment record](e2c/e2c_postrun_reporting_amendment_2026-08-11.md) preserves the
  historical evidence-index hash and confirms that no scientific evidence, manifest, statistic,
  validation, configuration, raw output or checksum ledger changed;
- Randy's reported `0.6943`: not reproduced;
- native physical completion/result-return evidence: unavailable.

The cumulative evidence and interpretation are in the
[E0-to-E1 seed-0 research record](e1/e1_seed0_three_cap_research_record_2026-08-08.md).

## The next thing to do

**Fresh independent exact-head review of the reporting-only E2c F1 amendment.**

The exact E2c contract is the
[E2c manifest](e2c/e2c_gated_placement_multidraw_manifest_v1.json), with its SHA-256 sidecar. The
[decision record](e2c/e2c_gated_placement_multidraw_decision_record_2026-08-10.md) explains why
seed 0 is prior pilot evidence and why only placement differs in the new matched pairs. The
[completed report](e2c/e2c_gated_placement_multidraw_report_2026-08-10.md),
[validation](e2c/e2c_gated_placement_multidraw_validation_v1.json),
[comparison](e2c/e2c_gated_placement_multidraw_comparison_v1.json),
[mechanism summary](e2c/e2c_gated_placement_mechanism_summary_v1.json) and
[evidence index](e2c/e2c_gated_placement_multidraw_evidence_index_v1.json) are the authoritative
completed records. The
[post-run reporting amendment](e2c/e2c_postrun_reporting_amendment_2026-08-11.md) records why the
supervisor summary changed after execution without rewriting the historical evidence index.

### Exit condition

E2c met its scientific exit condition: exact independent approval, all 16 repeated smokes, all
eight full cells, four paired validations, the primary four-draw analysis, the separately labelled
seed-0-to-4 descriptive summary and final checksum/evidence records passed. The final repository
head is not frozen until the reporting-only amendment receives fresh independent exact-head review.
No evaluator run is part of that review gate.

## What follows after this gate

Nothing follows automatically. After the bounded E2c evidence package, researcher review must
decide what the matched placement evidence supports. Another fleet seed, E3/backhaul, scaling,
P2C, learning or retraining requires a new direct instruction.

## Explicitly not next

Do not start:

- `off`, `jsq` or any E2c arm other than `ingress_dla` and `dla`;
- any fleet seed outside 1–4 or a seed-0 rerun;
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
