# Existing Strategy Assessment — v08 Requirements Closure (Lane 05)

**Campaign:** `v08-requirements-closure` — Lane `05` — Worker `muse-05`
**Feature:** Existing strategy assessment
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` (exact prepared base, peeled v0.8 target)
**Branch:** `agent/v08-closure-lane05-existing-strategies-v1`
**Date:** 2026-08-12

## 1. Source authority and hash verification

This assessment is bound to exact sources whose SHA-256 and identities are embedded in the committed artifacts (`strategy_matrix.json` authority, `strategy_evidence_map.json` allowed set/heads, and `scripts/validate_v08_strategy_assessment.py` `EXPECTED_*` constants) and cross-checked by the self-contained validator without requiring the ignored `.harness/context/source_map.json` at runtime. The ignored `.harness/context/source_map.json` was used only as a staging convenience before drafting and is not a runtime dependency for the committed package — the package is self-contained.

| Source | Staged path | SHA-256 | Standing |
|---|---|---|---|
| FINAL_AUDIT | `.harness/context/sources/FINAL_AUDIT__FINAL_TRAFFICTWIN_V08_AUDIT.md` | `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9` | FINAL_NEGOTIATED_REQUIREMENTS_AUDIT |
| NEGOTIATED_V1_WHOLE_FILE | `.harness/context/sources/NEGOTIATED_V1_WHOLE_FILE__canonical_baseline_v1.md` | `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` | FROZEN_REQUIREMENTS_BASELINE_CONTAINER |
| NEGOTIATED_V1 canonical payload | (within above, delimited `BEGIN/END CANONICAL PAYLOAD`) | `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` | Frozen payload |
| AUDIT_SOURCE_INDEX | `.harness/context/sources/AUDIT_SOURCE_INDEX__source_index.md` | `7ce9b43250d8b72e3c1aa9e0bbbc369b251bf7b7aedcae39ea8ed8cdda860d24` | AUDIT_SOURCE_INDEX |
| S-001 Project brief | `.harness/context/sources/S-001__Project.pdf` | `d2940e257e455de3f6694d59d66c4d3661471c732618700ad34b4d65240597b0` | PRIMARY_PROJECT_BRIEF (only substantive scope) |
| S-003 Rubric | `.harness/context/sources/S-003__MSc_Report_and_Video_Rubric.pdf` | `c88175e344c8aa0cfd5eba6164a8b5941670c7cc5bb69e89213c6c019bcd8c0f` | ASSESSMENT_RUBRIC |
| S-004 Handbook | `.harness/context/sources/S-004__SoE PGT Handbook - Appendices (MSc Advanced Computer Science).pdf` | `df504ec76271f2cb4b2fa34be1f53f55d1363e65d4352456f856a92178d3da82` | ASSESSMENT_PROCESS_SOURCE |
| S-007 Randy Q&A | `.harness/context/sources/S-007__MSc Students QnA.docx` | `e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4` | DIRECT_RANDY_QA |
| RESEARCH_AUDIT semantic contract | `.harness/context/sources/RESEARCH_AUDIT_SEMANTIC_CONTRACT__TrafficTwin_research_audit_2026-08-07.md` | `c7e01197160cb43db5f35bf804e6aa2beae6272a5915a1581369bdf0ec284645` | ORIGINAL_RESEARCH_AUDIT_AND_SEMANTIC_CONTRACT |
| PRODUCT_DESIGN_V2 | `.harness/context/sources/PRODUCT_DESIGN_V2__TrafficTwin_Product_Design_Document_V2.docx` | `f45a9449bab70dde579a35ffe4f8e00eeca25d02ee2f6b68b16583816d524045` | CLASS_D_PRODUCT_DESIGN_PROPOSAL (not Sandra approval) |
| S-035 / SANDRA-DIRECT-BODY-2026-08-04 | `.harness/context/sources/S-035__sandra-direct-email.md` | `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed` | DIRECT_SUPERVISOR_SOURCE_BODY |

**Key hash checks performed inline before edits and embedded for self-contained validation:**
- `sha256sum .harness/context/sources/*` matched every expected SHA above at staging time; the same SHAs are now embedded in `strategy_matrix.json` authority, `strategy_evidence_map.json` `allowed_sha256_set`/`heads`, and the validator `EXPECTED_*` constants for self-contained cross-check without requiring the ignored `.harness` directory at runtime (the ignored `.harness/context/source_map.json` is not a runtime dependency).
- Canonical payload SHA recomputed via delimiter convention `join(lines[BEGIN+1:END]) + "\n"` yields `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` — embedded in matrix authority and validator.
- `git rev-parse HEAD` = `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`; branch `agent/v08-closure-lane05-existing-strategies-v1`; `git status --porcelain` clean.
- Research heads `refs/harness/read-only/e2b` = `fe2ed4e9bd9043b19b96a5f179390db629b01ccb`, `e2c` = `1a08d6e148a1e8c430da39c3d575eda3f8ea5929`, `e2d` = `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761` — read-only, never launched; embedded in validator `EXPECTED_HEADS` and evidence_map `heads` for self-contained verification.

**Non-authoritative boundary:** `TrafficTwin_Product_Design_Document_V2.docx` is Class D and cannot amend Negotiated Version 1. S-011/S-012 and any missing 4 August Outlook headers remain Class C/provisional; the only 4 August body content that is authoritative is exactly the bytes of S-035. Repository route counts, page rendering, and V4 integration receipt `12ae986620a96794c807246376aceb14bcd7d1424bfa24dc82f3c010d90748de` do not create negotiated requirements.

## 2. S-035 direct supervisor body — controlled interpretation

**Exact staged path:** `.harness/context/sources/S-035__sandra-direct-email.md`
**SHA-256:** `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`
**Standing:** `DIRECT_SUPERVISOR_SOURCE_BODY` — verbatim body supplied directly by Abdulla; does not establish timestamp, message-id, transport headers, or Outlook provenance.

This body supports five points as **supervisor-identified problem / requested investigation / proposed direction / hypothesised outcome** — not as a mandatory implemented deliverable without additional authoritative evidence:

1. **RSU queue / waiting-room capacity, not compute power** — `2.5 → 0.75` was `RSU queue capacity (waiting room)` — an administrative ceiling on queued tasks, not computation power. [S-035 body, para 2]. honesty: SOURCE-DERIVED FACT. Must never be described as compute scaling.

2. **Fail-fast / rejection-accounting explanation** — reduced latency with unchanged attainment is *most likely caused by quick rejection due to lack of capacity* — the fail-fast situation; the improvement is *only an accounting effect* rather than genuine. [S-035 body, para 3]. honesty: SOURCE-DERIVED FACT (supervisor hypothesis), treated as the working causal interpretation for the pilot sweep, not as a measured hardware effect.

3. **No explicit current RSU load/capacity awareness in trained vehicle policy** — capacity awareness is a necessity that MAPPO fails to consider; RSUs do not broadcast capacity because it becomes quickly obsolete (microseconds concurrency). [S-035 body, para 4]. honesty: SOURCE-DERIVED FACT.

4. **Disproportionate congested-road load, idle farther RSUs** — the trained model has learned strongest-link as a strong reasoning; bottleneck occurs only at congested-road RSUs while farther RSUs remain idle. [S-035 body, para 5]. honesty: SOURCE-DERIVED FACT.

5. **Infrastructure load management as supervisor-identified problem** — *This represents a problem that you could solve… improvement of task completion rates* [S-035 body, para 6]. honesty: SOURCE-DERIVED FACT for problem statement.

**Requested investigations (A/B/C) — classification:**

| Request | Wording in S-035 | Classification |
|---|---|---|
| (A) DRL offloading + deterministic load balancing (Kubernetes framework, retraining not required) | `To model Kubernetes load balancing … deterministic approach … retraining is not required … agent chooses best link … RSU will forward` | **Supervisor-identified problem + requested investigation + proposed direction + hypothesised outcome (improved completion in free-flow and congested)**. Not a mandatory assessed implementation without further authoritative evidence. honesty: SOURCE-DERIVED FACT for request; INFERENCE if called mandatory. |
| (B) DRL offloading + DRL-based scheduling/load balancing | `To train a load balancing model based on existing DRL algorithm. DRL-based task offloading + DRL-based Scheduling/Load Balancing` | **Requested investigation / proposed direction**. Not mandatory implementation. honesty: SOURCE-DERIVED FACT for proposal. |
| (C) DRL offloading + AI-based infrastructure/resource control | `To design an AI-based Kubernetes. DRL-based task offloading + AI-based Kubernetes load balancing` | **Requested investigation / proposed direction**. Not mandatory implementation. honesty: SOURCE-DERIVED FACT for proposal. |

**TT-REQ-008 consequence (campaign overlay INFERENCE, not baseline amendment):** S-035 raises direct source confidence for infrastructure-aware load management and supports an **INFERENCE** that comparative load-management evidence could be considered **PARTIALLY_MET** as a **campaign overlay**. This PARTIALLY_MET standing is **INFERENCE + EXTERNAL DECISION REQUIRED** — it **does not change SHOULD priority** of the frozen Negotiated Version 1 and does **not** amend the frozen baseline (payload `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` remains unchanged) and does not establish a mandatory implemented deliverable. The frozen baseline priority/status remain distinct from this campaign inference; any overlay standing is not an effective baseline amendment. honesty: SOURCE-DERIVED FACT for supervisor-identified problem/investigations + INFERENCE for overlay status; EXTERNAL DECISION REQUIRED to adopt.

**Issue-body supersession (narrow, overlapping content only):** The direct Sandra body S-035 (SHA `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`, `DIRECT_SUPERVISOR_SOURCE_BODY`) supersedes the weaker SRC-010 paraphrase **only for verbatim body content that overlaps** between the two. Where SRC-010 summarizes content present in S-035, S-035 controls; SRC-010 content that does not overlap S-035's verbatim body is **not** superseded. S-035 establishes a supervisor-identified problem and requested investigations (A/B/C) as proposed directions/hypothesised outcomes, not a mandatory implemented deliverable or automatic frozen-baseline status amendment. All other audit limitations, timestamp/headers/provenance gaps, and unresolved decisions remain.

## 3. Strategy definitions — required product/content behavior

Five strategies are assessed. For each, the matrix records: exact definition, information, authority, admission, placement, sequential/common-target behavior, forwarding, determinism, benefit, failure mode, cost, exact experiment evidence, and limits. The machine-readable matrix is `strategy_matrix.json`; the evidence bindings are `strategy_evidence_map.json`. Every empirical number below is artifact/SHA-bound per acceptance criteria.

### 3.1 Strongest-link / LB-off — baseline, no infrastructure rebalancing

**Strategy ID:** `strongest_link_off`

| Field | Value | Honesty |
|---|---|---|
| **Definition** | Vehicle V2I choice is strongest radio link (`best_rsu_idx` from `compute_per_vehicle_links`). Infrastructure placement is identity: `selected_execution = ingress = best_rsu_idx` when admitted; execution = ingress. LB = off. | IMPLEMENTATION-VERIFIED FACT |
| **Information** | Per-vehicle link quality only. Does not use `rsu_busy_ms`, queue length, or remaining work. Frozen 17-dim MAPPO actor does not observe current RSU load. | SOURCE-DERIVED FACT (S-035, RESEARCH_AUDIT) + IMPLEMENTATION-VERIFIED FACT |
| **Authority** | Placement authority degenerate (identity). Admission authority separate: cap + local/V2V MQD + V2I unavailable still apply. | IMPLEMENTATION-VERIFIED FACT |
| **Admission** | Cap `2.5x → 6220 tasks/RSU` (`--rsu-cap-per-veh 2.5`, `--rsu-cap-mode reject`, `--substep-queue sequential --iters 3`). Cap is waiting-room ceiling, not compute power. No deadline gate. Rejected = code 4 (cap), retained selected ingress, `actual_execution = -1`, not enqueued. | SOURCE-DERIVED FACT (S-035) + IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT (counts) |
| **Placement** | `selected_execution_rsu = task_ingress_rsu`. No JSQ. | IMPLEMENTATION-VERIFIED FACT |
| **Sequential** | Model-C substeps ascending; within substep padded slots ascending; scatters only admitted V2I; three reconciliation iterations. | IMPLEMENTATION-VERIFIED FACT |
| **Common-target** | N/A — no common target. All admitted work on ingress-to-execution diagonal. Must not be called batch common-target. | PROVISIONAL WORDING clarification |
| **Forwarding** | Never: `forwarded_admitted=0`, share `0.0`, latency `0.0`, matrix diagonal. | RESEARCH-EVIDENCE FACT + IMPLEMENTATION-VERIFIED FACT |
| **Determinism** | Fully deterministic given trace/actor/seed/fleet/backlog. No new PRNG split. Vehicle actions byte-identical. | IMPLEMENTATION-VERIFIED FACT |
| **Benefit** | Baseline and isolation: accounting reference for conservation; offered attainment `0.683619229` seed0 (E2 off) and `0.766522526` admitted. Not claimed optimal. | RESEARCH-EVIDENCE FACT |
| **Failure mode** | Congested-road RSUs saturate while farther idle (S-035). No staleness tested. | SOURCE-DERIVED FACT + INFERENCE for generalisation |
| **Cost** | Fixed 1x service, zero backhaul (ideal fibre), cap rejections 834120 (seed0 off), `V2I unavailable 138`, `local MQD 34124`, `V2V MQD 545879`. | RESEARCH-EVIDENCE FACT |
| **Experiment evidence** | `e0_full_reference_manifest 71b?` — manifest `eae09f31bd049b70f99930507873b0efb84a7a7cbeab2a036a20ce9fd28229ed02a8` validation `3970b89e371a05cae6f5baa8142c98587b302d0c5a467601d50aa021e1368bfa`; E2 pilot manifest `53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8` comparison `67d626ca4e6b60afb6beb5c9d4c8cc2bf7b15c72922eba633194848439fe3d52` validation `30f6d117402e91decf8581b2b42030c0f9795881dd5eaef1a380bbf6408f0d38` path summary `54721d9a4b403e36e99123394193db06d7b6c596e66121975001a8d02196287e` evidence index `8c04c833f6b04140bac0f2dfcba788c50d29cc4be1dadf39cfacf5d8e366bba9` raw checksums `f33e974b3dbbfc0865a0b4d986c8bbfaf504424e4187aa5ba809e610384390d3` head `fe2ed4e9bd9043b19b96a5f179390db629b01ccb` vec_env `e11f4445a9cc939a79d4f419c6f48b43ce110664` tos-data `a75bbdb1a956f828ee0e9b97b33506bd32d31b85` trace `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056` actor `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` offered 13076234 admitted 11661973 share 0.0 range 0.098660108 | RESEARCH-EVIDENCE FACT |
| **Limits** | One Manchester incident hour 2024-03-15 20:00-21:00 (3600 steps), one actor/trace/cap/service/backhaul/evaluator seed (0), provisional uk2030 fleet, evaluator deadline not physical return, no staleness/learning. | EXTERNAL DECISION REQUIRED for breadth |

### 3.2 Evidenced JSQ without deadline gate — placement-only least-busy

**Strategy ID:** `jsq_without_gate`

| Field | Value | Honesty |
|---|---|---|
| **Definition** | Deterministic least-busy execution placement: selected target = `argmin(rsu_busy_ms)` over 10 RSUs; no deadline-aware gate. Placement-only JSQ. | IMPLEMENTATION-VERIFIED FACT |
| **Information** | `rsu_busy_ms` = total remaining RSU compute (ms, drained ≤1000 ms/s, remainder carried). Not queue length, not predicted earliest completion. Frozen actor not choosing execution RSUs. | IMPLEMENTATION-VERIFIED FACT |
| **Authority** | Infrastructure placement chooses execution RSU after V2I action. Admission unchanged. | IMPLEMENTATION-VERIFIED FACT |
| **Admission** | Same 2.5x/6220 cap; gate none (code 3 =0). Seed0 jsq cap 355207 vs off 834120 (spreading reduces cap pressure). | RESEARCH-EVIDENCE FACT |
| **Placement** | Per substep `jnp.argmin(rsu_busy_ms)` over all RSUs; reachability/ingress/cap do not filter; tie lowest index. Least-busy workload, not canonical queue-length JSQ. | IMPLEMENTATION-VERIFIED FACT |
| **Sequential** | Sequential: argmin from live backlog at substep entry; service added immediately affects later substeps. | IMPLEMENTATION-VERIFIED FACT |
| **Common-target** | Evidenced JSQ in E2 is common-target per substep: one argmin per substep broadcast to its padded slots. Batch common-target, not canonical per-task JSQ. Must not be called canonical general JSQ. | IMPLEMENTATION-VERIFIED FACT + PROVISIONAL WORDING |
| **Forwarding** | When selected ≠ ingress and admitted: seed0 forwarded 2067204 / 2297044 share 0.899940968, latent cost 0 ms (zero backhaul). Range `off 0.09866 → jsq 0.000458` (more balanced). Deterministic forwarding. | RESEARCH-EVIDENCE FACT |
| **Determinism** | Deterministic; no new PRNG; actions byte-identical to off. | IMPLEMENTATION-VERIFIED FACT |
| **Benefit** | Seed0 jsq admitted +478913 vs off (V2I), offered latency -1338.918 ms, range -0.0982 (balanced). | RESEARCH-EVIDENCE FACT |
| **Failure mode** | Seed0 offered -0.007937454, admitted -0.03878544, admitted latency +4839.858 ms vs off. Balancing did not improve deadlines. Zero-backhaul/stale-free idealisation. | RESEARCH-EVIDENCE FACT |
| **Cost** | Fixed 1x; backhaul zero deferred; admitted queuing higher (admitted latency up) while offered falls via fewer penalties; energy 0.468242424 J (Δ -0.00004). | RESEARCH-EVIDENCE FACT |
| **Experiment evidence** | Same E2 pilot manifests as above (manifest `53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8`, comparison `67d626ca4e6b60afb6beb5c9d4c8cc2bf7b15c72922eba633194848439fe3d52`, validation `30f6d117402e91decf8581b2b42030c0f9795881dd5eaef1a380bbf6408f0d38` etc.), head `fe2ed4e9bd9043b19b96a5f179390db629b01ccb`, offered 0.675681775, admitted 0.727737086, admitted 12140886, V2I 2297044, forwarded 2067204 share 0.89994 range 0.000458, contrast `jsq-off = -0.007937454`, head `fe2ed...`, vec_env `e11f444...` | RESEARCH-EVIDENCE FACT, one draw, no population inference, `canonical_jsq_claim_allowed=false` |
| **Limits** | One seed/fleet/trace/cap/backhaul/service/actor; evaluator deadline not physical return; no P2C/scaling/learning. | EXTERNAL DECISION REQUIRED |
| **Comparison compatibility** | `jsq - off` isolates placement without gate; `dla - jsq` isolates admission under JSQ; `dla - off` is joint. Forgetting common-target caveat contaminates JSQ claims. | INFERENCE boundary |

### 3.3 Ingress DLA — strongest-link execution + DLA admission (admission-only)

**Strategy ID:** `ingress_dla`

| Field | Value | Honesty |
|---|---|---|
| **Definition** | E2b new mode: ingress = strongest-link; selected = ingress; admission = exact DLA `seq_offsets` gate + 3-it fixed point at ingress live backlog. Code 3 gate rejection. | IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT |
| **Information** | Gate uses live backlog + service vs remaining deadline, recomputed per substep. No new telemetry beyond DLA backlog; frozen actor unchanged. | IMPLEMENTATION-VERIFIED FACT |
| **Authority** | Placement degenerate (ingress). Admission is DLA infrastructure gate. Admission-only contrast to DLA. | IMPLEMENTATION-VERIFIED FACT |
| **Admission** | Cap 6220 same; gate rejected 2373522 seed0 (replaces ~834k caps); cap 0 at seed0 under ingress_dla. Caveat: `ingress_dla - off` retains step-entry vs live-backlog timing difference (138 unavailable in off, ~1e-5 per offered); not perfectly gate-only. | IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT + INFERENCE caveat |
| **Placement** | `selected = best_rsu_idx` for every V2I attempt. No argmin. | IMPLEMENTATION-VERIFIED FACT |
| **Sequential** | Live per-substep gate with three iterations. | IMPLEMENTATION-VERIFIED FACT |
| **Common-target** | N/A — each task gated at its own ingress, not shared JSQ target. Matrix diagonal, zero forwards. | PROVISIONAL WORDING |
| **Forwarding** | Never: 0 forwards, 0 ms. | RESEARCH-EVIDENCE FACT |
| **Determinism** | Deterministic, no new PRNG. | IMPLEMENTATION-VERIFIED FACT |
| **Benefit** | Admission benefit under strongest-link: seed0 ingress_dla 0.715773211 vs off 0.683619229 (+0.032153983) admitted 0.897826701; E2c seeds1-4 ingress_dla 0.720032771, 0.703688004, 0.702976484, 0.708874512 consistently above paired dla. Fewer admitted (-1134224 seed0 vs off) but higher conditional success; latency down. | RESEARCH-EVIDENCE FACT (1+4 draws, not independent replicates) |
| **Failure mode** | Conservative backlog-only gate may reject some tasks that could have drained in time; ~2.37M rejections seed0. Trace/cap/service dependent. | INFERENCE limited to tested condition |
| **Cost** | Fixed 1x, no backhaul, fewer admitted throughput, energy ~0.468 J. | RESEARCH-EVIDENCE FACT |
| **Experiment evidence** | E2b manifest `9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91` head `fe2ed4e9bd9043b19b96a5f179390db629b01ccb` report `e2b_placement_admission_factorial_report_2026-08-10.md` raw `a0198c9f38295db8ee0aa34b2b4c786ebcb5c034450cb59b616f4a11076ea5c6`; E2c multidraw manifest `fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a` comparison `b0bc17ef097e8a8ca3639482bbf5ae05ef249c1221836cc6591207e87b511970` validation `25b80d66d991b424e20a7fd18d9e45c641cddc4b4aa9ffeed0cbdccacb5f8f2` raw `d3f41d2fc21257f16518f62ec2fbbde55243a89d31726c57f1a0171fe7f582d4` heads `e2b fe2ed...` / `e2c 1a08d6e148a1e8c430da39c3d575eda3f8ea5929` vec_env `0e5ed2f79b50011fe0475a5c2069978f9fdd778d` observed 0.715773211 admitted 0.897826701 offered 13076234 admitted 10424749 V2I 580907 gate 2373522 contrast +0.03215 vs off, E2c 1-4 as above. | RESEARCH-EVIDENCE FACT |
| **Limits** | Descriptive (1+4 draws); same trace/cap/service/backhaul/actor limits; backlog-only gate; not equivalence. | EXTERNAL DECISION REQUIRED |
| **Comparison compatibility** | `ingress_dla - off` isolates admission under strongest-link (mod timing caveat); `dla - ingress_dla` isolates placement with gate fixed — cleanest comparison (E2c). Joint contrasts not isolation. No equivalence. | IMPLEMENTATION-VERIFIED FACT |

### 3.4 Common-target DLA — JSQ (common-target per substep) + DLA gate

**Strategy ID:** `common_target_dla`

| Field | Value | Honesty |
|---|---|---|
| **Definition** | DLA = JSQ placement (common-target per substep argmin) + same deadline-aware gate. One common `argmin(rsu_busy_ms)` per substep broadcast to eligible V2I in that substep; gate at that selected target. Batch common-target behavior, not canonical per-task JSQ+DLA. | IMPLEMENTATION-VERIFIED FACT |
| **Information** | Placement: current `rsu_busy_ms` argmin over 10 RSUs (least remaining work). Admission: backlog-vs-deadline at common target, live per substep. Reachability/ingress/cap do not filter argmin. | IMPLEMENTATION-VERIFIED FACT |
| **Authority** | Placement chooses common execution RSU; admission gate at that RSU. Joint mode; isolate via contrasts. | IMPLEMENTATION-VERIFIED FACT |
| **Admission** | Gate strict backlog-only, `code 3`; at seed0 2373522 gate rejections replacing 355207 caps vs jsq; at seed0 dla cap 0. At E2c seeds1-4 dla cap 0 likewise. | RESEARCH-EVIDENCE FACT |
| **Placement** | One `jnp.argmin` per Model-C task substep; reused for all V2I in substep; sequential inter-substep, batched intra-substep. | IMPLEMENTATION-VERIFIED FACT + PROVISIONAL WORDING |
| **Sequential** | Inter-substep sequential; intra-substep batched (shared target before admissions). | IMPLEMENTATION-VERIFIED FACT |
| **Common-target** | This strategy IS the common-target behavior. E2c limitation verbatim: common `argmin` per substep so substep traffic shares one selected target; observations must be read under this convention. Do not call canonical general JSQ. | SOURCE-DERIVED FACT from E2c limitation + IMPLEMENTATION-VERIFIED FACT |
| **Forwarding** | When selected ≠ ingress and gate-passed: seed0 forwarded 232729/278729 share 0.834965145; E2c seeds1-4 ~234k-241k share ~0.848-0.857; latency 0 ms (zero backhaul). Execution concentrated: seed0 counts `[66743,66899,66772,52223,26092,0,0,0,0,0]` leaving 5 RSUs zero; range +0.17094 vs ingress_dla (more concentrated). | RESEARCH-EVIDENCE FACT |
| **Determinism** | Deterministic per substep; no new PRNG; logits Δ 2.38e-7 within 1e-5 bound but actions identical. | IMPLEMENTATION-VERIFIED FACT |
| **Benefit** | Admission benefit under JSQ: dla vs jsq +0.019258144 offered (seed0), +0.169979 admitted, latency -15400 ms; but this is admission, not placement. | RESEARCH-EVIDENCE FACT |
| **Failure mode** | Placement deficit vs ingress_dla: seed0 -0.020833292; E2c replication -0.022097035, -0.020519134, -0.021447383, -0.020825491 mean -0.021222261 95% CI [-0.022335, -0.020109] all negative. Associated with concentrated execution and heavy gate rejections at common target; not causal beyond simulator. | RESEARCH-EVIDENCE FACT (bounded 4-draw, not population) |
| **Cost** | Fixed 1x; backhaul zero but high forward count concentrates work; admitted fewer than jsq/ingress_dla (~2M fewer than jsq seed0). | RESEARCH-EVIDENCE FACT |
| **Experiment evidence** | E2 pilot as above + E2b `9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91` + E2c multidraw `fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a` comparison `b0bc17ef097e8a8ca3639482bbf5ae05ef249c1221836cc6591207e87b511970` validation `25b80d66d991b424e20a7fd18d9e45c641cddc4b4aa9ffeed0cbdccacb5f8f2` raw `d3f41d2fc21257f16518f62ec2fbbde55243a89d31726c57f1a0171fe7f582d4` heads `fe2ed...` / `1a08d6...` vec_env `0e5ed2f...` observed 0.694939919 admitted 0.897716302 admitted 10122571 V2I 278729 share 0.834965 etc., contrasts as above. | RESEARCH-EVIDENCE FACT |
| **Limits** | Four new draws + pilot; one trace/cap/service/backhaul/actor; backlog total work not earliest completion; common-target batch limits claims to that construction; no scaling/P2C/learning. | EXTERNAL DECISION REQUIRED |
| **Comparison compatibility** | `dla - ingress_dla` isolates placement with gate fixed; `dla - jsq` isolates admission; `dla - off` joint not placement-only. Common-target caveat must remain attached. | IMPLEMENTATION-VERIFIED FACT |
| **Provisional wording** | Call exactly `JSQ execution placement + deadline-aware admission (common-target per substep)`; do not call pure placement. | PROVISIONAL WORDING |

### 3.5 per_task_dla — per-task recomputed least-busy + DLA gate

**Strategy ID:** `per_task_dla`

| Field | Value | Honesty |
|---|---|---|
| **Definition** | E2d construct-validity mode: recomputes `argmin(rsu_busy_ms)` after each candidate's admitted reservation, in ascending padded-slot order within each substep, before next candidate's placement+gate. Same strict backlog gate and 3-it fixed point; backhaul zero. | IMPLEMENTATION-VERIFIED FACT |
| **Information** | Live `rsu_busy_ms` after prior reservations (least-busy per-task); ingress still strongest-link for eligibility; gate identical. Helper SHA `a6e047265dd09365c0d4029afa76f8cb7caa444883e2f549a4254e3d0b53472a`. | IMPLEMENTATION-VERIFIED FACT |
| **Authority** | Placement per-task infrastructure; admission same gate per-task at selected target. Tests E2c common-target deficit. | IMPLEMENTATION-VERIFIED FACT |
| **Admission** | Same gate at per-task selected target; cap per selected target interacting with reservations. | IMPLEMENTATION-VERIFIED FACT |
| **Placement** | Per-task argmin in slot order; tie lowest index; domain all 10 RSUs; contrast common-target once-per-substep vs per-task. | IMPLEMENTATION-VERIFIED FACT |
| **Sequential** | Intra-substep sequential (slot k sees reservations <k); inter-substep sequential. Finest granularity tested; deterministic order ascending slot. | IMPLEMENTATION-VERIFIED FACT |
| **Common-target** | Replaces batch with per-task. Mechanism summary shows greater target dispersion (candidate counts, unique targets, target switches, max concentration) vs common-target. | RESEARCH-EVIDENCE FACT |
| **Forwarding** | When selected ≠ ingress and admitted: E2d seeds1-4 forwarded ~600885,600181,601402,600755 share ~0.899-0.900 of 667k V2I admitted, higher than dla ~234k, zero latency; matrix more off-diagonal. | RESEARCH-EVIDENCE FACT |
| **Determinism** | Deterministic per-task order/tie; no new PRNG; path arrays exact. | IMPLEMENTATION-VERIFIED FACT |
| **Benefit** | `per_task - ingress_dla` (+0.004636732564, +0.005867285642, +0.005071796666, +0.005509919752) mean +0.005271433656 SD 0.000533733895 SE 0.000266866947 95% CI [+0.004422143925, +0.006120723387] `directional_advantage_for_per_task_placement_within_bounded_draws`. Secondary vs common-target mean +0.026493694591 CI [+0.02621,+0.02677]. Bounded 4-draw directional, not universal. | RESEARCH-EVIDENCE FACT |
| **Failure mode** | Per-task O(KMAX*N) vs one per substep; forwarding ~2.5x vs common-target increases backhaul exposure; still ~5 RSUs near-zero execution, not fully balanced; staleness would affect per-task more (more decisions on stale state, not tested). | INFERENCE + IMPLEMENTATION-VERIFIED FACT |
| **Cost** | Fixed 1x; placement eval cost higher unmeasured; backhaul zero but 600k forwards amplify nonzero cost; admitted 10594205,10378506,10342346,10367858 (>ingress/dla). Energy ~similar. | RESEARCH-EVIDENCE FACT |
| **Experiment evidence** | Manifest `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740` head `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761` report `e2d_per_task_placement_report_2026-08-11.md` SHA `8583503f817e159e74e20a8d0b3d72b281280984a2bbfac84b8e31786af8308e` comparison `1655ae76d3c9a6aac77d66b53555a35d608394427f86f0f19828fa5fb148afd0` validation `0e3f27cdec9d13ec8e340bf1d83b3afcd127e90d7bdcf316bc2a2b2738fd313f` evidence index `408cf8bb86370970941690b5887648c5bfb86d84a0da6bb2361b7edd508d80a7` mechanism `4975ab8792242a56c241d6513e7e49bcdfa5117ab462bcb6b9bb3c5d2a5e5410` raw `eb5de7ce1eea202fee4d08d28bf7f4e38888b24709550cfc78dca71b16b250ca` reused E2c ingress/dla `fcaf2ee...` `b0bc17...` vec_env `2f63706f46319433a2ba3af1df97afd0e56a95d1` parent `0e5ed2f79b50011fe0475a5c2069978f9fdd778d` helper `a6e047...` offered per_task 0.724669504,0.709555289,0.708048281,0.714384432 vs ingress 0.720032771,0.703688004,0.702976484,0.708874512 vs dla 0.697935736,0.683168870,0.681529101,0.688049021 differences above, primary mean 0.005271 etc., forwarded as above, offered 13076234. | RESEARCH-EVIDENCE FACT 4-draw not replication of unknown prior (E2c known), not population, zero backhaul, no task-level significance. |
| **Limits** | 4 fleet seeds, evaluator 0, one hour/cap/service/backhaul/fleet/actor, backlog-only gate, evaluator dealine not physical return, no ordinary-traffic/deployment/scaling/P2C/learning, construct-validity only. | EXTERNAL DECISION REQUIRED |
| **Comparison compatibility** | Primary `per_task - ingress_dla` isolates per-task placement with gate fixed (strongest-link baseline); secondary `per_task - dla` per-task vs common-target. Prior E2c known so not held-out. | RESEARCH-EVIDENCE FACT |
| **Provisional wording** | Still least-busy workload `rsu_busy_ms`, not queue length. Name `per-task recomputed least-busy placement + DLA gate`. | PROVISIONAL WORDING |

## 4. Determinism, implementation-vs-research separation, and controller comparison notes

- **Progressive overload exposure:** Off, JSQ, ingress_dla, common-target DLA, per_task_dla are distinct maturity levels: the later modes expand detail. They must not be post-hoc ranked as a universal curve.
- **Corrected implementation exposure:** The admissible controls for S-035 deterministic load balancing existed in vec_env at `e11f4445a9cc939a79d4f419c6f48b43ce110664` (evaluator `f9ec488528c52ce7cd6f7bb8b3a6c9c96aef532e5783a538bcac9763508519fe`) and parent `0e5ed2f…` . Each strategy's implementation verifier, timing caveat, and telemetry boundary are itemised above.
- **Fail-fast point rehearsal:** S-035's fail-fast reasoning is the correct lens for latency comparisons: penalty-inclusive offered latency vs admitted latency separate; capped vs gate rejection counts and `V2I unavailable 138` are payload fields. The dramatic offered latency drop `dla 522 ms vs off 17262 ms` is admission filtering, not faster service.
- **Randy-predicted load-balancing family:** Investigation A maps cleanly to deterministic JSQ (off → jsq) and to ingress_dla vs common-target comparisons; family B/C (learned/AI infrastructure control) remain requested investigations only, with no evaluated artifact in this closure. Do not claim they are empirically assessed here.

## 5. Field matrix completeness and comparison compatibility summary

Complete matrix JSON `strategy_matrix.json` covers all five strategies across required fields: definition, information, authority, admission, placement, sequential, common-target behavior, forwarding, determinism, benefit, failure mode, cost, exact experiment evidence, and limits. Every empirical value there resolves in `strategy_evidence_map.json` to an exact manifest/comparison/validation SHA and read-only head (`fe2ed4e9bd9043b19b96a5f179390db629b01ccb`, `1a08d6e148a1e8c430da39c3d575eda3f8ea5929`, `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`).

**Compatibility rules enforced by validator and narrative:**

- `jsq - off` : placement only when gate absent in both.
- `ingress_dla - off` : admission under strongest-link (mod step-entry vs live caveat).
- `dla - jsq` : admission under JSQ.
- `dla - off` : joint placement+admission, not isolation.
- `dla - ingress_dla` : placement with gate fixed (cleanest, E2c).
- `per_task - ingress_dla` : per-task placement with gate fixed (E2d primary).
- `per_task - dla` : per-task vs common-target.

Close values never treated as equivalence. Every delta is reported with replication unit (fleet seed), SD/SE/CI, and claim boundary flags.

## 6. Evidence references resolve on exact read-only heads

All empirical values resolve on exact read-only heads listed in Section 1. No `v0.8`/`main`/V4/PR #43/raw research-output/untracked worktree is a source for numbers here; those paths are forbidden for evidence. Research refs were read only through detached `git show refs/harness/read-only/...` and exact SHAs above.

## 7. Prohibited claims — enforcement

- **Common-target ≠ canonical JSQ:** Common-target DLA is explicitly labelled as batch common-target; validator rejects any matrix entry that omits the `common_target_behavior` field or labels common-target as canonical. See Section 3.4.
- **DLA ≠ pure placement:** DLA entries must contain both `admission.gate` and `placement` and state that DLA changes feasibility/admission (gate) as well as placement. Matrix field `admission` is required; validator fails on deletion.
- **No number without artifact/SHA + commit:** Every numeric in matrix/evidence_map is bound to SHA in `allowed_sha256_set` and a head commit. Redirecting an evidence SHA to a spurious value fails validation.
- **No universal winner:** Sections 3.1-3.5 state bounded directional observations and forbid universal superiority. `claim_boundaries_global` sets all population/equivalence/physical-deployment flags to `false`.

## 8. Honesty boundaries and remaining external decisions

Every artifact section above bears an honesty class:

- **SOURCE-DERIVED FACT:** S-035 body points, S-001 scope, RESEARCH_AUDIT direct supervision.
- **IMPLEMENTATION-VERIFIED FACT:** vec_env evaluator `eval_sumo_stage1_mc.py` and `vec_jax.py` flags/modes at `e11f444…` / `0e5ed2…` / `2f6370…`, deterministic tie/ordering logic.
- **RESEARCH-EVIDENCE FACT:** artifact/SHA-bound offered/admitted attainment, latency, counts, shares, ranges, and contrasts (with exact SHAs and commit identities).
- **INFERENCE:** generalisation beyond tested hour/cap/backhaul, and any causal placement vs admission attribution without controlling the timing caveat.
- **PROVISIONAL WORDING:** `strongest-link`, `JSQ` as least-busy workload, `DLA` as backlog-only simulator gate, cap as provisional `uk2030`/2.5x, backhaul idealisation.
- **EXTERNAL DECISION REQUIRED:** whether S-035 (A) deterministic Kubernetes load balancing suffices for TT-REQ-008 or whether (B) learned and (C) AI infrastructure control must also be implemented/evaluated; confirmation of primary denominator (offered vs admitted); required trace set beyond incident hour; acceptance of zero-backhaul idealisation and provisional fleet/cap; need for stale-state sensitivity (0/100/500/1000 ms) and nonzero backhaul.

Until those decisions are recorded in a new authoritative artifact, this assessment does not silently promote any investigation into a mandatory implemented deliverable, and it does not claim equivalence, population generality, or physical result return.

## 9. Validation and reproducibility

Self-contained: validator embeds expected hashes/heads (EXPECTED_* constants) and cross-checks the committed JSON artifacts without requiring the ignored `.harness/context/source_map.json` at runtime. The ignored harness is optional consistency context only.

Focused gate (exact):

```sh
uv run --frozen pytest -q tests/unit/test_validate_v08_strategy_assessment.py && uv run --frozen python scripts/validate_v08_strategy_assessment.py
```

Static gates (as relevant to changed files):

```sh
uv run --frozen ruff format --check
uv run --frozen ruff check
uv run --frozen mypy scripts/validate_v08_strategy_assessment.py
git diff --check
```

Discriminating mutation per acceptance: delete one `admission` field and redirect one evidence `sha256`; validator must fail; restore and pass. See `strategy_matrix.json` field matrix and `strategy_evidence_map.json` `allowed_sha256_set` for binding.

## 10. Traceability to audit and baseline

- Alignment is **PARTIALLY ALIGNED** per `FINAL_TRAFFICTWIN_V08_AUDIT.md` overall verdict; this lane closes the **existing strategy assessment** obligation (field matrix + evidence map) without relabelling commitment as execution or inventing supervisor approval.
- Frozen Negotiated Version 1 payload (`58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`) remains unchanged; S-035 direct body supports supervisor-identified problem and requested investigations A/B/C as proposed directions/hypothesised outcomes for overlapping verbatim content only (S-035 supersedes SRC-010 paraphrase only where they overlap, not blanket), and leaves SHOULD priority and frozen baseline status intact. Any TT-REQ-008 `PARTIALLY_MET` consideration is a campaign-overlay **INFERENCE + EXTERNAL DECISION REQUIRED**, not an effective baseline amendment.
- V4 integration receipt `docs/quality/v4_final_integration.md` blob SHA `12ae986620a96794c807246376aceb14bcd7d1424bfa24dc82f3c010d90748de` remains the factual integration handoff; no tag movement or lane merge is claimed here.

*End of assessment. Machine-readable companions: `strategy_matrix.json` and `strategy_evidence_map.json` (same directory). Validator: `scripts/validate_v08_strategy_assessment.py`. Unit test: `tests/unit/test_validate_v08_strategy_assessment.py`.*
