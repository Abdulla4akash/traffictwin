# Parallel-agent master prompt — batch 5 (27 July 2026, evening)

Successor to batches 1–4. Batch 4 shipped Features 17–19; Features 20–21 were correctly
held pending the confirmatory campaign and are INHERITED here. Paste into a fresh agent
session started from `~/AntigravityTest/diss-integration`:

```text
You are a parallel feature-building agent for TrafficTwin v0.7, batch 5. The canonical
copy of this brief is committed at repo root as PARALLEL_FEATURES_MASTER_PROMPT_5.md —
read it first; it governs over this paste. Same branch (`claude/complete-v0.7`) as an
active primary session: build ONLY the features below, ONLY in the exact files each
names, re-verify `git status` + `git log -1` before EVERY edit and commit,
`git pull --ff-only` when HEAD moved.

FIRST ACTIONS — VERIFY
1. Read AGENTS.md §"v0.7 Work Coordination": Phases 14–39 (primary) and 40–58 (batches
   1–4) are FORBIDDEN files unless a feature below grants a named touchpoint. Carried
   Features 20–21 claim Phases 59–60; new features claim Phase 61 upward.
2. Read PARALLEL_FEATURES_MASTER_PROMPT.md (batch 1) and the Feature 20/21 specs in
   PARALLEL_FEATURES_MASTER_PROMPT_4.md — batch 1's boundaries, gotchas, gates, and stop
   conditions apply verbatim; batch 4's two feature specs are executed here unchanged.
3. CAMPAIGN STATE CHECK (decides what you may run):
   `cat data/vec-fresh/capacity-confirmatory/launcher.pid` then `ps -p <pid>`.
   - Launcher ALIVE → build Features 23, 24, 26 only; everything else is pending; no
     multi-core/long compute; report pending items and stop.
   - Launcher DEAD and campaign_receipt.json status == "completed" → all features are
     runnable, compute restrictions lifted (the primary session may also be running the
     owner's attended bus session Monday 08:00–09:30 — that is I/O-light; ignore it).
   - Launcher DEAD but receipt missing/incomplete → do NOT touch anything in that
     directory; report the state and build only Features 23, 24, 26.
4. Standing untouchables, unchanged: external clones (never fetch), main/tags/changelog/
   cli.py/manifests, docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md
   (byte-frozen), .demo/registry-*, and never launch/kill/restart any capacity_* script.
   READ-ONLY carve-outs: data/vec-fresh/capacity-pilot/campaign_analysis.json (standing),
   plus — ONLY once the receipt shows completed —
   data/vec-fresh/capacity-confirmatory/campaign_analysis.json and campaign_receipt.json.
5. Expected start state: clean tree at `842edaf` or later, in sync with origin.

GATES per feature (unchanged): focused tests, all tests/unit, tests/ui when UI changed,
uv run ruff check src tests scripts, format check on touched files, uv run mypy src tests,
git diff --check. One feature = one AGENTS.md Phase claim = one commit series, pushed
immediately.

THE FEATURES

FEATURE 20 (Phase 59, carried) — Page figure capture.
  Exactly as specified in PARALLEL_FEATURES_MASTER_PROMPT_4.md. Precondition: campaign
  completed (§3).

FEATURE 21 (Phase 60, carried) — ev timing probe.
  Exactly as specified in PARALLEL_FEATURES_MASTER_PROMPT_4.md: one full-length ev run,
  timing evidence JSON only, no admission, no registry writes; a ceiling breach is the
  finding, not a failure. Precondition: campaign completed (§3).

FEATURE 22 (Phase 61) — Confirmatory figures
  Precondition: campaign completed AND the primary session has committed the confirmatory
  results record under docs/evaluation/ (look for a capacity_confirmatory_results_*.md
  file; if absent, report pending — the analysis may not be final yet).
  Goal: run the EXISTING batch-3 figure generator (scripts/generate_capacity_figures.py —
  do not modify it; it takes an analysis-JSON path) against
  data/vec-fresh/capacity-confirmatory/campaign_analysis.json and commit the outputs to
  docs/dissertation_appendices/figures/ under confirmatory_* names, with a provenance
  note (design fingerprint f289db31…, source-JSON identity, "held-out confirmatory per
  the signed candidate (b)") beside them. If the generator's assumptions don't fit the
  two-arm confirmatory shape, record precisely what didn't fit and stop — do not fork a
  modified copy.
  New files ONLY: the generated confirmatory_* figure files, the provenance note, one
  docs/index.md row.

FEATURE 23 (Phase 62) — Job-pack CLI wrapper
  Goal: operational commands for batch 4's job-pack contract without touching the
  lead-owned cli.py: scripts/vec_job_pack.py with `export` (design module path or a
  campaign scripts' design + output pack path) and `verify` (pack path + returned-results
  directory) subcommands, thin over the Phase 56 library, typed refusals passed through
  verbatim, exit codes 0/1.
  New files ONLY: that script, tests/unit/test_vec_job_pack_cli.py.

FEATURE 24 (Phase 63) — Single-command gate battery
  Goal: scripts/run_all_gates.py — runs the full handoff gate suite in order (ruff check,
  ruff format --check, mypy src tests, pytest tests/unit, pytest tests/ui, pytest
  tests/integration, git diff --check), streams each command's tail, prints a final
  PASS/FAIL table with durations, exits non-zero on first failure or runs-all with
  --keep-going. No new dependencies; subprocess only; never modifies anything.
  New files ONLY: that script, tests/unit/test_run_all_gates_script.py (test the table
  rendering and command list, not by running the real suites).

FEATURE 25 (Phase 64) — Stadium study fill-in candidate (docs only)
  Precondition: Feature 21's timing evidence JSON exists.
  Goal: mirror the primary session's confirmatory-candidates pattern for the stadium
  draft: docs/evaluation/stadium_event_study_candidate.md — a PROPOSED, UNSIGNED fill-in
  of docs/evaluation/stadium_event_study_draft.md with the measured ev timing re-cost
  from the probe evidence, the proposed seeds {40–44} confirmed disjoint, arm defaults,
  and an explicit note that signing binds the file's final SHA-256 and that an agent
  never completes the sign-off. Do not edit the draft beyond adding one pointer line to
  the candidate.
  New files ONLY: the candidate document, the one pointer line in the draft, one
  docs/index.md row.

FEATURE 26 (Phase 65) — Printable participant documents (docs only)
  Goal: split batch 4's instrument into the two documents an ethics submission attaches:
  docs/evaluation/participant_information_sheet_draft.md and
  docs/evaluation/consent_form_draft.md — PROPOSED, aligned to the ethics draft's
  proposed values (survey not interview, no recording, anonymised, degree+12mo retention,
  14-day withdrawal, supervisor-mediated recruitment), plain language, checkbox consent
  items, no fabricated approvals or reference numbers (fields marked
  assigned-at-submission).
  New files ONLY: those two documents + their docs/index.md rows.

STOP CONDITIONS and end-report format: batch 1's, unchanged. Never wait for a
precondition — report the item as pending and move on. Leave the changelog, week-4
checklist, and capacity_* evaluation documents alone (Feature 22's NEW files are the one
named exception).
```

Batch-5 claims run Phases 59–65; the primary session owns numbers below 40 and the
reconciliation passes.
