# Limitations Register — v08 Requirements Closure (Lane 10)

**Campaign:** `v08-requirements-closure` — Lane `10` — Worker `muse-10`
**Base SHA:** `a244776a2385a2ecb2e0d8f40a15afafaccad8f7`
**Frozen baseline payload:** `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`
**Date:** 2026-08-12

> **Standing banner — SOURCE-DERIVED FACT:** Every limitation below is a PARTIALLY_MET or NOT_APPLICABLE gap from `requirements_status_v08.json` plus its P0/P1/P3 severity and external decision. No gap is hidden. No upward reclassification to MET is claimed. Overall alignment is PARTIALLY ALIGNED — not FULLY ALIGNED. Manuscript is a complete unapproved draft.

## 1. Severity vocabulary

- **P0 — blocks core closure:** TT-002, TT-004, TT-005 — core Project 237 services/assessment/improved-strategy not yet defensibly closed.
- **P1 — substantive gap:** TT-001, TT-003, TT-007, TT-008, TT-011 — methodology/RQ confirmation, profiling reconciliation, video recording, three-arm RSU comparison, RSU-semantics probe.
- **P3 — sequencing/optional:** TT-014 — MAY extension condition "after core/if time" not met.
- **NOT_APPLICABLE (trigger not observed):** TT-013 — no human-participant/personal-data activity in v0.8; gate must reopen — not a waiver.

Validator enforces MUST arithmetic 3+7+1 (never 3+7+0); any P-level promotion without evidence must fail.

## 2. Register — one row per trace requirement (exactly 14)

| ID | Priority | Status | Gap | Severity | Honesty | Remaining action |
|---|---|---|---|---|---|---|
| TT-REQ-001 | MUST | PARTIALLY_MET | Methodology/RQs exist in `dissertation_manuscript_20260801.md` but not supervisor-approved; private-source reproducibility incomplete | P1 | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT | ED-001: obtain one direct Sandra RQ/method confirmation and package permitted artifacts — EXTERNAL DECISION REQUIRED |
| TT-REQ-002 | MUST | PARTIALLY_MET | Capacity arms, trace regimes, bus overlays not yet defended as two distinct ITS services | P0 | IMPLEMENTATION-VERIFIED FACT | ED-001/002: Sandra confirms final two services (A=bounded Manchester current-context, B=deadline-aware VEC) and whether VEC variants qualify — EXTERNAL DECISION REQUIRED |
| TT-REQ-003 | MUST | PARTIALLY_MET | Profiling substantial but not reconciled to final two-service set; only partly reproducible outside private inputs | P1 | RESEARCH-EVIDENCE FACT | Bind profiling to A/B with scenario IDs retained; await RQ confirmation (ED-001) |
| TT-REQ-004 | MUST | PARTIALLY_MET | No complete assessment of named existing strategy families against common QoS criteria | P0 | IMPLEMENTATION-VERIFIED FACT | ED-003: name families and complete suitability table with conditions — EXTERNAL DECISION REQUIRED |
| TT-REQ-005 | MUST | PARTIALLY_MET | B-CAP proposal exists but no admitted adequate QoS/trade-off assessment | P0 | RESEARCH-EVIDENCE FACT | ED-003: close benefit/trade-off evaluation under common scenarios |
| TT-REQ-006 | MUST | VERIFIED_MET | — | — | IMPLEMENTATION-VERIFIED FACT | None (medium-high confidence noted, no reopen) |
| TT-REQ-007 | MUST | PARTIALLY_MET | 8396-word draft + 7:00 storyboard/script exist; no formatted final dissertation or recorded 6–8 min video file | P1 | IMPLEMENTATION-VERIFIED FACT | Record video complementing report; submit per S-003/S-004 |
| TT-REQ-008 | SHOULD | PARTIALLY_MET | S-035 provides direct problem + three requested investigations A/B/C, but no common-scenario three-authority comparison with shared QoS + conditional analysis | P1 | SOURCE-DERIVED FACT + INFERENCE | ED-002: Sandra confirms which of A (DRL+deterministic Kubernetes) / B (DRL+DRL) / C (AI-based Kubernetes) is required; priority remains SHOULD; execute only after confirmation |
| TT-REQ-009 | SHOULD | VERIFIED_MET | — | — | RESEARCH-EVIDENCE FACT | None |
| TT-REQ-010 | MUST | VERIFIED_MET | — | — | IMPLEMENTATION-VERIFIED FACT | Maintain claim accuracy |
| TT-REQ-011 | MUST | PARTIALLY_MET | No targeted capacity−1/capacity/capacity+1 terminal-rejection probe; manuscript per-vehicle wording not reconciled to S-007 | P1 | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT | ED-004: boundary probe + wording correction |
| TT-REQ-012 | MUST | VERIFIED_MET | — (does not prove TfGM/NTIS measured-feed delivery) | — | IMPLEMENTATION-VERIFIED FACT | ED-007 open for any future measured feed |
| TT-REQ-013 | MUST | NOT_APPLICABLE | Trigger not observed (no human-participant/personal-data activity) — must reopen gate before any covered activity; not counted as MET | — | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT | ED-005: University ethics decision before any future covered activity — EXTERNAL DECISION REQUIRED |
| TT-REQ-014 | MAY | PARTIALLY_MET | Bounded synthetic what-if flow exists (SYNTHETIC standing) but sequencing condition not met because P0 cores remain open | P3 | IMPLEMENTATION-VERIFIED FACT | ED-006: confirm whether unseen correspondence changes MAY; otherwise freeze optional growth |

