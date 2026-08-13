# Dissertation Traceability — v08 Requirements Closure (Lane 10)

**Campaign:** `v08-requirements-closure` — Lane `10` — Worker `muse-10`
**Feature:** Dissertation traceability and restructure plan
**Base SHA:** `a244776a2385a2ecb2e0d8f40a15afafaccad8f7` (prepared base containing frozen lanes 01–09)
**Frozen baseline:** Negotiated Version 1 — canonical payload SHA-256 `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`
**Baseline container:** `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2`
**Date:** 2026-08-12

> **Standing banner — SOURCE-DERIVED FACT:** This trace is a complete unapproved draft. It does not claim Sandra confirmation, final/submitted report status, or FULLY ALIGNED standing. The frozen Negotiated Version 1 text and hash remain unchanged. Every statement carries a source-honesty label: **SOURCE-DERIVED FACT**, **IMPLEMENTATION-VERIFIED FACT**, **RESEARCH-EVIDENCE FACT**, **INFERENCE**, **PROVISIONAL WORDING**, **EXTERNAL DECISION REQUIRED**.

## 1. Source authority and hash verification

| Source | Staged path | SHA-256 | Standing |
|---|---|---|---|
| FINAL_AUDIT | `.harness/context/sources/FINAL_AUDIT__FINAL_TRAFFICTWIN_V08_AUDIT.md` | `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9` | FINAL_NEGOTIATED_REQUIREMENTS_AUDIT |
| NEGOTIATED_V1_WHOLE_FILE | `.harness/context/sources/NEGOTIATED_V1_WHOLE_FILE__canonical_baseline_v1.md` | `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` | FROZEN_REQUIREMENTS_BASELINE_CONTAINER |
| NEGOTIATED_V1 canonical payload | (delimited payload) | `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595` | Frozen payload |
| AUDIT_SOURCE_INDEX | `.harness/context/sources/AUDIT_SOURCE_INDEX__source_index.md` | `7ce9b43250d8b72e3c1aa9e0bbbc369b251bf7b7aedcae39ea8ed8cdda860d24` | AUDIT_SOURCE_INDEX |
| S-001 Project brief | `.harness/context/sources/S-001__Project.pdf` | `d2940e257e455de3f6694d59d66c4d3661471c732618700ad34b4d65240597b0` | PRIMARY_PROJECT_BRIEF |
| S-003 Rubric | `.harness/context/sources/S-003__MSc_Report_and_Video_Rubric.pdf` | `c88175e344c8aa0cfd5eba6164a8b5941670c7cc5bb69e89213c6c019bcd8c0f` | ASSESSMENT_RUBRIC |
| S-004 Handbook | `.harness/context/sources/S-004__SoE PGT Handbook - Appendices (MSc Advanced Computer Science).pdf` | `df504ec76271f2cb4b2fa34be1f53f55d1363e65d4352456f856a92178d3da82` | ASSESSMENT_PROCESS_SOURCE |
| S-007 Randy Q&A | `.harness/context/sources/S-007__MSc Students QnA.docx` | `e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4` | DIRECT_RANDY_QA |
| RESEARCH_AUDIT semantic contract | `.harness/context/sources/RESEARCH_AUDIT_SEMANTIC_CONTRACT__TrafficTwin_research_audit_2026-08-07.md` | `c7e01197160cb43db5f35bf804e6aa2beae6272a5915a1581369bdf0ec284645` | ORIGINAL_RESEARCH_AUDIT_AND_SEMANTIC_CONTRACT |
| PRODUCT_DESIGN_V2 | `.harness/context/sources/PRODUCT_DESIGN_V2__TrafficTwin_Product_Design_Document_V2.docx` | `f45a9449bab70dde579a35ffe4f8e00eeca25d02ee2f6b68b16583816d524045` | CLASS_D_PRODUCT_DESIGN_PROPOSAL |
| S-035 / SANDRA-DIRECT-BODY-2026-08-04 | `.harness/context/sources/S-035__sandra-direct-email.md` | `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed` | DIRECT_SUPERVISOR_SOURCE_BODY |

**Dependency standings preserved — SOURCE-DERIVED FACT:**

