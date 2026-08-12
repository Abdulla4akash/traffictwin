# E2b–E2d Evidence Synthesis: Improved Strategy (v08 Lane 07)

**Campaign:** v08-requirements-closure, Lane 07, Feature E2b–E2d evidence synthesis
**Base SHA:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6` (frozen product tree)
**Source-honesty tags used throughout:** SOURCE-DERIVED FACT, IMPLEMENTATION-VERIFIED FACT, RESEARCH-EVIDENCE FACT, INFERENCE, PROVISIONAL WORDING, EXTERNAL DECISION REQUIRED

This document synthesizes only admitted read-only E2b, E2c, and E2d evidence. No new experiment was run. All numbers are bound to code SHA, manifest hash, actor, trace, seed, and artifact (see companion JSON/CSV/index and validator). Replication unit is run / fleet draw, never task.

---

## 1. Research question

[SOURCE-DERIVED FACT — S-035 / SANDRA-DIRECT-BODY-2026-08-04, SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`] The supervisor-identified problem is infrastructure load management: the trained vehicle policy does not observe current RSU load (capacity/busy) and offloads to the best available link, so congested-road RSUs become bottlenecks while farther RSUs remain idle. [SOURCE-DERIVED FACT — S-007, Randy Q&A] RSU queue/waiting-room capacity is an administrative control, not compute power; RSU broadcast of load is infeasible because data becomes obsolete within microseconds under concurrent execution.

[INFERENCE — from S-035 body] The direct Sandra body supports infrastructure load management as a supervisor-identified problem and requests investigation of three directions:
(A) DRL offloading + deterministic (Kubernetes) load balancing — hypothesised to improve completion in free-flow and congested conditions without retraining;
(B) DRL offloading + DRL scheduling/load balancing;
(C) DRL offloading + AI-based infrastructure/resource control.
Each is a supervisor-identified problem / requested investigation / proposed direction / hypothesised outcome as the body supports. [SOURCE-DERIVED FACT — S-035 standing narrowly: direct supervisor evidence for the problem and requested investigation only; S-035 does not by itself make any direction a mandatory assessed deliverable nor amend frozen Negotiated Version 1.] [PROVISIONAL WORDING] No direction is a mandatory assessed implementation without additional authoritative evidence. [EXTERNAL DECISION REQUIRED — frozen Negotiated Version 1 baseline unchanged, SHA-256 `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`; TT-REQ-008 remains SHOULD in the frozen baseline; any overlay inference that S-035 raises confidence toward PARTIALLY_MET is provisional and requires external decision, priority unchanged.]

[IMPLEMENTATION-VERIFIED FACT — Negotiated Version 1 TT-REQ-008] Comparative infrastructure-side RSU load management is SHOULD, conditional on late RSU direction confirmation, with authority boundaries and requirement for conditional (not universal) winner reporting.

**Narrow E2 question instantiated by E2b/E2c/E2d:** Does the choice of RSU placement target (strongest-link ingress vs JSQ least-busy) and granularity (one-common-target-per-substep vs per-task sequential) change offered-task deadline attainment under the same deadline-aware admission gate and over matched fleet draws?

---

## 2. Comparators

[RESEARCH-EVIDENCE FACT — E2b/E2c/E2d manifests and comparison JSONs]

| Comparator | Placement | Admission gate | Code binding |
|---|---|---|---|
| `off` | strongest-link ingress only, no JSQ | none (except fixed cap and coarse saturation) | E2b, commit `fe2ed4e9bd9043b19b96a5f179390db629b01ccb` |
| `jsq` | JSQ without gate (one-common-target-per-substep) | none | same |
| `ingress_dla` | strongest-link ingress only | deadline-aware (DLA) gate: `effective_busy_ms < TASK_DEADLINE_MS[task]` | same |
| `dla` | one-common-target-per-substep JSQ (`argmin(rsu_busy_ms)` per substep, all eligible V2I in substep share one target) | deadline-aware gate | E2c commit `1a08d6e148a1e8c430da39c3d575eda3f8ea5929`, manifest `fcaf2ee34b...` |
| `per_task_dla` | per-task sequential least-busy: recomputes `argmin(effective_busy_ms)` per task in ascending padded vehicle-slot order | same inherited gate applied causally per selected target | E2d commit `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`, manifest `f77afb23...` |

