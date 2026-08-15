# Claude / Fable controller instructions

If you are acting as a controller, integrator, reviewer coordinator, source-changing builder, or multi-agent orchestrator in this repository, read these files before dispatching work:

1. `AGENTS.md`
2. `CONTROLLER.md`
3. `docs/traffictwin_product_design_v3.md`
4. `docs/traffictwin_use_cases_v3.md`
5. `docs/architecture_current_release.md`
6. `docs/quality/final_release_status_20260815.md`
7. the task-specific issue/contract/tests/receipts

## Current repository truth

Authoritative `main` is `337f1624e5ffe188393554b1110a35ababcce8e1`. The prior Dynamic Resource V2, Expansion V1, Lane 12, and global-release campaigns are closed and merged. Do not resume them from stale chat context or historical lane prompts.

The owner-authorized scheduling model remains **V6 concurrent orchestration**. Preserve the exact-SHA trust chain while allowing safe READY/PREPARABLE work in isolated worktrees during waits.

A source-changing Fable session is a builder, not an approver. Promotable source requires a fresh independent read-only exact-SHA review. `REVIEW_EXIT_CODE=0` is not approval; require an explicit terminal exact-SHA verdict.

Final integration review is bounded to concrete new/reintroduced composition defects. Do not reopen approved design because of style, preference, optional refactoring, unrelated debt, speculative hardening, or a desire to run additional experiments.

## Scientific hold

The merged E3 product contains software/acceptance/provenance capability only. Scientific execution remains unauthorised. Preserve:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Never infer experimental results from a merged feature, green test suite, or release receipt.

When resuming from another controller, trust current Git/GitHub state, exact committed docs, tests, and receipts over stale prose. Recover running/stale background tasks before duplicating them, and never run concurrent source-changing workers in the same worktree.