- Lane 02 frozen with confirmation packet DRAFT / NOT EFFECTIVE; decisions remain open (PROVISIONAL_PENDING_SANDRA/RANDY).
- Lane 09 MIXED — bounded offline Manchester/current-context demonstration, not a live-city deployment or measured general-road-current claim (RESEARCH-EVIDENCE FACT, IMPLEMENTATION-VERIFIED FACT).
- S-035 is direct supervisor body for overlapping 4 August content only; it does not establish timestamp, message-id, transport headers, or Outlook provenance (SOURCE-DERIVED FACT, INFERENCE avoided).
- TT-REQ-008 remains SHOULD with campaign status PARTIALLY_MET (INFERENCE + EXTERNAL DECISION REQUIRED); priority not silently amended.

## 2. Trace master — each requirement appears exactly once

P0 = blocks core closure; P1 = substantive gap; P3 = sequencing/optional; Verbatim canonical quotations are byte-for-byte from `requirements_baseline_v1.json`. Every row carries honesty label and explicit gap.

| ID | Priority | Chapter | Product entry point | Evidence (SOURCE-DERIVED FACT refs) | Status | Limitation | Remaining action | Honesty |
|---|---|---|---|---|---|---|---|---|
| TT-REQ-001 | MUST | Ch1 — Problem and Two Services (methodology) | `docs/dissertation_manuscript_20260801.md:118-135,325-505` | Methodology text; `docs/dissertation_appendices/objectives_traceability.md:1-35`; platform tests/probes passed (I2 §§3.2–3.4) — RESEARCH-EVIDENCE FACT | PARTIALLY_MET | Not supervisor-approved; private-source reproducibility incomplete | ED-001: obtain one direct Sandra RQ/method confirmation and package permitted artifacts — EXTERNAL DECISION REQUIRED | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT; gap P1 |
| TT-REQ-002 | MUST | Ch1 — Problem and Two Services | `docs/closure/v08_alignment/use_case_a_manchester_current_twin.md` (Service A); `docs/closure/v08_alignment/use_case_b_vec_dynamic_service.md` (Service B) | `implementation_i1.md I1-CAP-002,009,014,015`; `docs/evaluation/experiment_catalogue_20260730.md:18-267`; one-click pair generation probes — IMPLEMENTATION-VERIFIED FACT | PARTIALLY_MET | Capacity arms / trace regimes / bus overlays not yet defended as two distinct ITS services each with purpose, workload, resources, QoS | ED-001/ED-002: Sandra confirms final two services are A=bounded Manchester current-context and B=deadline-aware VEC; declare whether VEC variants qualify — EXTERNAL DECISION REQUIRED | SOURCE-DERIVED FACT; gap P0 |
| TT-REQ-003 | MUST | Ch5 — Evaluation | `src/traffictwin/metrics/engine.py:40-151`; `docs/dissertation_manuscript_20260801.md:387-515,516-749` | Direct metrics 63 typed values; historical five-paired-seed/ten-cell records — RESEARCH-EVIDENCE FACT (not independently rerun) | PARTIALLY_MET | Not reconciled to final two-service set; only partly reproducible outside private inputs | Bind profiling to A/B services; retain scenario IDs on every measure — P1; requires methodology confirmation (ED-001) | IMPLEMENTATION-VERIFIED FACT + RESEARCH-EVIDENCE FACT; gap P1 |
| TT-REQ-004 | MUST | Ch2 — Existing Strategies | `src/traffictwin/ui/pages/resource_strategy_explorer.py:164-225`; `docs/closure/v08_alignment/existing_strategy_assessment.md` | Pairwise comparison verified; `strategy_matrix.json` + `strategy_evidence_map.json`; historical actor/capacity comparisons — IMPLEMENTATION-VERIFIED FACT | PARTIALLY_MET | No complete Project-237 assessment of named existing strategy families against declared services and common QoS criteria | ED-003: name families (e.g., strongest-link, JSQ) and complete suitability table with conditions — EXTERNAL DECISION REQUIRED; gap P0 | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT; gap P0 |
| TT-REQ-005 | MUST | Ch3 — Improved Strategy | `docs/closure/v08_alignment/improved_dynamic_strategy_contract.md`; `docs/closure/v08_alignment/improved_dynamic_strategy_contract.json` | B-CAP proposal `docs/evaluation/bcap_training_predeclaration_20260728.md:15-43,70-109`; `improved_strategy_evidence_index.json` E2b-E2d chains — RESEARCH-EVIDENCE FACT | PARTIALLY_MET | No admitted or adequate full QoS/trade-off assessment closes improved-strategy outcome; synthetic smoke only proves plumbing | ED-003: close benefit/trade-off evaluation under common scenarios or justify design-level analysis — gap P0 | RESEARCH-EVIDENCE FACT; gap P0 |
| TT-REQ-006 | MUST | Ch5 — Evaluation | `docs/dissertation_manuscript_20260801.md:118-161,325-515,516-810,820-910`; `docs/dissertation_appendices/objectives_traceability.md:1-84` | 1244 distinct selected tests and direct probes corroborate instrument; claims correctly described as committed evidence — IMPLEMENTATION-VERIFIED FACT | VERIFIED_MET | None — medium-high confidence because private inputs not rerun does not reopen gap | Maintain traceability; no remaining action — SOURCE-DERIVED FACT | IMPLEMENTATION-VERIFIED FACT |
| TT-REQ-007 | MUST | Ch5 — Evaluation (report/video appendix) | `docs/dissertation_manuscript_20260801.md:1-16`; `docs/video_storyboard.md:1-39`; `docs/video_narration_script.md:1-25` | Report/export paths passed; complete 8396-word draft and exact 7:00 storyboard/script — IMPLEMENTATION-VERIFIED FACT | PARTIALLY_MET | No final formatted/submitted dissertation and no recorded 6–8 minute video file | Record video 6–8 min complementing report; submit report per handbook — P1 | IMPLEMENTATION-VERIFIED FACT; gap P1; PROVISIONAL WORDING: storyboard is preparation, not submission |
| TT-REQ-008 | SHOULD | Ch3 — Improved Strategy + Ch5 — Evaluation | `use_case_b_vec_dynamic_service.md` deterministic vs learned; `improved_dynamic_strategy_contract.md` (per-task DLA) | S-035 body SHA `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed` — SOURCE-DERIVED FACT (supervisor-identified problem + requested investigations A/B/C); no three-arm common-scenario comparison executed — IMPLEMENTATION-VERIFIED FACT | PARTIALLY_MET | No common-scenario three-authority comparison with shared QoS metrics and conditional analysis | ED-002: Sandra confirms which of A (DRL+deterministic Kubernetes) / B (DRL+DRL) / C (AI-based Kubernetes) is required; execute comparison only after confirmation — EXTERNAL DECISION REQUIRED; gap P1 | SOURCE-DERIVED FACT + INFERENCE; SHOULD priority unchanged |
| TT-REQ-009 | SHOULD | Ch5 — Evaluation | `docs/dissertation_manuscript_20260801.md:387-515,516-810`; `docs/evaluation/experiment_catalogue_20260730.md:18-267` | Ten-cell/five-pair records with seeds, uncertainty, nulls/refutations — RESEARCH-EVIDENCE FACT | VERIFIED_MET | None — audit did not independently rerun | Maintain varied/controlled reporting for future claims — SOURCE-DERIVED FACT | RESEARCH-EVIDENCE FACT |
| TT-REQ-010 | MUST | Ch6 — Evidence Standing | `src/traffictwin/ui/pages/resource_strategy_explorer.py:164-225`; `docs/dissertation_manuscript_20260801.md:47-61,146-172,749-810` | Direct probes preserved synthetic/unavailable states; Manchester scene_missing and forecast disclaimers — IMPLEMENTATION-VERIFIED FACT | VERIFIED_MET | None | Maintain labels on every Manchester/provider source — SOURCE-DERIVED FACT | IMPLEMENTATION-VERIFIED FACT |
| TT-REQ-011 | MUST | Ch6 — Evidence Standing | `src/traffictwin/integration/tos/contract.py:160-185`; `src/traffictwin/integration/tos/validation.py:215-223`; `task_semantics_contract.json` | TOS/UI tests passed; `task_semantics_contract.json` per-RSU waiting-room ceiling — IMPLEMENTATION-VERIFIED FACT | PARTIALLY_MET | Missing targeted capacity−1/capacity/capacity+1 terminal-rejection/no-queue/no-retry probe; manuscript per-vehicle wording not reconciled to S-007 | ED-004: boundary probe + wording correction per S-007 — P1 | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT; gap P1 |
| TT-REQ-012 | MUST | Ch4 — System and Data Engineering | `src/traffictwin/integration/manchester/national_highways_acquisition.py:175-176`; `src/traffictwin/integration/manchester/tfgm_acquisition.py:262-266`; `src/traffictwin/ui/pages/manchester_operations.py:1558-1560` | 102 provider-parser tests passed; restricted feeds fail closed — IMPLEMENTATION-VERIFIED FACT | VERIFIED_MET | None — VERIFIED_MET does not prove TfGM/NTIS measured-feed delivery | ED-007 remains open for any future measured-feed delivery — EXTERNAL DECISION REQUIRED | IMPLEMENTATION-VERIFIED FACT |
| TT-REQ-013 | MUST | Ch7 — Discussion and Limits | `docs/dissertation_manuscript_20260801.md:163-172,488-505,787-789`; `docs/dissertation_appendices/objectives_traceability.md:57-84` | No human-participant activity observed — SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT | NOT_APPLICABLE | Trigger not observed; must reopen gate before any covered activity — not a waiver, not counted as MET | ED-005: University ethics decision before any future covered activity — EXTERNAL DECISION REQUIRED | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT; MUST arithmetic 3+7+1 preserved |
| TT-REQ-014 | MAY | Ch4 — System and Data Engineering | `docs/closure/v08_alignment/manchester_demo/data_contract.json`; `use_case_a_manchester_current_twin.md` | Bounded synthetic what-if flow probes passed with honest synthetic standing — IMPLEMENTATION-VERIFIED FACT (SYNTHETIC) | PARTIALLY_MET | Sequencing condition "after core/if time" not met because P0 cores (TT-002,004,005) remain open | ED-006: confirm whether unseen later correspondence changes MAY priority; otherwise freeze optional growth — P3 | IMPLEMENTATION-VERIFIED FACT; gap P3 |

