# TrafficTwin post-meeting build queue and resume prompt

**Prepared:** 2 August 2026, Phase 172
**Repository:** `/Users/akashx/AntigravityTest/diss-integration`
**Branch:** `claude/complete-v0.7`
**Verified parent:** `b86b87f0690da5c485c7bbd9750ad2b2179be518` (Phase 171)
**Policy ceiling:** `owner_approved_candidate`

This is the standalone continuation record for a fresh context. The branch may advance after this
file is written: inspect live refs and never reset, check out or otherwise force the worktree back
to the verified parent.

## 1. Current truth

Phases 139–170 implemented all six data-platform v1 slices, all eight post-v1 backend designs and
the bounded DeepSeek scenario agent. Phase 171 reconciled the stale status documents. At its
completion, local HEAD, `origin/claude/complete-v0.7` and `origin/main` matched; the worktree was
clean. The Phase-171 audit passed 250 meeting/platform/research-workflow tests, lock validation,
relative-link checks, privacy screening and diff checks.

Implemented foundations include:

- receipted attended/scheduled BODS micro-batch tooling;
- VEC outcome prediction and aggregate bus-forecast contracts;
- structured and DeepSeek-assisted what-if composition;
- Inventory, Forecasts and Composer platform pages;
- local aggregate SQLite storage and feature registration;
- incremental analytics and data-quality policy;
- evidence matrix and append-only scenario/run lifecycle;
- mechanism/policy observatory and Decision-Safety Ruleset v2;
- maximum-coverage live-twin contracts with a deterministic fake;
- maximum-coverage capacity/multi-algorithm benchmark protocol tooling; and
- a receipted Dhaka Airport-corridor network feasibility result.

Implementation does not mean activation. No OS scheduler, populated operational store, real
live-twin transport, public/cloud/operator deployment, benchmark campaign, participant study or
new scientific result exists merely because its contract exists.

Authoritative current summaries:

- [`docs/implementation-status.md`](docs/implementation-status.md)
- [`docs/current_progress_v0_7.md`](docs/current_progress_v0_7.md)
- [`docs/traffictwin-data-platform-v1-plan.md`](docs/traffictwin-data-platform-v1-plan.md)
- [`AGENTS.md`](AGENTS.md), especially Phases 139–172 and shared-worktree rules

## 2. Build programme

All eight areas below are requested. The order is backend-first so later UI and execution adapters
consume stable contracts. Treat every area as its own design, phase, verification cycle, commit and
push; do not combine the programme into one phase or commit.

### Slice 1 — Operational aggregate-store activation

Goal: make the existing safe SQLite historical store usable in an owner-selected ignored local
workspace without making it a production or scientific dependency.

Design and deliver:

- typed activation configuration and receipt;
- explicit workspace selection, containment and permissions checks;
- safe-aggregate-only discovery and migration preview;
- source/schema/licence/digest validation before registration;
- atomic activation, idempotent resume and corruption/orphan reporting;
- complete verified backup plus restore drill;
- catalogue/integrity CLI commands and deterministic synthetic fixtures;
- import adapters only for already-safe aggregate artifacts; and
- tests proving no raw quarantine, identifier, participant, credential or private-path leakage.

Do not migrate a real workspace merely because the tooling exists. A real target path and actual
migration are separate owner actions.

### Slice 2 — Scenario lifecycle integration

Goal: connect the composer and DeepSeek translation receipts to the append-only scenario registry
without collapsing prediction, approval, execution, analysis or admission.

Design and deliver:

- exact composer-draft/revision to `scenario_drafted` binding;
- DeepSeek prompt/input/response digest carriage without retaining prose or credentials;
- local lifecycle service and typed views over replayed state;
- existing external approval-artifact validation only—never approval creation;
- changed-draft, stale-prior-digest and mismatched-receipt refusals;
- execution/deviation/analysis/admission import adapters using authoritative artifacts;
- idempotent retries and deterministic replay; and
- focused service, integration and adversarial tests.

There must still be no generic run endpoint, inferred approval, agent signature or automatic
admission.

### Slice 3 — Post-v1 Platform Console

Goal: expose the implemented post-v1 backends through additive, read-only platform pages.

Design and deliver four coherent views, which may share one safe service layer:

1. analytics freshness/quality/readiness and immutable report feed;
2. experiment evidence matrix coverage, compatibility, inclusion and exclusion provenance;
3. mechanism/policy observatory cards, citations and limitations; and
4. Decision-Safety assessments, metric-specific rankings/winners/advice and non-executing drafts.

Requirements:

- additive navigation with unique labels and routes;
- no recursive file browsing or raw artifact access;
- explicit evidence standing, support, uncertainty and deviations;
- no automatic calls, writes, approval, execution or admission;
- honest empty/unavailable states;
- responsive/a11y-compatible native Streamlit presentation; and
- AppTests covering privacy, links, citations, no-write and adversarial wording.

### Slice 4 — Concrete local-SUMO live-twin transport

Goal: implement the first real process transport under the Phase-168 contracts, using the existing
safe public SUMO fixture and engineering-only receipts.

Design and deliver:

- an injected local-SUMO process adapter using bounded argv and no shell;
- lifecycle, heartbeat, pause/resume/step, command sequence and shutdown handling;
- aggregate snapshot parsing with output and privacy bounds;
- local simulation closed-loop commands for allowlisted signal/speed/lane/incident/route actions;
- single-owner locking, idempotency, time/command/resource budgets and terminal receipts;
- crash, timeout, protocol-loss and cleanup recovery tests; and
- a non-scientific local smoke only if the pinned SUMO runtime and safe fixture are present.

Do not connect BODS, a public endpoint, cloud infrastructure, operator systems or real roads in
this slice. Do not describe road capacity and RSU compute capacity as one variable.

### Slice 5 — Benchmark execution infrastructure

Goal: turn the Phase-169 protocol into a locally testable execution package without performing the
scientific campaign.

Design and deliver:

- digest-pinned actor/runtime/plugin manifests for every declared family;
- compatible observation/action/reward and capacity-feature adapters;
- deterministic job-pack export for the frozen 240 cells / 2,400 matched jobs;
- local synthetic workers and tiny explicitly non-scientific dry runs;
- receipt ingestion, validation, retry/resume and checkpoint inventory;
- matched-budget and seed-namespace enforcement at dispatch and return;
- provider-neutral resource-plan export with estimates labelled as estimates;
- analysis-input freezing and result-compatibility gates; and
- adversarial tests for leakage, mismatched budgets, reused seeds and unsigned scope.

Do not train real actors, contact cloud providers, spend money, use inspected seeds as unseen,
change the frozen protocol post hoc or create evidence/admission.

### Slice 6 — XAI instrumentation

Goal: implement the fenced Meeting-1 explainability work as auditable instrumentation rather than
a causal or solution claim.

Design and deliver:

- typed decision-time snapshot and source-support contracts;
- counterfactual replay adapter interfaces for compatible always-local/Lyapunov baselines;
- policy-disagreement rows and browser;
- behavioural fingerprints such as action/offload share versus declared load;
- attribution artifact schema, stability/fidelity metadata and unavailable states;
- synthetic SHAP/Integrated-Gradients-shaped fixtures without claiming real actor explanation;
- read-only UI with exact source/actor/checkpoint binding; and
- tests preventing causal, optimal, faithful or validated wording without corresponding evidence.

Real actor attribution remains unavailable until a compatible producer snapshot hook, model
access and literature-grounded validation method exist.

### Slice 7 — Manchester Gate-D integration

Goal: progress observation-to-SUMO mapping, calibration, baseline and comparison using existing
accepted evidence and fail-closed decision packets.

Design and implement every safe independent part:

- extend real-network candidate generation and typed analyst-review records;
- complete mapping-policy decision support and threshold sensitivity evidence;
- connect temporal profiles and calibration orchestration;
- build versioned baseline-candidate and comparison-contract workflows;
- preserve coverage, exclusions, uncertainty, source time semantics and complete lineage; and
- add the read-only comparison UI and deterministic tests where the required contract is frozen.

Do not invent unresolved DfT/WebTRIS time semantics, silently select scientific thresholds or run
a scientific Manchester comparison without its accepted inputs and policy. If one decision blocks
one substage, finish disjoint scaffolding and continue to Slice 8.

### Slice 8 — Supervisor deck and bibliography completion

Goal: close the Meeting-1 communication and literature deliverables.

Design and deliver:

- a concise 3–4-slide supervisor deck covering the digital-twin loop, what-if differentiator,
  dual lenses, evidence result, portfolio/benchmark direction, status and decisions;
- editable source plus visually verified rendered output;
- an expanded primary-source literature matrix and bibliography toward the requested approximate
  100 verified references;
- DOI/publisher/metadata verification and claim-to-reference mapping;
- explicit separation between literature evidence, project measurements and LLM drafting; and
- updated manuscript references without inventing supervisor endorsement or publication status.

Use the presentation/document artifact workflow available in the new session and browse primary
sources for current citation metadata. Do not use generated prose as a source.

## 3. Cross-slice implementation rules

- Inspect `git status`, HEAD, feature remote and `origin/main` before work. Pull only when clean and
  fast-forwardable. Never reset to the parent recorded above.
