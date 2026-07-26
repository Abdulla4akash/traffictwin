# Independent critical review of *Research Directions — From Infrastructure to Findings*

**Review date:** 26 July 2026

**Document reviewed:** `research_directions_claude.md` on `feature-suggestions` at `ed33785`

**Status evidence reviewed:** `claude/complete-v0.7` / `codex/traffictwin-v0.7` at `7a4a16c` after `git fetch origin`

Unless a citation says otherwise, a `claude/complete-v0.7:<path>` locator means the file was
checked at the fetched v0.7 head rather than assumed to exist on this older feature branch.
Meeting assertions are assessed only from tracked repository evidence; the deliberately untracked
meeting material was not inspected. I did not re-run the full quality suite for this documentation
review. The last verified results are the briefing's 3,138 passed, 24 environment-dependent skips,
zero failures, Ruff/format clean, strict mypy clean over 728 files, and `git diff --check` clean
(`claude/complete-v0.7:CURRENT_STATUS_CONTEXT_PROMPT.md`).

## 1. Verdict summary

| Section | Verdict | One-line reason |
|---|---|---|
| §1 — What is being asked for | **Partially agree** | The stakeholder direction is consistent with the tracked design record, but “the platform phase is complete” is false for v0.7 and unsafe as a scheduling premise. |
| §2 — Constraint map | **Partially agree** | The runner flags and two actors are real, but only `we` is directly allowlisted, and fresh local runs do not yet enter the scientific-metric/statistics chain. |
| §3.1 — Capacity squeeze | **Partially agree** | It is the best first scientific hypothesis, but it is not executable end-to-end on `inc` today and its capacity meaning and confirmatory design need tightening. |
| §3.2 — Fleet mismatch | **Partially agree** | Actor and fleet are independently selectable, making the test feasible after the evidence-chain gap is closed; “the other's fleet” still needs an exact declared preset. |
| §3.3 — Scenario flip | **Disagree as an immediate follow-up** | The five traces exist, but four are not directly admitted by VEC-07 and the calm/stressed labels are not a tracked scientific classification. |
| §3.4 — New what-if scenes | **Partially agree** | VEC-06 can preprocess a new one-second FCD/network pair, but the Manchester SUMO baseline is currently blocked and a new scene would add scope on the critical path. |
| §3.5 — Ask Randy for a baseline | **Agree** | This is cheap, potentially high-value, and correctly subject to the same audit and permission gates. |
| §4 — Manchester bus/open data | **Partially agree** | One bounded corridor is the only defensible scope, but BODS is bus evidence, not general demand, and no accepted calibrated corridor currently exists. |
| §5–6 — CSF | **Partially agree** | CSF is optional for a readiness pilot, but local feasibility for the full incident sweep is unproved; the runner is foreground-only, has a two-hour timeout ceiling, and has no batch/SLURM interface. |
| §7 — Immediate plan | **Disagree as written** | The weekend pilot cannot produce admissible study evidence until trace admission, fresh-run scientific admission, and campaign execution are solved. |
| §8 — Marks-per-effort order | **Disagree** | It omits experiment-blocking platform work, overpromotes a new bus corridor, and relies on stale dissertation maps. |
| §9 — Deprioritised work | **Disagree in part** | Mobile-RSU and unrelated features should stay deferred, but blanket deferral of platform work contradicts the v0.7 backlog and blocks the proposed experiments themselves. |

## 2. Status reconciliation

Claude's conclusion is defensible only if “platform” means the accepted v0.5 catalogue plus the
narrow v0.6 VEC capability set. All 39 v0.5 catalogue capabilities and VEC-01–VEC-12 are accepted
within scoped boundaries (`claude/complete-v0.7:docs/implementation-status.md`). It is not
defensible if “platform” includes the v0.7 Manchester research product or the exact machinery
needed for the proposed new studies.

