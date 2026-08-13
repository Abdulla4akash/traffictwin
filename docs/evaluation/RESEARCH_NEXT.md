# Current authoritative research direction

**Status date:** 2026-08-13
**Scope:** supervisor-aligned Randy/VEC dissertation experiments
**Current phase:** E1, E2, E2b, E2c and E2d are closed and frozen; E2d completed its bounded four-draw
construct-validity study and remains immutable history. E3 dynamic-resource v2 contract v1
(`e3_dynamic_resource_v2_contract_v1` at `docs/evaluation/e3/e3_dynamic_resource_v2_contract_v1.md/.json`)
is predeclared on lane `01`/`worker/e3-lane-01-contract` from exact base `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`
and is the active bounded next research direction before any E3 trace execution.
**Execution authority:** none; E2d grants no automatic follow-on experiment authority, and E3 grants
no trace execution until its contract, validator, and tests pass independent review with `APPROVE`

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
- E2c frozen reporting-amendment head: `1a08d6e148a1e8c430da39c3d575eda3f8ea5929`; E2c remains
  closed and immutable;
- direct E2d instruction: add only `per_task_dla`, meaning per-task sequential least-busy
  (shortest-workload) placement plus the inherited deadline-aware gate, and compare its four new
  seed-1-to-4 cells with exact reused E2c `ingress_dla` and common-target `dla` evidence;
- E2d source audit: `rsu_busy_ms` is remaining compute service workload in milliseconds; inherited
  `dla` selects one lowest-index `argmin` across all RSUs per substep, while the new mode recomputes
  that target in ascending padded vehicle-slot order after every admitted service reservation;
- E2d first pre-run review: Claude returned exact `APPROVE` for TrafficTwin
  `6443b936064dba2766dcb8dee9146b246bc769bf`, vec_env
  `2f63706f46319433a2ba3af1df97afd0e56a95d1` and manifest SHA-256
  `b2d04fa31ae40fb0519ebd019817599be428392bf6b1ee98656740ea509aa420`;
- E2d pre-trace stop: after identity/environment/closed-evidence/storage preflight passed but before
  any evaluator launch, the agent found that the approved `--cell-index` path ran one seed's two
  smokes and immediate full cell before later seeds' smokes, contradicting the frozen global
  smoke-before-full order; execution authority for those identities was revoked, zero replay,
  smoke or full run started, and no scientific output was discarded;
- E2d corrected orchestration: TrafficTwin scientific-code commit
  `eb8571810cc0f29c8477b14e15a73d7e3c915f69` splits the runner into
  `--run-replay-gate`, full-free `--run-smoke-gate`, and smoke-free
  `--full-cell-index {1,2,3,4}`; every full invocation revalidates the global replay gate, global
  smoke PASS record and all eight smoke records before launch;
- E2d corrected manifest SHA-256:
  `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740`; it preserves the
  superseded receipt identity and binds a new immutable `claude_review_verdict_v2.json` path;
- E2d corrected-package review: Claude returned exact `APPROVE` for TrafficTwin
  `095e0c1fbd5307b60722cac2be89ae480911e7df`, unchanged vec_env
  `2f63706f46319433a2ba3af1df97afd0e56a95d1` and corrected manifest SHA-256
  `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740`; the distinct v2 receipt
  is retained beside, and does not overwrite, the superseded historical receipt;
- E2d execution status: all eight ordered existing-mode replay probes, all eight globally ordered
  `per_task_dla` smokes and all four serial 3,600-step cells passed; no run failed, stopped or was
  retried, and all task accounting, path reconciliation, V2I-work conservation, vehicle-work
  conservation and matched task/fleet/actor identity gates passed;
- E2d primary raw `per_task_dla - ingress_dla` offered-attainment differences for fleet seeds 1–4
  were `[+0.004636732564, +0.005867285642, +0.005071796666, +0.005509919752]`; all four were
  positive;
- E2d primary summary: mean `+0.005271433656`, sample SD `0.000533733895`, SE
  `0.000266866947`, and two-sided 95% Student-t interval with three degrees of freedom
  `[+0.004422143925, +0.006120723387]`;
