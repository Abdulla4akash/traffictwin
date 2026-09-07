# Fable 5.1 suggestions on the complete dissertation draft

| Field | Value |
|---|---|
| Reviewer | Claude Fable 5.1 (`claude-fable-5-1`), interactive Claude Code session |
| Review date | 7 September 2026 |
| Manuscript reviewed | [TrafficTwin_Dissertation.md](TrafficTwin_Dissertation.md) at commit `f91436af2b8f506b400d815947b3a87bda8cd3fd` |
| Evidence baseline | `04f3b6a95c7bc06c80ed95b54762f12861bba183` |
| Rubric | COMP66060 Master Project Rubric, 2025-26 |
| Status | Model-generated review. Not an examiner mark. Not supervisor approval. |

This file gives suggestions only. It does not change the manuscript, the evidence or the evaluator. No simulations were run.

## 1. What was checked

- The full Markdown manuscript, the package receipts, the claim-to-source map, the reference check and the author-input record.
- Every value in Tables 3, 4 and 5 against the archived CSV files. All values match.
- The PDF receipt. It records 23 pages and a passed visual check by the drafting agent.
- The body word count. The package records 7,424 words. An independent count gives 7,755 words under a rule that keeps headings, table cells and evidence labels. Both counts are inside the 7,000 to 9,000 band.
- The size of the artefact on the same branch. Table 1 gives the measured values.
- The E2b manifest caveat at line 291 of `e2b_placement_admission_factorial_manifest_v1_public_sanitized.json`. It exists and the manuscript does not mention it.

*Table 1. Artefact size measured on the reviewed branch. The manuscript states none of these values.*

| Measure | Value |
|---|---|
| UI page files in `src/traffictwin/ui/pages` | 81 |
| Test files under `tests/` | 576 |
| Test functions | 7,048 |
| Lines under `src/traffictwin` | about 270,000 |
| Manuscript mentions of Streamlit or the UI | 1 |
| Test counts stated in the manuscript | 1 (the delay extension only) |

## 2. Estimated marks by criterion

These are estimates from one model reading. They show where the marks are, not what an examiner will give.

| Criterion | Weight | Estimate | Main reason |
|---|---|---|---|
| Abstract | 5% | 62 | Correct, but reads as a ledger of five percentage-point values |
| Introductory Material | 20% | 60 | Eight references, no scheduling literature, no figure, gap not cited |
| Methodology | 20% | 70 | Evaluator semantics are clear and justified; the product is absent |
| Evaluation and Reflection | 20% | 72 | Verified numbers, prespecified replication, clear evidence levels |
| Conclusion | 10% | 68 | Answers each RQ; future work has no citations |
| Format and Structure | 5% | 60 | No front matter yet; equations not numbered |
| Project Achievement | 20% | 57 | The report does not show the artefact or who built what |
| Weighted total | 100% | about 65 | Merit band. Distinction is reachable. |

## 3. What is strong

- The story is single-threaded. Fix the accounting, split capacity from admission, split admission from placement, find the reversal, replicate it, explain it.
- The numbers are correct. The three result tables match the archived CSV files to the last digit.
- Exploratory, prespecified and post-hoc evidence stay apart. The pilot is excluded. The audit is labelled post-hoc. The tie-break test is labelled unrun.
- The methods chapter explains why the actor is frozen and why a black-box comparison would fail. This meets the rubric's request for alternatives.
- Section 2.5 explains the common-target versus per-task distinction with an algorithm and a worked example. This is the core of the result and it is clear.

## 4. Suggestions ranked by grade impact

Each suggestion gives the problem, the evidence, the action and a completion test.

### S1. Show the artefact

**Problem.** Project Achievement is 20% of the mark. The rubric asks how complex the artefact is and how well it is built. The manuscript describes the artefact in three abstract paragraphs in section 3.6. It gives no size, no test count, no page count and no screenshot. The August manuscript at least stated 39 routed views. An examiner who reads only this report sees an experiment on an inherited simulator.

**Action.** Add one table to section 2.2 or section 3.6 with these columns: component, purpose, size, tests, quality gates, role in this result. Include the UI pages, the evidence and provenance layers, the statistics tools, the type-checking and lint gates, and the determinism checks. Add one screenshot figure of the product. Its caption should say how the product exposed the common-target implementation. Budget about 250 words plus the table. Take the words from S5.

**Completion test.** A reader can state the artefact's size, its build quality and its role in the result from the report alone.

### S2. Allocate ownership

**Problem.** The reader cannot tell what Randy built and what the author built. The actor, environment and evaluator base are inherited. The E0 repair, the per-task selector, the delay extension, the forwarding qualification, the mechanism audit and the product are project work. Without this split the examiner cannot credit the project work.

**Action.** Add one contribution table. Rows: MAPPO actor, VEC environment, evaluator base, E0 repair, per-task placement, delay extension, forwarding qualification, mechanism audit, TrafficTwin product, manuscript. Columns: inherited, this project, AI-assisted, needs author confirmation. The queued revision plan already targets this item.

**Completion test.** Every experiment and component in the report has one named origin.

### S3. Add the scheduling literature and cite the gap

**Problem.** Eight references. One survey, one VEC offloading paper, two PPO papers, three RL-evaluation papers and SUMO. There is no reference on join-the-shortest-queue, power-of-d choices, batch dispatch, delayed-information load balancing or deadline-aware admission. The central result is about scheduling semantics, and it has no prior art to sit against. The gap sentence at the end of section 1.2 is internal to the project. The supervisor's rule is that a research gap must carry a citation.

