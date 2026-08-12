# Stakeholder Confirmation Packet — v08 Requirements Closure

**Status: DRAFT / NOT EFFECTIVE — PROVISIONAL PENDING STAKEHOLDER DECISION**
**Version: v08-closure-packet-v1**
**Date: 2026-08-12**
**Base: bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6**
**Lane: 02 — Feature: Sandra + Randy confirmation packet**

> **Standing banner:** This packet is DRAFT / NOT EFFECTIVE. No requirement is amended,
> no approval is claimed, and no delivery is asserted until explicit stakeholder
> confirmation is received. Every unresolved item remains EXTERNAL DECISION REQUIRED.

## 1. Purpose and scope

This packet is the smallest decision packet that closes the v08 negotiated-requirements
audit without presupposing any stakeholder answer. It maps the frozen baseline,
the campaign source refresh, and implementation evidence to explicit confirmation asks.

- Frozen baseline: Negotiated Version 1, canonical payload SHA-256
  `58d9b0e7a60fe0bdf00f06ed33c637ad4d764891d8cac8898cf11e4250303595`.
- Final audit: `FINAL_TRAFFICTWIN_V08_AUDIT.md` SHA-256
  `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9`.
- Baseline container: `canonical_baseline_v1.md` SHA-256
  `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2`.

All questions are neutral and do not presuppose their answers.

## 2. Evidence classification legend

Every statement below carries one of:

- **SOURCE-DERIVED FACT** — directly in an A/B primary source.
- **IMPLEMENTATION-VERIFIED FACT** — observed on the exact base SHA via code/probe.
- **RESEARCH-EVIDENCE FACT** — committed historical campaign record, not independently rerun.
- **INFERENCE** — reasoning from evidence, explicitly labelled.
- **PROVISIONAL WORDING** — draft language pending confirmation, tagged
  `PROVISIONAL_PENDING_SANDRA` or `PROVISIONAL_PENDING_RANDY`.
- **EXTERNAL DECISION REQUIRED** — cannot be closed without stakeholder reply.

## 3. Source inventory (verified pre-draft)

| Key | Staged path | SHA-256 | Standing |
|-----|-------------|---------|----------|
| FINAL_AUDIT | `.harness/context/sources/FINAL_AUDIT__FINAL_TRAFFICTWIN_V08_AUDIT.md` | `0da517b76817fd653a6afee4ab0a9dca986e60f299ec54b662066c7d14d5dbb9` | FINAL_NEGOTIATED_REQUIREMENTS_AUDIT |
| NEGOTIATED_V1_WHOLE_FILE | `.harness/context/sources/NEGOTIATED_V1_WHOLE_FILE__canonical_baseline_v1.md` | `732075260bcea1bcb404f97fb47709d4217455459e46801befe90b2103e2afe2` | FROZEN_REQUIREMENTS_BASELINE_CONTAINER |
| AUDIT_SOURCE_INDEX | `.harness/context/sources/AUDIT_SOURCE_INDEX__source_index.md` | `7ce9b43250d8b72e3c1aa9e0bbbc369b251bf7b7aedcae39ea8ed8cdda860d24` | AUDIT_SOURCE_INDEX |
| S-001 | `.harness/context/sources/S-001__Project.pdf` | `d2940e257e455de3f6694d59d66c4d3661471c732618700ad34b4d65240597b0` | PRIMARY_PROJECT_BRIEF |
| S-003 | `.harness/context/sources/S-003__MSc_Report_and_Video_Rubric.pdf` | `c88175e344c8aa0cfd5eba6164a8b5941670c7cc5bb69e89213c6c019bcd8c0f` | ASSESSMENT_RUBRIC |
| S-004 | `.harness/context/sources/S-004__SoE PGT Handbook - Appendices (MSc Advanced Computer Science).pdf` | `df504ec76271f2cb4b2fa34be1f53f55d1363e65d4352456f856a92178d3da82` | ASSESSMENT_PROCESS_SOURCE |
| S-007 | `.harness/context/sources/S-007__MSc Students QnA.docx` | `e8dbbdfa43995870b7e79b8de00dd5e3d73d2988a3846c5bac178bb6b3ab4ec4` | DIRECT_RANDY_QA |
| RESEARCH_AUDIT_SEMANTIC_CONTRACT | `.harness/context/sources/RESEARCH_AUDIT_SEMANTIC_CONTRACT__TrafficTwin_research_audit_2026-08-07.md` | `c7e01197160cb43db5f35bf804e6aa2beae6272a5915a1581369bdf0ec284645` | ORIGINAL_RESEARCH_AUDIT_AND_SEMANTIC_CONTRACT |
| PRODUCT_DESIGN_V2 | `.harness/context/sources/PRODUCT_DESIGN_V2__TrafficTwin_Product_Design_Document_V2.docx` | `f45a9449bab70dde579a35ffe4f8e00eeca25d02ee2f6b68b16583816d524045` | CLASS_D_PRODUCT_DESIGN_PROPOSAL |
| S-035 / SANDRA-DIRECT-BODY-2026-08-04 | `.harness/context/sources/S-035__sandra-direct-email.md` | `08e0fedfedb44c7e9e48ba5a5faf8c6e467d670fdc9d966b7ec11c00c00492ed` | DIRECT_SUPERVISOR_SOURCE_BODY |