## 3. External decisions — seven, all remain EXTERNAL DECISION REQUIRED

| ED | Maps to | Owner | Decision |
|---|---|---|---|
| ED-001 | TT-001, TT-002 | Sandra | Final RQs/methodology and two-service acceptance |
| ED-002 | TT-008 | Sandra | Full 4 August scope beyond S-035 body; which of A/B/C is required |
| ED-003 | TT-004/005 | Sandra | Strategy-family naming and suitability/trade-off closure |
| ED-004 | TT-011 | Randy/Sandra | Per-vehicle vs per-RSU arithmetic + boundary probe semantics |
| ED-005 | TT-013 | University ethics | Ethics approval/exemption before any human-data activity |
| ED-006 | TT-014 | Sandra | Whether later correspondence changes MAY platform priority |
| ED-007 | TT-012 | TfGM/Sandra | Measured-data delivery not evidenced — academic-mail/tutor-copy follow-up |

No decision is pre-resolved; no amendment is effective until a new primary source is recorded as a new ID/SHA with R1/R2 re-check and a new baseline hash — DRAFT / NOT EFFECTIVE.

## 4. What is explicitly not hidden

- Overall FINAL_AUDIT verdict remains **PARTIALLY ALIGNED** — SOURCE-DERIVED FACT.
- P0/P1/P3 are all visible in `dissertation_traceability.md` §2 and `dissertation_restructure_plan.md` §§2–3.
- Lane 09 remains **MIXED bounded demonstration**, not live-city — SOURCE-DERIVED FACT.
- S-035 remains **DIRECT_SUPERVISOR_SOURCE_BODY** for content only; no inferred timestamp/headers — SOURCE-DERIVED FACT.
- S-035 investigations A/B/C remain **requested investigations / proposed directions / hypothesised outcomes**, not mandatory implementations — PROVISIONAL WORDING.
- No FULLY ALIGNED, Sandra confirmation, final submission, or raw private evidence claim is made — validator rejects any such string.

*Validation: `uv run --frozen python scripts/validate_v08_dissertation_traceability.py` checks every PARTIALLY_MET has named gap + external decision, every P0 appears in limitations, and forbidden claims are absent.*
