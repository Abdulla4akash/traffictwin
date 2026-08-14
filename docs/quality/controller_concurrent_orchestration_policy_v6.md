# TrafficTwin controller concurrent-orchestration policy v6

Status: **OWNER-AUTHORIZED, AGENT-AGNOSTIC CONTROLLER POLICY**

Effective scope: all remaining TrafficTwin engineering/controller work, including the current E3 Dynamic Resource V2 campaign, Lane 11, Lane 12, Dynamic freeze, global integration, final release audit, and future multi-agent campaigns unless a newer owner-authorized policy explicitly supersedes this file.

V6 **supersedes V5 for scheduling and concurrency**. V5 trust, exact-SHA, review, promotion, research-hold, and stable-candidate gate rules remain in force unless this document restates them more strictly.

Canonical discovery entrypoint for controllers: repository-root `CONTROLLER.md`.

---

## 1. Purpose

TrafficTwin must behave like a multi-agent software factory, not a single serial CLI.

The controller must minimize **wall-clock critical-path time** while preserving exact-SHA evidence integrity. Waiting for one worker, reviewer, or test must not make unrelated safe work idle.

Core rule:

> **When the critical path blocks, immediately schedule every safe READY or PREPARABLE task in isolated state.**

Review serialization is required only where evidence identity requires it. It does **not** imply factory-wide serialization.

---

## 2. Roles are capabilities, not model names

Any future agent may occupy these roles if explicitly assigned:

- **OWNER** — human final authority; may change scope, research authorization, or policy.
- **CONTROLLER / INTEGRATOR** — maintains the DAG, dispatches work, runs gates, owns Git bookkeeping, reconciles exact SHAs, performs mechanical promotion/integration, and never self-approves source changes.
- **BUILDER / REMEDIATOR** — changes source in an isolated worktree/branch within an explicit file boundary. Current default implementation worker is Muse xhigh.
- **INDEPENDENT REVIEWER** — read-only adversarial exact-SHA review. Current default is Claude Opus 5 xhigh.
- **PREFLIGHT / ANALYSIS WORKER** — performs read-only dependency analysis, conflict analysis, attack generation, test planning, provenance checks, or speculative preparation. Its output is not approval.

The policy remains valid if model/provider names change. Trust is attached to role separation and exact artifacts, not brands.

---

## 3. Non-negotiable trust invariants

1. Source-changing work must occur in an explicit owned worktree/branch and file boundary.
2. The controller may not silently patch product/research source and then self-approve it.
3. Every promotable source-changing candidate requires a **fresh independent read-only exact-SHA review**.
4. Any source-changing commit creates a new SHA and invalidates predecessor approval.
5. An approved SHA is frozen.
6. Promotion is source-identical/mechanical only.
7. Reviewer verdict must bind the full SHA: `VERDICT: APPROVE exact SHA <FULL_SHA>` or `VERDICT: REQUEST CHANGES exact SHA <FULL_SHA>`.
8. Local HEAD, origin head, PR head, ledger candidate, implementation receipt, and review target must reconcile before approval/promotion.
9. No approval transfer between SHAs.
10. No force-push to `main` and no rebase of reviewed histories.
11. The final globally composed source SHA receives a fresh independent integration-level review before merge to `main`.
12. Hosted CI may be `HOSTED_CI_UNAVAILABLE`; unavailable is never represented as passed.

---

## 4. Immutable E3 scientific hold

Until the owner explicitly lifts it, preserve exactly:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Forbidden: E3a/E3b/E3c scientific execution, 3600-step research cells, reduced/pilot/exploratory scientific campaigns, Manchester comparative E3 execution, multi-draw E3 scientific workloads, benchmarks represented as scientific evidence, and empirical/statistical inference from unexecuted E3 work.

Allowed engineering activity includes ordinary unit/integration/AppTest/static checks and tiny deterministic construct/smoke tests already permitted by lane contracts. Software evidence must never be relabelled as scientific evidence.

---

## 5. The controller maintains a dependency DAG

Every meaningful unit of work is a DAG node. The controller must maintain at least these states:

- `BLOCKED` — cannot safely begin because a hard dependency/decision is missing.
- `PREPARABLE` — final source identity is blocked, but useful isolated preparation is safe now.
- `READY` — may execute and produce candidate work now.
- `RUNNING` — worker/check/reviewer process exists.
- `REVIEWING` — exact candidate is under independent review.
- `REQUEST_CHANGES` — immutable rejected SHA; remediation required.
- `APPROVED` — exact SHA independently approved but not yet mechanically promoted.
- `PROMOTED` — approved source integrated source-identically into its target.
- `FROZEN` — final lane/integration source identity may no longer change without opening a new reviewed successor.

The controller must know the hard dependencies for each node and distinguish them from soft/preparatory dependencies.

### Scheduling loop

Whenever any task starts, completes, blocks, or returns a verdict, the controller runs:

1. consume the event;
2. update DAG state;
3. identify the critical path;
4. scan all nodes for `READY` work;
5. scan all blocked future nodes for safe `PREPARABLE` work;
6. dispatch safe independent work subject to resource limits;
7. continue the critical-path transition;
8. never return to an idle prompt merely because one child is still running.