- **SOURCE-DERIVED FACT:** S-035 is direct supervisor evidence; it supersedes SRC-010 for overlapping body content only and does not establish timestamp, message-id, transport headers, or Outlook provenance.
- **SOURCE-DERIVED FACT:** The frozen Negotiated Version 1 text and canonical payload hash remain unchanged by S-035.

## 4. S-035 direct body — precise handling

### 4.1 What S-035 supports (SOURCE-DERIVED FACT)

- RSU queue is a waiting-room capacity (default 2.5, reduced to 0.75 in pilot), not compute power.
- Reduced queue can cause fail-fast / rejection-accounting: latency appears reduced while deadline attainment is unchanged.
- The trained vehicle policy has no explicit current RSU load/capacity awareness.
- Load is disproportionate at congested-road RSUs; farther RSUs may remain idle.
- Infrastructure load management is a supervisor-identified problem.

### 4.2 Requested investigations (SOURCE-DERIVED FACT — classified)

Each requested investigation is classified as all four where the body supports them:
supervisor-identified problem, requested investigation, proposed direction, hypothesised outcome.
None is a mandatory assessed implementation without additional authoritative evidence (INFERENCE, EXTERNAL DECISION REQUIRED).

| ID | Investigation as worded in S-035 | Classification | Standing |
|----|-----------------------------------|---------------|----------|
| S-035-A | DRL offloading + deterministic load balancing (Kubernetes load balancing) | supervisor-identified problem; requested investigation; proposed direction; hypothesised outcome = improved task completion in free-flow and congested situations, no retraining required | PROVISIONAL_PENDING_SANDRA — requested investigation, not mandatory deliverable |
| S-035-B | DRL offloading + DRL-based scheduling / load balancing | supervisor-identified problem; requested investigation; proposed direction; hypothesised outcome = improved tasks completion rates | PROVISIONAL_PENDING_SANDRA — requested investigation, not mandatory deliverable |
| S-035-C | DRL offloading + AI-based infrastructure / resource control (AI-based Kubernetes) | supervisor-identified problem; requested investigation; proposed direction; hypothesised outcome = improved tasks completion rates | PROVISIONAL_PENDING_SANDRA — requested investigation, not mandatory deliverable |

- **INFERENCE:** These three are the concrete instantiations of the broader SHOULD direction in TT-REQ-008.
- **PROVISIONAL WORDING:** Any work presenting one of A/B/C as the assessed comparison does so as `PROVISIONAL_PENDING_SANDRA` until Sandra confirms whether it is required, optional, or illustrative.

### 4.3 TT-REQ-008 update (SOURCE-DERIVED FACT + INFERENCE)

- **SOURCE-DERIVED FACT:** S-035 raises direct source confidence for TT-REQ-008's problem statement.
- **INFERENCE, EXTERNAL DECISION REQUIRED:** TT-REQ-008 campaign status is **PARTIALLY_MET** (substantive proposal/problem evidence now direct, but no complete three-arm comparison with supervisor-confirmed scope is admitted). Priority remains **SHOULD**. The frozen requirement is not silently amended; amendment would require a new baseline version and hash via `proposed_requirements_amendment_v2.md` which is DRAFT / NOT EFFECTIVE.

## 5. Sandra confirmation asks (5 explicit, neutral)

All Sandra asks are `PROVISIONAL_PENDING_SANDRA` and `EXTERNAL DECISION REQUIRED`. No question presupposes its answer.

### SQ-SANDRA-01 — Final two ITS use cases

