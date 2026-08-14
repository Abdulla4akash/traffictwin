# TrafficTwin repository instructions for coding agents

For ordinary code tasks, obey the repository's existing source/test conventions and lane boundaries.

For any multi-agent orchestration, controller, integration, review-coordination, or campaign-resume task, **read `CONTROLLER.md` first**, then read `docs/quality/controller_concurrent_orchestration_policy_v6.md` and the relevant GitHub lane issue.

Key V6 rule: preserve the exact-SHA trust chain, but do not idle the entire factory while one child is waiting. Maintain a dependency DAG and run safe READY/PREPARABLE work concurrently in isolated worktrees.

Never infer scientific authorization from software readiness. The current E3 campaign remains `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED` with `research_workloads_launched = 0` until the owner explicitly lifts the hold.
