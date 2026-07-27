# Parallel-agent master prompt — batch 4 (27 July 2026)

Successor to batches 1–3 (Phases 40–55), all shipped and independently verified. Paste into
a fresh agent session started from `~/AntigravityTest/diss-integration`:

```text
You are a parallel feature-building agent for TrafficTwin v0.7, batch 4. The canonical copy
of this brief is committed at repo root as PARALLEL_FEATURES_MASTER_PROMPT_4.md — read it
first; it governs over this paste. Same branch (`claude/complete-v0.7`) as an active
primary session: build ONLY the features below, ONLY in the exact files each names,
re-verify `git status` + `git log -1` before EVERY edit and commit, `git pull --ff-only`
when HEAD moved.

FIRST ACTIONS — VERIFY
1. Read AGENTS.md §"v0.7 Work Coordination": Phases 14–39 (primary) and 40–55 (batches 1–3)
   are FORBIDDEN files unless a feature below grants a named touchpoint. Your claims start
   at Phase 56.
2. Read PARALLEL_FEATURES_MASTER_PROMPT.md (batch 1) — its boundaries, gotchas, gates, and
   stop conditions apply verbatim. Key standing rules: external clones are NEVER fetched;
   main/tags/changelog/cli.py/manifests untouched; never edit
   docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md (byte-frozen);
   docs/index.md may gain one row per shipped feature and nothing else.
3. LIVE CAMPAIGN RULES (changed since batch 3): the held-out confirmatory campaign now runs
   as a DETACHED process — check `cat data/vec-fresh/capacity-confirmatory/launcher.pid`
   and `ps -p <pid>`. While that process is alive (expected until ~00:15 local 28 Jul):
   no multi-core or long-running compute (single-process pytest is fine), and
   `data/vec-fresh/**` plus `.demo/registry-*` stay untouched — with the standing read-only
   carve-out for data/vec-fresh/capacity-pilot/campaign_analysis.json only. NEVER launch,
   kill, or restart any capacity_* script; NEVER start a second launcher.
4. Expected start state: clean tree at `bb6992f` or later, in sync with origin.

GATES per feature (unchanged): focused tests, all tests/unit, tests/ui when UI changed,
uv run ruff check src tests scripts, format check on touched files, uv run mypy src tests,
git diff --check. One feature = one AGENTS.md Phase claim = one commit series, pushed
immediately.

BUILD ORDER: Features 17–19 anytime. Features 20–21 have a HARD precondition — the
campaign receipt at data/vec-fresh/capacity-confirmatory/campaign_receipt.json shows
status "completed" AND the launcher.pid process is dead. If that precondition is not met
by the time you finish 17–19, record 20–21 as pending in your end report and STOP — do not
wait around and do not weaken the precondition.

FEATURE 17 (Phase 56) — CSF job-pack contract (models + design doc; NO executor)
  Goal: the import-first contract for running approved campaigns on university compute
  later: a typed, fingerprinted "job pack" that EXPORTS one approved campaign design with
  an exact input manifest (tos-data commit + per-file sha256 references — never the bytes
  of external repositories), and an IMPORT side that verifies a returned cell-receipt set
  against the pack (design fingerprint match, receipt request-fingerprints ∈ the pack's
  declared cells, per-file output hashes present) before anything downstream may consume
  it. Pure models + export/verify functions; no SSH, no network, no executor, no scheduler;
  type-level literal that a verified import is NOT an admission (admission stays the
  existing ADR-061 path, run locally against the returned artifacts).
  New files ONLY: src/traffictwin/integration/vec_campaign/job_pack.py,
  tests/unit/test_vec_job_pack.py, docs/integration/csf_job_pack_contract.md, one
  docs/index.md row. Import models from vec_campaign.models and vec_runner.models only.

FEATURE 18 (Phase 57) — Bus-versus-DfT comparison report script
  Goal: one command over an explicit workspace path runs the ACCEPTED
  bus_profile_comparison machinery (import by FULL module path
  traffictwin.integration.manchester.bus_profile_comparison; the package __init__ is
  lead-claimed) against the committed Option-A edgeData file (path argument, default the
  committed docs/integration/evidence/manchester_edgedata_counts_option_a.xml), and writes
  the comparison artifact as JSON + markdown to a supplied output directory. Aggregates
  only; bus speed is never road speed; the declared UTC-to-local offset is a required
  argument; support-gated hours reported with their counts; no causal language.
  New files ONLY: scripts/bus_dft_comparison_report.py,
  tests/unit/test_bus_dft_comparison_report_script.py (synthetic fixtures).

FEATURE 19 (Phase 58) — Quality-gate snapshot appendix generator
  Goal: the dissertation's §3.2 quality table as a generated artifact:
  scripts/generate_quality_snapshot.py collects — WITHOUT executing any test — the suite
  inventory via `pytest --collect-only -q` per suite (unit/ui/integration counts), the
  mypy file count from a bounded `mypy --version`-safe invocation or a supplied value,
  ruff/format status strings, python/uv versions, and the current commit, and renders
  docs/dissertation_appendices/quality_snapshot.md with a generation timestamp and the
  exact commands a reader runs to reproduce each number. Collect-only is cheap and allowed
  while the campaign runs.
  New files ONLY: that script, tests/unit/test_quality_snapshot_script.py, the generated
  docs/dissertation_appendices/quality_snapshot.md, one docs/index.md row.

FEATURE 20 (Phase 59) — Page figure capture (HARD precondition above)
  Goal: dissertation/video screenshots of the four newest pages — RSU Monitor, Campaigns,
  Bus Sessions, Match Review — light and dark, desktop width, via a NEW standalone
  Playwright script (do not touch or import the existing browser-audit harness): boot the
  demo workspace app (`uv run traffictwin demo initialise/launch` pattern from
  docs/demo_script.md), navigate to each route, capture to
  docs/dissertation_appendices/figures/pages/, shut the app down cleanly. Pages showing
  honest empty/unavailable states is EXPECTED and fine — capture them as they are; never
  fabricate data to make a screenshot richer.
  New files ONLY: scripts/capture_page_figures.py, the captured images, one docs/index.md
  row. If Playwright is unavailable in the environment, record that and skip.

FEATURE 21 (Phase 60) — ev timing probe (HARD precondition above; measured, not scientific)
  Goal: ADR-065's recorded open risk — no ev execution has ever been timed. Run EXACTLY ONE
  full-length ev execution through the library runner (run_vec_evaluator with a request
  built from the admitted ev identity: trace_file traces/trace_ev_fullrsu.npz, sha
  70d6d12f…, actor ukfleettrain_mappo_model_c_17, fleet uk2030, evaluator_seed 0,
  fleet_seed 0, rsu capacity 2.5, max_steps 23400, timeout 7200), output under
  data/vec-fresh/ev-timing-probe/, and write
  docs/integration/evidence/vec_ev_timing_probe_20260728.json recording wall-clock
  seconds, output bytes, the request fingerprint, and the margin against the 7,200 s
  ceiling. NO admission, NO registry write, NO metric claims — timing evidence only. If
  the run exceeds the ceiling the refusal is the finding; record it honestly.
  New files ONLY: scripts/ev_timing_probe.py, the evidence JSON, one docs/index.md row.

STOP CONDITIONS and end-report format: batch 1's, unchanged, plus: never wait for the
campaign — report Features 20–21 as pending if the precondition holds them.
```

Batch-4 claims run Phase 56–60; the primary session owns numbers below 40 and the
reconciliation passes.
