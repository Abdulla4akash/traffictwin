# COMP66060 Dissertation Readiness and Writing Authority — 19 August 2026

**Status:** current dissertation-planning authority for TrafficTwin agents.

**Source:** the user-supplied **COMP66060 Master Project Rubric** received on 19 August 2026, together with the frozen TrafficTwin E0–E2d scientific record and the current TrafficTwin product evidence.

**Purpose:** state what can be written now as near-final dissertation prose, what must remain provisional, how the report should be structured, and which claims are allowed. This document is about the MSc report. It does not authorise a new scientific campaign.

---

## 1. Binding rubric facts

The report is **85% of the overall project grade** and the video is **15%**.

Within the report assessment, the rubric weights are:

| Criterion | Weight within report assessment |
|---|---:|
| Abstract | 5% |
| Introductory Material | 20% |
| Methodology | 20% |
| Evaluation and/or Reflection | 20% |
| Conclusion | 10% |
| Format and Structure | 5% |
| Project Achievement | 20% |

The report should be about **8,000 words**. Work significantly outside **7,000–9,000 words** is penalised. References, appendices, and figure/table/diagram captions are excluded from the word count.

The rubric explicitly says:

- there is **no separate Background section** in the new format;
- the Introduction must establish the subject area and contain a **concise literature review**;
- the literature review should favour **depth over breadth** and include only the key works needed to understand the problem and justify the approach;
- every project must have separate **Abstract** and **Conclusion** sections;
- Methodology must explain what was done, justify why the methods were suitable, and consider alternatives;
- Evaluation/Reflection must be aligned with the project goals and justify the chosen tests and evidence;
- Project Achievement is judged through complexity, scope, implementation quality, reliability, and technical accuracy.

The video must be **6–8 minutes** and must complement rather than merely repeat the report. It should use the medium to show software, animation, interactive visualisation, or another aspect that text cannot communicate as effectively.

---

## 2. Current readiness verdict

### Report readiness

Approximately **80–85% of the report content can be written now at near-final quality**.

This is not a rough project-proposal stage. The core scientific and technical evidence already exists:

- E0 evaluator/accounting validation;
- E1 waiting-room-capacity study, with an inconclusive primary result;
- E2 placement pilot;
- E2b placement/admission decomposition;
- E2c four-draw common-target replication;
- E2d per-task sequential placement and direction reversal;
- exact commits, manifests, checksums, raw-evidence records, and public compact evidence;
- a substantial TrafficTwin software artefact with deterministic diagnostics, provenance, What-If workflows, Analyst, Next Investigation, and related platform surfaces.

No additional experiment is required before writing begins. Any later staleness, forwarding-cost, or cross-trace study must be treated as an additive extension. It must not block the core E0–E2d report.

### Video readiness

The video can be **planned and scripted now**, but should not be treated as final until the report structure, final main branch, and final product demonstration path are fixed.

---

## 3. Rubric-by-rubric writing readiness

| Rubric criterion | Readiness now | Writing status | What can be completed now | What remains provisional |
|---|---:|---|---|---|
| **Abstract — 5%** | 20–30% | **Partial stretch** | Draft a compact skeleton covering problem, layered method, E0–E2d progression, and direction reversal. | Final wording, final result set, final contribution sentence, and any new extension. Write last. |
| **Introductory Material — 20%** | 90–95% | **Full stretch** | Problem importance; ITS/VEC context; layered MAPPO/infrastructure architecture; concise literature review; gap; aim; objectives; research questions; contribution and scope. | Minor final edits if a new experiment is added. |
| **Methodology — 20%** | 100% | **Full stretch** | Architecture, trace, frozen actor, task model, ingress/execution distinction, queue/admission semantics, metrics, replication unit, statistics, controls, E0–E2d designs, provenance, validation gates, alternatives and method justification. | Nothing essential. A later experiment would be an additional subsection. |
| **Evaluation and/or Reflection — 20%** | 85–95% | **Full stretch for E0–E2d; partial only for extensions** | Complete E0–E2d evaluation, mechanism evidence, paired effects, rejections, workload balance, forwarding, limitations, why results changed, critical reflection on design evolution. | Results and interpretation of any new experiment. |
| **Conclusion — 10%** | 60–70% | **Partial stretch** | Draft the bounded E0–E2d conclusion, objective-by-objective answer, limitations, and evidence-supported contribution. | Final prioritisation of future work and final synthesis after the experiment decision. |
| **Format and Structure — 5%** | 55–70% | **Partial stretch** | Create the final section hierarchy, bibliography system, figure/table numbering, notation table, acronym policy, cross-reference conventions, and word budget. | Final pagination, consistency pass, reference audit, caption check, and proofread. |
| **Project Achievement — 20%** | 90–95% | **Full stretch** | Explain the artefact’s scope, architecture, implementation complexity, evaluator repair, reproducibility, testing, reliability, technical accuracy, platform workflow, and independent validation. | Final product SHA, final screenshots, final video demo, and any last integrated feature. |

