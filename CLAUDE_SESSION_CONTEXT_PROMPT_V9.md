# TrafficTwin session handoff v9 — 6 August 2026

**Canonical at:** 6 August 2026, 11:29 BST (10:29 UTC). This supersedes the
operational instructions in every earlier root context prompt. Earlier numbered prompts remain
historical records; do not resume from them.

This is a handoff, not an authority artifact. Verify mutable Git/process state before acting, and
use the repository's evidence records for scientific claims.

## 1. Resume state in one minute

- Work in `/Users/akashx/AntigravityTest/diss-integration`.
- The current documentation branch is `agent/current-status-5-6-pro-analysis`; its open draft is
  [PR #2](https://github.com/Abdulla4akash/traffictwin/pull/2), targeting `main`.
- Commit `9036b6ed36577aa44fe18dc03ef4c8bf4b6357a7` added the owner-supplied 5.6 Pro
  audit at `docs/current_status_5_6_pro_analysis.md` and linked it from `docs/index.md`.
- Keep PR #2 documentation-only. New evaluator, scheduler or training code belongs on a new,
  explicitly scoped branch after the owner chooses the next slice.
- `main` and `origin/main` were both
  `49be6a2db8a69409a1b92fb02e954db7cf1441f6` (`release TrafficTwin v0.7.0 on
  main`). `claude/complete-v0.7` was
  `c3e2dc868bbe6cc3dff21f7433984bb28b74df80` (Phase 198).
- The annotated `v0.7.0` tag resolves to
  `e840be6c09ac4579e3604665110db2e3209fc7dd`, which is on
  `housekeeping/v0.7-completion`, not at the current `main` tip. Draft
  [PR #1](https://github.com/Abdulla4akash/traffictwin/pull/1) carries that housekeeping line.
  Record this topology; do not move a tag or reconcile branches without owner instruction.
- PR #2's GitHub Actions jobs started with no steps and failed because of the repository account's
  billing/spending-limit state. That is an external CI-start blocker, not a demonstrated test
  failure. Do not repeatedly rerun it until billing is resolved.
- `data/vec-fresh/capacity-confirmatory/launcher.pid` contained PID 49470, but that process was not
  alive at this snapshot. Recheck; never assume the stale observation remains true.

## 2. Read before deciding or editing

Read completely, in this order:

1. `AGENTS.md`, especially **v0.7 Work Coordination** and the latest claims.
2. This file.
3. `docs/current_status_5_6_pro_analysis.md`.
4. `docs/evaluation/experiment_catalogue_20260730.md` and
   `docs/experiments_and_findings_20260728.md`.
5. `docs/evaluation/capacity_study_detailed_findings.md` and the signed confirmatory results.
6. `docs/research_directions_v2.md`.
7. `docs/current_progress_v0_7.md`, `docs/implementation-status.md`,
   `docs/open-questions.md` and `CHANGELOG.md`.
8. `docs/integration/randy_data_and_publication_permission_20260729.md`.
9. `docs/project_guide.md` for the repository and terminology map.

Important chronology:

- `docs/research_directions_v2.md` is valuable design rationale, but its Tier-A “future” list is
  dated 27 July and several listed studies were subsequently completed. Use the experiment
  catalogue for execution status.
- Its B-CAP audit predates some GPU campaigns and the 29 July permission record. Use the catalogue
  and permission record for current status.
- Its capacity-mechanism wording also predates the 5.6 Pro audit. Read it through the limitations
  and corrections in `docs/current_status_5_6_pro_analysis.md`.
- The 5.6 Pro report is an owner-supplied external analysis. Its central counts were locally
  reproduced, but its 57%/51%/71% scores are subjective judgments and its claimed model origin is
  not authenticated. Do not turn the report itself into evidence or approval.

## 3. First checks in a fresh session

Run read-only checks before making a plan:

```bash
cd /Users/akashx/AntigravityTest/diss-integration
git status --short --branch
git log --oneline --decorate -8
git rev-parse main origin/main claude/complete-v0.7 origin/claude/complete-v0.7
git rev-parse 'v0.7.0^{}'
gh pr view 2 --json url,title,headRefName,baseRefName,isDraft,statusCheckRollup
```

Check the campaign PID without touching the campaign:

```bash
if [ -f data/vec-fresh/capacity-confirmatory/launcher.pid ]; then
  campaign_pid=$(tr -d '[:space:]' < data/vec-fresh/capacity-confirmatory/launcher.pid)
  ps -p "$campaign_pid" -o pid=,stat=,etime=,command=
fi
```

If it is alive, avoid heavy multi-core commands. Never touch, resume, kill or restart anything
under `data/vec-fresh/` or `.demo/` merely to inspect status.

## 4. Current scientific position

### The completed experiment

- The exploratory pilot used the `inc` incident/collapse-hour trace, capacities
  2.5/1.5/1.0/0.75 and seeds 0–2. Recorded deadline attainment stayed about 79.1%, while mean
  modelled latency fell from 9,798.8 ms to 3,083.6 ms. Keyed actor decisions were identical
  across arms (`docs/evaluation/experiment_catalogue_20260730.md`, A1/A3).
- The pre-data, digest-bound held-out comparison used seeds 10–14 and cap 2.5 versus 0.75. All
  five paired latency differences were negative; the mean was −8,310.9 ms with bootstrap interval
  [−9,097.5, −7,524.3] and a two-sided exact sign-test floor of p=0.0625. The deadline null
  replicated. Those held-out seeds are spent
  (`docs/evaluation/capacity_confirmatory_results_20260728.md`).
- Four normal traces (`we`, `ev`, `wd_am`, `wd_pm`) were effectively inert on the ordinary grid.
  The deep squeeze produced only tiny changes and the predeclared exact onset-scaling prediction
  was refuted (`docs/evaluation/experiment_catalogue_20260730.md`, A6/A7/A8/A17).

### What the intervention means now

- Do not call the 2.5→0.75 control CPU power, compute speed or physical RSU capacity. It is a
  per-padded-slot scaling value used to form a per-RSU admission/in-flight concurrency ceiling:
  `round(control × padded trace width)`. On `inc`, 2,488 slots make the bounds 6,220 and 1,866
  tasks (`docs/current_status_5_6_pro_analysis.md`, §B).
- “Queue/waiting-room capacity” is directionally closer than “compute power,” but still simplified:
  the model does not cleanly separate waiting, executing, server count, queue length and service
  rate. Prefer **admission/in-flight concurrency ceiling**.
- The lower mean is a real evaluator output, not faster computation. Median latency stayed about
  44.3 ms; the change is concentrated in the extreme tail of tasks already missing deadlines.
  Call the endpoint **modelled deadline attainment**, not physical task completion.
- The evaluator lacks a complete per-task lifecycle linking offered, admitted, rejected, queued,
  started, executed and returned work. Therefore “quick rejection/fail fast caused it” remains too
  strong.
- Local reconstruction found 5,973,330 eligible V2I tasks per pilot arm: 1,096,583 were not
  admitted at cap 2.5 and 1,157,465 at cap 0.75, an extra 60,882. The separate 51 seed-0
  no-eligible-target rows represented 107 tasks and were arm-invariant. Do not use those 51 rows
  as the capacity-effect rejection count (`docs/current_status_5_6_pro_analysis.md`, §E–§F).
- The saved load is post-drain, so a stored value below the cap does not prove the pre-drain clamp
  never bound. The clamp can omit excess work from backlog while tasks are still scored; work
  conservation is unresolved.
- Aggregate offered V2I work was below aggregate nominal service capacity in the measured seed-0
  reconstruction, but load was spatially asymmetric: four RSUs were individually oversubscribed
  and three had zero backlog. That motivates load management, but the current records do not prove
  the geographical cause of every idle/busy RSU.
- The actor chooses local/V2I/V2V; environment logic selects the best-link RSU. The trace evaluator
  uses an unmasked argmax rather than the environment's action-mask helper. A masking treatment may
  materially change behaviour and must be explicit, not silently inserted.

### Safe claim

Use wording like:

> Under one audited evaluator, actor and incident trace, lowering a configured per-RSU
> admission/in-flight ceiling compressed the extreme modelled latency tail without changing the
> actor's keyed decisions or deadline attainment. Because the evaluator does not conserve and
> record a complete task lifecycle, the result is not evidence of faster computation or improved
> physical task completion.

Do not use `scientifically_validated`, `ground_truth`, `publication_approved`, `causal` or
`production_deployment_ready`. The label ceiling remains `owner_approved_candidate` unless a
recorded governance artifact says less.

## 5. Other completed evidence

- A pre-registered ceiling-law test held 27/27 within its ±5% band, but only for the modelled RSU
  queue subsystem and tested population (`experiment_catalogue`, A15).
- The actor-crossover study found no crossover. The trained actor retained about a 6.09 percentage
  point deadline advantage, while the frozen actor-independent latency-slope prediction was
  refuted (`experiment_catalogue`, A16).
- GPU B-CAP, B-REWARD, B-MASK and B-DOMAIN campaigns completed as private, non-admitted
  diagnostics. B-BUS corridor was also diagnostic. The earlier Sparse-64 return with 147 unintended
  repeated held-out evaluations remains non-admitted. The clean Sparse-64 rerun was subsequently
  owner-admitted on 2 August only as descriptive evidence with the immutable
  `admitted_with_execution_deviation` qualifier. Its completed training, actors and checkpoints
  were not overwritten: the deviation was one unintended second fixed held-out evaluation/return
  after the first valid download, with unchanged scientific settings and no metric-based selection.
  Cross-return metric identity remains unverifiable, the result stays outside VEC-06 and must not be
  pooled with protocol-confirmed VEC evidence or promoted to causal, general-Manchester, physical-
  completion, actor-admission or supervisor-approved standing (`experiment_catalogue`, GPU track;
  `docs/evaluation/bbus_sparse64_clean_rerun_owner_admission_20260802.json`).
- BODS night, dawn, morning and evening sessions completed under the attended boundary. Buses are
  never relabelled as general traffic. The MAN-05 refusals were traced to cross-operator reuse of
  bare `VehicleRef`; they were not proof of feed overload (`experiment_catalogue`, bus programme).
- The earlier claim that Geofabrik mutated the Manchester source was withdrawn. Source identity
  had been confused with derived-artifact identity; the canonical network rebuild reproduced
  (`experiment_catalogue`, Manchester chain).
- Randy's code/data/publication permission is recorded only as an owner relay of a written grant;
  the private message is deliberately not committed. Permission does not create scientific
  admission, supervisor approval, budget or publication approval
  (`docs/integration/randy_data_and_publication_permission_20260729.md`).

## 6. Recommended next research sequence

Do not jump straight to “AI Kubernetes.” The defensible sequence is:

1. **Clarify and instrument lifecycle semantics.** Ask Randy to confirm the intended meaning of
   `RSU_MAX_CONCURRENT`, the existing service/drain parameters, action-mask semantics, scoring of
   non-admitted work, whether work should be conserved, and what constitutes completion. Add
   offered/admitted/rejected/queued/started/finished/returned outcomes and drop causes before using
   completion or throughput language.
2. **Correct deterministic baseline.** Define a Kubernetes-inspired application-level RSU
   dispatcher/forwarder—do not claim Kubernetes natively routes individual VEC tasks. Compare
   no-forwarding, least-loaded and predicted-earliest-completion policies with forwarding delay,
   queue discipline and stale-information age explicit. A frozen offloading actor is valid here;
   this is the narrow case in which retraining is unnecessary.
3. **Measure before learning.** Use matched seeds and work-conserving accounting. Primary outcomes
   should include physical lifecycle completion/throughput and deadline success, with rejection,
   latency distributions, queue age, forwarding count/overhead, per-RSU utilisation and Jain
   balance as mechanism/secondary outcomes. Predeclare congestion and free-flow expectations
   separately; improvement in both is not guaranteed.
4. **Learned scheduler second.** Train a DRL scheduler only after the deterministic baseline is
   correct. Match information, action space and budget, and include the deterministic result even
   if the learned method loses.
5. **Capacity-aware offloading is a different treatment.** If RSU load/headroom enters the actor's
   observation or the actor chooses a specific execution RSU, the observation/action contract
   changes and retraining is required. Frozen-actor forwarding and capacity-aware actor retraining
   must not be conflated.

No new scientific campaign starts merely because this handoff recommends it. Freeze the design,
seed roles, endpoints, resource budget and approval digest before data. A publishable null remains
an acceptable outcome.

## 7. Standing filesystem and evidence boundaries

- Never run `git fetch` or `git pull` inside
  `/Users/akashx/AntigravityTest/external/tos-data` or
  `/Users/akashx/AntigravityTest/external/vec_env`. Read-only file inspection is allowed.
- Never edit `docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`; its bytes are
  digest-bound to the completed approval chain.
- Treat `.demo/`, `data/vec-fresh/`, `data/gpu-track/`, quarantine trees, approval records and
  registries as read-only unless the owner gives an exact mutation task whose protocol permits it.
- Do not inspect or commit private credentials, raw BODS identifiers, private correspondence or
  meeting-note personal details. The owner checkout `/Users/akashx/AntigravityTest/diss` is a
  separate worktree and must not be used as a scratch area.
- Preserve existing dirty/untracked files. Stage exact paths only; never clean, reset, stash or
  reformat unrelated work.
- No LLM analysis is evidence. Do not invent source semantics, approvals, experiment results,
  provider facts or causal explanations.

## 8. Owner/external decisions still distinct from agent work

- Obtain Randy's semantic answers before treating the proposed scheduler experiment as a settled
  contract. If the owner elects to proceed first, record explicit assumptions and their limits.
- Resolve GitHub billing/spending limits before treating Actions as an available gate.
- Decide whether and how draft PR #1's housekeeping/tag line should reach `main`; never rewrite the
  release topology autonomously.
- The Manchester programme still has human/scientific, retention/privacy, provider-contract and
  measured-traffic decisions listed in `docs/current_progress_v0_7.md` §7 and
  `docs/open-questions.md`. Do not replace those registers with an older session queue.
- Supervisor, ethics, publication and deployment authority remain separate from owner approval.

## 9. Handback contract for the next session

At the end of any resumed work, report:

1. live branch/commit/PR and exact files changed;
2. what was read and which evidence supports the conclusions;
3. commands/checks actually run, including external CI blockers;
4. scientific label and admission status of every result mentioned;
5. unresolved discrepancies and owner/external decisions;
6. a refreshed standalone resume prompt if mutable state changed materially.

## 10. Paste this into the next session

```text
Continue TrafficTwin from /Users/akashx/AntigravityTest/diss-integration.

Read AGENTS.md and CLAUDE_SESSION_CONTEXT_PROMPT_V9.md completely before acting. Treat V9 as the
canonical 6 August 2026 handoff, but verify its mutable Git, PR, CI and PID state with the read-only
commands in V9 §3. Earlier context prompts are historical.

The current docs work is draft PR #2 on agent/current-status-5-6-pro-analysis. Keep that PR
documentation-only. Read docs/current_status_5_6_pro_analysis.md with the experiment catalogue,
signed capacity result and research_directions_v2; do not authenticate the report's claimed model
origin or treat its subjective percentages as measurements.

Scientific correction to preserve: the 2.5→0.75 intervention was a per-RSU admission/in-flight
concurrency ceiling, not compute power. The lower mean modelled latency came from compression of
the already-failed tail under incomplete task-lifecycle accounting; it is not evidence of faster
computation or improved physical completion. The load-balancing direction is worthwhile, but
instrument lifecycle/work conservation first, then compare a deterministic application-level
dispatcher before a learned scheduler. Frozen-actor forwarding needs no retraining; adding
load/capacity to the actor does.

Do not fetch/pull either pinned external clone, touch admitted campaign/registry bytes, edit the
digest-bound confirmatory candidate, expose private data, move tags, or mix implementation code
into PR #2. Ask the owner what concrete next slice to take after you report the verified state.
```
