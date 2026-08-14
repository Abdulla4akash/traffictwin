# Claude / Fable controller instructions

If you are acting as a controller, integrator, reviewer coordinator, or multi-agent orchestrator in this repository, read these files before dispatching work:

1. `CONTROLLER.md`
2. `docs/quality/controller_concurrent_orchestration_policy_v6.md`
3. the current lane's GitHub issue/contract

The current owner-authorized scheduling model is **V6 concurrent orchestration**.

Do not serialize the whole factory merely because one Muse, Opus, test, or GitHub operation is waiting. Maintain the dependency DAG and dispatch safe READY/PREPARABLE work in isolated worktrees during wait time.

Do not weaken exact-SHA review. Promotable source still requires fresh independent read-only exact-SHA approval; source-changing fixes create new SHAs; approved SHAs remain frozen; final global source receives a fresh integration-level audit.

For the current E3 campaign, the research execution hold remains absolute and `research_workloads_launched = 0` until the owner explicitly changes it.

When resuming from another controller, trust committed GitHub policy/issues/PRs/receipts and exact Git state over stale chat prose. Recover running/stale background tasks before duplicating them.
