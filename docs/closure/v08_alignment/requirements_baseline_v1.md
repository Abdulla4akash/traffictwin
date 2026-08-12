# TrafficTwin Requirements Baseline — Operationalised Version 1 (v08 Alignment)

**Campaign:** `v08-requirements-closure` · **Lane:** `01` · **Worker:** `muse-01`
**Baseline:** Negotiated Version 1 · **Freeze:** `2026-08-12T15:29:03Z`
**Whole-file SHA-256:** `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2`
**Canonical payload SHA-256:** `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`
**Hash convention:** SHA-256 over exact UTF-8 bytes after `BEGIN CANONICAL PAYLOAD` newline and before `END CANONICAL PAYLOAD` line (delimiters excluded). Recomputed by `scripts/validate_v08_requirements_baseline.py`.
**Implementation target:** `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`

> **Source honesty header — every section below distinguishes:** `SOURCE-DERIVED FACT` (from S-001..S-034 or S-035), `IMPLEMENTATION-VERIFIED FACT` (observed at `bd4570fd`), `RESEARCH-EVIDENCE FACT` (historical campaign artifacts, not independently rerun), `INFERENCE`, `PROVISIONAL WORDING`, and `EXTERNAL DECISION REQUIRED`. No silent baseline amendment; no source inflation.

## 1. Authority and interpretation (SOURCE-DERIVED FACT)

This is the single source-derived baseline for the TrafficTwin v0.8 traceability audit (Negotiated Version 1). It describes negotiated MSc/project obligations that can be defended from accessible evidence; it is not a union of product ideas and does not derive requirements from implementation.

- **S-001** is the only authoritative substantive product scope (Project 237 brief). `S-002–S-004` establish assessment/process duties. `S-005/S-006` establish provider conditions, not data delivery. `S-007` settles only explicitly confirmed technical semantics — per-RSU admission/in-flight waiting-room ceiling vs compute capacity; terminal rejection.
- **Direct supervisor body `S-035 / SANDRA-DIRECT-BODY-2026-08-04`** (staged `.harness/context/sources/S-035__sandra-direct-email.md`, SHA `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`) is verbatim body supplied by Abdulla; it supersedes `SRC-010` for overlapping body content only. It does **not** establish timestamp, message-id, transport headers, or Outlook provenance. The frozen Negotiated Version 1 text and hash remain unchanged. **Never use ambiguous bare identifier `SRC-011`; use exact campaign key `S-035 / SANDRA-DIRECT-BODY-2026-08-04` with path and SHA.**
- Class `D` proposal `TrafficTwin_Product_Design_Document_V2.docx` (`f45a9449…`) and repository features do **not** amend the baseline.
- **Priority:** `MUST` = required by authoritative/confirmed evidence (including explicitly triggered constraints); `SHOULD` = well-supported expected outcome with incomplete authority/scope; `MAY` = optional. Conditional `MUST` evaluated only when its trigger occurs.

**Counts (SOURCE-DERIVED FACT):** 14 IDs — 11 `MUST` (of which 3 trigger-conditional: `TT-REQ-011`, `TT-REQ-012`, `TT-REQ-013`), 2 `SHOULD`, 1 `MAY`. IDs are unique; validator recomputes.

## 2. Canonical requirements (byte-for-byte quotations — SOURCE-DERIVED FACT)

Quotations are frozen from `canonical_baseline_v1.md` and stored identically in `requirements_baseline_v1.json`. Any drift must fail validation.

