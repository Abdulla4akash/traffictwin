# TrafficTwin controller entrypoint

**READ THIS BEFORE ORCHESTRATING ANY MULTI-AGENT WORK IN THIS REPOSITORY.**

## Current authority

Authoritative `main` release:

`337f1624e5ffe188393554b1110a35ababcce8e1`

The Dynamic Resource V2 + Expansion V1 composition is merged. The previous Lane 08/10/11/12 campaign and global-integration campaign are closed historical work. Do not reopen them simply because historical prompts, issues, or receipts describe them as active.

Current owner-authorized orchestration policy remains:

`docs/quality/controller_concurrent_orchestration_policy_v6.md`

V6 governs scheduling/concurrency; the exact-SHA trust rules remain mandatory.

## Required operating model

1. Start new work from current `main` unless the owner/task explicitly names another reviewed base.
2. Maintain a dependency DAG with explicit states such as `BLOCKED`, `PREPARABLE`, `READY`, `RUNNING`, `REVIEWING`, `REQUEST_CHANGES`, `APPROVED`, `PROMOTED`, and `FROZEN`.
3. Keep exact-SHA trust serial where evidence identity requires it, but do not idle unrelated safe work while another child waits.
4. Never run two source-changing workers in the same worktree.
5. Every promotable source-changing SHA requires a fresh independent read-only exact-SHA review. Any source change invalidates prior approval.
6. A controller that edits source becomes a builder for that SHA and cannot self-approve it.
7. Use focused/adversarial/static gates during remediation; use the expensive broad suite at stable candidate boundaries.
8. Turn concrete reviewer exploits into permanent biting regressions.
9. Cache checks only when exact source/dependency/environment identity is unchanged.
10. Prefer one heavy repo-wide suite at a time; parallelise safe lightweight/preflight work where useful.
11. Never rebase reviewed histories or force-push `main`.
12. Final global source receives complete gates plus a fresh independent bounded integration audit before merge.

`MUSE_EXIT_CODE=0` and `REVIEW_EXIT_CODE=0` are process statuses only. Approval requires an explicit terminal verdict bound to the exact SHA.

## Bounded final-review rule

A final integration reviewer may block only a concrete defect that:

- affects the final composed exact SHA;
- concerns functionality, safety, truthfulness, provenance, security, deterministic build/reproduction, or cross-feature integration;
- is new or reintroduced by the current composition; and
- has a concrete reproduction, failing probe, exact contradiction, or surviving mutation.

Style, optional refactors, alternate architecture preferences, unrelated debt, speculative hardening, and generic requests for additional tests without a surviving defect are non-blocking. Already-approved lane-local design must not be reopened unless composition invalidates it.

## E3 execution hold — still absolute

The merged software does **not** authorise E3 scientific execution. Preserve exactly:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Do not launch E3 scientific workloads unless the owner explicitly changes this policy.

## Current design/read order

Before dispatching architectural work, read:

1. `AGENTS.md`
2. `docs/traffictwin_product_design_v3.md`
3. `docs/traffictwin_use_cases_v3.md`
4. `docs/architecture_current_release.md`
5. `docs/quality/final_release_status_20260815.md`
6. the task-specific issue/contract/tests/receipts

Historical V5/V6 campaign examples, v0.7/v0.8 handoffs, and lane receipts remain evidence of how the release was produced, not instructions to resume a closed campaign.
