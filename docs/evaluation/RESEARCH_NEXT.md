# Current authoritative research direction

**Status date:** 2026-08-08
**Scope:** supervisor-aligned Randy/VEC dissertation experiments
**Current phase:** E1 multi-draw campaign; seed 1 complete at all three caps
**Execution authority:** stopped before fleet seed 2; do not start another cell

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
`fcc4602d337de4824fb3b23ead9697aba41c3621`, together with the seed-1 records in this reviewed
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
- campaign execution: all six seed-1 ten-step smokes and all three seed-1 full cells passed, with
  zero failures and no seed-2 process;
- seed-1 task-stream identity: offered count, `task_active` and `task_type` matched across 0.75x,
  2.5x and 40x; each full cell passed all 32 task/work/numerical checks;
- seed-1 descriptive pattern: higher caps admitted more tasks and rejected fewer, while offered
  deadline attainment decreased slightly then plateaued and latency rose sharply;
- seed-0 qualitative comparison: the same seven-field admission/rejection/deadline/latency pattern
  was observed; this is descriptive two-draw evidence, not five-draw inference;
- multi-draw E1 evidence: seed 0 and seed 1 rows are available, but the predeclared five-draw
  estimate is not yet available;
- E2 deterministic execution-RSU placement: not started;
- Randy's reported `0.6943`: not reproduced;
- native physical completion/result-return evidence: unavailable.

The cumulative evidence and interpretation are in the
[E0-to-E1 seed-0 research record](e1/e1_seed0_three_cap_research_record_2026-08-08.md).

## The next thing to do

**Stop and review the completed fleet-seed-1 three-cap result. Do not start fleet seed 2.**

The selected-backend campaign is governed by
[e1_multidraw_physical_campaign_manifest_v1.json](e1/e1_multidraw_physical_campaign_manifest_v1.json),
SHA-256 `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`.
It selects `macos_arm64_cpu_jax_0_4_30`, fixes concurrency at one and governs all scientific and
validation fields. The [seed-1 validation](e1/e1_seed1_three_cap_validation_v1.json), SHA-256
`cfb6e076cb70f7aeb4143f7a91c33bd2b04c9af6d4af60b2b082b87889dd58db`,
[comparison](e1/e1_seed1_three_cap_comparison_v1.json), SHA-256
`0f2ea863a91419412130f70d201814ff7f75fcce7f03019afaa48c6132709c5d`, and
[report](e1/e1_seed1_three_cap_campaign_report_2026-08-08.md) govern the new evidence.

All three full cells offered 13,076,234 tasks. Admitted tasks increased from 11,779,070 to
11,805,950 to 12,149,755 as the cap rose; rejected/unavailable tasks fell from 1,297,164 to
1,270,284 to 926,479. Offered deadline attainment was 0.688367691, 0.688245561 and 0.688245561,
while penalty-inclusive offered latency rose from 4,642.546 to 14,519.940 to 117,993.732 ms.

The exact equality of the observed 2.5x and 40x offered-deadline values is not a formal tie or
equivalence result. This is one new fleet draw, and five-draw inference remains prohibited until
the full predeclared replication set is valid. The current direct instruction requires a stop
before fleet seed 2. If the researcher subsequently directs continuation, the next manifest gate
is fleet seed 2 at 0.75x, beginning with two serial ten-step smokes.

### Exit condition

The backend gate is closed. It records one backend, exact CPU environment, reuse of the three
validated macOS seed-0 artifacts, concurrency one, a projected 20.089 CPU-hour new-cell total and
the final 12-cell matrix. The campaign gate exits only after all authorised cells either pass or
stop on a mandatory condition and the five-draw analysis is published. E2 remains unauthorised.

## What follows after this gate

E2 is not authorised by the 8 August instruction. After a valid E1 campaign exit, the researcher
must explicitly authorise the bounded E2 native-placement pilot before any of these actions:

1. validate the two-RSU strong-link-full/weaker-idle case against current evaluator state;
2. add or validate native ingress-RSU, execution-RSU, forwarding-count and forwarding-cost fields;
3. predeclare identical tasks, actor, trace, seeds, cap, physical semantics and fixed 1x service;
4. compare strongest-link, JSQ and deterministic deadline-aware placement for one incident seed;
5. stop unless path-level evidence and conservation pass.

E2 multi-seed expansion and the E3 backhaul pilot follow only after that bounded E2 pilot. Static
3x/reactive scaling follows placement/accounting stability. Staleness is a later extension.

## Explicitly not next

Do not start:

- E2 before the E1 multi-draw exit condition;
- static/reactive/proactive scaling;
- MAPPO or other actor retraining;
- a learned infrastructure dispatcher;
- action masking or an RSU-load-augmented actor;
- proactive prediction or oracle forecasting;
- bus modelling as a replacement for the VEC thread;
- any G4, other-GPU, TPU or cross-backend E1 campaign cell;
- any full E1 cell whose own two serial ten-step CPU smokes have not passed.

## Active blockers and requests

- The pinned JAX 0.4.30 CUDA-12 and stable JAX 0.11.0 CUDA-13 G4 attempts are separate retained
  pre-task failures. No G4 scientific compatibility or performance measurement is available.
- All three seed-1 cells passed, but nine new full cells remain. The immediate blocker is the
  explicit stop-and-report boundary before fleet seed 2, not a scientific failure.
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
