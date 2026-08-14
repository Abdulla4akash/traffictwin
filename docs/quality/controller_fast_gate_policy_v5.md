# TrafficTwin controller fast-gate policy v5

Status: **OWNER-AUTHORIZED CONTROLLER SCHEDULING POLICY**

Effective scope: the remaining `e3-dynamic-resource-v2` engineering campaign after Lane 10 reaches an approved/promoted standing, specifically Lane 11, Lane 12, Dynamic freeze, global integration, and the final release audit.

This policy changes **gate scheduling only**. It does not weaken the scientific hold, source ownership, exact-SHA review, or approval-transfer rules.

## 1. Non-negotiable trust invariants

1. Muse remains the source-changing worker unless a lane contract explicitly says otherwise.
2. Fable remains controller/integrator and must not self-approve source changes.
3. Every source-changing candidate that can be promoted requires a **fresh read-only Claude Opus 5 xhigh exact-SHA review**.
4. Any source-changing commit creates a new SHA and invalidates every approval for the predecessor.
5. Approved SHAs are frozen. Promotion is source-identical/mechanical only.
6. A final globally composed source SHA requires a fresh Opus 5 xhigh integration-level audit before merge to `main`.
7. No force-push to `main` and no rebase of reviewed histories.
8. Hosted CI may be recorded as `HOSTED_CI_UNAVAILABLE`; it must never be represented as passed when it did not run.

## 2. Immutable E3 scientific hold

The following remain exact throughout this engineering campaign:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Forbidden until the researcher explicitly lifts the hold: E3a/E3b/E3c scientific execution, 3600-step cells, reduced/pilot/exploratory campaigns, Manchester comparative scientific execution, multi-draw scientific workloads, benchmarks presented as scientific evidence, and empirical/statistical inference from unexecuted E3 work.

Software/unit/construct correctness testing remains allowed where already authorized by the lane contract.

## 3. Why v5 exists

Previous lanes repeatedly reran very large repository-wide suites between tiny remediation commits. This produced long wall-clock cycles while Opus was still discovering new fail-open classes that were not exercised by those broad suites.

V5 therefore moves expensive broad regression to the **stable-candidate boundary** and makes previously discovered reviewer attacks permanent fast pre-review gates.

The objective is lower latency without reducing independent review depth.

## 4. Gate schedule for Lane 11 and Lane 12

### Stage A — worker iteration gate

After Muse edits, run only the cheapest discriminating checks required to reject an obviously bad worktree:

- lane-focused tests;
- tests covering directly changed dependency surfaces;
- the permanent adversarial/mutation corpus relevant to the changed code;
- `ruff format --check` and `ruff check` for the changed/owned paths or repository if the command is already cheap;
- relevant strict mypy targets;
- Python compile/import sanity where relevant;
- `git diff --check`;
- exact ownership/scope check;
- protected-path/leakage/secret checks required by the lane.

Do **not** run the full repository pytest sweep during ordinary worker iteration.

### Stage B — controller candidate gate before Opus

Fable independently validates the proposed candidate before committing/pushing it for review:

- all lane-focused tests;
- all regressions for every prior Opus blocker applicable to the lane;
- dependency/contract tests whose exercised surfaces actually changed;
- lane-specific validators;
- strict static/type/scope/provenance checks;
- exact research-hold assertions;
- exact candidate metadata/receipt integrity.

A full repository test sweep is **not required at this point** unless the candidate has a genuinely broad blast radius that cannot be bounded by dependency tests.

If Stage B fails, dispatch a narrow Muse remediation and repeat Stage A/B without performing a broad repository sweep.

### Stage C — fresh Opus exact-SHA review

Once Stage B is clean:

1. commit the candidate;
2. push it;
3. prove equality across local HEAD, remote branch, PR head, ledger, implementation receipt, and issue-declared candidate;
4. launch a completely fresh `claude-opus-5` / `xhigh` read-only exact-SHA review.

Required verdict:

- `VERDICT: APPROVE exact SHA <FULL_SHA>`; or
- `VERDICT: REQUEST CHANGES exact SHA <FULL_SHA>`.

No approval transfer is permitted.

### Stage C-R — remediation after REQUEST CHANGES

When Opus requests changes:

1. permanently record the rejected SHA and its findings;
2. convert each reproducible reviewer exploit into a permanent regression/adversarial test when feasible;
3. send only actionable blockers and explicitly requested secondary items to Muse xhigh;
4. consume the worker result immediately;
5. rerun focused/affected/adversarial/static gates only;
6. create a new SHA;
7. launch a completely fresh Opus review.

