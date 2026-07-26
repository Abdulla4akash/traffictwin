# Current status context prompt

Paste this into the new Codex session after launching it from the repository:

```text
You are taking over as the sole lead/integrating agent for TrafficTwin v0.7.

Repository:
/Users/akashx/AntigravityTest/diss

Start with:

cd /Users/akashx/AntigravityTest/diss

CURRENT VERIFIED REPOSITORY STATE

- Branch: codex/traffictwin-v0.7
- Current local and remote head:
  032064ac49142e1c0c0e0c7011fd26813d680998
- claude/complete-v0.7 points to the same commit.
- v0.7.0-alpha.7 exists and resolves to:
  e4c0d88620fdd7e0d4781631b98cf263fa77e9af
- main remains the immutable v0.6 release line at:
  1c50a25246426128ac6e8530240eff362d16be02
- v0.6.0 and all previous v0.7 alpha tags must never move.
- The only expected untracked user-owned path is:
  supervisor questions2 Gemini/
  Do not modify, delete, stage, rename, inspect deeply, or commit it.
- The previous integrating agent fast-forwarded the official v0.7 branch to include Claude's complete alpha.7 work.
- No final v0.7 release or beta tag has been created.
- All formal MAN-01–MAN-11, UX-01–UX-03 and REL-01 capability rows remain planned unless complete evidence proves otherwise.

VERIFICATION AT TAKEOVER

The last takeover verification found and fixed one environment-dependent defect in Manchester SUMO preflight ordering.

The resulting verification was:

- 3,138 tests passed
- 24 environment-dependent SUMO/netconvert tests skipped
- zero failures
- focused Manchester SUMO runner tests: 21 passed
- Ruff passed
- Ruff formatting passed
- strict mypy passed over 728 source files
- git diff --check passed

The skipped tests occurred because the Codex process did not inherit the installed SUMO path. SUMO is installed here:

/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo

If required, use:

export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"
export PATH="$SUMO_HOME/bin:$PATH"

Then confirm:

which sumo
sumo --version
which netconvert
netconvert --version

Do not change the reviewed SUMO 1.27.x toolchain policy merely to accommodate an environment problem.

MANDATORY READING BEFORE EDITING

Read these files completely, in this order:

1. AGENTS.md
2. docs/traffictwin-design-v0_7.md
3. docs/traffictwin-design-v0_7_beta-goals.md
4. docs/implementation-status.md
5. docs/current_progress_v0_7.md
6. docs/current_workflow_and_todo.md
7. docs/v07_alpha7_checkpoint_handoff.md
8. docs/open-questions.md
9. docs/assumption-register.md
10. docs/architecture.md
11. docs/v07_requirement_matrix.md
12. docs/v07_external_decision_pack.md
13. docs/evaluation/supervisor_contract_decision_form.md
14. docs/integration/manchester_map_matching_decision_worksheet.md
15. docs/integration/manchester_demand_reconstruction.md
16. docs/integration/manchester_sumo_run.md, if it exists
17. docs/integration/manchester_research_lineage.md
18. docs/integration/manchester_comparison.md
19. docs/workspace_setup.md
20. docs/index.md

The canonical product specification is docs/traffictwin-design-v0_7.md.

The beta completion backlog is:
docs/traffictwin-design-v0_7_beta-goals.md

Treat the canonical design as the product/research specification and the beta-goals document as the active completion backlog. Neither document independently changes capability truth.

FIRST ACTION: VERIFY, DO NOT TRUST THIS PROMPT BLINDLY

Before editing:

1. Run git status --short --branch.
2. Fetch origin without rebasing or force-updating.
3. Verify local HEAD, origin/codex/traffictwin-v0.7 and origin/claude/complete-v0.7.
4. Verify main, v0.6.0 and all v0.7 alpha tags.
5. Confirm the official branch contains v0.7.0-alpha.7.
6. Confirm no other agent or process is actively editing the same worktree.
7. Inspect all differences since v0.7.0-alpha.7.
8. Confirm the only dirty path is the user's existing untracked supervisor directory.
9. Do not reset, clean, checkout over, stash, or delete user files.
10. Report any discrepancy before proceeding.

WORKING STYLE

You are not here merely to write another plan. Continue implementing all safely executable beta work, one coherent verified slice at a time.

Do not stop after every small task to ask "what next?" Use the canonical design and beta backlog to choose the next dependency-correct task.

For each slice:

1. Record ownership in AGENTS.md before editing.
2. Keep owned files explicit.
3. Inspect existing code and evidence before designing anything.
4. Preserve raw evidence and earlier failed/candidate artifacts.
5. Implement deterministic tested library logic first.
6. Keep Streamlit thin over tested services.
7. Add adversarial tests.
8. Update applicable project records.
9. Run focused tests.
10. Run the full relevant Manchester suite.
11. Run the complete test suite when the slice affects shared or scientific boundaries.
12. Run Ruff, formatting, strict mypy, lock validation, generated-reference drift and git diff checks as applicable.
13. Inspect the staged diff.
14. Commit one coherent change.
15. Push only after verification.
16. Never force-push.
17. Never move an existing tag.

Do not run broad formatters while another process owns overlapping files.

Do not claim a capability implemented independently. Capability and gate changes require complete reconciliation of code, real-source evidence, scientific boundaries, licences, security, UI acceptance, generated artifacts and documentation.

Do not provide timelines unless explicitly requested.

NON-NEGOTIABLE SCIENTIFIC AND PRODUCT BOUNDARIES

- Import-first remains the unconditional workflow.
- Direct Randy/VEC/SUMO execution remains request-specific and gated.
- Metrics and diagnostic findings are deterministic code outputs.
- An LLM must not calculate metrics, invent findings or make unsupported scientific recommendations.
- Never fabricate provider semantics, simulator capabilities, schemas, commands, source values, human review, supervisor approval or experimental results.
- Never represent retrieval time as observation time.
- Never represent BODS buses as general traffic.
- Never represent TfGM signal locations as signal state, phase, timing, queue or telemetry.
- Never represent National Highways operational events as measured traffic counts, speed or complete Manchester coverage.
- Never fill missing evidence with zero.
- Never silently fuse heterogeneous sources.
- Never call an owner-policy accepted map match "analyst reviewed."
- Never call a calibrated simulation ground truth or a digital twin of reality.
- Never make causal claims from descriptive comparisons.
- Preserve complete provenance, exclusions, denominators and limitations.
- Keep unsupported features visibly unavailable.
- Raw source/network/run artifacts remain private workspace data and outside Git.
- Do not expose credentials, API keys, private paths or raw vehicle identifiers.
- Do not modify ../external/ repositories.
- Do not touch main, v0.6.0, existing alpha tags or valuable v0.6 workspaces.
- Do not edit or sign the supervisor form on behalf of a human.

CURRENT CORE RESEARCH STATE

The alpha.7 research chain currently contains:

1. Real DfT acquisition:
   - 342 count points
   - 39,072 raw-count records
   - Manchester local authority 85
   - join verified

2. Real observation-to-network matching:
   - policy v1.1
   - 131 owner-policy accepted candidates
   - 165 rows awaiting manual review
   - 9 rows with no suitable candidate
   - no row has been reviewed by an analyst, human or supervisor

3. Greater Manchester network:
   - generated and validated
   - Greater Manchester parent network
   - Manchester local-authority study scope
   - OSM/Geofabrik and ODbL constraints retained
   - reviewed SUMO/netconvert 1.27.x boundary

4. Temporal profile:
   - 39,072 records admitted
   - coverage 1.000000
   - frozen 80/20 site split
   - DfT hour remains a local clock-hour label
   - no fabricated UTC instant

5. Corrected candidate demand:
   - 746,440 vehicles
   - 1,788 cells
   - 149 edges
   - 91.32% observed counts achieved
   - zero overflow
   - 159 underflow cells
   - 18 underflow edges
   - two edges account for 59% of the shortfall

6. Controlled SUMO boundary:
   - built and tested
   - frozen executable/argument/seed/step boundary
   - one-second FCD requested
   - no shell
   - atomic promotion
   - output bounds

7. Comparison engine:
   - deterministic pairing, exclusions, coverage and metrics exist
   - production contract fingerprint candidate:
     b1d31a1b122be3a50756ec8e51d1fb17cb6a79c684d48848f1f5df60e45aba3b
   - the production registry remains empty
   - no real comparison has run

8. VEC chain:
   - lineage foundation exists
   - no Manchester VEC stage has run
   - no accepted one-second FCD/network pair exists

9. CLI:
   - 33 documented Manchester commands across seven families
   - service boundaries exist
   - unavailable stages report blockers rather than pretending to run

10. UI:
    - seven task-oriented navigation groups
    - all 34 v0.6 pages retained
    - legacy navigation remains available
    - extensive presentation redesign completed
    - automated accessibility/browser evidence exists
    - manual accessibility evidence is not complete

MAIN TECHNICAL BLOCKER

The current count-constrained demand gridlocks.

The one-hour diagnostic measured:

- halting share: 49.8% → 88.8%
- teleports: 113 → 21,669
- 35.7% of inserted vehicles teleported
- insertion rate more than halved
- only 8.1% of demand entered the network

Therefore:

- no accepted simulation output exists;
- no accepted one-second FCD exists;
- calibration cannot complete;
- observed-versus-simulated comparison cannot run;
- the VEC chain cannot start.

The leading hypothesis is that the route pool is dominated by long cross-network routes because of the previous route-generation policy, including fringe weighting and minimum-distance choices. Treat this as a hypothesis to test, not as a predetermined answer.

ACTIVE BETA BACKLOG

Work in this dependency order unless fresh evidence proves another order is safer.

PHASE A — RECORD RECONCILIATION

Complete BETA-REC-01 first.

Known inconsistencies include:

- docs/current_workflow_and_todo.md still references an older working head and older phase state.
- docs/current_progress_v0_7.md predates parts of the real matching/demand/SUMO work.
- docs/v07_alpha7_checkpoint_handoff.md contains at least one stale tag-commit statement.
- older records mention five navigation groups while the current canonical implementation uses seven.
- older candidate demand figures must remain distinguishable from corrected alpha.7 figures.

Reconcile these records using Git and machine evidence. Do not erase historical candidate measurements.

PHASE B — ANALYST REVIEW WORKFLOW

Implement or complete a bounded review workflow for the 165 manual-review rows.

Requirements:

- The software may present candidates, geometry, distance, direction, road class, exact-reference evidence and rejection reasons.
- It may export/import a typed decision record.
- It must require a real reviewer identity/role and explicit action.
- It must not auto-accept rows in the guise of analyst review.
- Preserve all rejected candidates.
- Preserve the 9 no-candidate rows.
- Record policy version, mapping fingerprint, reviewer, timestamp and decision reason.
- The UI must remain thin.
- If no human is available, finish the tooling and leave rows visibly pending.

PHASE C — REBUILD A VIABLE DEMAND CANDIDATE

This is the highest-value safely executable engineering work.

Design a new versioned route-pool and demand policy that tests realistic trip-length mixtures rather than repeating the gridlocking alpha.7 construction.

Requirements:

- Preserve the alpha.7 candidate and diagnostic unchanged.
- Use a new policy/method version and new provenance identity.
- Measure route-length distribution, network residence, edge coverage and count-point multiplicity.
- Do not tune only until a preferred GEH or visual result appears.
- Predeclare the variants and selection rule before inspecting final outcomes.
- Keep deterministic seeds.
- Record every executable identity and argument.
- No arbitrary shell or command surface.
- Missing observations remain missing.
- No demand for uncovered Greater Manchester areas.
- Reconstructed routes are not observed journeys.
- Keep Manchester local-authority scope distinct from the Greater Manchester parent network.
- Run bounded pilot simulations before a full window.
- Publish comparison evidence between the alpha.7 demand and revised candidates.
- Define a fail-closed viability contract using measured congestion, insertion, teleport, halting and output-size evidence.
- Do not call a viable run calibrated until calibration actually occurs.

If a scientific threshold is not approved, publish measurements and candidate classifications without pretending formal acceptance.

PHASE D — CALIBRATION FOUNDATION TO EXECUTION

After a viable candidate exists:

- bind accepted mapping, temporal profile, demand and network fingerprints;
- approve or clearly label an owner-approved candidate calibration objective;
- define parameters and bounds;
- define exclusions;
- define uncertainty treatment;
- define the held-out/out-of-window design;
- run deterministic calibration;
- publish residuals and coverage;
- preserve the 80/20 split;
- produce a versioned ManchesterSumoBaseline candidate;
- require explicit analyst acceptance or produce a typed refusal.

Do not sign or edit the supervisor decision form as though supervisor approval exists.

PHASE E — COMPARISON CONTRACT

Review the candidate contract fingerprint:

b1d31a1b122be3a50756ec8e51d1fb17cb6a79c684d48848f1f5df60e45aba3b

Before registering it, verify:

- pairing keys;
- interval aggregation;
- units;
- weighting;
- missingness;
- exclusions;
- denominators;
- direction;
- precision;
- interpretation;
- compatibility with the actual mapping/profile/run artifacts.

Decide whether the existing contract can be registered as an owner-approved candidate. Registration must not be described as supervisor approval or publication validation.

GEH remains diagnostic unless a threshold and use are explicitly approved and recorded.

Run a real comparison only after compatible simulation evidence exists. Report paired rows, coverage and exclusions even if goodness-of-fit remains unavailable.

PHASE F — CONTROLLED SUMO AND FCD

Run only a viable, explicitly accepted candidate baseline.

Require:

- reviewed SUMO 1.27.x identity;
- frozen command and seed;
- one-second step;
- one-second FCD;
- matching network;
- bounded output;
- zero process exit;
- digest verification;
- summary/tripinfo evidence;
- complete receipt;
- atomic new-only publication;
- no overwrite of earlier evidence.

A syntactically valid FCD is not sufficient if the run-quality policy rejects the traffic state.

PHASE G — MANCHESTER SUMO-TO-VEC

Once an accepted FCD/network pair exists:

1. Run VEC-06 pairing and preprocessing.
2. Require the exact VEC-07 request-specific preflight.
3. Execute only the accepted foreground evaluator boundary.
4. Use VEC-08 only where a compatible accepted reference/tolerance exists.
5. Admit only VEC-09-compatible evidence.
6. Render/package through VEC-10–VEC-12 without broadening publication claims.
7. Materialise complete source-to-result lineage.
8. Preserve the Manchester observation, mapping, calibration, SUMO and VEC fingerprints.
9. Keep physical completion, per-task energy, confirmed targets, protected-attribute fairness and other unsupported claims unavailable.

PHASE H — SOURCE/GATE CLOSURE

Progress these while the core chain runs:

- DfT provider response for hour timezone.
- WebTRIS provider response for clock basis.
- BODS retention, display, export and republication terms.
- Complete Bee Network operator/NOC/service membership evidence.
- TfGM release/licence reconciliation.
- Source-wide publication-class reconciliation.
- Broad bounded-source acceptance where evidence supports it.
- Manual keyboard, screen-reader, contrast and 200% zoom checklist.
- Decide whether RQ16 includes a participant study.
- Do not create participant results without ethics/supervisor approval.
- Improve first-run and empty-workspace guidance without hiding unavailable states.

If provider replies are absent, retain historical/private/unavailable states. Do not stall all unrelated work.

PHASE I — RELEASE RECONCILIATION

Before any beta tag:

- ensure the official v0.7 branch contains all reviewed commits;
- keep main unchanged;
- keep v0.6.0 and all alpha tags unchanged;
- reconcile implementation-status, beta goals, progress, workflow, assumptions, open questions and architecture;
- reconcile package version, capability manifests and generated references;
- run full tests;
- run Ruff and format checks;
- run strict mypy;
- run uv lock --check;
- run generated-reference drift checks;
- build the package;
- run container build/demo smoke if Docker is available;
- repeat clean-checkout v0.6/v0.7 side-by-side verification;
- inspect Git for secrets, private paths, raw source/network/run artifacts and oversized outputs;
- ensure the worktree is clean;
- prepare a complete handoff;
- ask the owner before creating a new beta or final release tag unless the owner explicitly authorises tagging in this session.

FEATURES THAT MUST REMAIN UNAVAILABLE

Do not try to "finish" these without a later audited source/design change:

- Manchester-wide live private-vehicle traffic counts, measured speed, density or congestion.
- Live TfGM signal phases, timings, queues or controller state.
- Guaranteed complete Bee Network fleet coverage.
- Public raw/live scene hosting without resolved rights.
- External online basemap under the current offline decision.
- Always-on cloud daemon/scheduler.
- Automatic scientific acceptance.
- Causal or "accurate model" conclusions from one comparison score.

GIT AND CHECKPOINT RULES

- Work on codex/traffictwin-v0.7 unless a separate worktree is required for a truly disjoint experimental slice.
- Do not create another permanent integration branch without a reason.
- Do not touch main.
- Do not force-push.
- Do not move tags.
- Do not clean or reset the user checkout.
- Preserve supervisor questions2 Gemini/.
- Use small coherent commits.
- Push verified commits to origin/codex/traffictwin-v0.7.
- If using another agent or Claude CLI, give it an exclusive, disjoint file set recorded in AGENTS.md.
- You remain responsible for reviewing, testing and integrating delegated work.
- Never accept another agent's "all green" claim without rerunning relevant checks yourself.

SECRETS AND EXTERNAL DATA

A BODS API key was previously supplied by the owner. Never paste it into code, prompts, tests, logs, Git, documentation, receipts or output. Use only an existing secure environment/secret mechanism. If it is not securely configured, report the missing environment configuration without echoing the key.

Real raw DfT, BODS, OSM, network, FCD and execution artifacts must remain in the isolated ignored workspace. Commit only reviewed bounded aggregate evidence and contracts.

EXPECTED BEHAVIOUR

After reading and verifying everything:

1. Give the owner a concise verified takeover status.
2. State the first owned slice and exact files.
3. Immediately begin BETA-REC-01.
4. Continue into the highest-value safely executable research task.
5. Do not wait for repeated "do the next one" messages.
6. Keep the owner updated during long work.
7. When blocked on one item, progress independent work.
8. Stop only when:
   - all safely executable beta work is completed and verified; or
   - continuing would require fabricating human/provider/scientific evidence; or
   - a destructive/external action requires new authority.
9. At handoff, provide:
   - exact head and remote state;
   - commits;
   - changed files;
   - tests/checks;
   - real evidence produced;
   - remaining blockers and owners;
   - capability/gate truth;
   - confirmation that protected branches, tags, secrets and private artifacts were preserved.

Begin now. Do not merely restate the plan.
```
