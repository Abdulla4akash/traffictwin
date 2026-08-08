# Current authoritative research direction

**Status date:** 2026-08-08
**Scope:** supervisor-aligned Randy/VEC dissertation experiments
**Current phase:** E1 seed-0 pilot complete; E1 multi-draw decision and predeclaration next
**Execution authority:** no new full campaign or E2 run is authorised by this record

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

The evidence base through TrafficTwin commit
`40d5dc792454165c1c845d776098d8f97b5e6d46` establishes:

- E0 corrected accounting and conservation: complete for the bounded repeated smoke and one full
  seed-0/fleet-0 strongest-link reference;
- E1 seed-0/fleet-0 pilot: complete at provisional 0.75x, 2.5x and 40x waiting-room ceilings under
  legacy and physical semantic packages;
- physical task and service-work conservation: passed at all three full cap points;
- legacy conservation: unavailable and non-conserving by source contract;
- multi-draw E1 evidence: unavailable because fleet seeds 1-4 have not been run;
- E2 deterministic execution-RSU placement: not started;
- Randy's reported `0.6943`: not reproduced;
- native physical completion/result-return evidence: unavailable.

The cumulative evidence and interpretation are in the
[E0-to-E1 seed-0 research record](e1/e1_seed0_three_cap_research_record_2026-08-08.md).

## The next thing to do

**Close the E1 seed-0 decision gate and produce a review-ready, predeclared multi-draw E1 campaign
manifest. Do not launch the campaign automatically.**

This is Day 4 of the dated research design. The seed-0 pilot has satisfied the preceding Day-3
execution requirement, but its exit decision and the multi-draw contract still need to be frozen.

### Required decision record

Record explicit answers to all of the following:

1. Which of the provisional 0.75x, 2.5x and 40x cap points remain in the final grid, and why?
2. Does the multi-draw grid retain the non-conserving legacy path as a historical diagnostic,
   require instrumentation, or restrict confirmatory inference to the conserved physical path?
3. Is the provisional `uk2030` fleet accepted for this bounded study?
4. Is fleet seed the replication unit with fleet seeds 0-4 and evaluator seed fixed/disclosed, as
   recommended by the dated audit?
5. What is the primary estimand and decision rule? Offered-task deadline attainment remains the
   primary outcome; admitted completion, latency, rejection and work conservation stay separate.
6. Is an ordinary-traffic control required, and at which most informative cap points?
7. What compute allocation, allowed concurrency, durable raw-output location and retention policy
   are approved?
8. What run-level stop conditions apply before later seeds or cells proceed?

The decision must continue to state that the waiting-room ceiling is admission/in-flight capacity,
not compute power, and that simulated deadline attainment is not confirmed physical result return.

### Required campaign manifest

The launch-ready manifest must include:

- exact TrafficTwin, vec_env and tos-data commits;
- evaluator, actor and trace paths plus SHA-256 identities;
- scenario date/window and every seed identity;
- selected cap grid and exact source-resolved cap values;
- legacy/physical inclusion decision and all queue/admission semantics;
- strongest-link placement, fixed 1x service, load balancing off and scaling off;
- common task-stream and seed-pairing contract;
- primary/secondary metrics, units and denominators;
- conservation, rejection-reconciliation, finite/nonnegative and no-silent-loss assertions;
- per-cell repeated-smoke gate, run order, stopping rule and failure-retention policy;
- raw-output locators, checksum/naming policy and permission boundaries;
- compute budget, concurrency and expected campaign size;
- analysis plan based on matched per-seed differences without task-level pseudo-replication.

### Exit condition

This gate is complete only when one of these is true:

1. approved multi-draw E1 outputs for the selected grid have passed validation; or
2. compute is unavailable and a fully reviewed, launch-ready campaign manifest is committed, with
   the campaign explicitly queued rather than one seed presented as conclusive.

## What follows after this gate

Only after the E1 multi-draw gate exits may the project begin the bounded E2 native-placement
pilot:

1. validate the two-RSU strong-link-full/weaker-idle case against current evaluator state;
2. add or validate native ingress-RSU, execution-RSU, forwarding-count and forwarding-cost fields;
3. predeclare identical tasks, actor, trace, seeds, cap, physical semantics and fixed 1x service;
4. compare strongest-link, JSQ and deterministic deadline-aware placement for one incident seed;
5. stop unless path-level evidence and conservation pass.

E2 multi-seed expansion and the E3 backhaul pilot follow only after that bounded E2 pilot. Static
3x/reactive scaling follows placement/accounting stability. Staleness is a later extension.

## Explicitly not next

Do not automatically start:

- E2 before the E1 multi-draw exit condition;
- static/reactive/proactive scaling;
- MAPPO or other actor retraining;
- a learned infrastructure dispatcher;
- action masking or an RSU-load-augmented actor;
- proactive prediction or oracle forecasting;
- bus modelling as a replacement for the VEC thread;
- a large local serial campaign without an approved compute/output plan.

## Active blockers and requests

- final cap-grid and legacy-evidence decisions;
- approval of the provisional fleet and seed protocol;
- CSF3 partition/quota, durable storage and allowed concurrency;
- Randy's original sweep package and exact definitions, if historical reproduction remains desired;
- native path-event feasibility for later E2;
- GitHub Actions billing/spending state, which currently prevents jobs from starting.

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
