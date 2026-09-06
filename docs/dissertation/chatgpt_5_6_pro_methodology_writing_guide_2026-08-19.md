# ChatGPT 5.6 Pro Methodology Writing Guide — 19 August 2026

**Status:** current methodology-drafting guidance for the COMP66060 TrafficTwin dissertation.

**Purpose:** define the source pack, evidence hierarchy, drafting workflow, section structure, prompts, figures, checks, and scientific boundaries needed for ChatGPT 5.6 Pro or another dissertation-writing agent to produce the strongest possible Methodology section.

**Authority boundary:** this document governs dissertation drafting. It does not authorise a new scientific campaign, modify frozen E0–E2d evidence, or turn unrun future work into findings.

---

## 1. Rubric contract

The COMP66060 rubric assigns **20% of the report assessment** to Methodology.

The Methodology must:

1. clearly explain the methods used to achieve the project goals;
2. justify why those methods were suitable;
3. compare or contrast relevant alternative approaches;
4. use figures, diagrams, and tables where they improve clarity;
5. remain aligned with the project objectives and the rest of the report.

The report has no separate Background section. Broad related work belongs in the concise literature review inside the Introduction. Methodology may cite literature only where it directly justifies a design choice, metric, statistical method, control, or alternative.

A strong Methodology is therefore not a code dump, chronological lab diary, or second literature review. It must make the experimental logic inspectable:

> **what was done → why it was done → what alternative existed → why the selected method was suitable → what limitation follows**

---

## 2. Does the writer need all Claude, ChatGPT, Gemini, and Fable deep-search outputs?

**No.** The writer does not need every raw deep-search transcript to produce a high-quality Methodology.

The Methodology depends primarily on exact technical evidence:

- frozen source code;
- experiment manifests;
- hashes and provenance;
- approved E0–E2d reports;
- evaluator and trace contracts;
- implementation confirmations from Randy;
- the COMP66060 rubric;
- a small, curated set of primary papers.

Raw Claude, ChatGPT, Gemini, and Fable research reports are useful only as secondary discovery aids. They can help locate papers, recover earlier questions, or identify possible alternatives. They must not outrank the frozen source and experiment record, and they must not be cited as academic evidence when the underlying primary paper is available.

Label raw model-generated research files as:

> **Secondary research notes — useful for discovery, not authoritative scientific evidence and not directly citable.**

Do not upload every transcript into the writing context without curation. Superseded plans and earlier interpretations can cause the writer to blend incompatible versions of the science.

---

## 3. Binding source authority

Use sources in this order:

1. **COMP66060 rubric**
2. **Frozen scientific source code, manifests, hashes, raw-evidence records, and exact experiment contracts**
3. **Approved E0–E2d scientific reports and machine-generated summaries**
4. **Randy’s implementation confirmations**
5. **Current TrafficTwin architecture and dissertation-authority documents**
6. **Primary academic papers**
7. **Consolidated literature matrices and novelty audits**
8. **Raw Claude, ChatGPT, Gemini, Fable, or other model-generated research notes**

When two sources conflict:

- use the higher-ranked source;
- report the conflict;
- do not silently combine incompatible versions;
- do not select the version that produces the strongest claim;
- preserve the exact frozen experiment identity for any result-bearing statement.

Current dissertation-wide authority:

- `docs/dissertation/comp66060_rubric_readiness_2026-08-19.md`

Current future-experiment planning note:

- `docs/evaluation/chatgpt_5_6_pro_suggestions_2026-08-19.md`

---

## 4. Curated methodology source pack

### 4.1 Tier 1 — required authoritative sources

The methodology writer should receive these before drafting.

#### A. Assessment and project scope

1. COMP66060 report/video rubric.
2. Original project brief: **Dynamic Resource Management for Intelligent Transportation System Applications**.
3. `docs/dissertation/comp66060_rubric_readiness_2026-08-19.md`.

#### B. Frozen scientific programme

4. One authoritative E0–E2d scientific summary containing:
   - aim and research questions;
   - experiment progression;
   - arm semantics;
   - metrics and estimands;
   - replication unit;
   - exact results;
   - limitations;
   - terminology.
