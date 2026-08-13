# Dissertation Restructure Plan — v08 Requirements Closure (Lane 10)

**Campaign:** `v08-requirements-closure` — Lane `10` — Worker `muse-10`
**Feature:** Dissertation traceability and restructure plan
**Base SHA:** `a244776a2385a2ecb2e0d8f40a15afafaccad8f7`
**Frozen baseline:** Negotiated Version 1 — canonical payload `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`
**Date:** 2026-08-12

> **Standing banner — SOURCE-DERIVED FACT:** This is a complete unapproved draft restructuring proposal. It proposes chapter ordering and traceability bindings for review only. No Sandra confirmation, final/submitted report, or FULLY ALIGNED standing is claimed. Every statement carries: **SOURCE-DERIVED FACT**, **IMPLEMENTATION-VERIFIED FACT**, **RESEARCH-EVIDENCE FACT**, **INFERENCE**, **PROVISIONAL WORDING**, **EXTERNAL DECISION REQUIRED**.

## 1. Authority and reuse

- Frozen requirements: `requirements_baseline_v1.json` + `requirements_baseline_v1.md` (byte-for-byte quotations) — SOURCE-DERIVED FACT.
- Requirement statuses: `requirements_status_v08.json` — IMPLEMENTATION-VERIFIED FACT (MUST 3+7+1).
- Trace master: `dissertation_traceability.md` §2 — exactly 14 IDs once; this plan's chapters are the only valid chapter targets — IMPLEMENTATION-VERIFIED FACT.
- Dependency artifacts consumed read-only at `a244776a`: `use_case_a_manchester_current_twin.md`, `use_case_b_vec_dynamic_service.md`, `existing_strategy_assessment.md`, `improved_dynamic_strategy_contract.md/json`, `manchester_demo/` contracts, `task_semantics_contract.json` — IMPLEMENTATION-VERIFIED FACT.
- Lane 09 packet is MIXED bounded offline demonstration, not live-city claim — SOURCE-DERIVED FACT.
- S-035 direct body (`08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`) is DIRECT_SUPERVISOR_SOURCE_BODY for content only; no timestamp/headers inferred — SOURCE-DERIVED FACT.

No change to frozen baseline priority/status; S-035 investigations A/B/C remain requested investigations / proposed directions / hypothesised outcomes, not mandatory implementations without additional confirmation — EXTERNAL DECISION REQUIRED.

## 2. Eight-chapter frame — each chapter lists resident requirements, narrative purpose, and evidence

### Ch1 — Problem and Two Services

**Resident requirements:** TT-REQ-001 (methodology), TT-REQ-002 (two services) — SOURCE-DERIVED FACT master binding.

**Narrative purpose:**

- State the Project 237 resource-management problem and why it is assessed as MUST (S-001) — SOURCE-DERIVED FACT.
- Justify the selected methodology and its alternatives per rubric S-003 — SOURCE-DERIVED FACT.
- Operationalise "a few ITS service use cases" as exactly two services:
  - **Service A — bounded Manchester current-context** (Lane 03): `use_case_a_manchester_current_twin.md` + `manchester_demo/data_contract.json` — IMPLEMENTATION-VERIFIED FACT; offline-first, honestly labelled synthetic/real separation, no live city-wide twin — RESEARCH-EVIDENCE FACT.
  - **Service B — deadline-aware VEC dynamic service** (Lane 04): `use_case_b_vec_dynamic_service.md` + `use_case_b_manifest.json` — IMPLEMENTATION-VERIFIED FACT; RSU waiting-room semantics per S-007/S-035.
- Declare each service's purpose, workload/input, resource needs, QoS outcomes — SOURCE-DERIVED FACT requirement.

**Trace anchors:** `dissertation_traceability.md:TT-REQ-001`, `TT-REQ-002`; `requirements_baseline_v1.json` quotations.

**Gap carried:** TT-REQ-002 P0 — whether VEC variants qualify as distinct services remains PROVISIONAL_PENDING_SANDRA — EXTERNAL DECISION REQUIRED.

### Ch2 — Existing Strategies

**Resident requirements:** TT-REQ-004 — SOURCE-DERIVED FACT.

**Narrative purpose:**

- Name existing/edge/RSU strategy families explicitly (e.g., strongest-link, JSQ, DLA as families under Lane 05) — SOURCE-DERIVED FACT from `existing_strategy_assessment.md` / `strategy_matrix.json` / `strategy_evidence_map.json`.
- Evaluate suitability against common service and QoS criteria using shared, justified evidence — SOURCE-DERIVED FACT acceptance criterion.
- Report limitations and conditions of suitability, not a universal winner — SOURCE-DERIVED FACT.
- Contain historical factorial evidence (E2b/E2c/E2d) as RESEARCH-EVIDENCE FACT by hash, not as fresh rerun — RESEARCH-EVIDENCE FACT.

**Trace anchors:** `dissertation_traceability.md:TT-REQ-004`.