### Weighted interpretation

The highest-value rubric areas—Introductory Material, Methodology, Evaluation/Reflection, and Project Achievement—are already mostly or fully writable. Together they account for **80% of the report assessment**. The remaining incompleteness is concentrated in the Abstract, final Conclusion, final formatting pass, and optional new-experiment material.

---

## 4. Recommended report structure

Do **not** create a separate Background chapter. Use the rubric-compatible structure below.

## Abstract

Write last. Target approximately **250–300 words**.

It must state:

- the problem;
- the TrafficTwin approach;
- the frozen actor/infrastructure separation;
- the evaluator/accounting contribution;
- the common-target versus per-task direction reversal;
- the bounded conclusion.

## 1. Introduction and Concise Related Work

Target approximately **1,300–1,600 words**.

Include:

1. ITS and VEC motivation;
2. deadline-sensitive vehicle tasks and overloaded RSUs;
3. why Local/V2V/V2I mode choice must be separated from execution placement;
4. why waiting-room capacity, compute service, admission, forwarding, and placement are different constructs;
5. concise literature review covering only the closest work needed to justify the gap;
6. project aim and objectives;
7. research questions;
8. contributions;
9. scope and nonclaims;
10. report structure.

The literature story must not claim that hierarchical control, least-busy scheduling, forwarding, admission, or rejection accounting are individually new. The defensible gap is the combined, matched, conservation-checked construct-validity result.

## 2. Methodology and TrafficTwin System Design

Target approximately **2,000–2,300 words**.

Include:

1. layered architecture;
2. MAPPO responsibility and frozen action space;
3. V2I ingress and execution identity;
4. V2V helper selection and Randy’s confirmed decision cadence;
5. evaluator and trace;
6. task, deadline, queue, service, and admission semantics;
7. offered/admitted/rejected lifecycle;
8. primary and secondary metrics;
9. replication unit and statistical plan;
10. E0–E2d experimental progression;
11. common-target and per-task algorithms;
12. worked scheduling example requested by Sandra;
13. source identities, manifests, checksums, and validation gates;
14. alternatives considered and why the chosen methods were suitable.

This section should use diagrams, operational pseudocode, and a compact experiment table.

## 3. Evaluation, Results, and Critical Reflection

Target approximately **3,000–3,300 words**.

Include:

1. E0 measurement foundation;
2. E1 queue-capacity result and the queue-versus-service distinction;
3. E2 pilot and the “balanced but worse” puzzle;
4. E2b placement/admission decomposition;
5. E2c common-target replication;
6. implementation audit;
7. E2d per-task algorithm and validation;
8. primary and secondary paired effects;
9. mechanism evidence: rejections, queues, execution shares, forwarding, target switches, workload conservation, and latency;
10. comparison with the closest literature;
11. critical reflection on how the research direction changed;
12. limitations and threats to validity;
13. optional additive extension, only if completed.

The central scientific message is:

> Two operational implementations carrying the same broad least-busy label produced opposite deadline-performance conclusions under matched controls. Scheduler labels are not sufficient descriptions of scheduler semantics.

## 4. Conclusion and Future Work

Target approximately **650–800 words**.

Include:

1. answer each objective and research question;
2. summarise the E0–E2d contribution;
3. state the direction reversal precisely;
4. explain the methodological and software contribution;
5. state limitations honestly;
6. rank future work, including state staleness, forwarding cost, cross-trace replication, per-task MAPPO decisions, action masking, and V2V helper selection;
7. avoid turning future work into unsupported findings.

## Appendices

Use appendices for:

- full parameter and experiment tables;
- exact commit/manifest/checksum ledger;
- additional plots;
- detailed validation gates;
- command examples;
- extended architecture tables;
- public-repository mapping;
- any material needed for auditability but not central to the 8,000-word narrative.

---

## 5. Suggested word budget

| Section | Suggested words |
|---|---:|
| Abstract | 250–300 |
| Introduction and concise related work | 1,300–1,600 |
| Methodology and system design | 2,000–2,300 |
| Evaluation, results, and critical reflection | 3,000–3,300 |
| Conclusion and future work | 650–800 |
| **Indicative total** | **7,200–8,300** |

This leaves a safe margin inside the rubric’s 7,000–9,000 range.

---

## 6. Sections that must be written now at full stretch

Agents must draft these as proper academic prose now, not as placeholders:

1. **Introduction context and motivation**
2. **Concise literature review and gap**
3. **Aim, objectives, and E0–E2d research questions**
4. **Layered TrafficTwin architecture**
5. **MAPPO, V2I, V2V, ingress, execution, admission, queue, forwarding, and service semantics**
6. **Complete methodology and experimental design**
7. **E0 results and measurement foundation**
8. **E1 method, inconclusive primary result, and secondary mechanism pattern**
9. **E2 and E2b decomposition**
10. **E2c common-target result and implementation discovery**
11. **E2d per-task result and mechanism evidence**
12. **Worked common-target versus per-task example**
13. **Reproducibility, exact identities, manifests, and checksums**
14. **Project achievement: artefact complexity, implementation quality, reliability, and testing**
15. **Current limitations and threats to validity**

