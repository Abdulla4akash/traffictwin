# Parallel-agent master prompt — batch 2 (27 July 2026)

Successor to `PARALLEL_FEATURES_MASTER_PROMPT.md` after batch 1 (Phases 40–45) shipped and
was independently verified. Paste into a fresh agent session started from
`~/AntigravityTest/diss-integration`:

```text
You are a parallel feature-building agent for TrafficTwin v0.7, batch 2. The canonical copy
of this brief is committed at repo root as PARALLEL_FEATURES_MASTER_PROMPT_2.md — read it
first; if this paste differs, the committed file governs. You work the SAME branch
(`claude/complete-v0.7`) as an active primary session: build ONLY the features below, ONLY
in the exact files each names, re-verify `git status` + `git log -1` before EVERY edit and
commit, and `git pull --ff-only` whenever HEAD moved.

FIRST ACTIONS — VERIFY
1. Read AGENTS.md §"v0.7 Work Coordination": Phases 14–39 belong to the primary agent and
   Phases 40–45 to batch 1 — every file those claims name is FORBIDDEN unless a feature
   below explicitly grants a named touchpoint. Your claims start at Phase 46.
2. Read PARALLEL_FEATURES_MASTER_PROMPT.md (batch 1) for the boundaries, gotchas, and
   additive-route mechanism — ALL of it applies verbatim here, including the live-campaign
   compute hazard (held-out campaign until ~23:30 local 27 Jul: no multi-core or
   long-running compute; single-process pytest is fine) and the untouchables
   (`data/vec-fresh/**`, `.demo/registry-*.sqlite`, `scripts/capacity_*.py`,
   `docs/evaluation/capacity_*`, external clones — never fetch, main, tags, changelog,
   cli.py, capability manifests, held-out seeds).
3. One byte-frozen file needs naming: docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md
   is digest-bound to the RUNNING campaign approval. Never edit it, whatever you find in it.
4. Expected start state: clean tree at `195afd8` or later, in sync with origin.

GATES per feature (unchanged from batch 1): focused tests, all tests/unit, tests/ui when UI
changed, `uv run ruff check src tests scripts`, format check on touched files,
`uv run mypy src tests`, `git diff --check`. One feature = one Phase claim appended to
AGENTS.md = one small commit series, pushed immediately.

THE FEATURES — in order, each independently shippable

FEATURE 7 (Phase 46) — Bus-trajectory derivation library (B1 execution prep)
  Goal: the predeclared trace-construction rules of
  docs/evaluation/bus_fleet_experiment_predeclaration_draft.md §3 as a tested library that
  runs on NO real data yet: path-following interpolation between per-vehicle fixes
  (constant progression along a supplied matched path between fix times — never
  straight-line), gap-ceiling handling (a segment whose fixes are further apart than the
  ceiling is DROPPED and counted, never invented), dwell handling (fixes within the dwell
  radius = stationary at the matched location), per-vehicle matched-share and
  interpolated-versus-observed-share accounting, implied-speed screening (flag, don't
  silently drop), and one-second resampling to the VEC-06 shape.
  Parameters (gap ceiling s, dwell radius m, matched-share floor, speed bound m/s) are
  REQUIRED function arguments with NO baked-in defaults — the values are owner decisions
  G2; tests pass explicit values (120 / 15 / 0.8 / 32 as *test* values only).
  Type-level literals on every output: derived_scenario=True, observed_fcd=False,
  buses_only=True. Pure functions; synthetic in-memory fixtures; no quarantine access, no
  BODS calls, no session artifacts.
  New files ONLY: src/traffictwin/integration/manchester/bus_trajectory.py,
  tests/unit/test_manchester_bus_trajectory.py.

FEATURE 8 (Phase 47) — Confirmatory-mode campaign report renderer
  Goal: today the analysis harness is type-level exploratory (`confirmatory: False`). Build
  the separate confirmatory renderer the signed protocol needs:
  `render_confirmatory_report(design, receipt, analysis, *, predeclaration_sha256)` that
  REFUSES (typed errors, fail closed) unless ALL of: design.phase is HELD_OUT,
  design.approval.held_out_authorised is True, design.approval.predeclaration_sha256 ==
  the passed digest, receipt.design_fingerprint == design.fingerprint(), analysis
  design/receipt fingerprints match, and receipt status is completed with zero
  failed/skipped cells. Output: markdown that presents EXACTLY ONE contrast (the design's
  primary metric, baseline vs the single variation arm) as the confirmatory result —
  STA-01 estimate, bootstrap interval, randomisation p, effect direction — citing the
  signed predeclaration path+digest and design fingerprint; every other number is labelled
  descriptive context. A null or reversed primary result renders with identical prominence
  and layout (write a test asserting the null path produces the same sections). No
  significance language beyond STA-01's own outputs; label ceiling
  owner_approved_candidate; supervisor approval never claimed.
  New files ONLY: src/traffictwin/integration/vec_campaign/confirmatory_report.py,
  tests/unit/test_vec_confirmatory_report.py. Import models/analysis modules only — never
  the campaign service, never a registry, never live campaign data; tests build synthetic
  design/receipt/analysis objects.

FEATURE 9 (Phase 48) — Campaigns browser additive page
  Goal: read-only inventory page "Campaigns" over campaign receipt files: user supplies a
  receipt JSON path (text input; no default path, no directory scanning — the live campaign
  directory must never be opened by default); page shows design identity (experiment id,
  phase, arms, seeds, fingerprints, approval provenance incl. held_out_authorised),
  per-cell state/elapsed table, budget usage, and honest typed errors for
  missing/invalid/mismatched receipts. No registry access, no analysis computation, no
  scientific numbers — receipts only. Phase/approval fields displayed verbatim with badges;
  never implies a campaign is running or live.
  New files ONLY: src/traffictwin/ui/campaigns_services.py,
  src/traffictwin/ui/pages/campaigns.py, src/traffictwin/ui/app_pages/campaigns.py,
  tests/unit/ui/test_campaigns_services.py, tests/ui/test_campaigns_page.py, plus the
  additive-spec + runtime-hook touchpoints in navigation_v07.py / page_runtime.py (the
  same tuple batch 1 extended — extend it again, additive only), one docs/v07_navigation.md
  sentence, one docs/index.md row. Tests use tmp_path receipt fixtures only.

FEATURE 10 (Phase 49) — Dissertation docs pack (docs only)
  (a) docs/dissertation_appendices/trace_provenance.md — the Appendix B trace table:
  file, scenario day, rationale, local window, SUMO seed, trace steps, slots, Gate-A
  sha256 (first 16 hex), occupancy rows — sourced from the committed Gate-A machine record
  (docs/reference/generated/vec_source_snapshot_audit.json) plus the admission-probe
  evidence JSONs; day/window/rationale rows cite "producer sidecar traces/PROVENANCE.md at
  upstream commit 6e56393 (read via blob-less peek; pinned clones unfetched pending R1)".
  Include we/inc/ev measured identity-snapshot numbers from the three probe evidence
  files; wd_am/wd_pm rows carry audit-table values only and say "not admitted".
  (b) docs/video_storyboard.md — the 6–8 minute video storyboard: shot list with timings
  mapped to the existing docs/demo_script.md steps, the rubric split stated (Use of Medium
  40% / Complementing the Report 40% / rest), which shots show un-reported material (UI
  interactions, provenance DAG click-through, replay animation, RSU Monitor drill-down,
  Match Review decide-persist-seal), a spoken-caveats checklist reusing
  docs/demo_checklist.md's required caveats, and equipment/recording notes. No scientific
  claims — reference the results records rather than restating numbers.
  New files ONLY: those two documents + their docs/index.md rows.

FEATURE 11 (Phase 50) — tos-analysis forked-child segfault: diagnose first
  Goal: tests/ui/test_tos_analysis_pages.py emits ~13 intermittent forked-child segfault
  dumps per run (tests still pass) — batch 1 traced the smell to a git-commit lookup
  inside the accepted TOS reader. Reproduce it, identify the exact mechanism (likely
  fork-after-threads or subprocess-in-forked-child on macOS), and write the diagnosis to
  docs/integration/tos_reader_fork_diagnosis.md with the reproduction command, the stack
  evidence, and the minimal candidate fix. THEN fix it ONLY IF the fix is a bounded,
  behaviour-preserving change in at most one source file (e.g. guarding the lookup,
  memoising before fork, or switching to a non-forking probe) with an unchanged public
  API and unchanged returned values — the Phase 18 dtype repair is the scale to match. If
  the honest fix is bigger than that, ship the diagnosis document alone and record the
  handoff. Verification when fixing: the dumps are gone across three consecutive runs of
  the file, and the full unit+ui suites stay green.
  New files: the diagnosis document + its docs/index.md row; plus (only if fixing) the one
  bounded source-file change and a focused regression test.

STOP CONDITIONS and the end-report format are batch 1's, unchanged. Leave the changelog,
week-4 checklist, and every capacity_* document alone — the primary agent reconciles those.
```

Batch-2 claims run Phase 46–50; the primary session owns numbers below 40 and the
reconciliation passes.
