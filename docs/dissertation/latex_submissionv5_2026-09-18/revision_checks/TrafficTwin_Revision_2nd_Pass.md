# TrafficTwin — second-pass revision notes

Recorded: 17 September 2026.

These are requested edits for a later revision. The dissertation has not been changed.

## 1. Software testing — appendix only (first-pass Issue 60)

**Requested change:** Remove the main-text discussion of repository software-test failures and the associated generic platform-reliability warning. Keep only a brief, neutral mention of software testing in Appendix A, separate from research-campaign validation. Do not include failure counts or a discussion of failures in that note.

**Locations in the revised TeX:**

- [Main software-testing paragraph, line 1164](/Users/akashx/Desktop/Dissertation/latex_objections_fixed_2026-09-17/TrafficTwin_Dissertation.tex:1164).
- [Concluding platform-reliability sentence, line 1264](/Users/akashx/Desktop/Dissertation/latex_objections_fixed_2026-09-17/TrafficTwin_Dissertation.tex:1264).
- [Appendix A, TrafficTwin product row, line 1759](/Users/akashx/Desktop/Dissertation/latex_objections_fixed_2026-09-17/TrafficTwin_Dissertation.tex:1759).

**Suggested appendix wording:**

> Repository software-testing records are retained separately from the research-campaign validation records.

**Reason:** Keep the scientific results focused on experimental evidence and avoid confusing repository software testing with research simulations.

## 2. Study-selection attribution — LLM brainstorming and subsequent PI discussion (first-pass Issue 55)

**Requested change:** Replace the description of study-design discussions with an AI assistant with brainstorming with large language models (LLMs), followed by discussion with the PI and permission to proceed. Retain the author's literature review, study selection and direction of implementation. This sequence records the author's clarification during the second-pass review.

**Location:** [Declaration, assistance and attribution paragraph, line 145](/Users/akashx/Desktop/Dissertation/latex_objections_fixed_2026-09-17/TrafficTwin_Dissertation.tex:145). Apply the same account wherever the study-selection process is described.

**Suggested wording:**

> Following literature review and brainstorming with large language models (LLMs), and subsequent discussion with my PI and permission to proceed, I selected the follow-up conditions and three-trace study and directed their implementation.

Keep the separate disclosure of coding, drafting and critique assistance accurate; this change concerns the account of research decisions and PI involvement.

## 3. Remove the objectives-outcomes subsection and table (first-pass Issue 63)

**Requested change:** Remove Section 4.1, "Outcomes against the objectives," and its table, "Evidence and remaining limitations against the stated objectives" (`tab:9`). Fold two or three concise sentences into the opening Conclusion paragraph connecting the original objectives to the accounting and scheduling findings, the implemented TrafficTwin functionality, and the remaining limitations, including unevaluated operator benefit. Avoid repeating the detailed research answers that follow.

**Location:** Revised TeX, source blocks 185–186, immediately after the [opening Conclusion paragraph, line 1226](/Users/akashx/Desktop/Dissertation/latex_objections_fixed_2026-09-17/TrafficTwin_Dissertation.tex:1226). Remove the subsection/table labels and their layout commands as appropriate, and update any affected references when implementing the edit.

**Reason:** Reduce repetition and avoid a presentation that resembles a marking checklist, while retaining an evidence-based account of outcomes against objectives. The rubric requires the Conclusion to align with the original objectives (§3.1.5, p. 3); it does not require a separate objectives-outcomes subsection or table.

## 4. Clarify the remaining target-timing wording (first-pass Issue 64)

**Requested change:** Replace the remaining phrase "target timing and reservation visibility" in Section 3.2 with a direct explanation of per-task destination reselection using workloads updated after earlier admissions. The corresponding passage in Section 4.5 was already clarified in the first revision.

**Location:** [Section 3.2, revised TeX line 838](/Users/akashx/Desktop/Dissertation/latex_objections_fixed_2026-09-17/TrafficTwin_Dissertation.tex:838).

**Suggested replacement sentence:**

> I therefore chose a causal per-task implementation to test reselecting the destination for each task using workloads updated after earlier admissions, while keeping the least-workload criterion fixed.

**Reason:** Explain when destinations are reselected and what workload information each decision uses, without suggesting a change to the simulation clock or task service times.