- Never touch `/Users/akashx/AntigravityTest/diss`.
- Multiple writers may share the worktree. Preserve all work not explicitly owned.
- Claim a fresh phase in `AGENTS.md` before editing each slice and list exclusive files.
- Read the relevant existing designs and implementations completely before producing a new design.
- Design first, then implement backend-first, then UI/integration.
- Recheck HEAD and status immediately before every edit.
- Use `apply_patch`; do not use broad formatting, broad staging, reset, checkout, clean or stash.
- Stage explicit owned paths only; inspect `git diff --cached --name-status`, run cached diff checks
  and review the complete staged diff.
- Run proportional gates: `uv lock --check`, Ruff, Ruff format, strict mypy, focused tests,
  adjacent platform tests, link/provenance/privacy checks and full tests for high-risk shared
  changes.
- Commit and push each slice independently to `claude/complete-v0.7`; verify local and feature
  remote refs match. Fast-forward `main` only when ancestry-safe and verify all three refs.
- Update each design/status document only after implementation truth is known.
- Continue to the next safe slice without waiting for repeated prompts. Batch genuinely blocking
  owner choices into one concise decision packet while continuing independent work.

## 4. Scientific, privacy and authority invariants

- Maximum policy ceiling is `owner_approved_candidate`.
- Never imply supervisor, ethics, publication, production or real-road approval.
- Predictions, forecasts, drafts, LLM output and engineering receipts do not create evidence.
- Preserve protocol-confirmed, post-hoc, exploratory, descriptive and execution-deviated roles.
- The clean Sparse-64 rerun is owner-admitted descriptive evidence with its execution deviation;
  the earlier archive remains non-admitted. Neither is pooled with corridor VEC evidence.
- Never expose credentials, salts, private permission text, private paths, raw BODS bytes,
  identities, participant data or non-redistributable artifacts.
- Do not output, log or commit the DeepSeek key. `.env.local` remains ignored and local only.
- No participant result exists until actual approved collection produces one.
- No benchmark result exists until an authorised campaign actually executes and is analysed.
- A successful dry run is software evidence only.

## 5. Paste-ready resume prompt

```text
You are the owner-directed primary implementation and integration agent for TrafficTwin.

Repository:
- Worktree: /Users/akashx/AntigravityTest/diss-integration
- Branch: claude/complete-v0.7
- Never touch /Users/akashx/AntigravityTest/diss.
- Multiple writers may share the worktree. Preserve all work you do not explicitly own.

First read POST_MEETING_BUILD_RESUME_PROMPT.md completely. It is the current standalone
continuation record and supersedes older build-queue summaries for this programme. Then read
AGENTS.md completely, especially the shared-worktree rules and Phases 139 onward. Read
docs/implementation-status.md, docs/current_progress_v0_7.md and every design/source file routed
by the first slice before acting.

Run these read-only checks first:
- git status --short --branch
- git log --oneline -12
- git rev-parse HEAD
- git rev-parse origin/claude/complete-v0.7
- git rev-parse origin/main
- inspect active claims in AGENTS.md

The handoff records Phase-171 parent b86b87f0690da5c485c7bbd9750ad2b2179be518, but the branch may
have advanced. Never reset to that commit. Pull --ff-only only when the worktree is completely clean
and the shared-worktree rules permit it.

Objective: design and implement all eight slices in POST_MEETING_BUILD_RESUME_PROMPT.md, in its
backend-first order, one fresh phase/verification/commit/push per slice. Start immediately with
Slice 1, Operational aggregate-store activation. Create or update a dedicated design before code,
claim the next free phase in AGENTS.md, state exact owned paths, and report concise initial status
before editing. After Slice 1 passes its acceptance gates, commit, push, verify refs and continue
to Slice 2 without waiting for another “go”. Continue through every independent safe slice.

The owner has already selected maximum bounded coverage for analytics, decision safety, live-twin
contracts and benchmark protocol. Do not repeatedly re-ask those choices. A contract does not
manufacture credentials, accounts, operator authority, participant data, a signature or scientific
evidence. If one external action genuinely requires a missing concrete input, finish all safe local
design/code/tests for that slice, record the exact residual, and continue with independent slices.

Use apply_patch, explicit staging and proportional verification. Never sweep another writer’s
changes into a commit. Review the complete staged diff. Push each phase to
origin/claude/complete-v0.7 and fast-forward main only when ancestry-safe. Keep predictions,
forecasts, drafts, LLM output and engineering receipts separate from evidence; preserve every
deviation and citation requirement; never expose private data or credentials.

Begin now. Do not merely restate the plan.
```