**Do not rerun the whole repository suite between each Opus remediation round.**

Examples of attacks that should remain permanent fast gates once discovered include provenance-SHA misattribution, omission/type-confusion, recursive-scan neutering, strict-bool bypasses, forbidden-claim variants, Unicode/NFKC/confusable/zero-width/fullwidth bypasses, and sidecar/config identity drift.

### Stage D — broad regression after Opus approval

After Opus approves the exact candidate, and before mechanical promotion, run the expensive broad regression **once for that stable approved source SHA**:

- full relevant repository/unit regression appropriate to the lane;
- repository-wide strict mypy where required by the campaign;
- repository-wide Ruff/format if required;
- cross-lane dependency/acceptance suites;
- exact baseline reproduction for any known pre-existing failures.

If Stage D passes, promotion may proceed source-identically.

If Stage D exposes a candidate-caused source defect, the approved SHA is not modified. Record the failure, create a new Muse remediation SHA, and obtain a fresh Opus review before promotion.

If Stage D failures reproduce unchanged on the exact base, record them as baseline-existing with exact counts/evidence rather than repeatedly burning remediation cycles for unrelated failures.

### Stage E — post-promotion check

After source-identical promotion:

- verify promoted source identity/ancestry;
- rerun lane-focused acceptance/smoke/contract tests;
- do not immediately repeat the same full repository sweep unless promotion/integration itself changed source or dependency composition.

## 5. Background-task handoff rule

A completed Muse or Opus background task is an event to consume, not a reason to return to an idle controller prompt.

When a background task ends, Fable must immediately:

1. recover the task output if available;
2. inspect worktree/Git/process state directly if the wrapper output is stale or empty;
3. advance the state machine to the next gate;
4. avoid launching a duplicate worker/reviewer while the original child is genuinely alive.

If a task wrapper says `Waiting for task` but the child process no longer exists, recover from the worktree, receipts, review files, Git state, and GitHub metadata and continue.

Routine transitions must not require the owner to type `continue`.

## 6. Safe parallelism

When no scientific workload is running, Fable may parallelize independent **cheap** controller checks where safe, for example Ruff, compile/import checks, metadata/scope validation, and independent focused test groups.

Do not create uncontrolled pytest/process oversubscription. Do not parallelize anything that can compromise deterministic receipts or exact-SHA attribution.

## 7. Reviewer learning loop

Every new Opus blocker should improve the harness:

`Opus discovery -> permanent regression/adversarial test -> future pre-review gate`

The goal is that Opus increasingly spends time finding genuinely novel problems instead of rediscovering the same exploit class in later lanes.

Regression tests must exercise the real production safety path. A test that merely duplicates the implementation's logic is not acceptable mutation coverage.

## 8. Lane 11 and Lane 12 application

Issues #105 and #106 retain their existing source boundaries, deliverables, dependency rules, and exact-SHA handoff requirements.

This v5 policy supersedes only any implied requirement to run a giant full-repository suite after every small remediation. The lane contracts remain authoritative for what may be changed; this document is authoritative for when controller gates are scheduled.

## 9. Dynamic freeze and global integration

After Lane 12 approval/promotion:

1. freeze the final Dynamic SHA;
2. validate the already frozen Expansion V1 SHA `85a6d98464ba5065f578632fd97456b91fa6ab0e` without rebuilding it;
3. compose frozen Dynamic + frozen Expansion + current `main` history on a new global integration branch;
4. do not rebase reviewed histories;
5. resolve genuine cross-feature source defects through Muse -> new SHA -> fresh Opus review;
6. once the integrated tree is source-stable, run the complete global regression/static/validator matrix;
7. launch a fresh Opus 5 xhigh integration audit on the exact final global SHA;
8. merge to `main` only after `VERDICT: APPROVE exact SHA <FINAL_GLOBAL_SHA>` and exact-head reconciliation.

For global integration, the expensive global regression belongs at the stable integration-candidate boundary rather than after each tiny conflict remediation. Focused conflict/dependency tests run during iteration; full global gates run when the composed tree is stable enough for final review.

## 10. Stop conditions

Fable should stop for owner input only when:

- a genuine researcher/scientific decision is required;
- proceeding would violate the E3 execution hold;
- a source-boundary conflict cannot be resolved inside the lane contract;
- an unrecoverable authentication/external-service failure prevents continuation;
- source evidence is contradictory in a way that requires owner judgment.

Routine test failures, reviewer remediation, Git bookkeeping, task-output recovery, and source-identical promotion are controller responsibilities and should continue automatically.
