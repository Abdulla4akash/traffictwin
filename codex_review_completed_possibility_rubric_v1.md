# Codex Review — Completed Possibility Rubric v1

**Date:** 26 July 2026

**Branch:** `feature-suggestions`

**Companion review:** `research_directions_codex_review.md`

This rubric answers one practical question: **what can realistically be completed in the remaining
six working weeks, what can only be started conditionally, and what cannot honestly be claimed with
the evidence and software currently available?**

The evidence baseline is `claude/complete-v0.7` / `codex/traffictwin-v0.7` at `7a4a16c`. Literal
machine-specific paths in `claude/complete-v0.7:CURRENT_STATUS_CONTEXT_PROMPT.md` are ignored. The
status and evidence rules in that briefing are retained.

## 1. How to read the rubric

| Rating | Plain-English meaning | Completion rule |
|---|---|---|
| **Can complete now** | The repository already contains the necessary foundation. | Finish it, test it, and retain the required evidence. |
| **Can complete with a gate** | Work can start now, but an external input, human decision, or evidence-chain repair is still required. | Do not call it complete until the named gate passes. |
| **Cannot complete now** | A required data source, model, simulator feature, permission, or accepted workflow does not exist. | Keep it unavailable or defer it; do not simulate certainty. |
| **Do not prioritise** | It is technically possible, but it is unlikely to improve the dissertation enough for the time it consumes. | Do only a tightly bounded fix if it removes a demonstrated blocker. |

“Can complete” means **defensibly complete**, not merely “some code or a screen can be produced.” A
new simulation is not research evidence until its inputs, execution receipt, metrics, and
statistical route are accepted.

## 2. Headline possibility table