The formal position is unambiguous: all 15 `MAN-01`–`MAN-11`, `UX-01`–`UX-03`, and `REL-01` rows
remain `planned` (`claude/complete-v0.7:docs/implementation-status.md`;
`claude/complete-v0.7:docs/v07_requirement_matrix.md`). The practical states are more informative:
many source and UI slices are `working_bounded`, while MAN-09, MAN-10, MAN-11 and REL-01 remain
`foundation_only` (`claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). In
particular, the current Manchester demand gridlocks; no accepted baseline, one-second FCD pair,
real observed-versus-simulated comparison, or Manchester VEC chain exists
(`claude/complete-v0.7:docs/current_workflow_and_todo.md`;
`claude/complete-v0.7:docs/v07_alpha7_checkpoint_handoff.md`).

There is also a second, experiment-specific gap that the capability-row summary understates:

- VEC-07 directly recognises only the reviewed weekend trace hash; the other four audited source
  traces are not in `PINNED_REVIEWED_TRACES` and would need an accepted VEC-06 receipt or a reviewed
  extension of the allowlist (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`;
  `claude/complete-v0.7:src/traffictwin/integration/vec_runner/service.py`).
- A fresh VEC-07 execution receipt explicitly has `scientific_admission: false`. The one-click
  import records scientific admission as unavailable and imports zero scientific metrics; the
  accepted VEC-09 report is bound to one audited `_s102` source run, not arbitrary new local runs
  (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`;
  `claude/complete-v0.7:docs/integration/vec_one_click_execution.md`;
  `claude/complete-v0.7:docs/integration/vec_scientific_admission.md`).

Consequently, the remaining v0.7 work does compete for the same six working weeks. It should not
all be completed merely to satisfy a release label: provider, broad UI, and final-release items
that do not feed the dissertation can be explicitly deferred. But the experiment-blocking slices
cannot be wished away. At minimum, the project must close trace admission, fresh-run metric
admission, campaign execution, and the evidence route into STA-01 before claiming that the
capacity or fleet studies are runnable.

My scheduling conclusion is therefore: **the platform is mature, but the research instrument is
not finished**. Treating it as finished risks spending the first experimental week discovering
that runs either fail preflight or cannot become admissible statistical evidence.

## 3. Fact-check results

### §1 — Stakeholder record and platform status

| Claim | Status | Repository evidence and finding |
|---|---|---|
| Sandra requested a non-trivial “Morocco” result, an easy what-if interface, a formal small user evaluation, and left offloading versus journey time open. | **Unverifiable in the repo** | The same points are recorded as meeting-derived requirements in `docs/traffictwin-design-v0_4.md`, but the primary meeting material is deliberately untracked. The repository corroborates the planning requirement, not the original quotation. |
| Ethics review takes about one week; anonymisation, survey/interview options and business-school contacts were offered. | **Unverifiable in the repo** | `docs/traffictwin-design-v0_4.md` repeats this as meeting-derived context. `docs/evaluation/ethics_application_draft.md` confirms only that the application is a draft with required fields still missing; it cannot verify an approval turnaround or recruitment route. |
| Randy requested a resource-monitoring view and analysis/explainability help. | **Unverifiable in the repo** | The request itself depends on untracked meeting material. The resulting read-only workbench does exist in `claude/complete-v0.7:docs/integration/tos_results_workbench.md`, so implementation of a bounded monitoring/analysis response is **Verified**, but not Randy's exact words. |
| Randy said the menus were cluttered and hinted at “Study Case 2.” | **Unverifiable in the repo** | No tracked primary meeting record establishes either statement. The current seven-group navigation and presentation overhaul are independently recorded in `claude/complete-v0.7:docs/v07_alpha7_checkpoint_handoff.md`. |
| “The platform phase is complete; every remaining mark comes from using TrafficTwin.” | **Contradicted** | All 15 formal v0.7 rows remain planned, and the beta backlog requires human map review, a viable demand rebuild, calibration, an accepted FCD, comparison/VEC execution, accessibility/usability work, and release reconciliation (`claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`; `claude/complete-v0.7:docs/implementation-status.md`). |

### §2 — Runner, traces, controls and runtime

| Claim | Status | Repository evidence and finding |
|---|---|---|
| Exactly two audited 17-input Model-C actors are runnable, both with a `17 -> 64 -> 64 -> 3` structure. | **Verified** | The closed actor IDs and hashes are in `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; structural validation is documented in `claude/complete-v0.7:docs/integration/vec_evaluator_runner.md` and `claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md`. |
| The five traces `wd_am`, `wd_pm`, `ev`, `inc`, and `we` exist. | **Verified** | All five trace/occupancy pairs, shapes and reconciliation results are recorded in `claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md` and inventoried in `claude/complete-v0.7:docs/reference/generated/vec_source_snapshot_audit.json`. |
| All five audited traces are available today through VEC-07. | **Contradicted** | `PINNED_REVIEWED_TRACES` contains only `trace_we_fullrsu.npz`. Any other trace needs a validated VEC-06 receipt (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/service.py`). Audit of a source trace is not the same as VEC-07 admission. |
| A new one-second FCD/network pair can enter through VEC-06. | **Verified** | The bounded preprocessing path, exact one-second requirement, generated placement, receipt and limitations are defined in `claude/complete-v0.7:docs/integration/vec_fcd_preprocessing.md`. |
| `--fleet`, `--fleet-seed`, `--rsu-cap-per-veh`, and `--max-steps` exist. | **Verified** | All four are in the allowed flags and constructed argv (`claude/complete-v0.7:docs/reference/generated/vec_runner_contract.json`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/service.py`). The request also exposes a separate evaluator seed. |
| Fleet is a closed evaluator preset plus a fleet seed. | **Verified** | `VecFleet` contains seven closed presets and `VecRunRequest` binds the preset and seed (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). |
| Task arrival rate and task-class mix are not VEC-07 evaluation controls. | **Verified** | They exist only as training/environment controls in the audited source contract and are absent from `VecRunRequest` and the allowlisted argv (`claude/complete-v0.7:docs/reference/generated/tos_source_contract.json`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). Unrelated TrafficTwin synthetic-fixture controls do not change this VEC fact. |
| RSU count/placement is not a direct evaluator override; placement is encoded upstream. | **Verified** | The source contract marks the direct override absent, while VEC-06 exposes bounded greedy placement controls (`claude/complete-v0.7:docs/reference/generated/tos_source_contract.json`; `claude/complete-v0.7:docs/integration/vec_fcd_preprocessing.md`). |
| No new/heuristic policy or local training is available through the runner. | **Verified** | VEC-07 admits only the two pinned actors and VEC-10 explicitly excludes training (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:docs/integration/vec_interface.md`). |
| Randy's “20-algorithm zoo” is not supplied. | **Unverifiable in the repo** | The audit proves only two runnable actor checkpoints and does not contain the Year 1 report or a complete external-algorithm inventory (`claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md`). It cannot verify the number 20. |
| Mobile RSUs, signal timing and lane-closure toggles are absent from the evaluator. | **Verified** | These controls are unknown/disabled in the audited source contract and absent from `VecRunRequest` (`claude/complete-v0.7:docs/reference/generated/tos_source_contract.json`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). |
| A real lane closure can already be modelled through a new accepted SUMO scene. | **Unverifiable in the repo** | The repository has synthetic S6 road-clearing/lane-closure workflow fixtures, but explicitly says they are not SUMO/Manchester validity evidence (`claude/complete-v0.7:docs/assumption-register.md`). VEC-06 can consume a suitable external pair, but no accepted real lane-closure authoring/run workflow is recorded. |
| Source wall times are about 4 minutes to 4.3 hours, with a median around 13 minutes. | **Verified** | The 60 source summaries record 265.5 s minimum, 813.0 s median and 15,305.9 s maximum (`claude/complete-v0.7:docs/integration/randy_execution_contract.md`). These are historical source runs, not a local service guarantee. |
| A local JAX/JAXLIB 0.4.30 CPU full-weekend run reproduced source output to at most three ULP. | **Verified** | Two complete local CPU runs are recorded. Discrete/state streams and most aggregates were exact; per-step latency reductions differed by at most three ULP, while average energy used a separate narrow absolute/relative tolerance (`claude/complete-v0.7:docs/integration/vec_reproduction_verification.md`; `claude/complete-v0.7:docs/reference/generated/vec_reproduction_report.json`). The result is one `we` case, not cross-scenario equivalence. |
| Fresh VEC-07 runs can immediately feed STA-01, N-way ranking, TOST and regression gates. | **Contradicted** | Those statistical tools exist (`claude/complete-v0.7:docs/architecture.md`), but fresh VEC execution imports have scientific admission unavailable and zero scientific metrics. VEC-09 is bound to the audited `_s102` source run (`claude/complete-v0.7:docs/integration/vec_one_click_execution.md`; `claude/complete-v0.7:docs/integration/vec_scientific_admission.md`). |

### §3 — Proposed experiments

| Claim | Status | Repository evidence and finding |
|---|---|---|
| The repository supplies paired common-seed studies, N-way ranking, TOST, regression gates, power planning, nearest-flip and threshold-sensitivity tools. | **Verified** | The implemented research/statistics and diagnostics layers are catalogued in `claude/complete-v0.7:docs/architecture.md`, with method limits in `claude/complete-v0.7:docs/power_analysis.md` and `claude/complete-v0.7:docs/assumption-register.md`. |
| The `inc` trace is one hour with a peak size of 2,488. | **Verified** | Its audit row has `T=3,600` and `maxN=2,488` (`claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md`). This is maximum padded concurrent slots, not a 2,488-vehicle total fleet; the same audit records 3,780 unique SUMO IDs. |
| Capacity values `{2.5, 2.0, 1.5, 1.0, 0.75}` are accepted by the request schema. | **Verified** | Capacity must be finite, positive and no more than 1,000 (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). Scientific interpretation still needs to retain the source meaning: a per-padded-vehicle concurrency bound, not CPU capacity. |
| Five capacities × two actors × five fleet seeds is 50 runs. | **Verified** | The arithmetic is correct. The source recommends at least five fleet seeds per cell/fleet (`claude/complete-v0.7:docs/integration/randy_execution_contract.md`), but that recommendation is not a power analysis. |
| Fifty incident runs are an overnight local job and trivial on CSF. | **Unverifiable in the repo** | There is no incident-run local timing, campaign runner, concurrent-memory/output benchmark, or CSF deployment receipt. VEC-10 is foreground-current-process only, has no persistent queue/SLURM path, and each request is capped at 7,200 seconds (`claude/complete-v0.7:docs/integration/vec_interface.md`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). |
| Randy identified “traffic jam overwhelms the RSUs” and the Year 1 report centres on distribution shift. | **Unverifiable in the repo** | These assertions appear in `research_directions_claude.md` and depend on untracked meeting/report sources. No tracked Year 1 report supports the exact attribution. |
| Actor and fleet preset can be crossed independently for a fleet-mismatch test. | **Verified** | `actor_id` and `fleet` are independent closed request fields (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). The plan must name the intended “baseline fleet” preset explicitly; `baseline` is not a `VecFleet` value. |
| `we` is calm and `inc`/`ev` are stressed scenario families. | **Unverifiable in the repo** | The trace identities and shapes are audited, but the repository does not freeze these qualitative calm/stressed labels as a scientific classification (`claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md`). |
| A new stadium/lane-closure FCD can be evaluated after VEC-06. | **Verified** | VEC-06 can admit a caller-supplied compatible one-second FCD/network pair and VEC-07 can then consume its receipt (`claude/complete-v0.7:docs/integration/vec_fcd_preprocessing.md`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/service.py`). The repository does not yet contain the proposed real scene or accepted outputs, so the claim is verified only as a conditional path. |
| No runnable always-local or Lyapunov baseline is present. | **Verified** | The runner contract exposes only the two Model-C checkpoints; synthetic always-local behaviour is explicitly not a real algorithm (`claude/complete-v0.7:docs/reference/generated/vec_runner_contract.json`; `claude/complete-v0.7:docs/synthetic_data_model.md`). |

### §4 — Manchester bus/open-data scenario

| Claim | Status | Repository evidence and finding |
|---|---|---|
| Historical BODS/TfGM/open data alone can support “real demand” and an accepted calibrated Oxford Road corridor. | **Contradicted** | BODS live transit is only `working_bounded`, with retention/republication and membership gaps; BODS cannot provide general traffic demand. MAN-09 has no accepted calibrated baseline at any scope (`claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`; `claude/complete-v0.7:docs/traffictwin-design-v0_7.md`). |
| The resulting defensible claim would already be “evaluated on a real-data-calibrated Manchester urban scenario.” | **Contradicted** | The design requires accepted map matching, temporal profiling, calibration, uncertainty and analyst acceptance before that wording is available. A calibrated simulation remains a model, and none exists yet (`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`; `claude/complete-v0.7:docs/v07_alpha7_checkpoint_handoff.md`). |
| Buses must not be treated as general traffic. | **Verified** | This is a non-negotiable v0.7 boundary (`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`; `claude/complete-v0.7:CURRENT_STATUS_CONTEXT_PROMPT.md`). |
| The evaluator uses fixed per-trace RSU positions and has no mobile-RSU/tram/mmWave physics. | **Verified** | RSU placement is encoded in the trace, and those physics/controls are outside the accepted evaluator request (`claude/complete-v0.7:docs/reference/generated/tos_source_contract.json`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`). VEC-06 can generate different static analysis-site placement; that does not create mobile RSUs. |
| Live GTFS-RT/BODS work violates the architecture because live data is explicitly out of scope. | **Contradicted** | Import-first remains mandatory, but v0.7 explicitly includes bounded live BODS bus positions, operator-triggered acquisition, immutable snapshots and stale fallback. What remains out of scope is an always-on hosted service and general live road telemetry (`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`; `claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). Deferring a new live dashboard is sensible; the stated reason is wrong. |

### §5–§6 — CSF and local feasibility

| Claim | Status | Repository evidence and finding |
|---|---|---|
| A CSF `eval_array.slurm` wrapper exists and is author/path specific. | **Verified** | The external-source inventory records that wrapper and its hard-coded environment/path boundary (`claude/complete-v0.7:docs/integration/randy_artifact_inventory.md`; `claude/complete-v0.7:docs/integration/randy_execution_contract.md`). |
| Per-run CSF speed is similar to local and an array finishes in the slowest-run time plus queueing. | **Unverifiable in the repo** | No CSF execution receipt, benchmark, dependency installation, queue observation or hardware comparison exists. The model is plausible but not repository evidence. |
| The repository already implements the proposed CSF/SLURM batch path. | **Contradicted** | VEC-10 explicitly prohibits SLURM, remote execution, detached recovery and persistent queues; it supports only request-specific foreground execution (`claude/complete-v0.7:docs/integration/vec_interface.md`). An external job may invoke one foreground request, but a separately audited cluster wrapper and deployment would be new work. |
| One paired study should stay on one platform because float tails can differ. | **Verified** | VEC-08's tolerance is accepted only for one JAX/JAXLIB 0.4.30 CPU case and must not be generalised across hardware (`claude/complete-v0.7:docs/integration/vec_reproduction_verification.md`). This supports the precaution, not a measured CSF/local difference. |
| The entire 50–100-run study is proven locally feasible in a few overnight batches. | **Unverifiable in the repo** | Only the full `we` protocol case has a local receipt. No `inc` runtime/output benchmark exists, and the runner's 7,200-second maximum is lower than the historical 15,305.9-second source maximum (`claude/complete-v0.7:docs/reference/generated/vec_reproduction_report.json`; `claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:docs/integration/randy_execution_contract.md`). |
| The 2,488-vehicle incident trace likely caused Randy's four-hour outliers. | **Unverifiable in the repo** | The audit verifies `maxN=2,488`, but no receipt links the slowest historical summaries to `inc` or proves causation (`claude/complete-v0.7:docs/integration/randy-source-snapshot-audit-v0_6.md`; `claude/complete-v0.7:docs/integration/randy_execution_contract.md`). |
| Sandra endorsed a CSF account. | **Unverifiable in the repo** | This is asserted in `research_directions_claude.md`; no tracked approval/account record establishes it. |

### §7–§9 — Immediate plan, supporting artifacts and deprioritisation

| Claim | Status | Repository evidence and finding |
|---|---|---|
| About 20 incident runs can be fired locally this weekend through VEC-07 and yield a crossover result by Sunday. | **Contradicted** | `inc` is not directly allowlisted, execution is foreground one-request-at-a-time, and fresh executions do not enter the accepted scientific metric/statistics chain (`claude/complete-v0.7:src/traffictwin/integration/vec_runner/models.py`; `claude/complete-v0.7:docs/integration/vec_interface.md`; `claude/complete-v0.7:docs/integration/vec_one_click_execution.md`). |
| Ethics application, survey, interview guide and participant task script already exist. | **Verified** | `docs/evaluation/ethics_application_draft.md`, `docs/evaluation/survey.md`, `docs/evaluation/interview_guide.md`, and `docs/evaluation/participant_task_script.md` exist on both reviewed branches. They are drafts, not submitted/approved materials (`docs/evaluation/README.md`). |
| The ethics draft is ready to submit without further decisions. | **Contradicted** | It still requires dates, recruitment route, survey-versus-interview choice, recording decision, retention/storage, withdrawal cutoff, and reference fields (`docs/evaluation/ethics_application_draft.md`). |
| Recruiting 4–6 participants fits the prepared protocol. | **Verified** | The draft allows approximately 4–10 adult researchers/postgraduates and requires the applicable approval before recruitment (`docs/evaluation/ethics_application_draft.md`; `docs/evaluation/README.md`). |
| Menu clutter remains the obvious gap-filling engineering task. | **Contradicted** | Alpha.7 already replaced the old arrangement with seven navigation groups and completed extensive presentation work. Remaining UX risks are first-run guidance and manual human accessibility/usability evidence (`claude/complete-v0.7:docs/v07_alpha7_checkpoint_handoff.md`; `claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). |
| `dissertation_mapping.md` and `dissertation_evaluation_plan.md` exist. | **Verified** | Both files exist on both branches: `docs/dissertation_mapping.md` and `docs/dissertation_evaluation_plan.md`. |
| Those dissertation documents are current maps of v0.7 evidence. | **Contradicted** | They map useful chapters, but still describe Randy/VEC execution and evidence as blocked despite accepted VEC-01–VEC-12, and do not incorporate the v0.7 Manchester beta state (`docs/dissertation_mapping.md`; `docs/dissertation_evaluation_plan.md`; `claude/complete-v0.7:docs/implementation-status.md`). |
| All 39 v0.5 capabilities and all 12 v0.6 VEC capabilities are accepted within their boundaries. | **Verified** | This is the formal implementation truth in `claude/complete-v0.7:docs/implementation-status.md` and the v0.6 catalogue in `docs/traffictwin-design-v0_6.md`. |
| Residual work is scientific/administrative rather than engineering. | **Contradicted** | The beta backlog includes safely executable engineering: review workflow completion, route-pool/demand redesign, viability checks, baseline/FCD execution, first-run UX, evidence-chain integration and release reconciliation (`claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). Fresh-run scientific admission and campaign support also remain absent. |
| Mobile-RSU/tram/mmWave work should remain deferred. | **Verified** | Modifying environment physics, training, and unsupported mobile-RSU semantics are outside the accepted v0.6/v0.7 boundaries (`docs/traffictwin-design-v0_6.md`; `claude/complete-v0.7:docs/traffictwin-design-v0_7.md`). |

## 4. Section-by-section assessment

### §3.1 Capacity squeeze — **Partially agree**

This is still the strongest first hypothesis because it manipulates a real, bounded evaluator
control and directly targets a plausible resource-pressure transition. It is more economical than
authoring a new SUMO scene. The claim must remain about the evaluator's source-specific concurrent
task capacity, not generic CPU utilisation or physical RSU capacity
(`claude/complete-v0.7:docs/integration/randy_schema_mapping.md`).

It should not yet be called the first experiment. It is the first *candidate experiment after an
experiment-readiness gate*. Before spending 20–50 long runs, demonstrate that `inc` passes VEC-07,
that one fresh output becomes an accepted metric collection, and that the exact collection enters
STA-01 without manual relabelling. Then use a development pilot to locate a broad response region
and a separately predeclared held-out seed set for the confirmatory contrast. Five seeds are a
source recommendation, not evidence of adequate power; use the prospective paired power tool with
declared pilot variance and effect size, while retaining its normal-approximation limits
(`claude/complete-v0.7:docs/power_analysis.md`).

### §3.2 Fleet mismatch — **Partially agree**

This is a good second test because actor and fleet are orthogonal request fields, and it probes a
clear distribution-shift question without new simulator construction. The protocol must replace
“the other's fleet” with exact presets, most likely `synthetic` and `uk2030`, and establish from
source evidence what each actor's training distribution actually was. The Year 1 motivation may
be cited only after the report itself is available and reviewed.

Run it after the capacity pilot only if it uses the same admitted trace and fresh-run admission
path. Otherwise it creates a second unresolved execution branch. Report actor × evaluation-fleet
interaction and paired effects, not merely whether a “wrongly trained” actor wins.

### §3.3 Scenario flip — **Disagree as the next follow-up**

Cross-scenario robustness is scientifically useful, but the plan mistakes source-audited traces
for runner-admitted traces. It also assigns calm/stressed semantics without a tracked
classification. First audit/admit each trace and predeclare scenario descriptors independently of
outcomes. Only then is the five-trace ranking a sound robustness or external-validity layer. It
should follow, not precede, a viable one-trace confirmatory study.

### §3.4 New what-if SUMO scenes — **Partially agree**

The end-to-end story is valuable for the demo and aligns with RQ15, but it is a follow-up after one
existing trace yields admissible findings. The v0.7 critical path already contains a gridlocking
demand candidate, pending human map review, calibration and accepted FCD production
(`claude/complete-v0.7:docs/traffictwin-design-v0_7_beta-goals.md`). A separate stadium or lane-
closure scene before that path works would multiply network, demand, calibration and acceptance
risks.

If retained, make it a single bounded demonstration scene with a typed provenance bundle, not a
second confirmatory study. Reuse the accepted Manchester network and revised viable-demand policy
rather than beginning a new corridor/network pipeline.

### §3.5 Email Randy for a dumb baseline — **Agree**

Send the request early. Prefer a checkpoint plus exact producer commit, evaluator compatibility,
training/evaluation labels and permission basis. Summary rows are a weaker fallback because they
cannot automatically enter new common-seed experiments or reproduce a checkpoint. Bundle the
“Study Case 2” question only if doing so does not dilute the precise artifact request. Any received
artifact must pass VEC-01/02/07/09-style review; it cannot be dropped into the runner by filename.

### §4 Manchester bus/open data — **Partially agree**

The scope cap—one corridor, one window, historical/frozen evidence—is right. The proposed evidence
claim is not. BODS can constrain bus routes, positions and possibly dwell observations within its
accepted retention terms; it cannot supply private-vehicle demand. DfT counts, an accepted
map-match policy, the reviewed network and an explicit calibration contract would have to carry
the road-demand claim. TfGM signal data supplies locations, not timing or traffic state
(`claude/complete-v0.7:docs/traffictwin-design-v0_7.md`).

I would not start a fresh Oxford Road calibration in mid-August. Finish or explicitly narrow the
existing MAN-09 path first. If the corridor survives the time gate, describe it as an
“observation-constrained candidate Manchester corridor scenario” until analyst acceptance and
held-out evaluation justify stronger wording. I agree with deferring mobile RSUs, tram anchors,
mmWave physics and a new live dashboard, but not with the assertion that live bus snapshots
violate v0.7's architecture.

### §5–§6 CSF — **Partially agree**

CSF is not needed to prove that one request works. It may become necessary for turnaround once the
study is sized. The current decision rule is too confident because the slowest source run exceeds
the runner's two-hour timeout ceiling, there is no `inc` local receipt, and the accepted interface
has no batch, detached or SLURM execution (`claude/complete-v0.7:docs/integration/vec_interface.md`).

Requesting access in parallel is sensible insurance. Do not claim CSF readiness until a clean
cluster environment passes the same pinned-code preflight and a new wrapper preserves one typed
request/receipt per job. A local timing pilot should measure elapsed time, peak memory, output
bytes, failure rate and serial/concurrent behaviour. The escalation trigger should fire if the
full incident request approaches the 7,200-second contract ceiling, not only after it exceeds an
hour.

### §7 Immediate action plan — **Disagree as written**

Replace “weekend pilot” with a two-day experiment-readiness spike:

1. preflight `inc` and record the exact trace-admission blocker;
2. run one short admitted request and prove the output-to-MetricCollection-to-STA-01 route;
3. decide the smallest reviewed code/contract change needed for fresh-run scientific admission;
4. generate a fixed request matrix and storage/runtime budget without adding an unsafe background
   queue; and
5. only then time one full request.

The Monday external actions should proceed in parallel. Finalise the ethics draft with its missing
fields and supervisor choice before submission; do not recruit first. Email Randy for the baseline
and Study Case 2. Request CSF access without making the study depend on it. Replace generic “fix
the menus” with a targeted first-run/manual-accessibility pass, since the navigation overhaul is
already complete. Write continuously, but first update the stale dissertation mapping/evaluation
documents so they no longer describe accepted v0.6 VEC capabilities as blocked.

### §8 Marks-per-effort priority — **Disagree**

I would change the order to:

1. **Experiment-readiness closure:** admit the target trace, admit fresh-run science, prove the
   statistics handoff, and measure one full run.
2. **One predeclared confirmatory finding:** capacity first; fleet mismatch only as the declared
   fallback/interaction arm. Include effect sizes, uncertainty, exclusions and a held-out design.
3. **Ethics and user evaluation in parallel:** complete approval fields now, stabilise one task
   path, then recruit within the approved 4–10 range.
4. **Write-up and evidence mapping continuously:** update the v0.6-era dissertation files before
   filling chapters from them.
5. **One end-to-end Manchester demonstration:** prefer completion/narrowing of the existing MAN-09
   path; attempt a new bus corridor only if the finding, user study and core write-up are secure.
6. **Cosmetic polish last:** only observed usability/accessibility defects, not broad redesign.

This order adds a small amount of engineering first because it is a prerequisite for every claimed
experimental mark, not because platform completion is intrinsically more valuable than findings.

### §9 Deprioritised list — **Disagree in part**

Keep mobile-RSU/tram/mmWave physics, new base algorithms, an always-on live service, and unrelated
metrics deferred. Keep the rule that a feature must serve a dissertation claim or demo. Do not
defer all platform work: trace admission, fresh-run scientific admission, a safe request matrix,
the viable Manchester demand/FCD path, first-run guidance and manual accessibility evidence are
direct consumers of the proposed experiments or evaluation.

### What is missing, and what risk is understated

The document is missing:

- a verified fresh-run evidence path from VEC-07 output through VEC-09-like admission into
  `MetricCollection`, registry and STA-01;
- a trace-by-trace preflight inventory rather than treating all audited traces as runnable;
- campaign orchestration, timeout, disk, memory, concurrency and failure-recovery budgets;
- a statistical analysis plan that separates exploratory pilot cells from confirmatory held-out
  cells, defines the experimental unit, addresses evaluator versus fleet seeds, justifies power,
  and controls multiplicity across capacities, actors, fleets, traces and metrics;
- an explicit decision about which formal v0.7 beta goals are dissertation-critical and which are
  deferred, with time reserved for writing and verification;
- a no-crossover/no-baseline fallback that still yields a defensible result rather than inducing
  further upset hunting; and
- current dissertation evidence maps and an approval-ready ethics pack.

The most understated technical risk is **inadmissible output**: long runs may complete yet remain
structural execution records with zero scientific metrics. The most understated scientific risk
is **selection bias from upset hunting**. Searching capacities, fleets, scenarios and metrics until
a winner flips can manufacture a narrative even with predeclared individual sweeps. A development
search followed by a frozen confirmatory cohort, transparent multiplicity handling, and reporting
null/no-flip outcomes are essential (`claude/complete-v0.7:docs/assumption-register.md`;
`claude/complete-v0.7:docs/power_analysis.md`).

## 5. Top 3 amendments

1. **Insert an experiment-readiness gate before the pilot.** Within two working days, produce a
   checked matrix showing trace admission, actor/fleet/capacity request validity, timeout and
   storage bounds, fresh-run scientific admission, registry import and STA-01 pairing. Do not
   launch the 20-run pilot until every row is green or has an approved bounded fix.
2. **Freeze a confirmatory protocol after a development pilot.** Use disjoint pilot and held-out
   fleet seeds; name the exact actor/fleet/trace/capacity cells; define deadline-success as the
   primary endpoint with effect size and interval; declare secondary metrics, exclusions,
   multiplicity handling, stopping rule and a publishable null-result interpretation; use
   prospective power planning to choose the final pair count.
3. **Triage v0.7 against the six-week dissertation path.** Mark each beta package
   `experiment-blocking`, `evaluation-blocking`, `release-only`, or `defer`. Complete the first two
   classes only; update `docs/dissertation_mapping.md` and `docs/dissertation_evaluation_plan.md`;
   reserve the new bus corridor and broad UI polish as explicit stretch work.

## 6. Final recommendation

**Endorse with amendments.** The core instinct—stop broad feature growth, obtain one non-trivial
predeclared VEC finding, start ethics/Randy/CSF lead-time actions early, and keep new Manchester
scope bounded—is sound. The plan cannot be executed as written because it confuses audited traces
with runner-admitted traces, accepted v0.6 infrastructure with a complete v0.7 research
instrument, and successful local execution with scientific admission. Close those specific gaps
first, then run the capacity study as the primary experiment and treat fleet mismatch as the
predeclared fallback/interaction study.