5. E0, E1, E2b, E2c, and E2d manifests and command ledgers.
6. Exact source, actor, trace, data, environment, and output identities.

#### C. Key source files

7. Frozen actor/training contract showing the Local/V2I/V2V action space.
8. Frozen VEC environment source, including observation and link-selection semantics.
9. Frozen full-hour evaluator source.
10. Per-task E2d placement implementation.
11. E2 instrumentation/accounting code and lifecycle definitions.

#### D. Data and implementation confirmation

12. Manchester incident trace provenance, time window, RSU layout, fleet construction, and access/licence boundaries.
13. Randy’s confirmations that:
   - observation-time and execution-time fast-fading samples are intentionally separate;
   - training uses the same sampling pattern;
   - one MAPPO mode is chosen per active vehicle-second;
   - one operational V2V helper is chosen per vehicle-second;
   - all task arrivals within that second inherit those choices.

#### E. Required terminology

14. Terminology sheet containing at least:
   - **strongest-link ingress execution**;
   - **common-target-per-substep least-busy placement**;
   - **per-task sequential least-busy placement**;
   - **per-task sequential shortest-workload placement**;
   - **offered-task deadline attainment**;
   - **fleet draw** as the independent replication unit;
   - distinct offered/admitted/rejected/forwarded/executed/deadline-success lifecycle concepts.

### 4.2 Tier 2 — useful supporting sources

Use these to improve justification, framing, and diagrams:

- 35-paper literature decision matrix;
- publication-strategy/novelty report;
- 6–10 closest primary papers;
- [Sandra's emails on the layered architecture and scheduler-semantics contribution](../correspondence/sandra_randy_vec_progress_email_thread_2026-08-18.md) (17-18 August 2026; the thread also contains Randy's implementation confirmations on PDF pages 1-2);
- current TrafficTwin architecture diagrams;
- reproducibility, validation, and public-evidence documents;
- exact experiment tables and mechanism plots.

### 4.3 Tier 3 — optional secondary notes

Raw deep-search outputs may remain available for audit, but they should be excluded from the initial drafting context unless needed to answer a specific unresolved question.

---

## 5. Recommended Methodology structure

Target approximately **2,000–2,300 words**.

### 2.1 Research design and methodological principles

Explain:

- applied/experimental systems-research orientation;
- controlled matched comparisons;
- deterministic infrastructure intervention under a frozen learned actor;
- rejection-aware system-level evaluation;
- conservation and provenance as validity requirements;
- why the programme progressed from evaluator validation to mechanism isolation.

### 2.2 Layered TrafficTwin VEC architecture

Define:

- Layer 1: MAPPO mode choice;
- Layer 2A: communication-target selection;
- Layer 2B: V2I execution placement and admission;
- optional/future resource-management layer;
- authority boundaries between these components.

### 2.3 Traffic scenario, trace, and execution environment

Specify:

- Manchester incident trace identity and time window;
- RSU layout;
- fleet draw construction;
- task-arrival and task-type process;
- evaluator seed contract;
- software and hardware environment;
- padding and active-mask semantics;
- data provenance and licence limits.

### 2.4 Frozen MAPPO policy and vehicle-side decision contract

Explain:

- Local/V2I/V2V action space;
- one action per active vehicle-second;
- why the actor was frozen;
- observation contents and limits;
- separate fast-fading samples at observation and execution;
- why this is not a training/evaluation mismatch;
- why execution-RSU choice was not added to the actor.

### 2.5 V2I and V2V target mechanisms

Define:

- strongest-link radio-ingress RSU;
- execution RSU under each experimental arm;
- current V2V helper selection;
- one V2V helper per vehicle-second;
- eligibility and full-queue handling;
- distinction between selected action, eligible target, admission, and completed execution.

### 2.6 Task, queue, service, admission, and lifecycle semantics

Define:

- task types, deadlines, payload, and service work;
- vehicle and RSU queues;
- waiting-room capacity versus compute/service capacity;
- placement versus admission;
- deadline-aware gate;
- finite capacity and rejection;
- logical forwarding;
- offered/admitted/rejected/forwarded/executed/deadline-success states;
- task and service-work conservation.