- E2d primary decision: `directional_advantage_for_per_task_placement_within_bounded_draws`;
  within these four matched incident draws, per-task sequential least-busy placement exceeded
  strongest-link under the shared deadline-feasibility rule, indicating that the inherited
  common-target-per-substep convention was an important mechanism in E2c's negative direction,
  without proving it was the sole cause;
- E2d secondary raw `per_task_dla - dla` offered-attainment differences were
  `[+0.026733767536, +0.026386419821, +0.026519179758, +0.026335411251]`; the separately labelled
  mean was `+0.026493694591` and interval `[+0.026210763951, +0.026776625232]`;
- E2d mechanism observation: `per_task_dla` admitted 667,085–667,720 V2I tasks per draw, forwarded
  600,181–601,402 (shares `0.899437272`–`0.900926840`), used all ten RSUs and produced execution-
  share ranges `0.000705579`–`0.001386630`; the recorded per-substep target switching confirms the
  new mode did not reproduce inherited common-target dispatch, without inferring unrecorded queue
  state;
- E2d compute/storage: the four accepted full cells used 24,419.7 evaluator seconds; the complete
  campaign used 24,911.7 evaluator seconds (6.9199 hours), raw evidence before the root index used
  853,500,054 bytes, and the immutable root checksum ledger contains 218 members;
- E2d remains bounded to four matched provisional `uk2030` fleet draws, evaluator seed 0, one
  Manchester incident hour, one 2.5x/6,220-task cap, fixed 1x service, zero-cost backhaul, the
  inherited backlog-only gate and a frozen actor that neither observes RSU load nor selects the
  execution RSU; it provides no task-level, equivalence, universal least-busy, physical-return,
  deployment, Manchester-wide or population-wide claim;
