# Current authoritative research direction

**Status date:** 2026-08-08
**Scope:** supervisor-aligned Randy/VEC dissertation experiments
**Current phase:** E1 seed-0 design gate closed; pinned-environment G4 smoke failed; backend pending
**Execution authority:** no new E1 smoke or full campaign cell is currently authorised

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

The evidence base through TrafficTwin parent commit
`b7dd42be5d02d6c2f6bfb120d9fabf90f7b9ca66`, together with the pre-run records in this reviewed
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
- campaign backend: still pending; no campaign cell has started;
- multi-draw E1 evidence: unavailable;
- E2 deterministic execution-RSU placement: not started;
- Randy's reported `0.6943`: not reproduced;
- native physical completion/result-return evidence: unavailable.

The cumulative evidence and interpretation are in the
[E0-to-E1 seed-0 research record](e1/e1_seed0_three_cap_research_record_2026-08-08.md).

## The next thing to do

**Review the failed G4 compatibility evidence and explicitly choose the next backend gate. Do not
start another smoke or a campaign cell without that reviewed choice.**

Abdulla's later direct instruction dated 8 August 2026 inserts a backend decision before the
campaign authority previously recorded here. The bounded comparison is governed by
[e1_colab_gpu_backend_smoke_manifest_v1.json](e1/e1_colab_gpu_backend_smoke_manifest_v1.json).
Its SHA-256 is `5f6a69cea9fd479cf0c8152565bfb52d01b6f080bacf9012da8b8f87708eb5b7`.
It fixes the existing physical 2.5x/fleet-seed-0 ten-step contract, requires two repeats, prohibits
CPU fallback and permits no full run.

The still-pending campaign design is
[e1_multidraw_physical_campaign_manifest_v1.json](e1/e1_multidraw_physical_campaign_manifest_v1.json),
SHA-256 `35531f397bc3ba5c93e2d49ac60b8d0f7bc016121f253bf2cc1496170ec2c66c`.
Its runner must refuse execution while `backend_decision.status` is not `selected`.

The direct G4-only instruction requested `colab new -s e1-g4-smoke --gpu G4`. The CLI and
in-runtime probes confirmed a G4 allocation backed by an NVIDIA RTX PRO 6000 Blackwell Server
Edition with 97,887 MiB VRAM. Exact input and package identities passed. The first evaluator
process then failed at `jax.random.PRNGKey(0)`: the pinned JAX 0.4.30 CUDA-12 `ptxas` could not
compile its `sm_90a` target for the assigned future Blackwell architecture. No task summary or
instrumentation was written; repeat 2 and every full cell were stopped. The failed-process time is
not a speed measurement.

The machine-readable
[G4 result](e1/e1_colab_g4_backend_smoke_result_v1.json) and
[human-readable report](e1/e1_colab_g4_backend_smoke_report_2026-08-08.md) govern this negative
evidence. G4 is not selected, and the campaign manifest remains deliberately unchanged with a
pending backend decision.

The next reviewed choice is either to select the already validated macOS CPU backend and update
both governing files, or to authorise a new package-compatibility smoke with its changed JAX/CUDA
contract predeclared. Do not silently substitute another Colab accelerator and do not change the
scientific environment merely to make G4 run. If a Colab backend is later selected, rerun all three
seed-0 cap points there; do not mix existing macOS seed-0 outputs with new Colab full outputs.

### Exit condition

The backend gate exits only when a selected single campaign backend, seed-0 handling, concurrency,
runtime estimate and final matrix are recorded in the campaign manifest and this file. The failed
G4 result alone does not close that gate. Until it closes, no campaign cell is authorised.

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
- any local or Colab E1 campaign before the backend decision is recorded in both governing files.

## Active blockers and requests

- The exact pinned JAX 0.4.30 CUDA-12 environment cannot execute on the assigned Colab G4
  Blackwell device: `ptxas` fails before task generation. No valid G4 speed or conservation result
  exists.
- A reviewed choice between the validated macOS CPU backend and a separately authorised revised
  package-compatibility smoke is missing. This blocks every campaign cell.
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