All arms share: actor `mappo_modelc_17dim`, SHA-256 `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`, training seed 100, frozen, 17-dim, does not observe RSU load nor select execution RSU [IMPLEMENTATION-VERIFIED FACT]; trace `trace_inc_fullrsu.npz`, SHA-256 `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`; evaluator seed 0; Manchester incident hour 2024-03-15 20:00-21:00; provisional uk2030 fleet; waiting-room cap 2.5× (6220 tasks/RSU); 1× service; zero backhaul [RESEARCH-EVIDENCE FACT].

---

## 3. Strategy

Structure: research question → comparators (above) → strategy (matched evidence under shared scenarios) → primary outcome → mechanism → uncertainty → interpretation → limits.

**Strategy — matched evidence:**
- E2b mechanism decomposition: 4-cell factorial (placement × admission) on one fleet draw (seed 0), 13,076,234 offered tasks. Three cells are immutable completed E2 outputs reused by exact hash; only `ingress_dla` is new. One-draw descriptive evidence only [RESEARCH-EVIDENCE FACT].
- E2c matched common-target result/limit: 4 new matched fleet draws (seeds 1–4), paired `dla` vs `ingress_dla` holding the deadline gate fixed. Primary interval is two-sided 95% Student-t over fleet-draw differences (df=3). Seed 0 is prior pilot evidence, excluded from primary interval [RESEARCH-EVIDENCE FACT].
- E2d per-task result/uncertainty: 4 matched provisional fleet draws (seeds 1–4), paired `per_task_dla` vs `ingress_dla` (primary) and vs `dla` (secondary). Same t-interval convention, fleet seed as replication unit [RESEARCH-EVIDENCE FACT].

Replication/uncertainty explicit: run / fleet draw is the replication unit; tasks are accounting records, never independent replicates. One-draw vs four-draw and t-interval reporting are in the respective JSON fields [RESEARCH-EVIDENCE FACT].

---

## 4. Matched evidence and primary outcome

[SOURCE-DERIVED FACT binding for every number: see `improved_strategy_results.json` and `improved_strategy_figure_data.csv`; each row carries manifest, code commit, actor, trace, seed, artifact. Validator rejects orphan numbers.]

### E2b — 4-cell factorial (seed 0, descriptive)

| Placement | Gate off | Gate on |
|---|---|---|
| Strongest-link | `off` 0.683619229 | `ingress_dla` 0.715773211 |
| JSQ (common-target) | `jsq` 0.675681775 | `dla` 0.694939919 |

Offered tasks: 13,076,234 in all cells. Declared offered-attainment contrasts: placement without gate JSQ−off = −0.007937454; placement with gate DLA−ingress_DLA = −0.020833292; admission under strongest-link ingress_DLA−off = +0.032153983; admission under JSQ DLA−JSQ = +0.019258144; interaction = −0.012895838 [RESEARCH-EVIDENCE FACT — E2b comparison, manifest `9383ec76...`, commit `fe2ed4e9...`]. Primary placement-with-gate observation is lower offered attainment for common-target JSQ vs strongest-link. Close values not treated as equivalent.

Inherited caveat: `off` vs `ingress_dla` contrast retains one eligibility-timing difference: `off` uses step-entry coarse saturation check, `ingress_dla` recomputes it against live backlog per substep; completed `off` recorded 138 unavailable V2I attempts (~1.1e-5/offered) [RESEARCH-EVIDENCE FACT].

### E2c — matched common-target, 4 new draws

Per-seed `dla − ingress_dla` offered attainment: seed1 −0.022097034972, seed2 −0.020519134179, seed3 −0.021447383092, seed4 −0.020825491499 [RESEARCH-EVIDENCE FACT — manifest `fcaf2ee34...`, commit `1a08d6e...`].

- Mean −0.021222260935, SD 0.000699457605, SE 0.000349728802
- Two-sided 95% Student-t interval, df=3: [−0.022335254070, −0.020109267800], excludes zero
- Decision (predeclared): `evidence_of_directional_difference_within_bounded_four_draw_replication`
- Combined 5-draw descriptive (seeds 0–4, not confirmatory): mean −0.021144467130, all 5 negative [RESEARCH-EVIDENCE FACT]