**MUST arithmetic — IMPLEMENTATION-VERIFIED FACT:** 3 VERIFIED_MET (TT-006,010,012) + 7 PARTIALLY_MET (TT-001,002,003,004,005,007,011) + 1 NOT_APPLICABLE trigger-not-observed (TT-013) = 11. Never 3+7+0 — validator enforces.

## 3. Downstream narrative cross-references — every reference resolves

All chapter references below resolve to `dissertation_restructure_plan.md` §2. Product entry points resolve to committed files at `a244776a`.

- `dissertation_restructure_plan.md:Ch1` ← TT-REQ-001, TT-REQ-002
- `dissertation_restructure_plan.md:Ch2` ← TT-REQ-004
- `dissertation_restructure_plan.md:Ch3` ← TT-REQ-005, TT-REQ-008
- `dissertation_restructure_plan.md:Ch4` ← TT-REQ-012, TT-REQ-014
- `dissertation_restructure_plan.md:Ch5` ← TT-REQ-003, TT-REQ-006, TT-REQ-007, TT-REQ-008 (evaluation half), TT-REQ-009
- `dissertation_restructure_plan.md:Ch6` ← TT-REQ-010, TT-REQ-011
- `dissertation_restructure_plan.md:Ch7` ← TT-REQ-013 (+ all P0/P1/P3 limits)
- `dissertation_restructure_plan.md:Ch8` ← conclusions answering each RQ (see §4)