- E3 predeclared contract v1 (2026-08-13, lane 01, base 80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761): JSON `e3_dynamic_resource_v2_contract_v1.json` is the single normative scientific contract and the Markdown `e3_dynamic_resource_v2_contract_v1.md` is a deterministic generated view via `render_markdown` (whole-file byte-equivalence required; JSON is authoritative) are frozen before any E3 trace execution; they preserve exact E2 identities (E2b fe2ed4e9bd9043b19b96a5f179390db629b01ccb, E2c 1a08d6e148a1e8c430da39c3d575eda3f8ea5929, E2d 80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761 with manifest f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740, actor 93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208, trace e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056, evaluator seed 0), distinguish placement/admission/scaling, enforce actor never observes RSU load nor selects execution RSU, queue ceiling is not compute capacity, rejected work never executes, fixed_1x is compute service baseline and static_overprovisioned is fixed 3x compute (multiplier 3, never queue capacity; static3x/static_3x forbidden), dynamic bounds 1--3 with exact reactive signal service_workload_ms (work-ms independent of capacity) scale-up >=800ms and scale-down <=200ms (600ms gap is hysteresis, no extra hysteresis_ms), cooldown 5000ms from applied, actuation delay 2000ms (2 ticks), one level, one pending, apply due before tick decision, stable inclusive edges, and transparent-baseline proactive per-RSU admitted arrival_work_ms at 1s ticks with exact four-point window W oldest-to-newest, warm-up 4, older_mean=mean(W[0:2]), recent_mean=mean(W[2:4]), trend=recent_mean-older_mean, forecast=max(0, mean(W)+2*trend) two ticks ahead, no future leakage (use only samples at or before observation time), same 800/200 thresholds, 600ms gap, cooldown 5000, delay 2000, bounds 1..3, one-level/pending, not optimal predictor, integer simulator-ms state age with 1000 ms outer tick and five within-tick task slots that do not advance physical time and candidate stale levels 0/1000/3000 ms (state age is signal snapshot age), exact compute-service semantics with invariant raw work_ms backlog, enqueue adds raw 1x work without dividing by capacity, drain per 1000 ms tick as min(backlog_work_ms, active_capacity_units * 1000) for all queued work including pre-scale (capacity not queue slots), due scaling applied at tick start before placement/admission and before latency estimate/drain with active capacity for entire tick and at most one resource_unit_seconds interval per RSU/tick as active_capacity_units * 1 even when idle, placement/admission/stale/reactive signals use invariant raw backlog_work_ms with same-tick reservation adding raw task work_ms and proactive using raw admitted arrival work_ms without capacity-normalized or queue-slot units, admission-time latency estimate (raw_work_ahead_ms + raw_own_service_work_ms) / active_capacity_units with unchanged radio/forwarding and no retroactive repricing and physical lifecycle fields remain null, reduction to E2d at fixed_1x and static_overprovisioned at 3 units from tick 0 with dynamic arms starting at 1 bounded 1..3, P2C feasibility-first with two distinct feasible candidates via stable counter key (evaluator seed, fleet seed, outer_tick, task slot, sequential_task_ordinal) using sorted ascending unique feasible RSU IDs and SplitMix64 over exactly (evaluator_seed, fleet_seed, outer_tick, task_slot, sequential_task_ordinal) with first index h % n, second index splitmix64(h) % (n-1) adjusted around first then sorted pair as deterministic pseudo-random modulo mapper with no hidden global RNG and negligible bias not mathematically exact-uniform (H1 is pair-only inspection/global-state dependence not statistical uniformity proof) and inspect-only-pair/lower-workload/stable RSU-id tie/immediate reservation/one-candidate and stale immutable delayed views with same-tick reservation overlay exposing requested/actual state_age_ms and observation/control times, stale-state semantics exact: staleness applies only to invariant raw backlog view for placement and inherited backlog-only deadline gate and reactive/proactive signals and does not mutate true environment/current active capacity/pending actions/current queue safety state, queue-ceiling/cap enforcement always uses true current waiting-room occupancy plus same-tick admitted reservations so stale views never overfill waiting room, radio viability remains current/frozen-channel input, deadline formula unchanged but workload observation has state_age, deterministic simulator initialization with 3000 ms control-clock offset for all arms when stale robustness evaluated prepopulating control times 0/1000/2000 with empty initial infrastructure state and trace tick 0 maps to control time 3000 ms as declared simulator initial condition not observed pre-trace Manchester traffic, permits exact 0/1000/3000 ms views without clamping/future leakage/unavailable laundering, proactive still requires four actual trace observations (pretrace zeros not warmup), scaling delay/cooldown use control-clock differences so offset adds no extra delay, fresh cells remain reusable because offset does not enter P2C key (outer_tick does) and formulas use elapsed differences and state_age 0 views identical, cost as resource_unit_seconds never monetary, required accounting offered/admitted/rejected/genuine classes/forwarded/deadline_success with unavailable started/compute_completed/returned/dropped remaining null, offered deadline attainment headline and admitted conditional diagnostic with resource_unit_seconds trade-off, staged candidate grid E3a (ingress_dla/per_task_dla/p2c_dla x fixed_1x x seeds 1..4, 12 cells, primary P2C minus per_task offered deadline) / E3b (per_task x fixed_1x/static_overprovisioned/reactive/proactive x seeds 1..4, 16 stage-listed entries but 4 per_task_dla/fixed_1x/0 byte-identical overlap with E3a reused not rerun so 12 unique additional) / E3c (per_task vs P2C at fixed_1x and reactive vs proactive at fixed per_task placement over 0/1000/3000 ms with 48 total contrast observations reusing 16 fresh observations not rerun leaving 32 stale variants) with 60 stage-listed base/additional entries but 56 unique planned executions (12 + 12 + 32) and equations 12+16+32=60 stage-listed and 12+12+32=56 unique and 48-16=32 stale variants and mandatory reduction before execution if representative benchmark projects unreasonable bounded local budget and E3c depending on fresh construct gates, paired fleet-draw inference N=4 with per-draw values/mean/95% Student-t interval compatible with E2 unless predeclared otherwise and includes-zero flag and no task-as-N/p-value/citywide/population claims, and validation/tests plus immutable manifest/gate requirements before any full cell; any post-observation source change requires a successor contract; no E3 trace execution has occurred under this contract;
- E3 validator and tests: `scripts/validate_e3_dynamic_resource_contract.py` strictly enforces the contract and rejects queue==compute, task replication, actor chooses RSU, free/unbounded scaling, unavailable lifecycle zero, monetary cost, hidden fleet_seed label, 200 ms pseudo-time, missing resource denominator, actual Kubernetes, future leakage, common-target P2C, and compute-service drifts (dividing enqueued work by capacity, draining only newly enqueued work, 1x-only drain, idle-free resource time, queue/capacity conflation, normalized placement/gate signals, retroactive latency repricing, wrong initial capacities, physical-completion claim) and the new pre-freeze distinctions — stale decision belief versus true execution outcome (observed_decision_backlog_work_ms is stale immutable workload plus decision overlay for placement/backlog-only deadline gate versus true_execution_backlog_work_ms is current true backlog plus actual prior same-tick admitted work for simulated queue wait/latency/deadline_success/enqueue/drain, optimistic stale admitted executes and may miss per true latency and pessimistic stale rejected never executes even if true would have been feasible, queue-cap safety still wins current, scaling decisions observe delayed signals while current capacity/action/drain operate on true state, deadline_success is based on true simulated latency never stale estimate as simulator outcome not physical lifecycle and later scale actions do not retroactively reprice), exact P2C dense counter-key mapping (outer_tick zero-based trace tick, task_slot zero-based within-tick substep [0,4] not advancing physical time, vehicle_slot zero-based padded fleet slot [0,2487], sequential_task_ordinal = task_slot * padded_fleet_width + vehicle_slot range [0,12439] per outer tick as dense position identity independent of active mask/actor choice/feasibility/admission/rejection so earlier outcomes never shift later pairs and vehicle_slot is provenance but declared mixer fields remain exactly five, forbidding active-only ordinal/ordinal reset-collision/200ms-time/outcome-dependent shifts), honest state-inspection estimands for H1 (feasibility-first P2C must enumerate all RSUs so must not claim only two total global reads/distributed communication savings/proven lower total state acquisition, separately recording feasibility_workload_checks/ranking_workload_inspections/unique_workload_values_observed with P2C ranking 0/1/2 per feasible count versus per_task_dla global argmin over R and common feasibility cost and duplicated reads remain visible as hypothesis about pair-only ranking vs global least-busy dependence not proved networking cost), and exact resource-state diagnostics (per-RSU per-tick capacity-adjusted utilization drained_work_ms / (active_capacity_units * 1000 work_ms) bounded [0,1] never queue occupancy as denominator, execution share actual admitted V2I per RSU over total admitted V2I with null and explicit reason when denominator zero not zeros, target switching over consecutive admitted V2I tasks in exact deterministic (outer_tick, task_slot, vehicle_slot) order with first admitted not a switch and rejected/non-V2I excluded and never across fleet draws, and resource_unit_seconds denominator stays required for diagnostic deadline per resource cost with no monetary or authoritative objective claim); `tests/test_e3_dynamic_resource_contract.py` proves each rejection by mutating valid payload copies without editing the canonical file in place and asserts specific error messages, with the Markdown regenerated only through `render_markdown`;
- E2d-lineage read-only audit (2026-08-13, five owned files, no commit/push/delegation/execution): exact normative JSON/whole-Markdown/render_markdown fail-closed validator/mutation-tests and RESEARCH_NEXT coverage for (1) exact P2C candidate predicate and low-cardinality behavior (active frozen-actor V2I + ingress radio viable, sorted feasible RSU set BOTH observed_decision_backlog_work_ms<deadline and true_current_waiting_room+same-tick<ceiling with current radio/queue and aged backlog only, n=0 v2i_unavailable/v2i_gate_rejected/v2i_cap_rejected, n=1 sole feasible without second hash/modulo ranking inspections=1, n>=2 deterministic distinct pair lower observed backlog stable lowest-ID tie, reserve true load/raw work and decision overlay immediately only on admission, killing sample-before-filter/stale queue-cap/undefined n=0/1/rejection ambiguity/rejected-work reservation); (2) fully reproducible uint64 P2C mixer (non-negative uint64 bounds, ordered evaluator_seed/fleet_seed/outer_tick/task_slot/sequential_task_ordinal, wrap modulo 2^64 after every operation, SplitMix64 z=(x+0x9E3779B97F4A7C15) mod 2^64; z=((z xor (z>>30))*0xBF58476D1CE4E5B9) mod 2^64; z=((z xor (z>>27))*0x94D049BB133111EB) mod 2^64; return z xor (z>>31), fold h=0x6A09E667F3BCC909 h=splitmix64(h xor uint64(field)) ordered fields, for n>=2 first_index=h%n j=splitmix64(h)%(n-1) second=j if j<first else j+1 with candidate order ascending unique RSU ID sorted pair only for telemetry, three independently computed exact hex/index test vectors including all-zero fields h=0x7d19c361a3548205 and boundary outer_tick=3599/task_slot=4/ordinal=12439 h=0x295c562a48f4f730, n=1 hashing skipped, killing alternate SplitMix/string-byte/signed overflow/field reordering/missing vectors/claim modulo exact uniformity); (3) canonical tick/snapshot/scaler transition used by every E3 cell (control_clock_offset_ms=3000 same telemetry schema for E3a/b/c including fresh cells so reused state_age=0 cell bytes truly identical, 8-step tick i-viii start from true state after prior drain, apply due pending with receipt, capture immutable tick-entry snapshot after due action before placement/admission, select exact t-state_age snapshot, if no pending and cooldown permits make at most one scaler decision per RSU and possibly emit/schedule one requested action, process all five task slots without advancing time, drain true raw backlog once by min(backlog,u*1000), charge post-due-action capacity u for [t,t+1000ms), cooldown starts at actual application elapsed>=5000 permits new request, just-applied starts cooldown so cannot request again that tick, any pending blocks all new directions, requested receipt draw/rsu/direction/from_units/requested_to_units/decision_time_ms/due_time_ms/observed_state_time_ms/state_age_ms/signal_name/signal_value and applied adds actual_application_time_ms/actual_to_units, counts scheduled requests and applied up/down separately, resource cost follows applied capacity only, reactive tick-entry signal is aged raw service backlog snapshot, proactive samples are completed prior trace-interval admitted-arrival-work samples with four actual trace intervals and aged arm uses only samples present in selected snapshot and pretrace empty never satisfies warm-up, killing decision-time cooldown/same-tick post-apply/action-count conflation/ambiguous timestamps and current/future arrivals not observable under declared lag); (4) exact simulated V2I latency/outcome contract (at admission with u=current applied units simulated_latency_ms=current_ingress_tx_ms+forwarding_ms+true_execution_backlog_work_ms/u+raw_task_service_work_ms/u+current_return_tx_ms with inherited radio/forward/return and random raw service draw, raw work enqueued never divided by u, deadline success is recorded admitted simulated latency<deadline, later scaling does not recompute latency backlog still evolves under actual capacity, rejected work never enqueues never succeeds and inherited 10*deadline penalty explicitly not valid latency observation, report admitted-task latency only and any declared deadline-met diagnostic offered-task latency null/unavailable because rejected penalty not physical latency, started/compute_completed/returned/dropped remain null with reasons, killing backlog-only/stale outcome/later repricing/rejected penalty in latency mean); (5) lossless accounting and exact contrast completion (offered=admitted+rejected rejected=v2i_gate_rejected+v2i_cap_rejected+local_mqd_rejected+v2v_mqd_rejected+v2i_unavailable+v2v_unavailable 0<=deadline_success<=admitted 0<=forwarded<=admitted_v2i<=admitted, rejection share rejected/offered forwarding share forwarded/admitted_v2i null+reason if denominator zero, deadline per normalized cost offered deadline attainment/resource_unit_seconds null+reason if cost zero, work-ms conservation separately for V2I and vehicle queues, unavailable V2V work has no destination work remains explicit count not zero, missing/incomplete cells make matched contrast incomplete/null never reduce n, reportable contrast requires all four paired seeds 1..4 exact treatment-minus-control sign, predeclared E3a primary p2c_dla-minus-per_task_dla for offered deadline at fixed_1x/state_age=0 secondary p2c_dla-minus-ingress_dla, E3b per_task_dla/state_age=0 each of static_overprovisioned/reactive/proactive minus fixed_1x for offered deadline/rejection_share/resource_unit_seconds plus proactive-minus-reactive diagnostic no scalar best, E3c at each state age p2c_dla-minus-per_task_dla under fixed_1x and proactive-minus-reactive under per_task_dla for offered deadline/rejection_share/resource_unit_seconds plus imbalance/action diagnostics, draw is N=4 tasks never replicates); preserves every prior binding, JSON sole authority, deterministic whole-Markdown rendering, 56 unique cell bound, and all passing mutation tests without weakening a test. The five owned files are JSON contract, Markdown contract, validator, tests, and RESEARCH_NEXT; no commit, push, delegation, or execution performed, and missing-Markdown still fails closed via validator default.
- Randy's reported `0.6943`: not reproduced;
- native physical completion/result-return evidence: unavailable.