Within bounded four-new-draw Manchester incident replication, common-target JSQ placement produced lower offered attainment than strongest-link when both used the same deadline gate.

### E2d — per-task sequential vs ingress, 4 draws

Per-seed `per_task_dla − ingress_dla`: seed1 +0.004636732564, seed2 +0.005867285642, seed3 +0.005071796666, seed4 +0.005509919752 [RESEARCH-EVIDENCE FACT — manifest `f77afb23...`, commit `80e8ae55...`].

- Mean +0.005271433656, SD 0.000533733895, SE 0.000266866947
- 95% Student-t, df=3: [+0.004422143925, +0.006120723387], excludes zero
- Decision: `directional_advantage_for_per_task_placement_within_bounded_draws`
- Secondary per_task−dla mean +0.026493694591, interval [+0.026210763951, +0.026776625232]

No equivalence, no universal superiority, no population generalisation [RESEARCH-EVIDENCE FACT].

All figure cells above resolve to exact read-only identities: see `improved_strategy_evidence_index.json` → `figure_cell_to_evidence` and companion CSV `artifact_path` per row.

---

## 5. Mechanism

[RESEARCH-EVIDENCE FACT — path/mechanism summaries bound to manifests above]

- **E2b path decomposition:** `ingress_dla` selected strongest-link ingress for every V2I attempt, forwarded 0 tasks, charged 0 ms forwarding, execution lay on ingress-to-ingress diagonal; gate-rejected tasks retained ingress, execution = −1, not enqueued. `dla` forwarded 232,729 (83.5% of admitted V2I) with ideal zero-cost fibre; `jsq` forwarded 2,067,204 (90%). Execution imbalance (max share − min share): `ingress_dla` 0.06005, `dla` 0.24001, `jsq` 0.000458 [E2b path summary `dd48da13...`].
- **E2c execution imbalance:** Over 4 new draws, `ingress_dla` range ~0.04–0.06 (balanced execution at ingress); `dla` range ~0.18–0.24 (max deviation concentrated on congested-road RSUs). `ingress_dla` forwarded 0; `dla` forwarded 234k–242k per draw [E2c mechanism summary `5556f0fc...`].
- **E2d per-task mechanism:** `per_task_dla` recomputed least remaining-service-work target per task in padded vehicle-slot order; `task_substeps_with_more_than_one_selected_target` >0, `maximum_unique_selected_targets_in_one_substep` >1 in per_task arms, versus 0/1 in common-target `dla`. Gate rejection then applied per selected target; admitted work added one load unit + exact service work to effective busy vector causally [E2d mechanism summary `4975ab87...`].

Conservation passed in all cells: task accounting, V2I/vehicle service-work, native path consistency [RESEARCH-EVIDENCE FACT].

---

## 6. Uncertainty

| Evidence | Replication unit | N | Inference treatment | Uncertainty statement |
|---|---|---|---|---|
| E2b | fleet_draw (seed 0) | 1 | tasks not replicates, no interval, descriptive only | No confidence interval; directional observation only [RESEARCH-EVIDENCE FACT] |
| E2c | fleet_draw | 4 (seeds 1–4) | paired fleet-draw differences; tasks not replicates | Two-sided 95% Student-t, df=3, mean −0.02122, interval [−0.02234, −0.02011], excludes zero; decision is directional within bounded draws only [RESEARCH-EVIDENCE FACT] |
| E2d | fleet_draw | 4 (seeds 1–4) | same paired convention | Two-sided 95% Student-t, df=3, mean +0.00527, interval [+0.00442, +0.00612], excludes zero; construct-validity comparison only [RESEARCH-EVIDENCE FACT] |

Validator requires explicit `replication_unit`, `n_fleet_draws`, `degrees_of_freedom`, `method`, `lower`/`upper`, and rejects labels such as `replication_unit: task` or `tasks as independent replicates` [IMPLEMENTATION-VERIFIED FACT — see `scripts/validate_v08_improved_strategy_evidence.py`].

---

## 7. Interpretation