| Requested area | Rating | What can be done | What cannot yet be claimed, and why | Recommended treatment |
|---|---|---|---|---|
| **One Manchester bus corridor** | **Can complete with a gate** | Build a tightly bounded corridor case using eligible historical road observations, accepted network geometry, and bus data kept explicitly as bus evidence. | BODS does not represent general road demand. No accepted calibrated Manchester baseline, one-second FCD/network pair, or Manchester VEC chain exists yet. Licence, retention, map-match, calibration, and analyst-acceptance gates still apply (`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`; `claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`; `claude/complete-v0.7:docs/current_workflow_and_todo.md`). | **Stretch goal.** Attempt one corridor only after the experiment evidence chain works. |
| **Alternative static RSU placement** | **Can complete now, within limits** | Supply a compatible one-second FCD/network pair to VEC-06 and let the bounded placement pipeline generate a trace and receipt. | This does not establish real roadside infrastructure, optimal placement, or mobile RSUs. Placement remains a simulated analysis input (`claude/complete-v0.7:docs/integration/vec_fcd_preprocessing.md`; `claude/complete-v0.7:docs/reference/generated/tos_source_contract.json`). | Useful only if it directly supports the main experiment. Keep the scientific wording narrow. |
| **Mobile RSUs** | **Cannot complete now** | A future design and external simulator extension could be specified. | The current evaluator has no mobile-RSU state, motion/control model, radio/propagation model, or admitted policy for it (`claude/complete-v0.7:docs/reference/generated/tos_source_contract.json`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). | Defer beyond this dissertation unless an independently validated environment and policy are supplied. |
| **Tram-mounted RSUs** | **Cannot complete now** | A concept and required evidence list can be documented. | It has the same missing mobile-RSU physics as above, plus no admitted tram trace, placement/control policy, or validation evidence in the repository. | Treat as future work, not a six-week deliverable. |
| **Extra SUMO scene: stadium/event** | **Can complete with a gate** | Author a candidate scene and produce a compatible FCD/network pair. VEC-06 provides a conditional admission route. | The repository contains no accepted stadium scene. A scene is not research evidence until the baseline, FCD, trace admission, execution, metric admission, and statistical chain all pass (`claude/complete-v0.7:docs/integration/vec_fcd_preprocessing.md`; `claude/complete-v0.7:docs/integration/vec_scientific_admission.md`). | Follow-up only. Do not put it on the critical path. |
| **Extra SUMO scene: lane closure** | **Can complete with a gate** | Author a candidate closed-lane scenario outside the evaluator and attempt the same VEC-06 route. | The evaluator has no lane-closure toggle, and existing synthetic lane-clearing fixtures are not Manchester/SUMO validity evidence (`claude/complete-v0.7:docs/reference/generated/tos_source_contract.json`; `claude/complete-v0.7:docs/assumption-register.md`). | Follow-up only, after the main experiment succeeds. |
| **Use all five Manchester traces** | **Can complete with a gate** | The five source trace pairs `wd_am`, `wd_pm`, `ev`, `inc`, and `we` exist. | Only `we` is directly pinned for VEC-07. The other four require an accepted VEC-06 receipt or reviewed allowlist extension; their informal calm/stressed labels are not repository-accepted scientific classes (`claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/service.py`). | Admit only the trace needed for the first study, then expand if time remains. |
| **Capacity-squeeze experiment** | **Can complete with a gate** | The two actors, fleet presets, seeds, `--rsu-cap-per-veh`, and `--max-steps` controls exist. | Fresh VEC-07 runs currently have `scientific_admission: false`; one-click import supplies zero scientific metrics, and there is no accepted batch campaign path (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:docs/integration/vec_one_click_execution.md`; `claude/complete-v0.7:docs/integration/vec_interface.md`). | **Highest research priority**, but repair trace/run/metric admission before scaling the run count. |
| **General UI polish** | **Can complete now, but do not prioritise broadly** | Fix demonstrated first-run, comprehension, navigation, and accessibility problems. The interface has already received substantial candidate presentation work. | Automated browser and UI checks do not complete manual keyboard, screen-reader, contrast, zoom, or participant acceptance (`claude/complete-v0.7:docs/implementation-status.md`; `claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). | Freeze broad redesign. Make only evidence-led fixes that help the study or remove a usability blocker. |
| **Manual accessibility and usability acceptance** | **Can complete with a human gate** | Prepare scripts, recruit, run the agreed checks/study after approval, record findings, and make bounded repairs. | The repository cannot manufacture participant consent, ethics approval, screen-reader evidence, or stakeholder acceptance (`docs/evaluation/ethics_application_draft.md`; `claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). | Start preparation now; keep final acceptance explicitly pending until the human evidence exists. |

## 3. Outstanding v0.7 capability rubric

All 15 formal rows below remain `planned`; candidate or `working_bounded` foundations do not equal
acceptance (`claude/complete-v0.7:docs/implementation-status.md`;
`claude/complete-v0.7:docs/v07_requirement_matrix.md`). The table therefore distinguishes useful
completion work from work that is blocked by external evidence.

| Capability | Possibility in six weeks | What is realistically achievable | Main completion blocker | Priority |
|---|---|---|---|---|
| **MAN-01 — source snapshots** | **Can complete with a gate** | Preserve immutable, provenance-bound eligible snapshots. | Provider terms, licence/retention decisions, and source-specific acceptance must be resolved. | Medium; do only sources needed by the study. |
| **MAN-02 — time basis** | **Can complete with a gate** | Retain explicit UTC anchors and honest unavailable states for bounded sources. | Every admitted source must have an accepted time interpretation; missing time evidence cannot be inferred. | Medium. |
| **MAN-03 — road observations** | **Can complete with a gate** | Use eligible historical DfT/WebTRIS evidence at its true spatial and temporal scope. | Historical observations cannot be relabelled live, Manchester-wide, or complete; uncovered locations remain unavailable. | High if building the corridor; otherwise defer. |
| **MAN-04 — signal infrastructure** | **Can complete with a gate** | Show accepted static signal-location reference data. | The repository has no admitted live signal-state/control feed, so live timing and phase claims are unavailable. | Low unless required by the corridor. |
| **MAN-05 — live transit vehicles** | **Can complete with a gate** | Show bounded, freshness-labelled bus observations with honest stale/unavailable states. | Coverage, membership, retention, redistribution, and provider conditions prevent a guaranteed complete/public feed. | Medium for a bus corridor; not evidence of general traffic. |
| **MAN-06 — Randy/TOS bridge** | **Can complete with a gate** | Retain the permission-safe, sanitised integration and accepted VEC boundaries. | Permission does not authorise raw evidence publication, arbitrary algorithms, or broader claims. | High only for the experiment chain. |
| **MAN-07 — geographic projection** | **Can complete with a gate** | Project evidence whose coordinate system and identity are accepted. | Unknown or incompatible coordinates cannot be guessed; analyst review is still required. | High for a Manchester corridor. |
| **MAN-08 — Manchester Operations** | **Can complete with a gate** | Finish a bounded, honest operations surface over accepted inputs and explicit unavailable states. | It cannot display sources or capabilities that have not passed their own gates. | Medium; avoid broad polish. |
| **MAN-09 — observed-to-SUMO baseline** | **Can complete with a major gate** | Rebuild one viable bounded baseline, then map, calibrate, measure residuals, and obtain analyst acceptance. | The current Manchester demand gridlocks, and no accepted map match, calibrated demand, residual record, or baseline exists (`claude/complete-v0.7:docs/current_workflow_and_todo.md`; `claude/complete-v0.7:docs/v07_alpha7_checkpoint_handoff.md`). | **Critical only if the corridor is pursued.** Otherwise do not let it consume the main experiment window. |
| **MAN-10 — observed/simulated comparison** | **Can complete only after MAN-09** | Compute honest matched-cohort comparison metrics after an accepted observed source and simulated baseline exist. | No accepted production comparison can precede its two accepted parents; missing observations must not become zero. | High after MAN-09; blocked before it. |
| **MAN-11 — Manchester SUMO-to-VEC chain** | **Can complete only after MAN-09/10** | Connect an accepted one-second FCD/network pair through VEC-06–VEC-12 with full lineage. | The accepted Manchester baseline, controlled SUMO receipt, paired FCD/network, and full Manchester VEC execution do not yet exist. | High only for a Manchester-VEC dissertation claim. |
| **UX-01 — grouped navigation** | **Can complete with a human gate** | Candidate grouped navigation and page migration already exist and can receive bounded fixes. | Formal cutover and user acceptance remain outstanding. | Medium. |
| **UX-02 — map-led workflow** | **Can complete with a human gate** | Validate the first-run and research flow with representative users and repair demonstrated problems. | Automated checks cannot substitute for participant comprehension and usability evidence. | High for the user evaluation. |
| **UX-03 — responsive/accessibility quality** | **Can complete with a human gate** | Run keyboard, screen-reader, contrast, zoom, responsive, and participant checks; fix bounded defects. | Manual accessibility and participant evidence have not been supplied. | High for defensible evaluation; keep the scope narrow. |
| **REL-01 — v0.6/v0.7 coexistence and release** | **Can complete with a release gate** | Preserve isolated workspaces and side-by-side compatibility, then reconcile the final package/version state. | Final release reconciliation and acceptance are still outstanding. | Low until the dissertation-critical work is stable. Never move protected release tags. |

## 4. Things that cannot honestly be delivered from the current repository

| Claim or feature | Why it is unavailable now | Honest alternative |
|---|---|---|
| **Live Manchester-wide private-vehicle traffic** | Available bus and historical road sources do not provide a complete live private-vehicle demand feed (`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`). | Say “historical/latest-available bounded observations,” with scope and gaps. |
| **Live traffic-signal phases or control** | Only bounded infrastructure references exist; no admitted live phase/state feed is recorded (`claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). | Display static eligible locations and mark live state unavailable. |
| **Guaranteed complete Bee Network bus coverage** | Provider coverage, membership, freshness, and retention conditions remain explicit limitations (`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`). | Display source-specific freshness and missing/stale states. |
| **Public hosting of unrestricted raw/live data** | Permission and redistribution boundaries allow only bounded, sanitised evidence (`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`; `claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md`). | Publish derived, permission-safe aggregates and provenance where authorised. |
| **Automatic calibration acceptance** | Calibration requires declared targets, residuals, uncertainty, and analyst acceptance; a built network alone is only geometry (`claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). | Automate calculations, then retain an explicit human acceptance gate. |
| **New trained, heuristic, or “dumb” VEC policies** | VEC-07 admits only two pinned actor checkpoints, and VEC-10 excludes training (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:docs/integration/vec_interface.md`). | Request an externally supplied baseline with provenance and permission, then audit it before use. |
| **Scientifically credible mobile/tram RSUs** | Required motion, control, propagation, placement, trace, and policy evidence is absent. | Record the design and validation requirements as future work. |
| **An immediate 20–50-run incident campaign with accepted statistics** | `inc` is not directly pinned, fresh executions are not scientifically admitted, execution is foreground-only, and the request timeout is capped at two hours (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:docs/integration/vec_one_click_execution.md`; `claude/complete-v0.7:docs/integration/vec_interface.md`). | First prove one end-to-end admitted run, then a small timed pilot, then set the campaign size from evidence. |

## 5. Recommended order of work

| Order | Work | Exit condition |
|---:|---|---|
| **1** | **Repair the research evidence chain.** Admit the chosen trace, make fresh-run metrics scientifically admissible, and connect them to the statistical workflow. | One new run reaches a reviewable metric/statistics artifact without unsupported manual relabelling. |
| **2** | **Run a tiny capacity pilot.** Use one actor comparison, a small capacity set, and a small seed count. Measure wall time and inspect failures. | The pilot is reproducible, interpretable, and supplies evidence for the final design and compute estimate. |
| **3** | **Freeze the confirmatory experiment.** Declare the hypothesis, primary outcome, capacity meaning, seeds, exclusions, stopping rule, and analysis before scaling. | A versioned protocol exists and the planned run count is justified. |
| **4** | **Execute the main capacity study.** Scale locally only if the pilot proves it viable; escalate compute only when measured runtime or reliability triggers it. | Accepted receipts, metrics, analysis, limitations, and plots exist for the declared design. |
| **5** | **Complete the small user evaluation.** Obtain ethics approval, run the task script, record results, and make only evidence-led UI repairs. | Ethics and participant evidence are retained; UX claims match the study's actual scope. |
| **6** | **Choose one follow-up.** Prefer fleet mismatch because actor and fleet are already independent request fields. | One bounded follow-up is completed without delaying the primary result. |
| **7** | **Attempt one Manchester corridor only if capacity remains.** Time-box MAN-09 first; stop if the acceptance gates cannot be met. | One accepted corridor baseline and its lineage exist, or the work ends with an explicit blocker report. |

Do **not** schedule mobile RSUs, multiple new scenes, a broad UI redesign, and a Manchester
calibration programme at the same time. Each is a separate project-sized risk; together they would
turn a six-week research plan back into an open-ended platform build.

## 6. Final possibility verdict

| Area | Final verdict |
|---|---|
| Capacity experiment | **Possible after a short, critical evidence-chain repair.** |
| Fleet-mismatch follow-up | **Possible after the main experiment path works.** |
| Five-trace/scenario comparison | **Conditionally possible; admit traces one at a time.** |
| One Manchester bus corridor | **Possible but high-risk and best treated as a time-boxed stretch goal.** |
| Static alternative RSU placement | **Possible within the existing simulated VEC-06 boundary.** |
| Mobile or tram RSUs | **Not possible to validate from the current repository.** |
| One extra SUMO scene | **Technically possible, but only as a follow-up with the full evidence gates.** |
| Broad UI polish | **Possible but poor value; use participant evidence to target fixes.** |
| Manual accessibility/user acceptance | **Possible only with human testing and ethics/participant gates.** |
| Every remaining MAN/UX/REL row | **Not safely achievable as a single six-week commitment. Prioritise only rows that unblock the dissertation evidence.** |

The practical conclusion is: **finish the research instrument first, produce one strong result,
evaluate the user workflow, and keep the Manchester corridor as a controlled stretch goal.** The
platform is mature, but the repository evidence does not support treating every v0.7 capability—or
mobile RSUs—as already complete or trivially finishable.