The cumulative evidence and interpretation are in the
[E0-to-E1 seed-0 research record](e1/e1_seed0_three_cap_research_record_2026-08-08.md).

## The next thing to do

**Independent contract review of the exact E3 dynamic-resource v2 contract v1 before any E3 trace execution.**

Review the normative JSON [E3 contract JSON](e3/e3_dynamic_resource_v2_contract_v1.json) (single authority) and its deterministic generated Markdown view [E3 contract Markdown](e3/e3_dynamic_resource_v2_contract_v1.md) (byte-equivalent via `render_markdown`), the validator [validate_e3_dynamic_resource_contract.py](../../scripts/validate_e3_dynamic_resource_contract.py), and the strong tests [test_e3_dynamic_resource_contract.py](../../tests/test_e3_dynamic_resource_contract.py) on lane `01` (`worker/e3-lane-01-contract`) at exact base `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`. Review must verify: exact E2 identities (E2b fe2ed4e9bd9043b19b96a5f179390db629b01ccb, E2c 1a08d6e148a1e8c430da39c3d575eda3f8ea5929, E2d 80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761 with manifest f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740, actor 93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208, trace e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056, evaluator seed 0), replication as fleet_draw keyed by fleet_seed with N=4 and padded-slot semantics, placement/admission/scaling separation and actor/queue/rejected-work guarantees, P2C feasibility-first with sorted ascending unique feasible RSU IDs and SplitMix64 over exactly (evaluator_seed, fleet_seed, outer_tick, task_slot, sequential_task_ordinal) with first index h % n and second splitmix64(h) % (n-1) adjusted around first then sorted pair as deterministic pseudo-random modulo mapper with no hidden global RNG and negligible bias not mathematically exact-uniform (H1 pair-only inspection not statistical uniformity proof) and stale immutable-delayed-view rules with requested/actual age and observation/control times, compute-service fixed_1x/static_overprovisioned/dynamic 1--3 bounds with exact thresholds 800/200 (gap 600 is hysteresis, no extra hysteresis_ms), cooldown 5000, two-second delay, one-level, one-pending, apply-due-before-decision, stable inclusive edges, signal units, and reactive service_workload_ms/proactive arrival_work_ms transparency/no-future-leakage constraints, exact compute-service semantics (invariant raw work_ms backlog, raw enqueue without dividing by capacity, drain min(backlog, u*1000) for all queued work, tick-start scaling before placement/admission/latency/drain with u for entire tick and at most one resource_unit_seconds per RSU/tick even when idle, invariant raw backlog/admission/stale/reactive signals with capacity-not-queue drain and no normalized units, admission-time latency (raw_work_ahead+raw_own)/u with no retroactive repricing and null physical lifecycle, reduction to E2d at fixed_1x and initial capacities 1/3/1..3), stale-state semantics exact with 3000 ms control-clock offset prepopulating 0/1000/2000 with empty initial state and trace tick 0 maps to 3000 ms as declared simulator initial condition not observed Manchester traffic and queue safety current and fresh cells reusable, integer-ms time model with 5 within-tick slots and stale levels 0/1000/3000 and control-clock offset 3000 ms, cost as resource_unit_seconds never monetary, required task accounting with null unavailable lifecycle and headline/diagnostic hierarchy, staged candidate grid E3a 12 cells / E3b 16 stage-listed but 4 overlap reused so 12 unique additional / E3c 48 observations reusing 16 fresh leaving 32 stale variants with 60 stage-listed entries but 56 unique planned executions (12+12+32) and equations 12+16+32=60 and 12+12+32=56 and 48-16=32 and mandatory benchmark-driven reduction and E3c construct-gate dependency, paired fleet-draw inference with 95% Student-t intervals and includes-zero flags, and fail-closed validator/tests that reject queue==compute/task replication/actor-chooses-RSU/free-unbounded scaling/unavailable-zero/monetary cost/hidden fleet_seed/200 ms pseudo-time/missing resource denominator/actual Kubernetes/future leakage/common-target P2C/compute-service drifts (dividing enqueued work, new-only drain, 1x-only drain, idle-free resource time, queue/capacity conflation, normalized signals, retroactive latency, wrong initial capacities, physical-completion) and staged 60-as-unique/overlap-rerun/fresh-rerun/48-32-56 miscount and stale deadline view silently fresh/stale queue cap/mutation of true state/pretrace warmup/clock clamp/state-age laundering/offset added to delay and P2C replacement/unsorted/alternate hash-key-mapper/uniform-unbiased claims via copy-mutation without editing the canonical file and that enforce Markdown byte-equivalence via render_markdown.