- **Context (SOURCE-DERIVED FACT):** TT-REQ-002 requires a few ITS service use cases; the audit notes capacity regimes, trace regimes, and bus overlays are not yet defended as distinct services.
- **Ask:** Which artifacts or service definitions should be presented as the final two ITS use cases that exercise the resource-management methodology, and what purpose, workload/input, resource needs, and QoS outcomes should each declare? Are variants within one VEC offloading service acceptable as two use cases, or do you require two differentiated services?

### SQ-SANDRA-02 — Core-vs-additional infrastructure VEC scheduling

- **Context (SOURCE-DERIVED FACT + RESEARCH-EVIDENCE FACT):** S-035 identifies infrastructure load management as a problem and requests investigation of edge-side balancing; S-010 demoted the platform to a small extension after core scientific work.
- **Ask:** Should the assessed core be (a) the VEC scheduling / load-management comparison, (b) enabling software, or (c) both? How should core versus additional infrastructure work be scheduled relative to the existing platform extension boundary in TT-REQ-014?

### SQ-SANDRA-03 — Sequential per-task least-busy placement as proposed strategy

- **Context (INFERENCE, PROVISIONAL WORDING):** Deterministic balancing could range from per-task least-busy forwarding to periodic rebalancing.
- **Ask:** Is sequential per-task least-busy placement (each admitted task forwarded from the initially selected RSU to the currently least-busy RSU before queuing) the proposed deterministic strategy you wish to see compared, or would a different trigger, batching, or periodic policy better represent the direction? What configuration and authority boundary should be documented?

### SQ-SANDRA-04 — Bounded Manchester demo acceptability

- **Context (SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT):** TT-REQ-010 and provider records constrain Manchester claims; implementation shows synthetic/Manchester-parsers as foundation-only for live twin.
- **Ask:** Is a bounded Manchester demo acceptable — e.g., historical/open-data acquisition with modelled event-district context, honestly labelled synthetic task/RSU demand, and no claim of real-time city-wide VEC validation — and what Manchester, real-data, or SUMO boundary should apply for the final demonstration?

### SQ-SANDRA-05 — Exact mandatory RQs and deliverables

- **Context (SOURCE-DERIVED FACT):** The dissertation draft contains three working RQs and an O1–O7 traceability map but no supervisor sign-off; TT-REQ-001, TT-REQ-004, TT-REQ-005 remain P0/P1.
- **Ask:** Which research questions are mandatory for assessment, and what are the exact mandatory deliverables (methodology, service use cases, existing-strategy assessment, improved strategy evaluation) that must be closed for the requirements to be considered met? Does TT-REQ-008 (comparative RSU comparison) remain SHOULD or should it be treated as mandatory for this submission?

## 6. Randy confirmation asks (6 explicit, neutral)

All Randy asks are `PROVISIONAL_PENDING_RANDY` and `EXTERNAL DECISION REQUIRED`.

### RQ-RANDY-01 — RSU waiting-room meaning

- **Context (SOURCE-DERIVED FACT):** S-007 defines the per-RSU admission/in-flight waiting-room ceiling as unrelated to processing power.
- **Ask:** Should the project adopt exactly the per-RSU admission/in-flight waiting-room ceiling definition for all code, report, and UI labels, and discard any per-vehicle RSU concurrency ceiling wording? Should configuration be named `rsu_max_concurrent` / `admission ceiling` rather than compute capacity?

### RQ-RANDY-02 — Offered / admitted / rejected denominators

- **Context (SOURCE-DERIVED FACT):** S-007 and S-035 describe immediate rejection when the waiting-room is full.
- **Ask:** For each VEC metric, which denominator should be reported — offered tasks, admitted tasks, or rejected tasks — and how should deadline attainment, latency, and completion rate be defined across those denominators to avoid accounting effects such as fail-fast?

### RQ-RANDY-03 — Deadline after return

- **Context (INFERENCE, EXTERNAL DECISION REQUIRED):** Deadline semantics could be measured at task return to the vehicle versus downstream completion.
- **Ask:** Should deadline compliance be evaluated after return to the requesting vehicle (including any RSU-to-RSU forwarding time), and what deadline interval and return path should be used for common reporting?

### RQ-RANDY-04 — Actor mode-only authority vs downstream RSU selection

