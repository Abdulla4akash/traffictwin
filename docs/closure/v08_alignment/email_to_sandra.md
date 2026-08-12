# Email to Sandra — Confirmation Request (DRAFT — DO NOT SEND WITHOUT REVIEW)

**Status: DRAFT / NOT EFFECTIVE — PROVISIONAL_PENDING_SANDRA**
**Base: bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6**
**Packet ref: docs/closure/v08_alignment/stakeholder_confirmation_packet.md**

Subject: Request for confirmation — final use cases, RSU investigations, and mandatory RQs/deliverables (v08 closure)

Dear Sandra,

I am writing to request explicit confirmation on five points that remain EXTERNAL DECISION REQUIRED before the v08 requirements can be considered closed. The full decision packet is attached for reference and remains DRAFT / NOT EFFECTIVE until you reply. No approval or amendment is claimed in this message.

**SOURCE-DERIVED FACT:** This request draws on the Project 237 brief (S-001), your direct email body (S-035, SHA-256 `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed`), and the frozen baseline Negotiated Version 1 (payload SHA-256 `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`).

**PROVISIONAL_PENDING_SANDRA — five neutral questions:**

1. **Final two ITS use cases (SQ-SANDRA-01).** Which artifacts or service definitions should be presented as the final two ITS use cases for the resource-management methodology, and what should each state for purpose, workload/input, resource needs, and QoS outcomes? Are variants within one VEC offloading service acceptable as two use cases, or do you prefer two differentiated services? *(INFERENCE: current audit records capacity regimes, trace regimes, and bus overlays as candidate but not yet defended services.)*

2. **Core-vs-additional infrastructure VEC scheduling (SQ-SANDRA-02).** Should the assessed core be the VEC scheduling comparison, the enabling software, or both, and how should core versus additional infrastructure work be scheduled relative to the bounded platform extension (TT-REQ-014, MAY)? *(SOURCE-DERIVED FACT: S-035 identifies infrastructure load management as a supervisor-identified problem.)*

3. **Sequential per-task least-busy placement (SQ-SANDRA-03).** Is sequential per-task forwarding from the initially selected RSU to the least-busy RSU before queuing the deterministic strategy you would like compared, or would a different trigger, batching, or periodic policy better represent the intended direction? What configuration and authority boundary should be documented? *(PROVISIONAL WORDING — no strategy is presupposed as required.)*

4. **Bounded Manchester demo acceptability (SQ-SANDRA-04).** Would a bounded Manchester demo be acceptable — historical/open-data acquisition with a modelled event district, honestly labelled synthetic task/RSU demand, and no claim of real-time city-wide VEC validation — and what Manchester, real-data, and SUMO boundary should apply? *(IMPLEMENTATION-VERIFIED FACT: current product shows synthetic/Manchester-parsers as foundation-only for live twin.)*

5. **Exact mandatory RQs and deliverables (SQ-SANDRA-05).** Which research questions are mandatory for assessment, and what are the exact mandatory deliverables that must be closed? Does the comparative RSU investigation (TT-REQ-008, SHOULD) remain SHOULD or should it be considered mandatory for this submission, and which of the three requested investigations should be in scope: (A) DRL + deterministic (Kubernetes) balancing, (B) DRL + DRL scheduling, (C) DRL + AI-based infrastructure control? *(All three are classified as requested investigation / proposed direction / hypothesised outcome, not mandatory assessed implementation without your confirmation.)*

All questions are `PROVISIONAL_PENDING_SANDRA` and do not presuppose any answer. A brief reply confirming or correcting any of the five points — or directing that no change is needed — will be recorded as a new source with a new hash and will trigger a proper baseline amendment only after independent review.

Thank you for your guidance.

Kind regards,
Abdulla

---
*This draft has not been sent. It references the packet and the proposed amendment v2, both marked DRAFT / NOT EFFECTIVE.*