E2, E2b, E2c, and E2d remain frozen history and are not rewritten; the E2d independent post-run evidence review of its final head (manifest/validation/comparison/mechanism summary/evidence index/report/supervisor summary binding the exact TrafficTwin head, unchanged vec_env head, frozen manifest SHA, raw root ledger, reused E2c hashes, statistical formulas, and claim boundaries) remains a retained prerequisite but does not block the bounded E3 contract review.

### Exit condition

E3 contract v1 exits this gate only after independent review returns `APPROVE` for the exact contract Markdown/JSON pair, validator, and tests at the exact base commit, with all checks passing. `APPROVE` authorises only the bounded E3 preparation sequence (unit/construct tests, tiny smoke, representative benchmark, runtime/storage projection, reduced machine plan, and immutable manifest) — it does not authorise any E3 trace execution itself, which requires a separate manifest `APPROVE`. Neither post-run approval of E2d nor contract `APPROVE` of E3 authorises another experiment outside the declared staged grid, and any post-observation source change requires a successor contract.

## What follows after this gate

If E3 contract v1 is approved, the next authorised work is the E3 preparation sequence under the approved contract: unit/construct tests, tiny smoke per new arm, representative benchmark per arm type with runtime/storage projection and budget reduction if needed, reduced machine plan with exact cell list and order, and an immutable manifest bound to exact TrafficTwin/vec_env/tos-data commits and hashes. Only after that manifest receives its own `APPROVE` may bounded fresh E3a/E3b/E3c cells execute. E2d remains frozen; no additional E2d/E2c replay or E1 cell follows automatically, and any new backhaul, ordinary-traffic, learning, fleet, or replication study beyond E3 requires a separate direct researcher instruction, predeclaration, and review.