| ID | Priority | Type | Canonical quotation (exact) |
|---|---|---|---|
| TT-REQ-001 | MUST | PRODUCT OUTCOME | TrafficTwin shall embody and document a suitable, justified methodology for assessing and improving resource management for data-intensive ITS services. |
| TT-REQ-002 | MUST | PRODUCT OUTCOME | TrafficTwin shall design and implement a few ITS service use cases sufficient to exercise the selected resource-management methodology and service-quality questions. |
| TT-REQ-003 | MUST | VALIDATION | TrafficTwin shall support investigation of the run-time profile of its selected data-intensive ITS service use cases, including resource behavior and service-quality outcomes relevant to the research question. |
| TT-REQ-004 | MUST | VALIDATION | TrafficTwin shall support an evidence-based assessment of the suitability of existing cloud, edge, or otherwise applicable resource-management strategies for meeting the requirements and quality-of-service needs of the selected ITS services. |
| TT-REQ-005 | MUST | PRODUCT OUTCOME | TrafficTwin shall support the proposal of one or more improved strategies for dynamic management of storage and/or computing resources across available devices and clouds for ITS data processing and information provision, taking relevant quality-of-service requirements into account. |
| TT-REQ-006 | MUST | VALIDATION | TrafficTwin shall be evaluated, tested, or critically reflected upon using justified methods aligned with the stated project goals, and every material conclusion shall be supported by the resulting evidence. |
| TT-REQ-007 | MUST | OTHER | TrafficTwin shall be presented through the assessed report and a 6–8 minute video that complements the report and appropriately demonstrates or visualises completed work. |
| TT-REQ-008 | SHOULD | VALIDATION | TrafficTwin shall, if the late RSU research direction is confirmed, support comparison of the existing vehicle-side offloading arrangement with a deterministic/rule-based infrastructure-side load-management approach and a separately defined learned scheduling/load-management approach, identifying the operating conditions in which each approach performs better. |
| TT-REQ-009 | SHOULD | VALIDATION | TrafficTwin shall, where comparative or causal claims are made, use sufficiently varied, challenging, and controlled scenarios to expose where resource-management strategies succeed or fail and to address uncertainty or statistical validity. |
| TT-REQ-010 | MUST | QUALITY | TrafficTwin shall make technically accurate, evidence-backed claims and shall explicitly distinguish observed provider data, simulated mobility, and synthetic or assumed task/RSU inputs; it shall not present a Manchester label or provider account as proof of real Manchester VEC validation. |
| TT-REQ-011 | MUST | QUALITY | TrafficTwin shall, whenever it uses Randy's environment or results, distinguish the per-RSU admission/in-flight waiting-room ceiling from compute service rate or worker capacity, preserve terminal rejection of surplus tasks outside the RSU queue, and avoid describing an admission-limit change as a processing-capacity change. |
| TT-REQ-012 | MUST | DATA | TrafficTwin shall, whenever National Highways or TfGM information is used, follow the applicable granted access path and licence conditions, retain sufficient source/time metadata for defensible interpretation, and provide the required source acknowledgement. |
| TT-REQ-013 | MUST | SAFETY | TrafficTwin shall, before any work involving human participants, human issues, or personal data begins, obtain the applicable University ethics approval or confirmed exemption and follow relevant information-governance policy. |
| TT-REQ-014 | MAY | USER WORKFLOW | TrafficTwin shall, if selected after completion of the core scientific work and if time permits, provide a small data-engineering extension that demonstrates a bounded path from honestly identified traffic inputs through retained context and analysis or prediction to a user-defined what-if scenario and decision-support output, using simulation where appropriate. |

**Conditional triggers remain explicit (SOURCE-DERIVED FACT):**

- `TT-REQ-008`: `if the late RSU research direction is confirmed`
- `TT-REQ-009`: `where comparative or causal claims are made`
- `TT-REQ-011`: `whenever it uses Randy's environment or results`
- `TT-REQ-012`: `whenever National Highways or TfGM information is used`
- `TT-REQ-013`: `before any work involving human participants, human issues, or personal data begins`
- `TT-REQ-014`: `if selected after completion of the core scientific work and if time permits`

## 3. Acceptance criteria and named gaps (observable, testable)

Criteria are verbatim from the frozen baseline (see `requirements_baseline_v1.json` for full lists). Every `MUST` has criteria (validator checks). Every `PARTIALLY_MET` carries a named gap; every `VERIFIED_MET` carries no gap; `NOT_APPLICABLE` carries trigger-not-observed justification.

**MUST arithmetic (IMPLEMENTATION-VERIFIED FACT, never 3+7+0):**

