# Parallel-agent master prompt — batch 6 (27 July 2026, night)

Successor to batches 1–5. Do NOT start this batch while a batch-5 session is still
working (its end report must exist) — the two batches are file-disjoint but share the
AGENTS.md append point. Paste into a fresh agent session started from
`~/AntigravityTest/diss-integration`:

```text
You are a parallel feature-building agent for TrafficTwin v0.7, batch 6. The canonical
copy of this brief is committed at repo root as PARALLEL_FEATURES_MASTER_PROMPT_6.md —
read it first; it governs over this paste. Same branch (`claude/complete-v0.7`) as an
active primary session: build ONLY the features below, ONLY in the exact files each
names, re-verify `git status` + `git log -1` before EVERY edit and commit,
`git pull --ff-only` when HEAD moved.

FIRST ACTIONS — VERIFY
1. Read AGENTS.md §"v0.7 Work Coordination": Phases 14–39 (primary) and 40–65 (batches
   1–5) are FORBIDDEN files unless a feature below grants a named touchpoint. Your claims
   run Phase 66–71 exactly; Phases 72–79 are reserved unused; the primary session
   continues at 80+.
2. Read PARALLEL_FEATURES_MASTER_PROMPT.md (batch 1) — boundaries, gotchas, gates, and
   stop conditions apply verbatim. Standing untouchables: external clones (never fetch),
   main/tags/changelog/cli.py/manifests,
   docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md (byte-frozen),
   .demo/registry-* (write-wise), and never launch/kill/restart any capacity_* script.
3. CAMPAIGN STATE CHECK — same procedure as batch 5
   (launcher.pid + ps + receipt status). Launcher ALIVE → single-process compute only and
   the confirmatory directory is untouchable. Launcher DEAD + receipt "completed" →
   compute restrictions lifted; READ-ONLY carve-outs then cover
   data/vec-fresh/capacity-pilot/campaign_analysis.json (standing) and
   data/vec-fresh/capacity-confirmatory/{campaign_analysis.json,campaign_receipt.json}.
   Registry files: READ-ONLY via the Registry API where a feature says so; never write.
4. Expected start state: clean tree at `2712d53` or later, in sync with origin; batch 5's
   end report exists.

GATES per feature (unchanged): focused tests, all tests/unit, tests/ui when UI changed,
uv run ruff check src tests scripts, format check on touched files, uv run mypy src tests,
git diff --check. One feature = one AGENTS.md Phase claim = one commit series, pushed
immediately.

THE FEATURES

FEATURE 27 (Phase 66) — Campaign offline verifier ("campaign doctor")
  Goal: an examiner-facing, read-only consistency check over a completed campaign: given
  a design module (script path exposing the design constructor), the campaign output
  directory, and the registry path, verify and report — design fingerprint ↔ receipt
  design_fingerprint; every receipt cell ↔ its output directory's execution_receipt.json
  (request fingerprint, status); published output file hashes ↔ the receipts; admitted
  cells ↔ registry runs and metric collections present under the expected
  receipt-derived identities; approval block present with its predeclaration digest
  re-hashed against the file on disk. Typed findings list, PASS/FAIL summary, exit codes;
  registry access READ-ONLY via the public Registry API; nothing is ever written or
  repaired.
  New files ONLY: src/traffictwin/integration/vec_campaign/verify.py,
  scripts/verify_campaign.py, tests/unit/test_vec_campaign_verify.py (synthetic tmp_path
  campaign fixtures), one docs/index.md row for a short new
  docs/integration/vec_campaign_verification.md describing the checks.

FEATURE 28 (Phase 67) — Dissertation results tables (LaTeX/SVG through accepted machinery)
  Goal: committed dissertation tables generated ONLY through the accepted
  src/traffictwin/reporting/latex.py models (do not modify it):
  scripts/generate_results_tables.py taking an analysis-JSON path and emitting (a) the
  per-arm primary/secondary descriptives table, (b) the predeclared-comparison table
  (mean paired difference, bootstrap interval, randomisation p — reported verbatim,
  labelled exploratory or confirmatory per the source), to
  docs/dissertation_appendices/tables/ with provenance notes. Run it for the pilot JSON
  (standing carve-out) now; run it for the confirmatory JSON ONLY if the primary
  session's confirmatory results record exists under docs/evaluation/ — otherwise commit
  the pilot tables and report the confirmatory half pending.
  New files ONLY: that script, tests/unit/test_results_tables_script.py, the generated
  table files + provenance notes, one docs/index.md row.

FEATURE 29 (Phase 68) — B1 bridge: derived bus trace to VEC-06 request shape
  Goal: close the technical gap between batch 2's bus_trajectory library and VEC-06
  preprocessing: a pure library that takes the derived one-second per-vehicle positions
  (bus_trajectory output structures) and assembles (a) the trace array set in the shape
  VEC-06 expects (T, maxN, mask, pos_x, pos_y, dt, times — read the accepted VEC-06
  contract first and mirror it exactly), (b) the occupancy span table
  (sumo_vehicle_id ↔ slot ↔ t_enter/t_exit semantics, session tokens as vehicle ids),
  and (c) a preprocessing-receipt REQUEST payload — construction only: the output is an
  input FOR the accepted VEC-06 machinery, never an accepted receipt, and a type-level
  literal says so (vec06_admitted=False). Type literals carried: derived_scenario=True,
  observed_fcd=False, buses_only=True. Slot assignment must be deterministic and
  documented (e.g. first-free-slot by token order); tests cover slot reuse, gap-dropped
  vehicles, and mask/span reconciliation on synthetic fixtures.
  New files ONLY: src/traffictwin/integration/manchester/bus_vec_bridge.py,
  tests/unit/test_manchester_bus_vec_bridge.py. Import bus_trajectory and VEC-06 models
  by full module path; modify neither.

FEATURE 30 (Phase 69) — Crossover fill-in candidate (docs only)
  Precondition: the primary session's confirmatory results record exists under
  docs/evaluation/ (capacity_confirmatory_results_*.md). Otherwise report pending.
  Goal: mirror the confirmatory-candidates pattern for
  docs/evaluation/actor_crossover_study_draft.md: a PROPOSED, UNSIGNED
  docs/evaluation/actor_crossover_study_candidate.md filling the FILL-FROM-PILOT fields —
  capacity levels (the knee selected nothing, so present the owner's options with
  cap-2.5 + cap-0.75 as the prepared default, mirroring the confirmatory), seeds {20–24}
  confirmed disjoint from {0–2}, {10–14}, {30–34}, {40–44}, runtime re-cost from the
  measured ~59-minute inc cell range (2 actors × 2 levels × 5 seeds = 20 cells ≈ two
  overnight campaigns), and the G6 method decision laid out honestly: option (i)
  per-algorithm checkpoints IS now available (the STA-02 extension shipped 27 July as
  Phase 28) alongside option (ii) slope comparison — the choice stays an owner decision
  at signing. Empty sign-off; note that signing binds the file's final SHA-256. One
  pointer line added to the draft.
  New files ONLY: the candidate document, the one pointer line in the draft, one
  docs/index.md row.

FEATURE 31 (Phase 70) — Methodology diagram drafts (docs only)
  Goal: three hand-authored, self-contained SVG diagrams committed under
  docs/dissertation_appendices/figures/diagrams/, each clearly titled DRAFT: (a) the
  layered architecture (ingestion → canonical → metrics/diagnostics/statistics →
  provenance → reporting → UI/CLI, with the "UI never computes" boundary marked); (b)
  the data flow for the Manchester chain (raw sources → quarantine → accepted snapshots
  → matching/demand → evidence records); (c) the experiment instrument
  (predeclaration → byte-bound approval → campaign cells → fresh admission → registry →
  STA-01 → results record, with the fail-closed points marked). Plain shapes and text,
  no external fonts/assets, legible in light and dark backgrounds (neutral greys, no
  pure-white or pure-black fills). A short provenance/README note beside them stating
  they are illustrative drafts for the dissertation, not generated artifacts.
  New files ONLY: the three SVGs + the README note, one docs/index.md row.

FEATURE 32 (Phase 71) — Video narration script (docs only)
  Goal: docs/video_narration_script.md — the spoken text for the committed storyboard
  (docs/video_storyboard.md), timed per shot at a ~140 words-per-minute budget summing to
  ≤ 8 minutes, with the required caveat sentences from docs/demo_checklist.md placed
  verbatim at their storyboard positions, the one-sentence pilot framing quoted exactly
  from the corrected results record, and explicit [SCREEN: …] cues matching the
  storyboard's shot list. No new scientific claims; numbers only by reference to the
  committed records.
  New files ONLY: that document, one docs/index.md row.

STOP CONDITIONS and end-report format: batch 1's, unchanged. Never wait on a
precondition — report pending and move on. Leave the changelog, week-4 checklist, and
capacity_* evaluation documents alone; Feature 30's pointer line in the crossover draft
is the one named exception this batch.
```

Batch-6 claims run Phase 66–71; Phases 72–79 stay reserved; the primary session continues
at Phase 80+.