- `contribution_statement.md` distinguishes software (IMPLEMENTATION-VERIFIED FACT), scientific evidence (RESEARCH-EVIDENCE FACT), and inference (INFERENCE) — see its §2.
- `limitations_register.md` enumerates every PARTIALLY_MET and NOT_APPLICABLE with gap and external decision — see its §2–§4.

No downstream narrative introduces a requirement ID absent from the master; validator checks `references ⊆ master`.

## 4. Restructure alignment — eight-chapter frame

Follows `dissertation_restructure_plan.md` exactly:

1. **Ch1 Problem and Two Services** — S-001 resource-management problem; two services A (bounded Manchester current-context) and B (deadline-aware VEC) as the operationalisation of "a few ITS service use cases" — PROVISIONAL_PENDING_SANDRA until confirmed.
2. **Ch2 Existing Strategies** — strategy family assessment against common QoS criteria.
3. **Ch3 Improved Strategy** — deterministic placement and learned scheduling directions A/B/C as requested investigations, not mandatory implementations.
4. **Ch4 System and Data Engineering** — bounded Manchester data acquisition, provider licence compliance, synthetic what-if extension (MAY).
5. **Ch5 Evaluation** — methodology justification, run-time profiling, varied controlled scenarios, report/video preparation, comparative RSU evaluation.
6. **Ch6 Evidence Standing** — claim accuracy, real/synthetic separation, RSU semantics (waiting-room vs compute).
7. **Ch7 Discussion and Limits** — P0/P1/P3 register, seven external decisions, honest boundaries.
8. **Ch8 Conclusions answering each RQ** — one conclusion per declared RQ, each tagged SUPPORTED / INSUFFICIENT EVIDENCE / NOT ASSESSED.

