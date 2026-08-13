# Contribution Statement — v08 Requirements Closure (Lane 10)

**Campaign:** `v08-requirements-closure` — Lane `10` — Worker `muse-10`
**Base SHA:** `a244776a2385a2ecb2e0d8f40a15afafaccad8f7`
**Frozen baseline payload:** `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`
**Date:** 2026-08-12

> **Standing banner — SOURCE-DERIVED FACT:** No Sandra confirmation, final/submitted-report, or FULLY ALIGNED claim is made. Every contribution below is tagged as **Software (IMPLEMENTATION-VERIFIED FACT)**, **Scientific evidence (RESEARCH-EVIDENCE FACT)**, or **Inference (INFERENCE)** per lane contract. Provisional claims are **PROVISIONAL WORDING**; open confirmations are **EXTERNAL DECISION REQUIRED**.

## 1. What is claimed — three strictly separated contribution classes

### 1.1 Software contributions — IMPLEMENTATION-VERIFIED FACT at `a244776a`

Observed on the exact prepared base by direct probe or retained committed receipt; not extrapolated from historical campaign numbers.

| Contribution | Binding | Label |
|---|---|---|
| Two service entry points operationalised as product code: (A) bounded Manchester current-context workflow via `src/traffictwin/ui/pages/manchester_evidence_hub.py` and `manchester_operations.py`; (B) deadline-aware VEC dynamic service via `src/traffictwin/integration/tos/` contract/validation and `strategy_matrix.json` families | `use_case_a_manchester_current_twin.md`, `use_case_b_vec_dynamic_service.md`, `manchester_demo/data_contract.json`, `task_semantics_contract.json` | IMPLEMENTATION-VERIFIED FACT |
| Explicit admission/in-flight waiting-room ceiling vs compute service rate separation in TOS evaluator (terminal rejection, no queue entry, no retry/fallback/re-forwarding) | `src/traffictwin/integration/tos/contract.py:160-185`, `task_semantics_contract.json:waiting_room_ceiling` — S-007/S-035 | SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT |
| Provider-condition handling: National Highways and TfGM acquisition paths, licence acknowledgement, restricted feeds fail closed, source/time metadata retained | `src/traffictwin/integration/manchester/national_highways_acquisition.py:175-176`, `tfgm_acquisition.py:262-266`, 102 parser tests | IMPLEMENTATION-VERIFIED FACT |
| Claim-boundary controls: Manchester provider account never presented as real Manchester VEC validation; synthetic/unavailable states preserved with scene_missing/forecast disclaimers | `src/traffictwin/ui/pages/resource_strategy_explorer.py:164-225`, `manchester_demo/` quality_report | IMPLEMENTATION-VERIFIED FACT |
| Bounded synthetic what-if workflow: manual incident → synthetic square (hand-authored, not netconvert) → scenario builder → provenance, with honest synthetic standing | `manchester_demo/data_contract.json:inputs.SYNTHETIC_DATA` | IMPLEMENTATION-VERIFIED FACT (SYNTHETIC) |
| Deterministic infrastructure placement contract: per-task sequential least-busy feasible RSU placement (`argmin(effective_busy_ms)`, gate `effective_busy_ms < TASK_DEADLINE_MS[task_type]`) with pseudocode fingerprint `af128cf...` | `improved_dynamic_strategy_contract.json/md`, `improved_dynamic_strategy_pseudocode.txt` | IMPLEMENTATION-VERIFIED FACT |

### 1.2 Scientific evidence — RESEARCH-EVIDENCE FACT (committed historical campaign, not independently rerun)

Cited only by frozen SHA-256 of committed comparison/manifest JSON; raw private bytes not republished.

| Evidence | Commitment hashes | Label |
|---|---|---|
| Filtration of five Project-237 core gaps and SHOULD/MAY standing (audit) | `FINAL_AUDIT` `0da517b7...`, Negotiated Version 1 payload `58d9b0e7...` | RESEARCH-EVIDENCE FACT via audit record |
| E2b factorial pilot (placement × admission, 1 fleet draw) and E2c matched four-draw common-target result (`dla − ingress_dla` mean −0.021, 95% t interval [−0.0223,−0.0201]) | E2b manifest `9383ec76...` commit `fe2ed4e9...`, E2c manifest `fcaf2ee3...` commit `1a08d6e...` | RESEARCH-EVIDENCE FACT |
| E2d per-task construct-validity study (per-task sequential vs common-target) over four matched fleet draws | E2d manifest `f77afb23...` commit `80e8ae55...` | RESEARCH-EVIDENCE FACT |
| Methodology/RQ documentation and evaluation traces in `docs/dissertation_manuscript_20260801.md` and `docs/dissertation_appendices/objectives_traceability.md` | Manuscript by path/line; campaign records by hash | RESEARCH-EVIDENCE FACT |

Every RESEARCH-EVIDENCE FACT is bounded: Manchester incident hour 2024-03-15 20:00–21:00, provisional uk2030 fleet draws seeds 1–4, 3600 steps, evaluator seed 0, 2.5×/6220-task cap, 1× service, zero backhaul, actor `mappo_modelc_17dim` SHA `93c97059...` — no universal claim.

### 1.3 Inference — INFERENCE (reasoning, explicitly hedged)

| Inference | Why hedged | Label |
|---|---|---|
| That two services A and B satisfy "a few ITS service use cases" for audit purposes | Whether VEC variants qualify as distinct services is an open semantic decision — S-001 ambiguity, ED-001 | INFERENCE + EXTERNAL DECISION REQUIRED |
| That S-035 raises TT-REQ-008 campaign status to PARTIALLY_MET without changing SHOULD priority | Priority change requires a new primary source and baseline re-hash; S-035 does not establish provenance | INFERENCE + PROVISIONAL WORDING; validator checks priority == SHOULD |
| That per-task sequential least-busy placement generalises beyond E2d bound | E2d is four-draw Manchester only; no broader measurement | INFERENCE — must not be presented as RESEARCH-EVIDENCE FACT |

## 2. What is explicitly not claimed

- **No Sandra-confirmed final use cases, RQs, or mandatory investigation scope** — all remain EXTERNAL DECISION REQUIRED (ED-001, ED-002).
- **No live-city deployment or measured general-road-current claim** — Lane 09 is MIXED bounded offline demonstration only — SOURCE-DERIVED FACT dependency standing preserved.
- **No final/submitted dissertation or recorded video** — complete unapproved draft only (8396-word draft + 7:00 storyboard/script) — PROVISIONAL WORDING.
- **No FULLY ALIGNED or universal winner claim** — overall standing is PARTIALLY ALIGNED per FINAL_AUDIT.
- **No raw private VEC outputs republished** — only committed artifact SHAs cited.

## 3. Validation of contribution hygiene

Validator `validate_v08_dissertation_traceability.py` checks:

- Every software entry resolves to a committed file at `a244776a` (probe existence).
- Every scientific-evidence entry cites an exact frozen manifest/commit/SHA (not a bare row count).
- Every inference is labelled INFERENCE and does not masquerade as RESEARCH-EVIDENCE FACT.
- No forbidden claim (Sandra confirmation, final submission, raw bytes, FULLY ALIGNED) appears.

*No email, GitHub write, or experiment launch is performed.*