### 2.7 Experimental progression from E0 to E2d

Use one compact table to explain:

- E0: evaluator/accounting validation;
- E1: waiting-room capacity with fixed service;
- E2: initial placement pilot;
- E2b: placement/admission decomposition;
- E2c: four-draw common-target replication;
- E2d: per-task sequential placement.

The section must explain why each stage was necessary and how findings from one stage changed the next design.

### 2.8 Common-target and per-task placement algorithms

Provide operational pseudocode and the worked example requested by Sandra.

Common-target semantics:

1. inspect the RSU state once per task substep;
2. select one least-busy execution RSU;
3. direct the substep’s eligible V2I candidates towards that common target;
4. do not refresh the target after each candidate.

Per-task semantics:

1. process candidates in fixed order;
2. inspect effective workload/load;
3. choose the minimum-workload RSU;
4. apply radio, deadline, and capacity checks;
5. reserve work only if admitted;
6. update effective state before the next candidate.

### 2.9 Metrics, estimands, and denominators

Define:

- offered-task deadline attainment as the primary system-level outcome;
- admitted-task attainment as a secondary diagnostic;
- reason-specific rejection counts;
- latency, forwarding, target-switch, execution-share, and workload metrics;
- direction of each primary contrast;
- why rejected and unavailable work remains in the offered denominator.

### 2.10 Replication and statistical analysis

Explain:

- fleet draw as the independent unit;
- why millions of tasks are not independent replicates;
- matched paired contrasts;
- mean effect, sample standard deviation, sign pattern, and Student-t 95% interval;
- descriptive mechanism analyses;
- small-n limitations;
- reused-control disclosure where applicable.

### 2.11 Validation, reproducibility, and evidence management

Cover:

- exact source and evidence identities;
- manifests and checksums;
- replay and smoke gates;
- deterministic reruns;
- raw-versus-summary equality;
- task/outcome/work conservation;
- failure and retry policy;
- immutable frozen evidence;
- public compact evidence and private-data limits.

### 2.12 Alternatives considered and methodological boundaries

Discuss why the study did not use:

- joint MAPPO mode-and-RSU learning;
- actor retraining;
- learned V2V helper selection;
- real Kubernetes deployment;
- physical topology-aware forwarding;
- stale-state intervention in E2d;
- task-level significance testing;
- a broad scheduler benchmark.

State the limitations that follow from these choices.

---

## 6. Required figures and tables

The Methodology should include at least the following.

### Figure 1 — layered architecture

```text
Frozen MAPPO actor
        ↓
Local / V2V / V2I
        ↓
communication target
        ↓
infrastructure placement
        ↓
admission
        ↓
execution and lifecycle accounting
```

### Figure 2 — task lifecycle

```text
offered
→ mode selected
→ eligible / unavailable
→ admitted / rejected
→ execution
→ deadline success / deadline miss
```

### Figure 3 — common-target versus per-task worked example

Use a small set of tasks and RSU workloads. Show that the common-target implementation retains one target for the substep, while the per-task implementation updates workload after each admission.

### Table 1 — E0–E2d progression

| Study | Changed factor | Fixed controls | Purpose |
|---|---|---|---|
| E0 | evaluator/accounting | not applicable | establish trustworthy measurement |
| E1 | waiting-room capacity | compute service fixed | separate queue capacity from processing rate |
| E2b | placement × admission | actor and streams fixed | isolate mechanisms |
| E2c | fleet draw | common-target semantics fixed | replicate the negative placement result |
| E2d | dispatch granularity | actor, admission, service, and streams fixed | test per-task placement |

### Table 2 — reproducibility identities

Include:

- TrafficTwin source SHA;
- `vec_env` SHA;
- actor SHA;
- trace/data SHA;
- manifest hash;
- Python/JAX/backend;
- seed and fleet-draw contract;
- raw-evidence location and checksum ledger.

---

## 7. Methodological paragraph pattern

For every important choice, use this five-part structure:

1. **What was done**
2. **Why it was suitable**
3. **What alternative existed**
4. **Why the alternative was not selected**
5. **What limitation follows**

Example:

> The MAPPO actor was frozen across all placement conditions. This isolated downstream infrastructure scheduling from changes in the learned Local/V2I/V2V policy. A joint design in which the actor also selected the execution RSU was possible, but it would have changed both the learned policy and the infrastructure intervention, preventing clean attribution of the paired differences. The resulting conclusions are therefore conditional on the frozen actor rather than claims of end-to-end optimality.

Use this pattern for:

- frozen actor;
- offered-task denominator;
- fleet-draw replication;
- Student-t interval;
- fixed service;
- zero forwarding latency;
- current RSU state;
- deterministic candidate order;
- common-target versus per-task semantics;
- exact reproducibility controls.

---

## 8. Literature use inside Methodology

Methodology should use a **small curated set of approximately 6–10 primary citations**, not the full literature matrix.

Citations should justify only decisions such as:

- layered or hierarchical control;
- batch/per-arrival workload updating;
- deadline-aware admission;
- offered/rejected system evaluation;
- paired small-sample inference;
- reproducible systems experimentation;
- why forwarding and state freshness were held fixed.

Do not claim novelty in Methodology. Novelty belongs primarily in the Introduction and Discussion.

Do not cite Claude, ChatGPT, Gemini, or Fable research reports as academic sources. Cite the primary papers they discovered.

---

## 9. Four-pass drafting workflow

### Pass 1 — evidence map

Before prose, produce a table:

| Subsection | Factual claim | Exact authoritative source | Uncertainty or missing evidence |
|---|---|---|---|

No prose should be accepted until this map is correct.

### Pass 2 — structure and word budget

Approve:

- subsection headings;
- word allocation;
- figure/table placement;
- purpose of each subsection;
- claims that belong elsewhere.

### Pass 3 — subsection drafting

Draft in four blocks:

1. Sections 2.1–2.3;
2. Sections 2.4–2.6;
3. Sections 2.7–2.8;
4. Sections 2.9–2.12.

Then merge, remove repetition, and check transitions.

Do not request the entire 2,300-word section in one unverified generation.

### Pass 4 — adversarial audit

Use a fresh reasoning pass to check:

- unsupported claims;
- incorrect terminology;
- results accidentally placed in Methodology;
- missing rationale;
- missing alternatives;
- task-level pseudoreplication;
- queue capacity confused with service capacity;
- action selection confused with target eligibility or execution;
- ingress confused with execution placement;
- simulated forwarding presented as a physical network;
- frozen scientific source confused with current product `main`;
- citations that do not support the sentence;
- unrun future work presented as completed.

---

## 10. Exact evidence-map prompt

Use this before drafting prose:

```text
You are the technical dissertation methodologist for my University of
Manchester COMP66060 MSc project.

Your task is to help produce the Methodology and TrafficTwin System Design
section of an approximately 8,000-word dissertation.

DO NOT WRITE THE METHODOLOGY PROSE YET.

FIRST produce an evidence map and a proposed section outline.

RUBRIC CONTRACT

The Methodology criterion is 20% of the report assessment. It requires:

1. a clear explanation of the methods used to achieve the project goals;
2. reasoning and justification for why the methods were suitable;
3. comparison with relevant alternative approaches;
4. figures, diagrams, and tables where they improve clarity.

The report has no separate Background chapter. Do not turn this section into
a broad literature review.

SOURCE AUTHORITY

Use sources in this order:

1. COMP66060 rubric;
2. frozen scientific source code, manifests, hashes, and evidence;
3. approved E0–E2d scientific reports;
4. Randy’s implementation confirmations;
5. current TrafficTwin architecture documents;
6. primary academic literature;
7. consolidated literature matrices;
8. raw model-generated research notes.

If two sources conflict, use the higher-ranked source and report the conflict.
Do not silently reconcile incompatible versions.

SCIENTIFIC CONTRACT

Preserve the following:

- MAPPO selects Local, V2I, or V2V only.
- MAPPO does not select the execution RSU.
- The evaluator makes one MAPPO mode choice per active vehicle-second.
- One operational V2V helper is selected per vehicle-second.
- Observation-time and execution-time fast-fading draws are intentionally
  separate.
- V2I radio ingress is distinct from execution placement.
- Waiting-room capacity is distinct from compute/service capacity.
- Placement is distinct from admission.
- Rejected and unavailable tasks remain in the offered-task denominator.
- The statistical replication unit is the fleet draw, not the task.
- E1 is inconclusive at the available replication size.
- E2c uses common-target-per-substep least-busy placement.
- E2d uses per-task sequential least-busy or shortest-workload placement.
- No unrun staleness, forwarding-cost, cross-trace, masking, or retraining
  result may be invented.
- Simulated forwarding is not a physical deployed backhaul.
- Kubernetes-inspired scaling is not a real Kubernetes deployment.

METHOD SECTION TARGET

Propose a structure of approximately 2,000–2,300 words covering:

1. research design;
2. layered architecture;
3. data and scenario;
4. MAPPO decision contract;
5. V2I/V2V target mechanisms;
6. task, queue, service, admission, and lifecycle semantics;
7. E0–E2d experimental progression;
8. common-target and per-task algorithms;
9. metrics and estimands;
10. replication and statistical analysis;
11. validation and reproducibility;
12. alternatives, limitations, and methodological boundaries.

FIRST OUTPUT ONLY

A. Evidence map:
   subsection → factual claims → exact source → uncertainty/missing evidence.

B. Proposed structure:
   subsection headings, word allocation, figures/tables, and purpose.

C. Missing-evidence list:
   anything that must be supplied before drafting.

D. Risk list:
   terms or claims likely to be written incorrectly.

Do not draft prose until I approve this evidence map.
```