**Gap carried:** P0 — complete family naming and suitability table not yet closed — EXTERNAL DECISION REQUIRED (ED-003).

### Ch3 — Improved Strategy

**Resident requirements:** TT-REQ-005 (improved strategy), TT-REQ-008 (comparative RSU load-management investigation — thesis-level SHOULD) — SOURCE-DERIVED FACT.

**Narrative purpose:**

- Specify the improved dynamic strategy clearly enough to assess/reproduce conceptually: `improved_dynamic_strategy_contract.md/json` per-task sequential least-busy feasible RSU placement (deterministic, per-task `argmin(effective_busy_ms)`) — IMPLEMENTATION-VERIFIED FACT; E2d-bounded — RESEARCH-EVIDENCE FACT.
- Trace it to a limitation identified under Ch2 (e.g., congested-road RSU bottleneck while farther RSUs idle — S-035 paras 4–6) — SOURCE-DERIVED FACT.
- Explain storage/compute management under mobility/dynamicity and expected/observed QoS effects and trade-offs — SOURCE-DERIVED FACT.
- For TT-REQ-008, present the three S-035 requested investigations as distinct rows:
  - (A) DRL offloading + deterministic (Kubernetes) load balancing — hypothesised improved completion in free-flow and congested without retraining — SOURCE-DERIVED FACT, PROVISIONAL WORDING for mandatory status.
  - (B) DRL offloading + DRL scheduling/load balancing — SOURCE-DERIVED FACT, PROVISIONAL WORDING.
  - (C) DRL offloading + AI-based infrastructure control — SOURCE-DERIVED FACT, PROVISIONAL WORDING.
  - None is a mandatory assessed implementation without additional authoritative evidence — INFERENCE, EXTERNAL DECISION REQUIRED (ED-002). Priority remains SHOULD, campaign status PARTIALLY_MET.

**Trace anchors:** `dissertation_traceability.md:TT-REQ-005`, `TT-REQ-008`; `improved_dynamic_strategy_pseudocode.txt` (fingerprint `af128cf...`).

**Gap carried:** TT-REQ-005 P0 (no adequate QoS/trade-off assessment); TT-REQ-008 P1 (three-arm common-scenario comparison not executed).

### Ch4 — System and Data Engineering

**Resident requirements:** TT-REQ-012 (provider conditions), TT-REQ-014 (bounded data-engineering extension, MAY) — SOURCE-DERIVED FACT.

**Narrative purpose:**

- Document acquired inputs with honest source/time metadata and licence acknowledgement: National Highways DATEX2 and WebTRIS (strategic road), BODS bus positions (bus-only), DfT counts (historical), ONS boundary (static), TfGM signals (DESIGN-ONLY CAPABILITY — unavailable for current view) — IMPLEMENTATION-VERIFIED FACT via `manchester_demo/data_contract.json` / `source_receipt.json`.
- Show that restricted feeds fail closed and unattributed delivery is not claimed — IMPLEMENTATION-VERIFIED FACT.
- Present the bounded synthetic what-if workflow (manual incident → synthetic square SUMO hand-authored → scenario builder) as the MAY extension, explicitly after-core/if-time — SOURCE-DERIVED FACT; synthetic standing — IMPLEMENTATION-VERIFIED FACT.
- Reuse only committed receipts/fixtures by SHA-256; never publish raw private bytes — RESEARCH-EVIDENCE FACT.

**Trace anchors:** `dissertation_traceability.md:TT-REQ-012`, `TT-REQ-014`.

**Gap carried:** TT-REQ-014 P3 sequencing condition not met because P0 cores remain open; ED-006 (whether later correspondence changes MAY) and ED-007 (TfGM delivery) remain — EXTERNAL DECISION REQUIRED.

### Ch5 — Evaluation

**Resident requirements:** TT-REQ-003 (run-time profiling), TT-REQ-006 (goal-aligned evaluation), TT-REQ-007 (report and complementary video), TT-REQ-009 (varied controlled non-trivial scenarios), TT-REQ-008 evaluation half — SOURCE-DERIVED FACT.

**Narrative purpose:**

- Align objectives → evaluation questions → methods → evidence → conclusions with explicit traceability — SOURCE-DERIVED FACT (TT-REQ-006).
- Present run-time profiling for each of the two services under declared workloads/scenarios with defined measures/units and distinction between executed observations and static design — SOURCE-DERIVED FACT (TT-REQ-003).
- Document report/video preparation: complete 8396-word draft and exact 7:00 storyboard/script as preparation, not submission — IMPLEMENTATION-VERIFIED FACT; PROVISIONAL WORDING for submission timeline.
- Show matched evidence design: replication unit is run/fleet draw, not task; uncertainty via per-draw intervals; historical E2b/E2c/E2d records are RESEARCH-EVIDENCE FACTs by manifest hash — RESEARCH-EVIDENCE FACT.
- Present comparative RSU evaluation on common resource/QoS outcomes under materially different operating conditions (free-flow vs congested); conditional strengths/limits, not universal winner — SOURCE-DERIVED FACT (TT-REQ-008 acceptance).

