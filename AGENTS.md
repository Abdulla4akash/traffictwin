# TrafficTwin Agent Instructions

## Current release authority

The authoritative repository state is `main` at:

`337f1624e5ffe188393554b1110a35ababcce8e1`

This is the integrated TrafficTwin release composition containing the frozen Expansion V1 product and the final frozen Dynamic Resource V2 product. Do not treat older v0.6/v0.7/v0.8 campaign branches, alpha tags, lane worktrees, handoff prompts, or historical ownership grants as the current source of truth.

Read, in order, before architectural or source-changing work:

1. `CONTROLLER.md` for multi-agent trust/orchestration rules.
2. `docs/traffictwin_product_design_v3.md` for the current product design.
3. `docs/traffictwin_use_cases_v3.md` for current bounded use cases.
4. `docs/architecture_current_release.md` for the current release architecture.
5. `docs/quality/final_release_status_20260815.md` for exact release identity and scientific hold state.
6. The task-specific code, tests, issue, ADR, receipt, and historical design documents needed for the requested change.

Historical documents remain evidence and design history; they must not silently override the current release overlay.

## Roles and trust model

- **Human owner:** final authority over scope, scientific execution, release decisions, and policy changes.
- **Controller/integrator:** Fable 5 or another explicitly designated controller. Coordinates the DAG, composes reviewed work, runs deterministic gates, and preserves exact-SHA provenance. A controller may also be designated as a source-changing builder, but must never self-approve that source.
- **Builder/remediator:** a designated source-changing worker such as Muse (`meta / muse-spark-1.2-contributor / xhigh`) or Fable 5 xhigh. Builder output is untrusted until gates and independent review pass.
- **Independent reviewer:** fresh Claude Opus 5 xhigh, read-only, reviewing the exact pushed SHA. Reviewer findings must be concrete and reproducible; reviewer code edits are forbidden.
- **Deterministic trust infrastructure:** Git/GitHub, isolated worktrees, pytest, Ruff, mypy, validators, fingerprints, receipts, and exact source identity.

`MUSE_EXIT_CODE=0` or `REVIEW_EXIT_CODE=0` means only that the CLI process exited successfully. It is not an approval. Promotable source requires an explicit terminal verdict such as `VERDICT: APPROVE exact SHA <SHA>`.

Any source-changing commit creates a new SHA and invalidates predecessor approval. Never rebase reviewed histories, force-push `main`, or run two source-changing workers in the same worktree.

## Current scientific truth boundary

The E3 software/product surface is implemented and integrated, but **E3 scientific execution was not authorised and was not run**. Preserve exactly until the owner explicitly changes the policy:

- `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`
- `E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`
- `evidence_state = NOT_EXECUTED`
- `result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`
- `research_workloads_launched = 0`

Never infer scientific evidence from software readiness, tests, a merged release, or a working UI. Do not launch E3 research workloads unless the owner explicitly changes this hold.

## Product/scientific constraints

- Keep evidence standing, provenance, denominators, exclusions, missingness, and limitations explicit.
- Metrics and diagnostic findings are deterministic code outputs; an LLM must not invent scientific measurements or results.
- Never fabricate provider semantics, live Manchester traffic, simulator output, human review, approvals, credentials, experimental results, or deployment state.
- BODS bus positions are not general road traffic.
- TfGM signal locations are not signal state/phase/queue telemetry.
- National Highways operational data is strategic-road context, not complete Manchester city-road coverage.
- Missing evidence is not zero.
- Do not call a simulation ground truth or a city-wide live twin.
- Vehicle actor mode choice (`Local`/`V2I`/`V2V`) is distinct from exact RSU selection.
- Use **deterministic infrastructure-side RSU load management** for the implemented deterministic placement/forwarding layer. Do not call simulated resource scaling a real Kubernetes deployment.
- RSU waiting-room/queue capacity is distinct from compute/service capacity.
- Preserve `offered`, `admitted`, `rejected`, `forwarded`, `compute_completed`, `returned`, and `deadline_success` as distinct lifecycle/accounting concepts.

## Working rules

For a source-changing task:

1. Start from current `main` unless the task explicitly names another reviewed base.
2. Work in an isolated branch/worktree.
3. Inspect existing implementation and tests before editing.
4. Keep the change bounded to the requested contract.
5. Add or preserve biting regressions for concrete defects.
6. Run focused/adversarial/static gates during remediation.
7. Run the expensive broad suite only at a stable candidate boundary unless the task requires otherwise.
8. Commit and push the exact candidate before independent review.
9. Bind review to the exact pushed SHA.
10. For final integration, run complete global gates and a bounded integration audit focused on new/reintroduced composition defects.

A final integration reviewer may block only concrete final-composition defects affecting functionality, safety, truth, provenance, security, deterministic build/reproduction, or cross-feature integration. Style preferences, optional refactors, unrelated debt, speculative hardening, and requests to run unauthorised experiments are non-blocking.

## Historical records

Old ownership sections, v0.7 handoff prompts, v0.8 lane documents, review receipts, and prior designs remain useful historical evidence. Do not rewrite them merely to make history look current. Add a current overlay or a new version when the meaning changed materially.
