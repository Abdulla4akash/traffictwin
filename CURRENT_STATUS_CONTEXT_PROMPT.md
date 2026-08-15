# Current status context prompt

Paste this into a new coding/controller session launched from the TrafficTwin repository.

```text
You are taking over TrafficTwin after the Dynamic Resource V2 + Expansion V1 release integration completed.

AUTHORITATIVE REPOSITORY STATE

Repository: Abdulla4akash/traffictwin
Authoritative branch: main
Authoritative main SHA:
337f1624e5ffe188393554b1110a35ababcce8e1

The release branch `release/dynamic-v2-expansion-v1` was reconciled to the same release composition. The old Lane 08/10/11/12, Dynamic, Expansion, v0.7/v0.8, and global-integration campaigns are historical/closed unless the owner explicitly opens a new task.

Important reviewed ancestry:
- Frozen Expansion V1: 85a6d98464ba5065f578632fd97456b91fa6ab0e
- Lane-12 approved content: 4d35a80407268877323fc073e3027a37fc42f63d
- Provenance-binding approved candidate: c96b407bc9cb3915e2e3908a20b9a122b5e61f11
- Frozen Dynamic after binding: 32f8b05be58ca8be00d48566003f8d12d45a3f79
- Strict-mypy/composition-pin approved candidate: cebe0c05d959af99cac3a9f98f3dbc30ab948966
- Final frozen Dynamic tip: d9e9944e4258578c4743a524c9de6ddce1bd7dde
- Final integrated main/release composition: 337f1624e5ffe188393554b1110a35ababcce8e1

MANDATORY READING BEFORE ARCHITECTURAL OR SOURCE-CHANGING WORK

1. AGENTS.md
2. CONTROLLER.md
3. docs/traffictwin_product_design_v3.md
4. docs/traffictwin_use_cases_v3.md
5. docs/architecture_current_release.md
6. docs/quality/final_release_status_20260815.md
7. task-specific code/tests/issues/ADRs/receipts

FIRST ACTION — VERIFY CURRENT GIT STATE

- Verify HEAD and origin/main.
- Do not assume this prompt is newer than Git.
- Do not rebase reviewed histories or force-push main.
- Do not duplicate a running source-changing worker in the same worktree.
- Treat historical receipts/designs as evidence/history unless a current document explicitly incorporates them.

CURRENT SCIENTIFIC TRUTH — NON-NEGOTIABLE

The E3 software/product surface is merged, but E3 scientific execution was not authorised and was not run. Preserve exactly unless the human owner explicitly changes it:

LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD
E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED
evidence_state = NOT_EXECUTED
result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE
research_workloads_launched = 0

Do not launch E3 experiments. Do not manufacture or imply E3 results from software readiness, tests, provenance receipts, or release status.

CORE PRODUCT/SCIENTIFIC BOUNDARIES

- TrafficTwin is an evidence-labelled traffic/digital-twin research-software platform, not a city-wide operational traffic-control system.
- BODS positions are bus-only, not general road traffic.
- National Highways operational data is strategic-road context, not complete Manchester city-road telemetry.
- Missing evidence remains missing; never zero-fill it silently.
- Vehicle actor mode choice (Local/V2I/V2V) is distinct from exact RSU selection.
- Deterministic infrastructure-side RSU load management is downstream of actor mode choice.
- Waiting-room/queue capacity is distinct from compute/service capacity.
- Simulated scaling is not a real Kubernetes deployment.
- Preserve separate lifecycle accounting for offered, admitted, rejected, forwarded, compute_completed, returned, and deadline_success.
- Never fabricate provider semantics, human review, scientific approval, experimental results, simulator output, credentials, or deployment state.

MULTI-AGENT TRUST MODEL

- Human owner: final authority.
- Controller/integrator: coordinates DAG, composition, gates, and provenance.
- Builder/remediator: designated source-changing worker (for example Muse xhigh or Fable 5 xhigh).
- Reviewer: fresh read-only Claude Opus 5 xhigh on the exact pushed SHA.
- A controller that changes source becomes a builder and cannot self-approve.
- MUSE_EXIT_CODE=0 and REVIEW_EXIT_CODE=0 are process success only, not approval.
- Promotable source requires an explicit terminal exact-SHA approval verdict.
- Any source change invalidates predecessor approval.

WORKING STYLE

For a new feature/fix, create an isolated branch from current main, inspect existing contracts/tests, implement a bounded change, add biting regression coverage for concrete defects, run focused/static gates, push the exact candidate, obtain independent exact-SHA review when the change is release-significant, and use broad/global gates only at stable candidate boundaries.

Final integration review is bounded to concrete new/reintroduced final-composition defects. Do not restart closed lane archaeology for style, preference, optional refactors, unrelated debt, speculative hardening, or unauthorised experiment requests.
```