**Trace anchors:** `dissertation_traceability.md:TT-REQ-003,006,007,008,009`.

**Gaps carried:** TT-REQ-003 P1; TT-REQ-007 P1 (no recorded video file); TT-REQ-008 P1; others VERIFIED_MET (TT-REQ-006/009).

### Ch6 — Evidence Standing

**Resident requirements:** TT-REQ-010 (claim accuracy), TT-REQ-011 (Randy semantics) — SOURCE-DERIVED FACT.

**Narrative purpose:**

- Enforce technically accurate, evidence-backed claims and explicit real/synthetic/simulated separation; Manchester label or provider account never presented as real Manchester VEC validation — SOURCE-DERIVED FACT (TT-REQ-010).
- Enforce per-RSU admission/in-flight waiting-room ceiling vs compute service rate distinction; terminal rejection of surplus tasks (outside queue, no retry/fallback/re-forwarding); do not describe admission-limit change as processing-capacity change — SOURCE-DERIVED FACT via S-007/S-035/`task_semantics_contract.json`.
- Carry `task_semantics_contract.json` lifecycle: offered == admitted + gate_rejected + capacity_rejected; forwarded is path event; deadline_success is distinct from returned — IMPLEMENTATION-VERIFIED FACT.
- Preserve exact dependency standings (Lane 09 MIXED; S-035 content-only).

**Trace anchors:** `dissertation_traceability.md:TT-REQ-010,011`.

**Gap carried:** TT-REQ-011 P1 (boundary probe missing + wording fix) — EXTERNAL DECISION REQUIRED.

### Ch7 — Discussion and Limits

**Resident requirements:** TT-REQ-013 (ethics, NOT_APPLICABLE trigger not observed) + cross-cutting limits aggregation — SOURCE-DERIVED FACT.

**Narrative purpose:**

- Aggregate every PARTIALLY_MET and NOT_APPLICABLE as explicit limitations with gap IDs (P0/P1/P3) — IMPLEMENTATION-VERIFIED FACT; see `limitations_register.md`.
- List all seven external decisions (ED-001 through ED-007) without resolving them — EXTERNAL DECISION REQUIRED.
- State what is not claimed (no FULLY ALIGNED, no inferred provenance, no mandatory A/B/C) and why — SOURCE-DERIVED FACT honesty boundaries.
- For TT-REQ-013, state trigger not observed, gate must reopen before any human-participant/personal-data activity — SOURCE-DERIVED FACT; MUST arithmetic 3+7+1 preserved.

**Trace anchors:** `dissertation_traceability.md:TT-REQ-013`; `limitations_register.md`; `stakeholder_decision_register.json`.

### Ch8 — Conclusions answering each RQ

**Resident requirements:** Conclusions closing the loop on Ch1 RQs and every TT-REQ that has an evaluation question — SOURCE-DERIVED FACT.

**Narrative purpose:**

- Restate the declared research questions (as in `dissertation_traceability.md` ED-001) — PROVISIONAL_PENDING_SANDRA until RQ set confirmed.
- Provide one conclusion per RQ, each labelled SUPPORTED / INSUFFICIENT EVIDENCE / NOT ASSESSED relative to the evidence cited — SOURCE-DERIVED FACT (TT-REQ-006).
- Do not exceed what the evidence demonstrates; negative results and confounders reported — SOURCE-DERIVED FACT (TT-REQ-006).
- Honestly bound each conclusion to its evidence hash (service, strategy, scenario, run) — RESEARCH-EVIDENCE FACT / IMPLEMENTATION-VERIFIED FACT.
- No conclusion presents a requested investigation A/B/C as executed without the comparison being run and confirmed — PROVISIONAL WORDING.

**Trace anchors:** `dissertation_traceability.md:Ch8` cross-references; `contribution_statement.md` for what is claimed as contribution vs inference.

## 3. Provenance and honesty footer

- Every chapter header in the final manuscript must carry its resident requirement IDs and honesty label for each material sentence.
- Historical campaign artifacts are cited by SHA-256 of committed JSON, not by republished raw outputs — RESEARCH-EVIDENCE FACT.
- The manuscript remains a complete unapproved draft until Sandra confirms the RQ/strategy-family/service-confirmation decisions and the assessors accept submission — EXTERNAL DECISION REQUIRED.
- Validation command: `uv run --frozen python scripts/validate_v08_dissertation_traceability.py` checks that every TT-REQ appears once, every chapter reference resolves to §2 above, no chapter/section introduces an unmastered ID (trace downstream and restructure plan both checked), and every product entry point exists.

*No SUMO, VEC, evaluator, or E-series experiment is launched by this plan. No email or GitHub write is performed.*