`Waiting for task` describes one child, not the state of the whole factory.

---

## 6. No-idle-controller principle

If the controller is waiting on Muse, Opus, a focused test, a broad test, or GitHub propagation, it must immediately ask:

> What useful work can run now without changing or falsely assuming the blocked exact artifact?

Examples that should normally run during reviewer wait time:

- prepare the next lane's test/validator architecture against the declared interface;
- generate adversarial cases for the next lane;
- inspect next-lane allowed files and dependency surfaces;
- preflight frozen Expansion against current `main`;
- compute likely Dynamic/Expansion/global merge conflicts read-only;
- prepare global integration worktree/branch plan;
- prepare the final global test matrix and provenance/ancestry checks;
- reproduce/cache known base-existing failures;
- audit docs, receipts, release metadata, leakage, paths, and source boundaries;
- precompute reviewer prompts and exact checklists;
- perform read-only dependency/API inventory work.

A controller that simply waits while safe work exists is violating V6 scheduling policy.

---

## 7. Speculative/preparatory source work

V6 permits carefully bounded speculative implementation for a future lane before its hard dependency freezes, **only in an isolated speculative worktree/branch**.

Rules:

1. Speculative work may touch only that future lane's declared allowed files.
2. It must never modify the live upstream lane/reviewer worktree.
3. It must never be called approved, promoted, frozen, or release-ready.
4. It must record the upstream provisional SHA/interface it assumed.
5. It may be discarded without consequence.
6. Once the dependency freezes, create the authoritative future-lane branch from the **actual promoted dependency head**.
7. Reapply/cherry-pick/copy only unreviewed speculative changes that still make sense; resolve against the real frozen dependency.
8. Run normal V6 focused gates on the authoritative branch.
9. Obtain a fresh exact-SHA independent review. A speculative SHA can never inherit approval.
10. Reviewed histories are never rebased; only unreviewed speculative work may be replayed/recreated.

Prefer read-only/test/preflight preparation when likely interface churn is high. Prefer speculative implementation when the declared interface is stable and the likely time saving is material.

---

## 8. Isolation and ownership

Parallel source-changing workers require separate Git worktrees and branches.

Never run two source-changing workers against the same worktree.

Each dispatched source task must declare:

- role/worker identity;
- branch/worktree;
- exact base/provisional base;
- allowed files;
- forbidden files;
- dependencies assumed;
- output expected;
- whether the work is authoritative or speculative;
- stop conditions.

Two workers may run concurrently only if their write sets do not overlap or if the controller explicitly classifies one output as disposable analysis rather than source.

---

## 9. Resource-aware concurrency budget

V6 requires useful concurrency, not uncontrolled oversubscription.

The controller must inspect current processes/load before dispatching heavy work and maintain a resource budget.

Default rules on a single developer workstation:

- at most **one repository-wide/full pytest sweep** at a time;
- at most **one repository-wide mypy/static mega-gate** at a time unless measurements show safe headroom;
- never run duplicate Opus reviews for the same SHA;
- never run duplicate Muse remediation for the same finding/worktree;
- multiple lightweight read-only/preflight tasks may run concurrently;
- multiple builders may run concurrently only in isolated worktrees with disjoint ownership;
- reviewer work on one lane may overlap builder/preflight work for other lanes;
- do not use `pytest -n` or high process fan-out when a lane/research guard forbids it.

If CPU/memory pressure would materially slow the critical-path task, prefer lightweight analysis/preparation rather than another heavy test/model process.

---

## 10. V5 fast gates remain the per-candidate gate schedule

V6 keeps the V5 stable-candidate gate model:

### Iteration gate

During ordinary Muse/remediation iteration, run focused discriminating checks only:

- lane-focused tests;
- directly affected dependency tests;
- permanent adversarial/mutation regressions;
- relevant Ruff/format;
- relevant strict mypy;
- compile/import sanity;
- `git diff --check`;
- exact scope/protected-path/leakage/secret checks;
- provenance/identity/research-hold checks.

Do not run the giant full repository pytest sweep after every tiny remediation.

### Candidate gate

The controller independently reruns focused/affected/adversarial/static/provenance gates, commits/pushes, reconciles all exact-SHA identities, then launches fresh independent review.

### REQUEST CHANGES loop

- freeze the rejected SHA and findings;
- turn each reproducible exploit into a permanent regression where feasible;
- dispatch narrow remediation;
- consume result automatically;
- focused gates only;
- new SHA;
- fresh independent review.

### Stable approved candidate gate

After independent approval, run expensive broad regression/static/cross-lane acceptance **once** on the stable approved SHA before promotion.

A candidate-caused source defect requires a new source SHA and fresh review. A failure proven unchanged on the exact base is recorded as base-existing rather than repeatedly burning remediation cycles.

---

## 11. Evidence/check caching

A successful check may be reused only when its identity inputs are unchanged.

Cache key should include, as applicable:

- exact source SHA or exact file/blob set;
- exact command and arguments;
- dependency/lockfile identity;
- environment/runtime identity relevant to the check;
- fixture/artifact fingerprints;
- policy/validator version.

