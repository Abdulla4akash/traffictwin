# Improved Dynamic Strategy Contract — V08 Closure Lane 06

**Campaign:** `v08-requirements-closure` · **Lane:** `06` · **Feature:** Improved dynamic strategy contract
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` · **Contract ID:** `TT-REQ-008-derived-improved-strategy-E2d-v1`
**Fingerprint (SHA-256 canonical):** `af128cf0826cd03ea85c29b71edb1385dd7523a1086626a4ebb4015f982abce4`
**Fingerprint payload keys:** `identity, input_state, order, feasible_set, load_and_service_work_quantity, immediate_reservation_update, deterministic_tie_break, admission_interaction, forwarding, refusal_taxonomy, actor_boundary`
**Algorithm:** `sha256(json.dumps(payload, sort_keys=True, separators=(',',':')).encode('utf-8'))` — must match JSON contract and pseudocode header.

> Source-honesty labels used throughout: **SOURCE-DERIVED FACT**, **IMPLEMENTATION-VERIFIED FACT**, **RESEARCH-EVIDENCE FACT**, **INFERENCE**, **PROVISIONAL WORDING**, **EXTERNAL DECISION REQUIRED**.
> Violating the label discipline is a contract defect.

## 1. Scope and identity — E2d-bounded

- **Precise name [IMPLEMENTATION-VERIFIED FACT / RESEARCH-EVIDENCE FACT]:** *per-task sequential least-busy feasible RSU placement* (equivalently *per-task sequential shortest-workload placement*; CLI `per_task_dla`). Frozen E2d manifest `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740` calls it `per-task sequential least-busy placement`.
- **What it is [IMPLEMENTATION-VERIFIED FACT]:** A deterministic infrastructure-side placement rule applied *after* the vehicle actor's offload intent. It is **not learned**. No neural policy selects the execution RSU.
- **What it is not [SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT]:** Not MAPPO policy learning, not actor RSU selection, not Kubernetes deployment, not compute scaling, not staleness-aware. Conflating downstream deterministic placement with actor learning is forbidden.
- **Bound [RESEARCH-EVIDENCE FACT]:** Evidenced only over **four matched `uk2030` provisional fleet draws (seeds 1–4)**, one Manchester incident trace `2024-03-15 20:00–21:00 Europe/London`, 3 600 steps, fixed evaluator seed 0, `2.5× / 6 220-task` cap, fixed `1×` service, zero backhaul. No broadening beyond this bound.

## 2. Input state

| Input | Units | Semantics | Honesty |
|---|---|---|---|
| `rsu_busy_ms` — total remaining RSU compute workload | ms of service work | Admitted `rsu_compute_ms` added; at most 1 000 ms drained per simulated second; remainder carried | **IMPLEMENTATION-VERIFIED FACT** at vec_env parent `0e5ed2f79b50011fe0475a5c2069978f9fdd778d` |
| `rsu_load` — admitted task count | tasks | One increment per admitted V2I task | **IMPLEMENTATION-VERIFIED FACT** |
| Live `rb`/`rl` at substep entry | ms / tasks | Temporary effective vectors `effective_busy_ms`/`effective_load` are copied from these at each task substep | **IMPLEMENTATION-VERIFIED FACT** |
| `TASK_DEADLINE_MS[task_type]` | ms | Per-type deadline threshold for the strict backlog gate | **IMPLEMENTATION-VERIFIED FACT** |
| Service multiplier | ratio | Locked to `1.0` in E2d | **RESEARCH-EVIDENCE FACT** |

## 3. Order (candidate scan)

- **Order [IMPLEMENTATION-VERIFIED FACT / RESEARCH-EVIDENCE FACT]:** Ascending task-substep index, then ascending padded vehicle-slot index (stable order shared with co-batch offsets and scatter updates; padded fleet width 2 488).
- Any *common-target* variant that selects one `argmin` per substep and reuses it for all candidates in that substep **does not satisfy this contract** — it is the inherited `dla` behaviour, not `per_task_dla` (mutant `common-target`).

## 4. Feasible set

- **Domain [IMPLEMENTATION-VERIFIED FACT]:** All configured RSUs (10). Identical to inherited `dla`.
- **Filtering [IMPLEMENTATION-VERIFIED FACT]:** Reachability, ingress quality, and capacity **do not** filter the `argmin` domain. The selector always considers all RSUs.
- **Post-selection eligibility:** A candidate proceeds only if it has positive ingress-link quality and its selected target is below cap at substep entry. This check happens *after* `argmin`, not before.

## 5. Load / service-work quantity

- **State interpretation [IMPLEMENTATION-VERIFIED FACT]:** Shortest remaining service workload in `rsu_busy_ms` — **not** task-count shortest-queue and **not** canonical JSQ. The E2d decision record explicitly denies a canonical JSQ claim.
- **Selection metric:** `selected_rsu = argmin(effective_busy_ms)` recomputed for *every* candidate.
- **Service reservation [IMPLEMENTATION-VERIFIED FACT]:** Quantity is the *exact selected RSU service work* = `compute_time_ms(task, RSU_TIER_IDX) / service_multiplier` derived from **split index 1 of the existing five-way `process_agent` subkey split**. No new RNG draw, split, or key-chain change.

## 6. Immediate reservation update

- **Admitted [IMPLEMENTATION-VERIFIED FACT]:** Add one load unit **and** the exact service work to the *temporary effective* vectors immediately; next candidate in scan sees the updated `effective_busy_ms`.
- **Rejected [IMPLEMENTATION-VERIFIED FACT]:** `unavailable`, `gate_rejected`, `cap_rejected` leave temporary state unchanged.
- **Mutant `no-reservation`** (omitting immediate update or batching reservations) violates this clause and must be rejected.

## 7. Deterministic tie-break

- **Rule [IMPLEMENTATION-VERIFIED FACT]:** `jnp.argmin` — lowest RSU index on exact workload tie. Non-random, non-configurable.
- **Mutant `nondeterministic-tie`** (random among ties, or unspecified break) violates this clause.

## 8. Admission interaction

Ordered per-candidate steps:

1. Record selected target for V2I attempt.
2. Inherited ingress-radio eligibility (positive ingress-link quality).
3. **Strict backlog deadline gate** at *selected* target.
4. Live in-batch cap with **gate-before-cap outcome precedence**.
5. Only if admitted, commit via unchanged evaluator admitted-work scatter.

### 8.1 Deadline gate — must not be removed

- **Formula [IMPLEMENTATION-VERIFIED FACT]:** `effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]` — strict, backlog-only.
- **Excludes [IMPLEMENTATION-VERIFIED FACT]:** own compute, radio transfer, return transfer, forwarding latency.
- **Label:** *deadline-aware feasibility* in E2d retains this limited backlog-only meaning; it is **not** confirmed physical result-return. Gate is simulator rule [IMPLEMENTATION-VERIFIED FACT / INFERENCE].
- **Mutant `removed-gate`** (any candidate admitted when `effective_busy_ms >= deadline`) fails validation.

### 8.2 Cap / waiting-room semantics

- **`MAX_CONCURRENT` meaning [SOURCE-DERIVED FACT via S-007 + S-035]:** Per-RSU admission / in-flight waiting-room ceiling — **not computation power**.
- **E2d values [RESEARCH-EVIDENCE FACT]:** `2.5×` / `6 220 tasks per RSU`, `reject` mode, `sequential` substeps (3 iterations), `conserved` vehicle queue.
- **Overflow [SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT]:** Immediate terminal rejection without queue entry, retry, fallback, or re-forwarding (S-007 confirmed).
- **Reconciliation [IMPLEMENTATION-VERIFIED FACT]:** Repeat complete causal pass three times from identical live `rb`/`rl`; use idempotent final result; state never accumulates across passes. First pass already self-consistent because rejected work never reserves.

## 9. Forwarding

- **Definition [IMPLEMENTATION-VERIFIED FACT]:** `forwarded` is true exactly when admitted V2I execution RSU ≠ strongest-link ingress RSU.
- Ingress remains strongest-link RSU; ordering does not change radio attachment.
- E2d backhaul `0.0 ms` [RESEARCH-EVIDENCE FACT]; forwarding cost is frozen out and not tested.
- `rejected` tasks have `execution = -1`, never forward, never enter a queue.

## 10. Refusal taxonomy

| Outcome | Meaning | Temp-state | Honesty |
|---|---|---|---|
| `unavailable` | No positive ingress link or no V2I candidate | unchanged | **IMPLEMENTATION-VERIFIED FACT** |
| `gate_rejected` | Deadline gate fails at selected target | unchanged | **IMPLEMENTATION-VERIFIED FACT** |
| `cap_rejected` | Live cap rejects at selected target | unchanged | **IMPLEMENTATION-VERIFIED FACT** |
| — | No retry, no fallback, no re-forwarding | — | **SOURCE-DERIVED FACT** (S-007) |

## 11. Actor boundary — deterministic vs learned

- **Actor [SOURCE-DERIVED FACT + RESEARCH-EVIDENCE FACT]:** MAPPO (`mappo_modelc_17dim__envs128__lr3e-3__seed100`, SHA-256 `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`), 17-dim obs, actions `[Local, V2I, V2V]`, **frozen** (`training_seed 100`), `frozen:true` in E2d manifest.
- **Capacity awareness [SOURCE-DERIVED FACT via S-035]:** Trained vehicle policy has **no explicit current RSU load/capacity awareness** — RSUs do not broadcast load because state ages in microseconds and the information would be stale.
- **Who selects RSU [IMPLEMENTATION-VERIFIED FACT]:** Actor emits offload *intent* (e.g., V2I via best available link in congested reasoning). **Infrastructure deterministic placement selects execution RSU downstream.** Actor `selects_execution_rsu == false`.
- **Mutant `actor-RSU-credit`** (claiming MAPPO/actor selects or learns the execution RSU) violates this boundary.

## 12. Identity and limitations (what is claimed vs not claimed)

**Claimed within bound [RESEARCH-EVIDENCE FACT]:** Under the four bounded draws, `per_task_dla` vs `ingress_dla` offered attainment deltas `[+0.0046, +0.0058]` with mean `+0.00527` and 95 % Student-t interval excluding zero; `per_task_dla` vs inherited `dla` deltas `[+0.0263, +0.0267]` — both labelled `directional_advantage_for_per_task_placement_within_bounded_draws` by predeclared decision.

**Explicitly not claimed [RESEARCH-EVIDENCE FACT + INFERENCE]:**

- No physical / Kubernetes deployment (claim boundary `physical_or_kubernetes_deployment_tested: false`).
- No reactive/static scaling, oracle, or AI-Kubernetes controller.
- No backhaul or staleness sensitivity (frozen at zero; not swept).
- No ordinary-traffic control, population or Manchester-wide claim, no task-level significance, no canonical JSQ semantics, no confirmed physical result-return.
- Fleet is provisional `uk2030`; seed 0 excluded; tasks are not independent replicates.

## 13. Sandra direct body S-035 — classification

- **Source [SOURCE-DERIVED FACT]:** Campaign key `S-035 / SANDRA-DIRECT-BODY-2026-08-04`, SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`, read-only mirror `.harness/context/sources/S-035__sandra-direct-email.md`. Supersedes `SRC-010` for overlapping body only; does not establish timestamp, message-id, transport headers, or Outlook provenance [PROVISIONAL WORDING].
- **Supports [SOURCE-DERIVED FACT]:** RSU queue/waiting-room capacity (not compute, `2.5 → 0.75` tightening); plausible fail-fast/rejection-accounting explanation for reduced latency with unchanged deadline attainment; no explicit current RSU load awareness; disproportionate congested-road RSU load while far RSUs idle; infrastructure load management as supervisor-identified problem.
- **Requests investigation of [SOURCE-DERIVED FACT, classified as PROVISIONAL WORDING]:**
  - **(A)** DRL offloading + deterministic load balancing (Kubernetes load balancing; *retraining not required*, forward from best-link RSU to quieter RSU, hypothesised improved completion in free-flow and congested).
  - **(B)** DRL offloading + DRL scheduling / load balancing.
  - **(C)** DRL offloading + AI-based infrastructure / resource control.
