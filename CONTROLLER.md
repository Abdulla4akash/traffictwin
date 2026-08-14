# TrafficTwin controller entrypoint

**READ THIS BEFORE ORCHESTRATING ANY MULTI-AGENT CAMPAIGN IN THIS REPOSITORY.**

Current owner-authorized controller policy:

`docs/quality/controller_concurrent_orchestration_policy_v6.md`

V6 supersedes V5 for scheduling/concurrency. V5 trust rules remain preserved through V6.

## Required operating model

1. Maintain a dependency DAG with `BLOCKED`, `PREPARABLE`, `READY`, `RUNNING`, `REVIEWING`, `REQUEST_CHANGES`, `APPROVED`, `PROMOTED`, and `FROZEN` states.
2. Keep the exact-SHA trust chain serial only where evidence identity requires it.
3. When any critical-path child is waiting, immediately dispatch safe READY/PREPARABLE work in isolated worktrees instead of idling the factory.
4. Never run two source-changing workers in the same worktree.
5. Future-lane speculative work is allowed only in an isolated branch/worktree, is never authoritative, and must be reconciled onto the actual promoted dependency head before fresh gates/review.
6. Every promotable source-changing SHA needs a fresh independent read-only exact-SHA review. Any source change invalidates predecessor approval.
7. Use focused/adversarial/static gates during remediation loops. Run the expensive broad suite once at the stable approved-candidate boundary.
8. Turn reproducible reviewer exploits into permanent regressions.
9. Cache expensive checks only when their exact identity inputs are unchanged.
10. Consume completed background tasks automatically; `Waiting for task` describes one child, not the whole factory.
11. Use resource-aware concurrency: one heavy repo-wide suite at a time by default, multiple safe lightweight/preflight workers where useful.
12. Final global source receives complete global gates plus a fresh independent exact-SHA integration audit before merge to `main`.

## Current E3 hold

Until the owner explicitly lifts it, preserve exactly:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Do not launch E3 scientific workloads.

## Current campaign concurrency example

While Lane 11 is under independent review, do not just wait. In separate isolated state, prepare Lane 12 validator/hostile cases, preflight frozen Expansion vs current main, forecast global conflicts, prepare global gates/ancestry/provenance, and cache safe base-existing checks.

While Lane 12 is under review, preflight global integration and final audit inputs without treating provisional Dynamic as frozen.

The canonical V6 file contains the full rules. If this entrypoint and another historical controller document disagree on scheduling, V6 wins unless a newer owner-authorized policy explicitly supersedes it.