- **E2b:** Under one Manchester incident fleet draw, deadline-aware admission raised offered attainment over no-gate at both placements, while common-target JSQ placement lowered it relative to strongest-link at both gate states. The interaction is negative (−0.0129). This is mechanism description, not a claim of universal controller superiority [INFERENCE boundary — descriptive only].
- **E2c:** Within four new matched incident draws, the one-common-target-per-substep implementation of least-busy placement under the inherited gate produced lower offered attainment than strongest-link execution. The predeclared directional decision is supported inside these bounded draws; equivalence, Kubernetes deployment, physical validity, and population-wide claims are not supported [RESEARCH-EVIDENCE FACT + PROVISIONAL WORDING].
- **E2d:** Within the same four-draw bounded study, per-task sequential least-busy placement showed a small positive directional advantage over strongest-link ingress and a larger advantage over the common-target implementation. This is a controlled simulator construct-validity result; it does not establish universal least-busy superiority, physical/Kubernetes evidence, or Manchester-wide performance [RESEARCH-EVIDENCE FACT + PROVISIONAL WORDING].

Combined reading (INFERENCE, not a new experiment): common-target granularity harmed attainment in E2b/E2c; per-task granularity recovered and modestly exceeded ingress in E2d, but all three effects remain bounded to the stated scenario, cap, actor, and replication unit.

---

## 8. Limits and honesty boundaries

**E2b/E2c/E2d distinctions preserved:**
- E2b = one-draw factorial mechanism decomposition, no interval.
- E2c = four-new-draw matched common-target result with 95% t-interval and explicit exclusions (seed 0 excluded, tasks not replicates).
- E2d = four-draw per-task construct-validity result with its own interval and separate secondary comparison.
All three are tagged and validated as distinct.

**All findings limited to:** one Manchester incident hour (2024-03-15 20:00–21:00), one provisional uk2030 fleet, fixed evaluator seed 0, waiting-room cap 2.5× (6220 tasks/RSU), fixed 1× service, zero-cost backhaul, frozen 17-dim MAPPO actor that neither observes RSU load nor chooses execution RSUs, identical arrival process. No ordinary/free-flow traffic control, no physical task-result-return confirmation, no Kubernetes or physical deployment, no actor retraining, no prediction/masking. Evaluator success ≠ confirmed physical return [RESEARCH-EVIDENCE FACT].

**Prohibited claims not made:** No new experiment, no task-level pseudo-replication, no copying raw outputs into product main, no independent-rerun claim beyond the exact read-only hashes, no supervisor-approval claim, no conclusion beyond admitted evidence, no claim that S-035 establishes timestamp/headers/Outlook provenance, no claim that every S-035 proposed direction is mandatory assessed implementation [SOURCE-DERIVED FACT — S-035 standing].

**External decisions still required:** Sandra confirmation of the primary late RQ and authority boundaries for TT-REQ-008; any extension beyond bounded fleet draws requires new primary evidence and independent review [EXTERNAL DECISION REQUIRED].

---

## 9. Traceability

Every numeric cell → `improved_strategy_figure_data.csv` row → `evidence_id` → `improved_strategy_evidence_index.json` identity (path, sha256, manifest, commit, read-only ref) → raw checksums and manifests listed there → actor/trace hashes and seeds in that manifest. Validator (`scripts/validate_v08_improved_strategy_evidence.py`) enforces: evidence identity exists, manifest/code/actor/trace/seed/fleet present per row, replication_unit is fleet_draw/run, tasks not used as replicates, intervals explicit, no orphan numbers. Mutations removing a binding or relabeling tasks as replicates must cause validation failure.

**Standings legend applied inline above:** SOURCE-DERIVED FACT (direct S-035/S-001/etc body), IMPLEMENTATION-VERIFIED FACT (code/manifest binding), RESEARCH-EVIDENCE FACT (admitted E2b/c/d JSON), INFERENCE (interpretive step), PROVISIONAL WORDING (hypothesised/candidate), EXTERNAL DECISION REQUIRED (confirmation gate).

---

*Generated at v08 lane 07 closure. Frozen baseline text and hash unchanged. This synthesis is admitted evidence only and does not amend Negotiated Version 1.*