- **Honesty obligation:** Each of (A)(B)(C) is a **supervisor-identified problem / requested investigation / proposed direction / hypothesised outcome** as the body supports. None is a mandatory assessed implementation without additional authoritative evidence. Do not promote Class C provisional body to approved MUST and do not convert requested investigations into mandatory deliverables.
- **TT-REQ-008 effect [INFERENCE + EXTERNAL DECISION REQUIRED]:** S-035 raises direct source confidence for comparative infrastructure RSU load management and supports campaign status `PARTIALLY_MET` for TT-REQ-008, but **does not change its SHOULD priority** and does not silently amend frozen Negotiated Version 1 (payload SHA-256 `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` remains unchanged).

## 14. Prohibited claims — verified absent

- No broadening beyond E2d evidence.
- No presentation of provisional Sandra scope as approved.
- No removal of deadline gate.
- No conflation of deterministic downstream placement with actor learning (MAPPO does not select RSU).
- No compute-power reinterpretation of queue cap.
- No universal, Manchester-wide, or Kubernetes-physical superiority claim.

## 15. Source honesty legend

- **SOURCE-DERIVED FACT:** Directly in staged primary source bytes.
- **IMPLEMENTATION-VERIFIED FACT:** Verified in exact committed code at stated parent SHA.
- **RESEARCH-EVIDENCE FACT:** Observed in closed E2d records under stated manifest.
- **INFERENCE:** Derivative reasoning constrained by above.
- **PROVISIONAL WORDING:** Supervisor-requested direction awaiting independent confirmation beyond S-035 body.
- **EXTERNAL DECISION REQUIRED:** Cannot be closed without new primary source or authority (e.g., final supervisor approval of RSU comparison as assessed MUST, Outlook provenance for S-035 timestamp).

## 16. Traceability

| Authoritative source | SHA-256 | Standing |
|---|---|---|
| FINAL_AUDIT | `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9` | FINAL_NEGOTIATED_REQUIREMENTS_AUDIT |
| NEGOTIATED_V1_WHOLE_FILE | `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` | FROZEN_REQUIREMENTS_BASELINE_CONTAINER (payload `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`) |
| RESEARCH_AUDIT_SEMANTIC_CONTRACT | `c7e01197160cb43db5f35bf804e6aa2beae6272a5915a1581369bdf0ec284645` | ORIGINAL_RESEARCH_AUDIT_AND_SEMANTIC_CONTRACT |
| S-035 | `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed` | DIRECT_SUPERVISOR_SOURCE_BODY |
| E2d TrafficTwin pre-run | `eb8571810cc0f29c8477b14e15a73d7e3c915f69` | candidate scientific code commit |
| E2d manifest | `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740` | corrected predeclared before any E2d trace |
| E2d vec_env candidate | `2f63706f46319433a2ba3af1df97afd0e56a95d1` | per_task_dla evaluator extension |

Deterministic pseudocode and validator fingerprint must agree with this header hash; any divergence is a lane defect.