- **Context (SOURCE-DERIVED FACT):** S-007 notes radio association once per second and per-task routing+admission; S-035 suggests the agent chooses the best RSU link while infrastructure forwards to quieter RSUs.
- **Ask:** Is the actor's authority limited to mode/offload decision only, with RSU selection handled downstream by the infrastructure/balancer, or does the actor retain RSU-choice authority? How should the boundary between actor decision and RSU selection be documented?

### RQ-RANDY-05 — Gate vs capacity rejection

- **Context (SOURCE-DERIVED FACT + IMPLEMENTATION-VERIFIED FACT):** S-007 describes terminal rejection of surplus tasks outside the queue; product code distinguishes admission ceiling from compute.
- **Ask:** How should gate rejection (e.g., policy/guard) be distinguished from capacity rejection (waiting-room full) in metrics and traces, and should surplus tasks be terminally rejected outside the RSU queue with no retry, fallback, or re-forwarding as the authoritative semantic?

### RQ-RANDY-06 — Authoritative lifecycle fields

- **Context (SOURCE-DERIVED FACT):** S-007 mentions task lifecycle and scheduler fields but leaves ledger scope optional.
- **Ask:** Which lifecycle fields are authoritative for the task record (e.g., offered time, admission time, RSU assignment, queue entry, service start/end, rejection reason, return time), and which fields should be added or remain out of scope for this closure?

## 7. Unresolved stakeholder decisions — frozen seven (Section F)

Every frozen decision maps to at least one explicit ask above and is EXTERNAL DECISION REQUIRED. No decision is claimed resolved.

| ID | Frozen decision (Section F verbatim) | Source class | Decision owner | Current standing | Mapped asks | Provisional tag |
|----|---------------------------------------|--------------|----------------|------------------|-------------|-----------------|
| UD-001 | Final supervisor-approved direction — retrieve Sandra's original 4 August Outlook email, thread, attachments, replies to determine whether comparative RSU load management formally specialised or amended Project 237 | C (S-011, S-012) now partially B via S-035 body only | Sandra | OPEN — body now direct via S-035; headers/thread/attachments still missing; amendment still DRAFT / NOT EFFECTIVE | SQ-SANDRA-01, SQ-SANDRA-02, SQ-SANDRA-05, S-035-A/B/C | PROVISIONAL_PENDING_SANDRA |
| UD-002 | Relationship between research and artefact — confirm whether assessed centre is strategy comparison/result, software that enables it, or both, and how few ITS service use cases obligation is instantiated | A (S-001) + C (S-009–S-012) | Sandra | OPEN | SQ-SANDRA-01, SQ-SANDRA-02, SQ-SANDRA-05 | PROVISIONAL_PENDING_SANDRA |
| UD-003 | Platform priority after Meeting 3 — confirm whether any later direct Sandra instruction restored bounded platform capability above MAY | C (S-010, S-012, S-021, S-022) | Sandra | OPEN — S-035 does not restore platform above MAY | SQ-SANDRA-02, SQ-SANDRA-04 | PROVISIONAL_PENDING_SANDRA |
| UD-004 | Final title and research questions — no signed proposal/title or supervisor-approved RQs found | A (S-003, S-004) + C (S-023, S-027) | Sandra / University assessment | OPEN | SQ-SANDRA-05 | PROVISIONAL_PENDING_SANDRA |
| UD-005 | Manchester, real data, and SUMO claim boundary — confirm which mobility/data layers if any Sandra expects to be real; whether TfGM academic-mail follow-up delivered data; whether SUMO is evaluation method, case-study generator, or optional product component | A (S-005, S-006) + C (S-008–S-011) | Sandra | OPEN | SQ-SANDRA-04 | PROVISIONAL_PENDING_SANDRA |
| UD-006 | User evaluation route — decide whether no user study, expert walkthrough, or formal participant evaluation is expected and obtain ethics/exemption determination before any covered activity | A (S-004) + C (S-009, S-023) | Sandra / University ethics | OPEN | SQ-SANDRA-05 | PROVISIONAL_PENDING_SANDRA |
| UD-007 | Randy artifact permission — if Randy's code, private data, or unpublished results are material, produce primary written grant privately and verify exact citation, data, publication scope | C (S-014, S-034) | Randy / Sandra | OPEN | RQ-RANDY-01, RQ-RANDY-05, RQ-RANDY-06 | PROVISIONAL_PENDING_RANDY |

## 8. Operational questions — audit's eight (Section 14)

