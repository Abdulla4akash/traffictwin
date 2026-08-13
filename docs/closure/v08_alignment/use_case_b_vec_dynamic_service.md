# Use Case B — Deadline-Aware VEC Dynamic Service

> Lane 04 — Campaign `v08-requirements-closure` — Feature: ITS service case B
> Base SHA: `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` — Branch: `agent/v08-closure-lane04-vec-service-case-v1`

## 1. Purpose and requirement binding

This document defines the deadline-aware Vehicle Edge Computing (VEC) service from offered tasks through frozen actor mode choice, ingress, admission, deterministic target selection, forwarding, service work, return, deadline assessment, and comparison output.

**Source-derived fact:** TT-REQ-002 (MUST) requires a few differentiated ITS service use cases sufficient to exercise the resource-management methodology. This VEC service is one such case. **[SOURCE-DERIVED FACT]**

**Source-derived fact:** TT-REQ-008 (SHOULD, Open decision YES) requires, if the late RSU research direction is confirmed, comparison of the existing vehicle-side offloading arrangement with a deterministic infrastructure-side load-management approach and a separately defined learned infrastructure approach, identifying conditions in which each performs better. Canonical wording is in the frozen baseline payload. **[SOURCE-DERIVED FACT]**

**Provenance update — S-035 / SANDRA-DIRECT-BODY-2026-08-04:** The staged mirror `.harness/context/sources/S-035__sandra-direct-email.md` (SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`) is direct supervisor evidence superseding SRC-010 for overlapping body content only. It does not establish timestamp, message-id, transport headers, or Outlook provenance. The frozen Negotiated Version 1 text and hash remain unchanged. **[SOURCE-DERIVED FACT]**

With S-035, TT-REQ-008 status is **PARTIALLY_MET** (campaign overlay): direct source confidence is raised, but the SHOULD priority is unchanged and the direction is not silently amended into a mandatory assessed implementation. The three investigations below remain requested investigations / proposed directions / hypothesised outcomes as the body supports, not mandatory deliverables absent additional authoritative evidence. **[INFERENCE + EXTERNAL DECISION REQUIRED]**

## 2. Authority and source register

| Source ID | Standing | SHA-256 | Use in this document |
|---|---|---|---|
| `FINAL_AUDIT` — FINAL_TRAFFICTWIN_V08_AUDIT.md | FINAL_NEGOTIATED_REQUIREMENTS_AUDIT | `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9` | Audit verdict, TT-REQ-008 SHOULD status, open decision |
| `NEGOTIATED_V1_WHOLE_FILE` — canonical_baseline_v1.md | FROZEN_REQUIREMENTS_BASELINE_CONTAINER | `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` | TT-REQ-008 canonical wording, priority SHOULD |
| `NEGOTIATED_V1` canonical payload | FROZEN | `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` | Payload binding |
| `RESEARCH_AUDIT_SEMANTIC_CONTRACT` — TrafficTwin_research_audit_2026-08-07.md | ORIGINAL_RESEARCH_AUDIT_AND_SEMANTIC_CONTRACT | `c7e01197160cb43db5f35bf804e6aa2beae6272a5915a1581369bdf0ec284645` | Lifecycle, vocabulary, authority boundaries, metric contract |
| `AUDIT_SOURCE_INDEX` — source_index.md | AUDIT_SOURCE_INDEX | `7ce9b43250d8b72e3c1aa9e0bbbc369b251bf7b7aedcae39ea8ed8cdda860d24` | Source classification (S-011/S-012 Class C) |
| `S-001` — Project.pdf | PRIMARY_PROJECT_BRIEF | `d2940e257e455de3f6694d59d66c4d3661471c732618700ad34b4d65240597b0` | Only substantive product scope — does not prescribe this service |
| `S-007` — MSc Students QnA.docx | DIRECT_RANDY_QA | `e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4` | Admission ceiling = waiting-room, terminal rejection, no retry/forward |
| `S-035 / SANDRA-DIRECT-BODY-2026-08-04` — sandra-direct-email.md | DIRECT_SUPERVISOR_SOURCE_BODY | `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed` | RSU queue/waiting-room not compute; fail-fast; no RSU load awareness; investigations A/B/C |
| `PRODUCT_DESIGN_V2` — TrafficTwin_Product_Design_Document_V2.docx | CLASS_D_PRODUCT_DESIGN_PROPOSAL | `f45a9449bab70dde579a35ffe4f8e00eeca25d02ee2f6b68b16583816d524045` | Non-authoritative; cannot amend Negotiated Version 1 |
| `docs/quality/v4_final_integration.md` at `bd4570f` | V4 integration receipt | blob SHA-256 `12ae986620a96794c807246376aceb14bcd7d1424bfa24dc82f3c010d90748de` | Implementation evidence bound |
| Base commit | `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` | — | Exact released product tree |
| PR #44 merge | `0442905cb06022c050a87c6fc8052fb6a6e68577` → `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` | — | V4 integration |

Every claim below is labelled with one of: **SOURCE-DERIVED FACT**, **IMPLEMENTATION-VERIFIED FACT**, **RESEARCH-EVIDENCE FACT**, **INFERENCE**, **PROVISIONAL WORDING**, or **EXTERNAL DECISION REQUIRED**.

## 3. Approved vocabulary (S-007 and semantic contract bound)

The following terms are used with the exact meanings from S-007 and `TrafficTwin_research_audit_2026-08-07.md`. Any term not in this list and not marked below is unavailable.

| Term | Meaning | Evidence label |
|---|---|---|
| **vehicle mode** | Actor-level offloading decision: `Local`, `V2I`, or `V2V`. The frozen MAPPO actor outputs a mode, not an RSU identity. | **[SOURCE-DERIVED FACT — S-007 semantic; RESEARCH-EVIDENCE FACT — jaxmarl/env/vec_jax.py]** |
| **ingress RSU** | The RSU that first receives the task over the radio link selected by the environment from the actor's mode. Distinct from execution RSU. | **[RESEARCH-EVIDENCE FACT]** |
| **execution RSU** | The RSU where the task actually queues and receives compute service. May equal ingress RSU or a different RSU after forwarding. | **[RESEARCH-EVIDENCE FACT]** |
| **admission** | Check of offered task against the per-RSU waiting-room ceiling (`MAX_CONCURRENT` / `rsu-cap-per-veh` / `rsu-cap-abs`). Surplus tasks are terminally rejected without queue entry, retry, fallback, or re-forwarding. | **[SOURCE-DERIVED FACT — S-007]** |
| **placement** | Selection of execution RSU for admitted tasks among eligible RSUs. Deterministic policies include strongest-link / least-loaded (JSQ), P2C sampling, and deadline-aware (DLA) variants. Placement is infrastructure-side, not actor-side. | **[RESEARCH-EVIDENCE FACT]** |
| **scaling** | Adjustment of per-RSU compute service rate via fixed `1×`, static `3×`, or reactive **Kubernetes-style resource-scaling simulation**. This is a simulated multiplier, not a real Kubernetes deployment. | **[SOURCE-DERIVED FACT — S-035 queue ≠ compute; RESEARCH-EVIDENCE FACT]** |
| **forwarding** | Infrastructure transfer of an admitted task from ingress RSU to execution RSU with backhaul delay/cost. One-hop, full-mesh model in current code. | **[IMPLEMENTATION-VERIFIED FACT]** |
| **service work** | Actual compute processing at the execution RSU at the current service rate. | **[RESEARCH-EVIDENCE FACT]** |
| **return** | Delivery of the computed result toward the vehicle. | **[RESEARCH-EVIDENCE FACT]** |
| **deadline assessment** | Determination of `deadline_success` by comparing end-to-end latency (including forwarding, queuing, service, return) against the task's deadline. | **[RESEARCH-EVIDENCE FACT]** |

**Provisional wording:** `AI-based Kubernetes`, `AI-based infrastructure/resource control`, and `learned infrastructure dispatcher` are provisional labels for direction (C) until a concrete controller specification is approved. Do not treat them as implemented APIs. **[PROVISIONAL WORDING]**

**Unavailable:** No approved vocabulary defines a vehicle-observable RSU load/capacity channel in the frozen actor. The body states RSUs DO NOT broadcast capacity because it goes stale in microseconds. **[SOURCE-DERIVED FACT — S-035]**

### 3.1 Mandatory distinctions

The following are conceptually and metrically distinct. Equating any pair is a semantic error.

- **vehicle mode** ≠ **ingress RSU** ≠ **execution RSU**. The actor chooses mode; the environment/dispatcher resolves ingress and execution RSUs. **[SOURCE-DERIVED FACT]**.
- **admission** ≠ **placement** ≠ **scaling**. Admission is a waiting-room ceiling; placement is target selection; scaling is service-rate adjustment. **[SOURCE-DERIVED FACT — S-007 + S-035]**
- **forwarded** ≠ **compute_completed** ≠ **returned** ≠ **deadline_success**. Each is a separate lifecycle counter with its own denominator. Conflating compute completion with deadline success is prohibited. **[RESEARCH-EVIDENCE FACT]**
- **waiting-room capacity** ≠ **compute power**. The `2.5 → 0.75` intervention changed queue capacity, not computation power. Reduced latency under tighter queue is a **fail-fast / rejection-accounting** effect, not a genuine service improvement. **[SOURCE-DERIVED FACT — S-035 + S-007]**
- **simulated Kubernetes-style scaling** ≠ **Kubernetes deployment**. Do not call simulated scaling a Kubernetes deployment. **[RESEARCH-EVIDENCE FACT]**

## 4. Actor / dispatcher authority boundary

**Unambiguous boundary — SOURCE-DERIVED FACT + RESEARCH-EVIDENCE FACT:**

- **Vehicle actor (frozen MAPPO, 17D, seed-100 Paper-2A):** Chooses only `Local / V2I / V2V` per task. The actor does **not** choose an exact RSU. Exact V2I/V2V targets are **environment-selected** (strongest-link by default). The actor's observation does not include adequate current RSU load/capacity — `best_rsu_load_frac` is computed but omitted from the 17D observation. No explicit current RSU load/capacity awareness in the trained vehicle policy. **[SOURCE-DERIVED FACT — S-035; RESEARCH-EVIDENCE FACT]**
- **Infrastructure dispatcher / load manager:** Selects execution RSU (placement), handles forwarding, and controls scaling. Deterministic options: strongest-link (no forwarding baseline), JSQ / least-loaded, P2C, deadline-aware (DLA). The dispatcher operates **downstream** of the actor's mode choice and may forward from ingress RSU to a quieter execution RSU. DLA additionally imposes an admission feasibility rule — do not call every DLA comparison a pure placement effect. **[RESEARCH-EVIDENCE FACT]**
- **RSU admission gate:** Enforces the waiting-room ceiling under `substep-queue=sequential` and `rsu-cap-mode=reject` (physical semantics). Rejected tasks are accounted as `rejected` with a reason and do not enter any queue. **[SOURCE-DERIVED FACT — S-007]**

Do not credit MAPPO with exact RSU choice unless exact evidence proves it for a specific checkpoint/observation variant. The frozen baseline actor lacks such evidence. **[IMPLEMENTATION-VERIFIED FACT]**

## 5. Complete lifecycle (ordered)

The service defines the following total order. Every stage is explicit; no stage may be skipped or silently merged.

1. **offered tasks** — Tasks generated by vehicles from the fleet/trace workload. Count = `offered`. Conservation: `offered = admitted + rejected`. **[RESEARCH-EVIDENCE FACT]**
2. **frozen actor mode choice** — For each offered task, the frozen vehicle policy outputs `Local / V2I / V2V`. No RSU identity is output. **[RESEARCH-EVIDENCE FACT]**
3. **ingress** — For `V2I` / `V2V` tasks, the environment resolves the **ingress RSU** as the strongest-link RSU (best available link). `Local` tasks do not ingress. **[RESEARCH-EVIDENCE FACT]**
4. **admission** — Ingress RSU checks the waiting-room ceiling (`rsu-cap-per-veh` scaled by `maxN` or `rsu-cap-abs`). If at ceiling, the task is **rejected** with reason `waiting_room_full`; it is not queued, retried, or re-forwarded. Otherwise it is **admitted**. **[SOURCE-DERIVED FACT — S-007]**.
5. **deterministic target selection (placement)** — For admitted offloaded tasks, the infrastructure dispatcher selects the **execution RSU**. Baseline is `ingress RSU = execution RSU` (strongest-link, LB off, no forwarding). Load-aware alternatives: JSQ (least-loaded), P2C, deadline-aware, DLA-P2C. Selection is deterministic except P2C sampling. **[RESEARCH-EVIDENCE FACT]**
6. **forwarding** — If `execution RSU ≠ ingress RSU`, the task is forwarded with a fixed backhaul delay (nominal 2 ms) and optional forwarding energy/cost accounting. Current model: one-hop, full-mesh, no bandwidth contention. The forwarded counter increments. **[IMPLEMENTATION-VERIFIED FACT]**
7. **service work** — The task waits in the execution RSU queue and receives service at the current compute multiplier (`fixed 1×`, `static 3×`, or reactive Kubernetes-style scaling). Report mean multiplier, core-seconds, scale events, and time-at-multiplier. **[RESEARCH-EVIDENCE FACT]**
8. **return** — Computed result is returned toward the vehicle. Return is distinct from compute completion. **[RESEARCH-EVIDENCE FACT]**
9. **deadline assessment** — End-to-end latency = queuing + service + forwarding + return. If latency ≤ deadline → `deadline_success`; otherwise `deadline_miss`. Deadline success is not synonymous with physical completion/return; the distinction matters for late-return semantics. **[RESEARCH-EVIDENCE FACT]**
10. **comparison output** — Aggregated metrics over a common-information run: `completion_offered = deadline_success / offered` (headline), `completion_admitted = deadline_success / admitted` (conditional diagnostic only), per-class completion (T1/T2/T3), latency mean/p50/p95/p99 and deadline-met latency, rejection fraction/reasons, forwarding count/cost, load imbalance per RSU, energy per offered/admitted task, action shares, conservation, and resource denominator. **[RESEARCH-EVIDENCE FACT — semantic metric contract §7]**

**Lifecycle counters that must remain distinct:** `forwarded`, `compute_completed`, `returned`, `deadline_success` are four separate integers. Do not equate forwarded with compute_completed, nor compute_completed with returned, nor returned with deadline_success. **[RESEARCH-EVIDENCE FACT]**

## 6. Infrastructure load-management investigations (S-035 bound)

S-035 states the supervisor-identified problem and three requested investigations. Classification strictly follows the body wording.

**Supervisor-identified problem (SOURCE-DERIVED FACT — S-035):** The trained MAPPO offloading policy favours the best available link, so tasks concentrate at RSUs near congested roads; farther RSUs remain idle while congested RSUs queue/reject. No current RSU load/capacity awareness in the vehicle policy; stale broadcast concern means vehicle-side capacity awareness is non-trivial. Infrastructure load management is the identified remedy domain. **[SOURCE-DERIVED FACT]**

**Requested investigations / proposed directions / hypothesised outcomes (S-035 — classified as the body supports):**

| Label | Direction as worded | Classification | Nature |
|---|---|---|---|
| (A) | DRL offloading + deterministic load balancing (Kubernetes load balancing — deterministic framework) — RSU forwards tasks from overloaded to quieter RSUs; retraining not required; best-link offload then forward. | **Requested investigation**; **proposed direction**; hypothesised outcome = improved task completion rate in free-flow and congested situations. | Deterministic infrastructure placement. |
| (B) | DRL offloading + DRL-based scheduling / load balancing — train a load-balancing model with a DRL algorithm. | **Requested investigation**; **proposed direction**. | Learned infrastructure scheduling. |
| (C) | DRL offloading + AI-based Kubernetes / AI-based infrastructure/resource control. | **Requested investigation**; **proposed direction**. | AI-based resource control (scaling/provisioning). |

Do not call any direction a mandatory assessed implementation without additional authoritative evidence. Each is a supervisor-identified problem + requested investigation, not a MUST deliverable on S-035 alone. **[INFERENCE + EXTERNAL DECISION REQUIRED]**

**Plausible fail-fast explanation (SOURCE-DERIVED FACT — S-035):** Tightening per-vehicle edge queue capacity `2.5 → 0.75` caused RSUs to refuse tasks quickly (fail-fast / quick rejection), producing reduced mean latency without changing deadline attainment. This is an accounting effect, not an improved service outcome, and motivates the E1 waiting-room semantic sweep. **[SOURCE-DERIVED FACT]**

## 7. Deterministic vs learned vs AI-resource separation

- (A) deterministic placement operates at task-dispatch time with a rule (JSQ / P2C / DLA) and requires no actor retraining. **[RESEARCH-EVIDENCE FACT]**
- (B) learned scheduling replaces the rule with a trained policy; it is gated after deterministic baselines. **[INFERENCE]**
- (C) AI-based resource control adjusts compute multiplier (scaling) reactively/proactively; simulated until a real deployment exists. **[RESEARCH-EVIDENCE FACT + PROVISIONAL WORDING]**

Admission, placement, and scaling remain conceptually separate even when a controller combines them (e.g., DLA's admission rule). Report which component drives any observed difference. **[SOURCE-DERIVED FACT]**

## 8. Comparison output and metric contract

For every head-to-head comparison, the run manifest must bind code commit, trace/checksum, actor checksum, `vec_env` commit, SUMO version, fleet draw, task RNG, caps, LB mode, backhaul, scaling mode, evaluator seed, fleet seed, and output checksums. **[RESEARCH-EVIDENCE FACT — §7 audit table]**

Headline metric: `completion_offered = deadline_success / offered_tasks`. Secondary: conditional `completion_admitted`, rejection reasons, class completion, latency tails, forwarded count/energy, per-RSU imbalance, conservation proof (`offered = admitted + rejected`; work conserved under physical semantics), and resource denominator (`core-seconds` / mean multiplier). **[RESEARCH-EVIDENCE FACT]**

Do not report latency without rejection fraction; do not use `completion_admitted` as a headline service-quality claim. **[RESEARCH-EVIDENCE FACT]**

## 9. Provenance and limitations

- **IMPLEMENTATION-VERIFIED FACT:** Current `vec_env` (main at `0f01f4d` per audit) supports `rsu-cap-per-veh`, `rsu-cap-abs`, `substep-queue sequential|snapshot`, `veh-queue conserved|legacy`, `rsu-cap-mode reject|clamp`, LB modes `off/jsq/p2c/dla/dla_p2c`, backhaul delay, and `compute modes off/fixed + static 3× + reactive Kubernetes-style scaling`. TrafficTwin v0.8 runner at `bd4570f` does not expose the new physical-semantics, placement, absolute-cap, or scaling flags without upgrade. **[IMPLEMENTATION-VERIFIED FACT]**
- **RESEARCH-EVIDENCE FACT:** No repository artifact at `bd4570f` establishes the reported `0.75×–40×` completion `~0.6943` and latency `4.9 → 128.4 s` sweep with raw JSON/CSV, commands, cap grid, actor checkpoint, or seeds. Treat as RANDY_REPORTED_RESULT only. **[RESEARCH-EVIDENCE FACT]**
- **LIMITATION:** Backhaul is modelled as one-hop fixed delay without bandwidth/loss/contention; staleness control, proactive forecasting, and learned dispatcher are not implemented in the evaluator at `bd4570f`. **[RESEARCH-EVIDENCE FACT]**
- **EXTERNAL DECISION REQUIRED:** Sandra's primary 4 August direction confirmation (beyond the S-035 body) remains needed to close TT-REQ-008 as MUST; until then the three-arm comparison is SHOULD with open decision YES. The exact comparison set for (B) and (C) needs a concrete controller specification. **[EXTERNAL DECISION REQUIRED]**
- **CLASS D material:** `TrafficTwin_Product_Design_Document_V2.docx` is proposal evidence only and does not amend the baseline. **[SOURCE-DERIVED FACT]**

## 10. Honesty boundaries

- No Sandra or Randy reply beyond S-035 and S-007 is authoritative for this lane. Do not infer Outlook headers, timestamps, or transport provenance. **[SOURCE-DERIVED FACT]**
- Repository features, issue text, PR claims, merges, route count, page rendering, provider accounts, and owner choices do not create negotiated requirements or prove scientific validity. **[SOURCE-DERIVED FACT]**
- The dissertation manuscript and `tos-data` are historical artifacts under v0.8; they are not independently re-executed or supervisor-approved as proof of TT-REQ-008's three-arm comparison. **[SOURCE-DERIVED FACT]**

## 11. External decisions still required

1. Supervisor confirmation of the primary late RSU comparison scope (exact arms for (B) and (C)) to promote TT-REQ-008 beyond SHOULD. **[EXTERNAL DECISION REQUIRED]**
2. Concrete specification for (B) learned scheduler and (C) AI-based resource controller (observation, action space, training data, reward, deployment target). **[EXTERNAL DECISION REQUIRED]**
3. Whether deterministic (A) alone suffices for the MSc thesis versus requiring implementation of (B) and (C). **[EXTERNAL DECISION REQUIRED]**

---
*Evidence labels are inline above. Frozen payload SHA `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` is not altered by this lane.*