Do not rerun an expensive unchanged check merely because time passed.

Invalidate cached evidence when any relevant input changes.

A cached check cannot replace a required fresh exact-SHA independent review.

---

## 12. Reviewer wait-time work stealing

When an exact SHA enters `REVIEWING`, the controller should immediately fill the reviewer latency window.

For the current E3 campaign, examples are:

### While Lane 11 is under Opus review

Safe concurrent work includes:

- Lane 12 read-only contract/allowed-file inventory;
- Lane 12 validator and hostile-case planning;
- optional speculative Lane 12 test/docs scaffolding in a separate worktree based on the current Lane 11 candidate, clearly marked speculative;
- read-only Expansion `85a6d98464ba5065f578632fd97456b91fa6ab0e` preflight against current `main`;
- global integration conflict forecast;
- final global gate matrix preparation;
- ancestry/provenance/release receipt preparation;
- baseline-failure reproduction/cache where safe.

Do not alter the exact Lane 11 review candidate.

### While Lane 12 is under Opus review

Safe concurrent work includes:

- global integration branch/worktree preflight;
- source-tree conflict forecast for frozen Expansion + provisional Dynamic + current main;
- final integration validator/checklist preparation;
- final reviewer prompt/attack plan preparation;
- docs/release/provenance/leakage audit.

Do not present provisional Dynamic as frozen until Lane 12 actually promotes/freezes.

### While final global SHA is under Opus review

Do not change that exact candidate. Prepare only non-source-changing release bookkeeping, final report skeleton, and exact merge command/guard conditions. Any source fix creates a new global SHA and a fresh final review.

---

## 13. Parallel review policy

Independent reviewers may work concurrently on **different** exact SHAs or different read-only analysis tasks when resource/account quotas allow.

For a single promotable SHA, designate exactly one authoritative independent review verdict unless the lane contract explicitly requires multiple reviewers.

Additional adversarial reviewers may be used as non-authoritative attack generation, but they do not replace the required designated verdict and must not create conflicting approval bookkeeping.

---

## 14. Background task recovery

A completed child task is a scheduling event.

When output says `completed (exit code 0)`, the controller must immediately consume it and advance the DAG.

If a wrapper says `Waiting for task`:

1. inspect the process table;
2. if child alive, keep that child and dispatch other safe work;
3. if child dead, recover from worktree/output/receipts/Git/GitHub;
4. never launch a duplicate merely because wrapper output is empty;
5. preserve valid partial edits after interrupted workers;
6. launch only minimal continuation when needed.

Routine task completion must not require the owner to type `continue`.

---

## 15. Current campaign application

### Lane 11

Lane 11 remains authoritative only after its exact SHA receives fresh independent approval and the stable-candidate broad gate passes.

**During any Lane 11 Muse/Opus wait, the controller must concurrently prepare safe Lane 12/global work per §12.**

### Lane 12

After Lane 11 promotion, reconcile any speculative Lane 12 work onto a branch created from the actual promoted Lane 11 head. Run V6 gates and fresh exact-SHA review. After promotion, freeze Dynamic.

### Global integration

Before Dynamic freeze, read-only/speculative integration preflight is allowed. The authoritative global branch is created only from the actual frozen inputs.

Final inputs must include:

- frozen Dynamic SHA;
- frozen Expansion V1 SHA `85a6d98464ba5065f578632fd97456b91fa6ab0e`;
- current `main` history, including owner-authorized controller policy/documentation advances.

Do not rebuild Expansion and do not rebase reviewed histories.

During integration remediation use focused/cross-feature gates. Once source-stable, run the complete global regression/static/validator matrix, then launch a fresh exact-SHA Opus integration audit. Only exact-SHA APPROVE authorizes merge to `main`.

---

## 16. Controller state/handoff requirements

A controller handing work to another agent must leave enough repo/GitHub state that the successor can resume without reconstructing the campaign from chat history.

At minimum record:

- current DAG node states;
- exact authoritative branch/SHA per active lane;
- immutable rejected SHAs and verdicts;
- currently running task identifiers where available;
- promoted/frozen SHAs;
- current `main` SHA;
- research-hold literals;
- outstanding hard dependencies;
- speculative branches/worktrees and the provisional base each assumed;
- cached broad/check receipts and their identity keys;
- next READY and PREPARABLE nodes.

GitHub issues/PRs plus committed policy/receipts are preferred over chat-only state.

---

## 17. Stop conditions

The controller stops for owner input only when:

- a genuine researcher/scientific decision is required;
- continuing would violate the scientific hold;
- a source-boundary conflict cannot be resolved inside the authoritative lane contract;
- primary evidence is contradictory and requires owner judgment;
- an unrecoverable authentication/external-service failure blocks the critical path and there is no other safe work.

Ordinary test failures, reviewer remediation, task recovery, Git bookkeeping, speculative work disposal, conflict preflight, and source-identical promotion are controller responsibilities.

---

## 18. One-line operating model

> **Keep the exact-SHA trust chain serial where it must be serial; keep the rest of the factory busy in isolated worktrees.**