---

## 11. Exact drafting prompt

Use this only after approving the evidence map:

```text
The evidence map is approved.

Write the Methodology and TrafficTwin System Design section subsection by
subsection.

For every important methodological choice, explain:

1. what was done;
2. why it was suitable;
3. what alternative was available;
4. why that alternative was not selected;
5. what limitation follows from the choice.

Use formal, precise academic English.

Do not use promotional language.
Do not claim novelty inside Methodology.
Do not report unrun results.
Do not treat individual tasks as independent replicates.
Do not confuse ingress, placement, admission, execution, or deadline success.

Use [CITATION NEEDED: exact topic] only where no supporting primary paper has
been provided. Never invent a citation.

Add explicit placeholders for:

- Figure: layered architecture;
- Figure: task lifecycle;
- Figure: common-target versus per-task example;
- Table: E0–E2d experiment progression;
- Table: reproducibility identities.

Write approximately 2,000–2,300 words.
```

---

## 12. Final acceptance checklist

The Methodology is ready only when all of these are true:

- every factual statement is mapped to an authoritative source;
- the section explains and justifies methods rather than merely naming them;
- alternatives and resulting limitations are explicit;
- the layered architecture is unambiguous;
- action, target, admission, execution, and deadline success are not conflated;
- waiting-room capacity is not presented as compute service;
- E1 remains inconclusive at the available replication size;
- E2c and E2d terminology is exact;
- the fleet draw is the statistical unit;
- no task-level inferential claim appears;
- no unrun result appears;
- no physical deployment claim is inferred from the simulator;
- figures and tables reduce prose burden rather than duplicate it;
- citations point to primary papers or authoritative technical records;
- source identities and reproducibility controls are present;
- the word count remains within the approved methodology budget;
- a fresh adversarial audit has passed.

---

## 13. Agent working rules

Before drafting or reviewing the TrafficTwin Methodology, agents must:

1. read `docs/dissertation/comp66060_rubric_readiness_2026-08-19.md`;
2. read this methodology guide;
3. inspect the exact frozen sources and evidence needed for each claim;
4. build the evidence map before drafting;
5. use raw deep-search outputs only as secondary discovery notes;
6. cite primary papers rather than model-generated reports;
7. preserve the frozen E0–E2d scientific contract;
8. keep optional experiments out of established-results language;
9. stop and report unresolved conflicts rather than inventing a reconciliation;
10. treat the human owner as final authority over structure, wording, and scientific execution.

The core instruction is:

> **The best Methodology comes from exact technical evidence, explicit experimental reasoning, controlled alternatives, and honest limitations—not from giving the writer the largest possible pile of research transcripts.**
