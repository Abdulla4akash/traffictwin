# Current authoritative research direction

**Status date:** 2026-08-09
**Scope:** supervisor-aligned Randy/VEC dissertation experiments
**Current phase:** E1 physical multi-draw campaign complete; five-draw result ready for review
**Execution authority:** stopped after the predeclared E1 exit; do not start E2 or another cell

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

The evidence base through TrafficTwin execution commit
`5111cbc23ec16b031435b2aba5a11e9f9074d3e9`, together with the final records in this reviewed
change, establishes:

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
- E2 deterministic execution-RSU placement: not started;
- Randy's reported `0.6943`: not reproduced;
- native physical completion/result-return evidence: unavailable.

The cumulative evidence and interpretation are in the
[E0-to-E1 seed-0 research record](e1/e1_seed0_three_cap_research_record_2026-08-08.md).

## The next thing to do

**Stop and review the completed physical E1 five-draw result. Do not start E2 or another
experiment.**

The selected-backend campaign is governed by
[e1_multidraw_physical_campaign_manifest_v1.json](e1/e1_multidraw_physical_campaign_manifest_v1.json),
SHA-256 `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`.
It selects `macos_arm64_cpu_jax_0_4_30`, fixes concurrency at one and governs all scientific and
validation fields.

The [final campaign report](e1/e1_multidraw_physical_campaign_report_2026-08-09.md) separates
observations, matched statistics, interpretation and limitations. Its governing
[validation](e1/e1_multidraw_physical_campaign_validation_v1.json), SHA-256
`f1edacf318109eb0b9ccb7c8848b68fa199056c78d8329e1aa5e92c2e2395e0b`, passed all 15 full
runs and all within-seed identity checks. The
[comparison](e1/e1_multidraw_physical_campaign_comparison_v1.json), SHA-256
`b2f7e8bf8769e7359bf5731b4b98d1007d294ed55595ec4977886f976d600ec3`, contains the exact
five-draw matched analysis. The
[evidence index](e1/e1_multidraw_physical_campaign_evidence_index_v1.json), SHA-256
`aeecdece2cbfffef4d7e68ac398c42fb2f36af5a6a1256536f58186c547f74e5`, retains the 12
repeated-smoke/full-cell gates and permission-safe raw-output hashes.

Execution of fleet seeds 2-4 used the append-only controller
[`scripts/resume_e1_multidraw_physical_campaign.py`](../../scripts/resume_e1_multidraw_physical_campaign.py),
SHA-256 `c42ca19416d1921031b9685181e5b4798a8881d02a5c9e600fa3edceacb55cd4`. It is a bounded adapter over
the unchanged manifest-pinned runner. It verifies the accepted seed-1 evidence index, accepts only
seeds 2-4, derived caps and commands from the frozen manifest, used concurrency one and refused any
existing target or control record. Raw outputs remain outside Git under the manifest's logical
locator. The first direct-file controller invocation failed at local import before evidence
creation or evaluator launch; module-mode invocation then ran the unchanged committed controller.

### Exit condition

The backend and campaign gates are closed. The 12 new full runs consumed 23.662 evaluator
wall-hours at concurrency one, within the 48 CPU-hour bound. The matched analysis and final
permission-safe evidence records are complete. E2 remains unauthorised, so the exact exit action
is researcher review and stop.

## What follows after this gate

E2 is not authorised by the 8-9 August instructions. A new direct researcher instruction is
required before any bounded E2 native-placement pilot or any of these actions:

1. validate the two-RSU strong-link-full/weaker-idle case against current evaluator state;
2. add or validate native ingress-RSU, execution-RSU, forwarding-count and forwarding-cost fields;
3. predeclare identical tasks, actor, trace, seeds, cap, physical semantics and fixed 1x service;
4. compare strongest-link, JSQ and deterministic deadline-aware placement for one incident seed;
5. stop unless path-level evidence and conservation pass.

E2 multi-seed expansion and the E3 backhaul pilot follow only after that bounded E2 pilot. Static
3x/reactive scaling follows placement/accounting stability. Staleness is a later extension.

## Explicitly not next

Do not start:

- E2 without a new direct researcher instruction;
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
- Native path-event feasibility and explicit authority remain unavailable for later E2.
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