**Action.** Add 6 to 10 primary references on: join-the-shortest-queue and power-of-d choices; load balancing under stale or delayed state; deadline-aware admission control; RSU load balancing in vehicular edge computing; digital twins for intelligent transport. Add one reference that states that implementation detail changes scheduling or MARL conclusions, and attach it to the gap sentence. Keep the total under about 20. The rubric asks for depth, not breadth. The queued revision plan targets the scheduling literature but not the cited gap.

**Completion test.** Section 1.2 ends with a gap sentence that carries a citation. A reader can name the closest prior scheduling work and say how this study differs.

### S4. Add an Introduction figure and the Manchester stakes

**Problem.** The rubric asks for citations and figures in the introductory material. The Introduction has no figure. It never says why a Manchester operator would care about the result.

**Action.** Add one figure: the Manchester scenario map or corridor with the RSU positions for both scenarios. Add two sentences on the real-world stakes of the incident window on 15 March 2024 and the morning window on 15 October 2024, with a citation.

**Completion test.** The Introduction has at least one figure and one cited sentence on real-world stakes.

### S5. Reduce the hedging density

**Problem.** Of 86 prose paragraphs, 55 end on a limitation or a negation. That is 64%. The body has 31 explicit disclaimer phrases and 148 negation tokens, or 19 per 1,000 words. Honest scoping earns marks. This density buries the finding and reads as low confidence.

**Action.** Apply one rule: each results paragraph ends on the finding. Move the limits into section 3.6 or into one limitations table with columns claim, limit, effect on the conclusion. Cut the 31 disclaimer phrases to about 10. Reinvest the words in S1 and S3. Do not delete any limit. Move it.

**Completion test.** Fewer than 30% of prose paragraphs end on a limitation. Every limit that was in the draft still appears once.

### S6. Acknowledge the dropped scope

**Problem.** The skeleton planned a user evaluation strand and numbered objectives. Neither appears. The absence is not stated. Sample reports reward an explicit statement of what was not done and why.

**Action.** In section 1.4, state that a planned user evaluation was not run and give the reason. Optionally add objectives O1 to O5 mapped to the four RQs and revisit them in section 4.

**Completion test.** Every planned strand that was dropped has one sentence in scope.

### S7. Close the format gaps

**Problem.** The Format criterion is 5%. Several items are missing or unnumbered.

**Action.**

- Add the front matter: title page on the University template, contents page ending with `Word count: NNNN`, declaration with an AI-use paragraph, copyright statement, acknowledgements, list of abbreviations.
- Number the equations: the attainment metric, the gate predicate, the conservation identity, the t interval and the aged-report rule.
- End every figure caption with a **Reading:** sentence. The draft has none.
- Add a figure for the incident reversal. Table 3 as a paired-dot plot is enough. The two data figures both show the morning scenario.
- Add the E2b eligibility-timing caveat to section 3.2 in one sentence: the completed `off` arm recorded 138 unavailable V2I attempts out of 13,076,234 offered tasks, so the ingress_dla minus off contrast is not a gate-only effect.
- Give each future-work proposal one citation.

**Completion test.** The PDF re-renders with all front matter, numbered equations and reading sentences, and the validator passes.

### S8. Simplify the Abstract

**Problem.** The Abstract carries five percentage-point values and two interval statements. It reads as a results ledger.

**Action.** Keep at most three numbers: the incident reversal (−2.122 and +0.527 points) and the morning per-task gain (+3.899 points). Replace the rest with plain statements of purpose, method and finding.

**Completion test.** A reader outside the field can say what was done and what was found after one reading.

### S9. Add an experiment roadmap table

**Problem.** The programme has ten stages: E0, E1, E2, E2b, E2c, E2d, the morning pilot, the morning replication, two sensitivities and the audit. The reader must hold all of them in mind from prose. Table 2 lists modes, not experiments.

**Action.** Add one table to section 2.6 with columns: experiment, question, scenario, draws, evidence level, section. Evidence level takes one of validation, exploratory, prespecified, post-hoc, proposed. This table can replace about 150 words of prose.

**Completion test.** A reader can find any experiment's draws, status and section in one table.

## 5. Overlap with the queued revision plan

The uncommitted revision report on branch `docs/dissertation-substantive-revision-2026-09-07` lists seven items. This table shows which suggestions it already covers.

| Suggestion | In the queued plan |
|---|---|
| S1 Show the artefact | No |
| S2 Allocate ownership | Yes |
| S3 Scheduling literature | Partly. The cited gap is not in the plan. |
| S4 Introduction figure and stakes | No |
| S5 Hedging density | No |
| S6 Dropped scope | No |
| S7 Format gaps | Partly. The E2b caveat and PDF checks are in the plan. |
| S8 Abstract | No |
| S9 Roadmap table | No |

## 6. Suggested order of work

1. S1. Highest weight, no new experiments, existing records only.
2. S3. Needs literature search. Start early because reference verification takes time.
3. S5. Frees the word budget for S1 and S3.
4. S9 and S4. Two tables and one figure.
5. S7, S2, S6 and S8. Format and framing. Do these last, then re-render and re-validate the PDF.

All nine suggestions can be completed from existing records. None requires a new simulation, a change to the evaluator or the unrun tie-break test.