---

## 7. Sections that must remain partial or provisional

1. **Abstract** — write last.
2. **Final conclusion wording** — draft now, finalise after the experiment decision.
3. **Any staleness result** — no result exists yet.
4. **Any forwarding-cost robustness result** — no result exists until equivalence checks and analysis pass.
5. **Any cross-trace generalisation result** — no result exists yet.
6. **Final future-work order** — depends on what is actually completed.
7. **Final screenshots, demo path, and video** — depends on the final product head.
8. **Final format and reference audit** — complete after prose stabilises.

A provisional subsection must be visibly marked during drafting. It must not contain invented numbers, conclusions, or implied execution.

---

## 8. Claim boundaries that agents must preserve

Agents must not write any of the following as established findings:

- per-task placement tolerates stale RSU state;
- the result generalises to ordinary traffic, another city, or another dataset;
- the advantage survives non-zero forwarding cost;
- the intervention improves physical road traffic, congestion, safety, or travel time;
- a deployed Manchester RSU network would obtain the same result;
- real Kubernetes was implemented;
- E1 demonstrated equivalence, a tie, noninferiority, or proof of no effect;
- common-target least-busy is canonical task-by-task JSQ;
- per-task least-busy is universally superior;
- individual tasks are independent statistical replicates.

Required wording:

- E1: **inconclusive at the available replication size**;
- E2c: **common-target-per-substep least-busy placement**;
- E2d: **per-task sequential least-busy placement** or **per-task sequential shortest-workload placement**;
- replication unit: **fleet draw**;
- implementation: **deterministic infrastructure-side RSU load management** or **Kubernetes-inspired scheduling**, not real Kubernetes deployment.

---

## 9. Project Achievement evidence to foreground

The 20% Project Achievement criterion should not be left implicit. The report must make the following visible:

- a broad TrafficTwin ITS/VEC software artefact rather than a single script;
- repair and validation of offered-task accounting;
- reason-specific rejection and terminal outcomes;
- task and service-work conservation;
- finite queue and admission semantics;
- layered actor/infrastructure design;
- deterministic RSU placement and logical forwarding;
- exact reproducibility records;
- frozen scientific evidence and public compact evidence;
- extensive automated testing and typed models;
- provenance and evidence-standing workflows;
- decision-support and What-If product surfaces;
- bounded LLM features that cannot invent scientific results;
- independent exact-head technical review where applicable;
- honest constraints and fail-closed behaviour.

Project Achievement should be demonstrated through technical evidence in the Methodology and Evaluation sections, not only asserted in the Conclusion.

---

## 10. Video planning note

Although this document prioritises the report, agents must remember that the video is 15% of the overall project grade.

A strong 6–8 minute video should complement the report by showing what prose cannot show as well:

1. a short visual explanation of the layered architecture;
2. a TrafficTwin workflow or live bounded demo;
3. an animation of common-target versus per-task placement;
4. the central paired-result plot;
5. mechanism visualisations such as RSU execution shares or target switching;
6. a short statement of limitations and contribution.

Do not spend the video reading report text over static slides. Use the software, diagrams, and animated scheduling example.

---

## 11. Agent working rules

Before dissertation, report, rubric, or video work, agents must read this file.

Agents must:

1. follow the actual rubric rather than a generic dissertation template;
2. keep the report within 7,000–9,000 words;
3. place concise related work inside the Introduction rather than creating a separate Background chapter;
4. preserve separate Abstract and Conclusion sections;
5. draft full-ready sections immediately;
6. keep future-experiment sections provisional until evidence exists;
7. connect every evaluation to a project objective;
8. justify methods and discuss alternatives;
9. make Project Achievement visible through implementation and reliability evidence;
10. avoid blocking core writing on optional experiments;
11. preserve exact scientific claim boundaries;
12. treat the human owner as final authority over new scientific execution.

---

## 12. Immediate writing order

1. Freeze the report outline and word budget.
2. Write the Introduction and concise related work.
3. Write Methodology and system design.
4. Write the complete E0–E2d evaluation.
5. Add the worked scheduler example and mechanism figures.
6. Write Project Achievement evidence into Methodology/Evaluation.
7. Draft the Discussion/Reflection and limitations.
8. Draft the Conclusion provisionally.
9. Decide whether any additive experiment will be completed.
10. Write the Abstract last.
11. Run the final structure, reference, caption, consistency, and word-count audit.
12. Produce the 6–8 minute complementary video.

The core instruction is:

> **Write the complete E0–E2d dissertation now. Treat any new experiment as an optional additive subsection, not as a prerequisite for beginning or completing the report.**