These operationalise the seven plus the additional Randy semantics item. All are EXTERNAL DECISION REQUIRED.

| ID | Operational question (Section 14) | Source class | Decision owner | Current standing | Mapped asks | Provisional tag |
|----|------------------------------------|--------------|----------------|------------------|-------------|-----------------|
| OQ-001 | Final approved scientific direction — recover or replace Sandra's 4 August primary email to determine whether comparative RSU load management formally specialised Project 237 and what minimum arms she expects | C→B (body) (S-011, S-012, S-035) | Sandra | OPEN — S-035 body now direct; scope still to confirm | SQ-SANDRA-01, SQ-SANDRA-02, SQ-SANDRA-05 | PROVISIONAL_PENDING_SANDRA |
| OQ-002 | Use-case instantiation — agree which artifacts constitute formal few ITS service use cases and whether variants within one VEC offloading service count | A (S-001) | Sandra | OPEN | SQ-SANDRA-01 | PROVISIONAL_PENDING_SANDRA |
| OQ-003 | Research-versus-artefact centre — confirm whether assessed centre is result, enabling software, or both | A (S-001) | Sandra | OPEN | SQ-SANDRA-02 | PROVISIONAL_PENDING_SANDRA |
| OQ-004 | Platform priority — confirm whether later direct instruction restored bounded platform capability above MAY after Meeting 3 | C (S-010, S-012) | Sandra | OPEN | SQ-SANDRA-02, SQ-SANDRA-04 | PROVISIONAL_PENDING_SANDRA |
| OQ-005 | Final title/RQs — obtain sign-off for current title and three RQs | C (S-023, S-027) | Sandra | OPEN | SQ-SANDRA-05 | PROVISIONAL_PENDING_SANDRA |
| OQ-006 | Manchester/data/SUMO boundary — confirm which mobility/data layers Sandra expects to be real and whether SUMO is evaluation method, generator, or optional component | A (S-005, S-006) + C (S-008–S-011) | Sandra | OPEN | SQ-SANDRA-04 | PROVISIONAL_PENDING_SANDRA |
| OQ-007 | User-evaluation route — decide no study / expert walkthrough / formal evaluation and obtain approval/exemption before covered work | A (S-004) | Sandra / University ethics | OPEN | SQ-SANDRA-05 | PROVISIONAL_PENDING_SANDRA |
| OQ-008 | Randy artifact permission/semantics — privately verify exact permission scope and reconcile per-vehicle/per-RSU arithmetic against S-007 before final claims | B (S-007) + C (S-014, S-034) + S-035 | Randy / Sandra | OPEN | RQ-RANDY-01, RQ-RANDY-05, RQ-RANDY-06 | PROVISIONAL_PENDING_RANDY |

## 9. Investigation vs deliverable boundary

- **SOURCE-DERIVED FACT:** S-035 requests investigation of A, B, and C.
- **INFERENCE, EXTERNAL DECISION REQUIRED:** The project may investigate any subset as a research direction and present results as `PROVISIONAL_PENDING_SANDRA` evidence. No direction becomes a mandatory assessed implementation deliverable without a new primary Sandra confirmation stating that it is required for assessment.
- **RESEARCH-EVIDENCE FACT:** Existing VEC/RSU historical campaigns remain historical project artifacts, not proof of the specific late three-arm comparison.

## 10. Honesty boundaries

- Every material dataset, input, and output remains labelled observed, simulated, synthetic, mixed, or unavailable with provenance (TT-REQ-010).
- No email is claimed sent, received after this packet, approved, or granted permission beyond what the primary sources directly state.
- The packet does not infer missing 4 August Outlook metadata (timestamp, message-id, transport headers) and does not convert requested investigations into implemented deliverables.
- `TrafficTwin_Product_Design_Document_V2.docx` remains Class D proposal evidence, not approval, and cannot amend Negotiated Version 1.

## 11. Next steps — external decisions

All items above remain `EXTERNAL DECISION REQUIRED`. Upon stakeholder reply:

1. Record the exact primary artifact (body, headers, attachments, date) as a new source with a new ID and hash.
2. Promote only the confirmed wording through `proposed_requirements_amendment_v2.md` via a new baseline version and canonical payload hash.
3. Preserve null, adverse, and non-obvious outcomes and keep evidence-state labels explicit.

---

*Packet prepared on the exact base `bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6`.
All changes are DRAFT / NOT EFFECTIVE until stakeholder decision is recorded.*