## 5. Honesty boundaries

- **No FULLY ALIGNED claim** — current standing is PARTIALLY ALIGNED per FINAL_AUDIT.
- **No Sandra confirmation claimed** — all RQ/method/service-confirmation remains EXTERNAL DECISION REQUIRED.
- **No final/submitted-report claim** — manuscript is a complete unapproved draft (8396-word draft + storyboard, no recorded video) — PROVISIONAL WORDING distinguished from submission.
- **No raw/private evidence publication** — historical campaign records are RESEARCH-EVIDENCE FACTs by hash, not republished raw private bytes.
- **No silent amendment** — frozen baseline quotations preserved byte-for-byte; S-035 raises confidence to PARTIALLY_MET for TT-REQ-008 without changing SHOULD priority.
- **No inferred Outlook metadata** — S-035 body only establishes content, not timestamp/message-id/transport.

## 6. Remaining external decisions (seven, explicit)

| ED | Requirement | Decision owner | Standing |
|---|---|---|---|
| ED-001 | TT-001 | Sandra | EXTERNAL DECISION REQUIRED — final RQs/methodology confirmation |
| ED-002 | TT-008 | Sandra | EXTERNAL DECISION REQUIRED — which of A/B/C is required; S-035 body content only |
| ED-003 | TT-004/005 | Sandra | EXTERNAL DECISION REQUIRED — name strategy families, complete suitability/trade-off table |
| ED-004 | TT-011 | Randy/Sandra | EXTERNAL DECISION REQUIRED — per-vehicle vs per-RSU arithmetic + boundary probe |
| ED-005 | TT-013 | University ethics | EXTERNAL DECISION REQUIRED — ethics gate before any human-data activity |
| ED-006 | TT-014 | Sandra | EXTERNAL DECISION REQUIRED — whether later correspondence changes MAY |
| ED-007 | TT-012 | TfGM/Sandra | EXTERNAL DECISION REQUIRED — measured-data delivery not evidenced |

## 7. Validation

```sh
uv run --frozen python scripts/validate_v08_dissertation_traceability.py
uv run --frozen pytest -q tests/unit/test_validate_v08_dissertation_traceability.py
```

Validator checks: 14 IDs exactly once, no duplication, status and priority match `requirements_status_v08.json` vs `requirements_baseline_v1.json` (TT-REQ-008 SHOULD), P0/P1 visible, chapter references resolve to `dissertation_restructure_plan.md`, every product entry point exists at `a244776a` (trace + contribution), no unmastered TT-REQ ID in downstream or restructure plan, every PARTIALLY_MET has a limitations row with named gap, contribution hygiene (three classes, per-entry frozen hash/path, inference distinctness), prohibited claims absent, honesty labels present, MUST arithmetic 3+7+1 preserved, external decisions explicit. Mutation of one MUST mapping, priority SHOULD→MUST, entry-point path, unknown downstream ID, or PARTIALLY_MET promotion/row removal must fail — restore must pass.

*No SUMO, VEC, evaluator, or E-series experiment is launched. No email or GitHub write is performed.*
