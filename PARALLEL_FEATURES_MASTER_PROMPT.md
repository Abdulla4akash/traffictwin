# Parallel-agent master prompt — TrafficTwin v0.7 feature batch (27 July 2026)

Paste into a fresh agent session started from `~/AntigravityTest/diss-integration`:

```text
You are a parallel feature-building agent for TrafficTwin v0.7, working the SAME branch
(`claude/complete-v0.7`) as an active primary agent session. Your safety rules are stricter
than usual because two sessions sharing a branch destroyed work once before (25 July): you
build ONLY the features listed below, ONLY in the exact new files each feature names, and
you re-verify `git status` + `git log -1` before EVERY edit and commit. If HEAD moved,
fetch/rebase-free: `git pull --ff-only` and re-check your files are untouched.

FIRST ACTIONS — VERIFY, NEVER TRUST THIS PROMPT BLINDLY
1. Read AGENTS.md §"v0.7 Work Coordination" completely — Phases 14–33 are the primary
   agent's claims; every file they name is FORBIDDEN to you.
2. Read docs/evaluation/capacity_pilot_results_20260727.md and
   docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md to understand the
   scientific state. Read docs/index.md to learn the documentation map.
3. Run git status/fetch; expected: clean tree on claude/complete-v0.7 at `53dd2bf` or later,
   in sync with origin.

LIVE HAZARD — A TIMED CAMPAIGN IS EXECUTING ON THIS MACHINE (until ~23:00 local, 27 Jul)
- A held-out confirmatory campaign runs in the primary session (~4 cores). Until it
  completes: NO multi-core or long-running local compute — no netconvert, duarouter, SUMO,
  training, or parallelised suites. Single-process pytest (the repo default) is fine.
- NEVER touch: `data/vec-fresh/**`, `.demo/registry-*.sqlite`, `scripts/capacity_*.py`,
  any `docs/evaluation/capacity_*` file, `data/workspace*`, quarantine directories.

HARD BOUNDARIES (identical to the primary agent's, non-negotiable)
- Never touch main, v0.6.0, any alpha tag, anything under `../external/` (NEVER fetch those
  clones — a fetch bricks scientific admissions), the untracked `supervisor questions2
  Gemini/`, or the user's checkout `~/AntigravityTest/diss`. Never force-push.
- Labels: `owner_approved_candidate` / `analyst_reviewed_candidate` ceilings. Never
  scientifically_validated, ground_truth, causal, supervisor-approved. Never fabricate
  evidence, approvals, participant data, or provider semantics. Buses are never general
  traffic. Pilot numbers are exploratory forever. Held-out seeds {10–14} are consumed by
  the running campaign only; you never reference them in code.
- Shared surfaces stay untouched: `src/traffictwin/cli.py`, capability manifests, generated
  references (except where a feature below explicitly says otherwise), changelog,
  `docs/index.md` EXCEPT adding one row per shipped feature, navigation files EXCEPT the
  additive-spec mechanism named in Feature 1.
- Before building each feature, append your claim to AGENTS.md §v0.7 Work Coordination as
  "Phase 4N claim" (start at Phase 40; the primary agent owns numbers below 40). One
  feature = one claim = one small commit series, pushed immediately.
- Gates per feature before its final push: focused tests green, all `tests/unit` green,
  `tests/ui` green when UI files changed, repo `uv run ruff check src tests scripts`,
  `uv run ruff format --check` on touched files, `uv run mypy src tests` clean,
  `git diff --check` clean.

GOTCHAS THAT COST TIME BEFORE
- `cd` persists across Bash calls. AppTest breaks on st.rerun() inside forms. Strict frozen
  pydantic models refuse python-dict tuples (use model_validate_json). scripts/ escapes CI
  mypy — still check locally. The UiPage enum is COUNTED by tests — new pages must use the
  V07AdditivePageSpec additive-route mechanism (see match_review precedent in
  navigation_v07.py / page_runtime.py / app_pages/match_review.py), which needs ZERO enum
  or count edits. Import Manchester modules by full path (integration/manchester/__init__
  is lead-claimed). The house test-fixture recipe for accepted loaders lives in
  tests/unit/test_bods_session_identity.py and tests/ui/test_match_review_page.py.

THE FEATURE LIST — build in this order, each independently shippable

FEATURE 1 — RSU Monitor page (Study Case 1 completion; Randy's explicit ask)
  Goal: the supervisor-relayed ask "which RSU is overwhelmed and how overwhelmed": per-RSU
  drill-down over an imported TOS run — queue depth, active/processed tasks, energy over
  the trace window, one RSU selectable at a time, plus a small all-RSU load-asymmetry
  table.
  New files ONLY: src/traffictwin/ui/rsu_monitor_services.py,
  src/traffictwin/ui/pages/rsu_monitor.py, src/traffictwin/ui/app_pages/rsu_monitor.py,
  tests/unit/ui/test_rsu_monitor_services.py, tests/ui/test_rsu_monitor_page.py.
  Plus the additive-spec + runtime-hook edits in navigation_v07.py and page_runtime.py
  (2–6 lines each, additive only, match_review precedent), one docs/v07_navigation.md
  sentence, one docs/index.md row.
  Data access: read-only through the EXISTING accepted loaders in
  traffictwin.ui.services (tos replay RSU series and task loaders) — import them, never
  edit them; no new parsing of raw artifacts. Honest states: no data → explicit
  unavailable; never imply live monitoring; per-RSU series labelled with their run/window
  identity. No scientific calculation in the page — derived series (utilisation ratios)
  belong in rsu_monitor_services.py with unit tests.

FEATURE 2 — Demand-diagnosis library (execution-ready prep for the signed rebuild)
  Goal: implement the four §2 measurements of
  docs/evaluation/demand_rebuild_predeclaration.md as a tested library that does NOT run
  on real data yet: route-length distribution (km), route edge-count distribution,
  free-flow residence time, counted-edge multiplicity, fringe share. Pure functions over a
  parsed route-pool iterator + an edge-length/boundary mapping; deterministic percentile
  summaries; a renderer to markdown.
  New files ONLY: src/traffictwin/integration/manchester/demand_diagnosis.py,
  tests/unit/test_manchester_demand_diagnosis.py.
  Tests use tiny synthetic in-memory pools. Type-level literals: measurements_only, no
  viability verdict, no threshold decision (thresholds are owner decisions E3). Streaming
  line-iteration for route files (the 1.28 GB lesson) — never load whole files.

FEATURE 3 — Campaign mechanism report (explainability exhibit)
  Goal: a deterministic renderer that takes a completed campaign analysis JSON (the
  committed data/vec-fresh/capacity-pilot/campaign_analysis.json SCHEMA — read the file for
  shape, do not modify it) and emits the "mechanism evidence" markdown: per-seed per-arm
  primary/secondary tables, the offload-rate invariance check (bit-identical values
  highlighted), latency-range overlap table, all under type-level
  descriptive_non_causal/exploratory literals.
  New files ONLY: src/traffictwin/integration/vec_campaign/mechanism_report.py,
  tests/unit/test_vec_mechanism_report.py.
  Input = parsed analysis model or plain dict; NEVER read the live registry; NEVER import
  the campaign service (models/analysis modules only).

FEATURE 4 — Stadium event-study predeclaration skeleton (docs only)
  Goal: the ev-trace study skeleton in the house structural-draft discipline (crossover
  draft is the template): question (event-night fleet dynamics vs the incident hour —
  actor behaviour on the admitted ev trace, 23,400 steps, 175 slots), arms/levels
  FILL-AT-SIGNING, fresh seed set proposed {40–44} disjoint from {0–2},{10–14},{20–24},
  {30–34}, publishable null fixed, STA-01/STA-02 method constraints carried, runtime
  re-cost note (first ev execution is an unmeasured timing probe; 7,200 s ceiling is an
  escalation trigger). UNSIGNED, empty sign-off, agent never completes it.
  New files ONLY: docs/evaluation/stadium_event_study_draft.md + docs/index.md row.

FEATURE 5 — Dissertation appendix generators
  Goal: deterministic generators for the dissertation's appendix payload:
  (a) capability catalogue table (id, family, status, ADR refs) from the machine-readable
  capability manifest; (b) software-version/parameter table from pyproject + uv.lock +
  recorded tool versions. Output = markdown files under docs/dissertation_appendices/
  (new directory), regenerated by script, committed.
  New files ONLY: scripts/generate_dissertation_appendices.py,
  docs/dissertation_appendices/*.md (generated), tests/unit/test_dissertation_appendices.py
  (runs the generator into tmp_path and asserts structure, not content bytes),
  docs/index.md row. Read manifests through existing public APIs only.

FEATURE 6 — Bus-session aggregates page (only after Features 1–5)
  Goal: additive page "Bus Sessions" rendering the aggregate-only session measurement
  artifacts (cadence percentiles, hourly progression with support counts) that the
  session-identity module writes into a workspace. Read-only, aggregates only; NEVER
  surface tokens or raw refs; bus speed is never road speed; absent workspace → honest
  unavailable state.
  New files ONLY: src/traffictwin/ui/bus_sessions_services.py,
  src/traffictwin/ui/pages/bus_sessions.py, src/traffictwin/ui/app_pages/bus_sessions.py,
  tests/unit/ui/test_bus_sessions_services.py, tests/ui/test_bus_sessions_page.py, plus the
  same additive-route touchpoints as Feature 1.

STOP CONDITIONS
- Any gate failure you cannot fix inside your claimed files → commit nothing, record the
  finding in your AGENTS.md claim, move to the next feature.
- Any need to edit a file outside your claimed set → do not; record it as a handoff note.
- The primary agent will reconcile the changelog and week-4 checklist — leave both alone.

Report at the end: features shipped with commits, gates run, anything skipped and why.
```

This file is owner-directed (27 July 2026): the feature batch runs in parallel while the
confirmatory campaign and the owner's email round-trips are pending. The primary session
owns Phases up to 39; parallel claims start at Phase 40.
