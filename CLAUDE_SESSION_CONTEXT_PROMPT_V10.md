# TrafficTwin session handoff v10 — 7 August 2026

**Canonical at:** 7 August 2026, 09:02 BST (08:02 UTC). This supersedes the operational
instructions in every earlier root context prompt. V9 and earlier numbered prompts are historical
records only.

This file is a handoff, not an approval or evidence artifact. Verify every mutable Git, GitHub and
process fact before acting. Work from the repository root supplied by the user or environment; do
not publish local machine paths.

## 1. Resume state in one minute

- The documentation line is `agent/current-status-5-6-pro-analysis`. Immediately before this V10
  update it was clean and local/remote-aligned at
  `a7c3a34055f5777e95e8efb93d84e8242c2d5a95`; the commit containing V10 necessarily advances
  that SHA. Resolve the live tip rather than copying the pre-update value.
- Open draft [PR #2](https://github.com/Abdulla4akash/traffictwin/pull/2) targets `main` from that
  branch. Its diff was Markdown-only at the audit. Keep it documentation-only.
- Five sequential implementation commits are built and pushed on separate branches, ending at
  `agent/vec-matched-dispatch-study-v1`. They are engineering foundations over synthetic or
  provisional contracts, not native evaluator integration or scientific evidence.
- `origin/main` was `a462c72b81f1668eef4ea0b7f8e806be4d208b47`. Local `main` was still
  `49be6a2db8a69409a1b92fb02e954db7cf1441f6`; do not silently reconcile that discrepancy.
- `claude/complete-v0.7` local/remote was
  `c3e2dc868bbe6cc3dff21f7433984bb28b74df80`. Annotated `v0.7.0^{}` resolved to
  `e840be6c09ac4579e3604665110db2e3209fc7dd`. Draft PR #1 remained open on
  `housekeeping/v0.7-completion` at `e3871c6c73106a5ca1178cb3ef58d504780ad027`. Do not move
  the tag or infer an integration decision.
- At the pre-V10 PR #2 tip, one Python 3.11 check was failed and three Python 3.11/3.12 checks were
  cancelled. The failed check had no runner and no steps. Its GitHub annotation said the job did
  not start because recent account payments failed or the spending limit needed increasing. This
  is an external CI-start blocker, not a code-test verdict. A V10 push may create newer checks;
  inspect them live.
- The admitted capacity-confirmatory campaign still contained 65 files totalling 975,791,580
  bytes. The registry existed with no WAL, SHM or journal sidecar. No campaign or registry byte was
  changed during this audit.
- `data/vec-fresh/capacity-confirmatory/launcher.pid` still contained PID 49470, and no such process
  was alive. Do not launch, resume, kill or restart a campaign merely from that observation.

## 2. What is built now

The implementation line is a five-commit chain based on `origin/main`; all five branch tips were
confirmed on `origin` on 7 August 2026.

| Branch | Commit | Built result | Evidence ceiling |
|---|---|---|---|
| `agent/vec-task-lifecycle-v1` | `b7bc0cca870f3eaa3fd9a0d49e04b8fd951ff114` | Strict per-task lifecycle event models, validation and task-count conservation | Provisional synthetic contract; no native producer |
| `agent/vec-two-rsu-handcheck-v1` | `ec256baef7682bae9bf3e9eec1c62bcc5d07a8fd` | One executable, hand-checkable two-RSU forwarding/reference case | Synthetic oracle only |
| `agent/vec-deterministic-dispatch-v1` | `3b13856134fc6afece5fa6fd1d7e7c5876ace096` | Strongest-link/no-forwarding, least-loaded and predicted-earliest-completion execution-RSU policies over one common contract | Deterministic application software; no native campaign |
| `agent/vec-native-runner-sidecar-v1` | `9fa1c379035f183784b714fcefe80311c0b8d408` | Read-only, exact-bound validation for future lifecycle/request/decision JSONL sidecars | Validator exists; current pinned evaluator emits no sidecar |
| `agent/vec-matched-dispatch-study-v1` | `3813431f7366c833924fcc79d50268be2179e974` | Exact-input structural comparison of all three deterministic policies | Synthetic engineering projections; no winner or scientific result |

The final implementation tip is five commits and 27 changed paths ahead of `origin/main`.
Recorded checks at that tip were:

- 11 focused matched-dispatch-study tests;
- 75 adjacent VEC integration tests;
- 3,505 unit tests;
- Ruff check and format verification over 989 files; and
- strict mypy over 934 source files.

These branches are pushed, but they are not merged into `main` and are not part of PR #2. Do not
copy their code into PR #2. Read their versioned integration documents from the final branch before
changing them:

- `docs/integration/vec_task_lifecycle_contract.md`;
- `docs/integration/vec_two_rsu_handcheck.md`;
- `docs/integration/vec_deterministic_dispatch.md`;
- `docs/integration/vec_native_runner_sidecar.md`; and
- `docs/integration/vec_matched_dispatch_study.md`.

## 3. What is not built, and why

The next evidence-producing component is a **native lifecycle/state producer** or an authorised,
reviewed adapter that can emit the implemented sidecar contract from genuinely available native
events. It is not yet built.

The blockers are substantive rather than missing scaffolding:

1. The pinned evaluator does not emit stable task identity, admission/rejection, reservation,
   forwarding, execution, physical-return or dispatcher-decision events.
2. Legacy `task_met` and latency arrays cannot reconstruct those missing events.
3. Service, drain, unavailable-task, action-mask, admission and return semantics still require
   producer confirmation or an explicit owner-approved provisional semantics record.
4. Both pinned external repositories are restricted: do not fetch, pull or modify them. A native
   producer needs separate authorisation and review at the correct source boundary.
5. Without native events, the sidecar validator, hand check and matched-policy harness remain
   synthetic. They cannot support physical completion, throughput, work conservation or policy
   superiority claims.

Consequently these remain unbuilt or unexecuted:

- native producer/adapter and runner emission of the three exact sidecar files;
- live runner/admission wiring for validated dispatcher requests and decisions;
- replay of the hand calculation against native emitted events;
- a predeclared matched native policy campaign with identical traffic, tasks and seeds;
- realised lifecycle metrics, uncertainty analysis and an admitted scientific result;
- a learned scheduler using the same information and costs; and
- capacity-aware actor retraining, which is a separate observation-contract experiment.

GitHub Actions is also unavailable as a hosted gate until the account billing/spending issue is
resolved. Local passing checks do not remove the native-data and scientific-admission blockers.

## 4. Read-only verification in every fresh session

Run from the repository root before planning or editing:

```bash
git status --short --branch
git log --oneline --decorate -8
git rev-parse HEAD main origin/main claude/complete-v0.7 origin/claude/complete-v0.7
git rev-parse 'v0.7.0^{}'
git ls-remote --heads origin \
  main \
  agent/current-status-5-6-pro-analysis \
  agent/vec-task-lifecycle-v1 \
  agent/vec-two-rsu-handcheck-v1 \
  agent/vec-deterministic-dispatch-v1 \
  agent/vec-native-runner-sidecar-v1 \
  agent/vec-matched-dispatch-study-v1
gh pr view 2 --json url,title,state,isDraft,headRefName,headRefOid,baseRefName,statusCheckRollup
gh run list --branch agent/current-status-5-6-pro-analysis --limit 5
```

Check only the recorded campaign metadata and process state; do not invoke a verifier that may
open or migrate the registry:

```bash
if [ -f data/vec-fresh/capacity-confirmatory/launcher.pid ]; then
  campaign_pid=$(tr -d '[:space:]' < data/vec-fresh/capacity-confirmatory/launcher.pid)
  printf 'campaign_pid=%s\n' "$campaign_pid"
  ps -p "$campaign_pid" -o pid=,stat=,etime=,command=
fi

shasum -a 256 \
  data/vec-fresh/capacity-confirmatory/launcher.pid \
  data/vec-fresh/capacity-confirmatory/campaign_receipt.json \
  data/vec-fresh/capacity-confirmatory/campaign_analysis.json \
  docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md \
  .demo/registry-capacity-confirmatory.sqlite
```

The pre-V10 audit hashes were:

| Artifact | SHA-256 |
|---|---|
| launcher PID file | `8d04eba9b2dc038b951eddbd8a64c15bcd160364320d2bbc14beaf78b95988af` |
| campaign receipt | `e022972f012287d9f27bc281b96d3add08425d2580bb243142df8225c79afb4a` |
| campaign analysis | `a62e3e50f8d3f3124a8fbb4bfa9a3a48efb3eb2d400fcda90b5a722e318ff8da` |
| digest-bound confirmatory candidate | `ac9d6cb7cd24f19ba683352cd3d12d91cbd610343ac392028feb53797bbae2a8` |
| confirmatory registry | `12fa0142cd7b079e51a4ff653d395a5b04e013eed3b17f77e40555420278031f` |

If a PID is alive, avoid heavy multi-core commands. Never touch, resume, kill or restart anything
under `data/vec-fresh/` or `.demo/` merely to inspect status.

## 5. Read before research analysis or editing

Read completely and together:

1. `AGENTS.md` and this file.
2. `docs/current_status_5_6_pro_analysis.md`.
3. `docs/evaluation/complete_experiment_history_20260806.md`.
4. `docs/evaluation/experiment_catalogue_20260730.md`.
5. `docs/evaluation/capacity_confirmatory_results_20260728.md`.
6. `docs/evaluation/capacity_study_detailed_findings.md`.
7. `docs/research_directions_v2.md`.
8. `docs/evaluation/supervisor_meeting_4_20260806.md`.
9. `docs/evaluation/traffic_to_vec_scheduling_experiment_plan_20260806.md`.
10. `docs/evaluation/supervisor_scheduling_build_status_20260806.md`.
11. `docs/muse-spark-1.2-publication-direction.md`.
12. The five implementation documents listed in §2 when implementation work is in scope.

The 5.6 Pro report is owner-supplied external analysis. Central counts were locally reproduced,
but its 57%/51%/71% scores are subjective and its claimed model origin is unauthenticated. Do not
turn the report itself into evidence or approval.

## 6. Scientific and architecture corrections that must survive

- The 2.5→0.75 intervention changed a per-RSU **admission/in-flight concurrency ceiling**. It did
  not change processor speed, computation power, service rate, worker count or bandwidth.
- The lower mean modelled latency came from compression of the already-deadline-failed extreme
  tail under incomplete task-lifecycle accounting. It is not evidence of faster computation,
  improved physical completion or a proven fail-fast mechanism.
- `task_met` is modelled deadline attainment, not eventual physical completion.
- A frozen MAPPO actor plus downstream RSU forwarding does not require retraining. Adding RSU
  load, capacity, headroom or telemetry age to the actor changes its observation contract and
  requires retraining.
- The existing actor chooses local/V2I/V2V. Environment logic selects the strongest/best-link RSU.
  Do not claim that MAPPO generally failed; the limitation belongs to the supplied observation,
  action and environment design.
- TfGM/BODS data supplies vehicle and bus mobility, not computing tasks. Routes, speeds, density,
  contact time and handover may be measurement-informed. Task arrivals, payloads, CPU work,
  deadlines, RSUs, radio behaviour and queues remain synthetic unless separately observed.
- Computing-task scheduling does not make roads less congested without a separate closed-loop
  traffic-control intervention and evidence.
- Meeting 4's detailed parameter-plan, RSU-count graph criticism and rapid deterministic-repair
  instructions were primarily directed to Ethan during his presentation. Do not automatically
  attribute every instruction to Abdulla. The wider scheduling limitation remains relevant.
- The corrected Meta Muse document makes the scheduling study the primary direction. A
  TrafficTwin/JOSS or SoftwareX paper is secondary and must pass licensing, public-release,
  related-work and reproducibility gates. Do not restore “immediately publishable” claims or
  propose restricted VEC artifacts for public hosting.

Safe capacity-result wording remains:

> Under one audited evaluator, actor and incident trace, lowering a configured per-RSU
> admission/in-flight ceiling compressed the extreme modelled latency tail without changing the
> actor's keyed decisions or deadline attainment. Because the evaluator does not conserve and
> record a complete task lifecycle, the result is not evidence of faster computation or improved
> physical task completion.

## 7. Defensible next sequence

The engineering foundation now covers the first deterministic scaffolding, but the research
sequence has not skipped its evidence gate:

1. Freeze producer semantics and implement/authorise the native lifecycle/state producer.
2. Validate one native emission through the sidecar and replay the hand-checkable two-RSU case.
3. Wire the three deterministic policies into identical native traffic, task and seed conditions.
4. Predeclare and run the matched native comparison with complete lifecycle/work-conservation
   accounting and uncertainty.
5. Compare a learned scheduler afterward with the same information and costs.
6. Treat capacity-aware actor retraining as a separate experiment.

Until producer semantics and source-boundary authority exist, the safest further work is
documentation-only: a reviewed producer conformance plan, exact semantic decision record and
native-campaign preflight checklist. Do not fabricate an adapter from aggregate arrays.

No scientific campaign starts merely because this handoff describes it. Freeze design, seed roles,
endpoints, resource budget and approval digest first. A publishable null remains acceptable.

## 8. Standing restrictions

- Keep PR #2 documentation-only. Implementation remains on its separate branch chain.
- Do not fetch or pull either pinned external clone and do not modify either external repository.
- Do not touch admitted campaign or registry bytes, and do not edit the digest-bound confirmatory
  candidate.
- Do not expose private data, credentials, source identities, raw traces, checkpoints, private
  correspondence or machine paths.
- Do not publish VEC-11/VEC-12 or any other restricted artifact.
- Do not move or create tags, reconcile local `main`, merge PR #1, or integrate the implementation
  chain without explicit owner direction.
- Do not launch or relaunch campaigns merely because a PID is absent or stale.
- Preserve unrelated user changes. Stage explicit paths only; never clean, reset or reformat
  unrelated work.
- Before any commit, inspect the exact diff, run `git diff --check`, and confirm the intended PR
  remains documentation-only. Push only when explicitly requested.
- No LLM analysis is evidence. Do not invent source semantics, approvals, experiment results,
  provider facts or causal explanations.

## 9. Handback contract

At the end of resumed work, report:

1. live branch, commit, remote alignment, PR and CI state;
2. exact files changed and the reviewed commit range;
3. commands and local checks actually run;
4. whether campaign, registry and PID observations changed;
5. scientific label and admission status of every result mentioned;
6. unresolved semantic, source-boundary, integration and owner decisions; and
7. a refreshed standalone resume prompt whenever mutable state changes materially.

## 10. Paste this into the next session

```text
Continue TrafficTwin in the diss-integration repository worktree.

Before acting, read AGENTS.md and CLAUDE_SESSION_CONTEXT_PROMPT_V10.md completely. V10 is the
canonical 7 August 2026 handoff; V9 and earlier prompts are historical. Run the exact read-only
checks in V10 §4 and report the verified branch/HEAD/worktree, local and remote refs, PR #2/CI,
admitted campaign/registry hashes and campaign PID/process state before starting another slice.

Keep PR #2 documentation-only. Five separate pushed implementation branches now provide a
provisional lifecycle contract, a synthetic two-RSU hand check, three deterministic execution-RSU
policies, a native-sidecar validator and a matched synthetic policy-study harness. Verify their
remote SHAs from V10 §2. Do not describe them as native evaluator integration, a campaign result,
a policy winner or scientific evidence.

The evidence bottleneck is an authorised native lifecycle/state producer or reviewed adapter from
genuinely available native events. The pinned evaluator emits no such events, aggregate task_met
and latency arrays cannot reconstruct them, and the external clones must not be fetched, pulled or
modified. Do not fabricate physical completion, work conservation or fail-fast claims.

Preserve the scientific correction: 2.5→0.75 changed a per-RSU admission/in-flight concurrency
ceiling, not compute speed. Its lower mean modelled latency compressed an already-failed extreme
tail under incomplete lifecycle accounting. task_met is modelled deadline attainment, not eventual
physical completion. Frozen-actor downstream forwarding needs no retraining; actor-visible load or
capacity does.

Do not touch admitted campaign/registry bytes, the digest-bound confirmatory candidate, restricted
artifacts, external repositories or tags; do not expose private data or machine paths; and do not
launch a campaign from PID state alone. After reporting verified live state, wait for my concrete
next slice unless I included one in the prompt.
```