## Explicitly not next

Do not start:

- any additional E2d replay, smoke, full cell, fleet seed or evaluator seed;
- any full `ingress_dla` or `dla` rerun, or any `off`/`jsq` run;
- any fleet seed outside 1–4 or any seed-0 E2d run, or any task-as-N inference;
- any E3 trace execution, smoke, benchmark, or full cell before E3 contract v1 `APPROVE`;
- any E3 cell outside the staged candidate grid (E3a/E3b/E3c as declared, maximum 56 unique cells (60 stage-listed), reduced plan before execution);
- any nonzero-backhaul run or queue-as-compute claim;
- any free/unbounded/fractional scaling outside 1--3 or without thresholds/hysteresis/cooldown/two-second delay/one-level actions;
- MAPPO or other actor retraining, or any actor that observes RSU load or selects execution RSU;
- a learned infrastructure dispatcher or ML-based proactive predictor;
- action masking, an RSU-load-augmented actor, or actual Kubernetes orchestration;
- proactive prediction with future leakage or non-four/ non-one-second window or undisclosed warm-up/formula;
- any P2C variant that samples with replacement, uses a global RNG without the stable counter key, inspects beyond the pair, or collapses to a common target;
- any stale view with 200 ms pseudo-time, non-integer state_age_ms, or within-tick slots advancing physical time;
- any monetary-cost claim or 0-coerced unavailable lifecycle field or missing resource_unit_seconds denominator;
- bus modelling as a replacement for the VEC thread;
- any G4, other-GPU, TPU or cross-backend E1 campaign cell;
- any additional E1 cell or semantic/cap variant;
- any successor contract or post-observation source change without a new versioned contract.

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