- `VERIFIED_MET`: 3 — `TT-REQ-006`, `TT-REQ-010`, `TT-REQ-012`
- `PARTIALLY_MET`: 7 — `TT-REQ-001` (P1: not supervisor-approved/private reproducibility), `TT-REQ-002` (P0: distinct services not reconciled), `TT-REQ-003` (P1: multi-use-case reconciliation), `TT-REQ-004` (P0: no complete strategy-family assessment), `TT-REQ-005` (P0: no adequate QoS/trade-off assessment), `TT-REQ-007` (P1: no recorded video/final submission), `TT-REQ-011` (P1: missing terminal-rejection probe + wording fix)
- `NOT_APPLICABLE` (trigger not observed): 1 — `TT-REQ-013` (no human-participant/personal-data activity in v0.8; must reopen before any covered activity — not a waiver, not counted as MET)
- **Total `MUST`: 3+7+1 = 11.** Any file claiming `3+7+0=11` is a prohibited claim and must fail review.

`SHOULD`: `TT-REQ-009` `VERIFIED_MET` (project-bound campaigns with nulls/refutations), `TT-REQ-008` `PARTIALLY_MET` (P1: three-arm comparison not executed with common metrics). `MAY`: `TT-REQ-014` `PARTIALLY_MET` (P3: sequencing condition not met).

See `requirements_status_v08.json` for per-requirement evidence refs, gap IDs, and `EXTERNAL DECISION REQUIRED` tags.

## 4. S-035 direct body — what it does and does not establish (SOURCE-DERIVED FACT)

**Supports (supervisor-identified problem):**
RSU queue/waiting-room capacity rather than compute power; fail-fast/rejection-accounting explanation for reduced latency; no explicit current RSU load/capacity awareness in trained vehicle policy; disproportionate load at congested-road RSUs while farther RSUs idle; infrastructure load management as supervisor-identified problem.

**Requested investigations (not mandatory implementations):**
(A) DRL offloading + deterministic load balancing (Kubernetes),
(B) DRL offloading + DRL scheduling/load balancing,
(C) DRL offloading + AI-based infrastructure/resource control.

**Classification rule:** each of A/B/C is classified only as `supervisor-identified problem`, `requested investigation`, `proposed direction`, and/or `hypothesised outcome` (improved completion rates) **as the body supports**. Do **not** call any direction a mandatory assessed implementation without additional authoritative evidence. Do **not** infer missing email metadata.

**For `TT-REQ-008`:** S-035 raises direct source confidence and supports campaign status `PARTIALLY_MET`, but does **not** change `SHOULD` priority or silently amend the frozen requirement. The exact workflow hashes above are still recomputed against the frozen payload.

## 5. Source map and honesty boundaries

All source IDs resolve via `requirements_source_map.json` (validator checks). Authoritative SHAs verified at `.harness/context/source_map.json` time. Provisional `Class C` paraphrases (`S-011/S-012`) remain `PROVISIONAL WORDING`; product document `V2` remains `Class D`. Every artifact must not invent sources, inflate standing, or modify the frozen audit `FINAL_TRAFFICTWIN_V08_AUDIT.md`.

**Remaining external decisions (EXTERNAL DECISION REQUIRED):**
ED-001 (TT-001 RQ/method confirmation), ED-002 (TT-008 full direction beyond S-035 body), ED-003 (TT-004/005 strategy-family naming), ED-004 (TT-011 per-vehicle vs per-RSU arithmetic), ED-005 (TT-013 future ethics gate), ED-006 (TT-014 unseen correspondence), ED-007 (TT-012 TfGM delivery). See `requirements_status_v08.json` `external_decisions`.

## 6. Validation

Run:

```sh
uv run --frozen python scripts/validate_v08_requirements_baseline.py
uv run --frozen pytest -q tests/unit/test_validate_v08_requirements_baseline.py
```

Validator recomputes payload hash and count, checks ID uniqueness, all `MUST`s have criteria, every `PARTIALLY_MET` has named gap, every source resolves, status vocabulary closed, quotations no drift, conditional triggers explicit, and `MUST` arithmetic `3+7+1`. Mutation of one quotation/status/source binding must fail; restore must pass.

*No SUMO, VEC, evaluator, or E-series experiment is launched by this baseline. No email or GitHub write is performed.*
