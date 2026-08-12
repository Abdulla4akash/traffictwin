# Proposed Requirements Amendment v2 — DRAFT / NOT EFFECTIVE

**Status: DRAFT / NOT EFFECTIVE — NOT AN AMENDMENT UNTIL APPROVED**
**Version: v2-proposal-2026-08-12**
**Base baseline: Negotiated Version 1 — canonical payload SHA-256 `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`**
**Base implementation SHA: `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`**

> This document is DRAFT / NOT EFFECTIVE. It proposes wording for review only.
> It does not amend the frozen baseline, does not change any priority, and does not
> claim approval. All proposals are `PROVISIONAL_PENDING_SANDRA` or
> `PROVISIONAL_PENDING_RANDY` and remain `EXTERNAL DECISION REQUIRED`.

## 1. Amendment standing

- **SOURCE-DERIVED FACT:** Frozen Negotiated Version 1 remains the single source-derived baseline.
- **INFERENCE:** Any amendment requires new source evidence, an explicit amendment reason, independent R1 and R2 re-check, a new version, and a new canonical payload hash. The implementation may not be used to revise the baseline retroactively.
- **PROVISIONAL WORDING:** The proposals below are not effective until all of the above are satisfied and stakeholders explicitly confirm.

## 2. Source basis for proposals

| Source | Hash | Standing | Role in proposal |
|--------|------|----------|-----------------|
| S-035 / SANDRA-DIRECT-BODY-2026-08-04 | `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed` | DIRECT_SUPERVISOR_SOURCE_BODY | Raises confidence for TT-REQ-008 problem statement; does not yet amend priority or wording without confirmation |
| S-007 | `e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4` | DIRECT_RANDY_QA | Authoritative lifecycle/RSU semantics for TT-REQ-011 |
| FINAL_AUDIT | `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9` | FINAL_NEGOTIATED_REQUIREMENTS_AUDIT | Defines 7 frozen decisions and 8 operational questions |

## 3. Proposed amendment — TT-REQ-008 (SHOULD, comparison)

**Current frozen wording (Negotiated Version 1):**

> "TrafficTwin shall, if the late RSU research direction is confirmed, support comparison
> of the existing vehicle-side offloading arrangement with a deterministic/rule-based
> infrastructure-side load-management approach and a separately defined learned
> scheduling/load-management approach, identifying the operating conditions in which
> each approach performs better."

**Proposed v2 wording — DRAFT / NOT EFFECTIVE, PROVISIONAL_PENDING_SANDRA:**

> "TrafficTwin shall, where Sandra confirms the late RSU research direction,
> support comparison of (a) the existing vehicle-side offloading arrangement,
> (b) a deterministic infrastructure-side load-management approach (e.g., sequential
> per-task forwarding from the initially selected RSU to the least-busy RSU), and
> (c) a separately defined learned scheduling / load-management approach, on common
> resource and QoS outcomes under materially different operating conditions (free-flow
> and congested), identifying conditional strengths and limitations rather than a
> single universal winner. The three investigations A/B/C in S-035 are requested
> investigations and hypothesised improvements; none is a mandatory assessed
> implementation without explicit additional confirmation."

**Classification:**

- **SOURCE-DERIVED FACT:** S-035 requests A, B, C as investigations with hypothesised improved completion.
- **INFERENCE:** Each is supervisor-identified problem + requested investigation + proposed direction + hypothesised outcome.
- **PROVISIONAL WORDING / EXTERNAL DECISION REQUIRED:** Whether any of A/B/C becomes required, and whether sequential per-task least-busy placement is the exact deterministic strategy, remains for Sandra to confirm. Priority remains SHOULD until a new primary source explicitly raises it to MUST and the baseline hash is recomputed.

**Amendment trigger:** This wording becomes effective only if Sandra confirms: (i) the RSU comparison is required for assessment, (ii) which of A/B/C are in scope, and (iii) the standing of TT-REQ-014's platform extension.

## 4. Proposed clarification — TT-REQ-011 semantics alignment

**Proposed v2 clarification — DRAFT / NOT EFFECTIVE, PROVISIONAL_PENDING_RANDY:**

- Adopt per-RSU admission/in-flight waiting-room ceiling as the authoritative term;
  reject per-vehicle RSU concurrency ceiling in public/report text.
- Define `rsu_max_concurrent` as waiting + being served, unrelated to compute power.
- Preserve terminal rejection: surplus tasks are rejected outside the RSU queue with no retry, fallback, or re-forwarding.
- Report offered / admitted / rejected denominators explicitly; evaluate deadline compliance after return where confirmed.

This clarification is PROVISIONAL_PENDING_RANDY and EXTERNAL DECISION REQUIRED pending Randy's answers to RQ-RANDY-01 through RQ-RANDY-06.

## 5. TT-REQ-008 standing note

- **INFERENCE:** S-035 raises direct source confidence for TT-REQ-008 and supports campaign status **PARTIALLY_MET**, but does not change its SHOULD priority or silently amend the frozen requirement.
- **EXTERNAL DECISION REQUIRED:** Full closure requires Sandra confirmation of the mandatory RQs/deliverables and the final two ITS use cases.

## 6. Non-amendments

- No change to MUST requirements TT-REQ-001 through TT-REQ-007, TT-REQ-009 through TT-REQ-014.
- No change to the 14 explicitly out-of-scope items (Section E).
- No inference of missing Outlook metadata (timestamp, message-id, transport headers).
- Class D `PRODUCT_DESIGN_V2` remains proposal evidence; Class C S-011/S-012 overlapped body is superseded by S-035 body only.

## 7. Effectiveness gate

This amendment is not effective. A future effective amendment would require:

1. Primary stakeholder reply as a new source with a new ID and SHA-256.
2. Explicit amendment reason referencing that source.
3. Independent R1/R2 re-check.
4. New baseline version and new canonical payload hash.
5. Update to `stakeholder_confirmation_packet.md` and `stakeholder_decision_register.json` reflecting the new standing.

Until then, the frozen baseline governs and this document is retained as DRAFT / NOT EFFECTIVE for reviewer inspection.

## 8. Honesty footer

- Every artifact continues to distinguish SOURCE-DERIVED FACT, IMPLEMENTATION-VERIFIED FACT, RESEARCH-EVIDENCE FACT, INFERENCE, PROVISIONAL WORDING, and EXTERNAL DECISION REQUIRED.
- No reply, approval, delivery, or effective amendment is claimed.
